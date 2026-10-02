# -*- coding: utf-8 -*-
"""RECRUIT P7 (G-20) — where a role goes, and a link per place.

THE LINK IS HOW WE KNOW WHERE SOMEBODY CAME FROM. Every channel a role can go
to — the careers page, LinkedIn, JobStreet, VietnamWorks, employee referrals,
agencies — gets its own tracked link, built on the stock job tracker
(`hr.recruitment.source`), whose `url` is the job page with
`utm_source=<the channel's source>`. The apply flow already records the utm
the visitor arrived with (`controllers/application.py`, the session touch on
`/jobs`, `/jobs/<job>`, `/jobs/apply/<job>`), so an application through the
LinkedIn link lands with Source = LinkedIn even though the posting itself was
pasted onto LinkedIn by hand.

NO BOARD IS CONNECTED, AND THE SCREEN SAYS SO. This build has no JobStreet,
VietnamWorks or LinkedIn API (ruling D12 kept outside services off; Rize holds
the subscriptions). What ships is the SEAM — `pb.hiring.channel.connector` —
with two working connectors: `manual` (the recruiter pastes the advert and
presses "Mark as posted") and `email_pack` (the advert is emailed to a board's
contact address). A later connector registers one more key; nothing on the
panel changes.

THE LATER CONNECTOR CONTRACT (also written in the ledger, RC83):
  * a model `pb.hiring.connector.<key>` inheriting `pb.hiring.channel.connector`
    and implementing `post(role_channel, **values) -> {ok, external_url, note}`,
    `status(role_channel) -> {state, note}`, `close(role_channel) -> {ok, note}`;
  * its key added to `_registry()` and to `CONNECTORS` (the channel's selection);
  * outbound HTTP through `_http(...)` only: 10-second timeout, no retries, and
    a failure says "Could not reach <board> — nothing was posted. Paste the
    advert by hand and press Mark as posted.";
  * credentials in `ir.config_parameter` `pb_hiring.<key>.api_key`, edited only
    through a settings field carrying `groups='base.group_system'`.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import email_normalize, html2plaintext

from .hiring_common import P_PLATFORM_MAIL, as_id, flag

_logger = logging.getLogger(__name__)

CHANNEL_KINDS = [
    ('careers', 'Careers page'),
    ('board', 'Job board'),
    ('social', 'Social network'),
    ('referral', 'Employee referrals'),
    ('agency', 'Agencies'),
]
#: The connector a channel posts through. Only the first two exist on this
#: build; a board's own API is added as a third key when the subscription and
#: the API access exist (owner item).
CONNECTORS = [
    ('manual', 'By hand (paste the advert, then Mark as posted)'),
    ('email_pack', 'By email to the board'),
]
ROLE_CHANNEL_STATES = [
    ('not_posted', 'Not posted yet'),
    ('posted', 'Posted'),
    ('closed', 'Taken down'),
]
#: The seed, per company. `utm` is the source NAME (matched case-insensitively
#: to what the database already has); `countries` are ISO codes, empty = every
#: country.
SEED = [
    # key, name, kind, utm source, countries, hint, sequence
    ('careers', 'Careers page', 'careers', 'Careers page', (),
     'Your own careers page. Publishing the role puts it there with the advert.', 10),
    ('linkedin', 'LinkedIn', 'social', 'LinkedIn', (),
     'Paste the advert into a LinkedIn job post or a company update, with this link.', 20),
    ('jobstreet', 'JobStreet (Indonesia)', 'board', 'JobStreet', ('ID',),
     'Paste the advert into your JobStreet employer account, with this link as the way to apply.', 30),
    ('vietnamworks', 'VietnamWorks (Vietnam)', 'board', 'VietnamWorks', ('VN',),
     'Paste the advert into your VietnamWorks employer account, with this link as the way to apply.', 40),
    ('referral', 'Employee referrals', 'referral', 'Referral', (),
     'Everybody here can put somebody forward on their referral page.', 50),
    ('agency', 'Agencies', 'agency', 'Agency', (),
     'Agencies see the role on their own portal and put people forward there.', 60),
]
#: Channels whose link is a stock job tracker (the job page + utm).
TRACKED_KINDS = ('careers', 'board', 'social')
ICONS = {'careers': 'globe', 'board': 'briefcase', 'social': 'share2',
         'referral': 'users', 'agency': 'building'}
#: Outbound HTTP for a later connector: seconds, no retries.
HTTP_TIMEOUT = 10


def utm_record(env, model, name):
    """The utm row for `name`, matched CASE-INSENSITIVELY, the oldest first
    (the seeded row wins over a later lower-case copy). Created with the name
    as given only when nothing matches — so `linkedin`, `LinkedIn` and
    `LINKEDIN` are all the one seeded LinkedIn."""
    name = (name or '').strip()[:200]
    if not name:
        return env[model].sudo().browse()
    Model = env[model].sudo().with_context(active_test=False)
    rec = Model.search([('name', '=ilike', name)], order='id', limit=1)
    if not rec:
        rec = Model.create({'name': name})
    return rec


class PbHiringChannel(models.Model):
    _name = 'pb.hiring.channel'
    _description = 'Where a role can be published'
    _order = 'sequence, id'

    name = fields.Char(string='Channel', required=True)
    key = fields.Char(string='Key', required=True, index=True,
                      help='careers, linkedin, jobstreet, vietnamworks, referral, '
                           'agency, or a company\'s own (custom_<n>).')
    kind = fields.Selection(CHANNEL_KINDS, string='Kind', required=True,
                            default='board')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 index=True, ondelete='cascade',
                                 default=lambda self: self.env.company)
    utm_source_id = fields.Many2one('utm.source', string='Source it tags',
                                    required=True, ondelete='restrict')
    utm_medium_id = fields.Many2one('utm.medium', string='Medium',
                                    ondelete='set null')
    contact_email = fields.Char(
        string='Email contact',
        help='Where "Send the advert" emails it. Leave empty for a board you '
             'post on yourself.')
    platform_id = fields.Many2one('hr.job.platform', string='Job board record',
                                  ondelete='set null', readonly=True)
    every_country = fields.Boolean(
        string='Every country', default=False,
        help='Offered for roles in any country. Off: only the countries listed '
             '(none listed = offered nowhere).')
    country_ids = fields.Many2many(
        'res.country', 'pb_hiring_channel_country_rel', 'channel_id', 'country_id',
        string='Countries', help='Offered for roles in these countries.')
    connector = fields.Selection(CONNECTORS, string='How it is posted',
                                 required=True, default='manual')
    posting_url_hint = fields.Char(string='Where to paste it')
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _pb_key_company_uniq = models.Constraint(
        'unique(company_id, key)', 'Each channel appears once per company.')

    # ------------------------------------------------------------- the seed
    @api.model
    def _seed_all(self):
        """Every company gets the six channels; idempotent (data `<function>`
        runs it on every upgrade, and the panel runs it for a company made
        later)."""
        companies = self.env['res.company'].sudo().search([])
        made = 0
        for company in companies:
            made += self._ensure_for(company)
        # JobStreet / VietnamWorks / Careers page / Agency exist once even on
        # a database where nothing has ever been published.
        for _key, _n, _k, utm, *_rest in SEED:
            utm_record(self.env, 'utm.source', utm)
        return made

    @api.model
    def _ensure_for(self, company):
        company = company.sudo() if company else self.env.company.sudo()
        Channel = self.sudo().with_context(active_test=False)
        have = set(Channel.search([('company_id', '=', company.id)]).mapped('key'))
        website = self.env['utm.medium'].sudo()._fetch_or_create_utm_medium('website')
        made = 0
        for key, name, kind, utm, codes, hint, seq in SEED:
            if key in have:
                continue
            countries = self.env['res.country'].sudo().search([('code', 'in', list(codes))]) \
                if codes else self.env['res.country']
            Channel.create({
                'name': name, 'key': key, 'kind': kind, 'company_id': company.id,
                'utm_source_id': utm_record(self.env, 'utm.source', utm).id,
                'utm_medium_id': website.id, 'country_ids': [(6, 0, countries.ids)],
                'every_country': not codes,
                'connector': 'manual', 'posting_url_hint': hint, 'sequence': seq,
            })
            made += 1
        return made

    # ------------------------------------------------------------- the rules
    def _applies_to(self, req):
        """Offered for this role: active, same company, its country listed (or
        no country listed)."""
        self.ensure_one()
        if not self.active or (req.company_id and self.company_id != req.company_id):
            return False
        if self.every_country:
            return True
        country = req.country_id or req.company_id.partner_id.country_id
        return bool(country) and country in self.country_ids

    @api.model
    def _for_company(self, company):
        return self.sudo().search([('company_id', '=', company.id)], order='sequence, id')

    @api.model
    def _for_source(self, company, source):
        """The channel a utm source belongs to, in one company."""
        if not source or not company:
            return self.browse()
        return self.sudo().search([('company_id', '=', company.id),
                                   ('utm_source_id', '=', source.id)], limit=1)

    # ------------------------------------------------------- the email contact
    def _set_contact(self, email):
        """The contact address, and the job board record the advert pack
        needs (`pb.hiring.posting` hangs off `hr.job.platform`, whose email is
        unique: an address another channel already uses is linked, never
        doubled)."""
        self.ensure_one()
        raw = (email or '').strip()
        if not raw:
            self.sudo().write({'contact_email': False, 'platform_id': False,
                               'connector': 'manual'})
            return True
        address = email_normalize(raw)
        if not address:
            raise UserError(_("\"%s\" does not look like an email address.", raw))
        Platform = self.env['hr.job.platform'].sudo()
        platform = Platform.search([('email', '=ilike', address)], limit=1) or \
            Platform.create({'name': self.name, 'email': address})
        self.sudo().write({'contact_email': address, 'platform_id': platform.id,
                           'connector': 'email_pack'})
        return True

    def _payload(self, countries=None):
        self.ensure_one()
        return {
            'id': self.id, 'key': self.key, 'name': self.name or '',
            'kind': self.kind, 'kind_label': dict(CHANNEL_KINDS).get(self.kind, ''),
            'icon': ICONS.get(self.kind, 'link'), 'active': bool(self.active),
            'contact_email': self.contact_email or '',
            'hint': self.posting_url_hint or '',
            'source': self.utm_source_id.name or '',
            'connector': self.connector,
            'connector_label': dict(CONNECTORS).get(self.connector, ''),
            'every_country': bool(self.every_country),
            'country_ids': self.country_ids.ids,
            'countries': ', '.join(self.country_ids.mapped('name')),
            'can_contact': self.kind in ('board', 'social'),
        }


class PbHiringRoleChannel(models.Model):
    _name = 'pb.hiring.role.channel'
    _description = 'A role on one channel'
    _order = 'sequence, id'

    requisition_id = fields.Many2one('pb.hiring.requisition', string='Role',
                                     required=True, index=True, ondelete='cascade')
    channel_id = fields.Many2one('pb.hiring.channel', string='Channel',
                                 required=True, index=True, ondelete='cascade')
    sequence = fields.Integer(related='channel_id.sequence', store=True)
    company_id = fields.Many2one('res.company', related='requisition_id.company_id',
                                 store=True, index=True)
    source_id = fields.Many2one('hr.recruitment.source', string='Tracked link',
                                ondelete='set null')
    state = fields.Selection(ROLE_CHANNEL_STATES, string='Where it is',
                             default='not_posted', required=True)
    posted_on = fields.Date(string='Posted on')
    posted_by = fields.Many2one('res.users', string='Posted by', ondelete='set null')
    external_url = fields.Char(string='The live posting')
    closed_on = fields.Date(string='Taken down on')
    posting_id = fields.Many2one('pb.hiring.posting', string='Advert email',
                                 ondelete='set null')
    sent_on = fields.Datetime(string='Advert emailed on')
    note = fields.Char(string='Note')

    _pb_role_channel_uniq = models.Constraint(
        'unique(requisition_id, channel_id)', 'A role is on each channel once.')

    # ------------------------------------------------------------- the link
    def _ensure_tracker(self):
        """The stock job tracker for this channel on this role's job: found
        (the Trackers tab may already hold one) or made, never doubled."""
        self.ensure_one()
        rc = self.sudo()
        channel = rc.channel_id
        job = rc.requisition_id.job_id
        if channel.kind not in TRACKED_KINDS or not job:
            return rc.source_id
        if rc.source_id and rc.source_id.job_id == job \
                and rc.source_id.source_id == channel.utm_source_id:
            return rc.source_id
        Source = self.env['hr.recruitment.source'].sudo()
        tracker = Source.search([('job_id', '=', job.id),
                                 ('source_id', '=', channel.utm_source_id.id)], limit=1)
        if not tracker:
            campaign = self.env.ref('hr_recruitment.utm_campaign_job', raise_if_not_found=False)
            tracker = Source.create({
                'job_id': job.id, 'source_id': channel.utm_source_id.id,
                'medium_id': (channel.utm_medium_id or self.env['utm.medium']
                              ._fetch_or_create_utm_medium('website')).id,
                'campaign_id': campaign.id if campaign else False,
            })
        rc.write({'source_id': tracker.id})
        return tracker

    def _link(self):
        self.ensure_one()
        rc = self.sudo()
        kind = rc.channel_id.kind
        req = rc.requisition_id
        if kind == 'referral':
            base = req.get_base_url().rstrip('/')
            return '%s/my/refer?role=%s' % (base, req.id)
        if kind in TRACKED_KINDS:
            tracker = rc._ensure_tracker()
            return tracker.url if tracker else ''
        return ''

    def _advert_text(self, link):
        """The advert as plain text with this channel's link as the way to
        apply — for pasting onto a board by hand."""
        self.ensure_one()
        req = self.requisition_id.sudo()
        job = req.job_id
        if not job:
            return ''
        Posting = self.env['pb.hiring.posting'].sudo().with_context(pb_pack_url=link)
        subject, body = Posting._render_pack(req, job, self.channel_id.platform_id)
        return '%s\n\n%s' % (subject, html2plaintext(body or '').strip())


class PbHiringChannelConnector(models.AbstractModel):
    """THE SEAM. One registry, one interface, two connectors that work today."""
    _name = 'pb.hiring.channel.connector'
    _description = 'How a role reaches a channel'

    @api.model
    def _registry(self):
        """connector key -> model. A later board's API adds its key here."""
        return {'manual': 'pb.hiring.connector.manual',
                'email_pack': 'pb.hiring.connector.email_pack'}

    @api.model
    def _get(self, key, channel_name=''):
        model = self._registry().get(key or '')
        if not model or model not in self.env:
            raise UserError(_(
                "There is no way to post to %(board)s automatically on this "
                "system yet. Paste the advert there by hand and press Mark as "
                "posted.", board=channel_name or _('this board')))
        return self.env[model]

    # The interface. Every connector answers these three.
    def post(self, role_channel, **values):
        raise NotImplementedError

    def status(self, role_channel):
        rc = role_channel.sudo()
        return {'state': rc.state,
                'note': dict(ROLE_CHANNEL_STATES).get(rc.state, '')}

    def close(self, role_channel):
        rc = role_channel.sudo()
        rc.write({'state': 'closed', 'closed_on': fields.Date.context_today(self)})
        return {'ok': True, 'note': _("%s: taken down.", rc.channel_id.name)}

    @api.model
    def _http(self, method, url, board, **kw):
        """Outbound HTTP for a later connector: ten seconds, no retries, and a
        failure that says what to do instead. Nothing on this build calls it
        yet; the test pins its error sentence."""
        import requests
        try:
            resp = requests.request(method, url, timeout=HTTP_TIMEOUT, **kw)
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            _logger.warning('pb_hiring: %s could not be reached', board, exc_info=True)
            raise UserError(_(
                "Could not reach %s — nothing was posted. Paste the advert by "
                "hand and press Mark as posted.", board)) from None


