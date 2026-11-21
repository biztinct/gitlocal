# -*- coding: utf-8 -*-
"""LEARNREV P5a — screen manifest for People › Employees.

Read by pb_learn's guide; never imported by this module. Plain data only.
The numbers line is worked out per call by `pb.people.get_roster_data`, so every
entry is `derived` from it (or from the JS that opens the row's contract) and is
checked by the truth gate. No "right now" list: the numbers line is already the
screen's own to-do list. Every sentence in English and Vietnamese.
"""

_XML = 'pb_people/static/src/xml/people.xml'
_JS = 'pb_people/static/src/js/people.js'
_ROSTER = 'pb_people/models/pb_people.py:get_roster_data'
_BANK_READER = {
    'label': {'en': "Pay run: people with no bank account, on Home",
              'vi': "Đợt lương: người chưa có tài khoản ngân hàng, trên Trang chủ"},
    'ref': 'pb_dashboard/models/home_data.py:_home_bank_link',
    'via': 'hr.employee.account_number',
}
_ELIGIBLE_READER = {
    'label': {'en': "Who a new pay run includes",
              'vi': "Ai được đưa vào một đợt lương mới"},
    'ref': 'pb_payrun_wizard/models/pb_payrun_wizard.py:_eligible_employees',
    'via': 'hr.contract.state',
}

