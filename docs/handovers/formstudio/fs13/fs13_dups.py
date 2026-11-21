# FS-13 item 4 probe (odoo-bin shell, read-only, rolled back): labels shared by two or more
# DIFFERENT fields in the lists the three builders draw — the employee and contract Form builder
# (Standard fields tab, the fixed sections' lines per section) and the My Payobook page builder.
# Also one field listed twice in one list. Prints field CODES and labels only, never values.
import collections

admin = env.ref('base.user_admin')
if not admin.has_group('base.group_system'):
    admin = env['res.users'].search([('share', '=', False), ('id', '!=', 1)]).filtered(
        lambda u: u.has_group('base.group_system'))[:1]


def fold(t):
    return ' '.join(str(t or '').lower().split())


def report(tag, rows):
    """rows: [(name, label)]"""
    by = collections.defaultdict(set)
    seen = collections.Counter(n for n, _l in rows if n)
    for n, l in rows:
        if n:
            by[fold(l)].add(n)
    same = {l: sorted(ns) for l, ns in by.items() if len(ns) > 1}
    twice = sorted(n for n, c in seen.items() if c > 1)
    print('DUPS %s rows %s same-label %s %s twice %s' % (tag, len(rows), len(same), same, twice))


for lang in ('en_US', 'vi_VN'):
    if not env['res.lang']._lang_get(lang):
        continue
    S = env(user=admin.id, context={'lang': lang, 'allowed_company_ids': admin.company_ids.ids})['pb.form.studio']
    with env.cr.savepoint():
        hosts = S._pbfs_hosts()
        for host in ('employee_detail', 'contract'):
            if host not in hosts:
                continue
            d = S.get_studio(host)
            flds = d.get('fields') or {}
            flds = flds if isinstance(flds, dict) else {f['name']: f for f in flds}
            std = []
            for f in flds.values():
                if f.get('custom') or f.get('deleted') or not (f.get('stdbox') or f.get('portal')):
                    continue
                s = f.get('stdbox') or {}
                std.append((f['name'], (s.get('labels') or {}).get(lang) or s.get('builtin') or f.get('label')))
            report('%s/%s/standard-tab' % (lang, host), std)
            for sec, items in (d.get('fixed') or {}).items():
                rows = []
                for it in items:
                    f = flds.get(it.get('ref')) if it.get('ref') else None
                    if not f:
                        continue
                    s = f.get('stdbox') or {}
                    lab = ((s.get('labels') or {}).get(lang) if (s.get('labels') or {}) else None) or it.get('label')
                    rows.append((f['name'], lab))
                if rows:
                    report('%s/%s/fixed:%s' % (lang, host, sec), rows)
        if hasattr(S, 'page_studio'):
            p = S.page_studio()
            report('%s/page-builder' % lang, [(n, r['label']) for n, r in p['fields'].items()])
env.cr.rollback()
