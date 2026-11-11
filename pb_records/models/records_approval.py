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

import pytz
from psycopg2 import errors as pg_errors

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError
from odoo.modules import module as odoo_module
from odoo.tools.misc import format_date

from odoo.addons.biz_approval_workflow.models import definition as D

_logger = logging.getLogger(__name__)

#: The catalogue key this model is approved under.
RECORDS_PROCESS_KEY = 'records'
#: UPDATES P3a (D3) — bank details travel a route of their own: a second
#: person, always. "No approval needed" on the records route never reaches it.
RECORDS_BANK_PROCESS_KEY = 'records_bank'

#: UPDATES P3a — the three lanes one proposal is split into.
LANES = [
    ('details', 'Personal details'),
    ('pay', 'Pay and contract'),
    ('bank', 'Bank details'),
]
#: Employee fields that are PAY, not personal details. Reviewed one by one
#: against `_master_fields()` (P3a report §R2): the only employee field the
#: old word match (`SALARY_TOKENS`) treated as pay is "Payroll Country", which
#: decides whose payroll rules apply. The dependants count (pay-relevant: it
#: sets the personal income tax allowance) is read-only on the record and can
#: never be written from a file, so it is listed for completeness only.
PAY_EMPLOYEE_FIELDS = frozenset({
    'f:hr.employee:payroll_country',
    'f:hr.employee:vn_dependent_record_count',
})

#: Content fields of a proposal that only the desk itself (under sudo) may
#: write: a client that rewrote them could move a bank change onto a route
#: with no second person.
GUARDED_FIELDS = frozenset({'plan_json', 'changes_json', 'lane', 'user_id',
                            'company_id', 'config_id', 'details_now',
                            'touches_bank'})


def lane_of(field_id):
    """UPDATES P3a — which lane a desk card id belongs to. By the id alone,
    so a stored plan can always be laned again without the catalogue."""
    fid = str(field_id or '')
    if fid.startswith('b:'):
        return 'bank'
    if fid.startswith('c:') or fid.startswith('f:hr.contract:') \
            or fid in PAY_EMPLOYEE_FIELDS:
        return 'pay'
    return 'details'


def _behaviour(definition):
    """What a route DOES, without its words: who decides each step, on what
    condition, and whether the independence rule is on. Titles, due dates
    and reminders are left out — renaming a step is not a different route."""
    d = D.normalise(definition)
    steps = [(s['kind'], json.dumps(s.get('who') or {}, sort_keys=True),
              json.dumps(s.get('condition'), sort_keys=True),
              float(s.get('min_amount') or 0))
             for s in d['steps'] if s['kind'] != 'notify']
    return (steps, bool(d['tiers'].get('enabled')),
            bool(d['safeguards'].get('independent')))


def route_kind(definition):
    """`fast` (nobody checks), `default` (the shipped records route, as
    laid) or `custom` (somebody set up their own)."""
    d = D.normalise(definition)
    active = [s for s in d['steps'] if s['kind'] != 'notify']
    if not active or any(s['kind'] == 'fast' for s in active):
        return 'fast'
    if _behaviour(d) == _behaviour(_records_definition()):
        return 'default'
    return 'custom'

#: UPDATES P2c — a start date can be at most this many days back or ahead.
START_DATE_REACH = 366

#: Row-lock failures: somebody else is writing this proposal right now.
LOCK_ERRORS = (pg_errors.LockNotAvailable, pg_errors.SerializationFailure)


class _WriteRefused(Exception):
    """A scheduled write found a row it could not write: nothing is kept."""

    def __init__(self, refused):
        super().__init__('refused while writing')
        self.refused = refused



