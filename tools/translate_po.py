#!/usr/bin/env python3
"""
Odoo PO File Translator — English → Vietnamese

Reusable script for translating .po files using a comprehensive
payroll-focused dictionary. Handles:
- Empty msgstr entries
- Entries where msgstr == msgid (untranslated)
- Skips code/HTML blocks, proper nouns, and technical terms
- Creates backups before modifying

Usage:
    python3 translate_po.py                    # Translate all target modules
    python3 translate_po.py path/to/vi_VN.po   # Translate a single file
    python3 translate_po.py --dry-run          # Preview without modifying
    python3 translate_po.py --stats            # Show stats only
"""
import argparse
import os
import re
import shutil
import sys
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# TRANSLATION DICTIONARY
# Organized by category for maintainability.
# Add new terms here as needed.
# ═══════════════════════════════════════════════════════════════

DICT_PAYROLL_CORE = {
    # Salary & Pay
    "Salary": "Lương",
    "Basic Salary": "Lương cơ bản",
    "Gross Salary": "Lương gộp",
    "Net Salary": "Lương thực nhận",
    "Net Pay": "Thực nhận",
    "Gross Pay": "Tổng thu nhập",
    "Total Income": "Tổng thu nhập",
    "Income": "Thu nhập",
    "Payslip": "Phiếu lương",
    "Payslips": "Phiếu lương",
    "Payslip Lines": "Dòng phiếu lương",
    "Payslip Line": "Dòng phiếu lương",
    "Payslip Batches": "Đợt lương",
    "Payslip Name": "Tên phiếu lương",
    "Payroll": "Bảng lương",
    "Payroll Report": "Báo cáo lương",
    "Payroll Structure": "Cơ cấu lương",
    "Salary Structure": "Cơ cấu lương",
    "Salary Rule": "Quy tắc lương",
    "Salary Rules": "Quy tắc lương",
    "Salary Rule Category": "Danh mục quy tắc lương",
    "Salary Component": "Thành phần lương",
    "Salary Components": "Thành phần lương",
    "Salary Configuration": "Cấu hình lương",
    "Salary Slip": "Phiếu lương",
    "Salary Computation": "Tính lương",
    "Compute Sheet": "Tính toán bảng lương",
    "Compute Salary": "Tính lương",
    "Run Payroll": "Chạy bảng lương",
    "Confirm Payslip": "Xác nhận phiếu lương",

    # Allowance & Benefits
    "Allowance": "Phụ cấp",
    "Allowances": "Phụ cấp",
    "Meal Allowance": "Phụ cấp cơm",
    "Transport Allowance": "Phụ cấp đi lại",
    "Transportation Allowance": "Phụ cấp đi lại",
    "Housing Allowance": "Phụ cấp nhà ở",
    "Phone Allowance": "Phụ cấp điện thoại",
    "Petrol Allowance": "Phụ cấp xăng xe",
    "Responsibility Allowance": "Phụ cấp trách nhiệm",
    "Hazard Allowance": "Phụ cấp độc hại",
    "Seniority Allowance": "Phụ cấp thâm niên",
    "Other Allowances": "Phụ cấp khác",
    "Benefits": "Phúc lợi",
    "Bonus": "Thưởng",
    "Performance Bonus": "Thưởng hiệu quả công việc",
    "KPI Bonus": "Thưởng KPI",

    # Deductions & Tax
    "Deduction": "Khấu trừ",
    "Deductions": "Các khoản trừ",
    "Tax": "Thuế",
    "Personal Income Tax": "Thuế thu nhập cá nhân",
    "PIT": "Thuế TNCN",
    "Tax Code": "Mã số thuế",
    "Tax Finalization": "Quyết toán thuế",
    "Dependents": "Người phụ thuộc",
    "Family Deduction": "Giảm trừ gia cảnh",

    # Insurance
    "Social Insurance": "Bảo hiểm xã hội",
    "Health Insurance": "Bảo hiểm y tế",
    "Unemployment Insurance": "Bảo hiểm thất nghiệp",
    "Insurance": "Bảo hiểm",
    "Union Fee": "Phí công đoàn",
    "Trade Union": "Công đoàn",

    # Attendance & Leave
    "Attendance": "Chấm công",
    "Leave": "Nghỉ phép",
    "Leaves": "Nghỉ phép",
    "Annual Leave": "Nghỉ phép năm",
    "Sick Leave": "Nghỉ ốm",
    "Maternity Leave": "Nghỉ thai sản",
    "Unpaid Leave": "Nghỉ không lương",
    "Personal Leave": "Nghỉ việc riêng",
    "Compensatory Leave": "Nghỉ bù",
    "Remaining Leave": "Phép còn lại",
    "Working Days": "Ngày làm việc",
    "Standard Days": "Công chuẩn",
    "Actual Days": "Công thực tế",
    "Timesheet": "Bảng công",
    "Timekeeping": "Chấm công",
    "Check In": "Giờ vào",
    "Check Out": "Giờ ra",
    "Working Hours": "Giờ làm việc",
    "Leave Type": "Loại nghỉ phép",
    "Leave Request": "Yêu cầu nghỉ phép",
    "Leave Allocation": "Phân bổ nghỉ phép",
    "Absence": "Vắng mặt",
    "Present": "Có mặt",
    "Late": "Đi trễ",
    "Early Leave": "Về sớm",
    "Overtime": "Tăng ca",
    "Overtime Hours": "Giờ tăng ca",
    "Overtime Rules": "Quy tắc tăng ca",
    "Overtime Rate": "Hệ số tăng ca",
    "Night Shift": "Ca đêm",
    "Day Shift": "Ca ngày",
    "Shift": "Ca làm việc",
    "Shifts": "Ca làm việc",
    "Shift Planning": "Kế hoạch ca làm việc",
    "Shift Roster": "Lịch ca",
    "Live Attendance": "Chấm công trực tiếp",
    "Timecard": "Thẻ công",
    "Timecards": "Thẻ công",

    # Employee
    "Employee": "Nhân viên",
    "Employees": "Nhân viên",
    "Employee ID": "Mã nhân viên",
    "Employee Name": "Tên nhân viên",
    "Full Name": "Họ tên",
    "Department": "Phòng ban",
    "Departments": "Phòng ban",
    "Job Position": "Chức danh",
    "Job Title": "Chức vụ",
    "Manager": "Quản lý",
    "Contract": "Hợp đồng",
    "Contracts": "Hợp đồng",
    "Contract Type": "Loại hợp đồng",
    "Labor Contract": "Hợp đồng lao động",
    "Probation": "Thử việc",
    "Probation Contract": "Hợp đồng thử việc",
    "Date of Birth": "Ngày sinh",
    "Gender": "Giới tính",
    "Male": "Nam",
    "Female": "Nữ",
    "Join Date": "Ngày vào làm",
    "Start Date": "Ngày bắt đầu",
    "End Date": "Ngày kết thúc",
    "Hire Date": "Ngày tuyển dụng",
    "Work Location": "Địa điểm làm việc",
    "Working Status": "Trạng thái làm việc",
    "Active": "Đang hoạt động",
    "Archived": "Đã lưu trữ",
    "Resigned": "Đã nghỉ việc",
    "Marital Status": "Tình trạng hôn nhân",
    "Nationality": "Quốc tịch",
    "ID Card": "CMND/CCCD",
    "Bank Account": "Tài khoản ngân hàng",
    "Bank Name": "Tên ngân hàng",
    "Account Number": "Số tài khoản",
    "Emergency Contact": "Liên hệ khẩn cấp",
    "Address": "Địa chỉ",
    "Phone Number": "Số điện thoại",
    "Email": "Email",

    # Company / Organization
    "Company": "Công ty",
    "Companies": "Công ty",
    "Branch": "Chi nhánh",
    "Head Office": "Trụ sở chính",
    "Organization": "Tổ chức",

    # Reports & Analytics
    "Report": "Báo cáo",
    "Reports": "Báo cáo",
    "Analytics": "Phân tích",
    "Dashboard": "Bảng điều khiển",
    "Analysis": "Phân tích",
    "Summary": "Tóm tắt",
    "Comparison": "So sánh",
    "Variance": "Chênh lệch",
    "Trend": "Xu hướng",
    "Chart": "Biểu đồ",
    "Graph": "Đồ thị",
    "Statistics": "Thống kê",
    "Export": "Xuất",
    "Import": "Nhập",
    "Download": "Tải xuống",
    "Upload": "Tải lên",
    "Preview": "Xem trước",
    "Print": "In",
    "Generate": "Tạo",
    "Generate Report": "Tạo báo cáo",

    # Bank Export
    "Bank Export": "Xuất ngân hàng",
    "Bank File": "Tệp ngân hàng",
    "Bank Transfer": "Chuyển khoản",
    "Export Bank File": "Xuất tệp ngân hàng",
    "Export Format": "Định dạng xuất",
    "Separator": "Ký tự phân cách",
    "Include Headers": "Bao gồm tiêu đề",
    "Filename": "Tên tệp",
    "Export File": "Tệp xuất",

    # Approval Workflow
    "Approve": "Phê duyệt",
    "Approved": "Đã phê duyệt",
    "Approval": "Phê duyệt",
    "Reject": "Từ chối",
    "Rejected": "Đã từ chối",
    "Pending": "Đang chờ",
    "Draft": "Nháp",
    "Done": "Hoàn thành",
    "Confirm": "Xác nhận",
    "Confirmed": "Đã xác nhận",
    "Cancel": "Hủy",
    "Cancelled": "Đã hủy",
    "Submit": "Gửi",
    "Reset": "Đặt lại",
    "Reset to Draft": "Đặt lại nháp",
    "Lock": "Khóa",
    "Unlock": "Mở khóa",
    "Close": "Đóng",
    "Closed": "Đã đóng",
    "Open": "Mở",
    "Archive": "Lưu trữ",
    "Unarchive": "Bỏ lưu trữ",

    # Common Odoo Terms
    "Name": "Tên",
    "Description": "Mô tả",
    "Notes": "Ghi chú",
    "Note": "Ghi chú",
    "Type": "Loại",
    "Category": "Danh mục",
    "Code": "Mã",
    "Sequence": "Thứ tự",
    "Amount": "Số tiền",
    "Rate": "Tỷ lệ",
    "Quantity": "Số lượng",
    "Total": "Tổng cộng",
    "Total Amount": "Tổng số tiền",
    "Currency": "Tiền tệ",
    "Date": "Ngày",
    "Date From": "Từ ngày",
    "Date To": "Đến ngày",
    "Period": "Kỳ",
    "Month": "Tháng",
    "Year": "Năm",
    "From": "Từ",
    "To": "Đến",
    "Status": "Trạng thái",
    "State": "Trạng thái",
    "Action": "Hành động",
    "Actions": "Hành động",
    "Settings": "Cài đặt",
    "Configuration": "Cấu hình",
    "Search": "Tìm kiếm",
    "Filter": "Lọc",
    "Group By": "Nhóm theo",
    "Sort By": "Sắp xếp theo",
    "Created on": "Ngày tạo",
    "Created by": "Người tạo",
    "Last Updated on": "Cập nhật lần cuối",
    "Last Updated by": "Người cập nhật",
    "Save": "Lưu",
    "Discard": "Hủy bỏ",
    "Create": "Tạo mới",
    "Edit": "Chỉnh sửa",
    "Delete": "Xóa",
    "Duplicate": "Nhân bản",
    "Details": "Chi tiết",
    "View": "Xem",
    "Warning": "Cảnh báo",
    "Error": "Lỗi",
    "Information": "Thông tin",
    "Yes": "Có",
    "No": "Không",
    "True": "Đúng",
    "False": "Sai",
    "Enabled": "Đã bật",
    "Disabled": "Đã tắt",
    "All": "Tất cả",
    "None": "Không có",
    "Other": "Khác",
    "Unknown": "Không xác định",
    "Required": "Bắt buộc",
    "Optional": "Tùy chọn",
    "Default": "Mặc định",
    "Custom": "Tùy chỉnh",
    "Loading": "Đang tải",

    # Government Reports (pb_hr_govt)
    "Government Report": "Báo cáo chính phủ",
    "Government Reports": "Báo cáo chính phủ",
    "Social Insurance Report": "Báo cáo bảo hiểm xã hội",
    "Health Insurance Report": "Báo cáo bảo hiểm y tế",
    "Tax Report": "Báo cáo thuế",
    "PIT Report": "Báo cáo thuế TNCN",
    "Participant List": "Danh sách tham gia",
    "Declaration": "Kê khai",
    "Report Type": "Loại báo cáo",
    "Report Period": "Kỳ báo cáo",
    "Monthly": "Hàng tháng",
    "Quarterly": "Hàng quý",
    "Annually": "Hàng năm",
    "Semi-annually": "Nửa năm",
    "XLS Report": "Báo cáo XLS",
    "Generate XLS": "Tạo XLS",
    "Download Report": "Tải báo cáo",
    "Submission": "Nộp",
    "Submission Date": "Ngày nộp",
    "Registration": "Đăng ký",
    "Adjustment": "Điều chỉnh",
    "Increase": "Tăng",
    "Decrease": "Giảm",

    # Flow Dashboard
    "Flow Dashboard": "Bảng điều khiển quy trình",
    "Flow": "Quy trình",
    "Workflow": "Quy trình",
    "Process": "Quy trình",
    "Step": "Bước",
    "Stage": "Giai đoạn",
    "Level": "Cấp",
    "Level 1": "Cấp 1",
    "Level 2": "Cấp 2",
    "Level 3": "Cấp 3",
    "Batch": "Đợt",
    "Batch Name": "Tên đợt",
    "Batch Workflow": "Quy trình đợt",

    # Formula / Computation
    "Formula": "Công thức",
    "Formula Configuration": "Cấu hình công thức",
    "Computation": "Tính toán",
    "Calculation": "Phép tính",
    "Condition": "Điều kiện",
    "Expression": "Biểu thức",
    "Variable": "Biến",
    "Parameter": "Tham số",
    "Input": "Đầu vào",
    "Output": "Đầu ra",
    "Result": "Kết quả",
    "Minimum": "Tối thiểu",
    "Maximum": "Tối đa",
    "Average": "Trung bình",
    "Percentage": "Phần trăm",
    "Fixed": "Cố định",
    "Percentage of": "Phần trăm của",
    "Python Code": "Mã Python",

    # Common Actions / Messages
    "Are you sure?": "Bạn có chắc không?",
    "Confirm action": "Xác nhận hành động",
    "No data found": "Không tìm thấy dữ liệu",
    "No records found": "Không tìm thấy bản ghi",
    "Please select": "Vui lòng chọn",
    "Required field": "Trường bắt buộc",
    "Invalid value": "Giá trị không hợp lệ",
    "Operation completed": "Thao tác hoàn thành",
    "Operation failed": "Thao tác thất bại",
    "Access Denied": "Từ chối truy cập",
    "Select All": "Chọn tất cả",
    "Deselect All": "Bỏ chọn tất cả",

    # Payroll Analytics specifics
    "Payroll Analytics": "Phân tích bảng lương",
    "Analytics Dashboard": "Bảng phân tích",
    "Component Analysis": "Phân tích thành phần",
    "Department Summary": "Tóm tắt phòng ban",
    "Employee Summary": "Tóm tắt nhân viên",
    "Earnings": "Thu nhập",
    "Contribution Register": "Sổ đóng góp",
    "Contribution Registers": "Sổ đóng góp",
    "Payslip Run": "Đợt chạy lương",

    # Workforce specifics
    "On Shift": "Đang ca",
    "Checked Out": "Đã ra",
    "Not Started": "Chưa bắt đầu",
    "On Leave": "Đang nghỉ",
    "No one on shift": "Không ai đang ca",
    "All Departments": "Tất cả phòng ban",
    "Search employee": "Tìm nhân viên",

    # Misc
    "Refresh": "Làm mới",
    "Clear": "Xóa",
    "Back": "Quay lại",
    "Next": "Tiếp theo",
    "Previous": "Trước",
    "Home": "Trang chủ",
    "Help": "Trợ giúp",
    "About": "Giới thiệu",
    "Version": "Phiên bản",
    "License": "Giấy phép",
    "Language": "Ngôn ngữ",
    "Preferences": "Tùy chỉnh",
    "Profile": "Hồ sơ",
    "Log out": "Đăng xuất",
    "Log in": "Đăng nhập",
    "Password": "Mật khẩu",
    "Username": "Tên đăng nhập",
    "Wage": "Tiền lương",
    "Wage Type": "Loại tiền lương",
    "Structure Type": "Loại cơ cấu",
    "Worked Days": "Ngày công",
    "Worked Hours": "Giờ công",
    "Resource Calendar": "Lịch làm việc",
    "Schedule Pay": "Lịch trả lương",
    "Payment Method": "Phương thức thanh toán",
    "Reference": "Tham chiếu",
    "Credit Note": "Ghi có",
    "Appears on Payslip": "Hiển thị trên phiếu lương",
    "Condition Based on": "Điều kiện dựa trên",
    "Amount Type": "Loại số tiền",
    "Contribution": "Đóng góp",
    "Register": "Sổ",
    "Inputs": "Đầu vào",
    "Other Inputs": "Đầu vào khác",
    "Input Type": "Loại đầu vào",
    "Child Rules": "Quy tắc con",
    "Parent Rule": "Quy tắc cha",
    "Company Contribution": "Đóng góp công ty",
    "Employee Contribution": "Đóng góp nhân viên",
    "Always True": "Luôn đúng",
    "Range": "Phạm vi",
    "Condition Range": "Phạm vi điều kiện",
    "Fix Amount": "Số tiền cố định",
    "Percentage (%)": "Phần trăm (%)",
    "Percentage based on": "Phần trăm dựa trên",

    # ── Additional terms from untranslatable analysis ──
    # Payroll specifics
    "Accounting": "Kế toán",
    "Birthday": "Sinh nhật",
    "Bonuses": "Thưởng",
    "Confidential": "Bảo mật",
    "Connector": "Kết nối",
    "Daily": "Hàng ngày",
    "Deprecated": "Ngừng sử dụng",
    "Disconnected": "Đã ngắt kết nối",
    "Gratuity": "Phụ cấp thôi việc",
    "Hourly": "Theo giờ",
    "Inactive": "Không hoạt động",
    "Maintenance": "Bảo trì",
    "Minimal": "Tối thiểu",
    "Mixed Sources": "Nguồn hỗn hợp",
    "Modern": "Hiện đại",
    "Performance": "Hiệu suất",
    "Processed": "Đã xử lý",
    "Quarter": "Quý",
    "Schedule": "Lịch trình",
    "Text": "Văn bản",
    "Troubleshooting": "Xử lý sự cố",
    "Weekly": "Hàng tuần",
    "Yearly": "Hàng năm",
    "Bi-weekly": "Hai tuần một lần",
    "Display Name": "Tên hiển thị",
    "Last Modified on": "Sửa đổi lần cuối",
    "Taxes": "Thuế",
    "Verified": "Đã xác minh",
    "Verify": "Xác minh",
    "Parent": "Cha",
    "Hospital": "Bệnh viện",
    "Household": "Hộ gia đình",
    "Lookup Type": "Loại tra cứu",
    "Province/City": "Tỉnh/Thành phố",
    "District": "Quận/Huyện",
    "Commune/Ward": "Xã/Phường",
    "Cash": "Tiền mặt",
    "To Date": "Đến ngày",
    "From Date": "Từ ngày",
    "Boolean": "Đúng/Sai",
    "FTE %": "FTE %",
    "Skills Development Levy (SDL)": "Thuế phát triển kỹ năng (SDL)",
    "Vietnam PIT": "Thuế TNCN Việt Nam",
    "VN Union Fee": "Phí công đoàn VN",
    "Payslip Count": "Số phiếu lương",
    "Payslip Details Report": "Báo cáo chi tiết phiếu lương",
    "Payslip Lines by Contribution Registers": "Dòng phiếu lương theo sổ đóng góp",
    "Payroll Contribution Register Report": "Báo cáo sổ đóng góp bảng lương",
    "You cannot create a recursive salary structure.": "Bạn không thể tạo cơ cấu lương đệ quy.",
    "Payslip 'Date From' must be earlier 'Date To'.": "'Từ ngày' của phiếu lương phải trước 'Đến ngày'.",
    "Add a new contribution register": "Thêm sổ đóng góp mới",
    "A contribution register is a third party involved in the salary\\n            payment of the employees.": "Sổ đóng góp là bên thứ ba liên quan đến việc trả lương cho nhân viên.",
    # Government report specifics
    "Vietnam Government XLS Reports": "Báo cáo XLS Chính phủ Việt Nam",
    "Vietnam Government XLS Report Wizard": "Trình tạo báo cáo XLS Chính phủ Việt Nam",
    "Base model for Vietnamese government XLS reports": "Mô hình cơ sở cho báo cáo XLS chính phủ Việt Nam",
    "MAIL REPORT": "GỬI BÁO CÁO",
    # Analytics specifics
    "Increasing (>5%)": "Tăng (>5%)",
    "Stable (±5%)": "Ổn định (±5%)",
    "Context (JSON)": "Ngữ cảnh (JSON)",
    "Movements (JSON)": "Biến động (JSON)",
    "Approved payroll analytics will appear here for bank file generation.": "Phân tích bảng lương đã duyệt sẽ xuất hiện tại đây để tạo tệp ngân hàng.",
    "Payroll variance is within acceptable range (< 5%).": "Chênh lệch bảng lương trong phạm vi chấp nhận được (< 5%).",
    # Formula specifics
    "Order in which worksheets are appended to form the final structure": "Thứ tự nối bảng tính vào cơ cấu cuối cùng",
    "Short identifier used to group components in payslip and reporting.": "Mã ngắn dùng để nhóm thành phần trong phiếu lương và báo cáo.",
    "Select at least one prorated component when proration is enabled.": "Chọn ít nhất một thành phần tính theo tỷ lệ khi bật chế độ prorate.",
}

