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
