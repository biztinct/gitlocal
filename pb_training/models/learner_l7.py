# -*- coding: utf-8 -*-
"""LEARNING L7 — the learner's phone.

Five things the learner's own pages gain, all read through `pb.my.training`
(the session user is "me", never a parameter):

  * NEXT FOR YOU (`next_best`) — ONE rule engine behind the hero on My
    learning and on the portal page. Ordered rules, first match wins:
    a late course or a late path step → the path's current step → a
    certificate running out within 30 days → required training missing →
    (a practical sign-off: not built, owner decision LD5) → the course in
    progress nearest to done → an assigned course not started yet → a
    session today or tomorrow → feedback waiting → a three-minute lesson →
    "Nothing to do right now.". Each answer is `{kind, title, line, url,
    button, reason_key, reason, channel_id, percent}` in the reader's
    language. The rule order is `NEXT_RULES`; the test asserts it.
  * THREE MINUTES TODAY (`three_minutes`) — one short unfinished lesson
    (5 minutes or less by the lesson's own duration, shortest first); when
    none is timed that short, the shortest lesson of a course the training
    team flagged "Short lessons, 3–5 minutes each" (`slide.channel.pb_short`).
    Nothing fits → None and the card is not drawn. It never promises three
    minutes for a forty-minute lesson.
  * THE ON-TIME STREAK (`streak`) — finished assignments, newest first,
    counted while each was finished on or before its date (an agreed
    "more time" date counts). A late finish ends it. Shown only to the
    person ("3 in a row, on time"); never on a board, never ranked
    (owner decision LD8: no leaderboards).
  * A BADGE ON EACH CERTIFICATE — the certificate payload carries
    `badge: {initials, tone}`; the wallet and My learning draw an SVG medal
    (Lucide award + the course initials, brand colour). No
    `gamification.badge.user` rows (the stock karma and leaderboard pages
    stay blocked, L0 gate). The certificate email gets the same badge in
    email-safe markup (tables, no SVG — mail clients drop SVG), added to
    the queued mail, because the templates are `noupdate` and would not
    change on a live database.
  * BOTH LANGUAGES — a lesson whose Vietnamese and English differ carries
    the other language (`both`), shown stacked under a "Show both
    languages" toggle; the course drawer marks lessons with no Vietnamese
    ("Missing Vietnamese") for the training team.

And the two portal writes answer JSON when the phone page asks for it
(`controllers/portal.py`, `X-Requested-With`), so "Mark as done" and a quiz
can be queued on the phone while the signal is gone and replayed when it is
back (`static/src/js/portal_lesson.js`). No service worker (LD7).
"""

import logging
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .pb_training_catalogue import PbTrainingCatalogue
from .training_common import (
    ASSIGN_OPEN, TEST_FAILED, TEST_READY, as_id, duration_words, fold,
    minutes, tr,
)

_logger = logging.getLogger(__name__)

#: The rules behind "Next for you", in the order they are tried. `signoff`
#: stays in the list so the order is the designed one, and answers nothing
#: until practical sign-off is built (owner decision LD5).
NEXT_RULES = ('overdue', 'path', 'renewal', 'required', 'signoff',
              'continue', 'start', 'session', 'feedback', 'three', 'none')

#: A lesson that takes this long or less is a "three minutes today" lesson.
SHORT_MINUTES = 5

#: The certificate badge's colour per state (the locked palette: brand
#: purple, amber when it needs renewing, grey once it has run out).
BADGE_TONES = {'valid': 'brand', 'soon': 'warn', 'expired': 'muted',
               'renewed': 'muted'}
BADGE_HEX = {'brand': '#5A4BB0', 'warn': '#B7791F', 'muted': '#8A8798'}

#: Words a badge's initials skip ("Fire safety for the warehouse" → "FS").
_SMALL_WORDS = {'a', 'an', 'and', 'the', 'of', 'for', 'to', 'in', 'on', 'demo',
                'va', 'cho', 'cua', 've', 'tai', 'voi'}


