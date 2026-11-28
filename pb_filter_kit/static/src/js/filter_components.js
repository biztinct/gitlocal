/** @odoo-module **/
/**
 * The filter panel's pieces. A screen only ever uses PbFilterLayout:
 *
 *   <PbFilterLayout kit="kit" searchPlaceholder="…">
 *       <t t-set-slot="toolbar">…extra buttons…</t>
 *       …the list…
 *   </PbFilterLayout>
 *
 * Every child takes the kit as a prop and re-wraps it with useState, so it
 * re-renders on exactly the parts of the model it reads.
 */
import { Component, onPatched, useExternalListener, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { fmtCount, pbfIcon } from "./filter_kit";

const LIST_TYPES = new Set(["many2one", "selection", "char", "choice"]);
const FEW = 6;

function isTyping(el) {
    return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

class PbfBase extends Component {
    static props = ["*"];
    setup() {
        this.kit = useState(this.props.kit);
    }
    icon(name, size = 16) {
        return pbfIcon(name, size);
    }
    fmt(n) {
        return fmtCount(n);
    }
}

// ================================================================= views
export class PbFilterViews extends PbfBase {
    static template = "pb_filter_kit.Views";
    setup() {
        super.setup();
        this.root = useRef("root");
        this.pop = useState({ open: "", name: "", shared: false, confirm: false, busy: false });
        useExternalListener(window, "mousedown", (ev) => {
            if (this.pop.open && this.root.el && !this.root.el.contains(ev.target)) {
                this.close();
            }
        });
        onPatched(() => {
            const input = this.root.el && this.root.el.querySelector(".pbf-pop input[autofocus]");
            if (input && this._focusPending) {
                this._focusPending = false;
                input.focus();
                input.select();
            }
        });
    }
    get showRow() {
        return this.kit.views.length > 1 || this.kit.dirty;
    }
    isDirtyTab(v) {
        return v.key === this.kit.viewKey && this.kit.dirty;
    }
    tabTitle(v) {
        if (v.owner) {
            return _t("Shared by %s", v.owner);
        }
        if (v.mine && v.shared) {
            return _t("Your view, shared with everyone");
        }
        if (v.mine) {
            return _t("Your view, only you can see it");
        }
        return "";
    }
    openSave() {
        Object.assign(this.pop, { open: "save", name: "", shared: false, confirm: false });
        this._focusPending = true;
    }
    openManage() {
        const v = this.kit.currentView;
        Object.assign(this.pop, { open: "manage", name: v ? v.label : "", shared: !!(v && v.shared), confirm: false });
        this._focusPending = true;
    }
    close() {
        Object.assign(this.pop, { open: "", confirm: false, busy: false });
    }
    async submitSave(ev) {
        ev && ev.preventDefault();
        if (!this.pop.name.trim() || this.pop.busy) {
            return;
        }
        this.pop.busy = true;
        const ok = await this.kit.saveView(this.pop.name.trim(), this.pop.shared);
        this.pop.busy = false;
        if (ok) {
            this.close();
        }
    }
    async submitRename(ev) {
        ev && ev.preventDefault();
        const v = this.kit.currentView;
        if (!v || !this.pop.name.trim() || this.pop.name.trim() === v.label) {
            return;
        }
        this.pop.busy = true;
        await this.kit.renameView(v.key, this.pop.name.trim());
        this.pop.busy = false;
    }
    async toggleShare() {
        const v = this.kit.currentView;
        if (v) {
            await this.kit.shareView(v.key, !v.shared);
            this.pop.shared = !!(this.kit.currentView && this.kit.currentView.shared);
        }
    }
    async doDelete() {
        const v = this.kit.currentView;
        if (v) {
            await this.kit.deleteView(v.key);
        }
        this.close();
    }
    setConfirm(on) {
        this.pop.confirm = on;
    }
    onPopKey(ev) {
        if (ev.key === "Escape") {
            this.close();
        }
    }
}

// ================================================================== sort
export class PbFilterSort extends PbfBase {
    static template = "pb_filter_kit.Sort";
    setup() {
        super.setup();
        this.root = useRef("root");
        this.st = useState({ open: false });
        useExternalListener(window, "mousedown", (ev) => {
            if (this.st.open && this.root.el && !this.root.el.contains(ev.target)) {
                this.st.open = false;
            }
        });
    }
    toggle() {
        this.st.open = !this.st.open;
    }
    get current() {
        return this.kit.sorts.find((s) => s.key === this.kit.sort) || this.kit.sorts[0];
    }
    pick(key) {
        this.st.open = false;
        this.kit.setSort(key);
    }
}

// ================================================================= panel
export class PbFilterPanel extends PbfBase {
    static template = "pb_filter_kit.Panel";
    setup() {
        super.setup();
        this.root = useRef("root");
        onPatched(() => {
            const key = this.kit.ui.flash;
            if (key && key !== this._flashed && this.root.el) {
                this._flashed = key;
                // scroll the panel only: scrollIntoView would move the page too
                const box = this.root.el.querySelector(".pbf-panel-in");
                const el = this.root.el.querySelector(`[data-pbf-key="${key}"]`);
                if (box && el) {
                    const head = box.querySelector(".pbf-ph");
                    const top = el.offsetTop - (head ? head.offsetHeight : 0) - 8;
                    box.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
                }
            }
            if (!key) {
                this._flashed = null;
            }
        });
    }
    get groupLabels() {
        return Object.fromEntries(this.kit.groups.map((g) => [g.key, g.label]));
    }
    /** Pinned sections first, then "More filters"; while finding, matches only. */
    get blocks() {
        const kit = this.kit;
        const finding = !!kit.ui.find.trim();
        const all = kit.panelSections.filter((s) => kit.matchesFind(s));
        if (finding) {
            return all.map((s) => ({ key: s.key, section: s }));
        }
        const pinned = all.filter((s) => kit.isPinned(s.key));
        const rest = all.filter((s) => !kit.isPinned(s.key));
        const out = pinned.map((s) => ({ key: s.key, section: s }));
        if (rest.length) {
            out.push({ key: "__more", divider: true, label: pinned.length ? _t("More filters") : _t("All filters") });
            out.push(...rest.map((s) => ({ key: s.key, section: s })));
        }
        return out;
    }
    get findExamples() {
        const names = this.kit.panelSections.slice(0, 2).map((s) => s.label);
        return names.join(_t(" or "));
    }

    // ---- one section, ready for the template
    view(s) {
        const kit = this.kit;
        const c = kit.counts[s.key];
        const open = kit.isOpen(s.key);
        const active = kit.isActive(s.key);
        const v = {
            key: s.key,
            label: s.label,
            icon: s.icon || "filter",
            help: s.help || "",
            type: s.type,
            open,
            active,
            pinned: kit.isPinned(s.key),
            flash: kit.ui.flash === s.key,
            nActive: Array.isArray(kit.filters[s.key]) ? kit.filters[s.key].length : active ? 1 : 0,
            summary: active ? kit.summary(s.key) : "",
            loading: open && !c,
            failed: !!(c && c.error),
        };
        if (!open || !c || c.error) {
            return v;
        }
        if (LIST_TYPES.has(s.type)) {
            const all = kit.rowsFor(s.key);
            const finding = !!kit.ui.find.trim() || !!(kit.ui.mini[s.key] || "").trim();
            const expanded = !!kit.ui.showAll[s.key];
            const limit = expanded || finding ? all.length : FEW;
            v.rows = all.slice(0, limit).map((r) => ({ ...r, on: kit.isOn(s.key, r.v) }));
            v.hiddenCount = all.length - v.rows.length;
            v.expanded = expanded && all.length > FEW;
            v.searchable = (c.values || []).length > 12 && !kit.ui.find.trim();
            v.mini = kit.ui.mini[s.key] || "";
            v.serverMore = !!c.more;
            v.empty = !all.length;
            v.tone = s.type === "choice";
        } else if (s.type === "date") {
            const cur = kit.filters[s.key] || {};
            v.presets = (c.presets || []).map((p) => ({ ...p, on: cur.preset === p.v }));
            v.custom = !!(cur.from || cur.to) || !!kit.ui.custom[s.key];
            v.from = cur.from || "";
            v.to = cur.to || "";
        } else if (s.type === "number") {
            const cur = kit.filters[s.key] || {};
            v.min = cur.min ?? "";
            v.max = cur.max ?? "";
            v.lo = c.min;
            v.hi = c.max;
            const grouped = (n) => (n === "" || n === null || n === undefined ? "" : Math.round(Number(n)).toLocaleString("en-US"));
            v.minText = grouped(v.min);
            v.maxText = grouped(v.max);
            v.loPh = c.min !== null && c.min !== undefined ? grouped(Math.floor(c.min)) : "";
            v.hiPh = c.max !== null && c.max !== undefined ? grouped(Math.ceil(c.max)) : "";
            v.loText = c.min !== null && c.min !== undefined ? kit.fmtNumber(c.min, s.unit) : "";
            v.hiText = c.max !== null && c.max !== undefined ? kit.fmtNumber(c.max, s.unit) : "";
            v.prefix = s.unit === "money" ? kit.extra.currency || "" : "";
        }
        return v;
    }

    pinTitle(v) {
        return v.pinned ? _t("Unpin: move it under More filters") : _t("Pin it to the top");
    }
    miniPlaceholder(v) {
        return _t("Find in %s…", v.label.toLowerCase());
    }
    onPresetKey(ev, key, preset, custom) {
        if (ev.key !== " " && ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        if (preset) {
            this.kit.setPreset(key, preset);
        } else {
            this.kit.setCustom(key, custom);
        }
    }
    /** A mouse press must not move focus: focusing a row inside the sticky
     * panel made the whole page jump to it. Keyboard focus is untouched. */
    noFocusJump(ev) {
        ev.preventDefault();
    }
    onValueKey(ev, key, value) {
        if (ev.key === " " || ev.key === "Enter") {
            ev.preventDefault();
            this.kit.toggle(key, value);
        } else if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault();
            const rows = [...ev.currentTarget.parentElement.querySelectorAll(".pbf-val")];
            const i = rows.indexOf(ev.currentTarget);
            const next = rows[i + (ev.key === "ArrowDown" ? 1 : -1)];
            if (next) {
                next.focus();
            }
        }
    }
    onFindKey(ev) {
        if (ev.key === "Escape") {
            this.kit.setFind("");
        } else if (ev.key === "Enter") {
            ev.preventDefault();
            this.kit.pickFirstFound();
        }
    }
    onNumber(key, which, ev) {
        const cur = this.kit.filters[key] || {};
        // typed with or without separators: keep digits and one decimal point
        const raw = ev.target.value.replace(/[^0-9.]/g, "");
        const val = raw === "" ? "" : raw;
        const min = which === "min" ? val : cur.min ?? "";
        const max = which === "max" ? val : cur.max ?? "";
        this.kit.setNumber(key, min, max);
    }
    onRange(key, which, ev) {
        const cur = this.kit.filters[key] || {};
        const from = which === "from" ? ev.target.value : cur.from || "";
        const to = which === "to" ? ev.target.value : cur.to || "";
        if (!from && !to) {
            this.kit.clear(key);
        } else {
            this.kit.setRange(key, from, to);
        }
    }
}

// ================================================================= chips
export class PbFilterChips extends PbfBase {
    static template = "pb_filter_kit.Chips";
    get matchedText() {
        const kit = this.kit;
        if (kit.matched === null || kit.matched === undefined) {
            return "";
        }
        return kit.matched === kit.total
            ? _t("%(n)s %(noun)s", { n: fmtCount(kit.matched), noun: kit.noun })
            : _t("%(n)s of %(total)s %(noun)s", { n: fmtCount(kit.matched), total: fmtCount(kit.total), noun: kit.noun });
    }
    removeLabel(c) {
        return _t("Remove %s", c.label);
    }
    onChipKey(ev, key) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.kit.jumpTo(key);
        } else if (ev.key === "Backspace" || ev.key === "Delete") {
            ev.preventDefault();
            this.kit.clear(key);
        }
    }
}

// ================================================================ layout
export class PbFilterLayout extends PbfBase {
    static template = "pb_filter_kit.Layout";
    static components = { PbFilterViews, PbFilterPanel, PbFilterChips, PbFilterSort };
    setup() {
        super.setup();
        this.searchRef = useRef("search");
        // "/" jumps to the list's search box, as on the best list screens
        useExternalListener(window, "keydown", (ev) => {
            if (ev.key === "/" && !ev.ctrlKey && !ev.metaKey && !ev.altKey && !isTyping(ev.target)
                && this.searchRef.el && document.body.contains(this.searchRef.el)
                && !document.querySelector(".modal.show, .o_dialog")) {
                ev.preventDefault();
                this.searchRef.el.focus();
            }
        });
    }
    get toggleTitle() {
        return this.kit.ui.panel ? _t("Give the list the full width") : _t("Show the filters");
    }
    get placeholder() {
        return this.props.searchPlaceholder || _t("Search…");
    }
    onSearchKey(ev) {
        if (ev.key === "Escape" && this.kit.search) {
            this.kit.setSearch("", true);
        }
    }
    clearSearch() {
        this.kit.setSearch("", true);
        this.searchRef.el && this.searchRef.el.focus();
    }
}
