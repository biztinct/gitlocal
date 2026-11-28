/** @odoo-module **/
/**
 * DocEditor — the Document studio's page editor, a standalone OWL component
 * other screens can reuse (DOCSTUDIO F2).
 *
 * Pattern of the Payslip Studio editor (pb_formula_studio formula_studio.js
 * `psOpenRich` and the `_psRich*` helpers), rebuilt here on its own: a hand-
 * made `contenteditable`, fields shown as non-editable chips, and the body
 * stored as inert text so the server's HTML sanitizer stays on:
 *
 *   field          `${employee_name}` (the letter engine's own grammar)
 *   "Show only     `<div class="pbds-when pbds-r-r1">…</div>` — classes, never
 *    when" block    `data-*` (the sanitizer drops those, ledger DS-1)
 *
 * The parent talks to the editor through the `api` object handed to
 * `onReady`, and reads the toolbar's state from the reactive `ui` prop.
 * `DocToolbar` is the matching toolbar.
 */
import { Component, onMounted, onWillUnmount, onPatched, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { dsIc } from "./doc_icons";
import { esc, modKey } from "./doc_words";

const KEY_RE = /\$\{([_a-zA-Z][_a-zA-Z0-9]*)\}/g;
const RULE_RE = /pbds-r-([a-z][a-z0-9]{0,15})/g;
const ZWSP = "​";
const ALLOWED = new Set(["P", "BR", "B", "STRONG", "I", "EM", "U", "S", "UL", "OL", "LI", "H1", "H2", "H3",
    "H4", "TABLE", "THEAD", "TBODY", "TR", "TD", "TH", "SPAN", "DIV", "BLOCKQUOTE", "IMG", "A", "SUB", "SUP"]);
const BLOCKS = new Set(["P", "DIV", "H1", "H2", "H3", "H4", "UL", "OL", "TABLE", "BLOCKQUOTE"]);
const IMG_SIZES = { s: "120px", m: "240px", l: "360px", full: "100%" };

/** A chip, as HTML. The label is chrome: serialisation keeps only the key. */
export function chipHtml(key, spec) {
    const s = spec || { label: key, missing: true };
    const cls = ["pbds-chip"];
    if (s.pay) { cls.push("is-pay"); }
    if (s.missing) { cls.push("is-missing"); }
    if (s.later) { cls.push("is-later"); }
    const label = s.missing ? _t("Field no longer exists") : (s.label || key);
    const lock = s.pay ? `<span class="pbds-chip-ic">${dsIc("lock", 11)}</span>` : "";
    return `<span class="${cls.join(" ")}" contenteditable="false" data-key="${esc(key)}" title="${esc(s.label || key)}">${lock}${esc(label)}</span>`;
}

export function ruleIds(html) {
    const ids = new Set();
    for (const m of String(html || "").matchAll(RULE_RE)) { ids.add(m[1]); }
    return ids;
}

export class DocEditor extends Component {
    static template = "pb_doc_studio.DocEditor";
    static props = {
        html: { type: String },
        fields: { type: Object },
        sentences: { type: Object, optional: true },
        values: { type: Object, optional: true },
        ui: { type: Object, optional: true },
        onChange: { type: Function },
        onReady: { type: Function, optional: true },
        onRule: { type: Function, optional: true },
        onPick: { type: Function, optional: true },
        onUpload: { type: Function, optional: true },
        hint: { type: String, optional: true },
    };

    setup() {
        this.body = useRef("body");
        this.wrap = useRef("wrap");
        this.pills = useState({ list: [] });
        this.hist = [];
        this.pos = -1;
        this.range = null;
        this._recordTimer = null;
        this._pillTimer = null;
        this.onSelection = () => this.trackSelection();
        this.onResize = () => this.schedulePills();
        onMounted(() => {
            this.setHtml(this.props.html || "", true);
            document.addEventListener("selectionchange", this.onSelection);
            window.addEventListener("resize", this.onResize);
            if (this.props.onReady) { this.props.onReady(this.api); }
        });
        onPatched(() => this.schedulePills());
        onWillUnmount(() => {
            document.removeEventListener("selectionchange", this.onSelection);
            window.removeEventListener("resize", this.onResize);
            clearTimeout(this._recordTimer);
            clearTimeout(this._pillTimer);
        });
        this.api = {
            insertField: (key) => this.insertField(key),
            command: (cmd, value) => this.command(cmd, value),
            block: (tag) => this.command("formatBlock", tag),
            showOnlyWhen: () => this.showOnlyWhen(),
            unwrapRule: (id) => this.unwrapRule(id),
            undo: () => this.undo(),
            redo: () => this.redo(),
            insertTable: () => this.insertTable(),
            table: (op) => this.tableOp(op),
            insertImage: (url, name) => this.insertImage(url, name),
            imageSize: (size) => this.imageSize(size),
            removeField: (key) => this.removeField(key),
            getHtml: () => this.serialize(),
            focus: () => this.focusEnd(),
            refreshChips: () => this.refreshChips(),
            caretRect: () => this.caretRect(),
            remember: () => this.trackSelection(),
            refreshPills: () => this.schedulePills(),
        };
    }

    ic(n, s = 13) { return dsIc(n, s); }
    get ui() { return this.props.ui || {}; }

    // ---------------------------------------------------------- content
    expand(html) {
        const tpl = document.createElement("template");
        tpl.innerHTML = html || "";
        const walker = document.createTreeWalker(tpl.content, NodeFilter.SHOW_TEXT);
        const hits = [];
        while (walker.nextNode()) {
            if (KEY_RE.test(walker.currentNode.nodeValue)) { hits.push(walker.currentNode); }
            KEY_RE.lastIndex = 0;
        }
        for (const node of hits) {
            const text = node.nodeValue;
            const frag = document.createDocumentFragment();
            let last = 0;
            for (const m of text.matchAll(KEY_RE)) {
                if (m.index > last) { frag.append(document.createTextNode(text.slice(last, m.index))); }
                const holder = document.createElement("template");
                holder.innerHTML = chipHtml(m[1], this.props.fields[m[1]]);
                frag.append(holder.content);
                last = m.index + m[0].length;
            }
            if (last < text.length) { frag.append(document.createTextNode(text.slice(last))); }
            node.replaceWith(frag);
        }
        if (!tpl.content.childNodes.length) {
            tpl.innerHTML = "<p><br></p>";
        }
        return tpl.innerHTML;
    }

    serialize() {
        const el = this.body.el;
        if (!el) { return ""; }
        const clone = el.cloneNode(true);
        for (const chip of clone.querySelectorAll(".pbds-chip")) {
            chip.replaceWith(document.createTextNode("${" + chip.dataset.key + "}"));
        }
        for (const node of clone.querySelectorAll("*")) {
            for (const attr of [...node.attributes]) {
                if (attr.name.startsWith("data-") || attr.name === "contenteditable") {
                    node.removeAttribute(attr.name);
                }
            }
            node.classList.remove("pbds-img-sel", "pbds-cell-sel");
            if (node.getAttribute("class") === "") { node.removeAttribute("class"); }
        }
        let html = clone.innerHTML.replaceAll(ZWSP, "");
        if (html === "<p><br></p>" || html === "<br>") { html = ""; }
        return html;
    }

    setHtml(html, resetHistory = false) {
        const el = this.body.el;
        if (!el) { return; }
        el.innerHTML = this.expand(html);
        if (resetHistory) {
            this.hist = [this.serialize()];
            this.pos = 0;
        }
        this.schedulePills();
    }

    refreshChips() {
        const el = this.body.el;
        if (!el) { return; }
        for (const chip of el.querySelectorAll(".pbds-chip")) {
            const holder = document.createElement("template");
            holder.innerHTML = chipHtml(chip.dataset.key, this.props.fields[chip.dataset.key]);
            chip.replaceWith(holder.content);
        }
    }

    changed(immediate = false) {
        const html = this.serialize();
        this.props.onChange(html);
        clearTimeout(this._recordTimer);
        if (immediate) {
            this.record(html);
        } else {
            this._recordTimer = setTimeout(() => this.record(this.serialize()), 380);
        }
        this.schedulePills();
    }

    record(html) {
        if (this.hist[this.pos] === html) { return; }
        this.hist = this.hist.slice(0, this.pos + 1);
        this.hist.push(html);
        if (this.hist.length > 120) { this.hist.shift(); }
        this.pos = this.hist.length - 1;
        this.syncUndoState();
    }

    syncUndoState() {
        if (this.props.ui) {
            this.props.ui.canUndo = this.pos > 0;
            this.props.ui.canRedo = this.pos < this.hist.length - 1;
        }
    }

    undo() {
        clearTimeout(this._recordTimer);
        this.record(this.serialize());
        if (this.pos <= 0) { return; }
        this.pos -= 1;
        this.setHtml(this.hist[this.pos]);
        this.props.onChange(this.hist[this.pos]);
        this.syncUndoState();
        this.focusEnd();
    }

    redo() {
        if (this.pos >= this.hist.length - 1) { return; }
        this.pos += 1;
        this.setHtml(this.hist[this.pos]);
        this.props.onChange(this.hist[this.pos]);
        this.syncUndoState();
        this.focusEnd();
    }

    // ---------------------------------------------------------- selection
    trackSelection() {
        const el = this.body.el;
        const sel = window.getSelection && window.getSelection();
        if (!el || !sel || !sel.rangeCount) { return; }
        const range = sel.getRangeAt(0);
        if (!el.contains(range.commonAncestorContainer)) { return; }
        this.range = range.cloneRange();
        const ui = this.props.ui;
        if (!ui) { return; }
        const q = (cmd) => { try { return document.queryCommandState(cmd); } catch { return false; } };
        ui.bold = q("bold");
        ui.italic = q("italic");
        ui.underline = q("underline");
        ui.ul = q("insertUnorderedList");
        ui.ol = q("insertOrderedList");
        ui.align = q("justifyCenter") ? "center" : q("justifyRight") ? "right" : q("justifyFull") ? "justify" : "left";
        let block = "";
        try { block = String(document.queryCommandValue("formatBlock") || "").toLowerCase(); } catch { block = ""; }
        ui.block = ["h1", "h2", "h3"].includes(block) ? block : "p";
        const node = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
        ui.inTable = Boolean(node && node.closest && node.closest("td, th") && el.contains(node));
        ui.inRule = Boolean(node && node.closest && node.closest(".pbds-when"));
        ui.focused = true;
    }

    restoreRange() {
        const el = this.body.el;
        if (!el) { return null; }
        el.focus({ preventScroll: true });
        const sel = window.getSelection();
        if (this.range && el.contains(this.range.commonAncestorContainer)) {
            sel.removeAllRanges();
            sel.addRange(this.range);
            return this.range;
        }
        const range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(false);
        sel.removeAllRanges();
        sel.addRange(range);
        this.range = range.cloneRange();
        return range;
    }

    focusEnd() {
        const el = this.body.el;
        if (!el) { return; }
        el.focus({ preventScroll: true });
        const range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(false);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        this.range = range.cloneRange();
    }

    caretRect() {
        const range = this.range;
        if (range) {
            const rects = range.getClientRects();
            const r = rects.length ? rects[0] : range.getBoundingClientRect();
            if (r && (r.top || r.left)) { return { x: r.left, y: r.bottom }; }
            const node = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
            if (node && node.getBoundingClientRect) {
                const b = node.getBoundingClientRect();
                return { x: b.left + 8, y: b.top + 22 };
            }
        }
        const b = this.body.el ? this.body.el.getBoundingClientRect() : { left: 200, top: 200 };
        return { x: b.left + 20, y: b.top + 30 };
    }

    // ---------------------------------------------------------- commands
    command(cmd, value = null) {
        this.restoreRange();
        try { document.execCommand("styleWithCSS", false, false); } catch { /* old engines */ }
        if (cmd === "formatBlock" && value) {
            document.execCommand("formatBlock", false, `<${value}>`);
        } else if (cmd.startsWith("justify")) {
            const img = this.body.el.querySelector("img.pbds-img-sel");
            if (img && img.parentElement && img.parentElement !== this.body.el) {
                const map = { justifyLeft: "left", justifyCenter: "center", justifyRight: "right", justifyFull: "left" };
                img.parentElement.style.textAlign = map[cmd];
            } else {
                document.execCommand(cmd, false, value);
            }
        } else {
            document.execCommand(cmd, false, value);
        }
        this.trackSelection();
        this.changed(true);
    }

    insertNodeAtRange(node, range) {
        range.deleteContents();
        range.insertNode(node);
        const after = document.createTextNode(ZWSP);
        node.after(after);
        const sel = window.getSelection();
        const r = document.createRange();
        r.setStart(after, 1);
        r.collapse(true);
        sel.removeAllRanges();
        sel.addRange(r);
        this.range = r.cloneRange();
    }

    insertField(key, atRange = null) {
        const range = atRange || this.restoreRange();
        if (!range) { return; }
        const el = this.body.el;
        // Never inside another chip.
        const host = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
        const inChip = host && host.closest && host.closest(".pbds-chip");
        if (inChip) {
            range.setStartAfter(inChip);
            range.collapse(true);
        }
        if (!el.contains(range.commonAncestorContainer)) { return; }
        const holder = document.createElement("template");
        holder.innerHTML = chipHtml(key, this.props.fields[key]);
        const chip = holder.content.firstElementChild;
        this.insertNodeAtRange(chip, range);
        chip.classList.add("is-new");
        setTimeout(() => chip.classList.remove("is-new"), 900);
        this.changed(true);
    }

    removeField(key) {
        const el = this.body.el;
        if (!el) { return 0; }
        let n = 0;
        for (const chip of el.querySelectorAll(".pbds-chip")) {
            if (chip.dataset.key === key) { chip.remove(); n += 1; }
        }
        if (n) { this.changed(true); }
        return n;
    }

    insertTable() {
        this.restoreRange();
        const head = esc(_t("Heading"));
        const html = `<table><tbody><tr><th>${head}</th><th>${head}</th></tr><tr><td><br></td><td><br></td></tr><tr><td><br></td><td><br></td></tr></tbody></table><p><br></p>`;
        document.execCommand("insertHTML", false, html);
        this.changed(true);
    }

    tableOp(op) {
        const range = this.range;
        if (!range) { return; }
        const node = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
        const cell = node && node.closest && node.closest("td, th");
        if (!cell || !this.body.el.contains(cell)) { return; }
        const row = cell.parentElement;
        const table = cell.closest("table");
        const idx = [...row.children].indexOf(cell);
        if (op === "row") {
            const tr = document.createElement("tr");
            for (let i = 0; i < row.children.length; i++) {
                const td = document.createElement("td");
                td.innerHTML = "<br>";
                tr.append(td);
            }
            row.after(tr);
        } else if (op === "col") {
            for (const tr of table.querySelectorAll("tr")) {
                const ref = tr.children[idx];
                const tag = ref && ref.tagName === "TH" ? "th" : "td";
                const td = document.createElement(tag);
                td.innerHTML = "<br>";
                if (ref) { ref.after(td); } else { tr.append(td); }
            }
        } else if (op === "delrow") {
            if (table.querySelectorAll("tr").length <= 1) { table.remove(); } else { row.remove(); }
        } else if (op === "delcol") {
            if (row.children.length <= 1) {
                table.remove();
            } else {
                for (const tr of table.querySelectorAll("tr")) {
                    if (tr.children[idx]) { tr.children[idx].remove(); }
                }
            }
        } else if (op === "deltable") {
            table.remove();
        }
        this.range = null;
        if (this.props.ui) { this.props.ui.inTable = false; }
        this.changed(true);
    }

    insertImage(url, name) {
        const range = this.restoreRange();
        if (!range) { return; }
        const p = document.createElement("p");
        const img = document.createElement("img");
        img.src = url;
        img.alt = name || "";
        img.style.width = IMG_SIZES.m;
        img.style.maxWidth = "100%";
        p.append(img);
        const host = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
        let block = host;
        while (block && block.parentElement !== this.body.el && block !== this.body.el) { block = block.parentElement; }
        if (block && block !== this.body.el) { block.after(p); } else { this.body.el.append(p); }
        this.selectImage(img);
        this.changed(true);
    }

    selectImage(img) {
        for (const other of this.body.el.querySelectorAll("img.pbds-img-sel")) { other.classList.remove("pbds-img-sel"); }
        if (img) { img.classList.add("pbds-img-sel"); }
        if (this.props.ui) { this.props.ui.image = Boolean(img); }
    }

    imageSize(size) {
        const img = this.body.el && this.body.el.querySelector("img.pbds-img-sel");
        if (!img || !IMG_SIZES[size]) { return false; }
        img.style.width = IMG_SIZES[size];
        img.style.maxWidth = "100%";
        img.style.height = "auto";
        this.changed(true);
        return true;
    }

    // ---------------------------------------------------------- show only when
    nextRuleId() {
        const used = ruleIds(this.serialize());
        let n = 1;
        while (used.has(`r${n}`)) { n += 1; }
        return `r${n}`;
    }

    /** The paragraph-level element holding `node` (a list or a table counts
     *  as one block; a plain wrapper div does not). */
    blockOf(node) {
        const el = this.body.el;
        let cur = node && node.nodeType === 3 ? node.parentElement : node;
        let found = null;
        while (cur && cur !== el) {
            if (cur.matches && cur.matches(".pbds-when")) { return cur; }
            if (cur.matches && cur.matches("p, h1, h2, h3, h4, ul, ol, table, blockquote")) { found = cur; }
            cur = cur.parentElement;
        }
        return found;
    }

    /** The blocks the selection covers: siblings from the start block to the
     *  end block, at the level where they share a parent. */
    topBlocks(range) {
        let start = this.blockOf(range.startContainer);
        let end = this.blockOf(range.endContainer) || start;
        if (!start) { return []; }
        while (start.parentElement !== end.parentElement) {
            if (start.parentElement && start.parentElement.contains(end)) {
                end = end.parentElement;
                while (end.parentElement !== start.parentElement) { end = end.parentElement; }
            } else if (end.parentElement && end.parentElement.contains(start)) {
                start = start.parentElement;
                while (start.parentElement !== end.parentElement) { start = start.parentElement; }
            } else {
                start = start.parentElement;
                end = end.parentElement;
                if (!start || !end || start === this.body.el) { return []; }
            }
        }
        const out = [];
        let cur = start;
        while (cur) {
            if (!(cur.nodeType === 3 && !cur.nodeValue.trim())) { out.push(cur); }
            if (cur === end) { break; }
            cur = cur.nextSibling;
        }
        return out;
    }

    showOnlyWhen() {
        const range = this.restoreRange();
        if (!range) { return; }
        const host = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
        const existing = host && host.closest && host.closest(".pbds-when");
        if (existing && this.body.el.contains(existing) && range.collapsed) {
            const id = [...existing.classList].find((c) => c.startsWith("pbds-r-"));
            if (id && this.props.onRule) { this.props.onRule(id.slice(7), false); }
            return;
        }
        let blocks = this.topBlocks(range);
        if (!blocks.length && host && host !== this.body.el && this.body.el.contains(host)) {
            // Loose text straight in the page: take the line it sits on.
            let block = host;
            while (block.parentElement && block.parentElement !== this.body.el) { block = block.parentElement; }
            blocks = [block];
        }
        if (!blocks.length) {
            // No paragraph under the cursor: say so rather than guess.
            if (this.props.onRule) { this.props.onRule(null, false); }
            return;
        }
        if (blocks.length === 1 && blocks[0].nodeType === 1 && blocks[0].classList.contains("pbds-when")) {
            const id = [...blocks[0].classList].find((c) => c.startsWith("pbds-r-"));
            if (id && this.props.onRule) { this.props.onRule(id.slice(7), false); }
            return;
        }
        if (!blocks.length) { return; }
        const id = this.nextRuleId();
        const wrapper = document.createElement("div");
        wrapper.className = `pbds-when pbds-r-${id}`;
        blocks[0].before(wrapper);
        for (const b of blocks) {
            if (b.nodeType === 3) {
                const p = document.createElement("p");
                p.append(b);
                wrapper.append(p);
            } else {
                wrapper.append(b);
            }
        }
        wrapper.classList.add("is-new");
        setTimeout(() => wrapper.classList.remove("is-new"), 900);
        this.changed(true);
        if (this.props.onRule) { this.props.onRule(id, true); }
    }

    unwrapRule(id) {
        const el = this.body.el;
        const block = el && el.querySelector(`.pbds-r-${CSS.escape(id)}`);
        if (!block) { return; }
        block.replaceWith(...block.childNodes);
        this.changed(true);
    }

    schedulePills() {
        clearTimeout(this._pillTimer);
        this._pillTimer = setTimeout(() => this.measurePills(), 40);
    }

    measurePills() {
        const el = this.body.el;
        const wrap = this.wrap.el;
        if (!el || !wrap) { return; }
        const base = wrap.getBoundingClientRect();
        const zoom = base.width && wrap.offsetWidth ? base.width / wrap.offsetWidth : 1;
        const list = [];
        for (const block of el.querySelectorAll(".pbds-when")) {
            const cls = [...block.classList].find((c) => c.startsWith("pbds-r-"));
            const id = cls ? cls.slice(7) : "";
            const r = block.getBoundingClientRect();
            list.push({
                id,
                top: Math.round((r.top - base.top) / zoom),
                height: Math.round(r.height / zoom),
                sentence: (this.props.sentences || {})[id] || _t("Show only when… (choose the condition)"),
                set: Boolean((this.props.sentences || {})[id]),
            });
        }
        const same = list.length === this.pills.list.length && list.every((p, i) =>
            p.id === this.pills.list[i].id && p.top === this.pills.list[i].top
            && p.sentence === this.pills.list[i].sentence && p.height === this.pills.list[i].height);
        if (!same) { this.pills.list = list; }
    }

    editRule(id) { if (this.props.onRule) { this.props.onRule(id, false); } }

    // ---------------------------------------------------------- events
    onInput() { this.changed(); }

    onClick(ev) {
        const img = ev.target.closest && ev.target.closest("img");
        this.selectImage(img && this.body.el.contains(img) ? img : null);
        const chip = ev.target.closest && ev.target.closest(".pbds-chip");
        if (chip) {
            const r = document.createRange();
            r.setStartAfter(chip);
            r.collapse(true);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(r);
            this.range = r.cloneRange();
        }
    }

    onKeydown(ev) {
        const mod = ev.metaKey || ev.ctrlKey;
        const key = ev.key.toLowerCase();
        if (mod && key === "z" && !ev.shiftKey) { ev.preventDefault(); this.undo(); return; }
        if (mod && ((key === "z" && ev.shiftKey) || key === "y")) { ev.preventDefault(); this.redo(); return; }
        if (mod && ["b", "i", "u"].includes(key)) {
            ev.preventDefault();
            this.trackSelection();
            this.command({ b: "bold", i: "italic", u: "underline" }[key]);
            return;
        }
        if (ev.key === "/" && !mod && !ev.altKey && this.props.onPick) {
            ev.preventDefault();
            this.trackSelection();
            this.props.onPick(this.caretRect());
            return;
        }
        if (ev.key === "Tab" && this.props.ui && this.props.ui.inTable) {
            ev.preventDefault();
            const node = this.range && (this.range.startContainer.nodeType === 1 ? this.range.startContainer : this.range.startContainer.parentElement);
            const cell = node && node.closest("td, th");
            if (cell) {
                const cells = [...cell.closest("table").querySelectorAll("td, th")];
                const next = cells[cells.indexOf(cell) + (ev.shiftKey ? -1 : 1)];
                if (next) {
                    const r = document.createRange();
                    r.selectNodeContents(next);
                    r.collapse(false);
                    const sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(r);
                    this.range = r.cloneRange();
                } else if (!ev.shiftKey) {
                    this.tableOp("row");
                }
            }
        }
    }

    onBlur() { if (this.props.ui) { this.props.ui.focused = false; } }

    onDragOver(ev) {
        if (ev.dataTransfer && [...ev.dataTransfer.types].includes("text/pbds-field")) {
            ev.preventDefault();
            ev.dataTransfer.dropEffect = "copy";
            this.wrap.el.classList.add("is-drop");
        }
    }
    onDragLeave() { if (this.wrap.el) { this.wrap.el.classList.remove("is-drop"); } }

    onDrop(ev) {
        const key = ev.dataTransfer && ev.dataTransfer.getData("text/pbds-field");
        this.wrap.el.classList.remove("is-drop");
        if (!key) { return; }
        ev.preventDefault();
        let range = null;
        if (document.caretRangeFromPoint) {
            range = document.caretRangeFromPoint(ev.clientX, ev.clientY);
        } else if (document.caretPositionFromPoint) {
            const pos = document.caretPositionFromPoint(ev.clientX, ev.clientY);
            if (pos) {
                range = document.createRange();
                range.setStart(pos.offsetNode, pos.offset);
                range.collapse(true);
            }
        }
        if (!range || !this.body.el.contains(range.startContainer)) { range = null; }
        this.body.el.focus({ preventScroll: true });
        this.insertField(key, range || this.restoreRange());
    }

    async onPaste(ev) {
        const data = ev.clipboardData;
        if (!data) { return; }
        const files = [...(data.files || [])].filter((f) => f.type.startsWith("image/"));
        if (files.length && this.props.onUpload) {
            ev.preventDefault();
            this.trackSelection();
            for (const file of files) {
                const res = await this.props.onUpload(file);
                if (res && res.ok) { this.insertImage(res.url, res.name); }
            }
            return;
        }
        const html = data.getData("text/html");
        const text = data.getData("text/plain");
        ev.preventDefault();
        if (html) {
            document.execCommand("insertHTML", false, this.expand(this.cleanPaste(html)));
        } else if (text) {
            const paras = text.replace(/\r\n/g, "\n").split(/\n{2,}/);
            const out = paras.map((p) => `<p>${esc(p).replace(/\n/g, "<br>")}</p>`).join("");
            document.execCommand("insertHTML", false, this.expand(paras.length > 1 ? out : esc(text)));
        }
        this.changed(true);
    }

    cleanPaste(html) {
        const tpl = document.createElement("template");
        tpl.innerHTML = html;
        const walk = (node) => {
            for (const child of [...node.childNodes]) {
                if (child.nodeType === 8) { child.remove(); continue; }
                if (child.nodeType !== 1) { continue; }
                if (["SCRIPT", "STYLE", "META", "LINK", "TITLE", "XML", "IFRAME", "OBJECT"].includes(child.tagName)) {
                    child.remove();
                    continue;
                }
                walk(child);
                if (!ALLOWED.has(child.tagName)) {
                    child.replaceWith(...child.childNodes);
                    continue;
                }
                const align = child.style && child.style.textAlign;
                const width = child.tagName === "IMG" ? child.style.width : "";
                for (const attr of [...child.attributes]) {
                    if (!["src", "alt", "colspan", "rowspan", "href"].includes(attr.name)) {
                        child.removeAttribute(attr.name);
                    }
                }
                if (child.tagName === "A") {
                    const href = child.getAttribute("href") || "";
                    if (!/^https?:|^mailto:/i.test(href)) { child.removeAttribute("href"); }
                }
                if (align && BLOCKS.has(child.tagName)) { child.style.textAlign = align; }
                if (width) { child.style.width = width; }
            }
        };
        walk(tpl.content);
        return tpl.innerHTML;
    }
}

/** The toolbar over the page. Reads the editor's reactive `ui` state. */
export class DocToolbar extends Component {
    static template = "pb_doc_studio.DocToolbar";
    static props = {
        api: { type: Object, optional: true },
        ui: { type: Object },
        disabled: { type: Boolean, optional: true },
        onImage: { type: Function, optional: true },
        onPick: { type: Function, optional: true },
    };

    ic(n, s = 15) { return dsIc(n, s); }
    get mod() { return modKey(); }
    call(name, ...args) {
        const api = this.props.api;
        if (!api || this.props.disabled) { return; }
        api[name](...args);
    }
    cmd(command, ev) {
        if (ev) { ev.preventDefault(); }
        this.call("command", command);
    }
    onBlock(ev) {
        this.call("block", ev.target.value);
    }
    tbl(op, ev) {
        if (ev) { ev.preventDefault(); }
        this.call("table", op);
    }
    size(s, ev) {
        if (ev) { ev.preventDefault(); }
        this.call("imageSize", s);
    }
    pick(ev) {
        if (ev) { ev.preventDefault(); }
        if (this.props.api && this.props.onPick) {
            this.props.onPick(this.props.api.caretRect());
        }
    }
    when(ev) {
        if (ev) { ev.preventDefault(); }
        this.call("showOnlyWhen");
    }
    alignClass(a) { return { "is-on": this.props.ui.align === a }; }
    /** Titles with their keys, translated here (a `t-att-` value in the
     *  template is not picked up for translation). */
    get tips() {
        const m = this.mod;
        return {
            undo: `${_t("Undo")} (${m}Z)`,
            redo: `${_t("Redo")} (⇧${m}Z)`,
            bold: `${_t("Bold")} (${m}B)`,
            italic: `${_t("Italic")} (${m}I)`,
            underline: `${_t("Underline")} (${m}U)`,
        };
    }
}
