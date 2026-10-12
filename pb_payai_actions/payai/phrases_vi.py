# -*- coding: utf-8 -*-
"""P4 — THE VIETNAMESE PHRASE TABLE.

One row per Action key: the ways a Vietnamese payroll officer orders it, in
the screens' own words ("chạy lương", "gửi duyệt", "duyệt", "trả lại",
"từ chối", "phiếu lương", "tờ khai"). Written WITH marks; the registry tries
each on the marked text and again with every mark folded away, so a person
typing without marks ("duyet bang luong thang 6") is understood too.

Named groups are slot texts, exactly like the English table; the slot
resolvers read Vietnamese months ("tháng 6", "tháng 12 năm 2031"), amounts
("500.000", "5 triệu") and dates ("từ tháng 11", "1/11/2026").

Politeness ("bạn giúp tôi …", "… nhé", "… được không") is cut before these
run (`registry.normalise_vi`). A how/why question ("làm sao để …") is never
an order (`registry.looks_like_question`).
"""

#: "… vì <reason>", "… với ghi chú <note>", "…: <reason>", "… — <reason>".
REASON_TAIL = (r'(?:(?:\s+(?:vì|bởi\s+vì|lý\s+do:?|ghi\s+chú:?|với\s+(?:lý\s+do|ghi\s+chú)'
               r'(?:\s+là)?|kèm\s+(?:lý\s+do|ghi\s+chú)(?:\s+là)?)|\s*[:—]|\s+-)\s+'
               r'(?P<reason>.+))?$')

_VAL = (r'(?P<value>[₫$]?\s*[0-9][0-9.,\s]*(?:k|nghìn|ngàn|tr|triệu|tỷ|m)?'
        r'(?:\s*(?:vnd|đồng|đ|₫))?)')
_FROM = (r'(?:\s+(?:mỗi|một|hàng)\s+tháng|\s*/\s*tháng)?'
         r'(?:\s+(?:từ|bắt\s+đầu\s+từ|kể\s+từ|áp\s+dụng\s+từ|có\s+hiệu\s+lực\s+từ)\s+(?P<from>.+))?$')
_PAY_WORDS = r'(?:phụ\s+cấp|lương|thưởng|trợ\s+cấp|khấu\s+trừ|tăng\s+ca|hỗ\s+trợ|tiền)'

