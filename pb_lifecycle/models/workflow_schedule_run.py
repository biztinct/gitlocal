"""Start on a schedule — the worker side and the preview (WORKFLOW-2 P5a).

NO NEW JOB. Scheduled starts are looked at inside the one Studio worker job
("Workflow Studio: progress active runs", every minute) before it does its
usual work. Where that job is switched off (sudima, D11) nothing scheduled
starts, and Review says so.

WHAT ONE LOOK DOES, per switched-on scheduled workflow:
  * the starts due between the last look (`last_tick_at`) and now are worked
    out with `workflow_schedule.ticks` — the same function the "Next 5
    starts" preview uses;
  * only the LATEST due start is made (a server that was off for a week
    starts once, not seven times); the others are written down as missed;
  * a new process: one run; on records: one run per record matching the
    workflow's filters, each with its own start key
    `schedule:<workflow>:<start>:<record>` so a retried job never starts a
    record twice; a record whose earlier run is still going is left alone
    (the existing one-run-per-record rule);
  * more matching records than the cap (500) → NOTHING is started, the
    workflow's Activity shows the reason with the count, and whoever
    published it is told once (never half a batch, silently).
Switching a scheduled workflow on sets `last_tick_at` to now: switching it
back on later never catches up.

Runs are started by the system and shown as "Started on schedule" (R7).
"""
import logging
from datetime import datetime

from markupsafe import Markup, escape

from odoo import SUPERUSER_ID, api, fields, models, _
from odoo.exceptions import AccessError, UserError

from . import workflow_definition as D
from . import workflow_schedule as WS
from .workflow_models import internal, system

_logger = logging.getLogger(__name__)

#: Schedule history rows kept on a workflow (newest first).
LOG_KEEP = 20


class WorkflowScheduleOutbox(models.Model):
    _inherit = 'biz.approval.outbox'

    kind = fields.Selection(selection_add=[
        ('schedule_problem', 'A scheduled workflow did not start'),
    ], ondelete={'schedule_problem': 'cascade'})

    def _deliver(self):
        """A scheduled workflow that could not start has no record and no run
        to post on: the note goes to the person's own in-app inbox (no email,
        no to-do), the way "Tell someone in the app" does (G31)."""
        self.ensure_one()
        if self.kind != 'schedule_problem':
            return super()._deliver()
        payload = self.payload or {}
        person = self.user_id
        if not person or not person.active or person.share:
            return True
        lines = [escape(x) for x in str(payload.get('body') or '').split('\n') if x.strip()]
        body = Markup('<p>%s</p>') % Markup('<br/>').join(lines)
        partner = person.partner_id
        company = self.env['res.company'].sudo().browse(int(payload.get('company_id') or 0)).exists()
        message = self.env['mail.message'].sudo().create({
            'model': 'res.partner', 'res_id': partner.id, 'body': body,
            'subject': str(payload.get('summary') or '')[:200],
            'message_type': 'notification',
            'subtype_id': self.env.ref('mail.mt_note').id,
            'author_id': (company or self.env.company).partner_id.id})
        partner.sudo()._notify_thread_by_inbox(
            message, [{'id': partner.id, 'uid': person.id, 'notif': 'inbox'}])
        return True


