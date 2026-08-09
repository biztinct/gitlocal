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
from datetime import datetime, timedelta

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

PROVISION_STEPS = [
    ('clone', 'Clone golden template'),
    ('configure', 'Configure tenant'),
    ('admin', 'Create admin access'),
    ('verify', 'Verify & go live'),
]
NIGHTLY_KEEP = 14


def _direct(fn):
    """The db-management functions are wrapped by check_db_management_enabled
    (raises when list_db=False). We keep list_db=False for the web surface and
    call the inner function directly for our own guarded, in-process use."""
    inner = getattr(fn, '__wrapped__', None)
    if inner is None:
        raise UserError(
            "Odoo's database service layer changed shape (no __wrapped__) — "
            "update pb_tenants before managing tenants on this build.")
    return inner


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
        try:
            return socket.gethostbyname(host)
        except OSError:
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
        }

    def _tenant_brief(self, t):
        return {
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
        }

    def _platform_status(self):
        dom = self._base_domain()
        cfg = odoo.tools.config
        ip = self._public_ip()
        probe_host = 'pb-probe-x7.%s' % dom
        wild_ip = self._resolve(probe_host)
        wildcard_dns = bool(ip and wild_ip == ip)
        wildcard_tls = self._check_wildcard_tls(dom)
        template_ok = self._db_exists(self._template_db())
        try:
            du = shutil.disk_usage('/')
            disk_free_h, disk_pct = self._human(du.free), int(du.free * 100 / du.total)
        except OSError:
            disk_free_h, disk_pct = '—', 0
        dbfilter = cfg['dbfilter'] or ''
        smtp_ok = bool(self.env['ir.mail_server'].sudo().search_count([]))
        checks = [
            {'key': 'dbfilter', 'label': 'Subdomain routing (dbfilter)', 'ok': '%d' in dbfilter,
             'hint': "Server config needs dbfilter = ^%d$ (currently: '" + (dbfilter or 'not set') + "')"},
            {'key': 'listdb', 'label': 'Database manager locked down', 'ok': not cfg['list_db'],
             'hint': 'Set list_db = False in the server config.'},
            {'key': 'template', 'label': 'Golden template database', 'ok': template_ok,
             'hint': 'Template "%s" not found — build it from the deploy runbook.' % self._template_db()},
            {'key': 'dns', 'label': 'Wildcard DNS  *.%s' % dom, 'ok': wildcard_dns,
             'hint': 'Add at your registrar: A record, host "*", value %s' % (ip or 'server IP')},
            {'key': 'tls', 'label': 'Wildcard TLS certificate', 'ok': wildcard_tls,
             'hint': 'Issue a *.%s certificate (DNS-01 challenge) and install it in nginx.' % dom},
            {'key': 'smtp', 'label': 'Outgoing mail (SMTP)', 'ok': smtp_ok,
             'hint': 'Configure an outgoing mail server so tenant emails can send.'},
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

    def _check_wildcard_tls(self, dom):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with socket.create_connection(('127.0.0.1', 443), timeout=3) as sock:
                with ctx.wrap_socket(sock, server_hostname='pb-probe-x7.%s' % dom) as tls:
                    der = tls.getpeercert(binary_form=True)
            cert = ssl.DER_cert_to_PEM_cert(der)
            # cheap SAN check without external deps
            import tempfile
            with tempfile.NamedTemporaryFile('w', suffix='.pem', delete=False) as f:
                f.write(cert)
                pem = f.name
            try:
                out = subprocess.run(['openssl', 'x509', '-in', pem, '-noout', '-text'],
                                     capture_output=True, text=True, timeout=5).stdout
            finally:
                os.unlink(pem)
            return ('*.%s' % dom) in out
        except Exception:
            return False

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
            if tenant.country_code:
                country = env['res.country'].search([('code', '=', tenant.country_code)], limit=1)
                if country:
                    vals['country_id'] = country.id
            company.write(vals)
            say('Company configured: %s%s' % (tenant.name, tenant.country_code and ' (%s)' % tenant.country_code or ''))
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
            })
            say('Tenant administrator: %s' % tenant.admin_email)
        say('Credentials generated — shown once on completion, never stored.', 'warn')
        return {'credentials': {'url': self._tenant_url(slug),
                                'login': tenant.admin_email,
                                'password': password}}

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
            with self._pg_cursor(t.slug) as cr:
                cr.execute("SELECT count(*) FROM res_users WHERE active AND share IS NOT TRUE")
                vals['user_count'] = cr.fetchone()[0]
                cr.execute("SELECT max(login_date) FROM res_users")
                row = cr.fetchone()
                vals['last_login'] = row and row[0] or False
                cr.execute("SELECT to_regclass('hr_employee')")
                if cr.fetchone()[0]:
                    cr.execute("SELECT count(*) FROM hr_employee WHERE active")
                    vals['employee_count'] = cr.fetchone()[0]
        except Exception as e:
            _logger.warning("Health SQL failed for %s: %s", t.slug, e)
        code, ms = self._probe('%s.%s' % (t.slug, self._base_domain()))
        vals['ping_ms'] = ms
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
