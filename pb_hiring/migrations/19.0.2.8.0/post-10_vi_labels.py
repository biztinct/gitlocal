"""Vietnamese for the rebuilt Hiring screens (ledger LR70).

The screen words themselves come from i18n/vi_VN.po (code translations, read
at run time). The one SEEDED value the screens show that had no Vietnamese is
the Standard column preset's name: fill `vi_VN` only where the row still
carries the product's English ("Standard") and has no Vietnamese of its own
(missing, or equal to the English). A name somebody typed is never touched.
Idempotent: a second run matches nothing.
"""
import logging

_logger = logging.getLogger(__name__)

STANDARD_EN = 'Standard'
STANDARD_VI = 'Tiêu chuẩn'


def migrate(cr, version):
    cr.execute("SELECT 1 FROM res_lang WHERE code = 'vi_VN' AND active")
    if not cr.fetchone():
        return
    cr.execute("""
        UPDATE pb_hiring_stage_preset
           SET name = name || jsonb_build_object('vi_VN', %s::text)
         WHERE name->>'en_US' = %s
           AND (name->>'vi_VN' IS NULL OR name->>'vi_VN' = %s)
    """, (STANDARD_VI, STANDARD_EN, STANDARD_EN))
    _logger.info('pb_hiring 19.0.2.8.0: Vietnamese name on %s Standard preset(s)', cr.rowcount)
