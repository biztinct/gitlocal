# -*- coding: utf-8 -*-
{
    'name': 'Geo Tracking Engine',
    'summary': 'Generic, reusable location-ping engine (pings, live positions, trails, route simulator)',
    'description': """
Framework-agnostic geo-tracking engine. Provides an append-only ping stream, a
public tracker service (register/live/trail/GC), a PWA-shell controller mixin, a
route simulator for demos, and a thin Leaflet map wrapper. No HR / Payobook /
country dependencies — reuse for drivers, field service, delivery, sales visits.
""",
    'version': '19.0.1.0.0',
    'category': 'Extra Tools',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'biz_geo_tracking/static/lib/leaflet/leaflet.css',
            'biz_geo_tracking/static/lib/leaflet/leaflet.js',
            'biz_geo_tracking/static/src/js/geo_map.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
