/** @odoo-module **/
/**
 * ORG CHART P4 — the Export menu, the share link and the arrival payload,
 * installed onto PbOrgChart (`installExport`) beside P2's and P3's halves.
 *
 *  * PICTURE (PNG). No library: the cards, lines, lane and title are painted
 *    straight onto a canvas from the layout the screen already holds (the same
 *    positions, the same edge path strings through `Path2D`, the same colours
 *    read from the page's own tokens), then saved as a PNG. Photos are
 *    `/web/image` on this origin, so they draw without tainting the canvas; one
 *    that has not loaded within 2 s becomes initials. 2× for print quality,
 *    smaller when a very wide chart would pass the browser's canvas limit.
 *    "Export this branch as a picture" paints one person's team only. A plan
 *    is painted as its projection (amber outlines, dashed red "came from"
 *    lines) and the file name carries the plan's name.
 *  * PDF. The print dialog on a print-only view: one page per team (the Teams
 *    grouping), A3 landscape, "Save as PDF" in the dialog. The `@page` rule is
 *    put in only for that print and taken out after, so no other print in the
 *    app changes.
 *  * SPREADSHEET. The server's full list (`export_rows`), not what a cut chart
 *    has loaded; the last row says when and how many.
 *  * SHARE. "Copy a link to this view": the People hub address with the view
 *    in the query string (`oc=1&oc_focus=&oc_view=&oc_color=&oc_as_of=&
 *    oc_plan=`). Sign-in is still required (ledger D9). The QUERY string, not
 *    a hash: the sign-in page keeps the query in its `redirect` and drops a
 *    hash. The address is read once, when this file loads — before the web
 *    client rewrites it — and it asks the hub to open on the Org chart.
 *  * ARRIVAL. ⌘K rows say what they meant in `pb_focus` ("me", "plan",
 *    "suggest"); a link says it in the query. `parseArrival` turns either into
 *    one object; the chart applies it once.
 */
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { ic } from "@pb_import_kit/js/import_icons";
import { descendants, directCount, totalCount, isUnloaded } from "@pb_orgchart/js/orgchart_layout";
import { parseArrival } from "@pb_orgchart/js/orgchart_arrival";

export { parseArrival };

const { DateTime } = luxon;

const MAX_SIDE = 16000;          // the browser refuses a bigger canvas side
const MAX_AREA = 120e6;          // …or more pixels than this (safe margin)
const PHOTO_WAIT = 2000;
const HUB_PATH = "/bizapp/action-pb_people_hub.action_pb_people_hub";

// =================================================================== arrival
/** The address this page was opened with, read before the router rewrites it. */
let BOOT = null;
try {
    BOOT = parseArrival("", window.location.search);
    if (BOOT) {
        // the hub opens on the lens it last showed: make that the Org chart
        window.localStorage.setItem("pbhub.people.lens.v1", "orgchart");
    }
} catch {
    BOOT = null;
}

const TAKEN = new WeakSet();

/** One arrival, applied once: the link's first, else the hub's ⌘K focus. */
export function takeArrival(hubArrival) {
    if (BOOT) { const b = BOOT; BOOT = null; return b; }
    if (hubArrival && typeof hubArrival === "object" && !TAKEN.has(hubArrival)) {
        TAKEN.add(hubArrival);
        return parseArrival(hubArrival.focus, "");
    }
    return null;
}

/** Days from today to an ISO day, clamped to the time machine's range. */
export function daysFromToday(iso) {
    const d = DateTime.fromISO(iso);
    if (!d.isValid) { return 0; }
    const n = Math.round(d.startOf("day").diff(DateTime.local().startOf("day"), "days").days);
    return Math.max(-365, Math.min(90, n));
}

// ===================================================================== files
function slug(s) {
    return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D")
        .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
}

function download(blob, name) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
}

function loadImage(src, wait) {
    return new Promise((res) => {
        const img = new Image();
        let done = false;
        const fin = (v) => { if (!done) { done = true; res(v); } };
        img.onload = () => fin(img);
        img.onerror = () => fin(null);
        setTimeout(() => fin(null), wait);
        img.src = src;
    });
}

