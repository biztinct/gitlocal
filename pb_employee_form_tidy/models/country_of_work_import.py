# -*- coding: utf-8 -*-
"""TIDY-E item 3a (owner rulings R12/R13) — Country of Work from a file.

Country of Work (`hr.employee.payroll_country`) was already a destination in
Mapping (every writable employee field is, `pb_formula_studio`
`_ec_right_items`), but only under "Other employee fields" and only under its
old name; and a file saying "Việt Nam" or "VNM" was dropped without a word
(`payroll_import_batch._coerce_mapped_value` accepts the choice's key or
label only, and returns None on anything else). Here, from outside:

* Mapping lists it in "Job & organisation" (a lane entry, no new card kind);
* the pay data file and the Updates / Records sheets accept the key, the label
  in any switched-on language, ISO 3-letter codes and common local spellings
  (`hr.employee._pb_country_of_work_key`);
* a word that is still not a country is never a failure: the row is loaded,
  Country of Work is left as it was, the load's log says so, and the pay run
  screen's load result lists the rows.
"""

import logging
import re
import unicodedata

from odoo import _, api, models

from odoo.addons.pb_formula_studio.models.pb_formula_studio import PbFormulaStudio as _StudioBase

_logger = logging.getLogger(__name__)

FIELD = 'payroll_country'

#: Words a pay data file or a sheet may use for a country, folded (lower case,
#: no accents, no spaces or punctuation): ISO 2- and 3-letter codes, English,
#: local names and the Vietnamese / Indonesian spellings. The choice's own keys
#: and labels (in every switched-on language) and the country list's names are
#: tried as well — this table only adds what those do not hold.
COUNTRY_WORDS = {
    'VN': ('vn', 'vnm', 'vietnam', 'vietnamese', 'socialistrepublicofvietnam',
           'cnxhvietnam'),
    'ID': ('id', 'idn', 'indonesia', 'republikindonesia', 'indonesian'),
    'IN': ('in', 'ind', 'india', 'bharat', 'ando', 'indian'),
    'SG': ('sg', 'sgp', 'singapore', 'singapura', 'xingapo', 'xinhgapo'),
    'MY': ('my', 'mys', 'malaysia', 'malaixia'),
    'TH': ('th', 'tha', 'thailand', 'thailan', 'muangthai', 'prathetthai'),
    'KH': ('kh', 'khm', 'cambodia', 'campuchia', 'kampuchea', 'kamboja'),
    'PH': ('ph', 'phl', 'philippines', 'philippin', 'pilipinas', 'filipina'),
}


def fold(text):
    """'Việt Nam' -> 'vietnam'; 'Viet-Nam ' -> 'vietnam'."""
    text = str(text or '').strip().lower().replace('đ', 'd')
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r'[\W_]+', '', text)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def _pb_country_of_work_key(self, value):
        """The Country of Work choice a file's word means, or None.

        Accepts the choice key ("VN"), its label in any switched-on language
        ("Vietnam", "Việt Nam"), an ISO 3-letter code ("VNM") and the common
        spellings in `COUNTRY_WORDS`. Never guesses beyond that: an unknown word
        is None, and the caller says so.
        """
        word = fold(value)
        if not word:
            return None
        field = self._fields[FIELD]
        keys = {fold(code): code for code, _label in field._description_selection(self.env)}
        if word in keys:
            return keys[word]
        Lang = self.env['res.lang']
        for lang, _name in Lang.get_installed():
            for code, label in field._description_selection(self.with_context(lang=lang).env):
                if fold(label) == word:
                    return code
        for code, words in COUNTRY_WORDS.items():
            if code in keys.values() and word in words:
                return code
        # the country list's own names, in every switched-on language
        Country = self.env['res.country'].sudo()
        for lang, _name in Lang.get_installed():
            for country in Country.with_context(lang=lang).search(
                    [('code', 'in', list(keys.values()))]):
                if fold(country.name) == word:
                    return country.code
        return None


