"""WF2 P5c — "Repeat for each…": a group of steps run once per line.

A repeat is a container step on the main path (`type: 'repeat'`, its steps in
`steps`, like a saved group) with a `source` (what to repeat for), a `mode`
(`together` / `one_by_one`), a `join` (`all` / `any`) and a cap (`max_lines`,
default 50, never above 200). Sources:

  * `area`    — the record's own lines, read only through the area's door
                (`_workflow_capabilities()['lines']` + `record._workflow_lines
                (key)`); expense claims declare their receipts;
  * `answers` — each answer of a list question (a multi-choice field, or each
                row of a line-items field) given earlier in this workflow;
  * `team`    — each person on an Approvals team.

ONE LINE = ONE RUN. When the repeat is reached the lines are read once (a
line added later is not picked up), and one run per line is started with
`parent_id`, the line's label and values. A line run walks the repeat's steps
as its main path (`pb.workflow.run._definition`), so tasks, forms, waits,
paths, messages, send backs and "Stop here" work inside a line exactly as they
do anywhere else, and a "Stop here" or a send back touches that line only. A
line is started once: its start key `line:<run>:<step>:<round>:<line>` is
unique. The parent waits on the repeat step and looks again whenever a line
moves (`_repeat_bounce`) and on every worker pass; it carries on when every
line is done (or the first one, for "any"), with the counts as values
(`step.<repeat>.count` / `.done` / `.<task>__<button>`). A line that needs
attention marks the repeat "1 of 5 lines needs attention"; Retry is per line.

Lines are never runs anywhere a person counts runs: the record strip, the
runs table (unless "Show lines"), "where time goes", record progress. Lines
run at system level like every run (R3, ledger G1) and inherit the parent's
company, record, version and starter.

No local is called `user` or `uid` in a method that calls `_()` (ledger G12).
"""
import copy
import json
import logging
import statistics
from collections import Counter
from datetime import timedelta

from odoo import SUPERUSER_ID, api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.http import request
from odoo.tools.misc import format_date

from . import workflow_definition as D
from .workflow_models import internal

_logger = logging.getLogger(__name__)

OPEN = ('running', 'waiting', 'failed', 'held')
#: The inbox shows a person's line tasks of one repeat one by one up to this
#: many; beyond it they are one card ("Do all in turn").
GROUP_CARDS = 5
#: Lines started inside a person's own click (their answer reached the
#: repeat); the worker starts the rest on its next pass, so nobody waits
#: on a page while two hundred lines are made. The worker starts them all.
LINE_BATCH = 25


def _line_value_words(value):
    """A line detail as plain words for the activity history."""
    if value in (None, '', False):
        return '—'
    if value is True:
        return _('yes')
    if isinstance(value, float):
        return ('%d' % value) if value == int(value) else ('%.2f' % value)
    return str(value)


