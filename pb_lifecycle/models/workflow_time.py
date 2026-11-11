"""WF2 P4b — where time goes.

Two sources, both real history (nothing is guessed):

  * the company's own stages — `pb.workflow.stage.visit`, one row per stay:
    opened when a record is put into a company stage, closed when it is put
    into the next one or leaves (written by the position model itself, so
    every path — a person's move, a workflow step, a stale row the engine
    removes — is counted, with or without a workflow running). A stale row
    is closed at the moment the area's own change history says the status
    changed, not when somebody happened to look.
  * the area's own statuses — read from the area's own change history (the
    status field is tracked on every area that declares a contract, except
    pay runs). No write hook is added to any area (R1, safety rail 1).

`time_report(workflow_id, period)` turns them into time per stage and per
step, in working time on the company calendar ("1 day 3 h"), with "Not
enough yet" under five records. Approval steps are read, never written, and
are labelled as Approvals' own.
"""
import bisect
import logging
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date

from . import workflow_definition as D
from .workflow_models import internal

_logger = logging.getLogger(__name__)

RUN = 'pb.workflow.run'
PERIODS = {'30': 30, '90': 90, 'all': None}
ENOUGH = 5
MAX_RECORDS = 1000
MAX_RUNS = 500


class WorkflowStageVisit(models.Model):
    """One stay of one record in one company stage."""
    _name = 'pb.workflow.stage.visit'
    _description = 'Time in a workflow stage'
    _inherit = ['pb.workflow.protected']
    _order = 'entered_at, id'

    company_id = fields.Many2one('res.company', required=True, index=True)
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    stage_id = fields.Many2one('pb.workflow.stage', required=True, ondelete='cascade', index=True)
    workflow_id = fields.Many2one('pb.workflow', ondelete='set null', index=True)
    entered_at = fields.Datetime(required=True, index=True)
    left_at = fields.Datetime(index=True)
    entered_by = fields.Many2one('res.users', ondelete='set null')
    #: Rebuilt from the workflow history on upgrade (only what it proves).
    backfilled = fields.Boolean()

    @api.model
    def _backfill(self):
        """Rebuild stays from the workflow history (1.15.0 upgrade): a stay
        is made ONLY when its "Moved to …" line and its end (a "Left …" line
        or the next "Moved to …") are both there, or when the record is
        still in that stage today. Nothing is guessed. Does nothing when any
        stay is already counted. Returns how many were made."""
        cr = self.env.cr
        cr.execute("SELECT 1 FROM pb_workflow_stage_visit LIMIT 1")
        if cr.fetchone():
            return 0
        cr.execute("""
            SELECT l.create_date, l.stage_id, l.actor_id, r.company_id,
                   COALESCE(NULLIF(r.source_model, ''), 'pb.workflow.run'),
                   CASE WHEN COALESCE(r.source_model, '') = '' THEN r.id ELSE r.source_id END,
                   r.workflow_id
              FROM pb_workflow_log l
              JOIN pb_workflow_run r ON r.id = l.run_id
             WHERE l.stage_id IS NOT NULL OR l.message LIKE 'Left %%'
             ORDER BY 5, 6, l.create_date, l.id""")
        rows = cr.fetchall()
        if not rows:
            return 0
        cr.execute("SELECT res_model, res_id, stage_id FROM pb_workflow_record_stage")
        current = {(m, i): s for m, i, s in cr.fetchall()}
        made, seen, open_ = [], set(), {}

        def keep(prior, left):
            stage, entered, actor, company, model, res_id, workflow = prior
            if (model, res_id, stage, entered) in seen:
                return
            seen.add((model, res_id, stage, entered))
            made.append({'company_id': company, 'res_model': model, 'res_id': res_id, 'stage_id': stage,
                         'workflow_id': workflow, 'entered_at': entered, 'left_at': left,
                         'entered_by': actor, 'backfilled': True})
        for at, stage, actor, company, model, res_id, workflow in rows:
            key = (model, res_id)
            if stage:
                # A "Moved to" line closes the stay before it and opens one.
                prior = open_.pop(key, None)
                if prior and prior[0] != stage:
                    keep(prior, at)
                open_[key] = prior if prior and prior[0] == stage else (stage, at, actor, company, model, res_id, workflow)
            elif key in open_ and open_[key][1] != at:
                # A "Left" line in the same instant as the "Moved to" belongs
                # to the stay before (one line is written per workflow).
                keep(open_.pop(key), at)
        for key, prior in open_.items():
            if current.get(key) == prior[0]:
                keep(prior, None)
        Stage = self.env['pb.workflow.stage'].sudo()
        alive = set(Stage.with_context(active_test=False).browse({m['stage_id'] for m in made}).exists().ids)
        made = [m for m in made if m['stage_id'] in alive]
        if made:
            internal(self).create(made)
        return len(made)


