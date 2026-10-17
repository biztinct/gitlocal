# -*- coding: utf-8 -*-
"""LEARNREV P1 — screen manifests for the screens this module owns.

Read by pb_learn (`learn.guide`), never imported by this module itself: a
product module does not know the learning system exists. Plain data only —
no Odoo import, no model access — so the truth gate can read it anywhere.

WHAT MAY BE WRITTEN HERE, AND WHAT MAY NOT
------------------------------------------
Labels, help texts and choice labels are NEVER written here: the guide reads
them from the field (`fields_get()`), translated. A wrong label is fixed in the
field's `string=` / `help=` and its .po, not papered over in this file. What is
written here is what the code cannot say for itself: one sentence of purpose,
how a value gets filled, who reads it (`ref` = file:function, checked by the
gate), and what changing it does. Every sentence carries `en` AND `vi`.

`column` is the header exactly as the screen draws it (the gate finds it in
`templates`, and its Vietnamese in this module's .po).
"""

_TR = 'pb_formula_studio/static/src/xml/component_treatment.xml'
_TR_JS = 'pb_formula_studio/static/src/js/component_treatment.js'

# The copied field every pay-role reader goes through: the role is stamped on
# each payslip line when payslips are computed (formula engine) or imported.
_LINE_ROLE = 'hr.payslip.line.pay_role'
_LINE_DETAIL = 'hr.payslip.line.component_detail'

