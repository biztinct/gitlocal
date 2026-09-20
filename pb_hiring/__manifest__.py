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

  * **The interview loop.** An hour is arranged once and everybody is invited
    from here — the candidate, the panel and the recruiter — each with a
    calendar file they can open straight into their own diary. Payobook
    reminds them the day before and again half an hour before. Moving an
    interview asks why and whose side moved it, and keeps both, so a company
    can finally answer why its hiring takes as long as it does. Nobody coming
    is written down rather than forgotten.
  * **Opinions that actually land.** Everybody who sat in the room gets their
    own private link — no sign-in, it works once — with five lines to score
    and one question: would you hire them. A day of working hours later,
    anybody who has not answered is chased once. A round cannot be closed
    while an opinion is missing, because "closed" would then mean "forgotten".
  * **The two answers a candidate is waiting for.** Through to the next round,
    or not this time — both written in plain words, both actually sent. On the
    last conversation the panel's verdict and the decision are recorded
    together, and that is where the offer starts from.

  * **The background check, and the door it holds shut.** A checklist per
    candidate, every line answered before an offer can be drafted, and a
    written "we are going ahead anyway" when something comes back. It is not a
    note: it stops the next step until somebody has said.
  * **The papers, asked for once.** The candidate gets one link, on their
    phone, listing exactly what is wanted with two working days to send it.
    They are reminded once a day and never twice, and the recruiter is told
    the day the window shuts — because somebody who has gone quiet is a person
    to ring, not a row to expire.
  * **The offer.** Every line of it typed out with the word a candidate would
    use, a month and a year worked out at the bottom, the company's own offer
    letter filled in and printed, and a route — the hiring manager first,
    because it is their team and their budget, then the HR lead, because it
    has to sit beside what everybody else is paid. Change a number after
    somebody has agreed it and it goes round again.
  * **Their answer, in their own words.** The candidate reads the offer on a
    page of their own, accepts or turns it down, and can say why. Signing is
    recorded by a person with the signed copy attached — nothing here pretends
    to be a signature it is not.
  * **Day one, in one press.** Closing an offer makes the employee record, the
    contract that gives them a joining date, the pay package for the
    compensation team, their login, and the SAME joining checklist somebody
    arriving through a connected system gets. The role closes itself when the
    last person has joined, the advert comes off the careers page and the
    people who need to know are told.
  * **Cover for a recruiter.** A fortnight away is a request their own manager
    agrees, and for that fortnight one named colleague can work on their roles
    and on nobody else's. Nothing is granted and nothing has to be taken back.
  * **The numbers.** How long a role takes to fill, how long to a first offer,
    where candidates get stuck, how many offers are accepted, which channels
    actually produce joiners, how often interviews move and whose side moves
    them, and whether an agency is faster than doing it yourself — with the
    whole thing downloadable as a spreadsheet.
""",
    'version': '19.0.1.2.0',
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
        'calendar',                 # A2: the diary entry behind an interview
        # A3. Every one of these is a JOIN and not a copy: the offer becomes a
        # pay package, the signed letter is filed in the vault, the joiner gets
        # the connected system's own joining path, the agency is the vendor
        # register's own row, and the numbers live on the Insights hub.
        'pb_comp_ben',              # the pay package an offer becomes
        'pb_employee_vault',        # where the signed letter is filed
        'pb_zoho_bridge',           # the joining checklist and the login (D6)
        'pb_vendor_access',         # the agency on the other end of the role
        'pb_insights_hub',          # the hub the Hiring numbers lens joins
    ],
    'data': [
        'security/pb_hiring_security.xml',
        'security/ir.model.access.csv',
        'data/approval_process.xml',
        'data/ir_sequence.xml',
        'data/hiring_params.xml',
        'data/hiring_criteria.xml',
        'data/mail_template_data.xml',
        'data/mail_template_interviews.xml',
        'data/hiring_bgv_templates.xml',
        'data/hiring_doc_templates.xml',
        'data/letter_template_offer.xml',
        'data/mail_template_offer.xml',
        'data/ir_cron.xml',
        'report/hiring_offer_report.xml',
        'views/hiring_views.xml',
        'views/interview_views.xml',
        'views/offer_views.xml',
        'views/vendor_views.xml',
        'views/portal_templates.xml',
        'views/token_templates.xml',
        'views/offer_token_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_hiring/static/src/scss/hiring.scss',
            # the leaf component first, then the rows that name its action
            'pb_hiring/static/src/scss/hiring_numbers.scss',
            'pb_hiring/static/src/js/hiring_board.js',
            'pb_hiring/static/src/js/hiring_numbers.js',
            'pb_hiring/static/src/js/hiring_palette.js',
            'pb_hiring/static/src/xml/hiring_board.xml',
            'pb_hiring/static/src/xml/hiring_numbers.xml',
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
