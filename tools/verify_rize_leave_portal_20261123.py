"""Verify Loi's actual portal service with his existing permissions; rollback all tests."""
import contextlib
import json
from pathlib import Path
assert env.cr.dbname=='rize'
u=env['res.users'].browse(2579)
assert u.login=='loi@rize.farm' and u.share
ctx=dict(env.context,allowed_company_ids=[1],lang='en_US',tracking_disable=True,
         mail_create_nosubscribe=True,mail_notify_force_send=False,mail_auto_subscribe_no_notify=True)
ess=env['pb.ess.workforce'].with_user(u).with_context(ctx)
assert ess._require_own_employee().id==3290
data=ess.get_my_leave()
balances={x['id']:x['balance'] for x in data['balances']}
assert balances[140]==18.5 and balances[141]==7.5
checks=[]
for type_id,left in [(140,18.5),(141,7.5)]:
    preview=ess.preview_leave(type_id,'2026-11-24','2026-11-24')
    assert preview['ok'] and not preview['blocked'] and preview['left_before']==left and preview['after']==left-1,preview
    with contextlib.closing(env.cr.savepoint()):
        result=ess.apply_leave(type_id,'2026-11-24','2026-11-24','Rollback-only portal verification')
        assert result['ok'],result
        leave=env['hr.leave'].browse(result['id'])
        assert leave.employee_id.id==3290 and leave.create_uid==u
        checks.append({'type_id':type_id,'preview_before':left,'preview_after':left-1,
                       'submit_state':result['state'],'correct_portal_filer':True,'rolled_back':True})
assert not env['hr.leave'].search_count([('employee_id','=',3290)])
env.cr.rollback()
out={'portal_only_permissions_preserved':True,'own_balances':balances,'checks':checks}
Path('/tmp/rize-leave-portal-result-20261123.json').write_text(json.dumps(out,indent=2))
print('PORTAL_VERIFIED',json.dumps(out))
