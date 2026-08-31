# -*- coding: utf-8 -*-
"""`pb.exits` — the Exits lens's only server surface.

The shape every cockpit in this product keeps: an `AbstractModel` facade,
`@api.model` reads, every independent probe inside its own `_safe()` so one
failing metric answers zero instead of taking the screen down, `self.env
.companies` scoping on every search, a row cap, and no sudo in a READ.

The one deliberate exception is the GATE. `pb_ready` is computed from three
sudo reads (P2's register, P4's clearances, P0's blocking steps) because a gate
a reader's own access can soften is not a gate — but it is only ever REPORTED
here. Every write goes through `_require_write()` and then through the model
that owns the fact.

It reuses P0's tiers, the same call P3 made for the same reason: an exit is not
a separate permission from the rest of the lifecycle, and a fifth ladder would
be a group nobody knew to grant.
"""

import logging
from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .offboarding_common import (
    CLEARANCE_DEPT_LABEL, CLEARANCE_ORDER, GROUP_ADMIN, GROUP_MANAGER,
    GROUP_USER, KT_STATE_LABEL, RESIGNATION_STATE_LABEL, initials,
)

_logger = logging.getLogger(__name__)

BOARD_LIMIT = 300

#: A leaver stays on this board for this long after their last day. Past it the
#: checklist may still have a stray step on it, but the person has gone and a
#: board that still calls them "leaving" is wrong.
LEAVING_FOR_DAYS = 120


