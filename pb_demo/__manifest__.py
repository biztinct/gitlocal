# -*- coding: utf-8 -*-
{
    'name': 'Payobook Demo Environment',
    'version': '19.0.1.6.0',
    'category': 'Human Resources/Payroll',
    'summary': 'World-class, regenerable demo world: multilingual component library, '
               'division schemes, thousands of realistic employees and months of payroll history.',
    'description': """
Payobook Demo Environment
=========================
Builds an enterprise-grade, fully reusable demo database:

* Deduplicated, multilingual (EN/VI) payroll **Component Library** assembled into
  division **schemes** (Retail, Manufacturing, Logistics, Corporate, IT, Construction),
  each with a mid-cycle and end-cycle configuration.
* Metadata-driven **scheme resolver** (company + division + grade -> structure).
* Group **presentation currency** + FX-aware analytics consolidation.
* Idempotent Python **generator**: legal entities, divisions, cost-centres,
  thousands of realistic employees, contracts, and months of payroll history
  with month-varying scenarios. Regenerate wipes and rebuilds.

Everything is driven by metadata so countries, languages, schemes and components
can be extended without changing payroll logic.
""",
    'author': 'Payobook',
    'website': 'https://payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'pb_hr_payroll_base',
        'pb_hr_payroll_formula',
        'pb_people',
        'pb_contracts',
        'pb_sidebar',
        'pb_payrun_wizard',
        'pb_payroll_ai_insights',
    ],
    'data': [
        'security/pb_demo_security.xml',
        'security/ir.model.access.csv',
        'data/pb_demo_data.xml',
        'views/pb_demo_views.xml',
        # Loaded last: re-applies the Demo User sidebar/access wiring on every
        # upgrade (post_init hook is install-only; a cascade resets it).
        'data/pb_demo_sidebar_access.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_demo/static/src/scss/demo_analytics.scss',
            'pb_demo/static/src/js/demo_analytics.js',
            'pb_demo/static/src/xml/demo_analytics.xml',
            # THE DEMO WORLD'S OWN CHROME (Phase C2). Moved out of pb_coach,
            # which is being retired: the body tag that keeps a trial user
            # inside Payroll, the ephemeral-data disclaimer, and the
            # missing-record guard are all facts about the DEMO, not about
            # guided tours. Every one of them stands down while pb_coach is
            # still installed, so the two coexist until the uninstall.
            'pb_demo/static/src/scss/demo_chrome.scss',
            'pb_demo/static/src/js/demo_missing_record.js',
            'pb_demo/static/src/js/demo_chrome.js',
            'pb_demo/static/src/xml/demo_chrome.xml',
            'pb_demo/static/src/js/demo_chrome_patch.js',
        ],
    },
    'post_init_hook': 'post_init_demo',
    'application': False,
    'installable': True,
}