MANIFESTS = {
    'employees': {
        'model': None,
        'templates': [_XML, _JS],
        'purpose': {
            'en': "See everyone the company employs, whether each person can be paid, "
                  "and open any contract from its row.",
            'vi': "Xem mọi người công ty đang thuê, từng người có trả lương được không, "
                  "và mở hợp đồng ngay từ dòng của họ.",
        },
        'path': {'tag': 'pb_people_hub', 'lens': 'employees'},
        'before': [
            {'screen': 'import',
             'why': {'en': "People usually arrive here from an import of your staff list.",
                     'vi': "Nhân viên thường đến đây từ việc nhập danh sách nhân sự của bạn."}},
        ],
        'after': [
            {'screen': 'runpayroll',
             'why': {'en': "Anyone who is not payroll-ready is computed in a run but not paid.",
                     'vi': "Người chưa sẵn sàng tính lương vẫn được tính trong đợt lương "
                           "nhưng không nhận được tiền."}},
        ],
        'fields': [
            {
                'key': 'not_ready', 'derived': True,
                'column': {'en': "Not payroll-ready", 'vi': "Chưa sẵn sàng tính lương"},
                'from': _ROSTER,
                'how': {
                    'en': "Counts people with no running contract or no bank details. "
                          "Press it to list only them; press it again for everyone.",
                    'vi': "Đếm những người chưa có hợp đồng đang hiệu lực hoặc chưa có thông "
                          "tin ngân hàng. Bấm vào để chỉ liệt kê họ; bấm lần nữa để xem "
                          "mọi người.",
                },
                'if_changed': {
                    'en': "Read-only. It drops when a contract becomes running or bank "
                          "details are added.",
                    'vi': "Chỉ xem. Con số giảm khi một hợp đồng trở thành đang hiệu lực "
                          "hoặc khi thêm thông tin ngân hàng.",
                },
                'used_by': [_BANK_READER, _ELIGIBLE_READER],
                'anchor': 'pe-kpis',
            },
            {
                'key': 'ready_share', 'derived': True,
                'column': {'en': "Payroll-ready", 'vi': "Sẵn sàng tính lương"},
                'from': _ROSTER,
                'how': {
                    'en': "The share of people with bank details on file. A row's tick "
                          "also needs a running contract, so this can read higher.",
                    'vi': "Tỷ lệ người đã có thông tin ngân hàng. Dấu tích trên mỗi dòng còn "
                          "cần hợp đồng đang hiệu lực, nên con số này có thể cao hơn.",
                },
                'if_changed': {
                    'en': "Read-only. It rises as bank details are added.",
                    'vi': "Chỉ xem. Con số tăng khi thông tin ngân hàng được thêm vào.",
                },
                'used_by': [_BANK_READER],
                'anchor': 'pe-kpis',
            },
            {
                'key': 'headcount', 'derived': True,
                'column': {'en': "Headcount", 'vi': "Số lượng nhân sự"},
                'from': _ROSTER,
                'how': {
                    'en': "Everyone active in your companies, not only the people listed "
                          "below. The list shows the first 240.",
                    'vi': "Mọi người đang làm việc trong các công ty của bạn, không chỉ những "
                          "người được liệt kê bên dưới. Danh sách hiển thị 240 người đầu.",
                },
                'if_changed': {
                    'en': "Read-only. Add an employee or archive one to change it.",
                    'vi': "Chỉ xem. Hãy thêm hoặc lưu trữ một nhân viên để thay đổi nó.",
                },
                'anchor': 'pe-kpis',
            },
            {
                'key': 'running', 'derived': True,
                'column': {'en': "Running contracts", 'vi': "Hợp đồng đang hiệu lực"},
                'from': _ROSTER,
                'how': {
                    'en': "Contracts that are running now, counted over every contract. "
                          "Press it to list the people who have one.",
                    'vi': "Các hợp đồng đang hiệu lực, đếm trên mọi hợp đồng. Bấm vào để "
                          "liệt kê những người có hợp đồng đó.",
                },
                'if_changed': {
                    'en': "Read-only. It follows each contract's status.",
                    'vi': "Chỉ xem. Con số thay đổi theo trạng thái của từng hợp đồng.",
                },
                'used_by': [
                    _ELIGIBLE_READER,
                    {'label': {'en': "The Contracts board's running count",
                               'vi': "Số hợp đồng đang hiệu lực trên bảng Hợp đồng"},
                     'ref': 'pb_contracts/models/pb_contracts.py:get_board',
                     'via': 'hr.contract.state'},
                ],
                'anchor': 'pe-kpis',
            },
            {
                'key': 'expiring', 'derived': True,
                'column': {'en': "Expiring within 30 days",
                           'vi': "Hết hạn trong 30 ngày"},
                'from': _ROSTER,
                'how': {
                    'en': "Running contracts whose end date falls in the next 30 days. "
                          "Each person's row also shows the days left.",
                    'vi': "Các hợp đồng đang hiệu lực có ngày kết thúc trong 30 ngày tới. "
                          "Dòng của mỗi người cũng hiện số ngày còn lại.",
                },
                'if_changed': {
                    'en': "Read-only. Renew or end the contract; the count follows its "
                          "end date.",
                    'vi': "Chỉ xem. Hãy gia hạn hoặc kết thúc hợp đồng; con số theo ngày "
                          "kết thúc của nó.",
                },
                'used_by': [
                    {'label': {'en': "The Contracts board's ending-soon count",
                               'vi': "Số hợp đồng sắp hết hạn trên bảng Hợp đồng"},
                     'ref': 'pb_contracts/models/pb_contracts.py:get_board',
                     'via': 'hr.contract.date_end'},
                ],
                'anchor': 'pe-kpis',
            },
            {
                'key': 'wage', 'derived': True,
                'column': {'en': "Monthly wage", 'vi': "Lương hàng tháng"},
                'from': _ROSTER,
                'how': {
                    'en': "The wages of all running contracts added up, shown in short "
                          "form such as 1.2B.",
                    'vi': "Tổng lương của mọi hợp đồng đang hiệu lực, hiển thị dạng rút "
                          "gọn như 1,2B.",
                },
                'if_changed': {
                    'en': "Read-only. It follows the wage on each contract.",
                    'vi': "Chỉ xem. Con số thay đổi theo mức lương trên từng hợp đồng.",
                },
                'used_by': [
                    {'label': {'en': "The Contracts board's wage total",
                               'vi': "Tổng lương trên bảng Hợp đồng"},
                     'ref': 'pb_contracts/models/pb_contracts.py:get_board',
                     'via': 'hr.contract.wage'},
                ],
                'anchor': 'pe-kpis',
            },
            {
                'key': 'contract_button', 'derived': True,
                'column': {'en': "Contract", 'vi': "Hợp đồng"},
                'from': _JS + ':openContract',
                'how': {
                    'en': "Shown on a row when the person has a contract and you may open "
                          "contracts. It opens that contract in a side panel.",
                    'vi': "Hiện trên dòng khi người đó có hợp đồng và bạn được mở hợp đồng. "
                          "Nó mở hợp đồng ấy trong một khung bên cạnh.",
                },
                'if_changed': {
                    'en': "Nothing is saved from the panel until you press Save there.",
                    'vi': "Không có gì được lưu từ khung đó cho đến khi bạn bấm Lưu ở đó.",
                },
                'anchor': 'pe-rowcontract',
            },
        ],
        # The screen's buttons (Contract, Select, Add employee, Bulk update) act
        # in the browser or open other screens; none calls a server method of
        # its own, so there is nothing to list here.
        'actions': [],
        'right_now': None,
        'station': 'employees',
        'tasks': ['sc_people'],
        'terms': ['contract', 'headcount', 'payrollReady'],
    },
}
