# WFSETUP P10b rehearsal (odoo-bin shell on the HIDDEN COPY zz_wfs_p10b_* only). PHASE=
#   neutral   resolve the 650 September test cases of scheme 7844 for a September period through the pay
#             data file resolver; write values + sources to OUT and print the md5 (run with the OLD code
#             before the upgrade, and with the NEW code after the clock mapping: must be identical)
#   setup     rehearsal manager; leave types paid / unpaid; rules confirmed through the studio; roster
#             1-23 Nov made from the working weeks (copy only: the engine never makes past days) and
#             published; scheme 7844 activated, contracts running, clock mapping through the scheme
#             editor's own method, clock date moved to 1 Nov 2026 (copy only)
#   switch    "Switch clock-ins on" for connectors 4-8 through the studio (never 1)
#   drain     the connector + pairing job bodies until nothing waits (as P8)
#   calc      the rules calculation for every published 1-23 Nov shift, 300 per transaction
#   ready1    readiness + the run's refusal BEFORE any overtime decision
#   decide    3 paid + 1 unpaid time off on days with no punches; every overtime entry submitted;
#             approved, 5 refused; rest-day shifts for Sunday punches (+ calculation + approval)
#   ready2    readiness after the decisions
#   run       pay run for the people who are ready, with a pay data file of September columns (this run
#             only), the rest computed without a file; 5 people checked by hand; double lateness, above
#             the limit, Sunday column, stamp
# Prints PROBE lines. No names or employee numbers are printed (people are P1..P5).
import base64, hashlib, io, json, os, time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

assert env.cr.dbname.startswith('zz_wfs_p10b_'), 'rehearsal copy only'
phase = os.environ['PHASE']
LOGIN = 'wfs-p10b-rehearsal-manager'
CID = 7844
D0, D1 = date(2026, 11, 1), date(2026, 11, 23)
company = env['res.company'].browse(1)
config = env['hr.formula.config'].browse(CID)


def P(*a):
    print('PROBE', *a, flush=True)


def manager():
    return env['res.users'].with_context(active_test=False).search([('login', '=', LOGIN)])


def file_row(raw):
    """A September test case as the pay data file loader hands it to the resolver: every column under
    its sheet-qualified heading ("Audit|Basic rate", what the scheme's columns are bound to), its plain
    heading and its letter."""
    out = {}
    for r in config.rule_ids.filtered(lambda r: r.column_type == 'input'):
        src = r.source_ids.filtered(lambda x: x.kind == 'excel')[:1]
        if not src or r.code not in raw:
            continue
        key = src.key
        out[key] = raw[r.code]
        out[key.split('|', 1)[-1]] = raw[r.code]
        if r.column_letter:
            out[r.column_letter] = raw[r.code]
    return out


if phase == 'map':
    Bp = env['pb.blueprint.studio']
    by_code = {r.code: r.id for r in config.rule_ids}
    for key, code in [('clock.paid_days', 'VNPAIDDAYS'), ('clock.ot_hours', 'VNOTHOURS'),
                      ('clock.ot_premium_hours', 'VNPREMHOURS'), ('clock.empty', 'VNSUNDAYHOURS')]:
        P('bind', key, Bp.bp_clock_bind(CID, key, by_code[code]).get('ok'))
    for key in ('clock.worked_days', 'clock.paid_leave_days', 'clock.holiday_days', 'clock.paid_normal_hours',
                'clock.actual_hours', 'clock.late_minutes', 'clock.over_limit_hours'):
        P('bind new', key, Bp.bp_clock_bind(CID, key, 'new').get('ok'))
    P('clock date', Bp.bp_save_settings(CID, {'pb_clock_from': '2026-11-01'}).get('ok'), config.pb_clock_from)
    env.cr.commit()

