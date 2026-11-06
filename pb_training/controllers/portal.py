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

import json
import logging

from odoo import _, http
from odoo.exceptions import AccessError, UserError
from odoo.http import content_disposition, request
from odoo.tools.misc import format_date
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
    # E3. A claim can be refused for reasons the person can DO something
    # about — a missing file, an amount over what is left — and those come
    # back from the model as a whole sentence rather than a code, because
    # the arithmetic is in them. These two are the ones that are not about
    # the claim itself.
    'no_employee': _("You do not have an employee record yet, so there is "
                     "nowhere to pay a claim into. Tell your HR team."),
    'claim': _("That claim could not be sent. Try again, and tell the "
               "training team if it keeps happening."),
    # LEARNING L1
    'certificate': _("That certificate could not be added. Try again, and "
                     "tell the training team if it keeps happening."),
    'record': _("Your learning record could not be printed just now. Try "
                "again in a minute."),
    'record_denied': _("You can only print your own learning record."),
    # LEARNING L4
    'book': _("That seat could not be booked. The session may be full or "
              "closed to booking — ask the training team."),
    'calendar': _("That session is not one of yours, so there is no "
                  "calendar file for it."),
    # LEARNING L5
    'request': _("That request could not be sent. Try again, and tell the "
                 "training team if it keeps happening."),
    'request_cancel': _("That request could not be cancelled. It may "
                        "already be decided — ask the training team."),
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
        if 'training_claims_count' in counters:
            values['training_claims_count'] = self._tr_facade().claims_count()
        if 'training_certificates_count' in counters:
            values['training_certificates_count'] = \
                self._tr_facade().certificates_count()
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
            'problem': self._tr_words(_PROBLEMS.get(kw.get('problem') or '', '')),
        })

    def _tr_notice(self, key):
        return {
            'done': _("Marked as done."),
            'enrolled': _("You are on the course."),
            # E2
            'asked': _("Asked. Your manager will see it and you will get an "
                       "email either way."),
            # E3
            'claimed': _("Sent in. The HR lead sees it now, and you will get "
                         "an email either way."),
            # LEARNING L1
            'cert_added': _("Added to your certificates. HR checks it and "
                            "marks it checked."),
            # LEARNING L4
            'booked': _("You have a seat. The invitation comes by email."),
            'waiting': _("The session is full, so you are waiting for a "
                         "seat. You get an email if one comes free."),
            # LEARNING L5
            'requested': _("Asked. You get an email when it is decided."),
            'request_cancelled': _("Cancelled. Nobody needs to decide it "
                                   "now."),
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
        return self._tr_words(_PROBLEMS.get(code, ''))

    @staticmethod
    def _tr_words(text):
        """A refusal in the reader's language (LEARNING L1).

        `_PROBLEMS` is built at import, when there is no reader, so every
        sentence in it is the English source; it is translated here, when the
        page is drawn. A sentence with no Vietnamese stays English.
        """
        if not text:
            return ''
        try:
            return request.env._(text)
        except Exception:               # noqa: BLE001 — a word is not fatal
            return text

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
            # LEARNING L7: "Show both languages" without a script is a link
            # (`?both=1`); the script remembers the choice on the phone.
            'both_on': kw.get('both') == '1',
            'problem': self._tr_words(_PROBLEMS.get(kw.get('problem') or '', '')),
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

    # ------------------------------------------------ LEARNING L7: the phone
    @staticmethod
    def _tr_wants_json():
        """The phone page's own fetch (`portal_lesson.js`) asks for JSON with
        `X-Requested-With`; a plain form post (no script, or the script
        absent) gets the redirect it always got."""
        try:
            return request.httprequest.headers.get('X-Requested-With') \
                == 'XMLHttpRequest'
        except Exception:               # noqa: BLE001
            return False

    def _tr_json(self, payload):
        return request.make_json_response(payload)

    def _tr_lesson_name(self, channel_id, slide_id):
        try:
            lesson = self._tr_facade().lesson(channel_id, slide_id)
            return (lesson or {}).get('name') or ''
        except Exception:               # noqa: BLE001
            return ''

    def _tr_refusal(self, code):
        """A refusal the phone page shows as a sentence (never queued)."""
        return self._tr_json({'ok': False, 'problem': code,
                              'message': self._tr_words(_PROBLEMS.get(code,
                                                                      ''))})

    @http.route(['/my/training/<int:channel_id>/<int:slide_id>/done'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_training_done(self, channel_id, slide_id, **post):
        wants_json = self._tr_wants_json()
        try:
            self._tr_facade().mark_done(channel_id, slide_id)
        except UserError:
            if wants_json:
                return self._tr_refusal('quiz')
            return request.redirect('/my/training/%s/%s?problem=quiz'
                                    % (channel_id, slide_id))
        except AccessError:
            if wants_json:
                return self._tr_refusal('mine')
            return request.redirect('/my/training?problem=mine')
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: lesson %s on course %s could not be '
                            'marked done', slide_id, channel_id, exc_info=True)
            if wants_json:
                return self._tr_refusal('denied')
            return request.redirect('/my/training/%s/%s?problem=denied'
                                    % (channel_id, slide_id))
        # STRAIGHT ON TO THE NEXT ONE, and back to the course when there is no
        # next one. A person who has just finished a lesson wants the next
        # lesson, not the page they were already on with a tick added to it.
        nxt = self._tr_int(post.get('next_id'))
        next_url = '/my/training/%s/%s' % (channel_id, nxt) if nxt else \
            '/my/training/%s?ok=done&from=%s' % (channel_id, slide_id)
        if wants_json:
            return self._tr_json({
                'ok': True, 'done': True, 'next_url': next_url,
                'lesson_name': self._tr_lesson_name(channel_id, slide_id)})
        return request.redirect(next_url)

    @http.route(['/my/training/<int:channel_id>/<int:slide_id>/quiz'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_training_quiz(self, channel_id, slide_id, **post):
        """Answer a quiz lesson. Graded on the SERVER, always.

        The form posts one `q<question id>` per question holding the chosen
        answer id, and nothing else. No marking crosses the wire in either
        direction — a page that knew which answer was right would be a page a
        learner could read the answers off.
        """
        wants_json = self._tr_wants_json()
        chosen = []
        for key, value in (post or {}).items():
            if not key.startswith('q'):
                continue
            chosen.append(self._tr_int(value))
        try:
            result = self._tr_facade().answer_quiz(channel_id, slide_id, chosen)
        except AccessError:
            if wants_json:
                return self._tr_refusal('mine')
            return request.redirect('/my/training?problem=mine')
        except UserError:
            if wants_json:
                return self._tr_refusal('lesson')
            return request.redirect('/my/training/%s/%s?problem=lesson'
                                    % (channel_id, slide_id))
        nxt = self._tr_int(post.get('next_id'))
        next_url = '/my/training/%s/%s' % (channel_id, nxt) if nxt else \
            '/my/training/%s?ok=done&from=%s' % (channel_id, slide_id)
        if wants_json:
            # The marks only (which questions were right, wrong or left
            # blank) and the sentence — never which answer was the right one.
            return self._tr_json({
                'ok': True, 'passed': bool(result.get('passed')),
                'result': {k: result.get(k) for k in
                           ('passed', 'wrong', 'unanswered', 'right',
                            'message')},
                'next_url': next_url if result.get('passed') else '',
                'lesson_name': self._tr_lesson_name(channel_id, slide_id)})
        if result.get('passed'):
            return request.redirect(next_url)
        # A wrong answer RE-RENDERS rather than redirecting, so the marks
        # against the questions they got wrong survive the round trip.
        lesson = self._tr_facade().lesson(channel_id, slide_id)
        if not lesson:
            return request.redirect('/my/training?problem=mine')
        return request.render('pb_training.portal_training_lesson', {
            'page_name': 'training',
            'lesson': lesson,
            'both_on': False,
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

    # =================================================================
    #  E3 — the training allowance and claiming a course back
    # =================================================================
    @http.route(['/my/training/claims'], type='http', auth='user',
                website=True)
    def portal_training_claims(self, **kw):
        return self._tr_claims_page(notice=self._tr_notice(kw.get('ok')),
                                    problem=self._tr_problem(kw),
                                    request_id=self._tr_int(kw.get('request')))

    def _tr_claims_page(self, notice='', problem='', request_id=0):
        """The page, rendered from one read. Used by the GET and by a refusal.

        A REFUSAL RE-RENDERS RATHER THAN REDIRECTING, and that is not a style
        choice: the sentences this page refuses with have ARITHMETIC in them
        ("your allowance is 5,000,000 ₫, 4,000,000 ₫ is agreed, so 1,000,000 ₫
        is left"), and a sentence carried in a query string is a sentence
        somebody else can write onto the page (R51, and the `_tr_problem`
        rule three screens up). So the codes stay codes and the real answer
        comes back in the render values.
        """
        return request.render('pb_training.portal_training_claims', {
            'page_name': 'training',
            'claims': self._tr_facade().claims(),
            'notice': notice,
            'problem': problem,
            # LEARNING L5: "Claim this course back" from an agreed request
            # opens the form already filled in (re-checked on the way in).
            'prefill': self._tr_facade().claim_prefill(request_id)
            if request_id else {},
        })

    @http.route(['/my/training/claims/new'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_training_claim_new(self, **post):
        """Claim a course back. ONE press, and it is already in.

        The two files arrive as real uploads and never as a path or an
        attachment id: an id in a form buys nothing (the vault learnt that the
        hard way — probing a stranger's attachment id would get their file
        deleted later), and the model binds what is uploaded to the claim it
        is about.
        """
        try:
            self._tr_facade().raise_claim(
                {
                    'course_name': (post.get('course_name') or '').strip()[:200],
                    'provider': (post.get('provider') or '').strip()[:200],
                    'amount': self._tr_money(post.get('amount')),
                    'paid_on': post.get('paid_on') or False,
                    'note': (post.get('note') or '')[:2000],
                    'assignment_id': self._tr_int(post.get('assignment_id')),
                    'request_id': self._tr_int(post.get('request_id')),
                },
                invoice=self._tr_upload(post.get('invoice')),
                certificate=self._tr_upload(post.get('certificate')))
        except AccessError:
            return request.redirect('/my/training/claims?problem=no_employee')
        except UserError as err:
            # The model's own sentence, straight onto the page. It is written
            # for the person reading it and it has the numbers in it.
            return self._tr_claims_page(problem=str(err))
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: a training claim could not be sent',
                            exc_info=True)
            return request.redirect('/my/training/claims?problem=claim')
        return request.redirect('/my/training/claims?ok=claimed')

    @staticmethod
    def _tr_money(value):
        """An amount typed on a phone. Commas, spaces and a stray symbol."""
        raw = (value or '').strip()
        for junk in (',', ' ', ' ', '₫', '$'):
            raw = raw.replace(junk, '')
        try:
            return float(raw or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _tr_upload(upload):
        """One uploaded file as `(name, bytes)`, or nothing.

        An empty file input arrives as a `FileStorage` with an empty filename
        rather than as `None`, so "did they attach anything" is a question
        about the BYTES and not about the object.
        """
        if not upload:
            return None
        try:
            content = upload.read()
        except Exception:               # noqa: BLE001 — a bad upload is not 500
            return None
        if not content:
            return None
        return (getattr(upload, 'filename', '') or '', content)

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

    # =================================================================
    #  LEARNING L1 — my certificates, and my learning record
    # =================================================================
    @http.route(['/my/training/certificates'], type='http', auth='user',
                website=True)
    def portal_training_certificates(self, **kw):
        return self._tr_certificates_page(notice=self._tr_notice(kw.get('ok')),
                                          problem=self._tr_problem(kw))

    def _tr_certificates_page(self, notice='', problem=''):
        """The wallet, from one read. A refusal RE-RENDERS with the model's
        own sentence (the claims page's rule: a sentence carried in a query
        string is a sentence somebody else can write onto the page)."""
        return request.render('pb_training.portal_training_certificates', {
            'page_name': 'training',
            'wallet': self._tr_facade().my_certificates(),
            'notice': notice,
            'problem': problem,
        })

    @http.route(['/my/training/certificates/new'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_training_certificate_new(self, **post):
        """Add an outside certificate or licence. The file arrives as a real
        upload, never an attachment id (an id in a form buys nothing)."""
        try:
            self._tr_facade().add_certificate(
                {
                    'name': (post.get('name') or '').strip()[:200],
                    'kind': post.get('kind') or 'CERT',
                    'issuer': (post.get('issuer') or '').strip()[:200],
                    'reference': (post.get('reference') or '').strip()[:100],
                    'issue_date': post.get('issue_date') or False,
                    'expiry_date': post.get('expiry_date') or False,
                    'note': (post.get('note') or '')[:2000],
                },
                self._tr_upload(post.get('file')))
        except AccessError:
            return request.redirect(
                '/my/training/certificates?problem=no_employee')
        except UserError as err:
            return self._tr_certificates_page(problem=str(err))
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: a certificate could not be added',
                            exc_info=True)
            return request.redirect(
                '/my/training/certificates?problem=certificate')
        return request.redirect('/my/training/certificates?ok=cert_added')

    @http.route(['/my/training/record.pdf'], type='http', auth='user',
                website=True)
    def portal_training_record(self, employee_id=None, **kw):
        """The learning record. Your own — or, for the training team,
        anybody's in their companies (`?employee_id=`); the facade decides."""
        try:
            pdf, filename = self._tr_facade().record_pdf(
                self._tr_int(employee_id))
        except AccessError:
            return request.redirect(
                '/my/training/certificates?problem=record_denied')
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: a learning record could not be '
                            'printed', exc_info=True)
            return request.redirect('/my/training/certificates?problem=record')
        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf)),
            ('Content-Disposition', content_disposition(filename)),
        ])

    # =================================================================
    #  LEARNING L4 — sessions: the QR scan, the calendar file, a seat
    # =================================================================
    @http.route(['/my/training/attend/<string:token>'], type='http',
                auth='user', website=True)
    def portal_training_attend(self, token, **kw):
        """The code on the trainer's screen. The person is the session user;
        the token only names the session (handover F2/F3)."""
        try:
            answer = self._tr_facade().attend_by_token(token)
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: an attendance scan failed',
                            exc_info=True)
            answer = {'code': 'invalid', 'session': None}
        return self._tr_attend_page(token, answer)

    @http.route(['/my/training/attend/<string:token>/join'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_training_attend_join(self, token, **post):
        try:
            answer = self._tr_facade().attend_by_token(token, join=True)
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: joining a session from a scan '
                            'failed', exc_info=True)
            answer = {'code': 'invalid', 'session': None}
        return self._tr_attend_page(token, answer)

    def _tr_attend_page(self, token, answer):
        return request.render('pb_training.portal_training_attend', {
            'page_name': 'training',
            'code': answer.get('code') or 'invalid',
            'info': answer.get('session') or {},
            'seats_words': answer.get('seats_words') or '',
            'token': token,
        })

    @http.route(['/my/training/sessions/<int:session_id>/calendar.ics'],
                type='http', auth='user', website=True)
    def portal_training_session_ics(self, session_id, **kw):
        data = self._tr_facade().session_ics(session_id)
        if not data:
            return request.redirect('/my/training?problem=calendar')
        return request.make_response(data, headers=[
            ('Content-Type', 'text/calendar; charset=utf-8'),
            ('Content-Length', len(data)),
            ('Content-Disposition', content_disposition('session.ics')),
        ])

    @http.route(['/my/training/sessions/<int:session_id>/book'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_training_session_book(self, session_id, **post):
        back = '/my/training'
        channel_id = self._tr_int(post.get('channel_id'))
        if channel_id:
            back = '/my/training/%s' % channel_id
        try:
            res = self._tr_facade().book_my_seat(session_id)
        except (AccessError, UserError):
            return request.redirect('%s?problem=book' % back)
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: a seat could not be booked',
                            exc_info=True)
            return request.redirect('%s?problem=book' % back)
        code = 'waiting' if res.get('code') == 'waiting' else 'booked'
        return request.redirect('%s?ok=%s' % (back, code))


    # =================================================================
    #  LEARNING L5 — asking to take a course, and the feedback pages
    # =================================================================
    @http.route(['/my/training/requests'], type='http', auth='user',
                website=True)
    def portal_training_requests(self, **kw):
        return self._tr_requests_page(notice=self._tr_notice(kw.get('ok')),
                                      problem=self._tr_problem(kw))

    def _tr_requests_page(self, notice='', problem='', form=None):
        """Re-renders on a refusal rather than redirecting: the money
        refusal carries arithmetic, which must never travel in a query
        string (the claims page's rule)."""
        facade = self._tr_facade()
        return request.render('pb_training.portal_training_requests', {
            'page_name': 'training',
            'options': facade.request_options(),
            'mine': facade.my_requests(),
            'notice': notice,
            'problem': problem,
            'form': form or {},
        })

    @http.route(['/my/training/requests/new'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_training_request_new(self, **post):
        kind = post.get('kind') or 'ours'
        values = {
            'kind': kind,
            'channel_id': self._tr_int(post.get('channel_id')),
            'outside_course_id': self._tr_int(post.get('outside_course_id')),
            'course_name': (post.get('course_name') or '').strip()[:200],
            'provider': (post.get('provider') or '').strip()[:200],
            'url': (post.get('url') or '').strip()[:500],
            'amount': self._tr_money(post.get('amount')),
            'when_words': (post.get('when_words') or '').strip()[:200],
            'why': (post.get('why') or '')[:2000],
        }
        try:
            self._tr_facade().ask_course(values)
        except AccessError:
            return request.redirect('/my/training/requests?problem='
                                    'no_employee')
        except (UserError, Exception) as err:  # noqa: BLE001
            if not isinstance(err, UserError):
                _logger.warning('pb_training: a course request could not be '
                                'sent', exc_info=True)
                return request.redirect('/my/training/requests?problem='
                                        'request')
            return self._tr_requests_page(problem=str(err), form=values)
        return request.redirect('/my/training/requests?ok=requested')

    @http.route(['/my/training/requests/<int:request_id>/cancel'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_training_request_cancel(self, request_id, **post):
        try:
            self._tr_facade().cancel_request(request_id)
        except (AccessError, UserError):
            return request.redirect('/my/training/requests?problem='
                                    'request_cancel')
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: a course request could not be '
                            'cancelled', exc_info=True)
            return request.redirect('/my/training/requests?problem='
                                    'request_cancel')
        return request.redirect('/my/training/requests?ok='
                                'request_cancelled')

    def _tr_feedback(self, token):
        """(request, status) for a COURSE feedback token only — the other
        kinds have their own page in the journey module."""
        req, status = request.env['pb.feedback.request'].sudo() \
            ._request_for_token(token)
        if req and req.kind not in ('training', 'training_followup'):
            return request.env['pb.feedback.request'].sudo().browse(), \
                'invalid'
        return req, status

    @http.route(['/my/training/feedback/<string:token>'], type='http',
                auth='public', website=True, sitemap=False)
    def portal_training_feedback(self, token, **kw):
        req, status = self._tr_feedback(token)
        if kw.get('done') == '1' and status in ('used', 'ok'):
            status = 'thanks'
        return self._tr_feedback_page(token, req, status)

    def _tr_feedback_page(self, token, req, status):
        env = request.env
        course = req._pb_course_name() if req else ''
        about = req.subject_employee_id.sudo().name if req else ''
        heading = env._("How was %s?", course) \
            if (req and req.kind == 'training') else \
            env._("Has %(who)s's work changed since %(course)s?", who=about,
                  course=course)
        window = env._("This link is open until %s and works once.",
                       format_date(env, req.window_end)) \
            if (req and req.window_end) else ''
        return request.render('pb_training.portal_training_feedback', {
            'status': status,
            'token': token,
            'heading': heading,
            'window_words': window,
            'kind': req.kind if req else '',
            'course': req._pb_course_name() if req else '',
            'about': req.subject_employee_id.sudo().name if req else '',
            'window_end': format_date(request.env, req.window_end)
            if (req and req.window_end) else '',
            'questions': req.questions() if (req and status == 'ok') else [],
        })

    @http.route(['/my/training/feedback/<string:token>/submit'],
                type='http', auth='public', website=True, methods=['POST'],
                sitemap=False)
    def portal_training_feedback_submit(self, token, **post):
        req, status = self._tr_feedback(token)
        if status == 'ok':
            answers = {}
            for q in req.questions():
                raw = post.get('q_%s' % q['key'], '')
                if isinstance(raw, str):
                    raw = raw.strip()[:2000]
                if q['type'] == 'rating' and raw not in ('1', '2', '3', '4',
                                                         '5'):
                    raw = ''
                if q['type'] == 'choice' and raw not in q['options']:
                    raw = ''
                answers[q['key']] = {'label': q['label'], 'value': raw}
            try:
                req.sudo().submit_answers(answers)
            except Exception:           # noqa: BLE001 — never a 500
                _logger.warning('pb_training: feedback could not be saved',
                                exc_info=True)
        return request.redirect('/my/training/feedback/%s?done=1' % token)

    # =================================================================
    #  LEARNING L7 — the home-screen manifest (no service worker, LD7)
    # =================================================================
    #: What a phone needs to put "My training" on its home screen. The
    #: shape is `biz_geo_tracking`'s `_make_manifest` (handover F2), written
    #: here so the training pages do not depend on the tracking module. NO
    #: SERVICE WORKER: nothing is cached for offline use — a lesson keeps its
    #: place and its answers wait on the phone (`portal_lesson.js`), and that
    #: is all (owner decision LD7).
    _TR_MANIFEST = {
        'name': 'My training',
        'short_name': 'Training',
        'description': 'My training',
        'scope': '/my/training',
        'start_url': '/my/training',
        'display': 'standalone',
        'orientation': 'portrait',
        'background_color': '#ffffff',
        'theme_color': '#1E1B2E',
        'icons': [
            {'src': '/pb_training/static/src/img/pwa-192.png',
             'sizes': '192x192', 'type': 'image/png',
             'purpose': 'any maskable'},
            {'src': '/pb_training/static/src/img/pwa-512.png',
             'sizes': '512x512', 'type': 'image/png',
             'purpose': 'any maskable'},
        ],
    }

    @http.route(['/my/training/manifest.webmanifest'], type='http',
                auth='public', methods=['GET'], website=False, sitemap=False)
    def portal_training_manifest(self, **kw):
        """Public on purpose: a browser fetches a manifest without the
        session cookie, so a signed-in-only route would answer the sign-in
        page. It names the page and nothing else."""
        return request.make_response(
            json.dumps(self._TR_MANIFEST),
            [('Content-Type', 'application/manifest+json'),
             ('Cache-Control', 'public, max-age=86400')])
