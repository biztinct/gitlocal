# FS-16 open-the-screens probe (odoo-bin shell). Counts and hashes only — never names, values or
# account numbers. Clone of fs15/fs15_probe.py (same page hashing), for what FS-16 touches:
#   * Full details: the employee form as HR sees it (en + vi + id). `forms` = md5 of the form with the
#     15 deleted Vietnam boxes (and the two empty pieces that held only them) taken out and the
#     white space normalised — so the old and the new form compare equal exactly when nothing else
#     changed; `forms_raw` = the plain md5;
#   * the side panel: md5 of the panel's tabs for up to 3 people per Country of Work (+ none);
#   * the Form builder (employee): standard fields listed, taken off the screens (can come back /
#     stay off), library rows; the 4 stay-off boxes listed anywhere (must be 0 after);
#   * People › Add employee: the defaults load, the bank list size, whether the bank check is there;
#   * the Approvals inbox (head + first page) opens for the administrator;
#   * the administrator's /my and /my/profile; employee pages for up to 3 logins.
#   * PROBE_CHANGE=1 (REHEARSAL COPIES ONLY — commits on the copy): a new hire with bank details
#     (route "No approval needed" for new hires on the copy) → one waiting bank change, old boxes
#     empty, nothing in either bank store; approved by its seat holder → both stores written.
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

TOKENS = re.compile(rb'[0-9a-f]{40}o[0-9]+')
ASSETS = re.compile(rb'/web/assets/[^"\' ]+|"registry_hash": "[0-9a-f]+"|data-server-now-ms="[0-9]+"')
host = os.environ.get('PROBE_HOST') or 'localhost'
admin_only = os.environ.get('PROBE_ADMIN_ONLY') == '1'
db = env.cr.dbname
MODEL = 'hr.employee'
DELETED = ('vn_foreign_insurance_exempt', 'vn_si_number', 'vn_si_effective_date', 'vn_hi_number',
           'vn_hi_effective_date', 'vn_ui_number', 'vn_ui_effective_date', 'vn_tax_table_id',
           'vn_tax_effective_date', 'vn_employer_insurance_cost', 'vn_employee_insurance_cost',
           'vn_total_insurance_contribution', 'vn_personal_tax_rate', 'vn_monthly_tax_allowance',
           'vn_dependent_tax_allowance')
STAY_OFF = ('account_number', 'bank_name', 'contract_type_id', 'structure_type_id')


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


def normalised(arch_text):
    """The form without the 15 deleted boxes: their <field> nodes out, the "Contribution Summary"
    group (it held only three of them) and the "Dependent Tax Allowance" line out, white space
    normalised. Applied to the old AND the new form."""
    root = etree.fromstring(arch_text.encode())
    for node in list(root.iter('field')):
        if node.get('name') in DELETED and not any(a.tag == 'field' for a in node.iterancestors()):
            node.getparent().remove(node)
    for grp in list(root.iter('group')):
        if 'o_label_nowrap' in (grp.get('class') or '') and not list(grp.iter('field')):
            grp.getparent().remove(grp)
    for div in list(root.iter('div')):
        # a line left with only its bold heading (any language), the same rule old and new
        if len(div) == 1 and div[0].tag == 'strong' and not list(div.iter('field')):
            div.getparent().remove(div)
    for el in root.iter():
        el.text = (el.text or '').strip() or None
        el.tail = (el.tail or '').strip() or None
    return etree.tostring(root)


env.cr.commit()
Emp = env['hr.employee'].sudo()
admin = env.ref('base.user_admin')
if not admin.has_group('base.group_system'):
    admin = env['res.users'].search([('share', '=', False), ('id', '!=', 1)]).filtered(
        lambda u: u.has_group('base.group_system'))[:1]
langs = [l for l in ('en_US', 'vi_VN', 'id_ID') if env['res.lang']._lang_get(l)]
e = env(user=admin.id, context={'allowed_company_ids': admin.company_ids.ids})
emp_view = env.ref('hr.view_employee_form')


def forms():
    env.registry.clear_cache('templates')
    norm, raw = [], []
    for lang in langs:
        # as HR sees it (superuser reads every group's tabs)
        arch = Emp.with_context(lang=lang).get_view(emp_view.id, 'form')['arch']
        norm.append('%s:%s' % (lang[:2], md5(normalised(arch))))
        raw.append('%s:%s' % (lang[:2], md5(arch.encode())))
    left = sum(1 for n in etree.fromstring(Emp.get_view(emp_view.id, 'form')['arch'].encode()).iter('field')
               if n.get('name') in DELETED)
    return ' '.join(norm), ' '.join(raw), left


