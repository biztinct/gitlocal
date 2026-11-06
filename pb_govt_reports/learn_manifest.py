# -*- coding: utf-8 -*-
"""LEARNREV P5a — screen manifest for Compliance › Filings (the board).

Read by pb_learn's guide; never imported by this module. Plain data only.
The board is a thin front door: `pb.govt.reports.get_govt_reports_data` picks
the filings for the company's country, and the Generate button opens the
filing flow (`pb.filing.flow`). Nothing here is an editable field, so every
entry is `derived`. No "Right now": a filing has nothing pending until a person
chooses a month. Every sentence in English and Vietnamese.
"""

_XML = 'pb_govt_reports/static/src/xml/govt_reports.xml'
_JS = 'pb_govt_reports/static/src/js/govt_reports.js'
_PY = 'pb_govt_reports/models/pb_govt_reports.py'
_FLOW = 'pb_govt_reports/models/pb_filing_flow.py'

MANIFESTS = {
    'govreports': {
        'model': None,
        'templates': [_XML, _JS],
        'purpose': {
            'en': "The government filings this company's country asks for, grouped "
                  "by authority and ready to generate for one month.",
            'vi': "Các báo cáo nộp cơ quan nhà nước mà quốc gia của công ty này yêu "
                  "cầu, nhóm theo cơ quan và sẵn sàng kết xuất cho một tháng.",
        },
        'path': {'tag': 'pb_compliance_hub', 'lens': 'filings'},
        'before': [
            {'screen': 'payruns',
             'why': {'en': "A filing reads only runs that are computed, so finish the "
                           "month's runs first.",
                     'vi': "Một báo cáo chỉ đọc các đợt lương đã được tính, nên hãy "
                           "hoàn tất các đợt lương của tháng trước."}},
            {'screen': 'statutory',
             'why': {'en': "The insurance and tax rates the filings use are set here.",
                     'vi': "Các tỷ lệ bảo hiểm và thuế mà báo cáo dùng được đặt ở "
                           "đây."}},
        ],
        'after': [
            {'screen': 'filing_flow',
             'why': {'en': "Generate opens the three-step flow: choose the filing, "
                           "set its scope, then produce the file.",
                     'vi': "Nút Tạo mở quy trình ba bước: chọn báo cáo, đặt phạm vi, "
                           "rồi tạo tệp."}},
        ],
        'fields': [
            {
                'key': 'filings', 'derived': True,
                'column': {'en': "Government Reports", 'vi': "Báo cáo chính phủ"},
                'from': _PY + ':_CATALOG',
                'how': {
                    'en': "A fixed list for each country, grouped by authority. A tile "
                          "shows only when the country's report tool is installed.",
                    'vi': "Một danh sách cố định cho mỗi quốc gia, nhóm theo cơ quan. "
                          "Biểu mẫu chỉ hiện khi công cụ báo cáo của quốc gia đó đã "
                          "được cài.",
                },
                'used_by': [
                    {'label': {'en': "The filing flow's first step",
                               'vi': "Bước đầu của quy trình nộp báo cáo"},
                     'ref': _FLOW + ':start', 'via': 'pb.govt.reports.groups'},
                ],
                'if_changed': {
                    'en': "Read-only. A country with no tile is shown as coming soon; "
                          "nothing on this board can add one.",
                    'vi': "Chỉ xem. Quốc gia chưa có biểu mẫu được hiện là sắp ra "
                          "mắt; không có gì trên bảng này thêm được biểu mẫu.",
                },
                'anchor': 'gr-grid',
            },
            {
                'key': 'country', 'derived': True,
                'column': {'en': "Country", 'vi': "Quốc gia"},
                'from': _PY + ':get_govt_reports_data',
                'how': {
                    'en': "The company's own country, plus any country its pay schemes "
                          "are set up for. The chips show only when there is more "
                          "than one.",
                    'vi': "Quốc gia của chính công ty, cộng các quốc gia mà chương "
                          "trình lương của công ty được thiết lập. Các nút chỉ hiện "
                          "khi có nhiều hơn một.",
                },
                'used_by': [
                    {'label': {'en': "Which filings the flow offers",
                               'vi': "Quy trình nộp báo cáo đưa ra những báo cáo nào"},
                     'ref': _FLOW + ':start', 'via': 'pb.govt.reports.country_code'},
                ],
                'if_changed': {
                    'en': "Choosing a chip changes the list of filings, not the "
                          "company or any data.",
                    'vi': "Chọn một nút chỉ đổi danh sách báo cáo, không đổi công ty "
                          "hay dữ liệu nào.",
                },
                'anchor': 'gr-countries',
            },
            {
                'key': 'company_line', 'derived': True,
                'column': {'en': "Statutory filings for",
                           'vi': "Hồ sơ theo luật định cho"},
                'from': _PY + ':get_govt_reports_data',
                'how': {
                    'en': "The company you are working in and the country whose "
                          "filings are on show.",
                    'vi': "Công ty bạn đang làm việc và quốc gia có các báo cáo đang "
                          "hiển thị.",
                },
                'if_changed': {
                    'en': "Read-only. Switch company from the company menu to see "
                          "another company's filings.",
                    'vi': "Chỉ xem. Hãy đổi công ty từ menu công ty để xem báo cáo của "
                          "công ty khác.",
                },
                'anchor': 'gr-head',
            },
        ],
        'actions': [
            {'label': {'en': "Generate", 'vi': "Tạo"},
             'method': 'pb.filing.flow.start',
             'effect': {'en': "Opens the filing flow with this report chosen and the "
                              "month you picked. The file is made in its last step.",
                        'vi': "Mở quy trình nộp báo cáo với báo cáo này đã chọn và "
                              "tháng bạn đã chọn. Tệp được tạo ở bước cuối."},
             'writes': False},
        ],
        'right_now': None,
        'station': 'govreports',
        'tasks': ['sc_filings'],
        'terms': ['filing', 'statutory', 'contribution', 'payrun'],
    },
}
