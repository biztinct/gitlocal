# -*- coding: utf-8 -*-
"""The accounting entry for pay, and who agrees to post it.

WHAT THIS BUILD DOES TODAY, AND WHY IT IS NOT CHANGED BY DEFAULT. Confirming a
payslip has never posted a journal entry here: the salary-rule → account
mapping is not maintained for the formula workflow (BASIC, GROSS and NET point
at the same accounts, so posting per payslip multi-counts), and the legacy
auto-posting sits behind an explicit context flag. A phase that started posting
journal entries by itself would be a phase that changed what a company's books
say — so the whole lane is behind ONE company switch, off until somebody turns
it on.

WITH THE SWITCH ON. When a pay run is finished, one balanced DRAFT entry is
built for the whole run — lines grouped by account, an adjustment line if the
mapping does not balance — and a `pb.payroll.journal` record carries it through
the route the business published for "Payroll journal and funding". The apply
POSTS the entry. Under the fast lane the whole thing happens in one press, at
the moment the run finishes, and is recorded.

ONE ENTRY PER RUN, not one per payslip. A payroll journal is a statement about
a period, an entry per person is an invoice ledger, and the per-payslip path
is what multi-counted.

WITHOUT ACCOUNTING. `om_hr_payroll_account` is optional and cannot even be
installed on a fresh database (ledger AM17), so every path here checks the
registry first and does nothing at all when it is absent. No record, no error.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: The catalogue key this model is approved under.
JOURNAL_PROCESS_KEY = 'journal'

STATES = [
    ('draft', 'Being prepared'),
    ('pending', 'Waiting for approval'),
    ('posted', 'Posted'),
    ('returned', 'Sent back'),
    ('rejected', 'Turned down'),
]


def accounting_installed(env):
    """Is the payroll → accounts bridge really on this database?"""
    return 'om_hr_payroll_account' in (env.registry._init_modules or set()) \
        or bool(env['ir.module.module'].sudo().search_count([
            ('name', '=', 'om_hr_payroll_account'),
            ('state', '=', 'installed')]))


class PbPayrollJournal(models.Model):
    _name = 'pb.payroll.journal'
    _inherit = ['biz.approval.adapter.mixin', 'pb.money.approval.mixin']
    _description = 'Payroll Journal Entry'
    _order = 'id desc'

    _approval_process_key = JOURNAL_PROCESS_KEY

    name = fields.Char(compute='_compute_name', store=True)
    run_id = fields.Many2one('hr.payslip.run', string='Pay run', required=True,
                             index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda s: s.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency')
    move_id = fields.Many2one('account.move', string='Accounting entry',
                              readonly=True, ondelete='set null', copy=False)
    amount_debit = fields.Monetary(readonly=True, currency_field='currency_id')
    amount_credit = fields.Monetary(readonly=True, currency_field='currency_id')
    funding_amount = fields.Monetary(
        string='Money to put aside', readonly=True,
        currency_field='currency_id',
        help="What has to be in the account for this run to be paid — the net "
             "pay of every confirmed payslip.")
    posted_on = fields.Datetime(readonly=True, copy=False)
    posted_by = fields.Many2one('res.users', readonly=True, copy=False)

    state = fields.Selection(STATES, default='draft', required=True,
                             index=True, readonly=True, copy=False)

    seat_user_ids = fields.Many2many(
        'res.users', 'pb_payroll_journal_seat_rel', 'journal_id', 'user_id',
        string='Asked to decide', copy=False)

    @api.depends('run_id')
    def _compute_name(self):
        for rec in self:
            rec.name = _("Payroll journal · %s", rec.run_id.name or '')

    # ==================================================================
    # Building one
    # ==================================================================
    @api.model
    def _lines_for_run(self, run):
        """(line vals, debit, credit) — the run's pay, grouped by account."""
        Rule = self.env['hr.salary.rule']
        if 'account_debit' not in Rule._fields:
            return [], 0.0, 0.0
        slips = run.sudo().slip_ids.filtered(lambda s: s.state == 'done')
        by_account = {}
        for line in slips.mapped('line_ids'):
            rule = line.salary_rule_id
            amount = float(line.total or 0.0)
            if not amount:
                continue
            for account, side in ((rule.account_debit, 'debit'),
                                  (rule.account_credit, 'credit')):
                if not account:
                    continue
                key = (account.id, side)
                by_account[key] = by_account.get(key, 0.0) + amount
        currency = (run.sudo().company_id or self.env.company).currency_id \
            if 'company_id' in run._fields else self.env.company.currency_id
        values, debit, credit = [], 0.0, 0.0
        for (account_id, side), amount in sorted(by_account.items()):
            amount = currency.round(amount)
            if not amount:
                continue
            values.append((0, 0, {
                'account_id': account_id,
                'name': run.name or _('Payroll'),
                'debit': amount if side == 'debit' else 0.0,
                'credit': amount if side == 'credit' else 0.0,
            }))
            if side == 'debit':
                debit += amount
            else:
                credit += amount
        return values, debit, credit

    @api.model
    def prepare(self, run):
        """One draft entry for a finished run, or nothing at all.

        Returns an empty recordset — never an error — when accounting is not
        installed, when no salary rule carries an account, or when one already
        exists for this run.
        """
        run = run if isinstance(run, models.BaseModel) \
            else self.env['hr.payslip.run'].browse(int(run))
        if not run.exists() or not accounting_installed(self.env):
            return self.browse()
        existing = self.sudo().search([
            ('run_id', '=', run.id),
            ('state', 'in', ('pending', 'posted'))], limit=1)
        if existing:
            return existing
        values, debit, credit = self._lines_for_run(run)
        if not values:
            _logger.info('pb_pay_delivery: run %s has no accounts on its pay '
                         'components, so there is no journal entry to make',
                         run.id)
            return self.browse()
        company = getattr(run, 'company_id', False) or self.env.company
        currency = company.currency_id
        journal = getattr(run, 'journal_id', False) or \
            self.env['account.journal'].sudo().search(
                [('type', '=', 'general'), ('company_id', '=', company.id)],
                limit=1)
        if not journal:
            _logger.info('pb_pay_delivery: no general journal for %s',
                         company.name)
            return self.browse()
        difference = currency.round(debit - credit)
        if difference:
            # Never post something that does not balance. The odd amount goes
            # on the last account used, and the fact that it was needed is on
            # the record for the approver to see.
            balancing = dict(values[-1][2])
            if difference > 0:
                balancing['credit'] = balancing.get('credit', 0.0) + difference
                balancing['debit'] = 0.0
            else:
                balancing['debit'] = balancing.get('debit', 0.0) - difference
                balancing['credit'] = 0.0
            balancing['name'] = _('Rounding')
            values.append((0, 0, balancing))
            credit += difference if difference > 0 else 0.0
            debit += -difference if difference < 0 else 0.0
        move = self.env['account.move'].sudo().with_context(
            check_move_validity=False).create({
                'journal_id': journal.id,
                'date': run.date_end or fields.Date.context_today(self),
                'ref': run.name or _('Payroll'),
                'move_type': 'entry',
                'company_id': company.id,
                'line_ids': values,
            })
        Wizard = self.env['vietnam.bank.export.wizard']
        funding = sum(Wizard._slip_net(slip)
                      for slip in run.sudo().slip_ids.filtered(
                          lambda s: s.state == 'done'))
        return self.create({
            'run_id': run.id,
            'company_id': company.id,
            'currency_id': currency.id,
            'move_id': move.id,
            'amount_debit': debit,
            'amount_credit': credit,
            'funding_amount': funding,
        })

    # ==================================================================
    # Adapter
    # ==================================================================
    def _approval_validate(self):
        self.ensure_one()
        if self.state in ('pending', 'posted'):
            raise UserError(_("This journal entry has already been sent in."))
        if not self.move_id:
            raise UserError(_("There is no accounting entry to post."))
        return True

    def _balanced(self):
        self.ensure_one()
        currency = self.currency_id or self.company_id.currency_id
        return not currency.round(
            float(self.amount_debit or 0.0) - float(self.amount_credit or 0.0))

    def _approval_context(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        currency = self.currency_id or company.currency_id
        run = self.run_id
        scope_keys, scope_label = self.scope_of_run(run)
        facts = {
            'amount': {'value': float(self.amount_debit or 0.0),
                       'unit': currency.name or ''},
            'balanced': {'value': self._balanced(), 'unit': ''},
            'run_approved': {'value': self.run_is_approved(run), 'unit': ''},
        }
        return {
            'company_id': company.id,
            'title': self.name or _('Payroll journal'),
            'scope_keys': scope_keys,
            'scope_label': scope_label,
            'kind_key': 'any',
            'facts': facts,
            'amount': float(self.amount_debit or 0.0),
            'currency_id': currency.id,
            'maker_uids': self.run_makers(run),
            'submitter_uid': self.env.uid,
            'subject_uids': [],
            'source_revision': self._approval_revision_of([
                self.move_id.id, round(float(self.amount_debit or 0.0), 2),
                round(float(self.amount_credit or 0.0), 2)]),
            'evidence': [
                {'key': 'balanced', 'name': _('The entry balances'),
                 'ok': self._balanced(), 'note': ''},
                {'key': 'run_approved', 'name': _('The pay run is approved'),
                 'ok': self.run_is_approved(run), 'note': run.name or ''},
            ],
        }

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'amount': {'type': 'decimal', 'label': _('Amount'),
                           'unit': 'currency'},
                'balanced': {'type': 'bool', 'label': _('The entry balances')},
                'run_approved': {'type': 'bool',
                                 'label': _('The pay run is approved')},
            },
            'kinds': [],
            'evidence': [
                {'key': 'balanced', 'label': _('The entry balances')},
                {'key': 'run_approved',
                 'label': _('The pay run is approved')},
            ],
            'scope_levels': [_('Pay scheme'), _('Division')],
            'manager_mode': False,
        }

    @api.model
    def _approval_scope_options(self, company):
        return self.env['pb.bank.file']._approval_scope_options(company)

    @api.model
    def _approval_coverage_scopes(self, company):
        return self.env['pb.bank.file']._approval_coverage_scopes(company)

    def _approval_card_count(self, request):
        self.ensure_one()
        lines = len(self.move_id.sudo().line_ids) if self.move_id else 0
        if lines == 1:
            return _("1 accounting line")
        return _("%s accounting lines", lines)

    def _approval_detail(self, request):
        self.ensure_one()
        if not self.move_id:
            return None
        rows = []
        for line in self.move_id.sudo().line_ids[:40]:
            rows.append({
                'head': line.account_id.display_name or '',
                'sub': line.name or '',
                'cells': ['{:,.0f}'.format(line.debit or 0.0),
                          '{:,.0f}'.format(line.credit or 0.0)],
                'tone': 'on' if line.debit else 'off',
            })
        return {
            'title': _('The accounting entry'),
            'columns': [_('Debit'), _('Credit')],
            'rows': rows,
            'chips': [{'label': _('Money to put aside'),
                       'value': '{:,.0f}'.format(
                           float(self.funding_amount or 0.0))}],
            'note': '' if self._balanced() else _(
                "This entry needed a rounding line to balance."),
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
        """Turned down: the draft entry is deleted, not left lying about."""
        self.ensure_one()
        move = self.move_id.sudo()
        self.sudo().write({'state': 'rejected', 'move_id': False})
        if move and move.state == 'draft':
            try:
                move.unlink()
            except Exception:   # noqa: BLE001 — the decision always stands
                _logger.warning('pb_pay_delivery: draft entry %s could not be '
                                'removed', move.id)
        return True

    def _approval_apply(self, request):
        self.ensure_one()
        if self.state == 'posted':
            return True
        self.require_pay(_('the payroll journal'))
        move = self.move_id.sudo()
        if not move.exists():
            raise UserError(_(
                "The accounting entry behind this is gone, so there is "
                "nothing to post."))
        if move.state == 'draft':
            move.action_post()
        self.sudo().write({'state': 'posted',
                           'posted_on': fields.Datetime.now(),
                           'posted_by': self.env.uid})
        self.env['biz.approval.event']._log(
            'applied',
            _("%(who)s posted the payroll journal for %(run)s",
              who=self.env.user.name, run=self.run_id.name or ''),
            company=self.company_id, request=request)
        self.audit(self, 'state', _('Payroll journal'), _('Draft'),
                   _('Posted'))
        return True


class ResCompanyPayrollJournal(models.Model):
    _inherit = 'res.company'

    pb_post_payroll_journal = fields.Boolean(
        string='Post a payroll journal entry when a pay run is finished',
        default=False,
        help="Off by default. Confirming payslips has never written to the "
             "books on this build, and turning this on is a decision about "
             "your accounts, not about payroll. When it is on, each finished "
             "pay run produces one entry that follows the route you set for "
             "the payroll journal.")


class HrPayslipRunJournal(models.Model):
    """A finished run offers its journal entry to whoever signs it off."""
    _inherit = 'hr.payslip.run'

    def _approval_apply(self, request):
        # The pay-run adapter itself lives in `pb_payruns`, which this module
        # does not depend on. Where it is absent nothing calls this at all, and
        # asking for the parent rather than assuming it says so honestly.
        parent = getattr(super(), '_approval_apply', None)
        result = parent(request) if parent else True
        for run in self:
            company = getattr(run, 'company_id', False) or self.env.company
            if not company.pb_post_payroll_journal:
                continue
            try:
                journal = self.env['pb.payroll.journal'].prepare(run)
                if journal and journal.state == 'draft':
                    self.env['biz.approval.engine'].submit(journal)
            except Exception:   # noqa: BLE001 — the pay run is already approved
                _logger.exception(
                    'pb_pay_delivery: the payroll journal for run %s could '
                    'not be prepared', run.id)
        return result
