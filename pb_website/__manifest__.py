{
    'name': 'Payobook Website',
    'version': '19.0.1.0.0',
    'category': 'Website',
    'summary': 'Stunning Payobook marketing landing page (served at /)',
    'description': """
Payobook — Effortless Payroll Solutions
=======================================
A bespoke, cinematic marketing landing page for Payobook, the multi-country
HR payroll suite. Served natively at the website root (/).

- Cinematic dark -> light long-scroll experience
- On-brand Violet Storm palette + the five in-app feature-zone accents
- GSAP + ScrollTrigger scroll choreography, Lenis smooth scroll
- Custom canvas aurora/particle hero, animated chevron logo
- PayAI section with a live Chart.js draw-in
- All copy drawn from the real Payobook modules (8 countries, import,
  people, pay runs, statutory, integrations, PayAI, analytics, formula engine)
""",
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': ['website'],
    'data': [
        'views/homepage_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            # Vendored libraries first so their globals exist before our code runs
            'pb_website/static/src/lib/gsap.min.js',
            'pb_website/static/src/lib/ScrollTrigger.min.js',
            'pb_website/static/src/lib/lenis.min.js',
            'pb_website/static/src/lib/chart.umd.min.js',
            # Our styles + behaviour
            'pb_website/static/src/scss/landing.scss',
            'pb_website/static/src/js/landing.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