PHRASES_VI = {
    'what_can_you_do': (
        r'^(?:payai\s+)?(?:có\s+thể\s+)?làm\s+(?:được\s+)?(?:những\s+)?(?:việc\s+)?gì'
        r'(?:\s+cho\s+(?:tôi|mình|em))?(?:\s+(?:ở\s+đây|được))?$',
        r'^(?:giúp|hỗ\s+trợ)\s+(?:được\s+)?(?:tôi\s+|mình\s+|em\s+)?(?:những\s+)?(?:việc\s+)?gì$',
        r'^(?:trợ\s+giúp|danh\s+sách\s+lệnh|các\s+lệnh)$',
    ),
    'open_screen': (
        r'^(?:mở|vào|đi\s+(?:đến|tới)|chuyển\s+(?:đến|sang|tới)|đưa\s+(?:tôi|mình|em)\s+'
        r'(?:đến|tới|vào)|cho\s+(?:tôi|mình|em)\s+(?:vào|đến))\s+(?:trang\s+|màn\s+hình\s+|'
        r'mục\s+|tab\s+)?(?P<door>.+?)(?:\s+(?:lên|ra))?$',
        r'^xem\s+(?:trang\s+|màn\s+hình\s+|mục\s+)(?P<door>.+)$',
        r'^xem\s+(?P<door>(?:các\s+)?(?:phiếu\s+lương|phê\s+duyệt|hồ\s+sơ)\b.*)$',
    ),
    'run_status': (
        r'^(?!.*\b(?:màn\s+hình|excel|phiếu)\b)(?:xem|kiểm\s+tra|tình\s+hình|tình\s+trạng|'
        r'trạng\s+thái)\s+(?:của\s+)?(?P<run>.*\blương\b.*)$',
        r'^(?P<run>.*\b(?:bảng|đợt|kỳ)\s+lương\b.*?)\s+(?:đang\s+)?(?:ở\s+đâu|thế\s+nào|'
        r'ra\s+sao|tới\s+đâu|đến\s+đâu|sao\s+rồi)$',
    ),
    'download_run_excel': (
        r'^(?:tải|xuất|lấy|gửi\s+(?:tôi|mình|em))\s+(?:về\s+)?(?:file\s+|tệp\s+)?'
        r'(?:excel|bảng\s+tính|xlsx)(?:\s+(?:của|cho|về))?(?:\s+(?P<run>.+))?$',
        r'^(?:tải|xuất)\s+(?:về\s+)?(?P<run>(?=.*\blương\b).+?)\s+(?:ra|sang|thành|về|dạng)\s+excel$',
        r'^(?:tải|xuất)\s+(?:về\s+)?(?P<run>.*\b(?:bảng|đợt|kỳ)\s+lương\b.*)$',
    ),
    'run_payroll': (
        r'^(?:chạy|tính|làm|xử\s+lý|lập|tạo)\s+(?:(?:bảng|đợt|kỳ)\s+)?lương(?:\s+mới)?\b'
        r'\s*(?P<period>.*?)(?:\s*,?\s+(?:cho|của)\s+(?P<scheme>.+))?$',
    ),
    'submit_run': (
        r'^(?:gửi|trình|nộp|chuyển)\s+(?:đi\s+)?(?:duyệt|phê\s+duyệt)\s+(?P<run>.+)$',
        r'^(?:gửi|trình|nộp|chuyển)\s+(?P<run>.+?)\s+(?:đi\s+|để\s+|cho\s+(?:người\s+)?|lên\s+)?'
        r'(?:duyệt|phê\s+duyệt)$',
    ),
    'send_payslips': (
        r'^(?:gửi|phát|email|chuyển)\s+(?:(?:các|những)\s+)?phiếu\s+lương\b'
        r'(?:\s+(?:của|cho))?\s*(?P<run>.*)$',
    ),
    'update_pay_data': (
        # "đổi phụ cấp ăn trưa của Vũ Khánh Chi thành 500.000 từ tháng 11"
        r'^(?:đổi|thay\s+đổi|sửa|cập\s+nhật|đặt|chỉnh)\s+(?P<field>.+?)\s+(?:của|cho)\s+'
        r'(?P<person>.+?)\s+(?:thành|là|lên|xuống|=|bằng|sang)\s+' + _VAL + _FROM,
        # "cho Linh phụ cấp 500.000 từ tháng 7", "tăng phụ cấp … cho Linh lên …"
        r'^(?:cho|tăng|giảm|nâng|hạ)\s+(?P<person>.+?)\s+(?P<field>' + _PAY_WORDS +
        r'[^0-9₫$]*?)\s+(?:là\s+|thành\s+|=\s*|lên\s+|xuống\s+)?' + _VAL + _FROM,
        r'^(?:tăng|giảm|nâng|hạ)\s+(?P<field>' + _PAY_WORDS + r'[^0-9₫$]*?)\s+(?:của|cho)\s+'
        r'(?P<person>.+?)\s+(?:lên|xuống|thành|còn)\s+' + _VAL + _FROM,
    ),
    'filing_prepare': (
        r'^(?:chuẩn\s+bị|lập|tạo|làm|soạn|nộp)\s+(?P<filing>(?:tờ\s+khai|(?:báo\s+cáo|hồ\s+sơ)'
        r'\s+(?=thuế|bảo\s+hiểm|bhxh|bhyt|tncn))\b.*?)(?:\s+(?:cho\s+|của\s+)?'
        r'(?P<period>(?:tháng|t\d)\b.*))?$',
    ),
    'approve_item': (
        r'^(?:phê\s+duyệt|duyệt|chấp\s+thuận)\s+(?P<item>.+?)' + REASON_TAIL,
    ),
    'send_back_item': (
        r'^(?:trả\s+lại|trả\s+về|gửi\s+trả(?:\s+lại)?)\s+(?P<item>.+?)' + REASON_TAIL,
        r'^trả\s+(?P<item>.+?)\s+(?:lại|về)(?:\s+cho\s+\S+(?:\s+\S+)?)?' + REASON_TAIL,
    ),
    'reject_item': (
        r'^(?:từ\s+chối|bác\s+bỏ|bác)\s+(?P<item>.+?)' + REASON_TAIL,
    ),
    'never_destructive': (
        r'^(?=.*\b(?:lương|phiếu|hồ\s+sơ|nhân\s+viên|hợp\s+đồng)\b)(?:xoá|xóa|huỷ|hủy|gỡ)\s+'
        r'(?:bỏ\s+)?(?:hết\s+|tất\s+cả\s+)?(?P<what>.+)$',
    ),
}
