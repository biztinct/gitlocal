# -*- coding: utf-8 -*-
"""`pb.incentives` — the Awards lens's only server surface.

THE QUESTION THIS BOARD ANSWERS: what has somebody promised, and has it been
paid. So the four numbers across the top are the four places an award can be
stuck — waiting for a decision, decided but not in a pay run, in a pay run, and
done — and a row is one award with its state on it.

The preview before "Queue this month" is the hero, and it is the safety rail as
well: nothing is written until somebody has read who gets what, out of which run,
and whether the pay scheme even knows the pay item the money would arrive under.
"""

import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .comp_common import (
    FEEDABLE_RUN_STATES, FULFILMENT_LABEL, GROUP_HEAD, GROUP_USER,
    INCENTIVE_KIND_LABEL, INCENTIVE_STATE_LABEL, P_INCENTIVE_CODE,
    P_LETTER_SEND, flag, param,
)

_logger = logging.getLogger(__name__)

BOARD_LIMIT = 400


def _refusal():
    return {
        'allowed': False, 'can_write': False, 'can_approve': False,
        'rows': [], 'kpis': {}, 'runs': [], 'kinds': [], 'states': [],
        'total': 0, 'capped': False, 'code': '', 'letters_on': False,
        'why': _("Awards are looked after by the pay team. This screen is not "
                 "part of the general HR permissions — somebody has to add you "
                 "to it by name."),
    }


