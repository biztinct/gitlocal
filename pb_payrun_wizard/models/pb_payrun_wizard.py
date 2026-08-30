# -*- coding: utf-8 -*-
import base64
import logging
from datetime import date, datetime, time as dtime
from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class PbPayrunWizard(models.AbstractModel):
    """Backend orchestration for the guided Run Payroll cockpit.

    Real, but guarded:
      * create_and_compute() creates a *draft* hr.payslip.run and computes its
        payslips for real (fully reversible — the draft run can be deleted).
      * submit_for_approval() advances state only (no irreversible payment).
    Everything is wrapped defensively so one bad employee cannot abort the run.
    """
    _name = 'pb.payrun.wizard'
    _description = 'Payobook Run Payroll wizard orchestration'

    # ---------------- Step 1: defaults ----------------
    @api.model
    def get_defaults(self):
        today = date.today()
        start = today.replace(day=1)
        end = (start + relativedelta(months=1)) - relativedelta(days=1)
        structs = self.env['hr.payroll.structure'].search([], limit=50)
        emp_ids = self._eligible_employees()
        return {
            'name': 'Payroll %s' % start.strftime('%B %Y'),
            'date_start': start.isoformat(),
            'date_end': end.isoformat(),
            'company': self.env.company.name,
            'currency': self.env.company.currency_id.name or 'VND',
            'structures': [{'id': s.id, 'name': s.name} for s in structs],
            'eligible': len(emp_ids),
            # VALUEKIND P4 — who to include, decided per run by a person rather
            # than by a rule baked into the generator. Empty when the scheme has
            # no component marked as carrying employment status, in which case
            # the wizard shows no filter and behaves exactly as it always has.
            'statuses': self.employment_status_options(),
        }

    def _eligible_employees(self, statuses=None, employee_ids=None):
        """Who this run should produce a payslip for.

        `statuses` — employment statuses to include, as the SOURCE spells them
        ("Active", "Resigned", …). None means "no opinion", which is the
        behaviour that shipped: everyone with a running contract.

        `employee_ids` — an explicit shortlist, for the "just these few people"
        case. It is intersected with the status choice rather than overriding
        it, so a shortlist can never quietly re-admit somebody the status
        filter excluded.

        The status is read from the FEED, never from `hr.employee.active` or the
        contract state: on ABM all 152 employees are active with a running
        contract while the source reports 85 Resigned and 25 Terminated. Filtering
        on the record would be a filter that does nothing.
        """
        try:
            contracts = self.env['hr.contract'].search([('state', '=', 'open')])
            emps = contracts.mapped('employee_id')
            base = emps.ids if emps else self.env['hr.employee'].search([]).ids
        except Exception:       # noqa: BLE001 — never let this break the wizard
            base = self.env['hr.employee'].search([]).ids

        if statuses is not None:
            wanted = {str(s or '').strip() for s in statuses}
            signals = self._employee_signals()
            if signals:
                # An employee the source said nothing about keeps the benefit of
                # the doubt only when "not stated" was ticked; otherwise a person
                # missing from the feed would silently drop off the payroll.
                base = [e for e in base
                        if (signals.get(e, {}).get('status') or '') in wanted]

        if employee_ids:
            shortlist = {int(e) for e in employee_ids}
            base = [e for e in base if e in shortlist]
        return base

    def _employee_signals(self):
        """``{employee_id: {status, hours}}`` across every scheme, merged."""
        Config = self.env.get('hr.formula.config')
        if Config is None or 'employee_signal_map' not in dir(Config):
            return {}
        out = {}
        for config in Config.sudo().search([]):
            try:
                out.update(config.employee_signal_map())
            except Exception:       # noqa: BLE001
                # LOUD. A swallowed AttributeError here presents as "this scheme
                # has no employment signals", which looks exactly like a scheme
                # that genuinely has none — so the wizard silently offers no
                # status filter and every run covers everybody (C18.126).
                _logger.exception(
                    "Could not read employment signals from scheme %s (%s) — the "
                    "pay run wizard will offer no employment-status filter",
                    config.id, config.name)
        return out

    def employment_status_options(self):
        """The tick boxes the wizard offers, merged across schemes."""
        Config = self.env.get('hr.formula.config')
        if Config is None or 'employment_status_options' not in dir(Config):
            return []
        merged = {}
        for config in Config.sudo().search([]):
            try:
                rows = config.employment_status_options()
            except Exception:       # noqa: BLE001
                _logger.exception(
                    "Could not read employment statuses from scheme %s (%s)",
                    config.id, config.name)
                continue
            for row in rows:
                key = row['value']
                if key in merged:
                    merged[key]['count'] += row['count']
                    merged[key]['worked'] += row['worked']
                else:
                    merged[key] = dict(row)
        return sorted(merged.values(), key=lambda r: -r['count'])

    @api.model
    def eligible_preview(self, vals=None):
        """How many people this run would cover, and who — before it is created.

        The wizard shows this live as the tick boxes change, so nobody presses
        Run Payroll and then discovers it covered 42 people instead of 152.
        Read-only; creates nothing.
        """
        vals = vals or {}
        statuses = vals.get('statuses')
        search = (vals.get('search') or '').strip()
        emp_ids = self._eligible_employees(
            statuses=statuses, employee_ids=vals.get('employee_ids'))
        signals = self._employee_signals()

        domain = [('id', 'in', emp_ids)]
        if search:
            domain = ['&', ('id', 'in', emp_ids),
                      '|', ('name', 'ilike', search), ('barcode', 'ilike', search)]
        Employee = self.env['hr.employee'].sudo()
        total = Employee.search_count(domain)
        rows = [{
            'id': e.id,
            'name': e.display_name or '',
            'code': e.barcode or '',
            'department': e.department_id.display_name or '',
            'status': (signals.get(e.id) or {}).get('status') or '',
            'hours': (signals.get(e.id) or {}).get('hours') or 0.0,
        } for e in Employee.search(domain, order='name', limit=40)]
        return {'total': total, 'shown': len(rows), 'employees': rows,
                'statuses': self.employment_status_options()}

    # ---------------- Existing-payroll detection + cleanup ----------------
    def _period_runs(self, ds, de):
        """Runs in the active company set overlapping [ds, de] that have payslips."""
        runs = self.env['hr.payslip.run'].search([
            ('date_start', '<=', de), ('date_end', '>=', ds),
            ('company_id', 'in', self.env.companies.ids)
        ]) if 'company_id' in self.env['hr.payslip.run']._fields else \
            self.env['hr.payslip.run'].search([('date_start', '<=', de), ('date_end', '>=', ds)])
        return runs.filtered(lambda r: r.slip_ids)

    # ---------------- Payslips this period already has, outside any run ----------------
    def _loose_slips(self, ds, de):
        """Computed payslips for exactly this period that belong to no pay run.

        An import batch produces payslips and groups them in its own run; delete
        that run from the list view and the payslips are left behind — the
        many2one is `set null`, so the work survives but nothing on any screen
        points at it any more. ABM June 2026 had 152 such payslips carrying
        12,160 computed lines while the Run Payroll wizard, which cannot see
        them, built a second, parallel, EMPTY June alongside.

        Deliberately narrow, because these get adopted into a run without
        asking: the dates must be the run's own, the payslip must still be a
        draft, and it must already have computed lines. Anything looser and this
        would sweep up an unrelated payslip somebody was in the middle of.
        """
        Slip = self.env['hr.payslip']
        domain = [
            ('payslip_run_id', '=', False),
            ('date_from', '=', ds), ('date_to', '=', de),
            ('state', '=', 'draft'),
        ]
        if 'company_id' in Slip._fields:
            domain.append(('company_id', 'in', self.env.companies.ids))
        return Slip.sudo().search(domain).filtered(lambda s: s.line_ids)

    def _adopt_loose_slips(self, run, ds, de):
        """Move this period's orphaned payslips into the run being built.

        Non-destructive by construction — it only claims payslips no run owns —
        and it is what stops the wizard from computing a second payroll on top
        of one that already exists. Nothing is recomputed: the numbers a batch
        produced are the numbers the run shows.
        """
        slips = self._loose_slips(ds, de)
        if slips:
            # Link them through the RUN's own one2many rather than by writing
            # the payslip's many2one. Both move the payslip; only this one tells
            # the run that `slip_ids` changed, and the run's KPI band is a
            # STORED field computed from `slip_ids` that a run created seconds
            # ago has already computed — over an empty list. Write it the other
            # way round and the pay run goes on showing the very 0.00 this
            # exists to repair.
            run.sudo().write({'slip_ids': [(4, sid) for sid in slips.ids]})
            _logger.info(
                "Payrun wizard: adopted %s existing payslip(s) for %s → %s into "
                "run %s instead of computing a parallel set.",
                len(slips), ds, de, run.id)
        return slips

    def _july_period(self, ds):
        year = (ds or '2026-01-01')[:4]
        return {'name': 'Payroll July %s' % year,
                'date_start': '%s-07-01' % year, 'date_end': '%s-07-31' % year}

    def _clean_period(self, runs):
        """Remove a period's generated artefacts: payslips, journal moves, formula
        computation logs and the runs themselves (fully reversible demo cleanup)."""
        if not runs:
            return 0
        slips = runs.mapped('slip_ids')
        moves = slips.mapped('move_id') if 'move_id' in slips._fields else self.env['account.move']
        for s in slips:
            if s.state not in ('draft', 'cancel'):
                s.state = 'cancel'
        if moves:
            posted = moves.filtered(lambda m: m.state == 'posted')
            if posted:
                posted.button_draft()
            moves.with_context(force_delete=True).unlink()
        fcols = {'formula_computation_log', 'formula_computed_values', 'formula_input_values'}
        common = fcols & set(slips._fields)
        if common and slips:
            slips.write({c: False for c in common})
        n = len(slips)
        slips.unlink()
        # the run state is fully sealed (pb_payruns); this pre-unlink reset is
        # sanctioned cleanup — the unlink right after still runs as the real
        # user, so the caller's own rights gate the whole path
        runs.sudo().write({'state': 'draft'})
        runs.unlink()
        return n

    # ---------------- Step 2: create + compute ----------------
    @api.model
    def create_and_compute(self, vals):
        Run = self.env['hr.payslip.run']
        Slip = self.env['hr.payslip']
        name = vals.get('name') or 'Payroll run'
        ds = vals.get('date_start')
        de = vals.get('date_end')
        force_clean = vals.get('force_clean')

        # Guard: if payroll already exists for this period, ask before overwriting.
        existing = self._period_runs(ds, de)
        if existing and not force_clean:
            locked = any(getattr(r, 'locked', False) for r in existing)
            if locked:
                return {
                    'needs_confirmation': True, 'kind': 'historical',
                    'message': "Historical payroll runs are locked. Would you like to "
                               "clean July’s payroll data and rerun July payroll?",
                    'july': self._july_period(ds),
                }
            return {
                'needs_confirmation': True, 'kind': 'exists',
                'message': "This month’s payroll already exists. Would you like to "
                           "clear existing payroll data and run payroll again?",
            }
        if force_clean and existing:
            self._clean_period(existing)

        run = Run.create({'name': name, 'date_start': ds, 'date_end': de})

        adopted = self._adopt_loose_slips(run, ds, de)      # see prepare_run
        emp_ids = [e for e in self._eligible_employees()
                   if e not in set(adopted.mapped('employee_id').ids)]
        exceptions = []
        created = Slip
        for emp in self.env['hr.employee'].browse(emp_ids):
            try:
                oc = Slip.onchange_employee_id(ds, de, emp.id, contract_id=False)
                v = oc.get('value', {})
                if not v.get('contract_id'):
                    exceptions.append({
                        'emp': emp.name,
                        'why': self._no_contract_reason(emp, ds, de)})
                    continue
                slip = Slip.create({
                    'employee_id': emp.id,
                    'name': v.get('name') or ('%s - %s' % (emp.name, name)),
                    'struct_id': v.get('struct_id'),
                    'contract_id': v.get('contract_id'),
                    'payslip_run_id': run.id,
                    'input_line_ids': [(0, 0, x) for x in (v.get('input_line_ids') or [])],
                    'worked_days_line_ids': [(0, 0, x) for x in (v.get('worked_days_line_ids') or [])],
                    'date_from': ds,
                    'date_to': de,
                    'company_id': emp.company_id.id,
                })
                created += slip
            except Exception as e:
                _logger.warning("Payrun wizard: skip %s: %s", emp.name, e)
                exceptions.append({'emp': emp.name, 'why': 'Generation error'})

        # compute each slip independently so one failure doesn't roll back all
        computed = 0
        for slip in created:
            try:
                slip.compute_sheet()
            except (AccessError, UserError) as e:
                _logger.warning("Payrun wizard: compute refused for %s: %s",
                                slip.employee_id.name, e)
                exceptions.append({'emp': slip.employee_id.name, 'why': str(e)})
                continue
            except Exception as e:
                _logger.exception("Payrun wizard: compute fail %s: %s",
                                  slip.employee_id.name, e)
                exceptions.append({'emp': slip.employee_id.name, 'why': 'Compute error'})
                continue
            if not slip.line_ids:
                exceptions.append({
                    'emp': slip.employee_id.name,
                    'why': 'Computed no pay components — neither a salary '
                           'structure nor a payroll scheme applies to this '
                           'employee for this period',
                })
                continue
            computed += 1

        summary = self.get_summary(run.id)
        summary['exceptions'] = exceptions
        summary['computed'] = computed
        summary['adopted'] = len(adopted)
        return summary

    # ---------------- Step 2 (chunked): prepare + compute in batches ----------------
    # The single create_and_compute() above blocks for the whole run (900 slips),
    # leaving the UI on an indeterminate spinner. prepare_run() + compute_batch()
    # let the OWL wizard drive the work in chunks, showing a determinate progress
    # bar and keeping each RPC bounded (and each batch commits on its own).
    @api.model
    # NOTE: there is deliberately NO scheme pre-flight here. `prepare_run`
    # cannot know whether a run will strand: an employee whose contract carries
    # a salary structure computes through the structure engine and needs no
    # scheme at all, and the eligible set is computed by the CLIENT in chunks
    # after this returns. A guard here refused runs that would have worked.
    # The diagnosis belongs where the failure actually happens —
    # `hr.payslip.compute_sheet` names the scheme and the state that blocks it,
    # and every refusal lands in this wizard's own exceptions list.

    def prepare_run(self, vals):
        """Guard existing payroll, (optionally) clean it, create the draft run and
        return the list of eligible employees for the client to compute in chunks."""
        name = vals.get('name') or 'Payroll run'
        ds = vals.get('date_start')
        de = vals.get('date_end')
        force_clean = vals.get('force_clean')

        existing = self._period_runs(ds, de)
        if existing and not force_clean:
            locked = any(getattr(r, 'locked', False) for r in existing)
            if locked:
                return {
                    'needs_confirmation': True, 'kind': 'historical',
                    'message': "Historical payroll runs are locked. Would you like to "
                               "clean July’s payroll data and rerun July payroll?",
                    'july': self._july_period(ds),
                }
            return {
                'needs_confirmation': True, 'kind': 'exists',
                'message': "This month’s payroll already exists. Would you like to "
                           "clear existing payroll data and run payroll again?",
            }
        # Run the mutations as sudo: on the shared demo the acting user can create
        # and compute payslips but not *unlink* them (record rules), so cleaning a
        # previous run to re-run would raise AccessError. The wizard only ever
        # produces a reversible DRAFT run, and the demo is explicitly shared /
        # overwritable, so elevating these data operations is safe & intended.
        if force_clean and existing:
            self.sudo()._clean_period(existing.sudo())

        run = self.env['hr.payslip.run'].sudo().create({'name': name, 'date_start': ds, 'date_end': de})

        # Claim the period's existing payslips before computing anything, and
        # take their employees off the list — computing them again would put two
        # payslips on one person for one month, which is the pay-run shape of the
        # duplicate this system already refuses everywhere else.
        adopted = self._adopt_loose_slips(run, ds, de)
        emp_ids = [e for e in self._eligible_employees(
                       statuses=vals.get('statuses'),
                       employee_ids=vals.get('employee_ids'))
                   if e not in set(adopted.mapped('employee_id').ids)]
        payload = {
            'run_id': run.id, 'name': name,
            'date_start': ds, 'date_end': de,
            'division': vals.get('division'),   # passed back to compute_batch
            'emp_ids': emp_ids, 'total': len(emp_ids),
            'adopted': len(adopted),
        }
        # NETROLE P3 — the scheme wanted this month's spreadsheet and the user,
        # looking at the list of components that would run without it, chose to
        # go on anyway. WHICH components those are does not belong in a log:
        # the summary has to be able to name them, so they ride back here.
        # Additive key; every existing caller (pb_demo's override included) is
        # unaffected by its presence or absence.
        if vals.get('spreadsheet_skipped'):
            payload['skipped_components'] = self._skipped_component_codes(vals)
        return payload

    @api.model
    def compute_batch(self, payload):
        """Create + compute payslips for one chunk of employees. `payload` carries
        {run_id, name, date_start, date_end, division, emp_ids}. Returns the count
        computed and any exceptions so the client can accumulate progress.
        (pb_demo overrides this to chunk the division-scoped formula compute.)"""
        run_id = payload['run_id']
        name = payload.get('name')
        ds = payload.get('date_start')
        de = payload.get('date_end')
        emp_ids = payload.get('emp_ids') or []
        # sudo: see prepare_run — demo users may lack create/unlink on payslips.
        Slip = self.env['hr.payslip'].sudo()
        exceptions = []
        created = Slip.browse()
        # Whoever is already in this run for this month keeps the payslip they
        # have. Chunks are retried by the client on a dropped connection, and a
        # retry must not be how somebody gets paid twice.
        already = set(Slip.search([
            ('payslip_run_id', '=', run_id), ('employee_id', 'in', emp_ids),
        ]).mapped('employee_id').ids)
        for emp in self.env['hr.employee'].sudo().browse(emp_ids):
            if emp.id in already:
                continue
            try:
                oc = Slip.onchange_employee_id(ds, de, emp.id, contract_id=False)
                v = oc.get('value', {})
                if not v.get('contract_id'):
                    exceptions.append({
                        'emp': emp.name,
                        'why': self._no_contract_reason(emp, ds, de)})
                    continue
                slip = Slip.create({
                    'employee_id': emp.id,
                    'name': v.get('name') or ('%s - %s' % (emp.name, name)),
                    'struct_id': v.get('struct_id'),
                    'contract_id': v.get('contract_id'),
                    'payslip_run_id': run_id,
                    'input_line_ids': [(0, 0, x) for x in (v.get('input_line_ids') or [])],
                    'worked_days_line_ids': [(0, 0, x) for x in (v.get('worked_days_line_ids') or [])],
                    'date_from': ds,
                    'date_to': de,
                    'company_id': emp.company_id.id,
                })
                created += slip
            except Exception as e:
                _logger.warning("Payrun wizard: skip %s: %s", emp.name, e)
                exceptions.append({'emp': emp.name, 'why': 'Generation error'})

        # A shared salary-rule cache across this chunk avoids the per-rule N+1
        # lookup in _create_payslip_lines_from_formulas (see hr_payslip_formula).
        computed = 0
        rule_cache = {}
        for slip in created:
            try:
                slip.with_context(pb_salary_rule_cache=rule_cache).compute_sheet()
            except (AccessError, UserError) as e:
                # A refusal states its own reason; passing it on is the whole
                # difference between a run that reports 146 employees and 0.00
                # and one that says what went wrong for each of them.
                _logger.warning("Payrun wizard: compute refused for %s: %s",
                                slip.employee_id.name, e)
                exceptions.append({'emp': slip.employee_id.name, 'why': str(e)})
                continue
            except Exception as e:
                _logger.exception("Payrun wizard: compute fail %s: %s",
                                  slip.employee_id.name, e)
                exceptions.append({'emp': slip.employee_id.name, 'why': 'Compute error'})
                continue
            if not slip.line_ids:
                # It did not raise and it produced nothing. Silence here is what
                # a whole month of zeros looks like from the outside.
                exceptions.append({
                    'emp': slip.employee_id.name,
                    'why': 'Computed no pay components — neither a salary '
                           'structure nor a payroll scheme applies to this '
                           'employee for this period',
                })
                continue
            computed += 1

        return {'computed': computed, 'exceptions': exceptions}

    # ==================================================================
    # NETROLE Phase 3 — the month's spreadsheet
    #
    # A scheme can say, component by component, "this one reads a spreadsheet
    # column" (`hr.formula.rule.source` rows with `kind='excel'`). The Run
    # Payroll wizard never asked for a file, and the batchless compute path has
    # no spreadsheet branch — so every one of those components quietly fell back
    # to the contract or to a default, and no screen said a file had been
    # expected. On ABM that is 26 components of a 2026 payroll.
    #
    # THE BATCH IS THE SPREADSHEET PATH, AND THERE IS ONLY ONE OF IT. Nothing
    # here re-implements reading a pay file: `attach_spreadsheet` builds the
    # very `hr.payroll.import.batch` the Import cockpit builds, points it at the
    # run that already exists, and drives load → match → validate → process.
    # `_get_formula_input_values` is deliberately untouched.
    # ==================================================================
    # ---------------- Freshening the feed before anything is computed --------
    def _no_contract_reason(self, employee, ds, de):
        """Why this person has no contract running in THIS period.

        "No running contract" was true and unhelpful: on the reference tenant
        every one of the six people it named had an open contract — starting in
        July or August, over a June pay run. The reader cannot tell that from
        the message and goes looking for missing contracts that are all there.
        """
        contracts = self.env['hr.contract'].sudo().search(
            [('employee_id', '=', employee.id)], order='date_start desc')
        if not contracts:
            return _("No contract at all — this employee has never had one.")
        running = contracts.filtered(lambda c: c.state == 'open')
        if not running:
            return _("No running contract — %(n)s contract(s) exist but none is "
                     "in the Running state.", n=len(contracts))
        later = running.filtered(lambda c: c.date_start and str(c.date_start) > str(de))
        if later:
            return _("Not employed yet in this period — contract starts "
                     "%(d)s.", d=later[-1].date_start)
        ended = running.filtered(
            lambda c: c.date_end and str(c.date_end) < str(ds))
        if ended:
            return _("Contract ended %(d)s, before this period.",
                     d=max(ended.mapped('date_end')))
        return _("No contract running between %(a)s and %(b)s.", a=ds, b=de)

    def _payrun_sync_plan(self, vals=None):
        """One step per FEED this scheme reads — not per kind of data.

        Per-kind was wrong twice over. `action_pull_data` handles only
        employee / salary / dependent / attendance / leave, so a scheme reading
        a `custom` feed (ABM's Overtime requests — six components) asked for a
        pull that had no branch and silently fetched nothing. And a connector
        can have SEVERAL feeds of one kind — Zoho has two attendance feeds and
        two custom ones — so even where a branch exists, the kind does not say
        which feed the person mapped.

        `action_pull_endpoint` is already endpoint-scoped and says so in its own
        docstring. Building the plan from the endpoints the wires point at is
        what makes the promise true: everything you map is what gets synced,
        and nothing else is.
        """
        vals = vals or {}
        Config = self.env.get('hr.formula.config')
        Mapping = self.env.get('hr.integration.field.mapping')
        if Config is None or Mapping is None:
            return []
        domain = [('state', '!=', 'archived')]
        if 'company_id' in Config._fields and self.env.companies:
            domain += ['|', ('company_id', '=', False),
                       ('company_id', 'in', self.env.companies.ids)]
        rules = Config.sudo().search(domain).mapped('rule_ids')
        if not rules:
            return []
        wires = Mapping.sudo().search([('target_rule_id', 'in', rules.ids)])

        plan, seen = [], set()
        for wire in wires:
            connector = wire.connector_id
            endpoint = wire.endpoint_id if 'endpoint_id' in wire._fields else None
            if not connector or not connector.active or not endpoint:
                continue                     # `_unroutable_wires` reports these
            if endpoint.id in seen:
                continue
            seen.add(endpoint.id)
            # A feed that cannot run is not a step. It is reported instead, so
            # nobody waits on a spinner for a fetch that was never possible.
            blocked = ''
            if not endpoint.active:
                blocked = _("this feed is switched off")
            elif (endpoint.operation or 'catalog_only') == 'catalog_only':
                blocked = _("this feed is catalogued for reference only and has "
                            "no handler that can fetch it")
            elif connector.connector_type == 'zoho' and not endpoint.path:
                blocked = _("this feed has no path set")
            plan.append({
                'connector_id': connector.id,
                'connector': connector.display_name or '',
                'endpoint_id': endpoint.id,
                'data_type': endpoint.data_type or '',
                'blocked': blocked,
                'label': _("%(sys)s — %(feed)s",
                           sys=connector.display_name or '',
                           feed=endpoint.name or self._sync_kind_label(
                               endpoint.data_type)),
            })
        return plan

    @api.model
    def _sync_kind_label(self, data_type):
        """The words a person reads for a kind of feed data."""
        return {
            'employee': _("employee records"),
            'salary': _("salary data"),
            'attendance': _("attendance"),
            'leave': _("leave"),
            'dependent': _("dependants"),
            'custom': _("timesheets and overtime"),
        }.get(data_type, data_type or _("data"))

    def _unroutable_wires(self, vals=None):
        """Components wired to a feed field that names no endpoint.

        Nothing can pull them, so they fall to their default every run — and
        the run reports success. Surfaced as an exception rather than a log
        line nobody reads.
        """
        Mapping = self.env.get('hr.integration.field.mapping')
        Config = self.env.get('hr.formula.config')
        if Mapping is None or Config is None or 'endpoint_id' not in Mapping._fields:
            return []
        domain = [('state', '!=', 'archived')]
        if 'company_id' in Config._fields and self.env.companies:
            domain += ['|', ('company_id', '=', False),
                       ('company_id', 'in', self.env.companies.ids)]
        rules = Config.sudo().search(domain).mapped('rule_ids')
        if not rules:
            return []
        rows = []
        for wire in Mapping.sudo().search([('target_rule_id', 'in', rules.ids),
                                           ('endpoint_id', '=', False)]):
            rule = wire.target_rule_id
            # A component fed by ANOTHER, complete wire is fine — only the ones
            # left with no route at all are worth a person's attention.
            siblings = Mapping.sudo().search_count([
                ('target_rule_id', '=', rule.id), ('endpoint_id', '!=', False)])
            if siblings:
                continue
            rows.append({
                'emp': rule.name or rule.code or '',
                'why': _("Wired to '%(field)s' but no feed is named, so nothing "
                         "can fetch it and it falls back to its default value "
                         "every run. Set the feed on this mapping.",
                         field=wire.source_field or ''),
            })
        return rows

    @api.model
    def sync_plan(self, vals=None):
        """What the wizard is about to sync, so it can say so while it does.

        The pull was one blocking call behind a spinner reading "Creating run
        and computing payslips…", which is not what it was doing and gave no
        sense of how long it would take. Split into steps, the wizard can name
        each one and count them.
        """
        vals = vals or {}
        # Returned here, and added to the run's exceptions ONCE by the client:
        # `compute_batch` runs per chunk of employees, and a per-run advisory
        # appended there is a per-run advisory reported N times (the workforce
        # close notes did exactly that).
        return {'steps': self._payrun_sync_plan(vals),
                'unroutable': self._unroutable_wires(vals)}

    @api.model
    def sync_step(self, step, vals=None):
        """Pull ONE feed from ONE connected system, for the period.

        Never raises. A feed that cannot be reached is a thing the person
        running payroll needs to SEE and then decide about — a connector that
        is down must not make payroll impossible, because the file and the
        contract fallbacks may well be enough.
        """
        vals = vals or {}
        step = step or {}
        out = {'label': step.get('label') or '', 'pulled': 0, 'error': ''}
        if step.get('blocked'):
            out['error'] = _("%(label)s was not synced — %(why)s.",
                             label=out['label'], why=step['blocked'])
            return out
        connector = self.env['hr.integration.connector'].sudo().browse(
            int(step.get('connector_id') or 0)).exists()
        endpoint_id = int(step.get('endpoint_id') or 0)
        if not connector or not endpoint_id:
            return out
        # RD55 — DON'T FETCH WHAT IS ALREADY HERE.
        #
        # The scheduled fetch (RD49) was supposed to take the wait out of a pay
        # run, and on its own it did not: the wizard rebuilt its plan from every
        # mapped feed and pulled all of them regardless, so the owner still
        # watched "Syncing Zoho People…" after the data had been fetched
        # overnight. Fetching early only helps if something declines to fetch
        # again.
        #
        # FRESH means: this feed already holds data for THIS period, pulled
        # since the period ended. Not "pulled recently" — a pull from the middle
        # of the month saw a month that had not finished, and re-reading a
        # complete month is cheap while trusting an incomplete one is not.
        fresh = self._rd55_feed_is_fresh(connector, endpoint_id, vals)
        if fresh:
            out['skipped'] = True
            out['pulled'] = fresh
            out['note'] = _(
                "%(label)s was already fetched — using that.",
                label=out['label'])
            return out
        try:
            connector.action_pull_endpoint(
                endpoint_id,
                period_from=vals.get('date_start'),
                period_to=vals.get('date_end'),
                triggered_by='manual')
            connector.invalidate_recordset()
            out['pulled'] = connector.total_synced_records or 0
        except Exception as exc:        # noqa: BLE001 — see docstring
            _logger.exception("Payrun wizard: could not pull %s before payroll",
                              out['label'])
            out['error'] = _("%(label)s could not be reached: %(why)s",
                             label=out['label'], why=exc)
        return out

    @api.model
    def update_records_from_feed(self, vals=None):
        """RD56 — bring employee and contract records into step, from the feed.

        The pay run with no spreadsheet wrote nothing to any record, so a
        tenant running payroll from a connected system watched its contracts
        drift further from it every month while the payslips stayed right: 152
        contracts all reading one person's salary while 29 different salaries
        were being paid.

        ONE BUTTON, NO SECOND CHOICE. The spreadsheet path offers "Update
        Payobook" or "This run only" because a FILE can legitimately be a
        one-off — a bonus, a correction. A connected system is the source of
        truth by definition, so there is nothing to decide.

        It writes records and creates NO payslips. The run is computed
        afterwards exactly as before, so pressing this changes what the records
        say and never what the wizard does next.

        Reuses the connector's own refresh, which reuses the one writeback
        there is (`action_process` with `create_payslips=False`) — the mapping
        priority, the bank assembly and the per-row error isolation all come
        with it rather than being written a second time.
        """
        vals = vals or {}
        Connector = self.env.get('hr.integration.connector')
        if Connector is None:
            return {'ok': False, 'msg': _("No connected system is set up.")}
        config = self._payrun_config(vals)
        connector = config.connector_id if config else None
        if not connector:
            return {'ok': False, 'msg': _(
                "This payroll scheme is not linked to a connected system, so "
                "there is nothing to bring the records into step with.")}
        date_start = vals.get('date_start')
        date_end = vals.get('date_end')
        try:
            connector.sudo()._rd54_writeback_from_store(date_start, date_end)
        except Exception as exc:        # noqa: BLE001 — never break the step
            _logger.exception("RD56: record update failed before payroll")
            return {'ok': False, 'msg': _(
                "The records could not be updated: %s") % exc}
        connector.invalidate_recordset()
        return {'ok': True,
                'msg': connector.sudo().cron_writeback_last_result or _(
                    "Records are up to date.")}

    @api.model
    def _payrun_config(self, vals=None):
        """The scheme this run is about, or an empty recordset."""
        vals = vals or {}
        Config = self.env.get('hr.formula.config')
        if Config is None:
            return Config
        cfg_id = vals.get('config_id') or vals.get('formula_config_id')
        if cfg_id:
            found = Config.sudo().browse(int(cfg_id)).exists()
            if found:
                return found
        domain = [('state', '=', 'active'), ('connector_id', '!=', False)]
        if 'company_id' in Config._fields and self.env.companies:
            domain += ['|', ('company_id', '=', False),
                       ('company_id', 'in', self.env.companies.ids)]
        return Config.sudo().search(domain, limit=1)

    @api.model
    def _rd55_feed_is_fresh(self, connector, endpoint_id, vals):
        """How many rows this feed already holds for the period, if it is safe
        to reuse them — otherwise 0.

        THE TEST IS THE PERIOD, NOT THE CLOCK. A pull made while the month was
        still running saw an unfinished month, so "pulled two hours ago" is not
        a reason to trust it. The data must have arrived AFTER the period ended.

        Never raises and answers 0 on any doubt: a wasted fetch costs a minute,
        a skipped one costs a pay run computed on last month's numbers.
        """
        try:
            Store = self.env.get('hr.api.data.store')
            if Store is None:
                return 0
            date_end = vals.get('date_end')
            if not date_end:
                return 0
            after = fields.Date.to_date(date_end)
            if not after:
                return 0
            return Store.sudo().search_count([
                ('connector_id', '=', connector.id),
                ('endpoint_id', '=', endpoint_id),
                ('create_date', '>', fields.Datetime.to_datetime(
                    datetime.combine(after, dtime.min))),
                ('state', 'not in', ('archived', 'error')),
            ])
        except Exception:       # noqa: BLE001 — see docstring
            _logger.warning("RD55: could not judge feed freshness; fetching.",
                            exc_info=True)
            return 0

    def _spreadsheet_configs(self):
        """Every scheme in view whose components declare a spreadsheet column.

        Returns `[{'config': record, 'components': [{code, name, key}]}]`,
        schemes that are live first and then the one waiting on the most
        columns. A source row with a blank key names nothing and is not a
        reason to ask anybody for a file, so it is dropped here rather than
        surfacing as a component that can never be fed.

        Read-only, and `sudo` on purpose: this decides whether a STEP appears.
        A payroll officer who has no read access to the scheme's source rows
        must still be asked for the file their scheme is waiting on, and the
        alternative — an officer silently getting the old, file-less behaviour
        — is the exact defect this phase exists to close.
        """
        # No formula engine on this database means no scheme can bind a
        # component to a column, so there is nothing to ask anybody for.
        if 'hr.formula.rule.source' not in self.env:
            return []
        Config = self.env['hr.formula.config'].sudo()
        domain = [('state', '!=', 'archived')]
        if 'company_id' in Config._fields and self.env.companies:
            domain += ['|', ('company_id', '=', False),
                       ('company_id', 'in', self.env.companies.ids)]
        configs = Config.search(domain)
        if not configs:
            return []
        sources = self.env['hr.formula.rule.source'].sudo().search([
            ('kind', '=', 'excel'), ('rule_id.config_id', 'in', configs.ids)])
        by_config = {}
        for src in sources:
            key = (src.key or '').strip()
            if not key:
                continue
            rule = src.rule_id
            by_config.setdefault(rule.config_id.id, []).append({
                'code': rule.code or '',
                'name': rule.name or rule.code or '',
                'key': key,
            })
        entries = []
        for cfg in configs:
            components = by_config.get(cfg.id)
            if not components:
                continue
            components.sort(key=lambda c: (c['name'] or '').lower())
            entries.append({'config': cfg, 'components': components})
        entries.sort(key=lambda e: (e['config'].state != 'active',
                                    -len(e['components']), e['config'].id))
        return entries

    def _last_spreadsheet_name(self, config):
        """What the last file loaded for this scheme was called, or ''.

        Purely so the step can say "last time this was `ABM June.xlsx`" — a
        hint, never a filter on what may be uploaded.
        """
        try:
            batch = self.env['hr.payroll.import.batch'].sudo().search([
                ('formula_config_id', '=', config.id),
                ('source_type', '=', 'excel'),
                ('import_filename', '!=', False),
            ], order='id desc', limit=1)
            return batch.import_filename or ''
        except Exception:       # noqa: BLE001 — a hint must never break a step
            return ''

    @api.model
    def spreadsheet_gate(self, vals=None):
        """Does this payroll want a spreadsheet before it is computed?

        `{'wanted': False}` means the wizard runs exactly as it did before —
        which is every database where no scheme binds a component to a column,
        the demo world included. Never raises: a gate that blew up would take
        the whole Run Payroll screen with it, so any doubt at all is answered
        with "no file wanted" and a loud log line (C7 — the failure is visible
        to whoever reads the log, and the run still happens).
        """
        try:
            entries = self._spreadsheet_configs()
        except Exception:       # noqa: BLE001
            _logger.exception(
                "Payrun wizard: could not read the schemes' spreadsheet "
                "columns; the pay-data step is hidden for this run.")
            return {'wanted': False}
        if not entries:
            return {'wanted': False}
        chosen = entries[0]
        cfg = chosen['config']
        return {
            'wanted': True,
            'config_id': cfg.id,
            'config_name': cfg.display_name or cfg.name or '',
            'components': chosen['components'],
            'filename_hint': self._last_spreadsheet_name(cfg),
            # More than one scheme can be waiting on a file. Naming them lets
            # the step ask which one rather than picking silently.
            'choices': [{'id': e['config'].id,
                         'name': e['config'].display_name or e['config'].name or '',
                         'count': len(e['components'])} for e in entries],
        }

    def _skipped_component_codes(self, vals=None):
        """The components that will run on fallback values because no file came."""
        gate = self.spreadsheet_gate(vals or {})
        if not gate.get('wanted'):
            return []
        wanted_id = (vals or {}).get('spreadsheet_config_id') or gate.get('config_id')
        for entry in self._spreadsheet_configs():
            if entry['config'].id == wanted_id:
                return [c['code'] for c in entry['components']]
        return [c['code'] for c in gate.get('components') or []]

    def _coverage(self, batch, components, keys):
        """Which of `components` a payload carrying `keys` actually feeds.

        `hr.payroll.import.batch._lookup_in_blob` is the header-matching ladder
        the RUN will use — exact key, normalised key, then the ≥6-character
        substring stage. Asking it, rather than comparing strings here, is what
        makes "this file feeds 24 of 26" a statement about the payroll and not
        about this screen's own idea of a match.
        """
        blob = {k: 1 for k in keys if k}   # presence only: this is a header check
        fed, fed_rows, missing = [], [], []
        for comp in components:
            _value, matched = batch._lookup_in_blob(blob, [comp['key']])
            if matched:
                fed.append(comp['code'])
                fed_rows.append(dict(comp, column=matched))
            else:
                missing.append(dict(comp))
        return fed, fed_rows, missing

    @api.model
    def preflight_spreadsheet(self, config_id, file_b64, filename):
        """Read a file's headings and say what it feeds. Creates nothing.

        `peek_source_columns` parses through an in-memory `new()` record: no
        batch row, no import line, no employee touched, no pay value written.
        A file that cannot be read is refused HERE, with the parser's own
        words, rather than half-loading a run.
        """
        if 'hr.payroll.import.batch' not in self.env:
            return {'ok': False, 'msg': _(
                "This database cannot read pay data files.")}
        config = self.env['hr.formula.config'].sudo() \
            .browse(int(config_id or 0)).exists()
        if not config:
            return {'ok': False,
                    'msg': _("That payroll scheme no longer exists.")}
        components = next((e['components'] for e in self._spreadsheet_configs()
                           if e['config'].id == config.id), [])
        try:
            content = base64.b64decode(file_b64 or '')
        except Exception:       # noqa: BLE001
            content = b''
        if not content:
            return {'ok': False,
                    'msg': _("This file arrived empty — nothing was read.")}
        Batch = self.env['hr.payroll.import.batch'].sudo()
        try:
            cols = Batch.peek_source_columns(config, content, filename or '')
        except Exception as e:  # noqa: BLE001
            _logger.warning("Payrun wizard: could not read %s: %s", filename, e)
            return {'ok': False, 'msg': _(
                "This file could not be read as a spreadsheet: %s") % e}
        if not cols:
            return {'ok': False, 'msg': _(
                "No column headings were found in this file. Check that the "
                "headings are on the first row.")}

        samples = {c['key']: (c.get('sample') or '') for c in cols if c.get('key')}
        # The peek deliberately returns every SPELLING of a column (the heading,
        # its bare letter, the sheet-qualified twin). All of them stay in the
        # blob because the resolver really does see them, but "N columns read"
        # must count real columns or the number is three times the truth.
        real = len([c for c in cols if c.get('preferred')]) \
            or len([c for c in cols if c.get('header')])
        fed, fed_rows, missing = self._coverage(Batch, components, samples.keys())
        for row in fed_rows:
            row['sample'] = samples.get(row['column'], '')

        # Who each row is about, read the way the loader itself reads it —
        # a file whose people cannot be identified matches nobody, and saying
        # so now is cheaper than a run of unmatched rows.
        employees_col = False
        try:
            probe = Batch.new({'formula_config_id': config.id})
            code, name, email = probe._identity_from_file_row(dict(samples))
            employees_col = bool(code or name or email)
        except Exception:       # noqa: BLE001
            employees_col = False

        return {
            'ok': True,
            'config_id': config.id,
            'config_name': config.display_name or config.name or '',
            'filename': filename or '',
            'columns': real,
            'total': len(components),
            'fed': fed,
            'fed_rows': fed_rows,
            'missing': missing,
            'employees_col': employees_col,
        }

    @api.model
    def attach_spreadsheet(self, run_id, config_id, file_b64, filename,
                           date_start, date_end, one_time=False):
        """Load this month's pay file INTO the run that already exists.

        `one_time` (RECORDS R1) is the "this run only" choice: the file feeds
        THIS run's payslips and nothing is written to any employee, contract or
        bank record — see `payroll_import_batch.action_process`. It is additive
        and defaults False, so every existing caller keeps today's behaviour.

        `payslip_run_id` is set on the batch BEFORE processing, which is what
        makes the created payslips land in this run instead of a second one
        being built beside it (`payroll_import_batch.py:1487-1498`).

        The whole load runs inside a savepoint. A file that fails halfway
        leaves nothing behind — no batch, no lines, no payslips — and the
        caller gets the server's own refusal rather than "Compute error"
        (the June lesson: a refusal that states its reason is the difference
        between a fixable run and a mystery).
        """
        if 'hr.payroll.import.batch' not in self.env:
            return {'ok': False, 'msg': _(
                "This database cannot read pay data files.")}
        run = self.env['hr.payslip.run'].sudo().browse(int(run_id or 0)).exists()
        if not run:
            return {'ok': False, 'msg': _("This pay run no longer exists.")}
        config = self.env['hr.formula.config'].sudo() \
            .browse(int(config_id or 0)).exists()
        if not config:
            return {'ok': False,
                    'msg': _("That payroll scheme no longer exists.")}
        if not file_b64:
            return {'ok': False, 'msg': _("No file was received.")}

        Batch = self.env['hr.payroll.import.batch'].sudo()
        once = bool(one_time)
        # Belt and braces: the one-time branch does not depend on these, but a
        # batch that says "save nothing" must not also be carrying a standing
        # instruction to create people.
        once_vals = {'one_time': True,
                     'auto_create_employees': False,
                     'auto_create_contracts': False} if once else {}
        try:
            with self.env.cr.savepoint():
                batch = Batch.create({
                    'name': _("%s — pay data") % (run.name or _('Payroll run')),
                    'source_type': 'excel',
                    'formula_config_id': config.id,
                    'payslip_run_id': run.id,
                    'payroll_period': 'custom',
                    'date_from': date_start or run.date_start,
                    'date_to': date_end or run.date_end,
                    'import_file': file_b64,
                    'import_filename': filename or 'pay-data.xlsx',
                    **once_vals,
                })
                batch.action_load_file()
                batch.action_match_employees()
                batch.action_validate()
                batch.action_process()
        except (AccessError, UserError) as e:
            # A refusal states its own reason; passing it on unchanged is the
            # whole point. invalidate: the rollback undid writes the ORM cache
            # may still be holding.
            self.env.invalidate_all()
            return {'ok': False, 'msg': str(e)}
        except Exception:       # noqa: BLE001
            _logger.exception(
                "Payrun wizard: pay data file failed on run %s", run.id)
            self.env.invalidate_all()
            # arbitrary exception internals never reach the client (L-5)
            return {'ok': False, 'msg': _(
                "The pay data file could not be loaded — the run was left "
                "unchanged. Ask an administrator to check the log.")}

        lines = batch.import_line_ids
        # RECORDS R1 — the rows a one-time file refused to pay because the
        # person is not in Payobook yet. They ride in `errors` too, so the
        # wizard's existing "Review exceptions" list shows them without a
        # second code path, and separately so the summary can COUNT them.
        # The test is STRUCTURAL (an error line that matched nobody), not a
        # string compare: `pb_hr_payroll_formula` is not a dependency of this
        # module — the whole method is guarded on the model merely existing —
        # so its sentence constant cannot be imported here.
        unmatched_lines = lines.filtered(
            lambda l: l.state == 'error' and not l.employee_id) if once else lines.browse()
        unmatched = [{
            'emp': (line.employee_name or line.employee_code
                    or _("Row %s") % (line.sequence or '?')),
            'why': line.error_message or '',
        } for line in unmatched_lines][:100]
        errors = [{
            'emp': (line.employee_name or line.employee_code
                    or _("Row %s") % (line.sequence or '?')),
            'why': line.error_message or _("This row could not be processed."),
        } for line in lines.filtered(lambda l: l.state == 'error')][:100]

        fed = []
        first = lines[:1]
        if first:
            try:
                raw = first.get_raw_data() or {}
                components = next(
                    (e['components'] for e in self._spreadsheet_configs()
                     if e['config'].id == config.id), [])
                fed = self._coverage(Batch, components, raw.keys())[0]
            except Exception:   # noqa: BLE001
                fed = []

        return {
            'ok': True,
            'batch_id': batch.id,
            'run_id': run.id,
            'rows': len(lines),
            'created': len(batch.created_payslip_ids),
            'matched': len(lines.filtered(lambda l: l.employee_id)),
            'created_employees': len(batch.created_employee_ids),
            'filename': batch.import_filename or '',
            'errors': errors,
            'fed_components': fed,
            'one_time': once,
            'unmatched': unmatched,
            'unmatched_count': len(unmatched),
        }

    @api.model
    def discard_empty_run(self, run_id):
        """Drop a draft run that was created for a file that never loaded.

        Deliberately narrow: draft, and not one payslip in it. A run that
        adopted this period's existing payslips has work in it and is never
        touched here — the failed upload can be retried against it.
        """
        run = self.env['hr.payslip.run'].sudo().browse(int(run_id or 0)).exists()
        if not run or run.state != 'draft' or run.slip_ids:
            return {'ok': False}
        try:
            run.unlink()
        except Exception:       # noqa: BLE001
            _logger.info("Payrun wizard: empty run %s could not be discarded.",
                         run_id)
            return {'ok': False}
        return {'ok': True}

    # ---------------- Step 3/4: summary + approve ----------------
    @api.model
    def _slip_net(self, slip):
        """What this employee is actually paid.

        The component's CATEGORY is what says "this is net pay"; its code is
        whatever the person who built the scheme called it. ABM's net component
        is `NETPAY`, so matching on the code `NET` found nothing, every payslip
        read as zero, and the review step flagged all 152 as needing attention
        while the run itself totalled ₫727,655,630. The pay run's own KPI band
        already aggregates by category — this now agrees with it.
        """
        try:
            lines = slip.line_ids.filtered(
                lambda l: (l.category_id.code or '').upper() == 'NET')
            if not lines:
                lines = slip.line_ids.filtered(
                    lambda l: (l.code or '').upper() == 'NET')
            if lines:
                return sum(lines.mapped('total'))
            # fallback: last line total
            return slip.line_ids and slip.line_ids[-1].total or 0.0
        except Exception:
            return 0.0

    @api.model
    def get_summary(self, run_id):
        # sudo: the run/slips may have been created as sudo (see compute_batch).
        run = self.env['hr.payslip.run'].sudo().browse(run_id)
        slips = run.slip_ids
        rows, total_net = [], 0.0
        for s in slips:
            net = self._slip_net(s)
            total_net += net
            rows.append({
                'id': s.id, 'emp': s.employee_id.name, 'state': s.state,
                'net': net, 'flag': (net <= 0),
            })
        return {
            'run_id': run.id, 'name': run.name, 'state': run.state,
            'count': len(slips), 'total_net': total_net,
            'flagged': len([r for r in rows if r['flag']]),
            'rows': rows,
        }

    @api.model
    def submit_for_approval(self, run_id):
        """Enter the approval chain at its FIRST tier (Officer review).

        Phase L fix: this used to call action_payslip_run_level1_done() on a
        DRAFT run — and that legacy method writes 'level2' unconditionally, so a
        submit jumped the run straight past the HR tier. done_payslip_run() is
        the only correct draft→chain transition (it confirms the payslips, then
        lands on level0).

        It also swallowed every exception into a bare ok=False; the caller now
        gets the server's real refusal (the tier gate's own words).
        """
        run = self.env['hr.payslip.run'].browse(int(run_id))
        if not run.exists():
            return {'ok': False, 'run_id': run_id, 'state': False,
                    'msg': _('This pay run no longer exists.')}
        if run.state != 'draft':
            return {'ok': False, 'run_id': run.id, 'state': run.state,
                    'msg': _('This pay run is already in the approval chain.')}
        try:
            with self.env.cr.savepoint():
                run.done_payslip_run()
        except (AccessError, UserError) as e:
            # a real, actionable refusal (missing tier / bad state) — surface it.
            # invalidate: the savepoint rollback undid writes the ORM cache may
            # still hold, so `state` below must be re-read from the DB.
            self.env.invalidate_all()
            return {'ok': False, 'run_id': run.id, 'state': run.state, 'msg': str(e)}
        except Exception:
            _logger.exception("Payrun wizard: submit failed on run %s", run.id)
            self.env.invalidate_all()
            # arbitrary exception internals never reach the client (L-5)
            return {'ok': False, 'run_id': run.id, 'state': run.state,
                    'msg': _('The submit failed on the server — the run was left '
                             'unchanged. Ask an administrator to check the log.')}
        return {'ok': True, 'run_id': run.id, 'state': run.state}
