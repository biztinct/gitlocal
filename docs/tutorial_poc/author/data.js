/* =============================================================================
   Payobook Learn — CONTENT SPINE  (schema 1.1)
   -----------------------------------------------------------------------------
   ONE content model feeds every learning surface: the Guided Journey, the
   always-on Coach and the practice missions. Nothing below is duplicated per
   surface.

   THIS FILE IS TEACHING CONTENT. Facts about the product — the menu inventory,
   the real state keys, the worked example's numbers — live in
   `practice-data.js` and are referenced from here as CASE / PRACTICE / MENU.
   If you are about to type a product fact into a lesson step, put it there
   instead: `tools/check_contract.py` can only guard what lives in one place.

   `B` and everything in practice-data.js are already defined: the dumper loads
   that file into the same context first, so redeclaring `B` here would throw.

   Schema 1.1
     Station    { id, icon, title*, desc*, required, star, mins, after,
                  outline*{what,why,when,prereq,mistakes[]} }
     Lesson     { id, station, mins, steps[], quiz }
     LessonStep { screen, anchor, kicker*, title*, body*, tip?*, consequence?*,
                  moment?{kind:trace|morph|calc|pipeline|list, from,to,chain,which} }
     Quiz       { question*, options[{text*, correct, explanation*}] }
     Mission    { id, group, icon, mins, full, conf{key,gain}, title*, desc*,
                  outlineNote?*, consequence*{title,scope,reversible,verify},
                  anomaly*{title,body}, debrief{did[]*, checklist[]*} }
     MissionStep{ id, nav?, target?, instruction*, detail?*, hint?*,
                  decision?, consequence?, undo?, options[], recovery{} }
     Screen     { blurb*, next*, chips[] }
     QAIntent   { id, match[], label*, screens, dynamic?, showMe?, simpler?*,
                  practice?, offer?, blocks[] | roleVariants{} }
     Column     [key, label*, body*]
   * = translatable; EVERY translatable ships a complete value in BOTH
   languages. The generator has no fallback — an English-only value would ship
   English to a Vietnamese reader, and tests/test_bundle.py fails the build
   for it.

   THE VIETNAMESE IS WRITTEN FOR A PAYROLL PROFESSIONAL, not machine-mapped
   from the English: BHXH/BHYT/BHTN, thuế TNCN, giảm trừ gia cảnh, mức đóng,
   kỳ lương. Tone matches the v1 prototype (docs/tutorial_poc/data.js), which
   was reviewed with that audience in mind.

   MATCH PHRASES ARE DELIBERATELY NOT TRANSLATED. English and Vietnamese live
   in one bag per intent: a learner types in whichever language they are
   thinking in — often mid-shift, often without tone marks — and both have to
   hit the same intent.
   ========================================================================== */

/* =============================================================================
   1. UI CHROME
   -----------------------------------------------------------------------------
   NOT `_t()`. `_t()` binds to the SESSION language, and the brief requires both
   languages switchable live: a learner flips EN/VI mid-lesson and the whole
   surface has to change without a reload, because the person who reaches for
   that toggle is usually mid-sentence in their second language.

   So every key here becomes a learn.string record carrying both languages, and
   the frontend picks. Dotted keys nest: `lines.payrun` is read as
   T("lines.payrun") and is the heading for a Journey line — a line with no
   string renders its own key as a heading, which is exactly what shipped once.
   ========================================================================== */
const I18N = {
  en: {
    /* -- brand + journey map ------------------------------------------- */
    brand: "Payobook",
    // NOT "Learn". That is the sidebar leaf's name, and gettext allows one
    // msgstr per msgid — the two would have to share a Vietnamese translation,
    // and "Học cùng Payobook" is wrong as a topbar suffix. The generator's
    // conflict guard caught this; it is not a stylistic choice.
    learn: "Learning",
    hubTitle: "Your journey",
    hubLead: "Learn the Pay Run desk one screen at a time. Nothing here touches your company's data.",
    yourJourney: "Your journey",
    overall: "Overall",
    badge: "Pay Run badge",
    badgeGot: "Pay Run badge earned",
    search: "Search the journey",
    lines: { payrun: "Pay Run", setup: "Setup" },
    /* -- station cards -------------------------------------------------- */
    fullLesson: "Full lesson",
    outline: "Outline",
    required: "Required",
    optional: "Optional",
    est: "About",
    min: "min",
    notVisible: "Not in your menu",
    notVisibleBody: "This screen is not in your sidebar, so you cannot open it yet. You can still read what it does and what it would take to be given access.",
    outlineNote: "This station is an outline: what it is, why it matters, when to use it and the mistakes it prevents. The full lesson is not written yet.",
    whatIs: "What it is",
    whyMatters: "Why it matters",
    whenUse: "When to use it",
    prereq: "What you need first",
    mistakes: "Mistakes this prevents",
    /* -- the lesson player ---------------------------------------------- */
    step: "Step",
    of: "of",
    back: "Back",
    next: "Next",
    replay: "Play this step again",
    exit: "Leave",
    check: "Understanding check",
    checkNote: "One judgement call. A wrong answer is a way back, never a mark against you.",
    tryAgain: "Try again",
    finish: "Finish",
    continueBtn: "Continue",
    consequence: "Before you do this",
    /* -- missions -------------------------------------------------------- */
    missions: "Practice missions",
    missionsLead: "Do it once where it cannot matter, before you do it where it can.",
    startMission: "Start mission",
    outlineMission: "Outline",
    liveNotYet: "This is a live capstone. It runs against real records in the Payobook demo world, so it opens only for a demo account — the practice mission above teaches the same judgement, safely, wherever you are.",
    liveBadge: "Live \u00b7 demo world",
    liveStart: "Start the live mission",
    liveReal: "This one is real",
    liveRealBody: "Every step below happens in Payobook itself, on records other people can see. Nothing here is a replica, and nothing here is undone for you when you leave.",
    liveNudge: "Rehearse it first?",
    liveNudgeBody: "The practice mission runs the same judgement on a fixture where nothing can matter. You do not have to \u2014 this is a nudge, not a lock.",
    liveNudgeGo: "Open the practice mission",
    liveOpenScreen: "Open the screen",
    liveCheckNow: "Check now",
    liveChecking: "Checking\u2026",
    liveWaiting: "Waiting for you to do this in Payobook",
    liveAck: "I have done this",
    liveNext: "Next",
    liveFinish: "Finish the mission",
    liveLeave: "Leave",
    liveMinimise: "Minimise",
    showHint: "Hint",
    scope: "What this touches",
    reversible: "Can I undo it",
    verify: "What to check first",
    proceed: "I have read this — continue",
    cancelAct: "Go back",
    undoShown: "Undo it",
    debriefTitle: "Debrief",
    whatYouDid: "What you did",
    checklist: "Before doing this for real, always check",
    confGain: "Confidence gained",
    recoveryUsed: "you needed a way back on this run",
    backToMissions: "Back to missions",
    /* -- the Coach ------------------------------------------------------- */
    coachName: "Payobook Coach",
    stuck: "Stuck?",
    askPlaceholder: "Ask about this screen…",
    honest: "I guide — you act. I never compute a run, approve a payslip or change a record for you.",
    groundedIn: "Grounded in this screen:",
    coachNoScreen: "I do not have lessons for this screen yet. Here is what I can answer anywhere.",
    suggested: "Suggested for this screen",
    canAnswer: "What I can answer here",
    showMe: "Show me",
    pointNotHere: "That control is not on this screen right now, so I will not pretend to point at it.",
    simpler: "Say it more simply",
    less: "Say it the full way",
    openLesson: "Open the lesson",
    refusal: "Your role cannot do this here.",
    whoCan: "Who can:",
    howAsk: "How to get access:",
    howInstead: "What to do instead:",
    source: "Grounded in:",
    columnAnswer: "From the column glossary",
    noAnswer: "I do not have an answer for that",
    noAnswerBody: "Nothing written here covers that question. Here is what I can answer on this screen.",
    /* -- the practice replica -------------------------------------------- */
    practiceBanner: "Practice company. Nothing you do here reaches a real employee, payslip or pay run.",
    employees: "employees",
    needReview: "Need review",
    compute: "Compute payslips",
    runPayroll: "Run payroll",
    submitReview: "Submit for review",
    reject: "Reject",
    bankFile: "Bank file",
    journals: "Journals",
    startImport: "Start import",
    commitImport: "Commit import",
    confidenceScore: "confidence score",
    match: "Match…",
    retry: "Retry",
    skip: "Skip",
    openFullList: "Open full list →",
    /* -- accessibility / motion ------------------------------------------ */
    reduceMotion: "Reduce motion",
    motionOn: "Motion on",
  },

  vi: {
    /* -- brand + journey map ------------------------------------------- */
    brand: "Payobook",
    learn: "Học tập",
    hubTitle: "Hành trình của bạn",
    hubLead: "Học nghiệp vụ Chạy lương từng màn hình một. Không thao tác nào ở đây chạm tới dữ liệu công ty bạn.",
    yourJourney: "Hành trình của bạn",
    overall: "Tiến độ chung",
    badge: "Huy hiệu Chạy lương",
    badgeGot: "Đã đạt huy hiệu Chạy lương",
    search: "Tìm trong hành trình",
    lines: { payrun: "Chạy lương", setup: "Thiết lập" },
    /* -- station cards -------------------------------------------------- */
    fullLesson: "Bài học đầy đủ",
    outline: "Dàn ý",
    required: "Bắt buộc",
    optional: "Tuỳ chọn",
    est: "Khoảng",
    min: "phút",
    notVisible: "Không có trong menu của bạn",
    notVisibleBody: "Màn hình này chưa có trong thanh bên của bạn nên bạn chưa mở được. Bạn vẫn có thể đọc nó làm gì và cần gì để được cấp quyền.",
    outlineNote: "Trạm này là dàn ý: nó là gì, vì sao quan trọng, khi nào dùng và những lỗi nó giúp tránh. Bài học đầy đủ chưa được viết.",
    whatIs: "Đây là gì",
    whyMatters: "Vì sao quan trọng",
    whenUse: "Khi nào dùng",
    prereq: "Cần gì trước",
    mistakes: "Những lỗi bài này giúp tránh",
    /* -- the lesson player ---------------------------------------------- */
    step: "Bước",
    of: "trên",
    back: "Quay lại",
    next: "Tiếp theo",
    replay: "Xem lại bước này",
    exit: "Thoát",
    check: "Kiểm tra hiểu bài",
    checkNote: "Một tình huống cần bạn phán đoán. Trả lời sai là một lối quay lại, không phải một điểm trừ.",
    tryAgain: "Thử lại",
    finish: "Hoàn thành",
    continueBtn: "Tiếp tục",
    consequence: "Trước khi bạn làm việc này",
    /* -- missions -------------------------------------------------------- */
    missions: "Nhiệm vụ thực hành",
    missionsLead: "Làm một lần ở nơi không hậu quả, trước khi làm ở nơi có hậu quả.",
    startMission: "Bắt đầu nhiệm vụ",
    outlineMission: "Dàn ý",
    liveNotYet: "Đây là nhiệm vụ tổng kết chạy trên dữ liệu thật của môi trường demo Payobook, nên chỉ mở được với tài khoản demo — nhiệm vụ thực hành ở trên dạy đúng phán đoán đó, một cách an toàn, ở bất kỳ đâu.",
    liveBadge: "Trực tiếp \u00b7 môi trường demo",
    liveStart: "Bắt đầu nhiệm vụ trực tiếp",
    liveReal: "Nhiệm vụ này là thật",
    liveRealBody: "Mọi bước dưới đây diễn ra ngay trong Payobook, trên những bản ghi người khác cũng nhìn thấy. Không có bản mô phỏng nào ở đây, và cũng không có gì được tự hoàn tác khi bạn thoát.",
    liveNudge: "Tập dượt trước nhé?",
    liveNudgeBody: "Nhiệm vụ thực hành dạy đúng phán đoán đó trên dữ liệu giả lập, nơi không có hậu quả nào. Bạn không bắt buộc phải làm \u2014 đây là lời nhắc, không phải khoá chặn.",
    liveNudgeGo: "Mở nhiệm vụ thực hành",
    liveOpenScreen: "Mở màn hình",
    liveCheckNow: "Kiểm tra ngay",
    liveChecking: "Đang kiểm tra\u2026",
    liveWaiting: "Đang chờ bạn thao tác trong Payobook",
    liveAck: "Tôi đã làm xong",
    liveNext: "Tiếp theo",
    liveFinish: "Hoàn thành nhiệm vụ",
    liveLeave: "Thoát",
    liveMinimise: "Thu gọn",
    showHint: "Gợi ý",
    scope: "Thao tác này ảnh hưởng tới đâu",
    reversible: "Có hoàn tác được không",
    verify: "Cần kiểm tra gì trước",
    proceed: "Tôi đã đọc — tiếp tục",
    cancelAct: "Quay lại",
    undoShown: "Hoàn tác",
    debriefTitle: "Tổng kết",
    whatYouDid: "Bạn đã làm gì",
    checklist: "Trước khi làm thật, luôn kiểm tra",
    confGain: "Mức tự tin tăng thêm",
    recoveryUsed: "bạn đã cần một lối quay lại trong lượt này",
    backToMissions: "Về danh sách nhiệm vụ",
    /* -- the Coach ------------------------------------------------------- */
    coachName: "Trợ lý Payobook",
    stuck: "Cần trợ giúp?",
    askPlaceholder: "Hỏi về màn hình này…",
    honest: "Tôi hướng dẫn — bạn thao tác. Tôi không bao giờ tự tính lương, phê duyệt phiếu lương hay sửa dữ liệu thay bạn.",
    groundedIn: "Căn cứ trên màn hình này:",
    coachNoScreen: "Tôi chưa có bài học cho màn hình này. Đây là những gì tôi trả lời được ở mọi nơi.",
    suggested: "Gợi ý cho màn hình này",
    canAnswer: "Những gì tôi trả lời được ở đây",
    showMe: "Chỉ cho tôi",
    pointNotHere: "Nút đó hiện không có trên màn hình này, nên tôi sẽ không giả vờ chỉ vào nó.",
    simpler: "Giải thích đơn giản hơn",
    less: "Giải thích đầy đủ lại",
    openLesson: "Mở bài học",
    refusal: "Vai trò của bạn không làm được việc này ở đây.",
    whoCan: "Ai làm được:",
    howAsk: "Cách xin quyền:",
    howInstead: "Nên làm gì thay thế:",
    source: "Căn cứ:",
    columnAnswer: "Từ từ điển cột số liệu",
    noAnswer: "Tôi chưa có câu trả lời cho việc đó",
    noAnswerBody: "Không có nội dung nào ở đây bao phủ câu hỏi đó. Đây là những gì tôi trả lời được trên màn hình này.",
    /* -- the practice replica -------------------------------------------- */
    practiceBanner: "Công ty thực hành. Mọi thao tác ở đây đều không chạm tới nhân viên, phiếu lương hay đợt lương thật.",
    employees: "nhân viên",
    needReview: "Cần soát xét",
    compute: "Tính phiếu lương",
    runPayroll: "Chạy bảng lương",
    submitReview: "Trình soát xét",
    reject: "Từ chối",
    bankFile: "Tệp chi lương",
    journals: "Bút toán",
    startImport: "Bắt đầu nhập",
    commitImport: "Ghi nhận dữ liệu",
    confidenceScore: "điểm tin cậy",
    match: "Khớp…",
    retry: "Thử lại",
    skip: "Bỏ qua",
    openFullList: "Mở danh sách đầy đủ →",
    /* -- accessibility / motion ------------------------------------------ */
    reduceMotion: "Giảm chuyển động",
    motionOn: "Bật chuyển động",
  },
};

/* =============================================================================
   2. GLOSSARY
   -----------------------------------------------------------------------------
   One entry per word this desk uses differently from ordinary Vietnamese or
   English. `term` and `def` are separate fields, not one "Term — definition"
   string: an em dash inside a definition would otherwise split it in the wrong
   place, and BHYT's definition legitimately contains one.
   ========================================================================== */
const GLOSSARY = {
  bhxh: {
    term: B("BHXH", "BHXH"),
    def: B("Social insurance. The employee pays 8% of the registered insurance base and the employer pays 17.5% on top of it. Charged on the REGISTERED base, which is why overtime does not move it.",
           "Bảo hiểm xã hội. Người lao động đóng 8% trên mức lương đóng BH đã đăng ký, doanh nghiệp đóng thêm 17,5%. Tính trên mức ĐÃ ĐĂNG KÝ, nên tăng ca không làm nó thay đổi."),
  },
  bhyt: {
    term: B("BHYT", "BHYT"),
    def: B("Health insurance — 1.5% employee and 3% employer, on the same registered insurance base as BHXH.",
           "Bảo hiểm y tế — người lao động 1,5% và doanh nghiệp 3%, trên cùng mức lương đóng BH như BHXH."),
  },
  bhtn: {
    term: B("BHTN", "BHTN"),
    def: B("Unemployment insurance — 1% employee and 1% employer, on the registered insurance base.",
           "Bảo hiểm thất nghiệp — người lao động 1% và doanh nghiệp 1%, trên mức lương đóng BH đã đăng ký."),
  },
  pit: {
    term: B("PIT (thuế TNCN)", "Thuế TNCN"),
    def: B("Personal income tax. Progressive 5–35%, charged on gross less insurance less the family deductions (₫11m for yourself, ₫4.4m per dependant).",
           "Thuế thu nhập cá nhân, luỹ tiến 5–35%, tính trên tổng thu nhập trừ bảo hiểm và giảm trừ gia cảnh (11 triệu cho bản thân, 4,4 triệu mỗi người phụ thuộc)."),
  },
  formulaConfig: {
    term: B("Formula configuration", "Cấu hình công thức"),
    def: B("The Excel-style rulebook that computes every payslip line for one division — inputs, earnings, deductions and totals, each a named component. Choosing a division chooses one of these.",
           "Bộ quy tắc kiểu Excel tính từng dòng phiếu lương cho một bộ phận — đầu vào, thu nhập, khấu trừ và các tổng, mỗi thứ là một thành phần có tên. Chọn bộ phận chính là chọn một trong các bộ này."),
  },
  payrun: {
    term: B("Pay run", "Đợt tính lương"),
    def: B("One batch of payslips for a division and a period, travelling draft → Payroll Officer → {{hrTierName}} → {{gmTierName}} → done. A rejection returns the whole batch to draft with a written reason.",
           "Một lô phiếu lương của một bộ phận trong một kỳ, đi qua Nháp → Chuyên viên tính lương → {{hrTierName}} → {{gmTierName}} → Hoàn tất. Từ chối sẽ trả cả lô về Nháp kèm lý do bằng văn bản."),
  },
  cycle: {
    term: B("Cycle", "Chu kỳ"),
    def: B("Which part of the month a run settles. Mid-cycle pays an advance during the month; end-cycle is the full monthly settlement. Most divisions run end-cycle only.",
           "Đợt lương quyết toán phần nào của tháng. Giữa kỳ là khoản tạm ứng trong tháng; cuối kỳ là quyết toán cả tháng. Đa số bộ phận chỉ chạy cuối kỳ."),
  },
  proration: {
    term: B("Proration", "Tính theo ngày công (pro-rata)"),
    def: B("Paying part of a month, as days worked over the division's standard working days. It is a factor, not a discount — the factor is the number to check when an amount looks wrong.",
           "Trả lương cho một phần của tháng, bằng số ngày công thực tế chia cho ngày công chuẩn của bộ phận. Đây là hệ số, không phải khoản giảm trừ — khi một con số trông sai, hệ số là thứ cần kiểm tra."),
  },
  retro: {
    term: B("Retro adjustment", "Điều chỉnh hồi tố"),
    def: B("A difference owed for a period that is already closed, paid in the current run with the source period recorded against it. It is how a closed month stays closed.",
           "Khoản chênh lệch còn nợ của một kỳ đã đóng, được chi trong kỳ hiện tại và có ghi rõ kỳ gốc. Đây là cách để một kỳ đã đóng vẫn luôn đóng."),
  },
  /* -- Setup (Phase B) ------------------------------------------------- */
  policy: {
    term: B("Insurance policy", "Chính sách bảo hiểm"),
    def: B("One record holding the BHXH, BHYT and BHTN rates and ceilings, with the date it takes effect. It is not versioned in place: a rate change is a NEW policy record with its own code, and the old one is end-dated.",
           "Một bản ghi chứa tỷ lệ và trần đóng BHXH, BHYT, BHTN, kèm ngày bắt đầu hiệu lực. Nó không được sửa đè theo phiên bản: đổi tỷ lệ nghĩa là tạo một bản ghi chính sách MỚI với mã riêng, và bản cũ được đặt ngày kết thúc."),
  },
  effectiveDate: {
    term: B("Effective date", "Ngày hiệu lực"),
    def: B("The date a policy starts applying. Payobook uses the latest effective date among the active policies, so this field — not the order records were created in — decides which rates a payslip is computed with.",
           "Ngày một chính sách bắt đầu được áp dụng. Payobook lấy chính sách có ngày hiệu lực mới nhất trong số các chính sách đang bật, nên chính trường này — chứ không phải thứ tự tạo bản ghi — quyết định phiếu lương được tính theo tỷ lệ nào."),
  },
  ceiling: {
    term: B("Insurance ceiling (trần đóng)", "Trần đóng bảo hiểm"),
    def: B("The maximum base a contribution is charged on. Above it the deduction stops growing, so two people on very different salaries can pay exactly the same BHXH.",
           "Mức đóng tối đa mà một khoản bảo hiểm được tính trên đó. Vượt qua mức này thì khoản khấu trừ không tăng nữa, nên hai người lương rất khác nhau vẫn có thể đóng BHXH bằng nhau."),
  },
  configCode: {
    term: B("Configuration code", "Mã cấu hình"),
    def: B("The short unique name of a formula configuration — the thing Run Payroll actually selects when you choose a division. On the demo world the codes follow one pattern: DEMO_<DIVISION>_END for the end-cycle rulebook and DEMO_<DIVISION>_MID for the mid-cycle one.",
           "Tên ngắn và duy nhất của một cấu hình công thức — chính là thứ Chạy bảng lương chọn khi bạn chọn bộ phận. Trên bản demo, các mã theo một quy ước: DEMO_<BỘ PHẬN>_END cho bộ quy tắc cuối kỳ và DEMO_<BỘ PHẬN>_MID cho giữa kỳ."),
  },
};

/* =============================================================================
   3. STATIONS — the nodes on the Journey map
   -----------------------------------------------------------------------------
   One per Pay Run sidebar leaf, in the order pb_sidebar draws them. The import
   WIZARD has no station: it is a flow, not a destination, and giving it a node
   on the map would promise a place a learner can go back to.

   `outline` is not filler for the stations without a lesson. What / why / when /
   what-you-need / the mistakes it prevents is the whole of an outline station,
   and a node with no `what` teaches nothing — worse than not drawing it.

   Prose ported from the v1 prototype (docs/tutorial_poc/data.js STATIONS),
   re-scoped: v1 mixed Pay Run and Setup on one map, Phase A ships Pay Run.
   ========================================================================== */
