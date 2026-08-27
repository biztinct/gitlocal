#!/usr/bin/env python3
"""Build complete Vietnamese catalogs for every ``pb_*`` Odoo module.

The script deliberately separates extraction from translation.  Odoo remains
the authority for extracting Python, model metadata, XML/QWeb and ``_t``
JavaScript strings; this tool merges those POT files with reviewed Vietnamese
catalogs and fills only the gaps.

Typical workflow::

    # Export current POT files with Odoo 19 first, then:
    .venv/bin/python tools/refresh_pb_vi.py \
        --pot-root /tmp/pb_i18n_pots \
        --db-export-root /tmp/pb_i18n_db_export \
        --translate-missing

The translation cache is deterministic and reusable.  Existing module
translations always win over shared translation memory, which in turn wins
over the curated payroll glossary and machine translation.
"""

from __future__ import annotations

import argparse
import ast
import html
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Iterable

import polib

from translate_po import DICT_PAYROLL_CORE, SKIP_TERMS, is_vietnamese_text


LANGUAGE = "vi_VN"
GOOGLE_MOBILE_URL = "https://translate.google.com/m"
SEPARATOR = "[[[PBSEP_93A7]]]"
MAX_REQUEST_CHARS = 4_500
MAX_BATCH_ITEMS = 35
LEGACY_MODULES = {
    "pb_hr_payroll_cambodia",
    "pb_hr_payroll_india",
    "pb_hr_payroll_indonesia",
    "pb_hr_payroll_malaysia",
    "pb_hr_payroll_singapore",
    "pb_hr_payroll_thailand",
}

# Tokens that must survive translation byte-for-byte.  The order matters:
# protect whole tags and interpolations before the shorter printf forms.
PROTECTED_RE = re.compile(
    r"(?:"
    r"</?[A-Za-z][^>]*>"
    r"|%\([^)]+\)[#0\- +]?\d*(?:\.\d+)?[diouxXeEfFgGcrsa%](?![A-Za-z])"
    r"|%[#0\- +]?\d*(?:\.\d+)?[diouxXeEfFgGcrsa%](?![A-Za-z])"
    r"|\$\{[^{}]*\}"
    r"|#\{[^{}]*\}"
    r"|\{[A-Za-z_][^{}]*\}"
    r"|&(?:[A-Za-z]+|#\d+|#x[0-9A-Fa-f]+);"
    r"|https?://[^\s<>\"']+"
    r")"
)
PLACEHOLDER_RE = re.compile(
    r"%\([^)]+\)[#0\- +]?\d*(?:\.\d+)?[diouxXeEfFgGcrsa%](?![A-Za-z])"
    r"|%[#0\- +]?\d*(?:\.\d+)?[diouxXeEfFgGcrsa%](?![A-Za-z])"
    r"|\$\{[^{}]*\}|#\{[^{}]*\}|\{[A-Za-z_][^{}]*\}"
)
TAG_RE = re.compile(r"<\s*(/?)\s*([A-Za-z][\w:-]*)\b[^>]*?(/?)>")
JS_T_RE = re.compile(
    r"\b_t\(\s*(?P<quote>['\"`])(?P<value>(?:\\.|(?!\1).)*?)(?P=quote)",
    re.S,
)
XML_TRANSLATABLE_ATTRIBUTES = {"string", "title", "placeholder", "help", "confirm"}
XML_TECHNICAL_FIELD_NAMES = {
    "binding_model_id", "binding_view_types", "code", "context", "domain",
    "inherit_id", "model", "priority", "res_model", "sequence", "tag", "view_mode",
}

