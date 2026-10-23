# Review I-H3: profile_rule_own shipped with a `create_uid` OR-branch, letting a
# self-authored request pass the rule regardless of whose employee it targeted.
# The record is noupdate=1, so the tightened domain needs this migration (C18.72).


def migrate(cr, version):
    cr.execute("""
        UPDATE ir_rule r
        SET domain_force = %s
        FROM ir_model_data d
        WHERE d.model = 'ir.rule' AND d.res_id = r.id
          AND d.module = 'pb_me_portal' AND d.name = 'profile_rule_own'
    """, ("[('employee_id.user_id', '=', user.id)]",))
