# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PbTenant(models.Model):
    _name = 'pb.tenant'
    _description = 'Payobook SaaS tenant'
    _order = 'state, name'

    name = fields.Char(required=True)
    slug = fields.Char(required=True, help="Subdomain label and database name (acme -> acme.payobook.com)")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('provisioning', 'Provisioning'),
        ('live', 'Live'),
        ('error', 'Error'),
        ('decommissioned', 'Decommissioned'),
    ], default='draft', required=True, index=True)
    admin_name = fields.Char()
    admin_email = fields.Char()
    country_code = fields.Char(size=2)
    notes = fields.Text()

    provision_step = fields.Char()
    provision_log = fields.Text(default='[]')
    last_error = fields.Text()

    # health cache (refreshed by cron / on demand)
    db_size = fields.Float(help="bytes")
    filestore_size = fields.Float(help="bytes")
    user_count = fields.Integer()
    employee_count = fields.Integer()
    last_login = fields.Datetime()
    ping_ms = fields.Integer(default=-1)
    health_state = fields.Selection([
        ('ok', 'Healthy'), ('warn', 'Warning'), ('down', 'Down'), ('unknown', 'Unknown'),
    ], default='unknown')
    health_checked = fields.Datetime()

    # TLS state, read off the certificate nginx actually serves for this host
    # (not off disk) — so "what the client's browser gets" is what we record.
    cert_expires = fields.Date(help="Expiry of the certificate served for this tenant's subdomain")
    cert_days_left = fields.Integer(default=-1, help="-1 when the certificate could not be read")
    cert_own = fields.Boolean(
        help="True when the tenant has its own auto-renewing certificate; False means it is "
             "falling back to the wildcard, which does NOT auto-renew.")

    # Where this customer stands against the release the fleet is aiming at.
    # Written by the "in step with master" screen and by the nightly drift
    # check, which only ever READS the customer's database (rail R1).
    release_id = fields.Many2one('pb.release', ondelete='set null',
                                 help="The release this database is on.")
    release_state = fields.Selection([
        ('on', 'In step'),
        ('behind', 'Behind'),
        ('none', 'Not on a release'),
        ('unknown', 'Not checked'),
    ], default='unknown', index=True)
    behind_count = fields.Integer(help="Parts of the product it does not have yet.")
    stale_count = fields.Integer(help="Parts it has at an older version.")
    skipped_count = fields.Integer(
        help="Parts it says it has but which did not load. -1 when it could "
             "not be determined.", default=0)
    drift_checked = fields.Datetime()
    last_sync_at = fields.Datetime()
    #: JSON of the last plan + outcome, shown on the detail screen so the
    #: question "what did that button actually do" has an answer afterwards.
    last_sync_result = fields.Text()

    # What this customer's users are currently being shown at the top of every
    # page. A MIRROR of what was pushed onto their database, kept here so the
    # cockpit can answer "what are they seeing right now" without opening their
    # registry. Their copy is the one that counts; this one is for the screen.
    notice = fields.Text(help="The message this customer's users are shown, as "
                              "it was sent. Empty when there is none.")
    notice_until = fields.Datetime(
        help="When the message stops showing. Their database drops it on its "
             "own at this moment — nobody has to come back and clear it.")
    notice_sent_at = fields.Datetime()

    # FLEET P4. When this customer's database was last told which parts of the
    # product are switched on for it. Empty means NEVER — and a customer who
    # has never been told loses nothing: their database reads "no answer" as
    # "everything on" (fail open, `pb_tenancy`). The screen shows the empty
    # state as "never pushed" with the button that fixes it, so the difference
    # between "everything on because that is the answer" and "everything on
    # because nobody has said otherwise" is never hidden from the owner.
    features_pushed_at = fields.Datetime()
    feature_ids = fields.One2many('pb.tenant.feature', 'tenant_id')

    last_backup_at = fields.Datetime()
    backup_ids = fields.One2many('pb.tenant.backup', 'tenant_id')
    domain_ids = fields.One2many('pb.tenant.domain', 'tenant_id')

    _sql_constraints = [
        ('slug_unique', 'unique(slug)', 'A tenant with this subdomain already exists.'),
    ]


class PbTenantBackup(models.Model):
    _name = 'pb.tenant.backup'
    _description = 'Payobook tenant backup'
    _order = 'create_date desc'

    tenant_id = fields.Many2one('pb.tenant', required=True, ondelete='cascade', index=True)
    filename = fields.Char(required=True)
    path = fields.Char(required=True)
    size = fields.Float(help="bytes")
    kind = fields.Selection([
        ('manual', 'Manual'),
        ('nightly', 'Nightly'),
        ('pre_restore', 'Pre-restore safety'),
        ('final', 'Final (offboarding)'),
    ], default='manual', required=True)
    state = fields.Selection([('done', 'Done'), ('failed', 'Failed')], default='done', required=True)
    note = fields.Char()


class PbTenantDomain(models.Model):
    _name = 'pb.tenant.domain'
    _description = 'Payobook tenant custom domain'
    _order = 'create_date desc'

    tenant_id = fields.Many2one('pb.tenant', required=True, ondelete='cascade', index=True)
    hostname = fields.Char(required=True)
    state = fields.Selection([
        ('pending', 'Waiting for DNS'),
        ('verified', 'DNS verified'),
        ('active', 'Active'),
        ('error', 'Error'),
    ], default='pending', required=True)
    message = fields.Char()
    last_check = fields.Datetime()

    _sql_constraints = [
        ('hostname_unique', 'unique(hostname)', 'This domain is already attached.'),
    ]
