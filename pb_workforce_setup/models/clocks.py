# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Step 6 "Time clocks" (WFSETUP P4, handover §2.2) — facade methods.

Two kinds of clock, both of THIS company only:
  * 'pc'      — `pb.clock.connector`: a Windows PC beside a clock that reads
                its database and sends the records (facts G);
  * 'machine' — `pb.clock.device` of kind terminal: a machine that calls in
                by itself. A machine that belongs to a PC (`connector.device_id`)
                is shown once, as the PC.

Health is worked out from the stored fields only (no protocol work):
  ok        "Sending clock-ins": heard from recently, no error and (a PC) its
            "Send accepted records to attendance" switch is on
  held      (PC only, P6) connected and heard from recently, but that switch
            is off: "Connected, but clock-ins are switched off"
  quiet     connected but not heard from recently: "Not heard from since …"
  waiting   not set up yet (PC awaiting setup, machine not let in / never heard)
  attention the PC reported a problem — mapped to ONE plain sentence, never
            the PC's own text (it can hold a local path; `_setup_status` keeps
            it out for the same reason)
  off       access revoked / machine ignored

"Recently" is pb_clock's own rule (P6), not a number of ours:
  * a PC: the connector setup page's "Contact overdue" pill —
    `max(60, 3 x interval_minutes)` minutes (`pb_clock/static/setup/setup.js:53`);
  * a machine: the Time clocks screen's "Connected · heard …" chip — 180 s
    (`pb_clock/static/src/js/clock_lens.js:435`).

What the switch does (read in the code, P6): with it off a PC's records are
still received and kept (`pb.clock.connector.event` state `ready`), and the
late and overtime rules read those `ready` events directly
(`pb_attendance_policy/models/policy.py:298-302`); the switch turns them into
clock-ins on the attendance side (`pb.clock.punch`, legacy pairing). Switching
it on also processes every record already received (`_cron_process` picks
`ready` rows of a publishing connector). The screen says exactly that.

