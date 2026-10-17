# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The carry-forward watch — six months' warning, once per person per year.

WHAT WAS TRUE BEFORE. A balance that is not used by the cut-off either
disappears or doubles up into next year, and the first anybody hears about it
is in January. Nothing on this database looked at the question at all.

WHAT IS TRUE NOW. A monthly job asks one question about each kind of time off
the business has put a cap on: **as the cut-off comes round, is anybody still
holding this many days or more?** If they are, they and their manager get one
email each, and the HR team gets a number in the log. Once — a `pb.timeoff
.carry.log` row per person, per kind, per cut-off year, which is what makes
running it twice do nothing the second time.

THREE RULES THIS JOB OBEYS, all of them scar tissue.

* **A cap is a PARAMETER and it ships at zero** (R76 — a cap that is right for
  a screen is a bug in a cron). Nothing is watched until somebody says what
  "too many days" is, per kind of time off, because that number is a business
  fact this code has no way to guess.
* **A switch that is off SAYS SO** (R54). Off, the job still counts and still
  logs the number — "4 people would have been warned tonight" — so the first
  month after an install can be read rather than guessed at.
* **"Did this run already today" is not asked of `create_date`** (R214). The
  question is whether THIS cut-off year has already been warned about, asked
  once, in one query, before the loop starts.
