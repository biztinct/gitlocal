# WFSETUP P8 step A (odoo-bin shell on the HIDDEN COPY only). PHASE=
#   user    a throwaway attendance manager in the copy (no password: nobody signs in with it)
#   switch  "Switch clock-ins on" for the REAL PC clocks (CONNECTORS, default 4,5,6,7,8) through the studio
#           method, as that manager. Connector 1 is the owner's test machine (owner, 2026-11-25): never switched.
#   drain   the connector job body (_cron_process) until no record waits, then the pairing job body
#           (_cron_run) until it stops asking to run again; one transaction per batch, as live
#   jobs    every other job that reacts to attendance, run once by hand (they are switched off on the copy)
# Prints PROBE lines; timings in seconds.
import json, os, time

assert env.cr.dbname.startswith('zz_wfs_p8_'), 'rehearsal copy only'
phase = os.environ['PHASE']
LOGIN = 'wfs-p8-rehearsal-manager'


def counts():
    env.cr.execute("select state, count(*) from pb_clock_connector_event group by 1 order by 1")
    ev = dict(env.cr.fetchall())
    env.cr.execute("select count(*) from pb_clock_punch")
    pu = env.cr.fetchone()[0]
    env.cr.execute("select count(*) from hr_attendance")
    at = env.cr.fetchone()[0]
    return {'events': ev, 'punches': pu, 'attendance': at}


if phase == 'user':
    groups = [env.ref('base.group_user').id, env.ref('hr.group_hr_user').id,
              env.ref('hr_attendance.group_hr_attendance_manager').id]
    u = env['res.users'].with_context(no_reset_password=True, mail_create_nosubscribe=True,
                                      active_test=False).search([('login', '=', LOGIN)])
    if not u:
        u = env['res.users'].with_context(no_reset_password=True, mail_create_nosubscribe=True).create({
            'name': 'P8 Rehearsal Manager', 'login': LOGIN, 'company_id': 1, 'company_ids': [(6, 0, [1])],
            'group_ids': [(6, 0, groups)], 'lang': 'en_US'})
    env.cr.commit()
    print('PROBE user', u.id)

elif phase == 'switch':
    u = env['res.users'].search([('login', '=', LOGIN)])
    studio = env['pb.workforce.setup'].with_user(u).with_company(1)
    wanted = [int(x) for x in (os.environ.get('CONNECTORS') or '4,5,6,7,8').split(',')]
    assert 1 not in wanted, 'connector 1 is the owner test machine - never switch it on'
    for conn in env['pb.clock.connector'].browse(wanted):
        t = time.time()
        res = studio.clock_switch_on(conn.id)
        print('PROBE switch', conn.id, round(time.time() - t, 2), res['summary'])
    env.cr.commit()
    env.invalidate_all()
    print('PROBE after-switch', json.dumps(counts()),
          [(c.id, c.publish_punches, c.write_uid.id) for c in env['pb.clock.connector'].search([], order='id')])

elif phase == 'drain':
    Event = env['pb.clock.connector.event']
    t0 = time.time(); n = 0
    while True:
        env.cr.execute("""select count(*) from pb_clock_connector_event e join pb_clock_connector c on c.id=e.connector_id
                          where e.state='pending' or (e.state='ready' and c.publish_punches)""")
        left = env.cr.fetchone()[0]
        if not left:
            break
        t = time.time()
        Event._cron_process()
        env.cr.commit()
        env.invalidate_all()
        n += 1
        if n % 10 == 0:
            print('PROBE process batch', n, 'left before', left, 'batch s', round(time.time() - t, 2), flush=True)
        if n > 400:
            print('PROBE process STOP: too many batches'); break
    t_proc = time.time() - t0
    print('PROBE process done batches', n, 'seconds', round(t_proc, 1), json.dumps(counts()), flush=True)
    t1 = time.time(); m = 0
    while True:
        t = time.time()
        res = env['pb.clock.pairing']._cron_run()
        env.cr.commit()
        env.invalidate_all()
        m += 1
        print('PROBE pair run', m, 's', round(time.time() - t, 1), {k: v for k, v in res.items()}, flush=True)
        if not res.get('retriggered') or m > 60:
            break
    print('PROBE pair done runs', m, 'seconds', round(time.time() - t1, 1), json.dumps(counts()), flush=True)

elif phase == 'jobs':
    # the live jobs that run on their own schedule and read clocks / attendance
    names = os.environ.get('JOBS', '').split(',')
    for xid in names:
        cron = env.ref(xid, raise_if_not_found=False)
        if not cron:
            print('PROBE job missing', xid); continue
        t = time.time()
        try:
            cron.sudo().method_direct_trigger()
            env.cr.commit()
            print('PROBE job', xid, cron.id, 'ok', round(time.time() - t, 1), flush=True)
        except Exception as exc:  # noqa: BLE001
            env.cr.rollback()
            print('PROBE job', xid, cron.id, 'ERROR', repr(exc)[:300], flush=True)
    env.invalidate_all()
    print('PROBE after-jobs', json.dumps(counts()))

