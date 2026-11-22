/** @odoo-module **/
/**
 * DOCSTUDIO A2 — "Contract document" in the contract side panel.
 *
 * HERO MOMENT: press "Contract document" and the finished contract for THIS
 * contract slides in on real A4 paper — the person's values glow into place
 * one after another, anything missing is an amber chip above the page that
 * jumps straight to the field in the panel, and "Download PDF" / "Save to
 * documents" give the true file (saved as the next version, earlier ones
 * kept).
 *
 * The drawer (`pb_contracts` `Contract360Drawer`) is extended by OWL `patch`
 * and template inheritance only. Server: `pb.contracts.contract_document*`
 * (this module). Lucide icons, locked indigo palette, no emoji.
 */
import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState,
         useExternalListener } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic as kitIc } from "@pb_import_kit/js/import_icons";
import { KIND_ICON } from "@pb_doc_studio/js/doc_icons";
import { Contract360Drawer } from "@pb_contracts/js/contract_360";

const MODEL = "pb.contracts";
const A4_W = 794;
const A4_H = 1123;

// The document studio's gallery group for employment contracts.
KIND_ICON.employment = "briefcase";

// Icons are cached: the same markup object on every redraw, so OWL never
// re-inserts the SVG (the markup-flicker trap).
const ICONS = new Map();
function ic(name, size = 16) {
    const key = name + "|" + size;
    if (!ICONS.has(key)) { ICONS.set(key, kitIc(name, size)); }
    return ICONS.get(key);
}

const PV_STYLE = `
@font-face{font-family:'Roboto';src:url('/web/static/fonts/google/Roboto/Roboto-Regular.ttf') format('truetype');font-weight:400}
@font-face{font-family:'Roboto';src:url('/web/static/fonts/google/Roboto/Roboto-Bold.ttf') format('truetype');font-weight:700}
@font-face{font-family:'Roboto';src:url('/web/static/fonts/google/Roboto/Roboto-Italic.ttf') format('truetype');font-style:italic}
@font-face{font-family:'Open_Sans';src:url('/web/static/fonts/google/Open_Sans/Open_Sans-Regular.ttf') format('truetype');font-weight:400}
@font-face{font-family:'Open_Sans';src:url('/web/static/fonts/google/Open_Sans/Open_Sans-Bold.ttf') format('truetype');font-weight:700}
@font-face{font-family:'Montserrat';src:url('/web/static/fonts/google/Montserrat/Montserrat-Regular.ttf') format('truetype');font-weight:400}
@font-face{font-family:'Montserrat';src:url('/web/static/fonts/google/Montserrat/Montserrat-Bold.ttf') format('truetype');font-weight:700}
@font-face{font-family:'DejaVu Serif';src:url('/pb_hr_payroll_formula/static/fonts/dejavu/DejaVuSerif.ttf') format('truetype');font-weight:400}
@font-face{font-family:'DejaVu Serif';src:url('/pb_hr_payroll_formula/static/fonts/dejavu/DejaVuSerif-Bold.ttf') format('truetype');font-weight:700}
html,body{margin:0;padding:0;background:#fff}
body{width:${A4_W}px;overflow:hidden}
.pbds-screen{min-height:${A4_H}px;box-sizing:border-box}
@keyframes pbdc-ink{0%{background-color:rgba(90,75,176,0);color:inherit}35%{background-color:rgba(90,75,176,.22)}100%{background-color:rgba(90,75,176,0)}}
.pbds-v{border-radius:3px}
.pbdc-ink .pbds-v{animation:pbdc-ink 1.1s ease-out both}
.pbds-miss{animation:none}
@media (prefers-reduced-motion: reduce){.pbdc-ink .pbds-v{animation:none}}
`;

function errText(e, fallback) {
    return (e && e.data && e.data.message)
        || (e && e.message && e.message.data && e.message.data.message)
        || fallback;
}
function isMac() { return /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || ""); }

