# -*- coding: utf-8 -*-
"""1.19.0 -> 1.20.0 (WF2 P6a, closeout item 12) — "Other request" status words
in Vietnamese and Indonesian.

Workflow Studio shows the statuses of an "Other request" (Approvals' generic
request) as the stages of that record type. They are a selection of
`biz_approval_workflow`, whose `.po` now carries them; a selection label is a
stored value, loaded only when that module is upgraded, and that module (38
dependents, shared with another session, ledger G29) is not upgraded by this
phase. So the stored labels are written here, from that module's own `.po`,
only where a label has no translation yet in that language (never
overwriting). Idempotent.
"""
import logging

from odoo.tools.misc import file_path
from odoo.tools.translate import PoFileReader

_logger = logging.getLogger(__name__)

PREFIX = 'selection__biz_approval_generic_request__state__'


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api
    env = api.Environment(cr, SUPERUSER_ID, {})
    langs = env['res.lang'].sudo().search([('code', 'in', ['vi_VN', 'id_ID']), ('active', '=', True)]).mapped('code')
    written = 0
    for code in langs:
        try:
            path = file_path('biz_approval_workflow/i18n/%s.po' % code)
        except FileNotFoundError:
            continue
        with open(path, 'rb') as handle:
            entries = [e for e in PoFileReader(handle)
                       if e.get('module') == 'biz_approval_workflow' and e.get('type') == 'model'
                       and str(e.get('imd_name') or '').startswith(PREFIX) and e.get('value')]
        for entry in entries:
            row = env.ref('biz_approval_workflow.%s' % entry['imd_name'], raise_if_not_found=False)
            if not row or row._name != 'ir.model.fields.selection':
                continue
            english = row.with_context(lang='en_US').name
            if row.with_context(lang=code).name != english:
                continue  # already has its own words in that language
            row.update_field_translations('name', {code: entry['value']})
            written += 1
    _logger.info('pb_lifecycle 1.20.0: %s "Other request" status words translated', written)
