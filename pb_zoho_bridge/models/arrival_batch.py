# -*- coding: utf-8 -*-
"""What arrives from the connected system waits for a person.

WHAT WAS TRUE BEFORE. A push from the connected HR system created employees,
created their logins, updated people's details and started leaving checklists —
straight away, from an unauthenticated endpoint validated only by a shared
token. The rules decided and Payobook did it. Anybody who could reach the
webhook with the right token could add a person to the payroll.

WHAT IS TRUE NOW. The rules still decide, exactly as they did — nothing about
matching, triggers or rule evaluation is changed. What changes is that the
three decisions that WRITE (update, onboard, offboard) are written down instead
of carried out, collected into one `pb.zoho.arrival.batch`, and sent for
approval. `ignore` and `review` still happen immediately: neither of them
changes a record, and a row put aside for somebody to look at is already
waiting for a person.

RE-DIFFED AT APPLY. A row is executed against the person as they are on the day
it is approved, not as they were when it arrived. Somebody whose record has
moved in between is SKIPPED with a note rather than overwritten — the rule that
governs every other arrival in the product ("HR's own answer wins") one step
further out.

FAST LANE. A company that publishes "No approval needed" gets yesterday's
behaviour back, push for push — and still gets the batch row, so what arrived
and what it did is on one record either way.
"""

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: The catalogue key this model is approved under.
ARRIVALS_PROCESS_KEY = 'arrivals'

#: The decisions that write. Everything else happens the moment it arrives.
DEFERRED_ACTIONS = ('update', 'onboard', 'offboard')

STATES = [
    ('draft', 'Being prepared'),
    ('pending', 'Waiting for approval'),
    ('applied', 'Carried out'),
    ('returned', 'Sent back'),
    ('rejected', 'Turned down'),
]