const STATIONS = {
  payrun: {
    stations: [
      {
        id: "runpayroll", icon: "zap", star: true, required: true, mins: 8, after: null,
        title: B("Run Payroll", "Chạy bảng lương"),
        desc: B("Create a month's draft payslips for one division — the heart of Payobook.",
                "Tạo phiếu lương nháp của một tháng cho một bộ phận — trái tim của Payobook."),
        outline: {
          what: B("A four-step wizard that takes one division and one period and computes a draft payslip for every eligible employee.",
                  "Trình hướng dẫn bốn bước, nhận một bộ phận và một kỳ lương rồi tính phiếu lương nháp cho từng nhân viên đủ điều kiện."),
          why: B("It is where a month of salaries starts. Everything downstream — review, approval, the bank file — reads what this step produced, so an error here is an error in all of it.",
                 "Đây là nơi một tháng lương bắt đầu. Mọi việc phía sau — soát xét, phê duyệt, tệp chi lương — đều đọc kết quả của bước này, nên sai ở đây là sai ở tất cả."),
          when: B("Once the month's attendance and overtime have been imported and committed. Not before: computing on an uncommitted import is the single most common first-week mistake.",
                  "Sau khi dữ liệu chấm công và tăng ca của tháng đã được nhập và ghi nhận. Không sớm hơn: tính lương khi dữ liệu chưa ghi nhận là lỗi phổ biến nhất trong tuần đầu."),
          prereq: B("The Payroll Officer group, a committed import for the period, and a formula configuration on the division you are running.",
                    "Quyền Chuyên viên tính lương, một đợt nhập liệu đã ghi nhận cho kỳ đó, và một cấu hình công thức trên bộ phận bạn định chạy."),
          mistakes: [
            B("Computing before the month's import is committed. The eligible count is the tell — 12 where you expected 48 means the data is not in yet.",
              "Tính lương khi dữ liệu tháng chưa được ghi nhận. Số nhân viên đủ điều kiện là dấu hiệu — thấy 12 trong khi bạn chờ 48 nghĩa là dữ liệu chưa vào."),
            B("Running the wrong cycle. Mid-cycle pays an advance; end-cycle settles the month. They are not two views of one thing.",
              "Chạy nhầm chu kỳ. Giữa kỳ là tạm ứng; cuối kỳ là quyết toán cả tháng. Đó không phải hai cách nhìn của cùng một thứ."),
            B("Submitting for approval without opening the flagged payslips. A flag is a question the engine wants answered, and submitting is you answering it with silence.",
              "Trình phê duyệt mà chưa mở các phiếu bị gắn cờ. Cờ là câu hỏi hệ thống muốn được trả lời, và trình duyệt là bạn trả lời nó bằng sự im lặng."),
          ],
        },
      },
      {
        id: "payruns", icon: "calendar", star: true, required: true, mins: 7, after: "runpayroll",
        title: B("Pay Runs", "Đợt tính lương"),
        desc: B("Every run on one board, moving draft → Officer → HR → GM → done.",
                "Mọi đợt lương trên một bảng, đi từ Nháp → Chuyên viên tính lương → HR → TGĐ → Hoàn tất."),
        outline: {
          what: B("A board of every pay run, grouped by the approval stage it is waiting at, with the actions that stage allows on each card.",
                  "Bảng chứa mọi đợt tính lương, nhóm theo trạng thái phê duyệt mà nó đang chờ, kèm các thao tác mà trạng thái đó cho phép trên từng thẻ."),
          why: B("Nothing is paid without the right sign-offs, and the board is what makes the pipeline visible and auditable. It answers the only question a payroll week really asks: what is stuck, and whose gate is it stuck at.",
                 "Không khoản nào được chi khi chưa đủ chữ ký, và bảng này làm quy trình minh bạch và kiểm toán được. Nó trả lời đúng câu hỏi mà tuần tính lương thực sự đặt ra: cái gì đang tắc, và tắc ở cổng của ai."),
          when: B("Daily during payroll week, and any time you need to know where a period has got to.",
                  "Hằng ngày trong tuần tính lương, và bất cứ khi nào bạn cần biết một kỳ đã đi tới đâu."),
          prereq: B("A computed run. Approving needs the group that owns that particular gate.",
                    "Một đợt đã tính xong. Muốn phê duyệt cần nhóm quyền sở hữu đúng cổng đó."),
          mistakes: [
            B("Approving a run without opening its flagged payslips. The board shows totals; the flags are on the slips.",
              "Phê duyệt một đợt mà chưa mở các phiếu bị gắn cờ. Bảng chỉ hiện các tổng; cờ nằm trên từng phiếu."),
            B("Rejecting without a written reason. The run goes back to draft either way, but the person who has to fix it is then guessing at what you saw.",
              "Từ chối mà không ghi lý do. Đợt lương vẫn quay về Nháp, nhưng người phải sửa nó lại phải đoán xem bạn đã thấy điều gì."),
            B("Reading a status column as a period. The columns are approval stages — July and June can sit in the same one.",
              "Đọc cột trạng thái như thể là kỳ lương. Các cột là bước phê duyệt — tháng 7 và tháng 6 có thể cùng nằm trong một cột."),
          ],
        },
      },
      {
        id: "payslips", icon: "receipt", required: true, mins: 6, after: "runpayroll",
        title: B("Payslips", "Phiếu lương"),
        desc: B("Read any employee's slip line by line — gross to net, with every rule visible.",
                "Đọc phiếu lương của từng nhân viên theo từng dòng — từ tổng thu nhập đến thực nhận, mọi quy tắc đều nhìn thấy được."),
        outline: {
          what: B("The review surface for individual payslips inside one run: a filterable list, and for the selected employee the approval stepper and the full salary breakdown.",
                  "Nơi soát xét từng phiếu lương trong một đợt: danh sách có bộ lọc, và với nhân viên đang chọn là thanh trạng thái phê duyệt cùng bảng chi tiết lương đầy đủ."),
          why: B("A run total can be right while an individual slip is wrong. This is the only screen that shows the working behind a net figure, so it is where an error is caught before money moves.",
                 "Tổng của một đợt có thể đúng trong khi một phiếu riêng lẻ vẫn sai. Đây là màn hình duy nhất cho thấy phần tính toán phía sau con số thực nhận, nên là nơi bắt lỗi trước khi tiền được chi."),
          when: B("After computing and before submitting for approval, and again whenever an employee asks why their pay is what it is.",
                  "Sau khi tính và trước khi trình phê duyệt, và bất cứ khi nào có nhân viên hỏi vì sao lương của họ lại như vậy."),
          prereq: B("A computed run to read. No special group is needed to look.",
                    "Một đợt đã tính để đọc. Chỉ để xem thì không cần quyền đặc biệt."),
          mistakes: [
            B("Editing a net amount directly instead of fixing the input and recomputing. The slip then no longer agrees with the data behind it, and the next recompute silently undoes the fix.",
              "Sửa thẳng số thực nhận thay vì sửa dữ liệu đầu vào rồi tính lại. Phiếu sẽ không còn khớp với dữ liệu phía sau, và lần tính lại sau sẽ âm thầm xoá sửa đổi của bạn."),
            B("Expecting insurance to move when overtime does. BHXH, BHYT and BHTN are charged on the registered base, which overtime does not change.",
              "Trông đợi bảo hiểm thay đổi khi tăng ca thay đổi. BHXH, BHYT và BHTN tính trên mức lương đóng BH đã đăng ký, mà tăng ca không làm thay đổi mức đó."),
            B("Clearing a flag by dismissing it. Clearing one means understanding it — the flag was the engine asking a question about that employee.",
              "Xoá một cờ cảnh báo bằng cách bỏ qua nó. Xoá cờ nghĩa là đã hiểu nó — cờ là hệ thống đang hỏi một câu về chính nhân viên đó."),
          ],
        },
      },
      {
        id: "import", icon: "database", required: true, mins: 6, after: null,
        title: B("Import Data", "Nhập dữ liệu"),
        desc: B("Bring attendance, overtime and inputs in — preview, score and fix before anything commits.",
                "Đưa dữ liệu chấm công, tăng ca và đầu vào vào hệ thống — xem trước, chấm điểm và sửa lỗi trước khi ghi nhận."),
        outline: {
          what: B("A guided four-step flow — source, review and match, validate and fix, commit — plus the batch history of everything imported before.",
                  "Luồng có hướng dẫn bốn bước — chọn nguồn, soát và khớp, kiểm tra và sửa, ghi nhận — kèm lịch sử các đợt đã nhập trước đó."),
          why: B("Most wrong payslips start as a wrong row in a file. Fixing it here costs minutes; fixing it after approval costs a retro line and a conversation.",
                 "Phần lớn phiếu lương sai bắt đầu từ một dòng sai trong tệp. Sửa ở đây tốn vài phút; sửa sau khi đã phê duyệt tốn một dòng hồi tố và một cuộc trao đổi."),
          when: B("Whenever the month's inputs arrive, and always before computing a run.",
                  "Ngay khi dữ liệu đầu vào của tháng về, và luôn trước khi tính một đợt lương."),
          prereq: B("The Import group, a file or a connected system to read from, and a formula configuration to map the columns onto.",
                    "Quyền Nhập dữ liệu, một tệp hoặc một hệ thống đã kết nối để đọc, và một cấu hình công thức để ánh xạ các cột vào."),
          mistakes: [
            B("Committing a batch with unresolved rows because the deadline is close. An unmatched row is an employee who will be missing from the run.",
              "Ghi nhận một đợt còn dòng chưa xử lý vì sắp tới hạn. Một dòng không khớp là một nhân viên sẽ bị thiếu trong đợt lương."),
            B("Importing one month's data into another month's period. The batch is named for the period it targets — read that name before committing.",
              "Nhập dữ liệu của tháng này vào kỳ của tháng khác. Đợt nhập được đặt tên theo kỳ mà nó nhắm tới — hãy đọc tên đó trước khi ghi nhận."),
            B("Fixing an import mistake on the payslips afterwards. That corrects the output and leaves the input wrong, so the next recompute brings the mistake back.",
              "Sửa lỗi nhập liệu trên phiếu lương về sau. Việc đó chỉ sửa kết quả và để nguyên đầu vào sai, nên lần tính lại kế tiếp sẽ mang lỗi quay lại."),
          ],
        },
      },
      {
        id: "fullfinal", icon: "file-text", mins: 4, after: "payruns",
        title: B("Full & Final", "Quyết toán thôi việc"),
        desc: B("Settle a leaver: last salary, unused leave, deductions — one closing statement.",
                "Quyết toán cho nhân viên nghỉ việc: lương cuối, phép chưa dùng, khấu trừ — một bảng chốt duy nhất."),
        outline: {
          what: B("The settlement workspace for departing employees, listing what each is still owed and whether it has been paid.",
                  "Không gian quyết toán cho nhân viên thôi việc, liệt kê từng người còn được nhận gì và đã chi hay chưa."),
          why: B("Leaver settlements have legal deadlines and one chance to be right. They are also the payment most likely to be disputed, because it is the last one.",
                 "Quyết toán thôi việc có thời hạn pháp lý và chỉ có một lần để làm đúng. Đây cũng là khoản dễ bị khiếu nại nhất, vì là khoản cuối cùng."),
          when: B("As soon as a resignation or termination date is confirmed — not on the payroll run date, which is usually too late.",
                  "Ngay khi ngày nghỉ việc hoặc chấm dứt hợp đồng được xác nhận — không phải vào ngày chạy lương, lúc đó thường đã muộn."),
          prereq: B("A recorded contract end date and a current leave balance for the employee.",
                    "Đã ghi ngày kết thúc hợp đồng và số dư phép cập nhật cho nhân viên đó."),
          mistakes: [
            B("Leaving the departing employee in the normal monthly run as well. They are then paid twice, and recovering an overpayment from someone who has left is a legal problem, not a payroll one.",
              "Vẫn để nhân viên thôi việc trong đợt lương tháng bình thường. Họ sẽ được trả hai lần, và thu hồi khoản trả thừa từ người đã nghỉ là chuyện pháp lý, không còn là chuyện tính lương."),
            B("Settling before the last month's attendance is in. The final salary is a prorated month, so it needs the same inputs every other month needs.",
              "Quyết toán khi chấm công tháng cuối chưa về. Lương cuối là một tháng tính theo ngày công, nên vẫn cần đúng những dữ liệu mà mọi tháng khác cần."),
          ],
        },
      },
      {
        id: "proration", icon: "calculator", mins: 4, after: "payslips",
        title: B("Proration Audit", "Soát xét ngày công (pro-rata)"),
        desc: B("See exactly how a part-month salary was prorated — day by day, no black box.",
                "Xem chính xác lương tháng lẻ ngày được tính theo tỷ lệ ra sao — từng ngày, không hộp đen."),
        outline: {
          what: B("An audit trail of every prorated amount in a run — joiners, leavers and unpaid leave — showing days worked, standard days and the factor between them.",
                  "Nhật ký kiểm toán mọi khoản tính theo tỷ lệ trong một đợt — người mới vào, người nghỉ việc và nghỉ không lương — hiển thị ngày công thực tế, ngày công chuẩn và hệ số giữa hai con số đó."),
          why: B("Proration is the question employees ask most often, and the one hardest to answer from memory. This screen is the evidence, written down before anyone asks.",
                 "Ngày công là thắc mắc nhân viên hỏi nhiều nhất, và cũng là câu khó trả lời nhất nếu chỉ dựa vào trí nhớ. Màn hình này là bằng chứng, đã ghi sẵn trước khi có ai hỏi."),
          when: B("When a payslip looks too small and you need to show why, and as a spot check on any run with mid-month movement.",
                  "Khi một phiếu lương trông thiếu và bạn cần chứng minh vì sao, và như một bước kiểm tra ngẫu nhiên cho mọi đợt có biến động giữa tháng."),
          prereq: B("A computed run containing at least one joiner, leaver or unpaid-leave case.",
                    "Một đợt đã tính có ít nhất một trường hợp vào mới, thôi việc hoặc nghỉ không lương."),
          mistakes: [
            B("Assuming calendar days when the division's configuration uses standard working days. Twenty-two is not thirty, and the difference is somebody's salary.",
              "Nhầm ngày dương lịch trong khi cấu hình của bộ phận dùng ngày công chuẩn. 22 không phải 30, và phần chênh là lương của một người."),
            B("Reading the money before the factor. If the factor is right and the amount still looks wrong, the problem is upstream in the contract or the import.",
              "Đọc số tiền trước khi đọc hệ số. Nếu hệ số đúng mà số tiền vẫn có vẻ sai thì vấn đề nằm ở phía trên: hợp đồng hoặc dữ liệu nhập."),
          ],
        },
      },
      {
        id: "retro", icon: "trending-up", mins: 4, after: "payruns",
        title: B("Retro Adjustments", "Điều chỉnh hồi tố"),
        desc: B("Backdated raises and corrections, applied cleanly to a later run — with a full trail.",
                "Tăng lương lùi ngày và các hiệu chỉnh, áp gọn vào kỳ sau — có vết lưu đầy đủ."),
        outline: {
          what: B("A ledger of differences owed from periods that are already closed, paid in the current run with the source period recorded on every line.",
                  "Sổ ghi các khoản chênh lệch còn nợ từ những kỳ đã đóng, được chi trong kỳ hiện tại và mỗi dòng đều ghi rõ kỳ gốc."),
          why: B("It keeps closed months closed. Reopening an approved run to fix the past invalidates everything that was reported from it — the retro line is how you pay the difference without doing that.",
                 "Nó giữ cho các kỳ đã đóng luôn đóng. Mở lại một đợt đã duyệt để sửa quá khứ sẽ làm sai lệch mọi báo cáo đã xuất từ đợt đó — dòng hồi tố là cách trả phần chênh mà không phải làm vậy."),
          when: B("Backdated raises, allowances missed in an earlier month, and any correction found after the run it belongs to was approved.",
                  "Tăng lương lùi ngày, phụ cấp bị sót ở tháng trước, và mọi hiệu chỉnh phát hiện sau khi đợt gốc đã được phê duyệt."),
          prereq: B("The source run is done, and the correction is documented — a retro line without a reason is an unexplained payment.",
                    "Đợt gốc đã Hoàn tất, và hiệu chỉnh có chứng từ — một dòng hồi tố không có lý do là một khoản chi không giải thích được."),
          mistakes: [
            B("Editing the old approved payslip instead of creating a retro line. The old month has already been reported; changing it changes a number somebody else has filed.",
              "Sửa phiếu lương cũ đã duyệt thay vì tạo dòng hồi tố. Kỳ cũ đã được báo cáo; sửa nó là sửa một con số mà người khác đã nộp đi."),
            B("Leaving the source period blank. Without it the line is money paid for no stated reason, which is exactly what an audit asks about first.",
              "Bỏ trống kỳ gốc. Không có nó, dòng này là một khoản chi không nêu lý do — đúng thứ mà kiểm toán hỏi đầu tiên."),
          ],
        },
      },
    ],
  },

  /* ---------------------------------------------------------------------------
     THE SETUP LINE (Phase B).

     A second line on the SAME map, not a second map: a learner who has finished
     the Pay Run desk meets these further along the same journey. The order is
     the order pb_sidebar draws the Setup section.

     Statutory is the flagship here rather than Formula Engine, and that is a
     judgement about consequence: a wrong formula produces one division's wrong
     payslips, and a wrong statutory rate produces every division's — silently,
     and with a legal deadline attached.
     ------------------------------------------------------------------------ */
  setup: {
    stations: [
      {
        id: "formula", icon: "calculator", required: true, mins: 7, after: null,
        title: B("Formula Engine", "Công thức lương"),
        desc: B("The visible rulebook: every payslip line is a named component with a formula you can read.",
                "Bộ quy tắc nhìn thấy được: mỗi dòng phiếu lương là một thành phần có tên, với công thức bạn đọc được."),
        outline: {
          what: B("A studio for each division's formula configuration — the components, the formula behind each one, what it depends on, and a live preview against a real employee.",
                  "Xưởng làm việc cho cấu hình công thức của từng bộ phận — các thành phần, công thức đằng sau mỗi thành phần, nó phụ thuộc vào gì, và bản xem trước trực tiếp trên một nhân viên thật."),
          why: B("It is the answer to every \"why is my pay this number\" question, written down. A payroll desk that can read the configuration stops guessing and starts showing.",
                 "Đây là câu trả lời đã được viết sẵn cho mọi thắc mắc \"vì sao lương tôi lại là con số này\". Một bộ phận lương đọc được cấu hình sẽ thôi phỏng đoán và bắt đầu trưng ra bằng chứng."),
          when: B("When an allowance is added, when a rule changes, and any time a number on a payslip has to be traced back to where it came from.",
                  "Khi thêm một khoản phụ cấp, khi một quy tắc thay đổi, và bất cứ lúc nào cần truy một con số trên phiếu lương về đúng nơi sinh ra nó."),
          prereq: B("The Payroll Officer group to read it and a manager tier to change it, plus a sample employee to preview against.",
                    "Quyền Chuyên viên tính lương để xem và quyền cấp quản lý để sửa, cùng một nhân viên mẫu để xem trước."),
          mistakes: [
            B("Editing a live configuration without previewing. The preview costs seconds; a wrong component costs every future payslip in that division.",
              "Sửa một cấu hình đang chạy mà không xem trước. Xem trước tốn vài giây; một thành phần sai làm hỏng mọi phiếu lương tương lai của bộ phận đó."),
            B("Renaming a component other formulas depend on. The dependency panel names them — read it before you rename, because a formula that lost its input does not always fail loudly.",
              "Đổi tên một thành phần mà công thức khác đang phụ thuộc. Bảng phụ thuộc liệt kê chúng — hãy đọc trước khi đổi tên, vì một công thức mất đầu vào không phải lúc nào cũng báo lỗi rõ ràng."),
            B("Building a statutory rate into a formula by hand. Rates belong on the statutory policy; a hard-typed 8% is one that nobody will remember to change.",
              "Gõ thẳng một tỷ lệ luật định vào công thức. Tỷ lệ thuộc về chính sách bảo hiểm; một con số 8% gõ tay là con số sẽ không ai nhớ để sửa."),
          ],
        },
      },
      {
        id: "structures", icon: "layers", mins: 4, after: "formula",
        title: B("Salary Structures", "Cấu trúc lương"),
        desc: B("The legacy rule sets — kept because old payslips still reference them, not because new pay logic belongs here.",
                "Các bộ quy tắc thế hệ cũ — giữ lại vì phiếu lương cũ vẫn tham chiếu tới chúng, không phải vì logic lương mới nên nằm ở đây."),
        outline: {
          what: B("Odoo salary structures and their rules: the older way of computing a payslip, still holding the logic that historical payslips were produced by.",
                  "Cấu trúc lương và các quy tắc của Odoo: cách tính phiếu lương thế hệ trước, vẫn đang giữ phần logic đã tạo ra các phiếu lương lịch sử."),
          why: B("You will meet them the first time you open a payslip from before the migration, and knowing what they are is the difference between reading history and doubting it.",
                 "Bạn sẽ gặp chúng ngay lần đầu mở một phiếu lương từ trước khi chuyển đổi, và hiểu chúng là gì chính là khác biệt giữa đọc được lịch sử và hoài nghi lịch sử."),
          when: B("When reading an old payslip, and when migrating a division onto a formula configuration — the structure is what you are migrating FROM.",
                  "Khi đọc một phiếu lương cũ, và khi chuyển một bộ phận sang cấu hình công thức — cấu trúc chính là thứ bạn đang chuyển ĐI TỪ đó."),
          prereq: B("A manager tier, and the Formula Engine basics — otherwise it is hard to see what the two are for.",
                    "Quyền cấp quản lý, và nắm cơ bản Công thức lương — nếu không sẽ khó thấy hai thứ này dùng để làm gì."),
          mistakes: [
            B("Building new pay logic here because it is familiar. A new rule added to a structure is invisible to the Formula Engine, so the division it was meant for never sees it.",
              "Xây logic lương mới ở đây vì thấy quen tay. Một quy tắc mới thêm vào cấu trúc thì Công thức lương không nhìn thấy, nên bộ phận cần nó sẽ chẳng bao giờ nhận được."),
            B("Deleting a structure that has no employees on it today. Payslips from three years ago still point at it, and a report run over those months needs it to still be there.",
              "Xoá một cấu trúc mà hôm nay không còn nhân viên nào dùng. Phiếu lương của ba năm trước vẫn trỏ tới nó, và một báo cáo chạy trên các tháng đó vẫn cần nó tồn tại."),
          ],
        },
      },
      {
        id: "statutory", icon: "shield-check", star: true, required: true, mins: 8, after: null,
        title: B("Statutory (Insurance & Tax)", "Bảo hiểm & Thuế"),
        desc: B("BHXH · BHYT · BHTN rates, the ceilings, and the thuế TNCN table — the rules the law writes for you.",
                "Tỷ lệ BHXH · BHYT · BHTN, các mức trần, và biểu thuế TNCN — những quy tắc do pháp luật viết sẵn cho bạn."),
        outline: {
          what: B("The company's active insurance policy and tax table: who pays what, on which base, up to which ceiling, and from which date.",
                  "Chính sách bảo hiểm và biểu thuế đang hiệu lực của công ty: ai đóng bao nhiêu, trên mức nào, tới trần nào, và từ ngày nào."),
          why: B("This is what the company DECLARES it contributes, and it is what the cockpit, the contribution analytics and the statutory reports read. It is not what prices a payslip — that is a parameter in each division's formula configuration — so the real work here is keeping the two in agreement. When they disagree, payroll is running on a rate the company is not declaring.",
                 "Đây là mức mà doanh nghiệp KHAI BÁO là mình đóng, và cũng là mức mà màn hình này, phần phân tích chi phí bảo hiểm và các báo cáo bắt buộc đọc vào. Nó không phải thứ tính ra tiền trên phiếu lương — thứ đó là một tham số trong cấu hình công thức của từng bộ phận — nên việc thật sự ở đây là giữ hai bên khớp nhau. Khi chúng lệch nhau, hệ thống lương đang chạy theo một tỷ lệ mà doanh nghiệp không hề khai báo."),
          when: B("When a decree changes a rate or a deduction, at the start of a tax year, and whenever an employee asks why a contribution is the amount it is.",
                  "Khi một nghị định thay đổi tỷ lệ hoặc mức giảm trừ, vào đầu một năm tính thuế, và bất cứ khi nào có nhân viên hỏi vì sao khoản đóng lại là con số đó."),
          prereq: B("A manager tier, and the decree or circular in front of you — this screen records a decision that was made elsewhere.",
                    "Quyền cấp quản lý, và văn bản pháp luật đang mở trước mặt — màn hình này ghi lại một quyết định đã được ra ở nơi khác."),
          mistakes: [
            B("Editing the rate on the policy that is currently in force. There is no version history to fall back on — the old declared rate is simply gone, and with it the evidence of what the company was declaring last month.",
              "Sửa tỷ lệ ngay trên chính sách đang có hiệu lực. Không có lịch sử phiên bản nào để quay lại — tỷ lệ đã khai báo trước đó đơn giản là biến mất, và mất theo cả bằng chứng về việc tháng trước doanh nghiệp đang khai báo mức nào."),
            B("Creating the new policy but dating it from today rather than from the day the decree applies. The effective date is the company's record of when the change legally started, and a date nobody can point at a decree for is the first thing an inspection asks about.",
              "Tạo chính sách mới nhưng đặt ngày hiệu lực là hôm nay thay vì ngày nghị định bắt đầu áp dụng. Ngày hiệu lực là ghi nhận của doanh nghiệp về thời điểm thay đổi bắt đầu có hiệu lực pháp lý, và một cái ngày không chỉ ra được văn bản nào là thứ đầu tiên đoàn kiểm tra hỏi tới."),
            B("Declaring the new rate and stopping there. The number that prices a payslip is a parameter on the division's formula configuration, so until that is changed too the run still charges the old rate — correctly, and against a declaration that now says otherwise.",
              "Khai báo tỷ lệ mới rồi dừng ở đó. Con số tính ra tiền trên phiếu lương là một tham số trong cấu hình công thức của bộ phận, nên tới khi tham số đó cũng được sửa thì đợt lương vẫn tính theo tỷ lệ cũ — tính đúng, nhưng lệch với bản khai báo vừa thay đổi."),
          ],
        },
      },
      {
        id: "integrations", icon: "database", mins: 4, after: null,
        title: B("Integrations", "Tích hợp"),
        desc: B("Connectors that pull attendance and HR data in automatically — mapped field by field, with a sync history.",
                "Các đầu nối tự động kéo dữ liệu chấm công và nhân sự về — ánh xạ theo từng trường, kèm lịch sử đồng bộ."),
        outline: {
          what: B("Configured links to the systems payroll data arrives from — an HR system, a time clock, the bank — with their field mappings and when each last synced.",
                  "Các kết nối đã cấu hình tới những hệ thống mà dữ liệu tính lương đi vào từ đó — hệ thống nhân sự, máy chấm công, ngân hàng — kèm ánh xạ trường và thời điểm đồng bộ gần nhất."),
          why: B("Data that arrives by itself is data nobody retyped, and most wrong payslips start as a retyped row. The sync history is the part that matters: a connector that stopped looks exactly like one that is working.",
                 "Dữ liệu tự về là dữ liệu không ai phải gõ lại, mà phần lớn phiếu lương sai đều bắt đầu từ một dòng gõ tay. Phần quan trọng là lịch sử đồng bộ: một đầu nối đã ngừng chạy trông y hệt một đầu nối đang chạy tốt."),
          when: B("Once at onboarding, again whenever a source system changes its fields — and as a two-minute check at the start of every payroll week.",
                  "Một lần khi triển khai, làm lại mỗi khi hệ thống nguồn đổi trường dữ liệu — và như một bước kiểm tra hai phút vào đầu mỗi tuần tính lương."),
          prereq: B("The Integration user group and credentials for the source system.",
                    "Quyền Người dùng tích hợp và thông tin đăng nhập của hệ thống nguồn."),
          mistakes: [
            B("Leaving a failed sync unnoticed until payroll week. The staged-record count is the tell — rows sitting in staging are a month of attendance that never became inputs.",
              "Để một lần đồng bộ lỗi trôi qua cho tới tuần tính lương. Số bản ghi đang chờ là dấu hiệu — những dòng nằm lại ở vùng chờ là cả một tháng chấm công không bao giờ trở thành dữ liệu đầu vào."),
            B("Assuming a connector that is \"connected\" is also up to date. Connected describes the credentials; the last-sync time describes the data.",
              "Cho rằng một đầu nối \"đã kết nối\" thì cũng đang cập nhật. Đã kết nối nói về thông tin đăng nhập; thời điểm đồng bộ gần nhất mới nói về dữ liệu."),
          ],
        },
      },
    ],
  },
};

/* =============================================================================
   4. MORPH ROWS — the before/after captions a `morph` step toggles between.
   -----------------------------------------------------------------------------
   These live HERE and not in practice-data.js on purpose. A morph caption is
   consequence prose that exists only inside a lesson ("insurance did not move")
   — it is not a product fact. `big` is the headline figure and is NEVER
   translated: a translator may reword a caption, and may not turn 12,919,000
   into something else. The generator writes it into learn.step.line.value,
   which is not a translatable column.
   ========================================================================== */
const MORPHS = {
  maiJuneJuly: {
    before: {
      h: B("June 2026", "Tháng 6/2026"),
      big: "12,064,000 ₫",
      d: B("Overtime 600,000 · insurance 1,260,000 · PIT 56,000",
           "Tăng ca 600.000 · bảo hiểm 1.260.000 · thuế TNCN 56.000"),
    },
    after: {
      h: B("July 2026", "Tháng 7/2026"),
      big: "12,919,000 ₫",
      d: B("Overtime 1,500,000 · insurance 1,260,000 · PIT 101,000",
           "Tăng ca 1.500.000 · bảo hiểm 1.260.000 · thuế TNCN 101.000"),
      delta: B("Net is 855,000 ₫ higher. Overtime rose 900,000 and PIT took 45,000 of it. Insurance is identical, because it is charged on the registered base and overtime does not touch that.",
               "Thực nhận cao hơn 855.000 ₫. Tăng ca tăng 900.000 và thuế TNCN lấy đi 45.000 trong đó. Bảo hiểm không đổi, vì tính trên mức lương đóng BH đã đăng ký và tăng ca không chạm tới mức đó."),
    },
  },

  /* The same employee, the same month, under two POLICIES. Every figure is
     RATE_CHANGE in practice-data.js, which is `payslip()` run twice — including
     the part that is easy to get wrong by hand: the extra BHYT also lowers
     taxable income, so PIT falls and the net drop is 57,000 rather than the
     60,000 the deduction grew by. */
  maiBhytRate: {
    before: {
      h: B("BHYT at 1.5%", "BHYT ở mức 1,5%"),
      big: "12,919,000 ₫",
      d: B("BHYT 180,000 · insurance 1,260,000 · taxable 2,020,000 · PIT 101,000",
           "BHYT 180.000 · bảo hiểm 1.260.000 · thu nhập chịu thuế 2.020.000 · thuế TNCN 101.000"),
    },
    after: {
      h: B("BHYT at 2.0%", "BHYT ở mức 2,0%"),
      big: "12,862,000 ₫",
      d: B("BHYT 240,000 · insurance 1,320,000 · taxable 1,960,000 · PIT 98,000",
           "BHYT 240.000 · bảo hiểm 1.320.000 · thu nhập chịu thuế 1.960.000 · thuế TNCN 98.000"),
      delta: B("Net falls 57,000 ₫, not 60,000. The deduction grew by 60,000, and because insurance comes off before tax, taxable income fell by the same 60,000 and PIT fell 3,000 with it. Half a percentage point, one employee, every month.",
               "Thực nhận giảm 57.000 ₫, không phải 60.000. Khoản khấu trừ tăng 60.000, và vì bảo hiểm được trừ trước khi tính thuế, thu nhập chịu thuế cũng giảm đúng 60.000 nên thuế TNCN giảm theo 3.000. Nửa điểm phần trăm, một nhân viên, mỗi tháng."),
    },
  },
};

/* =============================================================================
   5. LESSONS
   -----------------------------------------------------------------------------
   Every step renders over the PRACTICE REPLICA, never the live app: the
   spotlight card and the screen underneath it both come from
   pb_learn/static/src/engine/screens.js. The anchors are the real ones, so the
   vocabulary a learner picks up here is the vocabulary the Coach uses on the
   live screen tomorrow.

   `anchor` must exist in pb_learn/static/src/anchors.json. check_contract.py
   lints that before generation and tests/test_anchor_registry.py enforces it
   after, in both directions.

   Completion is a right answer to the check, never a click on Next.
   ========================================================================== */
