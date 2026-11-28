#!/usr/bin/env python3
"""VIFIX P1 scope D: build docs/handovers/vifix/VIFIX_GLOSSARY.md (offline, deterministic).

The CHOICES below are authored (English, the ONE Vietnamese to use, why, review flag). The
tool fills in the evidence: every current Vietnamese variant of that English across our
modules' effective vi_VN.po entries (vifix_po_scan.effective_entries, so the .pot merge
applies), with counts, and the term the Learn glossary uses (docs/tutorial_poc/author/data.js
GLOSSARY), so a reviewer sees what each choice replaces.

Run:  python3 docs/handovers/vifix/tools/vifix_glossary_build.py [--out path]
"""
import argparse
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vifix_common as C  # noqa: E402
import vifix_po_scan as PS  # noqa: E402

R = "REVIEW"  # the owner should confirm this choice
S = ""        # settled: screen term, Learn term and payroll usage agree

# (area, English, Vietnamese to use, why, flag[, extra English spellings to search])
CHOICES = [
    # --- pay and payslip ------------------------------------------------------------
    ("Pay", "Payslip", "Phiếu lương", "Screen, Learn and payroll usage agree.", S),
    ("Pay", "Payroll", "Lương", "The menu page is 'Lương'; use 'bảng lương' only for the computed sheet of a month.", R),
    ("Pay", "Payroll sheet", "Bảng lương", "The month's computed table, as accountants say it.", S, ["Payroll Sheet"]),
    ("Pay", "Pay run", "Đợt lương", "Screen says 'đợt lương' ('Mở các đợt lương'); Learn's card says 'Đợt tính lương'; never 'Kỳ lương' (that is the period).", R, ["Pay Run", "Payslip Batch", "Batch Payslips"]),
    ("Pay", "Pay period", "Kỳ lương", "The month a run settles; not 'Giai đoạn' (a phase).", S, ["Period"]),
    ("Pay", "Gross", "Tổng thu nhập", "Chart tab and Learn; 'lương gross' only in speech.", S, ["Gross pay", "Gross Pay"]),
    ("Pay", "Net pay", "Lương thực nhận", "Screen and Learn; replaces 'Thực lãnh', 'Thực lĩnh', 'Lương ròng', and the wrong 'mạng lưới'.", S, ["Net", "Net Pay"]),
    ("Pay", "Earning", "Khoản thu nhập", "A payslip line that adds money; never 'kiếm tiền'.", S, ["Earnings"]),
    ("Pay", "Allowance", "Phụ cấp", "Standard payroll term.", S, ["Allowances"]),
    ("Pay", "Deduction", "Khấu trừ", "'Giảm trừ' is kept for the family deduction only.", S, ["Deductions"]),
    ("Pay", "Basic salary", "Lương cơ bản", "Standard; replaces 'Basic Lương'.", S, ["Basic Salary", "Basic wage", "Basic Wage"]),
    ("Pay", "Salary", "Lương", "Short form on screens; 'tiền lương' in legal text.", S, ["Wage"]),
    ("Pay", "Bonus", "Thưởng", "Standard.", S),
    ("Pay", "Award", "Khoản thưởng", "A one-off award; Learn agrees.", S),
    ("Pay", "Pay advance", "Tạm ứng lương", "Never 'tiến lên' / 'Nâng cao' (move forward / advanced).", S, ["Advance", "Salary advance", "Salary Advance"]),
    ("Pay", "Loan", "Khoản vay", "A loan to an employee repaid from pay.", S),
    ("Pay", "Retro adjustment", "Điều chỉnh hồi tố", "Generic; say 'truy lĩnh' when the employee gets money back and 'truy thu' when it is taken back.", S, ["Retro", "Retro pay"]),
    ("Pay", "Proration", "Tính theo ngày công", "Plain payroll wording (Learn); replaces 'Phân bổ theo tỷ lệ'.", S, ["Prorated", "Pro-rata"]),
    ("Pay", "Working days", "Ngày công", "Vietnamese payroll counts 'ngày công'; standard days = 'ngày công chuẩn'.", S, ["Working Days", "Worked days"]),
    ("Pay", "Standard working days", "Ngày công chuẩn", "The divisor of a monthly salary.", S),
    ("Pay", "Component", "Thành phần lương", "Learn says 'Thành phần'; add 'lương' where the line stands alone.", S, ["Pay component", "Pay components"]),
    ("Pay", "Salary structure", "Cấu trúc lương", "Standard; replaces 'Cơ cấu tiền lương'.", S, ["Salary Structure", "Structure"]),
    ("Pay", "Salary rule", "Quy tắc lương", "Replaces the word-for-word 'Lương Quy tắc'.", S, ["Salary Rule", "Salary Rules"]),
    ("Pay", "Rule", "Quy tắc", "'Quy định' is a legal regulation; never 'cai trị'.", S, ["Rules"]),
    ("Pay", "Formula", "Công thức", "Standard.", S),
    ("Pay", "Formula configuration", "Cấu hình công thức", "Learn agrees.", S),
    ("Pay", "Formula Engine", "Công cụ công thức", "The menu says 'Bộ máy công thức' (machinery); 'công cụ' reads as a tool.", R, ["Formula engine"]),
    ("Pay", "Pay scheme", "Chương trình lương", "Learn's term; alternatives seen: 'Phương án lương', 'Bảng lương'. Payroll staff may prefer 'chính sách lương'.", R, ["Pay Scheme", "Scheme"]),
    ("Pay", "Pay data", "Dữ liệu lương", "Learn agrees; replaces 'Trả dữ liệu'.", S),
    ("Pay", "Pay band", "Khoảng lương", "Learn; 'dải lương' is accepted in speech.", S, ["Pay Band", "Pay bands"]),
    ("Pay", "Pay scale", "Thang lương", "The legal 'thang lương, bảng lương' pair.", S, ["Pay Scale", "Salary scale"]),
    ("Pay", "Pay grade", "Bậc lương", "The legal step of a pay scale.", S, ["Grade", "Step"]),
    ("Pay", "Salary coefficient", "Hệ số lương", "Public-sector style pay; keep 'hệ số' for this only.", S, ["Coefficient"]),
    ("Pay", "Pay review", "Xét lương", "Learn: 'Đợt xét lương' for the event.", S, ["Pay Review"]),
    ("Pay", "Wage bill", "Quỹ lương", "Standard finance wording.", S, ["Payroll cost", "Payroll Cost"]),
    ("Pay", "Cost per head", "Chi phí bình quân đầu người", "Learn agrees.", S),
    ("Pay", "Pay day", "Ngày trả lương", "Screen: 'ngày trả lương'.", S, ["Payday", "Pay date"]),
    ("Pay", "Cut-off", "Ngày chốt lương", "The last day changes count for the month.", S, ["Cutoff", "Cut-off date"]),
    ("Pay", "Pay calendar", "Lịch lương", "Learn agrees.", S),
    ("Pay", "Pay out", "Chi trả", "The Payroll tab; Learn agrees.", S, ["Payout", "Deliver"]),
    ("Pay", "Payment", "Thanh toán", "Generic payment; a salary transfer is 'chi lương'.", S),
    ("Pay", "Bank file", "Tệp chi lương", "Learn's term; two other names are on screens today ('Tệp ngân hàng', 'Hồ sơ ngân hàng').", R, ["Bank File", "Bank export"]),
    ("Pay", "Bank account", "Tài khoản ngân hàng", "Standard.", S, ["Bank Account"]),
    ("Pay", "Payment release", "Lệnh chuyển tiền", "Learn agrees.", S),
    ("Pay", "Money in", "Tiền vào", "Plain; replaces the garbled 'Tiền tính bằng'. Check each screen: on a ledger 'Thu' may read better.", R),
    ("Pay", "Money out", "Tiền ra", "Plain; replaces 'Hết tiền' ('out of money'). On a ledger 'Chi' may read better.", R),
    ("Pay", "Journal entry", "Bút toán", "Accounting term.", S, ["Journal Entry"]),
    ("Pay", "Shadow run", "Chạy thử song song", "Replaces the word-for-word 'Chạy song song bóng'.", S, ["Shadow Run"]),
    ("Pay", "Recompute", "Tính lại", "Learn agrees.", S, ["Recalculate", "Compute"]),
    ("Pay", "Payroll-ready", "Sẵn sàng tính lương", "Learn agrees.", S),
    ("Pay", "Eligible", "Đủ điều kiện", "Learn agrees.", S),
    ("Pay", "Variance", "Chênh lệch", "Never 'Phương sai' (statistical variance).", S),
    ("Pay", "Reconcile", "Đối chiếu", "Accounting usage.", S, ["Reconciliation"]),
    ("Pay", "Total", "Tổng cộng", "Table totals; 'Tổng' inside a phrase.", S),
    ("Pay", "Amount", "Số tiền", "Standard.", S),
    ("Pay", "Rate", "Tỷ lệ", "A percentage; an hourly rate is 'đơn giá', a currency rate 'tỷ giá'.", R),
    ("Pay", "Currency", "Tiền tệ", "Field label; 'loại tiền' inside a sentence.", S),
    ("Pay", "Exchange rate", "Tỷ giá", "Standard.", S, ["Exchange Rate"]),
    ("Pay", "Group currency", "Đồng tiền tập đoàn", "Learn agrees.", S),
    # --- statutory ---------------------------------------------------------------------
    ("Statutory", "Social insurance", "Bảo hiểm xã hội (BHXH)", "Legal name; BHXH on tight labels.", S, ["Social Insurance"]),
    ("Statutory", "Health insurance", "Bảo hiểm y tế (BHYT)", "Legal name; never 'bảo hiểm sức khỏe'.", S, ["Health Insurance"]),
    ("Statutory", "Unemployment insurance", "Bảo hiểm thất nghiệp (BHTN)", "Legal name.", S, ["Unemployment Insurance"]),
    ("Statutory", "Trade union fee", "Kinh phí công đoàn (KPCĐ)", "Legal name.", S, ["Union fee", "Trade Union Fee"]),
    ("Statutory", "Insurance base", "Mức lương đóng bảo hiểm", "Learn agrees.", S, ["Insurance salary", "Insurable salary"]),
    ("Statutory", "Contribution ceiling", "Mức trần đóng bảo hiểm", "Never 'Trần nhà' (a room's ceiling).", S, ["Ceiling", "Cap"]),
    ("Statutory", "Contribution", "Khoản đóng", "Learn; 'mức đóng' for the rate.", S, ["Contributions"]),
    ("Statutory", "Employee share", "Phần người lao động", "Fixed in LEARNREV; never 'Chân nhân viên'.", S, ["Employee part", "Employee contribution"]),
    ("Statutory", "Employer share", "Phần doanh nghiệp", "Fixed in LEARNREV; never 'Chân chủ' or 'Nhà tuyển dụng'.", S, ["Employer part", "Employer contribution"]),
    ("Statutory", "Employer", "Doanh nghiệp", "UI word; 'người sử dụng lao động' in legal text; never 'Nhà tuyển dụng' (recruiter).", S),
    ("Statutory", "Personal income tax", "Thuế thu nhập cá nhân (thuế TNCN)", "Legal name; replaces 'Cá nhân Thu nhập Thuế'.", S, ["PIT", "Personal Income Tax"]),
    ("Statutory", "Taxable income", "Thu nhập chịu thuế", "Legal term (before deductions).", S, ["Taxable Income"]),
    ("Statutory", "Assessable income", "Thu nhập tính thuế", "Legal term (after family deductions).", S, ["Assessable Income"]),
    ("Statutory", "Family deduction", "Giảm trừ gia cảnh", "Legal term.", S, ["Family Deduction", "Personal deduction"]),
    ("Statutory", "Dependant", "Người phụ thuộc", "Legal term.", S, ["Dependent", "Dependents", "Dependants"]),
    ("Statutory", "Tax table", "Biểu thuế", "'Biểu thuế lũy tiến từng phần' in full.", S, ["Tax Table", "Tax tables", "Tax Tables"]),
    ("Statutory", "Tax code", "Mã số thuế", "MST on tight labels.", S, ["Tax ID", "Tax number"]),
    ("Statutory", "Tax finalisation", "Quyết toán thuế", "The yearly settlement.", S, ["Tax settlement", "Tax finalization"]),
    ("Statutory", "Resident", "Cá nhân cư trú", "Legal term; 'không cư trú' for non-resident.", S, ["Tax resident"]),
    ("Statutory", "Statutory", "Theo luật định", "Learn says 'Luật định'; as an adjective 'theo luật định' reads naturally.", S),
    ("Statutory", "Filing", "Tờ khai", "What is filed is a 'tờ khai'; the act is 'nộp tờ khai'. Learn says 'Báo cáo bắt buộc'.", R, ["Filings", "Statutory filing", "Return"]),
    ("Statutory", "Decree", "Nghị định", "Legal term.", S),
    ("Statutory", "Circular", "Thông tư", "Legal term.", S),
    ("Statutory", "Effective date", "Ngày hiệu lực", "Replaces 'Hiệu lực Ngày'.", S, ["Effective Date", "Effective from"]),
    ("Statutory", "Labour Code", "Bộ luật Lao động", "Proper name, capitalised so.", S, ["Labor Code"]),
    # --- people and lifecycle ------------------------------------------------------------
    ("People", "Employee", "Nhân viên", "UI word; 'người lao động' in legal and insurance text.", S, ["Employees"]),
    ("People", "People", "Nhân sự", "The menu says 'Con người' (human beings, philosophical); HR software in Vietnam says 'Nhân sự'.", R),
    ("People", "Department", "Phòng ban", "Standard; never 'Phòng cấm' (a forbidden room).", S, ["Departments"]),
    ("People", "Division", "Khối", "Most of our files say 'Khối' (Khối văn phòng, Khối sản xuất); Learn says 'Bộ phận', which also means a department.", R, ["Divisions"]),
    ("People", "Team", "Nhóm", "Standard.", S),
    ("People", "Company", "Công ty", "Standard.", S),
    ("People", "Manager", "Quản lý", "'Quản lý trực tiếp' for a line manager.", S, ["Line manager"]),
    ("People", "Job position", "Vị trí công việc", "Standard.", S, ["Job Position", "Position"]),
    ("People", "Job title", "Chức danh", "Replaces 'Chức danh Tiêu đề'.", S, ["Job Title"]),
    ("People", "Contract", "Hợp đồng lao động", "'Hợp đồng' on tight labels.", S, ["Contracts", "Employment contract"]),
    ("People", "Probation", "Thử việc", "Legal and screen term.", S),
    ("People", "Joiner", "Người mới vào", "Learn; the People tab is 'Người mới'; never 'thợ mộc' (carpenter).", S, ["Joiners", "New joiner", "New joiners"]),
    ("People", "Onboarding", "Tiếp nhận nhân viên mới", "Plain; 'hội nhập' is also used. Nothing in our files today.", R),
    ("People", "Buddy", "Người đồng hành", "Learn agrees.", S),
    ("People", "Leaver", "Người nghỉ việc", "Matches the Exits tab 'Nghỉ việc'; Learn's card says 'Người thôi việc'.", R, ["Leavers"]),
    ("People", "Exit", "Nghỉ việc", "The People tab.", S, ["Exits", "Offboarding"]),
    ("People", "Resignation", "Đơn xin nghỉ việc", "The letter; 'tự nghỉ việc' for the reason.", S),
    ("People", "Termination", "Chấm dứt hợp đồng", "Legal wording.", S),
    ("People", "Severance", "Trợ cấp thôi việc", "Legal term.", S, ["Severance pay"]),
    ("People", "Notice period", "Thời hạn báo trước", "Legal term.", S, ["Notice Period"]),
    ("People", "Full and final", "Quyết toán thôi việc", "Learn agrees.", S, ["Full & final", "Final settlement"]),
    ("People", "Clearance", "Xác nhận bàn giao", "Learn agrees.", S),
    ("People", "Hand-over", "Bàn giao", "Standard.", S, ["Handover"]),
    ("People", "Date of birth", "Ngày sinh", "Standard.", S, ["Birthday"]),
    ("People", "ID number", "Số CCCD", "The citizen ID; 'số giấy tờ tùy thân' when any ID.", S, ["Citizen ID", "National ID"]),
    ("People", "Nationality", "Quốc tịch", "Standard.", S),
    ("People", "Gender", "Giới tính", "Standard.", S),
    ("People", "Headcount", "Số nhân sự", "Plain; Learn says 'Sĩ số' (a class or army roll).", R),
    ("People", "Records", "Hồ sơ", "People records; 'bản ghi' only in technical text.", S),
    ("People", "Document", "Giấy tờ", "An employee's papers; 'tài liệu' for help documents.", R, ["Documents"]),
    # --- time --------------------------------------------------------------------------
    ("Time", "Attendance", "Chấm công", "Standard.", S),
    ("Time", "Check in", "Giờ vào", "A field; the action is 'Chấm công vào'.", R, ["Check-in", "Check In"]),
    ("Time", "Check out", "Giờ ra", "A field; the action is 'Chấm công ra'.", R, ["Check-out", "Check Out"]),
    ("Time", "Punch", "Lượt chấm công", "Never 'cú đấm' (a blow); 'Missing punch-out' = 'Thiếu giờ ra'.", S, ["Punches", "Punch-out", "Missing punch-out"]),
    ("Time", "Timesheet", "Bảng giờ làm", "Hours on projects; 'Bảng chấm công' is attendance, so the two must not share a name.", R, ["Timesheets"]),
    ("Time", "Shift", "Ca làm việc", "'Ca' on tight labels.", S, ["Shifts"]),
    ("Time", "Working hours", "Giờ làm việc", "Standard.", S, ["Working Hours"]),
    ("Time", "Overtime", "Tăng ca", "Screen and Learn; the law says 'làm thêm giờ', so statutory screens may keep it.", R),
    ("Time", "Time off", "Nghỉ phép", "The concept; the standard app name 'Ngày nghỉ' should follow.", R, ["Time Off", "Leave"]),
    ("Time", "Annual leave", "Nghỉ phép năm", "Legal term.", S, ["Annual Leave"]),
    ("Time", "Sick leave", "Nghỉ ốm", "Standard.", S, ["Sick Leave"]),
    ("Time", "Unpaid leave", "Nghỉ không lương", "Standard.", S, ["Unpaid Leave"]),
    ("Time", "Public holiday", "Ngày lễ", "'Nghỉ lễ' for the day off itself.", S, ["Holiday", "Public Holiday"]),
    ("Time", "Lock the week", "Khóa tuần", "Learn says 'Khoá' (new spelling); pick one spelling with 'Hủy'.", S),
    ("Time", "Workforce", "Công và ca", "The menu says 'Lực lượng lao động' (the national labour force); this area holds shifts and attendance.", R),
    # --- hiring and talent ----------------------------------------------------------------
    ("Hiring", "Hiring", "Tuyển dụng", "Standard.", S, ["Recruitment"]),
    ("Hiring", "Hiring request", "Đề xuất tuyển dụng", "Learn's term; files also say 'Yêu cầu tuyển dụng'.", R, ["Hiring Request"]),
    ("Hiring", "Candidate", "Ứng viên", "Standard.", S, ["Candidates", "Applicant"]),
    ("Hiring", "Interview", "Phỏng vấn", "'Buổi phỏng vấn' for one meeting.", S, ["Interviews"]),
    ("Hiring", "Scorecard", "Phiếu đánh giá", "Learn agrees.", S),
    ("Hiring", "Job offer", "Thư mời nhận việc", "Standard.", S, ["Offer", "Offers"]),
    ("Hiring", "Talent pool", "Kho ứng viên", "The Hiring tab.", S, ["Talent Pool"]),
    ("Hiring", "Talent", "Nhân tài", "The menu page.", S),
    ("Hiring", "Goal", "Mục tiêu", "Standard.", S, ["Goals"]),
    ("Hiring", "Training", "Đào tạo", "Standard.", S),
    ("Hiring", "Growth plan", "Kế hoạch phát triển", "Learn agrees.", S),
    ("Hiring", "Praise", "Khen ngợi", "The wall itself is 'Bảng vinh danh'.", S),
    # --- approvals and requests -----------------------------------------------------------
    ("Approvals", "Approval", "Phê duyệt", "Standard.", S, ["Approvals"]),
    ("Approvals", "Approve", "Phê duyệt", "Button; 'Duyệt' only as the typed PayAI confirm word DUYỆT.", S),
    ("Approvals", "Approved", "Đã phê duyệt", "Replaces 'Đã duyệt', 'Tán thành'.", S),
    ("Approvals", "Reject", "Từ chối", "Standard.", S, ["Turn down"]),
    ("Approvals", "Rejected", "Đã từ chối", "Learn agrees.", S),
    ("Approvals", "Sent back", "Đã trả lại", "Learn agrees; replaces 'Đã trả về'.", S, ["Send back"]),
    ("Approvals", "Waiting for approval", "Chờ phê duyệt", "Learn; drop the 'Đang' on chips.", S, ["Pending approval", "To approve"]),
    ("Approvals", "Submit", "Gửi", "'Gửi phê duyệt' when it starts an approval.", S, ["Submit for approval"]),
    ("Approvals", "Approver", "Người phê duyệt", "Standard.", S, ["Approvers"]),
    ("Approvals", "Approval route", "Lộ trình phê duyệt", "Learn agrees.", S),
    ("Approvals", "Approval step", "Bước phê duyệt", "Learn agrees.", S),
    ("Approvals", "Approval cover", "Người trực thay phê duyệt", "Learn agrees; 'ủy quyền' for a delegation.", S, ["Delegate", "Delegation"]),
    ("Approvals", "Approvals inbox", "Hộp thư phê duyệt", "The Home tab says so; Learn says 'Hộp phê duyệt'.", S, ["Inbox"]),
    ("Approvals", "Request", "Yêu cầu", "Standard.", S, ["Requests"]),
    ("Approvals", "Ask HR", "Hỏi Nhân sự", "The Home tab.", S),
    # --- expenses -------------------------------------------------------------------------
    ("Expenses", "Expense", "Chi phí", "Standard.", S, ["Expenses"]),
    ("Expenses", "Expense claim", "Yêu cầu hoàn chi phí", "The Expenses tab.", S, ["Claim", "Claims", "Reimbursement"]),
    ("Expenses", "Business trip", "Chuyến công tác", "Never 'Chuyến đi' (a holiday trip).", S, ["Trip", "Trips"]),
    ("Expenses", "Per diem", "Công tác phí", "Standard.", S),
    ("Expenses", "Receipt", "Hóa đơn", "'Chứng từ' for any accounting proof.", R, ["Receipts"]),
    # --- the app itself ---------------------------------------------------------------------
    ("App", "Home", "Trang chủ", "Standard.", S),
    ("App", "Overview", "Tổng quan", "Hub first tab; use it for 'Dashboard' too.", S, ["Dashboard"]),
    ("App", "Insights", "Phân tích", "The menu page.", S),
    ("App", "Compliance", "Tuân thủ", "The menu page.", S),
    ("App", "Settings", "Cài đặt", "Standard; 'Thiết lập' is Setup.", S),
    ("App", "Setup", "Thiết lập", "Standard.", S),
    ("App", "Configuration", "Cấu hình", "Standard.", S),
    ("App", "Import", "Nhập dữ liệu", "'Nhập' on buttons; the Payroll tab is 'Đầu vào' (Inputs).", S, ["Inputs"]),
    ("App", "Export", "Xuất", "Never 'Xuất khẩu' (trade export).", S),
    ("App", "Column mapping", "Ánh xạ cột", "Learn agrees; never 'lập bản đồ'.", S, ["Mapping"]),
    ("App", "Data source", "Nguồn dữ liệu", "Replaces 'Dữ liệu Nguồn'.", S, ["Data Source", "Source"]),
    ("App", "Connector", "Kết nối", "Learn says 'Đầu nối' (a plug); the Connections tab says 'Kết nối'.", R, ["Connectors", "Connection"]),
    ("App", "Sync", "Đồng bộ", "Standard.", S),
    ("App", "Draft", "Nháp", "Standard.", S),
    ("App", "Done", "Hoàn tất", "Replaces 'Xong' on chips.", S),
    ("App", "Cancel", "Hủy", "Pick one spelling: 'Hủy' (33 entries) over 'Huỷ' (6).", S),
    ("App", "Cancelled", "Đã hủy", "Standard.", S, ["Canceled"]),
    ("App", "Confirm", "Xác nhận", "Standard.", S),
    ("App", "Validate", "Xác nhận", "Never 'Xác thực' (to authenticate).", S),
    ("App", "Status", "Trạng thái", "Standard.", S),
    ("App", "Stage", "Bước", "A step of a process ('Bước 2/5'); never 'Sân khấu' (a theatre stage).", S, ["Step"]),
    ("App", "Lens", "Góc nhìn", "Never 'Ống kính' (a camera lens).", S, ["Lenses"]),
    ("App", "Rail", "Thanh bên", "Learn agrees.", S, ["Sidebar"]),
    ("App", "Needs you", "Cần bạn", "Learn and the Home bar agree.", S),
    ("App", "Flag", "Gắn cờ", "Learn's card says 'Cờ cảnh báo'.", S),
    ("App", "History", "Lịch sử", "Standard.", S),
    ("App", "Audit trail", "Lịch sử thay đổi", "Never 'Dấu vết kiểm toán'.", S, ["Audit Trail", "Audit log"]),
    ("App", "Search", "Tìm kiếm", "Standard.", S),
    ("App", "Filter", "Bộ lọc", "Noun; the verb is 'Lọc'.", S, ["Filters"]),
    ("App", "Group by", "Nhóm theo", "Replaces 'Nhóm Bởi'.", S, ["Group By"]),
    ("App", "Archive", "Lưu trữ", "Standard.", S, ["Archived"]),
    ("App", "Active", "Đang hoạt động", "'Đang hiệu lực' for a contract.", S),
    ("App", "Overdue", "Quá hạn", "Standard.", S),
    ("App", "Due date", "Hạn", "'Hạn chót' for a deadline.", S, ["Deadline"]),
    ("App", "Reminder", "Nhắc nhở", "Standard.", S, ["Reminders"]),
    ("App", "Notes", "Ghi chú", "Standard.", S, ["Note"]),
    ("App", "Attachment", "Tệp đính kèm", "Standard.", S, ["Attachments"]),
    ("App", "File", "Tệp", "On screens; 'file' is understood but mixes languages.", R),
    ("App", "Template", "Mẫu", "Standard.", S, ["Templates"]),
    ("App", "Report", "Báo cáo", "Standard.", S, ["Reports"]),
    ("App", "Permission group", "Nhóm quyền", "Learn agrees.", S),
    ("App", "Access role", "Vai trò truy cập", "Learn agrees.", S),
    ("App", "Month", "Tháng", "Standard; dates as 'Tháng 10/2026', never 'thg 10 2026' on headings.", S),
    ("App", "Year", "Năm", "Standard.", S),
]


