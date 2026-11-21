# -*- coding: utf-8 -*-
"""RECRUIT P8 — every candidate email, in English, Vietnamese and Bahasa
Indonesia, in ONE place.

THE ONE MECHANISM (P8, G-47). Every email a candidate receives is a company
row of `pb.hiring.message.template` (the P2/P5/P6 "Candidate emails" model):
plain words with `{{tokens}}`, one text per language, edited by the talent
lead in Hiring set-up → Emails and languages. The code that sends one names
the KEY and passes the values only it knows (the interview time, the link);
`pb.hiring._mail_candidate` picks the company's row, the candidate's language
and the layout.

WHY NOT `mail.template` (the handover's first idea, recorded as a deviation):
`mail.template.body_html` is `html_translate` on this build — term-based. A
whole Vietnamese body written in the Vietnamese context is mapped term by term
onto the English, and any term without a match OVERWRITES the English with
the Vietnamese words (`fields_textual._String.write`). A per-language editor
on that field would corrupt the English the first time somebody rewrote a
paragraph. `pb.hiring.message.template.subject/body` are plain
`translate=True` (one whole value per language), which is exactly what a
three-tab editor needs.

These texts are DATA seeds (written with `update_field_translations`), not
`.po` entries: a talent lead's edit must survive every upgrade. A language is
written only where the company's row still carries the product's English and
has no text of its own in that language (the P2 rule).
"""

#: The order the Emails screen lists them in, and the plain sentence that
#: says when each one goes. `extra` is the list of details only the sender
#: knows (shown under the editor as "This email can also use").
EMAIL_ORDER = [
    ('received', 'Right after somebody applies on the careers page.',
     []),
    ('phone', 'When a candidate is moved into Recruiter review (an automation '
              'you can switch off).', ['scheduling_link', 'duration']),
    ('assignment', 'When a recruiter sends the assignment from the candidate.',
     ['tasks', 'format', 'deadline', 'submission_link']),
    ('next_round', 'When a recruiter presses "Through to the next round".', []),
    ('interview_invite', 'When an interview is arranged, with a calendar file.',
     ['when', 'duration', 'where', 'video_link']),
    ('interview_tomorrow', 'The day before an interview.',
     ['when', 'where', 'video_link']),
    ('interview_soon', 'Half an hour before an interview.',
     ['when', 'where', 'video_link']),
    ('interview_video', 'When the video link arrives after the invitation went.',
     ['when', 'video_link']),
    ('interview_off', 'When an interview is called off or moved.',
     ['when', 'next_step']),
    ('on_hold', 'When somebody is moved to On hold and "Send the email" is ticked.',
     ['reason', 'update_date']),
    ('cv_reject', 'When somebody is closed at CV reject and "Send the email" is '
                  'ticked.', []),
    ('interview_reject', 'When somebody is closed at Interview reject — by a '
                         'recruiter who ticks "Send the email", or when another '
                         'finalist signs.', []),
    ('docreq_ask', 'When the candidate is asked for their papers.',
     ['deadline', 'link']),
    ('docreq_remind', 'Once a day until the papers are in.',
     ['in_count', 'wanted_count', 'link']),
    ('offer', 'When the offer is sent, with the letter attached.',
     ['start_date', 'monthly', 'yearly', 'link']),
    ('laptop', 'When the new joiner is asked how they want their laptop.',
     ['join_date', 'laptop_link']),
]
EMAIL_KEYS = [k for k, _w, _x in EMAIL_ORDER]
WHEN = {k: w for k, w, _x in EMAIL_ORDER}
EXTRA = {k: x for k, _w, x in EMAIL_ORDER}

#: Every email can use these (filled from the candidate, the role and the
#: company). `first_name` is the FULL name since P3 (RC35).
COMMON_TOKENS = ['name', 'first_name', 'role', 'brand', 'website', 'linkedin',
                 'company_intro', 'sender_name', 'hr_name']
#: Allowed to be empty without stopping the email.
OPTIONAL_TOKENS = {'website', 'linkedin', 'company_intro', 'video_link', 'link'}

