# -*- coding: utf-8 -*-
"""Vietnamese for the role catalogue (LEARN REFRESH step 6, item 5).

THE WORDS ARE STORED, SO A .po CANNOT REACH THEM. A role's `name` and
`description` (`pb.role.profile`, `pb.role.ability`) are `translate=True`
fields: each row keeps a jsonb of `{lang: text}`, filled when the row is
created. `hooks.CATALOGUE` / `NEW_ABILITIES` are plain Python data, never
extracted, so every seeded row carries `en_US` only and a Vietnamese reader of
the Access screen sees English (LR38).

`apply_catalogue_vi` writes the `vi_VN` value for every seeded row, keyed by
the row's ENGLISH text. It is idempotent and it never overwrites somebody's
own words:

  * a row whose English is not a catalogue sentence (renamed by an
    administrator, or made by hand) is left alone;
  * a row that already carries a Vietnamese value different from its English
    (somebody translated it themselves) is left alone;
  * a database without Vietnamese installed is left alone.

`ensure_catalogue` calls it at the end, so a role seeded tomorrow gets its
Vietnamese the same moment; the 19.0.1.9.1 migration runs it once for the rows
already there.
"""
import logging

_logger = logging.getLogger(__name__)

LANG = 'vi_VN'

#: English (exactly as `hooks.py` writes it) -> Vietnamese.
VI = {
    # ------------------------------------------------------------- payroll
    "Payroll — can look": "Lương — chỉ xem",
    "Open pay runs and payslips and read them. Changes nothing, approves nothing, and cannot export bank files.":
        "Mở đợt lương và phiếu lương để xem. Không thay đổi gì, không duyệt gì và không xuất được tệp ngân hàng.",
    "Payroll officer": "Nhân viên tính lương",
    "Prepare a pay run: bring the pay data in, compute it, fix what is wrong and send it up for approval. Cannot approve their own work.":
        "Chuẩn bị đợt lương: đưa dữ liệu lương vào, tính lương, sửa chỗ sai và gửi lên để duyệt. Không tự duyệt được việc của mình.",
    "Payroll manager": "Quản lý lương",
    "Everything an officer does, plus approving a run and changing how pay is calculated. This is the role that decides what people are paid.":
        "Mọi việc của nhân viên tính lương, cộng thêm duyệt đợt lương và thay đổi cách tính lương. Đây là vai trò quyết định mỗi người được trả bao nhiêu.",
    "Payroll approver — final": "Người phê duyệt lương — cấp cuối",
    "The last signature before money moves. Nobody with this role should also be the person who prepared the run.":
        "Chữ ký cuối cùng trước khi tiền được chuyển. Người giữ vai trò này không nên là người đã chuẩn bị đợt lương.",
    "Payroll administrator": "Quản trị lương",
    "Every payroll screen in every country this system runs, including the ones that change the rules themselves. Give it to very few people.":
        "Mọi màn hình lương ở mọi quốc gia hệ thống đang chạy, kể cả những màn hình thay đổi chính các quy tắc. Chỉ giao cho rất ít người.",
    "Pay reporting — can look": "Báo cáo lương — chỉ xem",
    "Read the pay reports and the cost explorer. Sees totals and trends, never edits a payslip.":
        "Xem các báo cáo lương và màn hình phân tích chi phí. Thấy tổng số và xu hướng, không bao giờ sửa phiếu lương.",
    "Pay formulas — can look": "Công thức lương — chỉ xem",
    "Open a pay formula and see exactly how a number on a payslip was worked out. Changes no formula and computes nothing.":
        "Mở một công thức lương và xem chính xác một con số trên phiếu lương được tính ra như thế nào. Không sửa công thức nào và không tính gì.",
    "Pay formula builder": "Người xây dựng công thức lương",
    "Write and change the formulas that calculate pay, and test them against real figures before they go anywhere near a pay run.":
        "Viết và sửa các công thức tính lương, rồi thử chúng với số liệu thật trước khi đưa vào bất kỳ đợt lương nào.",
    "Formula engine administrator": "Quản trị bộ máy công thức",
    "Everything a formula builder does, plus the settings the formulas themselves run on and the connected systems they read from.":
        "Mọi việc của người xây dựng công thức, cộng thêm các thiết lập mà công thức dựa vào và các hệ thống được kết nối mà công thức đọc dữ liệu.",

    # ------------------------------------------------------------ lifecycle
    "Joiners and leavers — can look": "Nhân viên vào và nghỉ — chỉ xem",
    "Follow somebody's joining or leaving checklist and see where it has got to. Cannot start one or close a step somebody else owns.":
        "Theo dõi danh sách việc khi một người vào làm hoặc nghỉ việc và xem đã đến bước nào. Không bắt đầu danh sách mới và không đóng bước của người khác.",
    "HR lifecycle team": "Nhóm nhân sự vào – nghỉ",
    "Run joining and leaving: start a checklist, chase the steps, send the letters, and see every supplier on the vendor register.":
        "Lo việc vào làm và nghỉ việc: bắt đầu danh sách việc, nhắc các bước, gửi thư và xem mọi nhà cung cấp trong danh sách nhà cung cấp.",
    "HR lifecycle administrator": "Quản trị nhân sự vào – nghỉ",
    "Everything the lifecycle team does, plus writing the checklists and the letter templates everybody else then uses.":
        "Mọi việc của nhóm vào – nghỉ, cộng thêm soạn các danh sách việc và mẫu thư mà mọi người khác dùng.",
    "Recruiter": "Chuyên viên tuyển dụng",
    "See every hiring request in the company, screen candidates, and write and publish adverts. Does not agree a request or change the hiring rules.":
        "Xem mọi yêu cầu tuyển dụng trong công ty, sàng lọc ứng viên, viết và đăng tin tuyển dụng. Không duyệt yêu cầu và không thay đổi quy tắc tuyển dụng.",
    "Hiring manager": "Quản lý tuyển dụng",
    "Everything a recruiter does, plus agreeing a hiring request and an advert, closing a role and marking one filled.":
        "Mọi việc của chuyên viên tuyển dụng, cộng thêm duyệt yêu cầu tuyển dụng và tin tuyển dụng, đóng vị trí và đánh dấu vị trí đã tuyển đủ.",
    "Head of hiring": "Trưởng bộ phận tuyển dụng",
    "Everything a hiring manager does, plus the hiring rules — who recruits for which company and country — and the hiring switches.":
        "Mọi việc của quản lý tuyển dụng, cộng thêm các quy tắc tuyển dụng — ai tuyển cho công ty và quốc gia nào — và các công tắc tuyển dụng.",
    "Company equipment — can look": "Tài sản công ty — chỉ xem",
    "See what has been given to whom — laptops, phones, accounts, passes. Cannot hand anything out or take it back.":
        "Xem ai đang giữ gì — máy tính, điện thoại, tài khoản, thẻ ra vào. Không giao ra hay thu hồi được gì.",
    "Equipment team": "Nhóm tài sản",
    "Add equipment to the register, hand it over, take it back, and deal with requests for it.":
        "Thêm tài sản vào sổ, bàn giao, thu hồi và xử lý các yêu cầu cấp tài sản.",
    "Pay packages and awards": "Gói lương và thưởng",
    "Build somebody's pay package, raise a one-off award and enrol people in benefits. Awards still need a head of pay to approve them.":
        "Lập gói lương cho một người, tạo khoản thưởng một lần và đăng ký phúc lợi cho mọi người. Khoản thưởng vẫn cần trưởng bộ phận lương phê duyệt.",
    "Head of pay — packages and awards": "Trưởng bộ phận lương — gói lương và thưởng",
    "Everything above, plus approving awards and putting them into a pay run. This role decides who gets extra money.":
        "Mọi việc ở trên, cộng thêm phê duyệt khoản thưởng và đưa vào đợt lương. Vai trò này quyết định ai được nhận thêm tiền.",
    "Recognition": "Ghi nhận",
    "Praise a colleague and see the recognition wall. Everybody with a login can be given this one.":
        "Khen ngợi đồng nghiệp và xem bảng ghi nhận. Ai có tài khoản đăng nhập cũng có thể được giao vai trò này.",
    "Recognition lead": "Phụ trách ghi nhận",
    "Run the award cycles, decide what the company values are, and manage the wall.":
        "Điều hành các đợt khen thưởng, quyết định các giá trị của công ty và quản lý bảng ghi nhận.",
    "Goals team": "Nhóm mục tiêu",
    "Read every goal sheet in the company, set the goal year up and write the goal templates. Managers do NOT need this to see their own team.":
        "Xem mọi bảng mục tiêu trong công ty, thiết lập năm mục tiêu và soạn mẫu mục tiêu. Quản lý KHÔNG cần vai trò này để xem nhóm của mình.",
    "HR lead for goals": "Nhân sự phụ trách mục tiêu",
    "Everything the goals team does, plus agreeing and locking a goal sheet, sending one back, setting weights on anybody's, and opening goal sheets for a whole company at once.":
        "Mọi việc của nhóm mục tiêu, cộng thêm duyệt và khóa bảng mục tiêu, gửi trả lại, đặt trọng số cho bảng của bất kỳ ai và mở bảng mục tiêu cho cả công ty cùng lúc.",
    "Head of goals": "Trưởng bộ phận mục tiêu",
    "Everything above, plus the goal switches: whether sheets open for a new joiner, whether people are chased, and how long sign-off has.":
        "Mọi việc ở trên, cộng thêm các công tắc mục tiêu: có mở bảng cho người mới vào hay không, có nhắc mọi người hay không và thời hạn duyệt là bao lâu.",
    "Trainer": "Giảng viên",
    "Write courses, lessons and tests, and put people on a course.":
        "Soạn khóa học, bài học và bài kiểm tra, và xếp người vào khóa học.",
    "Training manager": "Quản lý đào tạo",
    "Everything a trainer does, plus every course and test in the company whoever wrote it, and the results behind them.":
        "Mọi việc của giảng viên, cộng thêm mọi khóa học và bài kiểm tra trong công ty dù ai soạn, cùng với kết quả của chúng.",
    "Head of training": "Trưởng bộ phận đào tạo",
    "Everything above, plus the training switches: whether the course site is open to people who are not staff, and whether a finished course sends an email.":
        "Mọi việc ở trên, cộng thêm các công tắc đào tạo: trang khóa học có mở cho người ngoài công ty hay không, và khi học xong có gửi email hay không.",
    "Announcements officer": "Nhân viên thông báo",
    "Write announcements, put them on the calendar, and read every announcement in the companies you can see.":
        "Soạn thông báo, đưa lên lịch và đọc mọi thông báo trong các công ty bạn được xem.",
    "Head of announcements": "Trưởng bộ phận thông báo",
    "Everything above, plus changing an announcement in its last two days, agreeing one when sign-off is on, and cancelling anybody's.":
        "Mọi việc ở trên, cộng thêm sửa thông báo trong hai ngày cuối, duyệt thông báo khi bật chế độ duyệt và hủy thông báo của bất kỳ ai.",
    "Announcements administrator": "Quản trị thông báo",
    "Everything above, plus the template library, who announcements reach in each company, and whether they are emailed at all.":
        "Mọi việc ở trên, cộng thêm thư viện mẫu, thông báo đến được những ai trong từng công ty và có gửi email hay không.",
    "Where they work": "Nơi họ làm việc",
    "Split a person's month between companies, join two employee records into one person, and choose how a split month is paid.":
        "Chia tháng làm việc của một người giữa các công ty, gộp hai hồ sơ nhân viên thành một người và chọn cách trả lương cho tháng bị chia.",
    "Field staff": "Nhân viên hiện trường",
    "For people who work away from a desk: check in and out with their location and a photo from the Field app on their phone. Nothing else.":
        "Dành cho người làm việc bên ngoài văn phòng: chấm công vào và ra kèm vị trí và ảnh chụp từ ứng dụng Hiện trường trên điện thoại. Không gì khác.",
    "Growth plans — HR": "Kế hoạch phát triển — nhân sự",
    "Open and run somebody's growth plan: the coaching notes, the objectives and the dates. Highly confidential.":
        "Mở và điều hành kế hoạch phát triển của một người: ghi chú kèm cặp, mục tiêu và các mốc ngày. Tuyệt mật.",
    "Growth plans — head of HR": "Kế hoạch phát triển — trưởng phòng nhân sự",
    "Everything above, plus seeing every growth plan in the company and making the final decision on one.":
        "Mọi việc ở trên, cộng thêm xem mọi kế hoạch phát triển trong công ty và đưa ra quyết định cuối cùng.",
    "Budget holder": "Người giữ ngân sách",
    "See the budget of the team you lead — what it was given, what it has spent, and whether that is ahead of the calendar.":
        "Xem ngân sách của nhóm bạn phụ trách — được cấp bao nhiêu, đã chi bao nhiêu và có chi nhanh hơn tiến độ thời gian hay không.",
    "Finance — budgets": "Tài chính — ngân sách",
    "See every budget in the companies you work in and export them. Reads everything; changes nothing.":
        "Xem và xuất mọi ngân sách trong các công ty bạn làm việc. Xem được tất cả, không sửa gì.",
    "Budget team": "Nhóm ngân sách",
    "Everything above, plus uploading a year's budget, entering what HR and the office spent, and re-reading the payroll figures.":
        "Mọi việc ở trên, cộng thêm tải lên ngân sách cả năm, nhập khoản chi của nhân sự và văn phòng, và đọc lại số liệu lương.",
    "Decision Room": "Phòng Quyết định",
    "Open the Decision Room, explore the year ahead and keep your own plans.":
        "Mở Phòng Quyết định, xem trước năm tới và lưu các kế hoạch của riêng bạn.",
    "Decision Room — the numbers": "Phòng Quyết định — các con số",
    "Everything above, plus changing the assumptions behind the picture and removing anybody's plan.":
        "Mọi việc ở trên, cộng thêm thay đổi các giả định đằng sau bức tranh và xóa kế hoạch của bất kỳ ai.",
    "Pay bands — can look": "Khoảng lương — chỉ xem",
    "Look at the pay bands, the health cards and the fairness figures, without the names behind them.":
        "Xem các khoảng lương, thẻ đánh giá tình trạng và số liệu công bằng, không kèm tên người.",
    "Pay bands team": "Nhóm khoảng lương",
    "Write and move pay bands, put jobs in them, import them, and see who is paid least for the same work.":
        "Tạo và điều chỉnh khoảng lương, xếp vị trí công việc vào, nhập từ tệp và xem ai được trả thấp nhất cho cùng một công việc.",
    "Pay review — finance check": "Xét lương — tài chính kiểm tra",
    "The finance step of a pay review: check what it costs and send it on, or send it back.":
        "Bước tài chính của đợt xét lương: kiểm tra chi phí rồi chuyển tiếp hoặc gửi trả lại.",
    "Pay review — final sign-off": "Xét lương — phê duyệt cuối",
    "The last step of a pay review: approve it so the new pay can be applied. This role decides pay rises.":
        "Bước cuối của đợt xét lương: phê duyệt để áp dụng mức lương mới. Vai trò này quyết định việc tăng lương.",
    "Vendor owner": "Người phụ trách nhà cung cấp",
    "See the suppliers you are named as looking after, and be the one told when one of their agreements is about to run out.":
        "Xem các nhà cung cấp bạn được giao phụ trách và là người được báo khi một hợp đồng của họ sắp hết hạn.",
    "Vendor team": "Nhóm nhà cung cấp",
    "Add and change suppliers, record and renew their agreements, and run the renewal check whenever you want to.":
        "Thêm và sửa nhà cung cấp, ghi nhận và gia hạn hợp đồng của họ, và chạy kiểm tra gia hạn bất cứ khi nào bạn muốn.",
    "Access team": "Nhóm phân quyền",
    "Give people roles and take them away, see every hand-over of access in the company, and take any of them back. It never includes the system administrator permission.":
        "Giao và thu hồi vai trò của mọi người, xem mọi lần ủy quyền trong công ty và thu hồi bất kỳ lần nào. Không bao giờ bao gồm quyền quản trị hệ thống.",
    "Set up the group": "Thiết lập tập đoàn",
    "Name the group of companies, choose its companies, its currency and how exchange rates are picked, and build its divisions.":
        "Đặt tên tập đoàn, chọn các công ty thành viên, tiền tệ và cách lấy tỷ giá, và lập các khối trực thuộc.",
    "Government reports": "Báo cáo cơ quan nhà nước",
    "Prepare and download the reports that go to the tax office and social insurance.":
        "Chuẩn bị và tải về các báo cáo nộp cho cơ quan thuế và bảo hiểm xã hội.",

    # ------------------------------------------------------ NEW_ABILITIES
    "Work the payroll desk": "Làm việc tại bàn lương",
    "Open pay runs and payslips on the core payroll screens and work through them day to day. It stops short of approving a run and of changing the rules that calculate pay.":
        "Mở đợt lương và phiếu lương trên các màn hình lương chính và xử lý hằng ngày. Không bao gồm duyệt đợt lương và thay đổi quy tắc tính lương.",
    "Manage the payroll desk": "Quản lý bàn lương",
    "Run the core payroll screens end to end: approve a run, reopen one that is wrong, and change the rules that calculate pay. It carries nothing outside pay itself.":
        "Điều hành các màn hình lương chính từ đầu đến cuối: duyệt đợt lương, mở lại đợt bị sai và thay đổi quy tắc tính lương. Không có quyền gì ngoài phần lương.",
    "Manage pay reporting": "Quản lý báo cáo lương",
    "Build, change and export the pay reports everybody else reads. It reads payslips; it never edits one and it never approves a run.":
        "Lập, sửa và xuất các báo cáo lương mà mọi người khác xem. Được xem phiếu lương; không bao giờ sửa phiếu lương và không bao giờ duyệt đợt lương.",
    "Run connected-system syncs": "Chạy đồng bộ với hệ thống được kết nối",
    "Start the syncs that bring people and pay data in from a connected system, and watch how they went. It moves data; it approves nothing and pays nobody.":
        "Bắt đầu đồng bộ để đưa dữ liệu nhân sự và lương từ hệ thống được kết nối vào, và theo dõi kết quả. Chỉ chuyển dữ liệu; không duyệt gì và không trả lương cho ai.",
    "Open pay formulas and read them": "Mở và xem công thức lương",
    "Open a pay formula and see exactly how a number on a payslip was worked out. Changes nothing.":
        "Mở một công thức lương và xem chính xác một con số trên phiếu lương được tính ra như thế nào. Không thay đổi gì.",
    "Build and change pay formulas": "Xây dựng và sửa công thức lương",
    "Write and change the formulas that calculate pay, and test them against a real run before anybody is paid by them. It does not approve the run.":
        "Viết và sửa các công thức tính lương, và thử với một đợt lương thật trước khi dùng để trả lương cho ai. Không duyệt đợt lương.",
    "Administer the formula engine": "Quản trị bộ máy công thức",
    "Everything above, plus the settings the formulas themselves run on and the tools that repair a broken one. Give it to very few people.":
        "Mọi việc ở trên, cộng thêm các thiết lập mà công thức dựa vào và các công cụ sửa công thức bị lỗi. Chỉ giao cho rất ít người.",
    "Work time and attendance": "Xử lý chấm công",
    "See and correct people's clock-in and clock-out records. It cannot change the working-hours rules those records are judged against.":
        "Xem và sửa dữ liệu giờ vào, giờ ra của mọi người. Không thay đổi được quy tắc giờ làm dùng để đối chiếu các dữ liệu đó.",
    "Manage time and attendance": "Quản lý chấm công",
    "Everything above, plus setting the working-hours rules and signing the month off so payroll can use it.":
        "Mọi việc ở trên, cộng thêm đặt quy tắc giờ làm và chốt dữ liệu tháng để bộ phận lương sử dụng.",
    "See workforce plans": "Xem kế hoạch nhân sự",
    "Read the headcount plans and what they would cost. Adds nothing to a plan and approves nothing.":
        "Xem kế hoạch định biên và chi phí dự kiến. Không thêm gì vào kế hoạch và không duyệt gì.",
    "Plan and approve the workforce": "Lập và duyệt kế hoạch nhân sự",
    "Build the headcount plans, put a request forward and approve one. This is what decides how many people a team may hire.":
        "Lập kế hoạch định biên, gửi đề xuất và phê duyệt đề xuất. Đây là quyền quyết định một nhóm được tuyển bao nhiêu người.",
    "Read the audit trail": "Xem nhật ký thay đổi",
    "Read the record of who changed what, and when, across the whole system. Reads only — the trail itself can never be edited or deleted by anybody.":
        "Xem ai đã thay đổi gì và vào lúc nào trên toàn hệ thống. Chỉ xem — không ai có thể sửa hay xóa nhật ký này.",
    "Correct this company's own details": "Sửa thông tin của công ty này",
    "Change the name, address, contact details, tax and registration numbers and logo that print on payslips, filings and letters. It is one company — this one — and nothing else about it: not the currency, not where it sits in a group of companies, and nothing belonging to the platform this runs on.":
        "Sửa tên, địa chỉ, thông tin liên hệ, mã số thuế, số đăng ký và logo in trên phiếu lương, hồ sơ nộp và thư từ. Chỉ một công ty — công ty này — và không gì khác: không đổi tiền tệ, không đổi vị trí trong tập đoàn và không đụng đến nền tảng mà hệ thống chạy trên đó.",

    # ------------------------------------------------ tenant administrator
    "Tenant administrator": "Quản trị viên đơn vị",
    "Runs this whole application: pay, people, joining and leaving, budgets, reporting, the connected systems, the calculation rules, and who here can do what. It does not include the system administrator permission, so it cannot switch developer mode on, open the raw permission table, or reach anything belonging to the platform this runs on. Growth plans are deliberately not part of it — give those to your head of HR separately.":
        "Điều hành toàn bộ ứng dụng này: lương, nhân sự, vào làm và nghỉ việc, ngân sách, báo cáo, các hệ thống được kết nối, quy tắc tính toán và ai ở đây được làm gì. Không bao gồm quyền quản trị hệ thống, nên không bật được chế độ nhà phát triển, không mở được bảng phân quyền gốc và không đụng đến nền tảng mà hệ thống chạy trên đó. Kế hoạch phát triển được cố ý để riêng — hãy giao phần đó cho trưởng phòng nhân sự.",
    # ------------------------------------------- 2026-10-01 (owner) additions
    'Take part in approvals':
        'Tham gia phê duyệt',
    'Send things in for approval, decide the steps that are yours, and see the requests you are part of.':
        'Gửi yêu cầu để phê duyệt, quyết định các bước thuộc về bạn và xem các yêu cầu bạn tham gia.',
    'Approval trail — can look':
        'Lịch sử phê duyệt — chỉ xem',
    'Read every approval that has ever happened, for compliance. Changes nothing.':
        'Xem mọi lần phê duyệt đã từng diễn ra, phục vụ kiểm tra tuân thủ. Không thay đổi gì.',
    'Approval routes — write':
        'Quy trình phê duyệt — soạn',
    'Write draft approval routes, name who holds each step, and choose where a route applies. A draft is not used until somebody publishes it.':
        'Soạn bản nháp quy trình phê duyệt, chỉ định người phụ trách từng bước và chọn nơi áp dụng. Bản nháp chưa được dùng cho đến khi có người ban hành.',
    'Approval routes — publish':
        'Quy trình phê duyệt — ban hành',
    'Make a draft route the one every new request follows. It does not make you an approver.':
        'Đưa một bản nháp thành quy trình mà mọi yêu cầu mới sẽ đi theo. Quyền này không biến bạn thành người duyệt.',
    'Approvals administrator':
        'Quản trị phê duyệt',
    'Arrange exceptions and hand-overs, move a waiting step to somebody else, and withdraw any request.':
        'Sắp xếp ngoại lệ và bàn giao, chuyển một bước đang chờ sang người khác và rút lại bất kỳ yêu cầu nào.',
    'Learning content author':
        'Người soạn nội dung học',
    'Edit the lessons and paths on the Learn screens. The lessons are the same for every company, so give this to very few people.':
        'Chỉnh sửa bài học và lộ trình trên màn hình Học. Bài học giống nhau cho mọi công ty, nên chỉ giao quyền này cho rất ít người.',
    'Demo login':
        'Tài khoản dùng thử',
    "The access the public demo login uses: a guided look around with the demo company's data. Not for real staff.":
        'Quyền dành cho tài khoản dùng thử công khai: xem hướng dẫn với dữ liệu của công ty mẫu. Không dành cho nhân viên thật.',
    'AI assistant':
        'Trợ lý AI',
    'Ask the AI assistant questions about pay and read its dashboards.':
        'Hỏi trợ lý AI về lương và xem các bảng tổng quan của trợ lý.',
    'AI assistant — dashboards':
        'Trợ lý AI — bảng tổng quan',
    'Everything above, plus setting the assistant up and managing its dashboards.':
        'Mọi quyền ở trên, thêm việc thiết lập trợ lý và quản lý các bảng tổng quan.',
    'AI assistant administrator':
        'Quản trị trợ lý AI',
    'Everything above, plus every assistant setting and all of its data.':
        'Mọi quyền ở trên, thêm mọi thiết lập của trợ lý và toàn bộ dữ liệu của nó.',
    'Runs this whole application: pay, people, joining and leaving, budgets, reporting, the connected systems, the calculation rules, hiring, goals, training, announcements, and who here can do what. It does not include the system administrator permission, so it cannot switch developer mode on, open the raw permission table, or reach anything belonging to the platform this runs on. Growth plans are deliberately not part of it — give those to your head of HR separately.':
        'Điều hành toàn bộ ứng dụng này: lương, nhân sự, vào làm và nghỉ việc, ngân sách, báo cáo, các hệ thống được kết nối, quy tắc tính toán, tuyển dụng, mục tiêu, đào tạo, thông báo và ai ở đây được làm gì. Không bao gồm quyền quản trị hệ thống, nên không bật được chế độ nhà phát triển, không mở được bảng phân quyền gốc và không đụng đến nền tảng mà hệ thống chạy trên đó. Kế hoạch phát triển được cố ý để riêng — hãy giao phần đó cho trưởng phòng nhân sự.',
    'Vietnam payroll':
        'Lương Việt Nam',
    'Open the payroll screens and reports that are only for Vietnam. It adds the country; what somebody may do there still comes from their payroll role.':
        'Mở các màn hình và báo cáo lương chỉ dành cho Việt Nam. Quyền này chỉ thêm quốc gia; việc được làm gì ở đó vẫn do vai trò lương của người đó quyết định.',
    'Singapore payroll':
        'Lương Singapore',
    'Open the payroll screens and reports that are only for Singapore. It adds the country; what somebody may do there still comes from their payroll role.':
        'Mở các màn hình và báo cáo lương chỉ dành cho Singapore. Quyền này chỉ thêm quốc gia; việc được làm gì ở đó vẫn do vai trò lương của người đó quyết định.',
    'Malaysia payroll':
        'Lương Malaysia',
    'Open the payroll screens and reports that are only for Malaysia. It adds the country; what somebody may do there still comes from their payroll role.':
        'Mở các màn hình và báo cáo lương chỉ dành cho Malaysia. Quyền này chỉ thêm quốc gia; việc được làm gì ở đó vẫn do vai trò lương của người đó quyết định.',
    'Thailand payroll':
        'Lương Thái Lan',
    'Open the payroll screens and reports that are only for Thailand. It adds the country; what somebody may do there still comes from their payroll role.':
        'Mở các màn hình và báo cáo lương chỉ dành cho Thái Lan. Quyền này chỉ thêm quốc gia; việc được làm gì ở đó vẫn do vai trò lương của người đó quyết định.',
    'Indonesia payroll':
        'Lương Indonesia',
    'Open the payroll screens and reports that are only for Indonesia. It adds the country; what somebody may do there still comes from their payroll role.':
        'Mở các màn hình và báo cáo lương chỉ dành cho Indonesia. Quyền này chỉ thêm quốc gia; việc được làm gì ở đó vẫn do vai trò lương của người đó quyết định.',
    'Cambodia payroll':
        'Lương Campuchia',
    'Open the payroll screens and reports that are only for Cambodia. It adds the country; what somebody may do there still comes from their payroll role.':
        'Mở các màn hình và báo cáo lương chỉ dành cho Campuchia. Quyền này chỉ thêm quốc gia; việc được làm gì ở đó vẫn do vai trò lương của người đó quyết định.',
    'India payroll':
        'Lương Ấn Độ',
    'Open the payroll screens and reports that are only for India. It adds the country; what somebody may do there still comes from their payroll role.':
        'Mở các màn hình và báo cáo lương chỉ dành cho Ấn Độ. Quyền này chỉ thêm quốc gia; việc được làm gì ở đó vẫn do vai trò lương của người đó quyết định.',
}

