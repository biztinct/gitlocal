# -*- coding: utf-8 -*-
{
    'name': 'Payobook Pay',
    'summary': 'Salary bands drawn as a picture, an honest answer to "is our '
               'pay fair?", and a pay review that opens already filled in.',
    # A manifest description is shown to a person in the Apps list, so it is a
    # USER-VISIBLE string and keeps this product's own vocabulary (ledger GR7).
    # The engineering account lives in the module's docstrings.
    'description': """
Pay bands, whether pay is fair, and the pay review itself.

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
  * THE PAY REVIEW, IN ONE SCREEN. It opens with a suggested rise already
    filled in for everybody it covers, read from a guidance grid — how well
    somebody did across, where their pay already sits down. The budget meter
    is already counting, the fairness check has already run, and the rows that
    break a limit are already marked and say why. Adjust in the worksheet or
    by dragging dots in the calibration picture; everything moves together.
  * FOUR SIGNATURES AND ONE WRITE. A review goes manager, HR, finance, chief
    executive, with a real task raised for each of them. Apply shows every
    contract that will change before it changes any of them, writes the new
    pay, prints and files a letter for each person, and can be taken back in
    full for twenty-four hours.
  * PAY CHANGES between reviews — a promotion, a correction, a counter-offer —
    through the same guidance, the same limits, the same approvals and the
    same letter, and refused while a review is open for that person.
  * YOUR PAY, EXPLAINED. Everybody can see what they are paid, where it sits
    in the range for their work, and what last changed it and why. Never
    anything about anybody else.

WHAT IT DOES NOT CHANGE

  A band never moves a wage on its own and no pay run reads one. The only
  thing here that changes what somebody is paid is Apply, and it shows you
  every figure first, records what it wrote, and gives it all back on one
  button for a day afterwards. A payslip that has already been worked out is
  never touched.
""",
    'version': '19.0.3.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'mail',
        'portal',                  # the self-service page "Your pay, explained"
        'om_hr_payroll',           # hr.contract, where the wage lives
        'biz_approval_chain',      # the shared four-tier approval state machine
        'pb_group',                # the group, divisions and the one conversion
        'pb_hub',                  # the global palette + the shared back chip
        'pb_import_kit',           # pbim tokens/primitives + the shared ic() set
        'pb_people_hub',           # the hub this lens is bolted onto
        'pb_explorer',             # what payroll actually paid (pb.fact.emp)
        'pb_lifecycle',            # the letter engine a pay letter is printed by
        'pb_me_portal',            # the portal kit the pay page is built on
    ],
    'data': [
        'security/pb_pay_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/pb_pay_views.xml',
        'views/pb_pay_review_views.xml',
        'views/pb_pay_action.xml',
        'views/pb_pay_statement.xml',
        'views/pb_pay_portal.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_pay/static/src/scss/pay.scss',
            # the screens first, then the rows that name doors to them
            'pb_pay/static/src/js/pay_review.js',
            'pb_pay/static/src/js/pay_hub.js',
            'pb_pay/static/src/js/pay_palette.js',
            'pb_pay/static/src/xml/pay.xml',
            'pb_pay/static/src/xml/pay_review.xml',
        ],
        'web.assets_frontend': [
            'pb_pay/static/src/scss/pay_portal.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
