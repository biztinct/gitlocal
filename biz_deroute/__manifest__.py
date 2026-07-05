# Part of biz_deroute — portable Odoo 19 white-label layer. License LGPL-3.
{
    'name': 'Biz Deroute',
    'summary': 'Serve the backend web client at /bizapp instead of /odoo',
    'description': """
Rebrands the backend URL prefix: the web client lives at /bizapp, every
legacy /odoo URL is 301-redirected, and the client-side router generates
/bizapp URLs natively (address bar, history, bookmarks, deep links).

Companion of biz_debrand (cosmetic debranding). Scope is the address bar
only — asset/RPC/websocket endpoints (/web/*, /websocket) are untouched.
""",
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'author': 'Biztinct',
    'license': 'LGPL-3',
    'depends': ['web'],
    'auto_install': True,
    'installable': True,
    'assets': {
        'web.assets_web': [
            'biz_deroute/static/src/js/deroute_router.js',
            'biz_deroute/static/src/js/deroute_click.js',
            'biz_deroute/static/src/js/deroute_sw.js',
        ],
    },
}
