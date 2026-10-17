/** @odoo-module **/
/**
 * RECRUIT P7 — where the role goes: the Publish panel, Hiring set-up →
 * Channels and Agencies, and each agency's figures on Hiring numbers.
 *
 * THE HERO IS THE PANEL. "Publish to…" slides a sheet in from the right: one
 * row per channel the role's country uses, each with its OWN tracked link in
 * a mono chip that copies in one press (the icon turns into a tick, the row
 * says "Copied"), and a count of the applications that came through that
 * link. While the sheet is open it listens (every 20 s, only while the tab is
 * visible): when somebody applies through LinkedIn, LinkedIn's count ticks
 * up with a pop and a toast says so. The recruiter sees which channel works
 * without opening a report.
 *
 * No board is connected on this build and the panel never pretends one is:
 * a board row says where to paste the advert, offers the advert text in one
 * press, and keeps the recruiter's promise ("Mark as posted").
 *
 * Keyboard: ↑ ↓ move between rows, C copies the row's link, M marks it as
 * posted, Esc closes. A PATCH, like P3–P6: the server decides who may do
 * what; this file only draws and asks.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { onWillUnmount } from "@odoo/owl";
import { PbHiringBoard } from "./hiring_board";
import { PbHiringSetup } from "./hiring_setup";

const POLL_MS = 20000;
const COPIED_MS = 1600;
const BUMP_MS = 1400;

function pad(n) { return String(n).padStart(2, "0"); }
function isoToday() {
    const d = new Date();
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Copy text: the async clipboard where the page is allowed it, else the
 *  old select-and-copy (an http page, an older browser). */
async function copyText(text) {
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
            return true;
        }
    } catch {
        // fall through to the textarea
    }
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch { ok = false; }
    area.remove();
    return ok;
}

