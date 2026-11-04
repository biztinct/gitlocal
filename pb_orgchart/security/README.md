# pb_orgchart security

`pb.orgchart` is an AbstractModel facade: reading the chart needs
`hr.employee` read access (the People hub's `EMPLOYEE_GATE`); the facade reads
employees as the signed-in user. P2's write RPCs check `hr.group_hr_user` or
`base.group_system` on the server (`may_write` in the payload is the same judge).

P3 adds `pb.orgchart.plan` and `pb.orgchart.plan.change`
(`ir.model.access.csv`, `pb_orgchart_security.xml`): HR users read and write
every plan of their companies; any internal user may READ a plan they started
or that an approval route asks them to decide (`seat_user_ids`). Approving
and turning down happen only through the approval engine. The plan's
employee writes happen on approval, as the person who planned them.
