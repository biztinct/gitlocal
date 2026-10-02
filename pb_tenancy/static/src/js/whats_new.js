/** @odoo-module **/
/**
 * What's new — the product's own changelog, on the customer's own database.
 *
 * THE QUESTION IT ANSWERS. "Something looks different this morning. What
 * happened?" Until now the only answer was to ask us. Now every release the
 * platform cuts arrives here with the sentence the owner wrote when he cut it,
 * newest first, with the one the reader is actually running badged as such.
 *
 * THE NOTES ARE WRITTEN BY A PERSON, IN A TEXTAREA, so they are rendered as a
 * person would type them: a blank line starts a new paragraph, a line beginning
 * `- ` is a bullet. Nothing else — no HTML, no links, no images. `t-esc` puts
 * every fragment on the page as TEXT, so a note can never carry markup onto a
 * customer's screen, whatever anybody types into the box.
 *
 * ZERO DEAD ENDS. A database that has never been told about a release shows a
 * sentence explaining what will appear here and when, not a blank page.
 */
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { _t } from "@web/core/l10n/translation";

/**
 * A note as blocks. PURE.
 *
 * Returns `[{kind: "p", text} | {kind: "ul", items: [...]}]`. A run of `- `
 * lines becomes ONE list rather than one list per line, which is what a person
 * typing three bullets means and never what a naive line-by-line pass gives.
 */
export function noteBlocks(notes) {
    const out = [];
    let para = [];
    let bullets = [];
    const flushPara = () => {
        if (para.length) { out.push({ kind: "p", text: para.join(" ") }); para = []; }
    };
    const flushBullets = () => {
        if (bullets.length) { out.push({ kind: "ul", items: bullets }); bullets = []; }
    };
    for (const raw of String(notes || "").split(/\r?\n/)) {
        const line = raw.trim();
        if (!line) { flushBullets(); flushPara(); continue; }
        if (/^[-*•]\s+/.test(line)) {
            flushPara();
            bullets.push(line.replace(/^[-*•]\s+/, ""));
            continue;
        }
        flushBullets();
        para.push(line);
    }
    flushBullets();
    flushPara();
    return out;
}

/** "3 September 2026" — the day, in the reader's locale. */
export function longDate(iso) {
    if (!iso) { return ""; }
    const d = new Date(String(iso).length <= 10 ? `${iso}T00:00:00` : iso);
    if (isNaN(d.getTime())) { return String(iso); }
    try {
        return d.toLocaleDateString(undefined,
            { day: "numeric", month: "long", year: "numeric" });
    } catch {
        return String(iso).slice(0, 10);
    }
}

export class PbTenancyWhatsNew extends Component {
    static template = "pb_tenancy.WhatsNew";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.tenancy = useService("pb_tenancy");
        // Subscribed, not merely fetched — see the note in tenancy_banner.js
        // (ledger F22). This page is open while a release is pushed often
        // enough to matter: it is the page the toast's button leads to.
        this.tstate = useState(this.tenancy.state);
        // Read ONCE, from props, never written back — the arrival protocol's
        // rule. Null when nobody sent us, and the chip is then absent rather
        // than inert.
        this.back = hubBack(this.props);
        this.state = useState({ expanded: {} });
    }

    ic(name, size = 16) { return ic(name, size); }

    /** Newest first, each with its notes already broken into blocks. */
    get releases() {
        const current = this.tstate.release;
        return (this.tstate.releases || []).map((r) => ({
            name: r.name || "",
            date: longDate(r.date || ""),
            blocks: noteBlocks(r.notes || ""),
            hasNotes: !!(r.notes || "").trim(),
            current: !!current && r.name === current,
        }));
    }

    get currentName() { return this.tstate.release || ""; }

    get pushedAt() { return this.tstate.pushed_at || ""; }

    /**
     * The one sentence at the top.
     *
     * Written for somebody who has never heard the word "release": it names the
     * one they are on and says what the list underneath is.
     */
    get lede() {
        const rel = this.currentName;
        if (!rel) {
            return _t("Payobook will list what changed here after each update.");
        }
        return _t("You are on release %(name)s. Every update the Payobook team " +
                  "ships is listed here, newest first.", { name: rel });
    }
}

registry.category("actions").add("pb_tenancy_whats_new", PbTenancyWhatsNew);