const LESSONS = {
  L1: {
    id: "L1", station: "runpayroll", mins: 8,
    title: B("Run Payroll — your first pay run", "Chạy bảng lương — đợt lương đầu tiên của bạn"),
    goal: B("Create one month of draft payslips for one division, and know exactly what you have and have not just done.",
            "Tạo phiếu lương nháp của một tháng cho một bộ phận, và biết chính xác bạn vừa làm gì và chưa làm gì."),
    steps: [
      {
        screen: "runpayroll", anchor: "pw-rail",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("This screen creates a month of pay", "Màn hình này tạo ra một tháng lương"),
        body: B("<b>Run Payroll</b> takes one division and one period and computes a draft payslip for every eligible employee. Nothing is paid here — you are creating <b>drafts</b> to review. The four dots above tell you how far through that you are.",
                "<b>Chạy bảng lương</b> nhận một bộ phận và một kỳ lương, rồi tính phiếu lương nháp cho từng nhân viên đủ điều kiện. Chưa có gì được chi trả ở đây — bạn đang tạo <b>bản nháp</b> để soát xét. Bốn chấm phía trên cho biết bạn đang ở đâu trong quy trình đó."),
      },
      {
        screen: "runpayroll", anchor: "pw-division",
        kicker: B("Step 1", "Bước 1"),
        title: B("The division chooses the rulebook", "Chọn bộ phận là chọn bộ quy tắc"),
        body: B("Picking a division here does more than filter a list of people: it selects the <b>formula configuration</b> every payslip in this run will be computed by. Retail's rules are not F&amp;B's. Choose the wrong one and every number downstream is wrong in the same direction — the hardest kind of error to spot, because nothing looks odd.",
                "Chọn bộ phận ở đây không chỉ là lọc danh sách người: nó chọn <b>cấu hình công thức</b> mà mọi phiếu lương trong đợt này sẽ được tính theo. Quy tắc của Bán lẻ khác F&amp;B. Chọn sai thì mọi con số phía sau đều sai theo cùng một hướng — loại lỗi khó phát hiện nhất, vì nhìn vào không thấy gì bất thường."),
        tip: B("The configuration name and its version are printed in the scope panel on the right. Read them before you compute, not after.",
               "Tên cấu hình và phiên bản của nó được in ở bảng phạm vi bên phải. Hãy đọc trước khi tính, đừng đọc sau."),
      },
      {
        screen: "runpayroll", anchor: "pw-scope",
        kicker: B("Step 2", "Bước 2"),
        title: B("Period and cycle", "Kỳ lương và chu kỳ"),
        body: B("The period is the month being settled. The <b>cycle</b> is which part of it: <b>mid-cycle</b> pays an advance during the month, <b>end-cycle</b> settles the whole month. Most divisions run end-cycle only, which is why running the other one by accident produces a payslip that is not wrong so much as unexpected.",
                "Kỳ lương là tháng đang được quyết toán. <b>Chu kỳ</b> là phần nào của tháng đó: <b>giữa kỳ</b> là khoản tạm ứng trong tháng, <b>cuối kỳ</b> là quyết toán cả tháng. Đa số bộ phận chỉ chạy cuối kỳ, nên chạy nhầm chu kỳ tạo ra một phiếu lương không hẳn sai — mà là ngoài dự kiến."),
      },
      {
        screen: "runpayroll", anchor: "pw-summary",
        kicker: B("Before you act", "Trước khi thao tác"),
        title: B("Read the eligible count before you compute", "Đọc số nhân viên đủ điều kiện rồi mới tính"),
        body: B("Payobook prints which configuration will run and how many employees are eligible. That count is your smoke alarm. If it says 12 where you expected 48, <b>stop</b> — the month's attendance import almost certainly has not been committed, and computing now would produce 12 real-looking payslips and 36 missing ones.",
                "Payobook in ra cấu hình nào sẽ chạy và bao nhiêu nhân viên đủ điều kiện. Con số đó là chuông báo khói của bạn. Nếu nó hiện 12 trong khi bạn chờ 48, hãy <b>dừng lại</b> — gần như chắc chắn dữ liệu chấm công của tháng chưa được ghi nhận, và tính lúc này sẽ tạo ra 12 phiếu trông rất thật và 36 phiếu thiếu."),
      },
      {
        screen: "runpayroll", anchor: "pw-compute",
        kicker: B("The action", "Thao tác chính"),
        title: B("Compute — what actually happens", "Tính — điều gì thực sự diễn ra"),
        body: B("One press runs the formula configuration for every eligible employee: gross, allowances, BHXH/BHYT/BHTN, thuế TNCN, net. It takes seconds and it writes 48 draft records.",
                "Một cú bấm chạy cấu hình công thức cho toàn bộ nhân viên đủ điều kiện: tổng thu nhập, phụ cấp, BHXH/BHYT/BHTN, thuế TNCN, thực nhận. Mất vài giây và ghi ra 48 bản nháp."),
        consequence: B("Affects July 2026 × Retail — Hà Nội only, 48 draft payslips. Reversible: <b>yes</b> — drafts can be recomputed or deleted, and nothing is paid or sent. No employee sees anything until the whole run reaches done. Verify first: the eligible count above, and that the month's import is committed.",
                       "Ảnh hưởng: chỉ Tháng 7/2026 × Bán lẻ — Hà Nội, 48 phiếu lương nháp. Hoàn tác: <b>được</b> — bản nháp có thể tính lại hoặc xoá, và chưa có gì được chi hay gửi đi. Nhân viên không thấy gì cho tới khi cả đợt đạt trạng thái Hoàn tất. Kiểm tra trước: số nhân viên đủ điều kiện ở trên, và dữ liệu nhập của tháng đã được ghi nhận."),
      },
      {
        screen: "runpayroll", anchor: "pw-pills",
        kicker: B("Reading results", "Đọc kết quả"),
        title: B("48 computed, 1 needs review", "48 phiếu đã tính, 1 phiếu cần soát xét"),
        body: B("Three numbers: how many payslips exist, how many computed cleanly, and how many the engine wants a human to look at. That third one is <b>Need review</b>, and it is not an error count. A flag is the engine saying it found something unusual and would like you to confirm it is intended.",
                "Ba con số: có bao nhiêu phiếu lương, bao nhiêu phiếu tính sạch, và bao nhiêu phiếu hệ thống muốn có người xem. Con số thứ ba là <b>Cần soát xét</b>, và nó không phải số lỗi. Cờ cảnh báo là hệ thống nói rằng nó thấy điều gì đó bất thường và muốn bạn xác nhận đó là có chủ ý."),
      },
      {
        screen: "runpayroll", anchor: "pw-exceptions",
        kicker: B("The judgement", "Phần cần phán đoán"),
        title: B("One flag, and why it is not an error", "Một cờ cảnh báo, và vì sao đó không phải lỗi"),
        body: B("Trần Văn Hùng's overtime is 4,200,000 ₫ against 1,100,000 ₫ in June — 382% of last month. That may be perfectly correct: a shop refit, a peak week, a genuine burst. It may also be 4.6 hours typed as 46. The engine cannot tell those apart and does not pretend to; you can, by checking the timesheet.",
                "Tăng ca của Trần Văn Hùng là 4.200.000 ₫ so với 1.100.000 ₫ của tháng 6 — bằng 382% tháng trước. Điều đó hoàn toàn có thể đúng: sửa cửa hàng, tuần cao điểm, một đợt tăng ca thật. Nhưng cũng có thể là 4,6 giờ bị gõ thành 46. Hệ thống không phân biệt được và cũng không giả vờ là phân biệt được; bạn thì phân biệt được, bằng cách đối chiếu bảng chấm công."),
        tip: B("A flag you clear without understanding is a flag you have answered with a guess.",
               "Một cờ cảnh báo bạn xoá đi mà chưa hiểu là một cờ bạn đã trả lời bằng phỏng đoán."),
      },
      {
        screen: "payruns", anchor: "rep-pipeline",
        kicker: B("Where it goes", "Đi về đâu"),
        title: B("Your run enters the pipeline", "Đợt lương vào quy trình"),
        body: B("The run is now in <b>draft</b> on the Pay Runs board. From here it travels through the Payroll Officer tier, {{hrTierName}}, {{gmTierName}} and then done. Each gate belongs to one group; nobody can skip one, and a rejection at any of them returns the run to draft with a written reason.",
                "Đợt lương giờ ở trạng thái <b>Nháp</b> trên bảng Đợt tính lương. Từ đây nó đi qua vòng Chuyên viên tính lương, {{hrTierName}}, {{gmTierName}} rồi Hoàn tất. Mỗi cổng thuộc về một nhóm quyền; không ai bỏ qua được cổng nào, và bị từ chối ở bất kỳ cổng nào cũng đưa đợt về Nháp kèm lý do bằng văn bản."),
        moment: { kind: "pipeline", chain: "payrun" },
      },
    ],
    quiz: {
      question: B("You computed July for Retail and then spot that one employee's overtime input is wrong. What is the safest next step?",
                  "Bạn đã tính lương tháng 7 cho Bán lẻ, rồi phát hiện dữ liệu tăng ca của một nhân viên bị sai. Bước an toàn nhất là gì?"),
      options: [
        {
          text: B("Edit the net amount directly on the payslip", "Sửa thẳng số thực nhận trên phiếu lương"),
          correct: false,
          explanation: B("Let's rethink that. Editing the output breaks the trail: the slip no longer agrees with the data behind it, and the next recompute silently undoes your fix — so the mistake comes back without anyone touching it.",
                         "Hãy nghĩ lại một chút. Sửa kết quả làm đứt vết dữ liệu: phiếu không còn khớp với dữ liệu phía sau, và lần tính lại kế tiếp sẽ âm thầm xoá sửa đổi của bạn — lỗi quay lại mà không ai chạm vào."),
        },
        {
          text: B("Fix the overtime input, then recompute the draft", "Sửa dữ liệu tăng ca, rồi tính lại bản nháp"),
          correct: true,
          explanation: B("Exactly. Drafts exist for this: correct the input, recompute, and every dependent line — gross, thuế TNCN, net — corrects itself, because they were all derived from that input in the first place.",
                         "Chính xác. Bản nháp sinh ra để làm việc đó: sửa đầu vào, tính lại, và mọi dòng phụ thuộc — tổng thu nhập, thuế TNCN, thực nhận — tự đúng theo, vì tất cả vốn được suy ra từ đầu vào đó."),
        },
        {
          text: B("Submit for approval now and correct it next month", "Cứ trình phê duyệt, tháng sau sửa"),
          correct: false,
          explanation: B("Let's rethink that. It turns a thirty-second fix into a retro line next month — and an employee who was paid the wrong amount today, which is the part they will remember.",
                         "Hãy nghĩ lại một chút. Việc đó biến một sửa đổi ba mươi giây thành một dòng hồi tố tháng sau — và một nhân viên bị trả sai ngay hôm nay, đó mới là điều họ nhớ."),
        },
      ],
    },
  },

  L2: {
    id: "L2", station: "payruns", mins: 7,
    title: B("The board and the gates", "Bảng đợt lương và các cổng phê duyệt"),
    goal: B("Read the Pay Runs board the way payroll week needs it read: what is stuck, whose gate it is stuck at, and what a rejection actually does.",
            "Đọc bảng Đợt tính lương theo đúng cách mà tuần tính lương cần: cái gì đang tắc, tắc ở cổng của ai, và từ chối thực sự gây ra điều gì."),
    steps: [
      {
        screen: "payruns", anchor: "pk-kpis",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Five numbers, and only one of them is yours", "Năm con số, và chỉ một con số là của bạn"),
        body: B("Total runs, in pipeline, <b>awaiting your approval</b>, completed, net paid. Four of those describe the department. The third one describes you: it is the work that will not move until you move it, and it is the number to read first every morning of payroll week.",
                "Tổng số đợt, đang trong quy trình, <b>chờ bạn phê duyệt</b>, đã hoàn tất, đã chi. Bốn con số mô tả cả bộ phận. Con số thứ ba mô tả bạn: đó là phần việc sẽ không nhúc nhích cho tới khi bạn động vào, và là con số cần đọc đầu tiên mỗi sáng trong tuần tính lương."),
      },
      {
        screen: "payruns", anchor: "pk-tabs",
        kicker: B("Reading the board", "Đọc bảng"),
        title: B("The columns are stages, not months", "Các cột là bước phê duyệt, không phải tháng"),
        body: B("This is the single most common misreading of this screen. A column is an <b>approval stage</b>, so July and June can sit side by side in the same one, and a run moves left to right by being approved — never by being edited. Use the date chips below when you want a period.",
                "Đây là cách đọc sai phổ biến nhất của màn hình này. Một cột là một <b>bước phê duyệt</b>, nên tháng 7 và tháng 6 có thể nằm cạnh nhau trong cùng một cột, và một đợt di chuyển từ trái sang phải bằng việc được phê duyệt — không bao giờ bằng việc bị sửa. Muốn lọc theo kỳ, hãy dùng các chip ngày ở dưới."),
      },
      {
        screen: "payruns", anchor: "rep-pipeline",
        kicker: B("The chain", "Chuỗi phê duyệt"),
        title: B("Draft, Officer, {{hrTierName}}, {{gmTierName}}, done", "Nháp, Chuyên viên tính lương, {{hrTierName}}, {{gmTierName}}, Hoàn tất"),
        body: B("Five stages, in that order, every time. Each gate belongs to one group, so the chain is also an answer to 'who do I chase': the run's current column names the person. Nothing skips a gate — not for a deadline, not for a director.",
                "Năm bước, đúng thứ tự đó, mọi lúc. Mỗi cổng thuộc về một nhóm quyền, nên chuỗi này cũng là câu trả lời cho 'tôi phải hỏi ai': cột hiện tại của đợt lương chỉ đích danh người đó. Không gì bỏ qua được một cổng — không vì hạn chót, không vì cấp trên."),
        moment: { kind: "pipeline", chain: "payrun" },
      },
      {
        screen: "payruns", anchor: "pk-card-actions",
        kicker: B("The card", "Thẻ đợt lương"),
        title: B("A card only offers what you can actually do", "Thẻ chỉ hiện những gì bạn thực sự làm được"),
        body: B("The buttons on a card are decided by the record's own gate fields and your groups — not by the card. If you cannot see Approve here, you do not hold that tier, and pressing harder will not help. That is also why the same run shows different buttons to different people.",
                "Các nút trên thẻ do chính các trường kiểm soát cổng của bản ghi và nhóm quyền của bạn quyết định — không phải do thẻ. Nếu bạn không thấy nút Phê duyệt ở đây thì bạn không giữ vòng đó, và bấm mạnh hơn cũng không giúp được. Đó cũng là lý do cùng một đợt lương lại hiện các nút khác nhau với những người khác nhau."),
      },
      {
        screen: "payruns", anchor: "pk-card",
        kicker: B("The hard part", "Phần khó"),
        title: B("A rejection is testimony, not a rebuke", "Từ chối là lời chứng, không phải lời quở trách"),
        body: B("Rejecting sends the whole run back to <b>draft</b> and records three things against it: who rejected it, when, and <b>why in writing</b>. That written reason is the entire value of the rejection. Without it the officer who has to fix the run is guessing at what you saw, and will probably resubmit the same thing.",
                "Từ chối đưa cả đợt lương về <b>Nháp</b> và ghi lại ba điều: ai từ chối, vào lúc nào, và <b>vì sao, bằng văn bản</b>. Chính lý do bằng văn bản đó mới là giá trị của việc từ chối. Không có nó, chuyên viên phải sửa đợt lương chỉ còn cách đoán xem bạn đã thấy gì, và nhiều khả năng sẽ trình lại đúng thứ cũ."),
        consequence: B("Affects the whole run, not one payslip: all 48 return to draft together. Reversible: <b>yes</b> — it is recomputed and resubmitted through the same chain, and nothing was paid. Verify first: that the problem really is the run, and not a single slip you could have discussed.",
                       "Ảnh hưởng cả đợt lương, không phải một phiếu: cả 48 phiếu cùng quay về Nháp. Hoàn tác: <b>được</b> — đợt sẽ được tính lại và trình lại qua đúng chuỗi đó, và chưa có gì được chi. Kiểm tra trước: vấn đề có thực sự nằm ở cả đợt không, hay chỉ là một phiếu mà bạn có thể trao đổi riêng."),
      },
      {
        screen: "payruns", anchor: "pk-datechips",
        kicker: B("Scoping", "Phạm vi"),
        title: B("Every count above is scoped by these chips", "Mọi con số ở trên đều bị các chip này giới hạn"),
        body: B("The KPI band is not the whole database — it is whatever the active date chip and division chip allow through. A number that looks alarming is worth re-reading with the scope in mind before it becomes an email.",
                "Dải chỉ số không phải toàn bộ cơ sở dữ liệu — nó là những gì chip ngày và chip bộ phận đang chọn cho đi qua. Một con số trông đáng báo động rất đáng được đọc lại cùng với phạm vi đang lọc, trước khi nó trở thành một email."),
      },
      {
        screen: "payruns", anchor: "pk-card-actions",
        kicker: B("The far end", "Đầu bên kia"),
        title: B("Done unlocks the money, and locks the run", "Hoàn tất mở khoá tiền, và khoá đợt lương"),
        body: B("Only a completed run offers {{bankFileFormat}}, the journals and the payments. That is the point of the chain — those buttons appear exactly when every gate has said yes. It is also the last reversible moment: after done, a correction is a retro line, never an edit.",
                "Chỉ đợt đã Hoàn tất mới hiện {{bankFileFormat}}, bút toán và các khoản thanh toán. Đó chính là ý nghĩa của chuỗi phê duyệt — các nút đó xuất hiện đúng lúc mọi cổng đã đồng ý. Đây cũng là thời điểm cuối còn hoàn tác được: sau Hoàn tất, mọi hiệu chỉnh là một dòng hồi tố, không bao giờ là sửa trực tiếp."),
      },
    ],
    quiz: {
      question: B("A run has been sitting at {{hrTierName}} for two days and payday is on {{payDay}}. You are the Payroll Officer. What do you do?",
                  "Một đợt lương đã nằm ở {{hrTierName}} hai ngày và ngày trả lương là {{payDay}}. Bạn là Chuyên viên tính lương. Bạn làm gì?"),
      options: [
        {
          text: B("Recompute the run so it moves forward", "Tính lại đợt lương để nó đi tiếp"),
          correct: false,
          explanation: B("Let's rethink that. Recomputing does not move a run through a gate — approving does. It would also change figures the reviewer has already read, so they would have to start again.",
                         "Hãy nghĩ lại một chút. Tính lại không đưa đợt lương qua được một cổng — chỉ phê duyệt mới làm được. Nó còn thay đổi những con số mà người soát xét đã đọc, nên họ sẽ phải bắt đầu lại từ đầu."),
        },
        {
          text: B("Ask the person who holds that tier — the column names them", "Hỏi người giữ vòng đó — cột đã chỉ đích danh"),
          correct: true,
          explanation: B("Yes. The column a run is sitting in is the answer to who can move it. Chasing the right person is the only thing that shortens the wait, and it is also the fastest way to find out whether they are stuck on something you can resolve.",
                         "Đúng vậy. Cột mà đợt lương đang nằm chính là câu trả lời cho việc ai có thể đẩy nó đi. Hỏi đúng người là cách duy nhất rút ngắn thời gian chờ, và cũng là cách nhanh nhất để biết họ đang vướng điều gì mà bạn có thể gỡ."),
        },
        {
          text: B("Reject it yourself and start a clean run", "Tự từ chối rồi chạy lại một đợt sạch"),
          correct: false,
          explanation: B("Let's rethink that. A rejection is testimony about a problem you found — using it as a scheduling tool puts a reason on the record that is not true, and throws away two days of somebody's review.",
                         "Hãy nghĩ lại một chút. Từ chối là lời chứng về một vấn đề bạn phát hiện — dùng nó như công cụ điều phối tiến độ sẽ ghi vào hồ sơ một lý do không đúng sự thật, và vứt bỏ hai ngày soát xét của người khác."),
        },
      ],
    },
  },

  L3: {
    id: "L3", station: "payslips", mins: 6,
    title: B("Read a payslip like an auditor", "Đọc phiếu lương như một kiểm toán viên"),
    goal: B("Take one payslip apart line by line and be able to say, out loud, where every number came from.",
            "Bóc tách một phiếu lương theo từng dòng và nói được thành lời mỗi con số đến từ đâu."),
    steps: [
      {
        screen: "payslips", anchor: "ps-runsel",
        kicker: B("Scope first", "Phạm vi trước"),
        title: B("Everything below belongs to one run", "Mọi thứ bên dưới thuộc về một đợt lương"),
        body: B("The selector at the top names the run. Every KPI, every chip and every slip under it is scoped to that run — so comparing two months means changing this control, not scrolling.",
                "Ô chọn ở trên cùng cho biết đợt lương nào. Mọi chỉ số, mọi chip lọc và mọi phiếu bên dưới đều thuộc đợt đó — nên muốn so hai tháng là đổi ô này, không phải cuộn xuống."),
      },
      {
        screen: "payslips", anchor: "ps-chips",
        kicker: B("Where to start", "Bắt đầu từ đâu"),
        title: B("Read Need review first, always", "Luôn đọc Cần soát xét trước tiên"),
        body: B("Forty-eight slips is more than anyone reads carefully. The engine has already told you which ones it could not settle on its own — start there, and sample a few of the rest. Reading top to bottom is how a flagged slip gets approved at 6pm.",
                "Bốn mươi tám phiếu là nhiều hơn mức bất kỳ ai đọc kỹ được. Hệ thống đã nói cho bạn biết những phiếu nào nó không tự quyết được — hãy bắt đầu từ đó, rồi lấy mẫu vài phiếu còn lại. Đọc lần lượt từ trên xuống chính là cách một phiếu bị gắn cờ được duyệt lúc 6 giờ chiều."),
      },
      {
        screen: "payslips", anchor: "ps-status",
        kicker: B("Whose is it now", "Giờ là của ai"),
        title: B("A payslip carries its own position", "Mỗi phiếu lương mang vị trí của chính nó"),
        body: B("The stepper here is this slip's stage, which is not always the run's. That distinction matters when a single payslip has been pulled out for a question while the rest of the batch moved on.",
                "Thanh trạng thái ở đây là bước của chính phiếu này, không phải lúc nào cũng trùng với bước của cả đợt. Sự khác biệt đó quan trọng khi một phiếu bị tách ra để hỏi trong khi phần còn lại của lô đã đi tiếp."),
      },
      {
        screen: "payslips", anchor: "ps-breakdown",
        kicker: B("The working", "Phần tính toán"),
        title: B("Gross to net, one line at a time", "Từ tổng thu nhập tới thực nhận, từng dòng một"),
        body: B("Mai's July: base 12,000,000 plus allowances 780,000 plus overtime 1,500,000 is a gross of <b>14,280,000 ₫</b>. Then BHXH 960,000, BHYT 180,000, BHTN 120,000 and thuế TNCN 101,000 come off, leaving <b>12,919,000 ₫</b>. Every one of those is a named rule, not a typed number.",
                "Tháng 7 của Mai: lương cơ bản 12.000.000 cộng phụ cấp 780.000 cộng tăng ca 1.500.000 là tổng thu nhập <b>14.280.000 ₫</b>. Sau đó trừ BHXH 960.000, BHYT 180.000, BHTN 120.000 và thuế TNCN 101.000, còn lại <b>12.919.000 ₫</b>. Mỗi khoản đó là một quy tắc có tên, không phải một con số gõ tay."),
        moment: { kind: "calc" },
      },
      {
        screen: "payslips", anchor: "ps-breakdown",
        kicker: B("The one that surprises people", "Điều khiến nhiều người bất ngờ"),
        title: B("Insurance is not charged on what you earned", "Bảo hiểm không tính trên số bạn kiếm được"),
        body: B("BHXH, BHYT and BHTN are charged on the <b>registered insurance base</b> — for Mai, 12,000,000 ₫, her contract base. Not on gross. That is why 1,500,000 ₫ of overtime moved her tax and did not move her insurance by a single đồng, and it answers most variance questions before they are asked.",
                "BHXH, BHYT và BHTN tính trên <b>mức lương đóng bảo hiểm đã đăng ký</b> — với Mai là 12.000.000 ₫, tức lương cơ bản trên hợp đồng. Không tính trên tổng thu nhập. Vì vậy 1.500.000 ₫ tăng ca làm thay đổi thuế của cô ấy nhưng không làm bảo hiểm nhúc nhích một đồng, và điều đó trả lời hầu hết thắc mắc về biến động trước cả khi ai đó hỏi."),
        tip: B("Say it as a sentence: insurance follows the contract, tax follows the month.",
               "Hãy nói thành một câu: bảo hiểm bám theo hợp đồng, thuế bám theo tháng."),
      },
      {
        screen: "payslips", anchor: "ps-detail",
        kicker: B("Before & after", "Trước & sau"),
        title: B("The same employee, two months", "Cùng một nhân viên, hai tháng"),
        body: B("Toggle between June and July and watch which lines move. Overtime and thuế TNCN move; insurance does not. Once you can predict which lines will move before you look, you can review forty-eight payslips in the time it used to take to explain one.",
                "Chuyển qua lại giữa tháng 6 và tháng 7 và xem dòng nào thay đổi. Tăng ca và thuế TNCN thay đổi; bảo hiểm thì không. Khi bạn đoán được dòng nào sẽ thay đổi trước cả khi nhìn, bạn soát được bốn mươi tám phiếu trong khoảng thời gian trước kia chỉ đủ để giải thích một phiếu."),
        moment: { kind: "morph", which: "maiJuneJuly" },
      },
    ],
    quiz: {
      question: B("An employee's overtime doubled this month but their BHXH deduction is unchanged. What is the correct reading?",
                  "Tăng ca của một nhân viên tăng gấp đôi tháng này nhưng khoản khấu trừ BHXH không đổi. Cách hiểu đúng là gì?"),
      options: [
        {
          text: B("The insurance calculation is broken and should be reported", "Phần tính bảo hiểm bị lỗi và cần được báo lại"),
          correct: false,
          explanation: B("Let's rethink that. It is working exactly as the law describes: contributions are charged on the registered base, and overtime is not part of that base. Reporting it would send someone looking for a bug that is not there.",
                         "Hãy nghĩ lại một chút. Nó đang chạy đúng như luật quy định: bảo hiểm tính trên mức lương đóng BH đã đăng ký, và tăng ca không nằm trong mức đó. Báo lỗi sẽ khiến ai đó đi tìm một lỗi không tồn tại."),
        },
        {
          text: B("Correct — insurance is charged on the registered base, which overtime does not change", "Đúng — bảo hiểm tính trên mức lương đóng BH đã đăng ký, mà tăng ca không làm thay đổi"),
          correct: true,
          explanation: B("Yes. Insurance follows the contract, tax follows the month. This is the single fact that explains most of the variance questions a payroll desk receives, and being able to say it plainly is worth more than any report.",
                         "Đúng vậy. Bảo hiểm bám theo hợp đồng, thuế bám theo tháng. Đây là điều duy nhất giải thích được phần lớn thắc mắc về biến động mà bộ phận lương nhận được, và nói được nó một cách rõ ràng còn giá trị hơn bất kỳ báo cáo nào."),
        },
        {
          text: B("Their insurance base should be raised to match the higher earnings", "Cần nâng mức đóng bảo hiểm của họ cho khớp thu nhập cao hơn"),
          correct: false,
          explanation: B("Let's rethink that. The registered base is a declared contract figure, not something payroll adjusts to follow a busy month — changing it is an HR and legal decision with consequences well beyond this payslip.",
                         "Hãy nghĩ lại một chút. Mức lương đóng BH là con số đã đăng ký theo hợp đồng, không phải thứ bộ phận lương chỉnh theo một tháng bận rộn — thay đổi nó là quyết định của nhân sự và pháp chế, với hệ quả vượt xa phiếu lương này."),
        },
      ],
    },
  },

  L4: {
    id: "L4", station: "import", mins: 6,
    title: B("Import with confidence", "Nhập dữ liệu một cách chắc chắn"),
    goal: B("Get a month of attendance and overtime into Payobook, and know exactly what the confidence score is telling you before you commit.",
            "Đưa dữ liệu chấm công và tăng ca của một tháng vào Payobook, và hiểu rõ điểm tin cậy đang nói gì trước khi bạn ghi nhận."),
    steps: [
      {
        screen: "import", anchor: "im-pipe",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Map, validate, commit — and only the last one writes", "Ánh xạ, kiểm tra, ghi nhận — và chỉ bước cuối mới ghi dữ liệu"),
        body: B("Three stages, and a batch that stops before the last one has changed nothing at all. That is the whole design: you are allowed to load a bad file, look at it, and walk away, and the system is exactly as it was.",
                "Ba bước, và một đợt nhập dừng trước bước cuối thì hoàn toàn chưa thay đổi gì. Đó chính là toàn bộ thiết kế: bạn được phép nạp một tệp sai, nhìn nó, rồi bỏ đi, và hệ thống vẫn y nguyên như trước."),
      },
      {
        screen: "import", anchor: "im-cta",
        kicker: B("The way in", "Lối vào"),
        title: B("Use the guided flow", "Hãy dùng luồng có hướng dẫn"),
        body: B("The other import surfaces exist for specific tools and older habits. This one scores the file before it writes, which is the difference between finding a bad row now and finding it on {{payDay}}.",
                "Các màn hình nhập liệu khác tồn tại cho những công cụ riêng và thói quen cũ. Luồng này chấm điểm tệp trước khi ghi, và đó là khác biệt giữa việc phát hiện một dòng sai ngay bây giờ và phát hiện nó vào {{payDay}}."),
      },
      {
        screen: "importwizard", anchor: "iw-review",
        kicker: B("The score", "Điểm tin cậy"),
        title: B("What 95.8% actually means", "95,8% thực sự nghĩa là gì"),
        body: B("It is not a grade. It is the share of rows the importer could match to an employee and read without ambiguity: 46 of 48. 95.8% of 48 rows still leaves two rows that need a human — and those two are the ones that become a missing or a wrong payslip.",
                "Đây không phải điểm số học. Đó là tỷ lệ dòng mà trình nhập liệu khớp được với một nhân viên và đọc được không nhập nhằng: 46 trên 48. 95,8% của 48 dòng vẫn còn hai dòng cần con người xử lý — và đúng hai dòng đó sẽ trở thành một phiếu lương thiếu hoặc sai."),
      },
      {
        screen: "importwizard", anchor: "iw-fixrows",
        kicker: B("Fixing", "Xử lý"),
        title: B("Match, Retry or Skip — and Skip has a cost", "Khớp, Thử lại hay Bỏ qua — và Bỏ qua có cái giá của nó"),
        body: B("<b>Match</b> points a row at the right employee. <b>Retry</b> re-reads it after you correct the file. <b>Skip</b> drops it — which is legitimate for a duplicate row and quietly wrong for an employee, because a skipped employee is simply absent from the run.",
                "<b>Khớp</b> trỏ một dòng tới đúng nhân viên. <b>Thử lại</b> đọc lại dòng đó sau khi bạn sửa tệp. <b>Bỏ qua</b> loại dòng đó ra — hợp lý với một dòng bị lặp, và sai một cách âm thầm với một nhân viên, vì nhân viên bị bỏ qua đơn giản là vắng mặt trong đợt lương."),
        tip: B("Skipping a duplicate and skipping a person look identical on this screen. The difference is entirely in what you understood about the row.",
               "Bỏ qua một dòng lặp và bỏ qua một con người trông y hệt nhau trên màn hình này. Khác biệt nằm hoàn toàn ở chỗ bạn đã hiểu gì về dòng đó."),
      },
      {
        screen: "importwizard", anchor: "iw-commit",
        kicker: B("The action", "Thao tác chính"),
        title: B("Commit is the first thing here that writes", "Ghi nhận là thứ đầu tiên ở đây thực sự ghi dữ liệu"),
        body: B("Everything before this was a preview. Pressing it writes the rows into the period and they become the inputs the next compute reads.",
                "Mọi thứ trước bước này chỉ là xem trước. Bấm nút này sẽ ghi các dòng vào kỳ lương và chúng trở thành dữ liệu đầu vào cho lần tính tiếp theo."),
        consequence: B("Affects the period this batch names, for every row it holds. Reversible: <b>partly</b> — you can import a correction, but rows already read into a computed run leave payslips that must be recomputed. Verify first: the period on the batch, that Need attention is zero, and that every Skip you used was a duplicate and not a person.",
                       "Ảnh hưởng: kỳ lương mà đợt nhập này ghi tên, với mọi dòng nó chứa. Hoàn tác: <b>một phần</b> — bạn có thể nhập một bản sửa, nhưng những dòng đã được đọc vào một đợt đã tính sẽ để lại các phiếu lương phải tính lại. Kiểm tra trước: kỳ lương trên đợt nhập, mục Cần xử lý bằng không, và mọi lần Bỏ qua đều là dòng lặp chứ không phải một con người."),
      },
      {
        screen: "payslips", anchor: "ps-breakdown",
        kicker: B("The rule this teaches", "Nguyên tắc bài này dạy"),
        title: B("Never fix an import on the payslips", "Đừng bao giờ sửa lỗi nhập liệu trên phiếu lương"),
        body: B("It is tempting: the payslip is right in front of you and the number is obviously wrong. But editing here corrects the output and leaves the input untouched, so the next recompute brings the mistake straight back — and now the slip and the timesheet disagree, which is worse than the original error.",
                "Rất dễ bị cám dỗ: phiếu lương đang ngay trước mặt và con số rõ ràng là sai. Nhưng sửa ở đây chỉ chỉnh kết quả và để nguyên đầu vào, nên lần tính lại kế tiếp mang lỗi quay lại ngay — và giờ phiếu lương với bảng chấm công không khớp nhau, còn tệ hơn lỗi ban đầu."),
      },
    ],
    quiz: {
      question: B("The confidence score is 91%, five rows need attention, and the import cut-off is {{importCutoff}}. What do you do?",
                  "Điểm tin cậy là 91%, năm dòng cần xử lý, và hạn nhập liệu là {{importCutoff}}. Bạn làm gì?"),
      options: [
        {
          text: B("Commit — 91% is high enough and the deadline is today", "Ghi nhận — 91% là đủ cao và hôm nay là hạn"),
          correct: false,
          explanation: B("Let's rethink that. The score is not a pass mark; the five rows are five people. Committing now means five payslips that are missing or wrong, discovered by the employees rather than by you.",
                         "Hãy nghĩ lại một chút. Điểm tin cậy không phải điểm đạt; năm dòng đó là năm con người. Ghi nhận lúc này nghĩa là năm phiếu lương thiếu hoặc sai, và người phát hiện ra sẽ là nhân viên chứ không phải bạn."),
        },
        {
          text: B("Resolve the five rows first, then commit", "Xử lý năm dòng đó trước, rồi mới ghi nhận"),
          correct: true,
          explanation: B("Yes. Each of those rows is a person who would otherwise be absent from the run or paid on the wrong figure — and every one of them is cheaper to fix now than as a retro line next month.",
                         "Đúng vậy. Mỗi dòng đó là một con người, nếu không xử lý thì sẽ vắng mặt trong đợt lương hoặc bị trả sai — và xử lý ngay bây giờ luôn rẻ hơn một dòng hồi tố vào tháng sau."),
        },
        {
          text: B("Skip the five rows so the score reaches 100%", "Bỏ qua năm dòng đó để điểm đạt 100%"),
          correct: false,
          explanation: B("Let's rethink that. Skipping removes the rows from the batch, not the problem from the month — the score goes green because those people are no longer in the import at all.",
                         "Hãy nghĩ lại một chút. Bỏ qua chỉ loại các dòng ra khỏi đợt nhập, không loại vấn đề ra khỏi tháng — điểm xanh lên vì những người đó không còn trong dữ liệu nhập nữa."),
        },
      ],
    },
  },

  /* ===========================================================================
     THE SETUP LINE.

     L5 and L6 render over two NEW replicas. The anchors on the formula screen
     are the REAL Formula Studio's — fs-config, fs-components, fs-formula,
     fs-namesletters, fs-deps, fs-preview, fs-simulate — because pb_learn adds
     nothing to studio.xml and does not need to: those attributes have been in
     that template since before this module existed. The registry now OWNS the
     seven the content names, which is what makes a rename break a build
     instead of a lesson.
     ======================================================================== */
  L5: {
    id: "L5", station: "formula", mins: 7,
    title: B("The formula is the payslip", "Công thức chính là phiếu lương"),
    goal: B("Read a division's rulebook end to end, and be able to point at the component that produced any line on a payslip.",
            "Đọc trọn bộ quy tắc của một bộ phận, và chỉ đúng được thành phần đã tạo ra bất kỳ dòng nào trên phiếu lương."),
    steps: [
      {
        screen: "formula", anchor: "fs-config",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("One division, one rulebook", "Một bộ phận, một bộ quy tắc"),
        body: B("This is <b>HOASEN_RETAIL_END</b> — the configuration every Retail payslip is computed by. The name at the top is a switcher: other divisions have their own, and they are not variations of this one. Choosing a division in Run Payroll is choosing which of these runs.",
                "Đây là <b>HOASEN_RETAIL_END</b> — cấu hình mà mọi phiếu lương của Bán lẻ được tính theo. Cái tên ở trên cùng là một ô chuyển: các bộ phận khác có cấu hình riêng, và chúng không phải biến thể của cấu hình này. Chọn bộ phận trong Chạy bảng lương chính là chọn cấu hình nào sẽ chạy."),
        tip: B("The code is the thing to quote when you ask someone about a number: \"HOASEN_RETAIL_END, component TNCN\" is a question that can be answered.",
               "Mã cấu hình là thứ nên trích dẫn khi bạn hỏi ai đó về một con số: \"HOASEN_RETAIL_END, thành phần TNCN\" là một câu hỏi có thể trả lời được."),
      },
      {
        screen: "formula", anchor: "fs-components",
        kicker: B("The inventory", "Danh mục thành phần"),
        title: B("Every line on a payslip is a component here", "Mỗi dòng trên phiếu lương là một thành phần ở đây"),
        body: B("Ten components in four kinds — <b>inputs</b> (base salary), <b>earnings</b> (allowances, overtime), <b>deductions</b> (BHXH, BHYT, BHTN, thuế TNCN) and <b>totals</b> (gross, taxable, net) — and below them the <b>parameters</b> those formulas reference. Nothing on a payslip comes from anywhere else: if a line exists it is one of these, and if a line is wrong the number behind it is one of these too.",
                "Mười thành phần thuộc bốn loại — <b>đầu vào</b> (lương cơ bản), <b>thu nhập</b> (phụ cấp, tăng ca), <b>khấu trừ</b> (BHXH, BHYT, BHTN, thuế TNCN) và <b>các tổng</b> (tổng thu nhập, thu nhập chịu thuế, thực nhận) — và bên dưới là các <b>tham số</b> mà những công thức đó tham chiếu tới. Không dòng nào trên phiếu lương đến từ nơi khác: có dòng nào thì nó là một trong số này, và dòng nào sai thì con số đứng sau nó cũng nằm trong số này."),
        tip: B("<b>EESI</b>, <b>EEHI</b> and <b>EEUI</b> are the contribution rates, and they live HERE — on the configuration. The Statutory screen declares what the company contributes; this is what actually charges it.",
               "<b>EESI</b>, <b>EEHI</b> và <b>EEUI</b> là các tỷ lệ đóng bảo hiểm, và chúng nằm Ở ĐÂY — trên cấu hình. Màn hình Bảo hiểm & Thuế khai báo mức doanh nghiệp đóng; còn đây mới là nơi thật sự tính ra khoản đó."),
      },
      {
        screen: "formula", anchor: "fs-formula",
        kicker: B("The formula", "Công thức"),
        title: B("Read it out loud and it is just a sentence", "Đọc to lên thì nó chỉ là một câu"),
        body: B("<b>TNCN = 5% × TNCT</b>, and <b>TNCT = GROSS − (BHXH + BHYT + BHTN) − 11,000,000</b>. That is the whole of Mai's tax line: gross, less her insurance, less the personal deduction, then the first band's rate. Each coloured chip is a component you can click through to.",
                "<b>TNCN = 5% × TNCT</b>, và <b>TNCT = Tổng thu nhập − (BHXH + BHYT + BHTN) − 11.000.000</b>. Đó là toàn bộ dòng thuế của Mai: tổng thu nhập, trừ bảo hiểm của cô ấy, trừ giảm trừ bản thân, rồi nhân thuế suất bậc đầu tiên. Mỗi chip màu là một thành phần bạn bấm vào để đi tiếp."),
        tip: B("The 11,000,000 is written as a chip, not typed into the formula twice. One relief figure, one place to change it.",
               "Con số 11.000.000 được viết thành một chip, không phải gõ lặp lại hai lần trong công thức. Một mức giảm trừ, một chỗ để sửa."),
      },
      {
        screen: "formula", anchor: "fs-namesletters",
        kicker: B("Two ways to read", "Hai cách đọc"),
        title: B("Names for people, letters for spreadsheets", "Tên cho người đọc, chữ cái cho bảng tính"),
        body: B("The same formula switches between <b>Names</b> (TNCN = 5% × TNCT) and <b>Letters</b> (I = 5% × H). Letters are how the engine stores it and how it reads next to a spreadsheet; names are how you explain it to somebody. They are one formula in two spellings, so a change in either is a change in both.",
                "Cùng một công thức chuyển qua lại giữa <b>Tên</b> (TNCN = 5% × TNCT) và <b>Chữ cái</b> (I = 5% × H). Chữ cái là cách hệ thống lưu công thức và là cách nó đọc song song với một bảng tính; tên là cách bạn giải thích cho người khác. Đó là một công thức với hai cách viết, nên sửa ở cách nào cũng là sửa cả hai."),
      },
      {
        screen: "formula", anchor: "fs-deps",
        kicker: B("The wiring", "Đường dây"),
        title: B("Depends on, and used by", "Phụ thuộc vào, và được dùng bởi"),
        body: B("TNCT <b>depends on</b> GROSS, BHXH, BHYT and BHTN — change any of those and it moves. It is <b>used by</b> THUCNHAN, so the net follows it. This panel is the one to read before renaming or deleting anything: it names, exactly, what would break.",
                "TNCT <b>phụ thuộc vào</b> Tổng thu nhập, BHXH, BHYT và BHTN — đổi bất kỳ cái nào thì nó đổi theo. Nó <b>được dùng bởi</b> THUCNHAN, nên thực nhận cũng đi theo. Đây là bảng cần đọc trước khi đổi tên hay xoá bất cứ thứ gì: nó nêu chính xác cái gì sẽ hỏng."),
      },
      {
        screen: "formula", anchor: "fs-preview",
        kicker: B("Proof", "Bằng chứng"),
        title: B("The rulebook, run on a real person", "Bộ quy tắc, chạy trên một người thật"),
        body: B("The preview evaluates the whole configuration against one employee: Mai's gross of <b>14,280,000 ₫</b>, taxable of 2,020,000, tax of 101,000 and net of <b>12,919,000 ₫</b>. This is the same arithmetic her payslip shows — the difference is that here you can see which component produced each line.",
                "Bản xem trước chạy toàn bộ cấu hình trên một nhân viên: tổng thu nhập của Mai là <b>14.280.000 ₫</b>, thu nhập chịu thuế 2.020.000, thuế 101.000 và thực nhận <b>12.919.000 ₫</b>. Vẫn đúng phép tính trên phiếu lương của cô ấy — khác ở chỗ tại đây bạn thấy được thành phần nào đã tạo ra từng dòng."),
        moment: { kind: "calc" },
      },
      {
        screen: "formula", anchor: "fs-simulate",
        kicker: B("Before you act", "Trước khi thao tác"),
        title: B("Simulate before you activate", "Mô phỏng trước khi kích hoạt"),
        body: B("<b>Simulate</b> runs the edited configuration against a period that has already been paid, and shows you what would have come out. It is the only way to see a change's effect on people rather than on one preview employee — and it costs a minute.",
                "<b>Mô phỏng</b> chạy cấu hình đã sửa trên một kỳ lương đã chi, và cho bạn thấy kết quả sẽ ra sao. Đây là cách duy nhất để thấy tác động của một thay đổi lên nhiều con người thay vì chỉ một nhân viên xem trước — và nó chỉ tốn một phút."),
        consequence: B("Affects every future payslip computed by this configuration — the whole division, not one employee, and not one month. Reversible: <b>partly</b> — the configuration can be edited back, but any run already computed on the changed version keeps its figures until it is recomputed. Verify first: the dependency panel for anything you renamed, and a simulation against last month.",
                       "Ảnh hưởng tới mọi phiếu lương tương lai được tính bằng cấu hình này — cả bộ phận, không phải một nhân viên, và không chỉ một tháng. Hoàn tác: <b>một phần</b> — cấu hình có thể sửa lại, nhưng đợt lương đã tính theo bản đã đổi vẫn giữ nguyên con số cho tới khi được tính lại. Kiểm tra trước: bảng phụ thuộc cho bất cứ thứ gì bạn đổi tên, và một lần mô phỏng trên tháng trước."),
      },
    ],
    quiz: {
      question: B("You need to add a meal allowance for Retail. The July run is computed and waiting at {{hrTierName}}. What do you do?",
                  "Bạn cần thêm phụ cấp ăn ca cho Bán lẻ. Đợt lương tháng 7 đã tính xong và đang chờ ở {{hrTierName}}. Bạn làm gì?"),
      options: [
        {
          text: B("Add the component now — the July run has already been computed, so it cannot be affected", "Thêm thành phần ngay — đợt tháng 7 đã tính xong nên không bị ảnh hưởng"),
          correct: false,
          explanation: B("Let's rethink that. Computed is not finished: a rejection at any gate sends the run back to draft, and the recompute that follows would use the configuration as it is then — so July would quietly acquire an allowance that was never approved for it.",
                         "Hãy nghĩ lại một chút. Đã tính không có nghĩa là đã xong: bị từ chối ở bất kỳ cổng nào cũng đưa đợt về Nháp, và lần tính lại sau đó sẽ dùng cấu hình tại thời điểm ấy — nên tháng 7 âm thầm có thêm một khoản phụ cấp chưa từng được duyệt cho nó."),
        },
        {
          text: B("Add the component, simulate it against last month, and apply it once July is done", "Thêm thành phần, mô phỏng trên tháng trước, và áp dụng khi tháng 7 đã Hoàn tất"),
          correct: true,
          explanation: B("Yes. The simulation tells you what the change does to real people before anybody is paid by it, and waiting for July to reach done means no open run can pick it up by accident. Both halves matter — the simulation is the evidence, the timing is the safety.",
                         "Đúng vậy. Mô phỏng cho bạn biết thay đổi này tác động thế nào tới người thật trước khi có ai được trả theo nó, còn chờ tháng 7 đạt Hoàn tất thì không đợt nào đang mở có thể vô tình nhận phải nó. Cả hai vế đều quan trọng — mô phỏng là bằng chứng, thời điểm là sự an toàn."),
        },
        {
          text: B("Add the allowance straight onto each employee's payslip instead", "Thay vào đó, cộng thẳng khoản phụ cấp vào từng phiếu lương"),
          correct: false,
          explanation: B("Let's rethink that. That is forty-eight manual edits that the next recompute erases, and next month it is forty-eight more. A component is written once and paid every month; an edit is written every month and remembered by nobody.",
                         "Hãy nghĩ lại một chút. Đó là bốn mươi tám lần sửa tay mà lần tính lại kế tiếp sẽ xoá sạch, và tháng sau lại thêm bốn mươi tám lần nữa. Một thành phần viết một lần và trả hằng tháng; một lần sửa tay phải viết lại mỗi tháng và không ai nhớ tới."),
        },
      ],
    },
  },

  L6: {
    id: "L6", station: "statutory", mins: 8,
    title: B("Statutory — the rules the law writes", "Bảo hiểm & Thuế — những quy tắc do luật viết"),
    goal: B("Read the policy and the tax table the way an inspector would, and know exactly how to apply a rate change without touching a month that is already open.",
            "Đọc chính sách bảo hiểm và biểu thuế theo cách một đoàn kiểm tra sẽ đọc, và biết chính xác cách áp dụng một thay đổi tỷ lệ mà không đụng tới kỳ đang mở."),
    steps: [
      {
        screen: "statutory", anchor: "st-kpis",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("You do not invent these numbers", "Bạn không tự nghĩ ra những con số này"),
        body: B("This screen holds what the law has already decided: the <b>BHXH</b>, <b>BHYT</b> and <b>BHTN</b> rates, the base they are charged on, and the <b>thuế TNCN</b> table. Your job is not to choose them — it is to keep them current, and to be able to show where each one came from.",
                "Màn hình này lưu những gì pháp luật đã quyết: tỷ lệ <b>BHXH</b>, <b>BHYT</b>, <b>BHTN</b>, mức lương làm căn cứ đóng, và biểu <b>thuế TNCN</b>. Việc của bạn không phải chọn chúng — mà là giữ chúng luôn đúng hiện hành, và chỉ ra được từng con số đến từ đâu."),
      },
      {
        screen: "statutory", anchor: "st-rates",
        kicker: B("Reading the policy", "Đọc chính sách"),
        title: B("Who pays what — and the bigger half is not yours", "Ai đóng bao nhiêu — và phần lớn hơn không phải của bạn"),
        body: B("Each scheme has an <b>employee share</b>, deducted from the payslip, and an <b>employer share</b>, which is a company cost and never appears in anybody's net. BHXH 8% / 17.5% · BHYT 1.5% / 3% · BHTN 1% / 1%. The employee pays 10.5% in total and the company pays 21.5% — twice as much, on top.",
                "Mỗi loại bảo hiểm có <b>phần người lao động</b>, khấu trừ trên phiếu lương, và <b>phần doanh nghiệp</b>, là chi phí công ty và không bao giờ xuất hiện trong thực nhận của ai. BHXH 8% / 17,5% · BHYT 1,5% / 3% · BHTN 1% / 1%. Người lao động đóng tổng 10,5% còn doanh nghiệp đóng 21,5% — gấp đôi, và là khoản cộng thêm."),
        tip: B("When an employee says \"I pay a third of my salary in insurance\", this table is the answer: they pay 10.5% of the registered base, and the company pays the rest.",
               "Khi một nhân viên nói \"tôi đóng cả một phần ba lương cho bảo hiểm\", bảng này chính là câu trả lời: họ đóng 10,5% trên mức lương đã đăng ký, phần còn lại do công ty đóng."),
      },
      {
        screen: "statutory", anchor: "st-rates",
        kicker: B("The base & the ceiling", "Mức đóng & trần"),
        title: B("Charged on the registered base, up to a ceiling", "Tính trên mức đã đăng ký, tới một mức trần"),
        body: B("Contributions apply to the <b>registered insurance base</b> — for Mai, her contract base of 12,000,000 ₫, not her 14,280,000 ₫ gross. And they stop at the ceiling in the last column: above <b>20,000,000 ₫</b> the deduction does not grow, so two people on very different salaries can pay exactly the same BHXH.",
                "Bảo hiểm tính trên <b>mức lương đóng bảo hiểm đã đăng ký</b> — với Mai là lương cơ bản theo hợp đồng 12.000.000 ₫, không phải tổng thu nhập 14.280.000 ₫. Và nó dừng ở mức trần tại cột cuối: trên <b>20.000.000 ₫</b> thì khoản khấu trừ không tăng nữa, nên hai người lương rất khác nhau vẫn có thể đóng BHXH bằng nhau."),
      },
      {
        screen: "statutory", anchor: "st-slabs",
        kicker: B("The tax table", "Biểu thuế"),
        title: B("PIT is progressive, and kind at the bottom", "Thuế TNCN luỹ tiến, và nhẹ ở bậc thấp"),
        body: B("Taxable income is gross <b>less insurance</b>, less <b>11,000,000 ₫</b> for yourself and <b>4,400,000 ₫</b> per dependant. Mai: 14,280,000 − 1,260,000 − 11,000,000 = <b>2,020,000 ₫</b>, which sits entirely in the 5% band, so her tax is <b>101,000 ₫</b>. The bands only bite further up.",
                "Thu nhập chịu thuế là tổng thu nhập <b>trừ bảo hiểm</b>, trừ <b>11.000.000 ₫</b> giảm trừ bản thân và <b>4.400.000 ₫</b> mỗi người phụ thuộc. Với Mai: 14.280.000 − 1.260.000 − 11.000.000 = <b>2.020.000 ₫</b>, nằm trọn trong bậc 5%, nên thuế là <b>101.000 ₫</b>. Các bậc cao chỉ ảnh hưởng khi thu nhập lớn hơn nhiều."),
        tip: B("Insurance comes off BEFORE the deductions, which is why a rise in a contribution rate always costs a little less net than it costs in contribution.",
               "Bảo hiểm được trừ TRƯỚC các khoản giảm trừ, nên khi một tỷ lệ đóng tăng, phần thực nhận mất đi luôn nhỏ hơn phần đóng thêm một chút."),
      },
      {
        screen: "statutory", anchor: "st-rates",
        kicker: B("The connection", "Sợi dây liên kết"),
        title: B("Check the declared rate against the charged one", "Đối chiếu tỷ lệ khai báo với tỷ lệ đã tính"),
        body: B("The <b>1.5%</b> on the BHYT row is what the company <b>declares</b>. The <b>−180,000 ₫</b> on Mai's July slip is what her division's configuration actually <b>charged</b> — 1.5% of her registered base of 12,000,000 ₫. Today they agree, and this line is how you check that. They are two records, though: editing the rate here would not move that đồng by itself.",
                "Con số <b>1,5%</b> ở dòng BHYT là mức doanh nghiệp <b>khai báo</b>. Khoản <b>−180.000 ₫</b> trên phiếu tháng 7 của Mai là mức mà cấu hình của bộ phận cô ấy <b>đã tính</b> — 1,5% trên mức đóng đã đăng ký 12.000.000 ₫. Hôm nay hai bên khớp nhau, và đường nối này chính là cách bạn kiểm tra điều đó. Nhưng đây là hai bản ghi khác nhau: chỉ sửa tỷ lệ ở đây thì đồng bạc kia không nhúc nhích."),
        tip: B("The number that priced that line is a parameter on Retail's configuration — <b>EEHI</b>, at the bottom of the component list in Formula Engine. That is where a rate actually moves a payslip.",
               "Con số đã tính ra dòng đó là một tham số trong cấu hình của Bán lẻ — <b>EEHI</b>, nằm cuối danh sách thành phần trong Công thức lương. Đó mới là nơi một tỷ lệ thật sự làm thay đổi phiếu lương."),
        moment: { kind: "trace", from: "st-rates", to: "rep-slipline" },
      },
      {
        screen: "statutory", anchor: "st-roster",
        kicker: B("The mechanics", "Cơ chế thật"),
        title: B("A rate change is a new record, not an edit", "Đổi tỷ lệ là tạo bản ghi mới, không phải sửa"),
        body: B("There is <b>no version history</b> on a policy. When a decree changes a rate you create a <b>new policy record</b> with its own code — codes are unique per company — and its own <b>effective date</b>. The old record stays as the evidence of what was declared before it; archiving it takes it off this list, which is why the roster shows the live declarations rather than the whole history.",
                "Chính sách <b>không có lịch sử phiên bản</b>. Khi một nghị định thay đổi tỷ lệ, bạn tạo một <b>bản ghi chính sách mới</b> với mã riêng — mã là duy nhất trong mỗi công ty — và <b>ngày hiệu lực</b> riêng. Bản cũ ở lại như bằng chứng cho những gì đã khai báo trước đó; lưu trữ nó sẽ đưa nó ra khỏi danh sách này, nên danh sách ở đây hiển thị các bản khai báo còn hiệu lực chứ không phải toàn bộ lịch sử."),
        tip: B("The rates table above shows the ACTIVE policy with the latest effective date. It does not compare that date to today and it does not read the end date — so a policy dated from next month is displayed the moment it is saved.",
               "Bảng tỷ lệ ở trên hiển thị chính sách đang BẬT có ngày hiệu lực mới nhất. Nó không so ngày đó với hôm nay và cũng không đọc ngày kết thúc — nên một chính sách ghi hiệu lực từ tháng sau sẽ hiển thị ngay khi vừa lưu."),
      },
      {
        screen: "statutory", anchor: "st-new",
        kicker: B("Before you act", "Trước khi thao tác"),
        title: B("Declaring a rate is half the job", "Khai báo một tỷ lệ mới chỉ là một nửa công việc"),
        body: B("Saving a new policy changes what this screen, the contribution analytics and the statutory reports say. It changes <b>no payslip</b>. The rate that prices pay is a parameter on each division's formula configuration, so a rate change is two pieces of work: declare it here, and change it there. Until both are done the two disagree — and it is this screen, not the payslip, that is telling the truth about the company's intention.",
                "Lưu một chính sách mới sẽ thay đổi những gì màn hình này, phần phân tích chi phí bảo hiểm và các báo cáo bắt buộc nói ra. Nó không làm thay đổi <b>một phiếu lương nào</b>. Tỷ lệ tính ra tiền là một tham số trong cấu hình công thức của từng bộ phận, nên đổi tỷ lệ là hai phần việc: khai báo ở đây, và sửa ở đó. Khi chưa làm đủ cả hai thì hai bên còn lệch — và chính màn hình này, chứ không phải phiếu lương, mới đang nói đúng ý định của doanh nghiệp."),
        consequence: B("Affects what is <b>declared and reported</b>, company-wide: this cockpit, the contribution analytics and the statutory reports. It does not reprice a single payslip on its own. Reversible: <b>yes</b> — archive the record and the previous declaration is displayed again, because nothing downstream has been recomputed from it. Verify first: that you know which configurations have to change too, and who is going to change them.",
                       "Ảnh hưởng tới phần <b>khai báo và báo cáo</b> trên toàn công ty: màn hình này, phần phân tích chi phí bảo hiểm và các báo cáo bắt buộc. Tự nó không tính lại một phiếu lương nào. Hoàn tác: <b>được</b> — lưu trữ bản ghi là bản khai báo trước đó hiển thị trở lại, vì chưa có gì phía sau được tính lại từ nó. Kiểm tra trước: bạn đã biết những cấu hình nào cũng phải sửa, và ai sẽ sửa chúng."),
      },
      {
        screen: "statutory", anchor: "rep-slipline",
        kicker: B("Before & after", "Trước & sau"),
        title: B("What half a percentage point costs", "Nửa điểm phần trăm đáng giá bao nhiêu"),
        body: B("If BHYT's employee share went from 1.5% to 2.0%, Mai's deduction grows 60,000 ₫ — and her net falls <b>57,000 ₫</b>, not 60,000, because insurance comes off before tax and her thuế TNCN falls 3,000 with it. Toggle the two sides and read which lines move.",
                "Nếu phần người lao động của BHYT tăng từ 1,5% lên 2,0%, khoản khấu trừ của Mai tăng 60.000 ₫ — và thực nhận giảm <b>57.000 ₫</b>, không phải 60.000, vì bảo hiểm được trừ trước khi tính thuế nên thuế TNCN của cô ấy giảm theo 3.000. Hãy chuyển qua lại hai bên và xem những dòng nào thay đổi."),
        moment: { kind: "morph", which: "maiBhytRate" },
      },
    ],
    quiz: {
      question: B("A decree raises BHYT's employee share from 1 August. It is 20 July and the July run is still awaiting {{gmTierName}}. What do you do?",
                  "Một nghị định nâng phần đóng BHYT của người lao động từ 1/8. Hôm nay là 20/7 và đợt lương tháng 7 vẫn đang chờ {{gmTierName}}. Bạn làm gì?"),
      options: [
        {
          text: B("Edit the rate on the policy that is in force now", "Sửa tỷ lệ ngay trên chính sách đang có hiệu lực"),
          correct: false,
          explanation: B("Let's rethink that. There is no version history to fall back on — the old declared rate is simply gone, and with it the record of what the company was declaring while July was being paid. That record is exactly what an inspection asks to see.",
                         "Hãy nghĩ lại một chút. Không có lịch sử phiên bản nào để quay lại — mức đã khai báo trước đó đơn giản là mất, và mất theo cả bằng chứng về mức mà doanh nghiệp đang khai báo trong lúc trả lương tháng 7. Chính bản ghi đó là thứ đoàn kiểm tra yêu cầu được xem."),
        },
        {
          text: B("Create a new policy record dated 01/08, and plan the configuration change with it", "Tạo bản ghi chính sách mới ghi ngày 01/08, và lên kế hoạch sửa cấu hình cùng lúc"),
          correct: true,
          explanation: B("Yes. The date records what the decree says, the old record stays as evidence of what was declared before it, and — the half people forget — the rate that actually prices pay is a parameter on each division's configuration, so somebody has to change that too before August runs.",
                         "Đúng vậy. Ngày hiệu lực ghi đúng những gì nghị định nêu, bản ghi cũ ở lại làm bằng chứng cho mức đã khai báo trước đó, và — phần mà người ta hay quên — tỷ lệ thực sự tính ra tiền là một tham số trong cấu hình của từng bộ phận, nên phải có người sửa cả chỗ đó trước khi tháng 8 chạy lương."),
        },
        {
          text: B("Create the new policy now with today's date so nothing is forgotten", "Tạo chính sách mới ngay hôm nay với ngày hiệu lực là hôm nay cho khỏi quên"),
          correct: false,
          explanation: B("Let's rethink that. The instinct is right and the date is wrong: today means 20 July, and the decree does not say 20 July — so the declaration would record a legal start the company cannot evidence. Create the record now if you like; put 01/08 in the effective date, and tell whoever is reviewing July that the rates on this screen are next month's.",
                         "Hãy nghĩ lại một chút. Ý thức cẩn thận là đúng, chỉ có ngày là sai: hôm nay là 20/7, mà nghị định không nói 20/7 — nên bản khai báo sẽ ghi một mốc pháp lý mà doanh nghiệp không chứng minh được. Cứ tạo bản ghi ngay bây giờ cũng được; hãy điền 01/08 vào ngày hiệu lực, và báo cho người đang soát xét tháng 7 rằng tỷ lệ trên màn hình này là của tháng sau."),
        },
      ],
    },
  },
};

