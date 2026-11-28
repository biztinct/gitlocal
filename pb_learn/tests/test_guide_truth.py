# -*- coding: utf-8 -*-
"""LEARNREV P1 — T1 the truth gate, T5 no elevation.

Nothing a screen's help says about a field, a choice, a reader or a header may
be untrue, and the build is where that is enforced: every manifest discovered
on this database is checked against the code (`guide_truth.check_files`, the
file half) and against the registry (this file: fields, choices, labels in
both languages, methods, the doors' actions).

Translations: a test database usually has no second language, so the gate
activates Vietnamese and loads the catalogues of every module a manifest leans
on (with overwrite, inside the test transaction) — otherwise "the Vietnamese is
there" would be proven against whatever a database happened to hold.
"""
import inspect
import json
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_learn.models.learn_guide import discover

from . import guide_truth as gt

#: The screens P1 promises a manifest for. The gate fails if one disappears.
EXPECTED = {'treatment', 'mapping', 'runpayroll', 'payruns', 'payslips',
            'approvals', 'dashboard', 'formula',
            # LEARNREV P5a (S3): the next eight.
            'statutory', 'employees', 'import', 'matrix', 'records',
            'payreview', 'govreports', 'wftime'}

FIELD_ATTRS = ['string', 'help', 'selection', 'type']


