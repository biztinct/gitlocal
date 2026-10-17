/** @odoo-module **/
/* =============================================================================
   LEARNREV P3 — the Library: the Learning page, calm.

   One card that says what to do next and why, a strip of the lessons your
   path requires, then every screen in the product in the SAME ORDER AS THE
   LEFT MENU — one row each, with a quiet progress ring and at most three
   small doors (Guide, Watch, Try). One search over screens, fields, terms,
   tasks and lessons. No badge, no streak, no overall ring (owner decision
   2026-10-17), no "Not on your path", no minutes on a row.

   PURE. Nothing here reads the DOM, the server or a component: the Journey
   (journey.js) hands in what it loaded and gets HTML back, and the node suite
   (tests/js/library.test.mjs) renders the same functions from a fixture.
   Every string is a chrome key of the content plane (EN + VI), every icon a
   Lucide symbol through `ic()`.

   MINIFIER RULE (engine/runtime.js): never a literal space right after a
   closing brace of an interpolation — `${SP}` instead; never a quoted string
   inside an interpolation.
   ========================================================================== */
import { RT, T, tx, esc, ic, SP } from "../engine/runtime";
import { hubScreenOf, parsePlace } from "../engine/places";

/* THE LEFT MENU, IN ITS ORDER. Mirrors the `pb.sidebar.item` records the rail
   draws (section sequence, then item sequence): Home · Pay Run · People ·
   Lifecycle · Workforce · Insights · Compliance · Settings. `item` is the
   record's xml-id and `tags` the hub actions whose tabs belong to it —
   Mapping (`pb_mapping_studio`) is opened from Settings › Integrations, so
   its screens are Settings screens. Learn itself is not a group: it is this
   page. `tests/test_learnrev_p3.py` compares this list with the database's
   rail, so a reordered menu fails a test, never the page. */
export const MENU_ORDER = [
    { key: "home", item: "pb_home_hub.item_home", tags: ["pb_home_hub"], icon: "home" },
    { key: "payrun", item: "pb_payhub.item_pay_run", tags: ["pb_pay_hub"], icon: "zap" },
    { key: "people", item: "pb_people_hub.item_people", tags: ["pb_people_hub"], icon: "users" },
    { key: "lifecycle", item: "pb_lifecycle.item_lifecycle", tags: ["pb_lifecycle_hub"], icon: "git-branch" },
    { key: "workforce", item: "pb_mission.item_workforce", tags: ["pb_workforce"], icon: "compass" },
    { key: "insights", item: "pb_insights_hub.item_insights", tags: ["pb_insights_hub"], icon: "trending-up" },
    { key: "compliance", item: "pb_compliance_hub.item_compliance", tags: ["pb_compliance_hub"], icon: "shield-check" },
    { key: "settings", item: "pb_settings.item_settings", tags: ["pb_settings_hub", "pb_mapping_studio"], icon: "sliders" },
];

/* A station whose screen has no hub tab (the Setup screens that open as
   their own action, a station with no screen yet) is grouped by its Journey
   line. Their `sidebar_key`s name rail items of the retired Setup section
   (inactive since the IA cutover), so the line is the honest fallback. */
export const LINE_GROUP = {
    overview: "home", payrun: "payrun", people: "people", lifecycle: "lifecycle",
    workforce: "workforce", insights: "insights", compliance: "compliance", setup: "settings",
};

/* The product tour. Offered once, on the Continue card, to somebody who has
   not started anything — never as a row. */
export const TOUR = "sc_welcome";

export const ROLE_ORDER = ["officer", "approver", "hr", "manager", "owner"];
export const ROLE_LABEL = { officer: "roleOfficer", approver: "roleApprover", hr: "roleHr",
                            manager: "roleManager", owner: "roleOwner" };
export const ROLE_ICON = { officer: "calculator", approver: "clipboard-check", hr: "users",
                           manager: "user-check", owner: "trending-up" };

/* The five kinds the search finds, in the order a tie is broken. */
export const KINDS = ["screen", "field", "term", "task", "lesson"];
const KIND_LABEL = { screen: "libKScreen", field: "libKField", term: "libKTerm",
                     task: "libKTask", lesson: "libKLesson" };
const KIND_ICON = { screen: "map-pin", field: "info", term: "book-open", task: "play", lesson: "grad-cap" };
export const MAX_HITS = 30;

