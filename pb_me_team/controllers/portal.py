# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`/my/team…` — a manager's area on the employee home.

THE ROUTE IS THE GATE. The manager is resolved from the SESSION on every
request (`_ess_employee`); no route accepts an employee id. The team is the
people whose record names that employee as their manager. A request is
opened through the approvals inbox as the caller, so a request id in a URL
buys nothing the inbox would not show anyway, and a decision is the engine's
to allow.

A REFUSAL RE-RENDERS, IT DOES NOT REDIRECT: the engine's reason is a sentence,
and a sentence carried in a query string is one somebody else could write onto
the page. Success redirects with a short code only.
"""

import logging
import uuid

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from odoo.addons.pb_me_portal.controllers.portal import PbMePortal

_logger = logging.getLogger(__name__)

#: The codes a successful decision may come back with.
DONE_CODES = ('approve', 'return', 'reject')


class PbMeTeamPortal(PbMePortal):

    def _pbmt(self):
        return request.env['pb.me.team']

    # ------------------------------------------------------------ the team
    @http.route(['/my/team'], type='http', auth='user', website=True)
    def portal_my_team(self, away=None, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        return self._team_page(emp, away_done=away if away in ('set', 'ended')
                               else '')

    def _team_page(self, emp, away_done='', away_problem=''):
        Team = self._pbmt()
        if not Team.is_manager(emp):
            return request.render('pb_me_team.portal_my_team_none',
                                  {'page_name': 'my_team'})
        safe = self._pbmt_safe
        return request.render('pb_me_team.portal_my_team', {
            'page_name': 'my_team',
            'today': safe(lambda: Team.today(emp),
                          {'rows': [], 'counts': {}, 'clock': False,
                           'holiday': None, 'date': None,
                           'size': len(Team.team(emp))}),
            'calendar': safe(lambda: Team.calendar(emp),
                             {'days': [], 'rows': [], 'clashes': [], 'size': 0}),
            'probation': safe(lambda: Team.probation(emp), []),
            'moments': safe(lambda: Team.moments(emp), []),
            'chart': safe(lambda: Team.chart(emp), None),
            'overtime': safe(lambda: Team.overtime(emp), None),
            'gaps': safe(lambda: Team.gaps(emp), None),
            'hours': safe(lambda: Team.hours(emp), None),
            'balances': safe(lambda: Team.balances(emp), []),
            'joiners': safe(lambda: Team.joiners(emp), []),
            'handover': safe(lambda: Team.handover(emp), None),
            'approvals_waiting': Team.my_turn_count(),
            'links': self._pbmt_links(),
            'away_done': away_done,
            'away_problem': away_problem,
        })

    def _pbmt_safe(self, fn, default):
        """One section of the page, isolated: a failure loses that section
        (logged), never the page."""
        try:
            with request.env.cr.savepoint():
                return fn()
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_me_team: a section of /my/team failed',
                            exc_info=True)
            return default

    def _pbmt_links(self):
        """The other manager pages that exist on this database."""
        Mod = request.env['ir.module.module'].sudo()
        on = set(Mod.search([('name', 'in', ('pb_training', 'pb_hiring',
                                             'pb_onboarding')),
                             ('state', '=', 'installed')]).mapped('name'))
        return {'training': 'pb_training' in on, 'hiring': 'pb_hiring' in on,
                'orgchart': 'pb_onboarding' in on}

    # ------------------------------------------------------- I'm away
    @http.route(['/my/team/away'], type='http', auth='user', website=True,
                methods=['POST'])
    def portal_my_team_away(self, **post):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        try:
            with request.env.cr.savepoint():
                if post.get('end'):
                    self._pbmt().end_handover(post.get('end'))
                    code = 'ended'
                else:
                    self._pbmt().set_handover(
                        post.get('delegate'), post.get('date_from'),
                        post.get('date_to'), post.get('reason'))
                    code = 'set'
        except (AccessError, UserError, ValidationError) as err:
            _logger.info('pb_me_team: a hand-over was refused (%s)', err)
            return self._team_page(emp, away_problem=str(err))
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_me_team: a hand-over failed', exc_info=True)
            return self._team_page(emp, away_problem=request.env._(
                "That did not go through. Nothing was changed — please try "
                "again."))
        return request.redirect('/my/team?away=%s#away' % code)

    # ----------------------------------------------------------- approvals
    @http.route(['/my/team/approvals'], type='http', auth='user', website=True)
    def portal_my_team_approvals(self, tab='mine', ok=None, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        data = self._pbmt().approvals(tab)
        return request.render('pb_me_team.portal_my_team_approvals', {
            'page_name': 'team_approvals',
            'ap': data,
            'done': ok if ok in DONE_CODES else '',
        })

    @http.route(['/my/team/approvals/<int:request_id>'], type='http',
                auth='user', website=True)
    def portal_my_team_approval(self, request_id, **kw):
        return self._approval_page(request_id)

    def _approval_page(self, request_id, problem='', reason='', action=''):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        req = self._pbmt().approval(emp, request_id)
        if not req:
            return request.render('pb_me_team.portal_team_approval_missing',
                                  {'page_name': 'team_approval'}, status=404)
        return request.render('pb_me_team.portal_my_team_approval', {
            'page_name': 'team_approval',
            'req': req,
            'problem': problem,
            'reason': reason,
            'action': action,
            'idem': uuid.uuid4().hex,
        })

    @http.route(['/my/team/approvals/<int:request_id>/decide'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_my_team_decide(self, request_id, **post):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        action = post.get('action') or ''
        reason = (post.get('reason') or '')[:2000]
        try:
            # a refusal rolls back to here, so the page re-renders on a
            # clean transaction
            with request.env.cr.savepoint():
                self._pbmt().decide(
                    request_id, post.get('step_key'), action, reason,
                    post.get('lock_revision'), post.get('idem'),
                    use_exception=post.get('use_exception') == '1')
        except (AccessError, UserError, ValidationError) as err:
            _logger.info('pb_me_team: a decision on request %s was refused '
                         '(%s)', request_id, err)
            return self._approval_page(request_id, problem=str(err),
                                       reason=reason, action=action)
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_me_team: a decision on request %s failed',
                            request_id, exc_info=True)
            return self._approval_page(
                request_id, problem=request.env._(
                    "That did not go through. Nothing was changed — "
                    "please try again."),
                reason=reason, action=action)
        return request.redirect('/my/team/approvals?ok=%s' % action)