class WorkflowRunLines(models.Model):
    _inherit = 'pb.workflow.run'

    #: WF2 P5c: the run whose repeat started this line (empty for every run
    #: a person or a record started).
    parent_id = fields.Many2one('pb.workflow.run', ondelete='cascade', index=True, copy=False)
    parent_step_key = fields.Char(copy=False)
    line_key = fields.Char(copy=False)
    line_label = fields.Char(copy=False)
    line_values = fields.Json(copy=False)
    line_number = fields.Integer(copy=False)
    line_count = fields.Integer(copy=False)
    line_round = fields.Integer(copy=False, default=0)
    line_start_key = fields.Char(copy=False, index=True)
    line_ids = fields.One2many('pb.workflow.run', 'parent_id')
    _unique_line_start = models.Constraint('unique(line_start_key)', 'This line has already been started.')

    # ------------------------------------------------------------- shape
    def _definition(self):
        """The definition this run walks: its version, or for one line of a
        repeat the repeat's steps as the main path."""
        srun = self.sudo()
        d = srun.version_id.definition
        if srun.parent_id and srun.parent_step_key:
            return D.line_view(d, srun.parent_step_key)
        return d

    def _initialize(self):
        self.ensure_one()
        srun = self.sudo()
        d = srun.version_id.definition
        if srun.parent_id:
            view = self._definition()
            keys = set(k for top in view['order'] for k in D.descendants(view, top))
        else:
            inner = set(k for n in d['nodes'] if n.get('type') == 'repeat'
                        for top in n.get('steps') or [] for k in D.descendants(d, top))
            if not inner:
                return super()._initialize()
            keys = set(n['id'] for n in d['nodes']) - inner
        internal(self.env['pb.workflow.step']).create([{
            'run_id': self.id, 'company_id': srun.company_id.id,
            'key': n['id'], 'name': n['title'], 'kind': n['type'],
            'config': copy.deepcopy(n), 'state': 'pending', 'position': i,
        } for i, n in enumerate(d['nodes']) if n['id'] in keys])
        if srun.parent_id:
            self._log(_('Started for %(line)s (%(n)s of %(count)s).', line=srun.line_label,
                        n=srun.line_number, count=srun.line_count))
        else:
            self._log(_('Started version %s.', srun.version_id.number))

    # ------------------------------------------------------------ advance
    def _advance(self):
        before = self.sudo().state
        srun = self.sudo()
        # WF2 P6a: a line's details are read again whenever one of its steps
        # may open (a step not started yet), so a receipt edited after the
        # repeat started shows its current details; a line that is gone is
        # closed instead of walked.
        gone = bool(srun.parent_id) and before in ('running', 'waiting', 'failed') \
            and not self.env.context.get('_pb_wf_line_fresh') and self._repeat_refresh_line() is False
        result = None if gone else super()._advance()
        srun = self.sudo()
        if srun.state in ('done', 'cancelled', 'rejected') and srun.line_ids:
            # The run is over (finished, stopped, turned down): its lines too.
            srun._repeat_close_lines(srun.line_ids.filtered(lambda r: r.state in OPEN),
                                     _('Stopped: the workflow it belongs to has ended.'))
        if srun.parent_id and srun.state != before and not self.env.context.get('_pb_wf_from_parent'):
            parent = srun.parent_id
            if parent.state in ('running', 'waiting', 'failed'):
                parent._advance()
        return result

    # ------------------------------------------------- line read again (P6a)
    def _repeat_refresh_line(self):
        """Read this line again through the area's door before a step of it
        opens. Returns False when the line is gone (closed here), True
        otherwise. Never fails: when the record or the door cannot be read,
        the details captured at the start stay."""
        self.ensure_one()
        srun = self.sudo()
        if not any(s.state == 'pending' for s in srun.step_ids):
            return True
        d = srun.version_id.definition or {}
        node = next((x for x in d.get('nodes', []) if x.get('id') == srun.parent_step_key), {})
        src = node.get('source') if isinstance(node.get('source'), dict) else {}
        if src.get('kind') != 'area' or not srun.source_model:
            return True
        service = self._service()
        try:
            source = srun._source()
            row = service._repeat_line_now(source, src.get('key'), srun.line_key)
        except Exception:  # noqa: BLE001 — keep the details from the start
            _logger.info('Workflow line %s: details could not be read again; kept as at the start', srun.id)
            return True
        if row is False:
            return True
        parent_step = srun.parent_id.step_ids.filtered(lambda s: s.key == srun.parent_step_key)[:1]
        if row is None:
            srun._repeat_line_gone(parent_step, service._repeat_words(srun.source_model, node, d))
            return False
        start = next((dict(x.get('values') or {}) for x in (parent_step.answers or {}).get('_lines') or []
                      if str(x.get('key')) == str(srun.line_key)), dict(srun.line_values or {}))
        values = dict(row.get('values') or {})
        label = str(row.get('name') or '')
        if values == dict(srun.line_values or {}) and label == (srun.line_label or ''):
            return True
        names = {f['key']: f.get('label') or f['key'] for f in service._line_fields(srun.source_model, node, d)}
        said = []
        for key in [k for k in names if values.get(k) != (srun.line_values or {}).get(k)]:
            said.append(_('%(what)s is now %(now)s (was %(then)s at the start).', what=names[key],
                          now=_line_value_words(values.get(key)), then=_line_value_words(start.get(key))))
        facts = dict(srun.facts or {})
        facts.update({'line.%s' % k: v for k, v in values.items()})
        facts['line.label'] = label
        internal(srun).write({'line_values': values, 'line_label': label, 'facts': facts})
        if said:
            self._log(_('Line details read again: %s', ' '.join(said)))
        return True

    def _repeat_line_gone(self, parent_step, words):
        """The line is no longer on the record: its open steps close with a
        plain note, the line ends, and the repeat counts one line fewer."""
        srun = self.sudo()
        note = _('This %(one)s is no longer on the record, so its steps were closed.', one=words['singular'])
        for s in srun.step_ids.filtered(lambda x: x.state not in ('done', 'skipped')):
            s._cancel_activity()
            internal(s).write({'state': 'skipped', 'error': note})
        internal(srun).write({'state': 'cancelled', 'ended_at': fields.Datetime.now()})
        self._log(_('%(line)s is no longer on the record, so this line was closed.', line=srun.line_label or words['singular']))
        if not parent_step:
            return
        found = [x for x in (parent_step.answers or {}).get('_lines') or [] if str(x.get('key')) != str(srun.line_key)]
        state = json.loads(parent_step.choice) if str(parent_step.choice or '').startswith('{') else {}
        state['count'] = len(found)
        internal(parent_step).write({'answers': dict(parent_step.answers or {}, _lines=found), 'choice': json.dumps(state)})
        siblings = srun.parent_id._repeat_lines_of(parent_step).filtered(
            lambda r: r.line_round == srun.line_round and r.id != srun.id and r.line_key in {str(x['key']) for x in found})
        for sib in siblings:
            internal(sib).write({'line_count': len(found),
                                 'line_number': sib.line_number - 1 if sib.line_number > srun.line_number else sib.line_number})
        srun.parent_id._log(_('%(line)s is no longer on the record: %(count)s %(lines)s left in this repeat.',
                              line=srun.line_label or words['singular'], count=len(found),
                              lines=words['plural'] if len(found) != 1 else words['singular']), parent_step)

    def _repeat_close_lines(self, lines, reason):
        for line in lines:
            for s in line.step_ids:
                s._cancel_activity()
            internal(line).write({'state': 'cancelled', 'ended_at': fields.Datetime.now()})
            line._log(reason)

    def _repeat_lines_of(self, step):
        return internal(self.env['pb.workflow.run']).search(
            [('parent_id', '=', self.id), ('parent_step_key', '=', step.key)], order='line_round, line_number, id')

    def _repeat_visit(self, s, n):
        """Visit a repeat step: start its lines, or look at them. True when
        it is done and the walk may carry on."""
        self.ensure_one()
        srun = self.sudo()
        lines = srun._repeat_lines_of(s)
        service = self._service()
        if s.state == 'pending':
            # The first time, or put back by a send back from later on: a
            # fresh round. Lines of an earlier round still open are stopped.
            srun._repeat_close_lines(lines.filtered(lambda r: r.state in OPEN),
                                     _('Stopped: it was sent back and starts again.'))
            found = service._repeat_lines(srun, n)
            words = service._repeat_words(srun.source_model or '', n, srun.version_id.definition)
            cap = min(int(n.get('max_lines') or D.REPEAT_DEFAULT), D.REPEAT_HARD)
            if len(found) > cap:
                raise UserError(_('There are %(count)s %(lines)s, more than the %(cap)s this repeats for, so none '
                                  'were started. Raise the limit in the step or narrow it down, then retry.',
                                  count=len(found), lines=words['plural'], cap=cap))
            started = fields.Datetime.now()
            if not found:
                internal(s).write({'started_at': started})
                s._finish({'count': 0, 'done': 0})
                internal(s).write({'error': _('There were no %s, so nothing was repeated.', words['plural'])})
                self._log(_('Nothing to repeat: there were no %s.', words['plural']), s)
                return True
            round_ = max(lines.mapped('line_round') or [0]) + 1
            internal(s).write({'state': 'active', 'started_at': s.started_at or started, 'error': False,
                               'choice': json.dumps({'round': round_, 'count': len(found)}),
                               'answers': {'_lines': found}})
            self._log(_('Repeating for %(count)s %(lines)s, %(how)s.', count=len(found),
                        lines=words['plural'] if len(found) != 1 else words['singular'],
                        how=_('together') if n.get('mode', 'together') == 'together' else _('one by one')), s)
        state = json.loads(s.choice) if str(s.choice or '').startswith('{') else {}
        round_ = state.get('round') or max(lines.mapped('line_round') or [0])
        found = (s.answers or {}).get('_lines') or []
        # WF2 P6a: a line that is gone from the record is out of `found`.
        keys = {str(x['key']) for x in found}
        mine = lines.filtered(lambda r: r.line_round == round_ and r.line_key in keys)
        if len(mine) < len(found):
            started = set(mine.mapped('line_key'))
            todo = [(i, line) for i, line in enumerate(found) if str(line['key']) not in started]
            if n.get('mode', 'together') == 'one_by_one':
                todo = todo[:1] if all(r.state in ('done', 'cancelled') for r in mine) else []
            elif request:
                todo = todo[:LINE_BATCH]
            for i, line in todo:
                srun._repeat_start_line(s, line, i + 1, len(found), round_)
            if todo:
                mine = srun._repeat_lines_of(s).filtered(lambda r: r.line_round == round_ and r.line_key in keys)
        done = mine.filtered(lambda r: r.state == 'done')
        failed = mine.filtered(lambda r: r.state == 'failed')
        over = mine.filtered(lambda r: r.state in ('done', 'cancelled', 'rejected'))
        words = service._repeat_words(srun.source_model or '', n, srun.version_id.definition)
        if n.get('join', 'all') == 'any' and done:
            srun._repeat_close_lines(mine.filtered(lambda r: r.state in OPEN),
                                     _('Stopped: another line finished first.'))
            srun._repeat_finish(s, n, found, mine, words)
            return True
        if len(over) == len(found) and len(mine) == len(found):
            srun._repeat_finish(s, n, found, mine, words)
            return True
        if failed:
            text = (_('1 of %s lines needs attention.', len(found)) if len(failed) == 1 else
                    _('%(n)s of %(count)s lines need attention.', n=len(failed), count=len(found)))
            if s.state != 'failed' or s.error != text:
                internal(s).write({'state': 'failed', 'error': text})
                self._log(text, s)
        elif s.state != 'active':
            internal(s).write({'state': 'active', 'error': False})
        return False

    def _repeat_start_line(self, s, line, number, count, round_):
        """Start one line, once (its start key is unique)."""
        key = 'line:%s:%s:%s:%s' % (self.id, s.key, round_, line['key'])
        Run = internal(self.env['pb.workflow.run'])
        old = Run.search([('line_start_key', '=', key)], limit=1)
        if old:
            return old
        srun = self.sudo()
        facts = dict(self._values())
        values = dict(line.get('values') or {})
        facts.update({'line.%s' % k: v for k, v in values.items()})
        facts.update({'line.label': line.get('label') or '', 'line.number': number})
        child = Run.create({
            'name': srun.name, 'workflow_id': srun.workflow_id.id, 'version_id': srun.version_id.id,
            'company_id': srun.company_id.id, 'source_model': srun.source_model,
            'source_id': srun.source_id, 'initiator_id': srun.initiator_id.id,
            'facts': facts,
            'scheduled_at': False, 'parent_id': self.id, 'parent_step_key': s.key,
            'line_key': str(line['key']), 'line_label': line.get('label') or '', 'line_values': values,
            'line_number': number, 'line_count': count, 'line_round': round_, 'line_start_key': key})
        child._initialize()
        # Its details were read a moment ago: no second read (WF2 P6a).
        child.with_context(_pb_wf_from_parent=True, _pb_wf_line_fresh=True)._advance()
        return child

    def _repeat_finish(self, s, n, found, mine, words):
        done = mine.filtered(lambda r: r.state == 'done')
        answers = {'count': len(found), 'done': len(done), '_lines': found}
        outcomes = Counter()
        for line in done:
            for step in line.sudo().step_ids:
                chosen = (step.answers or {}).get('outcome') if step.state == 'done' else None
                if chosen and step.kind == 'task':
                    outcomes['%s__%s' % (step.key, chosen)] += 1
        answers.update(outcomes)
        s._finish(answers)
        if n.get('join', 'all') == 'any':
            first = done.sorted(lambda r: (r.ended_at or r.write_date, r.id))[:1]
            self._log(_('%(line)s finished first; the other lines were stopped.', line=first.line_label), s)
        else:
            self._log(_('All %(count)s %(lines)s finished (%(done)s done).', count=len(found),
                        lines=words['plural'] if len(found) != 1 else words['singular'], done=len(done)), s)


