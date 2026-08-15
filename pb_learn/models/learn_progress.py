# -*- coding: utf-8 -*-
"""Learner state: progress, the event log, and confidence.

These three are the only learning tables left. Content moved to a static asset
in Phase 1a; what a PERSON did is irreducibly per-database, so it stays here.

The event log ships in release 1 on purpose. The measurement plan (analysis §6)
uses a *self-referential* baseline: month 1 is the reference period. If the log
slips to a later release that reference period is gone permanently, and the
system is pre-production exactly once — which is the only moment this is free.

It is deliberately thin. No free text, bounded ``detail``, no field anywhere
that could hold personal or pay data: an event log that can hold an employee's
name and their net pay eventually holds one.

WHY THE LINKS ARE KEYS AND NOT MANY2ONES
----------------------------------------
`learn.progress` used to carry `station_id` / `mission_id` and `learn.event` a
`station_id`. Those pointed at content models that no longer exist. The
replacement is the string the frontend was already using — a station key, or
`mission:<key>` — which is what `my_progress()` has always returned and what
`record()` has always been called with.

A key is weaker than a foreign key and the weakness is worth naming: nothing in
the database now stops a row referring to content that has been retired. That
is handled where it can be handled — `record()` refuses a key the content plane
does not declare — and a station that is renamed leaves an orphan row rather
than cascading a delete, which for a progress row is the better failure. The
upgrade carries the old links across (see migrations/19.0.9.0.0).
"""
from odoo import api, fields, models
from odoo.exceptions import AccessError

# The namespaces that tell a mission or a scenario key from a station key. One
# map, one shape: the frontend reads `progress[key]` and never has to know which
# kind of thing it completed.
MISSION_PREFIX = 'mission:'
# LEARNOS Phase 1b. A scenario is completed like a lesson and is not one: it
# runs over the real product or over the replica, has no understanding check,
# and the same authored steps can be taken three different ways. Namespacing it
# keeps `unique(user_id, key)` meaning what it says — one row per learner per
# thing — without a second table that would duplicate every rule about scoping.
SCENARIO_PREFIX = 'scenario:'


class LearnProgress(models.Model):
    _name = 'learn.progress'
    _description = 'Learn progress'
    _order = 'write_date desc'

    user_id = fields.Many2one('res.users', required=True, index=True,
                              default=lambda self: self.env.user, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda self: self.env.company)
    # Either a station (a lesson) or `mission:<key>`. Not both, never neither:
    # the two are different things a learner completes, and giving missions
    # their own table would duplicate every rule about scoping and resume.
    key = fields.Char(required=True, index=True,
                      help="A learn.content station key, 'mission:<key>' or "
                           "'scenario:<key>'.")
    state = fields.Selection(
        selection=lambda self: self._selection_state(),
        required=True, default='not_started')
    step_index = fields.Integer(default=0)
    attempts = fields.Integer(default=0, help="Understanding-check answers submitted.")
    first_try_correct = fields.Boolean(default=False)
    completed_at = fields.Datetime()
    lang = fields.Char(help="Language the learner was reading when they finished.")

    _sql_constraints = [
        ('user_key_uniq', 'unique(user_id, key)',
         'One progress row per learner per station or mission.'),
    ]

    @api.model
    def _selection_state(self):
        return [('not_started', self.env._('Not started')),
                ('in_progress', self.env._('In progress')),
                ('done', self.env._('Completed'))]

    @api.model
    def my_progress(self):
        return {
            r.key: {
                'state': r.state,
                'step_index': r.step_index,
                'attempts': r.attempts,
                'first_try_correct': r.first_try_correct,
                'completed_at': r.completed_at and r.completed_at.isoformat() or '',
            }
            for r in self.search([('user_id', '=', self.env.uid)])
        }

    @api.model
    def _declared(self, key):
        """True when the content plane ships this station, mission or scenario.

        The foreign key used to answer this. Asking the content directly keeps
        the same refusal — an unknown key writes nothing and returns False —
        without a table to join to.

        THE ORDER OF THE TWO PREFIX TESTS DOES NOT MATTER and the namespaces do:
        a scenario key that fell through to `content.station(key)` would be
        refused, silently, and the learner's Watch/Try/Do progress would never
        be written on any tenant — which is a failure with no error anywhere.
        """
        content = self.env['learn.content']
        if (key or '').startswith(MISSION_PREFIX):
            return bool(content.mission(key[len(MISSION_PREFIX):]))
        if (key or '').startswith(SCENARIO_PREFIX):
            return bool(content.scenario(key[len(SCENARIO_PREFIX):]))
        return bool(content.station(key))

    @api.model
    def record(self, station_key, values):
        """Upsert this user's progress for one station, mission or scenario.

        Always writes as the calling user, never sudo: a learner updating their
        own progress is the only write path, and the record rule is what proves
        it.
        """
        if not station_key or not self._declared(station_key):
            return False
        allowed = {'state', 'step_index', 'attempts', 'first_try_correct',
                   'completed_at', 'lang'}
        vals = {k: v for k, v in (values or {}).items() if k in allowed}
        row = self.search([('user_id', '=', self.env.uid),
                           ('key', '=', station_key)], limit=1)
        if row:
            row.write(vals)
        else:
            self.create(dict(vals, user_id=self.env.uid, key=station_key))
        return True