/* =============================================================================
   6. MISSIONS — the practice ladder
   -----------------------------------------------------------------------------
   Missions run on the REPLICA and nowhere else. A step that says "compute the
   run" would otherwise write 48 real payslips, and a practice surface whose
   actions have consequences the learner did not intend is not a practice
   surface. There is no server behind the replica, so that is structural rather
   than a rule anyone has to remember.

   THE RULES THE MODEL ENFORCES, so the content has to satisfy them:
     · a full mission carries all four consequence fields and one seeded anomaly
     · exactly ONE decision per step (two in one modal caused two off-by-one bugs
       in the v1 prototype)
     · a decision has at least two options and exactly one right answer
     · EVERY wrong option carries recovery text, in both languages. A wrong
       choice met with silence is a rejection, and this is the brief's hardest
       interaction rule to keep in a hurry
     · every full mission ends on an undo, because reversibility is learned by
       doing it once and not by being told

   `kind = live` exists in the model for the demo-tenant capstones. Nothing here
   uses it: Phase A ships the value, not the runtime, and the runner refuses to
   open one.
   ========================================================================== */
const MISSIONS = [
  {
    id: "m1", group: "payrun", icon: "zap", mins: 8, full: true,
    screen: "runpayroll",
    conf: { key: "run", gain: 25 },
    title: B("Run the July pay run", "Chạy đợt lương tháng 7"),
    desc: B("Compute Retail's July payroll, handle the anomaly the data is hiding, and send it into the approval chain.",
            "Tính lương tháng 7 cho Bán lẻ, xử lý điểm bất thường mà dữ liệu đang giấu, và đưa nó vào chuỗi phê duyệt."),
    consequence: {
      title: B("You are about to compute 48 payslips", "Bạn sắp tính 48 phiếu lương"),
      scope: B("July 2026 × Retail — Hà Nội only. 48 draft payslips are created; no other division and no other period is touched.",
               "Chỉ Tháng 7/2026 × Bán lẻ — Hà Nội. 48 phiếu lương nháp được tạo; không bộ phận nào khác và không kỳ nào khác bị ảnh hưởng."),
      reversible: B("Yes. Drafts can be recomputed or deleted, nothing is paid or sent, and no employee sees anything until the whole run reaches done.",
                    "Được. Bản nháp có thể tính lại hoặc xoá, chưa có gì được chi hay gửi đi, và không nhân viên nào thấy gì cho tới khi cả đợt đạt Hoàn tất."),
      verify: B("That the eligible count reads 48 and not something smaller, and that this month's attendance import has been committed. A short count means the data is not in yet.",
                "Rằng số nhân viên đủ điều kiện là 48 chứ không nhỏ hơn, và dữ liệu chấm công tháng này đã được ghi nhận. Con số thiếu nghĩa là dữ liệu chưa vào."),
    },
    anomaly: {
      title: B("The 4.6 that was typed as 46", "Con số 4,6 bị gõ thành 46"),
      body: B("Trần Văn Hùng's overtime came through at 4,200,000 ₫ against 1,100,000 ₫ in June — 382%. It reads like a genuine peak week, and that is exactly why it is worth stopping on: a decimal point dropped in a timesheet produces a number that is plausible, not absurd. The engine cannot tell a busy month from a typo. You can, by opening the timesheet — and the cost of not looking is one employee paid roughly three million đồng too much, in a run that forty-seven other people will assume was checked.",
             "Tăng ca của Trần Văn Hùng vào hệ thống ở mức 4.200.000 ₫ so với 1.100.000 ₫ của tháng 6 — bằng 382%. Nó trông như một tuần cao điểm thật, và chính vì thế mới đáng dừng lại: một dấu thập phân bị mất trong bảng chấm công tạo ra con số hợp lý chứ không hề vô lý. Hệ thống không phân biệt được tháng bận với lỗi gõ. Bạn thì phân biệt được, bằng cách mở bảng chấm công — và cái giá của việc không xem là một nhân viên được trả thừa khoảng ba triệu đồng, trong một đợt lương mà bốn mươi bảy người khác mặc định là đã được kiểm tra."),
    },
    debrief: {
      did: [
        B("Chose the division, and with it the formula configuration every payslip in the run was computed by.",
          "Chọn bộ phận, và cùng với nó là cấu hình công thức mà mọi phiếu lương trong đợt được tính theo."),
        B("Read the consequence card before computing, so you knew the scope and the way back before you acted.",
          "Đọc thẻ hậu quả trước khi tính, để biết phạm vi và lối quay lại trước khi thao tác."),
        B("Opened the flagged payslip instead of clearing it, and treated a 382% overtime figure as a question rather than a fact.",
          "Mở phiếu bị gắn cờ thay vì xoá cờ, và coi con số tăng ca 382% là một câu hỏi chứ không phải một dữ kiện."),
        B("Sent the run into the approval chain, where it now waits at a gate that belongs to somebody else.",
          "Đưa đợt lương vào chuỗi phê duyệt, nơi nó đang chờ ở một cổng thuộc về người khác."),
      ],
      checklist: [
        B("Headcount matches what you expected, and joiners and leavers are accounted for.",
          "Sĩ số khớp với kỳ vọng, và người vào mới cùng người thôi việc đã được tính đủ."),
        B("Every flagged payslip has been opened and understood, not dismissed.",
          "Mọi phiếu bị gắn cờ đã được mở và hiểu rõ, không phải bị bỏ qua."),
        B("Total net against last month — and you can explain the variance in one sentence.",
          "Tổng thực nhận so với tháng trước — và bạn giải thích được biến động trong một câu."),
        B("The statutory lines are present on a sample slip: BHXH, BHYT, BHTN, thuế TNCN.",
          "Các dòng bắt buộc có mặt trên một phiếu mẫu: BHXH, BHYT, BHTN, thuế TNCN."),
        B("Bank details are valid for anyone joining this month, or their pay will not land.",
          "Thông tin ngân hàng hợp lệ cho những người mới vào tháng này, nếu không lương sẽ không tới được tài khoản."),
      ],
    },
  },
  {
    id: "m2", group: "payrun", icon: "clipboard-check", mins: 7, full: true,
    screen: "payruns",
    conf: { key: "approve", gain: 20 },
    title: B("Review and approve like a manager", "Soát xét và phê duyệt như một quản lý"),
    desc: B("A run is waiting at {{hrTierName}}. Sample it properly, then approve it — or reject it with a reason somebody can act on.",
            "Một đợt lương đang chờ ở {{hrTierName}}. Hãy lấy mẫu soát xét cho đúng, rồi phê duyệt — hoặc từ chối kèm một lý do mà người khác xử lý được."),
    consequence: {
      title: B("Approving moves 48 payslips one gate closer to being paid", "Phê duyệt đưa 48 phiếu lương tiến gần thêm một cổng tới lúc được chi"),
      scope: B("The whole run, all 48 payslips together — there is no way to approve some of them. It moves from {{hrTierName}} to {{gmTierName}}.",
               "Cả đợt lương, toàn bộ 48 phiếu cùng lúc — không có cách nào duyệt một phần. Nó chuyển từ {{hrTierName}} sang {{gmTierName}}."),
      reversible: B("Yes, at this gate: the next reviewer can still reject it back to draft. That stops being true at done, after which a correction is a retro line and never an edit.",
                    "Ở cổng này thì được: người soát xét kế tiếp vẫn có thể từ chối và trả về Nháp. Điều đó không còn đúng khi đã Hoàn tất, sau đó mọi hiệu chỉnh là một dòng hồi tố chứ không bao giờ là sửa trực tiếp."),
      verify: B("That you have opened every flagged payslip, sampled a few unflagged ones, and can say in one sentence why the total differs from last month.",
                "Rằng bạn đã mở mọi phiếu bị gắn cờ, lấy mẫu vài phiếu không gắn cờ, và nói được trong một câu vì sao tổng khác tháng trước."),
    },
    anomaly: {
      title: B("The variance nobody questioned", "Biến động không ai chất vấn"),
      body: B("The run's net total is 612,480,000 ₫ against 596,110,000 ₫ in June — a rise of about 2.7%, on one more employee. That is a comfortable-looking number, and comfortable-looking numbers are where a single wrong payslip hides best: Hùng's overtime alone accounts for roughly three million of the difference, which is well inside the range a reviewer would wave through as 'a slightly busier month'. A total that looks reasonable is not evidence that every slip inside it is. The flags are.",
             "Tổng thực nhận của đợt là 612.480.000 ₫ so với 596.110.000 ₫ tháng 6 — tăng khoảng 2,7%, với thêm một nhân viên. Đó là con số trông rất dễ chịu, và những con số dễ chịu chính là nơi một phiếu lương sai ẩn mình tốt nhất: riêng tăng ca của Hùng đã chiếm khoảng ba triệu trong phần chênh đó, hoàn toàn nằm trong khoảng mà một người soát xét sẽ cho qua như 'một tháng bận hơn chút'. Tổng trông hợp lý không phải bằng chứng rằng từng phiếu bên trong đều hợp lý. Các cờ cảnh báo mới là bằng chứng."),
    },
    debrief: {
      did: [
        B("Found the run by the gate it was waiting at, rather than by the month it belonged to.",
          "Tìm đợt lương theo cổng mà nó đang chờ, thay vì theo tháng mà nó thuộc về."),
        B("Sampled the payslips the engine flagged first, and a few it did not.",
          "Soát trước những phiếu hệ thống gắn cờ, rồi lấy mẫu thêm vài phiếu không bị gắn cờ."),
        B("Read the consequence card and knew, before deciding, that this gate is still reversible and done is not.",
          "Đọc thẻ hậu quả và biết trước khi quyết định rằng cổng này vẫn hoàn tác được còn Hoàn tất thì không."),
        B("Made the call — and, if you rejected, wrote a reason the officer can actually act on.",
          "Ra quyết định — và nếu bạn từ chối, đã viết một lý do mà chuyên viên thực sự xử lý được."),
        B("Watched a rejection go back to draft and forward again, so reversibility is something you have done rather than been told.",
          "Xem một lần từ chối đưa đợt về Nháp rồi đi tiếp, để khả năng hoàn tác là điều bạn đã tự làm chứ không phải chỉ nghe kể."),
      ],
      checklist: [
        B("Every flagged payslip opened, and the flag understood rather than cleared.",
          "Mọi phiếu bị gắn cờ đã được mở, và cờ được hiểu rõ chứ không chỉ bị xoá."),
        B("A sample of unflagged slips read — the engine flags the unusual, not the wrong.",
          "Đã đọc một mẫu các phiếu không bị gắn cờ — hệ thống gắn cờ cái bất thường, không phải cái sai."),
        B("The variance against last month explained in one sentence, not just observed.",
          "Biến động so với tháng trước được giải thích trong một câu, không chỉ được ghi nhận."),
        B("If rejecting: a written reason that names what to change, not just what is wrong.",
          "Nếu từ chối: một lý do bằng văn bản nêu rõ cần sửa gì, không chỉ nêu cái gì sai."),
        B("If approving: that you are content for this to be paid, because the gate after yours is checking totals, not lines.",
          "Nếu phê duyệt: rằng bạn thực sự yên tâm để khoản này được chi, vì cổng sau bạn kiểm tra các tổng chứ không kiểm tra từng dòng."),
      ],
    },
  },
  {
    id: "m3", group: "payrun", icon: "flask", mins: 6, full: false,
    screen: "importwizard",
    conf: { key: "import", gain: 15 },
    title: B("Fix a bad import before it becomes salaries", "Sửa một đợt nhập lỗi trước khi nó thành lương"),
    desc: B("A file with duplicate rows and one employee nobody can match. The score drops. Do you fix it, or commit anyway?",
            "Một tệp có dòng bị lặp và một nhân viên không ai khớp được. Điểm tin cậy tụt xuống. Bạn sửa, hay cứ ghi nhận?"),
    outlineNote: B("The full version puts you in the wizard with the score falling in front of you, makes you choose between Match, Retry and Skip for each bad row, and then shows what each of those choices would have produced on {{payDay}} — including the one where a skipped row turns out to have been a person.",
                   "Bản đầy đủ đặt bạn vào trình hướng dẫn với điểm tin cậy đang tụt ngay trước mắt, buộc bạn chọn giữa Khớp, Thử lại và Bỏ qua cho từng dòng lỗi, rồi cho thấy mỗi lựa chọn đó sẽ tạo ra gì vào {{payDay}} — kể cả trường hợp dòng bị bỏ qua hoá ra là một con người."),
  },
  {
    id: "m4", group: "setup", icon: "shield-check", mins: 7, full: true,
    screen: "statutory",
    conf: { key: "setup", gain: 30 },
    title: B("Apply a BHYT rate change — properly", "Áp dụng thay đổi tỷ lệ BHYT — cho đúng cách"),
    desc: B("A decree raises the health-insurance rate. Declare it the way the product actually supports, date it so the record says what the decree says — and find out why declaring it is only half the job.",
            "Một nghị định nâng tỷ lệ bảo hiểm y tế. Hãy khai báo theo đúng cách sản phẩm hỗ trợ, đặt ngày sao cho bản ghi nói đúng những gì nghị định nói — và hiểu vì sao khai báo mới chỉ là một nửa công việc."),
    consequence: {
      title: B("You are about to change what the company declares", "Bạn sắp thay đổi điều doanh nghiệp khai báo"),
      scope: B("What this cockpit shows, and what the contribution analytics and the statutory reports read — company-wide. It reprices <b>nothing</b>: the rate that prices a payslip is a parameter on each division's formula configuration, and this record is not it.",
               "Những gì màn hình này hiển thị, và những gì phần phân tích chi phí bảo hiểm cùng các báo cáo bắt buộc đọc vào — trên toàn công ty. Nó <b>không</b> tính lại bất cứ khoản nào: tỷ lệ tính ra tiền trên phiếu lương là một tham số trong cấu hình công thức của từng bộ phận, và bản ghi này không phải thứ đó."),
      reversible: B("Yes. Archive the record and the previous declaration is displayed again — nothing downstream has been recomputed from it, because nothing downstream reads it to compute with.",
                    "Được. Lưu trữ bản ghi là bản khai báo trước đó hiển thị trở lại — chưa có gì phía sau được tính lại từ nó, vì không có gì phía sau đọc nó để tính."),
      verify: B("That the date is the one the decree gives, and that you know which formula configurations have to change with it. Declaring a rate nobody has configured leaves the two disagreeing, and the payslips are the ones that will look wrong.",
                "Rằng ngày hiệu lực đúng là ngày nghị định nêu, và bạn đã biết những cấu hình công thức nào phải sửa theo. Khai báo một tỷ lệ mà chưa ai cấu hình sẽ khiến hai bên lệch nhau, và phiếu lương mới là thứ trông có vẻ sai."),
    },
    anomaly: {
      title: B("The declaration that changed nothing", "Bản khai báo không làm thay đổi điều gì"),
      body: B("The natural next sentence after saving this record is \"so August's payslips will charge 2%\". They will not. Nothing downstream reads this record to compute with — the rate that prices the BHYT line is a parameter on each division's formula configuration, and it is still at 1.5%. The mission ends with the declaration correct and the payroll unchanged, and that gap is the point: it is not a bug, it is the reason pay never moves because a reference table moved. Somebody now has to change twelve configurations, preview them, and simulate them — and the person who assumed otherwise finds out on {{payDay}}.",
             "Câu nói tự nhiên ngay sau khi lưu bản ghi này là \"vậy phiếu lương tháng 8 sẽ tính 2%\". Không phải vậy. Không có gì phía sau đọc bản ghi này để tính — tỷ lệ tính ra dòng BHYT là một tham số trong cấu hình công thức của từng bộ phận, và nó vẫn đang là 1,5%. Nhiệm vụ kết thúc với bản khai báo đã đúng còn bảng lương thì chưa đổi, và chính khoảng cách đó mới là điều cần nhớ: đây không phải lỗi, mà là lý do khiến tiền lương không bao giờ thay đổi chỉ vì một bảng tham chiếu thay đổi. Giờ phải có người sửa mười hai cấu hình, xem trước và mô phỏng chúng — còn ai đã đinh ninh điều ngược lại thì sẽ biết vào {{payDay}}."),
    },
    debrief: {
      did: [
        B("Created a new policy record with its own code instead of editing the rates that were in force — the only shape the product actually supports.",
          "Tạo một bản ghi chính sách mới với mã riêng thay vì sửa các tỷ lệ đang có hiệu lực — đây là cách duy nhất mà sản phẩm thực sự hỗ trợ."),
        B("Changed the one rate the decree changed, and left the employer share and the other two schemes alone.",
          "Chỉ đổi đúng tỷ lệ mà nghị định thay đổi, và để nguyên phần doanh nghiệp cùng hai loại bảo hiểm còn lại."),
        B("Dated it from the day the decree applies, so the record evidences a legal start rather than the day somebody happened to type it.",
          "Đặt ngày hiệu lực đúng ngày nghị định áp dụng, để bản ghi chứng minh một mốc pháp lý chứ không phải ngày ai đó tình cờ gõ vào."),
        B("Found out that the declaration alone changes no payslip, and that the rate which does live in each division's configuration.",
          "Phát hiện ra rằng chỉ khai báo thôi thì không phiếu lương nào đổi, và tỷ lệ thực sự tính ra tiền nằm trong cấu hình của từng bộ phận."),
      ],
      checklist: [
        B("The decree or circular is in front of you, and the rate you typed is the one it names.",
          "Văn bản pháp luật đang mở trước mặt, và tỷ lệ bạn gõ đúng bằng tỷ lệ trong văn bản đó."),
        B("Only the changed rate has moved — an employer share edited by accident is invisible on every payslip.",
          "Chỉ tỷ lệ thay đổi mới bị sửa — một phần doanh nghiệp bị sửa nhầm sẽ không hiện ra trên bất kỳ phiếu lương nào."),
        B("The effective date is the one the decree gives, and you can point at the decree.",
          "Ngày hiệu lực đúng là ngày nghị định nêu, và bạn chỉ ra được văn bản đó."),
        B("Everyone reading this screen has been told the rates now shown are next month's — reviewers of an open run included.",
          "Mọi người đọc màn hình này đã được báo rằng tỷ lệ đang hiển thị là của tháng sau — kể cả những người đang soát xét một đợt còn mở."),
        B("The formula configurations that price the affected lines are on somebody's list, with a date, or the declaration and the payroll stay out of step.",
          "Các cấu hình công thức tính những dòng bị ảnh hưởng đã nằm trong danh sách việc của ai đó, kèm thời hạn, nếu không thì bản khai báo và bảng lương sẽ còn lệch nhau."),
      ],
    },
  },
  {
    id: "m5", group: "setup", icon: "calculator", mins: 6, full: false,
    screen: "formula",
    conf: { key: "formula", gain: 20 },
    title: B("Map a new allowance into a config", "Đưa một khoản phụ cấp mới vào cấu hình"),
    desc: B("A meal allowance has been agreed for Retail. Add it as a component, wire it into gross, and prove it before anybody is paid by it.",
            "Bán lẻ vừa thống nhất một khoản phụ cấp ăn ca. Hãy thêm nó thành một thành phần, nối vào tổng thu nhập, và chứng minh nó trước khi có ai được trả theo nó."),
    outlineNote: B("The full version adds the component to HOASEN_RETAIL_END, makes you choose where it belongs — an earning that feeds GROSS, not a total and not an input — then wire it into the gross formula and read the dependency panel to see what moved. It ends where every configuration change should: a simulation against last month's real payslips, and the decision of whether to activate while a run is still open.",
                   "Bản đầy đủ thêm thành phần vào HOASEN_RETAIL_END, buộc bạn chọn nó thuộc về đâu — một khoản thu nhập cấu thành Tổng thu nhập, không phải một tổng và cũng không phải đầu vào — rồi nối vào công thức tổng thu nhập và đọc bảng phụ thuộc để thấy những gì đã đổi. Nó kết thúc đúng ở nơi mọi thay đổi cấu hình nên kết thúc: một lần mô phỏng trên phiếu lương thật của tháng trước, và quyết định có kích hoạt hay không khi một đợt lương vẫn đang mở."),
  },

  /* ===========================================================================
     THE LIVE CAPSTONE.

     `kind: live` and everything that follows from it. This mission runs on the
     REAL Payobook, in the shared demo world, against the division this account
     was assigned at signup — so no two prospects fight over the same June run.

     WHAT IT DELIBERATELY DOES NOT DO
     --------------------------------
     It never asserts an amount. Every figure in a live run is on the screen in
     front of the learner and is theirs, not ours; a mission that printed
     "you should see 612,480,000" would be wrong the first time the demo world
     was regenerated, and confidently wrong is the failure this whole system is
     built to avoid. The fixture missions are where the worked example lives.

     It never intercepts either. The consequence card is a TEACHING step shown
     BEFORE the compute instruction — the learner then presses Payobook's own
     button, and the runner finds out what happened by asking the server what
     the records now say. Enforcement stays with the product's own gates,
     where it belongs.
     ======================================================================== */
  {
    id: "mL1", group: "payrun", icon: "zap", mins: 12, kind: "live",
    screen: "runpayroll",
    conf: { key: "run_live", gain: 40 },
    title: B("Run your division's June payroll — for real", "Chạy lương tháng 6 của bộ phận bạn — trên dữ liệu thật"),
    desc: B("The same judgement as the practice run, on real records in the demo world: your own division, the open June period, and the approval chain all the way to done.",
            "Vẫn là phán đoán như bài thực hành, nhưng trên bản ghi thật trong môi trường demo: đúng bộ phận của bạn, kỳ tháng 6 đang mở, và chuỗi phê duyệt đi trọn tới Hoàn tất."),
    consequence: {
      title: B("This one is real", "Nhiệm vụ này là thật"),
      scope: B("Your assigned division's June 2026 run, in the shared Payobook demo company. Real payslip records are created, and other people exploring the demo can see them. No other division and no other period is touched — and no real company's data is anywhere near this.",
               "Đợt lương tháng 6/2026 của bộ phận bạn được gán, trong công ty demo dùng chung của Payobook. Các bản ghi phiếu lương thật sẽ được tạo, và những người khác đang xem demo cũng nhìn thấy chúng. Không bộ phận nào khác và không kỳ nào khác bị ảnh hưởng — và không dữ liệu của công ty thật nào ở gần chỗ này."),
      reversible: B("Partly, and the halves matter. Draft payslips can be deleted and recomputed as often as you like. Submitting is not silently undoable: from there the run moves only by being approved, or by being rejected back to draft with a written reason — the same chain a real payroll travels.",
                    "Một phần, và ranh giới rất quan trọng. Phiếu lương nháp có thể xoá và tính lại bao nhiêu lần tuỳ ý. Trình phê duyệt thì không thể âm thầm hoàn tác: từ đó đợt lương chỉ đi tiếp bằng cách được duyệt, hoặc bị từ chối trả về Nháp kèm lý do bằng văn bản — đúng chuỗi mà một kỳ lương thật đi qua."),
      verify: B("That the division the wizard has selected is the one assigned to you. It is preselected and moved to the front of the list for exactly this reason, and the mission verifies against your assignment rather than against whatever the wizard happens to be showing.",
                "Rằng bộ phận mà trình hướng dẫn đang chọn đúng là bộ phận được gán cho bạn. Nó được chọn sẵn và đưa lên đầu danh sách chính vì lý do này, và nhiệm vụ xác minh theo phần được gán cho bạn chứ không theo thứ mà trình hướng dẫn đang hiển thị."),
    },
    debrief: {
      did: [
        B("Computed a real month of payroll for a real division, having read what the action would do before you did it.",
          "Tính một tháng lương thật cho một bộ phận thật, sau khi đã đọc xem thao tác đó sẽ gây ra điều gì."),
        B("Opened the run and read what the engine flagged, instead of taking a clean-looking total as evidence.",
          "Mở đợt lương và đọc những gì hệ thống gắn cờ, thay vì coi một con số tổng trông sạch sẽ là bằng chứng."),
        B("Submitted it, and watched it stop being yours: from that point the run moves only through the chain.",
          "Trình đợt lương lên, và thấy nó không còn là của riêng bạn: từ lúc đó đợt chỉ đi tiếp qua chuỗi phê duyệt."),
        B("Followed it through the gates to done — the same journey, and the same waiting, that payroll week is actually made of.",
          "Theo nó đi qua các cổng tới Hoàn tất — đúng hành trình đó, và đúng những khoảng chờ đó, chính là thứ làm nên một tuần tính lương."),
        B("Did it once where a mistake costs a demo record, which is the last place it is cheap.",
          "Làm một lần ở nơi mà sai sót chỉ tốn một bản ghi demo, và đó là nơi cuối cùng nó còn rẻ."),
      ],
      checklist: [
        B("The division is yours and the period is the one you meant — read both before computing, not after.",
          "Bộ phận đúng là của bạn và kỳ lương đúng là kỳ bạn định chạy — hãy đọc cả hai trước khi tính, đừng đọc sau."),
        B("Every flagged payslip opened and understood. A flag is a question about one employee, and submitting is you answering it.",
          "Mọi phiếu bị gắn cờ đã được mở và hiểu rõ. Cờ là một câu hỏi về một nhân viên cụ thể, và trình duyệt chính là bạn trả lời câu hỏi đó."),
        B("You can say in one sentence why the total is what it is, before anybody at a later gate asks you.",
          "Bạn nói được trong một câu vì sao tổng lại là con số đó, trước khi có ai ở cổng phía sau hỏi bạn."),
        B("You know which gate the run is at and who holds it — the column names them.",
          "Bạn biết đợt lương đang ở cổng nào và ai đang giữ cổng đó — cột đã chỉ đích danh."),
        B("Nothing was submitted to make a deadline. A gate skipped for a deadline is a signature nobody gave.",
          "Không có gì được trình chỉ để kịp hạn. Một cổng bị bỏ qua vì hạn chót là một chữ ký chưa ai đặt bút."),
      ],
    },
  },
];

