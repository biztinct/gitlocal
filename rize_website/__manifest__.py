{
    'name': 'Rize Website',
    'version': '19.0.1.2.0',
    'category': 'Website',
    'summary': 'Rize-branded public site: landing, sign-in and careers pages (tenant: rize)',
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
- Careers: the jobs list, each role page and the Hiring app's application form
  render inside the same Rize frame; an "Open roles" link sits in the top bar.
  A role still carrying the stock advert (with its stock photos) shows its
  summary instead.
- The leftover stock pages (contact us, the thank-you pages) are redrawn as
  short Rize notices, so no stock photo or placeholder contact detail is left
  on the public site.
- No external assets, no CDN: one PNG wordmark plus SCSS.
""",
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'website',
        'website_hr_recruitment',   # the /jobs pages re-framed here
        'website_project',          # its thank-you page is re-framed here
        'pb_hiring',                # the application form re-framed here
    ],
    'data': [
        'views/field_templates.xml',
        'views/frame_templates.xml',
        'views/homepage_templates.xml',
        'views/login_templates.xml',
        'views/careers_templates.xml',
        'views/pages_templates.xml',
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