# Reviewed entries that need domain judgement or contain markup whose visible
# attributes must be translated while CSS classes and styles remain untouched.
CURATED_OVERRIDES = {
    '<i class="fa fa-building" title="Company" style="font-size: 50px; margin-bottom: 10px; color: #475569;"/>':
        '<i class="fa fa-building" title="Công ty" style="font-size: 50px; margin-bottom: 10px; color: #475569;"/>',
    '<i class="fa fa-file-text" title="Salary Config" style="margin-right: 10px;"/>':
        '<i class="fa fa-file-text" title="Cấu hình lương" style="margin-right: 10px;"/>',
    '<i class="fa fa-check-circle" title="Employees"/>':
        '<i class="fa fa-check-circle" title="Nhân viên"/>',
    '<i class="fa fa-spinner fa-spin" title="Loading" style="font-size: 30px;"/>':
        '<i class="fa fa-spinner fa-spin" title="Đang tải" style="font-size: 30px;"/>',
    '<i class="fa fa-users" title="Department" style="margin-right: 10px;"/>':
        '<i class="fa fa-users" title="Phòng ban" style="margin-right: 10px;"/>',
    '<i class="fa fa-calculator fa-4x text-info" title="Calculate"/>':
        '<i class="fa fa-calculator fa-4x text-info" title="Tính toán"/>',
    '<i class="fa fa-edit fa-4x text-warning" title="Edit Spreadsheet"/>':
        '<i class="fa fa-edit fa-4x text-warning" title="Chỉnh sửa bảng tính"/>',
    '<i class="fa fa-file-text fa-4x text-danger" title="Generate Payslips"/>':
        '<i class="fa fa-file-text fa-4x text-danger" title="Tạo phiếu lương"/>',
    '<i class="fa fa-upload fa-4x text-primary" title="Import Data"/>':
        '<i class="fa fa-upload fa-4x text-primary" title="Nhập dữ liệu"/>',
    '<i class="fa fa-briefcase" title="Unemployment Insurance"/> BHTN':
        '<i class="fa fa-briefcase" title="Bảo hiểm thất nghiệp"/> BHTN',
    '<span class="pb-capability-card__stat-label">Critical</span>':
        '<span class="pb-capability-card__stat-label">Nghiêm trọng</span>',
    '<span class="pb-role-card__label">Gap</span>':
        '<span class="pb-role-card__label">Thiếu hụt</span>',
    '<span class="pb-role-card__label">Target</span>':
        '<span class="pb-role-card__label">Mục tiêu</span>',
    '<span>Day</span>': '<span>Ngày</span>',
    '<span class="k">Net</span>': '<span class="k">Lương thực nhận</span>',
    '<br/><span style="color:#6B7280; font-size:11px;">CELLS MATCHED</span>':
        '<br/><span style="color:#6B7280; font-size:11px;">Ô KHỚP</span>',
    '<br/><span style="color:#6B7280; font-size:11px;">CLUSTERS</span>':
        '<br/><span style="color:#6B7280; font-size:11px;">CỤM</span>',
    '<br/><span style="color:#6B7280; font-size:11px;">EMPLOYEES</span>':
        '<br/><span style="color:#6B7280; font-size:11px;">NHÂN VIÊN</span>',
    "Adv": "Tạm ứng",
    "Emp": "NV",
    "Agg Json": "JSON tổng hợp",
    '<span class="badge badge-success" style="padding: 8px 12px; font-size: 12px; font-weight: bold;">READY FOR APPROVAL</span>':
        '<span class="badge badge-success" style="padding: 8px 12px; font-size: 12px; font-weight: bold;">SẴN SÀNG PHÊ DUYỆT</span>',
    "JSON: {SI: {employee, employer, total}, HI: {...}, ...}":
        "JSON: {SI: {employee, employer, total}, HI: {...}, ...}",
    "JSON: {dimension: {SI: amount, HI: amount, CPF: amount, ...}}":
        "JSON: {dimension: {SI: amount, HI: amount, CPF: amount, ...}}",
    "JSON: {dimension: {amount: total, employees: count}}":
        "JSON: {dimension: {amount: total, employees: count}}",
    "JSON: {dimension: {amount: total, new_hires: count}}":
        "JSON: {dimension: {amount: total, new_hires: count}}",
    "JSON: {dimension: {basic: amount, allowances: amount, ...}}":
        "JSON: {dimension: {basic: amount, allowances: amount, ...}}",
    "JSON: {dimension: {health_insurance: amount, housing: amount, ...}}":
        "JSON: {dimension: {health_insurance: amount, housing: amount, ...}}",
    "JSON: {dimension: {total: amount, per_employee: amount}}":
        "JSON: {dimension: {total: amount, per_employee: amount}}",
    "JSON: {employee_id: {SI, HI, UI, CPF, SSF, NSSF, EPF, SOCSO, ...}}":
        "JSON: {employee_id: {SI, HI, UI, CPF, SSF, NSSF, EPF, SOCSO, ...}}",
    "JSON: {type: {amount, due_date, days_overdue}}":
        "JSON: {type: {amount, due_date, days_overdue}}",
    "JSON: {type: {due_date, paid_date, status}}":
        "JSON: {type: {due_date, paid_date, status}}",
    "This will be used to compute the % fields values; in general it is on basic, but you can also use categories code fields in lowercase as a variable names (hra, ma, lta, etc.) and the variable basic.":
        "Giá trị này dùng để tính các trường phần trăm; thông thường dựa trên lương cơ bản, nhưng bạn cũng có thể dùng mã danh mục viết thường làm tên biến (hra, ma, lta, v.v.) và biến basic.",
    '<i class="fa fa-calendar fa-2x text-warning"/>\n                                <br/><small>Workday</small>':
        '<i class="fa fa-calendar fa-2x text-warning"/>\n                                <br/><small>Ngày làm việc</small>',
    '<i class="fa fa-file-excel-o fa-2x text-success"/>\n                                <br/><small>Excel Import</small>':
        '<i class="fa fa-file-excel-o fa-2x text-success"/>\n                                <br/><small>Nhập Excel</small>',
    '<span class="badge bg-warning text-dark">⚠</span> Columns referenced by main sheet formulas are highlighted':
        '<span class="badge bg-warning text-dark">⚠</span> Các cột được công thức của bảng tính chính tham chiếu sẽ được tô sáng',
    '<span class="badge text-bg-success">\n                                            <i class="fa fa-check"/> Valid\n                                        </span>':
        '<span class="badge text-bg-success">\n                                            <i class="fa fa-check"/> Hợp lệ\n                                        </span>',
    "Discrepancy %": "Chênh lệch %",
    "Max Discrepancy %": "Chênh lệch tối đa %",
    "Employee %": "Tỷ lệ nhân viên %",
    "Employer %": "Tỷ lệ người sử dụng lao động %",
    "Avg Increase %": "Mức tăng trung bình %",
    "Compa Ratio vs Increase %": "Tỷ lệ lương so với mức tăng %",
    "Configure rules like max increase %, budget caps, and compa-ratio bounds\n                to govern compensation recommendations.":
        "Cấu hình các quy tắc như mức tăng tối đa %, giới hạn ngân sách và giới hạn tỷ lệ lương\n                để kiểm soát đề xuất đãi ngộ.",
    "Range Penetration %": "Mức thâm nhập dải lương %",
    "Range Spread %": "Độ rộng dải lương %",
    "Shaded area = ±10% confidence band": "Vùng tô màu = khoảng tin cậy ±10%",
    "Coverage %": "Tỷ lệ bao phủ (%)",
    "Spread %": "Độ rộng %",
    "%s employee(s) at 90%% of the %s monthly ceiling":
        "%s nhân viên ở mức 90%% trần hàng tháng của %s",
    "Deviation %": "Độ lệch %",
    "Variance % by dept/title/designation": "Chênh lệch % theo phòng ban/chức danh/vị trí",
    "3.25% paid by company for ESI": "Công ty đóng 3,25% cho ESI",
    "12-13% paid by company for EPF (Employees Provident Fund)":
        "Công ty đóng 12–13% cho EPF (Quỹ Tiết kiệm Nhân viên)",
    "1.75% paid by company for SOCSO": "Công ty đóng 1,75% cho SOCSO",
    "Only activate if any single increase % exceeds this value.":
        "Chỉ kích hoạt nếu một mức tăng riêng lẻ vượt quá tỷ lệ phần trăm này.",
    "PayAI: net pay is up 3.1% vs May": "PayAI: lương thực nhận tăng 3,1% so với tháng 5",
    '<span>Singapore</span><i>·</i><span>Malaysia</span><i>·</i><span>Indonesia</span><i>·</i><span>India</span><i>·</i><span>Vietnam</span><i>·</i><span>Thailand</span><i>·</i><span>Cambodia</span><i>·</i>\n              <span>Singapore</span><i>·</i><span>Malaysia</span><i>·</i><span>Indonesia</span><i>·</i><span>India</span><i>·</i><span>Vietnam</span><i>·</i><span>Thailand</span><i>·</i><span>Cambodia</span><i>·</i>':
        '<span>Singapore</span><i>·</i><span>Malaysia</span><i>·</i><span>Indonesia</span><i>·</i><span>Ấn Độ</span><i>·</i><span>Việt Nam</span><i>·</i><span>Thái Lan</span><i>·</i><span>Campuchia</span><i>·</i>\n              <span>Singapore</span><i>·</i><span>Malaysia</span><i>·</i><span>Indonesia</span><i>·</i><span>Ấn Độ</span><i>·</i><span>Việt Nam</span><i>·</i><span>Thái Lan</span><i>·</i><span>Campuchia</span><i>·</i>',
}

