/* ==========================================================================
   Payobook Learn — prototype content
   All copy is bilingual {en, vi}. Vietnamese written for payroll/business
   users (BHXH/BHYT/BHTN, thuế TNCN, giảm trừ gia cảnh terminology).
   Menu inventory mirrors pb_sidebar/data/pb_sidebar_data.xml (Pay Run + Setup).
   ========================================================================== */

// ---------------------------------------------------------------- UI strings
const I18N = {
  en: {
    prototype: "Prototype", practiceOnly: "Practice environment — no real data",
    hubTitle: "Learn Payobook without a trainer.",
    hubSub: "Three concepts for an animated, bilingual, self-sufficient learning system covering Pay Run and Setup. Open each one, compare, and pick a direction.",
    langLabel: "Language", roleLabel: "Role", motion: "Reduce motion", reset: "Reset progress",
    resumeTitle: "Welcome back", resumeBody: "Pick up where you left off:", resumeCta: "Resume",
    modeTitle: "How do you want to learn today?",
    open: "Open", explore: "Explore concept",
    concept1: "Cinematic Guided Journey", concept1Tag: "Watch, then understand",
    concept1Desc: "A story-driven journey map for Pay Run and Setup. Spotlight walkthroughs move camera-like across the real screens, trace how Setup decisions become Pay Run numbers, and end each lesson with a real understanding check.",
    concept2: "Safe Payroll Simulator", concept2Tag: "Learn by doing — safely",
    concept2Desc: "A clearly-marked practice company with realistic Vietnamese payroll data. Guided missions, consequence previews before every risky action, mistake recovery, and a confidence score earned by doing, not clicking Next.",
    concept3: "AI Learning Companion", concept3Tag: "Ask anything, anywhere",
    concept3Desc: "A context-aware companion docked into every Pay Run and Setup screen. It answers in your language with highlighted controls, numbered steps, calculation breakdowns and consequence warnings — and hands you to practice mode when you want to try.",
    back: "Back", backHub: "All concepts", next: "Next", prev: "Back", skip: "Skip lesson",
    replay: "Replay step", exit: "Save & exit", pause: "Pause", play: "Play", done: "Done",
    stepOf: (a, b) => `Step ${a} of ${b}`,
    lessonOutline: "Lesson outline", outlineNote: "Prototype: this station shows its outline. The two ★ lessons are fully playable.",
    fullLesson: "Full lesson", startLesson: "Start lesson", est: "est.",
    required: "Required", optional: "Optional", dependsOn: "After", mastered: "Mastered", inProgress: "In progress",
    journeyTitle: "Your learning journey", journeySub: "Two lines: master the monthly Pay Run loop, and the Setup that powers it. Finish the ★ lessons to unlock your payday badge.",
    payrunLine: "Pay Run line", setupLine: "Setup line", overall: "Overall progress",
    searchLessons: "Search lessons…",
    whatIs: "What it is", whyMatters: "Why it matters", whenUse: "When to use it", prereq: "Before you start", mistakes: "Common mistakes",
    quizTitle: "Quick check", quizWhy: "One question — to make sure it stuck.",
    correct: "Correct!", notQuite: "Not quite —",
    lessonDone: "Lesson complete", lessonDoneBody: "Nice work. Progress saved — your next stop is suggested below.",
    nextLesson: "Next lesson", backToMap: "Back to map",
    simTitle: "Practice Studio", simSub: "A fictional company — Hoa Sen Retail Co. (48 employees, July 2026) — where nothing you do can touch production. Break things, fix things, build confidence.",
    missions: "Missions", missionsPayrun: "Pay Run missions", missionsSetup: "Setup missions",
    confidence: "Your confidence", confidenceSub: "Earned by decisions, not clicks.",
    startMission: "Start mission", resumeMission: "Resume", missionDone: "Completed — replay",
    outlineMission: "Mission outline — playable in production build",
    sandboxReset: "Reset sandbox", showHint: "Show hint", abandonMission: "Exit mission",
    consequenceTitle: "Before you continue", consequenceAffects: "What this affects", consequenceReversible: "Can it be undone?", consequenceCheck: "Verify first",
    proceed: "Proceed", cancel: "Cancel", undo: "Undo change",
    debriefTitle: "Mission debrief", whatYouDid: "What you did", checklist: "Before finalising a real run, always check",
    confidenceUp: (n) => `Confidence +${n}%`,
    compTitle: "PayAI Coach", compSub: "Grounded in this screen", compGuard: "I guide — you act. Nothing here touches production, and I never perform payroll actions for you.",
    youAreOn: "You're on", suggested: "Suggested for this screen",
    askPlaceholder: "Ask about this screen…", send: "Send",
    showMe: "Show me", letMeTry: "Let me practise safely", openLessonLink: "Open the lesson",
    tellMore: "Tell me more", simpler: "Explain more simply", whySeeing: "Why am I seeing this?",
    grounded: "Grounded in", roleNote: "Answer adapted to your role",
    fallback: "In the prototype I answer a scripted set of questions — try a suggested chip below, or ask about running payroll, approvals, BHXH or PIT.",
    roles: { officer: "Payroll Officer", hr: "HR Manager", gm: "General Director", viewer: "Viewer" },
    menuOverview: "Overview", menuPayrun: "Pay Run", menuSetup: "Setup", menuPeople: "People", menuInsights: "Insights",
    coachKicker: "Payobook Coach", missionKicker: "Mission",
    autoplay: "Autoplay", interactive: "Step by step",
    minutes: "min", tryIt: "Try it in Practice Studio", watchIt: "Watch the lesson",
    completedBadge: "Payday-ready", morphBefore: "Before", morphAfter: "After",
    flagReview: "Flag for review", acceptAnyway: "Accept as correct",
    recoveryTitle: "Let's rethink that", keepGoing: "Keep going",
    submitApproval: "Submit for approval", computing: "Computing payslips…",
    anomaly: "needs review", anomalies: (n) => `${n} payslip needs review`,
    pipeline: ["Draft", "Payroll Officer", "HR review", "GM approval", "Done"],
    compute: "Compute payslips", eligible: "eligible employees",
    period: "Pay period", division: "Division", cycle: "Cycle", cycleEnd: "End-cycle", cycleMid: "Mid-cycle",
    net: "Net", gross: "Gross", employees: "Employees", total: "Total",
    close: "Close", gotIt: "Got it", continueBtn: "Continue",
    hero: { headcount: "Headcount", monthlyNet: "Monthly net", waiting: "Awaiting approval", configs: "Formula configs" },
    langName: "English",
  },
  vi: {
    prototype: "Bản thử nghiệm", practiceOnly: "Môi trường thực hành — không có dữ liệu thật",
    hubTitle: "Học Payobook mà không cần người hướng dẫn.",
    hubSub: "Ba ý tưởng cho một hệ thống học tập song ngữ, có hoạt ảnh, tự phục vụ — bao trùm Chạy lương và Thiết lập. Mở từng ý tưởng, so sánh và chọn hướng đi.",
    langLabel: "Ngôn ngữ", roleLabel: "Vai trò", motion: "Giảm chuyển động", reset: "Xoá tiến độ",
    resumeTitle: "Chào mừng trở lại", resumeBody: "Tiếp tục từ nơi bạn dừng lại:", resumeCta: "Tiếp tục",
    modeTitle: "Hôm nay bạn muốn học theo cách nào?",
    open: "Mở", explore: "Khám phá ý tưởng",
    concept1: "Hành trình có dẫn dắt", concept1Tag: "Xem để hiểu bản chất",
    concept1Desc: "Bản đồ hành trình theo mạch kể chuyện cho Chạy lương và Thiết lập. Đèn chiếu di chuyển như máy quay trên màn hình thật, cho thấy quyết định ở Thiết lập biến thành con số trên bảng lương ra sao, và kết thúc mỗi bài bằng câu hỏi kiểm tra hiểu bài.",
    concept2: "Xưởng thực hành an toàn", concept2Tag: "Học bằng cách làm — an toàn",
    concept2Desc: "Một công ty giả lập với dữ liệu lương Việt Nam thực tế. Nhiệm vụ có hướng dẫn, xem trước hậu quả trước mỗi thao tác rủi ro, khôi phục khi làm sai, và điểm tự tin tích luỹ bằng quyết định thật — không phải bằng nút Tiếp theo.",
    concept3: "Trợ lý học tập AI", concept3Tag: "Hỏi bất cứ điều gì, ở bất cứ đâu",
    concept3Desc: "Trợ lý hiểu ngữ cảnh, gắn vào mọi màn hình Chạy lương và Thiết lập. Trả lời bằng ngôn ngữ của bạn kèm vùng sáng chỉ đúng nút cần bấm, các bước đánh số, bảng diễn giải phép tính và cảnh báo hậu quả — và đưa bạn sang chế độ thực hành khi muốn tự làm.",
    back: "Quay lại", backHub: "Tất cả ý tưởng", next: "Tiếp theo", prev: "Trước", skip: "Bỏ qua bài",
    replay: "Xem lại bước", exit: "Lưu & thoát", pause: "Tạm dừng", play: "Phát", done: "Hoàn tất",
    stepOf: (a, b) => `Bước ${a}/${b}`,
    lessonOutline: "Dàn ý bài học", outlineNote: "Bản thử nghiệm: trạm này hiển thị dàn ý. Hai bài ★ chơi được đầy đủ.",
    fullLesson: "Bài học đầy đủ", startLesson: "Bắt đầu bài học", est: "khoảng",
    required: "Bắt buộc", optional: "Tuỳ chọn", dependsOn: "Sau khi học", mastered: "Đã thành thạo", inProgress: "Đang học",
    journeyTitle: "Hành trình học của bạn", journeySub: "Hai tuyến: làm chủ vòng lặp Chạy lương hằng tháng, và phần Thiết lập vận hành nó. Hoàn thành các bài ★ để nhận huy hiệu sẵn sàng trả lương.",
    payrunLine: "Tuyến Chạy lương", setupLine: "Tuyến Thiết lập", overall: "Tiến độ chung",
    searchLessons: "Tìm bài học…",
    whatIs: "Đây là gì", whyMatters: "Vì sao quan trọng", whenUse: "Khi nào dùng", prereq: "Trước khi bắt đầu", mistakes: "Lỗi thường gặp",
    quizTitle: "Kiểm tra nhanh", quizWhy: "Một câu hỏi — để chắc bạn đã nắm được.",
    correct: "Chính xác!", notQuite: "Chưa đúng —",
    lessonDone: "Hoàn thành bài học", lessonDoneBody: "Làm tốt lắm. Tiến độ đã được lưu — trạm tiếp theo được gợi ý bên dưới.",
    nextLesson: "Bài tiếp theo", backToMap: "Về bản đồ",
    simTitle: "Xưởng thực hành", simSub: "Một công ty giả lập — Công ty Bán lẻ Hoa Sen (48 nhân viên, tháng 7/2026) — nơi mọi thao tác đều không chạm tới dữ liệu thật. Cứ làm sai, sửa lại, và xây sự tự tin.",
    missions: "Nhiệm vụ", missionsPayrun: "Nhiệm vụ Chạy lương", missionsSetup: "Nhiệm vụ Thiết lập",
    confidence: "Mức tự tin của bạn", confidenceSub: "Tích luỹ bằng quyết định, không phải cú bấm.",
    startMission: "Bắt đầu", resumeMission: "Tiếp tục", missionDone: "Đã xong — chơi lại",
    outlineMission: "Dàn ý nhiệm vụ — chơi được ở bản chính thức",
    sandboxReset: "Đặt lại môi trường", showHint: "Xem gợi ý", abandonMission: "Thoát nhiệm vụ",
    consequenceTitle: "Trước khi tiếp tục", consequenceAffects: "Thao tác này ảnh hưởng", consequenceReversible: "Hoàn tác được không?", consequenceCheck: "Kiểm tra trước",
    proceed: "Tiếp tục", cancel: "Huỷ", undo: "Hoàn tác thay đổi",
    debriefTitle: "Tổng kết nhiệm vụ", whatYouDid: "Bạn đã làm gì", checklist: "Trước khi chốt một kỳ lương thật, luôn kiểm tra",
    confidenceUp: (n) => `Tự tin +${n}%`,
    compTitle: "PayAI Coach", compSub: "Bám sát màn hình này", compGuard: "Tôi hướng dẫn — bạn thao tác. Không gì ở đây chạm tới dữ liệu thật, và tôi không bao giờ tự thực hiện nghiệp vụ lương thay bạn.",
    youAreOn: "Bạn đang ở", suggested: "Gợi ý cho màn hình này",
    askPlaceholder: "Hỏi về màn hình này…", send: "Gửi",
    showMe: "Chỉ cho tôi", letMeTry: "Cho tôi thực hành an toàn", openLessonLink: "Mở bài học",
    tellMore: "Giải thích thêm", simpler: "Giải thích đơn giản hơn", whySeeing: "Vì sao tôi thấy câu trả lời này?",
    grounded: "Căn cứ", roleNote: "Câu trả lời theo vai trò của bạn",
    fallback: "Trong bản thử nghiệm, tôi trả lời một bộ câu hỏi có sẵn — hãy thử các gợi ý bên dưới, hoặc hỏi về chạy lương, phê duyệt, BHXH hay thuế TNCN.",
    roles: { officer: "Chuyên viên tính lương", hr: "Trưởng phòng Nhân sự", gm: "Tổng Giám đốc", viewer: "Chỉ xem" },
    menuOverview: "Tổng quan", menuPayrun: "Chạy lương", menuSetup: "Thiết lập", menuPeople: "Nhân sự", menuInsights: "Phân tích",
    coachKicker: "Payobook Coach", missionKicker: "Nhiệm vụ",
    autoplay: "Tự phát", interactive: "Từng bước",
    minutes: "phút", tryIt: "Thực hành trong Xưởng", watchIt: "Xem bài học",
    completedBadge: "Sẵn sàng trả lương", morphBefore: "Trước", morphAfter: "Sau",
    flagReview: "Đánh dấu cần soát xét", acceptAnyway: "Chấp nhận là đúng",
    recoveryTitle: "Hãy nghĩ lại một chút", keepGoing: "Tiếp tục",
    submitApproval: "Trình phê duyệt", computing: "Đang tính phiếu lương…",
    anomaly: "cần soát xét", anomalies: (n) => `${n} phiếu lương cần soát xét`,
    pipeline: ["Nháp", "CV tính lương", "HR soát xét", "TGĐ phê duyệt", "Hoàn tất"],
    compute: "Tính phiếu lương", eligible: "nhân viên đủ điều kiện",
    period: "Kỳ lương", division: "Bộ phận", cycle: "Chu kỳ", cycleEnd: "Cuối kỳ", cycleMid: "Giữa kỳ",
    net: "Thực nhận", gross: "Tổng thu nhập", employees: "Nhân viên", total: "Tổng",
    close: "Đóng", gotIt: "Đã hiểu", continueBtn: "Tiếp tục",
    hero: { headcount: "Nhân sự", monthlyNet: "Thực chi tháng", waiting: "Chờ phê duyệt", configs: "Cấu hình công thức" },
    langName: "Tiếng Việt",
  },
};

