/** @odoo-module **/

import { Component, useState, onWillStart, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

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
        title: "Meet Payobook",
        desc: "A 2-minute tour. I drive, you watch.",
        cta: "Watch the tour",
        // LEARNOS Phase 6. What the button says when the walkthrough is
        // half-taken. Only the two learning rows can be half-taken: the other
        // three are database facts, which are true or not.
        resume: "Pick up where you left off",
        run: (self) => self.scenario(SC_WELCOME, "watch"),
    },
    employee: {
        icon: "user-plus",
        title: "Add your first employee",
        desc: "A name, a contract, a salary. That is all it takes.",
        cta: "Add employee",
        run: (self) => self.open(ACT_EMPLOYEES),
    },
    import: {
        icon: "upload",
        title: "Bring in your payroll Excel",
        desc: "Already have a sheet? Bring everyone in at once.",
        cta: "Import data",
        run: (self) => self.open(ACT_IMPORT),
    },
    practice: {
        icon: "play",
        title: "Run a practice payroll",
        desc: "On a made-up company. Nothing here is real.",
        cta: "Try it",
        resume: "Pick up where you left off",
        run: (self) => self.scenario(SC_PAYRUN, "try"),
    },
    real: {
        icon: "zap",
        title: "Run your first real payroll",
        desc: "Your own data, with the guide beside you. You press every button.",
        cta: "Start",
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
        this.state = useState({ d: null, loaded: false });
        onWillStart(async () => {
            this.state.d = await this.orm.call("pb.dashboard", "get_dashboard_data", []);
            this.state.loaded = true;
        });
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
        if (h < 12) return "Good morning";
        if (h < 18) return "Good afternoon";
        return "Good evening";
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
            this.notification.add("That screen is not installed on this database.", {
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
                this.notification.add("The guided tour is not installed on this database.", {
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
