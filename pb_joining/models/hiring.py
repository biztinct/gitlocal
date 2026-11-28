from odoo import _, api, fields, models
from odoo.addons.pb_hiring.models.hiring_common import flag, leg


class JoiningHiring(models.Model):
    _inherit = 'pb.hiring.offer'

    def _on_signed(self, kind=None, label=None, quiet=False):
        result = super()._on_signed(kind=kind, label=label, quiet=quiet)
        if (not quiet and not any(self.env.context.get(k) for k in ('pb_no_automation', 'pb_no_stage_log', 'install_mode'))
                and not getattr(self.applicant_id, 'pb_internal', False)
                and flag(self.env, 'pb_joining.auto_invite', '1')):
            leg(self.env, 'joining invitation', lambda: self.env['pb.joining'].sudo()._open_for_offer(self))
        return result

    def action_change_join_date(self, new_date, reason=None, source='drawer', by_name=None):
        result = super().action_change_join_date(new_date, reason=reason, source=source, by_name=by_name)
        self.env['pb.joining'].sudo().search([('offer_id', '=', self.id)]).write({'first_day': self.expected_join_date})
        return result

    def action_did_not_join(self, reason=None, note=None, source='drawer', by_name=None):
        result = super().action_did_not_join(reason=reason, note=note, source=source, by_name=by_name)
        self.env['pb.joining'].sudo().search([('offer_id', '=', self.id)])._cancel(note or reason)
        return result


class JoiningOffer(models.Model):
    _inherit = 'pb.joining'

    @api.model
    def _open_for_offer(self, offer):
        offer.ensure_one()
        self.env.cr.execute('SELECT id FROM pb_hiring_offer WHERE id=%s FOR UPDATE', [offer.id])
        record = self.search([('offer_id', '=', offer.id)], limit=1)
        if record:
            return record
        app, req = offer.applicant_id, offer.requisition_id
        j = self.with_company(offer.company_id).create({
            'name': app.partner_name or app.partner_id.name or app.display_name, 'email': app.email_from, 'phone': app.partner_phone,
            'origin': 'hiring', 'offer_id': offer.id, 'company_id': offer.company_id.id,
            'job_title': offer.job_title or req.title, 'job_id': req.job_id.id, 'department_id': req.department_id.id,
            'manager_id': (offer.reporting_manager_id or req.reporting_manager_id).id,
            'payroll_country': (req.country_id or offer.company_id.country_id).code or 'XX',
            'first_day': offer.expected_join_date or offer.start_date, 'lang': app.pb_lang or offer.company_id.partner_id.lang,
        })
        j._send_link()
        return j

    def _cancel(self, reason):
        self.write({'state': 'cancelled', 'cancel_reason': reason, 'cancelled_at': fields.Datetime.now(),
                    'code_hash': False, 'code_until': False})

    def _send_link(self):
        self.ensure_one()
        if self._can_email() and self._mail('joining_link'):
            self.write({'link_sent_at': fields.Datetime.now(), 'link_mode': 'email'})
        else:
            self.link_mode = 'pass_on'
            self.activity_schedule('mail.mail_activity_data_todo', user_id=self._contact().id,
                                   summary=_('Pass on the joining link to %(name)s', name=self.name))