// ------------------------------------------------------------------- helpers
const B = (en, vi) => ({ en, vi });

// ----------------------------------------------------------------- mock data
// Payslip maths kept internally consistent (VN 2026 practice values):
// insurance base 12,000,000 → BHXH 8% / BHYT 1.5% / BHTN 1%;
// personal deduction 11,000,000; PIT tier 1 = 5%.
const EMP = {
  mai: {
    name: "Nguyễn Thị Mai", code: "NV0012", dept: B("Retail — Hà Nội", "Bán lẻ — Hà Nội"),
    base: 12000000, allowance: 780000, otJul: 1500000, otJun: 600000,
    bhxh: 960000, bhyt: 180000, bhtn: 120000,
    grossJul: 14280000, pitJul: 101000, netJul: 12919000,
    grossJun: 13380000, pitJun: 56000, netJun: 12064000,
  },
  hung: {
    name: "Trần Văn Hùng", code: "NV0031", dept: B("Retail — Hà Nội", "Bán lẻ — Hà Nội"),
    base: 10500000, allowance: 650000, otJul: 4200000, otJun: 1100000,
    grossJul: 15350000, netJul: 13648000,
  },
  trang: { name: "Lê Thu Trang", code: "NV0007", base: 15200000, netJul: 15530000 },
  duc: { name: "Phạm Minh Đức", code: "NV0019", base: 9800000, netJul: 10241000 },
};

const RUN = {
  name: B("Retail — July 2026", "Bán lẻ — Tháng 7/2026"),
  division: B("Retail — Hà Nội", "Bán lẻ — Hà Nội"),
  period: B("July 2026", "Tháng 7/2026"),
  employees: 48, totalNet: 612480000, totalGross: 691200000,
  config: "HOASEN_RETAIL_END", configVersion: "v12",
};

// -------------------------------------------------------------- menu (real)
// Mirrors pb_sidebar_data.xml: sections Overview / Pay Run / Setup (+ others
// shown for context but out of tutorial scope this phase).
const MENU = [
  {
    key: "overview", label: B("Overview", "Tổng quan"), items: [
      { id: "dashboard", icon: "home", label: B("Dashboard", "Bảng điều khiển") },
      { id: "approvals", icon: "clipboard-check", label: B("Approvals", "Phê duyệt") },
    ],
  },
  {
    key: "payrun", label: B("Pay Run", "Chạy lương"), scope: true, items: [
      { id: "runpayroll", icon: "zap", label: B("Run Payroll", "Chạy bảng lương") },
      { id: "payruns", icon: "calendar", label: B("Pay Runs", "Đợt tính lương") },
      { id: "payslips", icon: "receipt", label: B("Payslips", "Phiếu lương") },
      { id: "import", icon: "download", label: B("Import Data", "Nhập dữ liệu") },
      { id: "fullfinal", icon: "file", label: B("Full & Final", "Quyết toán thôi việc") },
      { id: "proration", icon: "calculator", label: B("Proration Audit", "Soát xét ngày công") },
      { id: "retro", icon: "percent", label: B("Retro Adjustments", "Điều chỉnh hồi tố") },
    ],
  },
  {
    key: "setup", label: B("Setup", "Thiết lập"), scope: true, items: [
      { id: "formula", icon: "calculator", label: B("Formula Engine", "Công thức lương") },
      { id: "structures", icon: "layers", label: B("Salary Structures", "Cấu trúc lương") },
      { id: "statutory", icon: "shield", label: B("Statutory (Insurance & Tax)", "Bảo hiểm & Thuế") },
      { id: "integrations", icon: "database", label: B("Integrations", "Tích hợp") },
    ],
  },
];

