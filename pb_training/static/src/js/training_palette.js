/** @odoo-module **/
/**
 * The Training lens's doors.
 *
 *   1. **The Learning hub's eight lenses** (LEARNING L0, 2026-10-21).
 *      GROW › Learning (`pb_learning_hub`) ships no lens of its own; this
 *      module registers all eight into `LEARNING_LENSES`, because the
 *      dependency runs this way (this module depends on the hub, so the hub
 *      cannot import this one back). Training left Talent completely (owner
 *      decision LD3): nothing here registers into Talent's registry any more.
 *
 *          10 overview · 20 mine · 30 courses · 35 paths · 40 assigned ·
 *          50 required · 60 tests · 65 certificates · 70 claims · 75 skills ·
 *          80 numbers
 *
 *      LEARNING L5 gave Courses a third inner tab, OUTSIDE (the outside-course
 *      catalogue), Claims a second, REQUESTS (course requests; Overview's
 *      "Course requests waiting" arrives on it), and added SKILLS (75): each
 *      person against their job's skills — offered to the training team and
 *      to anybody who manages people (`probe`). Eleven items (twelve is the
 *      hard maximum, ledger L2).
 *
 *      LEARNING L4 gave Courses a second inner tab, SESSIONS (sessions,
 *      attendance, toolbox talks); Overview's "Sessions to close" and the
 *      command bar arrive on it (`pb_training_tab` = "sessions").
 *
 *      LEARNING L3 added PATHS (35): learning paths with their station
 *      lines; Overview's "Late on a path" arrives on the late filter
 *      (`pb_training_path_state`). Ten items — the rail target (ledger L2).
 *
 *      LEARNING L1 added CERTIFICATES (65): the register of every
 *      certificate and licence, arriving on a filter when Overview or a
 *      Numbers link asks for one (`pb_training_cert_filter`).
 *
 *      Courses, Assigned, Required and Claims are the SAME board with
 *      `startTab` / `tabs` props (the Hiring precedent); Assigned reads its
 *      inner tab from the arrival (`pb_training_tab`) so Overview's "More
 *      time requests" lands on the requests. Labels are one word or two and
 *      fit the 64px rail box in English and Vietnamese (ledger L2).
 *
 *      Gates: the training tiers, restated here because the Python/JS
 *      boundary cannot be imported across. `pb.training._can_read()`
 *      enforces the real one independently; this only decides whether a lens
 *      is OFFERED. MY LEARNING is every member of staff's (`base.group_user`).
 *
 *   2. **⌘K palette rows**, in the **3900** block — E's block in the Wave 2
 *      plan, after A's 3500. Every door is an XMLID and never a bare tag: a
 *      bare tag is synthesised with no action NAME, so anything returning
 *      through a breadcrumb lands on a crumb labelled "Unnamed".
 *
 *      The employee's own page is reached through an `ir.actions.act_url`
 *      record, because the palette contract knows exactly two doors — a
 *      client-action tag and an xmlid — and nothing else (the shape
 *      `pb_rnr.action_my_recognition` set for `/my/recognition`). That row is
 *      UNGATED: everybody in the company can be put on a course, so a gate on
 *      it would hide the page from exactly the people it is for.
 *
 * Every icon is from the shared `ic()` registry in pb_import_kit — no
 * module-local map, no emoji.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { LEARNING_LENSES, LEARNING_HUB_XMLID } from "@pb_learning_hub/js/learning_hub";
import { INSIGHTS_LENSES } from "@pb_insights_hub/js/insights_hub";
import { PbTrainingBoard } from "@pb_training/js/training_board";
import { PbTrainingNumbers } from "@pb_training/js/training_numbers";
import { PbLearningOverview, TRAINING_TAB_KEY, CERT_FILTER_KEY } from "@pb_training/js/learning_overview";
import { PbCertificatesLens } from "@pb_training/js/certificates_lens";
import { PbMyLearningLens } from "@pb_training/js/my_learning_lens";
import { PbTrainingTestsLens } from "@pb_training/js/training_tests_lens";
import { PbRequiredLens } from "@pb_training/js/required_lens";
import { REQ_TAB_KEY, REQ_STATE_KEY, REQ_PACK_KEY } from "@pb_training/js/required_settings";
import { PbPathsLens, PATH_STATE_KEY, TRAINING_TERM_KEY } from "@pb_training/js/paths_lens";
import { SESSION_STATE_KEY, SESSION_OPEN_KEY } from "@pb_training/js/sessions_lens";
import { PbSkillsLens } from "@pb_training/js/skills_lens";

const TRAINING_GATE = [
    "pb_training.group_training_user",
    "pb_training.group_training_manager",
    "pb_training.group_training_admin",
];

/* ------------------------------------------------- the Learning rail --- */
const lenses = registry.category(LEARNING_LENSES);

