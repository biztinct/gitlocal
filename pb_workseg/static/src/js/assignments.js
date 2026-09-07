/** @odoo-module **/
/**
 * "Where they work" — the month as a strip of days.
 *
 * THE HERO IS THE STRIP. A month is thirty little cells. Drag across ten of
 * them, say where those days were worked and under which payroll scheme, and
 * beneath the strip two payslips draw themselves — Vietnam, twenty days;
 * Singapore, ten days — each in its own money, with the pattern named on a
 * chip. Switch the chip to "Home pays, the other entity is charged" and the
 * second payslip folds into one line: "₫4.2M charged to Payobook Singapore".
 * Nothing is saved until Confirm.
 *
 * The point of drawing it rather than typing it is that a month HAS a shape:
 * weekends, the day somebody left, the ten days in the middle. Two date boxes
 * make you hold that shape in your head. Thirty cells put it on the screen.
 *
 * THE SECOND SURFACE IS "SAME PERSON?" — pairs of employee records that look
 * like one human being, with the evidence that says so, and one press to join
 * them. It is the same screen with a different focus, because the two things
 * are one idea: a person is a human, not a record.
 *
 * THE RULES THIS FILE KEEPS
 *   * Every icon comes from the shared `ic()` set — no emoji, no glyph arrows.
 *   * Every sentence is ONE expression: JavaScript has no implicit string
 *     concatenation and a Python habit here kills the whole asset bundle.
 *   * Escape is registered with `{ capture: true }`, because the platform's
 *     own hotkey service listens on `window` and stops propagation for the
 *     keys it claims — Escape among them (WFPLAN WF4).
 *   * The refusal ladder is `error.data.message` → `error.message.data.message`
 *     → OUR OWN sentence. `error.message` is not a rung: on this platform it
 *     is the literal words "Odoo Server Error" (ledger GR17).
 *   * Small metadata lives in `useState`; nothing this screen reads sits on
 *     the instance behind a revision gate (GR26).
 */
