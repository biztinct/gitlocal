from odoo import http
from odoo.http import request
from odoo.exceptions import UserError
from odoo.addons.pb_lifecycle.controllers.token_pages import PbLifecycleTokenPages, _answers_from_post


class ProbationFeedbackJourney(PbLifecycleTokenPages):
    @http.route()
    def journey_feedback_submit(self, token, **post):
        record, status = request.env['pb.feedback.request'].sudo()._request_for_token(token)
        if status == 'ok' and record.probation_review_id and 'sop_' in (record.questions_json or ''):
            try:
                record.submit_answers(_answers_from_post(record.questions(), post))
            except UserError as error:
                response = self._feedback_page(token, record, 'ok')
                response.qcontext['sop_error'] = str(error)
                return response
            return request.redirect('/journey/f/%s?done=1' % token)
        return super().journey_feedback_submit(token, **post)