elif phase == 'neutral':
    Batch = env['hr.payroll.import.batch']
    emp_by_code = {e.barcode: e for e in env['hr.employee'].with_context(active_test=False).search([]) if e.barcode}
    batch = Batch.create({'name': 'P10b neutral probe', 'source_type': 'excel', 'formula_config_id': CID,
                          'payroll_period': 'custom', 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)})
    out = []
    for s in config.sample_data_ids.filtered('active').sorted('id'):
        raw = json.loads(s.input_values_json or '{}')
        emp = emp_by_code.get(str(raw.get('VNID') or ''))
        raw = file_row(raw)
        prov = {}
        vals = batch._transform_data_to_formula_inputs(raw, employee=emp or None, provenance=prov)
        out.append([s.id, vals, prov])
    blob = json.dumps(out, sort_keys=True, default=str)
    open(os.environ['OUT'], 'w').write(blob)
    src = Counter(e['src'] for _i, _v, p in out for e in p.values())
    paid = Counter(round(float(v.get('VNPAIDDAYS') or 0)) for _i, v, _p in out)
    P('neutral sources', dict(src), 'paid days seen', dict(paid.most_common(4)))
    P('neutral rows', len(out), 'md5', hashlib.md5(blob.encode()).hexdigest(),
      'clock date', config.pb_clock_from if 'pb_clock_from' in config._fields else 'no field')
    env.cr.rollback()

elif phase == 'setup':
    groups = [env.ref(x).id for x in ('base.group_user', 'hr.group_hr_manager',
                                      'hr_attendance.group_hr_attendance_manager',
                                      'hr_holidays.group_hr_holidays_manager',
                                      'om_hr_payroll.group_hr_payroll_manager',
                                      'pb_hr_payroll_formula.group_formula_manager',
                                      'pb_hr_payroll_base.group_payroll_base_manager')]
    u = manager()
    if not u:
        u = env['res.users'].with_context(no_reset_password=True, mail_create_nosubscribe=True).create({
            'name': 'P10b Rehearsal Manager', 'login': LOGIN, 'company_id': 1, 'company_ids': [(6, 0, [1])],
            'group_ids': [(6, 0, groups)], 'lang': 'en_US'})
    studio = env['pb.workforce.setup'].with_user(u).with_company(1)
    # time off pay treatment (copy only; on live this is Sudima's decision in the time off settings)
    LT = env['hr.leave.type']
    paid = LT.browse(1); unpaid = LT.browse(4)
    paid.write({'pb_pay_treatment': 'paid', 'pb_pay_funding': 'employer'})
    unpaid.write({'pb_pay_treatment': 'unpaid', 'pb_pay_funding': 'none'})
    P('leave types', paid.name, paid.pb_pay_treatment, '/', unpaid.name, unpaid.pb_pay_treatment)
    # rules: the 1-9 minute line is the one not confirmed; Confirm = the studio's own method
    t = time.time()
    res = studio.confirm_rules()
    P('confirm_rules', round(time.time() - t, 1), res.get('summary'), res.get('problems'))
    policy = env['pb.attendance.policy'].search([('company_id', '=', 1), ('state', '=', 'active')], limit=1)
    P('rules', policy.id, policy.state, 'people on it', env['hr.employee'].search_count([('pb_attendance_policy_id', '=', policy.id)]))
    # roster 1-18 Nov from the working weeks (the engine skips past days, so the copy makes them the
    # engine's way: its own wanted-days reading with "today" = 1 Nov), 19-23 Nov drafts already exist
    # copy only: the working-week memberships start 19 Nov; the fake December starts 1 Nov
    env.cr.execute("update pb_shift_pattern_member set date_from=%s where date_from > %s", [D0, D0])
    env.invalidate_all()
    Engine = env['pb.shift.pattern.engine']
    Grid = env['hr.shift.planning.grid']
    Shift = env['hr.shift.planning']
    have = {(s.employee_id.id, s.date) for s in Shift.search([('date', '>=', D0), ('date', '<=', D1),
                                                              ('state', '!=', 'cancelled')])}
    creates = []
    for pattern in env['pb.shift.pattern'].search([('company_id', '=', 1)]):
        wanted, _off, _past = Engine._pb_wanted(pattern.sudo(), D0, D1, D0)
        for (emp_id, iso), (emp, template, day) in wanted.items():
            if (emp_id, day) in have:
                continue
            start, end = Grid._pb_shift_window(template, day, Grid._pb_shift_tzname(emp))
            creates.append({'employee_id': emp_id, 'shift_template_id': template.id, 'date': day,
                            'start_datetime': start, 'end_datetime': end, 'state': 'draft',
                            'company_id': 1, 'pb_pattern_id': pattern.id, 'pb_policy_id': policy.id})
            have.add((emp_id, day))
    made = Shift.with_context(tracking_disable=True, mail_notrack=True).create(creates)
    rows = Shift.search([('date', '>=', D0), ('date', '<=', D1), ('state', '=', 'draft'), ('company_id', '=', 1)])
    rows.with_context(tracking_disable=True, mail_notrack=True).write({'pb_policy_id': policy.id})
    rows.with_context(tracking_disable=True, mail_notrack=True).action_publish()
    kinds = Counter(rows.mapped('pb_day_kind'))
    P('roster made', len(made), 'published 1-23 Nov', len(rows), 'people', len(set(rows.mapped('employee_id').ids)), 'kinds', dict(kinds))
    # scheme + contracts on (copy only: Sudima's decision on live)
    contracts = env['hr.contract'].search([('company_id', '=', 1), ('state', '=', 'draft')])
    contracts.write({'state': 'open'})
    if config.state != 'active':
        # copy only: on live this goes through the scheme approval ("Propose for approval")
        env.cr.execute("update hr_formula_config set state='active' where id=%s", [CID])
        env.invalidate_all()
    P('scheme', config.state, 'contracts running', env['hr.contract'].search_count([('state', '=', 'open')]))
    # the clock mapping through the scheme editor's own method (bp_clock_bind -> pb_clock_bind)
    Bp = env['pb.blueprint.studio'].with_user(u).with_company(1)
    plan = [('clock.paid_days', 'VNPAIDDAYS'), ('clock.ot_hours', 'VNOTHOURS'),
            ('clock.ot_premium_hours', 'VNPREMHOURS'), ('clock.empty', 'VNSUNDAYHOURS')]
    by_code = {r.code: r.id for r in config.rule_ids}
    for key, code in plan:
        r = Bp.bp_clock_bind(CID, key, by_code[code])
        P('bind', key, code, r.get('ok'), r.get('reason', ''))
    for key in ('clock.worked_days', 'clock.paid_leave_days', 'clock.holiday_days', 'clock.paid_normal_hours',
                'clock.actual_hours', 'clock.late_minutes', 'clock.over_limit_hours'):
        r = Bp.bp_clock_bind(CID, key, 'new')
        P('bind new', key, r.get('ok'), r.get('reason', ''))
    r = Bp.bp_save_settings(CID, {'pb_clock_from': '2026-11-01'})
    P('clock date', r.get('ok'), config.pb_clock_from, r.get('reason', ''))
    env.cr.commit()

