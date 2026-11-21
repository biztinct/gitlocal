# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Phase K — seed the VN daily OT cap on the pre-existing global ceiling row.

``pb.ot.ceiling`` gained ``daily_cap`` this version. The seed record
(``ot_ceiling_default``) is shipped ``noupdate="1"``, so on an ALREADY-installed
DB the new ``daily_cap=4.0`` in the data XML is NOT applied to the existing row
(it stays at the field default, 0.0 = not enforced). Set it here — but only if
the admin hasn't already chosen a value, so a deliberate 0 (or any custom cap)
survives. Idempotent: re-running finds daily_cap already set and no-ops.
"""


def migrate(cr, version):
    cr.execute("""
        UPDATE pb_ot_ceiling SET daily_cap = 4.0
        WHERE daily_cap = 0.0
          AND id IN (SELECT res_id FROM ir_model_data
                     WHERE module = 'pb_hr_workforce'
                       AND name = 'ot_ceiling_default')
    """)
