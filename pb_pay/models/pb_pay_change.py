# -*- coding: utf-8 -*-
"""`pb.pay.change` — one person's pay, changed outside a review.

A promotion in March. A correction to a figure that was typed wrongly. A
counter-offer to keep somebody. These are the pay decisions that do not wait
for the annual review, and until now the only way to make one was to open the
contract and type over the wage — no guidance, no limit, no approval, no
letter and no record of why.

This is the same machinery as a review, for one row: the guidance grid says
what it would suggest, the company's own limits say what it will not quietly
allow, the same approval chain carries it, and the same `pb.pay.apply` writes
it with the same twenty-four-hour way back and the same letter.

ONE RULE OF ITS OWN
-------------------
A pay change is refused while a review is open for the same person. Two people
deciding the same person's pay at the same time, from two screens, neither of
which can see the other, is how somebody ends up with two raises.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GROUP_MANAGER = 'pb_pay.group_pay_manager'
GROUP_FINANCE = 'pb_pay.group_pay_finance'
GROUP_CEO = 'pb_pay.group_pay_ceo'

KINDS = [
    ('promotion', 'Promotion'),
    ('correction', 'Putting a mistake right'),
    ('market', 'Keeping up with the market'),
    ('other', 'Something else'),
]

STATES = [
    ('draft', 'Being written'),
    ('proposed', 'With HR'),
    ('hr_review', 'With finance'),
    ('finance', 'With the CEO'),
    ('approved', 'Approved'),
    ('applied', 'Applied'),
    ('closed', 'Closed'),
    ('refused', 'Sent back'),
]

#: The states a review is in while it still has a say over somebody's pay.
LIVE_REVIEW_STATES = ('draft', 'proposed', 'hr_review', 'finance', 'approved')


class PbPayChange(models.Model):
    _name = 'pb.pay.change'
    _description = 'Pay change'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'biz.approval.chain.mixin']
    _order = 'effective_date desc, id desc'

    name = fields.Char(string='Pay change', compute='_compute_name',
                       store=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='cascade', tracking=True)
    person_id = fields.Integer(string='Person', index=True)
    contract_id = fields.Many2one(
        'hr.contract', string='Contract', ondelete='set null')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency')
    kind = fields.Selection(KINDS, string='Why', default='promotion',
                            required=True, tracking=True)
    new_job_id = fields.Many2one('hr.job', string='New job position')

    current_wage = fields.Monetary(string='Paid now')
    new_wage = fields.Monetary(string='New pay', tracking=True)
    pct = fields.Float(string='Rise', digits=(16, 2))
    effective_date = fields.Date(
        string='New pay starts on', required=True,
        default=lambda self: fields.Date.context_today(self))
    reason = fields.Text(string='The case for it')

    band_id = fields.Many2one('pb.pay.band', string='Band',
                              ondelete='set null')
    position_before = fields.Float(string='Position now', digits=(16, 2))
    position_after = fields.Float(string='Position after', digits=(16, 2))
    guidance_pct = fields.Float(string='Guidance', digits=(16, 2))
    chips = fields.Json(string='What to know')

    state = fields.Selection(
        STATES, string='Status', default='draft', tracking=True, index=True,
        copy=False)
    applied_at = fields.Datetime(string='Applied on', readonly=True)
    applied_by = fields.Many2one('res.users', string='Applied by',
                                 readonly=True)
    undo_until = fields.Datetime(string='Can be taken back until',
                                 readonly=True)
    apply_ids = fields.One2many('pb.pay.apply', 'change_id',
                                string='What was written')
    approval_widget_json = fields.Char(compute='_compute_approval_widget')

    _approval_transitions = {
        ('draft', 'proposed'): None,
        ('proposed', 'hr_review'): GROUP_MANAGER,
        ('hr_review', 'finance'): GROUP_FINANCE,
        ('hr_review', 'approved'): GROUP_FINANCE,
        ('finance', 'approved'): GROUP_CEO,
        ('approved', 'applied'): GROUP_MANAGER,
        ('applied', 'closed'): GROUP_MANAGER,
        ('proposed', 'draft'): GROUP_MANAGER,
        ('hr_review', 'draft'): GROUP_FINANCE,
        ('finance', 'draft'): GROUP_CEO,
    }
    _approval_dead_states = ('refused',)

    # ------------------------------------------------------------- the name
    @api.depends('employee_id', 'kind', 'effective_date')
    def _compute_name(self):
        labels = dict(KINDS)
        for change in self:
            change.name = _(
                '%(kind)s · %(who)s · %(when)s',
                kind=labels.get(change.kind, _('Pay change')),
                who=change.employee_id.name or _('somebody'),
                when=fields.Date.to_string(change.effective_date) or '')

    def _approval_steps(self):
        steps = [
            {'state': 'draft', 'label': _('Being written'),
             'group_label': _('The manager')},
            {'state': 'proposed', 'label': _('With HR'),
             'group_label': _('HR')},
        ]
        if self.needs_finance():
            steps.append({'state': 'hr_review', 'label': _('With finance'),
                          'group_label': _('Finance')})
            steps.append({'state': 'finance', 'label': _('With the CEO'),
                          'group_label': _('The CEO')})
        else:
            steps.append({'state': 'hr_review', 'label': _('With finance'),
                          'group_label': _('Finance')})
        steps.append({'state': 'approved', 'label': _('Approved'),
                      'group_label': _('Ready to apply')})
        steps.append({'state': 'applied', 'label': _('Applied'),
                      'group_label': _('Pay changed')})
        return steps

    @api.depends('state')
    def _compute_approval_widget(self):
        for change in self:
            change.approval_widget_json = \
                change._approval_widget_payload(change._approval_steps()) \
                if change.id else False

    def _approval_can(self, from_state, to_state):
        self.ensure_one()
        if self.env.su or self.env.user._is_admin():
            return True
        if (from_state, to_state) == ('draft', 'proposed'):
            if self.create_uid.id == self.env.uid:
                return True
            return self.env.user.has_group(GROUP_MANAGER)
        return super()._approval_can(from_state, to_state)

    def needs_finance(self):
        """Whether this one is big enough to go past finance."""
        self.ensure_one()
        settings = self.env['pb.pay.settings'].sudo().for_company(
            self.company_id or self.env.company)
        threshold = float(settings.change_finance_pct or 0.0)
        return bool(threshold) and abs(float(self.pct or 0.0)) > threshold

    # ------------------------------------------------------------- the maths
    @api.onchange('employee_id')
    def _onchange_employee(self):
        for change in self:
            if change.employee_id:
                change._fill_from_employee()

    def _fill_from_employee(self):
        """Read the person's contract, band and score in one place."""
        self.ensure_one()
        employee = self.employee_id
        if not employee:
            return
        contract = self.env['hr.contract'].sudo().search([
            ('employee_id', '=', employee.id), ('state', '=', 'open'),
        ], order='date_start desc, id desc', limit=1)
        company = contract.company_id or employee.company_id or self.env.company
        position = self.env['pb.pay.position'].sudo().search(
            [('employee_id', '=', employee.id)], limit=1)
        self.contract_id = contract.id or False
        self.company_id = company.id
        self.currency_id = company.currency_id.id
        self.current_wage = float(contract.wage or 0.0)
        self.band_id = position.band_id.id or False
        self.position_before = float(position.position_pct or 0.0)
        if 'pb_person_id' in employee._fields:
            self.person_id = employee.pb_person_id or employee.id
        else:
            self.person_id = employee.id
        grid = self.env['pb.pay.guidance'].for_company(company)
        rating = 0
        if 'pb_performance_rating' in employee._fields:
            try:
                rating = int(employee.sudo().pb_performance_rating or 0)
            except (TypeError, ValueError):
                rating = 0
        self.guidance_pct = grid.pct_for(
            rating or (grid.middle_rating() if grid else 0),
            self.position_before, bool(position.band_id)) if grid else 0.0
        if not self.new_wage:
            self.new_wage = self.current_wage

    @api.onchange('new_wage', 'current_wage')
    def _onchange_new_wage(self):
        for change in self:
            change._recalc()

    def _recalc(self):
        for change in self:
            base = float(change.current_wage or 0.0)
            new = float(change.new_wage or 0.0)
            change.pct = ((new - base) / base * 100.0) if base else 0.0
            band = change.band_id
            if band and band.max_amount > band.min_amount:
                change.position_after = round(
                    (new - band.min_amount)
                    / (band.max_amount - band.min_amount) * 100.0, 2)
            else:
                change.position_after = 0.0

    # ------------------------------------------------------------- the chips
    def recompute_chips(self):
        for change in self:
            chips = []
            settings = self.env['pb.pay.settings'].sudo().for_company(
                change.company_id or self.env.company)
            money = self.env['pb.pay.bands']
            currency = change.currency_id or change.company_id.currency_id
            for limit in settings.limit_ids:
                if limit.kind == 'max_raise_pct' \
                        and change.pct > limit.value:
                    chips.append({
                        'key': limit.kind, 'tone': 'bad',
                        'blocks': limit.enforcement == 'block',
                        'text': _("%(pct)s%% is above the %(cap)s%% this "
                                  "company allows without a special case.",
                                  pct=('%g' % round(change.pct, 2)),
                                  cap=('%g' % limit.value))})
                if limit.kind == 'max_raise_amount' \
                        and (change.new_wage - change.current_wage) \
                        > limit.value:
                    chips.append({
                        'key': limit.kind, 'tone': 'bad',
                        'blocks': limit.enforcement == 'block',
                        'text': _("%(rise)s is a bigger rise than this "
                                  "company allows.",
                                  rise=money._money(
                                      change.new_wage - change.current_wage,
                                      currency))})
                if limit.kind == 'band_ceiling' and change.band_id \
                        and change.new_wage > change.band_id.max_amount:
                    chips.append({
                        'key': limit.kind, 'tone': 'bad',
                        'blocks': limit.enforcement == 'block',
                        'text': _("%(pay)s is above the top of %(band)s.",
                                  pay=money._money(change.new_wage, currency),
                                  band=change.band_id.name)})
            if not change.band_id:
                chips.append({'key': 'no_band', 'tone': 'info',
                              'blocks': False,
                              'text': _("This job has no band yet, so there "
                                        "is nothing to measure the new pay "
                                        "against.")})
            elif change.position_after > 100:
                chips.append({'key': 'above', 'tone': 'warn', 'blocks': False,
                              'text': _("This puts them above the top of "
                                        "their band.")})
            if change.guidance_pct and change.pct > change.guidance_pct * 2:
                chips.append({
                    'key': 'far_above_guidance', 'tone': 'warn',
                    'blocks': False,
                    'text': _("The guidance for this person is %(guide)s%%; "
                              "this is %(pct)s%%.",
                              guide=('%g' % round(change.guidance_pct, 2)),
                              pct=('%g' % round(change.pct, 2)))})
            change.chips = chips
        return True

    # --------------------------------------------------------------- writing
    @api.model_create_multi
    def create(self, vals_list):
        changes = super().create(vals_list)
        for change in changes:
            if not change.current_wage:
                change._fill_from_employee()
            change._recalc()
            change._check_no_open_review()
        changes.recompute_chips()
        return changes

    def write(self, vals):
        result = super().write(vals)
        if {'new_wage', 'current_wage', 'employee_id',
                'band_id'} & set(vals):
            self._recalc()
            self.recompute_chips()
        return result

    def _check_no_open_review(self):
        """Two screens may not decide the same person's pay at once."""
        self.ensure_one()
        open_line = self.env['pb.pay.review.line'].sudo().search([
            ('employee_id', '=', self.employee_id.id),
            ('review_id.state', 'in', LIVE_REVIEW_STATES),
        ], limit=1)
        if open_line:
            raise UserError(_(
                "%(who)s is in the pay review “%(review)s”, which has not "
                "finished yet. Change their pay there, or finish that review "
                "first.",
                who=self.employee_id.name or _('this person'),
                review=open_line.review_id.name or ''))

    def _before_approval_transition(self, to_state):
        super()._before_approval_transition(to_state)
        if to_state == 'proposed':
            self.recompute_chips()
            if any(chip.get('blocks') for chip in (self.chips or [])):
                raise UserError(_(
                    "This pay change breaks a limit this company will not "
                    "bend. The reason is on the card above."))
            if abs(float(self.new_wage or 0.0)
                   - float(self.current_wage or 0.0)) < 0.005:
                raise UserError(_(
                    "The new pay is the same as the old pay, so there is "
                    "nothing to send for approval."))
            self._check_no_open_review()

    def _after_approval_transition(self, to_state):
        super()._after_approval_transition(to_state)
        group = {'proposed': GROUP_MANAGER, 'hr_review': GROUP_FINANCE,
                 'finance': GROUP_CEO}.get(to_state)
        if not group:
            return
        try:
            record = self.env.ref(group).sudo()
            people = record.all_user_ids if 'all_user_ids' in record._fields \
                else record.user_ids
        except Exception:                       # noqa: BLE001
            return
        for user in people.filtered(
                lambda u: u.active and u.id != self.env.uid)[:10]:
            try:
                self.activity_schedule(
                    act_type_xmlid='mail.mail_activity_data_todo',
                    summary=_('A pay change is waiting for you'),
                    note=self.name or '', user_id=user.id)
            except Exception:                   # noqa: BLE001
                pass

    # -------------------------------------------------------------- the doors
    def action_submit(self):
        self.ensure_one()
        return self._advance_state('proposed')

    def action_hr_approve(self):
        self.ensure_one()
        return self._advance_state('hr_review')

    def action_next_after_hr(self):
        self.ensure_one()
        return self._advance_state(
            'finance' if self.needs_finance() else 'approved')

    def action_ceo_approve(self):
        self.ensure_one()
        return self._advance_state('approved')

    def action_send_back(self, note=False):
        self.ensure_one()
        return self._advance_state('draft', note=note)

    # -------------------------------------------------------- apply and undo
    def action_apply(self):
        """Write the new pay, exactly the way a review does."""
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_(
                "Only an approved pay change can be applied."))
        contract = self.contract_id
        if not contract or contract.state != 'open':
            raise UserError(_(
                "%(who)s has no open contract, so there is nothing to write a "
                "new figure onto.",
                who=self.employee_id.name or _('this person')))
        now = fields.Datetime.now()
        Apply = self.env['pb.pay.apply']
        until = Apply._undo_deadline(now)
        old = float(contract.wage or 0.0)
        # SUDO for the reason set out on `pb.pay.apply.apply_review`: the
        # approval chain is the gate, and the alternative is giving every pay
        # manager blanket contract-editing rights.
        self.env['hr.contract'].sudo().with_context(
            pb_pay_no_rebuild=True).browse(contract.id).write(
                {'wage': self.new_wage})
        if self.new_job_id:
            try:
                self.env['hr.contract'].sudo().with_context(
                    pb_pay_no_rebuild=True).browse(contract.id).write(
                        {'job_id': self.new_job_id.id})
            except Exception:                   # noqa: BLE001
                _logger.info('pb_pay: the job could not be changed on '
                             'contract %s', contract.id)
        record = Apply.sudo().create({
            'change_id': self.id,
            'employee_id': self.employee_id.id,
            'contract_id': contract.id,
            'company_id': self.company_id.id,
            'currency_id': (self.currency_id
                            or self.company_id.currency_id).id,
            'old_wage': old, 'new_wage': self.new_wage,
            'effective_date': self.effective_date,
            'applied_at': now, 'applied_by': self.env.uid,
            'undo_until': until,
        })
        self.sudo().write({'applied_at': now, 'applied_by': self.env.uid,
                           'undo_until': until})
        self._advance_state('applied')
        record._make_letters(self)
        Apply._recompute_positions(self.company_id)
        self.message_post(body=_(
            "Applied. %(who)s is paid %(amount)s from %(date)s.",
            who=self.employee_id.name or '',
            amount=self.env['pb.pay.bands']._money(
                self.new_wage, self.currency_id
                or self.company_id.currency_id),
            date=fields.Date.to_string(self.effective_date)))
        return {'sentence': _(
            "Applied. You can take it back until %(when)s.",
            when=fields.Datetime.to_string(until)), 'undo_until': str(until)}

    def action_undo(self):
        self.ensure_one()
        rows = self.apply_ids.filtered(lambda a: a.state == 'applied')
        if not rows:
            raise UserError(_("There is nothing here to take back."))
        if self.undo_until and fields.Datetime.now() > self.undo_until:
            raise UserError(_(
                "The time to take this back ran out at %(when)s. Put it back "
                "down with another pay change, which leaves a record of both "
                "moves.", when=fields.Datetime.to_string(self.undo_until)))
        count = rows._restore()
        self.sudo().write({'undo_until': False, 'applied_at': False,
                           'applied_by': False})
        self._chain_state_write('approved')
        self._log_transition('applied', 'approved', _('Taken back'))
        self.env['pb.pay.apply']._recompute_positions(self.company_id)
        self.message_post(body=_("Taken back. The old pay is back in place."))
        return {'count': count,
                'sentence': _("The old pay is back in place.")}

    # -------------------------------------------------------------- the read
    def payload(self):
        self.ensure_one()
        money = self.env['pb.pay.bands']
        currency = self.currency_id or self.company_id.currency_id
        return {
            'id': self.id,
            'name': self.name or '',
            'employee_id': self.employee_id.id,
            'employee': self.employee_id.name or '',
            'kind': self.kind,
            'kind_label': dict(KINDS).get(self.kind, ''),
            'state': self.state,
            'state_label': dict(STATES).get(self.state, ''),
            'current_wage': float(self.current_wage or 0.0),
            'current_label': money._money(self.current_wage, currency),
            'new_wage': float(self.new_wage or 0.0),
            'new_label': money._money(self.new_wage, currency),
            'pct': round(float(self.pct or 0.0), 2),
            'guidance_pct': round(float(self.guidance_pct or 0.0), 2),
            'band': self.band_id.name or '',
            'position_before': round(float(self.position_before or 0.0), 1),
            'position_after': round(float(self.position_after or 0.0), 1),
            'effective_date': str(self.effective_date or ''),
            'reason': self.reason or '',
            'new_job': self.new_job_id.display_name or '',
            'chips': self.chips or [],
            'blocked': any(c.get('blocks') for c in (self.chips or [])),
            'undo_until': str(self.undo_until or ''),
            'needs_finance': self.needs_finance(),
            'trail': self.get_approval_trail(),
            'steps': self._approval_steps(),
        }
