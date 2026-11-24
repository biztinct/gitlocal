# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Step 6 "Time clocks" (WFSETUP P4, handover §2.2) — facade methods.

Two kinds of clock, both of THIS company only:
  * 'pc'      — `pb.clock.connector`: a Windows PC beside a clock that reads
                its database and sends the records (facts G);
  * 'machine' — `pb.clock.device` of kind terminal: a machine that calls in
                by itself. A machine that belongs to a PC (`connector.device_id`)
                is shown once, as the PC.

Health is worked out from the stored fields only (no protocol work):
  ok        heard from in the last 24 hours and no error
  quiet     connected but silent for more than 24 hours
  waiting   not set up yet (PC awaiting setup, machine not let in / never heard)
  attention the PC reported a problem — mapped to ONE plain sentence, never
            the PC's own text (it can hold a local path; `_setup_status` keeps
            it out for the same reason)
  off       access revoked / machine ignored

The setup link reuses the connector's own `_new_invitation` (manager check,
row lock, one valid invitation at a time). The link is built by the client
exactly as `pb_clock/static/setup/setup.js` does.
"""

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

QUIET_AFTER = timedelta(hours=24)


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
    def _connector_row(self, conn, now):
        error = bool((conn.last_error or '').strip())
        heard = conn.last_contact
        if conn.state == 'revoked':
            state = 'off'
        elif error:
            state = 'attention'
        elif conn.state != 'connected':
            state = 'waiting'
        elif heard and now - heard <= QUIET_AFTER:
            state = 'ok'
        else:
            state = 'quiet'
        until = conn.invitation_until if conn.invitation_until and conn.invitation_until > now else False
        device = conn.device_id
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
        }

    @api.model
    def _device_row(self, device, now):
        heard = device.last_seen_at
        if device.state == 'blocked':
            state = 'off'
        elif device.state == 'pending' or not device.allowed_at or not heard:
            state = 'waiting'
        elif now - heard <= QUIET_AFTER:
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
        }

    @api.model
    def _clock_rows(self, now=None):
        now = now or fields.Datetime.now()
        company = self.env.company
        conns = self.env['pb.clock.connector'].sudo().search(
            [('company_id', '=', company.id)], order='name, id')
        rows = [self._connector_row(c, now) for c in conns]
        if 'pb.clock.device' in self.env:
            devices = self.env['pb.clock.device'].sudo().search([
                ('company_id', '=', company.id), ('kind', '=', 'terminal'),
                ('id', 'not in', conns.mapped('device_id').ids)], order='name, id')
            rows += [self._device_row(d, now) for d in devices]
        order = {'attention': 0, 'waiting': 1, 'quiet': 2, 'ok': 3, 'off': 4}
        rows.sort(key=lambda r: (order.get(r['state'], 5), r['name'].lower(), r['key']))
        return rows

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
        return {
            'can_edit': self._can_edit(),
            'clocks': rows,
            'no_number': self._no_number(),
            'options': self._clock_options(),
            'confirmed': bool(company.pb_wfs_clocks_ok),
            'later': sum(1 for r in rows if r['state'] in ('waiting', 'quiet', 'attention')),
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
        later = sum(1 for r in self._clock_rows() if r['state'] in ('waiting', 'quiet', 'attention'))
        if later == 1:
            summary = _("Clocks confirmed. 1 clock is left to finish later.")
        elif later:
            summary = _("Clocks confirmed. %s clocks are left to finish later.", later)
        else:
            summary = _("Clocks confirmed.")
        return {'summary': summary, 'later': later}

    @api.model
    def _clocks_step(self):
        rows = self._clock_rows()
        later = sum(1 for r in rows if r['state'] in ('waiting', 'quiet', 'attention'))
        stuck = sum(1 for r in rows if r['state'] in ('waiting', 'attention'))
        if self.env.company.sudo().pb_wfs_clocks_ok:
            if later:
                return {'state': 'done', 'text': _("1 to finish later") if later == 1
                        else _("%s to finish later", later)}
            if not [r for r in rows if r['state'] != 'off']:
                return {'state': 'done', 'text': _("Confirmed without a clock")}
            return {'state': 'done', 'text': _("All connected")}
        if stuck:
            return {'state': 'warn', 'text': _("1 clock waiting for IT") if stuck == 1
                    else _("%s clocks waiting for IT", stuck)}
        return {'state': 'todo', 'text': _("Check and confirm")}