lenses.add("overview", {
    key: "overview",
    icon: "layoutGrid",
    label: _t("Overview"),
    title: _t("Training at a glance"),
    Component: PbLearningOverview,
    groups: TRAINING_GATE,
}, { sequence: 10 });

// Everybody's: the one tab a plain employee sees.
lenses.add("mine", {
    key: "mine",
    icon: "user",
    label: _t("My learning"),
    Component: PbMyLearningLens,
    groups: ["base.group_user"],
}, { sequence: 20 });

// LEARNING L4: Courses owns two inner tabs — Courses and Sessions. The
// arrival may ask for Sessions (Overview's "Sessions to close", the command
// bar), filtered on the sessions to close or opened on one session.
const COURSE_TABS = ["courses", "sessions", "outside"];
lenses.add("courses", {
    key: "courses",
    icon: "bookOpen",
    label: _t("Courses"),
    title: _t("Every course"),
    Component: PbTrainingBoard,
    groups: TRAINING_GATE,
    propsFromContext(ctx) {
        const c = ctx || {};
        const focus = c.pb_focus;
        const asked = c[TRAINING_TAB_KEY] || (COURSE_TABS.includes(focus) ? focus : "");
        return {
            startTab: COURSE_TABS.includes(asked) ? asked : "courses",
            tabs: COURSE_TABS,
            startSessionState: c[SESSION_STATE_KEY] === "to_close" ? "to_close" : "",
            startSession: Number(c[SESSION_OPEN_KEY]) || 0,
        };
    },
}, { sequence: 30 });

// LEARNING L3: learning paths. Overview's "Late on a path" arrives filtered.
lenses.add("paths", {
    key: "paths",
    icon: "route",
    label: _t("Paths"),
    title: _t("Learning paths"),
    Component: PbPathsLens,
    groups: TRAINING_GATE,
    propsFromContext(ctx) {
        const asked = ctx && ctx[PATH_STATE_KEY];
        return { startState: asked === "overdue" ? "overdue" : "" };
    },
}, { sequence: 35 });

// The arrival may ask for the "More time" tab (Overview's queue chip).
const ASSIGNED_TABS = ["assignments", "requests"];
lenses.add("assigned", {
    key: "assigned",
    icon: "userCheck",
    label: _t("Assigned"),
    title: _t("Who is on what, and more time"),
    Component: PbTrainingBoard,
    groups: TRAINING_GATE,
    propsFromContext(ctx) {
        const asked = ctx && ctx[TRAINING_TAB_KEY];
        return {
            startTab: ASSIGNED_TABS.includes(asked) ? asked : "assignments",
            tabs: ASSIGNED_TABS,
            // LEARNING L3: the path page's "Open their courses" searches a name.
            startTerm: (ctx && ctx[TRAINING_TERM_KEY]) || "",
        };
    },
}, { sequence: 40 });

// LEARNING L2: the Required lens is its own screen — Matrix · Rules · Day one
// · Comes round again. Arrivals may ask for a tab, a cell state (Overview's
// "Missing required training") or a country pack (Settings' "Review the
// rules"). The old board's Day one / Comes round again tabs live on inside
// it, read-only, as "from before".
const REQUIRED_TABS = ["matrix", "rules", "day_one", "recurring"];
lenses.add("required", {
    key: "required",
    icon: "listChecks",
    label: _t("Required"),
    title: _t("Who must hold what, and who is missing it"),
    Component: PbRequiredLens,
    groups: TRAINING_GATE,
    propsFromContext(ctx) {
        const c = ctx || {};
        const tab = c[REQ_TAB_KEY] || c[TRAINING_TAB_KEY];
        return {
            startTab: REQUIRED_TABS.includes(tab) ? tab : "matrix",
            startState: c[REQ_STATE_KEY] || "",
            startPack: c[REQ_PACK_KEY] || "",
        };
    },
}, { sequence: 50 });

