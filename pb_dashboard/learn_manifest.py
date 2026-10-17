# -*- coding: utf-8 -*-
"""LEARNREV P1 — screen manifest for Home › Pulse (the home dashboard).

Read by pb_learn's guide; never imported by this module. Plain data only.
Pulse draws figures, not fields: one of them is a stored pay run total
(`hr.payslip.run.pb_total_net`, labelled by its field), the rest are worked out
per call in `home_data.py` and are declared `derived` from the function that
computes them, checked by the truth gate. Every sentence in English and
Vietnamese.
"""

_HOME = 'pb_dashboard/static/src/xml/pb_dashboard.xml'
_HOME_JS = 'pb_dashboard/static/src/js/pb_dashboard.js'
_DATA = 'pb_dashboard/models/home_data.py'

_READ_ONLY = {
    'en': "Read-only. It follows the pay runs: change a run, and this changes "
          "with it.",
    'vi': "Chỉ xem. Nó đi theo các đợt lương: một đợt lương thay đổi thì số này "
          "thay đổi theo.",
}

MANIFESTS = {
    'dashboard': {
        'model': 'hr.payslip.run',
        'templates': [_HOME, _HOME_JS],
        'purpose': {
            'en': "See where this month's payroll is, what is waiting for you, and "
                  "twelve months of figures that match the payslips.",
            'vi': "Xem kỳ lương tháng này đang ở đâu, việc gì đang chờ bạn, và số liệu "
                  "mười hai tháng khớp với phiếu lương.",
        },
        'path': {'tag': 'pb_home_hub', 'lens': 'pulse'},
        'after': [
            {'screen': 'runpayroll',
             'why': {'en': "The one solid button opens the pay run that needs you next.",
                     'vi': "Nút đặc màu duy nhất mở đợt lương cần bạn tiếp theo."}},
            {'screen': 'approvals',
             'why': {'en': "Approvals waiting for you are decided in the one inbox.",
                     'vi': "Các phê duyệt đang chờ bạn được quyết định trong hộp phê "
                           "duyệt duy nhất."}},
        ],
        'fields': [
            {
                'key': 'net_pay', 'field': 'pb_total_net',
                'column': {'en': "Net pay", 'vi': "Lương thực nhận"},
                'filled_by': {
                    'en': "Added up from the month's pay runs that are not rejected, in "
                          "the company's own currency only; a run in another currency "
                          "is left out and named.",
                    'vi': "Được cộng từ các đợt lương của tháng không bị từ chối, chỉ "
                          "theo loại tiền của công ty; đợt lương bằng loại tiền khác "
                          "được để riêng và nêu tên.",
                },
                'used_by': [
                    {'label': {'en': "The month's figures on Home",
                               'vi': "Số liệu của tháng trên Trang chủ"},
                     'ref': _DATA + ':_home_money'},
                    {'label': {'en': "Insights", 'vi': "Phân tích"},
                     'ref': 'pb_insights/models/pb_insights.py:_hero'},
                ],
                'if_changed': _READ_ONLY,
                'anchor': 'dash-kpis',
            },
            {
                'key': 'people_paid', 'derived': True,
                'column': {'en': "People paid", 'vi': "Số người được trả lương"},
                'from': _DATA + ':_home_month_people',
                'how': {
                    'en': "Everyone with a payslip in the month's pay runs, each person "
                          "counted once.",
                    'vi': "Mọi người có phiếu lương trong các đợt lương của tháng, mỗi "
                          "người chỉ được đếm một lần.",
                },
                'if_changed': _READ_ONLY,
                'anchor': 'dash-kpis',
            },
            {
                'key': 'average_net', 'derived': True,
                'column': {'en': "Average net per person",
                           'vi': "Thực nhận bình quân mỗi người"},
                'from': _DATA + ':_home_months',
                'how': {
                    'en': "Net pay divided by people paid, for the month chosen on the "
                          "chart.",
                    'vi': "Lương thực nhận chia cho số người được trả lương, cho tháng "
                          "được chọn trên biểu đồ.",
                },
                'if_changed': _READ_ONLY,
                'anchor': 'dash-kpis',
            },
            {
                'key': 'total_cost', 'derived': True,
                'column': {'en': "Total cost to the company",
                           'vi': "Tổng chi phí của công ty"},
                'from': _DATA + ':_home_months',
                'how': {
                    'en': "Gross pay plus the employer's cost, such as the company's "
                          "insurance share: what the month costs the company.",
                    'vi': "Tổng thu nhập cộng chi phí doanh nghiệp, như phần bảo hiểm "
                          "công ty đóng: tháng đó tốn của công ty bao nhiêu.",
                },
                'if_changed': _READ_ONLY,
                'anchor': 'dash-kpis',
            },
            {
                'key': 'month_chart', 'derived': True,
                'column': {'en': "Payroll, month by month",
                           'vi': "Lương, theo từng tháng"},
                'from': _DATA + ':_home_months',
                'how': {
                    'en': "The last 12 months of pay runs, filed under the month each "
                          "run ends in. Click a month, or use the arrow keys, to read "
                          "its figures below.",
                    'vi': "Các đợt lương của 12 tháng gần nhất, xếp theo tháng mà mỗi "
                          "đợt kết thúc. Bấm vào một tháng, hoặc dùng phím mũi tên, để "
                          "xem số liệu của tháng đó bên dưới.",
                },
                'if_changed': _READ_ONLY,
                'anchor': 'dash-period',
            },
            {
                'key': 'needs_you', 'derived': True,
                'column': {'en': "Needs you", 'vi': "Cần bạn"},
                'from': _DATA + ':NEEDS_ORDER',
                'values': {
                    'runs_to_approve': {'en': "Pay runs to approve",
                                        'vi': "Đợt lương cần phê duyệt"},
                    'leave_to_approve': {'en': "Leave requests to approve",
                                         'vi': "Đơn nghỉ phép cần phê duyệt"},
                    'other_to_approve': {'en': "Other approvals",
                                         'vi': "Các phê duyệt khác"},
                    'settlements_to_check': {'en': "Final settlements to check",
                                             'vi': "Quyết toán nghỉ việc cần kiểm tra"},
                    'renewals_to_start': {'en': "Contract renewals to start",
                                          'vi': "Gia hạn hợp đồng cần bắt đầu"},
                    'writeups_overdue': {'en': "Interview write-ups overdue",
                                         'vi': "Nhận xét phỏng vấn quá hạn"},
                },
                'how': {
                    'en': "One chip for each kind of thing waiting for you, in the order "
                          "to do them. A chip shows only when its count is above zero.",
                    'vi': "Mỗi loại việc đang chờ bạn là một nhãn, theo thứ tự nên làm. "
                          "Nhãn chỉ hiện khi có ít nhất một việc.",
                },
                'if_changed': {
                    'en': "Read-only. Press a chip to open the place where it is done.",
                    'vi': "Chỉ xem. Bấm vào một nhãn để mở nơi xử lý việc đó.",
                },
                'anchor': 'dash-hero',
            },
            {
                'key': 'pay_schemes', 'derived': True,
                'column': {'en': "Pay schemes", 'vi': "Chương trình lương"},
                'from': _DATA + ':_home_schemes',
                'how': {
                    'en': "The schemes in use, how many components they hold, and "
                          "whether every test passed on their last check.",
                    'vi': "Các chương trình lương đang dùng, chúng có bao nhiêu thành "
                          "phần, và mọi bài kiểm tra có đạt ở lần kiểm tra gần nhất "
                          "không.",
                },
                'if_changed': {
                    'en': "Read-only. Open Formula Studio to change a scheme.",
                    'vi': "Chỉ xem. Hãy mở Xưởng công thức để thay đổi một chương trình "
                          "lương.",
                },
                'anchor': 'dash-formula',
            },
        ],
        'actions': [],
        'right_now': None,
        'station': 'dashboard',
        'tasks': ['sc_welcome'],
        'terms': ['needsYou', 'payrun', 'net', 'headcount'],
    },
}