#: The words a person sees for each detail in the editor's token chips.
TOKEN_WORDS = {
    'name': 'their full name', 'first_name': 'their name (older emails)',
    'role': 'the role', 'brand': 'your company name', 'website': 'your website',
    'linkedin': 'your LinkedIn page', 'company_intro': 'your short introduction',
    'sender_name': 'who signs it', 'hr_name': 'the recruiter',
    'scheduling_link': 'the recruiter’s scheduling link', 'duration': 'minutes',
    'tasks': 'the tasks', 'format': 'how to hand it in', 'deadline': 'the date',
    'submission_link': 'where to send it', 'when': 'the date and time',
    'where': 'the place or the video link', 'video_link': 'the video link',
    'next_step': 'what happens next', 'reason': 'the reason',
    'update_date': 'the date of the next update', 'link': 'their own page',
    'in_count': 'how many are in', 'wanted_count': 'how many were asked for',
    'start_date': 'the start date', 'monthly': 'pay a month', 'yearly': 'pay a year',
    'join_date': 'the joining date', 'laptop_link': 'their laptop page',
}

#: The NEW candidate emails P8 adds (the old English-only mail templates they
#: replace are archived by the 19.0.2.7.0 migration). English is the product
#: text; `button` is the label of the button under the words, drawn only
#: when the sender passes a `link` (or `video_link`).
NEW_EMAILS = {
    'interview_invite': {
        'name': 'Your interview is arranged',
        'subject': 'Your interview for {{role}}',
        'button': 'Join the video call',
        'body': ("Hi {{name}},\n\nThank you for your interest in {{role}}. We would "
                 "like to meet you.\n\nWhen: {{when}}\nHow long: {{duration}} minutes\n"
                 "Where: {{where}}\n\nA calendar file is attached - open it and the time "
                 "goes straight into your own diary.\n\nIf that time does not work, reply "
                 "to this email and say so. Moving it is easy, and far better than not "
                 "coming.\n\n{{brand}}"),
    },
    'interview_tomorrow': {
        'name': 'Your interview is tomorrow',
        'subject': 'Tomorrow: your interview for {{role}}',
        'button': 'Join the video call',
        'body': ("Hi {{name}},\n\nA reminder that your interview for {{role}} is "
                 "tomorrow, {{when}}.\n\nWhere: {{where}}\n\nIf something has changed, "
                 "tell us today rather than tomorrow - just reply to this email.\n\n"
                 "{{brand}}"),
    },
    'interview_soon': {
        'name': 'Your interview is in half an hour',
        'subject': 'In half an hour: your interview for {{role}}',
        'button': 'Join the video call',
        'body': ("Hi {{name}},\n\nYour interview for {{role}} starts {{when}}.\n\n"
                 "Where: {{where}}\n\nWe look forward to meeting you.\n\n{{brand}}"),
    },
    'interview_video': {
        'name': 'Your video link',
        'subject': 'Your video link - {{role}}',
        'button': 'Join the video call',
        'body': ("Hi {{name}},\n\nHere is the link for your interview on {{when}} "
                 "({{role}}). An updated calendar file is attached.\n\n{{brand}}"),
    },
    'interview_off': {
        'name': 'Your interview has changed',
        'subject': 'A change to your interview for {{role}}',
        'button': '',
        'body': ("Hi {{name}},\n\nThe interview on {{when}} for {{role}} is not going "
                 "ahead as planned. Please take it out of your diary.\n\n{{next_step}}\n\n"
                 "{{brand}}"),
    },
    'next_round': {
        'name': 'Through to the next round',
        'subject': 'Good news about {{role}}',
        'button': '',
        'body': ("Hi {{name}},\n\nThank you for the time you have given us so far. We "
                 "would like to take your application for {{role}} to the next stage.\n\n"
                 "Somebody will be in touch shortly to arrange it. If there are days or "
                 "times that are difficult for you, reply and say so - it is much easier "
                 "to work around than to undo.\n\n{{brand}}"),
    },
    'interview_reject': {
        'name': 'Not this time, after an interview',
        'subject': 'About your application for {{role}}',
        'button': '',
        'body': ("Hi {{name}},\n\nThank you for applying for {{role}}, and for the time "
                 "you gave us in our conversations.\n\nWe are not taking your application "
                 "further this time. That is a decision about one role at one moment and "
                 "nothing more - we would be glad to hear from you again.\n\nWe wish you "
                 "well with what comes next.\n\n{{sender_name}}\n{{brand}}"),
    },
    'docreq_ask': {
        'name': 'Please send us a few documents',
        'subject': 'A few documents for {{role}}',
        'button': 'Send my documents',
        'body': ("Hi {{name}},\n\nGood news - things are moving on {{role}}. Before we "
                 "can put the offer in front of you we need a few documents. The page "
                 "below has the list: you can do the whole thing from your phone, with no "
                 "account and no password.\n\nWe would like them by {{deadline}}. If "
                 "something is going to be hard to find, reply to this email and say so - "
                 "it is almost never a problem, and much better than going quiet.\n\n"
                 "{{brand}}"),
    },
    'docreq_remind': {
        'name': 'Still waiting on a document or two',
        'subject': 'Still waiting on a document or two',
        'button': 'Finish sending my documents',
        'body': ("Hi {{name}},\n\nWe have {{in_count}} of the {{wanted_count}} things "
                 "we asked you for. Your page is still open and it takes a minute.\n\n"
                 "If something is holding you up, just reply to this email.\n\n{{brand}}"),
    },
    'offer': {
        'name': 'Our offer to you',
        'subject': 'Our offer: {{role}}',
        'button': 'Read it and answer',
        'body': ("Hi {{name}},\n\nWe would like you to join us as {{role}}, starting on "
                 "{{start_date}}. The full letter is attached to this email.\n\n"
                 "A month: {{monthly}}\nA year: {{yearly}}\n\nTake your time, and ask us "
                 "anything. If something here is not what you were expecting, we would "
                 "far rather talk about it than lose you over it.\n\n{{brand}}"),
    },
}

