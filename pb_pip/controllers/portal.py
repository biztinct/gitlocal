# -*- coding: utf-8 -*-
"""`/my/growth` — the page the person on the plan actually reads.

THE ROUTE IS THE GATE, exactly as P2, P3 and P4 established. The employee is
re-resolved from the SESSION user on every request and no route accepts an
employee id or a plan id, so a crafted URL cannot reach another person's plan.
Everything past that point is read under `sudo()` — the doctrine
`pb_me_portal` set — because the record has already been proved to be the
caller's own. There is NO model access rule for portal users on any PIP model,
deliberately: the route is the only door and it is a narrow one.

THE PAGE IS SWITCHED OFF IN ONE PARAMETER. `pb_pip.employee_view` (owner ruling
D5) — off, and every route here answers a polite redirect to `/my` rather than
a 403 or a traceback. A page that exists but refuses is a page that tells
somebody there is something to see.

THE WORD "PIP" APPEARS NOWHERE ON THIS PAGE, and neither does "performance
improvement plan", "probation", "warning" or "formal". It is "My growth plan".
This is not decoration: the page is read by somebody who is already worried,
often on a phone, sometimes with a colleague nearby, and the vocabulary a
company uses at that moment is the whole of what it is saying.

WHAT THE PAGE DOES NOT SHOW: who asked for the plan, what they wrote when they
asked, the coaching note, the manager's evaluation answers, or any earlier plan
that has closed. The plan itself, the dates, the conversations and the letter —
that is all of it.
"""

import logging

from datetime import date
from urllib.parse import quote

from odoo import _, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

from odoo.addons.pb_pip.models.pip_common import (
    OBJECTIVE_STATE_LABEL, P_EMPLOYEE_VIEW, PIP_EMPLOYEE_VISIBLE, flag,
)

_logger = logging.getLogger(__name__)

#: What each objective's standing is called on the person's own page. The
#: model's own labels are written for HR ("Not met"); these are written for the
#: person, and they are not the same sentence.
MINE_STATUS = {
    'on_track': 'Going well',
    'at_risk': 'Needs attention',
    'met': 'Done',
    'not_met': 'Not there yet',
}


