# -*- coding: utf-8 -*-
"""TIDY-E — the employee record's "Full details" form and the name
"Country of Work"."""

import logging

from odoo import api, fields, models

from . import form_rules

_logger = logging.getLogger(__name__)

#: Context key that returns the form exactly as the owning modules draw it
#: (tests compare the two; nothing on screen sets it).
NO_TIDY = 'pb_form_tidy_off'


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # Handover 1e: one name on every screen. The People list filter already
    # says "Country of Work"; the field said "Payroll Country" (Settings tab,
    # Updates / Records sheet headings, Mapping). The storage is unchanged:
    # same column, same choices.
    payroll_country = fields.Selection(
        string='Country of Work',
        help="The country this person works and is paid in. It decides which "
             "country boxes show on this record. It is not nationality.")

    # ------------------------------------------------------------ the form
    @api.model
    def _get_view_cache_key(self, view_id=None, view_type='form', **options):
        key = super()._get_view_cache_key(view_id, view_type, **options)
        return key + (bool(self.env.context.get(NO_TIDY)),)

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """The employee form, with the TIDY-E rules applied (`form_rules`).

        Only the stock employee form (`hr.view_employee_form` and everything
        inheriting it — the "Full details" page). Other employee views, and
        the side panel, My Payobook and reports, are not touched.
        """
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type != 'form' or self.env.context.get(NO_TIDY) or not view:
            return arch, view
        base = self.env.ref('hr.view_employee_form', raise_if_not_found=False)
        if not base or view.id != base.id:
            return arch, view
        try:
            form_rules.apply_rules(arch)
            form_rules.show_full_dates(arch, self.env, self._name)
            self._pb_tidy_tab_names(arch)
        except Exception:       # noqa: BLE001 — a tidy-up must never cost the form
            _logger.exception("Employee form tidy-up could not be applied; "
                              "the form is shown as the modules draw it.")
            arch, view = super()._get_view(view_id, view_type, **options)
        return arch, view

    @api.model
    def _pb_tidy_tab_names(self, arch):
        """FS follow-up 1 — two tab names that stayed English for Vietnamese
        and Indonesian readers: "Employment profile" (pb_employee_vault, a page
        with no name) and "Payroll facts" (pb_payroll_mapping_vn, rize only).

        Done here, not by an xpath in a view: one owner is not installed on
        every database (an xpath to its page would fail to install there),
        and the owners' modules are shipped by other work streams. The arch
        reaching this method is already in the reader's language, so a page
        still carrying the English words has no translation of its own; it
        gets this module's words (code terms, read from this module's .po —
        there is no stored copy to fix). An owner translation, once it exists,
        wins because the English words are then gone.
        """
        lang = self.env.lang or 'en_US'
        if lang == 'en_US':
            return
        names = {
            'Employment profile': self.env._("Employment profile"),
            'Payroll facts': self.env._("Payroll facts"),
        }
        for page in arch.iter('page'):
            word = names.get(page.get('string'))
            if word:
                page.set('string', word)

    # ---------------------------------------------------- timezone note
    def _compute_pb_work_timezone_note(self):
        """The Settings tab says where the timezone came from; say it with the
        box's screen name."""
        super()._compute_pb_work_timezone_note()
        for employee in self:
            note = employee.pb_work_timezone_note or ''
            if note.startswith('Payroll Country:'):
                employee.pb_work_timezone_note = 'Country of Work:' + note[len('Payroll Country:'):]
