/**
 * LEARNREV P4 — the lesson played in the Guide panel, run in node (T2).
 *
 *   the card       the four lines (Look at · It means · It affects · Press),
 *                  a field step's readers as chips, kicker / title / tip,
 *                  a legacy `body` shown as the "It means" line;
 *   placeFor       reachable + product anchor → the panel; rep-* → the
 *                  practice copy; unreachable → the practice copy + note;
 *   country        VN, ID, unknown → generic; the scheme's country wins;
 *   placement      the spotlight's card never overlaps its control, in six
 *                  geometries including a headline at the top of the page;
 *   the drawer     "Start the lesson" in Understand plays the real lesson in
 *                  the panel: the card replaces the section, Next / Back /
 *                  Leave, the quiz, progress written to learn.progress;
 *   the content    the rewritten lessons of the eight screens (real content).
 *
 * Run: node pb_learn/tests/js/lesson_panel.test.mjs   (exit 1 on failure)
 */
import fs from "node:fs";
import path from "node:path";
import { check, load, summary, ROOT } from "./harness.mjs";

const pb = globalThis.__pb;
const noop = () => {};
const store = new Map();
globalThis.document = {
    addEventListener: noop, removeEventListener: noop,
    body: { classList: { add: noop, remove: noop, contains: () => false, toggle: noop }, appendChild: noop },
    documentElement: { style: { setProperty: noop } },
    querySelector: () => null, querySelectorAll: () => [], activeElement: null,
    createElement: () => ({ style: {}, setAttribute: noop, appendChild: noop, remove: noop,
                            classList: { add: noop, remove: noop, toggle: noop } }),
};
globalThis.window = {
    localStorage: { getItem: () => null, setItem: noop },
    sessionStorage: { getItem: (k) => (store.has(k) ? store.get(k) : null),
                      setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) },
    matchMedia: () => ({ matches: false }),
    innerHeight: 900, innerWidth: 1440,
    addEventListener: noop,
};
globalThis.requestAnimationFrame = () => 1;
globalThis.cancelAnimationFrame = noop;

const CONTENT = JSON.parse(fs.readFileSync(
    path.join(ROOT, "pb_learn", "static", "content", "learn_content.json"), "utf-8"));
const GUIDE = JSON.parse(fs.readFileSync(
    path.join(ROOT, "pb_learn", "tests", "data", "guide_treatment_en.json"), "utf-8"));
const clone = (x) => JSON.parse(JSON.stringify(x));

const runtime = await load("@pb_learn/engine/runtime");
const lp = await load("@pb_learn/coach/lesson_panel", ["@pb_learn/engine/runtime"]);
const spot = await load("@pb_learn/engine/spotlight", ["@pb_learn/engine/runtime"]);
const { RT } = runtime;
RT.chrome = CONTENT.chrome;
RT.lang = "en";
const T = (k) => runtime.T(k);
const text = (p) => runtime.tx(p);
const P = (en, vi) => ({ en, vi: vi || `VI ${en}` });

