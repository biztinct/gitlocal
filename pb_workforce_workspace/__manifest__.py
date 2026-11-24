{
    'name': 'Workforce planning workspace',
    'summary': 'One workspace for rosters, shift patterns, attendance rules and connections',
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Attendance',
    'license': 'LGPL-3',
    'depends': ['pb_mission', 'pb_shift_patterns', 'pb_clock', 'pb_settings', 'pb_form_studio'],
    'data': ['views/workspace.xml'],
    'assets': {'web.assets_backend': [
        'pb_workforce_workspace/static/src/workspace.js',
        'pb_workforce_workspace/static/src/workspace.xml',
        'pb_workforce_workspace/static/src/workspace.scss',
    ]},
    'installable': True,
}
