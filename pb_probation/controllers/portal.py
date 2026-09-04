# -*- coding: utf-8 -*-
"""One card on a page P3 already built.

ADDITIVE, AND THAT IS THE WHOLE DESIGN. `/my/journey` is P3's route and P3's
template; this phase has no business owning either. So the controller class
EXTENDS P3's — which is how Odoo composes controllers — calls it, and adds one
value to the context it already prepared. The template side does the same: an
`xpath` into P3's shared people block, so the card appears in BOTH states of
that page (the one with a journey running and the one without) without either
being touched.

TWO THINGS THIS FILE IS CAREFUL ABOUT.

  * **The response may not be a page.** `portal_my_journey` redirects to `/my`
    for a session with no employee record, and a redirect has no `qcontext` —
    so the addition is guarded rather than assumed. A portal page never shows a
    traceback.
  * **The key is ALWAYS set on a page that renders.** QWeb raises on a name it
    has never heard of, so `probation` reaching the template undefined would
    turn a missing card into a 500 for the whole page. Every path through here
    — including the one where something went wrong — leaves the key there,
    holding None.

WHAT THE CARD SAYS is deliberately small: where they stand, when it ends, and
what happens next. NOT who was asked about them, NOT what those colleagues
said, NOT the rating. A person reading their own probation page is entitled to
know the process and the date; four colleagues' unattributed opinions are for
the conversation with their manager, and putting them on a self-service page
would be the fastest way to make everybody stop answering honestly.
"""

import logging
from datetime import date

from odoo import _, http
from odoo.http import request

from odoo.addons.pb_onboarding.controllers.portal import PbOnboardingPortal

_logger = logging.getLogger(__name__)

#: What happens next, per state. One sentence each, in the words the person
#: would use rather than the words the model uses.
NEXT_STEP = {
    'in_probation': "Near the end, your manager will ask a few colleagues how "
                    "it has gone, and then sit down with you. Nothing is "
                    "decided before that conversation.",
    'extended': "Your trial period was extended so that you have a fair run at "
                "the things your manager talked to you about. There will be "
                "another review before the new date.",
    'passed': "Nothing more to do — your employment is confirmed.",
    'failed': "Your HR contact will go through what happens next with you.",
}

#: The tone each state carries on the chip, in the portal kit's own vocabulary.
STATE_TONE = {
    'in_probation': 'hr_review',
    'extended': 'hr_review',
    'passed': 'done',
    'failed': 'refused',
}


class PbProbationPortal(PbOnboardingPortal):

    @http.route(['/my/journey'], type='http', auth='user', website=True)
    def portal_my_journey(self, **kw):
        response = super().portal_my_journey(**kw)
        # A redirect has no qcontext. Probed rather than assumed.
        if not hasattr(response, 'qcontext'):
            return response
        card = None
        try:
            emp = self._ob_employee()
            if emp:
                card = self._probation_card(emp)
        except Exception:               # noqa: BLE001 — never break the page
            _logger.exception('pb_probation: could not add the trial period '
                              'card to /my/journey')
        response.qcontext['probation'] = card
        return response

    def _probation_card(self, emp):
        """What the card shows, or None when there is no card to show."""
        state = ''
        trial = False
        try:
            state = emp.sudo().pb_probation_state or ''
            trial = emp.sudo().trial_date_end
        except Exception:               # noqa: BLE001
            _logger.debug('pb_probation: no trial state for employee %s',
                          emp.id)
        if not state or state == 'na':
            # No card at all rather than a card that says "not applicable" — a
            # panel whose whole content is "this does not apply to you" makes a
            # page longer and says nothing.
            return None

        try:
            label = emp.sudo().pb_probation_label()
        except Exception:               # noqa: BLE001
            label = state

        review = request.env['pb.probation.review'].sudo().for_employee(emp)
        return {
            'state': state,
            'label': label,
            'tone': STATE_TONE.get(state, 'draft'),
            'trial_end': trial or False,
            'days': (trial - date.today()).days if trial else None,
            'live': state in ('in_probation', 'extended'),
            'next': _(NEXT_STEP.get(state, '')),
            # A word, never the report. See the module docstring.
            'review_running': bool(review and review.state != 'closed'),
        }