// =========================================================================
//  The board: the panel, the pill, the agency on the role
// =========================================================================
patch(PbHiringBoard.prototype, {
    setup() {
        super.setup(...arguments);
        Object.assign(this.state, {
            p7: null, p7Open: false, p7Loading: false, p7Busy: false,
            p7Copied: null, p7Bumped: [], p7Focus: 0,
            p7Mark: null, p7Invite: null, p7AgencyPick: "",
        });
        onWillUnmount(() => { clearInterval(this._p7Poll); clearTimeout(this._p7CopyT); });
    },

    async openRole(id, opts) {
        const changed = !this.state.drawer || this.state.drawer.id !== id;
        if (changed) {
            Object.assign(this.state, { p7: null, p7Open: false, p7Mark: null, p7Invite: null });
        }
        await super.openRole(id, opts);
        if (this.state.canRecruit && this.state.drawer) { this.p7Load({ quiet: true }); }
    },

    async refresh() {
        await super.refresh();
        if (this.state.view === "role" && this.state.drawer && this.state.p7) {
            await this.p7Load({ quiet: true });
        }
    },

    // ---------------------------------------------------------- the data
    async p7Load({ quiet = false } = {}) {
        const d = this.state.drawer;
        if (!d) { return; }
        if (!quiet) { this.state.p7Loading = true; }
        try {
            const data = await this.orm.call("pb.hiring", "get_publish_panel", [d.id]);
            this.p7Diff(data);
            this.state.p7 = data;
        } catch (e) {
            if (!quiet) { this.fail(e); }
        } finally {
            this.state.p7Loading = false;
        }
    },

    /** A count that went UP since the last read pops and is announced. */
    p7Diff(next) {
        const prev = this.state.p7;
        if (!prev || prev.id !== next.id) { return; }
        const before = {};
        for (const r of prev.rows) { before[r.id] = r.apps; }
        const bumped = [];
        for (const r of next.rows) {
            const was = before[r.id];
            if (was !== undefined && r.apps > was) {
                bumped.push(r.id);
                const n = r.apps - was;
                this.notif.add(n === 1 ? _t("1 new application through %s", r.name)
                    : _t("%(n)s new applications through %(name)s", { n, name: r.name }),
                { type: "success" });
            }
        }
        if (bumped.length) {
            this.state.p7Bumped = bumped;
            setTimeout(() => { this.state.p7Bumped = []; }, BUMP_MS);
        }
    },

    p7StartPoll() {
        clearInterval(this._p7Poll);
        this._p7Poll = setInterval(() => {
            if (!this.state.p7Open || document.hidden) { return; }
            this.p7Load({ quiet: true });
        }, POLL_MS);
    },

    async p7OpenSheet(focusKey) {
        this.state.p7Open = true;
        this.state.p7Focus = 0;
        await this.p7Load({ quiet: !!this.state.p7 });
        if (focusKey && this.state.p7) {
            const i = this.state.p7.rows.findIndex((r) => r.key === focusKey);
            if (i > -1) { this.state.p7Focus = i; }
        }
        this.p7StartPoll();
    },

    p7CloseSheet() {
        Object.assign(this.state, { p7Open: false, p7Mark: null, p7Invite: null });
        clearInterval(this._p7Poll);
    },

    // ---------------------------------------------------------- words
    get p7Pill() {
        const d = this.state.drawer;
        const n = d ? (d.p7_live || 0) : 0;
        if (!n) { return _t("Not published yet"); }
        return n === 1 ? _t("Published · 1 channel") : _t("Published · %s channels", n);
    },
    p7AppsWord(n) {
        if (!n) { return _t("No applications yet"); }
        return n === 1 ? _t("1 application") : _t("%s applications", n);
    },
    p7Short(link) {
        if (!link) { return ""; }
        return link.replace(/^https?:\/\//, "");
    },
    p7RowTone(r) {
        if (r.kind === "careers" || r.kind === "referral" || r.kind === "agency") { return r.live ? "live" : "off"; }
        return { posted: "live", closed: "closed" }[r.state] || "off";
    },
    get p7Totals() {
        const p = this.state.p7;
        if (!p) { return null; }
        const best = [...p.rows].sort((a, b) => b.apps - a.apps)[0];
        return { live: p.live, apps: p.apps, best: best && best.apps ? best : null };
    },
    p7Share(r) {
        const p = this.state.p7;
        if (!p || !p.apps) { return 0; }
        return Math.round((r.apps * 100) / p.apps);
    },

    // ---------------------------------------------------------- the verbs
    async p7Act(verb, payload, { undo = null } = {}) {
        this.state.p7Busy = true;
        try {
            const res = await this.orm.call("pb.hiring", "act", [verb, payload || {}]);
            if (res && res.note) {
                if (undo) {
                    // The board's own toast, with Undo for five seconds.
                    clearTimeout(this._toastTimer);
                    this.state.toast = { text: res.note, moved: [], prompt: null, undo: () => undo(res) };
                    this._toastTimer = setTimeout(() => { this.state.toast = null; }, 5000);
                } else {
                    this.notif.add(res.note, { type: "success" });
                }
            }
            if (res && res.live !== undefined && this.state.drawer) { this.state.drawer.p7_live = res.live; }
            await this.p7Load({ quiet: true });
            return res;
        } catch (e) {
            this.fail(e);
            return null;
        } finally {
            this.state.p7Busy = false;
        }
    },

    async p7Copy(r) {
        if (!r.link) { return; }
        const ok = await copyText(r.link);
        if (ok) {
            this.state.p7Copied = r.id;
            clearTimeout(this._p7CopyT);
            this._p7CopyT = setTimeout(() => { this.state.p7Copied = null; }, COPIED_MS);
            this.notif.add(_t("%s link copied. Every application through it is counted here.", r.name), { type: "success" });
        } else {
            this.notif.add(_t("This browser would not copy. Select the link and copy it yourself."), { type: "warning" });
        }
    },
    async p7CopyAdvert(r) {
        if (!r.advert) { return; }
        const ok = await copyText(r.advert);
        this.notif.add(ok ? _t("The advert for %s is copied, with its link as the way to apply. Paste it there, then press Mark as posted.", r.name)
            : _t("This browser would not copy."), { type: ok ? "success" : "warning" });
    },
    async p7CopyAll() {
        const p = this.state.p7;
        if (!p) { return; }
        const lines = p.rows.filter((r) => r.link).map((r) => `${r.name}: ${r.link}`);
        if (!lines.length) { return; }
        const ok = await copyText(`${p.title}\n` + lines.join("\n"));
        this.notif.add(ok ? _t("All %s links copied, one per line.", lines.length) : _t("This browser would not copy."),
            { type: ok ? "success" : "warning" });
    },

    p7StartMark(r) {
        this.state.p7Mark = { id: r.id, name: r.name, posted_on: isoToday(), external_url: r.external_url || "" };
    },
    async p7SaveMark() {
        const m = this.state.p7Mark;
        if (!m) { return; }
        const res = await this.p7Act("p7_mark_posted", { role_channel_id: m.id, posted_on: m.posted_on, external_url: m.external_url });
        if (res) { this.state.p7Mark = null; }
    },
    async p7Unmark(r) {
        await this.p7Act("p7_unmark", { role_channel_id: r.id });
    },
    async p7TakeDown(r) {
        await this.p7Act("p7_close", { role_channel_id: r.id }, {
            undo: () => this.p7Act("p7_mark_posted", { role_channel_id: r.id, posted_on: r.posted_on_iso, external_url: r.external_url }),
        });
    },
    async p7Send(r) { await this.p7Act("p7_send_pack", { role_channel_id: r.id }); },
    async p7Publish() {
        const d = this.state.drawer;
        await this.p7Act("p7_publish", { requisition_id: d.id });
        await this.reloadRole();
    },
    async p7Unpublish() {
        const d = this.state.drawer;
        await this.p7Act("p7_unpublish", { requisition_id: d.id }, {
            undo: () => this.p7Publish(),
        });
        await this.reloadRole();
    },
    async p7Referrals(on) {
        const d = this.state.drawer;
        await this.p7Act("p7_referrals", { requisition_id: d.id, open: on }, {
            undo: () => this.p7Act("p7_referrals", { requisition_id: d.id, open: !on }),
        });
        await this.reloadRole();
    },
    async p7AgencyAdd() {
        const d = this.state.drawer;
        const vid = Number(this.state.p7AgencyPick);
        if (!vid) { return; }
        const res = await this.p7Act("p7_agency_add", { requisition_id: d.id, vendor_id: vid });
        if (res) { this.state.p7AgencyPick = ""; await this.reloadRole(); }
    },
    async p7AgencyRemove(ag) {
        const d = this.state.drawer;
        await this.p7Act("p7_agency_remove", { requisition_id: d.id, vendor_id: ag.id }, {
            undo: () => this.p7Act("p7_agency_add", { requisition_id: d.id, vendor_id: ag.id }),
        });
        await this.reloadRole();
    },
    get p7AgencyChoices() {
        const p = this.state.p7;
        if (!p) { return []; }
        const row = p.rows.find((r) => r.kind === "agency");
        const on = new Set(((row && row.agencies) || []).map((a) => a.id));
        return (p.agencies_all || []).filter((a) => !on.has(a.id));
    },
    p7StartInvite(ag) {
        this.state.p7Invite = { vendor_id: ag.id, agency: ag.name, email: ag.contact_email || "", name: "" };
    },
    async p7SaveInvite() {
        const f = this.state.p7Invite;
        if (!f || !String(f.email || "").includes("@")) {
            this.notif.add(_t("Type the email address of the person at the agency."), { type: "warning" });
            return;
        }
        const res = await this.p7Act("p7_agency_invite", { vendor_id: f.vendor_id, email: f.email, name: f.name });
        if (res) { this.state.p7Invite = null; }
    },
    async p7Portal(ag) {
        if (ag.portal_url) { window.open(ag.portal_url, "_blank", "noopener"); }
    },

    /** The row's main press — what Enter does on a focused row. */
    async p7Primary(r) {
        if (r.kind === "careers") { return r.live ? this.p7Copy(r) : this.p7Publish(); }
        if (r.kind === "referral") { return r.live ? this.p7Copy(r) : this.p7Referrals(true); }
        if (r.kind === "agency") { return null; }
        if (r.state !== "posted") { return this.p7StartMark(r); }
        return this.p7Copy(r);
    },

    // ---------------------------------------------------------- keyboard
    get anyDialog() {
        const s = this.state;
        return super.anyDialog || !!(s.p7Open || s.p7Mark || s.p7Invite);
    },
    onKey(ev) {
        const s = this.state;
        if (s.p7Open || s.p7Mark || s.p7Invite) {
            const t = ev.target;
            const typing = t && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName));
            if (ev.key === "Escape") {
                if (s.p7Mark) { s.p7Mark = null; } else if (s.p7Invite) { s.p7Invite = null; } else { this.p7CloseSheet(); }
                ev.stopPropagation();
                ev.preventDefault();
                return;
            }
            if (typing || !s.p7Open || s.p7Mark || s.p7Invite || ev.metaKey || ev.ctrlKey || ev.altKey) { return; }
            const rows = (s.p7 && s.p7.rows) || [];
            if (!rows.length) { return; }
            const r = rows[Math.min(s.p7Focus, rows.length - 1)];
            if (ev.key === "ArrowDown") { ev.preventDefault(); s.p7Focus = Math.min(s.p7Focus + 1, rows.length - 1); this.p7ScrollRow(); return; }
            if (ev.key === "ArrowUp") { ev.preventDefault(); s.p7Focus = Math.max(s.p7Focus - 1, 0); this.p7ScrollRow(); return; }
            if (ev.key === "c" || ev.key === "C") { ev.preventDefault(); this.p7Copy(r); return; }
            if ((ev.key === "m" || ev.key === "M") && ["board", "social"].includes(r.kind) && r.state !== "posted") {
                ev.preventDefault(); this.p7StartMark(r); return;
            }
            if (ev.key === "Enter") { ev.preventDefault(); this.p7Primary(r); return; }
            return;
        }
        return super.onKey(ev);
    },
    p7FocusRow(i, inSheet) { if (inSheet) { this.state.p7Focus = i; } },
    p7ScrollRow() {
        setTimeout(() => {
            const el = document.querySelector(".pbhr-p7-sheet .pbhr-p7-row.is-focus");
            if (el && el.scrollIntoView) { el.scrollIntoView({ block: "nearest" }); }
        }, 0);
    },
});

