# -*- coding: utf-8 -*-
"""People › Pay › Scales — "Raise the scale" (WDGAP S8-D, SC1): the screen's
server half, on `pb.pay.scales` like the rest of the tab.

Reads: the people who may read pay bands. Prepare / send / take back: the
people who may set pay bands. Everything runs under sudo AFTER that gate,
inside the reader's own companies (the tab's rule).

A draft request is a saved record so the preview can be re-read, but saving a
draft writes nothing anywhere else: the table, the people and the cost are
worked out when read. Sending freezes them (`pb.pay.scale.raise._freeze`).
"""
import json
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .scale_raise import LIVE_STATES, METHODS, OPEN_STATES, OUTCOMES

_logger = logging.getLogger(__name__)

#: Rows a group of people sends to the screen at most.
ROWS_PER_GROUP = 300


class PbPayScalesRaiseScreen(models.AbstractModel):
    _inherit = 'pb.pay.scales'

    @api.model
    def _raise(self, raise_id):
        rec = self.env['pb.pay.scale.raise'].sudo().browse(int(raise_id or 0)).exists()
        if not rec:
            raise UserError(_("That scale rise is no longer there."))
        self._scale(rec.scale_id.id)
        if rec.company_id not in self._companies():
            raise UserError(_("That scale rise is no longer there."))
        return rec

    @api.model
    def _state_tone(self, state):
        return {'draft': 'muted', 'returned': 'warn', 'pending': 'act',
                'scheduled': 'info', 'applied': 'ok', 'rejected': 'bad',
                'cancelled': 'muted', 'taken_back': 'muted'}.get(state, 'muted')

    # ================================================================ list
    @api.model
    def raise_list(self, scale_id):
        """The rises of one scale, newest first, for the strip on the card."""
        self._require_read()
        scale = self._scale(scale_id)
        Raise = self.env['pb.pay.scale.raise'].sudo()
        rows = []
        for rec in Raise.search([('scale_id', '=', scale.id),
                                 ('company_id', 'in', self._companies().ids or [0])],
                                limit=12):
            counts = rec._counts() if rec.state not in OPEN_STATES else {}
            rows.append({
                'id': rec.id, 'name': rec.name if rec.name != '/' else _("Draft"),
                'state': rec.state, 'tone': self._state_tone(rec.state),
                'state_label': rec._sel_label('state', rec.state),
                'date': rec._day(rec.effective_date),
                'people': counts.get('move', 0),
            })
        return {'rows': rows,
                'live': bool(Raise.search_count([('scale_id', '=', scale.id),
                                                 ('state', 'in', LIVE_STATES)]))}

    # ================================================================ save
    @api.model
    def _raise_vals(self, scale, vals):
        vals = dict(vals or {})
        out = {}
        if 'effective_date' in vals:
            out['effective_date'] = self._day(vals['effective_date']) \
                if vals.get('effective_date') else False
        if vals.get('method') in dict(METHODS):
            out['method'] = vals['method']
        for key in ('pct', 'flat', 'new_base_rate'):
            if key in vals:
                out[key] = self._num(vals.get(key) or 0)
        if 'reason' in vals:
            out['reason'] = (vals.get('reason') or '').strip()[:2000]
        if 'typed' in vals:
            rows = []
            grades = set(scale.grade_ids.ids)
            for row in vals.get('typed') or []:
                try:
                    grade_id = int(row.get('grade_id') or 0)
                    step = int(row.get('step') or 0)
                except (TypeError, ValueError, AttributeError):
                    continue
                if grade_id not in grades or not 1 <= step <= scale.step_count:
                    continue
                key = 'coefficient' if scale.mode == 'coefficient' else 'amount'
                value = self._num(row.get(key) or row.get('value') or 0)
                if value < 0:
                    raise ValidationError(_("An amount on a scale cannot be below zero."))
                rows.append({'grade_id': grade_id, 'step': step, key: value})
            out['typed_json'] = json.dumps(rows)
        return out

    @api.model
    def raise_save(self, scale_id, vals=None, raise_id=0):
        """Create or change a DRAFT rise. Writes nothing outside the request."""
        self._require_write()
        scale = self._scale(scale_id)
        Raise = self.env['pb.pay.scale.raise'].sudo()
        out = self._raise_vals(scale, vals)
        if raise_id:
            rec = self._raise(raise_id)
            if rec.state not in OPEN_STATES:
                raise UserError(_("This scale rise has been sent in; it can no "
                                  "longer be changed."))
            rec.write(out)
        else:
            if not scale.version_ids:
                raise UserError(_("%s has no amounts yet, so there is nothing to "
                                  "raise.", scale.name))
            out.update(scale_id=scale.id, user_id=self.env.uid,
                       company_id=self.env.company.id
                       if self.env.company in self._companies()
                       else self._companies()[:1].id)
            if 'effective_date' not in out or not out['effective_date']:
                today = fields.Date.context_today(self)
                out['effective_date'] = (today.replace(day=28) + timedelta(days=4)) \
                    .replace(day=1)
            rec = Raise.create(out)
        return self.raise_read(rec.id)

    @api.model
    def raise_toggle(self, raise_id, contract_id, leave_out=True):
        """Leave one person out of a draft rise, or put them back."""
        self._require_write()
        rec = self._raise(raise_id)
        if rec.state not in OPEN_STATES:
            raise UserError(_("This scale rise has been sent in; it can no longer "
                              "be changed."))
        ids = rec.excluded()
        cid = int(contract_id or 0)
        if leave_out:
            ids.add(cid)
        else:
            ids.discard(cid)
        rec.write({'excluded_json': json.dumps(sorted(ids))})
        return self.raise_read(rec.id)

    # ================================================================ read
    @api.model
    def raise_read(self, raise_id):
        """One rise as the drawer shows it: the table, the people in groups,
        the cost per currency, what happens next."""
        self._require_read()
        rec = self._raise(raise_id)
        scale = rec.scale_id
        currency = scale.currency_id
        draft = rec.state in OPEN_STATES
        problems = []
        if draft:
            base = rec._base_version() if rec.effective_date else \
                scale.version_ids.sorted('date_from')[-1:]
            cells, rate, more = rec._new_table(base)
            problems = list(dict.fromkeys(rec._problems(cells) + more))
            # Nobody is listed until the table actually goes up (a fresh draft
            # at 0% would otherwise read as people "above" an unchanged step).
            rises = any(float(c['new']) > float(c['old']) + 1e-9 for c in cells or [])
            rows = rec._plan(cells) if rises else []
            costs = rec._costs_for(rows)
            people = [self._raise_row(r['contract'], r['placement'].grade_id,
                                      r['placement'].step_no, r['outcome'], r['why'],
                                      r['old'], r['new'], r.get('cost', 0.0),
                                      r.get('how'), r.get('currency') or currency,
                                      r['drifted'], '', '')
                      for r in rows]
            movers = self.env['hr.employee'].browse(
                [r['contract'].employee_id.id for r in rows if r['outcome'] == 'move'])
            paid = rec._paid_months_for(movers) if rec.effective_date else []
        else:
            base = rec.base_version_id
            cells, rate = rec.cells(), rec.cells_base_rate
            costs = rec.costs()
            people = [self._raise_row(l.contract_id, l.grade_id, l.step_no, l.outcome,
                                      l.why, l.old_wage, l.new_wage, l.cost_month,
                                      l.cost_how, l.cost_currency_id or currency,
                                      l.drifted, l.state, l.skip_reason)
                      for l in rec.line_ids]
            paid = rec.paid_months()
        counts = {key: 0 for key, _l in OUTCOMES}
        groups = {key: [] for key, _l in OUTCOMES}
        for row in people:
            counts[row['outcome']] = counts.get(row['outcome'], 0) + 1
            if len(groups[row['outcome']]) < ROWS_PER_GROUP:
                groups[row['outcome']].append(row)
        table = self._raise_table(scale, cells)
        request = rec.approval_request_id
        steps = []
        if request:
            for step in request.step_ids.sorted('sequence'):
                if not step.included or step.kind in ('fast', 'notify'):
                    continue
                steps.append({'title': step.title, 'status': step.status,
                              'people': ', '.join(sorted({s.acting_user_id.name or ''
                                                          for s in step.seat_ids}))})
        today = rec._company_today()
        done = rec.line_ids.filtered(lambda l: l.state == 'done')
        skipped = rec.line_ids.filtered(lambda l: l.state == 'skipped')
        can_write = self._can_write()
        unplaced = len(self._unplaced(scale)) if draft else 0
        cost_note = ''
        if any(c.get('wage') for c in costs):
            cost_note = _("Worked out through the pay rules where the person's scheme "
                          "allows it; the rest by the wage difference alone.")
        elif costs:
            cost_note = _("Worked out through each person's own pay rules: basic "
                          "pay and everything that follows from it, with the "
                          "employer's contributions.")
        return {
            'id': rec.id, 'name': rec.name if rec.name != '/' else '',
            'state': rec.state, 'state_label': rec._sel_label('state', rec.state),
            'tone': self._state_tone(rec.state), 'editable': bool(draft and can_write),
            'scale': {'id': scale.id, 'name': scale.name, 'mode': scale.mode,
                      'currency': self._currency_dict(currency),
                      'step_count': scale.step_count},
            'effective_date': fields.Date.to_string(rec.effective_date) or '',
            'effective_label': rec._day(rec.effective_date),
            'past': bool(rec.effective_date and rec.effective_date < today),
            'method': rec.method, 'pct': rec.pct, 'flat': rec.flat,
            'new_base_rate': rec.new_base_rate or (base.base_rate if base else 0.0),
            'old_base_rate': base.base_rate if base else 0.0,
            'base_rate': rate, 'reason': rec.reason or '',
            'base_label': self._version_label(base) if base else '',
            'table': table, 'counts': counts, 'groups': groups,
            'excluded': sorted(rec.excluded()),
            'costs': costs, 'cost_note': cost_note,
            'paid_months': [{'label': m.get('month_label'), 'config': m.get('config'),
                             'count': m.get('count', 0)} for m in paid],
            'unplaced': unplaced,
            'problems': problems if draft else [],
            'steps': steps,
            'waiting': rec._waiting_for() if rec.state == 'pending' else '',
            'block_note': rec.block_note or '',
            'blocked': bool(request and request.state == 'blocked'),
            'block_reason': (request.block_reason or '') if request else '',
            'prepared_by': rec.user_id.name or '',
            'done': len(done), 'skipped': len(skipped),
            'version_label': self._version_label(rec.version_id) if rec.version_id else '',
            'can_send': bool(draft and can_write and not problems
                             and counts.get('move')),
            'can_cancel': bool(rec.state in ('draft', 'pending', 'returned')
                               and (can_write or rec.user_id == self.env.user)),
            'can_take_back': bool(rec.state == 'scheduled' and rec.effective_date
                                  and rec.effective_date > today
                                  and (can_write or rec.user_id == self.env.user)),
            'can_rework': bool(rec.state == 'applied' and paid and can_write),
            'rework_ready': rec._retro_installed(),
        }

    @api.model
    def _raise_row(self, contract, grade, step, outcome, why, old, new, cost, how,
                   currency, drifted, state, skip):
        employee = contract.employee_id
        scale_money = currency
        return {
            'contract_id': contract.id, 'employee_id': employee.id,
            'name': employee.name or contract.name or '',
            'job': (contract.job_id or employee.job_id).display_name or '',
            'grade': grade.name or '', 'step': step or 0,
            'outcome': outcome, 'why': why or '',
            'old': old, 'new': new,
            'old_label': self._money(old, scale_money),
            'new_label': self._money(new, scale_money),
            'cost_label': self._money(cost, scale_money) if outcome == 'move' else '',
            'how': how or '', 'drifted': bool(drifted),
            'state': state or '', 'skip': skip or '',
        }

    @api.model
    def _raise_table(self, scale, cells):
        """``[{grade, steps: [{step, old, new, old_label, new_label, up}]}]``."""
        by_grade = {}
        for cell in cells or []:
            by_grade.setdefault(int(cell['grade_id']), {})[int(cell['step'])] = cell
        currency = scale.currency_id
        out = []
        for grade in scale.grade_ids.sorted(lambda g: (g.sequence, g.id)):
            steps = []
            for step in range(1, scale.step_count + 1):
                cell = by_grade.get(grade.id, {}).get(step)
                if not cell:
                    steps.append({'step': step, 'old': 0, 'new': 0, 'old_label': '',
                                  'new_label': '', 'up': '', 'coefficient': 0,
                                  'amount': 0})
                    continue
                old, new = float(cell.get('old') or 0), float(cell.get('new') or 0)
                steps.append({
                    'step': step, 'old': old, 'new': new,
                    'old_label': self._money(old, currency),
                    'new_label': self._money(new, currency),
                    'up': ('+%.1f%%' % ((new - old) / old * 100.0)) if old else '',
                    'coefficient': float(cell.get('coefficient') or 0.0),
                    'amount': float(cell.get('amount') or 0.0),
                })
            out.append({'grade_id': grade.id, 'grade': grade.name, 'steps': steps})
        return out

    # ================================================================= act
    @api.model
    def raise_act(self, raise_id, verb):
        """send / cancel / take_back / rework / remove (a draft)."""
        rec = self._raise(raise_id)
        if verb == 'send':
            self._require_write()
            answer = rec.sudo(False).action_send()
            return dict(answer, read=self.raise_read(rec.id))
        if verb == 'cancel':
            rec._act_guard()
            rec.action_cancel()
            return {'ok': True, 'message': _("Cancelled. Nothing was changed."),
                    'read': self.raise_read(rec.id)}
        if verb == 'take_back':
            rec._act_guard()
            rec.action_take_back()
            return {'ok': True, 'message': _("Taken back. Nobody's pay changed."),
                    'read': self.raise_read(rec.id)}
        if verb == 'rework':
            self._require_write()
            return rec.action_open_rework()
        if verb == 'remove':
            self._require_write()
            if rec.state != 'draft' or rec.approval_request_id:
                raise UserError(_("Only a draft that was never sent can be removed."))
            rec.unlink()
            return {'ok': True, 'message': _("The draft is removed.")}
        raise UserError(_("That is not something this screen can do."))


class PbPayScaleRaiseActs(models.Model):
    _inherit = 'pb.pay.scale.raise'

    def _act_guard(self):
        """The person pressing may act on it (prepared it, or sets pay bands)."""
        self.ensure_one()
        if not (self.user_id == self.env.user or self.env['pb.pay.scales']._can_write()):
            raise UserError(_("Only the person who prepared it or the people who "
                              "set pay bands can do this."))
        return True