class WorkflowRepeat(models.AbstractModel):
    _inherit = 'pb.workflow.studio'

    # ============================================================ sources
    def _area_lines(self, model):
        """What the area declares as lines of its records ([] when none)."""
        declared = self._declared(model) if model else {}
        return [dict(l) for l in declared.get('lines') or [] if isinstance(l, dict) and l.get('key')]

    def _answer_sources(self, d):
        """List questions on the main path a repeat may go through."""
        out = []
        order = (d or {}).get('order') or []
        for n in (d or {}).get('nodes') or []:
            if n.get('type') != 'input' or n.get('id') not in order:
                continue
            for f in (n.get('form') or {}).get('fields') or []:
                if f.get('type') in ('multiselect', 'rows'):
                    out.append({'step': n['id'], 'field': f.get('id'), 'label': f.get('label') or '',
                                'step_title': n.get('title') or '', 'rows': f.get('type') == 'rows'})
        return out

    def _repeat_words(self, model, n, d=None):
        """{'singular', 'plural', 'each'} for a repeat's lines, in words."""
        src = n.get('source') if isinstance(n.get('source'), dict) else {}
        kind = src.get('kind')
        if kind == 'area':
            spec = next((l for l in self._area_lines(model) if l['key'] == src.get('key')), None)
            if spec:
                singular = str(spec.get('singular') or spec.get('label') or _('line')).lower()
                plural = str(spec.get('label') or singular).lower()
                return {'singular': singular, 'plural': plural, 'each': _('For each %s', singular)}
        if kind == 'team':
            role = self.env['biz.approval.role'].sudo().browse(int(src.get('id') or 0)).exists()
            return {'singular': _('person'), 'plural': _('people'),
                    'each': _('For each person on %s', role.name) if role else _('For each person on a team')}
        if kind == 'answers':
            found = next((a for a in self._answer_sources(d) if a['step'] == src.get('step')
                          and a['field'] == src.get('field')), None)
            if found and found['rows']:
                return {'singular': _('line'), 'plural': _('lines'),
                        'each': _('For each line of “%s”', found['label'])}
            return {'singular': _('answer'), 'plural': _('answers'),
                    'each': _('For each answer to “%s”', found['label']) if found else _('For each answer')}
        return {'singular': _('line'), 'plural': _('lines'), 'each': _('For each line')}

    def _repeat_line_now(self, source, key, line_key):
        """One line of the record as the area gives it now (WF2 P6a):
        the row, None when the line is no longer there, or False when the
        area offers no way to read it (the start snapshot then stays)."""
        if hasattr(source, '_workflow_line'):
            return source._workflow_line(key, line_key)
        if hasattr(source, '_workflow_lines'):
            return next((r for r in source._workflow_lines(key) or [] if str(r.get('id')) == str(line_key)), None)
        return False

    def _repeat_lines(self, run, n):
        """The lines of a repeat for this run: [{key, label, values}], read
        through the area's door, the run's own answers, or Approvals."""
        src = n.get('source') if isinstance(n.get('source'), dict) else {}
        kind = src.get('kind')
        if kind == 'area':
            if not run.source_model:
                raise UserError(_('A new process has no record with lines. Edit the step.'))
            source = run._source()
            if not any(l['key'] == src.get('key') for l in self._area_lines(run.source_model)) \
                    or not hasattr(source, '_workflow_lines'):
                raise UserError(_('%s no longer offers these lines to workflows. Edit the step.',
                                  self._contract(run.source_model).get('area') or _('This area')))
            rows = source._workflow_lines(src['key']) or []
            return [{'key': str(r['id']), 'label': str(r.get('name') or ''), 'values': dict(r.get('values') or {})}
                    for r in rows]
        if kind == 'answers':
            value = run._values().get('step.%s.%s' % (src.get('step'), src.get('field')))
            if value in (None, ''):
                return []
            if not isinstance(value, list):
                raise UserError(_('The answer this repeats for is not a list. Edit the step.'))
            out = []
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    label = str(item.get('description') or '')
                    out.append({'key': str(i + 1), 'label': label,
                                'values': {'description': label, 'amount': item.get('amount')}})
                else:
                    out.append({'key': str(i + 1), 'label': str(item), 'values': {'value': item}})
            return out
        if kind == 'team':
            role = self.env['biz.approval.role'].sudo().browse(int(src.get('id') or 0)).exists()
            if not role or not role.is_pool:
                raise UserError(_('Choose one of the teams from Approvals › Who approves. Edit the step.'))
            members = self._team_members(role, run.company_id, run)
            return [{'key': 'u%s' % m.id, 'label': m.name, 'values': {'person': m.id}}
                    for m in members.sorted(lambda m: (m.name or '', m.id))]
        raise UserError(_('Choose what this repeats for. Edit the step.'))

    def _line_fields(self, model, n, d):
        """[{key, label, type}] a line carries, for conditions and owners."""
        src = n.get('source') if isinstance(n.get('source'), dict) else {}
        kind = src.get('kind')
        if kind == 'area':
            spec = next((l for l in self._area_lines(model) if l['key'] == src.get('key')), None)
            return [dict(f) for f in (spec or {}).get('fields') or [] if isinstance(f, dict) and f.get('key')]
        if kind == 'team':
            return [{'key': 'person', 'label': _('Person'), 'type': 'person'}]
        if kind == 'answers':
            found = next((a for a in self._answer_sources(d) if a['step'] == src.get('step')
                          and a['field'] == src.get('field')), None)
            if found and found['rows']:
                return [{'key': 'description', 'label': _('Description'), 'type': 'text'},
                        {'key': 'amount', 'label': _('Amount'), 'type': 'number'}]
            return [{'key': 'value', 'label': _('Answer'), 'type': 'text'}]
        return []

    #: A line detail's kind, as the condition checks know field types.
    LINE_TYPES = {'text': 'char', 'number': 'float', 'date': 'date', 'person': 'many2one',
                  'yesno': 'boolean', 'choice': 'char'}

    def _repeat_meta(self, w, d):
        """Condition types of `line.*` and of the counts a repeat leaves."""
        meta = {}
        for n in d.get('nodes') or []:
            if n.get('type') != 'repeat':
                continue
            meta['line.label'] = {'type': 'char'}
            meta['line.number'] = {'type': 'integer'}
            for f in self._line_fields(w.source_model or '', n, d):
                meta['line.%s' % f['key']] = {'type': self.LINE_TYPES.get(f.get('type'), 'char'),
                                              'relation': 'res.users' if f.get('type') == 'person' else None}
            for key in ('count', 'done'):
                meta['step.%s.%s' % (n['id'], key)] = {'type': 'integer'}
            for top in n.get('steps') or []:
                for x in D.descendants(d, top):
                    node = next((m for m in d['nodes'] if m.get('id') == x), {})
                    if node.get('type') == 'task' and len(D.buttons(node)) > 1:
                        for b in D.buttons(node):
                            meta['step.%s.%s__%s' % (n['id'], x, b['key'])] = {'type': 'integer'}
        return meta

    @api.model
    def metadata(self, model='', workflow_id=None):
        result = super().metadata(model, workflow_id)
        result['line_sources'] = {
            'area': [{'key': l['key'], 'label': l.get('label') or l['key'], 'singular': l.get('singular') or '',
                      'fields': [f for f in l.get('fields') or [] if isinstance(f, dict)]}
                     for l in self._area_lines(model)] if model else [],
            'teams': [{'id': r.id, 'name': r.name}
                      for r in self.env['biz.approval.role'].sudo().search([('is_pool', '=', True)])],
            'hard_cap': D.REPEAT_HARD, 'default_cap': D.REPEAT_DEFAULT,
        }
        return result

    @api.model
    def repeat_sample(self, workflow_id, node_id):
        """The inspector's live sample: how many lines a recent record (or
        the team) has, and the first few by name. Read only."""
        w = self._workflow(workflow_id)
        d = w.draft or {}
        n = next((x for x in d.get('nodes') or [] if x.get('id') == node_id and x.get('type') == 'repeat'), None)
        if not n:
            return {'ok': False}
        words = self._repeat_words(w.source_model or '', n, d)
        sample = self._repeat_sample_lines(w, n)
        if sample is None:
            return {'ok': True, 'words': words, 'known': False}
        record, rows = sample
        return {'ok': True, 'words': words, 'known': True, 'record': record, 'count': len(rows),
                'names': [r['label'] for r in rows[:4]],
                'cap': min(int(n.get('max_lines') or D.REPEAT_DEFAULT), D.REPEAT_HARD)}

    def _repeat_sample_lines(self, w, n):
        """(record name, lines) for a recent record of this type that has
        lines (or the team as it is today), or None when there is no way
        to know before it runs (answers given later)."""
        src = n.get('source') if isinstance(n.get('source'), dict) else {}
        if src.get('kind') == 'team':
            role = self.env['biz.approval.role'].sudo().browse(int(src.get('id') or 0)).exists()
            if not role:
                return None
            members = self._team_members(role, w.company_id)
            return role.name, [{'label': m.name} for m in members.sorted('name')]
        if src.get('kind') == 'area' and w.source_model and \
                any(l['key'] == src.get('key') for l in self._area_lines(w.source_model)):
            Model = self.env[w.source_model]
            if not hasattr(Model, '_workflow_lines'):
                return None
            for record in Model.search([('company_id', '=', w.company_id.id)], order='id desc', limit=20):
                rows = record.sudo()._workflow_lines(src['key']) or []
                if rows:
                    return record.display_name, [{'label': r.get('name') or ''} for r in rows]
            return None
        return None

    # ========================================================= validation
    def _new_step_issues(self, w, d, n):
        out = list(super()._new_step_issues(w, d, n))
        model = w.source_model or ''
        parent_map = D.parents(d)
        around = D.repeat_of(d, n['id'], parent_map)
        owner = n.get('owner') or {}
        if owner.get('kind') == 'line' and n['type'] in D.PEOPLE + ('notify',):
            persons = {f['key'] for f in self._line_fields(model, around, d) if f.get('type') == 'person'} \
                if around else set()
            if owner.get('field') not in persons:
                out.append(('line_owner', _('Only a step inside “Repeat for each…” can go to the person on the line, '
                                            'and only when the line names a person.')))
        if n['type'] != 'repeat':
            return out
        src = n.get('source') if isinstance(n.get('source'), dict) else {}
        kind = src.get('kind')
        if kind == 'area':
            spec = next((l for l in self._area_lines(model) if l['key'] == src.get('key')), None) if model else None
            if not spec:
                out.append(('repeat_source', _('%s has no lines a workflow can repeat for. Choose a list question '
                                               'or a team instead.', self._contract(model).get('area') or _('This record type'))
                            if model else _('A new process has no record with lines. Choose a list question or a team.')))
            else:
                known = {f.get('key') for f in spec.get('fields') or []}
                if set(src.get('fields') or []) - known:
                    out.append(('repeat_source', _('Some line details are not offered any more. Choose “%s” again.',
                                                   spec.get('label') or src.get('key'))))
        elif kind == 'answers':
            found = next((a for a in self._answer_sources(d) if a['step'] == src.get('step')
                          and a['field'] == src.get('field')), None)
            order = d.get('order') or []
            if not found or src.get('step') not in order or n['id'] not in order or \
                    order.index(src['step']) >= order.index(n['id']):
                out.append(('repeat_source', _('Repeat for the answers to a list question asked earlier on the main path.')))
        elif kind == 'team':
            role = self.env['biz.approval.role'].sudo().browse(int(src.get('id') or 0)).exists()
            if not role or not role.is_pool:
                out.append(('repeat_source', _('Choose one of the teams from Approvals › Who approves.')))
            elif not self._team_members(role, w.company_id):
                out.append(('team_empty', _('Nobody is on the team “%s” here yet. Add people to it in Approvals › Who approves.',
                                            role.name)))
        return out

    # ============================================================== people
    def _line_person(self, run, owner):
        srun = run.sudo()
        value = (srun.line_values or {}).get(owner.get('field')) if srun.parent_id else None
        person = self.env['res.users'].sudo().browse(value if type(value) is int else 0).exists()
        if not person:
            raise UserError(_('This line does not name a person. Edit the step.'))
        return person

    def _resolve_owner(self, run, owner):
        if (owner or {}).get('kind') == 'line':
            return self._line_person(run, owner).id
        return super()._resolve_owner(run, owner)

    def _resolve_people(self, run, owner):
        owner = owner or {}
        if owner.get('kind') != 'line':
            return super()._resolve_people(run, owner)
        person = self._line_person(run, owner)
        if person.active and not person.share:
            return {'mode': 'staff', 'uid': person.id}
        home = self._home_login(person, run.company_id)
        if home:
            return {'mode': 'home', 'uid': home[0].id, 'employee': home[1]}
        raise UserError(_('%s cannot sign in at the moment, so this cannot be given to them.', person.name))

    def _owner_words(self, model, owner):
        if (owner or {}).get('kind') == 'line':
            return _('The person on the line')
        return super()._owner_words(model, owner)

    def _line_words(self, run):
        """“receipt 2 of 5” for a line run, '' for any other run."""
        srun = run.sudo()
        if not srun.parent_id:
            return ''
        node = next((x for x in srun.version_id.definition.get('nodes', []) if x.get('id') == srun.parent_step_key), {})
        words = self._repeat_words(srun.source_model or '', node, srun.version_id.definition)
        return _('%(what)s %(n)s of %(count)s', what=words['singular'], n=srun.line_number, count=srun.line_count)

    def _task_card(self, step, mine=True):
        card = super()._task_card(step, mine)
        run = step.sudo().run_id
        if not run.parent_id:
            return card
        words = self._line_words(run)
        card.update(title='%s · %s' % (card['title'], run.line_label) if run.line_label else card['title'],
                    line={'label': run.line_label or '', 'number': run.line_number, 'count': run.line_count,
                          'words': words},
                    group={'key': 'rep-%s-%s-%s' % (run.parent_id.id, run.parent_step_key, step.key),
                           'title': step.name, 'count': run.line_count})
        return card

    @api.model
    def task_detail(self, task_id):
        result = super().task_detail(task_id)
        run = self.env['pb.workflow.step'].sudo().browse(int(task_id)).run_id
        if run.parent_id:
            result['line'] = {'label': run.line_label or '', 'number': run.line_number,
                              'count': run.line_count, 'words': self._line_words(run)}
        return result

    def _page_data(self, step, unsupported):
        data = super()._page_data(step, unsupported)
        run = step.sudo().run_id
        if run.parent_id:
            if run.line_label:
                data['name'] = '%s · %s' % (data['name'], run.line_label)
            words = self._line_words(run)
            data['record'] = ' · '.join(x for x in (data.get('record'), words) if x)
            data['line'] = {'label': run.line_label or '', 'words': words}
        return data

    @api.model
    def tasks(self, run_id=None):
        rows = super().tasks(run_id=run_id)
        steps = {s.id: s for s in self.env['pb.workflow.step'].sudo().browse([r['id'] for r in rows])}
        for row in rows:
            run = steps[row['id']].run_id if row['id'] in steps else None
            if run and run.parent_id:
                row['line'] = {'label': run.line_label or '', 'words': self._line_words(run)}
                if run.line_label:
                    row['name'] = '%s · %s' % (row['name'], run.line_label)
        return rows

    # ============================================================ progress
    def _line_row(self, line):
        """One line on the progress page: state, who, answer."""
        sline = line.sudo()
        steps = sline.step_ids.sorted(lambda s: (s.position, s.id))
        waiting = steps.filtered(lambda s: s.state == 'waiting')
        failed = steps.filtered(lambda s: s.state == 'failed')
        answered = steps.filtered(lambda s: s.state == 'done' and (s.answers or {}).get('outcome_label'))
        person = (waiting[:1].assignee_id or steps.filtered(lambda s: s.assignee_id)[-1:].assignee_id)
        return {'run_id': line.id, 'number': sline.line_number, 'label': sline.line_label or '',
                'state': sline.state, 'who': person.name or '',
                'answer': (answered[-1:].answers or {}).get('outcome_label') or '',
                'failed_step_id': failed[:1].id or None,
                'reason': (failed[:1].error or '') if self._can_design() else ''}

    @api.model
    def progress(self, run_id):
        result = super().progress(run_id)
        run = self._run(run_id).sudo()
        d = run.version_id.definition
        for node in result.get('graph', {}).get('nodes', []):
            if node.get('type') == 'repeat':
                full = next((n for n in d.get('nodes', []) if n.get('id') == node['id']), {})
                words = self._repeat_words(run.source_model or '', full, d)
                node.update(each=words['each'], singular=words['singular'], plural=words['plural'],
                            mode=full.get('mode', 'together'), join=full.get('join', 'all'))
        if not run.line_ids:
            return result
        nodes = {n['id']: n for n in d.get('nodes', [])}
        rows = {r['key']: r for r in result['steps']}
        for step in run.step_ids.filtered(lambda s: s.kind == 'repeat'):
            row = rows.get(step.key)
            n = nodes.get(step.key) or {}
            state = json.loads(step.choice) if str(step.choice or '').startswith('{') else {}
            lines = run._repeat_lines_of(step).filtered(lambda r: not state.get('round') or r.line_round == state['round'])
            if not row or not lines:
                continue
            words = self._repeat_words(run.source_model or '', n, d)
            done = len(lines.filtered(lambda r: r.state == 'done'))
            total = int(state.get('count') or len(lines))
            row['lines'] = [self._line_row(x) for x in lines]
            row['line_words'] = words
            row['reason'] = row.get('reason') or _('%(done)s of %(count)s %(lines)s done',
                                                    done=done, count=total, lines=words['plural'])
            row['line_done'], row['line_total'] = done, total
            # The steps inside the repeat, summed over the lines, so the
            # canvas shows where the lines are.
            for key in [k for top in n.get('steps') or [] for k in D.descendants(d, top)]:
                states = [s.state for x in lines for s in x.sudo().step_ids if s.key == key]
                if not states:
                    continue
                agg = ('failed' if 'failed' in states else 'waiting' if 'waiting' in states
                       else 'active' if 'active' in states else 'done' if all(x in ('done', 'skipped') for x in states)
                       and 'done' in states else 'skipped' if all(x == 'skipped' for x in states) else 'pending')
                finished = sum(1 for x in states if x in ('done', 'skipped'))
                waiting_for = sorted({s.assignee_id.name for x in lines for s in x.sudo().step_ids
                                      if s.key == key and s.state == 'waiting' and s.assignee_id})
                who = ', '.join(waiting_for[:2]) + (' +%s' % (len(waiting_for) - 2) if len(waiting_for) > 2 else '')
                result['steps'].append({'id': None, 'key': key, 'state': agg, 'line_total': total,
                                        'owner': who,
                                        'reason': _('%(done)s of %(count)s %(lines)s', done=finished, count=total,
                                                    lines=words['plural']),
                                        'started': '', 'finished': '', 'due': '', 'wake_at': '',
                                        'approval': None})
        return result

    @api.model
    def run_action(self, run_id, action, step_id=None):
        if action == 'retry' and step_id:
            run = self._run(run_id).sudo()
            step = run.step_ids.filtered(lambda s: s.id == int(step_id or 0))
            if step.kind == 'repeat' and step.state == 'failed':
                # Retry on the repeat = retry every line that needs attention.
                self._design()
                state = json.loads(step.choice) if str(step.choice or '').startswith('{') else {}
                for line in run._repeat_lines_of(step).filtered(
                        lambda r: r.state == 'failed' and (not state.get('round') or r.line_round == state['round'])):
                    super().run_action(line.id, 'retry', line.step_ids.filtered(lambda s: s.state == 'failed')[:1].id)
                run._advance()
                run._log(_('Retry by %s.', self.env.user.name))
                return self.run_detail(run.id)
        result = super().run_action(run_id, action, step_id)
        run = self.env['pb.workflow.run'].sudo().browse(int(run_id))
        if action in ('hold', 'resume', 'cancel') and run.line_ids:
            lines = run.line_ids.filtered(lambda r: r.state in OPEN)
            if action == 'cancel':
                run._repeat_close_lines(lines, _('Stopped: the workflow it belongs to was cancelled.'))
            for line in lines.filtered(lambda r: r.state in OPEN):
                if action == 'hold' and line.state != 'held':
                    internal(line).write({'state': 'held'})
                elif action == 'resume' and line.state == 'held':
                    internal(line).write({'state': 'waiting'})
                    line.with_context(_pb_wf_from_parent=True)._advance()
            if action == 'resume' and run.state in ('running', 'waiting', 'failed'):
                run._advance()
                result = self.run_detail(run.id)
        return result

    @api.model
    def runs(self, workflow_id=None, show_lines=False):
        rows = super().runs(workflow_id, show_lines=show_lines)
        if not show_lines:
            return rows
        lines = {r.id: r for r in self.env['pb.workflow.run'].sudo().browse([row['id'] for row in rows]) if r.parent_id}
        for row in rows:
            line = lines.get(row['id'])
            if line:
                row.update(line=True, parent_id=line.parent_id.id,
                           name='%s · %s' % (row['name'], line.line_label or self._line_words(line)),
                           line_words=self._line_words(line))
        return rows

    # =============================================================== strip
    def _strip_row(self, run, viewer, full, home=False):
        row = super()._strip_row(run, viewer, full, home)
        srun = run.sudo()
        if not srun.line_ids or srun.state not in ('running', 'waiting', 'failed'):
            return row
        step = srun.step_ids.filtered(lambda s: s.kind == 'repeat' and s.state in ('active', 'failed'))[:1]
        if not step or row.get('task_id'):
            return row
        n = step.config or {}
        state = json.loads(step.choice) if str(step.choice or '').startswith('{') else {}
        lines = srun._repeat_lines_of(step).filtered(lambda r: not state.get('round') or r.line_round == state['round'])
        words = self._repeat_words(srun.source_model or '', n, srun.version_id.definition)
        total = int(state.get('count') or len(lines))
        done = len(lines.filtered(lambda r: r.state == 'done'))
        row['sentence'] = _('%(done)s of %(count)s %(lines)s done', done=done, count=total, lines=words['plural'])
        row['tone'] = 'late' if step.state == 'failed' else 'wait'
        theirs = self.env['pb.workflow.step'].sudo().search([
            ('run_id', 'in', lines.ids), ('state', '=', 'waiting'), ('kind', 'in', list(D.PEOPLE)),
            '|', ('assignee_id', '=', viewer.id), '&', ('assignee_id', '=', False), ('team_user_ids', 'in', [viewer.id])],
            order='id', limit=1)
        waiting = self.env['pb.workflow.step'].sudo().search([
            ('run_id', 'in', lines.ids), ('state', '=', 'waiting'), ('kind', 'in', list(D.PEOPLE))], order='id')
        names = sorted({s.assignee_id.name or s.link_name or self._team_role(s).name or '' for s in waiting} - {''})
        # Who the lines wait for: the strip then says more than the page's
        # own "With X" box (D23) and the employee home shows it.
        row['who'] = ', '.join(names[:2]) + (' +%s' % (len(names) - 2) if len(names) > 2 else '')
        if theirs:
            row.update(task_id=theirs.id, tone='mine', who=_('you'),
                       task_name='%s · %s' % (theirs.name, theirs.run_id.line_label),
                       sentence=_('%(done)s of %(count)s %(lines)s done · next for you: %(what)s',
                                  done=done, count=total, lines=words['plural'],
                                  what='%s · %s' % (theirs.name, theirs.run_id.line_label)))
        return row

    # ===================================================== where time goes
    def _report_steps(self, w, runs, now):
        out = super()._report_steps(w, runs, now)
        Step = self.env['pb.workflow.step'].sudo()
        reps = Step.search([('run_id', 'in', runs.ids), ('kind', '=', 'repeat')])
        if not reps:
            return out
        clock, per_day, _calendar = self._work_clock(w.company_id, min(
            [s.started_at for s in reps if s.started_at] or [now - timedelta(days=1)]), now)
        draft = {n['id']: n for n in (w.draft or {}).get('nodes', [])}
        by_key = {}
        for s in reps:
            by_key.setdefault(s.key, []).append(s)
        rows = []
        for key, steps in by_key.items():
            whole = [clock(s.started_at, s.done_at) for s in steps if s.state == 'done' and s.started_at and s.done_at]
            lines = self.env['pb.workflow.run'].sudo().search([('parent_id', 'in', [s.run_id.id for s in steps]),
                                                               ('parent_step_key', '=', key)])
            each = [clock(r.create_date, r.ended_at) for r in lines if r.state == 'done' and r.ended_at]
            waiting = len(lines.filtered(lambda r: r.state in ('running', 'waiting', 'failed')))
            enough = len(whole) >= 3
            n = draft.get(key) or steps[-1].config or {}
            words = self._repeat_words(w.source_model or '', n, w.draft)
            rows.append({'key': key, 'title': (draft.get(key) or {}).get('title') or steps[-1].name,
                         'kind': 'repeat', 'approval': False, 'who': '', 'samples': len(whole), 'enough': enough,
                         'median_words': self._duration_words(statistics.median(whole), per_day) if enough else '',
                         'line_words': _('Each %(one)s usually %(time)s', one=words['singular'],
                                         time=self._duration_words(statistics.median(each), per_day))
                         if len(each) >= 3 else '',
                         'late': 0, 'late_share': None, 'sent_back': 0, 'reminders': 0, 'passed_up': 0,
                         'waiting': waiting, 'exists': key in draft})
        return (out + rows)[:6]

    # ====================================================== Try it out
    def _would(self, w):
        describe = super()._would(w)
        model = w.source_model or ''
        d = w.draft or {}

        def wrapped(n):
            if n.get('type') == 'repeat':
                words = self._repeat_words(model, n, d)
                how = _('together') if n.get('mode', 'together') == 'together' else _('one by one')
                return _('%(each)s, %(how)s', each=words['each'], how=how)
            return describe(n)

        def sample(n):
            words = self._repeat_words(model, n, d)
            try:
                found = self._repeat_sample_lines(w, n)
            except (AccessError, UserError):
                found = None
            rows = found[1] if found else []
            first = rows[0]['label'] if rows else ''
            more = len(rows) - 1
            return {'label': first,
                    'path': (_('%(each)s · shown for %(first)s', each=words['each'], first=first) if first
                             else _('%s · shown for one', words['each'])),
                    'after': (_('…and the same for %(n)s more %(lines)s', n=more,
                                lines=words['plural'] if more != 1 else words['singular']) if more > 0 else
                              _('…and the same for each other %s', words['singular']) if not rows else
                              _('That is the only %s.', words['singular'])),
                    'values': {}}
        wrapped.repeat_sample = sample
        return wrapped


