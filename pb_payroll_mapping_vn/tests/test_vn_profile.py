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

    def test_02b_the_file_carries_no_money(self):
        """The owner's ruling, as an assertion.

        The monthly file is the timesheet: days and hours. Every amount is a
        contract component. This is the one rule most likely to be relaxed by a
        well-meaning "just this one column", so it is stated where a change
        trips it immediately.
        """
        self.assertEqual(vn_profile.SHEET_MONEY_COLUMNS, [])
        amounts = {code for code, _l, _u in vn_profile.CONTRACT_COMPONENTS}
        self.assertFalse(amounts & vn_profile.sheet_codes())
        # And what IS in the file is time, plus the key the rows are about.
        self.assertEqual(
            vn_profile.sheet_codes(),
            {c for c, _l in vn_profile.SHEET_TIME_COLUMNS}
            | {vn_profile.SHEET_KEY_COLUMN[0]})

    def test_02c_a_short_file_does_not_drag_in_far_reservations(self):
        """Reservations past the end of the file protect nothing.

        Honouring them anyway padded an eight-column sheet out to twenty-five,
        seventeen of them blank. Which ones are in range depends on the width,
        and the width depends on which are in range, so it is settled by
        iteration — and this is the assertion that the iteration settles.
        """
        layout = vn_profile.sheet_layout()
        reserved = [i for i, (_c, _l, r) in enumerate(layout) if r]
        self.assertTrue(all(i < len(layout) for i in reserved))
        # Nothing trailing: the last column is a real one.
        self.assertFalse(layout[-1][2])

    def test_03_layout_reserves_the_right_positions(self):
        """Each reserved column sits at exactly the letter it is named for."""
        layout = vn_profile.sheet_layout()
        for letter, code, label in vn_profile.RESERVED_POSITIONS:
            index = vn_profile._letter_to_index(letter)
            if index >= len(layout):
                continue            # out of range, and so not this file's problem
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
