# -*- coding: utf-8 -*-
"""`pb.fund.payments` — the Fund & tax payments board's only server surface.

THE QUESTION THIS BOARD ANSWERS: for this pay month, what do we owe each fund
and the tax office, has it been approved, has it been paid, and where is the
receipt. A row is one payee in one currency; the drawer is the per-item
breakdown, the people behind it, the payslip lines, the proof and the history.

THE HERO is the month worked out in one press: "Work out what we owe for
October 2026" fills the board from the finished payslips, and every later press
says exactly what moved ("1 new, 2 updated, 1 changed since approval").

Rights (handover §1.7): the pay team reads (payroll users); the people who may
prepare a bank file act (`pb.money.approval.mixin` PAY_GROUPS — payroll
managers and the finance roles). Approving is the route's, in the one
Approvals inbox. A reader the board refuses is refused by the server too.
"""
import base64
import io
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain
from odoo.tools import html2plaintext
from odoo.tools.misc import format_date, format_datetime

from .fund_payee import MONEY_KINDS, ROLE_SHARE, SHARES
from .fund_payment import DONE_SLIP_STATES, UNPAID_STATES, month_of

_logger = logging.getLogger(__name__)

PAGE_SIZE = 60
READ_GROUPS = ('om_hr_payroll.group_hr_payroll_user',
               'om_hr_payroll.group_hr_payroll_manager')

WHERE_DOMAINS = {
    'to_pay': [('state', '=', 'to_pay')],
    'waiting': [('state', '=', 'waiting')],
    'approved': [('state', '=', 'approved')],
    'paid': [('state', '=', 'paid')],
    'cancelled': [('state', '=', 'cancelled')],
}


