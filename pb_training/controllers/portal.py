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
    # E2
    'no_team': _("You do not manage anybody, so there is no team page to "
                 "show."),
    'delay': _("That request could not be sent. Try again, and tell the "
               "training team if it keeps happening."),
}


def _locked_sentence(left):
    """"Finish every lesson first — 3 to go." Built here, from a number."""
    return _("Finish every lesson first — %s to go.", left)


class PbTrainingPortal(CustomerPortal):
    """EVERY HELPER HERE IS MODULE-PREFIXED, and that is not a style choice.

    ALL `CustomerPortal` SUBCLASSES MERGE INTO ONE CLASS. A helper called
    `_notice` here and `_notice` in `pb_rnr` are the same attribute on the same
    class, and whichever module loads last silently wins — so E1's "Marked as
    done." confirmation never once appeared on a live page, because the praise
    module's `_notice` was answering instead and had never heard of the key.
    Worse in the other direction: E1's `_problem(self, kw)` took the name
    `pb_offboarding` uses for `_problem(message)`, so a resignation that failed
    called our method with a string and died on `kw.get`.

    Nothing about either is visible at runtime. `pb_rnr` learnt it the same way
    (its `_rnr_card` docstring records the `_card` clash that took three portal
    pages down) and the rule it wrote down is this one: on a portal controller,
    a private helper carries the module's own prefix.
    """

    # --------------------------------------------------------------- helpers
    def _tr_facade(self):
        return request.env['pb.my.training']

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'training_count' in counters:
            values['training_count'] = self._tr_facade().home_count()
        if 'training_team_count' in counters:
            values['training_team_count'] = \
                self._tr_facade().team_overdue_count()
        return values

    # =================================================================
    #  my training
    # =================================================================
    @http.route(['/my/training'], type='http', auth='user', website=True)
    def portal_my_training(self, **kw):
        data = self._tr_facade().home()
        return request.render('pb_training.portal_my_training', {
            'page_name': 'training',
            'me': data,
            'notice': self._tr_notice(kw.get('ok')),
            'problem': _PROBLEMS.get(kw.get('problem') or '', ''),
        })

    def _tr_notice(self, key):
        return {
            'done': _("Marked as done."),
            'enrolled': _("You are on the course."),
            # E2
            'asked': _("Asked. Your manager will see it and you will get an "
                       "email either way."),
        }.get(key or '', '')

    # =================================================================
    #  one course
    # =================================================================
    @http.route(['/my/training/<int:channel_id>'], type='http', auth='user',
                website=True)
    def portal_training_course(self, channel_id, **kw):
        course = self._tr_facade().course(channel_id)
        if not course:
            return request.redirect('/my/training?problem=mine')
        return request.render('pb_training.portal_training_course', {
            'page_name': 'training',
            'course': course,
            'highlight': self._tr_int(kw.get('from')),
            'notice': self._tr_notice(kw.get('ok')),
            'problem': self._tr_problem(kw),
        })

    def _tr_problem(self, kw):
        """The sentence for a refusal code, or nothing.

        Anything the query string does not match a code with is nothing at
        all — never the raw value, which is how a page ends up printing what
        somebody typed into the address bar.
        """
        code = kw.get('problem') or ''
        if code == 'locked':
            return _locked_sentence(self._tr_int(kw.get('left')))
        return _PROBLEMS.get(code, '')

    @staticmethod
    def _tr_int(value):
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
        lesson = self._tr_facade().lesson(channel_id, slide_id)
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
            self._tr_facade().mark_done(channel_id, slide_id)
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
        nxt = self._tr_int(post.get('next_id'))
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
            chosen.append(self._tr_int(value))
        try:
            result = self._tr_facade().answer_quiz(channel_id, slide_id, chosen)
        except AccessError:
            return request.redirect('/my/training?problem=mine')
        except UserError:
            return request.redirect('/my/training/%s/%s?problem=lesson'
                                    % (channel_id, slide_id))
        if result.get('passed'):
            nxt = self._tr_int(post.get('next_id'))
            if nxt:
                return request.redirect('/my/training/%s/%s'
                                        % (channel_id, nxt))
            return request.redirect('/my/training/%s?ok=done&from=%s'
                                    % (channel_id, slide_id))
        # A wrong answer RE-RENDERS rather than redirecting, so the marks
        # against the questions they got wrong survive the round trip.
        lesson = self._tr_facade().lesson(channel_id, slide_id)
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
        answer = self._tr_facade().start_test(channel_id)
        if answer.get('url'):
            return request.redirect(answer['url'])
        if answer.get('code') == 'mine':
            return request.redirect('/my/training?problem=mine')
        if answer.get('code') == 'locked':
            return request.redirect(
                '/my/training/%s?problem=locked&left=%s'
                % (channel_id, self._tr_int(answer.get('left'))))
        return request.redirect('/my/training/%s?problem=%s'
                                % (channel_id, answer.get('code') or 'denied'))

    # =================================================================
    #  E2 — asking for more time, and the manager's own page
    # =================================================================
    @http.route(['/my/training/delay'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_training_delay(self, **post):
        """Ask for more time. ONE press, and the request is already in.

        The form posts the assignment it is about, and the model re-proves
        ownership from the session before it writes anything — the id in the
        form buys nothing, exactly as the course id in a URL buys nothing.
        """
        back = '/my/training'
        channel_id = self._tr_int(post.get('channel_id'))
        if channel_id:
            back = '/my/training/%s' % channel_id
        try:
            self._tr_facade().ask_more_time(
                self._tr_int(post.get('assignment_id')),
                post.get('reason_kind') or 'other',
                self._tr_int(post.get('days_asked')),
                (post.get('note') or '')[:2000])
        except (AccessError, UserError) as err:
            _logger.info('pb_training: a request for more time was refused '
                         '(%s)', err)
            return request.redirect('%s?problem=delay' % back)
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: a request for more time could not '
                            'be sent', exc_info=True)
            return request.redirect('%s?problem=delay' % back)
        return request.redirect('%s?ok=asked' % back)

    @http.route(['/my/training/team'], type='http', auth='user', website=True)
    def portal_training_team(self, **kw):
        """A manager's own view of their team's training.

        NOT A PERMISSION, A RELATIONSHIP: the page shows the people whose
        `parent_id` is the caller's own employee record and nobody else, and
        somebody who manages nobody is told so rather than shown an empty
        table they will read as a fault.
        """
        team = self._tr_facade().team()
        return request.render('pb_training.portal_training_team', {
            'page_name': 'training',
            'team': team,
            'notice': self._tr_notice(kw.get('ok')),
            'problem': self._tr_problem(kw),
        })

    @http.route(['/my/training/<int:channel_id>/certificate'], type='http',
                auth='user', website=True)
    def portal_training_certificate(self, channel_id, **kw):
        answer = self._tr_facade().certificate_url(channel_id)
        if answer.get('url'):
            return request.redirect(answer['url'])
        if answer.get('code') == 'mine':
            return request.redirect('/my/training?problem=mine')
        return request.redirect('/my/training/%s?problem=%s'
                                % (channel_id, answer.get('code') or 'denied'))
