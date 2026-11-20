# FS-11/FS-12 open-the-pages probe (odoo-bin shell on a REHEARSAL COPY; also run read-only on
# live for the administrator). Counts and hashes only — never names or values.
#
# For up to 3 employees with a login (and the site administrator) it opens the real pages over
# the in-process web stack with a server-made session (no password): /my, /my/profile,
# /my/details, My Leave. It prints the status code and a hash of each page with the per-request
# security tokens removed, so a run before and after the upgrade can be compared byte for byte.
# Then it calls, as the administrator, the Form builder screens the release changes (employee and
# contract builder with the fixed lists, the Full details tabs, the Field library, the page
# builder) and the employee side panel. Everything it may write is rolled back; the sessions it
# makes are deleted.
#   env: PROBE_HOST (Host header, e.g. rize.payobook.com), PROBE_ADMIN_ONLY=1 (live: no employees)
import hashlib
import os
import re

from werkzeug.test import Client
from werkzeug.wrappers import Response

import odoo
from odoo import http
from odoo.service import security

TOKENS = re.compile(rb'[0-9a-f]{40}o[0-9]+')
#: the bundles' addresses change with every module that ships a stylesheet or script
ASSETS = re.compile(rb'/web/assets/[^"\' ]+|"registry_hash": "[0-9a-f]+"|data-server-now-ms="[0-9]+"')
host = os.environ.get('PROBE_HOST') or 'localhost'
admin_only = os.environ.get('PROBE_ADMIN_ONLY') == '1'
db = env.cr.dbname


def session_for(user):
    s = http.root.session_store.new()
    s.update(http.get_default_session(), db=db, _trace_disable=True)
    s.uid = user.id
    s.login = user.login
    s.context = {'lang': user.lang or 'en_US'}
    s.session_token = security.compute_session_token(s, env(user=user.id))
    http.root.session_store.save(s)
    return s


def open_pages(user, paths):
    s = session_for(user)
    c = Client(http.root, Response)
    c.set_cookie('session_id', s.sid, domain=host)
    out = []
    try:
        for p in paths:
            r = c.get(p, headers={'Host': host})
            body = ASSETS.sub(b'', TOKENS.sub(b'', r.get_data()))
            if os.environ.get('PROBE_SAVE'):
                with open('%s/%s%s.html' % (os.environ['PROBE_SAVE'], user.id, p.replace('/', '_')), 'wb') as f:
                    f.write(body)
            out.append('%s %s %s%s' % (p, r.status_code, hashlib.md5(body).hexdigest()[:10],
                                       ' VENDOR' if b'Odoo' in body.replace(b'odoo', b'') else ''))
    finally:
        http.root.session_store.delete(s)
    return out


env.cr.commit()             # the web stack opens its own cursors: they must see this transaction
Emp = env['hr.employee'].sudo()
users = []
if not admin_only:
    # employee logins first (an administrator's own pages carry tools that change per visit)
    dom = [('user_id', '!=', False), ('active', '=', True), ('user_id.active', '=', True)]
    emps = Emp.search(dom + [('user_id.share', '=', True)], limit=3, order='id desc')
    emps |= Emp.search(dom + [('id', 'not in', emps.ids)], limit=3 - len(emps), order='id desc') \
        if len(emps) < 3 else Emp.browse()
    users = [e.user_id for e in emps]
admin = env.ref('base.user_admin')
if not admin.has_group('base.group_system'):
    admin = env['res.users'].search([('share', '=', False), ('id', '!=', 1)]).filtered(
        lambda u: u.has_group('base.group_system'))[:1]
paths = ['/my', '/my/profile', '/my/details']
if 'pb.ess.workforce' in env:
    paths.append('/my/work/leave')
for i, u in enumerate(users):
    print('PROBE page emp%s %s' % (i + 1, ' | '.join(open_pages(u, paths))))
print('PROBE page admin %s' % ' | '.join(open_pages(admin, ['/my', '/my/profile'])))

