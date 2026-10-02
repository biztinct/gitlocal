# -*- coding: utf-8 -*-
"""Who a review is FAIR to, and the two moments in a year when one happens.

THE PROBLEM THIS SOLVES IS A PERSON WHO ARRIVED IN NOVEMBER. Give them the same
year-end review as somebody who was here all twelve months and the review is
about the calendar rather than about them; skip it silently and they are the
only person in the company with nothing on their record, and nobody ever tells
them why. Both are the same failure — a rule the company has, applied to a
person, without the person being told.

So applicability is COMPUTED ONCE, STAMPED ON THE SHEET, AND EXPLAINED IN A
SENTENCE THE EMPLOYEE RECEIVES. The sentence is the deliverable; the booleans
are how a screen draws it.

  * `covered_from` — the day this sheet's goals actually start covering, which
    is the LATER of the person's joining day and the day the year began.
    Everything else is measured from it.
  * `applies_mid_year` — they had been here `mid_year_min_months` whole months
    by the half-way point.
  * `applies_year_end` — they will have been here `year_end_min_months` whole
    months by the time the year ends.
  * `prorated` — they joined after the year began, so their goals cover part
    of a year and their score is about that part.

WHY IT IS STAMPED AND NOT COMPUTED LIVE. A computed answer changes when
somebody corrects a joining date in February, which would silently move a
person in or out of a review they have already been told about. The stamp is
written once, at kick-off; `restamp()` exists and is a deliberate act with a
chatter line behind it.

A REVIEW ROW IS MADE WHEN IT IS NEARLY DUE and never twelve months early
(`pb_goals.review_lead_days`, 30). A list of things to do that is full of
things due in nine months is a list nobody reads.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .checkin import months_between
from .goals_common import (
    P_CHECKIN_DAY, P_MID_YEAR_MIN_MONTHS, P_YEAR_END_MIN_MONTHS, REVIEW_KINDS,
    REVIEW_KIND_LABEL, REVIEW_STATES, REVIEW_STATE_LABEL, leg, number,
)

_logger = logging.getLogger(__name__)


class PbGoalReview(models.Model):
    _name = 'pb.goal.review'
    _description = 'Goal review'
    _order = 'due_date asc, id desc'

    _one_per_kind = models.Constraint(
        'unique(set_id, kind)',
        'That goal sheet already has a review of that kind.')

    set_id = fields.Many2one(
        'pb.goal.set', string='Goal sheet', required=True, index=True,
        ondelete='cascade')
    employee_id = fields.Many2one(
        'hr.employee', string='Whose', related='set_id.employee_id',
        store=True, index=True, readonly=True)
    manager_user_id = fields.Many2one(
        'res.users', string='Their manager', related='set_id.manager_user_id',
        store=True, index=True, readonly=True)
    manager_employee_id = fields.Many2one(
        'hr.employee', string='Manager',
        related='set_id.manager_employee_id', store=True, readonly=True)
    cycle_id = fields.Many2one(
        'pb.goal.cycle', string='Goal year', related='set_id.cycle_id',
        store=True, index=True, readonly=True)
    department_id = fields.Many2one(
        'hr.department', string='Part of the business',
        related='set_id.department_id', store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', related='set_id.company_id',
        store=True, index=True, readonly=True)

    name = fields.Char(string='Review', compute='_compute_name', store=True,
                       readonly=True)
    kind = fields.Selection(REVIEW_KINDS, string='Which one', required=True,
                            index=True)
    due_date = fields.Date(string='Due', required=True, index=True)
    state = fields.Selection(REVIEW_STATES, string='Status', default='planned',
                             required=True, index=True, copy=False)
    manager_note = fields.Text(string="The manager's write-up")
    employee_note = fields.Text(string="What the employee wanted said")
    done_at = fields.Datetime(string='Done on', readonly=True, copy=False)
    done_by_id = fields.Many2one('res.users', string='Written up by',
                                 readonly=True, copy=False)
    #: The score as it stood when the review was written up. The live score
    #: keeps moving (a manager may re-score a key result up to the close); this
    #: is what was said on the day, which is the thing a person remembers.
    score_at_review = fields.Float(string='Score at the time', readonly=True,
                                   copy=False, aggregator='avg')
    reminder_log = fields.Char(string='Reminders already sent', copy=False,
                               readonly=True, default='')

    @api.depends('employee_id', 'kind')
    def _compute_name(self):
        for record in self:
            record.name = '%s · %s' % (
                record.employee_id.sudo().name or _('Somebody'),
                REVIEW_KIND_LABEL.get(record.kind, record.kind or ''))

    def _compute_display_name(self):
        for record in self:
            record.display_name = record.name or _('Review')

    def _kind_word(self):
        self.ensure_one()
        return REVIEW_KIND_LABEL.get(self.kind, self.kind or '')

    def _state_word(self):
        self.ensure_one()
        return REVIEW_STATE_LABEL.get(self.state, self.state or '')

    # ---------------------------------------------------------------- doors
    def _may_write_up(self):
        """The manager whose review it is, or the HR team."""
        self.ensure_one()
        if self.env.user.has_group('pb_goals.group_goals_manager'):
            return True
        return bool(self.sudo().manager_user_id.id == self.env.uid)

    def action_review_done(self, manager_note=False, employee_note=False):
        """Write the review up. THE MANAGER'S WRITE-UP IS REQUIRED.

        A review marked done with nothing on it is the same tick in the same
        box as an empty check-in, and it is worse here because this is the row
        a pay conversation gets pointed at.
        """
        for record in self:
            if record.state == 'done':
                continue
            if not record._may_write_up():
                raise UserError(_(
                    "A review is written up by the person's own manager or "
                    "by the HR team."))
            written = (manager_note or '').strip()
            if not written:
                raise UserError(_(
                    "Write up what was said. A review with nothing on it is "
                    "the one row somebody will want to read next year."))
            sheet = record.sudo().set_id
            record.sudo().write({
                'state': 'done',
                'manager_note': written,
                'employee_note': (employee_note or '').strip() or False,
                'done_at': fields.Datetime.now(),
                'done_by_id': self.env.uid,
                'score_at_review': sheet.score if sheet.scored else 0.0,
            })
            leg(self.env, 'the review note on sheet %s' % sheet.id,
                lambda rec=record, sh=sheet: sh.message_post(body=_(
                    "%(who)s wrote up the %(kind)s.",
                    who=self.env.user.name or '', kind=rec._kind_word())))
        return True

    # ------------------------------------------------------------ the chase
    def _already_nudged(self, key):
        self.ensure_one()
        return key in (self.reminder_log or '').split(',')

    def _remember_nudge(self, key):
        self.ensure_one()
        keys = [k for k in (self.reminder_log or '').split(',') if k]
        if key not in keys:
            keys.append(key)
        self.sudo().write({'reminder_log': ','.join(keys[-12:])})
        return True

    def _nudge(self, key):
        """One reminder to the manager, remembered so it goes once.

        THE MANAGER AND NOT BOTH SIDES, unlike a check-in: writing a review up
        is the manager's job, and chasing an employee about a piece of work
        somebody else owes them is how a process gets a reputation.
        """
        self.ensure_one()
        if self._already_nudged(key):
            return False
        record = self.sudo()
        manager = record.manager_user_id
        address = manager.email or manager.partner_id.email or ''
        sent = False
        template = self.env.ref('pb_goals.mail_goals_review_due',
                                raise_if_not_found=False)
        if template and address:
            values = {'email_to': address}
            sender = record.set_id._sender()
            if sender:
                values['email_from'] = sender
            template.sudo().send_mail(self.id, force_send=False,
                                      email_values=values)
            sent = True
        self._remember_nudge(key)
        return sent

    def action_view_set(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Goal sheet'),
            'res_model': 'pb.goal.set',
            'res_id': self.set_id.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }


class PbGoalCycleReviewRules(models.Model):
    """The two dials a company may want different from ours, on the year."""

    _inherit = 'pb.goal.cycle'

    mid_year_min_months = fields.Integer(
        string='Months here before a half-way review',
        default=lambda self: number(self.env, P_MID_YEAR_MIN_MONTHS, 3),
        help='Somebody who has been here fewer months than this when the '
             'half-way point arrives is not given a half-way review, and is '
             'told why.')
    year_end_min_months = fields.Integer(
        string='Months here before an end-of-year score',
        default=lambda self: number(self.env, P_YEAR_END_MIN_MONTHS, 3),
        help='Somebody who will have been here fewer months than this when '
             'the year ends is not scored this year. Their goals carry on '
             'into the next year instead, and they are told why.')
    checkin_day = fields.Integer(
        string='Day of the month for check-ins',
        default=lambda self: min(28, max(1, number(
            self.env, P_CHECKIN_DAY, 25))),
        help='The day each month the monthly conversation is planned for. '
             'Capped at the 28th so it falls on the same day every month.')
    band_ids = fields.One2many(
        'pb.goal.band', 'cycle_id', string='Score bands',
        help='Leave this empty to use the bands everybody else uses. Fill it '
             'in only if this year is scored differently.')

    def _bands(self):
        """This year's bands, or the ones everybody uses.

        A CYCLE WITH NO BANDS OF ITS OWN IS THE ORDINARY CASE and falls back to
        the shipped, company-less table rather than to nothing — a year with no
        bands would score everybody and then have no word for any of them.
        """
        self.ensure_one()
        own = self.sudo().band_ids
        if own:
            return own.sorted(lambda b: -b.min_score)
        shared = self.env['pb.goal.band'].sudo().search([
            ('cycle_id', '=', False),
            '|', ('company_id', '=', False),
            ('company_id', '=', self.company_id.id),
        ])
        return shared.sorted(lambda b: -b.min_score)

    def _min_months(self, key):
        self.ensure_one()
        if key == 'mid_year':
            return max(0, self.mid_year_min_months or 0)
        return max(0, self.year_end_min_months or 0)


class PbGoalSetApplicability(models.Model):
    """Which reviews this person's year actually gets, and why."""

    _inherit = 'pb.goal.set'

    covered_from = fields.Date(
        string='Their goals cover from', readonly=True,
        help='The later of the day they joined and the day the goal year '
             'began. Everything about half-way and end-of-year reviews is '
             'measured from this day.')
    applies_mid_year = fields.Boolean(
        string='Has a half-way review', readonly=True, default=True)
    applies_year_end = fields.Boolean(
        string='Is scored at the end of the year', readonly=True,
        default=True)
    prorated = fields.Boolean(
        string='Part of a year', readonly=True, default=False,
        help='Ticked when somebody joined after the goal year began, so '
             'their goals cover part of it.')
    applicability_note = fields.Text(
        string='What they were told about reviews', readonly=True,
        help='The sentence the employee was sent, in the words they read it '
             'in. Kept so nobody has to reconstruct it from the rules.')
    applicability_set = fields.Boolean(string='Reviews worked out',
                                       readonly=True, default=False,
                                       copy=False)
    review_ids = fields.One2many('pb.goal.review', 'set_id',
                                 string='Reviews')
    checkin_ids = fields.One2many('pb.goal.checkin', 'set_id',
                                  string='Check-ins')

    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # STAMPED AT THE MOMENT THE SHEET IS MADE, which is the only moment
        # everything it needs is known and nothing has been told to anybody
        # yet. Guarded: a sheet that exists and an applicability that could
        # not be worked out is a small problem; a sheet that could not be
        # created is a person with no goals.
        for record in records:
            leg(record.env, 'working out reviews for sheet %s' % record.id,
                lambda rec=record: rec._stamp_applicability())
        return records

    def _stamp_applicability(self, force=False):
        """Work out which reviews this person gets, once, and write it down."""
        self.ensure_one()
        record = self.sudo()
        if record.applicability_set and not force:
            return False
        cycle = record.cycle_id
        if not cycle or not cycle.date_start or not cycle.date_end:
            return False
        joined = record.joined_on or record._join_date(record.employee_id.id)
        start = cycle.date_start
        covered = max(joined, start) if joined else start
        prorated = bool(joined and joined > start)

        mid = cycle.mid_year_date
        mid_min = cycle._min_months('mid_year')
        end_min = cycle._min_months('year_end')
        # STRICTLY AFTER THE DAY THEY START COVERING. Somebody who joined the
        # day after the half-way point has no half-way point to be reviewed
        # at, whatever the minimum says.
        if not mid or covered > mid:
            applies_mid = False
        else:
            applies_mid = months_between(covered, mid) >= mid_min
        applies_end = months_between(covered, cycle.date_end) >= end_min

        record.write({
            'joined_on': joined or False,
            'covered_from': covered,
            'prorated': prorated,
            'applies_mid_year': applies_mid,
            'applies_year_end': applies_end,
            'applicability_set': True,
            'applicability_note': record._applicability_sentence(
                cycle, covered, prorated, applies_mid, applies_end),
        })
        return True

    def restamp_applicability(self):
        """Work it out again — a deliberate act, with a line on the record."""
        for record in self:
            before = (record.applies_mid_year, record.applies_year_end,
                      record.prorated)
            record._stamp_applicability(force=True)
            after = (record.applies_mid_year, record.applies_year_end,
                     record.prorated)
            if before != after:
                record.sudo().message_post(body=_(
                    "The reviews on this sheet were worked out again. "
                    "%s", record.applicability_note or ''))
        return True

    def _applicability_sentence(self, cycle, covered, prorated, applies_mid,
                                applies_end):
        """THE SENTENCE IS THE DELIVERABLE, and it is written whole (R117).

        Not a frame with holes in it: every branch is a complete sentence, so
        a translator gets something they can actually translate and nobody
        ever reads "You does not have a half-way review".
        """
        self.ensure_one()
        year = cycle.name or _('this year')
        joined_word = covered and covered.strftime('%B %Y') or ''
        ends = cycle.date_end and cycle.date_end.strftime('%B %Y') or ''
        if not prorated and applies_mid and applies_end:
            return _(
                "Your goals cover the whole of %(year)s. You have a half-way "
                "review and an end-of-year score, and a check-in with your "
                "manager every month in between.", year=year)
        if prorated and applies_mid and applies_end:
            return _(
                "You started part-way through %(year)s, in %(joined)s, so "
                "your goals cover from then. You still have a half-way "
                "review, an end-of-year score and a check-in every month — "
                "and the score is about the part of the year you were here "
                "for.", year=year, joined=joined_word)
        if applies_end and not applies_mid:
            return _(
                "You started in %(joined)s, which is too close to the "
                "half-way point of %(year)s for a half-way review to say "
                "anything useful. You do get an end-of-year score, and a "
                "check-in with your manager every month until then.",
                joined=joined_word, year=year)
        if not applies_end:
            return _(
                "You started in %(joined)s and %(year)s ends in %(ends)s, so "
                "there is not enough of the year left to score you on it. "
                "Your goals carry into next year and are scored at the end of "
                "that one instead. Your monthly check-ins still happen, and "
                "they are what next year's review is built on.",
                joined=joined_word, year=year, ends=ends)
        return _(
            "Your goals cover %(year)s from %(joined)s. Your monthly "
            "check-ins happen as usual.", year=year, joined=joined_word)

    # ---------------------------------------------------- making the reviews
    def _ensure_review(self, kind, due):
        """One review row of one kind on one sheet. Idempotent."""
        self.ensure_one()
        Review = self.env['pb.goal.review'].sudo()
        existing = Review.search(
            [('set_id', '=', self.id), ('kind', '=', kind)], limit=1)
        if existing:
            return existing
        return Review.create({'set_id': self.id, 'kind': kind,
                              'due_date': due})

    def _review_due_dates(self):
        """When each review this sheet gets falls due."""
        self.ensure_one()
        cycle = self.sudo().cycle_id
        out = {}
        if self.applies_mid_year and cycle.mid_year_date:
            out['mid_year'] = cycle.mid_year_date
        if self.applies_year_end and cycle.date_end:
            out['year_end'] = cycle.date_end
        return out


