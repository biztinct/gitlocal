/** @odoo-module **/
/**
 * UPDATES P5 (owner decision D20) — year-to-date figures before Payobook.
 *
 * Patches the Updates screen (one OWL root) with:
 *   - the fourth kind of sheet's own words, date and Apply card;
 *   - the year-to-date view (`view: "ytd"`): per person and figure, Before
 *     Payobook + Paid in Payobook = Total, months missing, a download, and
 *     "Download for the pay run";
 *   - the set-up a payroll manager does (which pay items "paid in Payobook"
 *     adds up, pay items named as figures, which pay item of which scheme
 *     receives which figure — nothing reaches a pay run without it);
 *   - the way out under "Nobody else … can approve bank details yet"
 *     (UPDATES P6 deviation 1): the same links the approvals inbox offers.
 *
 * Nothing here decides anything: the server facade is `pb.updates.desk`.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { grouped } from "@pb_records/js/records_review";
import { PbUpdatesDesk } from "@pb_updates/js/updates_desk";
import { UpdReview, plural, dayLabel, moneyLabel, cellKind } from "@pb_updates/js/updates_review";

const MODEL = "pb.updates.desk";
const PAGE = 50;

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

/** `{byCol: {field_id: n}, figures, people}` over the figures Apply would send. */
export function ytdTotals(rv) {
    const out = { byCol: {}, figures: 0, people: 0, cleared: 0 };
    const people = new Set();
    for (const row of (rv && rv.rows) || []) {
        for (const [fid, cell] of Object.entries(row.cells || {})) {
            if (cellKind(cell) !== "change") { continue; }
            out.figures += 1;
            people.add(row.emp_id);
            if (cell.cleared) { out.cleared += 1; continue; }
            out.byCol[fid] = (out.byCol[fid] || 0) + Number(cell.amount || 0);
        }
    }
    out.people = people.size;
    return out;
}

// ---------------------------------------------------------------------------
//  The review grid: the strip and the per-figure totals
// ---------------------------------------------------------------------------
patch(UpdReview.prototype, {
    get ytdSums() { return ytdTotals(this.rv); },
    get ytdStripLine() {
        return _t("Tax year %(year)s · before Payobook, up to %(date)s", {
            year: this.rv.tax_year, date: dayLabel(this.rv.covers_to) || this.rv.covers_label || "" });
    },
    get ytdSummary() {
        const t = this.ytdSums;
        return _t("%(figures)s for %(people)s", {
            figures: plural(t.figures, _t("1 figure"), _t("%s figures")),
            people: plural(t.people, _t("1 person"), _t("%s people")) });
    },
    get ytdLateChip() {
        const n = this.rv.late || 0;
        return n ? plural(n, _t("1 joined after this date"), _t("%s joined after this date")) : "";
    },
    ytdColTag(col) {
        const n = this.ytdSums.byCol[col.field_id] || 0;
        if (!n) { return col.count ? _t("Months") : _t("Before Payobook"); }
        return col.count ? plural(n, _t("1 month in total"), _t("%s months in total"))
            : _t("%s in total", moneyLabel(this.rv, n));
    },
});