lenses.add("tests", {
    key: "tests",
    icon: "fileCheck",
    label: _t("Tests"),
    title: _t("Tests and question bank"),
    Component: PbTrainingTestsLens,
    groups: TRAINING_GATE,
}, { sequence: 60 });

// LEARNING L1: the certificate register. Overview's chips arrive on a filter.
const CERT_FILTERS = ["expiring_30", "expiring_60", "expiring_90", "expired", "valid", "no_expiry", "renewed"];
lenses.add("certificates", {
    key: "certificates",
    icon: "award",
    label: _t("Certificates"),
    title: _t("Certificates and licences"),
    Component: PbCertificatesLens,
    groups: TRAINING_GATE,
    propsFromContext(ctx) {
        const asked = ctx && ctx[CERT_FILTER_KEY];
        return { startFilter: CERT_FILTERS.includes(asked) ? asked : "" };
    },
}, { sequence: 65 });

// LEARNING L5: Claims owns two inner tabs — Claims and Requests (course
// requests). Overview's "Course requests waiting" and the command bar arrive
// on Requests.
const CLAIM_TABS = ["claims", "course_requests"];
lenses.add("claims", {
    key: "claims",
    icon: "receipt",
    label: _t("Claims"),
    title: _t("Training claims and course requests"),
    Component: PbTrainingBoard,
    groups: TRAINING_GATE,
    propsFromContext(ctx) {
        const c = ctx || {};
        const asked = c[TRAINING_TAB_KEY] || (c.pb_focus === "course_requests" ? "course_requests" : "");
        return { startTab: CLAIM_TABS.includes(asked) ? asked : "claims", tabs: CLAIM_TABS };
    },
}, { sequence: 70 });

// LEARNING L5: skills against each job. Offered to the training team and to
// managers (their team only) — the probe asks the server.
lenses.add("skills", {
    key: "skills",
    icon: "sparkles",
    label: _t("Skills"),
    title: _t("Skills against each job, and the course that closes the gap"),
    Component: PbSkillsLens,
    groups: ["base.group_user"],
    probe: { model: "pb.training", method: "can_see_skills" },
}, { sequence: 75 });

lenses.add("numbers", {
    key: "numbers",
    icon: "barChart",
    label: _t("Numbers"),
    title: _t("Training numbers"),
    Component: PbTrainingNumbers,
    groups: TRAINING_GATE.concat(["base.group_system"]),
}, { sequence: 80 });

/* ---------------------------------------- Settings › HR › Learning (L6) ---
 * LEARNING L6 folded L2's "Required training" category into one "Learning"
 * category with five cards, each opening the Learning settings screen on its
 * own tab (Country packs is the L2 screen, embedded). The category names its
 * own group, so pb_settings needs no change; the registry key is written out
 * (not imported) so this module does not have to depend on pb_settings.
 * Training managers read the screen; only the head of training writes.
 */
registry.category("pb_settings_category").add("learning", {
    key: "learning",
    group: "hr",
    icon: "graduationCap",
    label: _t("Learning"),
    blurb: _t("The training pack, reminders, course feedback, country packs and day one."),
    groups: ["pb_training.group_training_manager", "pb_training.group_training_admin", "base.group_system"],
    cards: [
        { id: "report_pack", xmlid: "pb_training.action_pb_training_settings_pack", icon: "mail",
          label: _t("Report pack"), sub: _t("The training numbers by email, every week or month, and who gets them.") },
        { id: "reminders", xmlid: "pb_training.action_pb_training_settings_reminders", icon: "bell",
          label: _t("Reminders"), sub: _t("Who is reminded about a course or a certificate, and when.") },
        { id: "feedback", xmlid: "pb_training.action_pb_training_settings_feedback", icon: "messageSquare",
          label: _t("Feedback"), sub: _t("Asking people how a course was, and their manager whether it worked.") },
        { id: "country_packs", xmlid: "pb_training.action_pb_training_settings_packs", icon: "globe",
          label: _t("Country packs"), sub: _t("Country packs for Vietnam, India, Indonesia and Singapore.") },
        { id: "day_one", xmlid: "pb_training.action_pb_training_settings_day_one", icon: "sunrise",
          label: _t("Day one"), sub: _t("Courses and paths a new joiner gets on their first day.") },
    ],
}, { sequence: 47 });