The setup link reuses the connector's own `_new_invitation` (manager check,
row lock, one valid invitation at a time). The link is built by the client
exactly as `pb_clock/static/setup/setup.js` does.
"""

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# pb_clock's own "heard from recently" rules (see the module docstring)
PC_OVERDUE_MIN_MINUTES = 60
PC_OVERDUE_INTERVALS = 3
MACHINE_HEARD_WITHIN = timedelta(seconds=180)
# rows that are not finished yet ("N clocks left to finish later")
LATER_STATES = ('waiting', 'quiet', 'attention', 'held')
# rows whose clock-ins reach the rules: heard from recently (switch on or off)
DELIVERING_STATES = ('ok', 'held')


class WorkforceSetupClocks(models.AbstractModel):
    _inherit = 'pb.workforce.setup'

    # ============================================================ reading
    @api.model
    def _problem_sentence(self, raw):
        """The PC's error text -> one plain sentence. The raw text never
        leaves the server."""
        text = (raw or '').lower()
        if any(k in text for k in ('re-pair', 'pair', 'token', 'unauthor', '401', 'revoked', 'installation access')):
            return _("The PC is no longer paired. Copy a new setup link for your IT person.")
        if any(k in text for k in ('mdb', 'database', 'access', 'odbc', 'file', 'path', 'locked', 'permission')):
            return _("The PC cannot read the clock's records. Ask your IT person to check that the clock program's data is where the setup said.")
        if any(k in text for k in ('timeout', 'timed out', 'connect', 'network', 'dns', 'ssl', 'certificate', 'proxy', 'http')):
            return _("The PC could not reach Payobook. Ask your IT person to check its internet connection.")
        return _("The PC reported a problem. Open the clock details to see what your IT person should check.")

    @api.model
    def _today_count(self, device, now):
        if not device:
            return 0
        lo, hi = device._local_today_bounds_utc(now)
        return self.env['pb.clock.punch'].sudo().search_count([
            ('device_id', '=', device.id), ('punch_utc', '>=', lo), ('punch_utc', '<', hi)])

    @api.model
    def _dt(self, value):
        return fields.Datetime.to_string(value) if value else False

    @api.model
    def _pc_overdue(self, conn):
        """pb_clock's "Contact overdue" span for this PC (setup.js:53)."""
        return timedelta(minutes=max(PC_OVERDUE_MIN_MINUTES,
                                     (conn.interval_minutes or 0) * PC_OVERDUE_INTERVALS))

    @api.model
    def _can_switch(self):
        """The connector's own write rule (`pb.clock.connector._manager`):
        attendance managers with write access on the model."""
        Conn = self.env['pb.clock.connector']
        return bool(self.env.user.has_group('hr_attendance.group_hr_attendance_manager')
                    and Conn.has_access('write'))

    @api.model
    def _connector_row(self, conn, now, can_switch=None):
        error = bool((conn.last_error or '').strip())
        heard = conn.last_contact
        sending = bool(conn.publish_punches)
        if conn.state == 'revoked':
            state = 'off'
        elif error:
            state = 'attention'
        elif conn.state != 'connected':
            state = 'waiting'
        elif heard and now - heard <= self._pc_overdue(conn):
            state = 'ok' if sending else 'held'
        else:
            state = 'quiet'
        until = conn.invitation_until if conn.invitation_until and conn.invitation_until > now else False
        device = conn.device_id
        if can_switch is None:
            can_switch = self._can_switch()
        return {
            'kind': 'pc',
            'id': conn.id,
            'key': 'pc-%s' % conn.id,
            'name': conn.name or '',
            'where': (device.location or '').strip() or (conn.source_group or '').strip(),
            'state': state,
            'last_heard': self._dt(heard),
            'today': self._today_count(device, now),
            'pending': max(0, conn.pending_rows or 0),
            'problem': self._problem_sentence(conn.last_error) if state == 'attention' else False,
            'invite_until': self._dt(until),
            # P6: the PC's "Send accepted records to attendance" switch
            'switch': True,
            'sending': sending,
            'can_switch': bool(can_switch and conn.state == 'connected' and not sending),
        }

    @api.model
    def _device_row(self, device, now):
        heard = device.last_seen_at
        if device.state == 'blocked':
            state = 'off'
        elif device.state == 'pending' or not device.allowed_at or not heard:
            state = 'waiting'
        elif now - heard <= MACHINE_HEARD_WITHIN:
            state = 'ok'
        else:
            state = 'quiet'
        problem = False
        if device.state == 'pending':
            problem = _("This machine is asking to connect. Let it in on the Time clocks screen.")
        return {
            'kind': 'machine',
            'id': device.id,
            'key': 'machine-%s' % device.id,
            'name': device.name or device.serial or '',
            'where': (device.location or '').strip(),
            'state': state,
            'last_heard': self._dt(heard),
            'today': self._today_count(device, now),
            'pending': 0,
            'problem': problem,
            'invite_until': False,
            # a machine that calls in has no switch: what it sends arrives
            'switch': False,
            'sending': True,
            'can_switch': False,
        }

    @api.model
    def _clock_rows(self, now=None):
        now = now or fields.Datetime.now()
        company = self.env.company
        conns = self.env['pb.clock.connector'].sudo().search(
            [('company_id', '=', company.id)], order='name, id')
        can_switch = self._can_switch()
        rows = [self._connector_row(c, now, can_switch) for c in conns]
        if 'pb.clock.device' in self.env:
            devices = self.env['pb.clock.device'].sudo().search([
                ('company_id', '=', company.id), ('kind', '=', 'terminal'),
                ('id', 'not in', conns.mapped('device_id').ids)], order='name, id')
            rows += [self._device_row(d, now) for d in devices]
        order = {'attention': 0, 'waiting': 1, 'quiet': 2, 'held': 3, 'ok': 4, 'off': 5}
        rows.sort(key=lambda r: (order.get(r['state'], 6), r['name'].lower(), r['key']))
        return rows

    @api.model
    def _clock_counts(self, rows=None):
        """How many clocks are sending, heard from, and left to finish (P6).
        `delivering`: heard from recently, switch on or off — the late and
        overtime rules read a PC's received records either way."""
        rows = self._clock_rows() if rows is None else rows
        return {
            'sending': sum(1 for r in rows if r['state'] == 'ok'),
            'held': sum(1 for r in rows if r['state'] == 'held'),
            'delivering': sum(1 for r in rows if r['state'] in DELIVERING_STATES),
            'later': sum(1 for r in rows if r['state'] in LATER_STATES),
            'stuck': sum(1 for r in rows if r['state'] in ('waiting', 'attention')),
            'live': sum(1 for r in rows if r['state'] != 'off'),
        }

    @api.model
    def _no_number(self):
        """Active people of this company with neither a clock number nor a
        badge number (sudo after the gate: HR-only field, facts K24)."""
        Emp = self.env['hr.employee'].sudo()
        domain = [('active', '=', True)] + self._company_domain() + [
            '|', ('barcode', '=', False), ('barcode', '=', '')]
        if 'pb_clock_code' in Emp._fields:
            domain += ['|', ('pb_clock_code', '=', False), ('pb_clock_code', '=', '')]
        return Emp.search_count(domain)

    @api.model
    def _clock_options(self):
        """Only the ways without a machine that exist in this build. The client
        opens each one; a missing piece drops the option."""
        Module = self.env['ir.module.module'].sudo()
        installed = set(Module.search([('state', '=', 'installed'), ('name', 'in', (
            'pb_ess_workforce', 'pb_time_hub', 'pb_mission'))]).mapped('name'))
        out = []
        if 'pb_ess_workforce' in installed and 'pb.ess.workforce' in self.env:
            on = self.env['pb.ess.workforce'].sudo().portal_clock_enabled(self.env.company)
            # the switch lives in the attendance settings, which only an
            # administrator can open: for anyone else the card informs only
            out.append({'key': 'phone', 'on': bool(on), 'can_open': self.env.user.has_group('base.group_system')})
        if {'pb_time_hub', 'pb_mission'} <= installed:
            out.append({'key': 'import', 'on': True, 'can_open': True})
            out.append({'key': 'grid', 'on': True, 'can_open': True})
        return out

    @api.model
    def clocks(self):
        """Step 6: every clock of this company and how it is doing."""
        self._gate_read()
        rows = self._clock_rows()
        company = self.env.company.sudo()
        counts = self._clock_counts(rows)
        return {
            'can_edit': self._can_edit(),
            'can_switch': self._can_switch(),
            'clocks': rows,
            'no_number': self._no_number(),
            'options': self._clock_options(),
            'confirmed': bool(company.pb_wfs_clocks_ok),
            'later': counts['later'],
            'sending': counts['sending'],
            'delivering': counts['delivering'],
        }

    # ============================================================ writing
    @api.model
    def _own_connector(self, connector_id):
        conn = self.env['pb.clock.connector'].search([
            ('id', '=', self._int(connector_id)), ('company_id', '=', self.env.company.id)], limit=1)
        if not conn:
            raise UserError(_("This clock is no longer there."))
        return conn

    @api.model
    def clock_invite(self, connector_id):
        """A fresh 5-day setup link for IT. The model's own method: manager
        check, row lock, and the link sent before stops working."""
        self._gate_edit()
        conn = self._own_connector(connector_id)
        token = conn._new_invitation()
        return {'token': token, 'until': self._dt(conn.sudo().invitation_until), 'id': conn.id,
                'name': conn.name or ''}

    @api.model
    def clock_switch_on(self, connector_id):
        """"Switch clock-ins on" (P6): the same field the clock's own screen
        writes (`publish_punches`, "Send accepted records to attendance"),
        through the same `write` — as the caller, no sudo, so the connector's
        own manager check decides. Only this connector of this company."""
        self._gate_edit()
        conn = self._own_connector(connector_id)
        if not conn.publish_punches:
            conn.write({'publish_punches': True})
        return {
            'row': self._connector_row(conn.sudo(), fields.Datetime.now()),
            'summary': _("Clock-ins are switched on for “%s”.", conn.name or ''),
        }

    @api.model
    def _clock_tz(self):
        from odoo.addons.base.models.res_partner import _tz_get
        valid = {key for key, _label in _tz_get(self)}
        company = self.env.company.sudo()
        for name in (company.resource_calendar_id.tz, company.partner_id.tz, self.env.user.tz):
            if name and name in valid:
                return name
        return 'UTC'

    @api.model
    def clock_add(self, name, where=None):
        """A new PC clock in 'awaiting setup', then its card offers the link."""
        self._gate_edit()
        name = (name or '').strip()
        if not name:
            raise UserError(_("Give the clock a name, like the place it hangs."))
        where = (where or '').strip()
        try:
            with self.env.cr.savepoint():
                conn = self.env['pb.clock.connector'].create({
                    'name': name[:120],
                    'company_id': self.env.company.id,
                    'source_group': (where or name)[:120],
                    'tz': self._clock_tz(),
                })
        except ValidationError:
            raise UserError(_("Another clock at that place reads the time differently. Use another name for the place."))
        return self._connector_row(conn.sudo(), fields.Datetime.now())

    @api.model
    def clock_details(self, connector_id):
        """The clock's existing guided page (the model's own action)."""
        self._gate_edit()
        return self._own_connector(connector_id).action_setup()

    @api.model
    def confirm_clocks(self):
        self._gate_edit()
        self.env.company.sudo().write({'pb_wfs_clocks_ok': True})
        later = self._clock_counts()['later']
        if later == 1:
            summary = _("Clocks confirmed. 1 clock is left to finish later.")
        elif later:
            summary = _("Clocks confirmed. %s clocks are left to finish later.", self._num(later))
        else:
            summary = _("Clocks confirmed.")
        return {'summary': summary, 'later': later}

    @api.model
    def _clocks_step(self):
        """Green (P6) only when the manager confirmed the step (the existing
        "continue / we do not use clocks" escape) or at least one clock is
        sending clock-ins — never for clocks that are only connected."""
        c = self._clock_counts()
        later, stuck, sending, held = c['later'], c['stuck'], c['sending'], c['held']
        if self.env.company.sudo().pb_wfs_clocks_ok:
            if later:
                return {'state': 'done', 'text': _("1 to finish later") if later == 1
                        else _("%s to finish later", later)}
            if not c['live']:
                return {'state': 'done', 'text': _("Confirmed without a clock")}
            return {'state': 'done', 'text': _("All connected")}
        if sending:
            return {'state': 'done', 'text': _("1 clock sending clock-ins") if sending == 1
                    else _("%s clocks sending clock-ins", self._num(sending))}
        if stuck:
            return {'state': 'warn', 'text': _("1 clock waiting for IT") if stuck == 1
                    else _("%s clocks waiting for IT", stuck)}
        if held:
            return {'state': 'warn', 'text': _("Clock-ins switched off")}
        return {'state': 'todo', 'text': _("Check and confirm")}
