/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onPatched,
         onWillUnmount, markup, useRef, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/* Lucide paths, inline and owned by this module.
 *
 * NOT `ic()` from the shared kit, and that is the point: importing it would
 * pull `pb_import_kit` into the manifest of the leanest module in the product,
 * and this dashboard is the first screen of every tenant (LOOK ledger rule 19,
 * the module's own docstring rule 2). New icons are added HERE. Never emoji. */
const ICONS = {
    users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    wallet:'<path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0 0 4h14a1 1 0 0 1 1 1v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5"/><path d="M18 12a2 2 0 0 0 0 4h3v-4Z"/>',
    clock:'<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    calculator:'<rect width="16" height="20" x="4" y="2" rx="2"/><path d="M8 6h8"/><path d="M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01M16 18h.01"/>',
    zap:'<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    "trending-up":'<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
    shield:'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/>',
    flag:'<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><path d="M4 22v-7"/>',
    compass:'<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
    "user-plus":'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6"/><path d="M22 11h-6"/>',
    upload:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
    play:'<polygon points="6 3 20 12 6 21 6 3"/>',
    check:'<path d="M20 6 9 17l-5-5"/>',
    calendar:'<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/><path d="M8 2v4"/><path d="M16 2v4"/>',
};

/* =============================================================================
   THE ACTIVATION CHECKLIST — LEARNOS Phase 3
   -----------------------------------------------------------------------------
   Five steps from an empty database to a real pay run. This is the whole of
   what a brand-new tenant admin sees above the KPI strip, and it replaces the
   three-row setup panel that shipped in Phase 0.

   THE SERVER OWNS `done`, THIS TABLE OWNS THE WORDS. Every tick is a count
   taken in `pb.dashboard.get_dashboard_data` — never a browser flag, never
   "you pressed this button once". The payload carries `[{key, done}]` in
   order, and the two learning steps are simply absent from it on a database
   without pb_learn, so nothing here has to guess.

   THE COPY IS PLAIN ENGLISH LITERALS, deliberately. pb_dashboard is not a
   bilingual module — no i18n directory, no learn.string records — so putting
   these five sentences through pb_learn's authoring source would make this
   module depend on the one thing it must not depend on. They are written to
   the same register the learning content is held to: short, one idea each, no
   payroll jargon a beginner has not met.

   `run` is what each button does, and three of the five hand off to the
   scenario engine. That engine belongs to pb_learn, so it is looked up as an
   OPTIONAL service — `useService` throws when a service is missing, and this
   code runs on databases where it is guaranteed to be missing.
   ========================================================================== */
const ACTIVATION = {
    meet: {
        icon: "compass",
        title: _t("Meet Payobook"),
        desc: _t("A 2-minute tour. I drive, you watch."),
        cta: _t("Watch the tour"),
        // LEARNOS Phase 6. What the button says when the walkthrough is
        // half-taken. Only the two learning rows can be half-taken: the other
        // three are database facts, which are true or not.
        resume: _t("Pick up where you left off"),
        run: (self) => self.scenario(SC_WELCOME, "watch"),
    },
    employee: {
        icon: "user-plus",
        title: _t("Add your first employee"),
        desc: _t("A name, a contract, a salary. That is all it takes."),
        cta: _t("Add employee"),
        run: (self) => self.open(ACT_EMPLOYEES),
    },
    import: {
        icon: "upload",
        title: _t("Bring in your payroll Excel"),
        desc: _t("Already have a sheet? Bring everyone in at once."),
        cta: _t("Import data"),
        run: (self) => self.open(ACT_IMPORT),
    },
    practice: {
        icon: "play",
        title: _t("Run a practice payroll"),
        desc: _t("On a made-up company. Nothing here is real."),
        cta: _t("Try it"),
        resume: _t("Pick up where you left off"),
        run: (self) => self.scenario(SC_PAYRUN, "try"),
    },
    real: {
        icon: "zap",
        title: _t("Run your first real payroll"),
        desc: _t("Your own data, with the guide beside you. You press every button."),
        cta: _t("Start"),
        // Do-mode walks the REAL wizard and never presses anything itself.
        // With no guide on this database the honest fallback is the wizard,
        // which is where the step ends up either way.
        run: (self) => self.scenario(SC_PAYRUN, "do", ACT_PAYRUN),
    },
};

