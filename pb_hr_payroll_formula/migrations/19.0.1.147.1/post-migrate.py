# -*- coding: utf-8 -*-
"""Proration basis "Calendar Days" read "Lịch Ngày" (word-for-word) in
Vietnamese on the Adjust › Proration drawer (LEARN REFRESH step 6).

A selection label is a STORED translation: fixing the .po alone never
reaches a database that already holds the old value (LOOK L24), because an
upgrade only fills a language that is missing. This rewrites exactly the old
machine value and nothing else, so a label somebody changed by hand stays.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE ir_model_fields_selection s
           SET name = jsonb_set(s.name, '{vi_VN}', to_jsonb('Ngày lịch'::text))
          FROM ir_model_fields f
         WHERE f.id = s.field_id
           AND f.model IN ('hr.formula.config', 'hr.payroll.proration.line')
           AND f.name = 'proration_basis'
           AND s.value = 'calendar'
           AND s.name->>'vi_VN' = 'Lịch Ngày'
    """)
