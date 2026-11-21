"""Compare two dump folders (baseline vs after). Prints per file: identical or the
multiset differences of rows (order-independent within a tab; tab membership kept)."""
import collections
import json
import os
import sys

a, b = sys.argv[1], sys.argv[2]
ignore_values = '--no-values' in sys.argv
files = sorted(f for f in os.listdir(a) if f.endswith('.json'))
same = diff = 0
for f in files:
    da = json.load(open(os.path.join(a, f)))
    pb = os.path.join(b, f)
    if not os.path.exists(pb):
        print('MISSING after', f)
        diff += 1
        continue
    db = json.load(open(pb))

    def norm(d):
        rows = []
        for r in d.get('rows', []):
            r = list(r)
            if ignore_values and r[0] == 'F':
                r = r[:6]
            rows.append(tuple(r))
        return collections.Counter(rows)
    ca, cb = norm(da), norm(db)
    errs_a, errs_b = da.get('errors', []), db.get('errors', [])
    if ca == cb and da.get('error') == db.get('error') and len(errs_a) == len(errs_b):
        same += 1
        print('SAME %-28s rows=%d vu %s->%s errors %d->%d' % (f, sum(ca.values()), da.get('vuForm'), db.get('vuForm'), len(errs_a), len(errs_b)))
        continue
    diff += 1
    print('DIFF', f, 'errors', len(errs_a), '->', len(errs_b), da.get('error'), db.get('error'))
    for r, n in sorted((ca - cb).items(), key=str):
        print('   - %dx %s' % (n, r))
    for r, n in sorted((cb - ca).items(), key=str):
        print('   + %dx %s' % (n, r))
    for e in errs_b:
        print('   ERR', e)
print('TOTAL same=%d diff=%d' % (same, diff))