// =========================================================================
//  Hiring set-up → Channels and Agencies
// =========================================================================
patch(PbHiringSetup.prototype, {
    setup() {
        super.setup(...arguments);
        Object.assign(this.state, {
            p7Add: null, p7Invite: null, p7Cooling: null,
        });
    },
    get p7Ch() { return (this.state.data && this.state.data.channels) || { rows: [], countries: [] }; },
    get p7Ag() { return (this.state.data && this.state.data.agencies) || { rows: [] }; },
    async openCard(card) {
        const at = { channels: ".pbhr-su-p7ch", agencies: ".pbhr-su-p7ag" }[card.key];
        if (at) {
            const el = document.querySelector(at);
            if (el && el.scrollIntoView) { el.scrollIntoView({ behavior: "smooth", block: "start" }); }
            return;
        }
        return super.openCard(card);
    },
    p7On(ch, country) {
        return ch.every_country || ch.country_ids.includes(country.id);
    },
    p7CellTitle(ch, country) {
        return this.p7On(ch, country) ? _t("%(ch)s is offered for roles in %(c)s. Press to stop.", { ch: ch.name, c: country.name })
            : _t("%(ch)s is not offered for roles in %(c)s. Press to offer it.", { ch: ch.name, c: country.name });
    },
    async p7Toggle(ch, country) {
        const on = !this.p7On(ch, country);
        await this.call("p7_channel_country", { id: ch.id, country_id: country.id, on }, {
            undo: (res) => this.call("p7_channel_country", { id: ch.id, restore: res.before }),
        });
    },
    async p7Every(ch) {
        await this.call("p7_channel_country", { id: ch.id, every: true }, {
            undo: (res) => this.call("p7_channel_country", { id: ch.id, restore: res.before }),
        });
    },
    async p7Save(ch, field, value) {
        if (field === "name" && !String(value || "").trim()) { return; }
        if ((ch[field === "hint" ? "hint" : field] || "") === (value || "")) { return; }
        await this.call("p7_channel_save", { id: ch.id, [field]: value }, {
            undo: (res) => this.call("p7_channel_save", { id: ch.id, ...res.before }),
        });
    },
    async p7Active(ch) {
        await this.call("p7_channel_save", { id: ch.id, active: !ch.active }, {
            undo: (res) => this.call("p7_channel_save", { id: ch.id, ...res.before }),
        });
    },
    p7StartAdd() { this.state.p7Add = { name: "", kind: "board" }; },
    async p7SaveAdd() {
        const f = this.state.p7Add;
        if (!f || !f.name.trim()) { return; }
        const res = await this.call("p7_channel_add", { name: f.name, kind: f.kind });
        if (res) { this.state.p7Add = null; }
    },
    async p7MailSwitch() {
        const on = !this.p7Ch.mail_on;
        await this.call("p7_platform_mail", { on }, {
            undo: () => this.call("p7_platform_mail", { on: !on }),
        });
    },
    async p7SaveCooling(value) {
        const months = parseInt(value, 10);
        if (!months || months === this.p7Ch.cooling_months) { return; }
        await this.call("p7_cooling", { months }, {
            undo: (res) => this.call("p7_cooling", { months: res.before }),
        });
    },
    p7StartInvite(ag) { this.state.p7Invite = { vendor_id: ag.id, agency: ag.name, email: ag.contact_email || "", name: ag.contact_name || "" }; },
    async p7SaveInvite() {
        const f = this.state.p7Invite;
        if (!f || !String(f.email || "").includes("@")) {
            this.notif.add(_t("Type the email address of the person at the agency."), { type: "warning" });
            return;
        }
        const res = await this.call("p7_agency_invite", { vendor_id: f.vendor_id, email: f.email, name: f.name });
        if (res) { this.state.p7Invite = null; }
    },
    async p7Unlink(ag, lg) {
        await this.call("p7_agency_unlink", { vendor_id: ag.id, user_id: lg.id });
    },
    async p7OpenVendor(ag) {
        await this.action.doAction({
            type: "ir.actions.act_window", res_model: "pb.vendor", res_id: ag.id,
            views: [[false, "form"]], view_mode: "form", target: "current",
        });
    },
    async p7OpenSubmissions(ag) {
        await this.action.doAction({
            type: "ir.actions.act_window", res_model: "pb.hiring.agency.submission",
            name: _t("People %s put forward", ag.name),
            views: [[false, "list"], [false, "form"]], view_mode: "list,form",
            domain: [["vendor_id", "=", ag.id]], target: "current",
        });
    },
    p7Fig(ag, key) { return (ag.figures && ag.figures[key]) || 0; },
});
