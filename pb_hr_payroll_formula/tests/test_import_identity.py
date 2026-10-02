# -*- coding: utf-8 -*-
"""Run the same import twice and get the same people, not twice the people.

The June 2026 ABM run surfaced a family of identity defects, every one of which
either duplicated a person or — worse — merged two:

  * matching fell through to `name =ilike`, so **three different employees**
    (Zoho codes 0258, 11368 and 0016, three different email addresses) became
    one record because all three are called NGA NGUYEN, and were paid as one;
  * the identity fields a match relies on (`employee_id`, `barcode`,
    `identification_id`) are all mappable, and ABM's scheme points every one of
    them at the ID CARD number — so two people sharing a card number collided,
    and the feed's own stable key was overwritten on the first update;
  * `barcode` carries a UNIQUE constraint, so that same mapping raised
    `UniqueViolation` mid-run, which aborts the PostgreSQL transaction and
    failed every remaining line with "current transaction is aborted";
  * contracts were dated from the payroll PERIOD rather than the employee's
    joining date, and a contract that does not cover its own period is not
    found next month — so the next run would add another.

`pb_source_ref` is the answer to all four: one identifier, per connection, that
no mapping can point at and no update can overwrite.
"""
from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestImportIdentity(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.connector = self.env['hr.integration.connector'].create({
            'name': 'Identity probe', 'connector_type': 'zoho',
        })
        self.config = self.env['hr.formula.config'].create({
            'name': 'Identity probe scheme', 'country_code': 'VN',
        })
        self.batch = self.env['hr.payroll.import.batch'].create({
            'name': 'Identity probe batch',
            'source_type': 'api_data_store',
            'connector_id': self.connector.id,
            'formula_config_id': self.config.id,
            'date_from': '2026-06-01', 'date_to': '2026-06-30',
            'company_id': self.company.id,
        })

    def _line(self, code, name, email=False):
        return self.env['hr.payroll.import.line'].create({
            'batch_id': self.batch.id,
            'employee_code': code, 'employee_name': name,
            'employee_email': email, 'state': 'validated',
        })

    # ------------------------------------------------ the key, and the round trip
    def test_a_created_employee_carries_the_source_key(self):
        employee = self.batch._create_employee(self._line('11708', 'Thuy Bui'))
        self.assertEqual(employee.pb_source_ref,
                         '%s:11708' % self.connector.id)

    def test_the_same_row_finds_the_same_person_next_run(self):
        """The whole point: June creates, July matches."""
        created = self.batch._create_employee(self._line('11708', 'Thuy Bui'))
        found = self.batch._find_employee(self._line('11708', 'Thuy Bui'))
        self.assertEqual(found, created)

    def test_the_key_is_scoped_to_its_connection(self):
        """`0442` in one system is not the same key as `0442` in another.

        Scoping is about the KEY, not about forbidding a match: the weaker
        code rung below may still recognise a shared employee code across two
        systems, and that is a reasonable thing for it to do. What must never
        happen is one system's `0442` silently satisfying the other's identity
        check — so the references differ, and `_match_ok` only ever vetoes a
        contradiction from the SAME connection.
        """
        other = self.env['hr.integration.connector'].create({
            'name': 'Another system', 'connector_type': 'darwin',
        })
        employee = self.batch._create_employee(self._line('0442', 'Hai Nguyen'))
        mine = self.batch._source_ref('0442')
        self.batch.connector_id = other.id
        theirs = self.batch._source_ref('0442')
        self.assertNotEqual(mine, theirs)
        self.assertEqual(employee.pb_source_ref, mine)
        # A different connection's claim is not a contradiction of this one.
        self.assertTrue(self.batch._match_ok(employee, theirs))

    # ------------------------------------------- two people are not one person
    def test_two_people_with_one_name_stay_two_people(self):
        """NGA NGUYEN, three times, three codes. Three employees.

        The name rung used to return the first match on name alone.
        """
        first = self.batch._create_employee(
            self._line('0258', 'NGA NGUYEN', 'nga.t.nguyen@abmauri.vn'))
        second = self.batch._find_employee(
            self._line('11368', 'NGA NGUYEN', 'nga.h.nguyen@abmauri.vn'))
        self.assertFalse(
            second, "a shared name matched a different person's record")
        made = self.batch._create_employee(
            self._line('11368', 'NGA NGUYEN', 'nga.h.nguyen@abmauri.vn'))
        self.assertNotEqual(made, first)
        self.assertNotEqual(made.pb_source_ref, first.pb_source_ref)

    def test_a_name_still_attaches_a_code_to_a_record_that_has_none(self):
        """The rung keeps the case it was written for.

        An employee already in the system with no code at all, meeting a source
        that has one: matching by name is how the code gets attached.
        """
        legacy = self.env['hr.employee'].create({
            'name': 'Legacy Person', 'company_id': self.company.id})
        self.assertEqual(
            self.batch._find_employee(self._line('0999', 'Legacy Person')),
            legacy)

    def test_a_shared_mappable_code_cannot_merge_two_people(self):
        """The ID card number is not an identity.

        Both rows carry the same card number in a mappable field; the source
        says they are different people, and the source wins.
        """
        first = self.batch._create_employee(self._line('0442', 'HAI NGUYEN'))
        first.barcode = '075186015978'
        second_line = self._line('0729', 'CHUC NGUYEN')
        self.assertFalse(
            self.batch._match_ok(first, self.batch._source_ref('0729')),
            "a record this connection knows as someone else was accepted")
        self.assertFalse(self.batch._find_employee(second_line))

    def test_a_record_with_no_source_key_is_still_matchable(self):
        """Employees created before this existed must not become unreachable."""
        legacy = self.env['hr.employee'].create({
            'name': 'No Key', 'barcode': 'LEGACY1',
            'company_id': self.company.id})
        self.assertTrue(self.batch._match_ok(legacy, self.batch._source_ref('0001')))

    # -------------------------------------------------- the unique-barcode trap
    def test_a_contested_barcode_is_dropped_not_raised(self):
        """`hr_employee_barcode_uniq` aborts the whole transaction.

        One duplicated card number used to fail every line after it with
        "current transaction is aborted" — a total loss from one bad cell.
        """
        self.env['hr.employee'].create({
            'name': 'Holder', 'barcode': '066196005153',
            'company_id': self.company.id})
        vals = {'name': 'Someone else', 'barcode': '066196005153'}
        self.batch._drop_taken_barcode(vals)
        self.assertNotIn('barcode', vals)
        # A free barcode is left exactly where it is.
        free = {'name': 'Third', 'barcode': 'NOBODY-HAS-THIS'}
        self.batch._drop_taken_barcode(free)
        self.assertEqual(free['barcode'], 'NOBODY-HAS-THIS')

    # ------------------------------------------------------- contracts, once
    def test_a_contract_starts_when_the_person_did(self):
        """Not when payroll happened to run.

        `self.date_from or joining_date` could never reach the joining date, so
        every employee created by a June import got a contract starting 1 June
        — including someone who joined in 1998.
        """
        line = self._line('11708', 'Thuy Bui')
        line.raw_data_json = '{"date_of_joining": "1998-11-23"}'
        employee = self.batch._create_employee(self._line('11708', 'Thuy Bui'))
        contract = self.batch._create_contract(employee, line)
        self.assertEqual(contract.date_start, date(1998, 11, 23))

    def test_a_second_run_reuses_the_contract_it_already_made(self):
        employee = self.batch._create_employee(self._line('11708', 'Thuy Bui'))
        line = self._line('11708', 'Thuy Bui')
        first = self.batch._create_contract(employee, line)
        july = self.batch.copy({'date_from': '2026-07-01', 'date_to': '2026-07-31'})
        self.assertEqual(july._get_latest_contract(employee), first)

    def test_a_contract_that_covers_no_period_is_still_reused(self):
        """Never mint a second contract just because none overlaps.

        Doing that once a month is how one employee ends up with twelve.
        """
        employee = self.batch._create_employee(self._line('11708', 'Thuy Bui'))
        self.env['hr.contract'].create({
            'name': 'Old', 'employee_id': employee.id,
            'wage': 1000, 'state': 'close',
            'date_start': '2020-01-01', 'date_end': '2020-12-31',
            'company_id': self.company.id,
        })
        self.assertTrue(self.batch._get_latest_contract(employee))
