# -*- coding: utf-8 -*-
"""LEARNREV P5a - screen manifest for Workforce > Time.

Read by pb_learn's guide; never imported by this module. Plain data only.
Nothing on this screen is an editable field of one record: it is four views of
the same week (the lens tabs), and the Exceptions count is worked out per call
by `pb.time.hub`. So every entry is `derived` from the code that produces it,
checked by the truth gate. Every sentence in English and Vietnamese.
"""

_XML = 'pb_time_hub/static/src/xml/time_hub.xml'
_JS = 'pb_time_hub/static/src/js/time_hub.js'
_PY = 'pb_time_hub/models/time_hub.py'

MANIFESTS = {
    'wftime': {
        'model': None,
        'templates': [_XML, _JS],
        'purpose': {
            'en': "See the hours worked for the week, as a timeline or a grid, "
                  "and clear the entries that need a look before the week closes.",
            'vi': "Xem giờ làm trong tuần, dạng dòng thời gian hoặc dạng lưới, và "
                  "xử lý những mục cần xem trước khi chốt tuần.",
        },
        'path': {'tag': 'pb_workforce', 'lens': 'time'},
        'before': [
            {'screen': 'wftoday',
             'why': {'en': "Today shows who is in now; Time shows the whole week.",
                     'vi': "Hôm nay cho thấy ai đang có mặt; Chấm công cho thấy cả tuần."}},
        ],
        'after': [
            {'screen': 'wfclose',
             'why': {'en': "Once the week's exceptions are clear, close the week "
                           "so payroll can use it.",
                     'vi': "Khi các ngoại lệ của tuần đã xử lý xong, hãy chốt tuần "
                           "để bảng lương sử dụng."}},
        ],
        'fields': [
            {
                'key': 'timeline', 'derived': True,
                'column': {'en': "Timeline", 'vi': "Dòng thời gian"},
                'from': _JS + ':lenses',
                'how': {
                    'en': "One row per person for the chosen week, with a bar for "
                          "each stretch worked and the regular and overtime hours "
                          "added up.",
                    'vi': "Mỗi người một dòng cho tuần đã chọn, mỗi quãng đã làm là "
                          "một thanh, kèm tổng giờ thường và giờ tăng ca.",
                },
                'if_changed': {
                    'en': "Read-only. Press a name to open that person's week and "
                          "file a correction.",
                    'vi': "Chỉ xem. Bấm vào một tên để mở tuần của người đó và gửi "
                          "một đề nghị chỉnh sửa.",
                },
                'anchor': 'wf-time',
            },
            {
                'key': 'week_grid', 'derived': True,
                'column': {'en': "Week Grid", 'vi': "Lưới tuần"},
                'from': _JS + ':lenses',
                'how': {
                    'en': "The week as a table, one line per person and one column "
                          "per day, where hours are entered and corrected.",
                    'vi': "Tuần dưới dạng bảng, mỗi người một dòng và mỗi ngày một "
                          "cột, nơi giờ làm được nhập và chỉnh sửa.",
                },
                'if_changed': {
                    'en': "This is where hours are typed in. A change here shows on "
                          "the Timeline and in the Exceptions count.",
                    'vi': "Đây là nơi nhập giờ làm. Thay đổi ở đây hiện trên Dòng "
                          "thời gian và trong số Ngoại lệ.",
                },
                'anchor': 'wf-time',
            },
            {
                'key': 'exceptions', 'derived': True,
                'column': {'en': "Exceptions", 'vi': "Ngoại lệ"},
                'from': _PY + ':get_hub_summary',
                'how': {
                    'en': "Counts the entries in the week that need a look: a missing "
                          "punch in or out, a late start or an early departure.",
                    'vi': "Đếm các mục trong tuần cần xem: thiếu chấm công vào hoặc "
                          "ra, đi muộn hoặc về sớm.",
                },
                'if_changed': {
                    'en': "Read-only. The count drops as you fix each entry, and the "
                          "banner above disappears at zero.",
                    'vi': "Chỉ xem. Số này giảm khi bạn sửa từng mục, và dải thông "
                          "báo phía trên biến mất khi về không.",
                },
                'anchor': 'wf-exceptions',
            },
            {
                'key': 'import', 'derived': True,
                'column': {'en': "Import", 'vi': "Nhập"},
                'from': _JS + ':lenses',
                'how': {
                    'en': "Brings in hours from a file, step by step, and shows what "
                          "was read before anything is saved.",
                    'vi': "Nạp giờ làm từ một tệp, từng bước, và cho thấy những gì "
                          "đã đọc được trước khi lưu bất cứ điều gì.",
                },
                'if_changed': {
                    'en': "Writes the hours you confirm into the week. Check the "
                          "preview first.",
                    'vi': "Ghi các giờ bạn xác nhận vào tuần. Hãy xem phần xem "
                          "trước trước tiên.",
                },
                'anchor': 'wf-time',
            },
        ],
        'actions': [],
        'right_now': None,
        'station': 'wftime',
        'tasks': [],
        'terms': ['overtime'],
    },
}
