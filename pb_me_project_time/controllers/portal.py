# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`/my/project-time` — the week on one screen (ETP E3).

THE ROUTE IS THE GATE (ledger E-R2). The employee is re-resolved from the
SESSION on every request (`_ess_employee`, pb_me_portal); no route accepts an
employee id — the jsonrpc routes swallow unknown keys in ``**kw`` and pass
nothing of them on. Every write goes through the facade
(`pb.me.project.time`), which re-checks ownership and the project rule.

THE PAGE WORKS WITHOUT A SCRIPT (E-R8): the grid is one form; "Save week",
"Copy last week" and "Fill the week with 8 h" are its submit buttons; the
picker is a GET form; removing an empty row is a link. The script turns the
grid into autosave per cell and keeps the address bar's `rows` in step, so a
reload shows the same rows.

`rows` = the EMPTY rows the page carries ('12-0,12-7'). Absent = propose last
week's rows; present (even empty) = exactly those. Nothing about rows is
stored (D1).
"""

import logging
import re
from urllib.parse import urlencode

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from odoo.addons.pb_me_portal.controllers.portal import PbMePortal

from ..models.project_time import FILL_HOURS, fmt_h, key_str, parse_key, parse_rows

_logger = logging.getLogger(__name__)

_ERRORS = (AccessError, UserError, ValidationError, ValueError)
_RE_CELL = re.compile(r'^([hn])-(\d{1,9})-(\d{1,9})-(\d{4}-\d{2}-\d{2})$')
_DONE = ('saved', 'copied', 'filled')


class PbMeProjectTimePortal(PbMePortal):

    # ------------------------------------------------------------ helpers
    def _pt_facade(self, lang=None):
        """The facade, in the PAGE's language when the script says which one
        (a jsonrpc request carries the user's language, the page may be in
        another — `/vi/my/project-time`)."""
        env = request.env
        code = (lang or '').replace('-', '_')
        if code and code != env.lang:
            installed = dict(env['res.lang'].get_installed())
            if code not in installed:
                short = code.split('_')[0]
                code = next((c for c in installed if c.split('_')[0] == short), '')
            if code:
                env = env(context=dict(env.context, lang=code))
        return env['pb.me.project.time']

    def _pt_url(self, week=None, rows=None, **extra):
        params = {}
        if week:
            params['week'] = week
        if rows is not None:
            params['rows'] = rows
        params.update({k: v for k, v in extra.items() if v not in (None, '')})
        return '/my/project-time' + ('?' + urlencode(params) if params else '')

    def _pt_flash(self, Pt, done, n=0):
        """The result of the previous action as ONE sentence (one msgid,
        W80.2); never prose from the address bar."""
        _ = Pt.env._
        try:
            n = int(n or 0)
        except (TypeError, ValueError):
            n = 0
        if done == 'saved':
            return _("Your week is saved.")
        if done == 'copied':
            if not n:
                return _("Nothing to copy: those cells already have hours, or "
                         "last week was empty.")
            if n == 1:
                return _("1 cell copied from last week. Change anything that "
                         "was different.")
            return _("%s cells copied from last week. Change anything that "
                     "was different.", n)
        if done == 'filled':
            if not n:
                return _("Every working day on that row already has hours.")
            if n == 1:
                return _("1 empty working day now has 8 h.")
            return _("%s empty working days now have 8 h.", n)
        return ''

    def _pt_active_idx(self, data, day):
        week = data['week']
        isos = [d['iso'] for d in week['days']]
        if day in isos:
            return isos.index(day)
        today = data.get('today')
        return isos.index(today) if today in isos else 0

    def _pt_values(self, Pt, emp, week=None, rows=None, day=None, flash='',
                errors=None, fresh=None, focus=None):
        """Everything the page (and the grid partial) draws."""
        state = Pt.page_state(emp.company_id)
        values = {
            'page_name': 'project_time',
            'pt_state': state,
            'attendance': 'pb.ess.workforce' in Pt.env,
            'ask_hr': 'pb.ask.hr.ticket' in Pt.env,
            'flash': flash,
            'errors': errors or [],
            'fresh': set(fresh or []),
            'focus': focus or '',
            'fmt': fmt_h,
            'fill_hours': fmt_h(FILL_HOURS),
        }
        if state != 'ok':
            return values
        data = Pt.get_week(emp, week, rows=rows)
        picker = Pt.pickable_projects(emp)
        in_week = {r['key'] for r in data['rows']}
        labels = {r['key']: (r['label'] + (' · ' + r['sub'] if r['sub'] else ''))
                  for r in data['rows']}
        days = {d['iso']: d['long'] for d in data['week']['days']}
        for e in values['errors']:
            e.setdefault('label', labels.get(e.get('key'), ''))
            e.setdefault('day', days.get(e.get('date'), e.get('date')))
        values.update({
            'pt': data,
            'wk': data['week'],
            'picker': picker,
            'picker_empty': not any(g['projects'] for g in picker),
            'in_week': in_week,
            'active_idx': self._pt_active_idx(data, day),
            'rows_param': data['rows_param'],
            'has_project_rows': any(r['kind'] == 'project' for r in data['rows']),
        })
        return values

    def _pt_render_grid(self, Pt, values):
        return str(Pt.env['ir.qweb']._render('pb_me_project_time.pbpt_grid', values))

    def _pt_numbers(self, data):
        week = data['week']
        return {
            'week_total': week['total'], 'week_logged': week['logged'],
            'week_target': week['target'], 'week_pct': week['pct'],
            'week_state': week['state'],
            'can_copy': data['can_copy_last_week'],
        }

    def _pt_no_employee(self):
        return request.render('pb_me_project_time.pbpt_no_employee',
                              {'page_name': 'project_time'})

    def _pt_form_cells(self, post):
        """`h-<project>-<task>-<date>` / `n-…` fields → cells for save_week.
        A cell whose hours field was not sent keeps its hours (None)."""
        cells = {}
        for name, value in post.items():
            match = _RE_CELL.match(name or '')
            if not match:
                continue
            kind, pid, tid, iso = match.groups()
            cell = cells.setdefault((pid, tid, iso), {
                'project_id': int(pid), 'task_id': int(tid), 'date': iso,
                'hours': None, 'note': None})
            cell['hours' if kind == 'h' else 'note'] = value
        return list(cells.values())

    # --------------------------------------------------------------- page
    @http.route(['/my/project-time'], type='http', auth='user', website=True,
                methods=['GET', 'POST'])
    def portal_project_time(self, week=None, rows=None, add=None, day=None,
                            done=None, n=None, **post):
        emp = self._ess_employee()
        if not emp:
            return self._pt_no_employee()
        Pt = self._pt_facade()
        if request.httprequest.method == 'POST':
            return self._pt_post_week(Pt, emp, week, rows, day, post)
        rows_list = parse_rows(rows)
        focus = ''
        if add and Pt.page_state(emp.company_id) == 'ok':
            key = parse_key(add)
            if key:
                if rows_list is None:
                    rows_list = parse_rows(Pt.get_week(emp, week)['rows_param'])
                if key not in rows_list:
                    rows_list.append(key)
                focus = key_str(key)
        values = self._pt_values(Pt, emp, week=week, rows=rows_list, day=day,
                              flash=self._pt_flash(Pt, done, n) if done in _DONE else '',
                              focus=focus)
        return request.render('pb_me_project_time.portal_my_project_time', values)

    def _pt_post_week(self, Pt, emp, week, rows, day, post):
        """The no-JS form: save every changed cell, then the button's action
        ("Copy last week" / "Fill the week with 8 h"). Errors render the page
        with the reasons; success redirects (so a reload never posts twice)."""
        rows_list = parse_rows(rows)
        op = (post.get('op') or 'save').strip()
        try:
            monday = Pt._monday(week)
            with request.env.cr.savepoint():
                res = Pt.save_week(emp, monday, self._pt_form_cells(post))
        except _ERRORS as e:
            values = self._pt_values(Pt, emp, week=week, rows=rows_list, day=day,
                                  errors=[{'key': '', 'date': '', 'value': '',
                                           'error': (e.args and e.args[0]) or str(e)}])
            return request.render('pb_me_project_time.portal_my_project_time', values)
        if res['errors']:
            values = self._pt_values(Pt, emp, week=week, rows=rows_list, day=day,
                                  errors=res['errors'])
            return request.render('pb_me_project_time.portal_my_project_time', values)
        done, n = 'saved', 0
        try:
            if op == 'copy':
                with request.env.cr.savepoint():
                    n = Pt.copy_last_week(emp, monday)['copied']
                done = 'copied'
            elif op.startswith('fill:'):
                key = parse_key(op[5:])
                if key:
                    with request.env.cr.savepoint():
                        n = Pt.fill_row(emp, key[0], key[1], monday)['filled']
                    done = 'filled'
        except _ERRORS as e:
            values = self._pt_values(Pt, emp, week=week, rows=rows_list, day=day,
                                  errors=[{'key': '', 'date': '', 'value': '',
                                           'error': (e.args and e.args[0]) or str(e)}])
            return request.render('pb_me_project_time.portal_my_project_time', values)
        return request.redirect(self._pt_url(
            monday.isoformat(), rows if rows is not None else None,
            day=day or None, done=done, n=n or None))

    # ----------------------------------------------------- autosave (JSON)
    def _pt_json_error(self, e):
        return {'ok': False, 'error': (e.args and e.args[0]) or str(e)}

    def _pt_json_crash(self, Pt):
        _logger.warning('pb_me_project_time: a grid action failed for user %s',
                        request.env.uid, exc_info=True)
        return {'ok': False, 'error': Pt.env._("That did not save. Try again in "
                                               "a moment.")}

    @http.route(['/my/project-time/cell'], type='jsonrpc', auth='user',
                methods=['POST'])
    def portal_project_time_cell(self, project_id=None, task_id=None, date=None,
                                 hours=None, note=None, lang=None, **kw):
        """One cell. `**kw` swallows anything else — an `employee_id`
        included — and nothing of it is passed on: the employee is the
        session's."""
        Pt = self._pt_facade(lang)
        emp = self._ess_employee()
        if not emp:
            return {'ok': False, 'error': Pt.env._(
                "Your login is not linked to an employee record. Ask HR to link it.")}
        try:
            with request.env.cr.savepoint():
                return Pt.set_cell(emp, project_id, task_id, date, hours, note)
        except _ERRORS as e:
            return self._pt_json_error(e)
        except Exception:               # noqa: BLE001 — a cell never 500s
            return self._pt_json_crash(Pt)

    def _pt_grid_answer(self, Pt, emp, week, rows, day, flash='', fresh=None,
                     focus=None):
        values = self._pt_values(Pt, emp, week=week, rows=rows, day=day,
                              flash=flash, fresh=fresh, focus=focus)
        if values['pt_state'] != 'ok':
            return {'ok': False, 'error': Pt.env._(
                "Project time is switched off for your company.")}
        answer = {'ok': True, 'html': self._pt_render_grid(Pt, values),
                  'rows': values['rows_param'], 'message': flash,
                  'focus': focus or ''}
        answer.update(self._pt_numbers(values['pt']))
        return answer

    def _pt_structural(self, Pt, fn):
        emp = self._ess_employee()
        if not emp:
            return {'ok': False, 'error': Pt.env._(
                "Your login is not linked to an employee record. Ask HR to link it.")}
        try:
            with request.env.cr.savepoint():
                return fn(emp)
        except _ERRORS as e:
            return self._pt_json_error(e)
        except Exception:               # noqa: BLE001
            return self._pt_json_crash(Pt)

    @http.route(['/my/project-time/row/add'], type='jsonrpc', auth='user',
                methods=['POST'])
    def portal_project_time_row_add(self, project_id=None, task_id=None,
                                    week=None, rows=None, day=None, lang=None, **kw):
        Pt = self._pt_facade(lang)

        def run(emp):
            row = Pt.add_row(emp, project_id, task_id, week)
            keys = parse_rows(rows) or []
            key = parse_key(row['key'])
            if key not in keys:
                keys.append(key)
            return self._pt_grid_answer(Pt, emp, week, keys, day, focus=row['key'])
        return self._pt_structural(Pt, run)

    @http.route(['/my/project-time/copy-last-week'], type='jsonrpc', auth='user',
                methods=['POST'])
    def portal_project_time_copy(self, week=None, rows=None, day=None, lang=None,
                                 **kw):
        Pt = self._pt_facade(lang)

        def run(emp):
            res = Pt.copy_last_week(emp, week)
            return self._pt_grid_answer(Pt, emp, week, parse_rows(rows), day,
                                     flash=self._pt_flash(Pt, 'copied', res['copied']),
                                     fresh=res['fresh'])
        return self._pt_structural(Pt, run)

    @http.route(['/my/project-time/row/fill'], type='jsonrpc', auth='user',
                methods=['POST'])
    def portal_project_time_fill(self, project_id=None, task_id=None, week=None,
                                 hours=None, rows=None, day=None, lang=None, **kw):
        Pt = self._pt_facade(lang)

        def run(emp):
            res = Pt.fill_row(emp, project_id, task_id, week,
                              hours if hours not in (None, '') else FILL_HOURS)
            return self._pt_grid_answer(Pt, emp, week, parse_rows(rows), day,
                                     flash=self._pt_flash(Pt, 'filled', res['filled']),
                                     fresh=res['fresh'])
        return self._pt_structural(Pt, run)

    @http.route(['/my/project-time/picker'], type='jsonrpc', auth='user',
                methods=['POST'])
    def portal_project_time_picker(self, q=None, lang=None, **kw):
        """The picker's search, server side (the page also carries the whole
        list, so the script filters as you type without a round trip)."""
        Pt = self._pt_facade(lang)
        emp = self._ess_employee()
        if not emp or Pt.page_state(emp.company_id) != 'ok':
            return {'ok': True, 'groups': []}
        return {'ok': True, 'groups': Pt.pickable_projects(emp, query=q)}
