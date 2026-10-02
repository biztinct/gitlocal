# Part of biz_deroute — portable Odoo 19 white-label layer. License LGPL-3.
{
    'name': 'Biz Deroute',
    'summary': 'Serve the backend web client at /bizapp instead of the stock backend prefix',
    'description': """
Rebrands the backend URL prefix: the web client lives at /bizapp, every
legacy backend URL is 301-redirected, and the client-side router generates
/bizapp URLs natively (address bar, history, bookmarks, deep links).

Companion of biz_debrand (cosmetic debranding). URL scope is the address bar
only — asset/RPC/websocket endpoints (/web/*, /websocket) are untouched.

This module also owns the backend web-client ENTRY POINT (it overrides
`Home.web_client`), so the defensive guards that keep that entry point from
answering 500 live here too: see `models/ir_http_session_guard.py`, which
repairs the `hr_timesheet` multi-company `session_info` KeyError (W100).
""",
    'version': '19.0.1.1.1',
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
            'biz_deroute/static/src/js/deroute_dom.js',
        ],
    },
}
