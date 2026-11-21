# -*- coding: utf-8 -*-
"""WDGAP QF4 — a goal sheet's score, as a pay review's score.

ONE MAPPING, TWO READERS. The pay review's "Read scores from Goals" (pb_pay,
A1) and the stamp written at year close (A2) both turn a sheet's 0–5 Float
into a whole-number score through `pay_rating()` below. Two copies of that
rounding would drift the first time somebody changed one of them, and then a
review read straight from Goals would disagree with the review that opened
already filled in from the same year.

THE RULE: ``rating = max(1, min(levels, round_half_up(score / 5 * levels)))``.

* Half-up and not Python's ``round()``: banker's rounding sends 2.5 to 2 and
  3.5 to 4, so two people half a point apart would move in opposite
  directions. Decimal arithmetic, because ``4.5 / 5 * 5`` in floats is not
  always exactly 4.5.
* A sheet that is not scored gives ``None`` and is SKIPPED by both readers —
  never written as 1. A scored sheet of 0.0 ("nothing done") is a real score
  and maps to 1, the bottom of the scale.
* A closed sheet is read from its FROZEN copy (`frozen_json`), not the live
  compute: the year as it was put away is the year a raise is given on.

pb_goals does not depend on pb_pay, and pb_pay does not depend on pb_goals.
The employee field this writes (`pb_performance_rating`, owned by pb_pay and
shared with pb_demo) is PROBED, exactly as pb_pip and pb_probation do
(`pip_case.py:857`, `probation_review.py:927`).
"""

import logging
from decimal import ROUND_HALF_UP, Decimal

from odoo import _, api, models

_logger = logging.getLogger(__name__)

#: The scale the employee record keeps (pb_pay's Selection '1'..'5').
EMPLOYEE_LEVELS = 5

#: Where the latest score lives, newest name first (as the precedents).
RATING_FIELDS = ('pb_performance_rating', 'wfp_performance_rating')


def pay_rating(score, levels):
    """A 0–5 goals score as a whole score on a 1..levels scale; None = skip."""
    if score is None or score is False:
        return None
    try:
        value = Decimal(str(float(score)))
        top = int(levels)
    except (TypeError, ValueError):
        return None
    if top < 1:
        return None
    raw = (value / Decimal(5) * Decimal(top)).quantize(
        Decimal(1), rounding=ROUND_HALF_UP)
    return max(1, min(top, int(raw)))


class PbGoalSetPayScore(models.Model):
    _inherit = 'pb.goal.set'

    # ---------------------------------------------------------- the mapping
    @api.model
    def _pay_rating_for(self, score, levels):
        return pay_rating(score, levels)

    @api.model
    def _pay_mapping(self, levels):
        """Which goals scores land on which review score, as table rows.

        Worked out by RUNNING the rule over every two-decimal score a sheet
        can hold (sheet scores are stored to 2 places), so the table can never
        say something the rule does not do.
        """
        top = int(levels or 0)
        if top < 1:
            return []
        spans = {}
        for cents in range(0, 501):
            rating = pay_rating(cents / 100.0, top)
            low, high = spans.get(rating, (cents, cents))
            spans[rating] = (min(low, cents), max(high, cents))
        rows = []
        for rating in range(1, top + 1):
            if rating not in spans:
                continue
            low, high = spans[rating]
            rows.append({
                'rating': rating,
                'from': low / 100.0,
                'to': high / 100.0,
                'label': _("%(low)s to %(high)s",
                           low='%.2f' % (low / 100.0),
                           high='%.2f' % (high / 100.0)),
            })
        return rows

    def _pay_score(self):
        """This sheet's 0–5 score for pay, or None when it has none.

        Closed: the frozen figure. Otherwise: the live score, only once every
        key result is marked (`scored`).
        """
        self.ensure_one()
        record = self.sudo()
        if record.state == 'closed':
            frozen = record.frozen()
            if 'score' in frozen:
                value = frozen.get('score')
                return None if value is None else float(value)
        if not record.scored:
            return None
        return float(record.score or 0.0)

    # --------------------------------------------------------- A2: the stamp
    def _close_for_year(self):
        was_closed = self.sudo().state == 'closed'
        res = super()._close_for_year()
        if not was_closed and self.sudo().state == 'closed':
            # Its own savepoint: a score that has nowhere to go must never
            # cost a person their year being put away.
            try:
                with self.env.cr.savepoint():
                    self._stamp_performance_score()
            except Exception:           # noqa: BLE001
                _logger.exception('pb_goals: could not stamp the performance '
                                  'score for goal sheet %s', self.id)
        return res

    def _stamp_performance_score(self):
        """The closed sheet's score onto the employee as their latest score.

        So the NEXT pay review opens already filled in (`_seed_ratings`).
        Reopening the year does not take it back.
        """
        self.ensure_one()
        value = pay_rating(self._pay_score(), EMPLOYEE_LEVELS)
        if value is None:
            return False
        emp = self.sudo().employee_id
        if not emp:
            return False
        names = [name for name in RATING_FIELDS if name in emp._fields]
        if not names:
            _logger.info('pb_goals: no performance rating field on this '
                         'build — sheet %s did not write one', self.id)
            return False
        values = {}
        for name in names:
            field = emp._fields[name]
            values[name] = str(value) if field.type == 'selection' else value
        emp.sudo().write(values)
        emp.sudo().message_post(body=_(
            "Their latest performance score is now %(value)s out of 5, from "
            "the goals year %(year)s.", value=value,
            year=self.sudo().cycle_id.name or ''))
        return True
