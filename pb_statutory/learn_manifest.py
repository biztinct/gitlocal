# -*- coding: utf-8 -*-
"""LEARNREV P5a — screen manifest for the Statutory cockpit (insurance and tax).

Read by pb_learn's guide; never imported by this module. Plain data only.
The figures on this screen are worked out per call by `pb.statutory`
(`get_statutory_data`), so every entry is `derived` from that function and the
truth gate checks the column text against the template. "Right now" is
`pb.statutory.learn_right_now` (models/statutory_learn.py). Every sentence in
English and Vietnamese.
"""

_XML = 'pb_statutory/static/src/xml/statutory.xml'
_JS = 'pb_statutory/static/src/js/statutory.js'
_PY = 'pb_statutory/models/pb_statutory.py'
_EMP = 'pb_hr_payroll_vietnam/models/hr_employee_vietnam.py'
_ANALYTICS = 'pb_hr_payroll_vietnam/models/hr_formula_config_analytics_vietnam.py'
_WIZ = 'pb_hr_payroll_vietnam/wizards/vietnam_insurance_analytics.py'
_TAX = 'pb_hr_payroll_formula/models/payroll_tax_table.py'

_READ_ONLY = {
    'en': "Read-only here. To change a rate, add a new policy dated from the day the "
          "change applies; never edit the one in force.",
    'vi': "Chỉ xem ở đây. Muốn đổi một tỷ lệ, hãy thêm chính sách mới đề ngày bắt đầu "
          "áp dụng; đừng bao giờ sửa chính sách đang chạy.",
}


def _insurance_readers(field):
    """The three places that turn a policy rate or ceiling into money."""
    via = 'vietnam.insurance.policy.' + field
    return [
        {'label': {'en': "The insurance cost on each employee",
                   'vi': "Chi phí bảo hiểm trên từng nhân viên"},
         'ref': _EMP + ':_compute_insurance_cost', 'via': via},
        {'label': {'en': "The contribution analysis",
                   'vi': "Phân tích đóng góp"},
         'ref': _WIZ + ':_compute_contribution_totals', 'via': via},
        {'label': {'en': "The insurance totals on a pay scheme",
                   'vi': "Tổng bảo hiểm trên một chương trình lương"},
         'ref': _ANALYTICS + ':_compute_insurance_data', 'via': via},
    ]


