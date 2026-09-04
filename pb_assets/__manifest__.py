# -*- coding: utf-8 -*-
{
    'name': 'Payobook Assets',
    'summary': 'The asset register — every laptop, phone, card and account the '
               'company lends out, who has it, and what came back',
    'description': """
RIZE phase P2 — the asset register.

WHAT THIS MODULE IS

  * `pb.asset.category` — the kinds of thing a company hands out, physical
    (laptop, phone, SIM, ID card, company card, monitor) and digital (email
    account, system login, software licence, phone number). The category decides
    the two letters in an asset code, which state ladder the item follows, and
    whether every joiner should get one.
  * `pb.asset` — one item. Its code is `VN-LT-00042`: the country it lives in,
    the kind of thing it is, and its running number IN THAT COUNTRY. The number
    is per country and not per category on purpose — an inventory is counted by
    the office that holds it.
  * `pb.asset.assignment` — one row per handover, never edited away. Who had it,
    from when to when, what state it was in each way, and whether the person
    confirmed they actually had it. A partial unique index enforces the one rule
    that matters: one open holder per item, even when two screens save at the
    same second.
  * `pb.asset.request` — "this person needs a laptop", riding the shared
    approval chain (manager, then the asset team) with SPARES SUGGESTED FIRST:
    the cheapest laptop is the one already bought.
  * The **Assets lens** on the People hub — the board, the drawer with the whole
    history of one item, and a bulk bar.
  * `/my/assets` — what the employee has been given, with one button: "Yes, I
    have it".

THE TWO SEAMS INTO THE PHASES AROUND IT.

  * `pb.asset.open_items_for(employee_id)` is the one answer to "what is this
    person still holding" — P4 reads it to hold a final settlement.
  * When an OFFBOARDING journey opens, this module appends one step per item the
    person actually has: "Return: …" (which holds the final settlement) for the
    physical ones and "Switch off: …" for the digital ones. The same code runs
    from the connected system's leaver hook, and it is idempotent, so a case
    that reaches it twice still gets one step per item.

Nothing here modifies `pb_people` or `pb_people_hub`: the lens arrives through
their soft registry, which is what lets the dependency run one way only.
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
        'portal',               # the /my/assets page
        'pb_hub',               # the global palette registry
        'pb_import_kit',        # pbim tokens/primitives + the shared ic() set
        'pb_people_hub',        # the hub this module bolts its lens onto
        'pb_me_portal',         # the .pbme portal kit the page reuses
        'pb_lifecycle',         # the journey a leaver's asset steps join
        'pb_zoho_bridge',       # the leaver hook the connected system fires
        'biz_approval_chain',   # the chain an asset request rides
    ],
    'data': [
        'security/pb_assets_security.xml',
        'security/ir.model.access.csv',
        'data/asset_category_data.xml',
        'views/asset_views.xml',
        'views/asset_request_views.xml',
        'views/pb_assets_action.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_assets/static/src/scss/assets.scss',
            # the leaf component first, then the rows that name its action
            'pb_assets/static/src/js/assets_board.js',
            'pb_assets/static/src/js/assets_palette.js',
            'pb_assets/static/src/xml/assets_board.xml',
        ],
        # A LEAN frontend bundle for /my/assets: the kit's tokens, the ESS
        # page kit and this module's block. No backend asset is leaked in.
        'web.assets_frontend': [
            'pb_assets/static/src/scss/portal_assets.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
