# -*- coding: utf-8 -*-
"""A bulk change to many people's details is a proposal first.

WHAT WAS TRUE BEFORE. The Records Desk wrote. Somebody picked four hundred
people, typed a new bank account or a new salary, pressed Apply, and four
hundred records changed — with a perfect audit trail of a thing nobody had
agreed to. The trail answered "who did this?" and never "who said yes?".

WHAT IS TRUE NOW. Apply evaluates, writes the plan down, and asks. The
`pb.records.apply` row is the proposal: it carries the plan, the counts, and
whether the change touches bank details or salary — the two facts a route
almost always wants to condition on. It travels the "Records Desk bulk
changes" route; nothing is written until it is approved.

THE SNAPSHOT IS THE POINT. The plan stores the value each field held WHEN THE
PROPOSAL WAS MADE. At apply time the desk re-evaluates against the values as
they are NOW and compares. A row somebody else moved in between is not written
— and because a half-applied bulk change is worse than none, ONE such row
sends the whole proposal back with that row named. Undo already worked exactly
this way over `pb.records.change`; this is the same promise one step earlier.

FAST LANE. A company that publishes "No approval needed" for this process gets
the old behaviour back, press for press — and still gets the proposal row,
marked applied, so the trail exists either way.
"""

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: The catalogue key this model is approved under.
RECORDS_PROCESS_KEY = 'records'



