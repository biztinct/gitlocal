# -*- coding: utf-8 -*-
"""`pb.loans` — the Loans board's only server surface.

THE QUESTION THIS BOARD ANSWERS: who owes the company what, and what comes
off pay next. A row is one loan with its balance on it; the drawer is the plan,
the history and the moves (each with a reason). The hero is the live plan in
"New loan": the instalments appear, month by month, as the amount is typed.

Rights (WDGAP PR-B §9): the pay team — payroll officers and managers — reads
and manages; approving is the route's (the one Approvals inbox). A reader the
board refuses is refused by the server too.
"""
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain
from odoo.tools import html2plaintext
from odoo.tools.misc import format_datetime

from .loan import GROUP_MANAGER, GROUP_OFFICER, OPEN_STATES, month_of

_logger = logging.getLogger(__name__)

PAGE_SIZE = 60

WHERE_DOMAINS = {
    'draft': [('state', '=', 'draft')],
    'waiting': [('state', '=', 'waiting')],
    'running': [('state', '=', 'running')],
    'paused': [('state', '=', 'paused')],
    'closed': [('state', '=', 'closed')],
    'ended': [('state', 'in', ('cancelled', 'refused'))],
}


def _initials(name):
    parts = [p for p in (name or '').split() if p]
    if not parts:
        return '?'
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


