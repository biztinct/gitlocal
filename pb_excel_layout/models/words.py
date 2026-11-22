# -*- coding: utf-8 -*-
"""Every refusal and note of the Excel layout, in plain screen words.

Through `env._` HERE, never as literals in a module-level dict: a literal in
a dict is invisible to the string extractor (T24 / GR58), and a scheduled job
has no request language, so the caller passes the env of the person reading.
"""
try:  # WHITELABEL — the tenant's own name for the product
    from odoo.addons.biz_debrand.models.brand import product_label
except Exception:  # pragma: no cover — biz_debrand absent on this build
    def product_label(env, default='Payobook'):
        return default


def error_words(env, code, params=None):
    p = dict(params or {})
    words = {
        'too_big': env._(
            "This file is larger than 10 MB. Remove what is not needed (old "
            "sheets, large pictures) and upload it again."),
        'old_xls': env._(
            "This is an old-style Excel file (.xls). Open it in Excel, save "
            "it as .xlsx and upload it again."),
        'password': env._(
            "This file is password-protected. Remove the password and upload "
            "it again."),
        'wrong_ext': env._(
            "Only Excel files ending in .xlsx or .xlsm can be used."),
        'not_excel': env._(
            "This file could not be opened as an Excel workbook. Save it from "
            "Excel as .xlsx and upload it again."),
        'too_many_parts': env._(
            "This file is too large once it is opened. Remove what is not "
            "needed and upload it again."),
        'unzipped_too_big': env._(
            "This file is too large once it is opened (over 80 MB). Remove "
            "what is not needed and upload it again."),
        'bad_name': env._(
            "This file has unusual content and cannot be used. Save it again "
            "from Excel and upload the new copy."),
        'unsafe_xml': env._(
            "This file has unusual content and cannot be used. Save it again "
            "from Excel and upload the new copy."),
        'no_workbook': env._(
            "This file does not hold an Excel workbook. Save it from Excel as "
            ".xlsx and upload it again."),
        'unreadable': env._(
            "This file could not be read. Open it in Excel, save it again and "
            "upload the new copy."),
        'sheet_missing': env._(
            "The sheet “%(sheet)s” is not in this file. Pick the sheet that "
            "receives the figures.", sheet=p.get('sheet', '')),
        'chartsheet': env._(
            "“%(sheet)s” is a chart sheet, not a sheet with cells. Pick a "
            "sheet with cells.", sheet=p.get('sheet', '')),
        'bad_cell': env._(
            "“%(cell)s” is not a cell. Click a cell in the grid, or type one "
            "like B6.", cell=p.get('cell', '')),
        'merged': env._(
            "Merged cells (%(ref)s) are in the way of the figures. Unmerge "
            "them in Excel, or start the figures somewhere else.",
            ref=p.get('ref', '')),
        'formula_in_way': env._(
            "A formula that fills several cells (%(ref)s) reaches into the "
            "area where the figures go. Change it in Excel, or start the "
            "figures somewhere else.", ref=p.get('ref', '')),
        'table_in_way': env._(
            "The headings of the Excel table “%(table)s” (%(ref)s) are inside "
            "the area where the figures go. Start the figures at the table's "
            "heading row, or move the table.",
            table=p.get('table', ''), ref=p.get('ref', '')),
        'too_wide': env._(
            "The figures do not fit to the right of %(cell)s. Start further "
            "left.", cell=p.get('cell', '')),
        'too_long': env._(
            "The figures do not fit below %(cell)s. Start higher up.",
            cell=p.get('cell', '')),
        'no_columns': env._("This report has no columns to write yet."),
        'check_failed': env._(
            "The filled file did not pass the final check, so it was not "
            "handed out."),
        'wrong_source': env._("This layout belongs to a different report."),
        'no_layout': env._("This layout is no longer available."),
        'no_source': env._(
            "The report behind this layout is no longer available."),
    }
    return words.get(code) or env._(
        "The layout could not be used. Open it, check the sheet and the "
        "start cell, and try again.")


def note_words(env, notes):
    """The quiet notes that go with a filled file."""
    out = []
    cut = int((notes or {}).get('text_cut') or 0)
    if cut == 1:
        out.append(env._("One cell held more text than Excel allows; its "
                         "text was shortened."))
    elif cut:
        out.append(env._("%s cells held more text than Excel allows; their "
                         "text was shortened.", cut))
    for name in (notes or {}).get('table_left') or []:
        out.append(env._(
            "The Excel table “%s” has a different number of columns, so it "
            "was left as it is. Make it as wide as the report and it will "
            "grow with the rows.", name))
    for name in (notes or {}).get('table_resized') or []:
        out.append(env._("The Excel table “%s” now covers every row.", name))
    return out


def macro_words(env):
    return env._("This file contains macros. %(product)s does not run or "
                 "change them.", product=product_label(env))


def coach_words(env):
    return env._("Point your formulas and charts at whole columns or an "
                 "Excel table so they pick up new rows.")


def recalc_words(env):
    """Owner ruling X-b: one quiet line on the set-up screen."""
    return env._("Totals and charts in your file refresh when it is opened in "
                 "Excel. Some other spreadsheet programs need “Recalculate” "
                 "pressed.")