// ------------------------------------------------------------------ glossary
const GLOSSARY = {
  bhxh: { term: "BHXH", def: B("Social insurance. Employee pays 8% of the insurance base; employer pays 17.5% on top.", "Bảo hiểm xã hội. Người lao động đóng 8% trên mức lương đóng BH; doanh nghiệp đóng thêm 17,5%.") },
  bhyt: { term: "BHYT", def: B("Health insurance — 1.5% employee / 3% employer on the insurance base.", "Bảo hiểm y tế — người lao động 1,5% / doanh nghiệp 3% trên mức lương đóng BH.") },
  bhtn: { term: "BHTN", def: B("Unemployment insurance — 1% employee / 1% employer.", "Bảo hiểm thất nghiệp — người lao động 1% / doanh nghiệp 1%.") },
  pit: { term: B("PIT", "Thuế TNCN"), def: B("Personal income tax. Progressive 5–35% after deducting insurance and family allowances (₫11m self + ₫4.4m per dependant).", "Thuế thu nhập cá nhân, luỹ tiến 5–35% sau khi trừ bảo hiểm và giảm trừ gia cảnh (11 triệu bản thân + 4,4 triệu mỗi người phụ thuộc).") },
  formulaConfig: { term: B("Formula config", "Cấu hình công thức"), def: B("The Excel-style rulebook that computes every payslip line for a division — inputs, earnings, deductions, totals.", "Bộ quy tắc kiểu Excel tính từng dòng phiếu lương cho một bộ phận — đầu vào, thu nhập, khấu trừ, tổng.") },
  payrun: { term: B("Pay run", "Đợt tính lương"), def: B("One batch of payslips for a division and period, moving Draft → Officer → HR → GM → Done.", "Một lô phiếu lương của một bộ phận trong một kỳ, đi qua Nháp → CV tính lương → HR → TGĐ → Hoàn tất.") },
};

// ---------------------------------------------------------- journey stations
// status: "full" = playable lesson; "outline" = outline modal (placeholder,
// clearly labelled). All Pay Run + Setup submenu items are covered.
const STATIONS = {
  payrun: [
    {
      id: "runpayroll", icon: "zap", star: true, required: true, mins: 6, lesson: "L1",
      title: B("Run Payroll", "Chạy bảng lương"),
      desc: B("Create a month's draft payslips for a division — the heart of Payobook.", "Tạo phiếu lương nháp của một tháng cho một bộ phận — trái tim của Payobook."),
      after: null,
    },
    {
      id: "payruns", icon: "calendar", required: true, mins: 4,
      title: B("Pay Runs & approvals", "Đợt tính lương & phê duyệt"),
      desc: B("Every run on one board, moving Draft → Officer → HR → GM → Done.", "Mọi đợt lương trên một bảng, đi từ Nháp → CV tính lương → HR → TGĐ → Hoàn tất."),
      after: "runpayroll",
      outline: {
        what: B("A kanban board of every pay run and its approval stage.", "Bảng kanban của mọi đợt tính lương và trạng thái phê duyệt."),
        why: B("Nothing is paid without the right sign-offs; the board makes the pipeline visible and auditable.", "Không khoản nào được chi khi chưa đủ chữ ký phê duyệt; bảng này làm quy trình minh bạch và kiểm toán được."),
        when: B("Daily during payroll week; whenever you need to know 'where is July?'", "Hằng ngày trong tuần tính lương; bất cứ khi nào bạn cần biết 'kỳ tháng 7 đang ở đâu?'"),
        prereq: B("A computed run (see Run Payroll).", "Một đợt đã tính xong (xem Chạy bảng lương)."),
        mistakes: B("Approving a run without opening its flagged payslips; rejecting without a written reason.", "Phê duyệt khi chưa mở các phiếu bị gắn cờ; từ chối mà không ghi lý do."),
      },
    },
    {
      id: "payslips", icon: "receipt", required: true, mins: 5,
      title: B("Payslips", "Phiếu lương"),
      desc: B("Read any employee's slip line by line — gross to net, with every formula visible.", "Đọc phiếu lương của từng nhân viên theo từng dòng — từ tổng thu nhập đến thực nhận, công thức minh bạch."),
      after: "runpayroll",
      outline: {
        what: B("The review surface for individual payslips inside a run.", "Nơi soát xét từng phiếu lương trong một đợt."),
        why: B("This is where errors are caught before money moves — one wrong input is one wrong salary.", "Đây là nơi bắt lỗi trước khi tiền được chi — một đầu vào sai là một mức lương sai."),
        when: B("After computing, before submitting for approval.", "Sau khi tính, trước khi trình phê duyệt."),
        prereq: B("A computed run.", "Một đợt đã tính."),
        mistakes: B("Editing a net amount directly instead of fixing the input and recomputing.", "Sửa thẳng số thực nhận thay vì sửa dữ liệu đầu vào rồi tính lại."),
      },
    },
    {
      id: "import", icon: "download", required: true, mins: 5,
      title: B("Import Data", "Nhập dữ liệu"),
      desc: B("Bring in Excel attendance, OT and inputs — preview, score and fix before anything commits.", "Đưa dữ liệu chấm công, tăng ca, đầu vào từ Excel — xem trước, chấm điểm và sửa lỗi trước khi ghi nhận."),
      after: null,
      outline: {
        what: B("A guided 4-step import: Upload → Preview → Score → Commit.", "Quy trình nhập 4 bước có hướng dẫn: Tải lên → Xem trước → Chấm điểm → Ghi nhận."),
        why: B("Most payroll errors are import errors. The confidence score catches them while they're still cheap.", "Phần lớn lỗi lương là lỗi nhập liệu. Điểm tin cậy giúp bắt lỗi khi chi phí sửa còn rẻ."),
        when: B("Before computing a run, whenever the month's inputs arrive.", "Trước khi tính một đợt, ngay khi dữ liệu tháng về."),
        prereq: B("Mapped columns (Formula Engine → Mapping).", "Đã ánh xạ cột (Công thức lương → Mapping)."),
        mistakes: B("Committing with a low confidence score; importing July data into the June period.", "Ghi nhận khi điểm tin cậy thấp; nhập dữ liệu tháng 7 vào kỳ tháng 6."),
      },
    },
    {
      id: "fullfinal", icon: "file", mins: 4,
      title: B("Full & Final", "Quyết toán thôi việc"),
      desc: B("Settle a leaver: last salary, unused leave, deductions — one closing statement.", "Quyết toán cho nhân viên nghỉ việc: lương cuối, phép chưa dùng, khấu trừ — một bảng chốt duy nhất."),
      after: "payruns",
      outline: {
        what: B("The settlement workspace for departing employees.", "Không gian quyết toán cho nhân viên thôi việc."),
        why: B("Leaver settlements have legal deadlines and one shot at being right.", "Quyết toán thôi việc có thời hạn pháp lý và chỉ có một lần để làm đúng."),
        when: B("As soon as a resignation/termination date is confirmed.", "Ngay khi ngày nghỉ việc được xác nhận."),
        prereq: B("Contract end date recorded; leave balance current.", "Đã ghi ngày kết thúc hợp đồng; số dư phép cập nhật."),
        mistakes: B("Running the leaver in the normal monthly run as well — paying twice.", "Vẫn để nhân viên đó trong đợt lương tháng bình thường — trả trùng hai lần."),
      },
    },
    {
      id: "proration", icon: "calculator", mins: 3,
      title: B("Proration Audit", "Soát xét ngày công"),
      desc: B("See exactly how part-month salaries were prorated — day by day, no black box.", "Xem chính xác lương tháng lẻ ngày được tính theo tỷ lệ ra sao — từng ngày, không hộp đen."),
      after: "payslips",
      outline: {
        what: B("An audit trail of every prorated amount (joiners, leavers, unpaid leave).", "Nhật ký kiểm toán mọi khoản tính theo tỷ lệ (người mới, người nghỉ, nghỉ không lương)."),
        why: B("Proration disputes are the #1 employee question; this screen is your evidence.", "Thắc mắc về ngày công là câu hỏi số 1 của nhân viên; màn hình này là bằng chứng của bạn."),
        when: B("When a payslip looks 'too small' and you need to show why.", "Khi một phiếu lương trông 'thiếu' và bạn cần chứng minh vì sao."),
        prereq: B("A computed run with mid-month movement.", "Một đợt đã tính có biến động giữa tháng."),
        mistakes: B("Assuming calendar days when the config uses working days.", "Nhầm ngày dương lịch trong khi cấu hình dùng ngày công chuẩn."),
      },
    },
    {
      id: "retro", icon: "percent", mins: 4,
      title: B("Retro Adjustments", "Điều chỉnh hồi tố"),
      desc: B("Backdated raises and corrections, applied cleanly to a later run — with a full trail.", "Tăng lương lùi ngày và các hiệu chỉnh, áp gọn vào kỳ sau — có vết lưu đầy đủ."),
      after: "payruns",
      outline: {
        what: B("A ledger of differences owed from past periods, paid in the current run.", "Sổ ghi các chênh lệch còn nợ từ kỳ trước, chi trong kỳ hiện tại."),
        why: B("It keeps closed months closed — you never reopen an approved run to fix the past.", "Giúp kỳ đã đóng luôn đóng — không bao giờ mở lại đợt đã duyệt để sửa quá khứ."),
        when: B("Backdated raises, missed allowances, corrections found after approval.", "Tăng lương lùi ngày, phụ cấp bỏ sót, lỗi phát hiện sau phê duyệt."),
        prereq: B("The source run is Done; the correction is documented.", "Đợt gốc đã Hoàn tất; hiệu chỉnh có chứng từ."),
        mistakes: B("Editing the old approved payslip instead of creating a retro line.", "Sửa phiếu lương cũ đã duyệt thay vì tạo dòng hồi tố."),
      },
    },
  ],
  setup: [
    {
      id: "formula", icon: "calculator", required: true, mins: 7,
      title: B("Formula Engine", "Công thức lương"),
      desc: B("The Excel-style brain: every payslip line comes from a named, visible formula.", "Bộ não kiểu Excel: mỗi dòng phiếu lương sinh ra từ một công thức có tên, nhìn thấy được."),
      after: null,
      outline: {
        what: B("A visual studio of each division's formula config — components, dependencies, live preview.", "Xưởng trực quan cho cấu hình công thức của từng bộ phận — thành phần, phụ thuộc, xem trước trực tiếp."),
        why: B("If you can read the formula, you can answer any 'why is my pay X?' question yourself.", "Đọc được công thức nghĩa là bạn tự trả lời được mọi câu hỏi 'sao lương tôi là X?'."),
        when: B("When adding an allowance, changing a rule, or tracing a number.", "Khi thêm phụ cấp, đổi quy tắc, hoặc truy vết một con số."),
        prereq: B("Manager-level access; a test employee to preview with.", "Quyền cấp quản lý; một nhân viên mẫu để xem trước."),
        mistakes: B("Editing a live config without previewing; renaming a component other formulas depend on.", "Sửa cấu hình đang chạy mà không xem trước; đổi tên thành phần đang được công thức khác dùng."),
      },
    },
    {
      id: "structures", icon: "layers", mins: 3,
      title: B("Salary Structures", "Cấu trúc lương"),
      desc: B("The legacy rule sets — kept for heritage data; new divisions run on formula configs.", "Bộ quy tắc thế hệ cũ — giữ cho dữ liệu lịch sử; bộ phận mới chạy bằng cấu hình công thức."),
      after: "formula",
      outline: {
        what: B("Odoo salary structures & rules that older data still references.", "Cấu trúc lương & quy tắc Odoo mà dữ liệu cũ còn tham chiếu."),
        why: B("You'll meet them in old payslips; knowing what they are stops confusion.", "Bạn sẽ gặp chúng trong phiếu lương cũ; hiểu chúng để khỏi bối rối."),
        when: B("Reading history; migrating a division to the Formula Engine.", "Khi đọc lịch sử; khi chuyển một bộ phận sang Công thức lương."),
        prereq: B("Formula Engine basics.", "Nắm cơ bản Công thức lương."),
        mistakes: B("Building new pay logic here instead of in the Formula Engine.", "Xây logic lương mới ở đây thay vì trong Công thức lương."),
      },
    },
    {
      id: "statutory", icon: "shield", star: true, required: true, mins: 6, lesson: "L2",
      title: B("Statutory (Insurance & Tax)", "Bảo hiểm & Thuế"),
      desc: B("BHXH · BHYT · BHTN rates and the PIT table — the rules the law writes for you.", "Tỷ lệ BHXH · BHYT · BHTN và biểu thuế TNCN — các quy tắc do pháp luật quy định."),
      after: null,
    },
    {
      id: "integrations", icon: "database", mins: 3,
      title: B("Integrations", "Tích hợp"),
      desc: B("Connectors that pull attendance & HR data in automatically — mapped field by field.", "Đầu nối tự động kéo dữ liệu chấm công & nhân sự — ánh xạ theo từng trường."),
      after: null,
      outline: {
        what: B("Connector setup (e.g. Zoho People, bank SFTP) with field mappings and sync history.", "Thiết lập đầu nối (như Zoho People, SFTP ngân hàng) với ánh xạ trường và lịch sử đồng bộ."),
        why: B("Automated inputs beat retyped inputs — fewer keystrokes, fewer wrong salaries.", "Dữ liệu tự động thắng dữ liệu gõ tay — ít gõ phím hơn, ít lương sai hơn."),
        when: B("Once at onboarding; revisit when a source system changes fields.", "Một lần khi triển khai; xem lại khi hệ thống nguồn đổi trường dữ liệu."),
        prereq: B("Integration-user access; source system credentials.", "Quyền người dùng tích hợp; thông tin đăng nhập hệ thống nguồn."),
        mistakes: B("Leaving a broken sync unnoticed until payroll week.", "Để đồng bộ lỗi mà không phát hiện cho tới tuần tính lương."),
      },
    },
  ],
};

