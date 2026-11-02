# -*- coding: utf-8 -*-
{
    'name': 'Payobook Filter Panel',
    'summary': 'One filter panel for every list: counts, saved views, chips, find-a-filter',
    'description': """
The shared filter panel every Payobook list uses (FILTER program, owner
choice 2026-10-30: "B+", a left facet panel upgraded with saved views,
clickable chips, find-a-filter, pinned sections and hide-and-keep-chips).

Server half: `pb.filter.mixin` — a screen declares what can be filtered,
the mixin builds the domain, the counts beside every value and the
built-in views. `pb.filter.view` stores the views people save.

Client half: `useFilterKit` + `PbFilterLayout` (views tabs, toolbar, left
panel, chips) with a slot for the screen's own list.
""",
    # 1.3.0: view tabs are recounted on every full refresh (an approval shows
    # at once); "Clear all" no longer leaves the previous tab lit with a dot.
    # 1.4.0: the closeout backlog — kit.kw()/kit.context for a screen's own
    # calls; sudo screens label ticked values as sudo; reconfigure() load
    # guard; link/door filters remembered at once; initial.merge (on top of
    # the first view); date "none" only with a none_label; number units in
    # hints and chips; `hidden` sections; domain_method `args`; a one-option
    # choice.
    'version': '19.0.1.4.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'pb_import_kit'],
    'data': [
        'security/ir.model.access.csv',
        'security/filter_view_rules.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_filter_kit/static/src/scss/filter_kit.scss',
            'pb_filter_kit/static/src/js/filter_kit.js',
            'pb_filter_kit/static/src/js/filter_components.js',
            'pb_filter_kit/static/src/xml/filter_kit.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
