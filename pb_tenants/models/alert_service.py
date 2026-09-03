# -*- coding: utf-8 -*-
"""FLEET P3 — noticing, telling somebody, and admitting it in public.

THE SHAPE OF THIS FILE, and it is the same shape as the two phases before it:
every judgement is next door in `alert_rules.py`, pure and tested. What is left
here is the three things that can only be done on a live box — measure it, mail
somebody, write a file nginx serves.

RAIL R1 IS UNTOUCHED. Nothing in this file writes to a customer's database. The
readings are reads: cached health fields, a localhost HTTP probe, read-only SQL
on the template, the server's own log, /proc and the disk. The one thing this
phase writes anywhere new is a static HTML file on this machine.

THE ONE ALERT THAT CANNOT EMAIL ITSELF. When a send fails, `alert_channel_down`
is raised — and it is deliberately the only kind the sweep will not resolve on
its own, because no reading can see it. The sender clears it when a message
finally gets through. On screen it is a rose banner at the top of the cockpit:
the only place it can possibly be read.
"""
import json
import logging
import os
import re
import shutil
import socket
import ssl
from datetime import datetime, timedelta

import odoo
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .billing_rules import SERVING_STATES
from .alert_rules import (
    DEFAULT_THRESHOLDS, capacity_verdict, digest_lines, readings_to_alerts,
    reconcile, render_status_page, should_notify, status_state,
)
from .rollout_rules import CUSTOMER_RINGS, DEFAULT_TZ, filter_errors, to_local
from .rollout_service import LOG_BAD_LEVELS, LOG_RE, LOG_TAIL_BYTES
from .tenancy_rules import parse_stamp, render_range

_logger = logging.getLogger(__name__)

#: How far back each 15-minute sweep looks in the server log.
ALERT_WINDOW_MIN = 15
#: How far back "recent mail failures" reaches. Long enough to catch a channel
#: that broke overnight, short enough that yesterday's fixed problem is gone.
MAIL_WINDOW_HOURS = 6
#: How long a resolved problem stays on the public page as an incident.
INCIDENT_DAYS = 7
#: Where the page nginx serves lives. A setting, because the deploy that made
#: the directory is the one thing about this feature that is not in the repo.
DEFAULT_STATUS_DIR = '/var/www/pb-status'

EMAIL_RE = re.compile(r'^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$')

#: The settings this phase owns, with the defaults in CODE rather than in a
#: data record — an upgrade must not freeze whatever a test run left behind
#: (same reasoning as RAILS_DEFAULTS in service.py).
ALERT_DEFAULTS = {
    'pb_tenants.alert_emails': '',          # empty = every platform admin
    'pb_tenants.alert_from': '',            # empty = the mail server's own user
    'pb_tenants.alert_interval_critical': '2',
    'pb_tenants.alert_interval_warning': '6',
    'pb_tenants.alert_digest_hour': '8',
    'pb_tenants.tenant_cost_mb': '',        # measured at deploy, see the ledger
    'pb_tenants.capacity_reserve_mb': '400',
}

#: Threshold settings, `pb_tenants.alert_<name>` -> the name the rules use.
THRESHOLD_KEYS = ('disk_free_pct', 'mem_available_mb', 'backup_stale_hours',
                  'cert_tenant_days', 'cert_wildcard_days', 'error_lines',
                  'drift_days', 'mail_fail_count')

#: What the common SMTP failures mean, said the way a person would say them.
#: The raw message is kept underneath — this is a translation, not a
#: replacement, and the day one of these is wrong the original is what saves it.
SMTP_PLAIN = (
    ('username and password not accepted',
     "The mail provider refused the sign-in. The app password on the outgoing "
     "mail server is wrong or has been revoked."),
    ('authentication', "The mail provider refused the sign-in — check the "
     "password on the outgoing mail server."),
    ('5.7.0', "The mail provider refused the sign-in — check the password on "
     "the outgoing mail server."),
    ('must either provide a sender address',
     "No sender address. Set one in Alert settings."),
    ('at least one valid recipient',
     "There was nobody to send it to. Add an address in Alert settings."),
    ('name or service not known',
     "The mail server's address could not be looked up — check the host name."),
    ('connection refused', "The mail server refused the connection — check the "
     "host and port."),
    ('timed out', "The mail server did not answer in time. It may be blocked "
     "by a firewall on this machine."),
    ('certificate', "The mail server's security certificate was not accepted."),
)