// ================================================================ the card
function cardSuite() {
    console.log("T2 the four-line card");
    const step = {
        kicker: P("Pay role"), title: P("The pay role decides the arithmetic"),
        look: P("the amber cell on Loan Installment"),
        means: P("the formulas could not tell whether it reaches net pay"),
        affects: P("run totals, the payslip and the bank file"),
        press: P("the cell, and choose Taken off net pay"),
        uses: [P("Every payslip line"), P("Pay run totals"), P("The bank file")],
        tip: P("Saving never rewrites a payslip."),
        anchor: "tr-col-role", screen: "treatment",
    };
    const html = lp.lessonCardHTML(lp.stepView(step, "VN"), { index: 1, total: 6, text, note: null });
    for (const k of ["lpLook", "lpMeans", "lpAffects", "lpPress"]) {
        check(html.includes(runtime.esc(T(k))), `label "${T(k)}"`);
    }
    check(html.indexOf(T("lpLook")) < html.indexOf(T("lpMeans"))
          && html.indexOf(T("lpMeans")) < html.indexOf(T("lpAffects"))
          && html.indexOf(T("lpAffects")) < html.indexOf(T("lpPress")),
          "… in the order Look at, It means, It affects, Press");
    check(html.includes("the amber cell on Loan Installment") && html.includes("Taken off net pay"),
          "the lines say the step's words");
    check((html.match(/lrn-fc-chip use/g) || []).length === 3, "a field step's three readers as chips");
    check(html.includes(">PAY ROLE<") || html.includes(">Pay role<"), "the kicker");
    check(html.includes("The pay role decides the arithmetic"), "the title");
    check(html.includes("Saving never rewrites a payslip."), "the tip");
    check(html.includes(`${T("step")} 2 ${T("of")} 6`) && html.includes("width:33%"), "Step 2 of 6, and the meter");
    check(html.includes('data-act="c-lpback"') && html.includes('data-act="c-lpnext"')
          && html.includes('data-act="c-lpleave"'), "Back, Next and Leave at the bottom");
    const first = lp.lessonCardHTML(lp.stepView(step, "VN"), { index: 0, total: 6, text });
    check(/data-act="c-lpback" disabled/.test(first), "Back is off on the first step");
    const last = lp.lessonCardHTML(lp.stepView(step, "VN"), { index: 5, total: 6, text });
    check(last.includes(runtime.esc(T("check"))), "the last step's Next says it goes to the check");
    // a step that has no Press line draws none
    const noPress = lp.lessonCardHTML(lp.stepView(Object.assign({}, step, { press: "" }), "VN"),
                                      { index: 0, total: 6, text });
    check(!noPress.includes(runtime.esc(T("lpPress"))), "no Press line on a step without a real control");
    // legacy
    const legacy = { title: P("Old step"), body: P("Gross <b>less</b> deductions."), anchor: "tr-head" };
    const lv = lp.stepView(legacy, "VN");
    const lhtml = lp.lessonCardHTML(lv, { index: 0, total: 1, text, html: (p) => text(p) });
    check(lv.legacy && lv.means === legacy.body, "a legacy body becomes the It means line");
    check(lhtml.includes("Gross <b>less</b> deductions.") && lhtml.includes(runtime.esc(T("lpMeans")))
          && !lhtml.includes(runtime.esc(T("lpLook"))),
          "… drawn as It means (its inline markup kept), with no Look at line");
    // notes
    for (const kind of ["practice", "unreachable", "loading", "nothere"]) {
        const n = lp.lessonCardHTML(lv, { index: 0, total: 1, text, html: (p) => text(p), note: { kind } });
        check(n.includes(`lrn-lp-note ${kind}`), `note: ${kind}`);
        if (kind === "loading") {
            check(n.includes('data-act="c-lpretry"') && n.includes(runtime.esc(T("lpLoading"))),
                  "… a slow screen says still loading, with Retry");
            check(!n.includes(runtime.esc(T("scNoAccessT"))), "… and never says no access");
        }
    }
    // Vietnamese
    RT.lang = "vi";
    const vi = lp.lessonCardHTML(lp.stepView(step, "VN"), { index: 1, total: 6, text });
    check(vi.includes("Nhìn vào") && vi.includes("Nghĩa là") && vi.includes("Ảnh hưởng tới") && vi.includes("Bấm"),
          "Vietnamese labels: Nhìn vào · Nghĩa là · Ảnh hưởng tới · Bấm");
    check(vi.includes("VI the amber cell on Loan Installment"), "… and the step's Vietnamese");
    RT.lang = "en";
    // the quiz
    const quiz = { prompt: P("Which?"), options: [
        { label: P("A"), correct: false, feedback: P("Let's rethink that.") },
        { label: P("B"), correct: true, feedback: P("Yes.") }] };
    const q0 = lp.quizHTML(quiz, { answered: null, text });
    check((q0.match(/data-act="c-lpans"/g) || []).length === 2 && q0.includes("Which?"), "the quiz: prompt and options");
    const q1 = lp.quizHTML(quiz, { answered: 1, text });
    check(q1.includes('data-act="c-lpfinish"') && q1.includes("Yes."), "a right answer offers Finish");
    const q2 = lp.quizHTML(quiz, { answered: 0, text });
    check(q2.includes('data-act="c-lpretryq"') && q2.includes("Let's rethink that."), "a wrong one: Try again, and why");
}

// ============================================================== placeFor
function placeSuite() {
    console.log("T2 placeFor");
    const step = (anchor, screen) => ({ anchor, screen: screen || "treatment" });
    let r = lp.placeFor(step("tr-col-role"), { reachable: true, current: "treatment" });
    check(r.where === "panel" && !r.navigate, "reachable + product anchor → the panel");
    r = lp.placeFor(step("tr-col-role"), { reachable: null, current: "treatment" });
    check(r.where === "panel", "unknown reach is not a no → the panel");
    r = lp.placeFor(step("pk-card", "payruns"), { reachable: true, current: "treatment" });
    check(r.where === "panel" && r.navigate, "a step on another screen → the panel, after opening it");
    r = lp.placeFor(step("rep-ct-warn"), { reachable: true, current: "treatment" });
    check(r.where === "replica" && r.reason === "practice", "rep-* → the practice copy");
    r = lp.placeFor(step("tr-col-role"), { reachable: false, current: "treatment" });
    check(r.where === "replica" && r.reason === "unreachable", "unreachable → the practice copy, with the note");
    check(lp.isPracticeAnchor("rep-x") && !lp.isPracticeAnchor("tr-head"), "isPracticeAnchor");
}