// ---------------------------------------------------------------------------
//  The Updates screen
// ---------------------------------------------------------------------------
patch(PbUpdatesDesk.prototype, {
    // ------------------------------------------------ Start: the date
    get ytdYear() {
        const d = luxon.DateTime.fromISO(this.state.ytdCovers || "");
        return d.isValid ? d.year : (this.ytdInfo.this_year || "");
    },
    get ytdCoversLabel() { return dayLabel(this.state.ytdCovers); },
    get ytdYears() {
        const info = this.ytdInfo;
        return [info.this_year, info.last_year].filter(Boolean);
    },
    setYtdYear(year) {
        const info = this.ytdInfo;
        if (year === info.last_year) {
            this.state.ytdCovers = `${year}-12-31`;
        } else {
            this.state.ytdCovers = info.default || info.today || `${year}-01-31`;
        }
        this.state.ytdCoversNote = "";
        Object.assign(this.state.download, { busy: false, msg: "", tone: "" });
    },
    onYtdCovers(ev) {
        this.state.ytdCovers = ev.target.value || "";
        this.state.ytdCoversNote = "";
        Object.assign(this.state.download, { busy: false, msg: "", tone: "" });
    },
    get ytdCoversError() {
        const d = this.state.ytdCovers;
        const info = this.ytdInfo;
        if (!d) { return _t("Pick the date these figures cover up to: the last day before your first pay period on Payobook."); }
        if (info.min && d < info.min) { return _t("Figures can be for this tax year or last year only."); }
        if (info.max && d > info.max) { return _t("That date is too far ahead. Pick the last day before your first pay period on Payobook."); }
        return "";
    },
    get ytdCoversLine() {
        return _t("Tax year %(year)s: what each person was paid and taxed from 1 January to %(date)s, before your company ran payroll here.", {
            year: this.ytdYear, date: this.ytdCoversLabel });
    },
    get ytdFiguresLine() {
        return (this.ytdInfo.figures || []).map((f) => f.label).join(" · ");
    },
    get ytdMatchLead() {
        return _t("Year-to-date figures for %(year)s, up to %(date)s.", { year: this.ytdYear, date: this.ytdCoversLabel });
    },

    // ------------------------------------------------ Apply
    get ytdApply() {
        const rv = this.state.rv;
        if (!rv || !rv.ytd) { return null; }
        const t = ytdTotals(rv);
        const cols = (rv.columns || []).map((c) => ({
            key: c.field_id, label: c.label,
            total: c.count ? plural(t.byCol[c.field_id] || 0, _t("1 month"), _t("%s months"))
                : moneyLabel(rv, t.byCol[c.field_id] || 0),
        }));
        return Object.assign(t, { cols });
    },
    get ytdCardTitle() {
        return _t("Tax year %(year)s, before Payobook up to %(date)s", { year: this.ytdYear, date: this.ytdCoversLabel });
    },
    async refreshYtdOutlook() {
        this.state.ytdOutlook = null;
        if (!this.isYtd || !this.state.rv) { return; }
        try {
            const changes = [];
            for (const row of this.state.rv.rows || []) {
                for (const [fid, cell] of Object.entries(row.cells || {})) {
                    if (cellKind(cell) === "change") { changes.push({ emp_id: row.emp_id, field_id: fid }); }
                }
            }
            this.state.ytdOutlook = await this.orm.silent.call(MODEL, "ytd_outlook", [], { changes });
        } catch {
            this.state.ytdOutlook = { outcome: "approval", line: _t("Go for approval") };
        }
    },
    get ytdOutIcon() {
        const o = this.state.ytdOutlook;
        return o && o.outcome === "now" ? "check" : "clock";
    },

    // ------------------------------------------------ Past updates
    ytdHistoryNote(h) {
        const bits = [];
        if (h.state === "pending") {
            bits.push(h.with_whom ? _t("Waiting for approval with %s.", h.with_whom) : _t("Waiting for approval."));
        }
        if (h.not_set) {
            const first = (h.not_set_lines || [])[0];
            bits.push(first ? _t("%(n)s could not be set, for example %(who)s · %(what)s: %(why)s", {
                n: grouped(h.not_set), who: first.who, what: first.type, why: first.why })
                : plural(h.not_set, _t("1 could not be set."), _t("%s could not be set.")));
        }
        if (h.used_values) {
            bits.push(plural(h.used_values, _t("1 was used by a finished payslip and is locked."),
                             _t("%s were used by finished payslips and are locked.")));
        }
        if (h.undone_values) {
            bits.push(plural(h.undone_values, _t("1 figure was taken back."), _t("%s figures were taken back.")));
        }
        if (h.values_refused) {
            bits.push(plural(h.values_refused, _t("1 value from the file was left out."), _t("%s values from the file were left out.")));
        }
        return bits.join(" ");
    },
    undoYtd(h, thenHome = false) {
        return new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Undo “%s”?", h.name),
                body: _t("Each figure this update set is taken back, and a figure it replaced comes back. A figure a finished payslip has used stays."),
                confirmLabel: _t("Undo the figures"),
                cancelLabel: _t("Keep them"),
                confirm: async () => {
                    this.state.undoing = h.id;
                    try {
                        const res = await this.orm.call(MODEL, "undo", [], { batch_id: h.id });
                        this.notif.add(res.ok ? _t("“%(name)s”: %(msg)s", { name: h.name, msg: res.msg }) : res.msg,
                                       { type: res.ok ? "success" : "warning" });
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
    },

    // ------------------------------------------------ the way out (P6 deviation 1)
    openWayOut(link) {
        if (link && link.action) { this.action.doAction(link.action); }
    },

    // =================================================================
    //  The year-to-date view
    // =================================================================
    async openYtdView() {
        if (!this.ytdInfo.available) { return; }
        this.state.ytd = {
            year: this.ytdInfo.this_year, search: "", offset: 0, data: null, busy: true,
            msg: "", tone: "", setup: null, setupOpen: false, setupBusy: false, setupMsg: "", how: null,
            add: {}, itemPick: "", codePick: {},
            payrun: { config: "", month: "", busy: false, msg: "", tone: "" },
            downloading: false,
        };
        this.go("ytd");
        await this.loadYtdView();
    },
    async loadYtdView() {
        const y = this.state.ytd;
        if (!y) { return; }
        if (y.how) { this.closeYtdHow(); }
        y.busy = true;
        try {
            const data = await this.orm.call(MODEL, "get_ytd_view", [], {
                year: y.year, search: y.search, offset: y.offset, limit: PAGE });
            y.data = data;
            if (!y.payrun.month) {
                const cur = (data.months || []).find((m) => m.current);
                y.payrun.month = cur ? cur.value : "";
            }
            if (!y.payrun.config && (data.schemes || []).length) { y.payrun.config = String(data.schemes[0].id); }
        } catch (e) {
            y.msg = e.data?.message || _t("The year-to-date figures could not be read.");
            y.tone = "err";
        } finally {
            y.busy = false;
        }
    },
    get ytdView() { return (this.state.ytd && this.state.ytd.data) || null; },
    setViewYear(year) {
        const y = this.state.ytd;
        if (y.year === year) { return; }
        Object.assign(y, { year, offset: 0 });
        this.loadYtdView();
    },
    onYtdSearch(ev) {
        const y = this.state.ytd;
        y.search = ev.target.value || "";
        if (this._ytdSearchTimer) { clearTimeout(this._ytdSearchTimer); }
        this._ytdSearchTimer = setTimeout(() => {
            this._ytdSearchTimer = null;
            y.offset = 0;
            this.loadYtdView();
        }, 350);
    },
    ytdPage(step) {
        const y = this.state.ytd;
        const total = this.ytdView ? this.ytdView.total : 0;
        const next = Math.max(0, Math.min(y.offset + step * PAGE, Math.max(0, total - 1)));
        if (next === y.offset) { return; }
        y.offset = next;
        this.loadYtdView();
    },
    get ytdPageLine() {
        const v = this.ytdView;
        if (!v || !v.total) { return ""; }
        const from = v.offset + 1;
        const to = Math.min(v.offset + v.rows.length, v.total);
        return _t("%(from)s–%(to)s of %(total)s people", { from: grouped(from), to: grouped(to), total: grouped(v.total) });
    },
    get ytdHasPrev() { return !!(this.ytdView && this.ytdView.offset > 0); },
    get ytdHasNext() { return !!(this.ytdView && this.ytdView.offset + this.ytdView.rows.length < this.ytdView.total); },
    get ytdStrip() {
        const v = this.ytdView;
        if (!v) { return []; }
        const out = [{ key: "p", tone: "pri", icon: "users", label: plural(v.total, _t("1 person with figures this year"), _t("%s people with figures this year")) }];
        out.push({ key: "b", tone: v.people_before ? "ok" : "muted", icon: "history",
                   label: plural(v.people_before, _t("1 with figures before Payobook"), _t("%s with figures before Payobook")) });
        if (v.missing_people) {
            out.push({ key: "m", tone: "warn", icon: "alert",
                       label: plural(v.missing_people, _t("1 on this page has months missing"), _t("%s on this page have months missing")) });
        }
        if (v.open_people) {
            out.push({ key: "o", tone: "warn", icon: "listChecks",
                       label: plural(v.open_people, _t("1 on this page has a figure that is not complete yet"), _t("%s on this page have a figure that is not complete yet")) });
        }
        return out;
    },
    get ytdEmptyTitle() { return _t("No figures for %s yet", this.state.ytd.year); },
    ytdWhoLine(r) {
        const where = r.covers_label ? _t("before Payobook up to %s", r.covers_label) : _t("no figures before Payobook");
        return r.code ? `${r.code} · ${where}` : where;
    },
    ytdMissingLabel(r) { return plural(r.missing, _t("1 month missing"), _t("%s months missing")); },
    get ytdLegend() {
        return { before: _t("Before Payobook"), paid: _t("paid in Payobook"), total: _t("total") };
    },
    ytdMapLine(m) {
        return _t("%(item)s receives %(figure)s · %(basis)s", { item: m.item_label, figure: m.figure_label, basis: m.basis_label });
    },
    get ytdReceivesWord() { return _t("receives"); },
    get ytdDoorLine() {
        const n = this.ytdInfo.people || 0;
        return n ? plural(n, _t("Before Payobook, plus paid in Payobook, per person · 1 person with figures before Payobook this year."),
                          _t("Before Payobook, plus paid in Payobook, per person · %s people with figures before Payobook this year."))
            : _t("Before Payobook, plus paid in Payobook, per person.");
    },
    ytdMissingTitle(r) {
        return _t("No finished payslip for %s", (r.missing_labels || []).join(", "));
    },
    ytdCell(r, f) { return (r.cells || {})[f.key] || null; },

    // ------------------------------------------------ P5c: honest cells
    ytdCellState(r, f) {
        const c = this.ytdCell(r, f);
        return c ? (c.state || "") : "";
    },
    ytdCellTone(r, f) {
        // Amber only for a reason that belongs to the cell itself (payslips
        // without the figure, an overlap, an advance shown apart); a row-level
        // reason (months missing, not covered from January) is said once, by
        // the row's chip, and the cell just reads "Known so far".
        const c = this.ytdCell(r, f);
        if (!c || !c.total_label) { return ""; }
        if (c.year_total) { return "is-complete"; }
        return ["partial", "overlap", "split", "unknown"].includes(c.state) ? "is-open" : "is-soft";
    },
    get ytdKnownWord() { return _t("Known so far"); },
    get ytdBelowWord() { return _t("Includes a month below zero"); },
    ytdAdvanceLine(c) {
        return _t("+ %s in mid-month advances, shown apart and not added", c.advance_label);
    },
    ytdStartLabel(r) { return _t("Not covered: %s", r.start_label); },
    ytdStartTitle(r) {
        return _t("No figures before Payobook and no finished payslip for %s, so the totals are not year totals.", r.start_label);
    },
    ytdTwiceLabel() { return _t("Same pay period twice"); },
    ytdTwiceTitle(r) {
        return _t("Two finished payslips of the same pay scheme and pay period in %s. Both are counted; if one was a test or was replaced, cancel it.", (r.twice_labels || []).join(", "));
    },

    // ------------------------------------------------ P5c: "How this number was worked out"
    ytdHowOpen(r, f) {
        const h = this.state.ytd && this.state.ytd.how;
        return !!(h && h.emp_id === r.emp_id && h.key === f.key);
    },
    ytdHowAria(r, f) {
        return _t("How %(figure)s for %(who)s was worked out", { figure: f.label, who: r.name });
    },
    async openYtdHow(r, f, ev) {
        const y = this.state.ytd;
        if (this.ytdHowOpen(r, f)) { this.closeYtdHow(); return; }
        const rect = ev && ev.currentTarget ? ev.currentTarget.getBoundingClientRect() : null;
        const width = Math.min(380, window.innerWidth - 32);
        let left = rect ? rect.right - width : 16;
        left = Math.max(16, Math.min(left, window.innerWidth - width - 16));
        let top = rect ? rect.bottom + 6 : 80;
        if (top + 360 > window.innerHeight) { top = Math.max(16, (rect ? rect.top : 80) - 366); }
        // The opener lives outside the reactive state (a DOM node in it would be proxied).
        this._ytdHowOpener = ev && ev.currentTarget;
        y.how = { emp_id: r.emp_id, key: f.key, who: r.name, figure: f.label, busy: true, msg: "",
                  data: null, top, left, width };
        if (!this._ytdHowAway) {
            this._ytdHowAway = (e) => {
                if (!e.target.closest || !e.target.closest(".pbu-ytd-pop, .pbu-ytd-how")) { this.closeYtdHow(); }
            };
            window.addEventListener("click", this._ytdHowAway, true);
        }
        const asked = y.how;
        try {
            const data = await this.orm.silent.call(MODEL, "get_ytd_cell_detail", [], {
                year: y.year, emp_id: r.emp_id, key: f.key });
            if (y.how !== asked) { return; }
            if (!data.ok) { Object.assign(asked, { busy: false, msg: data.msg }); return; }
            Object.assign(asked, { busy: false, data });
        } catch (e) {
            if (y.how === asked) {
                Object.assign(asked, { busy: false, msg: e.data?.message || _t("The payslips could not be read.") });
            }
        }
    },
    closeYtdHow() {
        const y = this.state.ytd;
        const opener = this._ytdHowOpener;
        this._ytdHowOpener = null;
        if (y) { y.how = null; }
        if (this._ytdHowAway) {
            window.removeEventListener("click", this._ytdHowAway, true);
            this._ytdHowAway = null;
        }
        if (opener && opener.focus) { opener.focus(); }
    },
    onYtdHowKey(ev) {
        if (ev.key === "Escape") { ev.stopPropagation(); this.closeYtdHow(); }
    },
    get ytdHowStyle() {
        const h = this.state.ytd && this.state.ytd.how;
        return h ? `top:${h.top}px;left:${h.left}px;width:${h.width}px;` : "";
    },
    get ytdHowSubtitle() {
        const h = this.state.ytd.how;
        return _t("%(figure)s · %(who)s · %(year)s", { figure: h.figure, who: h.who, year: this.state.ytd.year });
    },
    get ytdHowItemsLine() {
        const d = this.state.ytd.how && this.state.ytd.how.data;
        return d ? _t("Adds up: %s", (d.items || []).join(", ")) : "";
    },
    get ytdHowLeftLine() {
        const d = this.state.ytd.how && this.state.ytd.how.data;
        return d ? plural(d.left.length, _t("1 payslip not counted, and why"), _t("%s payslips not counted, and why")) : "";
    },
    get ytdUncountedLine() {
        const v = this.ytdView;
        if (!v || !(v.uncounted || []).length) { return ""; }
        return _t("Paid in Payobook is not counted yet for %s: choose which pay items make it up in Set up.", v.uncounted.join(", "));
    },
    async downloadYtdView() {
        const y = this.state.ytd;
        if (y.downloading) { return; }
        y.downloading = true;
        try {
            const res = await this.orm.call(MODEL, "download_ytd_view", [], { year: y.year, search: y.search });
            if (!res.ok) { Object.assign(y, { msg: res.msg, tone: "err" }); return; }
            saveFile(res);
            Object.assign(y, { msg: _t("Downloaded “%(file)s” with %(people)s.", {
                file: res.filename, people: plural(res.rows, _t("1 person"), _t("%s people")) }), tone: "ok" });
        } catch (e) {
            Object.assign(y, { msg: e.data?.message || _t("The sheet could not be built."), tone: "err" });
        } finally {
            y.downloading = false;
        }
    },
    onPayrunScheme(ev) { this.state.ytd.payrun.config = ev.target.value || ""; this.state.ytd.payrun.msg = ""; },
    onPayrunMonth(ev) { this.state.ytd.payrun.month = ev.target.value || ""; this.state.ytd.payrun.msg = ""; },
    get ytdPayrunScheme() {
        const v = this.ytdView;
        const p = this.state.ytd && this.state.ytd.payrun;
        return v && p ? (v.schemes || []).find((s) => String(s.id) === p.config) || null : null;
    },
    async downloadForPayrun() {
        const p = this.state.ytd.payrun;
        if (p.busy || !p.config) { return; }
        p.busy = true;
        try {
            const res = await this.orm.call(MODEL, "download_for_payrun", [], {
                config_id: parseInt(p.config), month: p.month || false });
            if (!res.ok) { Object.assign(p, { msg: res.msg, tone: "err" }); return; }
            saveFile(res);
            const line = res.gaps
                ? plural(res.gaps, _t("1 person has a value that cannot be worked out yet: see the Check column."),
                         _t("%s people have a value that cannot be worked out yet: see the Check column."))
                : _t("Every value could be worked out.");
            Object.assign(p, { msg: _t("Downloaded “%(file)s” for %(people)s. %(line)s", {
                file: res.filename, people: plural(res.rows, _t("1 person"), _t("%s people")), line }),
                               tone: res.gaps ? "warn" : "ok" });
        } catch (e) {
            Object.assign(p, { msg: e.data?.message || _t("The sheet could not be built."), tone: "err" });
        } finally {
            p.busy = false;
        }
    },

    // =================================================================
    //  Set up (a payroll manager)
    // =================================================================
    async toggleYtdSetup() {
        const y = this.state.ytd;
        y.setupOpen = !y.setupOpen;
        if (y.setupOpen && !y.setup) { await this.loadYtdSetup(); }
    },
    async loadYtdSetup() {
        const y = this.state.ytd;
        y.setupBusy = true;
        try {
            y.setup = await this.orm.call(MODEL, "get_ytd_setup", []);
        } catch (e) {
            y.setupMsg = e.data?.message || _t("The set-up could not be read.");
        } finally {
            y.setupBusy = false;
        }
    },
    async ytdSetupCall(method, kwargs, okLine) {
        const y = this.state.ytd;
        if (y.setupBusy) { return; }
        y.setupBusy = true;
        y.setupMsg = "";
        try {
            const res = await this.orm.call(MODEL, method, [], kwargs);
            if (!res.ok) {
                y.setupMsg = res.msg || _t("That could not be saved.");
                return;
            }
            y.setup = res;
            if (okLine) { this.notif.add(okLine, { type: "success" }); }
            await this.loadYtdView();
        } catch (e) {
            y.setupMsg = e.data?.message || _t("That could not be saved. Nothing has changed.");
        } finally {
            y.setupBusy = false;
        }
    },
    get ytdSetupFigures() {
        const s = this.state.ytd && this.state.ytd.setup;
        return s ? s.figures.filter((f) => !f.count && !f.item) : [];
    },
    get ytdItemFigures() {
        const s = this.state.ytd && this.state.ytd.setup;
        return s ? s.figures.filter((f) => f.item) : [];
    },
    ytdItemsFor(f) {
        const s = this.state.ytd.setup;
        const have = new Set((f.codes || []).map((c) => c.code));
        return (s.items || []).filter((i) => !have.has(i.code));
    },
    addFigureCode(f, ev) {
        const code = ev.target.value;
        ev.target.value = "";
        if (!code) { return; }
        const codes = (f.codes || []).map((c) => c.code).concat([code]);
        this.ytdSetupCall("save_ytd_figure", { key: f.key, codes }, _t("%s: saved.", f.label));
    },
    removeFigureCode(f, code) {
        const codes = (f.codes || []).map((c) => c.code).filter((c) => c !== code);
        this.ytdSetupCall("save_ytd_figure", { key: f.key, codes }, _t("%s: saved.", f.label));
    },
    addItemFigure(ev) {
        const code = ev.target.value;
        ev.target.value = "";
        if (!code) { return; }
        this.ytdSetupCall("save_ytd_figure", { add_item: code }, _t("Added as a figure."));
    },
    removeItemFigure(f) {
        this.ytdSetupCall("save_ytd_figure", { key: f.key, remove: true }, _t("%s is no longer a figure.", f.label));
    },
    ytdAddRow(scheme) {
        const add = this.state.ytd.add;
        if (!add[scheme.id]) {
            const first = (scheme.inputs || [])[0];
            add[scheme.id] = { code: first ? first.code : "", figure: "gross", basis: "before_period" };
        }
        return add[scheme.id];
    },
    setAdd(scheme, key, ev) {
        const row = this.ytdAddRow(scheme);
        row[key] = ev.target.value;
        if (key === "figure" && row.figure !== "months" && row.basis === "with_period") { row.basis = "before_period"; }
    },
    ytdBases(row) {
        const s = this.state.ytd.setup;
        return (s.bases || []).filter((b) => b.value !== "with_period" || (row && row.figure === "months"));
    },
    saveMap(scheme) {
        const row = this.ytdAddRow(scheme);
        if (!row.code || !row.figure) { return; }
        const item = (scheme.inputs || []).find((i) => i.code === row.code);
        this.ytdSetupCall("save_ytd_map", { config_id: scheme.id, code: row.code, figure: row.figure, basis: row.basis },
                          _t("Saved. From now on, %s receives this figure in a pay run.", item ? item.label : row.code));
    },
    removeMap(m) {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Stop sending a figure to %s?", m.item_label),
            body: _t("From now on a pay run fills this pay item the way it did before. Payslips already calculated keep what they have until they are calculated again."),
            confirmLabel: _t("Stop sending it"),
            cancelLabel: _t("Keep it"),
            confirm: () => this.ytdSetupCall("remove_ytd_map", { map_id: m.id }, _t("Stopped.")),
            cancel: () => {},
        });
    },
    backFromYtd() {
        if (this.state.ytd && this.state.ytd.how) { this.closeYtdHow(); }
        this.state.ytd = null;
        this.go("home");
        this.loadHistory();
    },
});
