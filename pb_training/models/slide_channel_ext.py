# -*- coding: utf-8 -*-
"""What a course and a lesson mean to Payobook.

NO FIELD IS ADDED TO EITHER MODEL and no stored value is changed. Everything
here is a READ that both facades and the portal controller need to agree on,
written down once so the learner's page and the training team's board can
never answer the same question differently.

THE ONE RULE THAT EVERYTHING ELSE HANGS OFF: a course's LESSONS are its
published, active, non-category slides MINUS the certification slide. The
certification slide is the test at the end; counting it among the lessons
would mean the test unlocks only once the test has been passed, which is a
door that can never open. Every "how many are left", every progress bar and
the gate on the test itself go through `_pb_lessons()` so there is exactly one
answer to that question in the product.
"""

import logging

from odoo import api, models

from .training_common import LESSON_ICONS, LESSON_KINDS, TEST_CATEGORY

_logger = logging.getLogger(__name__)


class SlideChannel(models.Model):
    _inherit = 'slide.channel'

    # ---------------------------------------------------------- the content
    def _pb_lessons(self):
        """The slides a learner has to get through, in the order they are in.

        Sorted by the model's own `_order` (`sequence asc, is_category asc,
        id asc`), which is the order the training team dragged them into.
        """
        self.ensure_one()
        return self.sudo().slide_ids.filtered(
            lambda s: s.active and s.is_published and not s.is_category
            and s.slide_category != TEST_CATEGORY
        ).sorted(lambda s: (s.sequence, s.id))

    def _pb_test_slide(self):
        """The certification slide, or an empty recordset.

        A course may have none — a company that only wants people to watch
        something is a real case and must not be told its course is broken.
        Two would be a mistake somebody made in the editor; the FIRST is
        taken, because refusing to draw the page over it would hide the
        course rather than the mistake.
        """
        self.ensure_one()
        found = self.sudo().slide_ids.filtered(
            lambda s: s.active and s.is_published
            and s.slide_category == TEST_CATEGORY and s.survey_id
        ).sorted(lambda s: (s.sequence, s.id))
        return found[:1]

    def _pb_membership(self, partner):
        """This person's row on this course, or an empty recordset.

        Read under sudo on purpose: the caller has already proved whose
        partner this is (the portal routes resolve it from the session and
        never from the URL), and a portal user cannot read
        `slide.channel.partner` in their own right.
        """
        self.ensure_one()
        if not partner:
            return self.env['slide.channel.partner'].sudo().browse()
        return self.env['slide.channel.partner'].sudo().search([
            ('channel_id', '=', self.id),
            ('partner_id', '=', partner.id),
        ], limit=1)

    # -------------------------------------------------------- the progress
    def _pb_done_ids(self, partner):
        """The ids of the slides this person has finished on this course."""
        self.ensure_one()
        if not partner:
            return set()
        rows = self.env['slide.slide.partner'].sudo().search([
            ('channel_id', '=', self.id),
            ('partner_id', '=', partner.id),
            ('completed', '=', True),
        ])
        return set(rows.mapped('slide_id').ids)

    def _pb_lessons_left(self, partner):
        """How many lessons are still to do. The gate on the test."""
        self.ensure_one()
        done = self._pb_done_ids(partner)
        return len([s for s in self._pb_lessons() if s.id not in done])


class SlideSlide(models.Model):
    _inherit = 'slide.slide'

    @api.model
    def _pb_kind_word(self, category):
        """What a lesson is, in the word a person would use for it."""
        return LESSON_KINDS.get(category or '', 'Lesson')

    @api.model
    def _pb_kind_icon(self, category):
        return LESSON_ICONS.get(category or '', 'fileText')

    def _pb_is_quiz(self):
        """A lesson a person ANSWERS rather than reads.

        Two different things are true of a quiz lesson and only one of them is
        the category: a Video with three questions attached is answered too.
        The content engine says the same thing through
        `can_self_mark_completed`, which is False exactly when there are
        questions — so this is that rule, said out loud where the page can
        read it.
        """
        self.ensure_one()
        return bool(self.sudo().question_ids)
