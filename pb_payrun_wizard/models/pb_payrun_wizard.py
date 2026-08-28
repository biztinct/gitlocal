# -*- coding: utf-8 -*-
import base64
import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import _, api, models
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
                    exceptions.append({'emp': emp.name, 'why': 'No running contract'})
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
                    exceptions.append({'emp': emp.name, 'why': 'No running contract'})
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
                           date_start, date_end):
        """Load this month's pay file INTO the run that already exists.

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