def read_rel(rel):
    """`module/path/inside` → the file's text, or None."""
    module, _sep, rest = str(rel or '').partition('/')
    base = get_module_path(module, display_warning=False) if module else None
    if not base:
        return None
    path = os.path.join(base, rest)
    if not os.path.isfile(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return fh.read()


_PO = {}


def po_for(module):
    if module not in _PO:
        _PO[module] = gt.live_po(read_rel('%s/i18n/vi_VN.po' % module),
                                 read_rel('%s/i18n/%s.pot' % (module, module)))
    return _PO[module]


def field_modules(field):
    """The modules that define `field` (its translations live in their .po)."""
    mods = getattr(field, '_modules', None) or ()
    if isinstance(mods, str):
        mods = mods.split(',')
    one = getattr(field, '_module', None)
    return {m for m in list(mods) + [one] if m}


def load_vi(env, modules):
    """Activate Vietnamese and load these modules' catalogues from disk,
    overwriting whatever the database held (inside the test transaction)."""
    env['res.lang']._activate_lang('vi_VN')
    installed = env['ir.module.module'].search(
        [('name', 'in', sorted(modules)), ('state', '=', 'installed')])
    env['ir.module.module']._load_module_terms(
        installed.mapped('name'), ['vi_VN'], overwrite=True)
    env.invalidate_all()
    env.registry.clear_cache()


def retired_of(man, lang):
    r = man.get('retired_labels') or {}
    if isinstance(r, (list, tuple)):
        return list(r) if lang == 'en' else []
    return list(r.get(lang) or [])


@tagged('post_install', '-at_install', 'learnrev')
class TestGuideTruth(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manifests = discover(cls.env.registry._init_modules, strict=True)
        cls.content = cls.env['learn.content'].tree()
        cls.anchors = json.loads(read_rel('pb_learn/static/src/anchors.json'))
        # Vietnamese, loaded from the catalogues on disk.
        modules = set()
        for man in cls.manifests.values():
            modules.add(man['_module'])
            for rel in man.get('templates') or ():
                modules.add(rel.split('/', 1)[0])
            model = man.get('model')
            if model and model in cls.env:
                for f in man.get('fields') or ():
                    for name in (f.get('field'), f.get('source_field')):
                        field = cls.env[model]._fields.get(name) if name else None
                        if field is not None:
                            modules.update(field_modules(field))
        load_vi(cls.env, modules)

    # ------------------------------------------------------------ T1
    def test_01_every_promised_screen_has_a_manifest(self):
        missing = EXPECTED - set(self.manifests)
        self.assertFalse(missing, "no manifest discovered for: %s" % sorted(missing))
        for key, man in self.manifests.items():
            self.assertTrue(read_rel('%s/learn_manifest.py' % man['_module']),
                            "%s: its manifest file is not readable" % key)

    def test_02_files_say_what_the_code_says(self):
        errors = []
        for key, man in sorted(self.manifests.items()):
            errors += gt.check_files(key, man, read_rel, self.content, self.anchors,
                                     po_for)
        self.assertFalse(errors, "\n" + "\n".join(errors))

    def test_02b_practice_copies_say_what_the_screens_say(self):
        """LEARNREV P4 (S5) — every manifest column is in the practice copy,
        and every header the copy draws is on the real screen."""
        errors = []
        for key, man in sorted(self.manifests.items()):
            errors += gt.check_replica(key, man, read_rel)
        self.assertFalse(errors, "\n" + "\n".join(errors))

    def test_03_fields_choices_and_methods_exist(self):
        errors = []
        for key, man in sorted(self.manifests.items()):
            errors += self._check_registry(key, man)
        self.assertFalse(errors, "\n" + "\n".join(errors))

    def _check_registry(self, key, man):
        errs = []

        def err(msg):
            errs.append('manifest %s: %s' % (key, msg))

        model = man.get('model')
        en = vi = {}
        if model:
            if model not in self.env:
                err('model %s does not exist' % model)
                return errs
            Model = self.env[model]
            en = Model.with_context(lang='en_US').fields_get(attributes=FIELD_ATTRS)
            vi = Model.with_context(lang='vi_VN').fields_get(attributes=FIELD_ATTRS)
        retired_en = {w.lower() for w in retired_of(man, 'en')}
        retired_vi = {w.lower() for w in retired_of(man, 'vi')}

        def strings(meta):
            out = [meta.get('string') or '', meta.get('help') or '']
            out += [label for _v, label in meta.get('selection') or ()]
            return out

        for f in man.get('fields') or ():
            if f.get('derived'):
                continue
            where = 'field %s' % f.get('key')
            for attr in ('field', 'source_field'):
                name = f.get(attr)
                if not name:
                    continue
                if name not in en:
                    err('%s: %s %s.%s does not exist' % (where, attr, model, name))
                    continue
                m_en, m_vi = en[name], vi.get(name) or {}
                for s in strings(m_en) + strings(m_vi):
                    if re.search('odoo', s, re.IGNORECASE):
                        err('%s: %s.%s says "Odoo": %s' % (where, model, name, s))
                if (m_en.get('string') or '').lower() in retired_en:
                    err('%s: %s.%s is labelled with a retired label "%s"'
                        % (where, model, name, m_en['string']))
                if (m_vi.get('string') or '').lower() in retired_vi:
                    err('%s: %s.%s is labelled with a retired label "%s"'
                        % (where, model, name, m_vi['string']))
                # A missing Vietnamese sentence is a failure, not an English one.
                pairs = [(m_en.get('string'), m_vi.get('string')),
                         (m_en.get('help'), m_vi.get('help'))]
                vi_sel = dict(m_vi.get('selection') or ())
                pairs += [(label, vi_sel.get(value))
                          for value, label in m_en.get('selection') or ()]
                for e_text, v_text in pairs:
                    if e_text and (not v_text or v_text == e_text):
                        err('%s: %s.%s has no Vietnamese for "%s"'
                            % (where, model, name, e_text))
            name = f.get('field')
            if name in en:
                values = {v for v, _l in en[name].get('selection') or ()}
                for choice in (f.get('choices_when') or {}):
                    if choice not in values:
                        err('%s: choice "%s" is not one of %s.%s' % (where, choice,
                                                                     model, name))
        for a in man.get('actions') or ():
            ref = a.get('method') or ''
            amodel, _dot, meth = ref.rpartition('.')
            if amodel not in self.env or not hasattr(self.env[amodel], meth):
                err('action %s does not exist' % ref)
        rn = man.get('right_now')
        if rn:
            rmodel, _dot, meth = rn.rpartition('.')
            if rmodel not in self.env or not hasattr(self.env[rmodel], meth):
                err('right_now %s does not exist' % rn)
        # LEARNREV P4 — a walkthrough check names a method that exists, on a
        # scenario step that exists.
        scenarios = {s['key']: {st['key'] for st in s.get('steps') or ()}
                     for s in self.content.get('scenarios') or ()}
        for ref, target in (man.get('checks') or {}).items():
            sc_key, _dot, step_key = str(ref).partition('.')
            if step_key not in scenarios.get(sc_key, ()):
                err('check %s names no walkthrough step' % ref)
            cmodel, _dot, meth = str(target).rpartition('.')
            if cmodel not in self.env or not hasattr(self.env[cmodel], meth):
                err('check %s → %s does not exist' % (ref, target))
        p = man.get('path') or {}
        xmlids = [p['xmlid']] if p.get('xmlid') else []
        if p.get('tag'):
            hub = next((s for s in self.content['screens']
                        if (s.get('hub') or {}).get('tag') == p['tag']), None)
            if hub:
                xmlids.append(hub['hub']['xmlid'])
        for xmlid in xmlids:
            if not self.env.ref(xmlid, raise_if_not_found=False):
                err('path action %s does not exist' % xmlid)
        # The guide itself: both languages, no exception, nothing unresolved
        # but the live list (which needs screen state the gate does not have).
        for lang in ('en_US', 'vi_VN'):
            out = self.env['learn.guide'].with_context(lang=lang).guide(key)
            bad = [m for m in out['missing'] if not m.startswith('right_now')]
            if bad:
                err('guide(%s) in %s could not resolve: %s' % (key, lang, bad))
            for fld in out['fields']:
                for s in [fld.get('label'), fld.get('help')] + \
                        [c['label'] for c in fld.get('choices') or ()]:
                    if s and re.search('odoo', s, re.IGNORECASE):
                        err('guide(%s) %s prints "Odoo": %s' % (key, lang, s))
        return errs

    # ------------------------------------------------------------ T5
    def test_05_never_elevated(self):
        """`learn_guide.py`, every manifest and every right-now provider's own
        source contain no elevation call."""
        offenders = []
        guide_src = read_rel('pb_learn/models/learn_guide.py') or ''
        if 'sudo(' in guide_src:
            offenders.append('pb_learn/models/learn_guide.py')
        for key, man in self.manifests.items():
            rel = '%s/learn_manifest.py' % man['_module']
            if 'sudo(' in (read_rel(rel) or ''):
                offenders.append(rel)
            rn = man.get('right_now')
            if rn:
                model, _dot, meth = rn.rpartition('.')
                if model in self.env and hasattr(type(self.env[model]), meth):
                    src = inspect.getsource(getattr(type(self.env[model]), meth))
                    if 'sudo(' in src:
                        offenders.append('%s (right now of %s)' % (rn, key))
        self.assertFalse(offenders, "elevated reads in: %s" % offenders)
