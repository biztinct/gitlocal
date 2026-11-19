# -*- coding: utf-8 -*-
"""My Payobook > My details: custom fields, SEE ONLY (FS-5 item 4, R3).

Subclasses `PbMeDetailsPortal` (precedent: pb_me_tax) and adds one key to
the overview, drawn by a template inherit. No new route, no form, no write:
the page only shows.

THE ELEVATED READ. `_ess_employee()` returns the session's own employee as a
SUDO record (pb_me_portal), so a field's permission would not filter
anything here. The fields are therefore picked by the engine's
`fields_for(model, 'everyone')`, which decides from the field's own
"Who can see it" setting ("Everyone, including the employee") and never from
the caller — an HR-only or administrator-only field cannot reach this page,
whatever the request says (no route here takes an id or a field name).
Country of Work (R10): a field limited to other countries is left out.
"""
import logging

from odoo.http import request

from odoo.addons.pb_me_details.controllers.portal import PbMeDetailsPortal

_logger = logging.getLogger(__name__)


class PbFormBuilderMyDetails(PbMeDetailsPortal):

    def _pbmd_overview(self, emp):
        values = super()._pbmd_overview(emp)
        try:
            values['pbfr_sections'] = self._pbfr_sections(emp)
        except Exception:                               # noqa: BLE001
            # A broken extra card must never take the page down.
            _logger.exception('pb_form_studio_reach: My details extra card failed')
            values['pbfr_sections'] = []
        return values

    def _pbfr_rows(self, record):
        """`[{name, label, value}]` — 'Everyone' fields that apply to
        `record` (a sudo record of the session's own), in field order."""
        if not record:
            return []
        Studio = request.env['pb.form.studio']
        specs = Studio.fields_for(record._name, 'everyone')
        if not specs:
            return []
        values = Studio._pbfs_values_for(record, 'everyone').get(record.id, {})
        memo = {}
        rows = []
        for spec in specs:
            name = spec['name']
            if not Studio._pbfr_applies(record, name, memo):
                continue
            cell = values.get(name) or {}
            rows.append({'name': name, 'label': spec['label'],
                         'value': cell.get('display') or ''})
        return rows

    def _pbfr_sections(self, emp):
        emp = emp.sudo()
        sections = []
        rows = self._pbfr_rows(emp)
        if rows:
            sections.append({'key': 'employee', 'rows': rows,
                             'title': request.env._('Company details')})
        contract = emp.contract_id if 'contract_id' in emp._fields else None
        rows = self._pbfr_rows(contract.sudo()) if contract else []
        if rows:
            sections.append({'key': 'contract', 'rows': rows,
                             'title': request.env._('From your contract')})
        return sections