class PbHiringConnectorManual(models.AbstractModel):
    _name = 'pb.hiring.connector.manual'
    _inherit = 'pb.hiring.channel.connector'
    _description = 'Posted by hand'

    def post(self, role_channel, posted_on=None, external_url=None, **values):
        """Records the recruiter's promise: it is on that board."""
        rc = role_channel.sudo()
        url = (external_url or '').strip()[:2000]
        if url and not url.startswith(('https://', 'http://')):
            raise UserError(_("Paste the full address of the posting, starting "
                              "with https://"))
        rc.write({'state': 'posted',
                  'posted_on': fields.Date.to_date(posted_on) or fields.Date.context_today(self),
                  'posted_by': self.env.uid, 'external_url': url or False,
                  'closed_on': False})
        return {'ok': True, 'external_url': url,
                'note': _("%s marked as posted.", rc.channel_id.name)}


class PbHiringConnectorEmailPack(models.AbstractModel):
    _name = 'pb.hiring.connector.email_pack'
    _inherit = 'pb.hiring.channel.connector'
    _description = 'Advert emailed to the board'

    def post(self, role_channel, **values):
        """Email the advert pack — with THIS channel's link as the way to
        apply — to the board's contact. Needs a contact and the switch."""
        rc = role_channel.sudo()
        channel = rc.channel_id
        if not channel.contact_email or not channel.platform_id:
            raise UserError(_(
                "%s has no email contact yet. Add one in Hiring set-up → "
                "Channels, or paste the advert there yourself.", channel.name))
        if not flag(self.env, P_PLATFORM_MAIL):
            raise UserError(_(
                "Sending adverts to job boards by email is switched off. Turn "
                "it on in Hiring set-up → Channels, or copy the advert and "
                "send it yourself."))
        req = rc.requisition_id
        job = req.job_id or req._ensure_job()
        link = rc._link()
        Posting = self.env['pb.hiring.posting'].sudo().with_context(pb_pack_url=link)
        subject, body = Posting._render_pack(req, job, channel.platform_id)
        posting = Posting.search([('requisition_id', '=', req.id),
                                  ('platform_id', '=', channel.platform_id.id)], limit=1)
        vals = {'subject': subject, 'body_html': body, 'state': 'ready'}
        if posting:
            posting.write(vals)
        else:
            posting = Posting.create(dict(vals, requisition_id=req.id,
                                          platform_id=channel.platform_id.id))
        posting._send_one()
        rc.write({'posting_id': posting.id, 'sent_on': fields.Datetime.now()})
        return {'ok': True, 'external_url': '',
                'note': _("The advert went to %(board)s (%(email)s). Mark it as "
                          "posted when it is live.", board=channel.name,
                          email=channel.contact_email)}