fn, fr, left = forms()
print('PROBE forms %s' % fn)
print('PROBE forms_raw %s deleted-boxes-in-form %s' % (fr, left))

# the side panel, up to 3 people per Country of Work (Vietnam first)
codes = [c for c, in env.cr.execute("select distinct coalesce(payroll_country,'') from hr_employee where active") or env.cr.fetchall()]
panel = []
for code in sorted(codes, key=lambda c: (c != 'VN', c)):
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
        res.append('employee standard %s, off the screens %s (can come back %s, stay off %s)' % (
            len(std), len(off), sum(1 for s in off if not s['comeback']),
            sum(1 for s in off if s['comeback'])))
        res.append('stay-off boxes listed %s' % sum(1 for n in STAY_OFF if n in d['fields']))
        lib = S.library()
        lstd = [r for r in lib['std'] if r.get('model') == MODEL]
        res.append('library std rows %s, off %s, stay-off listed %s' % (
            len(lstd), sum(1 for r in lstd if r['stdbox'].get('off')),
            sum(1 for r in lstd if r['name'] in STAY_OFF)))
except Exception as exc:                                # noqa: BLE001
    res.append('ERROR %s: %s' % (type(exc).__name__, str(exc)[:200]))
print('PROBE screens %s' % '; '.join(res))
env.cr.rollback()

nh = []
try:
    with env.cr.savepoint():
        dflt = e['pb.people.onboard.wizard'].get_defaults()
        nh.append('defaults ok, banks %s, bank check %s' % (len(dflt.get('banks') or []), dflt.get('bank_check')))
except Exception as exc:                                # noqa: BLE001
    nh.append('ERROR %s: %s' % (type(exc).__name__, str(exc)[:200]))
try:
    with env.cr.savepoint():
        I = e['pb.approval.inbox'].with_context(pbf_ctx={'scope': 'me'})
        I.get_inbox_head()
        page = I.get_inbox_page()
        nh.append('inbox ok (%s cards)' % len(page.get('cards') or []))
except Exception as exc:                                # noqa: BLE001
    nh.append('inbox ERROR %s: %s' % (type(exc).__name__, str(exc)[:200]))
print('PROBE newhire %s' % '; '.join(nh))
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

if os.environ.get('PROBE_CHANGE') == '1' and db.startswith('fs16_rh_'):
    out = []
    try:
        env['biz.approval.seed'].sudo().set_no_approval_needed(admin.company_id, 'newhire')
        W = env['pb.people.onboard.wizard'].with_user(admin).with_context(
            allowed_company_ids=[admin.company_id.id])
        r = W.create_employee({'name': 'DEMO FS16 Rehearsal', 'with_contract': False,
                               'bank_name': 'Vietcombank', 'account_number': '0123 4567 8901',
                               'account_holder': 'DEMO FS16 REHEARSAL'})
        env.cr.commit()
        new = Emp.browse(r.get('employee_id') or 0)
        out.append('new hire made %s, bank %s' % (bool(new.exists()), (r.get('bank') or {}).get('state')))
        Req = env['pb.bank.change.request'].sudo()
        req = Req.search([('employee_id', '=', new.id)])
        out.append('bank changes %s state %s route %s' % (
            len(req), req[:1].state, req[:1].approval_request_id.process_id.key))
        out.append('old boxes empty %s; stores empty %s' % (
            not any(new[f] for f in ('account_number', 'bank_name') if f in new._fields),
            not new.vietnam_bank_account_number and not new.bank_account_ids))
        request = req[:1].approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        seat = step.seat_ids.filtered(lambda s: s.status == 'open' and s.acting_user_id != admin)[:1]
        out.append('second person seated %s (typist seated %s)' % (
            bool(seat), admin in step.seat_ids.acting_user_id))
        if seat:
            env['biz.approval.engine'].with_user(seat.acting_user_id).decide(request.id, step.key, 'approve')
            env.cr.commit()
            env.invalidate_all()
            out.append('approved: state %s, bank file number set %s, account first %s' % (
                req[:1].state, bool(new.vietnam_bank_account_number),
                bool(new.bank_account_ids[:1]) and new.bank_account_ids[:1].acc_number == new.vietnam_bank_account_number))
    except Exception as exc:                            # noqa: BLE001
        env.cr.rollback()
        out.append('ERROR %s: %s' % (type(exc).__name__, str(exc)[:200]))
    print('PROBE change %s' % '; '.join(out))
env.cr.rollback()