/* Mission 1 — the step machine. `nav` moves the replica; a step without one
   holds the screen it is already on, which is right for a decision: it asks a
   question about where the learner already is. */
const MISSION_STEPS = {
  m1: [
    {
      id: "open", nav: "runpayroll", target: "pw-rail",
      instruction: B("Open Run Payroll", "Mở Chạy bảng lương"),
      detail: B("It is the first leaf in the Pay Run section of the sidebar.",
                "Đó là mục đầu tiên trong phần Chạy lương ở thanh bên."),
      hint: B("The stepper at the top tells you where you are: you want step 1, Scope.",
              "Thanh bước ở trên cùng cho biết bạn đang ở đâu: bạn cần bước 1, Phạm vi."),
    },
    {
      id: "division", target: "pw-division", decision: true,
      instruction: B("Which division do you run?", "Bạn chạy bộ phận nào?"),
      detail: B("July's attendance has been imported and committed for Retail. The other two divisions are still waiting on their files.",
                "Dữ liệu chấm công tháng 7 đã được nhập và ghi nhận cho Bán lẻ. Hai bộ phận còn lại vẫn đang chờ tệp của họ."),
      hint: B("The scope panel on the right updates with your choice — read the eligible count it shows.",
              "Bảng phạm vi bên phải cập nhật theo lựa chọn của bạn — hãy đọc số nhân viên đủ điều kiện mà nó hiện ra."),
      options: [
        { id: "retail", correct: true, label: B("Retail — Hà Nội", "Bán lẻ — Hà Nội") },
        { id: "fnb", label: B("F&B", "F&B") },
        { id: "it", label: B("IT Services", "Dịch vụ CNTT") },
      ],
      recovery: {
        fnb: B("Let's rethink that. F&B's July attendance has not been committed yet, so the eligible count would come back far short of its headcount — and computing on it would create a run that looks finished and is missing most of its people.",
               "Hãy nghĩ lại một chút. Chấm công tháng 7 của F&B chưa được ghi nhận, nên số nhân viên đủ điều kiện sẽ thiếu rất nhiều so với sĩ số — và tính trên đó sẽ tạo ra một đợt lương trông như đã xong nhưng thiếu phần lớn nhân sự."),
        it: B("Let's rethink that. IT Services is in the same position — its file has not arrived. The division whose data is ready is the one the brief named, and the scope panel would have told you the moment you selected it.",
              "Hãy nghĩ lại một chút. Dịch vụ CNTT cũng vậy — tệp của họ chưa về. Bộ phận có dữ liệu sẵn sàng chính là bộ phận đề bài nêu tên, và bảng phạm vi sẽ cho bạn biết ngay khi bạn chọn."),
      },
    },
    {
      id: "consequence", target: "pw-compute", consequence: true,
      instruction: B("Read what Compute is about to do", "Đọc xem nút Tính sắp làm gì"),
      detail: B("This card is the interception. It is not a confirmation dialog — it names the scope, the way back and the thing to verify, and the mission will not move until you have seen all three.",
                "Thẻ này là điểm chặn. Nó không phải hộp thoại xác nhận — nó nêu rõ phạm vi, lối quay lại và thứ cần kiểm tra, và nhiệm vụ sẽ không đi tiếp cho tới khi bạn đã xem cả ba."),
    },
    {
      id: "compute", target: "pw-pills",
      instruction: B("Compute, then read the three pills", "Tính, rồi đọc ba ô số"),
      detail: B("48 payslips, 48 computed, 1 needing review. The third number is the only one that needs you.",
                "48 phiếu lương, 48 phiếu đã tính, 1 phiếu cần soát xét. Con số thứ ba mới là con số cần tới bạn."),
      hint: B("Need review is not an error count — it is the engine asking a question about a specific employee.",
              "Cần soát xét không phải số lỗi — đó là hệ thống đang hỏi một câu về một nhân viên cụ thể."),
    },
    {
      id: "inspect", target: "pw-exceptions",
      instruction: B("Open the flagged payslip", "Mở phiếu bị gắn cờ"),
      detail: B("Trần Văn Hùng. Overtime 4,200,000 ₫ this month against 1,100,000 ₫ in June.",
                "Trần Văn Hùng. Tăng ca 4.200.000 ₫ tháng này so với 1.100.000 ₫ tháng 6."),
      hint: B("In real payroll you would open the timesheet before deciding. 382% is not impossible — it is unverified.",
              "Trong thực tế bạn sẽ mở bảng chấm công trước khi quyết định. 382% không phải là không thể — nó chỉ là chưa được xác minh."),
    },
    {
      id: "decide", target: "pw-exceptions", decision: true,
      instruction: B("Overtime at 382% of last month. What do you do?", "Tăng ca bằng 382% tháng trước. Bạn xử lý thế nào?"),
      detail: B("You cannot see the timesheet from here, and the run is due. The question is what you do with an unverified number, not whether you can prove it wrong.",
                "Bạn không xem được bảng chấm công từ đây, và đợt lương thì đến hạn. Câu hỏi là bạn làm gì với một con số chưa được xác minh, không phải bạn có chứng minh được nó sai hay không."),
      options: [
        { id: "flag", correct: true, label: B("Flag it for review and check the timesheet before this run is approved", "Đánh dấu cần soát xét và kiểm tra bảng chấm công trước khi đợt này được duyệt") },
        { id: "accept", label: B("Accept it as correct — it was a busy month", "Chấp nhận là đúng — tháng đó bận") },
        { id: "zero", label: B("Set the overtime to zero so the run is clean", "Đặt tăng ca về 0 cho đợt lương sạch sẽ") },
      ],
      recovery: {
        accept: B("Let's rethink that. 4.6 hours typed as 46 is one of the most common timesheet errors there is, and it produces a number that looks like a busy month rather than a mistake. Accepting an unverified spike is not a decision — it is a decision deferred to whoever notices on {{payDay}}.",
                  "Hãy nghĩ lại một chút. 4,6 giờ bị gõ thành 46 là một trong những lỗi chấm công phổ biến nhất, và nó tạo ra con số trông giống tháng bận chứ không giống lỗi. Chấp nhận một mức tăng chưa xác minh không phải là ra quyết định — đó là đẩy quyết định cho người nào phát hiện ra vào {{payDay}}."),
        zero: B("Let's rethink that. That fixes the output and leaves the input untouched, so the next recompute brings it straight back — and if the overtime was real, you have just underpaid someone who worked for it. Fix inputs, never outputs.",
                "Hãy nghĩ lại một chút. Cách đó sửa kết quả và để nguyên đầu vào, nên lần tính lại kế tiếp sẽ mang nó quay lại ngay — và nếu tăng ca là thật, bạn vừa trả thiếu cho người đã làm. Hãy sửa đầu vào, đừng bao giờ sửa kết quả."),
      },
    },
    {
      id: "submit", target: "pw-result",
      instruction: B("Submit the run for approval", "Trình đợt lương lên phê duyệt"),
      detail: B("It leaves draft and enters the chain: Payroll Officer, {{hrTierName}}, {{gmTierName}}, done.",
                "Nó rời trạng thái Nháp và vào chuỗi: Chuyên viên tính lương, {{hrTierName}}, {{gmTierName}}, Hoàn tất."),
    },
    {
      id: "undo", nav: "payruns", target: "pk-card-actions", undo: true,
      instruction: B("Now undo it: send the run back to draft", "Giờ hãy hoàn tác: trả đợt lương về Nháp"),
      detail: B("Everything you just did is reversible until the run reaches done. Do it once here, so that when you need it on a real run you already know it is available and what it costs — the whole batch goes back together, and the reason is recorded.",
                "Mọi việc bạn vừa làm đều hoàn tác được cho tới khi đợt lương đạt Hoàn tất. Hãy làm một lần ở đây, để khi cần trên một đợt thật bạn đã biết là có cách và biết cái giá của nó — cả lô cùng quay về, và lý do được ghi lại."),
      hint: B("The card's action footer offers Reject while the run is in the chain. That is the same control a reviewer uses.",
              "Phần chân thẻ hiện nút Từ chối khi đợt lương còn trong chuỗi. Đó chính là nút mà người soát xét dùng."),
    },
  ],

  m2: [
    {
      id: "open", nav: "payruns", target: "pk-kpis",
      instruction: B("Find what is waiting for you", "Tìm phần việc đang chờ bạn"),
      detail: B("Time has moved on since m1: the Payroll Officer has approved the July run at their tier, so it now sits at {{hrTierName}} — yours. Awaiting your approval is the only number on this band that is about you.",
                "Thời gian đã trôi qua kể từ m1: Chuyên viên tính lương đã duyệt đợt tháng 7 ở vòng của họ, nên nó đang nằm ở {{hrTierName}} — vòng của bạn. Chờ bạn phê duyệt là con số duy nhất trên dải này nói về bạn."),
      hint: B("Read that tile first every morning of payroll week. The other four describe the department.",
              "Hãy đọc ô đó đầu tiên mỗi sáng trong tuần tính lương. Bốn ô còn lại mô tả cả bộ phận."),
    },
    {
      id: "locate", target: "pk-tabs",
      instruction: B("Open the run sitting at {{hrTierName}}", "Mở đợt lương đang nằm ở {{hrTierName}}"),
      detail: B("Filter by stage, not by month. The column a run sits in is the gate it is waiting at.",
                "Lọc theo bước phê duyệt, không phải theo tháng. Cột mà đợt lương nằm chính là cổng nó đang chờ."),
    },
    {
      id: "sample", nav: "payslips", target: "ps-chips",
      instruction: B("Read the flagged payslips first", "Đọc các phiếu bị gắn cờ trước"),
      detail: B("One slip is flagged out of 48. Open it, then sample two or three that are not — the engine flags the unusual, not the wrong, so a clean slip can still be incorrect.",
                "Một phiếu bị gắn cờ trong 48 phiếu. Mở nó ra, rồi lấy mẫu hai ba phiếu không bị gắn cờ — hệ thống gắn cờ cái bất thường chứ không phải cái sai, nên một phiếu sạch vẫn có thể sai."),
    },
    {
      id: "variance", target: "ps-breakdown",
      instruction: B("Explain the variance in one sentence", "Giải thích biến động trong một câu"),
      detail: B("Net total 612,480,000 ₫ against June's 596,110,000 ₫. Overtime moved; insurance did not, because it is charged on the registered base. If you cannot say why the totals differ, you are not ready to approve them.",
                "Tổng thực nhận 612.480.000 ₫ so với 596.110.000 ₫ của tháng 6. Tăng ca thay đổi; bảo hiểm thì không, vì tính trên mức lương đóng BH đã đăng ký. Nếu bạn chưa nói được vì sao hai tổng khác nhau, bạn chưa sẵn sàng phê duyệt."),
    },
    {
      id: "consequence", target: "pk-card-actions", consequence: true,
      instruction: B("Read what your decision does", "Đọc xem quyết định của bạn gây ra điều gì"),
      detail: B("Both paths move all 48 payslips together. Neither moves one.",
                "Cả hai lựa chọn đều tác động lên toàn bộ 48 phiếu cùng lúc. Không lựa chọn nào tác động lên một phiếu riêng lẻ."),
    },
    {
      id: "decide", target: "pk-card-actions", decision: true,
      instruction: B("The flagged payslip is still unverified. Approve, or reject?", "Phiếu bị gắn cờ vẫn chưa được xác minh. Phê duyệt, hay từ chối?"),
      detail: B("You cannot open the timesheet from your desk, and the officer who can is still in the building.",
                "Bạn không mở được bảng chấm công từ chỗ mình, và chuyên viên có thể mở thì vẫn đang ở công ty."),
      options: [
        { id: "reject", correct: true, label: B("Reject, with a written reason naming the payslip and what to check", "Từ chối, kèm lý do bằng văn bản nêu rõ phiếu nào và cần kiểm tra gì") },
        { id: "approve", label: B("Approve — the total looks reasonable against June", "Phê duyệt — tổng trông hợp lý so với tháng 6") },
        { id: "wait", label: B("Approve and send an email asking someone to check afterwards", "Phê duyệt rồi gửi email nhờ người khác kiểm tra sau") },
      ],
      recovery: {
        approve: B("Let's rethink that. A total that looks reasonable is not evidence that every slip inside it is — Hùng's three million is comfortably inside a 2.7% movement. The flag was raised about one employee, and approving is you answering it with silence.",
                   "Hãy nghĩ lại một chút. Tổng trông hợp lý không phải bằng chứng rằng từng phiếu bên trong đều hợp lý — ba triệu của Hùng nằm gọn trong mức biến động 2,7%. Cờ được giương lên về một nhân viên cụ thể, và phê duyệt là bạn trả lời nó bằng sự im lặng."),
        wait: B("Let's rethink that. Once you approve, the next gate checks totals rather than lines — so your email is now racing a run that has already moved on, and if it lands late the correction is a retro line rather than a fix.",
                "Hãy nghĩ lại một chút. Khi bạn đã duyệt, cổng kế tiếp kiểm tra các tổng chứ không kiểm tra từng dòng — nên email của bạn đang chạy đua với một đợt lương đã đi tiếp, và nếu nó tới muộn thì hiệu chỉnh sẽ là một dòng hồi tố chứ không còn là sửa lỗi."),
      },
    },
    {
      id: "reason", target: "pk-card-actions",
      instruction: B("Write the reason", "Viết lý do"),
      detail: B("\"Payslip NV0031 — overtime 4,200,000 ₫ is 382% of June. Please verify against the timesheet and resubmit.\" That is a reason somebody can act on. \"Wrong\" is not.",
                "\"Phiếu NV0031 — tăng ca 4.200.000 ₫ bằng 382% tháng 6. Vui lòng đối chiếu bảng chấm công và trình lại.\" Đó là lý do người khác xử lý được. \"Sai\" thì không."),
      hint: B("The reason is recorded against the run with your name and the time, and it is the only thing the officer has to work from.",
              "Lý do được ghi lại trên đợt lương kèm tên bạn và thời điểm, và đó là thứ duy nhất chuyên viên có để làm việc."),
    },
    {
      id: "undo", nav: "payruns", target: "pk-card", undo: true,
      instruction: B("Watch it come back, and send it forward again", "Xem nó quay lại, rồi đưa nó đi tiếp lần nữa"),
      detail: B("The rejected run is in draft with your reason on it. The officer corrects the input, recomputes, and resubmits through the same chain — nothing was lost and nothing was paid. Do the round trip once here, because at done this stops being true.",
                "Đợt bị từ chối nằm ở Nháp cùng lý do của bạn. Chuyên viên sửa dữ liệu đầu vào, tính lại, và trình lại qua đúng chuỗi đó — không mất gì và chưa chi gì. Hãy đi trọn vòng một lần ở đây, vì tới trạng thái Hoàn tất thì điều này không còn đúng nữa."),
    },
  ],

  /* m4 stays on ONE screen throughout, which is unusual for a mission and is
     the right shape here: the whole judgement is about a single record on the
     statutory replica, and navigating away from it would break the one thing
     the learner has to keep in view — that the roster ends up with two rows. */
  m4: [
    {
      id: "open", nav: "statutory", target: "st-roster",
      instruction: B("Open Statutory and read the roster", "Mở Bảo hiểm & Thuế và đọc danh sách chính sách"),
      detail: B("One policy is active — 2026, effective 01/01/2026 — and one is archived, ended on 31/12/2025. That pair is what a correctly applied rate change leaves behind.",
                "Một chính sách đang hiệu lực — bản 2026, hiệu lực từ 01/01/2026 — và một bản đã lưu trữ, kết thúc ngày 31/12/2025. Cặp bản ghi đó chính là dấu vết mà một lần đổi tỷ lệ đúng cách để lại."),
      hint: B("The rates table at the top always shows the CURRENT policy: the active one with the latest effective date.",
              "Bảng tỷ lệ ở trên cùng luôn hiển thị chính sách HIỆN HÀNH: bản đang bật có ngày hiệu lực mới nhất."),
    },
    {
      id: "newrecord", target: "st-new", decision: true,
      instruction: B("A decree raises BHYT's employee share. How do you apply it?", "Một nghị định nâng phần đóng BHYT của người lao động. Bạn áp dụng thế nào?"),
      detail: B("The decree takes effect on 1 August. Today is 20 July, and both the June and July runs are still unfinished.",
                "Nghị định có hiệu lực từ ngày 1/8. Hôm nay là 20/7, và cả đợt tháng 6 lẫn tháng 7 đều chưa xong."),
      hint: B("Ask what would be left to show an inspector afterwards — one record, or two.",
              "Hãy tự hỏi sau đó còn gì để trưng ra cho đoàn kiểm tra — một bản ghi, hay hai."),
      options: [
        { id: "newpolicy", correct: true, label: B("Create a new insurance policy record with its own code", "Tạo một bản ghi chính sách bảo hiểm mới với mã riêng") },
        { id: "editlive", label: B("Edit the rate on the policy that is in force", "Sửa tỷ lệ trên chính sách đang có hiệu lực") },
        { id: "samecode", label: B("Create a new record and reuse the current policy's code", "Tạo bản ghi mới và dùng lại mã của chính sách hiện tại") },
      ],
      recovery: {
        editlive: B("Let's rethink that. A policy has no version history, so editing it does not create a before and an after — the old rate is simply gone, and there is nothing left to show which rates July was computed under. The product's answer to a rate change is a second record, not a second version.",
                    "Hãy nghĩ lại một chút. Chính sách không có lịch sử phiên bản, nên sửa nó không tạo ra bản trước và bản sau — tỷ lệ cũ đơn giản là mất, và không còn gì để chứng minh tháng 7 đã được tính theo tỷ lệ nào. Câu trả lời của sản phẩm cho việc đổi tỷ lệ là một bản ghi thứ hai, không phải một phiên bản thứ hai."),
        samecode: B("Let's rethink that. The code is unique per company, so this one is refused outright — which is fortunate, because a shared code is exactly how two policies become indistinguishable in a report. Give the new record its own code and the pair reads as a history.",
                    "Hãy nghĩ lại một chút. Mã là duy nhất trong mỗi công ty, nên cách này bị từ chối ngay — và đó là điều may, vì trùng mã chính là cách hai chính sách trở nên không phân biệt được trong báo cáo. Cho bản ghi mới một mã riêng thì cặp bản ghi sẽ đọc ra như một lịch sử."),
      },
    },
    {
      id: "rate", target: "st-rates", decision: true,
      instruction: B("Set the BHYT employee share on the new record", "Đặt phần đóng BHYT của người lao động trên bản ghi mới"),
      detail: B("The decree names one number and it applies to the employee share only. The employer's 3% and the other two schemes are untouched.",
                "Nghị định nêu một con số và nó chỉ áp cho phần người lao động. Phần doanh nghiệp 3% và hai loại bảo hiểm còn lại giữ nguyên."),
      hint: B("Two of the three numbers on offer are already on this screen somewhere. That is the trap, not a coincidence.",
              "Hai trong ba con số đưa ra đã có sẵn đâu đó trên màn hình này. Đó là cái bẫy, không phải trùng hợp."),
      options: [
        { id: "two", correct: true, label: B("2.0%", "2,0%") },
        { id: "onefive", label: B("1.5%", "1,5%") },
        { id: "three", label: B("3.0%", "3,0%") },
      ],
      recovery: {
        onefive: B("Let's rethink that. 1.5% is the rate that is in force today — typing it into the new record creates a policy that changes nothing, and the first anybody knows about it is when August's deductions come out identical to July's.",
                   "Hãy nghĩ lại một chút. 1,5% là tỷ lệ đang có hiệu lực hôm nay — gõ nó vào bản ghi mới sẽ tạo ra một chính sách không thay đổi gì, và người ta chỉ biết khi khấu trừ tháng 8 ra y hệt tháng 7."),
        three: B("Let's rethink that. 3.0% is the EMPLOYER's BHYT share, sitting one column to the right. Putting it in the employee column doubles what every employee pays and leaves the company paying the same — a mistake that is invisible on this screen and very visible on a payslip.",
                 "Hãy nghĩ lại một chút. 3,0% là phần BHYT của DOANH NGHIỆP, nằm ngay cột bên phải. Đặt nó vào cột người lao động sẽ làm mọi nhân viên đóng gấp đôi trong khi công ty vẫn đóng như cũ — một lỗi không nhìn thấy trên màn hình này nhưng rất dễ thấy trên phiếu lương."),
      },
    },
    {
      id: "effective", target: "st-effective", decision: true,
      instruction: B("Choose the effective date", "Chọn ngày hiệu lực"),
      detail: B("It is 20 July and the decree applies from 1 August. This field is the company's record of when the change legally started — it is read by auditors and by the statutory reports, and it is not read by anything that computes pay.",
                "Hôm nay là 20/7 và nghị định áp dụng từ 1/8. Ô này là ghi nhận của doanh nghiệp về thời điểm thay đổi bắt đầu có hiệu lực pháp lý — kiểm toán và các báo cáo bắt buộc đọc nó, còn những thứ tính ra tiền lương thì không."),
      hint: B("Whatever date you type, this screen starts showing the new rates the moment you save. So the date is not a switch — it is a statement about the law, and it has to be true.",
              "Dù bạn gõ ngày nào, màn hình này cũng bắt đầu hiển thị tỷ lệ mới ngay khi bạn lưu. Nên ngày hiệu lực không phải một cái công tắc — nó là một tuyên bố về pháp luật, và nó phải đúng."),
      options: [
        { id: "aug", correct: true, label: B("01/08/2026 — the first day the decree applies", "01/08/2026 — ngày đầu tiên nghị định áp dụng") },
        { id: "today", label: B("Today, 20/07/2026, so it is not forgotten", "Hôm nay, 20/07/2026, cho khỏi quên") },
        { id: "jan", label: B("01/01/2026, to keep the year consistent", "01/01/2026, cho nhất quán cả năm") },
      ],
      recovery: {
        today: B("Let's rethink that. The decree says 1 August, so a record dated 20 July declares a legal start the company cannot evidence — and the statutory reports built from it will say July ran at the new rate when it did not. Dating it correctly costs nothing: this screen shows the new rates from the moment you save either way, which is why the people reviewing July need telling rather than the field needing bending.",
                 "Hãy nghĩ lại một chút. Nghị định nói ngày 1/8, nên một bản ghi đề ngày 20/7 là khai một mốc pháp lý mà doanh nghiệp không chứng minh được — và các báo cáo bắt buộc lập từ đó sẽ nói tháng 7 chạy theo tỷ lệ mới, trong khi không phải vậy. Ghi đúng ngày chẳng tốn gì: đằng nào màn hình này cũng hiển thị tỷ lệ mới ngay khi bạn lưu, nên thứ cần làm là báo cho những người đang soát xét tháng 7, chứ không phải bẻ cong cái ngày."),
        jan: B("Let's rethink that. Backdating to January declares that the company has been contributing at the new rate all year — for four months that have already been paid, reported and filed at the old one. That is not a tidier record, it is a false one, and it is the kind an inspection finds by comparing the declaration with the returns.",
               "Hãy nghĩ lại một chút. Lùi về tháng 1 là khai rằng doanh nghiệp đã đóng theo tỷ lệ mới suốt cả năm — trong khi bốn tháng đã chi, đã báo cáo và đã nộp theo tỷ lệ cũ. Đó không phải một bản ghi gọn gàng hơn, mà là một bản ghi sai sự thật, và đúng loại mà đoàn kiểm tra phát hiện khi đối chiếu bản khai với các tờ khai đã nộp."),
      },
    },
    {
      id: "reconcile", target: "rep-slipline",
      instruction: B("Check what the payslip is still charging", "Kiểm tra xem phiếu lương vẫn đang tính bao nhiêu"),
      detail: B("The declaration now says 2.0%. Mai's BHYT line still says −180,000 ₫, which is 1.5% of her registered base — because that line is priced by a parameter on Retail's configuration, not by the record you just wrote. This is the reconciliation the Statutory screen exists for, and right now it fails.",
                "Bản khai báo giờ nói 2,0%. Dòng BHYT của Mai vẫn là −180.000 ₫, tức 1,5% trên mức đóng đã đăng ký — vì dòng đó được tính bằng một tham số trong cấu hình của Bán lẻ, không phải bằng bản ghi bạn vừa tạo. Đây chính là phép đối chiếu mà màn hình Bảo hiểm & Thuế sinh ra để làm, và ngay lúc này nó đang lệch."),
      hint: B("If the configuration is changed too, her BHYT becomes 240,000 ₫ and her net falls 57,000 — not 60,000, because insurance comes off before the tax relief. But none of that happens from this screen.",
              "Nếu cấu hình cũng được sửa, BHYT của cô ấy thành 240.000 ₫ và thực nhận giảm 57.000 — không phải 60.000, vì bảo hiểm được trừ trước các khoản giảm trừ thuế. Nhưng không điều nào trong số đó xảy ra từ màn hình này."),
    },
    {
      id: "consequence", target: "st-new", consequence: true,
      instruction: B("Read what saving this record does", "Đọc xem việc lưu bản ghi này gây ra điều gì"),
      detail: B("Read the scope line twice. It is company-wide and it reprices nothing — the two facts people find hardest to hold together on this screen, and the reason the next step goes looking at a payslip that has not moved.",
                "Hãy đọc dòng phạm vi hai lần. Nó có hiệu lực trên toàn công ty nhưng không tính lại khoản nào — hai điều mà người ta khó giữ cùng lúc nhất ở màn hình này, và cũng là lý do bước kế tiếp đi xem một phiếu lương chưa hề thay đổi."),
    },
    {
      id: "commit", target: "st-roster",
      instruction: B("Save the new policy and read the roster", "Lưu chính sách mới và đọc lại danh sách"),
      detail: B("The August record is now the one the rates table shows, because it has the latest effective date among the active policies — the table does not compare that date to today. The 2026 record stays on the list as the evidence of what was declared before it.",
                "Bản ghi tháng 8 giờ là bản mà bảng tỷ lệ hiển thị, vì nó có ngày hiệu lực mới nhất trong số các chính sách đang bật — bảng này không so ngày đó với hôm nay. Bản ghi 2026 vẫn ở lại danh sách như bằng chứng cho mức đã khai báo trước đó."),
      hint: B("Read the effective-date chip above the rates table after you save. If it says 01/08, the screen is already showing August's declaration to everybody who opens it.",
              "Sau khi lưu, hãy đọc chip ngày hiệu lực phía trên bảng tỷ lệ. Nếu nó hiện 01/08 thì màn hình đã hiển thị bản khai báo của tháng 8 cho mọi người mở nó."),
    },
    {
      id: "undo", target: "st-roster", undo: true,
      instruction: B("Now undo it: archive the August policy", "Giờ hãy hoàn tác: lưu trữ chính sách tháng 8"),
      detail: B("Archiving takes it out of the active set, so the rates table falls back to the 2026 declaration and the roster stops listing it. That is the whole undo, and it is clean precisely because nothing was ever computed from it — a mistake in a declaration costs a correction, not a recompute.",
                "Lưu trữ sẽ đưa nó ra khỏi nhóm đang bật, nên bảng tỷ lệ quay lại bản khai báo 2026 và danh sách cũng thôi liệt kê nó. Đó là toàn bộ việc hoàn tác, và nó gọn gàng chính vì chưa có gì được tính từ nó — sai sót trong một bản khai báo chỉ tốn một lần đính chính, không tốn một lần tính lại."),
      hint: B("Compare that with a configuration change, which is reversible in the records and not in the payslips it has already produced. That difference is why the two are separate.",
              "Hãy so với một lần sửa cấu hình: bản ghi thì hoàn tác được, còn những phiếu lương nó đã tạo ra thì không. Chính khác biệt đó là lý do hai thứ này tách rời nhau."),
    },
  ],

  /* ---------------------------------------------------------------------------
     mL1 — the live capstone's step machine.

     THREE KINDS OF STEP, and the difference is who answers them:
       `check`  the SERVER answers, by looking at the record the learner just
                changed with the product's own buttons. Read-only, always
                gated (models/learn_live.py).
       `ack`    the LEARNER answers, because nothing observable happened —
                they read a card, or they are watching a gate somebody else
                holds.
       neither  instructional; Next moves it on.

     `nav` names a learn.screen, not an action: the runner turns it into a
     deep link through the SAME learn.screen record the Coach grounds on, so
     the two surfaces can never disagree about what "Pay Runs" means.

     No step asserts an amount. Every number in a live run is on the screen and
     belongs to the learner.
     ------------------------------------------------------------------------ */
  mL1: [
    {
      id: "brief", ack: true,
      instruction: B("Read what makes this one different", "Đọc xem nhiệm vụ này khác ở chỗ nào"),
      detail: B("Everything from here happens in Payobook itself. The practice missions ran on a fixture with no server behind them; this one creates real payslip records in the shared demo company, on the division assigned to your account. It is the safest real payroll you will ever run — and it is still a real one.",
                "Từ đây trở đi mọi thứ diễn ra ngay trong Payobook. Các nhiệm vụ thực hành chạy trên dữ liệu giả lập không có máy chủ phía sau; nhiệm vụ này tạo ra phiếu lương thật trong công ty demo dùng chung, trên bộ phận được gán cho tài khoản của bạn. Đây là kỳ lương thật an toàn nhất bạn từng chạy — nhưng vẫn là một kỳ lương thật."),
      hint: B("The run this mission watches is the one YOU create. Your division already has a June run sitting there from the demo build, and the mission deliberately ignores it — otherwise step one would tick itself green for work you had not done.",
              "Đợt lương mà nhiệm vụ này theo dõi là đợt do CHÍNH BẠN tạo. Bộ phận của bạn đã có sẵn một đợt tháng 6 từ lúc dựng bản demo, và nhiệm vụ cố ý bỏ qua đợt đó — nếu không thì bước đầu tiên sẽ tự động xanh cho phần việc bạn chưa hề làm."),
    },
    {
      id: "open", nav: "runpayroll", ack: true,
      instruction: B("Open Run Payroll", "Mở Chạy bảng lương"),
      detail: B("Your division is already selected and moved to the top of the list, and the period is pinned to June 2026 — the one month the demo world leaves open. Read both before you go on.",
                "Bộ phận của bạn đã được chọn sẵn và đưa lên đầu danh sách, còn kỳ lương được cố định ở tháng 6/2026 — tháng duy nhất mà môi trường demo để mở. Hãy đọc cả hai trước khi đi tiếp."),
      hint: B("The other five divisions are still on the list on purpose. You are welcome to look; the mission checks the one that is yours.",
              "Năm bộ phận còn lại vẫn nằm trong danh sách một cách có chủ ý. Bạn cứ xem thoải mái; nhiệm vụ chỉ kiểm tra đúng bộ phận của bạn."),
    },
    {
      id: "consequence", consequence: true,
      instruction: B("Read what Compute is about to do", "Đọc xem nút Tính sắp làm gì"),
      detail: B("This card is teaching, not a gate: nothing here blocks the button, and Payobook's own rules are what decide whether you may press it. Read the scope, the way back and the thing to verify — then act, in the product.",
                "Thẻ này để dạy, không phải để chặn: không có gì ở đây khoá nút lại, và chính các quy tắc của Payobook mới quyết định bạn có được bấm hay không. Hãy đọc phạm vi, lối quay lại và thứ cần kiểm tra — rồi thao tác, ngay trong sản phẩm."),
    },
    {
      id: "compute", check: "june_run_computed",
      instruction: B("Compute the run", "Tính đợt lương"),
      detail: B("Press Compute in the wizard. When the payslips exist, this step ticks itself — the mission is watching the records, not your clicks.",
                "Hãy bấm Tính trong trình hướng dẫn. Khi các phiếu lương đã có, bước này tự đánh dấu hoàn thành — nhiệm vụ đang theo dõi bản ghi, không theo dõi cú bấm của bạn."),
      hint: B("Nothing is paid and nobody is notified. Drafts can be deleted and recomputed as often as you want.",
              "Chưa có gì được chi và chưa ai được thông báo. Bản nháp có thể xoá và tính lại bao nhiêu lần tuỳ ý."),
    },
    {
      id: "review", nav: "payslips", ack: true,
      instruction: B("Open the payslips and read what is flagged", "Mở phiếu lương và đọc những gì bị gắn cờ"),
      detail: B("Filter to \"Need review\" first, then sample two or three that are not flagged. The engine flags the unusual, not the wrong — so a clean slip can still be incorrect, and a flagged one can be perfectly fine.",
                "Hãy lọc theo \"Cần soát xét\" trước, rồi lấy mẫu hai ba phiếu không bị gắn cờ. Hệ thống gắn cờ cái bất thường chứ không phải cái sai — nên một phiếu sạch vẫn có thể sai, và một phiếu bị gắn cờ vẫn có thể hoàn toàn ổn."),
      hint: B("Open the breakdown on one slip and follow it from base to net. If you can say where each line came from, you are ready to submit.",
              "Hãy mở bảng chi tiết của một phiếu và đi từ lương cơ bản tới thực nhận. Nếu bạn nói được mỗi dòng đến từ đâu thì bạn đã sẵn sàng để trình duyệt."),
    },
    {
      id: "submit", nav: "payruns", check: "june_run_submitted",
      instruction: B("Submit the run for approval", "Trình đợt lương lên phê duyệt"),
      detail: B("This is the step that stops being reversible in the easy way. After it, the run moves only by being approved at each gate, or by being rejected back to draft with a written reason.",
                "Đây là bước mà việc hoàn tác không còn dễ dàng nữa. Sau bước này, đợt lương chỉ đi tiếp bằng cách được duyệt ở từng cổng, hoặc bị từ chối trả về Nháp kèm lý do bằng văn bản."),
      hint: B("Submitting is you saying the flags have been answered. If any of them have not, go back — the run will still be there.",
              "Trình duyệt là bạn tuyên bố rằng các cờ cảnh báo đã được trả lời. Nếu còn cờ nào chưa, hãy quay lại — đợt lương vẫn nằm đó."),
    },
    {
      id: "officer", check: "june_run_officer_done",
      instruction: B("Move it past the Payroll Officer gate", "Đưa nó qua cổng Chuyên viên tính lương"),
      detail: B("On the demo world your account holds the approval tiers, so you can walk the run through the chain yourself. On a real tenant these are four different people, and the waiting between them is most of what payroll week is.",
                "Trên môi trường demo, tài khoản của bạn giữ các vòng phê duyệt, nên bạn tự đưa đợt lương đi hết chuỗi được. Ở một hệ thống thật, đây là bốn con người khác nhau, và phần lớn một tuần tính lương chính là những khoảng chờ giữa họ."),
      hint: B("The column a run sits in names the tier that has to act next. That is the answer to \"who do I chase\".",
              "Cột mà đợt lương đang nằm chỉ đích danh vòng phải xử lý tiếp theo. Đó chính là câu trả lời cho \"tôi phải hỏi ai\"."),
    },
    {
      id: "done", check: "june_run_done",
      instruction: B("Take it through the remaining gates to done", "Đưa nó qua các cổng còn lại tới Hoàn tất"),
      detail: B("HR review, then finance approval, then done. Only a completed run offers the bank file, the journals and the payments — those buttons appear exactly when every gate has said yes, and that is the whole point of the chain.",
                "HR soát xét, rồi Tài chính phê duyệt, rồi Hoàn tất. Chỉ đợt đã Hoàn tất mới hiện tệp chi lương, bút toán và các khoản thanh toán — các nút đó xuất hiện đúng lúc mọi cổng đã đồng ý, và đó chính là ý nghĩa của cả chuỗi."),
      hint: B("After done, a correction is a retro line and never an edit. That is not a restriction — it is what keeps a reported month reportable.",
              "Sau khi Hoàn tất, mọi hiệu chỉnh là một dòng hồi tố chứ không bao giờ là sửa trực tiếp. Đó không phải hạn chế — đó là thứ giữ cho một kỳ đã báo cáo vẫn báo cáo được."),
    },
  ],
};

