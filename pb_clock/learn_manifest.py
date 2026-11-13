# -*- coding: utf-8 -*-
"""CLOCK-3 — screen manifest for Workforce › Time › Time clocks.

Read by pb_learn's guide; never imported by this module. Plain data only.
Every block on this screen is worked out per call by `pb.clock.lens` (and the
Attention strip by the 15-minute watcher, `pb.clock.alert`), so every entry is
`derived` from the code that produces it and checked by the truth gate. Every
sentence in English and Vietnamese, plain words, never the brand name.
"""

_XML = 'pb_clock/static/src/xml/clock_lens.xml'
_JS = 'pb_clock/static/src/js/clock_lens.js'
_PY = 'pb_clock/models/clock_lens.py'
_ALERT = 'pb_clock/models/clock_alert.py'


def _f(key, en, vi, ref, how, if_changed, anchor='wf-clocks'):
    return {'key': key, 'derived': True, 'column': {'en': en, 'vi': vi},
            'from': ref, 'how': how, 'if_changed': if_changed, 'anchor': anchor}


MANIFESTS = {
    'wfclocks': {
        'model': None,
        'templates': [_XML, _JS],
        'purpose': {
            'en': "See the attendance machines and their punches, and fix what a "
                  "person must: a machine that went quiet, a clock that is off, a "
                  "number that matches nobody, a day missing a check-out.",
            'vi': "Xem các máy chấm công và lượt chấm của chúng, và xử lý những gì "
                  "cần người làm: một máy im lặng, đồng hồ máy bị lệch, một số chưa "
                  "khớp với ai, một ngày thiếu giờ ra.",
        },
        'path': {'tag': 'pb_workforce', 'lens': 'time'},
        'before': [
            {'screen': 'wftime',
             'why': {'en': "Time clocks is a tab of Time; its days show in the Week Grid.",
                     'vi': "Máy chấm công là một tab của Chấm công; các ngày của nó "
                           "hiện trong Lưới tuần."}},
        ],
        'after': [
            {'screen': 'wfclose',
             'why': {'en': "Once the machines' days are right, close the week so "
                           "payroll can use it.",
                     'vi': "Khi các ngày từ máy đã đúng, hãy chốt tuần để bảng lương "
                           "sử dụng."}},
        ],
        'fields': [
            _f('attention', "Attention", "Cần chú ý", _ALERT + ':_items',
               {'en': "One plain sentence per problem, with the door that fixes it: "
                      "a machine that has not called in, a clock that is off, a day "
                      "missing a check-out. Grey when nothing needs attention.",
                'vi': "Mỗi vấn đề một câu, kèm nút mở đúng chỗ cần sửa: một máy chưa "
                      "liên lạc, đồng hồ máy bị lệch, một ngày thiếu giờ ra. Màu xám "
                      "khi không có gì cần chú ý."},
               {'en': "Checked every 15 minutes; each line clears by itself once the "
                      "problem is gone. A manager can mute a line for a week.",
                'vi': "Được kiểm tra mỗi 15 phút; mỗi dòng tự biến mất khi vấn đề "
                      "không còn. Quản lý có thể tắt một dòng trong một tuần."},
               anchor='wf-clocks-attn'),
            _f('unknown', "Numbers that match nobody", "Mã chưa khớp với ai",
               _PY + ':_unknown',
               {'en': "Numbers a machine sent that no person has as clock number, "
                      "badge ID or ID number, with how many punches each one has.",
                'vi': "Các số máy gửi về mà không ai có làm mã chấm công, mã thẻ hay "
                      "số giấy tờ, kèm số lượt chấm của mỗi số."},
               {'en': "Assigning a number to a person pairs everything it punched.",
                'vi': "Gán một số cho một người sẽ ghép mọi lượt chấm của số đó."}),
            _f('held', "Punches on hold", "Lượt chấm công tạm giữ", _PY + ':_held',
               {'en': "Punches that were not applied because a person already decided "
                      "about that day: it is closed, under approval, corrected or "
                      "typed in by hand.",
                'vi': "Các lượt chấm chưa được áp dụng vì đã có người quyết định về "
                      "ngày đó: ngày đã chốt, đang chờ duyệt, đã chỉnh sửa hoặc được "
                      "nhập tay."},
               {'en': "Fix this day opens a correction; nothing is changed until it "
                      "is approved.",
                'vi': "Sửa ngày này mở một đề nghị chỉnh sửa; không có gì thay đổi "
                      "cho tới khi được duyệt."}),
            _f('missing', "Days missing a check-out", "Ngày thiếu giờ ra",
               _PY + ':_missing_checkout',
               {'en': "Someone punched in and not again until a later day. That day "
                      "was closed at its check-in, 0 hours, so the later days count.",
                'vi': "Một người chấm vào rồi không chấm lại cho tới một ngày sau. Ngày "
                      "đó được đóng tại giờ vào, 0 giờ, để các ngày sau được tính."},
               {'en': "Fix it with a correction before the week is closed.",
                'vi': "Hãy sửa bằng một đề nghị chỉnh sửa trước khi chốt tuần."}),
            _f('machines', "Machines", "Các máy", _PY + ':_devices',
               {'en': "One card per machine: connected or silent since when, punches "
                      "today, whether its clock is right, and history still arriving.",
                'vi': "Mỗi máy một thẻ: đang kết nối hay im lặng từ lúc nào, lượt chấm "
                      "hôm nay, đồng hồ máy có đúng không, và dữ liệu cũ còn đang gửi về."},
               {'en': "A manager can resend a machine's punches or ignore a machine "
                      "from its card.",
                'vi': "Quản lý có thể yêu cầu máy gửi lại lượt chấm hoặc bỏ qua một máy "
                      "từ thẻ của nó."},
               anchor='wf-clocks-machines'),
        ],
        'actions': [],
        'right_now': None,
        'tasks': ['sc_wfclocks'],
        'terms': [],
    },
}
