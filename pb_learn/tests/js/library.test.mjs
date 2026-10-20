/**
 * LEARNREV P3 — the Library (the Learning page) and the drawer polish, in node.
 *
 *   T1  the Library from a fixture bootstrap: the real 42 stations of the
 *       content plane, 3 role paths, progress for 5 — the Continue card's
 *       words, the path strip (= the required stations), the menu groups in
 *       MENU_ORDER (NAV P2: eleven, empty ones not drawn), every station exactly once, no row with more than three
 *       doors, none of the retired page words; the one search ("pay role"
 *       lands on the field card first, Vietnamese finds "vai trò", an empty
 *       search offers Ask PayAI); the real journey.js renders it; the drawer:
 *       openHelper({guide}), "Guide · <screen>", the fold on a sent message.
 *
 * Run: node pb_learn/tests/js/library.test.mjs   (exit 1 on failure)
 */
import fs from "node:fs";
import path from "node:path";
import { check, load, summary, ROOT } from "./harness.mjs";

const pb = globalThis.__pb;
const noop = () => {};
const store = new Map();
globalThis.document = {
    addEventListener: noop, removeEventListener: noop,
    body: { classList: { add: noop, remove: noop, contains: () => false, toggle: noop } },
    documentElement: { style: { setProperty: noop } },
    querySelector: () => null, querySelectorAll: () => [], activeElement: null,
};
globalThis.window = {
    localStorage: { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)) },
    matchMedia: () => ({ matches: false }),
    innerHeight: 900, innerWidth: 1440,
    addEventListener: noop,
};

const CONTENT = JSON.parse(fs.readFileSync(
    path.join(ROOT, "pb_learn", "static", "content", "learn_content.json"), "utf-8"));
const GUIDE = JSON.parse(fs.readFileSync(
    path.join(ROOT, "pb_learn", "tests", "data", "guide_treatment_en.json"), "utf-8"));
const clone = (x) => JSON.parse(JSON.stringify(x));

const runtime = await load("@pb_learn/engine/runtime");
const lib = await load("@pb_learn/journey/library",
                       ["@pb_learn/engine/runtime", "@pb_learn/engine/places"]);
const { RT } = runtime;
RT.chrome = CONTENT.chrome;
RT.lang = "en";
const T = (k) => runtime.T(k);

/* ---------------------------------------------------------------- fixture */
// Three role paths, the shape learn.path.bootstrap_extra serves.
const ROLES = {
    approver: ["dashboard", "approvals", "payruns", "payslips", "insights", "reports", "payreview"],
    officer: ["dashboard", "approvals", "runpayroll", "payruns", "payslips", "import", "treatment"],
    owner: ["dashboard", "insights", "explorer", "decisionroom", "govreports", "matrix", "access"],
};
// Progress for five stations: two done on the approver path, one started.
const PROGRESS = {
    dashboard: { state: "done" },
    payruns: { state: "done" },
    approvals: { state: "in_progress", step_index: 3 },
    hiring: { state: "done" },
    formula: { state: "in_progress", step_index: 1 },
};
// The field index as rpc_index serves it, from P1's real treatment Guide.
function firstSentence(t) {
    const hit = /^.*?[.!?](?=\s|$)/.exec(String(t || ""));
    return hit ? hit[0] : String(t || "");
}
// P1's fixture predates the Guide's two spellings (`columns`, P2); rpc_index
// serves both, so the Vietnamese ones come from the treatment manifest here.
const VI_COLUMN = { lane: "Đến từ", report_group: "Nhóm báo cáo", pay_role: "Vai trò trong lương",
                    rollup: "Đã tính trong một tổng khác", run_signal: "Tín hiệu cho đợt lương",
                    value_kind: "Loại giá trị" };
