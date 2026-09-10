/** @odoo-module **/

import { Component, useState, useRef, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

import { GROUP_TABS, groupLabel, healthWord } from "./recipe_text";
import { SentenceEditor } from "./sentence_editor";

/**
 * Every pay component, as a list you can read and change.
 *
 * The list is the whole configuration in one place: five groups, a search that
 * reaches across all of them, a checkbox that takes a component out and a tray
 * that puts it back, and a Configure button that opens the sentence behind any
 * row. Multi-select, shift-click ranges, arrow keys, Space and Enter — because
 * thirty-eight rows is a lot of clicking one at a time.
 *
 * Nothing here decides anything. Whether a component may be removed, whether a
 * formula is valid, what a rule pays — every one of those answers comes from
 * the server, and this only shows it.
 */
export class ComponentsTab extends Component {
    static template = "pb_blueprint.ComponentsTab";
    static components = { SentenceEditor };
    static props = {
        configId: { type: Number },
        revision: { type: Number, optional: true },
        sampleId: { type: [Number, Boolean], optional: true },
        sampleName: { type: String, optional: true },
        currency: { type: String, optional: true },
        onChanged: { type: Function },       // something was saved -> refresh the hero
        onRevision: { type: Function },
        onGrid: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.searchRef = useRef("search");
        this.listRef = useRef("list");

        this.state = useState({
            loading: true,
            error: "",
            groups: {},
            removed: [],
            counts: { included: 0, removed: 0 },
            group: "earning",
            query: "",
            selected: [],
            focus: 0,
            trayOpen: false,
            busy: false,
            rowError: {},           // {rule_id: "why this one refused"}
            editor: null,           // {ruleId} or {ruleId: false, group}
            confirmRemove: null,    // {ids, label, custom}
        });

        useHotkey("control+f", () => this.focusSearch(),
                  { bypassEditableProtection: true });

        onWillStart(async () => {
            await this.load();
            this.state.loading = false;
        });
    }

    ic(name, size = 16) { return ic(name, size); }

    get GROUPS() { return GROUP_TABS; }

    async rpc(method, args, kwargs) {
        try {
            return await this.orm.call("pb.blueprint.studio", method,
                                       args || [], kwargs || {});
        } catch (e) {
            const reason = (e && e.data && e.data.message) || (e && e.message) || "";
            this.notif.add(reason || _t("The server could not be reached."),
                           { type: "danger" });
            return { ok: false, reason };
        }
    }

    async load(sampleId) {
        const res = await this.rpc("bp_components",
                                   [this.props.configId, sampleId || this.props.sampleId || false]);
        if (!res || !res.ok) {
            this.state.error = (res && res.reason)
                || _t("The components could not be loaded.");
            return;
        }
        this.state.groups = res.groups || {};
        this.state.removed = res.removed || [];
        this.state.counts = res.counts || { included: 0, removed: 0 };
        this.state.error = "";
        this.state.trayOpen = this.state.trayOpen
            || (!this.state.counts.included && this.state.removed.length > 0);
        if (res.revision !== undefined) this.props.onRevision(res.revision);
        // If the group you were on has emptied, move to the first that has rows.
        if (!this.rowsIn(this.state.group).length) {
            const first = GROUP_TABS.find((g) => this.rowsIn(g.key).length);
            if (first) this.state.group = first.key;
        }
    }

    // ==================================================================
    // Reading the list
    // ==================================================================
    rowsIn(group) { return this.state.groups[group] || []; }

    countIn(group) { return this.rowsIn(group).length; }

    get matching() {
        const query = (this.state.query || "").trim().toLowerCase();
        if (!query) return this.rowsIn(this.state.group);
        const all = [];
        for (const tab of GROUP_TABS) {
            for (const row of this.rowsIn(tab.key)) all.push(row);
        }
        return all.filter((r) =>
            (r.name || "").toLowerCase().includes(query)
            || (r.code || "").toLowerCase().includes(query)
            || (r.summary || "").toLowerCase().includes(query));
    }

    get searching() { return !!(this.state.query || "").trim(); }

    get chipLine() {
        const included = this.state.counts.included || 0;
        const removed = this.state.counts.removed || 0;
        const left = included === 1 ? _t("1 included") : _t("%s included", included);
        if (!removed) return left;
        const right = removed === 1 ? _t("1 removed") : _t("%s removed", removed);
        return `${left} · ${right}`;
    }

    get trayLine() {
        const n = this.state.removed.length;
        return n === 1
            ? _t("1 removed from this configuration")
            : _t("%s removed from this configuration", n);
    }

    groupLabel(key) { return groupLabel(key); }
    healthWord(health) { return healthWord(health); }

    healthTitle(row) {
        return `${healthWord(row.health)} — ${row.health_text || ""}`;
    }

    valueOf(row) {
        if (row.value === null || row.value === undefined) return "—";
        return Number(row.value).toLocaleString("en-US", { maximumFractionDigits: 0 });
    }

    get emptyLine() {
        if (this.searching) {
            return _t("Nothing matches “%s”.", this.state.query.trim());
        }
        return _t("No components yet. Add your first one, or change the "
                  "starting point on the Start step.");
    }

    // ==================================================================
    // Selection, keyboard
    // ==================================================================
    isSelected(id) { return this.state.selected.includes(id); }

    onRowClick(row, ev) {
        const ids = this.matching.map((r) => r.id);
        const index = ids.indexOf(row.id);
        this.state.focus = index;
        if (ev.shiftKey && this.state.selected.length) {
            const last = ids.indexOf(this.state.selected[this.state.selected.length - 1]);
            const [from, to] = last < index ? [last, index] : [index, last];
            const range = ids.slice(from, to + 1);
            this.state.selected = [...new Set([...this.state.selected, ...range])];
            return;
        }
        if (ev.metaKey || ev.ctrlKey) {
            this.toggleSelect(row.id);
            return;
        }
        this.state.selected = this.isSelected(row.id) && this.state.selected.length === 1
            ? [] : [row.id];
    }

    toggleSelect(id) {
        this.state.selected = this.isSelected(id)
            ? this.state.selected.filter((x) => x !== id)
            : [...this.state.selected, id];
    }

    clearSelection() { this.state.selected = []; }

    onListKeydown(ev) {
        const rows = this.matching;
        if (!rows.length) return;
        if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault();
            const step = ev.key === "ArrowDown" ? 1 : -1;
            this.state.focus = Math.max(0, Math.min(rows.length - 1,
                                                    this.state.focus + step));
            this.focusRow(this.state.focus);
            return;
        }
        const row = rows[this.state.focus];
        if (!row) return;
        if (ev.key === " " || ev.key === "Spacebar") {
            ev.preventDefault();
            if (!row.locked) this.onToggleInclude(row);
            return;
        }
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.openEditor(row.id);
            return;
        }
        if (ev.key === "Escape" && this.state.selected.length) {
            ev.preventDefault();
            this.clearSelection();
        }
    }

    focusRow(index) {
        const el = this.listRef.el
            && this.listRef.el.querySelectorAll(".pbbp-cmp-row")[index];
        if (el) el.focus();
    }

    focusSearch() {
        if (this.searchRef.el) this.searchRef.el.focus();
    }

    onSearch(ev) {
        this.state.query = ev.target.value;
        this.state.focus = 0;
    }

    clearSearch() {
        this.state.query = "";
        this.focusSearch();
    }

    // ==================================================================
    // Include / exclude
    // ==================================================================
    async onToggleInclude(row) {
        if (row.locked) return;
        await this.remove([row.id], row.name, row.template_key);
    }

    async onBulkRemove() {
        const rows = this.matching.filter((r) => this.isSelected(r.id) && !r.locked);
        if (!rows.length) return;
        await this.remove(rows.map((r) => r.id),
                          rows.map((r) => r.name).join(", "),
                          rows.every((r) => r.template_key));
    }

    async remove(ids, label, fromStarter) {
        // A component that came from the starter can always come back, so it
        // goes without a question. One somebody added themselves cannot, so it
        // is worth a sentence first.
        if (!fromStarter && !this.state.confirmRemove) {
            this.state.confirmRemove = { ids, label };
            return;
        }
        this.state.confirmRemove = null;
        this.state.busy = true;
        const res = await this.rpc("bp_component_exclude",
                                   [this.props.configId, ids, false, this.props.revision]);
        this.state.busy = false;
        if (!res || !res.ok) {
            // The reason belongs ON THE ROW, not in a toast that floats away
            // from the thing it is about.
            const first = ids[0];
            this.state.rowError = { ...this.state.rowError,
                                    [first]: (res && res.reason) || _t("This could not be removed.") };
            if (res && res.conflict) this.props.onChanged({ conflict: true });
            return;
        }
        this.state.rowError = {};
        this.state.selected = [];
        if (res.revision !== undefined) this.props.onRevision(res.revision);
        await this.load();
        this.props.onChanged(res);
        this.notify(res.removed.length === 1
            ? _t("%s was removed. You can restore it from the tray below.", label)
            : _t("%s components were removed.", res.removed.length));
    }

    async onRestore(code) {
        this.state.busy = true;
        const res = await this.rpc("bp_component_include",
                                   [this.props.configId, code, this.props.revision]);
        this.state.busy = false;
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("That component could not be restored."),
                           { type: "warning" });
            return;
        }
        if (res.revision !== undefined) this.props.onRevision(res.revision);
        await this.load();
        this.props.onChanged(res);
        this.notify(_t("%s is back.", code));
    }

    async onRestoreAll() {
        for (const row of [...this.state.removed]) {
            await this.onRestore(row.code);
        }
    }

    notify(message) {
        this.notif.add(message, { type: "success" });
    }

    // ==================================================================
    // The editor
    // ==================================================================
    openEditor(ruleId) {
        this.state.editor = { ruleId, group: this.state.group };
    }

    openNew() {
        const group = ["earning", "deduction", "benefit"].includes(this.state.group)
            ? this.state.group : "earning";
        this.state.editor = { ruleId: false, group };
    }

    closeEditor() { this.state.editor = null; }

    get takenCodes() {
        const out = [];
        for (const tab of GROUP_TABS) {
            for (const row of this.rowsIn(tab.key)) out.push(row.code);
        }
        return out;
    }

    async onEditorSaved(res) {
        this.state.editor = null;
        if (res && res.revision !== undefined) this.props.onRevision(res.revision);
        await this.load();
        this.props.onChanged(res);
        if (res && res.problems && res.problems.length) {
            this.notif.add(
                _t("Saved, but %(code)s still has a problem: %(why)s",
                   { code: res.problems[0].code, why: res.problems[0].message }),
                { type: "warning", sticky: true });
            return;
        }
        this.notify(_t("Saved. The pay panel has been brought up to date."));
    }

    async onEditorRemoved(ruleId, label) {
        this.state.editor = null;
        const row = this.findRow(ruleId);
        await this.remove([ruleId], label, row && row.template_key);
    }

    findRow(id) {
        for (const tab of GROUP_TABS) {
            const hit = this.rowsIn(tab.key).find((r) => r.id === id);
            if (hit) return hit;
        }
        return null;
    }

    // ==================================================================
    // Regenerate everything
    // ==================================================================
    async onRegenerate() {
        this.state.busy = true;
        const res = await this.rpc("bp_regenerate",
                                   [this.props.configId, this.props.revision]);
        this.state.busy = false;
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("The rules could not be worked out again."),
                           { type: "warning" });
            return;
        }
        if (res.revision !== undefined) this.props.onRevision(res.revision);
        await this.load();
        this.props.onChanged(res);
        this.notify(res.changed.length
            ? _t("%s calculations were brought up to date.", res.changed.length)
            : _t("Everything was already up to date."));
    }
}
