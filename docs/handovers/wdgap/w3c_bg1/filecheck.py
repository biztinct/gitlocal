# READ-ONLY, writes nothing (in-memory wizard, rollback): the bank file's own row
# check (`_row_sources`) for the people of each pay run, whatever the payslip's
# state (no run is finished on these sites). Who would be left out, and why.
import json
from collections import Counter
cr = env.cr  # noqa: F821
Wiz = env['vietnam.bank.export.wizard'].sudo()  # noqa: F821
Reg = env['pb.bank.registry']  # noqa: F821
out = {}
for run in env['hr.payslip.run'].sudo().search([], order='id'):  # noqa: F821
    wiz = Wiz.new({'payslip_run_id': run.id})
    reasons = Counter()
    paid = 0
    for idx, slip in enumerate(run.slip_ids, start=1):
        _s, why, _n = wiz._row_sources(slip, idx, Reg)
        why = [w for w in why if w != 'no net pay']   # draft slips have no figures yet
        if why:
            reasons[', '.join(why)] += 1
        else:
            paid += 1
    out['%s %s' % (run.id, run.name)] = {'people': len(run.slip_ids), 'in_file': paid,
                                         'left_out': dict(reasons)}
print(json.dumps(out, indent=1, ensure_ascii=False))
json.dump(out, open('/tmp/bg1w3c/%s-filecheck.json' % cr.dbname, 'w'), indent=1, ensure_ascii=False)
cr.rollback()
