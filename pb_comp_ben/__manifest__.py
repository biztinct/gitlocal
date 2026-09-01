# -*- coding: utf-8 -*-
{
    'name': 'Payobook Pay Packages & Awards',
    'summary': 'What somebody is paid, written down — plus awards, the payroll '
               'calendar, benefits, and the pack finance is handed on approval',
    'description': """
RIZE phase P7 — the four money gaps, and none of them touch the payroll engine.

WHAT THIS MODULE IS

  * **A pay package that exists.** There is no CTC model anywhere in this
    product: a contract carries a wage, a payslip carries one month, and
    neither answers "what is my package". `pb.employee.comp` is a dated,
    versioned list of lines, bootstrapped from the contract and editable after
    — a statement the company makes, not a view over a table.
  * **Awards with a paper trail.** `pb.incentive` runs on the generic approval
    chain, prints the letter P0's engine already has a template for, and feeds
    the money into the next pay run through the EXISTING "this run only" lane.
    Four things happen to an award — asked, agreed, told, paid — and the model
    keeps agreement and payment in separate columns, because an approved award
    that has not been paid is the most useful row on the board.
  * **A payroll calendar that reminds people.** When changes stop being
    accepted and when people are paid, for twelve months, with an idempotent
    nightly reminder. It ships switched OFF and says so on screen, with the
    number the job would have sent.
  * **Benefits, and the employee's own page.** `/my/compensation` — the
    package, what they are covered by with a real link to the provider, and the
    awards they have actually been paid, with the letter to download.
  * **The finance pack.** On Finance approval (`action_payslip_run_level2_done`
    — NOT `done_payslip_run`, which is the draft→officer entry), the bank file
    and a one-page run summary are attached to the run and emailed. It runs
    after `super()`, inside its own try/except: a pack that fails must never
    stop a run somebody approved.

THE PAYROLL ENGINE AND ITS THREE-TIER APPROVAL ARE UNTOUCHED. No GL change, no
new tier, no edit to any formula scheme — the award feed REFUSES rather than
adding a pay item to somebody's scheme automatically.

ITS OWN GROUP LADDER. What a person is paid is the most closely held fact in an
HR system, so access is granted by name and not inherited from the lifecycle or
people tiers. Employee attributes are read as the system throughout (R56):
reading one field of an `hr.employee` prefetches forty, and forty of those sit
behind payroll groups a pay-package reader need not hold.

pbim tokens only, Lucide icons through the shared `ic()` registry, flat fills,
one accent.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'mail',
        'portal',                   # /my/compensation
        'om_hr_payroll',            # hr.payslip.run, hr.contract.advantage
        'biz_approval_chain',       # the award's approval ladder
        'pb_hub',                   # the global command palette registry
        'pb_import_kit',            # pbim tokens/primitives + the shared ic() set
        'pb_lifecycle',             # the letter engine and its incentive template
        'pb_employee_vault',        # where a finished letter is filed
        'pb_me_portal',             # the .pbme portal kit this page reuses
        'pb_payhub',                # the two lenses, through its soft registry
        'pb_payruns',               # the run chain the finance pack hooks
        'pb_pay_delivery',          # the bank-file builder the pack calls
        'pb_hr_payroll_formula',    # the one-time import batch the feed builds
    ],
    'data': [
        'security/pb_comp_ben_security.xml',
        'security/ir.model.access.csv',
        'data/comp_ben_params.xml',
        'data/mail_template_data.xml',
        'data/ir_cron.xml',
        'report/run_summary_report.xml',
        'views/comp_ben_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_comp_ben/static/src/scss/comp_ben.scss',
            # the leaf components first, then the file that names their actions
            'pb_comp_ben/static/src/js/paycal_board.js',
            'pb_comp_ben/static/src/js/incentives_board.js',
            'pb_comp_ben/static/src/js/comp_ben_palette.js',
            'pb_comp_ben/static/src/xml/paycal_board.xml',
            'pb_comp_ben/static/src/xml/incentives_board.xml',
        ],
        # The portal bundle gets this page's own rules and nothing else — no
        # backend asset is ever leaked into a /my/... page.
        'web.assets_frontend': [
            'pb_comp_ben/static/src/scss/portal_comp.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
