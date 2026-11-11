/** @odoo-module **/
/**
 * People › Updates — update many people at once from one spreadsheet.
 *
 * One OWL root, one `view` at a time, in the order a person thinks:
 *
 *     home → start → match → review → apply → done
 *
 *   home    the hero, two ways in (download a ready-to-fill sheet, or upload
 *           your own file) and Past updates with Undo.
 *   start   pick topics and download the sheet; or drop a filled-in file.
 *   match   one row per file column: where it goes, how that was decided
 *           (a Payobook sheet, remembered, by name, a careful guess). Skipped
 *           when every column came from a Payobook sheet.
 *   review  the grid (updates_review.js) — every change before → after.
 *   apply   name it, three honest counts, apply.
 *   done    what happened, in a sentence, and Undo.
 *
 * Nothing here decides what is written. The server facade is
 * `pb.updates.desk`, which hands every value to the Records Desk
 * (`pb.records.desk`) — the same evaluation, audit, approval and undo the
 * Records screen uses.
 *
 * Mounted two ways and the same in both: as the People hub's Updates lens
 * (registered at the bottom of this file, after Records) and as its own client
 * action `pb_updates_desk`.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PEOPLE_LENSES } from "@pb_people_hub/js/people_hub";
import { grouped } from "@pb_records/js/records_review";
import {
    UpdReview, icon, plural, reviewCounts, changesToSend, PAGE_ROWS,
    dayLabel, rowStart, startBuckets, oneoffTotals, moneyLabel,
    LANE_ICON, laneLabel,
} from "@pb_updates/js/updates_review";

const MODEL = "pb.updates.desk";
const STEPS = ["start", "match", "review", "apply"];
/** UPDATES P2c — the "Goes to" target of a start-date column. */
const WHEN = "when:start";
/** A start date can be at most this many days back or ahead. */
const REACH_DAYS = 366;
/** At most this many different start dates in one update. */
const MAX_DATES = 6;
/** The default name: "November 2026 update", the month in the reader's language. */
export function defaultName() {
    return _t("%s update", luxon.DateTime.now().toFormat("LLLL yyyy"));
}

/** UPDATES P2d — "November 2026" from `YYYY-MM-01`. */
export function monthLabel(iso) {
    if (!iso) { return ""; }
    const day = luxon.DateTime.fromISO(iso);
    return day.isValid ? day.toFormat("LLLL yyyy") : iso;
}

/** "11 Nov 2026, 14:05" in the reader's own time zone. */
export function whenLabel(utc) {
    if (!utc) { return ""; }
    try {
        return deserializeDateTime(utc).toFormat("d LLL yyyy, HH:mm");
    } catch {
        return utc;
    }
}

