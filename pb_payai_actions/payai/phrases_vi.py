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
an order (`registry.looks_like_question`), and a sentence ending as a
question does ("… chưa", "… thế nào") never starts or decides anything.

FIX-1: a folded match never stands for an order word marked as ANOTHER
word (vi-9: "Bắc Ninh" is not "bác", "Huy chạy …" is not "hủy" —
`registry._folded_ok`); a pattern opening with
`registry.MARKED_ONLY` is never tried with its marks folded away (vi-3: "gỡ"
folds to the English "go").
"""
from .registry import MARKED_ONLY

#: "… vì <reason>", "… với ghi chú <note>", "…: <reason>", "… — <reason>".
REASON_TAIL = (r'(?:(?:\s+(?:vì|bởi\s+vì|lý\s+do:?|ghi\s+chú:?|với\s+(?:lý\s+do|ghi\s+chú)'
               r'(?:\s+là)?|kèm\s+(?:lý\s+do|ghi\s+chú)(?:\s+là)?)|\s*[:—]|\s+-)\s+'
               r'(?P<reason>.+))?$')

_VAL = (r'(?P<value>[₫$]?\s*[0-9][0-9.,\s]*(?:k|nghìn|ngàn|tr|triệu|tỷ|m)?'
        r'(?:\s*(?:vnd|đồng|đ|₫))?)')
_FROM = (r'(?:\s+(?:mỗi|một|hàng)\s+tháng|\s*/\s*tháng)?'
         r'(?:\s+(?:từ|bắt\s+đầu\s+từ|kể\s+từ|áp\s+dụng\s+từ|có\s+hiệu\s+lực\s+từ)\s+(?P<from>.+))?$')
_PAY_WORDS = r'(?:phụ\s+cấp|lương|thưởng|trợ\s+cấp|khấu\s+trừ|tăng\s+ca|hỗ\s+trợ|tiền)'
#: FIX-1 (P4 vi-7): "thêm" (more / by), "bớt" (less), "… đi 200.000" (down
#: BY) make the amount a change, not the new value: no phrase reads them as
#: "set to" (the model or a question takes over). "làm thêm" is overtime.
#: Third pass: only "thêm" / "bớt" that say BY — before the amount ("thêm
#: 500.000"), before who gets it ("thêm cho Linh"), or right after the verb
#: ("tăng thêm") — so a pay item's own name keeps them ("phụ cấp thêm giờ",
#: "phụ cấp làm thêm").
_NOT_A_DELTA = (r'(?!.*(?<!làm\s)(?<!\w)(?:thêm|bớt)\s+(?:[₫$]?\s*[0-9]|(?:cho|của|lên|xuống|nữa)(?!\w)))'
                r'(?!.*(?<!\w)(?:tăng|giảm|nâng|hạ|cộng|trừ)\s+(?:thêm|bớt)(?!\w))'
                r'(?!.*\s(?:đi|ra)\s+[₫$]?\s*[0-9])'
                r'(?!.*\s[0-9][0-9.,]*\s*(?:k|nghìn|ngàn|tr|triệu|đồng|đ)?\s+nữa(?!\w))')
_NOT_A_DELTA_SET = (r'(?!.*(?<!\w)(?:thêm|bớt)\s+[₫$]?\s*[0-9])'
                    r'(?!.*\s(?:đi|ra)\s+[₫$]?\s*[0-9])'
                    r'(?!.*\s[0-9][0-9.,]*\s*(?:k|nghìn|ngàn|tr|triệu|đồng|đ)?\s+nữa(?!\w))')
#: FIX-1 (P4 vi-8): words after an approve / send-back / reject verb that are
#: not what is decided ("duyệt lại …", "duyệt giúp tôi …", "từ chối duyệt …").
_DECIDE_FILLER = (r'(?:\s+(?:lại|luôn|hết|giúp|giùm|hộ|dùm)(?:\s+(?:tôi|mình|em|với))?)*')
#: FIX-1 (P4 vi-9): "trả X lại/về" is a send-back only when X is something
#: that waits for a decision — not "trả lời" (answer), "trả lương" (pay), or
#: "trả lại tiền thừa" (a refund).
_ITEM_WORDS = (r'(?=.*\b(?:bảng\s+lương|đợt\s+lương|kỳ\s+lương|phiếu|yêu\s+cầu|đơn|'
               r'đề\s+(?:xuất|nghị)|tăng\s+ca|làm\s+thêm|nghỉ|phép|chi\s+phí|tạm\s+ứng|'
               r'hợp\s+đồng|điều\s+chỉnh|thay\s+đổi|hồ\s+sơ|công\s+tác|thanh\s+toán|'
               r'(?:cái|việc|mục)\s+(?:này|đó|kia|ấy)|nó)\b)')

#: FIX-1 (P4 vi-9, second pass): what a bare "bác" (uncle / aunt, as well
#: as "turn down") decides must OPEN with a word for a waiting request:
#: "bác yêu cầu của Lan", never "bác Hùng gửi bảng lương …".
_ITEM_START = (r'(?=(?:(?:các|những|cái|mục)\s+)?(?:bảng\s+lương|đợt\s+lương|kỳ\s+lương|'
               r'phiếu|yêu\s+cầu|đơn|đề\s+(?:xuất|nghị)|tăng\s+ca|làm\s+thêm|nghỉ|phép|'
               r'chi\s+phí|tạm\s+ứng|hợp\s+đồng|điều\s+chỉnh|thay\s+đổi|hồ\s+sơ|công\s+tác|'
               r'thanh\s+toán|(?:cái|việc|mục)\s+(?:này|đó|kia|ấy)|nó)\b)')
#: The little words that soften a question at its end ("… thế nào ạ",
#: "… sao rồi vậy").
_ASK_SOFT = r'(?:\s*,?\s*(?:ạ|à|vậy|nhỉ|thế|hả|hở|chứ|nhé|nha|đấy|bạn|bạn\s+ơi))*'

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
        # FIX-1 (P4 vi-1): "duyệt / chạy bảng lương thế nào" asks HOW to do
        # it — the answers' job, not a run's status.
        r'^(?!(?:phê\s+duyệt|duyệt|chạy|tính|gửi|trình|nộp|trả|từ\s+chối|xoá|xóa|huỷ|hủy|'
        r'tạo|lập|làm|tải|xuất)\b)'
        r'(?P<run>.*\b(?:bảng|đợt|kỳ)\s+lương\b.*?)\s+(?:đang\s+)?(?:ở\s+đâu|thế\s+nào|'
        r'ra\s+sao|tới\s+đâu|đến\s+đâu|sao\s+rồi)' + _ASK_SOFT + r'$',
    ),
    'download_run_excel': (
        r'^(?:tải|xuất|lấy|gửi\s+(?:tôi|mình|em))\s+(?:về\s+)?(?:file\s+|tệp\s+)?'
        r'(?:excel|bảng\s+tính|xlsx)(?:\s+(?:của|cho|về))?(?:\s+(?P<run>.+))?$',
        r'^(?:tải|xuất)\s+(?:về\s+)?(?P<run>(?=.*\blương\b).+?)\s+(?:ra|sang|thành|về|dạng)\s+excel$',
        r'^(?:tải|xuất)\s+(?:về\s+)?(?P<run>.*\b(?:bảng|đợt|kỳ)\s+lương\b.*)$',
    ),
    'run_payroll': (
        # FIX-1 (P4 vi-12, second pass): the month needs a space of its
        # own, so "chạy lương cho Bán lẻ" leaves "cho" to the scheme.
        r'^(?:chạy|tính|làm|xử\s+lý|lập|tạo)\s+(?:(?:bảng|đợt|kỳ)\s+)?lương(?:\s+mới)?\b'
        r'(?:\s+(?P<period>.+?))??(?:\s*,?\s+(?:cho|của)\s+(?P<scheme>.+))?$',
    ),
    'submit_run': (
        r'^(?:gửi|trình|nộp|chuyển)\s+(?:đi\s+)?(?:duyệt|phê\s+duyệt)\s+(?P<run>.+)$',
        # FIX-1 (P4 vi-8): "… cho chị Hoa duyệt", "… sang trạng thái chờ
        # duyệt": who is asked and the state's name are not the run.
        # Second pass: a full name ("cho anh Nguyễn Văn Hoa") or a role
        # ("lên sếp", "để trưởng phòng") is up to six words.
        r'^(?:gửi|trình|nộp|chuyển)\s+(?P<run>.+?)\s+(?:đi\s+|'
        r'(?:cho|lên|để|nhờ|tới|đến)\s+(?:\S+\s+){0,6}?|sang\s+(?:trạng\s+thái\s+)?)?(?:chờ\s+)?'
        r'(?:duyệt|phê\s+duyệt)$',
    ),
    'send_payslips': (
        r'^(?:gửi|phát|email|chuyển)\s+(?:(?:các|những)\s+)?phiếu\s+lương\b'
        r'(?:\s+(?:của|cho))?\s*(?P<run>.*)$',
    ),
    'update_pay_data': (
        # "đổi phụ cấp ăn trưa của Vũ Khánh Chi thành 500.000 từ tháng 11"
        # Third pass: "đổi … thành N" says the new value outright, so only a
        # "thêm / bớt" right before the amount makes it a change BY — a pay
        # item called "thưởng thêm" (extra bonus) keeps its name.
        r'^' + _NOT_A_DELTA_SET + r'(?:đổi|thay\s+đổi|sửa|cập\s+nhật|đặt|chỉnh)\s+(?P<field>.+?)'
        r'\s+(?:của|cho)\s+'
        r'(?P<person>.+?)\s+(?:thành|là|lên|xuống|=|bằng|sang)\s+' + _VAL + _FROM,
        # "cho Linh phụ cấp 500.000 từ tháng 7" (give Linh … of 500.000)
        # Third pass: "cho tôi xem / biết …" (show / tell me) is never a person.
        r'^' + _NOT_A_DELTA + r'cho\s+(?!(?:tôi|mình|em)\s+(?:xem|coi|biết|hỏi)(?!\w))'
        r'(?P<person>.+?)\s+(?P<field>' + _PAY_WORDS +
        r'[^0-9₫$]*?)\s+(?:là\s+|thành\s+|=\s*|lên\s+|xuống\s+)?' + _VAL + _FROM,
        # "tăng (cho) Linh phụ cấp lên 500.000": raise TO — the link word is
        # required; "tăng … 500.000" with none is a raise BY (FIX-1 vi-7).
        r'^' + _NOT_A_DELTA + r'(?:tăng|nâng)\s+(?:cho\s+)?(?P<person>.+?)\s+(?P<field>' +
        _PAY_WORDS + r'[^0-9₫$]*?)\s+(?:lên|thành|là|=)\s*' + _VAL + _FROM,
        r'^' + _NOT_A_DELTA + r'(?:giảm|hạ)\s+(?:cho\s+)?(?P<person>.+?)\s+(?P<field>' +
        _PAY_WORDS + r'[^0-9₫$]*?)\s+(?:xuống|còn|thành|là|=)\s*' + _VAL + _FROM,
        r'^' + _NOT_A_DELTA + r'(?:tăng|giảm|nâng|hạ)\s+(?P<field>' + _PAY_WORDS +
        r'[^0-9₫$]*?)\s+(?:của|cho)\s+'
        r'(?P<person>.+?)\s+(?:lên|xuống|thành|còn)\s+' + _VAL + _FROM,
    ),
    'filing_prepare': (
        r'^(?:chuẩn\s+bị|lập|tạo|làm|soạn|nộp)\s+(?P<filing>(?:tờ\s+khai|(?:báo\s+cáo|hồ\s+sơ)'
        r'\s+(?=thuế|bảo\s+hiểm|bhxh|bhyt|tncn))\b.*?)(?:\s+(?:cho\s+|của\s+)?'
        r'(?P<period>(?:tháng|t\d)\b.*))?$',
    ),
    # FIX-1 (P4 vi-8): the verb alone ("duyệt đi", "duyệt giúp tôi") decides
    # what is waiting for the person, as "approve it" does — the item is
    # left to the inbox, never a polite word.
    'approve_item': (
        # Second pass: the item is tried LAST ("??"), so "… vì sai số"
        # with no item is a reason, never the item.
        r'^(?:phê\s+duyệt|duyệt|chấp\s+thuận)' + _DECIDE_FILLER +
        r'(?:\s+(?P<item>.+?))??' + REASON_TAIL,
    ),
    'send_back_item': (
        # Fifth pass: what follows "trả lại" is the item as at HEAD (any
        # words: "trả lại lương tháng 6", "trả lại cho Mai"); only a refund
        # ("trả lại tiền thừa …") is not a send-back. `_ITEM_WORDS` guards
        # the "trả X lại/về" shape below, where X may be "lời" / "lương".
        r'^(?:trả\s+lại|trả\s+về|gửi\s+trả(?:\s+lại)?)(?!\s+tiền(?!\w))' + _DECIDE_FILLER +
        r'(?:\s+(?P<item>.+?))??' + REASON_TAIL,
        r'^trả\s+' + _ITEM_WORDS + r'(?P<item>.+?)\s+(?:lại|về)(?:\s+cho\s+\S+(?:\s+\S+)?)?' +
        REASON_TAIL,
    ),
    'reject_item': (
        r'^(?:từ\s+chối|bác\s+bỏ)' + _DECIDE_FILLER + r'(?:\s+(?:phê\s+)?duyệt)?' +
        r'(?:\s+(?P<item>.+?))??' + REASON_TAIL,
        # "bác" alone folds to "bac" (Bắc Ninh, Bạc Liêu, bác sĩ): the
        # request's own word must follow it (second pass), and a marked
        # "Bắc" / "Bạc" is never read as it (`registry._FOLD_TWINS`). Third
        # pass: folded again, so "bac bang luong thang 6" typed with no
        # marks is still a turn-down.
        r'^bác\s+' + _ITEM_START + r'(?P<item>.+?)' + REASON_TAIL,
    ),
    'never_destructive': (
        r'^(?=.*\b(?:lương|phiếu|hồ\s+sơ|nhân\s+viên|hợp\s+đồng)\b)(?:xoá|xóa|huỷ|hủy|gỡ\s+bỏ)\s+'
        r'(?:bỏ\s+)?(?:hết\s+|tất\s+cả\s+)?(?P<what>.+)$',
        # "gỡ" alone folds to the English "go" ("go to bảng lương"): marks only.
        MARKED_ONLY + r'^(?=.*\b(?:lương|phiếu|hồ\s+sơ|nhân\s+viên|hợp\s+đồng)\b)gỡ\s+'
        r'(?:hết\s+|tất\s+cả\s+)?(?P<what>.+)$',
    ),
}
