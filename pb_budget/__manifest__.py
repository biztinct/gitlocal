# -*- coding: utf-8 -*-
{
    'name': 'Payobook Budgets',
    'summary': 'What each function was given for the year, what it has actually '
               'spent, and who is burning it faster than the calendar',
    'description': """
RIZE phase P9 — budgets on the engine that is already here.

WHAT THIS MODULE IS

  * **One budget row, and it lives here.** A budget row is one month, one team
    and one kind of money: what was planned, what was spent, what is left, the
    currency it is in, where the figure came from and the function it rolls up
    into. It used to live in the old planning module and was extended from the
    outside; it has come home, with every row carried across and the totals
    checked on both sides before anything was removed.
  * **A budget arrives as a spreadsheet.** Download a template with the year's
    twelve months across the top and the departments down the side, fill it in,
    drop it back. The upload PREVIEWS before it writes: what would be created,
    what would be updated, and every row whose department this database has
    never heard of — named, and never created. The same file twice updates; it
    never duplicates.
  * **The spend posts itself.** Payroll actuals are read from the analytics fact
    tables — the same aggregation the Cost Explorer draws, filter for filter —
    and written onto the matching month's budget row. A department that spent
    money nobody budgeted for gets a row of its own, flagged. The job only ever
    writes the SPENT columns; the budget columns belong to whoever uploaded them.
  * **HR operations and admin spend are entered.** Payroll facts do not know what
    a training course or a recruitment agency cost, so those are `pb.budget.expense`
    rows — a date, a department, an amount, a note, a file — and they roll into
    their month's actuals exactly as payroll does.
  * **The Budget lens, and the heat view.** On the Insights mission: every
    function as a tile, coloured by how fast it is burning AGAINST THE CALENDAR
    rather than against zero, with the year's own position marked on each bar.
    One glance answers "who is going to run out". A tile opens its months, its
    departments and the expenses underneath. There is a table view beside it for
    people who would rather read the numbers, and both export.
  * **Everybody sees their own part.** A function head sees the function they
    lead. Finance sees every budget in the companies they are in. Nobody else
    sees anything at all, and the lens enforces the same boundary the record
    rules do.

MONEY IS NEVER CONVERTED ON A GUESS. Where the row's currency differs from the
reporting currency and this database has never been told what one is worth in
the other, the reporting column says so in words instead of showing a number
that is wrong by a factor of twenty-six thousand (R23).

pbim tokens only, Lucide icons through the shared `ic()` registry, flat fills,
one accent. No emoji.
""",
    'version': '19.0.2.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'pb_explorer',                # the fact tables the actuals are read from
        'pb_import_kit',              # pbim tokens/primitives + the shared ic() set
        'pb_hub',                     # the global command palette registry
        'pb_insights_hub',            # the hub the Budget lens bolts onto
        'pb_group',                   # `pb.fx`, the one conversion service
    ],
    'data': [
        'security/pb_budget_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'report/budget_report.xml',
        'views/budget_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_budget/static/src/scss/budget.scss',
            # the leaf component first, then the file that names its doors
            'pb_budget/static/src/js/budget_board.js',
            'pb_budget/static/src/js/budget_palette.js',
            'pb_budget/static/src/xml/budget_board.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