class PbZohoArrivalBatch(models.Model):
    _name = 'pb.zoho.arrival.batch'
    _inherit = ['biz.approval.adapter.mixin']
    _description = 'Arrivals Waiting for Approval'
    _order = 'id desc'

    _approval_process_key = ARRIVALS_PROCESS_KEY

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda s: s.env.company)
    source = fields.Selection([('webhook', 'Pushed to us'),
                               ('file', 'From a file'),
                               ('pull', 'Fetched by us')],
                              default='webhook', required=True)
    rows_json = fields.Text(string='What arrived (JSON)', readonly=True)
    row_count = fields.Integer(readonly=True)
    onboards = fields.Integer(readonly=True)
    offboards = fields.Integer(readonly=True)
    updates = fields.Integer(readonly=True)
    creates_logins = fields.Boolean(
        string='Would create sign-ins', readonly=True,
        help="At least one new person in this batch would be given a way to "
             "sign in to Payobook.")
    applied_at = fields.Datetime(readonly=True, copy=False)
    apply_note = fields.Text(readonly=True, copy=False)
    state = fields.Selection(STATES, default='draft', required=True,
                             index=True, readonly=True, copy=False)

    #: A seat is also a read (ledger AM60).
    seat_user_ids = fields.Many2many(
        'res.users', 'pb_zoho_arrival_seat_rel', 'batch_id', 'user_id',
        string='Asked to decide', copy=False)

    @api.depends('row_count', 'create_date')
    def _compute_name(self):
        for rec in self:
            rec.name = _("Arrivals · %s people", rec.row_count)

    def rows(self):
        self.ensure_one()
        try:
            rows = json.loads(self.rows_json or '[]')
        except (TypeError, ValueError):
            return []
        return rows if isinstance(rows, list) else []

    def _waiting_for(self):
        self.ensure_one()
        request = self.approval_request_id
        if not request:
            return ''
        step = request.step_ids.filtered(
            lambda s: s.key == request.current_step_key)[:1]
        names = sorted({seat.acting_user_id.name or ''
                        for seat in step.seat_ids if seat.status == 'open'})
        return ', '.join(n for n in names if n)

    # ==================================================================
    # Building one
    # ==================================================================
    @api.model
    def collect(self, rows, source, company):
        """Write down what the rules decided, and ask.

        Returns the batch, or an empty recordset when there was nothing to
        defer. The submission runs AS A NAMED PERSON even when the push came
        in over an unauthenticated webhook: `with_user(...).sudo()` and not one
        or the other, so the record rule is lifted without the trail losing the
        honest name (ledger AM26).
        """
        if not rows:
            return self.browse()
        onboards = len([r for r in rows if r.get('action') == 'onboard'])
        offboards = len([r for r in rows if r.get('action') == 'offboard'])
        updates = len([r for r in rows if r.get('action') == 'update'])
        batch = self.sudo().create({
            'company_id': company.id,
            'source': source if source in ('webhook', 'file', 'pull')
            else 'webhook',
            'rows_json': json.dumps(rows, default=str),
            'row_count': len(rows),
            'onboards': onboards,
            'offboards': offboards,
            'updates': updates,
            'creates_logins': any(r.get('creates_login') for r in rows),
        })
        publisher = self.env['biz.approval.seed'].publisher_for(company)
        engine = self.env['biz.approval.engine'].with_user(publisher).sudo()
        engine.submit(batch)
        batch.invalidate_recordset()
        return batch

    # ==================================================================
    # Adapter
    # ==================================================================
    def _approval_validate(self):
        self.ensure_one()
        if self.state in ('pending', 'applied'):
            raise UserError(_("These arrivals have already been sent in."))
        if not self.rows():
            raise UserError(_("There is nothing in this batch to approve."))
        return True

    def _approval_context(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        subjects = [int(r.get('employee_id') or 0) for r in self.rows()]
        employees = self.env['hr.employee'].sudo().browse(
            sorted({s for s in subjects if s})).exists()
        return {
            'company_id': company.id,
            'title': self.name or _('Arrivals'),
            'scope_keys': [''],
            'scope_label': company.name,
            'kind_key': self.source or 'webhook',
            'facts': {
                'rows': {'value': self.row_count, 'unit': ''},
                'onboards': {'value': self.onboards, 'unit': ''},
                'offboards': {'value': self.offboards, 'unit': ''},
                'updates': {'value': self.updates, 'unit': ''},
                'creates_logins': {'value': bool(self.creates_logins),
                                   'unit': ''},
            },
            'amount': 0.0,
            'currency_id': company.currency_id.id,
            # Nobody in Payobook prepared this: it was decided by the rules
            # from what another system sent. The submitter is whoever the
            # arrival is being asked about ON BEHALF OF, and there is no maker.
            'maker_uids': [],
            'submitter_uid': self.env.uid,
            'subject_uids': sorted(set(employees.mapped('user_id').ids)),
            'source_revision': self._approval_revision_of(
                [(r.get('event_id') or '', r.get('action') or '')
                 for r in self.rows()]),
            'evidence': [],
        }

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'rows': {'type': 'int', 'label': _('People in this batch')},
                'onboards': {'type': 'int', 'label': _('Joining')},
                'offboards': {'type': 'int', 'label': _('Leaving')},
                'updates': {'type': 'int', 'label': _('Details changing')},
                'creates_logins': {'type': 'bool',
                                   'label': _('Would create sign-ins')},
            },
            'kinds': [{'key': 'webhook', 'label': _('Pushed to us')},
                      {'key': 'file', 'label': _('From a file')},
                      {'key': 'pull', 'label': _('Fetched by us')}],
            'evidence': [],
            'scope_levels': [],
            'manager_mode': False,
        }

    @api.model
    def _approval_coverage_scopes(self, company):
        return [{'scope_key': '', 'scope_keys': [''], 'label': company.name,
                 'headcount': 0, 'kind_key': 'webhook', 'facts': {}}]

    def _approval_card_count(self, request):
        self.ensure_one()
        if self.row_count == 1:
            return _("1 person")
        return _("%s people", self.row_count)

    def _approval_detail(self, request):
        self.ensure_one()
        labels = {'update': _('Details change'), 'onboard': _('Joining'),
                  'offboard': _('Leaving')}
        rows = []
        for row in self.rows()[:40]:
            rows.append({
                'head': str(row.get('person_name') or '')[:40],
                'sub': str(row.get('employee_number') or '')[:40],
                'cells': [labels.get(row.get('action'), row.get('action') or '')],
                'tone': 'warn' if row.get('action') == 'offboard' else 'on',
            })
        if not rows:
            return None
        chips = []
        if self.creates_logins:
            chips.append({'label': _('Creates sign-ins'), 'value': _('Yes')})
        return {
            'title': _('Who is in this batch'),
            'columns': [_('What would happen')],
            'rows': rows,
            'chips': chips,
            'note': (_("Showing the first %(shown)s of %(total)s.",
                       shown=len(rows), total=self.row_count)
                     if self.row_count > len(rows) else ''),
        }

    # ------------------------------------------------------- the transitions
    def _approval_freeze(self, request):
        self.ensure_one()
        self.sudo().write({'state': 'pending'})
        return True

    def _approval_return(self, request, reason):
        self.ensure_one()
        self.sudo().write({'state': 'returned'})
        return True

    def _approval_reject(self, request, reason):
        """Turned down: every row is recorded as decided against, not lost."""
        self.ensure_one()
        self.sudo().write({'state': 'rejected'})
        self.env['pb.zoho.pipeline'].sudo()._log_rejected_rows(
            self, reason or '')
        return True

    def _approval_apply(self, request):
        self.ensure_one()
        if self.state == 'applied':
            return True
        summary = self.env['pb.zoho.pipeline'].sudo()._apply_rows(self)
        self.sudo().write({
            'state': 'applied',
            'applied_at': fields.Datetime.now(),
            'apply_note': json.dumps(summary, default=str),
        })
        return True

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        return self.env['biz.approval.seed'].lay(
            company, ARRIVALS_PROCESS_KEY, 'Arrivals from a connected system',
            _arrivals_definition(),
            binding_note='The route everything the connected system sends '
                         'follows.',
            model_name='pb.zoho.arrival.batch',
            role_keys=('hr_lead',),
            reason='Set up when arrival approvals were switched on')