// ---------------------------------------------------------------- lessons ★
const LESSONS = {
  L1: {
    id: "L1", station: "runpayroll", mins: 6,
    title: B("Run Payroll — your first pay run", "Chạy bảng lương — đợt lương đầu tiên của bạn"),
    steps: [
      {
        screen: "runpayroll", target: null,
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("This screen creates a month of pay", "Màn hình này tạo ra một tháng lương"),
        body: B("<b>Run Payroll</b> takes one division and one period, and computes a draft payslip for every eligible employee. Nothing is paid here — you are creating <b>drafts</b> to review.", "<b>Chạy bảng lương</b> nhận một bộ phận và một kỳ lương, rồi tính phiếu lương nháp cho từng nhân viên đủ điều kiện. Chưa có gì được chi trả ở đây — bạn đang tạo <b>bản nháp</b> để soát xét."),
      },
      {
        screen: "runpayroll", target: "pw-division",
        kicker: B("Step 1", "Bước 1"),
        title: B("Choose the division", "Chọn bộ phận"),
        body: B("Each division pays under its own <b>formula config</b> — Retail's rules differ from Construction's. Picking the division picks the rulebook.", "Mỗi bộ phận trả lương theo <b>cấu hình công thức</b> riêng — quy tắc của Bán lẻ khác Xây dựng. Chọn bộ phận là chọn bộ quy tắc."),
      },
      {
        screen: "runpayroll", target: "pw-period",
        kicker: B("Step 2", "Bước 2"),
        title: B("Period and cycle", "Kỳ lương và chu kỳ"),
        body: B("Pick the month, then the cycle: <b>Mid-cycle</b> pays an advance during the month; <b>End-cycle</b> is the full monthly settlement. Most divisions run End-cycle only.", "Chọn tháng, rồi chọn chu kỳ: <b>Giữa kỳ</b> là khoản tạm ứng trong tháng; <b>Cuối kỳ</b> là quyết toán cả tháng. Đa số bộ phận chỉ chạy Cuối kỳ."),
        tip: B("Running the wrong cycle is the most common first-week mistake — the preview card on the next step is how you catch it.", "Chạy nhầm chu kỳ là lỗi tuần-đầu phổ biến nhất — thẻ xem trước ở bước sau giúp bạn phát hiện."),
      },
      {
        screen: "runpayroll", target: "pw-config",
        kicker: B("Prerequisites", "Điều kiện"),
        title: B("Read the preview before you compute", "Đọc phần xem trước rồi mới tính"),
        body: B("Payobook shows which config version will run and how many employees are eligible. If the count looks wrong — say 12 instead of 48 — <b>stop</b>: your attendance import probably hasn't been committed.", "Payobook cho biết phiên bản cấu hình nào sẽ chạy và bao nhiêu nhân viên đủ điều kiện. Nếu con số bất thường — ví dụ 12 thay vì 48 — hãy <b>dừng lại</b>: có thể dữ liệu chấm công chưa được ghi nhận."),
      },
      {
        screen: "runpayroll", target: "pw-compute",
        kicker: B("The action", "Thao tác chính"),
        title: B("Compute — what actually happens", "Tính — điều gì thực sự diễn ra"),
        body: B("One click runs the formula engine for all 48 employees: gross, allowances, BHXH/BHYT/BHTN, PIT, net.", "Một cú bấm chạy công thức cho cả 48 nhân viên: tổng thu nhập, phụ cấp, BHXH/BHYT/BHTN, thuế TNCN, thực nhận."),
        consequence: B("Affects: July 2026 × Retail only. Reversible: <b>yes</b> — drafts can be deleted and recomputed. Employees see nothing until approval completes.", "Ảnh hưởng: chỉ Tháng 7/2026 × Bán lẻ. Hoàn tác: <b>được</b> — phiếu nháp xoá và tính lại được. Nhân viên chưa thấy gì cho tới khi phê duyệt xong."),
      },
      {
        screen: "runpayroll", target: "pw-result", simulate: "computed",
        kicker: B("Reading results", "Đọc kết quả"),
        title: B("48 drafts, 1 flag", "48 bản nháp, 1 cảnh báo"),
        body: B("The engine finished in seconds and flagged one payslip: Trần Văn Hùng's overtime is 250% of his usual. Flags are not errors — they are questions the system wants you to answer.", "Công thức chạy xong trong vài giây và gắn cờ một phiếu: tăng ca của Trần Văn Hùng bằng 250% mức thường lệ. Cờ không phải là lỗi — đó là câu hỏi hệ thống muốn bạn trả lời."),
      },
      {
        screen: "payruns", target: "k-draft",
        kicker: B("Where it goes", "Đi về đâu"),
        title: B("Your run enters the pipeline", "Đợt lương vào quy trình"),
        body: B("The run now sits in <b>Draft</b> on the Pay Runs board. From here it travels Officer → HR review → GM approval → Done. Each column is gated to a role — nobody can skip a gate.", "Đợt lương giờ nằm ở cột <b>Nháp</b> trên bảng Đợt tính lương. Từ đây nó đi qua CV tính lương → HR soát xét → TGĐ phê duyệt → Hoàn tất. Mỗi cột gắn với một vai trò — không ai bỏ qua được cổng nào."),
      },
      {
        screen: "payruns", target: null,
        kicker: B("Common mistakes", "Lỗi thường gặp"),
        title: B("Three mistakes this lesson just prevented", "Ba lỗi bài học này vừa giúp bạn tránh"),
        body: B("<b>1.</b> Computing before the month's import is committed. <b>2.</b> Running Mid-cycle when you meant End-cycle. <b>3.</b> Submitting for approval without opening the flagged payslips.", "<b>1.</b> Tính lương khi dữ liệu tháng chưa được ghi nhận. <b>2.</b> Chạy Giữa kỳ trong khi định chạy Cuối kỳ. <b>3.</b> Trình phê duyệt mà chưa mở các phiếu bị gắn cờ."),
      },
    ],
    quiz: {
      q: B("You computed July for Retail and then spot that one employee's overtime input is wrong. What is the safest next step?", "Bạn đã tính lương tháng 7 cho Bán lẻ, rồi phát hiện dữ liệu tăng ca của một nhân viên bị sai. Bước an toàn nhất là gì?"),
      opts: [
        { t: B("Edit the net amount directly on the payslip", "Sửa thẳng số thực nhận trên phiếu lương"), ok: false,
          expl: B("Editing outputs breaks the formula trail — the slip no longer matches its inputs, and the next recompute silently undoes your fix.", "Sửa kết quả làm đứt vết công thức — phiếu không còn khớp dữ liệu đầu vào, và lần tính lại sau sẽ âm thầm xoá sửa đổi của bạn.") },
        { t: B("Fix the overtime input, then recompute the draft", "Sửa dữ liệu tăng ca, rồi tính lại bản nháp"), ok: true,
          expl: B("Drafts exist exactly for this: fix the input, recompute, and every dependent line (gross, PIT, net) corrects itself.", "Bản nháp sinh ra chính là để làm vậy: sửa đầu vào, tính lại, và mọi dòng liên quan (tổng thu nhập, thuế, thực nhận) tự đúng theo.") },
        { t: B("Approve now and fix it next month", "Cứ phê duyệt, tháng sau sửa"), ok: false,
          expl: B("That turns a 30-second fix into a Retro Adjustment next month — and an employee paid wrongly today.", "Điều đó biến một chỉnh sửa 30 giây thành Điều chỉnh hồi tố tháng sau — và một nhân viên bị trả sai ngay hôm nay.") },
      ],
    },
  },

  L2: {
    id: "L2", station: "statutory", mins: 6,
    title: B("Statutory — insurance & tax, demystified", "Bảo hiểm & Thuế — hiểu tường tận"),
    steps: [
      {
        screen: "statutory", target: null,
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("The rules the law writes for you", "Các quy tắc do pháp luật quy định"),
        body: B("This screen holds Vietnam's statutory rates: <b>BHXH</b> (social), <b>BHYT</b> (health), <b>BHTN</b> (unemployment) and the <b>PIT</b> table. You don't invent these numbers — you keep them current.", "Màn hình này lưu các tỷ lệ bắt buộc tại Việt Nam: <b>BHXH</b>, <b>BHYT</b>, <b>BHTN</b> và biểu <b>thuế TNCN</b>. Bạn không tự nghĩ ra các con số này — việc của bạn là giữ chúng luôn đúng hiện hành."),
      },
      {
        screen: "statutory", target: "st-policy",
        kicker: B("Reading the policy", "Đọc chính sách"),
        title: B("Who pays what", "Ai đóng bao nhiêu"),
        body: B("Each line has an <b>employee share</b> (deducted from the payslip) and an <b>employer share</b> (a company cost that never appears in net pay). BHXH: 8% / 17.5% · BHYT: 1.5% / 3% · BHTN: 1% / 1%.", "Mỗi dòng gồm <b>phần người lao động</b> (khấu trừ trên phiếu lương) và <b>phần doanh nghiệp</b> (chi phí công ty, không xuất hiện trong thực nhận). BHXH: 8% / 17,5% · BHYT: 1,5% / 3% · BHTN: 1% / 1%."),
      },
      {
        screen: "statutory", target: "st-cap",
        kicker: B("The base & cap", "Mức đóng & trần"),
        title: B("Insurance is not computed on full salary", "Bảo hiểm không tính trên toàn bộ lương"),
        body: B("Contributions apply to the <b>registered insurance base</b> (often the contract base salary), capped at 20× the reference wage. Mai's base is ₫12,000,000 — so BHXH is 8% × 12,000,000 = <b>₫960,000</b>, even in a month with overtime.", "Bảo hiểm tính trên <b>mức lương đóng BH đã đăng ký</b> (thường là lương cơ bản trên hợp đồng), có trần 20 lần lương tham chiếu. Lương cơ bản của Mai là 12.000.000 ₫ — nên BHXH là 8% × 12.000.000 = <b>960.000 ₫</b>, kể cả tháng có tăng ca."),
      },
      {
        screen: "statutory", target: "st-pit",
        kicker: B("The tax table", "Biểu thuế"),
        title: B("PIT is progressive — and kind at the bottom", "Thuế TNCN luỹ tiến — nhẹ ở bậc thấp"),
        body: B("Taxable income = gross − insurance − <b>₫11m personal deduction</b> − ₫4.4m per dependant. Mai: 14,280,000 − 1,260,000 − 11,000,000 = ₫2,020,000 → all in the 5% band → PIT <b>₫101,000</b>.", "Thu nhập chịu thuế = tổng thu nhập − bảo hiểm − <b>giảm trừ bản thân 11 triệu</b> − 4,4 triệu mỗi người phụ thuộc. Với Mai: 14.280.000 − 1.260.000 − 11.000.000 = 2.020.000 ₫ → trọn bậc 5% → thuế <b>101.000 ₫</b>."),
      },
      {
        screen: "payslips", target: "sl-bhxh", trace: { from: "st-policy-mem", label: B("Setup → Payslip", "Thiết lập → Phiếu lương") },
        kicker: B("The connection", "Sợi dây liên kết"),
        title: B("Watch Setup become a payslip line", "Xem Thiết lập biến thành dòng phiếu lương"),
        body: B("The 8% you saw in Statutory is exactly this <b>−₫960,000 BHXH</b> line on Mai's July slip. Every deduction on every slip traces back to a rate on that policy screen — change the rate, and thousands of lines change.", "Con số 8% bạn thấy ở Bảo hiểm & Thuế chính là dòng <b>−960.000 ₫ BHXH</b> trên phiếu tháng 7 của Mai. Mọi khoản khấu trừ trên mọi phiếu đều truy về một tỷ lệ ở màn hình chính sách — đổi tỷ lệ, hàng nghìn dòng thay đổi."),
      },
      {
        screen: "payslips", target: "sl-net", morph: true,
        kicker: B("Before & after", "Trước & sau"),
        title: B("What a 0.5% change does", "Thay đổi 0,5% gây ra điều gì"),
        body: B("If BHYT rose from 1.5% to 2%, Mai's deduction grows ₫60,000, her taxable income falls, and net drops from <b>₫12,919,000</b> to <b>₫12,862,000</b>. Small setup numbers, real salary effects — watch the slip update.", "Nếu BHYT tăng từ 1,5% lên 2%, khấu trừ của Mai tăng 60.000 ₫, thu nhập chịu thuế giảm theo, và thực nhận giảm từ <b>12.919.000 ₫</b> xuống <b>12.862.000 ₫</b>. Con số thiết lập nhỏ, tác động lương thật — hãy nhìn phiếu lương cập nhật."),
      },
      {
        screen: "statutory", target: "st-effective",
        kicker: B("The danger zone", "Vùng nguy hiểm"),
        title: B("Effective dates protect open runs", "Ngày hiệu lực bảo vệ các đợt đang mở"),
        body: B("Never edit a live rate in place. Create a <b>new policy version with an effective date</b>. If you change rates while July is still open, the next recompute applies new rates to an old month — a silent compliance error.", "Đừng bao giờ sửa đè tỷ lệ đang chạy. Hãy tạo <b>phiên bản chính sách mới kèm ngày hiệu lực</b>. Nếu đổi tỷ lệ khi tháng 7 còn mở, lần tính lại kế tiếp sẽ áp tỷ lệ mới cho tháng cũ — một lỗi tuân thủ âm thầm."),
        consequence: B("Affects: every future payslip of every division using this policy. Reversible: versions can be ended, but recomputed history cannot self-heal — verify open runs first.", "Ảnh hưởng: mọi phiếu lương tương lai của mọi bộ phận dùng chính sách này. Hoàn tác: có thể kết thúc phiên bản, nhưng lịch sử đã tính lại không tự lành — hãy kiểm tra các đợt đang mở trước."),
      },
    ],
    quiz: {
      q: B("HR announces BHYT will change on 1 August. The July run is still awaiting GM approval. What should you do?", "Nhân sự thông báo BHYT thay đổi từ 1/8. Đợt lương tháng 7 vẫn đang chờ TGĐ phê duyệt. Bạn nên làm gì?"),
      opts: [
        { t: B("Edit the current policy's rate right now", "Sửa ngay tỷ lệ trên chính sách hiện hành"), ok: false,
          expl: B("If anything triggers a July recompute, the old month gets the new rate — wrong deductions on an already-reviewed run.", "Nếu có gì đó khiến tháng 7 tính lại, tháng cũ sẽ nhận tỷ lệ mới — khấu trừ sai trên một đợt đã soát xét.") },
        { t: B("Create a new policy version effective 1 August", "Tạo phiên bản chính sách mới, hiệu lực từ 1/8"), ok: true,
          expl: B("Exactly. July keeps its rates, August gets the new ones, and the change is documented with a date — auditors love you.", "Chính xác. Tháng 7 giữ nguyên tỷ lệ cũ, tháng 8 nhận tỷ lệ mới, và thay đổi được ghi nhận kèm ngày — kiểm toán sẽ rất hài lòng.") },
        { t: B("Wait until someone asks about it", "Cứ chờ tới khi có người hỏi"), ok: false,
          expl: B("August's first run would compute on outdated rates — every August payslip wrong by the same amount.", "Đợt đầu tiên của tháng 8 sẽ chạy trên tỷ lệ lỗi thời — mọi phiếu tháng 8 sai cùng một kiểu.") },
      ],
    },
  },
};

