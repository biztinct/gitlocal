# -*- coding: utf-8 -*-
"""RD51 — every employee was given one person's salary.

Found by a probe written to prove a PERFORMANCE change was safe. It compared
the whole-form salary read against the per-employee one on the live reference
tenant and reported 0 of 12 agreeing — because the per-employee path had been
wrong all along, not because the new one was.

WHAT WAS WRONG. `_get_employee_salary` searched
`searchField='Employee_ID.Zoho_ID'`. That field does not exist on the salary
form; the real ones are `Employee_ID` (the employee number) and `Employee_ID.ID`
(the record id). **Zoho does not reject an unknown search field — it ignores it**
and returns the first page of the whole form. `rows[0]` was therefore the same
row for every employee.

THE BILL, measured: 2,584 stored salary rows on the reference tenant carried
exactly ONE distinct Base Salary, ₫12,500,000, for 304 people. All 152 open
contracts held it. All 36 payslips of the June run were computed from it. Zoho
itself holds 60 different values, ₫10,033,520 to ₫117,978,000.

WHY THE FALLBACK IS GONE RATHER THAN FIXED. A search that silently ignores its
filter cannot be trusted as a second chance: it would reinstate the defect for
exactly the employees the bulk read could not place, which is the worst possible
subset to be wrong about. Nothing is returned instead, and the resolver already
treats "this source said nothing" as a reason to try the next rung.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRd51SalaryIdentity(TransactionCase):

    def _zoho(self):
        """A Zoho connector instance with no network behind it."""
        conn = self.env['hr.integration.connector'].create({
            'name': 'RD51 Zoho', 'connector_type': 'zoho'})
        from odoo.addons.pb_hr_payroll_formula.integrations import zoho_connector
        return zoho_connector.ZohoConnector(conn)

    ROWS = [
        {'Employee_ID': '11708', 'Employee_ID.ID': '81100001',
         'Base_Salary': '12500000'},
        {'Employee_ID': '11709', 'Employee_ID.ID': '81100002',
         'Base_Salary': '72000000'},
        {'Employee_ID': '11710', 'Employee_ID.ID': '81100003',
         'Base_Salary': '117978000'},
        # a second, later revision for the FIRST employee
        {'Employee_ID': '11708', 'Employee_ID.ID': '81100001',
         'Base_Salary': '99000000'},
    ]

    def test_01_each_employee_gets_their_own_row(self):
        z = self._zoho()
        z._paged_form_rows = lambda *a, **k: list(self.ROWS)

        self.assertEqual(z._get_employee_salary('11709')['Base_Salary'],
                         '72000000')
        self.assertEqual(z._get_employee_salary('11710')['Base_Salary'],
                         '117978000')
        self.assertNotEqual(z._get_employee_salary('11709')['Base_Salary'],
                            z._get_employee_salary('11710')['Base_Salary'],
                            "two people with different salaries must not be "
                            "given the same one — the whole defect in a line")

    def test_02_either_spelling_of_the_employee_key_finds_the_row(self):
        """Callers hold the number or the record id, depending on the feed."""
        z = self._zoho()
        z._paged_form_rows = lambda *a, **k: list(self.ROWS)
        self.assertEqual(z._get_employee_salary('11709')['Base_Salary'],
                         z._get_employee_salary('81100002')['Base_Salary'])

    def test_03_the_first_row_per_employee_wins_as_it_always_did(self):
        """An employee with salary history must not silently change revision."""
        z = self._zoho()
        z._paged_form_rows = lambda *a, **k: list(self.ROWS)
        self.assertEqual(z._get_employee_salary('11708')['Base_Salary'],
                         '12500000')

    def test_04_an_employee_with_no_row_gets_NOTHING_not_somebody_else_s(self):
        z = self._zoho()
        z._paged_form_rows = lambda *a, **k: list(self.ROWS)
        self.assertEqual(z._get_employee_salary('99999'), {},
                         "returning the first row of the form is what gave 152 "
                         "people the same pay")

    def test_05_the_form_is_read_ONCE_however_many_employees_are_asked_about(self):
        z = self._zoho()
        calls = []

        def once(*a, **k):
            calls.append(1)
            return list(self.ROWS)

        z._paged_form_rows = once
        for ext in ('11708', '11709', '11710', '99999'):
            z._get_employee_salary(ext)
        self.assertEqual(len(calls), 1,
                         "one whole-form read per pull, not one per employee")

    def test_06_a_failed_read_is_not_cached_as_an_answer(self):
        """`None` means 'not read yet'; `{}` means 'read, and it said nothing'."""
        z = self._zoho()

        def boom(*a, **k):
            raise RuntimeError('Zoho said no')

        z._paged_form_rows = boom
        self.assertEqual(z._get_employee_salary('11708'), {})
        # …and a later successful read is still allowed to populate the index
        z._salary_cache = None
        z._paged_form_rows = lambda *a, **k: list(self.ROWS)
        self.assertEqual(z._get_employee_salary('11709')['Base_Salary'],
                         '72000000')

    def test_07_the_dead_search_field_is_gone_from_the_source(self):
        """It must not come back as a 'safety net'. It was never one."""
        import inspect
        from odoo.addons.pb_hr_payroll_formula.integrations import zoho_connector
        src = inspect.getsource(zoho_connector.ZohoConnector._get_employee_salary)
        self.assertNotIn("'searchField': 'Employee_ID.Zoho_ID'", src)
