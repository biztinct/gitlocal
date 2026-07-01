{
    'name': 'Payobook Coach',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Animated guided tours (spotlight + pointer) and first-run onboarding for Payobook',
    'description': """
Payobook Coach
==============
A bespoke OWL coaching layer that floats above every backend screen:
 * spotlight + animated pointer + design-system coach cards
 * interactive AND autoplay ("Watch") tour modes
 * a first-run welcome modal and a "Getting Started" launcher
 * an ephemeral-demo-data disclaimer for trial users
Tours are registered in the ``pb_coach.tours`` registry category; steps target
elements via ``data-coach="..."`` anchors so they survive re-styling.
""",
    'author': 'Payobook',
    'depends': ['web', 'pb_import_kit'],
    'assets': {
        'web.assets_backend': [
            'pb_coach/static/src/scss/coach.scss',
            'pb_coach/static/src/js/coach_service.js',
            'pb_coach/static/src/js/coach_icons.js',
            'pb_coach/static/src/js/coach_overlay.js',
            'pb_coach/static/src/xml/coach_overlay.xml',
            # tour definitions (self-register into pb_coach.tours) — load order
            # drives the launcher list order.
            'pb_coach/static/src/js/tours/hero_path.js',
            'pb_coach/static/src/js/tours/tour_formula.js',
            'pb_coach/static/src/js/tours/tour_payrun.js',
            'pb_coach/static/src/js/tours/tour_payslips.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
