# -*- coding: utf-8 -*-
"""RECRUIT P3 — the two pages a line manager opens from an email.

`/hiring/r/<token>` — THE HIRING REQUEST, one page, saving as they type
(G-13). `/hiring/j/<token>` — THE ADVERT, shared for their comment (G-17).

THE LINK IS THE CREDENTIAL, exactly as the other hiring token pages
(`token_pages.py`): 24 bytes of `secrets.token_urlsafe`, minted per role (or
per advert version), single-purpose routes, no ids in the URL, and one
courteous "this link has closed" for an unknown key and a closed role alike.
A line manager may be a PORTAL user or have no login at all (RECRUIT P3
non-negotiable): nothing here asks anybody to sign in.

Writes go through the model's own whitelisted `_page_save` (typed at the
door, tracking off) and `_request_send_in`; the controller only moves bytes.
Autosave is rate-limited per token (a public JSON door must not be a way to
hammer the database).
"""

import logging
import time
from collections import deque

from odoo import SUPERUSER_ID, _, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from ..models.hiring_common import ROLE_TYPES

_logger = logging.getLogger(__name__)

#: Autosave budget per token: this many saves in this many seconds. A person
#: typing with a 700 ms debounce never meets it; a loop does.
_SAVE_MAX = 120
_SAVE_WINDOW = 300
_SAVES = {}

