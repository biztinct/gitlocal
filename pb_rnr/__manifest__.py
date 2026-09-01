# -*- coding: utf-8 -*-
{
    'name': 'Payobook Recognition',
    'summary': 'Company values, praise that two people have to agree with, '
               'quarterly winners, the wall everybody sees, and birthdays and '
               'work anniversaries nobody has to remember',
    'description': """
RIZE phase P8 — recognition that is worth having, and that can pay.

WHAT THIS MODULE IS

  * **Company values that are records, not a poster.** `pb.company.value` — five
    seeded to start with, editable, each with a motto in a sentence. Every piece
    of praise names one, which is what turns "well done" into "this is what we
    mean by Candour".
  * **Praise that two people have to agree with.** A nomination is written by a
    colleague, agreed by the nominee's own MANAGER, and then decided by HR. Two
    hands, on the generic approval chain (`biz.approval.chain.mixin`) rather than
    a fourth hand-rolled state machine. `state` says how far it got; `outcome`
    says what was decided. A declined nomination never appears anywhere public,
    ever.
  * **Cash, through the door that already exists.** HR can attach an amount when
    they recognise somebody. That creates a `pb.incentive` with `source='rnr'`
    and NOTHING ELSE — it rides P7's approval, P7's letter and P7's pay feed.
    **This module never puts money into a pay run.** Queueing stays one explicit
    press on the Awards lens, because money must never move without a human
    pressing the money button.
  * **Quarterly cycles.** A window, a roll-up that ranks people by how many times
    colleagues named them and under which values, and a pick of winners with
    amounts — behind a plain-English confirmation that says what the money does.
  * **The wall.** A lens on the Home mission: the praise that has actually been
    agreed, with photographs, in the values' own colours. Every internal user
    sees it. Nothing that was declined and nothing the writer marked private is
    on it.
  * **Birthdays and work anniversaries.** One read (`upcoming_celebrations`) used
    by the wall, the digest and two jobs: a congratulation on the day, and a
    Monday heads-up to managers listing their team's week. **No date of birth is
    ever shown** — the day and the month, and that is all.
  * **The monthly mood board.** One designed email a month: this month's praise,
    who joined, who is celebrating next month, and the quarter's winners when
    they are fresh. Idempotent by month.

EVERY SEND SHIPS OFF. The digest, the congratulations and the manager heads-up
are each behind their own switch, all three default '0', and each job COUNTS
what it would have sent and logs the number rather than going quiet (R54). The
digest also has a single-address test override so it can be read before anybody
else gets it.

pbim tokens only, Lucide icons through the shared `ic()` registry, flat fills,
one accent. No emoji anywhere — including in the emails.
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
        'portal',               # /my/recognition
        'biz_approval_chain',   # the nomination's two-step ladder
        'pb_hub',               # the global command palette registry
        'pb_import_kit',        # pbim tokens/primitives + the shared ic() set
        'pb_home_hub',          # the hub the wall bolts onto
        'pb_people_hub',        # the hub the board bolts onto
        'pb_me_portal',         # the .pbme portal kit this page reuses
        'pb_lifecycle',         # the letter engine an award's letter comes from
        'pb_comp_ben',          # `pb.incentive` + `pb.oneoff.feed` (P7)
    ],
    'data': [
        'security/pb_rnr_security.xml',
        'security/ir.model.access.csv',
        'data/rnr_params.xml',
        'data/company_value_data.xml',
        'data/mail_template_data.xml',
        'data/ir_cron.xml',
        'views/digest_templates.xml',
        'views/rnr_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_rnr/static/src/scss/rnr.scss',
            # the leaf components first, then the file that names their actions
            'pb_rnr/static/src/js/rnr_board.js',
            'pb_rnr/static/src/js/rnr_wall.js',
            'pb_rnr/static/src/js/rnr_palette.js',
            'pb_rnr/static/src/xml/rnr_board.xml',
            'pb_rnr/static/src/xml/rnr_wall.xml',
        ],
        # The portal bundle gets this page's own rules and nothing else — no
        # backend asset is ever leaked into a /my/... page.
        'web.assets_frontend': [
            'pb_rnr/static/src/scss/portal_rnr.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