class WorkflowRecordStageVisits(models.Model):
    """The position row opens and closes visits itself."""
    _inherit = 'pb.workflow.record.stage'

    def _visit_close(self, when=None):
        Visit = internal(self.env['pb.workflow.stage.visit'])
        for row in self.sudo():
            open_ = Visit.search([('company_id', '=', row.company_id.id), ('res_model', '=', row.res_model),
                                  ('res_id', '=', row.res_id), ('left_at', '=', False)])
            if open_:
                open_.write({'left_at': when or fields.Datetime.now()})

    def _visit_open(self):
        Visit = internal(self.env['pb.workflow.stage.visit'])
        for row in self.sudo():
            Visit.create({'company_id': row.company_id.id, 'res_model': row.res_model, 'res_id': row.res_id,
                          'stage_id': row.stage_id.id, 'workflow_id': row.run_id.workflow_id.id or False,
                          'entered_at': row.entered_at or fields.Datetime.now(),
                          'entered_by': row.entered_by.id or False})

    @api.model_create_multi
    def create(self, vals_list):
        rows = super().create(vals_list)
        try:
            with self.env.cr.savepoint():
                rows._visit_close()
                rows._visit_open()
        except Exception:  # noqa: BLE001 — counting time never blocks a move
            _logger.exception('Workflow stage visits could not be opened')
        return rows

    def write(self, vals):
        moved = self.filtered(lambda r: 'stage_id' in vals and r.stage_id.id != vals['stage_id']) \
            if 'stage_id' in vals else self.browse()
        result = super().write(vals)
        if moved:
            try:
                with self.env.cr.savepoint():
                    moved._visit_close(vals.get('entered_at'))
                    moved._visit_open()
            except Exception:  # noqa: BLE001
                _logger.exception('Workflow stage visits could not be moved on')
        return result

    def unlink(self):
        try:
            with self.env.cr.savepoint():
                for row in self.sudo():
                    row._visit_close(row._left_at())
        except Exception:  # noqa: BLE001
            _logger.exception('Workflow stage visits could not be closed')
        return super().unlink()

    def _left_at(self):
        """When the record really left: the area's own record of its status
        changing after it entered, else now."""
        self.ensure_one()
        if self.res_model == RUN or self.res_model not in self.env:
            return fields.Datetime.now()
        field = self.env['pb.workflow.studio'].sudo()._contract(self.res_model).get('stage_field')
        changes = self.env['pb.workflow.studio'].sudo()._status_changes(self.res_model, [self.res_id], field,
                                                                         after=self.entered_at)
        times = [at for at, _old, _new in changes.get(self.res_id, [])]
        return min(times) if times else fields.Datetime.now()