#: Vietnamese and Bahasa Indonesia for the NEW emails, by key.
NEW_I18N = {
    'interview_invite': {
        'vi_VN': {
            'subject': 'Lịch phỏng vấn của bạn cho vị trí {{role}}',
            'button': 'Tham gia cuộc gọi video',
            'body': ("Chào {{name}},\n\nCảm ơn bạn đã quan tâm đến vị trí {{role}}. Chúng "
                     "tôi rất muốn được gặp bạn.\n\nThời gian: {{when}}\nThời lượng: "
                     "{{duration}} phút\nĐịa điểm: {{where}}\n\nEmail có kèm tệp lịch - bạn "
                     "chỉ cần mở tệp là lịch hẹn sẽ có ngay trong lịch của bạn.\n\nNếu thời "
                     "gian này không phù hợp, bạn chỉ cần trả lời email này. Đổi lịch rất dễ, "
                     "và tốt hơn nhiều so với việc không đến được.\n\n{{brand}}"),
        },
        'id_ID': {
            'subject': 'Jadwal wawancara Anda untuk posisi {{role}}',
            'button': 'Bergabung ke panggilan video',
            'body': ("Halo {{name}},\n\nTerima kasih atas minat Anda pada posisi {{role}}. "
                     "Kami ingin bertemu dengan Anda.\n\nWaktu: {{when}}\nDurasi: "
                     "{{duration}} menit\nTempat: {{where}}\n\nBerkas kalender terlampir - "
                     "buka berkas itu dan jadwalnya langsung masuk ke kalender Anda.\n\nJika "
                     "waktu tersebut tidak cocok, balas email ini dan beri tahu kami. Mengubah "
                     "jadwal itu mudah, dan jauh lebih baik daripada tidak datang.\n\n"
                     "{{brand}}"),
        },
    },
    'interview_tomorrow': {
        'vi_VN': {
            'subject': 'Ngày mai: buổi phỏng vấn của bạn cho vị trí {{role}}',
            'button': 'Tham gia cuộc gọi video',
            'body': ("Chào {{name}},\n\nXin nhắc bạn rằng buổi phỏng vấn cho vị trí {{role}} "
                     "sẽ diễn ra vào ngày mai, {{when}}.\n\nĐịa điểm: {{where}}\n\nNếu có gì "
                     "thay đổi, hãy báo cho chúng tôi ngay hôm nay - bạn chỉ cần trả lời email "
                     "này.\n\n{{brand}}"),
        },
        'id_ID': {
            'subject': 'Besok: wawancara Anda untuk posisi {{role}}',
            'button': 'Bergabung ke panggilan video',
            'body': ("Halo {{name}},\n\nSekadar mengingatkan, wawancara Anda untuk posisi "
                     "{{role}} dijadwalkan besok, {{when}}.\n\nTempat: {{where}}\n\nJika ada "
                     "perubahan, beri tahu kami hari ini - cukup balas email ini.\n\n"
                     "{{brand}}"),
        },
    },
    'interview_soon': {
        'vi_VN': {
            'subject': 'Còn nửa tiếng nữa: buổi phỏng vấn của bạn cho vị trí {{role}}',
            'button': 'Tham gia cuộc gọi video',
            'body': ("Chào {{name}},\n\nBuổi phỏng vấn của bạn cho vị trí {{role}} sẽ bắt "
                     "đầu {{when}}.\n\nĐịa điểm: {{where}}\n\nChúng tôi rất mong được gặp "
                     "bạn.\n\n{{brand}}"),
        },
        'id_ID': {
            'subject': 'Setengah jam lagi: wawancara Anda untuk posisi {{role}}',
            'button': 'Bergabung ke panggilan video',
            'body': ("Halo {{name}},\n\nWawancara Anda untuk posisi {{role}} dimulai "
                     "{{when}}.\n\nTempat: {{where}}\n\nKami menantikan pertemuan dengan "
                     "Anda.\n\n{{brand}}"),
        },
    },
    'interview_video': {
        'vi_VN': {
            'subject': 'Đường dẫn cuộc gọi video của bạn - {{role}}',
            'button': 'Tham gia cuộc gọi video',
            'body': ("Chào {{name}},\n\nĐây là đường dẫn cho buổi phỏng vấn của bạn vào "
                     "{{when}} ({{role}}). Tệp lịch đã cập nhật được đính kèm.\n\n{{brand}}"),
        },
        'id_ID': {
            'subject': 'Tautan video Anda - {{role}}',
            'button': 'Bergabung ke panggilan video',
            'body': ("Halo {{name}},\n\nBerikut tautan untuk wawancara Anda pada {{when}} "
                     "({{role}}). Berkas kalender terbaru terlampir.\n\n{{brand}}"),
        },
    },
    'interview_off': {
        'vi_VN': {
            'subject': 'Thay đổi về buổi phỏng vấn của bạn cho vị trí {{role}}',
            'button': '',
            'body': ("Chào {{name}},\n\nBuổi phỏng vấn vào {{when}} cho vị trí {{role}} sẽ "
                     "không diễn ra như dự kiến. Bạn vui lòng xóa lịch hẹn này khỏi lịch của "
                     "mình.\n\n{{next_step}}\n\n{{brand}}"),
        },
        'id_ID': {
            'subject': 'Perubahan wawancara Anda untuk posisi {{role}}',
            'button': '',
            'body': ("Halo {{name}},\n\nWawancara pada {{when}} untuk posisi {{role}} tidak "
                     "jadi berlangsung sesuai rencana. Mohon hapus jadwal ini dari kalender "
                     "Anda.\n\n{{next_step}}\n\n{{brand}}"),
        },
    },
    'next_round': {
        'vi_VN': {
            'subject': 'Tin vui về vị trí {{role}}',
            'button': '',
            'body': ("Chào {{name}},\n\nCảm ơn bạn đã dành thời gian cho chúng tôi trong "
                     "thời gian qua. Chúng tôi muốn đưa hồ sơ của bạn cho vị trí {{role}} "
                     "sang vòng tiếp theo.\n\nChúng tôi sẽ sớm liên hệ để sắp xếp. Nếu có ngày "
                     "hoặc giờ nào không thuận tiện, hãy trả lời email này - sắp xếp từ đầu "
                     "bao giờ cũng dễ hơn phải thay đổi sau.\n\n{{brand}}"),
        },
        'id_ID': {
            'subject': 'Kabar baik tentang posisi {{role}}',
            'button': '',
            'body': ("Halo {{name}},\n\nTerima kasih atas waktu yang telah Anda berikan "
                     "sejauh ini. Kami ingin membawa lamaran Anda untuk posisi {{role}} ke "
                     "tahap berikutnya.\n\nKami akan segera menghubungi Anda untuk "
                     "mengaturnya. Jika ada hari atau jam yang sulit bagi Anda, balas email "
                     "ini dan beri tahu kami - jauh lebih mudah menyesuaikan dari awal "
                     "daripada mengubahnya nanti.\n\n{{brand}}"),
        },
    },
    'interview_reject': {
        'vi_VN': {
            'subject': 'Về hồ sơ ứng tuyển của bạn cho vị trí {{role}}',
            'button': '',
            'body': ("Chào {{name}},\n\nCảm ơn bạn đã ứng tuyển vị trí {{role}} và đã dành "
                     "thời gian trò chuyện cùng chúng tôi.\n\nLần này chúng tôi sẽ không tiếp "
                     "tục với hồ sơ của bạn. Đây chỉ là quyết định cho một vị trí vào một thời "
                     "điểm, không hơn - chúng tôi rất vui nếu được nghe tin từ bạn một lần "
                     "nữa.\n\nChúc bạn mọi điều tốt đẹp trên chặng đường sắp tới.\n\n"
                     "{{sender_name}}\n{{brand}}"),
        },
        'id_ID': {
            'subject': 'Tentang lamaran Anda untuk posisi {{role}}',
            'button': '',
            'body': ("Halo {{name}},\n\nTerima kasih telah melamar posisi {{role}} dan atas "
                     "waktu yang Anda berikan dalam percakapan kita.\n\nKali ini kami tidak "
                     "melanjutkan lamaran Anda. Ini keputusan untuk satu posisi pada satu "
                     "waktu, tidak lebih - kami akan senang mendengar kabar dari Anda lagi.\n\n"
                     "Semoga sukses untuk langkah Anda berikutnya.\n\n{{sender_name}}\n"
                     "{{brand}}"),
        },
    },
    'docreq_ask': {
        'vi_VN': {
            'subject': 'Một vài giấy tờ cho vị trí {{role}}',
            'button': 'Gửi giấy tờ của tôi',
            'body': ("Chào {{name}},\n\nTin vui - mọi việc cho vị trí {{role}} đang tiến "
                     "triển. Trước khi gửi thư mời nhận việc, chúng tôi cần một vài giấy tờ. "
                     "Trang bên dưới có danh sách đầy đủ: bạn có thể làm tất cả trên điện "
                     "thoại, không cần tài khoản hay mật khẩu.\n\nChúng tôi mong nhận được "
                     "trước {{deadline}}. Nếu có giấy tờ nào khó tìm, hãy trả lời email này - "
                     "hầu như không bao giờ là vấn đề, và tốt hơn nhiều so với im lặng.\n\n"
                     "{{brand}}"),
        },
        'id_ID': {
            'subject': 'Beberapa dokumen untuk posisi {{role}}',
            'button': 'Kirim dokumen saya',
            'body': ("Halo {{name}},\n\nKabar baik - proses untuk posisi {{role}} terus "
                     "berjalan. Sebelum kami menyampaikan penawaran, kami memerlukan beberapa "
                     "dokumen. Halaman di bawah berisi daftarnya: Anda bisa menyelesaikan "
                     "semuanya dari ponsel, tanpa akun dan tanpa kata sandi.\n\nKami harap "
                     "dokumen sudah kami terima paling lambat {{deadline}}. Jika ada yang sulit "
                     "ditemukan, balas email ini dan beri tahu kami - hampir tidak pernah "
                     "menjadi masalah, dan jauh lebih baik daripada tidak memberi kabar.\n\n"
                     "{{brand}}"),
        },
    },
    'docreq_remind': {
        'vi_VN': {
            'subject': 'Chúng tôi vẫn đang chờ một vài giấy tờ',
            'button': 'Gửi nốt giấy tờ',
            'body': ("Chào {{name}},\n\nChúng tôi đã nhận được {{in_count}} trên "
                     "{{wanted_count}} giấy tờ đã yêu cầu. Trang của bạn vẫn đang mở và chỉ "
                     "mất một phút.\n\nNếu có điều gì khiến bạn chưa gửi được, bạn chỉ cần "
                     "trả lời email này.\n\n{{brand}}"),
        },
        'id_ID': {
            'subject': 'Kami masih menunggu satu atau dua dokumen',
            'button': 'Selesaikan pengiriman dokumen',
            'body': ("Halo {{name}},\n\nKami sudah menerima {{in_count}} dari "
                     "{{wanted_count}} dokumen yang kami minta. Halaman Anda masih terbuka dan "
                     "hanya butuh satu menit.\n\nJika ada yang menghambat, cukup balas email "
                     "ini.\n\n{{brand}}"),
        },
    },
    'offer': {
        'vi_VN': {
            'subject': 'Thư mời nhận việc: {{role}}',
            'button': 'Xem và trả lời',
            'body': ("Chào {{name}},\n\nChúng tôi rất mong bạn gia nhập với vị trí {{role}}, "
                     "bắt đầu từ {{start_date}}. Thư mời đầy đủ được đính kèm trong email "
                     "này.\n\nMỗi tháng: {{monthly}}\nMỗi năm: {{yearly}}\n\nBạn cứ thong "
                     "thả, và hãy hỏi chúng tôi bất cứ điều gì. Nếu có điểm nào chưa đúng như "
                     "bạn mong đợi, chúng tôi rất muốn được trao đổi thay vì để lỡ mất bạn."
                     "\n\n{{brand}}"),
        },
        'id_ID': {
            'subject': 'Penawaran kami: {{role}}',
            'button': 'Baca dan beri jawaban',
            'body': ("Halo {{name}},\n\nKami ingin Anda bergabung bersama kami sebagai "
                     "{{role}}, mulai {{start_date}}. Surat penawaran lengkap terlampir di "
                     "email ini.\n\nPer bulan: {{monthly}}\nPer tahun: {{yearly}}\n\nSilakan "
                     "luangkan waktu, dan tanyakan apa saja kepada kami. Jika ada hal yang "
                     "tidak sesuai harapan Anda, kami jauh lebih memilih membicarakannya "
                     "daripada kehilangan Anda.\n\n{{brand}}"),
        },
    },
}

