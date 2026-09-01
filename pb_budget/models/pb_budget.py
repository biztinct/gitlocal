# -*- coding: utf-8 -*-
"""`pb.budget` — the Budget lens's facade.

One read builds the whole board: the year, its twelve months, every function the
reader is allowed to see, what each was given, what each has spent, and how that
compares with WHERE THE YEAR IS. That last comparison is the point of the whole
screen — "70% spent" is neither good nor bad until you know whether it is March
or November.

THE BOUNDARY IS ENFORCED HERE AND IN THE RECORD RULES, BOTH.
Every read below runs with the caller's own rights — no sudo on the budget rows —
so `ir.rule` is what decides which functions come back, and the facade's own gate
decides whether the screen opens at all. Two locks on one door, deliberately: the
rules protect the model from every other route into it, and the gate means a
person who holds nothing gets one plain sentence instead of a raw permission
error out of the ORM.

WHAT IT NEVER DOES
  * It never sums two currencies as though they were one. Where the budgets in
    scope are in more than one currency, everything is reported in the group's
    reporting currency; where a rate for that is missing, the affected rows are
    NAMED and left out rather than converted at one for one (R23).
  * It never writes. Writing is the upload wizard, the expense model and the
    actuals job — three doors, each with its own permission.
"""

import logging
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .budget_common import (BOARD_ROW_CAP, BUDGET_TYPES, EXPENSE_ROW_CAP,
                            TYPE_KEYS, counted, fold, param_int, safe,
                            type_label)

_logger = logging.getLogger(__name__)

#: Anybody holding one of these may open the board; what they then SEE is the
#: record rules' business, not this tuple's.
GATE_GROUPS = (
    'pb_budget.group_budget_viewer',
    'pb_budget.group_budget_manager',
    'pb_budget.group_budget_finance',
)
EDIT_GROUPS = (
    'pb_budget.group_budget_manager',
)
#: How far ahead of the calendar a function has to be before the board calls it
#: hot. Five points of the year is roughly a fortnight — inside the noise of
#: when a pay run happens to land; fifteen is a month and a half, which is not.
WATCH_AT = 5.0
OVER_AT = 15.0
CALM_AT = -10.0