# Terms that should NOT be translated (proper nouns, codes, technical terms)
SKIP_TERMS = {
    'CSV', 'Excel', 'D3.js', 'API', 'URL', 'JSON', 'XML', 'XLS', 'XLSX',
    'PDF', 'HTML', 'CSS', 'SQL', 'Python', 'JavaScript',
    'Indonesia', 'Malaysia', 'Singapore', 'Thailand', 'Cambodia',
    'Australia', 'India', 'Vietnam', 'Philippines',
    'United Kingdom', 'United States',
    'Odoo', 'Payobook', 'THACO', 'Biztinct',
    'BHXH', 'BHYT', 'BHTN', 'TNCN',
    'BHXH630', 'BHXHDSTK01-DV_595', 'BangKeHS D01', 'D01-TS',
    'TangLaoDong', 'GiamLaoDong', 'PayrollBackup',
    'BD PHSK', 'OAuth 2.0', 'Bearer Token', 'Token URL',
    'Oracle HCM', 'SAP SuccessFactors', 'Zoho People', 'Zoho API Key',
    'Zoho Organization ID',
    'BPJS TK JKK', 'BPJS TK JKM',
    'API URL', 'RM', 'Rp', 'fx',
    'ID', 'OK', 'N/A',
}

# Vietnamese diacritical marks used to detect Vietnamese text
VIETNAMESE_CHARS = set('ăắằẳẵặâấầẩẫậđêếềểễệôốồổỗộơớờởỡợưứừửữựàáảãạèéẻẽẹìíỉĩịòóỏõọùúủũụỳýỷỹỵĂẮẰẲẴẶÂẤẦẨẪẬĐÊẾỀỂỄỆÔỐỒỔỖỘƠỚỜỞỠỢƯỨỪỬỮỰÀÁẢÃẠÈÉẺẼẸÌÍỈĨỊÒÓỎÕỌÙÚỦŨỤỲÝỶỸỴ')