class PbExits(models.AbstractModel):
    _name = 'pb.exits'
    _description = 'Payobook Exits cockpit data'

    # ------------------------------------------------------------------ gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug('Exits metric failed: %s', e)
            return default

    @api.model
    def _can_read(self):
        user = self.env.user
        return (user.has_group(GROUP_USER) or user.has_group(GROUP_MANAGER)
                or user.has_group(GROUP_ADMIN) or user._is_admin())

    @api.model
    def _can_write(self):
        user = self.env.user
        return (user.has_group(GROUP_MANAGER) or user.has_group(GROUP_ADMIN)
                or user._is_admin())

    @api.model
    def _require_write(self):
        if not self._can_write():
            raise AccessError(_(
                "You can look at who is leaving, but changing an exit is for "
                "the HR team. Ask them to make the change."))
        return True

    # ------------------------------------------------------------- the board
    @api.model
    def get_board(self):
        if not self._can_read():
            return {'allowed': False, 'can_write': False, 'kpis': {},
                    'rows': [], 'countries': [], 'departments': [],
                    'months': [], 'depts': []}
        Case = self.env['pb.journey.case']
        co_ids = self.env.companies.ids or [self.env.company.id]
        today = date.today()
        floor = today - timedelta(days=LEAVING_FOR_DAYS)

        cases = self._safe(lambda: Case.search([
            ('company_id', 'in', co_ids),
            ('case_type', '=', 'offboarding'),
            ('state', 'in', ('draft', 'active', 'on_hold')),
            '|', ('anchor_date', '=', False), ('anchor_date', '>=', floor),
        ], order='anchor_date, id', limit=BOARD_LIMIT),
            default=Case.browse())

        rows = []
        for case in cases:
            try:
                rows.append(self._row(case, today))
            except Exception:
                _logger.exception('Exits row for case %s', case.id)

        month_end = today + timedelta(days=31)
        kpis = {
            'leaving': len([r for r in rows if r['lwd']
                            and today <= _d(r['lwd']) <= month_end]),
            'gone': len([r for r in rows if r['lwd']
                         and _d(r['lwd']) < today]),
            'blocked': len([r for r in rows
                            if r['ff']['id'] and not r['ff']['ready']
                            and not r['ff']['closed']]),
            'clearances': sum(
                len([c for c in r['clearances'] if c['state'] == 'pending'])
                for r in rows),
            'assets': sum(r['assets'] for r in rows),
        }
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'kpis': kpis,
            'rows': rows,
            'total': len(rows),
            'capped': len(rows) >= BOARD_LIMIT,
            'countries': _facet(rows, 'country'),
            'departments': _facet(rows, 'dept'),
            'months': _facet(rows, 'month'),
            'depts': [{'id': d, 'label': CLEARANCE_DEPT_LABEL[d]}
                      for d in CLEARANCE_ORDER],
        }

    @api.model
    def _row(self, case, today=None):
        today = today or date.today()
        emp = case.employee_id
        lwd = case.anchor_date
        days = (lwd - today).days if lwd else None
        clearances = self._safe(
            lambda: case.clearance_ids.sorted(key=lambda c: c.sequence),
            default=self.env['pb.exit.clearance'].browse())
        by_dept = {c.dept: c for c in clearances}
        assets = self._safe(
            lambda: self.env['pb.asset'].open_items_for(emp.id),
            default={'tangible': [], 'digital': [], 'total': 0})
        resignation = self._safe(
            lambda: self.env['pb.resignation'].sudo().search(
                [('employee_id', '=', emp.id)],
                order='create_date desc', limit=1),
            default=self.env['pb.resignation'].browse())
        ff = self._safe(
            lambda: self.env['hr.full.final.settlement'].pb_gate_for(emp.id),
            default={'id': 0, 'ready': False, 'closed': False, 'blockers': [],
                     'net': 0.0, 'currency': '', 'date': ''})
        kt = self._safe(lambda: case.kt_item_ids,
                        default=self.env['pb.kt.item'].browse())
        farewell = self._safe(
            lambda: case.task_ids.filtered(
                lambda t: t.automation_key == 'farewell')[:1],
            default=self.env['pb.journey.task'].browse())
        feedback = self._safe(
            lambda: self.env['pb.feedback.request'].sudo().search(
                [('case_id', '=', case.id), ('kind', '=', 'exit')], limit=1),
            default=self.env['pb.feedback.request'].browse())
        return {
            'id': case.id,
            'employee_id': emp.id,
            'employee': emp.name or '—',
            'initials': initials(emp.name),
            'avatar': '/web/image/hr.employee/%s/avatar_128' % emp.id
            if emp else '',
            'job': emp.job_title or (emp.job_id.name if emp.job_id else '')
            or '',
            'dept': (emp.department_id.name if emp.department_id else '')
            or _('No team'),
            'country': (emp.country_id.name if emp.country_id else '')
            or (emp.company_id.country_id.name
                if emp.company_id and emp.company_id.country_id else '')
            or _('Not set'),
            'lwd': str(lwd) if lwd else '',
            'month': str(lwd)[:7] if lwd else '',
            'days': days,
            'when': _when(days),
            'progress': case.progress,
            'open_tasks': case.open_task_count,
            'overdue': case.overdue_task_count,
            'resignation_id': resignation.id if resignation else 0,
            'resignation_state': resignation.state if resignation else '',
            'resignation_label': (
                RESIGNATION_STATE_LABEL.get(resignation.state, '')
                if resignation else _('Not through a resignation')),
            'clearances': [{
                'id': by_dept[d].id if d in by_dept else 0,
                'dept': d,
                'label': CLEARANCE_DEPT_LABEL[d],
                'state': by_dept[d].state if d in by_dept else 'missing',
                'owner': (by_dept[d].owner_user_id.name
                          if d in by_dept and by_dept[d].owner_user_id else ''),
                'note': (by_dept[d].note or '') if d in by_dept else '',
            } for d in CLEARANCE_ORDER],
            'kt_open': len([k for k in kt if k.state != 'done']),
            'kt_total': len(kt),
            'kt_last_ping': str(case.kt_last_ping) if case.kt_last_ping else '',
            'assets': len(assets.get('tangible') or []),
            'assets_digital': len(assets.get('digital') or []),
            'ff': ff,
            'feedback': feedback.state if feedback else '',
            'feedback_done': bool(feedback and feedback.state == 'submitted'),
            'feedback_id': feedback.id if feedback else 0,
            'farewell_task_id': farewell.id if farewell else 0,
            'farewell_state': farewell.state if farewell else '',
        }

    # -------------------------------------------------------------- one exit
    @api.model
    def get_exit(self, case_id):
        """The whole of one leaver — P0's case detail plus this phase's rows.

        The steps, check-ins and letters are read through `pb.journeys` rather
        than re-derived: two implementations of "what is on this checklist"
        would drift the first week one of them grew a column.
        """
        if not self._can_read():
            raise AccessError(_("Exits are looked after by the HR team."))
        case = self.env['pb.journey.case'].browse(int(case_id)).exists()
        if not case:
            raise UserError(_("That leaving checklist is no longer there."))
        detail = self.env['pb.journeys'].get_case(case.id)
        detail['leaver'] = self._row(case)
        detail['kt'] = [{
            'id': k.id,
            'topic': k.topic or '',
            'from': k.from_employee_id.name or '',
            'to': k.to_employee_id.name or '',
            'link': k.doc_link or '',
            'notes': k.notes or '',
            'state': k.state,
            'state_label': KT_STATE_LABEL.get(k.state, k.state or ''),
        } for k in case.kt_item_ids.sorted(key=lambda k: (k.sequence, k.id))]
        detail['assets'] = self._safe(
            lambda: self.env['pb.asset'].open_items_for(case.employee_id.id),
            default={'tangible': [], 'digital': [], 'total': 0})
        farewell = case.task_ids.filtered(
            lambda t: t.automation_key == 'farewell')[:1]
        detail['farewell'] = {
            'task_id': farewell.id if farewell else 0,
            'state': farewell.state if farewell else '',
            'due': str(farewell.due_date) if farewell and farewell.due_date
            else '',
            'draft': self._safe(lambda: farewell.farewell_draft(), default='')
            if farewell else '',
        } if farewell else None
        feedback = self.env['pb.feedback.request'].sudo().search(
            [('case_id', '=', case.id), ('kind', '=', 'exit')], limit=1)
        detail['feedback'] = {
            'id': feedback.id,
            'state': feedback.state,
            'window_end': str(feedback.window_end) if feedback.window_end
            else '',
            # The link is handed only to somebody who may WRITE — it is a
            # credential, and a credential on a read-only screen is a
            # credential in a screenshot.
            'link': self._safe(lambda: feedback._token_url(), default='')
            if self._can_write() else '',
            'answers': self._safe(lambda: _answers(feedback), default=[]),
        } if feedback else None
        return detail

    # --------------------------------------------------------- the row actions
    @api.model
    def clear_clearance(self, clearance_id, note=None, not_needed=False):
        """Sign one desk off. The MODEL decides who may — not this facade.

        `pb.exit.clearance.action_clear` admits the owner of the desk as well
        as the HR team, which is wider than `_require_write()` and deliberately
        so: an IT manager who is not in the lifecycle team still has to be able
        to say the laptop came back.
        """
        if not self._can_read():
            raise AccessError(_("Exits are looked after by the HR team."))
        row = self.env['pb.exit.clearance'].browse(
            int(clearance_id or 0)).exists()
        if not row:
            raise UserError(_("That clearance is no longer there."))
        if not_needed:
            return row.action_not_needed(note=note)
        return row.action_clear(note=note)

    @api.model
    def reopen_clearance(self, clearance_id):
        self._require_write()
        row = self.env['pb.exit.clearance'].browse(
            int(clearance_id or 0)).exists()
        if not row:
            raise UserError(_("That clearance is no longer there."))
        return row.action_reopen()

    @api.model
    def add_kt_item(self, case_id, topic, to_employee_id=None, doc_link=None):
        self._require_write()
        case = self.env['pb.journey.case'].browse(int(case_id or 0)).exists()
        if not case:
            raise UserError(_("That leaving checklist is no longer there."))
        topic = (topic or '').strip()
        if not topic:
            raise UserError(_("Say what is being handed over."))
        self.env['pb.kt.item'].create({
            'case_id': case.id,
            'topic': topic[:200],
            'from_employee_id': case.employee_id.id,
            'to_employee_id': int(to_employee_id) if to_employee_id else False,
            'doc_link': (doc_link or '').strip()[:400] or False,
            'company_id': (case.company_id or self.env.company).id,
        })
        return True

    @api.model
    def settle_kt_item(self, kt_id, done=True):
        self._require_write()
        row = self.env['pb.kt.item'].browse(int(kt_id or 0)).exists()
        if not row:
            raise UserError(_("That handover item is no longer there."))
        return row.action_done() if done else row.action_reopen()

    @api.model
    def nudge_kt(self, case_id):
        """Remind the people who owe a handover, now rather than on the 15th."""
        self._require_write()
        case = self.env['pb.journey.case'].browse(int(case_id or 0)).exists()
        if not case:
            raise UserError(_("That leaving checklist is no longer there."))
        if not case.kt_item_ids.filtered(lambda k: k.state != 'done'):
            raise UserError(_(
                "Everything on the handover list has been handed over — there "
                "is nobody left to remind."))
        if not case.send_kt_ping():
            raise UserError(_(
                "Nothing was sent. There may be no email address for the HR "
                "contact or for the people picking the work up."))
        return True

    @api.model
    def set_farewell_note(self, task_id, text):
        """HR's own wording for the farewell note, before the day it goes."""
        self._require_write()
        task = self.env['pb.journey.task'].browse(int(task_id or 0)).exists()
        if not task or task.automation_key != 'farewell':
            raise UserError(_("That is not the farewell step."))
        if task.state in ('done', 'skipped'):
            raise UserError(_(
                "The farewell note has already gone out, so the wording "
                "cannot be changed now."))
        task.sudo().write({'note': (text or '').strip()[:4000] or False})
        return True

    @api.model
    def run_step_now(self, task_id):
        """Run an automatic step today instead of waiting for its date."""
        self._require_write()
        task = self.env['pb.journey.task'].browse(int(task_id or 0)).exists()
        if not task:
            raise UserError(_("That step is no longer there."))
        if not task.is_automatic:
            raise UserError(_(
                "This step is for a person to do — there is nothing to run."))
        if not task.action_auto(force=True):
            raise UserError(_(
                "Nothing was sent. %s",
                task.auto_error or _(
                    "It may be waiting for something else — a settlement that "
                    "is not closed yet, or a switch that is off in the "
                    "settings.")))
        return True

    @api.model
    def send_exit_invite(self, case_id):
        """Send (or re-send) the exit questionnaire link."""
        self._require_write()
        case = self.env['pb.journey.case'].browse(int(case_id or 0)).exists()
        if not case:
            raise UserError(_("That leaving checklist is no longer there."))
        request = self.env['pb.feedback.request'].sudo().search(
            [('case_id', '=', case.id), ('kind', '=', 'exit')], limit=1)
        if not request:
            request = case.ensure_exit_feedback()
        if not request:
            raise UserError(_("The exit questionnaire could not be prepared."))
        if request.state == 'submitted':
            raise UserError(_("They have already answered it."))
        if not request.action_send():
            raise UserError(_(
                "There is no email address on this person's record to send "
                "it to."))
        return True

    @api.model
    def close_settlement(self, settlement_id):
        """The gate, from the board. The model raises the plain-English refusal."""
        self._require_write()
        settlement = self.env['hr.full.final.settlement'].browse(
            int(settlement_id or 0)).exists()
        if not settlement:
            raise UserError(_(
                "There is no final settlement for this person yet. Generate "
                "one first, then close it."))
        return settlement.action_pb_close()

    @api.model
    def run_automation(self):
        """The daily job, on demand. Managers only — it sends email."""
        self._require_write()
        return self.env['pb.journey.case'].run_offboarding_automation()

    # ------------------------------------------------------------- the doors
    @api.model
    def open_case_action(self, case_id):
        if not self._can_read():
            raise AccessError(_("Exits are looked after by the HR team."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Leaving checklist'),
            'res_model': 'pb.journey.case',
            'res_id': int(case_id or 0),
            'view_mode': 'form',
        }

    @api.model
    def open_settlement_action(self, employee_id):
        if not self._can_read():
            raise AccessError(_("Exits are looked after by the HR team."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Final settlement'),
            'res_model': 'hr.full.final.settlement',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', int(employee_id or 0))],
            'context': {'search_default_employee_id': int(employee_id or 0)},
        }

    @api.model
    def open_resignation_action(self, resignation_id):
        if not self._can_read():
            raise AccessError(_("Exits are looked after by the HR team."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Resignation'),
            'res_model': 'pb.resignation',
            'res_id': int(resignation_id or 0),
            'view_mode': 'form',
        }


def _answers(request):
    """The exit answers, paired with the question they answered.

    Anything unreadable answers with an empty list rather than raising: a
    broken answer set must not turn the board into an error page.
    """
    import json
    if not request or not request.answers_json:
        return []
    try:
        loaded = json.loads(request.answers_json) or {}
    except Exception:                   # noqa: BLE001
        return []
    out = []
    for key, item in loaded.items():
        if str(key).startswith('_'):
            continue
        value = (item or {}).get('value') if isinstance(item, dict) else item
        label = ((item or {}).get('label') if isinstance(item, dict)
                 else '') or key
        if value not in (None, '', False):
            out.append({'label': str(label), 'value': str(value)[:600]})
    return out


def _d(value):
    from datetime import datetime
    return datetime.strptime(value, '%Y-%m-%d').date()


def _when(days):
    """"in 3 days" / "today" / "left 12 days ago" — words, not arithmetic."""
    if days is None:
        return ''
    if days == 0:
        return _('last day is today')
    if days == 1:
        return _('last day is tomorrow')
    if days > 0:
        return _('leaves in %s days', days)
    if days == -1:
        return _('left yesterday')
    return _('left %s days ago', -days)


def _facet(rows, key):
    counts = {}
    for row in rows:
        value = row.get(key) or ''
        if value:
            counts[value] = counts.get(value, 0) + 1
    return [{'id': k, 'label': k, 'count': v}
            for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
