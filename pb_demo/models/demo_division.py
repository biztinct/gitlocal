# -*- coding: utf-8 -*-
"""One division per demo user.

THE PROBLEM THIS SOLVES
-----------------------
The demo world is SHARED. Every prospect who signs up lands in the same
'Payobook Vietnam JSC' company, and the live capstone mission asks them to
compute and submit June 2026 for real. Without an assignment they would all
reach for the same run: the second person finds it already submitted, the third
finds it approved, and the climax of the demo is somebody else's finished work.

Six divisions exist and the generator already builds a full formula
configuration, a headcount and an open June run for each. Handing each signup
one of them costs one Char field and gives every prospect their own run to
drive end to end.

ROUND ROBIN, OVER THE ASSIGNMENTS THEMSELVES
--------------------------------------------
The next division is chosen from how many users already hold one, not from a
sequence and not from a count of group members. That keeps it to a single
indexed search, makes the assignment deterministic in tests, and means the lazy
back-fill of an older demo user uses exactly the same rule as a fresh signup —
there is one code path, so there is one behaviour.
"""
from odoo import api, fields, models

from . import demo_catalog as cat

# The order is DIVISIONS' own, so the first six signups walk the catalogue in
# the order a reader of demo_catalog.py would expect.
DIVISION_KEYS = list(cat.DIVISIONS)


class ResUsers(models.Model):
    _inherit = 'res.users'

    pb_demo_division = fields.Char(
        string='Demo division',
        index=True,
        copy=False,
        help="Which of the six demo divisions this user's live capstone mission "
             "runs against. Set at signup and never changed: the prospect's own "
             "June run is the one thing in the shared demo world that is theirs.")

    # -- assignment -------------------------------------------------------
    @api.model
    def _pb_next_demo_division(self):
        """The next key in the rotation.

        Counted with sudo because a demo user may not read other users, and the
        answer must be the same whoever asks — an assignment that depended on
        the reader's access rights would hand two prospects the same division.
        """
        held = self.sudo().search_count([('pb_demo_division', '!=', False)])
        return DIVISION_KEYS[held % len(DIVISION_KEYS)]

    def _pb_ensure_demo_division(self):
        """Assign one if this user has none. Returns the key.

        Called at signup (pb_demo_portal) and lazily on first read, so demo
        users created before this field existed get one the first time the
        capstone looks — rather than being permanently excluded by an upgrade
        they had no part in.
        """
        self.ensure_one()
        if self.pb_demo_division:
            return self.pb_demo_division
        key = self._pb_next_demo_division()
        self.sudo().write({'pb_demo_division': key})
        return key

    def _pb_demo_division_label(self):
        """The assigned division's display name, in the context language."""
        self.ensure_one()
        spec = cat.DIVISIONS.get(self.pb_demo_division or '')
        if not spec:
            return ''
        lang = (self.env.context.get('lang') or self.env.user.lang or 'en_US')
        return spec['name_vi'] if lang.startswith('vi') else spec['name_en']