// =========================================================================
//  The sheet
// =========================================================================
export class ContractDocSheet extends Component {
    static template = "pb_doc_contracts.ContractDocSheet";
    static props = {
        contractId: { type: [Number, String] },
        onClose: { type: Function },
        onJump: { type: Function, optional: true },
        onDesign: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.desk = useRef("desk");
        this.frame = useRef("frame");
        this.state = useState({
            shown: false, loading: true, d: null, error: "",
            lang: false, docId: false, pdfBusy: false, saveBusy: false,
            leftOpen: false, scale: 0.6, height: A4_H, fresh: 0, inked: false,
        });
        useExternalListener(window, "keydown", (ev) => this.onKey(ev), { capture: true });
        useExternalListener(window, "resize", () => this.measure());
        onWillStart(() => this.load());
        onMounted(() => {
            requestAnimationFrame(() => { this.state.shown = true; });
            this.measure();
        });
        onWillUnmount(() => clearTimeout(this._inkTimer));
    }

    ic(n, s = 16) { return ic(n, s); }
    get mod() { return isMac() ? "⌘" : "Ctrl "; }
    get d() { return this.state.d || {}; }
    get title() { return (this.d.document && this.d.document.name) || _t("Employment contract"); }

    // ------------------------------------------------------------ loading
    async load() {
        this.state.loading = true;
        try {
            const res = await this.orm.call(MODEL, "contract_document",
                [Number(this.props.contractId)],
                { lang: this.state.lang || false, template_id: this.state.docId || false });
            if (res && res.ok) {
                this.state.d = res;
                this.state.error = "";
                this.state.lang = res.lang;
                this.state.docId = res.document.id;
                this.state.inked = false;
            } else {
                this.state.d = null;
                this.state.error = (res && res.msg) || _t("The contract could not be drawn.");
            }
        } catch (e) {
            this.state.d = null;
            this.state.error = errText(e, _t("The contract could not be drawn just now. Try again in a moment."));
        } finally {
            this.state.loading = false;
        }
    }
    reload() { return this.load(); }