class PbRecordsApply(models.Model):
    _name = 'pb.records.apply'
    _inherit = ['pb.records.apply', 'biz.approval.adapter.mixin']

    _approval_process_key = RECORDS_PROCESS_KEY
    #: UPDATES P3a — one model, two catalogue rows: a bank-details change is
    #: approved under its own key (precedent: the pay data file's
    #: `runonly`/`loads`, `payroll_import_approval.py`).
    _approval_process_keys = (RECORDS_PROCESS_KEY, RECORDS_BANK_PROCESS_KEY)

    #: UPDATES P3a — which lane this proposal is (empty on proposals made
    #: before lanes existed, and on the desk's own undo rows).
    lane = fields.Selection(LANES, string='Lane', readonly=True, copy=False,
                            index=True)
    #: UPDATES P3a — personal details from a sheet, carried out at once with
    #: no approval because the company's records route is the shipped one or
    #: "No approval needed" (and its switch is on).
    details_now = fields.Boolean(string='Applied without approval',
                                 readonly=True, copy=False)

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
        # UPDATES P2c — approved, and waiting for its start date.
        ('scheduled', 'Scheduled'),
        ('applied', 'Carried out'),
        ('returned', 'Sent back'),
        ('rejected', 'Turned down'),
        # UPDATES P2c — stopped before anything was written.
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, index=True, readonly=True, copy=False)
    block_note = fields.Text(string='Why it could not be carried out',
                             readonly=True, copy=False)

    # ------------------------------------------------ UPDATES P2c — dates
    #: Empty = "today, as before". A past date is a RECORD of when the change
    #: started (written now, history stamped with it); a future date holds the
    #: approved change as "Scheduled" until the job writes it on the day.
    start_date = fields.Date(string='Starts on', readonly=True, copy=False,
                             index=True)
    #: What a future date holds back. Updates splits a file by it; the desk
    #: keeps it as the record of what was asked.
    hold_scope = fields.Selection([
        ('pay', 'Pay and contract changes wait'),
        ('all', 'Everything waits'),
    ], string='What waits for the start date', default='pay', readonly=True,
        copy=False)
    started_by_job = fields.Boolean(string='Started automatically',
                                    readonly=True, copy=False)
    started_by_id = fields.Many2one('res.users', string='Started by',
                                    readonly=True, copy=False)
    cancelled_at = fields.Datetime(string='Cancelled at', readonly=True,
                                   copy=False)
    cancelled_by_id = fields.Many2one('res.users', string='Cancelled by',
                                      readonly=True, copy=False)
    #: Days the scheduled job could not start it (one bad day counts once).
    start_fail_days = fields.Integer(string='Days it could not start',
                                     readonly=True, copy=False)
    start_last_fail = fields.Date(string='Last day it could not start',
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

    # ============================================ UPDATES P3a — the bank lane
    def write(self, vals):
        """A proposal's content is the desk's to write, never a client's.

        Its plan, what was asked for, its lane, proposer and company decide
        which route it travels and what is written on approval. The desk
        writes them under `sudo()`; anybody else (an RPC call with only HR
        rights) is refused, so a bank change can never be re-labelled onto a
        route with no second person."""
        if not self.env.su and GUARDED_FIELDS.intersection(vals):
            raise UserError(_("A proposed change cannot be edited. Cancel it "
                              "and propose it again."))
        return super().write(vals)

    def _has_bank(self):
        """Does this proposal carry any bank-details value? Read off the
        CONTENT (the plan and what was asked for), never only the lane label:
        whatever route it is on, a bank value needs a second person."""
        self.ensure_one()
        if self.lane == 'bank':
            return True
        rows = self.plan() + self.requested()
        return any(str((r or {}).get('field_id') or '').startswith('b:')
                   for r in rows if isinstance(r, dict))

    def _bank_rule_applies(self, request=None):
        """Is this proposal held to the second-person rule? Every bank
        proposal made from P3a on (it carries a lane, which nobody can edit),
        and every one travelling the bank route. A proposal sent in BEFORE
        lanes existed keeps the route and the rules it was sent in under —
        it is never changed under somebody's feet (sudima had one waiting on
        the day this shipped)."""
        self.ensure_one()
        if not self._has_bank():
            return False
        if self.lane:
            return True
        request = request or self.approval_request_id
        return not request or request.sudo().process_id.key == RECORDS_BANK_PROCESS_KEY

    def _approval_process_key_for(self):
        self.ensure_one()
        return RECORDS_BANK_PROCESS_KEY if self._has_bank() \
            else RECORDS_PROCESS_KEY

    def _proposer(self):
        self.ensure_one()
        return self.user_id or self.create_uid

    @api.model
    def _records_managers(self, company):
        """People who look after records: HR managers, payroll managers and
        system administrators (the P2c reading of "Records manager"), with a
        staff login in this company. Never a background account."""
        users = self.env['res.users'].sudo().browse()
        for xmlid in ('hr.group_hr_manager',
                      'pb_hr_payroll_base.group_payroll_base_manager',
                      'base.group_system'):
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                users |= group.sudo().all_user_ids
        return users.filtered(
            lambda u: u.active and not u.share and u.id != SUPERUSER_ID
            and company.id in u.company_ids.ids).sorted('id')

    @api.model
    def _finance_holders(self, company):
        role = self.env['biz.approval.role'].sudo().search(
            [('key', '=', 'finance')], limit=1)
        if not role:
            return self.env['res.users']
        rows = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', company.id), ('role_id', '=', role.id)])
        users = self.env['res.users']
        for row in rows:
            users |= row.user_id | row.backup_user_id
            if 'pool_user_ids' in row._fields:
                users |= row.pool_user_ids
        return users.filtered(lambda u: u.active and not u.share
                              and company.id in u.company_ids.ids)

    @api.model
    def _second_people(self, company, proposer):
        """`(users, via)` who may approve somebody else's bank change: the
        Finance holders first, else any Records manager — never the
        proposer."""
        finance = self._finance_holders(company) - proposer
        if finance:
            return finance.sorted('id')[:20], _("Finance approver")
        managers = self._records_managers(company) - proposer
        return managers[:20], _("A second person (records manager)")

    def _note_second_person(self):
        """Say on the request itself, where the proposer reads it, that a
        bank change needs somebody else — not as a refusal, as the rule."""
        self.ensure_one()
        request = self.sudo().approval_request_id
        if not request or request.state not in ('pending', 'blocked'):
            return False
        notes = list(request.seat_notes or [])
        if any(n.get('code') == 'second_person' for n in notes):
            return False
        notes.append({'code': 'second_person', 'msg': _(
            "Bank details need a second person: %s proposed this change, so "
            "somebody else approves it.", self._proposer().name or '')})
        request.sudo().write({'seat_notes': notes})
        return True

    def _nobody_else_sentence(self, company=None):
        company = company or self.company_id or self.env.company
        return _("Waiting for a second person. Nobody else in %s can approve "
                 "bank details yet — add one in Access.", company.name)

    def _approval_step_people(self, step, people, issue, ctx, company):
        """UPDATES P3a — opt-in engine hook (`records_engine.py`): who may
        decide a step of THIS proposal. Only a bank-details proposal answers
        anything different: the proposer is never one of them (their backup
        stands in when the route named them), and when the route names
        nobody else, the second person is found — Finance, else a records
        manager. Nobody at all: the request waits, and says why."""
        self.ensure_one()
        rec = self.sudo()
        if not rec._bank_rule_applies():
            return people, issue
        proposer = rec._proposer()
        engine = self.env['biz.approval.engine']
        keep = []
        for person in people or []:
            if person.get('user_id') != proposer.id:
                keep.append(person)
                continue
            backup = person.get('backup_user_id')
            if backup and backup != proposer.id:
                keep += engine._people_payload(
                    [backup], _("Backup for %s, who proposed this change",
                                person.get('name') or ''))
        # Only a staff login can decide: a self-service (portal) login named
        # on the route (a demo Finance holder, say) cannot open the request.
        staff = set(self.env['res.users'].sudo().browse(
            [p['user_id'] for p in keep]).exists().filtered(
                lambda u: not u.share).ids)
        keep = [p for p in keep if p.get('active', True) and p['user_id'] in staff]
        if keep:
            blocking = issue and issue.get('level') == 'block'
            return keep, (None if blocking else issue)
        users, via = rec._second_people(company, proposer)
        if users:
            return engine._people_payload(users.ids, via), None
        return [], {'level': 'block', 'code': 'no_second_person',
                    'msg': rec._nobody_else_sentence(company), 'fixes': []}

    def _approval_may_decide(self, request, user):
        """UPDATES P3a — opt-in engine hook: a sentence when `user` may not
        APPROVE this proposal, else None. Bank details are never approved by
        the person who proposed them — whatever seat they hold."""
        self.ensure_one()
        rec = self.sudo()
        if rec._bank_rule_applies(request) and user == rec._proposer():
            return _("Bank details need a second person. You proposed this "
                     "change, so somebody else has to approve it.")
        return None

    def _second_person_approved(self, request=None):
        """Has somebody other than the proposer approved this request?"""
        self.ensure_one()
        request = request or self.approval_request_id
        if not request:
            return False
        proposer = self._proposer()
        return bool(request.sudo().decision_ids.filtered(
            lambda d: d.action == 'approve' and d.user_id
            and d.user_id != proposer))

    def _writer_desk(self):
        """The desk as the proposer (else the last approver), in the
        proposal's company first — the writer `_start_scheduled` uses."""
        self.ensure_one()
        rec = self.sudo()
        # Proposed by the system itself (a script, a test): it had every right.
        actor = rec.user_id if rec.user_id.id == SUPERUSER_ID else rec._start_user()
        mine = actor.sudo().company_ids.ids
        companies = [rec.company_id.id] if rec.company_id.id in mine else []
        companies += [c for c in mine if c not in companies]
        desk = self.env['pb.records.desk'].with_user(actor)
        if companies:
            desk = desk.with_context(allowed_company_ids=companies)
        return desk

    def _bank_refusal(self, request=None):
        """The fail-closed rail, checked wherever a proposal is WRITTEN:
        a bank value is never written without a second person's yes —
        whatever the route says (a "No approval needed" route on the bank
        key included), on its day, and on "Start now"."""
        self.ensure_one()
        if self._bank_rule_applies(request) and not self._second_person_approved(request):
            return _("Bank details need a second person. Nobody other than "
                     "the person who proposed this change has approved it, "
                     "so nothing was written.")
        return ''

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
        if self.state == 'cancelled' or self.undone:
            raise UserError(_("This change was cancelled, so nothing was "
                              "written."))
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

    def _headline(self):
        """What this change is, in words that survive the number being one.

        Found on the browser walk: the title read "Records change · 1 people ·
        1 values". A queue is read at a glance and bad grammar in it is read as
        a bug in the numbers.
        """
        self.ensure_one()
        if self._has_bank():
            # UPDATES P3a — the approvals inbox reads this first.
            return (_("Bank details for 1 person") if self.people_count == 1
                    else _("Bank details for %s people", self.people_count))
        people = (_("1 person") if self.people_count == 1
                  else _("%s people", self.people_count))
        values = (_("1 value") if self.values_count == 1
                  else _("%s values", self.values_count))
        return _("Records change · %(people)s · %(values)s",
                 people=people, values=values)

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
            'title': self._headline(),
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
            old, new = str(row.get('old_label') or ''), \
                str(row.get('new_label') or '')
            if row.get('field_id') == 'b:acc_number':
                # UPDATES P3a — an account number is shown to the approver
                # with only its last four characters.
                old, new = mask_account(old), mask_account(new)
            rows.append({
                'head': str(row.get('emp_name') or '')[:40],
                'sub': str(row.get('field_label') or '')[:40],
                'cells': [old[:40], new[:40]],
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

    def _approval_withdraw(self, request, reason):
        """UPDATES P2c — the request was withdrawn: the change stops waiting
        and can never be written later (the cancel defect, P2b §R7.3)."""
        self.ensure_one()
        if not self.applied and self.state != 'cancelled':
            self.sudo().write({'state': 'cancelled',
                               'cancelled_at': fields.Datetime.now(),
                               'cancelled_by_id': self.env.uid,
                               'block_note': False})
        return True

    def _moved_sentence(self, moved):
        """The existing "somebody else changed it" sentence, for block_note."""
        names = '; '.join(moved[:5])
        more = _(" and %s more", len(moved) - 5) if len(moved) > 5 else ''
        return _("These have been changed by somebody else since this was "
                 "proposed, so nothing was written: %(names)s%(more)s.",
                 names=names, more=more), names, more

    def _approval_apply(self, request):
        """Write the plan — all of it, or none of it.

        UPDATES P2c: a change that was cancelled (or "undone" before it was
        written — the old defect) is refused here, so a late approval can
        never write it. A change whose start date is still ahead is checked
        exactly as before and then HELD as "Scheduled": nothing is written
        until the job (or a person pressing "Start now") writes it.
        """
        self.ensure_one()
        if self.applied:
            return True
        if self.state == 'cancelled' or self.undone:
            raise UserError(_("This change was cancelled, so nothing was "
                              "written."))
        if self.state == 'scheduled':
            return True
        refusal = self._bank_refusal(request)
        if refusal:
            # UPDATES P3a — fails closed: the request reads "approved but
            # could not be carried out" with this sentence; nothing written.
            raise UserError(refusal)
        bank = self._bank_rule_applies(request)
        # UPDATES P3a — a bank change is WRITTEN with the proposer's rights
        # (the way a scheduled change is): the second person approves, and
        # may well be a Finance approver with no right to change employee
        # records — under their rights the evaluation would quietly find
        # nothing to write and the change would read "carried out".
        Desk = self._writer_desk() if bank else self.env['pb.records.desk']
        moved = Desk._plan_moved_since(self)
        if moved:
            note, names, more = self._moved_sentence(moved)
            self.sudo().write({'block_note': note})
            raise UserError(_(
                "Nothing was changed. Somebody else has already changed "
                "%(n)s of these values since this was proposed: "
                "%(names)s%(more)s. Send this back and propose it again "
                "against what is there now.",
                n=len(moved), names=names, more=more))
        if self.start_date and self.start_date > self._company_today():
            self.sudo().write({'state': 'scheduled', 'block_note': False})
            return True
        written, people, refused = Desk._write_plan(self)
        if bank and not written and self.plan():
            raise UserError(_(
                "Nothing could be written: none of these bank details can be "
                "saved any more. Send this back and propose it again."))
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

    # ==================================================================
    # UPDATES P2c — the start date, the job, "Start now" and Cancel
    # ==================================================================
    @api.model
    def _records_now(self):
        """UTC now. One seam, so a test can freeze the clock."""
        return fields.Datetime.now()

    @api.model
    def _today_for(self, company=None, user=None):
        """The date it is for a company: its address's time zone, else the
        person's, else UTC. "Is it the day yet" is the COMPANY's question —
        a change for a Jakarta office starts on Jakarta's morning."""
        company = company or self.env.company
        user = user or self.env.user
        zone = 'UTC'
        for tz in ((company.partner_id.tz if company else False),
                   (user.tz if user else False)):
            if tz and tz in pytz.all_timezones_set:
                zone = tz
                break
        now = pytz.utc.localize(self._records_now())
        return now.astimezone(pytz.timezone(zone)).date()

    def _company_today(self):
        self.ensure_one()
        return self._today_for(self.company_id or self.env.company,
                               self.user_id or self.env.user)

    def _start_user(self):
        """Who a scheduled write runs as: the proposer, so the audit names a
        person; the last approver if the proposer's login is gone; else the
        person running the job."""
        self.ensure_one()
        if self.user_id and self.user_id.active:
            return self.user_id
        request = self.approval_request_id
        if request:
            decisions = self.env['biz.approval.decision'].sudo().search(
                [('request_id', '=', request.id)], order='id desc')
            for decision in decisions:
                user = decision.create_uid
                if user and user.active and not user._is_public():
                    return user
        return self.env.user

    def _lock_row(self, wait=False):
        """Take this proposal's row lock. True when it is ours; False when
        somebody else (the job, or a person pressing Start now or Cancel) is
        on it this very moment. The job never waits (SKIP LOCKED); a person
        never waits either (NOWAIT) — they are told to look again."""
        self.ensure_one()
        self.env.flush_all()
        query = ('SELECT id FROM pb_records_apply WHERE id = %s FOR UPDATE '
                 + ('NOWAIT' if wait else 'SKIP LOCKED'))
        try:
            with self.env.cr.savepoint(flush=False):
                self.env.cr.execute(query, [self.id])
                got = self.env.cr.fetchone()
        except LOCK_ERRORS:
            return False
        self.invalidate_recordset()
        return bool(got)

    def _notify_proposer(self, note):
        """An activity for whoever proposed it — on the approval request, the
        proposal's mail-capable twin. Never an email: the activity is created
        quietly (`mail_activity_quick_update`), so a demo database with fake
        addresses sends nothing."""
        self.ensure_one()
        request = self.approval_request_id
        user = self.user_id
        if not request or not user or not user.active:
            return False
        todo = self.env.ref('mail.mail_activity_data_todo',
                            raise_if_not_found=False)
        try:
            with self.env.cr.savepoint():
                self.env['mail.activity'].sudo().with_context(
                    mail_activity_quick_update=True).create({
                        'res_model_id': self.env['ir.model']._get_id(
                            'biz.approval.request'),
                        'res_id': request.id,
                        'activity_type_id': todo.id if todo else False,
                        'summary': _("A scheduled change was not made: %s",
                                     self.name),
                        'note': self.block_note or '',
                        'user_id': user.id,
                        'date_deadline': self._company_today(),
                    })
        except Exception:   # noqa: BLE001 — a reminder must never undo the state
            _logger.exception('pb_records: no activity for %s', self.name)
            return False
        return True

    def _send_back(self, note):
        """Nothing written; the proposal is sent back with the reason and the
        proposer is told."""
        self.ensure_one()
        self.sudo().write({'state': 'returned', 'block_note': note})
        self.sudo()._notify_proposer(note)
        return True

    def _start_scheduled(self, by_job=False):
        """Write a scheduled change now. `(outcome, sentence)`.

        Shared by the hourly job (`by_job=True`) and "Start now". The SAME
        write as an approval: the moved-since check, then `_write_plan`, in
        one transaction — all of it or none of it. Three extra promises:

          * never twice: the row is locked first and the state read again,
            so the job and a person pressing "Start now" cannot both write;
          * never a subset: if the evaluation would now refuse a planned value
            (or add one nobody planned), or the write itself refuses one,
            nothing is kept;
          * never a guess: on the day, a conflict sends the change back with
            the reason; when a PERSON presses "Start now" a conflict only
            answers the reason and leaves it scheduled.

        Outcomes: `started`, `busy` (locked by somebody else), `gone` (no
        longer scheduled), `returned` (sent back), `refused` (Start now only).
        """
        self.ensure_one()
        if not self._lock_row(wait=not by_job):
            return 'busy', _("This change is being written right now. Look "
                             "again in a minute.")
        rec = self.sudo()
        if rec.applied or rec.undone or rec.state != 'scheduled':
            return 'gone', _("This change is no longer scheduled.")
        refusal = rec._bank_refusal()
        if refusal:
            # UPDATES P3a — a scheduled bank change is written on its day (or
            # by "Start now") only after a second person approved it.
            if by_job:
                rec._send_back(refusal)
                return 'returned', refusal
            return 'refused', refusal
        if by_job:
            actor = rec._start_user()
            effective = rec.start_date
        else:
            actor = self.env.user
            effective = rec._company_today()
        # The proposal's company first, then the actor's other companies —
        # never a company the actor may not use (a person moved since is
        # simply out of scope, and the change is sent back for it).
        mine = actor.sudo().company_ids.ids
        companies = [rec.company_id.id] if rec.company_id.id in mine else []
        companies += [c for c in mine if c not in companies]
        ctx = {'records_effective_date': fields.Date.to_string(effective)}
        if companies:
            ctx['allowed_company_ids'] = companies
        me = rec.with_user(actor).with_context(**ctx)
        Desk = me.env['pb.records.desk']._door_for(rec)

        moved = Desk._plan_moved_since(rec)
        problem = ''
        if moved:
            problem = rec._moved_sentence(moved)[0]
        else:
            lost, extra = Desk._plan_drift(rec)
            if lost or extra:
                bits = ['%s · %s: %s' % (i.get('emp_name') or '',
                                          i.get('field_label') or '',
                                          i.get('why') or '') for i in lost[:5]]
                bits += ['%s · %s' % (i.get('emp_name') or '',
                                      i.get('field_label') or '')
                         for i in extra[:5]]
                problem = _("These can no longer be written as they were "
                            "proposed, so nothing was written: %s.",
                            '; '.join(bits))
        if not problem:
            try:
                with self.env.cr.savepoint():
                    written, people, refused = Desk._write_plan(rec)
                    if refused:
                        raise _WriteRefused(refused)
            except _WriteRefused as exc:
                self.env.invalidate_all()
                problem = _("Nothing was written, because these could not be "
                            "saved: %s.", '; '.join(
                                r.get('why') or '' for r in exc.refused[:5]))
        if problem:
            if by_job:
                rec._send_back(problem)
                return 'returned', problem
            return 'refused', problem
        rec.write({
            'applied': True,
            'applied_at': fields.Datetime.now(),
            'state': 'applied',
            'count_values': written,
            'count_people': len(people),
            'refused_json': json.dumps([]),
            'block_note': False,
            'started_by_job': bool(by_job),
            'started_by_id': actor.id,
            'start_fail_days': 0,
        })
        return 'started', ''

    def _record_start_failure(self, error):
        """Something unexpected stopped the job on this one: it stays
        scheduled with a note and is tried again; on the third bad DAY it is
        sent back and the proposer is told. Never silent."""
        self.ensure_one()
        rec = self.sudo()
        today = rec._company_today()
        days = rec.start_fail_days or 0
        if rec.start_last_fail != today:
            days += 1
        vals = {'start_fail_days': days, 'start_last_fail': today,
                'block_note': _("Could not be started on %s; it will be tried "
                                "again.", format_date(self.env, today))}
        rec.write(vals)
        if days >= 3:
            rec._send_back(_(
                "Could not be started on three different days, so nothing "
                "was written. Propose it again."))
        return days

    @api.model
    def _cron_start_scheduled(self, limit=200):
        """The hourly job: write every scheduled change whose day has come,
        oldest first, one transaction per change."""
        # A test may not commit; everywhere else each change is its own
        # transaction, so one bad change never takes the others with it.
        testing = bool(odoo_module.current_test)
        todo = self.sudo().search([
            ('state', '=', 'scheduled'), ('applied', '=', False),
            ('start_date', '!=', False)], order='start_date, id',
            limit=int(limit or 200))
        tally = {}
        for rec in todo:
            if rec.start_date > rec._company_today():
                continue
            try:
                with self.env.cr.savepoint():
                    outcome, _sentence = rec._start_scheduled(by_job=True)
            except LOCK_ERRORS:
                self.env.invalidate_all()
                outcome = 'busy'
            except Exception as error:     # noqa: BLE001 — one never stops the rest
                self.env.invalidate_all()
                _logger.exception('pb_records: could not start %s', rec.name)
                rec._record_start_failure(error)
                outcome = 'failed'
            tally[outcome] = tally.get(outcome, 0) + 1
            if not testing:
                self.env.cr.commit()
        if tally:
            _logger.info('pb_records: scheduled changes %s', tally)
        return tally

    def _may_cancel(self):
        """The proposer, anybody asked to decide it, or an HR / payroll
        manager."""
        self.ensure_one()
        user = self.env.user
        if self.user_id == user or user in self.sudo().seat_user_ids:
            return True
        return any(user.has_group(g) for g in (
            'hr.group_hr_manager',
            'pb_hr_payroll_base.group_payroll_base_manager',
            'base.group_system'))

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        done = self.env['biz.approval.seed'].lay(
            company, RECORDS_PROCESS_KEY, 'Records Desk changes',
            _records_definition(),
            binding_note='The route every bulk change to people\'s details '
                         'follows unless a part of the business is given its '
                         'own.',
            model_name='pb.records.apply',
            role_keys=('hr_lead', 'finance'),
            reason='Set up when Records Desk approvals were switched on')
        self._approval_seed_bank(company)
        return done

    @api.model
    def _approval_seed_bank(self, company):
        """UPDATES P3a — the bank-details route, once per company. `lay`
        never touches a company that already has a published version, so a
        route somebody edited is never overwritten by an upgrade."""
        return self.env['biz.approval.seed'].lay(
            company, RECORDS_BANK_PROCESS_KEY,
            'Bank details — a second person', _bank_definition(),
            binding_note='Every bank-details change from Records or Updates '
                         'is approved by somebody other than the person who '
                         'proposed it.',
            role_keys=('finance',),
            reason='Set up when bank details got their own second check')

    def _ensure_bank_route(self):
        """A company that has no bank-details route yet (one created by a
        path that skipped the company hook) gets the shipped one — "a second
        person" — rather than a refusal. Never weaker: the shipped route is
        the strict one."""
        self.ensure_one()
        process = self.env['biz.approval.process']._by_key(
            RECORDS_BANK_PROCESS_KEY)
        if not process:
            return False
        company = self.company_id or self.env.company
        _b, _v, _t, error = self.env['biz.approval.engine'].sudo()._resolve_binding(
            company, process, [''], 'any')
        if error and error.get('code') == 'no_route':
            return self._approval_seed_bank(company)
        return True

    # ------------------------------------------------- UPDATES P3a — routes
    def _records_route(self):
        """`(kind, version)` of the records route THIS proposal would
        travel today: `fast`, `default`, `custom`, or `none`."""
        self.ensure_one()
        engine = self.env['biz.approval.engine'].sudo()
        process = self.env['biz.approval.process']._by_key(RECORDS_PROCESS_KEY)
        if not process:
            return 'none', self.env['biz.approval.workflow.version']
        ctx = self._approval_context()
        company = self.env['res.company'].browse(int(ctx['company_id']))
        _binding, version, _trace, error = engine._resolve_binding(
            company, process, ctx.get('scope_keys'), ctx.get('kind_key'))
        if error or not version:
            return 'none', version
        return route_kind(version.definition), version

    def _details_go_now(self):
        """Personal details from a sheet apply at once (D3) when the
        company's switch is on AND its records route is the shipped one or
        "No approval needed". A route the business set up itself is always
        followed."""
        self.ensure_one()
        company = self.company_id or self.env.company
        if not company.pb_records_sheet_details_now:
            return False
        kind, _version = self._records_route()
        return kind in ('fast', 'default')


def mask_account(text):
    """'•••• 6789' — the last four characters of an account number."""
    text = str(text or '').strip()
    if len(text) <= 4:
        return text
    return '•••• %s' % text[-4:]


def _bank_definition():
    """One step, "a second person": the Finance responsibility, and — in
    the adapter, never by a general engine change — never the proposer, with
    a records manager standing in when Finance is the proposer or nobody."""
    return {
        'schema_version': 1,
        'steps': [
            {'key': 's1', 'kind': 'approve', 'title': 'A second person',
             'who': {'mode': 'role', 'role': 'finance', 'scope': 'company'},
             'min_amount': 0, 'condition': None},
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

    #: UPDATES P3a (D3) — "Personal details from a sheet apply without
    #: approval". On by default; only ever relaxes the shipped records route
    #: or "No approval needed", never a route the company set up itself.
    pb_records_sheet_details_now = fields.Boolean(
        string='Personal details from a sheet apply without approval',
        default=True)

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