# Source Atlas explains payroll provenance, so literal machine translations of
# words such as "lane", "run", "feed", and "scheme" are misleading.  Keep its
# core vocabulary explicit and consistent across the screen and its workbook.
CURATED_OVERRIDES.update({
    "Adds to net pay": "Cộng vào lương thực nhận",
    "Taken off net pay": "Khấu trừ khỏi lương thực nhận",
    "Net pay": "Lương thực nhận",
    "Employer cost": "Chi phí của người sử dụng lao động",
    "Both added and taken off": "Vừa cộng vừa khấu trừ",
    "Nothing to export.": "Không có dữ liệu để xuất.",
    "%(from)s–%(to)s of %(total)s employees": "Nhân viên %(from)s–%(to)s trên tổng số %(total)s",
    "%(from)s–%(to)s of %(total)s components": "Thành phần %(from)s–%(to)s trên tổng số %(total)s",
    "Source Atlas export": "Bản xuất Nguồn dữ liệu",
    "There is no '%s' source lane to download.": "Không có luồng nguồn '%s' để tải xuống.",
    "This pay run has no payslips yet, so there is nothing to export.":
        "Kỳ lương này chưa có phiếu lương nên không có dữ liệu để xuất.",
    "Only the first %(cap)s of %(total)s employees are included.":
        "Chỉ bao gồm %(cap)s nhân viên đầu tiên trong tổng số %(total)s.",
    "Only the first %(cap)s of %(total)s components are included.":
        "Chỉ bao gồm %(cap)s thành phần đầu tiên trong tổng số %(total)s.",
    "Nothing in this pay run came from %(lane)s, so there is nothing to export.":
        "Không có dữ liệu nào trong kỳ lương này đến từ %(lane)s nên không có dữ liệu để xuất.",
    "How to read this": "Hướng dẫn đọc",
    "Pay run": "Kỳ lương",
    "Source lane": "Luồng nguồn",
    "Prepared": "Ngày tạo",
    "What each employee's component was worth in this run.":
        "Giá trị từng thành phần lương của mỗi nhân viên trong kỳ lương này.",
    "The same grid, but each cell says where the value came from: the lane, the key it arrived on, and why that source won.":
        "Cùng một bảng dữ liệu, nhưng mỗi ô cho biết giá trị đến từ luồng nào, qua khóa nào và vì sao nguồn đó được ưu tiên.",
    "The %(type)s feed carries %(n)s keys; the first %(cap)s are exported.":
        "Nguồn cấp %(type)s có %(n)s khóa; %(cap)s khóa đầu tiên được xuất.",
    "External id": "ID bên ngoài",
    "Pulled": "Thời điểm lấy",
    "Workbook": "Sổ tính",
    "Feed · %s": "Nguồn cấp · %s",
    "Read off %(model)s · %(field)s for this employee.":
        "Đọc từ %(model)s · %(field)s của nhân viên này.",
    "The Source Atlas shows every employee's pay data for a whole run. It is open to payroll officers and above.":
        "Nguồn dữ liệu hiển thị dữ liệu lương của mọi nhân viên trong toàn bộ kỳ lương. Chỉ chuyên viên tiền lương và cấp cao hơn được truy cập.",
    "Not tracked": "Chưa theo dõi",
    "That pay run no longer exists.": "Kỳ lương đó không còn tồn tại.",
    "This pay run has no payslips yet, so there is nothing to trace. Run payroll for the period and the Atlas fills in.":
        "Kỳ lương này chưa có phiếu lương nên chưa có dữ liệu để truy vết. Hãy tính lương cho kỳ này để Nguồn dữ liệu được cập nhật.",
    "Some components have no pay role yet, so they are left out of the money totals. Classify the scheme to include them.":
        "Một số thành phần chưa được phân loại vai trò lương nên chưa được tính vào tổng tiền. Hãy phân loại cấu hình để đưa chúng vào.",
    "Computed before source tracking existed": "Được tính trước khi có tính năng theo dõi nguồn",
    "This payslip was computed before the system recorded where each value came from. Recomputing the run captures it.":
        "Phiếu lương này được tính trước khi hệ thống ghi nhận nguồn của từng giá trị. Hãy tính lại kỳ lương để ghi nhận nguồn.",
    "Nothing fed this": "Không có nguồn dữ liệu",
    "This scheme has no net pay component, so the chain cannot be followed to the end.":
        "Cấu hình này chưa có thành phần lương thực nhận nên không thể truy theo chuỗi đến cuối.",
    "This component does not reach net pay through any formula on this scheme — it is carried for information.":
        "Thành phần này không đi vào lương thực nhận qua bất kỳ công thức nào trong cấu hình; nó chỉ dùng để tham khảo.",
    "The chain is longer than %(n)s hops and has been cut short here.":
        "Chuỗi có hơn %(n)s bước nên được rút gọn tại đây.",
    "Worked out here": "Được tính tại đây",
    "This component has no source of its own — this scheme's formula produces it.":
        "Thành phần này không có nguồn riêng; công thức trong cấu hình tạo ra giá trị này.",
    "A fixed value on the scheme": "Giá trị cố định trong cấu hình",
    "Ungrouped": "Chưa phân nhóm",
    "Made of the other lanes' numbers — not summed here.":
        "Được tạo từ số liệu của các luồng khác; không cộng lại tại đây.",
    "Lanes": "Luồng nguồn",
    "This run could not be read": "Không thể đọc kỳ lương này",
    "This pay run has no payslips, so there are no numbers to trace. Run payroll for the period and every value's source appears here.":
        "Kỳ lương này chưa có phiếu lương nên chưa có số liệu để truy vết. Hãy tính lương cho kỳ này để xem nguồn của từng giá trị.",
    "Run payroll": "Tính lương",
    "Nothing in this run came this way.": "Không có dữ liệu nào trong kỳ lương đi qua luồng này.",
    "Carried into this run": "Được đưa vào kỳ lương này",
    "See the cells": "Xem các ô dữ liệu",
    "Codes with a source but no component": "Mã có nguồn nhưng không còn thành phần tương ứng",
    "Reading the run…": "Đang đọc kỳ lương…",
    "no source recorded": "chưa ghi nhận nguồn",
    "Following the chain…": "Đang truy theo chuỗi…",
    "why this one": "lý do chọn nguồn này",
    "pulled": "được lấy lúc",
    "the other source also sent": "nguồn khác cũng cung cấp",
    "Shaped by a transformation rule": "Được xử lý theo quy tắc chuyển đổi",
    "feeds into": "được đưa vào",
    "folded into a total": "được cộng vào tổng",
    "Coverage": "Mức độ bao phủ",
    "This month's pay data": "Dữ liệu lương tháng này",
    "reads": "sử dụng",
    "pay component": "thành phần lương",
    "from a spreadsheet. Load the file for this period.":
        "lấy từ bảng tính. Hãy tải tệp của kỳ này.",
    "spreadsheet component": "thành phần bảng tính",
    "are fed by this file (": "được cấp dữ liệu từ tệp này (",
    "read).": "được đọc).",
    "This month's spreadsheet": "Bảng tính lương tháng này",
    "Add pay data": "Thêm dữ liệu lương",
    "fed": "đã cấp dữ liệu cho",
    "component(s) across": "thành phần trên",
    "row(s) and produced": "dòng và tạo ra",
    "payslip(s) in this run.": "phiếu lương trong kỳ lương này.",
    "component(s) used fallback values — no spreadsheet was loaded:":
        "thành phần đã dùng giá trị dự phòng vì chưa tải bảng tính:",
    "Reading the scheme's formulas…": "Đang đọc công thức của cấu hình…",
    "This scheme could not be read.": "Không thể đọc cấu hình này.",
    "Read the scheme again": "Đọc lại cấu hình",
    "Everything already matches the formula.": "Mọi thành phần đã khớp với công thức.",
    "are filed the way this scheme's own arithmetic reads them.":
        "đã được phân loại theo phép tính của chính cấu hình này.",
    "to settle": "cần xử lý",
    "Tick all": "Chọn tất cả",
    "Tick": "Chọn",
    "counted inside a total": "được tính trong một thành phần tổng",
    "Name the net-pay component and this scheme can be read; skip and nothing changes.":
        "Chọn thành phần lương thực nhận để hệ thống đọc cấu hình; nếu bỏ qua, sẽ không có gì thay đổi.",
    "Only ticked rows are written. Everything else keeps the category it has now.":
        "Chỉ các dòng được chọn mới được cập nhật. Các dòng còn lại giữ nguyên danh mục hiện tại.",
    "would be refiled. Untick anything you disagree with — only ticked rows are written, and the rest keep the role they have now.":
        "sẽ được phân loại lại. Bỏ chọn các dòng bạn không đồng ý; chỉ dòng được chọn mới được cập nhật, các dòng còn lại giữ nguyên vai trò hiện tại.",
    'Nobody matched. Names are matched exactly, accents included —               try "Bùi Anh" rather than "Bui Anh".':
        'Không tìm thấy ai phù hợp. Tên phải khớp chính xác, kể cả dấu; hãy thử "Bùi Anh" thay vì "Bui Anh".',
})

