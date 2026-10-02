# -*- coding: utf-8 -*-
"""U13 — every word of these screens exists in Vietnamese.

Two halves, and both are needed. COMPLETENESS: a term the module exports and
the catalogue has never seen is a survivor, and one English sentence in the
middle of a Vietnamese screen reads as a broken screen rather than a foreign
one. CORRECTNESS: no entry is empty or fuzzy, no placeholder is lost in
translation, and nothing says the vendor's name.
"""
import os
import re

from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.basename(HERE)


@tagged('post_install', '-at_install')
class TestVietnameseIsComplete(TransactionCase):

    def _catalogue(self):
        import polib
        path = os.path.join(HERE, 'i18n', 'vi_VN.po')
        self.assertTrue(os.path.exists(path),
                        '%s has no Vietnamese catalogue' % MODULE)
        return polib.pofile(path)

    def test_u13_every_word_of_this_module_exists_in_vietnamese(self):
        po = self._catalogue()
        self.assertEqual(po.metadata.get('Language'), 'vi_VN')

        done = {e.msgid: e.msgstr for e in po if not e.obsolete}
        empty = [k for k, v in done.items() if not (v or '').strip()]
        self.assertFalse(
            empty[:20],
            '%s of %s terms are still English: %s'
            % (len(empty), len(done), empty[:20]))

        fuzzy = [e.msgid[:60] for e in po if 'fuzzy' in (e.flags or [])]
        self.assertFalse(fuzzy[:10],
                         'a fuzzy entry is not a translation: %s' % fuzzy[:10])

    def test_u13_no_translated_string_says_the_vendors_name(self):
        po = self._catalogue()
        said = [e.msgid[:60] for e in po
                if 'odoo' in (e.msgstr or '').lower()]
        self.assertFalse(said, 'a translated string says the wrong name: %s'
                         % said)

    def test_u13_no_translation_loses_a_placeholder(self):
        po = self._catalogue()
        broken = []
        for entry in po:
            if entry.obsolete or not entry.msgstr:
                continue
            for hit in set(re.findall(r'%\([^)]+\)s', entry.msgid)):
                if hit not in entry.msgstr:
                    broken.append('%s -> %s' % (entry.msgid[:40], hit))
            if entry.msgid.count('%s') != entry.msgstr.count('%s'):
                broken.append('%s -> %%s count' % entry.msgid[:40])
        self.assertFalse(broken[:10],
                         'a translation lost a placeholder: %s' % broken[:10])

    def test_u13_the_catalogue_covers_the_whole_exported_template(self):
        """The template is committed beside the catalogue and refreshed from
        the platform's own exporter, which is the authority on what this
        module actually shows a person."""
        import polib
        pot_path = os.path.join(HERE, 'i18n', '%s.pot' % MODULE)
        self.assertTrue(os.path.exists(pot_path),
                        '%s has no exported template' % MODULE)
        pot = polib.pofile(pot_path)
        have = {e.msgid for e in self._catalogue() if not e.obsolete}
        missing = sorted({e.msgid for e in pot if e.msgid} - have)
        self.assertFalse(
            missing[:20],
            '%s terms are exported but not translated: %s'
            % (len(missing), missing[:20]))


#: Every module Phase 7 put new words into. One suite covers all of them: a
#: Vietnamese test per module would be nineteen suites to run for a check that
#: is the same nineteen times, and the words are the programme's rather than
#: any one module's.
P7_MODULES = (
    'biz_approval_workflow', 'pb_approval_config', 'pb_budget', 'pb_close',
    'pb_comp_ben', 'pb_demo', 'pb_demo_seed', 'pb_formula_studio',
    'pb_govt_reports', 'pb_group', 'pb_hr_fullandfinal',
    'pb_hr_payroll_formula', 'pb_hr_payroll_vietnam', 'pb_lifecycle',
    'pb_pay', 'pb_people_advanced', 'pb_probation', 'pb_scheme_map',
    'pb_statutory', 'pb_tenants', 'pb_contracts',
)

#: The marker each module's Phase-7 block carries.
P7_MARKER = 'Approval Matrix phase 7'


@tagged('post_install', '-at_install')
class TestP7Vietnamese(TransactionCase):
    """Z06's other half — the new words, in Vietnamese, in every module."""

    def _root(self):
        return os.path.dirname(HERE)

    def test_z06c_every_p7_module_has_a_vietnamese_catalogue(self):
        missing = [m for m in P7_MODULES
                   if not os.path.exists(
                       os.path.join(self._root(), m, 'i18n', 'vi_VN.po'))]
        self.assertFalse(missing,
                         'these modules ship new words with no Vietnamese: %s'
                         % missing)

    def test_z06d_every_p7_block_is_filled_in(self):
        thin = []
        for module in P7_MODULES:
            path = os.path.join(self._root(), module, 'i18n', 'vi_VN.po')
            if not os.path.exists(path):
                continue
            text = open(path, encoding='utf-8').read()
            if P7_MARKER not in text \
                    and 'browser walk' not in text \
                    and module != 'biz_approval_workflow':
                thin.append('%s: no Phase-7 block' % module)
                continue
            # The block itself, read as text: a `#. module:` comment is not
            # a marker polib hands back, and the question here is about the
            # entries this phase ADDED rather than about the whole file.
            marker = P7_MARKER if P7_MARKER in text else 'browser walk'
            block = text.split(marker, 1)[-1]
            pairs = re.findall(r'^msgid "(.*)"\nmsgstr "(.*)"$', block, re.M)
            self.assertTrue(pairs, '%s: the Phase-7 block is empty' % module)
            empty = [msgid[:50] for msgid, msgstr in pairs
                     if msgid and not msgstr.strip()]
            if empty:
                thin.append('%s: %s' % (module, empty[:5]))
        self.assertFalse(thin, 'the Phase-7 words are not translated: %s'
                               % thin)

    def test_z06e_no_p7_translation_loses_a_placeholder(self):
        import polib
        broken = []
        for module in P7_MODULES:
            path = os.path.join(self._root(), module, 'i18n', 'vi_VN.po')
            if not os.path.exists(path):
                continue
            for entry in polib.pofile(path):
                if entry.obsolete or not entry.msgstr:
                    continue
                for hit in set(re.findall(r'%\([^)]+\)s', entry.msgid)):
                    if hit not in entry.msgstr:
                        broken.append('%s · %s -> %s'
                                      % (module, entry.msgid[:40], hit))
                if entry.msgid.count('%s') != entry.msgstr.count('%s'):
                    broken.append('%s · %s (%%s count)'
                                  % (module, entry.msgid[:40]))
        self.assertFalse(broken[:10],
                         'a translation loses a placeholder: %s' % broken[:10])