/** base64 to a saved file without leaving the page (the desk's own way). */
function saveFile(res) {
    const binary = window.atob(res.file_b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) { bytes[i] = binary.charCodeAt(i); }
    const url = URL.createObjectURL(new Blob([bytes], { type: res.mimetype }));
    const link = document.createElement("a");
    link.href = url;
    link.download = res.filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** "3 values were skipped: those pay items are not in the person's pay scheme." */
export function offSchemeLine(n) {
    return plural(n,
        _t("1 value was skipped because that pay item is not in the person's pay scheme."),
        _t("%s values were skipped because those pay items are not in the person's pay scheme."));
}

export class PbUpdatesDesk extends Component {
    static template = "pb_updates.PbUpdatesDesk";
    static components = { UpdReview };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.dialog = useService("dialog");
        this.state = useState({
            view: "home",
            loading: true,
            error: "",
            home: { can_write: false, can_export: false, people_count: 0, topics: [], history: [], coming_up: [], today: "",
                    oneoff: { available: false, items: 0, months: [], this_month: "" },
                    waiting: { months: [], clashes: [], can_choose: false } },
            // UPDATES P2d — which kind of sheet: lasting changes, or one-off
            // pay items for one pay month.
            kind: "lasting",
            month: "",
            monthNote: "",
            openMonth: "",
            choosing: "",
            historyAll: false,
            historyTotal: 0,
            picked: {},
            download: { busy: false, msg: "", tone: "" },
            file: { name: "", b64: "", busy: false, rows: 0, phase: "", error: "", over: 0 },
            match: null,
            matchError: "",
            rv: null,
            apply: { name: "", busy: false, error: "", touched: false },
            // UPDATES P2c — when the changes start: today, or a picked date
            // (the default for rows without their own); what waits for a
            // future date; and the "already paid" count for a past one.
            when: { mode: "today", date: "", scope: "pay", paid: 0, paidKey: "" },
            done: null,
            undoing: 0,
            starting: 0,
            // UPDATES P3a — what each lane of this file will do (Apply step).
            lanes: [],
            lanesBusy: false,
            switching: false,
        });
        onWillStart(() => this.loadHome());
    }

    icon(name, size) { return icon(name, size); }
    grouped(n) { return grouped(n); }

    // =================================================================
    //  Home
    // =================================================================
    async loadHome() {
        try {
            const home = await this.orm.call(MODEL, "get_home", []);
            this.state.home = home;
            this.state.historyTotal = home.history.length;
            const picked = {};
            for (const t of home.topics) {
                // Bank details stay out unless asked for: a sheet that is
                // emailed around should not carry account numbers by default.
                picked[t.key] = t.key !== "bank";
            }
            this.state.picked = picked;
            await this.loadHistory();
        } catch (e) {
            this.state.error = e.data?.message || e.message?.data?.message || _t("Updates could not be opened.");
        } finally {
            this.state.loading = false;
        }
    }

    async loadHistory() {
        const [res, coming, waiting] = await Promise.all([
            this.orm.call(MODEL, "get_history", [], { limit: this.state.historyAll ? 200 : 8 }),
            this.orm.call(MODEL, "get_coming_up", []),
            this.orm.call(MODEL, "get_waiting", []),
        ]);
        this.state.home.history = res.batches || [];
        this.state.historyTotal = res.total || 0;
        this.state.home.coming_up = coming.items || [];
        this.state.home.waiting = waiting || { months: [], clashes: [] };
    }

    async showAllHistory() {
        this.state.historyAll = true;
        await this.loadHistory();
    }

    get canWrite() { return !!this.state.home.can_write; }
    get canExport() { return !!this.state.home.can_export; }

    get heroBody() {
        return _t("Change job details, contracts, bank details and ongoing pay items for the whole team from one spreadsheet, any day of the month, and add one-off pay items like a bonus to a pay month. You see every change before it happens.");
    }

    get noWriteNote() {
        return _t("You can check a file and see exactly what it would change. Applying it needs the HR or Payroll Officer role.");
    }

    historyTone(h) {
        return { applied: "ok", pending: "info", undone: "muted", rejected: "err", returned: "warn",
                 scheduled: "pri", mixed: "pri", cancelled: "muted", blocked: "err",
                 waiting_run: "pri", in_run: "info", paid: "ok", clash: "warn",
                 replaced: "muted" }[h.state] || "muted";
    }

    historyIcon(h) {
        if (h.kind === "oneoff") {
            return { pending: "clock", blocked: "alert", clash: "scale", cancelled: "ban",
                     rejected: "xCircle", returned: "rotate" }[h.state] || "coins";
        }
        return { applied: "check", pending: "clock", undone: "undo", rejected: "xCircle", returned: "rotate",
                 scheduled: "calendarClock", mixed: "calendarClock", cancelled: "ban",
                 blocked: "alert" }[h.state] || "info";
    }

    /** The chip's words — the new states in the reader's own date form. */
    historyLabel(h) {
        if (h.state === "scheduled" && h.state_date) { return _t("Scheduled for %s", dayLabel(h.state_date)); }
        if (h.state === "mixed" && h.state_date) { return _t("Part applied, part scheduled for %s", dayLabel(h.state_date)); }
        if (h.state === "cancelled") { return _t("Cancelled"); }
        return h.state_label;
    }

    // ------------------------------------------------------------ Coming up
    get comingUp() { return this.state.home.coming_up || []; }

    comingLine(c) {
        const bits = [
            _t("%(values)s for %(people)s", {
                values: plural(c.values, _t("1 value"), _t("%s values")),
                people: plural(c.people, _t("1 person"), _t("%s people")) }),
        ];
        if (c.user) { bits.push(_t("by %s", c.user)); }
        return bits.join(" · ");
    }

    comingDay(c) {
        const day = luxon.DateTime.fromISO(c.date);
        return day.isValid ? { d: day.toFormat("d"), m: day.toFormat("LLL"), y: day.toFormat("yyyy") } : { d: "", m: "", y: "" };
    }

    comingWhen(c) {
        const days = this.daysFromToday(c.date);
        if (days <= 0) { return _t("Starts within the hour"); }
        if (days === 1) { return _t("Starts tomorrow"); }
        return _t("Starts in %s days", grouped(days));
    }

    daysFromToday(iso) {
        const today = luxon.DateTime.fromISO(this.state.home.today || luxon.DateTime.now().toISODate());
        const day = luxon.DateTime.fromISO(iso);
        return day.isValid && today.isValid ? Math.round(day.diff(today, "days").days) : 0;
    }

    startNow(c) {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Start “%s” now?", c.name),
            body: _t("%(values)s for %(people)s: written today instead of on %(date)s, and recorded as starting today. You can undo it afterwards from Past updates.", {
                values: plural(c.values, _t("1 value"), _t("%s values")),
                people: plural(c.people, _t("1 person"), _t("%s people")),
                date: dayLabel(c.date) }),
            confirmLabel: _t("Start now"),
            cancelLabel: _t("Not yet"),
            confirm: async () => {
                this.state.starting = c.apply_id;
                try {
                    const res = await this.orm.call(MODEL, "start_now", [], { apply_id: c.apply_id });
                    if (res.ok) {
                        this.notif.add(_t("“%(name)s” has started. %(back)s", {
                            name: c.name,
                            back: plural(res.written, _t("1 value was changed."), _t("%s values were changed.")) }),
                            { type: "success" });
                    } else {
                        this.notif.add(res.msg, { type: "warning" });
                    }
                    await this.loadHistory();
                } catch (e) {
                    this.notif.add(e.data?.message || _t("The update could not be started. Nothing has changed."), { type: "danger" });
                } finally {
                    this.state.starting = 0;
                }
            },
            cancel: () => {},
        });
    }

    /** Cancel what has not been written: one scheduled part, or the whole
     *  waiting part of a named update. */
    cancelParts({ applyId = 0, batchId = 0, name = "", values = 0, date = "", pending = false, blocked = false }) {
        const what = plural(values, _t("1 value"), _t("%s values"));
        const body = blocked
            ? _t("It was approved but could not be made, so nothing has been changed. Once cancelled, the %s in it are never written.", what)
            : pending
            ? _t("The approval request is withdrawn and the %s waiting in it are never written. Nothing has been changed, so nothing needs putting back.", what)
            : _t("The %(what)s scheduled for %(date)s are never written. Nothing has been changed yet, so nothing needs putting back. To do it later, upload the file again.", {
                what, date: dayLabel(date) });
        this.dialog.add(ConfirmationDialog, {
            title: _t("Cancel “%s”?", name),
            body,
            confirmLabel: blocked ? _t("Cancel it") : pending ? _t("Cancel and withdraw") : _t("Cancel the scheduled change"),
            cancelLabel: _t("Keep it"),
            confirm: async () => {
                try {
                    const res = await this.orm.call(MODEL, "cancel", [], { batch_id: batchId, apply_id: applyId });
                    this.notif.add(res.ok
                        ? _t("“%(name)s”: %(what)s cancelled before anything was changed.", {
                            name, what: plural(res.values, _t("1 value"), _t("%s values")) })
                        : res.msg, { type: res.ok ? "success" : "warning" });
                    await this.loadHistory();
                } catch (e) {
                    this.notif.add(e.data?.message || _t("The update could not be cancelled. Nothing has changed."), { type: "danger" });
                }
            },
            cancel: () => {},
        });
    }

    cancelComing(c) {
        this.cancelParts({ applyId: c.apply_id, name: c.name, values: c.values, date: c.date });
    }

    cancelBatch(h) {
        if (h.kind === "oneoff") { return this.cancelOneoff(h); }
        const pending = h.state === "pending";
        const blocked = h.state === "blocked";
        const values = h.open_values || (h.scheduled || []).reduce((n, s) => n + s.values, 0);
        const date = (h.scheduled || [])[0] ? h.scheduled[0].date : "";
        this.cancelParts({ batchId: h.id, name: h.name, values, date, pending, blocked });
    }

    cancelLabel(h) {
        if (h.kind === "oneoff") { return _t("Cancel"); }
        if (h.state === "blocked") { return _t("Cancel it"); }
        return h.state === "pending" ? _t("Withdraw") : _t("Cancel the scheduled part");
    }

    historyLine(h) {
        const bits = [whenLabel(h.date)];
        if (h.kind === "oneoff") {
            if (h.month_label) { bits.push(h.month_label); }
            bits.push(_t("%(amounts)s for %(people)s", {
                amounts: plural(h.values, _t("1 one-off amount"), _t("%s one-off amounts")),
                people: plural(h.people, _t("1 person"), _t("%s people")) }));
            if (h.user) { bits.push(_t("by %s", h.user)); }
            return bits.filter(Boolean).join(" · ");
        }
        if (h.values) {
            bits.push(_t("%(changes)s for %(people)s", {
                changes: plural(h.values, _t("1 change"), _t("%s changes")),
                people: plural(h.people, _t("1 person"), _t("%s people")) }));
        }
        if (h.user) { bits.push(_t("by %s", h.user)); }
        return bits.filter(Boolean).join(" · ");
    }

    historyNote(h) {
        // UPDATES P3a — an update split into lanes says it lane by lane.
        if (h.lanes && h.lanes.length > 1 && ["pending", "mixed", "scheduled", "blocked"].includes(h.state)) {
            return "";
        }
        if (h.state === "blocked") {
            return h.state_reason || _t("Approved, but it could not be made.");
        }
        if (h.kind === "oneoff") {
            const bits = [];
            if (h.state === "pending") {
                bits.push(h.with_whom ? _t("Waiting for approval with %s.", h.with_whom) : _t("Waiting for approval."));
            } else if (h.state_note) {
                bits.push(h.state_note);
            }
            if (h.values_refused) { bits.push(plural(h.values_refused, _t("1 value from the file was left out."), _t("%s values from the file were left out."))); }
            if (h.values_off_scheme) { bits.push(offSchemeLine(h.values_off_scheme)); }
            if (h.cancelled_values && h.state !== "cancelled") {
                bits.push(plural(h.cancelled_values, _t("1 amount was cancelled."), _t("%s amounts were cancelled.")));
            }
            return bits.join(" ");
        }
        if (h.state === "pending") {
            return h.with_whom ? _t("Waiting for approval with %s.", h.with_whom) : _t("Waiting for approval.");
        }
        if (h.state === "scheduled" || h.state === "mixed") {
            const bits = [];
            if (h.state === "mixed" && h.applied_values) {
                bits.push(plural(h.applied_values, _t("1 value was changed when it was applied."), _t("%s values were changed when it was applied.")));
            }
            for (const s of h.scheduled || []) {
                bits.push(s.values === 1
                    ? _t("1 value starts on %s.", dayLabel(s.date))
                    : _t("%(n)s values start on %(date)s.", { n: grouped(s.values), date: dayLabel(s.date) }));
            }
            return bits.join(" ");
        }
        if (h.state === "cancelled") {
            return h.cancelled_by
                ? _t("Cancelled on %(when)s by %(who)s. Nothing was changed.", { when: whenLabel(h.cancelled_date), who: h.cancelled_by })
                : _t("Cancelled. Nothing was changed.");
        }
        if (h.state === "returned" && h.state_reason) {
            return h.state_reason;
        }
        if (h.state === "undone") {
            return h.undone_by
                ? _t("Put back on %(when)s by %(who)s.", { when: whenLabel(h.undone_date), who: h.undone_by })
                : _t("Put back on %s.", whenLabel(h.undone_date));
        }
        const bits = [];
        for (const r of h.recorded || []) {
            bits.push(r.values === 1
                ? _t("1 value is recorded as starting %s.", dayLabel(r.date))
                : _t("%(n)s values are recorded as starting %(date)s.", { n: grouped(r.values), date: dayLabel(r.date) }));
        }
        const left = (h.values_refused || 0);
        if (left) { bits.push(plural(left, _t("1 value from the file was left out."), _t("%s values from the file were left out."))); }
        if (h.values_off_scheme) { bits.push(offSchemeLine(h.values_off_scheme)); }
        if (h.started_early) {
            bits.push(plural(h.started_early, _t("1 value was started early, before its date."), _t("%s values were started early, before their date.")));
        }
        if (h.cancelled_values) {
            bits.push(plural(h.cancelled_values, _t("1 value was cancelled before it was changed."), _t("%s values were cancelled before they were changed.")));
        }
        return bits.join(" ");
    }

    fileUrl(h) { return `/web/content/${h.file_id}?download=true`; }

    get historyMoreLine() {
        const shown = this.state.home.history.length;
        if (this.state.historyAll || this.state.historyTotal <= shown) { return ""; }
        return _t("Showing the latest %(shown)s of %(total)s.", {
            shown: grouped(shown), total: grouped(this.state.historyTotal) });
    }

    // =================================================================
    //  Navigation
    // =================================================================
    go(view) {
        this.state.view = view;
        const el = document.querySelector(".pbu-root");
        if (el) { el.scrollTop = 0; }
    }

    newUpdate(kind = "lasting") {
        this.resetFlow();
        this.setKind(kind);
        this.go("start");
    }

    // =================================================================
    //  UPDATES P2d — the kind of sheet and its pay month
    // =================================================================
    get oneoffInfo() { return this.state.home.oneoff || { available: false, months: [] }; }
    get isOneoff() { return this.state.kind === "oneoff"; }

    setKind(kind) {
        if (kind === "oneoff" && !this.oneoffInfo.available) { return; }
        this.state.kind = kind === "oneoff" ? "oneoff" : "lasting";
        if (this.isOneoff && !this.state.month) {
            this.state.month = this.oneoffInfo.this_month || "";
        }
        Object.assign(this.state.download, { busy: false, msg: "", tone: "" });
        this.state.file.error = "";
    }

    onMonth(ev) {
        this.state.month = ev.target.value || "";
        this.state.monthNote = "";
        Object.assign(this.state.download, { busy: false, msg: "", tone: "" });
    }

    get monthLabel() { return monthLabel(this.state.month); }

    get oneoffMatchLead() { return _t("One-off pay for %s.", this.monthLabel); }
    get oneoffEachLine() { return _t("Each paid once, in %s.", this.monthLabel); }
    get monthCardTitle() { return _t("Paid in the %s pay run", this.monthLabel); }
    get monthCardBody() {
        return _t("Each amount is paid once, by the first pay run of %s for the person's pay scheme. If the pay data file of that run has a different amount, the run stops and asks which one to pay.", this.monthLabel);
    }
    get clashTitle() {
        const n = this.clashes.length;
        return n === 1 ? _t("A pay run found two amounts for one pay item")
            : _t("%s pay items have two amounts", n);
    }
    clashWhere(c) { return _t("%(month)s · pay run %(run)s", { month: c.month, run: c.run }); }

    /** "Paid once, in the November 2026 pay run of each person's pay scheme." */
    get monthLine() {
        return _t("Paid once, in the %s pay run of each person's pay scheme. Amounts already waiting for that month are in the sheet.", this.monthLabel);
    }

    // ------------------------------------------------------- Waiting for a pay run
    get waiting() { return this.state.home.waiting || { months: [], clashes: [] }; }
    get waitingMonths() { return this.waiting.months || []; }
    get clashes() { return this.waiting.clashes || []; }

    waitingLine(m) {
        const bits = [plural(m.people, _t("1 person"), _t("%s people")),
                      plural(m.items, _t("1 one-off amount"), _t("%s one-off amounts"))];
        return bits.join(" · ");
    }

    waitingMoney(m) {
        const bits = [];
        if (m.earn_label) { bits.push(_t("%s added to pay", m.earn_label)); }
        if (m.take_label) { bits.push(_t("%s taken from pay", m.take_label)); }
        return bits.join(" · ");
    }

    waitingChips(m) {
        const out = [];
        if (m.pending) { out.push({ key: "p", tone: "info", label: plural(m.pending, _t("1 waiting for approval"), _t("%s waiting for approval")) }); }
        if (m.in_run) { out.push({ key: "r", tone: "pri", label: plural(m.in_run, _t("1 in a pay run"), _t("%s in a pay run")) }); }
        return out;
    }

    monthDay(m) {
        const day = luxon.DateTime.fromISO(m.month);
        return day.isValid ? { m: day.toFormat("LLL"), y: day.toFormat("yyyy") } : { m: "", y: "" };
    }

    toggleMonth(m) { this.state.openMonth = this.state.openMonth === m.month ? "" : m.month; }

    rowTone(r) {
        return { pending: "info", approved: "pri", reserved: "ok" }[r.state] || "muted";
    }

    cancelOneoff(h) {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Cancel “%s”?", h.name),
            body: _t("Every one-off amount in it that no pay run has taken yet is cancelled and will not be paid. Amounts already in a pay run stay there."),
            confirmLabel: _t("Cancel them"),
            cancelLabel: _t("Keep them"),
            confirm: async () => {
                try {
                    const res = await this.orm.call(MODEL, "cancel", [], { batch_id: h.id });
                    this.notif.add(res.msg, { type: res.ok ? "success" : "warning" });
                    await this.loadHistory();
                } catch (e) {
                    this.notif.add(e.data?.message || _t("The update could not be cancelled. Nothing has changed."), { type: "danger" });
                }
            },
            cancel: () => {},
        });
    }

    async chooseAmount(c, choice) {
        if (this.state.choosing) { return; }
        this.state.choosing = `${c.id}:${choice}`;
        try {
            const res = await this.orm.call("pb.updates.oneoff", "resolve_clash", [], { row_id: c.id, choice });
            this.notif.add(res.msg, { type: res.ok ? "success" : "warning" });
            await this.loadHistory();
        } catch (e) {
            this.notif.add(e.data?.message || _t("The choice could not be saved. Nothing has changed."), { type: "danger" });
        } finally {
            this.state.choosing = "";
        }
    }

    resetFlow() {
        this.state.monthNote = "";
        Object.assign(this.state.file, { name: "", b64: "", busy: false, rows: 0, phase: "", error: "", over: 0 });
        Object.assign(this.state.download, { busy: false, msg: "", tone: "" });
        this.state.match = null;
        this.state.matchError = "";
        this.state.rv = null;
        this.state.done = null;
        Object.assign(this.state.apply, { name: "", busy: false, error: "", touched: false });
        Object.assign(this.state.when, { mode: "today", date: "", scope: "pay", paid: 0, paidKey: "" });
    }

    async close() {
        this.resetFlow();
        this.go("home");
        await this.loadHistory();
    }

    stepState(key) {
        const at = STEPS.indexOf(this.state.view === "done" ? "apply" : this.state.view);
        const me = STEPS.indexOf(key);
        if (key === "match" && this.state.rv && this.state.rv.fromSheet && at > me) { return "skip"; }
        if (me < at || this.state.view === "done") { return "done"; }
        return me === at ? "on" : "";
    }

    get stepLabels() {
        return [
            { key: "start", n: 1, label: _t("Start") },
            { key: "match", n: 2, label: _t("Match columns") },
            { key: "review", n: 3, label: _t("Review changes") },
            { key: "apply", n: 4, label: _t("Apply") },
        ];
    }

    // =================================================================
    //  Start — topics and the sheet
    // =================================================================
    toggleTopic(key) { this.state.picked[key] = !this.state.picked[key]; }

    get pickedTopics() { return this.state.home.topics.filter((t) => this.state.picked[t.key]); }

    get pickedColumns() { return this.pickedTopics.reduce((n, t) => n + t.count, 0); }

    get peopleLine() {
        return _t("Everyone you can see (%s)", grouped(this.state.home.people_count));
    }

    get downloadHint() {
        if (this.isOneoff) {
            if (!this.canExport) {
                return _t("Downloading a sheet needs permission to export employee records. You can still upload a file of your own.");
            }
            return _t("One row per person and one column per one-off pay item of their pay scheme. Type amounts without a minus sign: each item already says whether it adds to pay or takes from pay.");
        }
        if (!this.canExport) {
            return _t("Downloading a sheet needs permission to export employee records. You can still upload a file of your own.");
        }
        if (!this.pickedTopics.length) { return _t("Pick at least one topic above."); }
        return _t("One row per person, %s columns, filled with today's values. Leave a cell as it is, or blank, and nothing changes for it.", grouped(this.pickedColumns));
    }

    topicExamples(t) {
        const rest = t.count - t.examples.length;
        const shown = t.examples.join(", ");
        return rest > 0 ? _t("%(list)s and %(n)s more", { list: shown, n: grouped(rest) }) : shown;
    }

    async downloadSheet() {
        const d = this.state.download;
        if (d.busy || !this.canExport || (!this.isOneoff && !this.pickedTopics.length)) { return; }
        Object.assign(d, { busy: true, msg: "", tone: "" });
        try {
            const res = this.isOneoff
                ? await this.orm.call(MODEL, "download_oneoff_sheet", [], { month: this.state.month })
                : await this.orm.call(MODEL, "download_sheet", [], {
                    topic_keys: this.pickedTopics.map((t) => t.key) });
            if (!res.ok) {
                Object.assign(d, { msg: res.msg, tone: "err" });
                return;
            }
            saveFile(res);
            if (res.truncated) {
                Object.assign(d, { tone: "warn", msg: _t("%(shown)s of %(total)s people are in the sheet. That is the most one file holds, so do the rest in a second update.", {
                    shown: grouped(res.rows), total: grouped(res.total) }) });
            } else {
                Object.assign(d, { tone: "ok", msg: _t("Downloaded “%(file)s” with %(people)s. Change what you need, save it, then drop it back here.", {
                    file: res.filename, people: plural(res.rows, _t("1 person"), _t("%s people")) }) });
            }
        } catch (e) {
            Object.assign(d, { tone: "err", msg: e.data?.message || _t("The sheet could not be built. Nothing has changed.") });
        } finally {
            d.busy = false;
        }
    }

    // =================================================================
    //  Start — the file
    // =================================================================
    onDragEnter(ev) { ev.preventDefault(); this.state.file.over += 1; }
    onDragOver(ev) { ev.preventDefault(); }
    onDragLeave(ev) { ev.preventDefault(); this.state.file.over = Math.max(0, this.state.file.over - 1); }
    onDrop(ev) {
        ev.preventDefault();
        this.state.file.over = 0;
        const file = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
        if (file) { this.takeFile(file); }
    }
    onPick(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (file) { this.takeFile(file); }
        ev.target.value = "";
    }

    get busyLine() {
        const f = this.state.file;
        if (f.phase === "review") {
            return f.rows
                ? plural(f.rows, _t("Checking 1 row against your people…"), _t("Checking %s rows against your people…"))
                : _t("Checking the file against your people…");
        }
        return f.rows
            ? plural(f.rows, _t("Reading 1 row…"), _t("Reading %s rows…"))
            : _t("Reading “%s”…", f.name || _t("the file"));
    }

    readAsBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onerror = () => reject(new Error("read"));
            reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
            reader.readAsDataURL(file);
        });
    }

    async takeFile(file) {
        const f = this.state.file;
        if (f.busy) { return; }
        Object.assign(f, { name: file.name, b64: "", busy: true, rows: 0, phase: "read", error: "" });
        let b64 = "";
        try {
            b64 = await this.readAsBase64(file);
        } catch {
            Object.assign(f, { busy: false, error: _t("That file could not be read from this computer. Save it again and drop it back.") });
            return;
        }
        f.b64 = b64;
        try {
            // A cheap count first, so the wait can say how big it is.
            const probe = await this.orm.call("pb.records.desk", "import_probe", [], {
                file_b64: b64, filename: file.name }).catch(() => null);
            if (probe && probe.ok) { f.rows = probe.rows || 0; }
            const res = await this.orm.call(MODEL, "read_columns", [], this.kindArgs({
                file_b64: b64, filename: file.name }));
            if (!res.ok) {
                Object.assign(f, { busy: false, error: res.msg });
                return;
            }
            f.rows = res.rows;
            if (this.isOneoff && res.sheet_month && res.sheet_month !== this.state.month) {
                // A downloaded sheet says which month it is for: that month wins.
                this.state.monthNote = _t("This sheet was made for %(sheet)s, so it is used for %(sheet)s, not %(picked)s.", {
                    sheet: monthLabel(res.sheet_month), picked: monthLabel(this.state.month) });
                this.state.month = res.sheet_month;
            }
            this.state.match = this.buildMatch(res);
            if (res.from_sheet) {
                // A Payobook sheet: every column already knows where it goes.
                await this.toReview(true);
            } else {
                f.busy = false;
                this.state.matchError = "";
                this.go("match");
            }
        } catch (e) {
            Object.assign(f, { busy: false, error: e.data?.message || _t("The file could not be read. Nothing has changed.") });
        }
    }

    /** The extra arguments a one-off sheet sends with every call. */
    kindArgs(args) {
        return this.isOneoff ? Object.assign(args, { kind: "oneoff", month: this.state.month }) : args;
    }

    // =================================================================
    //  Match columns
    // =================================================================
    buildMatch(res) {
        return {
            filename: res.filename,
            rows: res.rows,
            truncated: res.truncated,
            layoutKnown: res.layout_known,
            fromSheet: res.from_sheet,
            fields: res.fields || [],
            schemes: res.schemes || [],
            noScheme: res.no_scheme || 0,
            columns: (res.columns || []).map((c) => ({
                idx: c.idx, head: c.head, samples: c.samples || [],
                target: c.target || "", how: c.how || "" })),
        };
    }

    get identityOptions() {
        return [
            { value: "identity:code", label: _t("Employee code") },
            { value: "identity:name", label: _t("Employee name") },
            { value: "identity:email", label: _t("Work email") },
        ];
    }

    /** UPDATES P2c — the start-date destination, first in "Goes to". */
    get whenOption() { return { value: WHEN, label: _t("Start date for this row") }; }

    get fieldLabels() {
        const out = {};
        out[WHEN] = this.whenOption.label;
        for (const o of this.identityOptions) { out[o.value] = o.label; }
        for (const t of (this.state.match ? this.state.match.fields : [])) {
            for (const f of t.fields) { out[f.id] = f.label; }
        }
        return out;
    }

    /**
     * The "Goes to" list (UPDATES P2b). Person, contract and bank fields keep
     * their topic groups. Pay items are grouped by pay scheme: first the
     * schemes the people in this file are paid under (most people first), then
     * the pay items several schemes share, then — under "Other pay schemes" —
     * the schemes nobody in this file is paid under, and last the pay items no
     * scheme has that are kept on contracts.
     */
    get goesTo() {
        const m = this.state.match;
        if (!m) { return []; }
        const out = [];
        const tag = (f) => (f.role
            ? `${f.label} · ${f.role === "deduction" ? _t("takes from pay") : _t("adds to pay")}`
            : f.label);
        for (const t of m.fields) {
            if (t.key !== "component" && t.key !== "oneoff") {
                out.push({ key: t.key, label: t.label, options: t.fields.map((f) => ({ id: f.id, label: f.label })) });
                continue;
            }
            const present = new Map((m.schemes || []).map((s, i) => [s.id, { ...s, order: i }]));
            const single = new Map();
            const several = [];
            const kept = [];
            for (const f of t.fields) {
                const schemes = f.schemes || [];
                if (!schemes.length) { kept.push({ id: f.id, label: tag(f) }); continue; }
                if (schemes.length > 1) {
                    const names = schemes.map((s) => s.name);
                    const shown = names.length > 3
                        ? _t("%(list)s and %(n)s more", { list: names.slice(0, 3).join(", "), n: names.length - 3 })
                        : names.join(", ");
                    several.push({ id: f.id, label: `${tag(f)} · ${shown}` });
                    continue;
                }
                const s = schemes[0];
                if (!single.has(s.id)) { single.set(s.id, { scheme: s, options: [] }); }
                single.get(s.id).options.push({ id: f.id, label: tag(f) });
            }
            const groups = [...single.values()];
            const inFile = groups.filter((g) => present.has(g.scheme.id))
                .sort((a, b) => present.get(a.scheme.id).order - present.get(b.scheme.id).order);
            const others = groups.filter((g) => !present.has(g.scheme.id))
                .sort((a, b) => a.scheme.name.localeCompare(b.scheme.name));
            for (const g of inFile) {
                out.push({ key: `s${g.scheme.id}`, label: _t("%(scheme)s · %(people)s in this file", {
                    scheme: g.scheme.name, people: plural(present.get(g.scheme.id).count, _t("1 person"), _t("%s people")) }),
                    options: g.options });
            }
            if (several.length) {
                out.push({ key: "several", label: _t("Used by several pay schemes"), options: several });
            }
            if (others.length) {
                out.push({ key: "others", label: _t("── Other pay schemes ──"), options: [], divider: true });
                for (const g of others) {
                    out.push({ key: `s${g.scheme.id}`, label: g.scheme.name, options: g.options });
                }
            }
            if (kept.length) {
                out.push({ key: "kept", label: _t("Kept on contracts only"), options: kept });
            }
        }
        return out;
    }

    /** The quiet line and chips under the "Match your columns" heading. */
    get matchSchemes() {
        const m = this.state.match;
        if (!m || !m.fields.some((t) => (t.key === "component" || t.key === "oneoff") && t.fields.length)) { return null; }
        const chips = (m.schemes || []).map((s) => ({ key: `s${s.id}`, label: s.name, count: s.count, tone: "pri" }));
        if (m.noScheme) {
            chips.push({ key: "none", label: _t("No pay scheme yet"), count: m.noScheme, tone: "warn" });
        }
        return { chips };
    }

    get fieldGroups() {
        const out = {};
        for (const t of (this.state.match ? this.state.match.fields : [])) {
            for (const f of t.fields) { out[f.id] = t.key; }
        }
        return out;
    }

    setTarget(col, value) {
        const wasIdentity = (col.target || "").startsWith("identity:");
        col.target = value;
        col.how = value && value !== "ignore" ? "you" : "";
        this.state.matchError = "";
        if (wasIdentity || (value || "").startsWith("identity:")) { this.refreshSchemes(); }
    }

    /** The pay schemes of the people this file finds, counted again once the
     *  column that finds the person has been chosen by hand. Quiet: a failure
     *  only leaves the counts as they were. */
    async refreshSchemes() {
        const m = this.state.match;
        if (!m || !this.matchSchemes) { return; }
        const seq = (this._schemeSeq = (this._schemeSeq || 0) + 1);
        const { identity } = this.matchColumns();
        try {
            const res = this.isOneoff
                ? await this.orm.silent.call(MODEL, "oneoff_file_schemes", [], {
                    file_b64: this.state.file.b64, filename: this.state.file.name, identity,
                    month: this.state.month })
                : await this.orm.silent.call(MODEL, "file_schemes", [], {
                    file_b64: this.state.file.b64, filename: this.state.file.name, identity });
            if (seq !== this._schemeSeq || !res.ok || this.state.match !== m) { return; }
            m.schemes = res.schemes || [];
            m.noScheme = res.no_scheme || 0;
        } catch {
            // the counts are a guide, never a gate
        }
    }

    confirmGuess(col) { col.how = "confirmed"; }

    /** The first column wins a target; a later one pointing at it is a duplicate. */
    duplicateOf(col) {
        if (!col.target || col.target === "ignore") { return null; }
        return this.state.match.columns.find((c) => c.idx < col.idx && c.target === col.target) || null;
    }

    kindOf(col) {
        const t = col.target || "";
        if (!t || t === "ignore") { return { label: "", tone: "none", icon: "" }; }
        if (t.startsWith("identity:")) { return { label: _t("Finds the person"), tone: "key", icon: "link" }; }
        if (t === WHEN) { return { label: _t("When it starts"), tone: "when", icon: "calendarClock" }; }
        const group = this.fieldGroups[t];
        return {
            employee: { label: _t("About the person"), tone: "person", icon: "user" },
            contract: { label: _t("Contract"), tone: "contract", icon: "fileText" },
            bank: { label: _t("Bank details"), tone: "bank", icon: "creditCard" },
            component: { label: _t("Ongoing pay"), tone: "pay", icon: "banknote" },
            oneoff: { label: _t("One-off pay"), tone: "pay", icon: "coins" },
        }[group] || { label: "", tone: "none", icon: "" };
    }

    chipOf(col) {
        if (this.duplicateOf(col)) {
            return { tone: "warn", icon: "alert", label: _t("Already used by “%s”. Only that one is brought in.", this.duplicateOf(col).head) };
        }
        if (!col.target || col.target === "ignore") {
            return { tone: "muted", icon: "minusCircle", label: col.how === "memory" ? _t("Not brought in, as last time") : _t("Not brought in") };
        }
        return {
            id: { tone: "ok", icon: "checkCircle", label: _t("From a Payobook sheet") },
            memory: { tone: "ok", icon: "history", label: _t("Remembered from last time") },
            label: { tone: "info", icon: "check", label: _t("Matched by name") },
            identity: { tone: "info", icon: "check", label: _t("Matched by name") },
            guess: { tone: "warn", icon: "alert", label: _t("Best guess. Please check") },
            confirmed: { tone: "ok", icon: "check", label: _t("Confirmed by you") },
            you: { tone: "pri", icon: "check", label: _t("Matched by you") },
        }[col.how] || { tone: "pri", icon: "check", label: _t("Matched by you") };
    }

    get matchCounts() {
        const m = this.state.match;
        const cols = m ? m.columns : [];
        const placed = cols.filter((c) => c.target && c.target !== "ignore" && !this.duplicateOf(c));
        return {
            total: cols.length,
            placed: placed.length,
            guesses: cols.filter((c) => c.how === "guess").length,
            identity: placed.filter((c) => c.target.startsWith("identity:")).length,
            values: placed.filter((c) => !c.target.startsWith("identity:") && c.target !== WHEN).length,
            dated: placed.some((c) => c.target === WHEN),
        };
    }

    get matchLead() {
        const m = this.state.match;
        const c = this.matchCounts;
        const size = _t("Your file has %(cols)s and %(rows)s.", {
            cols: plural(c.total, _t("1 column"), _t("%s columns")),
            rows: plural(m.rows, _t("1 row"), _t("%s rows")) });
        if (m.layoutKnown) {
            const known = _t("You have used these headings before, so the matching is remembered.");
            return size + " " + known;
        }
        if (!c.placed) {
            const none = _t("None of them is matched yet: choose where each one goes.");
            return size + " " + none;
        }
        const placed = plural(c.placed, _t("1 is matched already"), _t("%s are matched already"));
        return size + " " + placed + ".";
    }

    get matchCheckLine() {
        const n = this.matchCounts.guesses;
        return n ? plural(n, _t("1 best guess to check."), _t("%s best guesses to check.")) : "";
    }

    matchColumns() {
        const used = {};
        const identity = {};
        const heads = {};
        for (const col of this.state.match.columns) {
            heads[col.idx] = col.head;
            if (!col.target || col.target === "ignore" || this.duplicateOf(col)) { continue; }
            if (col.target.startsWith("identity:")) {
                identity[col.target.split(":")[1]] = col.idx;
            } else {
                used[col.idx] = col.target;
            }
        }
        return { used, identity, heads };
    }

    get matchRefusal() {
        const c = this.matchCounts;
        if (!c.identity) {
            return _t("Choose which column finds the person: Employee code, Employee name or Work email.");
        }
        if (!c.values) { return _t("Choose at least one column to bring in."); }
        return "";
    }

    async continueMatch() {
        const refusal = this.matchRefusal;
        if (refusal) {
            this.state.matchError = refusal;
            return;
        }
        await this.toReview(false);
    }

    // =================================================================
    //  Review
    // =================================================================
    async toReview(fromSheet) {
        const f = this.state.file;
        Object.assign(f, { busy: true, phase: "review", error: "" });
        this.state.matchError = "";
        const columns = this.matchColumns();
        try {
            const res = await this.orm.call(MODEL, "review", [], this.kindArgs({
                file_b64: f.b64, filename: f.name, columns }));
            if (!res.ok || res.empty) {
                if (fromSheet) {
                    Object.assign(f, { busy: false, error: res.msg });
                } else {
                    f.busy = false;
                    this.state.matchError = res.msg;
                }
                return;
            }
            const rows = (res.rows || []).map((r, i) => Object.assign(r, { key: `r${i}` }));
            const unmatched = (res.unmatched || []).map((u) => Object.assign(u, { skipped: false, bound: false }));
            this.state.rv = {
                filename: res.filename,
                summary: res.summary || {},
                identity: res.identity,
                truncated: res.truncated,
                fromSheet,
                columns: res.columns || [],
                rows,
                unmatched,
                pay_items: !!res.pay_items,
                schemes: res.schemes || [],
                no_scheme: res.no_scheme || 0,
                // UPDATES P2c — the file's start-date column, the company's
                // today, and the default picked on the Apply step.
                dated: !!res.dated,
                today: res.today || this.state.home.today || "",
                defaultStart: this.isOneoff ? "" : this.defaultStart,
                // UPDATES P2d — a sheet of one-off pay items for one month.
                oneoff: !!res.oneoff,
                month: res.month || "",
                month_label: res.month_label || "",
                currency: res.currency || null,
                scheme: null,
                filter: rows.length > 300 ? "chg" : "all",
                allCols: false,
                limit: PAGE_ROWS,
                fix: null,
                stats: { rows: (res.summary || {}).rows || rows.length + unmatched.length },
            };
            f.busy = false;
            this.go("review");
        } catch (e) {
            f.busy = false;
            const msg = e.data?.message || _t("The file could not be checked. Nothing has changed.");
            if (fromSheet) { f.error = msg; } else { this.state.matchError = msg; }
        }
    }

    recheck(changes) {
        return this.orm.call(MODEL, "recheck", [], this.kindArgs({ changes }));
    }

    lookup(term) {
        return this.orm.call(MODEL, "lookup_people", [], { term, limit: 8 });
    }

    backFromReview() {
        if (this.state.rv && this.state.rv.fromSheet) {
            this.state.rv = null;
            this.go("start");
        } else {
            this.go("match");
        }
    }

    changeMatching() {
        this.state.match.fromSheet = false;
        this.go("match");
    }

    toApply() {
        const a = this.state.apply;
        if (!a.touched) {
            a.name = this.isOneoff ? _t("%s one-off pay items", this.monthLabel) : defaultName();
        }
        a.error = "";
        this.go("apply");
        this.refreshPaid();
        this.refreshLanes();
    }

    // =================================================================
    //  UPDATES P3a — lanes
    // =================================================================
    /** Ask the server, once per visit to Apply, what each lane will do. */
    async refreshLanes() {
        this.state.lanes = [];
        if (this.isOneoff || !this.state.rv) { return; }
        this.state.lanesBusy = true;
        try {
            const res = await this.orm.silent.call(MODEL, "lane_outlook", [], {
                changes: changesToSend(this.state.rv) });
            this.state.lanes = res.lanes || [];
        } catch {
            // a forecast, never a gate: Apply still answers for itself
            this.state.lanes = [];
        } finally {
            this.state.lanesBusy = false;
        }
    }

    laneValues(l) {
        return _t("%(values)s for %(people)s", {
            values: plural(l.values, _t("1 value"), _t("%s values")),
            people: plural(l.people, _t("1 person"), _t("%s people")) });
    }

    laneOutIcon(l) {
        return { now: "check", approval: "clock", second: "users", nobody: "alert" }[l.outcome] || "info";
    }

    /** "Apply 42 and send 15 for approval" — from the lanes, when no date splits it. */
    get laneSplit() {
        const lanes = this.state.lanes || [];
        if (!lanes.length || this.laterCount) { return null; }
        const now = lanes.filter((l) => l.outcome === "now").reduce((n, l) => n + l.values, 0);
        const send = lanes.filter((l) => l.outcome !== "now").reduce((n, l) => n + l.values, 0);
        return { now, send };
    }

    laneIcon(lane) { return LANE_ICON[lane] || "pencil"; }
    laneName(lane) { return laneLabel(lane) || _t("Changes"); }

    /** One line of a Past-updates lane: what happened to that part. */
    hlaneLine(l) {
        const bits = [plural(l.values, _t("1 value"), _t("%s values"))];
        if (l.state === "pending") {
            bits.push(l.lane === "bank"
                ? (l.with_whom ? _t("waiting for a second person: %s", l.with_whom) : (l.note || _t("waiting for a second person")))
                : (l.with_whom ? _t("waiting for approval with %s", l.with_whom) : _t("waiting for approval")));
        } else if (l.state === "scheduled" && l.start_date) {
            bits.push(_t("scheduled for %s", dayLabel(l.start_date)));
        } else if (l.note && (l.state === "blocked" || l.state === "returned")) {
            bits.push(l.note);
        }
        return bits.join(" · ");
    }

    hlaneTone(l) {
        return { applied: "ok", pending: "info", scheduled: "pri", cancelled: "muted", undone: "muted",
                 rejected: "err", returned: "warn", blocked: "err" }[l.state] || "muted";
    }

    undoLane(h, l) {
        this.undoBatch(h.id, `${h.name} · ${l.label}`, false, false, l.apply_id);
    }

    cancelLane(h, l) {
        this.cancelParts({ applyId: l.apply_id, name: `${h.name} · ${l.label}`, values: l.values,
                           date: l.start_date, pending: l.state === "pending" });
    }

    // ------------------------------------------------------------ the switch
    get detailsNow() { return this.state.home.details_now || null; }

    get detailsNowNote() {
        const d = this.detailsNow;
        if (!d) { return ""; }
        if (d.route === "custom") {
            return _t("Your company has its own approval route for record changes, so personal details follow it either way.");
        }
        return d.on
            ? _t("Job titles, phone numbers and other personal details change as soon as you apply. Pay and bank details still follow their own rules.")
            : _t("Personal details go to the same approval as pay changes.");
    }

    async toggleDetailsNow() {
        const d = this.detailsNow;
        if (!d || !d.can_set || this.state.switching) { return; }
        this.state.switching = true;
        try {
            const res = await this.orm.call(MODEL, "set_details_now", [], { on: !d.on });
            if (res.ok) {
                this.state.home.details_now = res;
                this.notif.add(res.on
                    ? _t("Personal details from a sheet now apply without approval.")
                    : _t("Personal details from a sheet now go for approval."), { type: "success" });
            } else {
                this.notif.add(res.msg, { type: "warning" });
            }
        } catch (e) {
            this.notif.add(e.data?.message || _t("The setting could not be changed."), { type: "danger" });
        } finally {
            this.state.switching = false;
        }
    }

    // =================================================================
    //  Apply — when do these changes start? (UPDATES P2c)
    // =================================================================
    get todayIso() {
        return (this.state.rv && this.state.rv.today) || this.state.home.today || luxon.DateTime.now().toISODate();
    }

    get whenBounds() {
        const today = luxon.DateTime.fromISO(this.todayIso);
        return { min: today.minus({ days: REACH_DAYS }).toISODate(),
                 max: today.plus({ days: REACH_DAYS }).toISODate() };
    }

    /** The default start for rows without their own date ("" = today). */
    get defaultStart() {
        const w = this.state.when;
        if (w.mode !== "date" || !w.date || w.date === this.todayIso) { return ""; }
        const b = this.whenBounds;
        return w.date < b.min || w.date > b.max ? "" : w.date;
    }

    get whenDateError() {
        const w = this.state.when;
        if (w.mode !== "date" || !w.date) { return ""; }
        const b = this.whenBounds;
        if (w.date < b.min || w.date > b.max) {
            return _t("Pick a date up to a year back or a year ahead.");
        }
        return "";
    }

    syncDefault() {
        if (this.state.rv) { this.state.rv.defaultStart = this.defaultStart; }
        this.refreshPaid();
    }

    setWhenMode(mode) {
        this.state.when.mode = mode;
        if (mode === "date" && !this.state.when.date) {
            this.state.when.date = luxon.DateTime.fromISO(this.todayIso).plus({ months: 1 }).startOf("month").toISODate();
        }
        this.syncDefault();
    }

    onWhenDate(ev) {
        this.state.when.date = ev.target.value || "";
        this.syncDefault();
    }

    setScope(scope) { this.state.when.scope = scope; }

    /** Every row-date and default-date bucket, held as the person chose. */
    get buckets() { return startBuckets(this.state.rv || { rows: [] }, this.state.when.scope); }

    /** Is a future date in play at all (whatever is held back)? */
    get futureInPlay() {
        return Object.keys(startBuckets(this.state.rv || { rows: [] }, "all").later).length > 0;
    }

    get pastInPlay() { return Object.keys(this.buckets.past).length > 0; }

    get laterCount() { return Object.values(this.buckets.later).reduce((n, v) => n + v, 0); }

    get nowCount() {
        return this.buckets.now + Object.values(this.buckets.past).reduce((n, v) => n + v, 0);
    }

    get tooManyDates() { return this.buckets.dates.size > MAX_DATES; }

    /** "38 values change today · 12 are scheduled for 1 Dec 2026 · 4 are
     *  recorded as starting 1 Oct 2026" — the server's own grouping. */
    get whenSummary() {
        const b = this.buckets;
        const bits = [];
        if (b.now) {
            bits.push(plural(b.now, _t("1 value changes today"), _t("%s values change today")));
        }
        for (const day of Object.keys(b.later).sort()) {
            bits.push(b.later[day] === 1
                ? _t("1 is scheduled for %s", dayLabel(day))
                : _t("%(n)s are scheduled for %(date)s", { n: grouped(b.later[day]), date: dayLabel(day) }));
        }
        for (const day of Object.keys(b.past).sort()) {
            bits.push(b.past[day] === 1
                ? _t("1 is recorded as starting %s", dayLabel(day))
                : _t("%(n)s are recorded as starting %(date)s", { n: grouped(b.past[day]), date: dayLabel(day) }));
        }
        return bits.join(" · ");
    }

    get tooManyDatesLine() {
        return _t("This update has %(n)s different start dates. Split it into files of at most %(max)s.", {
            n: grouped(this.buckets.dates.size), max: MAX_DATES });
    }

    get paidNote() {
        const n = this.state.when.paid;
        if (!n || !this.pastInPlay) { return ""; }
        return n === 1
            ? _t("1 of these people has already been paid for a period after this date. Finished pay runs are not recalculated, and back pay is not added automatically.")
            : _t("%s of these people have already been paid for a period after this date. Finished pay runs are not recalculated, and back pay is not added automatically.", grouped(n));
    }

    /** One grouped question to the server: who already has a finished
     *  payslip ending on or after their past start date. */
    async refreshPaid() {
        const rv = this.state.rv;
        if (!rv) { return; }
        const people = {};
        for (const row of rv.rows || []) {
            const s = rowStart(rv, row);
            if (s.kind !== "past") { continue; }
            if (!Object.values(row.cells || {}).some((c) => c && c.status === "ok" && !c.left)) { continue; }
            if (!people[row.emp_id] || s.date < people[row.emp_id]) { people[row.emp_id] = s.date; }
        }
        const key = JSON.stringify(people);
        if (key === this.state.when.paidKey) { return; }
        this.state.when.paidKey = key;
        if (!Object.keys(people).length) { this.state.when.paid = 0; return; }
        try {
            const res = await this.orm.silent.call(MODEL, "paid_since", [], { people });
            if (this.state.when.paidKey === key) { this.state.when.paid = res.count || 0; }
        } catch {
            // a note, never a gate
        }
    }

    // =================================================================
    //  Apply
    // =================================================================
    get applyCounts() { return reviewCounts(this.state.rv); }

    get applyLabel() {
        const n = this.applyCounts.changes;
        if (this.isOneoff) {
            return this.state.apply.busy
                ? plural(n, _t("Sending 1 one-off amount…"), _t("Sending %s one-off amounts…"))
                : plural(n, _t("Send 1 one-off amount"), _t("Send %s one-off amounts"));
        }
        const later = this.laterCount;
        const now = this.nowCount;
        if (this.state.apply.busy) {
            return plural(n, _t("Applying 1 change…"), _t("Applying %s changes…"));
        }
        if (later && now) { return plural(n, _t("Apply and schedule 1 change"), _t("Apply and schedule %s changes")); }
        if (later) { return plural(n, _t("Schedule 1 change"), _t("Schedule %s changes")); }
        const split = this.laneSplit;
        if (split && split.now && split.send) {
            return _t("Apply %(now)s and send %(send)s for approval", {
                now: grouped(split.now), send: grouped(split.send) });
        }
        if (split && split.send && !split.now) {
            return plural(split.send, _t("Send 1 change for approval"), _t("Send %s changes for approval"));
        }
        return plural(n, _t("Apply 1 change"), _t("Apply %s changes"));
    }

    get applyIcon() {
        if (this.isOneoff) { return "coins"; }
        return this.laterCount && !this.nowCount ? "calendarClock" : "check";
    }

    /** UPDATES P2d — the month's totals on the Apply step. */
    get applyTotals() { return this.state.rv ? oneoffTotals(this.state.rv) : { earn: 0, take: 0 }; }
    money(n) { return moneyLabel(this.state.rv, n); }

    onName(ev) {
        this.state.apply.name = ev.target.value;
        this.state.apply.touched = true;
        this.state.apply.error = "";
    }

    onNameKey(ev) { if (ev.key === "Enter") { ev.preventDefault(); this.applyNow(); } }

    get nameMissing() { return !(this.state.apply.name || "").trim(); }

    async applyNow() {
        const a = this.state.apply;
        if (a.busy || !this.canWrite) { return; }
        if (this.nameMissing) {
            a.error = _t("Give this update a name so you can find it later in Past updates.");
            return;
        }
        if (!this.isOneoff && (this.whenDateError || this.tooManyDates)) {
            a.error = this.whenDateError || this.tooManyDatesLine;
            return;
        }
        const rv = this.state.rv;
        const counts = this.applyCounts;
        a.busy = true;
        try {
            const answer = await this.orm.call(MODEL, "apply", [], this.kindArgs({
                name: a.name.trim(),
                file_b64: this.state.file.b64,
                filename: this.state.file.name,
                columns: this.matchColumns(),
                changes: changesToSend(rv),
                stats: { rows: rv.stats.rows, unmatched: counts.rowsOpen + rv.unmatched.filter((u) => u.skipped).length,
                         left_out: counts.leftOut, off_scheme: counts.offScheme },
                start_date: this.isOneoff ? false : (this.defaultStart || false),
                hold_scope: this.state.when.scope,
            }));
            if (!answer.ok) {
                a.error = answer.msg;
                return;
            }
            this.state.done = answer;
            this.go("done");
        } catch (e) {
            a.error = e.data?.message || _t("Nothing was changed: the update could not be sent. Try again.");
        } finally {
            a.busy = false;
        }
    }

    // =================================================================
    //  Done
    // =================================================================
    /** UPDATES P2c — the parts of a dated update (none for an undated one). */
    get doneParts() { return (this.state.done && this.state.done.parts) || []; }

    get doneScheduled() { return this.doneParts.filter((p) => p.scheduled); }

    /** UPDATES P3a — the lanes of what was just sent (more than one only). */
    get doneLanes() {
        const lanes = (this.state.done && this.state.done.lanes) || [];
        return lanes.length > 1 || (lanes.length === 1 && lanes[0].lane === "bank") ? lanes : [];
    }

    doneLaneLine(l) {
        const what = plural(l.values, _t("1 value"), _t("%s values"));
        if (l.pending) {
            if (l.lane === "bank") {
                return l.with_whom
                    ? _t("%(what)s waiting for a second person: %(who)s", { what, who: l.with_whom })
                    : _t("%(what)s waiting: %(why)s", { what, why: l.block_note || _t("nobody else can approve bank details yet") });
            }
            return l.with_whom
                ? _t("%(what)s waiting for approval with %(who)s", { what, who: l.with_whom })
                : _t("%s waiting for approval", what);
        }
        if (l.scheduled) {
            return _t("%(what)s scheduled for %(date)s", { what, date: dayLabel(l.start_date || l.date) });
        }
        return l.details_now
            ? plural(l.written, _t("1 value changed now, no approval needed"), _t("%s values changed now, no approval needed"))
            : plural(l.written, _t("1 value changed"), _t("%s values changed"));
    }

    doneLaneTone(l) {
        if (l.pending) { return l.lane === "bank" && !l.with_whom ? "warn" : "info"; }
        return l.scheduled ? "pri" : "ok";
    }

    get doneOnlyLater() {
        const d = this.state.done;
        return !!(d && !d.pending && !d.written && this.doneScheduled.length);
    }

    get doneTitle() {
        const d = this.state.done;
        if (d.nothing) { return _t("Nothing needed changing"); }
        if (d.kind === "oneoff") { return d.pending ? _t("Sent for approval") : _t("Approved"); }
        if (d.pending && this.doneParts.some((p) => !p.pending)) { return _t("Sent, part of it for approval"); }
        if (d.pending && this.doneLanes.some((l) => !l.pending)) { return _t("Sent, part of it for approval"); }
        if (d.pending) { return _t("Sent for approval"); }
        if (this.doneOnlyLater) {
            return _t("Scheduled for %s", dayLabel(this.doneScheduled[0].date));
        }
        return _t("%(changes)s in for %(people)s", {
            changes: plural(d.written, _t("1 change is"), _t("%s changes are")),
            people: plural(d.people, _t("1 person"), _t("%s people")) });
    }

    /** "12 values changed today · 30 are scheduled for 1 Dec 2026" */
    get doneWhenLine() {
        const d = this.state.done;
        if (d && d.kind === "oneoff") {
            const bits = [];
            if (d.earn) { bits.push(_t("%s added to pay", d.earn)); }
            if (d.take) { bits.push(_t("%s taken from pay", d.take)); }
            if (d.not_used) { bits.push(plural(d.not_used, _t("1 not used: already in a pay run"), _t("%s not used: already in a pay run"))); }
            return bits.join(" · ");
        }
        const bits = [];
        for (const p of this.doneParts) {
            if (p.pending) {
                bits.push(p.date
                    ? _t("%(n)s waiting for approval, then starting %(date)s", { n: grouped(p.values), date: dayLabel(p.date) })
                    : plural(p.values, _t("1 waiting for approval"), _t("%s waiting for approval")));
            } else if (p.scheduled) {
                bits.push(p.values === 1
                    ? _t("1 value is scheduled for %s", dayLabel(p.date))
                    : _t("%(n)s values are scheduled for %(date)s", { n: grouped(p.values), date: dayLabel(p.date) }));
            } else if (p.kind === "past") {
                bits.push(p.written === 1
                    ? _t("1 value changed, recorded as starting %s", dayLabel(p.date))
                    : _t("%(n)s values changed, recorded as starting %(date)s", { n: grouped(p.written), date: dayLabel(p.date) }));
            } else {
                bits.push(plural(p.written, _t("1 value changed today"), _t("%s values changed today")));
            }
        }
        return bits.length > 1 || this.doneScheduled.length || this.doneParts.some((p) => p.kind === "past")
            ? bits.join(" · ") : "";
    }

    get doneLaterNote() {
        if (!this.doneScheduled.length) { return ""; }
        return _t("A scheduled change is written on its day by itself. Until then you will find it under Coming up, where you can start it now or cancel it.");
    }

    get doneLine() {
        const d = this.state.done;
        if (d.nothing) { return d.msg; }
        if (d.kind === "oneoff") {
            const what = plural(d.values, _t("1 one-off amount"), _t("%s one-off amounts"));
            const pay = _t("These will be included in the %s pay run.", d.month_label);
            if (d.pending) {
                return d.with_whom
                    ? _t("%(what)s are waiting with %(who)s. %(pay)s", { what, who: d.with_whom, pay })
                    : _t("%(what)s are waiting for approval. %(pay)s", { what, pay });
            }
            return _t("%(what)s for %(people)s are approved. %(pay)s", {
                what, people: plural(d.people, _t("1 person"), _t("%s people")), pay });
        }
        if (d.pending && (this.doneParts.some((p) => !p.pending) || this.doneLanes.length > 1)) {
            return _t("What is waiting for approval changes nothing until it is approved. Each part is listed below.");
        }
        if (d.pending) {
            const what = plural(this.applyCounts.changes, _t("1 change"), _t("%s changes"));
            return d.with_whom
                ? _t("%(what)s are waiting with %(who)s. Nothing changes until they approve.", { what, who: d.with_whom })
                : _t("%s are waiting for approval. Nothing changes until it is approved.", what);
        }
        return _t("Saved as “%s”. You will find it under Past updates, with the original file.", d.batch_name || this.state.apply.name);
    }

    get doneOffScheme() {
        const d = this.state.done;
        return d && d.off_scheme ? offSchemeLine(d.off_scheme) : "";
    }

    get applyOffScheme() {
        const n = this.applyCounts.offScheme;
        return n ? plural(n,
            _t("1 value will be skipped because that pay item is not in the person's pay scheme."),
            _t("%s values will be skipped because those pay items are not in the person's pay scheme.")) : "";
    }

    get refusedRows() {
        const d = this.state.done;
        const rv = this.state.rv;
        const names = {};
        for (const r of (rv ? rv.rows : [])) { names[r.emp_id] = r.name; }
        const labels = {};
        for (const c of (rv ? rv.columns : [])) { labels[c.field_id] = c.label; }
        return (d.refused || []).map((r, i) => ({
            key: i,
            who: r.emp_name || names[r.emp_id] || "",
            what: r.field_label || labels[r.field_id] || "",
            why: r.why || "",
        }));
    }

    stepTone(step) {
        return { open: "info", approved: "ok", done: "ok", rejected: "err", returned: "warn" }[step.status] || "muted";
    }

    async undoDone() {
        const d = this.state.done;
        if (!d || !d.batch_id) { return; }
        await this.undoBatch(d.batch_id, d.batch_name || this.state.apply.name, true,
                             this.doneScheduled.length > 0);
    }

    get undoDoneLabel() {
        return this.doneScheduled.length ? _t("Undo what was applied") : _t("Undo this update");
    }

    // =================================================================
    //  Undo (home and done)
    // =================================================================
    undoBatch(batchId, name, thenHome = false, mixed = false, applyId = 0) {
        return new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Undo “%s”?", name),
                body: mixed
                    ? _t("Every value this update has already changed goes back to what it was before. A value someone has changed since is left as it is. The scheduled part is not touched: cancel it separately.")
                    : _t("Every value this update changed goes back to what it was before. A value someone has changed since is left as it is."),
                confirmLabel: mixed ? _t("Undo what was applied") : _t("Undo the update"),
                cancelLabel: _t("Keep it"),
                confirm: async () => {
                    this.state.undoing = batchId;
                    try {
                        const res = await this.orm.call(MODEL, "undo", [], { batch_id: batchId, apply_id: applyId });
                        if (!res.ok) {
                            this.notif.add(res.msg, { type: "warning" });
                        } else {
                            const back = plural(res.restored, _t("1 value is back as it was."), _t("%s values are back as they were."));
                            const kept = res.skipped_changed_since
                                ? " " + plural(res.skipped_changed_since, _t("1 was left alone because someone changed it since."), _t("%s were left alone because someone changed them since."))
                                : "";
                            this.notif.add(_t("“%(name)s” is undone. %(back)s%(kept)s", { name, back, kept }), { type: "success" });
                        }
                        if (thenHome) {
                            this.resetFlow();
                            this.go("home");
                        }
                        await this.loadHistory();
                    } catch (e) {
                        this.notif.add(e.data?.message || _t("The update could not be undone. Nothing has changed."), { type: "danger" });
                    } finally {
                        this.state.undoing = 0;
                        resolve();
                    }
                },
                cancel: () => resolve(),
            });
        });
    }
}

registry.category("actions").add("pb_updates_desk", PbUpdatesDesk);

// ---------------------------------------------------------------------------
//  The doors: the People hub lens (right after Records) and a ⌘K row.
// ---------------------------------------------------------------------------

/** Who Updates lets in — `pb.records.desk._may_read`, restated (the same list
 *  the Records lens carries, so the two tabs never disagree). */
export const UPDATES_GATE = [
    "pb_records.group_records_viewer",
    "hr.group_hr_user",
    "pb_hr_payroll_base.group_payroll_base_officer",
    "base.group_system",
];

registry.category(PEOPLE_LENSES).add("updates", {
    key: "updates",
    icon: "fileSpreadsheet",
    label: _t("Updates"),
    title: _t("Update many people at once"),
    Component: PbUpdatesDesk,
    groups: UPDATES_GATE,
}, { sequence: 41 });

registry.category("pb_hub_palette").add("peoplehub_updates", {
    id: "peoplehub_updates",
    label: _t("Updates"),
    sublabel: _t("People"),
    icon: "fileSpreadsheet",
    groups: UPDATES_GATE,
    requires: "pb_updates_desk",
    action: { xmlid: "pb_people_hub.action_pb_people_hub", lens: "updates" },
}, { sequence: 1441 });
