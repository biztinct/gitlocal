# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Step 4 "Late and overtime rules" (WFSETUP P3) — facade methods.

Extends `pb.workforce.setup`. The screen edits ONE rule set per company
(`pb.attendance.policy`, handover §2.1):

  * the company's ACTIVE rule set, else its newest DRAFT, else none ('new');
  * an active one is read-only; "Change the rules" makes a revision
    (`policy.copy()` -> draft) that the screen edits while the active one
    keeps calculating; Confirm activates the revision and retires the old one;
  * more than one active rule set, or people pointing at different rule sets
    -> 'advanced': read-only, every write refuses with one sentence.

Mapping (facts D.1, handover §2.2):
  * late lines: the screen shows inclusive whole minutes from 1; band
    `[minimum, maximum)`. Line {from: 1, to: 9} <=> band [1, 10). A hidden
    first band [0, first.from) with 0 hours is always kept; the last line is
    open-ended. A save REBUILDS the bands of a group in one write;
  * per-shift lines: break start / overtime start as clock times <=> elapsed
    hours from the shift start (`break_start_offset` / `normal_end_offset`),
    across midnight for overnight shifts; `break_hours` = the shift's break;
  * rates: `hr.overtime.config` (weekday / weekend / holiday / night), read
    with `_pb_pick` (most specific row wins); a save writes this company's
    own row or creates one, never another company's or a shared row.

The pay example runs the REAL engine (`pb_attendance_policy/engine.py`
`calculate`, facts D.3 steps 1-7) on hypothetical punches and writes nothing.