class PbRecordsApply(models.Model):
    _name = 'pb.records.apply'
    _inherit = ['pb.records.apply', 'biz.approval.adapter.mixin']

    _approval_process_key = RECORDS_PROCESS_KEY

    #: The evaluated plan, with the value every field held at proposal time.
    plan_json = fields.Text(string='The plan (JSON)', readonly=True)
    #: What was asked for, so the plan can be re-evaluated rather than trusted.
    changes_json = fields.Text(string='What was asked for (JSON)',
                               readonly=True)
    applied = fields.Boolean(string='Carried out', readonly=True, copy=False)
    applied_at = fields.Datetime(readonly=True, copy=False)
    touches_bank = fields.Boolean(string='Changes bank details', readonly=True)
    touches_salary = fields.Boolean(string='Changes pay', readonly=True)
    people_count = fields.Integer(string='People in the plan', readonly=True)
    values_count = fields.Integer(string='Values in the plan', readonly=True)
    company_id = fields.Many2one('res.company', index=True,
                                 default=lambda s: s.env.company)
    state = fields.Selection([
        ('draft', 'Being prepared'),
        ('pending', 'Waiting for approval'),
        ('applied', 'Carried out'),
        ('returned', 'Sent back'),
        ('rejected', 'Turned down'),
    ], default='draft', required=True, index=True, readonly=True, copy=False)
    block_note = fields.Text(string='Why it could not be carried out',
                             readonly=True, copy=False)
    #: The rows the WRITE itself refused — a contract component already kept as
    #: text, a badge id somebody else holds. They are found only while writing,
    #: so they cannot be in the plan; they are kept here because the desk's
    #: answer has always listed them and a proposal must not swallow them.
    refused_json = fields.Text(string='Refused while writing (JSON)',
                               readonly=True, copy=False)

    #: A seat is also a read (ledger AM60).
    seat_user_ids = fields.Many2many(
        'res.users', 'pb_records_apply_seat_rel', 'apply_id', 'user_id',
        string='Asked to decide', copy=False)

    # ------------------------------------------------------------- the plan
    def _waiting_for(self):
        """Whose desk this proposal is on right now, in names."""
        self.ensure_one()
        request = self.approval_request_id
        if not request:
            return ''
        step = request.step_ids.filtered(
            lambda s: s.key == request.current_step_key)[:1]
        names = sorted({seat.acting_user_id.name or ''
                        for seat in step.seat_ids if seat.status == 'open'})
        return ', '.join(n for n in names if n)

    def plan(self):
        self.ensure_one()
        try:
            rows = json.loads(self.plan_json or '[]')
        except (TypeError, ValueError):
            return []
        return rows if isinstance(rows, list) else []

    def late_refusals(self):
        """What the write itself refused, in the desk's own shape."""
        self.ensure_one()
        try:
            rows = json.loads(self.refused_json or '[]')
        except (TypeError, ValueError):
            return []
        return rows if isinstance(rows, list) else []

    def requested(self):
        self.ensure_one()
        try:
            rows = json.loads(self.changes_json or '[]')
        except (TypeError, ValueError):
            return []
        return rows if isinstance(rows, list) else []

    # ==================================================================
    # Adapter
    # ==================================================================
    def _approval_validate(self):
        self.ensure_one()
        if self.applied:
            raise UserError(_("This change has already been carried out."))
        if self.state == 'pending':
            raise UserError(_("This change has already been sent in."))
        if not self.plan():
            raise UserError(_("There is nothing in this change to approve."))
        return True

    def _subject_uids(self):
        self.ensure_one()
        ids = {int(row.get('emp_id') or 0) for row in self.plan()}
        ids.discard(0)
        if not ids:
            return []
        employees = self.env['hr.employee'].sudo().browse(sorted(ids)).exists()
        return sorted(set(employees.mapped('user_id').ids))

    def _divisions(self):
        """Which part(s) of the business the people in this plan sit in."""
        self.ensure_one()
        Division = self.env.get('pb.division')
        if Division is None:
            return []
        ids = {int(row.get('emp_id') or 0) for row in self.plan()}
        ids.discard(0)
        employees = self.env['hr.employee'].sudo().browse(sorted(ids)).exists()
        found = set()
        on_date = fields.Date.context_today(self)
        for department in employees.mapped('department_id'):
            try:
                division = Division.division_for(department, on_date)
            except Exception:       # noqa: BLE001 — a scope must never raise
                division = None
            found.add(division.id if division else 0)
        return sorted(d for d in found if d)

    def _approval_context(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        # A change that stays inside ONE part of the business can be decided
        # there. One that crosses two cannot honestly be given to either, so it
        # goes to the company route.
        divisions = self._divisions()
        scope_keys = ['division:%s' % divisions[0], ''] \
            if len(divisions) == 1 else ['']
        scope_label = company.name
        if len(divisions) == 1:
            division = self.env['pb.division'].sudo().browse(divisions[0])
            scope_label = division.name or company.name
        facts = {
            'people': {'value': self.people_count, 'unit': ''},
            'values': {'value': self.values_count, 'unit': ''},
            'touches_bank': {'value': bool(self.touches_bank), 'unit': ''},
            'touches_salary': {'value': bool(self.touches_salary), 'unit': ''},
            'source': {'value': self.source or 'desk', 'unit': ''},
        }
        return {
            'company_id': company.id,
            'title': _("Records change · %(n)s people · %(v)s values",
                       n=self.people_count, v=self.values_count),
            'scope_keys': scope_keys,
            'scope_label': scope_label,
            'kind_key': self.source or 'desk',
            'facts': facts,
            'amount': 0.0,
            'currency_id': company.currency_id.id,
            'maker_uids': [self.user_id.id] if self.user_id else [],
            'submitter_uid': self.env.uid,
            'subject_uids': self._subject_uids(),
            # The plan IS the thing being approved, so the stamp is over the
            # plan — every person, every field, every before and after.
            'source_revision': self._approval_revision_of(self.plan()),
            'evidence': [{
                'key': 'reason_given', 'name': _('A reason was written down'),
                'ok': bool((self.note or '').strip()),
                'note': (self.note or '')[:240]}],
        }

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'people': {'type': 'int', 'label': _('People affected')},
                'values': {'type': 'int', 'label': _('Values changed')},
                'touches_bank': {'type': 'bool',
                                 'label': _('Changes bank details')},
                'touches_salary': {'type': 'bool',
                                   'label': _('Changes pay')},
                'source': {'type': 'selection', 'label': _('Where it came from')},
            },
            'kinds': [{'key': 'desk', 'label': _('Typed on the desk')},
                      {'key': 'import', 'label': _('From a file')}],
            'evidence': [{'key': 'reason_given',
                          'label': _('A reason was written down')}],
            'scope_levels': [_('Division')],
            'manager_mode': False,
        }

    @api.model
    def _approval_coverage_scopes(self, company):
        """Every part of the business a bulk change can happen in.

        `pb.division` HAS NO `company_id`. Which companies a division belongs
        to is worked out from its department links and lives in a computed,
        non-stored `company_ids` — so it cannot be searched on, and a domain
        that tries raises `Invalid field pb.division.company_id`. The
        configuration module's own division picker reads the same way: search
        them all, then filter in Python (`matrix_facade._capabilities`).
        """
        rows = []
        Division = self.env.get('pb.division')
        if Division is not None:
            for division in Division.sudo().search([], limit=200,
                                                   order='name'):
                companies = division.company_ids
                if companies and company not in companies:
                    continue
                rows.append({
                    'scope_key': 'division:%s' % division.id,
                    'scope_keys': ['division:%s' % division.id, ''],
                    'label': division.name or '',
                    'headcount': 0, 'kind_key': 'desk', 'facts': {},
                })
        if not rows:
            rows.append({'scope_key': '', 'scope_keys': [''],
                         'label': company.name, 'headcount': 0,
                         'kind_key': 'desk', 'facts': {}})
        return rows

    def _approval_card_count(self, request):
        self.ensure_one()
        if self.people_count == 1:
            return _("1 person")
        return _("%s people", self.people_count)

    def _approval_detail(self, request):
        """Every value that would change, before and after."""
        self.ensure_one()
        rows = []
        for row in self.plan()[:40]:
            if not isinstance(row, dict):
                continue
            rows.append({
                'head': str(row.get('emp_name') or '')[:40],
                'sub': str(row.get('field_label') or '')[:40],
                'cells': [str(row.get('old_label') or '')[:40],
                          str(row.get('new_label') or '')[:40]],
                'tone': 'on',
            })
        if not rows:
            return None
        chips = []
        if self.touches_bank:
            chips.append({'label': _('Bank details'), 'value': _('Yes')})
        if self.touches_salary:
            chips.append({'label': _('Pay'), 'value': _('Yes')})
        chips.append({'label': _('Values'), 'value': str(self.values_count)})
        note = self.note or ''
        if self.values_count > len(rows):
            note = (note + ' ' if note else '') + _(
                "Showing the first %(shown)s of %(total)s values.",
                shown=len(rows), total=self.values_count)
        return {
            'title': _('What would change'),
            'columns': [_('Now'), _('Proposed')],
            'rows': rows,
            'chips': chips,
            'note': note,
        }

    # ------------------------------------------------------- the transitions
    def _approval_freeze(self, request):
        self.ensure_one()
        self.sudo().write({'state': 'pending', 'block_note': False})
        return True

    def _approval_return(self, request, reason):
        self.ensure_one()
        self.sudo().write({'state': 'returned'})
        return True

    def _approval_reject(self, request, reason):
        self.ensure_one()
        self.sudo().write({'state': 'rejected'})
        return True

    def _approval_apply(self, request):
        """Write the plan — all of it, or none of it."""
        self.ensure_one()
        if self.applied:
            return True
        Desk = self.env['pb.records.desk']
        moved = Desk._plan_moved_since(self)
        if moved:
            names = '; '.join(moved[:5])
            more = _(" and %s more", len(moved) - 5) if len(moved) > 5 else ''
            self.sudo().write({'block_note': _(
                "These have been changed by somebody else since this was "
                "proposed, so nothing was written: %(names)s%(more)s.",
                names=names, more=more)})
            raise UserError(_(
                "Nothing was changed. Somebody else has already changed "
                "%(n)s of these values since this was proposed: "
                "%(names)s%(more)s. Send this back and propose it again "
                "against what is there now.",
                n=len(moved), names=names, more=more))
        written, people, refused = Desk._write_plan(self)
        self.sudo().write({
            'applied': True,
            'applied_at': fields.Datetime.now(),
            'state': 'applied',
            'count_values': written,
            'count_people': len(people),
            'refused_json': json.dumps(refused),
            'block_note': '; '.join(r['why'] for r in refused)[:1024] or False,
        })
        return True

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        return self.env['biz.approval.seed'].lay(
            company, RECORDS_PROCESS_KEY, 'Records Desk changes',
            _records_definition(),
            binding_note='The route every bulk change to people\'s details '
                         'follows unless a part of the business is given its '
                         'own.',
            model_name='pb.records.apply',
            role_keys=('hr_lead', 'finance'),
            reason='Set up when Records Desk approvals were switched on')


