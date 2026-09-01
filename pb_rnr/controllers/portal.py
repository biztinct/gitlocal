# -*- coding: utf-8 -*-
"""`/my/recognition` — where anybody says thank you, and where a manager agrees.

THE ROUTE IS THE GATE, exactly as P2-P7 established. The person is re-resolved
from the SESSION user on every request; no route accepts an employee id, and the
one route that accepts a nomination id proves the caller is that nominee's
MANAGER on the record it fetched before doing anything with it. Everything past
that point runs under `sudo()` — the doctrine `pb_me_portal` set — because the
record has already been proved to be the caller's business.

THREE THINGS HAPPEN ON THIS PAGE and they are deliberately in this order:

  1. **The wall.** The same stories the Home mission shows, from the same
     facade. Somebody who came here to write one has just read five.
  2. **Waiting for you.** A manager's own step. It is the reason the two-hand
     design works at all: line managers do not log into a back office, so the
     step has to be where they already are.
  3. **Mine.** What they have been thanked for, and what they have said about
     other people — with the second number shown as prominently as the first,
     because that is the one that changes behaviour.

THE PAGE IS SWITCHED OFF IN ONE PARAMETER (`pb_rnr.employee_view`), and switched
off every route here answers a polite redirect to `/my` rather than a 403.

WHAT IT NEVER SHOWS: a story that was declined (unless it is the reader's own),
a story the writer marked private (ditto), anybody's date of birth, or any
amount belonging to somebody else.
"""

import logging

from urllib.parse import quote

from odoo import _, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

from odoo.addons.pb_rnr.models.rnr_common import (
    NOMINATION_STATE_LABEL, OUTCOME_LABEL, P_EMPLOYEE_VIEW, day_label, excerpt,
    flag, initials,
)

_logger = logging.getLogger(__name__)

#: What each step is called on the person's own page. The model's labels are
#: written for HR; these are written for the person, and they are not the same
#: words.
MINE_STATE = {
    'draft': 'Being written',
    'submitted': 'With their manager',
    'manager': 'With HR',
    'done': 'Agreed',
    'refused': 'Not this time',
}