#: Vietnamese and Bahasa Indonesia for the three P0 emails that only ever had
#: English (assignment, on hold, CV reject). Keyed by key; written only where
#: the company's row still carries exactly the product's English (read from
#: `data/journey_content.json`, so a reworded row is never touched).
OLD_I18N = {
    'assignment': {
        'vi_VN': {
            'subject': 'Một bài tập ngắn cho vị trí {{role}}',
            'body': ("Chào {{first_name}},\n\nCảm ơn bạn vì cuộc trò chuyện rất thú vị. Bước "
                     "tiếp theo là một bài tập ngắn - giúp bạn hình dung những vấn đề chúng tôi "
                     "đang giải quyết, và giúp chúng tôi hiểu cách bạn suy nghĩ.\n\nĐây là "
                     "những nội dung chúng tôi mong bạn thực hiện:\n{{tasks}}\n{{format}}\n\n"
                     "Chúng tôi không cần bạn dành hàng giờ trau chuốt hay một bài làm hoàn "
                     "hảo. Chúng tôi quan tâm đến cách bạn tư duy hơn nhiều so với hình thức."
                     "\n\nVui lòng gửi bài trước {{deadline}}. Nếu có việc đột xuất và bạn cần "
                     "thêm thời gian, cứ báo cho chúng tôi - chúng tôi muốn bạn làm tốt nhất "
                     "thay vì phải vội vàng.\n\nHãy gửi bài làm tới {{submission_link}}, và "
                     "nếu có gì chưa rõ, bạn cứ trả lời email này.\n\nChúc bạn may mắn,\n"
                     "{{sender_name}}\n{{website}} | {{linkedin}}"),
        },
        'id_ID': {
            'subject': 'Tugas singkat untuk posisi {{role}}',
            'body': ("Halo {{first_name}},\n\nTerima kasih atas percakapan yang menyenangkan. "
                     "Langkah berikutnya adalah tugas singkat - memberi Anda gambaran tentang "
                     "masalah yang kami tangani, dan memberi kami gambaran tentang cara Anda "
                     "berpikir.\n\nBerikut hal-hal yang kami harap Anda kerjakan:\n{{tasks}}\n"
                     "{{format}}\n\nKami tidak mengharapkan berjam-jam merapikan hasil atau "
                     "hasil yang sempurna. Kami jauh lebih peduli pada cara berpikir Anda "
                     "daripada tampilan yang sempurna.\n\nMohon kirimkan paling lambat "
                     "{{deadline}}. Jika ada halangan dan Anda butuh waktu lebih, beri tahu "
                     "kami saja - kami lebih senang Anda mengerjakan yang terbaik daripada "
                     "terburu-buru.\n\nKirimkan hasil Anda ke {{submission_link}}, dan jika "
                     "ada yang kurang jelas, balas email ini.\n\nSemoga berhasil,\n"
                     "{{sender_name}}\n{{website}} | {{linkedin}}"),
        },
    },
    'on_hold': {
        'vi_VN': {
            'subject': 'Cập nhật nhanh và thẳng thắn về hồ sơ của bạn',
            'body': ("Chào {{first_name}},\n\nTôi muốn liên lạc với bạn thay vì để bạn phải "
                     "chờ đợi mà không biết gì. Chúng tôi vẫn đang cân nhắc quyết định cho vị "
                     "trí {{role}}, và việc này mất nhiều thời gian hơn chúng tôi mong muốn — "
                     "{{reason}}.\n\nTôi không muốn vội vàng với một quyết định quan trọng, "
                     "nhưng cũng không muốn bạn phải chờ trong im lặng. Hiện tại: hồ sơ của "
                     "bạn vẫn đang được xem xét tích cực, và tôi dự kiến sẽ có thông tin rõ "
                     "ràng hơn cho bạn trước {{update_date}}.\n\nNếu trong thời gian này hoàn "
                     "cảnh của bạn thay đổi — có một lời mời khác, hay thời gian của bạn thay "
                     "đổi — hãy cho tôi biết. Tôi sẽ cố gắng đẩy nhanh mọi việc từ phía chúng "
                     "tôi để bạn không phải chờ đợi một cách không công bằng.\n\nCảm ơn bạn đã "
                     "kiên nhẫn, và xin lỗi vì đã để bạn chờ.\n\nTrân trọng,\n{{sender_name}}\n"
                     "{{brand}}"),
        },
        'id_ID': {
            'subject': 'Kabar singkat dan jujur tentang lamaran Anda',
            'body': ("Halo {{first_name}},\n\nSaya ingin menghubungi Anda daripada membiarkan "
                     "Anda bertanya-tanya. Kami masih mempertimbangkan keputusan untuk posisi "
                     "{{role}}, dan prosesnya memakan waktu sedikit lebih lama dari yang kami "
                     "harapkan — {{reason}}.\n\nSaya tidak ingin terburu-buru dalam keputusan "
                     "yang penting, dan saya juga tidak ingin Anda menunggu tanpa kabar. Posisi "
                     "saat ini: lamaran Anda masih sangat aktif, dan saya berharap dapat "
                     "memberi kabar yang lebih jelas paling lambat {{update_date}}.\n\nJika "
                     "situasi Anda berubah sementara itu — ada tawaran lain, atau perubahan "
                     "waktu — mohon beri tahu saya. Saya akan berusaha mempercepat proses dari "
                     "pihak kami agar Anda tidak menunggu terlalu lama.\n\nTerima kasih atas "
                     "kesabaran Anda, dan mohon maaf atas penantiannya.\n\nSalam,\n"
                     "{{sender_name}}\n{{brand}}"),
        },
    },
    'cv_reject': {
        'vi_VN': {
            'subject': 'Hồ sơ ứng tuyển của bạn tại {{brand}}',
            'body': ("Chào {{first_name}},\n\nCảm ơn bạn đã dành thời gian ứng tuyển vị trí "
                     "{{role}} và quan tâm đến những gì chúng tôi đang xây dựng tại {{brand}}."
                     "\n\nSau khi xem xét hồ sơ, chúng tôi quyết định lần này sẽ không tiếp tục "
                     "với hồ sơ của bạn. Những quyết định như vậy hiếm khi rõ ràng trắng đen, "
                     "và đây không phải là đánh giá về năng lực của bạn — thường là do kinh "
                     "nghiệm chưa thật sự khớp với những gì vị trí này cần ở thời điểm hiện "
                     "tại.\n\nChúng tôi thật lòng mong bạn sẽ ứng tuyển lại cho những vị trí "
                     "phù hợp trong tương lai. Một lần nữa cảm ơn sự quan tâm của bạn, và chúc "
                     "bạn thành công trên chặng đường phía trước.\n\nThân mến,\n"
                     "{{sender_name}}"),
        },
        'id_ID': {
            'subject': 'Lamaran Anda di {{brand}}',
            'body': ("Halo {{first_name}},\n\nTerima kasih telah meluangkan waktu untuk "
                     "melamar posisi {{role}}, dan atas minat Anda pada apa yang kami bangun di "
                     "{{brand}}.\n\nSetelah meninjau lamaran Anda, kami memutuskan untuk tidak "
                     "melanjutkannya kali ini. Keputusan seperti ini jarang hitam-putih, dan "
                     "ini bukan penilaian atas kemampuan Anda — biasanya ini soal seberapa "
                     "dekat pengalaman Anda dengan kebutuhan posisi ini saat ini.\n\nKami "
                     "dengan senang hati menyambut Anda untuk melamar lagi pada posisi yang "
                     "sesuai di kemudian hari. Sekali lagi terima kasih atas minat Anda, dan "
                     "kami doakan sukses selalu.\n\nSalam hangat,\n{{sender_name}}"),
        },
    },
}

