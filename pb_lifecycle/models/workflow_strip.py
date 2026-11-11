"""WF2 P4b — progress where people already are.

A slim strip at the top of a record's own screen (staff) and on the employee
home's own request pages: the stage track (the area's statuses and the
company's own stages), one sentence about who it is waiting for, and — for
the right person — "Do it now" (their task) or "Move to…" (a company stage
the record may go to next, through the shipped `move_record_stage` rules).

Rules this file keeps:

  * Nothing to show (no workflow on the record, no company-stage position)
    → no strip at all. The early exit is two indexed searches.
  * A fault here never breaks another module's screen: every entry point is
    wrapped, logs once and answers "no strip".
  * Who sees what: people who may view workflow progress see the strip as
    "View workflow" would show it. Somebody without that right sees a strip
    only when it holds something of their own: a task waiting for them, or
    a company stage they are named to move the record into.
  * The employee home: session login → ownership → only then the system
    environment; only stage names, the waiting sentence and dates.
  * Studio never writes a module's status (R2c). A move here is a move
    between company stages, exactly as `move_record_stage` does it.

No local is called `user` or `uid` in a method that calls `_()` (ledger G12).
"""
import logging
from datetime import timedelta

from odoo import SUPERUSER_ID, api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date

from . import workflow_definition as D
from .workflow_models import internal, system
from .workflow_people import mask_email

_logger = logging.getLogger(__name__)

RUN = 'pb.workflow.run'
LIVE = ('running', 'waiting', 'failed', 'held')
#: The strip looks at this many workflows on one record at most.
MAX_RUNS = 6
#: Employee-home pages that show one request, and how to find it.
HOME_PAGES = {
    'expense_claim': {'model': 'pb.expense.claim', 'words': '_wf_expense_words'},
}