_MODELS = (('pb.role.profile', ('name', 'description')),
           ('pb.role.ability', ('name', 'description')))


def apply_catalogue_vi(env):
    """Write the Vietnamese of every seeded role and ability. Safe to re-run.

    Reads the jsonb straight from the table: the ORM hands back one language
    at a time, and the question here is "what does THIS row hold for en_US
    and for vi_VN" — both at once, without a fallback in between.
    """
    Lang = env['res.lang'].sudo().with_context(active_test=True)
    if not Lang.search_count([('code', '=', LANG)]):
        return 0
    cr = env.cr
    written = 0
    for model, fnames in _MODELS:
        Model = env.get(model)
        if Model is None:
            continue
        Model = Model.sudo().with_context(active_test=False)
        table = Model._table
        for fname in fnames:
            if not getattr(Model._fields.get(fname), 'translate', False):
                continue
            cr.execute(
                'SELECT id, "{f}"->>\'en_US\', "{f}"->>%s FROM "{t}" '
                'WHERE "{f}" IS NOT NULL'.format(f=fname, t=table), [LANG])
            for rec_id, en, vi in cr.fetchall():
                target = VI.get((en or '').strip())
                if not target:
                    continue            # not a catalogue sentence: theirs
                if vi and vi != en:
                    continue            # already Vietnamese (maybe their own)
                try:
                    Model.browse(rec_id).update_field_translations(
                        fname, {LANG: target})
                    written += 1
                except Exception:       # noqa: BLE001 — words never block a seed
                    _logger.warning(
                        'pb_vendor_access: could not write the Vietnamese of '
                        '%s,%s.%s', model, rec_id, fname, exc_info=True)
    if written:
        _logger.info('pb_vendor_access: role catalogue — %s Vietnamese values '
                     'written', written)
    return written