# Google is generally strong on Vietnamese prose but these product terms must
# remain consistent with the application's reviewed payroll vocabulary.
POST_REPLACEMENTS = (
    ("phiếu trả lương", "phiếu lương"),
    ("phiếu thanh toán", "phiếu lương"),
    ("chạy bảng lương", "kỳ lương"),
    ("lần chạy bảng lương", "kỳ lương"),
    ("lần tính lương", "kỳ lương"),
    ("biên chế", "nhân sự"),
    ("bảng thời gian", "bảng công"),
    ("đăng ký đóng góp", "sổ đóng góp"),
)


def module_dirs(repo: Path) -> list[Path]:
    return sorted(
        path.parent
        for path in repo.glob("pb_*/__manifest__.py")
        if path.parent.is_dir()
    )


def load_po(path: Path | None) -> polib.POFile | None:
    if not path or not path.is_file():
        return None
    try:
        return polib.pofile(str(path))
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError(f"Cannot parse {path}: {exc}") from exc


def usable_translation(entry: polib.POEntry) -> bool:
    if not entry.msgid or not entry.msgstr or "fuzzy" in entry.flags:
        return False
    # A legacy catalog often copied English into msgstr merely to make the file
    # complete.  Treat that as untranslated unless it is code, a product name,
    # or text that is already Vietnamese.
    if entry.msgid == entry.msgstr and not is_intentionally_untranslated(entry.msgid):
        return False
    return True