/** Fill `{name}` slots of a chrome string. */
export function fmt(text, vars = {}) {
    return String(text || "").replace(/\{(\w+)\}/g, (m, k) =>
        (Object.prototype.hasOwnProperty.call(vars, k) ? String(vars[k]) : m));
}

/* ------------------------------------------------------------- grouping */
const TAG_GROUP = {};
for (const g of MENU_ORDER) {
    for (const t of g.tags) {
        TAG_GROUP[t] = g.key;
    }
}

/** The menu group a station is listed under: the hub that holds most of
 *  its screen's places (ties: the first place), else its line's group. */
export function groupOf(station, screens) {
    const sc = (screens || []).find((s) => s.key === station.key) || null;
    const count = {};
    let first = "";
    for (const p of (sc && sc.places) || []) {
        const pl = parsePlace(p);
        const g = pl && !pl.detail ? TAG_GROUP[pl.tag] : "";
        if (g) {
            count[g] = (count[g] || 0) + 1;
            first = first || g;
        }
    }
    let best = first;
    for (const g of Object.keys(count)) {
        if (count[g] > (count[best] || 0)) {
            best = g;
        }
    }
    return best || LINE_GROUP[station.line] || MENU_ORDER[MENU_ORDER.length - 1].key;
}

/** The group's name: the hub page's own name in the content (bilingual). */
export function groupName(group, screens) {
    const g = MENU_ORDER.find((x) => x.key === group);
    const hs = g && hubScreenOf(screens, g.tags[0]);
    return hs ? tx(hs.name) : T(`lines.${group}`);
}

/* ------------------------------------------------------------- per station */
/** "done" | "started" | "none" — "started" is any step done. */
export function ringOf(progress, key) {
    const p = (progress || {})[key] || {};
    if (p.state === "done") {
        return "done";
    }
    return p.state === "in_progress" || (p.step_index || 0) > 0 ? "started" : "none";
}

/** The walkthrough doors a station's row carries: Watch and Try, from the
 *  walkthroughs that START on this screen, then the ones of the same line
 *  that walk through it. The tour is the Continue card's, never a row's. */
export function stationDoors(station, scenarios) {
    const live = (scenarios || []).filter((sc) => !sc.retired && (sc.modes || []).length
                                          && sc.key !== TOUR);
    const own = live.filter((sc) => (sc.entry || {}).screen === station.key);
    const near = live.filter((sc) => (sc.entry || {}).screen !== station.key
                             && sc.line === station.line
                             && (sc.screens || []).includes(station.key));
    const list = own.concat(near);
    const watch = list.find((sc) => sc.modes.includes("watch"));
    const tryIt = list.find((sc) => sc.modes.includes("try"));
    return { watch: watch ? watch.key : "", try: tryIt ? tryIt.key : "" };
}

/** The one status a row may carry: "menu" (cannot open it), "required"
 *  (on your path), or "". Never "not on your path". */
export function statusOf(station, required) {
    if (station.gated || station.missing || station.visible === false) {
        return "menu";
    }
    return required.has(station.key) ? "required" : "";
}

/* ------------------------------------------------------------- the model */
/**
 * What the page shows, from what the Journey loaded:
 *   stations, screens, scenarios, missions, progress, glossary
 *   path      {role, role_chosen, roles: {role: [keys]}, month_end}
 *   nextBest  learn.runtime.next_best()
 *   demoWorld, team (may read Team readiness)
 */
