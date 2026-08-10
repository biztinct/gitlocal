# -*- coding: utf-8 -*-
"""Practice missions.

WHERE THESE RUN, AND WHY IT MATTERS
-----------------------------------
On the practice replica, never the live screen. A mission step says "compute
the run" and another says "approve it" — driven against production those are 48
real payslips and a real approval on a real month's salaries. A practice
surface whose actions have consequences the learner did not intend is not a
practice surface.

The replica has no server behind it, so that is structural rather than a policy
we have to keep. The anchors still do their job: a step names `pw-compute`, and
that one key addresses the replica's Compute button AND the real Run Payroll
wizard, which is how the Coach can later point at the live control using the
vocabulary the mission taught.

kind='live' IS THE ONE EXCEPTION, AND IT RUNS SOMEWHERE ELSE ENTIRELY.
A live capstone validates real actions on real records and exists only in the
demo world (design_v2 §5). It does not run on the replica and it is not driven
by the Journey: `live_check` below observes what the learner did with the
PRODUCT's own controls, and models/learn_live.py — one read-only file, guarded
by a contract check — is the only place that looks. Everything in this file
that is not `live_check` still belongs to the fixture missions.

WHAT THE CONSTRAINTS ARE FOR
----------------------------
Every rule below could be an authoring convention instead. Each is a constraint
because the failure mode is silent: a wrong option with no recovery text reads
as a rejection, and nobody notices until a learner feels told off.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class LearnMission(models.Model):
    _name = 'learn.mission'
    _description = 'Learn practice mission'
    _order = 'sequence, key'

    key = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    line = fields.Selection(
        selection=lambda self: self._selection_line(), required=True, default='payrun')
    icon = fields.Char(default='flask')
    name = fields.Char(required=True, translate=True)
    summary = fields.Text(translate=True)
    duration_min = fields.Integer(default=5)
    kind = fields.Selection(
        selection=lambda self: self._selection_kind(), required=True, default='outline')
    outline_note = fields.Text(
        translate=True,
        help="Shown on an outline mission: what the full version would add.")
    screen = fields.Char(help="Practice screen the mission opens on.")
    active = fields.Boolean(default=True)

    confidence_key = fields.Char(help="Which competence this mission builds.")
    confidence_gain = fields.Integer(default=10)

    # The consequence card. Four separate fields ON PURPOSE: "what this touches ·
    # can I undo it · what to check first" is the question set a person actually
    # needs before a risky action, and separate fields stop an author writing
    # three fluent sentences and quietly omitting reversibility.
    consequence_title = fields.Char(translate=True)
    consequence_scope = fields.Text(translate=True)
    consequence_reversible = fields.Text(translate=True)
    consequence_verify = fields.Text(translate=True)

    # Exactly one seeded situation per flagship mission where the obvious answer
    # is wrong. Revealed in the debrief, AFTER the decision, so it is met as
    # judgement rather than as trivia.
    anomaly_title = fields.Char(translate=True)
    anomaly_body = fields.Text(translate=True)

    step_ids = fields.One2many('learn.mission.step', 'mission_id')
    note_ids = fields.One2many('learn.mission.note', 'mission_id')

    _sql_constraints = [('key_uniq', 'unique(key)', 'A mission key must be unique.')]

    @api.model
    def _selection_line(self):
        # Mirrors learn.station._selection_line — one vocabulary for the map
        # and the missions, so a mission cannot belong to a line the Journey
        # does not draw. tests/test_mission.py asserts the two never drift.
        return [('payrun', self.env._('Pay run line')),
                ('setup', self.env._('Setup line'))]

    @api.model
    def _selection_kind(self):
        return [('full', self.env._('Full mission')),
                ('outline', self.env._('Outline mission')),
                # Live capstones run against REAL records in the demo world
                # only — gated server-side on every check, not just hidden.
                ('live', self.env._('Live capstone (demo world only)'))]

    @api.constrains('kind', 'consequence_scope', 'anomaly_body')
    def _check_full_missions_are_complete(self):
        """A full mission without a consequence card is a practice run that
        teaches someone to act without checking — the opposite of the point.

        LIVE missions are held to the consequence card too, and more strictly in
        spirit: a fixture mission's worst outcome is a wrong answer, and a live
        one's is a real record in a world other people are looking at.

        They are NOT held to the anomaly. A seeded anomaly is a fact about a
        fixture — the same 382% overtime, every time, for every learner. Live
        data has whatever it has, and a mission that claimed otherwise would be
        asserting an amount, which is the one thing a live mission must never
        do.
        """
        for m in self:
            if m.kind not in ('full', 'live'):
                continue
            if not (m.consequence_title and m.consequence_scope
                    and m.consequence_reversible and m.consequence_verify):
                raise ValidationError(self.env._(
                    "Mission '%s' is %s but its consequence card is incomplete. "
                    "All four of title, scope, reversibility and what-to-verify "
                    "are required.", m.key, m.kind))
            if m.kind == 'full' and not m.anomaly_body:
                raise ValidationError(self.env._(
                    "Mission '%s' is full but seeds no judgement anomaly.", m.key))

    # ------------------------------------------------------- live capstones
    @api.model
    def live_check(self, mission_key, step_key):
        """Has the learner done the thing this live step asked for?

        The ONE call the live runner makes while a mission is open, and the
        only thing it can do: name a step and be told what the product's own
        records currently say. It cannot advance anything, and there is no
        method here that could — the runner instructs, the learner acts in the
        product, and this looks.

        Refuses by NAME rather than by silence in every failure mode: a live
        mission opened outside the demo world, a step that carries no check, a
        check key nothing implements. Each of those is a different mistake and
        a learner staring at a step that will not complete deserves to know
        which one they are in.
        """
        step = self.env['learn.mission.step'].sudo().search([
            ('mission_id.key', '=', mission_key), ('key', '=', step_key)], limit=1)
        if not step:
            return {'ok': False, 'note': {
                'en': "No step '%s' in mission '%s'." % (step_key, mission_key),
                'vi': "Không có bước '%s' trong nhiệm vụ '%s'." % (step_key, mission_key)}}
        if step.mission_id.kind != 'live':
            # A fixture mission has no business calling this. Its steps run on
            # a JavaScript replica with no server behind them, and the moment
            # one of them starts asking the database a question it has stopped
            # being a practice surface.
            return {'ok': False, 'note': {
                'en': "'%s' is a practice mission — it has nothing to check on the server."
                      % mission_key,
                'vi': "'%s' là nhiệm vụ thực hành — không có gì để kiểm tra trên máy chủ."
                      % mission_key}}
        if not step.check:
            return {'ok': False, 'note': {
                'en': "Step '%s' is not verified by the server." % step_key,
                'vi': "Bước '%s' không được máy chủ xác minh." % step_key}}
        return self.env['learn.live'].check(step.check)

    def _mission_dict(self):
        self.ensure_one()
        return {
            'key': self.key,
            'line': self.line,
            'icon': self.icon or 'flask',
            'name': self.name,
            'summary': self.summary or '',
            'duration_min': self.duration_min,
            'kind': self.kind,
            'outline_note': self.outline_note or '',
            'screen': self.screen or '',
            'confidence_key': self.confidence_key or '',
            'confidence_gain': self.confidence_gain,
            'consequence': {
                'title': self.consequence_title or '',
                'scope': self.consequence_scope or '',
                'reversible': self.consequence_reversible or '',
                'verify': self.consequence_verify or '',
            },
            'anomaly': {
                'title': self.anomaly_title or '',
                'body': self.anomaly_body or '',
            },
            'steps': [s._step_dict() for s in self.step_ids],
            'did': [n.body for n in self.note_ids if n.kind == 'did'],
            'check': [n.body for n in self.note_ids if n.kind == 'check'],
        }


class LearnMissionStep(models.Model):
    _name = 'learn.mission.step'
    _description = 'Learn mission step'
    _order = 'sequence, id'

    mission_id = fields.Many2one('learn.mission', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    key = fields.Char(required=True)
    nav = fields.Char(help="Practice screen this step needs.")
    target = fields.Char(help="Anchor key to highlight. Must be in anchors.json.")
    instruction = fields.Text(required=True, translate=True)
    detail = fields.Text(translate=True)
    hint = fields.Text(translate=True,
                       help="Revealed on request. Never shown unasked — a hint "
                            "offered before the learner is stuck is just the answer.")
    is_decision = fields.Boolean(default=False)
    is_consequence = fields.Boolean(
        default=False, help="Intercept: the consequence card must be acknowledged "
                            "before this step can complete.")
    is_undo = fields.Boolean(
        default=False, help="Demonstrates the reversal. Every mission ends on one "
                            "where an undo exists, so the learner has DONE it once.")

    # -- live steps (Phase B) ---------------------------------------------
    # A live step is one of exactly three things, and the runner needs to be
    # able to tell them apart without inspecting prose:
    #
    #   check    a server-side predicate answers it. The learner acts in the
    #            PRODUCT and the runner watches the record change.
    #   is_ack   nothing observable happens, so the learner confirms. Used
    #            where the instruction is "read this" or where the state the
    #            step is about belongs to somebody else's gate.
    #   neither  instructional. Next-gated, exactly like a fixture step.
    #
    # `check` is a KEY, not a domain: the predicate lives in models/learn_live.py
    # where one contract check can prove the whole registry only reads.
    check = fields.Char(
        help="Key of a learn.live predicate. The step completes when it says ok.")
    is_ack = fields.Boolean(
        default=False,
        help="The learner confirms this step themselves. For steps where no "
             "state is observable — reading a card, or watching a gate that "
             "belongs to another role.")

    option_ids = fields.One2many('learn.mission.option', 'step_id')

    @api.constrains('is_decision', 'option_ids')
    def _check_one_decision(self):
        """Interactive-editing guard only.

        The full invariant — a decision has at least two options and exactly one
        right answer — CANNOT be an ORM constraint, because a data file creates
        the step record before its option records exist and the constraint fires
        on a step that is correct but not yet populated. It lives in
        tests/test_mission.py, which sees the finished data.

        What IS safe here is the direction that is wrong at any moment in time:
        options on a step that is not a decision, and more than one right answer.
        """
        for step in self:
            if step.option_ids and not step.is_decision:
                raise ValidationError(self.env._(
                    "Step '%s' has options but is not marked as a decision.", step.key))
            if len(step.option_ids.filtered('is_correct')) > 1:
                raise ValidationError(self.env._(
                    "Decision step '%s' has more than one correct option.", step.key))

    def _step_dict(self):
        self.ensure_one()
        return {
            'key': self.key,
            'nav': self.nav or '',
            'target': self.target or '',
            'instruction': self.instruction,
            'detail': self.detail or '',
            'hint': self.hint or '',
            'is_decision': self.is_decision,
            'is_consequence': self.is_consequence,
            'is_undo': self.is_undo,
            # `check_key`, NOT `check`: the mission dict already has a `check`
            # and it is the debrief CHECKLIST — a list of prose. Marking a key
            # named `check` as structure so this one survived the bilingual zip
            # would ship the whole checklist in English, which is precisely the
            # bug _RAW_KEYS' comment warns about, one level deeper.
            'check_key': self.check or '',
            'is_ack': self.is_ack,
            'options': [o._option_dict() for o in self.option_ids],
        }


class LearnMissionOption(models.Model):
    _name = 'learn.mission.option'
    _description = 'Learn mission decision option'
    _order = 'sequence, id'

    step_id = fields.Many2one('learn.mission.step', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    key = fields.Char(required=True)
    label = fields.Text(required=True, translate=True)
    is_correct = fields.Boolean(default=False)
    recovery = fields.Text(
        translate=True,
        help="Shown when this option is chosen and it is wrong. Written as "
             "'let's rethink that', never as a rejection.")

    @api.constrains('is_correct', 'recovery')
    def _check_wrong_options_recover(self):
        """An option that can be chosen and not explained is a rejection.

        This is the brief's hardest interaction rule and the easiest one to
        lose in a hurry, so it is a constraint rather than a review note.
        """
        for opt in self:
            if not opt.is_correct and not (opt.recovery or '').strip():
                raise ValidationError(self.env._(
                    "Option '%s' is wrong but offers no recovery. A wrong choice "
                    "must always be met with a way back, never a rejection.", opt.key))

    def _option_dict(self):
        self.ensure_one()
        return {
            'key': self.key,
            'label': self.label,
            'correct': self.is_correct,
            'recovery': self.recovery or '',
        }


class LearnMissionNote(models.Model):
    _name = 'learn.mission.note'
    _description = 'Learn mission debrief note'
    _order = 'kind, sequence, id'

    mission_id = fields.Many2one('learn.mission', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    kind = fields.Selection(
        selection=lambda self: self._selection_kind(), required=True, default='did')
    body = fields.Text(required=True, translate=True)

    @api.model
    def _selection_kind(self):
        return [('did', self.env._('What you did')),
                ('check', self.env._('Before doing this for real, always check'))]


class LearnConfidence(models.Model):
    """Per-competence confidence, per learner.

    A recovery REDUCES the gain. Without that asymmetry "confidence" only
    measures completion, which the learner can already see as a tick — and a
    mission you had to be talked out of is not the same as one you got right.
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
        mission = self.env['learn.mission'].sudo().search(
            [('key', '=', mission_key)], limit=1)
        if not mission or not mission.confidence_key:
            return False
        gain = mission.confidence_gain or 0
        if recovered:
            gain = gain // 2
        row = self.search([('user_id', '=', self.env.uid),
                           ('key', '=', mission.confidence_key)], limit=1)
        if row:
            row.score = row.score + gain
        else:
            self.create({'key': mission.confidence_key, 'score': gain})
        return gain
