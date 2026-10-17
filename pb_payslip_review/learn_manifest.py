# -*- coding: utf-8 -*-
"""LEARNREV P1 — screen manifest for Pay Run › Payslips (payslip review).

Read by pb_learn's guide; never imported by this module. Plain data only.
Nothing on this screen is an editable field: the figures are worked out per
call (`pb.payslip.review`), so every entry is `derived` from the function that
computes it, checked by the truth gate. Every sentence in English and
Vietnamese.
"""

_PS = 'pb_payslip_review/static/src/xml/payslip_review.xml'
_PS_JS = 'pb_payslip_review/static/src/js/payslip_review.js'
_PY = 'pb_payslip_review/models/pb_payslip_review.py'

MANIFESTS = {
    'payslips': {
        'model': None,
        'templates': [_PS, _PS_JS],
        'purpose': {
            'en': "Read every payslip in one run before it is approved, starting with "
                  "the ones flagged for a look.",
            'vi': "Đọc mọi phiếu lương trong một đợt trước khi được phê duyệt, bắt đầu "
                  "từ những phiếu được gắn cờ cần xem.",
        },
        'path': {'tag': 'pb_pay_hub', 'lens': 'payslips'},
        'before': [
            {'screen': 'runpayroll',
             'why': {'en': "Payslips appear here once the run is computed.",
                     'vi': "Phiếu lương xuất hiện ở đây khi đợt lương đã được tính."}},
        ],
        'after': [
            {'screen': 'payruns',
             'why': {'en': "Submit the run for approval from the Runs board.",
                     'vi': "Gửi đợt lương đi phê duyệt từ bảng Các đợt lương."}},
        ],
        'fields': [
            {
                'key': 'need_review', 'derived': True,
                'column': {'en': "Need review", 'vi': "Cần xem xét"},
                'from': 'pb_payslip_review/models/review_flags.py:pb_review_flags',
                'how': {
                    'en': "A payslip is flagged when take-home pay is zero or below, or "
                          "moved more than the set share (30% unless changed) against "
                          "the person's last payslip on the same scheme. The reason is "
                          "written under the name.",
                    'vi': "Một phiếu lương bị gắn cờ khi thực nhận bằng không hoặc âm, "
                          "hoặc thay đổi quá mức đã đặt (30% nếu chưa đổi) so với phiếu "
                          "lương trước của người đó trong cùng chương trình lương. Lý do "
                          "được ghi dưới tên.",
                },
                'if_changed': {
                    'en': "Read-only. A flag is a question, not an error: read the "
                          "payslip, then sample a few ordinary ones too.",
                    'vi': "Chỉ xem. Cờ là một câu hỏi, không phải một lỗi: hãy đọc phiếu "
                          "lương đó, rồi lấy mẫu thêm vài phiếu bình thường.",
                },
                'anchor': 'ps-why',
            },
            {
                'key': 'status', 'derived': True,
                'column': {'en': "Waiting for approval", 'vi': "Đang chờ phê duyệt"},
                'from': 'pb_payslip_review/static/src/js/payslip_review.js:STATUS_FLOW',
                'values': {
                    'draft': {'en': "Draft", 'vi': "Nháp"},
                    'verify': {'en': "Waiting for approval", 'vi': "Đang chờ phê duyệt"},
                    'done': {'en': "Done", 'vi': "Hoàn tất"},
                },
                'how': {
                    'en': "Each payslip follows its run: draft when computed, waiting "
                          "once the run is submitted, done when the run is approved.",
                    'vi': "Mỗi phiếu lương đi theo đợt lương của nó: nháp khi được tính, "
                          "chờ khi đợt lương được gửi, hoàn tất khi đợt lương được phê "
                          "duyệt.",
                },
                'if_changed': {
                    'en': "Payslips are approved as a run, never one by one: submit the "
                          "run from the Runs board.",
                    'vi': "Phiếu lương được phê duyệt theo cả đợt, không bao giờ từng "
                          "phiếu: hãy gửi đợt lương từ bảng Các đợt lương.",
                },
                'anchor': 'ps-chips',
            },
            {
                'key': 'net_total', 'derived': True,
                'column': {'en': "Net total", 'vi': "Tổng thực nhận"},
                'from': _PY + ':get_review_data',
                'how': {
                    'en': "The take-home pay of the payslips in this run, added up.",
                    'vi': "Tổng thực nhận của các phiếu lương trong đợt này.",
                },
                'if_changed': {
                    'en': "Read-only. It follows the payslips.",
                    'vi': "Chỉ xem. Nó thay đổi theo các phiếu lương.",
                },
                'anchor': 'ps-kpis',
            },
            {
                'key': 'gross_total', 'derived': True,
                'column': {'en': "Gross total", 'vi': "Tổng thu nhập"},
                'from': _PY + ':_slip_totals',
                'how': {
                    'en': "The gross pay of the payslips in this run, added up.",
                    'vi': "Tổng thu nhập của các phiếu lương trong đợt này.",
                },
                'if_changed': {
                    'en': "Read-only. It follows the payslips.",
                    'vi': "Chỉ xem. Nó thay đổi theo các phiếu lương.",
                },
                'anchor': 'ps-kpis',
            },
            {
                'key': 'breakdown', 'derived': True,
                'column': {'en': "Salary breakdown", 'vi': "Chi tiết lương"},
                'from': _PY + ':get_slip_detail',
                'how': {
                    'en': "Every line of the selected payslip with its code: the "
                          "working behind its net pay.",
                    'vi': "Mọi dòng của phiếu lương đang chọn kèm mã của nó: phần tính "
                          "toán đứng sau lương thực nhận.",
                },
                'if_changed': {
                    'en': "Read-only. A wrong line is fixed in the scheme or the pay "
                          "data, then the run is recomputed.",
                    'vi': "Chỉ xem. Một dòng sai được sửa trong chương trình lương hoặc "
                          "dữ liệu lương, rồi tính lại đợt lương.",
                },
                'anchor': 'ps-breakdown',
            },
        ],
        'actions': [],
        'right_now': None,
        'station': 'payslips',
        'tasks': ['sc_payslips'],
        'terms': ['payslip', 'flag', 'net', 'gross'],
    },
}
