/** @odoo-module **/
/**
 * Step 3 — "Who works which week?" (WFSETUP P2).
 *
 * Every active person of the company arrives in ONE `people()` call; the
 * table filters, searches and sorts in memory so every keystroke is instant,
 * and renders 200 rows at a time as the list scrolls.
 *
 * Selection lives in a plain Set (not reactive: 678 entries would make every
 * tick a deep-proxy walk); `state.tick` is bumped to redraw. Click or Space
 * ticks, Shift-click / Shift+Arrow ticks a range, the header box ticks the
 * current list, Ctrl/Cmd+A ticks the current list, Escape clears.
 *
 * Bulk actions open a drawer whose "What will happen" is computed by the
 * server (`*_preview`, debounced 250 ms) BEFORE anything is applied; Apply
 * then shows a toast with Undo.
 */
import { Component, onWillStart, onWillUnmount, useExternalListener, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { deserializeDate, serializeDate } from "@web/core/l10n/dates";
import { MODEL, icon, dayNames, hrs, errorText, timeRange, rich } from "./setup_util";
import { SetupDrawer } from "./setup_drawer";

const CHUNK = 200;
const PREVIEW_MS = 250;

/** Lower case, no accents, đ -> d: "Nguyễn" matches "nguyen". */
function fold(text) {
    return String(text || "")
        .normalize("NFD")
        .replace(/[̀-ͯ]/g, "")
        .replace(/[đĐ]/g, "d")
        .toLowerCase();
}

export class StepPeople extends Component {
    static template = "pb_workforce_setup.StepPeople";
    static components = { SetupDrawer };
    static props = { studio: Object, data: Object };

    setup() {
        this.orm = useService("orm");
        this.icon = icon;
        this.days = dayNames();
        this.range = timeRange;
        this.root = useRef("root");
        this.wrap = useRef("wrap");
        this.bulk = useRef("bulk");
        this.search = useRef("search");
        this.sel = new Set();
        this.anchor = null;          // index in the current list of the last click
        this.version = 0;
        this.state = useState({
            loading: true,
            error: "",
            people: null,
            q: "",
            team: null,
            onlyMissing: false,
            limit: CHUNK,
            focus: -1,
            tick: 0,
            drawer: null,
            applying: false,
        });
        // capture phase: the web client's hotkey layer stops Escape before
        // it bubbles to window (found in the browser walk)
        useExternalListener(window, "keydown", (ev) => this.onWindowKey(ev), { capture: true });
        onWillStart(() => this.load());
        onWillUnmount(() => {
            clearTimeout(this.previewTimer);
            clearTimeout(this.personTimer);
        });
    }

    // ------------------------------------------------------------ data
    async load() {
        const seq = (this.loadSeq = (this.loadSeq || 0) + 1);
        this.state.error = "";
        try {
            const people = await this.orm.call(MODEL, "people", []);
            if (seq !== this.loadSeq) {
                return;
            }
            for (const row of people.rows) {
                row.hay = fold(`${row.name} ${row.number} ${row.department} ${row.site}`);
            }
            const live = new Set(people.rows.map((r) => r.id));
            for (const id of [...this.sel]) {
                if (!live.has(id)) {
                    this.sel.delete(id);
                }
            }
            this.version++;
            this.state.people = people;
            this.state.tick++;
        } catch (e) {
            if (seq === this.loadSeq) {
                this.state.error = errorText(e);
            }
        } finally {
            if (seq === this.loadSeq) {
                this.state.loading = false;
            }
        }
    }

    retry() {
        this.state.loading = true;
        this.load();
    }

    // ------------------------------------------------------------ reading
    get canEdit() { return this.props.data.can_edit; }
    get people() { return this.state.people; }
    get rows() { return this.people ? this.people.rows : []; }
    get teams() { return this.people ? this.people.teams : []; }
    get weeks() { return this.props.data.weeks; }
    get shifts() { return this.props.data.shifts; }
    get missing() { return this.people ? this.people.without_week : 0; }
    get total() { return this.people ? this.people.total : 0; }

    get shiftMap() {
        if (this._shiftsFor !== this.shifts) {
            this._shiftsFor = this.shifts;
            this._shiftMap = Object.fromEntries(this.shifts.map((s) => [s.id, s]));
        }
        return this._shiftMap;
    }

    /** The filtered list, memoised on its inputs. */
    get list() {
        const key = `${this.version}|${this.state.q}|${this.state.team}|${this.state.onlyMissing}`;
        if (this._listKey !== key) {
            const q = fold(this.state.q).trim();
            const words = q ? q.split(/\s+/) : [];
            const team = this.state.team;
            this._list = this.rows.filter((r) =>
                (team === null || r.department_id === team)
                && (!this.state.onlyMissing || !r.week_now)
                && words.every((w) => r.hay.includes(w)));
            this._listKey = key;
        }
        return this._list;
    }
    get visible() {
        void this.state.tick;
        return this.list.slice(0, this.state.limit);
    }
    get more() { return Math.max(0, this.list.length - this.state.limit); }
    get teamRow() { return this.teams.find((t) => t.id === this.state.team) || null; }

    // ------------------------------------------------------------ words
    get headChip() {
        if (!this.total) {
            return "";
        }
        return this.missing
            ? _t("%(n)s of %(total)s still need a working week", { n: this.missing, total: this.total })
            : _t("Everyone has a working week");
    }
    teamLine(team) {
        if (team.with_week === team.total) {
            return team.total === 1 ? _t("The 1 person has a working week") : _t("All %s have a working week", team.total);
        }
        return _t("%(n)s of %(total)s have a working week", { n: team.with_week, total: team.total });
    }
    teamWidth(team) {
        return `width:${team.total ? (team.with_week / team.total) * 100 : 0}%`;
    }
    get tickTeamLabel() { return _t("Tick all of %s", this.teamRow ? this.teamRow.name : ""); }
    get selCount() { void this.state.tick; return this.sel.size; }
    get selLine() {
        const n = this.selCount;
        return n === 1 ? _t("1 person ticked") : _t("%s people ticked", n);
    }
    get selAllLine() { return _t("%s ticked.", this.selCount); }
    get selAllButton() { return _t("Tick all %s in this list", this.list.length); }
    get showSelAll() {
        const n = this.selCount;
        return this.canEdit && n >= 8 && !this.allTicked && this.list.length > n;
    }
    get cappedLine() {
        return _t("Showing the first %s people. Search to find anyone else.", (this.people?.cap || 5000).toLocaleString());
    }
    get moreLine() { return _t("%s more below. Keep scrolling.", this.more); }
    groupLabel(row) {
        return row.group === "manager" ? _t("Manager") : row.group === "worker" ? _t("Worker") : _t("Not set");
    }
    tickLabel(row) { return _t("Tick %s", row.name); }
    mini(row) {
        return row.week_days.map((id, i) => {
            const s = id && this.shiftMap[id];
            return { key: i, cls: id ? `is-on pbws-c-${s ? s.color : "indigo"}` : "" };
        });
    }
    weekLabel(row) {
        return row.week_no ? _t("%(week)s · week %(n)s", { week: row.week_name, n: row.week_no }) : row.week_name;
    }
    /** The rotation week as its own chip: it never disappears into an
     *  ellipsis when the column is narrow (P2 report, weakest point). */
    weekNoLabel(row) { return _t("week %s", row.week_no); }
    alsoLabel(row) { return _t("%s working weeks", row.also_on.length + 1); }
    alsoTitle(row) { return _t("Also on: %s", row.also_on.join(", ")); }
    oneoffLabel(row) { return _t("+%s one-off", row.oneoff); }
    startsLabel(row) { return _t("starts %s", this.fmt(row.week_from)); }
    fromText(row) { return row.week_from ? this.fmt(row.week_from) : ""; }
    fmt(iso) {
        if (!iso) {
            return "";
        }
        try {
            return deserializeDate(iso).toFormat("ccc d LLL");
        } catch {
            return iso;
        }
    }
    isTicked(row) { void this.state.tick; return this.sel.has(row.id); }
    get allTicked() {
        void this.state.tick;
        return this.list.length > 0 && this.list.every((r) => this.sel.has(r.id));
    }
    get someTicked() {
        void this.state.tick;
        return !this.allTicked && this.list.some((r) => this.sel.has(r.id));
    }
    rowClass(row, index) {
        return `${this.isTicked(row) ? "is-sel" : ""}${index === this.state.focus ? " is-focus" : ""}${row.id === this.props.data.person?.id ? " is-shown" : ""}`;
    }

    // ------------------------------------------------------------ filters
    pickTeam(team) {
        this.state.team = this.state.team === team.id ? null : team.id;
        this.resetView();
    }
    showEveryone() {
        this.state.team = null;
        this.resetView();
    }
    toggleMissing() {
        this.state.onlyMissing = !this.state.onlyMissing;
        this.resetView();
    }
    onSearch(ev) {
        this.state.q = ev.target.value;
        this.resetView();
    }
    clearFilters() {
        this.state.q = "";
        this.state.team = null;
        this.state.onlyMissing = false;
        this.resetView();
        this.search.el?.focus();
    }
    resetView() {
        this.state.limit = CHUNK;
        this.state.focus = -1;
        this.anchor = null;
        if (this.wrap.el) {
            this.wrap.el.scrollTop = 0;
        }
    }
    onScroll(ev) {
        const el = ev.target;
        if (this.more && el.scrollTop + el.clientHeight > el.scrollHeight - 400) {
            this.state.limit += CHUNK;
        }
    }

    // ------------------------------------------------------------ ticking
    bump() { this.state.tick++; }
    tickTeam() {
        for (const r of this.list) {
            this.sel.add(r.id);
        }
        this.bump();
    }
    tickList() {
        if (!this.canEdit) {
            return;
        }
        const all = this.allTicked;
        for (const r of this.list) {
            if (all) {
                this.sel.delete(r.id);
            } else {
                this.sel.add(r.id);
            }
        }
        this.bump();
    }
    tickAllInList() {
        for (const r of this.list) {
            this.sel.add(r.id);
        }
        this.bump();
    }
    clearTicks() {
        this.sel.clear();
        this.anchor = null;
        this.bump();
    }
    onHeadBox(ev) {
        ev.preventDefault();
        this.tickList();
    }
    onRowClick(row, index, ev) {
        if (ev.target.closest("input[type=checkbox]")) {
            ev.preventDefault();    // the state decides, not the native toggle
        }
        this.state.focus = index;
        if (this.canEdit) {
            if (ev.shiftKey && this.anchor !== null) {
                this.tickRange(this.anchor, index);
            } else {
                if (this.sel.has(row.id)) {
                    this.sel.delete(row.id);
                } else {
                    this.sel.add(row.id);
                }
                this.anchor = index;
            }
            this.bump();
        }
        this.show(row);
    }
    tickRange(a, b) {
        const [from, to] = a < b ? [a, b] : [b, a];
        const list = this.list;
        for (let i = from; i <= to; i++) {
            if (list[i]) {
                this.sel.add(list[i].id);
            }
        }
    }
    /** The right panel follows the last row clicked (debounced for arrows). */
    show(row) {
        clearTimeout(this.personTimer);
        this.personTimer = setTimeout(() => this.props.studio.setPerson(row.id), 120);
    }
    onRowKey(row, index, ev) {
        const list = this.list;
        if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault();
            const next = Math.max(0, Math.min(list.length - 1, index + (ev.key === "ArrowDown" ? 1 : -1)));
            if (next >= this.state.limit) {
                this.state.limit += CHUNK;
            }
            if (ev.shiftKey && this.canEdit) {
                if (this.anchor === null) {
                    this.anchor = index;
                }
                this.sel.add(list[index].id);
                this.sel.add(list[next].id);
                this.bump();
            }
            this.focusRow(next);
            this.show(list[next]);
        } else if (ev.key === " " || ev.key === "Spacebar") {
            ev.preventDefault();
            if (this.canEdit) {
                if (this.sel.has(row.id)) {
                    this.sel.delete(row.id);
                } else {
                    this.sel.add(row.id);
                }
                this.anchor = index;
                this.bump();
            }
            this.show(row);
        } else if (ev.key === "Enter") {
            ev.preventDefault();
            this.show(row);
        }
    }
    focusRow(index) {
        this.state.focus = index;
        // after the redraw, move real focus to that row
        requestAnimationFrame(() => {
            const el = this.wrap.el?.querySelector(`tr[data-index="${index}"]`);
            el?.focus({ preventScroll: false });
            el?.scrollIntoView({ block: "nearest" });
        });
    }
    rowTab(index) {
        const focus = this.state.focus >= 0 ? this.state.focus : 0;
        return index === focus ? "0" : "-1";
    }
    onWindowKey(ev) {
        if (this.state.drawer || !this.root.el) {
            return;
        }
        const active = document.activeElement;
        const typing = active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA" || active.isContentEditable);
        const inside = active && (this.root.el.contains(active) || active === document.body);
        if (!inside) {
            return;
        }
        if ((ev.metaKey || ev.ctrlKey) && (ev.key === "a" || ev.key === "A") && !typing && this.canEdit) {
            ev.preventDefault();
            this.tickAllInList();
        } else if (ev.key === "Escape" && this.sel.size && !typing) {
            ev.preventDefault();
            this.clearTicks();
        }
    }

    // ------------------------------------------------------------ drawers
    get noWeeks() { return !this.weeks.length; }
    get noWeeksTitle() { return this.noWeeks ? _t("Build a working week first") : false; }
    get today() { return this.props.data.today; }
    plusDays(iso, n) {
        return serializeDate(deserializeDate(iso).plus({ days: n }));
    }
    nextMonday() {
        const d = deserializeDate(this.today);
        return serializeDate(d.plus({ days: 8 - d.weekday }));
    }
    openAssign() {
        if (this.noWeeks) {
            return;
        }
        this.state.drawer = { type: "assign", week: this.weeks[0].id, from: this.today, startWeek: 0, mode: "replace", preview: null, loading: true };
        this.schedulePreview();
    }
    openOneoff() {
        if (!this.shifts.length) {
            return;
        }
        const from = this.nextMonday();
        this.state.drawer = { type: "oneoff", shift: this.shifts[0].id, from, to: this.plusDays(from, 5), days: [0, 1, 2, 3, 4, 5], preview: null, loading: true };
        this.schedulePreview();
    }
    openLate() {
        this.state.drawer = { type: "late", group: "worker", preview: null, loading: true };
        this.schedulePreview();
    }
    closeDrawer() {
        this.state.drawer = null;
        clearTimeout(this.previewTimer);
        requestAnimationFrame(() => this.bulk.el?.querySelector(".pbws-bulk-pri")?.focus());
    }
    setChoice(key, value) {
        const d = this.state.drawer;
        d[key] = value;
        if (key === "week") {
            d.startWeek = 0;
        }
        this.schedulePreview();
    }
    onDate(key, ev) {
        if (ev.target.value) {
            this.setChoice(key, ev.target.value);
        }
    }
    toggleDay(i) {
        const d = this.state.drawer;
        d.days = d.days.includes(i) ? d.days.filter((x) => x !== i) : [...d.days, i].sort();
        this.schedulePreview();
    }
    schedulePreview() {
        const d = this.state.drawer;
        if (!d) {
            return;
        }
        d.loading = true;
        clearTimeout(this.previewTimer);
        this.previewTimer = setTimeout(() => this.runPreview(), PREVIEW_MS);
    }
    callArgs(d) {
        const ids = [...this.sel];
        if (d.type === "assign") {
            return ["assign_week", [ids, d.week, d.from, d.startWeek, d.mode]];
        }
        if (d.type === "oneoff") {
            return ["oneoff_apply", [ids, d.shift, d.from, d.to, d.days]];
        }
        return ["set_late_rule", [ids, d.group]];
    }
    previewMethod(d) {
        return { assign: "assign_week_preview", oneoff: "oneoff_preview", late: "set_late_rule_preview" }[d.type];
    }
    async runPreview() {
        const d = this.state.drawer;
        if (!d) {
            return;
        }
        const seq = (this.previewSeq = (this.previewSeq || 0) + 1);
        const [, args] = this.callArgs(d);
        try {
            const preview = await this.orm.call(MODEL, this.previewMethod(d), args);
            if (seq === this.previewSeq && this.state.drawer === d) {
                d.preview = preview;
                d.error = "";
            }
        } catch (e) {
            if (seq === this.previewSeq && this.state.drawer === d) {
                d.preview = null;
                d.error = errorText(e);
            }
        } finally {
            if (seq === this.previewSeq && this.state.drawer === d) {
                d.loading = false;
            }
        }
    }
    get dr() { return this.state.drawer; }
    get pv() { return this.dr?.preview || null; }
    get problems() { return this.pv?.problems || []; }
    get applyCount() {
        const d = this.dr;
        const p = this.pv;
        if (!d || !p || this.problems.length && !this.okWithProblems) {
            return 0;
        }
        if (d.type === "assign") {
            return p.will_move;
        }
        if (d.type === "oneoff") {
            return p.will_add;
        }
        return p.changed || p.policy_set || 0;
    }
    /** "left out" lines are warnings, not refusals. */
    get okWithProblems() {
        const p = this.pv;
        return !!p && (p.will_move > 0 || p.will_add > 0 || p.changed > 0 || p.policy_set > 0);
    }
    get applyDisabled() {
        return !this.dr || this.dr.loading || this.state.applying || !this.applyCount;
    }
    get applyLabel() {
        const d = this.dr;
        const n = this.applyCount;
        if (d?.type === "oneoff") {
            return n === 1 ? _t("Add 1 shift") : _t("Add %s shifts", n);
        }
        return _t("Apply to %s", n);
    }
    get drawerTitle() {
        const d = this.dr;
        const n = this.sel.size;
        if (d.type === "assign") {
            return n === 1 ? _t("Give 1 person a working week") : _t("Give %s people a working week", n);
        }
        if (d.type === "oneoff") {
            return n === 1 ? _t("One-off shift for 1 person") : _t("One-off shift for %s people", n);
        }
        return n === 1 ? _t("Late rule for 1 person") : _t("Late rule for %s people", n);
    }
    get drawerSub() {
        const d = this.dr;
        if (d.type === "assign") {
            return _t("One choice, applied to everyone you ticked.");
        }
        if (d.type === "oneoff") {
            return _t("For cover, a rush order or a training day. Their normal working week stays as it is.");
        }
        return _t("Decides which lateness lines from step 4 apply to them.");
    }

    // assign drawer
    weekOf(id) { return this.weeks.find((w) => w.id === id) || null; }
    get chosenWeek() { return this.dr ? this.weekOf(this.dr.week) : null; }
    weekStrip(w) {
        const days = w.weeks.length ? w.weeks[0] : w.days.slice(0, 7);
        return days.map((id, i) => {
            const s = id && this.shiftMap[id];
            return { key: i, cls: id ? `is-on pbws-c-${s ? s.color : "indigo"}` : "" };
        });
    }
    weekSub(w) {
        if (w.weeks.length > 1) {
            return _t("Repeats every %s weeks", w.weeks.length);
        }
        if (w.weeks.length === 1) {
            return _t("%s a week", hrs(w.minutes_per_week[0]));
        }
        return _t("Repeats every %s days", w.cycle_days);
    }
    get rotationWeeks() {
        const w = this.chosenWeek;
        return w && w.weeks.length > 1 ? w.weeks.map((_w, i) => i) : [];
    }
    weekButton(i) { return _t("Week %s", i + 1); }
    get differentLine() {
        const n = this.pv?.keep_theirs || 0;
        return n === 1 ? _t("1 already has a different week") : _t("%s already have a different week", n);
    }
    get assignLines() {
        const p = this.pv;
        if (!p || p.problems?.length && !p.will_move) {
            return [];
        }
        const out = [];
        const n = p.will_move;
        out.push(n === 0
            ? rich(_t("Nobody moves to %(week)s."), { week: p.week_name })
            : n === 1
                ? rich(_t("1 person moves to %(week)s from %(date)s."), { week: p.week_name, date: p.date_text })
                : rich(_t("%(n)s people move to %(week)s from %(date)s."), { n, week: p.week_name, date: p.date_text }));
        if (this.dr.mode === "keep" && p.kept) {
            out.push(rich(p.kept === 1 ? _t("1 person keeps the week they already have.") : _t("%(n)s keep the week they already have."), { n: p.kept }));
        }
        if (p.already) {
            out.push(rich(p.already === 1 ? _t("1 person already works this week, so nothing changes for them.")
                : _t("%(n)s already work this week, so nothing changes for them."), { n: p.already }));
        }
        if (this.dr.mode === "replace") {
            for (const e of p.ends || []) {
                out.push(rich(e.people === 1 ? _t("%(week)s ends on %(date)s for 1 of them.")
                    : _t("%(week)s ends on %(date)s for %(n)s of them."), { week: e.week_name, date: p.ends_text, n: e.people }));
            }
        }
        if (p.rotation_weeks > 1 && n) {
            out.push(rich(_t("In the week of %(date)s they work week %(k)s of the rotation."), { date: p.date_text, k: p.start_week + 1 }));
        }
        return out;
    }

    // one-off drawer
    shiftSub(s) { return timeRange(s.start, s.end); }
    get oneoffLines() {
        const p = this.pv;
        if (!p || (p.problems?.length && !p.will_add)) {
            return [];
        }
        const out = [];
        out.push(rich(p.will_add === 1 ? _t("1 one-off shift will be added.") : _t("%(n)s one-off shifts will be added."), { n: p.will_add }));
        const days = p.days === 1 ? _t("1 day") : _t("%s days", p.days);
        const people = p.people === 1 ? _t("1 person") : _t("%s people", p.people);
        out.push(rich(this.skippedTotal ? _t("That is %(days)s × %(people)s, less the days below.")
            : _t("That is %(days)s × %(people)s."), { days, people }));
        if (p.replace_drafts) {
            out.push(rich(p.replace_drafts === 1 ? _t("1 replaces a shift that was planned but not published yet.")
                : _t("%(n)s replace shifts that were planned but not published yet."), { n: p.replace_drafts }));
        }
        return out;
    }
    get skippedTotal() { return (this.pv?.skipped_list || []).reduce((a, s) => a + s.count, 0); }
    get skippedLine() {
        const n = this.skippedTotal;
        return n === 1 ? _t("1 day is left out:") : _t("%s days are left out:", n);
    }
    skipText(s) { return _t("%(why)s (%(n)s)", { why: s.label, n: s.count }); }

    // late drawer
    get groups() {
        return [
            { key: "worker", label: _t("Worker") },
            { key: "manager", label: _t("Manager") },
        ];
    }
    groupLines(key) {
        const lines = this.pv?.lines?.[key] || [];
        return lines.length ? lines.join(" · ") : _t("Its lateness lines are set in step 4.");
    }
    get lateLines() {
        const p = this.pv;
        if (!p || (p.problems?.length && !p.changed && !p.policy_set)) {
            return [];
        }
        const rule = this.dr.group === "manager" ? _t("Manager") : _t("Worker");
        const out = [];
        out.push(p.changed === 1
            ? rich(_t("1 person changes to the %(rule)s late rule."), { rule })
            : rich(_t("%(n)s people change to the %(rule)s late rule."), { n: p.changed, rule }));
        if (p.unchanged) {
            out.push(rich(p.unchanged === 1 ? _t("1 person already has it.") : _t("%(n)s already have it."), { n: p.unchanged }));
        }
        if (p.policy_set) {
            out.push(rich(p.policy_set === 1 ? _t("1 person is also linked to your late rules.")
                : _t("%(n)s people are also linked to your late rules."), { n: p.policy_set }));
        }
        return out;
    }

    // ------------------------------------------------------------ apply + undo
    async apply() {
        const d = this.dr;
        if (this.applyDisabled) {
            return;
        }
        this.state.applying = true;
        const [method, args] = this.callArgs(d);
        let res;
        try {
            res = await this.orm.call(MODEL, method, args);
        } catch (e) {
            this.state.applying = false;
            this.props.studio.toast(errorText(e), { kind: "error" });
            this.schedulePreview();
            return;
        }
        this.state.applying = false;
        this.closeDrawer();
        this.clearTicks();
        await Promise.all([this.load(), this.props.studio.refresh()]);
        this.toast(res);
        // the bulk bar is gone with the ticks: focus goes back to the list
        requestAnimationFrame(() => (this.wrap.el?.querySelector('tr[tabindex="0"]') || this.search.el)?.focus({ preventScroll: true }));
    }
    /** The studio's own toast, just above where the bulk bar sits, with
     *  Undo for ~8 s (the bar is gone by then: the ticks were cleared). */
    toast(res) {
        if (!res.undo_id) {
            this.props.studio.toast(res.summary, { kind: "info" });
            return;
        }
        this.props.studio.toast(res.summary, { undo: () => this.undo(res.undo_id) });
    }
    async undo(id) {
        try {
            const res = await this.orm.call(MODEL, "undo", [id]);
            await Promise.all([this.load(), this.props.studio.refresh()]);
            this.props.studio.toast(res.summary, { kind: "info" });
        } catch (e) {
            this.props.studio.toast(errorText(e), { kind: "error" });
        }
    }

    // ------------------------------------------------------------ misc
    goWeeks() { this.props.studio.go("weeks"); }
    get skeleton() { return [1, 2, 3, 4, 5, 6]; }
}