/** Ellipsis to fit `max` px in the canvas's current font. */
function fit(ctx, text, max) {
    text = String(text || "");
    if (ctx.measureText(text).width <= max) { return text; }
    let lo = 0;
    let hi = text.length;
    while (lo < hi) {
        const mid = (lo + hi + 1) >> 1;
        if (ctx.measureText(text.slice(0, mid) + "…").width <= max) { lo = mid; } else { hi = mid - 1; }
    }
    return text.slice(0, lo) + "…";
}

const TAG_TONES = {
    amber: ["#FEF3C7", "#B45309"], green: ["#D9F2E4", "#0F7B4F"], rose: ["#FFE4E8", "#DC2655"],
    blue: ["#DBEAFE", "#2563EB"], p: ["#EDEAF8", "#5A4BB0"], "": ["#EDF0F4", "#475569"],
};

class OcExport {
    // ============================================================ names
    get companyName() {
        try { return (user.activeCompany && user.activeCompany.name) || ""; } catch { return ""; }
    }

    get todayIso() { return DateTime.local().toISODate(); }

    get todayLabel() { return DateTime.local().toLocaleString({ day: "numeric", month: "short", year: "numeric" }); }

    /** org-chart-<company>[-<plan or person>]-<date> */
    fileBase(extra) {
        const parts = ["org-chart", slug(this.companyName)];
        if (this.state.plan && this.state.plan.name) { parts.push(slug(this.state.plan.name)); }
        if (extra) { parts.push(slug(extra)); }
        parts.push(this.state.asOf ? this.asOfIso(this.state.asOf) : this.todayIso);
        return parts.filter(Boolean).join("-");
    }

    /** What the file shows, in one line under the title. */
    get exportSubline() {
        const s = this.state;
        if (s.plan && s.plan.name) {
            return _t("Plan “%(n)s” · %(s)s · how the chart looks with it", { n: s.plan.name, s: s.plan.state_label || _t("Draft") });
        }
        if (s.plan) { return _t("Planned changes · not live yet"); }
        if (s.asOf) { return _t("As at %(d)s", { d: this.fmtDayOffset(s.asOf) }); }
        return _t("As at %(d)s", { d: this.todayLabel });
    }

    get exportFooter() {
        return _t("Exported from Payobook on %(d)s", { d: this.todayLabel });
    }

    // ============================================================ PNG
    exportBranch(id) {
        this.state.ctx = null;
        return this.exportPng(id);
    }

    async exportPng(branchId = null) {
        this.state.menu = null;
        if (this._exporting) { return; }
        if (!this.canvasView) {
            this.setView("tree");
            await new Promise((r) => setTimeout(r, 60));
        }
        if (!this.lay) { return; }
        this._exporting = true;
        this.state.exporting = "png";
        try {
            const res = await this._paintPng(branchId);
            if (res) {
                download(res.blob, res.name);
                const note = res.scale < 1
                    ? " " + _t("The chart is very wide, so the picture is smaller than print quality — export one team for a sharper one.")
                    : "";
                this.notif.add(_t("Picture saved as %(f)s.", { f: res.name }) + note, { type: "success" });
            }
        } catch (e) {
            console.warn("pb_orgchart: picture failed", e);
            this.notif.add(_t("The picture could not be made. Try again, or export one team."), { type: "danger" });
        } finally {
            this._exporting = false;
            this.state.exporting = null;
        }
    }

