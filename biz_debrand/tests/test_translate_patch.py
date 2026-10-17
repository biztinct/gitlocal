# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""ERRORS E2-2 — a translated string that names the vendor where the English does not.

``get_translation`` used to pre-filter on the English msgid, so a catalogue
entry whose *translation* carries the vendor name never reached the rewrite.
Two live cases, both in ``calendar``'s Vietnamese catalogue, both settings prose
a customer reads:

    Synchronize your calendar with Google Calendar
        -> Đồng bộ lịch của bạn trên Odoo với Lịch Google

The fix asks the question of the translation instead. These tests pin the new
behaviour AND the two things it must not cost: the en_US fast path, and the
no-op contract every other seam relies on.
"""
import odoo.tools.translate as tr_mod

from odoo.tests import TransactionCase, tagged

from ..models.brand import cache_brand, current_brand

#: The live pair from calendar/i18n/vi_VN.po.
VI_SOURCE = 'Synchronize your calendar with Google Calendar'
VI_TRANSLATION = 'Đồng bộ lịch của bạn trên Odoo với Lịch Google'


@tagged('post_install', '-at_install')
class TestTranslationPreFilter(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cache_brand(cls.env)
        pair = current_brand()
        cls.brand = pair[0] if pair else None

    def _with_catalogue(self, module, lang, entries):
        """Stand a fake code-translation catalogue in front of the real one."""
        original = tr_mod.code_translations.get_python_translations

        def get_python_translations(mod, language):
            if mod == module and language == lang:
                return entries
            return original(mod, language)

        self.patch(tr_mod.code_translations, 'get_python_translations',
                   get_python_translations)

    # ------------------------------------------------------------------
    # 1. The live case: the English is clean, the Vietnamese is not.
    # ------------------------------------------------------------------
    def test_01_translation_naming_the_vendor_is_rewritten(self):
        self.assertTrue(self.brand, 'No brand is resolved on this database.')
        self._with_catalogue('calendar', 'vi_VN', {VI_SOURCE: VI_TRANSLATION})
        out = str(tr_mod.get_translation('calendar', 'vi_VN', VI_SOURCE, ()))
        self.assertNotIn('odoo', out.lower(),
                         'The Vietnamese string still names the vendor: %r' % out)
        self.assertIn(self.brand, out,
                      'The Vietnamese string lost the vendor name but did not '
                      'gain the brand: %r' % out)
        # Only the vendor word moved — the sentence is otherwise intact.
        self.assertIn('Đồng bộ lịch của bạn', out)
        self.assertIn('Lịch Google', out)

    # ------------------------------------------------------------------
    # 2. Clean in both languages: returned untouched, and the catalogue
    #    entry still wins (we must not hand back the msgid by mistake).
    # ------------------------------------------------------------------
    def test_02_clean_translation_is_untouched(self):
        self._with_catalogue('calendar', 'vi_VN', {'Save': 'Lưu'})
        self.assertEqual(str(tr_mod.get_translation('calendar', 'vi_VN', 'Save', ())),
                         'Lưu')

    # ------------------------------------------------------------------
    # 3. The en_US branch is unchanged: still filtered on the source, still
    #    rewritten when the source itself names the vendor.
    # ------------------------------------------------------------------
    def test_03_en_us_branch_unchanged(self):
        asked = []
        original = tr_mod.code_translations.get_python_translations

        def spy(mod, language):
            asked.append((mod, language))
            return original(mod, language)

        self.patch(tr_mod.code_translations, 'get_python_translations', spy)

        clean = str(tr_mod.get_translation('base', 'en_US', 'Nothing to see here', ()))
        self.assertEqual(clean, 'Nothing to see here')
        self.assertEqual(asked, [],
                         'en_US now pays for a catalogue lookup it does not need.')

        branded = str(tr_mod.get_translation('base', 'en_US', 'Install Odoo', ()))
        self.assertEqual(branded, 'Install %s' % self.brand)

    # ------------------------------------------------------------------
    # 4. The no-op contract: a clean string comes back as the SAME object,
    #    so callers can still detect "nothing changed" by identity.
    # ------------------------------------------------------------------
    def test_04_no_op_returns_the_untouched_source(self):
        self._with_catalogue('base', 'vi_VN', {})
        source = 'A sentence with nothing to rewrite'
        self.assertEqual(str(tr_mod.get_translation('base', 'vi_VN', source, ())),
                         source)

    # ------------------------------------------------------------------
    # 5. A broken catalogue must never take a page down. The patch fails
    #    open: it logs and returns what the platform would have returned.
    # ------------------------------------------------------------------
    def test_05_a_broken_catalogue_fails_open(self):
        # Only OUR lookup blows up; the platform's own (which runs next, inside
        # the fallback) must still be reached and must still answer.
        calls = []

        def boom_once(mod, language):
            calls.append(mod)
            if len(calls) == 1:
                raise RuntimeError('catalogue on fire')
            return {'Save': 'Lưu'}

        self.patch(tr_mod.code_translations, 'get_python_translations', boom_once)
        with self.assertLogs('odoo.addons.biz_debrand.models.translate_patch',
                             level='WARNING'):
            out = str(tr_mod.get_translation('base', 'vi_VN', 'Save', ()))
        self.assertEqual(out, 'Lưu',
                         'A failure in the debrand patch changed what the user '
                         'reads instead of stepping out of the way.')
