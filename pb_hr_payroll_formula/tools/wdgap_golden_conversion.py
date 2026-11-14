#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WDGAP PR-A safety rail R1 — golden conversion of every formula in the repo.

Collects, programmatically, every Excel formula the repository ships or tests
with — the country pack scheme templates (``pb_pack_*``), the guided-setup
template, the demo scheme XML, the ``pb_demo`` catalogue, and every formula
string literal in the modules' Python (catalogues, fixtures, tests) — and runs
each through the REAL ``hr.formula.rule._convert_excel_to_python`` (odoo is
shimmed exactly as in ``excel_semantics_battery.py``).

    python3 pb_hr_payroll_formula/tools/wdgap_golden_conversion.py --write
        generate the fixture (run ONCE, on the code BEFORE a converter change)
    python3 pb_hr_payroll_formula/tools/wdgap_golden_conversion.py
        check: converting the same formulas must give byte-identical output

Exit code 0 = identical. The fixture lives at
``pb_hr_payroll_formula/tests/data/wdgap_golden_conversion.json`` and is also
checked inside Odoo by ``tests/test_wdgap_pra_dates.py`` (T7).
"""
import ast
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
FIXTURE = os.path.join(REPO_ROOT, 'pb_hr_payroll_formula', 'tests', 'data',
                       'wdgap_golden_conversion.json')

_CODE_RE = re.compile(r'^[A-Z][A-Z0-9]*$')
_TOKEN_RE = re.compile(r'(?<![A-Za-z0-9_$])([A-Z][A-Z0-9]*)(?![A-Za-z0-9_(])')
_CELL_RE = re.compile(r'^[A-Z]{1,3}\d+$')
_STRING_RE = re.compile(r'"(?:[^"]|"")*"')


def _letter(index):
    """0 -> A, 25 -> Z, 26 -> AA (the scheme's column-letter sequence)."""
    out = ''
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        out = chr(65 + rem) + out
    return out


def _formula_tokens(formula):
    body = _STRING_RE.sub('""', formula or '')
    out = []
    for tok in _TOKEN_RE.findall(body):
        if _CELL_RE.match(tok) or tok in ('TRUE', 'FALSE'):
            continue
        out.append(tok)
    return out


def _synthetic_map(codes, formulas):
    """[letter, code] pairs for a source whose letters are not known.

    Deterministic and C5-shaped (a code never equals a letter in use): every
    letter a formula uses (a cell reference's letters, a bare 1-2 letter
    token) maps to ``COL<letter>``; every other code-shaped name (defined by
    the source or read by a formula) gets the next free letter, in sorted
    order. Pairs, not a dict, because the converter's output depends on the
    column map's ORDER and JSON object keys would be re-sorted. The rail
    compares the converter against itself, so the map only has to be stable.
    """
    letters_used = set()
    names = set(c for c in codes if _CODE_RE.match(c or ''))
    for f in formulas:
        body = _STRING_RE.sub('""', f or '')
        letters_used.update(re.findall(r'\$?([A-Z]{1,3})\$?\d+', body))
        for tok in _formula_tokens(f):
            if len(tok) <= 2 and tok.isalpha():
                letters_used.add(tok)
            else:
                names.add(tok)
    names -= letters_used
    pairs = [[letter, 'COL' + letter] for letter in sorted(letters_used)]
    taken = set(letters_used) | names
    index = 0
    for code in sorted(names):
        while _letter(index) in taken:
            index += 1
        pairs.append([_letter(index), code])
        taken.add(_letter(index))
    return pairs


# ---------------------------------------------------------------------------
# Collectors — each yields (source_key, column_map, [formulas])
# ---------------------------------------------------------------------------

def _pack_templates():
    paths = []
    for name in sorted(os.listdir(REPO_ROOT)):
        if name.startswith('pb_pack_'):
            data = os.path.join(REPO_ROOT, name, 'data')
            if os.path.isdir(data):
                paths += [os.path.join(data, f) for f in sorted(os.listdir(data))
                          if f.startswith('config_template') and f.endswith('.xml')]
    blueprint = os.path.join(REPO_ROOT, 'pb_blueprint', 'data', 'config_template_vn_complete.xml')
    if os.path.exists(blueprint):
        paths.append(blueprint)
    for path in paths:
        tree = ET.parse(path)
        for rec in tree.iter('record'):
            for field in rec.iter('field'):
                if field.get('name') != 'components_json' or not (field.text or '').strip():
                    continue
                comps = json.loads(field.text)
                cmap = [[c['column_letter'], c['code']] for c in comps
                        if c.get('column_letter') and c.get('code')]
                formulas = [c['excel_formula'] for c in comps if c.get('excel_formula')]
                key = '%s#%s' % (os.path.relpath(path, REPO_ROOT), rec.get('id'))
                yield key, cmap, formulas


def _demo_formula_xml():
    path = os.path.join(REPO_ROOT, 'pb_hr_payroll_formula', 'data', 'demo_formula_config.xml')
    if not os.path.exists(path):
        return
    tree = ET.parse(path)
    cmap, formulas = [], []
    for rec in tree.iter('record'):
        if rec.get('model') != 'hr.formula.rule':
            continue
        vals = {f.get('name'): (f.text or '').strip() for f in rec.iter('field')}
        if vals.get('code') and vals.get('column_letter'):
            cmap.append([vals['column_letter'], vals['code']])
        if vals.get('excel_formula'):
            formulas.append(vals['excel_formula'])
    if not cmap:
        cmap = _synthetic_map([], formulas)
    yield os.path.relpath(path, REPO_ROOT), cmap, formulas


def _py_files():
    for name in sorted(os.listdir(REPO_ROOT)):
        mod = os.path.join(REPO_ROOT, name)
        if not (name.startswith('pb_') or name.startswith('om_')) or not os.path.isdir(mod):
            continue
        if name.startswith('pb_pack_'):
            pass  # their Python carries no formulas, but scanning is harmless
        for root, dirs, files in os.walk(mod):
            dirs[:] = sorted(d for d in dirs if d not in ('__pycache__', 'static', 'i18n'))
            for f in sorted(files):
                if f.endswith('.py'):
                    yield os.path.join(root, f)


def _python_literals():
    """Every formula-shaped string literal in the modules' Python.

    * the value of an ``'excel_formula'`` dict key / ``excel_formula=`` kwarg;
    * in ``pb_demo``'s catalogue and in every ``tests/`` and ``tools/`` file
      (the batteries): any string that starts with ``=`` and has a letter in
      it (catalogue rows and fixtures are positional tuples).

    Files added AFTER the fixture was written (this phase's own tests) are not
    in the fixture; the check only replays the fixture's formulas.
    """
    for path in _py_files():
        rel = os.path.relpath(path, REPO_ROOT)
        broad = ('/tests/' in '/' + rel or '/tools/' in '/' + rel
                 or rel.startswith('pb_demo/models/demo_catalog'))
        if rel.endswith('tools/wdgap_golden_conversion.py'):
            continue
        try:
            with open(path, encoding='utf-8') as fh:
                tree = ast.parse(fh.read())
        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue
        codes, formulas = [], []

        def _str(node):
            return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None

        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values):
                    ks, vs = _str(k) if k is not None else None, _str(v)
                    if ks == 'excel_formula' and vs:
                        formulas.append(vs)
                    elif ks == 'code' and vs:
                        codes.append(vs)
            elif isinstance(node, ast.keyword) and node.arg == 'excel_formula':
                vs = _str(node.value)
                if vs:
                    formulas.append(vs)
            elif isinstance(node, ast.Tuple) and node.elts:
                first = _str(node.elts[0])
                if first and _CODE_RE.match(first):
                    codes.append(first)
            if broad:
                vs = _str(node)
                if vs and vs.startswith('=') and re.search(r'[A-Za-z]', vs) and len(vs) < 4000:
                    formulas.append(vs)
        formulas = sorted(set(f for f in formulas if f.strip()))
        if formulas:
            yield rel, _synthetic_map(codes, formulas), formulas