class WorkflowStrip(models.AbstractModel):
    _inherit = 'pb.workflow.studio'

    # ------------------------------------------------------------- words
    def _day_words(self, day):
        """today / tomorrow / Friday / 13 Nov, in the reader's language."""
        if not day:
            return ''
        today = fields.Date.context_today(self)
        delta = (day - today).days
        if delta == 0:
            return _('today')
        if delta == 1:
            return _('tomorrow')
        if delta == -1:
            return _('yesterday')
        if 1 < delta < 7:
            return format_date(self.env, day, date_format='EEEE')
        return format_date(self.env, day, date_format='d MMM')

    def _when_words(self, moment):
        return format_date(self.env, fields.Datetime.context_timestamp(self, moment).date(),
                           date_format='d MMM') if moment else ''

    def _due_meta(self, step):
        """('due Friday' | 'Late by 2 days', late?) for a waiting person step."""
        if not step.due_at:
            return '', False
        due_day = (step.due_at - timedelta(days=1)).date()
        if fields.Datetime.now() >= step.due_at:
            days = max(1, (fields.Date.context_today(self) - due_day).days)
            return (_('Late by 1 day') if days == 1 else _('Late by %s days', days)), True
        return _('due %s', self._day_words(due_day)), False

    def _approval_words(self, step):
        request = step.sudo().approval_id
        if not request:
            return _('Waiting for this to be sent for approval')
        active = request.step_ids.filtered(lambda s: s.status == 'active').sorted('sequence')[:1]
        names = sorted({n for n in active.seat_ids.mapped('acting_user_id.name') if n}) if active else []
        if active and names:
            return _('Waiting for approval: %(step)s with %(who)s', step=active.title or _('approval'),
                     who=', '.join(names))
        return _('Waiting for approval')

    # ------------------------------------------------------------ one run
    def _strip_row(self, run, viewer, full, home=False):
        """One workflow on the record, in plain words, for this viewer."""
        srun = run.sudo()
        row = {'run_id': run.id, 'name': srun.name, 'state': srun.state, 'sentence': '', 'meta': '',
               'tone': 'wait', 'task_id': None, 'resend_id': None, 'late': False, 'who': ''}
        waiting = srun.step_ids.filtered(lambda s: s.state == 'waiting').sorted(lambda s: (s.position, s.id))
        people = waiting.filtered(lambda s: s.kind in D.PEOPLE)
        if srun.state in LIVE and srun.state != 'held' and people:
            mine = people.filtered(lambda s: s.assignee_id.id == viewer.id or (
                s.team_user_ids and not s.assignee_id and viewer in s.team_user_ids))
            step = mine[:1] or people[:1]
            role = self._team_role(step)
            what = step.name
            row['who'] = (_('you') if mine else role.name if step.team_user_ids and not step.assignee_id
                          else step.assignee_id.name or step.link_name or role.name or '')
            if mine:
                row.update(task_id=step.id, tone='mine', task_name=step.name)
                row['sentence'] = (_('Waiting for your team %(team)s: %(what)s', team=role.name, what=what)
                                   if step.team_user_ids and not step.assignee_id else
                                   _('Waiting for you: %s', what))
            elif step.team_user_ids and not step.assignee_id:
                row['tone'] = 'team'
                row['sentence'] = _('Waiting for %s — nobody has taken it yet', role.name or _('a team'))
            elif step.team_user_ids:
                row['sentence'] = _('Waiting for %(who)s (%(team)s): %(what)s', who=step.assignee_id.name,
                                    team=role.name, what=what)
            elif step.covered_user_id:
                row['sentence'] = _('Waiting for %(who)s, covering for %(whose)s: %(what)s',
                                    who=step.assignee_id.name, whose=step.covered_user_id.name, what=what)
            elif step.sudo().link_email:
                row['tone'] = 'link'
                if home:
                    row['sentence'] = _('Waiting for %s, by email', step.link_name or _('someone'))
                else:
                    row['sentence'] = _('Waiting for %(who)s by email link (%(email)s)',
                                        who=step.link_name or _('someone'), email=mask_email(step.sudo().link_email))
                    if full:
                        row['resend_id'] = step.id
            elif step.assignee_id.share:
                row['sentence'] = _('Waiting for %(who)s on their employee home: %(what)s',
                                    who=step.assignee_id.name, what=what)
            elif step.assignee_id:
                row['sentence'] = _('Waiting for %(who)s: %(what)s', who=step.assignee_id.name, what=what)
            else:
                row['sentence'] = _('Waiting: %s', what)
            meta, late = self._due_meta(step)
            row.update(meta=meta, late=late)
            if late:
                row['tone'] = 'late'
            return row
        if srun.state in ('running', 'waiting'):
            approval = waiting.filtered(lambda s: s.kind == 'matrix')[:1]
            pause = waiting.filtered(lambda s: s.kind == 'wait' and s.wake_at)[:1]
            if approval:
                row['sentence'] = self._approval_words(approval)
            elif (srun.gate or {}).get('reason'):
                row['sentence'] = str(srun.gate['reason']).rstrip('.')
            elif pause:
                row['sentence'] = _('Paused until %s', self._day_words(
                    fields.Datetime.context_timestamp(self, pause.wake_at).date()))
            elif waiting.filtered(lambda s: s.kind == 'email'):
                row['sentence'] = _('Sending a message')
            else:
                row['sentence'] = _('In progress')
            return row
        ended = srun.ended_at or srun.write_date
        row['sentence'] = {
            'done': _('Done on %s', self._when_words(ended)),
            'cancelled': _('Stopped on %s', self._when_words(ended)),
            'rejected': _('Turned down on %s', self._when_words(ended)),
            'held': _('On hold'),
            'failed': _('Needs a look from the workflow owner'),
        }.get(srun.state, _('In progress'))
        row['tone'] = {'done': 'done', 'cancelled': 'stopped', 'rejected': 'stopped',
                       'failed': 'late', 'held': 'stopped'}.get(srun.state, 'wait')
        return row

    # ----------------------------------------------------------- moving
    def _strip_moves(self, model, record, status, position, company, may):
        """Company stages a person may move the record into from here:
        every stage a person moves records into that counts as the record's
        current status. `may(stage, waiting)` answers for the viewer."""
        stages = self._user_stages(model, self.env['pb.workflow'], company).filtered(
            lambda s: s.enter == 'person' and str(s.anchor_value) == str(status)
            and (not position or s != position.stage_id))
        if not stages:
            return []
        waiting = self.env[RUN].sudo().search([('company_id', '=', company.id), ('source_model', '=', model),
                                               ('source_id', '=', record.id), ('state', 'in', ['running', 'waiting'])])
        rows = []
        for stage in stages:
            try:
                allowed = bool(may(stage, waiting))
            except (AccessError, UserError):
                allowed = False
            rows.append({'stage_id': stage.id, 'name': stage.name, 'allowed': allowed,
                         'reason': '' if allowed else _('Only %(who)s can move this to %(stage)s.',
                                                        who=self._lower_words(self._owner_words(model, stage.enter_owner)),
                                                        stage=stage.name)})
        return rows

    # ------------------------------------------------------------ track
    def _strip_track(self, stage_data, words=None):
        """The track rows the strip draws, with a page's own words for the
        area's statuses when the page has them (one word per status)."""
        words = words or {}
        track = []
        rows = (stage_data or {}).get('track', [])
        anchors = {s.id: str(s.anchor_value or '') for s in self.env['pb.workflow.stage'].sudo().browse(
            [r['key'] for r in rows if r['kind'] == 'yours']).exists()} if words else {}
        for row in rows:
            name = row['name']
            if row['kind'] == 'core' and str(row['key']) in words:
                name = words[str(row['key'])]
            counts_as = row.get('counts_as', '')
            if row['kind'] == 'yours' and anchors.get(row['key']) in words:
                counts_as = words[anchors[row['key']]]
            track.append({'kind': row['kind'], 'key': row['key'], 'state': row['state'], 'name': name,
                          'counts_as': counts_as})
        exits = [{'name': words.get(str(e['key']), e['name']), 'here': e['here']}
                 for e in (stage_data or {}).get('exits', [])]
        here = next((i for i, t in enumerate(track) if t['state'] == 'here'), None)
        stopped = next((e for e in exits if e['here']), None)
        compact = {'index': here + 1 if here is not None else 0, 'total': len(track),
                   'name': stopped['name'] if stopped else track[here]['name'] if here is not None else ''}
        # A long track keeps the first, the last and the stages around where
        # it is; each hidden run becomes one "+3" (its names in a popover).
        n = len(track)
        keep = set(range(n)) if n <= 6 else {0, n - 1} | (
            {here - 1, here, here + 1} if here is not None else {1, 2})
        i = 0
        while i < n:
            if i in keep:
                track[i]['more'] = False
                i += 1
                continue
            j = i
            while j < n and j not in keep:
                j += 1
            if j - i == 1:
                # One stage is drawn, never folded into a "+1".
                track[i]['more'] = False
                i += 1
                continue
            hidden = track[i:j]
            track.insert(i, {'more': True, 'count': len(hidden), 'names': [h['name'] for h in hidden],
                             'state': 'done' if all(h['state'] in ('done', 'passed') for h in hidden) else
                             'stopped' if all(h['state'] == 'stopped' for h in hidden) else 'later',
                             'key': 'more-%s' % i, 'kind': 'more', 'name': ''})
            for h in hidden:
                h['hidden'] = True
            n += 1
            keep = {k + 1 if k >= i else k for k in keep}
            i = j + 1
        return track, exits, compact

    def _position_sentence(self, position, stage_data):
        current = (stage_data or {}).get('current') or {}
        if not position:
            return ''
        since = self._when_words(position.entered_at)
        by = current.get('by') or ''
        return (_('In %(stage)s since %(day)s · moved by %(who)s', stage=position.stage_id.name, day=since, who=by)
                if by else _('In %(stage)s since %(day)s', stage=position.stage_id.name, day=since))

    # ------------------------------------------------------- staff strip
    def _strip_has_something(self, model, res_id, company):
        runs = self.env[RUN].sudo().search([('company_id', '=', company.id), ('source_model', '=', model),
                                            ('source_id', '=', int(res_id))], order='id desc', limit=MAX_RUNS)
        position = self.env['pb.workflow.record.stage'].sudo().search([
            ('company_id', '=', company.id), ('res_model', '=', model), ('res_id', '=', int(res_id))], limit=1)
        return runs, position

    def _strip(self, model, record_id, stage_data=None):
        """The strip for a staff screen, or None (see the module docstring)."""
        if not model or model.startswith('pb.workflow.') or model not in self.env or not int(record_id or 0):
            return None
        company = self.env.company
        runs, raw_position = self._strip_has_something(model, record_id, company)
        if not runs and not raw_position:
            return None
        record = self._source(model, record_id)
        viewer = self.env.user
        full = self._can_view_progress()
        position = self._record_position(model, record.id, company) if raw_position else raw_position
        if not runs and not position:
            return None
        if stage_data is None:
            stage_data = self._record_stage_safe(model, record.id)
        contract = self._contract(model, record)
        status = self._status_value(contract, record)
        moves = self._strip_moves(model, record, status, position, company,
                                  lambda stage, waiting: self._may_move(model, record, stage, waiting))
        live = runs.sorted(lambda r: (r.state not in LIVE, -r.id))
        rows = [self._strip_row(r, viewer, full) for r in live]
        mine = [r for r in rows if r['task_id']]
        if not full:
            if not mine and not any(m['allowed'] for m in moves):
                return None
            rows = mine
        track, exits, compact = self._strip_track(stage_data)
        for row in rows:
            row['action'] = ('do' if row['task_id'] else 'move' if any(m['allowed'] for m in moves)
                             else 'view' if full else '')
        return {'model': model, 'record_id': record.id, 'area': (stage_data or {}).get('area') or contract['area'],
                'track': track, 'exits': exits, 'compact': compact, 'workflows': rows,
                'sentence': '' if rows else self._position_sentence(position, stage_data),
                'moves': moves, 'can_view': full,
                'action': '' if rows else ('move' if any(m['allowed'] for m in moves) else 'view' if full else '')}

    def _strip_safe(self, model, record_id, stage_data=None):
        """Never raises: a Studio fault must not break another module's form."""
        try:
            with self.env.cr.savepoint():
                return self._strip(model, record_id, stage_data)
        except (AccessError, UserError):
            return None
        except Exception:  # noqa: BLE001 — logged once, the form opens without a strip
            _logger.exception('Workflow strip for %s,%s could not be built', model, record_id)
            return None

    @api.model
    def record_runs(self, model, record_id):
        result = super().record_runs(model, record_id)
        result['strip'] = self._strip_safe(model, record_id, result.get('record_stage') or None)
        return result

    @api.model
    def record_strip(self, model, record_id):
        """The strip alone, for screens that are not a form (the Hiring
        candidate drawer). Same checks as the form hook."""
        self._staff()
        return {'strip': self._strip_safe(model, record_id)}

    @api.model
    def strip_move(self, model, record_id, stage_id):
        """"Move to…" from the strip: the shipped door, then the fresh strip."""
        self.move_record_stage(model, record_id, stage_id)
        return {'strip': self._strip_safe(model, record_id)}

    # ======================================================= employee home
    def _home_owns(self, person, record):
        """The record is about this employee-home person (their request)."""
        if not person or not record:
            return False
        if hasattr(record, '_workflow_subject'):
            subject = record.sudo()._workflow_subject() or {}
            employee = subject.get('employee')
            if employee and employee[:1].user_id == person:
                return True
            if subject.get('user') and subject['user'][:1] == person:
                return True
        if 'employee_id' in record._fields and record.sudo().employee_id.user_id == person:
            return True
        return False

    def _home_names(self, person, record, stage, initiator=None):
        """Whether the stage names this person as the one who moves it,
        resolved the way the employee home knows people (a login without
        staff rights counts)."""
        owner = stage.enter_owner or {}
        kind = owner.get('kind')
        if kind == 'user':
            return owner.get('id') == person.id
        if kind == 'initiator':
            return bool(initiator) and initiator.id == person.id
        if kind == 'field':
            field = owner.get('field')
            return bool(field) and field in record._fields and record.sudo()[field].id == person.id
        subject = record.sudo()._workflow_subject() if hasattr(record, '_workflow_subject') else {}
        if kind == 'subject':
            login = (subject.get('user') or self.env['res.users'])[:1] or \
                (subject.get('employee') or self.env['hr.employee'])[:1].user_id
            return login == person
        if kind == 'manager':
            manager = (subject.get('manager_user') or self.env['res.users'])[:1]
            if not manager:
                employee = (subject.get('employee') or self.env['hr.employee'])[:1] or (
                    record.sudo().employee_id if 'employee_id' in record._fields else self.env['hr.employee'])
                manager = employee.parent_id.user_id
            return manager == person
        return False

    def _home_strip(self, person, model, record_id, words=None, owned=False):
        """The employee-home strip for one record, or None.

        `owned`: the caller already proved the person may see this record
        (their own task on it). Otherwise the record must be about them."""
        if not person or person._is_public() or model not in self.env or not int(record_id or 0):
            return None
        record = self.env[model].sudo().browse(int(record_id)).exists()
        if not record or 'company_id' not in record._fields or not record.company_id:
            return None
        if not owned and not self._home_owns(person, record):
            return None
        company = record.company_id
        # The reader's language and time zone, on the system environment.
        service = system(self.env, company)['pb.workflow.studio'].with_context(
            lang=person.lang or 'en_US', tz=person.tz or 'UTC')
        runs, raw_position = service._strip_has_something(model, record.id, company)
        if not runs and not raw_position:
            return None
        position = service._record_position(model, record.id, company) if raw_position else raw_position
        if not runs and not position:
            return None
        stage_data = service._record_stage_safe(model, record.id)
        contract = service._contract(model, record)
        status = service._status_value(contract, record)
        live = runs.sorted(lambda r: (r.state not in LIVE, -r.id))
        rows = [service._strip_row(r, person, False, home=True) for r in live]
        for row in rows:
            # Nothing of the workflow's own make-up: its name, history or
            # answers stay with the staff screens.
            for key in ('resend_id', 'name', 'run_id', 'task_name'):
                row.pop(key, None)
            if row['task_id']:
                row['url'] = '/my/todo/%s' % row['task_id']
        initiator = live[:1].initiator_id if live else None
        moves = service._strip_moves(model, record, status, position, company,
                                     lambda stage, waiting: self._home_names(person, record, stage, initiator))
        moves = [m for m in moves if m['allowed']]
        track, exits, compact = self._strip_track(stage_data, words)
        rows = [r for r in rows if r['state'] in LIVE] or rows[:1]
        return {'model': model, 'record_id': record.id, 'track': track, 'exits': exits, 'compact': compact,
                'workflows': rows[:2], 'moves': moves,
                'sentence': '' if rows else service._position_sentence(position, stage_data),
                # WF2 P2b (D23): does the strip say more than the page's own
                # "With X" box? (a workflow person step, or a user-made stage)
                'adds': bool(position) or any(r.get('who') for r in rows if r['state'] in LIVE)}

    def _home_strip_safe(self, *args, **kwargs):
        try:
            with self.env.cr.savepoint():
                return self._home_strip(*args, **kwargs)
        except Exception:  # noqa: BLE001 — the employee page opens without it
            _logger.exception('Employee-home workflow strip could not be built')
            return None

    def _home_move(self, person, model, record_id, stage_id):
        """"Move to…" on the employee home, for the person the stage names.
        Returns plain words: {'ok': bool, 'message': str}."""
        if not person or person._is_public() or model not in self.env \
                or not hasattr(self.env[model], '_workflow_capabilities'):
            return {'ok': False, 'code': 'gone', 'message': _('This cannot be moved from here.')}
        record = self.env[model].sudo().browse(int(record_id or 0)).exists()
        stage = self.env['pb.workflow.stage'].sudo().browse(int(stage_id or 0)).exists()
        if not record or not stage or not stage.active or 'company_id' not in record._fields \
                or stage.company_id != record.company_id or stage.source_model != model or stage.workflow_id:
            return {'ok': False, 'code': 'gone', 'message': _('This stage is not available.')}
        company = record.company_id
        service = system(self.env, company)['pb.workflow.studio']
        if stage.enter != 'person':
            return {'ok': False, 'code': 'auto',
                    'message': _('Records get into “%s” by themselves. Nobody needs to move them.', stage.name)}
        contract = service._contract(model, record)
        if str(service._status_value(contract, record)) != str(stage.anchor_value):
            return {'ok': False, 'code': 'gone', 'message': _('This has moved on, so it cannot go to %s now.', stage.name)}
        waiting = service.env[RUN].search([('company_id', '=', company.id), ('source_model', '=', model),
                                           ('source_id', '=', record.id), ('state', 'in', ['running', 'waiting'])])
        if not self._home_names(person, record, stage, waiting[:1].initiator_id if waiting else None):
            return {'ok': False, 'code': 'who', 'message': _('Only %(who)s can move this to %(stage)s.',
                                              who=service._lower_words(service._owner_words(model, stage.enter_owner)), stage=stage.name)}
        service._set_position(model, record.id, stage, company, run=waiting[:1] if waiting else None,
                              mover=service.env['res.users'].browse(person.id))
        for run in waiting:
            if run.state in ('running', 'waiting'):
                run._advance()
        return {'ok': True, 'code': 'ok', 'message': _('Moved to %s.', stage.name)}