class HiringApplicantChannel(models.Model):
    _inherit = 'hr.applicant'

    pb_channel_id = fields.Many2one('pb.hiring.channel', string='Came through',
                                    ondelete='set null', index='btree_not_null',
                                    copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        apps = super().create(vals_list)
        for app in apps:
            if app.pb_channel_id or not app.source_id:
                continue
            try:
                channel = self.env['pb.hiring.channel']._for_source(
                    app.sudo().company_id, app.source_id)
                if channel:
                    app.sudo().write({'pb_channel_id': channel.id})
            except Exception:           # noqa: BLE001 — a tag never fails an application
                _logger.warning('pb_hiring: channel tag on applicant %s failed', app.id,
                                exc_info=True)
        return apps


def merge_duplicate_sources(env):
    """`linkedin` beside `LinkedIn`: one row per name, case-insensitively.

    Keeps the seeded row (it has an xmlid) or else the oldest, points every
    column that references the others at it, then removes them. Each merge is
    its own savepoint: a table that cannot take the move keeps its row and the
    duplicate stays, logged, rather than failing the upgrade.
    """
    cr = env.cr
    cr.execute("""
        SELECT lower(name), array_agg(id ORDER BY id)
          FROM utm_source GROUP BY lower(name) HAVING count(*) > 1
    """)
    groups = cr.fetchall()
    if not groups:
        return 0
    cr.execute("""
        SELECT cl.relname, att.attname
          FROM pg_constraint con
          JOIN pg_class cl ON cl.oid = con.conrelid
          JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY(con.conkey)
         WHERE con.contype = 'f' AND con.confrelid = 'utm_source'::regclass
    """)
    refs = cr.fetchall()
    cr.execute("SELECT res_id FROM ir_model_data WHERE model = 'utm.source'")
    seeded = {r[0] for r in cr.fetchall()}
    merged = 0
    for _lname, ids in groups:
        keep = next((i for i in ids if i in seeded), ids[0])
        for dup in ids:
            if dup == keep:
                continue
            try:
                with cr.savepoint():
                    for table, column in refs:
                        cr.execute('UPDATE "%s" SET "%s" = %%s WHERE "%s" = %%s'
                                   % (table, column, column), (keep, dup))
                    cr.execute('DELETE FROM utm_source WHERE id = %s', (dup,))
                merged += 1
            except Exception:           # noqa: BLE001 — never fail the upgrade
                _logger.warning('pb_hiring: utm source %s could not be merged into %s',
                                dup, keep, exc_info=True)
    env.invalidate_all()
    return merged