def collect():
    sources = []
    for gen in (_pack_templates, _demo_formula_xml, _python_literals):
        for key, cmap, formulas in gen():
            sources.append({'source': key, 'column_map': cmap,
                            'formulas': sorted(set(formulas))})
    return sources


# ---------------------------------------------------------------------------
# Conversion through the real code (odoo shimmed, as the battery does)
# ---------------------------------------------------------------------------

def _rule_class():
    sys.path.insert(0, HERE)
    import excel_semantics_battery as battery  # installs the shim on import
    return battery.RuleCls


def convert_all(sources, rule_cls=None):
    rule_cls = rule_cls or _rule_class()
    rule = object.__new__(rule_cls)
    rule.config_id = None          # BRACKET expansion needs a database; the
    rule.code = 'GOLDEN'           # converter is checked on its own text pass
    out = []
    for src in sources:
        converted = {}
        for formula in src['formulas']:
            text = formula[1:] if formula.startswith('=') else formula
            try:
                column_map = {letter: code for letter, code in src['column_map']}
                converted[formula] = rule._convert_excel_to_python(text, column_map)
            except Exception as e:  # noqa: BLE001 — a refusal is an output too
                converted[formula] = '<ERROR %s: %s>' % (type(e).__name__, e)
        out.append(dict(src, converted=converted))
    return out


def main(argv):
    if '--write' in argv:
        data = convert_all(collect())
        os.makedirs(os.path.dirname(FIXTURE), exist_ok=True)
        with open(FIXTURE, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write('\n')
        n = sum(len(s['formulas']) for s in data)
        print('wrote %d formulas from %d sources to %s' % (
            n, len(data), os.path.relpath(FIXTURE, REPO_ROOT)))
        return 0
    with open(FIXTURE, encoding='utf-8') as fh:
        golden = json.load(fh)
    fresh = convert_all([{k: s[k] for k in ('source', 'column_map', 'formulas')}
                         for s in golden])
    diffs = 0
    total = 0
    for old, new in zip(golden, fresh):
        for formula, before in old['converted'].items():
            total += 1
            after = new['converted'][formula]
            if before != after:
                diffs += 1
                print('DIFF %s\n  formula: %s\n  before : %s\n  after  : %s' % (
                    old['source'], formula, before, after))
    print('R1 golden conversion: %d formulas from %d sources, %d differ -> %s' % (
        total, len(golden), diffs, 'IDENTICAL' if not diffs else 'CHANGED'))
    return 1 if diffs else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
