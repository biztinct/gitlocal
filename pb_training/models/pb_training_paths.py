# -*- coding: utf-8 -*-
"""Learning › PATHS — the board, the path page and the drawers (LEARNING L3).

One read per screen, behind the board's gate (`{'allowed': False}` without a
training group, never an AccessError):

  * `paths_board()`            every path as a card with its station line;
  * `path_page(path_id, f)`    one path: the big station line, the people on
                               it with a dot rail each, filters;
  * `path_lists()`             the drawers' own lists (courses, departments,
                               jobs, reasons).

WHO MAY DO WHAT (the Required precedent): a trainer reads every path and puts
people on and off a path (that is the trainer's job); only a training manager
or the head of training creates, edits or archives a path.

Verb names carry `path` because `pb.training.enrol` / `unenrol` already exist
(they put people on a COURSE) — a deviation from the handover's `enrol` /
`unenrol`, noted in the report.

Also here: the Overview's "Paths" block and queue chip, and My learning's
"My path" read (`pb.my.training.home()['paths']`).
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .path import ENROL_OPEN, ENROL_STATE_LABEL, PATH_PURPOSES
from .pb_training_required import PbTrainingRequired
from .training_common import (
    P_BULK_CAP, as_id, due_words, duration_words, fold, minutes, number,
    reason_choices, tr,
)

_logger = logging.getLogger(__name__)

#: People per path page.
PAGE_CAP = 200

#: Problem first on the path page.
_STATE_RANK = {'overdue': 0, 'not_started': 1, 'in_progress': 2, 'done': 3}

#: The reasons a person is put on a path from the board.
PATH_REASONS = ('adhoc', 'day_one', 'probation', 'leadership', 'compliance')


class PbTrainingPaths(models.AbstractModel):
    _inherit = 'pb.training'

    _VERBS = PbTrainingRequired._VERBS + (
        'save_path', 'archive_path', 'enrol_path', 'unenrol_path',
    )

    # =====================================================================
    #  reading
    # =====================================================================
    @api.model
    def _live_paths(self, active=True):
        domain = [('company_id', 'in', self.env.companies.ids)]
        if active is not None:
            domain.append(('active', '=', active))
        return self.env['pb.training.path'].sudo().with_context(
            active_test=False).search(domain)

    @api.model
    def _path(self, path_id):
        path = self.env['pb.training.path'].sudo().with_context(
            active_test=False).browse(as_id(path_id)).exists()
        if not path or path.company_id.id not in self.env.companies.ids:
            raise UserError(_("That path is not here any more."))
        return path

    @api.model
    def _people_words(self, n):
        return _("1 person") if n == 1 else _("%s people", n)

    @api.model
    def _path_steps(self, path):
        out = []
        for step in path._ordered_steps():
            channel = step.channel_id.sudo()
            out.append({
                'id': step.id,
                'channel_id': channel.id,
                'name': channel.name or '',
                'gate': bool(step.gate),
                'due_days': step.due_days or 0,
                'hours': step.hours or 0.0,
                'hours_words': duration_words(minutes(step.hours), self.env),
                'published': bool(channel.is_published and channel.active),
            })
        return out

    @api.model
    def _qsteps(self, path, enrolments, picked=''):
        """The station line in the QuietSteps contract (pb_import_kit)."""
        out = []
        stations = path._stations(enrolments)
        for st in stations:
            done = st['key'] == 'done'
            out.append({
                'key': st['key'],
                'step_id': st['step_id'],
                'n': st['n'],
                'title': _("Finished") if done else st['title'],
                'count': st['count'],
                'countLabel': self._people_words(st['count']),
                'sub': _("Later steps wait for this one") if st['gate']
                else (_("Every step done") if done else ''),
                'flag': '' if not st['late'] else (
                    _("1 late") if st['late'] == 1
                    else _("%s late", st['late'])),
                'flagTone': 'rose',
                'gate': st['gate'],
                'on': picked == st['key'],
            })
        return out

    @api.model
    def _path_card(self, path, picked=''):
        enrol = path.enrolment_ids.sudo().filtered(
            lambda e: e.state != 'cancelled')
        steps = self._path_steps(path)
        people = len(enrol)
        done = len(enrol.filtered(lambda e: e.state == 'done'))
        late = len(enrol.filtered(lambda e: e.state == 'overdue'))
        return {
            'id': path.id,
            'name': path.name or '',
            'purpose': path.purpose,
            'purpose_word': path._purpose_word(),
            'blurb': path.blurb or '',
            'active': bool(path.active),
            'steps': steps,
            'stations': self._qsteps(path, enrol, picked),
            'people': people,
            'done': done,
            'overdue': late,
            'people_words': _("%(n)s on it · %(done)s finished",
                              n=self._people_words(people), done=done),
            'day_one': bool(path.day_one),
            'audience_words': path._audience_words(),
            'unpublished': len([s for s in steps if not s['published']]),
            'hours_words': duration_words(
                minutes(sum(s['hours'] for s in steps)), self.env),
            'values': {
                'id': path.id,
                'name': path.name or '',
                'purpose': path.purpose,
                'blurb': path.blurb or '',
                'due_days': path.due_days,
                'counts_for_probation': bool(path.counts_for_probation),
                'day_one': bool(path.day_one),
                'department_ids': path.department_ids.ids,
                'job_ids': path.job_ids.ids,
                'steps': [{'channel_id': s['channel_id'], 'gate': s['gate'],
                           'due_days': s['due_days']} for s in steps],
            },
        }

    @api.model
    def _paths_headline(self, k):
        """"3 paths · 24 people on a path · 2 late" — whole pieces."""
        if not k['paths']:
            return _("No paths yet.")
        bits = [_("1 path") if k['paths'] == 1 else _("%s paths", k['paths'])]
        if k['people'] == 1:
            bits.append(_("1 person on a path"))
        else:
            bits.append(_("%s people on a path", k['people']))
        if k['late']:
            bits.append(_("1 late") if k['late'] == 1
                        else _("%s late", k['late']))
        if k['done']:
            bits.append(_("%s finished", k['done']))
        return ' · '.join(bits)

    @api.model
    def paths_board(self):
        if not self._can_read():
            return {'allowed': False, 'paths': []}
        paths = self._live_paths()
        cards = [self._path_card(p) for p in paths]
        cards.sort(key=lambda c: (-c['overdue'], fold(c['name'])))
        kpis = {
            'paths': len(cards),
            'people': sum(c['people'] - c['done'] for c in cards),
            'late': sum(c['overdue'] for c in cards),
            'done': sum(c['done'] for c in cards),
        }
        archived = [{'id': p.id, 'name': p.name or ''}
                    for p in self._live_paths(active=False)]
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'can_manage': self._can_manage(),
            'paths': cards,
            'archived': archived,
            'kpis': kpis,
            'headline': self._paths_headline(kpis),
        }

    @api.model
    def path_page(self, path_id, filters=None):
        if not self._can_read():
            return {'allowed': False}
        filters = filters or {}
        path = self._path(path_id)
        today = fields.Date.today()
        enrol = path.enrolment_ids.sudo().filtered(
            lambda e: e.state != 'cancelled')
        # The states are READ, so they are brought up to date first.
        enrol.filtered(lambda e: e.state in ENROL_OPEN)._refresh(today)
        station = filters.get('step') or ''
        card = self._path_card(path, picked=station)
        state = filters.get('state') or ''
        needle = fold(filters.get('q') or '')
        facts = {}
        if enrol:
            for row in enrol.mapped('employee_id').sudo().read(
                    ['name', 'department_id', 'job_id', 'job_title']):
                facts[row['id']] = row
        counts = {k: 0 for k in _STATE_RANK}
        rows = []
        for enr in enrol:
            f = facts.get(enr.employee_id.id, {})
            name = f.get('name') or ''
            if needle and needle not in fold(name):
                continue
            counts[enr.state] = counts.get(enr.state, 0) + 1
            if state and enr.state != state:
                continue
            at = 'done' if enr.state == 'done' else str(
                enr.current_step_id.id or '')
            if station and at != station:
                continue
            # WHAT THEY MUST HIT NEXT: the current step's own date (found in
            # the local walk — a row said "Late" over the whole path's "60
            # days left" because the course they are on was overdue).
            step_row = enr._step_rows().get(enr.current_step_id.id) \
                if enr.state != 'done' and enr.current_step_id else None
            next_due = step_row.due_date if step_row else enr.due_date
            rows.append({
                'enrolment_id': enr.id,
                'employee_id': enr.employee_id.id,
                'employee': name,
                'department': f.get('department_id') and
                f['department_id'][1] or '',
                'job': (f.get('job_id') and f['job_id'][1]) or
                f.get('job_title') or '',
                'state': enr.state,
                'state_words': tr(self.env, ENROL_STATE_LABEL.get(
                    enr.state, '')),
                'where_words': enr._where_words(),
                'percent': enr.percent,
                'current_step_id': enr.current_step_id.id or 0,
                'due': fields.Date.to_string(next_due) or '',
                'due_words': due_words(next_due, today, self.env)
                if enr.state != 'done' else '',
                'path_due_words': _("Whole path: %s", due_words(
                    enr.due_date, today, self.env))
                if enr.state != 'done' and enr.due_date else '',
                'late': enr.state == 'overdue',
                'reason_word': tr(self.env, dict(
                    enr._fields['reason'].selection).get(enr.reason, '')),
                'rail': [{'state': s['state'], 'name': s['name']}
                         for s in enr._learner_steps()],
            })
        rows.sort(key=lambda r: (_STATE_RANK.get(r['state'], 9),
                                 fold(r['employee'])))
        total = len(rows)
        return dict(card, **{
            'allowed': True,
            'can_write': self._can_write(),
            'can_manage': self._can_manage(),
            'rows': rows[:PAGE_CAP],
            'total': total,
            'truncated': total > PAGE_CAP,
            'counts': counts,
        })

    @api.model
    def path_lists(self):
        if not self._can_read():
            return {'allowed': False}
        comps = self.env.companies.ids
        courses = self.env['slide.channel'].sudo().search(
            [('active', '=', True)],
            limit=number(self.env, 'pb_training.course_limit', 200))
        return {
            'allowed': True,
            'courses': sorted([{
                'id': c.id, 'name': c.name or '',
                'published': bool(c.is_published),
                'hours_words': duration_words(minutes(c._pb_hours()),
                                              self.env),
            } for c in courses], key=lambda r: fold(r['name'])),
            'departments': sorted(
                [{'id': d['id'], 'name': d['complete_name'] or d['name']}
                 for d in self.env['hr.department'].sudo().search_read(
                     [('company_id', 'in', comps)],
                     ['name', 'complete_name'])],
                key=lambda r: fold(r['name'])),
            'jobs': sorted([{'id': j['id'], 'name': j['name']}
                            for j in self.env['hr.job'].sudo().search_read(
                                [('company_id', 'in', comps)], ['name'])],
                           key=lambda r: fold(r['name'])),
            'purposes': [{'key': k, 'label': tr(self.env, v)}
                         for k, v in PATH_PURPOSES],
            'reasons': [r for r in reason_choices(self.env)
                        if r['key'] in PATH_REASONS],
        }

    # =====================================================================
    #  writing a path (managers)
    # =====================================================================
    @api.model
    def save_path(self, payload=None):
        self._require_manager()
        payload = payload or {}
        name = (payload.get('name') or '').strip()
        if not name:
            raise UserError(_("Give the path a name people will recognise."))
        purpose = payload.get('purpose') or 'role'
        if purpose not in dict(PATH_PURPOSES):
            purpose = 'role'
        steps_in = payload.get('steps') or []
        Channel = self.env['slide.channel'].sudo()
        steps, seen = [], set()
        for raw in steps_in:
            cid = as_id((raw or {}).get('channel_id'))
            if not cid:
                continue
            if cid in seen:
                raise UserError(_("A course can be on a path only once."))
            if not Channel.browse(cid).exists():
                raise UserError(_("One of those courses is not here any "
                                  "more."))
            seen.add(cid)
            try:
                due = max(int(raw.get('due_days') or 0), 0)
            except (TypeError, ValueError):
                due = 0
            steps.append({'channel_id': cid, 'gate': bool(raw.get('gate')),
                          'due_days': due})
        if not steps:
            raise UserError(_("Add at least one course."))
        try:
            due_days = max(int(payload.get('due_days') or 90), 1)
        except (TypeError, ValueError):
            due_days = 90

        def ids(key, model):
            wanted = [as_id(v) for v in (payload.get(key) or []) if as_id(v)]
            return [(6, 0, self.env[model].sudo().browse(wanted).exists().ids)]

        vals = {
            'name': name[:200],
            'purpose': purpose,
            'blurb': (payload.get('blurb') or '').strip()[:400],
            'due_days': due_days,
            'counts_for_probation': bool(payload.get('counts_for_probation')),
            'day_one': bool(payload.get('day_one')),
            'department_ids': ids('department_ids', 'hr.department'),
            'job_ids': ids('job_ids', 'hr.job'),
        }
        path_id = as_id(payload.get('id'))
        Step = self.env['pb.training.path.step'].sudo()
        if path_id:
            path = self._path(path_id)
            path.write(vals)
            existing = {s.channel_id.id: s for s in path.step_ids}
            keep = set()
            for i, step in enumerate(steps):
                seq = (i + 1) * 10
                row = existing.get(step['channel_id'])
                if row:
                    row.write({'sequence': seq, 'gate': step['gate'],
                               'due_days': step['due_days']})
                    keep.add(row.id)
                else:
                    keep.add(Step.create(dict(step, path_id=path.id,
                                              sequence=seq)).id)
            path.step_ids.filtered(lambda s: s.id not in keep).unlink()
            # A step added to a running path opens for the people on it.
            path.enrolment_ids.filtered(
                lambda e: e.state in ENROL_OPEN)._refresh()
            message = _("%s is saved.", path.name)
        else:
            vals['company_id'] = self.env.company.id
            vals['step_ids'] = [(0, 0, dict(step, sequence=(i + 1) * 10))
                                for i, step in enumerate(steps)]
            path = self.env['pb.training.path'].sudo().create(vals)
            message = _("%s is ready. Put people on it with Enrol people.",
                        path.name)
        return {'id': path.id, 'message': message}

    @api.model
    def archive_path(self, path_id):
        self._require_manager()
        path = self._path(path_id)
        path.active = not path.active
        if path.active:
            return {'message': _("%s is back on the board.", path.name)}
        return {'message': _("%s is archived. Nobody new can be put on it; "
                             "the people already on it carry on.", path.name)}

    # =====================================================================
    #  people on and off a path (trainers)
    # =====================================================================
    @api.model
    def _path_audience(self, payload):
        """The employee ids an Enrol press is about: picked people, or a
        department (with everything under it), a job, or everybody."""
        Employee = self.env['hr.employee'].sudo()
        base = [('active', '=', True),
                ('company_id', 'in', self.env.companies.ids)]
        if payload.get('everyone'):
            return Employee.search(base).ids
        if as_id(payload.get('department_id')):
            return Employee.search(base + [(
                'department_id', 'child_of',
                as_id(payload['department_id']))]).ids
        if as_id(payload.get('job_id')):
            return Employee.search(base + [(
                'job_id', '=', as_id(payload['job_id']))]).ids
        return [as_id(e) for e in (payload.get('employee_ids') or [])
                if as_id(e)]

    @api.model
    def enrol_path(self, payload=None):
        self._require_write()
        payload = payload or {}
        path = self._path(payload.get('path_id'))
        if not path.active:
            raise UserError(_("%s is archived. Bring it back before putting "
                              "people on it.", path.name))
        ids = self._path_audience(payload)
        if not ids:
            raise UserError(_("Pick at least one person."))
        cap = number(self.env, P_BULK_CAP, 200)
        if len(ids) > cap:
            raise UserError(_(
                "That is %(n)s people at once. The most this screen will do "
                "in one press is %(cap)s — pick a smaller group.",
                n=len(ids), cap=cap))
        reason = payload.get('reason') or 'adhoc'
        if reason not in PATH_REASONS:
            reason = 'adhoc'
        res = self.env['pb.training.path.enrolment'].enrol_many(
            path.id, ids, reason, payload.get('due_date') or None)
        res['type'] = 'success' if res.get('made') else 'warning'
        return res

    @api.model
    def unenrol_path(self, enrolment_id):
        self._require_write()
        enr = self.env['pb.training.path.enrolment'].sudo().browse(
            as_id(enrolment_id)).exists()
        if not enr or enr.company_id.id not in self.env.companies.ids:
            raise UserError(_("That person is not on the path any more."))
        if enr.state == 'cancelled':
            raise UserError(_("%s is already off the path.",
                              enr.employee_id.name))
        res = enr.unenrol()
        who = enr.employee_id.name or ''
        bits = [_("%(who)s is off %(path)s.", who=who, path=enr.path_id.name)]
        if res['removed']:
            bits.append(_("1 course they had not started is taken off their "
                          "list.") if res['removed'] == 1 else
                        _("%s courses they had not started are taken off "
                          "their list.", res['removed']))
        if res['kept']:
            bits.append(_("1 course they had started stays on their list.")
                        if res['kept'] == 1 else
                        _("%s courses they had started stay on their list.",
                          res['kept']))
        return dict(res, message=' '.join(bits))

    # =====================================================================
    #  the Overview's block
    # =====================================================================
    @api.model
    def _paths_overview(self):
        paths = self._live_paths()
        if not paths:
            return {'has_paths': False, 'paths': 0, 'people': 0,
                    'done_quarter': 0, 'late': 0}
        today = fields.Date.today()
        quarter = today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1)
        Enrol = self.env['pb.training.path.enrolment'].sudo()
        base = [('path_id', 'in', paths.ids)]
        open_rows = Enrol.search(base + [('state', 'in', ENROL_OPEN)])
        return {
            'has_paths': True,
            'paths': len(paths),
            'people': len(open_rows.mapped('employee_id')),
            'late': len(open_rows.filtered(lambda e: e.state == 'overdue')),
            'done_quarter': Enrol.search_count(
                base + [('state', '=', 'done'),
                        ('completed_on', '>=', quarter)]),
        }

    @api.model
    def overview(self):
        data = super().overview()
        if not data.get('allowed'):
            return data
        block = self._safe(self._paths_overview, default={'has_paths': False})
        data['paths'] = block
        if block.get('has_paths'):
            late = block.get('late', 0)
            if late:
                fragment = _("1 person is late on a path.") if late == 1 \
                    else _("%s people are late on a path.", late)
                data['headline'] = '%s %s' % (data.get('headline', ''),
                                              fragment)
                data['calm'] = False
            data['queue'] = data.get('queue', []) + [{
                'key': 'paths', 'label': _("Late on a path"),
                'count': late, 'lens': 'paths', 'tab': '',
                'path_state': 'overdue',
            }]
        return data

    # =====================================================================
    #  the dispatcher
    # =====================================================================
    @api.model
    def act(self, verb, payload=None):
        payload = payload or {}
        if verb == 'save_path':
            return self.save_path(payload)
        if verb == 'archive_path':
            return self.archive_path(payload.get('path_id'))
        if verb == 'enrol_path':
            return self.enrol_path(payload)
        if verb == 'unenrol_path':
            return self.unenrol_path(payload.get('enrolment_id'))
        return super().act(verb, payload)


class PbMyTrainingPaths(models.AbstractModel):
    """"My path" on My learning and the portal."""
    _inherit = 'pb.my.training'

    @api.model
    def _my_paths(self):
        emp = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        if not emp:
            return []
        today = fields.Date.today()
        recent = today - timedelta(days=30)
        rows = self.env['pb.training.path.enrolment'].sudo().search(
            [('employee_id', '=', emp.id),
             '|', ('state', 'in', ENROL_OPEN),
             '&', ('state', '=', 'done'), ('completed_on', '>=', recent)])
        rows.filtered(lambda e: e.state in ENROL_OPEN)._refresh(today)
        out = []
        for enr in rows:
            steps = enr._learner_steps()
            now = next((s for s in steps if s['state'] == 'now'), None)
            path = enr.path_id.sudo()
            out.append({
                'enrolment_id': enr.id,
                'path_id': path.id,
                'name': path.name or '',
                'blurb': path.blurb or '',
                'purpose_word': path._purpose_word(),
                'percent': enr.percent,
                'state': enr.state,
                'state_words': tr(self.env, ENROL_STATE_LABEL.get(
                    enr.state, '')),
                'where_words': enr._where_words(),
                'steps': steps,
                'done': len([s for s in steps if s['state'] == 'done']),
                'total': len(steps),
                'due': fields.Date.to_string(enr.due_date) or '',
                'late': enr.state == 'overdue',
                'next': {'channel_id': now['channel_id'], 'name': now['name']}
                if now and now['channel_id'] else None,
            })
        rank = {'overdue': 0, 'in_progress': 1, 'not_started': 2, 'done': 3}
        out.sort(key=lambda r: (rank.get(r['state'], 9), fold(r['name'])))
        return out

    @api.model
    def home(self):
        data = super().home()
        try:
            data['paths'] = self._my_paths()
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: my learning paths could not be '
                            'read', exc_info=True)
            data['paths'] = []
        return data