def learn_terms():
    path = os.path.join(C.REPO, "docs", "tutorial_poc", "author", "data.js")
    out = {}
    if not os.path.exists(path):
        return out
    s = open(path, encoding="utf-8").read()
    i = s.find("const GLOSSARY = {")
    j = s.find("\n};", i)
    for m in re.finditer(r'term: B\("([^"]+)",\s*"([^"]+)"\)', s[i:j]):
        out[C.norm(m.group(1))] = m.group(2)
    return out


def variants():
    idx = collections.defaultdict(collections.Counter)
    for m in C.our_modules():
        po = os.path.join(C.REPO, m, "i18n", "vi_VN.po")
        if not os.path.exists(po):
            continue
        pot = os.path.join(C.REPO, m, "i18n", m + ".pot")
        entries, _, _ = PS.effective_entries(po, pot if os.path.exists(pot) else None)
        for e in entries:
            if e.msgstr.strip():
                idx[C.norm(e.msgid)][re.sub(r"\s+", " ", e.msgstr.strip()).rstrip(" .:…")] += 1
    return idx


def build():
    idx, learn = variants(), learn_terms()
    rows = []
    for row in CHOICES:
        area, en, vi, why, flag = row[:5]
        extra = row[5] if len(row) > 5 else []
        c = collections.Counter()
        keys = {C.norm(en)} | {C.norm(x) for x in extra}
        keys |= {k + "s" for k in list(keys)}
        for k in keys:
            c.update(idx.get(k, {}))
        lt = learn.get(C.norm(en)) or next((learn[C.norm(x)] for x in extra if C.norm(x) in learn), "")
        rows.append(dict(area=area, en=en, vi=vi, why=why, flag=flag, learn=lt,
                         variants=sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))))
    return rows