def add_memory(memory: dict[str, str], path: Path | None) -> None:
    po = load_po(path)
    if not po:
        return
    for entry in po:
        if usable_translation(entry):
            memory.setdefault(entry.msgid, entry.msgstr)


def build_shared_memory(repo: Path, db_export_root: Path | None) -> dict[str, str]:
    """Build priority-ordered translation memory from reviewed catalogs."""
    memory: dict[str, str] = {}
    # Custom application translations are the preferred vocabulary.
    for pattern in ("pb_*/i18n/vi_VN.po", "pb_*/i18n/vi.po"):
        for path in sorted(repo.glob(pattern)):
            add_memory(memory, path)
    if db_export_root:
        for path in sorted(db_export_root.glob("pb_*/i18n/vi_VN.po")):
            add_memory(memory, path)
    # Upstream/OCA Vietnamese catalogs provide high-quality common UI terms.
    for pattern in ("*/i18n/vi_VN.po", "*/i18n/vi.po"):
        for path in sorted(repo.glob(pattern)):
            add_memory(memory, path)
    return memory


def module_memory(repo: Path, module: str, db_export_root: Path | None) -> dict[str, str]:
    """Return exact module translations, ordered ahead of shared memory."""
    memory: dict[str, str] = {}
    paths = [
        repo / module / "i18n" / "vi_VN.po",
        repo / module / "i18n" / "vi.po",
    ]
    if db_export_root:
        paths.insert(0, db_export_root / module / "i18n" / "vi_VN.po")
    for path in paths:
        add_memory(memory, path)
    return memory


def template_path(repo: Path, pot_root: Path, module: str) -> Path | None:
    exported = pot_root / module / "i18n" / f"{module}.pot"
    if exported.is_file():
        return exported
    legacy = repo / "_translation_backups" / module / f"{module}.pot"
    if module in LEGACY_MODULES and legacy.is_file():
        return legacy
    return None