def _records_definition():
    """The HR lead always; Finance only when money is involved.

    The condition is the whole point of the default: a business should not
    have to choose between checking every address change and checking no bank
    account at all.
    """
    return {
        'schema_version': 1,
        'steps': [
            {'key': 's1', 'kind': 'approve', 'title': 'HR lead',
             'who': {'mode': 'role', 'role': 'hr_lead', 'scope': 'area'},
             'min_amount': 0, 'condition': None},
            {'key': 's2', 'kind': 'approve', 'title': 'Finance approver',
             'who': {'mode': 'role', 'role': 'finance', 'scope': 'company'},
             'min_amount': 0,
             'condition': {'fact': 'touches_bank', 'op': 'eq', 'value': True}},
        ],
        'tiers': {'enabled': False, 'fact': None},
        'safeguards': {
            'independent': True,
            'self_exception': {'enabled': False},
            'repeated': 'different',
            'evidence': [],
            'due': {'kind': 'working_days', 'days': 2, 'day': 15,
                    'calendar_id': None},
            'late': {'remind_days': 1, 'escalate_days': 2, 'reassign': False},
        },
    }


class BizApprovalRequestSeatRecords(models.Model):
    """A seat on a records change is also a permission to READ it (AM60)."""
    _inherit = 'biz.approval.request.seat'

    @api.model_create_multi
    def create(self, vals_list):
        seats = super().create(vals_list)
        for seat in seats:
            request = seat.step_id.request_id
            if request.res_model != 'pb.records.apply' or not request.res_id:
                continue
            record = self.env['pb.records.apply'].sudo().browse(
                request.res_id).exists()
            people = {seat.acting_user_id.id, seat.user_id.id}
            people.discard(False)
            if record and people:
                record.write({
                    'seat_user_ids': [(4, uid) for uid in sorted(people)]})
        return seats


class ResCompanyRecordsSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.records.apply']._approval_seed_default(company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('pb_records: %s has no records route yet',
                                  company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.records.apply']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an install must not die here
            _logger.exception('pb_records: %s has no records route yet',
                              company.name)
    _logger.info('pb_records: %s companies have a records route', done)
    return done


def post_init_hook(env):
    seed_all(env)
