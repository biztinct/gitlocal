# -*- coding: utf-8 -*-
"""NAV P3d — the two Vietnamese words the Ask HR board shares with the rest
of the module now read the same everywhere.

"With HR" is "Nhân sự đang xử lý" (it was "Đang ở Nhân sự"; lowercase in the
portal's counter line) and "Nobody has it yet" is "Chưa ai nhận" (it was
"Chưa có ai nhận"), the words the owner gave for the board and the words Learn
already uses. Code words (the board, "My requests") read the .po directly, but
STORED words keep their old value through an ordinary upgrade, because an
upgrade never overwrites a translation that is already there (LOOK ledger: a
translation fix is two fixes).

TARGETED, NOT A RELOAD (LEARNREV LR20/LR29, P5A_DEPLOY): a module-wide
overwrite load also rewrites shared records another module translated better
(the `display_name` field label, model names). So only these stored values
change, and only where the stored Vietnamese is still the OLD word:

  * the "With HR" choice of `pb.ask.hr.ticket.state`;
  * the vi_VN arch of pb_ask_hr's OWN views (ir_model_data module pb_ask_hr):
    the search filters, the portal pill and the portal counter line.

Measured on a copy before writing (am_nav_p3c): the selection row, and one
occurrence each in view_pb_ask_hr_ticket_search (both words), pbah_pill and
portal_ask_hr_list (lowercase). Nothing else in the database holds them.
"""
import logging

_logger = logging.getLogger(__name__)

#: (old, new) — exact strings, the longer lowercase variant is distinct text
WORDS = [
    ('Đang ở Nhân sự', 'Nhân sự đang xử lý'),
    ('đang ở Nhân sự', 'nhân sự đang xử lý'),
    ('Chưa có ai nhận', 'Chưa ai nhận'),
]


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE ir_model_fields_selection s
           SET name = jsonb_set(s.name, '{vi_VN}', to_jsonb(%s::text))
          FROM ir_model_fields f
         WHERE f.id = s.field_id AND f.model = 'pb.ask.hr.ticket'
           AND f.name = 'state' AND s.value = 'with_hr'
           AND s.name->>'vi_VN' = %s
    """, ('Nhân sự đang xử lý', 'Đang ở Nhân sự'))
    selections = cr.rowcount
    views = 0
    for old, new in WORDS:
        cr.execute("""
            UPDATE ir_ui_view v
               SET arch_db = jsonb_set(v.arch_db, '{vi_VN}',
                                       to_jsonb(replace(v.arch_db->>'vi_VN', %s, %s)))
              FROM ir_model_data d
             WHERE d.model = 'ir.ui.view' AND d.res_id = v.id AND d.module = 'pb_ask_hr'
               AND v.arch_db ? 'vi_VN' AND v.arch_db->>'vi_VN' LIKE %s
        """, (old, new, '%' + old + '%'))
        views += cr.rowcount
    _logger.info('pb_ask_hr: Vietnamese words updated in place (NAV P3d): '
                 '%s status choice(s), %s view(s); nothing else touched',
                 selections, views)