// --------------------------------------------------------------- simulator
const MISSIONS = [
  {
    id: "m1", group: "payrun", icon: "zap", mins: 5, conf: { key: "run", gain: 25 }, full: true,
    title: B("Run the July pay run", "Chạy đợt lương tháng 7"),
    desc: B("Compute Retail's July payroll, handle the anomaly the data hides, and submit for approval.", "Tính lương tháng 7 cho Bán lẻ, xử lý điểm bất thường ẩn trong dữ liệu, và trình phê duyệt."),
  },
  {
    id: "m2", group: "setup", icon: "shield", mins: 4, conf: { key: "setup", gain: 30 }, full: true,
    title: B("Apply a BHYT rate change", "Áp dụng thay đổi tỷ lệ BHYT"),
    desc: B("A (fictional) decree changes BHYT. Version the policy correctly and preview the payslip impact.", "Một nghị định (giả lập) thay đổi BHYT. Tạo phiên bản chính sách đúng cách và xem trước tác động lên phiếu lương."),
  },
  {
    id: "m3", group: "payrun", icon: "clipboard-check", mins: 4, conf: { key: "approve", gain: 20 }, full: false,
    title: B("Review & approve like a manager", "Soát xét & phê duyệt như một quản lý"),
    desc: B("Walk a submitted run through HR review: sample slips, check flags, approve or reject with reasons.", "Đưa một đợt đã trình qua vòng HR: chọn mẫu phiếu, kiểm tra cờ, phê duyệt hoặc từ chối kèm lý do."),
    outline: [
      B("Open the run waiting in HR review", "Mở đợt đang chờ ở vòng HR"),
      B("Sample 3 payslips + every flagged one", "Chọn mẫu 3 phiếu + mọi phiếu bị gắn cờ"),
      B("Compare totals against June (variance view)", "So tổng với tháng 6 (màn hình biến động)"),
      B("Approve — or reject with a written reason", "Phê duyệt — hoặc từ chối kèm lý do bằng văn bản"),
    ],
  },
  {
    id: "m4", group: "setup", icon: "calculator", mins: 6, conf: { key: "formula", gain: 30 }, full: false,
    title: B("Add a meal allowance to a config", "Thêm phụ cấp ăn trưa vào cấu hình"),
    desc: B("Create a new component in the Formula Engine, wire it into gross, and preview before publishing.", "Tạo thành phần mới trong Công thức lương, nối vào tổng thu nhập, và xem trước rồi mới phát hành."),
    outline: [
      B("Duplicate the live config as a draft", "Nhân bản cấu hình đang chạy thành bản nháp"),
      B("Add component PCAT (₫730,000, non-taxable cap)", "Thêm thành phần PCAT (730.000 ₫, có trần miễn thuế)"),
      B("Reference it in the GROSS formula", "Tham chiếu nó trong công thức GROSS"),
      B("Preview 3 sample employees, then publish v13", "Xem trước 3 nhân viên mẫu, rồi phát hành v13"),
    ],
  },
];

