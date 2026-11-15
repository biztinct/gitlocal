# -*- coding: utf-8 -*-
"""Cost centres as a proper list, kept in step with the contract's text.

THE ONE WRITTEN VALUE stays `hr.contract.costcenter` (free text). Everything
already reads it: the contract drawer, the employee panel, renewals
(`CARRIED_FIELDS`), the connected system, Updates and the application-data
formulas. This module does not add a second place to write.

* `pb.cost.centre` (code, name, company) is the list.
* `hr.contract.pb_cost_centre_id` is a STORED COMPUTE of the text: the list
  entry of the contract's company whose code (or, failing that, name) is the
  text, ignoring case and spaces. Typing the text anywhere keeps the two in
  step; nothing is ever written back from the list onto a contract.
* `pb.cost.centre.move` moves a person (or everybody in a team) to a cost
  centre FROM A DATE — today or later, never earlier. A move dated today is
  made at once; a later one waits and is made by a quiet daily job.

NEVER REWRITE HISTORY. `hr.payslip.line.costcenter` is a stored copy of the
contract's text (`related='slip_id.contract_id.costcenter', store=True`,
om_hr_payroll), so a write of the text used to rewrite the cost centre on
every past payslip of that contract. `hr.contract.write` below PROTECTS the
lines of every payslip that is no longer a draft, or whose period ended
before the change starts: they keep the cost centre they were paid under.
This holds for every writer of the text (drawer, Updates, connected system),
not only for moves made here. Draft payslips follow the contract, as before.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .org_common import DRAFT_SLIP_STATES

_logger = logging.getLogger(__name__)

#: Context key: the date a cost-centre write takes effect (a move's date).
CHANGE_DATE = 'pb_cost_centre_change_date'

MOVE_STATES = [
    ('scheduled', 'Waiting for its date'),
    ('done', 'Done'),
    ('cancelled', 'Cancelled'),
]


def _norm(text):
    return ' '.join((text or '').split()).casefold()


class PbCostCentre(models.Model):
    _name = 'pb.cost.centre'
    _description = 'Cost centre'
    _order = 'code, id'
    _rec_names_search = ['code', 'name']

    code = fields.Char(string='Code', required=True,
                       help='Exactly what contracts carry as their cost centre.')
    name = fields.Char(string='Name', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    note = fields.Text(string='Notes')
    active = fields.Boolean(default=True)
    contract_ids = fields.One2many(
        'hr.contract', 'pb_cost_centre_id', string='Contracts')

    _code_company_unique = models.Constraint(
        'UNIQUE(company_id, code)',
        'A cost centre code is used once per company.')

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for cc in self:
            if cc.code and cc.name and _norm(cc.code) != _norm(cc.name):
                cc.display_name = '%s · %s' % (cc.code, cc.name)
            else:
                cc.display_name = cc.code or cc.name or ''

    @api.constrains('code', 'name', 'company_id')
    def _check_clash(self):
        for cc in self:
            if not (cc.code or '').strip():
                raise ValidationError(_("A cost centre needs a code."))
            others = self.with_context(active_test=False).search(
                [('company_id', '=', cc.company_id.id), ('id', '!=', cc.id)])
            if any(_norm(o.code) == _norm(cc.code) for o in others):
                raise ValidationError(_(
                    "This company already has the cost centre \"%s\".",
                    cc.code))

    def _contracts_using(self):
        return self.env['hr.contract'].sudo().with_context(
            active_test=False).search([('pb_cost_centre_id', 'in', self.ids)])

    def write(self, vals):
        if 'code' in vals:
            for cc in self:
                if _norm(vals['code']) != _norm(cc.code):
                    n = len(cc._contracts_using())
                    if n:
                        raise UserError(_(
                            "Contracts carrying the code \"%(code)s\": %(n)s. It "
                            "cannot be changed here — that would rewrite what "
                            "they say. Add a new cost centre and move people "
                            "to it from a date instead.", n=n, code=cc.code))
        companies = self.company_id
        res = super().write(vals)
        if {'code', 'name', 'company_id', 'active'} & set(vals):
            (companies | self.company_id)._pb_relink_cost_centres()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.company_id._pb_relink_cost_centres()
        return records

    def unlink(self):
        used = self.filtered(lambda cc: cc._contracts_using())
        if used:
            raise UserError(_(
                "\"%s\" is on contracts. Archive it instead, or move the people "
                "to another cost centre first.", used[0].display_name))
        companies = self.company_id
        res = super().unlink()
        companies._pb_relink_cost_centres()
        return res

    @api.model
    def _match(self, text, company):
        """The list entry the text names in that company, or nothing."""
        key = _norm(text)
        if not key or not company:
            return self.browse()
        rows = self.sudo().search([('company_id', '=', company.id)])
        hit = rows.filtered(lambda cc: _norm(cc.code) == key)[:1]
        return hit or rows.filtered(lambda cc: _norm(cc.name) == key)[:1]


class ResCompanyCostCentre(models.Model):
    _inherit = 'res.company'

    def _pb_relink_cost_centres(self):
        """Re-read which list entry each contract's text names (a stored
        compute of the TEXT, so this never writes the text itself)."""
        if not self:
            return
        Contract = self.env['hr.contract'].sudo().with_context(
            active_test=False)
        contracts = Contract.search([('company_id', 'in', self.ids),
                                     ('costcenter', '!=', False)])
        contracts |= Contract.search([('company_id', 'in', self.ids),
                                      ('pb_cost_centre_id', '!=', False)])
        if contracts:
            self.env.add_to_compute(Contract._fields['pb_cost_centre_id'],
                                    contracts)
            contracts._recompute_recordset(['pb_cost_centre_id'])


class HrContractCostCentre(models.Model):
    _inherit = 'hr.contract'

    pb_cost_centre_id = fields.Many2one(
        'pb.cost.centre', string='Cost centre (from the list)',
        compute='_compute_pb_cost_centre_id', store=True, index=True,
        help='The cost centre in the list that this contract\'s cost centre '
             'names. Empty when the text matches nothing in the list.')

    @api.depends('costcenter', 'company_id')
    def _compute_pb_cost_centre_id(self):
        CC = self.env['pb.cost.centre'].sudo()
        by_company = {}
        for contract in self:
            if not (contract.costcenter or '').strip() or not contract.company_id:
                contract.pb_cost_centre_id = False
                continue
            rows = by_company.get(contract.company_id.id)
            if rows is None:
                rows = by_company[contract.company_id.id] = CC.search(
                    [('company_id', '=', contract.company_id.id)])
            key = _norm(contract.costcenter)
            hit = rows.filtered(lambda cc: _norm(cc.code) == key)[:1] \
                or rows.filtered(lambda cc: _norm(cc.name) == key)[:1]
            contract.pb_cost_centre_id = hit.id or False

    # ------------------------------------------------ never rewrite history
    def _pb_history_lines(self, change_date):
        """Payslip lines of these contracts that are history for a cost-centre
        change starting on `change_date`."""
        if not self.ids:
            return self.env['hr.payslip.line']
        Line = self.env['hr.payslip.line'].sudo().with_context(
            active_test=False)
        return Line.search([
            ('slip_id.contract_id', 'in', self.ids),
            '|', ('slip_id.state', 'not in', list(DRAFT_SLIP_STATES)),
            ('slip_id.date_to', '<', change_date),
        ])

    def write(self, vals):
        if 'costcenter' not in vals or not self.ids:
            return super().write(vals)
        change_date = self.env.context.get(CHANGE_DATE) \
            or fields.Date.context_today(self)
        lines = self._pb_history_lines(change_date)
        if not lines:
            return super().write(vals)
        field = self.env['hr.payslip.line']._fields['costcenter']
        with self.env.protecting([field], lines):
            return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        contracts = super().create(vals_list)
        for contract in contracts:
            if (contract.costcenter or '').strip():
                continue
            # A contract created with its company named gets no department
            # from the shared compute (the method's fields are protected
            # together), so the person's own team is the fallback.
            team = contract.sudo().department_id \
                or contract.sudo().employee_id.department_id
            default = team.pb_cost_centre_id
            if default and default.active \
                    and default.company_id == contract.company_id:
                # A new contract has no payslip yet: nothing to protect.
                contract.sudo().write({'costcenter': default.code})
        return contracts


class PbCostCentreMove(models.Model):
    _name = 'pb.cost.centre.move'
    _description = 'Cost centre change from a date'
    _order = 'date_start desc, id desc'

    contract_id = fields.Many2one(
        'hr.contract', string='Contract', required=True, index=True,
        ondelete='cascade')
    employee_id = fields.Many2one(
        'hr.employee', string='Person', related='contract_id.employee_id',
        store=True, index=True)
    company_id = fields.Many2one(
        'res.company', string='Company', related='contract_id.company_id',
        store=True, index=True)
    cost_centre_id = fields.Many2one(
        'pb.cost.centre', string='Cost centre', required=True,
        ondelete='restrict')
    date_start = fields.Date(string='From', required=True, index=True)
    state = fields.Selection(MOVE_STATES, string='Status', required=True,
                             default='scheduled', index=True)
    old_text = fields.Char(string='Cost centre before')
    note = fields.Char(string='Why')
    done_on = fields.Datetime(string='Made on')
    problem = fields.Char(string='Could not be made')

    @api.constrains('cost_centre_id', 'contract_id')
    def _check_company(self):
        for move in self:
            if move.cost_centre_id.company_id != move.contract_id.company_id:
                raise ValidationError(_(
                    "Choose a cost centre of the person's own company."))

    def _pb_apply(self):
        """Make the move now: the contract's cost-centre text becomes the
        list entry's code, dated from the move's own date."""
        today = fields.Date.context_today(self)
        for move in self.sudo():
            if move.state != 'scheduled' or move.date_start > today:
                continue
            contract = move.contract_id
            if contract.state not in ('open', 'draft'):
                move.write({'state': 'cancelled', 'problem': _(
                    "The contract was no longer running on that date.")})
                continue
            move.old_text = contract.costcenter or ''
            if _norm(contract.costcenter) != _norm(move.cost_centre_id.code):
                contract.with_context(**{CHANGE_DATE: move.date_start}).write(
                    {'costcenter': move.cost_centre_id.code})
            move.write({'state': 'done', 'done_on': fields.Datetime.now(),
                        'problem': False})
        return True

    @api.model
    def _cron_apply_due(self):
        """Daily, quiet: make every move whose date has come. Safe on an empty
        database; one move that fails never stops the others."""
        today = fields.Date.context_today(self)
        due = self.sudo().search([('state', '=', 'scheduled'),
                                  ('date_start', '<=', today)], limit=2000)
        done = 0
        for move in due:
            try:
                with self.env.cr.savepoint():
                    move._pb_apply()
                    done += 1
            except Exception as exc:  # noqa: BLE001 - one row never stops the job
                _logger.warning('pb_org_structure: cost-centre move %s: %s',
                                move.id, exc)
                move.write({'problem': _(
                    "This change could not be made. Open it and try again.")})
        if done:
            _logger.info('pb_org_structure: %s cost-centre changes made', done)
        return done
