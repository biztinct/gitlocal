# -*- coding: utf-8 -*-
"""`pb.retro.board` — the "Past-month re-work" screen's only server surface.

THE HERO: one sentence per currency once a re-work is worked out —
"Take-home +4,200,000 across 3 people · Income tax +310,000 · Employer cost
+5,100,000" — with, under it, the plain answer to "what happens next":
nothing has been paid or changed.

Rights: payroll managers (and administrators) — the people who approve or
reopen a pay run. Everybody else is refused here AND by the models' access
rules. Every read is scoped to the user's companies.
"""
import base64
import io
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain
from odoo.tools.misc import format_date, format_datetime

from .retro_review import (
    CHUNK, DONE_SLIP_STATES, MONTH_CAP, PEOPLE_CAP, TOTAL_KEYS, month_end,
    month_start, months_between, _loads,
)

_logger = logging.getLogger(__name__)

PAGE_SIZE = 40
PEOPLE_PAGE = 30
WHERE_DOMAINS = {
    'draft': [('state', '=', 'draft')],
    'done': [('state', '=', 'done')],
    'closed': [('state', '=', 'closed')],
    'cancelled': [('state', '=', 'cancelled')],
    # WDGAP W2-D2: sent for payment, not paid yet
    'topay': [('pay_state', 'in', ('waiting', 'approved', 'partly'))],
}


