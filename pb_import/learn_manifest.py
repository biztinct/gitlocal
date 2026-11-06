# -*- coding: utf-8 -*-
"""LEARNREV P5 — screen manifest for Payroll › Inputs (was Pay Run › Import).

Read by pb_learn's guide; never imported by this module. Plain data only.
Nothing on this screen is an editable field: every count is worked out per
call (`pb.import.get_import_data`), so each entry is `derived` from the code
that computes it. Every sentence in English and Vietnamese.
"""

_XML = 'pb_import/static/src/xml/import.xml'
_JS = 'pb_import/static/src/js/import.js'
_PY = 'pb_import/models/pb_import.py'

MANIFESTS = {
    'import': {
        'model': None,
        'templates': [_XML, _JS],
        'purpose': {
            'en': "Bring this period's pay data in from a file or a connected "
                  "system, and see where every import batch stands.",
            'vi': "Đưa dữ liệu lương của kỳ này vào từ tệp hoặc hệ thống đã kết nối, "
                  "và xem mỗi đợt nhập liệu đang ở bước nào.",
        },
        'path': {'tag': 'pb_pay_hub', 'lens': 'import'},
        'before': [
            {'screen': 'runpayroll',
             'why': {'en': "Start from the pay run for the period you are loading.",
                     'vi': "Bắt đầu từ đợt lương của kỳ bạn đang tải dữ liệu."}},
        ],
        'after': [
            {'screen': 'payslips',
             'why': {'en': "Once the data is committed and the run is computed, "
                           "read the payslips.",
                     'vi': "Khi dữ liệu đã được ghi và đợt lương đã được tính, hãy "
                           "đọc các phiếu lương."}},
        ],
        'fields': [
            {
                'key': 'total_lines', 'derived': True,
                'column': {'en': "Lines", 'vi': "Dòng"},
                'from': _PY + ':get_import_data',
                'how': {
                    'en': "The number of rows read from the file or the connected "
                          "system into that batch.",
                    'vi': "Số dòng đã đọc từ tệp hoặc hệ thống đã kết nối vào đợt "
                          "nhập đó.",
                },
                'if_changed': {
                    'en': "Read-only. It changes when the batch is loaded again.",
                    'vi': "Chỉ xem. Nó thay đổi khi đợt nhập được tải lại.",
                },
                'anchor': 'im-batches',
            },
            {
                'key': 'matched', 'derived': True,
                'column': {'en': "Matched", 'vi': "Đã khớp"},
                'from': _PY + ':get_import_data',
                'how': {
                    'en': "How many rows are tied to an existing person. Rows that "
                          "are not matched need you to pick the person or add them "
                          "as new.",
                    'vi': "Số dòng đã gắn với một nhân viên hiện có. Dòng chưa khớp "
                          "cần bạn chọn nhân viên hoặc thêm họ như người mới.",
                },
                'if_changed': {
                    'en': "Read-only here. Open the batch and match the rest "
                          "before committing.",
                    'vi': "Ở đây chỉ xem. Hãy mở đợt nhập và khớp phần còn lại "
                          "trước khi ghi.",
                },
                'anchor': 'im-batches',
            },
            {
                'key': 'errors', 'derived': True,
                'column': {'en': "Errors", 'vi': "Lỗi"},
                'from': _PY + ':get_import_data',
                'how': {
                    'en': "Rows that failed a check, such as a missing person or an "
                          "unreadable value. The number turns red when it is above "
                          "zero.",
                    'vi': "Các dòng không qua được bước kiểm tra, ví dụ thiếu nhân "
                          "viên hoặc giá trị không đọc được. Con số chuyển đỏ khi "
                          "lớn hơn không.",
                },
                'if_changed': {
                    'en': "Read-only here. Fix the rows inside the batch; a row "
                          "left in error is not written.",
                    'vi': "Ở đây chỉ xem. Hãy sửa các dòng trong đợt nhập; dòng còn "
                          "lỗi sẽ không được ghi.",
                },
                'anchor': 'im-batches',
            },
            {
                'key': 'status', 'derived': True,
                'column': {'en': "Status", 'vi': "Trạng thái"},
                'from': _PY + ':STATE_LABEL',
                'values': {
                    'draft': {'en': "Draft", 'vi': "Nháp"},
                    'loaded': {'en': "Loaded", 'vi': "Đã tải"},
                    'matched': {'en': "Matched", 'vi': "Đã khớp"},
                    'validated': {'en': "Validated", 'vi': "Đã kiểm tra"},
                    'processing': {'en': "Processing", 'vi': "Đang xử lý"},
                    'done': {'en': "Done", 'vi': "Hoàn tất"},
                },
                'how': {
                    'en': "Where the batch is: created, file read, people matched, "
                          "checked, being written, then committed.",
                    'vi': "Đợt nhập đang ở đâu: đã tạo, đã đọc tệp, đã khớp nhân "
                          "viên, đã kiểm tra, đang ghi, rồi đã ghi xong.",
                },
                'if_changed': {
                    'en': "Read-only. It moves forward as you work through the "
                          "guided flow; a batch that stops before commit has "
                          "changed nothing.",
                    'vi': "Chỉ xem. Nó tiến lên khi bạn đi qua luồng có hướng dẫn; "
                          "một đợt dừng trước bước ghi thì chưa thay đổi gì.",
                },
                'anchor': 'im-pipe',
            },
        ],
        'actions': [
            {'label': {'en': "Load pay data", 'vi': "Tải dữ liệu lương"},
             'method': 'pb.import.wizard.get_defaults',
             'effect': {'en': "Opens the guided flow: upload, review matches, fix "
                              "issues, then commit. Nothing is written until the "
                              "last step.",
                        'vi': "Mở luồng có hướng dẫn: tải lên, xem các dòng khớp, "
                              "sửa vấn đề, rồi ghi. Chưa có gì được ghi cho đến "
                              "bước cuối."},
             'writes': False},
        ],
        'right_now': 'pb.import.learn_right_now',
        'station': 'import',
        'tasks': ['sc_import'],
        'terms': ['importBatch', 'commitImport', 'payData', 'thisRunOnly'],
    },
}
