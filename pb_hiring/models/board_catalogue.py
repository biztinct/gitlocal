"""Country catalogue, guided account onboarding and explicitly selected job feeds."""
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlsplit

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

try:  # WHITELABEL 2026-10-31 — the tenant's own name for the product
    from odoo.addons.biz_debrand.models.brand import rebrand_payload
except Exception:  # pragma: no cover — biz_debrand absent on this build
    def rebrand_payload(env, value):
        return value
from odoo.tools import html2plaintext

from .channels_p7 import utm_record
from ..services.board_catalogue import BOARDS, CATALOGUE, COUNTRIES, FEED_KEYS, onboarding_request
from ..services.job_boards import BOARD_PROVIDERS

STAGES = [('not_started', 'Not started'), ('requested', 'Request sent'),
          ('in_review', 'Discussing with provider'), ('response_received', 'Provider response received')]


class CatalogueChannel(models.Model):
    _inherit = 'pb.hiring.channel'

    onboarding_stage = fields.Selection(STAGES, default='not_started', copy=False)
    onboarding_note = fields.Text(copy=False)
    feed_enabled = fields.Boolean(default=False, copy=False)
    feed_token = fields.Char(copy=False, readonly=True, groups='pb_hiring.group_hiring_manager')

    @api.model
    def _ensure_for(self, company):
        made = super()._ensure_for(company)
        Channel = self.sudo().with_context(active_test=False)
        have = set(Channel.search([('company_id', '=', company.id)]).mapped('key'))
        for index, spec in enumerate(BOARDS):
            if spec['key'] in have:
                continue
            countries = self.env['res.country'].sudo().search([('code', 'in', spec['countries'])])
            Channel.create(dict(name=spec['name'], key=spec['key'], kind='board',
                                company_id=company.id,
                                utm_source_id=utm_record(self.env, 'utm.source', spec['name']).id,
                                every_country=not spec['countries'], country_ids=[(6, 0, countries.ids)],
                                posting_url_hint=spec['url'], sequence=100 + index))
            made += 1
        return made

    @api.constrains('feed_enabled', 'key')
    def _check_feed_provider(self):
        if any(ch.feed_enabled and ch.key not in FEED_KEYS for ch in self):
            raise ValidationError(_('This provider has no supported feed format.'))

    def _feed_url(self, website):
        self.ensure_one()
        parts = urlsplit(website.domain or '')
        if (website.company_id != self.company_id or parts.scheme != 'https'
                or not parts.hostname or parts.username or parts.password or parts.query
                or parts.fragment or parts.path not in ('', '/')):
            raise UserError(_('Set a dedicated HTTPS domain on this company’s website before sharing a feed.'))
        return '%s/hiring/job-feed/%s/%s/%s.xml' % (
            website.domain.rstrip('/'), website.id, self.id, self.feed_token)

    def _feed_items(self, website):
        self.ensure_one()
        if (not self.active or not self.feed_enabled or self.key not in FEED_KEYS
                or website.company_id != self.company_id):
            return []
        self._feed_url(website)  # Enforce a company-owned canonical domain.
        rows = self.env['pb.hiring.role.channel'].sudo().search([
            ('channel_id', '=', self.id), ('company_id', '=', self.company_id.id),
            ('feed_selected', '=', True), ('feed_expires', '>=', fields.Date.today())], order='id')
        items = []
        for row in rows:
            req, job = row.requisition_id, row.requisition_id.job_id
            if (req.is_confidential or req.state != 'open' or not self._applies_to(req)
                    or not job.pb_hiring_accepts_applications(website)
                    or not html2plaintext(job.website_description or '').strip()):
                continue
            country = req.country_id or req.company_id.country_id
            if not country or not (req.location or job.address_id.city):
                continue
            base = website.domain.rstrip('/')
            query = urlencode({'utm_source': self.utm_source_id.name, 'utm_medium': 'website'})
            items.append(dict(
                id='%s-%s' % (website.id, row.id), title=job.name,
                url='%s%s?%s' % (base, job.website_url, query),
                apply_url='%s/jobs/apply/%s?%s' % (base, job.id, query),
                city=req.location or job.address_id.city, country=country.name,
                company=req.company_id.name, description=str(job.website_description),
                published=job.published_date or row.feed_started.date(),
                updated=(job.write_date or row.feed_started).date(), expires=row.feed_expires,
            ))
        return items