/* ---------------------------------------------------------- command bar --- */
const palette = registry.category("pb_hub_palette");
const HUB_XMLID = LEARNING_HUB_XMLID;

palette.add("training_board", {
    id: "training_board",
    label: _t("Training"),
    sublabel: _t("Learning"),
    icon: "graduationCap",
    groups: TRAINING_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_training_board",
    action: { xmlid: HUB_XMLID, lens: "overview" },
    // R10: people looked for this under Talent until LEARNING L0.
    keywords: ["learn", "đào tạo", "talent", "learning", "học tập"],
}, { sequence: 3900 });

palette.add("training_courses", {
    id: "training_courses",
    label: _t("Courses"),
    sublabel: _t("Learning"),
    icon: "bookOpen",
    groups: TRAINING_GATE,
    requires: "pb_training_board",
    action: { xmlid: HUB_XMLID, lens: "courses" },
    keywords: ["training", "talent"],
}, { sequence: 3910 });

palette.add("training_tests", {
    id: "training_tests",
    label: _t("Tests and question bank"),
    sublabel: _t("Learning"),
    icon: "fileCheck",
    groups: TRAINING_GATE,
    requires: "pb_training_board",
    action: { xmlid: HUB_XMLID, lens: "tests" },
    keywords: ["training", "talent"],
}, { sequence: 3920 });

// UNGATED, and that is the point: everybody in the company can be put on a
// course, so this is the one row here that is for everybody. LEARNING L0:
// it opens Learning › My learning (was the portal page "My training").
palette.add("training_my", {
    id: "training_my",
    label: _t("My learning"),
    sublabel: _t("Learning"),
    icon: "user",
    requires: "pb_training_board",
    action: { xmlid: HUB_XMLID, lens: "mine" },
    keywords: ["my training", "training", "talent", "đào tạo của tôi"],
}, { sequence: 3930 });

// LEARNING L3: learning paths, from the command bar.
palette.add("training_paths", {
    id: "training_paths",
    label: _t("Learning paths"),
    sublabel: _t("Learning"),
    icon: "route",
    groups: TRAINING_GATE,
    requires: "pb_training_board",
    action: { xmlid: HUB_XMLID, lens: "paths" },
    keywords: ["path", "career", "programme", "lộ trình", "training", "talent"],
}, { sequence: 3935 });

// LEARNING L4: sessions and toolbox talks, from the command bar.
palette.add("training_sessions", {
    id: "training_sessions",
    label: _t("Training sessions"),
    sublabel: _t("Learning"),
    icon: "calendar",
    groups: TRAINING_GATE,
    requires: "pb_training_board",
    // The palette carries `focus` (never a context): Courses reads it.
    action: { xmlid: HUB_XMLID, lens: "courses", focus: "sessions" },
    keywords: ["session", "classroom", "toolbox", "attendance", "buổi học", "điểm danh", "training"],
}, { sequence: 3915 });

// LEARNING L5: the outside catalogue, course requests and skills.
palette.add("training_outside", {
    id: "training_outside",
    label: _t("Outside courses"),
    sublabel: _t("Learning"),
    icon: "graduationCap",
    groups: TRAINING_GATE,
    requires: "pb_training_board",
    action: { xmlid: HUB_XMLID, lens: "courses", focus: "outside" },
    keywords: ["outside", "provider", "catalogue", "external", "khóa học bên ngoài", "training"],
}, { sequence: 3916 });

palette.add("training_requests", {
    id: "training_requests",
    label: _t("Course requests"),
    sublabel: _t("Learning"),
    icon: "send",
    groups: TRAINING_GATE,
    requires: "pb_training_board",
    action: { xmlid: HUB_XMLID, lens: "claims", focus: "course_requests" },
    keywords: ["request", "ask", "course", "yêu cầu", "training"],
}, { sequence: 3961 });

palette.add("training_skills", {
    id: "training_skills",
    label: _t("Skills"),
    sublabel: _t("Learning"),
    icon: "sparkles",
    requires: "pb_training_board",
    action: { xmlid: HUB_XMLID, lens: "skills" },
    keywords: ["skill", "gap", "kỹ năng", "competency", "training"],
}, { sequence: 3965 });