_FILE_MAX_BYTES = 10 * 1024 * 1024
_FILE_TYPES = {
    'application/pdf', 'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}


def _rate_ok(token):
    now = time.time()
    q = _SAVES.setdefault(token, deque())
    while q and now - q[0] > _SAVE_WINDOW:
        q.popleft()
    if len(q) >= _SAVE_MAX:
        return False
    q.append(now)
    if len(_SAVES) > 5000:              # never let the dict grow for ever
        for key in list(_SAVES)[:1000]:
            _SAVES.pop(key, None)
    return True


class PbHiringRequestPages(http.Controller):

    # ------------------------------------------------------------ helpers
    def _role(self, token):
        return request.env['pb.hiring.requisition'].sudo() \
            ._for_request_token(token)

    def _actor(self, rec):
        """Who the manager's page acts AS: their own login when they have
        one (portal or internal — the trail then carries their name), else
        whoever asked them, else the system."""
        user = rec.asked_user_id or rec.requested_by_id.user_id
        if not user or not user.active:
            user = rec.asked_by_id if rec.asked_by_id.active else \
                request.env['res.users'].sudo().browse(SUPERUSER_ID)
        return rec.with_user(user).sudo()

    def _options(self, rec):
        env = request.env
        company = rec.company_id
        depts = env['hr.department'].sudo().search_read(
            [('company_id', 'in', [company.id, False])], ['name'], limit=400)
        dept = rec.department_id
        emp_dom = [('company_id', '=', company.id)]
        people = env['hr.employee'].sudo().search_read(
            emp_dom + [('department_id', '=', dept.id)] if dept else emp_dom,
            ['name', 'job_title'], limit=200, order='name')
        others = env['hr.employee'].sudo().search_read(
            emp_dom + [('id', 'not in', [p['id'] for p in people])],
            ['name', 'job_title'], limit=400, order='name')
        keep = [rec.reporting_manager_id, rec.asked_employee_id]
        seen = {p['id'] for p in people} | {p['id'] for p in others}
        for emp in keep:
            if emp and emp.id not in seen:
                others.insert(0, {'id': emp.id, 'name': emp.name,
                                  'job_title': emp.job_title or ''})
        currencies = env['res.currency'].sudo().search_read(
            [('active', '=', True)], ['name'], order='name')
        countries = env['res.country'].sudo().search_read(
            [], ['name'], order='name')
        return {'departments': sorted(depts, key=lambda d: d['name'] or ''),
                'people': people, 'others': others,
                'currencies': currencies, 'countries': countries,
                'role_types': ROLE_TYPES}

    def _values(self, token, rec, status, problem=''):
        vals = {'status': status, 'token': token, 'problem': problem}
        if not rec or status == 'invalid':
            return vals
        company = rec.company_id
        vals['company'] = company._hiring_brand() if hasattr(
            company, '_hiring_brand') else company.name
        vals['contact'] = rec.asked_by_id.name or rec.recruiter_id.name or ''
        vals['contact_email'] = rec.asked_by_id.email or \
            rec.recruiter_id.email or ''
        if status == 'closed':
            return vals
        questions = rec._page_questions()
        tone, note = rec._page_budget_note()
        vals.update({
            'rec': rec,
            'asked': rec.asked_employee_id,
            'answered': sum(1 for _k, ok in questions if ok),
            'total': len(questions),
            'answers': dict(questions),
            'budget_note': note, 'budget_tone': tone,
            'focus': rec._page_focus(),
            'opt': self._options(rec),
            'missing': rec._missing_for_send_in(),
            'trail': request.env['pb.hiring'].sudo()._request_trail(rec)
            if status == 'sent' else [],
            'state_label': rec._request_chip()[0],
            'chip_tone': rec._request_chip()[1],
            'budget_text': rec._money(rec.budget_cost, rec.currency_id),
        })
        return vals

    def _render(self, token, rec, status, problem=''):
        return request.render('pb_hiring.hiring_request_page',
                              self._values(token, rec, status, problem))

    def _json(self, payload, status=200):
        return request.make_json_response(payload, status=status)

    # ---------------------------------------------------------- the page
    @http.route('/hiring/r/<string:token>', type='http', auth='public',
                website=True, sitemap=False)
    def hiring_request_view(self, token, **kw):
        rec, status = self._role(token)
        problem = ''
        if kw.get('problem') == 'file':
            problem = _("Send the job description as a PDF or Word document "
                        "under 10 MB.")
        return self._render(token, rec, status, problem)

    @http.route('/hiring/r/<string:token>/save', type='http', auth='public',
                methods=['POST'], csrf=False, sitemap=False)
    def hiring_request_save(self, token, **post):
        """One field (or a few) saved. JSON in, JSON out. `csrf=False` for
        the reason every token page has it: the visitor has no session."""
        if not _rate_ok(token):
            return self._json({'ok': False, 'error': _(
                "That is a lot of saving at once. Wait a minute and it will "
                "carry on.")}, status=429)
        rec, status = self._role(token)
        if status != 'ok':
            return self._json({'ok': False, 'closed': True, 'error': _(
                "This request has been sent in or closed, so nothing more "
                "can be saved here.")}, status=409)
        try:
            data = request.httprequest.get_json(silent=True) or post or {}
            if not isinstance(data, dict):
                data = {}
            self._actor(rec)._page_save(data)
        except UserError as exc:
            return self._json({'ok': False, 'error': str(exc)}, status=400)
        except Exception:               # noqa: BLE001 — never a traceback
            _logger.exception('pb_hiring: a request autosave failed')
            return self._json({'ok': False, 'error': _(
                "That did not save. Check your connection; the page will try "
                "again.")}, status=500)
        rec.invalidate_recordset()
        questions = rec._page_questions()
        tone, note = rec._page_budget_note()
        return self._json({
            'ok': True, 'answered': sum(1 for _k, ok in questions if ok),
            'total': len(questions), 'answers': dict(questions),
            'budget_note': note, 'budget_tone': tone,
            'missing': rec._missing_for_send_in(),
        })

    @http.route('/hiring/r/<string:token>/file', type='http', auth='public',
                methods=['POST'], csrf=False, sitemap=False)
    def hiring_request_file(self, token, **post):
        rec, status = self._role(token)
        back = '/hiring/r/%s' % token
        if status != 'ok':
            return request.redirect(back)
        upload = post.get('jd_file')
        if not upload or not getattr(upload, 'filename', ''):
            return request.redirect(back + '?problem=file#needs')
        data = upload.read(_FILE_MAX_BYTES + 1)
        kind = (upload.mimetype or '').split(';')[0].strip()
        if len(data) > _FILE_MAX_BYTES or not data or kind not in _FILE_TYPES:
            return request.redirect(back + '?problem=file#needs')
        import base64
        self._actor(rec).with_context(tracking_disable=True).write({
            'pb_jd_file': base64.b64encode(data),
            'pb_jd_filename': (upload.filename or 'job-description')[:200],
        })
        if rec.request_state == 'asked':
            rec._request_write('writing')
        return request.redirect(back + '#needs')

    @http.route('/hiring/r/<string:token>/send', type='http', auth='public',
                website=True, methods=['POST'], csrf=False, sitemap=False)
    def hiring_request_send(self, token, **post):
        """"Send in": everything on the form is saved, then checked, then
        sent. A missing answer re-renders the page with the sentence."""
        rec, status = self._role(token)
        if status != 'ok':
            return request.redirect('/hiring/r/%s' % token)
        actor = self._actor(rec)
        try:
            fields_in = {k: v for k, v in post.items()
                         if not hasattr(v, 'filename')}
            if 'is_confidential' not in fields_in:
                fields_in['is_confidential'] = ''
            actor._page_save(fields_in)
            actor._request_send_in(by_employee=rec.asked_employee_id
                                   or rec.requested_by_id)
        except (UserError, AccessError) as exc:
            rec.invalidate_recordset()
            return self._render(token, rec, 'ok', problem=str(exc))
        except Exception:               # noqa: BLE001 — never a traceback
            _logger.exception('pb_hiring: a request send-in failed')
            rec.invalidate_recordset()
            return self._render(token, rec, 'ok', problem=_(
                "Something went wrong sending it in. Your answers are saved; "
                "try again in a minute."))
        return request.redirect('/hiring/r/%s?sent=1' % token)

    # ------------------------------------------------ the advert, shared
    @http.route('/hiring/j/<string:token>', type='http', auth='public',
                website=True, sitemap=False)
    def hiring_jd_view(self, token, **kw):
        jd, status = request.env['pb.hiring.jd'].sudo()._for_share_token(
            token)
        req = jd.requisition_id if jd else jd
        return request.render('pb_hiring.hiring_jd_page', {
            'status': status, 'token': token, 'jd': jd, 'req': req,
            'thanks': kw.get('done') == '1',
            'comments': jd.comment_ids[:30] if jd and status == 'ok' else [],
            'company': (req.company_id._hiring_brand() if req else ''),
            'contact': (req.recruiter_id.name or '') if req else '',
        })

    @http.route('/hiring/j/<string:token>/comment', type='http',
                auth='public', website=True, methods=['POST'], csrf=False,
                sitemap=False)
    def hiring_jd_comment(self, token, **post):
        jd, status = request.env['pb.hiring.jd'].sudo()._for_share_token(
            token)
        if status == 'ok':
            try:
                jd.sudo()._receive_comment(post.get('body'),
                                           name=post.get('name'))
            except Exception:           # noqa: BLE001 — never a traceback
                _logger.exception('pb_hiring: an advert comment failed')
        return request.redirect('/hiring/j/%s?done=1' % token)