def is_vietnamese_text(text):
    """Check if text contains Vietnamese diacritical characters."""
    return bool(set(text) & VIETNAMESE_CHARS)


def is_code_block(text):
    """Check if the msgid contains code/HTML that shouldn't be translated."""
    code_patterns = [
        r'<[a-z]+[\s>]',       # HTML tags
        r'__custom__\.',        # Python references
        r'class=[\"\']',        # CSS classes
        r'def \w+\(',           # Python functions
        r'self\.\w+',           # Python self references
        r'\$\{',                # Template expressions
        r'%(.*?)s',             # Python string formatting (partial)
        r'\bbase\.\w+',        # Odoo XML IDs
    ]
    for pattern in code_patterns:
        if re.search(pattern, text):
            return True
    return False


def should_skip(msgid):
    """Check if this entry should be skipped (code, proper nouns, etc)."""
    if not msgid or len(msgid.strip()) <= 1:
        return True
    if is_code_block(msgid):
        return True
    stripped = msgid.strip()
    if stripped in SKIP_TERMS:
        return True
    # Skip entries that are just numbers or codes
    if re.match(r'^[\d\s\.\-\+\/\%\(\)]+$', stripped):
        return True
    return False


def translate_msgid(msgid, dictionary):
    """
    Try to translate a msgid using the dictionary.
    Returns the translation or None if no match found.
    """
    stripped = msgid.strip()

    # Exact match (case-sensitive)
    if stripped in dictionary:
        return dictionary[stripped]

    # Exact match (case-insensitive)
    lower = stripped.lower()
    for key, val in dictionary.items():
        if key.lower() == lower:
            return val

    return None