    /** Paint the chart (or one branch) onto a canvas; resolve {blob, name, scale}. */
    async _paintPng(branchId) {
        const lay = this.lay;
        const idx = this.idx;
        let ids;
        let head = this.companyName ? _t("%(c)s · Org chart", { c: this.companyName }) : _t("Org chart");
        let extra = "";
        if (branchId) {
            const n = this.nodeOf(branchId);
            if (!n) { return null; }
            ids = [n.id, ...descendants(idx, n.id).map((d) => d.id)].filter((i) => lay.pos.has(i));
            head = _t("%(p)s's team", { p: this.nameOf(n) });
            extra = n.name || n.title;
        } else {
            ids = [...lay.pos.keys()].filter((i) => i !== lay.moreId);
        }
        const set = new Set(ids);
        const P = (id) => lay.pos.get(id);
        let x0 = Infinity; let y0 = Infinity; let x1 = -Infinity; let y1 = -Infinity;
        const grow = (x, y, w, h) => { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x + w); y1 = Math.max(y1, y + h + 14); };
        for (const id of ids) { const p = P(id); grow(p.x, p.y, p.w, p.h); }
        const withLane = !branchId && lay.lane;
        if (withLane) { grow(lay.lane.x, lay.lane.y, lay.lane.w, lay.lane.h); }
        if (!branchId && lay.moreId && lay.pos.get(lay.moreId)) { const p = lay.pos.get(lay.moreId); grow(p.x, p.y, p.w, p.h); }
        if (x0 === Infinity) { return null; }
        const PAD = 48;
        const HEAD = 92;
        const FOOT = 44;
        const W = Math.max(640, x1 - x0 + PAD * 2);
        const H = y1 - y0 + PAD * 2 + HEAD + FOOT;
        const scale = Math.min(2, Math.sqrt(MAX_AREA / (W * H)), MAX_SIDE / W, MAX_SIDE / H);