class WorkflowInboxLines(models.AbstractModel):
    """The inbox groups one person's line tasks of one repeat; beyond five
    they become one card that is worked through with "Do all in turn"."""
    _inherit = 'pb.approval.inbox'

    @api.model
    def _extra_items(self, scope='me', search=None):
        items = list(super()._extra_items(scope, search) or [])
        groups = {}
        for card in items:
            if card.get('source') == 'workflow' and card.get('group'):
                groups.setdefault(card['group']['key'], []).append(card)
        if not groups:
            return items
        out, placed = [], set()
        for card in items:
            key = (card.get('group') or {}).get('key') if card.get('source') == 'workflow' else None
            if not key:
                out.append(card)
                continue
            if key in placed:
                continue
            placed.add(key)
            members = sorted(groups[key], key=lambda c: (c['line']['number'], c['id']))
            for c in members:
                c['group'] = dict(c['group'], size=len(members), ids=[m['id'] for m in members])
            if len(members) > GROUP_CARDS and scope == 'me':
                first = dict(members[0])
                first.update(kind='task_group', group_count=len(members),
                             title=_('%(what)s · %(n)s to do', what=members[0]['group']['title'], n=len(members)),
                             late=any(m['late'] for m in members))
                out.append(first)
            else:
                out.extend(members)
        return out
