# -*- coding: utf-8 -*-
"""RECRUIT P5 — scorecards people actually fill in (G-18, G-32, ruling R4).

WHAT THIS FILE ADDS
  * `pb.hiring.scorecard` + `pb.hiring.scorecard.part`: a template per role
    family AND per discussion round. Free-text questions, star ratings, scored
    lines (1–5, the workbook's lines kept as an option) and yes/no questions.
    Every scorecard ENDS with the decision — Yes / Maybe / No / Hold — which is
    not a part, because it is never optional.
  * Five seeds per company (Recruiter review, Tech, Non-tech, Operations,
    Go-to-market). They are placeholders for the talent lead's own designs and
    are seeded once per company, keyed by `seed_key`: a talent lead's edits
    survive every upgrade.
  * Which scorecard a round uses: `pb.hiring.step.scorecard_id` (the talent
    lead's pick for that round of that role), else the role's family + the
    round, else the family's any-round card, else the company default.
  * `pb.hiring.interview.scorecard_id`: stamped when the interview is made,
    editable until the first opinion lands.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .hiring_common import (
    FINAL_KINDS, ROLE_FAMILIES, ROUND_KEYS, SCORECARD_FAMILIES,
    SCORECARD_PART_KINDS, SCORECARD_ROUNDS, as_id,
)

_logger = logging.getLogger(__name__)

#: The product's starting scorecards. PLACEHOLDERS for the client's own
#: designs (Rize: Anita's four) — the talent lead edits them in Hiring set-up.
#: (key, name, family, applies_to, is_default, intro, parts)
#: part: (kind, prompt, help, required, criterion xmlid or None)
SEEDS = [
    ('recruiter_review', 'Recruiter review', 'recruiter_review', 'phone', False,
     'A short conversation: are they who the CV says, and is it worth the '
     'panel\'s time?',
     [('text', 'How did the conversation go?',
       'Two or three sentences a hiring manager can read in ten seconds.', True, None),
      ('rating', 'Overall fit', 'Five: you would put them in front of the panel tomorrow.', True, None),
      ('text', 'Anything to check in the next round?',
       'A doubt, a gap in the CV, a number to test.', False, None)]),
    ('tech', 'Tech', 'tech', 'any_round', False,
     'Score what you saw, not what the CV says.',
     [('line', 'Skills for the role', 'Five: they have done this exact work well.', True,
       'pb_hiring.criterion_role_skills'),
      ('line', 'Problem solving', 'Five: given a problem they had never seen, they asked the right question first.',
       True, 'pb_hiring.criterion_problem_solving'),
      ('rating', 'Depth', 'Five: they went two levels deeper than you asked.', True, None),
      ('text', 'Strengths', '', False, None),
      ('text', 'Concerns', '', False, None)]),
    ('non_tech', 'Non-tech', 'non_tech', 'any_round', True,
     'One thing they did well and one thing that worried you is more use than '
     'a paragraph of adjectives.',
     [('rating', 'Communication', 'Five: a person outside their field would have followed every word.',
       True, None),
      ('rating', 'Values and ways of working',
       'Five: you would put them in a room with a difficult colleague without worrying.', True, None),
      ('text', 'Strengths', '', False, None),
      ('text', 'Concerns', '', False, None)]),
    ('operations', 'Operations', 'operations', 'any_round', False,
     'For roles in the field, on a site or on the road.',
     [('rating', 'Field readiness', 'Five: they could run a day in the field on their own next week.',
       True, None),
      ('rating', 'Judgement in scenarios', 'Five: their answer to the scenario is the one you would give.',
       True, None),
      ('text', 'What stood out', '', False, None)]),
    ('gtm', 'Go-to-market', 'gtm', 'any_round', False,
     'For sales, marketing and partnership roles.',
     [('rating', 'Commercial reasoning', 'Five: they found the money in the case without being led.',
       True, None),
      ('rating', 'Stakeholder skills', 'Five: you would send them to your hardest customer.', True, None),
      ('text', 'What stood out', '', False, None)]),
]

#: The scorecard every earlier opinion was written on (the migration).
LEGACY_KEY = 'legacy'


class PbHiringScorecard(models.Model):
    _name = 'pb.hiring.scorecard'
    _description = 'Interview scorecard'
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    family = fields.Selection(SCORECARD_FAMILIES, string='Kind of role',
                              default='other', required=True)
    applies_to = fields.Selection(SCORECARD_ROUNDS, string='Which round',
                                  default='any_round', required=True)
    intro = fields.Text(string='A line for the interviewer',
                        help='Shown at the top of the interviewer\'s page.')
    part_ids = fields.One2many('pb.hiring.scorecard.part', 'scorecard_id',
                               string='Questions', copy=True)
    active = fields.Boolean(default=True)
    is_default = fields.Boolean(
        string='Company default',
        help='Used for a round nothing else matches.')
    seed_key = fields.Char(readonly=True, copy=False, index=True,
                           help='Which product seed this started as.')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Scorecard')

    # ------------------------------------------------------------- seeds
    @api.model
    def _ensure_seeds(self):
        """Five scorecards per company, once. Idempotent by `seed_key`
        (archived ones count: a talent lead who archived the Tech card does
        not get it back on the next upgrade)."""
        Card = self.sudo().with_context(active_test=False)
        made = 0
        for company in self.env['res.company'].sudo().search([]):
            for seq, (key, name, family, applies, default, intro, parts) in enumerate(SEEDS):
                if Card.search_count([('company_id', '=', company.id), ('seed_key', '=', key)]):
                    continue
                vals = {
                    'name': name, 'company_id': company.id, 'family': family,
                    'applies_to': applies, 'intro': intro, 'seed_key': key,
                    'sequence': (seq + 1) * 10,
                    'is_default': default and not Card.search_count(
                        [('company_id', '=', company.id), ('is_default', '=', True)]),
                    'part_ids': [],
                }
                for n, (kind, prompt, help_text, required, crit) in enumerate(parts):
                    criterion = self.env.ref(crit, raise_if_not_found=False) if crit else False
                    vals['part_ids'].append((0, 0, {
                        'sequence': (n + 1) * 10, 'kind': kind, 'prompt': prompt,
                        'help': help_text or False, 'required': required,
                        'criterion_id': criterion.id if criterion else False}))
                Card.create(vals)
                made += 1
        return made

    @api.model
    def _legacy_for(self, company):
        """The (archived) scorecard every opinion given before scorecards
        existed is filed under: one scored line per criterion."""
        Card = self.sudo().with_context(active_test=False)
        card = Card.search([('company_id', '=', company.id), ('seed_key', '=', LEGACY_KEY)], limit=1)
        if card:
            return card
        crits = self.env['pb.hiring.criterion'].sudo().with_context(active_test=False).search(
            ['|', ('company_id', '=', False), ('company_id', '=', company.id)])
        return Card.create({
            'name': 'Earlier scorecard', 'company_id': company.id, 'family': 'other',
            'applies_to': 'any_round', 'seed_key': LEGACY_KEY, 'active': False,
            'sequence': 999,
            'intro': 'The five scored lines every interviewer used before scorecards.',
            'part_ids': [(0, 0, {'sequence': (n + 1) * 10, 'kind': 'line',
                                 'prompt': c.with_context(lang='en_US').name or '',
                                 'help': c.with_context(lang='en_US').help_text or False,
                                 'criterion_id': c.id})
                         for n, c in enumerate(crits)],
        })

    # --------------------------------------------------------- choosing
    @api.model
    def _resolve(self, company, family=None, round_key=None):
        """The scorecard a round uses when nobody picked one.

        A recruiter review uses the recruiter-review card. Otherwise: the
        role's family for exactly this round, then the family's any-round
        card, then the company default, then anything the company has."""
        Card = self.sudo()
        company = company or self.env.company
        base = [('company_id', '=', company.id)]
        tries = []
        if round_key == 'phone':
            tries.append([('family', '=', 'recruiter_review')])
        if family:
            if round_key:
                tries.append([('family', '=', family), ('applies_to', '=', round_key)])
            tries.append([('family', '=', family), ('applies_to', '=', 'any_round')])
            tries.append([('family', '=', family)])
        tries.append([('is_default', '=', True)])
        tries.append([('family', '!=', 'recruiter_review')])
        tries.append([])
        for extra in tries:
            hit = Card.search(base + extra, order='sequence, id', limit=1)
            if hit:
                return hit
        return Card.browse()

    def _payload(self, with_parts=True):
        self.ensure_one()
        out = {
            'id': self.id, 'name': self.name or '', 'family': self.family,
            'family_label': dict(SCORECARD_FAMILIES).get(self.family, ''),
            'applies_to': self.applies_to,
            'applies_label': dict(SCORECARD_ROUNDS).get(self.applies_to, ''),
            'intro': self.intro or '', 'is_default': bool(self.is_default),
            'active': bool(self.active), 'seeded': bool(self.seed_key),
            'n_parts': len(self.part_ids),
        }
        if with_parts:
            out['parts'] = [p._payload() for p in self.part_ids.sorted(lambda p: (p.sequence, p.id))]
        return out

    def _parts_sorted(self):
        self.ensure_one()
        return self.part_ids.sorted(lambda p: (p.sequence, p.id))


class PbHiringScorecardPart(models.Model):
    _name = 'pb.hiring.scorecard.part'
    _description = 'Scorecard question'
    _order = 'scorecard_id, sequence, id'

    scorecard_id = fields.Many2one('pb.hiring.scorecard', required=True, index=True,
                                   ondelete='cascade')
    sequence = fields.Integer(default=10)
    kind = fields.Selection(SCORECARD_PART_KINDS, string='Kind', required=True,
                            default='rating')
    prompt = fields.Char(string='Question', required=True)
    help = fields.Char(string='A line under it')
    required = fields.Boolean(string='Must be answered', default=False)
    criterion_id = fields.Many2one('pb.hiring.criterion', string='Scoring line',
                                   ondelete='set null')
    company_id = fields.Many2one('res.company', related='scorecard_id.company_id',
                                 store=True, index=True)

    def _payload(self):
        self.ensure_one()
        return {'id': self.id, 'kind': self.kind,
                'kind_label': dict(SCORECARD_PART_KINDS).get(self.kind, ''),
                'prompt': self.prompt or '', 'help': self.help or '',
                'required': bool(self.required), 'sequence': self.sequence}


# =========================================================================
#  Who uses which
# =========================================================================
class HiringStepScorecard(models.Model):
    _inherit = 'pb.hiring.step'

    scorecard_id = fields.Many2one(
        'pb.hiring.scorecard', string='Scorecard', ondelete='set null',
        help='The questions every interviewer answers after this round.')


class HiringPresetFamily(models.Model):
    _inherit = 'pb.hiring.stage.preset'

    scorecard_family = fields.Selection(
        ROLE_FAMILIES, string='Kind of role',
        help='New roles from this preset start with this kind\'s scorecards.')


class HiringRequestScorecards(models.Model):
    _inherit = 'pb.hiring.requisition'

    scorecard_family = fields.Selection(
        ROLE_FAMILIES, string='Kind of role',
        help='Decides which scorecards the rounds of this role use, unless a '
             'round names its own.')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.scorecard_family:
                preset = self.env['pb.hiring.stage.preset']._match(
                    rec.company_id, rec.department_id, rec.country_id)
                if preset and preset.scorecard_family:
                    rec.sudo().write({'scorecard_family': preset.scorecard_family})
        return records

    def _pb_round_key(self, step=None, stage_key=None, kind=None):
        """Which round a step (or a stage) is, in scorecard words."""
        key = (step.stage_id.pb_key if step and step.stage_id else '') or stage_key or ''
        if key in ROUND_KEYS:
            return key
        if (step and step.kind in FINAL_KINDS) or kind in FINAL_KINDS:
            return 'final'
        return 'any_round'

    def _pb_scorecard_for(self, step=None, stage_key=None, kind=None):
        """The scorecard a round of THIS role uses."""
        self.ensure_one()
        if step and step.scorecard_id and step.scorecard_id.active:
            return step.scorecard_id
        return self.env['pb.hiring.scorecard']._resolve(
            self.company_id, self.scorecard_family,
            self._pb_round_key(step=step, stage_key=stage_key, kind=kind))

    def _pb_rounds(self):
        """The role's rounds, for "Rounds and scorecards": every step it was
        given, then every round column the board shows that has no step."""
        self.ensure_one()
        req = self.sudo()
        rows = []
        seen = set()
        for step in req.step_ids.sorted(lambda s: (s.sequence, s.id)):
            key = step.stage_id.pb_key or ''
            if key:
                seen.add(key)
            card = req._pb_scorecard_for(step=step)
            rows.append({'step_id': step.id, 'stage_key': key, 'name': step.name or '',
                         'stage': step.stage_id.name or '', 'owner': step.owner_id.name or '',
                         'scorecard_id': card.id or False, 'scorecard': card.name or '',
                         'picked': bool(step.scorecard_id)})
        for stage in req._pb_board_stages():
            if stage.pb_key in ROUND_KEYS and stage.pb_key not in seen:
                card = req._pb_scorecard_for(stage_key=stage.pb_key)
                rows.append({'step_id': False, 'stage_key': stage.pb_key, 'name': stage.name or '',
                             'stage': stage.name or '', 'owner': '',
                             'scorecard_id': card.id or False, 'scorecard': card.name or '',
                             'picked': False})
        order = {k: i for i, k in enumerate(ROUND_KEYS)}
        rows.sort(key=lambda r: (order.get(r['stage_key'], 50), r['step_id'] or 0))
        return rows

    def _pb_round_step(self, stage_key):
        """The step for a round column, made when the talent lead first
        picks a scorecard for it (a step is what carries the choice)."""
        self.ensure_one()
        Step = self.env['pb.hiring.step'].sudo()
        stage = self.env['hr.recruitment.stage']._pb_stage(stage_key)
        if not stage:
            raise UserError(_("That round is not one of the stages."))
        step = Step.search([('requisition_id', '=', self.id), ('stage_id', '=', stage.id)], limit=1)
        if step:
            return step
        n = ROUND_KEYS.index(stage_key) if stage_key in ROUND_KEYS else 9
        return Step.create({
            'requisition_id': self.id, 'name': stage.name or stage_key,
            'sequence': (n + 1) * 10, 'kind': 'call' if stage_key == 'phone' else 'interview',
            'stage_id': stage.id})


class HiringInterviewScorecard(models.Model):
    _inherit = 'pb.hiring.interview'

    scorecard_id = fields.Many2one(
        'pb.hiring.scorecard', string='Scorecard', ondelete='set null',
        help='What every interviewer answers. Change it before the first '
             'opinion lands.')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.scorecard_id:
                card = rec._pb_default_scorecard()
                if card:
                    rec.sudo().write({'scorecard_id': card.id})
        return records

    def _pb_round_key(self):
        self.ensure_one()
        req = self.requisition_id.sudo()
        stage_key = self.applicant_id.sudo().stage_id.pb_key or ''
        return req._pb_round_key(step=self.step_id, stage_key=stage_key, kind=self.kind)

    def _pb_default_scorecard(self):
        self.ensure_one()
        req = self.requisition_id.sudo()
        if not req:
            return self.env['pb.hiring.scorecard'].browse()
        stage_key = self.applicant_id.sudo().stage_id.pb_key or ''
        if self.step_id and self.step_id.stage_id:
            stage_key = self.step_id.stage_id.pb_key or stage_key
        return req._pb_scorecard_for(step=self.step_id or None, stage_key=stage_key,
                                     kind=self.kind)

    def _pb_set_scorecard(self, card):
        """Change the scorecard: only while nobody has answered."""
        self.ensure_one()
        card = self.env['pb.hiring.scorecard'].sudo().browse(as_id(card)).exists()
        if not card:
            raise UserError(_("Pick a scorecard."))
        if self.feedback_ids.filtered(lambda f: f.state == 'submitted'):
            raise UserError(_("Somebody has already answered on the current scorecard, so it "
                              "stays. Change it on the next round."))
        self.sudo().write({'scorecard_id': card.id})
        self.feedback_ids.sudo().filtered(lambda f: f.state == 'pending').write(
            {'scorecard_id': card.id})
        return card


def seed_p5(env):
    """Called on every load (from `seed_journey`): the five scorecards for
    every company that has none of them yet."""
    env['pb.hiring.scorecard']._ensure_seeds()
    from .form_seed_i18n import PHONE_I18N
    from .forms_p2 import seed_message_i18n
    seed_message_i18n(env, 'phone', PHONE_I18N)


class HiringFeedbackLegacy(models.Model):
    _inherit = 'pb.hiring.feedback'

    @api.model
    def _pb_migrate_legacy(self):
        """RECRUIT P5 migration of the A2 opinions (idempotent):
          * an answered one gets a decision from its recommendation
            (strong yes / yes → Yes, no / strong no → No) and its five scored
            lines become answers on the company's "Earlier scorecard";
            `score_avg` comes out the same, because it is the same numbers;
          * a waiting one gets its interview's scorecard;
          * a waiting one that was chased once (A2) carries that as its first
            reminder, so the daily chase continues from there.
        Returns {converted, pointed, chased}."""
        import json
        from .hiring_common import RECOMMENDATION_DECISION
        Feedback = self.sudo().with_context(active_test=False)
        out = {'converted': 0, 'pointed': 0, 'chased': 0}
        legacy = {}
        for row in Feedback.search([('state', '=', 'submitted'), ('answers_json', '=', False)]):
            card = legacy.get(row.company_id.id)
            if card is None:
                card = legacy[row.company_id.id] = self.env['pb.hiring.scorecard']._legacy_for(row.company_id)
            by_crit = {p.criterion_id.id: p for p in card.part_ids if p.criterion_id}
            answers = []
            for r in row._ratings():
                part = by_crit.get(r.get('id'))
                answers.append({'part_id': part.id if part else False, 'kind': 'line',
                                'prompt': (part.prompt if part else r.get('name')) or '',
                                'value': r.get('score')})
            vals = {'answers_json': json.dumps(answers), 'scorecard_id': card.id}
            if not row.decision and row.recommendation:
                vals['decision'] = RECOMMENDATION_DECISION.get(row.recommendation) or False
            row.write(vals)
            if not row.interview_id.scorecard_id:
                row.interview_id.write({'scorecard_id': card.id})
            out['converted'] += 1
        for iv in self.env['pb.hiring.interview'].sudo().search([('scorecard_id', '=', False)]):
            card = iv._pb_default_scorecard()
            if card:
                iv.write({'scorecard_id': card.id})
        for row in Feedback.search([('state', '=', 'pending'), ('scorecard_id', '=', False)]):
            if row._ensure_scorecard():
                out['pointed'] += 1
        for row in Feedback.search([('state', '=', 'pending'), ('urgent_sent_at', '!=', False),
                                    ('last_reminded_at', '=', False)]):
            row.write({'reminder_count': max(1, row.reminder_count or 0),
                       'last_reminded_at': row.urgent_sent_at})
            out['chased'] += 1
        # Interviews that already ended never get the new "How did it go?"
        # mail for history: it is for the hour that just ended.
        now = fields.Datetime.now()
        Feedback.search([('ask_sent_at', '=', False), ('interview_id.stop', '<=', now)]).write(
            {'ask_sent_at': now})
        return out