class WorkflowTimeReport(models.AbstractModel):
    _inherit = 'pb.workflow.studio'

    # ------------------------------------------------------------ history
    def _status_changes(self, model, ids, field, after=None):
        """{res_id: [(when, old value key, new value key)]} from the area's
        own tracked history of its status field. Labels of a selection are
        mapped back to their keys in every installed language."""
        if not ids or not field or model not in self.env or field not in self.env[model]._fields:
            return {}
        info = self.env[model]._fields[field]
        params = [model, list(ids), model, field]
        extra = ''
        if after:
            extra = ' AND v.create_date > %s'
            params.append(after)
        self.env.cr.execute("""
            SELECT m.res_id, v.create_date, v.old_value_char, v.old_value_integer,
                   v.new_value_char, v.new_value_integer
              FROM mail_tracking_value v
              JOIN mail_message m ON m.id = v.mail_message_id
              JOIN ir_model_fields f ON f.id = v.field_id
             WHERE m.model = %s AND m.res_id = ANY(%s) AND f.model = %s AND f.name = %s""" + extra + """
          ORDER BY m.res_id, v.create_date, v.id""", params)
        labels = {}
        if info.type == 'selection':
            for code, _name in self.env['res.lang'].get_installed():
                selection = self.env[model].with_context(lang=code).fields_get(
                    [field], ['selection'])[field].get('selection') or []
                for key, label in selection:
                    labels.setdefault(str(label), key)

        def value(char, integer):
            if info.type == 'many2one':
                return integer or None
            return labels.get(str(char or ''))
        out = defaultdict(list)
        for res_id, when, old_c, old_i, new_c, new_i in self.env.cr.fetchall():
            new = value(new_c, new_i)
            if new is not None:
                out[res_id].append((when, value(old_c, old_i), new))
        return out

    # ---------------------------------------------------- working time
    def _work_clock(self, company, start, end):
        """(hours(a, b), hours per day, uses the calendar?) — working hours
        between two moments on the company calendar, from one read of its
        attendance for the whole range."""
        calendar = company.resource_calendar_id
        if not calendar or not start or not end or end <= start:
            return (lambda a, b: max(0.0, (b - a).total_seconds() / 3600.0)), 24.0, False
        utc = pytz.utc
        intervals = calendar._attendance_intervals_batch(utc.localize(start), utc.localize(end))[False]
        starts, stops, cum = [], [], [0.0]
        for a, b, _att in intervals:
            starts.append(a.timestamp())
            stops.append(b.timestamp())
            cum.append(cum[-1] + (b - a).total_seconds())

        def hours(a, b):
            x, y = utc.localize(a).timestamp(), utc.localize(b).timestamp()
            if y <= x:
                return 0.0
            i = bisect.bisect_right(stops, x)
            j = bisect.bisect_left(starts, y)
            if i >= j:
                return 0.0
            total = cum[j] - cum[i] - max(0.0, x - starts[i]) - max(0.0, stops[j - 1] - y)
            return max(0.0, total) / 3600.0
        return hours, float(calendar.hours_per_day or 8.0), True

    def _duration_words(self, hours, per_day):
        if hours is None:
            return ''
        if hours < 1:
            minutes = max(1, int(round(hours * 60)))
            return _('%s min', minutes)
        if hours < per_day:
            return _('%s h', int(round(hours)))
        days = int(hours // per_day)
        rest = int(round(hours - days * per_day))
        if rest >= per_day:
            days, rest = days + 1, 0
        day_words = _('1 day') if days == 1 else _('%s days', days)
        return '%s %s' % (day_words, _('%s h', rest)) if rest else day_words

    @staticmethod
    def _p90(values):
        ordered = sorted(values)
        # Nearest rank: the value nine in ten are at or under.
        return ordered[max(0, math.ceil(0.9 * len(ordered)) - 1)] if ordered else None

    # ------------------------------------------------------- timelines
    def _timelines(self, model, records, company, now):
        """{res_id: [(kind, key, start, end or None)]} — the area's statuses
        minus the stays in company stages, plus those stays."""
        contract = self._contract(model)
        field = contract.get('stage_field')
        changes = self._status_changes(model, records.ids, field) if field else {}
        visits = defaultdict(list)
        for v in self.env['pb.workflow.stage.visit'].sudo().search([
                ('company_id', '=', company.id), ('res_model', '=', model), ('res_id', 'in', records.ids)]):
            visits[v.res_id].append(('yours', v.stage_id.id, v.entered_at, v.left_at or None))
        out = {}
        for record in records:
            history = changes.get(record.id, [])
            current = self._status_value(contract, record)
            if history:
                first = history[0][1] if history[0][1] is not None else current
                core = [('core', first, record.create_date, history[0][0])]
                for i, (when, _old, new) in enumerate(history):
                    core.append(('core', new, when, history[i + 1][0] if i + 1 < len(history) else None))
            else:
                core = [('core', current, record.create_date, None)]
            own = visits.get(record.id, [])
            segments = []
            for kind, key, start, end in core:
                # A stay in a company stage counts there, not at its anchor.
                pieces = [(start, end)]
                for _k, _s, vs, ve in own:
                    cut = []
                    for a, b in pieces:
                        b_ = b or now
                        ve_ = ve or now
                        if vs >= b_ or ve_ <= a:
                            cut.append((a, b))
                            continue
                        if vs > a:
                            cut.append((a, vs))
                        if ve_ < b_:
                            cut.append((ve_, b))
                    pieces = cut
                for a, b in pieces:
                    segments.append(('core', key, a, b))
            segments += own
            out[record.id] = segments
        return out

    # ---------------------------------------------------------- facade
    @api.model
    def time_report(self, workflow_id, period='90'):
        """Where time goes for one workflow (Activity tab)."""
        self._progress_permission()
        w = self.env['pb.workflow'].sudo().browse(int(workflow_id or 0)).exists()
        if not w or w.company_id not in self.env.companies:
            raise AccessError(_('This workflow is not available in your current company.'))
        period = str(period) if str(period) in PERIODS else '90'
        now = fields.Datetime.now()
        days = PERIODS[period]
        since = now - timedelta(days=days) if days else None
        company = w.company_id
        Run = self.env[RUN].sudo()
        domain = [('workflow_id', '=', w.id), ('company_id', '=', company.id)]
        ever = Run.search_count(domain)
        if not ever:
            return {'workflow_id': w.id, 'period': period, 'empty': True}
        runs = Run.search(domain + ([('create_date', '>=', since)] if since else []), order='id desc', limit=MAX_RUNS)
        model = w.source_model or ''
        try:
            stages_out, _live = self._report_stages(w, model, company, runs, since, now)
            steps_out = self._report_steps(w, runs, now)
        except Exception:  # noqa: BLE001 — a plain sentence, never a server message
            _logger.exception('Where time goes failed for workflow %s', w.id)
            raise UserError(_('Where time goes could not be worked out just now. Try again in a moment.'))
        first = min([r.create_date for r in Run.search(domain, order='id', limit=1)] +
                    [v.entered_at for v in self.env['pb.workflow.stage.visit'].sudo().search(
                        [('company_id', '=', company.id), ('res_model', '=', model or RUN)], order='entered_at', limit=1)])
        calendar = bool(company.resource_calendar_id)
        return {'workflow_id': w.id, 'period': period, 'empty': False, 'runs': len(runs),
                'records': stages_out.pop('records', 0), 'stages': stages_out['rows'], 'steps': steps_out,
                'sitting_total': sum(s['sitting'] for s in stages_out['rows']),
                'calendar': calendar,
                'counting_since': format_date(self.env, first.date(), date_format='d MMM yyyy')
                if first and (not since or first > since) else '',
                'enough': ENOUGH}

    def _report_stages(self, w, model, company, runs, since, now):
        Pos = self.env['pb.workflow.record.stage'].sudo()
        if model:
            contract = self._contract(model)
            stages = self._user_stages(model, self.env['pb.workflow'], company)
            track = [(k, i) for k, i in self._merged(contract, stages) if not (k == 'core' and i.get('exit'))]
            ids = list(dict.fromkeys(runs.mapped('source_id')))[:MAX_RECORDS]
            Visit = self.env['pb.workflow.stage.visit'].sudo()
            vdomain = [('company_id', '=', company.id), ('res_model', '=', model)] + (
                [('entered_at', '>=', since)] if since else [])
            ids = list(dict.fromkeys(ids + Visit.search(vdomain, limit=MAX_RECORDS).mapped('res_id')))[:MAX_RECORDS]
            records = self.env[model].sudo().browse(ids).exists()
            records = records.filtered(lambda r: 'company_id' not in r._fields or r.company_id == company)
            lines = self._timelines(model, records, company, now)
            live = runs.filtered(lambda r: r.state in ('running', 'waiting', 'failed', 'held'))
            live_ids = set(live.mapped('source_id'))
            runs_of = defaultdict(list)
            for r in live:
                runs_of[r.source_id].append(r.id)
        else:
            stages = self._user_stages('', w, company)
            track = [('yours', s) for s in stages]
            records = runs
            lines = defaultdict(list)
            for v in self.env['pb.workflow.stage.visit'].sudo().search([
                    ('company_id', '=', company.id), ('res_model', '=', RUN), ('res_id', 'in', runs.ids)]):
                lines[v.res_id].append(('yours', v.stage_id.id, v.entered_at, v.left_at or None))
            live_ids = set(runs.filtered(lambda r: r.state in ('running', 'waiting', 'failed', 'held')).ids)
            runs_of = {i: [i] for i in live_ids}
        starts = [seg[2] for segs in lines.values() for seg in segs if seg[2]]
        clock, per_day, _calendar = self._work_clock(company, min(starts) if starts else now - timedelta(days=1), now)
        rows = []
        for kind, item in track:
            key = item['key'] if kind == 'core' else item.id
            durations, late, passed, sitting, spent, sitting_runs = [], 0, set(), 0, 0.0, []
            target = item.target_hours if kind == 'yours' else 0
            for res_id, segs in lines.items():
                for k, value, start, end in segs:
                    if k != kind or str(value) != str(key):
                        continue
                    if end is None:
                        if kind == 'yours' or res_id in live_ids:
                            sitting += 1
                            sitting_runs += runs_of.get(res_id, [])
                        spent += clock(max(start, since) if since else start, now)
                        continue
                    if since and end < since:
                        continue
                    hours = clock(start, end)
                    durations.append(hours)
                    spent += hours
                    passed.add(res_id)
                    if target and (end - start).total_seconds() > target * 3600:
                        late += 1
            if kind == 'yours':
                # The live positions, read the way every screen reads them.
                sitting = max(sitting, len(self._occupants(item))) if model else sitting
            enough = len(durations) >= ENOUGH
            median = statistics.median(durations) if durations else None
            rows.append({'key': str(key), 'kind': kind, 'name': item['name'] if kind == 'core' else item.name,
                         'passed': len(passed), 'samples': len(durations), 'enough': enough,
                         'median_words': self._duration_words(median, per_day) if enough else '',
                         'p90_words': self._duration_words(self._p90(durations), per_day) if enough else '',
                         'late_share': int(round(100.0 * late / len(durations))) if target and enough else None,
                         'target_words': _('%s h', target) if target else '',
                         'sitting': sitting, 'run_ids': sitting_runs[:200], 'spent': spent})
        total = sum(r['spent'] for r in rows) or 0.0
        for r in rows:
            r['share'] = round(100.0 * r['spent'] / total, 1) if total else 0.0
            r.pop('spent')
        return {'rows': rows, 'records': len(records)}, live_ids

    def _report_steps(self, w, runs, now):
        Step = self.env['pb.workflow.step'].sudo()
        steps = Step.search([('run_id', 'in', runs.ids), ('kind', 'in', list(D.PEOPLE) + ['matrix'])])
        if not steps:
            return []
        company = w.company_id
        starts = [s.started_at for s in steps if s.started_at]
        clock, per_day, _calendar = self._work_clock(company, min(starts) if starts else now - timedelta(days=1), now)
        draft = {n['id']: n for n in (w.draft or {}).get('nodes', [])}
        loops = Counter()
        for back in Step.search([('run_id', 'in', runs.ids), ('kind', '=', 'send_back')]):
            target = (back.config or {}).get('target')
            if target and str(back.choice or '').isdigit():
                loops[target] += int(back.choice)
        groups = defaultdict(list)
        for s in steps:
            groups[s.key].append(s)
        out = []
        for key, rows in groups.items():
            kind = rows[0].kind
            title = (draft.get(key) or {}).get('title') or rows[-1].name
            waits, late, reminders, passed_up, waiting, who = [], 0, 0, 0, 0, Counter()
            for s in rows:
                if kind == 'matrix':
                    request = s.approval_id
                    marks = request.step_ids.filtered(lambda x: x.activated_at) if request else []
                    if marks:
                        begin = min(marks.mapped('activated_at'))
                        decided = [d for d in marks.mapped('decided_at') if d]
                        if request.state in ('approved', 'rejected', 'applied', 'cancelled') and decided:
                            waits.append(clock(begin, max(decided)))
                        elif s.state == 'waiting':
                            waiting += 1
                    continue
                if s.state == 'waiting':
                    waiting += 1
                    if s.due_at and now >= s.due_at:
                        late += 1
                elif s.state == 'done' and s.started_at and s.done_at:
                    waits.append(clock(s.started_at, s.done_at))
                    if s.due_at and s.done_at > s.due_at:
                        late += 1
                reminders += 1 if s.reminded_at else 0
                passed_up += 1 if s.passed_up_at else 0
                role = self._team_role(s)
                name = role.name if role and not s.assignee_id else s.assignee_id.name or (
                    _('Someone by email link') if s.link_name or s.sudo().link_email else '')
                if name:
                    who[name] += 1
            enough = len(waits) >= ENOUGH
            median = statistics.median(waits) if waits else None
            counted = len(waits) + waiting
            out.append({'key': key, 'title': title, 'kind': kind, 'approval': kind == 'matrix',
                        'who': _('Approvals') if kind == 'matrix' else (who.most_common(1)[0][0] if who else ''),
                        'samples': len(waits), 'enough': enough, 'median': median or 0.0,
                        'median_words': self._duration_words(median, per_day) if enough else '',
                        'late': late, 'late_share': int(round(100.0 * late / counted)) if counted and kind != 'matrix' else None,
                        'sent_back': loops.get(key, 0), 'reminders': reminders, 'passed_up': passed_up,
                        'waiting': waiting, 'exists': key in draft})
        out.sort(key=lambda r: (not r['enough'], -r['median'], -r['waiting'], r['title']))
        for r in out:
            r.pop('median')
        return out[:5]
