# -*- coding: utf-8 -*-
"""FAILING A TEST DOES NOT TAKE YOU OFF THE COURSE.

WHAT THE ENGINE DOES BY DEFAULT, and why it is right for somebody else. The
test engine's join with the content engine
(`website_slides_survey/models/survey_user.py:_check_for_failed_attempt`)
watches for an attempt that is finished, unsuccessful and out of goes — and
when it finds one it REMOVES THE PERSON FROM THE COURSE and emails them the
stock "you did not pass, enrol again" template. That is a sensible design for
a company selling certifications to the public: a candidate who has used their
three attempts buys another pool and starts again.

WHY IT IS WRONG HERE. This is an employer training an employee. The
consequences of not passing are a conversation with a manager, not an
un-enrolment — and the un-enrolment is silent and total: the course simply
disappears off the employee's own training page, taking the record of the
eleven lessons they DID finish with it, with nothing on any screen to say
where it went. It was found by the test that asks for a fourth go: the refusal
came back as "that course is not one of yours", which was true and was the
whole problem. Worse, the mail that goes with it is a template nobody here has
written, addressed to somebody who has just failed something at work.

SO THE REMOVAL IS A SWITCH, `pb_training.unenrol_on_failed_test`, OFF. Off,
the person stays on the course, their finished lessons stay finished, their
own page says "Not passed · no goes left" in words, and the training team can
see it on the board and decide what to do. On, the engine's own behaviour
comes back exactly as it was — which is what makes this a switch rather than a
deletion, and is why the test asserts it in both positions.
"""

import logging

from odoo import models

from .training_common import P_UNENROL_ON_FAIL, flag

_logger = logging.getLogger(__name__)


class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    def _check_for_failed_attempt(self):
        if flag(self.env, P_UNENROL_ON_FAIL):
            return super()._check_for_failed_attempt()
        # Named at DEBUG rather than WARNING: this is the configured
        # behaviour and not a failure, and a line per attempt at warning
        # level would bury the ones that matter. The switch is what a reader
        # looks for, and it is in the board's own note.
        _logger.debug('pb_training: a failed final attempt left the course '
                      'membership alone (pb_training.unenrol_on_failed_test '
                      'is off)')
        return False
