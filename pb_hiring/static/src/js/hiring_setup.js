/** @odoo-module **/
/**
 * `pb_hiring_setup` — Hiring set-up, the talent lead's door (RECRUIT P1, G-10).
 *
 * Six cards, each with a status sentence and a way in; the Stages card is
 * live in this phase: rename a stage by clicking its name, drag to reorder,
 * write its one-line meaning, and set which columns a NEW role shows per
 * department and country. "Preview as a board" draws the columns a preset
 * would give, so the choice is seen rather than imagined.
 *
 * Undo, not confirm: a rename, a meaning, a deleted preset all offer Undo for
 * five seconds. The server (`pb.hiring._require_write`) decides who may
 * change anything; `can_edit` only decides what is OFFERED.
 */
import { Component, useState, onWillStart, useRef, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { useSortable } from "@web/core/utils/sortable_owl";

const TOAST_MS = 5000;

export class PbHiringSetup extends Component {
    static template = "pb_hiring.PbHiringSetup";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        if (this.env.config && this.env.config.setDisplayName) {
            this.env.config.setDisplayName(_t("Hiring set-up"));
        }
        this.state = useState({
            loaded: false, data: null, error: "",
            editing: null, editName: "", meanings: {},
            adding: null, previewId: null, toast: null, busy: false,
        });
        this.listRef = useRef("stages");
        useSortable({
            enable: () => !!(this.state.data && this.state.data.can_edit),
            ref: this.listRef,
            elements: ".pbhr-su-row",
            handle: ".pbhr-su-grip",
            cursor: "grabbing",
            placeholderClasses: ["pbhr-su-ph"],
            onDrop: ({ element, previous }) => this.onReorder(element, previous),
        });
        onWillStart(() => this.load());
        onWillUnmount(() => clearTimeout(this._toastTimer));
    }

    ic(n, s = 16) { return ic(n, s); }

    async load() {
        try {
            const data = await this.orm.call("pb.hiring", "get_setup", []);
            const meanings = {};
            for (const st of data.stages) { meanings[st.id] = st.meaning; }
            Object.assign(this.state, { data, meanings, loaded: true, error: "" });
        } catch (e) {
            this.state.loaded = true;
            this.state.error = (e && e.data && e.data.message) || _t("Hiring set-up could not be read.");
        }
    }

    async call(verb, payload, { undo = null } = {}) {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.hiring", "act", [verb, payload]);
            await this.load();
            if (res && res.note) { this.toast(res.note, undo ? () => undo(res) : null); }
            return res;
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
            await this.load();
            return null;
        } finally {
            this.state.busy = false;
        }
    }

    toast(text, undo) {
        clearTimeout(this._toastTimer);
        this.state.toast = { text, undo };
        this._toastTimer = setTimeout(() => { this.state.toast = null; }, TOAST_MS);
    }

    async runUndo() {
        const t = this.state.toast;
        this.state.toast = null;
        clearTimeout(this._toastTimer);
        if (t && t.undo) { await t.undo(); }
    }

    // ------------------------------------------------------------ stages
    get stages() { return (this.state.data && this.state.data.stages) || []; }

    get openStages() { return this.stages.filter((s) => s.family !== "closed"); }

    get closedStages() { return this.stages.filter((s) => s.family === "closed"); }

    /** The columns a preset decides: open stages that are not always on. */
    get optionalStages() { return this.stages.filter((s) => s.family === "open" && !s.always_on); }

    get alwaysOnNames() {
        return this.stages.filter((s) => s.always_on && s.family !== "closed").map((s) => s.name).join(", ");
    }

    familyLabel(fam) {
        return { open: _t("Working column"), done: _t("Done"), closed: _t("Closed outcome") }[fam] || "";
    }

    get rolesCountLabel() {
        const n = (this.state.data && this.state.data.roles_count) || 0;
        return n === 1 ? _t("Used by 1 role") : _t("Used by %s roles", n);
    }

    get previewTitle() { return _t("A new role from %s would show these columns", this.previewName); }

    cellTitle(preset, st) {
        return this.has(preset, st) ? _t("Shown: %s", st.name) : _t("Hidden: %s", st.name);
    }

    get renameTitle() { return this.state.data && this.state.data.can_edit ? _t("Click to rename") : ""; }

    usedBy(st) {
        const n = st.roles_using || 0;
        return n === 1 ? _t("Used by 1 role") : _t("Used by %s roles", n);
    }

    startRename(st) {
        if (!this.state.data.can_edit) { return; }
        this.state.editing = st.id;
        this.state.editName = st.name;
    }

    async saveRename(st) {
        // Enter saves and removes the input, which then fires blur: the
        // second call must see that this rename is already done.
        if (this.state.editing !== st.id) { return; }
        const name = (this.state.editName || "").trim();
        this.state.editing = null;
        if (!name || name === st.name) { return; }
        await this.call("stage_rename", { stage_id: st.id, name }, {
            undo: (res) => this.call("stage_rename", { stage_id: st.id, name: res.old }),
        });
    }

    onRenameKey(ev, st) {
        if (ev.key === "Enter") { ev.preventDefault(); this.saveRename(st); }
        if (ev.key === "Escape") { ev.preventDefault(); this.state.editing = null; }
    }

    async saveMeaning(st) {
        const meaning = (this.state.meanings[st.id] || "").trim();
        if (meaning === (st.meaning || "")) { return; }
        await this.call("stage_meaning", { stage_id: st.id, meaning }, {
            undo: (res) => this.call("stage_meaning", { stage_id: st.id, meaning: res.old }),
        });
    }

    async onReorder(element, previous) {
        const id = Number(element.dataset.id);
        const moving = this.stages.find((s) => s.id === id);
        if (!moving) { return; }
        const prevId = previous ? Number(previous.dataset.id) : null;
        const prevStage = this.stages.find((s) => s.id === prevId);
        const family = this.stages.filter((s) => s.family === moving.family && s.id !== id);
        let at = 0;
        if (prevStage && prevStage.family === moving.family) {
            at = family.findIndex((s) => s.id === prevId) + 1;
        } else if (prevStage && prevStage.family !== moving.family) {
            at = (["open", "done", "closed"].indexOf(prevStage.family) < ["open", "done", "closed"].indexOf(moving.family)) ? 0 : family.length;
        }
        family.splice(at, 0, moving);
        const others = this.stages.filter((s) => s.family !== moving.family);
        const ids = [...family, ...others].map((s) => s.id);
        const before = this.stages.filter((s) => s.family === moving.family).map((s) => s.id);
        await this.call("stage_reorder", { ids }, {
            undo: () => this.call("stage_reorder", { ids: before }),
        });
    }

    // ----------------------------------------------------------- presets
    get presets() { return (this.state.data && this.state.data.presets) || []; }

    has(preset, st) { return preset.stage_ids.includes(st.id); }

    async toggleCell(preset, st) {
        if (!this.state.data.can_edit) { return; }
        const on = this.has(preset, st);
        const ids = on ? preset.stage_ids.filter((i) => i !== st.id) : [...preset.stage_ids, st.id];
        const before = [...preset.stage_ids];
        await this.call("preset_save", { id: preset.id, stage_ids: ids }, {
            undo: () => this.call("preset_save", { id: preset.id, stage_ids: before }),
        });
    }

    startAdd() { this.state.adding = { department_id: "", country_id: "" }; }

    async saveAdd() {
        const f = this.state.adding;
        if (!f || (!f.department_id && !f.country_id)) {
            this.notif.add(_t("Pick a department, a country, or both."), { type: "warning" });
            return;
        }
        const res = await this.call("preset_save", {
            department_id: Number(f.department_id) || false,
            country_id: Number(f.country_id) || false,
        });
        if (res) { this.state.adding = null; }
    }

    async removePreset(preset) {
        await this.call("preset_delete", { id: preset.id }, {
            undo: (res) => this.call("preset_save", { ...res.saved }),
        });
    }

    // ----------------------------------------------------------- preview
    togglePreview(preset) {
        this.state.previewId = this.state.previewId === preset.id ? null : preset.id;
    }

    get previewColumns() {
        const preset = this.presets.find((p) => p.id === this.state.previewId);
        if (!preset) { return []; }
        return this.stages.filter((s) => s.family !== "closed" && (s.always_on || preset.stage_ids.includes(s.id)));
    }

    get previewName() {
        const preset = this.presets.find((p) => p.id === this.state.previewId);
        return preset ? preset.name : "";
    }

    sampleCount(i) { return [3, 2, 2, 1, 1, 1, 0, 0, 0, 0, 0, 0][i] || 0; }

    sampleCards(i) { return Array.from({ length: this.sampleCount(i) }, (_x, n) => n); }

    // ----------------------------------------------------------- the rest
    async toggleSwitch(key) {
        const on = !this.state.data.switches[key];
        await this.call("set_switch", { key, on }, {
            undo: () => this.call("set_switch", { key, on: !on }),
        });
    }

    async openCard(card) {
        if (card.key === "stages") {
            const el = document.querySelector(".pbhr-su-stages");
            if (el && el.scrollIntoView) { el.scrollIntoView({ behavior: "smooth", block: "start" }); }
            return;
        }
        if (card.key === "automations") {
            const el = document.querySelector(".pbhr-su-switches");
            if (el && el.scrollIntoView) { el.scrollIntoView({ behavior: "smooth", block: "start" }); }
            return;
        }
        if (card.action) { await this.action.doAction(card.action); }
    }

    openBoard() {
        this.action.doAction("pb_lifecycle.action_pb_lifecycle_hub", {
            additionalContext: { pb_lens: "hiring" },
        });
    }
}

registry.category("actions").add("pb_hiring_setup", PbHiringSetup);