class PbTenantsAlerts(models.AbstractModel):
    """The alerting, capacity and status-page half of Mission Control."""
    _inherit = 'pb.tenants'

    # ==================================================== settings & recipients
    def _alert_param(self, key, default=''):
        """A setting whose EMPTY value is meaningful, read off the row.

        `get_param` cannot tell "absent" from "deliberately empty" and answers
        `False` for the first (ledger F24), so anything where empty means
        something reads the record instead.
        """
        row = self.env['ir.config_parameter'].sudo().search(
            [('key', '=', key)], limit=1)
        if not row:
            return default
        return row.value if row.value is not None else default

    def _alert_thresholds(self):
        """Every number the rules judge by: the defaults, then the settings."""
        out = dict(DEFAULT_THRESHOLDS)
        for name in THRESHOLD_KEYS:
            raw = self._alert_param('pb_tenants.alert_%s' % name, '')
            if raw in ('', None):
                continue
            try:
                out[name] = float(raw) if '.' in str(raw) else int(raw)
            except (TypeError, ValueError):
                _logger.warning("pb_tenants: alert threshold %s is not a "
                                "number (%r) — using the default.", name, raw)
        return out

    def _alert_intervals(self):
        def num(key, fallback):
            try:
                return float(self._alert_param(key, '') or fallback)
            except (TypeError, ValueError):
                return fallback
        return (num('pb_tenants.alert_interval_critical', 2.0),
                num('pb_tenants.alert_interval_warning', 6.0))

    def _alert_recipients(self):
        """Who gets told. The setting if there is one, every platform
        administrator with an address otherwise.

        Falling back to the administrators rather than to a hard-coded address
        means a platform that has never been configured still reaches a human,
        which is the only state in which this matters most.
        """
        raw = self._alert_param('pb_tenants.alert_emails', '')
        picked = [e.strip() for e in re.split(r'[,;\s]+', raw or '') if e.strip()]
        if picked:
            return [e for e in picked if EMAIL_RE.match(e)]
        users = self.env['res.users'].sudo().search([
            ('active', '=', True), ('share', '=', False), ('email', '!=', False),
        ])
        out = []
        for u in users:
            if u.has_group('base.group_system') and EMAIL_RE.match(u.email or ''):
                if u.email not in out:
                    out.append(u.email)
        return out

    def _alert_from(self):
        """The address every platform email is sent FROM, always explicit.

        185 messages died on this box for the want of it (ledger F5): with no
        `mail.default.from` and no `email_from` on the message, the framework
        refuses to send and files the mail under `exception`, where nobody looks.
        Order: the setting, the outgoing server's own user, the platform default
        sender, then a last-resort address on the platform domain.
        """
        picked = (self._alert_param('pb_tenants.alert_from', '') or '').strip()
        if picked and EMAIL_RE.match(picked):
            return picked
        server = self.env['ir.mail_server'].sudo().search([], limit=1)
        if server and EMAIL_RE.match(server.smtp_user or ''):
            return server.smtp_user
        icp = self.env['ir.config_parameter'].sudo()
        default_from = (icp.get_param('mail.default.from') or '').strip()
        domain = (icp.get_param('mail.catchall.domain') or '').strip()
        if default_from and '@' in default_from:
            return default_from
        if default_from and domain:
            return '%s@%s' % (default_from, domain)
        return 'platform@%s' % (domain or self._base_domain())

    def _cockpit_url(self):
        """A link that opens Mission Control, for the bottom of every email."""
        base = (self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                or 'https://%s' % self._base_domain()).rstrip('/')
        prefix = self._alert_param('pb_tenants.backend_prefix', '') or '/bizapp'
        return '%s%s/action-pb_tenants.action_pb_tenants' % (base, prefix)

    # ================================================================== sending
    def _send_alert_mail(self, subject, body_html, kind='alert', recipients=None):
        """Send one message NOW and know the outcome.

        SYNCHRONOUSLY, on purpose. The framework's own queue would have this
        return "created" and fail an hour later in a table nobody opens — which
        is exactly the failure this phase exists to end. `send()` here either
        works or leaves a reason, and the reason becomes an alert of its own.

        `channel` is the seam the owner ruling leaves for a second way of
        telling somebody later; today there is one and it is email.
        """
        to = recipients if recipients is not None else self._alert_recipients()
        to = [e for e in (to or []) if EMAIL_RE.match(e or '')]
        if not to:
            reason = _("There is nobody to send platform alerts to. Add an "
                       "address under Alert settings.")
            self._channel_down(reason)
            return {'ok': False, 'reason': reason, 'to': []}
        sender = self._alert_from()
        Mail = self.env['mail.mail'].sudo()
        mail = Mail.create({
            'subject': subject,
            'body_html': body_html,
            'email_from': sender,          # ALWAYS explicit — ledger F5
            'email_to': ','.join(to),
            'auto_delete': False,          # the trail is the proof of delivery
        })
        try:
            mail.send(raise_exception=True)
        except Exception as exc:           # noqa: BLE001
            reason = self._plain_smtp(exc)
            _logger.error("pb_tenants: platform alert email failed: %s", exc)
            self._channel_down(reason)
            return {'ok': False, 'reason': reason, 'to': to,
                    'raw': str(exc)[:400], 'from': sender}
        mail.invalidate_recordset(['state', 'failure_reason'])
        if mail.state != 'sent':
            reason = self._plain_smtp(mail.failure_reason or '')
            _logger.error("pb_tenants: platform alert email not sent: %s",
                          mail.failure_reason)
            self._channel_down(reason)
            return {'ok': False, 'reason': reason, 'to': to,
                    'raw': (mail.failure_reason or '')[:400], 'from': sender}
        self._channel_up()
        return {'ok': True, 'reason': '', 'to': to, 'from': sender,
                'mail_id': mail.id}

    @staticmethod
    def _plain_smtp(exc):
        """A mail failure in words a person can act on, cause kept underneath."""
        raw = str(exc or '').strip()
        low = raw.lower()
        for needle, sentence in SMTP_PLAIN:
            if needle in low:
                return sentence
        first = raw.split('\n')[0]
        return first[:240] or "The message could not be sent."

    def _channel_down(self, reason):
        """Raise (or refresh) the one alert that cannot email itself."""
        Alert = self.env['pb.alert'].sudo()
        now = fields.Datetime.now()
        rec = Alert.search([('key', '=', 'alert_channel_down'),
                            ('state', 'in', ('open', 'acknowledged'))], limit=1)
        text = _(
            "Alert emails are not getting out: %s Until this is fixed the "
            "platform can only tell you things on this screen. Next: open "
            "Alert settings, check the sender and the recipients, then press "
            "Send a test email.", reason)
        if rec:
            rec.write({'last_seen': now, 'count': rec.count + 1, 'text': text})
        else:
            Alert.create({
                'key': 'alert_channel_down', 'kind': 'alert_channel_down',
                'severity': 'critical',
                'title': _("Alert emails cannot be sent"),
                'text': text, 'first_seen': now, 'last_seen': now, 'count': 1,
            })

    def _channel_up(self):
        """A message got through, so the channel is not down any more."""
        Alert = self.env['pb.alert'].sudo()
        recs = Alert.search([('key', '=', 'alert_channel_down'),
                             ('state', 'in', ('open', 'acknowledged'))])
        if recs:
            recs.write({'state': 'resolved',
                        'resolved_at': fields.Datetime.now(),
                        'resolution': _("An email got through.")})

    # =================================================================== emails
    def _mail_shell(self, heading, intro, blocks, footer_note=''):
        """One email, laid out the same way every time.

        Inline styles and a table-free layout, because these are read on a
        phone at 07:00 in whatever client the owner happens to use, and the
        thing that must survive is the sentence and the next step.
        """
        rows = ''.join(blocks)
        return """<div style="font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#12121a">
  <div style="font-weight:700;color:#5A4BB0;letter-spacing:-.02em;margin-bottom:14px">Payobook platform</div>
  <div style="font-size:19px;font-weight:650;letter-spacing:-.02em;margin-bottom:6px">%s</div>
  <div style="color:#5c5c6b;margin-bottom:18px">%s</div>
  %s
  <div style="margin-top:22px">
    <a href="%s" style="background:#5A4BB0;color:#fff;text-decoration:none;padding:10px 16px;border-radius:9px;font-weight:600;display:inline-block">Open Mission Control</a>
  </div>
  <div style="color:#8b8899;font-size:12.5px;margin-top:20px">%s</div>
</div>""" % (heading, intro, rows, self._cockpit_url(),
             footer_note or "You are getting this because you look after this "
                            "platform. Change who is told under Alert settings.")

    @staticmethod
    def _alert_block(alert):
        colour = {'critical': '#DC2668', 'warning': '#D97706',
                  'info': '#2563EB'}.get(alert.severity, '#D97706')
        where = (' · %s' % alert.tenant_id.name) if alert.tenant_id else ''
        return ("""<div style="border:1px solid #e6e4f0;border-left:3px solid %s;border-radius:10px;padding:14px 16px;margin-bottom:10px">
  <div style="font-weight:640">%s</div>
  <div style="color:#5c5c6b;font-size:13.5px;margin-top:4px">%s</div>
  <div style="color:#8b8899;font-size:12px;margin-top:7px">%s%s</div>
</div>""" % (colour, alert.title or '', alert.text or '',
             dict(critical='Needs attention now', warning='Worth a look',
                  info='For information').get(alert.severity, ''), where))

    def _mail_new_alerts(self, alerts):
        if not alerts:
            return None
        worst = 'critical' if any(a.severity == 'critical' for a in alerts) else 'warning'
        word = 'Needs attention now' if worst == 'critical' else 'Worth a look'
        if len(alerts) == 1:
            subject = '[Payobook] %s: %s' % (word, alerts[0].title)
            intro = "One new thing needs you."
        else:
            subject = '[Payobook] %s: %d new problems' % (word, len(alerts))
            intro = "%d new things need you." % len(alerts)
        body = self._mail_shell("Something needs your attention", intro,
                                [self._alert_block(a) for a in alerts])
        return subject, body

    def _mail_reminder(self, alerts):
        if not alerts:
            return None
        subject = ('[Payobook] Still open: %s' % alerts[0].title if len(alerts) == 1
                   else '[Payobook] Still open: %d problems' % len(alerts))
        intro = ("This is a reminder — nothing here is new, and none of it has "
                 "cleared on its own.")
        body = self._mail_shell("Still not fixed", intro,
                                [self._alert_block(a) for a in alerts])
        return subject, body

    def _mail_resolved(self, alerts):
        if not alerts:
            return None
        names = ', '.join(a.title for a in alerts)
        subject = ('[Payobook] Cleared: %s' % alerts[0].title if len(alerts) == 1
                   else '[Payobook] Cleared: %d problems' % len(alerts))
        body = self._mail_shell(
            "It is over", "The platform checked again and this has cleared. "
            "Nothing for you to do.",
            ['<div style="border:1px solid #e6e4f0;border-left:3px solid #2E7D4F;'
             'border-radius:10px;padding:14px 16px">%s</div>' % names])
        return subject, body

    # ================================================================= readings
    def _memory_reading(self):
        """What the machine has, and what this application is holding.

        /proc, because the registry cache is NOT a bound on this box: it is
        sized off `limit_memory_soft`, which is unset, so it would answer "136
        customers" on a machine with room for a handful (ledger F6).
        """
        out = {'total_mb': 0, 'available_mb': None, 'rss_mb': 0, 'registries': 0}
        try:
            with open('/proc/meminfo', 'r') as fh:
                for line in fh:
                    if line.startswith('MemTotal:'):
                        out['total_mb'] = int(int(line.split()[1]) / 1024)
                    elif line.startswith('MemAvailable:'):
                        out['available_mb'] = int(int(line.split()[1]) / 1024)
        except OSError:
            pass
        try:
            with open('/proc/self/status', 'r') as fh:
                for line in fh:
                    if line.startswith('VmRSS:'):
                        out['rss_mb'] = int(int(line.split()[1]) / 1024)
                        break
        except OSError:
            pass
        try:
            from odoo.modules.registry import Registry
            out['registries'] = len(Registry.registries)
        except Exception:                          # noqa: BLE001
            out['registries'] = 0
        return out

    def _disk_reading(self):
        try:
            du = shutil.disk_usage('/')
            return {'free_pct': int(du.free * 100 / du.total),
                    'free_gb': round(du.free / (1024.0 ** 3), 1),
                    'total_gb': round(du.total / (1024.0 ** 3), 1)}
        except OSError:
            return {}

    def _log_error_counts(self, dbnames, since):
        """Error lines per database since a moment — ONE pass over the log.

        The health gate reads the same file for one database at a time, which is
        right for a rollout and wrong for a sweep that runs every quarter of an
        hour over the whole fleet: that would be twenty megabytes of reading per
        customer per sweep. Same regex, same tail, same ignore list (F25) —
        counted for every database in a single walk.
        """
        wanted = set(dbnames or ())
        counts = {db: 0 for db in wanted}
        if not wanted:
            return counts
        path = self._logfile()
        stamp = (since or datetime.min).strftime('%Y-%m-%d %H:%M:%S')
        ignore = self._log_ignore()
        found = {db: [] for db in wanted}
        try:
            size = os.path.getsize(path)
            with open(path, 'rb') as fh:
                if size > LOG_TAIL_BYTES:
                    fh.seek(size - LOG_TAIL_BYTES)
                    fh.readline()
                for raw in fh:
                    line = raw.decode('utf-8', 'replace').rstrip('\n')
                    m = LOG_RE.match(line)
                    if not m:
                        continue
                    ts, level, db, logger_name, msg = m.groups()
                    if db not in wanted or level not in LOG_BAD_LEVELS:
                        continue
                    if ts < stamp:
                        continue
                    found[db].append('%s %s %s: %s'
                                     % (ts, level, logger_name.strip(), msg[:200]))
        except Exception:                          # noqa: BLE001
            _logger.warning("pb_tenants: could not read %s", path, exc_info=True)
            return {db: 0 for db in wanted}
        for db, lines in found.items():
            kept, _ignored = filter_errors(lines, ignore)
            counts[db] = len(kept)
        return counts

    def _template_hot_crons(self):
        """Live scheduled jobs inside the blank template. Read-only SQL."""
        try:
            with self._pg_cursor(self._template_db()) as cr:
                cr.execute("SELECT count(*) FROM ir_cron WHERE active")
                return int(cr.fetchone()[0])
        except Exception:                          # noqa: BLE001
            return 0

    def _status_dir(self):
        return self._param('pb_tenants.status_dir', DEFAULT_STATUS_DIR)

    def _status_file(self):
        return os.path.join(self._status_dir(), 'index.html')

    def _status_reading(self):
        path, folder = self._status_file(), self._status_dir()
        if not os.path.isdir(folder):
            return {'writable': False, 'age_min': None,
                    'reason': 'The folder %s does not exist.' % folder}
        if not os.access(folder, os.W_OK):
            return {'writable': False, 'age_min': None,
                    'reason': 'The folder %s cannot be written by this '
                              'application.' % folder}
        age = None
        if os.path.exists(path):
            age = int((datetime.now().timestamp() - os.path.getmtime(path)) / 60)
        return {'writable': True, 'age_min': age, 'reason': ''}

    def _gather_readings(self, window_minutes=ALERT_WINDOW_MIN):
        """Everything the rules need, measured. READS ONLY — rail R1.

        Nothing here opens a customer's registry: the health fields are the
        cache the hourly job keeps, the site probe is one HTTP call through
        localhost, and the only SQL that leaves this database is a count of
        scheduled jobs on the template.
        """
        now = fields.Datetime.now()
        since = now - timedelta(minutes=window_minutes)
        dom = self._base_domain()
        Tenant = self.env['pb.tenant'].sudo()
        live = Tenant.search([('state', 'in', SERVING_STATES)])
        dbfilter_live = '%d' in (odoo.tools.config['dbfilter'] or '')
        counts = self._log_error_counts([t.slug for t in live] + [self.env.cr.dbname],
                                        since)
        rel = self.env['pb.release'].sudo().current()
        rel_age = int((now - rel.captured_at).days) if rel and rel.captured_at else None

        Backup = self.env['pb.tenant.backup'].sudo()
        rows = []
        for t in live:
            code, ms = self._probe('%s.%s' % (t.slug, dom))
            last = Backup.search([('tenant_id', '=', t.id)],
                                 order='create_date desc', limit=1)
            rows.append({
                'id': t.id, 'name': t.name, 'slug': t.slug, 'state': t.state,
                'health': ('ok' if code == 200
                           else ('down' if dbfilter_live else 'unknown')),
                'ping_ms': ms,
                'last_backup_at': t.last_backup_at or None,
                'last_backup_failed': bool(last and last.state == 'failed'),
                'cert_days_left': (t.cert_days_left
                                   if isinstance(t.cert_days_left, int) else None),
                'cert_own': t.cert_own,
                'error_lines': counts.get(t.slug, 0),
                'release_state': t.release_state,
                'behind_count': t.behind_count,
                'stale_count': t.stale_count,
                'release_age_days': rel_age,
            })

        mem = self._memory_reading()
        icp = self.env['ir.config_parameter'].sudo()
        fail_since = now - timedelta(hours=MAIL_WINDOW_HOURS)
        failed = self.env['mail.mail'].sudo().search_count([
            ('state', '=', 'exception'), ('write_date', '>=', fail_since)])
        roll = self.env['pb.rollout'].sudo().search(
            [('state', 'in', ('running', 'waiting', 'paused'))],
            order='create_date desc', limit=1)
        try:
            wildcard_days = self._check_wildcard_tls(dom)['days_left']
        except Exception:                          # noqa: BLE001
            wildcard_days = None
        return {
            'now': now,
            'tenants': rows,
            'wildcard_cert_days': wildcard_days,
            'disk': self._disk_reading(),
            'memory': {'total_mb': mem['total_mb'],
                       'available_mb': mem['available_mb'],
                       'rss_mb': mem['rss_mb']},
            'mail': {
                'default_from': bool((icp.get_param('mail.default.from') or '').strip()),
                'failed_recent': failed,
            },
            'rollout': ({'state': roll.state, 'release': roll.release_id.name,
                         'reason': (roll.reason or '').split('\n')[0]}
                        if roll else {}),
            'template_hot_crons': self._template_hot_crons(),
            'master_behind_files': self._master_behind_files(),
            'status_page': self._status_reading(),
            'master_errors': counts.get(self.env.cr.dbname, 0),
        }

    # ==================================================================== crons
    @api.model
    def _cron_alerts(self):
        """Every fifteen minutes: look, compare with what we knew, then speak.

        The order matters. Reconciling BEFORE mailing means a problem that
        cleared between two sweeps sends its "it is over" note in the same run
        that stops reminding about it, and the status page written at the end is
        written from the reconciled truth rather than from the readings.
        """
        now = fields.Datetime.now()
        Alert = self.env['pb.alert'].sudo()
        try:
            readings = self._gather_readings()
        except Exception:                          # noqa: BLE001
            _logger.exception("pb_tenants: the alert sweep could not take its "
                              "readings")
            return
        fresh = readings_to_alerts(readings, self._alert_thresholds())
        known = Alert.search([('state', 'in', ('open', 'acknowledged'))])
        to_create, to_bump, to_resolve = reconcile(known.as_dict(), fresh, now)

        created = Alert.browse()
        for vals in to_create:
            created |= Alert.create({
                'key': vals['key'], 'kind': vals['kind'],
                'severity': vals['severity'], 'title': vals['title'],
                'text': vals['text'], 'tenant_id': vals.get('tenant_id') or False,
                'first_seen': now, 'last_seen': now, 'count': 1, 'state': 'open',
            })
        for aid, vals in to_bump:
            Alert.browse(aid).write(vals)
        closing = Alert.browse(to_resolve)
        # WHICH ONES EARN AN "IT IS OVER" NOTE. Only the ones that were urgent:
        # a warning clearing on its own is not news, and an inbox that gets a
        # second message every time a certificate renewal ticks over is an
        # inbox where the urgent ones stop standing out.
        closed_critical = closing.filtered(lambda a: a.severity == 'critical')
        if closing:
            closing.write({'state': 'resolved', 'resolved_at': now,
                           'resolution': _("The platform checked again and it "
                                           "had cleared.")})
        self.env.cr.commit()

        crit_h, warn_h = self._alert_intervals()
        reminders = Alert.browse()
        for a in Alert.search([('state', '=', 'open')]):
            if a in created:
                continue
            if should_notify(a.as_dict()[0], now, crit_h, warn_h):
                reminders |= a
        self._speak(created, reminders, closed_critical, now)
        try:
            self._write_status_page()
        except Exception:                          # noqa: BLE001
            _logger.exception("pb_tenants: the status page could not be written")
        self.env.cr.commit()

    def _speak(self, created, reminders, closed, now):
        """At most three emails per sweep, never one per problem.

        THE STAMP IS ONLY WRITTEN WHEN THE MESSAGE ACTUALLY WENT. If a send
        failed and this stamped anyway, the problem would fall silent for two
        hours on the strength of an email nobody received — which is the exact
        shape of the failure this whole phase exists to end.
        """
        for group, builder in ((created, self._mail_new_alerts),
                               (reminders, self._mail_reminder)):
            if not group:
                continue
            made = builder(group)
            if not made:
                continue
            res = self._send_alert_mail(made[0], made[1], kind='alert')
            if res['ok']:
                for a in group:
                    a.write({'notified_at': now, 'notified_severity': a.severity})
        if closed:
            made = self._mail_resolved(closed)
            if made:
                self._send_alert_mail(made[0], made[1], kind='resolved')

    @api.model
    def _cron_alert_digest(self):
        """One short summary a day, whether or not anything is wrong.

        The empty one is the point. A channel that only ever speaks when
        something is broken is a channel nobody can tell from a broken channel;
        a line every morning saying everybody is well is the proof it works.
        """
        now = fields.Datetime.now()
        Alert = self.env['pb.alert'].sudo()
        rows = Alert.search([('state', 'in', ('open', 'acknowledged'))])
        lines = digest_lines(rows.as_dict(), now)
        live = self.env['pb.tenant'].sudo().search_count(
            [('state', 'in', SERVING_STATES)])
        if lines:
            subject = '[Payobook] Morning summary — %d open' % len(lines)
            blocks = [
                '<div style="border:1px solid #e6e4f0;border-radius:10px;'
                'padding:12px 15px;margin-bottom:8px;font-size:14px">%s</div>' % ln
                for ln in lines]
            intro = ("%d thing%s still open across %d customer%s."
                     % (len(lines), '' if len(lines) == 1 else 's',
                        live, '' if live == 1 else 's'))
        else:
            subject = '[Payobook] Morning summary — all clear'
            blocks = ['<div style="border:1px solid #e6e4f0;border-left:3px solid '
                      '#2E7D4F;border-radius:10px;padding:14px 16px">Nothing open. '
                      'All %d customer%s healthy.</div>'
                      % (live, '' if live == 1 else 's')]
            intro = "Nothing needs you this morning."
        body = self._mail_shell("Yesterday and this morning", intro, blocks)
        return self._send_alert_mail(subject, body, kind='digest')

    @api.model
    def _cron_status_page(self):
        try:
            self._write_status_page()
        except Exception:                          # noqa: BLE001
            _logger.exception("pb_tenants: the status page could not be written")

    # ================================================================= capacity
    def _capacity(self):
        mem = self._memory_reading()
        live = self.env['pb.tenant'].sudo().search_count(
            [('state', 'in', SERVING_STATES)])
        try:
            cost = float(self._alert_param('pb_tenants.tenant_cost_mb', '') or 0)
        except (TypeError, ValueError):
            cost = 0
        try:
            reserve = float(self._alert_param('pb_tenants.capacity_reserve_mb', '')
                            or 400)
        except (TypeError, ValueError):
            reserve = 400
        return capacity_verdict(mem['total_mb'], mem['available_mb'],
                                mem['rss_mb'], mem['registries'], live,
                                cost, reserve)

    @api.model
    def capacity_check(self):
        """What the wizard asks before it lets somebody start."""
        self._require_admin()
        return self._capacity()

    # ============================================================= status page
    def _status_tz(self):
        """Whose clock the public page speaks in.

        THE PAGE HAS NO READER TO ASK. A customer's own bar renders its window
        in the browser that is drawing it (F17); a file on disk cannot, so the
        window has to be SAID in a named zone or it is a lie by omission — the
        first cut printed the raw UTC stamp under a heading that read "today",
        and a maintenance window typed as 22:34 appeared to the world as 12:34.
        Same trap as F32, pointing at a page instead of at a customer.
        """
        picked = (self._alert_param('pb_tenants.status_tz', '') or '').strip()
        if picked:
            return picked
        try:
            tz = self.env.company.partner_id.tz
        except Exception:                          # noqa: BLE001
            tz = ''
        return tz or DEFAULT_TZ

    def _public_notices(self):
        """The messages the owner ticked as public, once each.

        The same announcement sent to five customers is five mirrors of ONE
        message with one id, so it is de-duplicated on that id — otherwise the
        public page would repeat the same maintenance window five times and look
        like five outages.
        """
        now = fields.Datetime.now()
        tz = self._status_tz()
        local_now = to_local(now, tz)
        seen, out = set(), []
        for t in self.env['pb.tenant'].sudo().search(
                [('state', 'in', SERVING_STATES)]):
            if not t.notice:
                continue
            if t.notice_until and t.notice_until <= now:
                continue
            try:
                data = json.loads(t.notice)
            except ValueError:
                continue
            if not isinstance(data, dict) or not data.get('public'):
                continue
            nid = data.get('id') or data.get('title')
            if nid in seen:
                continue
            seen.add(nid)
            window = render_range(
                to_local(parse_stamp(data.get('starts_at')), tz),
                to_local(parse_stamp(data.get('ends_at')), tz),
                now=local_now)
            out.append({
                'kind': data.get('kind') or 'info',
                'title': data.get('title') or '',
                'text': data.get('text') or '',
                'range': ('%s · %s' % (window, tz)) if window else '',
            })
        return out

    def _status_inputs(self):
        now = fields.Datetime.now()
        Alert = self.env['pb.alert'].sudo()
        opens = Alert.search([('state', 'in', ('open', 'acknowledged'))])
        since = now - timedelta(days=INCIDENT_DAYS)
        closed = Alert.search([('state', '=', 'resolved'),
                               ('severity', '=', 'critical'),
                               ('resolved_at', '>=', since)])
        incidents = []
        for a in closed:
            mins = 0
            if a.first_seen and a.resolved_at:
                mins = int((a.resolved_at - a.first_seen).total_seconds() / 60)
            incidents.append({'kind': a.kind, 'minutes': mins,
                              'ended': a.resolved_at})
        incidents.sort(key=lambda i: str(i['ended'] or ''), reverse=True)
        roll = self.env['pb.rollout'].sudo().search(
            [('state', 'in', ('running', 'waiting'))], limit=1)
        maintenance = bool(roll and roll.current_ring in CUSTOMER_RINGS)
        return status_state(opens.as_dict(), self._public_notices(),
                            incidents[:12], now, maintenance=maintenance)

    def _write_status_page(self):
        """Write the page nginx serves, atomically.

        Temp file plus `os.replace`, because a reader arriving mid-write must
        get the old page rather than half of the new one — the whole promise of
        this file is that it is there when everything else is not.
        """
        folder = self._status_dir()
        path = os.path.join(folder, 'index.html')
        # A FILE IS NOT ROLLED BACK. A test suite runs against a fabricated
        # fleet inside a transaction that is thrown away — but this write is not
        # in that transaction, so a run on the live platform PUBLISHED a page
        # built from invented customers and invented problems. It was harmless
        # the day it was noticed and one fabricated critical away from telling
        # the world about an incident that never happened. Every caller is
        # covered here rather than in each test, because the callers are
        # `alert_ack`, `alert_resolve`, `notice_send`, `notice_clear` and two
        # crons, and the next one will be written by somebody who has not read
        # this comment.
        if odoo.tools.config['test_enable']:
            return {'ok': True, 'path': path, 'skipped': 'test run'}
        state = self._status_inputs()
        page = render_status_page(state, fields.Datetime.now())
        tmp = path + '.tmp'
        try:
            os.makedirs(folder, exist_ok=True)
            with open(tmp, 'w', encoding='utf-8') as fh:
                fh.write(page)
            os.replace(tmp, path)
        except OSError as exc:
            _logger.warning("pb_tenants: could not write %s: %s", path, exc)
            return {'ok': False, 'reason': str(exc), 'path': path}
        return {'ok': True, 'path': path, 'level': state['level'],
                'bytes': len(page)}

    def _refresh_status_page_quietly(self):
        """Rewrite the page, and never let that break what called it.

        Sending a message to a customer must not fail because a folder on this
        machine is missing. The missing folder is an alert of its own, raised by
        the sweep, which is the right place for it.
        """
        try:
            return self._write_status_page()
        except Exception:                          # noqa: BLE001
            _logger.exception("pb_tenants: the status page could not be written")
            return {'ok': False}

    @api.model
    def status_page_refresh(self):
        self._require_admin()
        return self._write_status_page()

    @api.model
    def status_page_preview(self):
        """The page as it stands, for a screenshot and for a test."""
        self._require_admin()
        return render_status_page(self._status_inputs(), fields.Datetime.now())

    def _status_url(self):
        return 'https://%s/status' % self._base_domain()

    def _status_served(self):
        """Is nginx really serving the file? Asked of nginx, not of ourselves.

        Through 127.0.0.1 with the platform's host name, which is how every
        other probe on this cockpit asks the same kind of question — it proves
        the request never reached the application, because the application has
        no such route.
        """
        host = self._base_domain()
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with socket.create_connection(('127.0.0.1', 443), timeout=6) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as tls:
                    tls.sendall(
                        ("GET /status HTTP/1.1\r\nHost: %s\r\n"
                         "User-Agent: pb-status-check\r\nConnection: close\r\n\r\n"
                         % host).encode())
                    chunks, got = [], 0
                    while got < 8192:
                        part = tls.recv(4096)
                        if not part:
                            break
                        chunks.append(part)
                        got += len(part)
            raw = b''.join(chunks).decode('utf-8', 'replace')
            head, _sep, body = raw.partition('\r\n\r\n')
            first = head.split('\r\n')[0] if head else ''
            code = 0
            parts = first.split()
            if len(parts) > 1 and parts[1].isdigit():
                code = int(parts[1])
            return {
                'code': code,
                # nginx stamps a file it serves off disk with Last-Modified and
                # an ETag; the application stamps neither. That is how this
                # tells "nginx served the file" from "the app answered /status".
                'server_file': 'Last-Modified:' in head or 'ETag:' in head,
                'is_status': 'Payobook status' in body or 'Payobook status' in head,
            }
        except Exception as exc:                   # noqa: BLE001
            return {'code': 0, 'error': str(exc)[:160], 'server_file': False,
                    'is_status': False}

    # ======================================================= checklist rows
    def _mail_check(self):
        """"Outgoing mail proven" — and PROVEN is the whole change.

        The row it replaces asked whether an outgoing mail server record
        existed, which was true on this platform while 185 messages sat in the
        failed pile. A server record proves somebody typed a host name. What
        this asks instead is whether a message actually left the machine, and
        whether the sender address that killed those 185 is set.
        """
        icp = self.env['ir.config_parameter'].sudo()
        default_from = (icp.get_param('mail.default.from') or '').strip()
        week = fields.Datetime.now() - timedelta(days=7)
        sent = self.env['mail.mail'].sudo().search_count(
            [('state', '=', 'sent'), ('write_date', '>=', week)])
        proven_raw = self._alert_param('pb_tenants.mail_proven_at', '')
        proven = False
        if proven_raw:
            try:
                proven = fields.Datetime.to_datetime(proven_raw) >= week
            except (ValueError, TypeError):
                proven = False
        delivered = bool(sent) or proven
        missing = []
        if not default_from:
            missing.append("no default sender address is set")
        if not delivered:
            missing.append("no message has actually gone out in the last week")
        return {
            'key': 'mail', 'label': 'Outgoing mail proven',
            'ok': bool(default_from and delivered),
            'action': 'mail_test',
            'action_label': 'Send a test email',
            'hint': ('Alerts and customer emails cannot be relied on: %s. Press '
                     'Send a test email to find out exactly what is wrong.'
                     % ' and '.join(missing)) if missing else
                    ('Sending as %s; a message left this machine in the last '
                     'week.' % self._alert_from()),
        }

    def _status_check(self):
        """"Public status page" — the file is fresh AND nginx is serving it."""
        reading = self._status_reading()
        served = self._status_served()
        age = reading.get('age_min')
        fresh = age is not None and age < DEFAULT_THRESHOLDS['status_page_minutes']
        ok = bool(fresh and served.get('code') == 200 and served.get('is_status'))
        if not reading.get('writable'):
            hint = ('%s Create it on the server and let the application '
                    'write to it.' % reading.get('reason'))
        elif age is None:
            hint = ('The page has never been written. Press Re-check platform — '
                    'it is rewritten every five minutes and after every alert.')
        elif not fresh:
            hint = ('The page is %d minutes old, so it would tell a customer '
                    'something stale. Check the scheduled jobs are running.' % age)
        elif served.get('code') != 200:
            hint = ('The file is there but %s does not serve it (%s). Add the '
                    '/status location to the web server — see the Status page '
                    'section of docs/SAAS_RUNBOOK.md.'
                    % (self._status_url(),
                       served.get('error') or 'answered %s' % served.get('code')))
        else:
            hint = 'Served from disk, %d minute(s) old.' % (age or 0)
        return {'key': 'status_page', 'label': 'Public status page', 'ok': ok,
                'hint': hint, 'link': self._status_url(),
                'link_label': 'Open the page'}

    # ================================================================== the RPCs
    @api.model
    def alerts_data(self):
        """Everything the Alerts view draws."""
        self._require_admin()
        Alert = self.env['pb.alert'].sudo()
        now = fields.Datetime.now()
        opens = Alert.search([('state', 'in', ('open', 'acknowledged'))])
        since = now - timedelta(days=30)
        history = Alert.search([('state', '=', 'resolved'),
                                ('resolved_at', '>=', since)],
                               order='resolved_at desc', limit=100)

        def brief(a):
            row = a.as_dict()[0]
            row['since'] = (a.first_seen.isoformat(sep=' ', timespec='minutes')
                            if a.first_seen else '')
            row['seen'] = (a.last_seen.isoformat(sep=' ', timespec='minutes')
                           if a.last_seen else '')
            row['ended'] = (a.resolved_at.isoformat(sep=' ', timespec='minutes')
                            if a.resolved_at else '')
            row['age'] = self._age_words(a.first_seen, a.resolved_at or now)
            row['notified'] = (a.notified_at.isoformat(sep=' ', timespec='minutes')
                               if a.notified_at else '')
            for key in ('first_seen', 'last_seen', 'notified_at', 'resolved_at'):
                row.pop(key, None)
            return row

        rows = [brief(a) for a in opens]
        crit_h, warn_h = self._alert_intervals()
        return {
            'critical': [r for r in rows if r['severity'] == 'critical'
                         and r['state'] == 'open'],
            'warning': [r for r in rows if r['severity'] != 'critical'
                        and r['state'] == 'open'],
            'acknowledged': [r for r in rows if r['state'] == 'acknowledged'],
            'history': [brief(a) for a in history],
            'open_count': len(rows),
            'critical_count': len([r for r in rows if r['severity'] == 'critical'
                                   and r['state'] == 'open']),
            'recipients': self._alert_recipients(),
            'from': self._alert_from(),
            'intervals': {'critical': crit_h, 'warning': warn_h},
            'checked_at': now.isoformat(sep=' ', timespec='minutes'),
            'status_url': self._status_url(),
        }

    @staticmethod
    def _age_words(start, end):
        if not start or not end:
            return ''
        mins = int((end - start).total_seconds() / 60)
        if mins < 60:
            return "%d min" % max(1, mins)
        if mins < 60 * 48:
            return "%d h" % int(round(mins / 60.0))
        return "%d days" % int(round(mins / 1440.0))

    @api.model
    def alert_ack(self, alert_id):
        self._require_admin()
        rec = self.env['pb.alert'].sudo().browse(int(alert_id)).exists()
        if not rec:
            raise UserError(_("That alert is no longer there."))
        rec.write({'state': 'acknowledged', 'acknowledged_by': self.env.uid,
                   'acknowledged_at': fields.Datetime.now()})
        self._write_status_page()
        return self.alerts_data()

    @api.model
    def alert_resolve(self, alert_id, reason=''):
        self._require_admin()
        rec = self.env['pb.alert'].sudo().browse(int(alert_id)).exists()
        if not rec:
            raise UserError(_("That alert is no longer there."))
        rec.write({'state': 'resolved', 'resolved_at': fields.Datetime.now(),
                   'resolution': (reason or '').strip()[:240]
                   or _("Closed by hand.")})
        self._write_status_page()
        return self.alerts_data()

    @api.model
    def alert_check_now(self):
        """Run the sweep by hand. The same code the cron runs, nothing else."""
        self._require_admin()
        self._cron_alerts()
        return self.alerts_data()

    @api.model
    def mail_test(self):
        """Prove the channel, with the outcome in words.

        This is the button behind the "Outgoing mail proven" row, and it sends a
        real message to the real recipients — there is no other way to know.
        """
        self._require_admin()
        to = self._alert_recipients()
        if not to:
            return {'ok': False, 'reason': _(
                "There is nobody to send it to. Add at least one address under "
                "Alert settings."), 'to': []}
        body = self._mail_shell(
            "Your alerts are working",
            "This is the test message from Tenant Mission Control.",
            ['<div style="border:1px solid #e6e4f0;border-left:3px solid #2E7D4F;'
             'border-radius:10px;padding:14px 16px">If you are reading this, the '
             'platform can reach you. Real alerts arrive the same way, within '
             'fifteen minutes of something going wrong, and each one says what '
             'to do next.</div>'],
            footer_note="Sent by hand from the platform checklist.")
        res = self._send_alert_mail('[Payobook] Test message from your platform',
                                    body, kind='test')
        if res['ok']:
            self.env['ir.config_parameter'].sudo().set_param(
                'pb_tenants.mail_proven_at',
                fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            res['message'] = _(
                "Sent to %s. It leaves this machine now — check the inbox.",
                ', '.join(res['to']))
        else:
            res['message'] = res['reason']
        return res

    @api.model
    def alert_settings(self):
        """What the settings dialog opens holding."""
        self._require_admin()
        th = self._alert_thresholds()
        crit_h, warn_h = self._alert_intervals()
        cap = self._capacity()
        return {
            'emails': self._alert_param('pb_tenants.alert_emails', ''),
            'default_recipients': self._alert_recipients(),
            'from': self._alert_param('pb_tenants.alert_from', ''),
            'from_effective': self._alert_from(),
            'interval_critical': crit_h,
            'interval_warning': warn_h,
            'digest_hour': int(float(
                self._alert_param('pb_tenants.alert_digest_hour', '') or 8)),
            'thresholds': {k: th[k] for k in THRESHOLD_KEYS},
            'tenant_cost_mb': cap['cost_per_tenant_mb'],
            'reserve_mb': cap['reserve_mb'],
            'capacity': cap,
        }

    @api.model
    def alert_settings_save(self, vals):
        """Save the settings, refusing anything that would silence the alerts.

        Every refusal names the field and says what a good answer looks like.
        A settings screen that saves nonsense is a settings screen that turns
        the alarm off without telling anybody.
        """
        self._require_admin()
        vals = vals or {}
        icp = self.env['ir.config_parameter'].sudo()
        emails = (vals.get('emails') or '').strip()
        picked = [e.strip() for e in re.split(r'[,;\s]+', emails) if e.strip()]
        bad = [e for e in picked if not EMAIL_RE.match(e)]
        if bad:
            raise UserError(_("This does not look like an email address: %s",
                              ', '.join(bad)))
        sender = (vals.get('from') or '').strip()
        if sender and not EMAIL_RE.match(sender):
            raise UserError(_("The sender address does not look like an email "
                              "address: %s", sender))
        icp.set_param('pb_tenants.alert_emails', ', '.join(picked))
        icp.set_param('pb_tenants.alert_from', sender)

        def num(name, lo, hi, label):
            raw = vals.get(name)
            if raw in (None, ''):
                return None
            try:
                val = float(raw)
            except (TypeError, ValueError):
                raise UserError(_("%(label)s has to be a number.", label=label))
            if not (lo <= val <= hi):
                raise UserError(_("%(label)s has to be between %(lo)s and "
                                  "%(hi)s.", label=label, lo=lo, hi=hi))
            return val

        pairs = [
            ('interval_critical', 'pb_tenants.alert_interval_critical', 0, 168,
             _("The reminder for urgent problems")),
            ('interval_warning', 'pb_tenants.alert_interval_warning', 0, 168,
             _("The reminder for smaller problems")),
            ('digest_hour', 'pb_tenants.alert_digest_hour', 0, 23,
             _("The hour the morning summary is sent")),
            ('tenant_cost_mb', 'pb_tenants.tenant_cost_mb', 1, 4096,
             _("The memory one customer costs")),
            ('reserve_mb', 'pb_tenants.capacity_reserve_mb', 0, 8192,
             _("The memory kept back for the rest of the machine")),
        ]
        for name, key, lo, hi, label in pairs:
            val = num(name, lo, hi, label)
            if val is not None:
                icp.set_param(key, str(int(val) if val == int(val) else val))
        limits = {
            'disk_free_pct': (1, 90, _("Disk warning level")),
            'mem_available_mb': (32, 8192, _("Memory warning level")),
            'backup_stale_hours': (1, 720, _("Backup age")),
            'cert_tenant_days': (1, 90, _("Certificate warning (customer)")),
            'cert_wildcard_days': (1, 120, _("Certificate warning (wildcard)")),
            'error_lines': (1, 500, _("Errors before we say something")),
            'drift_days': (1, 365, _("Days behind the release")),
            'mail_fail_count': (1, 500, _("Failed messages before we say something")),
        }
        th = vals.get('thresholds') or {}
        for name, (lo, hi, label) in limits.items():
            if name not in th:
                continue
            val = th.get(name)
            if val in (None, ''):
                icp.set_param('pb_tenants.alert_%s' % name, '')
                continue
            try:
                num_val = float(val)
            except (TypeError, ValueError):
                raise UserError(_("%(label)s has to be a number.", label=label))
            if not (lo <= num_val <= hi):
                raise UserError(_("%(label)s has to be between %(lo)s and "
                                  "%(hi)s.", label=label, lo=lo, hi=hi))
            icp.set_param('pb_tenants.alert_%s' % name,
                          str(int(num_val) if num_val == int(num_val) else num_val))
        if not self._alert_recipients():
            raise UserError(_(
                "Nobody would be told. Add at least one email address, or "
                "leave the box empty so every platform administrator is used."))
        return self.alert_settings()
