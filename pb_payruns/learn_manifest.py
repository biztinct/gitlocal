# -*- coding: utf-8 -*-
"""LEARNREV P1 — screen manifest for Pay Run › Runs (the pay run board).

Read by pb_learn's guide; never imported by this module. Plain data only.
Labels, help texts and choice labels come from the fields (`fields_get()`);
what is written here is purpose, how a value is filled, who reads it
(file:function, checked by the truth gate) and what changing it does — every
sentence in English and Vietnamese. "Right now" is
`pb.payruns.learn_right_now` (models/pb_payruns_learn.py).
"""

_BOARD = 'pb_payruns/static/src/xml/payruns.xml'
_BOARD_JS = 'pb_payruns/static/src/js/payruns.js'

_RECOMPUTE = {
    'en': "Read-only. It changes when the payslips change: recompute the run "
          "after fixing the scheme.",
    'vi': "Chỉ xem. Nó thay đổi khi phiếu lương thay đổi: hãy tính lại đợt lương "
          "sau khi sửa chương trình lương.",
}

MANIFESTS = {
    'payruns': {
        'model': 'hr.payslip.run',
        'templates': [_BOARD, _BOARD_JS],
        'purpose': {
            'en': "Every pay run on one board, from draft to done, and who each "
                  "waiting run is with.",
            'vi': "Mọi đợt lương trên một bảng, từ nháp đến hoàn tất, và mỗi đợt đang "
                  "chờ ở chỗ ai.",
        },
        'path': {'tag': 'pb_pay_hub', 'lens': 'runs'},
        'before': [
            {'screen': 'runpayroll',
             'why': {'en': "A run appears here as a draft once it is computed.",
                     'vi': "Một đợt lương xuất hiện ở đây dưới dạng nháp khi đã được "
                           "tính."}},
        ],
        'after': [
            {'screen': 'approvals',
             'why': {'en': "Approvers decide a submitted run in the one inbox.",
                     'vi': "Người phê duyệt quyết định đợt lương đã gửi trong hộp phê "
                           "duyệt duy nhất."}},
            {'screen': 'treatment',
             'why': {'en': "When a run's figures don't add up, the fix is in its "
                           "scheme's Component treatment.",
                     'vi': "Khi số liệu của một đợt lương không khớp, cách sửa nằm ở "
                           "Xử lý thành phần của chương trình lương đó."}},
        ],
        'fields': [
            {
                'key': 'stage', 'derived': True,
                'column': {'en': "Where it is", 'vi': "Đang ở đâu"},
                'from': 'pb_payruns/models/hr_payslip_run.py:PB_STATES',
                'values': {
                    'draft': {'en': "Draft", 'vi': "Nháp"},
                    'approval_pending': {'en': "Waiting for approval",
                                         'vi': "Đang chờ phê duyệt"},
                    'done': {'en': "Done", 'vi': "Hoàn tất"},
                    'cancel': {'en': "Rejected", 'vi': "Đã từ chối"},
                },
                'how': {
                    'en': "A run is a draft once it is computed, waits for approval "
                          "once it is submitted, and is done when the last approver "
                          "signs it off. A rejected run leaves the board and is listed "
                          "under it.",
                    'vi': "Một đợt lương là bản nháp khi đã được tính, chờ phê duyệt khi "
                          "đã được gửi, và hoàn tất khi người phê duyệt cuối cùng đồng ý. "
                          "Đợt bị từ chối rời khỏi bảng và được liệt kê bên dưới.",
                },
                'used_by': [
                    {'label': {'en': "Where this month's payroll is, on Home",
                               'vi': "Kỳ lương tháng này đang ở đâu, trên Trang chủ"},
                     'ref': 'pb_dashboard/models/home_data.py:_home_runs',
                     'via': 'hr.payslip.run.state'},
                    {'label': {'en': "Whether a run may be paid",
                               'vi': "Một đợt lương có được chi trả hay không"},
                     'ref': 'pb_pay_delivery/models/approval_common.py:run_is_approved',
                     'via': 'hr.payslip.run.state'},
                ],
                'if_changed': {
                    'en': "Moves with Submit for approval, the approvers' decisions and "
                          "Reject run, never by editing the run.",
                    'vi': "Thay đổi khi bấm Gửi để phê duyệt, khi người phê duyệt quyết "
                          "định và khi Từ chối đợt lương, không bao giờ bằng cách sửa "
                          "đợt lương.",
                },
                'anchor': 'pk-steps',
            },
            {
                'key': 'net', 'field': 'pb_total_net',
                'column': {'en': "Net pay", 'vi': "Thực nhận"},
                'filled_by': {
                    'en': "Added up from the payslips' net pay lines, by pay role, "
                          "every time a payslip changes.",
                    'vi': "Được cộng từ các dòng lương thực nhận của phiếu lương, theo "
                          "vai trò trong lương, mỗi khi một phiếu lương thay đổi.",
                },
                'used_by': [
                    {'label': {'en': "The figures on Home",
                               'vi': "Các số liệu trên Trang chủ"},
                     'ref': 'pb_dashboard/models/home_data.py:_home_money'},
                    {'label': {'en': "Pay Run › Results",
                               'vi': "Đợt lương › Kết quả"},
                     'ref': 'pb_payrun_results/models/payrun_results.py:_run_card'},
                    {'label': {'en': "Analytics Explorer", 'vi': "Khám phá dữ liệu"},
                     'ref': 'pb_explorer/models/pb_fact_builder.py:_build_chunk'},
                    {'label': {'en': "Insights", 'vi': "Phân tích"},
                     'ref': 'pb_insights/models/pb_insights.py:_run_point'},
                ],
                'if_changed': _RECOMPUTE,
                'anchor': 'pk-card',
            },
            {
                'key': 'gross', 'field': 'pb_total_gross',
                'column': {'en': "Gross", 'vi': "Tổng thu nhập"},
                'filled_by': {
                    'en': "Added up from the payslips' lines that add to net pay, "
                          "counting a total once and not its parts.",
                    'vi': "Được cộng từ các dòng cộng vào thực nhận của phiếu lương, "
                          "tính một khoản tổng một lần chứ không tính các phần của nó.",
                },
                'used_by': [
                    {'label': {'en': "The \"Figures don't add up\" check",
                               'vi': "Kiểm tra \"Số liệu không khớp\""},
                     'ref': 'pb_payruns/models/hr_payslip_run.py:_pb_set_balance'},
                    {'label': {'en': "Insights", 'vi': "Phân tích"},
                     'ref': 'pb_insights/models/pb_insights.py:_run_point'},
                ],
                'if_changed': _RECOMPUTE,
                'anchor': 'pk-card',
            },
            {
                'key': 'people', 'field': 'pb_employee_count',
                'column': {'en': "People", 'vi': "Nhân sự"},
                'filled_by': {
                    'en': "The number of payslips in the run that are not rejected.",
                    'vi': "Số phiếu lương trong đợt không bị từ chối.",
                },
                'used_by': [
                    {'label': {'en': "Pay Run › Results",
                               'vi': "Đợt lương › Kết quả"},
                     'ref': 'pb_payrun_results/models/payrun_results.py:_run_card'},
                    {'label': {'en': "The rounding allowance of the balance check",
                               'vi': "Mức dung sai làm tròn của kiểm tra số liệu"},
                     'ref': 'pb_payruns/models/hr_payslip_run.py:_pb_set_balance'},
                ],
                'if_changed': _RECOMPUTE,
                'anchor': 'pk-card',
            },
            {
                'key': 'balance', 'field': 'pb_balance_ok',
                'column': {'en': "Figures don't add up", 'vi': "Số liệu không khớp"},
                'filled_by': {
                    'en': "Checked every time the totals are added up: gross minus "
                          "deductions minus net pay should come to nothing, allowing "
                          "for rounding.",
                    'vi': "Được kiểm tra mỗi lần cộng tổng: tổng thu nhập trừ khấu trừ "
                          "trừ thực nhận phải bằng không, có tính đến làm tròn.",
                },
                'used_by': [
                    {'label': {'en': "The figures on Home",
                               'vi': "Các số liệu trên Trang chủ"},
                     'ref': 'pb_dashboard/models/home_data.py:_home_money'},
                    {'label': {'en': "The run's card on this board",
                               'vi': "Thẻ của đợt lương trên bảng này"},
                     'ref': 'pb_payruns/models/pb_payruns.py:get_board_data'},
                ],
                'if_changed': {
                    'en': "Read-only. Put the components counted under the wrong heading "
                          "right in Mapping › Component treatment, then recompute the run.",
                    'vi': "Chỉ xem. Hãy sửa các thành phần bị tính sai mục ở Ánh xạ › Xử "
                          "lý thành phần, rồi tính lại đợt lương.",
                },
                'anchor': 'pk-card',
            },
            {
                'key': 'unsourced', 'field': 'pb_unsourced_count',
                'column': {'en': "payslips have no source data",
                           'vi': "phiếu lương không có dữ liệu nguồn"},
                'filled_by': {
                    'en': "Counted when the totals are added up: payslips computed by a "
                          "scheme that found none of their input values, so their "
                          "figures are the scheme's defaults.",
                    'vi': "Được đếm khi cộng tổng: các phiếu lương được tính theo chương "
                          "trình lương mà không tìm thấy giá trị đầu vào nào, nên số liệu "
                          "là giá trị mặc định của chương trình.",
                },
                'used_by': [
                    {'label': {'en': "The figures on Home",
                               'vi': "Các số liệu trên Trang chủ"},
                     'ref': 'pb_dashboard/models/home_data.py:_home_money'},
                    {'label': {'en': "The run's card on this board",
                               'vi': "Thẻ của đợt lương trên bảng này"},
                     'ref': 'pb_payruns/models/pb_payruns.py:get_board_data'},
                ],
                'if_changed': {
                    'en': "Read-only. Check the import, or Mapping › Connections, then "
                          "recompute the run.",
                    'vi': "Chỉ xem. Hãy kiểm tra dữ liệu nhập, hoặc Ánh xạ › Liên kết, "
                          "rồi tính lại đợt lương.",
                },
                'anchor': 'pk-card',
            },
            {
                'key': 'waiting_on_you', 'derived': True,
                'column': {'en': "Waiting on you", 'vi': "Đang chờ bạn"},
                'from': 'pb_payruns/models/hr_payslip_run.py:_pb_runs_awaiting',
                'how': {
                    'en': "The run is at an approval step that names you, or someone "
                          "you are standing in for.",
                    'vi': "Đợt lương đang ở một bước phê duyệt có tên bạn, hoặc tên "
                          "người mà bạn đang làm thay.",
                },
                'if_changed': {
                    'en': "Read-only. Decide the run in Approvals and it moves on.",
                    'vi': "Chỉ xem. Hãy quyết định đợt lương ở Phê duyệt và nó sẽ đi "
                          "tiếp.",
                },
                'anchor': 'pk-route',
            },
        ],
        'actions': [
            {'label': {'en': "Submit for approval", 'vi': "Gửi để phê duyệt"},
             'method': 'hr.payslip.run.action_approval_submit',
             'effect': {'en': "Sends the draft run along its approval route, with its "
                              "figures frozen as they are now.",
                        'vi': "Gửi đợt lương nháp đi theo lộ trình phê duyệt, với số "
                              "liệu được giữ nguyên như hiện tại."},
             'writes': True},
            {'label': {'en': "Reject run", 'vi': "Từ chối đợt lương"},
             'method': 'hr.payslip.run.action_payslip_run_cancel',
             'effect': {'en': "Rejects the run for good, with the reason you give. It "
                              "is kept under the board.",
                        'vi': "Từ chối hẳn đợt lương, kèm lý do bạn đưa ra. Nó được giữ "
                              "lại bên dưới bảng."},
             'writes': True},
            {'label': {'en': "Pay & Deliver", 'vi': "Chi trả & gửi phiếu"},
             'method': 'hr.payslip.run.action_pb_pay_deliver',
             'effect': {'en': "Opens the bank file, payment and payslip sending steps "
                              "for an approved run.",
                        'vi': "Mở các bước tệp ngân hàng, thanh toán và gửi phiếu lương "
                              "cho một đợt lương đã được phê duyệt."},
             'writes': False},
        ],
        'right_now': 'pb.payruns.learn_right_now',
        'station': 'payruns',
        'tasks': ['sc_payslips'],
        'terms': ['payrun', 'draft', 'approvalRoute', 'sentBack', 'reconcile', 'needsYou'],
    },
}