// LEARNING L1: the register, from the command bar.
palette.add("training_certificates", {
    id: "training_certificates",
    label: _t("Certificates and licences"),
    sublabel: _t("Learning"),
    icon: "award",
    groups: TRAINING_GATE,
    requires: "pb_training_board",
    action: { xmlid: HUB_XMLID, lens: "certificates" },
    keywords: ["certificate", "licence", "license", "expiry", "chứng chỉ", "giấy phép", "training", "talent"],
}, { sequence: 3925 });

/* -------------------------------------------------------------- E2 rows ---
 * Still inside E's 3900 block; B1 starts at 3600 per the wave plan. Both are
 * XMLIDs, because a bare tag is synthesised with no action NAME and anything
 * returning through a breadcrumb then lands on a crumb labelled "Unnamed".
 */
palette.add("training_assignments", {
    id: "training_assignments",
    label: _t("Training assignments"),
    sublabel: _t("Learning"),
    icon: "userCheck",
    groups: TRAINING_GATE,
    requires: "pb_training_board",
    action: { xmlid: HUB_XMLID, lens: "assigned" },
    keywords: ["training", "talent"],
}, { sequence: 3940 });

palette.add("training_schedules", {
    id: "training_schedules",
    label: _t("Compliance schedules"),
    sublabel: _t("Learning"),
    icon: "repeat",
    groups: TRAINING_GATE,
    requires: "pb_training_board",
    action: { xmlid: HUB_XMLID, lens: "required" },
    keywords: ["training", "talent", "required", "matrix", "bắt buộc", "safety", "an toàn"],
}, { sequence: 3950 });

/* --------------------------------------------- E3, the Insights lens ----
 * `pb_insights_hub`'s four shipped lenses carry no sequence, so bolted-on
 * ones start at 20: P9 took Budget 20, A3 took Hiring 30, so Training takes
 * **40** and lands after them. That is also the right reading order — what a
 * role was budgeted to cost, how long it took to fill, and then what the
 * person was trained on once they arrived.
 *
 * ITS OWN GATE AND NOT THE HUB'S (R97). A trainer holds no analytics group
 * and a data analyst holds no training group, so this lens's readers are
 * genuinely not the hub's usual readers. `pb.training.analytics._can_read()`
 * enforces the real one independently; this only decides whether the lens is
 * OFFERED.
 *
 * "Training" is one word of eight characters. The lens rail's label box is
 * 60px and wraps between words but never inside one (R63), so what matters is
 * the longest WORD — the two labels that spilled ("Improvement",
 * "Recognition") were eleven characters with no break in them. It is also the
 * word the command bar uses for this module's Learning row, which is the
 * point: one thing, one name, wherever a reader meets it.
 */
registry.category(INSIGHTS_LENSES).add("training", {
    key: "training",
    icon: "graduationCap",
    label: _t("Training"),
    Component: PbTrainingNumbers,
    groups: TRAINING_GATE.concat(["base.group_system"]),
}, { sequence: 40 });

/* -------------------------------------------------------------- E3 rows ---
 * Still inside E's 3900 block; B1 starts at 3600 per the wave plan. Both are
 * XMLIDs, because a bare tag is synthesised with no action NAME and anything
 * returning through a breadcrumb then lands on a crumb labelled "Unnamed".
 */
palette.add("training_claims", {
    id: "training_claims",
    label: _t("Training claims"),
    sublabel: _t("Learning"),
    icon: "receipt",
    groups: TRAINING_GATE,
    requires: "pb_training_board",
    action: { xmlid: HUB_XMLID, lens: "claims" },
    keywords: ["training", "talent"],
}, { sequence: 3960 });

// The presence probe is the LENS's own action tag and not the board's: a
// build that shipped the board and not the numbers must not offer a door into
// a screen that is not there.
palette.add("training_numbers", {
    id: "training_numbers",
    label: _t("Training numbers"),
    sublabel: _t("Insights"),
    icon: "barChart",
    groups: TRAINING_GATE.concat(["base.group_system"]),
    requires: "pb_training_numbers",
    action: { xmlid: "pb_training.action_pb_training_numbers" },
}, { sequence: 3970 });
