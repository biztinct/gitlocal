# -*- coding: utf-8 -*-
"""`/my/training` — the employee's own training pages.

THE ROUTE IS THE GATE, exactly as P2, P3 and P4 established. The learner is
re-resolved from the SESSION user on every request and no route accepts a
partner or an employee id, so a crafted URL can never open somebody else's
course or mark somebody else's lesson done. The only ids a route takes are a
COURSE and a LESSON, and both are checked against the caller's own membership
inside `pb.my.training` before anything is read or written.

THIS FILE HOLDS NO RULES. It proves who is asking and it renders; every fact
on every page comes from `pb.my.training`, so the same journey a person walks
in a browser is the journey the test suite walks in Python. A controller that
knew the rules would have half of them unreachable from a test and the other
half duplicated in it.

NOTHING HERE LINKS TO THE PUBLIC COURSE SITE. Not one `/slides` href: the
content routes are used for a PDF and an image and that is the whole of it.
"""

import logging

from odoo import _, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

#: Said once, in words, so the same refusal reads the same way on four pages.
_PROBLEMS = {
    'mine': _("That course is not one of yours. If you think it should be, "
              "ask the training team to put you on it."),
    'lesson': _("That lesson is not part of this course."),
    'quiz': _("That one has questions in it — answer them and it marks "
              "itself done."),
    'denied': _("That did not save. Try again, and tell the training team if "
                "it keeps happening."),
    # The refusals `pb.my.training` answers with. IT RETURNS A CODE AND THIS
    # FILE HOLDS THE WORDS, because the alternative — putting the sentence in
    # the redirect — writes whatever is in the query string onto the page, and
    # a page that prints back what somebody put in the address bar is a page
    # somebody else can write.
    'no_test': _("This course has no test at the end of it."),
    'already_passed': _("You have already passed this test."),
    'no_attempts': _("You have used every go at this test. Ask the training "
                     "team if you need another."),
    'no_certificate': _("This test does not come with a certificate."),
    'not_passed_yet': _("The certificate is ready once you have passed the "
                        "test."),
}


def _locked_sentence(left):
    """"Finish every lesson first — 3 to go." Built here, from a number."""
    return _("Finish every lesson first — %s to go.", left)


