/** @odoo-module **/
/**
 * Step 2 — "What does a normal week look like?"
 *
 * A working week is painted: pick a shift (the brush), then click, drag across
 * the days, or press Enter / Space on a focused day. Each working week keeps a
 * LOCAL working copy while it changes and saves itself 600 ms after the last
 * change ("Saving…" -> "Saved" in its header). A refused save restores the
 * last saved state and shows the server's sentence on the card.
 *
 * Painting uses pointer events. `pointerdown` releases the implicit pointer
 * capture so a finger dragging across the days still enters each cell.
 */
import { Component, onWillUnmount, useEffect, useExternalListener, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { MODEL, icon, dayNames, hrs, deepClone, errorText, timeRange } from "./setup_util";

const AUTOSAVE_MS = 600;

export class StepWeeks extends Component {
    static template = "pb_workforce_setup.StepWeeks";
    static props = { studio: Object, data: Object };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.icon = icon;
        this.range = timeRange;
        this.days = dayNames();
        const first = this.props.data.shifts[0];
        this.state = useState({
            brush: first ? first.id : false,
            edits: {},        // id -> {name, weeks, version}
            marks: {},        // id -> "saving" | "saved"
            errors: {},       // id -> sentence
            confirm: null,
            creating: false,
        });
        this.timers = {};
        this.inflight = {};
        this.again = {};
        this.painting = null;
        this.focusWeek = null;
        useExternalListener(window, "pointerup", () => (this.painting = null));
        useExternalListener(window, "pointercancel", () => (this.painting = null));
        useEffect(
            () => {
                if (this.focusWeek) {
                    const el = document.querySelector(`.pbws-pat[data-week="${this.focusWeek}"] .pbws-pat-name`);
                    if (el) {
                        this.focusWeek = null;
                        el.focus();
                        el.select();
                        el.scrollIntoView({ block: "center", behavior: this.props.studio.motion });
                    }
                }
            },
            () => [this.props.data.weeks.length]
        );
        this.unguard = this.props.studio.addGuard(() => this.flush());
        onWillUnmount(() => {
            this.unguard();
            for (const key of Object.keys(this.timers)) {
                clearTimeout(this.timers[key]);
                if (/^\d+$/.test(key)) {
                    this.saveWeek(Number(key));     // never lose the last strokes
                }
            }
        });
    }

    // ------------------------------------------------------------ reading
    get canEdit() { return this.props.data.can_edit; }
    get shifts() { return this.props.data.shifts; }
    get weeks() { return this.props.data.weeks; }
    get maxWeeks() { return this.props.data.max_weeks || 8; }
    get shiftMap() {
        const map = {};
        for (const s of this.shifts) {
            map[s.id] = s;
        }
        return map;
    }
    get brushValid() {
        return this.state.brush === false || !!this.shiftMap[this.state.brush];
    }
    brushOn(id) {
        const brush = this.brushValid ? this.state.brush : (this.shifts[0]?.id || false);
        return brush === id;
    }
    grid(row) {
        return this.state.edits[row.id]?.weeks || row.weeks;
    }
    nameOf(row) {
        const e = this.state.edits[row.id];
        return e && e.name !== undefined ? e.name : row.name;
    }
    cell(id) {
        return id ? this.shiftMap[id] || null : null;
    }
    weekLabel(row, w) {
        return this.grid(row).length > 1 ? _t("Week %s", w + 1) : _t("Every week");
    }
    peopleText(row) {
        return row.people === 1 ? _t("1 person") : _t("%s people", row.people);
    }
    hoursText(row) {
        const g = this.grid(row);
        if (g.length > 1) {
            return _t("Repeats every %s weeks", g.length);
        }
        const paid = g[0].reduce((sum, id) => sum + (this.cell(id)?.paid_minutes || 0), 0);
        return _t("%s a week", hrs(paid));
    }
    cellLabel(row, w, d) {
        const s = this.cell(this.grid(row)[w][d]);
        const day = this.days[d];
        return s ? _t("%(day)s: %(shift)s", { day, shift: s.name }) : _t("%s: day off", day);
    }
    cycleText(row) {
        return _t("Repeats every %s days", row.cycle_days);
    }

    // ------------------------------------------------------------ painting
    setBrush(id) {
        this.state.brush = id;
    }
    get brushValue() {
        if (this.brushValid) {
            return this.state.brush;
        }
        return this.shifts[0]?.id || false;
    }
    ensure(row) {
        if (!this.state.edits[row.id]) {
            this.state.edits[row.id] = { name: row.name, weeks: deepClone(row.weeks), version: 0 };
        }
        return this.state.edits[row.id];
    }
    paint(row, w, d) {
        if (!this.canEdit || !row.editable) {
            return;
        }
        const value = this.brushValue;
        const current = this.grid(row)[w][d] || false;
        if (current === value) {
            return;
        }
        this.ensure(row).weeks[w][d] = value;
        this.schedule(row);
    }
    onPointerDown(row, w, d, ev) {
        if (ev.button !== 0 || !this.canEdit || !row.editable) {
            return;
        }
        ev.preventDefault();
        if (ev.target.hasPointerCapture?.(ev.pointerId)) {
            ev.target.releasePointerCapture(ev.pointerId);
        }
        ev.currentTarget.focus({ preventScroll: true });
        this.painting = row.id;
        this.paint(row, w, d);
    }
    onPointerEnter(row, w, d) {
        if (this.painting === row.id) {
            this.paint(row, w, d);
        }
    }
    onCellKey(row, w, d, ev) {
        const moves = { ArrowLeft: [0, -1], ArrowRight: [0, 1], ArrowUp: [-1, 0], ArrowDown: [1, 0] };
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.paint(row, w, d);
        } else if (moves[ev.key]) {
            ev.preventDefault();
            const [dw, dd] = moves[ev.key];
            const card = ev.currentTarget.closest(".pbws-pat");
            const next = card?.querySelector(`[data-w="${w + dw}"][data-d="${d + dd}"]`);
            next?.focus();
        }
    }

    addWeek(row) {
        const e = this.ensure(row);
        if (e.weeks.length >= this.maxWeeks) {
            return;
        }
        e.weeks.push([...e.weeks[e.weeks.length - 1]]);
        this.schedule(row);
    }
    removeLastWeek(row) {
        const e = this.ensure(row);
        if (e.weeks.length <= 1) {
            return;
        }
        e.weeks.pop();
        this.schedule(row);
    }
    fill(row, n) {
        const value = this.brushValue || this.shifts[0]?.id || false;
        const e = this.ensure(row);
        e.weeks = e.weeks.map((week) => week.map((_c, i) => (i < n ? value : false)));
        this.schedule(row);
    }

    // ------------------------------------------------------------ the name
    onNameInput(row, ev) {
        this.ensure(row).name = ev.target.value;
    }
    onNameKey(row, ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            ev.target.blur();
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            this.ensure(row).name = row.name;
            ev.target.value = row.name;
            ev.target.blur();
        }
    }
    onNameCommit(row) {
        const e = this.state.edits[row.id];
        if (e && e.name !== row.name) {
            this.schedule(row, 0);
        }
    }

    // ------------------------------------------------------------ saving
    schedule(row, delay = AUTOSAVE_MS) {
        const e = this.ensure(row);
        e.version += 1;
        delete this.state.errors[row.id];
        this.state.marks[row.id] = "saving";
        clearTimeout(this.timers[row.id]);
        this.timers[row.id] = setTimeout(() => {
            delete this.timers[row.id];
            this.saveWeek(row.id);
        }, delay);
    }

    async saveWeek(id) {
        const e = this.state.edits[id];
        if (!e) {
            return true;
        }
        if (this.inflight[id]) {
            this.again[id] = true;
            return this.inflight[id];
        }
        const version = e.version;
        const vals = { name: e.name, weeks: deepClone(e.weeks) };
        const run = (async () => {
            try {
                const saved = await this.orm.call(MODEL, "save_week", [vals, id]);
                this.props.studio.putWeek(saved);
                const now = this.state.edits[id];
                if (now && now.version === version) {
                    delete this.state.edits[id];
                    this.state.marks[id] = "saved";
                    clearTimeout(this.timers[`mark${id}`]);
                    this.timers[`mark${id}`] = setTimeout(() => {
                        delete this.timers[`mark${id}`];
                        if (this.state.marks[id] === "saved") {
                            delete this.state.marks[id];
                        }
                    }, 2200);
                }
                this.props.studio.refresh();
                return true;
            } catch (err) {
                delete this.state.edits[id];          // back to the last saved state
                delete this.state.marks[id];
                this.state.errors[id] = errorText(err);
                this.props.studio.refresh();
                return false;
            } finally {
                delete this.inflight[id];
                if (this.again[id]) {
                    delete this.again[id];
                    if (this.state.edits[id] && !this.timers[id]) {
                        this.saveWeek(id);
                    }
                }
            }
        })();
        this.inflight[id] = run;
        return run;
    }

    /** Leave guard: push every pending change now. */
    async flush() {
        const ids = Object.keys(this.timers).filter((k) => /^\d+$/.test(k));
        for (const id of ids) {
            clearTimeout(this.timers[id]);
            delete this.timers[id];
        }
        await Promise.all([...ids.map((id) => this.saveWeek(Number(id))), ...Object.values(this.inflight)]);
        return true;
    }

    // ------------------------------------------------------------ whole weeks
    async newWeek() {
        if (this.state.creating) {
            return;
        }
        this.state.creating = true;
        try {
            const saved = await this.orm.call(MODEL, "save_week", [
                { name: _t("New working week"), weeks: [[false, false, false, false, false, false, false]] },
                false,
            ]);
            this.focusWeek = saved.id;
            this.props.studio.putWeek(saved);
            this.props.studio.refresh();
        } catch (err) {
            this.props.studio.toast(errorText(err), { kind: "error" });
        } finally {
            this.state.creating = false;
        }
    }

    askRemove(row) {
        this.state.confirm = row.id;
        clearTimeout(this.timers.confirm);
        this.timers.confirm = setTimeout(() => {
            delete this.timers.confirm;
            if (this.state.confirm === row.id) {
                this.state.confirm = null;
            }
        }, 5000);
    }

    async remove(row) {
        this.state.confirm = null;
        clearTimeout(this.timers[row.id]);
        delete this.timers[row.id];
        try {
            await this.orm.call(MODEL, "remove_week", [row.id]);
            delete this.state.edits[row.id];
            delete this.state.marks[row.id];
            this.props.studio.dropWeek(row.id);
            this.props.studio.toast(_t("“%s” is removed.", this.nameOf(row)));
            this.props.studio.refresh();
        } catch (err) {
            this.state.errors[row.id] = errorText(err);
        }
    }

    openRotationEditor() {
        this.action.doAction("pb_mission.action_pb_workforce", {
            additionalContext: { pb_shell_lens: "patterns" },
        });
    }

    goShifts() {
        this.props.studio.go("shifts");
    }
}
