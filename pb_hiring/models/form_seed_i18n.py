# -*- coding: utf-8 -*-
"""RECRUIT P2 — the Vietnamese and Indonesian words for every SEEDED form text.

These are DATA translations (written onto the form records with
`update_field_translations`), not `.po` entries: a talent lead edits them on
the Application forms screen and the next upgrade must never put the product's
words back. The seed writes a language only where the record still carries the
product's English AND has no text of its own in that language.

Keyed by the exact English the seed writes. One place, so a reviewer who reads
Vietnamese or Bahasa can check every candidate-facing seeded word at once.
"""

FORM_I18N = {
    # ---------------------------------------------------------- form names
    'Standard': {'vi_VN': 'Tiêu chuẩn', 'id_ID': 'Standar'},
    'Field roles': {'vi_VN': 'Vị trí làm việc thực địa', 'id_ID': 'Peran lapangan'},
    'Senior roles': {'vi_VN': 'Vị trí cấp cao', 'id_ID': 'Peran senior'},
    'Tech roles': {'vi_VN': 'Vị trí công nghệ', 'id_ID': 'Peran teknologi'},
    # ---------------------------------------------------------- labels
    'Full name': {'vi_VN': 'Họ và tên', 'id_ID': 'Nama lengkap'},
    'Email address': {'vi_VN': 'Địa chỉ email', 'id_ID': 'Alamat email'},
    'Phone number': {'vi_VN': 'Số điện thoại', 'id_ID': 'Nomor telepon'},
    'Country you live in': {'vi_VN': 'Quốc gia bạn đang sống',
                            'id_ID': 'Negara tempat Anda tinggal'},
    'Where are you based right now?': {'vi_VN': 'Hiện tại bạn đang sống ở đâu?',
                                       'id_ID': 'Di mana Anda tinggal saat ini?'},
    'LinkedIn profile': {'vi_VN': 'Hồ sơ LinkedIn', 'id_ID': 'Profil LinkedIn'},
    'CV': {'vi_VN': 'CV', 'id_ID': 'CV'},
    'Portfolio': {'vi_VN': 'Hồ sơ năng lực', 'id_ID': 'Portofolio'},
    'Portfolio (file or link)': {'vi_VN': 'Hồ sơ năng lực (tệp hoặc đường dẫn)',
                                 'id_ID': 'Portofolio (berkas atau tautan)'},
    'Expected monthly pay': {'vi_VN': 'Mức lương mong muốn mỗi tháng',
                             'id_ID': 'Gaji bulanan yang diharapkan'},
    'Are you willing to relocate for this role?': {
        'vi_VN': 'Bạn có sẵn sàng chuyển nơi ở cho vị trí này không?',
        'id_ID': 'Apakah Anda bersedia pindah domisili untuk peran ini?'},
    'Do you have the right to work in this country?': {
        'vi_VN': 'Bạn có quyền làm việc tại quốc gia này không?',
        'id_ID': 'Apakah Anda memiliki izin untuk bekerja di negara ini?'},
    'Why would you like to join us?': {'vi_VN': 'Vì sao bạn muốn gia nhập chúng tôi?',
                                       'id_ID': 'Mengapa Anda ingin bergabung dengan kami?'},
    'Your consent': {'vi_VN': 'Sự đồng ý của bạn', 'id_ID': 'Persetujuan Anda'},
    'Do you hold a driving licence?': {'vi_VN': 'Bạn có bằng lái xe không?',
                                       'id_ID': 'Apakah Anda memiliki SIM?'},
    'Which provinces can you cover?': {'vi_VN': 'Bạn có thể phụ trách những tỉnh nào?',
                                       'id_ID': 'Provinsi mana saja yang dapat Anda jangkau?'},
    'What is your notice period?': {
        'vi_VN': 'Thời gian báo trước khi nghỉ việc của bạn là bao lâu?',
        'id_ID': 'Berapa lama masa pemberitahuan pengunduran diri Anda?'},
    'Link to code you are proud of': {'vi_VN': 'Đường dẫn tới mã nguồn bạn tự hào',
                                      'id_ID': 'Tautan ke kode yang Anda banggakan'},
    # ---------------------------------------------------------- help lines
    'We only call about this application.': {
        'vi_VN': 'Chúng tôi chỉ gọi về hồ sơ ứng tuyển này.',
        'id_ID': 'Kami hanya menelepon terkait lamaran ini.'},
    'A monthly figure before tax. Only the hiring team sees it.': {
        'vi_VN': 'Số tiền mỗi tháng trước thuế. Chỉ đội tuyển dụng nhìn thấy.',
        'id_ID': 'Angka bulanan sebelum pajak. Hanya tim rekrutmen yang melihatnya.'},
    'Upload a file or paste a link.': {'vi_VN': 'Tải tệp lên hoặc dán đường dẫn.',
                                       'id_ID': 'Unggah berkas atau tempel tautan.'},
    'A city or district is enough.': {'vi_VN': 'Chỉ cần thành phố hoặc quận.',
                                      'id_ID': 'Cukup kota atau kecamatan.'},
    'Tell us what draws you to this role and what you would bring.': {
        'vi_VN': 'Hãy cho chúng tôi biết điều gì thu hút bạn đến vị trí này và bạn sẽ mang lại điều gì.',
        'id_ID': 'Ceritakan apa yang menarik Anda ke peran ini dan apa yang akan Anda bawa.'},
    'For example: one month, or available now.': {
        'vi_VN': 'Ví dụ: một tháng, hoặc có thể bắt đầu ngay.',
        'id_ID': 'Misalnya: satu bulan, atau bisa mulai sekarang.'},
    'A repository, a project or anything you built.': {
        'vi_VN': 'Một kho mã, một dự án hoặc bất cứ thứ gì bạn đã xây dựng.',
        'id_ID': 'Repositori, proyek, atau apa pun yang Anda bangun.'},
    'List the provinces or cities you could travel to regularly.': {
        'vi_VN': 'Liệt kê các tỉnh hoặc thành phố bạn có thể đi lại thường xuyên.',
        'id_ID': 'Sebutkan provinsi atau kota yang dapat Anda kunjungi secara rutin.'},
    # ---------------------------------------------------------- placeholders
    'https://www.linkedin.com/in/your-name': {
        'vi_VN': 'https://www.linkedin.com/in/ten-cua-ban',
        'id_ID': 'https://www.linkedin.com/in/nama-anda'},
    'https://': {'vi_VN': 'https://', 'id_ID': 'https://'},
    # ---------------------------------------------------------- options
    'Yes\nNo\nIt depends on the role and terms': {
        'vi_VN': 'Có\nKhông\nTùy vào vị trí và điều kiện',
        'id_ID': 'Ya\nTidak\nTergantung peran dan ketentuannya'},
    ('Yes, I have a valid work permit or visa\nYes, I am a citizen or permanent '
     'resident\nNo, I would need visa sponsorship\nI am not sure'): {
        'vi_VN': ('Có, tôi có giấy phép lao động hoặc thị thực hợp lệ\nCó, tôi là '
                  'công dân hoặc thường trú nhân\nKhông, tôi cần được bảo lãnh thị '
                  'thực\nTôi không chắc'),
        'id_ID': ('Ya, saya memiliki izin kerja atau visa yang berlaku\nYa, saya '
                  'warga negara atau penduduk tetap\nTidak, saya memerlukan sponsor '
                  'visa\nSaya tidak yakin')},
    # ---------------------------------------------------------- consent
    ('I agree that {brand} keeps my application for {months} months to consider '
     'me for this and similar roles.'): {
        'vi_VN': ('Tôi đồng ý để {brand} lưu hồ sơ ứng tuyển của tôi trong {months} '
                  'tháng để xem xét cho vị trí này và các vị trí tương tự.'),
        'id_ID': ('Saya setuju {brand} menyimpan lamaran saya selama {months} bulan '
                  'untuk mempertimbangkan saya untuk peran ini dan peran serupa.')},
}

