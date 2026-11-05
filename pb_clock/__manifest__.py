# -*- coding: utf-8 -*-
{
    'name': 'Time Clocks',
    'summary': 'Time clocks: punches from attendance machines become attendance days',
    'description': """
Punches from fingerprint, face and card machines become paid hours with no
re-typing.

WHAT THIS MODULE ADDS

  * A PUNCH LEDGER. Every tap a machine (or a punch file) reports is kept once
    — the number on the machine, the time, the machine and how the person was
    recognised. The same tap arriving twice is kept once. Fingerprints, faces
    and photos are never stored.
  * MATCHING. The number on the machine is matched to a person: their clock
    number first, then their badge ID, then their ID number. A number nobody
    has is shown in the Time clocks lens, with a one-click assign that pairs
    everything that number punched so far.
  * PAIRING. A person's punches become work days: the first punch opens a day
    and every punch within the longest possible work day (21 hours unless the
    company changes it) belongs to it, so night shifts stay one day. First
    punch in, last punch out; taps in between are shown, not paid. Taps closer
    than two minutes count once.
  * DEVICE DATA NEVER OVERRIDES A PERSON. Pairing only ever writes the days it
    made itself. A day that is closed, a week that is with someone for
    approval, a day with a correction or a hand-typed entry is left alone and
    the punch is held, with the reason in plain words.
  * UPLOAD. The Import lens takes a punch file — Excel, CSV, the machine's own
    attendance log or the attendance program's daily sheet — into the same
    ledger, so it is paired exactly like a machine's punches.
  * THE TIME CLOCKS LENS in Time: the last punch, the machines, the numbers
    that match nobody, the punches on hold and the recent punches.

The hours then travel the road that already exists: the weekly timesheet, its
approval, and the pay run.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Attendance',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # NOT pb_close and NOT pb_timesheet_approval: the day lock and the week
    # freeze are soft-hooked (`'pb.wf.lock' in self.env`, `'pb.timesheet.freeze'
    # in self.env`) so this module installs on a database that has neither.
    'depends': [
        'pb_hr_workforce',
        'pb_attendance_flow',
        'pb_time_hub',
        'pb_import_kit',
        'pb_wf_kit',
        'pb_sidebar',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_clock_security.xml',
        'views/hr_employee_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