// Resolved once, here, so the two buttons and the sidebar leaves they mirror
// cannot drift apart: both leaves carry an EMPTY action_xmlid and are opened by
// TAG (pb_sidebar/data/pb_sidebar_data.xml:77-95, pb_sidebar.js:249). These are
// the client actions behind those tags.
const ACT_EMPLOYEES = "pb_people.action_pb_people";
const ACT_IMPORT = "pb_import.action_pb_import";
const ACT_PAYRUN = "pb_payrun_wizard.action_pb_payrun_wizard";

/* The learning module's scenario engine, and the two walkthroughs the
   checklist offers. Named as STRINGS on purpose: pb_dashboard imports nothing
   from pb_learn and declares nothing about it in its manifest, so the only
   thing that can go stale here is a key, and a stale key degrades to a
   notification rather than to a broken screen. */
const SCENARIO_SERVICE = "learn.scenario";
const SC_WELCOME = "sc_welcome";
const SC_PAYRUN = "sc_payrun";

export class PbDashboard extends Component {
    static template = "pb_dashboard.PbDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.stripRef = useRef("strip");
        this.state = useState({
            d: null,
            loaded: false,
            // What was ASKED for. What was GOT is `state.d.period`, which the
            // server resolved and which this component ADOPTS rather than
            // keeping its own idea of (LOOK rule 18).
            period: "",
            scoping: false,      // a month is being switched to
            stripFocus: "",      // the chip the keyboard is standing on
        });

        // THE DEEP LINK, READ ONCE, in the vocabulary the Budget board already
        // uses: `pb_focus: "month:2026-06"`, `"month:current"` and
        // `"month:2026-03..2026-06"`. Two roads in — the Home hub hands its
        // arrival to a lens that says `wantsArrival`, and the standalone client
        // action carries the same key on its own context. A month this database
        // does not have is not an error: the server answers with the latest one
        // and says it fell back (ledger rule 21).
        const arrival = this.props.arrival || {};
        const ctx = (this.props.action && this.props.action.context) || {};
        const focus = String(arrival.focus || ctx.pb_focus || "");
        if (focus.startsWith("month:")) {
            this.state.period = focus.slice(6);
        }

        onWillStart(async () => {
            await this.load();
            this.state.loaded = true;
        });
        // BOTH hooks. The first read finishes before there is any DOM, so a
        // scroll asked for inside it finds no strip at all — on a phone the
        // board then opened on the oldest month with the newest one chosen
        // and nothing on screen saying where it was.
        onMounted(() => {
            this.keepChosenInView();
            // THE STRIP IS STILL SETTLING when the first frame is painted: at
            // 390 px it was measured 290 px wide at mount and 230 px once the
            // KPI grid above it had finished wrapping, so the correction was
            // computed against a scroll range 60 px shorter than the real one
            // and the newest month stayed half off the right-hand edge. A
            // resize is the only event that says the geometry moved.
            if (window.ResizeObserver && this.stripRef.el) {
                this._ro = new ResizeObserver(() => this.keepChosenInView());
                this._ro.observe(this.stripRef.el);
            }
        });
        onPatched(() => this.keepChosenInView());
        onWillUnmount(() => this._ro && this._ro.disconnect());

