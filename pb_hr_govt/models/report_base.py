# Copyright 2025
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import datetime

from odoo import fields, models
from odoo.modules.module import get_module_resource


def _fmt(date_val):
    """Format date to dd/MM/yyyy expected by VN templates."""
    if not date_val:
        return ""
    if isinstance(date_val, str):
        try:
            date_val = fields.Date.from_string(date_val)
        except Exception:
            return date_val
    return date_val.strftime("%d/%m/%Y")


class PbGovtReportBase(models.AbstractModel):
    _name = "pb.govt.report.base"
    _description = "Base model for Vietnamese government XLS reports"

    def _get_employees_in_range(self, company, date_from, date_to):
        """Return employees with active contract overlap in range."""
        Contract = self.env["hr.contract"]
        employees = self.env["hr.employee"].browse()
        contracts = Contract.search(
            [
                ("company_id", "=", company.id),
                ("state", "=", "open"),
                "|",
                "&",
                ("date_end", "!=", False),
                ("date_end", ">=", date_from),
                "&",
                ("date_end", "=", False),
                ("date_start", "<=", date_to),
            ]
        )
        if contracts:
            employees |= contracts.mapped("employee_id")
        return employees

    def _get_payslips_in_range(self, company, date_from, date_to):
        Payslip = self.env["hr.payslip"]
        return Payslip.search(
            [
                ("company_id", "=", company.id),
                ("date_from", "<=", date_to),
                ("date_to", ">=", date_from),
                ("state", "in", ["done", "paid", "verify", "draft"]),
            ]
        )

    def _payslip_lines_map(self, payslips):
        """Return map: employee_id -> {rule_code: total amount} for quick lookup."""
        res = {}
        for slip in payslips:
            emp_map = res.setdefault(slip.employee_id.id, {})
            for line in slip.line_ids:
                emp_map[line.code] = emp_map.get(line.code, 0.0) + line.total
        return res

    def _default_filename(self, report_code, company, date_from):
        suffix = ""
        if date_from:
            if isinstance(date_from, str):
                try:
                    date_from = fields.Date.from_string(date_from)
                except Exception:
                    date_from = None
            if isinstance(date_from, datetime):
                date_from = date_from.date()
            if date_from:
                suffix = date_from.strftime("%Y%m")
        return f"{report_code}_{company.name}_{suffix}".replace(" ", "_")

    def _rule_amount(self, emp_lines, codes, default=0.0):
        """Fetch first non-zero rule amount from a list of codes."""
        for code in codes:
            val = emp_lines.get(code, 0.0)
            if val:
                return val
        return default

    # Location / code lookups
    def _location_codes(self, partner):
        """Return (province_code, district_code, commune_code) using partner or lookup."""
        if not partner:
            return ("000", "000", "000")
        province = getattr(partner, "state_id", False)
        district = getattr(partner, "district_id", False)
        commune = getattr(partner, "city_id", False) or getattr(partner, "commune_id", False)

        province_code = province.code if province and province.code else "000"
        district_code = district.code if district and hasattr(district, "code") and district.code else "000"
        commune_code = commune.code if commune and hasattr(commune, "code") and commune.code else "000"

        # Try lookup table if codes missing
        Lookup = self.env["pb.govt.code.lookup"]
        if province_code == "000" and province and province.name:
            rec = Lookup.search([("lookup_type", "=", "province"), ("name", "ilike", province.name)], limit=1)
            province_code = rec.code if rec else "000"
        if district_code == "000" and district and district.name:
            rec = Lookup.search([("lookup_type", "=", "district"), ("name", "ilike", district.name)], limit=1)
            district_code = rec.code if rec else "000"
        if commune_code == "000" and commune and commune.name:
            rec = Lookup.search([("lookup_type", "=", "commune"), ("name", "ilike", commune.name)], limit=1)
            commune_code = rec.code if rec else "000"
        return (province_code, district_code, commune_code)

    def _hospital_code(self, partner):
        """Attempt to fetch hospital code; fallback to lookup_type=hospital."""
        if not partner:
            return "000"
        hospital_name = getattr(partner, "hospital_name", False) or ""
        Lookup = self.env["pb.govt.code.lookup"]
        if hospital_name:
            rec = Lookup.search([("lookup_type", "=", "hospital"), ("name", "ilike", hospital_name)], limit=1)
            if rec:
                return rec.code
        return "000"

    def _copy_template(self, workbook, template_filename, sheet_names):
        """
        Load an Excel template with openpyxl and copy values into the xlsxwriter workbook.
        Styles are not preserved (xlsxwriter limitation), but layout/labels/row heights/column widths
        are copied where possible.
        Returns a dict {sheet_name: worksheet}.
        """
        import logging

        _logger = logging.getLogger(__name__)

        try:
            import openpyxl
        except ImportError:
            _logger.warning("pb_hr_govt: openpyxl not installed; template %s will be blank", template_filename)
            return {name: workbook.add_worksheet(name) for name in sheet_names}

        path = get_module_resource("pb_hr_govt", "government", template_filename)
        ws_map = {}
        # Prefer xlrd for legacy .xls to avoid noisy openpyxl warnings.
        tpl = None
        if template_filename.lower().endswith(".xls"):
            try:
                import xlrd
            except Exception:
                _logger.error("pb_hr_govt: xlrd not installed; template %s will be blank", template_filename)
                return {name: workbook.add_worksheet(name) for name in sheet_names}
            try:
                tpl = xlrd.open_workbook(path, formatting_info=True)
                _logger.info("pb_hr_govt: loaded template %s with xlrd", template_filename)
            except Exception as exc_xlrd:
                _logger.error("pb_hr_govt: xlrd failed to load %s (%s); template will be blank", template_filename, exc_xlrd)
                return {name: workbook.add_worksheet(name) for name in sheet_names}
        else:
            try:
                tpl = openpyxl.load_workbook(path, data_only=False)
                _logger.info("pb_hr_govt: loaded template %s with openpyxl", template_filename)
            except Exception as exc:
                _logger.warning("pb_hr_govt: openpyxl failed to load %s (%s); trying xlrd", template_filename, exc)
                try:
                    import xlrd
                except Exception:
                    _logger.error("pb_hr_govt: xlrd not installed; template %s will be blank", template_filename)
                    return {name: workbook.add_worksheet(name) for name in sheet_names}
                try:
                    tpl = xlrd.open_workbook(path, formatting_info=True)
                    _logger.info("pb_hr_govt: loaded template %s with xlrd", template_filename)
                except Exception as exc_xlrd:
                    _logger.error("pb_hr_govt: xlrd failed to load %s (%s); template will be blank", template_filename, exc_xlrd)
                    return {name: workbook.add_worksheet(name) for name in sheet_names}

        for name in sheet_names:
            ws = workbook.add_worksheet(name)
            if hasattr(tpl, "sheetnames"):  # openpyxl workbook
                tpl_sheet = tpl[name] if name in tpl.sheetnames else tpl.active
                for idx, dim in tpl_sheet.column_dimensions.items():
                    if dim.width:
                        col_idx = openpyxl.utils.column_index_from_string(idx) - 1
                        ws.set_column(col_idx, col_idx, dim.width)
                for ridx, dim in tpl_sheet.row_dimensions.items():
                    if dim.height:
                        ws.set_row(ridx - 1, dim.height)
                for row in tpl_sheet.iter_rows():
                    for cell in row:
                        if cell.value is not None:
                            ws.write(cell.row - 1, cell.column - 1, cell.value)
            else:  # xlrd workbook (legacy .xls)
                try:
                    tpl_sheet = tpl.sheet_by_name(name)
                except Exception:
                    tpl_sheet = tpl.sheet_by_index(0)
                # column widths
                for col_idx, col in tpl_sheet.colinfo_map.items():
                    if col.width:
                        ws.set_column(col_idx, col_idx, col.width / 256)  # xlrd width units
                # row heights
                for ridx, row in tpl_sheet.rowinfo_map.items():
                    if row.height:
                        ws.set_row(ridx, row.height / 20)  # xlrd row height in twips
                # values
                for r in range(tpl_sheet.nrows):
                    for c in range(tpl_sheet.ncols):
                        val = tpl_sheet.cell_value(r, c)
                        if val != "":
                            ws.write(r, c, val)
            ws_map[name] = ws
        return ws_map

    def _select_employees(self, wizard):
        """Helper to pick employees based on wizard filters."""
        employees = wizard.employee_ids or self._get_employees_in_range(
            wizard.company_id, wizard.date_from, wizard.date_to
        )
        if wizard.department_id:
            employees = employees.filtered(lambda e: e.department_id == wizard.department_id)
        if wizard.contract_type_id:
            employees = employees.filtered(
                lambda e: e.contract_id and e.contract_id.type_id == wizard.contract_type_id
            )
        return employees
