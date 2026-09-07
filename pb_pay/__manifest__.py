# -*- coding: utf-8 -*-
{
    'name': 'Payobook Pay Bands and Fairness',
    'summary': 'Salary bands drawn as a picture with every person on them, and '
               'an honest answer to "is our pay fair?"',
    # A manifest description is shown to a person in the Apps list, so it is a
    # USER-VISIBLE string and keeps this product's own vocabulary (ledger GR7).
    # The engineering account lives in the module's docstrings.
    'description': """
Pay bands, and whether pay is fair.

WHAT THIS MODULE ADDS

  * PAY BANDS. A salary range per job family, per level, per country and
    currency, with a from-date so a band that moves does not rewrite last
    year. Every band is drawn as a range with every person in it as a dot.
    Drag an edge and the people who fall outside light up, with what it would
    cost to bring them back in. Nothing is saved until you let go.
  * A BAND AND A POSITION ON EVERY CONTRACT, kept current. "62% of the way
    through the band" in plain words, on the contract screen, with no figure
    anybody has to maintain by hand.
  * HEALTH CARDS you never have to go looking for: paid below the band, paid
    above it, newer people paid more than long-serving people in the same job,
    a manager paid less than somebody who reports to them, and how wide each
    band has become in practice.
  * PLACE A NEW HIRE. Pick the job and the level, say how experienced the
    person is, and see the band, the people already in it, the middle of the
    market you pay, and a suggested offer.
  * FAIRNESS, computed from what payroll actually paid rather than from a
    survey: the pay gap by gender, by level and by division, how far apart two
    people in the same job are, and who is paid least for the same work. Every
    number carries the people it was measured on and the method in one
    sentence, and refuses to answer when there are too few people to be fair.
  * A ONE-PAGE STATEMENT to print for a board or a regulator.

WHAT IT DOES NOT CHANGE

  Nothing here writes to anybody's pay. A band is a range this company means
  to pay inside; it never moves a wage on its own, and no pay run reads it.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'mail',
        'om_hr_payroll',           # hr.contract, where the wage lives
        'pb_group',                # the group, divisions and the one conversion
        'pb_hub',                  # the global palette + the shared back chip
        'pb_import_kit',           # pbim tokens/primitives + the shared ic() set
        'pb_people_hub',           # the hub this lens is bolted onto
        'pb_explorer',             # what payroll actually paid (pb.fact.emp)
    ],
    'data': [
        'security/pb_pay_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/pb_pay_views.xml',
        'views/pb_pay_action.xml',
        'views/pb_pay_statement.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_pay/static/src/scss/pay.scss',
            # the screen first, then the rows that name doors to it
            'pb_pay/static/src/js/pay_hub.js',
            'pb_pay/static/src/js/pay_palette.js',
            'pb_pay/static/src/xml/pay.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
