# -*- coding: utf-8 -*-
{
    'name': 'Payobook Vietnam — Record Mapping',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Typed employee/contract fields for the Vietnam pay scheme, plus '
               'the mapping that wires every steady column onto them.',
    'description': """
Vietnam record mapping
======================
The Vietnam starter scheme ("Vietnam · Complete", and every configuration
created from it) asks for about forty-five values a person types. Only seven of
them change from one run to the next — the days worked and the overtime hours.
The rest are facts about the person, their contract, or their bank account, and
re-typing a fact into a spreadsheet every month is how facts go wrong.

This module supplies the missing half of that arrangement:

* **Typed fields** on the employee and the employment contract for every steady
  Vietnam payroll fact — whole numbers for counts, yes/no for the flags, a
  decimal for the hours in a working day. Two of them (months on the contract,
  days of service this year) are DERIVED from dates nobody should restate.
* **Contract components** for the steady amounts — uniform allowance, the
  approved private-insurance allowance, the two private-health premiums — as
  `hr.contract.advantage.template` rows keyed on the scheme's own component
  code, which is how the payroll engine already finds them.
* **`hr.formula.config.pb_apply_vn_mapping()`** — applies the whole profile to
  one configuration: it creates the `hr.payslip.import.mapping` rows, adds the
  bank and employee-code columns if the scheme has none, and corrects the value
  kinds it touches. It is idempotent, it never edits a column the profile does
  not name, and it reports what it did.

Nothing here is specific to one tenant. Any database holding a Vietnam scheme
built from the same starter can run the same profile.
""",
    'author': 'Payobook',
    'website': 'https://payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'pb_hr_payroll_formula',
    ],
    'data': [
        'data/contract_advantage_templates.xml',
        'views/hr_employee_views.xml',
        'views/hr_contract_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
