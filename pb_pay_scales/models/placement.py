# -*- coding: utf-8 -*-
"""Where a contract stands on a scale — On scale, Pinned (with a reason) or
Drifted — and the job-to-grade link.

WHY A RECORD OF ITS OWN AND NOT COLUMNS ON `hr.contract`
---------------------------------------------------------
Placing somebody on a grade and step is a statement ABOUT a contract, not a
change TO it. A separate row means placing, pinning or un-placing a person
never writes `hr.contract` at all: no write date moves, no "Paid by" goes
stale, no position rebuild is queued, no trail row says the contract changed.
The safety rail "nothing changes an existing contract until a user applies a
scale" is then true by construction, and the test counts it.

The state is worked out when it is read (never stored), from the placement,
the version of the scale in force today and the contract's own wage, so it can
never be stale: edit a cell and the people on it read "Drifted" at once.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

PIN_REASONS = [
    ('offer', 'Offer agreed'),
    ('offer_match', 'Offer match'),
    ('retention', 'Kept to retain them'),
    ('above_top', 'Above the top step'),
    ('legacy', 'Paid this before the scale'),
    ('typed', 'Typed when hired'),
    ('other', 'Other reason'),
]

STATES = [('on', 'On scale'), ('pinned', 'Pinned'), ('drifted', 'Drifted')]


class PbPayScalePlacement(models.Model):
    _name = 'pb.pay.scale.placement'
    _description = 'Place on a pay scale'
    _order = 'id desc'

    contract_id = fields.Many2one('hr.contract', string='Contract', required=True,
                                  ondelete='cascade', index=True)
    employee_id = fields.Many2one(related='contract_id.employee_id', store=True,
                                  index=True)
    company_id = fields.Many2one(related='contract_id.company_id', store=True,
                                 index=True)
    grade_id = fields.Many2one('pb.pay.scale.grade', string='Grade', required=True,
                               ondelete='restrict', index=True)
    scale_id = fields.Many2one(related='grade_id.scale_id', store=True, index=True)
    step_no = fields.Integer(string='Step', required=True, default=1)
    pinned = fields.Boolean(string='Pinned')
    pin_reason = fields.Selection(PIN_REASONS, string='Why it is different')
    pin_note = fields.Char(string='Note')
    placed_on = fields.Date(string='Placed on', default=fields.Date.context_today)
    placed_by = fields.Many2one('res.users', string='Placed by',
                                default=lambda self: self.env.user)
    source = fields.Selection(
        [('hire', 'When hired'), ('hand', 'By hand'), ('match', 'Matched to a step')],
        string='How', default='hand')
    state = fields.Selection(STATES, string='Standing', compute='_compute_state')
    scale_amount = fields.Float(string='Scale amount', compute='_compute_state')

    _contract_uniq = models.Constraint(
        'unique(contract_id)', 'A contract stands in one place on one scale.')

    @api.constrains('step_no', 'grade_id')
    def _check_step(self):
        for row in self:
            top = row.grade_id.scale_id.step_count or 1
            if not 1 <= row.step_no <= top:
                raise ValidationError(_("This scale has steps 1 to %(top)s.", top=top))

    def _compute_state(self):
        today = fields.Date.context_today(self)
        for row in self:
            scale = row.grade_id.scale_id.sudo()
            version = scale.version_on(today) if scale else None
            value = version.value_of(row.grade_id, row.step_no) if version else None
            row.scale_amount = value or 0.0
            if row.pinned:
                row.state = 'pinned'
                continue
            wage = row.contract_id.sudo().wage or 0.0
            half = 0.5 * 10.0 ** (-(scale.decimals() if scale else 0))
            row.state = 'on' if value is not None and abs(wage - value) < half else 'drifted'

    def label(self):
        """One plain line: "On scale · Senior associate, step 2" …"""
        self.ensure_one()
        grade = self.grade_id.name or ''
        if self.state == 'on':
            return _("On scale · %(grade)s, step %(step)s", grade=grade, step=self.step_no)
        if self.state == 'pinned':
            reason = dict(self._fields['pin_reason']._description_selection(self.env)).get(
                self.pin_reason) if self.pin_reason else _("Other reason")
            return _("Pinned · %(reason)s", reason=reason)
        return _("Drifted · %(grade)s, step %(step)s", grade=grade, step=self.step_no)


class PbPayBandJob(models.Model):
    """The job → grade link, on the EXISTING job → band link (FACTS §3 item 2:
    never a second job-to-grade map)."""
    _inherit = 'pb.pay.band.job'

    pb_scale_grade_id = fields.Many2one(
        'pb.pay.scale.grade', string='Grade on a pay scale', ondelete='set null',
        index=True)

    @api.constrains('pb_scale_grade_id', 'band_id')
    def _check_scale_country(self):
        for link in self:
            grade = link.pb_scale_grade_id
            if grade and grade.scale_id.country_code != link.band_id.country_code:
                raise ValidationError(_(
                    "%(job)s is in a band for another country than the scale "
                    "%(scale)s.", job=link.job_id.display_name,
                    scale=grade.scale_id.name))


class HrContract(models.Model):
    """Read-only: where this contract stands on a scale. Nothing is stored on
    the contract (see the module docstring)."""
    _inherit = 'hr.contract'

    pb_scale_state = fields.Selection(STATES, string='Pay scale standing',
                                      compute='_compute_pb_scale')
    pb_scale_label = fields.Char(string='On the pay scale',
                                 compute='_compute_pb_scale')

    def _compute_pb_scale(self):
        rows = {}
        if self.ids:
            for row in self.env['pb.pay.scale.placement'].sudo().search(
                    [('contract_id', 'in', self.ids)]):
                rows[row.contract_id.id] = row
        for contract in self:
            row = rows.get(contract.id)
            contract.pb_scale_state = row.state if row else False
            contract.pb_scale_label = row.label() if row else False