elif phase == 'switch':
    u = manager()
    studio = env['pb.workforce.setup'].with_user(u).with_company(1)
    for cid in (4, 5, 6, 7, 8):
        res = studio.clock_switch_on(cid)
        P('switch', cid, res['summary'])
    assert not env['pb.clock.connector'].browse(1).publish_punches, 'connector 1 must stay off'
    env.cr.commit()

elif phase == 'drain':
    Event = env['pb.clock.connector.event']
    t0 = time.time(); n = 0
    while True:
        env.cr.execute("""select count(*) from pb_clock_connector_event e join pb_clock_connector c on c.id=e.connector_id
                          where e.state='pending' or (e.state='ready' and c.publish_punches)""")
        left = env.cr.fetchone()[0]
        if not left or n > 400:
            break
        Event._cron_process(); env.cr.commit(); env.invalidate_all(); n += 1
    P('process batches', n, 'seconds', round(time.time() - t0, 1))
    t1 = time.time(); m = 0
    while True:
        res = env['pb.clock.pairing']._cron_run(); env.cr.commit(); env.invalidate_all(); m += 1
        if not res.get('retriggered') or m > 60:
            break
    env.cr.execute("select state, count(*) from pb_clock_connector_event group by 1 order by 1")
    ev = dict(env.cr.fetchall())
    env.cr.execute("select count(*), count(employee_id) from pb_clock_punch")
    pu = env.cr.fetchone()
    env.cr.execute("select count(*), count(*) filter (where pb_policy_roster_id is null) from hr_attendance")
    at = env.cr.fetchone()
    P('pairing runs', m, 'seconds', round(time.time() - t1, 1), 'events', ev, 'punches/matched', pu,
      'attendance/outside a shift', at, 'matched %', round(100.0 * pu[1] / pu[0], 2) if pu[0] else 0)

