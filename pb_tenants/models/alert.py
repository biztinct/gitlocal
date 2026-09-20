# -*- coding: utf-8 -*-
"""FLEET P3 — one row per problem, for as long as the problem lasts.

WHY A RECORD AND NOT A LOG LINE. The question the owner asks is never "what
happened at 14:02", it is "what is wrong right now, and have I already dealt
with it". A log answers the first; only a record with a state answers the
second. So a problem is created once, bumped while it lasts, and resolved when
it stops — and the email traffic follows the RECORD, not the reading, which is
why the same broken backup does not mail every fifteen minutes.

THE KEY IS THE IDENTITY. `backup_failed:abm` is one problem however many times
it is measured. Uniqueness is not a database constraint, because a resolved
alert must be allowed to sit in history beside a new one with the same key —
it is `reconcile()` next door that keeps exactly one open.
"""
from odoo import api, fields, models

from .alert_rules import ALERT_KINDS

KIND_LABEL = {
    'tenant_down': 'Customer site unreachable',
    'backup_failed': 'Backup failed',
    'backup_stale': 'No recent backup',
    'mail_failing': 'Outgoing email failing',
    'alert_channel_down': 'Alert emails cannot be sent',
    'disk_low': 'Disk running out',
    'memory_high': 'Memory running out',
    'cert_expiring': 'Certificate expiring',
    'tenant_errors': 'A customer is logging errors',
    'rollout_paused': 'Release rollout stopped',
    'drift': 'Customer behind the release',
    'master_behind_files': 'Platform has not applied its own update',
    'support_session': 'Payobook support opened a customer\'s data',
    'template_hot_cron': 'Template has live scheduled jobs',
    'status_page_unwritable': 'Public status page not writable',
    # FLEET P5 — money and standing.
    'invoice_overdue': 'Invoice not paid',
    'suspend_candidate': 'Customer paused, or ready to be',
    'trial_ending': 'Trial running out',
}

#: Which icon the cockpit draws for each kind. Named from the shared Lucide
#: registries, so a kind added later without an entry still draws something.
KIND_ICON = {
    'tenant_down': 'activity',
    'backup_failed': 'shieldCheck',
    'backup_stale': 'shieldCheck',
    'mail_failing': 'send',
    'alert_channel_down': 'bellOff',
    'disk_low': 'hardDrive',
    'memory_high': 'gauge',
    'cert_expiring': 'lock',
    'tenant_errors': 'alert',
    'rollout_paused': 'pause',
    'drift': 'layers',
    'master_behind_files': 'layers',
    'template_hot_cron': 'clock',
    'status_page_unwritable': 'globe',
    'invoice_overdue': 'receipt',
    'suspend_candidate': 'pause',
    'trial_ending': 'hourglass',
    # FLEET P6.
    'support_session': 'shield',
}


class PbAlert(models.Model):
    _name = 'pb.alert'
    _description = 'Payobook platform alert'
    _order = 'severity, first_seen desc, id desc'

    key = fields.Char(required=True, index=True,
                      help="The identity of the problem, e.g. backup_failed:abm. "
                           "One open alert per key.")
    kind = fields.Selection([(k, KIND_LABEL.get(k, k)) for k in ALERT_KINDS],
                            required=True, index=True)
    #: `critical` sorts first because the Selection is stored as its key and
    #: `_order` is alphabetical: critical < info < warning. That is luck rather
    #: than design, so the cockpit sorts properly on its own side too.
    severity = fields.Selection([
        ('critical', 'Needs attention now'),
        ('warning', 'Worth a look'),
        ('info', 'For information'),
    ], default='warning', required=True, index=True)
    title = fields.Char(required=True)
    text = fields.Text(help="What is wrong and what to do next, in plain words.")
    tenant_id = fields.Many2one('pb.tenant', ondelete='set null', index=True)
    state = fields.Selection([
        ('open', 'Open'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
    ], default='open', required=True, index=True)
    first_seen = fields.Datetime(default=fields.Datetime.now, required=True)
    last_seen = fields.Datetime(default=fields.Datetime.now)
    count = fields.Integer(default=1, help="How many checks have seen it.")
    #: When an email about this alert last went out, and how bad it was called
    #: at the time — the pair `should_notify()` reads. Storing the severity is
    #: what lets a problem that gets WORSE mail again straight away.
    notified_at = fields.Datetime()
    notified_severity = fields.Char()
    resolved_at = fields.Datetime()
    resolution = fields.Char(help="Why it was closed, when a person closed it.")
    acknowledged_by = fields.Many2one('res.users', ondelete='set null')
    acknowledged_at = fields.Datetime()

    def as_dict(self):
        """One alert as the rules and the screen both read it."""
        out = []
        for a in self:
            out.append({
                'id': a.id, 'key': a.key, 'kind': a.kind,
                'kind_label': KIND_LABEL.get(a.kind, a.kind),
                'icon': KIND_ICON.get(a.kind, 'alert'),
                'severity': a.severity, 'title': a.title, 'text': a.text or '',
                'state': a.state,
                'tenant_id': a.tenant_id.id or None,
                'tenant': a.tenant_id.name or '',
                'tenant_slug': a.tenant_id.slug or '',
                'first_seen': a.first_seen, 'last_seen': a.last_seen,
                'count': a.count, 'notified_at': a.notified_at,
                'notified_severity': a.notified_severity or '',
                'resolved_at': a.resolved_at,
                'resolution': a.resolution or '',
                'acknowledged_by': a.acknowledged_by.name or '',
            })
        return out

    @api.model
    def open_alerts(self):
        return self.sudo().search([('state', 'in', ('open', 'acknowledged'))])
