#!/usr/bin/env python3
"""Audited, tenant-specific repair; dry-run by default, never delete departments.

Run as PostgreSQL owner while the application is stopped for --apply. Rehearse
on a disposable clone first. Supply a permanent evidence directory on Rize.
No ORM writes: changing department identity must not trigger manager/contract
onchanges or create employee versions. All non-department values are checked.
"""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extras import register_default_jsonb

register_default_jsonb(loads=lambda value: json.loads(value, parse_float=Decimal))


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')


def run(database, plan_path, evidence, apply=False):
    assert database == 'rize' or database.startswith('_test_rize_dept_'), database
    plan = json.loads(plan_path.read_text())
    evidence.mkdir(parents=True, exist_ok=False)
    conn = psycopg2.connect(dbname=database)
    conn.set_session(isolation_level='SERIALIZABLE')
    cr = conn.cursor()
    cr.execute("SET LOCAL lock_timeout='10s'")
    cr.execute("SELECT pg_advisory_xact_lock(hashtext('rize_department_consolidation'))")
    cr.execute('LOCK TABLE hr_department IN SHARE ROW EXCLUSIVE MODE')
    mapping = {old: min(g['ids']) for g in plan['groups'] for old in g['ids'] if old != min(g['ids'])}
    all_ids = [i for g in plan['groups'] for i in g['ids']]
    old_ids = sorted(mapping)
    cr.execute('SELECT to_jsonb(d) FROM hr_department d ORDER BY id')
    depts = [r[0] for r in cr.fetchall()]
    by_id = {d['id']: d for d in depts}
    if all(not by_id[i]['active'] for i in old_ids):
        assert sum(bool(d['active']) for d in depts) == plan['expected_active_after']
        dump(evidence/'result.json', {'status':'already applied', 'changed':False})
        conn.rollback()
        return
    assert sum(bool(d['active']) for d in depts) == plan['expected_active_before']
    ignored = {'id','create_uid','write_uid','create_date','write_date','parent_path','master_department_id'}
    for group in plan['groups']:
        rows = [by_id[i] for i in group['ids']]
        baseline = {k:v for k,v in rows[0].items() if k not in ignored}
        assert baseline['name'] == group['name'] and baseline['company_id'] == group['company']
        assert baseline['parent_id'] == group['parent']
        assert all({k:v for k,v in row.items() if k not in ignored} == baseline for row in rows), group
        assert not baseline['manager_id'] and not baseline['parent_id'] and not baseline['pb_cost_centre_id']
        assert all(row['master_department_id']==row['id'] and row['parent_path']==str(row['id'])+'/' for row in rows)
    # Discover every actual FK, including fields from other installed modules.
    cr.execute("""SELECT conrelid::regclass::text,a.attname FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=ANY(c.conkey)
        WHERE confrelid='hr_department'::regclass AND contype='f'""")
    refs = cr.fetchall()
    grouped = defaultdict(list)
    for table,col in refs:
        if table == 'hr_department':
            if col == 'parent_id':
                cr.execute('SELECT count(*) FROM hr_department WHERE parent_id=ANY(%s)',(all_ids,))
                assert cr.fetchone()[0] == 0, 'Nested department requires an explicit hierarchy plan'
            continue  # Archived roots retain their original path/master identity.
        grouped[table].append(col)
    snapshots = {}
    for table,cols in grouped.items():
        where=sql.SQL(' OR ').join(sql.SQL('{}=ANY(%s)').format(sql.Identifier(c)) for c in cols)
        cr.execute(sql.SQL('SELECT to_jsonb(t) FROM {} t WHERE {}').format(sql.Identifier(table),where),tuple(all_ids for _ in cols))
        rows=[r[0] for r in cr.fetchall()]
        if rows:
            # This particular repair has only row models, never relation-table collisions.
            assert all('id' in r for r in rows), ('Unreviewed relation table',table)
            snapshots[table] = rows
    allowed = {'hr_version','hr_leave','hr_work_entry','pb_fact_line','pb_fact_emp','hr_full_final_settlement','pb_budget_line'}
    assert set(snapshots) <= allowed, ('New dependencies require review',set(snapshots)-allowed)
    # Refuse configured membership/routing rules and saved numeric filters. Live
    # audit found no department-specific rule references or stored domains.
    cr.execute("SELECT id,domain FROM ir_filters WHERE domain ILIKE '%department%'")
    assert not cr.fetchall(), 'Saved department filters need explicit remapping'
    cr.execute("SELECT id,domain_force FROM ir_rule WHERE domain_force ILIKE '%department%'")
    rules=cr.fetchall()
    import re
    assert all(not re.search(r"(?:department_id|department_ids)['\"]\s*,\s*['\"](?:=|in|child_of)['\"]\s*,\s*(?:\[\s*)?\d",domain) for _,domain in rules), 'Numeric department access rule requires review'
    protected=['hr_employee','hr_contract','hr_payslip','hr_payslip_line','hr_formula_scheme_assignment']
    def digest(table):
        cr.execute(sql.SQL("SELECT count(*),md5(string_agg(md5(to_jsonb(t)::text), '' ORDER BY id)) FROM {} t").format(sql.Identifier(table)))
        return cr.fetchone()
    hashes={t:digest(t) for t in protected}
    dump(evidence/'departments-before.json',depts)
    dump(evidence/'references-before.json',snapshots)
    dump(evidence/'mapping.json',mapping)
    report={'database':database,'departments_archived':len(mapping),'groups':len(plan['groups']),'references':{},'protected':hashes}
    for table,cols in grouped.items():
        if table not in snapshots:continue
        for col in cols:
            changed=0
            for old,new in mapping.items():
                cr.execute(sql.SQL('UPDATE {} SET {}=%s WHERE {}=%s').format(sql.Identifier(table),sql.Identifier(col),sql.Identifier(col)),(new,old))
                changed+=cr.rowcount
            report['references'][table+'.'+col]=changed
        # Every row must match its original after changing ONLY department IDs.
        cr.execute(sql.SQL('SELECT to_jsonb(t) FROM {} t WHERE id=ANY(%s)').format(sql.Identifier(table)),([r['id'] for r in snapshots[table]],))
        after={r[0]['id']:r[0] for r in cr.fetchall()}
        for row in snapshots[table]:
            expected=dict(row)
            for col in cols:expected[col]=mapping.get(row[col],row[col])
            assert after[row['id']]==expected, (table,row['id'])
    # Auto budget rows must become one row per department/month/type; otherwise
    # the nightly updater would re-total only one duplicate and double count.
    budget=snapshots.get('pb_budget_line',[])
    assert all(r['pb_source']=='auto' and not r['forecast_cost'] and not r['forecast_headcount'] and r['pb_unbudgeted'] and not r['scenario_ref'] for r in budget)
    cr.execute("SELECT count(*) FROM pg_constraint WHERE confrelid='pb_budget_line'::regclass AND contype='f'")
    assert cr.fetchone()[0]==0, 'Budget references require explicit merge handling'
    cr.execute("SELECT count(*) FROM mail_message WHERE model='pb.budget.line' AND res_id=ANY(%s)",([r['id'] for r in budget],))
    assert cr.fetchone()[0]==0, 'Budget conversation history requires explicit handling'
    budget_groups=defaultdict(list)
    for row in budget:
        key=(row['company_id'],mapping.get(row['department_id'],row['department_id']),str(row['period_month']),row['pb_budget_type'])
        budget_groups[key].append(row)
    removed=0
    for key,rows in budget_groups.items():
        assert len({r['pb_currency_id'] for r in rows})==1, ('Mixed budget currencies',key)
        if len(rows)==1:continue
        keep=min(r['id'] for r in rows)
        amount=sum(Decimal(str(r['actual_cost'] or 0)) for r in rows)
        heads=sum(r['actual_headcount'] or 0 for r in rows)
        cr.execute('UPDATE pb_budget_line SET actual_cost=%s,actual_headcount=%s,variance_amount=%s,variance_pct=0 WHERE id=%s',(amount,heads,-amount,keep))
        ids=[r['id'] for r in rows if r['id']!=keep]
        cr.execute('DELETE FROM pb_budget_line WHERE id=ANY(%s)',(ids,));removed+=cr.rowcount
    report['derived_budget_duplicates_consolidated']=removed
    # Verify per-currency/month monetary and headcount totals without float rounding.
    def budget_totals(rows):
        out=defaultdict(lambda:[Decimal(0),0,Decimal(0),0])
        for r in rows:
            k=(r['company_id'],str(r['period_month']),r['pb_currency_id'],r['pb_budget_type'])
            for i,f in enumerate(('actual_cost','actual_headcount','forecast_cost','forecast_headcount')):out[k][i]+=Decimal(str(r[f] or 0))
        return dict(out)
    cr.execute('SELECT to_jsonb(t) FROM pb_budget_line t WHERE department_id=ANY(%s)',(all_ids,))
    assert budget_totals(budget)==budget_totals([r[0] for r in cr.fetchall()])
    cr.execute('UPDATE hr_department SET active=false WHERE id=ANY(%s)',(old_ids,))
    assert cr.rowcount==len(mapping)
    for table,cols in grouped.items():
        for col in cols:
            cr.execute(sql.SQL('SELECT count(*) FROM {} WHERE {}=ANY(%s)').format(sql.Identifier(table),sql.Identifier(col)),(old_ids,))
            assert cr.fetchone()[0]==0,(table,col)
    for table,before in hashes.items():assert digest(table)==before,table
    cr.execute('SELECT count(*) FROM hr_department WHERE active');assert cr.fetchone()[0]==plan['expected_active_after']
    cr.execute('SELECT count(*) FROM hr_department');assert cr.fetchone()[0]==len(depts)
    cr.execute('SELECT name,company_id,parent_id FROM hr_department WHERE active GROUP BY 1,2,3 HAVING count(*)>1');assert not cr.fetchall()
    report['status']='applied' if apply else 'dry-run passed'
    dump(evidence/'result.json',report)
    if apply:conn.commit()
    else:conn.rollback()
    print(json.dumps(report,default=str))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',required=True)
    parser.add_argument('--plan',type=Path,default=Path(__file__).with_name('rize_department_consolidation_20261121.json'))
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    run(args.database,args.plan,args.evidence,args.apply)
