from odoo import _, api, models
from odoo.exceptions import AccessError, UserError
from odoo.addons.pb_people_advanced.models.newhire_approval import require_hr


class JoiningBoard(models.AbstractModel):
    _name = 'pb.joining.board'
    _description = 'Joining board'
    _inherit = 'pb.filter.mixin'

    @api.model
    def _can_manage(self):
        try:
            return require_hr(self.env)
        except AccessError:
            return False

    @api.model
    def _check_manage(self):
        require_hr(self.env)

    @api.model
    def can_open(self):
        return bool(self.env.user._is_internal() and (self._can_manage() or self.env['pb.hiring'].can_open()
                    or self.env['pb.onboarding']._can_read() or self.env.user.has_group('pb_new_hire.group_joiners_board')))

    def _base(self):
        return [('company_id', 'in', self.env.companies.ids)]

    def _one(self, joining_id):
        j = self.env['pb.joining'].sudo().search(self._base() + [('id', '=', int(joining_id))], limit=1)
        if not self.can_open() or not j:
            raise AccessError(_('You cannot open this joining.'))
        return j

    @api.model
    def invite(self, vals):
        self._check_manage()
        name = str(vals.get('name') or '').strip()
        email = str(vals.get('email') or '').strip()
        phone = str(vals.get('phone') or '').strip()
        if not email and not phone:
            raise UserError(_('Add an email or a mobile number so the link can reach them.'))
        studio = self.env['pb.new.hire']
        if not name or not vals.get('first_day') or not vals.get('job_title') or vals.get('payroll_country') not in dict(studio._countries()):
            raise UserError(_('Add the full name, first day, country of work and job title.'))
        data = {k: vals[k] for k in ('first_day', 'job_title', 'payroll_country', 'manager_id', 'department_id', 'lang') if k in vals}
        j = self.env['pb.joining'].sudo().create(dict(data, name=name, email=email, phone=phone, company_id=self.env.company.id))
        j._send_link()
        return {'id': j.id, 'mode': j.link_mode}