class PbTrainingPortal(CustomerPortal):

    # --------------------------------------------------------------- helpers
    def _training(self):
        return request.env['pb.my.training']

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'training_count' in counters:
            values['training_count'] = self._training().home_count()
        return values

    # =================================================================
    #  my training
    # =================================================================
    @http.route(['/my/training'], type='http', auth='user', website=True)
    def portal_my_training(self, **kw):
        data = self._training().home()
        return request.render('pb_training.portal_my_training', {
            'page_name': 'training',
            'me': data,
            'notice': self._notice(kw.get('ok')),
            'problem': _PROBLEMS.get(kw.get('problem') or '', ''),
        })

    def _notice(self, key):
        return {
            'done': _("Marked as done."),
            'enrolled': _("You are on the course."),
        }.get(key or '', '')

    # =================================================================
    #  one course
    # =================================================================
    @http.route(['/my/training/<int:channel_id>'], type='http', auth='user',
                website=True)
    def portal_training_course(self, channel_id, **kw):
        course = self._training().course(channel_id)
        if not course:
            return request.redirect('/my/training?problem=mine')
        return request.render('pb_training.portal_training_course', {
            'page_name': 'training',
            'course': course,
            'highlight': self._int(kw.get('from')),
            'notice': self._notice(kw.get('ok')),
            'problem': self._problem(kw),
        })

    def _problem(self, kw):
        """The sentence for a refusal code, or nothing.

        Anything the query string does not match a code with is nothing at
        all — never the raw value, which is how a page ends up printing what
        somebody typed into the address bar.
        """
        code = kw.get('problem') or ''
        if code == 'locked':
            return _locked_sentence(self._int(kw.get('left')))
        return _PROBLEMS.get(code, '')

    @staticmethod
    def _int(value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    # =================================================================
    #  one lesson
    # =================================================================
    @http.route(['/my/training/<int:channel_id>/<int:slide_id>'],
                type='http', auth='user', website=True)
    def portal_training_lesson(self, channel_id, slide_id, **kw):
        lesson = self._training().lesson(channel_id, slide_id)
        if not lesson:
            return request.redirect('/my/training?problem=mine')
        return request.render('pb_training.portal_training_lesson', {
            'page_name': 'training',
            'lesson': lesson,
            'problem': _PROBLEMS.get(kw.get('problem') or '', ''),
            # The quiz result, when they have just answered one. Carried in
            # the render values and never in the URL: a wrong answer is
            # nobody's business but theirs, and a URL is copied, logged and
            # shared over somebody's shoulder. BOTH keys are always set —
            # QWeb raises on a name it has never heard of, so a key that is
            # present on one path through a controller and absent on the
            # other is a 500 on the second one.
            'result': None,
            'chosen': set(),
        })

    @http.route(['/my/training/<int:channel_id>/<int:slide_id>/done'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_training_done(self, channel_id, slide_id, **post):
        try:
            self._training().mark_done(channel_id, slide_id)
        except UserError:
            return request.redirect('/my/training/%s/%s?problem=quiz'
                                    % (channel_id, slide_id))
        except AccessError:
            return request.redirect('/my/training?problem=mine')
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: lesson %s on course %s could not be '
                            'marked done', slide_id, channel_id, exc_info=True)
            return request.redirect('/my/training/%s/%s?problem=denied'
                                    % (channel_id, slide_id))
        # STRAIGHT ON TO THE NEXT ONE, and back to the course when there is no
        # next one. A person who has just finished a lesson wants the next
        # lesson, not the page they were already on with a tick added to it.
        nxt = self._int(post.get('next_id'))
        if nxt:
            return request.redirect('/my/training/%s/%s' % (channel_id, nxt))
        return request.redirect('/my/training/%s?ok=done&from=%s'
                                % (channel_id, slide_id))

    @http.route(['/my/training/<int:channel_id>/<int:slide_id>/quiz'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_training_quiz(self, channel_id, slide_id, **post):
        """Answer a quiz lesson. Graded on the SERVER, always.

        The form posts one `q<question id>` per question holding the chosen
        answer id, and nothing else. No marking crosses the wire in either
        direction — a page that knew which answer was right would be a page a
        learner could read the answers off.
        """
        chosen = []
        for key, value in (post or {}).items():
            if not key.startswith('q'):
                continue
            chosen.append(self._int(value))
        try:
            result = self._training().answer_quiz(channel_id, slide_id, chosen)
        except AccessError:
            return request.redirect('/my/training?problem=mine')
        except UserError:
            return request.redirect('/my/training/%s/%s?problem=lesson'
                                    % (channel_id, slide_id))
        if result.get('passed'):
            nxt = self._int(post.get('next_id'))
            if nxt:
                return request.redirect('/my/training/%s/%s'
                                        % (channel_id, nxt))
            return request.redirect('/my/training/%s?ok=done&from=%s'
                                    % (channel_id, slide_id))
        # A wrong answer RE-RENDERS rather than redirecting, so the marks
        # against the questions they got wrong survive the round trip.
        lesson = self._training().lesson(channel_id, slide_id)
        if not lesson:
            return request.redirect('/my/training?problem=mine')
        return request.render('pb_training.portal_training_lesson', {
            'page_name': 'training',
            'lesson': lesson,
            'problem': '',
            'result': result,
            'chosen': set(chosen),
        })

    # =================================================================
    #  the test, and what it hands over
    # =================================================================
    @http.route(['/my/training/<int:channel_id>/test'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_training_test(self, channel_id, **post):
        answer = self._training().start_test(channel_id)
        if answer.get('url'):
            return request.redirect(answer['url'])
        if answer.get('code') == 'mine':
            return request.redirect('/my/training?problem=mine')
        if answer.get('code') == 'locked':
            return request.redirect(
                '/my/training/%s?problem=locked&left=%s'
                % (channel_id, self._int(answer.get('left'))))
        return request.redirect('/my/training/%s?problem=%s'
                                % (channel_id, answer.get('code') or 'denied'))

    @http.route(['/my/training/<int:channel_id>/certificate'], type='http',
                auth='user', website=True)
    def portal_training_certificate(self, channel_id, **kw):
        answer = self._training().certificate_url(channel_id)
        if answer.get('url'):
            return request.redirect(answer['url'])
        if answer.get('code') == 'mine':
            return request.redirect('/my/training?problem=mine')
        return request.redirect('/my/training/%s?problem=%s'
                                % (channel_id, answer.get('code') or 'denied'))