    // ------------------------------------------------------------ chrome
    close() {
        this.state.shown = false;
        setTimeout(() => this.props.onClose(), 200);
    }
    onKey(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            this.close();
            return;
        }
        const mod = ev.metaKey || ev.ctrlKey;
        if (!mod) { return; }
        const k = (ev.key || "").toLowerCase();
        if (k === "s") { ev.preventDefault(); ev.stopPropagation(); this.save(); }
        if (k === "p") { ev.preventDefault(); ev.stopPropagation(); this.download(); }
    }
    measure() {
        const box = this.desk.el;
        if (!box) { return; }
        const scale = Math.max(0.3, Math.min(1, (box.clientWidth - 48) / A4_W));
        if (Math.abs(scale - this.state.scale) > 0.004) { this.state.scale = scale; }
    }
    get paperStyle() {
        return `width:${Math.round(A4_W * this.state.scale)}px;height:${Math.round(this.state.height * this.state.scale)}px;`;
    }
    get frameStyle() {
        return `transform:scale(${this.state.scale});height:${this.state.height}px;`;
    }
    get frameDoc() {
        const html = this.d.html || "";
        return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src * data: blob:; font-src *"><style>${PV_STYLE}</style></head><body>${html}</body></html>`;
    }
    /** The hero beat: each value inks in, top to bottom, once per drawing. */
    onFrameLoad(ev) {
        const frame = ev.target;
        let doc = null;
        try { doc = frame.contentDocument; } catch { doc = null; }
        if (!doc || !doc.body) { return; }
        const h = Math.max(A4_H, doc.body.scrollHeight);
        frame.style.height = `${h}px`;
        if (Math.abs(h - this.state.height) > 2) { this.state.height = h; }
        this.measure();
        if (this.state.inked) { return; }
        this.state.inked = true;
        const spans = Array.from(doc.querySelectorAll(".pbds-v"));
        spans.forEach((span, i) => { span.style.animationDelay = `${Math.min(i * 45, 1600)}ms`; });
        doc.body.classList.add("pbdc-ink");
    }

    // ------------------------------------------------------------ choices
    get langs() { return this.d.langs || []; }
    get documents() { return this.d.documents || []; }
    setLang(code) {
        if (code === this.state.lang || this.state.loading) { return; }
        this.state.lang = code;
        this.load();
    }
    onDocument(ev) {
        const id = Number(ev.target.value);
        if (!id || id === this.state.docId) { return; }
        this.state.docId = id;
        this.state.lang = false;
        this.load();
    }
    shortLang(name) { return String(name || "").replace(/\s*\(.*\)\s*$/, ""); }

    // ------------------------------------------------------------ status
    get missing() { return this.d.missing || []; }
    get leftOut() { return this.d.left_out || []; }
    get versions() { return this.d.versions || []; }
    get blocked() { return Boolean(this.d.pay_blocked); }
    get canFile() { return Boolean(this.d.can_file) && !this.blocked; }
    get missingTitle() {
        const n = this.missing.length;
        return n === 1 ? _t("1 thing is missing") : _t("%s things are missing", n);
    }
    get leftOutTitle() {
        const n = this.leftOut.length;
        return n === 1 ? _t("1 paragraph is left out for this contract")
            : _t("%s paragraphs are left out for this contract", n);
    }
    toggleLeftOut() { this.state.leftOpen = !this.state.leftOpen; }
    canJump(target) { return Boolean(target && this.props.onJump); }
    jumpTitle(target) {
        if (!target) { return _t("Change it on the full contract form or the employee's record"); }
        return target.kind === "employee" ? _t("Open the employee to fill it in")
            : _t("Go to this field in the contract panel");
    }
    jump(target) {
        if (!this.canJump(target)) { return; }
        this.props.onJump(target);
    }
    get saveLabel() {
        return _t("Save to documents · v%s", this.d.next_version || 1);
    }
    get saveTitle() {
        if (this.blocked) { return this.d.pay_msg || ""; }
        if (!this.d.can_file) { return this.d.file_msg || ""; }
        return _t("Files the PDF in %s's documents as version %s. Earlier versions are kept.",
                  (this.d.person || {}).name || "", this.d.next_version || 1);
    }
    get emptyVersionsText() {
        return _t("Not saved yet. Saving files it as version 1 in %s's documents.", (this.d.person || {}).name || "");
    }
    versionWhen(v) {
        if (!v.date) { return v.by || ""; }
        const d = new Date(v.date + "T00:00:00");
        const when = isNaN(d) ? v.date : d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
        return v.by ? _t("%(when)s · by %(who)s", { when, who: v.by }) : when;
    }
    versionClass(v) { return { "is-fresh": v.version === this.state.fresh }; }

    // ------------------------------------------------------------ actions
    async download() {
        if (this.state.pdfBusy || !this.state.d) { return; }
        if (this.blocked) { this.notif.add(this.d.pay_msg, { type: "warning" }); return; }
        this.state.pdfBusy = true;
        try {
            const res = await this.orm.call(MODEL, "contract_document_pdf", [Number(this.props.contractId)],
                { lang: this.state.lang || false, template_id: this.state.docId || false });
            if (!res.ok) { this.notif.add(res.msg, { type: "warning" }); return; }
            const bytes = Uint8Array.from(atob(res.data), (c) => c.charCodeAt(0));
            const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
            const a = document.createElement("a");
            a.href = url;
            a.download = res.name;
            document.body.append(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 4000);
            this.notif.add(_t("PDF ready. Nothing was filed or sent."), { type: "success" });
        } catch (e) {
            this.notif.add(errText(e, _t("The PDF could not be made right now.")), { type: "danger" });
        } finally {
            this.state.pdfBusy = false;
        }
    }
    async save() {
        if (this.state.saveBusy || !this.state.d) { return; }
        if (!this.canFile) {
            this.notif.add(this.blocked ? this.d.pay_msg : this.d.file_msg, { type: "warning" });
            return;
        }
        this.state.saveBusy = true;
        try {
            const res = await this.orm.call(MODEL, "contract_document_save", [Number(this.props.contractId)],
                { lang: this.state.lang || false, template_id: this.state.docId || false });
            if (!res.ok) { this.notif.add(res.msg, { type: "warning" }); return; }
            this.state.d.versions = res.versions;
            this.state.d.next_version = res.next_version;
            this.state.fresh = res.version;
            this.notif.add(_t("Filed in %(who)s's documents as version %(n)s.",
                              { who: (this.d.person || {}).name || "", n: res.version }), { type: "success" });
        } catch (e) {
            this.notif.add(errText(e, _t("The contract could not be filed just now.")), { type: "danger" });
        } finally {
            this.state.saveBusy = false;
        }
    }
    design() {
        if (!this.d.can_design || !this.props.onDesign) { return; }
        this.props.onDesign(this.d.document.used_id || this.d.document.id);
    }
}