def badge_initials(text):
    """Two letters for a badge: the first letters of the first two words
    that are not small words, upper case, accents kept ("An toàn lao động"
    → "AT")."""
    words = [w for w in re.findall(r'[^\W\d_]+', text or '', re.U)]
    big = [w for w in words if fold(w) not in _SMALL_WORDS] or words
    letters = ''.join(w[0] for w in big[:2]).upper()
    return letters or '·'


# =========================================================================
#  the course: "Short lessons", and what a lesson is missing
# =========================================================================
class SlideChannelL7(models.Model):
    _inherit = 'slide.channel'

    pb_short = fields.Boolean(
        string='Short lessons, 3–5 minutes each',
        help='Tells the learner\'s page that every lesson of this course is '
             'short, so one can be offered as "Three minutes today" even '
             'when nobody timed it.')


class PbTrainingL7(models.AbstractModel):
    """The course drawer: "Short lessons" and "Missing Vietnamese"."""
    _inherit = 'pb.training'

    _VERBS = PbTrainingCatalogue._VERBS + ('set_short',)

    @api.model
    def _vi_active(self):
        return bool(self.env['res.lang'].sudo().search_count(
            [('code', '=', 'vi_VN'), ('active', '=', True)]))

    @api.model
    def _missing_vi(self, slide_ids):
        """{slide id: True} for lessons with no Vietnamese words stored.

        Read off the stored translations themselves (a key per language), not
        by comparing words: a lesson called "Excel" in both languages HAS a
        translation. A reading lesson needs its text translated too.
        """
        if not slide_ids or not self._vi_active():
            return {}
        self.env['slide.slide'].flush_model(['name', 'html_content',
                                             'slide_category'])
        self.env.cr.execute("""
            SELECT id,
                   NOT (COALESCE(name, '{}'::jsonb) ? 'vi_VN'),
                   slide_category = 'article'
                     AND html_content IS NOT NULL
                     AND NOT (html_content ? 'vi_VN')
              FROM slide_slide WHERE id IN %s
        """, [tuple(slide_ids)])
        return {sid: bool(no_name or no_text)
                for sid, no_name, no_text in self.env.cr.fetchall()}

    @api.model
    def get_course(self, channel_id):
        data = super().get_course(channel_id)
        try:
            missing = self._missing_vi([l['id'] for l in data.get('lessons')
                                        or []])
            for lesson in data.get('lessons') or []:
                lesson['missing_vi'] = bool(missing.get(lesson['id']))
            data['missing_vi'] = len([1 for v in missing.values() if v])
            channel = self.env['slide.channel'].sudo().browse(
                as_id(channel_id))
            data['short'] = bool(channel.pb_short)
        except Exception:                   # noqa: BLE001 — chips are extra
            _logger.warning('pb_training: the L7 course facts could not be '
                            'read', exc_info=True)
        return data

    @api.model
    def set_short(self, channel_id, on):
        self._require_write()
        channel = self.env['slide.channel'].sudo().browse(
            as_id(channel_id)).exists()
        if not channel:
            raise UserError(_("That course is not here any more."))
        channel.write({'pb_short': bool(on)})
        return {'message': _("Marked as short lessons. A lesson from it can "
                             "be offered as three minutes today.") if on
                else _("No longer marked as short lessons.")}

    @api.model
    def act(self, verb, payload=None):
        if verb == 'set_short':
            payload = payload or {}
            return self.set_short(payload.get('channel_id'),
                                  payload.get('on'))
        return super().act(verb, payload)