/* =============================================================================
   7. SCREENS — what the Coach is grounded on
   -----------------------------------------------------------------------------
   `blurb` answers "what is this screen"; `next` answers "what should I do next
   here". Both are shipped as real fields on learn.screen, and the two dynamic
   intents read them — so a screen with no `next` renders an empty answer to the
   most common question the Coach receives.

   `chips` are the questions offered BEFORE anything is typed. Three to five: a
   longer list is a menu, and someone who is stuck does not read menus.

   NOTE the eighth entry. importwizard is a FLOW, not a destination — it has no
   sidebar leaf, so it is the one screen resolved by an action tag instead. Seven
   leaves, eight screens.
   ========================================================================== */
const SCREEN_CTX = {
  runpayroll: {
    blurb: B("The wizard that creates and computes one batch of draft payslips for a division and a period.",
             "Trình hướng dẫn tạo và tính một lô phiếu lương nháp cho một bộ phận và một kỳ."),
    next: B("Check the configuration and the eligible headcount in the scope panel, then compute. Computing creates drafts only — nothing is paid, sent or approved.",
            "Kiểm tra cấu hình và số nhân viên đủ điều kiện ở bảng phạm vi, rồi tính. Tính chỉ tạo bản nháp — chưa có gì được chi, gửi hay phê duyệt."),
    chips: ["whatpage", "affectrun", "needreview", "checkfinal", "practice"],
  },
  payruns: {
    blurb: B("Every pay run on one board, in the column of the approval stage it is waiting at.",
             "Mọi đợt tính lương trên một bảng, nằm ở cột của bước phê duyệt mà nó đang chờ."),
    /* LIVE SITE 1 of 2. On the demo world this names the prospect's OWN
       division and the state their OWN June run is actually in — which is the
       whole reason "what should I do next here" is worth asking on a board
       full of other people's work. `liveFallback` is the sentence every other
       tenant sees, and it is the previous wording verbatim: adding a live
       token must not change what a real company reads. */
    next: B("Your division on this demo is {{live:division_name}}, and its June run is at {{live:june_run_state}} right now. Look at \"Awaiting your approval\" first — that count is the work only you can unblock.",
            "Bộ phận của bạn trên bản demo này là {{live:division_name}}, và đợt lương tháng 6 của bộ phận đó hiện đang ở {{live:june_run_state}}. Nhìn \"Chờ bạn phê duyệt\" trước — con số đó là phần việc chỉ bạn mới gỡ được."),
    liveFallback: B("Look at \"Awaiting your approval\" first — that count is the work only you can unblock. Everything else on this board is somebody else's gate.",
                    "Nhìn \"Chờ bạn phê duyệt\" trước — con số đó là phần việc chỉ bạn mới gỡ được. Mọi thứ khác trên bảng này là cổng của người khác."),
    chips: ["approve", "reject", "checkfinal", "retroq", "whatnext"],
  },
  payslips: {
    blurb: B("Line-by-line review of every payslip in one run, with the working behind each net figure.",
             "Soát xét từng dòng của mọi phiếu lương trong một đợt, kèm phần tính toán phía sau mỗi con số thực nhận."),
    next: B("Filter to \"Need review\" and read those first. A flag is the engine asking a question, not telling you something is broken.",
            "Lọc theo \"Cần soát xét\" và đọc những phiếu đó trước. Cờ cảnh báo là hệ thống đang hỏi một câu, không phải báo rằng có gì đó hỏng."),
    chips: ["whydiff", "needreview", "bhxh", "prorata", "fixerror"],
  },
  import: {
    blurb: B("Where attendance, overtime and HR data arrive from files and connected systems, before any of it becomes a payslip.",
             "Nơi dữ liệu chấm công, tăng ca và nhân sự đi vào từ tệp và các hệ thống đã kết nối, trước khi bất kỳ phần nào trở thành phiếu lương."),
    next: B("Start an import to use the guided flow — it scores the file and lets you fix rows before anything is written. A batch that stops before commit has changed nothing.",
            "Bắt đầu một đợt nhập để dùng luồng có hướng dẫn — nó chấm điểm tệp và cho bạn sửa các dòng trước khi ghi bất cứ gì. Một đợt dừng trước bước ghi nhận thì chưa thay đổi gì cả."),
    chips: ["whatpage", "confidence", "affectrun", "fixerror"],
  },
  importwizard: {
    blurb: B("The four-step import: choose a source, review what matched, fix what did not, then commit.",
             "Bốn bước nhập liệu: chọn nguồn, soát phần đã khớp, sửa phần chưa khớp, rồi ghi nhận."),
    next: B("Resolve every row in \"Need attention\" before you commit. Commit is the first control in this flow that writes anything — everything before it is a preview.",
            "Xử lý mọi dòng trong \"Cần xử lý\" trước khi ghi nhận. Ghi nhận là nút đầu tiên trong luồng này thực sự ghi dữ liệu — mọi thứ trước đó chỉ là xem trước."),
    chips: ["confidence", "fixerror", "whatnext", "practice"],
  },
  fullfinal: {
    blurb: B("Final settlement for departing employees: last salary, unused leave and deductions, in one place.",
             "Quyết toán cho nhân viên thôi việc: lương cuối, phép chưa dùng và các khoản khấu trừ, ở cùng một nơi."),
    next: B("Check that everyone settled here is excluded from the normal monthly run for the same period. A leaver in both is paid twice.",
            "Kiểm tra rằng mọi người được quyết toán ở đây đã bị loại khỏi đợt lương tháng thông thường của cùng kỳ. Người vừa quyết toán vừa nằm trong đợt tháng sẽ được trả hai lần."),
    chips: ["whatpage", "prorata", "whatnext"],
  },
  proration: {
    blurb: B("The audit trail behind every part-month amount: days worked, standard days, and the factor between them.",
             "Nhật ký kiểm toán phía sau mọi khoản lương tháng lẻ ngày: ngày công thực tế, ngày công chuẩn, và hệ số giữa hai con số."),
    next: B("Read the factor, not the money. If the factor is right and the amount still looks wrong, the problem is upstream in the contract or the import.",
            "Hãy đọc hệ số chứ không phải số tiền. Nếu hệ số đúng mà số tiền vẫn có vẻ sai thì vấn đề nằm ở phía trên: hợp đồng hoặc dữ liệu nhập."),
    chips: ["prorata", "whydiff", "whatpage"],
  },
  retro: {
    blurb: B("Corrections that belong to a closed month, paid in the current one, with the source period recorded against them.",
             "Các hiệu chỉnh thuộc về một kỳ đã đóng, được chi trong kỳ hiện tại, và có ghi rõ kỳ gốc kèm theo."),
    next: B("Check the source period on each line. That field is what lets a closed month stay closed and still be reported correctly later.",
            "Kiểm tra kỳ gốc trên từng dòng. Chính trường đó giúp một kỳ đã đóng vẫn luôn đóng mà sau này vẫn báo cáo đúng."),
    chips: ["retroq", "fixerror", "whatpage"],
  },

  /* -- Setup ------------------------------------------------------------- */
  formula: {
    blurb: B("The visible rulebook: every payslip line for one division, as a named component with a formula you can read.",
             "Bộ quy tắc nhìn thấy được: mỗi dòng phiếu lương của một bộ phận là một thành phần có tên, kèm công thức bạn đọc được."),
    next: B("Read the component list first, then open the one behind the number you are asking about. Nothing here is live until a configuration is activated — and a simulation against last month is what tells you whether it should be.",
            "Hãy đọc danh sách thành phần trước, rồi mở đúng thành phần đứng sau con số bạn đang thắc mắc. Không gì ở đây có hiệu lực cho tới khi một cấu hình được kích hoạt — và một lần mô phỏng trên tháng trước sẽ cho biết có nên kích hoạt hay không."),
    chips: ["whysetup", "editlive", "whichconfig", "configvsstructure", "practice"],
  },
  structures: {
    blurb: B("The legacy Odoo salary structures and their rules — kept because historical payslips still reference them.",
             "Các cấu trúc lương và quy tắc Odoo thế hệ cũ — giữ lại vì phiếu lương lịch sử vẫn tham chiếu tới chúng."),
    next: B("Read, do not build. New pay logic belongs in a formula configuration; what is here exists so that payslips from before the migration can still be explained.",
            "Hãy đọc, đừng xây mới ở đây. Logic lương mới thuộc về cấu hình công thức; những gì ở đây tồn tại để các phiếu lương từ trước khi chuyển đổi vẫn giải thích được."),
    chips: ["configvsstructure", "whysetup", "whatpage"],
  },
  statutory: {
    blurb: B("The company's active insurance policy and tax table: BHXH, BHYT and BHTN rates and ceilings, and the thuế TNCN bands.",
             "Chính sách bảo hiểm và biểu thuế đang hiệu lực của công ty: tỷ lệ và trần đóng BHXH, BHYT, BHTN, cùng các bậc thuế TNCN."),
    next: B("Check that the rates on display are the ones currently in force — the table shows the active policy with the latest effective date. To change one, create a new policy record dated from the day the change applies; never edit the one in force.",
            "Hãy kiểm tra các tỷ lệ đang hiển thị có đúng là tỷ lệ hiện hành không — bảng này hiển thị chính sách đang bật có ngày hiệu lực mới nhất. Muốn đổi một tỷ lệ, hãy tạo bản ghi chính sách mới với ngày hiệu lực đúng bằng ngày thay đổi có hiệu lực; đừng bao giờ sửa bản đang chạy."),
    chips: ["changerate", "whichpolicy", "ceiling", "pitcalc", "bhxh"],
  },
  integrations: {
    blurb: B("The connectors payroll data arrives through — an HR system, a time clock, the bank — with their field mappings and sync history.",
             "Các đầu nối mà dữ liệu tính lương đi vào qua đó — hệ thống nhân sự, máy chấm công, ngân hàng — kèm ánh xạ trường và lịch sử đồng bộ."),
    next: B("Read the last-sync time on every connector, not just its status. Connected describes the credentials; the sync time describes the data, and a connector that stopped looks exactly like one that is working.",
            "Hãy đọc thời điểm đồng bộ gần nhất của từng đầu nối, không chỉ đọc trạng thái. Đã kết nối nói về thông tin đăng nhập; thời điểm đồng bộ mới nói về dữ liệu, và một đầu nối đã ngừng chạy trông y hệt một đầu nối đang chạy tốt."),
    chips: ["syncbroken", "whysetup", "whatnext"],
  },
};

/* =============================================================================
   8. COACH INTENTS
   -----------------------------------------------------------------------------
   Every answer the Coach can give is a block here. There is no path from a
   question to the screen that skips this file, which is what lets it promise
   never to invent a rate.

   RULES THE TESTS ENFORCE, so the content has to satisfy them:
     · anything factual (p / steps / calc / calcKpi / ok / warn) also carries a
       `src` block — an answer with no provenance is indistinguishable from a
       guess. Dynamic intents are exempt: they cite the screen they are on.
     · a `refusal` in a capability group also carries `who` and `how`. A refusal
       that stops at "you can't" leaves the person exactly where they were.
     · match phrases stay untranslated and mixed EN/VI in one bag.
     · no two intents share a phrase — the label is auto-added as a phrase, and
       two intents answering to one sentence would resolve by key order, which
       is not a decision anybody made.
   ========================================================================== */
