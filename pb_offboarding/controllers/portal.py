# -*- coding: utf-8 -*-
"""`/my/resignation` — the one page the person leaving actually uses.

THE ROUTE IS THE GATE, exactly as P2 and P3 established. The employee is
re-resolved from the SESSION user on every request and no route accepts an
employee id, so a crafted URL can never reach another person's resignation.
Everything past that point is read and written under `sudo()` — the doctrine
`pb_me_portal` set for documents and payslips — because the record has already
been proved to be the caller's own.

The two writes this page can make are both re-checked on the way in:

  * SUBMIT creates a resignation for the SESSION EMPLOYEE and nobody else, and
    refuses when one is already live. The employee id is never taken from the
    form: a forged one would plant a resignation on a colleague's record and
    bait HR into approving it (the same hole `pb_me_portal` closed on profile
    change requests).
  * WITHDRAW loads by id, checks the record belongs to the session employee,
    and then hands the decision to the MODEL — `action_withdraw` is where "only
    before HR agrees" lives, and a second copy of that rule here would be a
    second rule to keep in step.

A portal page never shows a traceback. Every refusal is a redirect carrying a
sentence the person can read.
"""

import logging
from datetime import date

from urllib.parse import quote

from odoo import _, fields, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

_OPEN_STATES = ('pending', 'in_progress', 'blocked')
_LIVE = ('draft', 'submitted', 'manager_ok', 'approved')
_MAX_REASON = 4000


