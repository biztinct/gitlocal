# -*- coding: utf-8 -*-
{
# The opening line of this description is what the Apps list prints, so it is
# a USER-VISIBLE string and carries no programme code (ledger GR7, TIDY T10).
# Built as RIZE Wave 2 phase C1.
    'name': 'Payobook Announcements',
    'summary': 'One calendar for everything the company is about to tell its '
               'people, and it sends itself',
    'description': """
Company announcements, planned like anything else that matters.

THE PROBLEM. Announcements are written on the morning they go out, by whoever
remembers, from whichever mailbox is open — so two land in the same hour, the
public holiday notice goes to the wrong country, and nobody can say afterwards
who was told what.

WHAT THIS MODULE IS

  * **A month you can look at.** Every announcement on a calendar, one pill a
    day, coloured by where it has got to. The reason a town hall notice must
    not go out on the same Monday as the pay-day reminder is that both land in
    the same inbox an hour apart — and a list never shows that.
  * **Write it now, send it then.** Say what it is, who it is for and when it
    should go out. It goes out on its own, at the minute it was booked for, to
    everybody in the audience with a work email.
  * **Who gets it, said out loud.** Everybody at one company, certain parts of
    the business, people doing certain jobs, or every company in a country.
    One press counts them before anything is sent, and the people with no work
    email are named rather than quietly dropped.
  * **Somebody's name on it.** Every announcement has a person who looks after
    it — the HR lead of that company unless you say otherwise. They are
    reminded two days before, by email and on their own to-do list.
  * **A window, and it closes.** Up to two days before, the person responsible
    can change anything. Inside those two days only the HR lead can, and the
    change is written into the announcement's own history. After it has gone
    out nothing changes ever — the button says "Say something new" instead.
  * **Ones that come round.** Every week, every month, every year, until a day
    you choose. Each one is a real announcement of its own, so a single month
    can be reworded without touching the rest.
  * **A sign-off, if you want one.** Switched off, because most companies do
    not ask anybody to agree a canteen notice. Switched on, it goes to the HR
    lead through the same approval system everything else uses.
  * **Birthdays and work anniversaries.** The cards people actually get on the
    day, redesigned. The week's celebrations sit beside the calendar and on
    the Home screen, so a manager can say something out loud.

WHAT IT DELIBERATELY DOES NOT DO. Chat apps and text messages are not
connected — the screens are built ready for them and say so. There is no
second wall: praise stays where praise lives.
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
        'biz_approval_chain',       # the trail and the state-write guard
        'biz_approval_workflow',    # the route the sign-off runs on
        'pb_hub',                   # the global command-bar registry
        'pb_import_kit',            # pbim tokens/primitives + the shared ic()
        'pb_people_hub',            # the hub this calendar lens joins
        # The Home card is a JS import of a soft lens registry, and a registry
        # you import is a dependency you have whether or not the manifest says
        # so. `pb_goals`, `pb_rnr` and `pb_decision_room` declare it for the
        # same reason.
        'pb_home_hub',
        'pb_settings',              # the cog the library lives behind
        # The celebration engine. This module does not rebuild it: it swaps in
        # a designed card at the one seam that decides which template is
        # rendered, and leaves every question about WHO is celebrating where
        # it already is.
        'pb_rnr',
    ],
    'data': [
        'security/pb_hr_comm_security.xml',
        'security/ir.model.access.csv',
        'security/pb_hr_comm_rules.xml',
        'data/ir_cron.xml',
        'data/approval_process.xml',
        'views/mail_templates.xml',
        'views/comm_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_hr_comm/static/src/scss/comm.scss',
            'pb_hr_comm/static/src/js/comm_calendar.js',
            'pb_hr_comm/static/src/js/comm_home.js',
            'pb_hr_comm/static/src/js/comm_palette.js',
            'pb_hr_comm/static/src/xml/comm_calendar.xml',
            'pb_hr_comm/static/src/xml/comm_home.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