#: The "Application received" email, keyed by the English the product seeds
#: (`data/journey_content.json`). Written only where a company's template
#: still carries exactly that English and has no text of its own.
RECEIVED_I18N = {
    'subject': {
        "We got your application - here's what happens next": {
            'vi_VN': 'Chúng tôi đã nhận được hồ sơ của bạn - đây là những gì sẽ diễn ra tiếp theo',
            'id_ID': 'Lamaran Anda sudah kami terima - ini langkah selanjutnya',
        },
    },
    'body': {
        ("Hi {{first_name}},\n\nThanks for applying for the {{role}} role at {{brand}}. "
         "Your application landed with us, and a real person (not a black hole) will be "
         "reading it.\n\nWe take about two weeks to go through applications properly, so "
         "you'll hear from us within that time either way. If two weeks pass and you "
         "haven't, feel free to nudge us.\n\n{{company_intro}}\n\nTalk soon.\nTalent Team\n"
         "{{website}} | {{linkedin}}"): {
            'vi_VN': ("Chào {{first_name}},\n\nCảm ơn bạn đã ứng tuyển vị trí {{role}} tại "
                      "{{brand}}. Hồ sơ của bạn đã đến tay chúng tôi, và sẽ có một người thật "
                      "đọc nó.\n\nChúng tôi cần khoảng hai tuần để xem xét hồ sơ một cách kỹ "
                      "lưỡng, vì vậy bạn sẽ nhận được phản hồi trong thời gian đó dù kết quả "
                      "thế nào. Nếu đã qua hai tuần mà bạn chưa nhận được tin, hãy nhắc chúng "
                      "tôi nhé.\n\n{{company_intro}}\n\nHẹn sớm gặp lại.\nĐội ngũ Tuyển dụng\n"
                      "{{website}} | {{linkedin}}"),
            'id_ID': ("Halo {{first_name}},\n\nTerima kasih telah melamar untuk peran {{role}} "
                      "di {{brand}}. Lamaran Anda sudah sampai kepada kami, dan akan dibaca oleh "
                      "orang sungguhan.\n\nKami membutuhkan sekitar dua minggu untuk meninjau "
                      "lamaran dengan baik, jadi Anda akan mendapat kabar dari kami dalam waktu "
                      "tersebut, apa pun hasilnya. Jika dua minggu berlalu dan Anda belum "
                      "mendengar kabar, silakan ingatkan kami.\n\n{{company_intro}}\n\nSampai "
                      "jumpa.\nTim Rekrutmen\n{{website}} | {{linkedin}}"),
        },
    },
}