# =========================================================================
#  the certificate badge
# =========================================================================
class PbEmployeeDocumentL7(models.Model):
    _inherit = 'pb.employee.document'

    def _pb_badge(self):
        self.ensure_one()
        source = self.channel_id.sudo().name or self.name or ''
        tone = BADGE_TONES.get(self.training_state or '', 'brand')
        return {'initials': badge_initials(source), 'tone': tone,
                'hex': BADGE_HEX[tone]}

    def _pb_cert_payload(self):
        data = super()._pb_cert_payload()
        try:
            data['badge'] = self._pb_badge()
        except Exception:                   # noqa: BLE001 — a badge is extra
            data['badge'] = {'initials': '·', 'tone': 'brand',
                             'hex': BADGE_HEX['brand']}
        return data

    def _pb_badge_mail_html(self):
        """The badge as email-safe markup: a round table cell with the
        initials, and the course name beside it. No SVG (mail clients drop
        it), no image request."""
        self.ensure_one()
        badge = self._pb_badge()
        from markupsafe import escape
        return (
            '<table role="presentation" cellpadding="0" cellspacing="0" '
            'style="margin:0 0 14px 0;"><tr>'
            '<td style="width:52px;height:52px;border-radius:26px;'
            'background:%(hex)s;color:#ffffff;text-align:center;'
            'vertical-align:middle;font:700 18px Inter,Helvetica,Arial,'
            'sans-serif;letter-spacing:1px;">%(ini)s</td>'
            '<td style="padding-left:12px;font:600 14px Inter,Helvetica,'
            'Arial,sans-serif;color:#1B1733;">%(name)s</td>'
            '</tr></table>') % {
            'hex': badge['hex'], 'ini': escape(badge['initials']),
            'name': escape(self.name or '')}

    def _pb_training_mail(self, xmlid, email_to):
        """The person's own certificate email carries the badge (L7). The
        templates are `noupdate`, so the badge is put on the queued mail
        itself rather than written into a template no database would get."""
        before = 0
        if xmlid == 'pb_training.mail_template_certificate_expiring':
            before = self.env['mail.mail'].sudo().search(
                [], order='id desc', limit=1).id
        sent = super()._pb_training_mail(xmlid, email_to)
        if not sent or xmlid != 'pb_training.mail_template_certificate_expiring':
            return sent
        try:
            mail = self.env['mail.mail'].sudo().search(
                [('id', '>', before), ('model', '=', self._name),
                 ('res_id', '=', self.id)], order='id desc', limit=1)
            if mail:
                mail.body_html = self._pb_badge_mail_html() + (
                    mail.body_html or '')
        except Exception:                   # noqa: BLE001 — never lose a mail
            _logger.warning('pb_training: the badge could not be added to '
                            'the certificate mail of document %s', self.id,
                            exc_info=True)
        return sent