class PbOffboardingPortal(CustomerPortal):

    # ------------------------------------------------------------- helpers
    def _off_employee(self):
        """The OWN employee, from the session user. Never a parameter."""
        Emp = request.env['hr.employee'].sudo()
        emp = Emp.search([('user_id', '=', request.env.user.id),
                          ('company_id', '=', request.env.company.id)],
                         limit=1)
        return emp or Emp.search(
            [('user_id', '=', request.env.user.id)], limit=1)

    def _off_case(self, emp):
        if not emp:
            return request.env['pb.journey.case'].browse()
        return request.env['pb.journey.case'].sudo().search(
            [('employee_id', '=', emp.id), ('case_type', '=', 'offboarding')],
            order='state, anchor_date desc, id desc', limit=1)

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'resignation_count' in counters:
            emp = self._off_employee()
            count = 0
            if emp:
                count = request.env['pb.resignation'].sudo().search_count([
                    ('employee_id', '=', emp.id),
                    ('state', 'in', _LIVE),
                ])
            values['resignation_count'] = count
        return values

    # =================================================================
    #  /my/resignation
    # =================================================================
    @http.route(['/my/resignation'], type='http', auth='user', website=True)
    def portal_my_resignation(self, **kw):
        emp = self._off_employee()
        if not emp:
            return request.redirect('/my')
        resignation = request.env['pb.resignation'].for_employee(emp)
        live = bool(resignation and resignation.state in _LIVE)
        prefill = request.env['pb.resignation'].sudo().prefill_for(emp)
        policy = request.env['pb.notice.policy'].sudo().policy_for(emp)
        values = {
            'page_name': 'resignation',
            'employee': emp,
            'resignation': resignation if resignation else None,
            'live': live,
            'notice_days': prefill['days'],
            'suggested_lwd': prefill['lwd'],
            'policy_name': policy.name if policy else '',
            'today': fields.Date.today(),
            'notice': _('That is done — thank you.') if kw.get('ok') else '',
            'problem': kw.get('problem') or '',
        }
        if live:
            values.update(self._exit_values(emp, resignation))
        return request.render('pb_offboarding.portal_my_resignation', values)

    def _exit_values(self, emp, resignation):
        """What is left to do before the last day, from the leaver's side."""
        case = resignation.case_id or self._off_case(emp)
        today = date.today()
        steps, mine = [], 0
        if case:
            for task in case.task_ids.sorted(
                    key=lambda t: (t.due_date or date.max, t.sequence, t.id)):
                is_mine = bool(
                    (task.assignee_user_id
                     and task.assignee_user_id.id == request.env.user.id)
                    or (task.assignee_rule == 'employee'
                        and emp.user_id
                        and emp.user_id.id == request.env.user.id))
                settled = task.state in ('done', 'skipped')
                # The leaver's own checklist, not HR's. A step that belongs to
                # somebody else is shown ONLY when it is something they can see
                # the point of — returning a laptop, an exit conversation — and
                # never the internal ones (the settlement letter, the paperwork
                # a month later), which would read as work they had left undone.
                visible = is_mine or task.blocking_ff
                if not visible:
                    continue
                if is_mine and not settled:
                    mine += 1
                steps.append({
                    'id': task.id,
                    'name': task.name or '',
                    'description': task.description or '',
                    'due': task.due_date,
                    'settled': settled,
                    'mine': is_mine and not settled,
                    'overdue': bool(not settled and task.due_date
                                    and task.due_date < today),
                })
        assets = request.env['pb.asset'].sudo().open_items_for(emp.id)
        feedback = request.env['pb.feedback.request'].sudo().search(
            [('case_id', '=', case.id), ('kind', '=', 'exit')], limit=1) \
            if case else request.env['pb.feedback.request'].browse()
        lwd = resignation.approved_lwd or resignation.requested_lwd
        return {
            'case': case or None,
            'steps': steps,
            'open_mine': mine,
            'assets': assets.get('tangible') or [],
            'lwd': lwd,
            'days_left': (lwd - today).days if lwd else None,
            'feedback_link': (feedback._token_url()
                              if feedback and feedback.state != 'submitted'
                              else ''),
            'feedback_done': bool(feedback and feedback.state == 'submitted'),
            'trail': self._trail(resignation),
        }

    def _trail(self, resignation):
        """The four stages, and which one this resignation has reached."""
        order = ['draft', 'submitted', 'manager_ok', 'approved']
        labels = {
            'draft': _('Written'),
            'submitted': _('With your manager'),
            'manager_ok': _('With HR'),
            'approved': _('Agreed'),
        }
        state = resignation.state
        if state in ('refused', 'withdrawn'):
            reached = len(order)
        else:
            reached = order.index(state) if state in order else 0
        return [{'key': key, 'label': labels[key],
                 'done': index < reached or state == 'approved',
                 'current': index == reached and state not in
                 ('refused', 'withdrawn')}
                for index, key in enumerate(order)]

    # ----------------------------------------------------------- the writes
    @http.route(['/my/resignation/submit'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_resignation_submit(self, **post):
        """File a resignation for the SESSION EMPLOYEE and nobody else."""
        emp = self._off_employee()
        if not emp:
            return request.redirect('/my')
        Resignation = request.env['pb.resignation'].sudo()
        live = Resignation.search([('employee_id', '=', emp.id),
                                   ('state', 'in', _LIVE)], limit=1)
        if live:
            return self._problem(_(
                "You already have a resignation on file. Take that one back "
                "first if you want to change it."))
        reason = (post.get('reason') or '').strip()[:_MAX_REASON]
        if not reason:
            return self._problem(_(
                "Write a line about why you are leaving — your manager and HR "
                "will read it."))
        lwd = self._read_date(post.get('lwd'))
        if not lwd:
            lwd = Resignation.prefill_for(emp)['lwd']
        if lwd <= fields.Date.today():
            return self._problem(_(
                "Your last working day has to be in the future. Pick a later "
                "date."))
        try:
            resignation = Resignation.create({
                'employee_id': emp.id,
                'reason_text': reason,
                'requested_lwd': lwd,
                'notice_days': request.env['pb.notice.policy'].sudo(
                ).days_for(emp),
                'source': 'portal',
                'company_id': (emp.company_id or request.env.company).id,
            })
            resignation.action_submit()
        except (UserError, AccessError) as err:
            # The page SAYS what was wrong rather than silently doing nothing —
            # a redirect that looks like a no-op is a dead end. The message is
            # the one the model raised, truncated and escaped, never a
            # traceback.
            _logger.warning('pb_offboarding: resignation refused: %s', err)
            return self._problem(_message(err))
        except Exception:               # noqa: BLE001
            _logger.exception('pb_offboarding: portal resignation for '
                              'employee %s', emp.id)
            return self._problem(_(
                "That could not be saved. Try again in a moment, or speak to "
                "HR."))
        return request.redirect('/my/resignation?ok=1')

    @http.route(['/my/resignation/withdraw'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_resignation_withdraw(self, **post):
        """Take it back. The MODEL decides whether it is still allowed."""
        emp = self._off_employee()
        if not emp:
            return request.redirect('/my')
        try:
            resignation_id = int(post.get('resignation_id') or 0)
        except (TypeError, ValueError):
            resignation_id = 0
        resignation = request.env['pb.resignation'].sudo().browse(
            resignation_id).exists()
        # The id is accepted, and then the answer is re-derived from the
        # session anyway: a resignation that is not this person's is not found.
        if not resignation or resignation.employee_id.id != emp.id:
            return request.redirect('/my/resignation')
        try:
            resignation.action_withdraw(
                note=(post.get('note') or '').strip()[:400] or False)
        except (UserError, AccessError) as err:
            _logger.info('pb_offboarding: withdrawal refused: %s', err)
            return self._problem(_message(err))
        except Exception:               # noqa: BLE001
            _logger.exception('pb_offboarding: portal withdrawal %s',
                              resignation_id)
            return self._problem(_(
                "That could not be done. Speak to HR and they will sort it "
                "out."))
        return request.redirect('/my/resignation?ok=1')

    # -------------------------------------------------------------- plumbing
    @staticmethod
    def _problem(message):
        return request.redirect(
            '/my/resignation?problem=%s' % quote(str(message)[:300]))

    @staticmethod
    def _read_date(raw):
        if not raw:
            return False
        try:
            return fields.Date.to_date(raw)
        except (ValueError, TypeError):
            return False


def _message(err):
    """The sentence a model raised, without the exception's decoration."""
    args = getattr(err, 'args', None)
    return str(args[0]) if args else str(err)
