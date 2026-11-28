# WFSETUP P10b — the owner-instructed data changes on LIVE sudima, each through the method its screen uses
# (odoo-bin shell; run ONLY after the P10b code is live). PHASE=
#   before   read-only: what is there now (holidays 2026-12 / 2027, built-in extra-hours rules, scheme 7844 clock state)
#   apply    1. Vietnam's 2027 public holidays: Workforce setup step 5 "add the suggested holidays"
#               (`pb.workforce.setup.add_suggested(2027)`; December 2026 has no Vietnamese public holiday)
#            2. built-in extra hours OFF: step 4 "Switch it off" (`extra_hours_off`)
#            3. scheme 7844 "Hours from the clocks": the scheme editor's Connect card (`bp_clock_bind`,
#               `bp_save_settings`): paid days / overtime / premium from the clocks, Sunday hours must stay
#               empty, seven information columns added, clock date 1 Dec 2026. The scheme stays a draft.
# Nothing else: no rules confirmed, no roster published, no clock-ins switched on, no overtime decided,
# no pay run, scheme and contracts untouched. Prints PROBE lines (no names, no employee numbers).
import json, os
from datetime import date

assert env.cr.dbname == 'sudima', 'live sudima only'
phase = os.environ['PHASE']
CID = 7844
config = env['hr.formula.config'].browse(CID)
Studio = env['pb.workforce.setup'].with_company(1)


def P(*a):
    print('PROBE', *a, flush=True)


def state():
    env.cr.execute("""select count(*) filter (where date_from >= '2026-11-30' and date_from < '2027-01-01'),
                             count(*) filter (where date_from >= '2026-12-31' and date_from < '2028-01-01')
                      from resource_calendar_leaves where resource_id is null""")
    dec, y27 = env.cr.fetchone()
    env.cr.execute("select count(*) from hr_attendance_overtime_rule")
    rules = env.cr.fetchone()[0]
    keys = {r.code: r.pb_clock_key for r in config.rule_ids if r.pb_clock_key}
    return {'holidays_dec2026': dec, 'holidays_2027': y27, 'builtin_rules': rules,
            'scheme_state': config.state, 'clock_from': str(config.pb_clock_from or ''), 'clock_keys': keys,
            'inputs': len(config.rule_ids.filtered(lambda r: r.column_type == 'input')),
            'contracts_running': env['hr.contract'].search_count([('state', '=', 'open')]),
            'policy': [(p.id, p.state) for p in env['pb.attendance.policy'].search([])],
            'published_roster': env['hr.shift.planning'].search_count([('state', '=', 'published')]),
            'clock_ins_on': env['pb.clock.connector'].search([('publish_punches', '=', True)]).ids,
            'overtime': env['hr.overtime.request'].search_count([]), 'payslips': env['hr.payslip'].search_count([])}


if phase == 'before':
    P('before', json.dumps(state(), default=str))
    env.cr.rollback()

elif phase == 'apply':
    before = state()
    P('before', json.dumps(before, default=str))
    # 1. holidays 2027 (step 5's own method)
    res = Studio.add_suggested(2027)
    rows = env['resource.calendar.leaves'].browse(res['ids'])
    P('holidays added', res['added'], res['summary'], 'ids', res['ids'])
    P('holidays list', [(str(r.date_from)[:16], str(r.date_to)[:16], r.name, r.pb_holiday_kind) for r in rows.sorted('date_from')])
    # 2. built-in extra hours off (step 4's own method)
    res = Studio.extra_hours_off()
    P('extra hours', res['summary'], 'saved on company', bool(env.company.sudo().pb_wfs_extra_hours_saved))
    # 3. scheme 7844 clock mapping (the scheme editor's Connect card)
    Bp = env['pb.blueprint.studio'].with_company(1)
    by_code = {r.code: r.id for r in config.rule_ids}
    for key, code in [('clock.paid_days', 'VNPAIDDAYS'), ('clock.ot_hours', 'VNOTHOURS'),
                      ('clock.ot_premium_hours', 'VNPREMHOURS'), ('clock.empty', 'VNSUNDAYHOURS')]:
        r = Bp.bp_clock_bind(CID, key, by_code[code])
        P('bind', key, code, r.get('ok'), r.get('reason', ''))
        assert r.get('ok'), r
    for key in ('clock.worked_days', 'clock.paid_leave_days', 'clock.holiday_days', 'clock.paid_normal_hours',
                'clock.actual_hours', 'clock.late_minutes', 'clock.over_limit_hours'):
        r = Bp.bp_clock_bind(CID, key, 'new')
        P('bind new', key, r.get('ok'), r.get('reason', ''))
        assert r.get('ok'), r
    r = Bp.bp_save_settings(CID, {'pb_clock_from': '2026-12-01'})
    P('clock date', r.get('ok'), config.pb_clock_from, r.get('reason', ''))
    assert r.get('ok') and config.pb_clock_from == date(2026, 12, 1)
    after = state()
    for k in ('scheme_state', 'contracts_running', 'policy', 'published_roster', 'clock_ins_on', 'overtime', 'payslips'):
        assert after[k] == before[k], (k, before[k], after[k])
    new_cols = [(r.column_letter, r.code, r.name, r.net_role, r.appears_on_payslip) for r in config.rule_ids if r.code.startswith('CLK')]
    P('new information columns', new_cols)
    P('after', json.dumps(after, default=str))
    env.cr.commit()
