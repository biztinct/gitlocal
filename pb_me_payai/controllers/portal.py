# -*- coding: utf-8 -*-
"""`/my/ask-policy` — PayAI for employees, answered from company policies.

THE ROUTE IS THE GATE (ledger T-R11). The employee is re-resolved from the
SESSION on every request; no route accepts an employee id. A person whose
company has not switched PayAI on, has no AI account, or has published no
policy is sent back to their home: they see nothing of it (E5).

"Ask HR" with the question filled in: `/my/ask-hr/new?question=…` opens
Ask HR's own new-question form with the subject and details written in. The
form is still the person's to read, change and send; nothing is sent for
them. (pb_ask_hr's route is extended here by inheritance, never edited.)

Helpers carry the `_pbpa_` prefix: every portal controller of every module is
merged into ONE class.
"""
import logging
from urllib.parse import urlencode as url_encode

from odoo import http
from odoo.http import request

from odoo.addons.pb_ask_hr.controllers.portal import PbAskHrPortal

from ..models.policy_answer import MAX_QUESTION

_logger = logging.getLogger(__name__)


class PbMePayaiPortal(PbAskHrPortal):

    def _pbpa_ready(self, emp):
        try:
            return bool(emp) and request.env['pb.policy.answer']._ready_for(emp)
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_me_payai: readiness check failed', exc_info=True)
            return False

    def _pbpa_ask_hr_url(self, question):
        return '/my/ask-hr/new?' + url_encode({'category': 'other',
                                               'question': question or ''})

    def _pbpa_page(self, emp, result=None):
        docs = request.env['pb.policy.answer']._documents(emp)
        values = {
            'page_name': 'pbpa_ask',
            'policies': [d.name for d in docs if d.section_ids][:30],
            'result': result,
            'ask_hr_url': self._pbpa_ask_hr_url(result['question'] if result else ''),
            'max_question': MAX_QUESTION,
        }
        return request.render('pb_me_payai.portal_ask_policy', values)

    # ------------------------------------------------------ home counter
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'pbpa_count' in counters:
            values['pbpa_count'] = 1 if self._pbpa_ready(self._ess_employee()) else 0
        return values

    # ============================================================== page
    @http.route(['/my/ask-policy'], type='http', auth='user', website=True,
                methods=['GET'])
    def portal_ask_policy(self, **kw):
        emp = self._ess_employee()
        if not self._pbpa_ready(emp):
            return request.redirect('/my')
        return self._pbpa_page(emp)

    @http.route(['/my/ask-policy'], type='http', auth='user', website=True,
                methods=['POST'])
    def portal_ask_policy_post(self, **post):
        emp = self._ess_employee()
        if not self._pbpa_ready(emp):
            return request.redirect('/my')
        question = (post.get('question') or '').strip()[:MAX_QUESTION]
        try:
            result = request.env['pb.policy.answer'].ask(emp, question)
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_me_payai: a question failed', exc_info=True)
            result = {'state': 'failed', 'answer': '', 'sources': [],
                      'question': question}
        return self._pbpa_page(emp, result)

    # ===================================== Ask HR, with the question in it
    @http.route()
    def portal_ask_hr_new(self, category=None, **kw):
        question = (kw.get('question') or '').strip()[:MAX_QUESTION]
        if not question or not self._ess_employee():
            return super().portal_ask_hr_new(category=category, **kw)
        subject = question if len(question) <= 120 else question[:117].rstrip() + '...'
        return self._ask_hr_render_new({'category': 'other', 'subject': subject,
                                        'text': question})
