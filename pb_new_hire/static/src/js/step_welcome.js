/** @odoo-module **/
/**
 * Step 6 — Welcome and first day (NEWHIRE P2).
 *
 * The hero of this phase is "What happens, and when": a dated timeline built
 * by the server from the joining checklist that will really be picked, which
 * re-flows the moment the first day, the manager, the sign-in, the buddy or an
 * equipment chip changes. HR sees the whole first fortnight before pressing a
 * single button.
 *
 * Every control says what it really does: a sign-in mode that cannot work is
 * shown disabled with the reason and a way to fix it (never hidden); a buddy
 * the onboarding rule refuses is listed with its reason; your own fields that
 * are required here are required on the record, so they block Send.
 */
import { Component, useEffect, useRef, useState, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { IC } from "@pb_import_kit/js/import_icons";
import { icon, initials, fmtDay, ownMissingOf } from "./studio_util";

export class StepWelcome extends Component {
    static template = "pb_new_hire.StepWelcome";
    static props = { api: Object };

    setup() {
        this.icon = icon;
        this.initials = initials;
        this.nh = useState(this.props.api.nh);
        this.ui = useState({ q: "", open: false, list: [], active: 0, busy: false });
        this.pickRef = useRef("buddy");
        this.timer = null;
        onWillUnmount(() => clearTimeout(this.timer));
        // the chips start on the usual ones the first time the step is seen
        useEffect(() => { this.props.api.initEquipment(); }, () => [this.nh.welcome]);
    }

    get api() { return this.props.api; }
    get d() { return this.nh.draft; }
    get w() { return this.nh.welcome; }
    get first() { return this.api.first; }
    err(field) { return this.nh.fieldErr[field] || ""; }
    get heading() { return _t("How will %s be welcomed?", this.first); }
    get loading() { return !this.w; }

    // ------------------------------------------------------------ the checklist switch
    get caseInfo() { return (this.w && this.w.case) || { available: false }; }
    get caseOn() { return this.d.open_case !== false; }
    toggleCase() { this.api.set("open_case", !this.caseOn); }
    get caseTitle() {
        return this.caseInfo.available ? _t("Start the joining checklist") : _t("No joining checklist is set up");
    }
    get caseSub() {
        const c = this.caseInfo;
        if (!c.available) {
            return _t("Nothing is planned for %s's first weeks. You can add a checklist in Lifecycle, and the next hire gets it.", this.first);
        }
        return this.caseOn
            ? _t("%(name)s, %(n)s steps. %(first)s appears on the New joiners board when the hire is added.",
                 { name: c.template_name, n: c.steps, first: this.first })
            : _t("Switched off for %s: no checklist, buddy or equipment requests.", this.first);
    }
    get collapsed() { return !this.caseOn || !this.caseInfo.available; }

    // ------------------------------------------------------------ sign-in
    get modes() { return (this.w && this.w.login && this.w.login.modes) || []; }
    get mode() { return this.d.login_mode || (this.w && this.w.login && this.w.login.chosen) || "none"; }
    get modeInfo() { return this.modes.find((m) => m.key === this.mode) || null; }
    setMode(m) {
        if (m.available) {
            this.api.set("login_mode", m.key);
        }
    }
    get blockedModes() { return this.modes.filter((m) => !m.available); }
    fixMode(m) {
        if (m.fix === "who") {
            this.api.go("who", "work_email");
        } else if (m.fix === "sched") {
            this.api.go("sched", "clock_code");
        }
    }
    fixLabel(m) {
        return m.fix === "who" ? _t("Add an email") : m.fix === "sched" ? _t("Type a clock number") : "";
    }

    // ------------------------------------------------------------ buddy
    get buddyText() { return this.ui.open ? this.ui.q : (this.d.buddy_name || ""); }
    get buddySub() {
        const boss = this.d.parent_name;
        return this.d.buddy_id
            ? _t("%s is told when the hire is added, and catch-ups are planned.", this.d.buddy_name)
            : (boss ? _t("Left empty, %s is asked to choose one.", boss) : _t("Left empty, the manager is asked to choose one."));
    }
    get buddyPlaceholder() { return _t("Manager chooses"); }
    onBuddyFocus() {
        this.ui.open = true;
        this.ui.q = "";
        this.ui.list = (this.w && this.w.buddies) || [];
        this.ui.active = this.firstOk(this.ui.list);
    }
    onBuddyInput(ev) {
        this.ui.q = ev.target.value;
        this.ui.open = true;
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this.searchBuddy(this.ui.q), 250);
    }
    async searchBuddy(q) {
        const seq = (this.seq = (this.seq || 0) + 1);
        this.ui.busy = true;
        try {
            const rows = q ? await this.api.findBuddies(q) : ((this.w && this.w.buddies) || []);
            if (seq === this.seq) {
                this.ui.list = rows || [];
                this.ui.active = this.firstOk(this.ui.list);
            }
        } finally {
            if (seq === this.seq) {
                this.ui.busy = false;
            }
        }
    }
    firstOk(list) { return Math.max(0, list.findIndex((p) => p.level !== "fail")); }
    onBuddyKey(ev) {
        const list = this.ui.list;
        if (ev.key === "ArrowDown") {
            ev.preventDefault();
            this.ui.open = true;
            this.ui.active = Math.min(list.length - 1, this.ui.active + 1);
        } else if (ev.key === "ArrowUp") {
            ev.preventDefault();
            this.ui.active = Math.max(0, this.ui.active - 1);
        } else if (ev.key === "Enter" && !(ev.metaKey || ev.ctrlKey)) {
            ev.preventDefault();
            const p = list[this.ui.active];
            if (this.ui.open && p) {
                this.chooseBuddy(p);
            }
        } else if (ev.key === "Escape" && this.ui.open) {
            ev.preventDefault();
            ev.stopPropagation();
            this.ui.open = false;
        }
    }
    onBuddyBlur() { setTimeout(() => { this.ui.open = false; }, 120); }
    chooseBuddy(p) {
        if (p.level === "fail") {
            this.api.toast(p.why || _t("This person cannot be a buddy."), { kind: "error" });
            return;
        }
        this.api.patch({ buddy_id: p.id, buddy_name: p.name });
        this.ui.open = false;
    }
    clearBuddy() { this.api.patch({ buddy_id: false, buddy_name: "" }); }
    buddyLine(p) { return [p.job, p.team].filter(Boolean).join(" · "); }
    buddyCls(p, i) {
        return [i === this.ui.active ? "is-active" : "", p.level === "fail" ? "is-off" : ""].join(" ").trim();
    }

    // ------------------------------------------------------------ equipment
    get kit() { return (this.w && this.w.equipment) || []; }
    get chosenKit() { return this.d.equipment || this.kit.filter((c) => c.usual).map((c) => c.id); }
    kitOn(c) { return this.chosenKit.includes(c.id); }
    kitIcon(c) { return IC[c.icon] ? c.icon : "package"; }
    toggleKit(c) {
        const now = new Set(this.chosenKit);
        if (now.has(c.id)) {
            now.delete(c.id);
        } else {
            now.add(c.id);
        }
        this.api.set("equipment", this.kit.filter((k) => now.has(k.id)).map((k) => k.id));
    }

    // ------------------------------------------------------------ letter
    get letter() { return (this.w && this.w.letter) || { available: false }; }
    get letterOn() { return this.letter.available && this.d.letter !== false; }
    toggleLetter() { this.api.set("letter", !this.letterOn); }
    get letterSub() {
        const l = this.letter;
        if (!l.available) {
            return l.reason || "";
        }
        if (!this.letterOn) {
            return _t("No letter is prepared. You can print one later from the contract.");
        }
        const line = _t("In %(lang)s, filled from step 3 and saved to %(first)s's documents for signing on paper.",
                        { lang: l.language, first: this.first });
        return [line, l.note, l.approver_note].filter(Boolean).join(" ");
    }

    // ------------------------------------------------------------ your own fields
    get own() { return (this.w && this.w.own_fields) || []; }
    get ownOk() { return this.own.filter((f) => f.supported); }
    get ownLater() { return this.own.filter((f) => !f.supported); }
    ownValue(f) { return (this.d.own || {})[f.name]; }
    ownText(f) {
        const v = this.ownValue(f);
        return v === undefined || v === null || v === false ? "" : String(v);
    }
    ownId(f) { return `pbnh-f-own-${f.name}`; }
    ownErr(f) { return this.err(`own-${f.name}`); }
    ownMissing(f) { return ownMissingOf(this.nh).some((x) => x.name === f.name); }
    onOwn(f, ev) {
        let v = ev.target.type === "checkbox" ? ev.target.checked : ev.target.value;
        if (f.kind === "integer" || f.kind === "number") {
            v = v === "" ? "" : v;
        }
        this.api.setOwn(f.name, v);
    }
    get ownLaterLine() { return _t("Fill this on %s's record after the hire is added.", this.first); }
    inputType(f) {
        return f.kind === "date" ? "date" : (f.kind === "integer" || f.kind === "number") ? "number" : "text";
    }

    // ------------------------------------------------------------ the timeline
    get timeline() { return (this.w && this.w.timeline) || []; }
    get events() {
        let last = "";
        return this.timeline.map((e, i) => {
            const label = e.past ? _t("Straight away") : fmtDay(e.when);
            const show = label !== last;
            last = label;
            return { ...e, key: `${e.id}:${e.when}:${e.title}:${e.sub}`, label: show ? label : "",
                     style: `animation-delay:${Math.min(i, 20) * 30}ms` };
        });
    }
    get timelineSub() {
        return this.collapsed
            ? _t("Only the first day is planned, because there is no joining checklist.")
            : _t("Built from the joining checklist. Change the first day, the manager, the sign-in or the equipment and it moves with them.");
    }
}