class LearnEvent(models.Model):
    _name = 'learn.event'
    _description = 'Learn event'
    _order = 'occurred_at desc, id desc'

    user_id = fields.Many2one('res.users', required=True, index=True,
                              default=lambda self: self.env.user, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda self: self.env.company)
    station_key = fields.Char(index=True, help="A learn.content station key.")
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
            # Phase C1/C2 — somebody arrived at a lesson from OUTSIDE the
            # Journey, which today means PayAI's "Show me". It is the one row
            # in this table that measures whether the retarget was worth doing,
            # and an undeclared kind is silently dropped by `log` rather than
            # stored — so the signal would have been missing without anything
            # saying so.
            ('lesson_deeplink', self.env._('Lesson opened from a deep link')),
            # LEARNOS Phase 1b — scenarios. The MODE rides in `detail`
            # (`<key>:<mode>`), because the question these rows exist to answer
            # is not "did anybody run it" but "which of the three ways do
            # people actually take, and where do they stop". An undeclared kind
            # is dropped by `log` rather than raised, so a kind that is missing
            # from this list is a signal that never arrives and never complains.
            ('scenario_start', self.env._('Scenario started')),
            ('scenario_step', self.env._('Scenario step')),
            ('scenario_complete', self.env._('Scenario completed')),
            ('scenario_abandon', self.env._('Scenario abandoned')),
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
        in the middle of. A station key that the content plane does not declare
        is dropped the same way and for the same reason — it used to resolve to
        a null Many2one.
        """
        valid = {k for k, _label in self._selection_kind()}
        if kind not in valid:
            return False
        known = bool(station_key) and bool(
            self.env['learn.content'].station(station_key))
        self.create({
            'kind': kind,
            'station_key': station_key if known else False,
            'screen': (screen or '')[:64] or False,
            'detail': (str(detail) if detail is not None else '')[:64] or False,
            'lang': (lang or '')[:8] or False,
        })
        return True


class LearnConfidence(models.Model):
    """Per-competence confidence, per learner.

    A recovery REDUCES the gain. Without that asymmetry "confidence" only
    measures completion, which the learner can already see as a tick — and a
    mission you had to be talked out of is not the same as one you got right.

    Moved here in Phase 1a from learn_mission.py, whose other four models were
    content and are gone. It is learner state, which is what this file is.
    """
    _name = 'learn.confidence'
    _description = 'Learn confidence score'
    _order = 'user_id, key'

    user_id = fields.Many2one('res.users', required=True, index=True,
                              default=lambda self: self.env.user, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda self: self.env.company)
    key = fields.Char(required=True, index=True)
    score = fields.Integer(default=0)

    _sql_constraints = [
        ('user_key_uniq', 'unique(user_id, key)', 'One score per learner per competence.'),
    ]

    @api.model
    def my_scores(self):
        return {r.key: r.score for r in self.search([('user_id', '=', self.env.uid)])}

    @api.model
    def award(self, mission_key, recovered=False):
        """Add a completed mission's gain. Halved when the learner needed a
        recovery to get there."""
        mission = self.env['learn.content'].mission(mission_key)
        if not mission or not mission.get('confidence_key'):
            return False
        gain = mission.get('confidence_gain') or 0
        if recovered:
            gain = gain // 2
        row = self.search([('user_id', '=', self.env.uid),
                           ('key', '=', mission['confidence_key'])], limit=1)
        if row:
            row.score = row.score + gain
        else:
            self.create({'key': mission['confidence_key'], 'score': gain})
        return gain