#: RECRUIT P5 — the "Let's chat" email (key `phone`), sent automatically when
#: a candidate moves into Recruiter review, in the language they applied in.
#: Same rule as the received email: written only where a company's template
#: still carries exactly the product's English and has no text of its own.
PHONE_I18N = {
    'subject': {
        "Let's chat — {{role}} at {{brand}}": {
            'vi_VN': 'Cùng trò chuyện nhé — {{role}} tại {{brand}}',
            'id_ID': 'Mari mengobrol — {{role}} di {{brand}}',
        },
    },
    'body': {
        ("Hi {{first_name}},\n\nGood news - we liked what we saw, and we'd love to get to "
         "know you a bit better.\n\nThe next step is a relaxed conversation with {{hr_name}} "
         "from our team. Nothing to prepare, no trick questions. It's really just a chance for "
         "us to hear about you and what you're after, and for you to ask us anything - the "
         "role, the team, what we're building, all of it.\n\nIt'll take about {{duration}} "
         "minutes. Grab a time that works for you here: {{scheduling_link}}.\n\nLooking "
         "forward to it,\n{{sender_name}}\n{{website}} | {{linkedin}}"): {
            'vi_VN': ("Chào {{first_name}},\n\nTin vui - chúng tôi rất ấn tượng với hồ sơ của "
                      "bạn và muốn hiểu thêm về bạn.\n\nBước tiếp theo là một cuộc trò chuyện "
                      "thoải mái với {{hr_name}} từ đội ngũ của chúng tôi. Bạn không cần chuẩn bị "
                      "gì, cũng không có câu hỏi đánh đố nào. Đây chỉ là dịp để chúng tôi lắng "
                      "nghe về bạn và điều bạn đang tìm kiếm, và để bạn hỏi chúng tôi bất cứ điều "
                      "gì - về vị trí, đội ngũ, những gì chúng tôi đang xây dựng.\n\nCuộc trò "
                      "chuyện mất khoảng {{duration}} phút. Hãy chọn thời gian phù hợp với bạn "
                      "tại đây: {{scheduling_link}}.\n\nRất mong được trò chuyện cùng bạn,\n"
                      "{{sender_name}}\n{{website}} | {{linkedin}}"),
            'id_ID': ("Halo {{first_name}},\n\nKabar baik - kami menyukai apa yang kami lihat, "
                      "dan kami ingin mengenal Anda lebih jauh.\n\nLangkah berikutnya adalah "
                      "obrolan santai dengan {{hr_name}} dari tim kami. Tidak ada yang perlu "
                      "disiapkan, tidak ada pertanyaan jebakan. Ini hanya kesempatan bagi kami "
                      "untuk mendengar tentang Anda dan apa yang Anda cari, dan bagi Anda untuk "
                      "menanyakan apa saja - tentang peran ini, timnya, apa yang sedang kami "
                      "bangun, semuanya.\n\nObrolan ini sekitar {{duration}} menit. Pilih "
                      "waktu yang cocok untuk Anda di sini: {{scheduling_link}}.\n\nSampai "
                      "jumpa,\n{{sender_name}}\n{{website}} | {{linkedin}}"),
        },
    },
}