export function buildLibrary(src) {
    const stations = src.stations || [];
    const screens = src.screens || [];
    const progress = src.progress || {};
    const path = src.path || {};
    const role = ROLE_ORDER.includes(path.role) ? path.role : "";
    const roleKeys = role && path.roles && Array.isArray(path.roles[role]) ? path.roles[role] : null;
    const required = new Set(roleKeys || []);
    const byKey = new Map(stations.map((s) => [s.key, s]));

    const groups = MENU_ORDER.map((g) => ({ key: g.key, icon: g.icon, rows: [] }));
    const at = new Map(groups.map((g) => [g.key, g]));
    for (const st of stations) {
        const g = at.get(groupOf(st, screens)) || groups[groups.length - 1];
        g.rows.push({
            station: st,
            ring: ringOf(progress, st.key),
            status: statusOf(st, required),
            doors: stationDoors(st, src.scenarios),
        });
    }
    // The page's reading order: menu groups, then the station order inside.
    const order = groups.flatMap((g) => g.rows.map((r) => r.station.key));
    const path_ = order.filter((k) => required.has(k)).map((k) => byKey.get(k));
    const done = path_.filter((s) => ringOf(progress, s.key) === "done").length;
    return {
        role,
        roleChosen: !!path.role_chosen,
        // LEARNREV P5a: the seat a guessed role was read from, when the path
        // rule carries one ({en, vi}); empty otherwise, and the role stays
        // the reason.
        seat: path.why && (path.why.en || path.why.vi) ? path.why : null,
        hasPath: !!roleKeys,
        required,
        path: path_,
        done,
        groups,
        cont: continueOf(src, path_, byKey, role),
        monthEnd: path.month_end || {},
        tour: tourOf(src, progress),
        demoWorld: !!src.demoWorld,
        team: !!src.team,
    };
}

/** What the Continue card offers: the server's next step when it names
 *  something this page has, else the first required station not yet done,
 *  else nothing left ("all done"). */
function continueOf(src, path, byKey, role) {
    const nb = src.nextBest || {};
    const missions = src.missions || [];
    if (nb.key && nb.kind === "mission") {
        const m = missions.find((x) => x.key === nb.key);
        if (m) {
            return { kind: "mission", item: m, why: tx(nb.reason || {}) };
        }
    }
    if (nb.key && nb.kind === "station" && byKey.has(nb.key)) {
        return { kind: "station", item: byKey.get(nb.key), nb: nb.reason_key || "" };
    }
    const progress = src.progress || {};
    const next = path.find((s) => ringOf(progress, s.key) !== "done");
    if (next) {
        return { kind: "station", item: next, nb: "" };
    }
    return role ? { kind: "done" } : { kind: "pick" };
}

/** The tour, for a person with nothing started at all. */
function tourOf(src, progress) {
    const started = Object.values(progress || {}).some((p) => p && (p.state === "done"
        || p.state === "in_progress"));
    if (started) {
        return null;
    }
    const sc = (src.scenarios || []).find((x) => x.key === TOUR && !x.retired
                                           && (x.modes || []).includes("watch"));
    return sc ? { key: sc.key, steps: (sc.steps || []).length } : null;
}

/* ------------------------------------------------------------- rendering */
function roleName(role) {
    return role ? T(ROLE_LABEL[role]) : "";
}

function stepsOf(station) {
    const l = station && (station.lessons || [])[0];
    return l ? (l.steps || []).length : 0;
}

function roleChips(model) {
    return ROLE_ORDER.map((r) => `<button type="button" class="lrn-lib-role" data-act="role" data-role="${r}"
        aria-pressed="${r === model.role ? "true" : "false"}">${ic(ROLE_ICON[r])}${esc(T(ROLE_LABEL[r]))}</button>`).join("");
}

