# PSCHEME P3 D: "Work it out again" (the Mapping board's button, pb.scheme.board.recompute) for the filled
# company, so "Paid by" is settled now instead of at the next daily job (payobook's job is off by design).
import os
cid = int(os.environ['PS3_CID'])
B = env['pb.scheme.board'].with_company(cid).with_context(allowed_company_ids=[cid])
r = B.recompute(cid)
env.cr.commit()
env.cr.execute("select count(*) filter (where pb_paid_by_stale) from hr_employee where company_id=%s and active", [cid])
print('PROBE settled company', cid, 'changed', r.get('changed'), 'still stale', env.cr.fetchone()[0])
