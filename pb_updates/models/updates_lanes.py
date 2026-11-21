# -*- coding: utf-8 -*-
"""UPDATES P3a (D3) — one file, three lanes.

The desk (`pb_records`) does the splitting and the rules; this file is what
the Updates screen needs around them:

  * `lane_outlook` — before anything is sent, what each lane of THIS file
    will do, in plain words, with the real people's names: personal details
    change now (or follow the company's own route), pay and contract go to
    <who> for approval (or change now under "No approval needed"), bank
    details need a second person (<names>), or nobody else can approve them
    yet;
  * the company switch "Personal details from a sheet apply without
    approval" (on by default), shown on the Updates home to whoever looks
    after approvals;
  * a named update's lanes as separate lines in Past updates, each with its
    own state, Cancel and Undo (`undo(apply_id=...)`).

Loaded after `updates_desk` (models/__init__.py); constants come FROM that
file, never the other way round (ledger G21).
"""
import json

from odoo import _, api, fields, models

from odoo.addons.pb_records.models.records_approval import (
    RECORDS_BANK_PROCESS_KEY, RECORDS_PROCESS_KEY, lane_of, route_kind)

LANE_ICONS = {'details': 'userRound', 'pay': 'banknote', 'bank': 'landmark'}
_CONFIG_GROUPS = ('biz_approval_workflow.group_approval_config',
                  'base.group_system')