elif phase == 'calc':
    Shift = env['hr.shift.planning']
    ids = Shift.search([('state', '=', 'published'), ('pb_policy_id.state', '=', 'active'),
                        ('date', '>=', D0), ('date', '<=', D1)], order='date,id').ids
    t0 = time.time(); tally = Counter()
    for i in range(0, len(ids), 300):
        for row in Shift.browse(ids[i:i + 300]):
            try:
                with env.cr.savepoint():
                    ok = row._process_calculation()
                    tally['calculated' if ok else (row.pb_calculation_status or 'day guarded')[:70]] += 1
            except Exception as exc:  # noqa: BLE001
                tally[str(exc)[:70]] += 1
        env.cr.commit(); env.invalidate_all()
    P('calc shifts', len(ids), 'seconds', round(time.time() - t0, 1))
    for k, v in tally.most_common(8):
        P('calc', v, '|', k)
    env.cr.execute("select state, overtime_type, count(*), round(sum(planned_hours)::numeric,1) from hr_overtime_request where date between %s and %s group by 1,2 order by 1,2", [D0, D1])
    P('overtime entries', env.cr.fetchall())

elif phase in ('ready1', 'ready2'):
    W = env['pb.payrun.wizard']
    vals = {'formula_config_id': CID, 'date_start': str(D0), 'date_end': str(D1), 'name': 'P10b rehearsal run'}
    t = time.time()
    panel = W.pb_clock_readiness(vals)
    P(phase, 'seconds', round(time.time() - t, 1), 'total', panel.get('total'), 'ready', panel.get('ready'),
      'attention', panel.get('attention'), 'issues', panel.get('scheme_issues'))
    for g in panel.get('groups') or []:
        P(phase, 'group', g['code'], g['count'], '|', g['label'])
    prep = W.prepare_run(dict(vals))
    P(phase, 'prepare_run blocked', bool(prep.get('blocked')), (prep.get('message') or '').split('\n')[0][:300])
    env.cr.rollback()