def to_md(rows):
    n_rev = sum(1 for r in rows if r["flag"])
    out = ["# VIFIX — Vietnamese glossary (draft for the owner's review)", "",
           "Generated by `docs/handovers/vifix/tools/vifix_glossary_build.py`; edit the choices there, not here.",
           "One Vietnamese term per concept. **Variants now** are every Vietnamese our files use today for that "
           "English (with how many entries), so each fix wave knows what to replace. **Learn** is the term the Learn "
           "glossary card uses. Rows marked **REVIEW** are choices the owner should confirm (%d of %d)." % (n_rev, len(rows)),
           "", "Rules that apply to every term: sentence case (capitalise the first word only, plus names and legal "
           "titles); no English words inside Vietnamese except the allowlist (brand names, file types, BHXH/BHYT/BHTN, "
           "currency codes); one spelling of 'hủy/khóa' (old tone placement, as most files use).", ""]
    area = None
    for i, r in enumerate(rows, 1):
        if r["area"] != area:
            area = r["area"]
            out += ["", "## " + area, "", "| # | English | Use | Variants now | Learn | Why | Review |",
                    "|---|---|---|---|---|---|---|"]
        var = " · ".join("%s ×%d" % (v, n) for v, n in r["variants"][:6]) or "—"
        out.append("| %d | %s | **%s** | %s | %s | %s | %s |" % (
            i, r["en"], r["vi"], var.replace("|", "\\|"), r["learn"] or "—", r["why"], "**REVIEW**" if r["flag"] else ""))
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(C.REPO, "docs", "handovers", "vifix", "VIFIX_GLOSSARY.md"))
    a = ap.parse_args()
    rows = build()
    open(a.out, "w", encoding="utf-8").write(to_md(rows))
    print("terms %d, review %d -> %s" % (len(rows), sum(1 for r in rows if r["flag"]), a.out))


if __name__ == "__main__":
    main()