class PbUpdatesLanes(models.AbstractModel):
    _inherit = 'pb.updates.desk'

    @api.model
    def _lane_label(self, lane):
        return {
            'details': _("Personal details"),
            'pay': _("Pay and contract"),
            'bank': _("Bank details"),
        }.get(lane or '', '')

    @api.model
    def _names_line(self, names, limit=3):
        names = [n for n in names if n]
        if len(names) <= limit:
            return ', '.join(names)
        return _("%(names)s and %(n)s more", names=', '.join(names[:limit]),
                 n=len(names) - limit)

    # =================================================================
    # Before applying: what each lane will do
    # =================================================================
    @api.model
    def _probe_apply(self, lane, changes):
        """An unsaved proposal for one lane — enough to ask the route
        questions (company, part of the business, facts) without writing."""
        rows = [{'emp_id': int(c.get('emp_id') or 0),
                 'field_id': str(c.get('field_id') or '')} for c in changes]
        bank = lane == 'bank'
        salary = any(lane_of(r['field_id']) == 'pay' for r in rows)
        return self.env['pb.records.apply'].sudo().new({
            'name': '/', 'source': 'import', 'lane': lane,
            'plan_json': json.dumps(rows), 'changes_json': json.dumps(rows),
            'people_count': len({r['emp_id'] for r in rows} - {0}),
            'values_count': len(rows), 'touches_bank': bank,
            'touches_salary': salary, 'company_id': self.env.company.id,
            'user_id': self.env.user.id,
        })

    @api.model
    def _first_step_people(self, probe, key):
        """`(kind, names, sentence)` for the route `key` this probe would
        travel: `fast`, or the names on its first step that is included, or
        `blocked` with the engine's own sentence."""
        engine = self.env['biz.approval.engine'].sudo()
        process = self.env['biz.approval.process']._by_key(key)
        if not process:
            return 'none', [], ''
        ctx = probe._approval_context()
        company = self.env['res.company'].browse(int(ctx['company_id']))
        _binding, version, _trace, error = engine._resolve_binding(
            company, process, ctx.get('scope_keys'), ctx.get('kind_key'))
        if error or not version:
            return 'none', [], (error or {}).get('message') or ''
        from odoo.addons.biz_approval_workflow.models import definition as D
        d = D.normalise(version.definition)
        if route_kind(d) == 'fast':
            return 'fast', [], ''
        today = fields.Date.context_today(self)
        for step in d['steps']:
            if step['kind'] in ('notify', 'fast'):
                continue
            included, _why = engine._step_included(d, step, ctx)
            if not included:
                continue
            people, issue = engine._resolve_step_people(
                step, ctx, company, today, record=probe)
            if issue and issue.get('level') == 'block':
                return 'blocked', [], issue.get('msg') or ''
            return 'route', [p['name'] for p in people], ''
        return 'fast', [], ''

    @api.model
    def lane_outlook(self, changes=None):
        """`{'lanes': [{lane, label, icon, values, people, outcome, names,
        line, tone}]}` for the Apply step. Read only. `outcome` is `now`,
        `approval`, `second` or `nobody`."""
        desk = self._gate()
        changes = [c for c in (changes or []) if isinstance(c, dict)]
        groups = desk._lane_groups(changes)
        out = []
        for lane in ('details', 'pay', 'bank'):
            part = groups.get(lane) or []
            if not part:
                continue
            values = len(part)
            people = len({int(c.get('emp_id') or 0) for c in part} - {0})
            probe = self._probe_apply(lane, part)
            row = {'lane': lane, 'label': self._lane_label(lane),
                   'icon': LANE_ICONS[lane], 'values': values,
                   'people': people, 'names': []}
            if lane == 'bank':
                kind, names, sentence = self._first_step_people(
                    probe, RECORDS_BANK_PROCESS_KEY)
                if kind in ('fast', 'none'):
                    users, _via = probe._second_people(
                        probe.company_id or self.env.company, self.env.user)
                    names = users.mapped('name')
                    kind = 'route' if names else 'blocked'
                    sentence = '' if names else probe._nobody_else_sentence()
                if kind == 'route' and names:
                    row.update(outcome='second', names=names, tone='pri',
                               line=_("Need a second person: %s",
                                      self._names_line(names)))
                else:
                    row.update(outcome='nobody', tone='warn',
                               line=sentence or probe._nobody_else_sentence())
                    # UPDATES P5 (P6 deviation 1) — the way out, as in the
                    # approvals inbox: links for whoever can use them, else
                    # one sentence saying who to ask.
                    row['fix'] = self._way_out(
                        kind='route' if sentence and sentence == probe._nobody_named_sentence()
                        else 'access', probe=probe)
            else:
                go_now = lane == 'details' and probe._details_go_now()
                kind, names, sentence = ('fast', [], '') if go_now else \
                    self._first_step_people(probe, RECORDS_PROCESS_KEY)
                if kind == 'fast':
                    row.update(outcome='now', tone='ok', line=_("Change now"))
                elif kind == 'route' and names:
                    row.update(outcome='approval', names=names, tone='info',
                               line=_("Go to %s for approval",
                                      self._names_line(names)))
                else:
                    row.update(outcome='approval', tone='warn',
                               line=sentence or _("Go for approval"))
            out.append(row)
        return {'lanes': out}

    # =================================================================
    # UPDATES P5 (P6 deviation 1) — the way out of "Nobody else …"
    # =================================================================
    @api.model
    def _way_out(self, request=None, kind='', probe=None):
        """Under "Nobody else in <company> can approve bank details yet — add
        one in Access" (or its named-route twin): the same links the approvals
        inbox offers (`pb.approval.inbox._second_person_fix`, UPDATES P6),
        shown only to someone who can use them; otherwise one plain sentence
        saying who to ask. `None` where the approvals set-up is not installed.

        With a request (Past updates, the Done screen) the inbox's own helper
        answers. Before anything is sent there is no request yet, so the same
        links are built here from the same two gates (Access managers; people
        who set approvals up)."""
        if 'pb.approval.inbox' not in self.env:
            return None
        Inbox = self.env['pb.approval.inbox']
        if request:
            try:
                return Inbox._second_person_fix(request.sudo())
            except Exception:   # noqa: BLE001 — a link never blocks a screen
                return None
        if kind not in ('access', 'route'):
            return None
        Actions = self.env['ir.actions.actions']
        links = []
        try:
            can_access = 'pb.access' in self.env and bool(self.env['pb.access'].can_manage())
        except Exception:   # noqa: BLE001
            can_access = False
        try:
            can_setup = bool(Inbox._can_config())
        except Exception:   # noqa: BLE001
            can_setup = False
        matrix = 'pb_approval_config.action_pb_approval_matrix'
        try:
            if kind == 'route' and can_setup:
                action = Actions._for_xml_id(matrix)
                workflow = self._bank_workflow(probe) if probe is not None else 0
                action['params'] = {'workflow_id': workflow,
                                    'process_key': RECORDS_BANK_PROCESS_KEY}
                links.append({'key': 'route', 'icon': 'workflow',
                              'label': _("Add a person to the bank details route"),
                              'action': action})
            if kind == 'access':
                if can_access:
                    action = Actions._for_xml_id('biz_access.action_pb_access_board')
                    action['context'] = {'pb_lens': 'people'}
                    links.append({'key': 'access', 'icon': 'users',
                                  'label': _("Give someone a role in Access"),
                                  'action': action})
                if can_setup:
                    action = Actions._for_xml_id(matrix)
                    action['params'] = {'tab': 'people', 'role_key': 'finance'}
                    links.append({'key': 'people', 'icon': 'userCheck',
                                  'label': _("Name a Finance approver"),
                                  'action': action})
        except Exception:   # noqa: BLE001 — an action that is not there
            links = []
        return {'kind': kind, 'links': links, 'ask': '' if links else _(
            "Only your administrator can add someone who may approve bank details. Ask them "
            "to add one — they can then try this again from here.")}

    @api.model
    def _bank_workflow(self, probe):
        """The bank details route this probe would travel (its workflow id)."""
        try:
            engine = self.env['biz.approval.engine'].sudo()
            process = self.env['biz.approval.process']._by_key(RECORDS_BANK_PROCESS_KEY)
            ctx = probe._approval_context()
            company = self.env['res.company'].browse(int(ctx['company_id']))
            _binding, version, _trace, _error = engine._resolve_binding(
                company, process, ctx.get('scope_keys'), ctx.get('kind_key'))
            return version.workflow_id.id if version else 0
        except Exception:   # noqa: BLE001
            return 0

    # =================================================================
    # The company switch
    # =================================================================
    @api.model
    def _may_set_switch(self):
        return any(self.env.user.has_group(g) for g in _CONFIG_GROUPS)

    @api.model
    def get_details_now(self):
        self._gate()
        company = self.env.company
        probe = self._probe_apply('details', [])
        kind, _version = probe._records_route()
        return {'on': bool(company.pb_records_sheet_details_now),
                'can_set': self._may_set_switch(),
                'route': kind,
                'company': company.name}

    @api.model
    def set_details_now(self, on=True):
        """Turn "Personal details from a sheet apply without approval" on or
        off for the company in use. Only for whoever looks after
        approvals."""
        self._gate()
        if not self._may_set_switch():
            return {'ok': False, 'msg': _(
                "Only someone who looks after approvals can change this.")}
        self.env.company.sudo().write(
            {'pb_records_sheet_details_now': bool(on)})
        return dict(self.get_details_now(), ok=True)

    @api.model
    def get_home(self):
        answer = super().get_home()
        try:
            answer['details_now'] = self.get_details_now()
        except Exception:   # noqa: BLE001 — a switch never blocks the home
            answer['details_now'] = {'on': True, 'can_set': False,
                                     'route': '', 'company': ''}
        return answer

    # =================================================================
    # Past updates: one line per lane
    # =================================================================
    @api.model
    def _lane_rows(self, applies, may_write):
        labels = dict(applies._fields['state']._description_selection(self.env))
        rows = []
        for rec in applies.sorted(lambda a: ({'details': 0, 'pay': 1, 'bank': 2}
                                             .get(a.lane, 3), a.id)):
            reason = rec._blocked_reason()
            state = 'blocked' if reason else (
                'undone' if rec.undone else rec.state)
            label = _("Could not be made") if reason else (
                _("Undone") if rec.undone else labels.get(rec.state, rec.state))
            if rec.details_now and rec.applied and not rec.undone:
                label = _("Changed now")
            rows.append({
                'apply_id': rec.id,
                'reference': rec.name or '',
                'lane': rec.lane or '',
                'label': self._lane_label(rec.lane) or _("Changes"),
                'icon': LANE_ICONS.get(rec.lane or '', 'pencil'),
                'state': state,
                'state_label': label,
                'values': rec.count_values or rec.values_count,
                'people': rec.count_people or rec.people_count,
                'with_whom': rec._waiting_for() if rec.state == 'pending' else '',
                'note': reason or (rec.block_note or ''),
                'start_date': fields.Date.to_string(rec.start_date)
                if rec.start_date else '',
                'details_now': rec.details_now,
                # UPDATES P5 (P6 deviation 1) — the way out of "Nobody else …".
                'fix': self._way_out(request=rec.approval_request_id)
                if rec.lane == 'bank' and reason else None,
                'can_undo': bool(may_write and rec.applied and not rec.undone),
                'can_cancel': bool(
                    may_write and not rec.applied
                    and rec.state in ('pending', 'scheduled')
                    and rec.with_env(self.env)._may_cancel()),
            })
        return rows

    @api.model
    def _batch_row(self, batch, may_write):
        row = super()._batch_row(batch, may_write)
        if batch.kind == 'oneoff':
            return row
        applies = batch.apply_ids.sudo()
        if any(applies.mapped('lane')):
            row['lanes'] = self._lane_rows(applies, may_write)
        return row

    @api.model
    def undo(self, batch_id=0, apply_id=0):
        """UPDATES P3a — Undo one lane (`apply_id`) or the whole update."""
        if not apply_id:
            return super().undo(batch_id)
        desk = self._gate()
        rec, batch = self._batch_of(apply_id)
        if not rec:
            return {'ok': False, 'msg': _(
                "That update is not on record in the companies you are "
                "working in.")}
        if not self._can_write(desk):
            return {'ok': False, 'msg': _(
                "Undoing an update needs permission to change employee "
                "records. Ask an administrator for the HR or Payroll Officer "
                "role.")}
        if not rec.applied or rec.undone:
            return {'ok': False, 'msg': _(
                "Nothing in this part has been changed, so there is nothing "
                "to undo.") if not rec.applied else _(
                "This part has already been undone.")}
        res = desk.undo_apply(rec.id)
        if not res.get('ok'):
            return res
        return {'ok': True, 'restored': res.get('restored') or 0,
                'skipped_changed_since': res.get('skipped_changed_since') or 0,
                'skipped_missing': res.get('skipped_missing') or 0,
                'batch_id': batch.id, 'name': batch.name,
                'lane': rec.lane or ''}
