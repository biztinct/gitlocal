# -*- coding: utf-8 -*-
"""The three employee pages: my journey, my buddy, the org chart.

THE ROUTE IS THE GATE. The employee is re-resolved from the SESSION user on
every request and no own-data route accepts an employee id, so a crafted URL
can never reach another person's journey. Everything past that point is read
under `sudo()` — the doctrine `pb_me_portal` set for documents and payslips —
because the record it reads has already been proved to be the caller's own.

THE ORG CHART IS THE ONE PAGE THAT SHOWS OTHER PEOPLE, and it is therefore the
one that needs its own rules rather than the route boundary:

  * a FIXED FIELD WHITELIST — name, job title, department, photo, and the two
    links up and down. `_pb_card()` is the only shape that leaves this file,
    and there is no wage, no address, no phone in it that is not already the
    work number on a business card;
  * COMPANY SCOPE on every read, so a focus id from another tenant answers
    nothing rather than answering something;
  * CAPS on breadth and depth, because a company of four and a half thousand
    people has one node with two hundred children and a page that renders it
    is a page nobody can use.
"""

import logging
from datetime import date, timedelta

from urllib.parse import quote

from odoo import _, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

#: The org chart's ceilings. Breadth first: a manager with three hundred
#: reports is shown the first slice and TOLD there are more, which is honest;
#: silently truncating is what makes somebody believe their team is smaller
#: than it is.
ORG_MAX_CHILDREN = 60
ORG_MAX_SIBLINGS = 40
ORG_MAX_DEPTH = 12
ORG_MAX_SEARCH = 20

_OPEN_STATES = ('pending', 'in_progress', 'blocked')
_MAX_NOTE = 2000