class PayrollImportBatch(models.Model):
    _inherit = 'hr.payroll.import.batch'

    def _coerce_mapped_value(self, record, field, value):
        coerced = super()._coerce_mapped_value(record, field, value)
        if coerced is not None or value in (None, ''):
            return coerced
        if getattr(field, 'name', None) == FIELD and record is not None \
                and record._name == 'hr.employee':
            return self.env['hr.employee']._pb_country_of_work_key(value)
        return coerced

    # ------------------------------------------------------- the review
    def _pb_cow_mappings(self):
        self.ensure_one()
        return self._get_model_mappings('hr.employee').filtered(
            lambda m: m.target_field_id.name == FIELD and m.component_id)

    def _pb_cow_unknown_rows(self):
        """`[{'row', 'name', 'value'}]` — rows whose Country of Work word is not
        a country this system knows. A read: nothing is written."""
        self.ensure_one()
        mappings = self._pb_cow_mappings()
        if not mappings:
            return []
        Employee = self.env['hr.employee']
        out = []
        for line in self.import_line_ids.filtered(lambda l: l.employee_id):
            raw = line.get_raw_data() or {}
            for mapping in mappings:
                try:
                    value, has_value = self._writeback_raw_value(
                        raw, mapping.component_id, mapping=mapping, line=line,
                        employee=line.employee_id, allow_column_letter=False)
                except Exception:       # noqa: BLE001 — a note is never fatal
                    _logger.debug("Country of Work check skipped a row", exc_info=True)
                    continue
                if not has_value or value in (None, '') or not str(value).strip():
                    continue
                if self._coerce_mapped_value(line.employee_id, mapping.target_field_id, value) is None \
                        and Employee._pb_country_of_work_key(value) is None:
                    out.append({'row': line.sequence or 0,
                                'name': line.employee_name or line.employee_code or '',
                                'value': str(value).strip()})
                    break
        return out

    @api.model
    def _pb_cow_sentence(self, rows):
        if not rows:
            return ''
        shown = ', '.join(
            _('row %(row)s ("%(value)s")', row=r['row'], value=r['value'][:40])
            for r in rows[:10])
        if len(rows) > 10:
            shown = _('%(list)s and %(n)s more', list=shown, n=len(rows) - 10)
        return _("Country of Work was left as it was for %(n)s row(s): the file's "
                 "value is not a country this system knows — %(list)s. Use a country "
                 "name or code, such as Vietnam or VN.", n=len(rows), list=shown)

    def _get_mapping_updates(self, record, raw_data, mappings=None, line=None,
                             contract=None, employee=None):
        updates = super()._get_mapping_updates(
            record, raw_data, mappings=mappings, line=line,
            contract=contract, employee=employee)
        if record._name == 'hr.employee' and FIELD not in updates and line:
            try:
                for mapping in (mappings or self._get_model_mappings(record._name)).filtered(
                        lambda m: m.destination_type == 'field'
                        and m.target_field_id.name == FIELD and m.component_id):
                    value, has_value = self._writeback_raw_value(
                        raw_data, mapping.component_id, mapping=mapping, line=line,
                        contract=contract, employee=record, allow_column_letter=False)
                    if has_value and value not in (None, '') and str(value).strip():
                        self._log("Country of Work left unchanged on row %s: the "
                                  "file's value is not a known country."
                                  % (line.sequence or '?'))
                        break
            except Exception:           # noqa: BLE001 — a log line is never fatal
                _logger.debug("Country of Work log line skipped", exc_info=True)
        return updates


class PbPayrunWizard(models.AbstractModel):
    _inherit = 'pb.payrun.wizard'

    @api.model
    def attach_spreadsheet(self, *args, **kwargs):
        res = super().attach_spreadsheet(*args, **kwargs)
        if not isinstance(res, dict) or not res.get('ok') or not res.get('batch_id') \
                or res.get('one_time'):
            return res
        try:
            batch = self.env['hr.payroll.import.batch'].browse(res['batch_id']).exists()
            rows = batch._pb_cow_unknown_rows() if batch else []
            if rows:
                res['country_unknown'] = batch._pb_cow_sentence(rows)
        except Exception:               # noqa: BLE001 — a note is never fatal
            _logger.warning("Pay data load: Country of Work note failed", exc_info=True)
        return res


class PbRecordsDesk(models.AbstractModel):
    _inherit = 'pb.records.desk'

    @api.model
    def _selection_key(self, field, value):
        key, why = super()._selection_key(field, value)
        if key is None and why and getattr(field, 'name', None) == FIELD \
                and getattr(field, 'model_name', None) == 'hr.employee':
            found = self.env['hr.employee']._pb_country_of_work_key(value)
            if found:
                return found, None
        return key, why


class PbFormulaStudio(models.AbstractModel):
    _inherit = 'pb.formula.studio'

    # Country of Work is a person's job fact: list it with the job, not under
    # "Other employee fields". Same lanes, one name added at the end of "job".
    _EC_LANES = tuple(
        (key, tuple(
            (model, tuple(names) + ((FIELD,) if key == 'job' and model == 'hr.employee'
                                    and FIELD not in names else ()))
            for model, names in groups))
        for key, groups in _StudioBase._EC_LANES)
