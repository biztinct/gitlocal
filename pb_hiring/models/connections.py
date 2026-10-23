"""Company-scoped hiring setup; readiness is backed by an actual check."""
import json
import secrets
from datetime import timedelta
from urllib.parse import urlsplit

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services.connection_crypto import encrypt, decrypt


PROVIDERS = [
    ('documenso', 'Offer signing'), ('cv', 'CV extraction'),
    ('google', 'Google Calendar'), ('microsoft', 'Microsoft Outlook'),
    ('whatsapp', 'WhatsApp reminders'), ('email', 'Recruitment email'),
]

# Labels and prerequisites are shared by the setup UI and validation.
SPECS = {
    'documenso': dict(description='Send offers for signature and file the completed copy automatically.',
        help='Run Documenso on a separate HTTPS service. Create a team API key and a webhook secret. Prepare an offer draft before sending it.',
        fields=[('url', 'Service URL', False), ('api_key', 'Team API key', True), ('webhook_secret', 'Webhook secret', True)]),
    'cv': dict(description='Read PDF, Word and scanned CVs, then review extracted skills and experience.',
        help='Deploy the Payobook CV service with Docling and spaCy on a separate host. Enter its HTTPS address and service key.',
        fields=[('url', 'CV service URL', False), ('api_key', 'Service key', True)]),
    'google': dict(description='Find a time when the whole panel is available. Keep interviews in Google Calendar.',
        help='An administrator configures the Google OAuth app in Calendar settings. Each organiser connects their calendar. Panel calendars must be shared with that organiser.', fields=[]),
    'microsoft': dict(description='Check Outlook availability and synchronise interview calendar entries.',
        help='An administrator configures the Microsoft OAuth app in Calendar settings. Each organiser connects their account; tenant consent and calendar access are required.', fields=[]),
    'whatsapp': dict(description='Send approved interview reminder templates to candidates who opt in.',
        help='Use a verified Meta WhatsApp Business number and approved utility template. The template body takes candidate name, role, interview time and joining/location details, in that order. Provider charges apply.',
        fields=[('phone_id', 'Phone number ID', False), ('waba_id', 'WhatsApp business account ID', False), ('version', 'Graph API version', False), ('template', 'Approved template name', False), ('language', 'Template language code', False), ('api_key', 'System user access token', True), ('app_secret', 'Meta app secret', True), ('verify_token', 'Webhook verification token', True)]),
    'email': dict(description='Use the existing outgoing email connection and recruitment templates.',
        help='An administrator verifies the outgoing mail server, sender domain and reply-to. A connection test does not prove inbox delivery. Enable candidate emails only after a controlled delivery test.', fields=[]),
}


class HiringConnection(models.Model):
    _name = 'pb.hiring.connection'
    _description = 'Hiring connection'
    _rec_name = 'provider'

    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company, index=True)
    provider = fields.Selection(PROVIDERS, required=True)
    settings = fields.Json(default=dict, groups='base.group_system')
    credentials = fields.Text(groups='base.group_system', copy=False)
    webhook_key = fields.Char(default=lambda s: secrets.token_urlsafe(32), groups='base.group_system', copy=False)
    enabled = fields.Boolean(default=False)
    checked_at = fields.Datetime(readonly=True)
    check_ok = fields.Boolean(readonly=True)
    check_note = fields.Char(readonly=True)
    _company_provider = models.Constraint('unique(company_id, provider)', 'One connection per provider and company.')

    def _secret(self, key):
        self.ensure_one()
        return json.loads(decrypt(self.env, self.sudo().credentials)).get(key, '')

    def _config(self):
        self.ensure_one()
        return self.sudo().settings or {}

    @api.model
    def _for_company(self, provider, company):
        return self.sudo().search([('provider', '=', provider), ('company_id', '=', company.id)], limit=1)

    def _ready(self):
        self.ensure_one()
        if not self.enabled or not self.check_ok:
            raise UserError(_('Complete and check this connection in Hiring connections first.'))

    def _http(self, method, path, **kwargs):
        """URLs are saved by a hiring administrator, never from a webhook."""
        self.ensure_one()
        url = self._config().get('url', '').rstrip('/')
        if not url:
            raise UserError(_('Enter the service address first.'))
        headers = dict(kwargs.pop('headers', {}))
        headers['Authorization'] = 'Bearer ' + self._secret('api_key')
        try:
            response = requests.request(method, url + path, headers=headers,
                timeout=(5, 45), allow_redirects=False, **kwargs)
            if response.status_code >= 300:
                raise UserError(_('The service refused the request (HTTP %s). Check the connection and account permissions.', response.status_code))
            if len(response.content) > 15 * 1024 * 1024:
                raise UserError(_('The service response is too large.'))
            return response
        except requests.RequestException:
            raise UserError(_('The service could not be reached. Check its address and try again.')) from None

    def _check(self):
        self.ensure_one()
        cfg = self._config()
        for key, label, secret in SPECS[self.provider]['fields']:
            if not (self._secret(key) if secret else cfg.get(key)):
                raise UserError(_('Complete %s before checking.', label))
        if self.provider == 'documenso':
            data = self._http('GET', '/api/v2/envelope', params={'page': 1, 'perPage': 1}).json()
            if not isinstance(data, dict) or not isinstance(data.get('data'), list):
                raise UserError(_('Unexpected response from Documenso.'))
            return _('API access verified. Review a draft envelope and its signature fields before sending an offer.')
        if self.provider == 'cv':
            data = self._http('GET', '/health').json()
            if data.get('contract') != 'payobook-cv-v1' or not data.get('ready'):
                raise UserError(_('The CV service has not loaded Docling and spaCy yet.'))
            return _('Docling and spaCy are ready. Test a representative CV from a candidate record.')
        if self.provider in ('google', 'microsoft'):
            self.env['pb.hiring.booking']._provider_busy(self.provider, self.env.user,
                [self.env.user.email], fields.Datetime.now(), fields.Datetime.now() + timedelta(hours=1))
            return _('Your calendar availability was read successfully. Other organisers connect their own accounts.')
        if self.provider == 'whatsapp':
            return self._check_whatsapp()
        servers = self.env['ir.mail_server'].sudo().search([('active', '=', True)])
        if not servers:
            raise UserError(_('No outgoing email server is configured. Ask the administrator to connect it.'))
        # This check deliberately does not send email to anyone.
        for server in servers:
            smtp = server.connect()
            smtp.quit()
        return _('Outgoing server connection passed. Sender verification and controlled inbox delivery still need checking.')

    def _card(self):
        self.ensure_one()
        cfg = self._config()
        return dict(key=self.provider, title=dict(PROVIDERS)[self.provider],
            **{k: v for k, v in SPECS[self.provider].items() if k != 'fields'},
            fields=[dict(key=k, label=l, secret=s, value='' if s else cfg.get(k, ''),
                         stored=bool(self._secret(k)) if s else False) for k, l, s in SPECS[self.provider]['fields']],
            enabled=self.enabled, checked_at=str(self.checked_at or ''),
            status='Enabled' if self.enabled and self.check_ok else ('Checked' if self.check_ok else 'Setup needed'),
            note=self.check_note or '', check_ok=self.check_ok,
            callback=self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
                     + '/hiring/connect/' + self.provider + '/' + self.sudo().webhook_key)