const QA = [
  {
    id: "whatpage", screens: "*", dynamic: "screenCtx",
    label: B("What is this screen for?", "Màn hình này để làm gì?"),
    match: ["what does this page do", "what is this screen", "trang này", "màn hình này làm gì", "what page"],
  },
  {
    id: "whatnext", screens: "*", dynamic: "nextStep",
    label: B("What should I do next here?", "Tôi nên làm gì tiếp theo ở đây?"),
    match: ["what should i do next", "what now", "làm gì tiếp", "tiếp theo làm gì", "buoc tiep theo"],
  },

  {
    id: "needreview", screens: ["runpayroll", "payslips"],
    label: B("Why does this payslip need review?", "Vì sao phiếu lương này cần soát xét?"),
    match: ["why is this flagged", "what does the flag mean", "needs review", "sao bi gan co", "phiếu này bị gắn cờ"],
    showMe: ["pw-exceptions", "ps-list"],
    blocks: [
      { k: "p", v: B("A flag is the engine saying it found something unusual for this employee and would like a human to confirm it was intended. It is a question, not an error — the payslip computed correctly from the inputs it was given.",
                     "Cờ cảnh báo là hệ thống nói rằng nó thấy điều gì đó bất thường với nhân viên này và muốn có người xác nhận đó là có chủ ý. Đó là câu hỏi, không phải lỗi — phiếu lương đã tính đúng từ dữ liệu đầu vào mà nó nhận được.") },
      { k: "p", v: B("On this run it is Trần Văn Hùng: overtime of 4,200,000 ₫ against 1,100,000 ₫ in June, which is 382% of last month. That is well inside the range a genuine peak week produces, and also exactly what 4.6 hours typed as 46 looks like.",
                     "Trên đợt này là Trần Văn Hùng: tăng ca 4.200.000 ₫ so với 1.100.000 ₫ của tháng 6, tức 382% tháng trước. Con số đó hoàn toàn nằm trong khoảng mà một tuần cao điểm thật tạo ra, và cũng đúng là hình dạng của 4,6 giờ bị gõ thành 46.") },
      { k: "warn", v: B("Clearing a flag without understanding it is answering the question with a guess. Check the timesheet before the run leaves draft.",
                        "Xoá một cờ mà chưa hiểu nó là trả lời câu hỏi bằng phỏng đoán. Hãy đối chiếu bảng chấm công trước khi đợt lương rời trạng thái Nháp.") },
      { k: "src", v: B("The run's exception list, and Hùng's June and July payslips.",
                       "Danh sách ngoại lệ của đợt lương, và phiếu tháng 6 cùng tháng 7 của Hùng.") },
    ],
  },

  {
    id: "whydiff", screens: ["payslips", "proration"],
    label: B("Why is this pay different from last month?", "Vì sao lương này khác tháng trước?"),
    match: ["why is the pay different", "pay changed", "khác tháng trước", "sao lương thay đổi", "luong khac thang truoc"],
    showMe: ["ps-breakdown"],
    simpler: B("Two things move a monthly salary and one thing usually does not. Overtime moves it, and tax follows the overtime. Insurance normally stays put, because it is worked out from the salary written in the contract rather than from what was actually earned that month.",
               "Có hai thứ làm lương tháng thay đổi và một thứ thường thì không. Tăng ca làm lương thay đổi, và thuế đi theo tăng ca. Bảo hiểm thường đứng yên, vì nó được tính từ mức lương ghi trong hợp đồng chứ không phải từ số thực sự kiếm được trong tháng đó."),
    blocks: [
      { k: "p", v: B("Take Mai's June to July as the worked example. Net went from 12,064,000 ₫ to 12,919,000 ₫, and it decomposes exactly:",
                     "Lấy tháng 6 sang tháng 7 của Mai làm ví dụ. Thực nhận đi từ 12.064.000 ₫ lên 12.919.000 ₫, và phân tách chính xác như sau:") },
      { k: "calcKpi" },
      { k: "p", v: B("Insurance did not move because BHXH, BHYT and BHTN are charged on the registered insurance base — her contract base of 12,000,000 ₫ — and overtime is not part of that base. Tax did move, because taxable income is a monthly figure.",
                     "Bảo hiểm không đổi vì BHXH, BHYT và BHTN tính trên mức lương đóng bảo hiểm đã đăng ký — lương cơ bản theo hợp đồng 12.000.000 ₫ — và tăng ca không nằm trong mức đó. Thuế thì có đổi, vì thu nhập chịu thuế là con số theo tháng.") },
      { k: "src", v: B("Mai's June and July payslips, configuration HOASEN_RETAIL_END v12.",
                       "Phiếu lương tháng 6 và tháng 7 của Mai, cấu hình HOASEN_RETAIL_END v12.") },
    ],
  },

  {
    id: "approve", screens: ["payruns", "payslips"],
    label: B("Can I approve this run?", "Tôi có thể phê duyệt đợt này không?"),
    match: ["how do i approve", "can i approve", "approve this run", "phê duyệt thế nào", "toi duyet duoc khong"],
    showMe: ["pk-card-actions"],
    roleVariants: {
      any: [
        { k: "p", v: B("A run is approved one gate at a time: draft, then the Payroll Officer tier, then {{hrTierName}}, then {{gmTierName}}, then done. Each gate belongs to one group, and the buttons on a card are decided by the record's own gate fields and your groups — so what you can see is what you can do.",
                       "Một đợt lương được duyệt lần lượt qua từng cổng: Nháp, rồi vòng Chuyên viên tính lương, rồi {{hrTierName}}, rồi {{gmTierName}}, rồi Hoàn tất. Mỗi cổng thuộc về một nhóm quyền, và các nút trên thẻ do chính các trường kiểm soát cổng của bản ghi và nhóm quyền của bạn quyết định — nên thấy được gì là làm được nấy.") },
        { k: "src", v: B("The approval chain on the pay run record, and your group membership.",
                         "Chuỗi phê duyệt trên bản ghi đợt lương, và nhóm quyền của bạn.") },
      ],
      manager: [
        { k: "ok", v: B("Yes. You hold an approval gate, so a run waiting at your tier will show Approve on its card. Approving moves all 48 payslips together — there is no way to approve some of them.",
                        "Có. Bạn giữ một cổng phê duyệt, nên đợt lương đang chờ ở vòng của bạn sẽ hiện nút Phê duyệt trên thẻ. Phê duyệt sẽ chuyển toàn bộ 48 phiếu cùng lúc — không có cách nào duyệt một phần.") },
        { k: "steps", v: [
          { t: B("Open the run in the column that names your tier", "Mở đợt lương ở cột mang tên vòng của bạn"), a: "pk-tabs" },
          { t: B("Open every flagged payslip, and sample a few that are not flagged", "Mở mọi phiếu bị gắn cờ, và lấy mẫu vài phiếu không bị gắn cờ"), a: "ps-chips" },
          { t: B("Approve — or reject with a written reason, which returns the run to draft", "Phê duyệt — hoặc từ chối kèm lý do bằng văn bản, đợt sẽ quay về Nháp"), a: "pk-card-actions" },
        ] },
        { k: "src", v: B("The pay run's approval chain and the gate fields on the card.",
                         "Chuỗi phê duyệt của đợt lương và các trường kiểm soát cổng trên thẻ.") },
      ],
      owner: [
        { k: "ok", v: B("Yes — you hold every gate. That is worth using carefully rather than often: a chain where one person can sign every tier records one opinion four times, and the point of the tiers is that they are four different reads.",
                        "Có — bạn giữ mọi cổng. Điều đó nên được dùng một cách thận trọng chứ không nên dùng thường xuyên: một chuỗi mà một người ký được mọi vòng chỉ ghi lại một ý kiến bốn lần, trong khi ý nghĩa của các vòng là bốn lần soát khác nhau.") },
        { k: "src", v: B("The pay run's approval chain and your administrator groups.",
                         "Chuỗi phê duyệt của đợt lương và nhóm quyền quản trị của bạn.") },
      ],
      operator: [
        { k: "p", v: B("You own the first gate: you can submit a draft run for review and approve at the Payroll Officer tier. {{hrTierName}} and {{gmTierName}} come after you and belong to other people.",
                       "Bạn giữ cổng đầu tiên: bạn có thể trình một đợt nháp lên soát xét và duyệt ở vòng Chuyên viên tính lương. {{hrTierName}} và {{gmTierName}} nằm sau bạn và thuộc về người khác.") },
        { k: "steps", v: [
          { t: B("Open the run while it is still in draft", "Mở đợt lương khi còn ở trạng thái Nháp"), a: "pk-card" },
          { t: B("Submit it for review", "Trình lên soát xét"), a: "pk-card-actions" },
          { t: B("Approve your own tier once your checks pass", "Duyệt vòng của bạn khi các bước kiểm tra đã đạt"), a: "pk-card-actions" },
        ] },
        { k: "src", v: B("The pay run's approval chain and your group membership.",
                         "Chuỗi phê duyệt của đợt lương và nhóm quyền của bạn.") },
      ],
      no_access: [
        { k: "refusal", v: B("Not from here. Approving a pay run needs one of the payroll approval groups, and this screen is not in your menu — so there is no button for you to be missing.",
                             "Không phải từ đây. Phê duyệt một đợt lương cần một trong các nhóm quyền phê duyệt lương, và màn hình này không có trong menu của bạn — nên không có nút nào mà bạn đang thiếu cả.") },
        { k: "who", v: B("The Payroll Officer tier, {{hrTierName}} and {{gmTierName}} each belong to a different group. The column a run is sitting in names the tier that has to act next.",
                         "Vòng Chuyên viên tính lương, {{hrTierName}} và {{gmTierName}} mỗi vòng thuộc một nhóm quyền khác nhau. Cột mà đợt lương đang nằm chỉ đích danh vòng phải xử lý tiếp theo.") },
        { k: "how", v: B("Ask {{payrollSupportContact}}. Access to an approval tier is a decision about who signs for money, so it is granted deliberately rather than on request — expect to be asked what you need it for.",
                         "Hãy hỏi {{payrollSupportContact}}. Quyền vào một vòng phê duyệt là quyết định về việc ai ký cho những khoản tiền, nên nó được cấp một cách có cân nhắc chứ không phải cứ xin là có — hãy chuẩn bị trả lời bạn cần nó để làm gì.") },
        { k: "src", v: B("Your sidebar, and the payroll approval groups.",
                         "Thanh bên của bạn, và các nhóm quyền phê duyệt lương.") },
      ],
    },
  },

  {
    id: "reject", screens: ["payruns"],
    label: B("What happens if I reject a run?", "Nếu tôi từ chối một đợt thì điều gì xảy ra?"),
    match: ["how do i reject", "reject the run", "send it back", "từ chối đợt lương", "tra lai dot luong"],
    showMe: ["pk-card-actions"],
    blocks: [
      { k: "p", v: B("The whole run returns to draft — all 48 payslips together, never one — and three things are recorded against it: who rejected it, when, and why in writing.",
                     "Cả đợt lương quay về trạng thái Nháp — toàn bộ 48 phiếu cùng lúc, không bao giờ chỉ một phiếu — và ba điều được ghi lại: ai từ chối, vào lúc nào, và vì sao, bằng văn bản.") },
      { k: "steps", v: [
        { t: B("Open the run at the gate you hold", "Mở đợt lương ở cổng bạn đang giữ"), a: "pk-tabs" },
        { t: B("Reject, and write a reason that names the payslip and what to check", "Từ chối, và viết lý do nêu rõ phiếu nào và cần kiểm tra gì"), a: "pk-card-actions" },
        { t: B("The officer corrects the input, recomputes and resubmits through the same chain", "Chuyên viên sửa dữ liệu đầu vào, tính lại và trình lại qua đúng chuỗi đó") },
      ] },
      { k: "warn", v: B("Nothing is lost and nothing was paid, but a reason like \"wrong\" costs the officer a day of guessing. The written reason is the entire value of a rejection.",
                        "Không mất gì và chưa chi gì, nhưng một lý do kiểu \"sai\" khiến chuyên viên mất cả ngày để đoán. Chính lý do bằng văn bản mới là toàn bộ giá trị của việc từ chối.") },
      { k: "src", v: B("The rejection fields on the pay run record: reason, who and when.",
                       "Các trường từ chối trên bản ghi đợt lương: lý do, người từ chối và thời điểm.") },
    ],
  },

  {
    id: "checkfinal", screens: ["runpayroll", "payruns", "payslips"],
    label: B("What should I check before finalising?", "Cần kiểm tra gì trước khi chốt?"),
    match: ["before finalising", "before finalizing", "pre approval checklist", "trước khi chốt", "kiem tra gi truoc"],
    practice: "m2",
    blocks: [
      { k: "p", v: B("The list experienced officers actually use, in the order they use it:",
                     "Danh sách mà các chuyên viên giàu kinh nghiệm thực sự dùng, theo đúng thứ tự họ dùng:") },
      { k: "steps", v: [
        { t: B("Headcount is what you expected, and joiners and leavers are accounted for", "Sĩ số đúng như kỳ vọng, và người vào mới cùng người thôi việc đã được tính đủ"), a: "pw-summary" },
        { t: B("Every flagged payslip opened and understood, not dismissed", "Mọi phiếu bị gắn cờ đã được mở và hiểu rõ, không phải bị bỏ qua"), a: "ps-chips" },
        { t: B("Total net against last month, and you can explain the variance in one sentence", "Tổng thực nhận so với tháng trước, và bạn giải thích được biến động trong một câu"), a: "ps-kpis" },
        { t: B("The statutory lines present on a sample slip: BHXH, BHYT, BHTN, thuế TNCN", "Các dòng bắt buộc có mặt trên một phiếu mẫu: BHXH, BHYT, BHTN, thuế TNCN"), a: "ps-breakdown" },
        { t: B("Bank details valid for anyone who joined this month", "Thông tin ngân hàng hợp lệ cho những người mới vào tháng này") },
      ] },
      { k: "src", v: B("The pre-approval checklist taught in the Pay Runs lesson and practised in the approval mission.",
                       "Danh sách kiểm tra trước phê duyệt được dạy trong bài Đợt tính lương và thực hành trong nhiệm vụ phê duyệt.") },
    ],
  },

  {
    id: "fixerror", screens: "*",
    label: B("How do I correct a mistake?", "Tôi sửa một sai sót thế nào?"),
    match: ["how do i fix", "correct this error", "sửa lỗi", "lam sao sua", "how to correct"],
    showMe: ["ps-breakdown", "im-cta", "iw-fixrows"],
    blocks: [
      { k: "p", v: B("The golden rule is one sentence: fix the input, never the output. A payslip is a result — correcting the result leaves the data behind it wrong, and the next recompute quietly brings the mistake back.",
                     "Nguyên tắc vàng gói trong một câu: sửa đầu vào, đừng bao giờ sửa kết quả. Phiếu lương là một kết quả — sửa kết quả sẽ để nguyên dữ liệu sai phía sau, và lần tính lại kế tiếp âm thầm mang lỗi quay lại.") },
      { k: "steps", v: [
        { t: B("Open the payslip and find the line that is wrong", "Mở phiếu lương và tìm dòng bị sai"), a: "ps-breakdown" },
        { t: B("Trace it back to the input that produced it — attendance, overtime or the contract", "Truy ngược về dữ liệu đầu vào đã tạo ra nó — chấm công, tăng ca hoặc hợp đồng") },
        { t: B("Correct the input, through a new import or on the employee record", "Sửa đầu vào, bằng một đợt nhập mới hoặc trên hồ sơ nhân viên"), a: "im-cta" },
        { t: B("Recompute the draft — every dependent line corrects itself", "Tính lại bản nháp — mọi dòng phụ thuộc tự đúng theo"), a: "pw-compute" },
      ] },
      { k: "warn", v: B("If the run is already done, do not reopen it. The month has been reported from; use a retro adjustment so the correction lands in the current run with the source period on record.",
                        "Nếu đợt đã Hoàn tất, đừng mở lại. Kỳ đó đã được dùng để báo cáo; hãy dùng điều chỉnh hồi tố để phần sửa rơi vào kỳ hiện tại kèm kỳ gốc được ghi nhận.") },
      { k: "src", v: B("The draft lifecycle on a pay run, and the retro adjustment ledger.",
                       "Vòng đời bản nháp của một đợt lương, và sổ điều chỉnh hồi tố.") },
    ],
  },

  {
    id: "affectrun", screens: ["runpayroll", "import", "importwizard"],
    label: B("Will this affect a run that is already submitted?", "Việc này có ảnh hưởng đợt đã trình duyệt không?"),
    match: ["affect the current run", "will this change", "ảnh hưởng đợt đang chạy", "co anh huong dot da trinh"],
    blocks: [
      { k: "ok", v: B("No. What you do here reaches drafts only — the division and period you are working on. A run that has been submitted or approved cannot be touched from here at all.",
                      "Không. Những gì bạn làm ở đây chỉ chạm tới bản nháp — đúng bộ phận và kỳ bạn đang làm. Một đợt đã trình hoặc đã duyệt thì hoàn toàn không thể bị tác động từ đây.") },
      { k: "p", v: B("Safe: recomputing a draft, deleting a draft, importing again into an open period. Gated: everything after submission, which moves only through the approval chain or a rejection back to draft.",
                     "An toàn: tính lại bản nháp, xoá bản nháp, nhập lại vào một kỳ còn mở. Có cổng chặn: mọi thứ sau khi đã trình, chỉ đi được qua chuỗi phê duyệt hoặc bị từ chối để quay về Nháp.") },
      { k: "src", v: B("The pay run state chain, and what each state allows.",
                       "Chuỗi trạng thái của đợt lương, và mỗi trạng thái cho phép làm gì.") },
    ],
  },

  {
    id: "confidence", screens: ["import", "importwizard"],
    label: B("What does the confidence score mean?", "Điểm tin cậy nghĩa là gì?"),
    match: ["confidence score", "what does the score mean", "diem tin cay", "điểm tin cậy là gì", "import score"],
    showMe: ["iw-review"],
    simpler: B("It is not a mark out of a hundred. It is simply how much of your file the system could read without having to guess — so 96% of fifty rows still means two rows it could not place, and each of those is one person's pay.",
               "Đây không phải điểm trên thang một trăm. Nó chỉ đơn giản là phần dữ liệu trong tệp mà hệ thống đọc được mà không phải đoán — nên 96% của năm mươi dòng vẫn nghĩa là còn hai dòng nó không xếp được, và mỗi dòng đó là lương của một con người."),
    blocks: [
      { k: "p", v: B("It is the share of rows the importer matched to an employee and read without ambiguity — 46 of 48 here. It is not a grade and there is no pass mark, because the number that matters is the count underneath it: 95.8% of 48 rows still leaves two rows a human has to resolve.",
                     "Đó là tỷ lệ dòng mà trình nhập liệu khớp được với một nhân viên và đọc được không nhập nhằng — ở đây là 46 trên 48. Nó không phải điểm số và không có mức đạt, vì con số quan trọng là số lượng bên dưới nó: 95,8% của 48 dòng vẫn còn hai dòng phải có người xử lý.") },
      { k: "warn", v: B("Committing with rows unresolved does not lose them quietly — it produces payslips that are missing or wrong, and those are found by the employees rather than by you.",
                        "Ghi nhận khi còn dòng chưa xử lý không làm chúng biến mất êm thấm — nó tạo ra những phiếu lương thiếu hoặc sai, và người phát hiện sẽ là nhân viên chứ không phải bạn.") },
      { k: "p", v: B("Three ways to resolve a row: Match points it at the right employee, Retry re-reads it after you correct the file, Skip drops it. Skip is right for a duplicate row and quietly wrong for a person, because a skipped employee is simply absent from the run.",
                     "Ba cách xử lý một dòng: Khớp trỏ nó tới đúng nhân viên, Thử lại đọc lại sau khi bạn sửa tệp, Bỏ qua loại nó ra. Bỏ qua đúng với một dòng bị lặp và sai một cách âm thầm với một con người, vì nhân viên bị bỏ qua đơn giản là vắng mặt trong đợt lương.") },
      { k: "src", v: B("The import wizard's review step and its validation counts.",
                       "Bước soát xét của trình nhập liệu và các số liệu kiểm tra của nó.") },
    ],
  },

  {
    /* Also answers on the statutory screens, where the 8% is a cell in a table
       rather than a line on a slip. Same fact, two surfaces — and the reader
       who asks "explain BHXH" while looking at the policy deserves the worked
       example, not a definition. */
    id: "bhxh", screens: ["payslips", "runpayroll", "statutory"],
    label: B("Explain BHXH on this payslip", "Giải thích BHXH trên phiếu lương này"),
    match: ["what is bhxh", "explain bhxh", "social insurance", "bao hiem xa hoi", "bảo hiểm xã hội"],
    showMe: ["ps-breakdown"],
    simpler: B("Think of BHXH as a shared fund the law requires. Every month you put in 8% of the salary written in your contract — not your bonuses and not your overtime — and your company puts in more than double that on top. It pays for pensions, sick leave and maternity leave.",
               "Hãy hình dung BHXH như một quỹ chung mà pháp luật yêu cầu. Mỗi tháng bạn đóng 8% mức lương ghi trong hợp đồng — không tính thưởng, không tính tăng ca — và công ty đóng thêm hơn gấp đôi phần đó. Quỹ này chi trả lương hưu, ốm đau và thai sản."),
    blocks: [
      { k: "p", v: B("BHXH is social insurance. On Mai's July payslip the employee share is 8% of the registered insurance base of 12,000,000 ₫, which is 960,000 ₫ and is deducted. Her employer pays a further 17.5% — a company cost that never appears in her net.",
                     "BHXH là bảo hiểm xã hội. Trên phiếu tháng 7 của Mai, phần người lao động là 8% của mức lương đóng bảo hiểm đã đăng ký 12.000.000 ₫, tức 960.000 ₫ và được khấu trừ. Doanh nghiệp đóng thêm 17,5% — chi phí công ty, không bao giờ xuất hiện trong thực nhận của cô ấy.") },
      { k: "calc" },
      { k: "p", v: B("The base is the point. It is the salary registered on the contract, not what was earned this month, which is why a month with 1,500,000 ₫ of overtime produces exactly the same BHXH as a month without any.",
                     "Mấu chốt nằm ở mức đóng. Đó là mức lương đã đăng ký theo hợp đồng, không phải số kiếm được trong tháng, nên một tháng có 1.500.000 ₫ tăng ca vẫn cho ra đúng khoản BHXH như tháng không có đồng tăng ca nào.") },
      { k: "src", v: B("Mai's July payslip, and the BHXH line on the statutory policy.",
                       "Phiếu lương tháng 7 của Mai, và dòng BHXH trên chính sách bảo hiểm.") },
    ],
  },

  {
    id: "prorata", screens: ["proration", "payslips", "fullfinal"],
    label: B("How was this part-month salary worked out?", "Lương tháng lẻ ngày này được tính ra sao?"),
    match: ["prorated", "part month", "joined mid month", "tinh theo ngay cong", "ngày công lẻ"],
    showMe: ["lg-rows"],
    blocks: [
      { k: "p", v: B("Days worked over the division's standard working days, and the base multiplied by the factor that produces. For someone who left on the 15th: 11 days out of 22 gives a factor of 0.50, so a 10,500,000 ₫ base becomes 5,250,000 ₫.",
                     "Số ngày công thực tế chia cho ngày công chuẩn của bộ phận, rồi lấy lương cơ bản nhân với hệ số đó. Với người nghỉ ngày 15: 11 ngày trên 22 cho hệ số 0,50, nên lương cơ bản 10.500.000 ₫ thành 5.250.000 ₫.") },
      { k: "warn", v: B("The standard is {{standardWorkingDays}} working days, from the division's configuration — not calendar days. Reading it as calendar days is the mistake that turns an explanation into an argument.",
                        "Chuẩn là {{standardWorkingDays}} ngày công theo cấu hình của bộ phận — không phải ngày dương lịch. Hiểu nhầm thành ngày dương lịch là sai sót biến một lời giải thích thành một cuộc tranh cãi.") },
      { k: "p", v: B("Read the factor before the money. If the factor is right and the amount still looks wrong, the problem is upstream — in the contract base or in the attendance that was imported.",
                     "Hãy đọc hệ số trước khi đọc số tiền. Nếu hệ số đúng mà số tiền vẫn có vẻ sai thì vấn đề nằm ở phía trên — ở lương cơ bản trên hợp đồng hoặc ở dữ liệu chấm công đã nhập.") },
      { k: "src", v: B("The proration audit rows for this run, and the division's standard working days.",
                       "Các dòng soát xét ngày công của đợt lương này, và ngày công chuẩn của bộ phận.") },
    ],
  },

  {
    id: "retroq", screens: ["retro", "payruns"],
    label: B("When do I use a retro adjustment?", "Khi nào tôi dùng điều chỉnh hồi tố?"),
    match: ["retro", "backdated", "hồi tố", "tang luong lui ngay", "correct a closed month"],
    showMe: ["lg-rows"],
    blocks: [
      { k: "p", v: B("When the run the correction belongs to is already done. A retro line pays the difference in the current run and records which period it came from, so the closed month stays closed and still reports correctly.",
                     "Khi đợt lương mà phần sửa thuộc về đã Hoàn tất. Một dòng hồi tố chi phần chênh trong kỳ hiện tại và ghi rõ nó đến từ kỳ nào, để kỳ đã đóng vẫn luôn đóng mà báo cáo vẫn đúng.") },
      { k: "p", v: B("If the run is still in draft, do not use retro at all — fix the input and recompute. Retro is for the past you cannot reopen, not for the present you have not finished.",
                     "Nếu đợt còn ở trạng thái Nháp thì đừng dùng hồi tố — hãy sửa đầu vào và tính lại. Hồi tố dành cho quá khứ bạn không mở lại được, không dành cho hiện tại bạn chưa làm xong.") },
      { k: "warn", v: B("Editing an approved payslip instead of writing a retro line changes a number somebody has already filed. That is not a payroll correction, it is a reporting problem.",
                        "Sửa một phiếu lương đã duyệt thay vì viết một dòng hồi tố là thay đổi một con số mà người khác đã nộp đi. Đó không phải hiệu chỉnh lương, đó là một vấn đề báo cáo.") },
      { k: "src", v: B("The retro adjustment ledger, with the source period recorded on each line.",
                       "Sổ điều chỉnh hồi tố, mỗi dòng có ghi kỳ gốc.") },
    ],
  },

  {
    id: "practice", screens: "*",
    label: B("Let me practise this safely", "Cho tôi thực hành an toàn"),
    match: ["let me practise", "let me practice", "thực hành", "lam thu", "try it safely"],
    practice: "m1",
    blocks: [
      { k: "p", v: B("Good instinct. The practice missions run on a fictional 48-person company — not {{companyDisplayName}} — with no server behind it, so nothing you do can reach a real employee, payslip or pay run. Three are playable: computing a run, reviewing one at an approval gate, and applying a statutory rate change.",
                     "Bản năng tốt. Các nhiệm vụ thực hành chạy trên một công ty giả lập 48 người — không phải {{companyDisplayName}} — và không có máy chủ phía sau, nên mọi thao tác đều không chạm tới nhân viên, phiếu lương hay đợt lương thật. Ba nhiệm vụ chơi được: tính một đợt lương, soát xét một đợt ở cổng phê duyệt, và áp dụng một thay đổi tỷ lệ luật định.") },
      { k: "ok", v: B("You can fail safely there. The seeded anomaly is always present, so the judgement it teaches is the same one every time — and getting it wrong costs a recovery message rather than a salary.",
                      "Bạn được phép sai ở đó. Điểm bất thường được cài sẵn luôn có mặt, nên phán đoán mà nó dạy luôn là một, và làm sai chỉ tốn một lời gợi ý quay lại chứ không tốn một khoản lương.") },
      { k: "src", v: B("The practice missions in the Journey.",
                       "Các nhiệm vụ thực hành trong Hành trình học.") },
    ],
  },

  {
    id: "compliance", screens: "*", offer: false,
    label: B("Can Payobook reduce what we owe?", "Payobook có giảm được số phải đóng không?"),
    match: ["how do we pay less", "reduce contributions", "cach dong it hon", "giảm số phải nộp"],
    blocks: [
      { k: "refusal", v: B("I will not help reduce a statutory obligation. Payobook computes what the configured rates and the declared insurance base produce — it does not look for a smaller answer, and neither will I.",
                           "Tôi sẽ không giúp làm giảm một nghĩa vụ luật định. Payobook tính ra đúng những gì các tỷ lệ đã cấu hình và mức lương đóng bảo hiểm đã đăng ký tạo ra — nó không đi tìm một đáp số nhỏ hơn, và tôi cũng vậy.") },
      { k: "who", v: B("Your company's payroll policy owner decides the declared insurance base and the allowance structure. A change to either is a legal decision with consequences well beyond payroll, not a software setting.",
                       "Người phụ trách chính sách lương của công ty bạn quyết định mức lương đóng bảo hiểm đã đăng ký và cấu trúc phụ cấp. Thay đổi một trong hai là quyết định pháp lý với hệ quả vượt xa phạm vi tính lương, không phải một thiết lập phần mềm.") },
      { k: "how", v: B("What I can show you is where the numbers come from: the BHXH, BHYT and BHTN rates and the thuế TNCN table, and the per-division formula configuration that decides which of them apply to whom. If a figure looks wrong, that is where to look — a wrong figure is worth finding, and a smaller one is not the same thing.",
                       "Điều tôi có thể chỉ cho bạn là các con số đến từ đâu: tỷ lệ BHXH, BHYT, BHTN và biểu thuế TNCN, cùng cấu hình công thức theo từng bộ phận quyết định tỷ lệ nào áp cho ai. Nếu một con số trông sai, đó là nơi cần xem — tìm ra một con số sai là việc đáng làm, còn tìm một con số nhỏ hơn thì không phải cùng một việc.") },
      { k: "src", v: B("The statutory rates and the division's formula configuration.",
                       "Các tỷ lệ luật định và cấu hình công thức của bộ phận.") },
    ],
  },

  /* ===========================================================================
     SETUP INTENTS.

     Appended rather than interleaved: the generator writes records in this
     order, so inserting into the middle would rewrite every intent id after the
     insertion point for no content reason.
     ======================================================================== */
  {
    id: "whysetup", screens: ["formula", "structures", "statutory", "integrations"],
    dynamic: "screenCtx",
    label: B("Why do I have to set this up?", "Vì sao tôi phải thiết lập cái này?"),
    match: ["why do i need to configure", "why does setup exist", "what is setup for",
            "tai sao phai cau hinh", "vì sao phải thiết lập", "cau hinh de lam gi"],
    blocks: [
      { k: "p", v: B("Because a payroll system that decides anything for you is a payroll system you cannot defend. Every number on a payslip comes from something written down here: a component in a formula configuration, a rate on a statutory policy, a field mapped from a connected system.",
                     "Vì một hệ thống tính lương tự quyết thay bạn là hệ thống bạn không bảo vệ được. Mọi con số trên phiếu lương đều đến từ một thứ đã được ghi lại ở đây: một thành phần trong cấu hình công thức, một tỷ lệ trên chính sách bảo hiểm, một trường được ánh xạ từ hệ thống đã kết nối.") },
      { k: "steps", v: [
        { t: B("Formula Engine — how each line is computed, for one division", "Công thức lương — mỗi dòng được tính thế nào, cho một bộ phận"), a: "fs-components" },
        { t: B("Statutory — the rates the law sets, for the whole company", "Bảo hiểm & Thuế — các tỷ lệ do luật định, cho cả công ty"), a: "st-rates" },
        { t: B("Integrations — how the inputs arrive without anybody retyping them", "Tích hợp — dữ liệu đầu vào về tới nơi mà không ai phải gõ lại"), a: "ig-roster" },
      ] },
      { k: "ok", v: B("Setup is done rarely and read often. Most of the time you are here to answer a question, not to change anything — and reading is always safe.",
                      "Thiết lập ít khi phải sửa nhưng thường xuyên phải đọc. Phần lớn thời gian bạn tới đây để trả lời một câu hỏi, không phải để thay đổi gì — và đọc thì luôn an toàn.") },
      { k: "src", v: B("The Setup section of the sidebar: formula configurations, statutory policies and connectors.",
                       "Phần Thiết lập trên thanh bên: cấu hình công thức, chính sách bảo hiểm và các đầu nối.") },
    ],
  },

  {
    id: "changerate", screens: ["statutory"],
    label: B("What happens if I change this rate?", "Nếu tôi đổi tỷ lệ này thì sao?"),
    match: ["what happens if i change this rate", "change a contribution rate", "edit the rate",
            "doi ty le", "đổi tỷ lệ đóng", "sua ty le bao hiem"],
    showMe: ["st-new"],
    practice: "m4",
    blocks: [
      { k: "p", v: B("On its own — <b>nothing</b>. This record is what the company DECLARES: it is read by this cockpit, by the contribution analytics and by the statutory reports, and by nothing that computes pay. The rate that prices a payslip is a parameter on each division's <b>formula configuration</b>, and changing one does not change the other.",
                     "Tự nó thì — <b>không gì cả</b>. Bản ghi này là mức doanh nghiệp KHAI BÁO: nó được màn hình này, phần phân tích chi phí bảo hiểm và các báo cáo bắt buộc đọc vào, còn những thứ tính ra tiền lương thì không. Tỷ lệ tính ra tiền trên phiếu lương là một tham số trong <b>cấu hình công thức</b> của từng bộ phận, và sửa bên này không làm đổi bên kia.") },
      { k: "ok", v: B("That is deliberate, and it is worth saying out loud: pay does not move because a reference table moved. It moves when somebody edits a configuration — an edit that can be previewed, simulated and pointed at afterwards.",
                      "Đó là chủ ý, và rất đáng nói rõ: tiền lương không thay đổi chỉ vì một bảng tham chiếu thay đổi. Nó thay đổi khi có người sửa một cấu hình — một lần sửa có thể xem trước, mô phỏng và truy lại được về sau.") },
      { k: "steps", v: [
        { t: B("Create a NEW insurance policy record, with its own code", "Tạo một bản ghi chính sách bảo hiểm MỚI, với mã riêng"), a: "st-new" },
        { t: B("Date it from the day the decree applies — this field is the legal record, not a switch", "Đặt ngày theo ngày nghị định áp dụng — ô này là ghi nhận pháp lý, không phải một cái công tắc"), a: "st-newpolicy-date" },
        { t: B("Know that this screen shows the new rates the moment you save, so tell anyone reviewing an open run", "Biết rằng màn hình này hiển thị tỷ lệ mới ngay khi bạn lưu, nên hãy báo cho ai đang soát xét một đợt còn mở"), a: "st-rates" },
        { t: B("Change the rate parameter on every affected formula configuration, and simulate before activating", "Sửa tham số tỷ lệ trên mọi cấu hình công thức bị ảnh hưởng, và mô phỏng trước khi kích hoạt"), a: "fs-components" },
      ] },
      { k: "warn", v: B("Do not edit the policy that is in force. There is no version history to fall back on — the old declared rate is simply gone, and with it the evidence of what the company was declaring while last month was paid.",
                        "Đừng sửa chính sách đang có hiệu lực. Không có lịch sử phiên bản nào để quay lại — mức đã khai báo trước đó đơn giản là mất, và mất theo cả bằng chứng về mức mà doanh nghiệp đang khai báo khi tháng trước được trả lương.") },
      { k: "src", v: B("The insurance policy record, and the rate parameters on the division's formula configuration.",
                       "Bản ghi chính sách bảo hiểm, và các tham số tỷ lệ trên cấu hình công thức của bộ phận.") },
    ],
  },

  {
    id: "whichpolicy", screens: ["statutory", "payslips"],
    label: B("Which policy applies today?", "Hôm nay chính sách nào đang áp dụng?"),
    match: ["which policy is in force", "which rates apply now", "current policy",
            "chinh sach nao dang ap dung", "chính sách nào đang hiệu lực", "ty le hien hanh"],
    showMe: ["st-rates", "st-roster"],
    blocks: [
      { k: "p", v: B("The one with the <b>latest effective date</b> among the policies that are still active. Two things it does NOT do, and both surprise people: it does not compare that date to today, so a policy dated from next month is displayed as soon as it is saved; and it does not read the end date at all.",
                     "Bản có <b>ngày hiệu lực mới nhất</b> trong số các chính sách còn đang bật. Có hai điều nó KHÔNG làm, và cả hai đều khiến người ta bất ngờ: nó không so ngày đó với hôm nay, nên một chính sách ghi hiệu lực từ tháng sau sẽ hiển thị ngay khi vừa lưu; và nó hoàn toàn không đọc ngày kết thúc.") },
      { k: "p", v: B("The rates table at the top of this screen always shows that policy, with its effective date beside the heading. The roster below shows all of them, so a change reads as a history: one record ended, the next one starting.",
                     "Bảng tỷ lệ ở đầu màn hình này luôn hiển thị đúng chính sách đó, kèm ngày hiệu lực ngay cạnh tiêu đề. Danh sách bên dưới hiển thị tất cả, nên một thay đổi đọc ra như một lịch sử: bản này kết thúc, bản kế tiếp bắt đầu."),
      },
      /* LIVE SITE 2 of 2. The one place the Coach quotes a rate it did not
         author: the employee / employer split on the policy THIS company has
         in force, read at answer time by the same latest-effective-active rule
         the cockpit applies. If the read fails, or there is no policy, the
         fallback below is shown whole — the Coach's standing promise is that
         it never invents a rate, and half a sentence about one is an invention
         with a gap in it. */
      { k: "p",
        v: B("On this company right now, employee / employer: {{live:active_policy_rates}}. Read straight off the policy in force — if that is not what you expected, the roster below will show you which record is being applied.",
             "Trên công ty này ngay lúc này, người lao động / doanh nghiệp: {{live:active_policy_rates}}. Đọc trực tiếp từ chính sách đang hiệu lực — nếu con số khác với bạn nghĩ, danh sách bên dưới sẽ cho thấy bản ghi nào đang được áp dụng."),
        liveFallback: B("Open the rates table above to read the split that is in force here. Every figure the Coach quotes about contributions comes off that record, never from memory.",
                        "Hãy mở bảng tỷ lệ ở trên để đọc mức đóng đang hiệu lực tại đây. Mọi con số về bảo hiểm mà trợ lý đưa ra đều lấy từ bản ghi đó, không bao giờ theo trí nhớ."),
      },
      { k: "warn", v: B("Whichever policy is displayed, it is a DECLARATION. It is not what priced the payslips you are looking at — that came from the rate parameters on each division's formula configuration. If the two disagree, the payslips are not wrong; the declaration and the configuration are simply out of step, and somebody has to decide which one is behind.",
                        "Dù bản nào đang hiển thị thì đó cũng là một BẢN KHAI BÁO. Nó không phải thứ đã tính ra các phiếu lương bạn đang xem — những phiếu đó đến từ các tham số tỷ lệ trên cấu hình công thức của từng bộ phận. Nếu hai bên lệch nhau thì phiếu lương không sai; chỉ là bản khai báo và cấu hình đang không đồng bộ, và phải có người quyết định bên nào đang chậm.") },
      { k: "src", v: B("The active insurance policies, ordered by effective date.",
                       "Các chính sách bảo hiểm đang bật, sắp theo ngày hiệu lực.") },
    ],
  },

  {
    id: "ceiling", screens: ["statutory", "payslips"],
    label: B("What is the insurance base and the ceiling?", "Mức đóng bảo hiểm và trần đóng là gì?"),
    match: ["what is the insurance base", "contribution ceiling", "capped at",
            "muc dong bao hiem", "trần đóng", "tran bao hiem"],
    showMe: ["st-rates"],
    simpler: B("Insurance is not worked out from what you earned this month. It is worked out from the salary written in your contract, and only up to a limit — so a busy month with a lot of overtime does not change it, and a very high salary stops adding to it after a point.",
               "Bảo hiểm không tính từ số bạn kiếm được trong tháng. Nó tính từ mức lương ghi trong hợp đồng, và chỉ tính tới một mức giới hạn — nên một tháng bận rộn nhiều tăng ca không làm nó thay đổi, và lương rất cao thì qua một ngưỡng cũng không làm nó tăng thêm."),
    blocks: [
      { k: "p", v: B("Contributions are charged on the <b>registered insurance base</b> — normally the contract base salary. For Mai that is 12,000,000 ₫, not her gross of 14,280,000 ₫, which is why her 1,500,000 ₫ of overtime moved her tax and not a đồng of her insurance.",
                     "Bảo hiểm tính trên <b>mức lương đóng bảo hiểm đã đăng ký</b> — thường là lương cơ bản theo hợp đồng. Với Mai là 12.000.000 ₫, không phải tổng thu nhập 14.280.000 ₫, nên 1.500.000 ₫ tăng ca của cô ấy làm thay đổi thuế mà không làm thay đổi một đồng bảo hiểm nào.") },
      { k: "calc" },
      { k: "p", v: B("Each scheme also carries a <b>ceiling</b> in the last column of the rates table — the maximum base it is charged on. Above it the deduction stops growing, so two employees on very different salaries can pay exactly the same BHXH.",
                     "Mỗi loại bảo hiểm còn có một <b>mức trần</b> ở cột cuối của bảng tỷ lệ — mức đóng tối đa mà nó được tính trên đó. Vượt mức này thì khoản khấu trừ không tăng nữa, nên hai nhân viên lương rất khác nhau vẫn có thể đóng BHXH bằng nhau.") },
      { k: "src", v: B("The active insurance policy's rates and ceilings, and Mai's July payslip.",
                       "Tỷ lệ và trần đóng của chính sách bảo hiểm đang hiệu lực, và phiếu lương tháng 7 của Mai.") },
    ],
  },

  {
    id: "pitcalc", screens: ["statutory", "payslips"],
    label: B("How is thuế TNCN worked out?", "Thuế TNCN được tính thế nào?"),
    match: ["how is pit calculated", "personal income tax calculation", "tax brackets",
            "thue tncn tinh the nao", "cách tính thuế thu nhập", "giam tru gia canh"],
    showMe: ["st-slabs", "ps-breakdown"],
    simpler: B("First take off the insurance. Then take off a fixed allowance for yourself, and another for each person who depends on you. Whatever is left is what gets taxed — and the rate starts low and only rises on the part above each band.",
               "Trước hết trừ bảo hiểm. Rồi trừ một khoản cố định cho bản thân, và thêm một khoản nữa cho mỗi người phụ thuộc. Phần còn lại mới là phần chịu thuế — và thuế suất bắt đầu ở mức thấp, chỉ tăng lên với phần vượt qua từng bậc."),
    blocks: [
      { k: "p", v: B("Taxable income is gross, less insurance, less <b>11,000,000 ₫</b> personal relief and <b>4,400,000 ₫</b> for each dependant. Only what is left goes into the bands, and the bands are progressive: the first 5,000,000 ₫ is taxed at 5%, and each higher band applies only to the part inside it.",
                     "Thu nhập chịu thuế là tổng thu nhập, trừ bảo hiểm, trừ <b>11.000.000 ₫</b> giảm trừ bản thân và <b>4.400.000 ₫</b> cho mỗi người phụ thuộc. Chỉ phần còn lại mới đi vào biểu thuế, và biểu thuế là luỹ tiến: 5.000.000 ₫ đầu tiên chịu 5%, và mỗi bậc cao hơn chỉ áp cho phần nằm trong bậc đó.") },
      { k: "p", v: B("Mai's July: 14,280,000 − 1,260,000 insurance − 11,000,000 relief = <b>2,020,000 ₫</b> taxable, entirely inside the 5% band, so her tax is <b>101,000 ₫</b>. A dependant would take another 4,400,000 ₫ off and leave her paying almost nothing.",
                     "Tháng 7 của Mai: 14.280.000 − 1.260.000 bảo hiểm − 11.000.000 giảm trừ = <b>2.020.000 ₫</b> chịu thuế, nằm trọn trong bậc 5%, nên thuế là <b>101.000 ₫</b>. Thêm một người phụ thuộc sẽ trừ tiếp 4.400.000 ₫ và cô ấy gần như không phải nộp gì.") },
      { k: "warn", v: B("Dependants are registered, not assumed. A relief that was never registered is a tax bill the employee did not need to pay, and it is the single most common thing an employee is owed and never asks for.",
                        "Người phụ thuộc phải được đăng ký, không mặc định có. Một khoản giảm trừ chưa từng đăng ký là một khoản thuế mà nhân viên lẽ ra không phải nộp, và đây là thứ nhân viên bị thiệt phổ biến nhất mà lại chẳng mấy ai hỏi tới.") },
      { k: "src", v: B("The active tax table: its bands, its personal deduction and its dependant deduction.",
                       "Biểu thuế đang hiệu lực: các bậc, mức giảm trừ bản thân và mức giảm trừ người phụ thuộc.") },
    ],
  },

  {
    id: "configvsstructure", screens: ["formula", "structures"],
    label: B("Formula configuration or salary structure?", "Cấu hình công thức hay cấu trúc lương?"),
    match: ["difference between structure and config", "which one do i use", "legacy structures",
            "cau truc luong khac gi", "khác nhau cấu trúc và cấu hình", "dung cai nao"],
    showMe: ["fs-components", "sr-roster"],
    blocks: [
      { k: "p", v: B("A <b>formula configuration</b> is where pay logic lives now: named components, readable formulas, a live preview and a simulation. A <b>salary structure</b> is the older mechanism, and it is kept for one reason — payslips produced before the migration still point at it.",
                     "<b>Cấu hình công thức</b> là nơi logic lương nằm ở hiện tại: các thành phần có tên, công thức đọc được, xem trước trực tiếp và mô phỏng. <b>Cấu trúc lương</b> là cơ chế thế hệ trước, và được giữ lại vì đúng một lý do — phiếu lương tạo trước khi chuyển đổi vẫn trỏ tới nó.") },
      { k: "ok", v: B("New logic goes in a configuration, always. Run Payroll selects a configuration when you choose a division, so a rule added to a structure is a rule the division never sees.",
                      "Logic mới luôn đặt trong một cấu hình. Chạy bảng lương chọn một cấu hình khi bạn chọn bộ phận, nên một quy tắc thêm vào cấu trúc là quy tắc mà bộ phận đó không bao giờ nhìn thấy.") },
      { k: "warn", v: B("Do not delete a structure that shows zero employees. Zero means nobody is paid by it today, not that nothing references it — payslips from three years ago still do, and a report over those months needs it.",
                        "Đừng xoá một cấu trúc đang hiện số nhân viên bằng không. Bằng không nghĩa là hôm nay không ai được trả theo nó, chứ không phải không gì tham chiếu tới nó — phiếu lương ba năm trước vẫn tham chiếu, và một báo cáo trên các tháng đó vẫn cần nó.") },
      { k: "src", v: B("The division's formula configuration, and the salary structures kept for historical payslips.",
                       "Cấu hình công thức của bộ phận, và các cấu trúc lương giữ lại cho phiếu lương lịch sử.") },
    ],
  },

  {
    id: "editlive", screens: ["formula"],
    label: B("Is it safe to edit a live configuration?", "Sửa một cấu hình đang chạy có an toàn không?"),
    match: ["can i edit this config", "is it safe to change the formula", "edit a live configuration",
            "sua cau hinh dang chay", "sửa công thức đang dùng", "co an toan khong"],
    showMe: ["fs-deps", "fs-simulate"],
    practice: "m5",
    blocks: [
      { k: "p", v: B("It is allowed, and it reaches further than it looks: every payslip computed by this configuration from now on, for the whole division — and any run still in draft that gets recomputed, including one for a month you thought was finished with.",
                     "Được phép, và tác động xa hơn vẻ ngoài của nó: mọi phiếu lương do cấu hình này tính từ giờ trở đi, cho cả bộ phận — và bất kỳ đợt nào còn ở Nháp mà được tính lại, kể cả đợt của một tháng bạn tưởng đã xong.") },
      { k: "steps", v: [
        { t: B("Read the dependency panel for anything you are renaming or removing", "Đọc bảng phụ thuộc cho bất cứ thứ gì bạn định đổi tên hoặc xoá"), a: "fs-deps" },
        { t: B("Preview against a sample employee — the arithmetic, on one person", "Xem trước trên một nhân viên mẫu — phép tính, trên một con người"), a: "fs-preview" },
        { t: B("Simulate against last month, which is the same change across everybody", "Mô phỏng trên tháng trước, tức là cùng thay đổi đó trên tất cả mọi người"), a: "fs-simulate" },
        { t: B("Apply it once no run for an earlier period is still open", "Áp dụng khi không còn đợt nào của kỳ trước đó đang mở") },
      ] },
      { k: "warn", v: B("Renaming a component that other formulas depend on is the quiet one. The dependency panel names them; a formula that lost its input does not always fail loudly.",
                        "Đổi tên một thành phần mà công thức khác đang phụ thuộc là lỗi âm thầm nhất. Bảng phụ thuộc liệt kê chúng ra; một công thức mất đầu vào không phải lúc nào cũng báo lỗi rõ ràng.") },
      { k: "src", v: B("The configuration's dependency map, and its preview and simulation tools.",
                       "Bản đồ phụ thuộc của cấu hình, cùng các công cụ xem trước và mô phỏng của nó.") },
    ],
  },

  {
    id: "whichconfig", screens: ["formula", "runpayroll"],
    label: B("Which configuration does a division use?", "Bộ phận này dùng cấu hình nào?"),
    match: ["which config does this division use", "find the right configuration", "config code",
            "bo phan nay dung cau hinh nao", "mã cấu hình", "tim cau hinh"],
    showMe: ["fs-config", "pw-division"],
    blocks: [
      { k: "p", v: B("One per division and cycle, and the code says which: the division's name, then <b>END</b> for the end-of-month settlement or <b>MID</b> for a mid-cycle advance. On the demo world they read DEMO_RETAIL_END, DEMO_LOGISTICS_MID and so on — one naming rule, twelve configurations.",
                     "Mỗi bộ phận và mỗi chu kỳ có một cấu hình, và chính mã cho biết là cái nào: tên bộ phận, rồi <b>END</b> cho quyết toán cuối tháng hoặc <b>MID</b> cho khoản tạm ứng giữa kỳ. Trên bản demo, chúng đọc là DEMO_RETAIL_END, DEMO_LOGISTICS_MID và tương tự — một quy ước đặt tên, mười hai cấu hình.") },
      { k: "p", v: B("You do not have to look it up before running a payroll: choosing the division in Run Payroll selects the configuration, and prints its name in the scope panel. Reading that name before you compute is the check — it is also the only place the wrong-division mistake is visible.",
                     "Bạn không cần tra cứu trước khi chạy lương: chọn bộ phận trong Chạy bảng lương là đã chọn cấu hình, và tên của nó được in ở bảng phạm vi. Đọc cái tên đó trước khi tính chính là bước kiểm tra — và cũng là nơi duy nhất nhìn thấy được lỗi chọn nhầm bộ phận.") },
      { k: "src", v: B("The configuration codes on the divisions, and the scope panel in Run Payroll.",
                       "Mã cấu hình trên các bộ phận, và bảng phạm vi trong Chạy bảng lương.") },
    ],
  },

  {
    id: "syncbroken", screens: ["integrations", "import"],
    label: B("A connector has stopped syncing. What now?", "Một đầu nối đã ngừng đồng bộ. Giờ làm gì?"),
    match: ["connector not syncing", "sync failed", "integration error", "staged records",
            "dong bo loi", "đầu nối lỗi", "khong dong bo duoc"],
    showMe: ["ig-roster", "im-cta"],
    blocks: [
      { k: "p", v: B("Read the <b>last sync time</b> before the status. Connected describes the credentials; the sync time describes the data — and a connector that quietly stopped nine days ago still says connected.",
                     "Hãy đọc <b>thời điểm đồng bộ gần nhất</b> trước khi đọc trạng thái. Đã kết nối nói về thông tin đăng nhập; thời điểm đồng bộ mới nói về dữ liệu — và một đầu nối âm thầm ngừng chạy chín ngày trước vẫn hiện là đã kết nối.") },
      { k: "steps", v: [
        { t: B("Find the connector whose staged count is climbing — those rows never became inputs", "Tìm đầu nối có số bản ghi chờ đang tăng — những dòng đó chưa bao giờ thành dữ liệu đầu vào"), a: "ig-roster" },
        { t: B("Fix it at the source, or import the month's file by hand through the guided flow", "Sửa từ hệ thống nguồn, hoặc nhập tệp của tháng bằng tay qua luồng có hướng dẫn"), a: "im-cta" },
        { t: B("Check the eligible count in Run Payroll before you compute — it is the second alarm", "Kiểm tra số nhân viên đủ điều kiện trong Chạy bảng lương trước khi tính — đó là chuông báo thứ hai"), a: "pw-summary" },
      ] },
      { k: "warn", v: B("Do this before payroll week, not during it. A month of attendance sitting in staging becomes a run that computes cleanly on inputs that are three weeks old, and nothing about it looks wrong.",
                        "Hãy làm việc này trước tuần tính lương, không phải trong tuần đó. Cả một tháng chấm công nằm lại ở vùng chờ sẽ tạo ra một đợt lương tính rất sạch trên dữ liệu đã cũ ba tuần, và nhìn vào không thấy gì bất thường.") },
      { k: "src", v: B("The connector list with its sync history and staged-record counts.",
                       "Danh sách đầu nối kèm lịch sử đồng bộ và số bản ghi đang chờ.") },
    ],
  },
];