// =============================================================== country
function countrySuite() {
    console.log("T2 country");
    check(lp.pickCountry("VN", "") === "VN", "company VN → VN");
    check(lp.pickCountry("vn", "id") === "ID", "the scheme's country wins over the company's");
    check(lp.pickCountry("", "") === "", "no country at all → none");
    const step = {
        title: P("Who pays what"), look: P("the rates row"),
        means: P("shared line"), affects: P("shared affects"),
        variants: {
            VN: { means: P("BHXH 8% / 17.5%") },
            ID: { means: P("BPJS JHT 2% / 3.7%"), press: P("the row") },
            generic: { means: P("your country's insurance and tax") },
        },
    };
    check(text(lp.stepView(step, "VN").means) === "BHXH 8% / 17.5%", "VN reads the VN variant");
    check(text(lp.stepView(step, "ID").means) === "BPJS JHT 2% / 3.7%", "ID reads the ID variant");
    check(text(lp.stepView(step, "ID").press) === "the row", "… including its Press line");
    check(text(lp.stepView(step, "BR").means) === "your country's insurance and tax", "an unknown country → generic");
    check(text(lp.stepView(step, "").means) === "your country's insurance and tax", "no country → generic");
    check(text(lp.stepView(step, "SG").affects) === "shared affects", "a line no variant sets stays the shared one");
    check(text(lp.stepView({ means: P("plain"), look: P("x") }, "ID").means) === "plain", "no variants → the step's own lines");
}

// ============================================================= placement
function placementSuite() {
    console.log("T2 the card never covers its control");
    const g = { W: 1440, H: 900, cw: 372, ch: 300, guard: 12 };
    const rect = (top, left, w, h) => ({ top, left, width: w, height: h, right: left + w, bottom: top + h });
    const cases = [
        ["a control at the left middle → right", rect(400, 40, 200, 40), g, "right"],
        ["a control at the right edge → left", rect(400, 1200, 200, 40), g, "left"],
        ["a full-width table near the top → below", rect(120, 20, 1400, 200), g, "below"],
        ["a full-width bar at the bottom → above", rect(700, 20, 1400, 100), g, "above"],
        ["a headline across the top of the page, tall card → below, scrolled", rect(8, 0, 1440, 64),
         Object.assign({}, g, { ch: 860 }), "below"],
        ["a board that fills the window → the roomier side (above), scrolled", rect(200, 0, 1440, 520), g, "above"],
        ["docked Guide: the right-hand 420 px are not the card's", rect(400, 700, 300, 40),
         Object.assign({}, g, { dock: 420 }), "left"],
    ];
    for (const [label, r, geom, side] of cases) {
        const p = spot.placeCard(r, geom);
        const h = p.maxHeight ? Math.min(geom.ch, p.maxHeight) : geom.ch;
        const card = { top: p.top, left: p.left, right: p.left + p.width, bottom: p.top + h };
        check(!spot.overlaps(card, r), `${label}: no overlap`, JSON.stringify(p));
        check(p.side === side, `… placed ${side}`, p.side);
        check(card.left >= 0 && card.right <= geom.W - (geom.dock || 0) + 0.5, "… inside the free width");
    }
    // the case the old fallback got wrong: "above" clamped onto a top headline
    const top = rect(10, 0, 1440, 120);
    const p = spot.placeCard(top, Object.assign({}, g, { ch: 800 }));
    check(p.top >= top.bottom, "a top-of-page headline is never covered (old fallback clamped onto it)");
}

