# -*- coding: utf-8 -*-
"""`pb.contractlife` — the Contracts lens's only server surface.

The shape every cockpit in this product keeps: an `AbstractModel` facade,
`@api.model` reads, every independent probe inside its own `_safe()` so one
failing metric answers zero instead of taking the screen down, `self.env
.companies` scoping on every search, a row cap, and no sudo in a READ except
where a field's own `groups=` forces it (R56 — reading one field of an
`hr.employee` prefetches forty, half of them behind payroll groups).

THE QUESTION THIS BOARD ANSWERS is the one nobody asks until it is too late:
WHOSE AGREEMENT RUNS OUT, AND HAS ANYBODY DECIDED. So a row is a CONTRACT, the
number beside the name is the days left, and the chip after it says what kind of
employment this is — because "intern" and "contractor" are the two answers that
change what the decision even means.

THERE IS NO MONEY ON THIS BOARD, ON PURPOSE. A screen that lists what everybody
earns is a screen nobody can leave open on a shared desk, and a contract
decision does not need the number. The wage appears in exactly one place — the
confirm dialog, at the moment somebody is about to agree to it.
"""

import logging
from datetime import date

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError

from .contract_common import (
    DECISION_LABEL, EMPLOYEE_TYPE_LABEL, GROUP_ADMIN, GROUP_MANAGER,
    GROUP_USER, NON_PERMANENT_TYPES, P_AUTO_TRIGGER, P_EXTENSION_MONTHS,
    P_LEAD_DAYS, REVIEW_STATE_LABEL, flag, initials, number,
)

_logger = logging.getLogger(__name__)

#: How many rows the SCREEN reads. Right for a screen and wrong for a job —
#: the nightly work passes no cap at all (R76).
BOARD_LIMIT = 300