/** The Continue card (S2). `ui.rolesOpen` shows the role chips in place. */
export function continueHTML(model, ui = {}) {
    const c = model.cont;
    const pathLine = model.role && model.hasPath
        ? fmt(T("libYourPath"), { role: roleName(model.role), done: model.done, total: model.path.length })
        : "";
    const change = model.role
        ? `<button type="button" class="lrn-lib-link" data-act="lib-roles"
            aria-expanded="${ui.rolesOpen ? "true" : "false"}">${esc(T("libChange"))}</button>` : "";
    const eyebrow = `<div class="lrn-lib-eyebrow"><span>${esc(T("nbTitle"))}</span>${pathLine
        ? `<span class="lrn-lib-dot" aria-hidden="true"></span><span>${esc(pathLine)}</span>` : ""}${change}</div>`;
    const roles = (ui.rolesOpen || c.kind === "pick")
        ? `<div class="lrn-lib-roles" role="group" aria-label="${esc(T("libPick"))}">${roleChips(model)}</div>` : "";
    const extra = [monthEndLine(model, ui), tourLine(model)].filter(Boolean).join("");

    if (c.kind === "pick") {
        return `<section class="lrn-lib-cont pick" data-lib="continue">
            ${eyebrow}
            <h2 class="lrn-lib-ctitle">${esc(T("libPick"))}</h2>
            <p class="lrn-lib-cwhy">${esc(T("libPickLead"))}</p>
            ${roles}${extra}
        </section>`;
    }
    if (c.kind === "done") {
        return `<section class="lrn-lib-cont done" data-lib="continue">
            ${eyebrow}
            <div class="lrn-lib-cmain"><span class="lrn-lib-cico ok">${ic("check-circle")}</span>
                <div><h2 class="lrn-lib-ctitle">${esc(T("libAllDone"))}</h2>
                <p class="lrn-lib-cwhy">${esc(T("libAllDoneLead"))}</p></div></div>
            ${roles}${extra}
        </section>`;
    }
    const item = c.item;
    let why;
    let go;
    if (c.kind === "mission") {
        why = c.why;
        go = `<button type="button" class="lrn-btn pri lrn-lib-go" data-act="nb-go" data-kind="mission"
            data-key="${esc(item.key)}">${ic("play")}${esc(T("nbTitle"))}</button>`;
    } else {
        const onPath = model.required.has(item.key);
        const parts = [];
        if (c.nb === "nbResume") {
            parts.push(T("libStarted"));
        }
        if (onPath && !model.roleChosen && model.seat) {
            // The reason names the seat ("…because you hold the payroll
            // approval seat."), not only the role it came from.
            parts.push(tx(model.seat));
        } else {
            parts.push(onPath ? fmt(T("libReqFor"), { role: roleName(model.role) }) : T("libExtra"));
            if (onPath && !model.roleChosen) {
                parts.push(T("libRoleGuessed"));
            }
        }
        const n = stepsOf(item);
        if (n) {
            parts.push(fmt(T("libSteps"), { n }));
        }
        why = parts.join(SP);
        go = `<button type="button" class="lrn-btn pri lrn-lib-go" data-act="lib-continue"
            data-key="${esc(item.key)}">${ic("play")}${esc(T("nbTitle"))}</button>`;
    }
    return `<section class="lrn-lib-cont" data-lib="continue">
        ${eyebrow}
        <div class="lrn-lib-cmain">
            <span class="lrn-lib-cico">${ic(item.icon || "map-pin")}</span>
            <div class="lrn-lib-ctext">
                <h2 class="lrn-lib-ctitle">${esc(tx(item.name))}</h2>
                <p class="lrn-lib-cwhy">${esc(why)}</p>
            </div>
            ${go}
        </div>
        ${roles}${extra}
    </section>`;
}

/** Month-end, as ONE line inside the card, with its Watch door. */
function monthEndLine(model, ui) {
    const me = model.monthEnd || {};
    if (!me.cutoff || ui.monthEndSkipped) {
        return "";
    }
    const days = me.days || 0;
    const when = days <= 0 ? T("monthEndToday")
        : `${T("monthEndIn")}${SP}${days}${SP}${T(days === 1 ? "dayWord" : "daysWord")}`;
    const watch = (ui.scenarioKeys || new Set()).has("sc_payslips")
        ? `<button type="button" class="lrn-lib-chip" data-scenario="sc_payslips" data-mode="watch">${ic("play")}${esc(T("scWatch"))}</button>` : "";
    return `<div class="lrn-lib-cline">${ic("calendar")}<span><b>${esc(when)}</b>${SP}${esc(T("libMonthEnd"))}</span>${watch}</div>`;
}

/** "New here? Take the tour", for a person with nothing started. */
function tourLine(model) {
    const t = model.tour;
    if (!t) {
        return "";
    }
    return `<div class="lrn-lib-cline">${ic("sparkles")}<span>${esc(fmt(T("libTour"), { n: t.steps }))}</span>
        <button type="button" class="lrn-lib-chip" data-scenario="${esc(t.key)}" data-mode="watch">${ic("play")}${esc(T("scWatch"))}</button></div>`;
}

const PIP = `<span class="lrn-lib-pip" aria-hidden="true"></span>`;

