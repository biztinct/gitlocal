# -*- coding: utf-8 -*-
{
    'name': 'Business Trip → Expense Bridge',
    'summary': 'Turns approved trip expense lines into draft hr.expense records',
    'description': """
Glue module linking business trips to Accounting/Expenses. On final authorization
it creates one DRAFT hr.expense per receipted trip line (and, when the policy
channel is 'expense', one per-diem expense) — posting/paying stays in stock
expense/accounting. This is why pb_business_trip installs WITHOUT hr_expense
(C18.1): the expense_id field, the product mapping and the expense-creation hook
all live here.

Channel exclusivity (safety rail 1): a per-diem expense is created ONLY when the
policy channel is 'expense' — otherwise the per-diem is paid through payroll
(pb_trip_payroll_bridge), never both. Cancelling an authorized trip unlinks its
DRAFT expenses; a posted expense blocks the cancel with a clear error.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['pb_business_trip', 'hr_expense'],
    'data': [
        'data/product_data.xml',
        'views/pb_trip_expense_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