class WorkflowStripHome(models.AbstractModel):
    _inherit = 'pb.me.home'

    def _wf_expense_words(self):
        if 'pb.me.expense' not in self.env:
            return {}
        return {str(k): v[0] for k, v in self.env['pb.me.expense']._labels().items()}

    @api.model
    def _wf_page_strip(self, page_name, record_id):
        """The strip on an employee-home page that shows one request (the
        layout asks for it; the session's own login is the person)."""
        page = HOME_PAGES.get(page_name)
        person = self.env.user
        if not page or not record_id or person._is_public():
            return None
        studio = self.env['pb.workflow.studio'].sudo()
        try:
            words = getattr(self, page['words'])()
        except Exception:  # noqa: BLE001
            words = {}
        strip = studio._home_strip_safe(person, page['model'], record_id, words=words)
        # WF2 P2b (D23, owner 11 Nov): on a request page the strip shows only
        # when it adds something — a workflow step for a person, or a stage
        # the company made. A request that is only waiting for approval keeps
        # the page's own "With X" box alone.
        if strip and not strip.get('adds'):
            return None
        return strip

    @api.model
    def _my_requests_rows(self, src, emp):
        rows = super()._my_requests_rows(src, emp)
        try:
            with self.env.cr.savepoint():
                self._wf_request_lines(src, rows)
        except Exception:  # noqa: BLE001 — My requests opens without the line
            _logger.exception('My requests: workflow lines for %s could not be added', src.get('model'))
        return rows

    def _wf_request_lines(self, src, rows):
        """One quiet line under a request's status when a workflow or a
        company stage has something to say ("Stage 3 of 5 · with Lan Tran").
        The request's own status word stays exactly as it is."""
        if not rows:
            return
        model = src['model']
        ids = [r['id'] for r in rows]
        Run, Pos = self.env[RUN].sudo(), self.env['pb.workflow.record.stage'].sudo()
        runs = Run.search([('source_model', '=', model), ('source_id', 'in', ids)], order='id desc')
        positions = Pos.search([('res_model', '=', model), ('res_id', 'in', ids)])
        if not runs and not positions:
            return
        with_something = set(runs.mapped('source_id')) | set(positions.mapped('res_id'))
        words = {str(k): v[0] for k, v in (src.get('states') or {}).items()}
        studio = self.env['pb.workflow.studio'].sudo()
        person = self.env.user
        for row in rows:
            if row['id'] not in with_something:
                continue
            strip = studio._home_strip_safe(person, model, row['id'], words=words)
            if not strip:
                continue
            parts = []
            compact = strip['compact']
            if compact['total'] and compact['index']:
                parts.append(_('Stage %(n)s of %(total)s', n=compact['index'], total=compact['total']))
            live = [w for w in strip['workflows'] if w['state'] in ('running', 'waiting')]
            if live and live[0].get('who'):
                parts.append(_('waiting for you') if live[0]['task_id'] else _('with %s', live[0]['who']))
            elif live:
                parts.append(live[0]['sentence'])
            elif strip.get('sentence'):
                parts.append(strip['sentence'])
            if parts:
                row['wf_line'] = ' · '.join(parts)
                row['wf_late'] = bool(live and live[0].get('late'))
