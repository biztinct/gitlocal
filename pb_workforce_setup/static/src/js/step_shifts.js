/** @odoo-module **/
/**
 * Step 1 — "What shifts do you run?"
 *
 * Editing happens in place on a LOCAL draft: the 24-hour bar, the times and
 * the paid-hours line follow every keystroke. The row button reads Save when
 * the draft differs from what is stored and Done when it does not; Cancel
 * restores. Opening another row, adding a shift or leaving the step saves an
 * unsaved draft first, and a refused save keeps the row open with the
 * server's sentence under the fields.
 */
import { Component, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { MODEL, icon, barParts, spanOf, endsNextDay, hrs, toMin, errorText, timeRange } from "./setup_util";

const FIELDS = ["name", "start", "end", "break_minutes", "color"];

export class StepShifts extends Component {
    static template = "pb_workforce_setup.StepShifts";
    static props = { studio: Object, data: Object };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            open: null,          // row id, or "new"
            drafts: {},          // id -> {name, start, end, break_minutes, color}
            errors: {},          // id -> sentence
            saving: null,        // id being saved
            confirm: null,       // id whose Remove asks "for good?"
            newRow: null,        // the starter row, not yet stored
        });
        this.icon = icon;
        this.range = timeRange;
        this.nameRef = useRef("shiftName");
        useEffect(
            (open) => {
                if (open !== null && this.focusName && this.nameRef.el) {
                    this.focusName = false;
                    this.nameRef.el.focus();
                    this.nameRef.el.select();
                }
            },
            () => [this.state.open]
        );
        this.unguard = this.props.studio.addGuard(() => this.flush());
        onWillUnmount(() => {
            this.unguard();
            clearTimeout(this.confirmTimer);
        });
    }

    // ------------------------------------------------------------ rows
    get canEdit() { return this.props.data.can_edit; }
    get colors() { return this.props.data.colors; }
    get rows() {
        const rows = [...this.props.data.shifts];
        if (this.state.newRow) {
            rows.push({ id: "new", used_weeks: 0, shared: false, ...this.state.newRow });
        }
        return rows;
    }
    get starters() {
        return [
            { key: "morning", label: _t("Morning 06:00 to 14:00"), name: _t("Morning"), start: "06:00", end: "14:00", break_minutes: 30 },
            { key: "afternoon", label: _t("Afternoon 14:00 to 22:00"), name: _t("Afternoon"), start: "14:00", end: "22:00", break_minutes: 30 },
            { key: "night", label: _t("Night 22:00 to 06:00"), name: _t("Night"), start: "22:00", end: "06:00", break_minutes: 30 },
            { key: "blank", label: _t("Start from blank"), name: _t("New shift"), start: "08:00", end: "17:00", break_minutes: 60, blank: true },
        ];
    }

    view(row) {
        return this.state.drafts[row.id] || row;
    }
    isOpen(row) { return this.state.open === row.id; }
    isDirty(row) {
        if (row.id === "new") {
            return true;
        }
        const d = this.state.drafts[row.id];
        return !!d && FIELDS.some((f) => String(d[f]) !== String(row[f]));
    }
    isNight(row) {
        const v = this.view(row);
        const a = toMin(v.start);
        return endsNextDay(v.start, v.end) || (a !== null && a >= 18 * 60);
    }
    bar(row) {
        const v = this.view(row);
        return barParts(v.start, v.end, v.break_minutes);
    }
    paid(row) {
        const v = this.view(row);
        return hrs(Math.max(0, spanOf(v.start, v.end) - (Number(v.break_minutes) || 0)));
    }
    breakText(row) {
        const b = Number(this.view(row).break_minutes) || 0;
        return b ? _t("%s min break", b) : _t("no break");
    }
    nextDay(row) {
        const v = this.view(row);
        return endsNextDay(v.start, v.end);
    }
    usedText(row) {
        const n = row.used_weeks || 0;
        if (!n) {
            return row.used_roster ? _t("Not in a working week") : _t("Not used yet");
        }
        return n === 1 ? _t("Used in 1 working week") : _t("Used in %s working weeks", n);
    }
    toneClass(row) { return `pbws-c-${this.view(row).color || "indigo"}`; }
    colorLabel(name) {
        const labels = {
            indigo: _t("Indigo"), teal: _t("Teal"), amber: _t("Amber"),
            blue: _t("Blue"), rose: _t("Rose"), green: _t("Green"),
        };
        return labels[name] || name;
    }

    // ------------------------------------------------------------ editing
    async toggle(row) {
        if (this.isOpen(row)) {
            if (this.isDirty(row)) {
                await this.save(row);
                return;
            }
            this.state.open = null;
            return;
        }
        if (!(await this.flush())) {
            return;
        }
        this.state.open = row.id;
        this.state.confirm = null;
    }

    draft(row) {
        if (!this.state.drafts[row.id]) {
            const base = row.id === "new" ? this.state.newRow : row;
            this.state.drafts[row.id] = Object.fromEntries(FIELDS.map((f) => [f, base[f]]));
        }
        return this.state.drafts[row.id];
    }

    onInput(row, field, ev) {
        const d = this.draft(row);
        let value = ev.target.value;
        if (field === "break_minutes") {
            value = Math.max(0, parseInt(value, 10) || 0);
        } else if ((field === "start" || field === "end") && !value) {
            return;         // a half-typed time keeps the last good one
        }
        d[field] = value;
        if (row.id === "new") {
            this.state.newRow[field] = value;
        }
        delete this.state.errors[row.id];
    }

    pickColor(row, name) {
        this.draft(row).color = name;
        if (row.id === "new") {
            this.state.newRow.color = name;
        }
    }

    onKey(row, ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.save(row);
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            this.cancel(row);
        }
    }

    cancel(row) {
        delete this.state.drafts[row.id];
        delete this.state.errors[row.id];
        if (row.id === "new") {
            this.state.newRow = null;
            this.state.open = null;
        }
    }

    /** Save the open draft. Resolves true when nothing is left unsaved. */
    async save(row) {
        if (!this.isDirty(row)) {
            return true;
        }
        const v = this.view(row);
        const vals = { name: v.name, start: v.start, end: v.end, break_minutes: Number(v.break_minutes) || 0 };
        if (row.id === "new" || v.color !== row.color) {
            vals.color = v.color;
        }
        this.state.saving = row.id;
        try {
            const saved = await this.orm.call(MODEL, "save_shift", [vals, row.id === "new" ? false : row.id]);
            delete this.state.drafts[row.id];
            delete this.state.errors[row.id];
            if (row.id === "new") {
                this.state.newRow = null;
                delete this.state.drafts.new;
            }
            this.props.studio.putShift(saved);
            if (this.state.open === row.id) {
                this.state.open = saved.id;
            }
            this.props.studio.refresh();
            return true;
        } catch (e) {
            this.state.errors[row.id] = errorText(e);
            this.state.open = row.id;
            return false;
        } finally {
            this.state.saving = null;
        }
    }

    /** The leave guard: save the open row if it has changes. */
    async flush() {
        const open = this.state.open;
        if (open === null) {
            return true;
        }
        const row = this.rows.find((r) => r.id === open);
        return row ? this.save(row) : true;
    }

    async addStarter(starter) {
        if (!(await this.flush())) {
            return;
        }
        const n = this.props.data.shifts.length;
        this.state.newRow = {
            name: starter.name, start: starter.start, end: starter.end,
            break_minutes: starter.break_minutes,
            color: this.colors[n % this.colors.length].name,
        };
        delete this.state.drafts.new;
        this.state.open = "new";
        this.focusName = true;
    }

    async copy(row) {
        if (!(await this.flush())) {
            return;
        }
        try {
            const saved = await this.orm.call(MODEL, "copy_shift", [row.id]);
            this.props.studio.putShift(saved);
            this.focusName = true;
            this.state.open = saved.id;
            this.props.studio.refresh();
        } catch (e) {
            this.state.errors[row.id] = errorText(e);
        }
    }

    askRemove(row) {
        this.state.confirm = row.id;
        clearTimeout(this.confirmTimer);
        this.confirmTimer = setTimeout(() => {
            if (this.state.confirm === row.id) {
                this.state.confirm = null;
            }
        }, 5000);
    }

    async remove(row) {
        this.state.confirm = null;
        try {
            const res = await this.orm.call(MODEL, "remove_shift", [row.id]);
            delete this.state.drafts[row.id];
            delete this.state.errors[row.id];
            this.state.open = null;
            this.props.studio.dropShift(row.id);
            this.notification.add(
                res.archived
                    ? _t("“%s” is hidden from your shifts. Past roster days keep it.", row.name)
                    : _t("“%s” is removed.", row.name),
                { type: "success" }
            );
            this.props.studio.refresh();
        } catch (e) {
            this.state.errors[row.id] = errorText(e);
        }
    }

    goWeeks() {
        this.props.studio.go("weeks");
    }
}
