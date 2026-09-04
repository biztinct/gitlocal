# -*- coding: utf-8 -*-
{
    'name': 'Access, in plain English',
    'summary': 'Who can do what, said in words people recognise — with '
               'hand-overs that take themselves back',
    'description': """
One home for access management, and it belongs to no particular product.

WHAT THIS MODULE IS

  * **Roles, written the way people talk.** A curated layer over the permission
    groups an application already has: a plain name, one sentence saying WHAT
    THIS LETS SOMEONE DO, and the people who hold it. It adds no permission
    primitive and invents no tier — there is still exactly one place access is
    decided, and this is a readable window onto it.
  * **A role is a bundle of abilities.** An ability is the small unit somebody
    recognises — "approve a pay run", "read the audit trail" — and it carries
    the one or more permissions that sentence really costs. Roles are built out
    of abilities; nobody builds one out of raw permissions, because a job that
    needs two of them should not have to be split into two rows nobody
    recognises. Abilities are data, so covering a new one costs no release.
    Holding a role means holding ALL of it, and lending one means holding all of
    it first.
  * **One home, with lenses over the same truth.** A lens bar, and role cards
    that OPEN OUT into the three questions people actually ask — what does it
    open on the left menu, what does it let them do, and who holds it. Which
    screens a role opens is never written down on the role: it is worked out by
    matching what the role carries against what each left-menu entry asks for,
    using the left menu's own rule, on the server. Re-gate a screen and every
    role's answer changes with it, because there is only ever one answer.
  * **A passport for every person, and a pair of spectacles.** The People lens
    answers the other question — not "who holds this role" but "what does this
    person have". Their LEFT MENU is drawn as they see it, entry by entry, and
    the states come from the left menu's own code rather than from a copy of its
    rule. Under it, every role they carry and the reason they carry it — theirs,
    or lent until a date by somebody named. "See it as…" in the header repaints
    the whole home as somebody else's reality; it is a VIEW and can never be
    anything else, because nothing on this screen takes "who am I looking at" as
    an argument to a write.
  * **The left menu, drawn as the left menu, with its gates on it.** The Screens
    lens answers the third question — WHO SEES THIS SCREEN. Every entry is a row
    in the menu's own order with its own icon, carrying the ROLES that open it,
    whether the person in the "see it as" picker can open it, and a switch for
    whether it is on the menu at all. No permission-group name appears anywhere
    on it — an older permission that is part of a role is named as that role,
    and one that belongs to no role is a count.
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

IT SEEDS NOTHING, AND THAT IS THE POINT. This module ships no roles, no
abilities and no vocabulary of its own beyond one neutral area, because the
words on an access board are the application's words and not this one's. An
application registers three things and gets a full board:

  * its areas — `access_common.register_areas([...], default=...)`;
  * its own administrator tier, if that tier should also manage access —
    `access_common.register_manager_groups(...)` on the server and
    `registerAccessManagerGroups(...)` in the browser;
  * a callable that seeds its own catalogue — `hooks.register_catalogue(fn)`.

Installed on its own, it boots to a working, empty, honest Access home.

THE ONE ABSOLUTE. Nothing here can ever hand out the system administrator
permission (`base.group_system` / `base.group_erp_manager`). The role and
ability models refuse to be created pointing at one — over the whole implied
closure, so a permission that merely IMPLIES it is refused too — and the facade
checks again before it writes. Three refusals for one rule, because it is the
only rule in the module whose failure cannot be undone by somebody who is still
able to log in.

WHAT IT DELIBERATELY IS NOT. No new permission system, no approval chain on a
hand-over (notifications are the requirement and they are enough), and no
opinion whatsoever about what an application's roles should be.

pbim tokens only, `.pbva-*` class names, Lucide icons through the shared `ic()`
registry, flat fills, one accent. No emoji.
""",
    'version': '19.0.1.1.0',
    'category': 'Administration',
    'license': 'LGPL-3',
    'author': 'Biztinct',
    'website': 'https://www.biztinct.com',
    'depends': [
        'base',
        'hr',                   # the People lens draws colleagues, not logins
        'mail',                 # the hand-over's own thread and its two mails
        'pb_import_kit',        # pbim tokens/primitives + the shared ic() set
        'pb_hub',               # HubShell's back chip, openHub, the ⌘K registry
        'pb_settings',          # the cog this module's two panels bolt onto
        'pb_sidebar',           # the left menu the Access home reads to work
                                # out which screens a role opens, and the model
                                # the role lane is added to
    ],
    'data': [
        'security/biz_access_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'data/mail_template_data.xml',
        'views/access_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'biz_access/static/src/scss/access.scss',
            # the leaf component first, then the file that names its doors
            'biz_access/static/src/js/mini_rail.js',
            'biz_access/static/src/js/access_board.js',
            'biz_access/static/src/js/access_palette.js',
            'biz_access/static/src/xml/mini_rail.xml',
            'biz_access/static/src/xml/access_board.xml',
        ],
    },
    # The re-homing of what this module was extracted from. It runs BEFORE the
    # models are reflected and before any data file — the only moment at which
    # it can.
    'pre_init_hook': 'pre_init_hook',
    # This fires on INSTALL only, never on `-u`. `ensure_catalogue()` is public
    # so it can be run again by hand or from a later migration.
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
