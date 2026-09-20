# -*- coding: utf-8 -*-
"""The door on the public course site.

WHAT THIS CLOSES. The content engine ships a PUBLIC WEB SITE: a course
catalogue at `/slides`, a page per course, a page per lesson, a member
leaderboard and a public profile per person at `/profile`. Verified on the
live box before this was written — `/slides` answers 200 to an anonymous
request today. That is the right shape for a company selling courses to the
world and the wrong shape entirely for a company training its own staff: an
employee's training is not public, and neither is the list of who is on what.

WHAT IT DOES NOT CLOSE, and this is the important half. The CONTENT routes are
untouched — `pdf_content`, `get_image`, `get_html_content`, the embed pages and
the quiz JSON — because `/my/training` renders a lesson by pointing an iframe
at them. Gating those would take the learner's own pages down. The survey
routes are untouched for the same reason: the test runs on them.

WHY AN OVERRIDE AND NOT A RECORD RULE. The question is not "what may this
person read" — the record rules already answer that correctly and a member can
legitimately read their course. The question is "which PAGE should they be
looking at", and that is a routing decision. A rule would have hidden the
content from the learner's own page too.

IT IS A SWITCH (`pb_training.stock_pages_internal_only`, on). Off, every stock
page comes back exactly as it was, which is what makes this reversible rather
than a deletion — and is why the switch is tested in both positions.
"""

import logging

from odoo.http import request
from odoo.addons.website_slides.controllers.legacy import WebsiteSlidesLegacy
from odoo.addons.website_slides.controllers.main import WebsiteSlides

from ..models.training_common import P_STOCK_PAGES, flag

_logger = logging.getLogger(__name__)


def _their_page(channel=None, channel_id=None, slide=None):
    """`/my/training/<course>` when we can tell which course, else the list.

    WHY THIS MATTERS AND IS NOT A TIDY-UP. The test engine's own result page
    ends with a "Go back to course" button, and it points at the STOCK course
    URL. Sent to the front page, a learner who has just finished a test lands
    on a list and has to find their way back to the course they were three
    seconds ago — a dead end with a scroll in it. Resolving the id turns
    somebody else's button into a correct door.

    The membership is still the proof: an id that is not a course they are on
    falls through to the list, exactly as a typed URL does.
    """
    cid = 0
    for candidate in (channel, slide and slide.channel_id):
        if candidate:
            cid = candidate.id
            break
    if not cid and channel_id:
        try:
            cid = int(channel_id)
        except (TypeError, ValueError):
            cid = 0
    if cid:
        row = request.env['slide.channel.partner'].sudo().search([
            ('channel_id', '=', cid),
            ('partner_id', '=', request.env.user.partner_id.id),
            ('member_status', '!=', 'invited'),
        ], limit=1)
        if row:
            return request.redirect('/my/training/%s' % cid)
    return request.redirect('/my/training')


def _send_away():
    """Where this visitor should be instead, or None to carry on.

    Three answers, and the difference between them matters. An INTERNAL user
    carries on — the training team writes the courses on these very pages and
    taking them away would leave nowhere to write one. An employee with a
    login is sent to their own training page, which is the same content in a
    shape that is theirs. Somebody who is not signed in at all is sent to sign
    in, because "not for you" and "we do not know who you are" are different
    sentences and only one of them has something the visitor can do about it.

    A MODULE-LEVEL FUNCTION and not a method, because the two controller
    classes below are unrelated to each other (`/slides/all` lives in a legacy
    controller of its own) and one copy of this decision is the whole point.
    """
    if not flag(request.env, P_STOCK_PAGES):
        return None
    user = request.env.user
    if user.has_group('base.group_user'):
        return None
    if user._is_public():
        return request.redirect('/web/login?redirect=/my/training')
    return request.redirect('/my/training')


class PbTrainingSlidesLegacyGate(WebsiteSlidesLegacy):
    """`/slides/all` — a retro-compatibility redirect into the catalogue.

    Gated on its own rather than left to bounce off `/slides`, so a learner
    following an old link lands on their own page in one hop instead of
    watching the address bar visit a catalogue they may not open.
    """

    def slides_channel_all(self, *args, **kwargs):
        return _send_away() or super().slides_channel_all(*args, **kwargs)


class PbTrainingSlidesGate(WebsiteSlides):
    """The five stock pages an employee could otherwise reach.

    `WebsiteSlides` itself extends `WebsiteProfile`, so the three profile
    pages are overridden from the same class — one insertion point rather than
    two controllers that could disagree with each other.

    None of these redefinitions carries an `@http.route` decorator: the
    routing is inherited unchanged from the method being overridden, so this
    file cannot accidentally widen, narrow or rename a route while adding a
    gate to it.
    """

    # ------------------------------------------------- the catalogue & course
    def slides_channel(self, *args, **kwargs):
        """`/slides`, `/slides/page/<n>`, `/slides/tag/<tags>` — the catalogue."""
        return _send_away() or super().slides_channel(*args, **kwargs)

    def channel(self, channel=False, channel_id=False, *args, **kwargs):
        """The course page, in all nine of its URL shapes.

        Unlike the catalogue this one KNOWS which course was asked for, so a
        learner who is on it lands on their own page for that course rather
        than on the list.
        """
        if _send_away():
            return _their_page(channel=channel, channel_id=channel_id)
        return super().channel(channel=channel, channel_id=channel_id,
                               *args, **kwargs)

    def slide_view(self, slide, **kwargs):
        """The lesson page. Same idea: the slide names its own course."""
        if _send_away():
            return _their_page(slide=slide)
        return super().slide_view(slide, **kwargs)

    # ------------------------------------------------------- the public people
    def view_user_profile(self, *args, **kwargs):
        """Somebody else's public profile — karma, badges, courses taken."""
        return _send_away() or super().view_user_profile(*args, **kwargs)

    def view_all_users_page(self, *args, **kwargs):
        """The leaderboard. A list of colleagues ranked by points."""
        return _send_away() or super().view_all_users_page(*args, **kwargs)

    def view_ranks_badges(self, *args, **kwargs):
        return _send_away() or super().view_ranks_badges(*args, **kwargs)