        // photos and icons first (same origin / data URLs: the canvas stays clean)
        const photos = new Map();
        const want = ids.map((i) => this.nodeOf(i)).filter((n) => n && n.avatar && !n.isRole);
        await Promise.all(want.map(async (n) => {
            const img = await loadImage(n.avatar, PHOTO_WAIT);
            if (img) { photos.set(n.id, img); }
        }));
        const css = getComputedStyle(this.root.el);
        const tok = (k, d) => (css.getPropertyValue(k) || "").trim() || d;
        const C = {
            ink: tok("--oc-ink", "#1B1733"), ink2: tok("--oc-ink2", "#3F3B57"), muted: tok("--oc-muted", "#6F6B86"),
            line: tok("--oc-line", "#E4E5F1"), line2: tok("--oc-line2", "#D6D7E8"), p: tok("--oc-p", "#5A4BB0"),
            amber: tok("--oc-amber", "#B45309"), amberLine: tok("--oc-amber-line", "#FCD34D"), amberSoft: tok("--oc-amber-soft", "#FEF3C7"),
            rose: tok("--oc-rose", "#DC2655"), blue: tok("--oc-blue", "#2563EB"), slate: tok("--oc-slate", "#64748B"),
        };
        const iconImgs = new Map();
        const iconOf = async (name, color) => {
            const k = name + color;
            if (!iconImgs.has(k)) {
                const svg = String(ic(name, 24)).replace(/currentColor/g, color)
                    .replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ');
                iconImgs.set(k, await loadImage("data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg), 1000));
            }
            return iconImgs.get(k);
        };
        const cards = (this.cards || []).filter((c) => set.has(c.id));
        for (const c of cards) {
            for (const t of c.tags) { await iconOf(t.ic, (TAG_TONES[t.cls] || TAG_TONES[""])[1]); }
            if (c.n.isRole) { await iconOf("briefcase", C.amber); }
        }

        const cv = document.createElement("canvas");
        cv.width = Math.round(W * scale);
        cv.height = Math.round(H * scale);
        const ctx = cv.getContext("2d");
        const font = css.fontFamily || "system-ui, sans-serif";
        ctx.scale(scale, scale);
        ctx.fillStyle = "#fff";
        ctx.fillRect(0, 0, W, H);

        // title
        ctx.textBaseline = "alphabetic";
        ctx.fillStyle = C.ink;
        ctx.font = `700 24px ${font}`;
        ctx.fillText(fit(ctx, head, W - PAD * 2), PAD, PAD + 22);
        ctx.fillStyle = C.muted;
        ctx.font = `500 13px ${font}`;
        let sub = this.exportSubline;
        if (branchId) {
            const n = this.nodeOf(branchId);
            const t = totalCount(idx, n);
            sub = (t === 1 ? _t("1 person") : _t("%(n)s people", { n: this.fmtInt(t) })) + " · " + sub;
        } else {
            sub = this.headline + " · " + sub;
        }
        ctx.fillText(fit(ctx, sub, W - PAD * 2), PAD, PAD + 46);
        if (this.state.plan) {
            ctx.fillStyle = C.amber;
            ctx.fillText(fit(ctx, _t("Amber outline: changed in the plan · dashed red line: where they came from"), W - PAD * 2), PAD, PAD + 66);
        }

        ctx.save();
        ctx.translate(PAD - x0, PAD + HEAD - y0);
        // lane box
        if (withLane) {
            const L = lay.lane;
            ctx.save();
            ctx.setLineDash([6, 5]);
            ctx.strokeStyle = C.line2;
            ctx.fillStyle = "#FAFAFD";
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.roundRect(L.x, L.y, L.w, L.h, 16);
            ctx.fill();
            ctx.stroke();
            ctx.restore();
            ctx.fillStyle = C.muted;
            ctx.font = `700 11px ${font}`;
            ctx.fillText(fit(ctx, this.laneTitle.toUpperCase(), L.w - 24), L.x + 14, L.y + 22);
        }
        // lines
        ctx.lineCap = "round";
        for (const e of this.edgeList || []) {
            if (!set.has(e.id) || !set.has(e.from)) { continue; }
            const path = new Path2D(e.d);
            ctx.save();
            if (e.ghost) { ctx.strokeStyle = C.rose; ctx.globalAlpha = 0.7; ctx.lineWidth = 1.8; ctx.setLineDash([3, 4]); }
            else if (e.dot) { ctx.strokeStyle = C.amber; ctx.lineWidth = 1.6; ctx.setLineDash([5, 5]); }
            else { ctx.strokeStyle = C.line2; ctx.lineWidth = 1.6; }
            ctx.stroke(path);
            ctx.restore();
        }
        // cards
        const compact = this.state.compact;
        const av = compact ? 30 : 40;
        for (const c of cards) {
            const n = c.n;
            const fut = !!n.future;
            ctx.save();
            if (fut) { ctx.globalAlpha = 0.62; }
            ctx.shadowColor = "rgba(30, 27, 46, .07)";
            ctx.shadowBlur = 4;
            ctx.shadowOffsetY = 1;
            ctx.fillStyle = n.isRole ? "#FFFCF2" : fut ? "#F7FAFF" : "#fff";
            ctx.beginPath();
            ctx.roundRect(c.x, c.y, c.w, c.h, 14);
            ctx.fill();
            ctx.shadowColor = "transparent";
            ctx.lineWidth = 1;
            ctx.strokeStyle = n.isRole ? C.amberLine : fut ? C.blue : C.line;
            if (n.isRole || fut) { ctx.setLineDash([5, 4]); }
            ctx.stroke();
            ctx.setLineDash([]);
            if (n.changed) {
                ctx.strokeStyle = C.amber;
                ctx.lineWidth = 2.5;
                ctx.beginPath();
                ctx.roundRect(c.x - 1, c.y - 1, c.w + 2, c.h + 2, 15);
                ctx.stroke();
            }
            // avatar
            const ax = c.x + (compact ? 10 : 12);
            const ay = c.y + (compact ? 11 : 12);
            ctx.beginPath();
            ctx.roundRect(ax, ay, av, av, compact ? 9 : 12);
            if (n.isRole) {
                ctx.fillStyle = C.amberSoft;
                ctx.fill();
                const ii = iconImgs.get("briefcase" + C.amber);
                if (ii) { ctx.drawImage(ii, ax + av / 2 - 9, ay + av / 2 - 9, 18, 18); }
            } else if (photos.has(n.id)) {
                ctx.save();
                ctx.clip();
                ctx.drawImage(photos.get(n.id), ax, ay, av, av);
                ctx.restore();
            } else {
                ctx.fillStyle = this.colorOf(n);
                ctx.fill();
                ctx.fillStyle = "#fff";
                ctx.font = `700 ${compact ? 11 : 13}px ${font}`;
                ctx.textAlign = "center";
                ctx.fillText(n.ini || "", ax + av / 2, ay + av / 2 + (compact ? 4 : 5));
                ctx.textAlign = "left";
            }
            // text
            const tx = ax + av + 10;
            const tw = c.x + c.w - tx - 10;
            ctx.fillStyle = C.ink;
            ctx.font = `700 ${compact ? 12.5 : 13.5}px ${font}`;
            ctx.fillText(fit(ctx, this.nameOf(n), tw), tx, ay + (compact ? 12 : 14));
            ctx.fillStyle = C.ink2;
            ctx.font = `400 ${compact ? 11 : 12}px ${font}`;
            ctx.fillText(fit(ctx, n.title, tw), tx, ay + (compact ? 26 : 30));
            if (!compact) {
                ctx.fillStyle = this.deptColor.get(n.dept_id) || C.slate;
                ctx.fillRect(tx, ay + 40, 7, 7);
                ctx.fillStyle = C.muted;
                ctx.font = `400 11px ${font}`;
                ctx.fillText(fit(ctx, (n.dept || "—") + " · " + (n.loc || ""), tw - 12), tx + 12, ay + 47);
                // tags
                let gx = c.x + 12;
                const gy = ay + av + 8;
                ctx.font = `600 10.5px ${font}`;
                for (const t of c.tags) {
                    const [bg, fg] = TAG_TONES[t.cls] || TAG_TONES[""];
                    const label = fit(ctx, t.text, c.x + c.w - 12 - gx - 26);
                    const wv = ctx.measureText(label).width + 26;
                    if (gx + wv > c.x + c.w - 8) { break; }
                    ctx.fillStyle = bg;
                    ctx.beginPath();
                    ctx.roundRect(gx, gy, wv, 19, 9.5);
                    ctx.fill();
                    const ii = iconImgs.get(t.ic + fg);
                    if (ii) { ctx.drawImage(ii, gx + 6, gy + 4, 11, 11); }
                    ctx.fillStyle = fg;
                    ctx.fillText(label, gx + 20, gy + 13.5);
                    gx += wv + 5;
                }
            }
            ctx.restore();
            // the fold: +N where a team is folded
            if (c.hasTeam && (c.folded || (branchId && isUnloaded(idx, n)))) {
                const label = "+" + this.fmtInt(c.total);
                ctx.font = `700 11px ${font}`;
                const pw = Math.max(26, ctx.measureText(label).width + 16);
                const side = c.stk || this.state.view === "lr";
                const px = side ? c.x + c.w - pw / 2 : c.x + c.w / 2 - pw / 2;
                const py = side ? c.y + c.h / 2 - 12 : c.y + c.h - 12;
                ctx.fillStyle = "#fff";
                ctx.strokeStyle = C.line2;
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.roundRect(px, py, pw, 24, 12);
                ctx.fill();
                ctx.stroke();
                ctx.fillStyle = C.p;
                ctx.textAlign = "center";
                ctx.fillText(label, px + pw / 2, py + 16);
                ctx.textAlign = "left";
            }
        }
        // the lane's "+N more" tile
        if (!branchId && this.moreTile) {
            const m = this.moreTile;
            ctx.fillStyle = "#fff";
            ctx.strokeStyle = C.line2;
            ctx.setLineDash([5, 4]);
            ctx.beginPath();
            ctx.roundRect(m.x, m.y, m.w, m.h, 14);
            ctx.fill();
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.fillStyle = C.p;
            ctx.font = `700 15px ${font}`;
            ctx.textAlign = "center";
            ctx.fillText(this.moreLabel(m.n), m.x + m.w / 2, m.y + m.h / 2 + 5);
            ctx.textAlign = "left";
        }
        ctx.restore();
        // footer
        ctx.fillStyle = C.muted;
        ctx.font = `500 12px ${font}`;
        ctx.fillText(this.exportFooter, PAD, H - 20);

        const blob = await new Promise((res) => cv.toBlob(res, "image/png"));
        if (!blob) { throw new Error("canvas refused"); }
        return { blob, name: this.fileBase(branchId ? extra : "") + ".png", scale };
    }

    // ============================================================ PDF
    get printTeams() {
        void this.state.rev;
        return this.teamGroups.map((g) => ({
            k: g.k, name: g.name, color: g.color, sub: g.sub,
            rows: g.list.map((n) => ({
                id: n.id, n, name: this.nameOf(n), title: n.isRole ? n.title : n.title,
                mgr: this.listMgr(n), loc: n.loc, direct: n.isRole ? "" : (directCount(this.idx, n) || ""),
                lead: g.lead === n, note: this.leadNote(g, n), changed: !!n.changed,
            })),
        }));
    }

    get printHead() {
        return this.companyName ? _t("%(c)s · Org chart", { c: this.companyName }) : _t("Org chart");
    }

    async exportPdf() {
        this.state.menu = null;
        if (this._exporting) { return; }
        this._exporting = true;
        this.state.printPdf = true;
        const html = document.documentElement;
        const style = document.createElement("style");
        style.textContent = "@page { size: A3 landscape; margin: 12mm; }";
        // The print view is drawn by the template, then copied to a sheet
        // that sits straight on <body>: inside the app, the page's fixed
        // heights and hidden overflow would cut a long print to one page.
        const host = document.createElement("div");
        host.className = "pboc-print-host";
        let pages = 0;
        try {
            await new Promise((r) => setTimeout(r, 80));     // let the print view render
            const src = this.root.el && this.root.el.querySelector(".pboc-print-src");
            if (!src) { throw new Error("no print view"); }
            host.innerHTML = src.innerHTML;
            pages = host.querySelectorAll(".pboc-pp").length;
            document.body.appendChild(host);
            html.dataset.pbocPrint = "teams";
            document.head.appendChild(style);
            if (this.root.el) { this.root.el.dataset.printPages = pages; }
            window.print();
        } catch (e) {
            console.warn("pb_orgchart: print view failed", e);
            this.notif.add(_t("The print view could not be made. Try again."), { type: "danger" });
            pages = -1;
        } finally {
            setTimeout(() => {
                delete html.dataset.pbocPrint;
                style.remove();
                host.remove();
                this.state.printPdf = false;
                this._exporting = false;
            }, 400);
        }
        if (pages < 0) { return; }
        this.notif.add(pages === 1 ? _t("Print view made — 1 page. Choose Save as PDF in the print dialog to keep it.")
                                   : _t("Print view made — %(n)s pages, one per team. Choose Save as PDF in the print dialog to keep it.", { n: pages }),
                       { type: "info" });
    }

    // ============================================================ spreadsheet
    async exportCsv() {
        this.state.menu = null;
        if (this._exporting) { return; }
        this._exporting = true;
        this.state.exporting = "csv";
        let res = null;
        try {
            const kw = this.chartKw();
            delete kw.expand;
            res = await this.orm.call("pb.orgchart", "export_rows", [], kw);
        } catch (e) {
            console.warn("pb_orgchart: spreadsheet failed", e);
            res = null;
        } finally {
            this._exporting = false;
            this.state.exporting = null;
        }
        if (!res || res.error) {
            this.notif.add((res && res.error) || _t("The spreadsheet could not be made. Try again."), { type: "danger" });
            return;
        }
        const esc = (v) => '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"';
        const lines = [res.columns.map(esc).join(",")];
        for (const r of res.rows) { lines.push(r.map(esc).join(",")); }
        let note = _t("Exported from Payobook on %(d)s · %(n)s people", { d: this.todayLabel, n: this.fmtInt(res.people) });
        if (res.roles) { note += " · " + (res.roles === 1 ? _t("1 open role") : _t("%(n)s open roles", { n: this.fmtInt(res.roles) })); }
        if (res.plan_name) { note += " · " + _t("plan “%(p)s”, not live yet", { p: res.plan_name }); }
        else if (this.state.plan) { note += " · " + _t("planned changes, not live yet"); }
        if (res.as_of) { note += " · " + _t("as at %(d)s", { d: this.fmtDayOffset(this.state.asOf) }); }
        lines.push("");
        lines.push(esc(note));
        const name = this.fileBase("") + ".csv";
        download(new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8;" }), name);
        this.notif.add(_t("Spreadsheet saved with %(n)s people.", { n: this.fmtInt(res.people) }), { type: "success" });
    }

    // ============================================================ share
    get shareUrl() {
        const s = this.state;
        const q = new URLSearchParams();
        q.set("oc", "1");
        const sel = s.sel ? this.nodeOf(s.sel) : null;
        if (sel && sel.empId) { q.set("oc_focus", String(sel.empId)); }
        q.set("oc_view", s.view);
        q.set("oc_color", s.colorBy);
        if (s.plan && s.plan.plan_id) { q.set("oc_plan", String(s.plan.plan_id)); }
        else if (s.asOf) { q.set("oc_as_of", this.asOfIso(s.asOf)); }
        const path = this.props.embedded ? HUB_PATH : window.location.pathname;
        return window.location.origin + path + "?" + q.toString();
    }

    async copyLink() {
        this.state.menu = null;
        const url = this.shareUrl;
        let ok = false;
        try {
            await navigator.clipboard.writeText(url);
            ok = true;
        } catch {
            try {
                const ta = document.createElement("textarea");
                ta.value = url;
                ta.setAttribute("readonly", "");
                ta.style.position = "fixed";
                ta.style.opacity = "0";
                document.body.appendChild(ta);
                ta.select();
                ok = document.execCommand("copy");
                ta.remove();
            } catch {
                ok = false;
            }
        }
        this._lastLink = url;
        if (this.root.el) { this.root.el.dataset.lastLink = url; }
        if (ok) {
            this.notif.add(_t("Link copied. Anyone in the company who can see the chart can open it."), { type: "success" });
        } else {
            this.notif.add(_t("The link could not be copied here. Copy it from this message: %(u)s", { u: url }),
                           { type: "warning", sticky: true });
        }
    }

    // ============================================================ arrival
    /** Before the first read: the day or the plan the arrival asks for. */
    _arrivalBeforeLoad() {
        const a = this._arrival;
        if (!a) { return; }
        if (a.view) { this.state.view = a.view; }
        if (a.color) { this.state.colorBy = a.color; }
        if (a.plan) { this.state.plan = { plan_id: a.plan, editable: false }; }
        else if (a.asOf) {
            const d = daysFromToday(a.asOf);
            this.state.asOf = d;
            this.state.asOfDraft = d;
        }
    }

    /** After the first draw: who to focus, which mode to open. */
    async _arrivalAfterLoad() {
        const a = this._arrival;
        this._arrival = null;
        if (!a || this.state.failed) { return; }
        if (a.plan && this.state.plan) { this.state.side = "__changes"; }
        if (a.focus) {
            const n = this.nodeOf(String(a.focus));
            if (n) { this.select(n.id); }
            else if (!a.plan && !a.asOf) {
                // on a cut chart the person may sit in a team that is not loaded
                try {
                    await this._reveal(a.focus);
                } catch {
                    /* an id the reader may not see simply does not focus */
                }
            }
        } else if (a.me) {
            if (this.data && this.data.me) { this.findMe(); }
            else { this.notif.add(_t("You are not on the chart — no employee record is linked to your login."), { type: "info" }); }
        }
        if (a.mode === "plan" && this.mayWrite && !this.state.plan && !this.state.asOf) { await this.startPlan(); }
        if (a.mode === "suggest") {
            if (this.canSuggest) { this.openSuggest(); }
            else if (this.mayWrite) { this.notif.add(_t("Everyone here already has a manager or a team — nothing to suggest."), { type: "info" }); }
        }
    }

    /** Load the managers' teams down to `empId` on a cut chart, then focus it. */
    async _reveal(empId) {
        if (!this.data || !this.data.truncated) { return; }
        const chainIds = await this.orm.call("pb.orgchart", "chain_of", [empId]);
        for (const mid of chainIds || []) {
            const m = this.nodeOf(String(mid));
            if (m && isUnloaded(this.idx, m)) { await this.loadBranch(m); }
        }
        const n = this.nodeOf(String(empId));
        if (n) { this.relayout(); this.select(n.id); }
    }
}

/** Copy OcExport's methods and getters onto the chart component. */
export function installExport(Cls) {
    const desc = Object.getOwnPropertyDescriptors(OcExport.prototype);
    delete desc.constructor;
    Object.defineProperties(Cls.prototype, desc);
}
