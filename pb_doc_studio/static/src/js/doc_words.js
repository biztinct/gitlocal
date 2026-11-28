/** @odoo-module **/
/**
 * Small shared helpers of the Document studio screens.
 */
import { _t } from "@web/core/l10n/translation";

export const FACADE = "pb.doc.studio";

export function esc(value) {
    return String(value == null ? "" : value)
        .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

export function fold(value) {
    return String(value || "").normalize("NFD").replace(/[̀-ͯ]/g, "")
        .replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase().trim();
}

export function isMac() {
    return /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "");
}
export function modKey() { return isMac() ? "⌘" : "Ctrl "; }

/** "3 minutes ago" — from a server UTC string ("2026-11-22 04:40:05"). */
export function ago(utc) {
    if (!utc) { return ""; }
    const then = new Date(String(utc).replace(" ", "T") + "Z").getTime();
    if (!then) { return ""; }
    const s = Math.max(0, Math.round((Date.now() - then) / 1000));
    if (s < 60) { return _t("just now"); }
    const m = Math.round(s / 60);
    if (m < 60) { return m === 1 ? _t("a minute ago") : _t("%s minutes ago", m); }
    const h = Math.round(m / 60);
    if (h < 24) { return h === 1 ? _t("an hour ago") : _t("%s hours ago", h); }
    const d = Math.round(h / 24);
    if (d < 45) { return d === 1 ? _t("yesterday") : _t("%s days ago", d); }
    return new Date(then).toLocaleDateString();
}

/** Browser storage that never throws (private windows, blocked storage). */
export const store = {
    get(key) {
        try { const raw = window.localStorage.getItem(key); return raw ? JSON.parse(raw) : null; }
        catch { return null; }
    },
    set(key, value) {
        try { window.localStorage.setItem(key, JSON.stringify(value)); return true; }
        catch { return false; }
    },
    drop(key) {
        try { window.localStorage.removeItem(key); } catch { /* storage off: nothing kept */ }
    },
};

export function errorText(e, fallback) {
    return (e && e.data && e.data.message) || (e && e.message && !String(e.message).includes("RPC_ERROR") && e.message) || fallback;
}

/** Read a file as base64 (no "data:" prefix). */
export function readBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (ev) => resolve(String(ev.target.result || "").split(",")[1] || "");
        reader.onerror = () => reject(new Error("read"));
        reader.readAsDataURL(file);
    });
}