"""

import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

#: Switches, with the default each ships with.
SWITCH_ON = 'pb_timeoff.carry_watch'             # 1 — warn; 0 — count and log
SWITCH_CUTOFF = 'pb_timeoff.carry_cutoff'        # 'MM-DD'
SWITCH_MONTHS = 'pb_timeoff.carry_warn_months'   # 6

#: How many employees one allocation read covers. `get_allocation_data` is
#: built for batches and this database holds four and a half thousand people.
_CHUNK = 200


class PbTimeoffCarryLog(models.Model):
    """One warning, so the next run knows it has already been given."""
    _name = 'pb.timeoff.carry.log'
    _description = 'Carry-forward warning'
    _order = 'cutoff_year desc, id desc'

    employee_id = fields.Many2one('hr.employee', string='Employee',
                                  required=True, ondelete='cascade',
                                  index=True)
    leave_type_id = fields.Many2one('hr.leave.type', string='Kind of time off',
                                    required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', index=True)
    cutoff_year = fields.Integer(string='Cut-off year', required=True)
    cutoff_date = fields.Date(string='Cut-off')
    days_left = fields.Float(string='Days still to take', digits=(6, 2))
    cap_days = fields.Float(string='Warned above', digits=(6, 2))
    told_manager = fields.Boolean(string="Their manager was told too")
    warned_on = fields.Datetime(string='Warned', default=fields.Datetime.now)

    #: `_sql_constraints` as a LIST is silently ignored on Odoo 19 — the
    #: constraint has to be a class attribute or the whole idempotency claim
    #: is a comment (ledger gotcha).
    _one_per_year = models.Constraint(
        'unique(employee_id, leave_type_id, cutoff_year)',
        'Somebody has already been warned about this kind of time off for '
        'this cut-off.')

    def _compute_display_name(self):
        for row in self:
            row.display_name = '%s · %s · %s' % (
                row.employee_id.name or '', row.leave_type_id.name or '',
                row.cutoff_year)


class PbTimeoffCarryWatch(models.AbstractModel):
    """The job itself. An AbstractModel so it owns no rows of its own — the
    log above is the only thing it writes."""
    _name = 'pb.timeoff.carry.watch'
    _description = 'Carry-forward watch'

    # ------------------------------------------------------------ settings
    @api.model
    def _param(self, key, default):
        raw = self.env['ir.config_parameter'].sudo().get_param(key)
        return default if raw in (None, False, '') else raw

    @api.model
    def _cutoff_for(self, today):
        """The next cut-off date, on or after today."""
        raw = str(self._param(SWITCH_CUTOFF, '12-31'))
        try:
            month, day = [int(x) for x in raw.split('-')[:2]]
            cutoff = fields.Date.to_date('%s-%02d-%02d'
                                         % (today.year, month, day))
        except (ValueError, TypeError, IndexError):
            _logger.warning(
                'pb_timeoff: "%s" is not a cut-off this reads (MM-DD), so '
                'the last day of the year is used', raw)
            cutoff = fields.Date.to_date('%s-12-31' % today.year)
        if cutoff < today:
            cutoff += relativedelta(years=1)
        return cutoff

    @api.model
    def _warn_months(self):
        try:
            return max(1, int(self._param(SWITCH_MONTHS, 6)))
        except (TypeError, ValueError):
            return 6

    @api.model
    def _switched_on(self):
        try:
            return bool(int(self._param(SWITCH_ON, 1)))
        except (TypeError, ValueError):
            return True

    # ---------------------------------------------------------------- the job
    @api.model
    def cron_carry_watch(self):
        """Public on purpose — a private `_method` cannot be called over
        JSON-RPC and is therefore untestable from anything but a test run
        (R40), and `run it now` must do exactly what the night does (R53)."""
        today = fields.Date.today()
        cutoff = self._cutoff_for(today)
        opens = cutoff - relativedelta(months=self._warn_months())
        if today < opens:
            _logger.info(
                'pb_timeoff carry watch: the cut-off is %s and the warning '
                'window opens %s, so nothing is due yet', cutoff, opens)
            return {'warned': 0, 'would_have': 0, 'window_open': False}

        types = self.env['hr.leave.type'].sudo().search(
            [('pb_carry_cap_days', '>', 0)])
        if not types:
            _logger.info('pb_timeoff carry watch: no kind of time off has a '
                         'cap set, so there is nothing to watch')
            return {'warned': 0, 'would_have': 0, 'window_open': True}

        live = self._switched_on()
        warned = would = 0
        for company in self.env['res.company'].sudo().search([]):
            try:
                with self.env.cr.savepoint():
                    done, hypothetical = self._watch_company(
                        company, types, cutoff, live)
                warned += done
                would += hypothetical
            except Exception:                               # noqa: BLE001
                # One company that cannot be read must not stop the rest —
                # and the failure is logged at WARNING with its traceback,
                # never swallowed at DEBUG (R92).
                _logger.warning(
                    'pb_timeoff carry watch: %s could not be checked',
                    company.name, exc_info=True)
        if live:
            _logger.info('pb_timeoff carry watch: %s warned before %s',
                         warned, cutoff)
        else:
            # R54 — a switch that is off and does not say so is reported as
            # broken. The number is the same number it would have acted on.
            _logger.info(
                'pb_timeoff carry watch: switched off. %s would have been '
                'warned about time off to use before %s', would, cutoff)
        return {'warned': warned, 'would_have': would, 'window_open': True,
                'cutoff': cutoff.isoformat()}

    # ------------------------------------------------------------ one company
    @api.model
    def _watch_company(self, company, types, cutoff, live):
        Alloc = self.env['hr.leave.allocation'].sudo()
        # Only people who HAVE an allocation of a watched kind can be holding
        # days of it. Asking the question of four and a half thousand people
        # to answer it about nine is the difference between a job that runs
        # and a job that times out.
        allocations = Alloc.search([
            ('state', '=', 'validate'),
            ('holiday_status_id', 'in', types.ids),
            ('employee_id.company_id', '=', company.id),
            ('employee_id.active', '=', True),
        ])
        employees = allocations.mapped('employee_id')
        if not employees:
            return 0, 0

        Log = self.env['pb.timeoff.carry.log'].sudo()
        # ONE query for what has already been warned about, before the loop
        # (R214): asking per person per pass is how an idempotent job starts
        # reporting the same work every night.
        already = {
            (row.employee_id.id, row.leave_type_id.id)
            for row in Log.search([('cutoff_year', '=', cutoff.year),
                                   ('employee_id', 'in', employees.ids)])
        }

        warned = would = 0
        for start in range(0, len(employees), _CHUNK):
            chunk = employees[start:start + _CHUNK]
            data = types.sudo().get_allocation_data(chunk, fields.Date.today())
            for employee in chunk:
                for row in data.get(employee, []):
                    # (name, figures, requires_allocation, leave_type_id)
                    if len(row) < 4:
                        continue
                    type_id = row[3]
                    leave_type = types.filtered(lambda t, i=type_id: t.id == i)
                    if not leave_type:
                        continue
                    cap = leave_type.pb_carry_cap_days
                    figures = row[1] or {}
                    left = figures.get('remaining_leaves')
                    if left is None:
                        left = figures.get('virtual_remaining_leaves') or 0.0
                    if left < cap:
                        continue
                    would += 1
                    if not live:
                        continue
                    if (employee.id, leave_type.id) in already:
                        continue
                    if self._warn(employee, leave_type, left, cap, cutoff,
                                  company):
                        already.add((employee.id, leave_type.id))
                        warned += 1
        return warned, would

    # --------------------------------------------------------------- warning
    @api.model
    def _warn(self, employee, leave_type, left, cap, cutoff, company):
        """One person, one kind of time off, one cut-off. The log row is
        written FIRST, under its own savepoint, because the row is what makes
        the job idempotent — an email that went out twice is a nuisance and a
        row that was never written is the same nuisance every night."""
        manager = employee.sudo().parent_id.user_id \
            or employee.sudo().leave_manager_id
        try:
            with self.env.cr.savepoint():
                self.env['pb.timeoff.carry.log'].sudo().create({
                    'employee_id': employee.id,
                    'leave_type_id': leave_type.id,
                    'company_id': company.id,
                    'cutoff_year': cutoff.year,
                    'cutoff_date': cutoff,
                    'days_left': left,
                    'cap_days': cap,
                    'told_manager': bool(manager),
                })
        except Exception:                                   # noqa: BLE001
            _logger.warning('pb_timeoff carry watch: %s was not logged',
                            employee.name, exc_info=True)
            return False

        template = self.env.ref('pb_timeoff.mail_carry_forward',
                                raise_if_not_found=False)
        if not template:
            return True
        context = {
            'pb_days_left': '{:g}'.format(round(left, 2)),
            'pb_cutoff': cutoff,
            'pb_type_name': leave_type.name or _('time off'),
            'pb_employee_name': employee.name or '',
        }
        for who, address in self._addresses(employee, manager):
            try:
                with self.env.cr.savepoint():
                    # R6: always pass the recipient explicitly — a template's
                    # own rendered `email_to` can reach `mail.mail` EMPTY.
                    template.sudo().with_context(
                        **dict(context, pb_to_manager=who == 'manager')
                    ).send_mail(employee.id, force_send=False,
                                email_values={'email_to': address})
            except Exception:                               # noqa: BLE001
                _logger.warning(
                    'pb_timeoff carry watch: the %s email for %s failed',
                    who, employee.name, exc_info=True)
        return True

    @api.model
    def _addresses(self, employee, manager):
        """(who, address) pairs, deduplicated. Reading the employee AS THE
        SYSTEM (R56/R104): `work_email` and `private_email` sit behind HR
        groups, so a job that ran as anybody else would report a perfectly
        good warning as a failure."""
        out = []
        seen = set()
        for who, address in (
                ('employee', employee.sudo().work_email
                 or employee.sudo().user_id.email),
                ('manager', manager.email if manager else False)):
            if address and address not in seen:
                seen.add(address)
                out.append((who, address))
        return out