/** The path strip (S3): the role's required lessons, then "Change role". */
export function pathStripHTML(model) {
    if (!model.path.length) {
        return "";
    }
    const current = model.cont.kind === "station" ? model.cont.item.key : "";
    const steps = model.path.map((s) => {
        const ring = model.groups.flatMap((g) => g.rows).find((r) => r.station.key === s.key);
        const state = ring && ring.ring === "done" ? "done" : (s.key === current ? "now" : "todo");
        const mark = state === "done" ? ic("check") : PIP;
        return `<li><button type="button" class="lrn-lib-step ${state}" data-station="${esc(s.key)}"
            aria-current="${state === "now" ? "step" : "false"}">${mark}<span>${esc(tx(s.name))}</span></button></li>`;
    }).join("");
    return `<nav class="lrn-lib-path" aria-label="${esc(T("libPathTitle"))}">
        <ol>${steps}<li><button type="button" class="lrn-lib-step change" data-act="lib-roles">${ic("rotate-ccw")}<span>${esc(T("libChangeRole"))}</span></button></li></ol>
    </nav>`;
}

const RING_LABEL = { done: "libRingDone", started: "libRingStarted", none: "libRingNone" };

/** One screen's row (S4): ring, title, one line, at most three doors. */
export function rowHTML(row) {
    const s = row.station;
    const status = row.status === "menu"
        ? `<span class="lrn-lib-tag menu">${ic("lock")}${esc(T("notVisible"))}</span>`
        : (row.status === "required" ? `<span class="lrn-lib-tag req">${esc(T("required"))}</span>` : "");
    const chips = [`<button type="button" class="lrn-lib-chip pri" data-act="lib-guide" data-key="${esc(s.key)}"
        >${ic("panel-right")}${esc(T("libGuide"))}</button>`];
    if (row.doors.watch) {
        chips.push(`<button type="button" class="lrn-lib-chip" data-scenario="${esc(row.doors.watch)}" data-mode="watch"
            >${ic("play")}${esc(T("scWatch"))}</button>`);
    }
    if (row.doors.try) {
        chips.push(`<button type="button" class="lrn-lib-chip" data-scenario="${esc(row.doors.try)}" data-mode="try"
            >${ic("flask")}${esc(T("scTry"))}</button>`);
    }
    return `<li class="lrn-lib-row ${row.ring}" tabindex="0" data-lib-row="${esc(s.key)}">
        <span class="lrn-lib-ring ${row.ring}" role="img" aria-label="${esc(T(RING_LABEL[row.ring]))}"
            title="${esc(T(RING_LABEL[row.ring]))}">${row.ring === "done" ? ic("check") : ""}</span>
        <span class="lrn-lib-main" data-station="${esc(s.key)}">
            <span class="lrn-lib-title"><b>${esc(tx(s.name))}</b>${status}</span>
            <small>${esc(tx(s.summary))}</small>
        </span>
        <span class="lrn-lib-chips">${chips.join("")}</span>
    </li>`;
}

/** Browse by screen: eight groups in menu order (S4). */
export function browseHTML(model, screens, ui = {}) {
    const open = ui.openGroups || new Set();
    return `<div class="lrn-lib-groups">${model.groups.filter((g) => g.rows.length).map((g) => {
        const done = g.rows.filter((r) => r.ring === "done").length;
        const isOpen = open.has(g.key);
        return `<section class="lrn-lib-group${isOpen ? " open" : ""}" data-group="${g.key}">
            <h3 class="lrn-lib-ghead"><button type="button" data-act="lib-group" data-group="${g.key}"
                aria-expanded="${isOpen ? "true" : "false"}" aria-controls="lrn-lib-g-${g.key}">
                <span class="lrn-lib-gic">${ic(g.icon)}</span>
                <span class="lrn-lib-gname">${esc(groupName(g.key, screens))}</span>
                <span class="lrn-lib-gcount">${done}${SP}/${SP}${g.rows.length}</span>
                <span class="lrn-lib-gchev">${ic("chevron-down")}</span></button></h3>
            <ul class="lrn-lib-rows" id="lrn-lib-g-${g.key}">${g.rows.map(rowHTML).join("")}</ul>
        </section>`;
    }).join("")}</div>`;
}

/** The Practice row (S7): the practice company, and the guided practice. */
export function practiceRowHTML(model) {
    return `<div class="lrn-lib-extra" data-lib="practice">
        <span class="lrn-lib-xico">${ic("flask")}</span>
        <span class="lrn-lib-main"><b>${esc(T("libPractice"))}</b><small>${esc(T("libPracticeLead"))}</small></span>
        <span class="lrn-lib-chips">
            <button type="button" class="lrn-btn sm pri" data-act="to-practice">${ic("compass")}${esc(T(model.demoWorld ? "libPracticeDemo" : "libPracticeCopy"))}</button>
            <button type="button" class="lrn-btn sm ghost" data-act="to-missions">${ic("list-checks")}${esc(T("missions"))}</button>
        </span>
    </div>`;
}