import {
    Component, onWillStart, useExternalListener, useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";

const MODEL = "pb.assignments";

/** The kinds of stretch, in the words the screen uses. */
function kindOptions() {
    return [
        { key: "split", label: _t("Days in another entity") },
        { key: "transfer", label: _t("Moved to another entity") },
        { key: "parttime", label: _t("Part-time arrangement") },
    ];
}

const BLANK_DRAFT = {
    id: 0, host_company_id: 0, host_employee_id: 0, division_id: 0,
    config_id: 0, kind: "split", pay_policy: "inherit",
    date_from: "", date_to: "", note: "",
};

export class PbAssignmentsScreen extends Component {
    static template = "pb_workseg.PbAssignments";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.back = hubBack(this.env, this.props);

        const context = (this.props.action && this.props.action.context) || {};
        this.state = useState({
            loaded: false,
            busy: false,
            failed: "",
            room: null,
            // "days" is the strip; "merge" is the Same person? review.
            focus: context.pb_focus === "merge" ? "merge" : "days",
            month: "",
            // The selection being drawn on the strip, and the popover over it.
            anchor: "",
            hover: "",
            dragging: false,
            popover: false,
            draft: { ...BLANK_DRAFT },
            preview: null,
            previewing: false,
            dialogError: "",
            // "Create the employment in <entity>" — shown before it happens.
            makePlan: null,
            review: null,
            reviewing: false,
        });

        onWillStart(async () => {
            this.env.config.setDisplayName(
                this.state.focus === "merge"
                    ? _t("Same person?") : _t("Where people work"));
            await this.load();
            if (this.state.focus === "merge") { await this.loadReview(); }
        });

        useExternalListener(window, "keydown", (ev) => this.onKey(ev),
                            { capture: true });
        useExternalListener(window, "mouseup", () => this.endDrag());
    }

    ic(name, size = 16) { return ic(name, size); }

    // ================================================================ reading
    async load(personId = 0, month = "") {
        try {
            this.state.room = await this.orm.call(MODEL, "get_screen", [
                personId || (this.person ? this.person.id : 0), 0,
                month || this.state.month || null,
            ]);
            this.state.month = this.state.room.month || "";
            this.state.failed = "";
        } catch (e) {
            this.state.room = null;
            this.state.failed = this._msg(
                e, _t("Where people work could not be read."));
        } finally {
            this.state.loaded = true;
        }
    }

    async loadReview() {
        this.state.reviewing = true;
        try {
            this.state.review = await this.orm.call(MODEL, "get_merge_review",
                                                    [null]);
        } catch (e) {
            this.state.review = {
                allowed: false, suggestions: [], people: 0,
                error: this._msg(e, _t("The review could not be read.")),
            };
        } finally {
            this.state.reviewing = false;
        }
    }

    /** The server's own sentence, or ours — and never the platform's (GR17). */
    _msg(error, fallback) {
        const data = (error && error.data)
            || (error && error.message && error.message.data);
        const message = data && (data.message
            || (data.arguments && data.arguments[0]));
        return message || fallback;
    }

    async _write(method, args, done) {
        if (this.state.busy) { return false; }
        this.state.busy = true;
        this.state.dialogError = "";
        try {
            this.state.room = await this.orm.call(MODEL, method, args);
            this.state.month = this.state.room.month || this.state.month;
            this.state.failed = "";
            if (done) { this.notif.add(done, { type: "success" }); }
            return true;
        } catch (e) {
            // A refusal about something the reader is LOOKING AT belongs
            // beside it (GR12): a toast over an open popover is a sentence
            // about a control they can no longer see.
            const message = this._msg(e, _t("That change could not be saved."));
            if (this.state.popover) {
                this.state.dialogError = message;
            } else {
                this.notif.add(message, { type: "danger", sticky: true });
            }
            return false;
        } finally {
            this.state.busy = false;
        }
    }

    // ================================================================ getters
    get room() { return this.state.room || {}; }
    get allowed() { return !!this.room.allowed; }
    get canEdit() { return !!this.room.can_edit; }
    get person() { return this.room.person || null; }
    get employments() { return (this.person && this.person.employments) || []; }
    get days() { return this.room.days || []; }
    get segments() { return this.room.segments || []; }
    get transfers() { return this.room.transfers || []; }
    get companies() { return this.room.companies || []; }
    get divisions() { return this.room.divisions || []; }
    get schemes() { return this.room.schemes || []; }
    get history() { return this.room.history || []; }
    get policies() { return this.room.policies || []; }
    get group() { return this.room.group || null; }
    get kinds() { return kindOptions(); }
    get suggestions() {
        return (this.state.review && this.state.review.suggestions) || [];
    }

    /**
     * A head count in a SENTENCE is read, not calculated.
     *
     * "4,561" is a number a person takes in at a glance; "4561" is a string
     * they have to count the digits of. Formatted here because a template
     * expression is compiled against the component, so `Number(x)` in the
     * markup would be a property of ours that does not exist.
     */
    get peopleCount() {
        const n = Number((this.state.review && this.state.review.people) || 0);
        return n.toLocaleString();
    }

    /** The home employment: the one a stretch of days comes out of. */
    get homeEmployment() {
        return this.employments.find((e) => e.home) || this.employments[0]
            || null;
    }

    /** Only the entities this person does NOT already call home. */
    get hostChoices() {
        const home = this.homeEmployment;
        const mine = home ? home.company_id : 0;
        return this.companies.filter((c) => c.id !== mine);
    }

    get hostCompany() {
        return this.companies.find(
            (c) => c.id === this.state.draft.host_company_id) || null;
    }

    /** The employment in the chosen entity, when there is one. */
    get hostEmployment() {
        const id = this.state.draft.host_company_id;
        return this.employments.find((e) => e.company_id === id) || null;
    }

    get schemeChoices() {
        const id = this.state.draft.host_company_id;
        return this.schemes.filter((s) => !s.company_id || s.company_id === id);
    }

    /** The pattern in force for the stretch being drawn, in words. */
    get draftPolicy() {
        const chosen = this.state.draft.pay_policy;
        if (chosen && chosen !== "inherit") { return chosen; }
        return (this.group && this.group.policy) || "each_pays";
    }

    get draftPolicyLabel() {
        const found = this.policies.find((p) => p.key === this.draftPolicy);
        if (!found) { return ""; }
        return this.state.draft.pay_policy === "inherit"
            ? _t("%(pattern)s · group default", { pattern: found.label })
            : found.label;
    }

    /** How many days the current selection covers, and the month's total. */
    get selection() {
        const from = this.state.draft.date_from;
        const to = this.state.draft.date_to;
        if (!from || !to) { return { days: 0, total: this.workingDays }; }
        const days = this.days.filter(
            (d) => d.date >= from && d.date <= to && d.working).length;
        return { days, total: this.workingDays };
    }

    get workingDays() {
        return this.days.filter((d) => d.working).length;
    }

    /** The stretch a given day already belongs to, or null. */
    segmentOn(day) {
        return this.segments.find(
            (s) => s.date_from <= day.date && s.date_to >= day.date) || null;
    }

    dayClass(day) {
        const parts = ["wsg-day"];
        if (!day.working) { parts.push("is-off"); }
        const seg = this.segmentOn(day);
        if (seg) { parts.push("is-seg"); }
        const from = this.state.draft.date_from;
        const to = this.state.draft.date_to;
        if (from && to && day.date >= from && day.date <= to) {
            parts.push("is-picked");
        }
        return parts.join(" ");
    }

    dayLabel(day) {
        const seg = this.segmentOn(day);
        if (seg) {
            return _t("%(date)s — worked in %(company)s",
                      { date: day.date, company: seg.host_company });
        }
        return day.working ? day.date
            : _t("%(date)s — not a working day", { date: day.date });
    }

    // ================================================================ the strip
    startDrag(day) {
        if (!this.canEdit) { return; }
        this.state.dragging = true;
        this.state.anchor = day.date;
        this._span(day.date, day.date);
    }

    overDay(day) {
        if (!this.state.dragging) { return; }
        this._span(this.state.anchor, day.date);
    }

    endDrag() {
        if (!this.state.dragging) { return; }
        this.state.dragging = false;
        if (this.state.draft.date_from) { this.openPopover(); }
    }

    _span(a, b) {
        const from = a <= b ? a : b;
        const to = a <= b ? b : a;
        this.state.draft.date_from = from;
        this.state.draft.date_to = to;
    }

    /**
     * Keyboard reach over the strip: arrows move, Shift+arrows extend, Enter
     * opens the popover, Escape clears. A calendar somebody can only use with
     * a mouse is a calendar half this company cannot use at all.
     */
    onDayKey(ev, day) {
        const step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7,
                       ArrowDown: 7 }[ev.key];
        if (step) {
            ev.preventDefault();
            const index = this.days.findIndex((d) => d.date === day.date);
            const next = this.days[Math.min(Math.max(index + step, 0),
                                            this.days.length - 1)];
            if (!next) { return; }
            if (ev.shiftKey && this.state.anchor) {
                this._span(this.state.anchor, next.date);
            } else {
                this.state.anchor = next.date;
                this._span(next.date, next.date);
            }
            const el = document.querySelector(
                `[data-wsg-day="${next.date}"]`);
            if (el) { el.focus(); }
            return;
        }
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            if (this.state.draft.date_from) { this.openPopover(); }
        }
    }

    onKey(ev) {
        // Never `preventDefault` on Escape — the platform still gets its turn.
        if (ev.key !== "Escape") { return; }
        if (this.state.makePlan) { this.state.makePlan = null; return; }
        if (this.state.popover) { this.closePopover(); }
    }

    // ============================================================== the popover
    openPopover() {
        const existing = this.segments.find(
            (s) => s.date_from === this.state.draft.date_from
                && s.date_to === this.state.draft.date_to);
        if (existing) {
            this.state.draft = {
                id: existing.id,
                host_company_id: existing.host_company_id,
                host_employee_id: existing.host_employee_id,
                division_id: existing.division_id,
                config_id: existing.config_id,
                kind: existing.kind,
                pay_policy: existing.pay_policy,
                date_from: existing.date_from,
                date_to: existing.date_to,
                note: existing.note,
            };
        } else if (!this.state.draft.host_company_id) {
            const first = this.hostChoices[0];
            this.state.draft.host_company_id = first ? first.id : 0;
        }
        // The employment in that entity, if the person already has one.
        // Defaulting the ENTITY without also defaulting the employment is how
        // a preview draws one payslip where it should draw two: the entity is
        // picked, the employment is still zero, and nothing says so.
        if (!this.state.draft.host_employee_id && this.hostEmployment) {
            this.state.draft.host_employee_id = this.hostEmployment.id;
        }
        this.state.dialogError = "";
        this.state.preview = null;
        this.state.popover = true;
    }

    closePopover() {
        this.state.popover = false;
        this.state.preview = null;
        this.state.makePlan = null;
        this.state.draft = { ...BLANK_DRAFT };
        this.state.anchor = "";
    }

    setDraft(field, value) {
        const numbers = ["host_company_id", "host_employee_id", "division_id",
                         "config_id"];
        this.state.draft[field] = numbers.includes(field)
            ? Number(value || 0) : value;
        if (field === "host_company_id") {
            const found = this.hostEmployment;
            this.state.draft.host_employee_id = found ? found.id : 0;
            this.state.draft.config_id = 0;
        }
        this.state.preview = null;
    }

    setDraftPolicy(key) {
        this.state.draft.pay_policy = key;
        this.state.preview = null;
    }

    get draftPayload() {
        const home = this.homeEmployment;
        return {
            id: this.state.draft.id || 0,
            person_id: this.person ? this.person.id : 0,
            home_employee_id: home ? home.id : 0,
            host_company_id: this.state.draft.host_company_id,
            host_employee_id: this.state.draft.host_employee_id,
            division_id: this.state.draft.division_id,
            config_id: this.state.draft.config_id,
            date_from: this.state.draft.date_from,
            date_to: this.state.draft.date_to,
            kind: this.state.draft.kind,
            pay_policy: this.state.draft.pay_policy,
            note: this.state.draft.note,
        };
    }

    /**
     * Both payslips, computed for real and thrown away.
     *
     * "Twenty days here, ten days there" is a claim about money, and the only
     * thing that can settle it is the payroll engine. So the preview runs the
     * real scheme inside a savepoint the server rolls back — the numbers are
     * the ones the pay run will produce, and nothing survives having asked.
     */
    async runPreview() {
        this.state.previewing = true;
        this.state.dialogError = "";
        try {
            this.state.preview = await this.orm.call(
                MODEL, "preview", [this.draftPayload]);
        } catch (e) {
            this.state.dialogError = this._msg(
                e, _t("Those payslips could not be worked out."));
            this.state.preview = null;
        } finally {
            this.state.previewing = false;
        }
    }

    async confirmSegment() {
        const done = await this._write("save_segment", [this.draftPayload],
                                       _t("Saved."));
        if (done) { this.closePopover(); }
    }

    async removeSegment(segment) {
        await this._write("remove_segment", [segment.id],
                          _t("Those days are back to a normal month."));
    }

    async setSegmentPolicy(segment, key) {
        await this._write("set_segment_policy", [segment.id, key]);
    }

    // ================================================= the host employment
    /**
     * What "Create the employment" would create, shown BEFORE it happens.
     *
     * Nothing about somebody's employment record is created silently by this
     * product. The panel exists so the reader recognises what they are about
     * to make — the entity, the money, and that nothing is paid until a pay
     * run includes it.
     */
    async openMakePlan() {
        try {
            this.state.makePlan = await this.orm.call(
                MODEL, "host_employment_plan", [{
                    person_id: this.person ? this.person.id : 0,
                    host_company_id: this.state.draft.host_company_id,
                }]);
            this.state.makePlan.wage = this.state.makePlan.home_wage || 0;
        } catch (e) {
            this.state.dialogError = this._msg(
                e, _t("That employment could not be worked out."));
        }
    }

    setMakeWage(value) {
        if (!this.state.makePlan) { return; }
        this.state.makePlan.wage = Number(
            String(value || "").replace(/[^0-9.-]/g, "")) || 0;
    }

    async createHostEmployment() {
        if (!this.state.makePlan) { return; }
        this.state.busy = true;
        try {
            const made = await this.orm.call(MODEL, "create_host_employment", [{
                person_id: this.state.makePlan.person_id,
                host_company_id: this.state.makePlan.company_id,
                wage: this.state.makePlan.wage || 0,
            }]);
            this.state.makePlan = null;
            await this.load();
            this.state.draft.host_employee_id = made.employee_id || 0;
            this.notif.add(
                _t("%(name)s now has an employment in %(company)s.",
                   { name: this.person ? this.person.name : "",
                     company: this.hostCompany ? this.hostCompany.name : "" }),
                { type: "success" });
        } catch (e) {
            this.state.dialogError = this._msg(
                e, _t("That employment could not be created."));
        } finally {
            this.state.busy = false;
        }
    }

    // ================================================== "Same person?"
    setFocus(focus) {
        this.state.focus = focus;
        this.env.config.setDisplayName(
            focus === "merge" ? _t("Same person?") : _t("Where people work"));
        if (focus === "merge" && !this.state.review) { this.loadReview(); }
    }

    async mergePair(suggestion) {
        this.state.reviewing = true;
        try {
            const answer = await this.orm.call(
                MODEL, "merge_people", [suggestion.person_ids]);
            this.state.review = answer.review || this.state.review;
            this.notif.add(_t("Joined. They are one person from now on."),
                           { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("Those two could not be joined.")),
                           { type: "danger", sticky: true });
        } finally {
            this.state.reviewing = false;
        }
    }

    dismissPair(suggestion) {
        // Nothing is written: saying "not the same" is saying "leave these
        // two records alone", and the records are already alone. The row goes
        // for this reading so the queue can be worked through.
        this.state.review.suggestions = this.suggestions.filter(
            (s) => s !== suggestion);
    }

    async mergeAllStrong() {
        this.state.reviewing = true;
        try {
            const answer = await this.orm.call(MODEL, "merge_all_strong", []);
            this.state.review = answer.review || this.state.review;
            this.notif.add(
                _t("%(count)s joined.", { count: answer.merged || 0 }),
                { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("Those records could not be joined.")),
                           { type: "danger", sticky: true });
        } finally {
            this.state.reviewing = false;
        }
    }

    // ==================================================== the month picker
    async stepMonth(delta) {
        const current = this.state.month || "";
        if (!current) { return; }
        const parts = current.split("-").map(Number);
        const when = new Date(Date.UTC(parts[0], parts[1] - 1 + delta, 1));
        const month = when.toISOString().slice(0, 10);
        this.state.loaded = false;
        await this.load(this.person ? this.person.id : 0, month);
    }

    openPerson(personId) {
        this.state.loaded = false;
        this.state.focus = "days";
        this.load(personId);
    }

    /**
     * The way out of "there is only one entity here".
     *
     * A screen that can only say no has to say where yes lives. On a database
     * with one company a split month is not a thing that can exist yet, and
     * the thing to do about it is on the Group screen.
     */
    openGroupScreen() {
        this.action.doAction("pb_group.action_pb_group",
                             { clearBreadcrumbs: false })
            .catch(() => this.notif.add(
                _t("The Group screen is not switched on for this database."),
                { type: "warning" }));
    }

    openTransfers() {
        this.action.doAction("pb_workseg.action_pb_cost_transfers",
                             { clearBreadcrumbs: false });
    }

    // ------------------------------------------------------------- format
    money(row) {
        if (!row) { return ""; }
        return row.net_label || "";
    }
}

registry.category("actions").add("pb_assignments", PbAssignmentsScreen);
