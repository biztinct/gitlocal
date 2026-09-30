/** @odoo-module **/
/**
 * RECRUIT P2 — the public application page, made kind.
 *
 * No framework: the page must work inside any client's website (and inside
 * the Rize site frame). Everything here is a courtesy on top of a plain HTML
 * form — the SERVER re-checks every answer, files included.
 *
 *   * the progress line "N of M answered" ticks as answers land;
 *   * a question says what is wrong when you leave it (never while typing);
 *   * drop zones take a dragged file, show its name, and refuse a wrong kind
 *     or a too-large file before it is sent;
 *   * typed answers are kept in this tab (sessionStorage) so a failed send
 *     or a language switch never loses them — files are never kept;
 *   * the phone line shows the country code for the country chosen;
 *   * a long answer counts its words.
 *
 * Every sentence comes from the page (data-* attributes the server wrote in
 * the page's language), so there is no translation in this file.
 */

function store() {
    try { return window.sessionStorage; } catch { return null; }
}

function readDraft(key) {
    const s = store();
    if (!s || !key) { return {}; }
    try { return JSON.parse(s.getItem(key) || "{}") || {}; } catch { return {}; }
}

function writeDraft(key, data) {
    const s = store();
    if (!s || !key) { return; }
    try { s.setItem(key, JSON.stringify(data)); } catch { /* full or blocked: fine */ }
}

function dropDraft(key) {
    const s = store();
    if (!s || !key) { return; }
    try { s.removeItem(key); } catch { /* blocked: fine */ }
}

function fill(text, vals) {
    return String(text || "").replace(/\{(\w+)\}/g, (m, k) => (k in vals ? String(vals[k]) : m));
}

function words(text) {
    const t = String(text || "").trim();
    return t ? t.split(/\s+/).length : 0;
}