def process_po_file(filepath, dictionary, dry_run=False):
    """
    Process a single PO file, translating empty/untranslated entries.
    IMPORTANT: This function preserves the original file structure exactly,
    only modifying `msgstr ""` lines to add translations. This is critical
    because Odoo 19's PO parser relies on #: references and multiline formatting.
    """
    if not os.path.isfile(filepath):
        print(f"  ⚠️  File not found: {filepath}")
        return 0

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')

    # Build a map of translations to apply: { line_number_of_msgstr: new_value }
    translations_to_apply = {}

    translated_count = 0
    skipped_count = 0
    already_done = 0
    untranslatable = []

    # Parse entries by walking through lines
    i = 0
    while i < len(lines):
        line = lines[i]

        # Find msgid lines
        if line.startswith('msgid "'):
            msgid_match = re.match(r'msgid "(.*)"$', line)
            if not msgid_match:
                i += 1
                continue

            msgid = msgid_match.group(1)
            msgid_start = i
            i += 1

            # Handle multiline msgid
            while i < len(lines) and lines[i].startswith('"'):
                cont_match = re.match(r'"(.*)"$', lines[i])
                if cont_match:
                    msgid += cont_match.group(1)
                i += 1

            # Now we should be at msgstr line
            if i < len(lines) and lines[i].startswith('msgstr "'):
                msgstr_match = re.match(r'msgstr "(.*)"$', lines[i])
                if not msgstr_match:
                    i += 1
                    continue

                msgstr = msgstr_match.group(1)
                msgstr_line = i
                i += 1

                # Handle multiline msgstr
                while i < len(lines) and lines[i].startswith('"'):
                    cont_match = re.match(r'"(.*)"$', lines[i])
                    if cont_match:
                        msgstr += cont_match.group(1)
                    i += 1

                # Skip the PO header (empty msgid)
                if not msgid:
                    continue

                # Skip if already translated (msgstr is non-empty AND different from msgid)
                if msgstr and msgstr != msgid:
                    already_done += 1
                    continue

                # Skip code blocks, proper nouns
                if should_skip(msgid):
                    skipped_count += 1
                    continue

                # If msgid is already Vietnamese, set msgstr = msgid
                if is_vietnamese_text(msgid):
                    translations_to_apply[msgstr_line] = msgid
                    translated_count += 1
                    continue

                # Try to translate using dictionary
                translation = translate_msgid(msgid, dictionary)
                if translation:
                    translations_to_apply[msgstr_line] = translation
                    translated_count += 1
                else:
                    untranslatable.append(msgid)
            else:
                continue
        else:
            i += 1

    # Apply translations in-place (only modify msgstr lines)
    if not dry_run and translated_count > 0:
        # Create backup
        backup_path = filepath + '.bak'
        shutil.copy2(filepath, backup_path)

        for line_num, translation in translations_to_apply.items():
            # Escape any special characters for PO format
            escaped = translation.replace('\\', '\\\\').replace('"', '\\"')
            # Only replace simple single-line msgstr "" entries
            old_line = lines[line_num]
            if re.match(r'^msgstr ""$', old_line):
                lines[line_num] = f'msgstr "{escaped}"'
            elif re.match(r'^msgstr ".*"$', old_line):
                # Replace existing (same-as-msgid) single-line msgstr
                lines[line_num] = f'msgstr "{escaped}"'

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    return {
        'total': already_done + translated_count + skipped_count + len(untranslatable),
        'already_done': already_done,
        'translated': translated_count,
        'skipped': skipped_count,
        'untranslatable': untranslatable,
    }