def _arrivals_definition():
    """One step: the HR lead looks at who is joining, leaving and changing."""
    return {
        'schema_version': 1,
        'steps': [{
            'key': 's1', 'kind': 'approve', 'title': 'HR lead',
            'who': {'mode': 'role', 'role': 'hr_lead', 'scope': 'company'},
            'min_amount': 0, 'condition': None,
        }],
        'tiers': {'enabled': False, 'fact': None},
        'safeguards': {
            # NOT independent. Nobody in Payobook prepared this — the rules
            # decided it from what another system sent — so there is no
            # conflict for the rule to find, and leaving it on would block an
            # HR lead from approving an arrival about themselves for no
            # reason anybody could act on.
            'independent': False,
            'self_exception': {'enabled': False},
            'repeated': 'different',
            'evidence': [],
            'due': {'kind': 'working_days', 'days': 1, 'day': 15,
                    'calendar_id': None},
            'late': {'remind_days': 1, 'escalate_days': 2, 'reassign': False},
        },
    }


class BizApprovalRequestSeatArrivals(models.Model):
    """A seat on an arrivals batch is also a permission to READ it (AM60)."""
    _inherit = 'biz.approval.request.seat'

    @api.model_create_multi
    def create(self, vals_list):
        seats = super().create(vals_list)
        for seat in seats:
            request = seat.step_id.request_id
            if request.res_model != 'pb.zoho.arrival.batch' \
                    or not request.res_id:
                continue
            batch = self.env['pb.zoho.arrival.batch'].sudo().browse(
                request.res_id).exists()
            people = {seat.acting_user_id.id, seat.user_id.id}
            people.discard(False)
            if batch and people:
                batch.write({
                    'seat_user_ids': [(4, uid) for uid in sorted(people)]})
        return seats


class ResCompanyArrivalsSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.zoho.arrival.batch']._approval_seed_default(
                    company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('pb_zoho_bridge: %s has no arrivals route '
                                  'yet', company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.zoho.arrival.batch']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an install must not die here
            _logger.exception('pb_zoho_bridge: %s has no arrivals route yet',
                              company.name)
    return done


def post_init_hook(env):
    seed_all(env)
