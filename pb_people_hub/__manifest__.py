# -*- coding: utf-8 -*-
{
    'name': 'Payobook People Hub',
    'summary': 'The People mission — employees, contracts and a launcher for '
               'the planning room',
    'description': """
IA redesign Cycle 5 — the People mission.

Three lenses, in the order a person exists in payroll:

    employees · contracts · plan

`employees` and `contracts` are the EXISTING cockpits mounted with
`embedded: true` — one component, one facade, two mount points (W17). Neither is
reimplemented, neither is forked, and both standalone client actions keep
working.

**`plan` is a MOUNT POINT.** Whatever planning product is installed renders
inside it full-bleed; when nothing is, the lens says so in a sentence and
offers nothing. It used to be a card grid over seven screens of an older
planning module — scenarios, forecasts, pay grades, a merit matrix,
compensation cycles and a component-tagging wizard. Every one of those has
been replaced by something built on this product's own engine, and the grid
went with the module that owned them, because a card that opens nothing is
the worst screen this product can show.

pbim tokens only, Lucide icons through the shared `ic()` registry, flat fills,
one accent (W1/W2/W3).
""",
    'version': '19.0.2.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_hub',                       # the shell kit + the global palette
        'pb_settings',                  # the cog, and `pb.settings.resolve_actions`
        # the two surfaces this hub mounts as lenses
        'pb_people',
        'pb_contracts',
    ],
    'data': [
        'views/pb_people_hub_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_people_hub/static/src/scss/people_hub.scss',
            'pb_people_hub/static/src/js/plan_launcher.js',
            'pb_people_hub/static/src/js/people_hub.js',
            'pb_people_hub/static/src/js/people_hub_palette.js',
            'pb_people_hub/static/src/xml/people_hub.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