def _add_source_entry(
    catalog: polib.POFile,
    seen: set[str],
    source: str,
    relative_path: str,
    line: int,
) -> None:
    source = source.strip()
    if not source or source in seen:
        return
    seen.add(source)
    catalog.append(
        polib.POEntry(msgid=source, occurrences=[(relative_path, str(line))])
    )


def extract_javascript_terms(module_dir: Path, catalog: polib.POFile) -> None:
    """Merge literal ``_t()`` calls added since the last native Odoo export."""
    seen = {entry.msgid for entry in catalog if entry.msgid}
    for path in sorted((module_dir / "static").rglob("*.js")) if (module_dir / "static").is_dir() else []:
        text = path.read_text(encoding="utf-8")
        relative = str(path.relative_to(module_dir.parent))
        for match in JS_T_RE.finditer(text):
            value = match.group("value")
            if match.group("quote") == "`" and "${" in value:
                continue
            try:
                value = bytes(value, "utf-8").decode("unicode_escape") if "\\" in value else value
            except UnicodeDecodeError:
                pass
            _add_source_entry(catalog, seen, value, relative, text.count("\n", 0, match.start()) + 1)


def extract_python_terms(
    module_dir: Path,
    catalog: polib.POFile,
    paths: Iterable[Path] | None = None,
) -> None:
    """Extract literal Odoo ``_()`` calls for modules absent from the database."""
    seen = {entry.msgid for entry in catalog if entry.msgid}
    candidates = paths if paths is not None else module_dir.rglob("*.py")
    for path in sorted(path for path in candidates if path.suffix == ".py" and path.is_file()):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeError):
            continue
        relative = str(path.relative_to(module_dir.parent))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in {"_", "_lt"} or not node.args:
                continue
            value = node.args[0]
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                _add_source_entry(catalog, seen, value.value, relative, node.lineno)


def extract_xml_terms(
    module_dir: Path,
    catalog: polib.POFile,
    paths: Iterable[Path] | None = None,
) -> None:
    """Extract visible XML/QWeb text when native export is not yet possible."""
    from xml.etree import ElementTree as etree

    seen = {entry.msgid for entry in catalog if entry.msgid}
    candidates = paths if paths is not None else module_dir.rglob("*.xml")
    for path in sorted(path for path in candidates if path.suffix == ".xml" and path.is_file()):
        try:
            root = etree.parse(path).getroot()
        except (OSError, etree.ParseError):
            continue
        relative = str(path.relative_to(module_dir.parent))
        for node in root.iter():
            if node.get("t-translation") == "off":
                continue
            for attribute in XML_TRANSLATABLE_ATTRIBUTES:
                value = node.get(attribute)
                if value:
                    _add_source_entry(catalog, seen, value, relative, 1)
            for value in (node.text, node.tail):
                if value and value.strip():
                    normalized = " ".join(value.split())
                    if node.tag == "field" and node.get("name") in XML_TECHNICAL_FIELD_NAMES:
                        continue
                    if not re.search(r"[A-Za-z]", normalized):
                        continue
                    if (
                        node.tag == "field"
                        and (
                            re.fullmatch(r"\d+", normalized)
                            or re.fullmatch(r"[a-z0-9_.-]+", normalized)
                        )
                    ):
                        continue
                    _add_source_entry(catalog, seen, normalized, relative, 1)


def source_augmented_template(
    repo: Path,
    module: str,
    native_template: polib.POFile | None,
) -> polib.POFile:
    """Return native terms plus recent JS, or a full fallback for a new module."""
    template = native_template or polib.POFile()
    module_dir = repo / module
    extract_javascript_terms(module_dir, template)
    if native_template is None:
        extract_python_terms(module_dir, template)
        extract_xml_terms(module_dir, template)
    return template


def changed_source_paths(repo: Path, module: str, since: str) -> list[Path]:
    """Return module Python/XML files changed after a known POT source revision."""
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{since}..HEAD", "--", module],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return [repo / line for line in result.stdout.splitlines() if line.endswith((".py", ".xml"))]