/** The Practice row (journey's `_practiceCardHTML`, or the default) and, for
 *  managers, Team readiness. */
export function moreHTML(model, practice) {
    const team = model.team ? `<div class="lrn-lib-extra" data-lib="team">
        <span class="lrn-lib-xico">${ic("users")}</span>
        <span class="lrn-lib-main"><b>${esc(T("libTeam"))}</b><small>${esc(T("libTeamLead"))}</small></span>
        <span class="lrn-lib-chips"><button type="button" class="lrn-btn sm" data-act="lib-team">${ic("arrow-right")}${esc(T("libTeamOpen"))}</button></span>
    </div>` : "";
    return `<div class="lrn-lib-more">${practice || practiceRowHTML(model)}${team}</div>`;
}

/* The key, not words: the same in every language (so not a chrome string —
   test_bundle's parity check would read it as untranslated). */
const KBD = "⌘K";

/** The search box (S5). Its results are drawn into `[data-lib-results]` by
 *  the Journey without a re-render, so typing never loses the caret. */
export function searchBoxHTML(query) {
    return `<div class="lrn-lib-search" role="search">
        ${ic("search")}
        <input type="search" data-lib-q="1" value="${esc(query || "")}" autocomplete="off"
            placeholder="${esc(T("search"))}" aria-label="${esc(T("search"))}"
            aria-controls="lrn-lib-results"/>
        <kbd class="lrn-lib-kbd" title="${esc(T("libKbdHint"))}">${KBD}</kbd>
    </div>`;
}

/** The whole Library. */
export function libraryHTML(model, screens, ui = {}) {
    const q = String(ui.query || "");
    return `<div class="lrn-lib${q.trim() ? " searching" : ""}" data-lib="root">
        ${searchBoxHTML(q)}
        <div class="lrn-lib-results" id="lrn-lib-results" data-lib-results="1" aria-live="polite"></div>
        <div class="lrn-lib-home">
            ${continueHTML(model, ui)}
            ${pathStripHTML(model)}
            <h2 class="lrn-lib-browse">${esc(T("libBrowse"))}</h2>
            ${browseHTML(model, screens, ui)}
            ${moreHTML(model, ui.practice)}
        </div>
    </div>`;
}

/* ------------------------------------------------------------- the search */
/** Lower case, accents off ("vai trò" = "vai tro"), "đ" = "d". */
export function fold(s) {
    return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "")
        .replace(/[đĐ]/g, "d").toLowerCase().replace(/\s+/g, " ").trim();
}

function both(pair) {
    if (!pair) {
        return [];
    }
    if (typeof pair === "string") {
        return [pair];
    }
    return [pair.en, pair.vi].filter(Boolean);
}

/** Every searchable thing, once per language load:
 *  {kind, key, title, sub, titles (folded), hay (folded), ...target}. */
