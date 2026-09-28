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
     QAIntent   { id, match[], label*, screens, dynamic?, showMe?,
                  watch?, try?, simpler?*,
                  practice?, offer?, blocks[] | roleVariants{} }
                  watch/try name a SCENARIO key that declares that mode; the
                  generator refuses one that does not (a dead button is an
                  offer made and not kept).
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
    hubLead: "Learn payroll one screen at a time. You start from zero. Nothing you do here touches your company's data.",
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
      // LEARN REFRESH step 4 — the rail's own words for the two new lines.
      lifecycle: "Lifecycle", workforce: "Workforce",
    },
    /* LEARN REFRESH step 4 — a station whose tab this reader's company has
       not given them (the hub's own gate says so), the docked lesson card on
       a narrow screen, and the Lifecycle line's one-person road. */
    gatedChip: "No access in your company",
    gatedBody: "You don't have access to this in your company — you can still read the lesson.",
    cardFold: "Fold the card to see the screen",
    cardUnfold: "Show the card again",
    lifeTrailTitle: "One person's road",
    lifeTrailLead: "Follow Hoàng Văn Nam from the day his job was asked for to his last day. Each lesson you finish lights his next stop.",
    lifeTrailLater: "years later",
    lifeTrailHere: "Nam is here",
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
    notVisibleBody: "This screen is not in your menu yet, so you cannot open it. You can still read what it does. You can also read what to ask for if you need it.",
    // A screen you CAN open, that simply does not have a menu line of its own
    // any more. Naming the door is the whole point: "not in your menu" was
    // wrong for these, and wrong in the direction that makes a reader stop.
    reachVia: "Open it from",
    reachViaBody: "This screen no longer has its own menu line. Open the one named above, and you will find this screen inside it.",
    /* -- LEARN REFRESH step 1: the helper knows every tab ----------------- */
    hubTabs: "Tabs on this page",
    hubOften: "People often come here to",
    takeMeThere: "Take me there",
    youAreHere: "You are here",
    hubNoLesson: "This tab has no lesson yet. Here is what it is for, and what else is on this page.",
    hubAllTabs: "All tabs in",
    hubTabGone: "That tab is not open to you here, so I did not move.",
    hubTabClosed: "This tab is not open to you. If you need it, ask your administrator. Here is what it is for.",
    helperLoading: "Getting the guide ready…",
    helperFailed: "The guide could not load just now. Your screen is not affected. Close the helper and open it again, or use the Ask tab.",
    scNoAccessT: "You can't open this screen",
    scNoAccessA: "You don't have access to",
    scNoAccessB: ". Ask your administrator, or try this lesson in the practice company.",
    scTryPractice: "Try in practice",
    findItIn: "Find it in",
    openScreenIn: "Open",
    outlineNote: "This is a short guide, not a full lesson. It covers what the screen is, why it matters, when to use it, and the mistakes it saves you from.",
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
    // "Before you do this" is the consequence card. It always answers three
    // questions in the same order, so a learner learns the SHAPE of a
    // consequence and starts asking it of controls nobody taught them.
    tryAgain: "Try again",
    finish: "Finish",
    continueBtn: "Continue",
    consequence: "Before you do this",
    /* -- missions -------------------------------------------------------- */
    missions: "Practice missions",
    missionsLead: "Do it once where it cannot matter, before you do it where it can.",
    startMission: "Start mission",
    outlineMission: "Outline",
    liveNotYet: "This is a live capstone. It works on real records in the Payobook demo world, so only a demo account can open it. The practice mission above teaches the same judgement, safely, wherever you are.",
    liveBadge: "Live \u00b7 demo world",
    liveStart: "Start the live mission",
    liveReal: "This one is real",
    liveRealBody: "Every step below happens in Payobook itself. Other people can see the records you touch. Nothing here is a copy, and nothing is undone for you when you leave.",
    liveNudge: "Rehearse it first?",
    liveNudgeBody: "The practice mission asks the same judgement of you, on made-up data where nothing can matter. You do not have to \u2014 this is a nudge, not a lock.",
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
      notDemo: "Live missions need the demo world. This one works on real records in the Payobook demo company. Your session is somewhere else.",
      noDivision: "You do not have a division yet. Open Pay Run › Run once and you will be given one. Each demo account drives its own division's June run.",
      noRun: "Your division has no June run yet. Open Pay Run › Run, pick your division's pay scheme and compute it.",
      noSlips: "The run exists, but it has no payslips yet. Press Compute in the wizard.",
      computed: "%(count)s payslips computed for %(division)s.",
      stillDraft: "Still a draft. Press Submit for approval on its card in Pay Run › Runs.",
      noDecisionYet: "Nobody has approved a step on this pay run yet.",
      allGatesDone: "Done — every step on its route has said yes.",
      noSuchCheck: "There is no check called '%(key)s'.",
      noSuchStep: "No step '%(step)s' in mission '%(mission)s'.",
      notLive: "'%(mission)s' is a practice mission — it has nothing to check on the server.",
      notVerified: "Step '%(step)s' is not verified by the server.",
      stateDraft: "Draft",
      statePending: "Waiting for approval",
      stateDone: "Done",
      stateRejected: "Rejected",
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
    scenariosLead: "One task, three ways. Watch it happen. Try it where nothing can matter. Or do it for real, with me waiting beside you.",
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
    scWaitingBody: "This button writes something real. I will not press it for you. I will not move on by myself either.",
    scWouldDo: "What this would do",
    scNudge: "Not that one — try the glowing control.",
    scTyping: "Typing",
    scExpected: "Expected",
    scSkip: "Skip this step",
    scNotOnScreen: "That control is not on this screen right now. So here is what it does, rather than an arrow pointing at nothing.",
    scDone: "End of the walkthrough",
    scDoneBody: "That is the whole story. Take it again another way whenever you like. The steps are the same — only who presses changes.",
    /* -- input steps inside Try (LEARNOS Phase 5) -------------------------
       A Try step may ask the learner to TYPE. The card says what is wanted;
       the value is checked loosely — spaces, capitals and thousands marks are
       forgiven, a different value is not. A wrong value can never advance the
       walkthrough, so the hint below is the only thing a mismatch produces. */
    scTypeHere: "Type it in the field I am pointing at, then press Enter.",
    scNotYet: "That is not the value yet. Read the card and type it again.",
    /* -- practice mode: the free-roam sandbox (LEARNOS Phase 5) -----------
       The practice company, with the menu switched on. No walkthrough, no
       step counter, no right answer: a learner opens screens and reads them.
       The watermark says on every screen that none of it is real, and the
       view builder draws it whatever the state — see practiceShellHTML. */
    practiceMode: "Practice mode",
    practiceModeLead: "Open the practice company and click around. Every screen is here. Nothing you press reaches a real record.",
    practiceOpen: "Open practice mode",
    practiceWatermark: "Practice company — nothing here is real.",
    practiceHint: "Use the rail on the left and the tabs above the screen to move around. Leave when you are done.",
    // LEARN REFRESH step 2 — what the replica says after a press on its rail
    // or tabs that does not open a screen. Never a dead click.
    replicaQuiet: "Not in the practice company. In Payobook it is",
    replicaQuietTip: "Not in the practice company",
    replicaGuided: "The lesson moves the screen for you. Press Next to go on.",
    /* -- what to learn next (LEARNOS Phase 6) -----------------------------
       ONE SUGGESTION, WITH ITS REASON. `learn.runtime.next_best()` picks the
       station and picks the sentence: the reason is authored per RULE, so the
       learner is told why this one and not just handed a card. Nothing here is
       computed from anybody else's progress — the whole decision is made from
       this learner's own rows, on this server, and never leaves it. */
    nbTitle: "Continue",
    nbGo: "Open this one",
    // A SECOND KEY, not a sentence built in the page. The live capstone is a
    // mission, and "Open this one" beside a mission card reads as a lesson —
    // which is the one thing it is not. Two keys is also what makes both
    // wordings visible to the translator and to the register gate; a string
    // assembled from a condition is invisible to both.
    nbGoMission: "Open this mission",
    nbResume: "You started this one. Pick up where you stopped.",
    nbFinishLine: "You are close to finishing this section. This is the next lesson in it.",
    nbRequired: "This is the next lesson the map asks for.",
    nbCapstone: "The lessons are done. This one is real work, in the demo world.",
    nbOptional: "Everything required is done. This one is extra, and it is useful.",
    // RENDERED, not swallowed. `next_best` returns this reason with no key at
    // all, and both surfaces used to draw nothing for it — so the one learner
    // who finished everything was the one the feature went silent on.
    nbAllDone: "You have finished every lesson here. Practice mode is always open.",
    /* -- the skill tree and the streak (LEARNOS Phase 6) -------------------
       Both are DERIVED and neither is stored. A tier is read off the progress
       row the lesson already wrote; a streak is counted from this learner's
       own events, in their own time zone. There is no notification, no league
       table and no comparison with anybody else — a broken streak simply
       resets, quietly, and nothing says a word about it. */
    lineProgress: "done in this section",
    tierBronze: "Finished",
    tierSilver: "Finished, second try",
    tierGold: "Right first time",
    tierHint: "Gold means you got the understanding check right on the first answer.",
    // Lower case: it is rendered after the number ("3 days in a row"), so a
    // capital here puts one in the middle of a phrase.
    streakTitle: "days in a row",
    streakHint: "Days in a row with at least one lesson opened. Miss a day and it starts again.",
    /* -- the first-run welcome (LEARNOS Phase 3) --------------------------
       ONE CARD, ONCE, ON A REAL TENANT. Shown to somebody who has just
       logged into their own Payobook for the first time, and never again
       after they answer it either way. It OFFERS the welcome walkthrough
       and does not start it: the same ruling as the demo greeting, which
       opens the map and stops. A card that begins moving before you have
       read anything is the thing people learn to dismiss.

       "Later" is a real answer and the card takes it. There is no third
       state and nothing nags: the same walkthrough sits on the dashboard
       checklist and in the Coach for as long as it is useful. */
    welcomeTitle: "Welcome to Payobook",
    welcomeBody: "Want a 2-minute look around first? I will show you the screens you use most.",
    welcomeGo: "Watch the tour",
    welcomeLater: "Later",
    /* -- the Coach ------------------------------------------------------- */
    coachName: "Payobook helper",
    stuck: "Stuck?",
    askPlaceholder: "Ask about this screen…",
    honest: "I explain — you act. I never compute a pay run, approve a payslip or change a record for you.",
    groundedIn: "Grounded in this screen:",
    coachNoScreen: "This screen has no lesson yet. You can still ask me anything in the box below.",
    suggested: "Suggested for this screen",
    canAnswer: "What I can answer here",
    showMe: "Show me",
    pointNotHere: "That control is not on this screen right now. I will not pretend to point at it.",
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
    /* -- explain this screen (LEARNOS Phase 4) ----------------------------
       A question nobody has to phrase. The drawer's header carries it, and
       the answer is built from what this module already holds about the
       screen: what it is, what to do next here, and what its columns count.
       No provider is needed for any of that — see learn_intent.explain_screen,
       where the composer may only REWRITE a floor that already exists. */
    explainScreen: "Explain this screen",
    explainHint: "What this screen is, what to do next, and what its numbers mean.",
    screenAnswer: "From this screen's own guide",
    notSure: "Not sure what to ask?",
    /* -- LEARN v3: one helper ---------------------------------------------
       The Coach and PayAI used to be two floating buttons that knew nothing
       about each other. They are now one button with three tabs. The Ask
       tab is PayAI's chat, drawn inside this drawer when PayAI is installed;
       without it the drawer shows two tabs and says nothing about a third. */
    orbLabel: "Ask Payobook",
    orbHint: "Help for this screen. Press ? on any screen.",
    onScreen: "On:",
    tabGuide: "Guide me",
    tabAsk: "Ask",
    tabPractice: "Practice",
    nextStep: "Your next step",
    thisScreen: "This screen",
    askDataInstead: "Ask about your pay data instead",
    askDataLead: "The guide has no answer for that. The Ask tab can look at your own pay data.",
    practiceTry: "Try it on the practice company",
    practiceTour: "Take the tour",
    practiceTourLead: "The whole product in one pass. You watch, nothing is pressed.",
    /* -- LEARN v3: the path, month-end, moments, team --------------------
       Scene 2 turns the map into three chapters with a path per role; scene
       4 brings short notes onto the real screens; the Team lens is for
       payroll managers and shows progress only. */
    /* LEARN REFRESH step 5 — six chapters over the final station set. */
    ch1Title: "Get around",
    ch1Lead: "Where things live, what is waiting, and who signs what.",
    ch2Title: "Run pay",
    ch2Lead: "One month of pay, from the first compute to money out.",
    ch3Title: "Set up pay",
    ch3Lead: "The rules, the sources and the approvals a pay scheme runs on.",
    ch4Title: "People and their journeys",
    ch4Lead: "Everyone you employ, their pay, and their road from hiring to leaving.",
    ch5Title: "Workforce",
    ch5Lead: "The team's day, their time, and closing the week.",
    ch6Title: "Understand and comply",
    ch6Lead: "What the numbers say, and what the law asks of you.",
    chOff: "Not on your path",
    chMins: "min on your path",
    roleLabel: "I am the",
    roleOfficer: "Payroll officer",
    roleApprover: "Approver",
    roleHr: "HR admin",
    roleManager: "People manager",
    roleOwner: "Owner",
    roleGuess: "Picked from your access. Change it any time.",
    roleNeeds: "Required for you:",
    lessonsWord: "lessons",
    aboutWord: "about",
    offPath: "Not on your path",
    monthEndTitle: "Before month-end",
    monthEndIn: "Changes close in",
    monthEndToday: "Changes close today",
    daysWord: "days",
    dayWord: "day",
    monthEndBody: "A short refresher on what to check before a run goes for approval.",
    monthEndSkip: "Skip this month",
    fvOn: "First time on",
    fvLater: "Not now",
    msEmployeeT: "Your company has its first employee",
    msEmployeeB: "Next, give them a contract, so payroll knows what to pay them.",
    msRunT: "Your company's first pay run is here",
    msRunB: "Nothing is paid yet. Open one payslip and read it from top to bottom before the run goes for approval.",
    msSubmittedT: "A pay run went for approval",
    msSubmittedB: "Nothing is paid yet. The approver sees it in their inbox. Once they sign, it can be paid.",
    msDoneT: "Your first pay run is finished",
    msDoneB: "Next come the government reports for the month.",
    msGo: "What happens next",
    msOk: "Fine, thanks",
    teamLens: "Team",
    teamTitle: "Who is ready for month-end",
    teamLead: "The required lessons on each person's path. Progress only. Nobody's questions are shown here.",
    teamReady: "Ready",
    teamStarted: "In progress",
    teamNot: "Not started",
    teamRemind: "Send a reminder",
    teamReminded: "Reminder sent",
    teamNext: "Next:",
    teamLeft: "min left",
    teamLastSeen: "Last in Learn:",
    teamNever: "never",
    teamGuessed: "path guessed from access",
    teamEmpty: "Nobody in this company works on payroll yet.",
    teamOnly: "Only a payroll manager or an administrator can see the team.",
    teamOf: "of",
    teamReadyWord: "people are ready",
    teamFailed: "That reminder did not send. Try again.",
    scJump: "Go back to this step",
    scSwitch: "Switch mode",
    /* -- LEARN v3: learning settings (Learn > Settings) -------------------
       Every learning switch in one place, in plain words. Each switch says
       what it turns on and whether anything leaves Payobook. Only an
       administrator sees this lens, and the server asks again. */
    setTitle: "Learning settings",
    setLead: "Every learning switch in one place. Each one says what it turns on and whether anything leaves Payobook.",
    setAdminOnly: "Only an administrator can change these.",
    setSaved: "Saved",
    setFailed: "That did not save. Nothing was changed.",
    swOn: "On",
    swOff: "Off",
    swStays: "Stays inside Payobook",
    swNextTitle: "Suggest the next step",
    swNextBody: "The helper and the lesson map show one next lesson, with the reason it was picked. Chosen by fixed rules inside Payobook.",
    swSkillTitle: "Streaks and badge levels",
    swSkillBody: "Shows days in a row, and bronze, silver or gold on each finished lesson. Gold means the quiz was right the first time.",
    swComposeTitle: "Written answers from the guide",
    swComposeBody: "When no written answer fits a question, your AI service writes one from the lesson text only. These answers are marked so readers can tell.",
    swComposeLeaves: "Sends lesson text to your AI service. Never employee or pay data.",
    swVoiceTitle: "Talk to the helper",
    swVoiceBody: "Adds a microphone to the Ask tab. Each person agrees once before anything is recorded. What they say becomes text they check before sending.",
    swVoiceLeaves: "Sends the recording to a speech service.",
    swCollectTitle: "Learn from the questions people ask",
    swCollectBody: "Keeps questions for 180 days so we can see what the lessons miss. Each person also agrees in the helper. Names and amounts are removed first.",
    swNoProvider: "No AI service is set up yet, so this changes nothing until one is.",
    swNoSpeech: "No speech service is set up yet, so this changes nothing until one is.",
    /* -- storing questions: asked once, remembered either way -------------
       The three promises this card makes are checked against the code:
       test_04d asserts that the 180 days here is the same integer as
       RETENTION_DAYS, and that the row really does carry the learner's name.
       Reword the promises and the test fails, which is the point. */
    consentTitle: "Help improve the guide?",
    consentBody: "If you allow it, we store the question you just asked. That is how we see what the guide does not cover yet. Names and amounts are removed before anything is saved. The stored question does carry your name — that is how you can find yours and delete it at any time. We delete stored questions after 180 days. Say no and nothing is stored. The Coach works exactly the same either way.",
    consentYes: "Yes, store my questions",
    consentNo: "No, do not store them",
    /* -- the practice replica -------------------------------------------- */
    practiceBanner: "Practice company. Nothing you do here reaches a real employee, payslip or pay run.",
    employees: "employees",
    needReview: "Need review",
    compute: "Compute payslips",
    runPayroll: "Run payroll",
    submitReview: "Submit for approval",
    reject: "Reject",
    bankFile: "Bank file",
    journals: "Journals",
    startImport: "Load pay data",
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
    hubLead: "Học tính lương từng màn hình một. Bạn bắt đầu từ con số không. Không thao tác nào ở đây chạm tới dữ liệu công ty bạn.",
    yourJourney: "Hành trình của bạn",
    overall: "Tiến độ chung",
    badge: "Huy hiệu Chạy lương",
    badgeGot: "Đã đạt huy hiệu Chạy lương",
    search: "Tìm trong hành trình",
    lines: {
      payrun: "Chạy lương", setup: "Thiết lập", overview: "Tổng quan",
      people: "Nhân sự", insights: "Phân tích", compliance: "Tuân thủ",
      lifecycle: "Vòng đời nhân sự", workforce: "Lực lượng lao động",
    },
    gatedChip: "Công ty bạn chưa cấp quyền",
    gatedBody: "Bạn chưa có quyền mở màn hình này trong công ty — bạn vẫn đọc được bài học.",
    cardFold: "Thu gọn thẻ để xem màn hình",
    cardUnfold: "Mở lại thẻ",
    lifeTrailTitle: "Hành trình của một người",
    lifeTrailLead: "Theo chân Hoàng Văn Nam từ ngày vị trí của anh được đề xuất tuyển tới ngày làm việc cuối cùng. Mỗi bài bạn học xong thắp sáng chặng tiếp theo của anh.",
    lifeTrailLater: "nhiều năm sau",
    lifeTrailHere: "Nam đang ở đây",
    /* -- station cards -------------------------------------------------- */
    fullLesson: "Bài học đầy đủ",
    outline: "Dàn ý",
    required: "Bắt buộc",
    optional: "Tuỳ chọn",
    est: "Khoảng",
    min: "phút",
    startHere: "Bắt đầu từ đây",
    notVisible: "Không có trong menu của bạn",
    notVisibleBody: "Màn hình này chưa có trong menu của bạn nên bạn chưa mở được. Bạn vẫn đọc được rằng nó dùng để làm gì. Bạn cũng đọc được rằng mình cần xin quyền gì nếu cần tới nó.",
    reachVia: "Mở từ",
    reachViaBody: "Màn hình này không còn dòng menu riêng nữa. Bạn hãy mở dòng menu ghi ở trên, rồi tìm màn hình này ở bên trong.",
    /* -- LEARN REFRESH step 1: the helper knows every tab ----------------- */
    hubTabs: "Các tab trên trang này",
    hubOften: "Mọi người thường đến đây để",
    takeMeThere: "Đưa tôi tới đó",
    youAreHere: "Bạn đang ở đây",
    hubNoLesson: "Tab này chưa có bài học. Đây là công dụng của nó, và những gì khác có trên trang này.",
    hubAllTabs: "Tất cả các tab trong",
    hubTabGone: "Tab đó không mở được với bạn ở đây, nên tôi chưa chuyển trang.",
    hubTabClosed: "Tab này chưa mở với bạn. Nếu cần, hãy hỏi quản trị viên. Đây là công dụng của nó.",
    helperLoading: "Đang chuẩn bị phần hướng dẫn…",
    helperFailed: "Phần hướng dẫn chưa tải được lúc này. Màn hình của bạn không bị ảnh hưởng. Hãy đóng trợ lý rồi mở lại, hoặc dùng tab Hỏi đáp.",
    scNoAccessT: "Bạn không mở được màn hình này",
    scNoAccessA: "Bạn chưa có quyền mở",
    scNoAccessB: ". Hãy hỏi quản trị viên, hoặc thử bài này trong công ty thực hành.",
    scTryPractice: "Thử trong công ty thực hành",
    findItIn: "Nằm ở",
    openScreenIn: "Mở",
    outlineNote: "Đây là bài giới thiệu ngắn, chưa phải bài học đầy đủ. Nó nói màn hình này là gì, vì sao quan trọng, khi nào dùng, và giúp bạn tránh được những lỗi nào.",
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
    liveNotYet: "Đây là nhiệm vụ tổng kết. Nó làm việc trên dữ liệu thật của môi trường demo Payobook, nên chỉ tài khoản demo mới mở được. Nhiệm vụ thực hành ở trên rèn đúng phán đoán đó, một cách an toàn, ở bất kỳ đâu.",
    liveBadge: "Trực tiếp \u00b7 môi trường demo",
    liveStart: "Bắt đầu nhiệm vụ trực tiếp",
    liveReal: "Nhiệm vụ này là thật",
    liveRealBody: "Mọi bước dưới đây diễn ra ngay trong Payobook. Người khác cũng nhìn thấy những bản ghi bạn chạm vào. Ở đây không có bản mô phỏng nào, và cũng không có gì tự hoàn tác khi bạn thoát.",
    liveNudge: "Tập dượt trước nhé?",
    liveNudgeBody: "Nhiệm vụ thực hành hỏi bạn đúng phán đoán đó, trên dữ liệu giả lập, nơi không có hậu quả nào. Bạn không bắt buộc phải làm \u2014 đây là lời nhắc, không phải khoá chặn.",
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
      notDemo: "Nhiệm vụ trực tiếp cần môi trường demo. Nhiệm vụ này làm việc trên dữ liệu thật của công ty demo Payobook. Phiên của bạn đang ở nơi khác.",
      noDivision: "Bạn chưa có bộ phận nào. Hãy mở Đợt lương › Chạy lương một lần là bạn sẽ được gán. Mỗi tài khoản demo tự chạy đợt lương tháng 6 của bộ phận mình.",
      noRun: "Bộ phận của bạn chưa có đợt lương tháng 6. Hãy mở Đợt lương › Chạy lương, chọn chương trình lương của bộ phận bạn và tính.",
      noSlips: "Đợt lương đã có, nhưng chưa có phiếu lương nào. Hãy bấm Tính trong trình hướng dẫn.",
      computed: "Đã tính %(count)s phiếu lương cho %(division)s.",
      stillDraft: "Vẫn là bản nháp. Hãy bấm Gửi để phê duyệt trên thẻ của nó ở Đợt lương › Các đợt lương.",
      noDecisionYet: "Chưa ai phê duyệt bước nào của kỳ lương này.",
      allGatesDone: "Hoàn tất — mọi bước trên lộ trình phê duyệt đã đồng ý.",
      noSuchCheck: "Không có phép kiểm tra nào tên '%(key)s'.",
      noSuchStep: "Không có bước '%(step)s' trong nhiệm vụ '%(mission)s'.",
      notLive: "'%(mission)s' là nhiệm vụ thực hành — không có gì để kiểm tra trên máy chủ.",
      notVerified: "Bước '%(step)s' không được máy chủ xác minh.",
      stateDraft: "Nháp",
      statePending: "Đang chờ phê duyệt",
      stateDone: "Hoàn tất",
      stateRejected: "Đã từ chối",
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
    scenariosLead: "Một việc, ba cách học. Xem tôi làm. Tự thử ở nơi không có hậu quả. Hoặc làm thật, với tôi đứng chờ bên cạnh.",
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
    scWaitingBody: "Nút này ghi dữ liệu thật. Tôi sẽ không bấm hộ bạn. Tôi cũng không tự chuyển sang bước sau.",
    scWouldDo: "Nút này sẽ làm gì",
    scNudge: "Không phải nút đó — hãy thử nút đang phát sáng.",
    scTyping: "Đang nhập",
    scExpected: "Cần nhập",
    scSkip: "Bỏ qua bước này",
    scNotOnScreen: "Nút đó hiện không có trên màn hình này. Vậy nên tôi mô tả nó ở đây, thay vì chỉ mũi tên vào chỗ trống.",
    scDone: "Hết phần hướng dẫn",
    scDoneBody: "Đó là toàn bộ câu chuyện. Bạn xem lại theo cách khác bất cứ lúc nào cũng được. Các bước vẫn thế — chỉ khác ở chỗ ai là người bấm.",
    /* -- input steps inside Try (LEARNOS Phase 5) ------------------------- */
    scTypeHere: "Hãy gõ vào ô tôi đang chỉ, rồi bấm Enter.",
    scNotYet: "Giá trị này chưa đúng. Hãy đọc lại thẻ và gõ lại.",
    /* -- practice mode: khu thực hành tự do (LEARNOS Phase 5) ------------- */
    practiceMode: "Chế độ thực hành",
    practiceModeLead: "Mở công ty thực hành và bấm thoải mái. Mọi màn hình đều có ở đây. Không nút nào chạm tới dữ liệu thật.",
    practiceOpen: "Mở chế độ thực hành",
    practiceWatermark: "Công ty thực hành — không có gì ở đây là thật.",
    practiceHint: "Dùng thanh bên trái và các tab phía trên màn hình để đi lại. Xong việc thì bấm thoát.",
    replicaQuiet: "Không có trong công ty thực hành. Trong Payobook, nó nằm ở",
    replicaQuietTip: "Không có trong công ty thực hành",
    replicaGuided: "Bài học tự chuyển màn hình cho bạn. Bấm Tiếp để đi tiếp.",
    /* -- gợi ý học tiếp (LEARNOS Phase 6) --------------------------------- */
    nbTitle: "Học tiếp",
    nbGo: "Mở bài này",
    nbGoMission: "Mở nhiệm vụ này",
    nbResume: "Bạn đã bắt đầu bài này. Hãy học tiếp từ chỗ đang dở.",
    nbFinishLine: "Bạn sắp xong phần này. Đây là bài kế tiếp trong phần đó.",
    nbRequired: "Đây là bài kế tiếp mà lộ trình yêu cầu.",
    nbCapstone: "Bạn đã học xong các bài. Bài này là việc thật, làm trên môi trường demo.",
    nbOptional: "Các bài bắt buộc đã xong. Bài này là bài tự chọn, và rất đáng học.",
    nbAllDone: "Bạn đã học xong mọi bài ở đây. Chế độ thực hành luôn mở.",
    /* -- cây kỹ năng và chuỗi ngày (LEARNOS Phase 6) ----------------------- */
    lineProgress: "bài đã xong trong phần này",
    tierBronze: "Đã xong",
    tierSilver: "Đã xong ở lần thử thứ hai",
    tierGold: "Đúng ngay lần đầu",
    tierHint: "Vàng nghĩa là bạn trả lời đúng phần Kiểm tra hiểu bài ngay lần đầu.",
    streakTitle: "ngày liên tiếp",
    streakHint: "Số ngày liên tiếp bạn mở ít nhất một bài học. Nghỉ một ngày thì đếm lại từ đầu.",
    /* -- the first-run welcome (LEARNOS Phase 3) ------------------------- */
    welcomeTitle: "Chào mừng bạn đến với Payobook",
    welcomeBody: "Bạn muốn xem qua 2 phút trước không? Tôi sẽ chỉ cho bạn những màn hình bạn dùng nhiều nhất.",
    welcomeGo: "Xem hướng dẫn",
    welcomeLater: "Để sau",
    /* -- the Coach ------------------------------------------------------- */
    coachName: "Trợ lý Payobook",
    stuck: "Cần trợ giúp?",
    askPlaceholder: "Hỏi về màn hình này…",
    honest: "Tôi giải thích — bạn thao tác. Tôi không bao giờ tự tính một đợt lương, phê duyệt một phiếu lương hay sửa dữ liệu thay bạn.",
    groundedIn: "Căn cứ trên màn hình này:",
    coachNoScreen: "Màn hình này chưa có bài học. Bạn vẫn có thể hỏi tôi bất cứ điều gì ở ô bên dưới.",
    suggested: "Gợi ý cho màn hình này",
    canAnswer: "Những gì tôi trả lời được ở đây",
    showMe: "Chỉ cho tôi",
    pointNotHere: "Nút đó hiện không có trên màn hình này. Tôi sẽ không giả vờ chỉ vào nó.",
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
    /* -- explain this screen (LEARNOS Phase 4) --------------------------- */
    explainScreen: "Giải thích màn hình này",
    explainHint: "Màn hình này là gì, nên làm gì tiếp, và các con số ở đây nghĩa là gì.",
    screenAnswer: "Từ hướng dẫn của chính màn hình này",
    notSure: "Chưa biết nên hỏi gì?",
    /* -- LEARN v3: one helper -------------------------------------------- */
    orbLabel: "Hỏi Payobook",
    orbHint: "Trợ giúp cho màn hình này. Bấm ? ở bất kỳ màn hình nào.",
    onScreen: "Đang ở:",
    tabGuide: "Hướng dẫn",
    tabAsk: "Hỏi đáp",
    tabPractice: "Thực hành",
    nextStep: "Bước tiếp theo của bạn",
    thisScreen: "Màn hình này",
    askDataInstead: "Hỏi về dữ liệu lương của bạn",
    askDataLead: "Tài liệu hướng dẫn chưa có câu trả lời cho câu này. Thẻ Hỏi đáp có thể xem dữ liệu lương của chính bạn.",
    practiceTry: "Thử trên công ty thực hành",
    practiceTour: "Xem hướng dẫn tổng quan",
    practiceTourLead: "Toàn bộ sản phẩm trong một lượt. Bạn chỉ xem, không có nút nào bị bấm.",
    /* -- LEARN v3: the path, month-end, moments, team ------------------- */
    ch1Title: "Làm quen",
    ch1Lead: "Mọi thứ nằm ở đâu, việc gì đang chờ, và ai ký duyệt việc gì.",
    ch2Title: "Chạy lương",
    ch2Lead: "Một tháng lương, từ lần tính đầu tiên tới lúc chi tiền.",
    ch3Title: "Thiết lập lương",
    ch3Lead: "Các quy tắc, nguồn dữ liệu và phê duyệt mà một chương trình lương dựa vào.",
    ch4Title: "Con người và hành trình của họ",
    ch4Lead: "Mọi người bạn đang thuê, lương của họ, và chặng đường từ tuyển dụng tới nghỉ việc.",
    ch5Title: "Lực lượng lao động",
    ch5Lead: "Một ngày của nhóm, giờ công của họ, và chốt tuần.",
    ch6Title: "Hiểu số liệu và tuân thủ",
    ch6Lead: "Các con số nói gì, và pháp luật yêu cầu bạn điều gì.",
    chOff: "Không thuộc lộ trình của bạn",
    chMins: "phút trên lộ trình của bạn",
    roleLabel: "Tôi là",
    roleOfficer: "Chuyên viên tính lương",
    roleApprover: "Người phê duyệt",
    roleHr: "Quản trị nhân sự",
    roleManager: "Quản lý nhóm",
    roleOwner: "Chủ doanh nghiệp",
    roleGuess: "Chọn theo quyền truy cập của bạn. Bạn đổi lúc nào cũng được.",
    roleNeeds: "Bắt buộc với bạn:",
    lessonsWord: "bài",
    aboutWord: "khoảng",
    offPath: "Không thuộc lộ trình của bạn",
    monthEndTitle: "Trước khi chốt tháng",
    monthEndIn: "Hạn chốt thay đổi còn",
    monthEndToday: "Hôm nay là hạn chốt thay đổi",
    daysWord: "ngày",
    dayWord: "ngày",
    monthEndBody: "Ôn nhanh những gì cần kiểm tra trước khi gửi phê duyệt một đợt lương.",
    monthEndSkip: "Bỏ qua tháng này",
    fvOn: "Lần đầu ở",
    fvLater: "Để sau",
    msEmployeeT: "Công ty đã có nhân viên đầu tiên",
    msEmployeeB: "Tiếp theo, hãy tạo hợp đồng để hệ thống biết cần trả lương bao nhiêu.",
    msRunT: "Đợt lương đầu tiên của công ty đã được tạo",
    msRunB: "Chưa có khoản nào được chi. Hãy mở một phiếu lương và đọc từ trên xuống trước khi gửi phê duyệt.",
    msSubmittedT: "Một đợt lương đã được gửi phê duyệt",
    msSubmittedB: "Chưa có khoản nào được chi. Người phê duyệt sẽ thấy trong hộp thư. Khi họ ký, đợt lương có thể được chi trả.",
    msDoneT: "Đợt lương đầu tiên đã hoàn tất",
    msDoneB: "Tiếp theo là các báo cáo gửi cơ quan nhà nước của tháng.",
    msGo: "Bước tiếp theo là gì",
    msOk: "Đã hiểu",
    teamLens: "Nhóm",
    teamTitle: "Ai đã sẵn sàng cho kỳ chốt lương",
    teamLead: "Các bài bắt buộc trên lộ trình của từng người. Chỉ hiện tiến độ. Không hiện câu hỏi của ai.",
    teamReady: "Sẵn sàng",
    teamStarted: "Đang học",
    teamNot: "Chưa bắt đầu",
    teamRemind: "Gửi lời nhắc",
    teamReminded: "Đã gửi lời nhắc",
    teamNext: "Tiếp theo:",
    teamLeft: "phút còn lại",
    teamLastSeen: "Lần cuối vào Học tập:",
    teamNever: "chưa bao giờ",
    teamGuessed: "lộ trình đoán theo quyền truy cập",
    teamEmpty: "Công ty chưa có ai làm việc với bảng lương.",
    teamOnly: "Chỉ trưởng bộ phận lương hoặc quản trị viên mới xem được nhóm.",
    teamOf: "trên",
    teamReadyWord: "người đã sẵn sàng",
    teamFailed: "Chưa gửi được lời nhắc. Hãy thử lại.",
    scJump: "Quay lại bước này",
    scSwitch: "Đổi chế độ",
    /* -- LEARN v3: learning settings ------------------------------------- */
    setTitle: "Cài đặt học tập",
    setLead: "Mọi công tắc học tập ở cùng một chỗ. Mỗi công tắc nói rõ nó bật tính năng gì và có dữ liệu nào rời khỏi Payobook hay không.",
    setAdminOnly: "Chỉ quản trị viên mới thay đổi được các mục này.",
    setSaved: "Đã lưu",
    setFailed: "Chưa lưu được. Không có gì thay đổi.",
    swOn: "Bật",
    swOff: "Tắt",
    swStays: "Không rời khỏi Payobook",
    swNextTitle: "Gợi ý bước tiếp theo",
    swNextBody: "Trợ lý và bản đồ bài học gợi ý một bài học tiếp theo, kèm lý do chọn bài đó. Lựa chọn dựa trên quy tắc cố định trong Payobook.",
    swSkillTitle: "Chuỗi ngày học và cấp huy hiệu",
    swSkillBody: "Hiện số ngày học liên tiếp, và mức đồng, bạc hoặc vàng trên mỗi bài đã học xong. Vàng nghĩa là trả lời đúng phần kiểm tra ngay lần đầu.",
    swComposeTitle: "Câu trả lời soạn từ tài liệu hướng dẫn",
    swComposeBody: "Khi không có câu trả lời viết sẵn, dịch vụ AI của bạn soạn một câu trả lời chỉ từ nội dung bài học. Các câu trả lời này được đánh dấu để người đọc phân biệt.",
    swComposeLeaves: "Gửi nội dung bài học tới dịch vụ AI của bạn. Không bao giờ gửi dữ liệu nhân viên hay lương.",
    swVoiceTitle: "Nói chuyện với trợ lý",
    swVoiceBody: "Thêm micro vào thẻ Hỏi đáp. Mỗi người đồng ý một lần trước khi ghi âm. Lời nói được chuyển thành chữ để người dùng kiểm tra trước khi gửi.",
    swVoiceLeaves: "Gửi bản ghi âm tới dịch vụ nhận dạng giọng nói.",
    swCollectTitle: "Học hỏi từ câu hỏi của mọi người",
    swCollectBody: "Lưu câu hỏi trong 180 ngày để biết bài học còn thiếu gì. Mỗi người cũng phải đồng ý trong trợ lý. Tên riêng và số tiền được loại bỏ trước.",
    swNoProvider: "Chưa thiết lập dịch vụ AI nào, nên công tắc này chưa có tác dụng.",
    swNoSpeech: "Chưa thiết lập dịch vụ nhận dạng giọng nói nào, nên công tắc này chưa có tác dụng.",
    /* -- storing questions: asked once, remembered either way ------------- */
    consentTitle: "Giúp chúng tôi cải thiện tài liệu hướng dẫn?",
    consentBody: "Nếu bạn đồng ý, chúng tôi lưu lại câu hỏi bạn vừa đặt. Nhờ đó chúng tôi biết tài liệu còn thiếu những gì. Tên riêng và số tiền đều được loại bỏ trước khi lưu. Câu hỏi có lưu kèm tên bạn — nhờ vậy bạn tìm được câu hỏi của mình và xoá đi bất cứ lúc nào. Chúng tôi xoá câu hỏi đã lưu sau 180 ngày. Bạn từ chối thì không có gì được lưu. Trợ lý vẫn hoạt động y như vậy.",
    consentYes: "Đồng ý, hãy lưu câu hỏi của tôi",
    consentNo: "Không, đừng lưu lại",
    /* -- the practice replica -------------------------------------------- */
    practiceBanner: "Công ty thực hành. Mọi thao tác ở đây đều không chạm tới nhân viên, phiếu lương hay đợt lương thật.",
    employees: "nhân viên",
    needReview: "Cần soát xét",
    compute: "Tính phiếu lương",
    runPayroll: "Chạy bảng lương",
    submitReview: "Gửi để phê duyệt",
    reject: "Từ chối",
    bankFile: "Tệp chi lương",
    journals: "Bút toán",
    startImport: "Tải dữ liệu lương",
    commitImport: "Ghi vào hệ thống",
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
   2. GLOSSARY  (rewritten novice-first, LEARNOS Phase 2)
   -----------------------------------------------------------------------------
   One entry per word this desk uses differently from ordinary Vietnamese or
   English. `term` and `def` are separate fields, not one "Term — definition"
   string: an em dash inside a definition would otherwise split it in the wrong
   place, and BHYT's definition legitimately contains one.

   THE FORMAT IS FIXED, and it is two sentences.
     1. What it is, in words a person who has never run payroll already knows.
     2. Why you care — the consequence of not knowing it.
   A definition that only restates the term in longer words is the kind a
   learner reads twice and closes.

   `aliases` is what the HOVERCARD matches, per language, on top of `term`.
   It carries the spellings prose actually uses: plurals, participles, the
   long form beside the abbreviation, and the everyday phrase somebody would
   reach for before they know the term. Longest match wins at render time, so
   listing both "insurance base" and "base" is safe.

   The same table is the jargon gate's index: `tools/jargon.py` refuses to
   build when a term it demands is spelled in a way no entry here matches,
   because a definition the hovercard cannot reach is a definition nobody
   reads. One table, two consumers, on purpose.
   ========================================================================== */
const GLOSSARY = {
  /* -- money on a payslip, before anything else ------------------------- */
  payslip: {
    term: B("Payslip", "Phiếu lương"),
    aliases: { en: ["payslips", "slip", "slips"], vi: ["phiếu lương"] },
    def: B("One person's pay for one month, written out line by line. Read it when somebody asks why their pay is the number it is — every amount added and every amount taken out is on it.",
           "Tiền lương của một người trong một tháng, ghi ra từng dòng. Hãy mở nó khi có người hỏi vì sao lương của họ lại là con số đó — mọi khoản cộng vào và mọi khoản trừ đi đều nằm trên phiếu."),
  },
  gross: {
    term: B("Gross", "Tổng thu nhập"),
    aliases: { en: ["gross pay", "gross total"], vi: ["tổng thu nhập", "tổng lương"] },
    def: B("Everything a person earned this month, before anything is taken out. Gross is the figure every deduction comes off, so it is where you start when you check a payslip.",
           "Toàn bộ những gì một người kiếm được trong tháng, trước khi trừ bất cứ khoản nào. Mọi khoản khấu trừ đều trừ ra từ con số này, nên khi soát một phiếu lương bạn bắt đầu từ đây."),
  },
  net: {
    term: B("Net", "Thực nhận"),
    aliases: { en: ["net pay", "take-home pay", "net total"], vi: ["thực nhận", "lương thực nhận"] },
    def: B("The money that actually reaches the employee's bank account. It is gross minus every deduction, and it is the only number most people ever look at.",
           "Số tiền thật sự về tới tài khoản ngân hàng của nhân viên. Nó bằng tổng thu nhập trừ đi mọi khoản khấu trừ, và với phần lớn mọi người thì đây là con số duy nhất họ nhìn."),
  },
  earning: {
    term: B("Earning", "Khoản thu nhập"),
    aliases: { en: ["earnings"], vi: ["các khoản thu nhập"] },
    def: B("Any line on a payslip that adds money — basic salary, overtime, an allowance. Payobook keeps earnings and deductions apart so you can see which side a change came from.",
           "Bất kỳ dòng nào trên phiếu lương làm tăng tiền — lương cơ bản, tăng ca, một khoản phụ cấp. Payobook tách thu nhập và khấu trừ ra hai bên để bạn thấy ngay một thay đổi đến từ bên nào."),
  },
  allowance: {
    term: B("Allowance", "Phụ cấp"),
    aliases: { en: ["allowances"], vi: ["các khoản phụ cấp"] },
    def: B("Extra money paid on top of the basic salary — lunch, travel, phone, a shift premium. Each one is its own line, so an allowance that stops appearing is a change somebody can point at.",
           "Khoản tiền trả thêm ngoài lương cơ bản — ăn trưa, đi lại, điện thoại, phụ cấp ca. Mỗi khoản là một dòng riêng, nên khi một phụ cấp biến mất thì đó là một thay đổi có thể chỉ ra được."),
  },
  deduction: {
    term: B("Deduction", "Khấu trừ"),
    aliases: { en: ["deductions", "money taken out"], vi: ["các khoản khấu trừ", "khoản trừ"] },
    def: B("Money taken out of a person's pay before they are paid. The two big ones are insurance and tax, and both are set by law rather than by your company.",
           "Khoản tiền trừ ra khỏi lương của một người trước khi chi trả. Hai khoản lớn nhất là bảo hiểm và thuế, và cả hai đều do pháp luật quy định chứ không do công ty bạn chọn."),
  },

  /* -- the batch, and the month it settles ------------------------------ */
  payrun: {
    term: B("Pay run", "Đợt tính lương"),
    aliases: { en: ["pay runs", "pay run"], vi: ["đợt lương", "đợt tính lương", "lô phiếu lương"] },
    def: B("One batch of payslips for one pay scheme and one month. It moves as a single thing: Draft, then Waiting for approval while its approval route decides, then Done. Only a Done run can be paid. Sent back returns it to Draft; turned down or rejected cancels it.",
           "Một lô phiếu lương của một chương trình lương trong một tháng. Cả lô đi như một khối: Nháp, rồi Chờ phê duyệt trong lúc những người trên lộ trình phê duyệt quyết định, rồi Hoàn tất — và chỉ đợt Hoàn tất mới được chi. Trả lại đưa nó về Nháp; bị từ chối thì nó bị huỷ."),
  },

  period: {
    term: B("Period", "Kỳ lương"),
    aliases: { en: ["periods", "pay period"], vi: ["kỳ lương"] },
    def: B("The month a pay run settles. It is not the day you press the button — you can compute June in July, and the period still says June.",
           "Tháng mà một đợt lương quyết toán. Nó không phải ngày bạn bấm nút — bạn có thể tính tháng 6 vào tháng 7, và kỳ lương vẫn là tháng 6."),
  },
  cycle: {
    term: B("Cycle", "Chu kỳ"),
    aliases: { en: ["mid-cycle", "end-cycle"], vi: ["giữa kỳ", "cuối kỳ"] },
    def: B("Which part of the month a run settles. Mid-cycle pays an advance during the month; end-cycle settles the whole month. Most divisions run end-cycle only, so the wrong cycle produces a payslip that is not wrong — just unexpected.",
           "Đợt lương quyết toán phần nào của tháng. Giữa kỳ là khoản tạm ứng trong tháng; cuối kỳ là quyết toán cả tháng. Đa số bộ phận chỉ chạy cuối kỳ, nên chọn nhầm chu kỳ tạo ra một phiếu lương không hẳn sai — chỉ là ngoài dự kiến."),
  },
  division: {
    term: B("Division", "Bộ phận"),
    aliases: { en: ["divisions"], vi: ["các bộ phận"] },
    def: B("A part of the business. Each division usually has its own pay scheme, so the division people work in decides which rulebook pays them.",
           "Một phần của doanh nghiệp. Mỗi bộ phận thường có chương trình lương riêng, nên bộ phận một người làm việc quyết định bộ quy tắc nào trả lương cho họ."),
  },

  draft: {
    term: B("Draft", "Nháp"),
    /* The card still SAYS "Nháp" — that is what the product calls the state.
       It is kept out of the VI match table because it is a syllable of
       "bản nháp" and "phiếu lương nháp", and a bare syllable wraps the wrong
       half of a compound. The compounds are matched instead. */
    matchTerm: { vi: false },
    aliases: { en: ["drafts", "draft payslip", "draft payslips"], vi: ["bản nháp", "bản nháp nào", "phiếu lương nháp", "hợp đồng nháp", "trạng thái Nháp"] },
    def: B("A record Payobook has created that nobody has approved yet. Nothing in draft is paid and nothing is sent, so this is the stage where you are free to fix things.",
           "Bản ghi Payobook đã tạo nhưng chưa ai phê duyệt. Ở trạng thái Nháp thì chưa có gì được chi và chưa có gì gửi đi, nên đây là lúc bạn thoải mái sửa."),
  },
  eligible: {
    term: B("Eligible", "Đủ điều kiện"),
    aliases: { en: ["eligible count", "eligibility"], vi: ["số đủ điều kiện"] },
    def: B("A person the run will actually compute a payslip for. Somebody can be on the roster and still not be eligible — a contract left in draft is the usual reason, and the count is your first warning.",
           "Người mà đợt lương thật sự sẽ tính phiếu lương cho. Một người có tên trong danh sách vẫn có thể không đủ điều kiện — thường là do hợp đồng còn ở trạng thái Nháp, và con số đếm chính là cảnh báo đầu tiên của bạn."),
  },
  recompute: {
    term: B("Recompute", "Tính lại"),
    aliases: { en: ["recomputed", "recomputing", "recalculate"], vi: ["tính lại"] },
    def: B("Running the calculation again after you fix an input. It writes the draft payslips fresh, so anything you typed over by hand is quietly lost — fix the input, never the output.",
           "Chạy lại phép tính sau khi bạn sửa dữ liệu đầu vào. Nó ghi lại phiếu lương nháp từ đầu, nên mọi con số bạn gõ đè bằng tay sẽ âm thầm mất — hãy sửa đầu vào, đừng sửa kết quả."),
  },

  /* -- who has to say yes ------------------------------------------------ */




  rejection: {
    term: B("Rejected", "Đã từ chối"),
    aliases: { en: ["reject", "rejection", "rejecting"], vi: ["bị từ chối"] },
    def: B("A pay run that was turned down in the inbox, or rejected from the Runs board. The run and every payslip in it are cancelled, and it moves to the Rejected pay runs list. It does not come back; a new run has to be made.",
           "Một đợt lương bị từ chối trong hộp phê duyệt, hoặc bị Từ chối trên bảng Các đợt lương. Đợt lương và mọi phiếu lương trong đó bị huỷ, và nó chuyển xuống danh sách Đợt lương bị từ chối. Nó không quay lại; phải tạo một đợt mới."),
  },

  flag: {
    term: B("Flag", "Cờ cảnh báo"),
    aliases: { en: ["flags", "flagged", "need review", "needs review"], vi: ["cần soát xét", "gắn cờ", "bị gắn cờ"] },
    def: B("A mark Payobook puts on something it wants a person to look at: a payslip in a pay run, or a day on Workforce › Close. A flag is a question, not an error — only you can say whether it was meant.",
           "Dấu mà Payobook gắn lên thứ nó muốn có người xem: một phiếu lương trong đợt lương, hoặc một ngày ở Lực lượng lao động › Chốt kỳ. Cờ là một câu hỏi, không phải một lỗi — chỉ bạn mới nói được điều đó có chủ ý hay không."),
  },

  /* -- who has to say yes (LEARN REFRESH step 2) ------------------------- */
  approvalRoute: {
    term: B("Approval route", "Lộ trình phê duyệt"),
    aliases: { en: ["approval routes", "its route", "the route"], vi: ["lộ trình phê duyệt của"] },
    def: B("The steps a request must pass, in order, and who decides each one. Your company draws it in the Approval Matrix. A pay run's default route is Payroll check, then HR lead review, then Finance approval. A published change applies to new requests only.",
           "Các bước một yêu cầu phải đi qua, theo thứ tự, và ai quyết định từng bước. Công ty bạn vẽ nó trong Ma trận phê duyệt. Lộ trình mặc định của một đợt lương là Kiểm tra bảng lương, rồi Trưởng nhân sự soát xét, rồi Tài chính phê duyệt. Thay đổi đã ban hành chỉ áp cho yêu cầu mới."),
  },
  routeStep: {
    term: B("Approval step", "Bước phê duyệt"),
    aliases: { en: ["approval steps", "current step", "its step"], vi: ["bước hiện tại"] },
    def: B("One stop on an approval route, with the person who decides it. A request is yours to decide only when its current step names you.",
           "Một chặng trên lộ trình phê duyệt, kèm người quyết định chặng đó. Một yêu cầu chỉ là của bạn khi bước hiện tại ghi tên bạn."),
  },
  inbox: {
    term: B("Approvals inbox", "Hộp phê duyệt"),
    aliases: { en: ["the inbox", "approval inbox", "My turn"], vi: ["Đến lượt tôi"] },
    def: B("Home › Approvals: one place for everything waiting for a decision, pay runs included. My turn is what is waiting for you.",
           "Trang chủ › Phê duyệt: một nơi cho mọi thứ đang chờ quyết định, kể cả đợt lương. Đến lượt tôi là những gì đang chờ bạn."),
  },
  sentBack: {
    term: B("Sent back", "Trả lại"),
    aliases: { en: ["send it back", "sent back", "sending it back"], vi: ["bị trả lại", "trả lại"] },
    def: B("\"Change this and ask again.\" A sent-back pay run returns to Draft, its payslips editable, with the note on its card. Sent in again, it starts its route from the first step.",
           "\"Sửa điều này rồi xin lại.\" Một đợt lương bị trả lại quay về Nháp, các phiếu lương sửa được, ghi chú nằm trên thẻ của nó. Khi gửi lại, nó đi lại lộ trình từ bước đầu tiên."),
  },
  turnedDown: {
    term: B("Turn it down", "Từ chối"),
    aliases: { en: ["turned down", "turning it down"], vi: ["từ chối yêu cầu"] },
    def: B("\"No.\" The request ends. For a pay run, the run is Rejected and every payslip in it is cancelled, with the reason on the record.",
           "\"Không.\" Yêu cầu kết thúc. Với một đợt lương, đợt lương chuyển sang Đã từ chối và mọi phiếu lương trong đó bị huỷ, kèm lý do trong hồ sơ."),
  },
  payScheme: {
    term: B("Pay scheme", "Chương trình lương"),
    aliases: { en: ["pay schemes", "payroll scheme", "the scheme"], vi: ["các chương trình lương"] },
    def: B("A group of people paid by the same rulebook — its formula configuration. A pay run starts by picking one, under \"Pay run for\".",
           "Một nhóm người được trả lương theo cùng một bộ quy tắc — cấu hình công thức của nó. Một đợt lương bắt đầu bằng việc chọn một chương trình, trong mục \"Đợt lương cho\"."),
  },
  payData: {
    term: B("Pay data", "Dữ liệu lương"),
    aliases: { en: ["pay data file", "this month's pay data"], vi: ["tệp dữ liệu lương"] },
    def: B("This month's figures from a file or a connected system — attendance, overtime, allowances. A scheme that reads a spreadsheet asks for it before it computes.",
           "Số liệu của tháng này từ một tệp hoặc một hệ thống đã kết nối — chấm công, tăng ca, phụ cấp. Chương trình lương đọc bảng tính sẽ xin nó trước khi tính."),
  },
  thisRunOnly: {
    term: B("This run only", "Chỉ đợt này"),
    aliases: { en: ["this run only"], vi: ["chỉ đợt này"] },
    def: B("Use the file's values once, for this run, and change nothing in Payobook. The other answer, Update Payobook, saves them onto people's records from now on.",
           "Dùng các giá trị trong tệp một lần, cho đợt này, và không thay đổi gì trong Payobook. Câu trả lời còn lại, Cập nhật Payobook, lưu chúng vào hồ sơ từ nay về sau."),
  },
  hub: {
    term: B("Rail", "Thanh bên"),
    aliases: { en: ["left rail", "the rail"], vi: ["thanh bên trái"] },
    def: B("The list of nine pages on the left — Home, Pay Run, People and so on. Each page holds its screens as tabs.",
           "Danh sách chín trang ở bên trái — Trang chủ, Đợt lương, Con người và các mục khác. Mỗi trang chứa các màn hình của nó dưới dạng tab."),
  },
  tab: {
    term: B("Tab", "Tab màn hình"),
    aliases: { en: ["tabs"], vi: ["các tab"] },
    def: B("One screen inside a page, like Pay Run › Payslips. A tab you cannot see is one your access does not open.",
           "Một màn hình bên trong một trang, như Đợt lương › Phiếu lương. Tab nào bạn không thấy là tab quyền của bạn không mở được."),
  },

  /* -- part-months, closed months, leavers ------------------------------- */
  proration: {
    term: B("Proration", "Tính theo ngày công (pro-rata)"),
    aliases: { en: ["prorated", "prorate", "pro-rata", "part-month"], vi: ["theo ngày công", "tính theo tỷ lệ ngày công", "lương theo phần tháng"] },
    def: B("Paying part of a month: the monthly amount times the days that count, over the days in the period. Pay Run › Adjust › Proration keeps one line per amount, with the days in its drawer.",
           "Trả lương cho một phần của tháng: mức lương tháng nhân với số ngày được tính, chia cho số ngày của kỳ. Đợt lương › Điều chỉnh › Phân bổ theo tỷ lệ giữ mỗi khoản một dòng, với số ngày trong ngăn chi tiết."),
  },
  joiner: {
    term: B("Joiner", "Người mới vào"),
    aliases: { en: ["joiners", "new hire", "new hires"], vi: ["người vào mới", "nhân viên mới"] },
    def: B("Somebody who started part-way through the month being paid. Their first payslip is prorated, so it is smaller than their salary and that is correct.",
           "Người bắt đầu làm việc vào giữa tháng đang được trả lương. Phiếu lương đầu tiên của họ tính theo ngày công, nên nhỏ hơn mức lương — và như vậy là đúng."),
  },
  leaver: {
    term: B("Leaver", "Người thôi việc"),
    aliases: { en: ["leavers", "departing employee"], vi: ["người nghỉ việc", "nhân viên thôi việc"] },
    def: B("Somebody whose last working day falls inside the month being paid. Leaving mid-month prorates the salary, and the closing payment is handled separately.",
           "Người có ngày làm việc cuối cùng rơi vào trong tháng đang được trả lương. Nghỉ giữa tháng thì lương tính theo ngày công, còn khoản chốt cuối được xử lý riêng."),
  },
  fullFinal: {
    term: B("Full and final", "Quyết toán thôi việc"),
    aliases: { en: ["full & final", "final settlement", "settlement"], vi: ["quyết toán nghỉ việc", "chốt quyết toán"] },
    def: B("The closing payment for somebody who is leaving: last salary, unused leave, anything still owed either way. It has a legal deadline and one chance to be right, because it is the last money that person receives from you.",
           "Khoản chi chốt cho người thôi việc: lương cuối, phép chưa dùng, và mọi khoản còn nợ của cả hai bên. Nó có thời hạn pháp lý và chỉ có một lần làm đúng, vì đây là khoản tiền cuối cùng người đó nhận từ bạn."),
  },
  retro: {
    term: B("Retro adjustment", "Điều chỉnh hồi tố"),
    aliases: { en: ["retro", "retro line", "backdated", "back pay", "back-pay"], vi: ["hồi tố", "dòng hồi tố", "truy lĩnh"] },
    def: B("Money owed for a month that is already paid, added to the current month with the old month named on the line. The pay data import works it out when the scheme's Back-pay switch is on.",
           "Khoản tiền còn nợ của một tháng đã trả, được cộng vào tháng hiện tại và ghi rõ tháng gốc trên dòng. Lần tải dữ liệu lương tự tính khoản này khi công tắc Truy lĩnh của chương trình lương đang bật."),
  },

  /* -- what leaves the building ------------------------------------------ */
  bankFile: {
    term: B("Bank file", "Tệp chi lương"),
    aliases: { en: ["bank files", "payment file"], vi: ["tệp ngân hàng", "tệp chi trả"] },
    def: B("The file the bank reads to move the money. It is generated from the approved run, so a payslip fixed after the file was made is a payslip the bank never heard about.",
           "Tệp mà ngân hàng đọc để chuyển tiền. Nó được kết xuất từ đợt lương đã duyệt, nên một phiếu lương sửa sau khi tệp đã lập là phiếu mà ngân hàng không hề biết tới."),
  },
  journalEntry: {
    term: B("Journal entry", "Bút toán"),
    aliases: { en: ["journal entries", "journals"], vi: ["bút toán kế toán", "hạch toán"] },
    def: B("The accounting record of what payroll cost the company this month. Accounting reads it, not the payslips, so this is where payroll and the books meet.",
           "Bản ghi kế toán về chi phí lương của công ty trong tháng. Kế toán đọc bút toán chứ không đọc phiếu lương, nên đây là nơi bộ phận lương và sổ sách gặp nhau."),
  },

  /* -- the rulebook (Setup) ---------------------------------------------- */
  formulaConfig: {
    term: B("Formula configuration", "Cấu hình công thức"),
    aliases: { en: ["formula configurations", "configuration", "configurations", "rulebook", "config", "configs"], vi: ["cấu hình", "bộ quy tắc tính lương"] },
    def: B("The rulebook that computes every payslip line for one division. It is written like a spreadsheet: inputs, earnings, deductions and totals, each one a named component you can read.",
           "Bộ quy tắc tính từng dòng phiếu lương cho một bộ phận. Nó được viết như một bảng tính: đầu vào, thu nhập, khấu trừ và các tổng, mỗi thứ là một thành phần có tên mà bạn đọc được."),
  },
  component: {
    term: B("Component", "Thành phần"),
    aliases: { en: ["components"], vi: ["các thành phần", "thành phần lương"] },
    def: B("One named line inside a formula configuration, with the formula that produces it. Every figure on a payslip came from a component, so a wrong figure is a wrong component.",
           "Một dòng có tên trong cấu hình công thức, kèm công thức sinh ra nó. Mọi con số trên phiếu lương đều đến từ một thành phần, nên số sai nghĩa là thành phần sai."),
  },
  configCode: {
    term: B("Configuration code", "Mã cấu hình"),
    aliases: { en: ["config code", "configuration codes"], vi: ["mã cấu hình công thức"] },
    /* THE SHAPE PLUS A CONCRETE EXAMPLE, both languages. The ledger's Phase B
       VI ruling is explicit about this: two config-code worlds are correct at
       once (the practice company's HOASEN_*, the demo world's DEMO_*), and the
       fix was never to pick one — it was to say the SHAPE out loud and stand a
       real code beside it. A definition with only the shape sends a learner
       looking for a literal PREFIX. */
    def: B("The short unique name of a formula configuration — what a pay run really uses when you pick its pay scheme. The shape is PREFIX_DIVISION_CYCLE, and the prefix belongs to the company: this practice company writes HOASEN_RETAIL_END, the Payobook demo world writes DEMO_RETAIL_END. Learn the shape, not one code.",
           "Tên ngắn và duy nhất của một cấu hình công thức — chính là thứ một đợt lương thực sự dùng khi bạn chọn chương trình lương. Dạng chung là TIỀN TỐ_BỘ PHẬN_CHU KỲ, và tiền tố là của từng công ty: công ty thực hành này viết HOASEN_RETAIL_END, còn môi trường demo của Payobook viết DEMO_RETAIL_END. Hãy nhớ dạng chung, đừng nhớ một mã cụ thể."),
  },
  salaryStructure: {
    term: B("Salary structure", "Cấu trúc lương"),
    aliases: { en: ["salary structures"], vi: ["cấu trúc lương cũ"] },
    def: B("The older way of computing a payslip, kept because payslips from before the move still point at one. Read them to understand history; write new pay logic in a formula configuration instead.",
           "Cách tính phiếu lương thế hệ trước, được giữ lại vì các phiếu lương từ trước khi chuyển đổi vẫn trỏ tới chúng. Hãy đọc chúng để hiểu lịch sử; còn logic lương mới thì viết trong cấu hình công thức."),
  },
  connector: {
    term: B("Connector", "Đầu nối"),
    aliases: { en: ["connectors", "integration", "integrations"], vi: ["kết nối", "các đầu nối"] },
    def: B("A saved link to a system your payroll data arrives from — an HR system, a time clock, the bank. Data that arrives by itself is data nobody retyped, and a retyped row is where most wrong payslips start.",
           "Một kết nối đã lưu tới hệ thống mà dữ liệu lương đi vào từ đó — hệ thống nhân sự, máy chấm công, ngân hàng. Dữ liệu tự về là dữ liệu không ai phải gõ lại, mà một dòng gõ tay chính là khởi đầu của phần lớn phiếu lương sai."),
  },
  sync: {
    term: B("Sync", "Đồng bộ"),
    aliases: { en: ["synced", "syncs", "last sync", "syncing"], vi: ["lần đồng bộ", "đồng bộ dữ liệu"] },
    def: B("One run of a connector, fetching whatever is new. A connector that stopped syncing looks exactly like one that is working, so the last sync time is the part to read.",
           "Một lần chạy của đầu nối để lấy về dữ liệu mới. Một đầu nối đã ngừng đồng bộ trông y hệt một đầu nối đang chạy tốt, nên thời điểm đồng bộ gần nhất mới là phần cần đọc."),
  },

  /* -- getting the month's data in --------------------------------------- */
  importBatch: {
    term: B("Import batch", "Đợt nhập liệu"),
    aliases: { en: ["import batches", "batch of rows"], vi: ["đợt nhập", "lô nhập liệu"] },
    def: B("One load of a file into Payobook, kept together under a name and a target period. The name says which month the rows are for, and reading it before you commit is the cheapest check there is.",
           "Một lần nạp tệp vào Payobook, gom lại dưới một cái tên và một kỳ lương đích. Cái tên cho biết các dòng này thuộc tháng nào, và đọc nó trước khi ghi nhận là phép kiểm tra rẻ nhất bạn có."),
  },
  commitImport: {
    term: B("Commit", "Ghi nhận"),
    aliases: { en: ["committed", "commits", "committing", "uncommitted"], vi: ["ghi nhận dữ liệu", "đã ghi nhận", "chưa ghi nhận"] },
    def: B("The moment imported rows stop being a preview and become real inputs to payroll. Everything before commit can be thrown away; nothing after it can, so this is the button to slow down at.",
           "Thời điểm các dòng đã nhập thôi là bản xem trước và trở thành dữ liệu đầu vào thật của hệ thống lương. Trước khi ghi nhận thì bỏ đi lúc nào cũng được; sau đó thì không, nên đây là nút bạn cần chậm lại."),
  },
  staging: {
    term: B("Staging", "Vùng chờ"),
    aliases: { en: ["staged", "staged records", "staging area"], vi: ["vùng chờ", "bản ghi chờ"] },
    def: B("Where imported rows wait between arriving and being committed. Rows left sitting in staging are a month of data that never reached payroll, and nothing complains about them.",
           "Nơi các dòng đã nhập nằm chờ giữa lúc về và lúc được ghi nhận. Những dòng bị bỏ quên ở vùng chờ là cả một tháng dữ liệu không bao giờ tới được hệ thống lương, mà chẳng có gì báo động."),
  },
  confidenceScore: {
    term: B("Confidence score", "Điểm tin cậy"),
    aliases: { en: ["confidence"], vi: ["điểm tin cậy của tệp"] },
    def: B("How cleanly a workbook of salary RULES converted when you set up a scheme from Excel in Formula Studio. The month's pay data import has no score — read its counts instead: Rows loaded, Matched, Need attention.",
           "Mức độ chuyển đổi sạch sẽ của một bảng tính chứa QUY TẮC lương khi bạn thiết lập chương trình lương từ Excel trong Xưởng công thức. Việc nhập dữ liệu lương của tháng không có điểm số — hãy đọc các con số: Dòng đã nạp, Đã khớp, Cần xử lý."),
  },
  mapping: {
    term: B("Column mapping", "Ánh xạ cột"),
    aliases: { en: ["mapping", "mapped", "mappings", "match the columns"], vi: ["ánh xạ", "khớp cột"] },
    def: B("Telling Payobook where each value of a pay scheme comes from — which column, which system field, which record. Settings › Integrations › Mapping holds it. Get it wrong and the numbers arrive perfectly, in the wrong place.",
           "Việc chỉ cho Payobook mỗi giá trị của một chương trình lương đến từ đâu — cột nào, trường nào của hệ thống, hồ sơ nào. Cài đặt › Tích hợp › Ánh xạ lưu điều đó. Làm sai thì các con số vẫn về đầy đủ nhưng nằm sai chỗ."),
  },

  /* -- payroll setup (LEARN REFRESH step 3) ------------------------------ */
  guidedSetup: {
    term: B("Guided setup", "Thiết lập có hướng dẫn"),
    aliases: { en: ["new configuration", "the guided setup"], vi: ["cấu hình mới"] },
    def: B("Settings › Guided setup › New configuration: six steps that build one pay scheme, with a sample person's pay shown the whole way. A scheme's own Settings reopens it to edit.",
           "Cài đặt › Thiết lập có hướng dẫn › Cấu hình mới: sáu bước dựng một chương trình lương, luôn hiện lương của một người mẫu. Phần Cài đặt của một chương trình mở lại nó để sửa."),
  },
  startingPoint: {
    term: B("Starting point", "Điểm bắt đầu"),
    aliases: { en: ["starting points", "starter library"], vi: ["thư viện dựng sẵn"] },
    def: B("What a new pay scheme is built from: a ready-made library for the country, your own Excel workbook, or a blank canvas. Certified means the library was checked against the law.",
           "Thứ mà một chương trình lương mới được dựng từ đó: một thư viện dựng sẵn cho quốc gia, sổ tính Excel của bạn, hoặc một trang trắng. Đã chứng nhận nghĩa là thư viện đã được đối chiếu với luật."),
  },
  sampleEmployee: {
    term: B("Sample employee", "Nhân viên mẫu"),
    aliases: { en: ["sample person", "sample employees"], vi: ["người mẫu"] },
    def: B("The person the guided setup computes as you build, so you see real numbers. Only a preview: nobody is paid from it.",
           "Người mà phần thiết lập có hướng dẫn tính lương ngay khi bạn dựng, để bạn thấy con số thật. Chỉ là bản xem trước: không ai được trả lương từ đó."),
  },
  setupCheck: {
    term: B("Setup check", "Bước kiểm tra thiết lập"),
    aliases: { en: ["setup checks", "boundary cases", "run the checks"], vi: ["chạy kiểm tra"] },
    def: B("One awkward case the Test step runs through the real engine — a joiner, a leaver, a tax-band edge. It counts as evidence only once somebody has confirmed it.",
           "Một trường hợp khó mà bước Kiểm thử chạy qua bộ máy tính lương thật — người mới vào, người nghỉ việc, mức biên của bậc thuế. Nó chỉ được tính là bằng chứng khi đã có người xác nhận."),
  },
  schemeProposal: {
    term: B("Scheme proposal", "Đề xuất thay đổi chương trình lương"),
    aliases: { en: ["propose for approval", "scheme proposals"], vi: ["đề xuất để phê duyệt"] },
    def: B("A request to put a scheme live, merge a branch, seal a release, roll one back, or retire it. With an approval route it waits for a yes; without one it happens at once and is recorded.",
           "Một yêu cầu đưa chương trình vào dùng, gộp một nhánh, chốt một phiên bản, quay lại phiên bản cũ, hoặc ngừng dùng. Có lộ trình phê duyệt thì nó chờ được đồng ý; không có thì diễn ra ngay và được ghi lại."),
  },
  dataSource: {
    term: B("Data source", "Nguồn dữ liệu"),
    aliases: { en: ["data sources", "its source", "a source"], vi: ["các nguồn dữ liệu"] },
    def: B("Where a value in a pay scheme comes from: a connected system, a spreadsheet column, or Payobook's own records. Mapping draws them all on the Journey tab.",
           "Nơi một giá trị trong chương trình lương đến từ: một hệ thống đã kết nối, một cột bảng tính, hoặc chính hồ sơ trong Payobook. Ánh xạ vẽ tất cả trên tab Hành trình."),
  },
  sourcePriority: {
    term: B("Source priority", "Thứ tự ưu tiên nguồn"),
    aliases: { en: ["higher source", "lower source"], vi: ["nguồn cao hơn", "nguồn thấp hơn"] },
    def: B("The order a scheme reads its sources in. The higher one wins; a lower source may only fill an empty box, never overwrite one.",
           "Thứ tự mà chương trình lương đọc các nguồn. Nguồn cao hơn thắng; nguồn thấp hơn chỉ được điền vào ô trống, không bao giờ ghi đè."),
  },
  transformationRule: {
    term: B("Transformation rule", "Quy tắc chuyển đổi"),
    aliases: { en: ["transformation rules"], vi: ["phép chuyển đổi"] },
    def: B("A small rule between a system and a scheme that reshapes a value on the way — text to an amount, two fields into one. Mapping's Transformations tab lists them.",
           "Một quy tắc nhỏ giữa hệ thống và chương trình lương, sửa hình dạng một giá trị trên đường đi — chữ thành số tiền, hai trường thành một. Tab Chuyển đổi của Ánh xạ liệt kê chúng."),
  },
  mappingJourney: {
    term: B("Mapping Journey", "Hành trình ánh xạ"),
    aliases: { en: ["the journey tab", "journey board"], vi: ["tab hành trình"] },
    def: B("Mapping's first tab: five lanes — Files & systems, Feeds, Transformations, the Scheme and Payobook Source — with every wire between them.",
           "Tab đầu tiên của Ánh xạ: năm làn — Tệp & hệ thống, Nguồn cấp dữ liệu, Chuyển đổi, Chương trình lương và Nguồn Payobook — cùng mọi dây nối giữa chúng."),
  },
  componentTreatment: {
    term: B("Component treatment", "Xử lý thành phần"),
    aliases: { en: ["treatment board"], vi: ["bảng xử lý thành phần"] },
    def: B("What a scheme does with each component: its pay role, whether it is a subtotal, and its value type. It belongs to the scheme, so it affects every run.",
           "Chương trình lương làm gì với từng thành phần: vai trò trong lương, có phải tổng phụ không, và loại giá trị. Nó thuộc về chương trình, nên ảnh hưởng mọi đợt lương."),
  },
  payRole: {
    term: B("Pay role", "Vai trò trong lương"),
    aliases: { en: ["pay roles"], vi: ["vai trò lương"] },
    def: B("What net pay does with a component: adds it, takes it off, is it, counts it as employer cost, or ignores it. Every gross, deductions and net figure is counted from it.",
           "Thực nhận làm gì với một thành phần: cộng vào, trừ đi, chính là nó, tính là chi phí doanh nghiệp, hay bỏ qua. Mọi con số tổng thu nhập, khấu trừ và thực nhận đều đếm từ đây."),
  },
  subtotal: {
    term: B("Subtotal", "Tổng phụ"),
    aliases: { en: ["subtotal lines"], vi: ["dòng tổng phụ"] },
    def: B("A line whose parts are already counted elsewhere, like gross income. Ticking it stops the totals counting the same money twice.",
           "Một dòng mà các phần của nó đã được tính ở nơi khác, như tổng thu nhập. Đánh dấu nó giúp các tổng không tính cùng một khoản tiền hai lần."),
  },
  valueType: {
    term: B("Value type", "Loại giá trị"),
    aliases: { en: ["value types"], vi: ["kiểu giá trị"] },
    def: B("What a value is: an amount, a quantity such as hours or days, a percentage, text, a date or yes/no. Only an amount can be added to or taken off net pay.",
           "Một giá trị là gì: số tiền, số lượng như giờ hoặc ngày, phần trăm, chữ, ngày tháng hay có/không. Chỉ số tiền mới được cộng vào hoặc trừ khỏi thực nhận."),
  },
  approvalResponsibility: {
    term: B("Approval responsibility", "Trách nhiệm phê duyệt"),
    aliases: { en: ["a responsibility", "each responsibility"], vi: ["trách nhiệm phê duyệt của"] },
    def: B("A seat on an approval route, like HR lead, filled by whoever holds it. Naming the responsibility instead of a person keeps the route working when people change.",
           "Một vị trí trên lộ trình phê duyệt, như Trưởng nhân sự, do người đang giữ vị trí đó đảm nhận. Ghi trách nhiệm thay vì một người giúp lộ trình vẫn chạy khi người thay đổi."),
  },
  approvalCover: {
    term: B("Approval cover", "Người trực thay phê duyệt"),
    aliases: { en: ["arrange cover"], vi: ["sắp xếp người trực thay", "người trực thay"] },
    def: B("Someone who decides for a person while they are away. Set in the Approval Matrix under People & backups; the route itself does not change.",
           "Người quyết định thay cho một người trong lúc họ vắng mặt. Đặt trong Ma trận phê duyệt ở mục Con người & người thay thế; bản thân lộ trình không thay đổi."),
  },
  recordsDesk: {
    term: B("Records Desk", "Bàn cập nhật hồ sơ (Records Desk)"),
    aliases: { en: ["the records desk"], vi: ["bàn records desk"] },
    def: B("People › Records: change the employee, contract and bank fields a pay scheme reads, for many people at once, with Review before anything is saved and Undo after.",
           "Con người › Hồ sơ: sửa các trường nhân viên, hợp đồng và ngân hàng mà chương trình lương đọc, cho nhiều người cùng lúc, có Xem lại trước khi lưu và Hoàn tác sau đó."),
  },
  ratePolicy: {
    term: B("Exchange rate policy", "Cách chọn tỷ giá"),
    aliases: { en: ["how rates are picked", "exchange rates"], vi: ["tỷ giá"] },
    def: B("Which exchange rate the group uses for a month: the last rate of the month, the rate on the day the pay run ends, or the month's average. Changing it needs approval.",
           "Tỷ giá mà tập đoàn dùng cho một tháng: tỷ giá cuối cùng của tháng, tỷ giá vào ngày đợt lương kết thúc, hoặc tỷ giá bình quân của tháng. Thay đổi nó cần phê duyệt."),
  },
  groupCurrency: {
    term: B("Group currency", "Đồng tiền của tập đoàn"),
    aliases: { en: ["the group's currency"], vi: ["đồng tiền tập đoàn"] },
    def: B("The money the group board reads in. Nothing is stored in it: every figure keeps the money it was paid in and is converted only when you look.",
           "Đồng tiền mà bảng số liệu tập đoàn dùng để đọc. Không có gì được lưu bằng nó: mỗi con số giữ nguyên đồng tiền đã trả và chỉ quy đổi khi bạn xem."),
  },
  attendance: {
    term: B("Attendance", "Chấm công"),
    aliases: { en: ["attendance data", "attendance exceptions"], vi: ["dữ liệu chấm công", "ngoại lệ chấm công"] },
    def: B("The record of who worked which days. Payroll cannot see a working day that attendance never recorded, so a missing day is a smaller payslip nobody meant to produce.",
           "Bản ghi ai đã làm những ngày nào. Hệ thống lương không nhìn thấy được ngày công mà chấm công chưa ghi, nên một ngày bị thiếu là một phiếu lương nhỏ hơn mà không ai chủ ý."),
  },
  overtime: {
    term: B("Overtime", "Tăng ca"),
    aliases: { en: ["overtime hours", "OT"], vi: ["giờ tăng ca", "làm thêm giờ"] },
    def: B("Hours worked beyond the normal working time, paid at a higher rate. It moves take-home pay and it does not move insurance, because insurance is charged on the insurance base instead.",
           "Số giờ làm vượt thời gian làm việc bình thường, được trả với mức cao hơn. Nó làm thay đổi tiền thực nhận nhưng không làm thay đổi bảo hiểm, vì bảo hiểm tính trên mức lương đóng bảo hiểm."),
  },

  /* -- people, contracts and permissions --------------------------------- */
  contract: {
    term: B("Contract", "Hợp đồng"),
    aliases: { en: ["contracts", "running contract", "running contracts"], vi: ["hợp đồng lao động", "hợp đồng đang hiệu lực"] },
    def: B("The signed agreement Payobook computes a person's pay from. A person is not a contract: the employee record can be perfect and the run will still skip them if no contract is running.",
           "Thoả thuận đã ký mà Payobook dựa vào để tính lương cho một người. Con người không phải là hợp đồng: hồ sơ nhân viên có hoàn hảo đến đâu, không có hợp đồng đang hiệu lực thì đợt lương vẫn bỏ qua họ."),
  },
  headcount: {
    term: B("Headcount", "Sĩ số"),
    aliases: { en: ["head count"], vi: ["số nhân sự", "quân số"] },
    def: B("How many people the company employs. It is not the same as how many were paid, and the gap between those two numbers is where a missing payslip lives.",
           "Số người mà công ty đang sử dụng lao động. Nó khác với số người đã được trả lương, và khoảng chênh giữa hai con số ấy chính là chỗ một phiếu lương bị thiếu đang nằm."),
  },
  wageBill: {
    term: B("Wage bill", "Quỹ lương"),
    aliases: { en: ["monthly wage bill", "wage total"], vi: ["tổng quỹ lương", "quỹ lương tháng"] },
    def: B("Everybody's contract salary, added up. It is not what the month costs: overtime, allowances and the employer's share of insurance all sit on top of it.",
           "Tổng lương theo hợp đồng của tất cả mọi người. Đây không phải chi phí thật của tháng: tăng ca, phụ cấp và phần bảo hiểm doanh nghiệp đóng đều nằm thêm bên trên."),
  },
  payrollReady: {
    term: B("Payroll-ready", "Sẵn sàng tính lương"),
    aliases: { en: ["payroll ready", "ready to be paid"], vi: ["sẵn sàng chi lương"] },
    def: B("A mark saying somebody can actually be paid — a running contract and a bank account on file. Without it a payslip computes perfectly and the money goes nowhere.",
           "Dấu cho biết một người thật sự có thể được chi trả — có hợp đồng đang hiệu lực và có số tài khoản ngân hàng. Thiếu nó thì phiếu lương vẫn tính hoàn hảo mà tiền không đi đâu cả."),
  },
  group: {
    term: B("Permission group", "Nhóm quyền"),
    aliases: { en: ["groups", "user group", "user groups", "permission groups", "payroll approval groups", "approval groups", "payroll group", "analytics group", "import group"], vi: ["nhóm quyền truy cập", "nhóm quyền phê duyệt", "nhóm quyền"] },
    def: B("What your account is allowed to open and do. A screen missing from your menu is a group you do not hold — not a screen that is broken, and asking for the group is the fix.",
           "Những gì tài khoản của bạn được phép mở và được phép làm. Một màn hình không có trong menu nghĩa là bạn chưa có nhóm quyền đó — không phải màn hình bị lỗi, và cách xử lý là xin cấp nhóm quyền."),
  },

  /* -- what the law asks for --------------------------------------------- */
  statutory: {
    term: B("Statutory", "Luật định"),
    aliases: { en: ["statutory rate", "statutory rates", "required by law"], vi: ["theo luật", "bắt buộc theo luật"] },
    def: B("Set by law rather than by your company. You record a statutory rate in Payobook; you never choose it, and changing one without a document behind it is the first thing an inspection asks about.",
           "Do pháp luật quy định chứ không do công ty bạn quyết. Bạn ghi nhận một tỷ lệ luật định vào Payobook; bạn không chọn nó, và sửa một tỷ lệ mà không có văn bản kèm theo là điều đoàn kiểm tra hỏi đầu tiên."),
  },
  contribution: {
    term: B("Contribution", "Khoản đóng"),
    aliases: { en: ["contributions", "insurance contribution"], vi: ["khoản đóng bảo hiểm", "mức đóng"] },
    def: B("The money paid into an insurance fund each month. Both sides pay: part comes out of the employee's pay and the rest is a cost the company carries on top of the salary.",
           "Số tiền nộp vào quỹ bảo hiểm mỗi tháng. Cả hai bên cùng đóng: một phần trừ vào lương người lao động, phần còn lại là chi phí doanh nghiệp gánh thêm ngoài tiền lương."),
  },
  insuranceBase: {
    term: B("Insurance base", "Mức lương đóng bảo hiểm"),
    aliases: { en: ["registered base", "registered insurance base", "insurance salary", "the base"], vi: ["mức đóng đã đăng ký", "lương đóng BH", "mức lương đóng BH"] },
    def: B("The salary registered for insurance, written into the contract. Insurance is charged on this figure and on nothing else, which is why a month of overtime does not change it.",
           "Mức lương đăng ký để đóng bảo hiểm, ghi trong hợp đồng. Bảo hiểm chỉ tính trên con số này chứ không tính trên gì khác, nên một tháng tăng ca nhiều cũng không làm nó thay đổi."),
  },
  bhxh: {
    term: B("BHXH", "BHXH"),
    aliases: { en: ["social insurance"], vi: ["bảo hiểm xã hội"] },
    def: B("Social insurance — the pension and sickness fund everybody pays into. The employee pays 8% of the insurance base and the company pays 17.5% on top of it.",
           "Bảo hiểm xã hội — quỹ hưu trí và ốm đau mà mọi người đều đóng. Người lao động đóng 8% trên mức lương đóng bảo hiểm, doanh nghiệp đóng thêm 17,5%."),
  },
  bhyt: {
    term: B("BHYT", "BHYT"),
    aliases: { en: ["health insurance"], vi: ["bảo hiểm y tế"] },
    def: B("Health insurance — 1.5% from the employee and 3% from the company. It is charged on the same insurance base as BHXH.",
           "Bảo hiểm y tế — người lao động 1,5% và doanh nghiệp 3%. Tính trên cùng mức lương đóng bảo hiểm như BHXH."),
  },
  bhtn: {
    term: B("BHTN", "BHTN"),
    aliases: { en: ["unemployment insurance"], vi: ["bảo hiểm thất nghiệp"] },
    def: B("Unemployment insurance — 1% from the employee and 1% from the company, on the insurance base. It is the fund that pays somebody while they look for the next job.",
           "Bảo hiểm thất nghiệp — người lao động 1% và doanh nghiệp 1%, trên mức lương đóng bảo hiểm. Đây là quỹ chi trả cho người lao động trong lúc họ tìm việc mới."),
  },
  pit: {
    term: B("PIT (thuế TNCN)", "Thuế TNCN"),
    aliases: { en: ["pit", "personal income tax", "income tax", "thuế TNCN"], vi: ["thuế thu nhập cá nhân", "thuế TNCN"] },
    def: B("Personal income tax, taken out of pay before the employee receives it. The rate rises with income, from 5% to 35%, and it is charged on taxable income rather than on gross.",
           "Thuế thu nhập cá nhân, trừ vào lương trước khi người lao động nhận tiền. Thuế suất tăng dần theo thu nhập, từ 5% đến 35%, và tính trên thu nhập chịu thuế chứ không tính trên tổng thu nhập."),
  },
  taxableIncome: {
    term: B("Taxable income", "Thu nhập chịu thuế"),
    aliases: { en: ["taxable", "taxable pay"], vi: ["phần chịu thuế"] },
    def: B("The part of pay that tax is worked out on: gross, less insurance, less the family deductions. Because insurance comes off first, a bigger insurance deduction quietly lowers the tax as well.",
           "Phần thu nhập dùng để tính thuế: tổng thu nhập, trừ bảo hiểm, trừ giảm trừ gia cảnh. Vì bảo hiểm được trừ trước, một khoản bảo hiểm lớn hơn cũng âm thầm làm thuế giảm theo."),
  },
  familyDeduction: {
    term: B("Family deduction", "Giảm trừ gia cảnh"),
    aliases: { en: ["family deductions", "dependant", "dependants", "personal relief", "relief"], vi: ["người phụ thuộc", "giảm trừ"] },
    def: B("An amount subtracted before tax is worked out: ₫11m for yourself and ₫4.4m for each dependant. Registering a dependant late is one of the most common reasons a payslip's tax looks too high.",
           "Khoản được trừ ra trước khi tính thuế: 11 triệu cho bản thân và 4,4 triệu cho mỗi người phụ thuộc. Đăng ký người phụ thuộc muộn là một trong những lý do phổ biến nhất khiến thuế trên phiếu lương trông quá cao."),
  },
  ceiling: {
    term: B("Insurance ceiling", "Trần đóng bảo hiểm"),
    aliases: { en: ["ceiling", "ceilings", "trần đóng"], vi: ["trần đóng", "mức trần"] },
    def: B("The highest base a contribution is charged on. Above it the deduction stops growing, so two people on very different salaries can pay exactly the same BHXH.",
           "Mức cao nhất mà một khoản đóng được tính trên đó. Vượt qua mức này thì khoản khấu trừ không tăng nữa, nên hai người lương rất khác nhau vẫn có thể đóng BHXH bằng nhau."),
  },
  decree: {
    term: B("Decree", "Nghị định"),
    aliases: { en: ["decrees", "circular"], vi: ["thông tư", "văn bản pháp luật"] },
    def: B("The government document that changes a statutory rate or amount, from a stated date. Payobook records what the decree says; the decree itself is the evidence, and the date on it is not negotiable.",
           "Văn bản của cơ quan nhà nước thay đổi một tỷ lệ hoặc một mức luật định, kể từ một ngày nêu rõ. Payobook ghi lại nội dung nghị định; bản thân nghị định mới là bằng chứng, và ngày trong đó thì không thương lượng được."),
  },
  policy: {
    term: B("Insurance policy", "Chính sách bảo hiểm"),
    aliases: { en: ["insurance policies", "the policy", "policies", "declared rates"], vi: ["chính sách BH", "bản khai báo bảo hiểm"] },
    def: B("One record holding the BHXH, BHYT and BHTN rates and ceilings, with the date they take effect. It is what the company DECLARES it contributes — a rate change is a NEW record, because there is no version history to fall back on.",
           "Một bản ghi chứa tỷ lệ và trần đóng BHXH, BHYT, BHTN, kèm ngày bắt đầu hiệu lực. Đây là mức mà doanh nghiệp KHAI BÁO là mình đóng — đổi tỷ lệ nghĩa là tạo bản ghi MỚI, vì không có lịch sử phiên bản nào để quay lại."),
  },
  effectiveDate: {
    term: B("Effective date", "Ngày hiệu lực"),
    aliases: { en: ["effective dates", "effective from"], vi: ["ngày bắt đầu hiệu lực"] },
    def: B("The date a policy starts applying. Payobook shows the active policy with the latest effective date, so this field decides which rates you see — not the order the records were created in.",
           "Ngày một chính sách bắt đầu được áp dụng. Payobook hiển thị chính sách đang bật có ngày hiệu lực mới nhất, nên chính trường này quyết định bạn thấy tỷ lệ nào — chứ không phải thứ tự tạo bản ghi."),
  },
  reconcile: {
    term: B("Reconcile", "Đối chiếu"),
    aliases: { en: ["reconciles", "reconciled", "reconciliation"], vi: ["đối chiếu số liệu", "khớp số"] },
    def: B("Checking that two records of the same thing agree. On the Statutory screen that is the real job: the rate the company declares and the rate the payslips charge live in two different places. They have to match.",
           "Kiểm tra xem hai bản ghi về cùng một thứ có khớp nhau không. Ở màn hình Bảo hiểm & Thuế, đó mới là việc chính: tỷ lệ doanh nghiệp khai báo và tỷ lệ phiếu lương tính nằm ở hai nơi khác nhau. Hai bên phải khớp."),
  },

  /* -- reading the months back ------------------------------------------- */
  kpi: {
    term: B("KPI tile", "Ô chỉ số"),
    aliases: { en: ["kpi", "kpis", "kpi tiles", "tile", "tiles"], vi: ["ô số liệu", "thẻ chỉ số"] },
    def: B("One number on a card, answering one question about the company. A tile reports and does not explain, so read the method behind it before you quote it in an email.",
           "Một con số trên một thẻ, trả lời một câu hỏi về công ty. Ô chỉ số chỉ báo cáo chứ không giải thích, nên hãy hiểu cách nó được tính trước khi trích vào email."),
  },
  rollUp: {
    term: B("Roll-up", "Số tổng đã lưu"),
    aliases: { en: ["roll-ups", "rollup", "stored total", "stored totals"], vi: ["số tổng hợp đã lưu", "tổng đã lưu"] },
    def: B("A total Payobook saved on the run when it was computed, instead of adding the payslips again. Boards read roll-ups, which is why they are fast — and why a figure there can be older than the payslips beneath it.",
           "Con số tổng mà Payobook đã lưu sẵn trên đợt lương lúc tính, thay vì cộng lại từng phiếu lương. Các bảng phân tích đọc số tổng đã lưu, nhờ vậy chúng rất nhanh — và cũng vì vậy một con số ở đó có thể cũ hơn các phiếu lương bên dưới."),
  },
  snapshot: {
    term: B("Snapshot", "Ảnh chụp số liệu"),
    aliases: { en: ["snapshots", "analytics snapshot"], vi: ["ảnh chụp", "bản chụp số liệu"] },
    def: B("A copy of the numbers as they stood on one date. It does not change afterwards, which is what makes it useful and also what makes it go stale.",
           "Bản sao các con số tại đúng một thời điểm. Nó không đổi về sau — điều đó vừa làm nó hữu ích, vừa làm nó cũ đi."),
  },
  variance: {
    term: B("Variance", "Chênh lệch"),
    aliases: { en: ["variances"], vi: ["biến động", "chênh lệch giữa hai kỳ"] },
    def: B("The difference between one period and another. The number itself is easy; the useful question is which part of the payroll moved, and that is what the waterfall answers.",
           "Khoản khác biệt giữa kỳ này và kỳ khác. Con số thì dễ; câu hỏi có ích là phần nào của bảng lương đã biến động, và biểu đồ phân rã trả lời đúng câu đó."),
  },
  waterfall: {
    term: B("Waterfall", "Biểu đồ phân rã"),
    aliases: { en: ["variance waterfall", "waterfalls"], vi: ["phân rã chênh lệch", "biểu đồ phân rã chênh lệch"] },
    def: B("A chart that breaks a change into the pieces that caused it, and adds back up exactly. Use it when the total moved and nobody can say why.",
           "Biểu đồ tách một biến động thành các phần đã gây ra nó, và cộng lại khớp chính xác. Hãy dùng nó khi con số tổng thay đổi mà không ai nói được vì sao."),
  },
  drill: {
    term: B("Drill", "Đi sâu"),
    aliases: { en: ["drills", "drill down", "drilling"], vi: ["xem chi tiết", "đi sâu vào số liệu"] },
    def: B("Opening a figure to see the individual rows behind it. It is how a number stops being an opinion — you end up looking at the employees who make it up.",
           "Mở một con số ra để xem từng dòng phía sau nó. Đây là cách một con số thôi là ý kiến — cuối cùng bạn nhìn thẳng vào những nhân viên tạo nên nó."),
  },
  costPerHead: {
    term: B("Cost per head", "Chi phí bình quân đầu người"),
    aliases: { en: ["cost per employee"], vi: ["chi phí bình quân", "bình quân đầu người"] },
    def: B("The month's payroll divided by the people paid. Comparing two totals hides hiring; comparing cost per head does not, so it is the honest comparison between months.",
           "Chi phí lương của tháng chia cho số người được trả. So hai con số tổng thì che mất chuyện tuyển thêm người; so chi phí bình quân đầu người thì không, nên đây mới là phép so trung thực giữa các tháng."),
  },
  /* -- the wider app (LEARN REFRESH step 4) ------------------------------ */
  payBand: {
    term: B("Pay band", "Khoảng lương"),
    aliases: { en: ["pay bands", "salary band", "salary range"], vi: ["các khoảng lương", "dải lương"] },
    def: B("The lowest to highest pay the company means to pay for one kind of job, with its middle marked. Placing people in it shows who is below or above.",
           "Mức lương thấp nhất tới cao nhất mà công ty định trả cho một loại công việc, có đánh dấu điểm giữa. Đặt mọi người vào đó cho thấy ai thấp hơn hay cao hơn."),
  },
  inTheBand: {
    term: B("In the band", "Trong khoảng lương"),
    aliases: { en: ["compa position", "compa ratio"], vi: ["vị trí trong khoảng lương"] },
    def: B("Where someone's pay sits in their band, as a share of its middle: 100% is the middle, under 100% is below it.",
           "Vị trí lương của một người trong khoảng lương của họ, tính theo điểm giữa: 100% là điểm giữa, dưới 100% là thấp hơn."),
  },
  payReview: {
    term: B("Pay review", "Xét lương"),
    aliases: { en: ["pay reviews", "annual pay review"], vi: ["đợt xét lương"] },
    def: B("Deciding next year's pay for many people at once, inside a budget, then signing it off step by step. Apply writes the new pay onto their records.",
           "Quyết định lương năm sau cho nhiều người cùng lúc, trong một ngân sách, rồi duyệt từng bước. Áp dụng ghi lương mới vào hồ sơ của họ."),
  },
  calibration: {
    term: B("Calibration", "Cân chỉnh"),
    aliases: { en: ["calibrate"], vi: ["phần cân chỉnh"] },
    def: B("Comparing rises across people before they are signed off, so similar work and similar scores get similar rises. Anything that stands out is marked for a second look.",
           "So sánh mức tăng giữa mọi người trước khi duyệt, để công việc và điểm đánh giá giống nhau nhận mức tăng giống nhau. Điều gì nổi bật được đánh dấu để xem lại."),
  },
  decisionRoom: {
    term: B("Decision Room", "Phòng quyết định"),
    aliases: { en: ["the decision room"], vi: ["phòng quyết định"] },
    def: B("People › Plan: where you try next year — more people, a rise, less overtime — and see its cost before you commit. Nothing there changes payroll.",
           "Con người › Kế hoạch: nơi bạn thử trước năm sau — thêm người, tăng lương, bớt tăng ca — và thấy chi phí trước khi cam kết. Không có gì ở đó thay đổi bảng lương."),
  },
  exactCost: {
    term: B("Exact cost", "Chi phí chính xác"),
    aliases: { en: ["exact costs"], vi: ["chi phí chính xác của"] },
    def: B("A saved plan run through the real pay scheme, instead of the room's estimate. It shows how far the estimate was off.",
           "Một kế hoạch đã lưu được chạy qua chương trình lương thật, thay cho con số ước tính của căn phòng. Nó cho biết ước tính lệch bao nhiêu."),
  },
  hiringRequest: {
    term: B("Hiring request", "Đề xuất tuyển dụng"),
    aliases: { en: ["hiring requests", "raise a hiring request"], vi: ["đề xuất tuyển"] },
    def: B("Asking for a new person before looking for one: the role, the pay and the budget. A manager and HR sign it off; Finance only when it is over budget.",
           "Xin tuyển một người trước khi đi tìm: vị trí, mức lương và ngân sách. Quản lý và nhân sự duyệt; Tài chính chỉ duyệt khi vượt ngân sách."),
  },
  candidateStage: {
    term: B("Candidate stage", "Giai đoạn ứng viên"),
    aliases: { en: ["candidate stages", "move stage"], vi: ["các giai đoạn ứng viên"] },
    def: B("Where one candidate is on the road from Screening to Joined, or the reason they left it. Move stage is how they go on.",
           "Vị trí của một ứng viên trên chặng đường từ Sàng lọc tới Đã nhận việc, hoặc lý do họ rời chặng đó. Chuyển giai đoạn là cách đưa họ đi tiếp."),
  },
  buddy: {
    term: B("Buddy", "Người đồng hành"),
    aliases: { en: ["buddies"], vi: ["người đồng hành của"] },
    def: B("A colleague a new joiner can ask anything in their first weeks. The New joiners board counts anyone still without one.",
           "Một đồng nghiệp mà người mới có thể hỏi mọi điều trong những tuần đầu. Bảng Nhân viên mới đếm những ai chưa có."),
  },
  probation: {
    term: B("Probation", "Thử việc"),
    aliases: { en: ["trial period", "the trial"], vi: ["thời gian thử việc", "đợt thử việc"] },
    def: B("The trial at the start of a job. It ends with one decision: confirm them, extend the trial, or do not confirm.",
           "Giai đoạn làm thử khi mới vào làm. Nó kết thúc bằng một quyết định: xác nhận chính thức, kéo dài thử việc, hoặc không xác nhận."),
  },
  clearance: {
    term: B("Clearance", "Xác nhận bàn giao"),
    aliases: { en: ["clearances", "signed off by"], vi: ["xác nhận bàn giao của"] },
    def: B("IT, HR, Finance and Admin each saying a leaver has handed back what they held. The final settlement waits for all four.",
           "IT, Nhân sự, Tài chính và Quản trị viên lần lượt xác nhận người nghỉ đã trả lại những gì họ giữ. Quyết toán cuối cùng chờ đủ cả bốn."),
  },
  growthPlan: {
    term: B("Growth plan", "Kế hoạch phát triển"),
    aliases: { en: ["growth plans"], vi: ["các kế hoạch phát triển"] },
    def: B("A written plan to help someone who is struggling: objectives, dates and coaching, ending in a decision.",
           "Một kế hoạch bằng văn bản để giúp người đang gặp khó khăn: mục tiêu, mốc thời gian và kèm cặp, kết thúc bằng một quyết định."),
  },
  needsYou: {
    term: B("Needs you", "Cần bạn"),
    aliases: { en: ["needs you panel"], vi: ["khung cần bạn"] },
    def: B("The panel beside every Workforce tab: what is waiting for you now, with one press for overtime that is clean.",
           "Khung nằm cạnh mọi tab của Lực lượng lao động: những gì đang chờ bạn, với một lần bấm cho phần tăng ca sạch."),
  },
  lockWeek: {
    term: B("Lock the week", "Khoá tuần"),
    aliases: { en: ["lock week", "locked week", "week locked"], vi: ["khóa tuần", "tuần bị khóa"] },
    def: B("Closing a week's time so payroll can use it. The button waits until every flag is fixed or approved as it is.",
           "Chốt giờ công của một tuần để bảng lương sử dụng. Nút này chờ cho tới khi mọi cờ cảnh báo đã được điều chỉnh hoặc duyệt nguyên trạng."),
  },
  accessRole: {
    term: B("Access role", "Vai trò truy cập"),
    aliases: { en: ["access roles", "new role"], vi: ["vai trò truy cập của"] },
    def: B("A named set of things someone may open and do, written as one sentence. On Settings › Access & delegation you give a role, not a list of switches.",
           "Một nhóm việc có tên mà một người được mở và làm, viết thành một câu. Ở Cài đặt › Quyền truy cập & uỷ quyền, bạn cấp một vai trò, không phải một danh sách công tắc."),
  },
  handOver: {
    term: B("Hand-over", "Bàn giao quyền"),
    aliases: { en: ["hand-overs", "hand my access over"], vi: ["bàn giao quyền của tôi"] },
    def: B("Lending your access to someone for a while — who, what and until when. It is taken back automatically the morning after the end date.",
           "Cho người khác mượn quyền của bạn trong một thời gian — cho ai, quyền nào và đến khi nào. Quyền được tự động thu hồi vào sáng hôm sau ngày kết thúc."),
  },
  seeItAs: {
    term: B("See it as", "Xem dưới góc nhìn"),
    aliases: { en: ["looking at this as"], vi: ["xem dưới góc nhìn của"] },
    def: B("Seeing the app as another person sees it, to check their access. You still have exactly your own access while you look.",
           "Xem ứng dụng như một người khác nhìn thấy, để kiểm tra quyền của họ. Trong lúc xem, bạn vẫn giữ đúng quyền của mình."),
  },
  /* LEARN REFRESH step 5 — after the run */
  paymentRelease: {
    term: B("Payment release", "Lệnh chuyển tiền"),
    aliases: { en: ["release the money", "money release"], vi: ["chuyển tiền đi"] },
    def: B("The go-ahead to send the money, on Pay Run › Deliver. It waits for the bank file to be approved, and then goes through its own approval.",
           "Sự cho phép gửi tiền đi, ở Đợt lương › Chi trả. Nó chờ tệp ngân hàng được duyệt, rồi đi qua phê duyệt riêng của nó."),
  },
  payCalendar: {
    term: B("Pay calendar", "Lịch lương"),
    aliases: { en: ["changes close", "cut-off date", "cutoff date"], vi: ["ngày chốt thay đổi", "ngày chốt lương"] },
    def: B("The month's two dates on Pay Run › Calendar: the day changes close and the day people are paid. Reopening a closed month needs a reason.",
           "Hai mốc ngày của tháng ở Đợt lương › Lịch lương: ngày chốt thay đổi và ngày trả lương. Mở lại một tháng đã chốt cần nêu lý do."),
  },
  award: {
    term: B("Award", "Khoản thưởng"),
    aliases: { en: ["awards", "spot award"], vi: ["thưởng đột xuất", "tiền thưởng"] },
    def: B("A one-off bonus, incentive or spot award on Pay Run › Awards. It is approved first, then put into a draft pay run, which adds it to the payslip and recomputes it.",
           "Một khoản thưởng, khuyến khích hoặc thưởng đột xuất ở Đợt lương › Thưởng. Nó được duyệt trước, rồi được đưa vào một đợt lương nháp, cộng vào phiếu lương và tính lại."),
  },
  filing: {
    term: B("Filing", "Báo cáo bắt buộc"),
    aliases: { en: ["filings", "statutory filing", "statutory filings"], vi: ["hồ sơ nộp", "báo cáo nộp cơ quan"] },
    def: B("A report the company must send to a government office. The deadline is set by law rather than by your company. Payobook generates the file; you send it.",
           "Báo cáo mà doanh nghiệp phải nộp cho cơ quan nhà nước. Thời hạn do pháp luật ấn định chứ không do công ty bạn. Payobook tạo tệp; bạn là người nộp."),
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
/* =============================================================================
   THE READING ORDER OF THE MAP'S LINES  (LEARNOS Phase 6)
   -----------------------------------------------------------------------------
   It moved here from `journey/journey.js`, and the move is the point: the
   SERVER now needs this order too. `learn.runtime.next_best()` answers "what
   should I learn next", and the answer is "the next required station in
   reading order" — which the frontend knew and the server did not. Two copies
   of a reading order is exactly the shape the ledger keeps recording (a gate
   that rebuilds the table it gates drifts from it), so there is one, here,
   and the generator emits it into the content plane for both readers.

   NOT the storage order. The generator numbers stations with one counter
   running across every line in declaration order, so a new section is
   APPENDED there to avoid renumbering everything before it — right for
   storage, wrong for a page. A learner meets Overview first and Setup last.

   A line MISSING from this list is still drawn, after the ones that are in
   it (journey.js), and is still reachable by next_best (learn_runtime.py).
   That is deliberate: a section must never be able to vanish from the map
   because somebody forgot a second file.
   ========================================================================== */
/* LEARN REFRESH step 5 — station keys that were RETIRED by folding them into
   another station. The progress rows were migrated (pb_learn migration
   19.0.19.0.0); anything that still names an old key — a deep link, a
   bookmarked ⌘K row, an old chat's "Show me" — lands on the new station. */
const STATION_ALIASES = { contracts: "employees", proration: "adjust", retro: "adjust" };

const LINE_ORDER = ["overview", "payrun", "setup", "people", "lifecycle", "workforce", "insights", "compliance"];

const STATIONS = {
  payrun: {
    stations: [
      {
        id: "runpayroll", icon: "zap", star: true, required: true, mins: 8, after: null,
        title: B("Run", "Chạy lương"),
        desc: B("Start one month's pay run: pick the pay scheme, add the month's pay data, compute, and read what needs a look.",
                "Bắt đầu đợt lương của một tháng: chọn chương trình lương, thêm dữ liệu lương của tháng, tính, và đọc những gì cần xem lại."),
        outline: {
          what: B("Pay Run › Run. It asks which pay scheme the run is for, then which month. If that scheme reads a spreadsheet, it asks for this month's file. Then it computes a draft payslip for everyone the scheme pays, and lists what needs a look.",
                  "Đợt lương › Chạy lương. Nó hỏi đợt lương này dành cho chương trình lương nào, rồi tháng nào. Nếu chương trình đó đọc một bảng tính, nó xin tệp của tháng này. Rồi nó tính phiếu lương nháp cho mọi người mà chương trình đó trả lương, và liệt kê những gì cần xem lại."),
          why: B("Everything after this reads what this step produced: the review, the approval, the bank file. So a mistake here is a mistake in all of it.",
                 "Mọi việc phía sau đều đọc kết quả của bước này: soát xét, phê duyệt, tệp chi lương. Nên sai ở đây là sai ở tất cả."),
          when: B("Once the month's attendance and overtime are in. Not before.",
                  "Khi chấm công và tăng ca của tháng đã về. Không sớm hơn."),
          prereq: B("Access to Pay Run, a pay scheme for the people you are paying, and — if the scheme reads one — this month's pay data file.",
                    "Quyền vào Đợt lương, một chương trình lương cho những người bạn trả lương, và — nếu chương trình đó cần — tệp dữ liệu lương của tháng này."),
          mistakes: [
            B("Picking the wrong pay scheme. End of month settles the whole month; Mid-month advance pays part of it early. They are not two views of one thing.",
              "Chọn nhầm chương trình lương. Cuối tháng là quyết toán cả tháng; Tạm ứng giữa tháng là trả trước một phần. Đó không phải hai cách nhìn của cùng một thứ."),
            B("Choosing Update Payobook for a one-off amount. That saves the value onto the person's records for every month after. A one-off bonus belongs in This run only.",
              "Chọn Cập nhật Payobook cho một khoản chỉ có một lần. Làm vậy là lưu giá trị đó vào hồ sơ của người đó cho mọi tháng sau. Một khoản thưởng một lần thuộc về Chỉ đợt này."),
            B("Reading \"Need review\" as \"nothing else to check\". It counts people Payobook could not pay and payslips at zero. It does not flag a big jump on last month — that one is yours to spot.",
              "Hiểu \"Cần xem xét\" thành \"không còn gì để kiểm tra\". Nó đếm những người Payobook không trả lương được và các phiếu bằng không. Nó không đánh dấu một mức tăng lớn so với tháng trước — việc đó là của bạn."),
          ],
        },
      },
      {
        id: "payruns", icon: "calendar", star: true, required: true, mins: 7, after: "runpayroll",
        title: B("Runs", "Các đợt lương"),
        desc: B("Every pay run on one board: Draft, Waiting for approval, Done — and who each one is waiting for.",
                "Mọi đợt lương trên một bảng: Nháp, Chờ phê duyệt, Hoàn tất — và mỗi đợt đang chờ ai."),
        outline: {
          what: B("Pay Run › Runs. A board with three columns — Draft, Waiting for approval and Done — and a folded list of rejected runs. A card shows who the run is with, and offers only what its state allows.",
                  "Đợt lương › Các đợt lương. Một bảng ba cột — Nháp, Chờ phê duyệt và Hoàn tất — cùng một danh sách thu gọn các đợt bị từ chối. Mỗi thẻ cho biết đợt đang ở chỗ ai, và chỉ mở ra những thao tác trạng thái của nó cho phép."),
          why: B("Nothing is paid until the people on its approval route have said yes. This board shows where every run is on that road, and who is holding it.",
                 "Không khoản nào được chi cho tới khi những người trên lộ trình phê duyệt đã đồng ý. Bảng này cho thấy mỗi đợt đang ở đâu trên con đường đó, và ai đang giữ nó."),
          when: B("Every day of payroll week. And any time you need to know how far a month has got.",
                  "Mỗi ngày trong tuần tính lương. Và bất cứ khi nào bạn cần biết một tháng đã đi tới đâu."),
          prereq: B("A run that has been computed. To decide on one you need to be a person on its approval route.",
                    "Một đợt đã tính xong. Muốn quyết định về một đợt thì bạn phải là người có tên trên lộ trình phê duyệt của nó."),
          mistakes: [
            B("Pressing Reject when you meant \"please fix this\". Reject cancels the run and every payslip in it. To have it fixed, the person whose turn it is sends it back from the approval inbox.",
              "Bấm Từ chối khi ý bạn là \"hãy sửa giúp\". Từ chối là huỷ đợt lương và mọi phiếu lương trong đó. Muốn được sửa, người đến lượt duyệt sẽ trả lại nó từ hộp phê duyệt."),
            B("Reading a column as a month. The columns are states. July and June can sit in the same one.",
              "Đọc một cột như thể đó là tháng. Các cột là trạng thái. Tháng 7 và tháng 6 có thể cùng nằm trong một cột."),
            B("Missing the note on a run that came back. A sent-back run sits in Draft with the reason on its card. Fix what it says, then submit it again.",
              "Bỏ sót ghi chú trên một đợt bị trả lại. Đợt bị trả lại nằm ở cột Nháp, lý do ghi ngay trên thẻ. Sửa đúng điều đó rồi gửi lại."),
          ],
        },
      },
      {
        id: "payslips", icon: "receipt", required: true, mins: 6, after: "runpayroll",
        title: B("Payslips", "Phiếu lương"),
        desc: B("Read one person's payslip line by line, from gross down to net, with every rule visible.",
                "Đọc phiếu lương của một người theo từng dòng, từ tổng thu nhập xuống thực nhận, mọi quy tắc đều nhìn thấy được."),
        outline: {
          what: B("Pay Run › Payslips. Pick a run; you get its numbers, its payslips by state, and one payslip opened beside the list with its salary breakdown.",
                  "Đợt lương › Phiếu lương. Chọn một đợt; bạn có các con số của nó, các phiếu lương theo trạng thái, và một phiếu được mở bên cạnh danh sách kèm chi tiết lương."),
          why: B("A run total can be right while one payslip inside it is wrong. This is where you see the working behind a net figure, before the money moves.",
                 "Tổng của một đợt có thể đúng trong khi một phiếu lương bên trong vẫn sai. Đây là nơi bạn thấy phần tính toán phía sau con số thực nhận, trước khi tiền chạy đi."),
          when: B("After computing and before submitting for approval. And again whenever somebody asks why their pay is what it is.",
                  "Sau khi tính và trước khi gửi phê duyệt. Và bất cứ khi nào có người hỏi vì sao lương của họ lại như vậy."),
          prereq: B("A run that has been computed, and access to Pay Run.",
                    "Một đợt đã tính, và quyền vào Đợt lương."),
          mistakes: [
            B("Typing over a net amount instead of fixing the input. The payslip then disagrees with the data behind it, and the next recompute quietly undoes your fix.",
              "Gõ đè lên số thực nhận thay vì sửa dữ liệu đầu vào. Phiếu lương sẽ lệch với dữ liệu phía sau, và lần tính lại kế tiếp âm thầm xoá sửa đổi của bạn."),
            B("Expecting insurance to move when overtime does. BHXH, BHYT and BHTN are charged on the insurance base, and overtime does not change that figure.",
              "Trông đợi bảo hiểm thay đổi theo tăng ca. BHXH, BHYT và BHTN tính trên mức lương đóng bảo hiểm, mà tăng ca không làm thay đổi con số đó."),
            B("Taking \"Need review: 0\" as \"all checked\". On this screen it only counts payslips whose take-home pay came out at zero or below.",
              "Hiểu \"Cần xem xét: 0\" thành \"đã kiểm tra hết\". Trên màn hình này nó chỉ đếm những phiếu có thực nhận bằng không hoặc âm."),
          ],
        },
      },
      {
        id: "import", icon: "database", required: true, mins: 6, after: null,
        title: B("Import", "Nhập"),
        desc: B("Load this period's pay data from a file: match the rows to people, fix what is wrong, then commit.",
                "Tải dữ liệu lương của kỳ này từ một tệp: khớp các dòng với từng người, sửa chỗ sai, rồi ghi vào hệ thống."),
        outline: {
          what: B("Pay Run › Import. A guided flow in four steps — Source & file, Review & match, Validate, Commit — plus the history of every batch loaded before.",
                  "Đợt lương › Nhập. Một luồng có hướng dẫn gồm bốn bước — Nguồn & tệp, Soát & khớp, Kiểm tra, Ghi vào hệ thống — cùng lịch sử mọi đợt đã tải trước đó."),
          why: B("Most wrong payslips start as a wrong row in a file. Fixing that row here costs minutes. Fixing it after approval costs a retro line and a conversation.",
                 "Phần lớn phiếu lương sai bắt đầu từ một dòng sai trong tệp. Sửa dòng đó ở đây tốn vài phút. Sửa nó sau khi đã phê duyệt tốn một dòng hồi tố và một cuộc trao đổi."),
          when: B("As soon as the month's data arrives. And always before you compute the run.",
                  "Ngay khi dữ liệu của tháng về. Và luôn luôn trước khi bạn tính đợt lương."),
          prereq: B("Access to Pay Run, a file (or a connected system), and a formula configuration to map the columns onto.",
                    "Quyền vào Đợt lương, một tệp (hoặc một hệ thống đã kết nối), và một cấu hình công thức để ánh xạ các cột vào."),
          mistakes: [
            B("Committing with rows still unresolved because the deadline is close. A row that did not match is a person who will be missing from the run.",
              "Ghi vào hệ thống khi còn dòng chưa xử lý vì sắp tới hạn. Một dòng không khớp là một người sẽ bị thiếu trong đợt lương."),
            B("Importing one month's data into another month. Read the period on step one before you load anything.",
              "Nhập dữ liệu của tháng này vào tháng khác. Hãy đọc kỳ ở bước một trước khi tải bất cứ gì."),
            B("Fixing an import mistake on the payslips afterwards. That corrects the result and leaves the input wrong, so the next recompute brings the mistake back.",
              "Sửa lỗi nhập liệu trên phiếu lương về sau. Việc đó chỉ sửa kết quả và để nguyên đầu vào sai, nên lần tính lại kế tiếp mang lỗi quay lại."),
          ],
        },
      },
      {
        id: "fullfinal", icon: "file-text", mins: 6, after: "payruns",
        roles: ["officer", "hr"],
        search: B("final settlement, leaver, last pay, unused leave, full and final",
                  "quyết toán thôi việc, người nghỉ việc, lương cuối, phép chưa dùng"),
        title: B("Final settlements", "Quyết toán thôi việc"),
        desc: B("Everyone who is leaving, what they are still owed, and how far each settlement is on its way to approval.",
                "Mọi người sắp nghỉ việc, những khoản họ còn được nhận, và mỗi khoản quyết toán đã đi tới đâu trên đường phê duyệt."),
        outline: {
          what: B("Pay Run › Settle. One row per settlement with its net payable, and three steps: Being prepared, Waiting for approval, Approved. A row opens its breakdown.",
                  "Đợt lương › Quyết toán. Mỗi khoản quyết toán một dòng kèm số tiền phải trả, và ba bước: Being prepared, Waiting for approval, Approved. Một dòng mở ra phần chi tiết của nó."),
          why: B("It is the last money a person gets from you, and it has a legal deadline. Two approvals, the HR lead and then Finance, stand between the working and the payment.",
                 "Đây là khoản tiền cuối cùng một người nhận từ bạn, và nó có thời hạn pháp lý. Hai lần phê duyệt, trưởng nhân sự rồi Tài chính, đứng giữa phần tính toán và việc chi trả."),
          when: B("As soon as a leaving date is confirmed. And again once the four desks on Lifecycle › Exits have signed off.",
                  "Ngay khi ngày nghỉ việc được xác nhận. Và một lần nữa khi bốn bộ phận ở Vòng đời nhân sự › Nghỉ việc đã xác nhận xong."),
          prereq: B("A leaving date on the employee and the month's pay data. A settlement that arrives by itself starts at Being prepared.",
                    "Ngày nghỉ việc trên hồ sơ nhân viên và dữ liệu lương của tháng. Một khoản quyết toán tự xuất hiện sẽ bắt đầu ở Being prepared."),
          mistakes: [
            B("Leaving the person in the normal monthly run as well. They are then paid twice, and money paid to someone who has left is hard to get back.",
              "Vẫn để người đó trong đợt lương tháng bình thường. Họ sẽ được trả hai lần, và tiền đã trả cho người đã nghỉ thì rất khó đòi lại."),
            B("Looking for Download on a settlement that is not approved yet. The settlement document can be downloaded only once it is Approved.",
              "Tìm nút Download trên một khoản quyết toán chưa được duyệt. Chỉ khi đã Approved thì mới tải được văn bản quyết toán."),
            B("Settling before the last month's attendance is in. The settlement reads the same pay data as any other month.",
              "Quyết toán khi chấm công tháng cuối chưa về. Khoản quyết toán đọc cùng dữ liệu lương như mọi tháng khác."),
          ],
        },
      },
      {
        id: "afterrun", icon: "send", mins: 8, after: "payruns",
        roles: ["officer"],
        search: B("results grid, bank file, payment release, send payslips, pay calendar, changes close, bonus, award",
                  "bảng kết quả, tệp ngân hàng, lệnh chuyển tiền, gửi phiếu lương, lịch lương, chốt thay đổi, thưởng"),
        title: B("After the run: results, payments, calendar, awards", "Sau đợt lương: kết quả, chi trả, lịch lương, thưởng"),
        desc: B("Read the whole run as one grid, send the money and the payslips, know when changes close, and put one-off awards into a run.",
                "Đọc cả đợt lương trong một bảng, gửi tiền và phiếu lương, biết khi nào chốt thay đổi, và đưa các khoản thưởng một lần vào đợt lương."),
        outline: {
          what: B("Four Pay Run tabs. Results shows every person's figures in one grid. Deliver sends the bank file, the payment release and the payslips. Calendar says when changes close. Awards holds bonuses on their way into a run.",
                  "Bốn tab của Đợt lương. Kết quả hiện số liệu của mọi người trong một bảng. Chi trả gửi tệp ngân hàng, lệnh chuyển tiền và phiếu lương. Lịch lương cho biết khi nào chốt thay đổi. Thưởng giữ các khoản thưởng đang trên đường vào đợt lương."),
          why: B("Approval is not payment. The bank file and the payment release each go through their own approval, and payslips go out only when someone sends them.",
                 "Phê duyệt chưa phải là chi trả. Tệp ngân hàng và lệnh chuyển tiền mỗi thứ đi qua phê duyệt riêng, và phiếu lương chỉ được gửi khi có người gửi."),
          when: B("Results before and after approval. Deliver once a run is approved. Calendar at the start of each month. Awards whenever one is agreed.",
                  "Kết quả trước và sau khi phê duyệt. Chi trả khi một đợt đã được duyệt. Lịch lương vào đầu mỗi tháng. Thưởng bất cứ khi nào có một khoản được đồng ý."),
          prereq: B("An approved run for Deliver. Calendar and Awards show only to people with pay calendar or awards access.",
                    "Một đợt đã được duyệt để dùng Chi trả. Lịch lương và Thưởng chỉ hiện với người có quyền về lịch lương hoặc thưởng."),
          mistakes: [
            B("Reading Done as paid. A run can be Done while its bank file still waits for approval and no money has moved.",
              "Hiểu Hoàn tất là đã chi. Một đợt có thể đã Hoàn tất trong khi tệp ngân hàng vẫn chờ duyệt và chưa có đồng nào được chuyển."),
            B("Sending payslips before the money is released. People read a payslip as a promise that the money is on its way.",
              "Gửi phiếu lương trước khi tiền được chuyển. Mọi người đọc phiếu lương như một lời hứa rằng tiền đang tới."),
            B("Typing a bonus onto a payslip. Awards puts it into a draft run after approval, with a record; a typed amount has neither.",
              "Gõ một khoản thưởng thẳng vào phiếu lương. Thưởng đưa nó vào một đợt nháp sau khi được duyệt, có lưu vết; một con số gõ tay thì không có cả hai."),
          ],
        },
      },
      {
        id: "adjust", icon: "rotate-ccw", mins: 7, after: "payslips",
        roles: ["officer"],
        search: B("retro, back pay, backdated raise, proration, part month, mid-month change, joiner",
                  "hồi tố, truy lĩnh, tăng lương lùi ngày, phân bổ theo tỷ lệ, lương theo phần tháng, thay đổi giữa tháng, người mới vào"),
        title: B("Adjust: back pay and part months", "Điều chỉnh: truy lĩnh và lương theo phần tháng"),
        desc: B("Two ledgers that fill themselves when pay data is loaded: back pay for a change dated before this month, and every amount paid for part of a month.",
                "Hai sổ tự điền khi dữ liệu lương được tải: truy lĩnh cho một thay đổi có hiệu lực trước tháng này, và mọi khoản trả cho một phần tháng."),
        outline: {
          what: B("Pay Run › Adjust. Two tabs over one ledger. Retro lists back pay as old, new and delta per person. Proration lists every part-month amount as old, new and prorated.",
                  "Đợt lương › Điều chỉnh. Hai tab trên cùng một sổ. Hồi tố liệt kê khoản truy lĩnh theo cũ, mới và chênh lệch của từng người. Phân bổ theo tỷ lệ liệt kê mọi khoản trả cho một phần tháng theo cũ, mới và đã phân bổ."),
          why: B("Nobody types these lines. They are the working behind two questions people ask most: why did I get extra this month, and why is my first payslip smaller.",
                 "Không ai gõ các dòng này. Chúng là phần tính toán đứng sau hai câu hỏi hay gặp nhất: vì sao tháng này tôi được thêm tiền, và vì sao phiếu lương đầu tiên của tôi nhỏ hơn."),
          when: B("After a month's pay data is loaded with backdated changes, joiners or leavers in it. And whenever someone asks how one of those amounts was worked out.",
                  "Sau khi dữ liệu lương của một tháng có thay đổi lùi ngày, người mới vào hoặc người nghỉ việc được tải lên. Và bất cứ khi nào có người hỏi một khoản như vậy được tính ra sao."),
          prereq: B("A pay scheme with Part-month pay or Back-pay switched on in its Settings, under Pay rules, and a month of pay data loaded.",
                    "Một chương trình lương đã bật Lương theo phần tháng hoặc Truy lĩnh trong phần Cài đặt, mục Quy tắc lương, và dữ liệu lương của một tháng đã được tải."),
          mistakes: [
            B("Reopening a paid month to fix a backdated raise. The next pay data load works out the difference and pays it this month, with the old month named on the line.",
              "Mở lại một tháng đã trả để sửa một lần tăng lương lùi ngày. Lần tải dữ liệu lương kế tiếp tự tính phần chênh và trả trong tháng này, kèm tên tháng gốc trên dòng."),
            B("Looking for the days on the row. The row shows money only. The drawer's Period section holds the basis and the days on each side of the change.",
              "Tìm số ngày ngay trên dòng. Dòng chỉ hiện tiền. Phần Period trong ngăn chi tiết mới có cách tính và số ngày ở mỗi phía của thay đổi."),
            B("Expecting back pay with Back-pay switched off. The new amount then applies from this month on, and the earlier months' difference is never paid.",
              "Chờ khoản truy lĩnh trong khi Truy lĩnh đang tắt. Khi đó mức mới chỉ áp dụng từ tháng này, và phần chênh của các tháng trước không bao giờ được trả."),
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
        title: B("Formula Engine", "Bộ máy công thức"),
        desc: B("The rulebook, out in the open. Every payslip line is a named component with a formula you can read.",
                "Bộ quy tắc bày ra rõ ràng. Mỗi dòng phiếu lương là một thành phần có tên, với công thức bạn đọc được."),
        outline: {
          what: B("Settings › Formula Engine opens Formula Studio. It shows one pay scheme's formula configuration at a time: its components, the formula behind each, and a preview on one real employee. Six views sit above it: Cards, Grid, Test, Compare, Health and Settings.",
                  "Cài đặt › Bộ máy công thức mở Xưởng công thức: mỗi lần một cấu hình công thức của một chương trình lương — các thành phần, công thức đằng sau mỗi thành phần, chúng phụ thuộc vào gì, và bản xem trước trên một nhân viên thật. Phía trên có sáu cách xem: Thẻ, Lưới, Kiểm thử, So sánh, Sức khoẻ và Cài đặt."),
          why: B("This is the written answer to every \"why is my pay this number\" question. A payroll desk that can read the rulebook stops guessing and starts showing.",
                 "Đây là câu trả lời đã viết sẵn cho mọi thắc mắc \"vì sao lương tôi lại là con số này\". Một bộ phận lương đọc được bộ quy tắc sẽ thôi phỏng đoán và bắt đầu trưng ra bằng chứng."),
          when: B("When an allowance is added. When a rule changes. And any time you have to trace a number on a payslip back to where it came from.",
                  "Khi thêm một khoản phụ cấp. Khi một quy tắc thay đổi. Và bất cứ lúc nào bạn phải truy một con số trên phiếu lương về đúng nơi sinh ra nó."),
          prereq: B("Access to Settings › Formula Engine to read it, and a formula manager role to change it. A sample employee to preview against helps.",
                    "Quyền vào Cài đặt › Bộ máy công thức để xem, và vai trò quản lý công thức để sửa. Nên có một nhân viên mẫu để xem trước."),
          mistakes: [
            B("Activating a change without simulating it first. Simulate lives in Tools → Analyze; it runs the configuration on last period's real payslips. A wrong component costs every future payslip on that scheme.",
              "Kích hoạt một thay đổi mà không mô phỏng trước. Mô phỏng nằm trong Công cụ → Phân tích; nó chạy cấu hình trên phiếu lương thật của kỳ trước. Một thành phần sai làm hỏng mọi phiếu lương tương lai của chương trình đó."),
            B("Renaming a component other formulas depend on. The dependency panel names them, so read it before you rename. A formula that lost its input does not always fail loudly.",
              "Đổi tên một thành phần mà công thức khác đang phụ thuộc. Bảng phụ thuộc liệt kê chúng, nên hãy đọc trước khi đổi tên. Một công thức mất đầu vào không phải lúc nào cũng báo lỗi rõ ràng."),
            B("Typing a statutory rate straight into a formula. A rate belongs in a named parameter. A hand-typed 8% is one nobody will remember to change.",
              "Gõ thẳng một tỷ lệ luật định vào công thức. Tỷ lệ nên nằm trong một tham số có tên. Một con số 8% gõ tay là con số không ai nhớ để sửa."),
          ],
        },
      },
      {
        id: "structures", icon: "layers", mins: 6, after: "formula",
        roles: ["officer"],
        search: B("salary structure, salary rules, structure or pay scheme, old payslips",
                  "cấu trúc lương, quy tắc lương, cấu trúc hay chương trình lương, phiếu lương cũ"),
        title: B("Salary structures, and when you need one", "Cấu trúc lương, và khi nào bạn cần"),
        desc: B("The older way of computing a payslip, and the plain rule for when it still decides someone's pay.",
                "Cách tính phiếu lương thế hệ trước, và quy tắc rõ ràng cho biết khi nào nó vẫn quyết định lương của một người."),
        outline: {
          what: B("Settings › Salary Structures. Each structure is a set of salary rules, with the rules and employees it covers. Rows open the structure.",
                  "Cài đặt › Cấu trúc lương. Mỗi cấu trúc là một bộ quy tắc lương, kèm số quy tắc và số nhân viên nó bao gồm. Mỗi dòng mở ra cấu trúc đó."),
          why: B("A payslip is computed by the structure on the person's contract when it has one. Only a contract with no structure is paid by a pay scheme.",
                 "Phiếu lương được tính theo cấu trúc trên hợp đồng của người đó khi hợp đồng có cấu trúc. Chỉ hợp đồng không có cấu trúc mới được trả theo chương trình lương."),
          when: B("When you read an old payslip, when you move people onto a pay scheme, and when a payslip does not follow the scheme you expected.",
                  "Khi bạn đọc một phiếu lương cũ, khi chuyển mọi người sang một chương trình lương, và khi một phiếu lương không theo chương trình bạn nghĩ."),
          prereq: B("Payroll or HR access to Settings. A company on pay schemes needs no structures at all.",
                    "Quyền về lương hoặc nhân sự trong Cài đặt. Công ty dùng chương trình lương thì không cần cấu trúc nào."),
          mistakes: [
            B("Leaving a structure on the contracts of people you moved to a pay scheme. Their payslips keep following the structure's rules.",
              "Để nguyên cấu trúc trên hợp đồng của những người đã chuyển sang chương trình lương. Phiếu lương của họ vẫn đi theo quy tắc của cấu trúc."),
            B("Adding new pay logic to a structure. A pay scheme cannot see it, and nobody on a scheme gets it.",
              "Thêm logic lương mới vào một cấu trúc. Chương trình lương không thấy nó, và không ai trong chương trình nhận được nó."),
            B("Deleting a structure nobody uses today. Old payslips still point at it.",
              "Xoá một cấu trúc hôm nay không ai dùng. Phiếu lương cũ vẫn trỏ tới nó."),
          ],
        },
      },
      {
        id: "statutory", icon: "shield-check", star: true, required: true, mins: 8, after: null,
        title: B("Statutory (Insurance & Tax)", "Bảo hiểm & Thuế"),
        desc: B("BHXH, BHYT and BHTN rates, the ceilings, and the thuế TNCN table. These are the rules the law writes for you.",
                "Tỷ lệ BHXH, BHYT, BHTN, các mức trần, và biểu thuế TNCN. Đây là những quy tắc do pháp luật viết sẵn cho bạn."),
        outline: {
          what: B("The company's active insurance policy and tax table. Who pays what, on which base, up to which ceiling, and from which date.",
                  "Chính sách bảo hiểm và biểu thuế đang hiệu lực của công ty. Ai đóng bao nhiêu, trên mức nào, tới trần nào, và từ ngày nào."),
          why: B("This is what the company DECLARES it pays. It is read by this screen, by the contribution analytics and by the statutory reports. It is NOT what prices a payslip — that number is a parameter in each division's formula configuration. So the real job here is keeping the two in agreement. When they disagree, payroll is charging a rate the company never declared.",
                 "Đây là mức mà doanh nghiệp KHAI BÁO là mình đóng. Màn hình này, phần phân tích chi phí bảo hiểm và các báo cáo bắt buộc đều đọc nó. Nó KHÔNG phải thứ tính ra tiền trên phiếu lương — con số đó là một tham số trong cấu hình công thức của từng bộ phận. Nên việc thật sự ở đây là giữ hai bên khớp nhau. Khi chúng lệch nhau, hệ thống lương đang tính theo một tỷ lệ doanh nghiệp chưa hề khai báo."),
          when: B("When a decree changes a rate or a deduction. At the start of a tax year. And whenever somebody asks why a contribution is the amount it is.",
                  "Khi một nghị định thay đổi một tỷ lệ hoặc một mức giảm trừ. Vào đầu một năm tính thuế. Và bất cứ khi nào có người hỏi vì sao khoản đóng lại là con số đó."),
          prereq: B("Access to Settings › Statutory, and the decree open in front of you. This screen records a decision that was made somewhere else.",
                    "Quyền vào Cài đặt › Bảo hiểm & Thuế, và nghị định đang mở trước mặt bạn. Màn hình này ghi lại một quyết định đã được ra ở nơi khác."),
          mistakes: [
            B("Editing the rate on the policy that is in force today. There is no version history to fall back on. The old declared rate is simply gone, and so is the evidence of what you were declaring last month.",
              "Sửa tỷ lệ ngay trên chính sách đang có hiệu lực hôm nay. Không có lịch sử phiên bản nào để quay lại. Tỷ lệ đã khai báo trước đó đơn giản là biến mất, và bằng chứng về mức bạn khai tháng trước cũng mất theo."),
            B("Dating the new policy from today instead of from the day the decree applies. The effective date is your record of when the change legally started. A date with no decree behind it is the first thing an inspection asks about.",
              "Đặt ngày hiệu lực của chính sách mới là hôm nay thay vì ngày nghị định bắt đầu áp dụng. Ngày hiệu lực là ghi nhận của bạn về thời điểm thay đổi có hiệu lực pháp lý. Một cái ngày không có nghị định đứng sau là thứ đầu tiên đoàn kiểm tra hỏi tới."),
            B("Declaring the new rate and stopping there. The number that prices a payslip is a parameter on the division's formula configuration. Until you change that too, the run charges the old rate correctly — against a declaration that now says something else.",
              "Khai báo tỷ lệ mới rồi dừng ở đó. Con số tính ra tiền trên phiếu lương là một tham số trong cấu hình công thức của bộ phận. Chừng nào bạn chưa sửa cả tham số đó, đợt lương vẫn tính đúng theo tỷ lệ cũ — nhưng lệch với bản khai báo vừa thay đổi."),
          ],
        },
      },
      {
        id: "integrations", icon: "database", mins: 7, after: null,
        roles: ["officer", "owner"],
        search: B("connectors, connected system, sync, automatic fetch, schedule, arrivals",
                  "bộ kết nối, hệ thống được kết nối, đồng bộ, tự động lấy dữ liệu, lịch, hồ sơ đến"),
        title: B("Integrations: connections, fetch schedule, arrivals", "Tích hợp: kết nối, lịch lấy dữ liệu, hồ sơ đến"),
        desc: B("The systems pay data arrives from, how often each one is fetched, and what arrived from them.",
                "Các hệ thống mà dữ liệu lương đến từ đó, mỗi hệ thống được lấy dữ liệu bao lâu một lần, và những gì đã đến từ chúng."),
        outline: {
          what: B("Settings › Integrations. One row per connection with its last sync, feeds and mappings. A row opens the connection: its actions and its Automatic fetch schedule.",
                  "Cài đặt › Tích hợp. Mỗi kết nối một dòng kèm lần đồng bộ gần nhất, nguồn cấp và ánh xạ. Một dòng mở ra kết nối đó: các thao tác và lịch Automatic fetch."),
          why: B("Data that arrives by itself is data nobody retyped. But a connection that stopped looks just like one that works, until its feeds go stale.",
                 "Dữ liệu tự về là dữ liệu không ai phải gõ lại. Nhưng một kết nối đã ngừng trông y hệt một kết nối đang chạy, cho tới khi nguồn cấp của nó bị cũ."),
          when: B("When you set a system up. At the start of each payroll week. And when a number looks wrong and came from a connected system.",
                  "Khi thiết lập một hệ thống. Vào đầu mỗi tuần tính lương. Và khi một con số trông sai mà nó đến từ hệ thống được kết nối."),
          prereq: B("A formula role to open Settings › Integrations, and the login for the source system.",
                    "Một vai trò công thức để mở Cài đặt › Tích hợp, và thông tin đăng nhập của hệ thống nguồn."),
          mistakes: [
            B("Reading Connected as up to date. Connected is the login; the last sync and the stale feeds are the data.",
              "Hiểu Đã kết nối là đã cập nhật. Đã kết nối nói về đăng nhập; lần đồng bộ gần nhất và các nguồn cấp cũ mới nói về dữ liệu."),
            B("Leaving Automatic fetch off and forgetting it. Then each pay run fetches while you wait, or not at all.",
              "Để Automatic fetch tắt rồi quên. Khi đó mỗi đợt lương phải lấy dữ liệu trong lúc bạn chờ, hoặc không lấy gì."),
            B("Switching on record updates without reading the warning. The connected system then owns every mapped field on those records.",
              "Bật cập nhật hồ sơ mà không đọc cảnh báo. Khi đó hệ thống được kết nối nắm mọi trường đã ánh xạ trên các hồ sơ đó."),
          ],
        },
      },

      /* -----------------------------------------------------------------------
         LEARN REFRESH step 3 — PAYROLL SETUP. Six stations for the screens
         that shipped after the content was written: the guided setup, Mapping,
         Component treatment, the Approval Matrix, the Records Desk, and pay
         schemes in more than one currency. `roles` is who each is for (step 5
         builds the paths from it); `search` is the plain words the ⌘K search
         matches, in both languages.
         -------------------------------------------------------------------- */
      {
        id: "blueprint", icon: "sparkles", star: true, mins: 8, after: "formula",
        roles: ["owner", "officer"],
        search: B("new pay scheme, set up payroll, guided setup", "chương trình lương mới, thiết lập lương, thiết lập có hướng dẫn"),
        title: B("New configuration", "Cấu hình mới"),
        desc: B("Set up a new pay scheme step by step, and watch one person's pay change as you build it.",
                "Thiết lập một chương trình lương mới theo từng bước, và xem lương của một người thay đổi ngay khi bạn dựng nó."),
        outline: {
          what: B("Settings › Guided setup › New configuration. Six steps — Start, Pay rules, Connect, Outputs, Test, Finish — with a panel that shows a sample person's pay the whole way through.",
                  "Cài đặt › Thiết lập có hướng dẫn › Cấu hình mới. Sáu bước — Bắt đầu, Quy tắc lương, Kết nối, Đầu ra, Kiểm thử, Hoàn thành — kèm một khung luôn hiện lương của một người mẫu."),
          why: B("A pay scheme is the rulebook every payslip in it is computed by. Building it in one guided place means nothing is forgotten, and every choice can be explained later.",
                 "Chương trình lương là bộ quy tắc tính mọi phiếu lương trong đó. Dựng nó ở một nơi có hướng dẫn thì không bỏ sót gì, và mọi lựa chọn đều giải thích được về sau."),
          when: B("When you pay a new group of people by different rules, open a new country, or rebuild an old scheme. A scheme's own Settings reopens the same journey to edit it.",
                  "Khi bạn trả lương cho một nhóm người mới theo quy tắc khác, mở thêm một quốc gia, hoặc dựng lại một chương trình cũ. Phần Cài đặt của một chương trình mở lại đúng hành trình này để sửa."),
          prereq: B("A formula manager role, the company the scheme is for, and a sample employee to test it on.",
                    "Vai trò quản lý công thức, công ty mà chương trình lương dành cho, và một nhân viên mẫu để thử."),
          mistakes: [
            B("Thinking Finish switches the scheme on. Finish means the setup is complete and checked. Putting it live is a separate step, and it may need approval.",
              "Nghĩ rằng Hoàn thành là bật chương trình lên. Hoàn thành nghĩa là việc thiết lập đã xong và đã kiểm tra. Đưa vào dùng là một bước riêng, và có thể cần phê duyệt."),
            B("Skipping the Test step because the sample looks right. One ordinary person is one month. The checks try a joiner, a leaver and a tax-band edge.",
              "Bỏ qua bước Kiểm thử vì người mẫu trông đúng. Một người bình thường chỉ là một tháng. Các bước kiểm tra thử cả người mới vào, người nghỉ việc và mức biên của bậc thuế."),
            B("Picking the wrong country. The country decides the money the scheme pays in and its insurance and tax rules, and it locks once payslips exist.",
              "Chọn nhầm quốc gia. Quốc gia quyết định đồng tiền trả lương và các quy tắc bảo hiểm, thuế, và nó bị khoá khi đã có phiếu lương."),
          ],
        },
      },
      {
        id: "mapping", icon: "git-branch", star: true, mins: 9, after: "integrations",
        roles: ["officer", "owner"],
        search: B("mapping, where a number comes from, data source, spreadsheet columns", "ánh xạ, con số đến từ đâu, nguồn dữ liệu, cột bảng tính"),
        title: B("Mapping", "Ánh xạ"),
        desc: B("Where every value a pay scheme reads comes from — a file, a connected system or a record — drawn as one journey.",
                "Mỗi giá trị mà chương trình lương đọc đến từ đâu — một tệp, một hệ thống đã kết nối hay một hồ sơ — vẽ thành một hành trình."),
        outline: {
          what: B("Settings › Integrations › Mapping. A header reads FROM a source TO a scheme, and tabs show each kind of wire. The Journey tab draws the whole road, lane by lane.",
                  "Cài đặt › Tích hợp › Ánh xạ. Phần đầu đọc TỪ một nguồn ĐẾN một chương trình lương, và các tab cho thấy từng loại dây nối. Tab Hành trình vẽ cả chặng đường, từng làn một."),
          why: B("A payslip can only be as right as the values fed into it. When a number looks wrong, this is where you see which source it came from.",
                 "Một phiếu lương chỉ đúng được tới mức các giá trị đưa vào nó đúng. Khi một con số trông sai, đây là nơi bạn thấy nó đến từ nguồn nào."),
          when: B("When a scheme is new, when a source system changes its fields, and whenever someone asks where a number came from.",
                  "Khi chương trình lương còn mới, khi hệ thống nguồn đổi trường dữ liệu, và bất cứ khi nào có người hỏi một con số đến từ đâu."),
          prereq: B("Access to Settings › Integrations, a pay scheme, and at least one source: a connected system, a spreadsheet, or Payobook's own records.",
                    "Quyền vào Cài đặt › Tích hợp, một chương trình lương, và ít nhất một nguồn: một hệ thống đã kết nối, một bảng tính, hoặc chính hồ sơ trong Payobook."),
          mistakes: [
            B("Wiring the same component to two sources and expecting both to count. Sources are read in order, and a lower one only fills a box the higher one left empty.",
              "Nối cùng một thành phần vào hai nguồn và nghĩ rằng cả hai đều được tính. Các nguồn được đọc theo thứ tự, và nguồn thấp hơn chỉ điền vào ô mà nguồn cao hơn để trống."),
            B("Dropping this month's file on the spreadsheet tab and thinking the numbers are in. That tab reads headings and one example row. It imports nothing.",
              "Thả tệp của tháng này vào tab bảng tính và nghĩ rằng số liệu đã vào. Tab đó chỉ đọc tiêu đề và một dòng ví dụ. Nó không nhập gì cả."),
            B("Leaving a component marked not fed. The run will compute it as empty, and the payslip will be short by that much.",
              "Để một thành phần ở trạng thái chưa có nguồn. Đợt lương sẽ tính nó là trống, và phiếu lương sẽ thiếu đúng khoản đó."),
          ],
        },
      },
      {
        id: "treatment", icon: "settings", mins: 6, after: "mapping",
        roles: ["officer", "owner"],
        search: B("component treatment, figures do not add up, pay role, net pay", "xử lý thành phần, số liệu không khớp, vai trò trong lương, thực nhận"),
        title: B("Component treatment", "Xử lý thành phần"),
        desc: B("What a scheme does with each component: add it to net pay, take it off, or keep it for information only.",
                "Chương trình lương làm gì với từng thành phần: cộng vào thực nhận, trừ khỏi thực nhận, hay chỉ để tham khảo."),
        outline: {
          what: B("Mapping › Component treatment. One row per component, with its pay role, whether it is a subtotal, and its value type.",
                  "Ánh xạ › Xử lý thành phần. Mỗi thành phần một dòng, với vai trò trong lương, có phải tổng phụ hay không, và loại giá trị của nó."),
          why: B("The pay role decides the arithmetic from gross to net. A role set wrong makes deductions bigger than gross, and every report counts the wrong thing.",
                 "Vai trò trong lương quyết định phép tính từ tổng thu nhập xuống thực nhận. Đặt sai vai trò là khấu trừ lớn hơn cả tổng thu nhập, và mọi báo cáo đều đếm sai."),
          when: B("Before a scheme's first pay run, after a workbook import, and whenever a run says \"These figures do not add up\".",
                  "Trước đợt lương đầu tiên của một chương trình, sau khi nhập một sổ tính, và bất cứ khi nào một đợt lương báo \"Các số liệu này không khớp\"."),
          prereq: B("Access to Settings › Integrations › Mapping, and the pay scheme you want to check.",
                    "Quyền vào Cài đặt › Tích hợp › Ánh xạ, và chương trình lương bạn muốn kiểm tra."),
          mistakes: [
            B("Setting hours or days to add to net pay. Hours reach net pay by multiplying an amount; on their own they are information only.",
              "Đặt giờ hoặc ngày công để cộng vào thực nhận. Giờ đi vào thực nhận bằng cách nhân với một số tiền; riêng chúng chỉ để tham khảo."),
            B("Leaving gross as a normal line. Its parts are already added, so without Subtotal ticked the totals count them twice.",
              "Để tổng thu nhập như một dòng thường. Các phần của nó đã được cộng rồi, nên nếu không đánh dấu Tổng phụ thì các tổng sẽ tính chúng hai lần."),
            B("Saving and expecting the old payslips to change. Saving never rewrites a payslip; recompute the run to see the new treatment.",
              "Lưu rồi chờ các phiếu lương cũ tự thay đổi. Lưu không bao giờ viết lại phiếu lương; hãy tính lại đợt lương để thấy cách xử lý mới."),
          ],
        },
      },
      {
        id: "matrix", icon: "clipboard-check", star: true, mins: 8, after: null,
        roles: ["owner", "approver"],
        search: B("approval route, who approves, change an approval, sign-off", "lộ trình phê duyệt, ai phê duyệt, đổi phê duyệt, ký duyệt"),
        title: B("Approval Matrix", "Ma trận phê duyệt"),
        desc: B("Who signs off what, in which order: every approval route in the company, read and changed in one place.",
                "Ai phê duyệt việc gì, theo thứ tự nào: mọi lộ trình phê duyệt trong công ty, đọc và sửa ở cùng một nơi."),
        outline: {
          what: B("Settings › Approvals › Approval Matrix. One row per process — pay run, overtime, a bulk records change — with the route it follows and whether it is in use.",
                  "Cài đặt › Phê duyệt › Ma trận phê duyệt. Mỗi quy trình một dòng — đợt lương, tăng ca, thay đổi hồ sơ hàng loạt — kèm lộ trình nó đi theo và nó có đang được dùng hay không."),
          why: B("Every request in the Approvals inbox travels a route drawn here. When nobody seems to decide, the reason is almost always on this screen.",
                 "Mọi yêu cầu trong hộp Phê duyệt đều đi theo một lộ trình vẽ ở đây. Khi không ai quyết định, lý do hầu như luôn nằm trên màn hình này."),
          when: B("When a person leaves or goes on holiday, when a new process needs a check, and when the company decides a check is no longer needed.",
                  "Khi có người nghỉ việc hoặc đi nghỉ, khi một quy trình mới cần kiểm tra, và khi công ty quyết định một bước kiểm tra không còn cần nữa."),
          prereq: B("The approval administrator role. Anyone can read a route from the request it is on.",
                    "Vai trò quản trị phê duyệt. Ai cũng có thể đọc lộ trình ngay trên yêu cầu đang đi theo nó."),
          mistakes: [
            B("Expecting a published change to move requests already on their way. Publishing affects new requests only; the rest finish the route they started.",
              "Chờ một thay đổi vừa ban hành chuyển luôn những yêu cầu đang đi. Ban hành chỉ áp cho yêu cầu mới; số còn lại đi hết lộ trình chúng đã bắt đầu."),
            B("Naming a person instead of a responsibility. When that person leaves, the route stops. Name the responsibility, and arrange cover for holidays.",
              "Ghi tên một người thay vì một trách nhiệm. Khi người đó nghỉ, lộ trình dừng lại. Hãy ghi trách nhiệm, và sắp xếp người trực thay cho kỳ nghỉ."),
            B("Reading No approval needed as \"nothing is recorded\". It happens at once, and every use still shows in History.",
              "Hiểu Không cần phê duyệt là \"không có gì được ghi lại\". Việc đó diễn ra ngay, và mỗi lần dùng vẫn hiện trong Lịch sử."),
          ],
        },
      },
      {
        id: "records", icon: "database", mins: 7, after: "mapping",
        roles: ["hr", "officer"],
        search: B("bulk update, change many employees at once, records desk, export and import", "cập nhật hàng loạt, sửa nhiều nhân viên cùng lúc, records desk, xuất và nhập"),
        title: B("Records Desk", "Bàn cập nhật hồ sơ (Records Desk)"),
        desc: B("Change the employee, contract and bank details a pay scheme reads, for one person or hundreds, and review before anything is saved.",
                "Sửa thông tin nhân viên, hợp đồng và ngân hàng mà một chương trình lương đọc, cho một người hay hàng trăm người, và xem lại trước khi lưu."),
        outline: {
          what: B("People › Records. A grid of people and the fields their pay scheme reads, with a file round trip: export, edit, import, review.",
                  "Con người › Hồ sơ. Một lưới gồm mọi người và các trường mà chương trình lương của họ đọc, kèm một vòng qua tệp: xuất, sửa, nhập, xem lại."),
          why: B("A raise for forty people typed one form at a time is forty chances to slip. Here every change is listed before it is saved, and can be undone.",
                 "Tăng lương cho bốn mươi người mà gõ từng biểu mẫu là bốn mươi lần có thể nhầm. Ở đây mọi thay đổi được liệt kê trước khi lưu, và có thể hoàn tác."),
          when: B("A yearly pay review, a new allowance for a whole team, a bank change for many people, or cleaning data before a first pay run.",
                  "Một đợt xét lương hằng năm, một khoản phụ cấp mới cho cả nhóm, đổi ngân hàng cho nhiều người, hoặc làm sạch dữ liệu trước đợt lương đầu tiên."),
          prereq: B("A pay scheme whose Mapping reads employee, contract or bank fields. If it reads none, the desk says so and offers Open Mapping.",
                    "Một chương trình lương có phần Ánh xạ đọc các trường nhân viên, hợp đồng hoặc ngân hàng. Nếu không đọc trường nào, bàn làm việc sẽ nói vậy và gợi ý Mở Ánh xạ."),
          mistakes: [
            B("Editing an exported file for days, then importing it. A value changed on screen in the meantime makes that row sent back for a look.",
              "Sửa tệp đã xuất trong nhiều ngày rồi mới nhập. Giá trị nào bị sửa trên màn hình trong lúc đó sẽ khiến dòng ấy bị trả lại để xem."),
            B("Skipping Review because the grid looks right. Review is the only place that lists who changes, from what to what, before it is sent.",
              "Bỏ qua Xem lại vì lưới trông đúng. Xem lại là nơi duy nhất liệt kê ai thay đổi, từ gì sang gì, trước khi gửi đi."),
            B("Thinking Apply saved it when the company has a route for bulk changes. Then it says Sent for approval, and nothing changes until it is approved.",
              "Nghĩ rằng Áp dụng đã lưu trong khi công ty có lộ trình cho thay đổi hàng loạt. Khi đó nó báo Đã gửi phê duyệt, và chưa có gì thay đổi cho tới khi được duyệt."),
          ],
        },
      },
      {
        id: "schemes", icon: "globe", mins: 7, after: "blueprint",
        roles: ["owner", "officer"],
        search: B("currency, pay people in another currency, exchange rate, group, several schemes", "tiền tệ, trả lương bằng đồng tiền khác, tỷ giá, tập đoàn, nhiều chương trình lương"),
        title: B("Schemes and currencies", "Chương trình lương và tiền tệ"),
        desc: B("A pay scheme pays in its own country's money. Many schemes, many currencies — and totals that never add two monies together.",
                "Một chương trình lương trả bằng đồng tiền của quốc gia nó. Nhiều chương trình, nhiều đồng tiền — và các con số tổng không bao giờ cộng hai đồng tiền với nhau."),
        outline: {
          what: B("Where currency lives: on the pay scheme, set by its country. Settings › Group says how the companies are read together and how exchange rates are picked.",
                  "Đồng tiền nằm ở đâu: trên chương trình lương, do quốc gia của nó quyết định. Cài đặt › Tập đoàn cho biết các công ty được đọc chung ra sao và tỷ giá được chọn thế nào."),
          why: B("Adding đồng to Singapore dollars gives a number that means nothing. Payobook keeps each figure in the money it was paid in, and converts only when you ask.",
                 "Cộng đồng với đô la Singapore cho ra một con số vô nghĩa. Payobook giữ mỗi con số bằng đồng tiền đã trả, và chỉ quy đổi khi bạn yêu cầu."),
          when: B("When you pay people in a second country, when two schemes run in one month, and when someone asks for the group's total.",
                  "Khi bạn trả lương ở quốc gia thứ hai, khi hai chương trình chạy trong cùng một tháng, và khi có người hỏi tổng của cả tập đoàn."),
          prereq: B("A pay scheme per country you pay in. For group totals, a group with its currency and exchange rates set.",
                    "Mỗi quốc gia bạn trả lương có một chương trình lương. Để có tổng tập đoàn, cần một tập đoàn đã đặt đồng tiền và tỷ giá."),
          mistakes: [
            B("Running one pay run for two schemes. A pay run is always one scheme; two schemes in one month are two pay runs.",
              "Chạy một đợt lương cho hai chương trình. Một đợt lương luôn là một chương trình; hai chương trình trong một tháng là hai đợt lương."),
            B("Quoting a converted total as if it was paid. Nothing is stored in the group currency; the figure changes with the rate policy.",
              "Trích một con số đã quy đổi như thể đó là số đã chi. Không có gì được lưu bằng đồng tiền tập đoàn; con số thay đổi theo cách chọn tỷ giá."),
            B("Leaving a month without a rate. Figures for that month stay in their own money and are left out of the converted total, with the reason shown.",
              "Để một tháng không có tỷ giá. Số liệu của tháng đó giữ nguyên đồng tiền của nó và bị để ra ngoài tổng đã quy đổi, kèm lý do."),
          ],
        },
      },
      /* LEARN REFRESH step 4 — who can do what, and lending it while away. */
      {
        id: "access", icon: "key", star: true, mins: 8, after: null,
        roles: ["owner"],
        search: B("access, delegation, give someone access, hand my access over while I'm away, see it as", "quyền truy cập, uỷ quyền, cấp quyền, bàn giao quyền khi vắng mặt, xem dưới góc nhìn"),
        title: B("Access and delegation", "Quyền truy cập và uỷ quyền"),
        desc: B("Who can open which screens, told as roles in plain words — and handing your access to someone while you are away.",
                "Ai được mở màn hình nào, trình bày thành các vai trò bằng lời dễ hiểu — và bàn giao quyền của bạn cho người khác khi bạn vắng mặt."),
        outline: {
          what: B("Settings › Access & delegation. Tabs Roles, People, Screens and Hand-overs; See it as shows the app as someone else sees it.",
                  "Cài đặt › Quyền truy cập & uỷ quyền. Các tab Roles, People, Screens và Hand-overs; See it as cho thấy ứng dụng như người khác nhìn thấy."),
          why: B("Pay is private. Giving the right role, and taking it back when it ends, is what keeps it private.",
                 "Lương là thông tin riêng tư. Cấp đúng vai trò, và thu hồi khi hết hạn, là cách giữ nó riêng tư."),
          when: B("When someone joins or changes job, before you go on holiday, and when someone asks why they cannot see a screen.",
                  "Khi có người vào làm hoặc đổi việc, trước khi bạn đi nghỉ, và khi có người hỏi vì sao họ không thấy một màn hình."),
          prereq: B("Everyone can open it and hand their own access over. Giving roles and See it as need an access manager.",
                    "Ai cũng mở được và bàn giao được quyền của mình. Cấp vai trò và See it as cần quyền quản lý truy cập."),
          mistakes: [
            B("Sharing your password instead of handing access over. A hand-over is recorded and ends by itself; a password does neither.",
              "Đưa mật khẩu thay vì bàn giao quyền. Bàn giao được ghi lại và tự kết thúc; mật khẩu thì không làm được cả hai."),
            B("Forgetting that See it as is only a view. You still have exactly your own access, and nothing you press acts as them.",
              "Quên rằng See it as chỉ là một cách xem. Bạn vẫn giữ đúng quyền của mình, và không nút nào bạn bấm hành động thay họ."),
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
        title: B("Pulse", "Tổng quan"),
        desc: B("Home › Pulse: where this month's payroll is, the numbers that describe the company, and the way into everything else.",
                "Trang chủ › Tổng quan: kỳ lương tháng này đang ở đâu, các con số mô tả công ty, và lối vào mọi thứ khác."),
        outline: {
          what: B("The first tab of Home. A greeting with the latest pay run, then which month the figures are for, with a strip of payroll months. Then four numbers, and three cards: Latest pay run, Company overview and Formula engine.",
                  "Tab đầu tiên của Trang chủ. Một lời chào kèm đợt lương mới nhất, một dòng cho biết số liệu thuộc tháng nào, một dải các tháng lương, bốn con số, và ba thẻ: Đợt lương mới nhất, Tổng quan công ty và Bộ máy công thức."),
          why: B("It is the only screen that answers \"how is payroll doing right now\" without you choosing a filter first. The tiles report. The buttons and cards are the doors into the screens those figures came from.",
                 "Đây là màn hình duy nhất trả lời được \"công việc lương lúc này ra sao\" mà bạn không phải chọn bộ lọc trước. Các ô chỉ số chỉ báo cáo. Còn các nút và thẻ mới là cửa dẫn vào những màn hình đã sinh ra các con số ấy."),
          when: B("First thing, every day of payroll week. And any time you have been away long enough to lose the thread.",
                  "Việc đầu tiên, mỗi ngày trong tuần tính lương. Và bất cứ khi nào bạn vắng đủ lâu để mất mạch công việc."),
          prereq: B("Nothing at all. Home is the page everybody lands on.",
                    "Không cần gì cả. Trang chủ là trang ai cũng vào đầu tiên."),
          mistakes: [
            B("Reading a tile as today's work. Headcount and monthly payroll describe the company. \"Pending approval\" counts payslips waiting, company-wide — how many requests are yours is on the Approvals tab.",
              "Đọc một ô chỉ số như thể đó là việc của hôm nay. Số lượng nhân sự và chi phí lương tháng mô tả cả công ty. \"Đang chờ phê duyệt\" đếm số phiếu lương đang chờ trên toàn công ty — bao nhiêu yêu cầu là của bạn thì nằm ở tab Phê duyệt."),
            B("Forgetting which month the figures are for. The line above the tiles says it; press another month in the strip and every figure follows.",
              "Quên mất số liệu đang là của tháng nào. Dòng phía trên các ô nói rõ điều đó; bấm một tháng khác trên dải là mọi con số đổi theo."),
            B("Waiting for this page to tell you something is wrong. It shows what is happening, not what has been checked.",
              "Chờ trang này báo cho biết có gì đó sai. Nó cho thấy điều đang diễn ra, không cho thấy điều đã được kiểm tra."),
          ],
        },
      },
      {
        id: "approvals", icon: "clipboard-check", star: true, required: true, mins: 8, after: "dashboard",
        title: B("Approvals", "Phê duyệt"),
        desc: B("Home › Approvals: one inbox for everything waiting for a decision — pay runs included — and the route each one travels.",
                "Trang chủ › Phê duyệt: một hộp duy nhất cho mọi thứ đang chờ quyết định — kể cả đợt lương — và lộ trình mỗi yêu cầu đi qua."),
        outline: {
          what: B("One inbox with four tabs: My turn, All I can see, Sent back and Finished. Each request is a card with its route — the steps it must pass, in order — and who it is waiting for. Open one and you see the facts frozen when it was sent in, and the decisions: Approve, Send it back, Turn it down.",
                  "Một hộp phê duyệt với bốn tab: Đến lượt tôi, Tất cả tôi xem được, Đã trả lại và Đã xong. Mỗi yêu cầu là một thẻ kèm lộ trình — các bước phải đi qua, theo thứ tự — và đang chờ ai. Mở một yêu cầu, bạn thấy các dữ kiện được giữ nguyên từ lúc gửi, và các quyết định: Phê duyệt, Trả lại, Từ chối."),
          why: B("A pay run is paid only after everyone on its route has said yes. The route is the one your company drew in the Approval Matrix, so this inbox is where your signature actually happens.",
                 "Một đợt lương chỉ được chi khi mọi người trên lộ trình của nó đã đồng ý. Lộ trình do công ty bạn vẽ trong Ma trận phê duyệt, nên hộp này là nơi chữ ký của bạn thực sự diễn ra."),
          when: B("Every morning of payroll week, and whenever you are told something is waiting for you.",
                  "Mỗi sáng trong tuần tính lương, và bất cứ khi nào được báo có việc đang chờ bạn."),
          prereq: B("Being named on a step of a route. Anyone can open the inbox; a request is yours to decide only when a step names you.",
                    "Có tên trên một bước của lộ trình. Ai cũng mở được hộp phê duyệt; một yêu cầu chỉ là của bạn khi một bước ghi tên bạn."),
          mistakes: [
            B("Approving from the card without opening it. The card shows a total; the facts, the change against last month and the payslips behind them are one press away.",
              "Phê duyệt ngay trên thẻ mà chưa mở ra. Thẻ chỉ hiện con số tổng; các dữ kiện, mức thay đổi so với tháng trước và các phiếu lương phía sau chỉ cách một lần bấm."),
            B("Turning it down when it only needs fixing. Turn it down ends the request and cancels the pay run. Send it back returns it to Draft with your note, so it can be fixed and sent in again.",
              "Từ chối khi nó chỉ cần sửa. Từ chối là kết thúc yêu cầu và huỷ đợt lương. Trả lại đưa nó về Nháp kèm ghi chú của bạn, để được sửa và gửi lại."),
            B("Writing a note nobody can act on. \"Wrong\" makes the preparer guess. Name the payslip, the figure and what to check.",
              "Viết một ghi chú không ai xử lý được. \"Sai\" buộc người lập phải đoán. Hãy nêu rõ phiếu nào, con số nào và cần kiểm tra gì."),
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
        /* LEARN REFRESH step 5. Contracts is a door INSIDE People › Employees
           now (a button, and a per-row "Contract" drawer), so the old
           `contracts` station folds into this one; its key redirects here
           (STATION_ALIASES) and its progress rows were migrated. */
        id: "employees", icon: "users", required: true, mins: 8, after: null,
        roles: ["hr", "officer"],
        search: B("employees, contracts, contract drawer, payroll ready, bank details, monthly wage",
                  "nhân viên, hợp đồng, ngăn hợp đồng, sẵn sàng trả lương, thông tin ngân hàng, lương tháng"),
        title: B("Employees and contracts", "Nhân viên và hợp đồng"),
        desc: B("Everyone the company employs, whether each of them can be paid, and each person's contract in a drawer beside the list.",
                "Mọi người công ty đang thuê, từng người có trả lương được không, và hợp đồng của mỗi người trong một ngăn ngay cạnh danh sách."),
        outline: {
          what: B("People › Employees. A line of numbers, status chips, and one row per person with a Contract button. The button opens their contract in a drawer: Terms, Components and History.",
                  "Con người › Nhân viên. Một dòng con số, các chip trạng thái, và mỗi người một dòng có nút Hợp đồng. Nút đó mở hợp đồng của họ trong một ngăn: Terms, Components và History."),
          why: B("Payroll pays from the contract, not from the person. Someone on the list with no running contract or no bank details computes perfectly and is still not paid.",
                 "Hệ thống lương trả theo hợp đồng, không theo con người. Một người có trong danh sách mà không có hợp đồng đang hiệu lực hoặc chưa có thông tin ngân hàng vẫn được tính đúng mà vẫn không nhận được tiền."),
          when: B("Before every run. And whenever someone joins, changes job or pay, or asks what their contract says.",
                  "Trước mỗi đợt lương. Và mỗi khi có người vào làm, đổi công việc hay mức lương, hoặc hỏi hợp đồng của họ ghi gì."),
          prereq: B("People access for the list, and contract access for the Contract button and the Contracts board. Changing a contract needs an HR manager.",
                    "Quyền vào Con người để xem danh sách, và quyền về hợp đồng để dùng nút Hợp đồng và bảng Hợp đồng. Muốn sửa hợp đồng cần quản lý nhân sự."),
          mistakes: [
            B("Reading Payroll-ready as everyone ready. That number counts bank details only; the tick on each row also needs a running contract.",
              "Hiểu Sẵn sàng trả lương là mọi người đã sẵn sàng. Con số đó chỉ đếm thông tin ngân hàng; dấu tích trên từng dòng còn cần hợp đồng đang hiệu lực."),
            B("Expecting Components to show this month's amounts. Many arrive with each pay run, so the contract can rightly read 0.",
              "Chờ Components hiện số tiền của tháng này. Nhiều khoản đến theo từng đợt lương, nên hợp đồng có thể hiện 0 là đúng."),
            B("Editing a contract and walking away. Nothing is saved until Save, and a change may go for approval first.",
              "Sửa hợp đồng rồi bỏ đi. Không có gì được lưu cho tới khi bấm Save, và một thay đổi có thể phải qua phê duyệt trước."),
          ],
        },
      },
      /* -----------------------------------------------------------------------
         LEARN REFRESH step 4 — THE WIDER APP. People › Pay (bands, the pay
         review), People › Plan (the Decision Room) and a short tour of the
         rest of People and Home. `roles` and `search` as in step 3.
         -------------------------------------------------------------------- */
      {
        id: "paybands", icon: "bar-chart", mins: 7, after: null,
        roles: ["hr", "owner"],
        search: B("pay bands, salary ranges, fairness, pay gap, who is paid below the band", "khoảng lương, dải lương, công bằng, chênh lệch lương, ai được trả dưới khoảng lương"),
        title: B("Pay bands and fairness", "Khoảng lương và công bằng"),
        desc: B("The pay range for each kind of job, with every person placed in it, and a plain check on whether pay is fair.",
                "Khoảng lương cho từng loại công việc, với mỗi người được đặt vào đó, và một phép kiểm tra rõ ràng xem lương có công bằng không."),
        outline: {
          what: B("People › Pay, on the Bands and Fairness tabs. Bands draws each range as a picture with a dot per person. Fairness shows the pay gaps.",
                  "Con người › Lương, ở tab Khoảng lương và Công bằng. Khoảng lương vẽ mỗi khoảng thành một hình, mỗi người là một chấm. Công bằng cho thấy các khoảng chênh lệch lương."),
          why: B("A band is the company's promise about what a job is worth. Seeing everyone in it shows who has fallen behind before they tell you.",
                 "Khoảng lương là cam kết của công ty về giá trị của một công việc. Nhìn thấy mọi người trong đó cho biết ai đang bị tụt lại trước khi họ nói ra."),
          when: B("Before a pay review, when you place a new hire, and whenever someone asks whether their pay is fair.",
                  "Trước một đợt xét lương, khi xếp lương cho người mới, và bất cứ khi nào có người hỏi lương của mình có công bằng không."),
          prereq: B("Pay viewer access to read the bands. Only pay managers and group admins can change them.",
                    "Quyền xem lương để đọc các khoảng lương. Chỉ quản lý lương và quản trị tập đoàn mới sửa được."),
          mistakes: [
            B("Reading a band as a pay rise. Nothing on the Bands tab changes anybody's pay; a rise happens in a review or a pay change.",
              "Hiểu khoảng lương như một lần tăng lương. Không có gì ở tab Khoảng lương thay đổi lương của ai; tăng lương diễn ra trong đợt xét lương hoặc một thay đổi lương."),
            B("Dragging a band edge without reading the cost. The screen shows what the move would cost before you let go.",
              "Kéo mép một khoảng lương mà không đọc chi phí. Màn hình cho biết thay đổi đó tốn bao nhiêu trước khi bạn thả tay."),
            B("Quoting the pay gap as stored. Fairness is worked out each time you open it; print the statement to keep one.",
              "Trích khoảng chênh lệch lương như một con số đã lưu. Công bằng được tính lại mỗi lần bạn mở; hãy in bản tường trình nếu muốn giữ lại."),
          ],
        },
      },
      {
        id: "payreview", icon: "trending-up", star: true, mins: 9, after: "paybands",
        roles: ["hr", "owner", "approver"],
        search: B("pay review, pay rise, salary increase, who signs a pay review, pay change", "xét lương, tăng lương, ai ký đợt xét lương, thay đổi lương"),
        title: B("Pay review and pay changes", "Xét lương và thay đổi lương"),
        desc: B("A yearly review for everyone at once, inside a budget, signed off step by step — and a single pay change for one person.",
                "Đợt xét lương hằng năm cho mọi người cùng lúc, trong một ngân sách, được duyệt từng bước — và một thay đổi lương cho riêng một người."),
        outline: {
          what: B("People › Pay › Review: a worksheet with a row per person, a budget meter and calibration. Changes holds single pay changes.",
                  "Con người › Lương › Xét lương: một bảng tính mỗi người một dòng, một thước đo ngân sách và phần cân chỉnh. Thay đổi chứa các thay đổi lương lẻ."),
          why: B("A review decides next year's pay for everybody. Doing it in one place keeps it inside the budget and fair, with every sign-off recorded.",
                 "Đợt xét lương quyết định lương năm sau của mọi người. Làm ở một nơi giữ nó trong ngân sách và công bằng, mọi lần duyệt đều được ghi lại."),
          when: B("Once a year for the review. A pay change for a promotion, a mistake to put right, or keeping up with the market.",
                  "Mỗi năm một lần cho đợt xét lương. Một thay đổi lương khi thăng chức, khi sửa một sai sót, hoặc để theo kịp thị trường."),
          prereq: B("Pay manager access to write a review. Each step of its sign-off names who decides.",
                    "Quyền quản lý lương để soạn đợt xét lương. Mỗi bước duyệt ghi rõ ai quyết định."),
          mistakes: [
            B("Sending it for approval with the meter over budget. The review lists what stops approval; clear it first.",
              "Gửi duyệt khi thước đo đã vượt ngân sách. Đợt xét lương liệt kê điều gì chặn duyệt; hãy xử lý trước."),
            B("Skipping calibration. A top score with the smallest rise stands out, and somebody will ask why.",
              "Bỏ qua cân chỉnh. Điểm cao nhất mà mức tăng nhỏ nhất sẽ nổi bật, và sẽ có người hỏi vì sao."),
            B("Thinking Approved means paid. Apply writes the new pay onto the records; the next pay run reads it.",
              "Nghĩ rằng Đã duyệt là đã trả. Áp dụng mới ghi lương mới vào hồ sơ; đợt lương kế tiếp sẽ đọc nó."),
          ],
        },
      },
      {
        id: "decisionroom", icon: "sliders", mins: 7, after: null,
        roles: ["owner"],
        search: B("decision room, plan next year, what if, headcount plan, exact cost", "phòng quyết định, kế hoạch năm sau, nếu như, kế hoạch nhân sự, chi phí chính xác"),
        title: B("Decision Room", "Phòng quyết định"),
        desc: B("Try next year before you commit to it: more people, a rise, less overtime — and see what it does to cost and profit.",
                "Thử trước năm sau trước khi cam kết: thêm người, tăng lương, bớt tăng ca — và xem điều đó ảnh hưởng thế nào tới chi phí và lợi nhuận."),
        outline: {
          what: B("People › Plan. Levers on the left, results in tabs, a compare table, and Exact cost, which runs a plan through the real pay scheme.",
                  "Con người › Kế hoạch. Các cần gạt bên trái, kết quả theo tab, một bảng so sánh, và Chi phí chính xác, chạy kế hoạch qua chương trình lương thật."),
          why: B("A plan argued from a spreadsheet is argued from someone's guess. Here every lever shows its cost the moment you move it.",
                 "Một kế hoạch bàn từ bảng tính là bàn từ phỏng đoán của ai đó. Ở đây mỗi cần gạt cho thấy chi phí ngay khi bạn xoay nó."),
          when: B("Budget season, before a hiring wave, and whenever someone asks what a rise for everyone would really cost.",
                  "Mùa lập ngân sách, trước một đợt tuyển dụng, và bất cứ khi nào có người hỏi tăng lương cho mọi người thật sự tốn bao nhiêu."),
          prereq: B("A Decision Room role. Exact cost needs a saved plan and a pay scheme for the people in it.",
                    "Vai trò Phòng quyết định. Chi phí chính xác cần một kế hoạch đã lưu và chương trình lương cho những người trong đó."),
          mistakes: [
            B("Quoting the estimate as the answer. Press Exact cost; it says how far the estimate was off.",
              "Trích con số ước tính như câu trả lời. Hãy bấm Chi phí chính xác; nó cho biết ước tính lệch bao nhiêu."),
            B("Expecting a plan to change payroll. Nothing here changes payroll; an approved plan is a decision, not a pay run.",
              "Chờ một kế hoạch thay đổi bảng lương. Không có gì ở đây thay đổi bảng lương; kế hoạch được duyệt là một quyết định, không phải một đợt lương."),
          ],
        },
      },
      {
        id: "peoplemore", icon: "heart", mins: 5, after: "employees",
        roles: ["hr"],
        search: B("wall, praise, say thank you, announcements, assets, goals, where they work", "bảng vinh danh, khen ngợi, cảm ơn, thông báo, tài sản, mục tiêu, nơi làm việc"),
        title: B("The rest of People and Home", "Phần còn lại của Con người và Trang chủ"),
        desc: B("Praise on the Wall, messages in Announce, and the People tabs for where people work, what they hold and what they aim for.",
                "Lời khen trên Bảng vinh danh, thông báo ở Thông báo, và các tab của Con người về nơi mọi người làm, họ giữ gì và họ hướng tới điều gì."),
        outline: {
          what: B("Home › Wall and Announce; People › Where they work, Assets, Praise and Goals. Each tab shows only when your company uses it.",
                  "Trang chủ › Bảng vinh danh và Thông báo; Con người › Nơi họ làm việc, Tài sản, Khen ngợi và Mục tiêu. Mỗi tab chỉ hiện khi công ty bạn dùng nó."),
          why: B("Pay is one part of working here. These tabs hold the rest, next to the records payroll already trusts.",
                 "Lương chỉ là một phần của việc làm ở đây. Các tab này giữ phần còn lại, ngay cạnh hồ sơ mà bảng lương vẫn tin dùng."),
          when: B("Whenever you want to thank someone, tell everyone something, hand out a laptop, or check a goal.",
                  "Bất cứ khi nào bạn muốn cảm ơn ai đó, báo cho mọi người một điều, cấp một máy tính, hoặc xem một mục tiêu."),
          prereq: B("Everyone can read the Wall and Announce. The People tabs follow their own access.",
                    "Ai cũng đọc được Bảng vinh danh và Thông báo. Các tab của Con người theo quyền riêng của chúng."),
          mistakes: [
            B("Looking for a tab your company has not switched on. A missing tab is not broken; it is not in your company.",
              "Đi tìm một tab mà công ty bạn chưa bật. Tab không có không phải là bị lỗi; nó không có trong công ty bạn."),
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
        id: "insights", icon: "trending-up", required: true, mins: 6, after: null,
        roles: ["owner", "approver", "officer"],
        search: B("insights, pulse, cost story, net payroll, per head, statutory split",
                  "phân tích, tổng quan, diễn biến chi phí, lương thực chi, bình quân đầu người"),
        title: B("Insights › Pulse", "Phân tích › Tổng quan"),
        desc: B("The board that answers the questions every pay month asks, and opens Explorer on any figure.",
                "Bảng trả lời những câu hỏi tháng lương nào cũng đặt ra, và mở Explorer trên bất kỳ con số nào."),
        outline: {
          what: B("Insights › Pulse. At the top, the newest run's net payroll with its state. Below it: the cost story over 3, 6 or 12 months, the department leaderboard, the statutory split and the workforce pulse.",
                  "Phân tích › Tổng quan. Trên cùng là lương thực chi của đợt mới nhất kèm trạng thái. Bên dưới: diễn biến chi phí theo 3, 6 hoặc 12 tháng, xếp hạng phòng ban, cơ cấu khoản đóng bắt buộc và nhịp nhân sự."),
          why: B("It answers the usual questions fast, and every figure opens Explorer to show what it is made of.",
                 "Nó trả lời nhanh những câu hỏi quen thuộc, và mọi con số đều mở Explorer để cho thấy nó được tạo từ đâu."),
          when: B("After a run is computed, at month end, and whenever someone asks why payroll moved.",
                  "Sau khi một đợt được tính, vào cuối tháng, và bất cứ khi nào có người hỏi vì sao chi phí lương thay đổi."),
          prereq: B("An analytics role, and at least two runs for a trend.",
                    "Vai trò phân tích, và ít nhất hai đợt lương để có xu hướng."),
          mistakes: [
            B("Quoting the headline without its state chip. A draft computed an hour ago shows here too.",
              "Trích con số nổi bật mà bỏ qua chip trạng thái. Một đợt nháp vừa tính một giờ trước cũng hiện ở đây."),
            B("Comparing totals instead of per head. Headcount moves between months.",
              "So các con số tổng thay vì theo đầu người. Số người thay đổi giữa các tháng."),
            B("Quoting the cost story without its window. 3M and 12M tell different stories.",
              "Trích diễn biến chi phí mà không nói khoảng thời gian. 3M và 12M kể hai câu chuyện khác nhau."),
          ],
        },
      },
      {
        id: "explorer", icon: "compass", mins: 7, after: "insights",
        roles: ["owner", "officer"],
        search: B("explorer, measure, break down, compare schemes, filter, explain a movement",
                  "khám phá dữ liệu, chỉ tiêu, chia theo, so sánh chương trình lương, bộ lọc, giải thích biến động"),
        title: B("Explorer", "Khám phá dữ liệu"),
        desc: B("For the question the board did not expect: pick a measure, split it, set the time and the filters.",
                "Dành cho câu hỏi bảng tổng quan không lường trước: chọn chỉ tiêu, cách chia, thời gian và bộ lọc."),
        outline: {
          what: B("Insights › Explorer. Starting points, then Measure, By and Over, then When and Where. The headline gives the total, with Per person and Explain beside it.",
                  "Phân tích › Khám phá dữ liệu. Điểm xuất phát, rồi Chỉ tiêu, Theo và Chia theo thời gian, rồi Khi nào và Ở đâu. Dòng đầu cho tổng, kèm Trên mỗi người và Giải thích."),
          why: B("Real questions are rarely the ones a board expected. Explorer answers them from the payslips themselves, and never adds two currencies together.",
                 "Câu hỏi thật hiếm khi là câu bảng tổng quan đã lường trước. Explorer trả lời chúng từ chính phiếu lương, và không bao giờ cộng hai loại tiền với nhau."),
          when: B("When Pulse has said all it can, or someone needs a figure split a way no screen shows.",
                  "Khi Tổng quan đã nói hết những gì nó có thể, hoặc ai đó cần một con số chia theo cách chưa màn hình nào có."),
          prereq: B("An analytics role and a computed run. Know which measure you want before you filter.",
                    "Vai trò phân tích và một đợt đã tính. Hãy biết mình cần chỉ tiêu nào trước khi lọc."),
          mistakes: [
            B("Quoting a figure without its tags. Remove one and it is a different number.",
              "Trích một con số mà bỏ các thẻ. Gỡ một thẻ là ra con số khác."),
            B("Forgetting Main runs only. Mid-month advances are left out until you remove it.",
              "Quên thẻ Chỉ các kỳ lương chính. Các đợt tạm ứng giữa tháng bị loại cho tới khi bạn gỡ nó."),
          ],
        },
      },
      {
        id: "workforcean", icon: "bar-chart", mins: 5, after: "insights",
        roles: ["owner", "hr"],
        search: B("workforce insights, employees paid, joiners, leavers, cost per head",
                  "phân tích lực lượng lao động, nhân viên được trả lương, người vào, người nghỉ, chi phí bình quân"),
        title: B("Insights › Workforce", "Phân tích › Lực lượng lao động"),
        desc: B("The same months read as people: who was paid, who joined, who left, and the cost per head.",
                "Vẫn những tháng đó đọc theo con người: ai được trả lương, ai vào, ai nghỉ, và chi phí bình quân đầu người."),
        outline: {
          what: B("Insights › Workforce. Employees paid, joined, left and cost per head; the headcount-paid line; attendance exceptions, overtime load and time off.",
                  "Phân tích › Lực lượng lao động. Số nhân viên được trả lương, vào làm, đã nghỉ và chi phí bình quân đầu người; đường số người được trả; bất thường chấm công, khối lượng tăng ca và nghỉ phép."),
          why: B("People paid is not people employed. The gap between the two is where a missing payslip hides.",
                 "Được trả lương không đồng nghĩa với đang làm việc. Khoảng chênh giữa hai con số là chỗ một phiếu lương bị thiếu đang ẩn."),
          when: B("At month end, beside Pulse, and when a run's headcount is not what you expected.",
                  "Vào cuối tháng, cùng với Tổng quan, và khi số người của một đợt không như bạn nghĩ."),
          prereq: B("An analytics role, and at least two runs.",
                    "Vai trò phân tích, và ít nhất hai đợt lương."),
          mistakes: [
            B("Reading the headcount line as a hiring chart. A step can be a run that left somebody out.",
              "Đọc đường số người như biểu đồ tuyển dụng. Một bậc nhảy có thể là một đợt đã bỏ sót ai đó."),
            B("Leaving attendance exceptions for later. Each one becomes a question on next month's payslips.",
              "Để bất thường chấm công lại sau. Mỗi cái sẽ thành một câu hỏi trên phiếu lương tháng sau."),
          ],
        },
      },
      {
        id: "reports", icon: "landmark", mins: 6, after: "insights",
        roles: ["owner", "approver"],
        search: B("payroll report, budget, on pace, running warm, spent against budget",
                  "báo cáo lương, ngân sách, đúng nhịp, đang nóng lên, đã chi so với ngân sách"),
        title: B("Payroll Report and Budget", "Báo cáo lương và Ngân sách"),
        desc: B("One run's report against the run before, and whether each function's spending is on pace for the year.",
                "Báo cáo của một đợt so với đợt trước, và chi tiêu của từng bộ phận có đúng nhịp cả năm không."),
        outline: {
          what: B("Insights › Payroll Report: one run's totals, earnings, deductions and department summary, with changes against the run before. Insights › Budget: each function's spending against its budget, for the year or any stretch of months.",
                  "Phân tích › Báo cáo lương: tổng, thu nhập, khấu trừ và tổng theo phòng ban của một đợt, kèm thay đổi so với đợt trước. Phân tích › Ngân sách: chi tiêu của từng bộ phận so với ngân sách, cho cả năm hoặc bất kỳ khoảng tháng nào."),
          why: B("The report is what finance reads before sign-off. Budget warns early, while money is going faster than the year.",
                 "Báo cáo là thứ bộ phận tài chính đọc trước khi duyệt. Ngân sách cảnh báo sớm, khi tiền đang đi nhanh hơn năm."),
          when: B("The report before approving a run. Budget at each month end.",
                  "Báo cáo trước khi duyệt một đợt. Ngân sách vào mỗi cuối tháng."),
          prereq: B("Pay run access for the report; a budget role for Budget.",
                    "Quyền vào đợt lương để xem báo cáo; vai trò ngân sách để xem Ngân sách."),
          mistakes: [
            B("Reading under 100% as fine. Budget compares money gone with year gone.",
              "Hiểu dưới 100% là ổn. Ngân sách so tiền đã đi với năm đã trôi."),
            B("Signing off without opening the Changes. They are the people whose pay moved.",
              "Duyệt mà không mở phần Changes. Đó là những người có lương thay đổi."),
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
        id: "govreports", icon: "file-text", required: true, star: true, mins: 7, after: null,
        roles: ["officer", "owner"],
        search: B("government filings, file the monthly insurance report, generate a filing, social insurance", "báo cáo nộp cơ quan, nộp báo cáo bảo hiểm hằng tháng, tạo hồ sơ, bảo hiểm xã hội"),
        title: B("Government filings", "Báo cáo nộp cơ quan nhà nước"),
        desc: B("The statutory filings for this company's country, one month at a time — chosen, scoped and generated for you to file.",
                "Các báo cáo bắt buộc theo quốc gia của công ty này, mỗi lần một tháng — được chọn, khoanh phạm vi và tạo sẵn để bạn nộp."),
        outline: {
          what: B("Compliance › Filings shows the filings your country asks for, grouped by the office that reads them. Generate opens a three-step flow: Choose the filing, Scope, Generate.",
                  "Tuân thủ › Tờ khai hiện các báo cáo mà quốc gia bạn yêu cầu, nhóm theo cơ quan tiếp nhận. Tạo mở một luồng ba bước: Chọn hồ sơ, Phạm vi, Tạo."),
          why: B("A filing has a deadline set by law, not by your company, and somebody outside the company reads it. This screen tells you which filings apply to you without you having to ask around.",
                 "Một báo cáo bắt buộc có thời hạn do pháp luật ấn định chứ không do công ty bạn, và người đọc nó nằm ngoài công ty. Màn hình này cho bạn biết những báo cáo nào áp dụng với mình mà không phải đi hỏi khắp nơi."),
          when: B("After the month's runs are done, and before the office's deadline. A filing built on an unfinished month is a filing you will have to correct.",
                  "Sau khi các đợt lương của tháng đã Hoàn tất, và trước hạn nộp của cơ quan. Báo cáo lập trên một tháng chưa xong là báo cáo bạn sẽ phải đính chính."),
          prereq: B("Government filing access, and completed runs for the month. Payobook prepares the file. It does not submit it for you.",
                    "Quyền lập báo cáo nộp cơ quan, và các đợt lương của tháng đã Hoàn tất. Payobook lập tệp. Nó không nộp thay bạn."),
          mistakes: [
            B("Generating from a month whose runs are not all done. The tiles read what has been computed, so an unfinished run is a filing short by however many payslips are still moving.",
              "Kết xuất báo cáo khi các đợt lương của tháng chưa hoàn tất hết. Các biểu mẫu đọc phần đã tính, nên một đợt còn dở là một báo cáo thiếu đúng bằng số phiếu lương còn đang đi trong quy trình."),
            B("Reading \"coming soon\" as \"Payobook does not do this country\". It means the country's own payroll module is not installed on this database. Vietnam, Singapore, Thailand, Cambodia and Malaysia all have filings in the catalogue. Each set appears the moment its module is there, so the answer is a conversation with whoever administers the system.",
              "Hiểu dòng \"sắp có\" thành \"Payobook không hỗ trợ quốc gia này\". Nó chỉ có nghĩa là mô-đun tính lương của quốc gia đó chưa được cài trên cơ sở dữ liệu này. Việt Nam, Singapore, Thái Lan, Campuchia và Malaysia đều đã có biểu mẫu trong danh mục. Mỗi bộ xuất hiện ngay khi mô-đun của nó được cài, nên câu trả lời nằm ở cuộc trao đổi với người quản trị hệ thống."),
            B("Thinking Generate sent it. Generate makes the files for you to download; nothing is sent anywhere.",
              "Nghĩ rằng Tạo là đã nộp. Tạo chỉ sinh ra các tệp để bạn tải xuống; không có gì được gửi đi đâu cả."),
          ],
        },
      },
      /* LEARN REFRESH step 4 — the other three Compliance tabs, short. */
      {
        id: "compliancemore", icon: "shield-check", mins: 5, after: "govreports",
        roles: ["officer", "owner"],
        search: B("bank verification, bank-change request, young workers, audit trail, who changed what", "xác minh ngân hàng, yêu cầu đổi ngân hàng, lao động chưa thành niên, nhật ký kiểm toán, ai đã sửa gì"),
        title: B("Bank checks, young workers, audit", "Kiểm tra ngân hàng, lao động trẻ, kiểm toán"),
        desc: B("A bank change checked twice before anyone is paid to it, the hour limits for workers under 18, and who changed what.",
                "Một thay đổi ngân hàng được kiểm tra hai lần trước khi ai đó được trả vào đó, giới hạn giờ làm cho lao động dưới 18 tuổi, và ai đã sửa gì."),
        outline: {
          what: B("Compliance › Bank, Young workers and Audit. Bank takes a bank letter and walks it Draft → HR Review → Finance Review → Approved.",
                  "Tuân thủ › Ngân hàng, Lao động chưa thành niên và Nhật ký kiểm toán. Ngân hàng nhận một thư của ngân hàng và đưa nó qua Nháp → Nhân sự xét duyệt → Tài chính xét duyệt → Đã duyệt."),
          why: B("A changed bank account is the most common way pay is stolen. Two people checking it, and a record of who changed what, stop that.",
                 "Đổi tài khoản ngân hàng là cách phổ biến nhất để lương bị đánh cắp. Hai người kiểm tra, cùng nhật ký ai đã sửa gì, ngăn được điều đó."),
          when: B("When someone changes bank, when you hire anyone under 18, and when somebody asks who changed a salary.",
                  "Khi có người đổi ngân hàng, khi bạn tuyển người dưới 18 tuổi, và khi có người hỏi ai đã sửa một mức lương."),
          prereq: B("Everyone can start a bank change. Young workers needs payroll or attendance access; Audit is for payroll managers.",
                    "Ai cũng bắt đầu được một thay đổi ngân hàng. Lao động chưa thành niên cần quyền lương hoặc chấm công; Nhật ký kiểm toán dành cho quản lý lương."),
          mistakes: [
            B("Changing a bank account straight on the employee record. It skips both checks and leaves no request behind.",
              "Sửa tài khoản ngân hàng thẳng trên hồ sơ nhân viên. Làm vậy bỏ qua cả hai bước kiểm tra và không để lại yêu cầu nào."),
          ],
        },
      },
    ],
  },

  /* ---------------------------------------------------------------------------
     LEARN REFRESH step 4 — THE LIFECYCLE LINE.

     One person's road through the company, in the order it is lived: the job
     is asked for, the person joins, their trial ends, their contract comes up
     for a decision — and, years later, they leave. The map draws it as the
     road Hoàng Văn Nam walks (journey.js LIFE_TRAIL). Appended, not inserted,
     for the same numbering reason as the lines above.
     ------------------------------------------------------------------------ */
  lifecycle: {
    stations: [
      {
        id: "hiring", icon: "briefcase", star: true, mins: 8, after: null,
        roles: ["hr", "owner"],
        search: B("hiring, raise a hiring request, new job, candidates, interview", "tuyển dụng, đề xuất tuyển dụng, vị trí mới, ứng viên, phỏng vấn"),
        title: B("Hiring", "Tuyển dụng"),
        desc: B("Ask for a new person, get it signed off, write the advert, meet the candidates — every role on one board, four steps each.",
                "Đề xuất tuyển một người mới, xin phê duyệt, viết tin tuyển dụng, gặp ứng viên — mọi vị trí trên một bảng, mỗi vị trí bốn bước."),
        outline: {
          what: B("Lifecycle › Hiring. Quiet numbers on top, a four-step strip, and a card per role that says its step and what is next.",
                  "Vòng đời nhân sự › Tuyển dụng. Các con số nhỏ ở trên, một dải bốn bước, và mỗi vị trí một thẻ cho biết bước hiện tại và việc tiếp theo."),
          why: B("A new hire is a year of salary. Asking first, with the budget in front of the people who sign, stops a role being filled that nobody agreed to.",
                 "Một người mới là một năm lương. Đề xuất trước, với ngân sách trước mặt người phê duyệt, ngăn việc tuyển một vị trí chưa ai đồng ý."),
          when: B("As soon as a team needs someone new, or someone is leaving and must be replaced.",
                  "Ngay khi một nhóm cần thêm người, hoặc có người sắp nghỉ và cần người thay."),
          prereq: B("Hiring access. The tab shows only to the people the hiring screen itself lets in.",
                    "Quyền tuyển dụng. Tab chỉ hiện với những người mà chính màn hình tuyển dụng cho phép."),
          mistakes: [
            B("Advertising before the request is signed off. The board keeps the role at step 1 until it is.",
              "Đăng tin trước khi đề xuất được phê duyệt. Bảng giữ vị trí ở bước 1 cho tới khi được duyệt."),
            B("Leaving interview opinions unwritten. The board counts them as late, and the offer waits.",
              "Không viết ý kiến sau phỏng vấn. Bảng đếm chúng là trễ, và thư mời làm việc phải chờ."),
          ],
        },
      },
      {
        id: "joiners", icon: "user-plus", star: true, mins: 7, after: "hiring",
        roles: ["hr"],
        search: B("new joiner, first day, buddy, onboarding, starting soon", "nhân viên mới, ngày đầu tiên, người đồng hành, nhận việc, sắp vào làm"),
        title: B("New joiners", "Nhân viên mới"),
        desc: B("Everyone starting soon: their buddy, their first steps, and what is still to prepare before day one.",
                "Những người sắp vào làm: người đồng hành, những bước đầu tiên, và những gì còn phải chuẩn bị trước ngày đầu."),
        outline: {
          what: B("Lifecycle › New joiners. A card per person, three steps — Getting ready, Settling in, Checklist done — and a drawer of what is left.",
                  "Vòng đời nhân sự › Nhân viên mới. Mỗi người một thẻ, ba bước — Đang chuẩn bị, Đang hòa nhập, Đã xong danh mục — và một ngăn liệt kê việc còn lại."),
          why: B("The first week decides whether someone stays. It is also when payroll needs their bank account, before the first pay run.",
                 "Tuần đầu quyết định một người có ở lại hay không. Đó cũng là lúc bảng lương cần tài khoản ngân hàng của họ, trước đợt lương đầu tiên."),
          when: B("From the day an offer is accepted until the checklist is done.",
                  "Từ ngày lời mời được nhận lời cho tới khi danh mục việc xong."),
          prereq: B("Lifecycle access. The person must be in Payobook with a start date.",
                    "Quyền Vòng đời nhân sự. Người đó phải có trong Payobook với ngày bắt đầu."),
          mistakes: [
            B("Starting someone with no buddy. The board counts them as Still without a buddy; choose one.",
              "Để một người bắt đầu mà chưa có người đồng hành. Bảng đếm họ là Chưa có người đồng hành; hãy chọn một người."),
            B("Forgetting the bank account. A joiner without one is on the roster and cannot be paid.",
              "Quên tài khoản ngân hàng. Người mới chưa có tài khoản vẫn có trong danh sách nhưng không được trả lương."),
          ],
        },
      },
      {
        id: "probation", icon: "hourglass", mins: 7, after: "joiners",
        roles: ["hr"],
        search: B("probation, trial ends, confirm after probation, extend the trial", "thử việc, hết thử việc, xác nhận chính thức, kéo dài thử việc"),
        title: B("Probation", "Thử việc"),
        desc: B("Every trial that is running: colleagues asked, the manager's view, and one decision — confirm, extend or do not confirm.",
                "Mọi đợt thử việc đang chạy: ý kiến đồng nghiệp, nhận xét của quản lý, và một quyết định — xác nhận, kéo dài hoặc không xác nhận."),
        outline: {
          what: B("Lifecycle › Probation. Five steps from Choose peers to Share the outcome, and a card per person with their trial's end date.",
                  "Vòng đời nhân sự › Thử việc. Năm bước từ Chọn đồng nghiệp tới Thông báo kết quả, và mỗi người một thẻ với ngày kết thúc thử việc."),
          why: B("A trial that ends with no decision becomes a yes by default. The board makes sure somebody decides in time.",
                 "Một đợt thử việc kết thúc mà không có quyết định sẽ mặc nhiên thành đồng ý. Bảng đảm bảo có người quyết định kịp lúc."),
          when: B("Two weeks before a trial ends, and whenever colleagues' answers are overdue.",
                  "Hai tuần trước khi thử việc kết thúc, và bất cứ khi nào câu trả lời của đồng nghiệp bị quá hạn."),
          prereq: B("Lifecycle access. The manager decides first, then HR and leadership review.",
                    "Quyền Vòng đời nhân sự. Quản lý quyết định trước, rồi nhân sự và lãnh đạo xem xét."),
          mistakes: [
            B("Deciding before colleagues have answered. Their view is part of the record the decision rests on.",
              "Quyết định trước khi đồng nghiệp trả lời. Ý kiến của họ là một phần của hồ sơ mà quyết định dựa vào."),
            B("Letting the end date pass. Ending within a week is on the board so that does not happen.",
              "Để ngày kết thúc trôi qua. Mục Kết thúc trong vòng một tuần có trên bảng để điều đó không xảy ra."),
          ],
        },
      },
      {
        id: "growth", icon: "sprout", mins: 5, after: "probation",
        roles: ["hr"],
        search: B("growth plan, coaching, improvement plan, objectives at risk", "kế hoạch phát triển, kèm cặp, kế hoạch cải thiện, mục tiêu có rủi ro"),
        title: B("Growth plans", "Kế hoạch phát triển"),
        desc: B("When someone is struggling: a conversation first, coaching, then a written plan with objectives and dates.",
                "Khi một người gặp khó khăn: trao đổi trước, kèm cặp, rồi một kế hoạch bằng văn bản với mục tiêu và mốc thời gian."),
        outline: {
          what: B("Lifecycle › Growth plans. Four steps — Asked, Coaching, Plan running, Decision — and each plan's objectives marked on track or at risk.",
                  "Vòng đời nhân sự › Kế hoạch phát triển. Bốn bước — Đã yêu cầu, Kèm cặp, Kế hoạch đang chạy, Quyết định — và mục tiêu của mỗi kế hoạch được đánh dấu đúng hướng hay có rủi ro."),
          why: B("Help that is written down is help that can be shown. It is fair to the person and to the company.",
                 "Sự hỗ trợ được ghi lại là sự hỗ trợ có thể chứng minh. Điều đó công bằng cho cả người lao động lẫn công ty."),
          when: B("When a manager asks HR about someone in their team.",
                  "Khi một quản lý hỏi nhân sự về một người trong nhóm của mình."),
          prereq: B("A growth-plan role. The tab is kept to the few people who hold one.",
                    "Vai trò kế hoạch phát triển. Tab chỉ dành cho số ít người có vai trò đó."),
          mistakes: [
            B("Jumping to a plan before the conversation. The first step is a conversation, and many stop there.",
              "Nhảy thẳng tới kế hoạch trước khi trao đổi. Bước đầu tiên là một cuộc trao đổi, và nhiều trường hợp dừng ở đó."),
          ],
        },
      },
      {
        id: "contractends", icon: "file-signature", mins: 5, after: null,
        roles: ["hr", "officer"],
        search: B("contract ending, renew a contract, extend a contract, make permanent", "hợp đồng sắp hết hạn, gia hạn hợp đồng, chuyển chính thức"),
        title: B("Contracts ending", "Hợp đồng sắp hết hạn"),
        desc: B("Contracts that end soon, decided in good time: make it permanent, extend it, or let it end.",
                "Các hợp đồng sắp hết hạn, được quyết định sớm: chuyển chính thức, gia hạn, hoặc để hết hạn."),
        outline: {
          what: B("Lifecycle › Contracts. Four steps — Running, Decision needed, Being agreed, Decided — and a card per contract ending soon.",
                  "Vòng đời nhân sự › Hợp đồng. Bốn bước — Đang hiệu lực, Cần quyết định, Đang chờ đồng ý, Đã quyết định — và mỗi hợp đồng sắp hết hạn một thẻ."),
          why: B("A contract that ends with nobody deciding stops the person's pay in the middle of a month.",
                 "Một hợp đồng hết hạn mà không ai quyết định sẽ làm dừng lương của người đó giữa tháng."),
          when: B("Sixty days before a contract ends, when the board starts counting it.",
                  "Sáu mươi ngày trước khi hợp đồng hết hạn, lúc bảng bắt đầu đếm nó."),
          prereq: B("Lifecycle access. Raising the decision needs a contract with an end date.",
                    "Quyền Vòng đời nhân sự. Muốn nêu quyết định thì hợp đồng phải có ngày kết thúc."),
          mistakes: [
            B("Leaving Nobody has decided above zero at month end. That person may drop out of the next pay run.",
              "Để mục Chưa ai quyết định lớn hơn không vào cuối tháng. Người đó có thể rơi khỏi đợt lương kế tiếp."),
          ],
        },
      },
      {
        id: "exits", icon: "log-out", star: true, mins: 8, after: null,
        roles: ["hr", "officer"],
        search: B("someone is leaving, exit, resignation, clearance, final settlement, last day", "nghỉ việc, thôi việc, đơn nghỉ việc, bàn giao, quyết toán, ngày làm cuối"),
        title: B("Exits and final settlement", "Nghỉ việc và quyết toán"),
        desc: B("From resignation to the last payment: notice, four desks signing off, handover, and the final settlement.",
                "Từ đơn nghỉ việc tới khoản chi cuối cùng: thời gian báo trước, bốn phòng ban xác nhận bàn giao, bàn giao công việc, và quyết toán."),
        outline: {
          what: B("Lifecycle › Exits. Four steps — Working their notice, Signing off, Ready to settle, Settled — and IT, HR, Finance and Admin signing off each leaver.",
                  "Vòng đời nhân sự › Nghỉ việc. Bốn bước — Đang trong thời gian báo trước, Đang xác nhận bàn giao, Sẵn sàng quyết toán, Đã quyết toán — và IT, Nhân sự, Tài chính, Quản trị viên xác nhận cho mỗi người nghỉ."),
          why: B("The last payment has a legal deadline and one chance to be right. It waits until everything the company lent has come back.",
                 "Khoản chi cuối có thời hạn pháp lý và chỉ một lần làm đúng. Nó chờ cho tới khi mọi thứ công ty cho mượn đã được trả lại."),
          when: B("From the day a resignation is accepted to the day the settlement is closed.",
                  "Từ ngày đơn nghỉ việc được chấp nhận tới ngày quyết toán được chốt."),
          prereq: B("Lifecycle access. The settlement itself is paid from Pay Run › Settle.",
                    "Quyền Vòng đời nhân sự. Bản thân khoản quyết toán được chi từ Đợt lương › Quyết toán."),
          mistakes: [
            B("Closing the settlement with a desk still open. The final settlement waits for all four, and says which one.",
              "Chốt quyết toán khi còn một phòng ban chưa xác nhận. Quyết toán cuối cùng chờ đủ cả bốn, và nói rõ phòng ban nào."),
            B("Leaving the leaver in the monthly pay run too. They are then paid twice.",
              "Vẫn để người nghỉ trong đợt lương tháng. Khi đó họ được trả hai lần."),
          ],
        },
      },
    ],
  },

  /* ---------------------------------------------------------------------------
     LEARN REFRESH step 4 — THE WORKFORCE LINE. A manager's week, in order: a
     day in Workforce, the time and leave behind it, and closing the week so
     payroll can use it.
     ------------------------------------------------------------------------ */
  workforce: {
    stations: [
      {
        id: "wftoday", icon: "sun", mins: 6, after: null,
        roles: ["officer", "hr"],
        search: B("today, who is in, who is late, needs you, approve clean overtime", "hôm nay, ai có mặt, ai đi trễ, cần bạn, duyệt tăng ca sạch"),
        title: B("A day in Workforce", "Một ngày ở Lực lượng lao động"),
        desc: B("Who is in today, and the Needs you panel: everything waiting for you, and one press for the overtime that is clean.",
                "Hôm nay ai có mặt, và khung Cần bạn: mọi việc đang chờ bạn, và một lần bấm cho phần tăng ca sạch."),
        outline: {
          what: B("Workforce › Today: who is on shift, late, not started, checked out or on leave. The Needs you panel sits beside every Workforce tab.",
                  "Lực lượng lao động › Hôm nay: ai đang theo ca, trễ, chưa bắt đầu, đã về hoặc đang nghỉ phép. Khung Cần bạn nằm cạnh mọi tab của Lực lượng lao động."),
          why: B("Time becomes pay. What a manager does not look at today turns into a flag at the end of the week.",
                 "Giờ công trở thành tiền lương. Điều quản lý không xem hôm nay sẽ thành một cờ cảnh báo vào cuối tuần."),
          when: B("Every morning, and after lunch for the late starts.",
                  "Mỗi sáng, và sau giờ trưa cho những người bắt đầu muộn."),
          prereq: B("Attendance officer access. The panel's Organisation view is for the people who look after the whole company.",
                    "Quyền cán bộ chấm công. Chế độ Tổ chức của khung dành cho người phụ trách toàn công ty."),
          mistakes: [
            B("Approving all overtime at once. Only the clean ones go in one press; the rest need a look.",
              "Duyệt tất cả tăng ca một lần. Chỉ phần sạch được duyệt trong một lần bấm; phần còn lại cần xem."),
          ],
        },
      },
      {
        id: "wftime", icon: "clock", mins: 7, after: "wftoday",
        roles: ["officer", "hr"],
        search: B("time, attendance exceptions, time off, leave request, approve overtime", "chấm công, ngoại lệ chấm công, nghỉ phép, đơn nghỉ phép, duyệt tăng ca"),
        title: B("Time, time off and overtime", "Chấm công, nghỉ phép và tăng ca"),
        desc: B("Hours worked and their exceptions, leave waiting for a decision, and overtime to approve inside its limits.",
                "Giờ làm việc và các ngoại lệ, đơn nghỉ phép chờ quyết định, và tăng ca cần duyệt trong giới hạn của nó."),
        outline: {
          what: B("Three Workforce tabs. Time shows hours and exceptions; Time Off holds the leave queue; Overtime holds the approval queue and its limits.",
                  "Ba tab của Lực lượng lao động. Chấm công cho thấy giờ và ngoại lệ; Nghỉ phép giữ hàng chờ nghỉ phép; Tăng ca giữ hàng chờ duyệt và các giới hạn."),
          why: B("Every hour here reaches a payslip. A leave day approved late, or overtime past the legal limit, costs money and trust.",
                 "Mỗi giờ ở đây đều đi vào phiếu lương. Một ngày nghỉ duyệt muộn, hay tăng ca vượt giới hạn luật định, tốn cả tiền lẫn lòng tin."),
          when: B("Through the week, so that closing the week is a check rather than a scramble.",
                  "Trong suốt tuần, để việc chốt tuần chỉ là một bước kiểm tra chứ không phải chạy nước rút."),
          prereq: B("Attendance officer access for Time. Leave and overtime approval follow their own access.",
                    "Quyền cán bộ chấm công cho tab Chấm công. Duyệt nghỉ phép và tăng ca theo quyền riêng."),
          mistakes: [
            B("Ignoring the near-the-limit mark on overtime. Vietnam caps monthly and yearly overtime; the mark is the warning.",
              "Bỏ qua dấu gần giới hạn trên tăng ca. Việt Nam giới hạn tăng ca theo tháng và theo năm; dấu đó là lời cảnh báo."),
            B("Filing leave for someone without telling them. Apply on behalf is for when they cannot, and it is recorded.",
              "Đăng ký nghỉ thay một người mà không báo họ. Đăng ký thay dành cho lúc họ không tự làm được, và việc đó được ghi lại."),
          ],
        },
      },
      {
        id: "wfclose", icon: "lock", star: true, mins: 7, after: "wftime",
        roles: ["officer", "hr"],
        search: B("close the week, lock the week, send to payroll, attendance flags", "chốt tuần, khoá tuần, gửi vào bảng lương, cờ chấm công"),
        title: B("Close the week", "Chốt tuần"),
        desc: B("Clear the week's flags, read what goes to payroll, then lock the week and send it on.",
                "Xử lý các cờ cảnh báo của tuần, đọc những gì chuyển sang bảng lương, rồi khoá tuần và gửi đi."),
        outline: {
          what: B("Workforce › Close. The week's flags, each with Fix or Approve as-is, and a payroll handoff with its hours and one lock button.",
                  "Lực lượng lao động › Chốt kỳ. Các cờ cảnh báo của tuần, mỗi cờ có Điều chỉnh hoặc Phê duyệt nguyên trạng, và phần chuyển giao tiền lương với số giờ và một nút khoá."),
          why: B("Payroll trusts a locked week. Locking it with a flag unanswered sends a question to payroll as if it were a fact.",
                 "Bảng lương tin vào một tuần đã khoá. Khoá khi còn cờ chưa trả lời là gửi một câu hỏi sang bảng lương như thể đó là sự thật."),
          when: B("At the end of every week, before the pay run reads it.",
                  "Cuối mỗi tuần, trước khi đợt lương đọc dữ liệu."),
          prereq: B("An attendance or payroll manager locks a week. Others can read the board.",
                    "Quản lý chấm công hoặc quản lý lương mới khoá được tuần. Người khác chỉ đọc được bảng."),
          mistakes: [
            B("Pressing Approve as-is to get the lock to work. Approve only what really happened; fix the rest.",
              "Bấm Phê duyệt nguyên trạng chỉ để mở khoá nút. Chỉ duyệt những gì thật sự đã diễn ra; hãy điều chỉnh phần còn lại."),
            B("Reopening a locked week without a reason. Reopen… asks for one, and it stays on the record.",
              "Mở lại tuần đã khoá mà không có lý do. Mở lại… sẽ hỏi lý do, và lý do đó được lưu lại."),
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
      delta: B("Net is 855,000 ₫ higher. Overtime rose 900,000 and PIT took 45,000 of it. Insurance did not move at all. It is charged on the insurance base, and overtime does not touch that figure.",
               "Thực nhận cao hơn 855.000 ₫. Tăng ca tăng 900.000 và thuế TNCN lấy đi 45.000 trong đó. Bảo hiểm không nhúc nhích. Nó tính trên mức lương đóng bảo hiểm, mà tăng ca không chạm tới con số đó."),
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
      delta: B("Net falls 57,000 ₫, not 60,000. The deduction grew by 60,000. Insurance comes off before tax, so taxable income fell by the same 60,000 and PIT fell 3,000 with it. Half a percentage point, one employee, every month.",
               "Thực nhận giảm 57.000 ₫, không phải 60.000. Khoản khấu trừ tăng 60.000. Bảo hiểm được trừ trước khi tính thuế, nên thu nhập chịu thuế cũng giảm đúng 60.000 và thuế TNCN giảm theo 3.000. Nửa điểm phần trăm, một nhân viên, mỗi tháng."),
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
      d: B("47 employees · every step on its route said yes",
           "47 nhân viên · mọi bước trên lộ trình đã đồng ý"),
    },
    after: {
      h: B("July 2026", "Tháng 7/2026"),
      big: "612,480,000 ₫",
      d: B("48 employees · Contains overtime: Yes · nothing flagged",
           "48 nhân viên · Có làm thêm giờ: Có · không có gì bị đánh dấu"),
      delta: B("16,370,000 ₫ more, which is 2.7% on one extra employee. That is a comfortable-looking number. Comfortable-looking numbers are where one wrong payslip hides best. Hùng's 3,100,000 ₫ of extra overtime sits inside this total. Nothing on the request says so: Payobook does not flag a jump on last month.",
               "Nhiều hơn 16.370.000 ₫, tức 2,7% với thêm một nhân viên. Đó là con số trông rất dễ chịu. Những con số dễ chịu chính là nơi một phiếu lương sai ẩn mình tốt nhất: phần tăng ca thêm 3.100.000 ₫ của Hùng nằm gọn trong con số tổng này, và yêu cầu phê duyệt không hề nói ra điều đó — Payobook không đánh dấu một mức tăng so với tháng trước."),
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
    id: "L1", station: "runpayroll", mins: 9,
    title: B("Run — your first pay run", "Chạy lương — đợt lương đầu tiên của bạn"),
    goal: B("Make one month of draft payslips for one pay scheme, and know exactly what you have and have not just done.",
            "Tạo phiếu lương nháp của một tháng cho một chương trình lương, và biết chính xác bạn vừa làm gì và chưa làm gì."),
    steps: [
      {
        screen: "runpayroll", anchor: "pw-rail",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("This tab makes a month of pay", "Tab này tạo ra một tháng lương"),
        body: B("<b>Pay Run › Run</b> takes one pay scheme and one month and computes a <b>draft</b> payslip for everyone that scheme pays. Nothing is paid here. The steps at the top show where you are: <b>Select period</b>, <b>Pay data</b>, <b>Compute</b>, <b>Review exceptions</b>. Pay data only appears when the scheme reads a spreadsheet — without one, there are three steps.",
                "<b>Đợt lương › Chạy lương</b> nhận một chương trình lương và một tháng, rồi tính phiếu lương <b>nháp</b> cho mọi người mà chương trình đó trả lương. Chưa có gì được chi ở đây. Các bước ở trên cho biết bạn đang ở đâu: <b>Chọn kỳ lương</b>, <b>Dữ liệu lương</b>, <b>Tính lương</b>, <b>Soát ngoại lệ</b>. Bước Dữ liệu lương chỉ xuất hiện khi chương trình lương đọc một bảng tính — không có thì chỉ có ba bước."),
      },
      {
        screen: "runpayroll", anchor: "pw-scheme",
        kicker: B("Step 1", "Bước 1"),
        title: B("Pick the pay scheme first", "Chọn chương trình lương trước tiên"),
        body: B("\"Pay run for\" lists this company's pay schemes, grouped by kind: <b>End of month</b>, <b>Regular payroll</b>, <b>Mid-month advance</b>, <b>Final settlement</b>. Each card says how many people it covers and its last run. Picking a scheme picks the <b>rulebook</b> every payslip in this run is computed by. Choose the wrong one and every number is wrong in the same direction — the hardest error to spot.",
                "\"Đợt lương cho\" liệt kê các chương trình lương của công ty, nhóm theo loại: <b>Cuối tháng</b>, <b>Kỳ lương thường</b>, <b>Tạm ứng giữa tháng</b>, <b>Quyết toán thôi việc</b>. Mỗi thẻ ghi bao nhiêu người được áp dụng và đợt gần nhất. Chọn chương trình lương là chọn <b>bộ quy tắc</b> sẽ tính mọi phiếu lương trong đợt này — chọn sai thì mọi con số sai theo cùng một hướng, loại lỗi khó phát hiện nhất."),
        tip: B("F&B already has a July run — it was sent back and is waiting to be fixed. Starting a second one would make Payobook say \"Payroll already exists\".",
               "F&B đã có đợt lương tháng 7 — nó bị trả lại và đang chờ được sửa. Bắt đầu thêm một đợt nữa thì Payobook sẽ báo \"Payroll already exists\" (đã có bảng lương)."),
      },
      {
        screen: "runpayroll", anchor: "pw-scope",
        kicker: B("Step 1", "Bước 1"),
        title: B("Which month, and what to call it", "Tháng nào, và gọi đợt này là gì"),
        body: B("The <b>period</b> is the month being paid — From and To. The <b>batch name</b> is what everybody after you will search for, so make it say the scheme and the month.",
                "<b>Kỳ lương</b> là tháng đang được trả — Từ và Đến. <b>Tên đợt</b> là thứ mọi người sau bạn sẽ dùng để tìm, nên hãy để nó nói rõ chương trình lương và tháng."),
      },
      {
        screen: "runpayroll", anchor: "pw-summary",
        kicker: B("Before you act", "Trước khi thao tác"),
        title: B("Read the scope before you go on", "Đọc phạm vi trước khi đi tiếp"),
        body: B("Company, currency and pay scheme, and one promise: <b>only the people this scheme pays are affected</b>. If the scheme is not the one you meant, this is the cheapest moment to change it. Because this scheme reads a spreadsheet, the button says <b>Add pay data</b> rather than Compute.",
                "Công ty, tiền tệ và chương trình lương, cùng một cam kết: <b>chỉ những người thuộc chương trình lương này bị ảnh hưởng</b>. Nếu chương trình lương không đúng ý bạn, đây là lúc đổi rẻ nhất. Vì chương trình này đọc một bảng tính nên nút ghi là <b>Thêm dữ liệu lương</b> chứ không phải Tính."),
      },
      {
        screen: "runpayroll", anchor: "pw-paymode",
        kicker: B("Step 2 · Pay data", "Bước 2 · Dữ liệu lương"),
        title: B("What should these values do?", "Các giá trị này dùng để làm gì?"),
        body: B("Load this month's file, then answer one question. <b>Update Payobook</b> saves the values to employee and contract records and uses them from now on. <b>This run only</b> uses them once and changes nothing in Payobook — right for a one-off bonus or a correction. Import asks the same question; the answer means the same thing in both places.",
                "Tải tệp của tháng này lên, rồi trả lời một câu hỏi. <b>Cập nhật Payobook</b> lưu các giá trị vào hồ sơ nhân viên và hợp đồng, và dùng chúng từ nay về sau. <b>Chỉ đợt này</b> dùng chúng một lần và không thay đổi gì trong Payobook — hợp với một khoản thưởng một lần hoặc một lần sửa. Màn hình Nhập cũng hỏi đúng câu này; câu trả lời có cùng một nghĩa ở cả hai nơi."),
        tip: B("No file this month? If the scheme reads a connected system, \"Update records\" brings it up to date first. Payobook also syncs connected systems on its own before it computes.",
               "Tháng này không có tệp? Nếu chương trình lương đọc từ một hệ thống đã kết nối, nút \"Cập nhật hồ sơ\" sẽ đồng bộ trước. Payobook cũng tự đồng bộ các hệ thống đã kết nối trước khi tính."),
      },
      {
        screen: "runpayroll", anchor: "pw-coverage",
        kicker: B("Step 2 · Pay data", "Bước 2 · Dữ liệu lương"),
        title: B("Coverage: what the file feeds", "Mức bao phủ: tệp cung cấp những gì"),
        body: B("\"3 of 3 spreadsheet components are fed by this file.\" A component the file does not feed uses its fallback value for this run. So a missing column is not an error message; it is a quiet default. And anyone in the file who is not in Payobook yet is <b>listed, not paid</b>.",
                "\"3 trên 3 thành phần bảng tính được lấy từ tệp này.\" Thành phần nào tệp không cung cấp sẽ dùng giá trị mặc định cho đợt này — nên thiếu một cột không phải là thông báo lỗi, mà là một giá trị mặc định âm thầm. Và ai có trong tệp mà chưa có trong Payobook sẽ <b>được liệt kê, không được trả lương</b>."),
      },
      {
        screen: "runpayroll", anchor: "pw-result",
        kicker: B("The action", "Thao tác chính"),
        title: B("Compute — what actually happened", "Tính — điều gì thực sự đã diễn ra"),
        body: B("Continue made one draft payslip for each of the 48 people the scheme pays — gross, allowances, BHXH/BHYT/BHTN, thuế TNCN, net — and printed the run's net total. Three numbers under it: <b>Payslips</b>, <b>Computed</b> and <b>Need review</b>.",
                "Nút Tiếp tục đã tạo một phiếu lương nháp cho từng người trong 48 người mà chương trình lương trả — tổng thu nhập, phụ cấp, BHXH/BHYT/BHTN, thuế TNCN, thực nhận — và in ra tổng thực nhận của đợt. Bên dưới là ba con số: <b>Phiếu lương</b>, <b>Đã tính</b> và <b>Cần xem xét</b>."),
        consequence: B("Affects July 2026 for the people this scheme pays — 48 draft payslips in one draft run. Reversible: <b>yes</b> — drafts can be recomputed or deleted, and nothing is paid or sent. Nobody sees anything until the run is Done. Verify first: the pay scheme and the month, and which answer you gave to \"What should these values do?\".",
                       "Ảnh hưởng: tháng 7/2026 của những người thuộc chương trình lương này — 48 phiếu lương nháp trong một đợt nháp. Hoàn tác: <b>được</b> — bản nháp có thể tính lại hoặc xoá, và chưa có gì được chi hay gửi đi. Không ai thấy gì cho tới khi đợt lương Hoàn tất. Kiểm tra trước: chương trình lương và tháng, và câu trả lời bạn đã chọn cho \"Các giá trị này dùng để làm gì?\"."),
      },
      {
        screen: "runpayroll", anchor: "pw-missing",
        kicker: B("Reading results", "Đọc kết quả"),
        title: B("Need review: 2 — and what the 2 are", "Cần xem xét: 2 — và 2 đó là gì"),
        body: B("Need review adds up three things. Payslips that came out at zero or below. People Payobook could not make a payslip for. And people in the file who are not in Payobook yet. Here, <b>Lý Thị Hồng</b> is in the file and not in Payobook — listed, not paid. Nobody is created from a pay data file: <b>Add these people</b>, and her pay comes through on the next run.",
                "Cần xem xét cộng ba thứ: phiếu lương có thực nhận bằng không hoặc âm, những người Payobook không tạo được phiếu lương, và những người có trong tệp mà chưa có trong Payobook. Ở đây, <b>Lý Thị Hồng</b> có trong tệp mà chưa có trong Payobook — được liệt kê, không được trả lương. Không ai được tạo ra từ tệp dữ liệu lương: hãy bấm <b>Thêm những người này</b>, lương của cô ấy sẽ có ở đợt kế tiếp."),
      },
      {
        screen: "runpayroll", anchor: "pw-exceptions",
        kicker: B("The judgement", "Phần cần phán đoán"),
        title: B("One exception that is fine, and one thing nothing flagged", "Một ngoại lệ hoàn toàn ổn, và một điều không gì đánh dấu"),
        body: B("<b>Hoàng Văn Nam</b>: \"Not employed yet in this period — contract starts 2026-08-01.\" That is correct — nothing to fix. Now the part Payobook does <b>not</b> do: Trần Văn Hùng's overtime is 4,200,000 ₫ against 1,100,000 ₫ in June — 382%. No list here mentions it. It may be a real peak week, or 4.6 hours typed as 46. Only you can tell, by checking the timesheet.",
                "<b>Hoàng Văn Nam</b>: \"Chưa làm việc trong kỳ này — hợp đồng bắt đầu ngày 2026-08-01.\" Điều đó đúng — không có gì để sửa. Giờ tới phần Payobook <b>không</b> làm: tăng ca của Trần Văn Hùng là 4.200.000 ₫ so với 1.100.000 ₫ của tháng 6 — bằng 382%. Không danh sách nào ở đây nhắc tới nó. Có thể đó là một tuần cao điểm thật, cũng có thể là 4,6 giờ bị gõ thành 46. Chỉ bạn mới phân biệt được, bằng cách đối chiếu bảng chấm công."),
        tip: B("Payobook flags what it could not pay. A big jump on last month is yours to notice.",
               "Payobook đánh dấu những gì nó không trả được. Một mức tăng lớn so với tháng trước là việc của bạn phải nhận ra."),
      },
      {
        screen: "payruns", anchor: "rep-pipeline",
        kicker: B("Where it goes", "Đi về đâu"),
        title: B("Open Payroll, then Submit for approval", "Mở bảng lương, rồi Gửi để phê duyệt"),
        body: B("<b>Open Payroll →</b> takes you to <b>Pay Run › Runs</b>, where the run sits in <b>Draft</b>. <b>Submit for approval</b> sends it along the route your company drew in the Approval Matrix — here Payroll check, then HR lead review, then Finance approval. While it waits, its payslips are frozen. A step can <b>send it back</b> (to Draft, with a note) or <b>turn it down</b> (the run is cancelled).",
                "<b>Mở bảng lương →</b> đưa bạn tới <b>Đợt lương › Các đợt lương</b>, nơi đợt lương nằm ở cột <b>Nháp</b>. <b>Gửi để phê duyệt</b> đưa nó đi theo lộ trình mà công ty bạn vẽ trong Ma trận phê duyệt — ở đây là Kiểm tra bảng lương, rồi Trưởng nhân sự soát xét, rồi Tài chính phê duyệt. Trong lúc chờ, các phiếu lương bị giữ nguyên. Một bước có thể <b>trả lại</b> (về Nháp, kèm ghi chú) hoặc <b>từ chối</b> (đợt lương bị huỷ)."),
        moment: { kind: "pipeline", chain: "payrun" },
      },
    ],
    quiz: {
      question: B("You computed July and then spot that one employee's overtime input is wrong. The run is still a draft. What is the safest next step?",
                  "Bạn đã tính lương tháng 7, rồi phát hiện dữ liệu tăng ca của một nhân viên bị sai. Đợt lương vẫn là bản nháp. Bước an toàn nhất là gì?"),
      options: [
        {
          text: B("Edit the net amount directly on the payslip", "Sửa thẳng số thực nhận trên phiếu lương"),
          correct: false,
          explanation: B("Let's rethink that. Editing the result breaks the trail. The payslip no longer agrees with the data behind it, and the next recompute quietly undoes your fix.",
                         "Hãy nghĩ lại một chút. Sửa kết quả làm đứt vết dữ liệu. Phiếu lương không còn khớp với dữ liệu phía sau, và lần tính lại kế tiếp âm thầm xoá sửa đổi của bạn."),
        },
        {
          text: B("Fix the overtime input, then compute the draft again", "Sửa dữ liệu tăng ca, rồi tính lại bản nháp"),
          correct: true,
          explanation: B("Exactly. Drafts exist for this. Correct the input, then compute again. Every line that depends on it — gross, thuế TNCN, net — corrects itself.",
                         "Chính xác. Bản nháp sinh ra để làm việc đó. Sửa đầu vào, rồi tính lại. Mọi dòng phụ thuộc vào nó — tổng thu nhập, thuế TNCN, thực nhận — tự đúng theo."),
        },
        {
          text: B("Submit for approval now and correct it next month", "Cứ gửi phê duyệt, tháng sau sửa"),
          correct: false,
          explanation: B("Let's rethink that. It turns a thirty-second fix into a retro line next month — and an employee paid the wrong amount today, which is the part they will remember.",
                         "Hãy nghĩ lại một chút. Việc đó biến một sửa đổi ba mươi giây thành một dòng hồi tố tháng sau — và một nhân viên bị trả sai ngay hôm nay, đó mới là điều họ nhớ."),
        },
      ],
    },
  },

  L2: {
    id: "L2", station: "payruns", mins: 8,
    title: B("The board, and the road to Done", "Bảng đợt lương, và đường tới Hoàn tất"),
    goal: B("Read Pay Run › Runs the way payroll week needs it read: what state each run is in, who it is waiting for, and what Reject really does.",
            "Đọc Đợt lương › Các đợt lương theo đúng cách tuần tính lương cần: mỗi đợt đang ở trạng thái nào, đang chờ ai, và Từ chối thực sự làm gì."),
    steps: [
      {
        screen: "payruns", anchor: "pk-kpis",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Five numbers, and one of them is yours", "Năm con số, và một con số là của bạn"),
        body: B("<b>Pay runs</b> (every run, rejected ones too), <b>In pipeline</b> (Draft plus Waiting for approval), <b>Awaiting your approval</b>, <b>Completed</b>, and <b>Net paid (done)</b> — in the company's own currency only. The third is the one about you: runs whose route is waiting on you right now.",
                "<b>Đợt lương</b> (mọi đợt, kể cả đợt bị từ chối), <b>Đang xử lý</b> (Nháp cộng Chờ phê duyệt), <b>Chờ bạn phê duyệt</b>, <b>Hoàn tất</b>, và <b>Đã chi (hoàn tất)</b> — chỉ tính bằng tiền tệ của công ty. Con số thứ ba là con số về bạn: những đợt mà lộ trình đang chờ đúng bạn lúc này."),
      },
      {
        screen: "payruns", anchor: "pk-steps",
        kicker: B("Reading the board", "Đọc bảng"),
        title: B("Three states, not three months", "Ba trạng thái, không phải ba tháng"),
        body: B("<b>01 Draft</b>, <b>02 Waiting for approval</b>, <b>03 Done</b>, each with its count. A flag shows when something needs you: \"1 sent back to be fixed\", \"1 waiting on you\". Press a step to narrow the board to it. A column is a state — July and June can sit in the same one.",
                "<b>01 Nháp</b>, <b>02 Chờ phê duyệt</b>, <b>03 Hoàn tất</b>, mỗi bước kèm số lượng và một dấu khi có việc cần bạn: \"1 bị trả lại để sửa\", \"1 đang chờ bạn\". Bấm một bước để thu hẹp bảng về bước đó. Một cột là một trạng thái — tháng 7 và tháng 6 có thể cùng nằm trong một cột."),
      },
      {
        screen: "payruns", anchor: "pk-route",
        kicker: B("Who is holding it", "Ai đang giữ nó"),
        title: B("A waiting run names its step and its person", "Đợt đang chờ ghi rõ bước và người"),
        body: B("\"<b>HR lead review · With Đặng Thu Hà</b>.\" That line is the answer to \"who do I chase\" — read from the run's approval route, not from anybody's memory. The route is whatever your company drew; the run's own page says the same in one sentence.",
                "\"<b>Trưởng nhân sự soát xét · Đang ở Đặng Thu Hà</b>.\" Dòng đó là câu trả lời cho \"tôi phải hỏi ai\" — đọc từ lộ trình phê duyệt của đợt lương, không phải từ trí nhớ của ai. Lộ trình là do công ty bạn vẽ; trang của chính đợt lương cũng nói điều đó trong một câu."),
        tip: B("If a run's own page says \"These figures do not add up\", gross less deductions is not the take-home pay. A component is usually set to the wrong thing — open the pay scheme and check Component treatment before you send it in.",
               "Nếu trang của một đợt lương báo \"These figures do not add up\" (các con số không khớp), thì tổng thu nhập trừ khấu trừ không bằng thực nhận. Thường là một thành phần bị đặt sai loại — hãy mở chương trình lương và kiểm tra phần Component treatment (cách xử lý thành phần) trước khi gửi đi."),
      },
      {
        screen: "payruns", anchor: "pk-card",
        kicker: B("Sent back", "Bị trả lại"),
        title: B("A run that came back sits in Draft with its note", "Đợt bị trả lại nằm ở Nháp kèm ghi chú"),
        body: B("F&B's July run was <b>sent back</b> by Đặng Thu Hà. Her note: \"NV0203 — overtime reads 46 hours for the week; the timesheet says 4.6.\" It is a draft again, its payslips editable. Fix what the note says, compute again, and <b>Submit for approval</b> — the route starts again from its first step.",
                "Đợt lương tháng 7 của F&B đã bị Đặng Thu Hà <b>trả lại</b>: \"NV0203 — tăng ca ghi 46 giờ trong tuần; bảng chấm công ghi 4,6.\" Nó lại là bản nháp, các phiếu lương sửa được. Hãy sửa đúng điều ghi chú nói, tính lại, rồi <b>Gửi để phê duyệt</b> — lộ trình bắt đầu lại từ bước đầu tiên."),
      },
      {
        screen: "payruns", anchor: "pk-card-actions",
        kicker: B("The card", "Thẻ đợt lương"),
        title: B("A card only offers what its state allows", "Thẻ chỉ mở ra những gì trạng thái cho phép"),
        body: B("Draft: <b>Submit for approval</b> and <b>Reject</b>. Waiting, and it is your turn: <b>Open the approval</b> — the decision happens in Home › Approvals, not here. Waiting on someone else: just who it is with. Done: <b>Pay &amp; Deliver</b>, <b>Report</b>, <b>Excel</b>, <b>Journals</b>, <b>Payments</b>.",
                "Nháp: <b>Gửi để phê duyệt</b> và <b>Từ chối</b>. Đang chờ, và đến lượt bạn: <b>Mở phê duyệt</b> — quyết định diễn ra ở Trang chủ › Phê duyệt, không phải ở đây. Đang chờ người khác: chỉ ghi đang ở chỗ ai. Hoàn tất: <b>Chi trả &amp; gửi phiếu</b>, <b>Báo cáo</b>, <b>Excel</b>, <b>Bút toán</b>, <b>Thanh toán</b>."),
      },
      {
        screen: "payruns", anchor: "rep-pipeline",
        kicker: B("The road", "Con đường"),
        title: B("Draft, Waiting for approval, Done", "Nháp, Chờ phê duyệt, Hoàn tất"),
        body: B("Every run takes the same road. <b>Submit for approval</b> moves it to Waiting and freezes its payslips. The last step's yes makes it <b>Done</b> — and only then can it be paid. Two ways off the road: <b>sent back</b> returns it to Draft with a note; <b>turned down</b> (in the inbox) or <b>rejected</b> (from the board) cancels it.",
                "Đợt nào cũng đi cùng một con đường. <b>Gửi để phê duyệt</b> đưa nó sang Chờ phê duyệt và giữ nguyên các phiếu lương. Cái gật đầu ở bước cuối biến nó thành <b>Hoàn tất</b> — và chỉ khi đó nó mới được chi. Có hai lối rẽ: <b>trả lại</b> đưa nó về Nháp kèm ghi chú; <b>từ chối</b> (trong hộp phê duyệt) hoặc <b>Từ chối</b> (trên bảng) sẽ huỷ nó."),
        moment: { kind: "pipeline", chain: "payrun" },
      },
      {
        screen: "payruns", anchor: "pk-rejected",
        kicker: B("The hard part", "Phần khó"),
        title: B("Reject is final for that run", "Từ chối là dứt điểm với đợt đó"),
        body: B("Reject asks once, on the card — \"Every payslip in this batch is cancelled.\" — <b>Keep it</b> or <b>Reject run</b>. The run and all its payslips are cancelled, its open approval is withdrawn, and it moves to the folded <b>Rejected pay runs</b> list. It does not come back: you start a new run. Use it for a run that should not exist, like the one here made twice by mistake.",
                "Nút Từ chối hỏi lại một lần, ngay trên thẻ — \"Mọi phiếu lương trong đợt này sẽ bị huỷ.\" — <b>Giữ lại</b> hoặc <b>Từ chối đợt lương</b>. Đợt lương và mọi phiếu lương của nó bị huỷ, yêu cầu phê duyệt đang mở được rút lại, và nó chuyển xuống danh sách thu gọn <b>Đợt lương bị từ chối</b>. Nó không quay lại: bạn bắt đầu một đợt mới. Hãy dùng nó cho một đợt không nên tồn tại, như đợt ở đây bị tạo trùng."),
        consequence: B("Affects the whole run and every payslip in it, which are cancelled together. Reversible: <b>no</b> — a rejected run stays rejected; the way on is a new run. Nothing was paid. Verify first: that the run should not exist at all. If it only needs fixing, ask the person whose turn it is to send it back instead.",
                       "Ảnh hưởng cả đợt lương và mọi phiếu lương trong đó, cùng bị huỷ một lượt. Hoàn tác: <b>không</b> — đợt đã bị từ chối thì giữ nguyên như vậy; muốn đi tiếp thì tạo đợt mới. Chưa có gì được chi. Kiểm tra trước: đợt này thực sự không nên tồn tại. Nếu nó chỉ cần sửa, hãy nhờ người đến lượt duyệt trả lại nó."),
      },
      {
        screen: "payruns", anchor: "pk-divchips",
        kicker: B("Scoping", "Phạm vi"),
        title: B("The division chips narrow the cards", "Các chip bộ phận thu hẹp các thẻ"),
        body: B("\"All divisions\" or one division. The chips filter the cards; the numbers above still count the whole board. When a board holds more than one currency, it says so, shows each run in its own money, and adds up only the company's currency.",
                "\"Tất cả bộ phận\" hoặc một bộ phận. Các chip lọc các thẻ; các con số phía trên vẫn đếm toàn bộ bảng. Khi bảng có nhiều loại tiền tệ, nó nói rõ, hiện mỗi đợt bằng đúng loại tiền của đợt đó, và chỉ cộng dồn tiền tệ của công ty."),
      },
      {
        screen: "payruns", anchor: "pk-card-actions",
        kicker: B("The far end", "Đầu bên kia"),
        title: B("Done unlocks the money, and locks the run", "Hoàn tất mở khoá tiền, và khoá đợt lương"),
        body: B("Only a Done run offers <b>Pay &amp; Deliver</b> — the bank file and the payslips — plus the report, the journals and the payments. Those buttons appear exactly when every step on the route has said yes. After Done, a correction is a retro line, never an edit.",
                "Chỉ đợt đã Hoàn tất mới có <b>Chi trả &amp; gửi phiếu</b> — tệp ngân hàng và phiếu lương — cùng báo cáo, bút toán và thanh toán. Các nút đó xuất hiện đúng lúc mọi bước trên lộ trình đã đồng ý. Sau Hoàn tất, mọi hiệu chỉnh là một dòng hồi tố, không bao giờ là sửa trực tiếp."),
      },
    ],
    quiz: {
      question: B("A run you prepared has been Waiting for approval at HR lead review for two days, and payday is {{payDay}}. What do you do?",
                  "Một đợt lương bạn lập đã Chờ phê duyệt ở bước Trưởng nhân sự soát xét hai ngày, và ngày trả lương là {{payDay}}. Bạn làm gì?"),
      options: [
        {
          text: B("Put it back to draft and compute it again so it moves", "Đưa nó về nháp và tính lại để nó đi tiếp"),
          correct: false,
          explanation: B("Let's rethink that. A waiting run cannot be put back to draft from the board — Payobook says to reject it or ask the approver to send it back. And computing again would not move it past a step; only a decision does.",
                         "Hãy nghĩ lại một chút. Một đợt đang chờ không thể đưa về nháp từ bảng — Payobook sẽ bảo bạn từ chối nó hoặc nhờ người duyệt trả lại. Và tính lại cũng không đưa được nó qua một bước; chỉ có quyết định mới làm được."),
        },
        {
          text: B("Ask the person the card names — the route says whose turn it is", "Hỏi người mà thẻ ghi tên — lộ trình cho biết đến lượt ai"),
          correct: true,
          explanation: B("Yes. \"HR lead review · With Đặng Thu Hà\" tells you exactly who can move it. Asking the right person is the only thing that shortens the wait, and the fastest way to find out if they are stuck on something you can fix.",
                         "Đúng vậy. \"Trưởng nhân sự soát xét · Đang ở Đặng Thu Hà\" cho bạn biết chính xác ai có thể đẩy nó đi. Hỏi đúng người là cách duy nhất rút ngắn thời gian chờ, và là cách nhanh nhất để biết họ đang vướng điều gì mà bạn gỡ được."),
        },
        {
          text: B("Reject it and start a clean run", "Từ chối nó rồi chạy lại một đợt sạch"),
          correct: false,
          explanation: B("Let's rethink that. Reject cancels the run and every payslip in it, and throws away the review already done. The new run then travels the whole route again, which is slower, not faster.",
                         "Hãy nghĩ lại một chút. Từ chối sẽ huỷ đợt lương và mọi phiếu lương trong đó, bỏ phí phần soát xét đã làm, và đợt mới lại phải đi hết lộ trình từ đầu — chậm hơn, chứ không nhanh hơn."),
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
        body: B("The selector at the top names the run. Every number, every step and every payslip under it belongs to that run — so comparing two months means changing this control, not scrolling.",
                "Ô chọn ở trên cùng cho biết đợt lương nào. Mọi con số, mọi bước và mọi phiếu lương bên dưới đều thuộc đợt đó — nên muốn so hai tháng là đổi ô này, không phải cuộn xuống."),
      },
      {
        screen: "payslips", anchor: "ps-kpis",
        kicker: B("The numbers", "Các con số"),
        title: B("Need review means take-home pay at zero or below", "Cần xem xét nghĩa là thực nhận bằng không hoặc âm"),
        body: B("<b>Payslips</b> 48, <b>Need review</b>, <b>Gross total</b>, <b>Net total</b>. Say Need review plainly: it counts payslips whose take-home pay came out at <b>zero or below</b>. Here it is 0 — which means nobody is paid nothing, not that the run has been checked. Choose what to read yourself.",
                "<b>Phiếu lương</b> 48, <b>Cần xem xét</b>, <b>Tổng thu nhập</b>, <b>Tổng thực nhận</b>. Hãy nói rõ Cần xem xét: nó đếm những phiếu lương có thực nhận bằng <b>không hoặc âm</b>. Ở đây là 0 — nghĩa là không ai bị trả bằng không, chứ không có nghĩa đợt lương đã được kiểm tra. Hãy tự chọn những phiếu cần đọc."),
      },
      {
        screen: "payslips", anchor: "ps-chips",
        kicker: B("Where they are", "Chúng đang ở đâu"),
        title: B("Approved together, as a pay run", "Được duyệt cùng nhau, theo cả đợt lương"),
        body: B("<b>01 Draft</b>, <b>02 Waiting for approval</b>, <b>03 Done</b>. All 48 are Waiting, because their run is. A payslip never moves on its own: payslips are approved together, as a pay run — every one of them moves when the run does.",
                "<b>01 Nháp</b>, <b>02 Chờ phê duyệt</b>, <b>03 Hoàn tất</b>. Cả 48 phiếu đều đang chờ, vì đợt lương của chúng đang chờ. Một phiếu lương không bao giờ tự đi riêng: các phiếu được duyệt cùng nhau, theo cả đợt lương — đợt đi thì mọi phiếu cùng đi."),
      },
      {
        screen: "payslips", anchor: "ps-status",
        kicker: B("One payslip", "Một phiếu lương"),
        title: B("Its position, and no button to change it", "Vị trí của nó, và không có nút nào để đổi"),
        body: B("The stepper shows where this payslip is — Draft, Waiting for approval, Done — and it has no button, on purpose. While the run waits, its payslips are frozen, so the numbers a person approves are the numbers that get paid.",
                "Thanh bước cho biết phiếu này đang ở đâu — Nháp, Chờ phê duyệt, Hoàn tất — và nó cố ý không có nút nào. Trong lúc đợt lương chờ, các phiếu bị giữ nguyên, để con số người ta duyệt chính là con số được chi."),
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
        body: B("BHXH, BHYT and BHTN are charged on the <b>insurance base</b> — for Mai, 12,000,000 ₫, the salary in her contract. Not on gross. That is why 1,500,000 ₫ of overtime moved her tax and did not move her insurance by a single đồng.",
                "BHXH, BHYT và BHTN tính trên <b>mức lương đóng bảo hiểm</b> — với Mai là 12.000.000 ₫, tức mức lương ghi trong hợp đồng. Không tính trên tổng thu nhập. Vì vậy 1.500.000 ₫ tăng ca làm thay đổi thuế của cô ấy nhưng không làm bảo hiểm nhúc nhích một đồng."),
        tip: B("Say it as a sentence: insurance follows the contract, tax follows the month.",
               "Hãy nói thành một câu: bảo hiểm bám theo hợp đồng, thuế bám theo tháng."),
      },
      {
        screen: "payslips", anchor: "ps-detail",
        kicker: B("Before & after", "Trước & sau"),
        title: B("The same employee, two months", "Cùng một nhân viên, hai tháng"),
        body: B("Toggle between June and July and watch which lines move. Overtime and thuế TNCN move; insurance does not. Once you can predict which lines will move before you look, you can review a whole run in the time it used to take to explain one payslip.",
                "Chuyển qua lại giữa tháng 6 và tháng 7 và xem dòng nào thay đổi. Tăng ca và thuế TNCN thay đổi; bảo hiểm thì không. Khi bạn đoán được dòng nào sẽ thay đổi trước cả khi nhìn, bạn soát được cả một đợt lương trong khoảng thời gian trước kia chỉ đủ để giải thích một phiếu."),
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
          explanation: B("Let's rethink that. It is working exactly as the law describes. Contributions are charged on the insurance base, and overtime is not part of that base.",
                         "Hãy nghĩ lại một chút. Nó đang chạy đúng như luật quy định. Bảo hiểm tính trên mức lương đóng bảo hiểm, và tăng ca không nằm trong mức đó."),
        },
        {
          text: B("Correct — insurance is charged on the registered base, which overtime does not change", "Đúng — bảo hiểm tính trên mức lương đóng BH đã đăng ký, mà tăng ca không làm thay đổi"),
          correct: true,
          explanation: B("Yes. Insurance follows the contract, tax follows the month. This one fact explains most of the variance questions a payroll desk gets.",
                         "Đúng vậy. Bảo hiểm bám theo hợp đồng, thuế bám theo tháng. Một điều đó thôi đã giải thích được phần lớn thắc mắc về biến động mà bộ phận lương nhận được."),
        },
        {
          text: B("Their insurance base should be raised to match the higher earnings", "Cần nâng mức đóng bảo hiểm của họ cho khớp thu nhập cao hơn"),
          correct: false,
          explanation: B("Let's rethink that. The insurance base is a figure declared in the contract. Payroll does not raise it to follow a busy month; changing it is an HR and legal decision.",
                         "Hãy nghĩ lại một chút. Mức lương đóng bảo hiểm là con số khai báo theo hợp đồng. Bộ phận lương không nâng nó lên chỉ vì một tháng bận rộn; thay đổi nó là quyết định của nhân sự và pháp chế."),
        },
      ],
    },
  },

  L4: {
    id: "L4", station: "import", mins: 7,
    title: B("Load the month's pay data", "Tải dữ liệu lương của tháng"),
    goal: B("Get a month of attendance and overtime into Payobook, fix the rows that need you, and know what committing does.",
            "Đưa chấm công và tăng ca của một tháng vào Payobook, sửa những dòng cần bạn, và biết việc ghi vào hệ thống sẽ làm gì."),
    steps: [
      {
        screen: "import", anchor: "im-cta",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("\"Load this period's pay data\"", "\"Tải dữ liệu lương của kỳ này\""),
        body: B("Pay Run › Import opens on one job: loading this period's numbers through a guided flow — upload the file, review matches, fix any issues, then commit. The tiles under it are one-off setup: turning a workbook's columns into components, importing employees, setting up a scheme from a file.",
                "Đợt lương › Nhập mở ra với một việc chính: tải số liệu của kỳ này qua một luồng có hướng dẫn — tải tệp lên, soát các dòng khớp, sửa lỗi, rồi ghi vào hệ thống. Các ô bên dưới là thiết lập một lần: biến các cột của một bảng tính thành thành phần, nhập nhân viên, thiết lập chương trình lương từ tệp."),
      },
      {
        screen: "import", anchor: "im-pipe",
        kicker: B("Where every batch is", "Mỗi đợt nhập đang ở đâu"),
        title: B("Six steps, and only the last one wrote anything", "Sáu bước, và chỉ bước cuối đã ghi dữ liệu"),
        body: B("<b>Draft</b>, <b>Loaded</b>, <b>Matched</b>, <b>Validated</b>, <b>Processing</b>, <b>Done</b>. A batch that stops before Done has changed nothing, so you are allowed to load a bad file, look at it, and walk away.",
                "<b>Nháp</b>, <b>Đã tải</b>, <b>Đã khớp</b>, <b>Đã kiểm tra</b>, <b>Đang ghi</b>, <b>Hoàn tất</b>. Một đợt dừng trước Hoàn tất thì chưa thay đổi gì, nên bạn được phép tải một tệp sai, nhìn nó, rồi bỏ đi."),
      },
      {
        screen: "importwizard", anchor: "iw-steps",
        kicker: B("The guided flow", "Luồng có hướng dẫn"),
        title: B("Source & file · Review & match · Validate · Commit", "Nguồn & tệp · Soát & khớp · Kiểm tra · Ghi vào hệ thống"),
        body: B("Step one asks for the source, the formula configuration the columns map onto, the period, and <b>standard working days</b> — the days a full month is paid against. Drop it for a month with public holidays. Then <b>Load &amp; match</b>.",
                "Bước một hỏi nguồn, cấu hình công thức để ánh xạ các cột, kỳ lương, và <b>ngày công chuẩn</b> — số ngày mà một tháng đủ được trả lương theo. Hãy giảm nó cho tháng có ngày nghỉ lễ. Rồi bấm <b>Tải &amp; khớp</b>."),
      },
      {
        screen: "importwizard", anchor: "iw-review",
        kicker: B("The counts", "Các con số đếm"),
        title: B("Read the counts — each row is a person", "Đọc các con số — mỗi dòng là một con người"),
        body: B("<b>Rows loaded</b> 48, <b>Matched</b> 46, <b>New employees</b> 0, <b>Need attention</b> 2. Two rows is two people who would be missing or paid on a wrong figure. Rows loaded that is not your file's row count means a sheet was cut short.",
                "<b>Dòng đã nạp</b> 48, <b>Đã khớp</b> 46, <b>Nhân viên mới</b> 0, <b>Cần xử lý</b> 2. Hai dòng là hai con người sẽ bị thiếu hoặc bị trả theo con số sai. Số dòng đã nạp mà không bằng số dòng trong tệp nghĩa là một trang tính đã bị cắt."),
      },
      {
        screen: "importwizard", anchor: "iw-fixrows",
        kicker: B("Fixing", "Xử lý"),
        title: B("Match…, Retry or Skip — and Skip has a cost", "Khớp…, Thử lại hay Bỏ qua — và Bỏ qua có cái giá của nó"),
        body: B("<b>Match…</b> points a row at the right employee — or creates them as new. <b>Retry</b> re-reads it after you correct the file. <b>Skip</b> drops it — legitimate for a duplicate row, and quietly wrong for a person, because a skipped person is simply absent from the run.",
                "<b>Khớp…</b> trỏ một dòng tới đúng nhân viên — hoặc tạo họ thành nhân viên mới. <b>Thử lại</b> đọc lại dòng đó sau khi bạn sửa tệp. <b>Bỏ qua</b> loại dòng đó ra — hợp lý với một dòng bị lặp, và sai một cách âm thầm với một con người, vì người bị bỏ qua đơn giản là vắng mặt trong đợt lương."),
      },
      {
        screen: "importwizard", anchor: "iw-commit",
        kicker: B("The action", "Thao tác chính"),
        title: B("Commit is the first thing here that writes", "Ghi vào hệ thống là thao tác đầu tiên ở đây thực sự ghi dữ liệu"),
        body: B("Everything before this was a preview. <b>Commit import</b> writes the rows into the period, and they become the inputs the next compute reads. When your company's approval route covers pay data, the same button reads <b>Send for approval</b>, and nothing is written until it is approved.",
                "Mọi thứ trước bước này chỉ là xem trước. <b>Ghi vào hệ thống</b> ghi các dòng vào kỳ lương, và chúng trở thành dữ liệu đầu vào cho lần tính tiếp theo. Khi lộ trình phê duyệt của công ty bạn áp cho dữ liệu lương, chính nút này ghi <b>Gửi đi duyệt</b>, và chưa có gì được ghi cho tới khi được duyệt."),
        consequence: B("Affects the period this batch names, for every row it holds. Reversible: <b>partly</b> — you can import a correction, but a run already computed on these rows has to be computed again. Verify first: the period, that Need attention is zero, and that every Skip was a duplicate and not a person.",
                       "Ảnh hưởng: kỳ lương mà đợt nhập này ghi tên, với mọi dòng nó chứa. Hoàn tác: <b>một phần</b> — bạn có thể nhập một bản sửa, nhưng đợt lương đã tính trên các dòng này phải được tính lại. Kiểm tra trước: kỳ lương, mục Cần xử lý bằng không, và mọi lần Bỏ qua đều là dòng lặp chứ không phải một con người."),
      },
      {
        screen: "runpayroll", anchor: "pw-paymode",
        kicker: B("The same question, in Run", "Cùng một câu hỏi, ở Chạy lương"),
        title: B("Update Payobook, or This run only", "Cập nhật Payobook, hay Chỉ đợt này"),
        body: B("When a pay scheme reads a spreadsheet, Pay Run › Run asks for the file too, and asks what the values should do. <b>Update Payobook</b> saves them onto employee and contract records from now on. <b>This run only</b> uses them once — the batch then says \"This run only — no records were updated\".",
                "Khi một chương trình lương đọc bảng tính, Đợt lương › Chạy lương cũng xin tệp, và hỏi các giá trị dùng để làm gì. <b>Cập nhật Payobook</b> lưu chúng vào hồ sơ nhân viên và hợp đồng từ nay về sau. <b>Chỉ đợt này</b> dùng chúng một lần — đợt nhập sẽ ghi \"Chỉ đợt này — không hồ sơ nào được cập nhật\"."),
      },
      {
        screen: "payslips", anchor: "ps-breakdown",
        kicker: B("The rule this teaches", "Nguyên tắc bài này dạy"),
        title: B("Never fix an import on the payslips", "Đừng bao giờ sửa lỗi nhập liệu trên phiếu lương"),
        body: B("It is tempting. The payslip is right in front of you and the number is obviously wrong. But editing there corrects the result and leaves the input untouched. The next compute brings the mistake straight back.",
                "Rất dễ bị cám dỗ. Phiếu lương đang ngay trước mặt và con số rõ ràng là sai. Nhưng sửa ở đó chỉ chỉnh kết quả và để nguyên đầu vào. Lần tính kế tiếp mang lỗi quay lại ngay."),
      },
    ],
    quiz: {
      question: B("Rows loaded 50, Matched 45, Need attention 5, and the import cut-off is {{importCutoff}}. What do you do?",
                  "Dòng đã nạp 50, Đã khớp 45, Cần xử lý 5, và hạn nhập liệu là {{importCutoff}}. Bạn làm gì?"),
      options: [
        {
          text: B("Commit — 45 of 50 is close enough and the deadline is today", "Ghi vào hệ thống — 45 trên 50 là đủ và hôm nay là hạn"),
          correct: false,
          explanation: B("Let's rethink that. The five rows are five people. Committing now means five payslips that are missing or wrong, found by the employees rather than by you.",
                         "Hãy nghĩ lại một chút. Năm dòng đó là năm con người. Ghi vào hệ thống lúc này nghĩa là năm phiếu lương thiếu hoặc sai, và người phát hiện ra sẽ là nhân viên chứ không phải bạn."),
        },
        {
          text: B("Resolve the five rows first, then commit", "Xử lý năm dòng đó trước, rồi mới ghi vào hệ thống"),
          correct: true,
          explanation: B("Yes. Each of those rows is a person. Every one of them is cheaper to fix now than as a retro line next month.",
                         "Đúng vậy. Mỗi dòng đó là một con người. Xử lý ngay bây giờ luôn rẻ hơn một dòng hồi tố vào tháng sau."),
        },
        {
          text: B("Skip the five rows so Need attention reaches zero", "Bỏ qua năm dòng đó để Cần xử lý về không"),
          correct: false,
          explanation: B("Let's rethink that. Skipping removes the rows from the batch, not the problem from the month. The count goes to zero because those people are no longer in the import at all.",
                         "Hãy nghĩ lại một chút. Bỏ qua chỉ loại các dòng ra khỏi đợt nhập, không loại vấn đề ra khỏi tháng — con số về không vì những người đó không còn trong dữ liệu nhập nữa."),
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
    id: "L5", station: "formula", mins: 8,
    title: B("The formula is the payslip", "Công thức chính là phiếu lương"),
    goal: B("Read a pay scheme's rulebook end to end, point at the component behind any payslip line, and know how a change goes live safely.",
            "Đọc trọn bộ quy tắc của một chương trình lương, chỉ đúng thành phần đứng sau bất kỳ dòng phiếu lương nào, và biết một thay đổi được đưa vào dùng an toàn ra sao."),
    steps: [
      {
        screen: "formula", anchor: "fs-config",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("One pay scheme, one rulebook", "Một chương trình lương, một bộ quy tắc"),
        body: B("Settings › Formula Engine opens Formula Studio on one configuration: here <b>HOASEN_RETAIL_END</b>, the rulebook every Retail end-of-month payslip is computed by. The name at the top is a switcher. Picking a pay scheme in Pay Run › Run is picking which of these runs.",
                "Cài đặt › Bộ máy công thức mở Xưởng công thức trên một cấu hình: ở đây là <b>HOASEN_RETAIL_END</b>, bộ quy tắc tính mọi phiếu lương cuối tháng của Bán lẻ. Cái tên ở trên cùng là một ô chuyển. Chọn chương trình lương trong Đợt lương › Chạy lương chính là chọn cấu hình nào sẽ chạy."),
        tip: B("The code is the thing to quote when you ask about a number: \"HOASEN_RETAIL_END, component TNCN\" is a question someone can answer. The shape is PREFIX_DIVISION_CYCLE; the prefix belongs to the company.",
               "Mã cấu hình là thứ nên trích dẫn khi hỏi về một con số: \"HOASEN_RETAIL_END, thành phần TNCN\" là câu hỏi có người trả lời được. Dạng chung là TIỀN TỐ_BỘ PHẬN_CHU KỲ; tiền tố là của từng công ty."),
      },
      {
        screen: "formula", anchor: "fs-views",
        kicker: B("Six ways to look", "Sáu cách xem"),
        title: B("Cards, Grid, Test, Compare, Health, Settings", "Thẻ, Lưới, Kiểm thử, So sánh, Sức khoẻ, Cài đặt"),
        body: B("The same configuration, six views. <b>Cards</b> reads component by component. <b>Grid</b> lays them out like the spreadsheet they replaced. <b>Settings</b> opens the guided setup for this scheme in edit mode — the same steps as New configuration, already filled in.",
                "Cùng một cấu hình, sáu cách xem. <b>Thẻ</b> đọc từng thành phần một. <b>Lưới</b> bày chúng ra như bảng tính mà chúng thay thế. <b>Cài đặt</b> mở phần thiết lập có hướng dẫn của chương trình này ở chế độ sửa — đúng các bước của Cấu hình mới, đã điền sẵn."),
      },
      {
        screen: "formula", anchor: "fs-components",
        kicker: B("The inventory", "Danh mục thành phần"),
        title: B("Every line on a payslip is a component here", "Mỗi dòng trên phiếu lương là một thành phần ở đây"),
        body: B("Ten components in four kinds: <b>inputs</b> (base salary), <b>earnings</b> (allowances, overtime), <b>deductions</b> (BHXH, BHYT, BHTN, thuế TNCN) and <b>totals</b> (gross, taxable, net). Below them sit the <b>parameters</b> those formulas read. If a line is wrong, the number behind it is one of these.",
                "Mười thành phần thuộc bốn loại: <b>đầu vào</b> (lương cơ bản), <b>thu nhập</b> (phụ cấp, tăng ca), <b>khấu trừ</b> (BHXH, BHYT, BHTN, thuế TNCN) và <b>các tổng</b> (tổng thu nhập, thu nhập chịu thuế, thực nhận). Bên dưới là các <b>tham số</b> mà những công thức đó đọc vào. Dòng nào sai thì con số đứng sau nó nằm trong số này."),
        tip: B("<b>EESI</b>, <b>EEHI</b> and <b>EEUI</b> are the contribution rates, and they live HERE, on the configuration. Statutory declares what the company contributes; this is what actually charges it.",
               "<b>EESI</b>, <b>EEHI</b> và <b>EEUI</b> là các tỷ lệ đóng bảo hiểm, và chúng nằm Ở ĐÂY, trên cấu hình. Bảo hiểm & Thuế khai báo mức doanh nghiệp đóng; còn đây mới là nơi thật sự tính ra khoản đó."),
      },
      {
        screen: "formula", anchor: "fs-formula",
        kicker: B("The formula", "Công thức"),
        title: B("Read it out loud and it is just a sentence", "Đọc to lên thì nó chỉ là một câu"),
        body: B("<b>TNCN = 5% × TNCT</b>, and <b>TNCT = GROSS − (BHXH + BHYT + BHTN) − 11,000,000</b>. That is the whole of Mai's tax line: gross, less her insurance, less the personal deduction, then the first band's rate. Each coloured chip is a component you can click through to.",
                "<b>TNCN = 5% × TNCT</b>, và <b>TNCT = Tổng thu nhập − (BHXH + BHYT + BHTN) − 11.000.000</b>. Đó là toàn bộ dòng thuế của Mai: tổng thu nhập, trừ bảo hiểm của cô ấy, trừ giảm trừ bản thân, rồi nhân thuế suất bậc đầu tiên. Mỗi chip màu là một thành phần bạn bấm vào để đi tiếp."),
      },
      {
        screen: "formula", anchor: "fs-namesletters",
        kicker: B("Two ways to read", "Hai cách đọc"),
        title: B("Names for people, letters for spreadsheets", "Tên cho người đọc, chữ cái cho bảng tính"),
        body: B("The same formula switches between <b>Names</b> (TNCN = 5% × TNCT) and <b>Letters</b> (I = 5% × H). One formula in two spellings, so a change in either is a change in both.",
                "Cùng một công thức chuyển qua lại giữa <b>Tên</b> (TNCN = 5% × TNCT) và <b>Chữ cái</b> (I = 5% × H). Một công thức với hai cách viết, nên sửa ở cách nào cũng là sửa cả hai."),
      },
      {
        screen: "formula", anchor: "fs-deps",
        kicker: B("The wiring", "Đường dây"),
        title: B("Depends on, and used by", "Phụ thuộc vào, và được dùng bởi"),
        body: B("TNCT <b>depends on</b> GROSS, BHXH, BHYT and BHTN. It is <b>used by</b> THUCNHAN, so the net follows it. Read this panel before renaming or deleting anything: it names exactly what would break.",
                "TNCT <b>phụ thuộc vào</b> Tổng thu nhập, BHXH, BHYT và BHTN. Nó <b>được dùng bởi</b> THUCNHAN, nên thực nhận đi theo nó. Hãy đọc bảng này trước khi đổi tên hay xoá bất cứ thứ gì: nó nêu chính xác cái gì sẽ hỏng."),
      },
      {
        screen: "formula", anchor: "fs-preview",
        kicker: B("Proof", "Bằng chứng"),
        title: B("The rulebook, run on a real person", "Bộ quy tắc, chạy trên một người thật"),
        body: B("The preview runs the whole configuration on one employee: Mai's gross of <b>14,280,000 ₫</b>, taxable 2,020,000, tax 101,000 and net <b>12,919,000 ₫</b>. The same arithmetic as her payslip — here you can see which component produced each line.",
                "Bản xem trước chạy toàn bộ cấu hình trên một nhân viên: tổng thu nhập của Mai <b>14.280.000 ₫</b>, thu nhập chịu thuế 2.020.000, thuế 101.000 và thực nhận <b>12.919.000 ₫</b>. Đúng phép tính trên phiếu lương của cô ấy — ở đây bạn thấy thành phần nào đã tạo ra từng dòng."),
        moment: { kind: "calc" },
      },
      {
        screen: "formula", anchor: "rep-fs-stage",
        kicker: B("Going live", "Đưa vào dùng"),
        title: B("Start testing, Validate, Activate", "Bắt đầu thử nghiệm, Xác thực, Kích hoạt"),
        body: B("A configuration moves <b>Draft → Testing → Validated → Active</b>, one press of the button beside its name at a time. Only an Active configuration pays people. The stage badge opens <b>Put it back to draft</b> and <b>Retire this configuration</b> — or <b>Propose retiring it</b>, when your company's route says retiring needs a sign-off.",
                "Một cấu hình đi qua <b>Nháp → Đang thử nghiệm → Đã xác thực → Đang hoạt động</b>, mỗi lần bấm nút cạnh tên là một bước. Chỉ cấu hình Đang hoạt động mới trả lương cho người thật. Huy hiệu giai đoạn mở ra <b>Đưa về bản nháp</b> và <b>Ngừng sử dụng cấu hình này</b> — hoặc <b>Đề xuất ngừng sử dụng</b>, khi lộ trình của công ty bạn quy định việc ngừng cần được phê duyệt."),
        moment: { kind: "pipeline", chain: "formula" },
      },
      {
        screen: "formula", anchor: "rep-fs-tools",
        kicker: B("Before you act", "Trước khi thao tác"),
        title: B("Simulate lives in Tools → Analyze", "Mô phỏng nằm trong Công cụ → Phân tích"),
        body: B("<b>Tools</b> (or Ctrl/Cmd + K) opens every tool in one place. Under <b>Analyze</b>, <b>Simulate</b> runs this configuration against last period's real payslips and shows what would have come out. It is the only way to see a change's effect on everyone rather than on one preview employee.",
                "<b>Công cụ</b> (hoặc Ctrl/Cmd + K) mở mọi công cụ ở cùng một chỗ. Trong mục <b>Phân tích</b>, <b>Mô phỏng</b> chạy cấu hình này trên phiếu lương thật của kỳ trước và cho thấy kết quả sẽ ra sao. Đây là cách duy nhất để thấy tác động của một thay đổi lên mọi người thay vì chỉ một nhân viên xem trước."),
        consequence: B("Activating a changed configuration affects every future payslip on this pay scheme — the whole scheme, not one employee, not one month. Reversible: <b>partly</b> — you can put it back, but a run already computed on the changed version keeps its figures until it is computed again. Verify first: the dependency panel for anything you renamed, and a simulation against last month.",
                       "Kích hoạt một cấu hình đã sửa ảnh hưởng tới mọi phiếu lương tương lai của chương trình lương này — cả chương trình, không phải một nhân viên, không chỉ một tháng. Hoàn tác: <b>một phần</b> — bạn có thể đưa nó về, nhưng đợt lương đã tính theo bản đã sửa vẫn giữ nguyên con số cho tới khi được tính lại. Kiểm tra trước: bảng phụ thuộc cho bất cứ thứ gì bạn đổi tên, và một lần mô phỏng trên tháng trước."),
      },
    ],
    quiz: {
      question: B("You need to add a meal allowance for Retail. The July run is Waiting for approval. What do you do?",
                  "Bạn cần thêm phụ cấp ăn ca cho Bán lẻ. Đợt lương tháng 7 đang Chờ phê duyệt. Bạn làm gì?"),
      options: [
        {
          text: B("Add it and activate now — July is already computed, so it cannot be affected", "Thêm và kích hoạt ngay — tháng 7 đã tính xong nên không bị ảnh hưởng"),
          correct: false,
          explanation: B("Let's rethink that. Computed is not finished. If July is sent back, it is computed again with the configuration as it stands THEN — and quietly gains an allowance nobody approved for it.",
                         "Hãy nghĩ lại một chút. Đã tính không có nghĩa là đã xong. Nếu tháng 7 bị trả lại, nó sẽ được tính lại theo cấu hình TẠI THỜI ĐIỂM ĐÓ — và âm thầm có thêm một khoản phụ cấp chưa ai duyệt cho nó."),
        },
        {
          text: B("Add it, simulate it against last month, and activate once July is Done", "Thêm vào, mô phỏng trên tháng trước, và kích hoạt khi tháng 7 đã Hoàn tất"),
          correct: true,
          explanation: B("Yes. The simulation tells you what the change does to real people before anybody is paid by it. Waiting for July to reach Done means no open run can pick it up by accident.",
                         "Đúng vậy. Mô phỏng cho bạn biết thay đổi tác động thế nào tới người thật trước khi có ai được trả theo nó. Chờ tháng 7 Hoàn tất thì không đợt nào đang mở có thể vô tình nhận phải nó."),
        },
        {
          text: B("Add the allowance straight onto each employee's payslip instead", "Thay vào đó, cộng thẳng khoản phụ cấp vào từng phiếu lương"),
          correct: false,
          explanation: B("Let's rethink that. That is forty-eight manual edits that the next compute erases, and next month it is forty-eight more. A component is written once and paid every month.",
                         "Hãy nghĩ lại một chút. Đó là bốn mươi tám lần sửa tay mà lần tính kế tiếp sẽ xoá sạch, và tháng sau lại thêm bốn mươi tám lần nữa. Một thành phần viết một lần và trả hằng tháng."),
        },
      ],
    },
  },

  L6: {
    id: "L6", station: "statutory", mins: 8,
    title: B("Statutory — the rules the law writes", "Bảo hiểm & Thuế — những quy tắc do luật viết"),
    goal: B("Read the insurance policy and the tax table the way an inspector would. Then apply a rate change without touching a month that is already open.",
            "Đọc chính sách bảo hiểm và biểu thuế theo cách một đoàn kiểm tra sẽ đọc. Rồi áp dụng một thay đổi tỷ lệ mà không đụng tới tháng đang mở."),
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
        tip: B("Somebody will tell you they pay a third of their salary in insurance. This table is the answer: they pay 10.5% of the insurance base, and the company pays the rest.",
               "Sẽ có người nói với bạn rằng họ đóng cả một phần ba lương cho bảo hiểm. Bảng này chính là câu trả lời: họ đóng 10,5% trên mức lương đóng bảo hiểm, phần còn lại do công ty đóng."),
      },
      {
        screen: "statutory", anchor: "st-rates",
        kicker: B("The base & the ceiling", "Mức đóng & trần"),
        title: B("Charged on the registered base, up to a ceiling", "Tính trên mức đã đăng ký, tới một mức trần"),
        body: B("Contributions apply to the <b>insurance base</b> — for Mai, the 12,000,000 ₫ in her contract, not her 14,280,000 ₫ gross. They also stop at the ceiling in the last column. Above <b>20,000,000 ₫</b> the deduction does not grow, so two people on very different salaries can pay exactly the same BHXH.",
                "Bảo hiểm tính trên <b>mức lương đóng bảo hiểm</b> — với Mai là 12.000.000 ₫ ghi trong hợp đồng, không phải tổng thu nhập 14.280.000 ₫. Nó cũng dừng ở mức trần tại cột cuối. Trên <b>20.000.000 ₫</b> thì khoản khấu trừ không tăng nữa, nên hai người lương rất khác nhau vẫn có thể đóng BHXH bằng nhau."),
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
        body: B("There is <b>no version history</b> on a policy. When a decree changes a rate, you create a <b>new policy record</b> with its own code and its own <b>effective date</b>. Codes are unique per company. The old record stays as the evidence of what you declared before it. Archiving that record takes it off this list, so the list shows live declarations rather than the whole history.",
                "Chính sách <b>không có lịch sử phiên bản</b>. Khi một nghị định thay đổi tỷ lệ, bạn tạo một <b>bản ghi chính sách mới</b> với mã riêng và <b>ngày hiệu lực</b> riêng. Mã là duy nhất trong mỗi công ty. Bản cũ ở lại làm bằng chứng cho mức bạn đã khai báo trước đó. Lưu trữ bản đó sẽ đưa nó ra khỏi danh sách này, nên danh sách ở đây là các bản khai báo còn hiệu lực chứ không phải toàn bộ lịch sử."),
        tip: B("The rates table above shows the ACTIVE policy with the latest effective date. It does not compare that date to today, and it does not read the end date. So a policy dated from next month is displayed the moment you save it.",
               "Bảng tỷ lệ ở trên hiển thị chính sách đang BẬT có ngày hiệu lực mới nhất. Nó không so ngày đó với hôm nay, và cũng không đọc ngày kết thúc. Nên một chính sách ghi hiệu lực từ tháng sau sẽ hiển thị ngay khi bạn vừa lưu."),
      },
      {
        screen: "statutory", anchor: "st-new",
        kicker: B("Before you act", "Trước khi thao tác"),
        title: B("Declaring a rate is half the job", "Khai báo một tỷ lệ mới chỉ là một nửa công việc"),
        body: B("Saving a new policy changes what this screen, the contribution analytics and the statutory reports say. It changes <b>no payslip</b>. The rate that prices pay is a parameter on each division's formula configuration. So a rate change is two pieces of work: declare it here, and change it there. Until both are done, the two disagree — and this screen, not the payslip, is telling the truth about what the company intends.",
                "Lưu một chính sách mới sẽ thay đổi những gì màn hình này, phần phân tích chi phí bảo hiểm và các báo cáo bắt buộc nói ra. Nó không làm thay đổi <b>một phiếu lương nào</b>. Tỷ lệ tính ra tiền là một tham số trong cấu hình công thức của từng bộ phận. Nên đổi tỷ lệ là hai phần việc: khai báo ở đây, và sửa ở đó. Khi chưa làm đủ cả hai thì hai bên còn lệch — và chính màn hình này, chứ không phải phiếu lương, mới nói đúng điều doanh nghiệp muốn."),
        consequence: B("Affects what is <b>declared and reported</b>, company-wide: this cockpit, the contribution analytics and the statutory reports. It does not reprice a single payslip on its own. Reversible: <b>yes</b> — archive the record and the previous declaration is displayed again, because nothing downstream has been recomputed from it. Verify first: that you know which configurations have to change too, and who is going to change them.",
                       "Ảnh hưởng tới phần <b>khai báo và báo cáo</b> trên toàn công ty: màn hình này, phần phân tích chi phí bảo hiểm và các báo cáo bắt buộc. Tự nó không tính lại một phiếu lương nào. Hoàn tác: <b>được</b> — lưu trữ bản ghi là bản khai báo trước đó hiển thị trở lại, vì chưa có gì phía sau được tính lại từ nó. Kiểm tra trước: bạn đã biết những cấu hình nào cũng phải sửa, và ai sẽ sửa chúng."),
      },
      {
        screen: "statutory", anchor: "rep-slipline",
        kicker: B("Before & after", "Trước & sau"),
        title: B("What half a percentage point costs", "Nửa điểm phần trăm đáng giá bao nhiêu"),
        body: B("Say BHYT's employee share went from 1.5% to 2.0%. Mai's deduction grows 60,000 ₫, and her net falls <b>57,000 ₫</b> — not 60,000. Insurance comes off before tax, so her thuế TNCN falls 3,000 with it. Toggle the two sides and read which lines move.",
                "Giả sử phần người lao động của BHYT tăng từ 1,5% lên 2,0%. Khoản khấu trừ của Mai tăng 60.000 ₫, còn thực nhận giảm <b>57.000 ₫</b> — không phải 60.000. Bảo hiểm được trừ trước khi tính thuế, nên thuế TNCN của cô ấy giảm theo 3.000. Hãy chuyển qua lại hai bên và xem những dòng nào thay đổi."),
        moment: { kind: "morph", which: "maiBhytRate" },
      },
    ],
    quiz: {
      question: B("A decree raises BHYT's employee share from 1 August. It is 20 July and the July run is still Waiting for approval. What do you do?",
                  "Một nghị định nâng phần đóng BHYT của người lao động từ 1/8. Hôm nay là 20/7 và đợt lương tháng 7 vẫn đang Chờ phê duyệt. Bạn làm gì?"),
      options: [
        {
          text: B("Edit the rate on the policy that is in force now", "Sửa tỷ lệ ngay trên chính sách đang có hiệu lực"),
          correct: false,
          explanation: B("Let's rethink that. There is no version history to fall back on. The old declared rate is simply gone, and so is the record of what the company was declaring while July was being paid. That record is exactly what an inspection asks to see.",
                         "Hãy nghĩ lại một chút. Không có lịch sử phiên bản nào để quay lại. Mức đã khai báo trước đó đơn giản là mất, và bằng chứng về mức doanh nghiệp khai báo trong lúc trả lương tháng 7 cũng mất theo. Chính bản ghi đó là thứ đoàn kiểm tra yêu cầu được xem."),
        },
        {
          text: B("Create a new policy record dated 01/08, and plan the configuration change with it", "Tạo bản ghi chính sách mới ghi ngày 01/08, và lên kế hoạch sửa cấu hình cùng lúc"),
          correct: true,
          explanation: B("Yes. The date records what the decree says, and the old record stays as evidence of what you declared before it. Then the half people forget: the rate that actually prices pay is a parameter on each division's configuration. Somebody has to change that too, before August runs.",
                         "Đúng vậy. Ngày hiệu lực ghi đúng những gì nghị định nêu, và bản ghi cũ ở lại làm bằng chứng cho mức bạn đã khai báo trước đó. Rồi tới phần người ta hay quên: tỷ lệ thực sự tính ra tiền là một tham số trong cấu hình của từng bộ phận. Phải có người sửa cả chỗ đó, trước khi tháng 8 chạy lương."),
        },
        {
          text: B("Create the new policy now with today's date so nothing is forgotten", "Tạo chính sách mới ngay hôm nay với ngày hiệu lực là hôm nay cho khỏi quên"),
          correct: false,
          explanation: B("Let's rethink that. The instinct is right and the date is wrong. Today means 20 July, and the decree does not say 20 July. The declaration would then record a legal start the company cannot evidence. Create the record now if you like — put 01/08 in the effective date, and tell whoever is reviewing July that the rates on this screen are next month's.",
                         "Hãy nghĩ lại một chút. Ý thức cẩn thận là đúng, chỉ có ngày là sai. Hôm nay là 20/7, mà nghị định không nói 20/7. Bản khai báo sẽ ghi một mốc pháp lý mà doanh nghiệp không chứng minh được. Cứ tạo bản ghi ngay bây giờ cũng được — hãy điền 01/08 vào ngày hiệu lực, và báo cho người đang soát xét tháng 7 rằng tỷ lệ trên màn hình này là của tháng sau."),
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
    title: B("Welcome — Home and Pulse", "Chào mừng — Trang chủ và Tổng quan"),
    goal: B("Read Pulse the way the first ten minutes of a payroll day needs it read — and know where everything else in Payobook lives.",
            "Đọc tab Tổng quan theo đúng cách mười phút đầu của một ngày làm lương cần — và biết mọi thứ còn lại trong Payobook nằm ở đâu."),
    steps: [
      {
        screen: "dashboard", anchor: "dash-hero",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Where payroll is, before you choose anything", "Công việc lương đang ở đâu, trước khi bạn chọn bất cứ gì"),
        body: B("Home › Pulse is where you land. The line under the greeting is the latest pay run: its name, how many of its payslips are done, and how many are waiting for approval. <b>Run Payroll</b> beside it opens Pay Run › Run — the same place the rail takes you.",
                "Trang chủ › Tổng quan là nơi bạn vào đầu tiên. Dòng dưới lời chào là đợt lương mới nhất: tên của nó, bao nhiêu phiếu đã xong, và bao nhiêu phiếu đang chờ phê duyệt. Nút <b>Chạy bảng lương</b> bên cạnh mở Đợt lương › Chạy lương — đúng nơi thanh bên đưa bạn tới."),
      },
      {
        screen: "dashboard", anchor: "dash-period",
        kicker: B("Which month", "Tháng nào"),
        title: B("\"Figures for July 2026\"", "\"Số liệu của Tháng 7/2026\""),
        body: B("Every number below belongs to one payroll month, and this line says which — normally the latest. The strip under it has one chip per payroll month, its bar showing how many people were paid. Press a month and every figure follows; Escape comes back to the latest.",
                "Mọi con số bên dưới thuộc về một tháng lương, và dòng này cho biết tháng nào — thường là tháng gần nhất. Dải bên dưới có một chip cho mỗi tháng lương, thanh của nó cho thấy bao nhiêu người được trả lương. Bấm một tháng là mọi con số đổi theo; phím Escape đưa về tháng gần nhất."),
      },
      {
        screen: "dashboard", anchor: "dash-kpis",
        kicker: B("Reading the band", "Đọc dải chỉ số"),
        title: B("Four numbers, and what each one counts", "Bốn con số, và mỗi con số đếm gì"),
        body: B("<b>Headcount</b>: every employee — not tied to the month — with active contracts under it. <b>Monthly payroll</b>: the gross cost of that month's end-of-month payslips. <b>Pending approval</b>: payslips waiting for approval, company-wide. <b>Active configs</b>: pay schemes switched on, and their rules.",
                "<b>Số lượng nhân sự</b>: mọi nhân viên — không gắn với tháng — kèm số hợp đồng đang hiệu lực bên dưới. <b>Chi phí lương tháng</b>: tổng thu nhập của các phiếu lương cuối tháng trong tháng đó. <b>Đang chờ phê duyệt</b>: số phiếu lương đang chờ duyệt trên toàn công ty. <b>Cấu hình đang chạy</b>: các chương trình lương đang bật, kèm số quy tắc."),
        tip: B("Headcount is 70 and only 69 were paid in July: Hoàng Văn Nam is hired but starts in August. A gap between those two numbers is worth one look, every month.",
               "Số lượng nhân sự là 70 mà tháng 7 chỉ trả lương 69 người: Hoàng Văn Nam đã được tuyển nhưng bắt đầu từ tháng 8. Khoảng chênh giữa hai con số đó đáng nhìn qua một lần, mỗi tháng."),
      },
      {
        screen: "dashboard", anchor: "dash-formula",
        kicker: B("What makes this product different", "Điều làm sản phẩm này khác biệt"),
        title: B("Pay is computed from a rulebook you can read", "Lương được tính từ một bộ quy tắc bạn đọc được"),
        body: B("Every line on every payslip comes from a named component in a <b>formula configuration</b> — one per pay scheme. It is written the way a spreadsheet is written, so the person who has to explain it can read it. This card opens it; the Formula Engine lesson takes one apart.",
                "Mọi dòng trên mọi phiếu lương đều đến từ một thành phần có tên trong <b>cấu hình công thức</b> — mỗi chương trình lương một bộ. Nó được viết như một bảng tính, nên người phải giải thích vẫn đọc được. Thẻ này mở nó ra; bài Bộ máy công thức sẽ mổ xẻ một bộ."),
        tip: B("That is why \"why is my pay this number\" has an answer here rather than a promise to look into it.",
               "Đó là lý do câu hỏi \"vì sao lương tôi lại là con số này\" có câu trả lời ngay, chứ không phải một lời hứa sẽ xem lại."),
      },
      {
        screen: "dashboard", anchor: "rep-nav",
        kicker: B("Where everything lives", "Mọi thứ nằm ở đâu"),
        title: B("Nine pages on the rail", "Chín trang trên thanh bên"),
        body: B("<b>Home</b> is where you land and where approvals wait. <b>Pay Run</b> is the month's work, <b>People</b> who can be paid, <b>Lifecycle</b> joining and leaving, <b>Workforce</b> time and attendance. <b>Insights</b> and <b>Compliance</b> answer questions and file reports. <b>Learn</b> is where you are now, and <b>Settings</b> is read often and changed rarely.",
                "<b>Trang chủ</b> là nơi bạn vào và nơi các yêu cầu phê duyệt chờ. <b>Đợt lương</b> là công việc của tháng, <b>Con người</b> là những ai có thể được trả lương, <b>Vòng đời nhân sự</b> là vào và nghỉ việc, <b>Lực lượng lao động</b> là giờ công và chấm công. <b>Phân tích</b> và <b>Tuân thủ</b> trả lời câu hỏi và lập báo cáo. <b>Học cùng Payobook</b> là nơi bạn đang đứng, còn <b>Cài đặt</b> thì hay được đọc và hiếm khi bị sửa."),
      },
      {
        screen: "dashboard", anchor: "rep-tabs",
        kicker: B("Tabs", "Các tab"),
        title: B("Every page has tabs", "Trang nào cũng có tab"),
        body: B("Home has <b>Pulse</b>, <b>Approvals</b>, <b>Wall</b> and <b>Announce</b>. Pay Run has Run, Runs, Payslips and more. A tab you cannot see is one your access does not open. The lessons still describe it, because somebody who cannot open a screen is exactly the person who needs to know what it is.",
                "Trang chủ có <b>Tổng quan</b>, <b>Phê duyệt</b>, <b>Bảng vinh danh</b> và <b>Thông báo</b>. Đợt lương có Chạy lương, Các đợt lương, Phiếu lương và nhiều tab khác. Tab nào bạn không thấy là tab quyền của bạn không mở được. Các bài học vẫn mô tả nó, vì người không mở được một màn hình chính là người cần biết màn hình đó là gì."),
      },
      {
        screen: "dashboard", anchor: "",
        kicker: B("How to get help", "Cách hỏi khi cần"),
        title: B("There is a helper on every screen, and it will not act for you", "Mọi màn hình đều có trợ lý, và nó sẽ không thao tác thay bạn"),
        body: B("The button in the bottom-right corner opens on <b>any</b> screen. It knows which page and tab you are on: what it is for, what to do next, what a tile counts. It explains — you act. It never computes a run, approves a payslip or changes a record, and it never invents a rate.",
                "Nút ở góc dưới bên phải mở được trên <b>mọi</b> màn hình. Nó biết bạn đang ở trang và tab nào: màn hình đó để làm gì, nên làm gì tiếp, một ô số liệu đếm cái gì. Nó giải thích — bạn thao tác. Nó không bao giờ tự tính lương, phê duyệt phiếu lương hay sửa dữ liệu, và không bao giờ bịa ra một tỷ lệ."),
      },
    ],
    quiz: {
      question: B("Pulse says <b>48</b> pending approval, and you are on the approval route for pay runs. What does that number tell you about your own morning?",
                  "Tab Tổng quan hiện <b>48</b> đang chờ phê duyệt, và bạn có tên trên lộ trình phê duyệt đợt lương. Con số đó nói gì về buổi sáng của riêng bạn?"),
      options: [
        {
          text: B("Forty-eight pay runs are waiting for my signature", "Có bốn mươi tám đợt lương đang chờ chữ ký của tôi"),
          correct: false,
          explanation: B("Let's rethink that. The tile counts <b>payslips</b>, not runs — 48 is one ordinary run — and it counts them company-wide, whoever they are waiting for.",
                         "Hãy nghĩ lại một chút. Ô đó đếm <b>phiếu lương</b>, không phải đợt lương — 48 phiếu chỉ là một đợt bình thường — và đếm trên toàn công ty, dù chúng đang chờ ai."),
        },
        {
          text: B("Forty-eight payslips are waiting somewhere; Home › Approvals, My turn, tells me what is mine", "Có bốn mươi tám phiếu lương đang chờ ở đâu đó; Trang chủ › Phê duyệt, tab Đến lượt tôi, cho biết phần nào là của tôi"),
          correct: true,
          explanation: B("Exactly. Pulse reports a company-wide state, counted in payslips. What is YOURS is a request whose current step names you — and that is the My turn tab, next door.",
                         "Chính xác. Tổng quan báo cáo hiện trạng toàn công ty, đếm theo phiếu lương. Phần CỦA BẠN là những yêu cầu mà bước hiện tại ghi tên bạn — và đó là tab Đến lượt tôi, ngay bên cạnh."),
        },
        {
          text: B("Payroll is behind schedule", "Công việc tính lương đang chậm tiến độ"),
          correct: false,
          explanation: B("Let's rethink that. Payslips waiting mid-month is what a working approval looks like. The number means \"behind\" only once you know whose step they are at and for how long — and this tile carries neither.",
                         "Hãy nghĩ lại một chút. Phiếu lương đang chờ giữa tháng chính là hình ảnh của một quy trình phê duyệt đang chạy. Con số chỉ có nghĩa là \"chậm\" khi bạn biết chúng đang ở bước của ai và đã bao lâu — mà ô này không cho biết điều nào."),
        },
      ],
    },
  },

  LA: {
    id: "LA", station: "approvals", mins: 10,
    title: B("Approve like it's your signature", "Phê duyệt như thể đó là chữ ký của bạn"),
    goal: B("Decide on a pay run the way somebody who will be asked about it decides — and know what each decision in the inbox does to the run.",
            "Ra quyết định về một đợt lương theo cách của người sẽ bị hỏi lại về nó — và biết mỗi quyết định trong hộp phê duyệt tác động thế nào tới đợt lương."),
    steps: [
      {
        screen: "approvals", anchor: "ai-tabs",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("One inbox for everything", "Một hộp cho mọi thứ"),
        body: B("Home › Approvals holds every request waiting for a decision — pay runs, overtime, leave, hiring — in four tabs: <b>My turn</b>, <b>All I can see</b>, <b>Sent back</b> and <b>Finished</b>. My turn is the only one that is work for you: a request whose current step names you.",
                "Trang chủ › Phê duyệt chứa mọi yêu cầu đang chờ quyết định — đợt lương, tăng ca, nghỉ phép, tuyển dụng — trong bốn tab: <b>Đến lượt tôi</b>, <b>Tất cả tôi xem được</b>, <b>Đã trả lại</b> và <b>Đã xong</b>. Chỉ Đến lượt tôi mới là việc của bạn: những yêu cầu mà bước hiện tại ghi tên bạn."),
        tip: B("Mine, My team and Everyone change what you can SEE, not what you can decide. The screen says it: \"Watching, not deciding — a request is yours to decide only when a step names you.\"",
               "Của tôi, Nhóm của tôi và Tất cả mọi người đổi những gì bạn XEM được, không đổi những gì bạn được quyết: \"Chỉ xem, không quyết — một yêu cầu chỉ là của bạn khi một bước ghi tên bạn.\""),
      },
      {
        screen: "approvals", anchor: "ai-card",
        kicker: B("The card", "Thẻ yêu cầu"),
        title: B("What a request card tells you", "Thẻ yêu cầu cho bạn biết gì"),
        body: B("The July run shows \"Your turn\", who sent it in and when, and the route it follows. It says <b>Waiting for Đặng Thu Hà</b>, then the net in its own currency, the payslip count and the due date. Amounts are never added across currencies.",
                "Đợt lương tháng 7: \"Đến lượt bạn\", ai đã gửi và khi nào, lộ trình nó đi theo, <b>Đang chờ Đặng Thu Hà</b>, tổng thực nhận bằng đúng loại tiền của nó, số phiếu lương, và hạn. Số tiền không bao giờ được cộng chung giữa các loại tiền."),
      },
      {
        screen: "approvals", anchor: "ai-route",
        kicker: B("The route", "Lộ trình"),
        title: B("Payroll check → HR lead review → Finance approval", "Kiểm tra bảng lương → Trưởng nhân sự soát xét → Tài chính phê duyệt"),
        body: B("The dots are the steps, in order. The first is done, the pulsing one is now — yours — and the last is next. Your company drew this route in the Approval Matrix; this is the one Payobook starts every company with. Each yes moves the request one dot on; the last yes makes the run <b>Done</b>.",
                "Các chấm là các bước, theo thứ tự. Chấm đầu đã xong, chấm đang nhấp nháy là bây giờ — của bạn — và chấm cuối là tiếp theo. Công ty bạn vẽ lộ trình này trong Ma trận phê duyệt; đây là lộ trình Payobook tạo sẵn cho mọi công ty. Mỗi cái gật đầu đưa yêu cầu tiến một chấm; cái gật đầu cuối cùng biến đợt lương thành <b>Hoàn tất</b>."),
        moment: { kind: "pipeline", chain: "route" },
      },
      {
        screen: "approvals", anchor: "ai-facts",
        kicker: B("The facts", "Các dữ kiện"),
        title: B("Frozen when it was sent in", "Được giữ nguyên từ lúc gửi"),
        body: B("Open the request: its facts are the ones it was sent in with. <b>Total net pay</b>, <b>Total gross pay</b>, <b>Payslips</b>, <b>Employees</b>, <b>Change against the last run</b> (+2.7%), <b>Contains overtime</b> (Yes). The payslips are frozen too, so what you approve is what gets paid.",
                "Mở yêu cầu ra, các dữ kiện là đúng những gì nó mang theo lúc gửi: <b>Tổng thực nhận</b>, <b>Tổng lương gộp</b>, <b>Phiếu lương</b>, <b>Nhân viên</b>, <b>Thay đổi so với kỳ trước</b> (+2,7%), <b>Có làm thêm giờ</b> (Có). Các phiếu lương cũng bị giữ nguyên, nên thứ bạn duyệt chính là thứ được chi."),
      },
      {
        screen: "payslips", anchor: "ps-list",
        kicker: B("The strategy", "Cách làm"),
        title: B("Nobody reads forty-eight payslips, and nobody should", "Không ai đọc hết bốn mươi tám phiếu lương, và cũng không nên"),
        body: B("\"Contains overtime: Yes\" and +2.7% are your leads. Open the payslips with the most overtime first, then sample two or three ordinary ones. Payobook will not flag a big jump on last month for you — reading for it is the part of the signature that is yours.",
                "\"Có làm thêm giờ: Có\" và +2,7% là manh mối của bạn. Hãy mở những phiếu có nhiều tăng ca nhất trước, rồi lấy mẫu hai ba phiếu bình thường. Payobook sẽ không đánh dấu hộ bạn một mức tăng lớn so với tháng trước — đọc ra điều đó là phần chữ ký thuộc về bạn."),
      },
      {
        screen: "payslips", anchor: "ps-breakdown",
        kicker: B("Before & after", "Trước & sau"),
        title: B("Explain the change, or you are not ready to sign", "Giải thích được biến động, nếu không thì bạn chưa nên ký"),
        body: B("July is 612,480,000 ₫ against June's 596,110,000 ₫. Toggle the two and say out loud why they differ: one more employee, and Hùng's 3,100,000 ₫ more overtime. If you cannot finish that sentence, the gap is not small — it is unexamined.",
                "Tháng 7 là 612.480.000 ₫ so với 596.110.000 ₫ của tháng 6. Hãy chuyển qua lại hai bên và nói thành lời vì sao chúng khác nhau: thêm một nhân viên, và phần tăng ca nhiều hơn 3.100.000 ₫ của Hùng. Nếu bạn chưa nói trọn được câu đó thì khoảng chênh này không nhỏ — nó chỉ là chưa được soi tới."),
        moment: { kind: "morph", which: "runJuneJuly" },
      },
      {
        screen: "approvals", anchor: "ai-sendback",
        kicker: B("If it needs fixing", "Nếu cần sửa"),
        title: B("Send it back — with a note someone can act on", "Trả lại — kèm ghi chú người khác xử lý được"),
        body: B("<b>Send it back</b> asks \"What should change?\" The run goes back to <b>Draft</b>, its payslips become editable, and your note sits on its card. Fixed and sent in again, it starts the route from the first step. \"Payslip NV0031 — overtime is 382% of June; please check the timesheet\" is a note. \"Wrong\" is not.",
                "<b>Trả lại</b> sẽ hỏi \"Cần thay đổi điều gì?\" Đợt lương quay về <b>Nháp</b>, các phiếu lương sửa được, và ghi chú của bạn nằm ngay trên thẻ của nó. Sau khi sửa và gửi lại, nó đi lại lộ trình từ bước đầu tiên. \"Phiếu NV0031 — tăng ca bằng 382% tháng 6; vui lòng đối chiếu bảng chấm công\" là một ghi chú. \"Sai\" thì không."),
      },
      {
        screen: "approvals", anchor: "ai-turndown",
        kicker: B("The hard part", "Phần khó"),
        title: B("Turn it down ends it", "Từ chối là kết thúc"),
        body: B("<b>Turn it down</b> asks \"Why? (required)\" and ends the request. For a pay run that means the run is <b>Rejected</b> and every payslip in it is cancelled, with your reason on the record. It does not come back; a new run has to be made. When a correction would be enough, send it back instead.",
                "<b>Từ chối</b> sẽ hỏi \"Lý do? (bắt buộc)\" và kết thúc yêu cầu. Với một đợt lương, điều đó nghĩa là đợt lương <b>Đã từ chối</b> và mọi phiếu lương trong đó bị huỷ, kèm lý do của bạn trong hồ sơ. Nó không quay lại; phải tạo một đợt mới. Khi chỉ cần sửa là đủ, hãy trả lại thay vì từ chối."),
        consequence: B("Affects the whole run: every payslip is cancelled together. Reversible: <b>no</b> — the run stays rejected. Nothing was paid. Verify first: that the run should not be paid at all, not just corrected.",
                       "Ảnh hưởng cả đợt lương: mọi phiếu lương cùng bị huỷ. Hoàn tác: <b>không</b> — đợt lương giữ nguyên trạng thái bị từ chối. Chưa có gì được chi. Kiểm tra trước: đợt này thực sự không nên được chi, chứ không chỉ cần sửa."),
      },
      {
        screen: "approvals", anchor: "ai-move",
        kicker: B("Stuck?", "Bị tắc?"),
        title: B("Move it to somebody else, or Withdraw it", "Chuyển cho người khác, hoặc Thu hồi"),
        body: B("If the person on a step is away, whoever looks after the workflow can <b>Move it to somebody else</b> — with a reason. The person who sent it in can <b>Withdraw it</b>; a withdrawn pay run goes back to Draft, unchanged, to be sent in again when it is ready.",
                "Nếu người ở một bước đang vắng, người phụ trách luồng phê duyệt có thể <b>Chuyển cho người khác</b> — kèm lý do. Người đã gửi có thể <b>Thu hồi</b>; một đợt lương bị thu hồi quay về Nháp, giữ nguyên, để gửi lại khi đã sẵn sàng."),
      },
      {
        screen: "approvals", anchor: "ai-approve",
        kicker: B("Before you act", "Trước khi thao tác"),
        title: B("Approving is a signature, and it moves real money", "Phê duyệt là một chữ ký, và nó làm tiền thật dịch chuyển"),
        body: B("<b>Approve</b> records your name, the time, and exactly the facts above. It moves all 48 payslips one step closer to being paid, together — there is no way to approve some of them. Finance approval comes after you and reads totals. If a wrong line is going to be caught, this is one of the last places.",
                "<b>Phê duyệt</b> ghi lại tên bạn, thời điểm, và đúng các dữ kiện ở trên. Nó đưa cả 48 phiếu lương tiến thêm một bước tới lúc được chi, tất cả cùng lúc — không có cách nào duyệt một phần. Bước Tài chính phê duyệt sau bạn đọc các con số tổng. Nếu một dòng sai còn có thể bị bắt, đây là một trong những nơi cuối cùng."),
        consequence: B("Affects the whole run: it moves to Finance approval. Reversible: <b>stoppable, not undoable</b> — a later step can still send it back or turn it down; after Done, a correction is a retro line. Verify first: the payslips with the most overtime opened, a few ordinary ones sampled, and a one-sentence reason for the change on last month.",
                       "Ảnh hưởng cả đợt lương: nó chuyển sang bước Tài chính phê duyệt. Hoàn tác: <b>chặn được, không lùi lại được</b> — bước sau vẫn có thể trả lại hoặc từ chối; sau khi Hoàn tất, mọi hiệu chỉnh là một dòng hồi tố. Kiểm tra trước: đã mở những phiếu nhiều tăng ca nhất, lấy mẫu vài phiếu bình thường, và nói được trong một câu vì sao con số thay đổi so với tháng trước."),
      },
    ],
    quiz: {
      question: B("A pay run is your turn. It is 2.7% above last month, it contains overtime, nobody has opened the payslips, and payday is {{payDay}}. What do you do?",
                  "Một đợt lương đang đến lượt bạn. Nó cao hơn tháng trước 2,7%, có làm thêm giờ, chưa ai mở các phiếu lương, và ngày trả lương là {{payDay}}. Bạn làm gì?"),
      options: [
        {
          text: B("Approve — 2.7% against last month is well within normal", "Phê duyệt — 2,7% so với tháng trước là hoàn toàn bình thường"),
          correct: false,
          explanation: B("Let's rethink that. A total that looks reasonable is not evidence that every payslip inside it is: 3,100,000 ₫ of extra overtime on one person sits comfortably inside a 2.7% move.",
                         "Hãy nghĩ lại một chút. Tổng trông hợp lý không phải bằng chứng rằng từng phiếu bên trong đều hợp lý: 3.100.000 ₫ tăng ca thêm của một người nằm gọn trong mức biến động 2,7%."),
        },
        {
          text: B("Open the payslips with the most overtime, then approve — or send it back with a note that names what to check", "Mở những phiếu nhiều tăng ca nhất, rồi phê duyệt — hoặc trả lại kèm ghi chú nêu rõ cần kiểm tra gì"),
          correct: true,
          explanation: B("Yes. Minutes of reading, then a decision you can explain. If something is off, Send it back returns the run to Draft with your note — fast to fix, nothing cancelled.",
                         "Đúng vậy. Vài phút đọc, rồi một quyết định bạn giải thích được. Nếu có gì chưa ổn, Trả lại đưa đợt lương về Nháp kèm ghi chú của bạn — sửa nhanh, không có gì bị huỷ."),
        },
        {
          text: B("Turn it down so the preparer re-checks everything", "Từ chối để người lập kiểm tra lại toàn bộ"),
          correct: false,
          explanation: B("Let's rethink that. Turn it down CANCELS the run and every payslip in it — the preparer cannot just fix it, they have to make a new run. To have something checked, send it back with a note.",
                         "Hãy nghĩ lại một chút. Từ chối sẽ HUỶ đợt lương và mọi phiếu lương trong đó — người lập không thể chỉ sửa, họ phải tạo một đợt mới. Muốn có người kiểm tra lại, hãy trả lại kèm ghi chú."),
        },
      ],
    },
  },

  /* ===========================================================================
     LEARN REFRESH step 3 — PAYROLL SETUP. Six lessons over the setup replicas
     (engine/screens.js). Two hero moments: the guided setup's pay panel ticks
     when a component is added (`tick`), and Mai's base salary travels the
     Mapping Journey lane by lane into her payslip line (four `trace` steps).
     Numbers on the replicas are derived in practice-data.js; the prose names
     no money figure it would have to keep in step with them.
     ======================================================================== */
  L7: {
    id: "L7", station: "blueprint", mins: 8,
    title: B("Build a pay scheme, step by step", "Dựng một chương trình lương, từng bước một"),
    goal: B("Set up a new pay scheme in the guided setup, know what each of the six steps decides, and know what Finish does and does not do.",
            "Thiết lập một chương trình lương mới trong phần thiết lập có hướng dẫn, biết mỗi bước trong sáu bước quyết định điều gì, và biết Hoàn thành làm gì và không làm gì."),
    steps: [
      {
        screen: "blueprint", anchor: "bp-rail",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Six steps, one pay scheme", "Sáu bước, một chương trình lương"),
        body: B("Settings › Guided setup › New configuration. <b>Start</b>, <b>Pay rules</b>, <b>Connect</b>, <b>Outputs</b>, <b>Test</b>, <b>Finish</b>. A step you have finished gets a tick. You can go back to any of them.",
                "Cài đặt › Thiết lập có hướng dẫn › Cấu hình mới. <b>Bắt đầu</b>, <b>Quy tắc lương</b>, <b>Kết nối</b>, <b>Đầu ra</b>, <b>Kiểm thử</b>, <b>Hoàn thành</b>. Bước nào xong sẽ có dấu tích. Bạn có thể quay lại bất kỳ bước nào."),
        tip: B("A scheme's own Settings opens this same journey to edit it. The rail then says Editing.",
               "Phần Cài đặt của một chương trình lương mở lại đúng hành trình này để sửa. Khi đó thanh bước ghi Đang sửa."),
      },
      {
        screen: "blueprint", anchor: "bp-identity",
        kicker: B("Start", "Bắt đầu"),
        title: B("Name it so people can find it", "Đặt tên để mọi người tìm được"),
        body: B("Pick the <b>company</b> and give the configuration a <b>name</b> that says where and who it pays. Then choose the <b>pay cycle</b>: Regular payroll, Mid-month advance, End-month payroll, or Full and final. <b>Effective from</b> is the first pay period it is meant for.",
                "Chọn <b>công ty</b>, đặt <b>tên</b> cấu hình nói rõ trả lương ở đâu và cho ai, rồi chọn <b>chu kỳ thanh toán</b>: Kỳ lương thường, Tạm ứng giữa tháng, Kỳ lương cuối tháng, hoặc Thanh toán nghỉ việc. <b>Có hiệu lực từ</b> là kỳ lương đầu tiên nó dành cho."),
      },
      {
        screen: "blueprint", anchor: "bp-country",
        kicker: B("Start", "Bắt đầu"),
        title: B("The country decides the money", "Quốc gia quyết định đồng tiền"),
        body: B("As you choose the country, a chip says what the scheme pays in — <b>Pays in ₫ VND</b> here. The country also decides the insurance and tax rules. An amber line appears when that money has no exchange rate yet.",
                "Khi bạn chọn quốc gia, một nhãn cho biết chương trình trả lương bằng gì — ở đây là <b>Trả bằng ₫ VND</b>. Quốc gia còn quyết định các quy tắc bảo hiểm và thuế. Một dòng màu vàng hiện ra khi đồng tiền đó chưa có tỷ giá."),
        consequence: B("Affects every payslip the scheme will ever make. Reversible: only until it has components or payslips — then the country locks. Verify first: the country is where these people are paid, not where head office is.",
                       "Ảnh hưởng: mọi phiếu lương mà chương trình sẽ tạo ra. Hoàn tác: chỉ khi nó chưa có thành phần hay phiếu lương — sau đó quốc gia bị khoá. Kiểm tra trước: quốc gia là nơi những người này được trả lương, không phải nơi đặt trụ sở."),
      },
      {
        screen: "blueprint", anchor: "bp-starters",
        kicker: B("Start", "Bắt đầu"),
        title: B("Start from something, not from nothing", "Bắt đầu từ một thứ có sẵn, không phải từ con số không"),
        body: B("<b>How would you like to start?</b> A ready-made library for the country (Complete or Essentials), your own Excel workbook, or a blank canvas. <b>Certified</b> means Payobook has checked that library against the law; <b>Draft</b> means not yet.",
                "<b>Bạn muốn bắt đầu như thế nào?</b> Một thư viện dựng sẵn cho quốc gia (Đầy đủ hoặc Cơ bản), sổ tính Excel của chính bạn, hoặc một trang trắng. <b>Được chứng nhận</b> nghĩa là Payobook đã đối chiếu thư viện đó với luật; <b>Nháp</b> là chưa."),
      },
      {
        screen: "blueprint", anchor: "bp-audience",
        kicker: B("Start", "Bắt đầu"),
        title: B("Who you pay, and the months that are not ordinary", "Bạn trả lương cho ai, và những tháng không bình thường"),
        body: B("<b>Who are you paying?</b> decides which components and which sample people the next steps offer. <b>Real life belongs in the design</b> asks about joiners and leavers, yearly bonuses, mid-month raises and corrections — so they come up now, not on payday.",
                "<b>Bạn đang trả lương cho ai?</b> quyết định các bước sau gợi ý thành phần nào và người mẫu nào. <b>Đời thực phải có trong thiết kế</b> hỏi về người mới vào và người nghỉ, thưởng hằng năm, tăng lương giữa tháng và các khoản điều chỉnh — để chúng được tính tới ngay bây giờ, không phải vào ngày trả lương."),
      },
      {
        screen: "blueprint", anchor: "bp-status",
        kicker: B("Saving", "Lưu"),
        title: B("Nothing exists until you continue", "Chưa có gì cho tới khi bạn bấm tiếp tục"),
        body: B("Before the first <b>Continue to pay rules</b> the pill says <b>Not saved yet</b>. That press creates the draft, and from then on it saves as you go: <b>Draft · saved 2 min ago</b>. <b>Save &amp; close</b> keeps it; <b>Discard this draft</b> removes it.",
                "Trước lần bấm <b>Tiếp tục sang Quy tắc lương</b> đầu tiên, nhãn trạng thái ghi <b>Chưa lưu</b>. Lần bấm đó tạo bản nháp, và từ đó mọi thứ tự lưu khi bạn làm: <b>Bản nháp · đã lưu 2 phút trước</b>. <b>Lưu và đóng</b> giữ lại; <b>Bỏ bản nháp này</b> xoá nó đi."),
      },
      {
        screen: "blueprint_rules", anchor: "rep-bp-added",
        moment: { kind: "tick", from: "rep-bp-paynum" },
        kicker: B("Pay rules · the moment", "Quy tắc lương · khoảnh khắc"),
        title: B("Add a component, watch the pay move", "Thêm một thành phần, xem tiền lương thay đổi"),
        body: B("Each component is a sentence anyone can read, with its formula under it. Add <b>Allowances</b> and look at the panel: take-home pay rises by the allowance, less the income tax on it.",
                "Mỗi thành phần là một câu ai cũng đọc được, kèm công thức bên dưới. Thêm <b>Phụ cấp</b> rồi nhìn sang khung bên phải: tiền thực nhận tăng đúng bằng khoản phụ cấp, trừ đi phần thuế thu nhập trên nó."),
        tip: B("That is the real payroll engine working on one sample person. If a number surprises you here, it would have surprised a whole payroll.",
               "Đó là chính bộ máy tính lương đang tính cho một người mẫu. Nếu một con số làm bạn bất ngờ ở đây, nó đã có thể làm cả bảng lương bất ngờ."),
      },
      {
        screen: "blueprint_rules", anchor: "bp-pay",
        kicker: B("See it in someone's pay", "Xem ngay trên lương của một người"),
        title: B("One person, read the whole way through", "Một người, đọc từ đầu đến cuối"),
        body: B("The panel shows <b>Estimated take-home pay</b>, then cash earnings, employee deductions, income tax and employer cost. <b>Try a different situation</b> switches the sample person; <b>Adjust sample inputs</b> changes their figures. It is sample data only — nobody is paid from it.",
                "Khung này hiện <b>Thực nhận ước tính</b>, rồi thu nhập bằng tiền, các khoản trừ của nhân viên, thuế thu nhập và chi phí doanh nghiệp. <b>Thử một tình huống khác</b> đổi người mẫu; <b>Điều chỉnh đầu vào mẫu</b> đổi số liệu của họ. Đây chỉ là dữ liệu mẫu — không ai được trả lương từ nó."),
      },
      {
        screen: "blueprint_rules", anchor: "bp-foot",
        kicker: B("Connect · Outputs · Test · Finish", "Kết nối · Đầu ra · Kiểm thử · Hoàn thành"),
        title: B("Finish is not the same as switching it on", "Hoàn thành không phải là bật lên"),
        body: B("<b>Connect</b> says where values come from and who approves. <b>Outputs</b> lists every formula. <b>Test</b> runs the awkward cases. <b>Finish</b> means the setup is complete and checked. Putting the scheme live is a separate proposal, and it may need approval.",
                "<b>Kết nối</b> cho biết giá trị đến từ đâu và ai phê duyệt. <b>Đầu ra</b> liệt kê mọi công thức. <b>Kiểm thử</b> chạy các trường hợp khó. <b>Hoàn thành</b> nghĩa là việc thiết lập đã xong và đã kiểm tra. Đưa chương trình vào dùng là một đề xuất riêng, và có thể cần phê duyệt."),
        tip: B("Finish refuses while a calculation is broken or the checks have not been run since your last change. It says which.",
               "Hoàn thành sẽ từ chối khi còn một phép tính bị lỗi hoặc các bước kiểm tra chưa chạy lại từ lần sửa cuối. Nó nói rõ là cái nào."),
      },
    ],
    quiz: {
      question: B("You pressed Finish and the page says \"This setup is complete\". Is the scheme paying people now?",
                  "Bạn đã bấm Hoàn thành và trang ghi \"Thiết lập này đã hoàn tất\". Chương trình lương này đã trả lương cho mọi người chưa?"),
      options: [
        {
          text: B("Yes — Finish is the last step, so it is live", "Rồi — Hoàn thành là bước cuối nên nó đã chạy"),
          correct: false,
          explanation: B("Let's rethink that. Finish says the setup is complete and checked. Putting it live is a separate proposal — and when your company has a route for it, somebody has to approve it first.",
                         "Hãy nghĩ lại một chút. Hoàn thành nói rằng việc thiết lập đã xong và đã kiểm tra. Đưa vào dùng là một đề xuất riêng — và khi công ty bạn có lộ trình cho việc đó, phải có người phê duyệt trước."),
        },
        {
          text: B("Not yet — putting it live is a separate step, which may need approval", "Chưa — đưa vào dùng là một bước riêng, có thể cần phê duyệt"),
          correct: true,
          explanation: B("Yes. Finish means ready. Going live is its own decision, recorded — and approved first when a route covers it.",
                         "Đúng vậy. Hoàn thành nghĩa là sẵn sàng. Đưa vào dùng là một quyết định riêng, được ghi lại — và được phê duyệt trước khi có lộ trình áp cho nó."),
        },
        {
          text: B("Only for the sample employee", "Chỉ cho nhân viên mẫu"),
          correct: false,
          explanation: B("Let's rethink that. The sample person is never paid — the panel is a preview. Nobody is paid from this scheme until it is put live.",
                         "Hãy nghĩ lại một chút. Người mẫu không bao giờ được trả lương — khung đó chỉ là bản xem trước. Chưa ai được trả lương từ chương trình này cho tới khi nó được đưa vào dùng."),
        },
      ],
    },
  },

  L8: {
    id: "L8", station: "mapping", mins: 9,
    title: B("Follow a number to its source", "Lần theo một con số về tận nguồn"),
    goal: B("Read the Mapping Journey from a source to a payslip line. Know which source wins when there are two, and what the spreadsheet tab does.",
            "Đọc Hành trình ánh xạ từ một nguồn tới một dòng phiếu lương, biết nguồn nào thắng khi có hai nguồn, và biết tab bảng tính làm gì và không làm gì."),
    steps: [
      {
        screen: "mapping", anchor: "mp-story",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("FROM a source, TO a scheme", "TỪ một nguồn, ĐẾN một chương trình lương"),
        body: B("Settings › Integrations › Mapping. The header reads as a sentence: <b>FROM</b> a source <b>TO</b> a pay scheme, with how many values are fed between them. Both ends are pickers. The tabs below show each kind of wire; it opens on <b>Journey</b>.",
                "Cài đặt › Tích hợp › Ánh xạ. Phần đầu đọc như một câu: <b>TỪ</b> một nguồn <b>ĐẾN</b> một chương trình lương, kèm số giá trị đã được cấp giữa chúng. Cả hai đầu đều chọn được. Các tab bên dưới cho thấy từng loại dây nối; màn hình mở ở tab <b>Hành trình</b>."),
      },
      {
        screen: "mapping", anchor: "mp-lanes",
        kicker: B("The Journey", "Hành trình"),
        title: B("Five lanes, left to right", "Năm làn, từ trái sang phải"),
        body: B("<b>Files &amp; systems</b>, <b>Feeds</b>, <b>Transformations</b>, the <b>Scheme</b>, and <b>Payobook Source</b>. The line above counts what needs a source, what is fed and what is not fed yet. Press a card to open its fields.",
                "<b>Tệp &amp; hệ thống</b>, <b>Nguồn cấp dữ liệu</b>, <b>Chuyển đổi</b>, <b>Chương trình lương</b>, và <b>Nguồn Payobook</b>. Dòng phía trên đếm những gì cần một nguồn, đã có nguồn và chưa có nguồn. Bấm một thẻ để mở các trường của nó."),
      },
      {
        screen: "mapping", anchor: "rep-jny-feed",
        moment: { kind: "trace", from: "rep-jny-file", to: "rep-jny-feed" },
        kicker: B("Follow one value · 1", "Lần theo một giá trị · 1"),
        title: B("Mai's base salary leaves the HR system", "Lương cơ bản của Mai rời hệ thống nhân sự"),
        body: B("The connected HR system sends <b>basic_salary</b>. It arrives through a feed — one of the requests Payobook makes to that system.",
                "Hệ thống nhân sự đã kết nối gửi <b>basic_salary</b>. Nó đi vào qua một nguồn cấp dữ liệu — một trong các yêu cầu Payobook gửi tới hệ thống đó."),
      },
      {
        screen: "mapping", anchor: "rep-jny-xform",
        moment: { kind: "trace", from: "rep-jny-feed", to: "rep-jny-xform" },
        kicker: B("Follow one value · 2", "Lần theo một giá trị · 2"),
        title: B("A transformation makes it an amount", "Một phép chuyển đổi biến nó thành số tiền"),
        body: B("The system sends the salary as text. A <b>transformation</b> rule turns \"12.000.000\" into a number the formulas can use.",
                "Hệ thống gửi lương dưới dạng chữ. Một <b>quy tắc chuyển đổi</b> biến \"12.000.000\" thành một con số mà các công thức dùng được."),
      },
      {
        screen: "mapping", anchor: "rep-jny-scheme",
        moment: { kind: "trace", from: "rep-jny-xform", to: "rep-jny-scheme" },
        kicker: B("Follow one value · 3", "Lần theo một giá trị · 3"),
        title: B("It feeds a component of the scheme", "Nó cấp cho một thành phần của chương trình lương"),
        body: B("The amount lands on <b>LCB</b>, the base salary component. That card is now fed. A component marked <b>not fed</b> will be computed as empty.",
                "Số tiền đi vào <b>LCB</b>, thành phần lương cơ bản. Thẻ đó giờ đã có nguồn. Thành phần nào ghi <b>chưa có nguồn</b> sẽ được tính là trống."),
      },
      {
        screen: "mapping", anchor: "rep-jny-slip",
        moment: { kind: "trace", from: "rep-jny-scheme", to: "rep-jny-slip" },
        kicker: B("Follow one value · 4", "Lần theo một giá trị · 4"),
        title: B("…and ends on her payslip", "…và kết thúc trên phiếu lương của cô ấy"),
        body: B("When the run computes, LCB becomes the <b>Base salary</b> line on Mai's payslip. That is the whole road. When a number on a payslip looks wrong, walk it backwards, lane by lane.",
                "Khi đợt lương được tính, LCB trở thành dòng <b>Lương cơ bản</b> trên phiếu lương của Mai. Đó là cả chặng đường. Khi một con số trên phiếu lương trông sai, hãy đi ngược lại, từng làn một."),
      },
      {
        screen: "mapping", anchor: "rep-jny-source",
        kicker: B("Payobook Source", "Nguồn Payobook"),
        title: B("Values that come from Payobook itself", "Những giá trị đến từ chính Payobook"),
        body: B("Some values are already in Payobook: the employee, the contract, the bank account, contract pay components, and the pay run itself. <b>Open Records Desk</b> changes them for many people at once. <b>Who is paid by what</b> says which scheme pays each team.",
                "Một số giá trị đã có sẵn trong Payobook: nhân viên, hợp đồng, tài khoản ngân hàng, thành phần lương theo hợp đồng, và chính đợt lương. <b>Mở Records Desk</b> để sửa chúng cho nhiều người cùng lúc. <b>Ai được trả lương theo phương án nào</b> cho biết chương trình nào trả lương cho từng nhóm."),
      },
      {
        screen: "mapping_sheet", anchor: "mp-ramp",
        kicker: B("Spreadsheet columns → Scheme", "Cột bảng tính → Chương trình lương"),
        title: B("The file shows its columns. It imports nothing.", "Tệp cho thấy các cột của nó. Nó không nhập gì cả."),
        body: B("Drop this period's spreadsheet and the tab reads its <b>headings and one example row</b>, so you can wire columns to components. Numbers come in later, through the pay run's Pay data step. A group called <b>From this pay run</b> offers values the run already knows, like standard working days.",
                "Thả bảng tính của kỳ này và tab sẽ đọc <b>tiêu đề và một dòng ví dụ</b>, để bạn nối cột vào thành phần. Số liệu vào sau, qua bước Dữ liệu lương của đợt lương. Một nhóm tên <b>Từ đợt lương này</b> đưa ra các giá trị đợt lương đã biết, như ngày công chuẩn."),
        tip: B("No file in the right shape? Download a template built from this scheme.",
               "Chưa có tệp đúng mẫu? Hãy tải mẫu dựng từ chương trình lương này."),
      },
      {
        screen: "mapping_sheet", anchor: "rep-mp-conflict",
        kicker: B("Two sources, one component", "Hai nguồn, một thành phần"),
        title: B("A lower source only fills an empty box", "Nguồn thấp hơn chỉ điền vào ô trống"),
        body: B("Wire a column to a component the system already feeds, and Payobook asks first. <b>Add source</b> keeps both, in order: the higher source wins and the lower one only fills a box left empty. Or use one source instead of the other.",
                "Nối một cột vào thành phần mà hệ thống đã cấp, Payobook sẽ hỏi trước. <b>Thêm nguồn</b> giữ cả hai, theo thứ tự: nguồn cao hơn thắng và nguồn thấp hơn chỉ điền vào ô còn trống. Hoặc dùng một nguồn thay cho nguồn kia."),
        consequence: B("Affects every future pay run of this scheme. Reversible: yes — change the wires or the order. Verify first: which source should win when both have a value.",
                       "Ảnh hưởng: mọi đợt lương sau này của chương trình. Hoàn tác: có — đổi dây nối hoặc thứ tự. Kiểm tra trước: nguồn nào nên thắng khi cả hai cùng có giá trị."),
      },
    ],
    quiz: {
      question: B("Allowances are fed by the HR system and by a spreadsheet column, in that order. This month the system sent a value and the file has a different one. Which reaches the payslip?",
                  "Phụ cấp được cấp bởi hệ thống nhân sự và bởi một cột bảng tính, theo thứ tự đó. Tháng này hệ thống gửi một giá trị và tệp có giá trị khác. Giá trị nào vào phiếu lương?"),
      options: [
        {
          text: B("The system's value — the spreadsheet only fills an empty box", "Giá trị của hệ thống — bảng tính chỉ điền vào ô trống"),
          correct: true,
          explanation: B("Yes. The higher source wins. The spreadsheet is used only for people the system sent nothing for.",
                         "Đúng vậy. Nguồn cao hơn thắng. Bảng tính chỉ được dùng cho những người mà hệ thống không gửi gì."),
        },
        {
          text: B("The two are added together", "Hai giá trị được cộng lại"),
          correct: false,
          explanation: B("Let's rethink that. Two sources never add up. One value reaches the component, and the order decides which.",
                         "Hãy nghĩ lại một chút. Hai nguồn không bao giờ được cộng lại. Chỉ một giá trị đi vào thành phần, và thứ tự quyết định giá trị nào."),
        },
        {
          text: B("Whichever arrived last", "Giá trị nào đến sau cùng"),
          correct: false,
          explanation: B("Let's rethink that. Timing does not decide it. The order of the sources does, and it is the same every month.",
                         "Hãy nghĩ lại một chút. Thời điểm không quyết định điều này. Thứ tự các nguồn mới quyết định, và nó giống nhau mọi tháng."),
        },
      ],
    },
  },

  L9: {
    id: "L9", station: "treatment", mins: 6,
    title: B("Tell the scheme what each component is", "Cho chương trình lương biết mỗi thành phần là gì"),
    goal: B("Read the Component treatment board, set a pay role, a subtotal and a value type correctly, and know why a run says its figures do not add up.",
            "Đọc bảng Xử lý thành phần, đặt đúng vai trò trong lương, tổng phụ và loại giá trị, và biết vì sao một đợt lương báo số liệu không khớp."),
    steps: [
      {
        screen: "treatment", anchor: "tr-head",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("One board per scheme, for every run", "Mỗi chương trình một bảng, cho mọi đợt lương"),
        body: B("Mapping › <b>Component treatment</b>. Set once per component, it holds however the value arrives. It belongs to the scheme, so a change affects every run of it. <b>Re-classify from the formulas</b> works the answers out again and leaves rows you set yourself alone.",
                "Ánh xạ › <b>Xử lý thành phần</b>. Đặt một lần cho mỗi thành phần, và giữ nguyên dù giá trị đến bằng đường nào. Nó thuộc về chương trình lương, nên một thay đổi ảnh hưởng mọi đợt lương của chương trình đó. <b>Phân loại lại từ các công thức</b> tính lại các câu trả lời và để nguyên những dòng bạn tự đặt."),
      },
      {
        screen: "treatment", anchor: "tr-table",
        kicker: B("Pay role", "Vai trò trong lương"),
        title: B("The pay role decides the arithmetic", "Vai trò trong lương quyết định phép tính"),
        body: B("<b>Added to net pay</b>, <b>Taken off net pay</b>, <b>Net pay itself</b>, <b>Employer cost</b>, <b>Information only</b>, or <b>Both added and taken off</b>. Gross, deductions and net on every report are counted from this column.",
                "<b>Cộng vào thực nhận</b>, <b>Trừ khỏi thực nhận</b>, <b>Chính là thực nhận</b>, <b>Chi phí doanh nghiệp</b>, <b>Chỉ để tham khảo</b>, hoặc <b>Vừa cộng vừa trừ</b>. Tổng thu nhập, khấu trừ và thực nhận trên mọi báo cáo đều được đếm từ cột này."),
      },
      {
        screen: "treatment", anchor: "tr-table",
        kicker: B("Subtotal", "Tổng phụ"),
        title: B("A subtotal is already inside another line", "Tổng phụ đã nằm sẵn trong một dòng khác"),
        body: B("Gross income is base salary plus allowances plus overtime. Those are already added, so gross carries a tick under <b>Subtotal</b>. Without it, the totals would count the same money twice.",
                "Tổng thu nhập là lương cơ bản cộng phụ cấp cộng tăng ca. Những khoản đó đã được cộng rồi, nên tổng thu nhập có dấu tích ở cột <b>Tổng phụ</b>. Không có dấu đó, các tổng sẽ tính cùng một khoản tiền hai lần."),
      },
      {
        screen: "treatment", anchor: "rep-ct-warn",
        kicker: B("Value type", "Loại giá trị"),
        title: B("Hours are not money", "Giờ không phải là tiền"),
        body: B("A <b>value type</b> says what a value is: an amount, a quantity like hours or days, a percentage, text or a date. Only an amount can be added to or taken off net pay. When a quantity is set to add to net pay, the board warns you and offers <b>Set all of them to Information only</b>.",
                "<b>Loại giá trị</b> cho biết một giá trị là gì: số tiền, số lượng như giờ hoặc ngày, phần trăm, chữ hay ngày tháng. Chỉ số tiền mới được cộng vào hoặc trừ khỏi thực nhận. Khi một số lượng được đặt để cộng vào thực nhận, bảng sẽ cảnh báo và đề nghị <b>Đặt tất cả thành Chỉ để tham khảo</b>."),
      },
      {
        screen: "treatment", anchor: "tr-filters",
        kicker: B("What needs you", "Những gì cần bạn"),
        title: B("Needs your answer, and Type says otherwise", "Cần câu trả lời của bạn, và Loại giá trị nói khác"),
        body: B("The chips count what to look at. <b>Needs your answer</b> is a component with no pay role yet — a new column from a spreadsheet, say. <b>Type says otherwise</b> is a pay role the value type disagrees with.",
                "Các nhãn đếm những gì cần xem. <b>Cần câu trả lời của bạn</b> là thành phần chưa có vai trò trong lương — chẳng hạn một cột mới từ bảng tính. <b>Loại giá trị nói khác</b> là một vai trò mà loại giá trị không khớp."),
        tip: B("After an Excel workbook is imported, the same questions come up in a review window before the scheme is used.",
               "Sau khi nhập một sổ tính Excel, cũng những câu hỏi này hiện ra trong một cửa sổ xem lại trước khi chương trình được dùng."),
      },
      {
        screen: "treatment", anchor: "tr-head",
        kicker: B("The run's warning", "Cảnh báo của đợt lương"),
        title: B("\"These figures do not add up\" sends you here", "\"Các số liệu này không khớp\" đưa bạn tới đây"),
        body: B("When gross less deductions is not take-home pay, the pay run shows that line with the gap. Almost always a component is treated wrongly. Fix it here, save, then <b>recompute the run</b>.",
                "Khi tổng thu nhập trừ khấu trừ không bằng thực nhận, đợt lương hiện dòng đó kèm khoản chênh. Gần như luôn là một thành phần bị xử lý sai. Hãy sửa ở đây, lưu, rồi <b>tính lại đợt lương</b>."),
        consequence: B("Affects every run of this scheme, past and future, once recomputed. Reversible: yes — change the row back. Verify first: saving never rewrites a payslip; only a recompute does.",
                       "Ảnh hưởng: mọi đợt lương của chương trình, cũ và mới, khi được tính lại. Hoàn tác: có — đổi dòng đó lại. Kiểm tra trước: lưu không bao giờ viết lại phiếu lương; chỉ tính lại mới làm vậy."),
      },
    ],
    quiz: {
      question: B("Overtime hours come from a spreadsheet and are set to Added to net pay. What happens?",
                  "Giờ tăng ca lấy từ bảng tính và được đặt là Cộng vào thực nhận. Điều gì xảy ra?"),
      options: [
        {
          text: B("The hours are added to take-home pay as if they were money — the board warns you", "Số giờ bị cộng vào thực nhận như thể là tiền — bảng sẽ cảnh báo bạn"),
          correct: true,
          explanation: B("Yes. Twelve hours would be twelve đồng added to net. Hours reach pay through the overtime formula, so the hours themselves are Information only.",
                         "Đúng vậy. Mười hai giờ sẽ thành mười hai đồng cộng vào thực nhận. Giờ đi vào lương qua công thức tăng ca, nên bản thân số giờ chỉ để tham khảo."),
        },
        {
          text: B("Nothing — Payobook knows they are hours", "Không có gì — Payobook biết đó là giờ"),
          correct: false,
          explanation: B("Let's rethink that. The pay role is what the arithmetic follows. Payobook flags the clash with \"Type says otherwise\", but you have to fix it.",
                         "Hãy nghĩ lại một chút. Phép tính đi theo vai trò trong lương. Payobook báo sự lệch bằng \"Loại giá trị nói khác\", nhưng bạn phải là người sửa."),
        },
        {
          text: B("The overtime pay is doubled", "Tiền tăng ca bị nhân đôi"),
          correct: false,
          explanation: B("Let's rethink that. The overtime pay line is a separate component. The problem is the hours themselves being counted as money.",
                         "Hãy nghĩ lại một chút. Dòng tiền tăng ca là một thành phần riêng. Vấn đề là chính số giờ bị tính như tiền."),
        },
      ],
    },
  },

  L10: {
    id: "L10", station: "matrix", mins: 8,
    title: B("Decide who signs off what", "Quyết định ai phê duyệt việc gì"),
    goal: B("Read any approval route in the Approval Matrix, change one safely in the builder, and know what No approval needed and Publish really do.",
            "Đọc bất kỳ lộ trình phê duyệt nào trong Ma trận phê duyệt, sửa một lộ trình an toàn trong phần dựng lộ trình, và biết Không cần phê duyệt và Ban hành thật sự làm gì."),
    steps: [
      {
        screen: "matrix", anchor: "am-hero",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Every check, in one place", "Mọi bước kiểm tra, ở một nơi"),
        body: B("Settings › Approvals › <b>Approval Matrix</b>. Every request in the Approvals inbox follows a route drawn here. <b>Create a workflow</b> starts a new one; <b>Bring in from a spreadsheet</b> reads a sheet named \"Approval Matrix\" as draft routes.",
                "Cài đặt › Phê duyệt › <b>Ma trận phê duyệt</b>. Mọi yêu cầu trong hộp Phê duyệt đều đi theo một lộ trình vẽ ở đây. <b>Tạo một luồng phê duyệt</b> bắt đầu một lộ trình mới; <b>Nạp từ bảng tính</b> đọc trang tính tên \"Approval Matrix\" thành các lộ trình nháp."),
      },
      {
        screen: "matrix", anchor: "am-table",
        kicker: B("Read a route", "Đọc một lộ trình"),
        title: B("Process, route, where it applies, status", "Quy trình, lộ trình, nơi áp dụng, trạng thái"),
        body: B("Each row is one process with the route it follows. The pay run reads <b>Payroll check → HR lead review → Finance approval</b>. Status says <b>In use</b>, <b>Draft</b>, <b>Needs people</b> or <b>Not connected yet</b>.",
                "Mỗi dòng là một quy trình kèm lộ trình nó đi theo. Đợt lương ghi <b>Kiểm tra bảng lương → Trưởng nhân sự soát xét → Tài chính phê duyệt</b>. Trạng thái ghi <b>Đang dùng</b>, <b>Nháp</b>, <b>Cần bổ sung người</b> hoặc <b>Chưa kết nối</b>."),
        tip: B("Needs people means a step reaches a part of the business where nobody is named. Requests from there stop until somebody is.",
               "Cần bổ sung người nghĩa là có một bước đi tới một phần của doanh nghiệp mà chưa có ai được ghi tên. Yêu cầu từ đó sẽ dừng cho tới khi có người."),
      },
      {
        screen: "matrix", anchor: "am-bulk",
        kicker: B("No approval needed", "Không cần phê duyệt"),
        title: B("Switching a check off is still recorded", "Tắt một bước kiểm tra vẫn được ghi lại"),
        body: B("Any process can be set to <b>No approval needed</b>, one row or many at once. It then happens straight away — and every use still shows in History. <b>Undo</b> is offered straight after.",
                "Quy trình nào cũng có thể đặt <b>Không cần phê duyệt</b>, từng dòng hoặc nhiều dòng cùng lúc. Khi đó việc diễn ra ngay — và mỗi lần dùng vẫn hiện trong Lịch sử. <b>Hoàn tác</b> được đề nghị ngay sau đó."),
      },
      {
        screen: "matrix_builder", anchor: "rep-am-bsteps",
        kicker: B("The builder", "Dựng lộ trình"),
        title: B("Purpose · People · Safeguards · Review · Publish", "Mục đích · Nhân sự · Bảo vệ · Xem lại · Ban hành"),
        body: B("Open a row, or create a workflow, and the builder walks five steps. Nothing is live until the last one.",
                "Mở một dòng, hoặc tạo một luồng phê duyệt, phần dựng lộ trình sẽ đi qua năm bước. Chưa có gì được dùng cho tới bước cuối."),
      },
      {
        screen: "matrix_builder", anchor: "rep-am-route",
        kicker: B("People", "Nhân sự"),
        title: B("Kinds of step", "Các loại bước"),
        body: B("<b>Review</b>, <b>Final approval</b>, <b>Joint approval</b>, <b>Any one of a team</b>, and <b>Only when…</b> for a step above an amount. <b>Tell somebody</b> is never counted as a check. Name a responsibility, not a person, so the route survives a leaver.",
                "<b>Xem lại</b>, <b>Phê duyệt cuối</b>, <b>Cùng phê duyệt</b>, <b>Một người bất kỳ trong nhóm</b>, <b>Chỉ khi…</b> cho bước chỉ áp dụng trên một mức tiền, và <b>Báo cho ai đó</b>, không bao giờ được tính là một bước kiểm tra. Hãy ghi trách nhiệm, không ghi một người, để lộ trình vẫn chạy khi có người nghỉ."),
      },
      {
        screen: "matrix_builder", anchor: "rep-am-guards",
        kicker: B("Safeguards", "Bảo vệ"),
        title: B("The rules around the route", "Những quy tắc bao quanh lộ trình"),
        body: B("<b>Who may not decide?</b> <b>What must be attached?</b> <b>When is it due?</b> <b>And if it is late?</b> Then <b>Try an example</b> shows who, by name, would decide a real request.",
                "<b>Ai không được quyết định?</b> <b>Cần đính kèm gì?</b> <b>Khi nào đến hạn?</b> <b>Nếu trễ hạn thì sao?</b> Rồi <b>Thử một ví dụ</b> cho thấy ai, cụ thể tên, sẽ quyết định một yêu cầu thật."),
      },
      {
        screen: "matrix_builder", anchor: "rep-am-publish",
        kicker: B("Publish", "Ban hành"),
        title: B("New requests only", "Chỉ áp cho yêu cầu mới"),
        body: B("<b>Publish this route</b> and new requests follow it from the date shown. Requests already on their way finish the route they started on.",
                "<b>Ban hành lộ trình này</b> và các yêu cầu mới đi theo nó từ ngày được ghi. Những yêu cầu đang trên đường sẽ đi hết lộ trình chúng đã bắt đầu."),
        consequence: B("Affects every new request of this process. Reversible: yes — publish again. Verify first: Try an example names a real person for every step.",
                       "Ảnh hưởng: mọi yêu cầu mới của quy trình này. Hoàn tác: có — ban hành lại. Kiểm tra trước: Thử một ví dụ ra đúng tên một người thật cho mọi bước."),
      },
      {
        screen: "matrix", anchor: "am-tabs",
        kicker: B("People & backups", "Con người & người thay thế"),
        title: B("Cover for holidays, and a choice per scheme", "Người trực thay khi nghỉ, và lựa chọn cho từng chương trình lương"),
        body: B("<b>People &amp; backups</b> shows who holds each responsibility; <b>Arrange cover</b> hands it to someone while they are away. A pay scheme can also <b>Use the company flow</b>, use a different flow, or need no approval — chosen in its Connect step.",
                "<b>Con người &amp; người thay thế</b> cho biết ai giữ từng trách nhiệm; <b>Sắp xếp người trực thay</b> giao nó cho người khác khi họ vắng. Một chương trình lương cũng có thể <b>Dùng luồng của công ty</b>, dùng một luồng khác, hoặc không cần phê duyệt — chọn ở bước Kết nối của nó."),
      },
    ],
    quiz: {
      question: B("You add Finance approval to the pay run route and publish it. June's run is already waiting at HR lead review. What route does June's run follow?",
                  "Bạn thêm bước Tài chính phê duyệt vào lộ trình đợt lương rồi ban hành. Đợt lương tháng 6 đang chờ ở bước Trưởng nhân sự soát xét. Đợt tháng 6 đi theo lộ trình nào?"),
      options: [
        {
          text: B("The old one — publishing affects new requests only", "Lộ trình cũ — ban hành chỉ áp cho yêu cầu mới"),
          correct: true,
          explanation: B("Yes. June finishes the route it started on. July's run, sent in after you published, gets the new step.",
                         "Đúng vậy. Tháng 6 đi hết lộ trình nó đã bắt đầu. Đợt tháng 7, gửi đi sau khi bạn ban hành, sẽ có bước mới."),
        },
        {
          text: B("The new one, starting again from the first step", "Lộ trình mới, bắt đầu lại từ bước đầu"),
          correct: false,
          explanation: B("Let's rethink that. A published route never moves a request already on its way. Nobody's approval is thrown away.",
                         "Hãy nghĩ lại một chút. Một lộ trình vừa ban hành không bao giờ chuyển yêu cầu đang đi. Không phê duyệt nào của ai bị bỏ đi."),
        },
        {
          text: B("The new one, from where it is now", "Lộ trình mới, từ vị trí hiện tại"),
          correct: false,
          explanation: B("Let's rethink that. Requests keep the route they were sent in on. To get Finance to look at June, ask them — or send it back and in again.",
                         "Hãy nghĩ lại một chút. Yêu cầu giữ lộ trình mà nó được gửi đi. Muốn Tài chính xem tháng 6, hãy nhờ họ — hoặc trả lại rồi gửi lại."),
        },
      ],
    },
  },

  L11: {
    id: "L11", station: "records", mins: 7,
    title: B("Change many people at once, safely", "Sửa nhiều người cùng lúc, an toàn"),
    goal: B("Update employee, contract and bank fields for many people in the Records Desk, through the grid or a file, and know what Apply and Undo do.",
            "Cập nhật các trường nhân viên, hợp đồng và ngân hàng cho nhiều người trong Records Desk, qua lưới hoặc qua tệp, và biết Áp dụng và Hoàn tác làm gì."),
    steps: [
      {
        screen: "records", anchor: "rd-head",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("One desk for every bulk change", "Một bàn cho mọi thay đổi hàng loạt"),
        body: B("People › <b>Records</b>. The same desk opens from <b>Bulk update</b> on the employee list, from <b>Open Records Desk</b> in a pay run, and from Mapping's Payobook Source card.",
                "Con người › <b>Hồ sơ</b>. Cùng bàn làm việc này mở từ <b>Cập nhật hàng loạt</b> trên danh sách nhân viên, từ <b>Mở Records Desk</b> trong một đợt lương, và từ thẻ Nguồn Payobook trong Ánh xạ."),
      },
      {
        screen: "records", anchor: "rd-scheme",
        kicker: B("Only mapped fields", "Chỉ các trường đã ánh xạ"),
        title: B("It offers what your pay scheme reads", "Nó đưa ra những gì chương trình lương của bạn đọc"),
        body: B("Pick the pay scheme; the pill says how many fields it maps. The desk offers only those — a field no scheme reads cannot change anyone's pay, so it is not here. A scheme that maps nothing gets <b>Open Mapping</b> instead.",
                "Chọn chương trình lương; nhãn cho biết nó ánh xạ bao nhiêu trường. Bàn chỉ đưa ra những trường đó — trường nào không chương trình nào đọc thì không đổi được lương của ai, nên không có ở đây. Chương trình không ánh xạ gì sẽ thấy <b>Mở Ánh xạ</b>."),
      },
      {
        screen: "records", anchor: "rep-rd-grid",
        kicker: B("On screen", "Trên màn hình"),
        title: B("Pick who, pick what, type", "Chọn ai, chọn gì, rồi gõ"),
        body: B("Filter <b>Who</b> on the left, choose <b>Fields</b> across the top, then type into the grid. A changed cell is marked. Nothing is saved yet.",
                "Lọc <b>Ai</b> ở bên trái, chọn <b>Trường</b> ở phía trên, rồi gõ vào lưới. Ô nào đã sửa sẽ được đánh dấu. Chưa có gì được lưu."),
      },
      {
        screen: "records", anchor: "rd-file",
        kicker: B("Through a file", "Qua một tệp"),
        title: B("Export, edit, import", "Xuất, sửa, nhập"),
        body: B("<b>Export with data</b> gives you the people and fields on screen; <b>Export blank template</b> gives headings only. <b>Import a file</b> matches rows by employee code, work email or name, and shows Changes, Unmatched rows and Ignored columns before anything happens.",
                "<b>Xuất kèm dữ liệu</b> cho bạn những người và trường đang hiện; <b>Xuất mẫu trống</b> chỉ có tiêu đề. <b>Nhập một tệp</b> khớp dòng theo mã nhân viên, email công việc hoặc tên, và hiện Thay đổi, Dòng không khớp và Cột bị bỏ qua trước khi có gì xảy ra."),
      },
      {
        screen: "records", anchor: "rep-rd-reviewpanel",
        kicker: B("Review", "Xem lại"),
        title: B("Every change, from what to what", "Mọi thay đổi, từ gì sang gì"),
        body: B("<b>Review</b> lists each change with who, what it was and what it becomes. <b>Apply</b> then either writes at once, or — when your company has a route for bulk changes — says <b>Sent for approval</b> and names who has it.",
                "<b>Xem lại</b> liệt kê từng thay đổi: ai, giá trị cũ và giá trị mới. <b>Áp dụng</b> khi đó hoặc ghi ngay, hoặc — khi công ty bạn có lộ trình cho thay đổi hàng loạt — báo <b>Đã gửi phê duyệt</b> và ghi tên người đang giữ."),
        consequence: B("Affects every person listed, from the next pay run. Reversible: yes — Undo, from History. Verify first: the count of people matches what you meant to change.",
                       "Ảnh hưởng: mọi người trong danh sách, từ đợt lương kế tiếp. Hoàn tác: có — Hoàn tác trong Lịch sử. Kiểm tra trước: số người khớp với số bạn định sửa."),
      },
      {
        screen: "records", anchor: "rd-history",
        kicker: B("History", "Lịch sử"),
        title: B("Undo never expires", "Hoàn tác không bao giờ hết hạn"),
        body: B("Every apply is listed in <b>History</b> with an <b>Undo</b>. Undo skips any value somebody has changed since, rather than overwrite their work. If a value moved while a change waited for approval, the whole change is sent back to look at.",
                "Mỗi lần áp dụng đều có trong <b>Lịch sử</b> kèm nút <b>Hoàn tác</b>. Hoàn tác bỏ qua giá trị nào đã có người sửa sau đó, thay vì ghi đè lên việc của họ. Nếu một giá trị bị đổi trong lúc thay đổi đang chờ phê duyệt, cả thay đổi sẽ bị trả lại để xem."),
      },
    ],
    quiz: {
      question: B("You applied a raise for 40 people and the desk says \"Sent for approval — Đặng Thu Hà\". Will today's pay run pay the new salaries?",
                  "Bạn áp dụng tăng lương cho 40 người và bàn làm việc báo \"Đã gửi phê duyệt — Đặng Thu Hà\". Đợt lương hôm nay có trả mức lương mới không?"),
      options: [
        {
          text: B("Not yet — nothing changes until it is approved", "Chưa — chưa có gì thay đổi cho tới khi được duyệt"),
          correct: true,
          explanation: B("Yes. Sent for approval means the records still hold the old values. Once approved, the next computed run reads the new ones.",
                         "Đúng vậy. Đã gửi phê duyệt nghĩa là hồ sơ vẫn giữ giá trị cũ. Khi được duyệt, đợt lương được tính tiếp theo sẽ đọc giá trị mới."),
        },
        {
          text: B("Yes — Apply saved them", "Có — Áp dụng đã lưu chúng"),
          correct: false,
          explanation: B("Let's rethink that. Where a route covers bulk changes, Apply sends them for approval. The screen says which happened.",
                         "Hãy nghĩ lại một chút. Khi có lộ trình áp cho thay đổi hàng loạt, Áp dụng gửi chúng đi phê duyệt. Màn hình nói rõ điều nào đã xảy ra."),
        },
        {
          text: B("Only for the people Đặng Thu Hà manages", "Chỉ với những người Đặng Thu Hà quản lý"),
          correct: false,
          explanation: B("Let's rethink that. The change goes and comes back as one piece. It is approved for all 40, or for none.",
                         "Hãy nghĩ lại một chút. Thay đổi đi và về như một khối. Nó được duyệt cho cả 40 người, hoặc không ai cả."),
        },
      ],
    },
  },

  L12: {
    id: "L12", station: "schemes", mins: 7,
    title: B("Pay in more than one currency", "Trả lương bằng nhiều đồng tiền"),
    goal: B("Know where a pay scheme's currency comes from, why a pay run is always one scheme, and how the group reads two currencies without adding them together.",
            "Biết đồng tiền của một chương trình lương đến từ đâu, vì sao một đợt lương luôn là một chương trình, và tập đoàn đọc hai đồng tiền ra sao mà không cộng chúng lại."),
    steps: [
      {
        screen: "blueprint", anchor: "bp-country",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("A pay scheme pays in its country's money", "Chương trình lương trả bằng đồng tiền của quốc gia nó"),
        body: B("The currency is not a setting of its own. It follows the scheme's country, and the guided setup says it as you choose: <b>Pays in ₫ VND</b>. Everywhere a scheme's money is shown, it is read from here first.",
                "Đồng tiền không phải là một cài đặt riêng. Nó đi theo quốc gia của chương trình lương, và phần thiết lập có hướng dẫn nói rõ ngay khi bạn chọn: <b>Trả bằng ₫ VND</b>. Ở đâu hiện tiền của một chương trình, nó đều được đọc từ đây trước."),
      },
      {
        screen: "runpayroll", anchor: "pw-scheme",
        kicker: B("One run, one scheme", "Một đợt, một chương trình"),
        title: B("Two schemes in one month are two pay runs", "Hai chương trình trong một tháng là hai đợt lương"),
        body: B("Pay Run › Run starts with the scheme. A run is always one scheme, so it is always one currency. A company with two schemes this month runs two payrolls, each approved on its own.",
                "Đợt lương › Chạy lương bắt đầu bằng chương trình lương. Một đợt luôn là một chương trình, nên luôn chỉ có một đồng tiền. Công ty có hai chương trình trong tháng này sẽ chạy hai bảng lương, mỗi bảng được phê duyệt riêng."),
      },
      {
        screen: "schemes", anchor: "gp-tree",
        kicker: B("Settings › Group", "Cài đặt › Tập đoàn"),
        title: B("The companies, read as one business", "Các công ty, đọc như một doanh nghiệp"),
        body: B("<b>Your group</b> lists each company with its own currency and how many pay schemes it has. The group has a currency too — the money the group board reads in.",
                "<b>Tập đoàn của bạn</b> liệt kê từng công ty với đồng tiền riêng và số chương trình lương của nó. Tập đoàn cũng có một đồng tiền — đồng tiền mà bảng số liệu tập đoàn dùng để đọc."),
      },
      {
        screen: "schemes", anchor: "rep-gp-foot",
        kicker: B("The rule", "Nguyên tắc"),
        title: B("Nothing is stored converted", "Không có gì được lưu ở dạng đã quy đổi"),
        body: B("Every figure keeps the money it was paid in. The group currency is only a way of reading — converted when you look, never saved.",
                "Mỗi con số giữ nguyên đồng tiền đã trả. Đồng tiền tập đoàn chỉ là một cách đọc — quy đổi khi bạn xem, không bao giờ được lưu."),
      },
      {
        screen: "schemes", anchor: "gp-rates",
        kicker: B("Exchange rates", "Tỷ giá"),
        title: B("Which rate, for which month", "Tỷ giá nào, cho tháng nào"),
        body: B("<b>How rates are picked</b>: the last rate of the month, the rate on the day the pay run ends, or the average for the month. The strip shows which months have a rate. A rate change goes through approval.",
                "<b>Cách chọn tỷ giá</b>: tỷ giá cuối cùng của tháng, tỷ giá vào ngày đợt lương kết thúc, hoặc tỷ giá bình quân của tháng. Dải tháng cho biết tháng nào đã có tỷ giá. Thay đổi tỷ giá phải qua phê duyệt."),
      },
      {
        screen: "explorer", anchor: "ex-money",
        kicker: B("Insights › Explorer", "Phân tích › Khám phá dữ liệu"),
        title: B("Each in its own money, or the group's", "Mỗi bên theo đồng tiền của mình, hay theo tập đoàn"),
        body: B("<b>Compare schemes</b> lists every scheme side by side. <b>Each in its own money</b> keeps đồng and dollars apart and says so. <b>Group currency</b> converts them, so they can be added.",
                "<b>So sánh các chương trình lương</b> đặt mọi chương trình cạnh nhau. <b>Mỗi bên theo đồng tiền của mình</b> để đồng và đô la riêng rẽ và nói rõ điều đó. <b>Đồng tiền của tập đoàn</b> quy đổi chúng, để có thể cộng lại."),
      },
      {
        screen: "explorer", anchor: "rep-ex-compare",
        kicker: B("When there is no rate", "Khi không có tỷ giá"),
        title: B("Left out, and said so", "Để ra ngoài, và nói rõ"),
        body: B("A figure with no rate for its month is shown as <b>Not converted</b>, with the reason, and left out of the group total. Nothing is guessed. Turn on <b>Per person</b> to compare schemes of different sizes.",
                "Con số nào chưa có tỷ giá cho tháng của nó sẽ hiện là <b>Chưa quy đổi</b>, kèm lý do, và bị để ra ngoài tổng tập đoàn. Không có gì được đoán. Bật <b>Trên mỗi người</b> để so sánh các chương trình có quy mô khác nhau."),
      },
    ],
    quiz: {
      question: B("Your Vietnam scheme paid in đồng and your Singapore scheme in dollars this month. How do you show one total for both?",
                  "Tháng này chương trình Việt Nam trả bằng đồng và chương trình Singapore trả bằng đô la. Làm sao để có một con số tổng cho cả hai?"),
      options: [
        {
          text: B("Switch the Explorer to Group currency — they are converted at the group's rate for that month", "Chuyển Khám phá dữ liệu sang Đồng tiền của tập đoàn — chúng được quy đổi theo tỷ giá của tập đoàn cho tháng đó"),
          correct: true,
          explanation: B("Yes. The total is a reading, converted when you look, and it says which rate it used.",
                         "Đúng vậy. Con số tổng là một cách đọc, quy đổi khi bạn xem, và nó cho biết đã dùng tỷ giá nào."),
        },
        {
          text: B("Add the two totals together", "Cộng hai con số tổng lại"),
          correct: false,
          explanation: B("Let's rethink that. Đồng plus dollars is not a number anybody can use. Payobook never adds two currencies.",
                         "Hãy nghĩ lại một chút. Đồng cộng đô la không phải là một con số ai dùng được. Payobook không bao giờ cộng hai đồng tiền."),
        },
        {
          text: B("Run both schemes in one pay run", "Chạy cả hai chương trình trong một đợt lương"),
          correct: false,
          explanation: B("Let's rethink that. A pay run is always one scheme. The total belongs in Insights, not in the payroll.",
                         "Hãy nghĩ lại một chút. Một đợt lương luôn là một chương trình. Con số tổng thuộc về phần Phân tích, không thuộc về bảng lương."),
        },
      ],
    },
  },

  /* ===========================================================================
     LEARN REFRESH step 4 — THE WIDER APP. Lessons L13–L28 over the practice
     company's drawings of People › Pay and Plan, the Lifecycle boards,
     Workforce, Access & delegation and Compliance. Two hero moments: the pay
     review's budget meter FILLS as the rises go in (`meter`), and the map's
     Lifecycle line walks Hoàng Văn Nam from his hiring to his last day
     (journey.js). Money figures live in practice-data.js; the prose quotes
     the few the replica prints.
     ======================================================================== */
  L13: {
    id: "L13", station: "paybands", mins: 7,
    title: B("Pay bands, and whether pay is fair", "Khoảng lương, và lương có công bằng không"),
    goal: B("Read a band picture, spot who is paid below their band, and know what the Bands and Fairness tabs never change.",
            "Đọc bức tranh khoảng lương, nhận ra ai đang được trả dưới khoảng lương, và biết tab Khoảng lương và Công bằng không bao giờ thay đổi điều gì."),
    steps: [
      {
        screen: "paybands", anchor: "pp-tabs",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("People › Pay has four tabs", "Con người › Lương có bốn tab"),
        body: B("<b>Bands</b> and <b>Fairness</b> describe pay as it is. <b>Review</b> and <b>Changes</b> change it. This lesson is the first two; the next one is the other two.",
                "<b>Khoảng lương</b> và <b>Công bằng</b> mô tả lương như hiện tại. <b>Xét lương</b> và <b>Thay đổi</b> mới thay đổi nó. Bài này học hai tab đầu; bài sau học hai tab còn lại."),
      },
      {
        screen: "paybands", anchor: "pp-band-picture",
        kicker: B("The picture", "Bức tranh"),
        title: B("A range per job, a dot per person", "Mỗi công việc một khoảng, mỗi người một chấm"),
        body: B("The shaded range is the band, the tick is its middle, and every person stands in it as a dot. <b>Trần Văn Hùng</b>'s dot sits left of his band: he is paid below it, and the row says <b>1 below</b>.",
                "Phần tô màu là khoảng lương, vạch là điểm giữa, và mỗi người là một chấm trong đó. Chấm của <b>Trần Văn Hùng</b> nằm bên trái khoảng lương: anh được trả dưới khoảng, và dòng đó ghi <b>1 dưới</b>."),
        tip: B("Press a person's dot on the real screen and it names them. Dense rows fit a big family on one page.",
               "Bấm vào chấm của một người trên màn hình thật để thấy tên. Dòng gọn giúp một nhóm lớn nằm vừa một trang."),
      },
      {
        screen: "paybands", anchor: "pp-bands-tools",
        kicker: B("The tools", "Công cụ"),
        title: B("Four buttons, none of them a pay rise", "Bốn nút, không nút nào là tăng lương"),
        body: B("<b>Work it out again</b> redraws the bands from what you pay today. <b>Export</b> and <b>Import</b> take them through a file. <b>Place a new hire</b> suggests a starting salary inside the band.",
                "<b>Tính lại</b> vẽ lại các khoảng lương từ mức bạn đang trả. <b>Xuất ra</b> và <b>Nhập vào</b> đưa chúng qua một tệp. <b>Xếp lương người mới</b> gợi ý mức lương khởi điểm nằm trong khoảng."),
        tip: B("No bands yet? The tab offers a set drawn from what you already pay. Nothing is saved until you press Use these.",
               "Chưa có khoảng lương? Tab sẽ đưa ra một bộ vẽ từ mức bạn đang trả. Chưa có gì được lưu cho tới khi bạn bấm Dùng các khoảng này."),
      },
      {
        screen: "paybands", anchor: "pp-band-picture",
        kicker: B("Moving a band", "Dời một khoảng lương"),
        title: B("Drag an edge, read the cost, then let go", "Kéo mép, đọc chi phí, rồi mới thả tay"),
        body: B("A pay manager can drag a band's edge. While you hold it, the screen shows what the move would cost; letting go saves it, and <b>Undo</b> takes it back.",
                "Quản lý lương có thể kéo mép một khoảng lương. Trong lúc giữ, màn hình cho thấy thay đổi đó tốn bao nhiêu; thả tay là lưu, và <b>Hoàn tác</b> lấy lại."),
        consequence: B("Affects the band only — nobody's pay moves until a review or a pay change. Reversible: yes, with Undo. Verify first: the cost shown while you hold the edge.",
                       "Ảnh hưởng: chỉ khoảng lương — lương của không ai thay đổi cho tới khi có đợt xét lương hoặc thay đổi lương. Hoàn tác: có, bằng Hoàn tác. Kiểm tra trước: chi phí hiện ra khi bạn giữ mép."),
      },
      {
        screen: "paybands", anchor: "pp-health",
        kicker: B("Worth knowing", "Đáng biết"),
        title: B("Five checks, read for you", "Năm phép kiểm tra, đã đọc sẵn cho bạn"),
        body: B("Paid below the band, paid above it, newer people paid more, a manager paid less, and how wide each band has become. Here one person is below; that is where a review looks first.",
                "Được trả dưới khoảng lương, trên khoảng lương, người mới được trả cao hơn, quản lý được trả thấp hơn, và mỗi khoảng lương đã rộng ra bao nhiêu. Ở đây có một người ở dưới; đó là chỗ đợt xét lương nhìn vào trước."),
      },
      {
        screen: "paybands", anchor: "pp-fairness",
        kicker: B("Fairness", "Công bằng"),
        title: B("Worked out on open, never stored", "Tính khi mở, không bao giờ lưu"),
        body: B("The <b>Fairness</b> tab shows the pay gap by gender across everybody, then by level, by team and for the same job. Only pay managers and group admins see names.",
                "Tab <b>Công bằng</b> cho thấy chênh lệch lương theo giới trên toàn bộ nhân sự, rồi theo cấp bậc, theo phòng ban và cho cùng một công việc. Chỉ quản lý lương và quản trị tập đoàn mới thấy tên."),
        tip: B("A number worked out each time can move tomorrow. Print the statement when you need to keep one.",
               "Một con số tính lại mỗi lần có thể đổi vào ngày mai. Hãy in bản tường trình khi cần giữ lại."),
      },
    ],
    quiz: {
      question: B("Hùng's dot sits left of his band. What will raise his pay?",
                  "Chấm của Hùng nằm bên trái khoảng lương. Điều gì sẽ nâng lương của anh?"),
      options: [
        {
          text: B("A pay review or a pay change for him", "Một đợt xét lương hoặc một thay đổi lương cho anh"),
          correct: true,
          explanation: B("Yes. Bands describe pay; only Review and Changes change it, and both are signed off.",
                         "Đúng vậy. Khoảng lương chỉ mô tả lương; chỉ Xét lương và Thay đổi mới thay đổi nó, và cả hai đều phải được duyệt."),
        },
        {
          text: B("Dragging his band lower so he sits inside it", "Kéo khoảng lương của anh xuống để anh nằm bên trong"),
          correct: false,
          explanation: B("Let's rethink that. Moving the band changes the picture, not his pay — he would look fine and still be paid the same.",
                         "Hãy nghĩ lại một chút. Dời khoảng lương chỉ đổi bức tranh, không đổi lương của anh — trông thì ổn mà anh vẫn nhận như cũ."),
        },
        {
          text: B("Nothing — Payobook raises him on its own", "Không cần gì — Payobook tự tăng cho anh"),
          correct: false,
          explanation: B("Let's rethink that. Nothing here changes anybody's pay by itself. It shows you who to look at.",
                         "Hãy nghĩ lại một chút. Không có gì ở đây tự thay đổi lương của ai. Nó chỉ cho bạn biết cần nhìn vào ai."),
        },
      ],
    },
  },

  L14: {
    id: "L14", station: "payreview", mins: 9,
    title: B("Run a pay review inside its budget", "Xét lương trong phạm vi ngân sách"),
    goal: B("Fill a pay review's worksheet, watch it against its budget, calibrate it, and know who signs it and what Apply does.",
            "Điền bảng tính của đợt xét lương, theo dõi nó so với ngân sách, cân chỉnh, và biết ai phê duyệt và Áp dụng làm gì."),
    steps: [
      {
        screen: "payreview", anchor: "pp-reviews",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("One review, everybody's next year", "Một đợt xét lương, năm sau của mọi người"),
        body: B("People › Pay › <b>Review</b>. A review holds everyone's rise for the year in one worksheet, inside one budget. <b>New review</b> starts one; <b>Set up guidance</b> says what each score should earn.",
                "Con người › Lương › <b>Xét lương</b>. Một đợt xét lương giữ mức tăng của mọi người trong năm trên một bảng tính, trong một ngân sách. <b>Đợt xét lương mới</b> bắt đầu một đợt; <b>Thiết lập hướng dẫn</b> nói mỗi mức điểm nên được tăng bao nhiêu."),
      },
      {
        screen: "payreview", anchor: "pp-stepper",
        kicker: B("Who signs", "Ai phê duyệt"),
        title: B("Being written → HR → finance → the CEO → Applied", "Đang soạn → nhân sự → tài chính → tổng giám đốc → Đã áp dụng"),
        body: B("The stepper is the review's road. <b>Send for approval</b> hands it to HR, then finance, then the CEO. Each can approve it or <b>Send back</b> with a reason.",
                "Thanh các bước là chặng đường của đợt xét lương. <b>Gửi duyệt</b> chuyển nó cho nhân sự, rồi tài chính, rồi tổng giám đốc. Mỗi người có thể duyệt hoặc <b>Trả lại</b> kèm lý do."),
        moment: { kind: "pipeline", chain: "review" },
      },
      {
        screen: "payreview", anchor: "pp-worksheet",
        kicker: B("The worksheet", "Bảng tính"),
        title: B("A row per person", "Mỗi người một dòng"),
        body: B("Score, where they sit <b>in the band</b>, what they are paid now, the guidance, the rise, the new pay and what it costs a year. Filters find who is not scored, who stops approval and who is <b>Paid below the band</b>.",
                "Điểm đánh giá, vị trí <b>trong khoảng lương</b>, mức đang được trả, hướng dẫn, mức tăng, lương mới và chi phí cả năm. Bộ lọc tìm ai chưa chấm điểm, ai chặn duyệt và ai <b>Được trả dưới khoảng lương</b>."),
      },
      {
        screen: "payreview", anchor: "pp-bulk",
        kicker: B("Filling it in", "Điền vào"),
        title: B("Start from the guidance", "Bắt đầu từ hướng dẫn"),
        body: B("<b>Use the guidance</b> fills every rise from the scores. <b>Add 1%</b> and <b>Take off 1%</b> nudge the people you picked; <b>Share out what is left</b> spreads the rest of the budget.",
                "<b>Dùng hướng dẫn</b> điền mọi mức tăng theo điểm đánh giá. <b>Thêm 1%</b> và <b>Bớt 1%</b> chỉnh những người bạn chọn; <b>Chia phần còn lại</b> rải phần ngân sách còn dư."),
      },
      {
        screen: "payreview", anchor: "rep-pr-budget",
        kicker: B("The budget", "Ngân sách"),
        title: B("Watch the meter fill as the rises go in", "Nhìn thước đo đầy dần khi thêm các mức tăng"),
        body: B("Four rises go in: Mai 4%, Hùng 5% because he is below his band, Trang 2%, Đức 3%. The meter fills to <b>96%</b> of the budget. Over 100%, the review cannot be sent for approval.",
                "Bốn mức tăng được thêm vào: Mai 4%, Hùng 5% vì anh đang dưới khoảng lương, Trang 2%, Đức 3%. Thước đo đầy tới <b>96%</b> ngân sách. Vượt 100% thì không gửi duyệt được."),
        moment: { kind: "meter", from: "rep-pr-budget" },
      },
      {
        screen: "payreview", anchor: "pp-calibration",
        kicker: B("Calibration", "Cân chỉnh"),
        title: B("Does anyone stand out?", "Có ai nổi bật không?"),
        body: B("<b>Calibration</b> marks each rise as in line with the others, standing out, or breaking a limit. Trang has the top score and the smallest rise: <b>Worth a second look</b>.",
                "<b>Cân chỉnh</b> đánh dấu mỗi mức tăng là ngang với những người khác, nổi bật, hay vượt giới hạn. Trang có điểm cao nhất mà mức tăng nhỏ nhất: <b>Đáng xem lại</b>."),
        tip: B("Trang is already above her band's middle, so a small rise can be right. Calibration asks the question; you answer it.",
               "Trang đã ở trên điểm giữa khoảng lương của mình, nên mức tăng nhỏ có thể là đúng. Cân chỉnh đặt câu hỏi; bạn trả lời."),
      },
      {
        screen: "payreview", anchor: "pp-stops",
        kicker: B("Before you send it", "Trước khi gửi"),
        title: B("What stops approval", "Điều gì chặn duyệt"),
        body: B("Over budget, somebody not scored, a limit broken: each is listed here, and each keeps <b>Send for approval</b> from working. Here nothing is listed.",
                "Vượt ngân sách, có người chưa chấm điểm, vượt một giới hạn: mỗi điều được liệt kê ở đây, và mỗi điều khiến <b>Gửi duyệt</b> không bấm được. Ở đây không có điều nào."),
      },
      {
        screen: "payreview", anchor: "pp-review-actions",
        kicker: B("The action", "Thao tác chính"),
        title: B("Approved is not paid — Apply is", "Đã duyệt chưa phải là đã trả — Áp dụng mới là"),
        body: B("When the last step approves, the review is <b>Approved</b>. <b>Apply</b> shows what it would change, then writes the new pay onto everyone's records. The next pay run reads it.",
                "Khi bước cuối duyệt, đợt xét lương là <b>Đã duyệt</b>. <b>Áp dụng</b> cho thấy nó sẽ thay đổi gì, rồi ghi lương mới vào hồ sơ của mọi người. Đợt lương kế tiếp sẽ đọc nó."),
        consequence: B("Affects everyone in the review, from the next pay run. Reversible: Take it back works for 24 hours after Apply. Verify first: the meter, and nothing left under What stops approval.",
                       "Ảnh hưởng: mọi người trong đợt xét lương, từ đợt lương kế tiếp. Hoàn tác: Lấy lại dùng được trong 24 giờ sau khi Áp dụng. Kiểm tra trước: thước đo, và mục Điều gì chặn duyệt không còn gì."),
      },
      {
        screen: "payreview", anchor: "pp-tabs",
        kicker: B("One person, one change", "Một người, một thay đổi"),
        title: B("Changes, for everything between reviews", "Thay đổi, cho mọi việc giữa hai đợt xét lương"),
        body: B("A promotion, putting a mistake right, keeping up with the market: <b>Changes</b> › <b>New pay change</b> takes one person, a reason and the new pay. It goes up the same ladder of sign-offs.",
                "Thăng chức, sửa một sai sót, theo kịp thị trường: <b>Thay đổi</b> › <b>Thay đổi lương mới</b> nhận một người, một lý do và mức lương mới. Nó đi qua cùng các bước duyệt như trên."),
      },
    ],
    quiz: {
      question: B("The review says Approved. Will this month's pay run pay the new salaries?",
                  "Đợt xét lương báo Đã duyệt. Đợt lương tháng này có trả mức lương mới không?"),
      options: [
        {
          text: B("Only after somebody presses Apply", "Chỉ sau khi có người bấm Áp dụng"),
          correct: true,
          explanation: B("Yes. Apply writes the new pay onto the records, and a pay run computed after that reads it.",
                         "Đúng vậy. Áp dụng ghi lương mới vào hồ sơ, và đợt lương được tính sau đó sẽ đọc nó."),
        },
        {
          text: B("Yes — Approved means paid", "Có — Đã duyệt là đã trả"),
          correct: false,
          explanation: B("Let's rethink that. Approved is the last signature. Nothing reaches a record until Apply.",
                         "Hãy nghĩ lại một chút. Đã duyệt là chữ ký cuối cùng. Chưa có gì vào hồ sơ cho tới khi Áp dụng."),
        },
        {
          text: B("Only for the people the CEO looked at", "Chỉ với những người mà tổng giám đốc đã xem"),
          correct: false,
          explanation: B("Let's rethink that. A review is signed off and applied as one piece, for everyone in it.",
                         "Hãy nghĩ lại một chút. Một đợt xét lương được duyệt và áp dụng như một khối, cho mọi người trong đó."),
        },
      ],
    },
  },

  L15: {
    id: "L15", station: "decisionroom", mins: 7,
    title: B("Try next year before you commit to it", "Thử trước năm sau trước khi cam kết"),
    goal: B("Move the Decision Room's levers, read what they do to cost and profit, and turn an estimate into an exact cost.",
            "Xoay các cần gạt của Phòng quyết định, đọc tác động lên chi phí và lợi nhuận, và biến một ước tính thành chi phí chính xác."),
    steps: [
      {
        screen: "decisionroom", anchor: "dr-head",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("See the year before you commit to it", "Nhìn thấy cả năm trước khi cam kết"),
        body: B("People › <b>Plan</b> opens the Decision Room. <b>Undo</b>, <b>Reset</b> and <b>Save plan</b> sit at the top; everything in between is a question you can ask of next year.",
                "Con người › <b>Kế hoạch</b> mở Phòng quyết định. <b>Hoàn tác</b>, <b>Đặt lại</b> và <b>Lưu kế hoạch</b> nằm ở trên; mọi thứ ở giữa là một câu hỏi bạn đặt cho năm sau."),
      },
      {
        screen: "decisionroom", anchor: "dr-presets",
        kicker: B("What if we…", "Nếu chúng ta…"),
        title: B("Start from a preset, then move the levers", "Bắt đầu từ một phương án có sẵn, rồi xoay các cần gạt"),
        body: B("<b>Grow thoughtfully</b>, <b>Invest in people</b> or <b>Ease overtime</b> set the levers for you. Then change them: add people and the month they start, a rise and when, overtime per person, leavers.",
                "<b>Tăng trưởng thận trọng</b>, <b>Đầu tư vào con người</b> hoặc <b>Giảm làm thêm giờ</b> đặt sẵn các cần gạt. Rồi chỉnh chúng: thêm người và tháng bắt đầu, mức tăng lương và thời điểm, tăng ca mỗi người, người nghỉ việc."),
        tip: B("Explore freely. Nothing here changes payroll.", "Cứ thoải mái khám phá. Không có gì ở đây thay đổi bảng lương."),
      },
      {
        screen: "decisionroom", anchor: "dr-goals",
        kicker: B("Goals", "Mục tiêu"),
        title: B("Six goals. The room keeps score.", "Sáu mục tiêu. Căn phòng tự chấm điểm."),
        body: B("Say what a good year means — profit, overtime, room to hire. Every lever you move is scored against them, so a plan is judged by your goals, not by its size.",
                "Hãy nói một năm tốt nghĩa là gì — lợi nhuận, tăng ca, dư địa tuyển dụng. Mỗi cần gạt bạn xoay đều được chấm theo đó, nên kế hoạch được đánh giá theo mục tiêu của bạn chứ không theo quy mô."),
      },
      {
        screen: "decisionroom", anchor: "dr-results",
        kicker: B("The results", "Kết quả"),
        title: B("Four ways to read one plan", "Bốn cách đọc một kế hoạch"),
        body: B("<b>Work & shifts</b>, <b>Why profit changed</b>, <b>People & pay</b> and <b>Room to hire</b>. Why profit changed is the one to show a board: it names each lever's share.",
                "<b>Công việc & ca làm</b>, <b>Vì sao lợi nhuận thay đổi</b>, <b>Con người & lương</b> và <b>Dư địa tuyển dụng</b>. Vì sao lợi nhuận thay đổi là thứ nên trình ban lãnh đạo: nó nêu phần của từng cần gạt."),
      },
      {
        screen: "decisionroom", anchor: "rep-dr-exact",
        kicker: B("Estimate, then exact", "Ước tính, rồi chính xác"),
        title: B("Exact cost runs the real pay scheme", "Chi phí chính xác chạy chương trình lương thật"),
        body: B("The room's own figure is an estimate. <b>Exact cost</b> runs a saved plan through the real pay scheme and says how far the estimate was off — here under half a percent.",
                "Con số của căn phòng là ước tính. <b>Chi phí chính xác</b> chạy một kế hoạch đã lưu qua chương trình lương thật và cho biết ước tính lệch bao nhiêu — ở đây dưới nửa phần trăm."),
      },
      {
        screen: "decisionroom", anchor: "dr-propose",
        kicker: B("Deciding", "Quyết định"),
        title: B("Propose, then approve or send back", "Đề xuất, rồi duyệt hoặc trả lại"),
        body: B("A saved plan is <b>Propose</b>d; a manager approves it or sends it back. An approved plan is kept as it was — <b>Keep editing a copy</b> starts the next idea.",
                "Kế hoạch đã lưu được <b>Đề xuất</b>; quản lý duyệt hoặc trả lại. Kế hoạch đã duyệt được giữ nguyên — <b>Chép ra bản mới để sửa tiếp</b> bắt đầu ý tưởng kế tiếp."),
        tip: B("Export the decision brief turns the plan into a document you can send.",
               "Xuất bản tóm tắt quyết định biến kế hoạch thành một tài liệu bạn có thể gửi đi."),
      },
    ],
    quiz: {
      question: B("Your finance director asks what a 3.5% rise for everyone will really cost next year. What do you send?",
                  "Giám đốc tài chính hỏi tăng lương 3,5% cho mọi người thật sự tốn bao nhiêu vào năm sau. Bạn gửi gì?"),
      options: [
        {
          text: B("The Exact cost of a saved plan, with how far the estimate was off", "Chi phí chính xác của một kế hoạch đã lưu, kèm mức lệch của ước tính"),
          correct: true,
          explanation: B("Yes. It runs the real pay scheme, so it includes insurance and tax the way payroll will.",
                         "Đúng vậy. Nó chạy chương trình lương thật, nên đã gồm bảo hiểm và thuế đúng như bảng lương sẽ tính."),
        },
        {
          text: B("The room's estimate", "Con số ước tính của căn phòng"),
          correct: false,
          explanation: B("Let's rethink that. The estimate is quick and close, not exact. For a number somebody will budget from, press Exact cost.",
                         "Hãy nghĩ lại một chút. Ước tính nhanh và gần đúng, không chính xác. Với con số người khác dùng để lập ngân sách, hãy bấm Chi phí chính xác."),
        },
        {
          text: B("This year's wage bill plus 3.5%", "Quỹ lương năm nay cộng 3,5%"),
          correct: false,
          explanation: B("Let's rethink that. It misses the people joining and leaving, and what the rise does to insurance and tax.",
                         "Hãy nghĩ lại một chút. Cách đó bỏ sót người vào, người nghỉ, và tác động của mức tăng lên bảo hiểm và thuế."),
        },
      ],
    },
  },

  L16: {
    id: "L16", station: "hiring", mins: 8,
    title: B("Raise a hiring request, and follow it to a hire", "Đề xuất tuyển dụng, và theo nó tới khi có người"),
    goal: B("Read the Hiring board, raise a request with its budget, and know who signs it and what each step of a role means.",
            "Đọc bảng Tuyển dụng, đề xuất tuyển kèm ngân sách, và biết ai phê duyệt cũng như mỗi bước của một vị trí nghĩa là gì."),
    steps: [
      {
        screen: "hiring", anchor: "hi-numbers",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Every open role, on one board", "Mọi vị trí đang tuyển, trên một bảng"),
        body: B("Lifecycle › <b>Hiring</b>. The quiet numbers on top say what needs you: <b>Awaiting sign-off</b>, <b>Waiting on you</b>, <b>Over budget</b>, interviews this week and opinions that are late.",
                "Vòng đời nhân sự › <b>Tuyển dụng</b>. Các con số nhỏ ở trên cho biết việc gì cần bạn: <b>Chờ phê duyệt</b>, <b>Đang chờ bạn</b>, <b>Vượt ngân sách</b>, số buổi phỏng vấn tuần này và các ý kiến đang trễ."),
      },
      {
        screen: "hiring", anchor: "hi-steps",
        kicker: B("Four steps", "Bốn bước"),
        title: B("Every role walks the same four steps", "Mọi vị trí đi qua cùng bốn bước"),
        body: B("<b>Request & approve</b>, <b>Prepare & publish</b>, <b>Meet your candidates</b>, <b>Welcome aboard</b>. Press a step to see only the roles standing on it.",
                "<b>Đề xuất & phê duyệt</b>, <b>Chuẩn bị & đăng tin</b>, <b>Gặp ứng viên</b>, <b>Chào mừng gia nhập</b>. Bấm một bước để chỉ xem các vị trí đang ở bước đó."),
        moment: { kind: "pipeline", chain: "hiring" },
      },
      {
        screen: "hiring", anchor: "hi-next",
        kicker: B("Each card", "Mỗi thẻ"),
        title: B("Step X of 4, and what is next", "Bước X/4, và việc tiếp theo"),
        body: B("A role's card says its step and one <b>Next</b> line: here two interview opinions are late. The Next line is the board telling you the one thing that moves this role on.",
                "Thẻ của một vị trí ghi bước hiện tại và một dòng <b>Tiếp theo</b>: ở đây có hai ý kiến phỏng vấn đang trễ. Dòng Tiếp theo là bảng nói cho bạn một việc giúp vị trí này đi tiếp."),
      },
      {
        screen: "hiring", anchor: "hi-raise",
        kicker: B("Step 1", "Bước 1"),
        title: B("Raise a hiring request", "Đề xuất tuyển dụng"),
        body: B("Asking comes before advertising. The button opens a short wizard: <b>Let's shape your next hire.</b>",
                "Xin phép đi trước đăng tin. Nút này mở một trình hướng dẫn ngắn: <b>Hãy cùng phác thảo vị trí tuyển dụng tiếp theo.</b>"),
      },
      {
        screen: "hiring_request", anchor: "hi-wizard",
        kicker: B("The wizard", "Trình hướng dẫn"),
        title: B("The role, what they do, how you will interview, the budget", "Vị trí, công việc, cách phỏng vấn, ngân sách"),
        body: B("Four tabs: <b>The role</b>, <b>Responsibilities</b>, <b>Interview plan</b>, <b>Budget & review</b>. The last one sets the salary against the budget before anybody is asked to sign.",
                "Bốn tab: <b>Vị trí</b>, <b>Trách nhiệm</b>, <b>Kế hoạch phỏng vấn</b>, <b>Ngân sách & xem lại</b>. Tab cuối đặt mức lương cạnh ngân sách trước khi ai đó được mời phê duyệt."),
      },
      {
        screen: "hiring_request", anchor: "rep-hi-route",
        kicker: B("Who signs", "Ai phê duyệt"),
        title: B("Manager, HR lead — and Finance only if over budget", "Quản lý, trưởng nhân sự — và Tài chính chỉ khi vượt ngân sách"),
        body: B("Sent for approval, the request goes to the manager, then the HR lead. Finance is asked only when the role is over budget. It all arrives in Home › Approvals.",
                "Khi gửi phê duyệt, đề xuất đi tới quản lý, rồi trưởng nhân sự. Tài chính chỉ được hỏi khi vị trí vượt ngân sách. Tất cả đều về Trang chủ › Phê duyệt."),
        consequence: B("Affects this one role. Reversible: yes — it can be sent back or withdrawn while it waits. Verify first: the salary sits inside the budget, or Finance will be asked.",
                       "Ảnh hưởng: chỉ vị trí này. Hoàn tác: có — có thể trả lại hoặc thu hồi trong lúc chờ. Kiểm tra trước: mức lương nằm trong ngân sách, nếu không Tài chính sẽ được hỏi."),
      },
      {
        screen: "hiring", anchor: "hi-stage",
        kicker: B("Step 3", "Bước 3"),
        title: B("Candidates move stage by stage", "Ứng viên đi từng giai đoạn"),
        body: B("From <b>Screening</b> through interviews and a <b>Reference Check</b> to <b>Offer Stage</b> and <b>Joined</b>. <b>Move stage</b> takes a candidate on — or out, with a reason such as Drop Out.",
                "Từ <b>Sàng lọc</b> qua các buổi phỏng vấn và <b>Kiểm tra tham chiếu</b> tới <b>Giai đoạn đề nghị</b> và <b>Đã nhận việc</b>. <b>Chuyển giai đoạn</b> đưa ứng viên đi tiếp — hoặc ra ngoài, kèm lý do như Bỏ cuộc."),
        tip: B("Hoàng Văn Nam is the candidate here. When he joins, he appears on the New joiners board — the next stop on his road.",
               "Hoàng Văn Nam là ứng viên ở đây. Khi anh nhận việc, anh xuất hiện trên bảng Nhân viên mới — chặng tiếp theo trên hành trình của anh."),
      },
    ],
    quiz: {
      question: B("A store manager wants a new cashier. The salary they have in mind is above the budget. Who signs the request?",
                  "Một cửa hàng trưởng muốn tuyển thêm thu ngân. Mức lương họ định trả cao hơn ngân sách. Ai phê duyệt đề xuất?"),
      options: [
        {
          text: B("The manager and the HR lead, then Finance because it is over budget", "Quản lý và trưởng nhân sự, rồi Tài chính vì vượt ngân sách"),
          correct: true,
          explanation: B("Yes. Finance is added only when the role costs more than was planned.",
                         "Đúng vậy. Tài chính chỉ được thêm vào khi vị trí tốn hơn mức đã lên kế hoạch."),
        },
        {
          text: B("Nobody — raise it and advertise straight away", "Không ai cả — đề xuất rồi đăng tin ngay"),
          correct: false,
          explanation: B("Let's rethink that. The role stays at step 1, Request & approve, until it is signed off.",
                         "Hãy nghĩ lại một chút. Vị trí nằm ở bước 1, Đề xuất & phê duyệt, cho tới khi được duyệt."),
        },
        {
          text: B("Only Finance, because money is involved", "Chỉ Tài chính, vì liên quan tới tiền"),
          correct: false,
          explanation: B("Let's rethink that. The manager and the HR lead always sign; Finance joins when it is over budget.",
                         "Hãy nghĩ lại một chút. Quản lý và trưởng nhân sự luôn phê duyệt; Tài chính tham gia khi vượt ngân sách."),
        },
      ],
    },
  },

  L17: {
    id: "L17", station: "joiners", mins: 7,
    title: B("Get ready for someone starting", "Chuẩn bị cho người sắp vào làm"),
    goal: B("Read the New joiners board, make sure every joiner has a buddy and a finished checklist, and know what payroll needs before day one.",
            "Đọc bảng Nhân viên mới, đảm bảo mọi người mới đều có người đồng hành và danh mục việc xong, và biết bảng lương cần gì trước ngày đầu."),
    steps: [
      {
        screen: "joiners", anchor: "nj-numbers",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Everyone starting soon", "Những người sắp vào làm"),
        body: B("Lifecycle › <b>New joiners</b>. <b>Joining this week</b>, <b>Already started</b>, <b>Still without a buddy</b>, <b>Steps overdue</b>, and people who <b>said they are struggling</b>.",
                "Vòng đời nhân sự › <b>Nhân viên mới</b>. <b>Vào làm tuần này</b>, <b>Đã bắt đầu làm việc</b>, <b>Chưa có người đồng hành</b>, <b>Bước quá hạn</b>, và những người <b>cho biết đang gặp khó khăn</b>."),
      },
      {
        screen: "joiners", anchor: "nj-steps",
        kicker: B("Three steps", "Ba bước"),
        title: B("Getting ready → Settling in → Checklist done", "Đang chuẩn bị → Đang hòa nhập → Đã xong danh mục"),
        body: B("Before the first day a joiner is <b>Getting ready</b>; from it, <b>Settling in</b>. They leave the board when their <b>Checklist done</b>.",
                "Trước ngày đầu, người mới <b>Đang chuẩn bị</b>; từ ngày đó, <b>Đang hòa nhập</b>. Họ rời bảng khi <b>Đã xong danh mục</b>."),
      },
      {
        screen: "joiners", anchor: "nj-list",
        kicker: B("The cards", "Các thẻ"),
        title: B("Nam starts on 1 August, with Mai as his buddy", "Nam bắt đầu ngày 1/8, với Mai là người đồng hành"),
        body: B("Each card is one person and their start date. Đinh Thị Yến has no buddy yet: her card offers <b>Choose one</b>, and she is the one counted under Still without a buddy.",
                "Mỗi thẻ là một người và ngày bắt đầu của họ. Đinh Thị Yến chưa có người đồng hành: thẻ của chị có nút <b>Chọn một người</b>, và chị chính là người được đếm ở mục Chưa có người đồng hành."),
      },
      {
        screen: "joiners", anchor: "nj-drawer",
        kicker: B("Open a person", "Mở một người"),
        title: B("Still to do, Done, Conversations", "Còn phải làm, Hoàn tất, Trao đổi"),
        body: B("Open a card and the drawer lists what is <b>Still to do</b> — laptop, store card, bank account, first-week rota — what is <b>Done</b>, and the <b>Conversations</b> so far.",
                "Mở một thẻ, ngăn bên cạnh liệt kê việc <b>Còn phải làm</b> — máy tính, thẻ cửa hàng, tài khoản ngân hàng, lịch ca tuần đầu — việc đã <b>Hoàn tất</b>, và các cuộc <b>Trao đổi</b> tới nay."),
        tip: B("The bank account on that list is payroll's item. Without it Nam is computed in August and paid nothing.",
               "Tài khoản ngân hàng trong danh sách đó là việc của bảng lương. Thiếu nó, Nam vẫn được tính lương tháng 8 mà không nhận được đồng nào."),
      },
      {
        screen: "joiners", anchor: "nj-buddy",
        kicker: B("People around them", "Những người bên cạnh"),
        title: B("HR contact, buddy, their record", "Liên hệ nhân sự, người đồng hành, hồ sơ của họ"),
        body: B("The drawer names who the joiner can ask: their HR contact and their <b>Buddy</b>, and opens their record in one press.",
                "Ngăn bên cạnh ghi rõ người mới có thể hỏi ai: liên hệ nhân sự và <b>Người đồng hành</b>, và mở hồ sơ của họ chỉ với một lần bấm."),
      },
      {
        screen: "joiners", anchor: "nj-run",
        kicker: B("Every morning", "Mỗi sáng"),
        title: B("Run today's steps", "Chạy các bước hôm nay"),
        body: B("<b>Run today's steps</b> sends what is due today — welcome messages, reminders to the buddy — instead of waiting for tonight's automatic run.",
                "<b>Chạy các bước hôm nay</b> gửi những gì đến hạn hôm nay — lời chào mừng, lời nhắc cho người đồng hành — thay vì chờ lần chạy tự động tối nay."),
      },
    ],
    quiz: {
      question: B("Nam starts on Monday. His card shows a buddy, but the drawer still lists Bank account on file. What happens in August's pay run?",
                  "Nam bắt đầu vào thứ Hai. Thẻ của anh đã có người đồng hành, nhưng ngăn bên cạnh vẫn ghi Đã có tài khoản ngân hàng ở mục còn phải làm. Điều gì xảy ra ở đợt lương tháng 8?"),
      options: [
        {
          text: B("He is computed, and cannot be paid until the account is on file", "Anh được tính lương, nhưng không trả được cho tới khi có tài khoản"),
          correct: true,
          explanation: B("Yes. A payslip does not need a bank account; the payment does. Finish that item before the run.",
                         "Đúng vậy. Phiếu lương không cần tài khoản ngân hàng; việc chi trả thì cần. Hãy xong việc đó trước đợt lương."),
        },
        {
          text: B("Nothing — the buddy covers it", "Không sao — người đồng hành lo việc đó"),
          correct: false,
          explanation: B("Let's rethink that. A buddy helps the person settle in. The bank account is still missing.",
                         "Hãy nghĩ lại một chút. Người đồng hành giúp người mới hòa nhập. Tài khoản ngân hàng vẫn đang thiếu."),
        },
        {
          text: B("He is left out of the pay run", "Anh bị loại khỏi đợt lương"),
          correct: false,
          explanation: B("Let's rethink that. His running contract puts him in the run. The gap shows up when the money is paid.",
                         "Hãy nghĩ lại một chút. Hợp đồng đang hiệu lực đưa anh vào đợt lương. Chỗ thiếu lộ ra khi chi trả."),
        },
      ],
    },
  },

  L18: {
    id: "L18", station: "exits", mins: 8,
    title: B("Someone is leaving: from notice to final settlement", "Có người nghỉ việc: từ báo trước tới quyết toán"),
    goal: B("Follow a leaver across the Exits board, read who still has to sign off, and know why the final settlement waits.",
            "Theo một người nghỉ việc trên bảng Nghỉ việc, đọc ai còn phải xác nhận bàn giao, và biết vì sao quyết toán phải chờ."),
    steps: [
      {
        screen: "exits", anchor: "ex2-numbers",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Everyone on their way out", "Những người sắp rời công ty"),
        body: B("Lifecycle › <b>Exits</b>. <b>Leaving this month</b>, <b>Last day has passed</b>, <b>Settlements held up</b>, <b>Clearances still open</b> and <b>Items not back yet</b>.",
                "Vòng đời nhân sự › <b>Nghỉ việc</b>. <b>Nghỉ việc trong tháng này</b>, <b>Đã qua ngày làm việc cuối</b>, <b>Quyết toán bị vướng</b>, <b>Xác nhận bàn giao còn mở</b> và <b>Tài sản chưa trả lại</b>."),
      },
      {
        screen: "exits", anchor: "ex2-steps",
        kicker: B("Four steps", "Bốn bước"),
        title: B("Notice → Signing off → Ready to settle → Settled", "Báo trước → Xác nhận bàn giao → Sẵn sàng quyết toán → Đã quyết toán"),
        body: B("A leaver works their notice, then the desks sign them off. Only then are they <b>Ready to settle</b>, and <b>Settled</b> when the last payment is closed.",
                "Người nghỉ làm hết thời gian báo trước, rồi các phòng ban xác nhận bàn giao. Chỉ khi đó họ mới <b>Sẵn sàng quyết toán</b>, và <b>Đã quyết toán</b> khi khoản chi cuối được chốt."),
        moment: { kind: "pipeline", chain: "exit" },
      },
      {
        screen: "exits", anchor: "ex2-clearance",
        kicker: B("Signed off by", "Được ký tắt bởi"),
        title: B("Four desks: IT, HR, Finance, Admin", "Bốn phòng ban: IT, Nhân sự, Tài chính, Quản trị viên"),
        body: B("Each light is one desk saying the leaver has handed back what they held. Bùi Thị Hạnh's last day has passed; three lights are on and Finance's is not.",
                "Mỗi đèn là một phòng ban xác nhận người nghỉ đã trả lại những gì họ giữ. Ngày làm cuối của Bùi Thị Hạnh đã qua; ba đèn đã sáng và đèn Tài chính thì chưa."),
      },
      {
        screen: "exits", anchor: "rep-ex-desks",
        kicker: B("What each desk checks", "Mỗi phòng ban kiểm tra gì"),
        title: B("Finance is waiting for the store float", "Tài chính đang chờ quỹ tiền lẻ của quầy"),
        body: B("Open the card: the laptop is back, the exit conversation is held, the store card is handed in. The store float has not been counted back, so Finance has not signed.",
                "Mở thẻ ra: máy tính đã trả, cuộc trao đổi trước khi nghỉ đã diễn ra, thẻ cửa hàng đã nộp. Quỹ tiền lẻ của quầy chưa được đếm lại, nên Tài chính chưa ký."),
      },
      {
        screen: "exits", anchor: "ex2-settle",
        kicker: B("The settlement", "Quyết toán"),
        title: B("The final settlement waits for all four", "Quyết toán cuối cùng chờ đủ cả bốn"),
        body: B("<b>Close settlement</b> stays unavailable until every desk has signed. <b>Open the settlement</b> shows the last salary, unused leave and what is still owed.",
                "<b>Chốt quyết toán</b> chưa bấm được cho tới khi mọi phòng ban đã ký. <b>Mở quyết toán</b> cho thấy lương cuối, phép chưa dùng và những khoản còn nợ."),
        consequence: B("Affects the leaver's last payment, which has a legal deadline. Reversible: not once it is paid. Verify first: all four desks signed, and the leaver is not also in the monthly run.",
                       "Ảnh hưởng: khoản chi cuối của người nghỉ, vốn có thời hạn pháp lý. Hoàn tác: không, một khi đã chi. Kiểm tra trước: đủ bốn phòng ban đã ký, và người nghỉ không còn nằm trong đợt lương tháng."),
      },
      {
        screen: "exits", anchor: "ex2-handover",
        kicker: B("Before they go", "Trước khi họ đi"),
        title: B("Handover, and a farewell note", "Bàn giao công việc, và lời chia tay"),
        body: B("<b>Handover</b> lists the work passed to colleagues; <b>Add</b> puts another item on it. A farewell note can go to the team, in words you can change.",
                "<b>Bàn giao công việc</b> liệt kê những việc chuyển cho đồng nghiệp; <b>Thêm</b> đưa một việc nữa vào. Có thể gửi một lời chia tay tới nhóm, với câu chữ bạn sửa được."),
        tip: B("Years after he was hired, this is where Hoàng Văn Nam's road ends on the map — the last stop of the Lifecycle line.",
               "Nhiều năm sau khi được tuyển, đây là nơi hành trình của Hoàng Văn Nam kết thúc trên bản đồ — chặng cuối của tuyến Vòng đời nhân sự."),
      },
    ],
    quiz: {
      question: B("Hạnh's last day has passed. IT, HR and Admin have signed; Finance has not. Can you close her settlement?",
                  "Ngày làm cuối của Hạnh đã qua. IT, Nhân sự và Quản trị viên đã ký; Tài chính thì chưa. Bạn có chốt quyết toán cho chị được không?"),
      options: [
        {
          text: B("Not yet — the settlement waits for all four desks", "Chưa — quyết toán chờ đủ cả bốn phòng ban"),
          correct: true,
          explanation: B("Yes. Ask Finance about the store float; once they sign, Close settlement becomes available.",
                         "Đúng vậy. Hãy hỏi Tài chính về quỹ tiền lẻ; khi họ ký, Chốt quyết toán sẽ bấm được."),
        },
        {
          text: B("Yes — three out of four is enough", "Được — ba trên bốn là đủ"),
          correct: false,
          explanation: B("Let's rethink that. Money she still holds would be lost the moment the last payment goes out.",
                         "Hãy nghĩ lại một chút. Khoản tiền chị còn giữ sẽ mất ngay khi khoản chi cuối được chuyển đi."),
        },
        {
          text: B("Pay her in the monthly run instead", "Trả cho chị trong đợt lương tháng thay vào đó"),
          correct: false,
          explanation: B("Let's rethink that. A leaver is settled once, from Pay Run › Settle. Paying her in the monthly run as well pays her twice.",
                         "Hãy nghĩ lại một chút. Người nghỉ được quyết toán một lần, từ Đợt lương › Quyết toán. Trả thêm trong đợt lương tháng là trả hai lần."),
        },
      ],
    },
  },

  L19: {
    id: "L19", station: "probation", mins: 7,
    title: B("End a trial with a decision", "Kết thúc thử việc bằng một quyết định"),
    goal: B("Read the Probation board, gather colleagues' views in time, and make one of the three decisions before the trial ends.",
            "Đọc bảng Thử việc, thu thập ý kiến đồng nghiệp kịp lúc, và đưa ra một trong ba quyết định trước khi thử việc kết thúc."),
    steps: [
      {
        screen: "probation", anchor: "pr-numbers",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Every trial that is running", "Mọi đợt thử việc đang chạy"),
        body: B("Lifecycle › <b>Probation</b>. <b>In a trial period</b>, <b>Reviews running</b>, <b>Waiting on a decision</b>, <b>Answers overdue</b> and <b>Ending within a week</b> — the one that cannot wait.",
                "Vòng đời nhân sự › <b>Thử việc</b>. <b>Đang thử việc</b>, <b>Đánh giá đang chạy</b>, <b>Đang chờ quyết định</b>, <b>Câu trả lời quá hạn</b> và <b>Kết thúc trong vòng một tuần</b> — mục không thể chờ."),
      },
      {
        screen: "probation", anchor: "pr-steps",
        kicker: B("Five steps", "Năm bước"),
        title: B("From choosing peers to sharing the outcome", "Từ chọn đồng nghiệp tới thông báo kết quả"),
        body: B("<b>Choose peers</b>, <b>Gather perspectives</b>, <b>Manager conversation</b>, <b>HR & leadership review</b>, <b>Share the outcome</b>. Nam's trial is at the fourth.",
                "<b>Chọn đồng nghiệp</b>, <b>Thu thập ý kiến</b>, <b>Trao đổi với quản lý</b>, <b>Nhân sự và lãnh đạo xem xét</b>, <b>Thông báo kết quả</b>. Đợt thử việc của Nam đang ở bước thứ tư."),
      },
      {
        screen: "probation", anchor: "pr-list",
        kicker: B("The cards", "Các thẻ"),
        title: B("A card per person, with its end date", "Mỗi người một thẻ, kèm ngày kết thúc"),
        body: B("Each card says when the trial ends and how far it has got. Open one to see what everybody said.",
                "Mỗi thẻ cho biết thử việc kết thúc khi nào và đã đi tới đâu. Mở một thẻ để xem mọi người đã nói gì."),
      },
      {
        screen: "probation", anchor: "pr-peers",
        kicker: B("Colleagues asked", "Đồng nghiệp được hỏi"),
        title: B("Three of four have answered", "Ba trên bốn người đã trả lời"),
        body: B("The colleagues chosen are sent a few short questions. Their answers sit beside the manager's view, so the decision is not one person's impression.",
                "Những đồng nghiệp được chọn nhận vài câu hỏi ngắn. Câu trả lời của họ nằm cạnh nhận xét của quản lý, để quyết định không chỉ là ấn tượng của một người."),
      },
      {
        screen: "probation", anchor: "pr-verdict",
        kicker: B("The decision", "Quyết định"),
        title: B("Confirm them, extend the trial, or do not confirm", "Xác nhận chính thức, kéo dài thử việc, hoặc không xác nhận"),
        body: B("The manager decides first; HR and leadership review it; then it is shared with the person. A trial that ends with nobody deciding becomes a yes by default.",
                "Quản lý quyết định trước; nhân sự và lãnh đạo xem xét; rồi kết quả được thông báo cho người đó. Thử việc kết thúc mà không ai quyết định sẽ mặc nhiên thành đồng ý."),
        consequence: B("Affects this person's job and, if confirmed, their pay from the next pay run. Reversible: not once shared. Verify first: colleagues have answered and the end date has not passed.",
                       "Ảnh hưởng: công việc của người này và, nếu xác nhận, lương của họ từ đợt lương kế tiếp. Hoàn tác: không, một khi đã thông báo. Kiểm tra trước: đồng nghiệp đã trả lời và ngày kết thúc chưa qua."),
      },
    ],
    quiz: {
      question: B("Nam's trial ends on Friday. One colleague has not answered and nobody has decided. What do you do today?",
                  "Thử việc của Nam kết thúc vào thứ Sáu. Một đồng nghiệp chưa trả lời và chưa ai quyết định. Hôm nay bạn làm gì?"),
      options: [
        {
          text: B("Chase the last answer and get the manager to decide before Friday", "Nhắc câu trả lời còn thiếu và đề nghị quản lý quyết định trước thứ Sáu"),
          correct: true,
          explanation: B("Yes. Ending within a week is on the board so that nobody finds out on Monday.",
                         "Đúng vậy. Mục Kết thúc trong vòng một tuần có trên bảng để không ai phát hiện ra vào thứ Hai."),
        },
        {
          text: B("Let it pass — he will be confirmed anyway", "Cứ để qua — đằng nào anh cũng được xác nhận"),
          correct: false,
          explanation: B("Let's rethink that. A yes by default is a decision nobody made, and nobody can explain it later.",
                         "Hãy nghĩ lại một chút. Mặc nhiên đồng ý là một quyết định không ai đưa ra, và sau này không ai giải thích được."),
        },
        {
          text: B("Extend the trial to buy time", "Kéo dài thử việc để có thêm thời gian"),
          correct: false,
          explanation: B("Let's rethink that. Extending is a real decision with its own reasons, not a way to put one off.",
                         "Hãy nghĩ lại một chút. Kéo dài là một quyết định thật với lý do riêng, không phải cách để trì hoãn."),
        },
      ],
    },
  },

  L20: {
    id: "L20", station: "wftoday", mins: 6,
    title: B("A day in Workforce", "Một ngày ở Lực lượng lao động"),
    goal: B("Read Today at a glance, clear what the Needs you panel is holding, and know what clean overtime means.",
            "Đọc nhanh tab Hôm nay, xử lý những gì khung Cần bạn đang giữ, và biết tăng ca sạch nghĩa là gì."),
    steps: [
      {
        screen: "wftoday", anchor: "wf-today",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Who is in, today", "Hôm nay ai có mặt"),
        body: B("Workforce › <b>Today</b>. <b>On shift</b>, <b>Late</b>, <b>Not started</b>, <b>Checked out</b> and <b>On leave</b>, for the teams you look after. <b>Board</b> or <b>Map</b> shows the same people two ways.",
                "Lực lượng lao động › <b>Hôm nay</b>. <b>Theo ca</b>, <b>Trễ</b>, <b>Chưa bắt đầu</b>, <b>Đã về</b> và <b>Đang nghỉ phép</b>, cho các nhóm bạn phụ trách. <b>Bảng</b> hoặc <b>Bản đồ</b> cho thấy cùng những người đó theo hai cách."),
      },
      {
        screen: "wftoday", anchor: "wf-today",
        kicker: B("Act early", "Làm sớm"),
        title: B("Late and Not started are today's calls", "Trễ và Chưa bắt đầu là việc cần gọi hôm nay"),
        body: B("A shift nobody started is easier to cover this morning than to explain on Friday.",
                "Một ca chưa ai bắt đầu thì sắp xếp người thay ngay sáng nay dễ hơn là giải thích vào thứ Sáu."),
      },
      {
        screen: "wftoday", anchor: "wf-needs",
        kicker: B("Needs you", "Cần bạn"),
        title: B("The panel beside every Workforce tab", "Khung nằm cạnh mọi tab của Lực lượng lao động"),
        body: B("Leave requests, overtime to approve, flags on this week: everything waiting for you, whichever tab you are on. <b>My team</b> or <b>Organisation</b> decides whose.",
                "Đơn nghỉ phép, tăng ca cần duyệt, cờ cảnh báo tuần này: mọi việc đang chờ bạn, dù bạn ở tab nào. <b>Đội của tôi</b> hoặc <b>Tổ chức</b> quyết định là của ai."),
      },
      {
        screen: "wftoday", anchor: "wf-clean",
        kicker: B("One press", "Một lần bấm"),
        title: B("Approve all clean overtime", "Duyệt tất cả tăng ca sạch"),
        body: B("Clean overtime is overtime whose hours match the grid, stay under every limit and fall on a day that is still open. Only those go in one press; the rest wait for your look.",
                "Tăng ca sạch là tăng ca có giờ khớp với lưới, nằm dưới mọi giới hạn và rơi vào ngày còn mở. Chỉ phần đó được duyệt trong một lần bấm; phần còn lại chờ bạn xem."),
        consequence: B("Affects the clean requests listed — they reach payroll this week. Reversible: until the week is locked. Verify first: the count on the button is what you expected.",
                       "Ảnh hưởng: các yêu cầu sạch được liệt kê — chúng vào bảng lương tuần này. Hoàn tác: được, cho tới khi tuần bị khoá. Kiểm tra trước: con số trên nút đúng như bạn nghĩ."),
      },
      {
        screen: "wftoday", anchor: "rep-tabs",
        kicker: B("The week", "Cả tuần"),
        title: B("Today, then Time, then Close", "Hôm nay, rồi Chấm công, rồi Chốt kỳ"),
        body: B("A manager's week runs left to right: Today, Schedule, Time, Time Off, Overtime, Trips, Approvals, and <b>Close</b> at the end, where the week is locked for payroll.",
                "Một tuần của quản lý đi từ trái sang phải: Hôm nay, Lịch ca, Chấm công, Nghỉ phép, Tăng ca, Công tác, Phê duyệt, và <b>Chốt kỳ</b> ở cuối, nơi tuần được khoá cho bảng lương."),
        tip: B("A tab you do not see is one your access does not open.", "Tab nào bạn không thấy là tab quyền của bạn không mở được."),
      },
    ],
    quiz: {
      question: B("The panel offers Approve all 5 clean, and 7 overtime requests are waiting. What happens to the other 2?",
                  "Khung đề nghị Phê duyệt tất cả 5 sạch, trong khi có 7 yêu cầu tăng ca đang chờ. Hai yêu cầu còn lại thì sao?"),
      options: [
        {
          text: B("They stay waiting — something about them needs a person to look", "Chúng vẫn chờ — có điều gì đó cần một người xem"),
          correct: true,
          explanation: B("Yes. Near a limit, not matching the grid, or on a closed day: those are yours to decide one by one.",
                         "Đúng vậy. Gần giới hạn, không khớp lưới, hoặc rơi vào ngày đã đóng: những yêu cầu đó bạn phải quyết định từng cái."),
        },
        {
          text: B("They are approved too, a moment later", "Chúng cũng được duyệt, ngay sau đó"),
          correct: false,
          explanation: B("Let's rethink that. The button approves exactly the number it says.",
                         "Hãy nghĩ lại một chút. Nút đó duyệt đúng số lượng ghi trên nó."),
        },
        {
          text: B("They are turned down", "Chúng bị từ chối"),
          correct: false,
          explanation: B("Let's rethink that. Nothing is turned down for you; they wait.", "Hãy nghĩ lại một chút. Không có gì bị từ chối thay bạn; chúng chờ."),
        },
      ],
    },
  },

  L21: {
    id: "L21", station: "wftime", mins: 7,
    title: B("Time, time off and overtime", "Chấm công, nghỉ phép và tăng ca"),
    goal: B("Read the Time tab and its exceptions, decide leave requests, and approve overtime inside its limits.",
            "Đọc tab Chấm công và các ngoại lệ, quyết định đơn nghỉ phép, và duyệt tăng ca trong giới hạn của nó."),
    steps: [
      {
        screen: "wftime", anchor: "wf-time",
        kicker: B("Time", "Chấm công"),
        title: B("Four views of the hours worked", "Bốn cách xem giờ làm việc"),
        body: B("<b>Timeline</b> and <b>Week Grid</b> show the hours; <b>Exceptions</b> lists the days that did not add up; <b>Import</b> brings in a time-clock file.",
                "<b>Dòng thời gian</b> và <b>Lưới tuần</b> cho thấy số giờ; <b>Ngoại lệ</b> liệt kê những ngày không khớp; <b>Nhập</b> đưa vào tệp của máy chấm công."),
      },
      {
        screen: "wftime", anchor: "rep-wf-exc",
        kicker: B("Exceptions", "Ngoại lệ"),
        title: B("Fix them now, or meet them on Close", "Xử lý ngay, hoặc gặp lại ở Chốt kỳ"),
        body: B("A missing check-out or a late start with no reason is an exception. Left alone, each one becomes a flag at the end of the week.",
                "Thiếu giờ ra hoặc đi trễ không lý do là một ngoại lệ. Nếu để đó, mỗi ngoại lệ sẽ thành một cờ cảnh báo vào cuối tuần."),
      },
      {
        screen: "wftime", anchor: "wf-leave-queue",
        kicker: B("Time Off", "Nghỉ phép"),
        title: B("The approval queue", "Hàng chờ phê duyệt"),
        body: B("Leave waiting for a decision, oldest first. Mai asks for three days in August; approve it here and the days are counted before the pay run reads them.",
                "Đơn nghỉ chờ quyết định, đơn cũ nhất lên trước. Mai xin nghỉ ba ngày trong tháng 8; duyệt ở đây và các ngày đó được tính trước khi đợt lương đọc tới."),
      },
      {
        screen: "wftime", anchor: "wf-timeoff",
        kicker: B("On someone's behalf", "Đăng ký thay"),
        title: B("Apply on behalf, when they cannot", "Đăng ký thay, khi họ không tự làm được"),
        body: B("<b>Apply on behalf</b> files leave for somebody who cannot — off sick, no phone. It is recorded as filed by you.",
                "<b>Đăng ký thay</b> nộp đơn nghỉ cho người không tự làm được — ốm, không có điện thoại. Việc đó được ghi là do bạn nộp."),
      },
      {
        screen: "wftime", anchor: "wf-ot-queue",
        kicker: B("Overtime", "Tăng ca"),
        title: B("The overtime approval queue", "Hàng chờ duyệt tăng ca"),
        body: B("Every request waiting, with its day and hours. Hùng's Thursday is marked near the limit: approve it knowing he has little room left this month.",
                "Mọi yêu cầu đang chờ, kèm ngày và số giờ. Ngày thứ Năm của Hùng được đánh dấu gần giới hạn: hãy duyệt khi đã biết anh còn ít chỗ trong tháng này."),
      },
      {
        screen: "wftime", anchor: "wf-ot-rules",
        kicker: B("The limits", "Các giới hạn"),
        title: B("The monthly and yearly limits", "Giới hạn theo tháng và theo năm"),
        body: B("The rules panel lists the limits your company works to — here 40 hours a month and 200 a year. A request past one is marked, never quietly approved.",
                "Khung quy định liệt kê các giới hạn công ty bạn áp dụng — ở đây là 40 giờ một tháng và 200 giờ một năm. Yêu cầu vượt một giới hạn sẽ được đánh dấu, không bao giờ được duyệt âm thầm."),
      },
    ],
    quiz: {
      question: B("Hùng's overtime is marked near the limit. What does approving it do?",
                  "Tăng ca của Hùng được đánh dấu gần giới hạn. Duyệt nó thì điều gì xảy ra?"),
      options: [
        {
          text: B("It is paid this week and leaves him less room for the rest of the month", "Nó được trả trong tuần này và anh còn ít chỗ hơn cho phần còn lại của tháng"),
          correct: true,
          explanation: B("Yes. The mark is a warning, not a block. It tells you the next request may go past the limit.",
                         "Đúng vậy. Dấu đó là lời cảnh báo, không phải điều chặn. Nó cho biết yêu cầu tiếp theo có thể vượt giới hạn."),
        },
        {
          text: B("Nothing — marked requests cannot be approved", "Không gì cả — yêu cầu bị đánh dấu không duyệt được"),
          correct: false,
          explanation: B("Let's rethink that. Near the limit can still be approved. Past it is what the law forbids.",
                         "Hãy nghĩ lại một chút. Gần giới hạn vẫn duyệt được. Vượt giới hạn mới là điều luật cấm."),
        },
        {
          text: B("It resets his monthly total", "Nó đặt lại tổng giờ tháng của anh"),
          correct: false,
          explanation: B("Let's rethink that. Approving adds to his total; nothing resets until the month ends.",
                         "Hãy nghĩ lại một chút. Duyệt là cộng thêm vào tổng của anh; không có gì đặt lại cho tới hết tháng."),
        },
      ],
    },
  },

  L22: {
    id: "L22", station: "wfclose", mins: 7,
    title: B("Close the week for payroll", "Chốt tuần cho bảng lương"),
    goal: B("Clear a week's flags the right way, read the payroll handoff, then lock the week and send it on.",
            "Xử lý đúng cách các cờ cảnh báo của tuần, đọc phần chuyển giao tiền lương, rồi khoá tuần và gửi đi."),
    steps: [
      {
        screen: "wfclose", anchor: "wf-close",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("One week, and how many flags are left", "Một tuần, và còn bao nhiêu cờ cảnh báo"),
        body: B("Workforce › <b>Close</b>. The week at the top, and the number still flagged. Payroll trusts a locked week; this is where it is made trustworthy.",
                "Lực lượng lao động › <b>Chốt kỳ</b>. Tuần ở phía trên, và số cờ cảnh báo còn lại. Bảng lương tin vào một tuần đã khoá; đây là nơi làm cho nó đáng tin."),
      },
      {
        screen: "wfclose", anchor: "wf-close-flags",
        kicker: B("The flags", "Các cờ cảnh báo"),
        title: B("Every day that did not add up", "Mỗi ngày không khớp"),
        body: B("A missing check-out, overtime over the plan, a late start with no reason. <b>Review all</b> walks the flags of one kind together.",
                "Thiếu giờ ra, tăng ca vượt kế hoạch, đi trễ không lý do. <b>Xem lại tất cả</b> đi qua các cờ cùng một loại một lượt."),
      },
      {
        screen: "wfclose", anchor: "rep-wf-fix",
        kicker: B("Fix", "Điều chỉnh"),
        title: B("Fix it when the record is wrong", "Điều chỉnh khi dữ liệu sai"),
        body: B("Hùng forgot to check out on Tuesday. <b>Fix</b> opens the day so you can put in the time he really left. The flag clears when the day adds up.",
                "Hùng quên chấm giờ ra vào thứ Ba. <b>Điều chỉnh</b> mở ngày đó để bạn nhập đúng giờ anh thực sự về. Cờ biến mất khi ngày đó khớp."),
      },
      {
        screen: "wfclose", anchor: "rep-wf-asis",
        kicker: B("Approve as-is", "Phê duyệt nguyên trạng"),
        title: B("Approve as-is when it really happened", "Phê duyệt nguyên trạng khi điều đó thật sự đã xảy ra"),
        body: B("Trang's extra hours were a real rush. <b>Approve as-is</b> says so, and the hours go to payroll as they are. It is not a way to make the lock button work.",
                "Giờ làm thêm của Trang là một đợt cao điểm thật. <b>Phê duyệt nguyên trạng</b> xác nhận điều đó, và số giờ đi vào bảng lương như hiện có. Đó không phải cách để mở khoá nút."),
      },
      {
        screen: "wfclose", anchor: "wf-close-handoff",
        kicker: B("Payroll handoff", "Chuyển giao tiền lương"),
        title: B("What payroll will receive", "Những gì bảng lương sẽ nhận"),
        body: B("<b>Regular hours</b>, <b>Overtime</b>, <b>Bonus hours</b> and an estimated gross. Read them the way payroll will: a number that looks wrong here is wrong on a payslip.",
                "<b>Giờ thông thường</b>, <b>Tăng ca</b>, <b>Giờ thưởng</b> và tổng thu nhập ước tính. Hãy đọc như bảng lương sẽ đọc: con số trông sai ở đây sẽ sai trên phiếu lương."),
      },
      {
        screen: "wfclose", anchor: "wf-close-lock",
        kicker: B("The action", "Thao tác chính"),
        title: B("Lock week & send to payroll", "Khóa tuần và gửi vào bảng lương"),
        body: B("The button stays grey until every flag is fixed or approved as-is, and only an attendance or payroll manager can press it. Afterwards the week says <b>Week locked</b>.",
                "Nút này giữ màu xám cho tới khi mọi cờ đã được điều chỉnh hoặc duyệt nguyên trạng, và chỉ quản lý chấm công hoặc quản lý lương mới bấm được. Sau đó tuần ghi <b>Tuần bị khóa</b>."),
        consequence: B("Affects everyone's time this week — payroll reads it from now on. Reversible: Reopen… asks for a reason, and the reason is kept. Verify first: no flags left, and the handoff numbers make sense.",
                       "Ảnh hưởng: giờ công của mọi người trong tuần — bảng lương đọc nó từ đây. Hoàn tác: Mở lại… sẽ hỏi lý do, và lý do được lưu lại. Kiểm tra trước: không còn cờ nào, và các con số chuyển giao hợp lý."),
      },
    ],
    quiz: {
      question: B("One flag is left: a missing check-out you are sure is a mistake. The lock is grey and it is late. What do you do?",
                  "Còn một cờ: thiếu giờ ra mà bạn chắc chắn là nhầm. Nút khoá đang xám và đã muộn. Bạn làm gì?"),
      options: [
        {
          text: B("Fix the day with the real time, then lock the week", "Điều chỉnh ngày đó với giờ thật, rồi khoá tuần"),
          correct: true,
          explanation: B("Yes. Fix corrects the record; the flag clears and the lock becomes available.",
                         "Đúng vậy. Điều chỉnh sửa lại dữ liệu; cờ biến mất và nút khoá bấm được."),
        },
        {
          text: B("Approve it as-is so the lock works", "Phê duyệt nguyên trạng để nút khoá bấm được"),
          correct: false,
          explanation: B("Let's rethink that. As-is sends a wrong day to payroll as if it were true.",
                         "Hãy nghĩ lại một chút. Duyệt nguyên trạng là gửi một ngày sai sang bảng lương như thể đó là thật."),
        },
        {
          text: B("Leave the week open for payroll to sort out", "Để tuần mở cho bảng lương tự xử lý"),
          correct: false,
          explanation: B("Let's rethink that. Payroll cannot see the day behind the number. The person who can is you.",
                         "Hãy nghĩ lại một chút. Bảng lương không thấy được ngày đằng sau con số. Người thấy được là bạn."),
        },
      ],
    },
  },

  L23: {
    id: "L23", station: "access", mins: 8,
    title: B("Access, and handing it over while you are away", "Quyền truy cập, và bàn giao khi bạn vắng mặt"),
    goal: B("Read who can do what as roles, check someone's access with See it as, and hand your own access over for a while.",
            "Đọc ai được làm gì qua các vai trò, kiểm tra quyền của một người bằng See it as, và bàn giao quyền của bạn trong một thời gian."),
    steps: [
      {
        screen: "access", anchor: "ac-head",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("One page for who can do what", "Một trang cho ai được làm gì"),
        body: B("Settings › <b>Access & delegation</b>. Everyone can open it. Giving roles, <b>See it as</b> and <b>New role</b> are for access managers.",
                "Cài đặt › <b>Quyền truy cập & uỷ quyền</b>. Ai cũng mở được. Cấp vai trò, <b>See it as</b> và <b>New role</b> dành cho người quản lý truy cập."),
        tip: B("This screen has no Vietnamese yet, so its buttons are named here in English, as you will see them.",
               "Màn hình này chưa có tiếng Việt, nên các nút được gọi bằng tiếng Anh ở đây, đúng như bạn sẽ thấy."),
      },
      {
        screen: "access", anchor: "ac-tabs",
        kicker: B("Four tabs", "Bốn tab"),
        title: B("Roles, People, Screens, Hand-overs", "Bốn tab: Roles, People, Screens, Hand-overs"),
        body: B("<b>Roles</b> lists what can be given. <b>People</b> shows what each person holds. <b>Screens</b> shows who opens each screen. <b>Hand-overs</b> lists access lent for a while.",
                "<b>Roles</b> liệt kê những gì có thể cấp. <b>People</b> cho thấy mỗi người đang có gì. <b>Screens</b> cho thấy ai mở được từng màn hình. <b>Hand-overs</b> liệt kê quyền đang cho mượn tạm thời."),
      },
      {
        screen: "access", anchor: "ac-rolecard",
        kicker: B("A role", "Một vai trò"),
        title: B("One sentence, and who holds it", "Một câu, và ai đang có nó"),
        body: B("Each card says in one sentence what the role lets someone do, and <b>Held by</b> how many. Open it for what it opens on the left menu, and what it lets them do.",
                "Mỗi thẻ nói trong một câu vai trò đó cho phép làm gì, và <b>Held by</b> bao nhiêu người. Mở thẻ để xem nó mở gì trên thanh bên trái và cho phép làm gì."),
      },
      {
        screen: "access", anchor: "ac-newrole",
        kicker: B("A new role", "Một vai trò mới"),
        title: B("Called, belongs, worked out for you", "Tên gọi, thuộc về đâu, phần được tính sẵn"),
        body: B("<b>New role</b> asks what it is called, then where it belongs, and works out the rest. You give a role to a person with <b>Give a role</b>; <b>Take this role away</b> ends it.",
                "<b>New role</b> hỏi tên gọi, rồi nó thuộc về đâu, và tự tính phần còn lại. Bạn cấp vai trò cho một người bằng <b>Give a role</b>; <b>Take this role away</b> kết thúc nó."),
      },
      {
        screen: "access", anchor: "ac-seeas",
        kicker: B("Checking", "Kiểm tra"),
        title: B("See it as someone else", "Xem như một người khác"),
        body: B("<b>See it as</b> shows the app as that person sees it. A banner says <b>Looking at this as</b> them, and that you still have exactly your own access. <b>Back to your own view</b> ends it.",
                "<b>See it as</b> cho thấy ứng dụng như người đó nhìn thấy. Một dải thông báo ghi <b>Looking at this as</b> người đó, và rằng bạn vẫn giữ đúng quyền của mình. <b>Back to your own view</b> kết thúc việc xem."),
      },
      {
        screen: "access", anchor: "rep-ac-handover",
        kicker: B("Going away", "Khi đi vắng"),
        title: B("Hand my access over", "Bàn giao quyền của tôi"),
        body: B("Who, what and until when, then <b>Hand it over</b>. Here Lan Anh covers until 21 August. It is taken back automatically the morning after the end date.",
                "Cho ai, quyền nào và đến khi nào, rồi <b>Hand it over</b>. Ở đây Lan Anh trực thay tới hết 21/8. Quyền được tự động thu hồi vào sáng hôm sau ngày kết thúc."),
        consequence: B("Affects what that person can open until the end date. Reversible: yes — Take back what has ended, or end it early. Verify first: the end date, and that you picked only what they need.",
                       "Ảnh hưởng: những gì người đó mở được cho tới ngày kết thúc. Hoàn tác: có — thu hồi phần đã hết hạn, hoặc kết thúc sớm. Kiểm tra trước: ngày kết thúc, và bạn chỉ chọn những gì họ cần."),
      },
    ],
    quiz: {
      question: B("You are away for two weeks and Lan Anh must approve pay runs while you are gone. What is the right way?",
                  "Bạn vắng hai tuần và Lan Anh phải duyệt các đợt lương trong lúc đó. Cách đúng là gì?"),
      options: [
        {
          text: B("Hand my access over to her until the day you are back", "Bàn giao quyền của bạn cho chị tới ngày bạn quay lại"),
          correct: true,
          explanation: B("Yes. It is recorded, and it ends by itself the morning after the end date.",
                         "Đúng vậy. Việc đó được ghi lại, và tự kết thúc vào sáng hôm sau ngày kết thúc."),
        },
        {
          text: B("Give her your password", "Đưa chị mật khẩu của bạn"),
          correct: false,
          explanation: B("Let's rethink that. Everything she did would be recorded as you, and nothing would end it.",
                         "Hãy nghĩ lại một chút. Mọi việc chị làm sẽ được ghi là của bạn, và không gì kết thúc nó."),
        },
        {
          text: B("Use See it as to act for her", "Dùng See it as để làm thay chị"),
          correct: false,
          explanation: B("Let's rethink that. See it as is only a view; you keep exactly your own access while you look.",
                         "Hãy nghĩ lại một chút. See it as chỉ là cách xem; bạn giữ đúng quyền của mình trong lúc xem."),
        },
      ],
    },
  },

  L24: {
    id: "L24", station: "govreports", mins: 7,
    title: B("File the month's government reports", "Nộp các báo cáo nhà nước của tháng"),
    goal: B("Find the filings your country asks for, generate one for a finished month, and know that Payobook prepares it and you send it.",
            "Tìm các báo cáo mà quốc gia bạn yêu cầu, tạo một báo cáo cho một tháng đã xong, và biết Payobook chuẩn bị còn bạn là người nộp."),
    steps: [
      {
        screen: "govreports", anchor: "gr-head",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("The filings the law asks of you", "Các báo cáo pháp luật yêu cầu bạn"),
        body: B("Compliance › <b>Filings</b>. The company and the month at the top, and a tile for every filing this country asks for.",
                "Tuân thủ › <b>Tờ khai</b>. Công ty và tháng ở trên cùng, và mỗi báo cáo quốc gia này yêu cầu có một ô."),
      },
      {
        screen: "govreports", anchor: "gr-countries",
        kicker: B("Which country", "Quốc gia nào"),
        title: B("One country at a time", "Mỗi lần một quốc gia"),
        body: B("The chips switch country. A country whose payroll module is not installed shows <b>coming soon</b> — the filings exist; this system has not got them yet.",
                "Các nhãn chuyển quốc gia. Quốc gia nào chưa cài mô-đun tính lương sẽ hiện <b>sắp có</b> — các báo cáo vẫn tồn tại; chỉ là hệ thống này chưa có chúng."),
      },
      {
        screen: "govreports", anchor: "gr-grid",
        kicker: B("The tiles", "Các ô"),
        title: B("Grouped by the office that reads them", "Nhóm theo cơ quan tiếp nhận"),
        body: B("Social insurance filings in one group, labour changes in another. Each tile names the form, and <b>Generate</b> starts it.",
                "Các báo cáo bảo hiểm xã hội một nhóm, biến động lao động một nhóm. Mỗi ô ghi tên mẫu, và <b>Tạo</b> bắt đầu nó."),
      },
      {
        screen: "filing_flow", anchor: "cp-gen-steps",
        kicker: B("Generate a filing", "Tạo hồ sơ"),
        title: B("Choose the filing → Scope → Generate", "Chọn hồ sơ → Phạm vi → Tạo"),
        body: B("Pressing a tile's Generate lands you on <b>Scope</b> with the filing already chosen. The same flow opens from the search bar: type \"Generate a filing\".",
                "Bấm Tạo trên một ô đưa bạn thẳng tới <b>Phạm vi</b> với báo cáo đã được chọn. Luồng này cũng mở từ thanh tìm kiếm: gõ \"Tạo hồ sơ\"."),
      },
      {
        screen: "filing_flow", anchor: "cp-generate",
        kicker: B("Scope", "Phạm vi"),
        title: B("The company and the month", "Công ty và tháng"),
        body: B("Check the company and the month before you generate. A month whose pay runs are not all done makes a filing that is short.",
                "Kiểm tra công ty và tháng trước khi tạo. Một tháng mà các đợt lương chưa hoàn tất hết sẽ cho ra một báo cáo bị thiếu."),
      },
      {
        screen: "filing_flow", anchor: "cp-gen-go",
        kicker: B("The action", "Thao tác chính"),
        title: B("Generate makes files — you file them", "Tạo sinh ra tệp — bạn là người nộp"),
        body: B("<b>Generate</b> makes the files for you to download. Nothing is sent anywhere; you submit them to the office yourself.",
                "<b>Tạo</b> sinh ra các tệp để bạn tải xuống. Không có gì được gửi đi đâu cả; bạn tự nộp chúng cho cơ quan."),
      },
    ],
    quiz: {
      question: B("July's F&B pay run is still waiting for approval. Should you generate July's insurance filing today?",
                  "Đợt lương tháng 7 của F&B vẫn đang chờ phê duyệt. Hôm nay bạn có nên tạo báo cáo bảo hiểm tháng 7 không?"),
      options: [
        {
          text: B("Not yet — wait until every July run is done", "Chưa — chờ tới khi mọi đợt lương tháng 7 hoàn tất"),
          correct: true,
          explanation: B("Yes. The filing reads what has been computed; an unfinished run makes it short.",
                         "Đúng vậy. Báo cáo đọc phần đã tính; một đợt còn dở khiến nó bị thiếu."),
        },
        {
          text: B("Yes — Generate sends it, so the sooner the better", "Có — Tạo là gửi đi, nên càng sớm càng tốt"),
          correct: false,
          explanation: B("Let's rethink that. Generate sends nothing, and a filing on an unfinished month has to be corrected later.",
                         "Hãy nghĩ lại một chút. Tạo không gửi gì cả, và báo cáo lập trên một tháng chưa xong sẽ phải đính chính sau."),
        },
        {
          text: B("Yes — the filing only needs Retail's run", "Có — báo cáo chỉ cần đợt lương Bán lẻ"),
          correct: false,
          explanation: B("Let's rethink that. The filing is for the company, and F&B's people are in it too.",
                         "Hãy nghĩ lại một chút. Báo cáo là của cả công ty, và nhân viên F&B cũng nằm trong đó."),
        },
      ],
    },
  },

  /* ------------- the four short ones (five steps each since step 5) -------------- */
  L25: {
    id: "L25", station: "growth", mins: 5,
    title: B("Growth plans", "Kế hoạch phát triển"),
    goal: B("Know the four steps of a growth plan and read its objectives.",
            "Biết bốn bước của một kế hoạch phát triển và đọc các mục tiêu của nó."),
    steps: [
      {
        screen: "growth", anchor: "gw-numbers",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Help that is written down", "Sự hỗ trợ được ghi lại"),
        body: B("Lifecycle › <b>Growth plans</b>. <b>Open</b>, <b>Still a conversation</b>, <b>Plans running</b>, <b>Waiting on a decision</b>, and plans <b>Drifting or at risk</b>.",
                "Vòng đời nhân sự › <b>Kế hoạch phát triển</b>. <b>Đang mở</b>, <b>Vẫn đang trao đổi</b>, <b>Kế hoạch đang chạy</b>, <b>Đang chờ quyết định</b>, và các kế hoạch <b>Chệch hướng hoặc có rủi ro</b>."),
        tip: B("Only people with a growth-plan role see this tab. A manager starts from the form Ask HR about someone in your team.",
               "Chỉ người có vai trò kế hoạch phát triển mới thấy tab này. Quản lý bắt đầu từ biểu mẫu hỏi nhân sự về một người trong nhóm."),
      },
      {
        screen: "growth", anchor: "gw-steps",
        kicker: B("Four steps", "Bốn bước"),
        title: B("Asked → Coaching → Plan running → Decision", "Đã yêu cầu → Kèm cặp → Kế hoạch đang chạy → Quyết định"),
        body: B("It starts as a conversation and coaching. Only if that is not enough does it become a written plan, and every plan ends in a decision.",
                "Nó bắt đầu bằng trao đổi và kèm cặp. Chỉ khi chưa đủ mới thành kế hoạch bằng văn bản, và mọi kế hoạch đều kết thúc bằng một quyết định."),
      },
      {
        screen: "growth", anchor: "gw-list",
        kicker: B("One card each", "Mỗi người một thẻ"),
        title: B("Where each plan has got to", "Mỗi kế hoạch đã tới đâu"),
        body: B("Each card names the person, the step and how many objectives are on track. Press a step above to see only its cards.",
                "Mỗi thẻ ghi tên người, bước hiện tại và bao nhiêu mục tiêu đang đúng hướng. Bấm một bước ở trên để chỉ xem các thẻ của bước đó."),
      },
      {
        screen: "growth", anchor: "gw-objectives",
        kicker: B("Objectives", "Mục tiêu"),
        title: B("On track, at risk, met, not met", "Đúng hướng, có rủi ro, đạt, không đạt"),
        body: B("Each objective is marked as it goes. One at risk is the moment to talk, not the end of the plan.",
                "Mỗi mục tiêu được đánh dấu theo tiến độ. Một mục tiêu có rủi ro là lúc cần trao đổi, không phải lúc kết thúc kế hoạch."),
      },
      {
        screen: "growth", anchor: "gw-steps",
        kicker: B("The end", "Kết thúc"),
        title: B("Every plan ends in a decision", "Mọi kế hoạch đều kết thúc bằng một quyết định"),
        body: B("<b>Waiting on a decision</b> counts plans whose time is up. Nobody should sit there for long: the person is waiting to hear.",
                "<b>Đang chờ quyết định</b> đếm các kế hoạch đã hết thời hạn. Không ai nên nằm ở đó lâu: người đó đang chờ nghe kết quả."),
      },
    ],
    quiz: {
      question: B("A manager says someone in their team is struggling. What comes first?",
                  "Một quản lý nói có người trong nhóm đang gặp khó khăn. Điều gì đến trước?"),
      options: [
        {
          text: B("A conversation, and coaching", "Một cuộc trao đổi, và kèm cặp"),
          correct: true,
          explanation: B("Yes. Many stop there. A written plan comes only if it is needed.",
                         "Đúng vậy. Nhiều trường hợp dừng ở đó. Kế hoạch bằng văn bản chỉ đến khi cần."),
        },
        {
          text: B("A written plan with dates", "Một kế hoạch bằng văn bản có mốc thời gian"),
          correct: false,
          explanation: B("Let's rethink that. The plan is step three, after the conversation and coaching.",
                         "Hãy nghĩ lại một chút. Kế hoạch là bước ba, sau trao đổi và kèm cặp."),
        },
      ],
    },
  },

  L26: {
    id: "L26", station: "contractends", mins: 5,
    title: B("Contracts that end soon", "Hợp đồng sắp hết hạn"),
    goal: B("Know how the Contracts board counts down, and the three decisions it asks for.",
            "Biết bảng Hợp đồng đếm ngược thế nào, và ba quyết định nó yêu cầu."),
    steps: [
      {
        screen: "contractends", anchor: "cl-numbers",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Sixty days ahead", "Trước sáu mươi ngày"),
        body: B("Lifecycle › <b>Contracts</b>. <b>Ending within 60 days</b>, <b>Nobody has decided</b>, <b>Waiting to be agreed</b>, <b>Being evaluated</b>, <b>Made permanent this year</b>.",
                "Vòng đời nhân sự › <b>Hợp đồng</b>. <b>Kết thúc trong vòng 60 ngày</b>, <b>Chưa ai quyết định</b>, <b>Đang chờ đồng ý</b>, <b>Đang được đánh giá</b>, <b>Chuyển chính thức trong năm nay</b>."),
      },
      {
        screen: "contractends", anchor: "cl-steps",
        kicker: B("Four steps", "Bốn bước"),
        title: B("Running → Decision needed → Being agreed → Decided", "Đang hiệu lực → Cần quyết định → Đang chờ đồng ý → Đã quyết định"),
        body: B("Every contract is at one step. <b>Decision needed</b> is the one to empty first.",
                "Mỗi hợp đồng nằm ở một bước. <b>Cần quyết định</b> là bước cần dọn trước tiên."),
      },
      {
        screen: "contractends", anchor: "cl-list",
        kicker: B("Who", "Ai"),
        title: B("The contracts at that step", "Các hợp đồng ở bước đó"),
        body: B("Đức's fixed term ends on 30 September and nobody has decided yet.",
                "Hợp đồng xác định thời hạn của Đức kết thúc ngày 30/9 và chưa ai quyết định."),
      },
      {
        screen: "contractends", anchor: "cl-raise",
        kicker: B("Raise it", "Nêu ra"),
        title: B("Raise the decision", "Nêu quyết định"),
        body: B("A contract with an end date and no decision yet offers <b>Raise the decision</b>. That puts it in front of the people who must agree.",
                "Hợp đồng có ngày kết thúc mà chưa có quyết định sẽ có nút <b>Nêu quyết định</b>. Nút đó đưa nó tới những người phải đồng ý."),
      },
      {
        screen: "contractends", anchor: "cl-decide",
        kicker: B("Three choices", "Ba lựa chọn"),
        title: B("Make it permanent, extend it, or let it end", "Chuyển chính thức, gia hạn, hoặc để hết hạn"),
        body: B("Whatever is chosen, it is chosen before the end date. A contract that simply runs out stops the person's pay in the middle of a month.",
                "Dù chọn gì, nó phải được chọn trước ngày kết thúc. Hợp đồng cứ thế hết hạn sẽ làm dừng lương của người đó giữa tháng."),
      },
    ],
    quiz: {
      question: B("Đức's fixed term ends on 30 September and Nobody has decided. What is the risk?",
                  "Hợp đồng xác định thời hạn của Đức kết thúc ngày 30/9 và Chưa ai quyết định. Rủi ro là gì?"),
      options: [
        {
          text: B("His contract stops and October's pay run leaves him out", "Hợp đồng của anh dừng và đợt lương tháng 10 bỏ sót anh"),
          correct: true,
          explanation: B("Yes. Payroll pays from a running contract. Raise the decision now.",
                         "Đúng vậy. Bảng lương trả theo hợp đồng đang hiệu lực. Hãy nêu quyết định ngay."),
        },
        {
          text: B("None — contracts renew on their own", "Không có — hợp đồng tự gia hạn"),
          correct: false,
          explanation: B("Let's rethink that. Nothing renews by itself; someone has to decide.",
                         "Hãy nghĩ lại một chút. Không có gì tự gia hạn; phải có người quyết định."),
        },
      ],
    },
  },

  L27: {
    id: "L27", station: "compliancemore", mins: 5,
    title: B("Bank checks, young workers and audit", "Kiểm tra ngân hàng, lao động trẻ và kiểm toán"),
    goal: B("Know how a bank change is checked twice, what Young workers guards, and where to see who changed what.",
            "Biết một thay đổi ngân hàng được kiểm tra hai lần thế nào, Lao động chưa thành niên bảo vệ điều gì, và xem ai đã sửa gì ở đâu."),
    steps: [
      {
        screen: "compliancemore", anchor: "cp-bank-steps",
        kicker: B("Bank", "Ngân hàng"),
        title: B("Draft → HR Review → Finance Review → Approved", "Nháp → Nhân sự xét duyệt → Tài chính xét duyệt → Đã duyệt"),
        body: B("Drop a bank letter under <b>New bank-change request</b>. HR checks it, then Finance, and only then does the employee's bank account change.",
                "Thả thư của ngân hàng vào <b>Yêu cầu thay đổi ngân hàng mới</b>. Nhân sự kiểm tra, rồi Tài chính, và chỉ khi đó tài khoản ngân hàng của nhân viên mới thay đổi."),
        tip: B("An account already used by someone else is flagged before anyone approves it.",
               "Tài khoản đã được người khác dùng sẽ bị đánh dấu trước khi có ai duyệt."),
      },
      {
        screen: "compliancemore", anchor: "cp-bank-new",
        kicker: B("Start one", "Bắt đầu một yêu cầu"),
        title: B("The letter is the evidence", "Thư ngân hàng là bằng chứng"),
        body: B("Drop the bank's confirmation letter, statement or passbook. Without a document there is nothing for HR and Finance to check against.",
                "Thả thư xác nhận của ngân hàng, sao kê hoặc sổ tiết kiệm. Không có chứng từ thì Nhân sự và Tài chính không có gì để đối chiếu."),
      },
      {
        screen: "compliancemore", anchor: "cp-young",
        kicker: B("Young workers", "Lao động chưa thành niên"),
        title: B("Hour limits for anyone under 18", "Giới hạn giờ làm cho người dưới 18 tuổi"),
        body: B("<b>Protected</b>, <b>Compliant this week</b>, <b>Violations in the last 30 days</b> and <b>Missing birthdays</b> — a missing birthday means the guard cannot tell who to protect.",
                "<b>Được bảo vệ</b>, <b>Tuân thủ tuần này</b>, <b>Vi phạm trong 30 ngày qua</b> và <b>Thiếu ngày sinh</b> — thiếu ngày sinh nghĩa là hệ thống không biết cần bảo vệ ai."),
      },
      {
        screen: "compliancemore", anchor: "cp-audit",
        kicker: B("Audit", "Nhật ký kiểm toán"),
        title: B("Who changed what, and when", "Ai đã sửa gì, và khi nào"),
        body: B("A read-only record of changes. Filter to <b>Salary only</b> to answer \"who changed this salary\"; the login view shows who signed in.",
                "Nhật ký chỉ đọc về các thay đổi. Lọc <b>Chỉ có lương</b> để trả lời \"ai đã sửa mức lương này\"; chế độ đăng nhập cho biết ai đã đăng nhập."),
      },
      {
        screen: "compliancemore", anchor: "cp-audit-filters",
        kicker: B("Narrow it", "Thu hẹp"),
        title: B("Today, This week, By me, Salary only, Logins", "Hôm nay, Tuần này, Do tôi, Chỉ có lương, Đăng nhập"),
        body: B("Pick the filter that matches the question. Nothing here can be edited, which is why it can be trusted.",
                "Chọn bộ lọc đúng với câu hỏi. Không gì ở đây sửa được, và đó là lý do nó đáng tin."),
      },
    ],
    quiz: {
      question: B("An employee emails a new bank account number. What is the safe way to change it?",
                  "Một nhân viên gửi email số tài khoản ngân hàng mới. Cách an toàn để thay đổi là gì?"),
      options: [
        {
          text: B("A bank-change request with the bank's letter, checked by HR and Finance", "Một yêu cầu thay đổi ngân hàng kèm thư của ngân hàng, được Nhân sự và Tài chính kiểm tra"),
          correct: true,
          explanation: B("Yes. Two checks and a document stop the most common way pay is stolen.",
                         "Đúng vậy. Hai lần kiểm tra và một chứng từ ngăn được cách phổ biến nhất khiến lương bị đánh cắp."),
        },
        {
          text: B("Type it straight onto the employee record", "Gõ thẳng vào hồ sơ nhân viên"),
          correct: false,
          explanation: B("Let's rethink that. An email can be forged; this skips both checks.",
                         "Hãy nghĩ lại một chút. Email có thể bị giả mạo; cách này bỏ qua cả hai bước kiểm tra."),
        },
      ],
    },
  },

  L28: {
    id: "L28", station: "peoplemore", mins: 5,
    title: B("The rest of People and Home", "Phần còn lại của Con người và Trang chủ"),
    goal: B("Know what the Wall, Announce and the smaller People tabs are for.",
            "Biết Bảng vinh danh, Thông báo và các tab nhỏ của Con người dùng để làm gì."),
    steps: [
      {
        screen: "peoplemore", anchor: "rep-pm-wall",
        kicker: B("Home › Wall", "Trang chủ › Bảng vinh danh"),
        title: B("What people said about each other", "Mọi người nói gì về nhau"),
        body: B("<b>Say thank you</b> puts praise on the Wall, tied to one of the company's values. Everyone can read it.",
                "<b>Nói lời cảm ơn</b> đưa lời khen lên Bảng vinh danh, gắn với một giá trị của công ty. Ai cũng đọc được."),
      },
      {
        screen: "peoplemore", anchor: "rep-pm-announce",
        kicker: B("Home › Announce", "Trang chủ › Thông báo"),
        title: B("What the company told everyone", "Điều công ty đã thông báo tới mọi người"),
        body: B("Everyone can open it: the messages sent to the whole company, newest first.",
                "Ai cũng mở được: các thông báo gửi tới cả công ty, mới nhất ở trên."),
      },
      {
        screen: "peoplemore", anchor: "rep-pm-plan",
        kicker: B("People › Announce", "Con người › Thông báo"),
        title: B("Where messages are planned", "Nơi lên kế hoạch thông báo"),
        body: B("The people who send messages plan the month on one calendar here. Most people only ever see Home › Announce.",
                "Những người gửi thông báo lên kế hoạch cho cả tháng trên một lịch ở đây. Phần lớn mọi người chỉ thấy Trang chủ › Thông báo."),
      },
      {
        screen: "peoplemore", anchor: "rep-pm-tiles",
        kicker: B("People", "Con người"),
        title: B("Where they work, Assets, Goals, Announce", "Nơi họ làm việc, Tài sản, Mục tiêu, Thông báo"),
        body: B("People who work for more than one company; the laptops and cards handed out; this year's goals; messages to your people, on one calendar.",
                "Người làm cho nhiều công ty; máy tính và thẻ đã cấp; mục tiêu năm nay; thông báo tới mọi người, trên một lịch."),
      },
      {
        screen: "peoplemore", anchor: "rep-tabs",
        kicker: B("Missing a tab?", "Thiếu một tab?"),
        title: B("A tab shows only when your company uses it", "Tab chỉ hiện khi công ty bạn dùng nó"),
        body: B("Goals, Praise and Announce depend on what your company has switched on and on your access. A missing tab is not broken.",
                "Mục tiêu, Khen ngợi và Thông báo phụ thuộc vào những gì công ty bạn đã bật và quyền của bạn. Tab không có không phải là bị lỗi."),
      },
    ],
    quiz: {
      question: B("A colleague has no Goals tab under People. What is the likely reason?",
                  "Một đồng nghiệp không thấy tab Mục tiêu trong Con người. Lý do có thể là gì?"),
      options: [
        {
          text: B("Their company or their access does not include it", "Công ty hoặc quyền của họ không bao gồm nó"),
          correct: true,
          explanation: B("Yes. A tab shows only to people the screen itself lets in.",
                         "Đúng vậy. Tab chỉ hiện với những người mà chính màn hình cho phép."),
        },
        {
          text: B("Payobook is broken", "Payobook bị lỗi"),
          correct: false,
          explanation: B("Let's rethink that. Absent means not for them, not broken.",
                         "Hãy nghĩ lại một chút. Không có nghĩa là không dành cho họ, không phải bị lỗi."),
        },
      ],
    },
  },

  /* ------------------------------------------------ LEARN REFRESH step 5
     The outline-only Pay Run stations, made full: Adjust (Retro and
     Proration, one tab since the rail cutover), Settle, and the four tabs a
     run is finished through. Words are read from ledger.xml /
     ledger_cockpits.py, payrun_results.xml, pb_pay_delivery.xml,
     paycal_board.xml and incentives_board.xml (FACTS_STEP5). Where the
     screen has no Vietnamese, the VI lesson names the English label and
     glosses it. */
  L29: {
    id: "L29", station: "employees", mins: 8,
    title: B("Employees and their contracts", "Nhân viên và hợp đồng của họ"),
    goal: B("Find who cannot be paid before a run, and read one person's contract from the drawer beside the list.",
            "Tìm ra ai không thể trả lương trước một đợt, và đọc hợp đồng của một người từ ngăn ngay cạnh danh sách."),
    steps: [
      {
        screen: "employees", anchor: "pe-kpis",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("The numbers line", "Dòng con số"),
        body: B("People › <b>Employees</b>. <b>Headcount</b>, <b>Running contracts</b>, <b>Expiring within 30 days</b>, <b>New this month</b>, <b>Monthly wage</b> and <b>Payroll-ready</b>. A number that can narrow the list does.",
                "Con người › <b>Nhân viên</b>. <b>Số lượng nhân sự</b>, <b>Hợp đồng đang hiệu lực</b>, <b>Hết hạn trong 30 ngày</b>, <b>Mới trong tháng này</b>, <b>Lương hàng tháng</b> và <b>Sẵn sàng trả lương</b>. Con số nào lọc được danh sách thì bấm vào là lọc."),
        tip: B("Running contracts counts contracts, not people. Payroll-ready counts bank details only.",
               "Hợp đồng đang hiệu lực đếm hợp đồng, không đếm người. Sẵn sàng trả lương chỉ đếm thông tin ngân hàng."),
      },
      {
        screen: "employees", anchor: "pe-filters",
        kicker: B("Before a run", "Trước đợt lương"),
        title: B("Press No contract", "Bấm Không có hợp đồng"),
        body: B("<b>All</b>, <b>Running</b>, <b>Expiring soon</b>, <b>New this month</b>, <b>No contract</b>. Everyone under No contract will be left out of the run.",
                "<b>Tất cả</b>, <b>Đang hiệu lực</b>, <b>Sắp hết hạn</b>, <b>Mới trong tháng này</b>, <b>Không có hợp đồng</b>. Mọi người trong Không có hợp đồng sẽ bị bỏ ra khỏi đợt lương."),
      },
      {
        screen: "employees", anchor: "pe-roster",
        kicker: B("One row each", "Mỗi người một dòng"),
        title: B("The tick means two things", "Dấu tích nghĩa là hai điều"),
        body: B("A row is ready only with a running contract <b>and</b> bank details. Hover the warning and it names what is missing. Đức has no bank details, so he computes and is not paid.",
                "Một dòng chỉ sẵn sàng khi có hợp đồng đang hiệu lực <b>và</b> thông tin ngân hàng. Rê chuột lên dấu cảnh báo, nó ghi rõ thiếu gì. Đức chưa có thông tin ngân hàng, nên vẫn được tính lương mà không nhận được tiền."),
      },
      {
        screen: "employees", anchor: "pe-rowcontract",
        kicker: B("The door", "Lối vào"),
        title: B("Contract, on the row", "Hợp đồng, ngay trên dòng"),
        body: B("<b>Contract</b> opens that person's contract in a drawer, without leaving the list. The <b>Contracts</b> button at the top opens every contract on its own board.",
                "<b>Hợp đồng</b> mở hợp đồng của người đó trong một ngăn, không rời danh sách. Nút <b>Hợp đồng</b> ở trên cùng mở mọi hợp đồng trên một bảng riêng."),
      },
      {
        screen: "employees", anchor: "cd-tabs",
        kicker: B("The drawer", "Ngăn hợp đồng"),
        title: B("Terms, Components, History", "Terms, Components, History"),
        body: B("The header says when the contract ends and its state. Three tabs hold the rest.",
                "Phần đầu cho biết khi nào hợp đồng kết thúc và trạng thái của nó. Ba tab chứa phần còn lại: <b>Terms</b> (điều khoản), <b>Components</b> (thành phần), <b>History</b> (lịch sử)."),
        tip: B("The drawer's words are in English on the screen in both languages.",
               "Các chữ trong ngăn này hiện bằng tiếng Anh trên màn hình ở cả hai ngôn ngữ."),
      },
      {
        screen: "employees", anchor: "rep-cd-terms",
        kicker: B("Terms", "Điều khoản"),
        title: B("The money and the dates", "Tiền và ngày tháng"),
        body: B("A pencil marks what you can change; only an HR manager can. <b>Salary structure</b> left empty means a pay scheme pays this person.",
                "Biểu tượng bút chì đánh dấu chỗ sửa được; chỉ quản lý nhân sự mới sửa được. <b>Salary structure</b> (cấu trúc lương) để trống nghĩa là một chương trình lương trả cho người này."),
      },
      {
        screen: "employees", anchor: "rep-cd-comps",
        kicker: B("Components", "Thành phần"),
        title: B("Every amount says where it comes from", "Mỗi khoản đều ghi nó đến từ đâu"),
        body: B("<b>Paid by</b> names the scheme. Each amount is <b>Held on this contract</b>, <b>From a pay data file</b> or worked out by a formula. One fed each month can rightly read 0 here.",
                "<b>Paid by</b> ghi chương trình lương. Mỗi khoản là <b>Lưu trên hợp đồng này</b>, <b>Từ tệp dữ liệu lương</b> hoặc do công thức tính ra. Khoản được cấp mỗi tháng có thể hiện 0 ở đây là đúng."),
      },
      {
        screen: "employees", anchor: "rep-cd-history",
        kicker: B("History", "Lịch sử"),
        title: B("Every change, from and to", "Mọi thay đổi, từ đâu tới đâu"),
        body: B("Each line says what changed, from what to what, when, and where it came from. Mai's wage went from 11,000,000 ₫ to 12,000,000 ₫ in January.",
                "Mỗi dòng cho biết cái gì thay đổi, từ bao nhiêu thành bao nhiêu, khi nào, và đến từ đâu. Lương của Mai từ 11.000.000 ₫ lên 12.000.000 ₫ vào tháng 1."),
      },
      {
        screen: "employees", anchor: "cd-save",
        kicker: B("Saving", "Lưu"),
        title: B("Nothing is saved until Save", "Chưa bấm Save thì chưa lưu gì"),
        body: B("Once you change something, a bar slides up: <b>Discard</b> or <b>Save 1 change</b>. A change that needs approval says Sent for approval instead.",
                "Khi bạn thay đổi gì đó, một thanh trượt lên: <b>Discard</b> (bỏ) hoặc <b>Save 1 change</b> (lưu 1 thay đổi). Thay đổi nào cần phê duyệt sẽ ghi Sent for approval (đã gửi đi duyệt)."),
      },
    ],
    quiz: {
      question: B("Payroll-ready reads 98%. Đức's row shows a warning: No bank details. Will Đức be paid this month?",
                  "Sẵn sàng trả lương hiện 98%. Dòng của Đức có cảnh báo: chưa có thông tin ngân hàng. Tháng này Đức có nhận được lương không?"),
      options: [
        {
          text: B("No — a row is ready only with a running contract and bank details", "Không — một dòng chỉ sẵn sàng khi có hợp đồng đang hiệu lực và thông tin ngân hàng"),
          correct: true,
          explanation: B("Yes. Get his bank details in before the run; he computes either way.",
                         "Đúng vậy. Hãy bổ sung thông tin ngân hàng của anh trước đợt lương; đằng nào anh cũng được tính."),
        },
        {
          text: B("Yes — 98% means nearly everyone is fine", "Có — 98% nghĩa là gần như ai cũng ổn"),
          correct: false,
          explanation: B("Let's rethink that. The row decides, not the number; his warning names what is missing.",
                         "Hãy nghĩ lại một chút. Dòng mới quyết định, không phải con số; cảnh báo của anh ghi rõ thiếu gì."),
        },
      ],
    },
  },

  L33: {
    id: "L33", station: "structures", mins: 6,
    title: B("Salary structures, and when you need one", "Cấu trúc lương, và khi nào bạn cần"),
    goal: B("Know which one pays a person, the structure or the pay scheme, and read the Salary Structures screen.",
            "Biết cái nào trả lương cho một người, cấu trúc hay chương trình lương, và đọc được màn hình Cấu trúc lương."),
    steps: [
      {
        screen: "structures", anchor: "sr-kpis",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("The older way of computing pay", "Cách tính lương thế hệ trước"),
        body: B("Settings › <b>Salary Structures</b>. A structure is a set of salary rules. <b>Employees covered</b> counts the people whose contract names one.",
                "Cài đặt › <b>Cấu trúc lương</b>. Một cấu trúc là một bộ quy tắc lương. <b>Nhân viên áp dụng</b> đếm những người có hợp đồng ghi một cấu trúc."),
      },
      {
        screen: "structures", anchor: "sr-roster",
        kicker: B("The rule", "Quy tắc"),
        title: B("The contract decides", "Hợp đồng quyết định"),
        body: B("A contract that names a structure is computed by its rules. A contract with none is paid by the person's pay scheme. Here, five people on probation still follow a structure.",
                "Hợp đồng ghi một cấu trúc thì được tính theo quy tắc của cấu trúc đó. Hợp đồng không có cấu trúc thì được trả theo chương trình lương của người đó. Ở đây, năm người đang thử việc vẫn đi theo một cấu trúc."),
      },
      {
        screen: "employees", anchor: "rep-cd-terms",
        kicker: B("Where to look", "Xem ở đâu"),
        title: B("On the contract's Terms", "Trên Terms của hợp đồng"),
        body: B("Mai's contract shows <b>Salary structure</b>: —. So her pay scheme pays her. Check this field when a payslip does not follow the scheme you expected.",
                "Hợp đồng của Mai ghi <b>Salary structure</b>: —. Nên chương trình lương trả lương cho chị. Hãy xem trường này khi một phiếu lương không theo chương trình bạn nghĩ."),
      },
      {
        screen: "structures", anchor: "sr-filters",
        kicker: B("Status", "Trạng thái"),
        title: B("Active, Draft, Deprecated", "Đang hoạt động, Nháp, Ngừng sử dụng"),
        body: B("A structure nobody should start on is marked Deprecated, not deleted. Old payslips still point at it, and a report over those months needs it.",
                "Một cấu trúc không ai nên dùng thêm được đánh dấu Ngừng sử dụng, chứ không xoá. Phiếu lương cũ vẫn trỏ tới nó, và báo cáo cho những tháng đó vẫn cần nó."),
      },
      {
        screen: "structures", anchor: "sr-new",
        kicker: B("A new one?", "Tạo mới?"),
        title: B("Most companies build a pay scheme instead", "Phần lớn công ty dựng chương trình lương thay vào đó"),
        body: B("<b>New structure</b> exists, but new pay logic belongs in a pay scheme, built in Settings › Guided setup › New configuration.",
                "<b>Cấu trúc mới</b> vẫn có, nhưng logic lương mới thuộc về chương trình lương, dựng ở Cài đặt › Thiết lập có hướng dẫn › Cấu hình mới."),
      },
    ],
    quiz: {
      question: B("You moved Retail onto a pay scheme, but July's payslips still follow the old rules. What is the likely cause?",
                  "Bạn đã chuyển Bán lẻ sang một chương trình lương, nhưng phiếu lương tháng 7 vẫn theo quy tắc cũ. Nguyên nhân có thể là gì?"),
      options: [
        {
          text: B("Their contracts still name the old salary structure", "Hợp đồng của họ vẫn ghi cấu trúc lương cũ"),
          correct: true,
          explanation: B("Yes. A structure on the contract wins. Clear it and recompute.",
                         "Đúng vậy. Cấu trúc trên hợp đồng được ưu tiên. Hãy bỏ nó đi rồi tính lại."),
        },
        {
          text: B("The pay scheme needs a day to take effect", "Chương trình lương cần một ngày để có hiệu lực"),
          correct: false,
          explanation: B("Let's rethink that. Nothing waits a day; the contract decides.",
                         "Hãy nghĩ lại một chút. Không có gì phải chờ một ngày; hợp đồng quyết định."),
        },
      ],
    },
  },

  L34: {
    id: "L34", station: "integrations", mins: 7,
    title: B("Connections, fetch schedule and arrivals", "Kết nối, lịch lấy dữ liệu và hồ sơ đến"),
    goal: B("Tell a connection that works from one that stopped, set how often it fetches, and find what arrived.",
            "Phân biệt kết nối đang chạy với kết nối đã ngừng, đặt tần suất lấy dữ liệu, và tìm những gì đã đến."),
    steps: [
      {
        screen: "integrations", anchor: "ig-kpis",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Every connection, in one line of numbers", "Mọi kết nối, trong một dòng con số"),
        body: B("Settings › <b>Integrations</b>. <b>Connected</b>, <b>Errors</b>, <b>Staged records</b> — and <b>Feeds · 1 stale</b> when a feed has not run on time.",
                "Cài đặt › <b>Tích hợp</b>. <b>Đã kết nối</b>, <b>Lỗi</b>, <b>Bản ghi đang chờ</b> — và <b>Nguồn cấp dữ liệu · 1 cũ</b> khi có nguồn cấp không chạy đúng hạn."),
      },
      {
        screen: "integrations", anchor: "ig-roster",
        kicker: B("Read the time", "Đọc thời gian"),
        title: B("Last sync, not the badge", "Lần đồng bộ gần nhất, không phải nhãn"),
        body: B("The time clock last synced 9 days ago and has 214 staged rows. That is a month of attendance that never became pay data.",
                "Máy chấm công đồng bộ lần cuối 9 ngày trước và có 214 dòng đang chờ. Đó là cả một tháng chấm công chưa bao giờ thành dữ liệu lương."),
        tip: B("<b>N mappings</b> on a row opens Mapping for that connection.",
               "<b>N ánh xạ</b> trên một dòng mở Ánh xạ cho kết nối đó."),
      },
      {
        screen: "integrations", anchor: "ic-actions",
        kicker: B("One connection", "Một kết nối"),
        title: B("Test, pull, fetch fields", "Kiểm tra, kéo dữ liệu, lấy trường"),
        body: B("A row opens the connection. <b>Test connection</b> checks the login and moves no data. <b>Pull data</b> brings data in now.",
                "Một dòng mở ra kết nối đó. <b>Test connection</b> kiểm tra đăng nhập và không chuyển dữ liệu nào. <b>Pull data</b> kéo dữ liệu về ngay."),
        tip: B("The connection screen is in English in both languages.",
               "Màn hình kết nối hiện bằng tiếng Anh ở cả hai ngôn ngữ."),
      },
      {
        screen: "integrations", anchor: "ic-fetch",
        kicker: B("The schedule", "Lịch"),
        title: B("Automatic fetch", "Tự động lấy dữ liệu"),
        body: B("Switch on <b>Fetch this system's data automatically</b>, then pick how often: Daily, Weekly, Monthly or Last day of month. <b>Next run</b> says when.",
                "Bật <b>Fetch this system's data automatically</b> (tự động lấy dữ liệu), rồi chọn tần suất: Daily, Weekly, Monthly hoặc Last day of month. <b>Next run</b> cho biết lần chạy kế tiếp."),
        tip: B("Off means every pay run fetches this system's data while you wait.",
               "Tắt nghĩa là mỗi đợt lương sẽ lấy dữ liệu của hệ thống này trong lúc bạn chờ."),
      },
      {
        screen: "integrations", anchor: "rep-ig-arrivals",
        kicker: B("What arrived", "Những gì đã đến"),
        title: B("Arrivals from the connected system", "Hồ sơ đến từ hệ thống được kết nối"),
        body: B("Type \"Arrivals\" in the search bar. Each change the connected system sent is listed with its outcome. One marked <b>review</b> is waiting for a person.",
                "Gõ \"Arrivals\" vào thanh tìm kiếm. Mỗi thay đổi hệ thống được kết nối gửi về được liệt kê kèm kết quả. Dòng ghi <b>review</b> đang chờ một người xem."),
        tip: B("Record changes that need a decision also wait in Home › Approvals.",
               "Các thay đổi hồ sơ cần quyết định cũng chờ ở Trang chủ › Phê duyệt."),
      },
      {
        screen: "integrations", anchor: "ig-connect",
        kicker: B("A new system", "Một hệ thống mới"),
        title: B("Connect a system", "Kết nối một hệ thống"),
        body: B("Four steps: choose, connect, map the fields, confirm. The fields then feed a pay scheme through Mapping.",
                "Bốn bước: chọn, kết nối, ánh xạ trường, xác nhận. Sau đó các trường cấp dữ liệu cho chương trình lương qua Ánh xạ."),
      },
    ],
    quiz: {
      question: B("A connection says Connected, but its last sync was 9 days ago. What does that mean?",
                  "Một kết nối ghi Đã kết nối, nhưng lần đồng bộ gần nhất là 9 ngày trước. Điều đó nghĩa là gì?"),
      options: [
        {
          text: B("The login works, but no data has come in for 9 days", "Đăng nhập vẫn được, nhưng 9 ngày nay không có dữ liệu nào về"),
          correct: true,
          explanation: B("Yes. Open it, check Automatic fetch, and Pull data before the run.",
                         "Đúng vậy. Hãy mở nó, xem Automatic fetch, và Pull data trước đợt lương."),
        },
        {
          text: B("All is well — Connected means up to date", "Mọi thứ ổn — Đã kết nối là đã cập nhật"),
          correct: false,
          explanation: B("Let's rethink that. Connected is only the login.",
                         "Hãy nghĩ lại một chút. Đã kết nối chỉ nói về đăng nhập."),
        },
      ],
    },
  },

  /* ---------- LEARN REFRESH step 5 — the Insights line, made full ---------- */
  L35: {
    id: "L35", station: "insights", mins: 6,
    title: B("Read Insights › Pulse", "Đọc Phân tích › Tổng quan"),
    goal: B("Quote the headline with its state, compare months fairly, and know where each figure opens.",
            "Trích con số nổi bật kèm trạng thái, so các tháng cho công bằng, và biết mỗi con số mở ra đâu."),
    steps: [
      {
        screen: "insights", anchor: "in-hero",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("The latest run, whatever its state", "Đợt gần nhất, dù ở trạng thái nào"),
        body: B("Insights › <b>Pulse</b>. The big figure is the <b>net payroll</b> of the newest run, even a draft. The chip beside it says which state it is in.",
                "Phân tích › <b>Tổng quan</b>. Con số lớn là <b>lương thực chi</b> của đợt mới nhất, kể cả đợt còn nháp. Chip bên cạnh cho biết nó đang ở trạng thái nào."),
      },
      {
        screen: "insights", anchor: "in-hero",
        kicker: B("The move", "Mức thay đổi"),
        title: B("Month against month", "Tháng so với tháng"),
        body: B("The line under it compares every run in that month with the month before. A second division's run arriving moves it too.",
                "Dòng bên dưới so mọi đợt trong tháng đó với tháng trước. Khi đợt của một bộ phận khác về, dòng này cũng thay đổi."),
      },
      {
        screen: "insights", anchor: "in-trend",
        kicker: B("Cost story", "Diễn biến chi phí"),
        title: B("Pick the window first", "Chọn khoảng thời gian trước"),
        body: B("<b>3M</b>, <b>6M</b> or <b>12M</b>. Say which one you used whenever you quote the trend.",
                "<b>3M</b>, <b>6M</b> hoặc <b>12M</b>. Hãy nói rõ bạn dùng khoảng nào mỗi khi trích xu hướng."),
      },
      {
        screen: "insights", anchor: "in-duo",
        kicker: B("Compare fairly", "So sánh công bằng"),
        title: B("Per head, not total", "Theo đầu người, không theo tổng"),
        body: B("On the <b>Department leaderboard</b>, press <b>Per head</b>. One extra person explains most of what looks like a rise in a total. The <b>Statutory split</b> beside it shows what the law adds.",
                "Trên <b>Xếp hạng phòng ban</b>, bấm <b>Bình quân đầu người</b>. Thêm một người là đủ giải thích phần lớn cái vẻ tăng của một con số tổng. <b>Cơ cấu khoản đóng bắt buộc</b> bên cạnh cho thấy phần luật định cộng thêm."),
      },
      {
        screen: "insights", anchor: "in-pulse",
        kicker: B("People", "Con người"),
        title: B("Workforce pulse", "Nhịp nhân sự"),
        body: B("Attendance exceptions, time off and overtime this month. Each exception left open becomes a question on next month's payslips.",
                "Bất thường chấm công, nghỉ phép và tăng ca tháng này. Mỗi bất thường còn để mở sẽ thành một câu hỏi trên phiếu lương tháng sau."),
      },
      {
        screen: "insights", anchor: "in-explore",
        kicker: B("Go deeper", "Đi sâu hơn"),
        title: B("Every figure opens Explorer", "Mọi con số đều mở Explorer"),
        body: B("Press the big figure or any number and Explorer opens on it. <b>Ask something else</b> is there for the question this board did not expect.",
                "Bấm con số lớn hoặc bất kỳ con số nào, Explorer sẽ mở ra đúng nó. <b>Hỏi cái gì khác</b> dành cho câu hỏi bảng này không lường trước."),
      },
    ],
    quiz: {
      question: B("The headline shows ₫612 million with a Waiting for approval chip. Your CFO asks what July cost. What do you say?",
                  "Con số nổi bật là 612 triệu ₫ kèm chip Chờ phê duyệt. Giám đốc tài chính hỏi tháng 7 tốn bao nhiêu. Bạn trả lời thế nào?"),
      options: [
        {
          text: B("That is Retail's July run, not yet approved", "Đó là đợt tháng 7 của Bán lẻ, chưa được duyệt"),
          correct: true,
          explanation: B("Yes. Name the run and its state; it may still change.",
                         "Đúng vậy. Hãy nêu tên đợt và trạng thái của nó; nó vẫn có thể thay đổi."),
        },
        {
          text: B("₫612 million, final", "612 triệu ₫, đã chốt"),
          correct: false,
          explanation: B("Let's rethink that. The chip says it is not approved, and it is one division's run.",
                         "Hãy nghĩ lại một chút. Chip cho biết nó chưa được duyệt, và đó là đợt của một bộ phận."),
        },
      ],
    },
  },

  L36: {
    id: "L36", station: "explorer", mins: 7,
    title: B("Ask Explorer a question", "Đặt câu hỏi cho Explorer"),
    goal: B("Build a question from a measure, a split, a time and filters, and quote the answer with its scope.",
            "Dựng một câu hỏi từ chỉ tiêu, cách chia, thời gian và bộ lọc, rồi trích câu trả lời kèm phạm vi của nó."),
    steps: [
      {
        screen: "explorer", anchor: "ex-head",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Start from a starting point", "Bắt đầu từ một điểm xuất phát"),
        body: B("Insights › <b>Explorer</b>. <b>Starting points</b> are ready-made questions. <b>Compare schemes</b> puts every pay scheme side by side, month by month.",
                "Phân tích › <b>Khám phá dữ liệu</b>. <b>Điểm xuất phát</b> là các câu hỏi dựng sẵn. <b>So sánh các phương án lương</b> đặt mọi chương trình lương cạnh nhau, theo từng tháng."),
      },
      {
        screen: "explorer", anchor: "ex-rail",
        kicker: B("The question", "Câu hỏi"),
        title: B("Measure first, then By", "Chỉ tiêu trước, rồi Theo"),
        body: B("Choose what to count, like Net pay, then how to split it, like Division. Most wrong answers are the right filter on the wrong measure.",
                "Chọn thứ cần đếm, như Lương thực nhận, rồi cách chia, như Khối. Phần lớn câu trả lời sai là lọc đúng mà chọn nhầm chỉ tiêu."),
      },
      {
        screen: "explorer", anchor: "ex-when",
        kicker: B("When", "Khi nào"),
        title: B("The time is part of the question", "Thời gian là một phần câu hỏi"),
        body: B("Pick This month, Last month, This year, or drag across the month strip.",
                "Chọn Tháng này, Tháng trước, Năm nay, hoặc kéo qua dải các tháng."),
      },
      {
        screen: "explorer", anchor: "ex-filters",
        kicker: B("Where", "Ở đâu"),
        title: B("Every filter is a tag", "Mỗi bộ lọc là một thẻ"),
        body: B("<b>Main runs only</b> is on by default, so mid-month advances are left out. Remove a tag and the figure changes.",
                "<b>Chỉ các kỳ lương chính</b> bật sẵn, nên các đợt tạm ứng giữa tháng không được tính. Gỡ một thẻ là con số thay đổi."),
      },
      {
        screen: "explorer", anchor: "ex-headline",
        kicker: B("The answer", "Câu trả lời"),
        title: B("Quote it with its tags", "Trích nó kèm các thẻ"),
        body: B("The headline names the measure, the split and the total. <b>Explain</b> says what moved it; <b>Per person</b> divides it by the people in it.",
                "Dòng đầu ghi chỉ tiêu, cách chia và tổng. <b>Giải thích</b> cho biết điều gì làm nó thay đổi; <b>Trên mỗi người</b> chia nó cho số người trong đó."),
      },
      {
        screen: "explorer", anchor: "rep-ex-compare",
        kicker: B("Two schemes", "Hai chương trình"),
        title: B("Compare schemes", "So sánh các phương án lương"),
        body: B("One row per pay scheme, each in its own money. Explorer never adds two currencies together.",
                "Mỗi chương trình lương một dòng, mỗi dòng theo đồng tiền riêng. Explorer không bao giờ cộng hai loại tiền với nhau."),
      },
    ],
    quiz: {
      question: B("You remove the Main runs only tag and net pay goes up. Why?",
                  "Bạn gỡ thẻ Chỉ các kỳ lương chính và lương thực nhận tăng lên. Vì sao?"),
      options: [
        {
          text: B("Mid-month advances are now counted too", "Giờ các khoản tạm ứng giữa tháng cũng được tính"),
          correct: true,
          explanation: B("Yes. Same measure, wider scope — so quote the tags with the number.",
                         "Đúng vậy. Cùng chỉ tiêu, phạm vi rộng hơn — nên hãy trích kèm các thẻ."),
        },
        {
          text: B("Explorer recomputed the payslips", "Explorer đã tính lại phiếu lương"),
          correct: false,
          explanation: B("Let's rethink that. Explorer only reads; it never changes a payslip.",
                         "Hãy nghĩ lại một chút. Explorer chỉ đọc; nó không bao giờ thay đổi phiếu lương."),
        },
      ],
    },
  },

  L37: {
    id: "L37", station: "workforcean", mins: 5,
    title: B("People paid, month by month", "Số người được trả lương, theo từng tháng"),
    goal: B("Read headcount as people paid, and spot a month that left somebody out.",
            "Đọc số lượng là số người được trả lương, và nhận ra tháng nào đã bỏ sót ai đó."),
    steps: [
      {
        screen: "workforcean", anchor: "wa-head",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("The same months, read as people", "Vẫn những tháng đó, đọc theo con người"),
        body: B("Insights › <b>Workforce</b>. Pick the window: 1, 3, 6 or 12 months.",
                "Phân tích › <b>Lực lượng lao động</b>. Chọn khoảng thời gian: 1, 3, 6 hoặc 12 tháng."),
      },
      {
        screen: "workforcean", anchor: "wa-kpis",
        kicker: B("The numbers", "Các con số"),
        title: B("Paid, joined, left, cost per head", "Được trả, vào làm, đã nghỉ, chi phí bình quân"),
        body: B("<b>employees paid</b> counts payslips, not people employed. Cost per head is the fair way to compare two months.",
                "<b>nhân viên được trả lương</b> đếm phiếu lương, không đếm người đang làm. Chi phí bình quân đầu người là cách so hai tháng cho công bằng."),
      },
      {
        screen: "workforcean", anchor: "wa-chart",
        kicker: B("Read the line", "Đọc đường biểu đồ"),
        title: B("A step down is worth a look", "Một bậc tụt xuống đáng xem"),
        body: B("A step is a wave of joiners or leavers — or a run that left somebody out. Compare it with People › Employees before you explain it.",
                "Một bậc nhảy là một đợt người vào hoặc người nghỉ — hoặc một đợt lương đã bỏ sót ai đó. Hãy so với Con người › Nhân viên trước khi giải thích."),
      },
      {
        screen: "workforcean", anchor: "wa-duo",
        kicker: B("Time", "Thời gian"),
        title: B("Exceptions and overtime", "Bất thường và tăng ca"),
        body: B("Attendance exceptions and who carries the overtime. Hùng carries the most this month.",
                "Bất thường chấm công và ai đang gánh phần tăng ca. Tháng này Hùng gánh nhiều nhất."),
      },
      {
        screen: "workforcean", anchor: "wa-filters",
        kicker: B("Narrow it", "Thu hẹp"),
        title: B("One division at a time", "Mỗi lần một bộ phận"),
        body: B("Pick a division or department to see only its people. <b>Clear filters</b> brings the whole company back.",
                "Chọn một bộ phận hoặc phòng ban để chỉ xem người của nó. <b>Bỏ bộ lọc</b> đưa cả công ty trở lại."),
      },
    ],
    quiz: {
      question: B("People › Employees says 70, but employees paid in July says 69. What should you check?",
                  "Con người › Nhân viên ghi 70, nhưng số nhân viên được trả lương tháng 7 là 69. Bạn nên kiểm tra gì?"),
      options: [
        {
          text: B("Who is employed but had no July payslip", "Ai đang làm việc mà không có phiếu lương tháng 7"),
          correct: true,
          explanation: B("Yes. Often someone starting next month — or someone missed.",
                         "Đúng vậy. Thường là người bắt đầu từ tháng sau — hoặc một người bị sót."),
        },
        {
          text: B("Nothing — the two always differ", "Không gì cả — hai con số luôn khác nhau"),
          correct: false,
          explanation: B("Let's rethink that. The gap is exactly where a missing payslip hides.",
                         "Hãy nghĩ lại một chút. Khoảng chênh chính là chỗ một phiếu lương bị thiếu đang ẩn."),
        },
      ],
    },
  },

  L38: {
    id: "L38", station: "reports", mins: 6,
    title: B("Payroll Report and Budget", "Báo cáo lương và Ngân sách"),
    goal: B("Read one run's report against the run before, and see whether spending is on pace for the year.",
            "Đọc báo cáo của một đợt so với đợt trước, và xem chi tiêu có đúng nhịp cả năm không."),
    steps: [
      {
        screen: "reports", anchor: "rp-pick",
        kicker: B("Payroll Report", "Báo cáo lương"),
        title: B("One run, against the one before", "Một đợt, so với đợt trước"),
        body: B("Insights › <b>Payroll Report</b> opens on the newest run. Pick another from the list.",
                "Phân tích › <b>Báo cáo lương</b> mở trên đợt mới nhất. Chọn đợt khác trong danh sách."),
        tip: B("This report is in English on the screen in both languages.",
               "Báo cáo này hiện bằng tiếng Anh trên màn hình ở cả hai ngôn ngữ."),
      },
      {
        screen: "reports", anchor: "rp-kpis",
        kicker: B("The totals", "Các tổng"),
        title: B("Gross, deductions, net — and changes", "Tổng thu nhập, khấu trừ, thực nhận — và thay đổi"),
        body: B("<b>Changes</b> counts the people whose pay moved against the previous run. Open those first.",
                "<b>Changes</b> (thay đổi) đếm số người có lương thay đổi so với đợt trước. Hãy mở những người đó trước."),
      },
      {
        screen: "reports", anchor: "rp-tabs",
        kicker: B("Three views", "Ba cách xem"),
        title: B("Earnings, Deductions, Dept Summary", "Thu nhập, Khấu trừ, Tổng theo phòng ban"),
        body: B("Each row expands to its breakdown. Dept Summary adds the run up by department.",
                "Mỗi dòng mở ra phần chi tiết. Dept Summary cộng đợt lương theo phòng ban."),
      },
      {
        screen: "reports", anchor: "bg-months",
        kicker: B("Budget", "Ngân sách"),
        title: B("The whole year, or a stretch of it", "Cả năm, hoặc một khoảng trong năm"),
        body: B("Insights › <b>Budget</b>. <b>Whole year</b>, or press a month, shift-press another, or drag across them.",
                "Phân tích › <b>Ngân sách</b>. <b>Cả năm</b>, hoặc bấm một tháng, giữ Shift bấm tháng khác, hoặc kéo qua các tháng."),
      },
      {
        screen: "reports", anchor: "bg-heat",
        kicker: B("The reading", "Nhận định"),
        title: B("On pace, running warm, behind", "Đúng nhịp, đang nóng lên, chậm hơn năm"),
        body: B("Each function compares money gone with year gone. People is <b>On pace</b>; HR operations is <b>Running warm</b>.",
                "Mỗi bộ phận so tiền đã đi với năm đã trôi. Con người đang <b>Đúng nhịp</b>; Vận hành nhân sự <b>Đang nóng lên</b>."),
        tip: B("The pay figures fill in by themselves every night; nobody types them.",
               "Các con số lương tự điền mỗi đêm; không ai phải gõ."),
      },
    ],
    quiz: {
      question: B("By the end of July, HR operations has spent 69% of its year. Is that a problem?",
                  "Tới cuối tháng 7, Vận hành nhân sự đã chi 69% ngân sách cả năm. Có vấn đề không?"),
      options: [
        {
          text: B("Worth a look — money is going faster than the year", "Đáng xem — tiền đi nhanh hơn năm"),
          correct: true,
          explanation: B("Yes. About 58% of the year has gone, so it reads Running warm.",
                         "Đúng vậy. Khoảng 58% của năm đã trôi, nên nó hiện Đang nóng lên."),
        },
        {
          text: B("No — anything under 100% is fine", "Không — dưới 100% là ổn"),
          correct: false,
          explanation: B("Let's rethink that. Budget compares money gone with time gone, not with the total.",
                         "Hãy nghĩ lại một chút. Ngân sách so tiền đã đi với thời gian đã trôi, không so với tổng."),
        },
      ],
    },
  },

  L30: {
    id: "L30", station: "adjust", mins: 7,
    title: B("Back pay and part months", "Truy lĩnh và lương theo phần tháng"),
    goal: B("Read a back-pay line and a part-month line, find the days behind them, and know that nobody types either.",
            "Đọc một dòng truy lĩnh và một dòng theo phần tháng, tìm số ngày đứng sau chúng, và biết rằng không ai gõ tay dòng nào."),
    steps: [
      {
        screen: "retro", anchor: "lg-tabs",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Two ledgers, one tab", "Hai sổ, một tab"),
        body: B("Pay Run › <b>Adjust</b> has two tabs: <b>Retro</b> for back pay and <b>Proration</b> for part months. Nothing here is typed in. Loading a month's pay data fills both.",
                "Đợt lương › <b>Điều chỉnh</b> có hai tab: <b>Hồi tố</b> cho khoản truy lĩnh và <b>Phân bổ theo tỷ lệ</b> cho lương theo phần tháng. Không có gì ở đây được gõ tay. Tải dữ liệu lương của một tháng sẽ điền cả hai."),
      },
      {
        screen: "retro", anchor: "lg-kpis",
        kicker: B("The numbers", "Các con số"),
        title: B("Lines, people, loads — and the total", "Số dòng, số người, số lần tải — và tổng"),
        body: B("<b>Retro lines</b> counts every back-pay line and <b>Batches</b> the pay data loads that made them. <b>Total delta</b> is what they add to this month.",
                "<b>Retro lines</b> (số dòng truy lĩnh) đếm mọi dòng truy lĩnh, còn <b>Batches</b> (số lần tải) là các lần tải dữ liệu lương đã tạo ra chúng. <b>Total delta</b> (tổng chênh lệch) là phần chúng cộng thêm vào tháng này."),
        tip: B("These labels are in English on the screen in both languages.",
               "Các nhãn này hiện bằng tiếng Anh trên màn hình ở cả hai ngôn ngữ."),
      },
      {
        screen: "retro", anchor: "lg-rows",
        kicker: B("Old, new, delta", "Cũ, mới, chênh lệch"),
        title: B("One person, one component", "Một người, một thành phần"),
        body: B("Khoa's raise was dated 1 June, after June was paid. So June's difference, <b>800,000 ₫</b>, is added to July.",
                "Lần tăng lương của Khoa có hiệu lực từ 1/6, sau khi tháng 6 đã trả. Nên phần chênh của tháng 6, <b>800.000 ₫</b>, được cộng vào tháng 7."),
      },
      {
        screen: "retro", anchor: "lg-drawer",
        kicker: B("The trail", "Dấu vết"),
        title: B("Where the money came from and went", "Tiền đến từ đâu và đi về đâu"),
        body: B("A row opens its drawer. <b>Retro period</b> names the month being made good, <b>Applied in payslip</b> the payslip that pays it, and <b>Original payslip</b> the one that was short.",
                "Một dòng mở ra ngăn chi tiết. <b>Retro period</b> là tháng được bù, <b>Applied in payslip</b> là phiếu lương trả khoản đó, và <b>Original payslip</b> là phiếu đã bị thiếu."),
      },
      {
        screen: "proration", anchor: "lg-rows",
        kicker: B("Proration", "Phân bổ theo tỷ lệ"),
        title: B("Paid for part of the month", "Trả cho một phần tháng"),
        body: B("Two kinds of row. Hoa was promoted on 16 July, so July is split at the change. Tuấn started on 22 July, so he is paid for the days he was here.",
                "Có hai loại dòng. Hoa được thăng chức ngày 16/7, nên tháng 7 được chia tại thời điểm thay đổi. Tuấn bắt đầu làm ngày 22/7, nên anh được trả cho những ngày có mặt."),
      },
      {
        screen: "proration", anchor: "lg-drawer",
        kicker: B("The days", "Số ngày"),
        title: B("The days are in the drawer", "Số ngày nằm trong ngăn chi tiết"),
        body: B("The row shows money only. The drawer's <b>Period</b> section holds the <b>Basis</b> and the days on each side of the change: 15 days at the old pay, 16 at the new.",
                "Dòng chỉ hiện tiền. Phần <b>Period</b> trong ngăn chi tiết có <b>Basis</b> (cách tính) và số ngày ở mỗi phía của thay đổi: 15 ngày theo mức cũ, 16 ngày theo mức mới."),
        tip: B("Read the days before the money. If the days are right and the amount still looks wrong, look at the contract or the pay data.",
               "Hãy đọc số ngày trước khi đọc tiền. Nếu số ngày đúng mà số tiền vẫn có vẻ sai, hãy xem hợp đồng hoặc dữ liệu lương."),
      },
      {
        screen: "proration", anchor: "lg-facets",
        kicker: B("Answer one person", "Trả lời một người"),
        title: B("Filter to the question", "Lọc đúng câu hỏi"),
        body: B("Pick a <b>Component</b> or a <b>Batch</b>, then search the name. That is one employee's answer, ready before they ask.",
                "Chọn một <b>Component</b> (thành phần) hoặc một <b>Batch</b> (lần tải), rồi tìm theo tên. Đó là câu trả lời cho một nhân viên, sẵn sàng trước khi họ hỏi."),
      },
    ],
    quiz: {
      question: B("Khoa's raise was agreed today but dated back to 1 June. June is already paid. What do you do?",
                  "Lần tăng lương của Khoa được đồng ý hôm nay nhưng có hiệu lực từ 1/6. Tháng 6 đã trả. Bạn làm gì?"),
      options: [
        {
          text: B("Load July's pay data as usual — Retro adds June's difference to July", "Tải dữ liệu lương tháng 7 như thường lệ — Hồi tố cộng phần chênh của tháng 6 vào tháng 7"),
          correct: true,
          explanation: B("Yes, when the scheme's Back-pay switch is on. The line names June and shows old, new and the difference.",
                         "Đúng vậy, khi công tắc Truy lĩnh của chương trình lương đang bật. Dòng đó ghi tháng 6 và hiện mức cũ, mức mới và phần chênh."),
        },
        {
          text: B("Reopen June's pay run and compute it again", "Mở lại đợt lương tháng 6 và tính lại"),
          correct: false,
          explanation: B("Let's rethink that. June has been paid and reported. The difference is paid in July, with June named on the line.",
                         "Hãy nghĩ lại một chút. Tháng 6 đã được trả và báo cáo. Phần chênh được trả trong tháng 7, kèm tên tháng 6 trên dòng."),
        },
        {
          text: B("Type the difference onto Khoa's July payslip", "Gõ phần chênh vào phiếu lương tháng 7 của Khoa"),
          correct: false,
          explanation: B("Let's rethink that. A typed amount has no trail, and the next recompute removes it.",
                         "Hãy nghĩ lại một chút. Một con số gõ tay không có dấu vết, và lần tính lại kế tiếp sẽ xoá nó."),
        },
      ],
    },
  },

  L31: {
    id: "L31", station: "fullfinal", mins: 6,
    title: B("Settle someone who is leaving", "Quyết toán cho người nghỉ việc"),
    goal: B("Read a settlement from its steps to its breakdown, and know when it can be downloaded.",
            "Đọc một khoản quyết toán từ các bước tới phần chi tiết, và biết khi nào tải xuống được."),
    steps: [
      {
        screen: "fullfinal", anchor: "lg-kpis",
        kicker: B("What & why", "Là gì & vì sao"),
        title: B("Every settlement, and what it pays", "Mọi khoản quyết toán, và số tiền phải trả"),
        body: B("Pay Run › <b>Settle</b>. <b>Settlements</b> and <b>Manual</b> count them. <b>Net payable</b>, <b>Earnings</b> and <b>Deductions</b> add them up.",
                "Đợt lương › <b>Quyết toán</b>. <b>Settlements</b> và <b>Manual</b> đếm số khoản. <b>Net payable</b> (thực trả), <b>Earnings</b> (thu nhập) và <b>Deductions</b> (khấu trừ) cộng tổng của chúng."),
        tip: B("These labels are in English on the screen in both languages.",
               "Các nhãn này hiện bằng tiếng Anh trên màn hình ở cả hai ngôn ngữ."),
      },
      {
        screen: "fullfinal", anchor: "lg-steps",
        kicker: B("Three steps", "Ba bước"),
        title: B("Being prepared → Waiting for approval → Approved", "Being prepared → Waiting for approval → Approved"),
        body: B("The HR lead approves first, then Finance. A flag on a step says when one is waiting on you or was sent back to be fixed.",
                "Trưởng nhân sự duyệt trước, rồi tới Tài chính. Một dấu trên bước cho biết khi có khoản đang chờ bạn hoặc bị trả lại để sửa."),
      },
      {
        screen: "fullfinal", anchor: "lg-facets",
        kicker: B("Where it came from", "Nó đến từ đâu"),
        title: B("Auto or Manual", "Auto hay Manual"),
        body: B("<b>Auto</b> settlements appear by themselves when a month's pay data finishes loading, for everyone whose leaving date falls in it. <b>Manual</b> ones were made by hand.",
                "Khoản <b>Auto</b> (tự động) tự xuất hiện khi dữ liệu lương của một tháng tải xong, cho mọi người có ngày nghỉ rơi vào tháng đó. Khoản <b>Manual</b> (thủ công) do người làm tay."),
      },
      {
        screen: "fullfinal", anchor: "lg-rows",
        kicker: B("One row each", "Mỗi người một dòng"),
        title: B("Net payable, person by person", "Số thực trả, từng người một"),
        body: B("Hạnh left on 31 July. Her settlement is still Being prepared: on Lifecycle › Exits, Finance has not signed off yet.",
                "Hạnh nghỉ ngày 31/7. Khoản quyết toán của chị vẫn ở Being prepared: ở Vòng đời nhân sự › Nghỉ việc, Tài chính chưa xác nhận xong."),
      },
      {
        screen: "fullfinal", anchor: "lg-drawer",
        kicker: B("The breakdown", "Phần chi tiết"),
        title: B("Earnings less deductions", "Thu nhập trừ khấu trừ"),
        body: B("A row opens its drawer: basic salary, <b>Unused leave</b> paid out, then social, health and unemployment insurance. Net payable is earnings minus deductions.",
                "Một dòng mở ra ngăn chi tiết: lương cơ bản, <b>Unused leave</b> (phép chưa dùng) được trả, rồi bảo hiểm xã hội, y tế và thất nghiệp. Thực trả là thu nhập trừ khấu trừ."),
      },
      {
        screen: "fullfinal", anchor: "lg-rowact",
        kicker: B("Once approved", "Khi đã được duyệt"),
        title: B("Download the settlement", "Tải văn bản quyết toán"),
        body: B("Only an approved settlement offers <b>Download</b>, the document the person signs. Lan's is approved; Hạnh's is not.",
                "Chỉ khoản quyết toán đã được duyệt mới có nút <b>Download</b>, văn bản người đó ký nhận. Của Lan đã được duyệt; của Hạnh thì chưa."),
      },
    ],
    quiz: {
      question: B("Hạnh leaves on 31 July and is also in July's Retail pay run. What goes wrong if nothing changes?",
                  "Hạnh nghỉ ngày 31/7 và cũng có tên trong đợt lương tháng 7 của Bán lẻ. Nếu không thay đổi gì thì sai ở đâu?"),
      options: [
        {
          text: B("She is paid twice: once in the run, once in her settlement", "Chị được trả hai lần: một lần trong đợt lương, một lần trong quyết toán"),
          correct: true,
          explanation: B("Yes. Check the run before you submit it; money paid to someone who has left is hard to get back.",
                         "Đúng vậy. Hãy kiểm tra đợt lương trước khi gửi duyệt; tiền đã trả cho người đã nghỉ thì rất khó đòi lại."),
        },
        {
          text: B("Nothing — the settlement takes her out of the run", "Không sao — khoản quyết toán sẽ tự đưa chị ra khỏi đợt lương"),
          correct: false,
          explanation: B("Let's rethink that. Nothing takes her out of the run for you.",
                         "Hãy nghĩ lại một chút. Không có gì tự đưa chị ra khỏi đợt lương thay bạn."),
        },
      ],
    },
  },

  L32: {
    id: "L32", station: "afterrun", mins: 8,
    title: B("After the run: results, payments, calendar, awards", "Sau đợt lương: kết quả, chi trả, lịch lương, thưởng"),
    goal: B("Read a run as one grid, know the three things that must happen before people are paid, and where the month's dates and one-off awards live.",
            "Đọc một đợt lương trong một bảng, biết ba việc phải xảy ra trước khi mọi người nhận tiền, và biết ngày chốt của tháng cùng các khoản thưởng một lần nằm ở đâu."),
    steps: [
      {
        screen: "results", anchor: "rs-grid",
        kicker: B("Results", "Kết quả"),
        title: B("The whole run as one grid", "Cả đợt lương trong một bảng"),
        body: B("Pay Run › <b>Results</b>: one row per person, one column per component. It is read only; a row opens that person's payslip.",
                "Đợt lương › <b>Kết quả</b>: mỗi người một dòng, mỗi thành phần một cột. Chỉ để đọc; một dòng mở phiếu lương của người đó."),
      },
      {
        screen: "results", anchor: "rs-compare",
        kicker: B("Compare", "So sánh"),
        title: B("Against the previous run", "So với đợt trước"),
        body: B("Press <b>vs previous run</b> and each figure shows its move against that person's last payslip on the same scheme. A big arrow is the one to open.",
                "Bấm <b>so với đợt trước</b> và mỗi con số hiện mức thay đổi so với phiếu lương gần nhất của người đó trong cùng chương trình lương. Mũi tên lớn là cái cần mở ra xem."),
      },
      {
        screen: "results", anchor: "rs-head",
        kicker: B("Take it away", "Mang đi"),
        title: B("Export to Excel", "Xuất ra Excel"),
        body: B("<b>Export to Excel</b> hands the grid to finance as a spreadsheet. <b>Pay runs</b> picks another run.",
                "<b>Xuất ra Excel</b> gửi bảng cho bộ phận tài chính dưới dạng bảng tính. <b>Các đợt lương</b> chọn một đợt khác."),
      },
      {
        screen: "deliver", anchor: "dl-bank",
        kicker: B("Deliver", "Chi trả"),
        title: B("The bank file has its own approval", "Tệp ngân hàng có phê duyệt riêng"),
        body: B("Pay Run › <b>Deliver</b>, on an approved run. <b>Prepare bank file for approval</b> makes the file the bank pays from and sends it for approval.",
                "Đợt lương › <b>Chi trả</b>, trên một đợt đã duyệt. <b>Tạo tệp ngân hàng để duyệt</b> lập tệp mà ngân hàng dùng để chi và gửi nó đi duyệt."),
        tip: B("When your company's route needs no approval, the button says so and approves on the spot.",
               "Khi lộ trình của công ty bạn không cần phê duyệt, nút sẽ ghi rõ và duyệt ngay lập tức."),
      },
      {
        screen: "deliver", anchor: "dl-release",
        kicker: B("Money out", "Chi tiền"),
        title: B("Then the payment release", "Rồi tới lệnh chuyển tiền"),
        body: B("Once the bank file is approved, the <b>Payment release</b> is the go-ahead to send the money, through approval again. Until then it waits for the bank file.",
                "Khi tệp ngân hàng đã được duyệt, <b>Lệnh chuyển tiền</b> là sự cho phép gửi tiền đi, lại qua phê duyệt. Trước đó nó chờ tệp ngân hàng."),
      },
      {
        screen: "deliver", anchor: "dl-slips",
        kicker: B("Payslips out", "Phiếu lương ra"),
        title: B("Payslips by email, each with a password", "Phiếu lương qua email, mỗi phiếu một mật khẩu"),
        body: B("Each PDF is locked with its employee's own password. <b>Send payslips for approval</b> sends them on, and <b>Resend failures</b> retries the ones that did not arrive.",
                "Mỗi tệp PDF được khoá bằng mật khẩu riêng của nhân viên. <b>Gửi phiếu lương đi duyệt</b> đưa chúng đi, còn <b>Gửi lại thất bại</b> gửi lại những phiếu chưa tới nơi."),
      },
      {
        screen: "paycal", anchor: "pc-hero",
        kicker: B("Calendar", "Lịch lương"),
        title: B("When changes close", "Khi nào chốt thay đổi"),
        body: B("Pay Run › <b>Calendar</b> counts down to the day changes close for the month, and says when people are paid. Reopening a closed month needs a reason.",
                "Đợt lương › <b>Lịch lương</b> đếm ngược tới ngày chốt thay đổi của tháng, và cho biết ngày trả lương. Mở lại một tháng đã chốt cần nêu lý do."),
      },
      {
        screen: "awards", anchor: "aw-put",
        kicker: B("Awards", "Thưởng"),
        title: B("One-off money, approved first", "Khoản một lần, duyệt trước"),
        body: B("Pay Run › <b>Awards</b>. A bonus or spot award is approved, then <b>Put into a pay run</b> adds it to a draft run's payslips and recomputes them.",
                "Đợt lương › <b>Thưởng</b>. Một khoản thưởng được duyệt trước, rồi <b>Put into a pay run</b> (đưa vào đợt lương) cộng nó vào phiếu lương của một đợt nháp và tính lại."),
      },
    ],
    quiz: {
      question: B("July's run is Done. A manager asks whether the staff have been paid. Where do you look?",
                  "Đợt lương tháng 7 đã Hoàn tất. Một quản lý hỏi nhân viên đã nhận lương chưa. Bạn xem ở đâu?"),
      options: [
        {
          text: B("Deliver — whether the bank file and the payment release are approved", "Chi trả — tệp ngân hàng và lệnh chuyển tiền đã được duyệt chưa"),
          correct: true,
          explanation: B("Yes. Done means the run is approved. The money moves only after the release.",
                         "Đúng vậy. Hoàn tất nghĩa là đợt lương đã được duyệt. Tiền chỉ đi sau lệnh chuyển tiền."),
        },
        {
          text: B("Nowhere — Done means paid", "Không cần — Hoàn tất là đã trả"),
          correct: false,
          explanation: B("Let's rethink that. A Done run can still be waiting for its bank file.",
                         "Hãy nghĩ lại một chút. Một đợt Hoàn tất vẫn có thể đang chờ tệp ngân hàng."),
        },
        {
          text: B("Results — the net column", "Kết quả — cột thực nhận"),
          correct: false,
          explanation: B("Let's rethink that. Results shows what was computed, not what was sent.",
                         "Hãy nghĩ lại một chút. Kết quả cho thấy số đã tính, không phải số đã gửi."),
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
    desc: B("Compute Retail's July pay run, catch what Payobook does not flag, submit it for approval — then take it back.",
            "Tính đợt lương tháng 7 của Bán lẻ, bắt được điều Payobook không đánh dấu, gửi phê duyệt — rồi thu hồi lại."),
    consequence: {
      title: B("You are about to compute 48 payslips", "Bạn sắp tính 48 phiếu lương"),
      scope: B("July 2026 for the people Hoa Sen Retail — End-Month Payroll pays. 48 draft payslips are created; no other scheme and no other month is touched.",
               "Tháng 7/2026 của những người thuộc Hoa Sen Retail — End-Month Payroll. 48 phiếu lương nháp được tạo; không chương trình lương nào khác và không tháng nào khác bị ảnh hưởng."),
      reversible: B("Yes. Drafts can be computed again or deleted, nothing is paid or sent, and nobody sees anything until the run is Done.",
                    "Được. Bản nháp có thể tính lại hoặc xoá, chưa có gì được chi hay gửi đi, và không ai thấy gì cho tới khi đợt lương Hoàn tất."),
      verify: B("That the pay scheme and the month are the ones you meant, and which answer you gave to \"What should these values do?\".",
                "Rằng chương trình lương và tháng đúng là cái bạn định chạy, và bạn đã chọn câu trả lời nào cho \"Các giá trị này dùng để làm gì?\"."),
    },
    anomaly: {
      title: B("The 4.6 that was typed as 46", "Con số 4,6 bị gõ thành 46"),
      body: B("Trần Văn Hùng's overtime came through at 4,200,000 ₫ against 1,100,000 ₫ in June — 382%. Nothing on the screen flags it: Need review counts people Payobook could not pay, not big jumps. It reads like a peak week, and a decimal point dropped in a timesheet reads exactly the same. Only you can tell them apart, by opening the timesheet.",
             "Tăng ca của Trần Văn Hùng vào hệ thống ở mức 4.200.000 ₫ so với 1.100.000 ₫ của tháng 6 — bằng 382%. Không gì trên màn hình đánh dấu nó: Cần xem xét đếm những người Payobook không trả được, không đếm các mức tăng lớn. Nó trông như một tuần cao điểm, và một dấu thập phân bị mất trong bảng chấm công trông y hệt như vậy. Chỉ bạn phân biệt được, bằng cách mở bảng chấm công."),
    },
    debrief: {
      did: [
        B("Picked the pay scheme, and with it the rulebook every payslip in the run was computed by.",
          "Chọn chương trình lương, và cùng với nó là bộ quy tắc mà mọi phiếu lương trong đợt được tính theo."),
        B("Read the consequence card before computing, so you knew the scope and the way back before you acted.",
          "Đọc thẻ hậu quả trước khi tính, để biết phạm vi và lối quay lại trước khi thao tác."),
        B("Read Need review for what it counts, and spotted the one jump nothing flagged.",
          "Đọc Cần xem xét đúng với thứ nó đếm, và nhận ra mức tăng mà không gì đánh dấu."),
        B("Submitted the run, then withdrew it — and saw it come back to Draft, unchanged.",
          "Gửi đợt lương đi phê duyệt, rồi thu hồi — và thấy nó quay về Nháp, giữ nguyên."),
      ],
      checklist: [
        B("The pay scheme and the month are the ones you meant.",
          "Chương trình lương và tháng đúng là cái bạn định chạy."),
        B("Everyone Need review lists is understood: people not in Payobook yet, and anyone Payobook could not pay.",
          "Mọi người trong danh sách Cần xem xét đều đã được hiểu: người chưa có trong Payobook, và bất kỳ ai Payobook không trả được."),
        B("Total net against last month — and you can explain the change in one sentence.",
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
    title: B("A run came back — fix it and send it in again", "Một đợt lương bị trả lại — sửa và gửi lại"),
    desc: B("F&B's July run was sent back with a note. Read it, fix the right thing, send it in again — and clear away a run that should never have existed.",
            "Đợt lương tháng 7 của F&B bị trả lại kèm ghi chú. Hãy đọc, sửa đúng chỗ, gửi lại — và dọn đi một đợt lương lẽ ra không nên tồn tại."),
    consequence: {
      title: B("Sending it in again starts the route from the top", "Gửi lại là bắt đầu lộ trình từ đầu"),
      scope: B("The F&B July run, all 21 payslips together. It leaves Draft and waits at Payroll check again.",
               "Đợt lương tháng 7 của F&B, cả 21 phiếu cùng lúc. Nó rời Nháp và lại chờ ở bước Kiểm tra bảng lương."),
      reversible: B("Yes, until someone decides: you can withdraw it and it comes back to Draft. After the last yes it is Done, and a correction becomes a retro line.",
                    "Được, cho tới khi có người quyết định: bạn có thể thu hồi và nó quay về Nháp. Sau cái gật đầu cuối cùng nó Hoàn tất, và mọi hiệu chỉnh trở thành một dòng hồi tố."),
      verify: B("That you fixed the INPUT the note names, computed again, and that the payslip now shows the right figure.",
                "Rằng bạn đã sửa đúng DỮ LIỆU ĐẦU VÀO mà ghi chú nêu, đã tính lại, và phiếu lương giờ hiện đúng con số."),
    },
    anomaly: {
      title: B("The run made twice", "Đợt lương bị tạo hai lần"),
      body: B("Beside the real July run sits a second Retail July run, made by mistake. Nobody will submit it — until somebody does, and 48 people are paid twice. It is not a draft to fix; it should not exist. That is what Reject is for.",
             "Bên cạnh đợt lương tháng 7 thật có một đợt tháng 7 thứ hai của Bán lẻ, tạo nhầm. Sẽ không ai gửi nó đi — cho tới khi có người gửi, và 48 người bị trả lương hai lần. Nó không phải một bản nháp cần sửa; nó không nên tồn tại. Nút Từ chối sinh ra cho việc đó."),
    },
    debrief: {
      did: [
        B("Found the run that came back by its flag on the board, and read the note on its card.",
          "Tìm ra đợt bị trả lại nhờ dấu trên bảng, và đọc ghi chú trên thẻ của nó."),
        B("Fixed the input the note named, not the payslip, and computed again.",
          "Sửa đúng dữ liệu đầu vào mà ghi chú nêu, không sửa phiếu lương, rồi tính lại."),
        B("Sent it in again, knowing the route starts from the first step.",
          "Gửi lại, biết rằng lộ trình bắt đầu lại từ bước đầu tiên."),
        B("Rejected the run made by mistake, and saw it move to Rejected pay runs.",
          "Từ chối đợt lương tạo nhầm, và thấy nó chuyển xuống Đợt lương bị từ chối."),
      ],
      checklist: [
        B("The note is answered: the figure it names is right on the payslip now.",
          "Ghi chú đã được giải quyết: con số nó nêu giờ đã đúng trên phiếu lương."),
        B("The fix was made to the input, so the next compute keeps it.",
          "Chỗ sửa nằm ở dữ liệu đầu vào, nên lần tính kế tiếp vẫn giữ nó."),
        B("Nothing else changed that the reviewer did not ask for.",
          "Không có gì khác thay đổi ngoài điều người duyệt yêu cầu."),
        B("Only runs that should not exist are rejected — a run that needs fixing is sent back.",
          "Chỉ từ chối những đợt không nên tồn tại — đợt cần sửa thì được trả lại."),
      ],
    },
  },
  {
    id: "m3", group: "payrun", icon: "flask", mins: 6, full: false,
    screen: "importwizard",
    conf: { key: "import", gain: 15 },
    title: B("Fix a bad import before it becomes salaries", "Sửa một đợt nhập lỗi trước khi nó thành lương"),
    /* THE TWO FLAGGED ROWS ARE A PRODUCT FACT AND THIS SENTENCE HAS TO MATCH
       THEM. Phase 5 changed the first row from an unmatched code to a cell
       that could not be read — the failure the import lesson is actually
       about, and the one the Try flow repairs by typing. This description was
       still naming the old row, which is the fixture and the prose disagreeing
       about the same screen. */
    desc: B("A file with a duplicate row and one cell nobody could read. The score drops. Do you fix it, or commit anyway?",
            "Một tệp có một dòng bị lặp và một ô hệ thống không đọc được. Điểm tin cậy tụt xuống. Bạn sửa, hay cứ ghi nhận?"),
    outlineNote: B("The full version puts you in the wizard with the score falling in front of you. It makes you choose between Match, Retry and Skip for each bad row. Then it shows what each of those choices would have produced on {{payDay}} — including the one where a skipped row turns out to have been a person.",
                   "Bản đầy đủ đặt bạn vào trình hướng dẫn với điểm tin cậy đang tụt ngay trước mắt. Nó buộc bạn chọn giữa Khớp, Thử lại và Bỏ qua cho từng dòng lỗi. Rồi nó cho thấy mỗi lựa chọn đó sẽ tạo ra gì vào {{payDay}} — kể cả trường hợp dòng bị bỏ qua hoá ra là một con người."),
  },
  {
    id: "m4", group: "setup", icon: "shield-check", mins: 7, full: true,
    screen: "statutory",
    conf: { key: "setup", gain: 30 },
    title: B("Apply a BHYT rate change — properly", "Áp dụng thay đổi tỷ lệ BHYT — cho đúng cách"),
    desc: B("A decree raises the health-insurance rate. Declare it the way Payobook actually supports. Date it so the record says what the decree says. Then find out why declaring it is only half the job.",
            "Một nghị định nâng tỷ lệ bảo hiểm y tế. Hãy khai báo theo đúng cách Payobook hỗ trợ. Đặt ngày sao cho bản ghi nói đúng những gì nghị định nói. Rồi hiểu vì sao khai báo mới chỉ là một nửa công việc."),
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
      body: B("The natural next sentence after saving this record is \"so August's payslips will charge 2%\". They will not. Nothing downstream reads this record to compute with. The rate that prices the BHYT line is a parameter on each division's formula configuration, and it is still 1.5%. So the mission ends with the declaration correct and the payroll unchanged. That gap is the point. It is not a bug: it is the reason pay never moves just because a reference table moved. Somebody now has to change twelve configurations, preview them and simulate them. Anybody who assumed otherwise finds out on {{payDay}}.",
             "Câu nói tự nhiên ngay sau khi lưu bản ghi này là \"vậy phiếu lương tháng 8 sẽ tính 2%\". Không phải vậy. Không có gì phía sau đọc bản ghi này để tính. Tỷ lệ tính ra dòng BHYT là một tham số trong cấu hình công thức của từng bộ phận, và nó vẫn đang là 1,5%. Nên nhiệm vụ kết thúc với bản khai báo đã đúng còn bảng lương thì chưa đổi. Chính khoảng cách đó mới là điều cần nhớ. Đây không phải lỗi: đây là lý do tiền lương không bao giờ thay đổi chỉ vì một bảng tham chiếu thay đổi. Giờ phải có người sửa mười hai cấu hình, xem trước và mô phỏng chúng. Ai đã đinh ninh điều ngược lại thì sẽ biết vào {{payDay}}."),
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
    outlineNote: B("The full version adds the component to HOASEN_RETAIL_END. It makes you choose where the component belongs: an earning that feeds GROSS, not a total and not an input. Then you wire it into the gross formula and read the dependency panel to see what moved. It ends where every configuration change should. A simulation against last month's real payslips, and the decision of whether to activate while a run is still open.",
                   "Bản đầy đủ thêm thành phần vào HOASEN_RETAIL_END. Nó buộc bạn chọn thành phần đó thuộc về đâu: một khoản thu nhập cấu thành Tổng thu nhập, không phải một tổng và cũng không phải đầu vào. Rồi bạn nối nó vào công thức tổng thu nhập và đọc bảng phụ thuộc để thấy những gì đã đổi. Nó kết thúc đúng ở nơi mọi thay đổi cấu hình nên kết thúc. Một lần mô phỏng trên phiếu lương thật của tháng trước, và quyết định có kích hoạt hay không khi một đợt lương vẫn đang mở."),
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
    desc: B("The same judgement as the practice run, but on real records in the demo world. Your own division, the open June period, and its approval route all the way to Done.",
            "Vẫn là phán đoán như bài thực hành, nhưng trên bản ghi thật trong môi trường demo. Đúng bộ phận của bạn, kỳ tháng 6 đang mở, và lộ trình phê duyệt đi trọn tới Hoàn tất."),
    consequence: {
      title: B("This one is real", "Nhiệm vụ này là thật"),
      scope: B("Your assigned division's June 2026 run, in the shared Payobook demo company. Real payslip records are created, and other people exploring the demo can see them. No other division and no other period is touched — and no real company's data is anywhere near this.",
               "Đợt lương tháng 6/2026 của bộ phận bạn được gán, trong công ty demo dùng chung của Payobook. Các bản ghi phiếu lương thật sẽ được tạo, và những người khác đang xem demo cũng nhìn thấy chúng. Không bộ phận nào khác và không kỳ nào khác bị ảnh hưởng — và không dữ liệu của công ty thật nào ở gần chỗ này."),
      reversible: B("Partly, and the halves matter. Draft payslips can be deleted and computed again as often as you like. Once submitted, the run moves only by decisions on its route: a step can send it back to Draft, or turn it down, which cancels it. While nobody has decided, you can withdraw it and it comes back to Draft.",
                    "Một phần, và ranh giới rất quan trọng. Phiếu lương nháp có thể xoá và tính lại bao nhiêu lần tuỳ ý. Khi đã gửi, đợt lương chỉ đi tiếp nhờ các quyết định trên lộ trình: một bước có thể trả nó về Nháp, hoặc từ chối, tức là huỷ nó. Khi chưa ai quyết định, bạn có thể thu hồi và nó quay về Nháp."),
      verify: B("That the pay scheme you pick is your own division's End-Month Payroll, and the period is June 2026. The mission checks against your assignment, not against whatever the screen happens to be showing.",
                "Rằng chương trình lương bạn chọn là End-Month Payroll của đúng bộ phận bạn, và kỳ lương là tháng 6/2026. Nhiệm vụ kiểm tra theo phần được gán cho bạn, chứ không theo thứ màn hình đang hiển thị."),
    },
    debrief: {
      did: [
        B("Computed a real month of payroll for a real division, having read what the action would do before you did it.",
          "Tính một tháng lương thật cho một bộ phận thật, sau khi đã đọc xem thao tác đó sẽ gây ra điều gì."),
        B("Opened the run and read its payslips, instead of taking a clean-looking total as evidence.",
          "Mở đợt lương và đọc các phiếu lương, thay vì coi một con số tổng trông sạch sẽ là bằng chứng."),
        B("Submitted it, and watched it stop being yours: from that point the run moves only along its approval route.",
          "Gửi đợt lương đi, và thấy nó không còn là của riêng bạn: từ lúc đó đợt chỉ đi tiếp theo lộ trình phê duyệt."),
        B("Followed it through the inbox to Done — the same journey, and the same waiting, that payroll week is made of.",
          "Theo nó qua hộp phê duyệt tới Hoàn tất — đúng hành trình đó, và đúng những khoảng chờ đó, chính là thứ làm nên một tuần tính lương."),
        B("Did it once where a mistake costs a demo record, which is the last place it is cheap.",
          "Làm một lần ở nơi mà sai sót chỉ tốn một bản ghi demo, và đó là nơi cuối cùng nó còn rẻ."),
      ],
      checklist: [
        B("The pay scheme is yours and the period is the one you meant — read both before computing, not after.",
          "Chương trình lương đúng là của bạn và kỳ lương đúng là kỳ bạn định chạy — hãy đọc cả hai trước khi tính, đừng đọc sau."),
        B("Everything under Need review is understood, and the biggest changes on last month have been opened.",
          "Mọi thứ trong Cần xem xét đều đã được hiểu, và những thay đổi lớn nhất so với tháng trước đã được mở ra xem."),
        B("You can say in one sentence why the total is what it is, before anybody on the route asks you.",
          "Bạn nói được trong một câu vì sao tổng lại là con số đó, trước khi có ai trên lộ trình hỏi bạn."),
        B("You know which step the run is at and who holds it — the card on Runs names them.",
          "Bạn biết đợt lương đang ở bước nào và ai đang giữ — thẻ trên Các đợt lương ghi rõ."),
        B("Nothing was submitted just to make a deadline.",
          "Không có gì được gửi đi chỉ để kịp hạn."),
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
      instruction: B("Open Pay Run › Run", "Mở Đợt lương › Chạy lương"),
      detail: B("It is the first tab of Pay Run on the rail.",
                "Đó là tab đầu tiên của Đợt lương trên thanh bên."),
      hint: B("The steps at the top tell you where you are: Select period, Pay data, Compute, Review exceptions.",
              "Các bước ở trên cho biết bạn đang ở đâu: Chọn kỳ lương, Dữ liệu lương, Tính lương, Soát ngoại lệ."),
    },
    {
      id: "scheme", target: "pw-scheme", decision: true,
      instruction: B("Which pay scheme is this run for?", "Đợt lương này dành cho chương trình lương nào?"),
      detail: B("You are paying Retail for the whole of July.",
                "Bạn đang trả lương cho Bán lẻ cho trọn tháng 7."),
      hint: B("Read the group headings: End of month, Mid-month advance.",
              "Hãy đọc tiêu đề các nhóm: Cuối tháng, Tạm ứng giữa tháng."),
      options: [
        { id: "retail", correct: true, label: B("Hoa Sen Retail — End-Month Payroll", "Hoa Sen Retail — End-Month Payroll (Bán lẻ, cuối tháng)") },
        { id: "mid", label: B("Hoa Sen Retail — Mid-Month Advance", "Hoa Sen Retail — Mid-Month Advance (Bán lẻ, tạm ứng giữa tháng)") },
        { id: "fnb", label: B("Hoa Sen F&B — End-Month Payroll", "Hoa Sen F&B — End-Month Payroll (F&B, cuối tháng)") },
      ],
      recovery: {
        mid: B("Let's rethink that. The mid-month advance pays part of the month early. July is settled by the end-of-month scheme; the advance is not a second view of it.",
               "Hãy nghĩ lại một chút. Tạm ứng giữa tháng là trả trước một phần tháng. Tháng 7 được quyết toán bằng chương trình cuối tháng; khoản tạm ứng không phải một cách nhìn khác của nó."),
        fnb: B("Let's rethink that. F&B pays different people by different rules. And F&B's July run already exists — it was sent back and is waiting to be fixed.",
               "Hãy nghĩ lại một chút. F&B trả lương cho những người khác theo quy tắc khác. Và đợt tháng 7 của F&B đã có — nó bị trả lại và đang chờ được sửa."),
      },
    },
    {
      id: "consequence", target: "pw-summary", consequence: true,
      instruction: B("Read what computing is about to do", "Đọc xem việc tính sắp làm gì"),
      detail: B("This card is the interception. It names the scope, the way back and the thing to verify, and the mission will not move until you have seen all three.",
                "Thẻ này là điểm chặn. Nó nêu rõ phạm vi, lối quay lại và thứ cần kiểm tra, và nhiệm vụ sẽ không đi tiếp cho tới khi bạn đã xem cả ba."),
    },
    {
      id: "compute", target: "pw-pills",
      instruction: B("Compute, then read the three numbers", "Tính, rồi đọc ba con số"),
      detail: B("48 payslips, 48 computed, 2 need review: one person in the file who is not in Payobook yet, and one person Payobook could not pay.",
                "48 phiếu lương, 48 phiếu đã tính, 2 cần xem xét: một người có trong tệp nhưng chưa có trong Payobook, và một người Payobook không trả được."),
      hint: B("Need review counts people Payobook could not pay. It does not count unusual jumps.",
              "Cần xem xét đếm những người Payobook không trả được. Nó không đếm các mức tăng bất thường."),
    },
    {
      id: "inspect", target: "pw-exceptions",
      instruction: B("Read the exception", "Đọc ngoại lệ"),
      detail: B("Hoàng Văn Nam: \"Not employed yet in this period — contract starts 2026-08-01.\" Correct, and nothing to fix. Now look at what is NOT listed: Trần Văn Hùng's overtime is 4,200,000 ₫ against 1,100,000 ₫ in June.",
                "Hoàng Văn Nam: \"Chưa làm việc trong kỳ này — hợp đồng bắt đầu ngày 2026-08-01.\" Đúng, và không có gì để sửa. Giờ hãy nhìn vào điều KHÔNG được liệt kê: tăng ca của Trần Văn Hùng là 4.200.000 ₫ so với 1.100.000 ₫ tháng 6."),
      hint: B("382% is not impossible. It is unverified.",
              "382% không phải là không thể. Nó chỉ là chưa được xác minh."),
    },
    {
      id: "decide", target: "pw-exceptions", decision: true,
      instruction: B("Overtime at 382% of last month. What do you do?", "Tăng ca bằng 382% tháng trước. Bạn xử lý thế nào?"),
      detail: B("Nothing on screen flags it, and the run is due.",
                "Không gì trên màn hình đánh dấu nó, và đợt lương sắp tới hạn."),
      options: [
        { id: "check", correct: true, label: B("Check the timesheet before submitting, and fix the input if it is wrong", "Kiểm tra bảng chấm công trước khi gửi, và sửa dữ liệu đầu vào nếu sai") },
        { id: "accept", label: B("Accept it — nothing flagged it, so it must be fine", "Chấp nhận — không gì đánh dấu nên chắc là ổn") },
        { id: "zero", label: B("Set the overtime to zero on the payslip", "Đặt tăng ca về 0 trên phiếu lương") },
      ],
      recovery: {
        accept: B("Let's rethink that. Payobook flags people it could not pay, not unusual amounts. \"Nothing flagged it\" says nothing about whether 46 hours was really 4.6.",
                  "Hãy nghĩ lại một chút. Payobook đánh dấu những người nó không trả được, không đánh dấu các số tiền bất thường. \"Không gì đánh dấu\" không nói lên việc 46 giờ có thực ra là 4,6 hay không."),
        zero: B("Let's rethink that. That fixes the result and leaves the input untouched, so the next compute brings it straight back. And if the overtime was real, you have just underpaid somebody.",
                "Hãy nghĩ lại một chút. Cách đó sửa kết quả và để nguyên đầu vào, nên lần tính kế tiếp mang nó quay lại ngay. Và nếu tăng ca là thật, bạn vừa trả thiếu cho một người."),
      },
    },
    {
      id: "submit", nav: "payruns", target: "pk-card-actions",
      instruction: B("Submit the run for approval", "Gửi đợt lương để phê duyệt"),
      detail: B("It leaves Draft and waits at the first step of its route: Payroll check, then HR lead review, then Finance approval. Its payslips are frozen while it waits.",
                "Nó rời Nháp và chờ ở bước đầu tiên của lộ trình: Kiểm tra bảng lương, rồi Trưởng nhân sự soát xét, rồi Tài chính phê duyệt. Các phiếu lương bị giữ nguyên trong lúc chờ."),
    },
    {
      id: "undo", nav: "approvals", target: "ai-withdraw", undo: true,
      instruction: B("Now take it back: Withdraw it", "Giờ hãy lấy lại: Thu hồi"),
      detail: B("You sent it in, so you can withdraw it while nobody has finished deciding. The request closes and the run goes back to Draft, payslips editable, nothing cancelled. That is the clean way back — very different from Reject, which cancels the run.",
                "Bạn đã gửi nó, nên bạn thu hồi được khi chưa ai quyết xong. Yêu cầu đóng lại và đợt lương quay về Nháp, các phiếu lương sửa được, không có gì bị huỷ. Đó là lối quay lại gọn gàng — khác hẳn với Từ chối, thứ sẽ huỷ đợt lương."),
      hint: B("Withdraw it is in the request's drawer in Home › Approvals, shown only to the person who sent it in.",
              "Nút Thu hồi nằm trong ngăn chi tiết của yêu cầu ở Trang chủ › Phê duyệt, chỉ hiện với người đã gửi."),
    },
  ],

  m2: [
    {
      id: "open", nav: "payruns", target: "pk-steps",
      instruction: B("Find the run that came back", "Tìm đợt lương bị trả lại"),
      detail: B("Draft says \"1 sent back to be fixed\". A run that is sent back is a draft again, with the reason on its card.",
                "Cột Nháp ghi \"1 bị trả lại để sửa\". Một đợt bị trả lại là bản nháp trở lại, lý do ghi trên thẻ."),
    },
    {
      id: "read", target: "pk-card",
      instruction: B("Read the note", "Đọc ghi chú"),
      detail: B("\"Sent back by Đặng Thu Hà — NV0203: overtime reads 46 hours for the week; the timesheet says 4.6.\"",
                "\"Trả lại bởi Đặng Thu Hà — NV0203: tăng ca ghi 46 giờ trong tuần; bảng chấm công ghi 4,6.\""),
    },
    {
      id: "fix", target: "pk-card", decision: true,
      instruction: B("How do you answer the note?", "Bạn xử lý ghi chú thế nào?"),
      detail: B("The run is a draft again, so its payslips can be changed.",
                "Đợt lương lại là bản nháp, nên các phiếu lương sửa được."),
      options: [
        { id: "input", correct: true, label: B("Correct the overtime input to 4.6 hours, compute again, then submit", "Sửa dữ liệu tăng ca thành 4,6 giờ, tính lại, rồi gửi") },
        { id: "slip", label: B("Type the right amount over the payslip, then submit", "Gõ đè số đúng lên phiếu lương, rồi gửi") },
        { id: "asis", label: B("Submit it again as it is — the reviewer may have misread", "Gửi lại nguyên trạng — có thể người duyệt đọc nhầm") },
      ],
      recovery: {
        slip: B("Let's rethink that. A typed-over payslip disagrees with the data behind it, and the next compute puts the 46 back. Fix the input.",
                "Hãy nghĩ lại một chút. Phiếu lương bị gõ đè sẽ lệch với dữ liệu phía sau, và lần tính kế tiếp đưa con số 46 quay lại. Hãy sửa đầu vào."),
        asis: B("Let's rethink that. The note names the payslip and the timesheet figure. Sending it back unchanged costs the reviewer a second read and comes back again.",
                "Hãy nghĩ lại một chút. Ghi chú nêu rõ phiếu nào và con số trong bảng chấm công. Gửi lại nguyên trạng khiến người duyệt phải đọc lần hai và nó sẽ lại bị trả về."),
      },
    },
    {
      id: "check", nav: "payslips", target: "ps-breakdown",
      instruction: B("Check the payslip after computing again", "Kiểm tra phiếu lương sau khi tính lại"),
      detail: B("Read the overtime line and the net under it. The fix lives in the input, so every later compute keeps it.",
                "Đọc dòng tăng ca và số thực nhận bên dưới. Chỗ sửa nằm ở đầu vào, nên mọi lần tính sau đều giữ nó."),
    },
    {
      id: "consequence", nav: "payruns", target: "pk-card-actions", consequence: true,
      instruction: B("Read what sending it in again does", "Đọc xem việc gửi lại sẽ làm gì"),
      detail: B("The route starts from its first step. Everything the reviewers saw last time is in the history; this is a fresh attempt.",
                "Lộ trình bắt đầu lại từ bước đầu tiên. Mọi thứ người duyệt đã thấy lần trước nằm trong lịch sử; đây là một lượt gửi mới."),
    },
    {
      id: "resubmit", target: "pk-card-actions",
      instruction: B("Submit it for approval again", "Gửi phê duyệt lại"),
      detail: B("It moves to Waiting for approval, at Payroll check.",
                "Nó chuyển sang Chờ phê duyệt, ở bước Kiểm tra bảng lương."),
    },
    {
      id: "undo", target: "pk-rejected", undo: true,
      instruction: B("Clear away the run made by mistake: Reject it", "Dọn đợt lương tạo nhầm: Từ chối nó"),
      detail: B("\"Retail — July 2026 (made twice)\" should never have existed. Reject asks once — Keep it, or Reject run — then cancels it and every payslip in it, and it moves to the folded Rejected pay runs list. Use Reject for a run that should not exist, never for one that only needs fixing.",
                "\"Bán lẻ — Tháng 7/2026 (tạo trùng)\" lẽ ra không nên tồn tại. Từ chối hỏi lại một lần — Giữ lại, hoặc Từ chối đợt lương — rồi huỷ nó cùng mọi phiếu lương trong đó, và nó chuyển xuống danh sách thu gọn Đợt lương bị từ chối. Hãy dùng Từ chối cho đợt không nên tồn tại, không bao giờ cho đợt chỉ cần sửa."),
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
        editlive: B("Let's rethink that. A policy has no version history, so editing it does not create a before and an after. The old rate is simply gone, and nothing is left to show which rates July was computed under. Payobook's answer to a rate change is a second record, not a second version.",
                    "Hãy nghĩ lại một chút. Chính sách không có lịch sử phiên bản, nên sửa nó không tạo ra bản trước và bản sau. Tỷ lệ cũ đơn giản là mất, và không còn gì chứng minh tháng 7 đã được tính theo tỷ lệ nào. Câu trả lời của Payobook cho việc đổi tỷ lệ là một bản ghi thứ hai, không phải một phiên bản thứ hai."),
        samecode: B("Let's rethink that. The code is unique per company, so this one is refused outright. That is fortunate: a shared code is exactly how two policies stop being telling apart in a report. Give the new record its own code and the pair reads as a history.",
                    "Hãy nghĩ lại một chút. Mã là duy nhất trong mỗi công ty, nên cách này bị từ chối ngay. Đó là điều may: trùng mã chính là cách hai chính sách trở nên không phân biệt được trong báo cáo. Cho bản ghi mới một mã riêng thì cặp bản ghi đọc ra như một lịch sử."),
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
        onefive: B("Let's rethink that. 1.5% is the rate that is in force today. Typing it into the new record creates a policy that changes nothing. The first anybody knows about it is when August's deductions come out identical to July's.",
                   "Hãy nghĩ lại một chút. 1,5% là tỷ lệ đang có hiệu lực hôm nay. Gõ nó vào bản ghi mới sẽ tạo ra một chính sách không thay đổi gì. Người ta chỉ biết khi khấu trừ tháng 8 ra y hệt tháng 7."),
        three: B("Let's rethink that. 3.0% is the EMPLOYER's BHYT share, sitting one column to the right. Putting it in the employee column doubles what every employee pays, and leaves the company paying the same. That mistake is invisible on this screen and very visible on a payslip.",
                 "Hãy nghĩ lại một chút. 3,0% là phần BHYT của DOANH NGHIỆP, nằm ngay cột bên phải. Đặt nó vào cột người lao động sẽ làm mọi nhân viên đóng gấp đôi, còn công ty vẫn đóng như cũ. Lỗi đó không nhìn thấy trên màn hình này nhưng rất dễ thấy trên phiếu lương."),
      },
    },
    {
      id: "effective", target: "st-effective", decision: true,
      instruction: B("Choose the effective date", "Chọn ngày hiệu lực"),
      detail: B("It is 20 July and the decree applies from 1 August. This field is the company's record of when the change legally started. Auditors and the statutory reports read it. Nothing that computes pay reads it at all.",
                "Hôm nay là 20/7 và nghị định áp dụng từ 1/8. Ô này là ghi nhận của doanh nghiệp về thời điểm thay đổi bắt đầu có hiệu lực pháp lý. Kiểm toán và các báo cáo bắt buộc đọc nó. Còn những thứ tính ra tiền lương thì không đọc nó."),
      hint: B("Whatever date you type, this screen starts showing the new rates the moment you save. So the date is not a switch — it is a statement about the law, and it has to be true.",
              "Dù bạn gõ ngày nào, màn hình này cũng bắt đầu hiển thị tỷ lệ mới ngay khi bạn lưu. Nên ngày hiệu lực không phải một cái công tắc — nó là một tuyên bố về pháp luật, và nó phải đúng."),
      options: [
        { id: "aug", correct: true, label: B("01/08/2026 — the first day the decree applies", "01/08/2026 — ngày đầu tiên nghị định áp dụng") },
        { id: "today", label: B("Today, 20/07/2026, so it is not forgotten", "Hôm nay, 20/07/2026, cho khỏi quên") },
        { id: "jan", label: B("01/01/2026, to keep the year consistent", "01/01/2026, cho nhất quán cả năm") },
      ],
      recovery: {
        today: B("Let's rethink that. The decree says 1 August, so a record dated 20 July declares a legal start the company cannot evidence. The statutory reports built from it would say July ran at the new rate, when it did not. Dating it correctly costs nothing. This screen shows the new rates from the moment you save, either way. So tell the people reviewing July — do not bend the date.",
                 "Hãy nghĩ lại một chút. Nghị định nói ngày 1/8, nên một bản ghi đề ngày 20/7 là khai một mốc pháp lý mà doanh nghiệp không chứng minh được. Các báo cáo bắt buộc lập từ đó sẽ nói tháng 7 chạy theo tỷ lệ mới, trong khi không phải vậy. Ghi đúng ngày chẳng tốn gì. Đằng nào màn hình này cũng hiển thị tỷ lệ mới ngay khi bạn lưu. Vậy hãy báo cho những người đang soát xét tháng 7 — đừng bẻ cong cái ngày."),
        jan: B("Let's rethink that. Backdating to January declares that the company has been contributing at the new rate all year. Four of those months were already paid, reported and filed at the old rate. That is not a tidier record, it is a false one. It is also the kind an inspection finds by comparing the declaration with the returns.",
               "Hãy nghĩ lại một chút. Lùi về tháng 1 là khai rằng doanh nghiệp đã đóng theo tỷ lệ mới suốt cả năm. Bốn tháng trong đó đã chi, đã báo cáo và đã nộp theo tỷ lệ cũ. Đó không phải một bản ghi gọn gàng hơn, mà là một bản ghi sai sự thật. Đó cũng đúng là loại mà đoàn kiểm tra phát hiện khi đối chiếu bản khai với các tờ khai đã nộp."),
      },
    },
    {
      id: "reconcile", target: "rep-slipline",
      instruction: B("Check what the payslip is still charging", "Kiểm tra xem phiếu lương vẫn đang tính bao nhiêu"),
      detail: B("The declaration now says 2.0%. Mai's BHYT line still says −180,000 ₫, which is 1.5% of her insurance base. That line is priced by a parameter on Retail's configuration, not by the record you just wrote. This is the reconciliation the Statutory screen exists for, and right now it fails.",
                "Bản khai báo giờ nói 2,0%. Dòng BHYT của Mai vẫn là −180.000 ₫, tức 1,5% trên mức lương đóng bảo hiểm. Dòng đó được tính bằng một tham số trong cấu hình của Bán lẻ, không phải bằng bản ghi bạn vừa tạo. Đây chính là phép đối chiếu mà màn hình Bảo hiểm & Thuế sinh ra để làm, và ngay lúc này nó đang lệch."),
      hint: B("If the configuration is changed too, her BHYT becomes 240,000 ₫ and her net falls 57,000 — not 60,000, because insurance comes off before the tax relief. But none of that happens from this screen.",
              "Nếu cấu hình cũng được sửa, BHYT của cô ấy thành 240.000 ₫ và thực nhận giảm 57.000 — không phải 60.000, vì bảo hiểm được trừ trước các khoản giảm trừ thuế. Nhưng không điều nào trong số đó xảy ra từ màn hình này."),
    },
    {
      id: "consequence", target: "st-new", consequence: true,
      instruction: B("Read what saving this record does", "Đọc xem việc lưu bản ghi này gây ra điều gì"),
      detail: B("Read the scope line twice. It is company-wide, and it reprices nothing. Those are the two facts people find hardest to hold together here, and they are why the next step goes looking at a payslip that has not moved.",
                "Hãy đọc dòng phạm vi hai lần. Nó có hiệu lực trên toàn công ty, và nó không tính lại khoản nào. Đó là hai điều người ta khó giữ cùng lúc nhất ở màn hình này, và cũng là lý do bước kế tiếp đi xem một phiếu lương chưa hề thay đổi."),
    },
    {
      id: "commit", target: "st-roster",
      instruction: B("Save the new policy and read the roster", "Lưu chính sách mới và đọc lại danh sách"),
      detail: B("The August record is now the one the rates table shows. It has the latest effective date among the active policies, and the table does not compare that date to today. The 2026 record stays on the list as evidence of what was declared before it.",
                "Bản ghi tháng 8 giờ là bản mà bảng tỷ lệ hiển thị. Nó có ngày hiệu lực mới nhất trong số các chính sách đang bật, và bảng này không so ngày đó với hôm nay. Bản ghi 2026 vẫn ở lại danh sách làm bằng chứng cho mức đã khai báo trước đó."),
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
      detail: B("Everything from here happens in Payobook itself. The practice missions ran on made-up data with no server behind it. This one creates real payslip records in the shared demo company, on the division assigned to your account. It is the safest real payroll you will ever run, and it is still a real one.",
                "Từ đây trở đi mọi thứ diễn ra ngay trong Payobook. Các nhiệm vụ thực hành chạy trên dữ liệu giả lập không có máy chủ phía sau. Nhiệm vụ này tạo ra phiếu lương thật trong công ty demo dùng chung, trên bộ phận được gán cho tài khoản của bạn. Đây là kỳ lương thật an toàn nhất bạn từng chạy, và nó vẫn là một kỳ lương thật."),
      hint: B("The run this mission watches is the one YOU create. Your division already has a June run sitting there from the demo build, and the mission ignores it on purpose. Otherwise step one would tick itself green for work you had not done.",
              "Đợt lương mà nhiệm vụ này theo dõi là đợt do CHÍNH BẠN tạo. Bộ phận của bạn đã có sẵn một đợt tháng 6 từ lúc dựng bản demo, và nhiệm vụ cố ý bỏ qua đợt đó. Nếu không thì bước đầu tiên sẽ tự xanh cho phần việc bạn chưa hề làm."),
    },
    {
      id: "open", nav: "runpayroll", ack: true,
      instruction: B("Open Pay Run › Run", "Mở Đợt lương › Chạy lương"),
      detail: B("Under \"Pay run for\", pick your own division's End-Month Payroll scheme. The period is June 2026, the one month the demo world leaves open. Read both before you go on.",
                "Trong mục \"Đợt lương cho\", hãy chọn chương trình End-Month Payroll của đúng bộ phận bạn. Kỳ lương là tháng 6/2026, tháng duy nhất mà môi trường demo để mở. Hãy đọc cả hai trước khi đi tiếp."),
      hint: B("The other divisions' schemes are on the list too. You are welcome to look; the mission checks the one that is yours.",
              "Chương trình lương của các bộ phận khác cũng có trong danh sách. Bạn cứ xem thoải mái; nhiệm vụ chỉ kiểm tra đúng bộ phận của bạn."),
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
      detail: B("Press Compute payslips. When the payslips exist, this step ticks itself — the mission is watching the records, not your clicks.",
                "Hãy bấm Tính phiếu lương. Khi các phiếu lương đã có, bước này tự đánh dấu hoàn thành — nhiệm vụ đang theo dõi bản ghi, không theo dõi cú bấm của bạn."),
      hint: B("Nothing is paid and nobody is notified. Drafts can be deleted and recomputed as often as you want.",
              "Chưa có gì được chi và chưa ai được thông báo. Bản nháp có thể xoá và tính lại bao nhiêu lần tuỳ ý."),
    },
    {
      id: "review", nav: "payslips", ack: true,
      instruction: B("Open the payslips and read what is flagged", "Mở phiếu lương và đọc những gì bị gắn cờ"),
      detail: B("In Pay Run › Payslips, pick your run. Need review there counts payslips at zero or below. Anything else unusual is yours to find: sample the ones with the most overtime, and a few ordinary ones.",
                "Ở Đợt lương › Phiếu lương, hãy chọn đợt của bạn. Cần xem xét ở đó đếm những phiếu có thực nhận bằng không hoặc âm — mọi điều bất thường khác là bạn phải tự tìm, nên hãy lấy mẫu những phiếu nhiều tăng ca nhất và vài phiếu bình thường."),
      hint: B("Open the breakdown on one slip and follow it from base to net. If you can say where each line came from, you are ready to submit.",
              "Hãy mở bảng chi tiết của một phiếu và đi từ lương cơ bản tới thực nhận. Nếu bạn nói được mỗi dòng đến từ đâu thì bạn đã sẵn sàng để trình đợt lương lên duyệt."),
    },
    {
      id: "submit", nav: "payruns", check: "june_run_submitted",
      instruction: B("Submit the run for approval", "Trình đợt lương lên phê duyệt"),
      detail: B("Press Submit for approval on its card in Pay Run › Runs. After it, the run moves only by decisions on its route. A step that sends it back returns it to Draft; one that turns it down cancels it.",
                "Bấm Gửi để phê duyệt trên thẻ của nó ở Đợt lương › Các đợt lương. Sau bước này, đợt lương chỉ đi tiếp nhờ các quyết định trên lộ trình. Một bước trả lại sẽ đưa nó về Nháp; một bước từ chối sẽ huỷ nó."),
      hint: B("Submitting is you saying the flags have been answered. If any of them have not, go back — the run will still be there.",
              "Trình lên phê duyệt là bạn tuyên bố rằng các cờ cảnh báo đã được trả lời. Nếu còn cờ nào chưa, hãy quay lại — đợt lương vẫn nằm đó."),
    },
    {
      id: "officer", check: "june_run_officer_done",
      instruction: B("It is with the first person on its route", "Nó đang ở chỗ người đầu tiên trên lộ trình"),
      detail: B("Open Home › Approvals. If a step names you, it is on My turn: open it, read the facts, and approve. On a real company these are different people, and the waiting between them is most of what payroll week is.",
                "Mở Trang chủ › Phê duyệt. Nếu một bước ghi tên bạn, nó nằm ở Đến lượt tôi: mở ra, đọc các dữ kiện, và phê duyệt. Ở một công ty thật, đây là những người khác nhau, và phần lớn một tuần tính lương chính là những khoảng chờ giữa họ."),
      hint: B("The card on Pay Run › Runs says whose step it is at. That is the answer to \"who do I chase\".",
              "Thẻ trên Đợt lương › Các đợt lương ghi rõ nó đang ở bước của ai. Đó chính là câu trả lời cho \"tôi phải hỏi ai\"."),
    },
    {
      id: "done", check: "june_run_done",
      instruction: B("Take it through the rest of its route to Done", "Đưa nó qua phần còn lại của lộ trình tới Hoàn tất"),
      detail: B("Each step's yes moves it on; the last one makes it Done. Only a Done run offers Pay & Deliver, the journals and the payments — those buttons appear exactly when every step has said yes.",
                "Mỗi cái gật đầu ở một bước đưa nó đi tiếp; cái cuối cùng biến nó thành Hoàn tất. Chỉ đợt Hoàn tất mới có Chi trả & gửi phiếu, bút toán và thanh toán — các nút đó xuất hiện đúng lúc mọi bước đã đồng ý."),
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
    places: ["pb_pay_hub:run"],
    blurb: B("Start one month's pay run: pick the pay scheme, add the month's pay data, compute, and read what needs a look.",
             "Bắt đầu đợt lương của một tháng: chọn chương trình lương, thêm dữ liệu lương, tính, và đọc những gì cần xem lại."),
    next: B("Pick the pay scheme under \"Pay run for\" and check the month. If the scheme reads a spreadsheet, load the file and choose Update Payobook or This run only. Computing makes drafts only — nothing is paid, sent or approved.",
            "Chọn chương trình lương trong mục \"Đợt lương cho\" và kiểm tra tháng. Nếu chương trình đọc một bảng tính, hãy tải tệp và chọn Cập nhật Payobook hoặc Chỉ đợt này. Tính chỉ tạo bản nháp — chưa có gì được chi, gửi hay phê duyệt."),
    chips: ["howrun", "affectrun", "needreview", "checkfinal", "practice"],
  },

  payruns: {
    places: ["pb_pay_hub:runs"],
    blurb: B("Every pay run on one board: Draft, Waiting for approval and Done, and who each waiting run is with.",
             "Mọi đợt lương trên một bảng: Nháp, Chờ phê duyệt và Hoàn tất, và mỗi đợt đang chờ ở chỗ ai."),
    /* LIVE SITE 1 of 2. On the demo world this names the prospect's OWN
       division and the state their OWN June run is actually in. */
    next: B("Your division on this demo is {{live:division_name}}, and its June run is {{live:june_run_state}} right now. Look for the flags on the steps first: a run sent back to be fixed, or one waiting on you.",
            "Bộ phận của bạn trên bản demo này là {{live:division_name}}, và đợt lương tháng 6 của bộ phận đó hiện đang ở trạng thái {{live:june_run_state}}. Hãy xem các dấu trên các bước trước: một đợt bị trả lại để sửa, hoặc một đợt đang chờ bạn."),
    liveFallback: B("Look for the flags on the steps first: a run sent back to be fixed, or one waiting on you. A waiting run's card says whose step it is at.",
                    "Hãy xem các dấu trên các bước trước: một đợt bị trả lại để sửa, hoặc một đợt đang chờ bạn. Thẻ của một đợt đang chờ ghi rõ nó đang ở bước của ai."),
    chips: ["whoapproves", "stuckwaiting", "reject", "getpaid", "whatnext"],
  },

  payslips: {
    places: ["pb_pay_hub:payslips"],
    blurb: B("Every payslip in one run, and one opened beside the list with its salary breakdown.",
             "Mọi phiếu lương trong một đợt, và một phiếu được mở bên cạnh danh sách kèm chi tiết lương."),
    next: B("Pick the run at the top. Need review here means take-home pay at zero or below — beyond that, open the payslips with the biggest changes and sample a few ordinary ones.",
            "Chọn đợt lương ở trên cùng. Cần xem xét ở đây nghĩa là thực nhận bằng không hoặc âm — ngoài ra, hãy mở những phiếu thay đổi nhiều nhất và lấy mẫu vài phiếu bình thường."),
    chips: ["whydiff", "needreview", "bhxh", "howmanyslips", "fixerror"],
  },

  import: {
    places: ["pb_pay_hub:import"],
    blurb: B("Where this period's pay data comes in from a file or a connected system, before any of it becomes a payslip.",
             "Nơi dữ liệu lương của kỳ này đi vào từ tệp hoặc từ hệ thống đã kết nối, trước khi bất kỳ phần nào trở thành phiếu lương."),
    next: B("Press Load pay data for the guided flow. It matches rows to people and lets you fix them before anything is written. A batch that stops before commit has changed nothing.",
            "Bấm Tải dữ liệu lương để dùng luồng có hướng dẫn. Nó khớp các dòng với từng người và cho bạn sửa trước khi ghi bất cứ gì. Một đợt dừng trước bước ghi vào hệ thống thì chưa thay đổi gì cả."),
    chips: ["whatpage", "confidence", "thisrunonly", "fixerror"],
  },

  importwizard: {
    blurb: B("The four-step import: Source & file, Review & match, Validate, Commit.",
             "Bốn bước nhập liệu: Nguồn & tệp, Soát & khớp, Kiểm tra, Ghi vào hệ thống."),
    next: B("Resolve every row under Need attention before you commit. Commit import is the first control here that writes anything; everything before it is a preview.",
            "Hãy xử lý mọi dòng trong Cần xử lý trước khi ghi. Ghi vào hệ thống là nút đầu tiên ở đây thực sự ghi dữ liệu; mọi thứ trước đó chỉ là xem trước."),
    chips: ["confidence", "fixerror", "whatnext", "practice"],
  },

  fullfinal: {
    places: ["pb_pay_hub:settle/fullfinal", "pb_pay_hub:settle"],
    blurb: B("Pay Run › Settle: every final settlement, its net payable, and where it is on the way to approval.",
             "Đợt lương › Quyết toán: mọi khoản quyết toán thôi việc, số tiền phải trả, và mỗi khoản đang ở đâu trên đường phê duyệt."),
    next: B("Check that everyone settled here is out of the normal monthly run for the same month. Someone in both is paid twice.",
            "Kiểm tra rằng mọi người được quyết toán ở đây đã ra khỏi đợt lương tháng thông thường của cùng tháng. Người nằm ở cả hai sẽ được trả hai lần."),
    chips: ["whatpage", "prorata", "whatnext"],
  },
  adjust: {
    places: ["pb_pay_hub:adjust"],
    blurb: B("Pay Run › Adjust: back pay (Retro) and part-month amounts (Proration), filled in when pay data is loaded.",
             "Đợt lương › Điều chỉnh: khoản truy lĩnh (Hồi tố) và các khoản theo phần tháng (Phân bổ theo tỷ lệ), được điền khi tải dữ liệu lương."),
    next: B("Open a row's drawer before answering anyone. The days and the months it covers are there, not on the row.",
            "Hãy mở ngăn chi tiết của một dòng trước khi trả lời ai. Số ngày và tháng mà nó bao gồm nằm ở đó, không nằm trên dòng."),
    chips: ["retroq", "prorata", "whatpage"],
  },
  proration: {
    places: ["pb_pay_hub:adjust/proration"],
    blurb: B("Every part-month amount: old, new and prorated per person. The drawer holds the basis and the days on each side of a change.",
             "Mọi khoản theo phần tháng: cũ, mới và đã phân bổ của từng người. Ngăn chi tiết có cách tính và số ngày ở mỗi phía của một thay đổi."),
    next: B("Read the days in the drawer before the money. If the days are right and the amount still looks wrong, the problem is further back: the contract, or the pay data.",
            "Hãy đọc số ngày trong ngăn chi tiết trước khi đọc tiền. Nếu số ngày đúng mà số tiền vẫn có vẻ sai thì vấn đề nằm ở phía trước: hợp đồng, hoặc dữ liệu lương."),
    chips: ["prorata", "whydiff", "whatpage"],
  },
  retro: {
    places: ["pb_pay_hub:adjust/retro"],
    blurb: B("Back pay: a pay change dated before this month, compared with what was already paid, with the difference added to this month.",
             "Khoản truy lĩnh: một thay đổi lương có hiệu lực trước tháng này, đem so với số đã trả, và phần chênh được cộng vào tháng này."),
    next: B("Check the Retro period on each line. It names the month being made good, which is what keeps that month closed.",
            "Kiểm tra Retro period trên từng dòng. Nó ghi tháng đang được bù, và chính điều đó giữ cho tháng ấy luôn đóng."),
    chips: ["retroq", "fixerror", "whatpage"],
  },
  afterrun: {
    places: ["pb_pay_hub:results", "pb_pay_hub:deliver", "pb_pay_hub:paycal", "pb_pay_hub:awards"],
    blurb: B("After the run: Results reads it as one grid, Deliver sends the bank file and payslips, Calendar keeps the month's dates, Awards adds one-off money.",
             "Sau đợt lương: Kết quả đọc nó trong một bảng, Chi trả gửi tệp ngân hàng và phiếu lương, Lịch lương giữ các mốc ngày của tháng, Thưởng thêm các khoản một lần."),
    next: B("On an approved run, prepare the bank file first. The payment release waits for it, and payslips are best sent once the money is released.",
            "Trên một đợt đã duyệt, hãy lập tệp ngân hàng trước. Lệnh chuyển tiền chờ tệp đó, và phiếu lương nên gửi khi tiền đã được chuyển."),
    chips: ["getpaid", "whatpage", "whatnext"],
  },

  /* -- Setup ------------------------------------------------------------- */
  formula: {
    blurb: B("Formula Studio: one pay scheme's rulebook, out in the open. Every payslip line is a named component with a formula you can read.",
             "Xưởng công thức: bộ quy tắc của một chương trình lương, bày ra rõ ràng. Mỗi dòng phiếu lương là một thành phần có tên, kèm công thức bạn đọc được."),
    next: B("Read the component list, then open the one behind the number you are asking about. Before activating a change, run Simulate from Tools → Analyze against last period.",
            "Hãy đọc danh sách thành phần, rồi mở đúng thành phần đứng sau con số bạn đang thắc mắc. Trước khi kích hoạt một thay đổi, hãy chạy Mô phỏng từ Công cụ → Phân tích trên kỳ trước."),
    chips: ["whysetup", "editlive", "whichconfig", "configvsstructure", "practice"],
  },

  structures: {
    blurb: B("Salary structures: sets of salary rules. A contract that names one is computed by it; a contract with none is paid by a pay scheme.",
             "Cấu trúc lương: các bộ quy tắc lương. Hợp đồng ghi một cấu trúc thì được tính theo nó; hợp đồng không có cấu trúc thì được trả theo chương trình lương."),
    next: B("If a payslip ignores the pay scheme, open the person's contract and look at Salary structure. New pay logic belongs in a pay scheme, not here.",
            "Nếu một phiếu lương bỏ qua chương trình lương, hãy mở hợp đồng của người đó và xem Salary structure. Logic lương mới thuộc về chương trình lương, không phải ở đây."),
    chips: ["configvsstructure", "whysetup", "whatpage"],
  },
  statutory: {
    blurb: B("The company's active insurance policy and tax table. BHXH, BHYT and BHTN rates and ceilings, plus the thuế TNCN bands.",
             "Chính sách bảo hiểm và biểu thuế đang hiệu lực của công ty. Tỷ lệ và trần đóng BHXH, BHYT, BHTN, cùng các bậc thuế TNCN."),
    next: B("Check that the rates on display are the ones in force. The table shows the active policy with the latest effective date. To change one, create a new policy record dated from the day the change applies. Never edit the one in force.",
            "Hãy kiểm tra các tỷ lệ đang hiển thị có đúng là tỷ lệ hiện hành không. Bảng này hiển thị chính sách đang bật có ngày hiệu lực mới nhất. Muốn đổi một tỷ lệ, hãy tạo bản ghi chính sách mới, đề ngày đúng bằng ngày thay đổi có hiệu lực. Đừng bao giờ sửa bản đang chạy."),
    chips: ["changerate", "whichpolicy", "ceiling", "pitcalc", "bhxh"],
  },
  integrations: {
    blurb: B("The systems pay data arrives from: each connection's last sync, feeds and mappings, and its own screen with the Automatic fetch schedule.",
             "Các hệ thống mà dữ liệu lương đến từ đó: lần đồng bộ gần nhất, nguồn cấp và ánh xạ của từng kết nối, và màn hình riêng có lịch Automatic fetch."),
    next: B("Read the last sync on every row, not the badge. A stale feed or a climbing staged count is a connection that stopped; open it and check Automatic fetch.",
            "Hãy đọc lần đồng bộ gần nhất trên từng dòng, không phải nhãn. Nguồn cấp cũ hoặc số bản ghi đang chờ tăng dần là một kết nối đã ngừng; hãy mở nó và xem Automatic fetch."),
    chips: ["syncbroken", "whysetup", "whatnext"],
  },

  /* -- Overview, People, Insights, Compliance (Phase C1) ------------------ */
  dashboard: {
    places: ["pb_home_hub:pulse"],
    blurb: B("Home › Pulse: the latest pay run, which month the figures are for, four numbers that describe the company, and the way into the rest.",
             "Trang chủ › Tổng quan: đợt lương mới nhất, số liệu thuộc tháng nào, bốn con số mô tả công ty, và lối vào phần còn lại."),
    next: B("Read the line under your name first — it names the latest run and how much is waiting. Then open Approvals if anything is yours, or go to the page the work is on.",
            "Hãy đọc dòng ngay dưới tên bạn trước — nó cho biết đợt lương mới nhất và bao nhiêu đang chờ. Rồi mở Phê duyệt nếu có việc của bạn, hoặc đi tới trang chứa phần việc đó."),
    chips: ["howrun", "whatpage", "wherelives", "whatnext", "practice"],
  },

  approvals: {
    places: ["pb_home_hub:approvals"],
    blurb: B("The one inbox: everything waiting for a decision, pay runs included, each with the route it travels.",
             "Hộp phê duyệt duy nhất: mọi thứ đang chờ quyết định, kể cả đợt lương, mỗi yêu cầu kèm lộ trình nó đi qua."),
    next: B("Open My turn. For a pay run, read the facts it was sent in with and open a few payslips before you decide. To have something fixed, send it back with a note; turning it down cancels the run.",
            "Hãy mở Đến lượt tôi. Với một đợt lương, hãy đọc các dữ kiện nó mang theo lúc gửi và mở vài phiếu lương trước khi quyết định. Muốn được sửa, hãy trả lại kèm ghi chú; từ chối sẽ huỷ đợt lương."),
    chips: ["approve", "sentbackvsturneddown", "rejectright", "stuckwaiting", "howmanyslips"],
  },

  employees: {
    places: ["pb_people_hub:employees"],
    blurb: B("People › Employees: everyone the company employs, whether each can be paid, and a Contract button on every row.",
             "Con người › Nhân viên: mọi người công ty đang thuê, từng người có trả lương được không, và nút Hợp đồng trên mỗi dòng."),
    next: B("Press No contract, then read the warnings. A row is ready only with a running contract and bank details; anyone else computes and is not paid.",
            "Hãy bấm Không có hợp đồng, rồi đọc các cảnh báo. Một dòng chỉ sẵn sàng khi có hợp đồng đang hiệu lực và thông tin ngân hàng; người khác vẫn được tính mà không nhận được tiền."),
    chips: ["addperson", "payrollready", "whopays", "whosees", "whatnext"],
  },
  contracts: {
    /* LEARN REFRESH step 1. Contracts is a door INSIDE People › Employees now
       (commit c9e5f2ee4): a board of its own behind a button, and a drawer
       per person. `detail:contract` is the drawer, wherever it opens; the
       board is still its own action and grounds by its tag. `models` claims
       the native contract form, which the sidebar leaves share with
       Employees and so could never ground on either. */
    places: ["detail:contract"],
    models: ["hr.contract"],
    open: "pb_people_hub.action_pb_people_contracts",
    blurb: B("A contract: its terms, the components it carries and where each comes from, and every change made to it.",
             "Một hợp đồng: các điều khoản, các thành phần nó mang và mỗi thành phần đến từ đâu, cùng mọi thay đổi đã làm trên nó."),
    next: B("Read Components before answering a pay question: each amount says where it comes from. A draft contract pays nothing; a contract ending mid-month pays part of it.",
            "Hãy đọc Components trước khi trả lời một câu hỏi về lương: mỗi khoản ghi rõ nó đến từ đâu. Hợp đồng nháp không trả gì; hợp đồng kết thúc giữa tháng chỉ trả một phần tháng."),
    chips: ["expirysoon", "whopays", "prorata", "whatpage"],
  },
  insights: {
    places: ["pb_insights_hub:pulse"],
    blurb: B("Insights › Pulse: the newest run's net payroll with its state, the cost story, the department leaderboard, the statutory split and the workforce pulse.",
             "Phân tích › Tổng quan: lương thực chi của đợt mới nhất kèm trạng thái, diễn biến chi phí, xếp hạng phòng ban, cơ cấu khoản đóng bắt buộc và nhịp nhân sự."),
    next: B("Read the state chip beside the headline before you quote it. The headline is the latest run, whatever state it is in, while the leaderboard below waits for a run that is done. Then compare cost per head rather than one total against another. Headcount moves between months, and one extra employee explains most of what looks like a rise.",
            "Hãy đọc chip trạng thái bên cạnh con số nổi bật trước khi trích nó. Phần đầu lấy đợt gần nhất bất kể trạng thái, còn bảng xếp hạng bên dưới thì chờ một đợt đã hoàn tất. Rồi hãy so chi phí bình quân đầu người thay vì đem tổng so với tổng. Sĩ số thay đổi giữa các tháng, và thêm một nhân viên là đủ giải thích phần lớn cái vẻ \"tăng\" đó."),
    chips: ["whichtool", "variance", "whatpage", "whatnext"],
  },
  explorer: {
    places: ["pb_insights_hub:explorer"],
    blurb: B("A question builder over payroll figures that always reconcile to the payslip lines. One measure, one breakdown, and the filters that scope them. It also draws a waterfall that explains a movement.",
             "Công cụ đặt câu hỏi trên các số liệu lương luôn khớp với từng dòng phiếu lương. Một chỉ tiêu, một chiều tách, và các bộ lọc giới hạn phạm vi. Nó còn vẽ một biểu đồ phân rã để giải thích biến động."),
    next: B("Choose the measure before the filters. Most wrong answers here are the right filter on the wrong measure. Quote the tags with the number too: the same measure with one tag removed is a different figure, and it looks identical in an email.",
            "Hãy chọn chỉ tiêu trước rồi mới tới bộ lọc. Phần lớn câu trả lời sai ở đây là lọc đúng nhưng chọn nhầm chỉ tiêu. Khi trích con số thì trích kèm cả các thẻ lọc: cùng chỉ tiêu đó, gỡ một thẻ đi là một con số khác, mà trong email thì trông y hệt."),
    chips: ["whichtool", "whatpage", "whatnext"],
  },
  workforcean: {
    places: ["pb_insights_hub:workforce"],
    blurb: B("The same months read as people. Headcount paid, joiners and leavers, attendance exceptions and cost per head.",
             "Vẫn những tháng đó nhưng đọc theo con người. Số người được trả lương, người vào và người nghỉ, ngoại lệ chấm công và chi phí bình quân đầu người."),
    next: B("Read the headcount line as people PAID, not people employed. A step in it is a joiner wave, or a leaver wave. Or it is a run that left somebody out, which is the one worth checking.",
            "Hãy đọc đường sĩ số là số người ĐƯỢC TRẢ LƯƠNG, không phải số người đang làm việc. Một bậc nhảy trên đó là một nhóm người mới vào, hoặc một nhóm người nghỉ việc. Hoặc đó là một đợt lương đã bỏ sót ai đó, và đó mới là điều đáng kiểm tra."),
    // `prorata` was the third chip here and was filler: it is scoped to the
    // payslip-arithmetic screens, so it resolved to nothing at all on this
    // one — a suggested question that answers with a miss. `whatnext` renders
    // this screen's own next_step, which is the genuinely useful thing to read
    // here (employees PAID, not employed), and is the same third chip
    // govreports uses for the same reason.
    chips: ["whichtool", "whatpage", "whatnext"],
  },
  reports: {
    places: ["pb_insights_hub:payroll", "pb_insights_hub:budget"],
    blurb: B("Payroll Report: one run's totals against the run before. Budget: each function's spending against its budget, month by month.",
             "Báo cáo lương: tổng của một đợt so với đợt trước. Ngân sách: chi tiêu của từng bộ phận so với ngân sách, theo từng tháng."),
    next: B("On the report, open the people under Changes first. On Budget, read the reading on each function: money gone against year gone.",
            "Trên báo cáo, hãy mở những người trong Changes trước. Trên Ngân sách, hãy đọc nhận định của từng bộ phận: tiền đã đi so với năm đã trôi."),
    chips: ["whichtool", "whatpage", "whatnext"],
  },
  govreports: {
    places: ["pb_compliance_hub:filings"],
    blurb: B("The statutory filings this company's country asks for, grouped by authority and prefilled for one month.",
             "Các báo cáo bắt buộc mà quốc gia của công ty này yêu cầu, nhóm theo cơ quan và điền sẵn cho một tháng."),
    next: B("Check that the month's runs have all reached done before you generate anything. The tiles read what has been computed. An unfinished run is a filing that is short.",
            "Hãy kiểm tra mọi đợt lương của tháng đã đạt Hoàn tất trước khi kết xuất bất cứ gì. Các biểu mẫu chỉ đọc phần đã tính. Một đợt còn dở là một báo cáo bị thiếu."),
    chips: ["fileinsurance", "whichfilings", "whatnext"],
  },

  /* -- Payroll setup (LEARN REFRESH step 3) --------------------------------
     The guided setup, the Approval Matrix and the Group page are cockpits of
     their own, opened from a Settings card: they ground by their action tag
     (the generator's SCREEN_ACTION_TAGS) and open by their action (`open`).
     Mapping publishes its tab to the "where am I" store, so Component
     treatment is a place of its own; the Records Desk is People › Records.
     The three `_rules` / `_sheet` / `_builder` entries are the second view of
     a station in the practice company — replica screens, not destinations. */
  blueprint: {
    open: "pb_blueprint.action_pb_blueprint",
    blurb: B("The guided setup: six steps that build one pay scheme, with a sample person's pay beside you the whole way.",
             "Phần thiết lập có hướng dẫn: sáu bước dựng một chương trình lương, luôn có lương của một người mẫu bên cạnh."),
    next: B("Work down the steps on the left. Continue always says where it goes next. Nothing is created until the first Continue, and Finish does not put the scheme live.",
            "Đi lần lượt các bước bên trái. Nút Tiếp tục luôn nói nó sẽ đi tới đâu. Chưa có gì được tạo cho tới lần Tiếp tục đầu tiên, và Hoàn thành không đưa chương trình vào dùng."),
    chips: ["newscheme", "currency", "whatpage", "whatnext"],
  },
  blueprint_rules: {
    blurb: B("The guided setup's Pay rules step: each component written as a sentence, with its formula underneath.",
             "Bước Quy tắc lương của phần thiết lập có hướng dẫn: mỗi thành phần viết thành một câu, kèm công thức bên dưới."),
    next: B("Add or change a component, then watch the take-home figure on the right. Continue walks the three tabs before it moves on.",
            "Thêm hoặc sửa một thành phần, rồi nhìn con số thực nhận bên phải. Nút Tiếp tục đi qua ba tab trước khi chuyển bước."),
    chips: ["newscheme", "whatnext"],
  },
  mapping: {
    places: ["pb_mapping_studio:journey", "pb_mapping_studio:api", "pb_mapping_studio:transform",
             "pb_mapping_studio:import", "pb_mapping_studio:employee", "pb_mapping_studio:scheme",
             "pb_mapping_studio:cycle"],
    blurb: B("Where every value a pay scheme reads comes from: FROM a source, TO a scheme, drawn as one journey.",
             "Mỗi giá trị mà chương trình lương đọc đến từ đâu: TỪ một nguồn, ĐẾN một chương trình lương, vẽ thành một hành trình."),
    next: B("Read the line above the lanes first: anything not fed will be computed as empty. Open a card to see its fields; the arrow in its corner opens the tab that edits it.",
            "Hãy đọc dòng phía trên các làn trước: thứ gì chưa có nguồn sẽ được tính là trống. Mở một thẻ để xem các trường; mũi tên ở góc thẻ mở tab để sửa nó."),
    chips: ["wherefrom", "notaddup", "bulkupdate", "whatpage"],
  },
  mapping_sheet: {
    blurb: B("Mapping's spreadsheet tab: this period's file shows its columns, and you wire them to the scheme.",
             "Tab bảng tính của Ánh xạ: tệp của kỳ này cho thấy các cột, và bạn nối chúng vào chương trình lương."),
    next: B("Drop the file to read its headings — no numbers are imported here. When a column meets a component another source already feeds, choose the order.",
            "Thả tệp để đọc tiêu đề — ở đây không nhập con số nào. Khi một cột gặp thành phần đã có nguồn khác cấp, hãy chọn thứ tự."),
    chips: ["wherefrom", "whatnext"],
  },
  treatment: {
    places: ["pb_mapping_studio:treatment"],
    blurb: B("What the scheme does with each component: its pay role, whether it is a subtotal, and its value type.",
             "Chương trình lương làm gì với từng thành phần: vai trò trong lương, có phải tổng phụ không, và loại giá trị."),
    next: B("Clear the chips first: Needs your answer, then Type says otherwise. After saving, recompute the pay run — saving never rewrites a payslip.",
            "Hãy xử lý các nhãn trước: Cần câu trả lời của bạn, rồi Loại giá trị nói khác. Sau khi lưu, hãy tính lại đợt lương — lưu không bao giờ viết lại phiếu lương."),
    chips: ["notaddup", "wherefrom", "whatnext"],
  },
  matrix: {
    open: "pb_approval_config.action_pb_approval_matrix",
    blurb: B("The Approval Matrix: every process that needs a sign-off, the route it follows, and whether it is in use.",
             "Ma trận phê duyệt: mọi quy trình cần phê duyệt, lộ trình nó đi theo, và nó có đang được dùng hay không."),
    next: B("Look for Needs people first: those routes stop requests until somebody is named. A change you publish applies to new requests only.",
            "Hãy tìm Cần bổ sung người trước: những lộ trình đó làm dừng yêu cầu cho tới khi có người được ghi tên. Thay đổi bạn ban hành chỉ áp cho yêu cầu mới."),
    chips: ["changeroute", "whoapproves", "stuckwaiting", "whatpage"],
  },
  matrix_builder: {
    blurb: B("The route builder: Purpose, People, Safeguards, Review, Publish.",
             "Phần dựng lộ trình: Mục đích, Nhân sự, Bảo vệ, Xem lại, Ban hành."),
    next: B("Try an example before you publish: it names who would really decide. Publishing affects new requests only.",
            "Hãy Thử một ví dụ trước khi ban hành: nó ghi đúng tên người sẽ quyết định. Ban hành chỉ áp cho yêu cầu mới."),
    chips: ["changeroute", "whatnext"],
  },
  records: {
    places: ["pb_people_hub:records"],
    blurb: B("The Records Desk: change the employee, contract and bank fields your pay scheme reads, for one person or hundreds.",
             "Records Desk: sửa các trường nhân viên, hợp đồng và ngân hàng mà chương trình lương của bạn đọc, cho một người hay hàng trăm người."),
    next: B("Pick the scheme, then who and which fields. Type or import a file, open Review, then Apply. Every apply can be undone from History.",
            "Chọn chương trình lương, rồi chọn ai và trường nào. Gõ hoặc nhập một tệp, mở Xem lại, rồi Áp dụng. Mỗi lần áp dụng đều hoàn tác được trong Lịch sử."),
    chips: ["bulkupdate", "wherefrom", "whatpage"],
  },
  schemes: {
    open: "pb_group.action_pb_group",
    blurb: B("Your group: the companies you own, the money the group reads in, and how exchange rates are picked.",
             "Tập đoàn của bạn: các công ty bạn sở hữu, đồng tiền tập đoàn dùng để đọc, và cách chọn tỷ giá."),
    next: B("Check that every month you report on has a rate. A month without one keeps its own money and is left out of converted totals.",
            "Hãy kiểm tra mọi tháng bạn báo cáo đều có tỷ giá. Tháng nào không có sẽ giữ đồng tiền của nó và bị để ra ngoài các tổng đã quy đổi."),
    chips: ["currency", "whatpage", "whatnext"],
  },


  /* -- The wider app (LEARN REFRESH step 4) ------------------------------
     Every one of these is a TAB of a hub, so each grounds by its place first;
     People › Pay also says which of its own tabs is showing (pb_pay publishes
     the inner tab), so Bands/Fairness and Review/Changes find two lessons.
     Access & delegation and the Generate a filing flow open full-page, so
     they ground by their action tag (SCREEN_ACTION_TAGS) and open by `open`.
     `hiring_request` and `filing_flow` are second views in the practice
     company, like the step 3 ones. */
  paybands: {
    places: ["pb_people_hub:pay/bands", "pb_people_hub:pay/fairness", "pb_people_hub:pay"],
    blurb: B("Pay bands drawn as a picture, with everyone placed in them, and a check on whether pay is fair.",
             "Các khoảng lương vẽ thành hình, mọi người được đặt vào đó, cùng phép kiểm tra xem lương có công bằng không."),
    next: B("Read Worth knowing first: it names who is paid below or above their band. Nothing on this tab changes anybody's pay.",
            "Hãy đọc Đáng biết trước: nó nêu tên ai đang được trả dưới hoặc trên khoảng lương. Không có gì ở tab này thay đổi lương của ai."),
    chips: ["bandcheck", "whosignsreview", "whatpage"],
  },
  payreview: {
    places: ["pb_people_hub:pay/review", "pb_people_hub:pay/changes"],
    blurb: B("The yearly pay review: a worksheet inside a budget, calibrated and signed off step by step. Changes holds single pay changes.",
             "Đợt xét lương hằng năm: một bảng tính trong ngân sách, được cân chỉnh và duyệt từng bước. Thay đổi chứa các thay đổi lương lẻ."),
    next: B("Use the guidance, watch the budget meter, then open Calibration. Clear What stops approval before Send for approval.",
            "Dùng hướng dẫn, theo dõi thước đo ngân sách, rồi mở Cân chỉnh. Xử lý Điều gì chặn duyệt trước khi Gửi duyệt."),
    chips: ["whosignsreview", "bandcheck", "whatnext"],
  },
  decisionroom: {
    places: ["pb_people_hub:plan"],
    blurb: B("The Decision Room: try next year — people, rises, overtime — and see its cost and profit before you commit.",
             "Phòng quyết định: thử trước năm sau — con người, tăng lương, tăng ca — và xem chi phí, lợi nhuận trước khi cam kết."),
    next: B("Pick a preset, move the levers, save the plan, then press Exact cost before you propose it. Nothing here changes payroll.",
            "Chọn một phương án có sẵn, xoay các cần gạt, lưu kế hoạch, rồi bấm Chi phí chính xác trước khi đề xuất. Không có gì ở đây thay đổi bảng lương."),
    chips: ["whatif", "whatpage", "whatnext"],
  },
  peoplemore: {
    places: ["pb_home_hub:wall", "pb_home_hub:coming_up", "pb_people_hub:where", "pb_people_hub:assets",
             "pb_people_hub:praise", "pb_people_hub:goals", "pb_people_hub:announcements"],
    blurb: B("The Wall and Announce on Home, and People's smaller tabs: where people work, what they hold, their goals.",
             "Bảng vinh danh và Thông báo ở Trang chủ, cùng các tab nhỏ của Con người: nơi mọi người làm, họ giữ gì, mục tiêu của họ."),
    next: B("Say thank you on the Wall, or open the tab for what you came to do. A tab you cannot see is not in your company.",
            "Hãy nói lời cảm ơn trên Bảng vinh danh, hoặc mở tab cho việc bạn cần. Tab bạn không thấy là tab không có trong công ty bạn."),
    chips: ["whatpage", "whatnext"],
  },
  hiring: {
    places: ["pb_lifecycle_hub:hiring"],
    blurb: B("Hiring: every open role on one board, four steps each, from the request to the welcome.",
             "Tuyển dụng: mọi vị trí đang tuyển trên một bảng, mỗi vị trí bốn bước, từ đề xuất tới chào mừng."),
    next: B("Read each card's Next line — it is the one thing that moves that role on. Raise a hiring request before you advertise.",
            "Hãy đọc dòng Tiếp theo trên mỗi thẻ — đó là việc giúp vị trí đó đi tiếp. Đề xuất tuyển dụng trước khi đăng tin."),
    chips: ["raisehire", "whatpage", "whatnext"],
  },
  hiring_request: {
    blurb: B("The hiring request wizard: the role, its responsibilities, the interview plan, and the budget.",
             "Trình đề xuất tuyển dụng: vị trí, trách nhiệm, kế hoạch phỏng vấn, và ngân sách."),
    next: B("Set the salary on Budget & review, then send it for approval. Finance is asked only when it is over budget.",
            "Đặt mức lương ở Ngân sách & xem lại, rồi gửi phê duyệt. Tài chính chỉ được hỏi khi vượt ngân sách."),
    chips: ["raisehire", "whatnext"],
  },
  joiners: {
    places: ["pb_lifecycle_hub:newjoiners"],
    blurb: B("New joiners: everyone starting soon, their buddy, and what is still to prepare.",
             "Nhân viên mới: những người sắp vào làm, người đồng hành của họ, và những gì còn phải chuẩn bị."),
    next: B("Clear Still without a buddy first, then open each card for what is still to do — the bank account before the first pay run.",
            "Hãy xử lý Chưa có người đồng hành trước, rồi mở từng thẻ xem còn phải làm gì — tài khoản ngân hàng trước đợt lương đầu tiên."),
    chips: ["newjoiner", "whatpage", "whatnext"],
  },
  probation: {
    places: ["pb_lifecycle_hub:probation"],
    blurb: B("Probation: every trial that is running, colleagues' views, and the decision each one needs.",
             "Thử việc: mọi đợt thử việc đang chạy, ý kiến đồng nghiệp, và quyết định mỗi đợt cần."),
    next: B("Start with Ending within a week. Chase late answers, then make sure the manager decides before the end date.",
            "Hãy bắt đầu với Kết thúc trong vòng một tuần. Nhắc các câu trả lời trễ, rồi đảm bảo quản lý quyết định trước ngày kết thúc."),
    chips: ["endtrial", "whatpage", "whatnext"],
  },
  growth: {
    places: ["pb_lifecycle_hub:pip"],
    blurb: B("Growth plans: a conversation, coaching, then a written plan with objectives, ending in a decision.",
             "Kế hoạch phát triển: trao đổi, kèm cặp, rồi một kế hoạch bằng văn bản có mục tiêu, kết thúc bằng một quyết định."),
    next: B("Look at Drifting or at risk first. An objective at risk is the moment to talk.",
            "Hãy xem Chệch hướng hoặc có rủi ro trước. Một mục tiêu có rủi ro là lúc cần trao đổi."),
    chips: ["whatpage", "whatnext"],
  },
  contractends: {
    places: ["pb_lifecycle_hub:contracts"],
    blurb: B("Contracts ending: everything that ends in the next sixty days, and the decision each one needs.",
             "Hợp đồng sắp hết hạn: mọi hợp đồng kết thúc trong sáu mươi ngày tới, và quyết định mỗi hợp đồng cần."),
    next: B("Clear Nobody has decided before month end: raise the decision, then make it permanent, extend it or let it end.",
            "Hãy xử lý Chưa ai quyết định trước cuối tháng: nêu quyết định, rồi chuyển chính thức, gia hạn hoặc để hết hạn."),
    chips: ["expirysoon", "whatpage", "whatnext"],
  },
  exits: {
    places: ["pb_lifecycle_hub:exits"],
    blurb: B("Exits: everyone leaving, the four desks signing them off, and the final settlement that waits for all four.",
             "Nghỉ việc: những người sắp nghỉ, bốn phòng ban xác nhận bàn giao, và quyết toán chờ đủ cả bốn."),
    next: B("Open Settlements held up first: each card says which desk has not signed. Chase that desk, then close the settlement.",
            "Hãy mở Quyết toán bị vướng trước: mỗi thẻ cho biết phòng ban nào chưa ký. Nhắc phòng ban đó, rồi chốt quyết toán."),
    chips: ["leaver", "whatpage", "whatnext"],
  },
  wftoday: {
    places: ["pb_workforce:today"],
    blurb: B("Today: who is in, late, out or on leave, with the Needs you panel beside it.",
             "Hôm nay: ai có mặt, đi trễ, vắng hoặc nghỉ phép, cùng khung Cần bạn bên cạnh."),
    next: B("Clear the Needs you panel: approve the clean overtime in one press, and open the rest one by one.",
            "Hãy xử lý khung Cần bạn: duyệt phần tăng ca sạch trong một lần bấm, và mở từng việc còn lại."),
    chips: ["approveot", "lockweek", "whatpage"],
  },
  wftime: {
    places: ["pb_workforce:time"],
    blurb: B("Time, Time Off and Overtime: hours worked and their exceptions, leave waiting, and overtime to approve inside its limits.",
             "Chấm công, Nghỉ phép và Tăng ca: giờ làm và các ngoại lệ, đơn nghỉ đang chờ, và tăng ca cần duyệt trong giới hạn."),
    next: B("Clear exceptions through the week so Close is a check. Read any near-the-limit mark before you approve overtime.",
            "Hãy xử lý ngoại lệ trong suốt tuần để Chốt kỳ chỉ là bước kiểm tra. Đọc dấu gần giới hạn trước khi duyệt tăng ca."),
    chips: ["approveot", "whatnext"],
  },
  /* Time Off and Overtime are tabs of their own; the wftime lesson and
     walkthrough cover all three, so these two are places, not stations. */
  wftimeoff: {
    name: B("Time Off", "Nghỉ phép"),
    places: ["pb_workforce:timeoff"],
    blurb: B("Time Off: leave waiting for a decision, and who is out today. Apply on behalf files leave for someone who cannot.",
             "Nghỉ phép: đơn nghỉ đang chờ quyết định, và ai nghỉ hôm nay. Đăng ký thay nộp đơn cho người không tự làm được."),
    next: B("Decide the oldest request first; the pay run reads approved leave.",
            "Hãy quyết định đơn cũ nhất trước; đợt lương đọc các ngày nghỉ đã duyệt."),
    chips: ["approveot", "whatnext"],
  },
  wfovertime: {
    name: B("Overtime", "Tăng ca"),
    places: ["pb_workforce:overtime"],
    blurb: B("Overtime: the approval queue, and the monthly and yearly limits it is checked against.",
             "Tăng ca: hàng chờ duyệt, và các giới hạn theo tháng, theo năm mà nó được đối chiếu."),
    next: B("Read any near-the-limit mark before you approve. Clean overtime can also be approved from the Needs you panel.",
            "Hãy đọc dấu gần giới hạn trước khi duyệt. Tăng ca sạch cũng có thể được duyệt từ khung Cần bạn."),
    chips: ["approveot", "whatnext"],
  },
  wfclose: {
    places: ["pb_workforce:close"],
    blurb: B("Close: the week's flags, what goes to payroll, and the lock that sends it.",
             "Chốt kỳ: các cờ cảnh báo của tuần, những gì chuyển sang bảng lương, và nút khoá để gửi đi."),
    next: B("Fix what is wrong, approve as-is only what really happened, read the handoff, then Lock week & send to payroll.",
            "Điều chỉnh những gì sai, chỉ duyệt nguyên trạng những gì thật sự đã xảy ra, đọc phần chuyển giao, rồi Khóa tuần và gửi vào bảng lương."),
    chips: ["lockweek", "whatnext"],
  },
  access: {
    open: "biz_access.action_pb_access_board",
    blurb: B("Access & delegation: who can do what, as roles, and handing your access over while you are away.",
             "Quyền truy cập & uỷ quyền: ai được làm gì, theo vai trò, và bàn giao quyền của bạn khi vắng mặt."),
    next: B("Going away? Hand my access over, with an end date. Wondering what someone sees? See it as them.",
            "Sắp đi vắng? Hãy bàn giao quyền kèm ngày kết thúc. Muốn biết một người thấy gì? Hãy xem dưới góc nhìn của họ."),
    chips: ["delegate", "whatpage"],
  },
  filing_flow: {
    open: "pb_govt_reports.action_pb_filing_flow",
    blurb: B("Generate a filing: choose the filing, set its scope, then generate the files.",
             "Tạo hồ sơ: chọn báo cáo, đặt phạm vi, rồi tạo các tệp."),
    next: B("Check the company and the month on Scope. Generate makes files to download; nothing is sent anywhere.",
            "Kiểm tra công ty và tháng ở Phạm vi. Tạo sinh ra các tệp để tải xuống; không có gì được gửi đi."),
    chips: ["fileinsurance", "whatnext"],
  },
  compliancemore: {
    places: ["pb_compliance_hub:bank", "pb_compliance_hub:young", "pb_compliance_hub:audit"],
    blurb: B("Bank changes checked twice, hour limits for workers under 18, and a record of who changed what.",
             "Thay đổi ngân hàng được kiểm tra hai lần, giới hạn giờ làm cho lao động dưới 18 tuổi, và nhật ký ai đã sửa gì."),
    next: B("Start a bank change by dropping the bank's letter. For who changed a salary, filter Audit to Salary only.",
            "Bắt đầu một thay đổi ngân hàng bằng cách thả thư của ngân hàng vào. Muốn biết ai đã sửa lương, lọc Nhật ký kiểm toán theo Chỉ có lương."),
    chips: ["whatpage", "whatnext"],
  },

  /* -- The nine hubs (LEARN REFRESH step 1) --------------------------------
     Since the rail cutover every working screen is a TAB inside one of nine
     pages. These are not lessons: they are what the helper says on a tab that
     has no lesson yet, so it is never silent — what the page is for, its tabs
     in order with one plain line each, and the few things people most often
     come here to do. Steps 2–4 write the lessons.

     `hub.tabs` is keyed by the LENS KEY the shell uses; the helper lists only
     the tabs the shell itself shows this person (hub_place.js), in the
     shell's order, and a tab with no line here still shows its screen label.
     Tab NAMES match the product's own labels in both languages — where the
     product's Vietnamese is weak it is still what the reader sees on screen.
     `often` is [lens key, what people do there]; each gets "Take me there". */
  hub_home: {
    name: B("Home", "Trang chủ"),
    hub: {
      tag: "pb_home_hub", xmlid: "pb_home_hub.action_pb_home_hub",
      tabs: {
        pulse: [B("Pulse", "Tổng quan"),
                B("Where this month's payroll is, the numbers that describe the company, and a card for each part of Payobook worth opening today.",
                  "Kỳ lương tháng này đang ở đâu, các con số mô tả công ty, và một thẻ cho từng phần của Payobook đáng mở hôm nay.")],
        approvals: [B("Approvals", "Phê duyệt"),
                    B("One inbox for everything waiting for your sign-off, pay runs included.",
                      "Một hộp thư cho mọi thứ đang chờ bạn phê duyệt, kể cả các đợt lương.")],
        wall: [B("Wall", "Bảng vinh danh"),
               B("The recognition wall: praise colleagues have given each other.",
                 "Bảng vinh danh: những lời khen đồng nghiệp dành cho nhau.")],
        coming_up: [B("Announce", "Thông báo"),
                    B("What the company is about to tell its people, on one calendar.",
                      "Những gì công ty sắp thông báo tới mọi người, trên một lịch.")],
      },
      often: [
        ["approvals", B("Sign off what is waiting for you", "Phê duyệt những việc đang chờ bạn")],
        ["pulse", B("See where this month's payroll is", "Xem kỳ lương tháng này đang ở đâu")],
      ],
    },
    blurb: B("Your starting page. It tells you where this month's payroll is and what is waiting for you.",
             "Trang bạn bắt đầu. Nó cho biết kỳ lương tháng này đang ở đâu và việc gì đang chờ bạn."),
    next: B("Open Approvals first if anything is waiting for you. Otherwise read Pulse, then go to the page the work is on.",
            "Hãy mở Phê duyệt trước nếu có việc đang chờ bạn. Nếu không, hãy đọc Tổng quan, rồi đi tới trang có phần việc đó."),
    chips: ["whatpage", "whatnext", "howrun", "practice"],
  },
  hub_pay: {
    name: B("Pay Run", "Đợt lương"),
    hub: {
      tag: "pb_pay_hub", xmlid: "pb_payhub.action_pb_pay_hub",
      tabs: {
        run: [B("Run", "Chạy lương"),
              B("Start a new pay run for one month. It makes draft payslips; nothing is paid or sent yet.",
                "Bắt đầu một đợt lương mới cho một tháng. Bước này tạo phiếu lương nháp; chưa có gì được chi hay gửi đi.")],
        runs: [B("Runs", "Các đợt lương"),
               B("Every pay run on one board, in three columns: Draft, Waiting for approval and Done.",
                 "Mọi đợt lương trên một bảng, chia ba cột: Nháp, Chờ phê duyệt và Hoàn tất.")],
        payslips: [B("Payslips", "Phiếu lương"),
                   B("Read every payslip in a run line by line, with the working behind each net figure.",
                     "Đọc từng dòng của mọi phiếu lương trong một đợt, kèm phần tính toán phía sau mỗi con số thực nhận.")],
        results: [B("Results", "Kết quả"),
                  B("A run's results as one grid, each figure against the person's previous run, with an Excel download.",
                    "Kết quả của một đợt trong một bảng, mỗi con số so với đợt trước của người đó, kèm tải xuống Excel.")],
        import: [B("Import", "Nhập"),
                 B("Bring in attendance, overtime and other pay data from a file or a connected system.",
                   "Đưa dữ liệu chấm công, tăng ca và các dữ liệu lương khác vào từ tệp hoặc từ hệ thống đã kết nối.")],
        deliver: [B("Deliver", "Chi trả"),
                  B("The bank file and the payment release, each with its own approval, and payslips as password-protected PDFs.",
                    "Tệp ngân hàng và lệnh chuyển tiền, mỗi thứ có phê duyệt riêng, và phiếu lương dạng PDF có mật khẩu.")],
        adjust: [B("Adjust", "Điều chỉnh"),
                 B("Two lists: Retro, money owed for a month already closed, and Proration, pay for part of a month.",
                   "Hai danh sách: Hồi tố, khoản còn nợ của một tháng đã đóng, và Phân bổ theo tỷ lệ, lương cho một phần của tháng.")],
        settle: [B("Settle", "Quyết toán"),
                 B("The final pay of people who are leaving: last salary, unused leave and deductions.",
                   "Khoản chi cuối cho người nghỉ việc: lương cuối, phép chưa dùng và các khoản khấu trừ.")],
        paycal: [B("Calendar", "Lịch lương"),
                 B("The payroll calendar: when this month's pay closes and when it is paid.",
                   "Lịch lương: khi nào kỳ lương tháng này chốt và khi nào được chi.")],
        awards: [B("Awards", "Thưởng"),
                 B("Bonuses and awards to be paid through payroll.",
                   "Các khoản thưởng sẽ được chi qua bảng lương.")],
      },
      often: [
        ["run", B("Start this month's pay run", "Bắt đầu đợt lương tháng này")],
        ["payslips", B("Check payslips before they are approved", "Kiểm tra phiếu lương trước khi được phê duyệt")],
        ["deliver", B("Send payslips and the bank file", "Gửi phiếu lương và tệp ngân hàng")],
      ],
    },
    blurb: B("Everything about paying people this month: start a run, check it, and send the money and payslips.",
             "Mọi việc để trả lương tháng này: bắt đầu một đợt, kiểm tra nó, rồi gửi tiền và phiếu lương."),
    next: B("Look at Runs first. It shows which runs are still a draft and which are waiting for approval. Start a new one from Run.",
            "Hãy xem bảng các đợt lương trước. Nó cho biết đợt nào còn là nháp và đợt nào đang chờ phê duyệt. Bắt đầu đợt mới từ tab Chạy lương."),
    chips: ["whatpage", "whatnext", "howrun", "practice"],
  },
  hub_people: {
    name: B("People", "Con người"),
    hub: {
      tag: "pb_people_hub", xmlid: "pb_people_hub.action_pb_people_hub",
      tabs: {
        employees: [B("Employees", "Nhân viên"),
                    B("The people list. Open a person, or their contract, from their row. The Contracts button opens every contract.",
                      "Danh sách nhân sự. Mở một người, hoặc hợp đồng của họ, ngay từ dòng của họ. Nút Hợp đồng mở toàn bộ hợp đồng.")],
        records: [B("Records", "Hồ sơ"),
                  B("Update employee, contract and bank details for many people at once, with a file or on screen.",
                    "Cập nhật thông tin nhân viên, hợp đồng và ngân hàng cho nhiều người cùng lúc, bằng tệp hoặc ngay trên màn hình.")],
        pay: [B("Pay", "Lương"),
              B("Pay bands drawn as a picture, and the yearly pay review.",
                "Các dải lương dưới dạng hình vẽ, và đợt xét lương hằng năm.")],
        where: [B("Where they work", "Nơi họ làm việc"),
                B("People who work for more than one company, and the days they spend in each.",
                  "Những người làm cho nhiều công ty, và số ngày họ làm ở mỗi nơi.")],
        assets: [B("Assets", "Tài sản"),
                 B("Every laptop, phone, card and account the company has handed out, and who holds it.",
                   "Mọi máy tính, điện thoại, thẻ và tài khoản công ty đã cấp, và ai đang giữ.")],
        praise: [B("Praise", "Khen ngợi"),
                 B("Company values and the praise people give each other.",
                   "Giá trị của công ty và những lời khen mọi người dành cho nhau.")],
        goals: [B("Goals", "Mục tiêu"),
                B("What each person plans to do this year, and how it is going.",
                  "Điều mỗi người dự định làm trong năm nay, và tiến độ tới đâu.")],
        announcements: [B("Announce", "Thông báo"),
                        B("Write and schedule messages to your people.",
                          "Soạn và lên lịch các thông báo gửi tới mọi người.")],
        plan: [B("Plan", "Kế hoạch"),
               B("Try out next year's headcount and cost before you commit to it.",
                 "Thử trước số người và chi phí của năm sau trước khi quyết định.")],
      },
      often: [
        ["employees", B("Find or add an employee", "Tìm hoặc thêm một nhân viên")],
        ["records", B("Update many records at once", "Cập nhật nhiều hồ sơ cùng lúc")],
        ["pay", B("Check pay against the bands", "Đối chiếu lương với các dải lương")],
      ],
    },
    blurb: B("Your people and what is written down about them: who they are, their contracts, their pay and their goals.",
             "Nhân sự của bạn và những gì được ghi lại về họ: họ là ai, hợp đồng, lương và mục tiêu của họ."),
    next: B("Start in Employees. Clear anyone who is not ready to be paid before the month's pay run, not after it.",
            "Hãy bắt đầu ở Nhân viên. Xử lý những người chưa sẵn sàng nhận lương trước đợt lương tháng, đừng để sau."),
    chips: ["whatpage", "whatnext", "practice"],
  },
  hub_lifecycle: {
    name: B("Lifecycle", "Vòng đời nhân sự"),
    hub: {
      tag: "pb_lifecycle_hub", xmlid: "pb_lifecycle.action_pb_lifecycle_hub",
      tabs: {
        journeys: [B("Journeys", "Hành trình"),
                   B("The step-by-step checklists that run when someone joins, moves or leaves.",
                     "Các danh sách việc từng bước chạy khi có người vào, chuyển vị trí hoặc nghỉ việc.")],
        hiring: [B("Hiring", "Tuyển dụng"),
                 B("Ask for a new person, get it agreed, then write the job advert.",
                   "Đề xuất tuyển một người mới, xin phê duyệt, rồi viết tin tuyển dụng.")],
        newjoiners: [B("New joiners", "Nhân viên mới"),
                     B("Everyone starting soon: their buddy, their first days and what is still to prepare.",
                       "Những người sắp bắt đầu: người hướng dẫn, những ngày đầu và việc còn phải chuẩn bị.")],
        exits: [B("Exits", "Nghỉ việc"),
                B("From resignation to final pay: notice, approval, handover.",
                  "Từ đơn nghỉ việc tới khoản chi cuối: báo trước, phê duyệt, bàn giao.")],
        probation: [B("Probation", "Thử việc"),
                    B("Trial periods: when each one ends and who has to decide.",
                      "Thời gian thử việc: khi nào kết thúc và ai phải quyết định.")],
        pip: [B("Growth plans", "Kế hoạch phát triển"),
              B("Coaching first, then a written plan with dates on it.",
                "Kèm cặp trước, rồi một kế hoạch bằng văn bản có mốc thời gian.")],
        contracts: [B("Contracts", "Hợp đồng"),
                    B("Contracts that end soon, decided in good time: renew, change or let them end.",
                      "Các hợp đồng sắp hết hạn, được quyết định sớm: gia hạn, thay đổi hoặc để kết thúc.")],
      },
      often: [
        ["hiring", B("Ask for a new hire", "Đề xuất tuyển người mới")],
        ["newjoiners", B("Prepare for someone starting soon", "Chuẩn bị cho người sắp vào làm")],
        ["exits", B("Handle someone who is leaving", "Xử lý người sắp nghỉ việc")],
      ],
    },
    blurb: B("The moments in a person's time with the company: hiring, joining, probation, contracts and leaving.",
             "Những mốc trong quãng thời gian một người làm việc ở công ty: tuyển dụng, nhận việc, thử việc, hợp đồng và nghỉ việc."),
    next: B("Open the tab for the moment you are handling. Each one lists what is due soonest first.",
            "Hãy mở tab ứng với mốc bạn đang xử lý. Mỗi tab liệt kê việc đến hạn sớm nhất lên trước."),
    chips: ["whatpage", "whatnext"],
  },
  hub_workforce: {
    name: B("Workforce", "Lực lượng lao động"),
    hub: {
      tag: "pb_workforce", xmlid: "pb_mission.action_pb_workforce", lens_key: "pb_shell_lens",
      tabs: {
        today: [B("Today", "Hôm nay"),
                B("Who is in, who is late and who is out today.",
                  "Hôm nay ai có mặt, ai đi muộn và ai vắng.")],
        schedule: [B("Schedule", "Lịch ca"),
                   B("The shift roster for the week, with its cost and cover.",
                     "Lịch ca của tuần, kèm chi phí và mức phủ ca.")],
        time: [B("Time", "Chấm công"),
               B("Hours worked, as a timeline and a week grid, with the exceptions to fix.",
                 "Số giờ làm việc, dạng dòng thời gian và bảng tuần, kèm các ngoại lệ cần xử lý.")],
        timeoff: [B("Time Off", "Nghỉ phép"),
                  B("Leave requests waiting for a decision, and who is away this month.",
                    "Các đơn nghỉ phép đang chờ quyết định, và ai vắng mặt trong tháng này.")],
        overtime: [B("Overtime", "Tăng ca"),
                   B("Overtime to approve before it reaches payroll.",
                     "Giờ tăng ca cần phê duyệt trước khi vào bảng lương.")],
        trips: [B("Trips", "Công tác"),
                B("Business trip requests and their approval.",
                  "Các đề nghị đi công tác và việc phê duyệt chúng.")],
        approvals: [B("Approvals", "Phê duyệt"),
                    B("What your team is waiting for you to sign off.",
                      "Những gì nhóm của bạn đang chờ bạn phê duyệt.")],
        close: [B("Close", "Chốt kỳ"),
                B("Lock the week's time so payroll can use it.",
                  "Khoá dữ liệu giờ công của tuần để bảng lương sử dụng.")],
        holidays: [B("Holidays", "Ngày lễ"),
                   B("Public holidays this year.",
                     "Các ngày nghỉ lễ trong năm nay.")],
        field: [B("Field", "Hiện trường"),
                B("A live map of staff who check in from the field.",
                  "Bản đồ trực tiếp của nhân viên chấm công ngoài hiện trường.")],
      },
      often: [
        ["today", B("See who is in today", "Xem hôm nay ai có mặt")],
        ["timeoff", B("Decide on leave requests", "Quyết định các đơn nghỉ phép")],
        ["close", B("Close the week for payroll", "Chốt tuần cho bảng lương")],
      ],
    },
    blurb: B("Time and attendance for your teams: who is working, their shifts, leave and overtime, ready for payroll.",
             "Chấm công và thời gian làm việc của các nhóm: ai đang làm, ca làm, nghỉ phép và tăng ca, sẵn sàng cho bảng lương."),
    next: B("Start with Today. Then clear what is waiting in Time Off and Overtime before you close the week.",
            "Hãy bắt đầu với Hôm nay. Rồi xử lý những gì đang chờ ở Nghỉ Phép và Tăng ca trước khi chốt tuần."),
    chips: ["whatpage", "whatnext"],
  },
  hub_insights: {
    name: B("Insights", "Phân tích"),
    hub: {
      tag: "pb_insights_hub", xmlid: "pb_insights_hub.action_pb_insights_hub",
      tabs: {
        pulse: [B("Pulse", "Tổng quan"),
                B("The cost story of recent pay runs, department by department.",
                  "Diễn biến chi phí của các đợt lương gần đây, theo từng bộ phận.")],
        explorer: [B("Explorer", "Khám phá dữ liệu"),
                   B("Build your own question over payroll figures that match the payslips.",
                     "Tự đặt câu hỏi trên các số liệu lương luôn khớp với phiếu lương.")],
        workforce: [B("Workforce", "Lực lượng lao động"),
                    B("The same months read as people: headcount, joiners and leavers, attendance.",
                      "Vẫn những tháng đó nhưng đọc theo con người: sĩ số, người vào, người nghỉ, chấm công.")],
        payroll: [B("Payroll Report", "Báo cáo lương"),
                  B("The payroll report for a month, ready to download.",
                    "Báo cáo lương của một tháng, sẵn sàng để tải xuống.")],
        budget: [B("Budget", "Ngân sách"),
                 B("What each team was given for the year against what it has spent.",
                   "Ngân sách năm của từng nhóm so với số đã chi.")],
        hiring: [B("Hiring", "Tuyển dụng"),
                 B("How hiring is going: requests, adverts and people taken on.",
                   "Tình hình tuyển dụng: đề xuất, tin tuyển dụng và số người đã nhận.")],
        training: [B("Training", "Đào tạo"),
                   B("Who has taken which course, and how they did.",
                     "Ai đã học khoá nào, và kết quả ra sao.")],
        goals: [B("Goals", "Mục tiêu"),
                B("How this year's goals are going across the company.",
                  "Tiến độ mục tiêu năm nay trên toàn công ty.")],
      },
      often: [
        ["pulse", B("Read this month's cost story", "Xem diễn biến chi phí tháng này")],
        ["explorer", B("Answer your own question", "Tự trả lời câu hỏi của bạn")],
        ["payroll", B("Download the payroll report", "Tải báo cáo lương")],
      ],
    },
    blurb: B("Reports and analysis built from your pay runs and your people. Reading here changes nothing.",
             "Báo cáo và phân tích dựng từ các đợt lương và nhân sự của bạn. Xem ở đây không thay đổi gì cả."),
    next: B("Check the state of the run a number comes from before you quote it. A draft run can still change.",
            "Hãy kiểm tra trạng thái của đợt lương mà con số đến từ đó trước khi trích dẫn. Một đợt còn nháp vẫn có thể thay đổi."),
    chips: ["whatpage", "whatnext"],
  },
  hub_compliance: {
    name: B("Compliance", "Tuân thủ"),
    hub: {
      tag: "pb_compliance_hub", xmlid: "pb_compliance_hub.action_pb_compliance_hub",
      tabs: {
        filings: [B("Filings", "Tờ khai"),
                  B("The government filings your country asks for, prefilled for one month.",
                    "Các báo cáo bắt buộc mà quốc gia của bạn yêu cầu, điền sẵn cho một tháng.")],
        bank: [B("Bank", "Ngân hàng"),
               B("Read bank documents, check the details, and update employee bank records once approved.",
                 "Đọc chứng từ ngân hàng, kiểm tra thông tin, và cập nhật tài khoản ngân hàng của nhân viên sau khi được phê duyệt.")],
        young: [B("Young workers", "Lao động chưa thành niên"),
                B("The hour limits for workers under 18, and anyone close to breaking them.",
                  "Giới hạn giờ làm của lao động dưới 18 tuổi, và những ai sắp vượt giới hạn.")],
        audit: [B("Audit", "Nhật ký kiểm toán"),
                B("A read-only record of who changed what, and when.",
                  "Nhật ký chỉ đọc: ai đã thay đổi gì, và khi nào.")],
      },
      often: [
        ["filings", B("Prepare this month's filings", "Chuẩn bị các báo cáo tháng này")],
        ["audit", B("Check who changed something", "Kiểm tra ai đã thay đổi một thông tin")],
      ],
    },
    blurb: B("What the law asks of payroll: government filings, bank checks, young-worker limits and the audit trail.",
             "Những gì pháp luật yêu cầu với bảng lương: báo cáo cho cơ quan nhà nước, kiểm tra ngân hàng, giới hạn cho lao động trẻ và nhật ký kiểm tra."),
    next: B("Make sure every run for the month is done before you prepare a filing. A filing only counts what has been computed.",
            "Hãy chắc chắn mọi đợt lương của tháng đã hoàn tất trước khi chuẩn bị báo cáo. Báo cáo chỉ tính những gì đã được tính lương."),
    chips: ["whatpage", "whatnext"],
  },
  hub_learn: {
    name: B("Learn", "Học cùng Payobook"),
    hub: {
      tag: "learn_hub", xmlid: "pb_learn.action_learn_hub",
      tabs: {
        lessons: [B("Lessons", "Bài học"),
                  B("Your lesson map: short lessons, walkthroughs and practice tasks in a safe practice company.",
                    "Bản đồ bài học của bạn: bài học ngắn, hướng dẫn từng bước và bài thực hành trong một công ty thực hành an toàn.")],
        training: [B("Training", "Đào tạo"),
                   B("Courses your company has given you, with their tests.",
                     "Các khoá học công ty giao cho bạn, kèm bài kiểm tra.")],
        team: [B("Team", "Nhóm"),
               B("Who on your team is ready for month-end.",
                 "Ai trong nhóm của bạn đã sẵn sàng cho kỳ chốt lương cuối tháng.")],
        settings: [B("Settings", "Cài đặt"),
                   B("Every learning switch for your company, on one card.",
                     "Mọi công tắc về học tập của công ty, trên một thẻ.")],
      },
      often: [
        ["lessons", B("Carry on with your lessons", "Tiếp tục các bài học")],
        ["team", B("See who is ready for month-end", "Xem ai đã sẵn sàng cho cuối tháng")],
      ],
    },
    blurb: B("Where you learn Payobook: lessons, walkthroughs of the real screens, and practice that cannot touch real data.",
             "Nơi bạn học Payobook: bài học, hướng dẫn trên các màn hình thật, và bài thực hành không chạm tới dữ liệu thật."),
    next: B("Open Lessons and press the next lesson on your path. Each one takes a few minutes.",
            "Hãy mở Bài học và bấm bài tiếp theo trên lộ trình của bạn. Mỗi bài chỉ mất vài phút."),
    chips: ["whatpage", "whatnext", "practice"],
  },
  hub_settings: {
    name: B("Settings", "Cài đặt"),
    hub: {
      tag: "pb_settings_hub", xmlid: "pb_settings.action_pb_settings_hub",
      tabs: {
        formula: [B("Formula Engine", "Bộ máy công thức"),
                  B("How pay is calculated: configurations, components and test runs.",
                    "Cách tính lương: cấu hình, thành phần lương và các lần chạy thử.")],
        structures: [B("Salary Structures", "Cấu trúc lương"),
                     B("The older salary structures, kept so past payslips can still be explained.",
                       "Các cấu trúc lương thế hệ cũ, được giữ để phiếu lương cũ vẫn giải thích được.")],
        statutory: [B("Statutory", "Bảo hiểm & Thuế"),
                    B("Insurance rates, tax tables and family relief.",
                      "Tỷ lệ bảo hiểm, biểu thuế và giảm trừ gia cảnh.")],
        integrations: [B("Integrations", "Tích hợp"),
                       B("Connected systems, how their fields map, and what they have sent.",
                         "Các hệ thống đã kết nối, cách ánh xạ trường dữ liệu, và những gì chúng đã gửi về.")],
        payroll: [B("Payroll defaults", "Mặc định tính lương"),
                  B("The payroll settings screen.",
                    "Màn hình cài đặt bảng lương.")],
        org: [B("Companies & Tenants", "Công ty & Đơn vị thuê bao"),
              B("The companies this system runs payroll for.",
                "Các công ty mà hệ thống này tính lương.")],
        nav: [B("Navigation", "Điều hướng"),
              B("What the left rail offers, and in what order.",
                "Thanh bên trái có những mục gì, và theo thứ tự nào.")],
        company: [B("Your company", "Công ty của bạn"),
                  B("Your own name, address, tax numbers and logo.",
                    "Tên, địa chỉ, mã số thuế và logo của công ty bạn.")],
        guided_setup: [B("Guided setup", "Thiết lập có hướng dẫn"),
                       B("Set up a new pay configuration step by step.",
                         "Thiết lập một cấu hình lương mới theo từng bước.")],
        approvals: [B("Approvals", "Phê duyệt"),
                    B("Who signs off what, in which order.",
                      "Ai phê duyệt việc gì, theo thứ tự nào.")],
        access: [B("Access & delegation", "Quyền truy cập & uỷ quyền"),
                 B("Who can open which screens, and who can stand in for whom.",
                   "Ai được mở màn hình nào, và ai được làm thay ai.")],
        group: [B("Group", "Tập đoàn"),
                B("Companies that belong together, and the currency they are added up in.",
                  "Các công ty cùng một tập đoàn, và đồng tiền dùng để cộng gộp số liệu.")],
        hiring: [B("Hiring", "Tuyển dụng"),
                 B("How hiring requests are set up and approved.",
                   "Cách thiết lập và phê duyệt đề xuất tuyển dụng.")],
        announcements: [B("Announcements", "Thông báo"),
                        B("Settings for company announcements.",
                          "Cài đặt cho thông báo của công ty.")],
        vendors: [B("Vendors", "Nhà cung cấp"),
                  B("Outside firms and what they are allowed to see.",
                    "Các đơn vị bên ngoài và những gì họ được phép xem.")],
        about: [B("About Payobook", "Về Payobook"),
                B("Which version you are on, and your plan.",
                  "Phiên bản bạn đang dùng, và gói dịch vụ của bạn.")],
        demo_data: [B("Demo data", "Dữ liệu mẫu"),
                    B("Load or remove sample data for trying things out.",
                      "Nạp hoặc gỡ dữ liệu mẫu để thử nghiệm.")],
      },
      often: [
        ["formula", B("Change how pay is calculated", "Thay đổi cách tính lương")],
        ["approvals", B("Decide who signs off what", "Quyết định ai phê duyệt việc gì")],
        ["access", B("Give someone access", "Cấp quyền cho một người")],
      ],
    },
    blurb: B("Where Payobook is set up for your company: how pay is calculated, who can do what, and what is connected.",
             "Nơi Payobook được thiết lập cho công ty bạn: cách tính lương, ai được làm gì, và những hệ thống nào đã kết nối."),
    next: B("Pick the area on the left. Most changes here affect the next pay run, so check them before month-end rather than during it.",
            "Hãy chọn một mục ở bên trái. Phần lớn thay đổi ở đây ảnh hưởng tới đợt lương kế tiếp, nên hãy kiểm tra trước kỳ cuối tháng chứ đừng làm giữa chừng."),
    chips: ["whatpage", "whatnext"],
  },
  /* LEARN REFRESH step 3 — Mapping is not a hub on the rail, but it is a page
     of tabs that says which tab is on screen (mapping_studio.js publishes
     it), and its lens context key is `pb_mode`. Declaring it here is what
     lets a lesson open Mapping ON a tab — Component treatment — and lets the
     helper name the tab it cannot teach yet. */
  hub_mapping: {
    name: B("Mapping", "Ánh xạ"),
    hub: {
      tag: "pb_mapping_studio", xmlid: "pb_formula_studio.action_pb_mapping_studio", lens_key: "pb_mode",
      tabs: {
        api: [B("System fields → Scheme", "Trường hệ thống → Chương trình lương"),
              B("Wire the fields a connected system sends onto the scheme's inputs.",
                "Nối các trường mà hệ thống đã kết nối gửi về vào đầu vào của chương trình lương.")],
        transform: [B("Transformations", "Chuyển đổi"),
                    B("What each transformation rule reads, works out, and which components take its answer.",
                      "Mỗi quy tắc chuyển đổi đọc gì, tính ra gì, và những thành phần nào nhận kết quả của nó.")],
        import: [B("Spreadsheet columns → Scheme", "Cột bảng tính → Chương trình lương"),
                 B("Wire the columns of this period's file onto the scheme's inputs.",
                   "Nối các cột của tệp kỳ này vào đầu vào của chương trình lương.")],
        employee: [B("Employee & contract ⇆", "Nhân viên & hợp đồng ⇆"),
                   B("Values kept on employee and contract records, read back when a file or feed has nothing.",
                     "Giá trị giữ trên hồ sơ nhân viên và hợp đồng, được đọc lại khi tệp hoặc nguồn cấp dữ liệu không có gì.")],
        scheme: [B("Who is paid by what", "Ai được trả lương theo phương án nào"),
                 B("Which pay scheme pays each part of the workforce.",
                   "Chương trình lương nào trả lương cho từng bộ phận nhân sự.")],
        cycle: [B("Mid ↔ End cycle", "Giữa ↔ Cuối chu kỳ"),
                B("Carry a mid-month advance into the end-of-month run.",
                  "Chuyển khoản tạm ứng giữa tháng sang đợt lương cuối tháng.")],
        treatment: [B("Component treatment", "Xử lý thành phần"),
                    B("What the scheme does with each component: its pay role, subtotal and value type.",
                      "Chương trình lương làm gì với từng thành phần: vai trò trong lương, tổng phụ và loại giá trị.")],
        journey: [B("Journey", "Hành trình"),
                  B("The whole picture: every file, system and record that feeds this scheme.",
                    "Toàn cảnh: mọi tệp, hệ thống và hồ sơ cấp dữ liệu cho chương trình lương này.")],
      },
      often: [
        ["journey", B("See where each value comes from", "Xem mỗi giá trị đến từ đâu")],
        ["treatment", B("Fix figures that do not add up", "Sửa số liệu không khớp")],
        ["import", B("Wire this month's spreadsheet", "Nối bảng tính của tháng này")],
      ],
    },
    blurb: B("Mapping: where each value a pay scheme reads comes from, and what the scheme does with it.",
             "Ánh xạ: mỗi giá trị mà chương trình lương đọc đến từ đâu, và chương trình làm gì với nó."),
    next: B("Start on Journey to see the whole road. The scheme picker on the right of the header decides which scheme every tab shows.",
            "Hãy bắt đầu ở Hành trình để thấy cả chặng đường. Ô chọn chương trình lương ở bên phải phần đầu quyết định mọi tab hiện chương trình nào."),
    chips: ["wherefrom", "notaddup", "whatpage"],
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
    label: B("What does Need review count?", "Cần xem xét đếm những gì?"),
    match: ["why is this flagged", "what does the flag mean", "needs review", "sao bi gan co", "phiếu này bị gắn cờ", "what does need review count"],
    showMe: ["pw-pills", "ps-kpis"],
    blocks: [
      { k: "p", v: B("On Pay Run › Run it adds up three things. Payslips whose take-home pay came out at zero or below. People Payobook could not make a payslip for, such as someone with no running contract in the period. And people in the pay data file who are not in Payobook yet — listed, not paid.",
                     "Ở Đợt lương › Chạy lương, nó cộng ba thứ: phiếu lương có thực nhận bằng không hoặc âm, những người Payobook không tạo được phiếu lương (ví dụ không có hợp đồng hiệu lực trong kỳ), và những người có trong tệp dữ liệu lương mà chưa có trong Payobook — được liệt kê, không được trả lương.") },
      { k: "p", v: B("On Pay Run › Payslips it is narrower: only payslips whose take-home pay is zero or below.",
                     "Ở Đợt lương › Phiếu lương thì hẹp hơn: chỉ những phiếu có thực nhận bằng không hoặc âm.") },
      { k: "warn", v: B("It does not flag a big jump on last month. Trần Văn Hùng's overtime at 382% of June appears in no list — spotting that is the reviewer's job.",
                        "Nó không đánh dấu một mức tăng lớn so với tháng trước. Tăng ca của Trần Văn Hùng bằng 382% tháng 6 không nằm trong danh sách nào — nhận ra điều đó là việc của người soát xét.") },
      { k: "src", v: B("The Run tab's result and review steps, and the Payslips tab's numbers.",
                       "Bước kết quả và bước soát xét của tab Chạy lương, và các con số của tab Phiếu lương.") },
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
    // LEARNOS Phase 4. `showMe` opens the walkthrough on ONE step; these two
    // offer the whole story, and Try is offered because sc_payslips has a
    // replica to take it on. The generator refuses a `try` that names a
    // scenario without the mode, so this pair cannot drift into a dead button.
    watch: "sc_payslips",
    try: "sc_payslips",
    simpler: B("Two things move a monthly salary and one thing usually does not. Overtime moves it, and tax follows the overtime. Insurance normally stays put, because it is worked out from the salary written in the contract rather than from what was actually earned that month.",
               "Có hai thứ làm lương tháng thay đổi và một thứ thường thì không. Tăng ca làm lương thay đổi, và thuế đi theo tăng ca. Bảo hiểm thường đứng yên, vì nó được tính từ mức lương ghi trong hợp đồng chứ không phải từ số thực sự kiếm được trong tháng đó."),
    blocks: [
      { k: "p", v: B("Take Mai's June to July as the worked example. Net went from 12,064,000 ₫ to 12,919,000 ₫, and it decomposes exactly:",
                     "Lấy tháng 6 sang tháng 7 của Mai làm ví dụ. Thực nhận đi từ 12.064.000 ₫ lên 12.919.000 ₫, và phân tách chính xác như sau:") },
      { k: "calcKpi" },
      { k: "p", v: B("Insurance did not move because BHXH, BHYT and BHTN are charged on the insurance base. For her that is the 12,000,000 ₫ in her contract, and overtime is not part of it. Tax did move, because taxable income is a monthly figure.",
                     "Bảo hiểm không đổi vì BHXH, BHYT và BHTN tính trên mức lương đóng bảo hiểm. Với cô ấy đó là 12.000.000 ₫ ghi trong hợp đồng, và tăng ca không nằm trong mức đó. Thuế thì có đổi, vì thu nhập chịu thuế là con số theo tháng.") },
      { k: "src", v: B("Mai's June and July payslips, configuration HOASEN_RETAIL_END v12.",
                       "Phiếu lương tháng 6 và tháng 7 của Mai, cấu hình HOASEN_RETAIL_END v12.") },
    ],
  },

  {
    id: "approve", screens: ["payruns", "payslips", "approvals"],
    label: B("Can I approve this run?", "Tôi có thể phê duyệt đợt này không?"),
    match: ["how do i approve", "can i approve", "approve this run", "phê duyệt thế nào", "toi duyet duoc khong"],
    showMe: ["ai-approve", "ai-tabs"],
    roleVariants: {
      any: [
        { k: "p", v: B("A pay run is approved along the route your company drew in the Approval Matrix — by default Payroll check, then HR lead review, then Finance approval. You can decide it only when its current step names you, and then it is on Home › Approvals, My turn.",
                       "Một đợt lương được duyệt theo lộ trình mà công ty bạn vẽ trong Ma trận phê duyệt — mặc định là Kiểm tra bảng lương, rồi Trưởng nhân sự soát xét, rồi Tài chính phê duyệt. Bạn chỉ quyết định được khi bước hiện tại ghi tên bạn, và khi đó nó nằm ở Trang chủ › Phê duyệt, tab Đến lượt tôi.") },
        { k: "steps", v: [
          { t: B("Open Home › Approvals, My turn", "Mở Trang chủ › Phê duyệt, tab Đến lượt tôi"), a: "ai-tabs" },
          { t: B("Open the request and read the facts it was sent in with", "Mở yêu cầu và đọc các dữ kiện nó mang theo lúc gửi"), a: "ai-facts" },
          { t: B("Open a few payslips — the ones with the biggest changes first", "Mở vài phiếu lương — những phiếu thay đổi nhiều nhất trước"), a: "ps-list" },
          { t: B("Approve — or Send it back with a note if something needs fixing", "Phê duyệt — hoặc Trả lại kèm ghi chú nếu có gì cần sửa"), a: "ai-approve" },
        ] },
        { k: "src", v: B("The pay run's approval request and the route it follows.",
                         "Yêu cầu phê duyệt của đợt lương và lộ trình nó đi theo.") },
      ],
      manager: [
        { k: "ok", v: B("Yes, when the run's current step names you. It is then on Home › Approvals, My turn. Approving moves all its payslips together — there is no way to approve some of them.",
                        "Có, khi bước hiện tại của đợt lương ghi tên bạn. Khi đó nó nằm ở Trang chủ › Phê duyệt, tab Đến lượt tôi. Phê duyệt sẽ chuyển toàn bộ phiếu lương cùng lúc — không có cách nào duyệt một phần.") },
        { k: "steps", v: [
          { t: B("Open My turn and the request", "Mở tab Đến lượt tôi và yêu cầu đó"), a: "ai-tabs" },
          { t: B("Read the facts, then open a few payslips", "Đọc các dữ kiện, rồi mở vài phiếu lương"), a: "ai-facts" },
          { t: B("Approve — or Send it back with a note", "Phê duyệt — hoặc Trả lại kèm ghi chú"), a: "ai-approve" },
        ] },
        { k: "src", v: B("The pay run's approval route, and the step that names you.",
                         "Lộ trình phê duyệt của đợt lương, và bước ghi tên bạn.") },
      ],
      operator: [
        { k: "p", v: B("You prepare the run and send it in; the people on its route decide it. Press Submit for approval on its card in Pay Run › Runs, then follow whose step it is at.",
                       "Bạn lập đợt lương và gửi đi; những người trên lộ trình quyết định. Hãy bấm Gửi để phê duyệt trên thẻ của nó ở Đợt lương › Các đợt lương, rồi theo dõi nó đang ở bước của ai.") },
        { k: "steps", v: [
          { t: B("Submit for approval on the run's card", "Gửi để phê duyệt trên thẻ của đợt lương"), a: "pk-card-actions" },
          { t: B("Read whose step it is at", "Đọc xem nó đang ở bước của ai"), a: "pk-route" },
          { t: B("If it comes back, fix what the note says and submit again", "Nếu bị trả lại, sửa đúng điều ghi chú nói rồi gửi lại"), a: "pk-card" },
        ] },
        { k: "src", v: B("The pay run's approval route, and the Runs board.",
                         "Lộ trình phê duyệt của đợt lương, và bảng Các đợt lương.") },
      ],
      no_access: [
        { k: "refusal", v: B("Not unless a step on the route names you. The inbox shows everyone what they may see, but a request is yours to decide only when its current step names you.",
                             "Không, trừ khi một bước trên lộ trình ghi tên bạn. Hộp phê duyệt cho mọi người xem những gì họ được phép xem, nhưng một yêu cầu chỉ là của bạn khi bước hiện tại ghi tên bạn.") },
        { k: "who", v: B("The people on the route. The run's card on Pay Run › Runs says whose step it is at.",
                         "Những người trên lộ trình. Thẻ của đợt lương ở Đợt lương › Các đợt lương cho biết nó đang ở bước của ai.") },
        { k: "how", v: B("Ask {{payrollSupportContact}}. Who signs for a pay run is set in Settings › Approvals, and it is a decision about who signs for money.",
                         "Hãy hỏi {{payrollSupportContact}}. Ai ký cho một đợt lương được thiết lập ở Cài đặt › Phê duyệt, và đó là quyết định về việc ai ký cho những khoản tiền.") },
        { k: "src", v: B("The approval route, and the inbox's My turn tab.",
                         "Lộ trình phê duyệt, và tab Đến lượt tôi của hộp phê duyệt.") },
      ],
    },
  },


  {
    id: "reject", screens: ["payruns", "approvals"],
    label: B("What happens if I reject a run?", "Nếu tôi từ chối một đợt thì điều gì xảy ra?"),
    match: ["how do i reject", "reject the run", "từ chối đợt lương", "tra lai dot luong", "turn it down"],
    showMe: ["pk-rejected", "ai-turndown"],
    blocks: [
      { k: "p", v: B("The run is <b>cancelled</b>: its state becomes Rejected and every payslip in it is cancelled with it, all together. It moves to the folded Rejected pay runs list and does not come back — the way on is a new run.",
                     "Đợt lương bị <b>huỷ</b>: trạng thái chuyển thành Đã từ chối và mọi phiếu lương trong đó cùng bị huỷ, tất cả một lượt. Nó chuyển xuống danh sách thu gọn Đợt lương bị từ chối và không quay lại — muốn đi tiếp thì tạo đợt mới.") },
      { k: "p", v: B("Two doors lead there. <b>Reject</b> on the Runs board, for a run that should not exist — it asks once and needs no reason. <b>Turn it down</b> in the inbox, by the person whose step it is — it asks \"Why? (required)\" and keeps the reason on the run.",
                     "Có hai lối dẫn tới đó. <b>Từ chối</b> trên bảng Các đợt lương, cho một đợt không nên tồn tại — nó hỏi lại một lần và không cần lý do. <b>Từ chối</b> trong hộp phê duyệt, do người đến lượt duyệt thực hiện — nó hỏi \"Lý do? (bắt buộc)\" và lưu lý do trên đợt lương.") },
      { k: "warn", v: B("If the run only needs fixing, neither is right: Send it back returns it to Draft with a note.",
                        "Nếu đợt lương chỉ cần sửa thì cả hai đều không đúng: Trả lại sẽ đưa nó về Nháp kèm ghi chú.") },
      { k: "src", v: B("The run's Rejected state and its rejection fields: reason, who and when.",
                       "Trạng thái Đã từ chối của đợt lương và các trường từ chối: lý do, người từ chối và thời điểm.") },
    ],
  },


  {
    id: "checkfinal", screens: ["runpayroll", "payruns", "payslips"],
    label: B("What should I check before submitting?", "Cần kiểm tra gì trước khi gửi phê duyệt?"),
    match: ["before finalising", "before finalizing", "pre approval checklist", "trước khi chốt", "kiem tra gi truoc", "before submitting"],
    practice: "m1",
    blocks: [
      { k: "p", v: B("The list experienced officers actually use, in the order they use it:",
                     "Danh sách mà các chuyên viên giàu kinh nghiệm thực sự dùng, theo đúng thứ tự họ dùng:") },
      { k: "steps", v: [
        { t: B("The pay scheme and the month are the ones you meant", "Chương trình lương và tháng đúng là cái bạn định chạy"), a: "pw-summary" },
        { t: B("Everyone under Need review is understood — not in Payobook yet, or not paid for a reason you can name", "Mọi người trong Cần xem xét đều đã được hiểu — chưa có trong Payobook, hoặc không được trả vì lý do bạn nói được"), a: "pw-missing" },
        { t: B("The biggest changes on last month opened, and a few ordinary payslips sampled", "Đã mở những thay đổi lớn nhất so với tháng trước, và lấy mẫu vài phiếu bình thường"), a: "ps-list" },
        { t: B("The statutory lines present on a sample slip: BHXH, BHYT, BHTN, thuế TNCN", "Các dòng bắt buộc có mặt trên một phiếu mẫu: BHXH, BHYT, BHTN, thuế TNCN"), a: "ps-breakdown" },
        { t: B("Bank details valid for anyone who joined this month", "Thông tin ngân hàng hợp lệ cho những người mới vào tháng này") },
      ] },
      { k: "src", v: B("The checklist taught in the Run and Runs lessons and practised in the pay-run missions.",
                       "Danh sách kiểm tra được dạy trong bài Chạy lương và Các đợt lương, và thực hành trong các nhiệm vụ đợt lương.") },
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
    label: B("Will this affect a run that is already submitted?", "Việc này có ảnh hưởng đợt đã gửi phê duyệt không?"),
    match: ["affect the current run", "will this change", "ảnh hưởng đợt đang chạy", "co anh huong dot da trinh"],
    blocks: [
      { k: "ok", v: B("No. A run that is Waiting for approval has its payslips frozen, so nothing here changes it. What you do here reaches drafts only.",
                      "Không. Một đợt đang Chờ phê duyệt có các phiếu lương bị giữ nguyên, nên không gì ở đây làm thay đổi nó. Những gì bạn làm ở đây chỉ chạm tới bản nháp.") },
      { k: "p", v: B("Safe: computing a draft again, deleting a draft, loading pay data again for an open period. A submitted run changes only when someone on its route sends it back — then it is a draft again — or when it is withdrawn.",
                     "An toàn: tính lại bản nháp, xoá bản nháp, tải lại dữ liệu lương cho một kỳ còn mở. Một đợt đã gửi chỉ thay đổi khi có người trên lộ trình trả lại — khi đó nó lại là bản nháp — hoặc khi nó bị thu hồi.") },
      { k: "warn", v: B("\"Update Payobook\" is different: it saves values onto people's records, so it reaches every run computed from then on. Use This run only for a one-off.",
                        "\"Cập nhật Payobook\" thì khác: nó lưu giá trị vào hồ sơ của từng người, nên ảnh hưởng tới mọi đợt được tính từ đó về sau. Hãy dùng Chỉ đợt này cho khoản chỉ có một lần.") },
      { k: "src", v: B("The pay run's states, and what each one allows.",
                       "Các trạng thái của đợt lương, và mỗi trạng thái cho phép làm gì.") },
    ],
  },


  {
    id: "confidence", screens: ["import", "importwizard"],
    label: B("What do the import counts mean?", "Các con số khi nhập liệu nghĩa là gì?"),
    match: ["confidence score", "what does the score mean", "diem tin cay", "điểm tin cậy là gì", "import score", "import counts", "rows loaded matched"],
    showMe: ["iw-review", "iw-fixrows"],
    watch: "sc_import",
    try: "sc_import",
    simpler: B("Each row in your file is one person. The counts tell you how many were read, how many were matched to someone, and how many still need you. Every one that still needs you is somebody's pay.",
               "Mỗi dòng trong tệp là một người. Các con số cho biết bao nhiêu dòng đã được đọc, bao nhiêu dòng đã khớp với một người, và bao nhiêu dòng còn cần bạn. Mỗi dòng còn cần bạn là tiền lương của một ai đó."),
    blocks: [
      { k: "p", v: B("<b>Rows loaded</b>: rows read from the file. <b>Matched</b>: tied to an existing employee. <b>New employees</b>: rows you chose to create as people. <b>Need attention</b>: rows the importer could not place — no matching employee, a duplicate, or a cell it could not read.",
                     "<b>Dòng đã nạp</b>: số dòng đọc được từ tệp. <b>Đã khớp</b>: gắn được với một nhân viên đã có. <b>Nhân viên mới</b>: các dòng bạn chọn tạo thành người mới. <b>Cần xử lý</b>: các dòng trình nhập liệu không xếp được — không tìm ra nhân viên khớp, bị lặp, hoặc có ô không đọc được.") },
      { k: "p", v: B("There is no score on this screen. Read the counts: 46 of 48 matched still leaves two people. Resolve each with Match…, Retry or Skip — and Skip is right for a duplicate and quietly wrong for a person.",
                     "Màn hình này không có điểm số. Hãy đọc các con số: 46 trên 48 đã khớp vẫn còn hai con người. Xử lý từng dòng bằng Khớp…, Thử lại hoặc Bỏ qua — và Bỏ qua đúng với dòng lặp nhưng sai một cách âm thầm với một con người.") },
      { k: "src", v: B("The import wizard's review and validate steps.",
                       "Bước soát xét và bước kiểm tra của trình nhập liệu.") },
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
    simpler: B("Think of BHXH as a shared fund the law requires. Every month you put in 8% of the salary written in your contract. Not your bonuses, and not your overtime. Your company puts in more than double that on top. The fund pays for pensions, sick leave and maternity leave.",
               "Hãy hình dung BHXH như một quỹ chung mà pháp luật yêu cầu. Mỗi tháng bạn đóng 8% mức lương ghi trong hợp đồng. Không tính thưởng, không tính tăng ca. Công ty đóng thêm hơn gấp đôi phần đó. Quỹ này chi trả lương hưu, ốm đau và thai sản."),
    blocks: [
      { k: "p", v: B("BHXH is social insurance. On Mai's July payslip the employee share is 8% of the registered insurance base of 12,000,000 ₫, which is 960,000 ₫ and is deducted. Her employer pays a further 17.5% — a company cost that never appears in her net.",
                     "BHXH là bảo hiểm xã hội. Trên phiếu tháng 7 của Mai, phần người lao động là 8% của mức lương đóng bảo hiểm đã đăng ký 12.000.000 ₫, tức 960.000 ₫ và được khấu trừ. Doanh nghiệp đóng thêm 17,5% — chi phí công ty, không bao giờ xuất hiện trong thực nhận của cô ấy.") },
      { k: "calc" },
      { k: "p", v: B("The base is the point. It is the salary registered on the contract, not what was earned this month. That is why a month with 1,500,000 ₫ of overtime produces exactly the same BHXH as a month without any.",
                     "Mấu chốt nằm ở mức đóng. Đó là mức lương đã đăng ký theo hợp đồng, không phải số kiếm được trong tháng. Vì vậy một tháng có 1.500.000 ₫ tăng ca vẫn cho ra đúng khoản BHXH như tháng không có đồng tăng ca nào.") },
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
    id: "prorata", screens: ["proration", "adjust", "payslips", "fullfinal", "contracts"],
    label: B("How was this part-month salary worked out?", "Lương tháng lẻ ngày này được tính ra sao?"),
    match: ["prorated", "part month", "joined mid month", "tinh theo ngay cong", "ngày công lẻ"],
    showMe: ["lg-rows"],
    blocks: [
      { k: "p", v: B("The monthly amount times the days that count, over the days in the period. For someone who started on the 22nd of a 31-day month: 10 days out of 31, so a 10,000,000 ₫ salary becomes 3,225,806 ₫.",
                     "Mức lương tháng nhân với số ngày được tính, chia cho số ngày của kỳ. Với người bắt đầu ngày 22 của một tháng 31 ngày: 10 trên 31 ngày, nên mức lương 10.000.000 ₫ thành 3.225.806 ₫.") },
      { k: "p", v: B("Pay Run › Adjust › Proration keeps one line per amount. The row shows old, new and prorated; its drawer holds the basis and the days on each side of the change.",
                     "Đợt lương › Điều chỉnh › Phân bổ theo tỷ lệ giữ mỗi khoản một dòng. Dòng hiện mức cũ, mức mới và số đã phân bổ; ngăn chi tiết có cách tính và số ngày ở mỗi phía của thay đổi.") },
      { k: "warn", v: B("Read the days before the money. If the days are right and the amount still looks wrong, the problem is further back, in the contract or the pay data.",
                        "Hãy đọc số ngày trước khi đọc tiền. Nếu số ngày đúng mà số tiền vẫn có vẻ sai thì vấn đề nằm ở phía trước, trong hợp đồng hoặc dữ liệu lương.") },
      { k: "src", v: B("The Proration tab of Pay Run › Adjust, and the scheme's Part-month pay setting.",
                       "Tab Phân bổ theo tỷ lệ của Đợt lương › Điều chỉnh, và thiết lập Lương theo phần tháng của chương trình lương.") },
    ],
  },

  {
    id: "retroq", screens: ["retro", "adjust", "payruns"],
    label: B("Where does back pay come from?", "Khoản truy lĩnh đến từ đâu?"),
    match: ["retro", "backdated", "back pay", "hồi tố", "truy linh", "tang luong lui ngay", "correct a closed month"],
    showMe: ["lg-rows"],
    blocks: [
      { k: "p", v: B("From the pay data load. A pay change may be dated before this month. With the scheme's Back-pay switch on, the load compares it with what was paid and adds the difference to this month.",
                     "Từ lần tải dữ liệu lương. Một thay đổi lương có thể có hiệu lực trước tháng này. Khi công tắc Truy lĩnh của chương trình lương bật, lần tải so nó với số đã trả và cộng phần chênh vào tháng này.") },
      { k: "p", v: B("Each line is on Pay Run › Adjust › Retro with the old amount, the new one and the delta, and its drawer names the month being made good.",
                     "Mỗi dòng nằm ở Đợt lương › Điều chỉnh › Hồi tố với mức cũ, mức mới và phần chênh, và ngăn chi tiết ghi tháng đang được bù.") },
      { k: "warn", v: B("Do not reopen a paid month to fix it. That month has been paid and reported; back pay settles the difference in the current month instead.",
                        "Đừng mở lại một tháng đã trả để sửa. Tháng đó đã được trả và báo cáo; khoản truy lĩnh bù phần chênh trong tháng hiện tại.") },
      { k: "src", v: B("The Retro tab of Pay Run › Adjust, and the scheme's Back-pay setting.",
                       "Tab Hồi tố của Đợt lương › Điều chỉnh, và thiết lập Truy lĩnh của chương trình lương.") },
    ],
  },

  {
    id: "practice", screens: "*",
    label: B("Let me practise this safely", "Cho tôi thực hành an toàn"),
    match: ["let me practise", "let me practice", "thực hành", "lam thu", "try it safely"],
    practice: "m1",
    blocks: [
      { k: "p", v: B("Good instinct. The practice missions run on a made-up company, not {{companyDisplayName}}. There is no server behind it, so nothing you do can reach a real employee, payslip or pay run. Three are playable: running a pay run, fixing a run that was sent back, and applying a statutory rate change.",
                     "Bản năng tốt. Các nhiệm vụ thực hành chạy trên một công ty giả lập, không phải {{companyDisplayName}}. Phía sau nó không có máy chủ nào, nên mọi thao tác đều không chạm tới nhân viên, phiếu lương hay đợt lương thật. Ba nhiệm vụ chơi được: chạy một đợt lương, sửa một đợt bị trả lại, và áp dụng một thay đổi tỷ lệ luật định.") },
      { k: "ok", v: B("You can fail safely there. Getting it wrong costs a recovery message rather than a salary.",
                      "Bạn được phép sai ở đó. Làm sai chỉ tốn một lời gợi ý quay lại, chứ không tốn một khoản lương.") },
      { k: "src", v: B("The practice missions in Learn › Lessons.",
                       "Các nhiệm vụ thực hành trong Học cùng Payobook › Bài học.") },
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
      { k: "how", v: B("What I can show you is where the numbers come from. The BHXH, BHYT and BHTN rates and the thuế TNCN table, plus the formula configuration on each division that decides which of them apply to whom. If a figure looks wrong, that is where to look. A wrong figure is worth finding; a smaller one is not the same thing.",
                       "Điều tôi có thể chỉ cho bạn là các con số đến từ đâu. Tỷ lệ BHXH, BHYT, BHTN và biểu thuế TNCN, cùng cấu hình công thức trên từng bộ phận quyết định tỷ lệ nào áp cho ai. Nếu một con số trông sai, đó là nơi cần xem. Tìm ra một con số sai là việc đáng làm; tìm một con số nhỏ hơn thì không phải cùng một việc.") },
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
      { k: "p", v: B("Because a payroll system that decides anything for you is a payroll system you cannot defend. Every number on a payslip comes from something written down here. A component in a formula configuration, a rate on an insurance policy, or a field mapped from a connected system.",
                     "Vì một hệ thống tính lương tự quyết thay bạn là hệ thống bạn không bảo vệ được. Mọi con số trên phiếu lương đều đến từ một thứ đã được ghi lại ở đây. Một thành phần trong cấu hình công thức, một tỷ lệ trên chính sách bảo hiểm, hoặc một trường được ánh xạ từ hệ thống đã kết nối.") },
      { k: "steps", v: [
        { t: B("Formula Engine — how each line is computed, for one division", "Công thức lương — mỗi dòng được tính thế nào, cho một bộ phận"), a: "fs-components" },
        { t: B("Statutory — the rates the law sets, for the whole company", "Bảo hiểm & Thuế — các tỷ lệ do luật định, cho cả công ty"), a: "st-rates" },
        { t: B("Integrations — how the inputs arrive without anybody retyping them", "Tích hợp — dữ liệu đầu vào về tới nơi mà không ai phải gõ lại"), a: "ig-roster" },
      ] },
      { k: "ok", v: B("Setup is done rarely and read often. Most of the time you are here to answer a question, not to change anything — and reading is always safe.",
                      "Thiết lập ít khi phải sửa nhưng thường xuyên phải đọc. Phần lớn thời gian bạn tới đây để trả lời một câu hỏi, không phải để thay đổi gì — và đọc thì luôn an toàn.") },
      { k: "src", v: B("The Settings page: formula configurations, statutory policies and connectors.",
                       "Trang Cài đặt: cấu hình công thức, chính sách bảo hiểm và các đầu nối.") },
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
      { k: "warn", v: B("Do not edit the policy that is in force. There is no version history to fall back on. The old declared rate is simply gone, and so is the evidence of what the company was declaring while last month was paid.",
                        "Đừng sửa chính sách đang có hiệu lực. Không có lịch sử phiên bản nào để quay lại. Mức đã khai báo trước đó đơn giản là mất, và bằng chứng về mức doanh nghiệp khai báo khi tháng trước được trả lương cũng mất theo.") },
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
      { k: "p", v: B("The one with the <b>latest effective date</b> among the policies that are still active. Two things it does NOT do, and both surprise people. It does not compare that date to today, so a policy dated from next month is displayed as soon as it is saved. And it does not read the end date at all.",
                     "Bản có <b>ngày hiệu lực mới nhất</b> trong số các chính sách còn đang bật. Có hai điều nó KHÔNG làm, và cả hai đều khiến người ta bất ngờ. Nó không so ngày đó với hôm nay, nên một chính sách ghi hiệu lực từ tháng sau sẽ hiển thị ngay khi vừa lưu. Và nó hoàn toàn không đọc ngày kết thúc.") },
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
    simpler: B("Insurance is not worked out from what you earned this month. It comes from the salary written in your contract, and only up to a limit. So a busy month with a lot of overtime does not change it. And a very high salary stops adding to it after a point.",
               "Bảo hiểm không tính từ số bạn kiếm được trong tháng. Nó tính từ mức lương ghi trong hợp đồng, và chỉ tính tới một mức giới hạn. Nên một tháng bận rộn nhiều tăng ca không làm nó thay đổi. Và lương rất cao thì qua một ngưỡng cũng không làm nó tăng thêm."),
    blocks: [
      { k: "p", v: B("Contributions are charged on the <b>insurance base</b>, normally the base salary in the contract. For Mai that is 12,000,000 ₫, not her gross of 14,280,000 ₫. That is why her 1,500,000 ₫ of overtime moved her tax and not a đồng of her insurance.",
                     "Bảo hiểm tính trên <b>mức lương đóng bảo hiểm</b>, thường là lương cơ bản ghi trong hợp đồng. Với Mai là 12.000.000 ₫, không phải tổng thu nhập 14.280.000 ₫. Vì vậy 1.500.000 ₫ tăng ca của cô ấy làm thay đổi thuế mà không làm thay đổi một đồng bảo hiểm nào.") },
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
      { k: "p", v: B("Taxable income is gross, less insurance, less <b>11,000,000 ₫</b> for yourself and <b>4,400,000 ₫</b> for each dependant. Only what is left goes into the bands. The bands are progressive: the first 5,000,000 ₫ is taxed at 5%, and each higher band applies only to the part inside it.",
                     "Thu nhập chịu thuế là tổng thu nhập, trừ bảo hiểm, trừ <b>11.000.000 ₫</b> cho bản thân và <b>4.400.000 ₫</b> cho mỗi người phụ thuộc. Chỉ phần còn lại mới đi vào biểu thuế. Biểu thuế là luỹ tiến: 5.000.000 ₫ đầu tiên chịu 5%, và mỗi bậc cao hơn chỉ áp cho phần nằm trong bậc đó.") },
      { k: "p", v: B("Mai's July: 14,280,000 − 1,260,000 insurance − 11,000,000 relief = <b>2,020,000 ₫</b> taxable, entirely inside the 5% band, so her tax is <b>101,000 ₫</b>. A dependant would take another 4,400,000 ₫ off and leave her paying almost nothing.",
                     "Tháng 7 của Mai: 14.280.000 − 1.260.000 bảo hiểm − 11.000.000 giảm trừ = <b>2.020.000 ₫</b> chịu thuế, nằm trọn trong bậc 5%, nên thuế là <b>101.000 ₫</b>. Thêm một người phụ thuộc sẽ trừ tiếp 4.400.000 ₫ và cô ấy gần như không phải nộp gì.") },
      { k: "warn", v: B("Dependants are registered, not assumed. A relief that was never registered is a tax bill the employee did not need to pay. It is the most common thing an employee is owed and never asks for.",
                        "Người phụ thuộc phải được đăng ký, không mặc định có. Một khoản giảm trừ chưa từng đăng ký là khoản thuế mà nhân viên lẽ ra không phải nộp. Đây là thứ nhân viên bị thiệt phổ biến nhất mà lại chẳng mấy ai hỏi tới.") },
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
      { k: "ok", v: B("New logic goes in a configuration, always. Pay Run › Run uses a configuration when you pick the pay scheme, so a rule added to a structure is a rule the scheme never sees.",
                      "Logic mới luôn đặt trong một cấu hình. Đợt lương › Chạy lương dùng một cấu hình khi bạn chọn chương trình lương, nên một quy tắc thêm vào cấu trúc là quy tắc mà bộ phận đó không bao giờ nhìn thấy.") },
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
    showMe: ["fs-deps", "fs-command"],
    practice: "m5",
    blocks: [
      { k: "p", v: B("It is allowed, and it reaches further than it looks. Every payslip computed by this configuration from now on, for the whole division. And any run still in draft that gets recomputed, including one for a month you thought was finished with.",
                     "Được phép, và tác động xa hơn vẻ ngoài của nó. Mọi phiếu lương do cấu hình này tính từ giờ trở đi, cho cả bộ phận. Và bất kỳ đợt nào còn ở Nháp mà được tính lại, kể cả đợt của một tháng bạn tưởng đã xong.") },
      { k: "steps", v: [
        { t: B("Read the dependency panel for anything you are renaming or removing", "Đọc bảng phụ thuộc cho bất cứ thứ gì bạn định đổi tên hoặc xoá"), a: "fs-deps" },
        { t: B("Preview against a sample employee — the arithmetic, on one person", "Xem trước trên một nhân viên mẫu — phép tính, trên một con người"), a: "fs-preview" },
        { t: B("Simulate against last month from Tools → Analyze — the same change across everybody", "Mô phỏng trên tháng trước từ Công cụ → Phân tích — cùng thay đổi đó trên tất cả mọi người"), a: "fs-command" },
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
    showMe: ["fs-config", "pw-scheme"],
    blocks: [
      { k: "p", v: B("One per division and cycle, and the code says which. The shape is <b>PREFIX_DIVISION_CYCLE</b>: a prefix that belongs to the company, the division, then <b>END</b> for the end-of-month settlement or <b>MID</b> for a mid-cycle advance. On the demo world that reads DEMO_RETAIL_END, DEMO_LOGISTICS_MID and so on — one naming rule, twelve configurations. On the practice company in the lessons the same rule reads HOASEN_RETAIL_END; the prefix changes, the shape does not.",
                     "Mỗi bộ phận và mỗi chu kỳ có một cấu hình, và chính mã cho biết là cái nào. Dạng chung là <b>TIỀN TỐ_BỘ PHẬN_CHU KỲ</b>: một tiền tố thuộc về công ty, rồi tên bộ phận, rồi <b>END</b> cho quyết toán cuối tháng hoặc <b>MID</b> cho khoản tạm ứng giữa kỳ. Trên bản demo, mã đọc là DEMO_RETAIL_END, DEMO_LOGISTICS_MID và tương tự — một quy ước đặt tên, mười hai cấu hình. Trên công ty thực hành trong các bài học, cùng quy ước đó đọc là HOASEN_RETAIL_END; tiền tố đổi, còn dạng chung thì không.") },
      { k: "p", v: B("You do not have to look it up before running a payroll. Picking the pay scheme in Pay Run › Run picks the configuration, and the Scope panel prints the scheme's name. Reading that name before you compute is the check.",
                     "Bạn không cần tra cứu trước khi chạy lương. Chọn chương trình lương trong Đợt lương › Chạy lương là đã chọn cấu hình, và bảng Phạm vi in tên chương trình đó. Đọc cái tên đó trước khi tính chính là bước kiểm tra.") },
      { k: "src", v: B("The configuration codes, and the Scope panel in Pay Run › Run.",
                       "Các mã cấu hình, và bảng Phạm vi trong Đợt lương › Chạy lương.") },
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
        { t: B("Read Need review in Pay Run › Run after you compute — people missing from the data show up there", "Đọc Cần xem xét ở Đợt lương › Chạy lương sau khi tính — những người thiếu dữ liệu hiện ra ở đó"), a: "pw-pills" },
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
            "tim o dau", "menu nam o dau", "cac nhom muc", "where is the formula engine"],
    showMe: ["scenario:sc_welcome", "rep-nav"],
    watch: "sc_welcome",
    blocks: [
      { k: "p", v: B("Nine pages on the left rail, each with its own tabs. <b>Home</b> (Pulse, Approvals), <b>Pay Run</b> (Run, Runs, Payslips, Import, Deliver, Adjust, Settle…), <b>People</b>, <b>Lifecycle</b>, <b>Workforce</b>, <b>Insights</b>, <b>Compliance</b>, <b>Learn</b> and <b>Settings</b>.",
                     "Chín trang trên thanh bên trái, mỗi trang có các tab riêng. <b>Trang chủ</b> (Tổng quan, Phê duyệt), <b>Đợt lương</b> (Chạy lương, Các đợt lương, Phiếu lương, Nhập, Chi trả, Điều chỉnh, Quyết toán…), <b>Con người</b>, <b>Vòng đời nhân sự</b>, <b>Lực lượng lao động</b>, <b>Phân tích</b>, <b>Tuân thủ</b>, <b>Học cùng Payobook</b> và <b>Cài đặt</b>.") },
      { k: "steps", v: [
        { t: B("Home › Pulse — where you land; Home › Approvals — what waits for you", "Trang chủ › Tổng quan — nơi bạn vào; Trang chủ › Phê duyệt — việc đang chờ bạn"), a: "dash-hero" },
        { t: B("Pay Run › Run — start a month; Runs — every run and who it is with", "Đợt lương › Chạy lương — bắt đầu một tháng; Các đợt lương — mọi đợt và đang ở chỗ ai"), a: "pw-rail" },
        { t: B("People › Employees — who can be paid, and their contracts", "Con người › Nhân viên — ai có thể được trả lương, và hợp đồng của họ"), a: "pe-kpis" },
        { t: B("Insights — what was paid, and the Explorer for your own questions", "Phân tích — những gì đã chi, và Explorer cho câu hỏi của riêng bạn"), a: "in-hero" },
        { t: B("Settings — Formula Engine, Statutory, Integrations, Approvals and more", "Cài đặt — Bộ máy công thức, Bảo hiểm & Thuế, Tích hợp, Phê duyệt và nhiều mục khác"), a: "fs-components" },
      ] },
      { k: "ok", v: B("A tab you cannot see is one your access does not open. The lessons still describe it, so you know what to ask for.",
                      "Tab nào bạn không thấy là tab quyền của bạn không mở được. Các bài học vẫn mô tả nó, để bạn biết cần xin quyền gì.") },
      { k: "src", v: B("The left rail and each page's tabs, as Payobook shows them for your access.",
                       "Thanh bên trái và các tab của từng trang, đúng như Payobook hiển thị theo quyền của bạn.") },
    ],
  },


  {
    id: "whichlane", screens: ["approvals", "payruns"],
    label: B("Who is holding this run up?", "Ai đang giữ đợt lương này lại?"),
    match: ["who is holding it up", "who do i chase", "whose gate is it at", "who has to approve next",
            "ai dang giu", "phai hoi ai", "dot luong tac o dau"],
    showMe: ["pk-route", "ai-route"],
    blocks: [
      { k: "p", v: B("A run that is Waiting for approval says it on its card in Pay Run › Runs. The card names the step and the person: \"HR lead review · With Đặng Thu Hà\". In the inbox the same request shows its route dots and \"Waiting for …\".",
                     "Một đợt đang Chờ phê duyệt ghi rõ điều đó trên thẻ của nó ở Đợt lương › Các đợt lương: bước nó đang ở và đang ở chỗ ai — \"Trưởng nhân sự soát xét · Đang ở Đặng Thu Hà\". Trong hộp phê duyệt, cùng yêu cầu đó hiện các chấm lộ trình và \"Đang chờ …\".") },
      { k: "warn", v: B("A run in Draft is not waiting for anybody's signature. It is waiting for whoever made it to submit it — or to fix what the sent-back note says.",
                        "Một đợt ở Nháp không chờ chữ ký của ai cả. Nó chờ người lập gửi đi — hoặc sửa đúng điều mà ghi chú trả lại nói.") },
      { k: "src", v: B("The run's approval request: its route and its current step.",
                       "Yêu cầu phê duyệt của đợt lương: lộ trình và bước hiện tại.") },
    ],
  },


  {
    id: "howmanyslips", screens: ["approvals", "payslips", "payruns"],
    label: B("How many payslips should I read?", "Tôi nên đọc bao nhiêu phiếu lương?"),
    match: ["how many payslips do i read", "do i have to read every payslip", "sampling strategy",
            "doc bao nhieu phieu", "co phai doc het khong", "lay mau phieu luong"],
    showMe: ["ps-list", "ai-facts"],
    practice: "m2",
    simpler: B("Not all of them. Start with the ones that changed most since last month. Then pick two or three ordinary ones at random.",
               "Không phải tất cả. Hãy bắt đầu với những phiếu thay đổi nhiều nhất so với tháng trước. Rồi chọn ngẫu nhiên hai ba phiếu bình thường."),
    blocks: [
      { k: "p", v: B("Not forty-eight. Payobook does not mark unusual payslips for you — Need review on Payslips only catches take-home pay at zero or below — so the reading is yours to aim.",
                     "Không phải bốn mươi tám phiếu. Payobook không đánh dấu hộ bạn các phiếu bất thường — Cần xem xét ở Phiếu lương chỉ bắt thực nhận bằng không hoặc âm — nên việc chọn đọc gì là của bạn.") },
      { k: "steps", v: [
        { t: B("Read the request's facts: Change against the last run, Contains overtime", "Đọc các dữ kiện của yêu cầu: Thay đổi so với kỳ trước, Có làm thêm giờ"), a: "ai-facts" },
        { t: B("Open the payslips with the most overtime or the biggest change", "Mở những phiếu nhiều tăng ca nhất hoặc thay đổi nhiều nhất"), a: "ps-list" },
        { t: B("Sample two or three ordinary ones", "Lấy mẫu hai ba phiếu bình thường"), a: "ps-list" },
        { t: B("Read one breakdown end to end — base to net", "Đọc trọn một bảng chi tiết — từ lương cơ bản tới thực nhận"), a: "ps-breakdown" },
      ] },
      { k: "src", v: B("The frozen facts on the approval request, and the payslips in Pay Run › Payslips.",
                       "Các dữ kiện được giữ nguyên trên yêu cầu phê duyệt, và các phiếu lương ở Đợt lương › Phiếu lương.") },
    ],
  },


  {
    id: "variance", screens: ["approvals", "payslips", "insights", "payruns"],
    label: B("Is this variance normal?", "Biến động thế này có bình thường không?"),
    match: ["explain the variance", "the total moved", "why is the run bigger",
            "bien dong co binh thuong", "tong thay doi", "giai thich chenh lech"],
    showMe: ["ai-facts", "ps-kpis"],
    blocks: [
      { k: "p", v: B("\"Normal\" is not a percentage. It is whether you can finish the sentence. On this run, July is 612,480,000 ₫ against June's 596,110,000 ₫: the request says +2.7%. There is one more employee, and one payslip carries 3,100,000 ₫ more overtime than last month.",
                     "\"Bình thường\" không phải là một con số phần trăm. Nó là việc bạn có nói trọn được câu giải thích hay không. Trên đợt này, tháng 7 là 612.480.000 ₫ so với 596.110.000 ₫ của tháng 6 — yêu cầu ghi +2,7% — với thêm một nhân viên, và một phiếu có tăng ca nhiều hơn tháng trước 3.100.000 ₫.") },
      { k: "warn", v: B("A comfortable-looking total is where a single wrong payslip hides best, and nothing on the screen flags it for you.",
                        "Một con số tổng trông dễ chịu chính là nơi một phiếu lương sai ẩn mình tốt nhất, và không gì trên màn hình đánh dấu nó cho bạn.") },
      { k: "steps", v: [
        { t: B("Headcount first — one more employee explains most of what looks like a rise", "Xem sĩ số trước — thêm một nhân viên là đủ giải thích phần lớn cái vẻ tăng đó"), a: "ps-kpis" },
        { t: B("Then overtime, which moves with the month rather than with the contract", "Rồi tới tăng ca, thứ thay đổi theo tháng chứ không theo hợp đồng"), a: "ps-breakdown" },
      ] },
      { k: "src", v: B("Change against the last run on the approval request, and the payslips underneath.",
                       "Mức thay đổi so với kỳ trước trên yêu cầu phê duyệt, và các phiếu lương bên dưới.") },
    ],
  },


  {
    id: "rejectright", screens: ["approvals", "payruns"],
    label: B("How do I write a note when I send it back?", "Viết ghi chú khi trả lại thế nào cho đúng?"),
    match: ["what should the reason say", "good rejection note",
            "viet ly do tra lai", "ghi ly do the nao", "ly do tu choi viet gi", "send back note"],
    showMe: ["ai-sendback"],
    blocks: [
      { k: "p", v: B("Name the payslip, name the figure, and name what you want checked. \"Payslip NV0031 — overtime 4,200,000 ₫ is 382% of June. Please check the timesheet.\" is a note somebody can act on today.",
                     "Nêu rõ phiếu nào, con số nào, và bạn muốn kiểm tra điều gì. \"Phiếu NV0031 — tăng ca 4.200.000 ₫ bằng 382% tháng 6. Vui lòng đối chiếu bảng chấm công.\" là ghi chú người khác xử lý được ngay hôm nay.") },
      { k: "warn", v: B("\"Wrong\" or \"please recheck\" leave the preparer guessing, and they will probably send in the same thing again.",
                        "\"Sai\" hay \"kiểm tra lại giúp\" khiến người lập phải đoán, và nhiều khả năng họ sẽ gửi lại đúng thứ cũ.") },
      { k: "ok", v: B("The note sits on the run's card in Draft and is kept in the request's history, with your name and the time.",
                      "Ghi chú nằm trên thẻ của đợt lương ở cột Nháp và được lưu trong lịch sử của yêu cầu, kèm tên bạn và thời điểm.") },
      { k: "src", v: B("The Send it back note on the approval request, and the sent-back line on the run's card.",
                       "Ghi chú Trả lại trên yêu cầu phê duyệt, và dòng bị trả lại trên thẻ của đợt lương.") },
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
    id: "expirysoon", screens: ["contracts", "employees", "contractends"],
    label: B("A contract expires mid-month — what happens?", "Hợp đồng hết hạn giữa tháng thì sao?"),
    match: ["contract expires mid month", "expiring contract", "renewal not signed yet",
            "hop dong het han giua thang", "gia han chua ky", "het han hop dong"],
    showMe: ["ct-roster", "ct-filters"],
    blocks: [
      { k: "p", v: B("Payroll computes from the contract, so it pays up to the day the contract ends and prorates the month around it. That is correct behaviour, and it is a surprise to everybody who was expecting a full month.",
                     "Hệ thống lương tính theo hợp đồng, nên nó trả tới đúng ngày hợp đồng kết thúc và tính phần tháng đó theo ngày công. Đó là hành vi đúng, và là điều bất ngờ với bất kỳ ai đang chờ một tháng lương đầy đủ.") },
      { k: "warn", v: B("A renewal still in <b>draft</b> on the run date is worse. A draft contract pays nothing at all, so the person simply is not in the run. Draft is the state to hunt for in the week before payroll.",
                        "Một hợp đồng gia hạn còn ở trạng thái <b>Nháp</b> vào ngày chạy lương thì còn tệ hơn. Hợp đồng nháp không trả gì cả, nên người đó đơn giản là không có trong đợt lương. Nháp là trạng thái cần lùng cho ra trong tuần trước kỳ lương.") },
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
        { k: "p", v: B("You can open the contract and read it. Whether you can save a new wage on it depends on your groups. At most companies that decision sits a tier above payroll, because a wage is an HR agreement that payroll carries out.",
                       "Bạn mở được hợp đồng và đọc nó. Còn lưu được mức lương mới hay không thì tuỳ nhóm quyền của bạn. Ở phần lớn công ty, quyết định đó thuộc về một cấp trên bộ phận lương, vì mức lương là thoả thuận nhân sự còn bộ phận lương là bên thực thi.") },
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
        { k: "who", v: B("A payroll officer or above can read the contract. Saving a new wage on it usually sits a tier higher again, because it is an HR agreement rather than a payroll setting.",
                         "Chuyên viên tính lương trở lên có thể đọc hợp đồng. Còn lưu một mức lương mới thường thuộc về một cấp cao hơn nữa, vì đó là thoả thuận nhân sự chứ không phải một thiết lập của bộ phận lương.") },
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
      { k: "p", v: B("Whoever holds one of the three payroll groups these menu items are gated on: a payroll officer, a payroll manager or a super administrator. Read that as a <b>ladder</b>, not a list. A role carries every group it implies, so a super administrator is also a manager, and a manager is also an officer. Everybody else does not see a greyed-out screen. They do not have the menu item at all.",
                     "Những ai giữ một trong ba nhóm quyền lương mà các mục này bị chặn theo: chuyên viên tính lương, quản lý lương hoặc quản trị viên cấp cao. Hãy hiểu đó là một <b>bậc thang</b> chứ không phải một danh sách. Một vai trò mang theo mọi nhóm mà nó bao hàm, nên quản trị viên cấp cao cũng là quản lý lương, và quản lý lương cũng là chuyên viên tính lương. Người khác không thấy một màn hình bị làm mờ. Họ không hề có mục đó trong menu.") },
      { k: "p", v: B("The ladder has a consequence worth knowing before you rely on it. A <b>final approver</b> is not named on these menu items, and sees the roster anyway. That role implies the analytics manager, which implies the payroll manager. So approving a total and reading everybody's salary are <b>not</b> separated here. Your company may need them separated: a person who signs for the money without seeing the names. That is a change somebody has to make, not a promise the shipped roles already keep.",
                     "Bậc thang này có một hệ quả nên biết trước khi bạn dựa vào nó. <b>Người phê duyệt cuối</b> không được nêu tên trên các mục này, nhưng vẫn xem được danh sách. Vai trò đó bao hàm quản lý phân tích lương, mà quản lý phân tích lương lại bao hàm quản lý lương. Vậy nên ở đây, việc duyệt một con số tổng và việc đọc lương của từng người <b>không</b> hề được tách ra. Công ty bạn có thể cần tách hai việc đó: một người ký cho khoản tiền mà không nhìn thấy tên ai. Đó là việc phải làm thêm, chứ không phải điều mà bộ vai trò mặc định đã hứa.") },
      { k: "p", v: B("Three roles are genuinely outside it. A payroll analytics user implies only the base payroll user, so they get the boards without the names. A payroll base user has their own payslip and nothing else. And anybody whose only payroll group is a country toggle. None of them can open Employees or Contracts from the menu.",
                     "Có ba vai trò thực sự nằm ngoài. Người dùng phân tích lương chỉ bao hàm người dùng lương cơ bản, nên họ có các bảng số liệu mà không có tên. Người dùng lương cơ bản chỉ có phiếu lương của chính mình. Và bất kỳ ai mà nhóm quyền lương duy nhất là một công tắc bật theo quốc gia. Không ai trong số đó mở được Nhân viên hay Hợp đồng từ menu.") },
      { k: "ok", v: B("That is the right shape for this data. A wage list answers questions nobody asked about colleagues, and hiding the door is a stronger promise than disabling a button on it.",
                      "Đó là cách làm đúng với loại dữ liệu này. Một danh sách lương trả lời những câu hỏi chẳng ai đặt ra về đồng nghiệp, và giấu hẳn cánh cửa là một cam kết mạnh hơn việc chỉ vô hiệu hoá một cái nút trên đó.") },
      { k: "warn", v: B("Exporting it moves the data somewhere none of that applies. A spreadsheet of salaries has no groups on it and no way to be taken back.",
                        "Xuất nó ra là đưa dữ liệu tới nơi mà mọi quy tắc trên không còn áp dụng. Một bảng tính lương thì không mang theo nhóm quyền nào và cũng không có cách nào thu hồi.") },
      { k: "src", v: B("The groups on the People sidebar leaves, the chain of implied groups those roles are declared with, and your own group membership.",
                       "Các nhóm quyền trên những mục Nhân sự ở thanh bên, chuỗi nhóm bao hàm mà các vai trò đó được khai báo, và nhóm quyền của chính bạn.") },
    ],
  },

  {
    id: "whichtool", screens: ["insights", "explorer", "workforcean", "reports"],
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
      { k: "ok", v: B("Explorer does explain <b>why</b>, and it is the only one that does. It builds a variance waterfall between two comparable periods that reconciles exactly, with an anomaly rail beside it. Any cell drills straight through to the employees behind it. Those rows are read from the payslip lines themselves, so the drill doubles as the audit trail for the number.",
                      "Explorer có giải thích <b>vì sao</b>, và là công cụ duy nhất làm được. Nó dựng một biểu đồ phân rã biến động giữa hai kỳ so sánh được, khớp chính xác từng đồng, kèm một dải cảnh báo bất thường bên cạnh. Bấm vào ô nào cũng đi thẳng xuống danh sách nhân viên đứng sau ô đó. Các dòng đó đọc từ chính phiếu lương, nên bước đi sâu ấy cũng chính là vết kiểm toán cho con số.") },
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
      { k: "p", v: B("Whichever ones your company's <b>country</b> has, and nothing else. The active company's country chooses the tiles, not what Payobook can produce. A Vietnamese company sees the BHXH forms and the labour-change declarations. A company somewhere else sees that country's set.",
                     "Đúng những biểu mẫu mà <b>quốc gia</b> của công ty bạn có, không hơn. Quốc gia của công ty đang hoạt động mới chọn ra các ô biểu mẫu, chứ không phải những gì Payobook có thể tạo ra. Một công ty Việt Nam thấy các mẫu BHXH và các tờ khai biến động lao động. Công ty ở nơi khác thấy bộ biểu mẫu của quốc gia đó.") },
      { k: "steps", v: [
        { t: B("Choose the month — the period control here is a month, not a date range", "Chọn tháng — ô kỳ ở đây là một tháng, không phải một khoảng ngày"), a: "gr-head" },
        { t: B("Check every run in that month has reached Done before generating anything — on Pay Run › Runs, not here", "Kiểm tra mọi đợt lương của tháng đó đã đạt Hoàn tất trước khi kết xuất bất cứ gì — ở Đợt lương › Các đợt lương, không phải ở đây") },
        { t: B("Generate the tile you need — it opens the company's existing wizard, prefilled", "Kết xuất biểu mẫu bạn cần — nó mở đúng trình hướng dẫn sẵn có của công ty, đã điền sẵn"), a: "gr-grid" },
      ] },
      { k: "warn", v: B("A filing built from a month whose runs are not all done is short by however many payslips are still moving. The authority will notice that, not Payobook.",
                        "Một báo cáo lập từ tháng mà các đợt lương chưa hoàn tất hết sẽ thiếu đúng bằng số phiếu lương còn đang đi trong quy trình. Bên phát hiện ra sẽ là cơ quan quản lý, không phải Payobook.") },
      { k: "p", v: B("\"Coming soon\" on a country means its payroll module is not INSTALLED here — not that the filings do not exist. Vietnam, Singapore, Thailand, Cambodia and Malaysia are all in the catalogue, and a country's tiles appear as soon as the module holding its wizard is installed. So that message is an installation question for whoever administers the system, not a limit of the product. Either way Payobook prepares the file — it does not submit it for you.",
                     "Dòng \"sắp có\" ở một quốc gia nghĩa là mô-đun tính lương của quốc gia đó chưa được CÀI ở đây — chứ không phải các biểu mẫu không tồn tại. Việt Nam, Singapore, Thái Lan, Campuchia và Malaysia đều có trong danh mục, và biểu mẫu của một quốc gia sẽ xuất hiện ngay khi mô-đun chứa trình lập báo cáo của nó được cài. Vậy nên thông báo đó là câu hỏi về cài đặt dành cho người quản trị hệ thống, không phải giới hạn của sản phẩm. Dù thế nào thì Payobook cũng chỉ lập tệp — chứ không nộp thay bạn.") },
      { k: "src", v: B("The country report catalogue behind this cockpit, and the active company's country.",
                       "Danh mục biểu mẫu theo quốc gia đứng sau màn hình này, và quốc gia của công ty đang hoạt động.") },
    ],
  },

  /* ===========================================================================
     LEARNOS PHASE 4 — THE OBVIOUS QUESTIONS NOBODY HAD WRITTEN.

     The Phase 1 live validation asked the product's most ordinary questions and
     found no entry for any of these six. "How do I run payroll" was the worst
     of them: with no content to match, it scored 40 against `payrollready` on
     one shared word, cleared the screenless floor and was shown under a
     "Grounded in" badge. A badged wrong answer is worse than a miss, so the
     floor was raised too (learn_intent._SCREENLESS_FLOOR) — the two fixes are
     one fix, and neither alone would have been enough.

     Appended rather than interleaved, for the reason the Setup block gives.
     ======================================================================== */
  {
    id: "howrun", screens: "*",
    label: B("How do I run payroll?", "Tôi chạy bảng lương thế nào?"),
    match: ["how do i run payroll", "run a payroll", "start the payroll", "run the month",
            "how do i pay my staff", "how do i pay everyone", "how do i pay people",
            "pay my staff this month", "how do we pay everyone",
            "chay bang luong the nao", "bắt đầu tính lương", "lam sao chay luong",
            "tra luong cho nhan vien the nao", "trả lương cho nhân viên thế nào",
            "lam sao tra luong cho moi nguoi"],
    showMe: ["scenario:sc_payrun", "dash-runpayroll"],
    watch: "sc_payrun",
    try: "sc_payrun",
    practice: "m1",
    simpler: B("Pick who is being paid, add the month's data, press Compute, read what needs a look, and send it for approval. Nobody is paid until the people on its approval route have said yes.",
               "Chọn ai được trả lương, thêm dữ liệu của tháng, bấm Tính, đọc những gì cần xem lại, rồi gửi phê duyệt. Chưa ai được trả tiền cho tới khi những người trên lộ trình phê duyệt đồng ý."),
    blocks: [
      { k: "p", v: B("Everything starts in <b>Pay Run › Run</b>. Everything before Submit for approval is a draft, and a draft has paid nobody.",
                     "Mọi thứ bắt đầu ở <b>Đợt lương › Chạy lương</b>. Mọi thứ trước bước Gửi để phê duyệt đều là bản nháp, và bản nháp thì chưa trả cho ai cả.") },
      { k: "steps", v: [
        { t: B("Pay Run › Run: pick the pay scheme under \"Pay run for\", and check the month", "Đợt lương › Chạy lương: chọn chương trình lương trong \"Đợt lương cho\", và kiểm tra tháng"), a: "pw-scheme" },
        { t: B("If the scheme reads a spreadsheet, load the file and choose Update Payobook or This run only", "Nếu chương trình đọc bảng tính, tải tệp lên và chọn Cập nhật Payobook hoặc Chỉ đợt này"), a: "pw-paymode" },
        { t: B("Compute. This makes one draft payslip per person and does nothing else", "Tính. Bước này tạo mỗi người một phiếu lương nháp, và không làm gì khác"), a: "pw-result" },
        { t: B("Read Need review, then Open Payroll", "Đọc Cần xem xét, rồi Mở bảng lương"), a: "pw-missing" },
        { t: B("On Pay Run › Runs, press Submit for approval on the run's card", "Ở Đợt lương › Các đợt lương, bấm Gửi để phê duyệt trên thẻ của đợt lương"), a: "pk-card-actions" },
      ] },
      { k: "warn", v: B("Computing is not paying. After Submit the run follows its approval route — by default Payroll check, HR lead review, Finance approval — and only a Done run offers Pay & Deliver.",
                        "Tính không phải là chi. Sau khi gửi, đợt lương đi theo lộ trình phê duyệt — mặc định là Kiểm tra bảng lương, Trưởng nhân sự soát xét, Tài chính phê duyệt — và chỉ đợt Hoàn tất mới có Chi trả & gửi phiếu.") },
      { k: "src", v: B("The Run tab's own steps, and the pay run's approval route.",
                       "Các bước của chính tab Chạy lương, và lộ trình phê duyệt của đợt lương.") },
    ],
  },


  {
    id: "firstday", screens: "*",
    label: B("I am new here — where do I start?", "Tôi mới dùng — nên bắt đầu từ đâu?"),
    match: ["where do i start", "i am new", "first day", "getting started", "new to payobook",
            "bat dau tu dau", "tôi mới bắt đầu", "nguoi moi nen lam gi", "show me around"],
    showMe: ["scenario:sc_welcome"],
    watch: "sc_welcome",
    blocks: [
      { k: "p", v: B("Start with the tour, then Home › Pulse. The tour walks the real screens most people use — Pulse, a pay run, the Approvals inbox, the Formula Engine — and presses nothing for you.",
                     "Hãy bắt đầu bằng lượt giới thiệu, rồi tới Trang chủ › Tổng quan. Lượt giới thiệu đi qua các màn hình thật mà nhiều người dùng nhất — Tổng quan, một đợt lương, hộp Phê duyệt, Bộ máy công thức — và không bấm hộ bạn thứ gì.") },
      { k: "steps", v: [
        { t: B("Watch the tour — it starts on Home › Pulse", "Xem lượt giới thiệu — nó bắt đầu ở Trang chủ › Tổng quan"), a: "dash-hero" },
        { t: B("Read the line under your name: the latest pay run and what it is waiting for", "Đọc dòng dưới tên bạn: đợt lương mới nhất và nó đang chờ gì"), a: "dash-hero" },
        { t: B("Open Learn › Lessons and take the first lesson. Nothing in it is real", "Mở Học cùng Payobook › Bài học và làm bài đầu tiên. Không có gì trong đó là thật") },
      ] },
      { k: "ok", v: B("Nothing you read costs anything. The controls that write are the small number the lessons keep naming.",
                      "Đọc thì không mất gì cả. Những nút thực sự ghi dữ liệu chỉ là số ít mà các bài học liên tục gọi tên.") },
      { k: "src", v: B("The lessons in Learn, and the walkthroughs this helper can start.",
                       "Các bài học trong Học cùng Payobook, và những lượt hướng dẫn mà trợ lý này mở được.") },
    ],
  },


  {
    id: "monthloop", screens: ["dashboard", "payruns", "runpayroll"],
    label: B("When in the month do I do each part?", "Trong tháng thì làm phần nào vào lúc nào?"),
    match: ["when do i do this", "payroll calendar", "what order in the month", "monthly cycle",
            "lam vao luc nao trong thang", "lịch chạy lương", "thu tu trong thang"],
    showMe: ["scenario:sc_welcome", "dash-hero"],
    watch: "sc_welcome",
    blocks: [
      { k: "p", v: B("The same loop every month, in four moves. Pay data arrives, the run is computed, the people on its route sign, and the money goes out.",
                     "Vẫn một vòng lặp đó mỗi tháng, gồm bốn nhịp. Dữ liệu lương về, đợt lương được tính, những người trên lộ trình ký, rồi tiền được chi.") },
      { k: "steps", v: [
        { t: B("Pay data — attendance and overtime in, by {{importCutoff}}", "Dữ liệu lương — chấm công và tăng ca, xong trước {{importCutoff}}"), a: "im-cta" },
        { t: B("People — clear anybody who is not payroll-ready before the run", "Nhân sự — xử lý những người chưa sẵn sàng tính lương trước khi chạy"), a: "pe-filters" },
        { t: B("Pay Run › Run, then Submit for approval", "Đợt lương › Chạy lương, rồi Gửi để phê duyệt"), a: "pw-result" },
        { t: B("Approval in Home › Approvals, then Pay & Deliver around {{payDay}}", "Phê duyệt ở Trang chủ › Phê duyệt, rồi Chi trả & gửi phiếu vào khoảng {{payDay}}"), a: "pk-card-actions" },
      ] },
      { k: "warn", v: B("The order is not a preference. Loading data after the run is computed changes nothing on payslips already made, and fixing a person after the run is Done costs a retro line.",
                        "Thứ tự này không phải là sở thích. Tải dữ liệu sau khi đã tính thì không thay đổi gì trên các phiếu lương đã tạo, và sửa cho một người sau khi đợt đã Hoàn tất sẽ tốn một dòng hồi tố.") },
      { k: "src", v: B("The pay run's states, and the company's stated import cut-off and pay day.",
                       "Các trạng thái của đợt lương, và mốc chốt dữ liệu cùng ngày trả lương do công ty khai báo.") },
    ],
  },


  {
    id: "addperson", screens: ["employees", "contracts"],
    label: B("How do I add a new employee?", "Tôi thêm một nhân viên mới thế nào?"),
    match: ["how do i add an employee", "add a new employee", "onboard someone", "hire someone",
            "them nhan vien moi", "tạo hồ sơ nhân viên", "them nguoi vao he thong"],
    showMe: ["pe-head", "ct-roster"],
    blocks: [
      { k: "p", v: B("Add employee, at the top of the Employees screen. It opens a three-step wizard rather than a bare form: the person, then their role, then their contract.",
                     "Nút Thêm nhân viên, ở phía trên màn hình Nhân sự. Nó mở một trình hướng dẫn ba bước thay vì một biểu mẫu trống: thông tin cá nhân, rồi vị trí công việc, rồi hợp đồng.") },
      { k: "p", v: B("The third step is the one payroll depends on. A person with no running contract computes nothing at all, so they simply do not appear in the run.",
                     "Bước thứ ba mới là bước hệ thống lương phụ thuộc vào. Người chưa có hợp đồng đang hiệu lực thì không được tính gì cả, nên đơn giản là họ không xuất hiện trong đợt lương.") },
      { k: "warn", v: B("Bank details are the other half and they are not on that wizard. Somebody with a contract and no account computes perfectly and is still not paid on {{payDay}}.",
                        "Thông tin ngân hàng là nửa còn lại và nó không nằm trong trình hướng dẫn đó. Người có hợp đồng mà chưa có tài khoản vẫn được tính lương hoàn hảo và vẫn không nhận được tiền vào {{payDay}}.") },
      { k: "steps", v: [
        { t: B("Add employee — person, role, contract", "Thêm nhân viên — thông tin cá nhân, vị trí, hợp đồng"), a: "pe-head" },
        { t: B("Check the contract start date against the period you are about to run", "Đối chiếu ngày bắt đầu hợp đồng với kỳ lương bạn sắp chạy"), a: "ct-roster" },
        { t: B("Filter the roster to the people who are not payroll-ready and clear the new name off it", "Lọc danh sách theo những người chưa sẵn sàng tính lương và xử lý cho tên vừa thêm rời khỏi đó"), a: "pe-filters" },
      ] },
      { k: "src", v: B("The Add employee wizard's three steps, and the payroll-ready mark on the roster.",
                       "Ba bước của trình hướng dẫn Thêm nhân viên, và dấu sẵn sàng tính lương trên danh sách.") },
    ],
  },

  {
    id: "getpaid", screens: ["payruns", "payslips", "afterrun"],
    label: B("How does the money actually reach people?", "Tiền thực sự tới tay mọi người bằng cách nào?"),
    match: ["how does the money go out", "how are people actually paid", "make the payment",
            "generate the bank file", "chuyen tien the nao", "chi lương ra sao", "xuat tep ngan hang"],
    showMe: ["pk-card-actions"],
    blocks: [
      { k: "p", v: B("Not from the approval itself. Once a run is Done its card offers <b>Pay &amp; Deliver</b>. That opens Deliver for the run: the bank file ({{bankFileFormat}}), then the payment release, each approved on its own, and the payslips.",
                     "Không phải từ chính việc phê duyệt. Khi đợt lương Hoàn tất, thẻ của nó có <b>Chi trả &amp; gửi phiếu</b>. Nút đó mở Chi trả cho đợt: tệp ngân hàng ({{bankFileFormat}}), rồi lệnh chuyển tiền, mỗi thứ được duyệt riêng, và phiếu lương.") },
      { k: "p", v: B("Before Done the card offers the next step on the road instead, because there is nothing to pay yet. Journals and Payments are the accounting side of the same month, and neither moves money.",
                     "Trước khi Hoàn tất, thẻ chỉ hiện bước tiếp theo trên đường đi, vì chưa có gì để chi. Bút toán và Thanh toán là phần kế toán của cùng tháng đó, và không cái nào chuyển tiền.") },
      { k: "warn", v: B("A row the bank file cannot use is not dropped quietly. It is listed with the reason, and that list is the last chance to catch somebody before {{payDay}}.",
                        "Một dòng mà tệp chi lương không dùng được sẽ không bị bỏ đi âm thầm. Nó được liệt kê kèm lý do, và danh sách đó là cơ hội cuối để phát hiện ra ai đó trước {{payDay}}.") },
      { k: "src", v: B("The buttons a Done pay run offers on its card, and Pay Run › Deliver.",
                       "Các nút mà một đợt lương Hoàn tất hiện trên thẻ của nó, và Đợt lương › Chi trả.") },
    ],
  },


  {
    id: "seeslip", screens: ["payslips", "employees"],
    label: B("How does an employee get their own payslip?", "Nhân viên nhận phiếu lương của mình bằng cách nào?"),
    match: ["how do employees see their payslip", "send payslips to staff", "email the payslips",
            "payslip pdf for the employee", "nhan vien xem phieu luong o dau",
            "gửi phiếu lương cho nhân viên", "gui phieu luong qua email"],
    showMe: ["pk-card-actions", "ps-detail"],
    blocks: [
      { k: "p", v: B("Payobook sends it to them. Each payslip becomes a PDF, protected by a password that belongs to that one person, and it is emailed rather than handed round.",
                     "Payobook gửi tới tận nơi cho họ. Mỗi phiếu lương được kết xuất thành tệp PDF, đặt mật khẩu riêng của đúng người đó, và gửi qua email chứ không chuyền tay.") },
      { k: "p", v: B("It is sent from the run, once the run is Done — not from one payslip at a time. Sending before that would be sending a figure two people have still to sign for.",
                     "Việc gửi thực hiện từ đợt lương, khi đợt đã Hoàn tất — không phải gửi lẻ từng phiếu. Gửi trước lúc đó là gửi đi một con số mà còn hai người nữa phải ký.") },
      { k: "ok", v: B("Every send is logged per payslip, so a delivery that failed is visible and can be sent again on its own. Nobody has to guess who did not receive theirs.",
                      "Mỗi lần gửi đều được ghi nhật ký theo từng phiếu, nên lần gửi hỏng vẫn nhìn thấy được và gửi lại riêng được. Không ai phải đoán xem ai chưa nhận.") },
      { k: "warn", v: B("The password is worked out at send time and is never written down anywhere. If somebody cannot open theirs, the answer is the pattern the company set, not a stored copy.",
                        "Mật khẩu được tính ra ngay lúc gửi và không được ghi lại ở bất cứ đâu. Nếu ai đó không mở được tệp của mình thì câu trả lời nằm ở quy tắc công ty đã đặt, không phải ở một bản lưu nào cả.") },
      { k: "src", v: B("The payslip delivery log on the pay run, and the password rule in the delivery settings.",
                       "Nhật ký gửi phiếu lương trên đợt lương, và quy tắc mật khẩu trong thiết lập gửi phiếu.") },
    ],
  },
  /* ===========================================================================
     LEARN REFRESH step 2 — the approval questions the new inbox raises.
     ======================================================================== */
  {
    id: "whoapproves", screens: ["payruns", "approvals", "runpayroll", "dashboard", "matrix"],
    label: B("Who approves this pay run?", "Ai phê duyệt đợt lương này?"),
    match: ["who approves my pay run", "who approves this run", "who signs off payroll", "approval route",
            "ai duyet dot luong", "ai phê duyệt đợt lương", "lo trinh phe duyet"],
    showMe: ["pk-route", "ai-route"],
    blocks: [
      { k: "p", v: B("Whoever your company named on its <b>approval route</b> for pay runs. It is drawn in Settings › Approvals › Approval Matrix. Payobook starts every company with one: <b>Payroll check</b>, then <b>HR lead review</b>, then <b>Finance approval</b> — your company may have changed it.",
                     "Những người mà công ty bạn ghi trên <b>lộ trình phê duyệt</b> cho đợt lương. Lộ trình được vẽ ở Cài đặt › Phê duyệt › Ma trận phê duyệt. Payobook tạo sẵn cho mọi công ty một lộ trình: <b>Kiểm tra bảng lương</b>, rồi <b>Trưởng nhân sự soát xét</b>, rồi <b>Tài chính phê duyệt</b> — công ty bạn có thể đã thay đổi nó.") },
      { k: "steps", v: [
        { t: B("On Pay Run › Runs, a waiting run's card names its step and person", "Ở Đợt lương › Các đợt lương, thẻ của đợt đang chờ ghi rõ bước và người"), a: "pk-route" },
        { t: B("In Home › Approvals, the request shows every step as a dot", "Ở Trang chủ › Phê duyệt, yêu cầu hiện mỗi bước thành một chấm"), a: "ai-route" },
        { t: B("Open the run itself and one sentence says the whole route and who has it now", "Mở chính đợt lương là có một câu nói cả lộ trình và ai đang giữ nó") },
      ] },
      { k: "src", v: B("The pay run's approval request, and the route published in the Approval Matrix.",
                       "Yêu cầu phê duyệt của đợt lương, và lộ trình được công bố trong Ma trận phê duyệt.") },
    ],
  },
  {
    id: "stuckwaiting", screens: ["payruns", "approvals", "matrix"],
    label: B("Why is my run stuck waiting?", "Vì sao đợt lương của tôi cứ nằm chờ?"),
    match: ["why is my run stuck", "run stuck waiting", "nobody is approving", "approver is away",
            "dot luong bi tac", "vì sao đợt lương cứ chờ", "nguoi duyet vang mat"],
    showMe: ["pk-route", "ai-move"],
    blocks: [
      { k: "p", v: B("Because the person on its current step has not decided yet. The card on Pay Run › Runs names them — start by asking that person.",
                     "Vì người ở bước hiện tại chưa quyết định. Thẻ trên Đợt lương › Các đợt lương ghi tên họ — hãy bắt đầu bằng việc hỏi chính người đó.") },
      { k: "steps", v: [
        { t: B("Read whose step it is on the run's card", "Đọc xem đang ở bước của ai trên thẻ của đợt lương"), a: "pk-route" },
        { t: B("If they are away, whoever looks after the workflow can Move it to somebody else, with a reason", "Nếu họ vắng mặt, người phụ trách luồng phê duyệt có thể Chuyển cho người khác, kèm lý do"), a: "ai-move" },
        { t: B("If it was sent in too early, the person who sent it can Withdraw it — the run goes back to Draft", "Nếu đã gửi quá sớm, người gửi có thể Thu hồi — đợt lương quay về Nháp"), a: "ai-withdraw" },
      ] },
      { k: "warn", v: B("A run that says \"stuck\" has a step that found nobody to ask. That is a route to fix in the Approval Matrix, not a person to chase.",
                        "Một đợt ghi \"bị tắc\" là có một bước không tìm được ai để hỏi. Đó là lộ trình cần sửa trong Ma trận phê duyệt, không phải một người cần giục.") },
      { k: "src", v: B("The run's approval request: its current step, who holds it, and the inbox's Move and Withdraw.",
                       "Yêu cầu phê duyệt của đợt lương: bước hiện tại, ai đang giữ, và các nút Chuyển và Thu hồi trong hộp phê duyệt.") },
    ],
  },
  {
    id: "sentbackvsturneddown", screens: ["approvals", "payruns"],
    label: B("Sent back or turned down — what is the difference?", "Trả lại hay từ chối — khác nhau thế nào?"),
    match: ["sent back vs turned down", "difference between send back and turn down", "send it back or turn it down",
            "tra lai hay tu choi", "trả lại khác từ chối"],
    showMe: ["ai-sendback", "ai-turndown"],
    blocks: [
      { k: "p", v: B("<b>Send it back</b> means \"change this and ask again\". The run returns to Draft, its payslips become editable, and your note sits on its card. Sent in again, it starts the route from the first step.",
                     "<b>Trả lại</b> nghĩa là \"sửa điều này rồi xin lại\". Đợt lương quay về Nháp, các phiếu lương sửa được, và ghi chú của bạn nằm trên thẻ của nó. Khi gửi lại, nó đi lại lộ trình từ bước đầu tiên.") },
      { k: "p", v: B("<b>Turn it down</b> means \"no\". The request ends, and the run is Rejected with every payslip cancelled. It does not come back; a new run has to be made.",
                     "<b>Từ chối</b> nghĩa là \"không\". Yêu cầu kết thúc, và đợt lương chuyển sang Đã từ chối với mọi phiếu lương bị huỷ. Nó không quay lại; phải tạo một đợt mới.") },
      { k: "ok", v: B("When a correction would be enough, send it back. Turn it down only when the run should not be paid at all.",
                      "Khi chỉ cần sửa là đủ, hãy trả lại. Chỉ từ chối khi đợt lương hoàn toàn không nên được chi.") },
      { k: "src", v: B("The inbox's decisions, and what each does to the pay run.",
                       "Các quyết định trong hộp phê duyệt, và tác động của mỗi quyết định lên đợt lương.") },
    ],
  },
  {
    id: "thisrunonly", screens: ["import", "runpayroll", "importwizard"],
    label: B("Update Payobook or This run only?", "Cập nhật Payobook hay Chỉ đợt này?"),
    match: ["update payobook or this run only", "this run only", "one off bonus", "should values be saved",
            "chi dot nay", "chỉ đợt này", "cap nhat payobook"],
    showMe: ["pw-paymode"],
    blocks: [
      { k: "p", v: B("<b>Update Payobook</b> saves the file's values onto employee and contract records and uses them from now on. <b>This run only</b> uses them once, for this run, and changes nothing in Payobook — the batch then says \"This run only — no records were updated\".",
                     "<b>Cập nhật Payobook</b> lưu các giá trị trong tệp vào hồ sơ nhân viên và hợp đồng, và dùng chúng từ nay về sau. <b>Chỉ đợt này</b> dùng chúng một lần, cho đợt này, và không thay đổi gì trong Payobook — đợt nhập khi đó ghi \"Chỉ đợt này — không hồ sơ nào được cập nhật\".") },
      { k: "ok", v: B("A one-off bonus or a correction: This run only. A new allowance everyone keeps getting: Update Payobook.",
                      "Một khoản thưởng một lần hoặc một lần sửa: Chỉ đợt này. Một khoản phụ cấp mới mà mọi người sẽ tiếp tục nhận: Cập nhật Payobook.") },
      { k: "src", v: B("The Pay data step of Pay Run › Run, and the import batch.",
                       "Bước Dữ liệu lương của Đợt lương › Chạy lương, và đợt nhập liệu.") },
    ],
  },

  /* -- Payroll setup (LEARN REFRESH step 3) -------------------------------- */
  {
    id: "newscheme", screens: ["blueprint", "blueprint_rules", "formula", "hub_settings", "schemes"],
    label: B("How do I set up a new pay scheme?", "Làm sao để thiết lập một chương trình lương mới?"),
    match: ["set up a new pay scheme", "new pay scheme", "create a pay scheme", "new configuration", "guided setup",
            "thiet lap chuong trinh luong", "tạo chương trình lương mới", "cau hinh moi"],
    showMe: ["bp-rail", "bp-country"],
    watch: "sc_blueprint",
    try: "sc_blueprint",
    blocks: [
      { k: "p", v: B("Settings › Guided setup › <b>New configuration</b>. Six steps build one scheme, with a sample person's pay beside you the whole way.",
                     "Cài đặt › Thiết lập có hướng dẫn › <b>Cấu hình mới</b>. Sáu bước dựng một chương trình lương, luôn có lương của một người mẫu bên cạnh.") },
      { k: "steps", v: [
        { t: B("Start: name it, pick the country (it decides the money) and a starting point", "Bắt đầu: đặt tên, chọn quốc gia (nó quyết định đồng tiền) và một điểm bắt đầu"), a: "bp-identity" },
        { t: B("Pay rules: each component as a sentence — watch the take-home figure move", "Quy tắc lương: mỗi thành phần là một câu — xem con số thực nhận thay đổi"), a: "bp-pay" },
        { t: B("Connect, Outputs and Test: sources, every formula, and the awkward cases", "Kết nối, Đầu ra và Kiểm thử: nguồn dữ liệu, mọi công thức, và các trường hợp khó") },
        { t: B("Finish: the setup is complete — putting it live is a separate step", "Hoàn thành: việc thiết lập đã xong — đưa vào dùng là một bước riêng"), a: "bp-foot" },
      ] },
      { k: "warn", v: B("Nothing is created until the first Continue. Finish does not put the scheme live; that is a proposal of its own, and may need approval.",
                        "Chưa có gì được tạo cho tới lần Tiếp tục đầu tiên. Hoàn thành không đưa chương trình vào dùng; đó là một đề xuất riêng, và có thể cần phê duyệt.") },
      { k: "src", v: B("The guided setup (Settings › Guided setup › New configuration).",
                       "Phần thiết lập có hướng dẫn (Cài đặt › Thiết lập có hướng dẫn › Cấu hình mới).") },
    ],
  },
  {
    id: "wherefrom", screens: ["mapping", "mapping_sheet", "treatment", "payslips", "records", "formula", "hub_mapping"],
    label: B("Where does this number come from?", "Con số này đến từ đâu?"),
    match: ["where does this number come from", "where does the value come from", "which source", "not fed",
            "con so nay den tu dau", "giá trị lấy từ đâu", "nguon du lieu"],
    showMe: ["mp-lanes", "mp-story"],
    watch: "sc_mapjourney",
    try: "sc_mapjourney",
    blocks: [
      { k: "p", v: B("From one of the scheme's sources: a connected system, a spreadsheet column, or Payobook's own records. Settings › Integrations › <b>Mapping</b> draws them on the <b>Journey</b> tab, lane by lane, into the scheme.",
                     "Từ một trong các nguồn của chương trình lương: một hệ thống đã kết nối, một cột bảng tính, hoặc chính hồ sơ trong Payobook. Cài đặt › Tích hợp › <b>Ánh xạ</b> vẽ chúng trên tab <b>Hành trình</b>, từng làn một, vào chương trình lương.") },
      { k: "steps", v: [
        { t: B("Check the header: FROM which source, TO which scheme", "Xem phần đầu: TỪ nguồn nào, ĐẾN chương trình lương nào"), a: "mp-story" },
        { t: B("Find the component in the Scheme lane and follow its wire back", "Tìm thành phần ở làn Chương trình lương và lần theo dây nối ngược về"), a: "mp-lanes" },
        { t: B("A component marked not fed is computed as empty", "Thành phần ghi chưa có nguồn sẽ được tính là trống") },
      ] },
      { k: "ok", v: B("Two sources on one component? They are read in order, and a lower one only fills a box the higher one left empty.",
                      "Hai nguồn trên cùng một thành phần? Chúng được đọc theo thứ tự, và nguồn thấp hơn chỉ điền vào ô mà nguồn cao hơn để trống.") },
      { k: "src", v: B("Mapping, Journey tab, for the scheme in the header.",
                       "Ánh xạ, tab Hành trình, của chương trình lương ghi ở phần đầu.") },
    ],
  },
  {
    id: "notaddup", screens: ["treatment", "mapping", "payruns", "payslips", "hub_mapping"],
    label: B("Why don't my figures add up?", "Vì sao số liệu của tôi không khớp?"),
    match: ["figures do not add up", "these figures do not add up", "deductions bigger than gross", "net does not match",
            "so lieu khong khop", "số liệu không khớp", "khau tru lon hon tong thu nhap"],
    showMe: ["tr-table", "tr-filters"],
    watch: "sc_treatment",
    try: "sc_treatment",
    blocks: [
      { k: "p", v: B("Almost always a component is treated as the wrong thing: a working figure counted as pay, or a total counted twice. The pay run says so in a line across its top, with the gap.",
                     "Gần như luôn là một thành phần bị xử lý sai: một con số trung gian bị tính như lương, hoặc một khoản tổng bị tính hai lần. Đợt lương báo điều đó bằng một dòng ở phía trên, kèm khoản chênh.") },
      { k: "steps", v: [
        { t: B("Open Mapping › Component treatment for that scheme", "Mở Ánh xạ › Xử lý thành phần của chương trình đó"), a: "tr-head" },
        { t: B("Clear Needs your answer and Type says otherwise first", "Xử lý Cần câu trả lời của bạn và Loại giá trị nói khác trước"), a: "tr-filters" },
        { t: B("Check each pay role; tick Subtotal on a line whose parts are already added", "Kiểm tra từng vai trò trong lương; đánh dấu Tổng phụ cho dòng mà các phần của nó đã được cộng"), a: "tr-table" },
        { t: B("Save, then recompute the pay run", "Lưu, rồi tính lại đợt lương") },
      ] },
      { k: "warn", v: B("Saving never rewrites a payslip. Until the run is recomputed, it still shows the old figures.",
                        "Lưu không bao giờ viết lại phiếu lương. Cho tới khi đợt lương được tính lại, nó vẫn hiện số liệu cũ.") },
      { k: "src", v: B("The pay run's balance check, and the scheme's Component treatment board.",
                       "Phép kiểm tra cân đối của đợt lương, và bảng Xử lý thành phần của chương trình lương.") },
    ],
  },
  {
    id: "changeroute", screens: ["matrix", "matrix_builder", "approvals", "payruns", "hub_settings"],
    label: B("How do I change who approves something?", "Làm sao để đổi người phê duyệt một việc?"),
    match: ["change an approval route", "change who approves", "add an approver", "remove an approval step", "no approval needed",
            "doi lo trinh phe duyet", "đổi người phê duyệt", "them nguoi phe duyet"],
    showMe: ["am-table", "am-hero"],
    watch: "sc_matrix",
    try: "sc_matrix",
    blocks: [
      { k: "p", v: B("In Settings › Approvals › <b>Approval Matrix</b>. Each process has one route. Open its row, change the steps in the builder, and publish.",
                     "Ở Cài đặt › Phê duyệt › <b>Ma trận phê duyệt</b>. Mỗi quy trình có một lộ trình. Mở dòng của nó, sửa các bước trong phần dựng lộ trình, rồi ban hành.") },
      { k: "steps", v: [
        { t: B("Find the process in the table and open it", "Tìm quy trình trong bảng và mở nó"), a: "am-table" },
        { t: B("Change the steps: Review, Final approval, Joint approval, Only when… an amount", "Sửa các bước: Xem lại, Phê duyệt cuối, Cùng phê duyệt, Chỉ khi… trên một mức tiền") },
        { t: B("Try an example, then Publish this route", "Thử một ví dụ, rồi Ban hành lộ trình này") },
      ] },
      { k: "warn", v: B("Publishing affects new requests only. Requests already on their way finish the route they started on.",
                        "Ban hành chỉ áp cho yêu cầu mới. Những yêu cầu đang trên đường sẽ đi hết lộ trình chúng đã bắt đầu.") },
      { k: "ok", v: B("Someone away? Use People & backups › Arrange cover instead of editing the route.",
                      "Có người vắng mặt? Hãy dùng Con người & người thay thế › Sắp xếp người trực thay thay vì sửa lộ trình.") },
      { k: "src", v: B("The Approval Matrix and its route builder.",
                       "Ma trận phê duyệt và phần dựng lộ trình.") },
    ],
  },
  {
    id: "bulkupdate", screens: ["records", "employees", "mapping", "hub_people"],
    label: B("How do I change many employees at once?", "Làm sao để sửa nhiều nhân viên cùng lúc?"),
    match: ["change many employees at once", "bulk update", "update many records", "raise for everyone", "change bank details for many",
            "cap nhat hang loat", "sửa nhiều nhân viên cùng lúc", "records desk"],
    showMe: ["rd-review", "rd-file"],
    watch: "sc_records",
    try: "sc_records",
    blocks: [
      { k: "p", v: B("People › <b>Records</b> — the Records Desk. It offers the employee, contract and bank fields your pay scheme reads, for one person or hundreds.",
                     "Con người › <b>Hồ sơ</b> — Records Desk. Nó đưa ra các trường nhân viên, hợp đồng và ngân hàng mà chương trình lương của bạn đọc, cho một người hay hàng trăm người.") },
      { k: "steps", v: [
        { t: B("Pick the scheme, then who and which fields", "Chọn chương trình lương, rồi chọn ai và trường nào"), a: "rd-scheme" },
        { t: B("Type into the grid, or Export with data, edit, and Import a file", "Gõ vào lưới, hoặc Xuất kèm dữ liệu, sửa, rồi Nhập một tệp"), a: "rd-file" },
        { t: B("Open Review, read every change, then Apply", "Mở Xem lại, đọc từng thay đổi, rồi Áp dụng"), a: "rd-review" },
      ] },
      { k: "warn", v: B("When your company has a route for bulk changes, Apply says Sent for approval and nothing changes until it is approved.",
                        "Khi công ty bạn có lộ trình cho thay đổi hàng loạt, Áp dụng sẽ báo Đã gửi phê duyệt và chưa có gì thay đổi cho tới khi được duyệt.") },
      { k: "ok", v: B("Every apply can be undone from History.", "Mỗi lần áp dụng đều hoàn tác được trong Lịch sử.") },
      { k: "src", v: B("The Records Desk (People › Records).", "Records Desk (Con người › Hồ sơ).") },
    ],
  },
  {
    id: "currency", screens: ["schemes", "blueprint", "runpayroll", "explorer", "hub_settings"],
    label: B("How do I pay people in another currency?", "Làm sao để trả lương bằng một đồng tiền khác?"),
    match: ["pay people in another currency", "another currency", "two currencies", "exchange rate", "group currency", "pay in dollars",
            "tra luong bang ngoai te", "đồng tiền khác", "ty gia"],
    showMe: ["gp-rates", "ex-money"],
    watch: "sc_schemes",
    try: "sc_schemes",
    blocks: [
      { k: "p", v: B("Give those people a pay scheme of their own, for their country. A scheme pays in its country's money, and its pay runs stay in that money.",
                     "Hãy cho những người đó một chương trình lương riêng, theo quốc gia của họ. Một chương trình trả lương bằng đồng tiền của quốc gia nó, và các đợt lương của nó giữ nguyên đồng tiền đó.") },
      { k: "steps", v: [
        { t: B("New configuration: pick the country — the chip says what it pays in", "Cấu hình mới: chọn quốc gia — nhãn cho biết trả bằng đồng tiền gì"), a: "bp-country" },
        { t: B("Run it as its own pay run: one scheme, one currency", "Chạy nó thành một đợt lương riêng: một chương trình, một đồng tiền"), a: "pw-scheme" },
        { t: B("For group totals, set how exchange rates are picked in Settings › Group", "Để có tổng tập đoàn, đặt cách chọn tỷ giá ở Cài đặt › Tập đoàn"), a: "gp-rates" },
      ] },
      { k: "warn", v: B("Nothing is stored converted. A month with no exchange rate keeps its own money and is left out of the group total, with the reason shown.",
                        "Không có gì được lưu ở dạng đã quy đổi. Tháng nào chưa có tỷ giá sẽ giữ đồng tiền của nó và bị để ra ngoài tổng tập đoàn, kèm lý do.") },
      { k: "src", v: B("The pay scheme's country, Settings › Group, and Insights › Explorer.",
                       "Quốc gia của chương trình lương, Cài đặt › Tập đoàn, và Phân tích › Khám phá dữ liệu.") },
    ],
  },

  /* -- The wider app (LEARN REFRESH step 4): the top question of each area. */
  {
    id: "bandcheck", screens: ["paybands", "payreview", "hub_people"],
    label: B("Is anyone paid outside their pay band?", "Có ai được trả ngoài khoảng lương không?"),
    match: ["paid below the band", "outside their band", "pay band", "salary range", "compa ratio",
            "tra duoi khoang luong", "khoảng lương", "ngoai khoang luong"],
    showMe: ["pp-health", "pp-band-picture"],
    watch: "sc_paybands",
    blocks: [
      { k: "p", v: B("People › Pay › <b>Bands</b>. The band picture puts every person in their band as a dot, and <b>Worth knowing</b> names who is below or above.",
                     "Con người › Lương › <b>Khoảng lương</b>. Bức tranh khoảng lương đặt mỗi người vào khoảng của họ thành một chấm, và <b>Đáng biết</b> nêu tên ai đang ở dưới hoặc ở trên.") },
      { k: "steps", v: [
        { t: B("Read Worth knowing: Paid below the band, Paid above the band", "Đọc Đáng biết: Được trả dưới khoảng lương, Được trả trên khoảng lương"), a: "pp-health" },
        { t: B("Find their dot on the band picture", "Tìm chấm của họ trên bức tranh khoảng lương"), a: "pp-band-picture" },
        { t: B("Raise them in the next pay review, or with a pay change", "Nâng lương cho họ trong đợt xét lương tới, hoặc bằng một thay đổi lương") },
      ] },
      { k: "warn", v: B("Moving the band changes the picture, never anybody's pay.", "Dời khoảng lương chỉ đổi bức tranh, không bao giờ đổi lương của ai.") },
      { k: "src", v: B("People › Pay, Bands tab.", "Con người › Lương, tab Khoảng lương.") },
    ],
  },
  {
    id: "whosignsreview", screens: ["payreview", "paybands", "approvals", "hub_people"],
    label: B("Who has to sign a pay review?", "Ai phải phê duyệt một đợt xét lương?"),
    match: ["who signs a pay review", "pay review approval", "approve the pay review", "send the review for approval",
            "ai duyet xet luong", "phê duyệt đợt xét lương", "duyet dot xet luong"],
    showMe: ["pp-stepper", "pp-review-actions"],
    watch: "sc_payreview",
    try: "sc_payreview",
    blocks: [
      { k: "p", v: B("A review goes Being written → With HR → With finance → With the CEO → Approved. Each can approve it or send it back with a reason.",
                     "Một đợt xét lương đi Đang soạn → Đang ở nhân sự → Đang ở tài chính → Đang ở tổng giám đốc → Đã duyệt. Mỗi người có thể duyệt hoặc trả lại kèm lý do.") },
      { k: "steps", v: [
        { t: B("Clear What stops approval", "Xử lý Điều gì chặn duyệt"), a: "pp-stops" },
        { t: B("Send for approval", "Gửi duyệt"), a: "pp-review-actions" },
        { t: B("When it is Approved, press Apply", "Khi Đã duyệt, bấm Áp dụng") },
      ] },
      { k: "warn", v: B("Approved is not paid. Nothing reaches anyone's record until Apply.", "Đã duyệt chưa phải là đã trả. Chưa có gì vào hồ sơ của ai cho tới khi Áp dụng.") },
      { k: "src", v: B("People › Pay › Review, the review's stepper.", "Con người › Lương › Xét lương, thanh các bước của đợt xét lương.") },
    ],
  },
  {
    id: "whatif", screens: ["decisionroom", "hub_people"],
    label: B("What would next year cost if we hired or gave a rise?", "Năm sau sẽ tốn bao nhiêu nếu tuyển thêm hoặc tăng lương?"),
    match: ["what would next year cost", "plan next year", "what if we hire", "cost of a rise", "decision room",
            "ke hoach nam sau", "phòng quyết định", "chi phi tang luong"],
    showMe: ["dr-levers", "dr-exact"],
    watch: "sc_decisionroom",
    blocks: [
      { k: "p", v: B("People › <b>Plan</b> — the Decision Room. Move the levers and every result follows; nothing there changes payroll.",
                     "Con người › <b>Kế hoạch</b> — Phòng quyết định. Xoay các cần gạt và mọi kết quả thay đổi theo; không có gì ở đó thay đổi bảng lương.") },
      { k: "steps", v: [
        { t: B("Pick a preset, then move the levers", "Chọn một phương án có sẵn, rồi xoay các cần gạt"), a: "dr-presets" },
        { t: B("Save plan", "Lưu kế hoạch"), a: "dr-head" },
        { t: B("Press Exact cost to run it through the real pay scheme", "Bấm Chi phí chính xác để chạy qua chương trình lương thật"), a: "dr-exact" },
      ] },
      { k: "src", v: B("The Decision Room (People › Plan).", "Phòng quyết định (Con người › Kế hoạch).") },
    ],
  },
  {
    id: "raisehire", screens: ["hiring", "hiring_request", "hub_lifecycle"],
    label: B("How do I raise a hiring request?", "Làm sao để đề xuất tuyển dụng?"),
    match: ["raise a hiring request", "hire someone new", "new job opening", "request a new hire",
            "de xuat tuyen dung", "tuyển thêm người", "tuyen nguoi moi"],
    showMe: ["hi-raise", "hi-steps"],
    watch: "sc_hiring",
    try: "sc_hiring",
    blocks: [
      { k: "p", v: B("Lifecycle › <b>Hiring</b> › <b>Raise a hiring request</b>. A short wizard takes the role, what they will do, the interview plan and the budget.",
                     "Vòng đời nhân sự › <b>Tuyển dụng</b> › <b>Đề xuất tuyển dụng</b>. Một trình hướng dẫn ngắn nhận vị trí, công việc, kế hoạch phỏng vấn và ngân sách.") },
      { k: "steps", v: [
        { t: B("Press Raise a hiring request", "Bấm Đề xuất tuyển dụng"), a: "hi-raise" },
        { t: B("Fill The role, Responsibilities, Interview plan, Budget & review", "Điền bốn tab: The role, Responsibilities, Interview plan, Budget & review"), a: "hi-wizard" },
        { t: B("Send it for approval: manager, HR lead — Finance only if over budget", "Gửi phê duyệt: quản lý, trưởng nhân sự — Tài chính chỉ khi vượt ngân sách") },
      ] },
      { k: "ok", v: B("The role stays at step 1 until it is signed off, so nothing is advertised early.",
                      "Vị trí nằm ở bước 1 cho tới khi được duyệt, nên không có gì được đăng tin sớm.") },
      { k: "src", v: B("Lifecycle › Hiring and its request wizard.", "Vòng đời nhân sự › Tuyển dụng và trình đề xuất tuyển dụng.") },
    ],
  },
  {
    id: "newjoiner", screens: ["joiners", "hiring", "hub_lifecycle"],
    label: B("How do I get ready for someone starting?", "Làm sao để chuẩn bị cho người sắp vào làm?"),
    match: ["someone starting next week", "prepare for a new joiner", "first day checklist", "choose a buddy",
            "chuan bi nhan vien moi", "người sắp vào làm", "nguoi dong hanh"],
    showMe: ["nj-list", "nj-drawer"],
    watch: "sc_joiners",
    blocks: [
      { k: "p", v: B("Lifecycle › <b>New joiners</b>. Each person's card, their buddy, and what is still to do before day one.",
                     "Vòng đời nhân sự › <b>Nhân viên mới</b>. Thẻ của mỗi người, người đồng hành, và những gì còn phải làm trước ngày đầu.") },
      { k: "steps", v: [
        { t: B("Give everyone a buddy — clear Still without a buddy", "Chọn người đồng hành cho mọi người — xử lý Chưa có người đồng hành"), a: "nj-numbers" },
        { t: B("Open their card and finish Still to do", "Mở thẻ của họ và làm xong phần Còn phải làm"), a: "nj-drawer" },
        { t: B("Make sure the bank account is on file before the pay run", "Đảm bảo đã có tài khoản ngân hàng trước đợt lương") },
      ] },
      { k: "src", v: B("Lifecycle › New joiners.", "Vòng đời nhân sự › Nhân viên mới.") },
    ],
  },
  {
    id: "leaver", screens: ["exits", "fullfinal", "hub_lifecycle"],
    label: B("Someone is leaving — what do I do?", "Có người nghỉ việc — tôi phải làm gì?"),
    match: ["someone is leaving", "handle a resignation", "exit checklist", "clearance", "last day",
            "nhan vien nghi viec", "người nghỉ việc", "ban giao khi nghi"],
    showMe: ["ex2-clearance", "ex2-settle"],
    watch: "sc_exits",
    try: "sc_exits",
    blocks: [
      { k: "p", v: B("Lifecycle › <b>Exits</b>. The leaver works their notice, IT, HR, Finance and Admin sign them off, and the final settlement waits for all four.",
                     "Vòng đời nhân sự › <b>Nghỉ việc</b>. Người nghỉ làm hết thời gian báo trước, IT, Nhân sự, Tài chính và Quản trị viên xác nhận bàn giao, và quyết toán chờ đủ cả bốn.") },
      { k: "steps", v: [
        { t: B("Watch Clearances still open", "Theo dõi Xác nhận bàn giao còn mở"), a: "ex2-numbers" },
        { t: B("Chase the desk that has not signed", "Nhắc phòng ban chưa ký"), a: "ex2-clearance" },
        { t: B("Close settlement, then pay it from Pay Run › Settle", "Chốt quyết toán, rồi chi từ Đợt lương › Quyết toán"), a: "ex2-settle" },
      ] },
      { k: "warn", v: B("Take them out of the monthly pay run for the same month, or they are paid twice.",
                        "Hãy đưa họ ra khỏi đợt lương tháng của cùng tháng, nếu không họ được trả hai lần.") },
      { k: "src", v: B("Lifecycle › Exits, and Pay Run › Settle.", "Vòng đời nhân sự › Nghỉ việc, và Đợt lương › Quyết toán.") },
    ],
  },
  {
    id: "endtrial", screens: ["probation", "hub_lifecycle"],
    label: B("How do I confirm someone after probation?", "Làm sao để xác nhận chính thức sau thử việc?"),
    match: ["confirm after probation", "end of probation", "trial ends", "extend probation",
            "xac nhan sau thu viec", "hết thử việc", "keo dai thu viec"],
    showMe: ["pr-verdict", "pr-numbers"],
    watch: "sc_probation",
    blocks: [
      { k: "p", v: B("Lifecycle › <b>Probation</b>. Colleagues are asked, the manager decides, HR and leadership review, then the outcome is shared.",
                     "Vòng đời nhân sự › <b>Thử việc</b>. Đồng nghiệp được hỏi, quản lý quyết định, nhân sự và lãnh đạo xem xét, rồi kết quả được thông báo.") },
      { k: "steps", v: [
        { t: B("Check Ending within a week", "Xem Kết thúc trong vòng một tuần"), a: "pr-numbers" },
        { t: B("Open the card: colleagues asked, and who has answered", "Mở thẻ: đồng nghiệp được hỏi, và ai đã trả lời"), a: "pr-peers" },
        { t: B("Decide: Confirm them, Extend the trial, or Do not confirm", "Quyết định: Xác nhận chính thức, Kéo dài thử việc, hoặc Không xác nhận"), a: "pr-verdict" },
      ] },
      { k: "warn", v: B("A trial that ends with nobody deciding becomes a yes by default.", "Thử việc kết thúc mà không ai quyết định sẽ mặc nhiên thành đồng ý.") },
      { k: "src", v: B("Lifecycle › Probation.", "Vòng đời nhân sự › Thử việc.") },
    ],
  },
  {
    id: "approveot", screens: ["wftoday", "wftime", "wftimeoff", "wfovertime", "wfclose", "hub_workforce"],
    label: B("How do I approve overtime?", "Làm sao để duyệt tăng ca?"),
    match: ["approve overtime", "overtime waiting", "clean overtime", "overtime limit",
            "duyet tang ca", "tăng ca chờ duyệt", "gioi han tang ca"],
    showMe: ["wf-clean", "wf-ot-queue"],
    watch: "sc_wftime",
    blocks: [
      { k: "p", v: B("Two places. The <b>Needs you</b> panel approves all clean overtime in one press. Workforce › <b>Overtime</b> holds the queue for the rest.",
                     "Hai nơi. Khung <b>Cần bạn</b> duyệt tất cả tăng ca sạch trong một lần bấm. Lực lượng lao động › <b>Tăng ca</b> giữ hàng chờ cho phần còn lại.") },
      { k: "steps", v: [
        { t: B("Approve all N clean from the Needs you panel", "Phê duyệt tất cả N sạch từ khung Cần bạn"), a: "wf-clean" },
        { t: B("Open the rest in Overtime's approval queue", "Mở phần còn lại trong hàng chờ duyệt của tab Tăng ca"), a: "wf-ot-queue" },
        { t: B("Read any near-the-limit mark before you approve", "Đọc dấu gần giới hạn trước khi duyệt"), a: "wf-ot-rules" },
      ] },
      { k: "src", v: B("Workforce › Today's Needs you panel and Workforce › Overtime.", "Khung Cần bạn ở Lực lượng lao động › Hôm nay và Lực lượng lao động › Tăng ca.") },
    ],
  },
  {
    id: "lockweek", screens: ["wfclose", "wftoday", "hub_workforce"],
    label: B("How do I lock the week?", "Làm sao để khoá tuần?"),
    match: ["lock the week", "close the week", "send the week to payroll", "lock week",
            "khoa tuan", "chốt tuần", "gui tuan vao bang luong"],
    showMe: ["wf-close-flags", "wf-close-lock"],
    watch: "sc_wfclose",
    try: "sc_wfclose",
    blocks: [
      { k: "p", v: B("Workforce › <b>Close</b>. Clear every flag, read the payroll handoff, then <b>Lock week & send to payroll</b>.",
                     "Lực lượng lao động › <b>Chốt kỳ</b>. Xử lý mọi cờ cảnh báo, đọc phần chuyển giao tiền lương, rồi <b>Khóa tuần và gửi vào bảng lương</b>.") },
      { k: "steps", v: [
        { t: B("Fix each wrong day, or Approve as-is what really happened", "Điều chỉnh từng ngày sai, hoặc Phê duyệt nguyên trạng những gì thật sự đã xảy ra"), a: "wf-close-flags" },
        { t: B("Read Regular hours, Overtime, Bonus hours", "Đọc Giờ thông thường, Tăng ca, Giờ thưởng"), a: "wf-close-handoff" },
        { t: B("Lock week & send to payroll", "Khóa tuần và gửi vào bảng lương"), a: "wf-close-lock" },
      ] },
      { k: "warn", v: B("The button stays grey until every flag is answered, and only an attendance or payroll manager can press it.",
                        "Nút giữ màu xám cho tới khi mọi cờ được trả lời, và chỉ quản lý chấm công hoặc quản lý lương mới bấm được.") },
      { k: "src", v: B("Workforce › Close.", "Lực lượng lao động › Chốt kỳ.") },
    ],
  },
  {
    id: "delegate", screens: ["access", "hub_settings"],
    label: B("How do I give someone my access while I'm away?", "Làm sao để giao quyền của tôi cho người khác khi tôi vắng mặt?"),
    match: ["give someone access while i'm away", "hand my access over", "delegate my access", "cover for me while away",
            "uy quyen khi vang mat", "bàn giao quyền", "giao quyen cho nguoi khac"],
    showMe: ["ac-handover", "ac-tabs"],
    watch: "sc_access",
    blocks: [
      { k: "p", v: B("Settings › <b>Access & delegation</b> › <b>Hand my access over</b>: who, what and until when. It ends by itself the morning after the end date.",
                     "Cài đặt › <b>Quyền truy cập & uỷ quyền</b> › <b>Hand my access over</b> (bàn giao quyền của tôi): cho ai, quyền nào và đến khi nào. Nó tự kết thúc vào sáng hôm sau ngày kết thúc.") },
      { k: "steps", v: [
        { t: B("Press Hand my access over", "Bấm Hand my access over"), a: "ac-handover" },
        { t: B("Pick who, what and the end date, then Hand it over", "Chọn cho ai, quyền nào và ngày kết thúc, rồi Hand it over") },
        { t: B("It shows on the Hand-overs tab until it ends", "Nó hiện ở tab Hand-overs cho tới khi kết thúc"), a: "ac-tabs" },
      ] },
      { k: "warn", v: B("Never share your password instead: everything would be recorded as you, and nothing would end it.",
                        "Đừng bao giờ đưa mật khẩu thay vào đó: mọi thứ sẽ được ghi là của bạn, và không gì kết thúc nó.") },
      { k: "src", v: B("Settings › Access & delegation.", "Cài đặt › Quyền truy cập & uỷ quyền.") },
    ],
  },
  {
    id: "fileinsurance", screens: ["govreports", "filing_flow", "hub_compliance"],
    label: B("How do I file the monthly insurance report?", "Làm sao để nộp báo cáo bảo hiểm hằng tháng?"),
    match: ["file the monthly insurance report", "insurance filing", "generate a filing", "social insurance report",
            "nop bao cao bao hiem", "báo cáo bảo hiểm hằng tháng", "tao ho so"],
    showMe: ["gr-grid", "cp-gen-go"],
    watch: "sc_filings",
    blocks: [
      { k: "p", v: B("Compliance › <b>Filings</b>. Find the insurance filing under Social Insurance, press <b>Generate</b>, check the scope, then Generate the files.",
                     "Tuân thủ › <b>Tờ khai</b>. Tìm báo cáo bảo hiểm trong nhóm Bảo hiểm xã hội, bấm <b>Tạo</b>, kiểm tra phạm vi, rồi Tạo các tệp.") },
      { k: "steps", v: [
        { t: B("Make sure every run for the month is done", "Đảm bảo mọi đợt lương của tháng đã hoàn tất") },
        { t: B("Press Generate on the filing's tile", "Bấm Tạo trên ô của báo cáo"), a: "gr-grid" },
        { t: B("Check company and month on Scope, then Generate", "Kiểm tra công ty và tháng ở Phạm vi, rồi Tạo"), a: "cp-gen-go" },
      ] },
      { k: "warn", v: B("Generate sends nothing. You download the files and submit them yourself.", "Tạo không gửi gì cả. Bạn tải tệp xuống và tự nộp.") },
      { k: "src", v: B("Compliance › Filings and its Generate a filing flow.", "Tuân thủ › Tờ khai và luồng Tạo hồ sơ.") },
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
    ["payslips",
     B("Payslips", "Phiếu lương"),
     B("How many payslip records the compute created for this run — one per person the pay scheme pays in the period.",
       "Số bản ghi phiếu lương mà lần tính đã tạo cho đợt này — mỗi người thuộc chương trình lương trong kỳ một phiếu.")],
    ["computed",
     B("Computed", "Đã tính"),
     B("How many of those payslips the formula configuration evaluated all the way through. A payslip that exists but did not compute has no net figure.",
       "Trong số phiếu đó, bao nhiêu phiếu được cấu hình công thức tính trọn vẹn. Một phiếu có tồn tại nhưng chưa tính xong thì không có số thực nhận.")],
    ["need_review",
     B("Need review", "Cần xem xét"),
     B("Payslips at zero or below, plus people Payobook could not make a payslip for, plus people in the pay data file who are not in Payobook yet. It does not flag a big change on last month — that one is yours to spot.",
       "Các phiếu bằng không hoặc âm, cộng những người Payobook không tạo được phiếu lương, cộng những người có trong tệp dữ liệu lương mà chưa có trong Payobook. Nó không đánh dấu một thay đổi lớn so với tháng trước — việc đó là của bạn.")],
    ["exceptions",
     B("Exceptions", "Ngoại lệ"),
     B("The people the run could not pay, one line each with the reason — for example \"Not employed yet in this period\". A correct reason is not a thing to fix.",
       "Những người đợt lương không trả được, mỗi người một dòng kèm lý do — ví dụ \"Chưa làm việc trong kỳ này\". Một lý do đúng thì không phải thứ cần sửa.")],
  ],


  payruns: [
    ["pay_runs",
     B("Pay runs", "Đợt lương"),
     B("Every run on the board, rejected ones included.",
       "Mọi đợt trên bảng, kể cả các đợt bị từ chối.")],
    ["in_pipeline",
     B("In pipeline", "Đang xử lý"),
     B("Runs in Draft plus runs Waiting for approval — everything not Done and not rejected.",
       "Các đợt ở Nháp cộng các đợt đang Chờ phê duyệt — mọi đợt chưa Hoàn tất và không bị từ chối.")],
    ["awaiting_your_approval",
     B("Awaiting your approval", "Chờ bạn phê duyệt"),
     B("Runs whose approval route is waiting on you right now. This is the only number on the band that is about you; the decision itself happens in Home › Approvals.",
       "Các đợt mà lộ trình phê duyệt đang chờ đúng bạn lúc này. Đây là con số duy nhất trên dải nói về bạn; quyết định diễn ra ở Trang chủ › Phê duyệt.")],
    ["completed",
     B("Completed", "Hoàn tất"),
     B("Runs whose route has said yes at every step. Only these offer Pay & Deliver, and after this a correction is a retro line.",
       "Các đợt mà lộ trình đã đồng ý ở mọi bước. Chỉ những đợt này mới có Chi trả & gửi phiếu, và sau đó mọi hiệu chỉnh là một dòng hồi tố.")],
    ["net_paid",
     B("Net paid (done)", "Đã chi (hoàn tất)"),
     B("The net of Done runs, in the company's own currency only. Runs in another currency are shown in their own money and never added in.",
       "Tổng thực nhận của các đợt Hoàn tất, chỉ tính bằng tiền tệ của công ty. Các đợt bằng loại tiền khác hiện bằng đúng loại tiền đó và không bao giờ cộng vào.")],
  ],


  payslips: [
    ["payslips",
     B("Payslips", "Phiếu lương"),
     B("How many payslips this run contains — one per person paid. If it is not the headcount you expected, the problem is in the run, not on this screen.",
       "Số phiếu lương mà đợt này chứa — mỗi người được trả lương một phiếu. Nếu nó không đúng sĩ số bạn kỳ vọng thì vấn đề nằm ở đợt lương, không phải ở màn hình này.")],
    ["need_review",
     B("Need review", "Cần xem xét"),
     B("Payslips whose take-home pay came out at zero or below. Nothing else — a big change on last month is not counted here.",
       "Các phiếu có thực nhận bằng không hoặc âm. Không gì khác — một thay đổi lớn so với tháng trước không được đếm ở đây.")],
    ["gross_total",
     B("Gross total", "Tổng thu nhập"),
     B("The sum of earnings before any deduction across the run.",
       "Tổng thu nhập trước mọi khoản khấu trừ trên toàn đợt.")],
    ["net_total",
     B("Net total", "Tổng thực nhận"),
     B("The sum of every take-home figure in this run — what will actually leave the bank account.",
       "Tổng của mọi số thực nhận trong đợt này — số tiền thực sự sẽ rời tài khoản ngân hàng.")],
    ["salary_breakdown",
     B("Salary breakdown", "Chi tiết lương"),
     B("Every line of the open payslip with its rule code and amount, in the order the configuration produced them. It is the working behind the net figure.",
       "Từng dòng của phiếu lương đang mở kèm mã quy tắc và số tiền, theo đúng thứ tự cấu hình sinh ra. Đó là phần tính toán đứng sau con số thực nhận.")],
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
     B("Rows loaded", "Dòng đã nạp"),
     B("How many rows the importer read out of the file. If this is not your file's row count, a sheet was cut short.",
       "Số dòng trình nhập liệu đọc được từ tệp. Nếu con số này không bằng số dòng trong tệp thì một trang tính đã bị cắt.")],
    ["matched",
     B("Matched", "Đã khớp"),
     B("Rows tied to an existing employee with no ambiguity.",
       "Các dòng gắn được với một nhân viên đã có, không nhập nhằng.")],
    ["new_employees",
     B("New employees", "Nhân viên mới"),
     B("Rows you chose to create as new people. Committing creates them, so this number is a hiring decision arriving through a spreadsheet.",
       "Các dòng bạn chọn tạo thành người mới. Ghi vào hệ thống sẽ tạo ra họ, nên con số này là một quyết định nhân sự đi vào qua bảng tính.")],
    ["need_attention",
     B("Need attention", "Cần xử lý"),
     B("Rows the importer could not place: no matching employee, a duplicate, or a cell it could not read. Every one is a person.",
       "Các dòng trình nhập liệu không xếp được: không tìm ra nhân viên khớp, bị lặp, hoặc có ô không đọc được. Mỗi dòng là một con người.")],
  ],


  /* LEARN REFRESH step 5: the ledgers' labels as ledger_cockpits.py writes
     them today (English on screen in both languages). */
  fullfinal: [
    ["settlements",
     B("Settlements", "Settlements"),
     B("Every final settlement in scope, whatever its step. Each one is somebody who must ALSO be out of the normal monthly run, or they are paid twice.",
       "Mọi khoản quyết toán trong phạm vi, ở bất kỳ bước nào. Mỗi khoản là một người CŨNG phải được đưa ra khỏi đợt lương tháng thông thường, nếu không họ được trả hai lần.")],
    ["manual",
     B("Manual", "Manual"),
     B("Settlements made by hand rather than created when a month's pay data finished loading. Pressing it narrows the list to them.",
       "Các khoản quyết toán làm bằng tay thay vì được tạo khi dữ liệu lương của một tháng tải xong. Bấm vào để chỉ xem những khoản đó.")],
    ["net_payable",
     B("Net payable", "Net payable"),
     B("Earnings less deductions, added up over the settlements in scope. It sits outside the monthly run's net, so the two never add up to one bank total.",
       "Thu nhập trừ khấu trừ, cộng trên các khoản quyết toán trong phạm vi. Nó nằm ngoài số thực nhận của đợt lương tháng, nên hai con số không bao giờ cộng thành một tổng chuyển khoản.")],
  ],

  proration: [
    ["proration_lines",
     B("Proration lines", "Proration lines"),
     B("One line per part-month amount: a pay change in the middle of the month, or someone here for only part of it. Each is a question an employee is likely to ask.",
       "Mỗi khoản theo phần tháng một dòng: một thay đổi lương giữa tháng, hoặc một người chỉ có mặt một phần tháng. Mỗi dòng là một câu hỏi nhân viên nhiều khả năng sẽ hỏi.")],
    ["total_prorated",
     B("Total prorated", "Total prorated"),
     B("The part-month amounts added up. The days behind each one are in the row's drawer, under Period.",
       "Tổng các khoản theo phần tháng. Số ngày đứng sau từng khoản nằm trong ngăn chi tiết của dòng, mục Period.")],
  ],

  retro: [
    ["retro_lines",
     B("Retro lines", "Retro lines"),
     B("Back-pay lines the pay data load worked out: a pay change dated before this month, compared with what was already paid. Each keeps that month closed.",
       "Các dòng truy lĩnh mà lần tải dữ liệu lương đã tính: một thay đổi lương có hiệu lực trước tháng này, đem so với số đã trả. Mỗi dòng giữ cho tháng đó luôn đóng.")],
    ["total_delta",
     B("Total delta", "Total delta"),
     B("The back pay added to this month. The run's net will be higher than the same people usually cost, so say so before somebody asks about the jump.",
       "Khoản truy lĩnh cộng vào tháng này. Thực nhận của đợt sẽ cao hơn mức những người đó thường tốn, nên hãy nói trước khi có người hỏi về mức tăng.")],
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
     B("The components that read THIS one. It is the reach of a rename or a deletion, written down. Everything listed here would lose an input, and a formula that lost an input does not always fail loudly.",
       "Những thành phần đọc vào chính thành phần NÀY. Đây là phạm vi ảnh hưởng của việc đổi tên hay xoá, đã ghi rõ ra. Mọi thứ liệt kê ở đây sẽ mất một đầu vào, và một công thức mất đầu vào không phải lúc nào cũng báo lỗi rõ ràng.")],
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
     B("Older salary structures still held by this company. They are history rather than configuration: new pay logic belongs in a formula configuration, and these exist so old payslips can still be explained.",
       "Các cấu trúc lương thế hệ cũ mà công ty này còn giữ. Chúng là lịch sử chứ không phải cấu hình: logic lương mới thuộc về cấu hình công thức, còn những cái này tồn tại để phiếu lương cũ vẫn giải thích được.")],
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
     B("Everybody the company currently employs, whether or not they were in the last run. It describes the company rather than the month, so it will read almost the same tomorrow. Notice it when it MOVES. It is not a figure to act on today.",
       "Toàn bộ nhân sự công ty đang có, bất kể họ có nằm trong đợt lương gần nhất hay không. Con số này mô tả cả công ty chứ không mô tả tháng, nên ngày mai đọc lại gần như vẫn thế. Hãy chú ý khi nó THAY ĐỔI. Đây không phải con số để xử lý hôm nay.")],
    ["monthly_payroll",
     B("Monthly payroll", "Chi phí lương tháng"),
     B("The gross cost of the end-of-month payslips for the month named above the tiles, in any state. It is a cost figure rather than a payment figure: money in a run still waiting for approval is counted here and has not left the company.",
       "Tổng thu nhập của các phiếu lương cuối tháng trong tháng ghi phía trên các ô, ở mọi trạng thái. Đây là con số chi phí chứ không phải con số đã chi: tiền trong một đợt còn chờ phê duyệt vẫn được tính vào đây và chưa hề rời khỏi công ty.")],
    ["pending_approval",
     B("Pending approval", "Đang chờ phê duyệt"),
     B("How many PAYSLIPS are waiting for approval, company-wide — not runs, and not only yours. What is YOURS is on Home › Approvals, My turn.",
       "Có bao nhiêu PHIẾU LƯƠNG đang chờ phê duyệt trên toàn công ty — không phải số đợt, và không chỉ của bạn. Phần CỦA BẠN nằm ở Trang chủ › Phê duyệt, tab Đến lượt tôi.")],
    /* "Active configs" — the tile's caption in pb_dashboard.xml, verbatim. A
       column glossary is looked up BY LABEL, so a tidier wording than the
       product's is an entry the Coach can never match. */
    ["active_configs",
     B("Active configs", "Cấu hình đang chạy"),
     B("How many formula configurations are switched on — normally one per division and cycle. A number that has grown without anybody adding a division is worth opening: an old configuration left active can still be selected by a run.",
       "Có bao nhiêu cấu hình công thức đang được bật — thường là mỗi bộ phận và mỗi chu kỳ một bộ. Con số tăng lên mà không ai thêm bộ phận nào là điều đáng mở ra xem: một cấu hình cũ còn để bật vẫn có thể bị một đợt lương chọn phải.")],
  ],

  approvals: [
    ["my_turn",
     B("My turn", "Đến lượt tôi"),
     B("Requests whose current step names you. The only tab that is work for you.",
       "Các yêu cầu mà bước hiện tại ghi tên bạn. Tab duy nhất là việc của bạn.")],
    ["all_i_can_see",
     B("All I can see", "Tất cả tôi xem được"),
     B("Every open request you are allowed to see, whoever it is waiting for.",
       "Mọi yêu cầu đang mở mà bạn được phép xem, dù nó đang chờ ai.")],
    ["sent_back",
     B("Sent back", "Đã trả lại"),
     B("Requests a decider returned for changes. A sent-back pay run is a draft again with the note on it.",
       "Các yêu cầu bị người duyệt trả lại để sửa. Một đợt lương bị trả lại lại là bản nháp, kèm ghi chú.")],
    ["finished",
     B("Finished", "Đã xong"),
     B("Approved, applied, turned-down and withdrawn requests, kept with their history.",
       "Các yêu cầu đã duyệt, đã áp dụng, bị từ chối và bị thu hồi, được lưu kèm lịch sử.")],
  ],


  employees: [
    ["headcount",
     B("Headcount", "Số lượng nhân sự"),
     B("Everybody the company employs, active today. It counts people EMPLOYED, not people the last run PAID; that count lives on Insights › Workforce, and the gap is where a missing payslip hides.",
       "Mọi người công ty đang thuê, còn làm việc hôm nay. Nó đếm số người ĐANG THUÊ, không phải số người đợt lương gần nhất ĐÃ TRẢ; số đó nằm ở Phân tích › Lực lượng lao động, và khoảng chênh là chỗ một phiếu lương bị thiếu đang ẩn.")],
    ["running_contracts",
     B("Running contracts", "Hợp đồng đang hiệu lực"),
     B("Contracts in force today. It counts CONTRACTS, not people, so compare it with headcount: someone whose contract is still a draft is on the list and will not be in the run.",
       "Các hợp đồng đang có hiệu lực hôm nay. Nó đếm HỢP ĐỒNG, không đếm người, nên hãy so với số lượng nhân sự: người có hợp đồng còn ở Nháp vẫn có trong danh sách mà sẽ không có trong đợt lương.")],
    ["expiring_30",
     B("Expiring within 30 days", "Hết hạn trong 30 ngày"),
     B("Running contracts that end in the next thirty days. Each is a renewal somebody has to agree, or a leaver somebody has to settle — Lifecycle › Contracts raises the decision.",
       "Các hợp đồng đang hiệu lực sẽ kết thúc trong ba mươi ngày tới. Mỗi hợp đồng là một lần gia hạn cần người đồng ý, hoặc một người nghỉ cần quyết toán — Vòng đời nhân sự › Hợp đồng nêu quyết định đó.")],
    ["new_this_month",
     B("New this month", "Mới trong tháng này"),
     B("People who joined since the first of this month. They are the rows most likely to be paid for part of the month, and the most likely to have bank details missing.",
       "Những người vào làm từ ngày đầu tháng này. Đây là những dòng dễ được trả theo phần tháng nhất, và cũng dễ thiếu thông tin ngân hàng nhất.")],
    ["monthly_wage",
     B("Monthly wage", "Lương hàng tháng"),
     B("The monthly wages on running contracts, added up: what the company has agreed to pay before overtime, allowances or deductions.",
       "Tổng lương tháng trên các hợp đồng đang hiệu lực: mức công ty đã cam kết trả, chưa tính tăng ca, phụ cấp hay khấu trừ.")],
    ["payroll_ready",
     B("Payroll-ready", "Sẵn sàng trả lương"),
     B("The share of people with BANK DETAILS on file, over headcount, and nothing else. The tick on each row is stricter: a running contract AND bank details. Read the rows for the answer.",
       "Tỷ lệ những người ĐÃ CÓ THÔNG TIN NGÂN HÀNG, chia cho số lượng nhân sự, không tính gì khác. Dấu tích trên từng dòng chặt hơn: hợp đồng đang hiệu lực VÀ thông tin ngân hàng. Hãy đọc các dòng để có câu trả lời.")],
  ],

  contracts: [
    ["running",
     B("Running", "Đang hiệu lực"),
     B("Contracts in force today: the set payroll computes from. A contract that starts next week is not here yet, and neither is its person in this month's run.",
       "Các hợp đồng đang có hiệu lực hôm nay: tập hợp hệ thống lương dựa vào để tính. Hợp đồng bắt đầu từ tuần sau thì chưa ở đây, và người của hợp đồng đó cũng chưa có trong đợt lương tháng này.")],
    ["draft",
     B("Draft", "Nháp"),
     B("Contracts prepared and not put in force. A draft pays nothing: the person is on every other screen and simply absent from the payslips.",
       "Các hợp đồng đã soạn mà chưa đưa vào hiệu lực. Hợp đồng nháp không trả gì: người đó có trên mọi màn hình khác mà vắng mặt trong danh sách phiếu lương.")],
    ["expired",
     B("Expired", "Đã hết hạn"),
     B("Contracts past their end date. Each is a leaver who still needs settling on Pay Run › Settle, or a renewal that was never agreed.",
       "Các hợp đồng đã qua ngày kết thúc. Mỗi hợp đồng là một người nghỉ còn cần quyết toán ở Đợt lương › Quyết toán, hoặc một lần gia hạn chưa ai đồng ý.")],
    ["average_wage",
     B("Average wage", "Lương trung bình"),
     B("The monthly wages on running contracts, divided by how many there are. A company-wide average; the chips do not change it.",
       "Tổng lương tháng trên các hợp đồng đang hiệu lực, chia cho số hợp đồng đó. Là số trung bình toàn công ty; các chip lọc không làm nó thay đổi.")],
  ],

  insights: [
    /* The product's own caption under the headline is "net payroll" — NOT
       "Net paid", which is the Pay Runs board's KPI and already means
       "Đã chi". One English string, one Vietnamese; two screens that mean
       slightly different things get two names. */
    ["net_payroll",
     B("Net payroll", "Lương thực chi"),
     B("The net of the LATEST run this company has, in whatever state that run is in — a draft computed an hour ago counts. It comes from the run's own stored roll-up rather than from re-adding its payslip lines, and that is what makes the board fast. The state chip beside it tells you whether this is money that moved or money that might.",
       "Số thực nhận của đợt lương GẦN NHẤT mà công ty có, ở bất kỳ trạng thái nào — một bản nháp vừa tính cách đây một giờ vẫn được tính. Con số này lấy từ số tổng đã lưu sẵn của chính đợt đó chứ không phải cộng lại từng dòng phiếu lương, và đó là điều làm bảng này nhanh. Chip trạng thái bên cạnh cho biết đây là tiền đã chi hay tiền có thể sẽ chi.")],
    ["cost_story",
     B("Cost story", "Diễn biến chi phí"),
     B("The same measure over three, six or twelve months. The window chip decides which story it tells. Quote a figure without saying which window it came from, and somebody will contradict you using the same screen.",
       "Cùng một chỉ tiêu nhìn theo ba, sáu hay mười hai tháng. Chip chọn khoảng thời gian quyết định nó kể câu chuyện nào. Trích một con số mà không nói rõ lấy từ khoảng nào thì người khác sẽ phản bác bạn bằng đúng màn hình này.")],
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
     B("The dimension the rows are grouped into — division, department, cycle, month. Changing it does not change the total, only how that same total is divided up. It is the quickest way to check that a number is what you think it is.",
       "Chiều mà các dòng được nhóm theo — bộ phận, phòng ban, chu kỳ, tháng. Đổi nó không làm thay đổi con số tổng, chỉ thay đổi cách chia nhỏ cùng một tổng đó. Đây là cách nhanh nhất để kiểm tra xem một con số có đúng như bạn nghĩ không.")],
    ["where",
     B("Where", "Điều kiện"),
     B("Every filter currently applied, shown as a removable tag. The tags are part of the answer. The same measure with one tag removed is a different figure, and the two look identical once they are pasted into an email.",
       "Toàn bộ bộ lọc đang áp dụng, hiển thị thành các thẻ có thể gỡ. Các thẻ đó là một phần của câu trả lời. Cùng chỉ tiêu ấy mà gỡ đi một thẻ là ra một con số khác, và khi đã dán vào email thì hai con số trông y hệt nhau.")],
  ],

  workforcean: [
    ["employees_paid",
     B("Employees paid", "Nhân viên được trả lương"),
     B("How many people the runs in scope actually produced a payslip for. It is not headcount. Somebody employed all month whose contract sat in draft is counted on People and not here. That difference is the point of the tile.",
       "Có bao nhiêu người thực sự được các đợt lương trong phạm vi tạo ra phiếu lương. Đây không phải sĩ số. Một người làm cả tháng nhưng hợp đồng còn ở Nháp thì được đếm ở màn hình Nhân sự chứ không phải ở đây. Chính khác biệt đó mới là ý nghĩa của ô này.")],
    ["joiners",
     B("Joiners", "Vào mới"),
     B("People who first appear in a run inside this period. Almost all of them are prorated, which means almost all of them are a question somebody will ask about their first payslip.",
       "Những người lần đầu xuất hiện trong một đợt lương thuộc kỳ này. Gần như tất cả đều được tính theo ngày công, nghĩa là gần như tất cả đều sẽ là một câu hỏi về phiếu lương đầu tiên của họ.")],
    ["leavers",
     B("Leavers", "Thôi việc"),
     B("People whose last run falls in this period. Each one needs settling in Full & Final AND excluding from the ordinary monthly run. Somebody in both is paid twice, and getting that back is a legal conversation rather than a payroll one.",
       "Những người có đợt lương cuối cùng rơi vào kỳ này. Mỗi người vừa cần được quyết toán ở Quyết toán thôi việc VÀ cần bị loại khỏi đợt lương tháng thông thường. Người nằm ở cả hai chỗ sẽ được trả hai lần, và đòi lại khoản đó là chuyện pháp lý chứ không còn là chuyện tính lương.")],
    ["cost_per_head",
     B("Cost per head", "Chi phí bình quân đầu người"),
     B("The run's cost divided by the people it paid. It is the only figure on this screen that survives a headcount change, which makes it the honest way to compare two months. One total against another mostly measures how many people were in each.",
       "Chi phí của đợt lương chia cho số người nó đã trả. Đây là con số duy nhất trên màn hình này không bị méo khi sĩ số thay đổi, nên nó là cách so sánh trung thực giữa hai tháng. Còn đem tổng so với tổng thì chủ yếu là đang đo xem mỗi tháng có bao nhiêu người.")],
  ],

  govreports: [
    ["period",
     B("Period", "Kỳ báo cáo"),
     B("The month being filed for. It is a month rather than a date range, because the authorities ask for months. A filing generated before every run in that month is done is short by however many payslips are still moving.",
       "Tháng đang được lập báo cáo. Đây là một tháng chứ không phải một khoảng ngày, vì các cơ quan quản lý yêu cầu theo tháng. Một báo cáo kết xuất khi các đợt lương của tháng chưa xong sẽ thiếu đúng bằng số phiếu lương còn đang đi trong quy trình.")],
    ["country",
     B("Country", "Quốc gia"),
     B("Which country's filing set is on display. The active company's country decides the tiles, not what Payobook can produce. The chips only appear when a company runs payroll in more than one country.",
       "Bộ biểu mẫu của quốc gia nào đang hiển thị. Quốc gia của công ty đang hoạt động quyết định các ô biểu mẫu, chứ không phải những gì Payobook có thể tạo ra. Các chip chỉ xuất hiện khi công ty chạy lương ở nhiều hơn một quốc gia.")],
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
  "rep-pm-announce": "The practice Home › Announce card: one message sent to everyone.",
  "rep-pm-plan": "The practice People › Announce note: where the people who send messages plan the month.",
  "rep-ig-arrivals": "Arrivals from the connected system, drawn under the Integrations roster. In the product it is its own list, found through the search bar.",
  /* LEARN REFRESH step 5 — the contract drawer's three tabs, drawn at once in
     the replica (the product shows one at a time inside cd-body). */
  "rep-cd-terms": "The contract drawer's Terms, drawn beside Components and History so a lesson can walk all three. The product shows one tab at a time.",
  "rep-cd-comps": "The contract drawer's Components with Paid by and each amount's source chip.",
  "rep-cd-history": "The contract drawer's History: every change, from and to, with its source.",
  "rep-nav": "The replica's own sidebar. Mirrors pb_sidebar; nothing on it navigates the real app.",
  "rep-banner": "The practice banner. Says, on every screen, that none of this is your company.",
  /* The Dashboard replica's KPI row is NO LONGER practice-only. Phase C1 made
     the Dashboard a station with a full lesson, so the replica draws the real
     dash-hero / dash-runpayroll / dash-kpis / dash-formula attributes and the
     registry owns those names (promoted out of `foreign`). What is left here is
     the one panel with no product counterpart: the product's card is a single
     "Latest pay run" summary, and a lesson about the monthly loop needs to show
     a loop, so the replica draws three months and says so by name. */
  "rep-pipeline": "The pay run's road on the Runs replica: Draft → Waiting for approval → Done, with the two ways off it (sent back, turned down). A teaching view; the product draws this as columns and a route line.",
  "rep-tabs": "The replica's tab strip for the page being shown. Mirrors the product's hub tabs, in their order and words; tabs with no practice screen are drawn quiet and say so.",
  "rep-fs-stage": "The practice Formula Studio's stage badge and the Draft → Testing → Validated → Active chain drawn beside it. The product has the badge; the drawn chain is a teaching view.",
  "rep-fs-tools": "The practice panel that stands for Tools → Analyze → Simulate. In the product it is the Command Center overlay (fs-command opens it); here it is drawn open so a lesson can point at Simulate.",
  "rep-settings": "The practice company's Settings page of categories. The product draws the same categories; only the four with practice screens open anything here.",
  /* LEARNOS Phase 5. The free-roam sandbox's watermark. It is drawn by
     `practiceShellHTML` with no condition in front of it — the honesty of that
     view is that the mark cannot be switched off by any state the Journey
     holds — and it exists only here, because the product has no watermark. */
  /* LEARNOS Phase 5 — the two places a learner may TYPE, and the controls
     beside them. Both fields are declared in INPUT_ANCHORS (practice-data.js),
     which is the table the generator validates an `act: "input"` step against;
     an input step pointed anywhere else is refused. They are `rep-` names
     because neither field exists in the product: the real importer repairs a
     cell its own way and the real employee form is a form view. */
  "rep-impfix": "The import wizard's one repairable cell — the overtime amount on the row whose figure could not be read. A real input; the value a learner types is checked loosely against the step's own value, thousands marks and all.",
  "rep-impmatch": "The Match button on that same row. Practice-only because the product's importer offers its fixes differently; here it is what 'accept this row' looks like.",
  "rep-newemp-open": "The Add employee button on the Employees replica. In the product it opens a form view; here it is the step that takes the learner down to the practice form.",
  "rep-newemp-name": "The practice employee form's name field. A real input, declared in INPUT_ANCHORS as text, so tone marks are optional when it is checked.",
  "rep-newemp-div": "The practice employee form's division picker. A click target, not an input: choosing the division is choosing which formula configuration will pay this person.",
  "rep-newemp-save": "The practice employee form's Save button. It saves nothing — there is no server behind the replica — and the step that presses it is guarded for the same reason the real one would be.",
  "rep-watermark": "The practice-mode watermark. Says on every free-roam screen that none of this is real. Drawn unconditionally by the practice view builder; no product screen has one.",
  /* LEARN REFRESH step 3 — the payroll-setup replicas' own controls. */
  "rep-bp-rules": "The guided setup's Pay rules list on the practice company, each component as a sentence with its formula.",
  "rep-bp-added": "The component being added in the Pay rules replica (Allowances). The lesson's tick moment happens beside it.",
  "rep-bp-paynum": "The practice pay panel's take-home figure. Carries data-from / data-to so the tick moment can count from the before to the after value; the product shows the same number without the count.",
  "rep-jny-file": "The HR system's basic_salary field on the practice Journey — where Mai's base salary starts.",
  "rep-jny-feed": "The feed row that carries basic_salary on the practice Journey.",
  "rep-jny-xform": "The practice Journey's transformation card (text to amount).",
  "rep-jny-scheme": "LCB on the practice Journey's Scheme lane — where the value is fed.",
  "rep-jny-slip": "Mai's Base salary payslip line, drawn beside the practice Journey so the whole road fits on one screen. The product shows the payslip elsewhere.",
  "rep-jny-source": "The practice Journey's Payobook Source card, with Open Records Desk.",
  "rep-mp-runlane": "The From this pay run group on the practice spreadsheet tab.",
  "rep-mp-conflict": "The source-conflict question on the practice spreadsheet tab, drawn open. In the product it is a dialog that appears when a second source is wired.",
  "rep-ct-warn": "The Type says otherwise warning line on the practice Component treatment board.",
  "rep-am-payrow": "The pay run row of the practice Approval Matrix.",
  "rep-am-bsteps": "The practice route builder's five steps: Purpose, People, Safeguards, Review, Publish.",
  "rep-am-route": "The practice route builder's steps and the kinds of step it offers.",
  "rep-am-guards": "The practice route builder's safeguards and Try an example.",
  "rep-am-publish": "The practice route builder's Publish panel, with the date new requests follow it from.",
  "rep-rd-grid": "The practice Records Desk grid, with three edited cells.",
  "rep-rd-reviewpanel": "The practice Records Desk review drawer, drawn open beside the grid.",
  "rep-gp-foot": "The practice Group page's line that nothing is stored in the group currency.",
  "rep-ex-compare": "The practice Explorer's Compare schemes panel, each scheme in its own money.",
  "rep-slipline": "The worked example's statutory deductions, drawn on the STATUTORY replica beside the rates that produced them. It is the far end of L6's trace and it exists only here: the product's statutory cockpit shows rates, and a payslip shows đồng, and no single product screen shows both at once. Naming it rep- is the honest consequence — the Coach must never claim to point at this on a live screen.",
  /* LEARN REFRESH step 4 — the wider app's teaching views. */
  "rep-pr-budget": "The practice pay review's Budget meter, carrying its before/after for the `meter` moment: it fills as the rises go in.",
  "rep-pr-guide": "The practice worksheet's Use the guidance button (a Try target; it changes nothing).",
  "rep-pr-cal": "The practice worksheet's Calibration button (a Try target).",
  "rep-pr-send": "The practice review's Send for approval button — guarded in Try, like every control that would write.",
  "rep-dr-exact": "The practice Decision Room's line comparing the exact cost with the estimate.",
  "rep-hi-cands": "The practice Hiring board's candidate strip for the first role, with Nam at Discussion 1.",
  "rep-hi-route": "The practice hiring request's sign-off route: manager, HR lead, Finance only if over budget.",
  "rep-hi-send": "The practice hiring request's Send for approval — guarded in Try.",
  "rep-ex-card": "The practice Exits board's leaver card (Bùi Thị Hạnh), a Try target that opens her drawer.",
  "rep-ex-open": "The practice leaver drawer's Open the settlement button.",
  "rep-ex-desks": "The practice leaver drawer, drawn open: what each of the four desks checks, and which has not signed.",
  "rep-wf-exc": "The practice Time panel's line on exceptions becoming flags on Close.",
  "rep-wf-flag": "The practice Close board's first flag row (Hùng's missing check-out).",
  "rep-wf-fix": "The Fix button on that flag — the Try step that corrects the day.",
  "rep-wf-asis": "The Approve as-is button on that flag row.",
  "rep-wf-locked": "The practice Close board's picture of a locked week, with the Reopen… note. Drawn beside the grey lock so the lesson can show both states.",
  "rep-ac-handover": "The practice Hand my access over dialog, drawn open: who, what, until, and the automatic take-back.",
  "rep-pm-wall": "The practice Wall card: one piece of praise tied to a company value, and Say thank you.",
  "rep-pm-tiles": "The practice tiles for People's smaller tabs: Where they work, Assets, Goals, Announce.",
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
    screens: ["dashboard", "formula", "runpayroll", "payruns", "approvals"],
    name: B("Take the tour", "Đi một vòng Payobook"),
    tagline: B("Pulse, a pay run, the Approvals inbox, the Formula Engine and the helper — the whole product in one pass.",
               "Tổng quan, một đợt lương, hộp Phê duyệt, Bộ máy công thức và trợ lý — toàn bộ sản phẩm trong một lượt."),
    entry: { nav: "pb_dashboard.action_pb_dashboard" },
    steps: [
      {
        key: "hero", anchor: "dash-hero", nav: "pb_dashboard.action_pb_dashboard",
        act: "observe",
        say: {
          kicker: B("Welcome", "Chào bạn"),
          title: B("Home › Pulse", "Trang chủ › Tổng quan"),
          body: B("This is where you land. The line under your name is the latest pay run: how many of its payslips are done, and how many are waiting for approval.",
                  "Đây là nơi bạn vào đầu tiên. Dòng dưới tên bạn là đợt lương mới nhất: bao nhiêu phiếu đã xong, và bao nhiêu phiếu đang chờ phê duyệt."),
        },
      },
      {
        key: "kpis", anchor: "dash-kpis", act: "observe",
        say: {
          title: B("Four numbers that describe the company", "Bốn con số mô tả cả công ty"),
          body: B("Headcount, monthly payroll, pending approval and active configs — for the month named just above them.",
                  "Số lượng nhân sự, chi phí lương tháng, đang chờ phê duyệt và cấu hình đang chạy — của đúng tháng ghi ngay phía trên."),
        },
      },
      {
        key: "scheme", anchor: "pw-scheme", nav: "pb_payrun_wizard.action_pb_payrun_wizard",
        act: "observe",
        say: {
          kicker: B("Pay Run › Run", "Đợt lương › Chạy lương"),
          title: B("A pay run starts with its pay scheme", "Một đợt lương bắt đầu từ chương trình lương"),
          body: B("\"Pay run for\" lists the pay schemes. Picking one picks the rulebook every payslip in the run is computed by.",
                  "\"Đợt lương cho\" liệt kê các chương trình lương. Chọn một chương trình là chọn bộ quy tắc sẽ tính mọi phiếu lương trong đợt."),
          tip: B("I am not computing anything. This walk only reads.",
                 "Tôi không tính gì cả. Lượt này chỉ để đọc."),
        },
      },
      {
        key: "board", anchor: "pk-kpis", nav: "pb_payruns.action_pb_payruns_kanban",
        act: "observe",
        say: {
          kicker: B("Pay Run › Runs", "Đợt lương › Các đợt lương"),
          title: B("Every run on one board", "Mọi đợt lương trên một bảng"),
          body: B("Draft, Waiting for approval, Done. A waiting run's card says whose step it is at.",
                  "Nháp, Chờ phê duyệt, Hoàn tất. Thẻ của đợt đang chờ ghi rõ nó đang ở bước của ai."),
        },
      },
      {
        key: "inbox", anchor: "ai-tabs", nav: "pb_approval_config.action_pb_approval_inbox",
        act: "observe",
        say: {
          kicker: B("Home › Approvals", "Trang chủ › Phê duyệt"),
          title: B("One inbox for every decision", "Một hộp cho mọi quyết định"),
          body: B("Pay runs, overtime, leave, hiring — everything waiting for a decision lands here. My turn is what is waiting for you.",
                  "Đợt lương, tăng ca, nghỉ phép, tuyển dụng — mọi thứ đang chờ quyết định đều về đây. Đến lượt tôi là những gì đang chờ bạn."),
        },
      },
      {
        key: "studio", anchor: "fs-config", nav: "pb_formula_studio.action_pb_formula_studio",
        act: "observe",
        say: {
          kicker: B("Settings › Formula Engine", "Cài đặt › Bộ máy công thức"),
          title: B("One rulebook per pay scheme", "Mỗi chương trình lương một bộ quy tắc"),
          body: B("Every payslip line comes from a named component in a configuration you can open and read.",
                  "Mỗi dòng phiếu lương đến từ một thành phần có tên trong một cấu hình mà bạn mở ra đọc được."),
        },
      },
      {
        key: "components", anchor: "fs-components", act: "observe",
        say: {
          title: B("Every component, one list", "Mọi thành phần trong một danh sách"),
          body: B("Inputs, earnings, deductions and totals. The coloured tag says which kind each one is.",
                  "Đầu vào, thu nhập, khấu trừ và các tổng. Thẻ màu cho biết mỗi thành phần thuộc loại nào."),
        },
      },
      {
        key: "copilot", anchor: "helper-orb", nav: "pb_dashboard.action_pb_dashboard",
        act: "observe",
        say: {
          title: B("And help is always one press away", "Và trợ giúp luôn chỉ cách một lần bấm"),
          body: B("Press this button, or the ? key, on any screen. It knows which page and tab you are on, answers questions, and opens a safe practice copy. That is the tour.",
                  "Bấm nút này, hoặc phím ?, ở bất kỳ màn hình nào. Nó biết bạn đang ở trang và tab nào, trả lời câu hỏi, và mở một bản thực hành an toàn. Vậy là xong một vòng."),
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
    tagline: B("Pay scheme, month, scope, compute — the reads and the one press.",
               "Chương trình lương, tháng, phạm vi, tính — những lần đọc và một lần bấm."),
    entry: { nav: "pb_payrun_wizard.action_pb_payrun_wizard", screen: "runpayroll" },
    steps: [
      {
        key: "scheme", anchor: "pw-scheme", nav: "pb_payrun_wizard.action_pb_payrun_wizard",
        screen: "runpayroll", act: "observe",
        say: {
          kicker: B("Step 1", "Bước 1"),
          title: B("Pick the pay scheme", "Chọn chương trình lương"),
          body: B("\"Pay run for\" groups the schemes: End of month, Regular payroll, Mid-month advance, Final settlement. Picking a scheme picks the rulebook every payslip in this run is computed by.",
                  "\"Đợt lương cho\" nhóm các chương trình: Cuối tháng, Kỳ lương thường, Tạm ứng giữa tháng, Quyết toán thôi việc. Chọn chương trình là chọn bộ quy tắc sẽ tính mọi phiếu lương trong đợt này."),
        },
      },
      {
        key: "scope", anchor: "pw-scope", screen: "runpayroll", act: "observe",
        say: {
          kicker: B("Step 1", "Bước 1"),
          title: B("Which month, and what to call it", "Tháng nào, và gọi đợt này là gì"),
          body: B("The period decides which month is computed. The batch name is what everybody after you will search for.",
                  "Kỳ lương quyết định tháng nào được tính. Tên đợt là thứ những người sau bạn sẽ dùng để tìm."),
        },
      },
      {
        key: "summary", anchor: "pw-summary", screen: "runpayroll", act: "observe",
        say: {
          kicker: B("Step 1", "Bước 1"),
          title: B("The last read before anything is computed", "Lần đọc cuối trước khi tính"),
          body: B("Company, currency and pay scheme — and only the people this scheme pays are affected. If the scheme reads a spreadsheet, the next step asks for this month's file.",
                  "Công ty, tiền tệ và chương trình lương — và chỉ những người thuộc chương trình này bị ảnh hưởng. Nếu chương trình đọc một bảng tính, bước tiếp theo sẽ xin tệp của tháng này."),
        },
      },
      {
        key: "paymode", anchor: "pw-paymode", screen: "runpayroll", act: "observe", modes: ["try"],
        say: {
          kicker: B("Step 2 · Pay data", "Bước 2 · Dữ liệu lương"),
          title: B("Update Payobook, or This run only", "Cập nhật Payobook, hay Chỉ đợt này"),
          body: B("Update Payobook saves the file's values onto people's records from now on. This run only uses them once and changes nothing in Payobook.",
                  "Cập nhật Payobook lưu các giá trị trong tệp vào hồ sơ từ nay về sau. Chỉ đợt này dùng chúng một lần và không thay đổi gì trong Payobook."),
        },
      },
      {
        key: "compute", anchor: "pw-compute", screen: "runpayroll",
        act: "click", guard: true,
        say: {
          kicker: B("The press", "Lần bấm"),
          title: B("Compute the payslips", "Tính phiếu lương"),
          body: B("This creates one draft payslip per person the scheme pays. Drafts only: nothing is paid, sent or approved. They are still real records, with real names on them.",
                  "Thao tác này tạo một phiếu lương nháp cho mỗi người thuộc chương trình lương. Chỉ là bản nháp: chưa chi, chưa gửi, chưa duyệt. Nhưng chúng vẫn là bản ghi thật, mang tên người thật."),
          tip: B("When the scheme reads a spreadsheet this button says Add pay data, and the file comes first.",
                 "Khi chương trình đọc bảng tính, nút này ghi Thêm dữ liệu lương, và tệp phải có trước."),
        },
      },
      {
        key: "resultcard", act: "observe", modes: ["watch"],
        say: {
          kicker: B("After Compute", "Sau khi tính"),
          title: B("What you would see next", "Những gì bạn sẽ thấy tiếp theo"),
          body: B("I did not press Compute, so there is nothing to point at. Once computed, three numbers appear: Payslips, Computed, Need review. Need review lists anyone Payobook could not pay, and anyone in the file who is not in Payobook yet. Then Open Payroll takes you to Runs.",
                  "Tôi không bấm Tính, nên chưa có gì để chỉ vào. Sau khi tính, ba con số sẽ hiện ra — Phiếu lương, Đã tính, Cần xem xét — và Cần xem xét liệt kê những người Payobook không trả được và những người có trong tệp mà chưa có trong Payobook. Rồi Mở bảng lương đưa bạn tới Các đợt lương."),
        },
      },
      {
        key: "pills", anchor: "pw-pills", screen: "runpayroll", act: "observe", modes: ["try", "do"],
        say: {
          kicker: B("Reading results", "Đọc kết quả"),
          title: B("Payslips, Computed, Need review", "Phiếu lương, Đã tính, Cần xem xét"),
          body: B("Need review adds up payslips at zero or below, people Payobook could not pay, and people in the file who are not in Payobook yet. It does not flag a big jump on last month — that is yours to spot.",
                  "Cần xem xét cộng các phiếu bằng không hoặc âm, những người Payobook không trả được, và những người có trong tệp mà chưa có trong Payobook. Nó không đánh dấu mức tăng lớn so với tháng trước — việc đó là của bạn."),
        },
      },
      {
        key: "missing", anchor: "pw-missing", screen: "runpayroll", act: "observe", modes: ["try"],
        say: {
          title: B("Listed, not paid", "Được liệt kê, không được trả lương"),
          body: B("Nobody is created from a pay data file. Add these people, and their pay comes through on the next run.",
                  "Không ai được tạo ra từ tệp dữ liệu lương. Hãy thêm những người này, lương của họ sẽ có ở đợt kế tiếp."),
        },
      },
      {
        key: "next", act: "observe",
        say: {
          title: B("Then: Open Payroll, and Submit for approval", "Tiếp theo: Mở bảng lương, rồi Gửi để phê duyệt"),
          body: B("Open Payroll lands on Pay Run › Runs with the run in Draft. Submit for approval sends it along its approval route. Nobody is paid until the last step says yes.",
                  "Mở bảng lương đưa bạn tới Đợt lương › Các đợt lương với đợt ở cột Nháp. Gửi để phê duyệt đưa nó đi theo lộ trình phê duyệt. Chưa ai được trả tiền cho tới khi bước cuối đồng ý."),
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
          kicker: B("Pay Run › Runs", "Đợt lương › Các đợt lương"),
          title: B("Five numbers over the whole board", "Năm con số trên toàn bảng"),
          body: B("Pay runs, In pipeline, Awaiting your approval, Completed and Net paid. The third is the only one about you.",
                  "Đợt lương, Đang xử lý, Chờ bạn phê duyệt, Hoàn tất và Đã chi. Con số thứ ba là con số duy nhất nói về bạn."),
        },
      },
      {
        key: "steps", anchor: "pk-steps", screen: "payruns", act: "observe",
        say: {
          title: B("Three states, not three months", "Ba trạng thái, không phải ba tháng"),
          body: B("Draft, Waiting for approval, Done — each with its count, and a flag when a run was sent back or is waiting on you.",
                  "Nháp, Chờ phê duyệt, Hoàn tất — mỗi bước kèm số lượng, và một dấu khi có đợt bị trả lại hoặc đang chờ bạn."),
        },
      },
      {
        key: "card", anchor: "pk-card", screen: "payruns", act: "observe",
        say: {
          title: B("One card is one run", "Một thẻ là một đợt lương"),
          body: B("Employees, gross and net, and only the buttons its state allows. A waiting run says whose step it is at.",
                  "Nhân viên, tổng thu nhập và thực nhận, và chỉ những nút trạng thái của nó cho phép. Đợt đang chờ ghi rõ nó đang ở bước của ai."),
        },
      },
      {
        key: "runsel", anchor: "ps-runsel", nav: "pb_payslip_review.action_pb_payslip_review",
        screen: "payslips", act: "observe",
        say: {
          kicker: B("Pay Run › Payslips", "Đợt lương › Phiếu lương"),
          title: B("Everything below belongs to this run", "Mọi thứ bên dưới thuộc về đợt này"),
          body: B("The selector at the top scopes the whole screen. Change it to compare two months.",
                  "Ô chọn ở trên cùng giới hạn phạm vi của cả màn hình. Đổi nó để so sánh hai tháng."),
        },
      },
      {
        key: "pskpis", anchor: "ps-kpis", screen: "payslips", act: "observe",
        say: {
          title: B("Need review means take-home pay at zero or below", "Cần xem xét nghĩa là thực nhận bằng không hoặc âm"),
          body: B("Payslips, Need review, Gross total, Net total. Need review here only catches a payslip that pays nothing; what else to open is your choice.",
                  "Phiếu lương, Cần xem xét, Tổng thu nhập, Tổng thực nhận. Cần xem xét ở đây chỉ bắt phiếu không trả đồng nào; mở thêm phiếu nào là do bạn chọn."),
        },
      },
      {
        key: "list", anchor: "ps-list", screen: "payslips", act: "observe",
        say: {
          title: B("Pick one person", "Chọn một người"),
          body: B("Each row is one payslip: the person, their net and its state. Open the ones with the biggest changes first.",
                  "Mỗi dòng là một phiếu lương: người đó, thực nhận và trạng thái. Hãy mở những phiếu thay đổi nhiều nhất trước."),
        },
      },
      {
        key: "status", anchor: "ps-status", screen: "payslips", act: "observe",
        say: {
          title: B("A payslip moves with its run", "Một phiếu lương đi cùng đợt của nó"),
          body: B("Draft, Waiting for approval, Done — and no button here. Payslips are approved together, as a pay run.",
                  "Nháp, Chờ phê duyệt, Hoàn tất — và không có nút nào ở đây. Các phiếu được duyệt cùng nhau, theo cả đợt lương."),
        },
      },
      {
        key: "breakdown", anchor: "ps-breakdown", screen: "payslips", act: "observe",
        say: {
          title: B("The working behind the net", "Phần tính toán đứng sau số thực nhận"),
          body: B("Every line with its rule, in the order the configuration produced them. This is the answer to \"why is this person's pay different this month\".",
                  "Từng dòng kèm quy tắc của nó, theo đúng thứ tự cấu hình sinh ra. Đây là câu trả lời cho câu hỏi \"vì sao tháng này lương người này khác\"."),
        },
      },
    ],
  },


  /* ---------------------------------------------------------- sc_formula
     tour_formula, and from LEARNOS Phase 5 a READ-SIDE Try as well.

     WATCH WALKS ALL EIGHTEEN CONTROLS. TRY WALKS THE SEVEN THE REPLICA DRAWS,
     and the difference is structural rather than editorial: half of this
     walkthrough happens in the Grid, and the practice replica has no Grid. The
     answer Phase 5 chose is NOT to build one — a replica of a spreadsheet
     engine is a second spreadsheet engine to keep true — but to let each step
     say which modes it is playable in. So Try is the reading half: the
     configuration, its components, one formula in words, the names/letters
     toggle, what it depends on, the live preview and the simulator. Every one
     of those is a control the replica really has, and the generator refuses a
     try-playable step whose anchor it does not draw.

     The eleven steps scoped to `watch` are the editing half and the Grid. They
     are not lesser steps; they are steps whose controls only exist in the
     product, and pointing Try at one would be a learner clicking at nothing. */
  {
    key: "sc_formula",
    icon: "calculator",
    line: "setup",
    modes: ["watch", "try"],
    screens: ["formula"],
    name: B("Explore the formula engine", "Khám phá bộ máy công thức"),
    tagline: B("Components, formulas, dependencies and the spreadsheet grid behind them.",
               "Thành phần, công thức, quan hệ phụ thuộc và lưới bảng tính đứng sau chúng."),
    entry: { nav: "pb_formula_studio.action_pb_formula_studio", screen: "formula" },
    steps: [
      {
        key: "config", anchor: "fs-config", nav: "pb_formula_studio.action_pb_formula_studio",
        act: "observe",
        say: {
          kicker: B("Formula Studio", "Xưởng công thức"),
          title: B("Where every salary rule lives", "Nơi mọi quy tắc lương cư trú"),
          body: B("A live, visual spreadsheet engine. The switcher at the top chooses which division's configuration you are reading. The shape of the code is PREFIX_DIVISION_CYCLE.",
                  "Một bộ máy bảng tính trực quan và chạy thật. Ô chuyển ở trên cùng cho biết bạn đang đọc cấu hình của bộ phận nào. Mã có dạng TIỀN TỐ_BỘ PHẬN_CHU KỲ."),
        },
      },
      {
        key: "components", anchor: "fs-components", act: "observe",
        say: {
          title: B("Every component, one list", "Mọi thành phần trong một danh sách"),
          body: B("Inputs, earnings, deductions and totals. Click any component to open it. The coloured tag tells you what it is at a glance.",
                  "Đầu vào, thu nhập, khấu trừ và các tổng. Bấm vào thành phần nào là mở thành phần đó. Thẻ màu cho biết ngay nó thuộc loại gì."),
        },
      },
      {
        key: "arrows", anchor: "fs-arrows", act: "observe", modes: ["watch"],
        say: {
          title: B("See the dependencies", "Nhìn thấy quan hệ phụ thuộc"),
          body: B("Turn the arrows on and the connecting lines are drawn between components. You see what feeds what, across the whole configuration at once.",
                  "Bật mũi tên lên là các đường nối được vẽ ngay giữa các thành phần. Bạn thấy cái nào nuôi cái nào, trên toàn bộ cấu hình cùng lúc."),
          tip: B("With the arrows on, double-click a connector and the list on the left scrolls to the component it links.",
                 "Khi đã bật mũi tên, bấm đúp vào một đường nối là danh sách bên trái cuộn tới đúng thành phần mà nó dẫn đến."),
        },
      },
      {
        key: "card", anchor: "fs-card", act: "observe", modes: ["watch"],
        say: {
          title: B("The component card", "Thẻ thành phần"),
          body: B("Each rule shows its column, its code, its category and a validity check. You always know whether the arithmetic is sound before you trust it.",
                  "Mỗi quy tắc hiển thị cột, mã, nhóm và một dấu kiểm tính hợp lệ. Bạn luôn biết phép tính có đúng hay không trước khi tin vào nó."),
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
          body: B("Flip to letters (A, B, C…) to read a formula beside a spreadsheet. Flip back to names to explain it to somebody. Same formula either way.",
                  "Chuyển sang chữ cái (A, B, C…) để đọc công thức song song với bảng tính. Quay lại tên khi cần giải thích cho người khác. Vẫn là một công thức."),
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
        key: "flow", anchor: "fs-flow", act: "observe", timeout: 4000, modes: ["watch"],
        say: {
          title: B("Watch it calculate", "Xem nó tính"),
          body: B("The calculation flow shows how a result is built, step by step, down to the final output. Open it full screen. Scroll to zoom, drag to pan.",
                  "Sơ đồ tính toán cho thấy một kết quả được dựng lên từng bước ra sao, cho tới đầu ra cuối cùng. Hãy mở toàn màn hình. Cuộn để phóng to, kéo để di chuyển."),
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
        /* PLAYABLE IN BOTH, and it is the last read-side control the replica
           draws. Simulate answers the question a formula screen otherwise
           leaves open — "what would this do to real pay" — and it answers it
           without changing anything, which is why it belongs in the reading
           half rather than beside the editing controls below. */
        key: "simulate", anchor: "fs-command", act: "observe",
        say: {
          title: B("Try a change before you make it: Tools → Analyze → Simulate", "Thử một thay đổi trước khi làm thật: Công cụ → Phân tích → Mô phỏng"),
          body: B("Tools (Ctrl/Cmd + K) holds every tool. Simulate runs this configuration against a period that has already been paid, and shows what would have come out. Nothing is written and no payslip moves. It is the cheapest way to find out that a rule you were sure about is wrong.",
                  "Công cụ (Ctrl/Cmd + K) chứa mọi công cụ. Mô phỏng chạy cấu hình này trên một kỳ lương đã chi, rồi cho xem kết quả sẽ ra sao. Không có gì được ghi và không phiếu lương nào thay đổi. Đây là cách rẻ nhất để phát hiện một quy tắc bạn đinh ninh là đúng hoá ra lại sai."),
        },
      },
      {
        key: "add", anchor: "fs-add", act: "observe", modes: ["watch"],
        say: {
          title: B("Add a component, or a whole sheet", "Thêm một thành phần, hoặc cả một trang tính"),
          body: B("Need a new allowance or deduction? The plus adds one component. The same control imports an entire Excel sheet, which is scored before anything is saved.",
                  "Cần thêm một khoản phụ cấp hay khấu trừ? Dấu cộng thêm một thành phần. Cũng chính nút đó nhập cả một trang Excel, và bản nhập được chấm điểm trước khi có gì được lưu."),
        },
      },
      {
        key: "editai", anchor: "fs-editai", act: "observe", modes: ["watch"],
        say: {
          title: B("Edit by describing it", "Sửa bằng cách mô tả"),
          body: B("Change a formula by describing the change in plain language. Whether editing is available to you at all is a permission, set by your administrator.",
                  "Đổi một công thức bằng cách mô tả thay đổi bằng lời. Việc bạn có quyền sửa hay không là do quản trị viên cấp."),
        },
      },
      {
        key: "views", anchor: "fs-views", act: "observe",
        say: {
          title: B("Cards, Grid, Test, Compare, Health, Settings", "Thẻ, Lưới, Kiểm thử, So sánh, Sức khoẻ, Cài đặt"),
          body: B("Six ways to hold the same configuration; Settings opens its guided setup in edit mode. Let us open the Grid, which looks like the spreadsheet this all replaced.",
                  "Sáu cách nhìn cùng một cấu hình; Cài đặt mở phần thiết lập có hướng dẫn ở chế độ sửa. Chúng ta hãy mở Lưới, cách nhìn giống bảng tính mà hệ thống này thay thế."),
        },
      },
      {
        key: "opengrid", anchor: "fs-view-grid", act: "click", guard: false, modes: ["watch"],
        say: {
          kicker: B("Your turn", "Đến lượt bạn"),
          title: B("Open the Grid", "Mở Lưới"),
          body: B("Every component laid out as spreadsheet columns — column letter, code, formula and its live value. Switching view writes nothing; it is a way of looking.",
                  "Mọi thành phần được bày ra thành các cột bảng tính — chữ cái cột, mã, công thức và giá trị hiện tại. Đổi cách xem không ghi gì cả; đó chỉ là một cách nhìn."),
        },
      },
      {
        key: "canvas", anchor: "grid-canvas", act: "observe", timeout: 5000, modes: ["watch"],
        say: {
          title: B("The full spreadsheet grid", "Toàn bộ lưới bảng tính"),
          body: B("Each component is a column. The rows are its name, category, type, formula, live value and validity. Walk it with the arrow keys, A, B, C, straight across.",
                  "Mỗi thành phần là một cột. Các hàng là tên, nhóm, loại, công thức, giá trị hiện tại và tính hợp lệ. Dùng phím mũi tên để đi ngang qua A, B, C."),
        },
      },
      {
        key: "fbar", anchor: "grid-fbar", act: "observe", timeout: 4000, modes: ["watch"],
        say: {
          title: B("The formula bar", "Thanh công thức"),
          body: B("Click any formula cell and it loads here. Edit it in the bar, or press F2 in the cell. Both take the same validated round trip, with live feedback as you type.",
                  "Bấm vào ô công thức bất kỳ là nó hiện ở đây. Sửa trong thanh này, hoặc bấm F2 ngay trong ô. Cả hai đều đi qua cùng một lượt kiểm tra, có phản hồi ngay khi bạn gõ."),
        },
      },
      {
        key: "gridhint", anchor: "grid-hint", act: "observe", timeout: 4000, modes: ["watch"],
        say: {
          title: B("Edit, multi-select and drag-fill", "Sửa, chọn nhiều và kéo điền"),
          body: B("Enter saves, Esc cancels, Ctrl+Z undoes. Shift-click or Ctrl-click column headers to set several categories at once. Or drag a formula's fill handle sideways to copy it, with its references translated.",
                  "Enter để lưu, Esc để huỷ, Ctrl+Z để hoàn tác. Giữ Shift hoặc Ctrl rồi bấm tiêu đề cột để đặt nhóm cho nhiều cột cùng lúc. Hoặc kéo tay cầm điền của một công thức sang ngang để sao chép, kèm dịch tham chiếu."),
        },
      },
      {
        key: "payai", anchor: "fs-payai", act: "observe", modes: ["watch"],
        say: {
          title: B("The copilot knows this configuration", "Trợ lý hiểu cấu hình này"),
          body: B("Ask it to explain a rule or draft a new one. That is Formula Studio — spreadsheet power without a spreadsheet to keep in a folder.",
                  "Hãy nhờ nó giải thích một quy tắc hoặc phác một quy tắc mới. Đó là Xưởng công thức — sức mạnh bảng tính mà không phải giữ một tệp bảng tính trong thư mục nào cả."),
        },
      },
    ],
  },

  /* ----------------------------------------------------------- sc_import
     tour_import, and from LEARNOS Phase 5 a Try as well.

     THE TWO MODES WALK DIFFERENT CONTROLS, AND THAT IS THE HONEST SHAPE HERE.
     Watch narrates the REAL multi-sheet importer, which lives inside a backend
     wizard that cannot be opened cold: its steps point at `imp-*`, they degrade
     to centred cards until the learner has the wizard on screen, and their
     timeout is short so the degradation is quick rather than a nine-second
     stare. Try walks the PRACTICE importer, which is a replica of the same
     flow with controls of its own. Both tell one story — score the file, fix
     the row that could not be read, then commit — and a step declares which
     mode it belongs to rather than the two being two scenarios that drift.

     `entry.nav` opens the import cockpit. Watch used to start wherever the
     learner happened to be standing, which meant its first card described a
     screen that was not there. */
  {
    key: "sc_import",
    icon: "inbox",
    line: "payrun",
    modes: ["watch", "try"],
    screens: ["import", "importwizard"],
    name: B("Load a month's pay data", "Tải dữ liệu lương của một tháng"),
    tagline: B("Load the month's file, match rows to people, fix what is wrong — then commit.",
               "Tải tệp của tháng, khớp các dòng với từng người, sửa chỗ sai — rồi ghi vào hệ thống."),
    entry: { nav: "pb_import.action_pb_import", screen: "import" },
    steps: [
      {
        key: "intro", anchor: "im-cta", act: "observe", modes: ["watch"], timeout: 2000,
        say: {
          kicker: B("Pay Run › Import", "Đợt lương › Nhập"),
          title: B("Load this period's pay data", "Tải dữ liệu lương của kỳ này"),
          body: B("This is the guided flow for a month's numbers: upload the file, match rows to people, fix what is wrong, then commit. The tiles under it are one-off setup.",
                  "Đây là luồng có hướng dẫn cho số liệu của một tháng: tải tệp lên, khớp các dòng với từng người, sửa chỗ sai, rồi ghi vào hệ thống. Các ô bên dưới là thiết lập một lần."),
        },
      },
      {
        key: "pipe", anchor: "im-pipe", act: "observe", modes: ["watch"], timeout: 2000,
        say: {
          title: B("Where every import batch is", "Mỗi đợt nhập đang ở đâu"),
          body: B("Draft, Loaded, Matched, Validated, Processing, Done. A batch that stops before Done has changed nothing at all.",
                  "Nháp, Đã tải, Đã khớp, Đã kiểm tra, Đang ghi, Hoàn tất. Một đợt dừng trước Hoàn tất thì chưa thay đổi gì cả."),
        },
      },
      {
        key: "batches", anchor: "im-batches", act: "observe", modes: ["watch"], timeout: 2000,
        say: {
          title: B("The history", "Lịch sử"),
          body: B("Every batch ever loaded, with its rows, matches and errors. Press Load pay data to open the flow yourself; nothing is written until you commit.",
                  "Mọi đợt từng được tải, kèm số dòng, số khớp và số lỗi. Bấm Tải dữ liệu lương để tự mở luồng; chưa có gì được ghi cho tới khi bạn ghi vào hệ thống."),
          tip: B("In the flow, the counts to read are Rows loaded, Matched, New employees and Need attention — each row is a person.",
                 "Trong luồng, các con số cần đọc là Dòng đã nạp, Đã khớp, Nhân viên mới và Cần xử lý — mỗi dòng là một con người."),
        },
      },

      /* ---- the Try track, on the practice importer (LEARNOS Phase 5) ----
         Six steps over two replica screens. The learner starts the flow, reads
         the score, repairs the one cell that could not be read, matches the
         row, commits, and reads what the commit produced. Nothing here can
         reach a record: there is no server behind a replica. */
      {
        key: "openflow", anchor: "im-cta", screen: "import",
        act: "click", guard: false, modes: ["try"],
        say: {
          kicker: B("Your turn", "Đến lượt bạn"),
          title: B("Open the guided flow", "Mở luồng có hướng dẫn"),
          body: B("An import is four steps: choose the source, review what was matched, fix what was not, then write it. Press the button to begin. Opening the flow writes nothing.",
                  "Một lượt nhập liệu có bốn bước: chọn nguồn, soát phần đã khớp, sửa phần chưa khớp, rồi ghi vào hệ thống. Hãy bấm nút để bắt đầu. Mở luồng này chưa ghi gì cả."),
        },
      },
      {
        key: "readscore", anchor: "iw-review", screen: "importwizard",
        act: "observe", modes: ["try"],
        say: {
          title: B("Read the counts — each row is a person", "Đọc các con số — mỗi dòng là một con người"),
          body: B("46 of 48 rows matched, and two still need you. Those two are the people the run would get wrong.",
                  "46 trên 48 dòng đã khớp, và còn hai dòng cần bạn. Hai dòng đó là những người mà đợt lương sẽ tính sai."),
        },
      },
      {
        key: "fixcell", anchor: "rep-impfix", screen: "importwizard",
        act: "input", value: B("1,200,000", "1.200.000"), modes: ["try"],
        say: {
          title: B("Repair the cell that could not be read", "Sửa ô mà hệ thống không đọc được"),
          body: B("This row's overtime cell is not a number, so the import would read it as nothing. Type the amount from the file and press Enter. A cell nobody repairs becomes a zero on somebody's payslip.",
                  "Ô tăng ca của dòng này không phải là số, nên hệ thống sẽ hiểu là không có gì. Hãy gõ số tiền theo tệp rồi bấm Enter. Ô không ai sửa sẽ thành số không trên phiếu lương của một người."),
          tip: B("Type it the way you write numbers. Dots, commas or neither — the amount is what is checked.",
                 "Bạn viết số theo thói quen nào cũng được. Dấu chấm, dấu phẩy hay không dấu gì — cái được kiểm là con số."),
        },
      },
      {
        /* GUARDED. `match` joined the writing verbs in the Phase 5 review
           round, and it belongs there: pressing this writes the row's
           employee onto the staged batch. In Try the guard changes nothing a
           learner can feel — the replica has no server either way — which is
           exactly why declaring it honestly costs nothing. */
        key: "matchrow", anchor: "rep-impmatch", screen: "importwizard",
        act: "click", guard: true, modes: ["try"],
        say: {
          title: B("Match the row to a person", "Ghép dòng đó với một con người"),
          body: B("Three choices sit on this row: Match, Retry and Skip. Match tells Payobook which employee record the repaired figure belongs to. Skip would leave this person out of the run.",
                  "Dòng này có ba lựa chọn: Khớp, Thử lại và Bỏ qua. Khớp cho Payobook biết con số vừa sửa thuộc về hồ sơ nhân viên nào. Bỏ qua sẽ để người này ra ngoài đợt lương."),
        },
      },
      {
        key: "commit", anchor: "iw-commit", screen: "importwizard",
        act: "click", guard: true, modes: ["try"],
        say: {
          title: B("Commit the import", "Ghi nhận dữ liệu"),
          body: B("Nothing was written until now. This is the press that writes, and on your own data it is the one worth reading the counts before. Here it is a rehearsal.",
                  "Cho tới lúc này chưa có gì được ghi. Đây chính là cú bấm ghi dữ liệu, và trên dữ liệu thật thì nên đọc kỹ các con số trước khi bấm. Ở đây chỉ là tập dượt."),
          tip: B("Abandoning the flow before this leaves everything exactly as it was.",
                 "Bỏ dở luồng này trước bước đó thì mọi thứ vẫn y nguyên như cũ."),
        },
      },
      {
        key: "landed", anchor: "iw-outcome", screen: "importwizard",
        act: "observe", modes: ["try"],
        say: {
          title: B("What the import produced", "Lượt nhập đã tạo ra gì"),
          body: B("Two counts: people created and payslips created. Read them against what you expected. A number you did not expect is a question to ask now, not after the run is approved.",
                  "Hai con số: số người được tạo và số phiếu lương được tạo. Hãy đối chiếu với những gì bạn mong đợi. Con số lệch là câu hỏi cần hỏi ngay, đừng đợi đến khi đợt lương đã duyệt xong."),
        },
      },
    ],
  },

  /* ----------------------------------------------------------- sc_people
     ADD YOUR FIRST EMPLOYEE — LEARNOS Phase 5, and the first scenario in this
     module that was never a pb_coach tour.

     TRY ONLY, and the reason is the same one that makes it worth writing. The
     activation checklist's second item asks a brand-new tenant to add their
     first person, and the two ways to teach that are both bad on their own: a
     Watch of the real form would be a walkthrough of an empty database with
     nobody in it, and a Do would have somebody's first act in their own
     Payobook be one a tutorial talked them through. Try is the third answer —
     the same five steps, on a company that is not theirs — so that when they
     do it for real they have done it before.

     THE LAST STEP DOES NOT SHOW THE ROW APPEARING, and that is deliberate. The
     replica has no server, so a roster that grew by one would be a lie the
     fixture told; instead the step points at the roster the learner already
     read in LP and at the person on it who is NOT payroll-ready. That is the
     more useful ending anyway: adding somebody is the easy half. */
  {
    key: "sc_people",
    icon: "user-plus",
    line: "people",
    modes: ["try"],
    screens: ["employees"],
    name: B("Add your first employee", "Thêm nhân viên đầu tiên"),
    tagline: B("Name, division, save — and the one thing that still stands between a new person and their pay.",
               "Tên, bộ phận, lưu — và điều duy nhất còn ngăn giữa một người mới và tiền lương của họ."),
    entry: { screen: "employees" },
    steps: [
      {
        key: "open", anchor: "rep-newemp-open", screen: "employees",
        act: "click", guard: false,
        say: {
          kicker: B("Step 1", "Bước 1"),
          title: B("Find the new employee form", "Tìm biểu mẫu nhân viên mới"),
          body: B("Everybody who is paid starts here. In Payobook this button opens a form of its own. In the practice company that form is already drawn under the roster — press the button, then read it there.",
                  "Mọi người được trả lương đều bắt đầu từ đây. Trong Payobook, nút này mở ra một biểu mẫu riêng. Trong công ty thực hành, biểu mẫu đó đã có sẵn ngay dưới danh sách — hãy bấm nút rồi đọc ở đó."),
        },
      },
      {
        key: "name", anchor: "rep-newemp-name", screen: "employees",
        act: "input", value: B("Nguyễn Văn An", "Nguyễn Văn An"),
        say: {
          kicker: B("Step 2", "Bước 2"),
          title: B("Type the person's name", "Nhập tên người đó"),
          body: B("The name is what everybody after you will search for, so write it the way their contract writes it. Type it and press Enter.",
                  "Cái tên là thứ những người sau bạn sẽ dùng để tìm, nên hãy viết đúng như trong hợp đồng của họ. Gõ vào rồi bấm Enter."),
          tip: B("Tone marks are optional here. The practice company is not marking your spelling.",
                 "Ở đây bạn gõ có dấu hay không đều được. Công ty thực hành không chấm chính tả của bạn."),
        },
      },
      {
        key: "division", anchor: "rep-newemp-div", screen: "employees",
        act: "click", guard: false,
        say: {
          kicker: B("Step 3", "Bước 3"),
          title: B("Pick the division", "Chọn bộ phận"),
          body: B("This is the decision on this form. A division carries its own formula configuration, so choosing one here is choosing the rules that will price every payslip this person ever gets.",
                  "Đây là quyết định quan trọng nhất trên biểu mẫu này. Mỗi bộ phận có cấu hình công thức riêng, nên chọn bộ phận ở đây là chọn bộ quy tắc sẽ tính mọi phiếu lương của người này về sau."),
        },
      },
      {
        key: "save", anchor: "rep-newemp-save", screen: "employees",
        act: "click", guard: true,
        say: {
          kicker: B("Step 4", "Bước 4"),
          title: B("Save the person", "Lưu người này"),
          body: B("On your own Payobook this writes a record other people can see. Here it writes nothing at all — there is no server behind the practice company.",
                  "Trên Payobook của chính bạn, thao tác này ghi một bản ghi mà người khác cũng nhìn thấy. Ở đây nó không ghi gì cả — không có máy chủ nào phía sau công ty thực hành."),
        },
      },
      {
        key: "roster", anchor: "pe-roster", screen: "employees",
        act: "observe",
        say: {
          kicker: B("Step 5", "Bước 5"),
          title: B("On the roster is not the same as paid", "Có trong danh sách chưa phải là được trả lương"),
          body: B("Read the last row. That person is on the roster and has no bank account on file, so payroll cannot pay them. Adding somebody is the easy half; a running contract and bank details are the half that decides whether they are in the next run.",
                  "Hãy đọc dòng cuối cùng. Người đó đã có trong danh sách nhưng chưa có tài khoản ngân hàng, nên hệ thống không chi lương cho họ được. Thêm người mới là phần dễ; hợp đồng đang hiệu lực và thông tin ngân hàng mới là phần quyết định họ có mặt trong đợt lương tới hay không."),
          tip: B("The payroll-ready column is where this shows up. It counts bank details over headcount, and it is the tile to read before a run rather than after it.",
                 "Cột \"sẵn sàng tính lương\" là nơi điều này hiện ra. Nó đếm số người đã có thông tin ngân hàng trên tổng sĩ số, và nên đọc trước khi chạy đợt lương chứ đừng đọc sau."),
        },
      },
    ],
  },

  /* ---------------------------------------------------------- sc_mapping
     tour_mapping. Watch only: the mid/end mapping wizard is opened from a
     configuration, not from a menu, and the practice replica has no wizard of
     its own to stand in for it.

     `entry.nav` opens FORMULA STUDIO rather than the import cockpit, and that
     is a deliberate departure from the Phase 5 handover's wording, which asked
     for the import action on both of the watch-only tours. Import is right for
     sc_import and wrong here: this walkthrough's own first card tells the
     learner to open the mapping wizard from a configuration, so landing them
     on a screen none of its three steps mentions would be a worse start than
     the one it replaces. The two steps whose anchors live inside the closed
     wizard keep their centred-card degradation and drop to a 2-second wait. */
  {
    key: "sc_mapping",
    /* LEARN REFRESH step 2: RETIRED from the map and from every offer. It
       rides the old mid/end-cycle mapping wizard; step 3 writes the Mapping
       walkthrough. Kept so progress rows for it keep their meaning. */
    retired: true,
    icon: "git-branch",
    line: "setup",
    modes: ["watch"],
    screens: ["formula", "structures"],
    name: B("Map mid-cycle pay to end-cycle", "Ánh xạ lương giữa kỳ sang cuối kỳ"),
    tagline: B("Pair the components of two configurations without matching dozens by hand.",
               "Ghép các thành phần của hai cấu hình mà không phải khớp tay hàng chục dòng."),
    entry: { nav: "pb_formula_studio.action_pb_formula_studio" },
    steps: [
      {
        key: "intro", act: "observe",
        say: {
          kicker: B("Mid to end cycle", "Giữa kỳ sang cuối kỳ"),
          title: B("Two configurations, one month", "Hai cấu hình, một tháng"),
          body: B("A division that pays twice a month has a mid-cycle configuration and an end-cycle one. Their components have to line up. To follow along, open the mid/end mapping wizard and pick both configurations.",
                  "Bộ phận trả lương hai lần một tháng có một cấu hình giữa kỳ và một cấu hình cuối kỳ. Các thành phần của chúng phải khớp nhau. Để đi theo, hãy mở trình ánh xạ giữa kỳ / cuối kỳ và chọn cả hai cấu hình."),
        },
      },
      {
        key: "matched", anchor: "map-intro", act: "observe", timeout: 2000,
        say: {
          title: B("Matched by code, then by name", "Khớp theo mã, rồi theo tên"),
          body: B("Auto-suggest pairs components with the same code first, which is a perfect match. For the rest it falls back to name similarity, and it skips anything you have already mapped. Every suggestion shows its confidence and the reason it was made.",
                  "Chức năng gợi ý tự động ghép trước các thành phần trùng mã, tức khớp tuyệt đối. Với phần còn lại, nó dựa vào độ giống tên, và bỏ qua những cặp bạn đã ánh xạ. Mỗi gợi ý đều kèm độ tin cậy và lý do được ghép."),
        },
      },
      {
        key: "accept", anchor: "map-actions", act: "observe", timeout: 2000,
        say: {
          title: B("Suggest, review, accept", "Gợi ý, soát lại, chấp nhận"),
          body: B("Generate the proposals and read them. Then accept the confident ones in one go, or take them one at a time. The machine does the tedious first pass. The judgement stays yours.",
                  "Hãy sinh ra các đề xuất và đọc chúng. Rồi chấp nhận một lượt những cặp có độ tin cậy cao, hoặc duyệt từng cặp một. Máy làm giúp lượt rà soát nhàm chán đầu tiên. Phần phán đoán vẫn là của bạn."),
          tip: B("A component left unmapped is not an error. It is a component that exists in one cycle and not the other, and that happens.",
                 "Một thành phần chưa được ánh xạ không phải là lỗi. Đó là thành phần chỉ có ở một chu kỳ mà không có ở chu kỳ kia, và chuyện đó vẫn xảy ra."),
        },
      },
    ],
  },

  /* ==========================================================================
     LEARN REFRESH step 3 — PAYROLL SETUP WALKTHROUGHS.
     Watch walks the real screens and presses NOTHING that writes: every step
     is an observe. Try walks the practice replicas of the same screens. The
     Mapping walkthrough replaces the retired sc_mapping under a new key, so
     old progress rows keep their meaning.
     ======================================================================== */

  /* ---------------------------------------------------------- sc_blueprint */
  {
    key: "sc_blueprint",
    icon: "sparkles",
    line: "setup",
    modes: ["watch", "try"],
    screens: ["blueprint", "blueprint_rules"],
    name: B("Set up a new pay scheme", "Thiết lập một chương trình lương mới"),
    tagline: B("The guided setup's six steps, and the pay panel that answers as you build.",
               "Sáu bước của phần thiết lập có hướng dẫn, và khung lương trả lời ngay khi bạn dựng."),
    entry: { nav: "pb_blueprint.action_pb_blueprint", screen: "blueprint" },
    steps: [
      {
        key: "rail", anchor: "bp-rail", nav: "pb_blueprint.action_pb_blueprint",
        screen: "blueprint", act: "observe",
        say: {
          kicker: B("Settings › Guided setup", "Cài đặt › Thiết lập có hướng dẫn"),
          title: B("Six steps, one pay scheme", "Sáu bước, một chương trình lương"),
          body: B("Start, Pay rules, Connect, Outputs, Test, Finish. The steps after Start open once the draft exists.",
                  "Bắt đầu, Quy tắc lương, Kết nối, Đầu ra, Kiểm thử, Hoàn thành. Các bước sau Bắt đầu mở ra khi bản nháp đã có."),
          tip: B("I only read in this walkthrough. Nothing is created.", "Trong lượt hướng dẫn này tôi chỉ đọc. Không có gì được tạo ra."),
        },
      },
      {
        key: "identity", anchor: "bp-identity", screen: "blueprint", act: "observe",
        say: {
          kicker: B("Start", "Bắt đầu"),
          title: B("Name, company and pay cycle", "Tên, công ty và chu kỳ lương"),
          body: B("Give it a name that says where and who it pays. The pay cycle is the shape of the run it drives.",
                  "Đặt một cái tên nói rõ trả lương ở đâu và cho ai. Chu kỳ lương là hình dạng của đợt lương mà nó điều khiển."),
        },
      },
      {
        key: "country", anchor: "bp-country", screen: "blueprint", act: "observe",
        say: {
          kicker: B("Start", "Bắt đầu"),
          title: B("The country decides the money", "Quốc gia quyết định đồng tiền"),
          body: B("Pick a country and a chip says what the scheme pays in. It also brings that country's insurance and tax rules.",
                  "Chọn một quốc gia và một nhãn cho biết chương trình trả lương bằng gì. Nó cũng mang theo các quy tắc bảo hiểm và thuế của quốc gia đó."),
        },
      },
      {
        key: "starters", anchor: "bp-starters", screen: "blueprint", act: "observe",
        say: {
          kicker: B("Start", "Bắt đầu"),
          title: B("A starting point", "Một điểm bắt đầu"),
          body: B("A ready-made library for the country, your own Excel workbook, or a blank canvas. Certified libraries were checked against the law.",
                  "Một thư viện dựng sẵn cho quốc gia, sổ tính Excel của bạn, hoặc một trang trắng. Thư viện được chứng nhận đã được đối chiếu với luật."),
        },
      },
      {
        key: "audience", anchor: "bp-audience", screen: "blueprint", act: "observe",
        say: {
          kicker: B("Start", "Bắt đầu"),
          title: B("Who you pay", "Bạn trả lương cho ai"),
          body: B("Local, international, short-term, guaranteed take-home. Your answer decides which components and sample people come next.",
                  "Trong nước, nước ngoài, ngắn hạn, lương thực nhận cố định. Câu trả lời của bạn quyết định các thành phần và người mẫu ở bước sau."),
        },
      },
      {
        key: "pay", anchor: "bp-pay", screen: "blueprint", act: "observe",
        say: {
          kicker: B("See it in someone's pay", "Xem ngay trên lương của một người"),
          title: B("The panel that answers as you build", "Khung trả lời ngay khi bạn dựng"),
          body: B("Once the draft exists, a sample person's take-home pay appears here and moves each time a rule changes. Sample data only.",
                  "Khi bản nháp đã có, tiền thực nhận của một người mẫu hiện ở đây và thay đổi mỗi khi một quy tắc thay đổi. Chỉ là dữ liệu mẫu."),
        },
      },
      {
        key: "tick", anchor: "rep-bp-added", screen: "blueprint_rules", act: "observe", modes: ["try"],
        say: {
          kicker: B("Pay rules", "Quy tắc lương"),
          title: B("A component was just added", "Một thành phần vừa được thêm"),
          body: B("Allowances joined the rules. Look right: take-home pay rose by the allowance, less the income tax on it.",
                  "Phụ cấp vừa vào danh sách quy tắc. Nhìn sang phải: tiền thực nhận tăng đúng bằng khoản phụ cấp, trừ đi phần thuế thu nhập trên nó."),
        },
      },
      {
        key: "continue", anchor: "bp-foot", screen: "blueprint", act: "observe",
        say: {
          kicker: B("The press", "Lần bấm"),
          title: B("Continue creates the draft", "Tiếp tục sẽ tạo bản nháp"),
          body: B("Continue to pay rules is the first press that saves anything. I will not press it. After that, the setup saves as you go.",
                  "Tiếp tục sang Quy tắc lương là lần bấm đầu tiên lưu bất cứ thứ gì. Tôi sẽ không bấm nó. Sau đó, phần thiết lập tự lưu khi bạn làm."),
        },
      },
      {
        key: "finish", act: "observe",
        say: {
          title: B("Finish is not switching it on", "Hoàn thành không phải là bật lên"),
          body: B("Finish means complete and checked. Putting the scheme live is a separate proposal — approved first when your company has a route for it.",
                  "Hoàn thành nghĩa là đã xong và đã kiểm tra. Đưa chương trình vào dùng là một đề xuất riêng — được phê duyệt trước khi công ty bạn có lộ trình cho việc đó."),
        },
      },
    ],
  },

  /* -------------------------------------------------------- sc_mapjourney
     Replaces sc_mapping (retired in step 2). The Journey tab of the real
     Mapping screen, and the practice company's Journey with the one value the
     lesson follows. */
  {
    key: "sc_mapjourney",
    icon: "git-branch",
    line: "setup",
    modes: ["watch", "try"],
    screens: ["mapping", "mapping_sheet"],
    name: B("Follow a number through Mapping", "Lần theo một con số qua Ánh xạ"),
    tagline: B("FROM a source, TO a scheme — lane by lane, and which source wins when there are two.",
               "TỪ một nguồn, ĐẾN một chương trình lương — từng làn một, và nguồn nào thắng khi có hai."),
    entry: { nav: "pb_formula_studio.action_pb_mapping_studio", screen: "mapping" },
    steps: [
      {
        key: "story", anchor: "mp-story", nav: "pb_formula_studio.action_pb_mapping_studio",
        screen: "mapping", act: "observe",
        say: {
          kicker: B("Settings › Integrations › Mapping", "Cài đặt › Tích hợp › Ánh xạ"),
          title: B("FROM a source, TO a scheme", "TỪ một nguồn, ĐẾN một chương trình lương"),
          body: B("The header is a sentence. Both ends are pickers: change the scheme on the right and every tab follows it.",
                  "Phần đầu là một câu. Cả hai đầu đều chọn được: đổi chương trình lương bên phải thì mọi tab đi theo nó."),
        },
      },
      {
        key: "modes", anchor: "mp-modes", screen: "mapping", act: "observe",
        say: {
          title: B("One tab per kind of wire", "Mỗi loại dây nối một tab"),
          body: B("System fields, Transformations, Spreadsheet columns, Employee & contract, Who is paid by what, Mid and End cycle, Component treatment — and the Journey, which draws them all.",
                  "Trường hệ thống, Chuyển đổi, Cột bảng tính, Nhân viên & hợp đồng, Ai được trả lương theo phương án nào, Giữa và Cuối chu kỳ, Xử lý thành phần — và Hành trình, nơi vẽ tất cả."),
        },
      },
      {
        key: "headline", anchor: "mp-jbar", screen: "mapping", act: "observe",
        say: {
          title: B("Read the counts first", "Hãy đọc các con số trước"),
          body: B("What needs a source, what is fed, what is not fed yet. Anything not fed is computed as empty.",
                  "Những gì cần một nguồn, đã có nguồn, chưa có nguồn. Thứ gì chưa có nguồn sẽ được tính là trống."),
        },
      },
      {
        key: "lanes", anchor: "mp-lanes", screen: "mapping", act: "observe",
        say: {
          title: B("Left to right is the road", "Từ trái sang phải là chặng đường"),
          body: B("Files & systems, Feeds, Transformations, the Scheme, Payobook Source. Open a card to see its fields; the corner arrow opens the tab that edits it.",
                  "Tệp & hệ thống, Nguồn cấp dữ liệu, Chuyển đổi, Chương trình lương, Nguồn Payobook. Mở một thẻ để xem các trường; mũi tên ở góc mở tab để sửa nó."),
        },
      },
      {
        key: "follow", anchor: "rep-jny-scheme", screen: "mapping", act: "observe", modes: ["try"],
        say: {
          kicker: B("One value", "Một giá trị"),
          title: B("Mai's base salary, fed", "Lương cơ bản của Mai, đã có nguồn"),
          body: B("It left the HR system, was turned from text into an amount, and feeds LCB. On payday it is her Base salary line.",
                  "Nó rời hệ thống nhân sự, được chuyển từ chữ thành số tiền, và cấp cho LCB. Vào ngày trả lương, nó là dòng Lương cơ bản của cô ấy."),
        },
      },
      {
        key: "sheet", anchor: "mp-ramp", screen: "mapping_sheet", act: "observe", modes: ["try"],
        say: {
          kicker: B("Spreadsheet columns → Scheme", "Cột bảng tính → Chương trình lương"),
          title: B("Headings, not numbers", "Tiêu đề, không phải con số"),
          body: B("Drop this period's file to see its columns and one example row. Nothing is imported here.",
                  "Thả tệp của kỳ này để xem các cột và một dòng ví dụ. Ở đây không nhập gì cả."),
        },
      },
      {
        key: "conflict", anchor: "rep-mp-conflict", screen: "mapping_sheet", act: "observe", modes: ["try"],
        say: {
          title: B("Two sources, one component", "Hai nguồn, một thành phần"),
          body: B("Payobook asks before a second source is added. Keep both and the higher one wins; the lower one only fills an empty box.",
                  "Payobook hỏi trước khi thêm nguồn thứ hai. Giữ cả hai thì nguồn cao hơn thắng; nguồn thấp hơn chỉ điền vào ô trống."),
        },
      },
      {
        key: "rule", act: "observe", modes: ["watch"],
        say: {
          title: B("When two sources feed one component", "Khi hai nguồn cùng cấp một thành phần"),
          body: B("Wiring a second source asks first. Keep both and they are read in order: the higher one wins, the lower one only fills an empty box.",
                  "Nối thêm nguồn thứ hai sẽ được hỏi trước. Giữ cả hai thì chúng được đọc theo thứ tự: nguồn cao hơn thắng, nguồn thấp hơn chỉ điền vào ô trống."),
        },
      },
    ],
  },

  /* --------------------------------------------------------- sc_treatment
     Opens Mapping ON its Component treatment tab: the screen has a place
     (pb_mapping_studio:treatment), so `nav` names the screen and the helper's
     hub page for Mapping says which context key carries the tab. */
  {
    key: "sc_treatment",
    icon: "settings",
    line: "setup",
    modes: ["watch", "try"],
    screens: ["treatment", "mapping"],
    name: B("Fix figures that do not add up", "Sửa số liệu không khớp"),
    tagline: B("Pay role, subtotal and value type — the three answers that decide net pay.",
               "Vai trò trong lương, tổng phụ và loại giá trị — ba câu trả lời quyết định thực nhận."),
    entry: { nav: "treatment", screen: "treatment" },
    steps: [
      {
        key: "head", anchor: "tr-head", nav: "treatment", screen: "treatment", act: "observe",
        say: {
          kicker: B("Mapping › Component treatment", "Ánh xạ › Xử lý thành phần"),
          title: B("One board per scheme", "Mỗi chương trình lương một bảng"),
          body: B("It belongs to the scheme, so a change affects every run. Re-classify from the formulas works the answers out again and keeps the rows you set.",
                  "Nó thuộc về chương trình lương, nên một thay đổi ảnh hưởng mọi đợt lương. Phân loại lại từ các công thức tính lại các câu trả lời và giữ nguyên những dòng bạn tự đặt."),
          tip: B("I only read here. Saving is yours to press.", "Ở đây tôi chỉ đọc. Nút Lưu là để bạn bấm."),
        },
      },
      {
        key: "filters", anchor: "tr-filters", screen: "treatment", act: "observe",
        say: {
          title: B("What needs you", "Những gì cần bạn"),
          body: B("Needs your answer: no pay role yet. Type says otherwise: a pay role the value type disagrees with. Clear these first.",
                  "Cần câu trả lời của bạn: chưa có vai trò trong lương. Loại giá trị nói khác: vai trò mà loại giá trị không khớp. Hãy xử lý những dòng này trước."),
        },
      },
      {
        key: "table", anchor: "tr-table", screen: "treatment", act: "observe",
        say: {
          title: B("Pay role, subtotal, value type", "Vai trò trong lương, tổng phụ, loại giá trị"),
          body: B("The pay role decides the arithmetic from gross to net. Subtotal stops a total being counted twice. Only an amount can touch net pay.",
                  "Vai trò trong lương quyết định phép tính từ tổng thu nhập xuống thực nhận. Tổng phụ giúp một khoản tổng không bị tính hai lần. Chỉ số tiền mới được chạm tới thực nhận."),
        },
      },
      {
        key: "warn", anchor: "rep-ct-warn", screen: "treatment", act: "observe", modes: ["try"],
        say: {
          title: B("Hours set to add to net pay", "Giờ được đặt để cộng vào thực nhận"),
          body: B("The board warns you and offers to set them all to Information only. Hours reach pay through the overtime formula, not by themselves.",
                  "Bảng sẽ cảnh báo và đề nghị đặt tất cả thành Chỉ để tham khảo. Giờ đi vào lương qua công thức tăng ca, không tự đi vào."),
        },
      },
      {
        key: "recompute", act: "observe",
        say: {
          title: B("Save, then recompute", "Lưu, rồi tính lại"),
          body: B("Saving never rewrites a payslip. Recompute the pay run, and the \"These figures do not add up\" line goes away when the treatment is right.",
                  "Lưu không bao giờ viết lại phiếu lương. Hãy tính lại đợt lương, và dòng \"Các số liệu này không khớp\" sẽ biến mất khi cách xử lý đã đúng."),
        },
      },
    ],
  },

  /* ------------------------------------------------------------ sc_matrix */
  {
    key: "sc_matrix",
    icon: "clipboard-check",
    line: "setup",
    modes: ["watch", "try"],
    screens: ["matrix", "matrix_builder"],
    name: B("Change an approval route", "Đổi một lộ trình phê duyệt"),
    tagline: B("Read who signs off what, and what publishing a change really does.",
               "Đọc ai phê duyệt việc gì, và việc ban hành một thay đổi thật sự làm gì."),
    entry: { nav: "pb_approval_config.action_pb_approval_matrix", screen: "matrix" },
    steps: [
      {
        key: "hero", anchor: "am-hero", nav: "pb_approval_config.action_pb_approval_matrix",
        screen: "matrix", act: "observe",
        say: {
          kicker: B("Settings › Approvals", "Cài đặt › Phê duyệt"),
          title: B("Every check, in one place", "Mọi bước kiểm tra, ở một nơi"),
          body: B("Every request in the Approvals inbox follows a route drawn here.",
                  "Mọi yêu cầu trong hộp Phê duyệt đều đi theo một lộ trình vẽ ở đây."),
          tip: B("I only read. Nothing here is published by this walkthrough.", "Tôi chỉ đọc. Lượt hướng dẫn này không ban hành gì."),
        },
      },
      {
        key: "tabs", anchor: "am-tabs", screen: "matrix", act: "observe",
        say: {
          title: B("Matrix, People & backups, History", "Ma trận, Con người & người thay thế, Lịch sử"),
          body: B("The routes; who holds each responsibility and their cover; and every change ever made.",
                  "Các lộ trình; ai giữ từng trách nhiệm và người trực thay; và mọi thay đổi từng được thực hiện."),
        },
      },
      {
        key: "table", anchor: "am-table", screen: "matrix", act: "observe",
        say: {
          title: B("Read a route", "Đọc một lộ trình"),
          body: B("Each row is a process, the route it follows, where it applies, and whether it is In use, a Draft, or Needs people.",
                  "Mỗi dòng là một quy trình, lộ trình nó đi theo, nơi áp dụng, và nó Đang dùng, là Nháp, hay Cần bổ sung người."),
        },
      },
      {
        key: "bulk", anchor: "am-bulk", screen: "matrix", act: "observe",
        say: {
          title: B("No approval needed — still recorded", "Không cần phê duyệt — vẫn được ghi lại"),
          body: B("A check can be switched off for one row or many. It then happens at once, and every use still shows in History.",
                  "Một bước kiểm tra có thể tắt cho một dòng hoặc nhiều dòng. Khi đó việc diễn ra ngay, và mỗi lần dùng vẫn hiện trong Lịch sử."),
        },
      },
      {
        key: "builder", anchor: "rep-am-bsteps", screen: "matrix_builder", act: "observe", modes: ["try"],
        say: {
          kicker: B("The builder", "Dựng lộ trình"),
          title: B("Purpose · People · Safeguards · Review · Publish", "Mục đích · Nhân sự · Bảo vệ · Xem lại · Ban hành"),
          body: B("Opening a row walks these five steps. Nothing changes until Publish.",
                  "Mở một dòng sẽ đi qua năm bước này. Chưa có gì thay đổi cho tới Ban hành."),
        },
      },
      {
        key: "publish", anchor: "rep-am-publish", screen: "matrix_builder", act: "observe", modes: ["try"],
        say: {
          title: B("New requests only", "Chỉ áp cho yêu cầu mới"),
          body: B("New requests follow a published route from the date shown. Requests already on their way finish the route they started on.",
                  "Yêu cầu mới đi theo lộ trình đã ban hành từ ngày được ghi. Những yêu cầu đang trên đường sẽ đi hết lộ trình chúng đã bắt đầu."),
        },
      },
      {
        key: "open", act: "observe", modes: ["watch"],
        say: {
          title: B("To change one, open its row", "Muốn sửa, hãy mở dòng đó"),
          body: B("The builder walks Purpose, People, Safeguards, Review and Publish. Publishing affects new requests only.",
                  "Phần dựng lộ trình đi qua Mục đích, Nhân sự, Bảo vệ, Xem lại và Ban hành. Ban hành chỉ áp cho yêu cầu mới."),
        },
      },
    ],
  },

  /* ----------------------------------------------------------- sc_records */
  {
    key: "sc_records",
    icon: "database",
    line: "setup",
    modes: ["watch", "try"],
    screens: ["records"],
    name: B("Bulk update employee records", "Cập nhật hàng loạt hồ sơ nhân viên"),
    tagline: B("Pick who and what, change it on screen or in a file, review, apply — and undo.",
               "Chọn ai và gì, sửa trên màn hình hoặc trong tệp, xem lại, áp dụng — và hoàn tác."),
    entry: { nav: "pb_records.action_pb_records_desk", screen: "records" },
    steps: [
      {
        key: "head", anchor: "rd-head", nav: "pb_records.action_pb_records_desk",
        screen: "records", act: "observe",
        say: {
          kicker: B("People › Records", "Con người › Hồ sơ"),
          title: B("The Records Desk", "Bàn cập nhật hồ sơ (Records Desk)"),
          body: B("Employee, contract and bank details your pay scheme reads — for one person or hundreds at once.",
                  "Thông tin nhân viên, hợp đồng và ngân hàng mà chương trình lương của bạn đọc — cho một người hay hàng trăm người cùng lúc."),
          tip: B("I only read. Nothing is applied by this walkthrough.", "Tôi chỉ đọc. Lượt hướng dẫn này không áp dụng gì."),
        },
      },
      {
        key: "scheme", anchor: "rd-scheme", screen: "records", act: "observe",
        say: {
          title: B("Only what the scheme reads", "Chỉ những gì chương trình lương đọc"),
          body: B("The pill names the scheme and how many fields it maps. The desk offers only those.",
                  "Nhãn ghi tên chương trình và số trường nó ánh xạ. Bàn làm việc chỉ đưa ra những trường đó."),
        },
      },
      {
        key: "fields", anchor: "rd-fields", screen: "records", act: "observe", modes: ["try"],
        say: {
          title: B("Pick the fields", "Chọn các trường"),
          body: B("Choose the columns you want on the grid, and filter who on the left.",
                  "Chọn các cột bạn muốn trên lưới, và lọc ai ở bên trái."),
        },
      },
      {
        key: "fieldswatch", act: "observe", modes: ["watch"],
        say: {
          title: B("Pick who, and which fields", "Chọn ai, và trường nào"),
          body: B("Filter who on the left and choose the columns for the grid. A scheme that maps no fields yet shows Open Mapping here instead — wire a column first.",
                  "Lọc ai ở bên trái và chọn các cột cho lưới. Chương trình lương chưa ánh xạ trường nào sẽ hiện Mở Ánh xạ ở đây — hãy nối một cột trước."),
        },
      },
      {
        key: "file", anchor: "rd-file", screen: "records", act: "observe",
        say: {
          title: B("Or go through a file", "Hoặc đi qua một tệp"),
          body: B("Export with data, edit it, then Import a file. Rows are matched by employee code, work email or name.",
                  "Xuất kèm dữ liệu, sửa, rồi Nhập một tệp. Các dòng được khớp theo mã nhân viên, email công việc hoặc tên."),
        },
      },
      {
        key: "review", anchor: "rd-review", screen: "records", act: "observe",
        say: {
          title: B("Review before Apply", "Xem lại trước khi Áp dụng"),
          body: B("Review lists every change from what to what. Apply then writes it — or sends it for approval when your company has a route for bulk changes.",
                  "Xem lại liệt kê mọi thay đổi từ gì sang gì. Áp dụng khi đó sẽ ghi — hoặc gửi đi phê duyệt khi công ty bạn có lộ trình cho thay đổi hàng loạt."),
        },
      },
      {
        key: "history", anchor: "rd-history", screen: "records", act: "observe",
        say: {
          title: B("Undo never expires", "Hoàn tác không bao giờ hết hạn"),
          body: B("Every apply is in History with an Undo. It skips any value somebody has changed since.",
                  "Mỗi lần áp dụng đều có trong Lịch sử kèm Hoàn tác. Nó bỏ qua giá trị nào đã có người sửa sau đó."),
        },
      },
    ],
  },

  /* ----------------------------------------------------------- sc_schemes */
  {
    key: "sc_schemes",
    icon: "globe",
    line: "setup",
    modes: ["watch", "try"],
    screens: ["schemes", "runpayroll", "explorer"],
    name: B("Pay people in another currency", "Trả lương bằng một đồng tiền khác"),
    tagline: B("A scheme pays in its country's money; the group reads two monies without adding them.",
               "Chương trình lương trả bằng đồng tiền của quốc gia nó; tập đoàn đọc hai đồng tiền mà không cộng chúng."),
    entry: { nav: "pb_group.action_pb_group", screen: "schemes" },
    steps: [
      {
        key: "head", anchor: "gp-head", nav: "pb_group.action_pb_group",
        screen: "schemes", act: "observe",
        say: {
          kicker: B("Settings › Group", "Cài đặt › Tập đoàn"),
          title: B("Your group", "Tập đoàn của bạn"),
          body: B("The companies you own, the money the group reads in, and how exchange rates are picked.",
                  "Các công ty bạn sở hữu, đồng tiền tập đoàn dùng để đọc, và cách chọn tỷ giá."),
          tip: B("I only read. Nothing here is changed.", "Tôi chỉ đọc. Không có gì ở đây bị thay đổi."),
        },
      },
      {
        key: "tree", anchor: "gp-tree", screen: "schemes", act: "observe",
        say: {
          title: B("Each company keeps its own money", "Mỗi công ty giữ đồng tiền của mình"),
          body: B("Every company shows its currency and its pay schemes. Nothing is stored in the group currency.",
                  "Mỗi công ty hiện đồng tiền và các chương trình lương của nó. Không có gì được lưu bằng đồng tiền tập đoàn."),
        },
      },
      {
        key: "rates", anchor: "gp-rates", screen: "schemes", act: "observe",
        say: {
          title: B("How rates are picked", "Cách chọn tỷ giá"),
          body: B("The last rate of the month, the rate on the day the pay run ends, or the month's average. The strip shows which months have a rate.",
                  "Tỷ giá cuối cùng của tháng, tỷ giá vào ngày đợt lương kết thúc, hoặc tỷ giá bình quân của tháng. Dải tháng cho biết tháng nào đã có tỷ giá."),
        },
      },
      {
        key: "run", anchor: "pw-scheme", nav: "pb_payrun_wizard.action_pb_payrun_wizard",
        screen: "runpayroll", act: "observe",
        say: {
          kicker: B("Pay Run › Run", "Đợt lương › Chạy lương"),
          title: B("One run, one scheme, one currency", "Một đợt, một chương trình, một đồng tiền"),
          body: B("A pay run starts with its scheme, so it pays in one money. Two schemes this month are two pay runs.",
                  "Một đợt lương bắt đầu từ chương trình lương, nên nó trả bằng một đồng tiền. Hai chương trình trong tháng này là hai đợt lương."),
        },
      },
      {
        key: "money", anchor: "ex-money", nav: "pb_explorer.action_pb_explorer",
        screen: "explorer", act: "observe",
        say: {
          kicker: B("Insights › Explorer", "Phân tích › Khám phá dữ liệu"),
          title: B("Each in its own money, or the group's", "Mỗi bên theo đồng tiền của mình, hay theo tập đoàn"),
          body: B("With more than one currency on screen, this switch appears. Each in its own money keeps them apart; Group currency converts them so they can be added.",
                  "Khi có nhiều hơn một đồng tiền trên màn hình, công tắc này hiện ra. Mỗi bên theo đồng tiền của mình để chúng riêng rẽ; Đồng tiền của tập đoàn quy đổi chúng để có thể cộng lại."),
        },
      },
    ],
  },

  /* ==========================================================================
     LEARN REFRESH step 4 — THE WIDER APP'S WALKTHROUGHS.
     One Watch per full station, on the real screens, pressing NOTHING that
     writes: every step is an observe, except a few that open a card or a
     drawer (guard: false — opening reads). Hiring, the pay review, Exits and
     Close the week can also be taken as Try, over the practice company.
     A reader whose company does not give them the tab gets the no-access
     ending first (scenario_overlay.js refusalOnScreen + the hubs' own gates).
     ======================================================================== */

  /* ---------------------------------------------------------- sc_paybands */
  {
    key: "sc_paybands",
    icon: "bar-chart",
    line: "people",
    modes: ["watch"],
    screens: ["paybands"],
    name: B("Read your pay bands", "Đọc các khoảng lương"),
    tagline: B("Every person in their band, the five checks worth knowing, and the fairness view.",
               "Mọi người trong khoảng lương của mình, năm phép kiểm tra đáng biết, và phần công bằng."),
    entry: { nav: "paybands" },
    steps: [
      {
        key: "tabs", anchor: "pp-tabs", nav: "paybands", act: "observe",
        say: {
          kicker: B("People › Pay", "Con người › Lương"),
          title: B("Four tabs: Bands, Fairness, Review, Changes", "Bốn tab: Khoảng lương, Công bằng, Xét lương, Thay đổi"),
          body: B("Bands and Fairness describe pay as it is. Review and Changes are where it changes.",
                  "Khoảng lương và Công bằng mô tả lương như hiện tại. Xét lương và Thay đổi là nơi lương thay đổi."),
          tip: B("I only read. Nothing here is changed.", "Tôi chỉ đọc. Không có gì ở đây bị thay đổi."),
        },
      },
      {
        key: "tools", anchor: "pp-bands-tools", act: "observe",
        say: {
          title: B("Work it out again, Export, Import, Place a new hire", "Tính lại, Xuất ra, Nhập vào, Xếp lương người mới"),
          body: B("None of these is a pay rise. Place a new hire suggests a starting salary inside the band.",
                  "Không nút nào là tăng lương. Xếp lương người mới gợi ý mức lương khởi điểm nằm trong khoảng."),
        },
      },
      {
        key: "picture", anchor: "pp-band-picture", act: "observe",
        say: {
          title: B("A range per job, a dot per person", "Mỗi công việc một khoảng, mỗi người một chấm"),
          body: B("A dot outside its range is somebody paid below or above their band. Dragging an edge shows the cost before you let go.",
                  "Chấm nằm ngoài khoảng là người đang được trả dưới hoặc trên khoảng lương. Kéo mép cho thấy chi phí trước khi bạn thả tay."),
        },
      },
      {
        key: "health", anchor: "pp-health", act: "observe",
        say: {
          title: B("Worth knowing", "Đáng biết"),
          body: B("Five checks read for you: below the band, above it, newer people paid more, a manager paid less, and how wide each band has become.",
                  "Năm phép kiểm tra đã đọc sẵn: dưới khoảng, trên khoảng, người mới được trả cao hơn, quản lý được trả thấp hơn, và mỗi khoảng lương đã rộng ra bao nhiêu."),
        },
      },
    ],
  },

  /* --------------------------------------------------------- sc_payreview */
  {
    key: "sc_payreview",
    icon: "trending-up",
    line: "people",
    modes: ["watch", "try"],
    screens: ["payreview"],
    name: B("Run a pay review", "Thực hiện một đợt xét lương"),
    tagline: B("Fill the worksheet from the guidance, watch the budget, calibrate — and see who signs.",
               "Điền bảng tính theo hướng dẫn, theo dõi ngân sách, cân chỉnh — và xem ai phê duyệt."),
    entry: { nav: "payreview", screen: "payreview" },
    steps: [
      {
        key: "opentab", anchor: "pp-tab-review", nav: "payreview", act: "click", guard: false, modes: ["watch"],
        say: {
          kicker: B("People › Pay", "Con người › Lương"),
          title: B("The Review tab", "Tab Xét lương"),
          body: B("I open the Review tab. Switching a tab only changes what you are looking at.",
                  "Tôi mở tab Xét lương. Chuyển tab chỉ đổi thứ bạn đang xem."),
        },
      },
      {
        key: "list", anchor: "pp-reviews", nav: "payreview", screen: "payreview", act: "observe",
        say: {
          kicker: B("People › Pay › Review", "Con người › Lương › Xét lương"),
          title: B("Pay reviews", "Đợt xét lương"),
          body: B("Every review, and New review to start one. Set up guidance says what each score should earn.",
                  "Mọi đợt xét lương, và Đợt xét lương mới để bắt đầu. Thiết lập hướng dẫn nói mỗi mức điểm nên được tăng bao nhiêu."),
          tip: B("I only read. Nothing is sent or applied by this walkthrough.", "Tôi chỉ đọc. Lượt hướng dẫn này không gửi hay áp dụng gì."),
        },
      },
      {
        key: "stepper", anchor: "pp-stepper", screen: "payreview", act: "observe", modes: ["try"],
        say: {
          title: B("Who signs it", "Ai phê duyệt"),
          body: B("Being written, With HR, With finance, With the CEO, Approved, Applied. Any step can send it back with a reason.",
                  "Đang soạn, Đang ở nhân sự, Đang ở tài chính, Đang ở tổng giám đốc, Đã duyệt, Đã áp dụng. Bước nào cũng có thể trả lại kèm lý do."),
        },
      },
      {
        key: "openone", anchor: "pp-reviews", act: "observe", modes: ["watch"],
        say: {
          title: B("Open a review", "Mở một đợt xét lương"),
          body: B("An open review shows its stepper — HR, finance, the CEO — a worksheet with a row per person, the budget meter and Calibration. Approved is not paid: Apply writes the new pay. Try it in the practice company to see one open.",
                  "Một đợt xét lương đang mở hiện thanh các bước — nhân sự, tài chính, tổng giám đốc — một bảng tính mỗi người một dòng, thước đo ngân sách và Cân chỉnh. Đã duyệt chưa phải là đã trả: Áp dụng mới ghi lương mới. Hãy thử trong công ty thực hành để xem một đợt đang mở."),
        },
      },
      {
        key: "guidance", anchor: "rep-pr-guide", screen: "payreview", act: "click", guard: false, modes: ["try"],
        say: {
          title: B("Fill it from the guidance", "Điền theo hướng dẫn"),
          body: B("Press Use the guidance. Every rise is filled from the scores; a person below their band gets more.",
                  "Bấm Dùng hướng dẫn. Mọi mức tăng được điền theo điểm đánh giá; người dưới khoảng lương được tăng nhiều hơn."),
        },
      },
      {
        key: "worksheet", anchor: "pp-worksheet", screen: "payreview", act: "observe", modes: ["try"],
        say: {
          title: B("A row per person", "Mỗi người một dòng"),
          body: B("Score, in the band, paid now, guidance, rise, new pay and a year's cost. The filters find who is not scored or paid below the band.",
                  "Điểm, trong khoảng lương, đang được trả, hướng dẫn, mức tăng, lương mới và chi phí cả năm. Bộ lọc tìm ai chưa chấm điểm hoặc được trả dưới khoảng lương."),
        },
      },
      {
        key: "meters", anchor: "pp-meters", screen: "payreview", act: "observe", modes: ["try"],
        say: {
          title: B("Budget, Fairness, Scores", "Ngân sách, Công bằng, Điểm đánh giá"),
          body: B("The budget meter fills as rises go in. Over budget, the review cannot be sent for approval.",
                  "Thước đo ngân sách đầy dần khi thêm các mức tăng. Vượt ngân sách thì không gửi duyệt được."),
        },
      },
      {
        key: "calibrate", anchor: "rep-pr-cal", screen: "payreview", act: "click", guard: false, modes: ["try"],
        say: {
          title: B("Open Calibration", "Mở Cân chỉnh"),
          body: B("Press Calibration: each rise is marked in line, standing out, or breaking a limit.",
                  "Bấm Cân chỉnh: mỗi mức tăng được đánh dấu là ngang với người khác, nổi bật, hay vượt giới hạn."),
        },
      },
      {
        key: "actions", anchor: "pp-review-actions", screen: "payreview", act: "observe", modes: ["try"],
        say: {
          title: B("Send for approval, then Apply", "Gửi duyệt, rồi Áp dụng"),
          body: B("Approved is the last signature. Apply writes the new pay onto the records, and the next pay run reads it.",
                  "Đã duyệt là chữ ký cuối. Áp dụng ghi lương mới vào hồ sơ, và đợt lương kế tiếp đọc nó."),
        },
      },
    ],
  },

  /* ------------------------------------------------------ sc_decisionroom */
  {
    key: "sc_decisionroom",
    icon: "sliders",
    line: "people",
    modes: ["watch"],
    screens: ["decisionroom"],
    name: B("Try next year in the Decision Room", "Thử trước năm sau ở Phòng quyết định"),
    tagline: B("Presets, levers, results and the exact cost — nothing here changes payroll.",
               "Phương án có sẵn, cần gạt, kết quả và chi phí chính xác — không có gì ở đây thay đổi bảng lương."),
    entry: { nav: "decisionroom" },
    steps: [
      {
        key: "head", anchor: "dr-head", nav: "decisionroom", act: "observe",
        say: {
          kicker: B("People › Plan", "Con người › Kế hoạch"),
          title: B("See the year before you commit to it", "Nhìn thấy cả năm trước khi cam kết"),
          body: B("Undo, Reset and Save plan at the top. Everything below is a question you can ask of next year.",
                  "Hoàn tác, Đặt lại và Lưu kế hoạch ở trên. Mọi thứ bên dưới là một câu hỏi bạn đặt cho năm sau."),
          tip: B("I only read. Nothing is saved or proposed by this walkthrough.", "Tôi chỉ đọc. Lượt hướng dẫn này không lưu hay đề xuất gì."),
        },
      },
      {
        key: "levers", anchor: "dr-levers", act: "observe",
        say: {
          title: B("What if we…", "Nếu chúng ta…"),
          body: B("Start from a preset, then move the levers: people, a rise, overtime, leavers. Every result follows at once.",
                  "Bắt đầu từ một phương án có sẵn, rồi xoay các cần gạt: con người, tăng lương, tăng ca, người nghỉ. Mọi kết quả thay đổi theo ngay."),
        },
      },
      {
        key: "goals", anchor: "dr-goals", act: "observe",
        say: {
          title: B("Your definition of a good year", "Định nghĩa của bạn về một năm tốt"),
          body: B("Set goals, and the room scores every plan against them.", "Đặt mục tiêu, và căn phòng chấm điểm mọi kế hoạch theo đó."),
        },
      },
      {
        key: "results", anchor: "dr-results", act: "observe",
        say: {
          title: B("Four ways to read a plan", "Bốn cách đọc một kế hoạch"),
          body: B("Work & shifts, Why profit changed, People & pay, Room to hire.", "Công việc & ca làm, Vì sao lợi nhuận thay đổi, Con người & lương, Dư địa tuyển dụng."),
        },
      },
      {
        key: "compare", anchor: "dr-compare", act: "observe",
        say: {
          title: B("Compare, then press Exact cost", "So sánh, rồi bấm Chi phí chính xác"),
          body: B("Saved plans sit side by side. Exact cost runs one through the real pay scheme and says how far the estimate was off.",
                  "Các kế hoạch đã lưu nằm cạnh nhau. Chi phí chính xác chạy một kế hoạch qua chương trình lương thật và cho biết ước tính lệch bao nhiêu."),
        },
      },
    ],
  },

  /* ------------------------------------------------------------ sc_hiring */
  {
    key: "sc_hiring",
    icon: "briefcase",
    line: "lifecycle",
    modes: ["watch", "try"],
    screens: ["hiring", "hiring_request"],
    name: B("Raise a hiring request", "Đề xuất tuyển dụng"),
    tagline: B("The Hiring board, a request with its budget, and who signs it.",
               "Bảng Tuyển dụng, một đề xuất kèm ngân sách, và ai phê duyệt."),
    entry: { nav: "hiring", screen: "hiring" },
    steps: [
      {
        key: "numbers", anchor: "hi-numbers", nav: "hiring", screen: "hiring", act: "observe",
        say: {
          kicker: B("Lifecycle › Hiring", "Vòng đời nhân sự › Tuyển dụng"),
          title: B("What needs you", "Việc gì cần bạn"),
          body: B("Awaiting sign-off, Waiting on you, Over budget, interviews this week, opinions late.",
                  "Chờ phê duyệt, Đang chờ bạn, Vượt ngân sách, phỏng vấn tuần này, ý kiến đang trễ."),
          tip: B("I only read. Nothing is raised or sent by this walkthrough.", "Tôi chỉ đọc. Lượt hướng dẫn này không đề xuất hay gửi gì."),
        },
      },
      {
        key: "steps", anchor: "hi-steps", screen: "hiring", act: "observe",
        say: {
          title: B("Four steps for every role", "Bốn bước cho mọi vị trí"),
          body: B("Request & approve, Prepare & publish, Meet your candidates, Welcome aboard.",
                  "Đề xuất & phê duyệt, Chuẩn bị & đăng tin, Gặp ứng viên, Chào mừng gia nhập."),
        },
      },
      {
        key: "roles", anchor: "hi-row", screen: "hiring", act: "observe",
        say: {
          title: B("Step X of 4, and Next", "Bước X của 4, và Tiếp theo"),
          body: B("Each role's card says its step and the one thing that moves it on. With no request raised yet, this is where the board says so.",
                  "Thẻ của mỗi vị trí ghi bước hiện tại và một việc giúp nó đi tiếp. Khi chưa có đề xuất nào, bảng nói điều đó ngay tại đây."),
        },
      },
      {
        key: "raise", anchor: "hi-raise", screen: "hiring", act: "click", guard: false, modes: ["try"],
        say: {
          title: B("Press Raise a hiring request", "Bấm Đề xuất tuyển dụng"),
          body: B("Asking comes before advertising.", "Xin phép đi trước đăng tin."),
        },
      },
      {
        key: "raisewatch", anchor: "hi-raise", screen: "hiring", act: "observe", modes: ["watch"],
        say: {
          title: B("Raise a hiring request", "Đề xuất tuyển dụng"),
          body: B("This opens a short wizard: the role, responsibilities, the interview plan, and the budget. I will not press it.",
                  "Nút này mở một trình hướng dẫn ngắn: vị trí, trách nhiệm, kế hoạch phỏng vấn, và ngân sách. Tôi sẽ không bấm."),
        },
      },
      {
        key: "wizard", anchor: "hi-wizard", screen: "hiring_request", act: "observe", modes: ["try"],
        say: {
          title: B("Let's shape your next hire", "Hãy cùng phác thảo vị trí tuyển dụng tiếp theo"),
          body: B("Four tabs, ending with Budget & review: the salary set against the budget before anybody signs.",
                  "Bốn tab, cuối cùng là Ngân sách & xem lại: mức lương đặt cạnh ngân sách trước khi ai đó phê duyệt."),
        },
      },
      {
        key: "route", anchor: "rep-hi-route", screen: "hiring_request", act: "observe", modes: ["try"],
        say: {
          title: B("Manager, HR lead — Finance only if over budget", "Quản lý, trưởng nhân sự — Tài chính chỉ khi vượt ngân sách"),
          body: B("Sent for approval, it arrives in their Home › Approvals.", "Khi gửi phê duyệt, nó đến Trang chủ › Phê duyệt của họ."),
        },
      },
      {
        key: "send", anchor: "rep-hi-send", screen: "hiring_request", act: "click", guard: true, modes: ["try"],
        say: {
          title: B("Send for approval", "Gửi phê duyệt"),
          body: B("On your own Payobook this sends the request. Here it sends nothing.", "Trên Payobook của bạn, nút này gửi đề xuất đi. Ở đây nó không gửi gì cả."),
        },
      },
    ],
  },

  /* ----------------------------------------------------------- sc_joiners */
  {
    key: "sc_joiners",
    icon: "user-plus",
    line: "lifecycle",
    modes: ["watch"],
    screens: ["joiners"],
    name: B("Get ready for a new joiner", "Chuẩn bị cho nhân viên mới"),
    tagline: B("Who starts soon, who still has no buddy, and what is left before day one.",
               "Ai sắp vào làm, ai chưa có người đồng hành, và việc gì còn lại trước ngày đầu."),
    entry: { nav: "joiners" },
    steps: [
      {
        key: "numbers", anchor: "nj-numbers", nav: "joiners", act: "observe",
        say: {
          kicker: B("Lifecycle › New joiners", "Vòng đời nhân sự › Nhân viên mới"),
          title: B("Everyone starting soon", "Những người sắp vào làm"),
          body: B("Joining this week, Already started, Still without a buddy, Steps overdue, and those who said they are struggling.",
                  "Vào làm tuần này, Đã bắt đầu làm việc, Chưa có người đồng hành, Bước quá hạn, và những người cho biết đang gặp khó khăn."),
          tip: B("I only read. Nothing is sent by this walkthrough.", "Tôi chỉ đọc. Lượt hướng dẫn này không gửi gì."),
        },
      },
      {
        key: "steps", anchor: "nj-steps", act: "observe",
        say: {
          title: B("Getting ready, Settling in, Checklist done", "Đang chuẩn bị, Đang hòa nhập, Đã xong danh mục"),
          body: B("Press a step to see only the people on it.", "Bấm một bước để chỉ xem những người đang ở đó."),
        },
      },
      {
        key: "list", anchor: "nj-list", act: "observe",
        say: {
          title: B("A card per person", "Mỗi người một thẻ"),
          body: B("Open a card for what is still to do, what is done, and the conversations so far — and give them a buddy if they have none. With nobody starting soon, the board says so here.",
                  "Mở một thẻ để xem việc còn phải làm, việc đã xong, và các cuộc trao đổi — và chọn người đồng hành nếu họ chưa có. Khi không ai sắp vào làm, bảng nói điều đó tại đây."),
        },
      },
    ],
  },

  /* ------------------------------------------------------------- sc_exits */
  {
    key: "sc_exits",
    icon: "log-out",
    line: "lifecycle",
    modes: ["watch", "try"],
    screens: ["exits"],
    name: B("See someone out, and settle them", "Tiễn một người nghỉ, và quyết toán"),
    tagline: B("The four desks, the handover, and the final settlement that waits for all of them.",
               "Bốn phòng ban, phần bàn giao, và quyết toán chờ đủ tất cả."),
    entry: { nav: "exits", screen: "exits" },
    steps: [
      {
        key: "numbers", anchor: "ex2-numbers", nav: "exits", screen: "exits", act: "observe",
        say: {
          kicker: B("Lifecycle › Exits", "Vòng đời nhân sự › Nghỉ việc"),
          title: B("Everyone on their way out", "Những người sắp rời công ty"),
          body: B("Leaving this month, Last day has passed, Settlements held up, Clearances still open, Items not back yet.",
                  "Nghỉ việc trong tháng này, Đã qua ngày làm việc cuối, Quyết toán bị vướng, Xác nhận bàn giao còn mở, Tài sản chưa trả lại."),
          tip: B("I only read. Nothing is closed by this walkthrough.", "Tôi chỉ đọc. Lượt hướng dẫn này không chốt gì."),
        },
      },
      {
        key: "steps", anchor: "ex2-steps", screen: "exits", act: "observe",
        say: {
          title: B("Notice, signing off, ready, settled", "Báo trước, xác nhận bàn giao, sẵn sàng, đã quyết toán"),
          body: B("The four steps every leaver walks.", "Bốn bước mọi người nghỉ việc đều đi qua."),
        },
      },
      {
        key: "card", anchor: "rep-ex-card", screen: "exits", act: "click", guard: false, modes: ["try"],
        say: {
          title: B("Open Hạnh's card", "Mở thẻ của Hạnh"),
          body: B("Her last day has passed. Press her card to see who has signed her off.", "Ngày làm cuối của chị đã qua. Bấm vào thẻ để xem ai đã xác nhận bàn giao."),
        },
      },
      {
        key: "cards", anchor: "ex2-list", screen: "exits", act: "observe", modes: ["watch"],
        say: {
          title: B("A card per leaver", "Mỗi người nghỉ một thẻ"),
          body: B("Each card shows Signed off by: IT, HR, Finance and Admin. Open one for the settlement, which waits for all four. With nobody leaving, the board says so here.",
                  "Mỗi thẻ hiện Được ký tắt bởi: IT, Nhân sự, Tài chính và Quản trị viên. Mở một thẻ để xem quyết toán, vốn chờ đủ cả bốn. Khi không ai nghỉ, bảng nói điều đó tại đây."),
        },
      },
      {
        key: "clearance", anchor: "ex2-clearance", screen: "exits", act: "observe", modes: ["try"],
        say: {
          title: B("Signed off by IT, HR, Finance, Admin", "Được ký tắt bởi IT, Nhân sự, Tài chính, Quản trị viên"),
          body: B("One light per desk. A dark one is the desk still waiting for something back.",
                  "Mỗi phòng ban một đèn. Đèn chưa sáng là phòng ban vẫn đang chờ lấy lại một thứ gì đó."),
        },
      },
      {
        key: "settle", anchor: "ex2-settle", screen: "exits", act: "observe", modes: ["try"],
        say: {
          title: B("The final settlement waits for all four", "Quyết toán cuối cùng chờ đủ cả bốn"),
          body: B("Close settlement becomes available when every desk has signed. The payment itself is made from Pay Run › Settle.",
                  "Chốt quyết toán bấm được khi mọi phòng ban đã ký. Bản thân khoản chi được thực hiện từ Đợt lương › Quyết toán."),
        },
      },
    ],
  },

  /* --------------------------------------------------------- sc_probation */
  {
    key: "sc_probation",
    icon: "hourglass",
    line: "lifecycle",
    modes: ["watch"],
    screens: ["probation"],
    name: B("End a trial with a decision", "Kết thúc thử việc bằng một quyết định"),
    tagline: B("Every trial running, colleagues' answers, and the decision before the end date.",
               "Mọi đợt thử việc đang chạy, câu trả lời của đồng nghiệp, và quyết định trước ngày kết thúc."),
    entry: { nav: "probation" },
    steps: [
      {
        key: "numbers", anchor: "pr-numbers", nav: "probation", act: "observe",
        say: {
          kicker: B("Lifecycle › Probation", "Vòng đời nhân sự › Thử việc"),
          title: B("Ending within a week comes first", "Kết thúc trong vòng một tuần là việc đầu tiên"),
          body: B("In a trial period, Reviews running, Waiting on a decision, Answers overdue, Ending within a week.",
                  "Đang thử việc, Đánh giá đang chạy, Đang chờ quyết định, Câu trả lời quá hạn, Kết thúc trong vòng một tuần."),
          tip: B("I only read. Nothing is decided by this walkthrough.", "Tôi chỉ đọc. Lượt hướng dẫn này không quyết định gì."),
        },
      },
      {
        key: "steps", anchor: "pr-steps", act: "observe",
        say: {
          title: B("Five steps to an outcome", "Năm bước tới kết quả"),
          body: B("Choose peers, Gather perspectives, Manager conversation, HR & leadership review, Share the outcome.",
                  "Chọn đồng nghiệp, Thu thập ý kiến, Trao đổi với quản lý, Nhân sự và lãnh đạo xem xét, Thông báo kết quả."),
        },
      },
      {
        key: "list", anchor: "pr-list", act: "observe",
        say: {
          title: B("Open a card to decide", "Mở một thẻ để quyết định"),
          body: B("Inside: colleagues asked and who answered, then Confirm them, Extend the trial or Do not confirm. With nobody on a trial, the board says so here.",
                  "Bên trong: đồng nghiệp được hỏi và ai đã trả lời, rồi Xác nhận chính thức, Kéo dài thử việc hoặc Không xác nhận. Khi không ai đang thử việc, bảng nói điều đó tại đây."),
        },
      },
    ],
  },

  /* ----------------------------------------------------------- sc_wftoday */
  {
    key: "sc_wftoday",
    icon: "sun",
    line: "workforce",
    modes: ["watch"],
    screens: ["wftoday"],
    name: B("A day in Workforce", "Một ngày ở Lực lượng lao động"),
    tagline: B("Who is in today, and everything the Needs you panel is holding for you.",
               "Hôm nay ai có mặt, và mọi việc khung Cần bạn đang giữ cho bạn."),
    entry: { nav: "wftoday" },
    steps: [
      {
        key: "today", anchor: "wf-today", nav: "wftoday", act: "observe",
        say: {
          kicker: B("Workforce › Today", "Lực lượng lao động › Hôm nay"),
          title: B("Who is in, today", "Hôm nay ai có mặt"),
          body: B("On shift, Late, Not started, Checked out, On leave — for the teams you look after.",
                  "Theo ca, Trễ, Chưa bắt đầu, Đã về, Đang nghỉ phép — cho các nhóm bạn phụ trách."),
          tip: B("I only read. Nothing is approved by this walkthrough.", "Tôi chỉ đọc. Lượt hướng dẫn này không duyệt gì."),
        },
      },
      {
        key: "needs", anchor: "wf-needs", act: "observe",
        say: {
          title: B("Needs you", "Cần bạn"),
          body: B("Everything waiting for you, beside every Workforce tab. My team or Organisation decides whose.",
                  "Mọi việc đang chờ bạn, nằm cạnh mọi tab của Lực lượng lao động. Đội của tôi hoặc Tổ chức quyết định là của ai."),
        },
      },
      {
        key: "tabs", anchor: "wf-tabs", act: "observe",
        say: {
          title: B("The week, left to right", "Cả tuần, từ trái sang phải"),
          body: B("Today, Schedule, Time, Time Off, Overtime, Trips, Approvals — and Close, where the week is locked for payroll.",
                  "Hôm nay, Lịch ca, Chấm công, Nghỉ phép, Tăng ca, Công tác, Phê duyệt — và Chốt kỳ, nơi tuần được khoá cho bảng lương."),
        },
      },
    ],
  },

  /* ------------------------------------------------------------ sc_wftime */
  {
    key: "sc_wftime",
    icon: "clock",
    line: "workforce",
    modes: ["watch"],
    screens: ["wftime", "wftimeoff", "wfovertime"],
    name: B("Time, leave and overtime", "Chấm công, nghỉ phép và tăng ca"),
    tagline: B("Exceptions to fix, leave to decide, overtime to approve inside its limits.",
               "Ngoại lệ cần xử lý, đơn nghỉ cần quyết định, tăng ca cần duyệt trong giới hạn."),
    entry: { nav: "wftime" },
    steps: [
      {
        key: "time", anchor: "wf-time", nav: "wftime", act: "observe",
        say: {
          kicker: B("Workforce › Time", "Lực lượng lao động › Chấm công"),
          title: B("Timeline, Week Grid, Exceptions, Import", "Dòng thời gian, Lưới tuần, Ngoại lệ, Nhập"),
          body: B("Exceptions are the days that did not add up. Left alone, each becomes a flag on Close.",
                  "Ngoại lệ là những ngày không khớp. Nếu để đó, mỗi ngoại lệ thành một cờ cảnh báo ở Chốt kỳ."),
          tip: B("I only read. Nothing is approved by this walkthrough.", "Tôi chỉ đọc. Lượt hướng dẫn này không duyệt gì."),
        },
      },
      {
        key: "leave", anchor: "wf-leave-queue", nav: "wftimeoff", screen: "wftimeoff", act: "observe",
        say: {
          kicker: B("Workforce › Time Off", "Lực lượng lao động › Nghỉ phép"),
          title: B("The approval queue", "Hàng chờ phê duyệt"),
          body: B("Leave waiting for a decision. Apply on behalf files leave for someone who cannot.",
                  "Đơn nghỉ chờ quyết định. Đăng ký thay nộp đơn cho người không tự làm được."),
        },
      },
      {
        key: "overtime", anchor: "wf-ot-queue", nav: "wfovertime", screen: "wfovertime", act: "observe",
        say: {
          kicker: B("Workforce › Overtime", "Lực lượng lao động › Tăng ca"),
          title: B("Overtime waiting for approval", "Tăng ca chờ duyệt"),
          body: B("Each request with its day and hours. A near-the-limit mark is a warning, not a block.",
                  "Mỗi yêu cầu kèm ngày và số giờ. Dấu gần giới hạn là lời cảnh báo, không phải điều chặn."),
        },
      },
      {
        key: "rules", anchor: "wf-ot-rules", act: "observe",
        say: {
          title: B("The limits", "Các giới hạn"),
          body: B("The monthly and yearly limits your company works to. A request past one is marked, never quietly approved.",
                  "Giới hạn theo tháng và theo năm công ty bạn áp dụng. Yêu cầu vượt một giới hạn sẽ được đánh dấu, không bao giờ được duyệt âm thầm."),
        },
      },
    ],
  },

  /* ----------------------------------------------------------- sc_wfclose */
  {
    key: "sc_wfclose",
    icon: "lock",
    line: "workforce",
    modes: ["watch", "try"],
    screens: ["wfclose"],
    name: B("Close the week", "Chốt tuần"),
    tagline: B("Fix or approve every flag, read the handoff, then lock the week for payroll.",
               "Điều chỉnh hoặc duyệt mọi cờ, đọc phần chuyển giao, rồi khoá tuần cho bảng lương."),
    entry: { nav: "wfclose", screen: "wfclose" },
    steps: [
      {
        key: "head", anchor: "wf-close", nav: "wfclose", screen: "wfclose", act: "observe",
        say: {
          kicker: B("Workforce › Close", "Lực lượng lao động › Chốt kỳ"),
          title: B("The week, and how many flags are left", "Tuần này, và còn bao nhiêu cờ"),
          body: B("Payroll trusts a locked week. This is where it is made trustworthy.", "Bảng lương tin vào một tuần đã khoá. Đây là nơi làm cho nó đáng tin."),
          tip: B("I only read. Nothing is locked by this walkthrough.", "Tôi chỉ đọc. Lượt hướng dẫn này không khoá gì."),
        },
      },
      {
        key: "flags", anchor: "wf-close-flags", screen: "wfclose", act: "observe",
        say: {
          title: B("Every day that did not add up", "Mỗi ngày không khớp"),
          body: B("Fix a day that is wrong; Approve as-is only what really happened. Review all walks one kind together.",
                  "Điều chỉnh ngày bị sai; chỉ Phê duyệt nguyên trạng những gì thật sự đã xảy ra. Xem lại tất cả đi qua một loại cờ cùng lúc."),
        },
      },
      {
        key: "fix", anchor: "rep-wf-fix", screen: "wfclose", act: "click", guard: true, modes: ["try"],
        say: {
          title: B("Fix Hùng's Tuesday", "Điều chỉnh ngày thứ Ba của Hùng"),
          body: B("He forgot to check out. Fix opens the day to put in the real time — on your own Payobook that writes the correction.",
                  "Anh quên chấm giờ ra. Điều chỉnh mở ngày đó để nhập giờ thật — trên Payobook của bạn, việc đó ghi lại phần sửa."),
        },
      },
      {
        key: "handoff", anchor: "wf-close-handoff", screen: "wfclose", act: "observe",
        say: {
          title: B("Payroll handoff", "Chuyển giao tiền lương"),
          body: B("Regular hours, Overtime, Bonus hours and an estimated gross: what payroll will receive.",
                  "Giờ thông thường, Tăng ca, Giờ thưởng và tổng thu nhập ước tính: những gì bảng lương sẽ nhận."),
        },
      },
      {
        key: "lock", anchor: "wf-close-lock", screen: "wfclose", act: "observe",
        say: {
          title: B("Lock week & send to payroll", "Khóa tuần và gửi vào bảng lương"),
          body: B("Grey until every flag is answered, and only for an attendance or payroll manager. Reopen… asks for a reason.",
                  "Xám cho tới khi mọi cờ được trả lời, và chỉ dành cho quản lý chấm công hoặc quản lý lương. Mở lại… sẽ hỏi lý do."),
        },
      },
    ],
  },

  /* ------------------------------------------------------------ sc_access */
  {
    key: "sc_access",
    icon: "key",
    line: "setup",
    modes: ["watch"],
    screens: ["access"],
    name: B("Access, and handing it over", "Quyền truy cập, và bàn giao"),
    tagline: B("Roles in plain words, See it as, and lending your access while you are away.",
               "Vai trò bằng lời dễ hiểu, See it as, và cho mượn quyền khi bạn vắng mặt."),
    entry: { nav: "access" },
    steps: [
      {
        key: "head", anchor: "ac-head", nav: "access", act: "observe",
        say: {
          kicker: B("Settings › Access & delegation", "Cài đặt › Quyền truy cập & uỷ quyền"),
          title: B("Who can do what", "Ai được làm gì"),
          body: B("Everyone can open this page. Giving roles and See it as are for access managers.",
                  "Ai cũng mở được trang này. Cấp vai trò và See it as dành cho người quản lý truy cập."),
          tip: B("I only read. Nothing is given or handed over by this walkthrough.", "Tôi chỉ đọc. Lượt hướng dẫn này không cấp hay bàn giao gì."),
        },
      },
      {
        key: "tabs", anchor: "ac-tabs", act: "observe",
        say: {
          title: B("Roles, People, Screens, Hand-overs", "Bốn tab: Roles, People, Screens, Hand-overs"),
          body: B("What can be given, what each person holds, who opens each screen, and what is lent for a while.",
                  "Những gì có thể cấp, mỗi người đang có gì, ai mở được từng màn hình, và những gì đang cho mượn tạm thời."),
        },
      },
      {
        key: "roles", anchor: "ac-rolecard", act: "observe",
        say: {
          title: B("A role in one sentence", "Một vai trò trong một câu"),
          body: B("Each card says what the role lets someone do, and who holds it.", "Mỗi thẻ nói vai trò đó cho phép làm gì, và ai đang có nó."),
        },
      },
      {
        key: "handover", anchor: "ac-handover", act: "observe",
        say: {
          title: B("Hand my access over", "Bàn giao quyền của tôi"),
          body: B("Who, what and until when. It is taken back automatically the morning after the end date. I will not press it.",
                  "Cho ai, quyền nào và đến khi nào. Quyền được tự động thu hồi vào sáng hôm sau ngày kết thúc. Tôi sẽ không bấm."),
        },
      },
    ],
  },

  /* ----------------------------------------------------------- sc_filings */
  {
    key: "sc_filings",
    icon: "file-text",
    line: "compliance",
    modes: ["watch"],
    screens: ["govreports", "filing_flow"],
    name: B("File the month's government reports", "Nộp các báo cáo nhà nước của tháng"),
    tagline: B("The filings your country asks for, and the three steps that make one.",
               "Các báo cáo quốc gia bạn yêu cầu, và ba bước để tạo một báo cáo."),
    entry: { nav: "govreports" },
    steps: [
      {
        key: "head", anchor: "gr-head", nav: "govreports", act: "observe",
        say: {
          kicker: B("Compliance › Filings", "Tuân thủ › Tờ khai"),
          title: B("The filings the law asks of you", "Các báo cáo pháp luật yêu cầu bạn"),
          body: B("The company and the month, then a tile per filing.", "Công ty và tháng, rồi mỗi báo cáo một ô."),
          tip: B("I only read. Nothing is generated by this walkthrough.", "Tôi chỉ đọc. Lượt hướng dẫn này không tạo gì."),
        },
      },
      {
        key: "countries", act: "observe",
        say: {
          title: B("One country at a time", "Mỗi lần một quốc gia"),
          body: B("When your companies pay in more than one country, chips above the tiles switch country. \"Coming soon\" means that country's module is not installed here — not that its filings do not exist.",
                  "Khi các công ty của bạn trả lương ở nhiều quốc gia, các nhãn phía trên các ô dùng để chuyển quốc gia. \"Sắp có\" nghĩa là mô-đun của quốc gia đó chưa được cài ở đây — không phải các báo cáo không tồn tại."),
        },
      },
      {
        key: "grid", anchor: "gr-grid", act: "observe",
        say: {
          title: B("Grouped by the office that reads them", "Nhóm theo cơ quan tiếp nhận"),
          body: B("Generate on a tile opens Generate a filing on its Scope step: check the company and the month, then Generate. Nothing is sent anywhere.",
                  "Tạo trên một ô mở Tạo hồ sơ ở bước Phạm vi: kiểm tra công ty và tháng, rồi Tạo. Không có gì được gửi đi."),
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
   hunting inside Pay Run. Learning is now its own destination — its own
   section, which is where a section that is about the whole product rather
   than one desk belongs.

   IA REDESIGN CYCLE 5 RENAMED AND RENUMBERED THAT SECTION. The rail is now five
   sections and eight items — Overview / OPERATE / UNDERSTAND / GROW / System —
   and this is GROW: the only section on the rail that is about the person
   using the product rather than about the payroll. Sequence 40, between
   UNDERSTAND (30) and System (50); the neighbours it used to be numbered
   against (Compliance 45, Planning 55) are retired sections now.

   THE NAME IS "Grow" AND NOT "Learning", and that is the same A2 ruling one
   step further on: gettext allows ONE msgstr per msgid, "Learn" already means
   "Học cùng Payobook" as the leaf's name, and "Learning" already means "Học
   tập" as the topbar suffix. A third word for the same idea would have been a
   third fight over the same two Vietnamese strings. "Grow" is a different
   claim — what the section is FOR rather than what is in it — so it takes its
   own msgid, "Phát triển".

   THE ICON IS `book-open` AND NOT `compass`. Cycle 5 put Workforce (Mission
   Control) on the same five-section rail, four rows above this one, and it has
   drawn a compass since P3b — two identical glyphs on an eight-item rail is a
   rail that reads as a mistake. `book-open` was ADDED to pb_sidebar's fixed
   icon set in the same cycle; the set is closed and an unknown name draws a
   plain circle with no error anywhere, which is why the two edits belong
   together.

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
    sequence: 40,
    showLabel: true,
    name: B("Grow", "Phát triển"),
  },
  leaf: {
    xmlid: "item_learn_journey",
    sequence: 10,
    icon: "book-open",
    // RIZE W2 E1. The rail opens the Learn HUB, whose first lens is the
    // Journey. The leaf claims BOTH tags, so the entry stays lit whether
    // somebody arrived through the rail or through one of the many places
    // that still open `action_learn_journey` by name (R126).
    actionXmlid: "pb_learn.action_learn_hub",
    actionTag: "learn_hub",
    matchTags: "learn_hub,learn_journey",
    name: B("Learn", "Học cùng Payobook"),
  },
};
