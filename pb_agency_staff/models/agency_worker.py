# -*- coding: utf-8 -*-
"""`pb.agency.worker` — somebody an agency supplies, who is not on our payroll.

Owner ruling J5: a SEPARATE LIGHT RECORD that can never get into a pay run.

WHY IT IS NOT AN `hr.employee` (S8 facts §8). The pay run population is
contract-driven and FALLS BACK TO EVERY COMPANY EMPLOYEE when nobody has an
open contract (`_undated_contract_population`); nothing anywhere filters on
the employment type; every headcount counts every active employee. A person
kept as an employee "not on payroll" would be one wrong click from a payslip.
So this record has no employee, no contract, no login and no link a pay run,
a payslip or a clock-in could follow — it is safe by construction, not by a
filter somebody has to remember.

Rights: HR (`hr.group_hr_user` reads and keeps them; HR managers may delete).
Never shown to managers on /my or to agencies.
"""
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

#: "Ending soon" on the quiet board.
ENDING_DAYS = 30


class PbAgencyWorker(models.Model):
    _name = 'pb.agency.worker'
    _description = 'Agency staff member'
    _inherit = ['mail.thread']
    _order = 'name, id'

    name = fields.Char(string='Name', required=True, index=True,
                       tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 required=True, index=True,
                                 default=lambda s: s.env.company)
    vendor_id = fields.Many2one(
        'pb.vendor', string='Agency', index=True, ondelete='restrict',
        tracking=True, help='The agency that supplies them, from Vendors.')
    job_title = fields.Char(string='Role', tracking=True)
    department_id = fields.Many2one('hr.department', string='Team',
                                    index=True, ondelete='set null',
                                    tracking=True)
    work_location_id = fields.Many2one('hr.work.location', string='Site',
                                       ondelete='set null', tracking=True)
    manager_id = fields.Many2one('hr.employee', string='Manager here',
                                 ondelete='set null', index=True,
                                 tracking=True)
    date_start = fields.Date(string='Starts', tracking=True, index=True)
    date_end = fields.Date(string='Ends', tracking=True, index=True)
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    notes = fields.Text(string='Notes')
    attachment_ids = fields.Many2many(
        'ir.attachment', 'pb_agency_worker_attachment_rel', 'worker_id',
        'attachment_id', string='Documents')
    status = fields.Selection([
        ('upcoming', 'Starting later'),
        ('on_site', 'On site'),
        ('ended', 'Ended'),
    ], string='Status', compute='_compute_status')

    @api.depends('date_start', 'date_end', 'active')
    def _compute_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.date_end and rec.date_end < today or not rec.active:
                rec.status = 'ended'
            elif rec.date_start and rec.date_start > today:
                rec.status = 'upcoming'
            else:
                rec.status = 'on_site'

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("The end date cannot be before the "
                                        "start date."))

    @api.constrains('department_id', 'manager_id', 'company_id')
    def _check_company(self):
        for rec in self:
            for other, label in ((rec.department_id, _('team')),
                                 (rec.manager_id, _('manager'))):
                if other and other.company_id and \
                        other.company_id != rec.company_id:
                    raise ValidationError(_(
                        "The %(what)s belongs to another company.",
                        what=label))

    # ------------------------------------------------------------ domains
    @api.model
    def _today(self):
        return fields.Date.context_today(self)

    @api.model
    def _dom_on_site(self):
        today = fields.Date.to_string(self._today())
        return [('active', '=', True),
                '|', ('date_start', '=', False), ('date_start', '<=', today),
                '|', ('date_end', '=', False), ('date_end', '>=', today)]

    @api.model
    def _dom_upcoming(self):
        today = fields.Date.to_string(self._today())
        return [('active', '=', True), ('date_start', '>', today)]

    @api.model
    def _dom_ending(self):
        today = self._today()
        return [('active', '=', True),
                ('date_end', '>=', fields.Date.to_string(today)),
                ('date_end', '<=', fields.Date.to_string(
                    today + timedelta(days=ENDING_DAYS)))]

    @api.model
    def _dom_ended(self):
        today = fields.Date.to_string(self._today())
        return ['|', ('active', '=', False), ('date_end', '<', today)]

    @api.model
    def on_site_count(self, company_ids=None):
        """How many are on site today — the figure beside the headcount."""
        if not self.env.user.has_group('hr.group_hr_user'):
            return 0
        domain = self._dom_on_site()
        if company_ids:
            domain = [('company_id', 'in', list(company_ids))] + domain
        return self.search_count(domain)


class PbPeopleAgency(models.AbstractModel):
    """The figure beside the headcount: never added to it (ruling J5)."""
    _inherit = 'pb.people'

    @api.model
    def _roster_kpis(self):
        answer = super()._roster_kpis()
        try:
            count = self.env['pb.agency.worker'].on_site_count(
                self.env.companies.ids)
        except Exception:       # noqa: BLE001 — a side figure never blanks People
            count = 0
        if isinstance(answer, dict) and isinstance(answer.get('kpis'), dict):
            answer['kpis']['agency_staff'] = count
        return answer


class PbVendorsAgency(models.AbstractModel):
    """The agency's drawer in Vendors lists the people it supplies."""
    _inherit = 'pb.vendors'

    def get_vendor(self, vendor_id):
        answer = super().get_vendor(vendor_id)
        if not self.env.user.has_group('hr.group_hr_user'):
            return answer
        workers = self.env['pb.agency.worker'].search(
            [('vendor_id', '=', int(vendor_id))], order='date_end, name',
            limit=50)
        answer = dict(answer)
        answer['agency_staff'] = [{
            'id': w.id, 'name': w.name, 'role': w.job_title or '',
            'team': w.department_id.name or '',
            'status': w.status,
            'status_label': dict(w._fields['status']._description_selection(
                self.env)).get(w.status, ''),
        } for w in workers]
        return answer