# ==========================================================================
#  RECRUIT P6 — the new joiner's laptop email (G-56), the P5 "Let's chat"
#  pattern: a company email in Candidate emails, one text per language,
#  seeded only where the company still carries the product's English.
# ==========================================================================
LAPTOP_EMAIL = {
    'name': 'Before you join: your laptop',
    'key': 'laptop',
    'subject': 'Your laptop for {{role}} at {{brand}}',
    'body': ("Hi {{first_name}},\n\nWe are getting ready for your first day on "
             "{{join_date}}. So your laptop is set up the way you like it, tell us "
             "what you prefer - it takes about a minute: {{laptop_link}}\n\n"
             "Nothing here is a test, and \"no preference\" is a perfectly good "
             "answer.\n\nSee you soon,\n{{sender_name}}"),
}

LAPTOP_I18N = {
    'subject': {
        'Your laptop for {{role}} at {{brand}}': {
            'vi_VN': 'Máy tính xách tay của bạn cho vị trí {{role}} tại {{brand}}',
            'id_ID': 'Laptop Anda untuk posisi {{role}} di {{brand}}',
        },
    },
    'body': {
        LAPTOP_EMAIL['body']: {
            'vi_VN': ("Chào {{first_name}},\n\nChúng tôi đang chuẩn bị cho ngày làm việc "
                      "đầu tiên của bạn vào {{join_date}}. Để máy tính của bạn được cài đặt "
                      "theo đúng ý bạn, hãy cho chúng tôi biết lựa chọn của bạn - chỉ mất "
                      "khoảng một phút: {{laptop_link}}\n\nĐây không phải là bài kiểm tra, "
                      "và \"không có yêu cầu riêng\" cũng là một câu trả lời hoàn toàn "
                      "hợp lệ.\n\nHẹn sớm gặp bạn,\n{{sender_name}}"),
            'id_ID': ("Halo {{first_name}},\n\nKami sedang bersiap untuk hari pertama Anda "
                      "pada {{join_date}}. Agar laptop Anda disiapkan sesuai keinginan, "
                      "beri tahu kami pilihan Anda - hanya sekitar satu menit: "
                      "{{laptop_link}}\n\nIni bukan ujian, dan \"tidak ada preferensi\" "
                      "adalah jawaban yang sepenuhnya baik.\n\nSampai jumpa,\n"
                      "{{sender_name}}"),
        },
    },
}
