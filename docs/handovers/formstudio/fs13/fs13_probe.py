# FS-13 open-the-pages probe (odoo-bin shell). Counts and hashes only — never names or values.
# Clone of fs1112/fs12_probe.py (same page hashing), trimmed to what FS-13 touches, plus:
#   * the administrator's /my/profile (FS-13: no employee record -> a note with "Edit this page");
#   * the page builder: fields, ticked, companies offered vs active companies, preview people;
#   * the showcase page (payobook): md5 of the published page row;
#   * PROBE_PREVIEW=1 (REHEARSAL COPIES ONLY — it commits a draft, then deletes it): a draft that
#     places one field not yet shown; the preview over the web stack must draw it, its photo route
#     must answer an image, and the field's "Show on My Payobook" tick must stay off.
#   env: PROBE_HOST, PROBE_ADMIN_ONLY=1 (live: administrator pages only), PROBE_PREVIEW=1
import hashlib
import json
import os
import re

from werkzeug.test import Client
from werkzeug.wrappers import Response

from odoo import http
from odoo.service import security

TOKENS = re.compile(rb'[0-9a-f]{40}o[0-9]+')
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


def fetch(user, paths):
    s = session_for(user)
    c = Client(http.root, Response)
    c.set_cookie('session_id', s.sid, domain=host)
    out = []
    try:
        for p in paths:
            r = c.get(p, headers={'Host': host})
            out.append((p, r.status_code, r.headers.get('Content-Type', ''), r.get_data()))
    finally:
        http.root.session_store.delete(s)
    return out


def open_pages(user, paths):
    out = []
    for p, code, _ct, data in fetch(user, paths):
        body = ASSETS.sub(b'', TOKENS.sub(b'', data))
        out.append('%s %s %s%s' % (p, code, hashlib.md5(body).hexdigest()[:10],
                                   ' VENDOR' if b'Odoo' in body.replace(b'odoo', b'') else ''))
    return out


env.cr.commit()
Emp = env['hr.employee'].sudo()
users = []
if not admin_only:
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
own = bool(Emp.search_count([('user_id', '=', admin.id)]))
prof = fetch(admin, ['/my/profile'])[0]
print('PROBE admin has-employee %s /my/profile %s note %s builder-link %s' % (
    own, prof[1], b'Your login has no employee record' in prof[3],
    b'action-pb_form_studio_portal.action_page_builder' in prof[3]))

e = env(user=admin.id, context={'allowed_company_ids': admin.company_ids.ids})
S = e['pb.form.studio']
res = []
try:
    with env.cr.savepoint():
        p = S.page_studio()
        res.append('page builder fields %s ticked %s published %s' % (
            len(p['fields']), len(p['ticked']), bool(p['published'])))
        active = env['res.company'].sudo().search_count([])
        archived = env['res.company'].sudo().with_context(active_test=False).search_count([('active', '=', False)])
        res.append('companies offered %s (active %s, archived %s)' % (
            len(p['companies']), active, archived))
        res.append('preview people %s' % len(S.page_employees('')))
        d = S.get_studio('employee_detail')
        res.append('employee fixed %s lines' % sum(len(v) for v in (d.get('fixed') or {}).values()))
        if 'contract' in S._pbfs_hosts():
            d = S.get_studio('contract')
            res.append('contract fixed %s' % sum(len(v) for v in (d.get('fixed') or {}).values()))
        emp = e['hr.employee'].search([], limit=1)
        if emp:
            r = e['pb.people'].get_employee_360(emp.id)
            res.append('side panel ok' if r else 'side panel EMPTY')
except Exception as exc:                                # noqa: BLE001
    res.append('ERROR %s: %s' % (type(exc).__name__, str(exc)[:160]))
print('PROBE screens %s' % '; '.join(res))
env.cr.rollback()
env.cr.execute("select md5(coalesce(sections::text,'')||coalesce(page::text,'')||version::text) "
               "from pb_form_layout where host_key='my_profile_page'")
print('PROBE page row %s' % ([r[0][:10] for r in env.cr.fetchall()] or 'none'))

if os.environ.get('PROBE_PREVIEW') == '1' and not db.startswith(('payobook', 'rize', 'sudima', 'p0clone')):
    out = []
    try:
        data = S.page_studio()
        ticked = set(data['ticked'])
        pick = next((n for n in ('birthday', 'mobile_phone', 'place_of_birth') if n in data['fields']
                     and n not in ticked), None) or next(
            (n for n in data['fields'] if n not in ticked and not n.startswith('x_')), None)
        target = Emp.search([('active', '=', True)], limit=1, order='id desc')
        if pick and target:
            base = data['published']['default'] if data['published'] else data['standard']
            spec = json.loads(json.dumps(base))
            spec['sections'][0]['fields'].append({'name': pick, 'width': 'half'})
            label = data['fields'][pick]['label']
            S.save_draft('my_profile_page', {'spec': spec, 'companies': {}, 'updates': {},
                                             'changes': ['FS13 probe'], 'base_version': data['version']})
            env.cr.commit()
            got = fetch(admin, ['/my/profile/preview?employee_id=%s&source=draft' % target.id,
                                '/my/profile/preview/photo/%s' % target.id])
            html = got[0][3].decode('utf-8', 'replace')
            out.append('preview %s new-field-drawn %s photo-src %s photo %s %s' % (
                got[0][1], ('<span>%s</span>' % label) in html,
                ('/my/profile/preview/photo/%s' % target.id) in html, got[1][1], got[1][2][:10]))
            meta = env['pb.form.field.meta'].sudo().search([('model', '=', 'hr.employee'), ('name', '=', pick)])
            out.append('tick still off %s' % (not meta.portal_show))
            if target.user_id:
                mine = fetch(target.user_id, ['/my/profile'])[0][3].decode('utf-8', 'replace')
                out.append('employee page shows it %s' % (('<span>%s</span>' % label) in mine))
            S.discard_draft('my_profile_page')
            env.cr.commit()
            out.append('draft removed %s' % (not S._pbfs_drafts('my_profile_page')))
        else:
            out.append('nothing to place')
    except Exception as exc:                            # noqa: BLE001
        env.cr.rollback()
        out.append('ERROR %s: %s' % (type(exc).__name__, str(exc)[:160]))
    print('PROBE preview %s' % '; '.join(out))
env.cr.rollback()