export function buildIndex(src, fieldRows) {
    const out = [];
    const add = (e, titles, words) => {
        e.titles = titles.map(fold).filter(Boolean);
        e.hay = fold([...titles, ...words].join(" "));
        out.push(e);
    };
    const stations = src.stations || [];
    const nameOf = new Map(stations.map((s) => [s.key, s]));
    for (const s of stations) {
        add({ kind: "screen", key: s.key, title: tx(s.name), sub: tx(s.summary) },
            both(s.name), [...both(s.summary), ...both(s.search)]);
    }
    for (const r of fieldRows || []) {
        // The same column can sit on two screens (Pay role: Component
        // treatment's board AND Mapping's inspector). The screen whose own
        // authored search words name it is where people go for it, so that
        // one wins a tie (`home`, read by `search`).
        const owner = nameOf.get(r.screen);
        add({ kind: "field", key: `${r.screen}.${r.key}`, screen: r.screen, field: r.key,
              title: r.column, sub: fmt(T("libFieldOn"), { screen: r.screen_name || r.screen }),
              line: r.line || "", home: fold(both(owner && owner.search).join(" ")) },
            [r.column, ...(r.columns || [])], [r.line || "", ...(r.screen_names || [])]);
    }
    for (const g of src.glossary || []) {
        add({ kind: "term", key: g.key, title: tx(g.term), sub: tx(g.definition) },
            both(g.term), [...both(g.definition), ...((g.aliases || {}).en || []),
                           ...((g.aliases || {}).vi || [])]);
    }
    for (const sc of src.scenarios || []) {
        if (sc.retired || !(sc.modes || []).length) {
            continue;
        }
        add({ kind: "task", key: sc.key, title: tx(sc.name), sub: tx(sc.tagline),
              mode: sc.modes.includes("watch") ? "watch" : sc.modes[0] },
            both(sc.name), both(sc.tagline));
    }
    for (const s of stations) {
        const steps = ((s.lessons || [])[0] || {}).steps || [];
        steps.forEach((st, i) => {
            if (!st.title) {
                return;
            }
            const owner = nameOf.get(s.key);
            add({ kind: "lesson", key: `${s.key}.${i}`, station: s.key, step: i, title: tx(st.title),
                  sub: fmt(T("libLessonStep"), { lesson: tx(owner.name), n: i + 1 }) },
                both(st.title), []);
        });
    }
    return out;
}

/** The hits for `query`, best first: the whole words as a title, then a
 *  title that starts with them, then every word in the title, then every
 *  word anywhere. A tie goes to the kind earlier in KINDS (a field before a
 *  term, so "pay role" lands on the field card). */
export function search(index, query, max = MAX_HITS) {
    const q = fold(query);
    if (!q) {
        return [];
    }
    const words = q.split(" ");
    const scored = [];
    for (const e of index || []) {
        let s = 0;
        if (e.titles.some((t) => t === q)) {
            s = 100;
        } else if (e.titles.some((t) => t.startsWith(q))) {
            s = 80;
        } else if (e.titles.some((t) => words.every((w) => t.includes(w)))) {
            s = 60;
        } else if (words.every((w) => e.hay.includes(w))) {
            s = 30;
        }
        if (s) {
            const home = e.home && e.titles.some((t) => e.home.includes(t)) ? 0.4 : 0;
            scored.push([s - KINDS.indexOf(e.kind) * 0.5 + home, e]);
        }
    }
    scored.sort((a, b) => b[0] - a[0]);
    return scored.slice(0, max).map((x) => x[1]);
}

/** The results list, or the honest empty state with "Ask PayAI". */
export function resultsHTML(hits, query, opts = {}) {
    const q = String(query || "").trim();
    if (!q) {
        return "";
    }
    if (!hits.length) {
        return `<div class="lrn-lib-empty">
            <p>${ic("search")}<span>${esc(fmt(T("libNoMatch"), { q }))}</span></p>
            ${opts.canAsk === false ? "" : `<button type="button" class="lrn-btn sm pri" data-act="lib-ask">${ic("message-circle")}${esc(T("libAsk"))}</button>`}
        </div>`;
    }
    const rows = hits.map((h, i) => {
        const open = opts.openTerm === h.key && h.kind === "term";
        const sub = h.kind === "field" && h.line ? `${h.sub}${SP}·${SP}${h.line}` : h.sub;
        return `<li class="lrn-lib-hit${open ? " open" : ""}" data-kind="${h.kind}">
            <button type="button" data-act="lib-hit" data-i="${i}"${h.kind === "term"
                ? ` aria-expanded="${open ? "true" : "false"}"` : ""}>
                <span class="lrn-lib-kind k-${h.kind}">${ic(KIND_ICON[h.kind])}${esc(T(KIND_LABEL[h.kind]))}</span>
                <span class="lrn-lib-htx"><b>${esc(h.title)}</b><small>${esc(h.kind === "term" && open ? "" : sub)}</small></span>
                ${ic(h.kind === "term" ? "chevron-down" : "arrow-right")}
            </button>
            ${open ? `<p class="lrn-lib-def">${esc(h.sub)}</p>` : ""}
        </li>`;
    }).join("");
    return `<p class="lrn-lib-count">${esc(fmt(T("libResults"), { n: hits.length }))}</p><ul class="lrn-lib-hits">${rows}</ul>`;
}

/** For the tests: the language the renderer is reading. */
export function lang() {
    return RT.lang;
}
