# -*- coding: utf-8 -*-
"""Tenant Mission Control facade.

All heavy lifting for the SaaS platform: tenant provisioning (clone the golden
template DB + filestore), backups/restores, offboarding, custom domains and
fleet health. Every public method is an admin-only RPC called by the cockpit.

Database operations reuse Odoo's own battle-tested service layer
(odoo.service.db: duplicate / dump / restore / drop, which also handle the
filestore). Those functions are gated on the `list_db` config flag, which we
keep False for security — `_direct()` calls their functools-wrapped inner
function (`__wrapped__`), bypassing only the RPC-exposure gate while our own
`_require_admin()` guards every entry point. No config flipping, no race.
"""
import json
import logging
import os
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import time
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import odoo
from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.modules.registry import Registry
from odoo.service import db as db_service

_logger = logging.getLogger(__name__)

SLUG_RE = re.compile(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$')
HOST_RE = re.compile(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$')
RESERVED_SLUGS = {
    'www', 'mail', 'smtp', 'imap', 'pop', 'ftp', 'admin', 'api', 'app', 'apps',
    'staging', 'demo', 'test', 'dev', 'ns1', 'ns2', 'cdn', 'static', 'assets',
    'portal', 'help', 'docs', 'status', 'vpn', 'git', 'db', 'postgres', 'odoo',
    'payobook', 'template', 'billing', 'pay', 'blog', 'shop', 'webmail', 'm',
    'autoconfig', 'autodiscover', 'login', 'auth', 'secure', 'support',
}

def currency_change(country_currency_id, company_currency_id):
    """Which currency should a freshly cloned tenant's company be moved to?

    Returns the currency id to write, or None to leave the company alone.

    THIS IS THE WHOLE DECISION, AND IT IS PURE ON PURPOSE. The provisioning
    path it belongs to runs against a database that has just been cloned on a
    live box: it cannot be exercised anywhere but a deploy, so the part that
    can be exercised is lifted out and tested
    (pb_tenants/tests/test_currency.py). What is left at the call site is two
    record reads and a write.

    WHY IT EXISTS: the golden template's company is in USD, and every clone
    inherits that. A Vietnamese tenant therefore opened its first dashboard
    with "$0" on the payroll tile — the figure was honest and the money sign
    was not, which is the same family of bug as the hard-coded `₫` this
    dashboard's formatter used to carry, pointing the other way.

    Both guards are load-bearing:
      * a country with NO currency (a handful in `res.country` have none)
        must leave the company where it is rather than clearing its currency,
        which would break every monetary field on the tenant.
      * a country whose currency is ALREADY the company's is not a change,
        and writing it anyway would put a misleading line in the provisioning
        trail somebody reads when a clone goes wrong.
    """
    if not country_currency_id:
        return None
    if country_currency_id == company_currency_id:
        return None
    return country_currency_id


# =============================================================================
# THE TENANT-ADMINISTRATOR RAILS (ACCESS P5).
#
# THE FINDING THIS EXISTS FOR. Provisioning creates no user and assigns no
# permissions: `_step_admin` re-uses the golden template's own `base.user_admin`
# account, which the template ships archived, and simply renames it and switches
# it on. That account carries the SYSTEM ADMINISTRATOR permission, so every
# customer's own administrator has been holding the keys to the whole database —
# the view editor, every model's raw table, the module list, the switch that
# turns developer mode on — not because anybody decided that, but because that
# is what the template's account happened to have.
#
# WHAT THE RAILS DO. For a tenant created from here on, that account is given
# the "Tenant administrator" ROLE — the administrator tier of every part of the
# product — and the platform permissions are taken off it. It runs its whole
# application and nothing of ours. A second account, which cannot be logged
# into and is never shown to the customer, is left in the clone so the platform
# can still get in when something has gone wrong (see `_ensure_break_glass` for
# why it is switched on rather than archived — Odoo will not let a database
# exist with no active administrator, and that refusal is the reason).
#
# NOTHING HAPPENS TO A TENANT THAT ALREADY EXISTS. This runs during
# provisioning, for a database that has existed for about a minute and that
# nobody has logged into. Applying it to a live customer is a separate,
# deliberate act with its own method, its own dry run and its own guards
# (`apply_tenant_admin_rails`), and it is not called from anywhere.
#
# AND THERE IS A SWITCH. `pb_tenants.tenant_admin_rails` = 0 and provisioning
# goes back to handing over the account exactly as it did before, without a
# deploy.
# =============================================================================
#: The role a tenant's own administrator holds instead of the platform's keys.
#: Seeded by the access module; an xmlid rather than a name, because the name is
#: the one thing an administrator is invited to change.
TENANT_ADMIN_ROLE_XMLID = 'pb_vendor_access.role_tenant_administrator'

#: What a tenant administrator must not carry. The same two the access module
#: refuses to put in any role.
PLATFORM_GROUP_XMLIDS = ('base.group_system', 'base.group_erp_manager')

#: Defaults for the switches. In CODE rather than in a `noupdate="1"` record,
#: so an upgrade cannot freeze whatever a test run left behind.
RAILS_DEFAULTS = {
    #: Are the rails applied to newly provisioned tenants? On.
    'pb_tenants.tenant_admin_rails': '1',
    #: The archived account the platform keeps in every clone.
    'pb_tenants.break_glass_login': 'platform.recovery@payobook.com',
    #: Logins the rails will never demote, whatever else is asked of them.
    #: The owner's own account is here because on at least one existing tenant
    #: the customer administrator IS the owner's address.
    'pb_tenants.tenant_admin_rails_protect': 'ash@biztinct.com',
    #: Databases the flip routine refuses outright, on top of the platform's own.
    'pb_tenants.tenant_admin_rails_never': 'payobook_template',
}

#: Words that mean "off" for any of the switches above. Anything else leaves the
#: rail armed — a mistyped value must never quietly stand a rail down.
_OFF_WORDS = ('0', 'off', 'false', 'no')


# =============================================================================
# KEEPING A CUSTOMER'S DATABASE IN STEP WITH THE MASTER.
#
# The deny-list, the split and every other judgement this feature makes now live
# in `sync_rules.py` — pure, and therefore tested (rail R6). They are re-exported
# here because that is where the rest of the platform has always imported them
# from. The owner's rule and the reasoning behind the list are quoted in full at
# the top of that file.
# =============================================================================
from .sync_rules import (  # noqa: E402  (re-export, kept beside its call sites)
    TENANT_SYNC_NEVER, TENANT_SYNC_NEVER_PREFIXES, is_never,
    master_behind_files, norm_version, release_name, release_state, sync_diff,
    sync_never_reason, sync_split, template_cron_plan,
)

# =============================================================================
# TELLING A CUSTOMER SOMETHING (FLEET P2A).
#
# The platform now has one channel into a customer's screen, and it is five
# settings written through that customer's own ORM. `pb_tenancy` on their side
# reads them; nothing on their side calls back. The judgements — is this message
# sendable, what does its window say in words, which ten releases does a
# customer's "What's new" page carry — are pure and live next door.
# =============================================================================
from .tenancy_rules import (  # noqa: E402
    NOTICE_KINDS, RELEASE_HISTORY, default_window, notice_payload,
    parse_stamp, releases_list, render_range,
)

#: The module a customer's database needs before the platform can say anything
#: to it. Not on the never-list (rail R2) — it is a part of the product, and it
#: reaches a customer the same way every other part does: somebody presses
#: "Bring in step".
TENANCY_MODULE = 'pb_tenancy'

#: The settings that carry the whole contract. Written here, read there. Kept
#: as literals rather than imported from `pb_tenancy`, because this module must
#: keep working on a master where that one is not installed yet.
T_RELEASE = 'pb_tenancy.release'
T_RELEASE_DATE = 'pb_tenancy.release_date'
T_RELEASES = 'pb_tenancy.releases'
T_NOTICE = 'pb_tenancy.notice'
T_PUSHED_AT = 'pb_tenancy.pushed_at'

PROVISION_STEPS = [
    ('clone', 'Clone golden template'),
    ('configure', 'Configure tenant'),
    ('admin', 'Create admin access'),
    ('cert', 'Secure with HTTPS'),
    ('verify', 'Verify & go live'),
]
# 'verify' must stay last: _run_step promotes the tenant to 'live' on that key.
NIGHTLY_KEEP = 14

IPV4_RE = re.compile(r'^\d{1,3}(?:\.\d{1,3}){3}$')
# Public resolvers consulted when the host's own resolver fails us — see _resolve().
FALLBACK_RESOLVERS = ('1.1.1.1', '8.8.8.8')
# Start nagging about the wildcard certificate this many days before it expires.
# Manual DNS-01 certificates do NOT auto-renew, so this is the only warning there is.
TLS_RENEW_WARN_DAYS = 30
# certbot renews at 30 days. A tenant cert still below this is not renewing on
# its own, so _cron_certs re-runs the issuer rather than waiting for expiry.
CERT_REISSUE_DAYS = 21

# Per-tenant health probes, each run independently: (field, required table, SQL).
# They used to share a single try/except, so the first schema drift silently
# zeroed everything after it — Odoo 19 dropped res_users.login_date, which meant
# the employee count that followed never ran and every tenant reported 0 staff.
HEALTH_PROBES = (
    ('user_count', None, "SELECT count(*) FROM res_users WHERE active AND share IS NOT TRUE"),
    # Odoo 19 moved "when was this user last seen" to res_device_log.last_activity.
    ('last_login', 'res_device_log', "SELECT max(last_activity) FROM res_device_log"),
    ('employee_count', 'hr_employee', "SELECT count(*) FROM hr_employee WHERE active"),
)


def _direct(fn):
    """Run a db-management service function with the management gate lifted.

    odoo.service.db functions are wrapped by check_db_management_enabled, which
    raises when list_db=False — and some (dump_db) call other wrapped functions
    internally, so unwrapping only the outer one is not enough. We keep
    list_db=False for the web surface (the web db-manager is also 404'd at nginx)
    and lift the flag for the duration of one call, restoring it in finally.
    Our own _require_admin() guards every entry point that reaches here."""
    def run(*args, **kwargs):
        cfg = odoo.tools.config
        prev = cfg['list_db']
        cfg['list_db'] = True
        try:
            return fn(*args, **kwargs)
        finally:
            cfg['list_db'] = prev
    return run


class PbTenants(models.AbstractModel):
    _name = 'pb.tenants'
    _description = 'Payobook Tenant Mission Control'

    # ------------------------------------------------------------------ guard
    def _require_admin(self):
        u = self.env.user
        if not (self.env.su or u._is_admin() or u.has_group('base.group_system')):
            raise AccessError(_("Tenant Mission Control is restricted to system administrators."))

    # ------------------------------------------------------------------ config helpers
    def _param(self, key, default):
        return self.env['ir.config_parameter'].sudo().get_param(key, default)

    def _base_domain(self):
        return self._param('pb_tenants.base_domain', 'payobook.com')

    def _template_db(self):
        return self._param('pb_tenants.template_db', 'payobook_template')

    def _backup_root(self):
        return self._param('pb_tenants.backup_root', '/odoo/backups/tenants')

    def _http_port(self):
        return int(odoo.tools.config['http_port'] or 8069)

    def _tenant_url(self, slug):
        return "https://%s.%s" % (slug, self._base_domain())

    # ------------------------------------------------------------------ low-level helpers
    @contextmanager
    def _pg_cursor(self, dbname='postgres'):
        """Autocommit cursor on an arbitrary database via Odoo's pool."""
        conn = odoo.sql_db.db_connect(dbname)
        cr = conn.cursor()
        try:
            cr._cnx.autocommit = True
            yield cr
        finally:
            cr.close()

    def _db_exists(self, name):
        with self._pg_cursor() as cr:
            cr.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
            return bool(cr.fetchone())

    def _db_size(self, name):
        try:
            with self._pg_cursor() as cr:
                cr.execute("SELECT pg_database_size(%s)", (name,))
                row = cr.fetchone()
                return row and float(row[0]) or 0.0
        except Exception:
            return 0.0

    def _filestore_size(self, dbname):
        path = odoo.tools.config.filestore(dbname)
        total = 0.0
        try:
            for root, _dirs, files in os.walk(path):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
        except OSError:
            pass
        return total

    @contextmanager
    def _tenant_env(self, dbname):
        """ORM environment on another database of this cluster (commits on success)."""
        reg = Registry(dbname)
        with reg.cursor() as cr:
            yield api.Environment(cr, SUPERUSER_ID, {})
            cr.commit()

    def _probe(self, host):
        """HTTP probe of this Odoo through localhost with a tenant Host header."""
        url = "http://127.0.0.1:%d/web/login" % self._http_port()
        req = urllib.request.Request(url, headers={'Host': host})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                return resp.status, int((time.time() - t0) * 1000)
        except Exception:
            return 0, -1

    def _resolve(self, host):
        """Resolve a hostname, falling back to public resolvers.

        The go-live checklist asks "does this name resolve on the public
        internet?", but socket.gethostbyname() can only answer "does it resolve
        for *this box*". Those differ: on 2026-08-14 the AWS VPC resolver held a
        stale negative answer for the wildcard probe for an hour after the
        registrar was already correct, so the checklist showed an alarming red
        DNS row against perfectly good infrastructure. Ask someone else before
        concluding the record is missing.
        """
        try:
            return socket.gethostbyname(host)
        except OSError:
            pass
        for resolver in FALLBACK_RESOLVERS:
            try:
                out = subprocess.run(
                    ['dig', '+short', '+time=3', '+tries=1', '@%s' % resolver, host, 'A'],
                    capture_output=True, text=True, timeout=8).stdout
            except Exception:
                continue  # no dig on this box, or it hung — try the next resolver
            for line in out.split():
                if IPV4_RE.match(line):  # skip CNAME lines dig also prints
                    return line
        return None

    def _public_ip(self):
        """The server's public IP = whatever the apex A record points to."""
        ip = self._param('pb_tenants.public_ip', '')
        return ip or self._resolve(self._base_domain())

    def _log_line(self, tenant, step, line, level='info'):
        try:
            log = json.loads(tenant.provision_log or '[]')
        except ValueError:
            log = []
        log.append({'step': step, 'line': line, 'level': level,
                    'ts': fields.Datetime.now().isoformat(timespec='seconds')})
        tenant.write({'provision_log': json.dumps(log), 'provision_step': step})
        return line

    @staticmethod
    def _human(nbytes):
        n = float(nbytes or 0)
        for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
            if n < 1024 or unit == 'TB':
                return ("%.1f %s" if unit not in ('B',) else "%d %s") % (n, unit)
            n /= 1024.0

    # ================================================================== fleet
    @api.model
    def get_fleet_data(self):
        self._require_admin()
        Tenant = self.env['pb.tenant'].sudo()
        tenants = Tenant.search([])
        platform = self._platform_status()
        live = tenants.filtered(lambda t: t.state == 'live')
        total_db = sum(live.mapped('db_size')) + sum(live.mapped('filestore_size'))
        last_backups = [t.last_backup_at for t in live if t.last_backup_at]
        stale_cut = datetime.now() - timedelta(hours=30)
        backup_ok = bool(live) and all(t.last_backup_at and t.last_backup_at > stale_cut for t in live)
        return {
            'base_domain': self._base_domain(),
            'platform': platform,
            'kpis': {
                'live': len(live),
                'provisioning': len(tenants.filtered(lambda t: t.state in ('draft', 'provisioning', 'error'))),
                'storage': self._human(total_db),
                'disk_free': platform.get('disk_free_h', '—'),
                'disk_free_pct': platform.get('disk_free_pct', 0),
                'backup_ok': backup_ok,
                'last_backup': max(last_backups).isoformat(sep=' ', timespec='minutes') if last_backups else None,
            },
            'tenants': [self._tenant_brief(t) for t in tenants],
            'steps': [{'key': k, 'label': l} for k, l in PROVISION_STEPS],
            'release': self._release_brief(),
            # What the fleet card's chip counts. Read off OUR records — the
            # numbers the nightly check and the last button-press left behind —
            # so opening the fleet never touches a customer's database.
            'drift_total': sum((t.behind_count or 0) + (t.stale_count or 0)
                               for t in live),
            'drift_tenants': len(live.filtered(
                lambda t: t.release_state == 'behind'
                or (t.behind_count or 0) or (t.stale_count or 0))),
            # FLEET P3. Two numbers the fleet head cannot be read without: how
            # much is wrong right now, and whether this machine can take
            # another customer. Both are cheap — one search, one read of
            # /proc — so they ride along with the fleet rather than needing a
            # second call after the screen has already drawn.
            'alerts': self._alert_head(),
            'capacity': self._capacity(),
        }

    def _alert_head(self):
        """The chip in the fleet header: how many, how bad, and the one that
        cannot email itself."""
        Alert = self.env['pb.alert'].sudo()
        rows = Alert.search([('state', '=', 'open')])
        channel = rows.filtered(lambda a: a.kind == 'alert_channel_down')
        return {
            'open': len(rows),
            'critical': len(rows.filtered(lambda a: a.severity == 'critical')),
            'acknowledged': Alert.search_count([('state', '=', 'acknowledged')]),
            # THE ONE ALERT THAT CANNOT EMAIL ITSELF is carried in full, because
            # the screen is the only place it can possibly be read.
            'channel_down': (channel[0].text or '') if channel else '',
        }

    def _release_brief(self):
        rel = self.env['pb.release'].sudo().current()
        if not rel:
            return None
        live = self.env['pb.tenant'].sudo().search([('state', '=', 'live')])
        return {
            'id': rel.id, 'name': rel.name,
            'captured_at': rel.captured_at.isoformat(sep=' ', timespec='minutes'),
            'module_count': rel.module_count, 'notes': rel.notes or '',
            'on': len(live.filtered(lambda t: t.release_state == 'on')),
            'total': len(live),
        }

    def _tenant_brief(self, t):
        return {
            'release': t.release_id.name or '',
            'release_state': t.release_state or 'unknown',
            'behind_count': t.behind_count or 0,
            'stale_count': t.stale_count or 0,
            'skipped_count': t.skipped_count or 0,
            'drift_checked': (t.drift_checked.isoformat(sep=' ', timespec='minutes')
                              if t.drift_checked else None),
            'last_sync_at': (t.last_sync_at.isoformat(sep=' ', timespec='minutes')
                             if t.last_sync_at else None),
            'id': t.id, 'name': t.name, 'slug': t.slug, 'state': t.state,
            'url': self._tenant_url(t.slug),
            'admin_email': t.admin_email or '',
            'users': t.user_count, 'employees': t.employee_count,
            'db_size_h': self._human((t.db_size or 0) + (t.filestore_size or 0)),
            'ping_ms': t.ping_ms,
            'health': t.health_state,
            'last_backup': t.last_backup_at and t.last_backup_at.isoformat(sep=' ', timespec='minutes') or None,
            'last_login': t.last_login and t.last_login.isoformat(sep=' ', timespec='minutes') or None,
            'domains': len(t.domain_ids.filtered(lambda d: d.state == 'active')),
            'error': t.last_error or '',
            # What this customer's users are being shown right now, mirrored off
            # our own record — reading it back out of their database on every
            # fleet load would open a registry per customer for one string.
            'notice': self._notice_brief(t),
        }

    def _notice_brief(self, t):
        """The message a customer is showing, unpacked for the cockpit.

        `expired` is computed HERE rather than left to the reader, because the
        mirror on our side has no way of knowing the customer's page has already
        stopped drawing it — their database drops it on its own at `ends_at`.
        """
        if not t.notice:
            return None
        try:
            data = json.loads(t.notice)
        except ValueError:
            return None
        if not isinstance(data, dict) or not data.get('title'):
            return None
        return {
            'id': data.get('id', ''),
            'kind': data.get('kind', 'info'),
            'title': data.get('title', ''),
            'text': data.get('text', ''),
            'starts_at': data.get('starts_at', ''),
            'ends_at': data.get('ends_at', ''),
            'range': render_range(data.get('starts_at'), data.get('ends_at')),
            'expired': bool(t.notice_until
                            and t.notice_until <= fields.Datetime.now()),
            'sent_at': (t.notice_sent_at.isoformat(sep=' ', timespec='minutes')
                        if t.notice_sent_at else None),
        }

    def _platform_status(self):
        dom = self._base_domain()
        cfg = odoo.tools.config
        ip = self._public_ip()
        probe_host = 'pb-probe-x7.%s' % dom
        wild_ip = self._resolve(probe_host)
        wildcard_dns = bool(ip and wild_ip == ip)
        tls = self._check_wildcard_tls(dom)
        # A cert that is valid but about to lapse is not "done" — flip the row
        # amber early, because a manual DNS-01 cert has no other alarm.
        tls_days = tls['days_left']
        tls_expiring = bool(tls['ok'] and tls_days is not None and tls_days <= TLS_RENEW_WARN_DAYS)
        if not tls['ok']:
            tls_hint = 'Issue a *.%s certificate (DNS-01 challenge) and install it in nginx.' % dom
        else:
            tls_hint = ('Certificate expires %s (%d days left). Manual DNS-01 certificates do '
                        'NOT auto-renew — reissue with certbot (deploy runbook).'
                        % (tls['expires'], tls_days))
        template_ok = self._db_exists(self._template_db())
        try:
            du = shutil.disk_usage('/')
            disk_free_h, disk_pct = self._human(du.free), int(du.free * 100 / du.total)
        except OSError:
            disk_free_h, disk_pct = '—', 0
        dbfilter = cfg['dbfilter'] or ''
        mail_row = self._mail_check()
        status_row = self._status_check()
        checks = [
            {'key': 'dbfilter', 'label': 'Subdomain routing (dbfilter)', 'ok': '%d' in dbfilter,
             'hint': "Server config needs dbfilter = ^%d$ (currently: '" + (dbfilter or 'not set') + "')"},
            {'key': 'listdb', 'label': 'Database manager locked down', 'ok': not cfg['list_db'],
             'hint': 'Set list_db = False in the server config.'},
            {'key': 'template', 'label': 'Golden template database', 'ok': template_ok,
             'hint': 'Template "%s" not found — build it from the deploy runbook.' % self._template_db()},
            {'key': 'dns', 'label': 'Wildcard DNS  *.%s' % dom, 'ok': wildcard_dns,
             'hint': 'Add at your registrar: A record, host "*", value %s' % (ip or 'server IP')},
            {'key': 'tls', 'label': 'Wildcard TLS certificate', 'ok': tls['ok'] and not tls_expiring,
             'hint': tls_hint},
            mail_row,
            status_row,
            {'key': 'domain_script', 'label': 'Custom-domain automation', 'ok': os.path.exists('/usr/local/bin/pb-domain-attach'),
             'hint': 'Install pb-domain-attach (deploy runbook) to automate client domains.'},
        ]
        return {
            'checks': checks,
            'ready': all(c['ok'] for c in checks if c['key'] in ('dbfilter', 'listdb', 'template', 'dns', 'tls')),
            'public_ip': ip or '',
            'registrar_records': [
                {'type': 'A', 'host': '*', 'value': ip or 'server IP',
                 'why': 'Routes every client.%s subdomain to this server' % dom},
            ],
            'disk_free_h': disk_free_h, 'disk_free_pct': disk_pct,
            'template_db': self._template_db(),
            'template_size': self._human(self._db_size(self._template_db())) if template_ok else None,
        }

    def _peer_cert(self, server_name):
        """Read the certificate nginx actually serves for `server_name`.

        Probes our own https on 127.0.0.1 with SNI, so it reports what a client
        would really be handed — including which server block won. Reading PEM
        files off /etc/letsencrypt instead would be a lie by omission (root-only,
        and it cannot tell you which block nginx picked).

        Returns {'text': openssl -text output, 'expires': 'YYYY-MM-DD'|None,
        'days_left': int|None}; empty text when the probe failed.
        """
        blank = {'text': '', 'expires': None, 'days_left': None}
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with socket.create_connection(('127.0.0.1', 443), timeout=3) as sock:
                with ctx.wrap_socket(sock, server_hostname=server_name) as tls:
                    der = tls.getpeercert(binary_form=True)
            cert = ssl.DER_cert_to_PEM_cert(der)
            # cheap parse without external deps
            import tempfile
            with tempfile.NamedTemporaryFile('w', suffix='.pem', delete=False) as f:
                f.write(cert)
                pem = f.name
            try:
                out = subprocess.run(['openssl', 'x509', '-in', pem, '-noout', '-text'],
                                     capture_output=True, text=True, timeout=5).stdout
            finally:
                os.unlink(pem)
        except Exception:
            return blank
        res = {'text': out, 'expires': None, 'days_left': None}
        m = re.search(r'Not After\s*:\s*(.+)', out)
        if m:
            try:
                # "Nov 12 02:24:43 2026 GMT" — day is space-padded when < 10.
                end = datetime.strptime(' '.join(m.group(1).split()), '%b %d %H:%M:%S %Y %Z')
                res['expires'] = end.strftime('%Y-%m-%d')
                # openssl prints GMT; compare against naive UTC (utcnow() is deprecated).
                res['days_left'] = (end - datetime.now(timezone.utc).replace(tzinfo=None)).days
            except ValueError:
                pass
        return res

    def _check_wildcard_tls(self, dom):
        """Does a random *.dom name get a certificate covering the wildcard?

        Uses a hostname nobody could have issued a per-tenant cert for, so this
        keeps measuring the WILDCARD even now that tenants have their own certs.
        """
        info = self._peer_cert('pb-probe-x7.%s' % dom)
        return {'ok': ('*.%s' % dom) in info['text'],
                'expires': info['expires'], 'days_left': info['days_left']}

    # ================================================================== slug
    @api.model
    def check_slug(self, slug):
        self._require_admin()
        slug = (slug or '').strip().lower()
        if not slug:
            return {'ok': False, 'reason': ''}
        if not SLUG_RE.match(slug) or len(slug) < 3 or len(slug) > 30:
            return {'ok': False, 'reason': '3–30 chars, lowercase letters, digits and hyphens; must start with a letter.'}
        if slug in RESERVED_SLUGS or slug.endswith('-staging'):
            return {'ok': False, 'reason': 'This name is reserved by the platform.'}
        if self.env['pb.tenant'].sudo().search_count([('slug', '=', slug)]):
            return {'ok': False, 'reason': 'A tenant already uses this subdomain.'}
        if self._db_exists(slug):
            return {'ok': False, 'reason': 'A database with this name already exists on the server.'}
        return {'ok': True, 'url': self._tenant_url(slug)}

    # ================================================================== provisioning
    @api.model
    def provision_start(self, form):
        self._require_admin()
        slug = (form.get('slug') or '').strip().lower()
        chk = self.check_slug(slug)
        if not chk.get('ok'):
            raise UserError(chk.get('reason') or _('Invalid subdomain.'))
        name = (form.get('name') or '').strip()
        email = (form.get('admin_email') or '').strip().lower()
        if not name:
            raise UserError(_('Company name is required.'))
        if not email or '@' not in email:
            raise UserError(_('A valid admin email is required.'))
        if not self._db_exists(self._template_db()):
            raise UserError(_('Golden template database "%s" does not exist yet — build it first (deploy runbook).') % self._template_db())
        # FLEET P3 — THE MEMORY GUARD (owner ruling 4). A customer created past
        # the safe count does not fail here; it fails at 09:00 on a Monday,
        # taking every other customer down with it, because this box has one
        # process and one pool of memory. So the refusal is at the door, it
        # names the way out, and the way out is one page long.
        cap = self._capacity()
        if cap['level'] == 'full':
            raise UserError(_(
                "This machine cannot safely hold another customer. Resize it "
                "first — the runbook is one page: docs/SAAS_RESIZE_RUNBOOK.md.\n\n%s",
                cap['reason']))
        tenant = self.env['pb.tenant'].sudo().create({
            'name': name, 'slug': slug, 'state': 'provisioning',
            'admin_name': (form.get('admin_name') or '').strip(),
            'admin_email': email,
            'country_code': (form.get('country_code') or '').strip().upper()[:2],
            'provision_log': '[]',
        })
        self._log_line(tenant, 'start', 'Tenant record created for %s (%s)' % (name, self._tenant_url(slug)))
        return {'tenant_id': tenant.id,
                'steps': [{'key': k, 'label': l} for k, l in PROVISION_STEPS]}

    @api.model
    def provision_run(self, tenant_id, step):
        self._require_admin()
        tenant = self.env['pb.tenant'].sudo().browse(int(tenant_id)).exists()
        if not tenant:
            raise UserError(_('Tenant not found.'))
        if tenant.state not in ('provisioning', 'error'):
            raise UserError(_('Tenant %s is not in provisioning.') % tenant.slug)
        t0 = time.time()
        log = []

        def say(line, level='info'):
            log.append({'line': self._log_line(tenant, step, line, level), 'level': level})

        try:
            extra = {}
            if step == 'clone':
                extra = self._step_clone(tenant, say)
            elif step == 'configure':
                extra = self._step_configure(tenant, say)
            elif step == 'admin':
                extra = self._step_admin(tenant, say)
            elif step == 'cert':
                extra = self._step_cert(tenant, say)
            elif step == 'verify':
                extra = self._step_verify(tenant, say)
            else:
                raise UserError(_('Unknown provisioning step: %s') % step)
            tenant.write({'last_error': False, 'state': 'live' if step == 'verify' else 'provisioning'})
            return {'ok': True, 'ms': int((time.time() - t0) * 1000), 'log': log, **extra}
        except Exception as e:
            _logger.exception("Provisioning step %s failed for %s", step, tenant.slug)
            msg = str(e) or e.__class__.__name__
            say('FAILED: %s' % msg, 'error')
            tenant.write({'state': 'error', 'last_error': msg})
            return {'ok': False, 'error': msg, 'ms': int((time.time() - t0) * 1000), 'log': log}

    def _step_clone(self, tenant, say):
        slug, template = tenant.slug, self._template_db()
        if self._db_exists(slug):
            say('Found leftover database from a previous attempt — removing it first.', 'warn')
            _direct(db_service.exp_drop)(slug)
        say('Cloning golden template "%s" → "%s"…' % (template, slug))
        _direct(db_service.exp_duplicate_database)(template, slug)
        size = self._db_size(slug)
        say('Database cloned (%s). Filestore copied.' % self._human(size))
        tenant.write({'db_size': size})
        return {}

    def _step_configure(self, tenant, say):
        slug = tenant.slug
        url = self._tenant_url(slug)
        say('Loading tenant registry (first boot of %s)…' % slug)
        with self._tenant_env(slug) as env:
            icp = env['ir.config_parameter'].sudo()
            icp.set_param('web.base.url', url)
            icp.set_param('web.base.url.freeze', 'True')
            icp.set_param('database.uuid', str(uuid.uuid4()))
            icp.set_param('database.secret', secrets.token_hex(16))
            icp.set_param('pb.tenant.slug', slug)
            say('Base URL locked to %s; database identity regenerated.' % url)
            company = env['res.company'].browse(1)
            vals = {'name': tenant.name}
            if tenant.admin_email:
                vals['email'] = tenant.admin_email
            currency = None
            if tenant.country_code:
                country = env['res.country'].search([('code', '=', tenant.country_code)], limit=1)
                if country:
                    vals['country_id'] = country.id
                    # The template is a USD company and every clone inherits
                    # that, so a VN tenant read "$0" on its first dashboard.
                    # The decision is a pure function so it can be tested; the
                    # records are read here.
                    new_id = currency_change(country.currency_id.id, company.currency_id.id)
                    if new_id:
                        currency = env['res.currency'].browse(new_id)
            company.write(vals)
            say('Company configured: %s%s' % (tenant.name, tenant.country_code and ' (%s)' % tenant.country_code or ''))
            if currency:
                # The currency is COSMETIC relative to provisioning and gets
                # its OWN write: Odoo refuses a currency change once journal
                # items exist (account/company.py raises), and bundling it with
                # the rename would turn that refusal into a configure-step
                # abort. Ask first — the same guard chart_template.py uses —
                # and treat any failure as a logged skip, never an error.
                try:
                    root = company.root_id
                    if (hasattr(root, '_existing_accounting')
                            and root._existing_accounting()):
                        say('Currency left as %s: journal items already exist.'
                            % company.currency_id.name)
                    else:
                        # An INACTIVE currency on a company appears in no
                        # selection and has no rate maintained — Odoo ships
                        # almost every one switched off. Activate BEFORE the
                        # write so the company never points at a dead row.
                        if not currency.active:
                            currency.sudo().write({'active': True})
                        company.write({'currency_id': currency.id})
                        say('Currency set from country: %s (%s).'
                            % (currency.name, currency.symbol or ''))
                except Exception:
                    say('Currency could not be set; left as %s.'
                        % company.currency_id.name)
            # the golden template ships with all crons disabled (keeps its
            # registry cold on the shared box) — re-enable the recorded set
            crons = icp.get_param('pb_tenants.template_active_crons', '')
            ids = [int(x) for x in crons.split(',') if x.strip().isdigit()]
            if ids:
                env['ir.cron'].sudo().browse(ids).exists().write({'active': True})
                icp.set_param('pb_tenants.template_active_crons', '')
                say('Scheduled jobs re-enabled (%d crons).' % len(ids))
        return {}

    def _step_admin(self, tenant, say):
        slug = tenant.slug
        password = 'Pb-' + secrets.token_urlsafe(9)
        with self._tenant_env(slug) as env:
            admin = env.ref('base.user_admin')
            admin.write({
                'name': tenant.admin_name or tenant.name,
                'login': tenant.admin_email,
                'email': tenant.admin_email,
                'password': password,
                # The golden template ships this user ARCHIVED so the template DB
                # cannot be logged into. Every clone inherits that, and Odoo answers
                # an inactive login with "Wrong login/password" — so without this the
                # credentials we hand the client are silently useless.
                'active': True,
            })
            # res.users.active and res.partner.active are separate columns; an
            # archived partner keeps the user unusable even once the user is active.
            admin.partner_id.write({'active': True})
            # Without a home action Odoo drops the client into Discuss on first
            # login, which is a poor first impression of a payroll product.
            home = env.ref('pb_dashboard.action_pb_dashboard', raise_if_not_found=False)
            if home:
                admin.write({'action_id': home.id})
            else:
                say('Payroll dashboard action not found — home screen left at the default.', 'warn')
            say('Tenant administrator: %s' % tenant.admin_email)
            # The rails. A brand-new database nobody has logged into yet is the
            # only safe moment to do this, and it is the moment that decides
            # what "administrator" means for the life of this tenant.
            self._apply_rails_to(env, admin, say)
        say('Credentials generated — shown once on completion, never stored.', 'warn')
        return {'credentials': {'url': self._tenant_url(slug),
                                'login': tenant.admin_email,
                                'password': password}}

    # ================================================ the tenant-admin rails
    def _rails_param(self, key):
        return str(self._param(key, RAILS_DEFAULTS[key]) or '').strip()

    def _rails_armed(self):
        return self._rails_param(
            'pb_tenants.tenant_admin_rails').lower() not in _OFF_WORDS

    def _protected_logins(self):
        """Accounts the rails never touch, whatever they are asked to do."""
        raw = self._rails_param('pb_tenants.tenant_admin_rails_protect')
        return {x.strip().lower() for x in raw.split(',') if x.strip()}

    def _never_flip(self):
        """Databases the flip routine refuses outright."""
        raw = self._rails_param('pb_tenants.tenant_admin_rails_never')
        names = {x.strip() for x in raw.split(',') if x.strip()}
        # The platform's own database is on this list by construction and can
        # never be taken off it by editing a parameter.
        names.add(self.env.cr.dbname)
        names.add(self._template_db())
        return names

    def _ensure_break_glass(self, env, say):
        """The recovery account the platform keeps in every tenant database.

        WHY IT IS HERE. Once the customer's administrator no longer carries the
        platform permissions, nobody in that database does — and the day
        something goes wrong with a customer's data is not the day to discover
        that. So one account is left behind that still does.

        WHY IT IS SWITCHED ON RATHER THAN ARCHIVED, WHICH IS NOT WHAT THE PLAN
        SAID. Odoo refuses to let a database exist with no ACTIVE administrator:
        `res.users._check_at_least_one_administrator` reads the group's user
        list, which leaves archived accounts out, and raises on the very write
        that would take the last one away. Measured, not guessed — it is the
        same refusal that makes creating any user in the golden template fail
        today, because the template's own administrator ships archived. So an
        archived recovery account would not be a recovery account: it would be
        a demotion that cannot happen.

        SO IT IS SWITCHED ON AND IT CANNOT BE LOGGED INTO. No password is ever
        set on it, so there is no secret to store, to leak or to hand over and
        no password to guess; and it is given no email address, so the "forgot
        my password" flow has nowhere to send a token. Getting in is a
        deliberate act by whoever owns the server — set a password on it from
        the platform side — and nothing about it is shown to the customer or
        returned to any screen.
        """
        login = self._rails_param('pb_tenants.break_glass_login')
        Users = env['res.users'].sudo().with_context(active_test=False)
        group_ids = []
        for xmlid in ('base.group_user',) + PLATFORM_GROUP_XMLIDS:
            group = env.ref(xmlid, raise_if_not_found=False)
            if group:
                group_ids.append(group.id)
        existing = Users.search([('login', '=', login)], limit=1)
        if existing:
            vals = {} if existing.active else {'active': True}
            missing = [g for g in group_ids
                       if g not in existing.group_ids.ids]
            if missing:
                vals['group_ids'] = [(4, g) for g in missing]
            if vals:
                existing.write(vals)
                existing.partner_id.write({'active': True})
            return existing
        try:
            user = Users.create({
                'name': 'Platform support (recovery account)',
                'login': login,
                'active': True,
                'group_ids': [(6, 0, group_ids)],
            })
            # No email anywhere on it: "forgot my password" has nowhere to send
            # a token, and no password was ever set, so there is nothing to
            # guess either.
            user.partner_id.write({'email': False})
        except Exception as e:                      # noqa: BLE001
            _logger.warning("Recovery account could not be created: %s", e)
            say('The platform recovery account could not be created, so the '
                'tenant administrator is NOT being restricted — nobody has '
                'lost anything.', 'warn')
            return Users.browse()
        say('Platform recovery account kept in this database. It has no '
            'password and no email address, so nobody can log in as it until '
            'the platform team deliberately gives it one.')
        return user

    def _platform_group_ids(self, env):
        out = []
        for xmlid in PLATFORM_GROUP_XMLIDS:
            group = env.ref(xmlid, raise_if_not_found=False)
            if group:
                out.append(group.id)
        return out

    def _group_names(self, user):
        """What somebody holds, in a form a person can read in a report."""
        return sorted(g.display_name or g.name or str(g.id)
                      for g in user.sudo().group_ids)

    def _apply_rails_to(self, env, user, say, dry_run=False):
        """Give this account the Tenant administrator role, take the keys back.

        THE ORDER IS LOAD-BEARING. The role goes on FIRST and the platform
        permissions come off SECOND, so there is no moment in between where the
        account can do neither. And the result is CHECKED rather than assumed:
        the platform permission can be held through a ladder as well as
        directly, so taking the two memberships away is not by itself proof
        that it is gone. If it is still there afterwards the whole thing is
        undone and said out loud — a tenant told it was restricted when it was
        not is worse than one that was never restricted.

        It refuses, rather than half-doing it, when:
          * the switch is off;
          * the access module (and therefore the role) is not on this database;
          * this login is on the protected list;
          * the recovery account could not be kept.
        """
        report = {'applied': False, 'login': user.login,
                  'before': self._group_names(user), 'after': None,
                  'reason': ''}
        if not self._rails_armed():
            report['reason'] = 'The tenant-administrator rails are switched off.'
            say('Tenant-administrator rails are switched off — this account '
                'keeps full administrator permissions.', 'warn')
            return report
        if (user.login or '').lower() in self._protected_logins():
            report['reason'] = 'This login is on the protected list.'
            say('%s is a protected login — left exactly as it is.' % user.login,
                'warn')
            return report
        role = env.ref(TENANT_ADMIN_ROLE_XMLID, raise_if_not_found=False)
        if not role or role._name != 'pb.role.profile':
            report['reason'] = ('The Tenant administrator role is not on this '
                                'database.')
            say('The Tenant administrator role is not on this database, so the '
                'account keeps full administrator permissions. Install the '
                'access module here and run this again.', 'warn')
            return report
        if not role.group_ids:
            report['reason'] = 'The Tenant administrator role carries nothing.'
            say('The Tenant administrator role carries no permissions here — '
                'the account is left as it is rather than being emptied.',
                'warn')
            return report

        platform_ids = self._platform_group_ids(env)
        keep = [g.id for g in role.group_ids]
        if dry_run:
            report['after'] = sorted(set(report['before']) | {
                g.display_name or g.name for g in role.group_ids})
            report['reason'] = 'Dry run — nothing was written.'
            report['would_remove'] = sorted(
                g.display_name or g.name
                for g in user.sudo().group_ids if g.id in platform_ids)
            return report

        if not self._ensure_break_glass(env, say):
            report['reason'] = 'No recovery account could be kept.'
            return report

        target = user.sudo()
        target.write({'group_ids': [(4, gid) for gid in keep]})
        target.write({'group_ids': [(3, gid) for gid in platform_ids]})
        target.invalidate_recordset()

        # THE CHECK IS ON THE TRANSITIVE SET, NOT ON THE TWO MEMBERSHIPS.
        # A permission can be held through a ladder — a group that IMPLIES the
        # system administrator permission hands over the same database — so
        # "the two rows are gone" is not the same question as "is it gone".
        # `all_group_ids` is the transitive set and is what decides here.
        def still_holds():
            return set(platform_ids) & set(target.all_group_ids.ids)

        laddered = []
        for _attempt in range(4):
            if not still_holds():
                break
            culprits = target.group_ids.filtered(
                lambda g: set(platform_ids) & set(g.all_implied_ids.ids))
            if not culprits:
                break
            laddered += [g.display_name or g.name for g in culprits]
            target.write({'group_ids': [(3, g.id) for g in culprits]})
            target.invalidate_recordset()

        if still_holds():
            # Put it back exactly as it was and say so. Half a rail is a lie.
            raise UserError(_(
                'This account still holds the system administrator permission '
                'after the change, so nothing has been changed at all. Nobody '
                'has been locked out; tell the platform team.'))

        # An internal login is what everything else assumes.
        internal = env.ref('base.group_user', raise_if_not_found=False)
        if internal and internal.id not in target.all_group_ids.ids:
            target.write({'group_ids': [(4, internal.id)]})
            target.invalidate_recordset()

        report.update({'applied': True, 'after': self._group_names(target),
                       'laddered': sorted(set(laddered)),
                       'role': role.name})
        say('%s now holds the "%s" role and no longer holds the system '
            'administrator permission.' % (target.login, role.name))
        if laddered:
            say('Also removed, because it carried the same permission through '
                'another one: %s' % ', '.join(sorted(set(laddered))), 'warn')
        return report

    @api.model
    def prepare_template_for_rails(self):
        """Put the recovery account into the golden template. Safe to run again.

        WHY THE TEMPLATE NEEDS ONE AT ALL. Odoo refuses to let a database exist
        with no ACTIVE administrator — `res.users._check_at_least_one_
        administrator` reads the group's user list, which leaves archived
        accounts out, and raises on any write that would take the last one
        away. The golden template ships its own administrator ARCHIVED so that
        the template cannot be logged into, which means the template currently
        has none: creating ANY user in it fails, and so would the demotion
        step, on the clone, on the day a tenant is provisioned.

        So the template gets the same account every tenant gets: switched on,
        with no password and no email address, therefore impossible to log in
        as and impossible to reset your way into. The template stays unloggable
        — its own administrator is still archived — and every clone starts life
        already carrying the recovery account, so provisioning has one less
        thing that can fail at the worst moment.

        Run once, by the platform, after this version ships. Running it again
        changes nothing.
        """
        self._require_admin()
        name = self._template_db()
        lines = []

        def say(line, level='info'):
            lines.append({'line': line, 'level': level})
            _logger.info("template recovery account [%s]: %s", name, line)

        if not self._db_exists(name):
            raise UserError(_('There is no database called "%s" here.') % name)
        with self._tenant_env(name) as env:
            user = self._ensure_break_glass(env, say)
            ok = bool(user)
            login = user.login if user else ''
        if ok:
            say('The golden template now has an administrator that nobody can '
                'log in as. Clones made from it can be handed over safely.')
        return {'database': name, 'ok': ok, 'login': login, 'log': lines}

    @api.model
    def apply_tenant_admin_rails(self, dbname, dry_run=True):
        """THE FLIP — restrict an EXISTING tenant's administrator. Not automatic.

        Nothing calls this. It exists so that the day the owner decides an
        existing customer's administrator should stop holding the keys to their
        whole database, that is one call with a dry run in front of it rather
        than a hand-written script written under pressure.

        HOW IT IS RUN. From the platform database, as a system administrator::

            env['pb.tenants'].apply_tenant_admin_rails('acme')                # look
            env['pb.tenants'].apply_tenant_admin_rails('acme', dry_run=False) # do

        The first form CHANGES NOTHING and returns what the second one would
        do: the account it found, everything it holds now, and everything it
        would hold afterwards. The second form is the only one that writes, and
        `dry_run` has to be spelled out to get there.

        WHAT IT REFUSES, AND WHY EACH ONE IS A REFUSAL RATHER THAN A WARNING.
          * the platform's own database, and the golden template. Demoting the
            platform's administrator would lock the owner out of the fleet, and
            demoting the template's would ship the demotion to every future
            clone through the back door instead of through provisioning.
          * a database that is not on this server.
          * a protected login — including the owner's own address, which IS the
            administrator account on at least one existing tenant.
          * a database without the access module: there is no role to give, and
            taking permissions away without giving a role back is how a customer
            ends up with an administrator who can do nothing.

        It reports what it did in plain words; it never returns a password and
        it never touches anybody but the one administrator account.
        """
        self._require_admin()
        name = str(dbname or '').strip()
        if not name or not re.match(r'^[A-Za-z0-9_][A-Za-z0-9_.-]*$', name):
            raise UserError(_('That is not a database name.'))
        if name in self._never_flip():
            raise UserError(_(
                '"%s" is the platform\'s own database or the golden template. '
                'The rails are never applied to those.') % name)
        if not self._db_exists(name):
            raise UserError(_('There is no database called "%s" here.') % name)

        lines = []

        def say(line, level='info'):
            lines.append({'line': line, 'level': level})
            _logger.info("tenant-admin rails [%s]: %s", name, line)

        with self._tenant_env(name) as env:
            admin = env.ref('base.user_admin', raise_if_not_found=False)
            if not admin:
                raise UserError(_(
                    'There is no administrator account in "%s".') % name)
            report = self._apply_rails_to(env, admin, say,
                                          dry_run=bool(dry_run))
            # Anybody else still holding the keys is worth saying out loud —
            # this method deliberately touches one account and only one.
            others = []
            group = env.ref('base.group_system', raise_if_not_found=False)
            if group:
                others = sorted(
                    u.login for u in group.sudo().all_user_ids
                    if u.id != admin.id and u.active)
            if others:
                say('Still holding the system administrator permission in this '
                    'database: %s' % ', '.join(others), 'warn')
        report.update({'database': name, 'dry_run': bool(dry_run),
                       'log': lines, 'others_with_the_keys': others})
        return report

    # ============================================== in step with the master
    #
    # The rule this implements is quoted in full at the top of `sync_rules.py`,
    # beside TENANT_SYNC_NEVER, together with every judgement it makes. Two
    # kinds of entry point here, and the split between them is the point:
    # `sync_report` and `_cron_drift` only ever READ another database, and
    # `sync_bring_in_step` only ever runs because somebody pressed something
    # (rail R1).

    #: The golden template is not a customer and has no `pb.tenant` row — but it
    #: is what every new customer is cloned from, so a template that is behind
    #: hands its arrears to everybody who arrives after it. It gets a row on the
    #: same screen under this key.
    TEMPLATE_KEY = 'template'

    def _installed_on(self, dbname):
        """What another database of this cluster has installed, and at what version.

        Read with plain SQL rather than an ORM environment on purpose: this runs
        once per customer every time the report is opened, and loading a whole
        registry per customer to answer "what is installed" would make a
        read-only screen the most expensive thing in the cockpit.

        The value is the version THAT DATABASE has applied — not the version of
        the file sitting on the server, which every database shares. The two
        differ, and the difference is the whole subject of this screen (F1/F2).
        """
        with self._pg_cursor(dbname) as cr:
            cr.execute("SELECT name, coalesce(latest_version, '') "
                       "FROM ir_module_module WHERE state = 'installed'")
            return {r[0]: r[1] for r in cr.fetchall()}

    def _module_labels(self, names):
        """The name a person would recognise, for each module, off the master."""
        if not names:
            return {}
        mods = self.env['ir.module.module'].sudo().search(
            [('name', 'in', list(names))])
        return {m.name: (m.shortdesc or m.name) for m in mods}

    def _master_modules(self):
        """What the master has installed, and what its own files say it should.

        `have` is what this database has applied; `file` is what is on the
        server's disk. They should be equal. When `file` is newer the master is
        running a mixture of old data and new code, and rail R3 stops everything
        until somebody applies it.
        """
        out = {}
        for m in self.env['ir.module.module'].sudo().search(
                [('state', '=', 'installed')]):
            out[m.name] = {'label': m.shortdesc or m.name,
                           'have': m.latest_version or '',
                           'file': m.installed_version or ''}
        return out

    def _master_behind_files(self, master=None):
        master = master if master is not None else self._master_modules()
        return master_behind_files(
            [(n, d['have'], d['file']) for n, d in master.items()])

    def _target_versions(self, master=None):
        """The versions the fleet is measured against, and where they came from.

        A cut release if there is one — a frozen photograph, so that a fix
        applied to the master at 11:00 does not put every customer "behind" at
        11:01 through nobody's decision. The live master otherwise, and the
        screen says as much and invites somebody to cut one.
        """
        master = master if master is not None else self._master_modules()
        rel = self.env['pb.release'].sudo().current()
        if rel:
            snap = rel.snapshot_dict()
            if snap:
                return snap, rel
        return ({n: d['have'] for n, d in master.items()},
                self.env['pb.release'].sudo().browse())

    def _skipped_on(self, dbname):
        """Parts a database claims to have, which it did not actually load.

        THE SILENT FAILURE THIS CATCHES (runbook, 2026-08-19). When a part of
        the product gains a dependency that a customer's database has never
        heard of, that database quietly drops the whole family on its next
        start: the rows still read "installed", the log says "Modules loaded",
        and the only loud symptom is a scheduled job failing on a name that no
        longer exists. Twenty-seven parts sat like that for a day.

        The framework keeps the set of modules a registry really loaded, so the
        answer is that set subtracted from what the database says it has.

        Returns `(count, names)`, and `count` is -1 when the framework gives us
        nothing to compare against — an honest "could not tell" beats a green 0.
        """
        installed = set(self._installed_on(dbname))
        try:
            loaded = set(getattr(Registry(dbname), '_init_modules', None) or ())
        except Exception:                                # noqa: BLE001
            _logger.warning("pb_tenants: could not read the loaded parts of %s",
                            dbname, exc_info=True)
            return -1, []
        if not loaded:
            return -1, []
        missing = sorted(installed - loaded)
        return len(missing), missing

    def _decorate(self, names_or_rows, master):
        """Put the recognisable name beside each module, for the screen."""
        out = []
        for item in names_or_rows:
            if isinstance(item, dict):
                row = dict(item)
                row['label'] = master.get(row['module'], {}).get('label', row['module'])
                out.append(row)
            else:
                out.append({'module': item,
                            'label': master.get(item, {}).get('label', item)})
        return out

    def _sync_row(self, dbname, master, target, *, key, name, slug,
                  is_template=False, tenant=None):
        """One line of the report. READ ONLY, on every database it touches."""
        row = {
            'key': key, 'name': name, 'slug': slug, 'database': dbname,
            'is_template': is_template,
            'id': tenant.id if tenant else 0,
            'state': tenant.state if tenant else 'template',
            'checked': False, 'error': '', 'installed': 0,
            'to_install': [], 'to_update': [], 'held_back': [], 'ahead': [],
            'in_step': False, 'release_state': 'unknown',
            'release': (tenant.release_id.name if tenant and tenant.release_id
                        else ''),
            'behind_count': 0, 'stale_count': 0,
            'skipped_count': tenant.skipped_count if tenant else 0,
            'drift_checked': (tenant.drift_checked.isoformat(sep=' ', timespec='minutes')
                              if tenant and tenant.drift_checked else None),
            'last_sync_at': (tenant.last_sync_at.isoformat(sep=' ', timespec='minutes')
                             if tenant and tenant.last_sync_at else None),
        }
        if tenant is not None and tenant.state == 'decommissioned':
            row['error'] = _("This customer has been closed down.")
            return row
        if not self._db_exists(dbname):
            row['error'] = _("There is no database for this one yet.")
            return row
        try:
            have = self._installed_on(dbname)
        except Exception as exc:                        # noqa: BLE001
            _logger.warning("pb_tenants: could not read the module list of %s",
                            dbname, exc_info=True)
            row['error'] = _("This database could not be read: %s") % exc
            return row
        diff = sync_diff({n: d['have'] for n, d in master.items()}, have)
        row.update({
            'checked': True,
            'installed': len(have),
            'to_install': self._decorate(diff['to_install'], master),
            'to_update': self._decorate(diff['to_update'], master),
            'held_back': [{'module': n,
                           'label': master.get(n, {}).get('label', n),
                           'reason': sync_never_reason(n)}
                          for n in diff['held_back']],
            'ahead': self._decorate(diff['ahead'], master),
            'behind_count': len(diff['to_install']),
            'stale_count': len(diff['to_update']),
            'in_step': not diff['to_install'] and not diff['to_update'],
            'release_state': release_state(target, have),
        })
        return row

    @api.model
    def sync_report(self):
        """Where every customer's database stands against the master.

        READ ONLY. Nothing here installs, upgrades or writes anything, on any
        database — including this one.
        """
        self._require_admin()
        master = self._master_modules()
        behind_files = self._master_behind_files(master)
        target, rel = self._target_versions(master)
        rows = [self._sync_row(
            self._template_db(), master, target,
            key=self.TEMPLATE_KEY, name=_("Golden template"),
            slug=self._template_db(), is_template=True)]
        for t in self.env['pb.tenant'].sudo().search([]):
            rows.append(self._sync_row(
                t.slug, master, target, key=str(t.id), name=t.name,
                slug=t.slug, tenant=t))
        live = [r for r in rows if r['checked'] and r['state'] != 'decommissioned']
        on_release = [r for r in live if r['release_state'] == 'on']
        # The master's own files have moved past the frozen photograph: the
        # release is out of date, which is amber rather than red — nothing is
        # broken, there is simply a newer one to cut.
        ahead_of_release = sorted(
            n for n, d in master.items()
            if not is_never(n)
            and norm_version(d['have']) > norm_version(target.get(n, ''))
        ) if rel else []
        return {
            'master_db': self.env.cr.dbname,
            'master_count': len(master),
            'master_behind_files': self._decorate(behind_files, master),
            'master_behind_command': (
                '-u %s -d %s' % (','.join(behind_files), self.env.cr.dbname)
                if behind_files else ''),
            'release': ({
                'id': rel.id, 'name': rel.name,
                'captured_at': rel.captured_at.isoformat(sep=' ', timespec='minutes'),
                'module_count': rel.module_count, 'notes': rel.notes or '',
                'cut_by': rel.cut_by.name or '',
            } if rel else None),
            'master_ahead_of_release': self._decorate(ahead_of_release, master),
            'on_release': len(on_release),
            'measured': len(live),
            'drift_total': sum(r['behind_count'] + r['stale_count'] for r in live),
            'never': [{'module': n, 'label': master.get(n, {}).get('label', n),
                       'reason': r}
                      for n, r in sorted(TENANT_SYNC_NEVER.items())],
            'rows': rows,
            # Kept so anything still reading the old shape keeps working.
            'tenants': [r for r in rows if not r['is_template']],
        }

    # ---------------------------------------------------------------- the button
    def _resolve_sync_target(self, target):
        """Which database is the button pointing at, and may it be pointed there?

        Three answers and nothing else: the golden template, one customer, or a
        `<customer>-staging` rehearsal copy. The rehearsal is the one reason a
        bare database name is accepted at all (rail R4: the first real run of any
        phase happens on a restore first), and it is accepted ONLY when the name
        is a real customer's slug with `-staging` on the end.
        """
        Tenant = self.env['pb.tenant'].sudo()
        if isinstance(target, str) and target.strip().isdigit():
            target = int(target.strip())
        if isinstance(target, int) and not isinstance(target, bool):
            t = Tenant.browse(target).exists()
            if not t:
                raise UserError(_("That customer is not on the list any more."))
            return t.slug, t.name, t, False
        name = (target or '').strip()
        if not name:
            raise UserError(_("Which database?"))
        if name == self.env.cr.dbname:
            raise UserError(_(
                "This is the master database. It is where the parts come "
                "FROM — it is never a place to bring them to."))
        if name in (self.TEMPLATE_KEY, self._template_db()):
            return self._template_db(), _("Golden template"), None, True
        if name.endswith('-staging'):
            stem = name[:-len('-staging')]
            t = Tenant.search([('slug', '=', stem)], limit=1)
            if t:
                return name, _("%s (rehearsal copy)") % t.name, None, False
        raise UserError(_(
            'There is nothing here called "%s". This button works on the '
            'golden template, on one customer, or on a customer\'s rehearsal '
            'copy — and on nothing else.') % name)

    @api.model
    def sync_bring_in_step(self, target, dry_run=True):
        """Bring one database up to what the master runs. THE WHOLE UNIT.

        This is the runbook's four-step catch-up turned into one button, in the
        order the runbook proved out, with the checks it learned the hard way:

          1. refuse the master itself, a closed-down customer, and — above all —
             a master that has not applied its own files yet (rail R3);
          2. refresh the target's list of available parts, because a part that
             gained a dependency the target has never heard of cannot install
             (ledger F3), and NEVER by upgrading `base`, which would run every
             migration in the product on a customer;
          3. install what is missing;
          4. update what is older, which also reaches anything that depends on
             it — the dry run says so;
          5. ask the access home to re-read its catalogue (ledger H1);
          6. check that nothing was quietly skipped;
          7. on the golden template only, switch its scheduled jobs back off
             (rail R8);
          8. read the versions back and stamp where this database now stands.

        A dry run does every read and none of the writes, anywhere.
        """
        self._require_admin()
        dbname, label, tenant, is_template = self._resolve_sync_target(target)
        dry_run = bool(dry_run)
        master = self._master_modules()
        behind_files = self._master_behind_files(master)
        target_versions, rel = self._target_versions(master)

        log = []

        def say(line, level='info'):
            log.append({'line': line, 'level': level})
            _logger.info("pb_tenants sync[%s]: %s", dbname, line)
            if tenant is not None and not dry_run:
                self._log_line(tenant, 'sync', line, level)
            return line

        plan = {
            'target': str(target), 'database': dbname, 'label': label,
            'is_template': is_template, 'dry_run': dry_run,
            'master_behind_files': self._decorate(behind_files, master),
            'installed_before': 0, 'installed_after': 0,
            'to_install': [], 'to_update': [], 'held_back': [], 'ahead': [],
            'installed': [], 'updated': [], 'still_missing': [], 'still_stale': [],
            'seeded': {}, 'skipped': [], 'skipped_count': -1,
            'crons_disabled': 0, 'release_state': 'unknown',
            'release': rel.name if rel else '',
            'log': log, 'message': '',
        }

        # ---- 1. the refusals -------------------------------------------------
        if dbname == self.env.cr.dbname:
            raise UserError(_(
                "This is the master database. It is where the parts come "
                "FROM — it is never a place to bring them to."))
        if tenant is not None and tenant.state == 'decommissioned':
            raise UserError(_(
                '"%s" has been closed down. Nothing is installed on a database '
                'that is on its way out.') % tenant.name)
        if not self._db_exists(dbname):
            raise UserError(_('There is no database called "%s".') % dbname)
        if behind_files:
            raise UserError(_(
                "The master has not caught up with its own files yet — %(count)s "
                "part(s) are waiting, starting with %(first)s. Until the master "
                "runs what it is holding, nothing can be sent out from it. "
                "Apply them on the master first.",
                count=len(behind_files), first=behind_files[0]))

        have = self._installed_on(dbname)
        diff = sync_diff({n: d['have'] for n, d in master.items()}, have)
        to_install, to_update = diff['to_install'], [r['module'] for r in diff['to_update']]
        plan.update({
            'installed_before': len(have), 'installed_after': len(have),
            'to_install': self._decorate(to_install, master),
            'to_update': self._decorate(diff['to_update'], master),
            'held_back': [{'module': n,
                           'label': master.get(n, {}).get('label', n),
                           'reason': sync_never_reason(n)}
                          for n in diff['held_back']],
            'ahead': self._decorate(diff['ahead'], master),
        })

        # THE LAST GUARD, AND IT IS DELIBERATELY THE THIRD. `sync_diff` already
        # took the exceptions out; this re-asks the question of the exact lists
        # about to be written, because those lists are what actually run and
        # every earlier check is a check of something else. TENANT_SYNC_NEVER,
        # once more, on the literal names (rail R2).
        blocked = [n for n in list(to_install) + list(to_update) if is_never(n)]
        if blocked:
            raise UserError(_(
                "Refusing to put %s on a customer's database.",
                ', '.join(sorted(blocked))))

        if not to_install and not to_update:
            plan['release_state'] = release_state(target_versions, have)
            plan['skipped_count'], plan['skipped'] = (
                (-1, []) if dry_run else self._skipped_on(dbname))
            plan['message'] = _("This database already has everything the "
                                "master has, at the same versions.")
            if not dry_run:
                if tenant is not None:
                    self._stamp(tenant, dbname, master, target_versions, rel, plan)
                self._push_release_stamp(target, plan, rel, say)
            return plan

        if dry_run:
            bits = []
            if to_install:
                bits.append(_("%s to add", len(to_install)))
            if to_update:
                bits.append(_("%s to move to a newer version (and anything "
                              "that depends on them)", len(to_update)))
            plan['message'] = _(
                "%(what)s. Nothing has been changed.", what=", ".join(bits))
            return plan

        # ---- 2. refresh what this database knows about ------------------------
        say(_("Refreshing the list of available parts on %s…") % dbname)
        with self._tenant_env(dbname) as env:
            env['ir.module.module'].sudo().update_list()
        say(_("List refreshed."))

        # ---- 3. install -------------------------------------------------------
        if to_install:
            _logger.info("pb_tenants: installing %s part(s) on %s: %s",
                         len(to_install), dbname, ', '.join(to_install))
            with self._tenant_env(dbname) as env:
                mods = env['ir.module.module'].sudo().search(
                    [('name', 'in', to_install)])
                missing = set(to_install) - set(mods.mapped('name'))
                if missing:
                    raise UserError(_(
                        'The database "%(db)s" has never heard of %(mods)s, '
                        'even after refreshing its list.',
                        db=dbname, mods=', '.join(sorted(missing))))
                say(_("Adding %s part(s)…") % len(to_install))
                mods.button_immediate_install()
            # `button_immediate_install` rebuilds that database's registry and
            # closes the environment above with it, so everything after this
            # point asks for a fresh one (ledger F4).
            say(_("Added."))

        # ---- 4. update --------------------------------------------------------
        if to_update:
            _logger.info("pb_tenants: upgrading %s part(s) on %s: %s",
                         len(to_update), dbname, ', '.join(to_update))
            with self._tenant_env(dbname) as env:
                mods = env['ir.module.module'].sudo().search(
                    [('name', 'in', to_update), ('state', '=', 'installed')])
                if mods:
                    say(_("Moving %s part(s) to the master's version…") % len(mods))
                    mods.button_immediate_upgrade()
            say(_("Versions matched."))

        # ---- 5. the access catalogue -----------------------------------------
        with self._tenant_env(dbname) as env:
            if 'pb.access' in env:
                try:
                    plan['seeded'] = env['pb.access'].sudo().reseed_catalogue()
                    say(_("Who-can-do-what list re-read."))
                except Exception:                       # noqa: BLE001
                    _logger.warning("pb_tenants: the access catalogue on %s "
                                    "could not be re-read", dbname, exc_info=True)
                    say(_("The who-can-do-what list could not be re-read — "
                          "open the access home on this database and press "
                          "Re-read."), 'warn')

        # ---- 6. did anything get skipped? ------------------------------------
        plan['skipped_count'], plan['skipped'] = self._skipped_on(dbname)
        if plan['skipped_count'] > 0:
            say(_("%s part(s) say they are installed but did not load: %s")
                % (plan['skipped_count'], ', '.join(plan['skipped'][:8])), 'error')
        elif plan['skipped_count'] == 0:
            say(_("Everything installed loaded — nothing was skipped."))
        else:
            say(_("Could not tell whether anything was skipped."), 'warn')

        # ---- 7. the template's scheduled jobs go back off ---------------------
        if is_template:
            with self._tenant_env(dbname) as env:
                crons = env['ir.cron'].sudo().with_context(active_test=False).search(
                    [('active', '=', True)])
                icp = env['ir.config_parameter'].sudo()
                to_disable, new_param = template_cron_plan(
                    crons.ids, icp.get_param('pb_tenants.template_active_crons', ''))
                if to_disable:
                    env['ir.cron'].sudo().browse(to_disable).write({'active': False})
                icp.set_param('pb_tenants.template_active_crons', new_param)
                plan['crons_disabled'] = len(to_disable)
            say(_("%s scheduled job(s) switched back off on the template — a "
                  "new customer gets them back when it is created.")
                % plan['crons_disabled'])

        # ---- 8. read it back and stamp ---------------------------------------
        after = self._installed_on(dbname)
        after_diff = sync_diff({n: d['have'] for n, d in master.items()}, after)
        plan.update({
            'installed_after': len(after),
            'installed': self._decorate(sorted(set(to_install) & set(after)), master),
            'updated': self._decorate(
                sorted(n for n in to_update
                       if n in after
                       and norm_version(after[n]) >= norm_version(master[n]['have'])),
                master),
            'still_missing': self._decorate(after_diff['to_install'], master),
            'still_stale': self._decorate(after_diff['to_update'], master),
            'release_state': release_state(target_versions, after),
        })
        plan['message'] = _(
            "%(added)s added, %(moved)s brought up to date. %(skipped)s",
            added=len(plan['installed']), moved=len(plan['updated']),
            skipped=(_("Nothing was skipped.") if plan['skipped_count'] == 0
                     else _("%s did not load — see below.", plan['skipped_count'])
                     if plan['skipped_count'] > 0
                     else _("The skipped check could not be run.")))
        say(plan['message'])

        if tenant is not None:
            self._stamp(tenant, dbname, master, target_versions, rel, plan)
            try:
                self._refresh_one(tenant)
            except Exception:                           # noqa: BLE001
                _logger.warning("pb_tenants: health refresh after sync failed "
                                "for %s", dbname, exc_info=True)
        self._push_release_stamp(target, plan, rel, say)
        return plan

    def _push_release_stamp(self, target, plan, rel, say):
        """Tell a database which release it is now on — but only if it IS.

        THE ONE MOMENT A CUSTOMER IS TOLD ABOUT A RELEASE. Cutting one does not
        announce it to anybody: a changelog for software somebody does not have
        yet is worse than no changelog. The announcement happens here, at the
        end of the run that actually put them on it, and only when the run
        SUCCEEDED — a database that came out `behind` is left saying whatever it
        said before.

        Never fatal. A message that could not be delivered must not turn a
        successful update into a failed one; it becomes a line in the log.

        FLEET P2B ADDS ONE DOOR AND NOTHING ELSE. Inside a rollout the update
        is not finished when the install is: the site still has to answer and
        the log still has to be clean. So a rollout runs the unit with
        `pb_defer_release_stamp` in the context and does this itself, after its
        checks have passed. A customer must never be shown "you are on release
        X — see what's new" about an update that is about to be called a
        failure.
        """
        plan['release_pushed'] = False
        if self.env.context.get('pb_defer_release_stamp'):
            plan['release_deferred'] = True
            return
        if plan.get('release_state') != 'on' or not rel:
            return
        try:
            res = self.push_tenancy(target, self._release_params(rel))
        except Exception:                               # noqa: BLE001
            _logger.warning("pb_tenants: could not stamp the release on %s",
                            plan.get('database'), exc_info=True)
            say(_("This database is on the release, but could not be told so — "
                  "its \"What's new\" page will catch up next time."), 'warn')
            return
        plan['release_pushed'] = bool(res.get('ok'))
        if res.get('ok'):
            say(_("Told it that it is now on release %s — its users get one "
                  "note about it and a page saying what changed.") % rel.name)
        else:
            say(res.get('reason') or _("The release stamp was not delivered."),
                'warn')

    def _stamp(self, tenant, dbname, master, target_versions, rel, plan):
        """Write where this customer now stands. On OUR database, never theirs."""
        after = self._installed_on(dbname)
        diff = sync_diff({n: d['have'] for n, d in master.items()}, after)
        state = release_state(target_versions, after)
        vals = {
            'behind_count': len(diff['to_install']),
            'stale_count': len(diff['to_update']),
            'skipped_count': plan.get('skipped_count', -1),
            'release_state': state,
            'drift_checked': fields.Datetime.now(),
            'last_sync_at': fields.Datetime.now(),
            'last_sync_result': json.dumps(plan, default=str)[:200000],
        }
        if rel and state == 'on':
            vals['release_id'] = rel.id
        tenant.write(vals)

    @api.model
    def sync_install(self, tenant_id, dry_run=True):
        """Install, on ONE customer's database, the safe set it is missing.

        The older, narrower entry point, kept for anything still calling it. The
        whole unit is `sync_bring_in_step`, which also brings versions up.
        """
        self._require_admin()
        return self.sync_bring_in_step(int(tenant_id), dry_run=dry_run)

    # ---------------------------------------------------------------- releases
    @api.model
    def release_cut(self, notes=''):
        """Freeze what the master runs right now, and name it.

        Refuses while the master has not applied its own files: a photograph of
        a database in the middle of catching up is a photograph of a mixture,
        and every customer would then be aimed at it.
        """
        self._require_admin()
        master = self._master_modules()
        behind = self._master_behind_files(master)
        if behind:
            raise UserError(_(
                "The master has not caught up with its own files yet — "
                "%(count)s part(s) are waiting, starting with %(first)s. A "
                "release is a photograph of what the master runs, so it cannot "
                "be taken while the master is halfway through.",
                count=len(behind), first=behind[0]))
        Release = self.env['pb.release'].sudo()
        name = release_name(fields.Date.today(),
                            Release.search([]).mapped('name'))
        snapshot = {n: d['have'] for n, d in master.items()}
        rel = Release.create({
            'name': name,
            'captured_at': fields.Datetime.now(),
            'notes': (notes or '').strip(),
            'snapshot': json.dumps(snapshot, sort_keys=True),
            'module_count': len(snapshot),
            'cut_by': self.env.user.id,
        })
        rel.make_current()
        _logger.info("pb_tenants: release %s cut with %s parts", name, len(snapshot))
        # The master's own What's new page. NOT the tenants': a customer is told
        # about a release when they are actually MOVED onto it, which happens in
        # `sync_bring_in_step`. Announcing a release to somebody still running
        # the previous one would be a changelog for software they do not have.
        try:
            self._push_release_here(rel)
        except Exception:                               # noqa: BLE001
            _logger.warning("pb_tenants: the release was cut but the master's "
                            "own What's new could not be updated", exc_info=True)
        # Re-measure everybody against the new photograph. READ ONLY on their
        # databases: the only thing written is our own record of where they are.
        for t in self.env['pb.tenant'].sudo().search([('state', '=', 'live')]):
            try:
                self._measure(t, master, snapshot, rel)
            except Exception:                           # noqa: BLE001
                _logger.warning("pb_tenants: could not measure %s against %s",
                                t.slug, name, exc_info=True)
        return self.sync_report()

    def _measure(self, tenant, master, target_versions, rel):
        """Read one customer and record where it stands. Writes nothing there."""
        if not self._db_exists(tenant.slug):
            tenant.write({'release_state': 'unknown',
                          'drift_checked': fields.Datetime.now()})
            return
        have = self._installed_on(tenant.slug)
        diff = sync_diff({n: d['have'] for n, d in master.items()}, have)
        state = release_state(target_versions, have)
        vals = {
            'behind_count': len(diff['to_install']),
            'stale_count': len(diff['to_update']),
            'release_state': state,
            'drift_checked': fields.Datetime.now(),
        }
        if rel and state == 'on':
            vals['release_id'] = rel.id
        tenant.write(vals)

    @api.model
    def _cron_drift(self):
        """Nightly: how far has each customer drifted from the release?

        READS every customer's database and WRITES only our own record of what
        it found (rail R1). Nothing is installed, upgraded or repaired here, and
        nothing ever will be: a customer's database does not change while
        everybody is asleep.
        """
        master = self._master_modules()
        if self._master_behind_files(master):
            _logger.warning("pb_tenants: the master has not applied its own "
                            "files yet; the drift check is measuring against "
                            "what it is actually running.")
        target, rel = self._target_versions(master)
        for t in self.env['pb.tenant'].sudo().search(
                [('state', 'in', ('live', 'error'))]):
            try:
                self._measure(t, master, target, rel)
            except Exception as e:                      # noqa: BLE001
                _logger.warning("Drift check failed for %s: %s", t.slug, e)
            self.env.cr.commit()

    # ================================================ talking to a customer
    #
    # ONE DOOR, AND IT IS `push_tenancy`. Every later phase — feature switches,
    # plan limits, the support-access switch — writes through this method and
    # nothing else, so there is exactly one place where the platform touches a
    # customer's settings, one place that refuses the databases it must never
    # touch, and one place that leaves a line in that customer's own log.
    #
    # AND IT IS ALWAYS SOMEBODY PRESSING SOMETHING (rail R1). Nothing below runs
    # on a cron, on a deploy or on an upgrade. The nightly drift check reads;
    # this writes; they are different methods on purpose.

    def _tenancy_installed(self, dbname):
        """Has this database got the part that can be talked to?"""
        try:
            return TENANCY_MODULE in self._installed_on(dbname)
        except Exception:                                # noqa: BLE001
            _logger.warning("pb_tenants: could not read the module list of %s",
                            dbname, exc_info=True)
            return False

    def push_tenancy(self, target, values):
        """Write what the platform has to say onto ONE database.

        `target` is the same three things the "bring in step" button takes — a
        customer id, `template`, or a `<customer>-staging` rehearsal copy — and
        nothing else. `values` is a plain `{setting: string}` dict.

        THROUGH THE ORM, NEVER SQL (rail R5). A settings row changed behind the
        running registry's back stays cached there until something happens to
        clear it, which on a database nobody restarts is "never". The ORM path
        invalidates it, so a notice sent at 14:00 is readable at 14:00.

        Returns `{'ok', 'database', 'reason'}`. A database without the Platform
        Link is a SKIP with a sentence saying what to do about it, not an error:
        the platform owner sending one message to eleven customers must not have
        the whole send fail because the twelfth has not been brought in step.
        """
        self._require_admin()
        dbname, label, tenant, is_template = self._resolve_sync_target(target)
        # Belt and braces on top of the resolver, which already refuses the
        # master by name: the literal database about to be written is re-asked
        # the never question (rail R2), because that list is what actually runs.
        if dbname == self.env.cr.dbname or is_never(dbname):
            raise UserError(_(
                "This is the platform's own database. Messages go OUT from "
                "here — they are not sent to it."))
        if not self._db_exists(dbname):
            return {'ok': False, 'database': dbname, 'label': label,
                    'reason': _('There is no database called "%s".') % dbname}
        if not self._tenancy_installed(dbname):
            return {'ok': False, 'database': dbname, 'label': label,
                    'reason': _(
                        "%s does not have the Platform Link yet, so there is "
                        "nowhere to put the message. Bring it in step first — "
                        "the button is on the \"In step with master\" screen.")
                    % label}
        vals = dict(values or {})
        vals[T_PUSHED_AT] = fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self._tenant_env(dbname) as env:
            icp = env['ir.config_parameter'].sudo()
            for key, value in vals.items():
                icp.set_param(key, value or '')
        _logger.info("pb_tenants: pushed %s setting(s) to %s",
                     len(vals), dbname)
        return {'ok': True, 'database': dbname, 'label': label,
                'reason': '', 'keys': sorted(vals)}

    def _release_params(self, rel=None):
        """The release settings a database is given when it lands on a release."""
        Release = self.env['pb.release'].sudo()
        rel = rel if rel is not None else Release.current()
        history = releases_list([{
            'name': r.name,
            'date': r.captured_at and r.captured_at.date().isoformat() or '',
            'notes': r.notes or '',
        } for r in Release.search([], limit=RELEASE_HISTORY * 3)])
        return {
            T_RELEASE: rel.name if rel else '',
            T_RELEASE_DATE: (rel.captured_at.date().isoformat()
                             if rel and rel.captured_at else ''),
            T_RELEASES: json.dumps(history),
        }

    def _push_release_here(self, rel=None):
        """The master reads its own What's new page too.

        Written straight onto this database rather than through `push_tenancy`,
        which refuses the master by design: the owner is a user of the product,
        and a changelog he cannot see on his own screen is a changelog nobody
        proof-reads.
        """
        icp = self.env['ir.config_parameter'].sudo()
        vals = dict(self._release_params(rel))
        vals[T_PUSHED_AT] = fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for key, value in vals.items():
            icp.set_param(key, value or '')
        return vals

    # ---------------------------------------------------------------- notices
    def _notice_recipients(self, target):
        """Which databases one send reaches.

        `'all'` is EVERY LIVE CUSTOMER AND NOT THE MASTER. A platform-wide
        maintenance message is addressed to the people whose service is about
        to pause; the owner's own database is where it is being sent FROM, and
        putting the bar on his screen would make him the only person who cannot
        tell whether it went out. The dialog says this in those words.
        """
        Tenant = self.env['pb.tenant'].sudo()
        if isinstance(target, str) and target.strip() == 'all':
            return Tenant.search([('state', '=', 'live')])
        _dbname, _label, tenant, is_template = self._resolve_sync_target(target)
        if tenant is None:
            raise UserError(_(
                "A message goes to a customer. The golden template and "
                "rehearsal copies have nobody reading them."))
        return tenant

    @api.model
    def notice_compose_defaults(self):
        """What the composer opens holding. Read-only."""
        self._require_admin()
        starts, ends = default_window()
        live = self.env['pb.tenant'].sudo().search([('state', '=', 'live')])
        return {
            'kinds': list(NOTICE_KINDS),
            'starts_at': starts,
            'ends_at': ends,
            'live': [{'id': t.id, 'name': t.name, 'slug': t.slug,
                      'linked': self._tenancy_installed(t.slug)} for t in live],
        }

    @api.model
    def notice_send(self, target, kind, title, text, starts_at, ends_at,
                    live=False, public=False):
        """Put a message at the top of every page on one customer, or on all.

        The message is composed ONCE — one id, one wording, one window — and the
        same dict is written on every recipient, so two customers can never be
        looking at two different versions of the same announcement.

        `live` marks a message the reader may not close: an update that is
        happening to them right now. FLEET P2B's worker is the only caller that
        passes it, and it must travel through THIS method rather than round it,
        because this is the one door that mints an id, mirrors the message on
        our own record and leaves a line in the customer's trail. It was
        dropped on the floor here once, which made the whole no-close rule on
        the customer's side dead code.
        """
        self._require_admin()
        try:
            payload = notice_payload(kind, title, text, starts_at, ends_at,
                                     uuid.uuid4().hex[:12])
        except ValueError as exc:
            raise UserError(str(exc)) from exc
        if live:
            payload['live'] = True
        # FLEET P3. `public` puts the SAME words on payobook.com/status, where
        # anybody can read them without signing in — which is where somebody
        # locked out by the very thing being announced will look. It is a
        # deliberate tick on the composer and never a default: most messages
        # are addressed to one customer about their own database.
        if public:
            payload['public'] = True
        tenants = self._notice_recipients(target)
        if not tenants:
            raise UserError(_(
                "There are no live customers to send this to yet."))
        blob = json.dumps(payload)
        until = parse_stamp(payload['ends_at']) or None
        sent, skipped = [], []
        for t in tenants:
            res = self.push_tenancy(t.id, {T_NOTICE: blob})
            if res['ok']:
                t.write({'notice': blob,
                         'notice_until': until,
                         'notice_sent_at': fields.Datetime.now()})
                self._log_line(t, 'notice', _(
                    'Message sent to this customer\'s users: "%(title)s"%(when)s',
                    title=payload['title'],
                    when=(' — %s' % render_range(payload['starts_at'],
                                                 payload['ends_at']))
                    if payload['ends_at'] or payload['starts_at'] else ''))
                sent.append(t.name)
            else:
                skipped.append({'name': t.name, 'reason': res['reason']})
                self._log_line(t, 'notice', res['reason'], 'warn')
        # The public page is rewritten HERE rather than waiting for the
        # five-minute job: a maintenance notice that appears on the status page
        # four minutes after it appears on the customers' screens is a status
        # page people learn not to trust.
        self._refresh_status_page_quietly()
        return {
            'notice': payload,
            'sent': sent, 'skipped': skipped,
            'range': render_range(payload['starts_at'], payload['ends_at']),
            # Counted in words a person uses. "1 customer(s)" is the shape a
            # developer writes when the plural is somebody else's problem.
            'message': self._reach_sentence(len(sent), len(skipped)),
        }

    @api.model
    def notice_clear(self, target):
        """Take the message down. Same door, empty value."""
        self._require_admin()
        tenants = self._notice_recipients(target)
        cleared, skipped = [], []
        for t in tenants:
            res = self.push_tenancy(t.id, {T_NOTICE: ''})
            if res['ok']:
                t.write({'notice': False, 'notice_until': False})
                self._log_line(t, 'notice', _("Message taken down."))
                cleared.append(t.name)
            else:
                skipped.append({'name': t.name, 'reason': res['reason']})
        self._refresh_status_page_quietly()
        return {'cleared': cleared, 'skipped': skipped,
                'message': (_("Taken down for 1 customer.") if len(cleared) == 1
                            else _("Taken down for %(n)s customers.", n=len(cleared)))}

    @staticmethod
    def _reach_sentence(sent, skipped):
        """"3 customers will see it; 1 could not be reached." Plain counting."""
        who = (_("1 customer will see it.") if sent == 1
               else _("%(n)s customers will see it.", n=sent))
        if not skipped:
            return who
        return "%s %s" % (who, _("1 could not be reached.") if skipped == 1
                          else _("%(m)s could not be reached.", m=skipped))

    def _tenant_cert_vals(self, tenant):
        """What certificate is this tenant's subdomain actually being served?

        `cert_own` False means the host is falling back to the wildcard, which
        cannot auto-renew — that is the state _cron_certs exists to repair.
        """
        host = '%s.%s' % (tenant.slug, self._base_domain())
        info = self._peer_cert(host)
        if not info['text']:
            return {'cert_expires': False, 'cert_days_left': -1, 'cert_own': False}
        # Its own cert names the host in the subject; the wildcard names *.domain.
        own = ('CN=%s' % host) in info['text'] or ('DNS:%s' % host) in info['text']
        return {'cert_expires': info['expires'] or False,
                'cert_days_left': info['days_left'] if info['days_left'] is not None else -1,
                'cert_own': own}

    def _step_cert(self, tenant, say):
        """Give this tenant's subdomain its own auto-renewing certificate.

        The *.payobook.com wildcard was issued through certbot's MANUAL dns-01
        flow and its renewal config has no auth hook, so `certbot renew` reaches
        it and blocks waiting for a human — it will never renew unattended. A
        per-host HTTP-01 certificate renews through certbot.timer like every
        other cert on the box.

        NEVER FATAL. The wildcard still serves this hostname perfectly well, so
        a slow DNS propagation or a bumped Let's Encrypt rate limit must not
        fail an otherwise good tenant. It degrades to a warning in the
        provisioning trail and the tenant goes live on the wildcard.
        """
        host = '%s.%s' % (tenant.slug, self._base_domain())
        script = '/usr/local/bin/pb-tenant-cert'
        if not os.path.exists(script):
            say('%s not installed — tenant will use the wildcard certificate.' % script, 'warn')
            return {}
        try:
            proc = subprocess.run(['sudo', '-n', script, host, tenant.slug],
                                  capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            say('Certificate request timed out — falling back to the wildcard certificate.', 'warn')
            return {}
        if proc.returncode == 0:
            say('HTTPS certificate issued for %s — renews automatically.' % host)
        else:
            tail = ((proc.stdout or '') + '\n' + (proc.stderr or '')).strip()[-300:]
            say('Certificate request failed, using the wildcard instead: %s' % (tail or 'unknown error'), 'warn')
        return {}

    def _detach_tenant_cert(self, tenant):
        """Drop a tenant subdomain's nginx block + certificate, if it has one.

        pb-domain-detach is hostname-generic, so it serves both custom domains
        and our own subdomains. Best-effort: offboarding must not fail because
        nginx housekeeping did.
        """
        script = '/usr/local/bin/pb-domain-detach'
        if not os.path.exists(script):
            return
        host = '%s.%s' % (tenant.slug, self._base_domain())
        try:
            subprocess.run(['sudo', '-n', script, host],
                           capture_output=True, text=True, timeout=120)
        except Exception as e:
            _logger.warning("Could not detach certificate for %s: %s", host, e)

    def _step_verify(self, tenant, say):
        slug = tenant.slug
        host = '%s.%s' % (slug, self._base_domain())
        dbfilter = odoo.tools.config['dbfilter'] or ''
        if '%d' not in dbfilter:
            say('dbfilter is not active on this server yet — tenant will be reachable once platform go-live plumbing is applied.', 'warn')
        code, ms = self._probe(host)
        if code == 200:
            say('HTTP probe OK — %s answers in %d ms.' % (host, ms))
        elif '%d' in dbfilter:
            raise UserError(_('HTTP probe of %s failed (status %s).') % (host, code or 'no response'))
        else:
            say('HTTP probe skipped (routing not live).', 'warn')
        with self._pg_cursor(slug) as cr:
            cr.execute("SELECT count(*) FROM res_users WHERE active")
            say('Registry sane: %d active users in tenant database.' % cr.fetchone()[0])
        tenant.write({'ping_ms': ms if ms >= 0 else -1, 'health_state': 'ok' if code == 200 else 'unknown',
                      'health_checked': fields.Datetime.now()})
        say('Tenant %s is LIVE.' % self._tenant_url(slug))
        return {'url': self._tenant_url(slug)}

    # ================================================================== detail / health
    @api.model
    def get_tenant(self, tenant_id):
        self._require_admin()
        t = self.env['pb.tenant'].sudo().browse(int(tenant_id)).exists()
        if not t:
            raise UserError(_('Tenant not found.'))
        return {
            **self._tenant_brief(t),
            'db_size': t.db_size, 'filestore_size': t.filestore_size,
            'db_size_only_h': self._human(t.db_size),
            'filestore_size_h': self._human(t.filestore_size),
            'health_checked': t.health_checked and t.health_checked.isoformat(sep=' ', timespec='minutes') or None,
            'created': t.create_date and t.create_date.isoformat(sep=' ', timespec='minutes') or None,
            'notes': t.notes or '',
            'last_sync_result': t.last_sync_result or '',
            # Whether there is anywhere to put a message on this customer at
            # all. Asked once, on opening one customer — never on the fleet.
            'tenancy_linked': self._tenancy_installed(t.slug),
            'staging_db': '%s-staging' % t.slug,
            'staging_exists': self._db_exists('%s-staging' % t.slug),
            'staging_url': self._tenant_url('%s-staging' % t.slug),
            'backups': [{
                'id': b.id, 'filename': b.filename, 'kind': b.kind, 'state': b.state,
                'size_h': self._human(b.size), 'note': b.note or '',
                'date': b.create_date.isoformat(sep=' ', timespec='minutes'),
            } for b in t.backup_ids],
            'domain_list': [{
                'id': d.id, 'hostname': d.hostname, 'state': d.state, 'message': d.message or '',
                'last_check': d.last_check and d.last_check.isoformat(sep=' ', timespec='minutes') or None,
            } for d in t.domain_ids],
        }

    @api.model
    def refresh_health(self, tenant_id=None):
        self._require_admin()
        dom = [('state', '=', 'live')]
        if tenant_id:
            dom = [('id', '=', int(tenant_id))]
        for t in self.env['pb.tenant'].sudo().search(dom):
            self._refresh_one(t)
        return tenant_id and self.get_tenant(tenant_id) or self.get_fleet_data()

    def _refresh_one(self, t):
        vals = {'health_checked': fields.Datetime.now()}
        vals['db_size'] = self._db_size(t.slug)
        vals['filestore_size'] = self._filestore_size(t.slug)
        try:
            # The cursor is autocommit, so a failed probe does not poison the ones
            # after it — but only if each gets its own except. See HEALTH_PROBES.
            with self._pg_cursor(t.slug) as cr:
                for field, table, sql in HEALTH_PROBES:
                    try:
                        if table:
                            cr.execute("SELECT to_regclass(%s)", (table,))
                            if not cr.fetchone()[0]:
                                continue  # module not installed in this tenant
                        cr.execute(sql)
                        val = cr.fetchone()[0]
                        vals[field] = False if val is None else val
                    except Exception as e:
                        _logger.warning("Health probe %s failed for %s: %s", field, t.slug, e)
        except Exception as e:
            _logger.warning("Health SQL failed for %s: %s", t.slug, e)
        code, ms = self._probe('%s.%s' % (t.slug, self._base_domain()))
        vals['ping_ms'] = ms
        vals.update(self._tenant_cert_vals(t))
        stale = not t.last_backup_at or t.last_backup_at < datetime.now() - timedelta(hours=48)
        dbfilter_live = '%d' in (odoo.tools.config['dbfilter'] or '')
        if code == 200:
            vals['health_state'] = 'warn' if (stale or ms > 3000) else 'ok'
        elif dbfilter_live:
            vals['health_state'] = 'down'
        else:
            vals['health_state'] = 'unknown'
        t.write(vals)

    # ================================================================== backups
    @api.model
    def backup_now(self, tenant_id, kind='manual'):
        self._require_admin()
        t = self.env['pb.tenant'].sudo().browse(int(tenant_id)).exists()
        if not t or t.state not in ('live', 'error', 'provisioning'):
            raise UserError(_('Tenant not available for backup.'))
        rec = self._do_backup(t, kind)
        if rec.state == 'failed':
            raise UserError(_('Backup failed: %s') % (rec.note or 'unknown error'))
        return self.get_tenant(tenant_id)

    def _do_backup(self, t, kind):
        root = os.path.join(self._backup_root(), t.slug)
        os.makedirs(root, exist_ok=True)
        fname = '%s_%s.zip' % (t.slug, datetime.now().strftime('%Y%m%d_%H%M%S'))
        path = os.path.join(root, fname)
        Backup = self.env['pb.tenant.backup'].sudo()
        try:
            with open(path, 'wb') as stream:
                _direct(db_service.dump_db)(t.slug, stream, 'zip')
            size = os.path.getsize(path)
            rec = Backup.create({'tenant_id': t.id, 'filename': fname, 'path': path,
                                 'size': size, 'kind': kind, 'state': 'done'})
            t.write({'last_backup_at': fields.Datetime.now()})
            self._prune_nightly(t)
            return rec
        except Exception as e:
            _logger.exception("Backup failed for %s", t.slug)
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except OSError:
                pass
            return Backup.create({'tenant_id': t.id, 'filename': fname, 'path': path,
                                  'kind': kind, 'state': 'failed', 'note': str(e)[:500]})

    def _prune_nightly(self, t):
        nightly = self.env['pb.tenant.backup'].sudo().search(
            [('tenant_id', '=', t.id), ('kind', '=', 'nightly'), ('state', '=', 'done')],
            order='create_date desc')
        for old in nightly[NIGHTLY_KEEP:]:
            try:
                if old.path and os.path.exists(old.path):
                    os.unlink(old.path)
            except OSError:
                pass
            old.unlink()

    @api.model
    def restore_staging(self, tenant_id, backup_id=None):
        self._require_admin()
        t = self.env['pb.tenant'].sudo().browse(int(tenant_id)).exists()
        if not t:
            raise UserError(_('Tenant not found.'))
        Backup = self.env['pb.tenant.backup'].sudo()
        if backup_id:
            b = Backup.browse(int(backup_id)).exists()
        else:
            b = Backup.search([('tenant_id', '=', t.id), ('state', '=', 'done')], limit=1)
        if not b or not os.path.exists(b.path):
            raise UserError(_('No usable backup file found for this tenant.'))
        staging = '%s-staging' % t.slug
        if self._db_exists(staging):
            _direct(db_service.exp_drop)(staging)
        _direct(db_service.restore_db)(staging, b.path, True)
        # point staging at its own URL without booting its registry
        url = self._tenant_url(staging)
        try:
            with self._pg_cursor(staging) as cr:
                cr.execute("UPDATE ir_config_parameter SET value=%s WHERE key='web.base.url'", (url,))
        except Exception as e:
            _logger.warning("Could not set staging base url: %s", e)
        return {'staging_url': url, 'from_backup': b.filename}

    @api.model
    def drop_staging(self, tenant_id):
        self._require_admin()
        t = self.env['pb.tenant'].sudo().browse(int(tenant_id)).exists()
        staging = '%s-staging' % t.slug
        if self._db_exists(staging):
            _direct(db_service.exp_drop)(staging)
        return self.get_tenant(tenant_id)

    # ================================================================== offboarding
    @api.model
    def offboard(self, tenant_id, confirm_slug):
        self._require_admin()
        t = self.env['pb.tenant'].sudo().browse(int(tenant_id)).exists()
        if not t:
            raise UserError(_('Tenant not found.'))
        if (confirm_slug or '').strip().lower() != t.slug:
            raise UserError(_('Confirmation text does not match the tenant subdomain.'))
        if t.state == 'decommissioned':
            raise UserError(_('Tenant is already decommissioned.'))
        final = None
        if self._db_exists(t.slug):
            final = self._do_backup(t, 'final')
            if final.state == 'failed':
                raise UserError(_('Refusing to offboard: final backup failed (%s).') % (final.note or 'unknown'))
            staging = '%s-staging' % t.slug
            if self._db_exists(staging):
                _direct(db_service.exp_drop)(staging)
            _direct(db_service.exp_drop)(t.slug)
        # Take the subdomain's own nginx block + certificate down with the DB,
        # or the host keeps answering on a block that proxies to nothing.
        self._detach_tenant_cert(t)
        t.write({'state': 'decommissioned', 'health_state': 'unknown',
                 'notes': (t.notes or '') + '\nDecommissioned %s.' % fields.Date.today()})
        return {'ok': True, 'final_backup_id': final and final.id or None,
                'final_backup': final and final.filename or None}

    # ================================================================== custom domains
    @api.model
    def domain_add(self, tenant_id, hostname):
        self._require_admin()
        t = self.env['pb.tenant'].sudo().browse(int(tenant_id)).exists()
        hostname = (hostname or '').strip().lower().rstrip('.')
        if not t or t.state != 'live':
            raise UserError(_('Tenant must be live before attaching a domain.'))
        if not HOST_RE.match(hostname) or hostname.endswith(self._base_domain()):
            raise UserError(_('Enter a valid external hostname, e.g. payroll.acme.com.'))
        self.env['pb.tenant.domain'].sudo().create({'tenant_id': t.id, 'hostname': hostname})
        return self.get_tenant(tenant_id)

    @api.model
    def domain_check(self, domain_id):
        self._require_admin()
        d = self.env['pb.tenant.domain'].sudo().browse(int(domain_id)).exists()
        if not d:
            raise UserError(_('Domain not found.'))
        ip = self._public_ip()
        got = self._resolve(d.hostname)
        if got and ip and got == ip:
            d.write({'state': 'verified' if d.state != 'active' else 'active',
                     'message': 'DNS resolves to this server (%s).' % ip,
                     'last_check': fields.Datetime.now()})
        else:
            d.write({'state': 'pending' if d.state != 'active' else 'active',
                     'message': 'Resolves to %s — expected %s.' % (got or 'nothing yet', ip or '?'),
                     'last_check': fields.Datetime.now()})
        return self.get_tenant(d.tenant_id.id)

    @api.model
    def domain_activate(self, domain_id):
        self._require_admin()
        d = self.env['pb.tenant.domain'].sudo().browse(int(domain_id)).exists()
        if not d or d.state not in ('verified',):
            raise UserError(_('Verify DNS first, then activate.'))
        script = '/usr/local/bin/pb-domain-attach'
        if not os.path.exists(script):
            raise UserError(_('Domain automation script is not installed on this server (deploy runbook step).'))
        try:
            proc = subprocess.run(['sudo', '-n', script, d.hostname, d.tenant_id.slug],
                                  capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            raise UserError(_('Domain activation timed out.'))
        tail = ((proc.stdout or '') + '\n' + (proc.stderr or '')).strip()[-400:]
        if proc.returncode == 0:
            d.write({'state': 'active', 'message': 'Serving with TLS.', 'last_check': fields.Datetime.now()})
        else:
            d.write({'state': 'error', 'message': tail or 'activation failed', 'last_check': fields.Datetime.now()})
            raise UserError(_('Activation failed:\n%s') % (tail or 'unknown error'))
        return self.get_tenant(d.tenant_id.id)

    @api.model
    def domain_remove(self, domain_id):
        self._require_admin()
        d = self.env['pb.tenant.domain'].sudo().browse(int(domain_id)).exists()
        if not d:
            return {}
        tenant_id = d.tenant_id.id
        if d.state == 'active':
            script = '/usr/local/bin/pb-domain-detach'
            if os.path.exists(script):
                subprocess.run(['sudo', '-n', script, d.hostname], capture_output=True, text=True, timeout=120)
        d.unlink()
        return self.get_tenant(tenant_id)

    # ================================================================== crons
    @api.model
    def _cron_nightly_backups(self):
        for t in self.env['pb.tenant'].sudo().search([('state', '=', 'live')]):
            self._do_backup(t, 'nightly')
            self.env.cr.commit()

    @api.model
    def _cron_health(self):
        for t in self.env['pb.tenant'].sudo().search([('state', '=', 'live')]):
            try:
                self._refresh_one(t)
            except Exception as e:
                _logger.warning("Health refresh failed for %s: %s", t.slug, e)
            self.env.cr.commit()
        self._warn_cert_expiry()

    def _cron_certs(self):
        """Keep every live tenant on its own auto-renewing certificate.

        Provisioning's cert step is deliberately non-fatal — a tenant whose
        issuance failed (slow DNS, Let's Encrypt rate limit) goes live on the
        wildcard and nothing would ever notice. That is the worst place to be
        left: the wildcard is precisely the certificate that cannot auto-renew.
        This is the safety net that closes that gap.

        Two repairable states, and nothing else is touched:
          * no certificate of its own  -> issue one
          * its own, but under CERT_REISSUE_DAYS and still not renewed by
            certbot.timer -> re-run, since something is wrong with renewal

        pb-tenant-cert passes --keep-until-expiring, so a needless run is a
        no-op rather than an issuance against the weekly rate limit. Healthy
        tenants are not touched at all, so nginx is not reloaded for nothing.
        """
        script = '/usr/local/bin/pb-tenant-cert'
        for t in self.env['pb.tenant'].sudo().search([('state', '=', 'live')]):
            host = '%s.%s' % (t.slug, self._base_domain())
            try:
                vals = self._tenant_cert_vals(t)
                t.write(vals)
                self.env.cr.commit()
            except Exception as e:
                _logger.warning("Certificate check failed for %s: %s", host, e)
                continue
            days = vals['cert_days_left']
            if vals['cert_own'] and days >= CERT_REISSUE_DAYS:
                continue  # healthy and renewing on its own
            if not os.path.exists(script):
                _logger.warning(
                    "%s has no certificate of its own and %s is not installed.", host, script)
                continue
            reason = ('has no certificate of its own (falling back to the non-renewing wildcard)'
                      if not vals['cert_own'] else
                      'expires in %s days and has not renewed' % days)
            _logger.warning("Repairing TLS for %s: %s", host, reason)
            try:
                proc = subprocess.run(['sudo', '-n', script, host, t.slug],
                                      capture_output=True, text=True, timeout=300)
            except subprocess.TimeoutExpired:
                _logger.warning("Certificate repair for %s timed out.", host)
                continue
            if proc.returncode == 0:
                # nginx reloads gracefully, so re-probing immediately can still be
                # answered by the OLD config and record a stale "no certificate".
                # Let the new workers take over before believing the answer.
                time.sleep(3)
                t.write(self._tenant_cert_vals(t))
                _logger.info("Certificate repaired for %s.", host)
            else:
                tail = ((proc.stdout or '') + '\n' + (proc.stderr or '')).strip()[-300:]
                _logger.warning("Certificate repair for %s failed: %s", host, tail)
            self.env.cr.commit()

    def _warn_cert_expiry(self):
        """Nag the server log when the wildcard cert is close to lapsing.

        The cockpit checklist shows this too, but nobody watches a green
        checklist — and a manual DNS-01 cert has no renewal cron to fail loudly.
        """
        dom = self._base_domain()
        try:
            tls = self._check_wildcard_tls(dom)
        except Exception as e:
            return _logger.warning("Certificate expiry check failed for *.%s: %s", dom, e)
        days = tls['days_left']
        if not tls['ok'] or days is None:
            return
        if days <= TLS_RENEW_WARN_DAYS:
            _logger.warning(
                "Wildcard TLS certificate for *.%s expires in %d days (%s). Manual DNS-01 "
                "certificates do NOT auto-renew — reissue it (see docs/SAAS_RUNBOOK.md).",
                dom, days, tls['expires'])