elif phase == 'decide':
    u = manager()
    Facts = env['pb.clock.payroll']
    emps = env['hr.employee'].search([('company_id', '=', 1), ('pb_attendance_policy_id', '!=', False)])
    facts = Facts.facts_many(emps, D0, D1)
    # time off: 3 paid + 1 unpaid, on a rostered day the person did not punch (an absence)
    picks = [(e, d) for e in emps for d in (facts[e.id]['absent'] or [])[:1]][:4]
    # copy only: no leave allocations exist on sudima; the types take requests without one here
    env['hr.leave.type'].browse([1, 4]).write({'requires_allocation': False})
    Leave = env['hr.leave'].with_user(u).with_company(1)
    made = []
    for i, (emp, day) in enumerate(picks):
        lt = 1 if i < 3 else 4
        lv = Leave.with_context(leave_skip_date_check=True).create({
            'employee_id': emp.id, 'holiday_status_id': lt, 'request_date_from': day, 'request_date_to': day})
        if lv.state != 'validate':
            try:
                lv.sudo().action_approve()
            except Exception:  # noqa: BLE001
                pass
        if lv.state != 'validate':
            lv.sudo().write({'state': 'validate'})
        made.append((lv.id, lt, lv.state))
    P('time off', made)
    # Sunday (and any other off-day) punches: a rest-day shift, as HR adds one on the roster
    Shift = env['hr.shift.planning']; Grid = env['hr.shift.planning.grid']
    tmpl = env['hr.shift.template'].search([('code', '=', 'SD-DAY-0730-1630'), ('company_id', '=', 1)], limit=1)
    extra = []
    for e in emps:
        for b in facts[e.id]['blockers']:
            if b['code'] != 'no_shift_punch':
                continue
            for iso in b['dates']:
                day = date.fromisoformat(iso)
                start, end = Grid._pb_shift_window(tmpl, day, Grid._pb_shift_tzname(e))
                extra.append({'employee_id': e.id, 'shift_template_id': tmpl.id, 'date': day,
                              'start_datetime': start, 'end_datetime': end, 'state': 'draft', 'company_id': 1,
                              'pb_policy_id': e.pb_attendance_policy_id.id})
    rest = Shift.with_context(tracking_disable=True, mail_notrack=True).create(extra) if extra else Shift
    rest.with_context(tracking_disable=True, mail_notrack=True).action_publish()
    tally = Counter()
    for row in rest:
        try:
            with env.cr.savepoint():
                tally['calculated' if row._process_calculation() else (row.pb_calculation_status or '')[:60]] += 1
        except Exception as exc:  # noqa: BLE001
            tally[str(exc)[:60]] += 1
    P('rest-day shifts added', len(rest), 'kinds', dict(Counter(rest.mapped('pb_day_kind'))), dict(tally))
    env.cr.commit()
    # every overtime entry decided: submit, approve all but five (refused)
    Req = env['hr.overtime.request'].with_user(u).with_company(1)
    reqs = Req.search([('date', '>=', D0), ('date', '<=', D1), ('state', 'in', ('draft', 'submitted'))], order='id')
    reqs.filtered(lambda r: r.state == 'draft').action_submit()
    refuse = reqs[:5]
    refuse.action_refuse()
    (reqs - refuse).action_approve()
    env.cr.commit()
    env.cr.execute("select state, count(*), round(sum(approved_hours)::numeric,1), round(sum(bonus_hours)::numeric,1) from hr_overtime_request where date between %s and %s group by 1 order by 1", [D0, D1])
    P('overtime decided', env.cr.fetchall())

