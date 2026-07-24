# -*- coding: utf-8 -*-
{
    'name': 'Attendance Flow',
    'summary': 'Missing-punch exceptions, config-driven late rules, approved '
               'corrections, bulk import — over a branded Attendance Control cockpit',
    'description': """
Sudima Phase G — Attendance Workflow (#4 Attendance Management).

The exception/correction surface over the raw attendance + shift engines (the
Weekly-Entry grid stays the bulk-entry surface, untouched):

  * Exception engine — a read-only per-day feed of missing punch / missing
    check-out / late arrival / early departure, computed against PUBLISHED
    shifts, minus approved-trip days, minus validated leave days, minus days
    before the employee's first contract day. It consumes hr.shift.planning's
    own compliance_status (now config-driven, below); it never duplicates the
    math and NEVER writes.
  * Config-driven grace — pb.attendance.rule holds per-company grace minutes
    (in/out) and the open-checkout threshold; the shift compliance tolerance
    (previously a 15-min hardcode) reads it. DATA, not constants.
  * Correction workflow — hr.attendance.correction (create / adjust / delete a
    punch) on the generic biz_approval_chain, approved by an attendance officer
    OR the employee's own line manager, applied by ONE guarded writer under a
    module-level sentinel. The system never invents a punch: every mutation is a
    human-approved correction, and a device/kiosk punch can only be deleted
    through one.
  * Bulk import — pb.attendance.import.wizard: upload CSV/XLSX → auto-mapped
    columns → dry-run validation table → commit under PER-ROW savepoints
    (one bad row never rolls back the batch; nothing is written during validate).
  * Attendance Control cockpit — exceptions queue, corrections pipeline with the
    approval stepper, compliance KPIs, and the import stepper. HR/officer gated.

Report-only (C18.38): historical days are surfaced, never mutated.
""",
    'version': '19.0.1.0.1',
    'category': 'Human Resources/Attendance',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_hr_workforce',      # hr.shift.planning, hr.attendance rail, weekentry
        'biz_approval_chain',   # the generic state machine + stepper
        'pb_sidebar',
        'pb_import_kit',
        # soft-hooks (resolved via `in self.env`, module stays installable
        # without them): pb_business_trip (trip-day exclusion), hr_holidays
        # (validated-leave exclusion — already a pb_hr_workforce dep in practice).
    ],
    'data': [
        'security/pb_attendance_flow_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/attendance_rule_data.xml',
        'views/attendance_flow_views.xml',
        'views/attendance_flow_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_attendance_flow/static/src/scss/pb_attendance_flow.scss',
            'pb_attendance_flow/static/src/js/pbaf_icons.js',
            'pb_attendance_flow/static/src/js/pb_attendance_flow.js',
            'pb_attendance_flow/static/src/xml/pb_attendance_flow.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
