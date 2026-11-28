# -*- coding: utf-8 -*-
{
    'name': 'Payobook Build Pay From a Total',
    'summary': 'Type a yearly or monthly total package and see every pay item '
               'filled so the total comes out right, before anything is saved.',
    # Shown in the Apps list: product words only (ledger GR7).
    'description': """
Build a contract's pay from a total package ("cost to company"): type the
total for a year or a month, say how much of it is basic pay and which pay
item takes the rest. The person's own pay scheme works out everything that
follows from basic pay, and the item that takes the rest is set so that gross
pay plus the employer's contributions equals the total.

Nothing is saved by this screen. "Use these figures" puts them into the open
contract; the contract's own Save sends them for approval like any other pay
change. Works for any pay scheme that has a basic pay item and an item that
can take the rest, and says plainly when a scheme cannot.

The same box is on a Hiring offer: the split becomes the offer's monthly pay
lines, so the offer letter shows basic pay and allowances, and the contract
starts with them when the person joins.
""",
    'version': '19.0.1.2.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_formula_studio',   # the W2-C engine and search, reused as-is
        'pb_pay_builder',
        'pb_contracts',        # the contract drawer that opens the card
        'pb_hiring',           # WDGAP S8-D: the offer panel opens it too
    ],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'pb_pay_package/static/src/scss/build_total.scss',
            'pb_pay_package/static/src/js/build_total.js',
            'pb_pay_package/static/src/js/offer_total.js',
            'pb_pay_package/static/src/js/offer_builder.js',
            'pb_pay_package/static/src/xml/build_total.xml',
            'pb_pay_package/static/src/xml/offer_total.xml',
            'pb_pay_package/static/src/xml/offer_builder.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
