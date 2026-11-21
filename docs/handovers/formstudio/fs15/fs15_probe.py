# FS-15 open-the-screens probe (odoo-bin shell). Counts and hashes only — never names or values.
# Clone of fs14/fs14_probe.py (same page hashing), plus what FS-15 touches:
#   * Full details: the employee form as HR sees it (arch md5, en + vi + id) and the contract form;
#   * the side panel: md5 of the panel's tabs for up to 3 people per Country of Work (+ none);
#   * the Form builder (employee + contract): standard fields listed, taken off the screens (can come
#     back / stay off), settings rows, the Countries of Work in use (counts per country code only);
#   * the administrator's /my and /my/profile; employee pages for up to 3 logins.
#   * PROBE_CHANGE=1 (REHEARSAL COPIES ONLY — it commits, then puts everything back): widen a
#     Vietnam-only field to Indonesia, a locked one too; narrow/hide a locked one (must be refused);
#     show a removed one again for Vietnam; a stays-off one (must be refused); check the form for an
#     Indonesia / Vietnam person; Reset to built-in; the form must be back to its first hash.
#   env: PROBE_HOST, PROBE_ADMIN_ONLY=1 (no employee pages), PROBE_CHANGE=1
import hashlib
import json
import os
import re

from lxml import etree
from werkzeug.test import Client
from werkzeug.wrappers import Response

from odoo import http
from odoo.service import security
from odoo.tools.safe_eval import safe_eval

TOKENS = re.compile(rb'[0-9a-f]{40}o[0-9]+')
ASSETS = re.compile(rb'/web/assets/[^"\' ]+|"registry_hash": "[0-9a-f]+"|data-server-now-ms="[0-9]+"')
host = os.environ.get('PROBE_HOST') or 'localhost'
admin_only = os.environ.get('PROBE_ADMIN_ONLY') == '1'
db = env.cr.dbname
MODEL = 'hr.employee'


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


