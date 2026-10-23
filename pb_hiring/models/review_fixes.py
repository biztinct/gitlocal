"""Corrections from the October client traceability review."""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .analytics import _mean, _median, _span
from .channels_p7 import utm_record


def hiring_only(user):
    return user.has_group('pb_hiring.group_hiring_only') and not user.has_group('base.group_system')


class HiringAccessDirectory(models.AbstractModel):
    _inherit = 'pb.access'

    def _require(self):
        if hiring_only(self.env.user):
            raise AccessError(_('The access directory is not available to hiring-only accounts.'))
        return super()._require()

    def _require_manage(self):
        if hiring_only(self.env.user):
            raise AccessError(_('Hiring-only accounts cannot change access outside hiring.'))
        return super()._require_manage()


class HiringSession(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        info = super().session_info()
        info['pb_hiring_only'] = bool(info.get('uid') and hiring_only(self.env.user))
        return info


class HiringSidebar(models.Model):
    _inherit = 'pb.sidebar.item'

    @api.model
    def visibility_for(self, user):
        return super(HiringSidebar, self.with_context(pb_sidebar_uid=user.id)).visibility_for(user)

    def _state_for(self, item, is_admin, user_groups):
        user = self.env['res.users'].browse(self.env.context.get('pb_sidebar_uid') or self.env.uid)
        if hiring_only(user) and item != self.env.ref('pb_hiring.item_hiring'):
            return False, False
        return super()._state_for(item, is_admin, user_groups)

    def _section_state_for(self, section, is_admin):
        user = self.env['res.users'].browse(self.env.context.get('pb_sidebar_uid') or self.env.uid)
        if hiring_only(user) and section != self.env.ref('pb_hiring.item_hiring').section_id:
            return False, False, ''
        return super()._section_state_for(section, is_admin)


class HiringSettings(models.AbstractModel):
    _inherit = 'pb.settings'

    @api.model
    def resolve_gates(self, categories):
        result = super().resolve_gates(categories)
        if hiring_only(self.env.user):
            for key in result['categories']:
                result['categories'][key] = key == 'hiring'
            for key in result['cards']:
                result['cards'][key] = key.startswith('hiring:') and result['cards'][key]
        return result


class HiringReview(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def _kpis(self, rows, interviews=None):
        result = super()._kpis(rows, interviews)
        # Count candidates, matching the Applicants chip, across every round
        # and without the recent-interview display window or its row cap.
        roles = self.env['pb.hiring.requisition'].search([
            ('company_id', 'in', self.env.companies.ids)])
        late = self.env['pb.hiring.feedback'].sudo().search([
            ('requisition_id', 'in', roles.ids), ('state', '=', 'pending'),
            ('due_at', '<', fields.Datetime.now()), ('due_at', '!=', False),
            ('interview_id.state', 'in', ('scheduled', 'done')),
            ('applicant_id.active', '=', True),
            ('applicant_id.stage_id.pb_family', '=', 'open')])
        result['feedback_late'] = len(late.mapped('applicant_id'))
        return result


class HiringAnalyticsReview(models.AbstractModel):
    _inherit = 'pb.hiring.analytics'

    @api.model
    def _agency_split(self, requests):
        """Attribute a joined person to their submitting agency, not the role."""
        apps = self.env['hr.applicant'].sudo().with_context(active_test=False).search([
            ('pb_requisition_id', 'in', requests.ids)])
        offers = self.env['pb.hiring.offer'].sudo().search([
            ('requisition_id', 'in', requests.ids), ('state', '=', 'joined')])
        result = []
        for key, label, agency in [('agency', _('With an agency'), True),
                                    ('inhouse', _('Our own team'), False)]:
            candidates = apps.filtered(lambda a: bool(a.pb_agency_vendor_id) == agency)
            joined = offers.filtered(lambda o: o.applicant_id in candidates)
            # One person per role; guard against multiple offers for them.
            unique = {o.applicant_id.id: o for o in joined}
            spans = [_span(o.joined_on, o.requisition_id.opened_on)
                     for o in unique.values() if o.joined_on and o.requisition_id.opened_on]
            result.append({'key': key, 'name': label, 'roles': len(candidates),
                           'filled': len(unique),
                           'median': round(_median(spans), 1) if spans else None,
                           'mean': round(_mean(spans), 1) if spans else None})
        return result


class ApplicantReview(models.Model):
    _inherit = 'hr.applicant'

    @api.model_create_multi
    def create(self, vals_list):
        # Website, referral and agency entry points set their exact source.
        # For the internal form preserve an honest origin instead of a blank.
        for vals in vals_list:
            if (vals.get('pb_requisition_id') or self.env.context.get('default_pb_requisition_id')) \
                    and not vals.get('source_id') and not self.env.context.get('default_source_id'):
                vals['source_id'] = utm_record(self.env, 'utm.source', 'Manual entry / import').id
        return super().create(vals_list)