def main():
    parser = argparse.ArgumentParser(description='Translate Odoo PO files (EN→VI)')
    parser.add_argument('files', nargs='*', help='PO files to translate (default: all target modules)')
    parser.add_argument('--dry-run', action='store_true', help='Preview without modifying files')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')
    parser.add_argument('--show-untranslated', action='store_true', help='Show untranslatable entries')
    parser.add_argument('--base-dir', default='/Users/adity/Documents/GitHub/gitlocal',
                        help='Base directory of the Odoo project')
    args = parser.parse_args()

    # Default target modules
    if not args.files:
        target_modules = [
            'om_hr_payroll/i18n/vi_VN.po',
            'payroll_analytics_approval/i18n/vi_VN.po',
            'pb_hr_flow/i18n/vi_VN.po',
            'pb_hr_govt/i18n/vi_VN.po',
            'pb_hr_payroll_analytics/i18n/vi_VN.po',
            'pb_hr_payroll_base/i18n/vi_VN.po',
            'pb_hr_payroll_formula/i18n/vi_VN.po',
        ]
        files = [os.path.join(args.base_dir, m) for m in target_modules]
    else:
        files = args.files

    print("═" * 60)
    print("  Odoo PO Translator — English → Vietnamese")
    print("═" * 60)
    print(f"  Dictionary: {len(DICT_PAYROLL_CORE)} terms")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    grand_total = 0
    grand_translated = 0
    all_untranslatable = []

    for filepath in files:
        module = os.path.basename(os.path.dirname(os.path.dirname(filepath)))
        print(f"  Processing: {module}")

        result = process_po_file(filepath, DICT_PAYROLL_CORE, dry_run=args.dry_run or args.stats)
        if isinstance(result, int):
            continue

        grand_total += result['total']
        grand_translated += result['translated']

        print(f"    Total entries:    {result['total']}")
        print(f"    Already done:     {result['already_done']}")
        print(f"    Newly translated: {result['translated']}")
        print(f"    Skipped (code):   {result['skipped']}")
        print(f"    Untranslatable:   {len(result['untranslatable'])}")

        if args.show_untranslated and result['untranslatable']:
            print(f"    --- Untranslatable entries ---")
            for u in result['untranslatable'][:20]:
                print(f"      • {u[:80]}")
            if len(result['untranslatable']) > 20:
                print(f"      ... and {len(result['untranslatable']) - 20} more")

        all_untranslatable.extend(result['untranslatable'])
        print()

    print("═" * 60)
    print(f"  TOTAL: {grand_translated} entries translated across {len(files)} files")
    print(f"  Remaining untranslatable: {len(all_untranslatable)}")
    if not args.dry_run and not args.stats and grand_translated > 0:
        print(f"  Backups created as *.bak files")
    print("═" * 60)


if __name__ == '__main__':
    main()