class PbIncentives(models.AbstractModel):
    _name = 'pb.incentives'
    _description = 'Payobook awards cockpit data'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:              # noqa: BLE001
            _logger.debug('awards metric failed: %s', e)
            return default

    @api.model
    def _can_read(self):
        user = self.env.user
        return bool(self.env.su or user._is_admin()
                    or user.has_group(GROUP_USER)
                    or user.has_group(GROUP_HEAD))

    @api.model
    def _can_write(self):
        return self._can_read()

    @api.model
    def _can_approve(self):
        return bool(self.env.su or self.env.user._is_admin()
                    or self.env.user.has_group(GROUP_HEAD))

    @api.model
    def _require_read(self):
        if not self._can_read():
            raise AccessError(_refusal()['why'])
        return True

    # ------------------------------------------------------------- the board
    @api.model
    def get_board(self, month=None):
        if not self._can_read():
            return _refusal()
        Incentive = self.env['pb.incentive']
        recs = Incentive.search([
            '|', ('company_id', '=', False),
            ('company_id', 'in', self.env.companies.ids),
        ], order='period_month desc, id desc', limit=BOARD_LIMIT + 1)
        capped = len(recs) > BOARD_LIMIT
        recs = recs[:BOARD_LIMIT]
        rows = [self._row(rec) for rec in recs]
        today = date.today()
        this_month = today.replace(day=1)
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'can_approve': self._can_approve(),
            'rows': rows,
            'total': len(rows),
            'capped': capped,
            'code': (param(self.env, P_INCENTIVE_CODE) or 'INCENTV').upper(),
            'letters_on': flag(self.env, P_LETTER_SEND),
            'month': this_month.isoformat(),
            'runs': self._open_runs(),
            'kinds': [{'key': k, 'label': v}
                      for k, v in INCENTIVE_KIND_LABEL.items()],
            'states': [{'key': k, 'label': v}
                       for k, v in INCENTIVE_STATE_LABEL.items()],
            'kpis': {
                'waiting': len([r for r in rows if r['state'] == 'submitted']),
                'to_queue': len([r for r in rows
                                 if r['state'] == 'approved'
                                 and r['fulfilment'] in ('pending', 'letter')
                                 and r['month'][:7] == this_month.isoformat()[:7]]),
                'queued': len([r for r in rows if r['fulfilment'] == 'queued']),
                'paid_mtd': len([r for r in rows
                                 if r['fulfilment'] == 'paid'
                                 and r['month'][:7] == this_month.isoformat()[:7]]),
                'amount_to_queue': sum(
                    r['amount'] for r in rows
                    if r['state'] == 'approved'
                    and r['fulfilment'] in ('pending', 'letter')
                    and r['month'][:7] == this_month.isoformat()[:7]),
            },
            'why': '',
        }

    @api.model
    def _row(self, rec):
        emp = rec._person()
        return {
            'id': rec.id,
            'employee': emp.name or '',
            'employee_id': emp.id,
            'initials': _initials(emp.name or ''),
            'kind': rec.kind or '',
            'kind_label': INCENTIVE_KIND_LABEL.get(rec.kind, ''),
            'amount': rec.amount or 0.0,
            'currency': rec.currency_id.symbol or '',
            'month': (rec.period_month.isoformat() if rec.period_month else ''),
            'month_label': (rec.period_month.strftime('%b %Y')
                            if rec.period_month else ''),
            'state': rec.state or 'draft',
            'state_label': INCENTIVE_STATE_LABEL.get(rec.state, ''),
            'fulfilment': rec.fulfilment or '',
            'fulfilment_label': FULFILMENT_LABEL.get(rec.fulfilment, ''),
            'has_letter': bool(rec.letter_id and rec.letter_id.attachment_id),
            'letter_id': rec.letter_id.id if rec.letter_id else 0,
            'run': rec.run_id.name if rec.run_id else '',
            'run_id': rec.run_id.id if rec.run_id else 0,
            'reason': rec.reason or '',
            'source': rec.source or 'manual',
        }

    @api.model
    def _open_runs(self):
        """Pay runs an award can still be put into — and NOTHING else.

        A closed list is the safety rail expressed as a control: the dialog
        cannot offer a run past level0, so nobody has to be told no.
        """
        runs = self.env['hr.payslip.run'].sudo().search(
            [('state', 'in', list(FEEDABLE_RUN_STATES))],
            order='date_start desc, id desc', limit=25)
        return [{'id': r.id, 'name': r.name or '',
                 'state': r.state or 'draft',
                 'period': ('%s → %s' % (r.date_start or '', r.date_end or ''))}
                for r in runs]

    # ------------------------------------------------------------ the writes
    @api.model
    def create_award(self, vals):
        self._require_read()
        clean = {
            'employee_id': int((vals or {}).get('employee_id') or 0),
            'kind': (vals or {}).get('kind') or 'bonus',
            'amount': float((vals or {}).get('amount') or 0.0),
            'reason': (vals or {}).get('reason') or '',
        }
        month = (vals or {}).get('period_month')
        if month:
            clean['period_month'] = fields.Date.to_date(month).replace(day=1)
        if not clean['employee_id']:
            raise AccessError(_("Choose who the award is for."))
        rec = self.env['pb.incentive'].create(clean)
        return rec.id

    @api.model
    def submit(self, incentive_id):
        self._require_read()
        return self.env['pb.incentive'].browse(int(incentive_id)).action_submit()

    @api.model
    def approve(self, incentive_id):
        self._require_read()
        return self.env['pb.incentive'].browse(int(incentive_id)).action_approve()

    @api.model
    def refuse(self, incentive_id, note=False):
        self._require_read()
        return self.env['pb.incentive'].browse(
            int(incentive_id)).action_refuse(note=note or False)

    @api.model
    def make_letter(self, incentive_id):
        self._require_read()
        return bool(self.env['pb.incentive'].browse(
            int(incentive_id)).action_make_letter())

    @api.model
    def employee_options(self, term=''):
        """People to pick from. Read as the system for the SAME reason every
        other employee read in this module is (R56) — the search is the gate."""
        self._require_read()
        Emp = self.env['hr.employee'].sudo()
        domain = [('company_id', 'in', self.env.companies.ids)]
        if term:
            domain += ['|', ('name', 'ilike', term), ('barcode', 'ilike', term)]
        rows = Emp.search(domain, order='name', limit=25)
        return [{'id': e.id, 'name': e.name or '',
                 'code': e.barcode or ''} for e in rows]

    # -------------------------------------------------------------- the feed
    @api.model
    def preview_queue(self, run_id, incentive_ids=None):
        self._require_read()
        return self.env['pb.oneoff.feed'].preview_for_run(
            run_id, incentive_ids=incentive_ids or None)

    @api.model
    def confirm_queue(self, run_id, incentive_ids=None):
        self._require_read()
        return self.env['pb.oneoff.feed'].queue_for_run(
            incentive_ids or None, run_id)


def _initials(name):
    parts = [p for p in (name or '').split() if p]
    if not parts:
        return '?'
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else '')).upper()