class PbFundPayments(models.AbstractModel):
    _name = 'pb.fund.payments'
    _inherit = ['pb.filter.mixin']
    _description = 'Fund and tax payments board data'

    # ------------------------------------------------------------ gates
    @api.model
    def _can_read(self):
        user = self.env.user
        if self.env.su or user._is_admin():
            return True
        if any(user.has_group(g) for g in READ_GROUPS):
            return True
        return self.env['pb.fund.payment']._pay_groups_held()

    @api.model
    def _can_write(self):
        return bool(self.env.su or self.env['pb.fund.payment']._pay_groups_held())

    @api.model
    def _refusal(self):
        return _("Fund and tax payments are looked after by the pay team. Ask your "
                 "administrator for payroll rights to see this screen.")

    @api.model
    def _require(self, write=False):
        if not self._can_read():
            raise AccessError(self._refusal())
        if write and not self._can_write():
            raise AccessError(_(
                "Only the people who may prepare a bank file — a payroll manager "
                "or a finance role — can change fund and tax payments."))

    @api.model
    def _scope(self):
        return [('company_id', 'in', self.env.companies.ids)]

    @api.model
    def _safe(self, fn, default=0):
        try:
            with self.env.cr.savepoint(flush=False):
                return fn()
        except Exception as e:      # noqa: BLE001
            _logger.debug('fund payments board metric failed: %s', e)
            return default

    @api.model
    def _label(self, month):
        return self.env['pb.fund.payment']._month_label(month)

    @api.model
    def _default_month(self):
        """The latest month with finished payslips; else the latest month with
        a payment row; else last month (contributions are paid the month
        after)."""
        self.env['hr.payslip'].flush_model(['state', 'date_to', 'company_id'])
        self.env.cr.execute("""
            SELECT MAX(date_to) FROM hr_payslip
             WHERE state IN %s AND company_id IN %s
        """, (DONE_SLIP_STATES, tuple(self.env.companies.ids)))
        last = self.env.cr.fetchone()[0]
        if not last:
            row = self.env['pb.fund.payment'].search(self._scope(), order='month desc',
                                                     limit=1)
            last = row.month if row else None
        if not last:
            last = fields.Date.context_today(self) - relativedelta(months=1)
        return month_of(last)

    @api.model
    def _month(self, month=None):
        return month_of(month) if month else self._default_month()

    # ------------------------------------------------------------ head
    @api.model
    def get_board(self, month=None):
        if not self._can_read():
            return {'allowed': False, 'why': self._refusal()}
        Pay = self.env['pb.fund.payment']
        month = self._month(month)
        scope = self._scope()
        in_month = scope + [('month', '=', month)]
        counts = {}
        for key, dom in WHERE_DOMAINS.items():
            counts[key] = self._safe(lambda d=dom: Pay.search_count(in_month + d))
        # Owed and paid per currency — never added across currencies (R2).
        money = {}
        for rec in self._safe(lambda: Pay.search(in_month + [('state', '!=', 'cancelled')]),
                              default=Pay):
            row = money.setdefault(rec.currency_id, {'owed': 0.0, 'paid': 0.0,
                                                     'left': 0.0})
            row['owed'] += rec.amount_owed
            if rec.state == 'paid':
                row['paid'] += rec.paid_amount
            else:
                row['left'] += rec.amount_owed
        totals = [{'currency': cur.name or '',
                   'owed': Pay._money(v['owed'], cur), 'paid': Pay._money(v['paid'], cur),
                   'left': Pay._money(v['left'], cur), 'left_zero': not v['left']}
                  for cur, v in sorted(money.items(), key=lambda kv: kv[0].name or '')]
        today = fields.Date.context_today(self)
        late_dom = scope + [('state', 'in', list(UNPAID_STATES)),
                            ('due_date', '<', today)]
        late = self._safe(lambda: Pay.search_count(late_dom))
        late_first = self._safe(lambda: Pay.search(late_dom, order='month asc', limit=1),
                                default=Pay)
        changed = self._safe(lambda: Pay.search_count(
            in_month + [('figures_changed', '=', True)]))
        payees = self.env['pb.fund.payee'].search_count(scope)
        return {
            'allowed': True,
            'why': '',
            'can_write': self._can_write(),
            'month': fields.Date.to_string(month),
            'month_label': self._label(month),
            'prev': fields.Date.to_string(month - relativedelta(months=1)),
            'next': fields.Date.to_string(month + relativedelta(months=1)),
            'next_label': self._label(month + relativedelta(months=1)),
            'is_future': month > month_of(today),
            'payees': payees,
            'slips': self._safe(lambda: self._done_slip_count(month)),
            'kpis': dict(counts, late=late, changed=changed,
                         late_month=fields.Date.to_string(late_first.month)
                         if late_first else '',
                         late_month_label=self._label(late_first.month)
                         if late_first else ''),
            'totals': totals,
            'total': self._safe(lambda: Pay.search_count(in_month)),
        }

    @api.model
    def _done_slip_count(self, month):
        nxt = month + relativedelta(months=1)
        return self.env['hr.payslip'].search_count([
            ('state', 'in', list(DONE_SLIP_STATES)), ('date_to', '>=', month),
            ('date_to', '<', nxt), ('company_id', 'in', self.env.companies.ids)])

    # ============================================================ filter panel
    def _pbf_model(self):
        return 'pb.fund.payment'

    def _pbf_screen(self):
        return 'fund_payments'

    def _pbf_base_domain(self):
        ctx = self._pbf_ctx()
        dom = list(self._scope())
        month = month_of(ctx.get('month')) if ctx.get('month') else None
        if month:
            dom.append(('month', '=', month))
        return dom

    def _pbf_search_domain(self, search):
        q = (search or '').strip()
        if not q:
            return None
        return Domain.OR([Domain('payee_id.name', 'ilike', q),
                          Domain('payment_reference', 'ilike', q)])

    def _pbf_sorts(self):
        return [
            {'key': 'due', 'label': _('Due soonest first'), 'order': 'due_date asc, id asc'},
            {'key': 'owed', 'label': _('Largest amount first'), 'order': 'amount_owed desc, id desc'},
            {'key': 'payee', 'label': _('Pay to, A to Z'), 'order': 'payee_id, id'},
        ]

    def _pbf_spec(self):
        today = fields.Date.context_today(self)
        return [
            {'key': 'where', 'label': _('Where it is'), 'icon': 'route',
             'group': 'pay', 'type': 'choice', 'pinned': True, 'requires': ['state'],
             'help': _('The steps above the table, plus payments that were cancelled.'),
             'options': [
                 {'value': 'to_pay', 'label': _('To pay'), 'tone': 'slate',
                  'domain': WHERE_DOMAINS['to_pay']},
                 {'value': 'waiting', 'label': _('Waiting for approval'), 'tone': 'amber',
                  'domain': WHERE_DOMAINS['waiting']},
                 {'value': 'approved', 'label': _('Approved, not paid'), 'tone': 'blue',
                  'domain': WHERE_DOMAINS['approved']},
                 {'value': 'paid', 'label': _('Paid'), 'tone': 'green',
                  'domain': WHERE_DOMAINS['paid']},
                 {'value': 'cancelled', 'label': _('Cancelled'), 'tone': 'rose',
                  'domain': WHERE_DOMAINS['cancelled']},
             ]},
            {'key': 'payee', 'label': _('Pay to'), 'icon': 'landmark', 'group': 'pay',
             'type': 'many2one', 'path': 'payee_id', 'pinned': True},
            {'key': 'late', 'label': _('Due date'), 'icon': 'calendarClock',
             'group': 'dates', 'type': 'choice', 'pinned': True, 'requires': ['due_date'],
             'options': [
                 {'value': 'late', 'label': _('Past its due date, not paid'), 'tone': 'rose',
                  'domain': [('state', 'in', list(UNPAID_STATES)),
                             ('due_date', '<', today)]},
                 {'value': 'soon', 'label': _('Due in the next 7 days'), 'tone': 'amber',
                  'domain': [('state', 'in', list(UNPAID_STATES)),
                             ('due_date', '>=', today),
                             ('due_date', '<=', today + relativedelta(days=7))]},
             ]},
            {'key': 'changed', 'label': _('Figures'), 'icon': 'triangleAlert',
             'group': 'other', 'type': 'choice', 'requires': ['figures_changed'],
             'options': [
                 {'value': 'changed', 'label': _('Changed since approval'), 'tone': 'amber',
                  'domain': [('figures_changed', '=', True)]},
             ]},
            {'key': 'currency', 'label': _('Currency'), 'icon': 'coins', 'group': 'pay',
             'type': 'many2one', 'path': 'currency_id'},
            {'key': 'owed', 'label': _('Owed'), 'icon': 'banknote', 'group': 'pay',
             'type': 'number', 'path': 'amount_owed', 'unit': 'money'},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All payments'), 'icon': 'landmark', 'filters': {}},
            {'key': 'to_pay', 'label': _('To pay'), 'filters': {'where': ['to_pay']}},
            {'key': 'waiting', 'label': _('Waiting for approval'),
             'filters': {'where': ['waiting']}},
            {'key': 'approved', 'label': _('Approved, not paid'),
             'filters': {'where': ['approved']}},
            {'key': 'late', 'label': _('Past due'), 'filters': {'late': ['late']}},
        ]

    @api.model
    def pbf_layout(self, **kw):
        if not self._can_read():
            return {'refused': self._refusal()}
        return super().pbf_layout(**kw)

    @api.model
    def _pbf_step_counts(self, filters, search):
        spec = self._pbf_clean_spec()
        s = next((x for x in spec if x['key'] == 'where'), None)
        if not s:
            return {}
        res = self._pbf_count_section(s, filters or {}, search, spec)
        return {r['v']: r['n'] for r in res.get('values') or []}

    @api.model
    def get_page(self, filters=None, search=None, sort=None, offset=0, limit=PAGE_SIZE):
        if not self._can_read():
            return {'rows': [], 'total': 0, 'offset': 0, 'steps': {}}
        Pay = self.env['pb.fund.payment']
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        order = self.pbf_order(sort) or 'due_date asc, payee_id, id'
        rows = []
        for rec in Pay.search(domain, order=order, offset=offset, limit=limit):
            try:
                rows.append(self._row(rec))
            except Exception as e:      # noqa: BLE001 — one bad row never blanks it
                _logger.debug('fund payment row %s failed: %s', rec.id, e)
        out = {'rows': rows, 'total': Pay.search_count(domain), 'offset': offset}
        if not offset:
            out['steps'] = self._safe(lambda: self._pbf_step_counts(filters, search),
                                      default={})
        return out

    @api.model
    def _row(self, rec):
        payee = rec.payee_id.sudo()
        paid = rec.state == 'paid'
        diff = rec.paid_difference if paid else 0.0
        return {
            'id': rec.id,
            'payee': payee.name or '',
            'month_label': self._label(rec.month),
            'currency': rec.currency_id.name or '',
            'owed_label': rec._money(rec.amount_owed),
            'employee_label': rec._money(rec.amount_employee),
            'employer_label': rec._money(rec.amount_employer),
            'paid_label': rec._money(rec.paid_amount) if paid else '',
            'diff_label': rec._signed_money(diff) if diff else '',
            'people': rec.head_count,
            'due_label': format_date(self.env, rec.due_date, date_format='d MMM y')
            if rec.due_date else '',
            'state': rec.state, 'state_label': rec._state_label(),
            'late': rec.is_late, 'paid_late': paid and rec.is_late,
            'changed': bool(rec.figures_changed),
            'changed_label': rec._signed_money(rec.live_diff) if rec.figures_changed else '',
            'has_receipt': bool(rec.evidence_attachment_id),
        }

    # ============================================================ drawer
    @api.model
    def get_payment(self, payment_id):
        self._require()
        rec = self.env['pb.fund.payment'].browse(int(payment_id or 0)).exists()
        if not rec:
            raise UserError(_("This payment no longer exists."))
        row = self._row(rec)
        payee = rec.payee_id.sudo()
        items = []
        for it in rec._breakdown():
            items.append({
                'key': '%s-%s' % (it.get('rule_id'), it.get('share')),
                'name': it.get('name') or it.get('code') or '',
                'scheme': it.get('scheme') or '',
                'share': it.get('share'),
                'share_label': dict(SHARES).get(it.get('share'), ''),
                'amount': rec._money(it.get('amount') or 0.0),
                'people': it.get('people') or 0,
            })
        trail = []
        for msg in rec.sudo().message_ids.filtered(
                lambda m: m.message_type in ('comment', 'notification') and m.body)[:15]:
            trail.append({'when': format_datetime(self.env, msg.date, dt_format='d MMM y, HH:mm'),
                          'who': msg.author_id.name or '',
                          'body': html2plaintext(msg.body or '').strip()})
        request = rec.approval_request_id
        can_write = self._can_write()
        receipt = rec.evidence_attachment_id
        row.update({
            'payee_id': payee.id,
            'month': fields.Date.to_string(rec.month),
            'items': items,
            'people_rows': self._safe(lambda: self._people(rec), default=[]),
            'slips': len(rec.slip_ids),
            'bank_details': payee.bank_details or '',
            'reference_text': payee.reference_text or '',
            'due_full': format_date(self.env, rec.due_date, date_format='d MMM y')
            if rec.due_date else '',
            'worked_out': format_datetime(self.env, rec.worked_out_on, dt_format='d MMM y, HH:mm')
            if rec.worked_out_on else '',
            'live_owed_label': rec._money(rec.live_owed),
            'paid_on': format_date(self.env, rec.paid_on, date_format='d MMM y')
            if rec.paid_on else '',
            'reference': rec.payment_reference or '',
            'note': rec.difference_note or '',
            'receipt': {'id': receipt.id, 'name': receipt.name,
                        'url': '/web/content/%s?download=true' % receipt.id} if receipt else False,
            'reopen_reason': rec.reopen_reason or '',
            'waiting_on': rec._waiting_for() if rec.state == 'waiting' else '',
            'request_id': request.id if request else 0,
            'owed_raw': rec.amount_owed,
            'decimals': rec.currency_id.decimal_places,
            'trail': trail,
            'can': {
                'submit': can_write and rec.state == 'to_pay' and rec.amount_owed > 0,
                'withdraw': can_write and rec.state == 'waiting' and bool(request)
                and (request.submitter_uid.id == self.env.uid or self.env.user._is_admin()),
                'pay': can_write and rec.state == 'approved',
                'reopen': can_write and rec.state in ('approved', 'paid'),
                'lines': bool(rec.slip_ids),
            },
        })
        return row

    @api.model
    def _people(self, rec, cap=100):
        """Who is behind the figure: per person, the employee and employer share
        — read from the payslips the figure was worked out from."""
        pairs = {(it.get('config_id'), it.get('code')): it.get('share')
                 for it in rec._breakdown()}
        if not rec.slip_ids or not pairs:
            return []
        self.env['hr.payslip.line'].flush_model(['slip_id', 'code', 'total'])
        self.env.cr.execute("""
            SELECT s.employee_id, s.formula_config_id, l.code, COALESCE(l.total, 0)
              FROM hr_payslip_line l
              JOIN hr_payslip s ON s.id = l.slip_id
             WHERE s.id IN %s AND l.code IN %s
        """, (tuple(rec.slip_ids.ids), tuple(sorted({c for _x, c in pairs if c}))))
        per = {}
        for emp_id, config_id, code, total in self.env.cr.fetchall():
            share = pairs.get((config_id, code))
            if not share:
                continue
            row = per.setdefault(emp_id, {'employee': 0.0, 'employer': 0.0})
            row[share] += abs(total or 0.0)
        names = {e.id: e for e in self.env['hr.employee'].sudo().with_context(
            active_test=False).browse(list(per))}
        out = []
        for emp_id, v in sorted(per.items(), key=lambda kv: -(kv[1]['employee']
                                                               + kv[1]['employer'])):
            if not (v['employee'] or v['employer']):
                continue
            emp = names.get(emp_id)
            out.append({'id': emp_id, 'name': emp.name if emp else '',
                        'code': (emp.barcode or '') if emp else '',
                        'employee': rec._money(v['employee']),
                        'employer': rec._money(v['employer']),
                        'total': rec._money(v['employee'] + v['employer'])})
        return {'rows': out[:cap], 'more': max(0, len(out) - cap)}

    @api.model
    def open_lines(self, payment_id):
        self._require()
        rec = self.env['pb.fund.payment'].browse(int(payment_id or 0)).exists()
        if not rec:
            raise UserError(_("This payment no longer exists."))
        return rec.action_open_lines()

    @api.model
    def open_request(self, payment_id):
        self._require()
        rec = self.env['pb.fund.payment'].browse(int(payment_id or 0)).exists()
        request = rec.approval_request_id if rec else False
        return {
            'type': 'ir.actions.client', 'tag': 'pb_approval_inbox',
            'name': _('Approvals'),
            'params': {'request_id': request.id if request else 0},
        }

    # ============================================================ the moves
    @api.model
    def work_out(self, month):
        self._require(write=True)
        month = month_of(month)
        if not month:
            raise UserError(_("Pick the pay month first."))
        if not self.env['pb.fund.payee'].search_count(self._scope()):
            raise UserError(_("Say who you pay first: press “Who we pay” and add the "
                              "funds and offices, or let Payobook suggest them."))
        stats = self.env['pb.fund.payment'].pb_work_out(month)
        label = self._label(month)
        bits = []
        if stats['created']:
            bits.append(_("%s new", stats['created']))
        if stats['updated']:
            bits.append(_("%s updated", stats['updated']))
        if stats['changed']:
            bits.append(_("%s changed since approval", stats['changed']))
        if stats['cancelled']:
            bits.append(_("%s no longer owed", stats['cancelled']))
        if bits:
            msg = _("%(month)s worked out: %(what)s.", month=label, what=', '.join(bits))
        elif stats['unchanged']:
            msg = _("%s worked out again: nothing changed.", label)
        elif not self._done_slip_count(month):
            msg = _("No payslips of %s are finished yet, so nothing is owed yet.", label)
        else:
            msg = _("The finished payslips of %s hold none of the pay items your "
                    "funds are set up with.", label)
        return dict(stats, msg=msg)

    @api.model
    def move(self, payment_id, verb, vals=None):
        self._require(write=True)
        vals = vals if isinstance(vals, dict) else {}
        rec = self.env['pb.fund.payment'].browse(int(payment_id or 0)).exists()
        if not rec:
            raise UserError(_("This payment no longer exists."))
        if verb == 'submit':
            rec.action_submit()
            rec.invalidate_recordset()
            msg = _("Approved — it can be paid now.") if rec.state == 'approved' \
                else _("Sent for approval.")
        elif verb == 'withdraw':
            rec.action_withdraw(vals.get('reason'))
            msg = _("Withdrawn. It is back to “To pay”.")
        elif verb == 'pay':
            rec.action_mark_paid(paid_on=vals.get('paid_on'),
                                 paid_amount=vals.get('paid_amount'),
                                 reference=vals.get('reference'),
                                 attachment_id=vals.get('attachment_id'),
                                 note=vals.get('note'))
            msg = _("Marked as paid. The receipt is kept with it.")
        elif verb == 'reopen':
            rec.action_reopen(vals.get('reason'))
            msg = _("Reopened. It is back to “To pay” and needs a new approval.")
        else:
            raise UserError(_("That cannot be done here."))
        rec.invalidate_recordset()
        return {'ok': True, 'msg': msg, 'state': rec.state}

    @api.model
    def attach_receipt(self, payment_id, name, data_b64, mimetype=None):
        self._require(write=True)
        return self.env['pb.fund.payment'].pb_attach_evidence(payment_id, name, data_b64,
                                                              mimetype)

    # ============================================================ who we pay
    @api.model
    def _item_payload(self, rule, share, payee=None):
        cfg = rule.config_id
        return {
            'rule_id': rule.id, 'share': share,
            'label': rule.name or rule.code, 'code': rule.code,
            'scheme': cfg.name or '', 'currency': cfg.currency_id.name or '',
            'role': rule.net_role or '',
            'detail': bool(rule.net_role_detail),
            'on_payslip': bool(rule.appears_on_payslip),
            'active_scheme': cfg.state == 'active',
        }

    @api.model
    def get_payees(self):
        self._require()
        out = []
        for payee in self.env['pb.fund.payee'].search(self._scope()):
            items = [self._item_payload(i.rule_id.sudo(), i.share, payee)
                     for i in payee.item_ids if i.rule_id]
            currencies = sorted({i['currency'] for i in items if i['currency']})
            warnings = []
            if not items:
                warnings.append(_("No pay items yet — nothing is owed to it."))
            if len(currencies) > 1:
                warnings.append(_("Its pay items come from schemes paying in %s. Each "
                                  "currency is worked out as its own payment.",
                                  ', '.join(currencies)))
            for share in ('employee', 'employer'):
                mine = [i for i in items if i['share'] == share]
                if any(i['detail'] for i in mine) and any(not i['detail'] for i in mine):
                    warnings.append(_("Some of its pay items are already included in "
                                      "another total. Pick the total or its parts, not "
                                      "both, or the amount is counted twice."))
                    break
            if any(not i['on_payslip'] for i in items):
                warnings.append(_("A pay item is not printed on payslips, so there is "
                                  "nothing to add up for it."))
            out.append({
                'id': payee.id, 'name': payee.name or '',
                'currency_id': payee.currency_id.id, 'currency': payee.currency_id.name or '',
                'due_day': payee.due_day, 'bank_details': payee.bank_details or '',
                'reference_text': payee.reference_text or '',
                'items': items, 'warnings': warnings,
                'employee_items': len([i for i in items if i['share'] == 'employee']),
                'employer_items': len([i for i in items if i['share'] == 'employer']),
            })
        # Active currencies, plus every currency a payee or a pay scheme of
        # these companies uses — a scheme may pay in a currency the database
        # keeps inactive (SC1), and a select without it shows the wrong one.
        Currency = self.env['res.currency'].sudo().with_context(active_test=False)
        used = self.env['pb.fund.payee'].search(self._scope()).mapped('currency_id') \
            | self.env['hr.formula.config'].sudo().search([
                ('company_id', 'in', self.env.companies.ids)]).mapped('currency_id')
        currencies = (Currency.search([('active', '=', True)]) | used).sorted('name')
        return {'payees': out, 'can_write': self._can_write(),
                'currencies': [{'id': c.id, 'name': c.name} for c in currencies],
                'company_currency_id': self.env.company.currency_id.id}

    @api.model
    def item_options(self, term='', payee_id=0):
        """Pay items a payee can be given: the companies' active schemes'
        money components, the ones taken off pay or paid by the employer
        first. A typed term searches every money component."""
        self._require()
        term = (term or '').strip()
        domain = [('config_id.state', '=', 'active'),
                  ('config_id.company_id', 'in', self.env.companies.ids)]
        if term:
            domain += ['|', ('name', 'ilike', term), ('code', 'ilike', term)]
        else:
            domain += [('net_role', 'in', list(ROLE_SHARE))]
        rules = self.env['hr.formula.rule'].sudo().search(
            domain, order='config_id, sequence, id', limit=120).filtered(
                lambda r: (r.value_kind or 'money') in MONEY_KINDS)
        taken = {}
        for item in self.env['pb.fund.payee.item'].sudo().search([
                ('rule_id', 'in', rules.ids), ('payee_id.active', '=', True)]):
            if item.payee_id.id != int(payee_id or 0):
                taken[item.rule_id.id] = item.payee_id.name
        out = []
        for rule in rules:
            row = self._item_payload(rule, ROLE_SHARE.get(rule.net_role, 'employee'))
            row['taken_by'] = taken.get(rule.id, '')
            out.append(row)
        return out

    @api.model
    def save_payee(self, vals):
        self._require(write=True)
        vals = vals if isinstance(vals, dict) else {}
        Payee = self.env['pb.fund.payee']
        payee = Payee.browse(int(vals.get('id') or 0)).exists() if vals.get('id') else Payee
        name = (vals.get('name') or '').strip()
        if not name:
            raise UserError(_("Give the fund or office a name."))
        company = payee.company_id if payee else self.env.company
        try:
            due_day = int(vals.get('due_day') or 15)
        except (TypeError, ValueError):
            due_day = 15
        currency = self.env['res.currency'].browse(int(vals.get('currency_id') or 0)).exists() \
            or company.currency_id
        items = self.env['pb.fund.payee.item']._pb_clean_items(vals.get('items'), company)
        data = {
            'name': name[:120], 'due_day': due_day, 'currency_id': currency.id,
            'bank_details': (vals.get('bank_details') or '').strip() or False,
            'reference_text': (vals.get('reference_text') or '').strip()[:120] or False,
        }
        if payee:
            # The list the person saved IS the list: every old line goes, the
            # saved ones come back (one write, so the one-payee rule is checked
            # against the final state).
            commands = [(2, it.id) for it in payee.item_ids]
            commands += [(0, 0, i) for i in items]
            payee.write(dict(data, item_ids=commands))
        else:
            payee = Payee.create(dict(data, company_id=company.id,
                                      item_ids=[(0, 0, i) for i in items]))
        return {'ok': True, 'id': payee.id}

    @api.model
    def archive_payee(self, payee_id):
        self._require(write=True)
        payee = self.env['pb.fund.payee'].browse(int(payee_id or 0)).exists()
        if not payee:
            raise UserError(_("This payee no longer exists."))
        payee.write({'active': False})
        return {'ok': True}

    @api.model
    def suggest(self):
        self._require()
        return self.env['pb.fund.payee']._pb_suggest(self.env.companies)

    @api.model
    def create_from_suggestions(self, proposals):
        """Create the payees a person accepted in the Suggest dialog.

        [{'name', 'company_id', 'into': key or '', 'key', 'items': [{'rule_id',
          'share', 'on'}]}] — a proposal with `into` set joins another one.
        """
        self._require(write=True)
        proposals = [p for p in (proposals or []) if isinstance(p, dict)]
        by_key = {p.get('key'): p for p in proposals}
        merged = {}
        for p in proposals:
            target = p
            seen = set()
            while target.get('into') and target.get('into') in by_key \
                    and target.get('key') not in seen:
                seen.add(target.get('key'))
                target = by_key[target['into']]
            bucket = merged.setdefault(target.get('key'), {
                'name': (target.get('name') or '').strip(),
                'company_id': target.get('company_id'), 'items': []})
            bucket['items'] += [i for i in (p.get('items') or [])
                                if isinstance(i, dict) and i.get('on', True)]
        made = 0
        for bucket in merged.values():
            if not bucket['items'] or not bucket['name']:
                continue
            company = self.env['res.company'].browse(int(bucket['company_id'] or 0)).exists()
            if not company or company.id not in self.env.companies.ids:
                company = self.env.company
            items = self.env['pb.fund.payee.item']._pb_clean_items(bucket['items'], company)
            if not items:
                continue
            first = self.env['hr.formula.rule'].sudo().browse(items[0]['rule_id'])
            self.env['pb.fund.payee'].create({
                'name': bucket['name'][:120], 'company_id': company.id,
                'currency_id': (first.config_id.currency_id or company.currency_id).id,
                'item_ids': [(0, 0, i) for i in items]})
            made += 1
        return {'ok': True, 'made': made}

    # ============================================================ export
    @api.model
    def export_xlsx(self, month=None):
        """The month as an Excel workbook, one block per currency (R2).
        Cloned from the Explorer's export: nothing is stored."""
        self._require()
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Font, PatternFill
        except Exception:       # noqa: BLE001
            return {'ok': False, 'msg': _("Excel files cannot be made on this server yet.")}
        month = self._month(month)
        Pay = self.env['pb.fund.payment']
        recs = Pay.search(self._scope() + [('month', '=', month),
                                           ('state', '!=', 'cancelled')],
                          order='currency_id, due_date, payee_id, id')
        wb = Workbook()
        ws = wb.active
        ws.title = (_('Fund payments'))[:31]
        bold = Font(bold=True)
        muted = Font(color='64748B')
        head_fill = PatternFill('solid', fgColor='EDEAF8')
        head_font = Font(bold=True, color='241F52')
        r = 1
        ws.cell(r, 1, _('Fund and tax payments · %s', self._label(month))).font = \
            Font(bold=True, size=14, color='241F52')
        r += 1
        ws.cell(r, 1, _('Made on')).font = muted
        ws.cell(r, 2, fields.Datetime.context_timestamp(
            self, fields.Datetime.now()).strftime('%Y-%m-%d %H:%M'))
        r += 2
        head = [_('Pay to'), _('Due by'), _('People'), _('Employee share'),
                _('Employer share'), _('Owed'), _('Paid'), _('Difference'),
                _('Status'), _('Paid on'), _('Payment reference')]
        if not recs:
            ws.cell(r, 1, _('Nothing has been worked out for this month yet.')).font = muted
        for currency in recs.mapped('currency_id'):
            block = recs.filtered(lambda x, c=currency: x.currency_id == c)
            places = currency.decimal_places
            fmt = '#,##0' if not places else '#,##0.' + '0' * places
            ws.cell(r, 1, _('Amounts in %s', currency.name)).font = bold
            r += 1
            for j, label in enumerate(head, start=1):
                cell = ws.cell(r, j, label)
                cell.font = head_font
                cell.fill = head_fill
                cell.alignment = Alignment(horizontal='left' if j in (1, 2, 9, 10, 11)
                                           else 'right')
            r += 1
            sums = [0.0] * 5
            for rec in block:
                paid = rec.state == 'paid'
                values = [rec.amount_employee, rec.amount_employer, rec.amount_owed,
                          rec.paid_amount if paid else 0.0,
                          rec.paid_difference if paid else 0.0]
                ws.cell(r, 1, rec.payee_id.sudo().name or '')
                ws.cell(r, 2, format_date(self.env, rec.due_date) if rec.due_date else '')
                ws.cell(r, 3, rec.head_count)
                for j, value in enumerate(values, start=4):
                    cell = ws.cell(r, j, float(value or 0.0))
                    cell.number_format = fmt
                    sums[j - 4] += float(value or 0.0)
                ws.cell(r, 9, rec._state_label())
                ws.cell(r, 10, format_date(self.env, rec.paid_on) if rec.paid_on else '')
                ws.cell(r, 11, rec.payment_reference or '')
                r += 1
            ws.cell(r, 1, _('Total')).font = bold
            for j, value in enumerate(sums, start=4):
                cell = ws.cell(r, j, value)
                cell.number_format = fmt
                cell.font = bold
            r += 2
        for col, width in zip('ABCDEFGHIJK', (30, 14, 9, 18, 18, 18, 18, 16, 20, 14, 22)):
            ws.column_dimensions[col].width = width
        buf = io.BytesIO()
        wb.save(buf)
        return {
            'ok': True,
            'file_b64': base64.b64encode(buf.getvalue()).decode('ascii'),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'filename': 'fund-payments-%s.xlsx' % fields.Date.to_string(month)[:7],
            'rows': len(recs),
        }