class CatalogueRoleChannel(models.Model):
    _inherit = 'pb.hiring.role.channel'

    feed_selected = fields.Boolean(default=False, copy=False, readonly=True)
    feed_started = fields.Datetime(copy=False, readonly=True)
    feed_expires = fields.Date(copy=False, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and any(k.startswith('feed_') for vals in vals_list for k in vals):
            raise AccessError(_('Use the job-board feed controls.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and any(k.startswith('feed_') for k in vals):
            raise AccessError(_('Use the job-board feed controls.'))
        return super().write(vals)


class CatalogueWorkspace(models.AbstractModel):
    _inherit = 'pb.hiring'

    def _catalogue_channel(self, key):
        if not self._can_recruit():
            raise AccessError(_('Job boards are available to the hiring team.'))
        if key not in CATALOGUE:
            raise UserError(_('Choose a supported job board.'))
        Channel = self.env['pb.hiring.channel'].sudo().with_context(active_test=False)
        Channel._ensure_for(self.env.company)
        return Channel.search([('company_id', '=', self.env.company.id), ('key', '=', key)], limit=1)

    @api.model
    def job_board_catalogue(self):
        if not self._can_recruit():
            raise AccessError(_('Job boards are available to the hiring team.'))
        Channel = self.env['pb.hiring.channel'].sudo().with_context(active_test=False)
        Channel._ensure_for(self.env.company)
        channels = {ch.key: ch for ch in Channel.search([('company_id', '=', self.env.company.id)])}
        rows = []
        for spec in BOARDS:
            ch = channels[spec['key']]
            ready = False
            if spec['route'] == 'api':
                ready = self._workspace_connection(BOARD_PROVIDERS[spec['key']], self.env.company)['ready']
            status = ('Connected' if ready else 'Connection setup required') if spec['route'] == 'api' else (
                ('Feed enabled' if ch.feed_enabled else 'Feed setup required') if spec['route'] == 'feed' else
                'Careers-page discovery' if spec['route'] == 'discovery' else 'Payobook integration pending')
            rows.append(dict(spec, enabled=ch.active, status=status, ready=ready,
                             country_label=', '.join(COUNTRIES[c] for c in spec['countries']) or 'All countries',
                             onboarding_stage=ch.onboarding_stage or 'not_started',
                             onboarding_label=dict(STAGES)[ch.onboarding_stage or 'not_started']))
        # The catalogue's guidance talks about the platform by name; a
        # white-label tenant reads its own (WHITELABEL 2026-10-31). The
        # company name is the tenant's own data and is added AFTER the walk.
        out = rebrand_payload(self.env, dict(
            boards=rows, countries=[dict(code=k, name=v) for k, v in COUNTRIES.items()],
            can_setup=self._can_write()))
        out['company'] = self.env.company.name
        return out

    @api.model
    def job_board_guide(self, key):
        """`_job_board_guide_raw` with the product named as THIS tenant knows
        it: the board guidance and the provider letter talk about the
        platform by name (WHITELABEL 2026-10-31)."""
        return rebrand_payload(self.env, self._job_board_guide_raw(key))

    @api.model
    def _job_board_guide_raw(self, key):
        ch = self._catalogue_channel(key)
        spec = CATALOGUE[key]
        result = dict(spec, onboarding_stage=ch.onboarding_stage or 'not_started',
                      onboarding_note=ch.onboarding_note or '', enabled=ch.active,
                      feed_enabled=ch.feed_enabled, feeds=[], can_setup=self._can_write(),
                      request_text=onboarding_request(spec, self.env.company.name))
        if self._can_write() and key in FEED_KEYS and ch.feed_enabled:
            sites = self.env['website'].sudo().search([('company_id', '=', self.env.company.id)])
            for site in sites:
                try:
                    result['feeds'].append(dict(id=site.id, name=site.name, url=ch._feed_url(site),
                                               count=len(ch._feed_items(site)), note=''))
                except UserError as exc:
                    result['feeds'].append(dict(id=site.id, name=site.name, url='', count=0, note=str(exc)))
        return result

    @api.model
    def job_board_setup(self, key, values):
        self._require_write()
        ch = self._catalogue_channel(key)
        if not isinstance(values, dict) or set(values) - {'enabled', 'onboarding_stage', 'onboarding_note', 'feed_enabled'}:
            raise UserError(_('Choose valid setup fields.'))
        vals = {}
        if 'enabled' in values:
            if type(values['enabled']) is not bool:
                raise UserError(_('Choose whether the board is enabled.'))
            vals['active'] = values['enabled']
        if 'onboarding_stage' in values:
            if values['onboarding_stage'] not in dict(STAGES):
                raise UserError(_('Choose a valid onboarding stage.'))
            vals['onboarding_stage'] = values['onboarding_stage']
        if 'onboarding_note' in values:
            vals['onboarding_note'] = str(values['onboarding_note'] or '').strip()[:2000]
        if 'feed_enabled' in values:
            if key not in FEED_KEYS or type(values['feed_enabled']) is not bool:
                raise UserError(_('This board does not support feed setup.'))
            vals['feed_enabled'] = values['feed_enabled']
            if values['feed_enabled'] and (not ch.feed_token or not ch.feed_enabled):
                vals['feed_token'] = secrets.token_urlsafe(32)
        ch.write(vals)
        return self.job_board_guide(key)

    @api.model
    def job_board_detail(self, role_id):
        """`_job_board_detail_raw`, product named as this tenant knows it."""
        return rebrand_payload(self.env, self._job_board_detail_raw(role_id))

    @api.model
    def _job_board_detail_raw(self, role_id):
        panel = super().job_board_detail(role_id)
        req = self._workspace_role(role_id)
        panel['feed_description'] = html2plaintext(req.job_id.website_description or '')
        for row in panel['rows']:
            spec = CATALOGUE.get(row['key'])
            if not spec:
                continue
            rc = self.env['pb.hiring.role.channel'].sudo().browse(row['id'])
            row.update(route=spec['route'], audience=spec['audience'], feed_ready=bool(rc.channel_id.feed_enabled),
                       feed_selected=rc.feed_selected, feed_expires=str(rc.feed_expires or ''),
                       feed_current=bool(rc.feed_selected and rc.feed_expires and rc.feed_expires >= fields.Date.today()
                                         and rc.channel_id.feed_enabled and row['applies'] and panel['on_page']
                                         and panel['state'] == 'open' and not panel['confidential']))
            if spec['route'] == 'partner':
                row['connection']['note'] = _('Automatic publishing awaits Payobook partner onboarding. Tracked manual posting is available.')
            elif spec['route'] == 'feed':
                row['connection']['note'] = _('Share selected public jobs through an approved feed. Publication is confirmed separately.')
            elif spec['route'] == 'discovery':
                row['connection']['note'] = _('Google discovers your published careers pages. Search visibility is not guaranteed.')
        return panel

    @api.model
    def job_board_feed_select(self, channel_id, selected, expires=None):
        rc = self._p7_row({'role_channel_id': channel_id})
        req = self._workspace_role(rc.requisition_id.id)
        if type(selected) is not bool or rc.channel_id.key not in FEED_KEYS:
            raise UserError(_('Choose a supported feed action.'))
        if selected:
            ch = rc.channel_id
            if (not ch.feed_enabled or not ch._applies_to(req) or req.is_confidential
                    or req.state != 'open' or not req.job_id.is_published):
                raise UserError(_('Enable the feed and publish an open, nonconfidential role first.'))
            try:
                expiry = fields.Date.to_date(expires)
            except (ValueError, TypeError):
                expiry = None
            if not expiry or not fields.Date.today() <= expiry <= fields.Date.today() + timedelta(days=90):
                raise UserError(_('Choose an expiry date from today through the next 90 days.'))
            sites = self.env['website'].sudo().search([('company_id', '=', req.company_id.id)])
            eligible = sites.filtered(lambda w: req.job_id.pb_hiring_accepts_applications(w))
            if (not eligible or not html2plaintext(req.job_id.website_description or '').strip() or not (req.location or req.job_id.address_id.city)
                    or not (req.country_id or req.company_id.country_id)):
                raise UserError(_('Complete the published careers advert, location and company website first.'))
            ch._feed_url(eligible[0])
            rc._ensure_tracker()
            rc.write(dict(feed_selected=True, feed_expires=expiry,
                          feed_started=rc.feed_started or fields.Datetime.now()))
        else:
            rc.write({'feed_selected': False})
        return self.job_board_detail(req.id)