class PbRnrPortal(CustomerPortal):

    # --------------------------------------------------------------- helpers
    def _rnr_enabled(self):
        return flag(request.env, P_EMPLOYEE_VIEW)

    def _rnr_employee(self):
        """The OWN employee, from the session user. Never a parameter."""
        Emp = request.env['hr.employee'].sudo()
        emp = Emp.search([('user_id', '=', request.env.user.id),
                          ('company_id', '=', request.env.company.id)], limit=1)
        return emp or Emp.search(
            [('user_id', '=', request.env.user.id)], limit=1)

    # ------------------------------------------------------------ /my's card
    def _prepare_home_portal_values(self, counters):
        """The counter counts ONE thing: praise that is waiting on YOU.

        A badge that says "12" against how often somebody has been thanked
        would be a permanent decoration. This one appears when a manager has a
        story to agree and disappears the moment they do.
        """
        values = super()._prepare_home_portal_values(counters)
        if 'recognition_count' in counters:
            count = 0
            try:
                if self._rnr_enabled():
                    emp = self._rnr_employee()
                    if emp:
                        count = request.env['pb.rnr.nomination'].sudo(
                        ).search_count([('state', '=', 'submitted'),
                                        ('nominee_id.parent_id', '=', emp.id)])
            except Exception:           # noqa: BLE001 — never break /my
                _logger.exception('pb_rnr: could not count the waiting praise')
            values['recognition_count'] = count
        return values

    @http.route()
    def home(self, **kw):
        """`/my` — with one extra key, eagerly computed.

        R62 — portal counters are fetched LAZILY, after the page has rendered,
        so a card gated on `recognition_count` is simply never drawn. The key is
        set on EVERY path through here, because QWeb raises on a name it has
        never heard of and a missing key would turn a hidden card into a 500 for
        the whole of `/my`. This card is shown to everybody, because everybody
        can say thank you — that is the one page in the product with no reason
        to be conditional.
        """
        response = super().home(**kw)
        if not hasattr(response, 'qcontext'):
            return response
        response.qcontext['has_recognition'] = bool(self._safe_enabled())
        return response

    def _safe_enabled(self):
        try:
            return self._rnr_enabled() and bool(self._rnr_employee())
        except Exception:               # noqa: BLE001 — never break /my
            _logger.exception('pb_rnr: could not look for the recognition page')
            return False

    # =================================================================
    #  /my/recognition
    # =================================================================
    @http.route(['/my/recognition'], type='http', auth='user', website=True)
    def portal_my_recognition(self, **kw):
        if not self._rnr_enabled():
            return request.redirect('/my')
        emp = self._rnr_employee()
        if not emp:
            return request.redirect('/my')
        Wall = request.env['pb.rnr.wall'].sudo()
        wall = Wall.get_wall()
        team = self._team(emp)
        values = {
            'page_name': 'recognition',
            'employee': emp,
            'stories': wall.get('stories') or [],
            'celebrations': wall.get('celebrations') or [],
            'winners': wall.get('winners') or {},
            'values': request.env['pb.rnr'].sudo().values_list(),
            'team': team,
            'colleagues': self._colleagues(emp, exclude=[t['id'] for t in team]),
            'waiting': self._waiting_for_me(emp),
            'received': self._mine(emp, 'nominee_id'),
            'given': self._mine(emp, 'nominator_id'),
            'notice': self._notice(kw.get('ok')),
            'problem': (kw.get('problem') or '')[:300],
        }
        return request.render('pb_rnr.portal_my_recognition', values)

    def _notice(self, key):
        return {
            'sent': _("Thank you — that has gone to their manager."),
            'agreed': _("Agreed. It has gone to HR."),
            'declined': _("Noted. Nothing about it will be shown to anybody."),
        }.get(key or '', '')

    def _team(self, emp):
        """The people this person sits with: their manager, and everybody who
        reports to the same manager, and everybody who reports to them.

        Most praise goes to somebody near you, so these go at the TOP of the
        picker. It is the only ergonomic move available on a page that carries
        no JavaScript of ours, and it is the one that matters.
        """
        boss = emp.parent_id
        domain = ['&', ('active', '=', True), ('id', '!=', emp.id)]
        if boss:
            domain += ['|', '|', ('id', '=', boss.id),
                       ('parent_id', '=', boss.id), ('parent_id', '=', emp.id)]
        else:
            domain += [('parent_id', '=', emp.id)]
        rows = request.env['hr.employee'].sudo().search(domain, order='name')
        return [{'id': e.id, 'name': e.name or ''} for e in rows]

    def _colleagues(self, emp, exclude=None):
        """Everybody else this person may thank: ACTIVE, in their own company.

        The whole list rather than a search box, because this page carries no
        JavaScript of ours and a native `<select>` with the browser's own
        type-to-find is faster than anything we could write — and it works with
        a keyboard, a screen reader and no network.
        """
        rows = request.env['hr.employee'].sudo().search([
            ('active', '=', True),
            ('company_id', '=', (emp.company_id or request.env.company).id),
            ('id', '!=', emp.id),
        ], order='name')
        skip = set(exclude or [])
        return [{'id': e.id, 'name': e.name or ''}
                for e in rows if e.id not in skip]

    def _waiting_for_me(self, emp):
        """A manager's own step. The record is found FROM the session person —
        `nominee_id.parent_id = me` — so there is no id to forge on the way in.
        """
        recs = request.env['pb.rnr.nomination'].sudo().search([
            ('state', '=', 'submitted'),
            ('nominee_id.parent_id', '=', emp.id),
        ], order='submitted_at desc, id desc', limit=25)
        return [self._card(rec) for rec in recs]

    def _mine(self, emp, field):
        domain = [(field, '=', emp.id)]
        if field == 'nominee_id':
            # What was said ABOUT them: agreed praise only. A story somebody
            # wrote and HR turned down is not something to put in front of the
            # person it is about.
            domain += [('state', '=', 'done'),
                       ('outcome', 'in', ('recognised', 'awarded'))]
        recs = request.env['pb.rnr.nomination'].sudo().search(
            domain, order='id desc', limit=25)
        return [self._card(rec) for rec in recs]

    def _card(self, rec):
        Nom = request.env['pb.rnr.nomination'].sudo()
        nominee = Nom._person(rec.nominee_id)
        nominator = Nom._person(rec.nominator_id)
        val = rec.value_id.sudo()
        return {
            'id': rec.id,
            'nominee': nominee.name or '',
            'initials': initials(nominee.name or ''),
            'avatar': ('/web/image/hr.employee/%s/avatar_128' % nominee.id
                       if nominee else ''),
            'nominator': nominator.name or '',
            'value': val.name or '',
            'color': val.color or 'primary',
            'motto': val.motto or '',
            'story': excerpt(rec.story, 400),
            'state': rec.state or 'draft',
            'state_label': MINE_STATE.get(
                rec.state, NOMINATION_STATE_LABEL.get(rec.state, '')),
            'outcome': rec.outcome or '',
            'outcome_label': OUTCOME_LABEL.get(rec.outcome, ''),
            'public': bool(rec.public),
            'winner': bool(rec.is_winner),
            'when': day_label(rec.decided_at.date() if rec.decided_at
                              else (rec.submitted_at.date()
                                    if rec.submitted_at else None)),
        }

    # ------------------------------------------------------------- the write
    @http.route(['/my/recognition/nominate'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_recognition_nominate(self, **post):
        """The only write anybody can make from this page about somebody else.

        The NOMINATOR is re-derived from the session and never taken from the
        form, so the one thing a crafted request could forge — putting words in
        a colleague's mouth — cannot be forged. `_create_nomination` does the
        rest of the checking, and it is the identical call the backend makes.
        """
        if not self._rnr_enabled():
            return request.redirect('/my')
        emp = self._rnr_employee()
        if not emp:
            return request.redirect('/my')
        try:
            request.env['pb.rnr'].sudo()._create_nomination({
                'nominee_id': post.get('nominee_id'),
                'value_id': post.get('value_id'),
                'story': post.get('story'),
                'public': post.get('public') in ('1', 'on', 'true', True),
            }, emp)
        except Exception as e:              # noqa: BLE001 — never a traceback
            return request.redirect(
                '/my/recognition?problem=%s' % quote(self._msg(e)))
        return request.redirect('/my/recognition?ok=sent')

    @http.route(['/my/recognition/decide'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_recognition_decide(self, **post):
        """A manager's step, and the ownership test is the gate.

        The nomination is fetched, and then checked on the RECORD — is this
        caller the nominee's manager, and is it still at their step — before
        anything happens. Nothing the caller sent is trusted past the id, and an
        id that does not pass gets a redirect rather than an error, because a
        403 tells somebody there was something there.
        """
        if not self._rnr_enabled():
            return request.redirect('/my')
        emp = self._rnr_employee()
        if not emp:
            return request.redirect('/my')
        rec = request.env['pb.rnr.nomination'].sudo().browse(
            int(post.get('nomination_id') or 0)).exists()
        boss = rec.nominee_id.sudo().parent_id if rec else None
        if not rec or rec.state != 'submitted' or not boss or boss.id != emp.id:
            return request.redirect('/my/recognition')
        note = (post.get('note') or '').strip()[:500]
        agree = post.get('decision') == 'agree'
        try:
            if agree:
                rec.action_manager_agree(note=note or False)
            else:
                rec.action_decline(note=note or False)
        except Exception as e:              # noqa: BLE001
            return request.redirect(
                '/my/recognition?problem=%s' % quote(self._msg(e)))
        return request.redirect(
            '/my/recognition?ok=%s' % ('agreed' if agree else 'declined'))

    def _msg(self, e):
        """The sentence a person reads when something did not work."""
        raw = ''
        try:
            raw = (getattr(e, 'args', None) or [''])[0] or ''
        except Exception:                   # noqa: BLE001
            raw = ''
        if not isinstance(raw, str) or not raw.strip():
            raw = str(_("That could not be saved just now. Try again in a "
                        "moment."))
        _logger.info('pb_rnr: the recognition page refused a write: %s', raw)
        return raw[:300]