class PbGoalBand(models.Model):
    """What a number out of five is CALLED.

    A score of 3.6 tells a person nothing on its own; "Strong" tells them
    something, and the two together tell them everything. The table is shipped
    company-less so every company has one from the first day, and a year that
    wants different words fills in its own.

    THE BANDS ARE A CATALOGUE AND NOT A CALCULATION. Nothing here decides what
    somebody scored; it decides what the number is called, which is a thing a
    business is entitled to have an opinion about.
    """

    _name = 'pb.goal.band'
    _description = 'Score band'
    #: Highest first, because that is the order a band table is read in.
    _order = 'min_score desc, id'

    name = fields.Char(string='What it is called', required=True,
                       translate=True)
    min_score = fields.Float(string='From', required=True, default=0.0,
                             help='Scores at or above this number.')
    max_score = fields.Float(string='Up to', required=True, default=5.0,
                             help='Scores below this number. The top band '
                                  'includes its own top figure.')
    description = fields.Char(string='What it means')
    tone = fields.Selection(
        [('good', 'Good'), ('ok', 'Fine'), ('warn', 'Worth a look'),
         ('bad', 'Needs attention')], string='How it is shown',
        default='ok', required=True)
    cycle_id = fields.Many2one(
        'pb.goal.cycle', string='Only for this goal year',
        ondelete='cascade', index=True,
        help='Leave empty for the bands every goal year uses.')
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        help='Leave empty to use these bands in every company.')
    sequence = fields.Integer(default=10)

    def _compute_display_name(self):
        for band in self:
            band.display_name = band.name or _('Band')

    def holds(self, score):
        """Whether a score reaches this band.

        ONLY THE FLOOR IS ASKED, and the caller walks the bands HIGHEST FIRST
        (`pb.goal.cycle._bands()` sorts them that way), so the first band a
        score reaches is its band. Asking both ends of every band is how a
        table with a gap in it — 3.5 to 4.49 and 4.5 upwards, typed by a
        person — leaves a score of 4.495 with no word at all, and the screen
        then shows a number beside an empty space with nothing to explain it.
        `max_score` is kept because it is what makes the table readable to
        the person editing it.
        """
        self.ensure_one()
        return float(score or 0.0) >= self.min_score

    def words(self):
        self.ensure_one()
        return self.name or ''
