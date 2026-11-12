# -*- coding: utf-8 -*-
"""Workflow tasks on the employee home (WF2 P4a, R5).

Pattern of `pb_me_portal/controllers/portal.py`: `auth='user'`, the person is
the SESSION's own login (never an id from the URL), the ownership check
("this step is waiting for exactly this login") comes FIRST, and only then
is anything read under sudo. An employee-home login has no rights on any
workflow model; it reaches its own task through these routes and nothing
else. A step that is not theirs gets the ordinary not-found page.

The paths are `/my/todo…`: `/my/tasks` belongs to the Projects portal.
"""
import logging

from odoo import http
from odoo.http import request
from odoo.tools.misc import format_date

from .task_form import parse_answers, parse_outcome
from ..models.workflow_people import HOME_UNSUPPORTED

_logger = logging.getLogger(__name__)


class WorkflowMyTasks(http.Controller):

    def _studio(self):
        return request.env['pb.workflow.studio'].sudo()

    def _own(self, step_id):
        """The step when it is the session user's, else None. Nothing about
        the step is read before this check passes."""
        person = request.env.user
        if not person or person._is_public():
            return None
        return self._studio()._home_task(person, step_id)

    def _files(self, step, person):
        atts = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'pb.workflow.step'), ('res_id', '=', step.id),
            ('create_uid', '=', person.id)])
        names = {a.id: a.name for a in atts}
        out = {}
        for fid, ids in ((k, v) for k, v in (step.answers or {}).items() if isinstance(v, list)):
            rows = [{'id': i, 'name': names[i]} for i in ids if isinstance(i, int) and i in names]
            if rows:
                out[fid] = rows
        return out

    def _render(self, step, state, errors=None, values=None):
        studio = self._studio()
        data = studio._page_data(step, HOME_UNSUPPORTED)
        data['files'] = self._files(step, request.env.user)
        return request.render('pb_lifecycle.workflow_my_task_page', {
            'page_name': 'workflow_task', 't': data, 'mode': 'home', 'state': state,
            'errors': errors or {}, 'values': values if values is not None else data['values'],
            'post_url': '/my/todo/%s/done' % step.id,
            # WF2 P4b: where the whole thing is, above the task. The step is
            # already proven to be this person's (`_own`), so the record it
            # belongs to may be shown in the employee-home way.
            'wf_strip': self._task_strip(step),
            'back': '/my/todo/%s' % step.id,
        })

    def _task_strip(self, step):
        run = step.run_id
        if not run.source_model or step.state != 'waiting':
            return None
        home = request.env['pb.me.home']
        try:
            words = next(({str(k): v[0] for k, v in (src.get('states') or {}).items()}
                          for src in home._my_requests_sources() if src.get('model') == run.source_model), {})
        except Exception:  # noqa: BLE001 — the area's own words are optional
            words = {}
        return self._studio()._home_strip_safe(request.env.user, run.source_model, run.source_id,
                                               words=words, owned=True)

    @http.route(['/my/todo'], type='http', auth='user', website=True, sitemap=False)
    def my_todo(self, **kw):
        person = request.env.user
        studio = self._studio()
        tasks = []
        for step in studio._home_tasks(person):
            data = studio._page_data(step, HOME_UNSUPPORTED)
            # WF2 P5c: `data['name']` carries a repeat's line ("Check · Taxi").
            tasks.append({'id': step.id, 'name': data['name'], 'kind': step.kind,
                          'verb': {'input': 'Fill in', 'confirm': 'Read and confirm'}.get(step.kind, 'To do'),
                          'workflow': data['workflow'], 'due': data['due'], 'late': data['late']})
        notices = [{'id': n.id, 'subject': n.subject or '', 'body': n.body or '',
                    'when': format_date(request.env, n.create_date.date()), 'read': bool(n.read_at)}
                   for n in studio._home_notices(person)]
        return request.render('pb_lifecycle.workflow_my_tasks_page', {
            'page_name': 'workflow_tasks', 'tasks': tasks, 'notices': notices})

    @http.route(['/my/todo/<int:step_id>'], type='http', auth='user', website=True, sitemap=False)
    def my_todo_task(self, step_id, **kw):
        step = self._own(step_id)
        if step is None:
            return request.not_found()
        if step.state == 'done':
            return self._render(step, 'thanks' if kw.get('done') == '1' else 'done')
        if step.state != 'waiting' or step.run_id.state in ('held', 'done', 'cancelled', 'rejected'):
            return request.not_found()
        return self._render(step, 'ok')

    @http.route(['/my/todo/<int:step_id>/done'], type='http', auth='user', website=True,
                methods=['POST'], sitemap=False)
    def my_todo_done(self, step_id, **post):
        step = self._own(step_id)
        if step is None:
            return request.not_found()
        if step.state != 'waiting':
            return request.redirect('/my/todo/%s' % step.id)
        person = request.env.user
        studio = self._studio()
        form = request.httprequest.form
        values, errors = {}, {}
        if step.kind == 'input':
            fields_ = studio._page_fields(step, HOME_UNSUPPORTED)
            keep = {}
            for f in fields_:
                if f.get('type') != 'file':
                    continue
                kept = [int(x) for x in form.getlist('keep_%s' % f['id']) if str(x).isdigit()]
                for upload in request.httprequest.files.getlist('f_%s' % f['id']):
                    if not upload or not upload.filename:
                        continue
                    try:
                        kept.append(studio._home_upload(person, step, f['id'], upload))
                    except Exception as exc:  # noqa: BLE001 — shown beside the field
                        errors[f['id']] = getattr(exc, 'args', [''])[0] or 'This file could not be read.'
                keep[f['id']] = kept
            values = parse_answers(fields_, form, keep_files=keep)
        else:
            values = parse_outcome(form)
        if not errors:
            try:
                result = studio._complete_outside(step, values, actor_words=person.name, person=person)
            except Exception:  # noqa: BLE001 — never a 500 on the employee home
                _logger.exception('pb_lifecycle: employee-home task %s could not be sent', step.id)
                result = {'ok': False, 'errors': {'_form': 'This could not be sent. Try again in a moment.'}}
            if result.get('ok') or result.get('state') == 'done':
                return request.redirect('/my/todo/%s?done=1' % step.id)
            errors = result.get('errors') or {}
        merged = dict(studio._page_values(step), **values)
        return self._render(step, 'ok', errors=errors, values=merged)

    @http.route(['/my/todo/move'], type='http', auth='user', website=True, methods=['POST'], sitemap=False)
    def my_todo_move(self, **post):
        """WF2 P4b: "Move to…" on the employee home. The person is the
        session's own login; the record and the stage from the form are
        re-checked by `_home_move` (the stage must name this person) before
        anything is written, as the system, through the shipped move."""
        person = request.env.user
        if not person or person._is_public():
            return request.not_found()
        back = str(post.get('back') or '/my')
        if not back.startswith('/my') or '//' in back or '\\' in back:
            back = '/my'
        back = back.split('?', 1)[0]
        record_id, stage_id = str(post.get('record_id') or ''), str(post.get('stage_id') or '')
        if not record_id.isdigit() or not stage_id.isdigit():
            return request.redirect('%s?wf_move=gone' % back)
        result = self._studio()._home_move(person, str(post.get('model') or ''), int(record_id), int(stage_id))
        return request.redirect('%s?wf_move=%s' % (back, result.get('code') or ('ok' if result.get('ok') else 'gone')))

    @http.route(['/my/todo/notice/<int:notice_id>/read'], type='http', auth='user', website=True,
                methods=['POST'], sitemap=False)
    def my_todo_notice_read(self, notice_id, **post):
        notice = request.env['pb.workflow.notice'].sudo().browse(int(notice_id)).exists()
        if not notice or notice.user_id.id != request.env.user.id:
            return request.not_found()
        if not notice.read_at:
            from odoo import fields
            notice.write({'read_at': fields.Datetime.now()})
        return request.redirect('/my/todo')