        // Capture phase: the platform's own hotkey service listens on `window`
        // and stops propagation for the keys it claims, Escape among them, so
        // a bubble-phase listener in a cockpit never fires (WF4).
        useExternalListener(window, "keydown", (ev) => this.onKey(ev),
                            { capture: true });
    }

    /** The one data call. `period` travels; everything else follows it. */
    async load() {
        this.state.d = await this.orm.call(
            "pb.dashboard", "get_dashboard_data", [this.state.period || null]);
        // ADOPT what the server answered. A link naming a month this database
        // has never had comes back as the latest one, and the strip then shows
        // THAT chip lit rather than a chip that is not there.
        const got = this.state.d && this.state.d.period;
        this.state.period = got ? got.key : "";
        if (got && !this.state.stripFocus) { this.state.stripFocus = got.key; }
    }

    icon(name, size = 18) {
        const p = ICONS[name] || ICONS.users;
        return markup(`<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${p}</svg>`);
    }

    ring(value, size = 66) {
        const v = Math.max(0, Math.min(100, value || 0));
        const c = v >= 70 ? "#10B981" : v >= 40 ? "#B7791F" : "#C0332A";
        const r = (size - 8) / 2, circ = 2 * Math.PI * r, off = circ * (1 - v / 100);
        return markup(`<span class="pbd-ring" style="width:${size}px;height:${size}px">
            <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
              <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="#E7E5F2" stroke-width="6"/>
              <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="${c}" stroke-width="6" stroke-linecap="round"
                stroke-dasharray="${circ}" stroke-dashoffset="${off}" transform="rotate(-90 ${size/2} ${size/2})"/>
            </svg><span class="pbd-ring-n" style="color:${c};font-size:${size*0.3}px">${v}</span></span>`);
    }

    // Compact money. Symbol and side come from the company's currency, which
    // the payload carries; the `₫ before` fallback only covers a stale bundle
    // talking to an older payload.
    money(n) {
        n = n || 0;
        const c = (this.state.d && this.state.d.currency) || {};
        const sym = c.symbol || "₫";
        let v;
        if (n >= 1e9) v = (n / 1e9).toFixed(1) + "B";
        else if (n >= 1e6) v = (n / 1e6).toFixed(1) + "M";
        else if (n >= 1e3) v = (n / 1e3).toFixed(0) + "K";
        else v = String(Math.round(n));
        return c.position === "after" ? v + " " + sym : sym + v;
    }

    // Local browser time — the server's clock is not the reader's.
    greeting() {
        const h = new Date().getHours();
        if (h < 12) return _t("Good morning");
        if (h < 18) return _t("Good afternoon");
        return _t("Good evening");
    }

    companyEyebrow() {
        return `${this.state.d.company} · ${_t("Payroll command centre")}`;
    }

    activeContractsLabel() {
        return _t("%s active contracts", this.state.d.kpis.contracts);
    }

    rulesLabel() {
        return _t("%s rules", this.state.d.formula.rules);
    }

    // A tenant that has not started: nobody under contract, nothing computed,
    // nothing configured. Read during render, so OWL re-renders it when the
    // payload lands.
    //
    // HEADCOUNT CANNOT CARRY THIS TEST. The golden template ships the admin's
    // hr.employee row (id 1, renamed per tenant — "Ash" on abm), so a clone
    // never reports zero headcount and the panel would never appear on the one
    // database it exists for. `contracts` is the honest property: with no
    // employment contract nobody can be paid.
    get isEmpty() {
        const d = this.state.d;
        return !!d && !d.kpis.contracts && !d.run.slips && !d.formula.count;
    }

    // ------------------------------------------------------- the pay month
    /* WHAT THESE FIGURES ARE ABOUT.
     *
     * The headline numbers on this page have always been one payroll month's,
     * and the page never said which — so ₫16.8M of a single November test
     * payslip sat under a headcount of four and a half thousand people and
     * nobody could tell. The month is named first (R4) and the strip is the
     * upgrade. A chip's micro bar is HOW MANY PEOPLE were paid that month
     * against the busiest month: this strip's own question is "was anybody
     * paid, and how many" (ledger rule 19), and the money for the month on
     * screen is the headline figure directly above it. */

    /** The month this board is about, or null on a database with no payroll. */
    get period() { return (this.state.d && this.state.d.period) || null; }

    /** Every payroll month that exists, oldest first. */
    get periods() { return (this.state.d && this.state.d.periods) || []; }

    /** "Figures for November 2026" — the sentence R4 exists for. */
    get periodLine() {
        const p = this.period;
        return p ? _t("Figures for %s", p.label)
                 : _t("No payroll has been run yet");
    }

    /* The four sentences around the strip, each built as ONE string here and
     * printed with a single `t-esc`. A sentence written either side of a
     * `<t t-esc/>` comes out of the extractor as TWO msgids no translator can
     * put into their own word order (L17), and the indentation of an XML file
     * is baked into whatever it does collect. */

    get fellBackLine() {
        const p = this.period;
        return _t("That month is not on this database, so these figures are for %s.",
                  p ? p.label : "");
    }

    get stripHint() {
        return _t("Press a month to read the figures above for it. Arrow keys walk the strip; Escape comes back to the latest month.");
    }

    get emptyStripLead() { return _t("No payroll months yet."); }

    get emptyStripLine() {
        return _t("Once a pay run is done, every month it covers appears here and the figures above can be read for any of them.");
    }

    /** What a chip says when a person hovers or focuses it. ONE expression. */
    chipTitle(mo) {
        if (mo.people === 1) {
            return _t("%s — 1 person was paid.", mo.label);
        }
        if (mo.people) {
            return _t("%(month)s — %(count)s people were paid.",
                      { month: mo.label, count: mo.people.toLocaleString() });
        }
        if (mo.all_slips) {
            return _t("%s — no end-of-month run.", mo.label);
        }
        return _t("%s — nobody was paid.", mo.label);
    }

    /** The line under a chip's bar. Written once, singular included, because
     *  "1 people" is how a screen announces nobody read it (GR42). */
    chipCount(mo) {
        if (mo.people === 1) { return _t("1 person"); }
        if (mo.people) { return _t("%s people", mo.people.toLocaleString()); }
        if (mo.all_slips) { return _t("no end-of-month run"); }
        return _t("nobody paid");
    }

    /** A bar nobody can see is a bar that says nothing.
     *
     *  The floor is on the PEOPLE, not on the share: one person out of four
     *  and a half thousand rounds to nought per cent, and drawing nothing for
     *  them would say "nobody was paid" about a month where somebody was. */
    barWidth(mo) {
        if (!mo || !mo.people) { return 0; }
        return Math.max(4, Math.min(100, Number(mo.share) || 0));
    }

    isLit(key) { return !!this.period && this.period.key === key; }

    /** The caption under a money figure, naming its month so the number can be
     *  checked. Without a month it is the sentence it always was. */
    moneyCaption(base) {
        const p = this.period;
        return p ? _t("%(what)s in %(month)s", { what: base, month: p.label })
                 : base;
    }

    get payrollCaption() { return this.moneyCaption(_t("personnel cost")); }

    /**
     * Pick a month. The board is NOT unmounted: `loaded` stays true, the cards
     * keep their places and the numbers change under them.
     *
     * The busy guard is HERE and never on a chip's `disabled` attribute (T23):
     * disabling the button the keyboard is standing on blurs it, and the next
     * arrow press is then read against a state it was about to change.
     */
    async setPeriod(key) {
        if (this.state.scoping) { return; }
        if (this.state.period === key) { return; }
        this.state.period = key;
        this.state.scoping = true;
        try {
            await this.load();
        } catch (e) {
            this.notification.add(
                _t("That month could not be read. Try again in a moment."),
                { type: "danger" });
            console.warn("pb_dashboard: could not read the month", e);
        } finally {
            this.state.scoping = false;
        }
    }

    /** Escape's way out: back to the latest payroll month, which is where
     *  this board opens and what it reported before it could be moved. */
    async toLatest() {
        const all = this.periods;
        if (!all.length) { return; }
        this.state.stripFocus = all[all.length - 1].key;
        await this.setPeriod(all[all.length - 1].key);
        this.focusChip(this.state.stripFocus);
    }

    async pressChip(mo) {
        this.state.stripFocus = mo.key;
        await this.setPeriod(mo.key);
    }

    /**
     * ← and → walk the strip and Home / End jump to its ends — the ledger's
     * rule 20 contract, the same one the Budget strip answers.
     */
    async onStripKey(ev) {
        const walk = { ArrowLeft: -1, ArrowRight: 1, Home: "first",
                       End: "last" }[ev.key];
        if (walk === undefined) { return; }
        const keys = this.periods.map((m) => m.key);
        if (!keys.length) { return; }
        ev.preventDefault();
        if (this.state.scoping) { return; }
        // WHERE THE KEYBOARD IS STANDING IS THE CHIP THAT HAS FOCUS, never the
        // month in scope: tabbing to April and pressing → must go to May, and
        // reading it off the state would send it somewhere else entirely (T23).
        const chip = ev.target && ev.target.closest
            ? ev.target.closest("[data-month]") : null;
        const from = (chip && chip.dataset.month) || this.state.stripFocus
            || (this.period ? this.period.key : "");
        const here = keys.indexOf(from);
        let next;
        if (walk === "first") {
            next = 0;
        } else if (walk === "last") {
            next = keys.length - 1;
        } else if (here < 0) {
            next = walk > 0 ? 0 : keys.length - 1;
        } else {
            next = Math.min(keys.length - 1, Math.max(0, here + walk));
        }
        const key = keys[next];
        this.state.stripFocus = key;
        await this.setPeriod(key);
        this.focusChip(key);
    }

    focusChip(key) {
        const root = this.stripRef.el;
        if (!root) { return; }
        const el = root.querySelector(`[data-month="${key}"]`);
        if (el) { el.focus(); }
    }

    /**
     * Many months scroll, and the chosen one is never off the end of them.
     *
     * Called from `onMounted` and `onPatched`, not from `load()`: the first
     * read finishes BEFORE there is any DOM, so a scroll asked for there finds
     * no strip and a phone opens on April with November chosen and nothing on
     * screen saying so. A patch only ever follows a change to the data, never a
     * reader scrolling the strip by hand, so this never fights a scroll.
     */
    scrollChosenIntoView() {
        const p = this.period;
        const root = this.stripRef.el;
        if (!p || !root) { return; }
        const el = root.querySelector(`[data-month="${p.key}"]`);
        if (!el) { return; }
        // The arithmetic rather than `scrollIntoView`: `inline: "nearest"` left
        // the last chip half off the right-hand edge at 390 px, and it is free
        // to scroll ANCESTORS as well, which on a phone means the whole page
        // jumps sideways for a chip. This moves one element and no other.
        //
        // MEASURED FROM THE RECTANGLES, not from `offsetLeft`: that is relative
        // to the nearest POSITIONED ancestor, and this strip is not one — so
        // the sum came out 475 px when the answer was 535 and the newest month
        // stayed half off the edge with nothing saying so.
        const sb = root.getBoundingClientRect();
        const cb = el.getBoundingClientRect();
        const pad = 10;
        if (cb.left < sb.left) {
            root.scrollLeft += cb.left - sb.left - pad;
        } else if (cb.right > sb.right) {
            root.scrollLeft += cb.right - sb.right + pad;
        }
    }

    /** The same, once now and once after the browser has finished laying the
     *  page out. At mount the KPI grid above has not settled, so the strip is
     *  briefly WIDER than it ends up: measured then, the correction came out
     *  60 px short and the newest month stayed half off the right-hand edge on
     *  a phone. The second pass costs nothing and is the one that lands. */
    keepChosenInView() {
        this.scrollChosenIntoView();
        if (typeof window.requestAnimationFrame === "function") {
            window.requestAnimationFrame(() => this.scrollChosenIntoView());
        }
    }

    /**
     * Escape means "back to the month this board opens on", and it says so
     * beside the strip. It is claimed ONLY when the reader has actually moved
     * off that month, so every other Escape on the page — the hub's, the
     * platform's — still gets its turn.
     */
    onKey(ev) {
        if (ev.key !== "Escape") { return; }
        const p = this.period;
        if (!p || p.latest || this.state.scoping) { return; }
        ev.stopPropagation();
        this.toLatest();
    }

    // ------------------------------------------------- the activation checklist
    /** The five steps, in payload order, each carrying its words.
     *
     *  The SERVER decides which steps exist and which are done; this only
     *  joins that to the copy. A key the payload names and this table does
     *  not is dropped rather than rendered blank — the alternative is a row
     *  with a button and no sentence.
     */
    get activation() {
        const a = (this.state.d && this.state.d.activation) || null;
        if (!a || !a.show) return null;
        const items = (a.items || [])
            .filter((it) => ACTIVATION[it.key])
            .map((it) => {
                const copy = ACTIVATION[it.key];
                // A step the learner STARTED says so. The server sends
                // `state` for the two learning rows and nothing for the
                // three database facts, so this reads as "not started"
                // everywhere it does not apply — which is correct, not a
                // default: a contract either exists or it does not.
                const resuming = it.state === "in_progress" && !!copy.resume;
                return Object.assign({}, copy, {
                    key: it.key,
                    done: !!it.done,
                    resuming,
                    cta: resuming ? copy.resume : copy.cta,
                });
            });
        if (!items.length) return null;
        // The first step still to do is the one being ASKED for. Everything
        // else is either behind you or waiting its turn, and drawing three
        // primary buttons at once asks somebody to choose where to start on
        // the screen that exists to stop them having to.
        const next = items.findIndex((it) => !it.done);
        return { items, next, doneCount: items.filter((it) => it.done).length };
    }

    /** One handler for all five buttons. The step carries what it does. */
    runStep(item) {
        if (item && typeof item.run === "function") item.run(this);
    }

    // doAction is a promise: a synchronous try/catch around it catches nothing
    // (pb_learn ledger, Phase C review). A module that is not on this database
    // gets a notification, never an unhandled rejection.
    open(xmlid) {
        if (!xmlid) return;
        Promise.resolve(this.action.doAction(xmlid, { clearBreadcrumbs: true })).catch(() => {
            this.notification.add(_t("That screen is not installed on this database."), {
                type: "warning",
            });
        });
    }

    /**
     * The two Analytics doors — the hero button and "Open analytics →".
     *
     * Both used to open `pb_hr_payroll_analytics.action_open_hr_analytics_
     * dashboard`, a NATIVE form on `hr.analytics.dashboard`: the last legacy
     * escape left on the home screen, and the one place in the product where a
     * click on the word "analytics" landed on a record form instead of on the
     * analytics. Cycle 4 built the Insights hub over the four real analytics
     * cockpits, so that is where the word points now, with a back chip that
     * says Home.
     *
     * By XMLID rather than by tag (W98). The `pb_back` payload is written out
     * BY HAND instead of through `@pb_hub/js/hub_nav`'s `openHub`, and that is
     * rule 2 of this file's header being kept rather than an oversight: the
     * dashboard is the first screen of every tenant and declares no cockpit
     * dependency, so importing the hub kit would pull `pb_hub` (and through it
     * `pb_wf_kit`) into the manifest of the leanest module in the product. The
     * shape below is `hub_nav.js`'s `pb_back` contract verbatim — every key it
     * writes, in the same types — and `pb_home_hub/tests` pins the two against
     * each other so a protocol change cannot leave this copy behind.
     *
     * `doAction` is a promise, so a database without the Insights hub gets the
     * same notification every other door here gets rather than an unhandled
     * rejection.
     */
    openInsights() {
        const back = {
            label: _t("Home"), tag: "", xmlid: "pb_home_hub.action_pb_home_hub",
            lens: "", lensKey: "pb_lens", context: {},
        };
        Promise.resolve(this.action.doAction(
            "pb_insights_hub.action_pb_insights_hub",
            { additionalContext: { pb_back: back }, clearBreadcrumbs: true },
        )).catch(() => {
            this.notification.add(_t("That screen is not installed on this database."), {
                type: "warning",
            });
        });
    }

    /** Start a walkthrough, if there is an engine on this database to start it.
     *
     *  `env.services[...]` rather than `useService`, which THROWS on a missing
     *  service — and a home dashboard that will not mount because an optional
     *  learning module is absent is a worse bug than a missing button. Same
     *  optional-lookup idiom pb_learn itself uses for its neighbours.
     *
     *  `fallback` is an xml-id to open instead. Only the last step has one:
     *  "run your first real payroll" is a thing somebody can do without a
     *  guide, and the other two are the guide.
     */
    scenario(key, mode, fallback) {
        const sc = this.env.services && this.env.services[SCENARIO_SERVICE];
        if (!sc) {
            if (fallback) {
                this.open(fallback);
            } else {
                this.notification.add(_t("The guided tour is not installed on this database."), {
                    type: "warning",
                });
            }
            return;
        }
        // begin() returns false for an unknown key and never throws; it is
        // async, so the rejection path needs a .catch of its own.
        Promise.resolve(sc.begin(key, mode)).then((started) => {
            if (!started && fallback) this.open(fallback);
        }).catch(() => {
            if (fallback) this.open(fallback);
        });
    }
}

registry.category("actions").add("pb_dashboard", PbDashboard);
