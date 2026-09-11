# -*- coding: utf-8 -*-
"""The profile's arithmetic, with no database in sight.

`vn_profile` is deliberately plain Python so the spreadsheet builder can import
it on a laptop. These tests hold it to that: they exercise the layout maths that
decides where every column of the monthly file lands, which is the thing that
went wrong in the field and the thing a future edit is most likely to break.
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_payroll_mapping_vn.models import vn_profile


@tagged('post_install', '-at_install', 'pb_vn_mapping')
class TestVnProfile(TransactionCase):

    def test_01_every_mapped_code_is_named_once(self):
        """A code cannot be mapped to a record AND carried by the file.

        Two homes for one value is two answers to one question, and the
        resolver would pick whichever ranked higher without anybody having
        decided which was meant.
        """
        overlap = set(vn_profile.FIELD_MAPPING) & vn_profile.sheet_codes()
        self.assertFalse(
            overlap,
            "these columns are both mapped and in the file: %s" % sorted(overlap))

    def test_02_contract_components_are_not_also_mapped(self):
        """A contract component is rank 5; a mapped field is rank 4.

        Declaring both would make the field silently win, and the component the
        operator can see on the contract would stop being the one that pays.
        """
        components = {code for code, _l, _u in vn_profile.CONTRACT_COMPONENTS}
        self.assertFalse(components & set(vn_profile.FIELD_MAPPING))
        self.assertFalse(components & vn_profile.sheet_codes())

    def test_03_layout_reserves_the_right_positions(self):
        """Each reserved column sits at exactly the letter it is named for."""
        layout = vn_profile.sheet_layout()
        for letter, code, label in vn_profile.RESERVED_POSITIONS:
            index = vn_profile._letter_to_index(letter)
            self.assertLess(index, len(layout),
                            "%s is past the end of the sheet" % letter)
            at_index = layout[index]
            self.assertTrue(at_index[2], "%s should be reserved" % letter)
            self.assertEqual(at_index[0], code)
            self.assertEqual(at_index[1], label)

    def test_04_layout_carries_every_real_column_once(self):
        """Nothing is dropped on the floor while making room for the reserved."""
        layout = vn_profile.sheet_layout()
        real = [(code, label) for code, label, reserved in layout
                if not reserved]
        self.assertEqual(real, vn_profile.sheet_columns())

    def test_05_the_employee_code_is_the_first_column(self):
        """The importer keys a row on it, and a person reads it first."""
        layout = vn_profile.sheet_layout()
        self.assertEqual(layout[0][0], vn_profile.SHEET_KEY_COLUMN[0])
        self.assertFalse(layout[0][2])

    def test_06_computed_fields_are_all_mapped(self):
        """The two derived fields are named in the mapping they belong to.

        If one were listed as computed but never mapped, the writeback guard
        would be protecting a field nothing writes to, and the reader of
        `COMPUTED_FIELDS` would be told something untrue.
        """
        mapped = {field for _model, field in vn_profile.FIELD_MAPPING.values()}
        for name in vn_profile.COMPUTED_FIELDS:
            self.assertIn(name, mapped)
