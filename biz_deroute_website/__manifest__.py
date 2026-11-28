# Part of biz_deroute — portable Odoo 19 white-label layer. License LGPL-3.
{
    'name': 'Biz Deroute — Website bridge',
    'summary': "Serve the website's backend shortcut at /bizapp, without a redirect",
    'description': """
biz_deroute cannot depend on `website`: it is an auto-installed, web-only
layer that has to stay installable on a database with no website. This bridge
carries the one frontend template that needs the branded prefix, and
auto-installs itself wherever both modules are present.

WHAT IT FIXES. Two frontend templates hand a signed-in member of staff a link
into the backend, both built against the stock prefix:

* `website.layout`'s fixed "go to the backend" shortcut
  (`o_frontend_to_backend_nav`, rendered under `groups="base.group_user"`), and
* `portal.user_dropdown`'s "Apps" entry in the account menu, which renders on
  every portal and website page — twice, for desktop and mobile.

biz_deroute 301-redirects those, so they worked — but via a redirect hop, and
the browser showed the unbranded URL on hover, in the status bar and in "Copy
link address". `deroute_dom.js` already rewrites such anchors, but it is
loaded into `web.assets_web` only: no frontend page has it.

SCOPE. `portal.user_dropdown` belongs to `portal`, so a database carrying
portal without website keeps the redirect. That combination does not exist on
this platform (website is in the tenant template), and gating this module on
portal instead would break its install wherever `website.layout` is absent.

WHY A TEMPLATE INHERIT AND NOT MORE JS. The shortcut is server-rendered QWeb,
so the href can be corrected at the source. That keeps the markup right for
hover, middle-click and copy-link, needs no MutationObserver on every public
page, and costs nothing at runtime.
""",
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'author': 'Biztinct',
    'license': 'LGPL-3',
    'depends': ['biz_deroute', 'website'],
    'data': [
        'views/frontend_backend_nav.xml',
    ],
    'auto_install': True,
    'installable': True,
}