// =========================================================================
//  The drawer: the button, the sheet, the jumps
// =========================================================================
patch(Contract360Drawer.prototype, {
    setup() {
        super.setup(...arguments);
        this.pbdc = useState({ open: false });
        this._pbdcRemove = null;
        onWillUnmount(() => { if (this._pbdcRemove) { this._pbdcRemove(); } });
    },
    get pbdcAvailable() {
        const doc = this.d && this.d.contract_document;
        return Boolean(doc && doc.available);
    },
    get pbdcInActs() { return Boolean(this.nextActions.length && this.canWrite); },
    pbdcIcon() { return ic("fileText", 14); },
    pbdcOpen() {
        if (this.pbdc.open) { return; }
        this.state.edit = null;
        this.pbdc.open = true;
        this._pbdcRemove = this.overlay.add(ContractDocSheet, {
            contractId: Number(this.props.contractId),
            onClose: () => this.pbdcClosed(),
            onJump: (target) => this.pbdcJump(target),
            onDesign: (templateId) => this.pbdcDesign(templateId),
        });
    },
    pbdcClosed() {
        const remove = this._pbdcRemove;
        this._pbdcRemove = null;
        this.pbdc.open = false;
        if (remove) { remove(); }
    },
    onKey(ev) {
        // The sheet owns every key while it is up.
        if (this.pbdc && this.pbdc.open) { return; }
        return super.onKey(ev);
    },
    /** A chip on the sheet: close it and land on the field. */
    pbdcJump(target) {
        this.pbdcClosed();
        if (!target) { return; }
        if (target.kind === "employee") {
            const Drawer = registry.category("pb_people_drawer").get("employee_360", null);
            const empId = this.header.employee_id;
            if (Drawer && empId) {
                const remove = this.overlay.add(Drawer, { empId, onClose: () => remove() });
            }
            return;
        }
        const entry = this.termEntry(target.name);
        if (!entry) {
            this.notif.add(_t("This is not on the contract panel. Open the full form to fill it in."),
                           { type: "info" });
            return;
        }
        if (this.state.tab !== "terms") { this.setTab("terms"); }
        setTimeout(() => {
            const el = document.querySelector('.pbc-drawer [data-cdkey="term:' + target.name + '"]');
            if (!el) { return; }
            if (el.scrollIntoView) { el.scrollIntoView({ block: "center", behavior: "smooth" }); }
            el.classList.add("pbdc-flash");
            setTimeout(() => el.classList.remove("pbdc-flash"), 1800);
            if (this.canEdit(entry)) {
                this._anchorEl = el;
                this.state.edit = { scope: "term", key: target.name };
            } else if (el.focus) {
                el.setAttribute("tabindex", "-1");
                el.focus({ preventScroll: true });
            }
        }, 90);
    },
    /** "Change the wording": to the designer, on the wording this contract uses. */
    pbdcDesign(templateId) {
        this.pbdcClosed();
        if (this.dirtyCount > 0) {
            this.notif.add(_t("Save or discard your changes first."), { type: "warning" });
            return;
        }
        this.reallyClose();
        setTimeout(() => {
            this.action.doAction("pb_doc_studio.action_pb_doc_studio",
                                 { additionalContext: { pbds_open: templateId } });
        }, 200);
    },
});

