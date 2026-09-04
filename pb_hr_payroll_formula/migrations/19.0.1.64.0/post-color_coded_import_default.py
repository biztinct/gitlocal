# -*- coding: utf-8 -*-
"""Existing configurations adopt the color-coded Excel import.

`use_color_coded_excel_import` shipped with `default=False` and this version
flips the default to True, because the color-coded reader is the ONLY import
path that reads header font colour — and font colour is what marks a column as
a contract component (red) or as requiring a fresh contract (red + underline).
With the flag off, `_import_from_excel` falls through to the colour-blind
reader, every rule lands with `is_contract_component = False`, and no advantage
template is ever created however the workbook was formatted. Found live on abm:
"Bonus - STIP" is genuinely red in ABM Template.xlsx, yet imported unflagged.

WHY A MIGRATION. An Odoo field default applies at CREATE time only, so the new
default reaches new configurations and never the ones already in the database —
which are exactly the ones the owner is importing into today.

WHAT IS NOT TOUCHED. Only the False rows move, so a configuration somebody
deliberately turned off stays off on the next `-u`... which is indistinguishable
from a row that simply never had the flag set. That ambiguity is accepted here:
the previous default was False, so essentially every existing row is an
un-chosen False rather than a chosen one, and the flag only decides how the
NEXT import reads a workbook — it re-reads nothing and rewrites no rule that
already exists. An operator who wants the colour-blind reader back unticks it
in Settings -> Advanced.
"""
import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    Config = env.get('hr.formula.config')
    # The addons tree is shared by every database on this box while a schema
    # arrives with that database's own upgrade, so the registry knowing the
    # field is not the schema having the column (W116).
    if Config is None or 'use_color_coded_excel_import' not in Config._fields \
            or not table_exists(cr, Config._table):
        _logger.warning(
            "Color-coded import default skipped on %s: hr.formula.config is "
            "not on this database yet.", cr.dbname)
        return

    stale = Config.with_context(active_test=False).search(
        [('use_color_coded_excel_import', '=', False)])
    if not stale:
        _logger.info(
            "Color-coded import default on %s: every configuration already "
            "reads header colour.", cr.dbname)
        return

    stale.write({'use_color_coded_excel_import': True})
    _logger.info(
        "Color-coded import default on %s: %s configuration(s) switched on "
        "(%s). Red headers now mark contract components on the next import.",
        cr.dbname, len(stale), ', '.join(stale.mapped('name')[:10]))
