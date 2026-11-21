# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Rotating Shift Patterns',
    'summary': 'Rotas that repeat: set the cycle once, give each team its start, '
               'and make the next weeks as draft shifts to check and publish.',
    'description': """
WDGAP S5-C — rotating shift patterns (study item 6).

A PATTERN (`pb.shift.pattern`) is a cycle of N days (one week, two weeks, the
eight days of "4 on, 4 off", ...) anchored on a first day, with one SLOT per
day of the cycle (a shift template, or off). TEAMS (A, B, C, D ...) each start
the cycle a number of days after Team A, and MEMBERS are the people in a team,
optionally from / to a date.

"Make drafts" walks every member over N weeks and creates `hr.shift.planning`
rows in DRAFT, with the Schedule's own Copy Week checks (`_pb_check`: overlap,
approved leave, the young-worker night ban, the overtime ceiling) plus public
holidays (company closures), and returns a skip report. A preview runs the same
plan without writing. Every made shift carries a "made from pattern" mark and a
signature, so making the drafts again replaces only drafts nobody touched and
never makes a second copy; published shifts and drafts changed by hand are left
exactly as they are.

Nothing is published automatically. Nothing is created on install: no demo
data, no scheduled job, no email. Doors: a "Patterns" lens on Mission Control
(registered through `pb_mission_lens`, no edit to pb_mission), two ⌘K rows, a
"Patterns" button and a pattern mark on the Schedule (template inheritance, no
edit to pb_schedule).
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Attendance',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_schedule',      # the roster facade: _pb_check, _pb_shift_window, caches
        'pb_filter_kit',    # the shared filter panel on the patterns list
        'pb_import_kit',    # pbim tokens + the quiet board
        'pb_wf_kit',        # WfDrawer
        # NOT pb_mission: the lens joins through the `pb_mission_lens` registry
        # by its literal name (pb_mission depends on pb_schedule, so importing
        # it back is allowed by the graph but would make this module load
        # Mission Control; the string + a spelling test is the precedent).
        # NOT pb_young_worker: probed by pb_schedule's _pb_check.
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pattern_security.xml',
        'views/pattern_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_shift_patterns/static/src/scss/patterns_board.scss',
            'pb_shift_patterns/static/src/js/patterns_board.js',
            'pb_shift_patterns/static/src/js/patterns_palette.js',
            'pb_shift_patterns/static/src/js/schedule_patch.js',
            'pb_shift_patterns/static/src/xml/patterns_board.xml',
            'pb_shift_patterns/static/src/xml/schedule_patch.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