elif phase == 'run':
    W = env['pb.payrun.wizard']
    Facts = env['pb.clock.payroll']
    vals = {'formula_config_id': CID, 'date_start': str(D0), 'date_end': str(D1), 'name': 'P10b rehearsal run'}
    panel = W.pb_clock_readiness(vals)
    ready_ids = []
    blocked = {p['id'] for g in panel.get('groups') or [] for p in g['people']}
    elig = W._eligible_employees(formula_config_id=CID, date_start=str(D0), date_end=str(D1))
    emps = env['hr.employee'].browse(elig)
    facts = Facts.facts_many(emps, D0, D1)
    ready_ids = [e.id for e in emps if not facts[e.id]['blockers']]
    P('run eligible', len(elig), 'ready', len(ready_ids))
    prep = W.prepare_run(dict(vals, employee_ids=ready_ids, force_clean=True))
    P('prepare_run', 'blocked' if prep.get('blocked') else 'ok', (prep.get('message') or '')[:200], 'run', prep.get('run_id'))
    if prep.get('blocked'):
        raise SystemExit
    # the pay data file: September columns of the stored test cases, for the ready people
    import openpyxl
    rules = config.rule_ids.filtered(lambda r: r.column_type == 'input' and r.source_ids.filtered(lambda s: s.kind == 'excel'))
    rules = rules.sorted('sequence')
    heads = [(r.code, r.source_ids.filtered(lambda s: s.kind == 'excel')[0].key.split('|', 1)[-1]) for r in rules]
    by_code = {}
    for s in config.sample_data_ids.filtered('active'):
        raw = json.loads(s.input_values_json or '{}')
        by_code[str(raw.get('VNID') or '')] = raw
    ready = env['hr.employee'].browse(ready_ids)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'Audit'
    ws.append([h for _c, h in heads])
    in_file = []
    for e in ready:
        raw = by_code.get(e.barcode or '')
        if not raw:
            continue
        in_file.append(e.id)
        ws.append([raw.get(c, '') for c, _h in heads])
    buf = io.BytesIO(); wb.save(buf)
    t = time.time()
    att = W.attach_spreadsheet(prep['run_id'], CID, base64.b64encode(buf.getvalue()).decode(), 'september-columns.xlsx',
                               str(D0), str(D1), True)
    P('file rows', att.get('rows'), 'payslips', att.get('created'), 'refused rows', len(att.get('errors') or []),
      'ok', att.get('ok'), (att.get('msg') or '')[:200], 'seconds', round(time.time() - t, 1),
      'waiting for approval', att.get('pending'))
    if att.get('pending'):
        # Sudima has an approval route for "this run only" pay data files. Copy only: the approved body
        # runs as the approver's Yes would run it (payroll_import_approval.apply_context).
        from odoo.addons.pb_hr_payroll_formula.models.payroll_import_approval import apply_context
        batch = env['hr.payroll.import.batch'].browse(att['batch_id'])
        t = time.time()
        apply_context(batch).action_process()
        lines = batch.import_line_ids
        att['created'] = len(batch.created_payslip_ids)
        att['errors'] = [{'why': l.error_message} for l in lines.filtered(lambda l: l.state == 'error')]
        P('after approval: payslips', att['created'], 'refused rows', len(att['errors']), 'seconds', round(time.time() - t, 1))
    for er in (att.get('errors') or [])[:3]:
        P('file row refused', (er.get('why') or '')[:300])
    rest = [i for i in prep['emp_ids'] if i not in in_file]
    t = time.time(); computed = 0; why = Counter()
    for i in range(0, len(rest), 40):
        r = W.compute_batch({'run_id': prep['run_id'], 'name': prep['name'], 'date_start': str(D0), 'date_end': str(D1),
                             'formula_config_id': CID, 'emp_ids': rest[i:i + 40]})
        computed += r['computed']
        for x in r['exceptions']:
            why[(x.get('why') or '')[:80]] += 1
    P('without a file', len(rest), 'computed', computed, 'seconds', round(time.time() - t, 1), dict(why.most_common(3)))
    env.cr.commit()
    run = env['hr.payslip.run'].browse(prep['run_id'])
    slips = run.slip_ids
    P('run payslips', len(slips), 'with clock values', sum(1 for s in slips if '"via": "clock"' in (s.formula_input_sources or '')),
      'stamped', len(slips.filtered('pb_clock_stamp')))
    codes = {r.pb_clock_key: r.code for r in config.rule_ids if r.pb_clock_key}
    # five people by hand
    sample = [s for s in slips if json.loads(s.formula_input_values or '{}').get(codes['clock.late_minutes'])][:2]
    sample += [s for s in slips if json.loads(s.formula_input_values or '{}').get(codes['clock.over_limit_hours']) and s not in sample][:2]
    sample += [s for s in slips if json.loads(s.formula_input_values or '{}').get(codes['clock.paid_leave_days']) and s not in sample][:1]
    sample += [s for s in slips if s not in sample][:5 - len(sample)]
    Shift = env['hr.shift.planning']; Req = env['hr.overtime.request']
    for n, s in enumerate(sample, 1):
        v = json.loads(s.formula_input_values or '{}')
        c = json.loads(s.formula_computed_values or '{}')
        e = s.employee_id
        days = 0.0
        for sh in Shift.search([('employee_id', '=', e.id), ('date', '>=', D0), ('date', '<=', D1), ('state', '=', 'published')]):
            proof = json.loads(sh.pb_attendance_id.pb_policy_proof or '{}') if sh.pb_attendance_id else {}
            if proof and proof.get('day_kind') == 'weekday':
                rule = env['pb.attendance.policy.shift'].browse(proof['shift_rule_id'])
                days += proof['normal_hours'] / rule.normal_hours
        leave = sum((1.0 if lv.holiday_status_id.id == 1 else 0.0)
                    for lv in env['hr.leave'].search([('employee_id', '=', e.id), ('state', '=', 'validate'),
                                                     ('request_date_from', '>=', D0), ('request_date_to', '<=', D1)]))
        ot = sum(Req.search([('employee_id', '=', e.id), ('date', '>=', D0), ('date', '<=', D1), ('state', '=', 'approved'),
                             ('overtime_type', 'in', ('weekday', 'weekend', 'holiday'))]).mapped('approved_hours'))
        prem = sum(r.approved_hours * (r.rate_multiplier - 1) for r in Req.search([
            ('employee_id', '=', e.id), ('date', '>=', D0), ('date', '<=', D1), ('state', '=', 'approved'),
            ('overtime_type', 'in', ('weekday', 'weekend', 'holiday'))]))
        dayrate = (v['VNBASE'] + v['VNRESP'] + v['VNPOS']) / v['VNDIVISOR'] if v.get('VNBASIS') == 1 else v['VNBASE'] + v['VNRESP'] + v['VNPOS']
        basehour = (v['VNBASE'] / v['VNDIVISOR'] if v.get('VNBASIS') == 1 else v['VNBASE']) / v['VNHOURSDAY']
        hand = {'days': round(days + leave, 6), 'ot': round(ot, 4), 'prem': round(prem, 4),
                'regular': round(dayrate * (days + leave), 2), 'otpay': round(basehour * ot, 2), 'prempay': round(basehour * prem, 2)}
        got = {'days': v['VNPAIDDAYS'], 'ot': v['VNOTHOURS'], 'prem': v['VNPREMHOURS'],
               'regular': round(c.get('VNREGULAR', 0), 2), 'otpay': round(c.get('VNOTPAY', 0), 2), 'prempay': round(c.get('VNPREMPAY', 0), 2)}
        same = all(abs(float(hand[k]) - float(got[k])) < 0.011 for k in hand)
        info = {k.split('.', 1)[1]: v.get(code) for k, code in codes.items() if k not in ('clock.paid_days', 'clock.ot_hours', 'clock.ot_premium_hours', 'clock.empty')}
        P('person P%s' % n, 'basis', v.get('VNBASIS'), 'clock', got, 'hand', hand, 'match', same, 'info', info,
          'file said days', json.loads(s.formula_input_sources).get('VNPAIDDAYS', {}).get('ignored', {}).get('value'))