// Mission 1 step machine (ids used by app.js)
const M1_STEPS = [
  { id: "open", nav: "runpayroll",
    t: B("Open Run Payroll", "Mở Chạy bảng lương"),
    d: B("Find it in the Pay Run section of the sidebar.", "Tìm trong mục Chạy lương ở thanh bên."),
    hint: B("The glowing item on the left — Run Payroll.", "Mục đang phát sáng bên trái — Chạy bảng lương.") },
  { id: "division",
    t: B("Choose the Retail division", "Chọn bộ phận Bán lẻ"),
    d: B("July's inputs are ready for Retail only.", "Dữ liệu tháng 7 mới sẵn sàng cho Bán lẻ."),
    hint: B("Use the Division dropdown. Notice how the config preview follows your choice.", "Dùng ô chọn Bộ phận. Để ý phần xem trước cấu hình đổi theo lựa chọn của bạn.") },
  { id: "compute",
    t: B("Compute — after reading the consequences", "Tính — sau khi đọc kỹ hậu quả"),
    d: B("Payobook will show you what the action affects first.", "Payobook sẽ cho bạn biết thao tác ảnh hưởng tới đâu trước."),
    hint: B("Press “Compute payslips”. Read the consequence card before confirming.", "Bấm “Tính phiếu lương”. Đọc thẻ hậu quả trước khi xác nhận.") },
  { id: "inspect",
    t: B("Inspect the flagged payslip", "Kiểm tra phiếu bị gắn cờ"),
    d: B("One of 48 slips needs your judgement.", "1 trong 48 phiếu cần bạn phán đoán."),
    hint: B("Click the amber row — Trần Văn Hùng.", "Bấm vào dòng màu hổ phách — Trần Văn Hùng.") },
  { id: "decide",
    t: B("Make the call", "Ra quyết định"),
    d: B("Expected vs actual don't match. What do you do?", "Kỳ vọng và thực tế lệch nhau. Bạn xử lý thế nào?"),
    hint: B("In real payroll you'd verify against the timesheet before accepting a 250% spike.", "Trong thực tế, bạn cần đối chiếu bảng chấm công trước khi chấp nhận mức tăng 250%.") },
  { id: "submit",
    t: B("Submit for approval", "Trình phê duyệt"),
    d: B("Send the run into the Officer → HR → GM pipeline.", "Đưa đợt lương vào quy trình CV tính lương → HR → TGĐ."),
    hint: B("The Submit button on the results panel.", "Nút Trình phê duyệt trên bảng kết quả.") },
];

const M2_STEPS = [
  { id: "open", nav: "statutory",
    t: B("Open Statutory", "Mở Bảo hiểm & Thuế"),
    d: B("Setup section, shield icon.", "Mục Thiết lập, biểu tượng khiên."),
    hint: B("The glowing sidebar item.", "Mục đang phát sáng trên thanh bên.") },
  { id: "newversion",
    t: B("Start a new policy version", "Tạo phiên bản chính sách mới"),
    d: B("Never edit live rates in place.", "Không bao giờ sửa đè tỷ lệ đang chạy."),
    hint: B("Use “New version (practice)” on the policy card.", "Dùng “Phiên bản mới (thực hành)” trên thẻ chính sách.") },
  { id: "rate",
    t: B("Set BHYT employee share to 2.0%", "Đặt phần người lao động BHYT là 2,0%"),
    d: B("The fictional decree raises it from 1.5%.", "Nghị định giả lập nâng từ 1,5%."),
    hint: B("Change only the BHYT employee field.", "Chỉ thay đổi ô phần người lao động của BHYT.") },
  { id: "effective",
    t: B("Choose the effective date", "Chọn ngày hiệu lực"),
    d: B("July is still open. When should this start?", "Tháng 7 vẫn đang mở. Nên bắt đầu từ khi nào?"),
    hint: B("Think about what happens if July recomputes.", "Nghĩ xem điều gì xảy ra nếu tháng 7 được tính lại.") },
  { id: "preview",
    t: B("Preview the impact, then commit", "Xem trước tác động, rồi ghi nhận"),
    d: B("See Mai's slip before/after, then save the version.", "Xem phiếu của Mai trước/sau, rồi lưu phiên bản."),
    hint: B("The comparison shows exactly which lines move.", "Bảng so sánh chỉ rõ những dòng nào thay đổi.") },
];