class PbLoans(models.AbstractModel):
    _name = 'pb.loans'
    _inherit = ['pb.filter.mixin']
    _description = 'Loans board data'

    # ------------------------------------------------------------ gates
    @api.model
    def _can_read(self):
        user = self.env.user
        return bool(self.env.su or user._is_admin() or user.has_group(GROUP_OFFICER)
                    or user.has_group(GROUP_MANAGER))

    @api.model
    def _can_set_up(self):
        user = self.env.user
        return bool(self.env.su or user._is_admin() or user.has_group(GROUP_MANAGER))

    @api.model
    def _refusal(self):
        return _("Loans are looked after by the pay team. Ask your administrator to "
                 "give you payroll officer rights to see this screen.")

    @api.model
    def _require(self):
        if not self._can_read():
            raise AccessError(self._refusal())

    @api.model
    def _scope(self):
        return [('company_id', 'in', self.env.companies.ids)]

    @api.model
    def _safe(self, fn, default=0):
        try:
            with self.env.cr.savepoint(flush=False):
                return fn()
        except Exception as e:      # noqa: BLE001
            _logger.debug('loans board metric failed: %s', e)
            return default

    # ------------------------------------------------------------ head
    @api.model
    def get_board(self):
        if not self._can_read():
            return {'allowed': False, 'why': self._refusal()}
        Loan = self.env['pb.loan']
        scope = self._scope()

        def count(key):
            return self._safe(lambda: Loan.search_count(scope + WHERE_DOMAINS[key]))

        this_month = month_of(fields.Date.context_today(self))
        closed_mtd = self._safe(lambda: Loan.search_count(
            scope + [('state', '=', 'closed'), ('closed_on', '>=', this_month)]))
        # Totals never add two currencies (multi-scheme-currency-gaps).
        left = {}
        for loan in self._safe(lambda: Loan.search(scope + [('state', 'in', OPEN_STATES)]),
                               default=Loan):
            left.setdefault(loan.currency_id, 0.0)
            left[loan.currency_id] += loan.balance
        left_label = ' · '.join(Loan._money(v, c) for c, v in sorted(
            left.items(), key=lambda kv: kv[0].name or '')) if left else ''
        return {
            'allowed': True,
            'why': '',
            'can_write': True,
            'can_set_up': self._can_set_up(),
            'total': self._safe(lambda: Loan.search_count(scope)),
            'kpis': {
                'waiting': count('waiting'),
                'running': count('running'),
                'paused': count('paused'),
                'closed_mtd': closed_mtd,
                'left_label': left_label,
                'currencies': len(left),
            },
            'kinds': [{'key': k, 'label': v} for k, v in
                      Loan._fields['kind']._description_selection(self.env)],
            'leaving': [{'key': k, 'label': v} for k, v in
                        Loan._fields['on_leaving']._description_selection(self.env)],
            'setup': self._safe(self._setup, default={'schemes': [], 'missing': 0}),
            'notes': self._safe(self._run_notes, default=[]),
            'this_month': fields.Date.to_string(this_month),
            'next_month': fields.Date.to_string(this_month + relativedelta(months=1)),
        }

    @api.model
    def _setup(self):
        """Every active pay scheme that can take an instalment, and its pay item."""
        Config = self.env['hr.formula.config'].sudo()
        configs = Config.search([('state', '=', 'active'),
                                 ('company_id', 'in', self.env.companies.ids),
                                 ('cycle_type', '!=', 'mid_cycle')], order='name')
        open_loans = self.env['pb.loan'].search(self._scope() + [('state', 'in', OPEN_STATES)])
        rows, missing = [], 0
        for config in configs:
            rule = config._pb_loan_rule()
            app = bool(getattr(config, 'application_data_enabled', False))
            options = [{'id': r.id, 'label': '%s (%s)' % (r.name or r.code, r.code)}
                       for r in config.rule_ids.filtered(
                           lambda r: r.column_type == 'input'
                           and (r.value_kind or 'money') == 'money'
                           and not r.is_contract_component).sorted('sequence')]
            in_company = open_loans.filtered(lambda l: l.company_id == config.company_id)
            if in_company and not rule:
                missing += 1
            rows.append({
                'id': config.id, 'name': config.name or '',
                'currency': config.currency_id.name or '',
                'rule_id': rule.id if rule else 0,
                'rule_label': ('%s (%s)' % (rule.name or rule.code, rule.code)) if rule else '',
                'application': app,
                'keyed': bool(rule and (getattr(rule, 'application_source_key', '') or '') ==
                              'loans.instalment'),
                'options': options,
                'needed': bool(in_company),
            })
        return {'schemes': rows, 'missing': missing}

    @api.model
    def _run_notes(self):
        """Pay runs still being prepared that did not take an instalment
        somebody owed (a finished payslip can no longer be changed)."""
        slips = self.env['hr.payslip'].sudo().search([
            ('pb_loan_issue', '!=', False),
            ('state', 'not in', ('cancel', 'done', 'paid')),
            ('payslip_run_id', '!=', False),
            ('company_id', 'in', self.env.companies.ids)])
        out = []
        for run in slips.mapped('payslip_run_id').sorted('id', reverse=True)[:5]:
            sentences = run.pb_loan_notes()
            if sentences:
                out.append({'id': run.id, 'name': run.name or '',
                            'sentences': sentences})
        return out

    # ============================================================ filter panel
    def _pbf_model(self):
        return 'pb.loan'

    def _pbf_screen(self):
        return 'loans'

    def _pbf_base_domain(self):
        return self._scope()

    def _pbf_search_domain(self, search):
        q = (search or '').strip()
        if not q:
            return None
        parts = [Domain('reason', 'ilike', q), Domain('name', 'ilike', q)]
        try:
            emp_ids = self.env['hr.employee'].sudo().with_context(active_test=False).search(
                ['|', ('name', 'ilike', q), ('barcode', 'ilike', q)]).ids
        except Exception:   # noqa: BLE001
            emp_ids = []
        if emp_ids:
            parts.append(Domain('employee_id', 'in', emp_ids))
        return Domain.OR(parts)

    def _pbf_sorts(self):
        return [
            {'key': 'recent', 'label': _('Raised most recently'), 'order': 'id desc'},
            {'key': 'balance', 'label': _('Most left to repay'), 'order': 'balance desc, id desc'},
            {'key': 'amount', 'label': _('Largest amount first'), 'order': 'amount desc, id desc'},
            {'key': 'first', 'label': _('First pay month, newest first'),
             'order': 'first_month desc, id desc'},
        ]

    def _pbf_spec(self):
        return [
            {'key': 'where', 'label': _('Where it is'), 'icon': 'route',
             'group': 'pay', 'type': 'choice', 'pinned': True, 'requires': ['state'],
             'help': _('The steps above the table, plus loans that were cancelled or not approved.'),
             'options': [
                 {'value': 'draft', 'label': _('Being prepared'), 'tone': 'slate',
                  'domain': WHERE_DOMAINS['draft']},
                 {'value': 'waiting', 'label': _('Waiting for approval'), 'tone': 'amber',
                  'domain': WHERE_DOMAINS['waiting']},
                 {'value': 'running', 'label': _('Running'), 'tone': 'blue',
                  'domain': WHERE_DOMAINS['running']},
                 {'value': 'paused', 'label': _('Paused'), 'tone': 'amber',
                  'domain': WHERE_DOMAINS['paused']},
                 {'value': 'closed', 'label': _('Closed'), 'tone': 'green',
                  'domain': WHERE_DOMAINS['closed']},
                 {'value': 'ended', 'label': _('Cancelled or not approved'), 'tone': 'rose',
                  'domain': WHERE_DOMAINS['ended']},
             ]},
            {'key': 'kind', 'label': _('Kind'), 'icon': 'wallet', 'group': 'pay',
             'type': 'selection', 'path': 'kind', 'pinned': True},
            {'key': 'first', 'label': _('First pay month'), 'icon': 'calendar',
             'group': 'dates', 'type': 'date', 'path': 'first_month', 'presets': 'past',
             'pinned': True},
            {'key': 'person', 'label': _('Who it is for'), 'icon': 'user',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id', 'label_sudo': True},
            {'key': 'department', 'label': _('Department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'department_id',
             'none_label': _('No department'), 'label_sudo': True},
            {'key': 'amount', 'label': _('Amount'), 'icon': 'banknote', 'group': 'pay',
             'type': 'number', 'path': 'amount', 'unit': 'money'},
            {'key': 'balance', 'label': _('Left to repay'), 'icon': 'coins', 'group': 'pay',
             'type': 'number', 'path': 'balance', 'unit': 'money'},
            {'key': 'leaving', 'label': _('If the person leaves'), 'icon': 'logOut',
             'group': 'other', 'type': 'selection', 'path': 'on_leaving'},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All loans'), 'icon': 'wallet', 'filters': {}},
            {'key': 'waiting', 'label': _('Waiting for approval'),
             'filters': {'where': ['waiting']}},
            {'key': 'running', 'label': _('Running'), 'filters': {'where': ['running']}},
            {'key': 'paused', 'label': _('Paused'), 'filters': {'where': ['paused']}},
        ]

    @api.model
    def pbf_layout(self):
        if not self._can_read():
            return {'refused': self._refusal()}
        return super().pbf_layout()

    @api.model
    def _pbf_step_counts(self, filters, search):
        spec = self._pbf_clean_spec()
        s = next((x for x in spec if x['key'] == 'where'), None)
        if not s:
            return {}
        res = self._pbf_count_section(s, filters or {}, search, spec)
        return {r['v']: r['n'] for r in res.get('values') or []}

    @api.model
    def get_loans_page(self, filters=None, search=None, sort=None, offset=0, limit=PAGE_SIZE):
        if not self._can_read():
            return {'rows': [], 'total': 0, 'offset': 0, 'steps': {}}
        Loan = self.env['pb.loan']
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        order = self.pbf_order(sort) or 'id desc'
        rows = []
        for loan in Loan.search(domain, order=order, offset=offset, limit=limit):
            try:
                rows.append(self._row(loan))
            except Exception as e:      # noqa: BLE001 — one bad row never blanks it
                _logger.debug('loans row %s failed: %s', loan.id, e)
        out = {'rows': rows, 'total': Loan.search_count(domain), 'offset': offset}
        if not offset:
            out['steps'] = self._safe(lambda: self._pbf_step_counts(filters, search),
                                      default={})
        return out

    @api.model
    def _row(self, loan):
        emp = loan.employee_id.sudo()
        amount = loan.amount or 0.0
        pct = 0
        if amount > 0:
            pct = int(max(0.0, min(100.0, (loan.repaid or 0.0) / amount * 100.0)))
        next_label = ''
        if loan.state in OPEN_STATES and loan.next_amount:
            next_label = _("%(amount)s in %(month)s", amount=loan._money(loan.next_amount),
                           month=loan._month_label(loan.next_month))
        return {
            'id': loan.id, 'name': loan.name or '',
            'employee': emp.name or '', 'employee_id': emp.id,
            'initials': _initials(emp.name or ''),
            'department': emp.department_id.name or '',
            'kind': loan.kind, 'kind_label': loan._kind_label(),
            'amount_label': loan._money(amount),
            'repaid_label': loan._money(loan.repaid),
            'balance_label': loan._money(loan.balance),
            'pct': pct,
            'state': loan.state, 'state_label': loan._state_label(),
            'next_label': next_label,
            'months_left': loan.months_left if loan.state in OPEN_STATES else 0,
            'pause_reason': loan.pause_reason or '',
        }

    # ============================================================ drawer
    @api.model
    def get_loan(self, loan_id):
        self._require()
        loan = self.env['pb.loan'].browse(int(loan_id or 0)).exists()
        if not loan:
            raise UserError(_("This loan no longer exists."))
        row = self._row(loan)
        history = []
        for line in loan.repayment_ids.sorted(lambda l: (l.pay_month, l.id), reverse=True):
            history.append({
                'id': line.id,
                'month': loan._month_label(line.pay_month),
                'amount': loan._money(line.amount),
                'kind': line.kind,
                'state': line.state,
                'state_label': dict(line._fields['state']._description_selection(
                    self.env)).get(line.state, ''),
                'how': (_("Pay run %s", line._run_label()) if line.kind == 'payroll'
                        else _("Paid outside payroll")),
                'why': line.reason or line.note or '',
                'reference': line.reference or '',
            })
        schedule = []
        if loan.state in OPEN_STATES or loan.state in ('draft', 'waiting'):
            remaining = loan.amount if loan.state in ('draft', 'waiting') else loan._available()
            for month, amount in loan._schedule(remaining=remaining)[:12]:
                schedule.append({'month': loan._month_label(month),
                                 'amount': loan._money(amount)})
        trail = []
        for msg in loan.sudo().message_ids.filtered(
                lambda m: m.message_type in ('comment', 'notification') and m.body)[:12]:
            trail.append({'when': format_datetime(self.env, msg.date, dt_format='d MMM y, HH:mm'),
                          'who': msg.author_id.name or '',
                          'body': html2plaintext(msg.body or '').strip()})
        managed = loan._engine_managed() if loan.state == 'waiting' else False
        my_turn = False
        if loan.state == 'waiting':
            my_turn = bool(loan._chain_my_seat()) if managed else \
                bool(self.env.user.has_group(GROUP_MANAGER) or self.env.user._is_admin())
        waiting_on = ''
        if loan.state == 'waiting' and managed:
            step = loan._chain_active_step()
            names = sorted({s.acting_user_id.name or '' for s in step.sudo().seat_ids
                            if s.status == 'open'}) if step else []
            waiting_on = ', '.join(n for n in names if n)
        row.update({
            'reason': loan.reason or '',
            'first_month': loan._month_label(loan.first_month),
            'plan': loan._plan_sentence(),
            'leaving_label': dict(loan._fields['on_leaving']._description_selection(
                self.env)).get(loan.on_leaving, ''),
            'in_payrun_label': loan._money(loan.in_payrun) if loan.in_payrun else '',
            'available_label': loan._money(loan._available()),
            'history': history,
            'schedule': schedule,
            'trail': trail,
            'my_turn': my_turn,
            'waiting_on': waiting_on,
            'closed_on': loan._month_label(loan.closed_on) if loan.closed_on else '',
            'currency': loan.currency_id.name or '',
            'can': {
                'submit': loan.state == 'draft',
                'delete': loan.state == 'draft' and not loan.repayment_ids,
                'approve': my_turn,
                'pause': loan.state == 'running',
                'resume': loan.state == 'paused',
                'record': loan.state in OPEN_STATES,
                'settle': loan.state in OPEN_STATES and loan._available() > 0,
                'cancel': loan.state in ('draft', 'waiting', 'running', 'paused'),
            },
        })
        return row

    # ============================================================ new loan
    @api.model
    def employee_options(self, term=''):
        self._require()
        term = (term or '').strip()
        if len(term) < 2:
            return []
        people = self.env['hr.employee'].sudo().search([
            ('company_id', 'in', self.env.companies.ids),
            '|', ('name', 'ilike', term), ('barcode', 'ilike', term)], limit=8)
        out = []
        for emp in people:
            currency = self._pay_currency(emp)
            out.append({'id': emp.id, 'name': emp.name or '', 'code': emp.barcode or '',
                        'department': emp.department_id.name or '',
                        'currency_id': currency.id, 'currency': currency.name or '',
                        'leaving': bool(getattr(emp, 'departure_date', False))})
        return out

    @api.model
    def _pay_currency(self, employee):
        """The person's pay currency: their scheme's, else their company's."""
        employee = employee.sudo()
        Map = self.env.get('pb.scheme.map')
        if Map is not None:
            try:
                answer = Map.sudo().resolve(employee, 'any') or {}
                config = self.env['hr.formula.config'].sudo().browse(
                    answer.get('config_id') or 0).exists()
                if config and config.currency_id:
                    return config.currency_id
            except Exception:   # noqa: BLE001
                pass
        return employee.company_id.currency_id or self.env.company.currency_id

    @api.model
    def plan_preview(self, vals):
        """The hero: the instalments, month by month, as the person types."""
        self._require()
        vals = vals or {}
        Loan = self.env['pb.loan']
        currency = self.env['res.currency'].browse(int(vals.get('currency_id') or 0)).exists() \
            or self.env.company.currency_id
        try:
            amount = float(vals.get('amount') or 0)
            plan_amount = float(vals.get('plan_amount') or 0)
            months = int(float(vals.get('plan_months') or 0))
        except (TypeError, ValueError):
            return {'ok': False, 'sentence': _("Type the amounts as numbers.")}
        mode = vals.get('plan_mode') if vals.get('plan_mode') in ('amount', 'months') else 'amount'
        each, n, last = Loan._plan_numbers(amount, mode, plan_amount, months, currency)
        if not n:
            return {'ok': False, 'sentence': _(
                "Type the amount, then how much comes off each month or over how many months.")}
        start = month_of(vals.get('first_month')) or month_of(fields.Date.context_today(self))
        rows = []
        for i in range(n):
            month = start + relativedelta(months=i)
            take = last if i == n - 1 else each
            rows.append({'month': Loan._month_label(month), 'amount': Loan._money(take, currency),
                         'last': i == n - 1})
        finish = start + relativedelta(months=n - 1)
        if n == 1:
            sentence = _("All of it comes off the %(month)s pay run.",
                         month=Loan._month_label(start))
        elif last == each:
            sentence = _("%(n)s instalments of %(each)s, from %(start)s to %(end)s.",
                         n=n, each=Loan._money(each, currency),
                         start=Loan._month_label(start), end=Loan._month_label(finish))
        else:
            sentence = _("%(n)s instalments of %(each)s from %(start)s to %(end)s; the "
                         "last one is %(last)s.", n=n, each=Loan._money(each, currency),
                         start=Loan._month_label(start), end=Loan._month_label(finish),
                         last=Loan._money(last, currency))
        return {'ok': True, 'each': each, 'months': n, 'last': last,
                'each_label': Loan._money(each, currency),
                'sentence': sentence, 'rows': rows[:24], 'more': max(0, n - 24)}

    @api.model
    def create_loan(self, vals, send=False):
        self._require()
        vals = vals or {}
        emp = self.env['hr.employee'].sudo().browse(int(vals.get('employee_id') or 0)).exists()
        if not emp or emp.company_id.id not in self.env.companies.ids:
            raise UserError(_("Pick who the loan is for."))
        try:
            amount = float(vals.get('amount') or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if amount <= 0:
            raise UserError(_("A loan needs an amount above zero."))
        if not (vals.get('reason') or '').strip():
            raise UserError(_("Say what the loan is for, in a few words."))
        if not vals.get('first_month'):
            raise UserError(_("Pick the first pay month."))
        currency = self.env['res.currency'].browse(int(vals.get('currency_id') or 0)).exists() \
            or self._pay_currency(emp)
        loan = self.env['pb.loan'].create({
            'employee_id': emp.id,
            'company_id': emp.company_id.id,
            'kind': vals.get('kind') if vals.get('kind') in ('loan', 'advance') else 'loan',
            'amount': amount,
            'currency_id': currency.id,
            'reason': vals['reason'].strip(),
            'first_month': vals['first_month'],
            'plan_mode': vals.get('plan_mode') if vals.get('plan_mode') in ('amount', 'months')
            else 'amount',
            'plan_amount': float(vals.get('plan_amount') or 0),
            'plan_months': int(float(vals.get('plan_months') or 0)),
            'on_leaving': vals.get('on_leaving') if vals.get('on_leaving') in
            ('take_rest', 'leave_open') else 'take_rest',
        })
        if send:
            loan.action_submit()
        return {'id': loan.id, 'state': loan.state, 'name': loan.name}

    # ============================================================ the moves
    @api.model
    def move(self, loan_id, verb, reason=None, amount=None, reference=None):
        self._require()
        loan = self.env['pb.loan'].browse(int(loan_id or 0)).exists()
        if not loan:
            raise UserError(_("This loan no longer exists."))
        if verb == 'submit':
            loan.action_submit()
            msg = _("Sent for approval.") if loan.state == 'waiting' else _("Approved.")
        elif verb == 'approve':
            loan.action_approve()
            msg = _("Approved.") if loan.state == 'running' else _("Your approval is recorded.")
        elif verb == 'refuse':
            loan.action_refuse(note=reason or False)
            msg = _("Marked as not approved.")
        elif verb == 'pause':
            loan.action_pause(reason)
            msg = _("Paused. No instalment is taken until it is resumed.")
        elif verb == 'resume':
            loan.action_resume(reason)
            msg = _("Resumed.")
        elif verb == 'cancel':
            loan.action_cancel(reason)
            msg = _("Cancelled.")
        elif verb == 'record':
            loan.action_record_repayment(amount, reason, reference)
            msg = _("Repayment recorded.")
        elif verb == 'settle':
            loan.action_settle(reason, reference)
            msg = _("Settled.")
        elif verb == 'delete':
            loan.unlink()
            return {'ok': True, 'msg': _("Deleted."), 'deleted': True}
        else:
            raise UserError(_("That cannot be done here."))
        return {'ok': True, 'msg': msg, 'state': loan.state}

    @api.model
    def set_loan_item(self, config_id, rule_id):
        """Set up: which pay item of a scheme receives loan instalments.

        A payroll manager's choice (it changes what a scheme takes from pay)."""
        self._require()
        if not self._can_set_up():
            raise AccessError(_("Only a payroll manager can choose where loan "
                                "repayments go."))
        config = self.env['hr.formula.config'].sudo().browse(int(config_id or 0)).exists()
        if not config or config.company_id.id not in self.env.companies.ids:
            raise UserError(_("This pay scheme cannot be found."))
        rule = self.env['hr.formula.rule'].sudo().browse(int(rule_id or 0)).exists()
        if rule and rule.config_id != config:
            raise UserError(_("Pick a pay item of this pay scheme."))
        config.write({'pb_loan_rule_id': rule.id or False})
        return {'ok': True}
