# pb_orgchart security

P1 adds no model with records (`pb.orgchart` is an AbstractModel facade), so
there is no `ir.model.access.csv`. Reading the chart needs `hr.employee` read
access, which the People hub's `EMPLOYEE_GATE` already requires; the facade
reads employees as the signed-in user (no `sudo()`).

P2's write RPCs check `hr.group_hr_user` or `base.group_system` on the server
(`may_write` in the payload is the same judge).