# backend screens as the administrator (rolled back)
cos = env['res.company'].search([]).ids
e = env(user=admin.id, context={'allowed_company_ids': cos})
S = e['pb.form.studio']
res = []
try:
    with env.cr.savepoint():
        d = S.get_studio('employee_detail')
        res.append('employee fixed %s lines' % sum(len(v) for v in (d.get('fixed') or {}).values()))
        d = S.with_context(pbfs_surface='full').get_studio('employee_detail')
        res.append('full details tabs %s' % len([s for s in d['sections'] if s['kind'] == 'locked']))
        if 'contract' in S._pbfs_hosts():
            d = S.get_studio('contract')
            res.append('contract fixed %s' % sum(len(v) for v in (d.get('fixed') or {}).values()))
            d = S.with_context(pbfs_surface='full').get_studio('contract')
            res.append('contract form tabs %s' % len([s for s in d['sections'] if s['kind'] == 'locked']))
        lib = S.library()
        res.append('library screens %s' % len(lib['screens']))
        if hasattr(S, 'page_studio'):
            p = S.page_studio()
            res.append('page builder fields %s ticked %s published %s' % (
                len(p['fields']), len(p['ticked']), bool(p['published'])))
        # WF2 P6e ships inside this go-live: the Workflow Studio opens, and Time off
        if 'pb.workflow.studio' in e:
            b = e['pb.workflow.studio'].bootstrap()
            res.append('workflow studio ok (%s workflows)' % len(b.get('workflows') or [])
                       if isinstance(b, dict) else 'workflow studio ok')
        if 'hr.leave' in e:
            e['hr.leave'].get_views([(False, 'list'), (False, 'form')])
            res.append('time off ok (%s rows read)' % len(e['hr.leave'].search_read([], ['name', 'state'], limit=5)))
        emp = e['hr.employee'].search([], limit=1)
        if emp:
            r = e['pb.people'].get_employee_360(emp.id)
            res.append('side panel ok' if r else 'side panel EMPTY')
            r = e['pb.people'].get_employee_detail(emp.id)
            res.append('employee page ok' if r and not r.get('error') else 'employee page ERROR')
except Exception as exc:                                # noqa: BLE001
    res.append('ERROR %s: %s' % (type(exc).__name__, str(exc)[:160]))
print('PROBE screens %s' % '; '.join(res))

# Workflow Studio's words over the web stack, as the administrator (status + caching headers)
if 'pb.workflow.studio' in env:
    s = session_for(admin)
    c = Client(http.root, Response)
    c.set_cookie('session_id', s.sid, domain=host)
    try:
        r = c.get('/pb_lifecycle/workflow/words', headers={'Host': host})
        r2 = c.get('/pb_lifecycle/static/workflow/index.html', headers={'Host': host})
        print('PROBE studio words %s cache=%s etag=%s; index %s new-address %s' % (
            r.status_code, r.headers.get('Cache-Control'), bool(r.headers.get('ETag')), r2.status_code,
            b'/pb_lifecycle/workflow/words?v=wf2-p6e' in r2.get_data()))
    finally:
        http.root.session_store.delete(s)

# My Leave and the employee home for the newest employees with a login (server side, read-only,
# rolled back — the WF2 P6 check; no page is opened as a customer's employee on live)
if 'pb.ess.workforce' in env:
    ok = bad = 0
    errs = []
    for emp in Emp.search([('user_id', '!=', False), ('active', '=', True)], limit=5, order='id desc'):
        try:
            with env.cr.savepoint():
                d = env['pb.ess.workforce'].with_user(emp.user_id).with_company(emp.company_id).get_my_leave(again=None)
                assert 'requests' in d
                env['pb.me.home'].with_user(emp.user_id).get_home_data(emp)
            ok += 1
        except Exception as exc:                        # noqa: BLE001
            bad += 1
            errs.append('%s: %s' % (type(exc).__name__, str(exc)[:80]))
    print('PROBE my-leave+home ok %s failed %s %s' % (ok, bad, ' | '.join(errs[:2])))
env.cr.rollback()
env.cr.rollback()