class PbBudget(models.AbstractModel):
    _name = 'pb.budget'
    _description = 'Budget board — read-only facade'

    # ================================================================= access
    @api.model
    def _is_admin(self):
        return self.env.user.has_group('base.group_system')

    @api.model
    def _has(self, groups):
        for g in groups:
            try:
                if self.env.user.has_group(g):
                    return True
            except (ValueError, KeyError):     # the group is not on this DB
                continue
        return False

    @api.model
    def _require(self):
        if self._is_admin() or self._has(GATE_GROUPS):
            return
        raise AccessError(_(
            "Budgets are shown to the people who hold one — a function head, "
            "the budget team or finance. Ask an administrator to add you if "
            "you should be seeing this."))

    @api.model
    def _require_edit(self):
        if self._is_admin() or self._has(EDIT_GROUPS):
            return
        raise AccessError(_(
            "Only the budget team can change a budget. You can read the "
            "figures and export them."))

    @api.model
    def can_edit(self):
        return bool(self._is_admin() or self._has(EDIT_GROUPS))

    # ================================================================ the year
    @api.model
    def _fy_start_month(self):
        m = param_int(self.env, 'pb_budget.fy_start_month', 1)
        return m if 1 <= m <= 12 else 1

    @api.model
    def _fy_months(self, fy):
        start_month = self._fy_start_month()
        first = date(int(fy), start_month, 1)
        return [first + relativedelta(months=i) for i in range(12)]

    @api.model
    def _fy_label(self, fy):
        if self._fy_start_month() == 1:
            return str(fy)
        return '%s/%s' % (fy, str(int(fy) + 1)[-2:])

    @api.model
    def _current_fy(self, today=None):
        today = today or fields.Date.context_today(self)
        start_month = self._fy_start_month()
        return today.year if today.month >= start_month else today.year - 1

    @api.model
    def _pace(self, fy, today=None):
        """How far through the year the CALENDAR is, 0–100.

        Whole months elapsed plus the fraction of the one we are in — a budget
        board that jumps ten points on the first of the month tells people the
        wrong thing for a fortnight either side of it.
        """
        today = today or fields.Date.context_today(self)
        months = self._fy_months(fy)
        first, last = months[0], months[-1]
        if today < first:
            return 0.0
        if today > last + relativedelta(months=1) - relativedelta(days=1):
            return 100.0
        elapsed = (today.year - first.year) * 12 + (today.month - first.month)
        days_in = (first + relativedelta(months=elapsed + 1)
                   - first - relativedelta(months=elapsed)).days or 30
        return round(min(100.0, (elapsed + (today.day - 1) / days_in) / 12 * 100), 1)

    # ================================================================ the board
    @api.model
    def get_board(self, fy=None, budget_type='manpower', currency='report',
                  row_cap=None):
        """Everything the lens draws, in one call."""
        self._require()
        fy = int(fy or self._current_fy())
        btype = budget_type if budget_type in TYPE_KEYS else 'manpower'
        months = self._fy_months(fy)
        cap = int(row_cap or BOARD_ROW_CAP)

        rows = self.env['wfp.budget.actual'].search([
            ('pb_budget_type', '=', btype),
            ('period_month', '>=', months[0]),
            ('period_month', '<=', months[-1]),
        ], order='period_month, department_id', limit=cap)
        truncated = 1 if len(rows) >= cap else 0

        fx = self.env['pb.budget.fx']
        presentation = fx.presentation_currency()
        currencies = {r.pb_currency_id for r in rows if r.pb_currency_id}
        one_currency = list(currencies)[0] if len(currencies) == 1 else None
        mode = currency if currency in ('report', 'local') else 'report'
        forced = ''
        if mode == 'local' and not one_currency and len(currencies) > 1:
            mode = 'report'
            forced = _(
                "These budgets are kept in %s different currencies, so they can "
                "only be added up in %s.",
                len(currencies), presentation.name if presentation else '')

        payload = self._matrix(rows, months, mode, presentation, one_currency,
                               self._pace(fy))
        payload.update({
            'ok': True,
            'fy': fy,
            'fy_label': self._fy_label(fy),
            'fy_options': self._fy_options(fy),
            'budget_type': btype,
            'type_label': type_label(btype),
            'type_options': [{'key': k, 'label': type_label(k)}
                             for k, _l in BUDGET_TYPES],
            'months': [{'key': m.strftime('%Y-%m'),
                        'label': m.strftime('%b'),
                        'year': m.year,
                        'date': str(m)} for m in months],
            'pace': self._pace(fy),
            'truncated': truncated,
            'can_edit': self.can_edit(),
            'last_sync': self.env['ir.config_parameter'].sudo().get_param(
                'pb_budget.actuals_last_run') or '',
            'forced_currency_note': forced,
        })
        payload['kpis'] = self._kpis(payload)
        payload['headline'] = self._headline(payload)
        return payload

    @api.model
    def _fy_options(self, fy):
        """The years there is anything to look at, plus this one and next."""
        years = set()
        rows = safe(lambda: self.env['wfp.budget.actual'].search_read(
            [], ['period_month'], limit=BOARD_ROW_CAP), [], 'the year list') or []
        for r in rows:
            if r.get('period_month'):
                d = r['period_month']
                years.add(d.year if self._fy_start_month() == 1
                          else (d.year if d.month >= self._fy_start_month()
                                else d.year - 1))
        now = self._current_fy()
        years |= {now, now + 1, int(fy)}
        return [{'key': y, 'label': self._fy_label(y)} for y in sorted(years)]

    # --------------------------------------------------------------- the grid
    @api.model
    def _matrix(self, rows, months, mode, presentation, one_currency, pace):
        """Rows -> functions -> departments -> months, in ONE currency."""
        keys = [m.strftime('%Y-%m') for m in months]
        funcs, unknown, unbudgeted = {}, 0, 0
        cur = (one_currency if mode == 'local' and one_currency
               else presentation)

        for rec in rows:
            budget, spent, known = self._amounts(rec, mode, cur)
            if not known:
                unknown += 1
                continue
            if rec.pb_unbudgeted:
                unbudgeted += 1
            fid = rec.pb_function_id.id or (rec.department_id.id or 0)
            fname = (rec.pb_function_id.name or rec.department_id.name
                     or _('Whole company'))
            f = funcs.setdefault(fid, {
                'id': fid, 'name': fname, 'budget': 0.0, 'spent': 0.0,
                'months': {k: {'budget': 0.0, 'spent': 0.0} for k in keys},
                'departments': {}, 'unbudgeted': False, 'rows': 0,
            })
            f['budget'] += budget
            f['spent'] += spent
            f['rows'] += 1
            f['unbudgeted'] = f['unbudgeted'] or rec.pb_unbudgeted
            mkey = rec.period_month.strftime('%Y-%m')
            if mkey in f['months']:
                f['months'][mkey]['budget'] += budget
                f['months'][mkey]['spent'] += spent
            did = rec.department_id.id or 0
            d = f['departments'].setdefault(did, {
                'id': did,
                'name': rec.department_id.name or _('Whole company'),
                'budget': 0.0, 'spent': 0.0, 'unbudgeted': False,
            })
            d['budget'] += budget
            d['spent'] += spent
            d['unbudgeted'] = d['unbudgeted'] or rec.pb_unbudgeted

        out = []
        for f in funcs.values():
            f['months'] = [dict(f['months'][k], key=k) for k in keys]
            f['departments'] = sorted(
                f['departments'].values(), key=lambda d: -abs(d['spent']))
            f['budget'] = round(f['budget'], 2)
            f['spent'] = round(f['spent'], 2)
            f['left'] = round(f['budget'] - f['spent'], 2)
            f['burn'] = round(f['spent'] / f['budget'] * 100, 1) if f['budget'] else 0.0
            f['pace'] = pace
            f['gap'] = round(f['burn'] - pace, 1) if f['budget'] else 0.0
            f['tone'] = self._tone(f)
            f['tone_label'] = self._tone_label(f)
            out.append(f)
        out.sort(key=lambda f: (-abs(f['spent']), f['name']))

        return {
            'functions': out,
            'currency': {
                'mode': mode,
                'code': cur.name if cur else '',
                'symbol': cur.symbol if cur else '',
                'position': cur.position if cur else 'after',
                'digits': cur.decimal_places if cur else 2,
                'report_code': presentation.name if presentation else '',
                'local_available': bool(one_currency),
                'local_code': one_currency.name if one_currency else '',
            },
            'fx_unknown': unknown,
            'fx_note': (self.env['pb.budget.fx'].unknown_rate_note(
                one_currency or (rows[:1].pb_currency_id if rows else None),
                presentation) if unknown else ''),
            'unbudgeted': unbudgeted,
        }

    @api.model
    def _amounts(self, rec, mode, cur):
        if mode == 'local':
            return (round(rec.forecast_cost or 0.0, 2),
                    round(rec.actual_cost or 0.0, 2), True)
        rep = rec.pb_reported(presentation=cur)
        return rep['budget'], rep['spent'], rep['known']

    @api.model
    def _tone(self, f):
        """Four words, and a number beside every one of them.

        Colour alone is never the message — every tile carries its percentage
        and its word, so the board reads correctly to somebody who cannot tell
        the amber from the rose.
        """
        if not f['budget'] and f['spent']:
            return 'none'
        if not f['budget']:
            return 'calm'
        if f['gap'] > OVER_AT:
            return 'over'
        if f['gap'] > WATCH_AT:
            return 'watch'
        if f['gap'] < CALM_AT:
            return 'calm'
        return 'onpace'

    @api.model
    def _tone_label(self, f):
        return {
            'none': _('No budget set'),
            'over': _('Ahead of the year'),
            'watch': _('Running warm'),
            'onpace': _('On pace'),
            'calm': _('Behind the year'),
        }.get(f['tone'], '')

    # ---------------------------------------------------------------- the KPIs
    @api.model
    def _kpis(self, payload):
        funcs = payload['functions']
        budget = round(sum(f['budget'] for f in funcs), 2)
        spent = round(sum(f['spent'] for f in funcs), 2)
        pace = payload['pace']
        burn = round(spent / budget * 100, 1) if budget else 0.0
        return {
            'budget': budget,
            'spent': spent,
            'left': round(budget - spent, 2),
            'burn': burn,
            'pace': pace,
            'gap': round(burn - pace, 1) if budget else 0.0,
            'hot': len([f for f in funcs if f['tone'] in ('over', 'watch')]),
            'unbudgeted': len([f for f in funcs if f['tone'] == 'none']),
            'functions': len(funcs),
        }

    @api.model
    def _headline(self, payload):
        """One sentence, built in ONE expression so its spaces survive (R34)."""
        k = payload['kpis']
        cur = payload['currency']['code']
        if not payload['functions']:
            return _("Nothing has been budgeted for %s yet.", payload['fy_label'])
        if not k['budget']:
            return _(
                "No budget has been set for %(year)s, and %(spent)s %(cur)s has "
                "already been spent across %(n)s.",
                year=payload['fy_label'], spent='{:,.0f}'.format(k['spent']),
                cur=cur, n=counted(k['functions'], _("1 function"),
                                   _("%s functions")))
        if k['gap'] > OVER_AT:
            return _(
                "%(burn)s%% of the %(year)s budget is spent and the year is "
                "%(pace)s%% gone — spending is running ahead of the calendar.",
                burn='{:,.0f}'.format(k['burn']), year=payload['fy_label'],
                pace='{:,.0f}'.format(k['pace']))
        if k['gap'] < CALM_AT:
            return _(
                "%(burn)s%% of the %(year)s budget is spent against a year that "
                "is %(pace)s%% gone — comfortably inside it.",
                burn='{:,.0f}'.format(k['burn']), year=payload['fy_label'],
                pace='{:,.0f}'.format(k['pace']))
        return _(
            "%(burn)s%% of the %(year)s budget is spent and the year is "
            "%(pace)s%% gone — about where it should be.",
            burn='{:,.0f}'.format(k['burn']), year=payload['fy_label'],
            pace='{:,.0f}'.format(k['pace']))

    # =============================================================== the drill
    @api.model
    def get_function(self, function_id, fy=None, budget_type='manpower',
                     currency='report'):
        """One function, opened: its months, its departments, its expenses."""
        self._require()
        fy = int(fy or self._current_fy())
        btype = budget_type if budget_type in TYPE_KEYS else 'manpower'
        months = self._fy_months(fy)
        board = self.get_board(fy, btype, currency)
        func = next((f for f in board['functions']
                     if f['id'] == int(function_id or 0)), None)
        if not func:
            return {'ok': False,
                    'message': _("That function has nothing budgeted for "
                                 "%s.", self._fy_label(fy))}
        return {
            'ok': True,
            'function': func,
            'currency': board['currency'],
            'months': board['months'],
            'pace': board['pace'],
            'expenses': self._expenses(function_id, months, btype),
            'rows': self._rows(function_id, months, btype,
                               board['currency']['mode'],
                               self._board_currency(board['currency'])),
        }

    @api.model
    def _board_currency(self, block):
        """The currency record the board reported in — resolved ONCE, from the
        code the payload already carries, so the drill can never quietly report
        in a different one."""
        if not block.get('code'):
            return self.env['pb.budget.fx'].presentation_currency()
        return self.env['res.currency'].sudo().search(
            [('name', '=', block['code'])], limit=1)

    @api.model
    def _expenses(self, function_id, months, btype):
        if btype == 'manpower':
            return []
        recs = self.env['pb.budget.expense'].search([
            ('function_id', '=', int(function_id or 0)),
            ('budget_type', '=', btype),
            ('period_month', '>=', months[0]),
            ('period_month', '<=', months[-1]),
        ], order='spend_date desc', limit=EXPENSE_ROW_CAP)
        return [{
            'id': r.id, 'name': r.name or '',
            'date': str(r.spend_date or ''),
            'department': r.department_id.name or '',
            'supplier': r.supplier or '',
            'amount': r.amount or 0.0,
            'currency': r.currency_id.name or '',
            'note': r.note or '',
        } for r in recs]

    @api.model
    def _rows(self, function_id, months, btype, mode, cur):
        recs = self.env['wfp.budget.actual'].search([
            ('pb_function_id', '=', int(function_id or 0)),
            ('pb_budget_type', '=', btype),
            ('period_month', '>=', months[0]),
            ('period_month', '<=', months[-1]),
        ], order='period_month, department_id', limit=BOARD_ROW_CAP)
        out = []
        for rec in recs:
            budget, spent, known = self._amounts(rec, mode, cur)
            out.append({
                'id': rec.id,
                'month': rec.period_month.strftime('%Y-%m'),
                'month_label': rec.period_month.strftime('%b %Y'),
                'department': rec.department_id.name or _('Whole company'),
                'budget': budget, 'spent': spent,
                'left': round(budget - spent, 2),
                'known': known,
                'source': dict(rec._fields['pb_source'].selection).get(
                    rec.pb_source, ''),
                'own_currency': rec.pb_currency_id.name or '',
                'manual_rate': rec.pb_manual_rate or 0.0,
                'unbudgeted': rec.pb_unbudgeted,
                'synced': str(rec.pb_actual_synced_on or ''),
            })
        return out

    # =============================================================== the doors
    @api.model
    def refresh_actuals(self):
        """The button, and it does EXACTLY what the night does (R53)."""
        self._require_edit()
        report = self.env['pb.budget.actuals'].sudo().run_now()
        return {'ok': True, 'report': report,
                'message': self._sync_sentence(report)}

    @api.model
    def _sync_sentence(self, report):
        if report.get('off'):
            return _(
                "Automatic spend figures are switched off. %s "
                "department-months would have been written.",
                report.get('would_write', 0))
        bits = [_("%s department-months updated.", report.get('written', 0))]
        if report.get('created'):
            bits.append(_("%s had no budget set and were added, flagged.",
                          report.get('created')))
        if report.get('pending_runs'):
            bits.append(_(
                "%s pay runs have not been summarised yet, so they are not in "
                "these figures.", report.get('pending_runs')))
        if report.get('skipped_fx'):
            bits.append(_(
                "%s rows were left alone because there is no exchange rate for "
                "the money they are kept in.", report.get('skipped_fx')))
        return ' '.join(bits)

    @api.model
    def department_options(self, term=None, limit=20):
        """A department picker that finds "Kỹ thuật" when you type "ky thuat".

        Accents are folded in PYTHON over a `search_read` of two columns —
        Postgres on this box has no `unaccent` (R78) and a domain `ilike` would
        simply not match.
        """
        self._require()
        recs = self.env['hr.department'].search_read(
            [('company_id', 'in', self.env.companies.ids)],
            ['id', 'display_name', 'company_id'], limit=500)
        needle = fold(term or '')
        out = [r for r in recs if not needle
               or needle in fold(r.get('display_name') or '')]
        return [{'id': r['id'], 'name': r.get('display_name') or '',
                 'company': (r.get('company_id') or [0, ''])[1]}
                for r in out[:int(limit or 20)]]

    @api.model
    def add_expense(self, vals):
        """Add an HR-operations or admin expense from the lens."""
        self._require_edit()
        vals = dict(vals or {})
        if not (vals.get('name') or '').strip():
            raise UserError(_("Say what the money was for."))
        try:
            amount = float(vals.get('amount') or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if amount <= 0:
            raise UserError(_("Put in what it cost."))
        btype = vals.get('budget_type')
        if btype not in ('hr_ops', 'admin'):
            raise UserError(_(
                "An expense belongs to HR operations or to Admin. What people "
                "are paid comes from the pay runs themselves and is never "
                "typed in here."))
        rec = self.env['pb.budget.expense'].create({
            'name': vals['name'].strip(),
            'spend_date': vals.get('spend_date') or fields.Date.context_today(self),
            'budget_type': btype,
            'department_id': int(vals.get('department_id') or 0) or False,
            'amount': amount,
            'supplier': (vals.get('supplier') or '').strip(),
            'note': (vals.get('note') or '').strip(),
            'company_id': self.env.company.id,
            'currency_id': self.env.company.currency_id.id,
        })
        return {'ok': True, 'id': rec.id,
                'message': _("Added — it counts against %(month)s's %(type)s "
                             "budget.",
                             month=rec.period_month.strftime('%B %Y'),
                             type=type_label(btype))}

    @api.model
    def export_board(self, fy=None, budget_type='manpower', currency='report',
                     kind='xlsx'):
        """The matrix as a workbook, or the year as a page."""
        self._require()
        return self.env['pb.budget.export'].build(
            fy=fy, budget_type=budget_type, currency=currency, kind=kind)