Screen words: rules, late, overtime, rest day, public holiday, night work.
Never policy, band, category, offset, capture, pairing, multiplier, day kind.
"""

import math
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date

from odoo.addons.pb_attendance_policy.engine import calculate

from .setup import COLOUR_NAME, DEFAULT_COLOUR

GROUPS = ('worker', 'manager')
RATE_TYPES = (('normal', 'weekday'), ('rest_day', 'weekend'), ('holiday', 'holiday'), ('night', 'night'))
DEFAULT_RATES = {'normal': 150, 'rest_day': 200, 'holiday': 300, 'night': 30}
DEFAULT_LATE = {
    'worker': [{'from': 1, 'to': 9, 'hours': 0.0}, {'from': 10, 'to': 29, 'hours': 0.5},
               {'from': 30, 'to': None, 'hours': 1.0}],
    'manager': [{'from': 1, 'to': 29, 'hours': 0.0}, {'from': 30, 'to': None, 'hours': 0.5}],
}
MAX_LATE_MINUTES = 24 * 60
DAY_KINDS = {'weekday': 'weekday', 'normal': 'weekday', 'rest_day': 'weekend', 'weekend': 'weekend',
             'holiday': 'holiday'}


class _Refused(Exception):
    """Rolls a confirm back and carries the plain sentences out."""

    def __init__(self, problems):
        super().__init__(problems)
        self.problems = problems


class PolicyPendingRates(models.Model):
    """Rate changes wait on the draft rule set until Confirm (found in the P3
    walk): the rates live in `hr.overtime.config`, which every overtime
    request reads at once, so writing them while a new version is being
    edited would change pay before the person confirms — and Discard could
    not undo it. A storage field only; no rule-set behaviour changes."""
    _inherit = 'pb.attendance.policy'

    pb_pending_rates = fields.Json(string='Rates waiting for confirmation', copy=False)


class WorkforceSetupRules(models.AbstractModel):
    _inherit = 'pb.workforce.setup'

    # ============================================================ the rule set
    @api.model
    def _rule_sets(self):
        """(active, drafts) of THIS company, sudo behind the caller's gate."""
        Policy = self.env['pb.attendance.policy'].sudo()
        rows = Policy.search([('company_id', '=', self.env.company.id),
                              ('state', 'in', ('draft', 'active'))], order='id desc')
        return rows.filtered(lambda p: p.state == 'active'), rows.filtered(lambda p: p.state == 'draft')

    @api.model
    def _people_policies(self):
        """{policy id: n} over this company's active people (False = none)."""
        out = {}
        for policy, count in self.env['hr.employee'].sudo()._read_group(
                [('active', '=', True)] + self._company_domain(), ['pb_attendance_policy_id'], ['__count']):
            out[policy.id or False] = count
        return out

    @api.model
    def _rules_state(self):
        """(state, record being shown, the active one or empty)."""
        active, drafts = self._rule_sets()
        linked = {k for k in self._people_policies() if k}
        if len(active) > 1 or len(linked) > 1:
            return 'advanced', active[:1] or drafts[:1], active
        if active:
            if drafts:
                return 'revision', drafts[0], active
            return 'active', active, active
        if drafts:
            return 'draft', drafts[0], active
        return 'new', self.env['pb.attendance.policy'].sudo(), active

    @api.model
    def _rules_record(self):
        return self._rules_state()[1]

    @api.model
    def _advanced_sentence(self):
        return _("This company uses more than one set of rules. Open the advanced rules screen.")

    # ============================================================ helpers
    @api.model
    def _default_tz(self):
        company = self.env.company.sudo()
        for name in (company.resource_calendar_id.tz, self.env.user.tz, 'UTC'):
            if name:
                try:
                    pytz.timezone(name)
                    return name
                except Exception:
                    continue
        return 'UTC'

    @api.model
    def _span_minutes(self, shift):
        start = int(round((shift.start_hour or 0.0) * 60))
        end = int(round((shift.end_hour or 0.0) * 60))
        span = end - start + (1440 if shift.is_overnight else 0)
        return span if span > 0 else span + 1440

    @api.model
    def _clock_at(self, shift, offset_hours):
        return self._hhmm((shift.start_hour or 0.0) + (offset_hours or 0.0))

    @api.model
    def _offset_of(self, shift, text):
        """'HH:MM' -> elapsed hours from the shift start (next day if earlier)."""
        start = int(round((shift.start_hour or 0.0) * 60)) % 1440
        return ((self._minutes(text) - start) % 1440) / 60.0

    @api.model
    def _hours_text(self, value):
        return ('%g' % round(value or 0.0, 2))

    @api.model
    def _pct(self, multiplier, extra=False):
        value = (multiplier or 1.0) - (1.0 if extra else 0.0)
        return int(round(value * 100))

    # ------------------------------------------------------------ late lines
    @api.model
    def _bands_to_lines(self, bands):
        """Stored bands of ONE group -> screen lines (the hidden [0, x) band
        with 0 hours folds away; anything else becomes a line from 1)."""
        lines = []
        for band in bands.sorted('minimum'):
            lo = int(round(band.minimum or 0))
            hi = None if (band.open_ended or not band.maximum) else int(round(band.maximum))
            if lo == 0:
                if not band.hours and hi is not None and hi <= 1:
                    continue                     # the hidden first band
                lo = 1
            lines.append({'from': lo, 'to': (hi - 1) if hi is not None else None,
                          'hours': round(band.hours or 0.0, 2)})
        if lines:
            lines[-1]['to'] = None
        return lines

    @api.model
    def _clean_lines(self, lines):
        """Validate the screen's lines of one group. Returns them sorted, the
        last one open-ended. Refuses gaps, overlaps and bad numbers."""
        if not isinstance(lines, (list, tuple)):
            raise UserError(_("The late lines must follow on from each other with no gap."))
        gap = _("The late lines must follow on from each other with no gap.")
        out = []
        for line in lines:
            if not isinstance(line, dict):
                raise UserError(gap)
            lo = self._int(line.get('from'), -1)
            hi = line.get('to')
            hi = None if hi in (None, False, '') else self._int(hi, -1)
            try:
                hours = float(line.get('hours') or 0.0)
            except (TypeError, ValueError):
                raise UserError(_("Hours taken off are a number from 0 to 24."))
            if not 0 <= hours <= 24 or abs(hours * 4 - round(hours * 4)) > 1e-6:
                raise UserError(_("Hours taken off are a number from 0 to 24, in quarter hours."))
            if lo < 1 or lo > MAX_LATE_MINUTES:
                raise UserError(_("A late line starts at 1 minute or more."))
            if hi is not None and hi < lo:
                raise UserError(_("Each late line must end at or after the minute it starts."))
            out.append({'from': lo, 'to': hi, 'hours': round(hours, 2)})
        out.sort(key=lambda l: l['from'])
        for i, line in enumerate(out):
            last = i == len(out) - 1
            if not last:
                if line['to'] is None or out[i + 1]['from'] != line['to'] + 1:
                    raise UserError(gap)
            else:
                line['to'] = None                # the last line is "N minutes late or more"
        return out

    @api.model
    def _lines_to_bands(self, lines, group, confirmed=False):
        """Clean lines -> band values: hidden [0, first) + one per line."""
        if not lines:
            return []
        bands = [{'category': group, 'minimum': 0.0, 'maximum': float(lines[0]['from']),
                  'open_ended': False, 'hours': 0.0, 'confirmed': confirmed}]
        for line in lines:
            open_ = line['to'] is None
            bands.append({'category': group, 'minimum': float(line['from']),
                          'maximum': 0.0 if open_ else float(line['to'] + 1),
                          'open_ended': open_, 'hours': float(line['hours']), 'confirmed': confirmed})
        return bands

    # ------------------------------------------------------------ shifts
    @api.model
    def _rule_shifts(self):
        """Active shifts of this company (and shared ones), those used in a
        working week first. Returns (shifts, ids used in a week)."""
        shifts = self.env['hr.shift.template'].sudo().search(self._shift_domain(), order='sequence, id')
        used = set(self.env['pb.shift.pattern.slot'].sudo().search([
            ('template_id', 'in', shifts.ids), ('company_id', '=', self.env.company.id),
            ('pattern_id.active', '=', True)]).mapped('template_id').ids)
        ordered = shifts.filtered(lambda s: s.id in used) + shifts.filtered(lambda s: s.id not in used)
        return ordered, used

    @api.model
    def _default_shift_line(self, shift):
        span = self._span_minutes(shift) / 60.0
        brk = min(shift.break_duration or 0.0, span)
        return {'break_start_offset': max(0.0, (span - brk) / 2.0), 'normal_end_offset': span,
                'break_hours': brk}

    @api.model
    def _shift_line_ok(self, shift, normal_end, break_start, break_hours):
        span = self._span_minutes(shift) / 60.0 + 1e-9
        return 0 < normal_end <= span and break_start >= 0 and break_hours >= 0 \
            and break_start + break_hours <= span

    @api.model
    def _shift_payload(self, shift, rule, in_weeks):
        stored = bool(rule)
        vals = ({'break_start_offset': rule.break_start_offset, 'normal_end_offset': rule.normal_end_offset,
                 'break_hours': rule.break_hours} if rule else self._default_shift_line(shift))
        problem = False
        if rule and not self._shift_line_ok(shift, rule.normal_end_offset, rule.break_start_offset,
                                            rule.break_hours):
            problem = _("These times no longer fit the shift. Pick new ones.")
        return {
            'shift_id': shift.id,
            'name': shift.name or '',
            'start': self._hhmm(shift.start_hour),
            'end': self._hhmm(shift.end_hour),
            'color': self._colour_name(shift),
            'overnight': bool(shift.is_overnight),
            'break_start': self._clock_at(shift, vals['break_start_offset']),
            'break_minutes': int(round((vals['break_hours'] or 0.0) * 60)),
            'overtime_from': self._clock_at(shift, vals['normal_end_offset']),
            'in_weeks': in_weeks,
            'stored': stored,
            'problem': problem,
        }

    @api.model
    def _colour_name(self, shift):
        return COLOUR_NAME.get(shift.color, DEFAULT_COLOUR)

    @api.model
    def _clean_shift_line(self, shift, line):
        """Screen line -> (break_start_offset, normal_end_offset, break_hours)."""
        normal_end = self._offset_of(shift, line.get('overtime_from'))
        break_start = self._offset_of(shift, line.get('break_start'))
        break_hours = shift.break_duration or 0.0
        span = self._span_minutes(shift) / 60.0 + 1e-9
        if not 0 < normal_end <= span:
            raise UserError(_("Overtime must start after the shift starts and no later than it ends."))
        if break_start + break_hours > span:
            raise UserError(_("The unpaid break must start after the shift starts and end before it ends."))
        return round(break_start, 6), round(normal_end, 6), break_hours

    # ------------------------------------------------------------ rates
    @api.model
    def _rate_rows(self):
        """{screen key: the row the runtime picks for this company and its
        country} — `hr.overtime.config._pb_pick` (most specific row wins)."""
        company = self.env.company.sudo()
        Config = self.env['hr.overtime.config'].sudo()
        return {key: Config._pb_pick(kind, company.country_id, company) for key, kind in RATE_TYPES}

    @api.model
    def _rates_payload(self):
        rows = self._rate_rows()
        out = {}
        for key, _kind in RATE_TYPES:
            row = rows[key]
            if row:
                out[key] = self._pct(row.rate_multiplier, extra=(key == 'night'))
            else:
                out[key] = DEFAULT_RATES[key]
        return out

    @api.model
    def _effective_rates(self, policy):
        """The rates in use, with a draft's waiting changes on top."""
        rates = self._rates_payload()
        if policy and policy.state == 'draft' and policy.pb_pending_rates:
            rates.update({k: v for k, v in policy.pb_pending_rates.items() if k in rates})
        return rates

    @api.model
    def _clean_rates(self, rates):
        out = {}
        for key, _kind in RATE_TYPES:
            if key not in rates:
                continue
            value = self._int(rates.get(key), -1)
            if key == 'night':
                if not 0 <= value <= 500:
                    raise UserError(_("Night work extra is a percentage from 0 to 500."))
            elif not 100 <= value <= 1000:
                raise UserError(_("An overtime rate is a percentage from 100 to 1000."))
            out[key] = value
        return out

    @api.model
    def _write_rates(self, rates):
        """Write each rate onto THIS company's own rows; never another
        company's row or a shared one.

        The runtime picks a row by the PERSON's nationality (facts E.1), so the
        rows in use for this company's people are looked up twice: for people
        of the company's country and for people with no nationality. Each one
        that belongs to this company is written. When either is a more
        general row, ONE company row with no country is created: under
        "company + country > company > country > global" it is then the row
        for everyone in the company who has no company row of their own."""
        if not rates:
            return
        company = self.env.company.sudo()
        Config = self.env['hr.overtime.config']          # as the caller (manager ACL)
        labels = {'normal': _("Overtime"), 'rest_day': _("Rest-day overtime"),
                  'holiday': _("Public holiday overtime"), 'night': _("Night work extra")}
        countries = [company.country_id, False] if company.country_id else [False]
        for key, kind in RATE_TYPES:
            if key not in rates:
                continue
            multiplier = (100 + rates[key]) / 100.0 if key == 'night' else rates[key] / 100.0
            own, need_row = Config.browse(), False
            for country in countries:
                picked = Config.sudo()._pb_pick(kind, country, company)
                if picked and picked.company_id == company:
                    own |= Config.browse(picked.id)
                else:
                    need_row = True
            for row in own:
                if abs((row.rate_multiplier or 0.0) - multiplier) > 1e-9:
                    row.write({'rate_multiplier': multiplier})
            if need_row:
                Config.create({
                    'name': '%s — %s' % (company.name, labels[key]),
                    'overtime_type': kind,
                    'rate_multiplier': multiplier,
                    'company_id': company.id,
                    'country_id': False,
                    'requires_approval': True,
                    'time_from': 22.0 if kind == 'night' else 0.0,
                    'time_to': 6.0 if kind == 'night' else 0.0,
                })

    # ============================================================ read
    @api.model
    def rules(self):
        """Everything step 4 shows. Writes nothing."""
        self._gate_read()
        state, policy, _active = self._rules_state()
        return self._rules_payload(state, policy)

    @api.model
    def _rules_payload(self, state, policy):
        shifts, used = self._rule_shifts()
        rules_by_shift = {}
        if policy:
            for rule in policy.shift_ids:
                rules_by_shift[rule.template_id.id] = rule
        if policy:
            late = {g: self._bands_to_lines(policy.band_ids.filtered(lambda b, g=g: b.category == g))
                    for g in GROUPS}
            night = {'on': bool(policy.night_premium), 'from': self._hhmm(policy.night_start),
                     'to': self._hhmm(policy.night_end)}
            clock = {'before': policy.capture_before, 'after': policy.capture_after}
        else:
            late = {g: [dict(l) for l in DEFAULT_LATE[g]] for g in GROUPS}
            night = {'on': False, 'from': '22:00', 'to': '06:00'}
            clock = {'before': 2.0, 'after': 2.0}
        counts = self._people_policies()
        groups = {}
        for group, count in self.env['hr.employee'].sudo()._read_group(
                [('active', '=', True)] + self._company_domain(), ['pb_attendance_category'], ['__count']):
            groups[group or False] = count
        total = sum(counts.values())
        problems = []
        if state == 'advanced':
            problems.append(self._advanced_sentence())
        else:
            for group in GROUPS:
                if not late[group]:
                    problems.append(self._no_lines_sentence(group))
            if not used and not rules_by_shift:
                problems.append(_("No shift is used in a working week yet. Build a working week in step 2."))
        lines = [self._shift_payload(s, rules_by_shift.get(s.id), s.id in used) for s in shifts]
        return {
            'state': state,
            'can_edit': self._can_edit() and state in ('new', 'draft', 'revision'),
            'can_change': self._can_edit() and state == 'active',
            'policy_id': policy.id if policy else False,
            'late': late,
            'shifts': lines,
            'rates': self._effective_rates(policy),
            'rates_pending': bool(policy and policy.state == 'draft' and policy.pb_pending_rates),
            'night': night,
            'clock': clock,
            'people': {
                'total': total,
                'with_rules': counts.get(policy.id, 0) if policy else 0,
                'worker': groups.get('worker', 0),
                'manager': groups.get('manager', 0),
                'no_group': groups.get(False, 0),
            },
            'problems': problems,
            'approval': _("Overtime always needs a manager's approval before it is paid."),
        }

    @api.model
    def _no_lines_sentence(self, group):
        return (_("Managers have no late lines yet.") if group == 'manager'
                else _("Workers have no late lines yet."))

    # ============================================================ write
    @api.model
    def _gate_rules_edit(self):
        """(state, record) for a write; refuses read-only states."""
        self._gate_edit()
        state, policy, active = self._rules_state()
        if state == 'advanced':
            raise UserError(self._advanced_sentence())
        return state, policy, active

    @api.model
    def _new_policy(self):
        company = self.env.company.sudo()
        return self.env['pb.attendance.policy'].create({
            'name': _("%s attendance rules", company.name),
            'company_id': company.id,
            'tz': self._default_tz(),
            'capture_before': 2.0,
            'capture_after': 2.0,
            'band_ids': [(0, 0, b) for g in GROUPS for b in self._lines_to_bands(DEFAULT_LATE[g], g)],
        })

    @api.model
    def _ensure_shift_lines(self, policy):
        """One line for every shift used in a working week (defaults)."""
        shifts, used = self._rule_shifts()
        have = set(policy.shift_ids.mapped('template_id').ids)
        missing = [s for s in shifts if s.id in used and s.id not in have]
        if missing:
            self.env['pb.attendance.policy.shift'].create([
                dict(self._default_shift_line(s), policy_id=policy.id, template_id=s.id) for s in missing])

    @api.model
    def save_rules(self, vals):
        """Save the screen's current values (any of: late, shifts, rates, night,
        clock) onto the draft. The first save creates the draft."""
        state, policy, _active = self._gate_rules_edit()
        if state == 'active':
            raise UserError(_("These rules are in use. Press Change the rules to make a new version."))
        vals = vals if isinstance(vals, dict) else {}
        Policy = self.env['pb.attendance.policy']        # as the caller (manager)
        try:
            with self.env.cr.savepoint():
                if not policy:
                    policy = self._new_policy()
                policy = Policy.browse(policy.id)
                self._save_into(policy, vals)
                self._ensure_shift_lines(policy)
                self.env.flush_all()
        except ValidationError as e:
            self.env.invalidate_all()
            raise UserError(self._validation_sentence(e))
        self.env.invalidate_all()
        state, policy, _active = self._rules_state()
        return self._rules_payload(state, policy)

    @api.model
    def _validation_sentence(self, error):
        text = (error.args[0] if error.args else '') or ''
        if 'Normal hours' in text:
            return _("Overtime must start after the shift starts and no later than it ends.")
        if 'night' in text.lower():
            return _("Night work must start and end at different times.")
        if 'Capture' in text:
            return _("Clock-ins and clock-outs are counted up to 6 hours before or after a shift.")
        if 'positive interval' in text:
            return _("The late lines must follow on from each other with no gap.")
        return _("These rules could not be saved. Check the highlighted numbers.")

    @api.model
    def _save_into(self, policy, vals):
        write = {}
        if isinstance(vals.get('late'), dict):
            Band = self.env['pb.attendance.policy.band']
            for group in GROUPS:
                if group not in vals['late']:
                    continue
                lines = self._clean_lines(vals['late'][group])
                old = policy.band_ids.filtered(lambda b, g=group: b.category == g)
                new = self._lines_to_bands(lines, group)
                if [self._band_key(b) for b in old.sorted('minimum')] != [self._band_key(b) for b in new]:
                    old.unlink()
                    if new:
                        Band.create([dict(b, policy_id=policy.id) for b in new])
        if isinstance(vals.get('shifts'), list):
            Rule = self.env['pb.attendance.policy.shift']
            ordered, used = self._rule_shifts()
            shifts = {s.id: s for s in ordered}
            by_shift = {r.template_id.id: r for r in policy.shift_ids}
            for line in vals['shifts']:
                if not isinstance(line, dict):
                    continue
                shift = shifts.get(self._int(line.get('shift_id'), 0))
                if not shift:
                    continue
                break_start, normal_end, break_hours = self._clean_shift_line(shift, line)
                values = {'break_start_offset': break_start, 'normal_end_offset': normal_end,
                          'break_hours': break_hours}
                rule = by_shift.get(shift.id)
                if rule:
                    if any(abs((rule[k] or 0.0) - v) > 1e-6 for k, v in values.items()):
                        rule.write(values)
                elif line.get('touched') or shift.id in used:
                    # a shift outside every working week gets a line only once
                    # someone changes its times
                    Rule.create(dict(values, policy_id=policy.id, template_id=shift.id))
        if isinstance(vals.get('night'), dict):
            night = vals['night']
            if 'on' in night:
                write['night_premium'] = bool(night.get('on'))
            if night.get('from'):
                write['night_start'] = self._minutes(night['from']) / 60.0
            if night.get('to'):
                write['night_end'] = self._minutes(night['to']) / 60.0
            start = write.get('night_start', policy.night_start)
            end = write.get('night_end', policy.night_end)
            if abs(start - end) < 1e-9:
                raise UserError(_("Night work must start and end at different times."))
        if isinstance(vals.get('clock'), dict):
            for key, field in (('before', 'capture_before'), ('after', 'capture_after')):
                if key in vals['clock']:
                    try:
                        value = float(vals['clock'][key])
                    except (TypeError, ValueError):
                        value = -1
                    if not 0 <= value <= 6:
                        raise UserError(_("Clock-ins and clock-outs are counted up to 6 hours before or after a shift."))
                    write[field] = value
        write = {k: v for k, v in write.items() if policy[k] != v}
        if write:
            policy.write(write)
        if isinstance(vals.get('rates'), dict):
            rates = self._clean_rates(vals['rates'])
            live = self._rates_payload()
            pending = dict(policy.pb_pending_rates or {})
            for key, value in rates.items():
                if value == live.get(key):
                    pending.pop(key, None)
                else:
                    pending[key] = value
            if pending != (policy.pb_pending_rates or {}):
                policy.write({'pb_pending_rates': pending or False})

    @api.model
    def _band_key(self, band):
        get = band.get if isinstance(band, dict) else (lambda k, b=band: b[k])
        return (get('category'), round(get('minimum') or 0.0, 4),
                None if get('open_ended') else round(get('maximum') or 0.0, 4),
                round(get('hours') or 0.0, 4))

    # ------------------------------------------------------------ revision
    @api.model
    def change_rules(self):
        """Active -> a draft copy the screen edits; the active one keeps
        calculating until Confirm."""
        state, policy, active = self._gate_rules_edit()
        if state != 'active':
            return self.rules()
        self.env['pb.attendance.policy'].browse(active.id).copy()
        return self.rules()

    @api.model
    def discard_rules(self):
        state, policy, active = self._gate_rules_edit()
        if state != 'revision':
            raise UserError(_("There is no new version to discard."))
        self.env['pb.attendance.policy'].browse(policy.id).unlink()
        return self.rules()

    # ------------------------------------------------------------ confirm
    @api.model
    def confirm_rules(self):
        """Pressing Confirm IS the confirmation: every late line confirmed, the
        rule set activated, the old one retired, every active person of the
        company pointed at it (Worker when they have no group) and their
        future, not-yet-calculated roster rows too. One transaction; a refusal
        rolls everything back and comes out as plain sentences."""
        state, policy, active = self._gate_rules_edit()
        if state == 'active':
            return {'problems': [], 'people': 0, 'rows_updated': 0, 'retired': False,
                    'summary': _("These rules are already in use.")}
        Policy = self.env['pb.attendance.policy']
        try:
            with self.env.cr.savepoint():
                if not policy:
                    policy = self._new_policy()
                policy = Policy.browse(policy.id)
                self._ensure_shift_lines(policy)
                problems = self._activation_problems(policy)
                if problems:
                    raise _Refused(problems)
                policy.band_ids.filtered(lambda b: not b.confirmed).write({'confirmed': True})
                pending = dict(policy.pb_pending_rates or {})
                if pending:
                    policy.write({'pb_pending_rates': False})     # still a draft here
                try:
                    policy.action_activate()
                except UserError as e:
                    raise _Refused([self._activation_sentence(e)])
                retired = False
                if state == 'revision' and active:
                    Policy.browse(active.id).action_retire()
                    retired = True
                if pending:
                    self._write_rates(self._clean_rates(pending))
                people = self._point_people(policy)
                rows, skipped = self._point_rows(policy)
                self.env.flush_all()
        except _Refused as refused:
            self.env.invalidate_all()
            return {'problems': refused.problems, 'people': 0, 'rows_updated': 0, 'retired': False}
        remark = self.remark_days()
        n = people
        summary = (_("Rules confirmed for 1 person.") if n == 1
                   else _("Rules confirmed for %s people.", '{:,}'.format(n)))
        return {'problems': [], 'people': people, 'rows_updated': rows, 'rows_skipped': skipped,
                'retired': retired, 'remark': remark, 'summary': summary}

    @api.model
    def _activation_problems(self, policy):
        problems = []
        for group in GROUPS:
            bands = policy.band_ids.filtered(lambda b, g=group: b.category == g).sorted('minimum')
            if not bands:
                problems.append(self._no_lines_sentence(group))
                continue
            cursor = 0.0
            for band in bands:
                if cursor is None or abs(band.minimum - cursor) > 1e-9:
                    problems.append(_("The late lines for managers must follow on from each other with no gap.")
                                    if group == 'manager' else
                                    _("The late lines for workers must follow on from each other with no gap."))
                    cursor = 'bad'
                    break
                cursor = None if band.open_ended else band.maximum
            if cursor is not None and cursor != 'bad':
                problems.append(_("The last late line for managers must be “or more”.") if group == 'manager'
                                else _("The last late line for workers must be “or more”."))
        if not policy.shift_ids:
            problems.append(_("No shift is used in a working week yet. Build a working week in step 2."))
        for rule in policy.shift_ids:
            if not self._shift_line_ok(rule.template_id, rule.normal_end_offset, rule.break_start_offset,
                                       rule.break_hours):
                problems.append(_("The overtime and break times of “%s” no longer fit the shift. Pick new ones.",
                                  rule.template_id.name))
        return problems

    @api.model
    def _activation_sentence(self, error):
        text = (error.args[0] if error.args else '') or ''
        if 'shift rules' in text:
            return _("No shift is used in a working week yet. Build a working week in step 2.")
        if 'Confirm' in text:
            return _("Every late line needs to be confirmed. Press Confirm again.")
        if 'gaps' in text:
            return _("The late lines must follow on from each other with no gap.")
        if 'upper limit' in text:
            return _("The last late line must be “or more”.")
        return _("These rules could not be confirmed. Check the lines above.")

    @api.model
    def _point_people(self, policy):
        """Every active person of the company -> this rule set; people with no
        group -> Worker. sudo after the edit gate (HR-only fields, facts K24)."""
        ctx = {'tracking_disable': True, 'mail_notrack': True}
        emps = self.env['hr.employee'].sudo().with_context(**ctx).search(
            [('active', '=', True)] + self._company_domain())
        emps.filtered(lambda e: e.pb_attendance_policy_id != policy).write(
            {'pb_attendance_policy_id': policy.id})
        emps.filtered(lambda e: not e.pb_attendance_category).write({'pb_attendance_category': 'worker'})
        return len(emps)

    @api.model
    def _future_rows_domain(self, day=None):
        return [('company_id', '=', self.env.company.id),
                ('date', '>=', day or self._today()),
                ('state', 'in', ('draft', 'published')),
                ('pb_attendance_id', '=', False),
                '|', ('pb_calculation_status', '=', False), ('pb_calculation_status', '=', '')]

    @api.model
    def _point_rows(self, policy):
        """Future, not-yet-calculated roster rows of this company's people ->
        this rule set. Written through the ORM as the caller: no context token
        guards `pb_policy_id` on a row without generated attendance (the
        `_attendance_calc` token only fences rows that have it — excluded
        here). `_policy_scope` still applies: rows on a shared shift or whose
        local start day differs in the rules' time zone are left out."""
        Shift = self.env['hr.shift.planning'].with_context(
            tracking_disable=True, mail_notrack=True, mail_create_nolog=True)
        rows = Shift.search(self._future_rows_domain() + [('pb_policy_id', '!=', policy.id)])
        if not rows:
            return 0, 0
        zone = pytz.timezone(policy.tz)
        good, skipped = Shift.browse(), 0
        for row in rows:
            start = pytz.utc.localize(row.start_datetime).astimezone(zone)
            if (row.employee_id.company_id != row.company_id
                    or row.shift_template_id.company_id != row.company_id
                    or start.date() != row.date
                    or not row.end_datetime or row.end_datetime <= row.start_datetime
                    or row.end_datetime - row.start_datetime > timedelta(hours=24)):
                skipped += 1
                continue
            good |= row
        if not good:
            return 0, skipped
        try:
            with self.env.cr.savepoint():
                good.write({'pb_policy_id': policy.id})
                self.env.flush_all()
            return len(good), skipped
        except (UserError, ValidationError):
            self.env.invalidate_all()
        done = 0
        for row in good:
            try:
                with self.env.cr.savepoint():
                    row.write({'pb_policy_id': policy.id})
                    self.env.flush_all()
                done += 1
            except (UserError, ValidationError):
                self.env.invalidate_all()
                skipped += 1
        return done, skipped

    # ============================================================ the pay example
    @api.model
    def pay_example(self, employee_id, in_minutes, out_minutes, rules=None, day_kind='weekday'):
        """One real person's paid hours on their first working day this week,
        worked out by the real engine. `rules` = the screen's current values
        (unsaved edits included). Writes nothing."""
        self._gate_read()
        kind = DAY_KINDS.get(day_kind or 'weekday', 'weekday')
        try:
            return self._pay_example(employee_id, self._int(in_minutes, 0), self._int(out_minutes, 0),
                                     rules if isinstance(rules, dict) else None, kind)
        except UserError as e:
            return {'error': e.args[0] if e.args else _("This example cannot be worked out.")}

    @api.model
    def _example_error(self, text, fix=False, **extra):
        """`fix` names the step where the problem is put right (the panel
        shows a button to it): 'people' or 'rules'."""
        out = {'error': text, 'fix': fix}
        out.update(extra)
        return out

    @api.model
    def _pay_example(self, employee_id, in_min, out_min, rules, kind):
        emp = self.env['hr.employee'].sudo().search(
            [('id', '=', self._int(employee_id, 0)), ('active', '=', True)] + self._company_domain(), limit=1)
        if not emp:
            return self._example_error(_("This person is no longer here. Pick someone else."))
        first = (emp.name or '').split()[-1:] or ['']
        base = {'name': emp.name or '', 'first_name': first[0]}
        week = self.person_week(emp.id) or {}
        day = next((d for d in week.get('days', []) if d.get('shift_id')), None)
        if not day:
            return self._example_error(_("%s has no working week yet. Give them one in step 3.", emp.name),
                                       'people', **base)
        shift = self.env['hr.shift.template'].sudo().browse(day['shift_id'])
        group = emp.pb_attendance_category
        if not group:
            return self._example_error(
                _("%s has no late rule yet. Pick Worker or Manager for them in step 3.", emp.name), 'people', **base)
        state, policy, _active = self._rules_state()
        if state == 'advanced':
            policy = emp.pb_attendance_policy_id
            rules = None
        # step 5: the late lines, as bands, all treated as confirmed (a
        # hypothetical must never fail on "not confirmed")
        bands = []
        if rules is not None:
            late = rules.get('late') or {}
            for g in GROUPS:
                try:
                    lines = self._clean_lines(late.get(g) or [])
                except UserError as e:
                    return self._example_error(e.args[0], 'rules', **base)
                bands += self._lines_to_bands(lines, g, confirmed=True)
        elif policy:
            bands = [{'category': b.category, 'minimum': b.minimum,
                      'maximum': None if b.open_ended else b.maximum, 'hours': b.hours,
                      'confirmed': True} for b in policy.band_ids]
        else:
            for g in GROUPS:
                bands += self._lines_to_bands(DEFAULT_LATE[g], g, confirmed=True)
        for b in bands:
            if b.get('open_ended'):
                b['maximum'] = None
        # step 1: this shift's line (break and overtime start)
        rule = None
        if rules is not None:
            line = next((l for l in (rules.get('shifts') or []) if isinstance(l, dict)
                         and self._int(l.get('shift_id'), 0) == shift.id), None)
            if line:
                try:
                    rule = self._clean_shift_line(shift, line)
                except UserError as e:
                    return self._example_error(e.args[0], 'rules', **base)
        elif policy:
            stored = policy.shift_ids.filtered(lambda r: r.template_id == shift)
            if len(stored) == 1:
                rule = (stored.break_start_offset, stored.normal_end_offset, stored.break_hours)
        if not rule:
            return self._example_error(
                _("“%s” has no overtime time yet. Set it in step 4.", shift.name), 'rules', **base)
        break_start, normal_end, break_hours = rule
        # step 3: the shift window, exactly as the roster stores it
        Grid = self.env['hr.shift.planning.grid']
        tzname = (policy.tz if policy else False) or self._default_tz()
        zone = pytz.timezone(tzname)
        start_utc, end_utc = Grid._pb_shift_window(shift, fields.Date.to_date(day['date']),
                                                   Grid._pb_shift_tzname(emp))
        start = pytz.utc.localize(start_utc).astimezone(zone)
        end = pytz.utc.localize(end_utc).astimezone(zone)
        # step 4
        normal_end_dt = start + timedelta(hours=normal_end)
        breaks = [(start + timedelta(hours=break_start), start + timedelta(hours=break_start + break_hours))]
        # step 6: night intervals, as the calculation job builds them
        night_src = (rules or {}).get('night') if rules is not None else None
        if night_src is not None:
            night_on = bool(night_src.get('on'))
            try:
                n_start = self._minutes(night_src.get('from') or '22:00') / 60.0
                n_end = self._minutes(night_src.get('to') or '06:00') / 60.0
            except UserError as e:
                return self._example_error(e.args[0], 'rules', **base)
        elif policy:
            night_on, n_start, n_end = bool(policy.night_premium), policy.night_start, policy.night_end
        else:
            night_on, n_start, n_end = False, 22.0, 6.0
        night_intervals = []
        if night_on and abs(n_start - n_end) > 1e-9:
            for offset in (-1, 0, 1, 2):
                midnight = datetime.combine(start.date() + timedelta(days=offset), time.min)
                a = midnight + timedelta(hours=n_start)
                b = midnight + timedelta(hours=n_end, days=1 if n_end < n_start else 0)
                night_intervals.append((zone.localize(a, is_dst=None), zone.localize(b, is_dst=None)))
        # step 7: the punches and the engine. The calculation job only reads
        # punches inside the clock window (`_policy_calculate`: start -
        # capture_before .. end + capture_after); one outside it is ignored.
        clock = (rules or {}).get('clock') if rules is not None else None
        if isinstance(clock, dict):
            try:
                before, after = float(clock.get('before')), float(clock.get('after'))
            except (TypeError, ValueError):
                before, after = 2.0, 2.0
        elif policy:
            before, after = policy.capture_before, policy.capture_after
        else:
            before, after = 2.0, 2.0
        if in_min < -before * 60 - 1e-9:
            return self._example_error(
                _("A clock-in %(n)s min before the shift is outside the %(h)s hours the clock is read for, so it "
                  "would not count. Change “Reading the clock” or move the slider.", n=-in_min,
                  h=self._hours_text(before)), 'rules', **base)
        if out_min > after * 60 + 1e-9:
            return self._example_error(
                _("A clock-out %(n)s min after the shift is outside the %(h)s hours the clock is read for, so it "
                  "would not count. Change “Reading the clock” or move the slider.", n=out_min,
                  h=self._hours_text(after)), 'rules', **base)
        punch_in = start + timedelta(minutes=in_min)
        punch_out = end + timedelta(minutes=out_min)
        result = calculate([punch_in, punch_out], start, normal_end_dt, end, breaks, bands, group,
                           kind, night_intervals)
        rates = (rules or {}).get('rates') if rules is not None else None
        rates = rates if isinstance(rates, dict) else self._effective_rates(policy)
        rate_key = {'weekday': 'normal', 'weekend': 'rest_day', 'holiday': 'holiday'}[kind]
        out = dict(base, **{
            'clock_in': punch_in.strftime('%H:%M'),
            'clock_out': punch_out.strftime('%H:%M'),
            'shift_name': shift.name or '',
            'shift_start': start.strftime('%H:%M'),
            'shift_end': end.strftime('%H:%M'),
            'day_label': format_date(self.env, fields.Date.to_date(day['date']), date_format='EEEE'),
            'group': group,
            'day_kind': {'weekday': 'normal', 'weekend': 'rest_day', 'holiday': 'holiday'}[kind],
            'rate_percent': self._int(rates.get(rate_key), DEFAULT_RATES[rate_key]),
            'night_percent': self._int(rates.get('night'), DEFAULT_RATES['night']),
            'night_on': night_on,
            'overtime_from': (start + timedelta(hours=normal_end)).strftime('%H:%M'),
        })
        if result.get('error'):
            out['error'] = self._engine_sentence(result, in_min)
            text = (result.get('error') or '').lower()
            out['fix'] = False if ('punch' in text or 'check-out' in text) else 'rules'
            return out
        late = result.get('late_minutes') or 0.0
        out.update({
            'error': False,
            'fix': False,
            'late_minutes': int(math.ceil(late - 1e-9)) if late > 0 else 0,
            'early_minutes': max(0, -in_min),
            'taken_off_hours': round(result.get('penalty_hours') or 0.0, 4),
            'worked_hours': round(result.get('worked_hours') or 0.0, 4),
            'break_hours': round(result.get('break_hours') or 0.0, 4),
            'normal_hours': round(result.get('normal_hours') or 0.0, 4),
            'overtime_hours': round(result.get('overtime_hours') or 0.0, 4),
            'night_hours': round(result.get('night_hours') or 0.0, 4),
        })
        return out

    @api.model
    def _engine_sentence(self, result, in_min):
        """The engine's refusals, in plain words — never the raw key."""
        text = result.get('error') or ''
        if 'first and last punch' in text or 'Check-out must follow' in text:
            return _("The clock-out must come after the clock-in. Move the sliders apart.")
        if 'Normal-hours boundary' in text:
            return _("Overtime must start after the shift starts and no later than it ends.")
        if 'No single lateness band' in text:
            return _("No late line covers %s minutes late. Add a line in the late rules.",
                     int(math.ceil(result.get('late_minutes') or in_min)))
        if 'needs confirmation' in text:
            return _("A late line is not confirmed yet. Press Confirm these rules.")
        if 'do not overlap' in text:
            return _("They leave before the shift starts, so nothing is paid.")
        return _("This example cannot be worked out. Check the rules above.")

    # ============================================================ the studio around step 4
    @api.model
    def load(self, employee_id=False):
        out = super().load(employee_id)
        state, policy, _active = self._rules_state()
        out['rules'] = self._rules_payload(state, policy)
        return out

    @api.model
    def _steps(self, shifts, weeks):
        steps = super()._steps(shifts, weeks)
        state = self._rules_state()[0]
        entry = {
            'advanced': {'state': 'warn', 'text': _("More than one set of rules")},
            'active': {'state': 'done', 'text': _("Rules confirmed")},
            'revision': {'state': 'warn', 'text': _("Changes not confirmed yet")},
        }.get(state, {'state': 'todo', 'text': _("Check and confirm")})
        for step in steps:
            if step['key'] == 'rules':
                step.update(entry)
        return steps

    @api.model
    def save_shift(self, vals, shift_id=False):
        """Step 1 keeps the rules in step: a changed shift re-syncs the unpaid
        break on every DRAFT rule set of the company (an active one is never
        touched), and pulls times that no longer fit back inside the shift."""
        row = super().save_shift(vals, shift_id)
        if shift_id:
            self._resync_shift_lines(row['id'])
        return row

    @api.model
    def _resync_shift_lines(self, shift_id):
        Rule = self.env['pb.attendance.policy.shift']        # as the caller (manager)
        lines = Rule.sudo().search([('template_id', '=', shift_id), ('policy_id.state', '=', 'draft'),
                                    ('company_id', '=', self.env.company.id)])
        for line in lines:
            shift = line.template_id
            span = self._span_minutes(shift) / 60.0
            values = {'break_hours': min(shift.break_duration or 0.0, span)}
            normal_end = line.normal_end_offset if 0 < line.normal_end_offset <= span + 1e-9 else span
            break_start = line.break_start_offset
            if break_start + values['break_hours'] > span + 1e-9:
                break_start = max(0.0, (span - values['break_hours']) / 2.0)
            values.update(normal_end_offset=normal_end, break_start_offset=break_start)
            if any(abs((line[k] or 0.0) - v) > 1e-9 for k, v in values.items()):
                Rule.browse(line.id).write(values)
