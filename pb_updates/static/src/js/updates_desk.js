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
} from "@pb_updates/js/updates_review";

const MODEL = "pb.updates.desk";
const STEPS = ["start", "match", "review", "apply"];
/** The default name: "November 2026 update", the month in the reader's language. */
export function defaultName() {
    return _t("%s update", luxon.DateTime.now().toFormat("LLLL yyyy"));
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
            home: { can_write: false, can_export: false, people_count: 0, topics: [], history: [] },
            historyAll: false,
            historyTotal: 0,
            picked: {},
            download: { busy: false, msg: "", tone: "" },
            file: { name: "", b64: "", busy: false, rows: 0, phase: "", error: "", over: 0 },
            match: null,
            matchError: "",
            rv: null,
            apply: { name: "", busy: false, error: "", touched: false },
            done: null,
            undoing: 0,
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
        const res = await this.orm.call(MODEL, "get_history", [], {
            limit: this.state.historyAll ? 200 : 8 });
        this.state.home.history = res.batches || [];
        this.state.historyTotal = res.total || 0;
    }

    async showAllHistory() {
        this.state.historyAll = true;
        await this.loadHistory();
    }

    get canWrite() { return !!this.state.home.can_write; }
    get canExport() { return !!this.state.home.can_export; }

    get heroBody() {
        return _t("Change job details, contracts, bank details and ongoing pay items for the whole team from one spreadsheet, any day of the month. You see every change before it happens, and you can undo it afterwards.");
    }

    get noWriteNote() {
        return _t("You can check a file and see exactly what it would change. Applying it needs the HR or Payroll Officer role.");
    }

    historyTone(h) {
        return { applied: "ok", pending: "info", undone: "muted", rejected: "err", returned: "warn" }[h.state] || "muted";
    }

    historyIcon(h) {
        return { applied: "check", pending: "clock", undone: "undo", rejected: "xCircle", returned: "rotate" }[h.state] || "info";
    }

    historyLine(h) {
        const bits = [whenLabel(h.date)];
        if (h.values) {
            bits.push(_t("%(changes)s for %(people)s", {
                changes: plural(h.values, _t("1 change"), _t("%s changes")),
                people: plural(h.people, _t("1 person"), _t("%s people")) }));
        }
        if (h.user) { bits.push(_t("by %s", h.user)); }
        return bits.filter(Boolean).join(" · ");
    }

    historyNote(h) {
        if (h.state === "pending") {
            return h.with_whom ? _t("Waiting for approval with %s.", h.with_whom) : _t("Waiting for approval.");
        }
        if (h.state === "undone") {
            return h.undone_by
                ? _t("Put back on %(when)s by %(who)s.", { when: whenLabel(h.undone_date), who: h.undone_by })
                : _t("Put back on %s.", whenLabel(h.undone_date));
        }
        const bits = [];
        const left = (h.values_refused || 0);
        if (left) { bits.push(plural(left, _t("1 value from the file was left out."), _t("%s values from the file were left out."))); }
        if (h.values_off_scheme) { bits.push(offSchemeLine(h.values_off_scheme)); }
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

    newUpdate() {
        this.resetFlow();
        this.go("start");
    }

    resetFlow() {
        Object.assign(this.state.file, { name: "", b64: "", busy: false, rows: 0, phase: "", error: "", over: 0 });
        Object.assign(this.state.download, { busy: false, msg: "", tone: "" });
        this.state.match = null;
        this.state.matchError = "";
        this.state.rv = null;
        this.state.done = null;
        Object.assign(this.state.apply, { name: "", busy: false, error: "", touched: false });
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
        if (d.busy || !this.canExport || !this.pickedTopics.length) { return; }
        Object.assign(d, { busy: true, msg: "", tone: "" });
        try {
            const res = await this.orm.call(MODEL, "download_sheet", [], {
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
            const res = await this.orm.call(MODEL, "read_columns", [], { file_b64: b64, filename: file.name });
            if (!res.ok) {
                Object.assign(f, { busy: false, error: res.msg });
                return;
            }
            f.rows = res.rows;
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

    get fieldLabels() {
        const out = {};
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
        for (const t of m.fields) {
            if (t.key !== "component") {
                out.push({ key: t.key, label: t.label, options: t.fields.map((f) => ({ id: f.id, label: f.label })) });
                continue;
            }
            const present = new Map((m.schemes || []).map((s, i) => [s.id, { ...s, order: i }]));
            const single = new Map();
            const several = [];
            const kept = [];
            for (const f of t.fields) {
                const schemes = f.schemes || [];
                if (!schemes.length) { kept.push({ id: f.id, label: f.label }); continue; }
                if (schemes.length > 1) {
                    const names = schemes.map((s) => s.name);
                    const shown = names.length > 3
                        ? _t("%(list)s and %(n)s more", { list: names.slice(0, 3).join(", "), n: names.length - 3 })
                        : names.join(", ");
                    several.push({ id: f.id, label: `${f.label} · ${shown}` });
                    continue;
                }
                const s = schemes[0];
                if (!single.has(s.id)) { single.set(s.id, { scheme: s, options: [] }); }
                single.get(s.id).options.push({ id: f.id, label: f.label });
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
        if (!m || !m.fields.some((t) => t.key === "component" && t.fields.length)) { return null; }
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
            const res = await this.orm.silent.call(MODEL, "file_schemes", [], {
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
        const group = this.fieldGroups[t];
        return {
            employee: { label: _t("About the person"), tone: "person", icon: "user" },
            contract: { label: _t("Contract"), tone: "contract", icon: "fileText" },
            bank: { label: _t("Bank details"), tone: "bank", icon: "creditCard" },
            component: { label: _t("Ongoing pay"), tone: "pay", icon: "banknote" },
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
            values: placed.filter((c) => !c.target.startsWith("identity:")).length,
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
            const res = await this.orm.call(MODEL, "review", [], {
                file_b64: f.b64, filename: f.name, columns });
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
        return this.orm.call(MODEL, "recheck", [], { changes });
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
        if (!a.touched) { a.name = defaultName(); }
        a.error = "";
        this.go("apply");
    }

    // =================================================================
    //  Apply
    // =================================================================
    get applyCounts() { return reviewCounts(this.state.rv); }

    get applyLabel() {
        const n = this.applyCounts.changes;
        return this.state.apply.busy
            ? plural(n, _t("Applying 1 change…"), _t("Applying %s changes…"))
            : plural(n, _t("Apply 1 change"), _t("Apply %s changes"));
    }

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
        const rv = this.state.rv;
        const counts = this.applyCounts;
        a.busy = true;
        try {
            const answer = await this.orm.call(MODEL, "apply", [], {
                name: a.name.trim(),
                file_b64: this.state.file.b64,
                filename: this.state.file.name,
                columns: this.matchColumns(),
                changes: changesToSend(rv),
                stats: { rows: rv.stats.rows, unmatched: counts.rowsOpen + rv.unmatched.filter((u) => u.skipped).length,
                         left_out: counts.leftOut, off_scheme: counts.offScheme },
            });
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
    get doneTitle() {
        const d = this.state.done;
        if (d.nothing) { return _t("Nothing needed changing"); }
        if (d.pending) { return _t("Sent for approval"); }
        return _t("%(changes)s in for %(people)s", {
            changes: plural(d.written, _t("1 change is"), _t("%s changes are")),
            people: plural(d.people, _t("1 person"), _t("%s people")) });
    }

    get doneLine() {
        const d = this.state.done;
        if (d.nothing) { return d.msg; }
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
        await this.undoBatch(d.batch_id, d.batch_name || this.state.apply.name, true);
    }

    // =================================================================
    //  Undo (home and done)
    // =================================================================
    undoBatch(batchId, name, thenHome = false) {
        return new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Undo “%s”?", name),
                body: _t("Every value this update changed goes back to what it was before. A value someone has changed since is left as it is."),
                confirmLabel: _t("Undo the update"),
                cancelLabel: _t("Keep it"),
                confirm: async () => {
                    this.state.undoing = batchId;
                    try {
                        const res = await this.orm.call(MODEL, "undo", [], { batch_id: batchId });
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