#: How red the days-left number goes: half the lead time, or a fortnight,
#: whichever is smaller.
def _urgent_days(lead):
    return min(30, max(7, int(lead or 60) // 2))


class PbContractLife(models.AbstractModel):
    _name = 'pb.contractlife'
    _description = 'Payobook Contracts & interns cockpit data'

    # ------------------------------------------------------------------ gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception:               # noqa: BLE001
            # WARNING with the traceback, never DEBUG (R92): a swallowed
            # exception logged at debug level is invisible on a live server,
            # and the caller gets a cheerful zero either way.
            _logger.warning('pb_contract_lifecycle: a board metric failed',
                            exc_info=True)
            return default

    @api.model
    def _can_read(self):
        user = self.env.user
        return (user.has_group(GROUP_USER) or user.has_group(GROUP_MANAGER)
                or user.has_group(GROUP_ADMIN) or user._is_admin())

    @api.model
    def _can_write(self):
        user = self.env.user
        return (user.has_group(GROUP_MANAGER) or user.has_group(GROUP_ADMIN)
                or user._is_admin())

    @api.model
    def _require_write(self):
        if not self._can_write():
            raise AccessError(_(
                "You can look at which contracts are ending, but deciding "
                "what happens to one is for the HR team. Ask them to make the "
                "change."))
        return True

    # ------------------------------------------------------------- the board
    @api.model
    def get_board(self):
        if not self._can_read():
            return {'allowed': False, 'can_write': False, 'kpis': {},
                    'rows': [], 'kinds': [], 'departments': [], 'months': [],
                    'states': [], 'auto_on': False, 'lead_days': 60,
                    'total': 0, 'capped': False, 'would_raise': 0}
        Contract = self.env['hr.contract']
        co_ids = self.env.companies.ids or [self.env.company.id]
        today = date.today()
        lead = max(1, number(self.env, P_LEAD_DAYS, 60))

        # ---- everybody with an end date, plus every intern and contractor ----
        # TWO SEARCHES AND NOT ONE, because they answer different questions and
        # a person can be either without being both: a fixed-term contract has
        # an end date whoever is on it, and an intern with no end date on their
        # paperwork is exactly the person this board exists to catch.
        rows_by_id = {}
        dated = self._safe(lambda: Contract.search([
            ('company_id', 'in', co_ids),
            ('date_end', '!=', False),
            ('state', 'in', ('draft', 'open')),
        ], order='date_end, id', limit=BOARD_LIMIT),
            default=Contract.browse())
        for contract in dated:
            rows_by_id[contract.id] = contract

        if len(rows_by_id) < BOARD_LIMIT:
            people = self._safe(lambda: self.env['hr.employee'].search([
                ('company_id', 'in', co_ids),
                ('active', '=', True),
                ('employee_type', 'in', list(NON_PERMANENT_TYPES)),
            ], limit=BOARD_LIMIT), default=self.env['hr.employee'].browse())
            extra = self._safe(lambda: Contract.search([
                ('company_id', 'in', co_ids),
                ('employee_id', 'in', people.ids),
                ('state', 'in', ('draft', 'open')),
            ], order='date_start desc, id desc',
                limit=BOARD_LIMIT - len(rows_by_id)),
                default=Contract.browse())
            for contract in extra:
                rows_by_id.setdefault(contract.id, contract)

        rows = []
        for contract in rows_by_id.values():
            try:
                rows.append(self._row(contract, today, lead))
            except Exception:           # noqa: BLE001
                _logger.warning('pb_contract_lifecycle: row for contract %s',
                                contract.id, exc_info=True)
        rows.sort(key=lambda r: (r['days'] if r['days'] is not None else 99999,
                                 r['employee']))

        year_start = date(today.year, 1, 1)
        converted = self._safe(lambda: self.env['pb.contract.review'].search_count([
            ('company_id', 'in', co_ids),
            ('decision', '=', 'convert'),
            ('decided_at', '>=', str(year_start)),
        ]))
        would = self._safe(lambda: len(
            self.env['pb.journey.case']._due_for_decision()))

        kpis = {
            'ending': len([r for r in rows if r['days'] is not None
                           and 0 <= r['days'] <= lead]),
            'undecided': len([r for r in rows if r['needs_decision']]),
            'running': len([r for r in rows
                            if r['review_state'] == 'conversion']),
            'waiting': len([r for r in rows
                            if r['review_state'] == 'extension']),
            'converted': converted,
        }
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'auto_on': flag(self.env, P_AUTO_TRIGGER),
            'would_raise': would,
            'lead_days': lead,
            'default_months': number(self.env, P_EXTENSION_MONTHS, 12),
            'kpis': kpis,
            'rows': rows,
            'total': len(rows),
            'capped': len(rows) >= BOARD_LIMIT,
            'kinds': _facet(rows, 'kind_label'),
            'departments': _facet(rows, 'dept'),
            'months': _facet(rows, 'end_month'),
            'states': _facet(rows, 'review_label'),
        }

    @api.model
    def _row(self, contract, today=None, lead=None):
        today = today or date.today()
        lead = lead or max(1, number(self.env, P_LEAD_DAYS, 60))
        emp = contract.employee_id
        Review = self.env['pb.contract.review']
        review = self._safe(
            lambda: Review.sudo().search(
                [('contract_id', '=', contract.id)],
                order='id desc', limit=1),
            default=Review.browse())
        # The LIVE one if there is one — never `order='state, ...'`, which
        # sorts a Selection by its stored string and would put "conversion"
        # ahead of "decide" for no reason anybody could explain (R50).
        live = self._safe(
            lambda: Review.sudo().search(
                [('contract_id', '=', contract.id),
                 ('state', 'in', ('upcoming', 'decide', 'extension',
                                  'conversion'))],
                order='id desc', limit=1),
            default=Review.browse())
        review = live or review

        kind = self._safe(lambda: emp._pb_employment_type(), default='') \
            if emp else ''
        days = (contract.date_end - today).days if contract.date_end else None
        urgent = _urgent_days(lead)
        needs = bool(
            days is not None and days <= lead
            and (not review or review.state in ('upcoming', 'decide')))
        return {
            'id': contract.id,
            'employee_id': emp.id if emp else 0,
            'employee': (emp.name if emp else '') or _('Nobody on it'),
            'initials': initials(emp.name if emp else ''),
            'avatar': ('/web/image/hr.employee/%s/avatar_128' % emp.id)
            if emp else '',
            'job': self._safe(
                lambda: emp.sudo().job_title
                or (emp.sudo().job_id.name if emp.sudo().job_id else ''),
                default='') or '' if emp else '',
            'dept': self._safe(
                lambda: emp.sudo().department_id.name
                if (emp and emp.sudo().department_id) else '',
                default='') or _('No team'),
            'manager': self._safe(
                lambda: emp.sudo().parent_id.name
                if (emp and emp.sudo().parent_id) else '', default='') or '',
            'kind': kind,
            'kind_label': EMPLOYEE_TYPE_LABEL.get(kind, '') or _('Not set'),
            'non_permanent': kind in NON_PERMANENT_TYPES,
            'contract_name': contract.name or '—',
            'contract_type': contract.type_id.name if contract.type_id else '',
            'state': contract.state,
            'date_start': str(contract.date_start) if contract.date_start
            else '',
            'date_end': str(contract.date_end) if contract.date_end else '',
            'end_month': (contract.date_end.strftime('%Y-%m')
                          if contract.date_end else ''),
            'days': days,
            'when': _when(days),
            'urgent': bool(days is not None and days <= urgent),
            'needs_decision': needs,
            'review_id': review.id if review else 0,
            'review_state': review.state if review else '',
            'review_label': (REVIEW_STATE_LABEL.get(review.state, '')
                             if review else _('Not raised')),
            'decision': review.decision if review else '',
            'decision_label': (DECISION_LABEL.get(review.decision, '')
                               if review else ''),
            'new_contract_id': (review.new_contract_id.id
                                if (review and review.new_contract_id) else 0),
            'evaluation_id': (review.review_id.id
                              if (review and review.review_id) else 0),
        }

    # ------------------------------------------------------- one contract
    @api.model
    def get_contract(self, contract_id):
        """One contract, whole — the decision drawer behind a row."""
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        contract = self.env['hr.contract'].browse(int(contract_id)).exists()
        if not contract:
            raise UserError(_("That contract could not be found."))
        Review = self.env['pb.contract.review'].sudo()
        history = self._safe(
            lambda: Review.search([('contract_id', '=', contract.id)],
                                  order='id desc'),
            default=Review.browse())
        live = history.filtered(
            lambda r: r.state in ('upcoming', 'decide', 'extension',
                                  'conversion'))[:1]
        review = live or history[:1]
        extension = self.env['pb.contract.extension'].browse()
        if review:
            extension = review.extension_ids.filtered(
                lambda e: e.state in ('draft', 'pending'))[:1]
        return {
            'row': self._row(contract),
            'terms': self._safe(lambda: contract.pb_terms_summary(),
                                default={}),
            'review_id': review.id if review else 0,
            'review_state': review.state if review else '',
            'previews': {kind: self._safe(
                lambda k=kind: review.decision_preview(k), default={})
                for kind in ('terminate', 'extend', 'convert')}
            if review else {},
            'extension': {
                'id': extension.id,
                'reason': extension.reason or '',
                'months': extension.months,
                'approver': (extension.approver_user_id.name
                             if extension.approver_user_id else ''),
                'approve_by': str(extension.approve_by or ''),
                'state': extension.state,
                'state_label': extension.state_label(),
                'overdue': bool(extension.approve_by
                                and extension.approve_by < date.today()),
                'new_start': str(extension.new_date_start or ''),
                'new_end': str(extension.new_date_end or ''),
            } if extension else None,
            'evaluation': self._evaluation(review),
            'history': [{
                'id': r.id,
                'raised': str(r.create_date.date()) if r.create_date else '',
                'end_date': str(r.end_date or ''),
                'state': r.state,
                'state_label': r.state_label(),
                'decision': r.decision or '',
                'decision_label': DECISION_LABEL.get(r.decision, '')
                if r.decision else '',
                'by': r.decided_by.name if r.decided_by else '',
                'on': str(r.decided_at.date()) if r.decided_at else '',
                'note': r.decision_note or '',
                'new_contract_id': (r.new_contract_id.id
                                    if r.new_contract_id else 0),
                'new_contract': (r.new_contract_id.name
                                 if r.new_contract_id else ''),
                'exit_case_id': r.exit_case_id.id if r.exit_case_id else 0,
                'letter_id': r.letter_id.id if r.letter_id else 0,
            } for r in history],
            'kinds': [{'id': k, 'label': v}
                      for k, v in EMPLOYEE_TYPE_LABEL.items()],
        }

    def _evaluation(self, review):
        """Where a conversion evaluation has got to, in P5's own words."""
        if not review or not review.review_id:
            return None
        evaluation = review.review_id
        return {
            'id': evaluation.id,
            'state': evaluation.state,
            'state_label': self._safe(lambda: evaluation.state_label(),
                                      default=''),
            'verdict': evaluation.verdict or '',
            'nominees': evaluation.nominee_count,
            'answers_in': evaluation.feedback_in,
            'answers_total': evaluation.feedback_total,
            'deadline': str(evaluation.feedback_deadline or ''),
        }

    # =====================================================================
    #  WRITES. Every one of them goes through the model that owns the fact.
    # =====================================================================
    @api.model
    def raise_decision(self, contract_id):
        self._require_write()
        review = self.env['pb.contract.review'].open_for(int(contract_id))
        review.notify_decision_needed()
        return {'review_id': review.id}

    @api.model
    def decision_preview(self, review_id, decision, months=None):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        review = self._review(review_id)
        return review.decision_preview(decision, months=months)

    @api.model
    def decide_terminate(self, review_id, note=None):
        self._require_write()
        return self._review(review_id).action_terminate(note=note)

    @api.model
    def request_extension(self, review_id, reason=None, months=None):
        self._require_write()
        return self._review(review_id).action_request_extension(
            reason=reason, months=months)

    @api.model
    def request_conversion(self, review_id):
        self._require_write()
        return self._review(review_id).action_request_conversion()

    @api.model
    def approve_extension(self, extension_id, note=None):
        """Agree an extension. The APPROVAL is checked by the chain, not here.

        `_require_write` is deliberately NOT called: the person who agrees an
        extension is the employee's own manager, who may hold no HR group at
        all. `biz.approval.chain.mixin._approval_can` — overridden on the
        request to admit exactly that person — is the boundary.
        """
        request = self.env['pb.contract.extension'].browse(
            int(extension_id)).exists()
        if not request:
            raise UserError(_("That extension request could not be found."))
        return request.action_approve(note=note)

    @api.model
    def refuse_extension(self, extension_id, note=None):
        request = self.env['pb.contract.extension'].browse(
            int(extension_id)).exists()
        if not request:
            raise UserError(_("That extension request could not be found."))
        return request.action_refuse(note=note)

    @api.model
    def set_employment_type(self, employee_id, kind):
        """Type somebody by hand — the one write this board makes to a person."""
        self._require_write()
        emp = self.env['hr.employee'].browse(int(employee_id)).exists()
        if not emp:
            raise UserError(_("That person could not be found."))
        if kind not in EMPLOYEE_TYPE_LABEL:
            raise UserError(_("That is not an employment type this build "
                              "knows."))
        emp.pb_set_employment_type(kind, reason=_(
            "Recorded as %(what)s by %(who)s.",
            what=EMPLOYEE_TYPE_LABEL.get(kind, kind),
            who=self.env.user.name))
        return {'kind': kind,
                'label': EMPLOYEE_TYPE_LABEL.get(kind, kind)}

    @api.model
    def run_automation(self):
        self._require_write()
        return self.env['pb.journey.case'].run_contract_automation()

    def _review(self, review_id):
        review = self.env['pb.contract.review'].browse(
            int(review_id)).exists()
        if not review:
            raise UserError(_("That contract decision could not be found."))
        return review

    # ------------------------------------------------------------ the doors
    @api.model
    def open_contract_action(self, contract_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        return {'type': 'ir.actions.act_window', 'res_model': 'hr.contract',
                'res_id': int(contract_id), 'view_mode': 'form'}

    @api.model
    def open_employee_action(self, employee_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        return {'type': 'ir.actions.act_window', 'res_model': 'hr.employee',
                'res_id': int(employee_id), 'view_mode': 'form'}

    @api.model
    def open_review_action(self, review_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.contract.review',
                'res_id': int(review_id), 'view_mode': 'form'}

    @api.model
    def open_evaluation_action(self, evaluation_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.probation.review',
                'res_id': int(evaluation_id), 'view_mode': 'form'}

    @api.model
    def open_letter_action(self, letter_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        letter = self.env['pb.hr.letter'].browse(int(letter_id)).exists()
        if not letter:
            raise UserError(_("That letter could not be found."))
        return letter.action_open_pdf()

    @api.model
    def open_case_action(self, case_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.journey.case',
                'res_id': int(case_id), 'view_mode': 'form'}


def _when(days):
    """"in 12 days" / "ends today" / "6 days ago" — never a bare number."""
    if days is None:
        return _('no end date')
    if days == 0:
        return _('ends today')
    if days == 1:
        return _('ends tomorrow')
    if days > 1:
        return _('in %s days', days)
    if days == -1:
        return _('ended yesterday')
    return _('%s days ago', -days)


def _facet(rows, key):
    counts = {}
    for row in rows:
        value = row.get(key) or ''
        if value:
            counts[value] = counts.get(value, 0) + 1
    return [{'id': k, 'label': k, 'count': v}
            for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