elif phase == 'probes':
    Shift = env['hr.shift.planning']; Req = env['hr.overtime.request']
    run = env['hr.payslip.run'].search([('name', '=', 'P10b rehearsal run')], order='id desc', limit=1)
    slips = run.slip_ids
    codes = {r.pb_clock_key: r.code for r in config.rule_ids if r.pb_clock_key}
    by_code = {}
    for s_ in config.sample_data_ids.filtered('active'):
        raw_ = json.loads(s_.input_values_json or '{}')
        by_code[str(raw_.get('VNID') or '')] = raw_
    sample = [s_ for s_ in slips if json.loads(s_.formula_input_values or '{}').get(codes['clock.late_minutes'])][:1] or slips[:1]
    # double lateness: no late-minute columns, nothing held by the weekly Close, file deductions unchanged
    late_rows = env['pb.time.late'].search_count([('payslip_id', 'in', slips.ids)]) if 'pb.time.late' in env else 0
    P('double lateness: late-minute inputs on the scheme', len(config.rule_ids.filtered(lambda r: r.code in ('LATEMIN', 'EARLYMIN'))),
      'late rows held by these payslips', late_rows, 'scheme refusals', config._pb_clock_refusals())
    tot_over = sum(json.loads(s.formula_input_values or '{}').get(codes['clock.over_limit_hours'], 0) or 0 for s in slips)
    tot_ot = sum(json.loads(s.formula_input_values or '{}').get('VNOTHOURS', 0) or 0 for s in slips)
    env.cr.execute("select round(sum(approved_hours)::numeric,2), round(sum(bonus_hours)::numeric,2) from hr_overtime_request where state='approved' and employee_id = any(%s) and date between %s and %s and overtime_type in ('weekday','weekend','holiday')", [slips.employee_id.ids, D0, D1])
    appr, bonus = env.cr.fetchone()
    P('above the limit: paid hours in VNOTHOURS', round(tot_ot, 2), '= approved', appr, '; shown', round(tot_over, 2), '= bonus', bonus)
    # Sunday column guard
    one = slips[:1]
    Batch = env['hr.payroll.import.batch']
    b = Batch.create({'name': 'P10b Sunday probe', 'source_type': 'excel', 'formula_config_id': CID,
                      'payroll_period': 'custom', 'date_from': D0, 'date_to': D1})
    prov = {}
    vals = b._transform_data_to_formula_inputs(file_row(by_code.get(one.employee_id.barcode or '') or {}),
                                               employee=one.employee_id, provenance=prov)
    P('file values shown beside: paid days', vals['VNPAIDDAYS'], prov['VNPAIDDAYS'],
      '| overtime', vals['VNOTHOURS'], prov['VNOTHOURS'].get('ignored'), '| an allowance from the file', prov.get('VNATT'))
    raw = dict(by_code.get(one.employee_id.barcode or '') or {}, VNSUNDAYHOURS=8)
    raw = file_row(raw)
    try:
        b._transform_data_to_formula_inputs(raw, employee=one.employee_id, provenance={})
        P('sunday guard', 'NOT REFUSED')
    except Exception as exc:  # noqa: BLE001
        P('sunday guard refused:', str(exc)[:200].replace(one.employee_id.name or '#', 'P'))
    env.cr.rollback()
    # stamp: a later first punch recalculates a shift of a computed payslip (a day without overtime);
    # approval is refused; Recompute; approval goes through. Rolled back.
    for slip in slips:
        days_ot = set(Req.search([('employee_id', '=', slip.employee_id.id), ('date', '>=', D0), ('date', '<=', D1)]).mapped('date'))
        sh = Shift.search([('employee_id', '=', slip.employee_id.id), ('date', '>=', D0), ('date', '<=', D1),
                           ('pb_attendance_id', '!=', False), ('pb_day_kind', '=', 'weekday'),
                           ('date', 'not in', list(days_ot))], order='date desc', limit=1)
        if sh:
            break
    import pytz
    ev = env['pb.clock.connector.event'].search([('id', 'in', json.loads(sh.pb_calculation_json)['source_event_ids'])], order='punch_local', limit=1)
    start_local = pytz.utc.localize(sh.start_datetime).astimezone(pytz.timezone('Asia/Ho_Chi_Minh')).replace(tzinfo=None)
    first = ev.punch_local
    late = start_local + timedelta(minutes=15)
    zone = pytz.timezone('Asia/Ho_Chi_Minh')
    same = env['pb.clock.connector.event'].search([('company_id', '=', 1), ('user_code', '=', ev.user_code), ('punch_local', '=', first)])
    same.sudo().write({'punch_local': late})
    utc_first = zone.localize(first).astimezone(pytz.utc).replace(tzinfo=None)
    led = env['pb.clock.punch'].search([('employee_id', '=', sh.employee_id.id), ('punch_utc', '=', utc_first)])
    led.sudo().write({'punch_utc': zone.localize(late).astimezone(pytz.utc).replace(tzinfo=None)})
    P('stamp: first punch moved to 15 min late on', len(same), 'received records and', len(led), 'ledger punches')
    before = sh.pb_normal_hours
    ok = sh._process_calculation()
    P('stamp: shift recalculated', ok, 'normal hours', before, '->', sh.pb_normal_hours)
    try:
        with env.cr.savepoint():
            slip.write({'state': 'verify'})
        P('stamp', 'NOT REFUSED')
    except Exception as exc:  # noqa: BLE001
        P('stamp refused:', str(exc)[:160].replace(slip.employee_id.name or '#', 'P'))
    slip.action_recompute_formula_lines()
    try:
        slip.write({'state': 'verify'})
        P('stamp after Recompute: approved, state', slip.state, 'paid days now', json.loads(slip.formula_input_values)['VNPAIDDAYS'])
    except Exception as exc:  # noqa: BLE001
        P('stamp after Recompute still refused:', str(exc)[:160])
    env.cr.rollback()
