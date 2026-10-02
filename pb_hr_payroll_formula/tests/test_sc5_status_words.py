# -*- coding: utf-8 -*-
"""SC-5 — a status arriving from outside must land in the box, not vanish.

`hr.contract.hirestatus` offered Long Leave / Resignee / New Hire. Zoho sends
Active / Resigned / Terminated. `_coerce_mapped_value`'s selection branch did
`str(value) in allowed` against the stored VALUES, so every incoming status
coerced to None and all 164 abm contracts sat NULL while the mapping board
showed the wire as healthy — the worst kind of failure, silent on both sides.

Two things changed and both are pinned here: the vendor's three words are now
options on the field, and the coercion matches a label as well as a value,
case- and space-insensitively, so we are not hostage to how a source we do not
control capitalises a word.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSc5StatusWords(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Batch = cls.env['hr.payroll.import.batch']
        cls.contract = cls.env['hr.contract'].new({})

    # A `Field` is a descriptor: bound to a class attribute it hands back the
    # VALUE for whatever object reads it, and a TestCase is not a recordset.
    # Fetch it through a method so it stays an object, not an attribute.
    def _hs(self):
        return self.env['hr.contract']._fields['hirestatus']

    def _coerce(self, value, field=None):
        return self.Batch._coerce_mapped_value(
            self.contract, field or self._hs(), value)

    # 1 — the vendor's vocabulary is on the field at all.
    def test_01_vendor_words_are_options(self):
        values = dict(self._hs().selection)
        for key, label in (('active', 'Active'), ('resigned', 'Resigned'),
                           ('terminated', 'Terminated')):
            self.assertEqual(values.get(key), label,
                             "%s must be an employment status option" % label)

    # 2 — 'new hire' survives: pb_hr_workforce_planning still tests for it.
    def test_02_new_hire_survives(self):
        self.assertIn('new hire', dict(self._hs().selection))

    # 3 — exactly what Zoho sends lands, by label match.
    def test_03_zoho_words_coerce(self):
        self.assertEqual(self._coerce('Active'), 'active')
        self.assertEqual(self._coerce('Resigned'), 'resigned')
        self.assertEqual(self._coerce('Terminated'), 'terminated')

    # 4 — case and stray whitespace do not decide whether a status is kept.
    def test_04_case_and_space_tolerated(self):
        self.assertEqual(self._coerce('  ACTIVE '), 'active')
        self.assertEqual(self._coerce('resigned'), 'resigned')
        self.assertEqual(self._coerce('New Hire'), 'new hire')

    # 5 — a stored value still wins directly, unchanged.
    def test_05_stored_value_still_exact(self):
        self.assertEqual(self._coerce('long leave'), 'long leave')

    # 6 — a word nobody offers is still refused, not guessed at.
    def test_06_unknown_word_refused(self):
        self.assertIsNone(self._coerce('On Sabbatical'))
        self.assertIsNone(self._coerce('   '))

    # 7 — the tolerance is generic, not a hirestatus special case: YES/NO
    #     participation boxes read the same way.
    def test_07_tolerance_is_generic(self):
        shui = self.env['hr.contract']._fields['shuipart']
        self.assertEqual(self._coerce('yes', field=shui), 'YES')

    # 8 — THE ONE THAT WOULD HAVE CAUGHT IT. `_get_mapping_updates` describes
    #     the destination with an `ir.model.fields` row, whose `selection` Char
    #     is empty for a Python-declared field. Handed that, the coercion used
    #     to compute an empty allow-list and refuse everything in silence.
    def test_08_ir_model_fields_row_is_resolved(self):
        row = self.env['ir.model.fields'].search([
            ('model', '=', 'hr.contract'), ('name', '=', 'hirestatus')], limit=1)
        self.assertTrue(row, "hr.contract.hirestatus must be introspectable")
        contract = self.env['hr.contract'].new({})
        self.assertEqual(
            self.Batch._coerce_mapped_value(contract, row, 'Resigned'),
            'resigned',
            "a destination described by its model-fields row must accept the "
            "same words as one described by the Python field")

    # 9 — the same row shape must still reject a word nobody offers, so the
    #     fix widened what lands, not what is guessed at.
    def test_09_row_shape_still_refuses_unknown(self):
        row = self.env['ir.model.fields'].search([
            ('model', '=', 'hr.contract'), ('name', '=', 'hirestatus')], limit=1)
        contract = self.env['hr.contract'].new({})
        self.assertIsNone(
            self.Batch._coerce_mapped_value(contract, row, 'On Sabbatical'))
