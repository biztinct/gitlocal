# -*- coding: utf-8 -*-
"""A file of pay data is a thing somebody signs before it becomes money.

WHAT WAS TRUE BEFORE. `action_validate` checked the file and `action_process`
wrote it: employees created, contracts created, payslips computed. Both were
one press each, by one person, gated only on "may this person run payroll".
A spreadsheet is the single largest lever in the product — one column of the
wrong numbers is everybody's pay — and nobody else had to look at it.

WHAT IS TRUE NOW. `action_validate` is unchanged: it is the CHECK, not the
money, and a person must be able to see what a file would do before deciding
whether to ask about it. `action_process` asks. The processing body itself is
untouched and runs from `_approval_apply`, so what happens when the answer is
yes is exactly what happened before.

TWO CATALOGUE ROWS, ONE MODEL. A file whose figures are used for one pay run
and then forgotten is not the same risk as a file that writes what people are
paid from now on, and a business must be able to check one and wave the other
through. `one_time` decides which row a batch travels under —
`_approval_process_key_for` is the engine hook that makes one model answer to
two processes.

THIS MODULE NEVER LEARNS ABOUT THE MATRIX. `pb_hr_payroll_formula` depends on
`biz_approval_workflow` and on nothing above it (ledger AM52): the panels and
the cockpit changes live in `pb_import_batch` and `pb_payrun_wizard`.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: The two catalogue rows this model answers to.
RUNONLY_PROCESS_KEY = 'runonly'
LOADS_PROCESS_KEY = 'loads'

#: The sentinel a sanctioned process carries. A module-level `object()`
#: IDENTITY, so a context value arriving over `call_kw` can never equal it.
PROCESS_KEY = 'pb_import_apply'
PROCESS_TOKEN = object()

#: Column codes that look like take-home pay, for the one fact a route about a
#: file most wants: how much money is in it.
_NET_TOKENS = ('NET', 'NETPAY', 'TAKEHOME', 'THUCLINH', 'THUCNHAN')


def apply_context(record):
    return record.with_context(**{PROCESS_KEY: PROCESS_TOKEN})


class HrPayrollImportBatch(models.Model):
    _name = 'hr.payroll.import.batch'
    _inherit = ['hr.payroll.import.batch', 'biz.approval.adapter.mixin']

    #: The row a batch travels under when it is NOT one-time.
    _approval_process_key = LOADS_PROCESS_KEY
    #: Both rows this model can serve, for the catalogue's static check.
    _approval_process_keys = (RUNONLY_PROCESS_KEY, LOADS_PROCESS_KEY)

    #: A seat is also a read (ledger AM60).
    seat_user_ids = fields.Many2many(
        'res.users', 'hr_payroll_import_batch_seat_rel', 'batch_id', 'user_id',
        string='Asked to decide', copy=False)

    def _approval_process_key_for(self):
        self.ensure_one()
        return RUNONLY_PROCESS_KEY if self.one_time else LOADS_PROCESS_KEY

    # ==================================================================
    # The door
    # ==================================================================
    def action_process(self):
        """Ask first. The processing body runs from the approval.

        Where the business published "No approval needed" the engine applies in
        the same breath, so this press behaves exactly as it always did — and
        writes a request saying so.
        """
        self.ensure_one()
        if self.env.context.get(PROCESS_KEY) is PROCESS_TOKEN:
            return super().action_process()
        request = self.approval_request_id
        if request and request.state == 'applied':
            # Already approved and already carried out. A second press is a
            # person trying to finish something that stalled, not a new ask.
            return apply_context(self).action_process()
        if request and request.state in ('pending', 'blocked'):
            raise UserError(_(
                "This file is already waiting to be approved, with %s.",
                self._waiting_for() or _('its approver')))
        self.env['biz.approval.engine'].submit(self)
        if self.state == 'done':
            return {'type': 'ir.actions.client', 'tag': 'reload'}
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Sent for approval'),
                'message': _("This pay data is now with %s.",
                             self._waiting_for() or _('its approver')),
                'type': 'success', 'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

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
    # Adapter
    # ==================================================================
    def _approval_validate(self):
        self.ensure_one()
        if self.state not in ('validated', 'matched'):
            raise UserError(_("Please validate data first."))
        return True

    def _money_in_file(self):
        """The take-home total this file carries, or 0 when it carries none.

        Read off the pay-data rows rather than off anything computed: the
        question an approver asks about a spreadsheet is how much money is in
        it, and the payslips do not exist yet.
        """
        self.ensure_one()
        import json as _json
        total = 0.0
        for line in self.import_line_ids:
            try:
                raw = _json.loads(line.raw_data_json or '{}') or {}
            except (TypeError, ValueError):
                continue
            for key, value in raw.items():
                code = ''.join(ch for ch in str(key or '').upper()
                               if ch.isalnum())
                if code not in _NET_TOKENS:
                    continue
                try:
                    total += float(value or 0)
                except (TypeError, ValueError):
                    continue
                break
        return total

    def _approval_context(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        config = self.formula_config_id
        currency = company.currency_id
        amount = self._money_in_file()
        facts = {
            'lines': {'value': self.total_lines, 'unit': ''},
            'employees': {'value': self.matched_employees + self.new_employees,
                          'unit': ''},
            'new_employees': {'value': self.new_employees, 'unit': ''},
            'amount_total': {'value': amount, 'unit': currency.name or ''},
            'one_time': {'value': bool(self.one_time), 'unit': ''},
            'creates_payslips': {'value': bool(self.create_payslips),
                                 'unit': ''},
        }
        subjects = set(self.import_line_ids.mapped(
            'employee_id.user_id').ids)
        return {
            'company_id': company.id,
            'title': self.name or _('Pay data'),
            'scope_keys': ['scheme:%s' % config.id, ''] if config else [''],
            'scope_label': config.name or company.name,
            'kind_key': 'one_time' if self.one_time else 'keep',
            'facts': facts,
            'amount': amount,
            'currency_id': currency.id,
            'maker_uids': [self.create_uid.id] if self.create_uid else [],
            'submitter_uid': self.env.uid,
            'subject_uids': sorted(u for u in subjects if u),
            'source_revision': self._source_revision(),
            'evidence': [{
                'key': 'validated', 'name': _('The file passed its checks'),
                'ok': self.state == 'validated' and not self.error_lines,
                'note': (_("%s row(s) have a problem", self.error_lines)
                         if self.error_lines else '')}],
        }

    def _source_revision(self):
        """A stamp of the FIGURES this approval covers.

        Read from the rows themselves, every time, and never from anything the
        submission wrote down — a stamp read back off its own snapshot always
        equals itself and the rail would be decoration (ledger AM46).
        """
        self.ensure_one()
        rows = sorted(
            (line.id, (line.raw_data_json or '')[:4000])
            for line in self.import_line_ids)
        return self._approval_revision_of(rows)

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'lines': {'type': 'int', 'label': _('Rows in the file')},
                'employees': {'type': 'int', 'label': _('People in the file')},
                'new_employees': {'type': 'int',
                                  'label': _('People it would create')},
                'amount_total': {'type': 'decimal',
                                 'label': _('Take-home pay in the file'),
                                 'unit': 'currency'},
                'one_time': {'type': 'bool',
                             'label': _('Used for this pay run only')},
                'creates_payslips': {'type': 'bool',
                                     'label': _('Creates payslips')},
            },
            'kinds': [{'key': 'one_time', 'label': _('This run only')},
                      {'key': 'keep', 'label': _('Kept on the records')}],
            'evidence': [{'key': 'validated',
                          'label': _('The file passed its checks')}],
            'scope_levels': [_('Pay scheme')],
            'manager_mode': False,
        }

    @api.model
    def _approval_coverage_scopes(self, company):
        rows = []
        Config = self.env['hr.formula.config']
        domain = [('company_id', '=', company.id)]
        if 'state' in Config._fields:
            domain.append(('state', '!=', 'archived'))
        for config in Config.sudo().search(domain, limit=200, order='name'):
            rows.append({
                'scope_key': 'scheme:%s' % config.id,
                'scope_keys': ['scheme:%s' % config.id, ''],
                'label': config.name or '', 'headcount': 0,
                'kind_key': 'keep', 'facts': {},
            })
        if not rows:
            rows.append({'scope_key': '', 'scope_keys': [''],
                         'label': company.name, 'headcount': 0,
                         'kind_key': 'keep', 'facts': {}})
        return rows

    @api.model
    def _approval_scope_options(self, company):
        options = []
        Config = self.env['hr.formula.config']
        domain = [('company_id', '=', company.id)]
        if 'state' in Config._fields:
            domain.append(('state', '!=', 'archived'))
        for config in Config.sudo().search(domain, limit=200, order='name'):
            options.append({'key': 'scheme:%s' % config.id,
                            'label': config.name or ''})
        if not options:
            return []
        return [{'level': 'scheme', 'label': _('Pay scheme'),
                 'options': options}]

    def _approval_card_count(self, request):
        self.ensure_one()
        if self.total_lines == 1:
            return _("1 row")
        return _("%s rows", self.total_lines)

    def _approval_detail(self, request):
        """Who is in this file, and whether the app already knows them."""
        self.ensure_one()
        rows = []
        for line in self.import_line_ids[:40]:
            rows.append({
                'head': (line.employee_id.name or line.employee_name or '')[:40],
                'sub': line.employee_code or '',
                'cells': [_('New person') if line.is_new_employee
                          else _('Already on file')],
                'tone': 'warn' if line.is_new_employee else 'on',
            })
        if not rows:
            return None
        chips = [{'label': _('Rows'), 'value': str(self.total_lines)}]
        if self.new_employees:
            chips.append({'label': _('People it would create'),
                          'value': str(self.new_employees)})
        if self.error_lines:
            chips.append({'label': _('Rows with a problem'),
                          'value': str(self.error_lines)})
        return {
            'title': _('What is in the file'),
            'columns': [_('Status')],
            'rows': rows,
            'chips': chips,
            'note': (_("Showing the first %(shown)s of %(total)s rows.",
                       shown=len(rows), total=self.total_lines)
                     if self.total_lines > len(rows) else ''),
        }

    # ------------------------------------------------------- the transitions
    def _approval_apply(self, request):
        """Process the file — exactly the body that has always processed it."""
        self.ensure_one()
        if self.state == 'done':
            return True
        apply_context(self).action_process()
        return True


class BizApprovalRequestSeatImport(models.Model):
    """A seat on a pay-data file is also a permission to READ it (AM60)."""
    _inherit = 'biz.approval.request.seat'

    @api.model_create_multi
    def create(self, vals_list):
        seats = super().create(vals_list)
        for seat in seats:
            request = seat.step_id.request_id
            if request.res_model != 'hr.payroll.import.batch' \
                    or not request.res_id:
                continue
            batch = self.env['hr.payroll.import.batch'].sudo().browse(
                request.res_id).exists()
            people = {seat.acting_user_id.id, seat.user_id.id}
            people.discard(False)
            if batch and people:
                batch.write({
                    'seat_user_ids': [(4, uid) for uid in sorted(people)]})
        return seats


# ======================================================================
# The two default routes
# ======================================================================
def _loads_definition():
    """Past pay data is checked by the payroll manager, then the HR lead."""
    return {
        'schema_version': 1,
        'steps': [
            {'key': 's1', 'kind': 'review', 'title': 'Payroll check',
             'who': {'mode': 'role', 'role': 'payroll_mgr',
                     'scope': 'company'},
             'min_amount': 0, 'condition': None},
            {'key': 's2', 'kind': 'approve', 'title': 'HR lead',
             'who': {'mode': 'role', 'role': 'hr_lead', 'scope': 'area'},
             'min_amount': 0, 'condition': None},
        ],
        'tiers': {'enabled': False, 'fact': None},
        'safeguards': _safeguards(),
    }


def _runonly_definition():
    """A figure for one pay run only is checked by the payroll manager.

    One step and not two, because the pay run it feeds has a route of its own
    and every number in this file is on it. Two routes over the same money is
    how an approval queue stops being read.
    """
    return {
        'schema_version': 1,
        'steps': [
            {'key': 's1', 'kind': 'approve', 'title': 'Payroll manager',
             'who': {'mode': 'role', 'role': 'payroll_mgr',
                     'scope': 'company'},
             'min_amount': 0, 'condition': None},
        ],
        'tiers': {'enabled': False, 'fact': None},
        'safeguards': _safeguards(),
    }


def _safeguards():
    return {
        'independent': True,
        'self_exception': {'enabled': False},
        'repeated': 'different',
        'evidence': [],
        'due': {'kind': 'working_days', 'days': 1, 'day': 15,
                'calendar_id': None},
        'late': {'remind_days': 1, 'escalate_days': 2, 'reassign': False},
    }


IMPORT_ROUTES = (
    (LOADS_PROCESS_KEY, 'Past pay data loads', _loads_definition,
     ('payroll_mgr', 'hr_lead'),
     'The route every pay-data file follows unless a pay scheme is given its '
     'own.'),
    (RUNONLY_PROCESS_KEY, '"This run only" pay data', _runonly_definition,
     ('payroll_mgr',),
     'The route a figure entered for one pay run follows unless a pay scheme '
     'is given its own.'),
)


class HrPayrollImportBatchSeed(models.Model):
    _inherit = 'hr.payroll.import.batch'

    @api.model
    def _approval_seed_default(self, company):
        laid = False
        for key, name, definition_fn, roles, note in IMPORT_ROUTES:
            laid = self.env['biz.approval.seed'].lay(
                company, key, name, definition_fn(), binding_note=note,
                model_name='hr.payroll.import.batch', role_keys=roles,
                reason='Set up when pay-data approvals were switched on'
            ) or laid
        return laid


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['hr.payroll.import.batch']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an install must not die here
            _logger.exception('pb_hr_payroll_formula: %s has no pay-data '
                              'route yet', company.name)
    return done


class ResCompanyImportSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['hr.payroll.import.batch']._approval_seed_default(
                    company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('pb_hr_payroll_formula: %s has no pay-data '
                                  'route yet', company.name)
        return companies
