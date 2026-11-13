# -*- coding: utf-8 -*-
"""LEARNREV P1 — screen manifest for Pay Run › Run (the pay run wizard).

Read by pb_learn's guide; never imported by this module. Plain data only.
Labels, help texts and choice labels come from the fields themselves
(`fields_get()`); what is written here is what the code cannot say: purpose,
how a value is filled, who reads it (file:function, checked by the truth gate)
and what changing it does — every sentence in English and Vietnamese.
"""

_WZ = 'pb_payrun_wizard/static/src/xml/payrun_wizard.xml'
_WZ_JS = 'pb_payrun_wizard/static/src/js/payrun_wizard.js'

MANIFESTS = {
    'runpayroll': {
        'model': 'hr.payslip.run',
        'templates': [_WZ, _WZ_JS],
        'purpose': {
            'en': "Start one month's pay run: pick the pay scheme, add the month's "
                  "pay data, compute the payslips and read what needs a look.",
            'vi': "Bắt đầu đợt lương của một tháng: chọn chương trình lương, thêm dữ "
                  "liệu lương của tháng, tính phiếu lương và đọc những gì cần xem lại.",
        },
        'path': {'tag': 'pb_pay_hub', 'lens': 'run'},
        'before': [
            {'screen': 'mapping',
             'why': {'en': "Every input the scheme reads is connected there.",
                     'vi': "Mọi đầu vào mà chương trình lương đọc được nối ở đó."}},
        ],
        'after': [
            {'screen': 'payslips',
             'why': {'en': "Read the payslips before you send the run for approval.",
                     'vi': "Đọc các phiếu lương trước khi gửi đợt lương đi phê duyệt."}},
            {'screen': 'payruns',
             'why': {'en': "The run then waits on the Runs board as a draft.",
                     'vi': "Sau đó đợt lương nằm trên bảng Các đợt lương ở dạng nháp."}},
        ],
        'fields': [
            {
                'key': 'scheme', 'field': 'pb_formula_config_id',
                'column': {'en': "Payroll scheme", 'vi': "Chương trình lương"},
                'filled_by': {
                    'en': "You pick it on the first step; with only one scheme it is "
                          "picked for you. It decides who is paid, by which rulebook "
                          "and in which currency.",
                    'vi': "Bạn chọn ở bước đầu tiên; nếu chỉ có một chương trình lương "
                          "thì hệ thống chọn sẵn. Nó quyết định ai được trả lương, theo "
                          "bộ quy tắc nào và bằng loại tiền nào.",
                },
                'used_by': [
                    {'label': {'en': "The rulebook each payslip is computed by",
                               'vi': "Bộ quy tắc dùng để tính mỗi phiếu lương"},
                     'ref': 'pb_hr_payroll_formula/models/hr_payslip_formula.py:'
                            '_find_formula_config'},
                    {'label': {'en': "The currency the run is priced in",
                               'vi': "Loại tiền dùng cho đợt lương"},
                     'ref': 'pb_payruns/models/hr_payslip_run.py:_pb_scheme_currency'},
                    {'label': {'en': "The division named on Home",
                               'vi': "Bộ phận được nêu trên Trang chủ"},
                     'ref': 'pb_dashboard/models/home_data.py:_home_division'},
                    {'label': {'en': "Analytics Explorer", 'vi': "Khám phá dữ liệu"},
                     'ref': 'pb_explorer/models/pb_fact_builder.py:_coverage'},
                ],
                'if_changed': {
                    'en': "Only a new run can use another scheme: a computed run keeps "
                          "the scheme it was computed with.",
                    'vi': "Chỉ một đợt lương mới mới dùng được chương trình khác: đợt "
                          "đã tính giữ chương trình lương mà nó đã được tính theo.",
                },
                'anchor': 'pw-scheme',
            },
            {
                'key': 'batch_name', 'field': 'name',
                'column': {'en': "Batch name", 'vi': "Tên đợt"},
                'filled_by': {
                    'en': "Filled in from the scheme and the month. You can change it "
                          "before you compute.",
                    'vi': "Được điền sẵn theo chương trình lương và tháng. Bạn có thể "
                          "đổi trước khi tính.",
                },
                'used_by': [
                    {'label': {'en': "The run's card on the Runs board",
                               'vi': "Thẻ của đợt lương trên bảng Các đợt lương"},
                     'ref': 'pb_payruns/models/pb_payruns.py:get_board_data'},
                ],
                'if_changed': {
                    'en': "Only the name people read changes; nothing is recomputed.",
                    'vi': "Chỉ tên mọi người đọc thay đổi; không có gì được tính lại.",
                },
                'anchor': 'pw-scope',
            },
            {
                'key': 'date_from', 'field': 'date_start',
                'column': {'en': "From", 'vi': "Từ"},
                'filled_by': {
                    'en': "The first day of the month, or of the scheme's own cycle.",
                    'vi': "Ngày đầu tiên của tháng, hoặc của chu kỳ riêng của chương "
                          "trình lương.",
                },
                'used_by': [
                    {'label': {'en': "The days every payslip in the run covers",
                               'vi': "Những ngày mà mọi phiếu lương trong đợt bao gồm"},
                     'ref': 'pb_payrun_wizard/models/pb_payrun_wizard.py:prepare_run'},
                    {'label': {'en': "The period on the Runs board",
                               'vi': "Kỳ lương trên bảng Các đợt lương"},
                     'ref': 'pb_payruns/models/pb_payruns.py:get_board_data'},
                ],
                'if_changed': {
                    'en': "Changes which days the payslips cover. Set it before you "
                          "compute: a computed run keeps its dates.",
                    'vi': "Thay đổi những ngày mà phiếu lương bao gồm. Hãy đặt trước "
                          "khi tính: đợt lương đã tính giữ nguyên ngày của nó.",
                },
                'anchor': 'pw-scope',
            },
            {
                'key': 'date_to', 'field': 'date_end',
                'column': {'en': "To", 'vi': "Đến"},
                'filled_by': {
                    'en': "The last day of the month, or of the scheme's own cycle. "
                          "It names the month the run belongs to.",
                    'vi': "Ngày cuối cùng của tháng, hoặc của chu kỳ riêng của chương "
                          "trình lương. Nó cho biết đợt lương thuộc về tháng nào.",
                },
                'used_by': [
                    {'label': {'en': "The month Home files the run under",
                               'vi': "Tháng mà Trang chủ xếp đợt lương vào"},
                     'ref': 'pb_dashboard/models/home_data.py:_home_months'},
                    {'label': {'en': "The month on the Runs board",
                               'vi': "Tháng trên bảng Các đợt lương"},
                     'ref': 'pb_payruns/models/pb_payruns.py:get_board_data'},
                ],
                'if_changed': {
                    'en': "Changes which days the payslips cover and which month the "
                          "run is counted in. Set it before you compute.",
                    'vi': "Thay đổi những ngày mà phiếu lương bao gồm và tháng mà đợt "
                          "lương được tính vào. Hãy đặt trước khi tính.",
                },
                'anchor': 'pw-scope',
            },
            {
                'key': 'pay_data_mode', 'derived': True,
                'column': {'en': "What should these values do?",
                           'vi': "Các giá trị này dùng để làm gì?"},
                'from': 'pb_payrun_wizard/static/src/js/payrun_wizard.js:SHEET_MODES',
                'values': {
                    'update': {'en': "Update Payobook", 'vi': "Cập nhật Payobook"},
                    'once': {'en': "This run only", 'vi': "Chỉ đợt này"},
                },
                'how': {
                    'en': "Asked when the scheme reads a spreadsheet. Update Payobook "
                          "also saves the values to employee and contract records; This "
                          "run only uses them for this run and saves nothing else.",
                    'vi': "Được hỏi khi chương trình lương đọc một bảng tính. Cập nhật "
                          "Payobook còn lưu các giá trị vào hồ sơ nhân viên và hợp đồng; "
                          "Chỉ đợt này chỉ dùng chúng cho đợt lương này và không lưu gì "
                          "khác.",
                },
                'used_by': [
                    {'label': {'en': "Whether the file also updates records",
                               'vi': "Tệp có cập nhật cả hồ sơ hay không"},
                     'ref': 'pb_payrun_wizard/models/pb_payrun_wizard.py:attach_spreadsheet',
                     'via': 'hr.payroll.import.batch.one_time'},
                ],
                'if_changed': {
                    'en': "Decided when you continue with the file. To change it, add "
                          "the file again.",
                    'vi': "Được quyết định khi bạn tiếp tục với tệp. Muốn đổi, hãy thêm "
                          "lại tệp.",
                },
                'anchor': 'pw-paymode',
            },
            {
                'key': 'coverage', 'derived': True,
                'column': {'en': "Coverage", 'vi': "Mức bao phủ"},
                'from': 'pb_payrun_wizard/models/pb_payrun_wizard.py:preflight_spreadsheet',
                'how': {
                    'en': "How many of the people in this run the spreadsheet covers. "
                          "The people it misses are named, with the door that adds them.",
                    'vi': "Bảng tính bao phủ bao nhiêu người trong đợt lương này. Những "
                          "người bị thiếu được nêu tên, kèm lối để thêm họ.",
                },
                'if_changed': {
                    'en': "Read-only. Add the missing people to the file, or run "
                          "without them on purpose.",
                    'vi': "Chỉ xem. Hãy thêm những người còn thiếu vào tệp, hoặc chủ "
                          "động chạy lương không có họ.",
                },
                'anchor': 'pw-coverage',
            },
            {
                'key': 'need_review', 'derived': True,
                'column': {'en': "Need review", 'vi': "Cần xem xét"},
                'from': 'pb_payslip_review/models/review_flags.py:pb_review_flags',
                'how': {
                    'en': "A payslip is flagged when take-home pay is zero or below, or "
                          "moved more than the set share (30% unless changed) against "
                          "the person's last payslip on the same scheme. A flag is a "
                          "question, not an error.",
                    'vi': "Một phiếu lương bị gắn cờ khi thực nhận bằng không hoặc âm, "
                          "hoặc thay đổi quá mức đã đặt (30% nếu chưa đổi) so với phiếu "
                          "lương trước của người đó trong cùng chương trình lương. Cờ là "
                          "một câu hỏi, không phải một lỗi.",
                },
                'if_changed': {
                    'en': "Read-only. The share is set in the payroll settings.",
                    'vi': "Chỉ xem. Mức thay đổi được đặt trong cài đặt bảng lương.",
                },
                'anchor': 'pw-pills',
            },
        ],
        'actions': [
            {'label': {'en': "Compute payslips", 'vi': "Tính toán phiếu lương"},
             'method': 'pb.payrun.wizard.compute_batch',
             'effect': {'en': "Creates draft payslips only: nothing is paid, sent or "
                              "approved.",
                        'vi': "Chỉ tạo phiếu lương nháp: chưa có gì được chi, gửi hay "
                              "phê duyệt."},
             'writes': True},
            # LEARNING L6 (2026-10-22): "Update records" left the Pay Run screen
            # (163f75c60 — master-record sync stays outside Pay Run), so the
            # Guide no longer names it (ledger rule L3: lessons follow screens).
        ],
        'right_now': None,
        'station': 'runpayroll',
        'tasks': ['sc_payrun'],
        'terms': ['payrun', 'payScheme', 'payData', 'thisRunOnly', 'period', 'draft'],
    },
}
