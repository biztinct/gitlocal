# -*- coding: utf-8 -*-
"""Where the review form reaches into Goals — by inheritance only.

FOUR SEAMS, each one a method pb_goals already has:

  * `pb.goal.set._pay_score()` (QF4's one seam into pay): once a goal year has
    a form IN USE, the pay review starts from the OVERALL review result (owner
    ruling P2). A year with no form in use returns `super()` untouched — the
    golden rule, proved by test.
  * `pb.goal.set._freeze()` / `_close_for_year()`: the overall result is
    frozen with the year, and closing the year shares every finished review
    (closing tells everybody their score anyway).
  * `pb.goals._review_rows` / `_score_rows` / `_year_scores` (the Goals board
    and drawer) and `pb.my.goals._reviews` / `_scores` (My Payobook): each row
    of a form review says so, and nothing the manager wrote or scored reaches
    the EMPLOYEE before it may be shown.

"THE EMPLOYEE" MEANS THE PERSON WHOSE REVIEW IT IS, WHATEVER GROUPS THEY HOLD.
An HR lead's own review is hidden from the HR lead exactly as anybody else's
is from them.
"""

import json
import logging

from odoo import _, api, fields, models

from .rf_common import FORM_KIND

_logger = logging.getLogger(__name__)


def _hidden_scores_sentence(entry):
    if entry and entry.mgr_state == 'done':
        return entry._shown_from_words()
    return _("Your manager's marks are shared with you together with your "
             "review.")


class PbGoalReviewRF(models.Model):
    _inherit = 'pb.goal.review'

    def _rf_entry(self, create=False):
        """The filled-in form of this review, or empty.

        Made on first use, and only for an end-of-year review that is still
        open when its year's form is in use: a review written up the old way
        before the form was put in use stays the old kind of review.
        """
        self.ensure_one()
        Entry = self.env['pb.review.entry'].sudo()
        entry = Entry.search([('review_id', '=', self.id)], limit=1)
        if entry or not create:
            return entry
        record = self.sudo()
        if record.kind != FORM_KIND or record.state != 'planned':
            return Entry.browse()
        form = self.env['pb.review.form']._published_for(record.cycle_id)
        if not form:
            return Entry.browse()
        return Entry.create({'review_id': record.id, 'form_id': form.id})

    def _rf_applies(self):
        """Whether this review is (or will be) done on the year's form."""
        self.ensure_one()
        record = self.sudo()
        if record.kind != FORM_KIND:
            return False
        entry = record._rf_entry()
        if entry:
            return entry.form_id.state == 'published'
        return bool(record.state == 'planned'
                    and self.env['pb.review.form']._published_for(
                        record.cycle_id))

    def _rf_is_self(self):
        """Is the reader the person this review is about?"""
        self.ensure_one()
        return bool(self.sudo().employee_id.user_id.id == self.env.uid)


class PbGoalSetRF(models.Model):
    _inherit = 'pb.goal.set'

    def _rf_year_end_review(self):
        self.ensure_one()
        return self.env['pb.goal.review'].sudo().search(
            [('set_id', '=', self.id), ('kind', '=', FORM_KIND)], limit=1)

    def _rf_pay_basis(self):
        """('form', overall-or-None) when the year's form decides, else
        ('goals', None) — today's behaviour."""
        self.ensure_one()
        record = self.sudo()
        form = self.env['pb.review.form']._published_for(record.cycle_id)
        if not form or not record.applies_year_end:
            return 'goals', None
        review = record._rf_year_end_review()
        entry = review._rf_entry() if review else \
            self.env['pb.review.entry'].sudo().browse()
        if review and review.state == 'done' and not entry:
            # Written up the old way before the form was put in use.
            return 'goals', None
        if entry and entry.mgr_state == 'done':
            return 'form', entry._overall()
        return 'form', None

    def _rf_hidden_from_me(self):
        """True while the manager's marks must not reach this reader.

        Only the person themselves is ever kept out, only in a year whose
        form is in use with a "shown from" date, and only until their review
        is shared (or the year closes).
        """
        self.ensure_one()
        record = self.sudo()
        if record.employee_id.user_id.id != self.env.uid:
            return False
        if record.state == 'closed':
            return False
        form = self.env['pb.review.form']._published_for(record.cycle_id)
        if not form or form.reveal != 'date' or not record.applies_year_end:
            return False
        review = record._rf_year_end_review()
        entry = review._rf_entry() if review else None
        if review and review.state == 'done' and not entry:
            return False
        return not (entry and entry._may_show())

    # ------------------------------------------------------------ P2
    def _pay_score(self):
        """The overall review result once the year has a form in use.

        Closed: what was frozen with the year. Open: the live overall once the
        manager has finished, else None (skipped by the pay review, never 1).
        A year with no form in use: exactly `super()`.
        """
        self.ensure_one()
        record = self.sudo()
        if record.state == 'closed':
            frozen = record.frozen()
            if frozen.get('review_basis') == 'form':
                value = frozen.get('review_overall')
                return None if value is None else float(value)
            return super()._pay_score()
        basis, value = record._rf_pay_basis()
        if basis != 'form':
            return super()._pay_score()
        return None if value is None else float(value)

    def _freeze(self):
        raw = super()._freeze()
        try:
            basis, value = self._rf_pay_basis()
        except Exception:               # noqa: BLE001 — never block a close
            _logger.warning('pb_review_forms: could not work out the review '
                            'result for sheet %s', self.id, exc_info=True)
            return raw
        if basis != 'form':
            return raw
        data = json.loads(raw or '{}')
        review = self._rf_year_end_review()
        entry = review._rf_entry() if review else None
        data.update({
            'review_basis': 'form',
            'review_overall': value,
            'review_parts': entry._parts() if entry else [],
        })
        return json.dumps(data)

    def _close_for_year(self):
        was_closed = self.sudo().state == 'closed'
        res = super()._close_for_year()
        if not was_closed and self.sudo().state == 'closed':
            try:
                with self.env.cr.savepoint():
                    entries = self.env['pb.review.entry'].sudo().search([
                        ('set_id', '=', self.id), ('mgr_state', '=', 'done'),
                        ('released_at', '=', False)])
                    entries._release()
            except Exception:           # noqa: BLE001
                _logger.warning('pb_review_forms: could not share the '
                                'reviews of sheet %s at close', self.id,
                                exc_info=True)
        return res