// --------------------------------------------------------------- companion
// Per-screen context blurbs + suggested question ids
const SCREEN_CTX = {
  dashboard: { blurb: B("Your command centre — live headcount, monthly cost and what's waiting for you.", "Trung tâm chỉ huy — nhân sự, chi phí tháng và những việc đang chờ bạn."), chips: ["whatnext", "whatpage", "practice"] },
  runpayroll: { blurb: B("Creates draft payslips for one division and period via the formula engine.", "Tạo phiếu lương nháp cho một bộ phận và một kỳ bằng công thức."), chips: ["whatpage", "affectrun", "checkfinal", "practice"] },
  payruns: { blurb: B("Every pay run and its approval stage, Draft through Done.", "Mọi đợt tính lương và trạng thái phê duyệt, từ Nháp đến Hoàn tất."), chips: ["approve", "checkfinal", "fixerror"] },
  payslips: { blurb: B("Line-by-line review of each employee's slip.", "Soát xét từng dòng phiếu lương của mỗi nhân viên."), chips: ["whydiff", "bhxh", "fixerror"] },
  import: { blurb: B("Guided import: preview, score and fix before anything commits.", "Nhập liệu có hướng dẫn: xem trước, chấm điểm và sửa lỗi trước khi ghi nhận."), chips: ["whatpage", "whatnext"] },
  fullfinal: { blurb: B("Final settlements for departing employees.", "Quyết toán cho nhân viên thôi việc."), chips: ["whatpage", "whatnext"] },
  proration: { blurb: B("The audit trail behind every part-month amount.", "Vết kiểm toán sau mỗi khoản lương tính theo ngày công."), chips: ["whatpage", "whydiff"] },
  retro: { blurb: B("Backdated corrections applied to current runs.", "Hiệu chỉnh lùi ngày áp vào kỳ hiện tại."), chips: ["whatpage", "fixerror"] },
  formula: { blurb: B("The visible rulebook: every payslip line as a named formula.", "Bộ quy tắc nhìn thấy được: mỗi dòng phiếu lương là một công thức có tên."), chips: ["whysetup", "whatpage", "practice"] },
  structures: { blurb: B("Legacy rule sets kept for historical payslips.", "Bộ quy tắc cũ, giữ cho phiếu lương lịch sử."), chips: ["whatpage", "whysetup"] },
  statutory: { blurb: B("BHXH · BHYT · BHTN rates and the PIT table.", "Tỷ lệ BHXH · BHYT · BHTN và biểu thuế TNCN."), chips: ["changerate", "bhxh", "whysetup"] },
  integrations: { blurb: B("Connectors that feed attendance & HR data automatically.", "Đầu nối tự động cấp dữ liệu chấm công & nhân sự."), chips: ["whatpage", "whatnext"] },
  approvals: { blurb: B("Runs awaiting your sign-off, filtered to your role.", "Các đợt chờ bạn ký duyệt, lọc theo vai trò."), chips: ["approve", "checkfinal"] },
};

// Q&A knowledge base. Blocks render in order.
const QA = [
  {
    id: "whatpage", match: ["what does this page do", "what is this", "trang này", "màn hình này làm gì", "what page"],
    label: B("What does this page do?", "Trang này để làm gì?"),
    perScreen: true, // answer text comes from SCREEN_CTX + station outline
  },
  {
    id: "whatnext", match: ["what should i do next", "next", "làm gì tiếp", "tiếp theo"],
    label: B("What should I do next?", "Tôi nên làm gì tiếp theo?"),
    roleAware: {
      officer: {
        blocks: [
          { p: B("It's the 6th — July's inputs are committed but Retail hasn't been computed. As Payroll Officer, your next move:", "Hôm nay mùng 6 — dữ liệu tháng 7 đã ghi nhận nhưng Bán lẻ chưa được tính. Với vai trò Chuyên viên tính lương, bước tiếp theo của bạn:") },
          { steps: [
            { t: B("Open <b>Run Payroll</b>", "Mở <b>Chạy bảng lương</b>"), target: "nav-runpayroll" },
            { t: B("Division: Retail — Hà Nội · Period: July 2026 · End-cycle", "Bộ phận: Bán lẻ — Hà Nội · Kỳ: Tháng 7/2026 · Cuối kỳ"), target: "pw-division" },
            { t: B("Compute, then open every flagged slip", "Tính, rồi mở mọi phiếu bị gắn cờ"), target: "pw-compute" },
          ] },
          { links: ["lesson:L1", "mission:m1"] },
        ],
      },
      hr: { blocks: [
        { p: B("One run — <b>Retail — July 2026</b> — is waiting in HR review. Sample a few slips, open every flag, then approve or reject with a reason.", "Một đợt — <b>Bán lẻ — Tháng 7/2026</b> — đang chờ ở vòng HR. Hãy chọn mẫu vài phiếu, mở mọi cờ cảnh báo, rồi phê duyệt hoặc từ chối kèm lý do.") },
        { steps: [ { t: B("Open <b>Approvals</b>", "Mở <b>Phê duyệt</b>"), target: "nav-approvals" }, { t: B("Review flagged payslips first", "Soát các phiếu gắn cờ trước") }, { t: B("Approve → the run moves to GM", "Phê duyệt → đợt chuyển sang TGĐ") } ] },
        { links: ["mission:m3"] },
      ] },
      gm: { blocks: [
        { p: B("Nothing is waiting at your gate right now. When HR approves July, you'll see it in <b>Approvals</b> — your check is totals vs last month, not line-by-line.", "Hiện chưa có gì chờ ở cổng của bạn. Khi HR duyệt tháng 7, đợt sẽ xuất hiện trong <b>Phê duyệt</b> — việc của bạn là so tổng với tháng trước, không phải soát từng dòng.") },
      ] },
      viewer: { blocks: [
        { p: B("Your role is read-only, so there is no required action. You can browse payslips and reports, and learn any workflow safely in Practice Studio.", "Vai trò của bạn chỉ xem, nên không có việc bắt buộc. Bạn có thể xem phiếu lương, báo cáo, và học mọi quy trình an toàn trong Xưởng thực hành.") },
        { links: ["mission:m1"] },
      ] },
    },
  },
  {
    id: "whydiff", match: ["why is this employee", "pay different", "lương khác", "sao lương", "khác tháng trước"],
    label: B("Why is Mai's pay different from June?", "Sao lương của Mai khác tháng 6?"),
    blocks: [
      { p: B("Short answer: <b>overtime</b>. Mai's July net is ₫855,000 higher than June, and it decomposes exactly:", "Trả lời ngắn: <b>tăng ca</b>. Thực nhận tháng 7 của Mai cao hơn tháng 6 đúng 855.000 ₫, phân tách như sau:") },
      { calc: { title: B("June → July, line by line", "Tháng 6 → Tháng 7, theo từng dòng"), rows: [
        [B("Overtime", "Tăng ca"), "600,000 → 1,500,000", "+900,000"],
        [B("Insurance (base unchanged)", "Bảo hiểm (mức đóng không đổi)"), "1,260,000 → 1,260,000", "0"],
        [B("PIT (more taxable income)", "Thuế TNCN (thu nhập chịu thuế tăng)"), "56,000 → 101,000", "−45,000"],
        [B("Net", "Thực nhận"), "12,064,000 → 12,919,000", "+855,000"],
      ] } },
      { p: B("Insurance didn't move because BHXH/BHYT/BHTN are computed on her registered base (₫12m), not on overtime.", "Bảo hiểm không đổi vì BHXH/BHYT/BHTN tính trên mức lương đóng BH đã đăng ký (12 triệu), không tính trên tăng ca.") },
      { src: B("Mai's July & June payslips · HOASEN_RETAIL_END v12", "Phiếu lương tháng 7 & 6 của Mai · HOASEN_RETAIL_END v12") },
      { more: { label: null, body: B("Want the general method? Open any two slips side by side in Payslips, or Proration Audit if the employee joined/left mid-month.", "Muốn phương pháp tổng quát? Mở hai phiếu cạnh nhau trong Phiếu lương, hoặc Soát xét ngày công nếu nhân viên vào/nghỉ giữa tháng.") } },
    ],
  },
  {
    id: "changerate", match: ["what happens if i change", "change this rate", "đổi tỷ lệ", "nếu tôi thay đổi", "sửa tỷ lệ"],
    label: B("What happens if I change this rate?", "Nếu tôi đổi tỷ lệ này thì sao?"),
    blocks: [
      { p: B("Changing a statutory rate re-prices <b>every future payslip in every division</b> that uses this policy — for BHYT +0.5%, Mai alone loses ₫57,000/month net.", "Đổi một tỷ lệ bắt buộc sẽ tính lại <b>mọi phiếu lương tương lai của mọi bộ phận</b> dùng chính sách này — chỉ riêng BHYT +0,5%, Mai đã giảm 57.000 ₫ thực nhận mỗi tháng.") },
      { warn: B("The July run is still open. If you edit the live policy now and July recomputes, an old month gets new rates. Create a dated new version instead.", "Đợt tháng 7 vẫn đang mở. Nếu bạn sửa chính sách đang chạy và tháng 7 tính lại, tháng cũ sẽ nhận tỷ lệ mới. Hãy tạo phiên bản mới kèm ngày hiệu lực.") },
      { steps: [
        { t: B("Create a <b>new policy version</b>", "Tạo <b>phiên bản chính sách mới</b>"), target: "st-policy" },
        { t: B("Effective date: first day of the next closed-off period", "Ngày hiệu lực: ngày đầu của kỳ kế tiếp"), target: "st-effective" },
        { t: B("Preview one payslip before saving", "Xem trước một phiếu lương rồi mới lưu") },
      ] },
      { links: ["mission:m2", "lesson:L2"] },
      { src: B("Statutory policy VN-2026 · effective-date rules", "Chính sách VN-2026 · quy tắc ngày hiệu lực") },
    ],
  },
  {
    id: "affectrun", match: ["affect the current pay run", "ảnh hưởng đợt", "đợt hiện tại"],
    label: B("Will this affect the current pay run?", "Việc này có ảnh hưởng đợt lương hiện tại?"),
    blocks: [
      { p: B("Computing here only creates <b>drafts</b> for the division and period you choose — it cannot touch a run that is already submitted or approved.", "Tính ở đây chỉ tạo <b>bản nháp</b> cho bộ phận và kỳ bạn chọn — không thể chạm tới đợt đã trình hoặc đã duyệt.") },
      { ok: B("Safe: recomputing drafts, deleting drafts. Gated: anything after submission requires the approval chain (or a rejection back to draft).", "An toàn: tính lại bản nháp, xoá bản nháp. Có cổng chặn: mọi thứ sau khi trình cần chuỗi phê duyệt (hoặc bị từ chối để về nháp).") },
    ],
  },
  {
    id: "checkfinal", match: ["before finalising", "before finalizing", "trước khi chốt", "kiểm tra gì trước"],
    label: B("What should I check before finalising?", "Cần kiểm tra gì trước khi chốt?"),
    blocks: [
      { p: B("The pre-approval checklist experienced officers actually use:", "Danh sách kiểm tra trước phê duyệt mà các chuyên viên giàu kinh nghiệm thật sự dùng:") },
      { steps: [
        { t: B("Headcount = expected (48)? Joiners/leavers accounted for?", "Sĩ số = kỳ vọng (48)? Người vào/nghỉ đã tính đủ?") },
        { t: B("Every flagged payslip opened and resolved", "Mọi phiếu gắn cờ đã mở và xử lý") },
        { t: B("Total net vs last month — is the variance explainable?", "Tổng thực nhận so tháng trước — biến động giải thích được không?") },
        { t: B("Statutory lines present on a sample slip (BHXH/BHYT/BHTN/PIT)", "Các dòng bắt buộc có mặt trên phiếu mẫu (BHXH/BHYT/BHTN/TNCN)") },
        { t: B("Bank details valid for new joiners", "Thông tin ngân hàng hợp lệ cho nhân viên mới") },
      ] },
      { links: ["mission:m1"] },
    ],
  },
  {
    id: "fixerror", match: ["correct this error", "fix", "sửa lỗi", "làm sao sửa"],
    label: B("Show me how to correct an error", "Chỉ tôi cách sửa một lỗi"),
    showme: true,
    blocks: [
      { p: B("Golden rule: <b>fix the input, never the output</b>. For a wrong overtime figure on a draft run:", "Nguyên tắc vàng: <b>sửa đầu vào, không sửa kết quả</b>. Với số tăng ca sai trên đợt còn nháp:") },
      { steps: [
        { t: B("Open the payslip and find the wrong line", "Mở phiếu lương và tìm dòng sai"), target: "nav-payslips" },
        { t: B("Trace it to its input (the slip shows the source)", "Truy về dữ liệu đầu vào (phiếu chỉ rõ nguồn)") },
        { t: B("Correct the input via Import Data or the employee record", "Sửa đầu vào qua Nhập dữ liệu hoặc hồ sơ nhân viên"), target: "nav-import" },
        { t: B("Recompute the draft — dependent lines fix themselves", "Tính lại bản nháp — các dòng liên quan tự đúng theo") },
      ] },
      { warn: B("If the run is already approved (Done), do not reopen it — use Retro Adjustments so the correction lands in the next run with an audit trail.", "Nếu đợt đã duyệt (Hoàn tất), đừng mở lại — hãy dùng Điều chỉnh hồi tố để hiệu chỉnh rơi vào kỳ sau kèm vết kiểm toán.") },
    ],
  },
  {
    id: "bhxh", match: ["bhxh", "insurance", "social insurance", "bảo hiểm", "explain bhxh"],
    label: B("Explain BHXH on this slip", "Giải thích BHXH trên phiếu này"),
    simpler: B("Think of BHXH like a shared piggy bank the law requires: every month you put in 8% of your contracted base salary (not your bonuses), and your company puts in even more (17.5%) on your behalf. It funds your pension, sick leave and maternity leave.", "Hãy hình dung BHXH như một ống heo chung mà pháp luật yêu cầu: mỗi tháng bạn bỏ vào 8% lương cơ bản trên hợp đồng (không tính thưởng), và công ty bỏ thêm phần lớn hơn (17,5%) cho bạn. Quỹ này chi trả lương hưu, ốm đau và thai sản."),
    blocks: [
      { p: B("BHXH is social insurance. On Mai's slip: employee share = 8% × insurance base ₫12,000,000 = <b>₫960,000</b> (deducted). Her employer also pays 17.5% (₫2,100,000) — a company cost that never reduces her net.", "BHXH là bảo hiểm xã hội. Trên phiếu của Mai: phần người lao động = 8% × mức đóng 12.000.000 ₫ = <b>960.000 ₫</b> (khấu trừ). Doanh nghiệp đóng thêm 17,5% (2.100.000 ₫) — chi phí công ty, không làm giảm thực nhận của cô ấy."),
      },
      { calc: { title: B("Mai — July statutory deductions", "Mai — khấu trừ bắt buộc tháng 7"), rows: [
        ["BHXH (8%)", "960,000", ""], ["BHYT (1.5%)", "180,000", ""], ["BHTN (1%)", "120,000", ""],
        [B("Total insurance", "Tổng bảo hiểm"), "1,260,000", ""],
      ] } },
      { src: B("Statutory → VN-2026 policy · Mai's July payslip", "Bảo hiểm & Thuế → chính sách VN-2026 · phiếu tháng 7 của Mai") },
    ],
  },
  {
    id: "whysetup", match: ["why do i need this setup", "sao cần thiết lập", "cần cấu hình"],
    label: B("Why do I need this setup?", "Vì sao tôi cần phần thiết lập này?"),
    blocks: [
      { p: B("Setup is where pay logic lives so that Pay Run can be one click. Every minute invested here removes a manual step from all twelve monthly runs.", "Thiết lập là nơi chứa logic tính lương, để Chạy lương chỉ còn một cú bấm. Mỗi phút đầu tư ở đây bớt đi một thao tác thủ công trong cả mười hai kỳ lương của năm.") },
      { steps: [
        { t: B("Formula Engine → how each line is computed", "Công thức lương → mỗi dòng được tính thế nào"), target: "nav-formula" },
        { t: B("Statutory → the rates the law sets", "Bảo hiểm & Thuế → tỷ lệ do luật định"), target: "nav-statutory" },
        { t: B("Integrations → inputs arrive without retyping", "Tích hợp → dữ liệu tự về, khỏi gõ tay"), target: "nav-integrations" },
      ] },
    ],
  },
  {
    id: "approve", match: ["how do i approve", "approve", "phê duyệt thế nào", "duyệt"],
    label: B("How do I approve this run?", "Tôi phê duyệt đợt này thế nào?"),
    permission: true, // varies strongly by role
  },
  {
    id: "practice", match: ["practise", "practice", "thực hành", "làm thử"],
    label: B("Let me practise this safely", "Cho tôi thực hành an toàn"),
    blocks: [
      { p: B("Good instinct — Practice Studio has a fictional 48-person company where nothing can go wrong for real. Recommended for this screen:", "Bản năng tốt đấy — Xưởng thực hành có một công ty giả lập 48 người, nơi không gì hỏng thật được. Gợi ý cho màn hình này:") },
      { links: ["mission:m1", "mission:m2"] },
    ],
  },
];

