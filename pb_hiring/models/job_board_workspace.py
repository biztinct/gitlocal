"""Recruiter publishing workspace. Reuse the existing delivery and permission gates."""
import re

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html2plaintext, plaintext2html

from .job_boards import BOARD_FIELDS
from ..services.job_boards import BOARD_PROVIDERS


class JobBoardWorkspace(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def can_open_job_boards(self):
        return bool(self._can_recruit())

    def _workspace_role(self, role_id):
        req = self._p7_role({'requisition_id': role_id})
        if req.company_id != self.env.company:
            raise AccessError(_('Switch to this role’s company before publishing.'))
        covered = self._cover_scope()
        if not (covered and req.recruiter_id.id in covered) and not self._role_readable(req):
            raise AccessError(_('You cannot publish this role.'))
        return req

    @api.model
    def job_board_home(self):
        if not self._can_recruit():
            raise AccessError(_('Job boards are available to the hiring team.'))
        roles = self.env['pb.hiring.requisition']
        domain = [('company_id', '=', self.env.company.id), ('state', 'in', ['setup', 'open'])]
        covered = self._cover_scope()
        if covered:
            roles = roles.sudo()
            domain.append(('recruiter_id', 'in', covered))
        rows = roles.search(domain, order='id desc', limit=501)
        return dict(company=self.env.company.name, can_setup=self._can_write(), capped=len(rows) > 500,
                    roles=[dict(id=r.id, title=r.title, location=r.location or '',
                                country=r.country_id.name or '', confidential=r.is_confidential,
                                published=bool(r.job_id.is_published)) for r in rows[:500]])

    def _workspace_connection(self, provider, company):
        conn = self.env['pb.hiring.connection'].sudo()._for_company(provider, company)
        if not conn:
            return dict(ready=False, environment='', note=_('Your administrator can connect this board. Manual posting is available now.'))
        try:
            conn._ready()
            ready = True
        except UserError:
            ready = False
        return dict(ready=ready, environment=conn._config().get('environment', ''),
                    note=_('Connected. Review the advert before sending.') if ready else
                    _('Connection setup is incomplete. Use manual posting or ask your administrator.'))

    @api.model
    def job_board_detail(self, role_id):
        req = self._workspace_role(role_id)
        panel = self.get_publish_panel(req.id)
        panel.update(location=req.location or '', company=req.company_id.name,
                     description=html2plaintext(req.job_id.website_description or req.jd_current_id.body or ''))
        for row in panel['rows']:
            rc = self.env['pb.hiring.role.channel'].sudo().browse(row['id'])
            provider = BOARD_PROVIDERS.get(row['key'])
            row['connection'] = self._workspace_connection(provider, req.company_id) if provider else dict(
                ready=False, environment='', note=_('Post using the advert and tracked application link.'))
            row['delivery_state'] = rc.board_state
            row['draft'] = {k: v for k, v in (rc.board_values or {}).items() if k in BOARD_FIELDS}
            row['draft']['description'] = html2plaintext(row['draft'].get('description') or
                                                        req.job_id.website_description or req.jd_current_id.body or '')
        return panel

    @api.model
    def job_board_save(self, channel_id, values, operation='draft'):
        rc = self._p7_row({'role_channel_id': channel_id})
        req = self._workspace_role(rc.requisition_id.id)
        if operation not in ('draft', 'publish', 'update') or not isinstance(values, dict):
            raise UserError(_('Choose a valid publishing action.'))
        if req.is_confidential or req.state not in ('setup', 'open'):
            raise UserError(_('Only active, public roles can be advertised.'))
        if rc.channel_id.kind not in ('board', 'social') or not rc.channel_id._applies_to(req):
            raise UserError(_('This board is not enabled for this role.'))
        vals = {k: v for k, v in values.items() if k in BOARD_FIELDS}
        # The workspace edits plain text. Preserve original rich formatting unless changed.
        previous = (rc.board_values or {}).get('description') or req.job_id.website_description or req.jd_current_id.body or ''
        text = str(vals.get('description') or '')
        if len(text) > 100000:
            raise UserError(_('The advert is too long.'))
        vals['description'] = previous if text == html2plaintext(previous) else plaintext2html(text)
        vals.update(role_channel_id=rc.id, confirmed=values.get('confirmed') is True)
        wizard = self.env['pb.hiring.board.review'].create(vals)
        if operation == 'draft':
            wizard.action_save()
        else:
            if rc.channel_id.key not in BOARD_PROVIDERS:
                raise UserError(_('Post this advert on the board, then record its live link here.'))
            if operation == 'publish':
                wizard.action_submit()
            else:
                wizard.action_update()
        return self.job_board_detail(req.id)

    @api.model
    def connection_save(self, provider, values):
        if provider == 'linkedin' and isinstance(values, dict) and 'organization_id' in values:
            values = dict(values)
            raw = str(values['organization_id'] or '').strip()
            match = re.fullmatch(r'(?:urn:li:organization:)?(\d+)', raw) or re.fullmatch(
                r'https://(?:www\.)?linkedin\.com/company/(\d+)(?:/admin/dashboard)?/?', raw)
            if not match:
                raise UserError(_('Enter the numeric LinkedIn company ID or its company admin page URL.'))
            values['organization_id'] = 'urn:li:organization:' + match[1]
        return super().connection_save(provider, values)

    @api.model
    def connection_overview(self):
        result = super().connection_overview()
        for card in result['cards']:
            if card['key'] not in ('linkedin', 'seek'):
                continue
            conn = self.env['pb.hiring.connection'].sudo()._for_company(card['key'], self.env.company)
            card.update(platform_ready=False, platform_note=_('Save your company details first. Payobook then checks partner access for your tenant.'))
            if conn:
                card.update(conn._workspace_setup_status())
        return result


class JobBoardSetupStatus(models.Model):
    _inherit = 'pb.hiring.connection'

    def _workspace_setup_status(self):
        self.ensure_one()
        try:
            self._partner_config()
            return dict(platform_ready=True, platform_note=_('Payobook partner access is configured for this company and environment.'))
        except UserError as exc:
            return dict(platform_ready=False, platform_note=str(exc))

    def _card(self):
        result = super()._card()
        if self.provider in ('linkedin', 'seek'):
            result.update(self._workspace_setup_status())
        return result