// ============================================================== the drawer
async function drawerSuite() {
    console.log("T2 the drawer plays a lesson in the panel");
    const calls = [];
    pb.services.orm = {
        call: async (model, method, args = [], kwargs = {}) => {
            calls.push({ model, method, args, kwargs });
            if (model === "learn.guide" && method === "rpc_guide") { return clone(GUIDE); }
            return null;
        },
    };
    pb.services.action = { currentController: null, doAction: async () => {} };
    pb.services["learn.scenario"] = {
        state: {}, load: async () => {}, forScreen: () => [], steps: () => [],
        get: (k) => (CONTENT.scenarios || []).find((s) => s.key === k) || null,
    };
    const coachMod = await load("@pb_learn/coach/coach",
                                ["@pb_learn/engine/runtime", "@pb_learn/engine/glossary",
                                 "@pb_learn/coach/guide_panel", "@pb_learn/coach/field_info",
                                 "@pb_learn/coach/lesson_panel", "@pb_learn/content/content_loader",
                                 "@pb_learn/engine/spotlight", "@pb_hub/js/hub_nav"]);
    const { CoachHost, COACH_ACTIONS } = coachMod;
    for (const a of ["c-lpstart", "c-lpnext", "c-lpback", "c-lpleave", "c-lpretry", "c-lppractice",
                     "c-lpans", "c-lpretryq", "c-lpfinish"]) {
        check(COACH_ACTIONS.has(a), `declared action ${a}`);
    }
    const hooks = { willStart: [], mounted: [] };
    pb.hookCtx.current = hooks;
    const host = new CoachHost({}, { bus: { trigger: () => {} } });
    host.setup();
    pb.hookCtx.current = null;
    // A lesson whose steps all stand on the screen on show, with real anchors.
    const stations = clone(CONTENT.stations);
    const st = stations.find((s) => s.key === "treatment");
    const lesson = st.lessons[0];
    const playable = lesson.steps.filter((s) => !lp.isPracticeAnchor(s.anchor));
    lesson.steps = playable;
    host.place = { tag: "pb_mapping_studio", lens: "treatment", subs: {}, lenses: [], seq: 1, detail: "", ready: true, extra: {} };
    host.bundle = { screens: CONTENT.screens, global_suggest: [], chrome: CONTENT.chrome, stations,
                    guide: true, collect_questions: false, progress: {}, features: {}, country: "VN" };
    host.state.ready = true;
    host.state.open = true;
    host.state.screen = "treatment";
    host.state.gSec = { screen: true, now: true, fields: false, tasks: true, understand: true };
    await host._loadGuide();
    const before = String(host.guideHTML);
    check(before.includes('data-act="c-lpstart"') && before.includes(runtime.esc(T("lpStart"))),
          "Understand offers Start the lesson");
    const btn = { dataset: { act: "c-lpstart" }, closest: () => null };
    host.onClick({ target: { closest: (sel) => (sel === "[data-act]" ? btn : null) }, preventDefault: noop });
    await new Promise((r) => setTimeout(r, 0));
    check(host.state.lp && host.state.lp.station === "treatment" && host.state.lp.index === 0,
          "the lesson starts at step 1 in the panel");
    check(JSON.stringify(host.state.gSec) === JSON.stringify(host._lpSections()), "only Understand stays open");
    const html = String(host.guideHTML);
    check(html.includes('data-lp="1"') && html.includes(runtime.esc(text(playable[0].title))),
          "the step card replaces the Understand body");
    const rec = calls.find((c) => c.model === "learn.progress" && c.method === "record");
    check(rec && rec.args[0] === "treatment" && rec.args[1].state === "in_progress",
          "progress: in_progress on learn.progress", JSON.stringify(rec));
    host._lpNext();
    check(host.state.lp.index === 1, "Next moves to step 2");
    check(calls.some((c) => c.method === "record" && c.args[1].step_index === 1), "… and records the step");
    host._lpBack();
    check(host.state.lp.index === 0, "Back returns to step 1");
    while (!host.state.lp.quiz) { host._lpNext(); }
    const qhtml = String(host.guideHTML);
    check(qhtml.includes('data-act="c-lpans"'), "past the last step: the quiz plays in the panel");
    const right = (lesson.quizzes[0].options || []).findIndex((o) => o.correct);
    host._lpAnswer(right);
    host._lpFinish();
    check(host.state.lp.done && String(host.guideHTML).includes(runtime.esc(T("lpDone"))), "a right answer, Finish: Lesson done");
    check(calls.some((c) => c.method === "record" && c.args[1].state === "done" && c.args[1].completed_at),
          "… progress done, with completed_at");
    host._lpLeave();
    check(host.state.lp === null && host.state.gSec.screen === true, "Leave restores the sections as they were");
    // a practice-copy step hands over to the Journey, at that step
    const opened = [];
    const st2 = clone(CONTENT.stations).find((s) => s.key === "treatment");
    host.bundle.stations = [Object.assign(st2, { lessons: [Object.assign(st2.lessons[0], {
        steps: [{ title: P("x"), look: P("l"), means: P("m"), affects: P("a"), anchor: "rep-ct-warn", screen: "treatment" }],
    })] })];
    host.action.doAction = async (a) => { opened.push(a); };
    host.startPanelLesson("treatment");
    await new Promise((r) => setTimeout(r, 0));
    const handed = JSON.parse(store.get("pbLearnLessonReturn") || "null");
    check(host.state.lp === null && handed && handed.station === "treatment" && handed.from === "treatment",
          "a rep-* step → handed to the practice copy, with where to come back", JSON.stringify(handed));
}

cardSuite();
placeSuite();
countrySuite();
placementSuite();
await drawerSuite();
summary();
