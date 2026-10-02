# Copyright 2025
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""The Odoo-19 employee sources behind the five VN filings.

Odoo 19 deleted `hr.employee.address_home_id` and `hr.employee.bank_account_id`
and renamed `gender` to `sex`. Four of the five VN filings read one of those on
every employee row, so they raised AttributeError — and because the filing flow
catches broadly (pb_govt_reports/models/pb_filing_flow.py:437), the user saw
"This filing could not be generated: …" rather than a traceback. That is why the
breakage survived: nothing crashed loudly and no test named the fields.

So this file has two jobs, and the second matters more than the first:

* a STATIC gate that fails on any read of a field Odoo 19 does not have, over
  the whole module. A resolver that is correct today does not stop the next
  author writing `emp.gender` in the sixth filing.
* a LIVE-SOURCE gate: on a database that carries the Vietnam pack, the VN
  branch must be the branch taken. A fallback chain whose first leg is never
  exercised is indistinguishable from a fallback chain whose first leg is dead
  (W79), and the difference is a form full of blanks nobody notices.
"""

import os
import re

from odoo.tests import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Fields Odoo 19 removed or renamed on hr.employee. The pattern matches an
# attribute read, so the ledger prose above and the comments in report_base.py
# that EXPLAIN the removal are not hits (W48's corollary: a word-shaped gate
# fails on its own documentation).
# `<local>.<field>` where <local> is a bare name, never the tail of a dotted
# path. See the comment at the call site for why that distinction is the gate.
_ATTR_READ = r'(?<![\w.])[A-Za-z_]\w*\.%s\b'

GONE = {
    'address_home_id': 'private_* address fields / pb.govt.report.base._home_address',
    'bank_account_id': 'primary_bank_account_id / pb.govt.report.base._bank_details',
    'gender': 'sex / pb.govt.report.base._is_female',
}


def _sources():
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in ('tests', '__pycache__', 'i18n')]
        for name in files:
            if name.endswith('.py'):
                yield os.path.join(root, name)


@tagged('post_install', '-at_install')
class TestOdoo19EmployeeSources(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base = cls.env['pb.govt.report.base']
        cls.has_vn_pack = 'vietnam_province' in cls.env['hr.employee']._fields

    # ------------------------------------------------------------- static

    def test_01_no_report_reads_a_field_odoo_19_removed(self):
        bad = []
        for path in _sources():
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    stripped = line.strip()
                    if stripped.startswith('#'):
                        continue
                    for field, replacement in GONE.items():
                        # An attribute read off a plain LOCAL name — `emp.sex`,
                        # `x.bank_account_id`. Two things must not match, and
                        # both bit on the first run of this gate:
                        #   * a dotted model path in prose, `hr.employee.gender`,
                        #     which is how the docstring in report_base.py
                        #     EXPLAINS the removal. A word-shaped gate that
                        #     fails on its own documentation is a gate the next
                        #     reader deletes (W48's corollary);
                        #   * a string key, "bank_account_id", which is Odoo's
                        #     own m2m relation column name.
                        # The negative lookbehind on the receiver does both: in
                        # `hr.employee.gender` the receiver `employee` is
                        # preceded by a dot, so it is not a local name.
                        if re.search(_ATTR_READ % field, line):
                            bad.append('%s:%s: %s   → use %s'
                                       % (os.path.relpath(path, HERE), n,
                                          stripped, replacement))
        self.assertFalse(bad, 'Odoo-19 field drift:\n%s' % '\n'.join(bad))

    def test_02_the_resolvers_are_the_only_door(self):
        """Every filing goes through pb.govt.report.base for these three, so a
        semantic change lands in one place instead of five."""
        report_dir = os.path.join(HERE, 'report')
        seen = set()
        for name in sorted(os.listdir(report_dir)):
            if not name.endswith('_report.py'):
                continue
            with open(os.path.join(report_dir, name), encoding='utf-8') as fh:
                body = fh.read()
            for helper in ('_home_address', '_location_codes', '_bank_details',
                           '_is_female'):
                if 'base.%s(' % helper in body:
                    seen.add(helper)
        self.assertEqual(
            seen, {'_home_address', '_location_codes', '_bank_details', '_is_female'},
            'a resolver is no longer used by any filing: %s' % sorted(seen))

    # ------------------------------------------------------------- semantics

    def test_03_is_female_reads_sex_not_gender(self):
        emp = self.env['hr.employee'].create({'name': 'VN drift F', 'sex': 'female'})
        other = self.env['hr.employee'].create({'name': 'VN drift M', 'sex': 'male'})
        self.assertTrue(self.base._is_female(emp))
        self.assertFalse(self.base._is_female(other))

    def test_04_home_address_prefers_the_vn_permanent_address(self):
        """The VN branch must be the branch taken where the pack is installed."""
        if not self.has_vn_pack:
            self.skipTest('pb_hr_payroll_vietnam is not installed on this database')
        emp = self.env['hr.employee'].create({
            'name': 'VN drift addr',
            'vietnam_permanent_address': '12 Nguyễn Huệ\n  Quận 1',
            'vietnam_temporary_address': 'somewhere else',
            'private_street': 'Core Street',
            'private_city': 'Core City',
        })
        self.assertEqual(self.base._home_address(emp), '12 Nguyễn Huệ Quận 1')

    def test_05_home_address_falls_back_to_the_core_private_fields(self):
        emp = self.env['hr.employee'].create({
            'name': 'VN drift addr core',
            'private_street': '5 Core Street',
            'private_city': 'Core City',
            'private_zip': '700000',
        })
        if self.has_vn_pack:
            emp.write({'vietnam_permanent_address': False,
                       'vietnam_temporary_address': False})
        self.assertEqual(self.base._home_address(emp),
                         '5 Core Street, Core City, 700000')

    def test_06_home_address_never_uses_the_work_contact(self):
        """The office address is a WRONG answer, not a partial one."""
        partner = self.env['res.partner'].create({
            'name': 'HQ', 'street': 'Office Tower', 'city': 'Office City'})
        emp = self.env['hr.employee'].create({
            'name': 'VN drift work contact', 'work_contact_id': partner.id})
        self.assertNotIn('Office', self.base._home_address(emp))

    def test_07_location_codes_take_the_three_vn_administrative_levels(self):
        if not self.has_vn_pack:
            self.skipTest('pb_hr_payroll_vietnam is not installed on this database')
        emp = self.env['hr.employee'].create({
            'name': 'VN drift codes',
            'vietnam_province': '01',
            'vietnam_district': '002',
            'vietnam_ward': '00037',
        })
        self.assertEqual(self.base._location_codes(emp), ('01', '002', '00037'))

    def test_08_location_codes_resolve_a_name_through_the_lookup_table(self):
        lookup = self.env['pb.govt.code.lookup'].create({
            'name': 'W-C6 Test Province', 'code': '99', 'lookup_type': 'province'})
        self.assertEqual(self.base._code_for('province', 'w-c6 test province'),
                         lookup.code)
        self.assertEqual(self.base._code_for('province', ''), '000')
        self.assertEqual(self.base._code_for('province', 'no such place'), '000')

    def test_09_location_codes_never_raise_on_a_bare_employee(self):
        """Every filing calls this for every row: an employee with nothing
        filled in files zeros, it does not abort the run for the other 900."""
        emp = self.env['hr.employee'].create({'name': 'VN drift empty'})
        self.assertEqual(self.base._location_codes(emp), ('000', '000', '000'))
        self.assertEqual(self.base._home_address(emp), '')
        self.assertEqual(self.base._bank_details(emp), ('', '', ''))

    def test_10_bank_details_read_the_columns_pay_and_deliver_pays_from(self):
        if not self.has_vn_pack:
            self.skipTest('pb_hr_payroll_vietnam is not installed on this database')
        emp = self.env['hr.employee'].create({
            'name': 'VN drift bank',
            'vietnam_bank_account_number': '1903 6688 8888',
            'vietnam_bank_account_name': 'NGUYEN VAN A',
            'vietnam_bank_name': 'Techcombank',
        })
        number, holder, code = self.base._bank_details(emp)
        self.assertEqual(number, '1903 6688 8888')
        self.assertEqual(holder, 'NGUYEN VAN A')
        self.assertTrue(code, 'the bank name resolved to no code at all')

    def test_11_the_bank_resolution_is_the_same_source_as_pay_and_deliver(self):
        """Not "similar" — the same three columns, asserted against that
        module's own source. Two resolutions that drift put a different account
        on the filing from the one the money went to."""
        try:
            import odoo.addons.pb_pay_delivery as delivery  # noqa: F401
        except ImportError:
            self.skipTest('pb_pay_delivery is not on the addons path')
        path = os.path.join(os.path.dirname(delivery.__file__),
                            'models', 'bank_export_wizard.py')
        with open(path, encoding='utf-8') as fh:
            body = fh.read()
        for field in ('vietnam_bank_account_number', 'vietnam_bank_account_name',
                      'vietnam_bank_name'):
            self.assertIn(
                'emp.%s' % field, body,
                'pb_pay_delivery no longer resolves %s — the filing and the '
                'payment have drifted apart' % field)
