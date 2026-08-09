# -*- coding: utf-8 -*-
"""Learner state, and the event log.

The event log ships in release 1 on purpose. The measurement plan (analysis §6)
uses a *self-referential* baseline: month 1 is the reference period. If the log
slips to a later release that reference period is gone permanently, and the
system is pre-production exactly once — which is the only moment this is free.

It is deliberately thin. No free text, bounded ``detail``, no field anywhere
that could hold personal or pay data: an event log that can hold an employee's
name and their net pay eventually holds one.
"""
from odoo import api, fields, models
from odoo.exceptions import AccessError


class LearnProgress(models.Model):
    _name = 'learn.progress'
    _description = 'Learn progress'
    _order = 'write_date desc'

    user_id = fields.Many2one('res.users', required=True, index=True,
                              default=lambda self: self.env.user, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda self: self.env.company)
    # Either a station (a lesson) or a mission. Not both, never neither: the
    # two are different things a learner completes, and giving missions their
    # own table would duplicate every rule about scoping and resume.
    station_id = fields.Many2one('learn.station', index=True, ondelete='cascade')
    mission_id = fields.Many2one('learn.mission', index=True, ondelete='cascade')
    state = fields.Selection(
        selection=lambda self: self._selection_state(),
        required=True, default='not_started')
    step_index = fields.Integer(default=0)
    attempts = fields.Integer(default=0, help="Understanding-check answers submitted.")
    first_try_correct = fields.Boolean(default=False)
    completed_at = fields.Datetime()
    lang = fields.Char(help="Language the learner was reading when they finished.")

    _sql_constraints = [
        ('user_station_uniq', 'unique(user_id, station_id)',
         'One progress row per learner per station.'),
        ('user_mission_uniq', 'unique(user_id, mission_id)',
         'One progress row per learner per mission.'),
    ]

    @api.model
    def _selection_state(self):
        return [('not_started', self.env._('Not started')),
                ('in_progress', self.env._('In progress')),
                ('done', self.env._('Completed'))]

    @api.model
    def my_progress(self):
        rows = self.search([('user_id', '=', self.env.uid)])
        return {
            (r.mission_id and 'mission:' + r.mission_id.key or r.station_id.key): {
                'state': r.state,
                'step_index': r.step_index,
                'attempts': r.attempts,
                'first_try_correct': r.first_try_correct,
                'completed_at': r.completed_at and r.completed_at.isoformat() or '',
            }
            for r in rows
        }

    @api.model
    def record(self, station_key, values):
        """Upsert this user's progress for one station.

        Always writes as the calling user, never sudo: a learner updating their
        own progress is the only write path, and the record rule is what proves
        it. ``station_key`` is resolved here so the frontend never sends an id.
        """
        # "mission:<key>" addresses a mission; a bare key is a station. One
        # namespace, so the frontend's progress map has one shape.
        target, mission = None, None
        if (station_key or '').startswith('mission:'):
            mission = self.env['learn.mission'].sudo().search(
                [('key', '=', station_key[8:])], limit=1)
            if not mission:
                return False
        else:
            target = self.env['learn.station'].sudo().search(
                [('key', '=', station_key)], limit=1)
            if not target:
                return False
        allowed = {'state', 'step_index', 'attempts', 'first_try_correct',
                   'completed_at', 'lang'}
        vals = {k: v for k, v in (values or {}).items() if k in allowed}
        key_field = 'mission_id' if mission else 'station_id'
        key_value = mission.id if mission else target.id
        row = self.search([('user_id', '=', self.env.uid),
                           (key_field, '=', key_value)], limit=1)
        if row:
            row.write(vals)
        else:
            row = self.create(dict(vals, user_id=self.env.uid, **{key_field: key_value}))
        return True


class LearnEvent(models.Model):
    _name = 'learn.event'
    _description = 'Learn event'
    _order = 'occurred_at desc, id desc'

    user_id = fields.Many2one('res.users', required=True, index=True,
                              default=lambda self: self.env.user, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda self: self.env.company)
    station_id = fields.Many2one('learn.station', index=True, ondelete='set null')
    kind = fields.Selection(
        selection=lambda self: self._selection_kind(),
        required=True, index=True)
    screen = fields.Char()
    detail = fields.Char(size=64, help="Bounded. An option index, a step key, a ms bucket.")
    lang = fields.Char(size=8)
    occurred_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)

    @api.model
    def _selection_kind(self):
        # Phase 2 appends coach_*, Phase 3 appends mission_*. Kept in one
        # selection so the metrics queries in §6 never have to union tables.
        return [
            ('journey_open', self.env._('Journey opened')),
            ('station_open', self.env._('Station opened')),
            ('lesson_start', self.env._('Lesson started')),
            ('step_view', self.env._('Step viewed')),
            ('quiz_answer', self.env._('Understanding check answered')),
            ('lesson_complete', self.env._('Lesson completed')),
            ('lesson_abandon', self.env._('Lesson abandoned')),
            # Phase 2 — the Coach. coach_miss is the most valuable row in this
            # table: it is a question a real person asked that the content does
            # not answer, which is the next piece of content to write.
            ('coach_open', self.env._('Coach opened')),
            ('coach_hit', self.env._('Coach answered')),
            ('coach_miss', self.env._('Coach had no answer')),
            # Phase 3. mission_recover is the content signal here: a mission
            # nobody ever recovers from is not teaching a judgement.
            ('mission_start', self.env._('Mission started')),
            ('mission_step', self.env._('Mission step')),
            ('mission_recover', self.env._('Mission recovery shown')),
            ('mission_complete', self.env._('Mission completed')),
            ('mission_abandon', self.env._('Mission abandoned')),
        ]

    # -- append-only ------------------------------------------------------
    def write(self, vals):
        raise AccessError(self.env._("The learning event log is append-only."))

    def unlink(self):
        raise AccessError(self.env._("The learning event log is append-only."))

    @api.model
    def log(self, kind, station_key=None, screen=None, detail=None, lang=None):
        """The frontend's only write into the log.

        Unknown kinds are dropped rather than raised: a stale browser tab
        emitting a retired event name must never break a lesson the learner is
        in the middle of.
        """
        valid = {k for k, _label in self._selection_kind()}
        if kind not in valid:
            return False
        station = self.env['learn.station'].sudo().search(
            [('key', '=', station_key)], limit=1) if station_key else None
        self.create({
            'kind': kind,
            'station_id': station.id if station else False,
            'screen': (screen or '')[:64] or False,
            'detail': (str(detail) if detail is not None else '')[:64] or False,
            'lang': (lang or '')[:8] or False,
        })
        return True