def md5(x):
    return hashlib.md5(x if isinstance(x, bytes) else json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()[:10]


env.cr.commit()
Emp = env['hr.employee'].sudo()
admin = env.ref('base.user_admin')
if not admin.has_group('base.group_system'):
    admin = env['res.users'].search([('share', '=', False), ('id', '!=', 1)]).filtered(
        lambda u: u.has_group('base.group_system'))[:1]
langs = [l for l in ('en_US', 'vi_VN', 'id_ID') if env['res.lang']._lang_get(l)]
e = env(user=admin.id, context={'allowed_company_ids': admin.company_ids.ids})
emp_view = env.ref('hr.view_employee_form')


def form_hashes():
    env.registry.clear_cache('templates')
    out = []
    for lang in langs:
        arch = e[MODEL].with_context(lang=lang).get_view(emp_view.id, 'form')['arch']
        out.append('%s:%s' % (lang[:2], md5(arch.encode())))
    if 'hr.contract' in env:
        v = env.ref('hr_contract.hr_contract_view_form', raise_if_not_found=False) or env.ref(
            'om_hr_payroll.hr_contract_view_form', raise_if_not_found=False)
        if v:
            out.append('contract:%s' % md5(e['hr.contract'].get_view(v.id, 'form')['arch'].encode()))
    return ' '.join(out)


print('PROBE forms %s' % form_hashes())

# the side panel, up to 3 people per Country of Work
codes = [c for c, in env.cr.execute("select distinct coalesce(payroll_country,'') from hr_employee where active") or env.cr.fetchall()]
panel = []
for code in sorted(codes):
    dom = [('active', '=', True), ('payroll_country', '=', code or False)]
    for emp in Emp.search(dom, limit=3, order='id desc'):
        try:
            with env.cr.savepoint():
                det = e['pb.people'].get_employee_360(emp.id).get('details') or {}
            panel.append(md5(det))
        except Exception as exc:                        # noqa: BLE001
            panel.append('ERR-%s' % type(exc).__name__)
    panel.append('|')
print('PROBE panel %s' % ' '.join(panel))

res = []
try:
    with env.cr.savepoint():
        S = e['pb.form.studio']
        d = S.get_studio('employee_detail')
        std = {n: f['stdbox'] for n, f in d['fields'].items() if f.get('stdbox')}
        off = [s for s in std.values() if s.get('off')]
        res.append('employee standard %s, off the screens %s (can come back %s, stay off %s), changed %s' % (
            len(std), len(off), sum(1 for s in off if not s['comeback']),
            sum(1 for s in off if s['comeback']), sum(1 for s in std.values() if s.get('changed'))))
        res.append('in use %s none %s' % (' '.join('%s %s' % (c['code'], c['n']) for c in d['countries_in_use']),
                                         d['countries_none']))
        res.append('employee fixed %s lines' % sum(len(v) for v in (d.get('fixed') or {}).values()))
        if 'contract' in S._pbfs_hosts():
            c = S.get_studio('contract')
            res.append('contract standard %s fixed %s' % (
                sum(1 for f in c['fields'].values() if f.get('stdbox')),
                sum(len(v) for v in (c.get('fixed') or {}).values())))
        lib = S.library()
        res.append('library std rows %s' % len(lib['std']))
        env.cr.execute("select count(*) filter (where std_show is not null), count(*) filter (where std_hidden), "
                       "(select count(*) from pb_form_field_meta_std_country_rel) from pb_form_field_meta")
        res.append('settings rows shown-for %s, older hide rows %s/%s' % env.cr.fetchone())
except Exception as exc:                                # noqa: BLE001
    res.append('ERROR %s: %s' % (type(exc).__name__, str(exc)[:200]))
print('PROBE screens %s' % '; '.join(res))
env.cr.rollback()

users = []
if not admin_only:
    dom = [('user_id', '!=', False), ('active', '=', True), ('user_id.active', '=', True)]
    emps = Emp.search(dom + [('user_id.share', '=', True)], limit=3, order='id desc')
    if len(emps) < 3:
        emps |= Emp.search(dom + [('id', 'not in', emps.ids)], limit=3 - len(emps), order='id desc')
    users = [x.user_id for x in emps]
paths = ['/my', '/my/profile', '/my/details']
for i, u in enumerate(users):
    print('PROBE page emp%s %s' % (i + 1, ' | '.join(open_pages(u, paths))))
print('PROBE page admin %s' % ' | '.join(open_pages(admin, ['/my', '/my/profile'])))


def shown(arch, name, emp):
    node = next((n for n in arch.iter('field') if n.get('name') == name
                 and not any(a.tag == 'field' for a in n.iterancestors())), None)
    if node is None:
        return False
    ctx = {'pbfs_country_of_work_id': emp.pbfs_country_of_work_id.id or False,
           'payroll_country': emp.payroll_country or False, 'id': emp.id}
    for el in [node] + list(node.iterancestors()):
        expr = (el.get('invisible') or '').strip()
        if not expr:
            continue
        if expr in ('1', 'True', 'true'):
            return False
        local = dict(ctx)
        for _i in range(40):
            try:
                if safe_eval(expr, dict(local)):
                    return False
                break
            except (NameError, ValueError) as err:
                bits = str(err).split("'")
                if len(bits) < 2:
                    raise
                local[bits[1]] = False
    return True


if os.environ.get('PROBE_CHANGE') == '1' and db.startswith('fs15_rh_'):
    out = []
    try:
        S = e['pb.form.studio']
        vn = env.ref('base.vn')
        idn = env.ref('base.id')
        before = form_hashes()

        def arch():
            env.registry.clear_cache('templates')
            return etree.fromstring(e[MODEL].get_view(emp_view.id, 'form')['arch'])
        p_vn = Emp.new({'payroll_country': 'VN'})
        p_id = Emp.new({'payroll_country': 'ID'})
        if 'pb_safety_group' in env[MODEL]._fields:
            S.update_standard(MODEL, 'pb_safety_group', {'std_show': 'only', 'std_show_country_ids': [vn.id, idn.id]})
            env.cr.commit()
            a = arch()
            out.append('widen VN-only to ID: VN %s ID %s' % (shown(a, 'pb_safety_group', p_vn), shown(a, 'pb_safety_group', p_id)))
        S.update_standard(MODEL, 'pb_npwp_number', {'std_show': 'only', 'std_show_country_ids': [vn.id, idn.id]})
        env.cr.commit()
        a = arch()
        out.append('locked widened: VN %s ID %s' % (shown(a, 'pb_npwp_number', p_vn), shown(a, 'pb_npwp_number', p_id)))
        for vals in ({'std_show': 'none'}, {'std_show': 'only', 'std_show_country_ids': [vn.id]}):
            try:
                with env.cr.savepoint():
                    S.update_standard(MODEL, 'pb_npwp_number', vals)
                out.append('locked narrowed ALLOWED')
            except Exception as exc:                    # noqa: BLE001
                out.append('locked narrow refused')
        name = 'level_of_health_compensation'
        if name in env[MODEL]._fields:
            S.update_standard(MODEL, name, {'std_show': 'only', 'std_show_country_ids': [vn.id]})
            env.cr.commit()
            a = arch()
            out.append('shown again: VN %s ID %s' % (shown(a, name, p_vn), shown(a, name, p_id)))
        try:
            with env.cr.savepoint():
                S.update_standard(MODEL, 'account_number', {'std_show': 'all'})
            out.append('stays-off ALLOWED')
        except Exception:                               # noqa: BLE001
            out.append('stays-off refused')
        rules = S._pbfs_std_rules(MODEL)
        out.append('rules %s' % len(rules))
        for n in ('pb_safety_group', 'pb_npwp_number', name):
            if n in env[MODEL]._fields:
                S.update_standard(MODEL, n, {'std_show': 'builtin'})
        env.cr.commit()
        after = form_hashes()
        out.append('after reset form = first %s' % (after == before))
    except Exception as exc:                            # noqa: BLE001
        env.cr.rollback()
        out.append('ERROR %s: %s' % (type(exc).__name__, str(exc)[:200]))
    print('PROBE change %s' % '; '.join(out))
env.cr.rollback()