elif phase == 'conflict':
    # What happens LATER, once the rules are confirmed and a past roster day is published, for people whose
    # day already has a time-clock attendance row: run the rules calculation on up to 40 such roster rows.
    # Everything is ROLLED BACK at the end (no commit) - the copy keeps its state for the undo proof.
    from collections import Counter
    env.cr.execute("""select r.id from hr_shift_planning r
        where r.date between '2026-11-19' and '2026-11-23' and r.state='draft' and r.pb_policy_id is not null
          and exists (select 1 from hr_attendance a where a.employee_id=r.employee_id
                      and a.check_in < r.end_datetime + interval '4 hours' and coalesce(a.check_out, a.check_in) > r.start_datetime - interval '4 hours')
        order by r.date, r.id limit 40""")
    ids = [r[0] for r in env.cr.fetchall()]
    env.cr.execute("select count(*) from hr_shift_planning r where r.date between '2026-11-19' and '2026-11-23' and r.state='draft'")
    print('PROBE conflict past draft roster rows 19-23 Nov', env.cr.fetchone()[0], 'sampled with a clock row', len(ids))
    env.cr.execute("update pb_attendance_policy set state='active'")
    env.cr.execute("update hr_shift_planning set state='published' where id = any(%s)", [ids])
    env.invalidate_all()
    tally = Counter()
    for row in env['hr.shift.planning'].sudo().browse(ids):
        try:
            with env.cr.savepoint():
                ok = row._process_calculation()
                tally['calculated' if ok else 'not sent: %s' % ((row.pb_calculation_status or 'day guarded')[:100])] += 1
        except Exception as exc:  # noqa: BLE001
            tally[str(exc)[:120]] += 1
    for k, v in tally.most_common():
        print('PROBE conflict', v, '|', k)
    # the same rows WITHOUT the clock rows (as if they had never been made), still inside the rollback
    env.cr.execute("update pb_clock_punch set attendance_id=null")
    env.cr.execute("delete from hr_attendance where pb_entry_source='device' and pb_policy_roster_id is null")
    env.invalidate_all()
    tally = Counter()
    for row in env['hr.shift.planning'].sudo().browse(ids):
        try:
            with env.cr.savepoint():
                ok = row._process_calculation()
                tally['calculated' if ok else 'not sent: %s' % ((row.pb_calculation_status or 'day guarded')[:100])] += 1
        except Exception as exc:  # noqa: BLE001
            tally[str(exc)[:120]] += 1
    for k, v in tally.most_common():
        print('PROBE conflict-without-clock-rows', v, '|', k)
    env.cr.rollback()
    print('PROBE conflict rolled back', json.dumps(counts()))

elif phase == 'chain':
    # October for five people with clock rows: attendance -> weekly timesheet -> what a pay run would read.
    # ROLLED BACK at the end. People are numbered P1..P5 in the output (no names, no numbers).
    from datetime import date, timedelta
    env.cr.execute("""select employee_id from hr_attendance where check_in >= '2026-10-01' and check_in < '2026-11-01'
                      group by 1 having count(*) >= 18 order by employee_id limit 5""")
    emps = env['hr.employee'].sudo().browse([r[0] for r in env.cr.fetchall()])
    Packet = env['pb.timesheet.packet'].sudo()
    weeks = [date(2026, 9, 29) + timedelta(days=7 * i) for i in range(5)]   # Mondays 29 Sep .. 27 Oct
    for n, emp in enumerate(emps, 1):
        env.cr.execute("""select count(*), round(sum(worked_hours)::numeric, 1) from hr_attendance
                          where employee_id=%s and check_in >= '2026-09-30 17:00' and check_in < '2026-10-31 17:00'""", [emp.id])
        rows, hours = env.cr.fetchone()
        out = []
        for wk in weeks:
            p = Packet.packet_for(emp, wk)
            out.append('%s: %sh %sd ot%s %s' % (wk.strftime('%d %b'), p.reg_hours, p.days_with_hours, p.ot_hours, p.state))
        approved = Packet.approved_in_period(emp.id, date(2026, 10, 1), date(2026, 10, 31))
        print('PROBE chain P%s attendance Oct rows %s hours %s | weeks %s | approved weeks for an October pay run %s | rule set %s' % (
            n, rows, hours, ' ; '.join(out), len(approved), emp.pb_attendance_policy_id.state or 'none'))
    co = env['res.company'].browse(1)
    print('PROBE chain company reads approved timesheets for pay:', co.pb_timesheet_payroll)
    for cfg in env['hr.formula.config'].sudo().search([]):
        codes = {r.code for r in cfg.rule_ids if r.column_type == 'input'}
        print('PROBE chain scheme %s inputs %s; timesheet codes declared: %s' % (
            cfg.id, len(codes), sorted(codes & {'REGHRS', 'TOTHRS', 'WORKDAYS', 'OTHRS150', 'OTHRS200', 'OTHRS300', 'OTHRSNGT', 'BONHRS'}) or 'none'))
    env.cr.rollback()
    print('PROBE chain rolled back', json.dumps(counts()))
