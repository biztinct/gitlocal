# -*- coding: utf-8 -*-
{
    'name': 'Payobook Pay Run Hub',
    'summary': 'The Pay Run mission — eight cockpits as eight lenses of one '
               'workspace, with a real period tracker',
    'description': """
IA redesign Cycle 2 — the first real hub.

Option A of the IA dossier collapses the rail into six missions. This module is
the first of them: the eight PAY RUN surfaces become eight lenses of one
`pb_hub` shell, in the mockup's order —

    run · runs · payslips · results · import · deliver · adjust · settle

Every lens is the EXISTING cockpit mounted with `embedded: true` (W17: one
component, one facade, two mount points). No cockpit is reimplemented, no
cockpit is forked, and all eight standalone client actions keep working
unchanged — the hub is ADDITIVE until the rail cutover in Cycle 5, and this
cycle ships no menu and no `pb.sidebar.item` at all. The one door is a
"Pay Run Hub (preview)" entry in the global command palette, plus a per-lens
sub-entry each.

What the hub adds that no single lens could:

  * **the escapes are closed.** The Run wizard's terminal CTA used to leave for
    a native `hr.payslip.run` form; in the hub it switches to the Runs lens with
    the new run focused. The Adjust and Settle ledgers used to offer
    "Open full list →" into a native list; in the hub they are an IN-LENS ledger
    whose rows open a 320px drawer (the `pb_wf_kit` WfDrawer, imported not
    forked) and that link is not rendered.
  * **Adjust is two descriptors in one lens** — Retro | Proration — because an
    officer reconciling a month reads them together.
  * **the period tracker** — `pb.pay.hub.get_period_state()`, a read-only model
    that says where THIS CALENDAR MONTH's payroll actually is, on a heuristic
    written out in README.md and asserted stage by stage in the tests. Clicking
    the chip lands on the lens where the outstanding work lives.
  * **the Runs lens is a revived cockpit.** `pb_payruns`'s bespoke pipeline
    board was written, registered and then never pointed at — the rail opens the
    native kanban instead. Cycle 2 revives it, which is also how its three
    invisible defects were finally fixed.

pbim tokens only, Lucide icons through the shared `ic()` registry, flat fills,
one accent (W1/W2/W3).
""",
    'version': '19.0.1.3.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_hub',               # the shell kit + the global palette registry
        'pb_settings',          # C3: the cog in the command bar opens this hub
        # the eight surfaces this hub mounts as lenses
        'pb_payrun_wizard',
        'pb_payruns',
        'pb_payslip_review',
        'pb_payrun_results',
        'pb_import',
        'pb_pay_delivery',      # also the source of the tracker's stage 5
        'pb_payrun_ledgers',
    ],
    'data': [
        'views/pb_pay_hub_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_payhub/static/src/js/pay_hub.js',
            'pb_payhub/static/src/js/pay_hub_palette.js',
            'pb_payhub/static/src/xml/pay_hub.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
