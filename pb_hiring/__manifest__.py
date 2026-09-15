# -*- coding: utf-8 -*-
{
# The opening line of this description is what the Apps list prints, so it is
# a USER-VISIBLE string and carries no programme code (ledger GR7, TIDY T10).
# Built as RIZE Wave 2 phase A1.
    'name': 'Payobook Hiring',
    'summary': 'Ask for a new person, get it agreed, write the advert and let '
               'everybody refer somebody',
    'description': """
Hiring, from the moment somebody needs a person to the moment the
advert goes out.

THE PROBLEM. Asking for a new person is a conversation, a spreadsheet and a
chain of forwarded emails. Nobody can say who agreed it, whether there was any
money for it, which advert went out, or who in the company put a friend
forward. By the time a candidate arrives the request that started it all has
disappeared.

WHAT THIS MODULE IS

  * **The hiring request.** A function head asks for a role. The request
    carries the money it expects to cost and Payobook works out, from the
    budget already in the system, whether there is room for it — within, over
    by how much, or nothing budgeted at all. It then travels the route the
    business published: their manager, the HR lead, and the Finance approver
    only when it is over budget.
  * **The advert, written down and agreed.** A job description is a numbered
    version on the request. It is agreed by the hiring manager, and the agreed
    one is what goes onto the job and onto the careers page. The older versions
    stay readable, so a year later somebody can see what was actually promised.
  * **Referrals that go somewhere.** Every employee gets a page listing the
    roles that are open to referrals, with one short form. What they send in
    becomes a real candidate on the real job, tagged as a referral, and the
    person who sent it can see how far it got.
  * **A posting pack per platform.** Pressing Publish puts the role on the
    careers page and prepares a ready-to-send advert for every job board the
    company uses. Sending them is a switch, off to begin with, so nothing
    leaves the building until somebody says so.
  * **Screening in one press.** Shortlisted, not this time, worth keeping, or
    better suited to another role — and that last one moves the candidate to
    the other role rather than making somebody retype them.
  * **Who recruits for where.** One small table says, per company and country,
    which recruiter picks a request up and who their manager is, so an approved
    request lands on a real person's desk within the minute.

WHAT IT DELIBERATELY DOES NOT DO YET. Interviews, background checks, offers and
the hiring analytics are the next two phases and are not in this one.
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
        'portal',
        'utm',                      # the Referral source a referral is tagged with
        'hr_recruitment',           # the job / applicant / talent-pool store
        'website_hr_recruitment',   # the public careers page a posting publishes to
        'biz_approval_chain',       # the trail and the state-write guard
        'biz_approval_workflow',    # the route both sign-offs run on
        'pb_hub',                   # the global command-bar registry
        'pb_import_kit',            # pbim tokens/primitives + the shared ic() set
        'pb_lifecycle',             # the hub this lens joins, and its tiers
        'pb_me_portal',             # the .pbme employee-page kit
        'pb_budget',                # the one budget table (ruling D2)
        'pb_settings',              # the cog the hiring rules live behind
    ],
    'data': [
        'security/pb_hiring_security.xml',
        'security/ir.model.access.csv',
        'data/approval_process.xml',
        'data/ir_sequence.xml',
        'data/hiring_params.xml',
        'data/mail_template_data.xml',
        'data/ir_cron.xml',
        'views/hiring_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_hiring/static/src/scss/hiring.scss',
            # the leaf component first, then the rows that name its action
            'pb_hiring/static/src/js/hiring_board.js',
            'pb_hiring/static/src/js/hiring_palette.js',
            'pb_hiring/static/src/xml/hiring_board.xml',
        ],
        'web.assets_frontend': [
            'pb_hiring/static/src/scss/portal_hiring.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