# =========================================================================
#  the learner: next for you, three minutes today, the streak, two languages
# =========================================================================
class PbMyTrainingL7(models.AbstractModel):
    _inherit = 'pb.my.training'

    # ------------------------------------------------------------- three
    @api.model
    def three_minutes(self):
        """One short unfinished lesson, or None (see the module docstring)."""
        timed, flagged = [], []
        for row in self._memberships():
            channel = row.channel_id.sudo()
            if row.member_status == 'completed' \
                    or (getattr(channel, 'delivery', '') == 'session'):
                continue
            done = channel._pb_done_ids(row.partner_id)
            for slide in channel._pb_lessons():
                if slide.id in done:
                    continue
                mins = minutes(slide.completion_time)
                key = (mins or 999, 0 if channel.pb_short else 1,
                       fold(channel.name), slide.sequence, slide.id)
                if 0 < mins <= SHORT_MINUTES:
                    timed.append((key, channel, slide, mins))
                elif channel.pb_short:
                    flagged.append((key, channel, slide, mins))
        pick = min(timed, key=lambda r: r[0]) if timed else (
            min(flagged, key=lambda r: r[0]) if flagged else None)
        if not pick:
            return None
        _key, channel, slide, mins = pick
        Slide = self.env['slide.slide']
        return {
            'channel_id': channel.id,
            'course': channel.name or '',
            'lesson_id': slide.id,
            'name': slide.name or '',
            'kind_word': tr(self.env, Slide._pb_kind_word(
                slide.slide_category)),
            'icon': Slide._pb_kind_icon(slide.slide_category),
            'duration': duration_words(mins, self.env),
            'url': '/my/training/%s/%s' % (channel.id, slide.id),
        }

    # ------------------------------------------------------------- streak
    @api.model
    def streak(self):
        """{count, words}: finished on time in a row, newest first."""
        emp = self._my_employee()
        if not emp:
            return {'count': 0, 'words': ''}
        rows = self.env['pb.training.assignment'].sudo().search(
            [('employee_id', '=', emp.id), ('state', '=', 'done'),
             ('completed_on', '!=', False)],
            order='completed_on desc, id desc', limit=200)
        count = 0
        for row in rows:
            due = row.due_date
            if row.excused_until and (not due or row.excused_until > due):
                due = row.excused_until
            if not due:
                continue            # nothing to be on time for
            if row.completed_on <= due:
                count += 1
            else:
                break
        if count >= 2:
            words = _("%s in a row, on time", count)
        elif count == 1:
            words = _("Your last course was finished on time.")
        else:
            words = ''
        return {'count': count, 'words': words}

    # ------------------------------------------------------------- next
    @api.model
    def next_best(self):
        """The one thing to do next (the hero), from a fresh read."""
        return self.home().get('next') or self._next_none(False)

    @api.model
    def _course_step(self, tile):
        """(title, url, button) for "do the next thing on this course"."""
        if tile.get('next_id'):
            return (tile.get('next_name') or tile.get('name') or '',
                    '/my/training/%s/%s' % (tile['id'], tile['next_id']),
                    _("Continue"))
        if tile.get('test') in (TEST_READY, TEST_FAILED):
            return (_("The test at the end"),
                    '/my/training/%s' % tile['id'], _("Take the test"))
        return (tile.get('name') or '', '/my/training/%s' % tile['id'],
                _("Open"))

    def _answer(self, kind, title, line, url, button, reason, tile=None):
        return {
            'kind': kind,
            'title': title or '',
            'line': line or '',
            'url': url or '/my/training',
            'button': button or _("Open"),
            'reason_key': kind,
            'reason': reason or '',
            'channel_id': (tile or {}).get('id') or 0,
            'percent': (tile or {}).get('percent') or 0,
            'duration': (tile or {}).get('duration') or '',
        }

    def _next_none(self, has_courses):
        return self._answer(
            'none', _("Nothing to do right now."),
            _("Every course you are on is finished. When the training team "
              "puts you on a new one, it appears here.") if has_courses
            else _("You are not on any course yet. When the training team "
                   "puts you on one, it appears here."),
            '/my/training', _("Open my training"), '')

    @api.model
    def _pick_next(self, data, certs=None, required=None, three=None,
                   today=None, now_local=None):
        """THE RULES, over the payload `home()` already built (pure: every
        fact is passed in, so a test can hand it each case)."""
        today = today or fields.Date.today()
        courses = [c for c in (data.get('courses') or [])]
        by_id = {c['id']: c for c in courses}
        open_online = [c for c in courses if not c.get('finished')
                       and c.get('delivery') != 'session']

        def asg(c):
            return c.get('assignment') or {}

        for rule in NEXT_RULES:
            if rule == 'overdue':
                late = [c for c in open_online if asg(c).get('state') == 'overdue']
                late.sort(key=lambda c: (-(asg(c).get('days_over') or 0),
                                         fold(c.get('name'))))
                if late:
                    tile = late[0]
                    title, url, button = self._course_step(tile)
                    return self._answer(
                        'overdue', title,
                        '%s · %s' % (tile.get('name') or '',
                                     asg(tile).get('due_words') or ''),
                        url, button, _("It is past its date. Finish it, or "
                                       "ask your manager for more time."),
                        tile)
                for pth in data.get('paths') or []:
                    if pth.get('late') and pth.get('next'):
                        tile = by_id.get(pth['next']['channel_id']) or {}
                        if tile.get('finished'):
                            continue
                        title, url, button = self._course_step(tile) if tile \
                            else (pth['next']['name'], '/my/training/%s'
                                  % pth['next']['channel_id'], _("Open"))
                        return self._answer(
                            'overdue', title,
                            pth.get('where_words') or pth.get('name') or '',
                            url, button,
                            _("Your path is late. This is the step it waits "
                              "for."), tile)
            elif rule == 'path':
                for pth in data.get('paths') or []:
                    nxt = pth.get('next')
                    if pth.get('state') == 'done' or not nxt:
                        continue
                    tile = by_id.get(nxt['channel_id']) or {}
                    if tile.get('finished'):
                        continue
                    title, url, button = self._course_step(tile) if tile \
                        else (nxt['name'], '/my/training/%s'
                              % nxt['channel_id'], _("Open"))
                    return self._answer(
                        'path', title,
                        pth.get('where_words') or pth.get('name') or '',
                        url, button, _("The next step on your path."), tile)
            elif rule == 'renewal':
                soon = today + timedelta(days=30)
                for row in (certs or {}).get('rows') or []:
                    if row.get('state') not in ('soon', 'expired'):
                        continue
                    expiry = fields.Date.to_date(row.get('expiry') or None)
                    if row.get('state') == 'soon' and expiry and expiry > soon:
                        continue
                    renewal = row.get('renewal') or {}
                    if renewal.get('open') and renewal.get('channel_id'):
                        tile = by_id.get(renewal['channel_id']) or {}
                        title, url, button = self._course_step(tile) if tile \
                            else (row.get('name'), '/my/training/%s'
                                  % renewal['channel_id'], _("Start renewal"))
                        return self._answer(
                            'renewal', title,
                            '%s · %s' % (row.get('name') or '',
                                         row.get('valid_words') or ''),
                            url, button, _("Your certificate runs out soon. "
                                           "The refresher course renews it."),
                            tile)
                    return self._answer(
                        'renewal', row.get('name') or '',
                        row.get('valid_words') or '',
                        '/my/training/certificates', _("My certificates"),
                        _("Your certificate runs out soon. Add the new one "
                          "when you have it."))
            elif rule == 'required':
                for row in (required or {}).get('rows') or []:
                    if row.get('state') != 'missing':
                        continue
                    tile = by_id.get(row.get('channel_id')) or {}
                    if tile:
                        title, url, button = self._course_step(tile)
                    else:
                        title, url, button = (
                            row.get('name') or '', '/my/training', _("Open"))
                    return self._answer(
                        'required', title,
                        '%s · %s' % (row.get('name') or '',
                                     row.get('words') or ''),
                        url, button, _("Required for your job."), tile)
            elif rule == 'signoff':
                continue                    # LD5: not built yet
            elif rule == 'continue':
                going = [c for c in open_online if (c.get('percent') or 0) > 0]
                going.sort(key=lambda c: (-(c.get('percent') or 0),
                                          asg(c).get('due') or '9999-12-31',
                                          fold(c.get('name'))))
                if going:
                    tile = going[0]
                    title, url, button = self._course_step(tile)
                    return self._answer(
                        'continue', title, tile.get('name') or '', url,
                        button, _("You are nearly there on this one.")
                        if (tile.get('percent') or 0) >= 50
                        else _("Pick up where you left off."), tile)
            elif rule == 'start':
                fresh = [c for c in open_online
                         if not (c.get('percent') or 0)
                         and (c.get('total') or c.get('next_id'))]
                fresh.sort(key=lambda c: (asg(c).get('due') or '9999-12-31',
                                          fold(c.get('name'))))
                if fresh:
                    tile = fresh[0]
                    title, url, button = self._course_step(tile)
                    return self._answer(
                        'start', title, tile.get('name') or '', url,
                        _("Start"), _("A course the training team put you "
                                      "on."), tile)
            elif rule == 'session':
                nxt = (data.get('sessions') or {}).get('next')
                if nxt and nxt.get('start'):
                    when = self._local_day(nxt['start'], now_local)
                    local_today = (now_local or self._local_now()).date()
                    if when in (local_today, local_today + timedelta(days=1)):
                        return self._answer(
                            'session', nxt.get('course') or '',
                            '%s · %s' % (nxt.get('when_words') or '',
                                         nxt.get('where_words') or ''),
                            '/my/training/%s' % nxt.get('channel_id')
                            if nxt.get('channel_id') else '/my/training',
                            _("Open"),
                            _("Your session is today.") if when == local_today
                            else _("Your session is tomorrow."))
            elif rule == 'feedback':
                asks = data.get('feedback') or []
                if asks:
                    ask = asks[0]
                    return self._answer(
                        'feedback', ask.get('words') or '',
                        ask.get('course') or '', ask.get('url'),
                        _("Answer"), _("The training team asked what you "
                                       "thought. It takes a minute."))
            elif rule == 'three':
                if three:
                    return self._answer(
                        'three', three['name'],
                        '%s · %s' % (three['course'],
                                     three['duration'] or three['kind_word']),
                        three['url'], _("Start"),
                        _("A short lesson for today."))
            elif rule == 'none':
                return self._next_none(bool(courses))
        return self._next_none(bool(courses))

    def _local_now(self):
        return fields.Datetime.context_timestamp(self, fields.Datetime.now())

    def _local_day(self, value, now_local=None):
        try:
            dt = fields.Datetime.to_datetime(value)
            return fields.Datetime.context_timestamp(self, dt).date()
        except Exception:                   # noqa: BLE001
            return None

    @api.model
    def home(self):
        """Everything My learning and `/my/training` draw, plus L7's three
        answers. Each one is extra: a failure leaves the page as it was."""
        data = super().home()
        three = None
        try:
            three = self.three_minutes()
        except Exception:                   # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: three minutes today could not be '
                            'read', exc_info=True)
        data['three'] = three
        try:
            data['streak'] = self.streak()
        except Exception:                   # noqa: BLE001
            _logger.warning('pb_training: the streak could not be read',
                            exc_info=True)
            data['streak'] = {'count': 0, 'words': ''}
        try:
            certs = self.my_certificates()
            required = self.required_for_me()
            data['next'] = self._pick_next(data, certs=certs,
                                           required=required, three=three)
        except Exception:                   # noqa: BLE001
            _logger.warning('pb_training: next for you could not be read',
                            exc_info=True)
            data['next'] = None
        return data

    # ------------------------------------------------------------- languages
    @api.model
    def _both_languages(self, slide):
        """The lesson in the OTHER language when its words differ, or None.

        English and Vietnamese only (the two languages of this product). A
        lesson whose words are the same in both (nobody translated it) has
        nothing to show twice.
        """
        Lang = self.env['res.lang'].sudo()
        if Lang.search_count([('code', 'in', ('en_US', 'vi_VN')),
                              ('active', '=', True)]) < 2:
            return None
        this = 'vi_VN' if (self.env.lang or 'en_US') == 'vi_VN' else 'en_US'
        other = 'en_US' if this == 'vi_VN' else 'vi_VN'
        a = slide.sudo().with_context(lang=this)
        b = slide.sudo().with_context(lang=other)
        is_article = slide.slide_category == 'article'

        def text(rec):
            return str(rec.html_content or '') if is_article else ''

        if (a.name or '') == (b.name or '') and text(a) == text(b) \
                and (a.description or '') == (b.description or ''):
            return None
        word = {'en_US': 'EN', 'vi_VN': 'VI'}
        return {
            'this_code': word[this],
            'other_code': word[other],
            'other_lang': other,
            'name': b.name or '',
            'article': b.html_content or '' if is_article else '',
            'description': self._plain(b.description),
        }

    @api.model
    def lesson(self, channel_id, slide_id):
        data = super().lesson(channel_id, slide_id)
        if not data:
            return data
        try:
            slide = self.env['slide.slide'].sudo().browse(data['id'])
            data['both'] = self._both_languages(slide)
        except Exception:                   # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: the second language could not be '
                            'read for lesson %s', data.get('id'),
                            exc_info=True)
            data['both'] = None
        # A phone that blocks a document inside the page opens the file.
        data['file_url'] = data.get('pdf_url') or ''
        return data