MANIFESTS = {
    'statutory': {
        'model': None,
        'templates': [_XML, _JS],
        'purpose': {
            'en': "The insurance rates and tax brackets in force for this company, and "
                  "what the last pay run paid into them.",
            'vi': "Các tỷ lệ bảo hiểm và bậc thuế đang hiệu lực của công ty này, và số "
                  "tiền đợt lương gần nhất đã đóng vào đó.",
        },
        'path': {'xmlid': 'pb_statutory.action_pb_statutory'},
        'before': [
            {'screen': 'structures',
             'why': {'en': "The pay scheme holds the insurance and tax lines these "
                           "rates feed.",
                     'vi': "Chương trình lương chứa các dòng bảo hiểm và thuế mà các "
                           "tỷ lệ này cung cấp số liệu."}},
        ],
        'after': [
            {'screen': 'govreports',
             'why': {'en': "Once the rates are right, file the month's insurance "
                           "report.",
                     'vi': "Khi các tỷ lệ đã đúng, hãy nộp báo cáo bảo hiểm của "
                           "tháng."}},
        ],
        'fields': [
            {
                'key': 'rates', 'derived': True,
                'column': {'en': "Active insurance rates",
                           'vi': "Tỷ lệ bảo hiểm tích cực"},
                'from': _PY + ':get_statutory_data',
                'how': {
                    'en': "The company's active policy with the latest effective date. "
                          "One row each for social (BHXH), health (BHYT) and "
                          "unemployment (BHTN) insurance.",
                    'vi': "Chính sách đang bật của công ty có ngày hiệu lực mới nhất. "
                          "Mỗi dòng là một loại: bảo hiểm xã hội (BHXH), y tế (BHYT) "
                          "và thất nghiệp (BHTN).",
                },
                'if_changed': _READ_ONLY,
                'anchor': 'st-rates',
            },
            {
                'key': 'employee', 'derived': True,
                'column': {'en': "Employee", 'vi': "Nhân viên"},
                'from': _PY + ':get_statutory_data',
                'how': {
                    'en': "The share of a person's insured pay, up to the ceiling, "
                          "that is taken from their own pay. Typed on the policy.",
                    'vi': "Phần lương tính bảo hiểm của một người, tối đa bằng mức "
                          "trần, được trừ vào lương của chính họ. Được nhập trên "
                          "chính sách.",
                },
                'used_by': _insurance_readers('si_employee_rate'),
                'if_changed': _READ_ONLY,
                'anchor': 'st-rates',
            },
            {
                'key': 'employer', 'derived': True,
                'column': {'en': "Employer", 'vi': "Doanh nghiệp"},
                'from': _PY + ':get_statutory_data',
                'how': {
                    'en': "The share the company pays on top of the person's pay, on "
                          "the same insured amount. Typed on the policy.",
                    'vi': "Phần công ty đóng thêm, ngoài lương của người đó, trên cùng "
                          "mức tính bảo hiểm. Được nhập trên chính sách.",
                },
                'used_by': _insurance_readers('si_employer_rate'),
                'if_changed': _READ_ONLY,
                'anchor': 'st-rates',
            },
            {
                'key': 'ceiling', 'derived': True,
                'column': {'en': "Ceiling", 'vi': "Trần nhà"},
                'from': _PY + ':get_statutory_data',
                'how': {
                    'en': "The most pay that insurance is worked out on. Pay above it "
                          "adds nothing to the contribution. Typed on the policy.",
                    'vi': "Mức lương cao nhất dùng để tính bảo hiểm. Phần lương vượt "
                          "mức này không làm tăng khoản đóng. Được nhập trên chính "
                          "sách.",
                },
                'used_by': _insurance_readers('si_max_salary_ceiling'),
                'if_changed': _READ_ONLY,
                'anchor': 'st-rates',
            },
            {
                'key': 'brackets', 'derived': True,
                'column': {'en': "Tax brackets", 'vi': "khung thuế"},
                'from': _PY + ':get_statutory_data',
                'how': {
                    'en': "The tax table in force today for the tax country shown: "
                          "the latest active Vietnam table, or the published country "
                          "table whose dates cover today.",
                    'vi': "Bảng thuế đang hiệu lực hôm nay của quốc gia thuế đang hiển "
                          "thị: bảng Việt Nam đang bật mới nhất, hoặc bảng quốc gia đã "
                          "phát hành có ngày bao gồm hôm nay.",
                },
                'used_by': [
                    {'label': {'en': "The payroll constants mapped to a bracket",
                               'vi': "Các hằng số lương gắn với một bậc thuế"},
                     'ref': _TAX + ':_values',
                     'via': 'hr.payroll.tax.band.income_to'},
                    {'label': {'en': "The check that brackets keep rising",
                               'vi': "Kiểm tra các bậc thuế luôn tăng dần"},
                     'ref': _TAX + ':_validate_edition',
                     'via': 'hr.payroll.tax.band.income_to'},
                ],
                'if_changed': {
                    'en': "Read-only here. A new table is added with Tax table; where "
                          "approval is on, it waits for sign-off before it applies.",
                    'vi': "Chỉ xem ở đây. Bảng mới được thêm bằng nút Bảng thuế; nếu "
                          "có bật phê duyệt, bảng chờ được duyệt rồi mới áp dụng.",
                },
                'anchor': 'st-slabs',
            },
            {
                'key': 'rate', 'derived': True,
                'column': {'en': "Rate", 'vi': "Hệ số"},
                'from': _PY + ':get_statutory_data',
                'how': {
                    'en': "The tax rate for the slice of income inside that bracket. "
                          "Some countries apply one rate to the whole income instead.",
                    'vi': "Thuế suất cho phần thu nhập nằm trong bậc đó. Một số quốc "
                          "gia áp một mức thuế cho toàn bộ thu nhập.",
                },
                'used_by': [
                    {'label': {'en': "The payroll constants mapped to a bracket",
                               'vi': "Các hằng số lương gắn với một bậc thuế"},
                     'ref': _TAX + ':_values',
                     'via': 'hr.payroll.tax.band.tax_rate'},
                ],
                'if_changed': {
                    'en': "Read-only here. Open the tax table to change a rate; the "
                          "payroll constants mapped to it show if they no longer match.",
                    'vi': "Chỉ xem ở đây. Hãy mở bảng thuế để đổi thuế suất; các hằng "
                          "số lương gắn với nó sẽ báo nếu không còn khớp.",
                },
                'anchor': 'st-slabs',
            },
            {
                'key': 'contributions', 'derived': True,
                'column': {'en': "Contributions", 'vi': "Đóng góp"},
                'from': _PY + ':get_statutory_data',
                'how': {
                    'en': "The insurance lines of the latest pay run, added up: what "
                          "was taken from people plus what the company paid.",
                    'vi': "Các dòng bảo hiểm của đợt lương gần nhất, cộng lại: phần "
                          "trừ vào lương người lao động cộng phần công ty đóng.",
                },
                'if_changed': {
                    'en': "Read-only. It follows the latest pay run; recompute that "
                          "run after a rate changes.",
                    'vi': "Chỉ xem. Nó thay đổi theo đợt lương gần nhất; hãy tính lại "
                          "đợt đó sau khi một tỷ lệ thay đổi.",
                },
                'anchor': 'st-kpis',
            },
        ],
        'actions': [
            {'label': {'en': "Insurance policy", 'vi': "Chính sách bảo hiểm"},
             'method': 'pb.statutory.create_policy',
             'effect': {'en': "Opens a form for a new policy. Saving it applies it, or "
                              "sends it for approval first if your company asks for one.",
                        'vi': "Mở biểu mẫu cho một chính sách mới. Lưu là áp dụng, hoặc "
                              "gửi đi phê duyệt trước nếu công ty bạn yêu cầu."},
             'writes': True},
            {'label': {'en': "Tax table", 'vi': "Bảng thuế"},
             'method': 'pb.statutory.create_tax_table',
             'effect': {'en': "Opens a form for a new tax table. Saving it applies it, "
                              "or sends it for approval first if your company asks "
                              "for one.",
                        'vi': "Mở biểu mẫu cho một bảng thuế mới. Lưu là áp dụng, hoặc "
                              "gửi đi phê duyệt trước nếu công ty bạn yêu cầu."},
             'writes': True},
        ],
        'right_now': 'pb.statutory.learn_right_now',
        'station': 'statutory',
        'tasks': [],
        'terms': ['statutory', 'contribution', 'bhxh', 'ceiling', 'policy', 'pit'],
    },
}
