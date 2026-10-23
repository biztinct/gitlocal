# -*- coding: utf-8 -*-
"""The four advert templates every company starts with (RECRUIT P3, G-17).

A template is a STARTING POINT a recruiter edits, by role family. The words in
brackets are the parts they fill in. Candidate-facing, so English, Vietnamese
and Bahasa Indonesia are all seeded (the language a role's advert is read in
is the careers page's); a company's own edits are never overwritten — the
seed only creates a template that is missing.
"""


def _body(about, do, bring, why):
    return ('<h2>%s</h2><p>%s</p><h2>%s</h2><ul>%s</ul><h2>%s</h2><ul>%s</ul>'
            '<h2>%s</h2><p>%s</p>') % (
        about[0], about[1], do[0], ''.join('<li>%s</li>' % x for x in do[1]),
        bring[0], ''.join('<li>%s</li>' % x for x in bring[1]),
        why[0], why[1])


JD_TEMPLATES = [
    {
        'key': 'field', 'family': 'Field',
        'name': {'en_US': 'Field roles', 'vi_VN': 'Vị trí hiện trường',
                 'id_ID': 'Peran lapangan'},
        'body': {
            'en_US': _body(
                ('About the role', 'You will spend most of your week with '
                 'the people we serve, in [the region], making sure [what the '
                 'role delivers].'),
                ('What you will do', ['Visit [who] and keep a clear record of '
                                      'every visit',
                                      'Solve problems on the spot and know '
                                      'when to call for help',
                                      'Report what you see each week to '
                                      '[the team]']),
                ('What you bring', ['[Years] of work in the field',
                                    'A motorbike licence and a smartphone',
                                    'Comfort speaking [the local language]']),
                ('Why join us', '[One sentence about the company and the '
                 'difference this role makes.]')),
            'vi_VN': _body(
                ('Về vị trí này', 'Phần lớn thời gian trong tuần bạn sẽ ở '
                 'cùng những người chúng tôi phục vụ, tại [khu vực], để bảo '
                 'đảm [vị trí này mang lại điều gì].'),
                ('Bạn sẽ làm gì', ['Đến gặp [ai] và ghi chép rõ ràng mỗi lần '
                                   'đến',
                                   'Giải quyết vấn đề tại chỗ và biết khi nào '
                                   'cần hỗ trợ',
                                   'Báo cáo những gì bạn thấy mỗi tuần cho '
                                   '[nhóm]']),
                ('Bạn cần có', ['[Số năm] làm việc hiện trường',
                                'Bằng lái xe máy và điện thoại thông minh',
                                'Tự tin giao tiếp bằng [ngôn ngữ địa phương]']),
                ('Vì sao gia nhập chúng tôi', '[Một câu về công ty và sự '
                 'khác biệt mà vị trí này tạo ra.]')),
            'id_ID': _body(
                ('Tentang peran ini', 'Sebagian besar waktu Anda setiap '
                 'minggu akan bersama orang-orang yang kami layani, di '
                 '[wilayah], memastikan [hasil peran ini].'),
                ('Yang akan Anda kerjakan', ['Mengunjungi [siapa] dan '
                                             'mencatat setiap kunjungan '
                                             'dengan jelas',
                                             'Menyelesaikan masalah di '
                                             'tempat dan tahu kapan harus '
                                             'meminta bantuan',
                                             'Melaporkan temuan setiap '
                                             'minggu kepada [tim]']),
                ('Yang Anda bawa', ['[Jumlah tahun] pengalaman di lapangan',
                                    'SIM sepeda motor dan ponsel pintar',
                                    'Nyaman berbicara dalam [bahasa '
                                    'setempat]']),
                ('Mengapa bergabung', '[Satu kalimat tentang perusahaan dan '
                 'perbedaan yang dibuat peran ini.]')),
        },
    },
    {
        'key': 'sales', 'family': 'Sales',
        'name': {'en_US': 'Sales roles', 'vi_VN': 'Vị trí kinh doanh',
                 'id_ID': 'Peran penjualan'},
        'body': {
            'en_US': _body(
                ('About the role', 'You will own [the territory or the '
                 'customers] and grow [what you sell] there.'),
                ('What you will do', ['Build and keep relationships with '
                                      '[customers]',
                                      'Plan your month and hit [the target]',
                                      'Share what customers tell you with '
                                      'the team']),
                ('What you bring', ['[Years] of selling [what]',
                                    'A record you can talk about with numbers',
                                    'Energy for being out and about']),
                ('Why join us', '[One sentence about the company and the '
                 'difference this role makes.]')),
            'vi_VN': _body(
                ('Về vị trí này', 'Bạn sẽ phụ trách [khu vực hoặc khách '
                 'hàng] và phát triển [sản phẩm bạn bán] tại đó.'),
                ('Bạn sẽ làm gì', ['Xây dựng và giữ quan hệ với [khách hàng]',
                                   'Lên kế hoạch hằng tháng và đạt [chỉ '
                                   'tiêu]',
                                   'Chia sẻ với đội những gì khách hàng nói']),
                ('Bạn cần có', ['[Số năm] kinh nghiệm bán [sản phẩm]',
                                'Thành tích có thể nói bằng con số',
                                'Năng lượng cho công việc di chuyển nhiều']),
                ('Vì sao gia nhập chúng tôi', '[Một câu về công ty và sự '
                 'khác biệt mà vị trí này tạo ra.]')),
            'id_ID': _body(
                ('Tentang peran ini', 'Anda akan bertanggung jawab atas '
                 '[wilayah atau pelanggan] dan mengembangkan [apa yang Anda '
                 'jual] di sana.'),
                ('Yang akan Anda kerjakan', ['Membangun dan menjaga hubungan '
                                             'dengan [pelanggan]',
                                             'Merencanakan bulan Anda dan '
                                             'mencapai [target]',
                                             'Berbagi apa yang disampaikan '
                                             'pelanggan dengan tim']),
                ('Yang Anda bawa', ['[Jumlah tahun] pengalaman menjual '
                                    '[apa]',
                                    'Rekam jejak yang dapat Anda jelaskan '
                                    'dengan angka',
                                    'Semangat untuk banyak berada di luar']),
                ('Mengapa bergabung', '[Satu kalimat tentang perusahaan dan '
                 'perbedaan yang dibuat peran ini.]')),
        },
    },
    {
        'key': 'tech', 'family': 'Tech',
        'name': {'en_US': 'Tech roles', 'vi_VN': 'Vị trí công nghệ',
                 'id_ID': 'Peran teknologi'},
        'body': {
            'en_US': _body(
                ('About the role', 'You will build [what] with a small team '
                 'that ships every week.'),
                ('What you will do', ['Design, build and look after [the '
                                      'system]',
                                      'Review your colleagues\' work and ask '
                                      'for reviews of yours',
                                      'Talk to the people who use what you '
                                      'build']),
                ('What you bring', ['[Years] with [the technologies]',
                                    'Examples of work you are proud of',
                                    'Clear writing in English']),
                ('Why join us', '[One sentence about the company and the '
                 'difference this role makes.]')),
            'vi_VN': _body(
                ('Về vị trí này', 'Bạn sẽ xây dựng [sản phẩm] cùng một nhóm '
                 'nhỏ ra mắt tính năng mỗi tuần.'),
                ('Bạn sẽ làm gì', ['Thiết kế, xây dựng và chăm sóc [hệ '
                                   'thống]',
                                   'Xem xét công việc của đồng nghiệp và nhờ '
                                   'họ xem lại việc của bạn',
                                   'Trao đổi với người dùng sản phẩm bạn làm']),
                ('Bạn cần có', ['[Số năm] làm việc với [công nghệ]',
                                'Những sản phẩm bạn tự hào',
                                'Viết tiếng Anh rõ ràng']),
                ('Vì sao gia nhập chúng tôi', '[Một câu về công ty và sự '
                 'khác biệt mà vị trí này tạo ra.]')),
            'id_ID': _body(
                ('Tentang peran ini', 'Anda akan membangun [apa] bersama tim '
                 'kecil yang merilis setiap minggu.'),
                ('Yang akan Anda kerjakan', ['Merancang, membangun, dan '
                                             'merawat [sistem]',
                                             'Meninjau pekerjaan rekan dan '
                                             'meminta tinjauan atas pekerjaan '
                                             'Anda',
                                             'Berbicara dengan orang yang '
                                             'memakai apa yang Anda bangun']),
                ('Yang Anda bawa', ['[Jumlah tahun] dengan [teknologi]',
                                    'Contoh karya yang Anda banggakan',
                                    'Tulisan bahasa Inggris yang jelas']),
                ('Mengapa bergabung', '[Satu kalimat tentang perusahaan dan '
                 'perbedaan yang dibuat peran ini.]')),
        },
    },
    {
        'key': 'finance', 'family': 'Finance',
        'name': {'en_US': 'Finance roles', 'vi_VN': 'Vị trí tài chính',
                 'id_ID': 'Peran keuangan'},
        'body': {
            'en_US': _body(
                ('About the role', 'You will keep [the numbers] right and '
                 'help the business decide with them.'),
                ('What you will do', ['Close [the month] on time and '
                                      'accurately',
                                      'Prepare the reports [who] relies on',
                                      'Spot what looks wrong before it '
                                      'matters']),
                ('What you bring', ['[Qualification] and [years] in finance',
                                    'Care with detail and deadlines',
                                    'Plain explanations of hard numbers']),
                ('Why join us', '[One sentence about the company and the '
                 'difference this role makes.]')),
            'vi_VN': _body(
                ('Về vị trí này', 'Bạn sẽ giữ [các con số] chính xác và giúp '
                 'doanh nghiệp ra quyết định dựa trên chúng.'),
                ('Bạn sẽ làm gì', ['Khóa sổ [tháng] đúng hạn và chính xác',
                                   'Chuẩn bị các báo cáo mà [ai] cần',
                                   'Phát hiện điều bất thường trước khi nó '
                                   'thành vấn đề']),
                ('Bạn cần có', ['[Bằng cấp] và [số năm] trong tài chính',
                                'Cẩn thận với chi tiết và thời hạn',
                                'Giải thích đơn giản những con số khó']),
                ('Vì sao gia nhập chúng tôi', '[Một câu về công ty và sự '
                 'khác biệt mà vị trí này tạo ra.]')),
            'id_ID': _body(
                ('Tentang peran ini', 'Anda akan menjaga [angka-angka] tetap '
                 'benar dan membantu bisnis mengambil keputusan dengannya.'),
                ('Yang akan Anda kerjakan', ['Menutup [bulan] tepat waktu '
                                             'dan akurat',
                                             'Menyiapkan laporan yang '
                                             'diandalkan [siapa]',
                                             'Melihat yang janggal sebelum '
                                             'menjadi masalah']),
                ('Yang Anda bawa', ['[Kualifikasi] dan [jumlah tahun] di '
                                    'bidang keuangan',
                                    'Teliti terhadap detail dan tenggat',
                                    'Penjelasan sederhana untuk angka yang '
                                    'rumit']),
                ('Mengapa bergabung', '[Satu kalimat tentang perusahaan dan '
                 'perbedaan yang dibuat peran ini.]')),
        },
    },
]