class PbPipPortal(CustomerPortal):

    # --------------------------------------------------------------- helpers
    def _pip_enabled(self):
        return flag(request.env, P_EMPLOYEE_VIEW)

    def _pip_employee(self):
        """The OWN employee, from the session user. Never a parameter."""
        Emp = request.env['hr.employee'].sudo()
        emp = Emp.search([('user_id', '=', request.env.user.id),
                          ('company_id', '=', request.env.company.id)],
                         limit=1)
        return emp or Emp.search(
            [('user_id', '=', request.env.user.id)], limit=1)

    def _pip_case(self, emp):
        if not emp:
            return request.env['pb.pip.case'].browse()
        return request.env['pb.pip.case'].sudo().search([
            ('employee_id', '=', emp.id),
            ('state', 'in', list(PIP_EMPLOYEE_VISIBLE)),
        ], order='start_date desc, id desc', limit=1)

    def _prepare_home_portal_values(self, counters):
        """The counter, and it counts ONE thing: "you have not read it yet".

        A badge on `/my` that says "1" against a growth plan forever would be a
        permanent mark on somebody's home page. It appears while the plan is
        waiting to be acknowledged and disappears the moment they press the
        button.
        """
        values = super()._prepare_home_portal_values(counters)
        if 'growth_count' in counters:
            count = 0
            try:
                if self._pip_enabled():
                    emp = self._pip_employee()
                    case = self._pip_case(emp)
                    count = 1 if (case and not case.employee_ack) else 0
            except Exception:           # noqa: BLE001 — never break /my
                _logger.exception('pb_pip: could not count the growth plan')
            values['growth_count'] = count
        return values

    @http.route()
    def home(self, **kw):
        """`/my` — with one extra key, and the reason it cannot be the counter.

        The card below is shown ONLY when there is a plan to read: a permanent
        "My growth plan" tile on everybody's home page would be a standing
        invitation to wonder who has one.

        `growth_count` cannot decide that. Portal counters are fetched LAZILY,
        after the page has rendered, so at render time the name is not a number
        — the card gated on it is simply never drawn. So the question is
        answered here, eagerly, and the counter keeps its own job of putting a
        number on the card once it is on screen.

        The key is set on EVERY path through here, including the one where
        something went wrong: QWeb raises on a name it has never heard of, so a
        missing key would turn a hidden card into a 500 for the whole of `/my`.
        """
        response = super().home(**kw)
        if not hasattr(response, 'qcontext'):
            return response
        has_plan = False
        try:
            if self._pip_enabled():
                has_plan = bool(self._pip_case(self._pip_employee()))
        except Exception:               # noqa: BLE001 — never break /my
            _logger.exception('pb_pip: could not look for a growth plan')
        response.qcontext['has_growth_plan'] = has_plan
        return response

    # =================================================================
    #  /my/growth
    # =================================================================
    @http.route(['/my/growth'], type='http', auth='user', website=True)
    def portal_my_growth(self, **kw):
        if not self._pip_enabled():
            # A polite redirect and not a 404: the person did nothing wrong,
            # and a page that shouts at them is the last thing this module
            # should do.
            return request.redirect('/my')
        emp = self._pip_employee()
        if not emp:
            return request.redirect('/my')
        case = self._pip_case(emp)
        values = {
            'page_name': 'growth',
            'employee': emp,
            'plan': case if case else None,
            'notice': _('Thank you — that is noted.') if kw.get('ok') else '',
            'problem': kw.get('problem') or '',
        }
        if case:
            values.update(self._plan_values(case))
        return request.render('pb_pip.portal_my_growth', values)

    def _plan_values(self, case):
        """The plan, in the words of the person it is about."""
        now = date.today()
        end = case.end_date
        start = case.start_date
        span = (end - start).days if (end and start) else 0
        gone = (now - start).days if start else 0
        elapsed = 0
        if span > 0:
            elapsed = max(0, min(100, int(round(gone * 100.0 / span))))
        objectives = [{
            'id': o.id,
            'name': o.name or '',
            'metric': o.metric or '',
            'target': o.target or '',
            'status': o.status,
            'label': MINE_STATUS.get(o.status,
                                     OBJECTIVE_STATE_LABEL.get(o.status, '')),
        } for o in case.objective_ids]
        checkins = [{
            'id': c.id,
            'date': c.scheduled_date,
            'state': c.state,
            'done': c.state == 'done',
            'next': False,
        } for c in case.checkin_ids.sorted(
            key=lambda c: (c.scheduled_date or now, c.id))
            if c.state != 'cancelled']
        # The NEXT one, marked. A list of dates with nothing picked out is a
        # list somebody has to read twice to find the only line that matters.
        for row in checkins:
            if not row['done'] and row['date'] and row['date'] >= now:
                row['next'] = True
                break
        return {
            'objectives': objectives,
            'checkins': checkins,
            'days_left': (end - now).days if end else None,
            'elapsed': elapsed,
            'has_letter': bool(case.letter_id and case.letter_id.attachment_id),
            'hr_owner': (case.hr_owner_user_id.name
                         if case.hr_owner_user_id else ''),
            'freq_label': _('every week')
            if (case.checkin_freq or 'weekly') == 'weekly'
            else _('every two weeks'),
        }

    # ----------------------------------------------------------- the ack
    @http.route(['/my/growth/ack'], type='http', auth='user', website=True,
                methods=['POST'])
    def portal_growth_ack(self, **post):
        """"I have read it." The only write this page can make.

        The plan is re-derived from the SESSION rather than taken from the
        form, so there is no id to forge. `action_acknowledge` refuses a second
        stamp on its own account.
        """
        if not self._pip_enabled():
            return request.redirect('/my')
        emp = self._pip_employee()
        if not emp:
            return request.redirect('/my')
        case = self._pip_case(emp)
        if not case:
            return request.redirect('/my/growth')
        try:
            case.action_acknowledge()
        except Exception:               # noqa: BLE001 — never a traceback
            _logger.exception('pb_pip: could not record the acknowledgement '
                              'for plan %s', case.id)
            return request.redirect(
                '/my/growth?problem=%s' % quote(str(_(
                    "That could not be saved just now. Try again in a moment, "
                    "or tell your HR contact you have read it."))[:300]))
        return request.redirect('/my/growth?ok=1')

    # ------------------------------------------------------------ the letter
    @http.route(['/my/growth/letter'], type='http', auth='user', website=True)
    def portal_growth_letter(self, **kw):
        """The person's own copy of their plan, as the PDF that was filed.

        NOT `/web/content/<id>` — a portal user has no access to the
        attachment, and handing them a link that 403s is worse than not
        offering it. The route proves the plan is theirs and then streams the
        file it already knows the id of; no id crosses the wire in either
        direction.
        """
        if not self._pip_enabled():
            return request.redirect('/my')
        emp = self._pip_employee()
        case = self._pip_case(emp) if emp else None
        letter = case.letter_id if case else None
        attachment = letter.attachment_id if letter else None
        if not attachment:
            return request.redirect('/my/growth')
        try:
            return request.env['ir.binary']._get_stream_from(
                attachment.sudo(), 'raw').get_response(
                    as_attachment=True)
        except Exception:               # noqa: BLE001
            _logger.exception('pb_pip: could not serve the letter for plan %s',
                              case.id)
            return request.redirect('/my/growth')
