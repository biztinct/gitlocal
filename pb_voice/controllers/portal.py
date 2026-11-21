# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`/my/voice…` — surveys on My Payobook (owner ruling P5: the ONLY place
people answer; no tablet, no paper).

THE ROUTE IS THE GATE: the employee comes from the SESSION on every request
(`_ess_employee`); no route accepts an employee id. `pb.voice.round` checks
again that the employee is the caller's own and was asked in the round.

NOTHING HERE LOGS OR TRACKS WHO ANSWERED: no `track=True` (no page-view
record with the visitor), no log line naming the person, and a refusal
re-renders the form rather than redirecting with words in the address.
"""
import logging

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from odoo.addons.pb_me_portal.controllers.portal import PbMePortal
from odoo.addons.pb_me_team.controllers.portal import PbMeTeamPortal

_logger = logging.getLogger(__name__)


class PbVoicePortal(PbMePortal):

    def _voice_list_values(self, emp, done=''):
        Round = request.env['pb.voice.round']
        rows = (Round.voice_my_rounds(emp) or []) if emp else []
        plans = request.env['pb.voice.action'].sudo().search(
            [('owner_id', '=', request.env.uid)], order='state, date_due, id')
        return {
            'page_name': 'my_voice',
            'pbv_linked': bool(emp),
            'pbv_waiting': [r for r in rows if r['state'] == 'open' and not r['answered']],
            'pbv_answered': [r for r in rows if r['state'] == 'open' and r['answered']],
            'pbv_closed': [r for r in rows if r['state'] == 'closed'][:6],
            'pbv_plans': [p._voice_dict() for p in plans],
            'pbv_done': done,
        }

    @http.route(['/my/voice'], type='http', auth='user', website=True,
                sitemap=False)
    def portal_my_voice(self, done=None, **kw):
        emp = self._ess_employee()
        return request.render('pb_voice.portal_my_voice', self._voice_list_values(
            emp, done=done if done in ('thanks', 'plan') else ''))

    @http.route(['/my/voice/<int:round_id>'], type='http', auth='user',
                website=True, sitemap=False, methods=['GET'])
    def portal_my_voice_round(self, round_id, **kw):
        return self._voice_form_page(round_id)

    def _voice_form_page(self, round_id, problem='', posted=None):
        emp = self._ess_employee()
        Round = request.env['pb.voice.round']
        rnd = Round.sudo().browse(int(round_id)).exists()
        form = None
        if emp and rnd:
            try:
                form = rnd.with_user(request.env.user).voice_form(emp)
            except Exception:               # noqa: BLE001 — never a 500 on /my
                _logger.warning('pb_voice: the survey form failed', exc_info=True)
                form = None
        if not form:
            form = {'ok': False, 'why': request.env._(
                "You are not asked in this survey.")}
        return request.render('pb_voice.portal_my_voice_form', {
            'page_name': 'my_voice_form',
            'pbv': form,
            'pbv_problem': problem,
            'pbv_posted': posted or {},
        })

    @http.route(['/my/voice/<int:round_id>/answer'], type='http', auth='user',
                website=True, sitemap=False, methods=['POST'])
    def portal_my_voice_answer(self, round_id, **post):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my/voice')
        answers, comments = {}, {}
        for name, value in post.items():
            if name.startswith('q_'):
                answers[name[2:]] = value
            elif name.startswith('t_'):
                comments[name[2:]] = value
        rnd = request.env['pb.voice.round'].sudo().browse(int(round_id)).exists()
        if not rnd:
            return request.redirect('/my/voice')
        try:
            with request.env.cr.savepoint():
                rnd.with_user(request.env.user).voice_submit(emp, answers, comments)
        except (AccessError, UserError) as err:
            return self._voice_form_page(round_id, problem=str(err),
                                         posted=dict(answers, **{
                                             't' + k: v for k, v in comments.items()}))
        except Exception:                   # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_voice: an answer could not be taken',
                            exc_info=False)
            return self._voice_form_page(round_id, problem=request.env._(
                "That did not go through. Nothing was saved — please try "
                "again."))
        return request.redirect('/my/voice?done=thanks')

    @http.route(['/my/voice/plan/<int:plan_id>'], type='http', auth='user',
                website=True, sitemap=False, methods=['POST'])
    def portal_my_voice_plan(self, plan_id, **post):
        """The owner updates their OWN action plan (state + progress)."""
        plan = request.env['pb.voice.action'].sudo().browse(int(plan_id)).exists()
        if not plan or plan.owner_id.id != request.env.uid:
            return request.redirect('/my/voice')
        vals = {}
        if post.get('state') in ('open', 'doing', 'done'):
            vals['state'] = post['state']
        if 'progress' in post:
            vals['progress'] = (post.get('progress') or '').strip()[:2000]
        if vals:
            try:
                with request.env.cr.savepoint():
                    # owner proven above; only state and progress are passed
                    plan.write(vals)
            except (AccessError, UserError):
                return request.redirect('/my/voice#plans')
        return request.redirect('/my/voice?done=plan#plans')


class PbVoiceTeamPortal(PbMeTeamPortal):
    """The "Team voice" card on /my/team: the page's own values, plus ours
    (the template is inherited by xpath, never edited — FACTS §6)."""

    def _team_page(self, emp, away_done='', away_problem=''):
        response = super()._team_page(emp, away_done=away_done,
                                      away_problem=away_problem)
        qcontext = getattr(response, 'qcontext', None)
        if qcontext is not None:
            card = None
            try:
                with request.env.cr.savepoint():
                    card = request.env['pb.voice'].manager_card(emp)
            except Exception:               # noqa: BLE001 — never a 500 on /my
                _logger.warning('pb_voice: the team voice card failed',
                                exc_info=True)
            qcontext['pbv_team'] = card
        return response


class PbVoiceExport(http.Controller):

    @http.route(['/pb_voice/results/<int:round_id>.xlsx'], type='http',
                auth='user', methods=['GET'])
    def voice_results_xlsx(self, round_id, **kw):
        try:
            data = request.env['pb.voice'].results_xlsx(round_id)
        except (AccessError, UserError):
            return request.not_found()
        name = 'survey-results-%s.xlsx' % int(round_id)
        return request.make_response(data, headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.'
                             'spreadsheetml.sheet'),
            ('Content-Disposition', 'attachment; filename="%s"' % name),
        ])
