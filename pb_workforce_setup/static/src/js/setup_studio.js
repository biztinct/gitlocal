/** @odoo-module **/
/**
 * Workforce setup — the Setup Studio client action (WFSETUP P1).
 *
 * Three columns, as the design of record: the seven steps in order with live
 * status on the left, the one thing being done now in the centre, and a real
 * person on the right. The tag starts with `pb_` so the Payobook sidebar stays
 * (facts H). The current step lives in the URL (`?step=`) so a refresh lands
 * on the same step.
 *
 * Data: ONE `load()` payload; every save is followed by one `refresh()` that
 * is sequence-guarded against out-of-order replies (precedent `workspace.js`).
 * Children keep their unsaved work locally and register a leave guard that
 * saves it before the step changes.
 */
import { Component, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { router } from "@web/core/browser/router";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { MODEL, icon, errorText, deepClone } from "./setup_util";
import { StepShifts } from "./step_shifts";
import { StepWeeks } from "./step_weeks";
import { StepPeople } from "./step_people";
import { StepRules } from "./step_rules";
import { StepSoon } from "./step_soon";
import { PreviewPanel } from "./preview_panel";

const ACTION_XMLID = "pb_workforce_setup.action_setup_studio";
const TOAST_MS = 8000;

function stepList() {
    return [
        { key: "shifts", n: 1, title: _t("Shifts"), icon: "clock", next: _t("Next: build the working week") },
        { key: "weeks", n: 2, title: _t("Working weeks"), icon: "repeat", next: _t("Next: choose who works what") },
        { key: "people", n: 3, title: _t("Who works what"), icon: "users", next: _t("Next: late and overtime rules") },
        { key: "rules", n: 4, title: _t("Late and overtime rules"), icon: "sliders", next: _t("Next: holidays") },
        { key: "holidays", n: 5, title: _t("Holidays"), icon: "calendar", next: _t("Next: time clocks") },
        { key: "clocks", n: 6, title: _t("Time clocks"), icon: "plug", next: _t("Next: check and go live") },
        { key: "live", n: 7, title: _t("Check and go live"), icon: "send", next: "" },
    ];
}

export class SetupStudio extends Component {
    static template = "pb_workforce_setup.SetupStudio";
    static components = { HubBackChip, StepShifts, StepWeeks, StepPeople, StepRules, StepSoon, PreviewPanel };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.icon = icon;
        this.root = useRef("root");
        this.steps = stepList();
        this.back = hubBack(this.props);
        this.guards = new Set();
        this.state = useState({
            loading: true,
            error: "",
            data: null,
            step: this.initialStep(),
            personId: false,
            moving: false,
            // step 4: the screen's values, unsaved edits included (the pay
            // example on the right works them out as you type)
            rules: null,
            rulesRev: 0,
            rulesInvalid: false,
            confirming: false,
            toast: null,
        });
        this.rulesBusy = false;
        this.confirmFn = null;
        const studio = this;
        // The studio API the children call. A plain object, so a child never
        // needs the root component itself.
        this.api = {
            addGuard: (fn) => this.addGuard(fn),
            go: (key) => this.go(key),
            refresh: () => this.refresh(),
            putShift: (row) => this.put("shifts", row),
            dropShift: (id) => this.drop("shifts", id),
            putWeek: (row) => this.put("weeks", row),
            dropWeek: (id) => this.drop("weeks", id),
            setPerson: (id) => this.setPerson(id),
            stepMeta: (key) => this.steps.find((s) => s.key === key),
            toast: (msg, opts) => this.toast(msg, opts),
            get rules() { return studio.state.rules; },
            get rulesInvalid() { return studio.state.rulesInvalid; },
            rulesEdited: () => { this.state.rulesRev++; },
            setRules: (payload) => {
                this.state.rules = payload ? deepClone(payload) : null;
                this.state.rulesRev++;
            },
            setRulesBusy: (busy) => { this.rulesBusy = !!busy; },
            setRulesInvalid: (bad) => { this.state.rulesInvalid = !!bad; },
            setConfirming: (on) => { this.state.confirming = !!on; },
            onConfirm: (fn) => {
                this.confirmFn = fn;
                return () => { if (this.confirmFn === fn) { this.confirmFn = null; } };
            },
            get motion() {
                return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
            },
        };
        // Record the step in the action's state now, not only on a change:
        // the action service writes the URL from that state once mounted, and
        // without it a reload on `?step=weeks` loses the parameter (WS4).
        this.props.updateActionState?.({ step: this.state.step });
        onWillStart(() => this.load());
        onWillUnmount(() => clearTimeout(this.toastTimer));
    }

    // ------------------------------------------------------------ the URL
    initialStep() {
        const keys = stepList().map((s) => s.key);
        const ctx = this.props.action?.context || {};
        const cur = router.current || {};
        const mine = [this.props.action?.id, this.props.action?.xml_id, this.props.action?.path, ACTION_XMLID]
            .filter(Boolean).map(String);
        if (cur.step && keys.includes(cur.step) && mine.includes(String(cur.action))) {
            return cur.step;
        }
        if (ctx.pb_setup_step && keys.includes(ctx.pb_setup_step)) {
            return ctx.pb_setup_step;
        }
        return "shifts";
    }

    // ------------------------------------------------------------ data
    async load() {
        const seq = (this.seq = (this.seq || 0) + 1);
        this.state.loading = !this.state.data;
        this.state.error = "";
        try {
            const data = await this.orm.call(MODEL, "load", [this.state.personId || false]);
            if (seq === this.seq) {
                this.state.data = data;
                this.state.personId = data.person ? data.person.id : false;
                this.state.rules = data.rules ? deepClone(data.rules) : null;
                this.state.rulesRev++;
            }
        } catch (e) {
            if (seq === this.seq) {
                this.state.error = errorText(e);
            }
        } finally {
            if (seq === this.seq) {
                this.state.loading = false;
            }
        }
    }

    /** One load()-style refresh after any save; a late reply never wins. */
    async refresh() {
        const seq = (this.seq = (this.seq || 0) + 1);
        try {
            const data = await this.orm.call(MODEL, "load", [this.state.personId || false]);
            if (seq === this.seq && this.state.data) {
                Object.assign(this.state.data, data);
                // never over the top of rule edits that are still being saved
                if (data.rules && !this.rulesBusy) {
                    this.state.rules = deepClone(data.rules);
                    this.state.rulesRev++;
                }
            }
        } catch (e) {
            if (seq === this.seq) {
                this.toast(errorText(e), { kind: "error" });
            }
        }
    }

    retry() {
        this.state.data = null;
        this.load();
    }

    put(list, row) {
        const rows = this.state.data[list];
        const i = rows.findIndex((r) => r.id === row.id);
        if (i >= 0) {
            rows[i] = row;
        } else {
            rows.push(row);
        }
    }

    drop(list, id) {
        const rows = this.state.data[list];
        const i = rows.findIndex((r) => r.id === id);
        if (i >= 0) {
            rows.splice(i, 1);
        }
    }

    /** The right panel follows one person: fetch only that person's week
     *  (a whole load() per row click would recount every step). */
    async setPerson(id) {
        if (!id || id === this.state.personId) {
            return;
        }
        this.state.personId = id;
        const seq = (this.personSeq = (this.personSeq || 0) + 1);
        try {
            const person = await this.orm.call(MODEL, "person_week", [id]);
            if (seq === this.personSeq && this.state.data && this.state.personId === id) {
                this.state.data.person = person;
            }
        } catch (e) {
            if (seq === this.personSeq) {
                this.toast(errorText(e), { kind: "error" });
            }
        }
    }

    // ------------------------------------------------------------ steps
    addGuard(fn) {
        this.guards.add(fn);
        return () => this.guards.delete(fn);
    }

    async go(key) {
        if (key === this.state.step || this.state.moving) {
            return;
        }
        this.state.moving = true;
        try {
            for (const guard of [...this.guards]) {
                if (!(await guard())) {
                    return;         // a refused save stays where its sentence is
                }
            }
            this.state.step = key;
            this.props.updateActionState?.({ step: key });
            this.root.el?.scrollTo({ top: 0, behavior: this.api.motion });
        } finally {
            this.state.moving = false;
        }
    }

    // ------------------------------------------------------------ the toast
    /**
     * The studio's own toast (design of record `.toast`): a dark pill at the
     * bottom centre of the working area, just above where step 3's bulk bar
     * sits, ~8 s, with Undo when the change can be undone. One at a time; a
     * new one replaces the last. Used by every step instead of the web
     * client's top-right notifications.
     */
    toast(msg, opts = {}) {
        clearTimeout(this.toastTimer);
        const id = (this.toastSeq = (this.toastSeq || 0) + 1);
        this.state.toast = {
            id,
            msg: String(msg || ""),
            kind: opts.kind || "ok",
            undo: opts.undo || null,
            left: this.stageCentre(),
        };
        this.toastTimer = setTimeout(() => {
            if (this.state.toast && this.state.toast.id === id) {
                this.state.toast = null;
            }
        }, opts.ms || TOAST_MS);
    }
    stageCentre() {
        const el = this.root.el?.querySelector(".pbws-stage");
        if (!el) {
            return null;
        }
        const r = el.getBoundingClientRect();
        return Math.round(r.left + r.width / 2);
    }
    get toastStyle() {
        const t = this.state.toast;
        return t && t.left ? `left:${t.left}px` : "";
    }
    get toastIcon() {
        const kind = this.state.toast?.kind;
        return kind === "error" ? "triangleAlert" : kind === "info" ? "info" : "checkCircle";
    }
    onToastUndo() {
        const t = this.state.toast;
        clearTimeout(this.toastTimer);
        this.state.toast = null;
        t?.undo?.();
    }
    closeToast() {
        clearTimeout(this.toastTimer);
        this.state.toast = null;
    }

    // ------------------------------------------------------------ step 4 confirm
    /** On step 4, while the rules can still be changed, the bar's one solid
     *  button confirms them instead of moving on (design of record). */
    get confirmShown() {
        return this.state.step === "rules" && !!this.state.rules?.can_edit;
    }
    get confirmLabel() {
        return this.state.rules?.state === "revision" ? _t("Confirm the new version") : _t("These rules are right. Confirm");
    }
    async confirmRules() {
        if (this.state.confirming || !this.confirmFn) {
            return;
        }
        await this.confirmFn();
    }

    get data() { return this.state.data; }
    get current() { return this.steps.find((s) => s.key === this.state.step) || this.steps[0]; }
    get prevStep() { return this.steps[this.current.n - 2] || null; }
    get nextStep() { return this.steps[this.current.n] || null; }
    status(key) {
        return (this.data?.steps || []).find((s) => s.key === key) || { state: "todo", text: "" };
    }
    get doneCount() {
        return (this.data?.steps || []).filter((s) => s.state === "done").length;
    }
    get progressLine() {
        return _t("%(done)s of %(total)s", { done: this.doneCount, total: this.steps.length });
    }
    get progressStyle() {
        return `width:${(this.doneCount / this.steps.length) * 100}%`;
    }
    stepClass(step) {
        const st = this.status(step.key).state;
        return `pbws-step is-${st}${step.key === this.state.step ? " is-cur" : ""}`;
    }
    get skeletonRows() { return [1, 2, 3, 4, 5, 6, 7]; }
}

registry.category("actions").add("pb_workforce_setup_studio", SetupStudio);