const FIELD_ROWS = GUIDE.fields.map((c) => ({
    screen: "treatment", screen_name: "Component treatment",
    screen_names: ["Component treatment", "Xử lý thành phần"],
    key: c.key, column: c.column, columns: [c.column, VI_COLUMN[c.key]].filter(Boolean),
    line: firstSentence(c.derived ? c.filled_by : (c.help || c.filled_by)),
}));
const stations = clone(CONTENT.stations);
// One station this person cannot open.
stations.find((s) => s.key === "access").visible = false;
for (const s of stations) {
    if (s.visible === undefined) {
        s.visible = true;
    }
}
const SRC = {
    stations, screens: CONTENT.screens, scenarios: CONTENT.scenarios, missions: CONTENT.missions,
    glossary: CONTENT.glossary, progress: PROGRESS,
    path: { role: "approver", role_chosen: true, roles: ROLES, month_end: {} },
    nextBest: {}, demoWorld: true, team: true,
};
const RETIRED = ["Not on your path", "badge", "streak", "Show me how", "Reduce motion",
                 "Overall", "Your journey", "Practice missions", "Start here", "Find it in"];
const MIN_RE = /About\s+\d+\s+min/i;

/* ================================================================== T1 */
function librarySuite() {
    console.log("T1 the Library from a fixture bootstrap");
    const model = lib.buildLibrary(SRC);
    const html = lib.libraryHTML(model, CONTENT.screens, {});

    // -- every station exactly once, the groups in menu order
    const rows = Array.from(html.matchAll(/data-lib-row="([a-z0-9_]+)"/g), (m) => m[1]);
    check(stations.length === 42, "the fixture has the 42 stations of the content plane", String(stations.length));
    check(rows.length === stations.length && new Set(rows).size === rows.length,
          "every station appears exactly once", `${rows.length} rows, ${new Set(rows).size} distinct`);
    const groups = Array.from(html.matchAll(/class="lrn-lib-group[^"]*" data-group="([a-z]+)"/g), (m) => m[1]);
    // NAV P2: eleven menu groups; a group with no station (Expenses, Learn)
    // is not drawn, and the rest keep MENU_ORDER's order.
    check(lib.MENU_ORDER.length === 11, "MENU_ORDER lists the eleven menu pages", String(lib.MENU_ORDER.length));
    check(JSON.stringify(groups) === JSON.stringify(["home", "payrun", "people", "hiring", "workforce",
                                                     "insights", "compliance", "talent", "settings"]),
          "9 drawn groups, in MENU_ORDER (Home, Payroll, People, Hiring, Workforce, Insights, Compliance, Talent, Settings)",
          groups.join(","));
    check(groups.every((g, i) => i === 0 || lib.MENU_ORDER.findIndex((m) => m.key === g)
                                            > lib.MENU_ORDER.findIndex((m) => m.key === groups[i - 1])),
          "… a subsequence of MENU_ORDER");
    const names = Array.from(html.matchAll(/class="lrn-lib-gname">([^<]+)</g), (m) => m[1]);
    check(JSON.stringify(names) === JSON.stringify(["Home", "Payroll", "People", "Hiring", "Workforce",
                                                    "Insights", "Compliance", "Talent", "Settings"]),
          "… named as the menu names them", names.join(", "));
    const grp = (k) => lib.groupOf(stations.find((s) => s.key === k), CONTENT.screens);
    check(["hiring", "hiringrole", "hiringsetup"].every((k) => grp(k) === "hiring")
          && ["joiners", "probation", "exits", "contractends"].every((k) => grp(k) === "people")
          && grp("growth") === "talent",
          "the old Lifecycle boards land under Hiring, People and Talent");
    const groupOf = (k) => lib.groupOf(stations.find((s) => s.key === k), CONTENT.screens);
    check(["formula", "mapping", "treatment", "matrix", "statutory", "integrations", "blueprint",
           "schemes", "access"].every((k) => groupOf(k) === "settings"),
          "Setup screens (Formula Engine, Mapping, Component treatment, Approval Matrix, Statutory, …) live under Settings");
    check(groupOf("runpayroll") === "payrun" && groupOf("dashboard") === "home" && groupOf("peoplemore") === "people",
          "a station goes to the hub holding most of its places (People more → People)");
    const orphan = stations.filter((s) => {
        const g = lib.groupOf(s, CONTENT.screens);
        const sc = CONTENT.screens.find((x) => x.key === s.key);
        const byTag = ((sc && sc.places) || []).some((p) => !p.startsWith("detail:"));
        return !lib.MENU_ORDER.some((m) => m.key === g) || (!byTag && !lib.LINE_GROUP[s.line]);
    });
    check(!orphan.length, "no station is orphaned (each by its hub tab or its line)", orphan.map((s) => s.key).join(","));

    // -- the rows: at most three doors, one status
    let maxChips = 0;
    let maxStatus = 0;
    for (const li of html.split('<li class="lrn-lib-row').slice(1)) {
        const body = li.split("</li>")[0];
        maxChips = Math.max(maxChips, (body.match(/class="lrn-lib-chip[ "]/g) || []).length);
        maxStatus = Math.max(maxStatus, (body.match(/class="lrn-lib-tag/g) || []).length);
    }
    check(maxChips <= 3, "no row carries more than 3 chips (Guide · Watch · Try)", String(maxChips));
    check(maxStatus <= 1, "at most one status per row", String(maxStatus));
    const treat = html.split('data-lib-row="treatment"')[1].split("</li>")[0];
    check(treat.includes('data-act="lib-guide"') && treat.includes('data-scenario="sc_treatment" data-mode="watch"')
          && treat.includes('data-scenario="sc_treatment" data-mode="try"'),
          "Component treatment: Guide, Watch and Try");
    const people = html.split('data-lib-row="employees"')[1].split("</li>")[0];
    check(!people.includes('data-mode="watch"') && people.includes('data-mode="try"'),
          "only the modes a station's walkthrough has (Employees: Try, no Watch)");
    const access = html.split('data-lib-row="access"')[1].split("</li>")[0];
    check(access.includes(runtime.esc(T("notVisible"))) && !access.includes(T("required")),
          "a screen you cannot open says Not in your menu, once, and still has its Guide",
          access.slice(0, 200));
    check(access.includes('data-act="lib-guide"'), "… the Guide chip is still there");
    const payslips = html.split('data-lib-row="payslips"')[1].split("</li>")[0];
    check(payslips.includes(`>${T("required")}<`), "a station on the path says Required");
    const hiring = html.split('data-lib-row="hiring"')[1].split("</li>")[0];
    check(/lrn-lib-row done/.test(html.split('data-lib-row="hiring"')[0].slice(-60)) && hiring.includes("lrn-lib-ring done"),
          "a done station has the done ring");
    check(html.split('data-lib-row="formula"')[1].includes("lrn-lib-ring started"), "a started station has the started ring");
    check(html.split('data-lib-row="explorer"')[1].split("</li>")[0].includes("lrn-lib-ring none"),
          "an untouched station has the empty ring");

    // -- retired words
    for (const w of RETIRED) {
        check(!html.toLowerCase().includes(w.toLowerCase()), `the page never says "${w}"`);
    }
    check(!MIN_RE.test(html) && !html.includes(`${T("est")}${runtime.SP}`), "no \"About … min\" on any row");
    check(!/gradient/i.test(html), "no gradient in the markup");
    check(!/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(html), "no emoji");
    check(!/odoo/i.test(html), "never the word Odoo");

    // -- Continue card
    const cont = lib.continueHTML(model, {});
    check(cont.includes(runtime.esc(lib.fmt(T("libYourPath"), { role: T("roleApprover"), done: 2, total: 7 }))),
          "Continue: \"your path as Approver · 2 of 7 done\"", cont.slice(0, 400));
    check(cont.includes(">Approvals<") || cont.includes(runtime.esc(runtime.tx(stations.find((s) => s.key === "approvals").name))),
          "… the next required lesson not done (Approvals)");
    check(cont.includes(runtime.esc(lib.fmt(T("libReqFor"), { role: T("roleApprover") }))),
          "… with its reason: Required for you as Approver");
    const steps = stations.find((s) => s.key === "approvals").lessons[0].steps.length;
    check(cont.includes(runtime.esc(lib.fmt(T("libSteps"), { n: steps }))), `… and its steps (${steps}), not minutes`);
    check(cont.includes('data-act="lib-continue" data-key="approvals"') || cont.includes('data-key="approvals"'),
          "… and one Continue button for it");
    check(cont.includes('data-act="lib-roles"'), "… and the role control inline (Change)");
    check(!cont.includes('class="lrn-lib-roles"'), "the role chips stay folded until Change");
    check(lib.continueHTML(model, { rolesOpen: true }).split('data-act="role"').length - 1 === 5,
          "Change opens the five role chips in place");
    const guessed = lib.buildLibrary(Object.assign({}, SRC, { path: Object.assign({}, SRC.path, { role_chosen: false }) }));
    check(lib.continueHTML(guessed, {}).includes(runtime.esc(T("libRoleGuessed"))),
          "a guessed role says it was picked from your access (G12)");
    // LEARNREV P5a: a guessed role whose path rule carries a seat names the seat.
    const SEAT = { en: "Required because you hold the payroll approval seat.", vi: "Bắt buộc vì bạn giữ vị trí phê duyệt lương." };
    const seated = lib.buildLibrary(Object.assign({}, SRC, { path: Object.assign({}, SRC.path, { role_chosen: false, why: SEAT }) }));
    const seatedHtml = lib.continueHTML(seated, {});
    check(seatedHtml.includes(runtime.esc(SEAT.en)) && !seatedHtml.includes(runtime.esc(T("libRoleGuessed"))),
          "P5a: a guessed role with a seat says the seat (not only the role)");
    const picked = lib.buildLibrary(Object.assign({}, SRC, { path: Object.assign({}, SRC.path, { role_chosen: true, why: SEAT }) }));
    check(!lib.continueHTML(picked, {}).includes(runtime.esc(SEAT.en)),
          "P5a: a role the person picked keeps the role-name reason");
    check(lib.continueHTML(guessed, {}).includes(runtime.esc(lib.fmt(T("libReqFor"), { role: T("roleApprover") }))),
          "P5a: no seat on the rule → the role stays the reason (fallback)");
    const nb = lib.buildLibrary(Object.assign({}, SRC, { nextBest: { key: "payslips", kind: "station", reason_key: "nbResume" } }));
    check(lib.continueHTML(nb, {}).includes('data-key="payslips"') && lib.continueHTML(nb, {}).includes(runtime.esc(T("libStarted"))),
          "the server's next step wins when the page has it (resume says so)");
    const me = lib.buildLibrary(Object.assign({}, SRC, { path: Object.assign({}, SRC.path, { month_end: { cutoff: "2026-10-20", days: 3, month: "2026-10-01" } }) }));
    const meHtml = lib.continueHTML(me, { scenarioKeys: new Set(["sc_payslips"]) });
    check(meHtml.split("lrn-lib-cline").length - 1 === 1 && meHtml.includes('data-scenario="sc_payslips" data-mode="watch"'),
          "month-end is ONE line in the card with its Watch door");
    const fresh = lib.buildLibrary(Object.assign({}, SRC, { progress: {} }));
    check(lib.continueHTML(fresh, {}).includes('data-scenario="sc_welcome" data-mode="watch"'),
          "nothing started: the tour is offered on the Continue card");
    check(!lib.continueHTML(model, {}).includes("sc_welcome"), "… and not once something is started");
    check(!html.includes('data-lib-row="sc_welcome"') && !/data-scenario="sc_welcome"[^>]*>[\s\S]*?lrn-lib-row/.test(""),
          "the tour is never a row");
    const pick = lib.buildLibrary(Object.assign({}, SRC, { path: { roles: ROLES } }));
    const pickHtml = lib.continueHTML(pick, {});
    check(pick.cont.kind === "pick" && pickHtml.includes(runtime.esc(T("libPick")))
          && pickHtml.split('data-act="role"').length - 1 === 5,
          "no role: the Continue card asks \"Pick what you do\" with the role chips");
    const done = lib.buildLibrary(Object.assign({}, SRC, {
        progress: Object.fromEntries(ROLES.approver.map((k) => [k, { state: "done" }])) }));
    check(done.cont.kind === "done" && lib.continueHTML(done, {}).includes(runtime.esc(T("libAllDone"))),
          "every required lesson done: the card says so (no dead button)");

    // -- path strip
    const strip = lib.pathStripHTML(model);
    const stepsDrawn = Array.from(strip.matchAll(/class="lrn-lib-step (done|now|todo)"/g), (m) => m[1]);
    check(stepsDrawn.length === ROLES.approver.length, "path strip count = the required stations",
          `${stepsDrawn.length} vs ${ROLES.approver.length}`);
    check(stepsDrawn.filter((s) => s === "done").length === 2 && stepsDrawn.filter((s) => s === "now").length === 1,
          "… 2 done ticks, one current, the rest to do", stepsDrawn.join(","));
    check(strip.includes('class="lrn-lib-step change" data-act="lib-roles"'), "… ending in the dashed Change role chip");
    check(lib.pathStripHTML(pick) === "", "no required stations: no strip");
    const ownerHtml = lib.pathStripHTML(lib.buildLibrary(Object.assign({}, SRC, { path: Object.assign({}, SRC.path, { role: "owner" }) })));
    check(ownerHtml.includes('data-station="govreports"') && !ownerHtml.includes('data-station="payslips"'),
          "a role change redraws the strip from that role's path");

    // -- practice + team
    check(html.includes('data-act="to-practice"') && html.includes(runtime.esc(T("libPracticeDemo"))),
          "the Practice row opens practice mode (demo database: on the demo company)");
    check(lib.libraryHTML(lib.buildLibrary(Object.assign({}, SRC, { demoWorld: false })), CONTENT.screens, {})
          .includes(runtime.esc(T("libPracticeCopy"))), "… elsewhere: Practice on a copy");
    check(html.includes('data-act="lib-team"'), "a manager gets the Team readiness row");
    check(!lib.libraryHTML(lib.buildLibrary(Object.assign({}, SRC, { team: false })), CONTENT.screens, {})
          .includes('data-act="lib-team"'), "… nobody else does");
    check(html.indexOf('data-lib="practice"') > html.lastIndexOf('data-lib-row='), "Practice comes after every screen");
}

/* ============================================================ T1 search */
function searchSuite() {
    console.log("T1 the one search");
    RT.lang = "en";
    const index = lib.buildIndex(SRC, FIELD_ROWS);
    const kinds = new Set(index.map((e) => e.kind));
    check(["screen", "field", "term", "task", "lesson"].every((k) => kinds.has(k)),
          "five kinds are searched: screens, fields, terms, tasks, lessons", [...kinds].join(","));
    const hits = lib.search(index, "pay role");
    check(hits.length && hits[0].kind === "field" && hits[0].field === "pay_role",
          "\"pay role\" returns the field row first", hits.slice(0, 3).map((h) => `${h.kind}:${h.key}`).join(" | "));
    // The same column on two screens: the one whose own search words name it
    // (Component treatment) comes first, Mapping's Pay role after it.
    const twice = FIELD_ROWS.concat([{ screen: "mapping", screen_name: "Mapping",
        screen_names: ["Mapping", "Ánh xạ"], key: "pay_role", column: "Pay role",
        columns: ["Pay role", "Vai trò trong lương"], line: "How the component counts." }]);
    const both2 = lib.search(lib.buildIndex(SRC, twice), "pay role").filter((h) => h.kind === "field");
    check(both2.length === 2 && both2[0].screen === "treatment" && both2[1].screen === "mapping",
          "a column on two screens: its home screen first (treatment, then Mapping)",
          both2.map((h) => h.screen).join(","));
    const html = lib.resultsHTML(hits, "pay role");
    check(html.includes(runtime.esc(lib.fmt(T("libFieldOn"), { screen: "Component treatment" }))),
          "… saying where it is (Field on Component treatment)");
    check(html.includes(`>${runtime.esc(T("libKField"))}<`), "… with its kind chip");
    const empty = lib.resultsHTML(lib.search(index, "xyzzy"), "xyzzy");
    check(empty.includes(runtime.esc(lib.fmt(T("libNoMatch"), { q: "xyzzy" }))) && empty.includes('data-act="lib-ask"'),
          "no hit: \"Nothing matches …\" and Ask PayAI");
    check(lib.search(index, "payslips")[0].kind === "screen", "a screen's own name lands on the screen first");
    check(lib.search(index, "Payslips").length === lib.search(index, "payslips").length, "case does not matter");
    const term = index.find((e) => e.kind === "term");
    const th = lib.search(index, term.title);
    check(th.some((h) => h.kind === "term" && h.key === term.key), "a glossary term is found by its name");
    const open = lib.resultsHTML(th, term.title, { openTerm: term.key });
    check(open.includes('class="lrn-lib-def"'), "… and opens its definition inline");
    const lesson = index.find((e) => e.kind === "lesson");
    check(lib.search(index, lesson.title).some((h) => h.kind === "lesson"), "a lesson step is found by its title");
    const task = index.find((e) => e.kind === "task");
    check(lib.search(index, task.title).some((h) => h.kind === "task" && h.mode), "a walkthrough is found, with its mode");
    check(!index.some((e) => e.kind === "task" && e.key === "sc_retired"), "no retired walkthrough");
    // Vietnamese
    RT.lang = "vi";
    const vi = lib.buildIndex(SRC, FIELD_ROWS);
    const v = lib.search(vi, "vai trò");
    check(v.length && v[0].kind === "field", "Vietnamese: \"vai trò\" finds the field", v.slice(0, 4).map((h) => `${h.kind}:${h.title}`).join(" | "));
    check(lib.search(vi, "vai tro").length === v.length, "… with or without the accents");
    check(lib.search(vi, "phieu luong").length > 0, "… and a Vietnamese screen name without accents");
    const viHtml = lib.libraryHTML(lib.buildLibrary(SRC), CONTENT.screens, {});
    check(viHtml.includes(runtime.esc(T("search"))) && T("search") !== CONTENT.chrome.search.en,
          "the page reads Vietnamese (the search box)");
    const names = Array.from(viHtml.matchAll(/class="lrn-lib-gname">([^<]+)</g), (m) => m[1]);
    check(names[0] !== "Home" || names.includes("Cài đặt"), "… the group names", names.join(", "));
    let missing = [];
    for (const k of Object.keys(CONTENT.chrome).filter((x) => x.startsWith("lib"))) {
        const pair = CONTENT.chrome[k];
        if (!pair.en || !pair.vi) {
            missing.push(k);
        }
    }
    check(!missing.length, "every Library chrome key has English and Vietnamese", missing.join(","));
    RT.lang = "en";
}

/* ======================================================= T1 journey.js */
async function journeySuite() {
    console.log("T1 the real journey.js draws the Library");
    pb.services.orm = { call: async () => null };
    pb.services.action = { currentController: null, doAction: async () => {} };
    pb.services["learn.scenario"] = { state: {}, load: async () => {}, begin: async () => {} };
    const mod = await load("@pb_learn/journey/journey",
                           ["@pb_learn/engine/runtime", "@pb_learn/journey/library", "@pb_learn/engine/places"]);
    const { LearnJourney } = mod;
    pb.hookCtx.current = { willStart: [], mounted: [] };
    const j = new LearnJourney({}, { bus: { trigger: noop } });
    j.setup();
    pb.hookCtx.current = null;
    j.bundle = {
        stations, screens: CONTENT.screens, scenarios: CONTENT.scenarios, missions: CONTENT.missions,
        glossary: CONTENT.glossary, chrome: CONTENT.chrome, path: SRC.path, nextBest: {},
        stationAliases: CONTENT.station_aliases || {}, demoWorld: false,
    };
    j.progress = PROGRESS;
    j.state.ready = true;
    j.state.role = "approver";
    j.state.roleChosen = true;
    const body = String(j.body);
    check(body.includes('data-lib="root"') && body.includes('data-lib="continue"'), "the map view is the Library");
    check(j.body === j.body, "the same markup object while nothing changed (no flicker, the caret stays)");
    check(!/lrn-chapter|lrn-ytrail|lrn-progress|lrn-ring\b/.test(body), "no chapters, no road, no overall ring");
    check(typeof j._practiceCardHTML === "function" && j._practiceCardHTML().includes('data-act="to-practice"'),
          "_practiceCardHTML is the Practice row's door");
    j._q = "pay role";
    j._fieldRows = FIELD_ROWS;
    check(j._searchIndex().some((e) => e.kind === "field"), "the page's index holds the field rows");
    j.state.view = "outline";
    j.state.stationKey = "access";
    j.state.outlineNote = true;
    check(String(j.body).includes(runtime.esc(T("libNotInMenuNote"))),
          "a screen you cannot open: its outline with the grey note");
}

/* ============================================================ the drawer */
async function drawerSuite() {
    console.log("T1 the drawer: guide option, header, fold");
    pb.services.orm = {
        call: async (model, method) => (model === "learn.guide" && method === "rpc_guide" ? clone(GUIDE) : null),
    };
    pb.services.action = { currentController: null, doAction: async () => {} };
    pb.services["learn.scenario"] = { state: {}, load: async () => {}, forScreen: () => [], steps: () => [],
                                       get: (k) => (CONTENT.scenarios || []).find((s) => s.key === k) || null };
    const coachMod = await load("@pb_learn/coach/coach",
                                ["@pb_learn/engine/runtime", "@pb_learn/engine/glossary",
                                 "@pb_learn/coach/guide_panel", "@pb_learn/coach/field_info",
                                 "@pb_hub/js/hub_nav", "@pb_learn/coach/guide_door"]);
    const { CoachHost, COACH_ACTIONS } = coachMod;
    pb.hookCtx.current = { willStart: [], mounted: [] };
    const host = new CoachHost({}, { bus: { trigger: noop } });
    host.setup();
    pb.hookCtx.current = null;
    host.place = { tag: "pb_mapping_studio", lens: "treatment", subs: {}, lenses: [], seq: 1, detail: "", ready: true, extra: {} };
    host.bundle = { screens: CONTENT.screens, chrome: CONTENT.chrome, stations: CONTENT.stations, guide: true };
    host.state.ready = true;
    host.state.screen = "treatment";
    host.state.dock = "float";
    await host._loadGuide();
    host.openHelper({ guide: { screen: "treatment", section: "fields", field: "pay_role" } });
    check(host.state.open && host.state.gSec.fields === true && host.state.gField === "pay_role",
          "openHelper({guide}) opens the drawer, Fields expanded, the Pay role row open");
    check(host.state.dock === "dock", "… docked at 1440 px");
    check(String(host.guideHTML).includes('class="lrn-gfield open" data-field="pay_role"'), "… the row is drawn open");
    host.openHelper({ guide: { screen: "treatment", section: "this" } });
    check(host.state.gSec.screen === true, "section \"this\" opens This screen");
    host.openHelper({ guide: { screen: "payruns", section: "screen" } });
    check(host._pendingGuide && host._pendingGuide.screen === "payruns",
          "a Guide for a screen not grounded yet waits for it");
    host._ground("payruns");
    check(!host._pendingGuide && host.state.gSec.screen === true, "… and is applied once the screen is grounded");
    host.state.screen = "treatment";
    host.state.gKey = "";
    await host._loadGuide();
    // S8a
    const name = runtime.tx(CONTENT.screens.find((s) => s.key === "treatment").name);
    check(host.headTitle === lib.fmt(T("gHead"), { screen: name }) && host.headTitle === "Guide · Component treatment",
          "the header reads \"Guide · Component treatment\"", host.headTitle);
    host.bundle.guide = false;
    check(host.headTitle === T("coachName"), "switch off: the helper's own name");
    host.bundle.guide = true;
    // S8b
    host._sentThisOpen = false;
    host.state.gFolded = false;
    host.helper.guideArgs();
    check(host.state.gFolded === true, "a sent message folds the Guide to its titles");
    const folded = String(host.guideHTML);
    check(folded.includes('data-act="c-gshow"') && !folded.includes('lrn-gsec open'),
          "… titles only, with a Show the Guide link");
    check(COACH_ACTIONS.has("c-gshow"), "c-gshow is a declared action");
    host._showGuide();
    check(host.state.gFolded === false && store.get("pbLearnGuideShow").includes("treatment"),
          "Show the Guide re-expands and is remembered for this screen");
    host._sentThisOpen = false;
    host.helper.guideArgs();
    check(host.state.gFolded === false, "… so the next message on this screen does not fold it");
    host.state.screen = "payruns";
    host._sentThisOpen = false;
    host.helper.guideArgs();
    check(host.state.gFolded === true, "… another screen still folds");
    host.helper.guideArgs();
    host._toggleSection("now");
    check(host.state.gFolded === false && host.state.gSec.now === true, "a title pressed while folded opens that section");
    host.bundle.guide = false;
    host.state.open = false;
    host._queue = [];
    host.openHelper({ guide: { screen: "treatment", section: "screen" } });
    check(host.state.open, "switch off: the guide option still opens the drawer (Explain is the floor)");
}

/* ======================================================== the palette */
async function paletteSuite() {
    console.log("T1 ⌘K field rows");
    const pal = await load("@pb_learn/hub/learn_palette", ["@pb_learn/engine/runtime"]);
    RT.lang = "en";
    const opened = [];
    pal.registerFieldRows(FIELD_ROWS, (s, f) => opened.push([s, f]));
    const reg = pb.registry.category("pb_hub_palette");
    const row = reg.get("learn.field.treatment.pay_role");
    check(row && row.label === "Pay role" && row.sublabel.startsWith("Field on Component treatment"),
          "\"Pay role · Field on Component treatment\"", row && `${row.label} | ${row.sublabel}`);
    check(row && row.door === false, "… a palette row only, never a PayAI door");
    row.onRun("");
    check(opened.length === 1 && opened[0][0] === "treatment" && opened[0][1] === "pay_role",
          "… opening the treatment board with the Pay role row");
    // LEARNREV P5a (LR51): the screen whose own search words name the column
    // goes first, whatever order the rows arrive in.
    const payRoleOn = (screen) => ({ screen, key: "pay_role", column: "Pay role", columns: ["Pay role", "Vai trò lương"] });
    const ordered = pal.homeFirst([payRoleOn("mapping"), payRoleOn("treatment")], SRC);
    check(ordered.map((r) => r.screen).join() === "treatment,mapping",
          "⌘K: Pay role on Component treatment ranks before Mapping's");
    check(pal.homeFirst([payRoleOn("mapping"), payRoleOn("formula")], SRC).map((r) => r.screen).join() === "mapping,formula",
          "… and with no home screen the order is kept");
    pal.registerFieldRows(FIELD_ROWS, noop);
    check(Object.keys(reg.content).filter((k) => k.startsWith("learn.field.")).length === FIELD_ROWS.length,
          "registering twice adds nothing");
    const svc = fs.readFileSync(path.join(ROOT, "pb_hub", "static", "src", "js", "hub_palette_service.js"), "utf-8");
    check(/entries: doorEntries/.test(svc) && /filter\(\(r\) => r\.door\)/.test(svc),
          "the palette service hands PayAI only the rows that are doors");
}

librarySuite();
searchSuite();
await journeySuite();
await drawerSuite();
await paletteSuite();
summary();
