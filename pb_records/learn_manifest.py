# -*- coding: utf-8 -*-
"""LEARNREV P5a — screen manifest for People › Records Desk.

Read by pb_learn's guide; never imported by this module. Plain data only.
The desk's columns are its own controls, not model fields, so every entry is
`derived` from the server method behind the control, checked by the truth gate.
"Right now" is `pb.records.desk.learn_right_now` (models/records_learn.py):
changes waiting to be applied. Every sentence in English and Vietnamese.
"""

_XML = 'pb_records/static/src/xml/records_desk.xml'
_JS = 'pb_records/static/src/js/records_desk.js'
_GRID = 'pb_records/static/src/js/records_grid.js'
_DESK = 'pb_records/models/pb_records_desk.py'
_IO = 'pb_records/models/pb_records_io.py'

MANIFESTS = {
    'records': {
        'model': None,
        'templates': [_XML, _JS, _GRID],
        'purpose': {
            'en': "Change the employee, contract and bank details your pay scheme reads, "
                  "for one person or hundreds, with each change reviewed first.",
            'vi': "Sửa thông tin nhân viên, hợp đồng và ngân hàng mà chương trình lương "
                  "của bạn đọc, cho một người hay hàng trăm người, mỗi thay đổi đều "
                  "được xem lại trước.",
        },
        'path': {'tag': 'pb_people_hub', 'lens': 'records'},
        'before': [
            {'screen': 'mapping',
             'why': {'en': "The desk offers only the fields your pay scheme maps.",
                     'vi': "Bàn hồ sơ chỉ đưa ra các trường mà chương trình lương của bạn "
                           "đã ánh xạ."}},
        ],
        'after': [
            {'screen': 'approvals',
             'why': {'en': "Approvers decide a waiting change in the one inbox.",
                     'vi': "Người phê duyệt quyết định một thay đổi đang chờ trong hộp "
                           "phê duyệt duy nhất."}},
        ],
        'fields': [
            {
                'key': 'person', 'derived': True,
                'column': {'en': "Person", 'vi': "Người"},
                'from': _GRID + ':IDENTITY_COLUMNS',
                'how': {
                    'en': "The first column of the grid: one row for each person you "
                          "picked, with their code and department beside the name.",
                    'vi': "Cột đầu tiên của lưới: mỗi người bạn đã chọn một dòng, kèm "
                          "mã và phòng ban cạnh tên.",
                },
                'if_changed': {
                    'en': "Read-only. Pick other people to add or remove rows.",
                    'vi': "Chỉ xem. Hãy chọn người khác để thêm hoặc bớt dòng.",
                },
            },
            {
                'key': 'review', 'derived': True,
                'column': {'en': "Review your changes", 'vi': "Xem lại thay đổi"},
                'from': _DESK + ':preview_changes',
                'how': {
                    'en': "Lists every value you typed with the old value beside the new "
                          "one, and flags any the desk will refuse, before anything is sent.",
                    'vi': "Liệt kê mọi giá trị bạn đã gõ với giá trị cũ cạnh giá trị mới, "
                          "và đánh dấu những giá trị bàn hồ sơ sẽ từ chối, trước khi gửi.",
                },
                'if_changed': {
                    'en': "Opening it changes nothing. Applying sends the changes along "
                          "their approval route, or applies them at once if none is needed.",
                    'vi': "Mở ra không thay đổi gì. Áp dụng sẽ gửi các thay đổi theo lộ "
                          "trình phê duyệt, hoặc áp dụng ngay nếu không cần phê duyệt.",
                },
                'anchor': 'rd-review',
            },
            {
                'key': 'history', 'derived': True,
                'column': {'en': "History", 'vi': "Lịch sử"},
                'from': _DESK + ':get_history',
                'how': {
                    'en': "Every change made from this desk, with who made it, when and "
                          "the note they gave. A change still waiting for approval is listed too.",
                    'vi': "Mọi thay đổi được thực hiện từ bàn này, kèm người thực hiện, "
                          "thời gian và ghi chú của họ. Thay đổi còn chờ phê duyệt cũng "
                          "được liệt kê.",
                },
                'if_changed': {
                    'en': "Read-only. A new line appears each time a change is applied "
                          "or undone.",
                    'vi': "Chỉ xem. Một dòng mới xuất hiện mỗi khi một thay đổi được áp "
                          "dụng hoặc hoàn tác.",
                },
                'used_by': [
                    {'label': {'en': "Whether a change can still be undone",
                               'vi': "Một thay đổi còn hoàn tác được hay không"},
                     'ref': _DESK + ':undo_apply',
                     'via': 'pb.records.apply.undone'},
                ],
                'anchor': 'rd-history',
            },
            {
                'key': 'undo', 'derived': True,
                'column': {'en': "Undo", 'vi': "Hoàn tác"},
                'from': _DESK + ':undo_apply',
                'how': {
                    'en': "Puts back the values a change replaced. A value someone else "
                          "has changed since is left alone and reported.",
                    'vi': "Đặt lại các giá trị mà một thay đổi đã thay thế. Giá trị mà "
                          "người khác đã đổi sau đó sẽ được giữ nguyên và được báo lại.",
                },
                'if_changed': {
                    'en': "The undo is itself recorded in History. A change still waiting "
                          "for approval has nothing to undo yet.",
                    'vi': "Chính việc hoàn tác cũng được ghi trong Lịch sử. Thay đổi còn "
                          "chờ phê duyệt thì chưa có gì để hoàn tác.",
                },
            },
            {
                'key': 'export', 'derived': True,
                'column': {'en': "Export with data", 'vi': "Xuất kèm dữ liệu"},
                'from': _IO + ':export_records',
                'how': {
                    'en': "Downloads the people and fields you picked as a spreadsheet "
                          "you can edit and bring back.",
                    'vi': "Tải về các người và trường bạn đã chọn dưới dạng bảng tính để "
                          "bạn sửa rồi nhập lại.",
                },
                'if_changed': {
                    'en': "Nothing changes in the system until you import the file back "
                          "and apply it.",
                    'vi': "Hệ thống không thay đổi gì cho đến khi bạn nhập lại tệp và áp dụng.",
                },
                'anchor': 'rd-file',
            },
            {
                'key': 'import', 'derived': True,
                'column': {'en': "Import a file", 'vi': "Nhập từ tệp"},
                'from': _IO + ':import_peek',
                'how': {
                    'en': "Reads a spreadsheet and lines its values up against your "
                          "people, so you can review them like typed changes.",
                    'vi': "Đọc một bảng tính và đối chiếu các giá trị với nhân viên của "
                          "bạn, để bạn xem lại như các thay đổi tự gõ.",
                },
                'if_changed': {
                    'en': "Reading the file writes nothing. Rows that match nobody are "
                          "listed for you to fix.",
                    'vi': "Đọc tệp không ghi gì cả. Các dòng không khớp với ai sẽ được "
                          "liệt kê để bạn sửa.",
                },
                'anchor': 'rd-file',
            },
        ],
        'actions': [
            {'label': {'en': "Review your changes", 'vi': "Xem lại thay đổi"},
             'method': 'pb.records.desk.preview_changes',
             'effect': {'en': "Checks every typed change against the people and fields; "
                              "nothing is written.",
                        'vi': "Kiểm tra mọi thay đổi đã gõ so với nhân viên và trường; "
                              "không có gì được ghi."},
             'writes': False},
            {'label': {'en': "Apply 1 change", 'vi': "Áp dụng 1 thay đổi"},
             'method': 'pb.records.desk.apply_changes',
             'effect': {'en': "Sends the changes for approval, or applies them at once "
                              "where no approval is needed.",
                        'vi': "Gửi các thay đổi đi phê duyệt, hoặc áp dụng ngay nơi không "
                              "cần phê duyệt."},
             'writes': True},
            {'label': {'en': "Undo", 'vi': "Hoàn tác"},
             'method': 'pb.records.desk.undo_apply',
             'effect': {'en': "Puts back the earlier values of an applied change, leaving "
                              "alone any value changed since.",
                        'vi': "Đặt lại các giá trị trước đó của một thay đổi đã áp dụng, "
                              "giữ nguyên mọi giá trị đã bị đổi sau đó."},
             'writes': True},
            {'label': {'en': "History", 'vi': "Lịch sử"},
             'method': 'pb.records.desk.get_history',
             'effect': {'en': "Lists the changes made from this desk, newest first.",
                        'vi': "Liệt kê các thay đổi đã thực hiện từ bàn này, mới nhất trước."},
             'writes': False},
        ],
        'right_now': 'pb.records.desk.learn_right_now',
        'station': 'records',
        'tasks': ['sc_records'],
        'terms': ['recordsDesk', 'payScheme', 'payData', 'approvalRoute'],
    },
}
