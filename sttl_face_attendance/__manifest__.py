# -*- coding: utf-8 -*-

{
    'name': 'Face Recognition for HR Attendance',
    'version': '16.0.1.0',
    'summary': 'Face Recognition for HR Attendance',
    'category': 'Human Resources',
    'depends': ['hr_attendance','hr'],
    'description':
    '''
        Face Recognition for HR Attendance
    '''
,    'data': [
        'views/employee.xml',
    ],
    "author": "Silver Touch Technologies Limited",
    "website": "https://www.silvertouch.com/",
    'license': 'LGPL-3',
    'assets': {
        'web.assets_backend': [
            'sttl_face_attendance/static/src/xml/attendence.xml',
            'sttl_face_attendance/static/src/xml/capture_employee_image.xml',

            'sttl_face_attendance/static/src/css/style.css',

            'sttl_face_attendance/static/face-api/dist/face-api.js',
            'sttl_face_attendance/static/src/js/my_attendances_auto.js',
            'sttl_face_attendance/static/src/js/capture_employee_image.js',
            'sttl_face_attendance/static/src/js/kiosk_confirm_auto.js',
            'sttl_face_attendance/static/src/js/kiosk_mode_auto.js',
        ]
    },
    'installable': True,
    'application': False,
    'images': ['static/description/banner.png'],
}

