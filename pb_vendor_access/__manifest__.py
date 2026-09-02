# -*- coding: utf-8 -*-
{
    'name': 'Payobook Vendors & Access',
    'summary': 'The suppliers HR deals with and when their agreements run out, '
               'and who holds what access — in plain English, with hand-overs '
               'that take themselves back',
    'description': """
RIZE phase P11 — vendors on a leash, access in plain language.

WHAT THIS MODULE IS

  * **A vendor register that tells you before it is too late.** Agencies,
    training providers, insurers, software suppliers — who they are, who here
    owns the relationship, and what has been agreed with them. Every agreement
    carries its dates and its files, and its state is COMPUTED from the calendar
    rather than typed, so it can never say "Running" about something that ended
    last March. A nightly job tells the owner while there is still time to do
    something, and escalates to HR once it has run out.
  * **Renewal is a new record, never an edit.** What was agreed last year is a
    fact about last year. Renewing prefills a fresh agreement from the old one,
    marks the old one replaced and keeps both.
  * **Roles, written the way people talk.** A curated catalogue over the
    permission groups this product already has: a plain name, one sentence
    saying WHAT THIS LETS SOMEONE DO, and the people who hold it. It adds no
    permission primitive and invents no tier — there is still exactly one place
    access is decided, and this is a readable window onto it.
  * **A role is a bundle of abilities.** An ability is the small unit somebody
    recognises — "approve a pay run", "read the audit trail" — and it carries
    the one or more permissions that sentence really costs. Roles are built out
    of abilities; nobody builds one out of raw permissions, because a job that
    needs two of them should not have to be split into two rows nobody
    recognises. Abilities are data, so covering a new one costs no release.
    Holding a role means holding ALL of it, and lending one means holding all of
    it first.
  * **One home, with lenses over the same truth.** The roles board is the
    Access home: a lens bar, and role cards that OPEN OUT into the three
    questions people actually ask — what does it open on the left menu, what
    does it let them do, and who holds it. Which screens a role opens is never
    written down on the role: it is worked out by matching what the role
    carries against what each left-menu entry asks for, using the left menu's
    own rule, on the server. Re-gate a screen and every role's answer changes
    with it, because there is only ever one answer.
  * **A passport for every person, and a pair of spectacles.** The People lens
    answers the other question — not "who holds this role" but "what does this
    person have". Their LEFT MENU is drawn as they see it, entry by entry, and
    the states come from the left menu's own code rather than from a copy of its
    rule: there is one answer to "can they open this", and both screens ask the
    same one. Under it, every role they carry and the reason they carry it —
    theirs, or lent until a date by somebody named. "See it as…" in the header
    repaints the whole home as somebody else's reality; it is a VIEW and can
    never be anything else, because nothing on this screen takes "who am I
    looking at" as an argument to a write.
  * **The left menu, drawn as the left menu, with its gates on it.** The
    Screens lens answers the third question — not "who holds this role" or
    "what does this person have" but WHO SEES THIS SCREEN. Every entry is a row
    in the rail's own order with the rail's own icon, carrying the ROLES that
    open it, whether the person in the "see it as" picker can open it, and a
    switch for whether it is on the menu at all. Clicking one says who can reach
    it today and through which role, what is inside it, and what everybody else
    sees instead. It is also the only place a gate is edited: before it, the one
    way to change who saw an entry was a table of permission-group names, which
    is exactly why the live menu had ended up with no gates on it at all. No
    permission-group name appears anywhere on it — an older permission that is
    part of a role is named as that role, and one that belongs to no role is a
    count.
  * **A builder that shows the outcome while you build it.** "New role" is a
    name, one honest sentence, and a list of ABILITIES to tick — never a raw
    permission — beside a miniature of the left menu that lights up as they are
    ticked. Nobody has to imagine what they are about to hand out.
  * **Hand-overs that take themselves back.** Somebody going away lends what
    they hold to somebody covering, until a date. Activation adds only what the
    lender ACTUALLY HOLDS — checked on the server, not just hidden in the dialog
    — and writes down exactly what it added. A nightly job removes precisely
    those permissions, only where they are still there, and tells both people.
    A group somebody was given in their own right in the meantime is not taken
    away, and a group an administrator revoked is not re-added and re-removed.
  * **One audit trail, and it has no delete button.** Every hand-over, and every
    role given or taken away on the board, is a row in the same table. `unlink`
    is refused for everybody, an administrator included.

THE ONE ABSOLUTE. Nothing here can ever hand out the system administrator
permission (`base.group_system` / `base.group_erp_manager`). It is excluded from
the seeded catalogue, the role model refuses to be created pointing at one, and
both facades check again before they write. Three refusals for one rule, because
it is the only rule in the module whose failure cannot be undone by somebody who
is still allowed to log in.

WHAT IT DELIBERATELY IS NOT. No supplier invoicing, no purchase orders, no
approval chain on a hand-over (notifications are the requirement and they are
enough), and no new permission system. `vendor_license_core` — the product's own
self-licensing — shares a word with this module and nothing else; it is not
touched, referenced or imported.

pbim tokens only, `.pbva-*` class names, Lucide icons through the shared `ic()`
registry, flat fills, one accent. No emoji.
""",
    'version': '19.0.1.4.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'mail',
        'pb_lifecycle',         # the reminder/letter patterns + the HR tiers
                                # the vendor rules and the ACL name directly
        'pb_employee_vault',    # the attachment + expiry-cron canon
        'pb_import_kit',        # pbim tokens/primitives + the shared ic() set
        'pb_hub',               # HubShell's back chip, openHub, the ⌘K registry
        'pb_settings',          # the cog this module's two panels bolt onto
        'pb_sidebar',           # the left menu the Access home reads to work
                                # out which screens a role opens. Already here
                                # through pb_settings; named because this
                                # module now depends on the MODEL, not just on
                                # whatever happens to be installed alongside.
        'pb_assets',            # `pb.asset` — the vendor_id link
        'pb_budget',            # `pb.budget.expense` — the optional vendor link
    ],
    'data': [
        'security/pb_vendor_access_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'data/mail_template_data.xml',
        'views/vendor_access_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_vendor_access/static/src/scss/vendor_access.scss',
            # the leaf components first, then the file that names their doors
            'pb_vendor_access/static/src/js/mini_rail.js',
            'pb_vendor_access/static/src/js/vendors_board.js',
            'pb_vendor_access/static/src/js/access_board.js',
            'pb_vendor_access/static/src/js/vendor_palette.js',
            'pb_vendor_access/static/src/xml/mini_rail.xml',
            'pb_vendor_access/static/src/xml/vendors_board.xml',
            'pb_vendor_access/static/src/xml/access_board.xml',
        ],
    },
    # R84 — this fires on INSTALL only, never on `-u`. `ensure_catalogue()` is
    # public so it can be run again by hand or from a later migration.
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