class PbOnboardingPortal(CustomerPortal):

    # ------------------------------------------------------------- helpers
    def _ob_employee(self):
        """The OWN employee, from the session user. Never a parameter."""
        Emp = request.env['hr.employee'].sudo()
        emp = Emp.search([('user_id', '=', request.env.user.id),
                          ('company_id', '=', request.env.company.id)],
                         limit=1)
        return emp or Emp.search(
            [('user_id', '=', request.env.user.id)], limit=1)

    def _ob_case(self, emp):
        if not emp:
            return request.env['pb.journey.case'].browse()
        return request.env['pb.journey.case'].sudo().search(
            [('employee_id', '=', emp.id), ('case_type', '=', 'onboarding')],
            order='state, anchor_date desc, id desc', limit=1)

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'journey_task_count' in counters:
            emp = self._ob_employee()
            count = 0
            if emp:
                case = self._ob_case(emp)
                if case and case.state in ('draft', 'active', 'on_hold'):
                    count = len(case.task_ids.filtered(
                        lambda t: t.state in _OPEN_STATES))
            values['journey_task_count'] = count
        if 'buddy_count' in counters:
            emp = self._ob_employee()
            values['buddy_count'] = len(self._my_buddies(emp)) if emp else 0
        return values

    # =================================================================
    #  /my/journey — the timeline
    # =================================================================
    @http.route(['/my/journey'], type='http', auth='user', website=True)
    def portal_my_journey(self, **kw):
        emp = self._ob_employee()
        if not emp:
            return request.redirect('/my')
        case = self._ob_case(emp)
        values = {
            'page_name': 'journey',
            'employee': emp,
            'has_case': bool(case),
            'notice': _('That is noted — thank you.') if kw.get('ok') else '',
        }
        if case:
            values.update(self._journey_values(emp, case))
        else:
            values.update({'team': self._team_strip(emp),
                           'buddy': self._card(emp._pb_buddy_now()),
                           'hrbp': self._user_card(emp.hrbp_user_id)})
        return request.render('pb_onboarding.portal_my_journey', values)

    def _journey_values(self, emp, case):
        today = date.today()
        doj = case.anchor_date or case._joining_date()
        steps = []
        current_marked = False
        my_user = request.env.user
        for task in case.task_ids.sorted(
                key=lambda t: (t.due_date or date.max, t.sequence, t.id)):
            settled = task.state in ('done', 'skipped')
            # "Current" is the FIRST unsettled step, not every unsettled one.
            # A timeline that highlights nine things highlights nothing.
            is_current = not settled and not current_marked
            if is_current:
                current_marked = True
            mine = bool(
                (task.assignee_user_id and task.assignee_user_id.id
                 == my_user.id)
                or (task.assignee_rule == 'employee'
                    and emp.user_id and emp.user_id.id == my_user.id))
            steps.append({
                'id': task.id,
                'name': task.name or '',
                'description': task.description or '',
                'due': task.due_date,
                'state': task.state,
                'settled': settled,
                'done': task.state == 'done',
                'skipped': task.state == 'skipped',
                'current': is_current,
                'overdue': bool(not settled and task.due_date
                                and task.due_date < today),
                'mine': mine and not settled,
                'owner': task.assignee_user_id.name or '',
            })
        done = len([s for s in steps if s['settled']])
        return {
            'case': case,
            'doj': doj,
            'days': (doj - today).days if doj else None,
            'progress': case.progress,
            'ring': max(0, min(100, case.progress)),
            'done_count': done,
            'step_count': len(steps),
            'steps': steps,
            'open_mine': len([s for s in steps if s['mine']]),
            'buddy': self._card(emp._pb_buddy_now()),
            'hrbp': self._user_card(emp.hrbp_user_id),
            'team': self._team_strip(emp),
            'complete': emp.profile_complete_pct,
            'missing': emp.profile_missing or '',
            'batch': request.env['pb.orientation.batch'].sudo().search(
                [('attendee_ids', 'in', emp.id), ('state', '!=', 'cancelled')],
                order='batch_date', limit=1),
        }

    @http.route(['/my/journey/step/<int:task_id>/done'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_journey_step_done(self, task_id, **post):
        """The one write this page can make, checked three ways.

        The step must be on the caller's OWN journey, it must be theirs to do,
        and it must still be open. Any of those failing is a redirect, not an
        error — a portal page never shows a traceback.
        """
        emp = self._ob_employee()
        if not emp:
            return request.redirect('/my')
        task = request.env['pb.journey.task'].sudo().browse(
            int(task_id)).exists()
        if not task or task.case_id.employee_id.id != emp.id \
                or task.state not in _OPEN_STATES:
            return request.redirect('/my/journey')
        mine = (task.assignee_user_id
                and task.assignee_user_id.id == request.env.user.id) or (
            task.assignee_rule == 'employee')
        if not mine:
            return request.redirect('/my/journey')
        try:
            task.sudo().action_done(payload={'_portal': {
                'label': 'Marked done by', 'value': emp.name or ''}})
        except Exception:               # noqa: BLE001
            _logger.exception('pb_onboarding: portal step done %s', task_id)
            return request.redirect('/my/journey')
        return request.redirect('/my/journey?ok=1')

    # =================================================================
    #  /my/buddy — both sides of the same relationship
    # =================================================================
    def _my_buddies(self, emp):
        """The joiners this person is looking after, named or standing in."""
        if not emp:
            return request.env['hr.employee'].browse()
        Emp = request.env['hr.employee'].sudo()
        today = date.today()
        named = Emp.search([('buddy_id', '=', emp.id), ('active', '=', True)])
        cover = Emp.search([('buddy_temp_id', '=', emp.id),
                            ('active', '=', True)]).filtered(
            lambda e: (not e.buddy_temp_from or e.buddy_temp_from <= today)
            and (not e.buddy_temp_to or today <= e.buddy_temp_to))
        return named | cover

    @http.route(['/my/buddy'], type='http', auth='user', website=True)
    def portal_my_buddy(self, **kw):
        emp = self._ob_employee()
        if not emp:
            return request.redirect('/my')
        Checkin = request.env['pb.employee.checkin'].sudo()
        mine = self._my_buddies(emp)
        looking_after = []
        for joiner in mine:
            rows = Checkin.search(
                [('employee_id', '=', joiner.id), ('kind', '=', 'buddy')],
                order='scheduled_date')
            nxt = rows.filtered(lambda c: c.state == 'scheduled')[:1]
            looking_after.append({
                'card': self._card(joiner),
                'joined': joiner._pb_join_date(),
                'is_cover': bool(joiner.buddy_temp_id
                                 and joiner.buddy_temp_id.id == emp.id),
                'next': nxt.scheduled_date if nxt else False,
                'connects': [self._connect_row(c) for c in rows],
            })
        # The other side: my own buddy, and what we have talked about.
        my_buddy = emp._pb_buddy_now()
        my_connects = Checkin.search(
            [('employee_id', '=', emp.id), ('kind', '=', 'buddy')],
            order='scheduled_date') if my_buddy else Checkin.browse()
        return request.render('pb_onboarding.portal_my_buddy', {
            'page_name': 'buddy',
            'employee': emp,
            'looking_after': looking_after,
            'my_buddy': self._card(my_buddy),
            'my_connects': [self._connect_row(c) for c in my_connects],
            'temp': self._card(emp.buddy_temp_id),
            'temp_from': emp.buddy_temp_from,
            'temp_to': emp.buddy_temp_to,
            'colleagues': self._handover_options(emp),
            'notice': _('That is noted — thank you.') if kw.get('ok') else '',
            'problem': kw.get('problem') or '',
        })

    def _connect_row(self, checkin):
        return {
            'id': checkin.id,
            'date': checkin.scheduled_date,
            'state': checkin.state,
            'done': checkin.state == 'done',
            'notes': checkin.notes or '',
            'red': checkin.red_flag,
            'red_note': checkin.red_flag_note or '',
            'owner': checkin.owner_user_id.name or '',
            'due': bool(checkin.state == 'scheduled'
                        and checkin.scheduled_date
                        and checkin.scheduled_date <= date.today()),
        }

    def _handover_options(self, emp):
        """Who this person could hand the buddy job to — their own team.

        A whole-company picker on a portal page is a whole-company directory
        on a portal page, which is not what a temporary handover needs.
        """
        Emp = request.env['hr.employee'].sudo()
        domain = [('active', '=', True), ('id', '!=', emp.id),
                  ('company_id', '=', (emp.company_id
                                       or request.env.company).id)]
        if emp.department_id:
            domain.append(('department_id', '=', emp.department_id.id))
        elif emp.parent_id:
            domain.append(('parent_id', '=', emp.parent_id.id))
        else:
            return []
        return [{'id': e.id, 'name': e.name or ''}
                for e in Emp.search(domain, order='name', limit=50)]

    @http.route(['/my/buddy/connect/<int:checkin_id>'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_buddy_connect(self, checkin_id, **post):
        """Write down what was said — and raise a flag if it needs one."""
        emp = self._ob_employee()
        if not emp:
            return request.redirect('/my')
        row = request.env['pb.employee.checkin'].sudo().browse(
            int(checkin_id)).exists()
        mine = self._my_buddies(emp)
        if not row or row.kind != 'buddy' or row.employee_id.id not in mine.ids:
            return request.redirect('/my/buddy')
        try:
            row.action_done(
                notes=(post.get('notes') or '').strip()[:_MAX_NOTE],
                red_flag=bool(post.get('red')),
                red_flag_note=(post.get('red_note') or '').strip()[:200])
        except Exception:               # noqa: BLE001
            _logger.exception('pb_onboarding: buddy connect %s', checkin_id)
            return request.redirect('/my/buddy')
        return request.redirect('/my/buddy?ok=1')

    @http.route(['/my/buddy/handover'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_buddy_handover(self, **post):
        """Hand the buddy job over while I am away — for ONE of my joiners.

        The joiner id is accepted here and it is checked against the list this
        person actually looks after, which is the same boundary as everywhere
        else: a parameter is allowed only when the answer is re-derived from
        the session anyway.
        """
        emp = self._ob_employee()
        if not emp:
            return request.redirect('/my')
        mine = self._my_buddies(emp)
        try:
            joiner_id = int(post.get('joiner_id') or 0)
        except (TypeError, ValueError):
            joiner_id = 0
        if joiner_id not in mine.ids:
            return request.redirect('/my/buddy')
        joiner = request.env['hr.employee'].sudo().browse(joiner_id)
        try:
            joiner.set_temp_buddy(
                post.get('temp_id') or False,
                post.get('date_from') or False,
                post.get('date_to') or False)
        except Exception as err:        # noqa: BLE001 — say what went wrong
            # The page SAYS what was wrong rather than silently doing nothing:
            # "the last day cannot be before the first day" is a sentence the
            # person can act on, and a redirect that looks like a no-op is the
            # dead end safety rail 4 is about. The message is the one the model
            # raised, truncated and URL-escaped — never a traceback.
            _logger.warning('pb_onboarding: handover refused: %s', err)
            message = getattr(err, 'args', None) and str(err.args[0]) or str(err)
            return request.redirect(
                '/my/buddy?problem=%s' % quote(message[:160]))
        return request.redirect('/my/buddy?ok=1')

    # =================================================================
    #  /my/orgchart — the living org chart
    # =================================================================
    @http.route(['/my/orgchart'], type='http', auth='user', website=True)
    def portal_my_orgchart(self, **kw):
        emp = self._ob_employee()
        if not emp:
            return request.redirect('/my')
        Emp = request.env['hr.employee'].sudo()
        company = emp.company_id or request.env.company
        focus = emp
        raw_focus = kw.get('focus')
        if raw_focus:
            try:
                candidate = Emp.browse(int(raw_focus)).exists()
            except (TypeError, ValueError):
                candidate = Emp.browse()
            # COMPANY SCOPE. A focus id from anywhere else answers with the
            # caller's own node rather than with somebody else's people.
            if candidate and candidate.active \
                    and candidate.company_id.id == company.id:
                focus = candidate
        term = (kw.get('q') or '').strip()
        results = []
        if term:
            results = [self._card(e) for e in Emp.search(
                [('active', '=', True), ('company_id', '=', company.id),
                 ('name', 'ilike', term)], order='name',
                limit=ORG_MAX_SEARCH)]

        # ---- the path up to the top, capped so a cycle cannot hang a page ----
        chain, seen, node = [], set(), focus.parent_id
        while node and node.id not in seen and len(chain) < ORG_MAX_DEPTH:
            seen.add(node.id)
            chain.append(self._card(node))
            node = node.parent_id
        chain.reverse()

        children = Emp.search(
            [('parent_id', '=', focus.id), ('active', '=', True),
             ('company_id', '=', company.id)],
            order='name', limit=ORG_MAX_CHILDREN + 1)
        more_children = len(children) > ORG_MAX_CHILDREN
        children = children[:ORG_MAX_CHILDREN]

        siblings = Emp.browse()
        more_siblings = False
        if focus.parent_id:
            siblings = Emp.search(
                [('parent_id', '=', focus.parent_id.id),
                 ('id', '!=', focus.id), ('active', '=', True),
                 ('company_id', '=', company.id)],
                order='name', limit=ORG_MAX_SIBLINGS + 1)
            more_siblings = len(siblings) > ORG_MAX_SIBLINGS
            siblings = siblings[:ORG_MAX_SIBLINGS]

        return request.render('pb_onboarding.portal_my_orgchart', {
            'page_name': 'orgchart',
            'employee': emp,
            'me_id': emp.id,
            'focus': self._card(focus),
            'manager': self._card(focus.parent_id),
            'chain': chain,
            'children': [self._card(e) for e in children],
            'siblings': [self._card(e) for e in siblings],
            'more_children': more_children,
            'more_siblings': more_siblings,
            'max_children': ORG_MAX_CHILDREN,
            'term': term,
            'results': results,
            # The count is computed HERE, not in the template: QWeb's eval
            # context is not Python's and a builtin that happens to work today
            # is a page that breaks on an upgrade.
            'result_count': len(results),
            'company_name': company.name or '',
        })

    # ------------------------------------------------------------- the cards
    def _card(self, employee):
        """The ONLY employee shape that leaves this file (whitelist)."""
        if not employee:
            return None
        try:
            return employee.sudo()._pb_card()
        except Exception:               # noqa: BLE001
            _logger.exception('pb_onboarding: card for employee %s',
                              employee.id)
            return None

    def _user_card(self, user):
        if not user:
            return None
        parts = [p for p in (user.name or '').split() if p]
        return {
            'id': user.id,
            'name': user.name or '',
            'initials': ((parts[0][0] if parts else '?')
                         + (parts[-1][0] if len(parts) > 1 else '')).upper(),
            'email': user.email or '',
            'job': _('HR business partner'),
            'dept': '',
            'phone': '',
            'avatar': '/web/image/res.users/%s/avatar_128' % user.id,
        }

    def _team_strip(self, emp):
        """The manager and the people beside them — a face, not a directory."""
        Emp = request.env['hr.employee'].sudo()
        out = []
        if emp.parent_id:
            card = self._card(emp.parent_id)
            if card:
                card['role'] = _('Manager')
                out.append(card)
            peers = Emp.search(
                [('parent_id', '=', emp.parent_id.id), ('id', '!=', emp.id),
                 ('active', '=', True)], order='name', limit=11)
            for peer in peers:
                card = self._card(peer)
                if card:
                    card['role'] = ''
                    out.append(card)
        return out
