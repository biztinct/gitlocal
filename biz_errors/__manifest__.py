# Part of biz_errors — the branded breakdown screen.
# License LGPL-3.
{
    'name': 'Business Breakdown Screens',
    'summary': 'Calm, branded, plain-English pages for every server-rendered '
               'failure, with a support reference instead of a crash report.',
    'description': '''
Business Breakdown Screens
==========================

When a page fails, the person in front of it should meet the product, not the
platform.

This layer replaces every server-rendered error page on the public and staff
side with one design in several wordings: a brand wordmark, a line icon, a
plain-English headline, a way out, and a short support reference.

What it removes
---------------
* The Python traceback, the QWeb card and the raw error card. Nobody sees
  technical detail on screen any more, including a website designer and
  including anybody who asks for developer mode.
* The status code. It never appears on screen; it lives in the log line.
* Framework prose. Only the text of a genuine UserError — a sentence somebody
  wrote for a person — survives onto the page.

What it adds
------------
* A support reference, eight Crockford base32 characters grouped XXXX-XXXX,
  printed on the page and logged at ERROR beside the full traceback. One grep
  turns the code a customer reads out into the stack that produced it.
* The brand, read from biz_debrand.brand_name / web_debranding.new_name with no
  hard dependency on either, falling back to the company name and then to a
  neutral phrase. Never to a vendor name.

Deliberately untouched: the website 404 page, the backend error dialogs and the
developer-mode rail, each of which is already owned elsewhere.
''',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'license': 'LGPL-3',
    'author': 'Biztinct',
    'website': 'https://example.com',
    # http_routing owns the templates and the _get_error_html seam; web owns
    # web.frontend_layout, which the 4xx family keeps. Nothing else: this must
    # stay portable, so biz_debrand is read through ir.config_parameter rather
    # than imported.
    'depends': ['http_routing', 'web'],
    'data': [
        'views/error_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