class WorkflowScheduleStudio(models.AbstractModel):
    _inherit = 'pb.workflow.studio'

    # ------------------------------------------------------------ helpers
    @api.model
    def _schedule_of(self, definition):
        t = (definition or {}).get('trigger') or {}
        return t.get('schedule') if t.get('kind') == 'schedule' else None

    @api.model
    def _company_clock(self, company):
        """(time zone name, working-day test) for a company: its working
        calendar's zone and days, its public holidays; UTC and every day when
        it has no calendar."""
        calendar = company.resource_calendar_id
        tzname = (calendar.tz if calendar else '') or company.partner_id.tz or 'UTC'
        if not calendar:
            return tzname, None
        leaves = self.env['resource.calendar.leaves'].sudo().search([
            ('resource_id', '=', False), ('company_id', 'in', [company.id, False]),
            ('calendar_id', 'in', [calendar.id, False])], limit=500)
        off = set()
        for leave in leaves:
            if not leave.date_from or not leave.date_to:
                continue
            day, last = leave.date_from.date(), leave.date_to.date()
            while day <= last and len(off) < 5000:
                off.add(day)
                day = day.fromordinal(day.toordinal() + 1)

        def working(day):
            try:
                return day not in off and bool(calendar._works_on_date(day))
            except Exception:  # noqa: BLE001 — a calendar fault never blocks a start
                return True
        return tzname, working

    @api.model
    def _schedule_clock_on(self):
        job = self.env.ref('pb_lifecycle.cron_workflow_progress', raise_if_not_found=False)
        return bool(job and job.sudo().active)

    @api.model
    def _schedule_domain(self, w, definition):
        Model = self.env[w.source_model]
        types = {key: f.type for key, f in Model._fields.items()}
        domain = [('company_id', '=', w.company_id.id)] if 'company_id' in Model._fields else []
        return domain + D.native_domain(definition.get('scope') or {}, types)

    @api.model
    def _schedule_log(self, w, row):
        rows = [row] + list(w.schedule_log or [])
        internal(w).write({'schedule_log': rows[:LOG_KEEP]})

    # ------------------------------------------------------------- worker
    @api.model
    def _cron_workflows(self):
        """Scheduled starts first (each workflow in its own savepoint, one
        fault never stops the others or the usual work), then the usual
        work, which also processes the events made here."""
        try:
            self._schedule_pass(fields.Datetime.now())
        except Exception:  # noqa: BLE001
            _logger.exception('Workflow Studio: the schedule pass failed')
        return super()._cron_workflows()

    @api.model
    def _schedule_pass(self, now):
        started = 0
        for w in self.env['pb.workflow'].sudo().search([('enabled', '=', True), ('component', '=', False)]):
            definition = w.published_id.definition or {}
            schedule = self._schedule_of(definition)
            if not schedule:
                continue
            try:
                with self.env.cr.savepoint():
                    started += self._schedule_tick(w, definition, schedule, now)
            except Exception:  # noqa: BLE001
                _logger.exception('Workflow %s: the scheduled start failed', w.id)
        return started

    @api.model
    def _schedule_tick(self, w, definition, schedule, now):
        """Start what is due for one workflow. Returns the number of starts
        queued. Writes nothing when nothing is due (no write every minute)."""
        self.env.cr.execute('SELECT id FROM pb_workflow WHERE id=%s FOR UPDATE', [w.id])
        w.invalidate_recordset(['last_tick_at', 'schedule_log'])
        if not w.last_tick_at:
            internal(w).write({'last_tick_at': now})
            return 0
        tzname, working = self._company_clock(w.company_id)
        due = WS.ticks(schedule, tzname, w.last_tick_at, now, working)
        if not due:
            return 0
        tick = due[-1]
        stamp = fields.Datetime.to_string(tick)
        internal(w).write({'last_tick_at': now})
        if (w.schedule_log or [{}])[0].get('tick') == stamp:
            # this start was already made (a look that reached it twice)
            return 0
        row = {'tick': stamp, 'missed': len(due) - 1, 'started': 0, 'count': 0, 'reason': ''}
        service = system(self.env, w.company_id)['pb.workflow.studio']
        if not w.source_model:
            event = service._enqueue(w, 0, SUPERUSER_ID, 'schedule:%s:%s' % (w.id, stamp))
            if not event.scheduled_at:
                internal(event).write({'scheduled_at': tick})
            row.update(started=1, count=1)
            self._schedule_log(w, row)
            return 1
        domain = self._schedule_domain(w, definition)
        Model = service.env[w.source_model]
        count = Model.search_count(domain)
        cap = WS.FAN_OUT_CAP
        row['count'] = count
        if count > cap:
            row.update(reason='over_cap', cap=cap)
            self._schedule_log(w, row)
            self._schedule_tell_publisher(w, stamp, count, cap)
            return 0
        if not count:
            row['reason'] = 'nothing'
            self._schedule_log(w, row)
            return 0
        queued = 0
        for rec in Model.search(domain, order='id'):
            event = service._enqueue(w, rec.id, SUPERUSER_ID, 'schedule:%s:%s:%s' % (w.id, stamp, rec.id))
            if event.key.startswith('schedule:%s:%s:' % (w.id, stamp)):
                if not event.scheduled_at:
                    internal(event).write({'scheduled_at': tick})
                queued += 1
        row['started'] = queued
        if queued < count:
            row['reason'] = 'already_running'
        self._schedule_log(w, row)
        return queued

    @api.model
    def _schedule_tell_publisher(self, w, stamp, count, cap):
        person = w.published_id.published_by
        if not person or not person.active or person.share or person.id == SUPERUSER_ID:
            return False
        payload = {
            'summary': _('“%s” did not start on schedule', w.name),
            'body': _('%(count)s records matched “%(name)s” at its scheduled start, more than the '
                      '%(cap)s it may start at once, so it started none. Narrow its filters in '
                      'Workflow Studio, or split it into smaller workflows.',
                      count=count, name=w.name, cap=cap),
            'company_id': w.company_id.id, 'workflow_id': w.id}
        self.env['biz.approval.outbox'].sudo()._queue(
            'schedule_problem', person, payload=payload,
            dedupe='wf-schedule-cap-%s-%s' % (w.id, stamp))
        return True

    # ------------------------------------------------------- switching on
    @api.model
    def activate(self, workflow_id, enabled, acknowledge_existing=False):
        result = super().activate(workflow_id, enabled, acknowledge_existing=acknowledge_existing)
        w = self._workflow(workflow_id)
        if w.enabled and self._schedule_of(w.published_id.definition):
            # from now on; switching back on never catches up
            internal(w).write({'last_tick_at': fields.Datetime.now()})
        return result

    # ------------------------------------------------------------ preview
    @api.model
    def schedule_preview(self, workflow_id, trigger=None):
        """"Next 5 starts" and "Would start for 12 records today": the same
        functions the worker uses. Reads the draft, or the trigger the
        screen is editing (validated, never saved here)."""
        w = self._workflow(workflow_id)
        definition = dict(w.draft or {})
        if isinstance(trigger, dict):
            definition['trigger'] = trigger
        schedule = self._schedule_of(definition)
        if not schedule:
            return {'ok': False, 'issues': [], 'next': []}
        problems = WS.issues(schedule, bool(w.source_model), self.env.lang)
        result = {'ok': not problems, 'issues': [{'code': c, 'text': t} for c, t in problems],
                  'words': WS.words(schedule, self.env.lang), 'next': [], 'clock_on': self._schedule_clock_on(),
                  'cap': WS.FAN_OUT_CAP, 'count': None, 'names': [], 'over_cap': False}
        tzname, working = self._company_clock(w.company_id)
        result['tz'] = tzname
        if problems:
            return result
        now = fields.Datetime.now()
        for moment in WS.next_ticks(schedule, tzname, now, 5, working):
            local = fields.Datetime.context_timestamp(self.with_context(tz=tzname), moment)
            result['next'].append({'at': fields.Datetime.to_string(moment),
                                   'day': local.strftime('%a %-d %b %Y'),
                                   'time': '%d:%02d' % (local.hour, local.minute)})
        if w.source_model:
            try:
                service = system(self.env, w.company_id)['pb.workflow.studio']
                Model = service.env[w.source_model]
                domain = self._schedule_domain(w, definition)
                count = Model.search_count(domain)
                result.update(count=count, over_cap=count > WS.FAN_OUT_CAP,
                              names=[r.display_name for r in Model.search(domain, limit=5, order='id')])
            except (AccessError, UserError, ValueError):
                result['count'] = None
        return result

    @api.model
    def schedule_history(self, workflow_id):
        """Activity: the last starts made or not made, newest first, in
        words."""
        w = self._workflow(workflow_id, design=False)
        tzname, _working = self._company_clock(w.company_id)
        rows = []
        for row in (w.schedule_log or [])[:LOG_KEEP]:
            try:
                moment = fields.Datetime.to_datetime(row.get('tick'))
            except (TypeError, ValueError):
                continue
            if not isinstance(moment, datetime):
                continue
            local = fields.Datetime.context_timestamp(self.with_context(tz=tzname), moment)
            reason = row.get('reason') or ''
            if reason == 'over_cap':
                text = _('Did not start: %(count)s records matched, more than the %(cap)s it may start at once.',
                         count=row.get('count', 0), cap=row.get('cap', WS.FAN_OUT_CAP))
            elif reason == 'nothing':
                text = _('Nothing to start: no record matched.')
            elif reason == 'already_running':
                text = _('Started for %(started)s of %(count)s records; the others already had this workflow running.',
                         started=row.get('started', 0), count=row.get('count', 0))
            elif w.source_model:
                text = _('Started for %s records.', row.get('started', 0)) if row.get('started') != 1 \
                    else _('Started for 1 record.')
            else:
                text = _('Started.')
            if row.get('missed'):
                text += ' ' + (_('1 earlier start was missed while the system was off; it started once.')
                               if row['missed'] == 1 else
                               _('%s earlier starts were missed while the system was off; it started once.',
                                 row['missed']))
            rows.append({'day': local.strftime('%a %-d %b %Y'), 'time': '%d:%02d' % (local.hour, local.minute),
                         'text': text, 'problem': reason == 'over_cap'})
        return {'rows': rows, 'clock_on': self._schedule_clock_on()}

    # ------------------------------------------------------- design checks
    TRIGGER_LABELS = {'manual': 'Started by a person', 'created': 'When a record is created',
                      'changed': 'When selected fields change', 'date': 'Based on a record date',
                      'approval_applied': 'After approval is applied', 'schedule': 'On a schedule'}

    def _validate(self, w, definition):
        errors = super()._validate(w, definition)
        schedule = self._schedule_of(definition) if isinstance(definition, dict) else None
        if schedule is None or any(e.get('code', '').startswith('schedule_') for e in errors):
            return errors
        for code, text in WS.issues(schedule, bool(w.source_model), self.env.lang):
            if code == 'schedule_starts':
                errors.append({'id': 'trigger', 'code': code, 'text': text, 'severity': 'error'})
        if not w.source_model and (definition.get('scope') or {}).get('rules'):
            errors.append({'id': 'trigger', 'code': 'schedule_process_filters', 'severity': 'error', 'text': _(
                'A new process started on a schedule has no record to filter. Remove the filters.')})
        return errors

    def _schedule_review(self, w):
        """Review's "On a schedule" panel: the pattern in words, how many
        records it would start for now, and the double-up checks (R2):
        another switched-on workflow on the same records with the same
        pattern, and anything the area says it already does on its own
        timetable."""
        definition = w.draft or {}
        schedule = self._schedule_of(definition)
        if not schedule:
            return None
        preview = self.schedule_preview(w.id)
        warnings = []
        if not preview.get('clock_on'):
            warnings.append({'code': 'schedule_clock_off', 'text': _(
                "This site's workflow clock is switched off. Scheduled workflows here do not start "
                "until it is switched on.")})
        if preview.get('over_cap'):
            warnings.append({'code': 'schedule_over_cap', 'text': _(
                '%(count)s records match today, more than the %(cap)s a scheduled start may make at once. '
                'As it stands it would start none. Narrow the filters.',
                count=preview.get('count'), cap=WS.FAN_OUT_CAP)})
        canon = lambda value: repr(sorted((value or {}).items()))
        twins = self.env['pb.workflow'].sudo().search([
            ('company_id', '=', w.company_id.id), ('source_model', '=', w.source_model or False),
            ('enabled', '=', True), ('id', '!=', w.id), ('published_id', '!=', False)])
        for other in twins:
            theirs = self._schedule_of(other.published_id.definition)
            if not theirs:
                continue
            same_time = all(theirs.get(k) == schedule.get(k) for k in ('every', 'weekdays', 'day', 'month', 'date'))
            if same_time:
                warnings.append({'code': 'schedule_twin', 'text': _(
                    '“%(name)s” already starts %(when)s for %(which)s. Check this one does different work.',
                    name=other.name, when=WS.words(theirs, self.env.lang)[0].lower() + WS.words(theirs, self.env.lang)[1:],
                    which=self._scope_summary(other.source_model, other.published_id.definition.get('scope') or {}).lower()
                    if other.source_model else _('a new process'))})
        if w.source_model:
            contract = self._contract(w.source_model)
            for effect in contract.get('effects') or []:
                if effect.get('kind') == 'reminder' and not effect.get('stage'):
                    warnings.append({'code': 'schedule_area_chaser', 'text': _(
                        '%(area)s already does this on its own timetable: %(what)s',
                        area=effect.get('owner') or contract.get('area') or _('This area'),
                        what=effect.get('text') or '')})
        return {'words': preview.get('words'), 'count': preview.get('count'), 'names': preview.get('names'),
                'cap': WS.FAN_OUT_CAP, 'next': preview.get('next'), 'clock_on': preview.get('clock_on'),
                'warnings': warnings}

    @api.model
    def review(self, workflow_id):
        result = super().review(workflow_id)
        try:
            panel = self._schedule_review(self._workflow(workflow_id))
        except (AccessError, UserError):
            panel = None
        if panel:
            result['schedule'] = panel
        return result

    def _readable_starter(self, run):
        """Who started a run, in words: "Started on schedule" for a scheduled
        start (never the system account's name, R7)."""
        if run.sudo().scheduled_at:
            return _('Started on schedule')
        return run.initiator_id.name

    @api.model
    def runs(self, workflow_id=None, show_lines=False):
        rows = super().runs(workflow_id, show_lines=show_lines)
        scheduled = {r.id: r.scheduled_at for r in self.env['pb.workflow.run'].sudo().browse(
            [row['id'] for row in rows]) if r.scheduled_at}
        for row in rows:
            if row['id'] in scheduled:
                row.update(initiator=_('Started on schedule'), scheduled=True)
        return rows