// Approve answers per role (permission-aware demo)
const APPROVE_BY_ROLE = {
  officer: { blocks: [
    { p: B("Your role (Payroll Officer) owns the <b>first</b> gate. You can submit a draft run and approve at the Officer tier — HR review and GM approval come after you.", "Vai trò của bạn (Chuyên viên tính lương) giữ cổng <b>đầu tiên</b>. Bạn có thể trình đợt nháp và duyệt ở vòng Chuyên viên — HR và TGĐ duyệt sau bạn.") },
    { steps: [ { t: B("Open the run card in Draft", "Mở thẻ đợt ở cột Nháp"), target: "k-draft" }, { t: B("Submit for approval", "Trình phê duyệt") }, { t: B("Approve your tier once checks pass", "Duyệt vòng của bạn khi kiểm tra đạt") } ] },
    { src: B("Approval chain: Draft → Officer → HR → GM → Done", "Chuỗi phê duyệt: Nháp → CV tính lương → HR → TGĐ → Hoàn tất") },
  ] },
  hr: { blocks: [
    { p: B("As HR Manager you approve the <b>HR review</b> tier. Open Approvals, review flags and variance, then Approve — or Reject with a written reason (the run returns to draft).", "Là Trưởng phòng Nhân sự, bạn duyệt vòng <b>HR soát xét</b>. Mở Phê duyệt, kiểm tra cờ và biến động, rồi Phê duyệt — hoặc Từ chối kèm lý do (đợt sẽ quay về nháp).") },
  ] },
  gm: { blocks: [
    { p: B("As General Director you hold the <b>final</b> gate. Your approval marks the run Done — after that, payment files can be generated. Check totals vs last month; the detail was HR's job.", "Là Tổng Giám đốc, bạn giữ cổng <b>cuối cùng</b>. Bạn duyệt là đợt Hoàn tất — sau đó có thể xuất file chi lương. Hãy so tổng với tháng trước; chi tiết là việc của HR.") },
  ] },
  viewer: { blocks: [
    { p: B("Your current role can't approve pay runs — approval needs the Payroll Officer, HR Manager or General Director role. You can watch how it works, though:", "Vai trò hiện tại của bạn không thể phê duyệt — cần vai trò Chuyên viên tính lương, Trưởng phòng Nhân sự hoặc Tổng Giám đốc. Nhưng bạn có thể xem quy trình vận hành:") },
    { links: ["mission:m3", "lesson:L1"] },
    { warn: B("If you believe you should have approval rights, ask your administrator (Roles & Access).", "Nếu bạn cho rằng mình cần quyền phê duyệt, hãy liên hệ quản trị viên (Roles & Access).") },
  ] },
};
