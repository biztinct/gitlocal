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
    // One key per station LINE. A line with no string here renders its own key
    // as a heading — health_learn shipped exactly that when its selection was
    // extended without the matching UI strings, and the map is the first thing
    // a learner sees. tests/test_bundle.py::test_09 is the guard.
    lines: {
      payrun: "Pay Run", setup: "Setup", overview: "Overview",
      people: "People", insights: "Insights", compliance: "Compliance",
    },
    /* -- station cards -------------------------------------------------- */
    fullLesson: "Full lesson",
    outline: "Outline",
    required: "Required",
    optional: "Optional",
    est: "About",
    min: "min",
    // The "Start here" pulse the demo first-login greeting puts on LW. It is
    // a POINT, not a play button — the card still has to be pressed.
    startHere: "Start here",
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
    /* -- server-side (Phase B review fix) --------------------------------
       These are read by models/learn_live.py and models/learn_mission.py,
       not by the JS. They are records for the same reason every other
       translatable is: a bilingual dict literal in Python is invisible to
       the .po tooling, so a translator never sees it and a reviewer cannot
       diff it. `%s` marks an interpolation the Python does, INTO this
       template — the composition stays in code, the sentence does not. */
    live: {
      notDemo: "Live missions need the demo world. This one runs against real records in the Payobook demo company, and your session is somewhere else.",
      noDivision: "No division has been assigned to you yet. Open Run Payroll once and one will be — each demo account drives its own division's June run.",
      noRun: "No June run for your division yet. Open Run Payroll and compute it — the wizard already has your division and the period selected.",
      noSlips: "The run exists but has no payslips yet. Press Compute in the wizard.",
      computed: "%(count)s payslips computed for %(division)s.",
      stillDraft: "Still in draft. Submit the run for approval from the Pay Runs board.",
      notPastOfficer: "Not past the Payroll Officer gate yet.",
      allGatesDone: "Done — every gate has said yes.",
      noSuchCheck: "There is no check called '%(key)s'.",
      noSuchStep: "No step '%(step)s' in mission '%(mission)s'.",
      notLive: "'%(mission)s' is a practice mission — it has nothing to check on the server.",
      notVerified: "Step '%(step)s' is not verified by the server.",
      stateDraft: "Draft",
      stateLevel0: "Payroll Officer pending",
      stateLevel1: "HR review",
      stateLevel2: "Finance approval",
      stateDone: "Done",
    },
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
    /* -- scenarios: one story, three ways (LEARNOS Phase 1b) --------------
       A scenario is authored ONCE and can be taken three ways — Watch it on
       the real screens, Try it on the practice company, Do it for real with
       the engine waiting before anything is written. These strings are the
       chrome of that engine; the steps themselves are in SCENARIOS below. */
    scenarios: "Show me how",
    scenariosLead: "One task, three ways: watch it happen, try it where nothing can matter, or do it for real with me waiting.",
    scWatch: "Watch",
    scTry: "Try",
    scDo: "Do it live",
    scWatchHint: "I drive. Real screens, and I stop at anything that writes.",
    scTryHint: "You drive, on the practice company.",
    scDoHint: "You drive, on your own data. I never press anything for you.",
    scRealBadge: "Real screens",
    scTryBadge: "Practice company",
    scYourTurn: "Your turn",
    scPressIt: "Press the control I am pointing at.",
    scWaiting: "You press it — I'll wait.",
    scWaitingBody: "This control writes something real. I will not press it for you, and I will not move on by myself.",
    scWouldDo: "What this would do",
    scNudge: "Not that one — try the glowing control.",
    scTyping: "Typing",
    scExpected: "Expected",
    scSkip: "Skip this step",
    scNotOnScreen: "That control is not on this screen right now, so here is what it does instead of a spotlight pointing at nothing.",
    scDone: "End of the walkthrough",
    scDoneBody: "That is the whole scenario. Take it again in another mode whenever you like — the steps are the same, only who presses changes.",
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
    composedAnswer: "Composed from the guide",
    noAnswer: "I do not have an answer for that",
    noAnswerBody: "Nothing written here covers that question. Here is what I can answer on this screen.",
    /* -- storing questions: asked once, remembered either way ------------- */
    consentTitle: "Help improve the guide?",
    consentBody: "If you allow it, the question you just asked is stored so we can see what the guide does not cover yet. Names and amounts are removed before anything is saved, and the stored question carries your name — that is how you can find and delete yours at any time. Stored questions are deleted after 180 days. Say no and nothing is stored — the Coach works exactly the same either way.",
    consentYes: "Yes, store my questions",
    consentNo: "No, do not store them",
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
    lines: {
      payrun: "Chạy lương", setup: "Thiết lập", overview: "Tổng quan",
      people: "Nhân sự", insights: "Phân tích", compliance: "Tuân thủ",
    },
    /* -- station cards -------------------------------------------------- */
    fullLesson: "Bài học đầy đủ",
    outline: "Dàn ý",
    required: "Bắt buộc",
    optional: "Tuỳ chọn",
    est: "Khoảng",
    min: "phút",
    startHere: "Bắt đầu từ đây",
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
    live: {
      notDemo: "Nhiệm vụ trực tiếp cần môi trường demo. Nhiệm vụ này chạy trên dữ liệu thật của công ty demo Payobook, còn phiên của bạn đang ở nơi khác.",
      noDivision: "Bạn chưa được gán bộ phận nào. Hãy mở Chạy bảng lương một lần là sẽ có — mỗi tài khoản demo tự chạy đợt lương tháng 6 của bộ phận mình.",
      noRun: "Chưa có đợt lương tháng 6 cho bộ phận của bạn. Hãy mở Chạy bảng lương và tính — trình hướng dẫn đã chọn sẵn bộ phận và kỳ lương của bạn.",
      noSlips: "Đợt lương đã có nhưng chưa có phiếu nào. Hãy bấm Tính trong trình hướng dẫn.",
      computed: "Đã tính %(count)s phiếu lương cho %(division)s.",
      stillDraft: "Vẫn ở trạng thái Nháp. Hãy trình đợt lương lên phê duyệt từ bảng Đợt tính lương.",
      notPastOfficer: "Chưa qua cổng Chuyên viên tính lương.",
      allGatesDone: "Hoàn tất — mọi cổng đã đồng ý.",
      noSuchCheck: "Không có phép kiểm tra nào tên '%(key)s'.",
      noSuchStep: "Không có bước '%(step)s' trong nhiệm vụ '%(mission)s'.",
      notLive: "'%(mission)s' là nhiệm vụ thực hành — không có gì để kiểm tra trên máy chủ.",
      notVerified: "Bước '%(step)s' không được máy chủ xác minh.",
      stateDraft: "Nháp",
      stateLevel0: "Chờ Chuyên viên tính lương",
      stateLevel1: "HR soát xét",
      stateLevel2: "Tài chính phê duyệt",
      stateDone: "Hoàn tất",
    },
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
    /* -- scenarios: one story, three ways (LEARNOS Phase 1b) ------------- */
    scenarios: "Chỉ tôi cách làm",
    scenariosLead: "Một việc, ba cách học: xem tôi làm, tự thử ở nơi không có hậu quả, hoặc làm thật với tôi đứng chờ bên cạnh.",
    scWatch: "Xem",
    scTry: "Thử",
    scDo: "Làm thật",
    scWatchHint: "Tôi thao tác. Trên màn hình thật, và tôi dừng lại ở mọi nút có ghi dữ liệu.",
    scTryHint: "Bạn thao tác, trên công ty thực hành.",
    scDoHint: "Bạn thao tác, trên dữ liệu của chính bạn. Tôi không bao giờ bấm hộ bạn.",
    scRealBadge: "Màn hình thật",
    scTryBadge: "Công ty thực hành",
    scYourTurn: "Đến lượt bạn",
    scPressIt: "Hãy bấm vào nút tôi đang chỉ.",
    scWaiting: "Bạn bấm nút đó — tôi chờ.",
    scWaitingBody: "Nút này ghi dữ liệu thật. Tôi sẽ không bấm hộ bạn, và cũng không tự chuyển sang bước sau.",
    scWouldDo: "Nút này sẽ làm gì",
    scNudge: "Không phải nút đó — hãy thử nút đang phát sáng.",
    scTyping: "Đang nhập",
    scExpected: "Cần nhập",
    scSkip: "Bỏ qua bước này",
    scNotOnScreen: "Nút đó hiện không có trên màn hình này, nên tôi mô tả nó ở đây thay vì chỉ vào chỗ trống.",
    scDone: "Hết phần hướng dẫn",
    scDoneBody: "Đó là toàn bộ kịch bản. Bạn có thể xem lại theo cách khác bất cứ lúc nào — các bước vẫn thế, chỉ khác ở chỗ ai là người bấm.",
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
    composedAnswer: "Tổng hợp từ tài liệu hướng dẫn",
    noAnswer: "Tôi chưa có câu trả lời cho việc đó",
    noAnswerBody: "Không có nội dung nào ở đây bao phủ câu hỏi đó. Đây là những gì tôi trả lời được trên màn hình này.",
    /* -- storing questions: asked once, remembered either way ------------- */
    consentTitle: "Giúp chúng tôi cải thiện tài liệu hướng dẫn?",
    consentBody: "Nếu bạn đồng ý, câu hỏi bạn vừa đặt sẽ được lưu lại để chúng tôi biết tài liệu còn thiếu những gì. Tên riêng và số tiền đều được loại bỏ trước khi lưu, và câu hỏi được lưu kèm tên của bạn — nhờ vậy bạn có thể tìm và xoá câu hỏi của mình bất cứ lúc nào. Câu hỏi đã lưu sẽ bị xoá sau 180 ngày. Nếu bạn từ chối thì không có gì được lưu — Trợ lý vẫn hoạt động y như vậy.",
    consentYes: "Đồng ý, hãy lưu câu hỏi của tôi",
    consentNo: "Không, đừng lưu lại",
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
    def: B("One batch of payslips for a division and a period, travelling draft → Payroll Officer → {{hrTierName}} → {{gmTierName}} → done. A rejection at any gate CANCELS the whole batch, every payslip with it, and records who, when and why in writing.",
           "Một lô phiếu lương của một bộ phận trong một kỳ, đi qua Nháp → Chuyên viên tính lương → {{hrTierName}} → {{gmTierName}} → Hoàn tất. Bị từ chối ở bất kỳ cổng nào sẽ HUỶ cả lô, kèm toàn bộ phiếu lương trong đó, và ghi lại ai từ chối, lúc nào và vì sao bằng văn bản."),
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
    def: B("The short unique name of a formula configuration — the thing Run Payroll actually selects when you choose a division. The shape is PREFIX_DIVISION_CYCLE, and the prefix is the company's: on this practice company the codes read HOASEN_RETAIL_END, and on the Payobook demo world they read DEMO_RETAIL_END for the end-cycle rulebook and DEMO_RETAIL_MID for the mid-cycle one. Learn the shape rather than any one prefix.",
           "Tên ngắn và duy nhất của một cấu hình công thức — chính là thứ Chạy bảng lương chọn khi bạn chọn bộ phận. Dạng chung là TIỀN TỐ_BỘ PHẬN_CHU KỲ, và tiền tố là của từng công ty: trên công ty thực hành này mã đọc là HOASEN_RETAIL_END, còn trên môi trường demo của Payobook mã đọc là DEMO_RETAIL_END cho bộ quy tắc cuối kỳ và DEMO_RETAIL_MID cho giữa kỳ. Hãy nhớ dạng chung, đừng nhớ một tiền tố cụ thể."),
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
              "Trình phê duyệt mà chưa mở các phiếu bị gắn cờ. Cờ là câu hỏi hệ thống muốn được trả lời, và việc trình phê duyệt là bạn trả lời nó bằng sự im lặng."),
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
            B("Rejecting without a written reason. The product refuses an empty one, and a thin one is worse than none: the run is cancelled either way, and the person who has to rebuild it is guessing at what you saw.",
              "Từ chối mà không ghi lý do. Sản phẩm không cho để trống, và một lý do hời hợt còn tệ hơn không có: đằng nào đợt lương cũng bị huỷ, còn người phải dựng lại nó thì phải đoán xem bạn đã thấy điều gì."),
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

  /* ---------------------------------------------------------------------------
     THE OVERVIEW LINE (Phase C1).

     APPENDED, NOT INSERTED, and the reason is mechanical rather than editorial:
     the generator numbers stations with one counter that runs across every line
     in declaration order, so inserting here would renumber Pay Run and Setup for
     no content reason. The MAP does not draw them in this order — journey.js
     holds the reading order (Overview, Pay Run, People, Insights, Compliance,
     Setup), which is where a presentation decision belongs.

     Two stations, and both are flagships. The Dashboard is where a new user
     lands and the only screen that describes the whole month at once; Approvals
     is where money stops being reversible. Everything between them already had
     a lesson before Phase C.
     ------------------------------------------------------------------------ */
  overview: {
    stations: [
      {
        id: "dashboard", icon: "grid", star: true, required: true, mins: 8, after: null,
        title: B("Dashboard", "Bảng điều khiển"),
        desc: B("Where you land, what the month looks like, and where everything else lives.",
                "Nơi bạn vào đầu tiên, bức tranh cả tháng, và mọi thứ khác nằm ở đâu."),
        outline: {
          what: B("The command centre: who you are, which run is live, four numbers that describe the company, and a card for each part of the product worth opening today.",
                  "Bảng điều khiển tổng: bạn là ai, đợt lương nào đang chạy, bốn con số mô tả cả công ty, và mỗi phần của sản phẩm đáng mở hôm nay là một thẻ."),
          why: B("It is the only screen that answers \"what is the state of payroll right now\" without you choosing a filter first. The tiles report it; the buttons and the run rows beside them are the doors into the screens those figures came from.",
                 "Đây là màn hình duy nhất trả lời được \"hiện trạng công việc lương lúc này ra sao\" mà bạn không phải chọn bộ lọc trước. Các ô chỉ số báo cáo hiện trạng đó; còn các nút và các dòng đợt lương bên cạnh mới là cửa dẫn vào những màn hình đã sinh ra các con số ấy."),
          when: B("First thing, every day of payroll week, and any time you have been away long enough to have lost the thread.",
                  "Việc đầu tiên mỗi ngày trong tuần tính lương, và bất cứ khi nào bạn vắng đủ lâu để mất mạch công việc."),
          prereq: B("Nothing. This is the one screen everybody can open, and it is deliberately the least gated in the product.",
                    "Không cần gì. Đây là màn hình ai cũng mở được, và nó cố ý là nơi ít bị chặn quyền nhất trong sản phẩm."),
          mistakes: [
            B("Reading a dashboard figure as today's work. Headcount and monthly payroll describe the company; only \"pending approval\" is a queue, and only one of those is yours.",
              "Đọc một con số trên bảng điều khiển như thể là việc của hôm nay. Nhân sự và chi phí lương tháng mô tả cả công ty; chỉ \"chờ phê duyệt\" mới là hàng đợi, và trong đó chỉ một phần là của bạn."),
            B("Treating it as a report and copying the numbers out. The KPI tiles only REPORT — it is the buttons and the run rows that open the screen a figure came from, and a figure copied away from its working loses the part somebody will ask about.",
              "Coi nó như một báo cáo rồi chép số ra ngoài. Các ô chỉ số chỉ để BÁO CÁO — chính các nút và các dòng đợt lương mới mở ra màn hình đã sinh ra con số, và một con số bị chép rời khỏi phần tính toán của nó sẽ mất đúng phần mà sau này có người hỏi tới."),
            B("Waiting for the dashboard to tell you something is wrong. It shows what is happening, not what has been checked — a flagged payslip is a number here and a question on the Payslips screen.",
              "Chờ bảng điều khiển báo cho biết có gì đó sai. Nó cho thấy điều đang diễn ra, không cho thấy điều đã được kiểm tra — một phiếu bị gắn cờ ở đây chỉ là một con số, còn câu hỏi thật nằm ở màn hình Phiếu lương."),
          ],
        },
      },
      {
        id: "approvals", icon: "clipboard-check", star: true, required: true, mins: 7, after: "dashboard",
        title: B("Approvals", "Phê duyệt"),
        desc: B("Every run waiting for a signature, in the lane of the gate it is waiting at — including yours.",
                "Mọi đợt lương đang chờ chữ ký, nằm ở làn của đúng cổng nó đang chờ — kể cả cổng của bạn."),
        outline: {
          what: B("Three lanes — Officer review, {{hrTierName}}, {{gmTierName}} — with a card per submitted run, the net at stake across all of them, and a list of what has already been decided.",
                  "Ba làn — Chuyên viên soát, {{hrTierName}}, {{gmTierName}} — mỗi đợt đã trình là một thẻ, kèm tổng số tiền đang treo và danh sách những gì đã được quyết."),
          why: B("The Pay Runs board shows every run there is; this screen shows only the ones a human still has to answer for. It is the queue, and the number in its header is the part of that queue that will not move until you move it.",
                 "Bảng Đợt tính lương hiển thị mọi đợt đang có; màn hình này chỉ hiển thị những đợt vẫn cần một con người chịu trách nhiệm. Đây là hàng đợi, và con số ở tiêu đề chính là phần hàng đợi sẽ không nhúc nhích cho tới khi bạn động vào."),
          when: B("Every morning of payroll week, and before you tell anybody a run is stuck — the lane it is in names who is holding it.",
                  "Mỗi sáng trong tuần tính lương, và trước khi bạn nói với ai rằng một đợt đang tắc — làn mà nó nằm chỉ đích danh người đang giữ."),
          prereq: B("One of the payroll approval groups. Without one the leaf is not in your sidebar at all, which is the honest form of \"you cannot approve\".",
                    "Một trong các nhóm quyền phê duyệt lương. Không có nhóm nào thì mục này không xuất hiện trong thanh bên của bạn — đó là cách nói thẳng thắn của câu \"bạn không phê duyệt được\"."),
          mistakes: [
            B("Approving from the lane without opening the run. The card shows a total and a payslip count; the flags are on the payslips, and the total is what a wrong payslip hides inside.",
              "Phê duyệt ngay trên làn mà chưa mở đợt lương ra. Thẻ chỉ hiện một con số tổng và số lượng phiếu; cờ cảnh báo nằm trên từng phiếu, và con số tổng chính là chỗ một phiếu sai ẩn mình."),
            B("Reading an empty lane as a broken screen. Two of the three lanes are empty on most days — that is what a month looks like when nothing is stuck.",
              "Thấy một làn trống rồi cho rằng màn hình bị lỗi. Đa số ngày trong tháng có hai trên ba làn trống — đó là hình ảnh của một kỳ lương không có gì bị tắc."),
            B("Rejecting instead of asking. A rejection CANCELS the whole batch and is recorded with your name on it, and only the {{gmTierName}} tier can reopen it as a draft; a question in the corridor costs nobody two days.",
              "Từ chối thay vì hỏi. Một lần từ chối HUỶ cả lô và được ghi lại kèm tên bạn, và chỉ vòng {{gmTierName}} mới mở lại nó thành bản nháp được; một câu hỏi ngoài hành lang thì không làm ai mất hai ngày."),
          ],
        },
      },
    ],
  },

  /* ---------------------------------------------------------------------------
     THE PEOPLE LINE (Phase C1).

     Two outlines rather than a lesson, and that is a scope decision with a
     reason: what a payroll officer needs from People is a small number of
     habits (read payroll-readiness before the run, watch the expiry chip) and
     one distinction (a person is not a contract). Neither needs a nine-step
     lesson, and writing one to be symmetrical with Pay Run would pad it.
     ------------------------------------------------------------------------ */
  people: {
    stations: [
      {
        id: "employees", icon: "users", required: true, mins: 5, after: null,
        title: B("Employees", "Nhân viên"),
        desc: B("Everyone payroll can pay — with the two facts that decide whether they will actually be paid.",
                "Toàn bộ những người hệ thống lương có thể trả — kèm hai dữ kiện quyết định họ có thực sự được trả hay không."),
        outline: {
          what: B("The people roster: headcount, running contracts, contracts expiring within thirty days, new hires, the monthly wage bill, and a payroll-ready mark on each person.",
                  "Danh sách nhân sự: sĩ số, hợp đồng đang hiệu lực, hợp đồng hết hạn trong ba mươi ngày, người mới vào, quỹ lương tháng, và dấu sẵn sàng tính lương trên từng người."),
          why: B("Payroll-ready is the whole point of this screen. Somebody with no bank account computes perfectly and is not paid, and you find that out either here, in a minute, or on {{payDay}}, from them.",
                 "Dấu sẵn sàng tính lương mới là ý nghĩa của màn hình này. Một người chưa có tài khoản ngân hàng vẫn được tính lương hoàn hảo mà không nhận được tiền, và bạn biết điều đó hoặc ở đây trong một phút, hoặc vào {{payDay}}, do chính họ báo."),
          when: B("Before a run rather than after it, and whenever somebody joins, leaves or changes department.",
                  "Trước khi chạy một đợt lương chứ không phải sau, và mỗi khi có người vào, người nghỉ hoặc người đổi bộ phận."),
          prereq: B("The Payroll Officer group or above — the leaf is gated, because a wage list is not something everybody in a company should be able to read.",
                    "Quyền Chuyên viên tính lương trở lên — mục này bị chặn quyền, vì danh sách lương không phải thứ ai trong công ty cũng nên đọc được."),
          mistakes: [
            B("Reading the wage column as take-home pay. It is the registered contract base — the figure insurance is charged on — and nobody is paid exactly that in any month with overtime in it.",
              "Đọc cột lương như thể là số thực nhận. Đó là lương cơ bản đã đăng ký theo hợp đồng — mức dùng tính bảo hiểm — và không ai nhận đúng con số đó trong bất kỳ tháng nào có tăng ca."),
            B("Fixing a person's pay here. This screen holds who they are and what they were hired on; what they were paid last month is a payslip, and the two are corrected in different places.",
              "Sửa lương của một người ở đây. Màn hình này lưu họ là ai và được tuyển với mức nào; còn số họ được trả tháng trước nằm trên phiếu lương, và hai thứ đó được sửa ở hai nơi khác nhau."),
            B("Using bulk mode without reading the count. It is the one control here that changes many records at once, and \"12 selected\" is the only thing standing between a helpful edit and twelve wrong ones.",
              "Dùng chế độ chọn nhiều mà không đọc con số. Đây là nút duy nhất ở đây thay đổi nhiều bản ghi cùng lúc, và dòng \"đã chọn 12\" là thứ duy nhất ngăn giữa một chỉnh sửa hữu ích và mười hai chỉnh sửa sai."),
          ],
        },
      },
      {
        id: "contracts", icon: "file-text", mins: 5, after: "employees",
        title: B("Contracts", "Hợp đồng"),
        desc: B("The agreements payroll is actually paid from — and the expiry dates that quietly end them.",
                "Những thoả thuận mà hệ thống lương thực sự dựa vào để trả — và các ngày hết hạn âm thầm kết thúc chúng."),
        outline: {
          what: B("Every contract with its type, its period and its wage: running, expiring within thirty days, draft and expired, plus the wage bill and the average wage across them.",
                  "Từng hợp đồng kèm loại, thời hạn và mức lương: đang hiệu lực, sắp hết hạn trong ba mươi ngày, nháp và đã hết hạn, cùng quỹ lương và mức lương bình quân trên toàn bộ."),
          why: B("A person is not a contract. Payroll computes from the contract, so a contract still in draft pays nothing however complete the employee record is — and a contract that expired mid-month is a proration nobody asked for.",
                 "Con người không phải là hợp đồng. Hệ thống lương tính theo hợp đồng, nên một hợp đồng còn ở trạng thái Nháp thì không trả gì cả dù hồ sơ nhân viên có đầy đủ đến đâu — và một hợp đồng hết hạn giữa tháng là một lần tính theo ngày công mà không ai yêu cầu."),
          when: B("In the week before a run, on the expiring filter, and whenever somebody is promoted, transferred or renewed.",
                  "Trong tuần trước khi chạy lương, với bộ lọc sắp hết hạn, và mỗi khi có người được thăng chức, luân chuyển hoặc gia hạn."),
          prereq: B("The Payroll Officer group or above, and the signed paperwork — this screen records an agreement that was made somewhere else.",
                    "Quyền Chuyên viên tính lương trở lên, và giấy tờ đã ký — màn hình này ghi lại một thoả thuận đã được lập ở nơi khác."),
          mistakes: [
            B("Leaving a renewal in draft over the run date. The employee is on the roster, their contract is not running, and the run simply computes without them.",
              "Để một hợp đồng gia hạn ở trạng thái Nháp vắt qua ngày chạy lương. Nhân viên vẫn có trong danh sách, hợp đồng thì chưa hiệu lực, và đợt lương đơn giản là tính mà không có họ."),
            B("Editing a running contract's wage to correct one month. That changes the insurance base going forward and corrects nothing that has already been paid — the past is a retro line.",
              "Sửa mức lương trên một hợp đồng đang hiệu lực để chỉnh cho một tháng. Việc đó thay đổi mức lương đóng bảo hiểm từ nay về sau và không sửa được gì đã trả — quá khứ phải xử lý bằng một dòng hồi tố."),
          ],
        },
      },
    ],
  },

  /* ---------------------------------------------------------------------------
     THE INSIGHTS LINE (Phase C1).

     Three outlines whose real content is a single distinction: which tool
     answers which question. A board answers the questions somebody anticipated,
     an explorer answers the ones nobody did, and workforce analytics answers a
     question about people rather than about money. A learner who leaves with
     that has everything these three screens can give them.
     ------------------------------------------------------------------------ */
  insights: {
    stations: [
      {
        id: "insights", icon: "trending-up", required: true, mins: 5, after: null,
        title: B("Insights", "Phân tích"),
        desc: B("The board that answers the questions a payroll month asks every time.",
                "Bảng phân tích trả lời những câu hỏi mà tháng lương nào cũng đặt ra."),
        outline: {
          what: B("Executive analytics over the runs this company has: the headline net for the LATEST run whatever state it is in, the cost story over three, six or twelve months, a department leaderboard read from the latest DONE run, the statutory split, a workforce pulse and the analytics snapshots panel.",
                  "Phân tích tổng hợp trên các đợt lương của công ty: số thực chi nổi bật của đợt GẦN NHẤT bất kể đang ở trạng thái nào, diễn biến chi phí theo ba, sáu hay mười hai tháng, xếp hạng bộ phận đọc từ đợt ĐÃ HOÀN TẤT gần nhất, cơ cấu đóng bắt buộc, nhịp nhân sự và bảng ảnh chụp phân tích."),
          why: B("It answers the questions a payroll month asks every time, fast, because it reads the STORED per-run roll-ups rather than re-adding payslip lines. That is also the thing to know about it: the hero and the leaderboard do not have the same scope — the hero shows the latest run and prints its state beside itself, and the leaderboard waits for a run to be done. Read the state chip before you quote the number.",
                 "Nó trả lời nhanh những câu hỏi mà tháng lương nào cũng đặt ra, vì nó đọc các số TỔNG HỢP đã lưu sẵn theo từng đợt chứ không cộng lại từng dòng phiếu lương. Và đây cũng là điều cần biết về nó: phần đầu và bảng xếp hạng không cùng phạm vi — phần đầu hiển thị đợt gần nhất và in kèm trạng thái của chính đợt đó, còn bảng xếp hạng thì chờ tới khi có đợt đã hoàn tất. Hãy đọc chip trạng thái trước khi trích con số."),
          when: B("After a run reaches done, at month end, and any time somebody senior asks a question that starts with \"why is payroll\".",
                  "Sau khi một đợt lương đạt Hoàn tất, vào cuối tháng, và bất cứ khi nào có lãnh đạo hỏi một câu bắt đầu bằng \"vì sao chi phí lương\"."),
          prereq: B("An analytics group, and at least two completed runs — a trend needs a second point before it is a trend.",
                    "Quyền phân tích, và ít nhất hai đợt lương đã hoàn tất — một xu hướng cần điểm thứ hai mới thành xu hướng."),
          mistakes: [
            B("Comparing a total against a total. Headcount moves between months, so the honest comparison is cost per head — one more employee explains most of what looks like a rise.",
              "Đem một con số tổng so với một con số tổng. Sĩ số thay đổi giữa các tháng, nên phép so trung thực là chi phí bình quân đầu người — thêm một nhân viên là đủ giải thích phần lớn cái vẻ \"tăng\" đó."),
            B("Reading a board figure without its window. Three months and twelve months tell different stories about the same company, and the chip that decides which is easy to leave where somebody else left it.",
              "Đọc một con số trên bảng mà quên khoảng thời gian của nó. Ba tháng và mười hai tháng kể hai câu chuyện khác nhau về cùng một công ty, và cái chip quyết định điều đó rất dễ bị để nguyên như người trước đã chọn."),
            B("Quoting the headline without its state chip. The hero is the LATEST run in any state — a draft that nobody has reviewed appears here the moment it is computed, and it reads exactly like a paid month unless you look at the chip beside it.",
              "Trích con số nổi bật mà bỏ qua chip trạng thái. Phần đầu lấy đợt GẦN NHẤT ở bất kỳ trạng thái nào — một đợt còn Nháp chưa ai soát vẫn xuất hiện ở đây ngay khi vừa tính xong, và nhìn vào không khác gì một tháng đã chi, trừ khi bạn nhìn cái chip bên cạnh."),
          ],
        },
      },
      {
        id: "explorer", icon: "compass", mins: 5, after: "insights",
        title: B("Explorer", "Explorer"),
        desc: B("For the question the board did not anticipate: pick a measure, break it down, filter it.",
                "Dành cho câu hỏi mà bảng phân tích không lường trước: chọn chỉ tiêu, tách theo chiều, rồi lọc."),
        outline: {
          what: B("A question builder over the same payroll facts: one measure, one breakdown, one comparison, and any number of filters shown as removable tags above the result.",
                  "Công cụ đặt câu hỏi trên cùng dữ liệu lương: một chỉ tiêu, một chiều tách, một chiều so sánh, và bao nhiêu bộ lọc tuỳ ý, hiển thị thành các thẻ có thể gỡ ngay phía trên kết quả."),
          why: B("Boards answer anticipated questions and real ones are rarely anticipated. This is where \"net pay by division for the divisions that ran mid-cycle\" gets answered without anybody exporting a spreadsheet — and it reconciles with the payslips, which a spreadsheet stops doing the moment it is saved. It is also the only analytics screen that explains a MOVEMENT: a variance waterfall between two periods that adds up exactly, and a drill from any cell down to the employees behind it.",
                 "Bảng phân tích trả lời những câu hỏi đã lường trước, còn câu hỏi thật thì hiếm khi được lường trước. Đây là nơi \"thực nhận theo bộ phận, chỉ các bộ phận chạy giữa kỳ\" được trả lời mà không ai phải xuất bảng tính — và nó luôn khớp với phiếu lương, điều mà một bảng tính hết đúng ngay khi vừa được lưu. Đây cũng là màn hình phân tích duy nhất giải thích được một BIẾN ĐỘNG: biểu đồ phân rã chênh lệch giữa hai kỳ khớp chính xác, và từ bất kỳ ô nào cũng đi sâu xuống tới những nhân viên đứng sau nó."),
          when: B("When the board has answered everything it can and the question is still open, and when somebody needs a figure broken down a way nobody built a screen for.",
                  "Khi bảng phân tích đã trả lời hết những gì nó có thể mà câu hỏi vẫn còn đó, và khi ai đó cần một con số tách theo cách chưa có màn hình nào dựng sẵn."),
          prereq: B("An analytics group and a computed run. Knowing which measure you actually want helps more than any filter.",
                    "Quyền phân tích và một đợt lương đã tính. Biết rõ mình thật sự cần chỉ tiêu nào còn hữu ích hơn mọi bộ lọc."),
          mistakes: [
            B("Quoting a figure without its filters. The tags above the result are part of the answer — the same measure with one tag removed is a different number and looks identical when it is pasted into an email.",
              "Trích một con số mà bỏ quên bộ lọc của nó. Các thẻ phía trên kết quả là một phần của câu trả lời — cùng chỉ tiêu đó, gỡ một thẻ đi là một con số khác, mà khi dán vào email thì trông y hệt nhau."),
            B("Stopping at the table. The waterfall and the drill are where the answer usually is — the table tells you a division moved, and those two tell you which component moved and which employees carried it.",
              "Dừng lại ở cái bảng. Câu trả lời thường nằm ở biểu đồ phân rã và ở bước đi sâu — cái bảng chỉ cho biết một bộ phận có biến động, còn hai thứ kia mới cho biết thành phần nào biến động và những nhân viên nào gánh phần đó."),
          ],
        },
      },
      {
        id: "workforcean", icon: "bar-chart", mins: 4, after: "insights",
        title: B("Workforce Analytics", "Phân tích nhân sự"),
        desc: B("The same months read as people rather than as money: who was paid, who joined, who left.",
                "Vẫn những tháng đó nhưng đọc theo con người thay vì theo tiền: ai được trả lương, ai vào, ai nghỉ."),
        outline: {
          what: B("Headcount paid month by month, joiners and leavers, cost per head, attendance exceptions and overtime — all read off the payroll that was actually run.",
                  "Số người được trả lương theo từng tháng, người vào và người nghỉ, chi phí bình quân đầu người, ngoại lệ chấm công và tăng ca — tất cả đọc từ chính các đợt lương đã chạy."),
          why: B("\"Employees paid\" is not \"employees employed\", and the gap between them is where a missing payslip lives. A month where headcount is flat and cost per head jumps is a different problem from one where both move.",
                 "\"Được trả lương\" không đồng nghĩa với \"đang làm việc\", và khoảng chênh giữa hai con số ấy chính là chỗ một phiếu lương bị thiếu đang nằm. Một tháng có sĩ số đứng yên mà chi phí bình quân nhảy vọt là vấn đề khác hẳn với tháng cả hai cùng thay đổi."),
          when: B("At month end beside Insights, and whenever a run's headcount does not match what you expected.",
                  "Vào cuối tháng, đọc cùng với Phân tích, và bất cứ khi nào sĩ số của một đợt lương không khớp với kỳ vọng của bạn."),
          prereq: B("An analytics group, and at least two runs to compare.",
                    "Quyền phân tích, và ít nhất hai đợt lương để so sánh."),
          mistakes: [
            B("Reading the headcount line as a hiring chart. It counts people who were PAID, so a step in it can equally be a run that left somebody out.",
              "Đọc đường sĩ số như biểu đồ tuyển dụng. Nó đếm những người ĐÃ ĐƯỢC TRẢ LƯƠNG, nên một bậc nhảy trên đó cũng có thể là một đợt lương đã bỏ sót ai đó."),
            B("Taking attendance exceptions as somebody else's problem. Each one becomes an input, and the ones nobody resolved are the flags on next month's payslips.",
              "Coi ngoại lệ chấm công là chuyện của người khác. Mỗi ngoại lệ đều trở thành một dữ liệu đầu vào, và những ngoại lệ không ai xử lý chính là các cờ cảnh báo trên phiếu lương tháng sau."),
          ],
        },
      },
    ],
  },

  /* ---------------------------------------------------------------------------
     THE COMPLIANCE LINE (Phase C1).

     One station, and it is the honest size of the thing: the cockpit is a
     country-aware front door over wizards that already existed. What has to be
     learned is which filings exist for the company's country, that the period
     is a month, and that a country with no tiles is being told the truth rather
     than being broken.
     ------------------------------------------------------------------------ */
  compliance: {
    stations: [
      {
        id: "govreports", icon: "file-text", required: true, mins: 4, after: null,
        title: B("Government Reports", "Báo cáo cơ quan nhà nước"),
        desc: B("The statutory filings for this company's country, one month at a time.",
                "Các báo cáo bắt buộc theo quốc gia của công ty này, mỗi lần một tháng."),
        outline: {
          what: B("A front door over the filing wizards: the report tiles this company's country has, grouped by the authority that asks for them, prefilled with the company and the month you chose.",
                  "Cửa vào các trình lập báo cáo: những biểu mẫu mà quốc gia của công ty này có, nhóm theo cơ quan yêu cầu, và được điền sẵn công ty cùng tháng bạn đã chọn."),
          why: B("Filings have deadlines set by law rather than by the company, and they are read by somebody outside it. This screen is where you find out which ones apply to you without asking who knows.",
                 "Báo cáo bắt buộc có thời hạn do pháp luật ấn định chứ không do doanh nghiệp, và người đọc chúng nằm ngoài doanh nghiệp. Màn hình này cho biết những báo cáo nào áp dụng với bạn mà không phải đi hỏi xem ai biết."),
          when: B("After the month's runs are done and before the authority's deadline — a filing built on an unfinished month is a filing that will have to be corrected.",
                  "Sau khi các đợt lương của tháng đã Hoàn tất và trước hạn nộp của cơ quan — báo cáo lập trên một tháng chưa xong là báo cáo sẽ phải đính chính."),
          prereq: B("Completed runs for the month, and the country's own paperwork rules — Payobook prepares the file, it does not submit it for you.",
                    "Các đợt lương của tháng đã Hoàn tất, và quy định hồ sơ của chính quốc gia đó — Payobook lập tệp, chứ không nộp thay bạn."),
          mistakes: [
            B("Generating from a month whose runs are not all done. The tiles read what has been computed, so an unfinished run is a filing that is short by however many payslips are still in the pipeline.",
              "Kết xuất báo cáo khi các đợt lương của tháng chưa hoàn tất hết. Các biểu mẫu đọc phần đã tính, nên một đợt còn dở là một báo cáo thiếu đúng bằng số phiếu lương còn đang trong quy trình."),
            B("Reading \"coming soon\" as \"Payobook does not do this country\". It means the country's own payroll module is not INSTALLED on this database — Vietnam, Singapore, Thailand, Cambodia and Malaysia all have filings in the catalogue, and each one appears the moment the module that owns its wizard is there. It is an install question, and the answer is a conversation with whoever administers the system.",
              "Hiểu dòng \"sắp có\" thành \"Payobook không hỗ trợ quốc gia này\". Nó chỉ có nghĩa là mô-đun tính lương của quốc gia đó chưa được CÀI trên cơ sở dữ liệu này — Việt Nam, Singapore, Thái Lan, Campuchia và Malaysia đều đã có biểu mẫu trong danh mục, và mỗi bộ sẽ xuất hiện ngay khi mô-đun chứa trình lập báo cáo của nó được cài. Đây là chuyện cài đặt, và câu trả lời nằm ở người quản trị hệ thống."),
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

  /* The RUN totals rather than one payslip — the comparison an approver
     actually makes, and the one place a wrong payslip is invisible. Every
     figure is already in the fixture: RUN.totalNet and the June row on
     PRACTICE.board / PRACTICE.recentRuns, the two headcounts beside them, and
     Hùng's overtime inputs. The 3,100,000 is 4,200,000 minus 1,100,000, before
     tax, which is why it is quoted as overtime and not as net. */
  runJuneJuly: {
    before: {
      h: B("June 2026", "Tháng 6/2026"),
      big: "596,110,000 ₫",
      d: B("47 employees · every gate said yes",
           "47 nhân viên · mọi cổng đã đồng ý"),
    },
    after: {
      h: B("July 2026", "Tháng 7/2026"),
      big: "612,480,000 ₫",
      d: B("48 employees · one payslip flagged, still unanswered",
           "48 nhân viên · một phiếu bị gắn cờ, vẫn chưa được trả lời"),
      delta: B("16,370,000 ₫ more, which is 2.7% on one extra employee. That is a comfortable-looking number, and comfortable-looking numbers are where a single wrong payslip hides best: Hùng's 3,100,000 ₫ of extra overtime sits inside it, and nothing about the total says so.",
               "Nhiều hơn 16.370.000 ₫, tức 2,7% với thêm một nhân viên. Đó là con số trông rất dễ chịu, và những con số dễ chịu chính là nơi một phiếu lương sai ẩn mình tốt nhất: phần tăng ca thêm 3.100.000 ₫ của Hùng nằm gọn trong đó, và con số tổng không hề nói ra điều ấy."),
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
        body: B("The run is now in <b>draft</b> on the Pay Runs board. From here it travels through the Payroll Officer tier, {{hrTierName}}, {{gmTierName}} and then done. Each gate belongs to one group; nobody can skip one, and a rejection at any of them <b>cancels</b> the run — every payslip in it with it — with a written reason on the record.",
                "Đợt lương giờ ở trạng thái <b>Nháp</b> trên bảng Đợt tính lương. Từ đây nó đi qua vòng Chuyên viên tính lương, {{hrTierName}}, {{gmTierName}} rồi Hoàn tất. Mỗi cổng thuộc về một nhóm quyền; không ai bỏ qua được cổng nào, và bị từ chối ở bất kỳ cổng nào cũng <b>huỷ</b> đợt lương — kèm theo toàn bộ phiếu lương trong đó — và ghi lý do bằng văn bản vào hồ sơ."),
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
        body: B("Rejecting <b>cancels</b> the run. Not \"sends it back\" — the run's own state becomes Rejected and every payslip in it is cancelled with it, together, and three things are recorded: who rejected it, when, and <b>why in writing</b>. That written reason is the entire value of the rejection. Without it the officer who has to rebuild the run is guessing at what you saw.",
                "Từ chối là <b>huỷ</b> đợt lương. Không phải \"trả lại\" — trạng thái của chính đợt chuyển thành Đã từ chối và mọi phiếu lương trong đó cùng bị huỷ theo, một lượt, đồng thời ghi lại ba điều: ai từ chối, vào lúc nào, và <b>vì sao, bằng văn bản</b>. Chính lý do bằng văn bản đó mới là giá trị của việc từ chối. Không có nó, chuyên viên phải dựng lại đợt lương chỉ còn cách đoán xem bạn đã thấy gì."),
        consequence: B("Affects the whole run, not one payslip: all 48 are cancelled together and the run reads Rejected. Reversible: <b>not by you</b> — reopening a run as a draft is a {{gmTierName}} action, and until somebody with that tier does it there is nothing for the officer to recompute. Nothing was paid. Verify first: that the problem really is the run, and not a single slip you could have discussed.",
                       "Ảnh hưởng cả đợt lương, không phải một phiếu: cả 48 phiếu cùng bị huỷ và đợt chuyển sang trạng thái Đã từ chối. Hoàn tác: <b>không phải bởi bạn</b> — mở lại một đợt thành bản nháp là thao tác của vòng {{gmTierName}}, và tới khi có người ở vòng đó làm việc ấy thì chuyên viên chẳng có gì để tính lại. Chưa có gì được chi. Kiểm tra trước: vấn đề có thực sự nằm ở cả đợt không, hay chỉ là một phiếu mà bạn có thể trao đổi riêng."),
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
          explanation: B("Let's rethink that. A rejection is testimony about a problem you found, and it CANCELS the run — using it as a scheduling tool puts an untrue reason on the record, throws away two days of somebody's review, and leaves the batch needing a {{gmTierName}} reset before anybody can even recompute it.",
                         "Hãy nghĩ lại một chút. Từ chối là lời chứng về một vấn đề bạn phát hiện, và nó HUỶ đợt lương — dùng nó như công cụ điều phối tiến độ sẽ ghi vào hồ sơ một lý do không đúng sự thật, vứt bỏ hai ngày soát xét của người khác, và để lại một lô cần vòng {{gmTierName}} mở lại thì mới có ai tính lại được."),
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
        tip: B("The code is the thing to quote when you ask someone about a number: \"HOASEN_RETAIL_END, component TNCN\" is a question that can be answered. The shape is PREFIX_DIVISION_CYCLE and the prefix belongs to the company — this practice company uses HOASEN, the Payobook demo world uses DEMO. Learn the shape, not the prefix.",
               "Mã cấu hình là thứ nên trích dẫn khi bạn hỏi ai đó về một con số: \"HOASEN_RETAIL_END, thành phần TNCN\" là một câu hỏi có thể trả lời được. Dạng chung là TIỀN TỐ_BỘ PHẬN_CHU KỲ và tiền tố là của từng công ty — công ty thực hành này dùng HOASEN, môi trường demo của Payobook dùng DEMO. Hãy nhớ dạng chung, đừng nhớ tiền tố."),
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
          explanation: B("Let's rethink that. Computed is not finished: a rejection at any gate cancels the run, and once {{gmTierName}} reopens it the recompute would use the configuration as it is THEN — so July would quietly acquire an allowance that was never approved for it.",
                         "Hãy nghĩ lại một chút. Đã tính không có nghĩa là đã xong: bị từ chối ở bất kỳ cổng nào cũng huỷ đợt lương, và khi vòng {{gmTierName}} mở lại thì lần tính lại sẽ dùng cấu hình TẠI THỜI ĐIỂM ĐÓ — nên tháng 7 âm thầm có thêm một khoản phụ cấp chưa từng được duyệt cho nó."),
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
  /* ===========================================================================
     THE OVERVIEW LINE (Phase C1).

     LW IS THE SUCCESSOR TO pb_coach's `hero_path`, and the succession is a
     change of shape rather than of subject. The tour said the same four things
     about the Dashboard — welcome, the KPIs, formula-driven payroll, the way in
     — as spotlights over the LIVE screen, in English only, with no check at the
     end and nothing recorded when it finished. Here it is a lesson: it runs over
     the practice replica, it ships in both languages, it ends on a judgement
     call rather than a "Done" button, and completion is stored per learner.

     What was ADDED to the tour's narrative, because a first lesson has to leave
     somebody able to work rather than impressed: the monthly loop (a Dashboard
     is a state, and payroll is a cycle), the sidebar map (where the rest of the
     product is), and the meta-step about asking for help — which is the whole
     reason there is a Coach on every screen.

     What was DROPPED: the Formula Studio deep-dive and the pay-run walkthrough.
     Both are full lessons of their own now (L5 and L1), and a welcome that
     rehearses them is a welcome nobody finishes.
     ======================================================================== */
  LW: {
    id: "LW", station: "dashboard", mins: 8,
    title: B("Welcome to your command centre", "Chào mừng tới trung tâm điều hành của bạn"),
    goal: B("Read the Dashboard the way the first ten minutes of a payroll day needs it read — and know where everything else in Payobook lives.",
            "Đọc Bảng điều khiển theo đúng cách mười phút đầu của một ngày làm lương cần — và biết mọi thứ còn lại trong Payobook nằm ở đâu."),
    steps: [
      {
        screen: "dashboard", anchor: "dash-hero",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("The state of payroll, before you choose anything", "Hiện trạng công việc lương, trước khi bạn chọn bất cứ gì"),
        body: B("This is the one screen that answers <b>\"where is payroll right now\"</b> without a filter, a period or a division being picked first. The line under your name is the live run: which one it is, how many payslips it holds, and how many are still waiting on a signature.",
                "Đây là màn hình duy nhất trả lời câu hỏi <b>\"công việc lương đang ở đâu\"</b> mà không cần chọn trước bộ lọc, kỳ lương hay bộ phận nào. Dòng chữ dưới tên bạn là đợt lương đang chạy: đó là đợt nào, có bao nhiêu phiếu lương, và còn bao nhiêu phiếu đang chờ chữ ký."),
        tip: B("Read it before your inbox. An email about payroll is somebody's version of this line; this is the line.",
               "Hãy đọc nó trước khi mở hộp thư. Một email về chuyện lương là phiên bản của ai đó về dòng này; còn đây mới là dòng gốc."),
      },
      {
        screen: "dashboard", anchor: "dash-kpis",
        kicker: B("Reading the band", "Đọc dải chỉ số"),
        title: B("Four numbers, and only one of them is a queue", "Bốn con số, và chỉ một trong số đó là hàng đợi"),
        body: B("Headcount, monthly payroll, pending approval, active configurations. Three of those <b>describe the company</b> and will read almost the same tomorrow. <b>Pending approval</b> is different: it is work that has stopped, and it is the only number here that somebody has to do something about.",
                "Nhân sự, chi phí lương tháng, chờ phê duyệt, cấu hình đang chạy. Ba trong số đó <b>mô tả cả công ty</b> và ngày mai đọc lại gần như vẫn thế. <b>Chờ phê duyệt</b> thì khác: đó là phần việc đang dừng lại, và là con số duy nhất ở đây cần có người xử lý."),
        tip: B("It counts <b>payslips</b> waiting at {{hrTierName}} or {{gmTierName}}, across the whole company — not runs, not the Officer gate, and not yours in particular. How many are yours is a question the Approvals screen answers.",
               "Nó đếm số <b>phiếu lương</b> đang chờ ở {{hrTierName}} hoặc {{gmTierName}}, trên toàn công ty — không phải số đợt lương, không tính cổng Chuyên viên, và cũng không phải riêng phần của bạn. Bao nhiêu trong đó là của bạn thì màn hình Phê duyệt mới trả lời."),
      },
      {
        screen: "dashboard", anchor: "dash-formula",
        kicker: B("What makes this product different", "Điều làm sản phẩm này khác biệt"),
        title: B("Pay is computed from a rulebook you can read", "Lương được tính từ một bộ quy tắc bạn đọc được"),
        body: B("Payobook does not hide its arithmetic behind fixed salary structures. Every line on every payslip comes from a named component in a <b>formula configuration</b> — one per division — written the way a spreadsheet is written and readable by the person who has to explain it. This card is the way in; the Formula Engine lesson is where you take one apart.",
                "Payobook không giấu phép tính của mình sau các cấu trúc lương cố định. Mọi dòng trên mọi phiếu lương đều đến từ một thành phần có tên trong <b>cấu hình công thức</b> — mỗi bộ phận một bộ — được viết như một bảng tính và người phải đi giải thích nó vẫn đọc được. Thẻ này là lối vào; còn bài Công thức lương mới là nơi bạn mổ xẻ một bộ."),
        tip: B("That is why \"why is my pay this number\" has an answer here rather than a promise to look into it.",
               "Đó là lý do câu hỏi \"vì sao lương tôi lại là con số này\" có câu trả lời ngay, chứ không phải một lời hứa sẽ xem lại."),
      },
      {
        screen: "dashboard", anchor: "dash-runpayroll",
        kicker: B("The doors", "Những cánh cửa"),
        title: B("Most doors here lead where the sidebar leads", "Phần lớn cửa ở đây dẫn tới đúng nơi thanh bên dẫn"),
        body: B("The buttons and cards open screens you could have opened anyway. <b>Run Payroll</b> from the hero is the same wizard as the Run Payroll leaf — same rules, same gates, same consequences — and that matters: a dashboard with its own shortcut to computing a run would be a second place a run could be created, with no way to be sure which one made the month. The two <b>Analytics</b> buttons are the exception, and worth knowing about: they open an older reporting screen that has no sidebar leaf at all, so it is the one door here you cannot find your way back to from the menu.",
                "Các nút và thẻ ở đây mở những màn hình mà đằng nào bạn cũng mở được. <b>Chạy bảng lương</b> ở phần đầu chính là trình hướng dẫn của mục Chạy bảng lương — cùng quy tắc, cùng cổng kiểm soát, cùng hậu quả — và điều đó quan trọng: một bảng điều khiển có lối tắt riêng để tính lương sẽ tạo ra nơi thứ hai sinh ra đợt lương, và khi đó không cách nào biết chắc tháng này được tạo từ nơi nào. Hai nút <b>Analytics</b> là ngoại lệ, và rất đáng biết: chúng mở một màn hình báo cáo thế hệ cũ hoàn toàn không có mục nào trên thanh bên, nên đó là cánh cửa duy nhất ở đây mà bạn không tìm lại được từ menu."),
      },
      {
        screen: "dashboard", anchor: "rep-dash-runs",
        kicker: B("The shape of a month", "Hình dạng của một tháng"),
        title: B("Payroll is a loop, not a task", "Tính lương là một vòng lặp, không phải một đầu việc"),
        body: B("Each row here is one month that was imported, computed, reviewed, approved by every gate and paid. The same loop, every month, in the same order — and the reason a run has a <b>state</b> rather than a tick is that the loop can stop at any point in it and somebody has to know where.",
                "Mỗi dòng ở đây là một tháng đã được nhập dữ liệu, tính, soát xét, được mọi cổng phê duyệt và chi trả. Vẫn vòng lặp đó, mỗi tháng, theo đúng thứ tự đó — và lý do một đợt lương có <b>trạng thái</b> thay vì một dấu tích là vì vòng lặp có thể dừng ở bất kỳ điểm nào và phải có người biết nó dừng ở đâu."),
        moment: { kind: "pipeline", chain: "payrun" },
      },
      {
        screen: "dashboard", anchor: "rep-nav",
        kicker: B("Where everything lives", "Mọi thứ nằm ở đâu"),
        /* NO COUNT IN THE TITLE. The replica's menu draws the sections this
           Journey teaches; the real sidebar also carries Workforce, Planning,
           Admin and Learning, and those come and go with what is installed and
           what your groups open. A number here would be wrong for most readers
           and would have to be re-counted every time a section is taught. */
        title: B("Sections, and you only work in two of them", "Các nhóm mục, và bạn chỉ thật sự làm việc trong hai"),
        body: B("<b>Overview</b> is where you land and where approvals queue. <b>Pay Run</b> is the month's work, top to bottom. <b>People</b> holds who can be paid, <b>Insights</b> answers questions about what was paid, <b>Compliance</b> is the filings the authorities ask for, and <b>Setup</b> is read often and changed rarely. A leaf that is not in your sidebar is one your groups do not open — the Journey still describes it, because the person who cannot open a screen is exactly the person who needs to know what it is.",
                "<b>Tổng quan</b> là nơi bạn vào đầu tiên và là nơi các lượt phê duyệt xếp hàng. <b>Chạy lương</b> là toàn bộ công việc của tháng, từ đầu đến cuối. <b>Nhân sự</b> giữ thông tin ai có thể được trả lương, <b>Phân tích</b> trả lời các câu hỏi về những gì đã chi, <b>Tuân thủ</b> là các báo cáo mà cơ quan quản lý yêu cầu, còn <b>Thiết lập</b> thì thường xuyên được đọc và hiếm khi bị sửa. Mục nào không có trong thanh bên của bạn là mục mà nhóm quyền của bạn không mở được — Hành trình học vẫn mô tả nó, vì người không mở được một màn hình chính là người cần biết màn hình đó là gì."),
        tip: B("The menu on the left of this practice screen is the shape of the real one, not a copy of it — your own sidebar also carries a <b>Learning</b> section, which is where the Journey you are reading this in lives.",
               "Menu bên trái màn hình thực hành này mô phỏng hình dạng của menu thật, không phải bản sao của nó — thanh bên của chính bạn còn có nhóm mục <b>Học tập</b>, và đó là nơi chứa Hành trình học mà bạn đang đọc bài này trong đó."),
      },
      {
        screen: "dashboard", anchor: "",
        kicker: B("How to get help", "Cách hỏi khi cần"),
        title: B("There is a Coach on every screen, and it will not act for you", "Mọi màn hình đều có Trợ lý, và nó sẽ không thao tác thay bạn"),
        body: B("The launcher in the bottom-right corner opens on <b>any</b> screen in Payobook, and it answers about the screen you are standing on: what it is, what to do next here, what a tile counts, and what a control would do before you press it. It guides — you act. It never computes a run, approves a payslip or changes a record, and it never invents a rate: every answer it gives is something a person wrote and a test checks.",
                "Nút trợ giúp ở góc dưới bên phải mở được trên <b>mọi</b> màn hình của Payobook, và nó trả lời về đúng màn hình bạn đang đứng: đây là gì, ở đây nên làm gì tiếp, một ô số liệu đang đếm cái gì, và một nút sẽ gây ra điều gì trước khi bạn bấm. Nó hướng dẫn — bạn thao tác. Nó không bao giờ tự tính lương, phê duyệt phiếu lương hay sửa dữ liệu, và cũng không bao giờ bịa ra một tỷ lệ: mọi câu trả lời đều do con người viết và có kiểm thử canh giữ."),
        tip: B("If it has nothing written for a screen it says so. \"I do not have lessons for this screen yet\" is a better answer than a confident one about the wrong screen.",
               "Nếu chưa có nội dung cho một màn hình, nó sẽ nói thẳng. \"Tôi chưa có bài học cho màn hình này\" là câu trả lời tốt hơn một câu chắc nịch nhưng nói về màn hình khác."),
      },
    ],
    quiz: {
      question: B("The Dashboard says <b>48</b> pending approval, and you hold the {{hrTierName}} gate. What does that number tell you about your own morning?",
                  "Bảng điều khiển hiện <b>48</b> lượt chờ phê duyệt, và bạn là người giữ cổng {{hrTierName}}. Con số đó nói gì về buổi sáng của riêng bạn?"),
      options: [
        {
          text: B("Forty-eight runs are waiting for my signature", "Có bốn mươi tám đợt lương đang chờ chữ ký của tôi"),
          correct: false,
          explanation: B("Let's rethink that, twice over. The tile counts <b>payslips</b>, not runs — 48 of them is one ordinary batch — and it counts them company-wide, at {{hrTierName}} and {{gmTierName}} together. Reading a payslip count as a run count is how a normal Tuesday reads like a crisis.",
                         "Hãy nghĩ lại một chút, và có hai điều cần nghĩ lại. Ô đó đếm <b>phiếu lương</b>, không phải đợt lương — 48 phiếu chỉ là một lô bình thường — và đếm trên toàn công ty, gộp cả {{hrTierName}} lẫn {{gmTierName}}. Đọc số phiếu như thể số đợt chính là cách một ngày thứ Ba bình thường trông như một cuộc khủng hoảng."),
        },
        {
          text: B("Forty-eight payslips are waiting somewhere in the HR and Finance tiers, and Approvals will tell me how many are mine", "Có bốn mươi tám phiếu lương đang chờ đâu đó trong vòng HR và Tài chính, và màn hình Phê duyệt sẽ cho biết bao nhiêu là của tôi"),
          correct: true,
          explanation: B("Exactly. The Dashboard reports a company-wide state in payslips; the queue that is YOURS is counted in runs, on its own screen, by the gate your groups let you act on. Reading the state first and the queue second is the order the whole product is built in.",
                         "Chính xác. Bảng điều khiển báo cáo hiện trạng toàn công ty theo số phiếu lương; còn hàng đợi CỦA BẠN được đếm theo đợt, trên màn hình riêng của nó, theo đúng cổng mà nhóm quyền của bạn cho phép xử lý. Đọc hiện trạng trước rồi mới tới hàng đợi là đúng trật tự mà cả sản phẩm này được dựng lên."),
        },
        {
          text: B("Payroll is behind schedule", "Công việc tính lương đang chậm tiến độ"),
          correct: false,
          explanation: B("Let's rethink that. Payslips sitting at a gate mid-month is what a working approval chain looks like — the number only means \"behind\" once you know which gate they are at and how long they have been there, and this tile carries neither.",
                         "Hãy nghĩ lại một chút. Giữa tháng có phiếu lương nằm chờ ở các cổng chính là hình ảnh của một chuỗi phê duyệt đang hoạt động — con số này chỉ có nghĩa là \"chậm\" khi bạn biết chúng đang ở cổng nào và đã nằm đó bao lâu, mà ô này không mang theo điều nào trong hai điều đó."),
        },
      ],
    },
  },

  /* ===========================================================================
     LA — the approval judgement.

     It runs over the APPROVALS replica, whose lanes are the same board rows the
     Pay Runs replica draws: the July Retail run at the Officer gate, and two
     empty lanes behind it. Two of its steps stand on the Payslips replica
     instead, because the judgement this lesson teaches is not made on the
     approvals screen at all — it is made on the payslips inside the run, and
     walking there is the point.
     ======================================================================== */
  LA: {
    id: "LA", station: "approvals", mins: 9,
    title: B("Approve like it's your signature", "Phê duyệt như thể đó là chữ ký của bạn"),
    goal: B("Decide on a run the way somebody who will be asked about it decides: flags first, a sample after, and a variance you can explain in one sentence before you sign.",
            "Ra quyết định trên một đợt lương theo cách của người sẽ bị hỏi lại về nó: xem cờ cảnh báo trước, lấy mẫu sau, và giải thích được biến động trong một câu trước khi ký."),
    steps: [
      {
        screen: "approvals", anchor: "pa-hero",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("This screen is a queue, not a board", "Màn hình này là hàng đợi, không phải bảng theo dõi"),
        body: B("The Pay Runs board shows every run there is. This one shows only the runs a human still has to answer for — and the chip in the corner counts the ones waiting on <b>you</b>. Everything else here is somebody else's signature, shown so you know who to ask rather than so you can do it for them.",
                "Bảng Đợt tính lương hiển thị mọi đợt đang có. Màn hình này chỉ hiển thị những đợt vẫn cần một con người chịu trách nhiệm — và cái chip ở góc đếm số đợt đang chờ <b>bạn</b>. Mọi thứ khác ở đây là chữ ký của người khác, hiển thị ra để bạn biết cần hỏi ai, chứ không phải để bạn ký thay họ."),
      },
      {
        screen: "approvals", anchor: "pa-kpis",
        kicker: B("The number that matters", "Con số đáng chú ý"),
        title: B("Net at stake is money that has not been paid yet", "Số tiền đang treo là khoản chưa được chi"),
        body: B("Three counts, one per gate, and then <b>612,480,000 ₫</b> — the net of every run in the pipeline. It is worth reading as what it is: money that is one or more signatures away from leaving the company's account, and that can still be stopped by anybody who finds a reason to.",
                "Ba con số đếm, mỗi cổng một con số, rồi tới <b>612.480.000 ₫</b> — tổng thực nhận của mọi đợt đang trong quy trình. Rất nên đọc nó đúng bản chất: đây là số tiền chỉ còn cách tài khoản công ty một hoặc vài chữ ký, và bất kỳ ai tìm ra lý do đều còn kịp chặn lại."),
        tip: B("After the last gate that sentence stops being true. A correction to a completed run is a retro line in the next one, never an edit to this one.",
               "Sau cổng cuối cùng thì câu đó không còn đúng nữa. Sửa một đợt đã Hoàn tất là một dòng hồi tố ở kỳ sau, không bao giờ là sửa trực tiếp vào đợt này."),
      },
      {
        screen: "approvals", anchor: "pa-lanes",
        kicker: B("Reading the lanes", "Đọc các làn"),
        title: B("A lane is a gate, and an empty one is not a fault", "Mỗi làn là một cổng, và làn trống không phải là lỗi"),
        body: B("Officer review, then {{hrTierName}}, then {{gmTierName}}. A run sits in the lane of the gate it is waiting at, so the lane <b>names the person to chase</b>. Two of the three are empty here, and that is what most days look like — a lane fills when work reaches it and empties when somebody signs.",
                "Chuyên viên soát, rồi {{hrTierName}}, rồi {{gmTierName}}. Một đợt lương nằm ở làn của cổng nó đang chờ, nên làn đó <b>chỉ đích danh người cần hỏi</b>. Ở đây hai trên ba làn đang trống, và phần lớn các ngày đều như vậy — một làn chỉ đầy khi công việc tới đó và trống trở lại khi có người ký."),
        tip: B("A card offers Approve and Reject only at the gate you hold. If you cannot see them, you are looking at somebody else's work, and pressing harder will not help.",
               "Một thẻ chỉ hiện nút Phê duyệt và Từ chối ở đúng cổng bạn đang giữ. Không thấy hai nút đó nghĩa là bạn đang nhìn phần việc của người khác, và bấm mạnh hơn cũng không giúp được gì."),
      },
      {
        screen: "payslips", anchor: "ps-chips",
        kicker: B("The strategy", "Cách làm"),
        title: B("Nobody reads forty-eight payslips, and nobody should", "Không ai đọc hết bốn mươi tám phiếu lương, và cũng không nên"),
        body: B("Reading top to bottom is how a flagged payslip gets approved at six in the evening. The engine has already told you which ones it could not settle on its own — start there, then <b>sample</b> two or three it did not flag. A flag marks the unusual, not the wrong, so a clean slip can still be incorrect and a flagged one can be perfectly fine.",
                "Đọc lần lượt từ trên xuống chính là cách một phiếu bị gắn cờ được duyệt vào sáu giờ chiều. Hệ thống đã chỉ ra những phiếu nó không tự quyết được — hãy bắt đầu từ đó, rồi <b>lấy mẫu</b> hai ba phiếu không bị gắn cờ. Cờ đánh dấu điều bất thường, không phải điều sai, nên một phiếu sạch vẫn có thể sai và một phiếu bị gắn cờ vẫn có thể hoàn toàn ổn."),
        tip: B("Sampling is not a shortcut. It is how you find out whether the flags are the only problem — and if a sampled slip is wrong, the flags were never the point.",
               "Lấy mẫu không phải là làm tắt. Đó là cách để biết các cờ cảnh báo có phải vấn đề duy nhất hay không — và nếu một phiếu lấy mẫu bị sai thì hoá ra các cờ chưa bao giờ là điều đáng lo nhất."),
      },
      {
        screen: "payslips", anchor: "ps-breakdown",
        kicker: B("Before & after", "Trước & sau"),
        title: B("Explain the variance, or you are not ready to sign", "Giải thích được biến động, nếu không thì bạn chưa nên ký"),
        body: B("July is 612,480,000 ₫ against June's 596,110,000 ₫ — run totals, which live on the board and the KPI band rather than on the slip in front of you. This step stands here anyway, because the answer does: toggle the two and say, out loud, why they differ — one more employee, and one payslip with 3,100,000 ₫ more overtime on it than last month. If you cannot finish that sentence, the gap is not small; it is unexamined.",
                "Tháng 7 là 612.480.000 ₫ so với 596.110.000 ₫ của tháng 6 — đây là tổng của cả đợt, nằm trên bảng và dải chỉ số chứ không nằm trên phiếu lương trước mặt bạn. Bước này vẫn đứng ở đây, vì câu trả lời nằm ở đây: hãy chuyển qua lại hai bên và nói thành lời vì sao chúng khác nhau — thêm một nhân viên, và một phiếu lương có tăng ca nhiều hơn tháng trước 3.100.000 ₫. Nếu bạn chưa nói trọn được câu đó thì khoảng chênh này không phải nhỏ; nó chỉ là chưa được soi tới."),
        moment: { kind: "morph", which: "runJuneJuly" },
      },
      {
        screen: "approvals", anchor: "pa-reject",
        kicker: B("The hard part", "Phần khó"),
        title: B("A rejection is testimony, and the reason is required", "Từ chối là lời chứng, và lý do là bắt buộc"),
        body: B("Rejecting <b>cancels the whole run</b> — all 48 payslips together, never one — and records three things against it: who rejected it, when, and <b>why in writing</b>. The product refuses an empty reason, because without it the officer who has to rebuild the run is guessing at what you saw. And rejecting is not the officer's undo: only the {{gmTierName}} tier can reopen a run as a draft.",
                "Từ chối sẽ <b>huỷ cả đợt lương</b> — toàn bộ 48 phiếu cùng lúc, không bao giờ chỉ một phiếu — và ghi lại ba điều: ai từ chối, vào lúc nào, và <b>vì sao, bằng văn bản</b>. Sản phẩm không cho để trống lý do, vì thiếu nó thì chuyên viên phải dựng lại đợt lương chỉ còn cách đoán xem bạn đã thấy gì. Và từ chối không phải là nút hoàn tác của chuyên viên: chỉ vòng {{gmTierName}} mới mở lại một đợt thành bản nháp được."),
        tip: B("\"Payslip NV0031 — overtime is 382% of June, verify against the timesheet\" is a reason somebody can act on. \"Wrong\" is a reason somebody has to interpret.",
               "\"Phiếu NV0031 — tăng ca bằng 382% tháng 6, hãy đối chiếu bảng chấm công\" là lý do người khác xử lý được. Còn \"sai\" là lý do người khác phải tự đoán ý."),
      },
      {
        screen: "approvals", anchor: "pa-lanes",
        kicker: B("Before you act", "Trước khi thao tác"),
        title: B("Approving is a signature, and it moves real money", "Phê duyệt là một chữ ký, và nó làm tiền thật dịch chuyển"),
        body: B("Nothing about the button says so, which is why this step does. Pressing Approve moves 48 payslips one gate closer to being paid, together — there is no way to approve some of them — and the gate after yours checks totals rather than lines. If a wrong line is going to be caught, this is one of the last places it can be.",
                "Cái nút không hề nói ra điều đó, nên bước này phải nói. Bấm Phê duyệt là đẩy 48 phiếu lương tiến thêm một cổng tới lúc được chi, cùng một lúc — không có cách nào duyệt một phần — và cổng sau bạn kiểm tra các con số tổng chứ không kiểm tra từng dòng. Nếu một dòng sai còn có thể bị bắt, thì đây là một trong những nơi cuối cùng bắt được."),
        consequence: B("Affects the whole run, all 48 payslips together. It moves from your gate to the next one. Reversible: <b>stoppable, not undoable</b> — a later reviewer can still reject it, which cancels the batch rather than handing it back, and after done even that is gone: a correction is then a retro line. Verify first: every flagged payslip opened, a few unflagged ones sampled, and a one-sentence explanation of the variance against last month.",
                       "Ảnh hưởng cả đợt lương, toàn bộ 48 phiếu cùng lúc. Đợt chuyển từ cổng của bạn sang cổng kế tiếp. Hoàn tác: <b>chặn được, chứ không lùi lại được</b> — người soát xét sau vẫn có thể từ chối, và điều đó huỷ cả lô chứ không phải trả nó lại cho bạn; sau khi Hoàn tất thì đến cách đó cũng không còn: mọi hiệu chỉnh khi ấy là một dòng hồi tố. Kiểm tra trước: đã mở mọi phiếu bị gắn cờ, đã lấy mẫu vài phiếu không gắn cờ, và giải thích được biến động so với tháng trước trong một câu."),
      },
      {
        screen: "approvals", anchor: "pa-recent",
        kicker: B("Afterwards", "Sau khi quyết"),
        title: B("Whatever you decide is written down with your name on it", "Bạn quyết thế nào thì điều đó cũng được ghi lại kèm tên bạn"),
        body: B("Approvals and rejections land in the same list, and a rejection keeps its written reason where the next person can read it. That is not surveillance — it is the reason a payroll month can be defended six months later, when nobody remembers the conversation and the record is all there is.",
                "Phê duyệt và từ chối cùng rơi vào một danh sách, và một lần từ chối vẫn giữ nguyên lý do bằng văn bản ở nơi người sau đọc được. Đó không phải là giám sát — đó là lý do một kỳ lương vẫn bảo vệ được sau sáu tháng, khi không ai còn nhớ cuộc trao đổi nào và chỉ còn lại hồ sơ."),
      },
    ],
    quiz: {
      question: B("A run is waiting at your gate. The total is 2.7% above last month, one payslip is flagged and nobody has opened it, and payday is {{payDay}}. What do you do?",
                  "Một đợt lương đang chờ ở cổng của bạn. Tổng cao hơn tháng trước 2,7%, một phiếu bị gắn cờ và chưa ai mở nó, và ngày trả lương là {{payDay}}. Bạn làm gì?"),
      options: [
        {
          text: B("Approve — 2.7% against last month is well within normal", "Phê duyệt — 2,7% so với tháng trước là hoàn toàn bình thường"),
          correct: false,
          explanation: B("Let's rethink that. A total that looks reasonable is not evidence that every slip inside it is: one payslip with 3,100,000 ₫ of extra overtime sits comfortably inside a 2.7% move. The flag was raised about one employee, and approving without opening it is answering that question with silence.",
                         "Hãy nghĩ lại một chút. Tổng trông hợp lý không phải bằng chứng rằng từng phiếu bên trong đều hợp lý: một phiếu có tăng ca thêm 3.100.000 ₫ nằm gọn trong mức biến động 2,7%. Cờ được giương lên về một nhân viên cụ thể, và duyệt mà không mở nó ra là trả lời câu hỏi đó bằng sự im lặng."),
        },
        {
          text: B("Open the flagged payslip, and decide once you can say in one sentence why the total moved", "Mở phiếu bị gắn cờ, và chỉ quyết định khi nói được trong một câu vì sao con số tổng thay đổi"),
          correct: true,
          explanation: B("Yes. That sentence is the whole test, and it takes minutes: one more employee, and one payslip with far more overtime than last month. Once you can say it you can approve with your eyes open — or reject with something the officer can act on.",
                         "Đúng vậy. Chính câu nói đó là toàn bộ phép thử, và nó chỉ tốn vài phút: thêm một nhân viên, và một phiếu lương có tăng ca nhiều hơn hẳn tháng trước. Khi nói được câu đó, bạn có thể duyệt một cách tỉnh táo — hoặc từ chối kèm một lý do mà chuyên viên xử lý được."),
        },
        {
          text: B("Reject it so the officer re-checks everything before payday", "Từ chối để chuyên viên kiểm tra lại toàn bộ trước ngày trả lương"),
          correct: false,
          explanation: B("Let's rethink that. Rejecting CANCELS all 48 payslips and puts a reason on the permanent record — and \"please check everything\" is not a reason anybody can act on. Worse, the officer cannot simply pick the run back up: reopening it as a draft is a {{gmTierName}} action. A rejection is testimony about a problem you found, not a way of asking somebody to go looking for one.",
                         "Hãy nghĩ lại một chút. Từ chối sẽ HUỶ cả 48 phiếu lương và ghi một lý do vào hồ sơ vĩnh viễn — mà \"vui lòng kiểm tra lại toàn bộ\" thì không phải lý do ai xử lý được. Tệ hơn, chuyên viên không thể tự nhặt đợt lương đó lên làm tiếp: mở lại nó thành bản nháp là thao tác của vòng {{gmTierName}}. Từ chối là lời chứng về một vấn đề bạn đã phát hiện, không phải cách nhờ người khác đi tìm xem có vấn đề gì không."),
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
      reversible: B("Stoppable at this gate rather than undoable: the next reviewer can still reject it, which cancels the whole batch — and reopening a cancelled run as a draft is a {{gmTierName}} action. At done even that is gone, and a correction becomes a retro line.",
                    "Ở cổng này thì chặn được chứ không lùi lại được: người soát xét kế tiếp vẫn có thể từ chối, và điều đó huỷ cả lô — còn mở lại một đợt đã bị từ chối thành bản nháp là thao tác của vòng {{gmTierName}}. Khi đã Hoàn tất thì đến cách đó cũng không còn, và mọi hiệu chỉnh trở thành một dòng hồi tố."),
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
        B("Watched a rejection cancel the batch, and found out who has to reopen it — so the cost of that decision is something you have seen rather than been told.",
          "Xem một lần từ chối huỷ cả lô, và biết được ai mới là người mở lại nó — để cái giá của quyết định ấy là điều bạn đã tận mắt thấy chứ không phải chỉ nghe kể."),
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
      reversible: B("Partly, and the halves matter. Draft payslips can be deleted and recomputed as often as you like. Submitting is not silently undoable: from there the run moves only by being approved, or by being rejected — which cancels the batch and needs the {{gmTierName}} tier to reopen it as a draft. The same chain a real payroll travels.",
                    "Một phần, và ranh giới rất quan trọng. Phiếu lương nháp có thể xoá và tính lại bao nhiêu lần tuỳ ý. Trình phê duyệt thì không thể âm thầm hoàn tác: từ đó đợt lương chỉ đi tiếp bằng cách được duyệt, hoặc bị từ chối — mà từ chối là huỷ cả lô và cần vòng {{gmTierName}} mở lại thành bản nháp. Đúng chuỗi mà một kỳ lương thật đi qua."),
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
          "Mọi phiếu bị gắn cờ đã được mở và hiểu rõ. Cờ là một câu hỏi về một nhân viên cụ thể, và việc trình phê duyệt chính là bạn trả lời câu hỏi đó."),
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
      instruction: B("Now stop it: reject the run you just submitted", "Giờ hãy chặn lại: từ chối đợt lương bạn vừa trình"),
      detail: B("A submitted run can still be STOPPED, and that is not the same as undone. Rejecting cancels the whole batch — all 48 payslips with it — and records your reason. Getting a workable draft back afterwards is a {{gmTierName}} action, not yours. Do it once here, so that on a real run you already know both halves: that there is a way to stop money moving, and what it costs the people who have to restart it.",
                "Một đợt đã trình vẫn CHẶN được, và điều đó không giống với hoàn tác. Từ chối sẽ huỷ cả lô — kèm toàn bộ 48 phiếu lương — và ghi lại lý do của bạn. Còn để có lại một bản nháp làm việc được thì đó là thao tác của vòng {{gmTierName}}, không phải của bạn. Hãy làm một lần ở đây, để khi gặp đợt lương thật bạn đã biết cả hai vế: rằng có cách chặn dòng tiền lại, và cái giá của nó với những người phải khởi động lại."),
      hint: B("The card's action footer offers Reject while the run is in the chain. That is the same control a reviewer uses — which is why it is worth feeling how blunt it is before somebody else uses it on your run.",
              "Phần chân thẻ hiện nút Từ chối khi đợt lương còn trong chuỗi. Đó chính là nút mà người soát xét dùng — nên rất đáng cảm nhận xem nó thô đến mức nào, trước khi có người dùng nó lên đợt lương của bạn."),
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
      instruction: B("Watch what a rejection actually costs", "Xem một lần từ chối thực sự tốn những gì"),
      detail: B("The run now reads <b>Rejected</b> and all 48 payslips are cancelled with it, your reason on the record. It does NOT come back by itself: reopening it as a draft is a {{gmTierName}} action, and only then can the officer correct the input, recompute and resubmit through the same chain. Nothing was paid — but a rejection costs a second person's time as well as the officer's, which is exactly why the reason has to be worth acting on.",
                "Đợt lương giờ ở trạng thái <b>Đã từ chối</b> và cả 48 phiếu lương bị huỷ theo, kèm lý do của bạn trong hồ sơ. Nó KHÔNG tự quay lại: mở lại thành bản nháp là thao tác của vòng {{gmTierName}}, và chỉ sau đó chuyên viên mới sửa được dữ liệu đầu vào, tính lại và trình lại qua đúng chuỗi đó. Chưa có gì được chi — nhưng một lần từ chối tốn thời gian của cả người thứ hai chứ không chỉ của chuyên viên, và đó chính là lý do lý do phải đáng để người ta hành động."),
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
              "Hãy mở bảng chi tiết của một phiếu và đi từ lương cơ bản tới thực nhận. Nếu bạn nói được mỗi dòng đến từ đâu thì bạn đã sẵn sàng để trình đợt lương lên duyệt."),
    },
    {
      id: "submit", nav: "payruns", check: "june_run_submitted",
      instruction: B("Submit the run for approval", "Trình đợt lương lên phê duyệt"),
      detail: B("This is the step that stops being reversible in the easy way. After it, the run moves only by being approved at each gate, or by being rejected — and a rejection cancels the batch rather than handing it back to you.",
                "Đây là bước mà việc hoàn tác không còn dễ dàng nữa. Sau bước này, đợt lương chỉ đi tiếp bằng cách được duyệt ở từng cổng, hoặc bị từ chối — và từ chối là huỷ cả lô chứ không phải trả nó lại cho bạn."),
      hint: B("Submitting is you saying the flags have been answered. If any of them have not, go back — the run will still be there.",
              "Trình lên phê duyệt là bạn tuyên bố rằng các cờ cảnh báo đã được trả lời. Nếu còn cờ nào chưa, hãy quay lại — đợt lương vẫn nằm đó."),
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

  /* -- Overview, People, Insights, Compliance (Phase C1) ------------------ */
  dashboard: {
    blurb: B("The command centre: the live run, four numbers that describe the company, and a card for each part of the product worth opening today.",
             "Trung tâm điều hành: đợt lương đang chạy, bốn con số mô tả cả công ty, và một thẻ cho từng phần của sản phẩm đáng mở hôm nay."),
    next: B("Read the line under your name first — it names the live run and how much of it is still waiting. Then open the section the work is actually in; nothing on this screen is a second way of doing anything.",
            "Hãy đọc dòng ngay dưới tên bạn trước — nó cho biết đợt lương đang chạy và còn bao nhiêu phần đang chờ. Rồi mở đúng nhóm mục chứa phần việc đó; không thứ gì trên màn hình này là một cách làm thứ hai."),
    chips: ["whatpage", "wherelives", "whatnext", "practice"],
  },
  approvals: {
    blurb: B("Every submitted run in the lane of the gate it is waiting at, with the net at stake across all of them.",
             "Mọi đợt đã trình phê duyệt, nằm ở làn của cổng nó đang chờ, kèm tổng số tiền đang treo trên tất cả."),
    next: B("Read the count in the header — that is the part of this queue only you can move. Then open the run rather than deciding from its card: the total is on the card and the flags are on the payslips.",
            "Hãy đọc con số ở tiêu đề — đó là phần hàng đợi chỉ bạn mới đẩy đi được. Rồi mở đợt lương ra thay vì quyết định ngay trên thẻ: con số tổng nằm trên thẻ, còn cờ cảnh báo nằm trên từng phiếu lương."),
    chips: ["howmanyslips", "variance", "rejectright", "whichlane", "approve"],
  },
  employees: {
    blurb: B("The people roster: contract status, the monthly wage bill, and whether each person can actually be paid.",
             "Danh sách nhân sự: tình trạng hợp đồng, quỹ lương tháng, và liệu từng người có thực sự nhận được lương hay không."),
    next: B("Filter to the people who are not payroll-ready and clear them before the run, not after it. Somebody with no bank account computes perfectly and is still not paid.",
            "Hãy lọc ra những người chưa sẵn sàng tính lương và xử lý trước khi chạy đợt lương, đừng để sau. Người chưa có tài khoản ngân hàng vẫn được tính lương hoàn hảo mà vẫn không nhận được tiền."),
    chips: ["payrollready", "whopays", "whosees", "whatnext"],
  },
  contracts: {
    blurb: B("Every contract with its type, its period and its wage — the agreements payroll is actually computed from.",
             "Từng hợp đồng kèm loại, thời hạn và mức lương — chính là những thoả thuận mà hệ thống lương dựa vào để tính."),
    next: B("Read the expiring filter before the run. A contract that ends mid-month is a proration nobody asked for, and one still in draft pays nothing at all.",
            "Hãy xem bộ lọc sắp hết hạn trước khi chạy lương. Hợp đồng kết thúc giữa tháng là một lần tính theo ngày công mà không ai yêu cầu, còn hợp đồng còn ở Nháp thì không trả gì cả."),
    chips: ["expirysoon", "whopays", "prorata", "whatpage"],
  },
  insights: {
    blurb: B("Executive analytics from the stored per-run roll-ups: the cost story, the department leaderboard, the statutory split and the analytics snapshots.",
             "Phân tích tổng hợp dựng từ các số tổng đã lưu theo từng đợt: diễn biến chi phí, xếp hạng bộ phận, cơ cấu đóng bắt buộc và các ảnh chụp phân tích."),
    next: B("Read the state chip beside the headline before you quote it — the hero is the latest run whatever state it is in, while the leaderboard below waits for a done one. Then compare cost per head rather than total against total: headcount moves between months, and one more employee explains most of what looks like a rise.",
            "Hãy đọc chip trạng thái bên cạnh con số nổi bật trước khi trích nó — phần đầu lấy đợt gần nhất bất kể trạng thái, trong khi bảng xếp hạng bên dưới chờ đợt đã hoàn tất. Rồi hãy so chi phí bình quân đầu người thay vì đem tổng so với tổng: sĩ số thay đổi giữa các tháng, và thêm một nhân viên là đủ giải thích phần lớn cái vẻ \"tăng\" đó."),
    chips: ["whichtool", "variance", "whatpage", "whatnext"],
  },
  explorer: {
    blurb: B("A question builder over derived fact tables that reconcile to the payslip lines: one measure, one breakdown, the filters that scope them — and a waterfall that explains a movement.",
             "Công cụ đặt câu hỏi trên các bảng dữ liệu dẫn xuất khớp với từng dòng phiếu lương: một chỉ tiêu, một chiều tách, các bộ lọc giới hạn phạm vi — và một biểu đồ phân rã giải thích biến động."),
    next: B("Choose the measure before the filters — most wrong answers here are the right filter on the wrong measure. And quote the tags with the number: the same measure with one tag removed is a different figure that looks identical in an email.",
            "Hãy chọn chỉ tiêu trước rồi mới tới bộ lọc — phần lớn câu trả lời sai ở đây là lọc đúng nhưng chọn nhầm chỉ tiêu. Và khi trích con số thì trích kèm các thẻ lọc: cùng chỉ tiêu đó, gỡ một thẻ đi là một con số khác, mà trong email thì trông y hệt."),
    chips: ["whichtool", "whatpage", "whatnext"],
  },
  workforcean: {
    blurb: B("The same months read as people: headcount paid, joiners and leavers, attendance exceptions and cost per head.",
             "Vẫn những tháng đó nhưng đọc theo con người: số người được trả lương, người vào và người nghỉ, ngoại lệ chấm công và chi phí bình quân đầu người."),
    next: B("Read the headcount line as employees PAID, not employed. A step in it is a joiner wave, a leaver wave — or a run that left somebody out, which is the one worth checking.",
            "Hãy đọc đường sĩ số là số người ĐƯỢC TRẢ LƯƠNG, không phải số người đang làm việc. Một bậc nhảy trên đó là một nhóm người mới vào, một nhóm người nghỉ việc — hoặc một kỳ lương đã bỏ sót ai đó, và đó mới là điều đáng kiểm tra."),
    // `prorata` was the third chip here and was filler: it is scoped to the
    // payslip-arithmetic screens, so it resolved to nothing at all on this
    // one — a suggested question that answers with a miss. `whatnext` renders
    // this screen's own next_step, which is the genuinely useful thing to read
    // here (employees PAID, not employed), and is the same third chip
    // govreports uses for the same reason.
    chips: ["whichtool", "whatpage", "whatnext"],
  },
  govreports: {
    blurb: B("The statutory filings this company's country asks for, grouped by authority and prefilled for one month.",
             "Các báo cáo bắt buộc mà quốc gia của công ty này yêu cầu, nhóm theo cơ quan và điền sẵn cho một tháng."),
    next: B("Check that the month's runs have all reached done before you generate anything. The tiles read what has been computed, so an unfinished run is a filing that is short.",
            "Hãy kiểm tra mọi đợt lương của tháng đã đạt Hoàn tất trước khi kết xuất bất cứ gì. Các biểu mẫu đọc phần đã tính, nên một đợt còn dở là một báo cáo bị thiếu."),
    chips: ["whichfilings", "whatpage", "whatnext"],
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
    // UPGRADED IN PHASE 1b, and to a STEP rather than to the scenario: the
    // walkthrough ends on the salary breakdown, and somebody asking why one
    // person's pay moved wants that step, not the board it opens on. The
    // fragment is a step KEY and not an index, so inserting a step in the
    // middle of the walkthrough cannot silently re-point it somewhere else.
    showMe: ["scenario:sc_payslips#breakdown", "ps-breakdown"],
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
    /* Phase C1 added "approvals" to the screen list. The Approvals cockpit is
       where approving now actually happens, and a capability-aware answer that
       is unreachable on the screen the action lives on is content nobody can
       find. Same for `reject` below. */
    id: "approve", screens: ["payruns", "payslips", "approvals"],
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
          { t: B("Approve — or reject with a written reason, which cancels the run", "Phê duyệt — hoặc từ chối kèm lý do bằng văn bản, việc đó sẽ huỷ đợt lương"), a: "pk-card-actions" },
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
    id: "reject", screens: ["payruns", "approvals"],
    label: B("What happens if I reject a run?", "Nếu tôi từ chối một đợt thì điều gì xảy ra?"),
    match: ["how do i reject", "reject the run", "send it back", "từ chối đợt lương", "tra lai dot luong"],
    showMe: ["pk-card-actions"],
    blocks: [
      { k: "p", v: B("The whole run is <b>cancelled</b> — all 48 payslips together, never one — its state becomes Rejected, and three things are recorded against it: who rejected it, when, and why in writing.",
                     "Cả đợt lương bị <b>huỷ</b> — toàn bộ 48 phiếu cùng lúc, không bao giờ chỉ một phiếu — trạng thái chuyển thành Đã từ chối, và ba điều được ghi lại: ai từ chối, vào lúc nào, và vì sao, bằng văn bản.") },
      { k: "steps", v: [
        { t: B("Open the run at the gate you hold", "Mở đợt lương ở cổng bạn đang giữ"), a: "pk-tabs" },
        { t: B("Reject, and write a reason that names the payslip and what to check", "Từ chối, và viết lý do nêu rõ phiếu nào và cần kiểm tra gì"), a: "pk-card-actions" },
        { t: B("Somebody at the {{gmTierName}} tier reopens the cancelled run as a draft — this is the part people expect to be automatic and is not", "Một người ở vòng {{gmTierName}} mở lại đợt đã huỷ thành bản nháp — đây là khâu người ta hay tưởng là tự động, nhưng không phải") },
        { t: B("Only then does the officer correct the input, recompute and resubmit through the same chain", "Sau đó chuyên viên mới sửa dữ liệu đầu vào, tính lại và trình lại qua đúng chuỗi đó") },
      ] },
      { k: "warn", v: B("Nothing was paid, but this is blunter than it looks: the batch is cancelled, not handed back, and it takes a second person at the {{gmTierName}} tier before the officer can even start. A reason like \"wrong\" costs all of that and a day of guessing.",
                        "Chưa có gì được chi, nhưng thao tác này thô hơn vẻ ngoài của nó: cả lô bị huỷ chứ không phải được trả lại, và phải có người thứ hai ở vòng {{gmTierName}} thì chuyên viên mới bắt đầu lại được. Một lý do kiểu \"sai\" khiến người ta trả toàn bộ cái giá đó cộng thêm cả ngày đoán mò.") },
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
    label: B("Will this affect a run that is already submitted?", "Việc này có ảnh hưởng đợt đã trình phê duyệt không?"),
    match: ["affect the current run", "will this change", "ảnh hưởng đợt đang chạy", "co anh huong dot da trinh"],
    blocks: [
      { k: "ok", v: B("No. What you do here reaches drafts only — the division and period you are working on. A run that has been submitted or approved cannot be touched from here at all.",
                      "Không. Những gì bạn làm ở đây chỉ chạm tới bản nháp — đúng bộ phận và kỳ bạn đang làm. Một đợt đã trình hoặc đã duyệt thì hoàn toàn không thể bị tác động từ đây.") },
      { k: "p", v: B("Safe: recomputing a draft, deleting a draft, importing again into an open period. Gated: everything after submission, which moves only through the approval chain — or a rejection, which cancels the run outright.",
                     "An toàn: tính lại bản nháp, xoá bản nháp, nhập lại vào một kỳ còn mở. Có cổng chặn: mọi thứ sau khi đã trình, chỉ đi được qua chuỗi phê duyệt — hoặc bị từ chối, mà từ chối là huỷ thẳng đợt lương.") },
      { k: "src", v: B("The pay run state chain, and what each state allows.",
                       "Chuỗi trạng thái của đợt lương, và mỗi trạng thái cho phép làm gì.") },
    ],
  },

  {
    id: "confidence", screens: ["import", "importwizard"],
    label: B("What does the confidence score mean?", "Điểm tin cậy nghĩa là gì?"),
    match: ["confidence score", "what does the score mean", "diem tin cay", "điểm tin cậy là gì", "import score"],
    // UPGRADED IN PHASE 1b. The confidence score is not a control to point
    // at, it is a process to watch: convert, score, fix, and only then
    // commit — which is exactly the three steps of sc_import.
    showMe: ["scenario:sc_import", "iw-review"],
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
    // `contracts` is here because the Contracts screen's own next_step raises
    // proration by name — "a contract that ends mid-month is a proration
    // nobody asked for" — so "how was this part-month salary worked out" is
    // the direct follow-up to the thing that screen tells you to look for, and
    // this answer is what that reader needs. It is NOT on workforcean: that
    // screen counts people, and an answer about one person's base times a
    // factor does not belong to a question anybody asks there.
    id: "prorata", screens: ["proration", "payslips", "fullfinal", "contracts"],
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
      { k: "p", v: B("One per division and cycle, and the code says which. The shape is <b>PREFIX_DIVISION_CYCLE</b>: a prefix that belongs to the company, the division, then <b>END</b> for the end-of-month settlement or <b>MID</b> for a mid-cycle advance. On the demo world that reads DEMO_RETAIL_END, DEMO_LOGISTICS_MID and so on — one naming rule, twelve configurations. On the practice company in the lessons the same rule reads HOASEN_RETAIL_END; the prefix changes, the shape does not.",
                     "Mỗi bộ phận và mỗi chu kỳ có một cấu hình, và chính mã cho biết là cái nào. Dạng chung là <b>TIỀN TỐ_BỘ PHẬN_CHU KỲ</b>: một tiền tố thuộc về công ty, rồi tên bộ phận, rồi <b>END</b> cho quyết toán cuối tháng hoặc <b>MID</b> cho khoản tạm ứng giữa kỳ. Trên bản demo, mã đọc là DEMO_RETAIL_END, DEMO_LOGISTICS_MID và tương tự — một quy ước đặt tên, mười hai cấu hình. Trên công ty thực hành trong các bài học, cùng quy ước đó đọc là HOASEN_RETAIL_END; tiền tố đổi, còn dạng chung thì không.") },
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
  /* ===========================================================================
     OVERVIEW / PEOPLE / INSIGHTS / COMPLIANCE INTENTS (Phase C1).

     Appended rather than interleaved, for the same reason the Setup block was:
     the generator writes records in this order, so inserting into the middle
     renames every intent record id after the insertion point for no content
     reason.
     ======================================================================== */
  {
    id: "wherelives", screens: ["dashboard", "employees", "insights"],
    label: B("Where do I find things in Payobook?", "Tìm các chức năng trong Payobook ở đâu?"),
    match: ["where is everything", "where do i find", "sidebar sections", "what are the sections",
            "tim o dau", "menu nam o dau", "cac nhom muc"],
    // UPGRADED IN PHASE 1b, and it fixes a real bug as well as improving the
    // answer: `rep-nav` is a PRACTICE-ONLY anchor, so on the real Dashboard
    // this button could only ever report "that control is not on this
    // screen". "Where does everything live" is a question a walkthrough
    // answers and a point-at cannot.
    showMe: ["scenario:sc_welcome", "rep-nav"],
    blocks: [
      { k: "p", v: B("Six sections, and you work in two of them most days. <b>Overview</b> is where you land and where approvals queue. <b>Pay Run</b> is the month's work end to end. <b>People</b> holds who can be paid, <b>Insights</b> answers questions about what was paid, <b>Compliance</b> is the filings, and <b>Setup</b> is read often and changed rarely.",
                     "Sáu nhóm mục, và phần lớn các ngày bạn chỉ làm việc trong hai nhóm. <b>Tổng quan</b> là nơi bạn vào đầu tiên và là nơi các lượt phê duyệt xếp hàng. <b>Chạy lương</b> là toàn bộ công việc của tháng từ đầu tới cuối. <b>Nhân sự</b> giữ thông tin ai có thể được trả lương, <b>Phân tích</b> trả lời các câu hỏi về những gì đã chi, <b>Tuân thủ</b> là các báo cáo bắt buộc, còn <b>Thiết lập</b> thì thường xuyên được đọc và hiếm khi bị sửa.") },
      { k: "steps", v: [
        { t: B("Overview — the Dashboard you land on, and the Approvals queue", "Tổng quan — Bảng điều khiển bạn vào đầu tiên, và hàng đợi Phê duyệt"), a: "dash-hero" },
        { t: B("Pay Run — run payroll, the board, the payslips, the import", "Chạy lương — chạy bảng lương, bảng đợt lương, phiếu lương, nhập dữ liệu"), a: "pw-rail" },
        { t: B("People — employees and the contracts payroll is computed from", "Nhân sự — nhân viên và các hợp đồng mà hệ thống lương dựa vào để tính"), a: "pe-kpis" },
        { t: B("Insights — what was paid, and the Explorer for the questions the board did not anticipate", "Phân tích — những gì đã chi, và Explorer cho các câu hỏi mà bảng không lường trước"), a: "in-hero" },
        { t: B("Setup — the formula configurations and the statutory rates behind every figure", "Thiết lập — các cấu hình công thức và tỷ lệ luật định đứng sau mọi con số"), a: "fs-components" },
      ] },
      { k: "ok", v: B("A leaf that is not in your sidebar is one your groups do not open. The Journey still describes it — the person who cannot open a screen is exactly the person who needs to know what it is before asking for access.",
                      "Mục nào không có trong thanh bên của bạn là mục mà nhóm quyền của bạn không mở được. Hành trình học vẫn mô tả nó — người không mở được một màn hình chính là người cần biết màn hình đó là gì trước khi đi xin quyền.") },
      { k: "src", v: B("Your own sidebar, as the product renders it for your groups.",
                       "Chính thanh bên của bạn, đúng như sản phẩm hiển thị theo nhóm quyền của bạn.") },
    ],
  },

  {
    id: "whichlane", screens: ["approvals", "payruns"],
    label: B("Who is holding this run up?", "Ai đang giữ đợt lương này lại?"),
    match: ["who is holding it up", "who do i chase", "whose gate is it at", "who has to approve next",
            "ai dang giu", "phai hoi ai", "dot luong tac o dau"],
    showMe: ["pa-lanes"],
    blocks: [
      { k: "p", v: B("The lane a run is sitting in names the tier that has to act next — Officer review, then {{hrTierName}}, then {{gmTierName}}. That is the answer to \"who do I chase\", and it is more reliable than asking, because the record decides it rather than a memory of who said they would look.",
                     "Làn mà một đợt lương đang nằm chỉ đích danh vòng phải xử lý tiếp theo — Chuyên viên soát, rồi {{hrTierName}}, rồi {{gmTierName}}. Đó chính là câu trả lời cho \"tôi phải hỏi ai\", và nó đáng tin hơn việc đi hỏi, vì chính bản ghi quyết định điều đó chứ không phải trí nhớ về việc ai đã hứa sẽ xem.") },
      { k: "p", v: B("A card offers Approve and Reject only at the gate you hold. If you cannot see those buttons on a run, it is not yours to move — and pressing harder will not change that, because the buttons are decided by the record's own gate fields and your groups.",
                     "Một thẻ chỉ hiện nút Phê duyệt và Từ chối ở đúng cổng bạn đang giữ. Nếu bạn không thấy hai nút đó trên một đợt lương thì đợt đó không phải phần việc của bạn — và bấm mạnh hơn cũng không đổi được, vì các nút do chính các trường kiểm soát cổng của bản ghi và nhóm quyền của bạn quyết định.") },
      { k: "warn", v: B("A run in draft is not waiting for a signature at all. It is waiting for whoever computes it to submit it, and it does not appear in these lanes until they do.",
                        "Một đợt còn ở Nháp thì không hề chờ chữ ký nào. Nó đang chờ người tính lương trình lên, và nó chưa xuất hiện trong các làn này cho tới khi việc đó được làm.") },
      { k: "src", v: B("The approval lane the run is in, and the gate fields on its own record.",
                       "Làn phê duyệt mà đợt lương đang nằm, và các trường kiểm soát cổng trên chính bản ghi đó.") },
    ],
  },

  {
    id: "howmanyslips", screens: ["approvals", "payslips", "payruns"],
    label: B("How many payslips should I read?", "Tôi nên đọc bao nhiêu phiếu lương?"),
    match: ["how many payslips do i read", "do i have to read every payslip", "sampling strategy",
            "doc bao nhieu phieu", "co phai doc het khong", "lay mau phieu luong"],
    showMe: ["ps-chips", "pa-lanes"],
    practice: "m2",
    simpler: B("Not all of them. The system has already marked the ones it was unsure about — read those first, then pick two or three ordinary ones at random to make sure the ordinary ones are fine too.",
               "Không phải tất cả. Hệ thống đã đánh dấu sẵn những phiếu mà nó không chắc — hãy đọc những phiếu đó trước, rồi chọn ngẫu nhiên hai ba phiếu bình thường để chắc rằng các phiếu bình thường cũng ổn."),
    blocks: [
      { k: "p", v: B("Not forty-eight. Reading top to bottom is how a flagged payslip gets approved at six in the evening — the engine has already told you which ones it could not settle on its own, and those are where the judgement is.",
                     "Không phải bốn mươi tám phiếu. Đọc lần lượt từ trên xuống chính là cách một phiếu bị gắn cờ được duyệt vào sáu giờ chiều — hệ thống đã chỉ ra những phiếu nó không tự quyết được, và phần cần phán đoán nằm ở đó.") },
      { k: "steps", v: [
        { t: B("Filter to \"Need review\" and open every one of them", "Lọc theo \"Cần soát xét\" và mở từng phiếu một"), a: "ps-chips" },
        { t: B("Sample two or three the engine did NOT flag", "Lấy mẫu hai ba phiếu mà hệ thống KHÔNG gắn cờ"), a: "ps-list" },
        { t: B("Read one breakdown end to end — base to net — so you know the shape of a normal slip", "Đọc trọn một bảng chi tiết — từ lương cơ bản tới thực nhận — để nắm hình dạng của một phiếu bình thường"), a: "ps-breakdown" },
        { t: B("Compare the run's total against last month and say why it moved", "So tổng của đợt với tháng trước và nói được vì sao nó thay đổi"), a: "ps-kpis" },
      ] },
      { k: "warn", v: B("A flag marks the unusual, not the wrong. A clean payslip can still be incorrect and a flagged one can be perfectly fine — which is why the sample matters as much as the flags do.",
                        "Cờ cảnh báo đánh dấu điều bất thường, không phải điều sai. Một phiếu sạch vẫn có thể sai và một phiếu bị gắn cờ vẫn có thể hoàn toàn ổn — nên phần lấy mẫu quan trọng ngang với phần xem cờ.") },
      { k: "src", v: B("The run's flagged payslips, and the filter chips on the payslip review screen.",
                       "Các phiếu bị gắn cờ của đợt lương, và các chip lọc trên màn hình soát xét phiếu lương.") },
    ],
  },

  {
    id: "variance", screens: ["approvals", "payslips", "insights", "payruns"],
    label: B("Is this variance normal?", "Biến động thế này có bình thường không?"),
    match: ["explain the variance", "the total moved", "why is the run bigger",
            "bien dong co binh thuong", "tong thay doi", "giai thich chenh lech"],
    showMe: ["ps-kpis", "in-trend"],
    blocks: [
      { k: "p", v: B("\"Normal\" is not a percentage — it is whether you can finish the sentence. On this run: July is 612,480,000 ₫ against June's 596,110,000 ₫, a rise of 2.7% on one more employee, and one payslip carries 3,100,000 ₫ more overtime than it did last month.",
                     "\"Bình thường\" không phải là một con số phần trăm — mà là việc bạn có nói trọn được câu giải thích hay không. Trên đợt này: tháng 7 là 612.480.000 ₫ so với 596.110.000 ₫ của tháng 6, tăng 2,7% với thêm một nhân viên, và một phiếu lương có tăng ca nhiều hơn tháng trước 3.100.000 ₫.") },
      { k: "warn", v: B("A comfortable-looking total is where a single wrong payslip hides best. Three million đồng sits invisibly inside a 2.7% move, and nothing about the total says so — the flags do.",
                        "Một con số tổng trông dễ chịu chính là nơi một phiếu lương sai ẩn mình tốt nhất. Ba triệu đồng nằm vô hình trong mức biến động 2,7%, và con số tổng không hề nói ra điều đó — các cờ cảnh báo mới nói.") },
      { k: "steps", v: [
        { t: B("Headcount first — one more employee explains most of what looks like a rise", "Xem sĩ số trước — thêm một nhân viên là đủ giải thích phần lớn cái vẻ tăng đó"), a: "ps-kpis" },
        { t: B("Then overtime, which moves with the month rather than with the contract", "Rồi tới tăng ca, thứ thay đổi theo tháng chứ không theo hợp đồng"), a: "ps-breakdown" },
        { t: B("Then the flags, one at a time, because a total cannot show you those", "Rồi tới từng cờ cảnh báo một, vì con số tổng không cho bạn thấy chúng"), a: "ps-chips" },
      ] },
      { k: "src", v: B("The run's net total against the previous month's, and the payslips underneath both.",
                       "Tổng thực nhận của đợt so với tháng trước, và các phiếu lương nằm dưới cả hai con số đó.") },
    ],
  },

  {
    id: "rejectright", screens: ["approvals", "payruns"],
    label: B("How do I write a rejection reason?", "Viết lý do từ chối thế nào cho đúng?"),
    match: ["what should the reason say", "good rejection note",
            "viet ly do tra lai", "ghi ly do the nao", "ly do tu choi viet gi"],
    showMe: ["pa-reject"],
    blocks: [
      { k: "p", v: B("Name the payslip, name the figure, and name what you want checked. \"Payslip NV0031 — overtime 4,200,000 ₫ is 382% of June. Please verify against the timesheet and resubmit.\" is a reason somebody can act on today.",
                     "Nêu rõ phiếu nào, con số nào, và bạn muốn kiểm tra điều gì. \"Phiếu NV0031 — tăng ca 4.200.000 ₫ bằng 382% tháng 6. Vui lòng đối chiếu bảng chấm công và trình lại.\" là lý do người khác xử lý được ngay hôm nay.") },
      { k: "warn", v: B("\"Wrong\", \"please recheck\" and \"the numbers look off\" all cancel 48 payslips, need a {{gmTierName}} reset before anybody can start again, and leave the officer guessing at what you saw. They will probably rebuild the same thing, and the second rejection is the one that becomes an argument.",
                        "\"Sai\", \"kiểm tra lại giúp\" hay \"số liệu trông không ổn\" đều huỷ 48 phiếu lương, cần vòng {{gmTierName}} mở lại thì mới có ai bắt đầu lại được, và để chuyên viên tự đoán xem bạn đã thấy gì. Nhiều khả năng họ sẽ dựng lại đúng thứ cũ, và lần từ chối thứ hai mới là lần biến thành tranh cãi.") },
      { k: "ok", v: B("The reason is stored with your name and the time and stays on the record. That is what makes a payroll month defensible six months later, when nobody remembers the conversation.",
                      "Lý do được lưu kèm tên bạn và thời điểm, và ở lại trên bản ghi. Chính điều đó khiến một kỳ lương vẫn bảo vệ được sau sáu tháng, khi không ai còn nhớ cuộc trao đổi nào.") },
      { k: "src", v: B("The rejection fields on the pay run record: the note, who wrote it and when.",
                       "Các trường từ chối trên bản ghi đợt lương: nội dung lý do, ai viết và viết lúc nào.") },
    ],
  },

  {
    id: "payrollready", screens: ["employees", "runpayroll"],
    label: B("Why is somebody not payroll-ready?", "Vì sao một người chưa sẵn sàng tính lương?"),
    match: ["not payroll ready", "why can this person not be paid", "readiness tick",
            "chua san sang tinh luong", "vi sao chua tra luong duoc", "dau san sang"],
    showMe: ["pe-roster", "pe-kpis"],
    blocks: [
      { k: "p", v: B("On a ROW it means both things are present: a running contract, and bank details the payment file can use. Miss either and the payslip still computes perfectly and the money still does not arrive. The tick tells you which one is missing — hover it.",
                     "Trên một DÒNG, nó nghĩa là có đủ cả hai thứ: một hợp đồng đang hiệu lực, và thông tin ngân hàng mà tệp chi lương dùng được. Thiếu một trong hai thì phiếu lương vẫn tính hoàn hảo và tiền vẫn không tới nơi. Dấu tích cho biết đang thiếu thứ nào — hãy rê chuột lên nó.") },
      { k: "warn", v: B("The percentage in the KPI band is NOT that test. It counts bank details only, over headcount — so it can read 100% while somebody on a draft contract is still going to be missing from the run. The band is a trend; the rows are the answer.",
                        "Tỷ lệ phần trăm ở dải chỉ số KHÔNG dùng phép thử đó. Nó chỉ đếm thông tin ngân hàng, chia cho sĩ số — nên nó vẫn có thể hiện 100% trong khi một người đang ở hợp đồng nháp sẽ vắng mặt trong đợt lương. Dải chỉ số cho thấy xu hướng; các dòng mới cho câu trả lời.") },
      { k: "warn", v: B("This is the failure with the longest gap between cause and symptom: the run looks finished, the reports reconcile, and the person tells you on {{payDay}}.",
                        "Đây là kiểu lỗi có khoảng cách dài nhất giữa nguyên nhân và triệu chứng: đợt lương trông đã xong, báo cáo vẫn khớp, và người đó báo cho bạn vào {{payDay}}.") },
      { k: "steps", v: [
        { t: B("Filter the roster to the people who are not ready", "Lọc danh sách theo những người chưa sẵn sàng"), a: "pe-filters" },
        { t: B("Read what each one is missing — the row says which fact it is", "Đọc từng người đang thiếu gì — dòng đó ghi rõ thiếu dữ kiện nào"), a: "pe-roster" },
        { t: B("Fix it on the employee or the contract, not on the payslip afterwards", "Sửa trên hồ sơ nhân viên hoặc hợp đồng, đừng sửa trên phiếu lương về sau"), a: "ct-roster" },
      ] },
      { k: "src", v: B("The payroll-ready mark on the employee roster, and the contract behind it.",
                       "Dấu sẵn sàng tính lương trên danh sách nhân viên, và hợp đồng đứng sau nó.") },
    ],
  },

  {
    id: "expirysoon", screens: ["contracts", "employees"],
    label: B("A contract expires mid-month — what happens?", "Hợp đồng hết hạn giữa tháng thì sao?"),
    match: ["contract expires mid month", "expiring contract", "renewal not signed yet",
            "hop dong het han giua thang", "gia han chua ky", "het han hop dong"],
    showMe: ["ct-roster", "ct-filters"],
    blocks: [
      { k: "p", v: B("Payroll computes from the contract, so it pays up to the day the contract ends and prorates the month around it. That is correct behaviour, and it is a surprise to everybody who was expecting a full month.",
                     "Hệ thống lương tính theo hợp đồng, nên nó trả tới đúng ngày hợp đồng kết thúc và tính phần tháng đó theo ngày công. Đó là hành vi đúng, và là điều bất ngờ với bất kỳ ai đang chờ một tháng lương đầy đủ.") },
      { k: "warn", v: B("A renewal that is still in <b>draft</b> on the run date is worse: a draft contract pays nothing at all, and the employee simply is not in the run. Draft is the state to hunt for in the week before payroll.",
                        "Một hợp đồng gia hạn còn ở trạng thái <b>Nháp</b> vào ngày chạy lương thì còn tệ hơn: hợp đồng nháp không trả gì cả, và nhân viên đó đơn giản là không có trong đợt lương. Nháp là trạng thái cần lùng cho ra trong tuần trước kỳ lương.") },
      { k: "p", v: B("Both cases are visible before the run and expensive after it. The expiring filter on this screen is a two-minute check; a missed renewal is a retro line next month and a conversation this one.",
                     "Cả hai trường hợp đều nhìn thấy được trước khi chạy lương và đều đắt sau đó. Bộ lọc sắp hết hạn trên màn hình này chỉ tốn hai phút; còn một lần quên gia hạn là một dòng hồi tố vào tháng sau và một cuộc trao đổi ngay tháng này.") },
      { k: "src", v: B("The contract's own period and state, and the expiring filter over the roster.",
                       "Thời hạn và trạng thái của chính hợp đồng, và bộ lọc sắp hết hạn trên danh sách.") },
    ],
  },

  {
    id: "whopays", screens: ["employees", "contracts", "payslips"],
    label: B("Who can change what somebody is paid?", "Ai được sửa mức lương của một người?"),
    match: ["who can change a salary", "can i change someone pay", "edit a wage",
            "sua muc luong", "doi luong nhan vien", "ai duoc sua luong"],
    showMe: ["ct-roster"],
    roleVariants: {
      any: [
        { k: "p", v: B("A wage is changed on the <b>contract</b>, never on a payslip. The payslip is a result: correcting it leaves the agreement behind it unchanged, and the next recompute quietly puts the old figure back.",
                       "Mức lương được sửa trên <b>hợp đồng</b>, không bao giờ sửa trên phiếu lương. Phiếu lương là kết quả: sửa nó thì thoả thuận phía sau vẫn nguyên như cũ, và lần tính lại kế tiếp âm thầm đưa con số cũ quay lại.") },
        { k: "warn", v: B("A change on a running contract applies from now on — it moves the registered insurance base with it, and it corrects nothing that has already been paid. The past is a retro line.",
                          "Một thay đổi trên hợp đồng đang hiệu lực chỉ áp dụng từ nay về sau — nó kéo theo mức lương đóng bảo hiểm đã đăng ký, và không sửa được gì đã trả. Quá khứ phải xử lý bằng một dòng hồi tố.") },
        { k: "src", v: B("The contract record, and the retro adjustment ledger for anything already paid.",
                         "Bản ghi hợp đồng, và sổ điều chỉnh hồi tố cho những gì đã chi.") },
      ],
      operator: [
        { k: "p", v: B("You can open the contract and read it. Whether you can save a new wage on it depends on your groups, and on most companies that decision belongs a tier above payroll — a wage is an HR agreement that payroll executes.",
                       "Bạn mở được hợp đồng và đọc nó. Còn lưu được mức lương mới hay không thì tuỳ nhóm quyền của bạn, và ở phần lớn công ty, quyết định đó thuộc về một cấp trên bộ phận lương — mức lương là thoả thuận nhân sự, còn bộ phận lương là bên thực thi.") },
        { k: "steps", v: [
          { t: B("Open the person on the Employees roster", "Mở đúng người trên danh sách Nhân viên"), a: "pe-roster" },
          { t: B("Read the contract behind them — the wage lives there", "Đọc hợp đồng phía sau họ — mức lương nằm ở đó"), a: "ct-roster" },
          { t: B("Recompute the draft run afterwards, so the payslip follows the contract", "Sau đó tính lại đợt lương nháp, để phiếu lương đi theo hợp đồng"), a: "pw-compute" },
        ] },
        { k: "src", v: B("The contract record, and your group membership.",
                         "Bản ghi hợp đồng, và nhóm quyền của bạn.") },
      ],
      no_access: [
        { k: "refusal", v: B("Not from here. The Employees and Contracts screens are not in your menu, so there is no wage for you to change and no button you are missing.",
                             "Không phải từ đây. Màn hình Nhân viên và Hợp đồng không có trong menu của bạn, nên không có mức lương nào để bạn sửa và cũng không có nút nào bạn đang thiếu.") },
        { k: "who", v: B("A payroll officer or above can read the contract; saving a new wage on it is usually held a tier higher again, because it is an HR agreement rather than a payroll setting.",
                         "Chuyên viên tính lương trở lên có thể đọc hợp đồng; còn lưu một mức lương mới thường thuộc về một cấp cao hơn nữa, vì đó là thoả thuận nhân sự chứ không phải một thiết lập của bộ phận lương.") },
        { k: "how", v: B("Ask {{payrollSupportContact}}. A wage list is not something everybody in a company should be able to read, so expect to be asked what you need it for.",
                         "Hãy hỏi {{payrollSupportContact}}. Danh sách lương không phải thứ ai trong công ty cũng nên đọc được, nên hãy chuẩn bị trả lời bạn cần nó để làm gì.") },
        { k: "src", v: B("Your sidebar, and the groups the People leaves are gated on.",
                         "Thanh bên của bạn, và các nhóm quyền mà mục Nhân sự bị chặn theo.") },
      ],
    },
  },

  {
    id: "whosees", screens: ["employees", "contracts", "insights"],
    label: B("Who can see this wage list?", "Ai được xem danh sách lương này?"),
    match: ["who can see salaries", "is this list private", "who has access to wages",
            "ai xem duoc danh sach luong", "danh sach nay co rieng tu khong", "quyen xem luong"],
    blocks: [
      { k: "p", v: B("Whoever holds one of the three payroll groups these leaves are gated on — a payroll officer, a payroll manager or a super administrator. Read that as a <b>ladder</b>, not a list: a role carries every group it implies, so a super administrator is also a manager and a manager is also an officer. Everybody else does not see a greyed-out screen; they do not have the leaf in their sidebar at all.",
                     "Những ai giữ một trong ba nhóm quyền lương mà các mục này bị chặn theo — chuyên viên tính lương, quản lý lương hoặc quản trị viên cấp cao. Hãy hiểu đó là một <b>bậc thang</b> chứ không phải một danh sách: một vai trò mang theo mọi nhóm mà nó bao hàm, nên quản trị viên cấp cao cũng là quản lý lương và quản lý lương cũng là chuyên viên tính lương. Người khác không thấy một màn hình bị làm mờ; họ không hề có mục đó trong thanh bên của mình.") },
      { k: "p", v: B("The ladder has a consequence worth knowing before you rely on it. A <b>final approver</b> is not named on these leaves, and sees the roster anyway: that role implies the analytics manager, which implies the payroll manager. So approving a total and reading everybody's salary are <b>not</b> separated here. If your company needs them separated — a person who signs for the money without seeing the names — that is a change somebody has to make, not a promise the shipped roles already keep.",
                     "Bậc thang này có một hệ quả nên biết trước khi bạn dựa vào nó. <b>Người phê duyệt cuối</b> không được nêu tên trên các mục này, nhưng vẫn xem được danh sách: vai trò đó bao hàm quản lý phân tích lương, mà quản lý phân tích lương lại bao hàm quản lý lương. Vậy nên ở đây, việc duyệt một con số tổng và việc đọc lương của từng người <b>không</b> hề được tách ra. Nếu công ty bạn cần tách hai việc đó — một người ký cho khoản tiền mà không nhìn thấy tên ai — thì đó là việc phải làm thêm, chứ không phải điều mà bộ vai trò mặc định đã hứa.") },
      { k: "p", v: B("Who is genuinely outside it: a payroll analytics user, whose role implies only the base payroll user, so they get the boards without the names; a payroll base user, who has their own payslip and nothing else; and anyone whose only payroll group is a country toggle. None of them can open Employees or Contracts from the menu.",
                     "Ai thực sự nằm ngoài: người dùng phân tích lương — vai trò này chỉ bao hàm người dùng lương cơ bản, nên họ có các bảng số liệu mà không có tên; người dùng lương cơ bản, chỉ có phiếu lương của chính mình; và bất kỳ ai mà nhóm quyền lương duy nhất là một công tắc bật theo quốc gia. Không ai trong số đó mở được Nhân viên hay Hợp đồng từ thanh bên.") },
      { k: "ok", v: B("That is the right shape for this data. A wage list answers questions nobody asked about colleagues, and hiding the door is a stronger promise than disabling a button on it.",
                      "Đó là cách làm đúng với loại dữ liệu này. Một danh sách lương trả lời những câu hỏi chẳng ai đặt ra về đồng nghiệp, và giấu hẳn cánh cửa là một cam kết mạnh hơn việc chỉ vô hiệu hoá một cái nút trên đó.") },
      { k: "warn", v: B("Exporting it moves the data somewhere none of that applies. A spreadsheet of salaries has no groups on it and no way to be taken back.",
                        "Xuất nó ra là đưa dữ liệu tới nơi mà mọi quy tắc trên không còn áp dụng. Một bảng tính lương thì không mang theo nhóm quyền nào và cũng không có cách nào thu hồi.") },
      { k: "src", v: B("The groups on the People sidebar leaves, the chain of implied groups those roles are declared with, and your own group membership.",
                       "Các nhóm quyền trên những mục Nhân sự ở thanh bên, chuỗi nhóm bao hàm mà các vai trò đó được khai báo, và nhóm quyền của chính bạn.") },
    ],
  },

  {
    id: "whichtool", screens: ["insights", "explorer", "workforcean"],
    label: B("Insights or Explorer — which one answers this?", "Phân tích hay Explorer — cái nào trả lời được?"),
    match: ["insights or explorer", "which analytics screen", "board or explorer",
            "dung phan tich hay explorer", "man hinh phan tich nao", "cong cu nao tra loi"],
    showMe: ["in-hero", "ex-rail"],
    simpler: B("Use the board when your question is one that comes up every month, and the Explorer when it is not. The board has the answers somebody already thought of; the Explorer lets you ask for one nobody did.",
               "Dùng bảng phân tích khi câu hỏi của bạn là câu tháng nào cũng gặp, và dùng Explorer khi không phải vậy. Bảng chứa những câu trả lời đã có người nghĩ trước; còn Explorer cho bạn hỏi một câu chưa ai nghĩ tới."),
    blocks: [
      { k: "p", v: B("<b>Insights</b> answers the questions a payroll month asks every time: what did it cost, is that a trend, which department carries it, how much of it is statutory. <b>Explorer</b> answers the one you thought of this morning — you pick the measure and the breakdown yourself.",
                     "<b>Phân tích</b> trả lời những câu hỏi mà tháng lương nào cũng đặt ra: tốn bao nhiêu, đó có phải xu hướng không, bộ phận nào gánh phần lớn, bao nhiêu trong đó là khoản bắt buộc. <b>Explorer</b> trả lời câu hỏi bạn vừa nghĩ ra sáng nay — bạn tự chọn chỉ tiêu và chiều tách.") },
      { k: "p", v: B("<b>Workforce Analytics</b> is the third and it asks a different kind of question: not what payroll cost, but who was in it. Headcount paid, joiners and leavers, attendance exceptions, cost per head.",
                     "<b>Phân tích nhân sự</b> là công cụ thứ ba và nó đặt một loại câu hỏi khác: không phải chi phí lương là bao nhiêu, mà là những ai nằm trong đó. Số người được trả lương, người vào và người nghỉ, ngoại lệ chấm công, chi phí bình quân đầu người.") },
      { k: "p", v: B("Knowing WHERE each one reads from is what stops you comparing two numbers that were never the same number. <b>Insights</b> reads the stored per-run roll-ups, plus the analytics snapshots panel. <b>Explorer</b> reads derived fact tables, rebuilt from the payslips and reconciled to them. <b>Workforce Analytics</b> reads the attendance, overtime and leave models. Three lineages, one payroll.",
                     "Biết mỗi công cụ ĐỌC TỪ ĐÂU là điều giúp bạn không đem so hai con số vốn chưa bao giờ là cùng một con số. <b>Phân tích</b> đọc các số tổng đã lưu theo từng đợt, cộng thêm bảng ảnh chụp phân tích. <b>Explorer</b> đọc các bảng dữ liệu dẫn xuất, được dựng lại từ phiếu lương và đối chiếu khớp với phiếu lương. <b>Phân tích nhân sự</b> đọc dữ liệu chấm công, tăng ca và nghỉ phép. Ba nguồn gốc, một hệ thống lương.") },
      { k: "ok", v: B("Explorer does explain <b>why</b>, and it is the only one that does: it builds a variance waterfall between two comparable periods that reconciles exactly, with an anomaly rail beside it — and any cell drills straight through to the employees behind it, read from the payslip lines rather than from the facts, so the drill doubles as the audit trail for the number.",
                      "Explorer có giải thích <b>vì sao</b>, và là công cụ duy nhất làm được: nó dựng một biểu đồ phân rã biến động giữa hai kỳ so sánh được, khớp chính xác từng đồng, kèm một dải cảnh báo bất thường bên cạnh — và bấm vào ô nào cũng đi thẳng xuống danh sách nhân viên đứng sau ô đó, đọc từ chính các dòng phiếu lương chứ không từ bảng dẫn xuất, nên bước đi sâu ấy cũng chính là vết kiểm toán cho con số.") },
      { k: "warn", v: B("What none of them can do is tell you a number is WRONG. A waterfall explains where a movement came from; whether that movement should have happened is a question for the division's configuration and the payslips themselves.",
                        "Điều mà không công cụ nào làm được là nói cho bạn biết một con số SAI. Biểu đồ phân rã giải thích một biến động đến từ đâu; còn biến động đó có nên xảy ra hay không lại là câu hỏi dành cho cấu hình của bộ phận và cho chính các phiếu lương.") },
      { k: "src", v: B("The stored run roll-ups behind Insights, the derived fact tables behind Explorer, and the attendance models behind Workforce Analytics.",
                       "Các số tổng đã lưu theo đợt đứng sau Phân tích, các bảng dữ liệu dẫn xuất đứng sau Explorer, và các mô hình chấm công đứng sau Phân tích nhân sự.") },
    ],
  },

  {
    id: "whichfilings", screens: ["govreports"],
    label: B("Which filings does my company have to submit?", "Công ty tôi phải nộp những báo cáo nào?"),
    match: ["which filings do we submit", "what reports does the government want", "statutory filings list",
            "phai nop bao cao nao", "bao cao bat buoc gom nhung gi", "mau bieu nop cho co quan"],
    showMe: ["gr-grid", "gr-countries"],
    blocks: [
      { k: "p", v: B("Whichever ones your company's <b>country</b> has, and nothing else. The tiles are chosen by the active company's country rather than by what Payobook can produce — a Vietnamese company sees the BHXH forms and the labour-change declarations, and a company somewhere else sees that country's set.",
                     "Đúng những biểu mẫu mà <b>quốc gia</b> của công ty bạn có, không hơn. Các ô biểu mẫu được chọn theo quốc gia của công ty đang hoạt động chứ không theo những gì Payobook có thể tạo ra — một công ty Việt Nam thấy các mẫu BHXH và các tờ khai biến động lao động, còn công ty ở nơi khác thấy bộ biểu mẫu của quốc gia đó.") },
      { k: "steps", v: [
        { t: B("Choose the month — the period control here is a month, not a date range", "Chọn tháng — ô kỳ ở đây là một tháng, không phải một khoảng ngày"), a: "gr-head" },
        { t: B("Check every run in that month has reached done before generating anything — on the Pay Runs board, not here", "Kiểm tra mọi đợt lương của tháng đó đã đạt Hoàn tất trước khi kết xuất bất cứ gì — trên bảng Đợt tính lương, không phải ở đây") },
        { t: B("Generate the tile you need — it opens the company's existing wizard, prefilled", "Kết xuất biểu mẫu bạn cần — nó mở đúng trình hướng dẫn sẵn có của công ty, đã điền sẵn"), a: "gr-grid" },
      ] },
      { k: "warn", v: B("A filing built from a month whose runs are not all done is short by however many payslips are still in the pipeline — and it is the authority, not Payobook, that will notice.",
                        "Một báo cáo lập từ tháng mà các đợt lương chưa hoàn tất hết sẽ thiếu đúng bằng số phiếu lương còn đang trong quy trình — và bên phát hiện ra sẽ là cơ quan quản lý, không phải Payobook.") },
      { k: "p", v: B("\"Coming soon\" on a country means its payroll module is not INSTALLED here — not that the filings do not exist. Vietnam, Singapore, Thailand, Cambodia and Malaysia are all in the catalogue, and a country's tiles appear as soon as the module holding its wizard is installed. So that message is an installation question for whoever administers the system, not a limit of the product. Either way Payobook prepares the file — it does not submit it for you.",
                     "Dòng \"sắp có\" ở một quốc gia nghĩa là mô-đun tính lương của quốc gia đó chưa được CÀI ở đây — chứ không phải các biểu mẫu không tồn tại. Việt Nam, Singapore, Thái Lan, Campuchia và Malaysia đều có trong danh mục, và biểu mẫu của một quốc gia sẽ xuất hiện ngay khi mô-đun chứa trình lập báo cáo của nó được cài. Vậy nên thông báo đó là câu hỏi về cài đặt dành cho người quản trị hệ thống, không phải giới hạn của sản phẩm. Dù thế nào thì Payobook cũng chỉ lập tệp — chứ không nộp thay bạn.") },
      { k: "src", v: B("The country report catalogue behind this cockpit, and the active company's country.",
                       "Danh mục biểu mẫu theo quốc gia đứng sau màn hình này, và quốc gia của công ty đang hoạt động.") },
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
  /* -- Overview, People, Insights, Compliance (Phase C1) ----------------- */
  dashboard: [
    ["headcount",
     B("Headcount", "Sĩ số"),
     B("Everybody the company currently employs, whether or not they were in the last run. It describes the company rather than the month, so it will read almost the same tomorrow — a figure to notice when it MOVES, not one to act on today.",
       "Toàn bộ nhân sự công ty đang có, bất kể họ có nằm trong đợt lương gần nhất hay không. Con số này mô tả cả công ty chứ không mô tả tháng, nên ngày mai đọc lại gần như vẫn thế — đây là con số đáng chú ý khi nó THAY ĐỔI, không phải con số để xử lý hôm nay.")],
    ["monthly_payroll",
     B("Monthly payroll", "Chi phí lương tháng"),
     B("The personnel cost of the current month, as computed so far. It is a cost figure rather than a payment figure: money still sitting in an unapproved run is counted here and has not left the company.",
       "Chi phí nhân sự của tháng hiện tại, theo phần đã tính tới lúc này. Đây là con số chi phí chứ không phải con số đã chi: khoản tiền còn nằm trong một đợt chưa được duyệt vẫn được tính vào đây và chưa hề rời khỏi công ty.")],
    ["pending_approval",
     B("Pending approval", "Chờ phê duyệt"),
     B("How many PAYSLIPS are waiting at the HR or Finance tier, company-wide — not runs, and not the Officer gate, which this tile does not count at all. It is a state, not your queue: how many are YOURS is a question the Approvals screen answers, in runs, and confusing the two means chasing work that was never yours.",
       "Có bao nhiêu PHIẾU LƯƠNG đang chờ ở vòng HR hoặc Tài chính, trên toàn công ty — không phải số đợt lương, và cũng không tính cổng Chuyên viên, ô này hoàn toàn không đếm cổng đó. Đây là một hiện trạng, không phải hàng đợi của bạn: bao nhiêu là CỦA BẠN thì màn hình Phê duyệt mới trả lời, và trả lời theo số đợt; nhầm lẫn hai thứ khiến bạn đi giục những phần việc vốn không phải của mình.")],
    /* "Active configs" — the tile's caption in pb_dashboard.xml, verbatim. A
       column glossary is looked up BY LABEL, so a tidier wording than the
       product's is an entry the Coach can never match. */
    ["active_configs",
     B("Active configs", "Cấu hình đang chạy"),
     B("How many formula configurations are switched on — normally one per division and cycle. A number that has grown without anybody adding a division is worth opening: an old configuration left active can still be selected by a run.",
       "Có bao nhiêu cấu hình công thức đang được bật — thường là mỗi bộ phận và mỗi chu kỳ một bộ. Con số tăng lên mà không ai thêm bộ phận nào là điều đáng mở ra xem: một cấu hình cũ còn để bật vẫn có thể bị một đợt lương chọn phải.")],
  ],

  approvals: [
    ["at_officer_review",
     B("At Officer review", "Ở vòng Chuyên viên"),
     B("Runs sitting at the first gate, waiting for the Payroll Officer to sign. A run only reaches this lane by being submitted, so anything still in draft is not counted here and is not waiting for anybody.",
       "Các đợt đang nằm ở cổng đầu tiên, chờ Chuyên viên tính lương ký. Một đợt chỉ tới được làn này khi đã được trình lên, nên đợt còn ở Nháp thì không được tính vào đây và cũng không chờ ai cả.")],
    ["at_hr_review",
     B("At HR review", "Ở vòng HR"),
     B("Runs the Officer has already passed, waiting at {{hrTierName}}. The lane names the tier that has to act next, which makes it the answer to \"who do I chase\" rather than a status word.",
       "Các đợt đã qua vòng Chuyên viên, đang chờ ở {{hrTierName}}. Làn này chỉ đích danh vòng phải xử lý tiếp theo, nên nó là câu trả lời cho \"tôi phải hỏi ai\" chứ không chỉ là một từ mô tả trạng thái.")],
    ["at_finance_approval",
     B("At Finance approval", "Ở vòng Tài chính"),
     B("The last gate before done. A run here has been read twice already, which is exactly why the reading at this tier is about totals rather than lines — and why a wrong line has to have been caught earlier.",
       "Cổng cuối cùng trước khi Hoàn tất. Một đợt ở đây đã được soát hai lần rồi, và chính vì vậy phần soát ở vòng này là soát các con số tổng chứ không soát từng dòng — nên một dòng sai buộc phải bị bắt từ sớm hơn.")],
    ["net_at_stake",
     B("Net at stake", "Số tiền đang treo"),
     B("The net of every run in the pipeline added together — money that is one or more signatures away from leaving the company's account and can still be stopped by anybody who finds a reason. After the last gate that stops being true.",
       "Tổng thực nhận của mọi đợt đang trong quy trình cộng lại — số tiền chỉ còn cách tài khoản công ty một hoặc vài chữ ký, và bất kỳ ai tìm ra lý do đều còn kịp chặn lại. Sau cổng cuối cùng thì điều đó không còn đúng nữa.")],
  ],

  employees: [
    ["headcount",
     B("Headcount", "Sĩ số"),
     B("Everybody on the roster within the filters currently active — on the practice company, all 48. It counts people the company EMPLOYS, which is not the same as people the last run PAID: that count lives on Workforce Analytics, and the gap between the two is where a missing payslip hides.",
       "Toàn bộ những người trong danh sách theo bộ lọc đang chọn — trên công ty thực hành là đủ 48 người. Nó đếm số người công ty ĐANG THUÊ, khác với số người mà đợt lương gần nhất ĐÃ TRẢ: con số đó nằm ở Phân tích nhân sự, và khoảng chênh giữa hai bên chính là chỗ một phiếu lương bị thiếu đang ẩn.")],
    ["running_contracts",
     B("Running contracts", "Hợp đồng đang hiệu lực"),
     B("Contracts in force today. Payroll computes from the contract, so somebody on the roster whose contract is still in draft is on this screen and will not be in the run — which is why this number is worth comparing with headcount.",
       "Số hợp đồng đang có hiệu lực hôm nay. Hệ thống lương tính theo hợp đồng, nên người có trong danh sách mà hợp đồng còn ở Nháp thì vẫn hiện trên màn hình này nhưng sẽ không có trong đợt lương — vì thế con số này rất đáng đem so với sĩ số.")],
    ["expiring_30",
     B("Expiring in 30 days", "Hết hạn trong 30 ngày"),
     B("Contracts that end within the next month. Each one is either a renewal somebody has to sign or a leaver somebody has to settle, and both are cheaper to handle now than as a surprise proration on a payslip.",
       "Các hợp đồng sẽ kết thúc trong vòng một tháng tới. Mỗi hợp đồng như vậy hoặc là một lần gia hạn cần người ký, hoặc là một trường hợp thôi việc cần quyết toán, và cả hai đều rẻ hơn nếu xử lý ngay bây giờ thay vì để thành một khoản tính theo ngày công bất ngờ trên phiếu lương.")],
    ["new_this_month",
     B("New this month", "Vào mới tháng này"),
     B("People who joined inside the current period. They are the most likely rows to be prorated and the most likely to have bank details missing, so they are worth reading one by one rather than as a count.",
       "Những người vào làm trong kỳ hiện tại. Đây là nhóm dễ bị tính theo ngày công nhất và cũng dễ thiếu thông tin ngân hàng nhất, nên rất đáng đọc từng người thay vì chỉ đọc con số tổng.")],
    ["monthly_wage_bill",
     B("Monthly wage bill", "Quỹ lương tháng"),
     B("The registered contract bases added together — what the company has agreed to pay, before overtime, allowances or deductions. It is also the base insurance is charged on, which is why it moves when a contract is renewed rather than when a month is busy.",
       "Tổng các mức lương cơ bản đã đăng ký theo hợp đồng — mức công ty đã cam kết trả, chưa tính tăng ca, phụ cấp hay khấu trừ. Đây cũng là mức dùng để tính bảo hiểm, nên nó thay đổi khi có hợp đồng được gia hạn chứ không phải khi tháng đó bận rộn.")],
    ["payroll_ready",
     B("Payroll-ready", "Sẵn sàng tính lương"),
     B("The share of people with BANK DETAILS on file — that one fact, over headcount, and nothing else. The tick on each row is stricter than the tile above it: a row is ready only with a running contract AND bank details, so the percentage can read 100% while a person on a draft contract still will not be paid. Read the rows for the answer and the tile for the trend.",
       "Tỷ lệ những người ĐÃ CÓ THÔNG TIN NGÂN HÀNG trong hồ sơ — đúng một dữ kiện đó, chia cho sĩ số, không tính gì thêm. Dấu tích trên từng dòng lại chặt hơn ô chỉ số phía trên: một dòng chỉ được coi là sẵn sàng khi vừa có hợp đồng đang hiệu lực VỪA có thông tin ngân hàng, nên tỷ lệ vẫn có thể hiện 100% trong khi một người đang ở hợp đồng nháp thì vẫn không được trả lương. Hãy đọc các dòng để có câu trả lời, còn ô chỉ số thì để nhìn xu hướng.")],
  ],

  contracts: [
    ["running",
     B("Running", "Đang hiệu lực"),
     B("Contracts in force today, which is the set payroll will compute from. A contract that starts next week is not here yet and a person on it is not in this month's run either.",
       "Các hợp đồng đang có hiệu lực hôm nay, tức là tập hợp mà hệ thống lương sẽ dựa vào để tính. Một hợp đồng bắt đầu từ tuần sau thì chưa nằm ở đây, và người thuộc hợp đồng đó cũng chưa có trong đợt lương tháng này.")],
    ["draft",
     B("Draft", "Nháp"),
     B("Contracts that have been prepared and not put in force. A draft pays nothing at all — it is the state to hunt for in the week before a run, because the employee is on every other screen and simply absent from the payslips.",
       "Các hợp đồng đã soạn nhưng chưa được đưa vào hiệu lực. Hợp đồng nháp thì không trả gì cả — đây là trạng thái cần lùng cho ra trong tuần trước khi chạy lương, vì nhân viên đó vẫn hiện trên mọi màn hình khác mà đơn giản là vắng mặt trong danh sách phiếu lương.")],
    ["expired",
     B("Expired", "Đã hết hạn"),
     B("Contracts whose end date has passed. Each is either a leaver who still needs settling in Full & Final or a renewal that was never signed, and the second one is paid up to the end date and then stops.",
       "Các hợp đồng đã qua ngày kết thúc. Mỗi hợp đồng như vậy hoặc là một người thôi việc còn phải quyết toán ở Quyết toán thôi việc, hoặc là một lần gia hạn chưa ai ký — và trường hợp thứ hai được trả tới đúng ngày kết thúc rồi dừng.")],
    ["average_wage",
     B("Average wage", "Lương bình quân"),
     B("The wage bill divided by the number of contracts in the current filters. It is a scoped average, so it moves when you change a chip without anything having changed in the database — useful for comparing divisions, misleading as a headline.",
       "Quỹ lương chia cho số hợp đồng trong phạm vi bộ lọc hiện tại. Đây là số bình quân theo phạm vi, nên nó thay đổi khi bạn đổi chip lọc dù dữ liệu không hề đổi — hữu ích để so sánh giữa các bộ phận, nhưng dễ gây hiểu nhầm nếu lấy làm con số tiêu đề.")],
  ],

  insights: [
    /* The product's own caption under the headline is "net payroll" — NOT
       "Net paid", which is the Pay Runs board's KPI and already means
       "Đã chi". One English string, one Vietnamese; two screens that mean
       slightly different things get two names. */
    ["net_payroll",
     B("Net payroll", "Lương thực chi"),
     B("The net of the LATEST run this company has, in whatever state that run is in — a draft computed an hour ago counts. It comes from the run's own stored roll-up rather than from re-adding its payslip lines, which is what makes the board fast; the state chip beside it is the part that tells you whether the figure is money that moved or money that might.",
       "Số thực nhận của đợt lương GẦN NHẤT mà công ty có, ở bất kỳ trạng thái nào — một bản nháp vừa tính cách đây một giờ vẫn được tính. Con số này lấy từ số tổng đã lưu sẵn của chính đợt đó chứ không phải cộng lại từng dòng phiếu lương, và đó là điều làm bảng này nhanh; còn chip trạng thái bên cạnh mới là thứ cho biết đây là tiền đã chi hay tiền có thể sẽ chi.")],
    ["cost_story",
     B("Cost story", "Diễn biến chi phí"),
     B("The same measure over three, six or twelve months. The window chip decides which story it tells, and a figure quoted without saying which window it came from is a figure somebody will contradict with the same screen.",
       "Cùng một chỉ tiêu nhìn theo ba, sáu hay mười hai tháng. Chip chọn khoảng thời gian quyết định nó kể câu chuyện nào, và một con số trích ra mà không nói rõ lấy từ khoảng nào là con số sẽ bị người khác phản bác bằng đúng màn hình này.")],
    ["statutory_split",
     B("Statutory split", "Cơ cấu đóng bắt buộc"),
     B("How much of the company's payroll cost is the law rather than salary: the employee leg deducted from payslips beside the employer leg paid on top. The second one never appears in anybody's net, so it is invisible in every conversation about pay unless somebody puts it on the table.",
       "Bao nhiêu phần chi phí lương của công ty là do luật định chứ không phải tiền lương: phần người lao động bị khấu trừ trên phiếu lương đặt cạnh phần doanh nghiệp đóng thêm. Phần thứ hai không bao giờ xuất hiện trong thực nhận của ai, nên nó vô hình trong mọi cuộc trao đổi về lương trừ khi có người chủ động nêu ra.")],
  ],

  explorer: [
    ["measure",
     B("Measure", "Chỉ tiêu"),
     B("What is being counted — net pay, gross, a contribution, a headcount. It is the first thing to choose and the most common thing to get wrong: most wrong answers here are the right filter applied to the wrong measure.",
       "Thứ đang được đo — thực nhận, tổng thu nhập, một khoản đóng bảo hiểm, hay số người. Đây là thứ cần chọn đầu tiên và cũng là thứ hay chọn sai nhất: phần lớn câu trả lời sai ở đây là lọc đúng nhưng áp lên nhầm chỉ tiêu.")],
    ["break_down_by",
     B("Break down by", "Tách theo"),
     B("The dimension the rows are grouped into — division, department, cycle, month. Changing it does not change the total, only how the same total is divided up, which is the quickest way to check that a number is what you think it is.",
       "Chiều mà các dòng được nhóm theo — bộ phận, phòng ban, chu kỳ, tháng. Đổi nó không làm thay đổi con số tổng, chỉ thay đổi cách chia nhỏ cùng một tổng đó — và đây là cách nhanh nhất để kiểm tra xem một con số có đúng như bạn nghĩ không.")],
    ["where",
     B("Where", "Điều kiện"),
     B("Every filter currently applied, shown as a removable tag. The tags are part of the answer: the same measure with one tag removed is a different figure, and the two look identical once they have been pasted into an email.",
       "Toàn bộ bộ lọc đang áp dụng, hiển thị thành các thẻ có thể gỡ. Các thẻ đó là một phần của câu trả lời: cùng chỉ tiêu ấy mà gỡ đi một thẻ là ra một con số khác, và khi đã dán vào email thì hai con số trông y hệt nhau.")],
  ],

  workforcean: [
    ["employees_paid",
     B("Employees paid", "Nhân viên được trả lương"),
     B("How many people the runs in scope actually produced a payslip for. It is not headcount: somebody employed all month whose contract sat in draft is counted on People and not here, and that difference is the point of the tile.",
       "Có bao nhiêu người thực sự được các đợt lương trong phạm vi tạo ra phiếu lương. Đây không phải sĩ số: một người làm cả tháng nhưng hợp đồng còn ở Nháp thì được đếm ở màn hình Nhân sự chứ không phải ở đây, và chính khác biệt đó mới là ý nghĩa của ô này.")],
    ["joiners",
     B("Joiners", "Vào mới"),
     B("People who first appear in a run inside this period. Almost all of them are prorated, which means almost all of them are a question somebody will ask about their first payslip.",
       "Những người lần đầu xuất hiện trong một đợt lương thuộc kỳ này. Gần như tất cả đều được tính theo ngày công, nghĩa là gần như tất cả đều sẽ là một câu hỏi về phiếu lương đầu tiên của họ.")],
    ["leavers",
     B("Leavers", "Thôi việc"),
     B("People whose last run falls in this period. Each one needs settling in Full & Final AND excluding from the ordinary monthly run — a leaver in both is paid twice, and recovering that is a legal conversation rather than a payroll one.",
       "Những người có đợt lương cuối cùng rơi vào kỳ này. Mỗi người vừa cần được quyết toán ở Quyết toán thôi việc VÀ cần bị loại khỏi đợt lương tháng thông thường — người nằm ở cả hai chỗ sẽ được trả hai lần, và thu hồi khoản đó là chuyện pháp lý chứ không còn là chuyện tính lương.")],
    ["cost_per_head",
     B("Cost per head", "Chi phí bình quân đầu người"),
     B("The run's cost divided by the people it paid. It is the only figure on this screen that survives a headcount change, which makes it the honest way to compare two months — a total against a total mostly measures how many people were in each.",
       "Chi phí của đợt lương chia cho số người nó đã trả. Đây là con số duy nhất trên màn hình này không bị méo khi sĩ số thay đổi, nên nó là cách so sánh trung thực giữa hai tháng — còn đem tổng so với tổng thì chủ yếu là đang đo xem mỗi tháng có bao nhiêu người.")],
  ],

  govreports: [
    ["period",
     B("Period", "Kỳ báo cáo"),
     B("The month being filed for. It is a month rather than a date range because the authorities ask for months, and a filing generated before every run in that month is done is short by however many payslips are still in the pipeline.",
       "Tháng đang được lập báo cáo. Đây là một tháng chứ không phải một khoảng ngày, vì các cơ quan quản lý yêu cầu theo tháng — và một báo cáo kết xuất khi các đợt lương của tháng chưa xong sẽ thiếu đúng bằng số phiếu lương còn đang trong quy trình.")],
    ["country",
     B("Country", "Quốc gia"),
     B("Which country's filing set is on display. The tiles are decided by the active company's country rather than by what Payobook can produce, and the chips only appear when a company runs payroll in more than one.",
       "Bộ biểu mẫu của quốc gia nào đang hiển thị. Các ô biểu mẫu do quốc gia của công ty đang hoạt động quyết định chứ không do những gì Payobook có thể tạo ra, và các chip chỉ xuất hiện khi công ty chạy lương ở nhiều hơn một quốc gia.")],
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
  /* The Dashboard replica's KPI row is NO LONGER practice-only. Phase C1 made
     the Dashboard a station with a full lesson, so the replica draws the real
     dash-hero / dash-runpayroll / dash-kpis / dash-formula attributes and the
     registry owns those names (promoted out of `foreign`). What is left here is
     the one panel with no product counterpart: the product's card is a single
     "Latest pay run" summary, and a lesson about the monthly loop needs to show
     a loop, so the replica draws three months and says so by name. */
  "rep-dash-runs": "The replica Dashboard's three-month run list. The product draws ONE latest-run card here; three months is a teaching view, so it keeps a rep- name and the Coach must never claim to point at it on a live screen.",
  "rep-pipeline": "The lifecycle stepper: draft → level0 → level1 → level2 → done, with the rejection branch. A teaching view; the product draws this as columns, not as a stepper.",
  "rep-slipline": "The worked example's statutory deductions, drawn on the STATUTORY replica beside the rates that produced them. It is the far end of L6's trace and it exists only here: the product's statutory cockpit shows rates, and a payslip shows đồng, and no single product screen shows both at once. Naming it rep- is the honest consequence — the Coach must never claim to point at this on a live screen.",
};

/* =============================================================================
   11. SCENARIOS — one story, three ways  (LEARNOS Phase 1b)
   -----------------------------------------------------------------------------
   A scenario is a walkthrough of a REAL task, authored once and playable three
   ways. The steps, the anchors and the words are identical in all three; the
   only thing that changes is who presses:

     watch  the engine drives the real screens and narrates. It may synthesise
            a click on an ordinary control, and it NEVER synthesises one on a
            guarded step — that step becomes an observe with a card explaining
            what pressing would do.
     try    the learner drives the PRACTICE replica. A wrong click is a nudge,
            never a failure. Every click here is safe by construction: there is
            no server on the other end of a replica.
     do     the learner drives the REAL product. The engine attaches a one-shot
            listener and waits. It never presses anything, and on a guarded
            step it never times out into advancing either.

   THE GUARD RULE, and it is generator-enforced:
     every `click` step must state `guard` explicitly — true or false. There is
     no default, because a default is a decision nobody made. `guard: false` is
     additionally refused when the step's key, anchor or English title names a
     writing verb (compute, submit, approve, reject, confirm, delete, send,
     commit, pay, post, generate, activate, archive, cancel, apply). If in
     doubt, guard: the cost of an unnecessary guard is one extra press by the
     learner; the cost of a missing one is a pay run computed by a tutorial.

   THESE SIX ARE THE PORTED pb_coach TOURS. hero_path became `sc_welcome`,
   tour_payrun `sc_payrun`, tour_payslips `sc_payslips`, tour_formula
   `sc_formula`, tour_import `sc_import`, tour_mapping `sc_mapping`. The anchors
   are verbatim — they are the same controls in the same templates — and the
   copy is de-demo-flavoured: no "your 12 division configs", no "editing is off
   in this shared demo, ask us for a trial", no month named as though it were
   everybody's open period.

   `modes` is a claim the engine keeps. A scenario is `try`-capable only when
   every screen its steps stand on is one of the 20 practice replicas AND the
   replica draws every anchor it points at — which is why the Formula Studio
   deep-dive is watch-only: the replica has no Grid, and a Try step whose
   control is not on the replica is a dead end, not a lesson.
   ========================================================================== */
const SCENARIOS = [
  /* ---------------------------------------------------------- sc_welcome
     hero_path. The whole-product walk: dashboard, the formula engine, a pay
     run, the copilot. Watch only — it crosses four cockpits, three of which
     have no replica in the same order, and its job is the first ninety
     seconds of somebody's first login rather than practice. */
  {
    key: "sc_welcome",
    icon: "compass",
    line: "overview",
    modes: ["watch"],
    screens: ["dashboard", "formula", "runpayroll", "payruns"],
    name: B("Take the tour", "Đi một vòng Payobook"),
    tagline: B("Dashboard, the formula engine, a pay run and the copilot — the whole product in one pass.",
               "Trang tổng quan, bộ máy công thức, một đợt tính lương và trợ lý — toàn bộ sản phẩm trong một lượt."),
    entry: { nav: "pb_dashboard.action_pb_dashboard" },
    steps: [
      {
        key: "hero", anchor: "dash-hero", nav: "pb_dashboard.action_pb_dashboard",
        act: "observe",
        say: {
          kicker: B("Welcome", "Chào bạn"),
          title: B("Your command centre", "Trung tâm điều hành của bạn"),
          body: B("This is the Payobook dashboard. One screen that says who you are, which pay run is live and how much of it is still waiting on somebody.",
                  "Đây là trang tổng quan Payobook. Một màn hình cho biết bạn là ai, đợt lương nào đang chạy và còn bao nhiêu phần đang chờ người khác."),
        },
      },
      {
        key: "kpis", anchor: "dash-kpis", act: "observe",
        say: {
          title: B("Four numbers that describe the company", "Bốn con số mô tả cả công ty"),
          body: B("Headcount, monthly payroll, approvals pending and active configurations. They describe the company, not today — read the hero line above for today.",
                  "Sĩ số, quỹ lương tháng, số việc chờ duyệt và số cấu hình đang bật. Chúng mô tả cả công ty chứ không phải hôm nay — muốn biết hôm nay thì đọc dòng nổi bật ở trên."),
        },
      },
      {
        key: "engine", anchor: "dash-formula", act: "observe",
        say: {
          title: B("Pay is computed from formulas", "Lương được tính bằng công thức"),
          body: B("Payobook does not compute pay from a fixed salary structure. Every payslip line comes from a named component in a formula configuration you can open and read. Let us go and read one.",
                  "Payobook không tính lương bằng cấu trúc lương cố định. Mỗi dòng phiếu lương đến từ một thành phần có tên trong một cấu hình công thức mà bạn mở ra đọc được. Chúng ta cùng đi đọc thử một cái."),
        },
      },
      {
        key: "studio", anchor: "fs-config", nav: "pb_formula_studio.action_pb_formula_studio",
        act: "observe",
        say: {
          kicker: B("Formula Studio", "Xưởng công thức"),
          title: B("One rulebook per division", "Mỗi bộ phận một bộ quy tắc"),
          body: B("The name at the top IS the rulebook this division is paid by. A company runs one configuration per division and cycle, and switching here switches everything below.",
                  "Cái tên ở trên cùng CHÍNH LÀ bộ quy tắc trả lương cho bộ phận này. Mỗi bộ phận và mỗi chu kỳ có một cấu hình riêng, và đổi ở đây là đổi toàn bộ phần bên dưới."),
        },
      },
      {
        key: "components", anchor: "fs-components", act: "observe",
        say: {
          title: B("Every component, one list", "Mọi thành phần trong một danh sách"),
          body: B("Inputs, earnings, deductions and totals. A payslip line exists because a component here produced it, and the coloured tag says which kind it is.",
                  "Đầu vào, thu nhập, khấu trừ và các tổng. Một dòng phiếu lương tồn tại vì có một thành phần ở đây sinh ra nó, và thẻ màu cho biết nó thuộc loại nào."),
        },
      },
      {
        key: "formula", anchor: "fs-formula", act: "observe", timeout: 4000,
        say: {
          title: B("The formula, in plain words", "Công thức viết bằng lời"),
          body: B("No cell references. Components read by their own name, coloured by kind, and every chip is a link to the component behind it.",
                  "Không có địa chỉ ô. Các thành phần được gọi bằng chính tên của chúng, tô màu theo loại, và mỗi thẻ là một đường dẫn tới thành phần đứng sau nó."),
        },
      },
      {
        key: "namesletters", anchor: "fs-namesletters", act: "observe", timeout: 4000,
        say: {
          title: B("Names or letters", "Tên hay chữ cái"),
          body: B("Prefer spreadsheet style? Flip to letters (A, B, C…) and back to names. Same formula, your choice of spelling.",
                  "Bạn quen kiểu bảng tính? Hãy chuyển sang chữ cái (A, B, C…) rồi quay lại tên. Vẫn là công thức đó, chỉ khác cách viết."),
        },
      },
      {
        key: "deps", anchor: "fs-deps", act: "observe",
        say: {
          title: B("What it needs, and what needs it", "Nó cần gì, và ai cần nó"),
          body: B("Depends on and Used by are the blast radius of a rename or a deletion, written down before you make one.",
                  "\"Phụ thuộc vào\" và \"Được dùng bởi\" chính là phạm vi ảnh hưởng của một lần đổi tên hay xoá bỏ, được viết ra trước khi bạn làm."),
        },
      },
      {
        key: "flow", anchor: "fs-flow", act: "observe", timeout: 4000,
        say: {
          title: B("Watch it calculate", "Xem nó tính"),
          body: B("The calculation flow builds the result step by step, down to the final output. Open it full screen to scroll and zoom around a big configuration.",
                  "Sơ đồ tính toán dựng kết quả từng bước một, cho tới con số cuối cùng. Mở toàn màn hình để cuộn và phóng to khi cấu hình lớn."),
        },
      },
      {
        key: "preview", anchor: "fs-preview", act: "observe",
        say: {
          title: B("Live preview, real arithmetic", "Xem trước trực tiếp, số liệu thật"),
          body: B("The whole configuration evaluated against one sample employee, line by line. Change a rule and this moves while you watch.",
                  "Toàn bộ cấu hình được tính trên một nhân viên mẫu, từng dòng một. Sửa một quy tắc là phần này thay đổi ngay trước mắt bạn."),
        },
      },
      {
        key: "editai", anchor: "fs-editai", act: "observe",
        say: {
          title: B("Edit by describing it", "Sửa bằng cách mô tả"),
          body: B("A formula can be changed by describing the change in plain language. Whether that is switched on is a permission your administrator sets, not a property of the screen.",
                  "Bạn có thể đổi một công thức bằng cách mô tả thay đổi bằng lời. Việc này có được bật hay không là quyền do quản trị viên của bạn cấp, chứ không phải đặc tính của màn hình."),
          tip: B("Every edit here changes future payslips, never past ones. A computed payslip keeps the numbers it was computed with.",
                 "Mọi chỉnh sửa ở đây chỉ ảnh hưởng tới phiếu lương sau này, không đụng tới phiếu cũ. Phiếu đã tính vẫn giữ nguyên các con số lúc tính."),
        },
      },
      {
        key: "division", anchor: "pw-division", nav: "pb_payrun_wizard.action_pb_payrun_wizard",
        act: "observe",
        say: {
          kicker: B("Run payroll", "Chạy bảng lương"),
          title: B("Pick a division", "Chọn một bộ phận"),
          body: B("The wizard loads that division's configuration and the employees eligible for the period. Choosing the division is choosing the rulebook.",
                  "Trình hướng dẫn sẽ nạp cấu hình của bộ phận đó và những nhân viên đủ điều kiện trong kỳ. Chọn bộ phận chính là chọn bộ quy tắc."),
        },
      },
      {
        key: "compute", anchor: "pw-compute", act: "observe",
        say: {
          title: B("Compute creates drafts", "Tính lương chỉ tạo bản nháp"),
          body: B("This is the control that generates a draft payslip for every eligible employee — gross, allowances, BHXH and thuế TNCN, net. Drafts only: nothing is paid, sent or approved by pressing it.",
                  "Đây là nút sinh ra một phiếu lương nháp cho từng nhân viên đủ điều kiện — tổng thu nhập, phụ cấp, BHXH và thuế TNCN, thực nhận. Chỉ là bản nháp: bấm nút này không chi tiền, không gửi và không phê duyệt gì cả."),
          tip: B("I am not pressing it. This walkthrough only reads; the pay-run scenario is where you press it yourself.",
                 "Tôi sẽ không bấm nút này. Lượt đi vòng này chỉ để đọc; muốn tự bấm thì hãy mở kịch bản chạy đợt lương."),
        },
      },
      {
        key: "board", anchor: "pk-kpis", nav: "pb_payruns.action_pb_payruns_kanban",
        act: "observe",
        say: {
          title: B("Every run on one board", "Mọi đợt lương trên một bảng"),
          body: B("A run travels draft → Payroll Officer → {{hrTierName}} → {{gmTierName}} → done, one column per gate. Each gate is a different role, so nothing is paid on one person's say-so.",
                  "Một đợt lương đi qua Nháp → Chuyên viên tính lương → {{hrTierName}} → {{gmTierName}} → Hoàn tất, mỗi cổng một cột. Mỗi cổng là một vai trò khác nhau, nên không khoản nào được chi chỉ vì một người nói vậy."),
        },
      },
      {
        key: "copilot", anchor: "payai-pill", nav: "pb_dashboard.action_pb_dashboard",
        act: "observe",
        say: {
          title: B("And the copilot is always there", "Và trợ lý luôn ở đó"),
          body: B("Ask it about a number on the screen you are standing on. That is the tour — everything else you can find from the sidebar.",
                  "Hãy hỏi nó về một con số trên chính màn hình bạn đang đứng. Vậy là xong một vòng — mọi thứ còn lại bạn tìm được từ thanh bên."),
        },
      },
    ],
  },

  /* ----------------------------------------------------------- sc_payrun
     tour_payrun, expanded to the six controls the wizard actually has. All
     three modes: the replica draws every pw-* anchor, and Do is the point —
     the learner presses Compute themselves, on their own division. */
  {
    key: "sc_payrun",
    icon: "zap",
    line: "payrun",
    modes: ["watch", "try", "do"],
    screens: ["runpayroll"],
    name: B("Run a pay run", "Chạy một đợt lương"),
    tagline: B("Period, division, scope, compute — the four reads and the one press.",
               "Kỳ lương, bộ phận, phạm vi, tính — bốn lần đọc và một lần bấm."),
    entry: { nav: "pb_payrun_wizard.action_pb_payrun_wizard", screen: "runpayroll" },
    steps: [
      {
        key: "scope", anchor: "pw-scope", nav: "pb_payrun_wizard.action_pb_payrun_wizard",
        screen: "runpayroll", act: "observe",
        say: {
          kicker: B("Step 1", "Bước 1"),
          title: B("Which month, and what to call it", "Tháng nào, và gọi đợt này là gì"),
          body: B("The period decides which month is computed. The batch name is what everybody downstream will search for, so it is worth reading before you move on.",
                  "Kỳ lương quyết định tháng nào được tính. Tên đợt là thứ mọi người phía sau sẽ dùng để tìm, nên đáng đọc kỹ trước khi đi tiếp."),
        },
      },
      {
        key: "division", anchor: "pw-division", screen: "runpayroll", act: "observe",
        say: {
          kicker: B("Step 2", "Bước 2"),
          title: B("Choose the division", "Chọn bộ phận"),
          body: B("Each division has its own formula configuration, one for mid-cycle and one for end-cycle. Choosing the division here is choosing which rulebook computes every payslip in this batch.",
                  "Mỗi bộ phận có cấu hình công thức riêng, một cho giữa kỳ và một cho cuối kỳ. Chọn bộ phận ở đây chính là chọn bộ quy tắc sẽ tính mọi phiếu lương trong lô này."),
        },
      },
      {
        key: "summary", anchor: "pw-summary", screen: "runpayroll", act: "observe",
        say: {
          kicker: B("Step 3", "Bước 3"),
          title: B("The last read before anything is computed", "Lần đọc cuối trước khi tính"),
          body: B("Company, configuration and eligible headcount. If the headcount is not the number you expected, the answer is upstream — a contract, or a person the import missed — and it is much cheaper to find it here.",
                  "Công ty, cấu hình và số nhân viên đủ điều kiện. Nếu sĩ số không đúng như bạn nghĩ thì nguyên nhân nằm ở phía trên — một hợp đồng, hoặc một người mà đợt nhập liệu bỏ sót — và tìm ra ở đây rẻ hơn nhiều."),
          tip: B("Nobody is paid because they are on this list. They are paid because a payslip was computed, approved and sent — this is only the first of those.",
                 "Không ai được trả lương chỉ vì có tên trong danh sách này. Người ta được trả vì một phiếu lương đã được tính, được duyệt và được chi — đây mới là bước đầu tiên trong ba bước đó."),
        },
      },
      {
        key: "compute", anchor: "pw-compute", screen: "runpayroll",
        act: "click", guard: true,
        say: {
          kicker: B("Step 4", "Bước 4"),
          title: B("Compute the payslips", "Tính phiếu lương"),
          body: B("This creates one draft payslip per eligible employee, computed by the configuration named above. Drafts only — nothing is paid, sent or approved — but they are real records with real names on them.",
                  "Thao tác này tạo một phiếu lương nháp cho mỗi nhân viên đủ điều kiện, tính theo cấu hình đã nêu ở trên. Chỉ là bản nháp — chưa chi, chưa gửi, chưa duyệt — nhưng vẫn là bản ghi thật, mang tên người thật."),
          tip: B("Computed twice? The wizard replaces the drafts rather than doubling them. What it cannot undo is a run somebody has already submitted.",
                 "Lỡ tính hai lần? Trình hướng dẫn sẽ thay thế các bản nháp chứ không nhân đôi chúng. Cái nó không sửa được là một đợt lương đã có người trình duyệt."),
        },
      },
      {
        key: "pills", anchor: "pw-pills", screen: "runpayroll", act: "observe",
        say: {
          kicker: B("Step 5", "Bước 5"),
          title: B("Payslips, computed, need review", "Số phiếu, đã tính, cần soát xét"),
          body: B("The third number is a question, not an error. The engine flags a payslip when something about it is unusual for this employee, and it wants a person to look — not to fix.",
                  "Con số thứ ba là một câu hỏi, không phải một lỗi. Hệ thống gắn cờ một phiếu lương khi có gì đó bất thường so với chính nhân viên đó, và nó muốn có người nhìn qua — chứ không phải sửa."),
        },
      },
      {
        key: "result", anchor: "pw-result", screen: "runpayroll", act: "observe",
        say: {
          kicker: B("Step 6", "Bước 6"),
          title: B("What the compute produced", "Kết quả của lần tính"),
          body: B("The run's name, its net total and its counts. From here the batch goes to the board, where somebody other than you moves it through its gates.",
                  "Tên đợt lương, tổng thực chi và các con số đếm. Từ đây lô này đi ra bảng đợt lương, nơi một người khác — không phải bạn — đẩy nó qua các cổng phê duyệt."),
        },
      },
    ],
  },

  /* --------------------------------------------------------- sc_payslips
     tour_payslips, taken through to the payslip itself. The old tour stopped
     at the board and then pointed at the copilot; the anchors for reading a
     slip line by line have existed since Phase A and this is what they are
     for. */
  {
    key: "sc_payslips",
    icon: "file-text",
    line: "payrun",
    modes: ["watch", "try", "do"],
    screens: ["payruns", "payslips"],
    name: B("Read a pay run and its payslips", "Đọc một đợt lương và các phiếu lương"),
    tagline: B("From the board to one person's net, and the working behind it.",
               "Từ bảng đợt lương tới số thực nhận của một người, và phần tính toán đứng sau."),
    entry: { nav: "pb_payruns.action_pb_payruns_kanban", screen: "payruns" },
    steps: [
      {
        key: "kpis", anchor: "pk-kpis", nav: "pb_payruns.action_pb_payruns_kanban",
        screen: "payruns", act: "observe",
        say: {
          kicker: B("The board", "Bảng đợt lương"),
          title: B("Five numbers over the whole board", "Năm con số trên toàn bảng"),
          body: B("Total, in pipeline, awaiting YOUR approval, completed and net paid. The third one is the only number here that is your work rather than somebody else's.",
                  "Tổng số, đang chạy, chờ BẠN duyệt, đã hoàn tất và đã chi. Con số thứ ba là con số duy nhất ở đây thuộc về phần việc của bạn chứ không phải của người khác."),
        },
      },
      {
        key: "tabs", anchor: "pk-tabs", screen: "payruns", act: "observe",
        say: {
          title: B("The tabs filter by gate, not by month", "Các thẻ lọc theo cổng, không theo tháng"),
          body: B("A run sits in the column of the gate it is waiting at. If a batch you expected is missing, it has usually moved a column rather than disappeared.",
                  "Một đợt lương nằm ở cột của cổng mà nó đang chờ. Nếu không thấy lô bạn đang tìm thì thường là nó đã chuyển cột chứ không phải biến mất."),
        },
      },
      {
        key: "card", anchor: "pk-card", screen: "payruns", act: "observe",
        say: {
          title: B("One card is one batch", "Một thẻ là một lô"),
          body: B("Division, period, headcount and net. Which buttons a card offers is decided by the record's own state and your role — never by the card, which is why two people see different footers on the same run.",
                  "Bộ phận, kỳ lương, sĩ số và số thực chi. Việc một thẻ hiện nút nào là do trạng thái của chính bản ghi và vai trò của bạn quyết định — không phải do cái thẻ, nên hai người nhìn cùng một đợt lương có thể thấy hai bộ nút khác nhau."),
        },
      },
      {
        key: "runsel", anchor: "ps-runsel", nav: "pb_payslip_review.action_pb_payslip_review",
        screen: "payslips", act: "observe",
        say: {
          kicker: B("Inside a run", "Bên trong một đợt"),
          title: B("Everything below belongs to this run", "Mọi thứ bên dưới thuộc về đợt này"),
          body: B("The selector at the top scopes the whole screen. A figure read here without checking it is a figure about a batch you were not looking at.",
                  "Ô chọn ở trên cùng giới hạn phạm vi của cả màn hình. Đọc một con số ở đây mà không xem ô này là đang đọc con số của một lô khác."),
        },
      },
      {
        key: "list", anchor: "ps-list", screen: "payslips", act: "observe",
        say: {
          title: B("Read the flagged ones first", "Đọc những phiếu bị gắn cờ trước"),
          body: B("A dot marks a payslip the engine wants read. It is not a broken slip; it is a slip whose numbers moved more than this employee's usually do.",
                  "Một chấm đánh dấu phiếu lương mà hệ thống muốn có người đọc. Đó không phải phiếu hỏng; đó là phiếu có con số biến động nhiều hơn bình thường của chính nhân viên đó."),
        },
      },
      {
        key: "status", anchor: "ps-status", screen: "payslips", act: "observe",
        say: {
          title: B("A payslip's chain is not the run's", "Chuỗi duyệt của phiếu khác của đợt"),
          body: B("A payslip travels draft → {{hrTierName}} → {{gmTierName}} → done. The Payroll Officer gate belongs to the RUN, so do not go looking for it here.",
                  "Một phiếu lương đi qua Nháp → {{hrTierName}} → {{gmTierName}} → Hoàn tất. Cổng Chuyên viên tính lương là của ĐỢT LƯƠNG, nên đừng tìm nó ở đây."),
        },
      },
      {
        key: "breakdown", anchor: "ps-breakdown", screen: "payslips", act: "observe",
        say: {
          title: B("The working behind the net", "Phần tính toán đứng sau số thực nhận"),
          body: B("Every line with its rule code, in the order the configuration produced them. This is the answer to \"why is this person's pay different this month\" — read the lines, not the total.",
                  "Từng dòng kèm mã quy tắc, theo đúng thứ tự cấu hình sinh ra chúng. Đây là câu trả lời cho câu hỏi \"vì sao tháng này lương người này khác\" — hãy đọc từng dòng, đừng đọc con số tổng."),
        },
      },
    ],
  },

  /* ---------------------------------------------------------- sc_formula
     tour_formula. WATCH ONLY, and the reason is structural rather than
     editorial: half of it happens in the Grid, and the practice replica has
     no Grid. A Try step whose control the replica does not draw would leave
     the learner clicking at nothing. */
  {
    key: "sc_formula",
    icon: "calculator",
    line: "setup",
    modes: ["watch"],
    screens: ["formula"],
    name: B("Explore the formula engine", "Khám phá bộ máy công thức"),
    tagline: B("Components, formulas, dependencies and the spreadsheet grid behind them.",
               "Thành phần, công thức, quan hệ phụ thuộc và lưới bảng tính đứng sau chúng."),
    entry: { nav: "pb_formula_studio.action_pb_formula_studio" },
    steps: [
      {
        key: "config", anchor: "fs-config", nav: "pb_formula_studio.action_pb_formula_studio",
        act: "observe",
        say: {
          kicker: B("Formula Studio", "Xưởng công thức"),
          title: B("Where every salary rule lives", "Nơi mọi quy tắc lương cư trú"),
          body: B("A live, visual spreadsheet engine. The switcher at the top chooses which division's configuration you are reading — the shape of the code is PREFIX_DIVISION_CYCLE.",
                  "Một bộ máy bảng tính trực quan và chạy thật. Ô chuyển ở trên cùng cho biết bạn đang đọc cấu hình của bộ phận nào — mã có dạng TIỀN TỐ_BỘ PHẬN_CHU KỲ."),
        },
      },
      {
        key: "components", anchor: "fs-components", act: "observe",
        say: {
          title: B("Every component, one list", "Mọi thành phần trong một danh sách"),
          body: B("Inputs, earnings, deductions and totals. Click any component to open it; the coloured type tag tells you what it is at a glance.",
                  "Đầu vào, thu nhập, khấu trừ và các tổng. Bấm vào thành phần nào là mở thành phần đó; thẻ màu cho biết ngay nó thuộc loại gì."),
        },
      },
      {
        key: "arrows", anchor: "fs-arrows", act: "observe",
        say: {
          title: B("See the dependencies", "Nhìn thấy quan hệ phụ thuộc"),
          body: B("Turn the arrows on and the connector lines are drawn live between components — what feeds what, across the whole configuration at once.",
                  "Bật mũi tên lên là các đường nối được vẽ ngay giữa các thành phần — cái nào nuôi cái nào, trên toàn bộ cấu hình cùng lúc."),
          tip: B("With the arrows on, double-click a connector and the list on the left scrolls to the component it links.",
                 "Khi đã bật mũi tên, bấm đúp vào một đường nối là danh sách bên trái cuộn tới đúng thành phần mà nó dẫn đến."),
        },
      },
      {
        key: "card", anchor: "fs-card", act: "observe",
        say: {
          title: B("The component card", "Thẻ thành phần"),
          body: B("Each rule shows its column, its code, its category and a validity check — so you always know whether the arithmetic is sound before you trust it.",
                  "Mỗi quy tắc hiển thị cột, mã, nhóm và một dấu kiểm tính hợp lệ — nhờ vậy bạn luôn biết phép tính có đúng hay không trước khi tin vào nó."),
        },
      },
      {
        key: "formula", anchor: "fs-formula", act: "observe", timeout: 4000,
        say: {
          title: B("The formula, in plain words", "Công thức viết bằng lời"),
          body: B("No cryptic cell references — every component reads by its own name, coloured by kind. Click a name inside the formula and the list scrolls straight to it.",
                  "Không có địa chỉ ô khó hiểu — mỗi thành phần được gọi bằng chính tên của nó, tô màu theo loại. Bấm vào một cái tên trong công thức là danh sách cuộn thẳng tới đó."),
        },
      },
      {
        key: "namesletters", anchor: "fs-namesletters", act: "observe", timeout: 4000,
        say: {
          title: B("Names or letters", "Tên hay chữ cái"),
          body: B("Flip to letters (A, B, C…) to read a formula beside a spreadsheet, and back to names to explain it to somebody. Same formula either way.",
                  "Chuyển sang chữ cái (A, B, C…) để đọc công thức song song với bảng tính, rồi quay lại tên khi cần giải thích cho người khác. Vẫn là một công thức."),
        },
      },
      {
        key: "deps", anchor: "fs-deps", act: "observe",
        say: {
          title: B("Full traceability", "Truy vết đầy đủ"),
          body: B("Depends on and Used by map exactly how this number connects to the rest of payroll. Nothing here is hidden, which is what makes a rename safe to plan.",
                  "\"Phụ thuộc vào\" và \"Được dùng bởi\" mô tả chính xác con số này nối với phần còn lại của hệ thống lương ra sao. Không có gì bị giấu, nên bạn có thể lên kế hoạch đổi tên một cách an toàn."),
        },
      },
      {
        key: "flow", anchor: "fs-flow", act: "observe", timeout: 4000,
        say: {
          title: B("Watch it calculate", "Xem nó tính"),
          body: B("The calculation flow shows how a result is built, step by step, down to the final output. Open it full screen — scroll to zoom, drag to pan.",
                  "Sơ đồ tính toán cho thấy một kết quả được dựng lên từng bước ra sao, cho tới đầu ra cuối cùng. Mở toàn màn hình — cuộn để phóng to, kéo để di chuyển."),
        },
      },
      {
        key: "preview", anchor: "fs-preview", act: "observe",
        say: {
          title: B("Live preview, real numbers", "Xem trước trực tiếp, số liệu thật"),
          body: B("Every component computes in real time for one sample employee. Tap the sample name to cycle employees and watch the values recalculate.",
                  "Mọi thành phần được tính ngay lập tức cho một nhân viên mẫu. Bấm vào tên mẫu để đổi sang nhân viên khác và xem các giá trị tính lại."),
        },
      },
      {
        key: "add", anchor: "fs-add", act: "observe",
        say: {
          title: B("Add a component, or a whole sheet", "Thêm một thành phần, hoặc cả một trang tính"),
          body: B("Need a new allowance or deduction? The plus adds one component. The same control imports an entire Excel sheet, which is scored before anything is saved.",
                  "Cần thêm một khoản phụ cấp hay khấu trừ? Dấu cộng thêm một thành phần. Cũng chính nút đó nhập cả một trang Excel, và bản nhập được chấm điểm trước khi có gì được lưu."),
        },
      },
      {
        key: "editai", anchor: "fs-editai", act: "observe",
        say: {
          title: B("Edit by describing it", "Sửa bằng cách mô tả"),
          body: B("Change a formula by describing the change in plain language. Whether editing is available to you at all is a permission, set by your administrator.",
                  "Đổi một công thức bằng cách mô tả thay đổi bằng lời. Việc bạn có quyền sửa hay không là do quản trị viên cấp."),
        },
      },
      {
        key: "views", anchor: "fs-views", act: "observe",
        say: {
          title: B("Cards, Grid, Test and Settings", "Thẻ, Lưới, Kiểm thử và Thiết lập"),
          body: B("Four ways to hold the same configuration. Let us open the Grid, which is the one that looks like the spreadsheet this all replaced.",
                  "Bốn cách nhìn cùng một cấu hình. Chúng ta hãy mở Lưới, cách nhìn giống nhất với bảng tính mà hệ thống này thay thế."),
        },
      },
      {
        key: "opengrid", anchor: "fs-view-grid", act: "click", guard: false,
        say: {
          kicker: B("Your turn", "Đến lượt bạn"),
          title: B("Open the Grid", "Mở Lưới"),
          body: B("Every component laid out as spreadsheet columns — column letter, code, formula and its live value. Switching view writes nothing; it is a way of looking.",
                  "Mọi thành phần được bày ra thành các cột bảng tính — chữ cái cột, mã, công thức và giá trị hiện tại. Đổi cách xem không ghi gì cả; đó chỉ là một cách nhìn."),
        },
      },
      {
        key: "canvas", anchor: "grid-canvas", act: "observe", timeout: 5000,
        say: {
          title: B("The full spreadsheet grid", "Toàn bộ lưới bảng tính"),
          body: B("Each component is a column; the rows are its name, category, type, formula, live value and validity. Walk it with the arrow keys, A, B, C… straight across.",
                  "Mỗi thành phần là một cột; các hàng là tên, nhóm, loại, công thức, giá trị hiện tại và tính hợp lệ. Dùng phím mũi tên để đi ngang qua A, B, C…"),
        },
      },
      {
        key: "fbar", anchor: "grid-fbar", act: "observe", timeout: 4000,
        say: {
          title: B("The formula bar", "Thanh công thức"),
          body: B("Click any formula cell and it loads here. Edit it in the bar or press F2 in the cell — the same validated round trip either way, with live feedback as you type.",
                  "Bấm vào ô công thức bất kỳ là nó hiện ở đây. Sửa trong thanh này hoặc bấm F2 ngay trong ô — cả hai đều đi qua cùng một vòng kiểm tra, có phản hồi ngay khi bạn gõ."),
        },
      },
      {
        key: "gridhint", anchor: "grid-hint", act: "observe", timeout: 4000,
        say: {
          title: B("Edit, multi-select and drag-fill", "Sửa, chọn nhiều và kéo điền"),
          body: B("Enter saves, Esc cancels, Ctrl+Z undoes. Shift- or Ctrl-click column headers to set several categories at once, or drag a formula's fill handle sideways to copy it with its references translated.",
                  "Enter để lưu, Esc để huỷ, Ctrl+Z để hoàn tác. Giữ Shift hoặc Ctrl rồi bấm tiêu đề cột để đặt nhóm cho nhiều cột cùng lúc, hoặc kéo tay cầm điền của một công thức sang ngang để sao chép kèm dịch tham chiếu."),
        },
      },
      {
        key: "payai", anchor: "fs-payai", act: "observe",
        say: {
          title: B("The copilot knows this configuration", "Trợ lý hiểu cấu hình này"),
          body: B("Ask it to explain a rule or draft a new one. That is Formula Studio — spreadsheet power without a spreadsheet to keep in a folder.",
                  "Hãy nhờ nó giải thích một quy tắc hoặc phác một quy tắc mới. Đó là Xưởng công thức — sức mạnh bảng tính mà không phải giữ một tệp bảng tính trong thư mục nào cả."),
        },
      },
    ],
  },

  /* ----------------------------------------------------------- sc_import
     tour_import. The multi-sheet importer lives INSIDE a backend wizard that
     cannot be opened cold, so this scenario navigates nowhere and its steps
     degrade to centred cards until the learner has the wizard on screen —
     which is exactly what the tour it replaces did, deliberately. */
  {
    key: "sc_import",
    icon: "inbox",
    line: "payrun",
    modes: ["watch"],
    screens: ["import", "importwizard", "formula"],
    name: B("Import a sheet with confidence", "Nhập một trang tính có kiểm chứng"),
    tagline: B("Preview, score and fix — before a single component is saved.",
               "Xem trước, chấm điểm và sửa — trước khi lưu bất kỳ thành phần nào."),
    entry: {},
    steps: [
      {
        key: "intro", act: "observe",
        say: {
          kicker: B("Import confidence", "Điểm tin cậy khi nhập"),
          title: B("A workbook is not trusted, it is checked", "Không tin ngay bảng tính, mà kiểm tra nó"),
          body: B("When you import a workbook of salary rules, Payobook converts every formula and then shows you exactly how clean the result is, before a single component is saved. Open a configuration's importer from Formula Studio and land on the resolution preview to follow along.",
                  "Khi bạn nhập một bảng tính chứa các quy tắc lương, Payobook chuyển đổi từng công thức rồi cho bạn thấy chính xác kết quả sạch tới mức nào, trước khi lưu bất kỳ thành phần nào. Hãy mở trình nhập của một cấu hình từ Xưởng công thức và dừng ở trang xem trước kết quả để đi theo."),
        },
      },
      {
        key: "score", anchor: "imp-confidence", act: "observe", timeout: 3000,
        say: {
          title: B("A score, not a leap of faith", "Một điểm số, không phải một cú nhắm mắt"),
          body: B("The percentage comes from how cleanly the formulas resolved, how many references survived intact and how sane the sample numbers look. A row in red references something that could not be mapped and quietly became zero — which is the exact trap this catches.",
                  "Tỷ lệ phần trăm được tính từ mức độ sạch khi chuyển đổi công thức, số tham chiếu còn nguyên vẹn và độ hợp lý của các con số mẫu. Dòng màu đỏ là dòng tham chiếu tới thứ không ánh xạ được và đã lặng lẽ thành số không — đúng cái bẫy mà bước này bắt được."),
        },
      },
      {
        key: "fix", anchor: "imp-actions", act: "observe", timeout: 3000,
        say: {
          title: B("Fix it before you commit", "Sửa trước khi ghi nhận"),
          body: B("Pick a fix on any broken row and apply it — the score climbs as you go. Nothing is written until you finish, and abandoning the preview leaves the configuration exactly as it was.",
                  "Chọn cách sửa cho dòng bị lỗi rồi áp dụng — điểm số tăng dần theo từng lần sửa. Không có gì được ghi cho tới khi bạn kết thúc, và bỏ dở trang xem trước thì cấu hình vẫn y nguyên."),
          tip: B("Fixing the INPUT here is what stops a wrong payslip later. A row corrected after the commit is a correction somebody has to explain.",
                 "Sửa ĐẦU VÀO ở đây chính là cách chặn một phiếu lương sai về sau. Một dòng sửa sau khi đã ghi nhận là một khoản hiệu chỉnh mà ai đó sẽ phải giải trình."),
        },
      },
    ],
  },

  /* ---------------------------------------------------------- sc_mapping
     tour_mapping. Same shape and same reason as sc_import: the mid/end
     mapping wizard is opened from a configuration, not from a menu. */
  {
    key: "sc_mapping",
    icon: "git-branch",
    line: "setup",
    modes: ["watch"],
    screens: ["formula", "structures"],
    name: B("Map mid-cycle pay to end-cycle", "Ánh xạ lương giữa kỳ sang cuối kỳ"),
    tagline: B("Pair the components of two configurations without matching dozens by hand.",
               "Ghép các thành phần của hai cấu hình mà không phải khớp tay hàng chục dòng."),
    entry: {},
    steps: [
      {
        key: "intro", act: "observe",
        say: {
          kicker: B("Mid to end cycle", "Giữa kỳ sang cuối kỳ"),
          title: B("Two configurations, one month", "Hai cấu hình, một tháng"),
          body: B("A division that pays twice a month has a mid-cycle configuration and an end-cycle one, and their components have to line up. Open the mid/end mapping wizard and pick both configurations to follow along.",
                  "Bộ phận trả lương hai lần một tháng có một cấu hình giữa kỳ và một cấu hình cuối kỳ, và các thành phần của chúng phải khớp nhau. Hãy mở trình ánh xạ giữa kỳ / cuối kỳ và chọn cả hai cấu hình để đi theo."),
        },
      },
      {
        key: "matched", anchor: "map-intro", act: "observe", timeout: 3000,
        say: {
          title: B("Matched by code, then by name", "Khớp theo mã, rồi theo tên"),
          body: B("Auto-suggest pairs components with the same code first — a perfect match — then falls back to name similarity for the rest, and skips anything you have already mapped. Every suggestion shows its confidence and the reason it was made.",
                  "Chức năng gợi ý tự động ghép trước các thành phần trùng mã — khớp tuyệt đối — rồi mới dựa vào độ giống tên cho phần còn lại, và bỏ qua những cặp bạn đã ánh xạ. Mỗi gợi ý đều kèm độ tin cậy và lý do được ghép."),
        },
      },
      {
        key: "accept", anchor: "map-actions", act: "observe", timeout: 3000,
        say: {
          title: B("Suggest, review, accept", "Gợi ý, soát lại, chấp nhận"),
          body: B("Generate the proposals, read them, then accept the confident ones in one go — or take them one at a time. The machine does the tedious first pass; the judgement stays yours.",
                  "Sinh ra các đề xuất, đọc chúng, rồi chấp nhận một lượt những cặp có độ tin cậy cao — hoặc duyệt từng cặp một. Máy làm giúp lượt rà soát nhàm chán đầu tiên; phần phán đoán vẫn là của bạn."),
          tip: B("A component left unmapped is not an error. It is a component that exists in one cycle and not the other, and that is a real thing.",
                 "Một thành phần chưa được ánh xạ không phải là lỗi. Đó là thành phần chỉ có ở một chu kỳ và không có ở chu kỳ kia, và điều đó là bình thường."),
        },
      },
    ],
  },
];

/* =============================================================================
   12. THE JOURNEY'S FRONT DOOR
   -----------------------------------------------------------------------------
   The sidebar SECTION and the leaf inside it. Both are here rather than
   hand-written in the module for one reason: their NAMES are content, and
   content ships in both languages. "Learn" / "Học cùng Payobook" has to reach
   the .po through the same path as every other translatable, or it is a string
   that only a code review can catch when it drifts.

   PHASE C1 MOVED THE LEAF OUT OF Pay Run. Until now the Journey hung off
   `sec_payrun` after Retro, which was honest while the map taught the Pay Run
   desk and became wrong the moment it also taught Overview, People, Insights
   and Compliance: a learner looking for the People lessons would have gone
   hunting inside Pay Run. Learning is now its own destination —
   `technical_key: learn`, sequence 50, so it sits after Compliance (45) and
   before Planning (55), which is where a section that is about the whole
   product rather than one desk belongs.

   `groups` is deliberately empty and there is no field for it: every gated leaf
   in this sidebar hides itself from users who cannot use it, which is right for
   a working screen and wrong for a learning one. Someone who cannot open Run
   Payroll is exactly the person who needs to read what it is before asking for
   access — the Journey marks those stations "not in your menu" rather than
   hiding them.

   `compass` is not a preference. pb_sidebar renders a FIXED icon set and an
   unknown name draws a plain circle, so this is one of the names it knows.
   `technical_key` is required on pb.sidebar.section; a section without one does
   not load at all.

   THE SECTION IS CALLED "Learning", NOT "Learn", and that is the A2 ruling
   applied rather than a style choice: gettext allows ONE msgstr per msgid, and
   "Learn" already means "Học cùng Payobook" as the leaf's name. Two English
   "Learn"s with two different Vietnamese cannot both ship. "Learning" is
   already a string in this module — the topbar suffix, chrome key `learn` —
   with exactly the Vietnamese the section wants, so the two merge into one
   entry instead of fighting over it.
   ========================================================================== */
const SIDEBAR = {
  section: {
    xmlid: "sec_learn",
    technicalKey: "learn",
    sequence: 50,
    showLabel: true,
    name: B("Learning", "Học tập"),
  },
  leaf: {
    xmlid: "item_learn_journey",
    sequence: 10,
    icon: "compass",
    actionXmlid: "pb_learn.action_learn_journey",
    actionTag: "learn_journey",
    name: B("Learn", "Học cùng Payobook"),
  },
};
