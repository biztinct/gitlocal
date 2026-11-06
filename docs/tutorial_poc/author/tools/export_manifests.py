#!/usr/bin/env python3
"""LEARNREV P4 — the screen manifests, exported for the content generator.

    python3 docs/tutorial_poc/author/tools/export_manifests.py      # JSON on stdout

WHY THE GENERATOR NEEDS THEM
----------------------------
A lesson step may say `field: "<screen>.<field key>"`. The generator then
WRITES that step's "It means" from the field's own one-line help and its "It
affects" from the field's first three readers plus what changing it does — the
same words the Guide's field card shows (pb_learn/models/learn_guide.py). An
author writes only what to look at and what to press, so a step about a column
cannot drift from the column (truth by construction, LEARNREV P1 rule).

HOW, WITHOUT A DATABASE
-----------------------
The generator runs offline, so the loader is the P1 offline truth gate's: each
`<module>/learn_manifest.py` is plain data and is imported by file path. The
field's help is NOT in the manifest (P1: labels and help come from the field);
it is read from the model source with `ast`, and its Vietnamese from the
defining module's `i18n/vi_VN.po` (the reader the truth gate uses,
`pb_learn/tests/guide_truth.py parse_po`). When several modules define the
same field, the one deepest in the dependency chain wins — the one Odoo loads
last, so the one whose help the screen shows.
"""
import ast
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))

_SKIP_DIRS = {'docs', 'node_modules', '.git', '.claude', '__pycache__'}


def _load_py(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _gt():
    return _load_py(os.path.join(REPO, 'pb_learn', 'tests', 'guide_truth.py'), 'guide_truth_x')


def modules(repo=REPO):
    return sorted(d for d in os.listdir(repo)
                  if d not in _SKIP_DIRS and not d.startswith('.')
                  and os.path.isfile(os.path.join(repo, d, '__manifest__.py')))


def load_manifests(repo=REPO):
    """{screen_key: manifest + `_module`} — exactly the gate's loader."""
    out = {}
    for mod in modules(repo):
        path = os.path.join(repo, mod, 'learn_manifest.py')
        if not os.path.isfile(path):
            continue
        m = _load_py(path, 'learn_manifest_%s' % mod)
        for key, man in (getattr(m, 'MANIFESTS', None) or {}).items():
            out[key] = dict(man, _module=mod)
    return out


# ------------------------------------------------------------ model source
_DEPTH = {}


def _depends(repo, mod):
    path = os.path.join(repo, mod, '__manifest__.py')
    try:
        with open(path, encoding='utf-8') as fh:
            return list(ast.literal_eval(fh.read()).get('depends') or [])
    except Exception:                                         # noqa: BLE001
        return []


def depth(repo, mod, seen=None):
    """How far down the dependency chain a module sits (0 = depends on
    nothing we know). Odoo loads deeper modules later."""
    if mod in _DEPTH:
        return _DEPTH[mod]
    seen = set(seen or ()) | {mod}
    deps = [d for d in _depends(repo, mod)
            if d not in seen and os.path.isdir(os.path.join(repo, d))]
    _DEPTH[mod] = 1 + max([depth(repo, d, seen) for d in deps] or [-1])
    return _DEPTH[mod]


def _str(node):
    try:
        v = ast.literal_eval(node)
    except Exception:                                         # noqa: BLE001
        return None
    return v if isinstance(v, str) else None


def _class_models(cls):
    names = set()
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name) \
                and stmt.targets[0].id in ('_name', '_inherit'):
            try:
                v = ast.literal_eval(stmt.value)
            except Exception:                                 # noqa: BLE001
                continue
            names.update([v] if isinstance(v, str) else list(v or []))
    return names


