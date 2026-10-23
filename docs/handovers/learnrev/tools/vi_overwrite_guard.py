"""LEARNREV P1 deploy: Vietnamese term snapshot / compare (read only).

snap <db> <out.json> <po_root> <modules...>
    For every 'model' entry in <po_root>/<m>/i18n/vi_VN.po, store the DB's current
    vi_VN value (jsonb ->> 'vi_VN') of that record's field; for views named by
    'model_terms' entries, store the whole vi_VN arch.
check <snap.json> <old_po_root> <new_po_root> <modules...>
    Classify every model term where the DB differs from the NEW .po:
    'reword' (DB == old .po msgstr) or 'other' (hand edit / never loaded).
diff <before.json> <after.json>
    Count changed values per module (model terms + views).
"""
import sys, json, re
sys.path.insert(0, '/odoo/odoo-server')
from odoo.tools.translate import PoFileReader
import psycopg2


def entries(root, m):
    with open('%s/%s/i18n/vi_VN.po' % (root, m), 'rb') as f:
        for r in PoFileReader(f):
            if r.get('type') in ('model', 'model_terms') and r.get('imd_name'):
                yield r


def key_of(r):
    mod = r.get('module')
    name = r['imd_name']
    if '.' in name:
        mod, name = name.split('.', 1)
    return r['type'], r['name'], r['imd_model'], mod, name


def snap(db, out, root, mods):
    cn = psycopg2.connect(dbname=db)
    cr = cn.cursor()
    res = {}
    for m in mods:
        for r in entries(root, m):
            typ, fname, model, mod, name = key_of(r)
            cr.execute("select res_id from ir_model_data where module=%s and name=%s and model=%s", (mod, name, model))
            row = cr.fetchone()
            if not row:
                continue
            table = model.replace('.', '_')
            field = fname.split(',', 1)[1]
            k = '%s|%s|%s.%s|%s' % (m, typ, mod, name, field)
            if k in res and typ == 'model_terms':
                continue
            try:
                cr.execute('select "%s"->>%%s, "%s"->>%%s from "%s" where id=%%s' % (field, field, table), ('vi_VN', 'en_US', row[0]))
            except Exception:
                cn.rollback(); continue
            v = cr.fetchone()
            if v is None:
                continue
            res[k] = {'vi': v[0], 'en': v[1]} if typ == 'model' else {'vi': v[0]}
    json.dump(res, open(out, 'w'), ensure_ascii=False)
    print('%s: %d values' % (db, len(res)))


def po_map(root, m):
    d = {}
    for r in entries(root, m):
        typ, fname, model, mod, name = key_of(r)
        if typ == 'model':
            d['%s|%s|%s.%s|%s' % (m, typ, mod, name, fname.split(',', 1)[1])] = (r['src'], r['value'])
    return d


def check(snapf, old_root, new_root, mods):
    s = json.load(open(snapf))
    for m in mods:
        old, new = po_map(old_root, m), po_map(new_root, m)
        rew, other, same = [], [], 0
        for k, (src, val) in new.items():
            if k not in s or not val:
                continue
            dbv = s[k]['vi']
            if dbv == val:
                same += 1
            elif k in old and old[k][1] == dbv:
                rew.append((k, dbv, val))
            else:
                other.append((k, s[k]['en'], dbv, val))
        print('%s: same=%d reword=%d other=%d' % (m, same, len(rew), len(other)))
        for k, dbv, val in rew:
            print('  REWORD %s\n     db : %s\n     new: %s' % (k, dbv, val))
        for k, en, dbv, val in other:
            print('  OTHER  %s (en=%r)\n     db : %r\n     new: %r' % (k, en, dbv, val))


def diff(a, b):
    A, B = json.load(open(a)), json.load(open(b))
    per = {}
    for k in B:
        m, typ = k.split('|')[:2]
        if A.get(k, {}).get('vi') != B[k].get('vi'):
            per.setdefault((m, typ), []).append(k)
    for (m, typ), ks in sorted(per.items()):
        print('%s %s changed=%d' % (m, typ, len(ks)))
        for k in ks[:60]:
            if typ == 'model':
                print('   %s: %r -> %r' % (k, A.get(k, {}).get('vi'), B[k]['vi']))
            else:
                print('   %s' % k)
    if not per:
        print('no changes')


TXT = re.compile(r'>([^<>]+)<')


def texts(arch):
    from collections import Counter
    c = Counter()
    for t in TXT.findall(arch or ''):
        t = ' '.join(t.split())
        if t:
            c[t] += 1
    for t in re.findall(r'(?:string|placeholder|title|help|confirm)="([^"]+)"', arch or ''):
        c['@' + t] += 1
    return c


def viewdiff(a, b):
    A, B = json.load(open(a)), json.load(open(b))
    for k in sorted(B):
        if '|model_terms|' not in k or A.get(k, {}).get('vi') == B[k].get('vi'):
            continue
        ta, tb = texts(A.get(k, {}).get('vi')), texts(B[k].get('vi'))
        print(k)
        for t in sorted(set(ta) - set(tb)):
            print('   - %s' % t)
        for t in sorted(set(tb) - set(ta)):
            print('   + %s' % t)


def restore(db, pre, cand_file):
    """Write back the pre-load vi_VN value for each key listed in cand_file."""
    P = json.load(open(pre))
    cn = psycopg2.connect(dbname=db); cr = cn.cursor(); n = 0
    for k in [l.strip() for l in open(cand_file) if l.strip()]:
        m, typ, xid, field = k.split('|')
        mod, name = xid.split('.', 1)
        val = P[k]['vi']
        if typ != 'model' or val is None:
            continue
        cr.execute("select model, res_id from ir_model_data where module=%s and name=%s", (mod, name))
        model, rid = cr.fetchone()
        cr.execute('update "%s" set "%s" = jsonb_set("%s", \'{vi_VN}\', to_jsonb(%%s::text)) where id=%%s' % (model.replace('.', '_'), field, field), (val, rid))
        n += cr.rowcount
    cn.commit(); print('%s restored=%d' % (db, n))


def candidates(snapf, old_root, new_root, mods, out):
    """Keys where the DB holds a value that neither equals the new .po nor came from the old .po."""
    s = json.load(open(snapf)); ks = []
    for m in mods:
        old, new = po_map(old_root, m), po_map(new_root, m)
        for k, (src, val) in new.items():
            if k in s and val and s[k]['vi'] is not None and s[k]['vi'] != val and not (k in old and old[k][1] == s[k]['vi']):
                ks.append(k)
    open(out, 'w').write('\n'.join(ks) + '\n'); print('candidates=%d' % len(ks))


if __name__ == '__main__':
    if sys.argv[1] == 'viewdiff':
        viewdiff(sys.argv[2], sys.argv[3]); sys.exit()
    if sys.argv[1] == 'restore':
        restore(sys.argv[2], sys.argv[3], sys.argv[4]); sys.exit()
    if sys.argv[1] == 'candidates':
        candidates(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[6:], sys.argv[5]); sys.exit()
    cmd = sys.argv[1]
    if cmd == 'snap':
        snap(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:])
    elif cmd == 'check':
        check(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:])
    elif cmd == 'diff':
        diff(sys.argv[2], sys.argv[3])