#: Words the CODE puts into an email (a place nobody typed, what happens
#: next), in the email's own language so a Vietnamese email never carries an
#: English sentence in the middle.
WORDS = {
    'en_US': {
        'where_later': 'We will confirm the place separately.',
        'video': 'On a video call: %s',
        'moved': 'It has moved to %s. A fresh invitation is on its way, with a calendar file.',
        'later': 'We will be in touch about a new time.',
        'paste': 'Or paste this into your browser:',
        'test': '[Test] ',
    },
    'vi_VN': {
        'where_later': 'Chúng tôi sẽ xác nhận địa điểm riêng.',
        'video': 'Gọi video: %s',
        'moved': 'Buổi phỏng vấn đã được dời sang %s. Thư mời mới kèm tệp lịch đang được gửi tới bạn.',
        'later': 'Chúng tôi sẽ liên hệ lại với bạn về thời gian mới.',
        'paste': 'Hoặc dán đường dẫn này vào trình duyệt:',
        'test': '[Thử] ',
    },
    'id_ID': {
        'where_later': 'Kami akan mengonfirmasi tempatnya secara terpisah.',
        'video': 'Panggilan video: %s',
        'moved': 'Wawancara dipindahkan ke %s. Undangan baru beserta berkas kalender sedang dikirim.',
        'later': 'Kami akan menghubungi Anda untuk waktu yang baru.',
        'paste': 'Atau tempel tautan ini di browser Anda:',
        'test': '[Uji] ',
    },
}

#: The sample values "Send me a test" and the editor's preview use.
SAMPLE = {
    'scheduling_link': 'https://calendly.com/your-recruiter/30min',
    'duration': '30', 'tasks': '1. A one-page plan for your first month.',
    'format': 'A PDF or a link is fine.', 'deadline': 'Friday 10 October',
    'submission_link': 'talent@example.com', 'when': 'Tuesday 7 October, 10:00 (Ho Chi Minh)',
    'where': 'Floor 5, 12 Nguyen Hue, District 1', 'video_link': '',
    'next_step': 'We will be in touch about a new time.', 'reason': 'the hiring manager is travelling',
    'update_date': 'Friday 17 October', 'link': 'https://example.com/your-own-page',
    'in_count': '2', 'wanted_count': '4', 'start_date': 'Monday 3 November',
    'monthly': '30,000,000 ₫', 'yearly': '390,000,000 ₫', 'join_date': 'Monday 3 November',
    'laptop_link': 'https://example.com/your-laptop-page',
}
