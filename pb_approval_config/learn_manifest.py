# -*- coding: utf-8 -*-
"""LEARNREV P1 — screen manifest for Home › Approvals (the one inbox).

Read by pb_learn's guide; never imported by this module. Plain data only.
Labels, help texts and choice labels come from the request's own fields
(`biz.approval.request`, `fields_get()`); what is written here is purpose, how
a value is filled, who reads it (file:function, checked by the truth gate) and
what changing it does — every sentence in English and Vietnamese.
"""

_INBOX = 'pb_approval_config/static/src/xml/inbox.xml'
_INBOX_JS = 'pb_approval_config/static/src/js/inbox.js'
_DRAWER_JS = 'pb_approval_config/static/src/js/request_drawer.js'
_FACADE = 'pb_approval_config/models/inbox_facade.py'

MANIFESTS = {
    'approvals': {
        'model': 'biz.approval.request',
        'templates': [_INBOX, _INBOX_JS, _DRAWER_JS],
        'purpose': {
            'en': "Decide everything that is waiting for a sign-off, pay runs "
                  "included, each with the route it travels.",
            'vi': "Quyết định mọi thứ đang chờ phê duyệt, kể cả đợt lương, mỗi yêu "
                  "cầu kèm lộ trình nó đi qua.",
        },
        'path': {'tag': 'pb_home_hub', 'lens': 'approvals'},
        'before': [
            {'screen': 'payruns',
             'why': {'en': "A pay run arrives here when someone submits it for "
                           "approval.",
                     'vi': "Một đợt lương đến đây khi có người gửi nó đi phê duyệt."}},
        ],
        'after': [
            {'screen': 'payruns',
             'why': {'en': "An approved run moves to Done on the Runs board, ready "
                           "to pay.",
                     'vi': "Đợt lương đã duyệt chuyển sang Hoàn tất trên bảng Các đợt "
                           "lương, sẵn sàng chi trả."}},
        ],
        'fields': [
            {
                'key': 'state', 'field': 'state',
                'column': {'en': "Waiting for a decision", 'vi': "Đang chờ quyết định"},
                'filled_by': {
                    'en': "Moved by the approval route: sent in, waiting at each step, "
                          "then approved and carried out, or sent back, turned down or "
                          "withdrawn.",
                    'vi': "Được lộ trình phê duyệt chuyển: được gửi, chờ ở từng bước, "
                          "rồi được duyệt và thực hiện, hoặc bị trả lại, bị từ chối hay "
                          "bị thu hồi.",
                },
                'choices_when': {
                    'returned': {
                        'en': "Back with the person who sent it in, with a note on what "
                              "to change. A pay run is a draft again.",
                        'vi': "Trả về người đã gửi, kèm ghi chú cần thay đổi gì. Một đợt "
                              "lương trở lại thành bản nháp."},
                    'rejected': {
                        'en': "Ended for good. A pay run is Rejected.",
                        'vi': "Kết thúc hẳn. Một đợt lương bị Từ chối."},
                    'blocked': {
                        'en': "The route cannot move until a step is set up; the request "
                              "says what is missing.",
                        'vi': "Lộ trình không thể đi tiếp cho tới khi một bước được thiết "
                              "lập; yêu cầu cho biết còn thiếu gì."},
                },
                'used_by': [
                    {'label': {'en': "\"Waiting on you\" on the Runs board",
                               'vi': "\"Đang chờ bạn\" trên bảng Các đợt lương"},
                     'ref': 'pb_payruns/models/hr_payslip_run.py:_pb_runs_awaiting'},
                    {'label': {'en': "Where a run's approval has got to, on its card",
                               'vi': "Việc phê duyệt một đợt lương đã đến đâu, trên thẻ "
                                     "của nó"},
                     'ref': 'pb_payruns/models/pb_payruns.py:_approval_chip_data'},
                    {'label': {'en': "The run's own approval status",
                               'vi': "Trạng thái phê duyệt của chính đợt lương"},
                     'ref': 'biz_approval_workflow/models/adapter.py:_compute_approval'},
                    {'label': {'en': "The route shown after Compute",
                               'vi': "Lộ trình hiện ra sau khi Tính lương"},
                     'ref': 'pb_payrun_wizard/models/pb_payrun_wizard.py:_batch_route'},
                ],
                'if_changed': {
                    'en': "Read-only: it moves when someone decides, sends it back or "
                          "withdraws it.",
                    'vi': "Chỉ xem: nó thay đổi khi có người quyết định, trả lại hoặc "
                          "thu hồi.",
                },
                'anchor': 'ai-card',
            },
            {
                'key': 'sent_in_by', 'field': 'submitter_uid',
                'column': {'en': "sent in by", 'vi': "người gửi"},
                'filled_by': {
                    'en': "Whoever sent the request in; on a pay run, the person who "
                          "pressed Submit for approval.",
                    'vi': "Người đã gửi yêu cầu; với một đợt lương, đó là người đã bấm "
                          "Gửi để phê duyệt.",
                },
                'used_by': [
                    {'label': {'en': "Who sent a run in, named on Home",
                               'vi': "Ai đã gửi đợt lương, được nêu trên Trang chủ"},
                     'ref': 'pb_dashboard/models/home_data.py:_home_submitter'},
                    {'label': {'en': "The approval trail on the record",
                               'vi': "Dấu vết phê duyệt trên hồ sơ"},
                     'ref': 'biz_approval_workflow/models/chain_shim.py:_chain_trail'},
                ],
                'if_changed': {
                    'en': "Read-only. Whoever sent it in can withdraw it while it waits.",
                    'vi': "Chỉ xem. Người đã gửi có thể thu hồi khi yêu cầu còn đang chờ.",
                },
                'anchor': 'ai-card',
            },
            {
                'key': 'due', 'field': 'due_at',
                'column': {'en': "Due", 'vi': "Hạn"},
                'filled_by': {
                    'en': "Copied from the current step's deadline, when the workflow "
                          "gives the step one.",
                    'vi': "Được chép từ hạn của bước hiện tại, khi luồng phê duyệt đặt "
                          "hạn cho bước đó.",
                },
                'used_by': [
                    {'label': {'en': "Reminders sent before and after the deadline",
                               'vi': "Lời nhắc gửi trước và sau hạn"},
                     'ref': 'biz_approval_workflow/models/outbox.py:_deliver'},
                ],
                'if_changed': {
                    'en': "Read-only here. Deadlines are set per step in the workflow.",
                    'vi': "Chỉ xem ở đây. Hạn được đặt cho từng bước trong luồng phê "
                          "duyệt.",
                },
                'anchor': 'ai-card',
            },
            {
                'key': 'facts', 'field': 'facts',
                'column': {'en': "The facts, as they were when it was sent in",
                           'vi': "Các dữ kiện, đúng như lúc yêu cầu được gửi đi"},
                'filled_by': {
                    'en': "Frozen when the request is sent in. For a pay run: net, "
                          "gross, payslips, people, the change against the last run and "
                          "whether it holds overtime.",
                    'vi': "Được giữ nguyên từ lúc yêu cầu được gửi. Với một đợt lương: "
                          "thực nhận, tổng thu nhập, số phiếu lương, số người, mức thay "
                          "đổi so với đợt trước và có tăng ca hay không.",
                },
                'used_by': [
                    {'label': {'en': "The facts in the open request",
                               'vi': "Các dữ kiện trong yêu cầu đang mở"},
                     'ref': _FACADE + ':_facts'},
                ],
                'if_changed': {
                    'en': "Never changes. If the pay run's figures move after it is sent "
                          "in, the approval no longer covers them and cannot be carried "
                          "out.",
                    'vi': "Không bao giờ thay đổi. Nếu số liệu của đợt lương thay đổi sau "
                          "khi gửi, phê duyệt không còn áp dụng và không thể thực hiện.",
                },
                'anchor': 'ai-facts',
            },
            {
                'key': 'waiting_for', 'derived': True,
                'column': {'en': "Waiting for", 'vi': "Đang chờ"},
                'from': _FACADE + ':_card',
                'how': {
                    'en': "The people who can decide the current step, or who is "
                          "standing in for them.",
                    'vi': "Những người có thể quyết định bước hiện tại, hoặc người đang "
                          "làm thay họ.",
                },
                'if_changed': {
                    'en': "Read-only. Whoever looks after the workflow can move it to "
                          "somebody else.",
                    'vi': "Chỉ xem. Người phụ trách luồng phê duyệt có thể chuyển nó cho "
                          "người khác.",
                },
                'anchor': 'ai-card',
            },
            {
                'key': 'route', 'derived': True,
                'column': {'en': "The route", 'vi': "Lộ trình"},
                'from': _FACADE + ':_card',
                'values': {
                    'done': {'en': "Decided", 'vi': "Đã quyết định"},
                    'current': {'en': "Waiting for a decision", 'vi': "Đang chờ quyết định"},
                    'next': {'en': "Not started", 'vi': "Chưa bắt đầu"},
                    'skipped': {'en': "Not needed", 'vi': "Không cần"},
                    'bad': {'en': "Sent back or turned down", 'vi': "Bị trả lại hoặc từ chối"},
                },
                'how': {
                    'en': "One dot per step of the workflow the request was sent in "
                          "under, in order.",
                    'vi': "Mỗi bước của luồng phê duyệt mà yêu cầu được gửi theo là một "
                          "chấm, theo thứ tự.",
                },
                'if_changed': {
                    'en': "Read-only. A changed workflow applies to requests sent in "
                          "after the change.",
                    'vi': "Chỉ xem. Luồng phê duyệt đã đổi áp dụng cho các yêu cầu được "
                          "gửi sau khi đổi.",
                },
                'anchor': 'ai-route',
            },
        ],
        'actions': [
            {'label': {'en': "Approve", 'vi': "Phê duyệt"},
             'method': 'pb.approval.inbox.decide',
             'effect': {'en': "Records your approval; the request moves to its next "
                              "step, or is carried out after the last one.",
                        'vi': "Ghi nhận phê duyệt của bạn; yêu cầu chuyển sang bước "
                              "tiếp theo, hoặc được thực hiện sau bước cuối."},
             'writes': True},
            {'label': {'en': "Send it back", 'vi': "Trả lại"},
             'method': 'pb.approval.inbox.decide',
             'effect': {'en': "Returns it with your note on what to change. A pay run "
                              "is a draft again.",
                        'vi': "Trả lại kèm ghi chú của bạn về điều cần thay đổi. Một đợt "
                              "lương trở lại thành bản nháp."},
             'writes': True},
            {'label': {'en': "Turn it down", 'vi': "Từ chối"},
             'method': 'pb.approval.inbox.decide',
             'effect': {'en': "Ends the request for good. A pay run is Rejected.",
                        'vi': "Kết thúc hẳn yêu cầu. Một đợt lương bị Từ chối."},
             'writes': True},
            {'label': {'en': "Move it to somebody else", 'vi': "Chuyển cho người khác"},
             'method': 'pb.approval.inbox.move_it',
             'effect': {'en': "Hands the current step to another person, with the "
                              "reason.",
                        'vi': "Giao bước hiện tại cho người khác, kèm lý do."},
             'writes': True},
            {'label': {'en': "Withdraw it", 'vi': "Thu hồi"},
             'method': 'pb.approval.inbox.cancel',
             'effect': {'en': "Takes the request back while it waits. A pay run returns "
                              "to Draft.",
                        'vi': "Lấy lại yêu cầu khi nó còn đang chờ. Một đợt lương trở về "
                              "Nháp."},
             'writes': True},
        ],
        'right_now': None,
        'station': 'approvals',
        'tasks': [],
        'terms': ['inbox', 'approvalRoute', 'routeStep', 'sentBack', 'turnedDown',
                  'approvalCover'],
    },
}
