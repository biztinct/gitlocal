{
    'name': 'Rize Website',
    'version': '19.0.1.0.0',
    'category': 'Website',
    'summary': 'Rize-branded landing page and sign-in page (tenant: rize)',
    'description': """
Rize — landing page + sign-in page
==================================
Tenant-only branding for rize.payobook.com. Install on the `rize` database
ONLY; it must not be part of the standard tenant module set.

- Landing page at / (inherits website.homepage): dawn rice-field backdrop drawn
  in SVG, Rize gold wordmark, one hero statement, three short cards, sign-in CTA.
- Sign-in page at /web/login: same backdrop behind a glass card. Odoo's own form
  markup is re-emitted untouched (CSRF token, OAuth block, reset-password link)
  and only re-skinned.
- Palette sampled from rize.farm: paddy green #192D06, harvest gold #CC9900,
  husk cream #FAEED3.
- No external assets, no CDN: one PNG wordmark plus SCSS.
""",
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': ['website'],
    'data': [
        'views/field_templates.xml',
        'views/homepage_templates.xml',
        'views/login_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'rize_website/static/src/scss/rize.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
