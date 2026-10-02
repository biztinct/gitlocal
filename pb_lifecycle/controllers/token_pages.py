# -*- coding: utf-8 -*-
"""The two login-less pages.

Modelled point for point on `pb_ess_workforce/controllers/ack.py`, which is the
one login-less precedent this codebase trusts:

  * an unguessable token — 24 bytes of `secrets.token_urlsafe`, minted per TASK
    and per REQUEST, so a leaked link answers one question for one person;
  * single-purpose routes — a GET to look and a POST to answer, and nothing else
    lives under either prefix;
  * no data beyond the target record — the page shows the step's own wording,
    the first name of the person it is about, and nothing else. Not an id, not a
    department, not a neighbouring step, not a link into the backend;
  * ONE page for every outcome, so a stranger probing the URL space learns
    nothing: an unknown token, a finished one and a cancelled journey all get
    the same courteous "this link is closed".

The controller is sudo because the visitor is the public user with no ACL on
anything. Every write behind it goes through the model's own action, touches
one record, and can only move that record forward.
"""

import logging

from odoo import _, http
from odoo.http import request

_logger = logging.getLogger(__name__)

#: A single answer is capped so a public form cannot be used to post a book.
_MAX_ANSWER = 4000


def _answers_from_post(questions, post):
    out = {}
    for q in questions:
        raw = post.get('q_%s' % q['key'], '')
        if isinstance(raw, str):
            raw = raw.strip()[:_MAX_ANSWER]
        out[q['key']] = {'label': q['label'], 'value': raw}
    note = (post.get('note') or '').strip()[:_MAX_ANSWER]
    if note:
        out['_note'] = {'label': 'Note', 'value': note}
    return out


class PbLifecycleTokenPages(http.Controller):

    # ------------------------------------------------------------ the steps
    def _task_page(self, token, task, status):
        emp = task.employee_id if task else None
        first = (emp.name or '').split(' ')[-1] if emp else ''
        return request.render('pb_lifecycle.journey_task_page', {
            'status': status,
            # echoed back so the form posts to the same token — never
            # re-derived from the record, whose token is a restricted field.
            'token': token,
            'has_task': bool(task),
            'task': {
                'name': task.name or '',
                'description': task.description or '',
                'kind': task.step_kind or 'task',
                'due': str(task.due_date) if task and task.due_date else '',
                'who': first,
                'company': (task.company_id.name
                            if task and task.company_id else ''),
            } if task else {},
            'questions': task.questions() if (task and status == 'ok'
                                              and task.step_kind == 'form')
            else [],
            # ONE sentence, one msgid, and deliberately NOT "before your first
            # day": the same page answers a joiner's confirmation and a
            # leaver's clearance, and a leaver told about their first day reads
            # it as a mistake and stops trusting the rest of the page.
            'greeting': _('Hi %(name)s — there is one thing to confirm.',
                          name=first) if first else '',
        })

    @http.route('/journey/t/<string:token>', type='http', auth='public',
                website=True, sitemap=False)
    def journey_task_view(self, token, **kw):
        task, status = request.env['pb.journey.task'].sudo()._task_for_token(
            token)
        if kw.get('done') == '1' and status in ('used', 'ok'):
            status = 'thanks'
        return self._task_page(token, task, status)

    @http.route('/journey/t/<string:token>/submit', type='http',
                auth='public', website=True, methods=['POST'], csrf=False,
                sitemap=False)
    def journey_task_submit(self, token, **post):
        """csrf=False for the reason the shift acknowledgment is: the visitor
        has no session to carry a token in. The write is idempotent — a replay
        finds the step already done and writes nothing."""
        task, status = request.env['pb.journey.task'].sudo()._task_for_token(
            token)
        if status == 'ok':
            try:
                payload = _answers_from_post(task.questions(), post) \
                    if task.step_kind == 'form' else {
                        '_confirmed': {'label': 'Confirmed', 'value': 'yes'},
                        '_note': {'label': 'Note',
                                  'value': (post.get('note') or '').strip()[
                                      :_MAX_ANSWER]},
                    }
                task.sudo().action_done(payload=payload)
            except Exception:
                _logger.exception('pb_lifecycle: token submit failed')
        return request.redirect('/journey/t/%s?done=1' % token)

    # --------------------------------------------------------- the feedback
    @http.route('/journey/f/<string:token>', type='http', auth='public',
                website=True, sitemap=False)
    def journey_feedback_view(self, token, **kw):
        req, status = request.env[
            'pb.feedback.request'].sudo()._request_for_token(token)
        if kw.get('done') == '1' and status in ('used', 'ok'):
            status = 'thanks'
        return self._feedback_page(token, req, status)

    def _feedback_page(self, token, req, status):
        subject = req.subject_employee_id if req else None
        return request.render('pb_lifecycle.journey_feedback_page', {
            'status': status,
            'token': token,
            'has_request': bool(req),
            # NOT `request`: QWeb already has one, and ours would shadow the
            # HTTP request the layout itself reads — the page then dies with
            # "'Request' object is not subscriptable" and the visitor gets a
            # 500 instead of a form.
            'feedback': {
                'about': (subject.name or '') if subject else '',
                'window_end': str(req.window_end)
                if (req and req.window_end) else '',
                'company': (req.company_id.name
                            if req and req.company_id else ''),
            } if req else {},
            'questions': req.questions() if (req and status == 'ok') else [],
        })

    @http.route('/journey/f/<string:token>/submit', type='http',
                auth='public', website=True, methods=['POST'], csrf=False,
                sitemap=False)
    def journey_feedback_submit(self, token, **post):
        req, status = request.env[
            'pb.feedback.request'].sudo()._request_for_token(token)
        if status == 'ok':
            try:
                req.sudo().submit_answers(
                    _answers_from_post(req.questions(), post))
            except Exception:
                _logger.exception('pb_lifecycle: feedback submit failed')
        return request.redirect('/journey/f/%s?done=1' % token)