class PbRetroBoard(models.AbstractModel):
    _name = 'pb.retro.board'
    _inherit = ['pb.filter.mixin']
    _description = 'Past-month re-work board data'

    # ------------------------------------------------------------ gates
    @api.model
    def _can(self):
        return self.env['pb.retro.review']._pb_may_use()

    @api.model
    def _refusal(self):
        return _("Re-working past months is for the people who approve pay runs. Ask "
                 "your administrator for the payroll manager role to see this screen.")

    @api.model
    def _require(self):
        if not self._can():
            raise AccessError(self._refusal())

    @api.model
    def _scope(self):
        return [('company_id', 'in', self.env.companies.ids)]

    @api.model
    def _review(self, review_id):
        self._require()
        # A search, not a browse: the company rule decides what exists for
        # this reader, so another company's re-work reads "not there".
        try:
            rid = int(review_id or 0)
        except (TypeError, ValueError):
            rid = 0
        rec = self.env['pb.retro.review'].search(self._scope() + [('id', '=', rid)], limit=1)
        if not rec:
            raise UserError(_("This re-work is no longer there."))
        return rec

    @api.model
    def _safe(self, fn, default=0):
        try:
            with self.env.cr.savepoint(flush=False):
                return fn()
        except Exception as e:      # noqa: BLE001
            _logger.debug('retro board metric failed: %s', e)
            return default

    # ------------------------------------------------------------ money
    @api.model
    def _cur(self, currency):
        currency = currency or self.env.company.currency_id
        return {'id': currency.id, 'name': currency.name or '',
                'symbol': currency.symbol or currency.name or '',
                'position': currency.position or 'after',
                'decimals': currency.decimal_places or 0}

    @api.model
    def _money(self, amount, cur, signed=False):
        return self.env['pb.formula.studio']._th_money(amount or 0.0, cur) if not signed \
            else self._signed(amount, cur)

    @api.model
    def _signed(self, amount, cur):
        text = self.env['pb.formula.studio']._th_money(abs(amount or 0.0), cur)
        if not amount:
            return text
        return ('+' if amount > 0 else '−') + text

    @api.model
    def _plain(self, amount, cur):
        """A number without the currency, signed — for tables."""
        decimals = int(cur.get('decimals') or 0)
        from odoo.addons.pb_hr_payroll_formula.formula_engine import excel_semantics
        value = excel_semantics.excel_round(amount or 0.0, decimals)
        text = '{:,.{d}f}'.format(abs(value), d=decimals)
        return ('−' + text) if value < 0 else text

    @api.model
    def _plain_signed(self, amount, cur):
        text = self._plain(abs(amount or 0.0), cur)
        if not amount:
            return text
        return ('+' if amount > 0 else '−') + text

    @api.model
    def _date(self, day, fmt='d MMM y'):
        return format_date(self.env, day, date_format=fmt) if day else ''

    @api.model
    def _month(self, day):
        return format_date(self.env, day, date_format='MMMM y') if day else ''

    # ============================================================ the board
    @api.model
    def get_board(self):
        if not self._can():
            return {'allowed': False, 'why': self._refusal()}
        Review = self.env['pb.retro.review']
        scope = self._scope()
        kpis = {key: self._safe(lambda d=dom: Review.search_count(scope + d))
                for key, dom in WHERE_DOMAINS.items()}
        return {
            'allowed': True, 'why': '', 'can_write': True,
            'kpis': kpis,
            'total': self._safe(lambda: Review.search_count(scope)),
            'has_updates': bool(self.env.ref('pb_updates.action_pb_updates_desk',
                                             raise_if_not_found=False)),
        }

    # ------------------------------------------------------------ filter panel
    def _pbf_model(self):
        return 'pb.retro.review'

    def _pbf_screen(self):
        return 'retro_reviews'

    def _pbf_base_domain(self):
        return list(self._scope())

    def _pbf_search_domain(self, search):
        q = (search or '').strip()
        if not q:
            return None
        return Domain.OR([Domain('name', 'ilike', q), Domain('reason', 'ilike', q),
                          Domain('config_id.name', 'ilike', q)])

    def _pbf_sorts(self):
        return [
            {'key': 'new', 'label': _('Newest first'), 'order': 'create_date desc, id desc'},
            {'key': 'month', 'label': _('Latest months first'),
             'order': 'month_to desc, id desc'},
            {'key': 'scheme', 'label': _('Pay scheme, A to Z'), 'order': 'config_id, id desc'},
        ]

    def _pbf_spec(self):
        return [
            {'key': 'where', 'label': _('Where it is'), 'icon': 'route', 'group': 'pay',
             'type': 'choice', 'pinned': True, 'requires': ['state'],
             'options': [
                 {'value': 'draft', 'label': _('Draft'), 'tone': 'slate',
                  'domain': WHERE_DOMAINS['draft']},
                 {'value': 'done', 'label': _('Worked out'), 'tone': 'blue',
                  'domain': WHERE_DOMAINS['done']},
                 {'value': 'closed', 'label': _('Closed'), 'tone': 'green',
                  'domain': WHERE_DOMAINS['closed']},
                 {'value': 'cancelled', 'label': _('Cancelled'), 'tone': 'rose',
                  'domain': WHERE_DOMAINS['cancelled']},
             ]},
            {'key': 'payment', 'label': _('Payment'), 'icon': 'wallet', 'group': 'pay',
             'type': 'choice', 'pinned': True, 'requires': ['pay_state'],
             'options': [
                 {'value': 'topay', 'label': _('Waiting to be paid'), 'tone': 'amber',
                  'domain': WHERE_DOMAINS['topay']},
                 {'value': 'paid', 'label': _('Paid'), 'tone': 'green',
                  'domain': [('pay_state', '=', 'paid')]},
                 {'value': 'none', 'label': _('Not sent for payment'), 'tone': 'slate',
                  'domain': [('pay_state', '=', False)]},
             ]},
            {'key': 'scheme', 'label': _('Pay scheme'), 'icon': 'layers', 'group': 'pay',
             'type': 'many2one', 'path': 'config_id', 'pinned': True, 'label_sudo': True},
            {'key': 'currency', 'label': _('Currency'), 'icon': 'coins', 'group': 'pay',
             'type': 'many2one', 'path': 'currency_id'},
            {'key': 'who', 'label': _('Made by'), 'icon': 'user', 'group': 'other',
             'type': 'many2one', 'path': 'create_uid', 'label_sudo': True},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All re-works'), 'icon': 'history', 'filters': {}},
            {'key': 'open', 'label': _('Open'), 'filters': {'where': ['draft', 'done']}},
            {'key': 'closed', 'label': _('Closed'), 'filters': {'where': ['closed']}},
            {'key': 'topay', 'label': _('Waiting to be paid'),
             'filters': {'payment': ['topay']}},
        ]

    @api.model
    def pbf_layout(self, **kw):
        if not self._can():
            return {'refused': self._refusal()}
        return super().pbf_layout(**kw)

    @api.model
    def get_page(self, filters=None, search=None, sort=None, offset=0, limit=PAGE_SIZE):
        if not self._can():
            return {'rows': [], 'total': 0, 'offset': 0}
        Review = self.env['pb.retro.review']
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        order = self.pbf_order(sort) or 'create_date desc, id desc'
        rows = []
        for rec in Review.search(domain, order=order, offset=offset, limit=limit):
            try:
                rows.append(self._row(rec))
            except Exception as e:      # noqa: BLE001 — one bad row never blanks it
                _logger.debug('retro row %s failed: %s', rec.id, e)
        return {'rows': rows, 'total': Review.search_count(domain), 'offset': offset}

    @api.model
    def _state_label(self, rec):
        return dict(rec._fields['state']._description_selection(self.env)).get(rec.state, '')

    @api.model
    def _row(self, rec):
        cur = self._cur(rec.currency_id)
        roll = rec._pb_rollup() if rec.state in ('done', 'closed') else {}
        bucket = next(iter(roll.values()), None)
        net = bucket['diff']['net'] if bucket else 0.0
        people = len(bucket['people']) if bucket else 0
        return {
            'id': rec.id, 'name': rec.name or '',
            'scheme': rec.config_id.sudo().name or '',
            'months': rec._pb_months_label(),
            'reason': (rec.reason or '').strip().split('\n')[0][:140],
            'state': rec.state, 'state_label': self._state_label(rec),
            'currency': cur['name'],
            'net_label': self._signed(net, cur) if bucket else '',
            'net_sign': (1 if net > 0 else -1 if net < 0 else 0),
            'people': people,
            'payslips': len(rec.slip_ids),
            'when': format_datetime(self.env, rec.worked_out_on, dt_format='d MMM y, HH:mm')
            if rec.worked_out_on else '',
            'by': rec.create_uid.sudo().name or '',
            'pay_state': rec.pay_state or '',
            'pay_label': self._pay_state_label(rec),
        }

    @api.model
    def _pay_state_label(self, rec):
        if not rec.pay_state:
            return ''
        return dict(rec._fields['pay_state']._description_selection(self.env)).get(
            rec.pay_state, '')

    # ============================================================ new re-work
    @api.model
    def new_options(self):
        """Schemes with finished payslips, and the months each one has."""
        self._require()
        companies = tuple(self.env.companies.ids)
        self.env['hr.payslip'].flush_model(['formula_config_id', 'state', 'date_to',
                                            'company_id', 'payslip_run_id'])
        self.env.cr.execute("""
            SELECT s.formula_config_id,
                   date_trunc('month', s.date_to)::date AS m,
                   COUNT(*) FILTER (WHERE COALESCE(r.pb_run_kind, 'regular') = 'regular'),
                   COUNT(*) FILTER (WHERE COALESCE(r.pb_run_kind, 'regular') <> 'regular'),
                   COUNT(DISTINCT s.employee_id)
              FROM hr_payslip s
              LEFT JOIN hr_payslip_run r ON r.id = s.payslip_run_id
             WHERE s.state IN %s AND s.company_id IN %s
               AND s.formula_config_id IS NOT NULL AND s.date_to IS NOT NULL
             GROUP BY 1, 2
             ORDER BY 1, 2 DESC
        """, (DONE_SLIP_STATES, companies))
        months = {}
        for cfg_id, m, regular, other, people in self.env.cr.fetchall():
            months.setdefault(cfg_id, []).append({
                'month': fields.Date.to_string(m), 'label': self._month(m),
                'short': self._date(m, 'MMM y'), 'payslips': regular,
                'other': other, 'people': people,
            })
        Config = self.env['hr.formula.config'].sudo().with_context(active_test=False)
        out = []
        for cfg in Config.browse(list(months)).exists().sorted(lambda c: (c.name or '').lower()):
            if cfg.company_id and cfg.company_id.id not in companies:
                continue
            cur = cfg.scheme_currency()
            out.append({'id': cfg.id, 'name': cfg.name or '', 'currency': cur.get('name'),
                        'state': cfg.state, 'months': months[cfg.id][:36],
                        'company_id': (cfg.company_id or self.env.company).id})
        return {'schemes': out, 'month_cap': MONTH_CAP, 'people_cap': PEOPLE_CAP,
                'chunk': CHUNK}

    @api.model
    def _draft_review(self, vals):
        """An unsaved re-work for a preview — the same scope rules, no row."""
        vals = vals if isinstance(vals, dict) else {}
        cfg = self.env['hr.formula.config'].sudo().browse(int(vals.get('config_id') or 0)).exists()
        if not cfg:
            raise UserError(_("Pick the pay scheme first."))
        if cfg.company_id and cfg.company_id not in self.env.companies:
            raise UserError(_("This pay scheme belongs to a company you do not work in."))
        first = month_start(vals.get('month_from'))
        last = month_start(vals.get('month_to') or vals.get('month_from'))
        if not first or not last:
            raise UserError(_("Pick the months first."))
        if last < first:
            first, last = last, first
        emp_ids = [int(i) for i in (vals.get('employee_ids') or [])]
        # Built under sudo AFTER the gate and the company check above: the
        # contract-change rows it reads need formula rights a payroll manager
        # does not necessarily hold (every read of the re-work is a read for
        # the people who approve pay runs, whatever else they may edit).
        return self.env['pb.retro.review'].sudo().new({
            'company_id': (cfg.company_id or self.env.company).id,
            'config_id': cfg.id, 'month_from': first, 'month_to': last,
            'people': 'picked' if vals.get('people') == 'picked' else 'all',
            'employee_ids': [(6, 0, emp_ids)],
            'excluded_change_ids': [(6, 0, [int(i) for i in (vals.get('excluded_change_ids') or [])])],
            'reason': vals.get('reason') or '-',
            'currency_id': cfg.scheme_currency().get('id') or False,
        })

    @api.model
    def scope_preview(self, vals):
        """What the re-work would cover, before it exists: payslips, people,
        Extra/top-up payslips left out, and the contract changes found."""
        self._require()
        draft = self._draft_review(vals)
        n_months = months_between(draft.month_from, draft.month_to)
        regular, other = draft._pb_split()
        people = {}
        for slip in regular:
            emp = slip.employee_id
            row = people.setdefault(emp.id, {'id': emp.id, 'name': emp.sudo().name or '',
                                             'months': 0})
            row['months'] += 1
        changes = self._changes_payload(draft, regular)
        cur = self._cur(draft.currency_id)
        return {
            'months': n_months, 'month_cap': MONTH_CAP, 'too_many_months': n_months > MONTH_CAP,
            'payslips': len(regular), 'other': len(other),
            'other_kinds': sorted({(s.payslip_run_id.pb_run_kind or '') for s in other}),
            'people': len(people), 'people_cap': PEOPLE_CAP,
            'too_many_people': len(people) > PEOPLE_CAP,
            'changes': changes,
            'items': self._items(draft.config_id),
            'currency': cur,
            'label': draft._pb_months_label(),
        }

    @api.model
    def _changes_payload(self, review, slips):
        """The contract changes found, one row per change (months summed)."""
        cur = self._cur(review.currency_id)
        found = review._pb_contract_changes(slips)
        by_change = {}
        names = {s.id: s for s in slips}
        for slip_id, rows in found.items():
            slip = names.get(slip_id)
            for row in rows:
                entry = by_change.setdefault(row['change_id'], {
                    'id': row['change_id'], 'name': row['name'], 'code': row['code'],
                    'person': slip.employee_id.sudo().name or '',
                    'employee_id': slip.employee_id.id,
                    'old': self._money(row['old'], cur), 'new': self._money(row['new'], cur),
                    'effective': self._date(fields.Date.to_date(row['effective'])),
                    'entered': format_datetime(self.env, fields.Datetime.to_datetime(row['entered']),
                                               dt_format='d MMM y') if row['entered'] else '',
                    'months': [], 'total': 0.0, 'paid_back': False, 'paid_back_in': '',
                    'left_out': row['left_out'], 'note': row['note'],
                })
                entry['months'].append(self._date(slip.date_to, 'MMM y'))
                if row['paid_back']:
                    entry['paid_back'] = True
                    entry['paid_back_in'] = row['paid_back_in']
                else:
                    entry['total'] += row['delta']
        out = []
        for entry in sorted(by_change.values(), key=lambda e: (e['person'], e['name'], e['id'])):
            entry['total_label'] = self._signed(entry['total'], cur)
            entry['months_label'] = ', '.join(entry['months'])
            out.append(entry)
        return out

    @api.model
    def _items(self, config):
        """The pay items a what-if value can be typed for: number inputs."""
        Studio = self.env['pb.formula.studio']
        return [{'code': r.code, 'name': r.name or r.code}
                for r in Studio._th_items(config.sudo())]

    @api.model
    def people_options(self, vals, term=''):
        """People in the scheme's finished payslips of those months."""
        self._require()
        draft = self._draft_review(dict(vals or {}, people='all'))
        regular, _other = draft._pb_split()
        term = (term or '').strip().lower()
        seen = {}
        for slip in regular:
            emp = slip.employee_id.sudo()
            if emp.id in seen:
                seen[emp.id]['months'] += 1
                continue
            name = emp.name or ''
            if term and term not in name.lower() and term not in (emp.barcode or '').lower():
                continue
            seen[emp.id] = {'id': emp.id, 'name': name, 'code': emp.barcode or '',
                            'job': emp.job_title or '', 'months': 1}
        rows = sorted(seen.values(), key=lambda r: r['name'].lower())
        return {'rows': rows[:PEOPLE_CAP], 'more': max(0, len(rows) - PEOPLE_CAP)}

    @api.model
    def slip_options(self, vals, employee_id):
        """One person's finished regular payslips in scope, with the figures
        each was worked out from (for the what-if grid's "was")."""
        self._require()
        draft = self._draft_review(dict(vals or {}, people='all'))
        regular, _other = draft._pb_split()
        codes = {i['code'] for i in self._items(draft.config_id)}
        cur = self._cur(draft.currency_id)
        out = []
        for slip in regular.filtered(lambda s: s.employee_id.id == int(employee_id or 0)):
            inputs = _loads(slip.formula_input_values)
            out.append({
                'id': slip.id, 'label': self._month(month_start(slip.date_to)),
                'short': self._date(slip.date_to, 'MMM y'),
                'run': slip.payslip_run_id.name or '',
                'values': {c: inputs.get(c, 0) for c in codes if c in inputs},
                'labels': {c: self._money(self._n(inputs.get(c)), cur)
                           for c in codes if c in inputs},
            })
        return out

    @staticmethod
    def _n(value):
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @api.model
    def save_review(self, vals):
        """Create or change a re-work (draft or worked out). A change to what
        it covers or what changed sends a worked-out one back to draft."""
        self._require()
        vals = vals if isinstance(vals, dict) else {}
        draft = self._draft_review(vals)
        reason = (vals.get('reason') or '').strip()
        if not reason:
            raise UserError(_("Say why this re-work is needed, in a few words."))
        whatifs = self._clean_whatifs(draft, vals.get('whatifs'))
        data = {
            'config_id': draft.config_id.id, 'company_id': draft.company_id.id,
            'month_from': draft.month_from, 'month_to': draft.month_to,
            'people': draft.people, 'employee_ids': [(6, 0, draft.employee_ids.ids)],
            'reason': reason[:2000],
        }
        excluded = [(6, 0, draft.excluded_change_ids.ids)]
        Review = self.env['pb.retro.review']
        rec = Review.browse(int(vals.get('id') or 0)).exists() if vals.get('id') else Review
        if rec:
            rec = self._review(rec.id)
            if rec.state not in ('draft', 'done'):
                raise UserError(_("A closed or cancelled re-work cannot be changed."))
            rec.action_back_to_draft()
            rec.write(dict(data, whatif_ids=[(5, 0, 0)] + [(0, 0, w) for w in whatifs]))
        else:
            if draft.employee_ids and draft.people == 'picked' and \
                    len(draft.employee_ids) > PEOPLE_CAP:
                raise UserError(_("A re-work covers at most %s people.", PEOPLE_CAP))
            rec = Review.create(dict(data, whatif_ids=[(0, 0, w) for w in whatifs]))
        # the left-out contract changes: written under sudo after the gate
        # (see `_draft_review`), on a re-work this reader may change
        rec.sudo().with_context(pb_retro_internal=True).write({'excluded_change_ids': excluded})
        return {'ok': True, 'id': rec.id}

    @api.model
    def _clean_whatifs(self, draft, rows):
        regular, _other = draft._pb_split()
        allowed = set(regular.ids)
        items = {i['code']: i['name'] for i in self._items(draft.config_id)}
        out = []
        for seq, row in enumerate(rows or []):
            if not isinstance(row, dict):
                continue
            slip_id = int(row.get('payslip_id') or 0)
            code = row.get('code') or ''
            if not slip_id or not code:
                continue
            if slip_id not in allowed:
                raise UserError(_("A what-if value is for a payslip this re-work does not "
                                  "cover. Check its person and month."))
            if code not in items:
                raise UserError(_("Pick a pay item for every what-if value."))
            try:
                value = float(row.get('value'))
            except (TypeError, ValueError):
                raise UserError(_("Type a number for every what-if value.")) from None
            note = (row.get('note') or '').strip()
            if not note:
                raise UserError(_("Every what-if value needs a note: say where the new "
                                  "figure comes from."))
            out.append({'sequence': seq, 'payslip_id': slip_id, 'code': code,
                        'name': items[code], 'value': value, 'note': note[:240]})
        return out

    # ============================================================ working out
    @api.model
    def work_start(self, review_id):
        rec = self._review(review_id)
        return rec.pb_work_start()

    @api.model
    def work_chunk(self, review_id, slip_ids):
        rec = self._review(review_id)
        return rec.pb_work_chunk(slip_ids)

    @api.model
    def work_finish(self, review_id, ms=0):
        rec = self._review(review_id)
        rec.pb_work_finish(ms)
        return {'ok': True}

    @api.model
    def move(self, review_id, verb):
        rec = self._review(review_id)
        if verb == 'close':
            rec.action_close()
            return {'ok': True, 'msg': _("Closed. It stays here as a record and cannot be "
                                         "worked out again.")}
        if verb == 'cancel':
            rec.action_cancel()
            return {'ok': True, 'msg': _("Cancelled.")}
        if verb == 'send':
            rec.action_send_for_payment()
            rec.invalidate_recordset()
            if rec.pay_state == 'waiting':
                who = rec.sudo()._waiting_for()
                return {'ok': True, 'msg': _("Sent for approval — with %s.", who) if who
                        else _("Sent for approval.")}
            return {'ok': True, 'msg': _("Approved. The next pay run of this scheme pays "
                                         "the difference.")}
        if verb == 'withdraw':
            rec.action_withdraw_payment()
            return {'ok': True, 'msg': _("Withdrawn. Nothing will be paid.")}
        raise UserError(_("That cannot be done here."))

    @api.model
    def cancel_backpay(self, review_id, reason, employee_ids=None):
        """Undo approved back pay no finished pay run has paid (reason required)."""
        rec = self._review(review_id)
        res = rec.action_cancel_backpay(reason, employee_ids=employee_ids)
        return {'ok': True, 'msg': _("Cancelled. It will not be paid.") if res.get('cancelled')
                else _("Nothing was cancelled.")}

    # ============================================================ the payment
    @api.model
    def _payment(self, rec):
        """The Payment strip: where the back pay is, per person, in words."""
        cur = self._cur(rec.currency_id)
        sudo = rec.sudo()
        people = []
        entries_by_emp = {}
        for e in sudo.backpay_ids:
            entries_by_emp.setdefault(e.employee_id.id, []).append(e)
        totals = {'payable': 0, 'not_payable': 0, 'nothing': 0}
        for p in sudo.person_ids:
            totals[p.status] = totals.get(p.status, 0) + 1
            mine = entries_by_emp.get(p.employee_id.id, [])
            where, tone = self._where_words(rec, p, mine)
            people.append({
                'id': p.id, 'employee_id': p.employee_id.id, 'name': p.employee_name or '',
                'status': p.status, 'why': sudo._pb_why_text(p.why) if p.why else '',
                'net': self._signed(p.net, cur), 'net_sign': self._sign(p.net),
                'months': p.months_label or '', 'where': where, 'tone': tone,
                'can_cancel': any(e.state == 'open' or (e.state == 'reserved' and
                                  e.payslip_id.state not in ('done', 'paid'))
                                  for e in mine),
            })
        order = {'payable': 0, 'not_payable': 1, 'nothing': 2}
        people.sort(key=lambda x: (order.get(x['status'], 3), x['name'].lower()))
        payable = sudo.person_ids.filtered(lambda p: p.status == 'payable')
        live = sudo.backpay_ids.filtered(lambda e: e.state != 'cancelled')
        runs = sorted({e.run_id.name for e in live if e.run_id and e.run_id.name})
        state = rec.pay_state or ''
        locked = state in ('waiting', 'approved', 'partly', 'paid')
        n = len(payable)
        net_label = self._signed(sum(payable.mapped('net')), cur)
        who = rec.sudo()._waiting_for() if state == 'waiting' else ''
        return {
            'state': state, 'state_label': self._pay_state_label(rec),
            'summary': _("Take-home %s for 1 person", net_label) if n == 1 else
            _("Take-home %(net)s for %(n)s people", net=net_label, n=n),
            'with_line': _("With %s.", who) if who else '',
            'runs_line': _("In %s", ', '.join(runs)) if runs else '',
            'cancel_line': _("Cancelled: %s", rec.pay_cancel_reason)
            if rec.pay_cancel_reason else '',
            'waiting_with': rec.sudo()._waiting_for() if state == 'waiting' else '',
            'people': people[:300], 'more': max(0, len(people) - 300), 'counts': totals,
            'net': self._signed(sum(payable.mapped('net')), cur),
            'net_sign': self._sign(sum(payable.mapped('net'))),
            'runs': runs,
            'open': len(live.filtered(lambda e: e.state == 'open')),
            'reserved': len(live.filtered(lambda e: e.state == 'reserved')),
            'paid': len(live.filtered(lambda e: e.state == 'paid')),
            'cancel_reason': rec.pay_cancel_reason or '',
            'can_send': rec.state == 'done' and not locked and rec._pay_groups_held(),
            'can_withdraw': state == 'waiting',
            'can_cancel': state in ('approved', 'partly') and any(
                x['can_cancel'] for x in people),
        }

    @api.model
    def _where_words(self, rec, person, entries):
        """Where one person's back pay is, in a few words, and its tone."""
        if person.status != 'payable':
            return '', ''
        state = rec.pay_state or ''
        # BP1: a leaver is paid in their final payslip, never "the next pay run"
        final = person.why == 'final'
        later = _("Will be paid in their final payslip") if final \
            else _("Will be paid in the next pay run")
        if state == 'waiting':
            return _("Waiting for approval"), 'amber'
        if not entries:
            return (later, 'blue') if state == 'approved' else ('', '')
        live = [e for e in entries if e.state != 'cancelled']
        if not live:
            return _("Cancelled"), 'rose'
        if all(e.state == 'paid' for e in live):
            run = live[0].run_id.name or ''
            return (_("Paid in %s", run) if run else _("Paid")), 'green'
        reserved = [e for e in live if e.state == 'reserved']
        waiting = [e for e in live if e.state == 'open']
        if reserved and not waiting:
            return _("In pay run %s", reserved[0].run_id.name or ''), 'blue'
        if final and waiting and (any(e.waited for e in waiting)
                                  or not rec.sudo()._pb_final_payslip_to_come(
                                      person.employee_id)):
            # no next pay run for a leaver: whatever the final payslip did not
            # take is settled by hand (cancel it here first)
            return _("The final payslip does not take all of it — cancel the rest here "
                     "and settle it by hand"), 'amber'
        if waiting and any(e.waited for e in waiting):
            return _("Part waits for the next pay run (take-home would go below zero)"), 'amber'
        if any(e.state == 'paid' for e in live) or reserved:
            return _("Part paid, the rest in the next pay run"), 'amber'
        return later, 'blue'

    # ============================================================ the result
    @api.model
    def get_review(self, review_id):
        rec = self._review(review_id)
        cur = self._cur(rec.currency_id)
        slips = rec.slip_ids
        status = {key: 0 for key in ('same', 'changed', 'drift', 'error', 'skipped')}
        for row in slips:
            status[row.status] = status.get(row.status, 0) + 1
        worked = slips.filtered(lambda s: s.status != 'skipped')
        older = worked.filtered(lambda s: s.scheme_changed)
        unknown = worked.filtered(lambda s: s.scheme_unknown)
        roll = rec._pb_rollup()
        strips = []
        for bucket in roll.values():
            bcur = self._cur(bucket['currency'])
            diff = bucket['diff']
            items = sorted(bucket['items'].items(), key=lambda kv: (-abs(kv[1]), kv[0]))
            strips.append({
                'currency': bcur['name'],
                'people': len(bucket['people']),
                'net': self._signed(diff['net'], bcur), 'net_sign': self._sign(diff['net']),
                'gross': self._signed(diff['gross'], bcur), 'gross_sign': self._sign(diff['gross']),
                'deductions': self._signed(diff['deductions'], bcur),
                'employer': self._signed(diff['employer_cost'], bcur),
                'employer_sign': self._sign(diff['employer_cost']),
                'items': [{'name': k, 'amount': self._signed(v, bcur), 'sign': self._sign(v)}
                          for k, v in items if v][:3],
                'zero': not any(diff[k] for k in TOTAL_KEYS),
            })
        whatifs = [{
            'id': w.id, 'payslip_id': w.payslip_id.id,
            'employee_id': w.payslip_id.employee_id.id,
            'person': w.payslip_id.employee_id.sudo().name or '',
            'month': self._date(w.payslip_id.date_to, 'MMM y'),
            'code': w.code, 'name': w.name or w.code,
            'value': w.value, 'value_label': self._money(w.value, cur), 'note': w.note or '',
        } for w in rec.whatif_ids]
        issues = {
            'drift': [self._issue(s, cur) for s in slips.filtered(lambda s: s.status == 'drift')[:60]],
            'error': [self._issue(s, cur) for s in slips.filtered(lambda s: s.status == 'error')[:60]],
            'skipped': [self._issue(s, cur) for s in slips.filtered(lambda s: s.status == 'skipped')[:60]],
        }
        updates = self.env.ref('pb_updates.action_pb_updates_desk', raise_if_not_found=False)
        locked = rec.pay_state in ('waiting', 'approved', 'partly', 'paid')
        return {
            'id': rec.id, 'name': rec.name or '', 'state': rec.state,
            'state_label': self._state_label(rec),
            'scheme': rec.config_id.sudo().name or '', 'config_id': rec.config_id.id,
            'months': rec._pb_months_label(),
            'month_from': fields.Date.to_string(rec.month_from),
            'month_to': fields.Date.to_string(rec.month_to),
            'people': rec.people, 'employee_ids': rec.employee_ids.ids,
            'employees': [{'id': e.id, 'name': e.sudo().name or ''} for e in rec.employee_ids],
            'excluded_change_ids': rec.sudo().excluded_change_ids.ids,
            'reason': rec.reason or '',
            'currency': cur,
            'by': rec.create_uid.sudo().name or '',
            'made': format_datetime(self.env, rec.create_date, dt_format='d MMM y, HH:mm')
            if rec.create_date else '',
            'worked_out': format_datetime(self.env, rec.worked_out_on, dt_format='d MMM y, HH:mm')
            if rec.worked_out_on else '',
            'worked_by': rec.worked_out_by.sudo().name or '',
            'seconds': round((rec.work_ms or 0) / 1000.0, 1),
            'status': status,
            'payslips': len(worked),
            'scheme_banner': {
                'older': len(older), 'unknown': len(unknown), 'total': len(worked),
                'today': bool(older or unknown),
                'moved_since': bool(rec.scheme_hash) and
                rec.scheme_hash != rec.config_id.sudo()._content_hash(),
            },
            'strips': strips,
            'changes': self._used_changes(rec, cur),
            'whatifs': whatifs,
            'issues': issues,
            'updates_xmlid': 'pb_updates.action_pb_updates_desk' if updates else '',
            'payment': self._payment(rec),
            'can': {
                'work': rec.state in ('draft', 'done') and not locked,
                'edit': rec.state in ('draft', 'done') and not locked,
                'close': rec.state == 'done' and rec.pay_state not in (
                    'waiting', 'approved', 'partly'),
                'cancel': rec.state in ('draft', 'done') and not locked,
                'export': rec.state in ('done', 'closed'),
            },
        }

    @staticmethod
    def _sign(value):
        return 1 if (value or 0) > 0 else -1 if (value or 0) < 0 else 0

    @api.model
    def _issue(self, row, cur):
        drift = []
        for item in json.loads(row.drift_json or '[]'):
            drift.append({'name': item.get('name') or item.get('code'),
                          'stored': self._money(item.get('stored'), cur),
                          'today': self._money(item.get('today'), cur)})
        return {
            'id': row.id, 'payslip_id': row.payslip_id.id,
            'person': row.employee_name or '', 'month': self._date(row.month, 'MMM y'),
            'run': row.run_name or '', 'status': row.status,
            'skip': dict(row._fields['skip_reason']._description_selection(self.env)).get(
                row.skip_reason, '') if row.skip_reason else '',
            'error_item': row.error_item or '',
            'error_why': self.env['pb.formula.studio']._th_why(row.error_why)
            if row.status == 'error' and row.error_item else '',
            'no_inputs': row.no_inputs,
            'drift': drift[:8], 'drift_more': max(0, len(drift) - 8),
        }

    @api.model
    def _overlay_label(self, row, cur):
        if row.get('kind') == 'whatif':
            return _("What if %(item)s was %(value)s: %(note)s", item=row.get('name'),
                     value=self._money(row.get('value'), cur), note=row.get('note') or '')
        return _("Contract amount for %(item)s: %(old)s to %(new)s from %(day)s",
                 item=row.get('name'), old=self._money(row.get('old'), cur),
                 new=self._money(row.get('new'), cur),
                 day=self._date(fields.Date.to_date(row.get('effective'))))

    @api.model
    def _used_changes(self, rec, cur):
        """What changed, as worked out: one row per source, months summed."""
        out = {}
        for row in rec.slip_ids.filtered(lambda s: s.status != 'skipped'):
            for item in json.loads(row.overlay_json or '[]'):
                key = (item.get('kind'), item.get('change_id') or item.get('whatif_id'))
                entry = out.setdefault(key, {
                    'key': '%s-%s' % key, 'kind': item.get('kind'),
                    'label': self._overlay_label(item, cur),
                    'person': row.employee_name or '', 'months': [],
                    'applied': False, 'paid_back': bool(item.get('paid_back')),
                    'paid_back_in': item.get('paid_back_in') or '',
                    'left_out': bool(item.get('left_out')), 'replaced': False,
                    'total': 0.0, 'prorated': [],
                })
                entry['months'].append(self._date(row.month, 'MMM y'))
                if item.get('applied'):
                    entry['applied'] = True
                    if item.get('kind') == 'contract':
                        entry['total'] += item.get('delta') or 0.0
                        if item.get('covered') and item.get('period') and \
                                item['covered'] < item['period']:
                            entry['prorated'].append(_(
                                "%(month)s: %(n)s of %(d)s days",
                                month=self._date(row.month, 'MMM y'),
                                n=self._days(item['covered']), d=self._days(item['period'])))
                elif item.get('kind') == 'contract' and not item.get('paid_back') \
                        and not item.get('left_out'):
                    entry['replaced'] = True
        rows = sorted(out.values(), key=lambda e: (e['person'], e['kind'], e['label']))
        for entry in rows:
            entry['months_label'] = ', '.join(entry['months'])
            entry['total_label'] = self._signed(entry['total'], cur) \
                if entry['kind'] == 'contract' else ''
        return rows

    @staticmethod
    def _days(value):
        return ('%g' % round(float(value or 0.0), 2))

    @api.model
    def get_people(self, review_id, offset=0, limit=PEOPLE_PAGE, show='changed', search=''):
        """Per person, month by month: was / would be / difference per item."""
        rec = self._review(review_id)
        cur = self._cur(rec.currency_id)
        rows = rec.slip_ids
        if show == 'changed':
            rows = rows.filtered(lambda s: s.line_ids)
        elif show == 'issues':
            rows = rows.filtered(lambda s: s.status in ('drift', 'error', 'skipped'))
        q = (search or '').strip().lower()
        if q:
            rows = rows.filtered(lambda s: q in (s.employee_name or '').lower())
        by_emp = {}
        for row in rows:
            key = row.employee_id.id or ('n%s' % row.id)
            by_emp.setdefault(key, []).append(row)
        keys = sorted(by_emp, key=lambda k: ((by_emp[k][0].employee_name or '').lower(), str(k)))
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PEOPLE_PAGE), 100))
        except (TypeError, ValueError):
            offset, limit = 0, PEOPLE_PAGE
        people = []
        for key in keys[offset:offset + limit]:
            months = []
            net = 0.0
            for row in sorted(by_emp[key], key=lambda r: (r.month or fields.Date.today(), r.id)):
                approx = row.status == 'drift'
                lines = []
                causes = {}
                for item in json.loads(row.overlay_json or '[]'):
                    k = '%s-%s' % (item.get('kind'), item.get('change_id') or item.get('whatif_id'))
                    causes[k] = item
                month_why = []
                for line in row.line_ids.sorted(lambda l: (l.sequence, l.id)):
                    why = []
                    for c in json.loads(line.cause or '[]'):
                        item = causes.get('%s-%s' % (c.get('kind'), c.get('id')))
                        if item:
                            why.append(self._overlay_label(item, cur))
                    for text in why:
                        if text not in month_why:
                            month_why.append(text)
                    # money taken off or paid by the employer: going up is the
                    # bad direction, so the colour follows take-home
                    flip = -1 if line.band in ('deduction', 'employer') else 1
                    lines.append({
                        'id': line.id, 'name': line.name or line.code, 'band': line.band,
                        'counts': line.counts,
                        'was': self._plain(line.was, cur),
                        'would_be': self._plain(line.would_be, cur),
                        'diff': self._plain_signed(line.diff, cur),
                        'sign': self._sign(line.diff) * flip,
                        'why': why,
                    })
                # a reason is said once for the month; a line repeats it only
                # when its own reasons are not the month's
                for entry in lines:
                    if entry['why'] == month_why:
                        entry['why'] = []
                net += row.diff_net or 0.0
                months.append({
                    'id': row.id, 'payslip_id': row.payslip_id.id,
                    'month': self._month(row.month), 'short': self._date(row.month, 'MMM y'),
                    'run': row.run_name or '', 'status': row.status, 'approx': approx,
                    'net': self._signed(row.diff_net, cur), 'net_sign': self._sign(row.diff_net),
                    'was_net': self._money(row.was_net, cur),
                    'lines': lines,
                    'why': month_why,
                    'issue': self._issue(row, cur) if row.status in ('drift', 'error', 'skipped')
                    else False,
                })
            first = by_emp[key][0]
            people.append({
                'key': str(key), 'name': first.employee_name or '',
                'employee_id': first.employee_id.id,
                'net': self._signed(net, cur), 'net_sign': self._sign(net),
                'months': months,
                'changed': sum(1 for m in months if m['lines']),
            })
        return {'people': people, 'total': len(keys), 'offset': offset}

    @api.model
    def open_payslip(self, review_id, payslip_id):
        rec = self._review(review_id)
        slip = self.env['hr.payslip'].browse(int(payslip_id or 0)).exists()
        if not slip or slip.id not in rec.slip_ids.mapped('payslip_id').ids:
            raise UserError(_("That payslip is no longer there."))
        return {
            'type': 'ir.actions.act_window', 'res_model': 'hr.payslip', 'res_id': slip.id,
            'name': slip.display_name, 'view_mode': 'form', 'views': [[False, 'form']],
            'target': 'current',
        }

    # ============================================================ export
    @api.model
    def export_xlsx(self, review_id):
        """The result as an Excel workbook — one block per currency (R4).
        Built from the stored snapshot; nothing is worked out again."""
        rec = self._review(review_id)
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Font, PatternFill
        except Exception:       # noqa: BLE001
            return {'ok': False, 'msg': _("Excel files cannot be made on this server yet.")}
        wb = Workbook()
        ws = wb.active
        ws.title = _('Re-work')[:31]
        title = Font(bold=True, size=14, color='241F52')
        bold = Font(bold=True)
        muted = Font(color='64748B')
        head_fill = PatternFill('solid', fgColor='EDEAF8')
        head_font = Font(bold=True, color='241F52')
        r = 1
        ws.cell(r, 1, _('Past-month re-work · %s', rec.name or '')).font = title
        r += 1
        for label, value in (
                (_('Pay scheme'), rec.config_id.sudo().name or ''),
                (_('Months'), rec._pb_months_label()),
                (_('Why'), rec.reason or ''),
                (_('Worked out on'), format_datetime(self.env, rec.worked_out_on)
                 if rec.worked_out_on else ''),
                (_('Status'), self._state_label(rec))):
            ws.cell(r, 1, label).font = muted
            ws.cell(r, 2, value)
            r += 1
        ws.cell(r, 1, _('Nothing has been paid or changed. These are what the payslips '
                        'would say, worked out again with today\'s figures.')).font = muted
        r += 1
        worked = rec.slip_ids.filtered(lambda s: s.status != 'skipped')
        if worked.filtered(lambda s: s.scheme_changed or s.scheme_unknown):
            ws.cell(r, 1, _("Worked out with today's version of the scheme.")).font = muted
            r += 1
        r += 1
        head = [_('Person'), _('Month'), _('Pay item'), _('Was'), _('Would be'),
                _('Difference'), _('Compared exactly'), _('Why')]
        currencies = rec.line_ids.mapped('currency_id') | rec.slip_ids.mapped('currency_id')
        if not rec.line_ids:
            ws.cell(r, 1, _('No pay item would change.')).font = muted
            r += 2
        for currency in currencies.sorted('name'):
            lines = rec.line_ids.filtered(lambda l, c=currency: l.currency_id == c)
            if not lines:
                continue
            places = currency.decimal_places or 0
            fmt = '#,##0' if not places else '#,##0.' + '0' * places
            ws.cell(r, 1, _('Amounts in %s', currency.name)).font = bold
            r += 1
            for j, label in enumerate(head, start=1):
                cell = ws.cell(r, j, label)
                cell.font = head_font
                cell.fill = head_fill
                cell.alignment = Alignment(horizontal='right' if j in (4, 5, 6) else 'left')
            r += 1
            cur = self._cur(currency)
            for line in lines.sorted(lambda l: (l.slip_row_id.employee_name or '',
                                                l.month or fields.Date.today(),
                                                l.sequence, l.id)):
                row = line.slip_row_id
                causes = {('%s-%s' % (i.get('kind'), i.get('change_id') or i.get('whatif_id'))): i
                          for i in json.loads(row.overlay_json or '[]')}
                why = []
                for c in json.loads(line.cause or '[]'):
                    item = causes.get('%s-%s' % (c.get('kind'), c.get('id')))
                    if item:
                        why.append(self._overlay_label(item, cur))
                ws.cell(r, 1, row.employee_name or '')
                ws.cell(r, 2, self._date(line.month, 'MMM y'))
                ws.cell(r, 3, line.name or line.code)
                for j, value in ((4, line.was), (5, line.would_be), (6, line.diff)):
                    cell = ws.cell(r, j, float(value or 0.0))
                    cell.number_format = fmt
                ws.cell(r, 7, _('No') if row.status == 'drift' else _('Yes'))
                ws.cell(r, 8, '; '.join(why))
                r += 1
            r += 1
            roll = rec._pb_rollup().get(currency.id)
            if roll:
                for label, key in ((_('Gross pay'), 'gross'), (_('Deductions'), 'deductions'),
                                   (_('Take-home'), 'net'), (_('Employer cost'), 'employer_cost')):
                    ws.cell(r, 3, label).font = bold
                    cell = ws.cell(r, 6, float(roll['diff'][key] or 0.0))
                    cell.number_format = fmt
                    cell.font = bold
                    r += 1
            r += 1
        for col, width in zip('ABCDEFGH', (28, 12, 30, 16, 16, 16, 16, 70)):
            ws.column_dimensions[col].width = width
        # second sheet: every payslip and what was found
        ws2 = wb.create_sheet((_('Payslips'))[:31])
        labels = dict(rec.slip_ids._fields['status']._description_selection(self.env))
        head2 = [_('Person'), _('Month'), _('Pay run'), _('Result'), _('Note')]
        for j, label in enumerate(head2, start=1):
            cell = ws2.cell(1, j, label)
            cell.font = head_font
            cell.fill = head_fill
        i = 2
        for row in rec.slip_ids:
            cur = self._cur(row.currency_id)
            issue = self._issue(row, cur)
            note = ''
            if row.status == 'error':
                note = _('The formula for “%(item)s” has an error for this person (%(why)s).',
                         item=issue['error_item'] or _('a pay item'),
                         why=issue['error_why'] or _('it cannot be worked out'))
            elif row.status == 'drift':
                note = '; '.join(_('%(item)s: stored %(stored)s, worked out again %(today)s',
                                   item=d['name'], stored=d['stored'], today=d['today'])
                                 for d in issue['drift'])
            elif row.status == 'skipped':
                note = issue['skip']
            ws2.cell(i, 1, row.employee_name or '')
            ws2.cell(i, 2, self._date(row.month, 'MMM y'))
            ws2.cell(i, 3, row.run_name or '')
            ws2.cell(i, 4, labels.get(row.status, ''))
            ws2.cell(i, 5, note)
            i += 1
        for col, width in zip('ABCDE', (28, 12, 30, 26, 90)):
            ws2.column_dimensions[col].width = width
        # WDGAP W2-D2: third sheet — the payment, per person and pay item
        if rec.pay_state or rec.sudo().person_ids:
            ws3 = wb.create_sheet((_('Payment'))[:31])
            head3 = [_('Person'), _('Can be paid'), _('Why not'), _('Past month'),
                     _('Pay item'), _('Difference'), _('Where it is'), _('Pay run')]
            for j, label in enumerate(head3, start=1):
                cell = ws3.cell(1, j, label)
                cell.font = head_font
                cell.fill = head_fill
            entry_labels = dict(self.env['pb.retro.backpay']._fields['state']
                                ._description_selection(self.env))
            status_labels = dict(self.env['pb.retro.person']._fields['status']
                                 ._description_selection(self.env))
            i = 2
            by_emp = {}
            for e in rec.sudo().backpay_ids:
                by_emp.setdefault(e.employee_id.id, []).append(e)
            for p in rec.sudo().person_ids:
                mine = by_emp.get(p.employee_id.id, [])
                if not mine:
                    ws3.cell(i, 1, p.employee_name or '')
                    ws3.cell(i, 2, status_labels.get(p.status, ''))
                    ws3.cell(i, 3, rec.sudo()._pb_why_text(p.why) if p.why else '')
                    ws3.cell(i, 6, float(p.net or 0.0))
                    i += 1
                    continue
                for e in sorted(mine, key=lambda x: (x.month, x.sequence, x.id)):
                    places = e.currency_id.decimal_places or 0
                    fmt = '#,##0' if not places else '#,##0.' + '0' * places
                    ws3.cell(i, 1, p.employee_name or '')
                    ws3.cell(i, 2, status_labels.get(p.status, ''))
                    ws3.cell(i, 4, self._date(e.month, 'MMM y'))
                    ws3.cell(i, 5, e.name or e.code)
                    cell = ws3.cell(i, 6, float(e.amount or 0.0))
                    cell.number_format = fmt
                    ws3.cell(i, 7, entry_labels.get(e.state, ''))
                    ws3.cell(i, 8, e.run_id.name or '')
                    i += 1
            for col, width in zip('ABCDEFGH', (28, 18, 44, 12, 30, 16, 22, 30)):
                ws3.column_dimensions[col].width = width
        buf = io.BytesIO()
        wb.save(buf)
        stamp = fields.Date.to_string(rec.month_from)[:7]
        return {
            'ok': True,
            'file_b64': base64.b64encode(buf.getvalue()).decode('ascii'),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'filename': 're-work-%s-%s.xlsx' % (stamp, rec.id),
            'rows': len(rec.line_ids),
        }