function setupForm(form) {
    const qs = [...form.querySelectorAll(".pba-q")];
    const key = form.dataset.draft;
    const preview = !!form.closest("[data-preview]");
    const bar = form.querySelector(".pba-bar > span");
    const progressT = form.querySelector(".pba-progress-t");
    const counted = qs.filter((q) => q.dataset.widget !== "consent");

    // ---------------------------------------------------------- answers
    function valueOf(q) {
        const w = q.dataset.widget;
        if (w === "choice" || w === "yes_no") {
            const on = q.querySelector("input[type=radio]:checked");
            return on ? on.value : "";
        }
        if (w === "multi") {
            return [...q.querySelectorAll("input[type=checkbox]:checked")].map((i) => i.value);
        }
        if (w === "consent") {
            const c = q.querySelector("input[type=checkbox]");
            return c && c.checked ? "1" : "";
        }
        if (w === "file" || w === "portfolio") {
            const f = q.querySelector("input[type=file]");
            const l = q.querySelector("input[type=url]");
            return (f && f.files && f.files.length ? "file" : "") || (l ? l.value.trim() : "");
        }
        const el = q.querySelector(".pba-in");
        return el ? el.value.trim() : "";
    }

    function answered(q) {
        const v = valueOf(q);
        return Array.isArray(v) ? v.length > 0 : !!v;
    }

    function progress() {
        const n = counted.filter(answered).length;
        const m = counted.length;
        if (progressT) { progressT.textContent = fill(form.dataset.progress, { n, m }); }
        if (bar) { bar.style.width = (m ? Math.round((n / m) * 100) : 0) + "%"; }
    }

    // ---------------------------------------------------------- checking
    function problem(q) {
        const w = q.dataset.widget;
        const v = valueOf(q);
        const empty = Array.isArray(v) ? !v.length : !v;
        if (empty) { return q.dataset.required ? q.dataset.err : ""; }
        if (w === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) { return form.dataset.errEmail; }
        if (w === "url" && !/^https?:\/\/\S+$/i.test(v)) { return form.dataset.errUrl; }
        if (w === "portfolio" && v !== "file" && !/^https?:\/\/\S+$/i.test(v)) { return form.dataset.errUrl; }
        if (w === "textarea") {
            const n = words(v);
            const lo = Number(q.dataset.min || 0);
            const hi = Number(q.dataset.max || 0);
            if ((lo && n < lo) || (hi && n > hi)) {
                return fill(form.dataset.errWords, { min: lo || 0, max: hi || "…", n });
            }
        }
        if (w === "file" || w === "portfolio") {
            const f = q.querySelector("input[type=file]");
            const file = f && f.files && f.files[0];
            if (file) {
                const mb = Number(q.dataset.maxmb || 5);
                const ok = (q.dataset.suffixes || "").split(",");
                const suffix = (file.name.split(".").pop() || "").toLowerCase();
                if (file.size > mb * 1024 * 1024) { return fill(form.dataset.errBig, { mb }); }
                if (!ok.includes(suffix)) { return form.dataset.errKind; }
            }
        }
        return "";
    }

    function show(q, text) {
        const err = q.querySelector(".pba-err");
        if (err) { err.textContent = text || ""; }
        q.classList.toggle("has-error", !!text);
    }

    function check(q) {
        const p = problem(q);
        show(q, p);
        return !p;
    }

    // ---------------------------------------------------------- the draft
    function saveDraft() {
        const data = {};
        for (const q of qs) {
            const w = q.dataset.widget;
            if (w === "file") { continue; }
            if (w === "portfolio") {
                const l = q.querySelector("input[type=url]");
                if (l && l.value) { data[q.dataset.key + "_link"] = l.value; }
                continue;
            }
            const v = valueOf(q);
            if (v && (!Array.isArray(v) || v.length)) { data[q.dataset.key] = v; }
        }
        writeDraft(key, data);
    }

    function restoreDraft() {
        const data = readDraft(key);
        for (const q of qs) {
            const w = q.dataset.widget;
            const k = q.dataset.key;
            if (w === "portfolio") {
                const l = q.querySelector("input[type=url]");
                if (l && !l.value && data[k + "_link"]) { l.value = data[k + "_link"]; }
                continue;
            }
            // The country arrives pre-chosen from the role's market; a person's
            // own pick (kept in the draft) wins over that.
            if (!(k in data) || (answered(q) && w !== "country")) { continue; }
            const v = data[k];
            if (w === "choice" || w === "yes_no") {
                const r = q.querySelector(`input[type=radio][value="${CSS.escape(String(v))}"]`);
                if (r) { r.checked = true; }
            } else if (w === "multi") {
                for (const c of q.querySelectorAll("input[type=checkbox]")) { c.checked = (v || []).includes(c.value); }
            } else if (w === "consent") {
                const c = q.querySelector("input[type=checkbox]");
                if (c) { c.checked = v === "1"; }
            } else {
                const el = q.querySelector(".pba-in");
                if (el && (!el.value || w === "country")) { el.value = v; }
            }
        }
    }

    // ---------------------------------------------------------- extras
    const country = form.querySelector(".pba-w-country select");
    const phoneHint = form.querySelector(".pba-phone-hint");
    function phone() {
        if (!country || !phoneHint) { return; }
        const opt = country.options[country.selectedIndex];
        const code = opt && opt.dataset.phone;
        phoneHint.textContent = code ? fill(form.dataset.phoneHint, { code }) : "";
    }

    function countWords(q) {
        const out = q.querySelector(".pba-words-n");
        const el = q.querySelector("textarea");
        if (out && el) { out.textContent = fill(form.dataset.words, { n: words(el.value) }); }
    }

    function fileName(q) {
        const f = q.querySelector("input[type=file]");
        const name = q.querySelector(".pba-drop-name");
        const t = q.querySelector(".pba-drop-t");
        const drop = q.querySelector(".pba-drop");
        const file = f && f.files && f.files[0];
        if (name) { name.textContent = file ? `${file.name} · ${Math.max(1, Math.round(file.size / 1024))} KB` : ""; }
        if (t && t.dataset.change) {
            if (!t.dataset.first) { t.dataset.first = t.textContent; }
            t.textContent = file ? t.dataset.change : t.dataset.first;
        }
        if (drop) { drop.classList.toggle("has-file", !!file); }
    }

    // The chosen rows light up (a class, not :has() — the page must style in
    // every browser a candidate brings).
    function marks() {
        for (const lab of form.querySelectorAll(".pba-choice, .pba-consent")) {
            const inp = lab.querySelector("input");
            lab.classList.toggle("is-checked", !!(inp && inp.checked));
        }
    }

    // ---------------------------------------------------------- wiring
    for (const q of qs) {
        q.addEventListener("input", () => {
            if (q.classList.contains("has-error") && !problem(q)) { show(q, ""); }
            if (q.dataset.widget === "textarea") { countWords(q); }
            progress();
            saveDraft();
        });
        q.addEventListener("change", () => {
            marks();
            if (q.dataset.widget === "file" || q.dataset.widget === "portfolio") {
                fileName(q);
                check(q);
            } else if (q.classList.contains("has-error")) {
                check(q);
            }
            progress();
            saveDraft();
        });
        // On leaving a question — never while somebody is still typing.
        q.addEventListener("focusout", (ev) => {
            if (q.contains(ev.relatedTarget)) { return; }
            const w = q.dataset.widget;
            if (["choice", "yes_no", "multi", "consent", "file", "portfolio"].includes(w)) { return; }
            if (valueOf(q)) { check(q); }
        });
        const drop = q.querySelector(".pba-drop");
        const input = drop && drop.querySelector("input[type=file]");
        if (drop && input) {
            drop.addEventListener("dragover", (ev) => { ev.preventDefault(); drop.classList.add("is-over"); });
            drop.addEventListener("dragleave", () => drop.classList.remove("is-over"));
            drop.addEventListener("drop", (ev) => {
                ev.preventDefault();
                drop.classList.remove("is-over");
                if (ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files.length) {
                    try {
                        input.files = ev.dataTransfer.files;
                    } catch { return; }
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                }
            });
        }
        if (q.dataset.widget === "textarea") { countWords(q); }
    }
    if (country) { country.addEventListener("change", phone); }

    const summary = form.querySelector(".pba-summary");
    const summaryT = form.querySelector(".pba-summary-t");
    const send = form.querySelector(".pba-send");
    form.addEventListener("submit", (ev) => {
        if (preview) { ev.preventDefault(); return; }
        const bad = qs.filter((q) => !check(q));
        if (bad.length) {
            ev.preventDefault();
            if (summary && summaryT) {
                summaryT.textContent = bad.length === 1 ? form.dataset.summaryOne
                    : fill(form.dataset.summaryMany, { n: bad.length });
                summary.hidden = false;
            }
            const first = bad[0];
            first.scrollIntoView({ behavior: "smooth", block: "center" });
            const el = first.querySelector("input:not([type=hidden]), select, textarea");
            if (el) { try { el.focus({ preventScroll: true }); } catch { el.focus(); } }
            return;
        }
        saveDraft();
        if (send) {
            send.disabled = true;
            send.classList.add("is-busy");
            const label = send.querySelector("span");
            if (label && form.dataset.sending) { label.textContent = form.dataset.sending; }
        }
    });

    restoreDraft();
    marks();
    phone();
    for (const q of qs) {
        if (q.dataset.widget === "textarea") { countWords(q); }
        if (q.dataset.widget === "file" || q.dataset.widget === "portfolio") { fileName(q); }
    }
    progress();
    // A server refusal: take the person to the first answer that needs a look.
    const firstErr = form.querySelector(".pba-q.has-error");
    if (firstErr) { firstErr.scrollIntoView({ block: "center" }); }
}

function start() {
    const done = document.querySelector("[data-pba-done]");
    if (done) { dropDraft(done.dataset.draft); }
    for (const form of document.querySelectorAll("form.pba-form")) {
        if (!form.dataset.pbaReady) {
            form.dataset.pbaReady = "1";
            setupForm(form);
        }
    }
}

if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
}
