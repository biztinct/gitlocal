"""WF2 P5b: prove the Vietnamese and Indonesian words load, on a real database.

    odoo-bin shell -d <db> --no-http < tools/workflow_studio/p5b_language_proof.py
    (P5B_SCOPE=/path/to/data_p5b_scope.json when not run from the repo root)

Read only (rolls back). For every string this phase translated
(`data_p5b_scope.json`):
  * code strings (`_()`, `_t`, OWL templates): what Odoo's own loader returns
    for the module and language (reads the module's .po on THIS server);
  * stored values (views, mail templates, the new right and ability): the
    value saved in the database for that language — a translation fix is two
    fixes, the .po and the stored value.
Prints one P5B_PROOF= line: remaining-English counts per file per language
(0 is the target) and the stored values per record and language.
"""
import html
import json
import os
import re
from collections import defaultdict

from odoo.tools.translate import PoFileReader, code_translations
from odoo.modules import get_module_path

SCOPE = os.environ.get('P5B_SCOPE') or os.path.join(os.getcwd(), 'tools/workflow_studio/data_p5b_scope.json')
rows = json.load(open(SCOPE, encoding='utf-8'))
LANGS = [code for code in ('vi_VN', 'id_ID') if env['res.lang']._lang_get(code)]


def po_values(module, lang):
    out = {}
    path = os.path.join(get_module_path(module), 'i18n', lang + '.po')
    if os.path.exists(path):
        for row in PoFileReader(path):
            if row.get('value'):
                out[(row['type'], row.get('imd_name') or '', row['src'])] = row['value']
                out.setdefault(('any', '', row['src']), row['value'])
    return out


po = {}
remaining = defaultdict(lambda: defaultdict(list))   # file -> lang -> [src]
checked = defaultdict(lambda: defaultdict(int))
stored = {}
for r in rows:
    module = r['module']
    for lang in r['langs']:
        if lang not in LANGS:
            continue
        if r['kind'] in ('python', 'javascript'):
            where = r['occ'][0][1]
            if r['kind'] == 'python':
                got = code_translations.get_python_translations(module, lang).get(r['src'])
            else:
                messages = code_translations.get_web_translations(module, lang)['messages']
                got = next((m['string'] for m in messages if m['id'] == r['src']), None)
            checked[where][lang] += 1
            if not got or got == r['src']:
                remaining[where][lang].append(r['src'][:80])
            continue
        values = po.setdefault((module, lang), po_values(module, lang))
        for name, xmlid in r['occ']:
            model, field = name.split(',')
            record = env.ref(xmlid, raise_if_not_found=False)
            key = '%s %s %s' % (xmlid, field, lang)
            checked[xmlid][lang] += 1
            if not record:
                stored[key] = 'missing record'
                remaining[xmlid][lang].append(r['src'][:80])
                continue
            value = record.with_context(lang=lang)[field] or ''
            english = record.with_context(lang='en_US')[field] or ''
            want = values.get((r['kind'], xmlid.split('.', 1)[1], r['src'])) or values.get(('any', '', r['src']))
            if r['kind'] == 'model_terms':
                # a term with an inline element reads "{{0}} more stages"
                pieces = [p.strip() for p in re.split(r'\{\{\d+\}\}', want or '') if p.strip()]
                ok = bool(want) and all(p in value or html.escape(p, quote=False) in value for p in pieces)
            else:
                ok = bool(value) and value != english
            stored[key] = stored.get(key, True) and ok
            if not ok:
                remaining[xmlid][lang].append(r['src'][:80])

report = {
    'database': env.cr.dbname, 'languages': LANGS,
    'per_file': {f: {lang: {'checked': checked[f][lang], 'still_english': len(remaining[f][lang])}
                     for lang in LANGS} for f in sorted(checked)},
    'still_english': {f: {lang: v for lang, v in d.items() if v} for f, d in remaining.items() if any(d.values())},
    'stored_ok': sum(1 for v in stored.values() if v is True), 'stored_not_ok': sorted(k for k, v in stored.items() if v is not True),
    'totals': {lang: {'checked': sum(checked[f][lang] for f in checked),
                      'still_english': sum(len(remaining[f][lang]) for f in remaining)} for lang in LANGS},
}
print('P5B_PROOF=' + json.dumps(report, ensure_ascii=False))
env.cr.rollback()