def is_intentionally_untranslated(text: str) -> bool:
    value = text.strip()
    if not value:
        return True
    if value in SKIP_TERMS:
        return True
    if is_vietnamese_text(value):
        return True
    if not re.search(r"[A-Za-z]", value):
        return True
    if re.fullmatch(r"[A-Z0-9_.+/#:@-]{1,24}", value):
        return True
    if re.fullmatch(r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+", value):
        return True
    return False


def protect(text: str) -> tuple[str, list[str]]:
    tokens: list[str] = []

    def replace(match: re.Match[str]) -> str:
        index = len(tokens)
        tokens.append(match.group(0))
        return f"ZXQPH{index:04d}QXZ"

    return PROTECTED_RE.sub(replace, text), tokens


def restore(text: str, tokens: list[str]) -> str | None:
    restored = html.unescape(text)
    for index, original in enumerate(tokens):
        token = f"ZXQPH{index:04d}QXZ"
        # Google occasionally inserts spaces inside artificial tokens.
        loose = re.compile(rf"Z\s*X\s*Q\s*P\s*H\s*{index:04d}\s*Q\s*X\s*Z", re.I)
        matches = loose.findall(restored)
        if len(matches) != 1:
            return None
        restored = loose.sub(lambda _match, value=original: value, restored, count=1)
    if re.search(r"ZXQPH\d+QXZ", restored, re.I):
        return None
    return restored


def same_structure(source: str, target: str) -> bool:
    def tag_shapes(value: str) -> Counter[tuple[str, str, str]]:
        return Counter(
            (match.group(1), match.group(2).lower(), match.group(3))
            for match in TAG_RE.finditer(value)
        )

    return (
        Counter(PLACEHOLDER_RE.findall(source)) == Counter(PLACEHOLDER_RE.findall(target))
        and tag_shapes(source) == tag_shapes(target)
    )


def polish_translation(text: str) -> str:
    result = text.strip()
    for wrong, preferred in POST_REPLACEMENTS:
        result = re.sub(re.escape(wrong), preferred, result, flags=re.I)
    return result


def preserve_boundary_whitespace(source: str, target: str) -> str:
    """Match Odoo's significant leading/trailing whitespace in multiline terms."""
    leading = re.match(r"^\s*", source).group(0)
    trailing = re.search(r"\s*$", source).group(0)
    core = target.strip()
    return f"{leading}{core}{trailing}"


class GoogleMobileTranslator:
    def __init__(self, delay: float = 0.35, retries: int = 5):
        import requests

        self.requests = requests
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        self.delay = delay
        self.retries = retries

    def _request(self, text: str) -> str:
        from bs4 import BeautifulSoup

        for attempt in range(self.retries):
            response = self.session.get(
                GOOGLE_MOBILE_URL,
                params={"sl": "en", "tl": "vi", "q": text},
                timeout=30,
            )
            if response.status_code == 200:
                element = BeautifulSoup(response.text, "html.parser").find(
                    "div", class_="result-container"
                )
                if element:
                    return element.get_text()
            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()
            time.sleep(min(30, 2 ** attempt))
        raise RuntimeError(f"Google translation failed with HTTP {response.status_code}")

    def translate_many(self, sources: list[str]) -> dict[str, str]:
        results: dict[str, str] = {}
        batch: list[tuple[str, str, list[str]]] = []
        batch_chars = 0

        def flush() -> None:
            nonlocal batch, batch_chars
            if not batch:
                return
            payload = f"\n{SEPARATOR}\n".join(item[1] for item in batch)
            translated = self._request(payload)
            parts = re.split(rf"\s*{re.escape(SEPARATOR)}\s*", translated)
            if len(parts) != len(batch):
                raise RuntimeError(
                    f"Translation batch delimiter mismatch: {len(batch)} inputs, "
                    f"{len(parts)} outputs"
                )
            for (source, _protected, tokens), part in zip(batch, parts):
                restored = restore(part, tokens)
                if restored and same_structure(source, restored):
                    results[source] = polish_translation(restored)
            batch = []
            batch_chars = 0
            time.sleep(self.delay)

        for source in sources:
            protected, tokens = protect(source)
            extra = len(protected) + len(SEPARATOR) + 2
            if len(protected) > MAX_REQUEST_CHARS:
                flush()
                # Oversized HTML/template entries are unsafe to split.  They
                # remain visible in the final validation report for review.
                continue
            if batch and (batch_chars + extra > MAX_REQUEST_CHARS or len(batch) >= MAX_BATCH_ITEMS):
                flush()
            batch.append((source, protected, tokens))
            batch_chars += extra
        flush()
        return results


def read_cache(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"Translation cache must be a JSON object: {path}")
    return {str(key): str(value) for key, value in data.items() if value}


def write_cache(path: Path, cache: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def make_catalog(template: polib.POFile, translations: dict[str, str]) -> polib.POFile:
    catalog = polib.POFile(wrapwidth=88)
    catalog.metadata = {
        "Project-Id-Version": "Odoo Server 19.0",
        "Report-Msgid-Bugs-To": "",
        "POT-Creation-Date": template.metadata.get("POT-Creation-Date", ""),
        "PO-Revision-Date": time.strftime("%Y-%m-%d %H:%M%z"),
        "Last-Translator": "Payobook Translation Automation",
        "Language-Team": "Vietnamese",
        "Language": LANGUAGE,
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
        "Plural-Forms": "nplurals=1; plural=0;",
    }
    for source_entry in template:
        entry = polib.POEntry(
            msgid=source_entry.msgid,
            msgid_plural=source_entry.msgid_plural,
            msgctxt=source_entry.msgctxt,
            occurrences=list(source_entry.occurrences),
            comment=source_entry.comment,
            tcomment=source_entry.tcomment,
            flags=list(source_entry.flags),
        )
        entry.flags = [flag for flag in entry.flags if flag != "fuzzy"]
        entry.msgstr = translations.get(entry.msgid, "")
        if entry.msgid_plural:
            plural = translations.get(entry.msgid_plural, entry.msgstr)
            entry.msgstr_plural = {0: plural}
        existing = catalog.find(entry.msgid, msgctxt=entry.msgctxt)
        if existing and existing.msgid_plural == entry.msgid_plural:
            existing.occurrences = list(dict.fromkeys(existing.occurrences + entry.occurrences))
            existing.flags = list(dict.fromkeys(existing.flags + entry.flags))
            if entry.comment and entry.comment not in existing.comment:
                existing.comment = "\n".join(filter(None, [existing.comment, entry.comment]))
            if entry.tcomment and entry.tcomment not in existing.tcomment:
                existing.tcomment = "\n".join(filter(None, [existing.tcomment, entry.tcomment]))
            continue
        catalog.append(entry)
    return catalog


def chunks(values: Iterable[str]) -> list[str]:
    return sorted(set(values), key=lambda item: (len(item), item))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--pot-root", type=Path, required=True)
    parser.add_argument("--db-export-root", type=Path)
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path(__file__).with_name("vi_translation_cache.json"),
    )
    parser.add_argument("--translate-missing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--module", action="append", dest="modules")
    parser.add_argument(
        "--source-augment",
        action="append",
        default=[],
        metavar="MODULE",
        help="also merge Python/XML source terms for a module changed after POT export",
    )
    parser.add_argument(
        "--source-since",
        metavar="GIT_REVISION",
        help="merge Python/XML files changed after the revision used for POT export",
    )
    args = parser.parse_args()

    repo = args.repo.resolve()
    modules = [path.name for path in module_dirs(repo)]
    if args.modules:
        requested = set(args.modules)
        unknown = requested.difference(modules)
        if unknown:
            parser.error(f"Unknown pb_* modules: {', '.join(sorted(unknown))}")
        modules = [module for module in modules if module in requested]
    unknown_augment = set(args.source_augment).difference(modules)
    if unknown_augment:
        parser.error(f"Unknown source augmentation modules: {', '.join(sorted(unknown_augment))}")

    shared = build_shared_memory(repo, args.db_export_root)
    cache = read_cache(args.cache)
    templates: dict[str, polib.POFile] = {}
    missing_sources: set[str] = set()

    for module in modules:
        path = template_path(repo, args.pot_root, module)
        if not path:
            # New modules may not be installed in the reference database yet;
            # extract their source without mutating that database.  Truly empty
            # asset/pack modules still produce an empty catalog.
            template = source_augmented_template(repo, module, None)
        else:
            template = load_po(path)
            assert template is not None
            template = source_augmented_template(repo, module, template)
            if module in args.source_augment:
                extract_python_terms(repo / module, template)
                extract_xml_terms(repo / module, template)
            elif args.source_since:
                changed = changed_source_paths(repo, module, args.source_since)
                extract_python_terms(repo / module, template, changed)
                extract_xml_terms(repo / module, template, changed)
        templates[module] = template
        local = module_memory(repo, module, args.db_export_root)
        for entry in template:
            source = entry.msgid
            if not source:
                continue
            if (
                source in local
                or source in shared
                or source in CURATED_OVERRIDES
                or source in cache
                or source in DICT_PAYROLL_CORE
            ):
                continue
            if is_intentionally_untranslated(source):
                continue
            missing_sources.add(source)

    if args.translate_missing and missing_sources:
        translator = GoogleMobileTranslator()
        translated = translator.translate_many(chunks(missing_sources))
        cache.update(translated)
        if not args.dry_run:
            write_cache(args.cache, cache)
        print(f"Machine translated {len(translated)} of {len(missing_sources)} missing strings")

    totals = Counter()
    unresolved: list[tuple[str, str]] = []
    for module in modules:
        template = templates[module]
        local = module_memory(repo, module, args.db_export_root)
        translations: dict[str, str] = {}
        for entry in template:
            source = entry.msgid
            if not source:
                continue
            target = (
                CURATED_OVERRIDES.get(source)
                or local.get(source)
                or shared.get(source)
                or DICT_PAYROLL_CORE.get(source)
                or cache.get(source)
            )
            if target:
                target = preserve_boundary_whitespace(source, target)
            if not target and is_intentionally_untranslated(source):
                target = source
                totals["technical"] += 1
            if target and same_structure(source, target):
                translations[source] = target
                totals["translated"] += 1
            else:
                unresolved.append((module, source))
                totals["unresolved"] += 1

        catalog = make_catalog(template, translations)
        if not args.dry_run:
            destination = repo / module / "i18n" / "vi_VN.po"
            destination.parent.mkdir(parents=True, exist_ok=True)
            catalog.save(str(destination))

    print(
        f"Modules: {len(modules)}; entries translated: {totals['translated']}; "
        f"technical literals retained: {totals['technical']}; unresolved: {totals['unresolved']}"
    )
    if unresolved:
        report = repo / "tools" / "vi_translation_unresolved.txt"
        body = "\n".join(f"{module}\t{source.replace(chr(10), r'\n')}" for module, source in unresolved)
        if not args.dry_run:
            report.write_text(body + "\n", encoding="utf-8")
        print(f"Unresolved report: {report}")
        return 2
    report = repo / "tools" / "vi_translation_unresolved.txt"
    if report.exists() and not args.dry_run:
        report.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