class HiringConnectionsFacade(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def get_setup(self):
        result = super().get_setup()
        result['cards'].insert(0, dict(key='connections', title=_('Hiring connections'), icon='link',
            status=_('Guided setup for signing, CVs, calendars and reminders.'), live=False,
            action={'type': 'ir.actions.client', 'tag': 'pb_hiring_connections', 'name': _('Hiring connections')}))
        return result

    @api.model
    def connection_overview(self):
        self._require_write()
        Conn = self.env['pb.hiring.connection'].sudo()
        cards = []
        for key, title in PROVIDERS:
            row = Conn._for_company(key, self.env.company)
            if row:
                cards.append(row._card())
            else:
                cards.append(dict(key=key, title=title, description=SPECS[key]['description'], help=SPECS[key]['help'],
                    fields=[dict(key=k, label=l, secret=s, value='', stored=False) for k,l,s in SPECS[key]['fields']],
                    enabled=False, status='Setup needed', note='', check_ok=False, checked_at='', callback='Save setup to generate the callback address.'))
        return dict(company=self.env.company.name, cards=cards)

    @api.model
    def connection_save(self, provider, values):
        self._require_write()
        if provider not in SPECS or not isinstance(values, dict):
            raise UserError(_('Choose a supported connection.'))
        Conn = self.env['pb.hiring.connection'].sudo()
        row = Conn._for_company(provider, self.env.company)
        if not row:
            row = Conn.create({'provider': provider, 'company_id': self.env.company.id})
        cfg = dict(row._config())
        secret_values = json.loads(decrypt(self.env, row.credentials))
        for key, label, secret in SPECS[provider]['fields']:
            if key not in values:
                continue
            value = str(values[key] or '').strip()
            if len(value) > 4096:
                raise ValidationError(_('The value for %s is too long.', label))
            if secret:
                if value:
                    secret_values[key] = value
            else:
                cfg[key] = value
        if cfg.get('url'):
            parsed = urlsplit(cfg['url'])
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValidationError(_('Use an HTTPS service address without credentials, query parameters or fragments.'))
        row.write({'settings': cfg, 'credentials': encrypt(self.env, json.dumps(secret_values)),
                   'enabled': False, 'check_ok': False, 'checked_at': False, 'check_note': _('Saved. Run the connection check next.')})
        return row._card()

    @api.model
    def connection_check(self, provider):
        self._require_write()
        row = self.env['pb.hiring.connection']._for_company(provider, self.env.company)
        if not row:
            self.connection_save(provider, {})
            row = self.env['pb.hiring.connection']._for_company(provider, self.env.company)
        try:
            note = row._check()
            ok = True
        except Exception as exc:
            # Provider bodies and credentials are never exposed or logged.
            note = str(exc) if isinstance(exc, UserError) else _('The connection check could not complete. Ask the administrator to verify the service, credentials and required SDK installation.')
            ok = False
        row.write({'check_ok': ok, 'checked_at': fields.Datetime.now(), 'check_note': note,
                   'enabled': row.enabled and ok})
        return row._card()

    @api.model
    def connection_enable(self, provider, enabled):
        self._require_write()
        row = self.env['pb.hiring.connection']._for_company(provider, self.env.company)
        if not row or (enabled and not row.check_ok):
            raise UserError(_('Run a successful connection check before enabling this feature.'))
        row.write({'enabled': bool(enabled)})
        return row._card()