/* =============================================================================
   9. COLUMN GLOSSARY — what a tile or a chip actually counts
   -----------------------------------------------------------------------------
   Curated, not derived from ir.model.fields. Most of these are COMPUTED tiles on
   an OWL cockpit — there is no field behind them to read a help string from, and
   the fields that do exist carry Odoo's own boilerplate. A schema-driven answer
   would restate the tile's own caption back at the person who just read it.

   The Coach reaches these only when no curated intent covers the question,
   which is the right order: an intent knows the procedure, a column only knows
   the definition. Matching is deliberately narrow — the question must contain
   the label — because a loose match would answer "what is the status of this
   run" with a column definition, which is worse than missing.

   Format: [key, label, body].
   ========================================================================== */
const COLUMNS = {
  runpayroll: [
    ["eligible_employees",
     B("Eligible employees", "Nhân viên đủ điều kiện"),
     B("How many people this configuration would compute a payslip for, given the period and the division you have chosen. It is the count to read before pressing Compute: a number far below the division's headcount almost always means the month's attendance import has not been committed yet.",
       "Số người mà cấu hình này sẽ tính phiếu lương cho, với kỳ và bộ phận bạn đã chọn. Đây là con số cần đọc trước khi bấm Tính: một con số thấp hơn hẳn sĩ số của bộ phận gần như luôn nghĩa là dữ liệu chấm công của tháng chưa được ghi nhận.")],
    ["payslips",
     B("Payslips", "Phiếu lương"),
     B("How many payslip records the compute created for this run. It should match the eligible count you read beforehand; if it does not, something was excluded during the compute and is worth finding before the run moves on.",
       "Số bản ghi phiếu lương mà lần tính này đã tạo cho đợt. Con số này phải khớp với số nhân viên đủ điều kiện bạn đã đọc trước đó; nếu không khớp thì đã có gì đó bị loại ra trong quá trình tính, và rất đáng tìm ra trước khi đợt lương đi tiếp.")],
    ["computed",
     B("Computed", "Đã tính"),
     B("How many of those payslips the formula configuration was able to evaluate all the way through. A payslip that exists but did not compute has no net figure, so it would leave somebody unpaid rather than underpaid.",
       "Trong số phiếu đó, bao nhiêu phiếu được cấu hình công thức tính trọn vẹn tới cuối. Một phiếu có tồn tại nhưng chưa tính xong thì không có số thực nhận, nên sẽ khiến ai đó không được trả lương chứ không phải bị trả thiếu.")],
    ["need_review",
     B("Need review", "Cần soát xét"),
     B("How many payslips the engine flagged for a human to read — an unusual variance, a zero net, an input it could not reconcile. A flag is a question, not an error, and clearing one means understanding it rather than dismissing it.",
       "Số phiếu lương mà hệ thống gắn cờ để có người đọc — một biến động bất thường, thực nhận bằng không, hay một đầu vào nó không đối chiếu được. Cờ là câu hỏi, không phải lỗi, và xoá cờ nghĩa là đã hiểu nó chứ không phải bỏ qua nó.")],
    ["exceptions",
     B("Exceptions", "Ngoại lệ"),
     B("The list behind the Need review count, one line per payslip with the reason the engine raised it. It is where the judgement in a pay run actually lives — everything else on this screen computed itself.",
       "Danh sách phía sau con số Cần soát xét, mỗi dòng một phiếu lương kèm lý do hệ thống nêu ra. Đây mới là nơi phần phán đoán của một đợt lương thực sự nằm — mọi thứ khác trên màn hình này đã tự tính xong.")],
  ],

  payruns: [
    ["pay_runs",
     B("Pay runs", "Đợt tính lương"),
     B("How many runs exist within the date and division filters currently active. It is a scoped count, not a total: changing a chip below changes this number without anything having happened in the database.",
       "Số đợt lương tồn tại trong phạm vi bộ lọc ngày và bộ phận đang chọn. Đây là con số theo phạm vi, không phải tổng: đổi một chip bên dưới sẽ đổi con số này mà không có gì thay đổi trong dữ liệu.")],
    ["in_pipeline",
     B("In pipeline", "Đang trong quy trình"),
     B("Runs that have left draft and have not reached done — they are sitting at somebody's approval gate. It is not a count of work you owe; \"Awaiting your approval\" is that.",
       "Các đợt đã rời trạng thái Nháp và chưa đạt Hoàn tất — chúng đang chờ ở cổng phê duyệt của một người nào đó. Đây không phải số việc bạn đang nợ; \"Chờ bạn phê duyệt\" mới là con số đó.")],
    ["awaiting_your_approval",
     B("Awaiting your approval", "Chờ bạn phê duyệt"),
     B("Runs sitting at a gate that your groups let you act on. This is the only number on the band that is about you, and the one to read first every morning of payroll week — nothing here moves until you move it.",
       "Các đợt đang nằm ở cổng mà nhóm quyền của bạn cho phép xử lý. Đây là con số duy nhất trên dải này nói về bạn, và là con số cần đọc đầu tiên mỗi sáng trong tuần tính lương — không gì ở đây nhúc nhích cho tới khi bạn động vào.")],
    ["completed",
     B("Completed", "Hoàn tất"),
     B("Runs that have passed every gate. Completion is what unlocks the bank file, the journals and the payments — and it is also the point after which a correction becomes a retro line rather than an edit.",
       "Các đợt đã qua mọi cổng phê duyệt. Hoàn tất là điều mở khoá tệp chi lương, bút toán và các khoản thanh toán — và cũng là mốc mà sau đó mọi hiệu chỉnh trở thành một dòng hồi tố chứ không còn là sửa trực tiếp.")],
    ["net_paid",
     B("Net paid", "Đã chi"),
     B("The total net of completed runs inside the current filters. Runs still in the pipeline are deliberately excluded: this is money that has passed every gate, not money that is expected to.",
       "Tổng thực nhận của các đợt đã Hoàn tất trong phạm vi bộ lọc hiện tại. Các đợt còn trong quy trình bị loại ra một cách có chủ ý: đây là tiền đã qua mọi cổng, không phải tiền dự kiến sẽ qua.")],
  ],

  payslips: [
    ["payslips",
     B("Payslips", "Phiếu lương"),
     B("How many payslips this run contains, before any filter chip is applied. If it is not the headcount you expected, the problem is in the run rather than on this screen.",
       "Số phiếu lương mà đợt này chứa, trước khi áp bất kỳ chip lọc nào. Nếu nó không đúng sĩ số bạn kỳ vọng thì vấn đề nằm ở đợt lương chứ không phải ở màn hình này.")],
    ["net_total",
     B("Net total", "Tổng thực nhận"),
     B("The sum of every net figure in this run — what will actually leave the bank account. Compare it with last month before approving: a variance you cannot explain in one sentence is a variance you have not checked.",
       "Tổng của mọi số thực nhận trong đợt này — số tiền thực sự sẽ rời tài khoản ngân hàng. Hãy so với tháng trước trước khi phê duyệt: một biến động bạn không giải thích được trong một câu là biến động bạn chưa kiểm tra.")],
    ["gross_total",
     B("Gross total", "Tổng thu nhập"),
     B("The sum of earnings before any deduction — base, allowances and overtime added together across the run. The gap between this and the net total is the statutory deductions plus tax, and that gap should move roughly in step with headcount.",
       "Tổng thu nhập trước mọi khoản khấu trừ — lương cơ bản, phụ cấp và tăng ca cộng lại trên toàn đợt. Khoảng cách giữa con số này và tổng thực nhận là các khoản bắt buộc cộng thuế, và khoảng cách đó nên biến động tương ứng với sĩ số.")],
    ["approved",
     B("Approved", "Đã duyệt"),
     B("How many payslips in this run have reached the done stage, against the total. A payslip carries its own position in the chain, which is not always the run's — that difference shows up here when one slip has been held back for a question.",
       "Bao nhiêu phiếu trong đợt này đã đạt trạng thái Hoàn tất, trên tổng số. Mỗi phiếu mang vị trí riêng của nó trong chuỗi, không phải lúc nào cũng trùng với vị trí của cả đợt — khác biệt đó hiện ra ở đây khi một phiếu bị giữ lại để hỏi.")],
    ["need_review",
     B("Need review", "Cần soát xét"),
     B("Payslips the engine flagged for a human to read — an unusual variance, a zero net, an input it could not reconcile. A flag is a question, not an error, and clearing one means understanding it rather than dismissing it.",
       "Các phiếu lương mà hệ thống gắn cờ để có người đọc — một biến động bất thường, thực nhận bằng không, hay một đầu vào nó không đối chiếu được. Cờ là câu hỏi, không phải lỗi, và xoá cờ nghĩa là đã hiểu nó chứ không phải bỏ qua nó.")],
  ],

  import: [
    ["import_batches",
     B("Import batches", "Đợt nhập liệu"),
     B("Every batch ever started, whatever became of it. A batch is a file or a connector pull with a period attached — it is the unit you go back to when something in a month looks wrong.",
       "Mọi đợt nhập từng được bắt đầu, bất kể kết quả ra sao. Một đợt nhập là một tệp hoặc một lần kéo dữ liệu từ đầu nối, có gắn kỳ lương — đây là đơn vị bạn quay lại khi có gì đó trong một tháng trông sai.")],
    ["completed",
     B("Completed", "Hoàn tất"),
     B("Batches that reached commit. Only these have written anything: a batch that stopped earlier changed nothing at all, which is the whole design of the guided flow.",
       "Các đợt đã tới bước ghi nhận. Chỉ những đợt này mới thực sự ghi dữ liệu: đợt dừng sớm hơn thì chưa thay đổi gì cả, và đó chính là toàn bộ thiết kế của luồng có hướng dẫn.")],
    ["in_progress",
     B("In progress", "Đang xử lý"),
     B("Batches that have been loaded but not committed. They are safe to leave — nothing is written — but a batch left here on the day of the run is a month of inputs that never arrived.",
       "Các đợt đã nạp nhưng chưa ghi nhận. Để đó thì an toàn — chưa ghi gì cả — nhưng một đợt còn nằm đây vào đúng ngày chạy lương là một tháng dữ liệu đầu vào không bao giờ tới nơi.")],
    ["with_errors",
     B("With errors", "Có lỗi"),
     B("Batches holding at least one row the importer could not place. Each of those rows is a person: unresolved, they become a payslip that is missing or computed on the wrong figure.",
       "Các đợt còn ít nhất một dòng mà trình nhập liệu không xếp được. Mỗi dòng đó là một con người: nếu không xử lý, chúng thành một phiếu lương bị thiếu hoặc bị tính trên con số sai.")],
    ["connectors",
     B("Connectors", "Đầu nối"),
     B("Configured links to a source system that can pull data without anybody retyping it. A connector that has quietly stopped syncing looks exactly like a connector that is working until the month it matters.",
       "Các kết nối đã cấu hình tới hệ thống nguồn, có thể kéo dữ liệu về mà không ai phải gõ lại. Một đầu nối đã âm thầm ngừng đồng bộ trông y hệt một đầu nối đang chạy tốt, cho tới đúng tháng nó trở nên quan trọng.")],
  ],

  importwizard: [
    ["rows_loaded",
     B("Rows loaded", "Số dòng đã nạp"),
     B("How many rows the importer read out of the source. If this is not the row count of your file, the file was truncated or a sheet was missed — and that is a better thing to find here than after the compute.",
       "Số dòng mà trình nhập liệu đọc được từ nguồn. Nếu con số này không bằng số dòng trong tệp của bạn thì tệp đã bị cắt hoặc bỏ sót một sheet — và phát hiện điều đó ở đây tốt hơn nhiều so với phát hiện sau khi đã tính lương.")],
    ["matched",
     B("Matched", "Đã khớp"),
     B("Rows the importer tied to an existing employee with no ambiguity. These are the rows that will become inputs without anybody looking at them again, so the count matters more than the percentage above it.",
       "Các dòng mà trình nhập liệu gắn được với một nhân viên đã có, không nhập nhằng. Đây là những dòng sẽ trở thành dữ liệu đầu vào mà không ai phải xem lại, nên số lượng quan trọng hơn tỷ lệ phần trăm ở trên.")],
    ["new_employees",
     B("New employees", "Nhân viên mới"),
     B("Rows the importer could not tie to anybody and that you have marked as a person who does not exist yet. Committing creates them, so this number is a hiring decision arriving through a spreadsheet — worth a second look.",
       "Các dòng mà trình nhập liệu không gắn được với ai và bạn đã đánh dấu là người chưa tồn tại trong hệ thống. Ghi nhận sẽ tạo ra họ, nên con số này là một quyết định nhân sự đi vào qua bảng tính — rất đáng xem lại lần nữa.")],
    ["need_attention",
     B("Need attention", "Cần xử lý"),
     B("Rows the importer could not place on its own: no matching employee, a duplicate, or a value it could not read. Every one of these is a person, and committing with any of them open produces a payslip that is missing or wrong.",
       "Các dòng mà trình nhập liệu không tự xếp được: không tìm ra nhân viên khớp, bị lặp, hoặc có giá trị nó không đọc được. Mỗi dòng như vậy là một con người, và ghi nhận khi còn dòng chưa xử lý sẽ tạo ra một phiếu lương thiếu hoặc sai.")],
    ["confidence_score",
     B("Confidence score", "Điểm tin cậy"),
     B("The share of rows read without ambiguity. It is not a grade and there is no pass mark — the number that matters is the count of rows underneath it, because 98% of fifty rows still leaves one person unaccounted for.",
       "Tỷ lệ số dòng được đọc mà không nhập nhằng. Đây không phải điểm số và không có mức đạt — con số quan trọng là số dòng bên dưới nó, vì 98% của năm mươi dòng vẫn còn một con người chưa được tính đến.")],
  ],

  fullfinal: [
    ["leavers_this_period",
     B("Leavers this period", "Thôi việc kỳ này"),
     B("Employees whose contract ends inside this period. Each one needs settling here AND excluding from the normal monthly run — a leaver in both is paid twice, and recovering that is a legal conversation rather than a payroll one.",
       "Những nhân viên có hợp đồng kết thúc trong kỳ này. Mỗi người vừa cần được quyết toán ở đây VÀ cần bị loại khỏi đợt lương tháng thông thường — người nằm ở cả hai chỗ sẽ được trả hai lần, và thu hồi khoản đó là chuyện pháp lý chứ không còn là chuyện tính lương.")],
    ["pending_settlement",
     B("Pending settlement", "Chờ quyết toán"),
     B("Leavers whose final amount has been worked out but not yet paid. Settlements have legal deadlines, so this count is a clock rather than a queue.",
       "Những người thôi việc đã tính xong khoản cuối nhưng chưa được chi. Quyết toán có thời hạn pháp lý, nên con số này là một chiếc đồng hồ chứ không phải một hàng đợi.")],
    ["settled",
     B("Settled", "Đã chốt"),
     B("The total already paid out as final settlements in this period. It sits outside the monthly run's net total, which is why the two numbers never add up to what left the bank.",
       "Tổng số đã chi cho các khoản quyết toán trong kỳ này. Nó nằm ngoài tổng thực nhận của đợt lương tháng, và đó là lý do hai con số không bao giờ cộng lại bằng số tiền đã rời tài khoản.")],
  ],

  proration: [
    ["prorated_payslips",
     B("Prorated payslips", "Phiếu tính theo ngày công"),
     B("Payslips in this run paid for part of a month rather than all of it — joiners, leavers and unpaid leave. Every one of them is a likely question from the employee, and this screen is the answer written down before it is asked.",
       "Các phiếu trong đợt này được trả cho một phần của tháng thay vì cả tháng — người mới vào, người thôi việc và nghỉ không lương. Mỗi phiếu như vậy đều có khả năng thành một câu hỏi từ nhân viên, và màn hình này là câu trả lời đã viết sẵn trước khi ai đó hỏi.")],
    ["standard_working_days",
     B("Standard working days", "Ngày công chuẩn"),
     B("The divisor every proration factor is built from, taken from the division's configuration. It is working days and not calendar days, and reading it as calendar days is the mistake that turns an explanation into an argument.",
       "Mẫu số mà mọi hệ số tính theo ngày công dựa vào, lấy từ cấu hình của bộ phận. Đó là ngày công chứ không phải ngày dương lịch, và hiểu nhầm thành ngày dương lịch là sai sót biến một lời giải thích thành một cuộc tranh cãi.")],
  ],

  retro: [
    ["retro_lines",
     B("Retro lines", "Dòng hồi tố"),
     B("Corrections belonging to a period that is already closed, paid in the current run. Each is a deliberate decision not to reopen an approved month, which is what keeps everything already reported from that month true.",
       "Các hiệu chỉnh thuộc về một kỳ đã đóng, được chi trong đợt hiện tại. Mỗi dòng là một quyết định có chủ ý không mở lại một tháng đã duyệt, và chính điều đó giữ cho mọi báo cáo đã xuất từ tháng đó vẫn đúng.")],
    ["total_adjustment",
     B("Total adjustment", "Tổng điều chỉnh"),
     B("The sum of the retro lines in this run. It is added on top of the month's own earnings, so the run's net total will be higher than the same headcount would normally produce — worth saying out loud before somebody asks about the variance.",
       "Tổng của các dòng hồi tố trong đợt này. Nó được cộng thêm trên phần thu nhập của chính tháng đó, nên tổng thực nhận của đợt sẽ cao hơn mức mà cùng sĩ số thường tạo ra — rất đáng nói ra trước khi có người hỏi về biến động.")],
    ["oldest_source_period",
     B("Oldest source period", "Kỳ gốc xa nhất"),
     B("The furthest-back month any line here is correcting. The older it is, the more reporting has already been done on the original figure — which is exactly why the correction is a retro line and never an edit to that month.",
       "Tháng xa nhất mà một dòng ở đây đang hiệu chỉnh. Càng lâu thì càng nhiều báo cáo đã được lập trên con số gốc — và đó chính là lý do việc sửa phải là một dòng hồi tố chứ không bao giờ là sửa vào tháng đó.")],
  ],

  /* -- Setup ------------------------------------------------------------- */
  formula: [
    ["components",
     B("Components", "Thành phần"),
     B("Every named piece of a division's rulebook: the inputs, the earnings, the deductions and the totals. A payslip line exists because a component here produced it, so a missing line is a missing component rather than a bug in the compute.",
       "Từng phần có tên trong bộ quy tắc của một bộ phận: đầu vào, các khoản thu nhập, các khoản khấu trừ và các tổng. Một dòng trên phiếu lương tồn tại vì có một thành phần ở đây tạo ra nó, nên thiếu dòng nghĩa là thiếu thành phần chứ không phải lỗi khi tính.")],
    ["depends_on",
     B("Depends on", "Phụ thuộc vào"),
     B("The components this one reads to produce its own value. Change any of them and this line moves — which makes this the list to check before you edit an input rather than after somebody notices the output.",
       "Những thành phần mà thành phần này đọc vào để tạo ra giá trị của chính nó. Đổi bất kỳ cái nào thì dòng này thay đổi theo — nên đây là danh sách cần kiểm tra trước khi sửa một đầu vào, chứ không phải sau khi có người phát hiện kết quả sai.")],
    ["used_by",
     B("Used by", "Được dùng bởi"),
     B("The components that read THIS one. It is the blast radius of a rename or a deletion, written down: everything listed here would lose an input, and a formula that lost an input does not always fail loudly.",
       "Những thành phần đọc vào chính thành phần NÀY. Đây là phạm vi ảnh hưởng của việc đổi tên hay xoá, đã được ghi rõ: mọi thứ liệt kê ở đây sẽ mất một đầu vào, và một công thức mất đầu vào không phải lúc nào cũng báo lỗi rõ ràng.")],
    ["live_preview",
     B("Live preview", "Xem trước trực tiếp"),
     B("The whole configuration evaluated against one sample employee, line by line. It is the cheapest possible check on an edit — and it is one person, which is why it is a first look rather than the evidence.",
       "Toàn bộ cấu hình được chạy trên một nhân viên mẫu, theo từng dòng. Đây là cách kiểm tra rẻ nhất cho một lần sửa — và chỉ trên một người, nên nó là cái nhìn đầu tiên chứ chưa phải bằng chứng.")],
    ["simulate",
     B("Simulate", "Mô phỏng"),
     B("The edited configuration run against a period that has already been paid, so you can compare what it would have produced with what was actually paid. This is the evidence the preview is not: everybody, not one person.",
       "Cấu hình đã sửa được chạy trên một kỳ lương đã chi, để bạn so kết quả nó sẽ tạo ra với số đã thực trả. Đây mới là bằng chứng mà bản xem trước chưa phải: trên tất cả mọi người, không phải một người.")],
  ],

  statutory: [
    ["contributions",
     B("Contributions", "Tổng đóng bảo hiểm"),
     B("The total of both legs — what employees have deducted plus what the company pays on top — for the period on display. It is a cost figure, not a deduction figure, so it is roughly three times what appears on the payslips.",
       "Tổng của cả hai phần — khoản khấu trừ của người lao động cộng khoản doanh nghiệp đóng thêm — trong kỳ đang hiển thị. Đây là con số chi phí, không phải con số khấu trừ, nên nó lớn hơn phần hiện trên phiếu lương khoảng ba lần.")],
    ["employee_leg",
     B("Employee leg", "Phần người lao động"),
     B("The part deducted from payslips — 10.5% of the registered insurance base under the current policy. This is the only half an employee ever sees, and it is the half they ask about.",
       "Phần được khấu trừ trên phiếu lương — 10,5% của mức lương đóng bảo hiểm đã đăng ký theo chính sách hiện hành. Đây là nửa duy nhất mà nhân viên nhìn thấy, và cũng là nửa họ hỏi tới.")],
    ["employer_leg",
     B("Employer leg", "Phần doanh nghiệp"),
     B("The part the company pays on top of salary — 21.5% of the same base, twice what the employee pays. It never appears in anybody's net, which is why it is invisible in every conversation about pay unless somebody puts it on the table.",
       "Phần doanh nghiệp đóng thêm ngoài lương — 21,5% trên cùng mức đóng đó, gấp đôi phần người lao động. Nó không bao giờ xuất hiện trong thực nhận của ai, nên vô hình trong mọi cuộc trao đổi về lương trừ khi có người chủ động nêu ra.")],
    ["policies",
     B("Policies", "Chính sách"),
     B("How many insurance policy records exist, active and archived together. More than one is normal and healthy: a rate change is a new record, so the count grows every time the law does.",
       "Có bao nhiêu bản ghi chính sách bảo hiểm, tính cả đang bật và đã lưu trữ. Nhiều hơn một là bình thường và lành mạnh: đổi tỷ lệ là tạo bản ghi mới, nên con số này tăng mỗi lần pháp luật thay đổi.")],
    ["tax_tables",
     B("Tax tables", "Biểu thuế"),
     B("One per tax year, holding the bands and the two relief figures. Last year's stays because last year's payslips were computed by it and still have to be explainable.",
       "Mỗi năm tính thuế một biểu, chứa các bậc thuế và hai mức giảm trừ. Biểu của năm ngoái vẫn được giữ vì phiếu lương năm ngoái được tính theo nó và vẫn phải giải thích được.")],
    ["dependents",
     B("Dependents", "Người phụ thuộc"),
     B("Registered dependants across the company, each worth 4,400,000 ₫ a month off taxable income. Registration is the point: an unregistered dependant is relief the employee is entitled to and is not getting.",
       "Số người phụ thuộc đã đăng ký trên toàn công ty, mỗi người giảm trừ 4.400.000 ₫ mỗi tháng vào thu nhập chịu thuế. Mấu chốt là việc đăng ký: một người phụ thuộc chưa đăng ký là khoản giảm trừ mà nhân viên có quyền hưởng nhưng không được hưởng.")],
  ],

  structures: [
    ["structures",
     B("Structures", "Cấu trúc"),
     B("Legacy Odoo salary structures still held by this company. They are history rather than configuration: new pay logic belongs in a formula configuration, and these exist so old payslips can still be explained.",
       "Các cấu trúc lương Odoo thế hệ cũ mà công ty này còn giữ. Chúng là lịch sử chứ không phải cấu hình: logic lương mới thuộc về cấu hình công thức, còn những cái này tồn tại để phiếu lương cũ vẫn giải thích được.")],
    ["salary_rules",
     B("Salary rules", "Quy tắc lương"),
     B("The individual rules inside those structures — the older equivalent of a component. Reading one tells you how a payslip from before the migration got its number.",
       "Từng quy tắc bên trong các cấu trúc đó — tương đương thành phần ở thế hệ trước. Đọc một quy tắc là biết một phiếu lương từ trước khi chuyển đổi đã ra con số đó bằng cách nào.")],
    ["categories",
     B("Categories", "Nhóm quy tắc"),
     B("How the rules are grouped for reporting — basic, allowance, deduction, net. The grouping is what a payslip's subtotals are built from, which is why two structures with the same rules can still print differently.",
       "Cách các quy tắc được nhóm lại để báo cáo — lương cơ bản, phụ cấp, khấu trừ, thực nhận. Chính cách nhóm này tạo ra các tổng phụ trên phiếu lương, nên hai cấu trúc có cùng quy tắc vẫn có thể in ra khác nhau.")],
    ["employees_covered",
     B("Employees covered", "Nhân viên áp dụng"),
     B("How many people are still paid through a structure rather than a formula configuration. On a migrated company this trends to zero, and zero is the signal that a division has finished moving — not that the structure can be deleted.",
       "Còn bao nhiêu người được trả lương qua cấu trúc thay vì qua cấu hình công thức. Ở một công ty đã chuyển đổi, con số này tiến về không, và không là dấu hiệu một bộ phận đã chuyển xong — chứ không phải dấu hiệu có thể xoá cấu trúc đó.")],
    ["countries",
     B("Countries", "Quốc gia"),
     B("How many country rule sets are represented here. A structure carries its country's statutory assumptions, so a structure from the wrong country is wrong in ways that do not look wrong.",
       "Có bao nhiêu bộ quy tắc theo quốc gia đang hiện diện ở đây. Mỗi cấu trúc mang theo các giả định luật định của quốc gia đó, nên một cấu trúc sai quốc gia sẽ sai theo cách nhìn vào không thấy sai.")],
  ],

  integrations: [
    ["connectors",
     B("Connectors", "Đầu nối"),
     B("Configured links to a source system that can pull data in without anybody retyping it — an HR system, a time clock, the bank. Each one is a place a wrong row can enter payroll without passing a human.",
       "Các kết nối đã cấu hình tới hệ thống nguồn, có thể kéo dữ liệu về mà không ai phải gõ lại — hệ thống nhân sự, máy chấm công, ngân hàng. Mỗi đầu nối là một cửa để một dòng sai có thể vào hệ thống lương mà không qua tay người nào.")],
    ["connected",
     B("Connected", "Đã kết nối"),
     B("How many connectors currently hold working credentials. It says nothing about whether data is arriving: connected describes the login, and the last-sync time describes the data.",
       "Bao nhiêu đầu nối hiện có thông tin đăng nhập còn dùng được. Nó không nói gì về việc dữ liệu có đang về hay không: đã kết nối nói về đăng nhập, còn thời điểm đồng bộ gần nhất mới nói về dữ liệu.")],
    ["errors",
     B("Errors", "Lỗi"),
     B("Connectors whose last attempt failed. One here in the week before payroll is a month of inputs that will not arrive — and the payslips computed without them will look perfectly normal.",
       "Các đầu nối có lần chạy gần nhất thất bại. Một lỗi ở đây trong tuần trước kỳ lương là cả một tháng dữ liệu đầu vào sẽ không về — và những phiếu lương tính thiếu chúng vẫn trông hoàn toàn bình thường.")],
    ["synced_records",
     B("Synced records", "Bản ghi đã đồng bộ"),
     B("How many records have come through successfully. Compare it with last month rather than reading it alone: a number that stopped growing is a connector that stopped working.",
       "Bao nhiêu bản ghi đã về thành công. Hãy so với tháng trước thay vì đọc riêng con số này: một con số ngừng tăng là một đầu nối đã ngừng chạy.")],
    ["field_mappings",
     B("Field mappings", "Ánh xạ trường"),
     B("How many fields in the source system are wired to a field here. A mapping that was never made is a column that silently arrives empty, and the payslip line it feeds simply computes on zero.",
       "Có bao nhiêu trường ở hệ thống nguồn được nối tới một trường ở đây. Một ánh xạ chưa từng được tạo là một cột âm thầm về rỗng, và dòng phiếu lương ăn theo nó chỉ đơn giản tính trên số không.")],
    ["staged_records",
     B("Staged records", "Bản ghi đang chờ"),
     B("Rows that arrived but have not been taken into payroll yet. A count that is climbing is the clearest single sign of a broken sync — those rows are somebody's attendance, waiting.",
       "Các dòng đã về nhưng chưa được đưa vào hệ thống lương. Con số này tăng dần là dấu hiệu rõ nhất của một đầu nối hỏng — những dòng đó là chấm công của ai đó, đang nằm chờ.")],
  ],
};

/* =============================================================================
   10. PRACTICE-ONLY ANCHORS
   -----------------------------------------------------------------------------
   Anchors the practice replica draws that have NO product counterpart: the
   arithmetic breakdown, the lifecycle stepper, the replica's own navigation.
   Declared here so the gap is visible and so the generator can write the
   `practice` block of pb_learn/static/src/anchors.json from one place — the
   Coach must never claim to point at one of these on a live screen.

   The product and pattern blocks of that registry are NOT generated: they
   describe real templates in other modules and are curated by hand.
   ========================================================================== */
const PRACTICE_ANCHORS = {
  "rep-nav": "The replica's own sidebar. Mirrors pb_sidebar; nothing on it navigates the real app.",
  "rep-banner": "The practice banner. Says, on every screen, that none of this is your company.",
  "rep-dash-kpis": "The replica Dashboard's KPI row. Context only — Phase A teaches the Pay Run section.",
  "rep-dash-runs": "The replica Dashboard's recent-runs list.",
  "rep-pipeline": "The lifecycle stepper: draft → level0 → level1 → level2 → done, with the rejection branch. A teaching view; the product draws this as columns, not as a stepper.",
  "rep-slipline": "The worked example's statutory deductions, drawn on the STATUTORY replica beside the rates that produced them. It is the far end of L6's trace and it exists only here: the product's statutory cockpit shows rates, and a payslip shows đồng, and no single product screen shows both at once. Naming it rep- is the honest consequence — the Coach must never claim to point at this on a live screen.",
};

/* =============================================================================
   11. THE JOURNEY'S FRONT DOOR
   -----------------------------------------------------------------------------
   The sidebar leaf that opens the Journey. It is here rather than hand-written
   in the module for one reason: its NAME is content, and content ships in both
   languages. "Learn" / "Học cùng Payobook" has to reach the .po through the
   same path as every other translatable, or it is a string that only a code
   review can catch when it drifts.

   `groups` is deliberately empty and there is no field for it: every gated leaf
   in this sidebar hides itself from users who cannot use it, which is right for
   a working screen and wrong for a learning one. Someone who cannot open Run
   Payroll is exactly the person who needs to read what it is before asking for
   access — the Journey marks those stations "not in your menu" rather than
   hiding them.

   `compass` is not a preference. pb_sidebar renders a FIXED icon set and an
   unknown name draws a plain circle, so this is one of the names it knows.
   ========================================================================== */
const SIDEBAR_LEAF = {
  xmlid: "item_learn_journey",
  section: "pb_sidebar.sec_payrun",
  sequence: 90,
  icon: "compass",
  actionXmlid: "pb_learn.action_learn_journey",
  actionTag: "learn_journey",
  name: B("Learn", "Học cùng Payobook"),
};
