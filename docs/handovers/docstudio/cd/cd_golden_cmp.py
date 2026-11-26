# DOCSTUDIO close-out D: compare phase F's golden (w2_golden.py) before/after, naming which template
# rows and which columns changed. Expected: letters identical; template rows identical except the
# NAME of the two built-in offer letters (Z3 adds their vi/id names).
import json, sys
def rd(f):
    l = [x for x in open(f) if x.startswith('GOLDEN ')]
    return json.loads(l[0][7:]) if l else None
b, a = rd(sys.argv[1]), rd(sys.argv[2])
if not b or not a:
    print('MISSING OUTPUT'); raise SystemExit
cols = ['id', 'body', 'subject', 'name', 'active', 'company']
tb = {r[0]: r for r in b['templates']}; ta = {r[0]: r for r in a['templates']}
changed = []
for i, r in sorted(tb.items()):
    ra = ta.get(i)
    if ra is None:
        changed.append('%s:gone' % i)
    elif ra != r:
        changed.append('%s:%s' % (i, '+'.join(cols[k] for k in range(len(r)) if r[k] != ra[k])))
print('letters %s (%d); existing template rows changed: %s; rows added: %s' % (
    'IDENTICAL' if a['letters'] == b['letters'] else 'DIFFERENT %s' % [k for k in b['letters'] if a['letters'].get(k) != b['letters'][k]],
    len(b['letters']), ' '.join(changed) or 'none', ' '.join(str(i) for i in sorted(set(ta) - set(tb))) or 'none'))
