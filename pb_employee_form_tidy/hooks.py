# -*- coding: utf-8 -*-
"""TIDY-E2 — the stored translation of the "Country of Work" label.

Relabelling an EXISTING field from this module does not replace its stored
translation in a language that already has one: installing loads this
module's .po without overwriting, so Vietnamese kept the old "Payroll Country"
wording ("Bảng lương Quốc gia", from pb_hr_payroll_base) on all five live
databases (deploy report TE-D1). A translation fix is two fixes: the .po
(`i18n/vi_VN.po`, `i18n/id_ID.po`) AND the stored value — written here, on a
fresh install (post_init_hook) and on upgrade (migrations/19.0.1.1.0).

Only a value that is still one of the known old / untranslated wordings is
replaced; a label a customer typed themselves is left alone.
"""

import logging

_logger = logging.getLogger(__name__)

LABEL = {
    'vi_VN': 'Quốc gia làm việc',
    'id_ID': 'Negara Kerja',
}
#: wordings this module may replace (old label, its old Vietnamese, untranslated)
OLD = {'', 'Payroll Country', 'Country of Work', 'Bảng lương Quốc gia',
       'Negara Penggajian', 'Negara Payroll'}


def fix_country_of_work_label(env):
    """Write the vi / id name of Country of Work where it is still an old
    wording. Returns `{lang: new value}` for what it changed."""
    field = env['ir.model.fields'].sudo()._get('hr.employee', 'payroll_country')
    if not field:
        return {}
    installed = {code for code, _name in env['res.lang'].get_installed()}
    env.cr.execute("SELECT field_description FROM ir_model_fields WHERE id = %s", [field.id])
    stored = (env.cr.fetchone() or [{}])[0] or {}
    changes = {}
    for lang, label in LABEL.items():
        if lang not in installed:
            continue
        value = (stored.get(lang) or '').strip()
        if value == label or value not in OLD:
            continue
        changes[lang] = label
    if changes:
        field.update_field_translations('field_description', changes)
        env.registry.clear_cache()
        _logger.info("Country of Work label written for %s", sorted(changes))
    return changes


def post_init_hook(env):
    fix_country_of_work_label(env)