MANIFESTS = {
    # =================================================================
    # Mapping › Component treatment
    # =================================================================
    'treatment': {
        'model': 'hr.formula.rule',
        'templates': [_TR, _TR_JS],
        'purpose': {
            'en': "Tell the pay scheme what each component is, so every pay run, "
                  "payslip and report counts it the right way.",
            'vi': "Cho chương trình lương biết mỗi thành phần là gì, để mọi đợt "
                  "lương, phiếu lương và báo cáo đều tính nó đúng cách.",
        },
        'path': {'tag': 'pb_mapping_studio', 'lens': 'treatment'},
        'before': [
            {'screen': 'formula',
             'why': {'en': "Most answers on this board are worked out from the "
                           "scheme's formulas.",
                     'vi': "Phần lớn câu trả lời trên bảng này được suy ra từ các "
                           "công thức của chương trình lương."}},
        ],
        'after': [
            {'screen': 'runpayroll',
             'why': {'en': "Recompute the pay run so its figures use what you saved.",
                     'vi': "Tính lại đợt lương để số liệu dùng những gì bạn vừa lưu."}},
            {'screen': 'payruns',
             'why': {'en': "Each run's card says whether its figures add up.",
                     'vi': "Thẻ của mỗi đợt lương cho biết số liệu có khớp không."}},
        ],
        'fields': [
            # ---------------------------------------------- Comes from
            {
                'key': 'lane', 'derived': True,
                'column': {'en': "Comes from", 'vi': "Đến từ"},
                'from': 'pb_hr_payroll_formula/models/formula_config.py:_value_kind_lane',
                'values': {
                    'calculated': {'en': "Calculated by a formula",
                                   'vi': "Tính bằng công thức"},
                    'feed': {'en': "Connected system", 'vi': "Hệ thống được kết nối"},
                    'excel': {'en': "Spreadsheet", 'vi': "Bảng tính"},
                    'contract_component': {'en': "Contract", 'vi': "Hợp đồng"},
                    'constant': {'en': "Fixed value", 'vi': "Giá trị cố định"},
                },
                'how': {
                    'en': "Read from where the value arrives: a formula on this "
                          "scheme, a connected system, the month's spreadsheet, the "
                          "contract or a fixed value. The small grey chips beside it "
                          "are values that actually arrived.",
                    'vi': "Được đọc từ nơi giá trị đi vào: một công thức của chương "
                          "trình lương, một hệ thống được kết nối, bảng tính của "
                          "tháng, hợp đồng hoặc một giá trị cố định. Các nhãn xám nhỏ "
                          "bên cạnh là những giá trị đã thực sự đi vào.",
                },
                'if_changed': {
                    'en': "Read-only here. Change where a value comes from in "
                          "Mapping › Connections.",
                    'vi': "Chỉ xem ở đây. Hãy đổi nơi một giá trị đến từ ở "
                          "Ánh xạ › Liên kết.",
                },
                'anchor': 'tr-table',
            },
            # ---------------------------------------------- Report group
            {
                'key': 'report_group', 'field': 'component_type',
                'column': {'en': "Report group", 'vi': "Nhóm báo cáo"},
                'source_field': 'component_type_source',
                'filled_by': {
                    'en': "Filled from the pay role: Earnings, Deductions, Net pay, "
                          "Employer costs or Information. Type a group of your own "
                          "and it is kept; clear the box to go back to the "
                          "automatic one.",
                    'vi': "Được điền theo vai trò trong lương: Thu nhập, Khấu trừ, "
                          "Lương thực nhận, Chi phí doanh nghiệp hoặc Thông tin. Nếu "
                          "bạn tự gõ một nhóm, nhóm đó được giữ nguyên; xoá ô để "
                          "quay về nhóm tự động.",
                },
                'used_by': [
                    {'label': {'en': "The group shown on each payslip line",
                               'vi': "Nhóm hiện trên mỗi dòng phiếu lương"},
                     'ref': 'pb_hr_payroll_formula/models/hr_payslip_formula.py:'
                            '_create_payslip_lines_from_formulas',
                     'via': 'hr.payslip.line.component_type'},
                    {'label': {'en': "Sections of the Formula Studio grid",
                               'vi': "Các phần của lưới trong Xưởng công thức"},
                     'ref': 'pb_formula_studio/models/studio_experience.py:get_studio_data'},
                    {'label': {'en': "Groups on Mapping › Journey",
                               'vi': "Các nhóm trên Ánh xạ › Hành trình"},
                     'ref': 'pb_source_atlas/models/pb_source_atlas.py:_atlas_components'},
                ],
                'if_changed': {
                    'en': "Only how components are grouped on screens and reports "
                          "changes; no amount changes. Payslips already computed "
                          "keep the old group until you recompute the run.",
                    'vi': "Chỉ cách nhóm các thành phần trên màn hình và báo cáo thay "
                          "đổi; không số tiền nào thay đổi. Các phiếu lương đã tính "
                          "giữ nhóm cũ cho tới khi bạn tính lại đợt lương.",
                },
                'anchor': 'tr-table',
            },
            # ---------------------------------------------- Pay role
            {
                'key': 'pay_role', 'field': 'net_role',
                'column': {'en': "Pay role", 'vi': "Vai trò trong lương"},
                'source_field': 'net_role_source',
                'filled_by': {
                    'en': "Worked out from the scheme's own formulas when you press "
                          "Re-classify from the formulas. A role you choose is marked "
                          "Set by a person and is kept on every re-classify. Only an "
                          "amount can be added to or taken off net pay.",
                    'vi': "Được suy ra từ chính các công thức của chương trình lương "
                          "khi bạn bấm Phân loại lại từ các công thức. Vai trò bạn tự "
                          "chọn được đánh dấu là do một người đặt và được giữ nguyên "
                          "mỗi lần phân loại lại. Chỉ một số tiền mới có thể được "
                          "cộng vào hoặc trừ khỏi lương thực nhận.",
                },
                'choices_when': {
                    'earning': {
                        'en': "Pay the person receives: salary, allowances, overtime pay.",
                        'vi': "Khoản người lao động nhận: lương, phụ cấp, tiền tăng ca."},
                    'deduction': {
                        'en': "Money taken from the person's pay: their insurance "
                              "share, tax, a loan repayment.",
                        'vi': "Khoản trừ vào lương của người lao động: phần bảo hiểm "
                              "của họ, thuế, tiền trả nợ vay."},
                    'net': {
                        'en': "The final take-home figure. One component per scheme.",
                        'vi': "Con số thực nhận cuối cùng. Mỗi chương trình lương chỉ "
                              "có một thành phần như vậy."},
                    'employer_cost': {
                        'en': "Paid by the company on top of pay, such as the "
                              "employer's insurance share. It never reaches the person.",
                        'vi': "Công ty chi thêm ngoài lương, như phần bảo hiểm công ty "
                              "đóng. Khoản này không bao giờ đến tay người lao động."},
                    'info': {
                        'en': "Shown, never counted: hours, days, rates, codes and dates.",
                        'vi': "Chỉ hiển thị, không bao giờ được tính: giờ, ngày, tỷ lệ, "
                              "mã và ngày tháng."},
                    'mixed': {
                        'en': "The formulas both add it and take it off. It usually "
                              "needs splitting into two components.",
                        'vi': "Các công thức vừa cộng vừa trừ nó. Thường cần tách thành "
                              "hai thành phần."},
                },
                'used_by': [
                    {'label': {'en': "Every payslip line, when payslips are computed",
                               'vi': "Mọi dòng phiếu lương, khi phiếu lương được tính"},
                     'ref': 'pb_hr_payroll_formula/models/hr_payslip_formula.py:'
                            '_create_payslip_lines_from_formulas',
                     'via': _LINE_ROLE},
                    {'label': {'en': "Payslips made from imported pay data",
                               'vi': "Phiếu lương tạo từ dữ liệu lương được nhập"},
                     'ref': 'pb_hr_payroll_formula/models/payroll_import_batch.py:'
                            '_compute_and_create_payslip_lines',
                     'via': _LINE_ROLE},
                    {'label': {'en': "Pay run totals: Gross, Deductions, Net",
                               'vi': "Tổng của đợt lương: Tổng thu nhập, Khấu trừ, "
                                     "Thực nhận"},
                     'ref': 'pb_payruns/models/hr_payslip_run.py:_pb_bucket_sql',
                     'via': _LINE_ROLE},
                    {'label': {'en': "The \"Figures don't add up\" check on Runs",
                               'vi': "Kiểm tra \"Số liệu không khớp\" ở Các đợt lương"},
                     'ref': 'pb_payruns/models/hr_payslip_run.py:_compute_pb_totals',
                     'via': _LINE_ROLE},
                    {'label': {'en': "The figures on Home",
                               'vi': "Các số liệu trên Trang chủ"},
                     'ref': 'pb_dashboard/models/home_data.py:_home_money',
                     'via': 'hr.payslip.run.pb_total_net'},
                    {'label': {'en': "Gross, Deductions and Net on every payslip",
                               'vi': "Tổng thu nhập, Khấu trừ và Thực nhận trên mọi "
                                     "phiếu lương"},
                     'ref': 'om_hr_payroll/models/pay_bands.py:pb_pay_band',
                     'via': _LINE_ROLE},
                    {'label': {'en': "The payslip statement people receive",
                               'vi': "Bảng kê phiếu lương người lao động nhận"},
                     'ref': 'pb_payslip/models/hr_payslip.py:_pb_build_statement',
                     'via': _LINE_ROLE},
                    {'label': {'en': "The bank file (the net pay line)",
                               'vi': "Tệp ngân hàng (dòng lương thực nhận)"},
                     'ref': 'pb_pay_delivery/models/bank_export_wizard.py:_slip_net',
                     'via': 'hr.payslip.line.pb_net_line'},
                    {'label': {'en': "Need review on Payslips",
                               'vi': "Cần xem xét ở Phiếu lương"},
                     'ref': 'pb_payslip_review/models/review_flags.py:pb_review_flags',
                     'via': _LINE_ROLE},
                    {'label': {'en': "Analytics Explorer",
                               'vi': "Khám phá dữ liệu"},
                     'ref': 'pb_explorer/models/pb_fact_builder.py:_division_sql'},
                    {'label': {'en': "Final settlement",
                               'vi': "Quyết toán khi nghỉ việc"},
                     'ref': 'pb_hr_fullandfinal/models/full_and_final.py:'
                            '_build_component_summary'},
                    {'label': {'en': "Decision Room costings",
                               'vi': "Tính chi phí trong Phòng quyết định"},
                     'ref': 'pb_decision_room/models/pb_decision_exact.py:_classified'},
                    {'label': {'en': "Pay for part of a month (work segments)",
                               'vi': "Lương cho một phần của tháng (theo giai đoạn làm việc)"},
                     'ref': 'pb_workseg/models/pb_work_segment.py:_roles_for'},
                    {'label': {'en': "Groups on Mapping › Journey",
                               'vi': "Các nhóm trên Ánh xạ › Hành trình"},
                     'ref': 'pb_source_atlas/models/pb_source_atlas.py:_atlas_components'},
                ],
                'if_changed': {
                    'en': "Reports use the new role from now on. Payslips already "
                          "computed keep the old role until you recompute the run.",
                    'vi': "Từ giờ các báo cáo dùng vai trò mới. Các phiếu lương đã "
                          "tính giữ vai trò cũ cho tới khi bạn tính lại đợt lương.",
                },
                'anchor': 'tr-table',
            },
            # ---------------------------------------------- Included in another total
            {
                'key': 'rollup', 'field': 'net_role_detail',
                'column': {'en': "Included in another total",
                           'vi': "Đã tính trong một tổng khác"},
                'source_field': 'net_role_source',
                'filled_by': {
                    'en': "Ticked from the formulas when this amount is already "
                          "counted inside another component, such as an allowance "
                          "inside gross pay. Re-classify keeps a tick you changed "
                          "yourself.",
                    'vi': "Được đánh dấu theo các công thức khi số tiền này đã được "
                          "tính bên trong một thành phần khác, như một khoản phụ cấp "
                          "nằm trong tổng thu nhập. Phân loại lại giữ nguyên dấu bạn "
                          "tự đổi.",
                },
                'used_by': [
                    {'label': {'en': "Every payslip line, when payslips are computed",
                               'vi': "Mọi dòng phiếu lương, khi phiếu lương được tính"},
                     'ref': 'pb_hr_payroll_formula/models/hr_payslip_formula.py:'
                            '_create_payslip_lines_from_formulas',
                     'via': _LINE_DETAIL},
                    {'label': {'en': "Pay run totals: Gross, Deductions, Net",
                               'vi': "Tổng của đợt lương: Tổng thu nhập, Khấu trừ, "
                                     "Thực nhận"},
                     'ref': 'pb_payruns/models/hr_payslip_run.py:_compute_pb_totals',
                     'via': _LINE_DETAIL},
                    {'label': {'en': "Gross, Deductions and Net on every payslip",
                               'vi': "Tổng thu nhập, Khấu trừ và Thực nhận trên mọi "
                                     "phiếu lương"},
                     'ref': 'om_hr_payroll/models/pay_bands.py:pb_counts_in_totals',
                     'via': _LINE_DETAIL},
                    {'label': {'en': "The payslip statement people receive",
                               'vi': "Bảng kê phiếu lương người lao động nhận"},
                     'ref': 'pb_payslip/models/hr_payslip.py:_pb_build_statement',
                     'via': _LINE_DETAIL},
                    {'label': {'en': "Decision Room costings",
                               'vi': "Tính chi phí trong Phòng quyết định"},
                     'ref': 'pb_decision_room/models/pb_decision_exact.py:_classified'},
                    {'label': {'en': "Pay for part of a month (work segments)",
                               'vi': "Lương cho một phần của tháng (theo giai đoạn làm việc)"},
                     'ref': 'pb_workseg/models/pb_work_segment.py:_employer_cost',
                     'via': _LINE_DETAIL},
                ],
                'if_changed': {
                    'en': "Totals start or stop counting this line, so the same money "
                          "is never counted twice. The line still shows on the "
                          "payslip. Recompute the run to update payslips already "
                          "computed.",
                    'vi': "Các tổng bắt đầu hoặc thôi tính dòng này, để cùng một khoản "
                          "tiền không bao giờ bị tính hai lần. Dòng này vẫn hiện trên "
                          "phiếu lương. Hãy tính lại đợt lương để cập nhật các phiếu "
                          "lương đã tính.",
                },
                'anchor': 'tr-table',
            },
            # ---------------------------------------------- Run signal
            {
                'key': 'run_signal', 'field': 'payroll_signal',
                'column': {'en': "Run signal", 'vi': "Tín hiệu cho đợt lương"},
                'filled_by': {
                    'en': "Suggested during setup from the component's name and "
                          "sample values; you choose it here. Leave it blank for an "
                          "ordinary pay component.",
                    'vi': "Được gợi ý khi thiết lập, dựa trên tên và giá trị mẫu của "
                          "thành phần; bạn chọn ở đây. Để trống với một thành phần "
                          "lương bình thường.",
                },
                'choices_when': {
                    'employment_status': {
                        'en': "The pay run reads it to decide whether a person still "
                              "gets a payslip.",
                        'vi': "Đợt lương đọc nó để quyết định một người có còn nhận "
                              "phiếu lương không."},
                    'worked_hours': {
                        'en': "The pay run reads it as the hours each person actually "
                              "worked.",
                        'vi': "Đợt lương đọc nó là số giờ mỗi người đã thực sự làm."},
                },
                'used_by': [
                    {'label': {'en': "Run › who gets a payslip this month",
                               'vi': "Chạy lương › ai nhận phiếu lương tháng này"},
                     'ref': 'pb_payrun_wizard/models/pb_payrun_wizard.py:_employee_signals',
                     'via': 'hr.formula.config.employee_signal_map'},
                    {'label': {'en': "Finding the status and hours components",
                               'vi': "Tìm thành phần trạng thái và số giờ"},
                     'ref': 'pb_hr_payroll_formula/models/formula_config.py:'
                            '_signal_component'},
                    {'label': {'en': "Pay for part of a month (work segments)",
                               'vi': "Lương cho một phần của tháng (theo giai đoạn làm việc)"},
                     'ref': 'pb_workseg/models/pb_work_segment.py:_prorated_codes'},
                ],
                'if_changed': {
                    'en': "The next pay run reads the new signal, and it can change "
                          "who gets a payslip. Check the number of people in the run "
                          "after you change it.",
                    'vi': "Đợt lương tiếp theo đọc tín hiệu mới, và điều đó có thể "
                          "thay đổi ai nhận phiếu lương. Hãy kiểm tra số người trong "
                          "đợt lương sau khi bạn đổi.",
                },
                'anchor': 'tr-table',
            },
            # ---------------------------------------------- Value type
            {
                'key': 'value_kind', 'field': 'value_kind',
                'column': {'en': "Value type", 'vi': "Loại giá trị"},
                'source_field': 'value_kind_source',
                'filled_by': {
                    'en': "Worked out when the scheme is imported, from the "
                          "spreadsheet's values, its date and percentage formats and "
                          "the formulas. New pay data can refine it when you "
                          "re-classify. A type you choose is never overwritten.",
                    'vi': "Được suy ra khi nhập chương trình lương, từ các giá trị "
                          "trong bảng tính, định dạng ngày và phần trăm, và các công "
                          "thức. Dữ liệu lương mới có thể chỉnh lại khi bạn phân loại "
                          "lại. Loại bạn tự chọn không bao giờ bị ghi đè.",
                },
                'choices_when': {
                    'money': {
                        'en': "An amount of money. The only type that can be added "
                              "to or taken off net pay.",
                        'vi': "Một số tiền. Loại duy nhất có thể được cộng vào hoặc "
                              "trừ khỏi lương thực nhận."},
                    'quantity': {
                        'en': "Hours or days. Its pay role can only be Information "
                              "only; the pay comes from the formula that multiplies it.",
                        'vi': "Số giờ hoặc số ngày. Vai trò trong lương của nó chỉ có "
                              "thể là Chỉ để tham khảo; tiền lương đến từ công thức "
                              "nhân với nó."},
                    'text': {
                        'en': "Words kept exactly as they arrive, such as a location "
                              "a formula compares against.",
                        'vi': "Chữ được giữ đúng như khi đi vào, như một địa điểm mà "
                              "công thức đem ra so sánh."},
                },
                'used_by': [
                    {'label': {'en': "Which components become payslip lines",
                               'vi': "Thành phần nào trở thành dòng phiếu lương"},
                     'ref': 'pb_hr_payroll_formula/models/hr_payslip_formula.py:'
                            '_create_payslip_lines_from_formulas'},
                    {'label': {'en': "Reading the month's spreadsheet",
                               'vi': "Đọc bảng tính của tháng"},
                     'ref': 'pb_hr_payroll_formula/models/payroll_import_batch.py:'
                            'normalize_input_value'},
                    {'label': {'en': "Payslips made from imported pay data",
                               'vi': "Phiếu lương tạo từ dữ liệu lương được nhập"},
                     'ref': 'pb_hr_payroll_formula/models/payroll_import_batch.py:'
                            '_compute_and_create_payslip_lines'},
                    {'label': {'en': "Values from a connected system",
                               'vi': "Giá trị từ một hệ thống được kết nối"},
                     'ref': 'pb_hr_payroll_formula/models/integration_field_mapping.py:'
                            'transform_value'},
                    {'label': {'en': "Components in the contract drawer",
                               'vi': "Các thành phần trong ngăn hợp đồng"},
                     'ref': 'pb_contracts/models/pb_contract_360.py:_cd_comp_row'},
                    {'label': {'en': "Decision Room costings",
                               'vi': "Tính chi phí trong Phòng quyết định"},
                     'ref': 'pb_decision_room/models/pb_decision_exact.py:_classified'},
                    {'label': {'en': "Mapping › Journey",
                               'vi': "Ánh xạ › Hành trình"},
                     'ref': 'pb_source_atlas/models/pb_source_atlas.py:_atlas_components'},
                ],
                'if_changed': {
                    'en': "New values are read the new way. Values already stored on "
                          "payslips stay as they were until you recompute the run. "
                          "Choosing a type that is not an amount sets its pay role to "
                          "Information only.",
                    'vi': "Các giá trị mới được đọc theo cách mới. Các giá trị đã lưu "
                          "trên phiếu lương giữ nguyên cho tới khi bạn tính lại đợt "
                          "lương. Chọn một loại không phải số tiền sẽ đặt vai trò trong "
                          "lương của nó thành Chỉ để tham khảo.",
                },
                'anchor': 'tr-table',
            },
        ],
        'actions': [
            {'label': {'en': "Re-classify from the formulas",
                       'vi': "Phân loại lại từ các công thức"},
             'method': 'hr.formula.config.reclassify_from_formulas',
             'effect': {'en': "Works out value types, pay roles, totals and report "
                              "groups again. Choices you saved are kept.",
                        'vi': "Suy ra lại loại giá trị, vai trò trong lương, các tổng "
                              "và nhóm báo cáo. Những lựa chọn bạn đã lưu được giữ "
                              "nguyên."},
             'writes': True},
            {'label': {'en': "Set all of them to Information only",
                       'vi': "Đặt tất cả thành Chỉ để tham khảo"},
             'method': 'hr.formula.config.fix_role_conflicts',
             'effect': {'en': "Every row whose value type says otherwise becomes "
                              "Information only, marked as set by you.",
                        'vi': "Mọi dòng có loại giá trị nói khác trở thành Chỉ để "
                              "tham khảo, được đánh dấu là do bạn đặt."},
             'writes': True},
            {'label': {'en': "Save", 'vi': "Lưu"},
             'method': 'hr.formula.config.set_component_setup',
             'effect': {'en': "Saves the rows you changed. Payslips keep their "
                              "values until you recompute the run.",
                        'vi': "Lưu các dòng bạn đã đổi. Phiếu lương giữ nguyên giá trị "
                              "cho tới khi bạn tính lại đợt lương."},
             'writes': True},
        ],
        'right_now': 'hr.formula.config.learn_right_now',
        'station': 'treatment',
        'tasks': ['sc_treatment'],
        'terms': ['componentTreatment', 'payRole', 'subtotal', 'valueType'],
        'retired_labels': {'en': ["Group", "Subtotal", "Tells the run"],
                           'vi': ["Tổng phụ", "Báo cho đợt lương"]},
    },
}
