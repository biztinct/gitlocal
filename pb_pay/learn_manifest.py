# -*- coding: utf-8 -*-
"""LEARNREV P5 — screen manifest for People › Pay › Pay review and Pay changes.

Read by pb_learn's guide; never imported by this module. Plain data only.
The meters, the blockers and the buttons are worked out per call
(`pb.pay.reviews`), so each entry is `derived` from the function that
produces it. Every sentence in English and Vietnamese.
"""

_XML = 'pb_pay/static/src/xml/pay_review.xml'
_PY = 'pb_pay/models/pb_pay_reviews.py'

MANIFESTS = {
    'payreview': {
        'model': None,
        'templates': [_XML],
        'purpose': {
            'en': "Run the yearly pay review inside a budget, calibrate it, and "
                  "take it through approval; single pay changes sit beside it.",
            'vi': "Chạy đợt xét lương hằng năm trong một ngân sách, cân chỉnh, rồi "
                  "đưa đi phê duyệt; các thay đổi lương lẻ nằm cạnh đó.",
        },
        'path': {'tag': 'pb_people_hub', 'lens': 'pay'},
        'before': [
            {'screen': 'paybands',
             'why': {'en': "Set the pay bands first; the review checks pay against them.",
                     'vi': "Đặt các dải lương trước; đợt xét lương đối chiếu lương "
                           "với chúng."}},
        ],
        'after': [
            {'screen': 'approvals',
             'why': {'en': "Each approval step decides in the one approvals inbox.",
                     'vi': "Mỗi bước phê duyệt được quyết định trong hộp phê duyệt "
                           "duy nhất."}},
        ],
        'fields': [
            {
                'key': 'budget', 'derived': True,
                'column': {'en': "Budget", 'vi': "Ngân sách"},
                'from': _PY + ':_card',
                'how': {
                    'en': "What the proposed rises add up to, against the budget set "
                          "for the review. The bar turns over when it passes it.",
                    'vi': "Tổng các mức tăng được đề xuất, so với ngân sách đã đặt "
                          "cho đợt xét lương. Thanh chuyển sang vượt khi quá mức.",
                },
                'if_changed': {
                    'en': "Read-only. It moves as you change rises on the rows; "
                          "passing the budget is listed under What stops approval.",
                    'vi': "Chỉ xem. Nó thay đổi khi bạn đổi mức tăng ở các dòng; "
                          "việc vượt ngân sách được liệt kê trong Điều gì chặn duyệt.",
                },
                'anchor': 'pp-meters',
            },
            {
                'key': 'fairness', 'derived': True,
                'column': {'en': "Fairness", 'vi': "Công bằng"},
                'from': _PY + ':open_review',
                'how': {
                    'en': "One sentence on whether the proposed rises treat people "
                          "in the same position alike.",
                    'vi': "Một câu cho biết các mức tăng được đề xuất có đối xử như "
                          "nhau với những người cùng vị trí hay không.",
                },
                'if_changed': {
                    'en': "Read-only. It is worked out again each time you change "
                          "a rise.",
                    'vi': "Chỉ xem. Nó được tính lại mỗi khi bạn đổi một mức tăng.",
                },
                'anchor': 'pp-meters',
            },
            {
                'key': 'blockers', 'derived': True,
                'column': {'en': "What stops approval", 'vi': "Điều gì chặn duyệt"},
                'from': _PY + ':_blockers',
                'how': {
                    'en': "Rows that break a limit, and the budget when it is "
                          "passed. Each is written as a plain sentence.",
                    'vi': "Các dòng vi phạm một giới hạn, và ngân sách khi bị vượt. "
                          "Mỗi mục được viết thành một câu rõ ràng.",
                },
                'if_changed': {
                    'en': "Read-only. Clear every item here before Send for "
                          "approval.",
                    'vi': "Chỉ xem. Hãy xử lý hết các mục ở đây trước khi Gửi duyệt.",
                },
                'anchor': 'pp-stops',
            },
            {
                'key': 'scores', 'derived': True,
                'column': {'en': "Scores", 'vi': "Điểm đánh giá"},
                'from': _PY + ':open_review',
                'how': {
                    'en': "How many people have no performance score yet; for them "
                          "the guidance used the middle.",
                    'vi': "Có bao nhiêu người chưa có điểm đánh giá; với họ, phần "
                          "hướng dẫn đã dùng mức giữa.",
                },
                'if_changed': {
                    'en': "Read-only. Add the scores and the suggested rises are "
                          "worked out again.",
                    'vi': "Chỉ xem. Thêm điểm đánh giá và các mức tăng gợi ý sẽ "
                          "được tính lại.",
                },
                'anchor': 'pp-meters',
            },
        ],
        'actions': [
            {'label': {'en': "New review", 'vi': "Đợt xét lương mới"},
             'method': 'pb.pay.reviews.create_review',
             'effect': {'en': "Starts a review with a suggested rise already on "
                              "every row. Nothing is paid until it is applied.",
                        'vi': "Bắt đầu một đợt xét lương với mức tăng gợi ý sẵn ở "
                              "mọi dòng. Chưa có gì được trả cho đến khi áp dụng."},
             'writes': True},
            {'label': {'en': "Set up guidance", 'vi': "Thiết lập hướng dẫn"},
             'method': 'pb.pay.reviews.make_default_guidance',
             'effect': {'en': "Creates the default table of suggested rises, which "
                              "you can then edit.",
                        'vi': "Tạo bảng mức tăng gợi ý mặc định, sau đó bạn có thể "
                              "chỉnh sửa."},
             'writes': True},
            {'label': {'en': "Send for approval", 'vi': "Gửi duyệt"},
             'method': 'pb.pay.reviews.act',
             'effect': {'en': "Sends the review to HR, the first approval step. "
                              "Clear what stops approval before you press it.",
                        'vi': "Gửi đợt xét lương cho nhân sự, bước phê duyệt đầu "
                              "tiên. Hãy xử lý điều chặn duyệt trước khi bấm."},
             'writes': True},
            {'label': {'en': "Apply", 'vi': "Áp dụng"},
             'method': 'pb.pay.reviews.apply',
             'effect': {'en': "Writes the approved new pay onto the contracts. You "
                              "can take it back for a short time afterwards.",
                        'vi': "Ghi mức lương mới đã duyệt vào các hợp đồng. Sau đó "
                              "bạn có thể lấy lại trong một thời gian ngắn."},
             'writes': True},
            {'label': {'en': "Take it back", 'vi': "Lấy lại"},
             'method': 'pb.pay.reviews.undo',
             'effect': {'en': "Puts the old pay back on the contracts, while the "
                              "time allowed has not run out.",
                        'vi': "Trả mức lương cũ về các hợp đồng, khi thời gian cho "
                              "phép chưa hết."},
             'writes': True},
        ],
        'right_now': None,
        'station': 'payreview',
        'tasks': ['sc_payreview'],
        'terms': ['payReview', 'calibration', 'payBand', 'inTheBand'],
    },
}