def field_helps(repo, model, field_names):
    """{field: (module, help_en)} for the fields that carry a `help=`."""
    found = {}
    wanted = set(field_names)
    needle = "'%s'" % model
    for mod in modules(repo):
        base = os.path.join(repo, mod)
        for sub in ('models', 'wizard', 'wizards'):
            folder = os.path.join(base, sub)
            if not os.path.isdir(folder):
                continue
            for fn in sorted(os.listdir(folder)):
                if not fn.endswith('.py'):
                    continue
                path = os.path.join(folder, fn)
                with open(path, encoding='utf-8') as fh:
                    src = fh.read()
                if needle not in src and ('"%s"' % model) not in src:
                    continue
                try:
                    tree = ast.parse(src)
                except SyntaxError:
                    continue
                for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
                    if model not in _class_models(cls):
                        continue
                    for stmt in cls.body:
                        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                                and isinstance(stmt.targets[0], ast.Name)
                                and stmt.targets[0].id in wanted
                                and isinstance(stmt.value, ast.Call)):
                            continue
                        helptext = None
                        for kw in stmt.value.keywords:
                            if kw.arg == 'help':
                                helptext = _str(kw.value)
                        if not helptext:
                            continue
                        name = stmt.targets[0].id
                        prev = found.get(name)
                        if prev is None or depth(repo, mod) >= depth(repo, prev[0]):
                            found[name] = (mod, helptext)
    return found


_PO = {}


def po(repo, mod):
    if mod not in _PO:
        gt = _gt()
        read = lambda rel: (open(os.path.join(repo, rel), encoding='utf-8').read()  # noqa: E731
                            if os.path.isfile(os.path.join(repo, rel)) else None)
        _PO[mod] = gt.live_po(read('%s/i18n/vi_VN.po' % mod), read('%s/i18n/%s.pot' % (mod, mod)))
    return _PO[mod]


def vi_of(repo, mod, english):
    """The Vietnamese the screen shows for a help text: the defining module's
    catalogue first, then any module's (a help may be re-declared)."""
    norm = lambda s: ' '.join(str(s or '').split())               # noqa: E731
    want = norm(english)
    for m in [mod] + [x for x in modules(repo) if x != mod]:
        for msgid, msgstr in po(repo, m).items():
            if norm(msgid) == want:
                return msgstr
    return ''


# ------------------------------------------------------------ one sentence
_FIRST = re.compile(r'^.*?[.!?](?=\s|$)', re.S)


def first_sentence(text):
    """The first sentence — `learn_guide.first_sentence` without the cap."""
    t = ' '.join(str(text or '').split())
    hit = _FIRST.match(t)
    return hit.group(0) if hit else t


def pair_first(pair):
    if not pair:
        return None
    return {'en': first_sentence(pair.get('en')), 'vi': first_sentence(pair.get('vi'))}


# ------------------------------------------------------------ the export
def export(repo=REPO):
    out = {}
    for key, man in sorted(load_manifests(repo).items()):
        model = man.get('model')
        names = [f['field'] for f in man.get('fields') or () if f.get('field')]
        helps = field_helps(repo, model, names) if model and names else {}
        fields = {}
        for f in man.get('fields') or ():
            hit = helps.get(f.get('field')) if f.get('field') else None
            help_pair = None
            if hit:
                mod, en = hit
                help_pair = {'en': ' '.join(en.split()), 'vi': ' '.join(vi_of(repo, mod, en).split())}
            fields[f['key']] = {
                'column': f.get('column') or {},
                'derived': bool(f.get('derived')),
                'field': f.get('field') or '',
                'help': help_pair,
                'how': f.get('how') or None,
                'filled_by': f.get('filled_by') or None,
                'used_by': [u.get('label') or {} for u in f.get('used_by') or ()],
                'if_changed': f.get('if_changed') or None,
                'anchor': f.get('anchor') or '',
            }
        out[key] = {'module': man['_module'], 'model': model or '', 'fields': fields,
                    'checks': dict(man.get('checks') or {})}
    return out


if __name__ == '__main__':
    json.dump(export(), sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)
    sys.stdout.write('\n')
