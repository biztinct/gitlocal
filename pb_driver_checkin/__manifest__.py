# -*- coding: utf-8 -*-
{
    'name': 'Payobook Driver Check-in',
    'summary': 'Driver GPS check-in PWA + manager live-map cockpit',
    'description': """
Payobook overlay on the generic geo-tracking engine. Adds a driver GPS check-in
PWA (installable, /driver), a manager Live-Map cockpit, an in_mode/out_mode 'gps'
attendance mode, and demo route simulators. Check-ins land in hr.attendance
(consumed by payroll unchanged).
""",
    # 19.0.1.5.0 — RIZE W2 D1 (ruling D16): the driver app is the FIELD
    # check-in app. New `group_pb_field_staff`, which Driver now implies; the
    # map reads the broad group transitively and says who is on leave; the
    # Field lens on Mission Control; /field.
    'version': '19.0.1.5.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'biz_geo_tracking', 'hr_attendance', 'pb_sidebar', 'pb_import_kit',
        'hr_holidays',   # who is on approved time off today, on the map rail
        'pb_hub',        # the ⌘K palette registry
    ],
    'post_init_hook': 'post_init_hook',
    'data': [
        'security/driver_security.xml',
        'security/ir.model.access.csv',
        'views/actions.xml',
        'views/driver_pwa_templates.xml',
        'data/pb_sidebar.xml',
        'data/demo_routes.xml',
    ],
    'assets': {
        # Manager cockpit (backend).
        'web.assets_backend': [
            'pb_driver_checkin/static/src/scss/driver_map.scss',
            'pb_driver_checkin/static/src/js/driver_map.js',
            'pb_driver_checkin/static/src/js/field_palette.js',
            'pb_driver_checkin/static/src/xml/driver_map.xml',
        ],
        # NOTE: the phone PWA does NOT use an Odoo asset bundle — a bundle is
        # wrapped in module-loader code that needs the `odoo` global, absent on
        # a bare page. driver_pwa_templates.xml loads the plain Leaflet lib +
        # driver_app.js/.css as direct static <script>/<link> tags instead.
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