class PbGoalsBoardRF(models.AbstractModel):
    """The Goals board and drawer (backend)."""

    _inherit = 'pb.goals'

    @api.model
    def _review_rows(self, sheet, today):
        rows = super()._review_rows(sheet, today)
        Review = self.env['pb.goal.review'].sudo()
        for row in rows:
            review = Review.browse(row['id'])
            if not review.exists() or not review._rf_applies():
                continue
            entry = review._rf_entry()
            is_self = review._rf_is_self()
            row['form'] = {
                'self_state': entry.self_state if entry else 'todo',
                'mgr_state': entry.mgr_state if entry else 'todo',
                'released': bool(entry and entry.released_at),
                'ack_state': entry.ack_state if entry else 'none',
                'is_self': is_self,
                'url': '/my/goals/review/%s' % review.id,
            }
            if is_self:
                if not (entry and entry._may_show()):
                    row['manager_note'] = ''
                    row['score'] = 0.0
            elif entry and entry.overall_comment:
                row['manager_note'] = entry.overall_comment
        return rows

    @api.model
    def _score_rows(self, sheet, today=None):
        out = super()._score_rows(sheet)
        if sheet.with_env(self.env)._rf_hidden_from_me():
            return _blank_scores(out, sheet)
        return out

    @api.model
    def _year_scores(self, cycle_id):
        rows = super()._year_scores(cycle_id)
        Set = self.env['pb.goal.set']
        for row in rows:
            sheet = Set.browse(row['id'])
            if sheet.exists() and sheet.with_env(self.env)._rf_hidden_from_me():
                row.update({'scored': False, 'score': 0.0, 'band': '',
                            'tone': ''})
        return rows


def _blank_scores(out, sheet):
    review = sheet._rf_year_end_review()
    entry = review._rf_entry() if review else None
    blank = dict(out)
    blank['goals'] = [dict(goal, scored=False, score=0.0, score_words='',
                           krs=[dict(kr, score='', score_word='')
                                for kr in goal.get('krs') or []])
                      for goal in out.get('goals') or []]
    blank.update({'scored': False, 'score': 0.0, 'band': '', 'tone': '',
                  'words': '', 'sentence': _hidden_scores_sentence(entry)})
    return blank


class PbMyGoalsRF(models.AbstractModel):
    """`/my/goals` — the employee's own page."""

    _inherit = 'pb.my.goals'

    @api.model
    def _reviews(self, sheet, today):
        rows = super()._reviews(sheet, today)
        Review = self.env['pb.goal.review'].sudo()
        for row in rows:
            review = Review.browse(row['id'])
            if not review.exists() or not review._rf_applies():
                continue
            entry = review._rf_entry()
            shown = bool(entry and entry._may_show())
            row['form'] = {
                'url': '/my/goals/review/%s' % review.id,
                'self_state': entry.self_state if entry else 'todo',
                'mgr_state': entry.mgr_state if entry else 'todo',
                'shown': shown,
                'ack_state': entry.ack_state if entry else 'none',
                'sentence': _my_card_sentence(entry, shown),
            }
            if not shown:
                row['manager_note'] = ''
        return rows

    @api.model
    def _scores(self, sheet):
        out = super()._scores(sheet)
        if sheet and sheet.with_env(self.env)._rf_hidden_from_me():
            review = sheet._rf_year_end_review()
            entry = review._rf_entry() if review else None
            return {'shown': False, 'closed': False, 'scored': False,
                    'sentence': _hidden_scores_sentence(entry)}
        return out


def _my_card_sentence(entry, shown):
    """What the review card on /my/goals says, whole (R117)."""
    if not entry or entry.self_state == 'todo':
        return _("Give your own view first. Your manager reads it before "
                 "they write theirs.")
    if entry.self_state == 'draft' and entry.mgr_state != 'done':
        return _("You have started your own view. Send it when it is "
                 "ready.")
    if entry.mgr_state != 'done':
        return _("Your own view is with your manager. They write their part "
                 "next.")
    if not shown:
        return _("Your manager has finished. %(when)s",
                 when=entry._shown_from_words())
    if entry.ack_state == 'none':
        return _("Your review is ready to read. Tell us when you have read "
                 "it.")
    return _("Your review is finished and filed in your documents.")
