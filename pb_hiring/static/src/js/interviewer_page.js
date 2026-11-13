/** @odoo-module **/
/**
 * RECRUIT P5 — the interviewer's scorecard page (`/hiring/f/<token>`).
 *
 * A courtesy layer on a plain HTML form (the page works with the script
 * blocked; the server checks every answer again):
 *   * the answers are kept on this device while they type (sessionStorage,
 *     per link), so a phone that locks in a corridor loses nothing;
 *   * the stars say what they mean ("Strong") as they light;
 *   * "3 of 5 answered" and a bar fill as questions are answered;
 *   * Send checks the required questions and the decision first, marks
 *     what is missing and scrolls to it, instead of a server round trip.
 */

const WORDS = { 1: "Poor", 2: "Below the bar", 3: "Fine", 4: "Strong", 5: "Exceptional" };

function store() {
    try { return window.sessionStorage; } catch { return null; }
}

function setupInterviewer(form) {
    const key = `pbiv.${form.dataset.token || "x"}`;
    const bar = document.getElementById("pbiv-bar");
    const count = document.getElementById("pbiv-count");
    const draftLine = document.getElementById("pbiv-draft");
    const questions = [...form.querySelectorAll(".pbiv-q[data-required]")];

    const answered = (q) => {
        const kind = q.dataset.kind;
        if (kind === "text") {
            const t = q.querySelector("textarea");
            return !!(t && t.value.trim());
        }
        return !!q.querySelector("input[type=radio]:checked");
    };

    const refresh = () => {
        const needed = questions.filter((q) => q.dataset.required === "1");
        const done = needed.filter(answered).length;
        for (const q of questions) {
            q.classList.toggle("is-done", answered(q));
            if (answered(q)) { q.classList.remove("is-missing"); }
        }
        if (bar) { bar.style.width = needed.length ? `${Math.round((done * 100) / needed.length)}%` : "100%"; }
        if (count) {
            count.textContent = done >= needed.length
                ? "Ready to send"
                : `${done} of ${needed.length} answered`;
        }
        for (const wrap of form.querySelectorAll(".pbiv-stars-wrap")) {
            const on = wrap.querySelector("input:checked");
            const word = wrap.querySelector(".pbiv-stars-word");
            if (word) { word.textContent = on ? WORDS[on.value] || "" : ""; }
        }
    };

    const save = () => {
        const s = store();
        if (!s) { return; }
        const data = {};
        for (const el of form.elements) {
            if (!el.name || el.type === "hidden") { continue; }
            if (el.type === "radio") {
                if (el.checked) { data[el.name] = el.value; }
            } else if (el.value) {
                data[el.name] = el.value;
            }
        }
        try {
            s.setItem(key, JSON.stringify(data));
            if (draftLine) { draftLine.textContent = "Kept on this device — nothing is lost if you close the page."; }
        } catch { /* a full or blocked storage is not a reason to stop */ }
    };

    const restore = () => {
        const s = store();
        if (!s) { return; }
        let data = null;
        try { data = JSON.parse(s.getItem(key) || "null"); } catch { data = null; }
        if (!data) { return; }
        for (const [name, value] of Object.entries(data)) {
            const radios = form.querySelectorAll(`input[type=radio][name="${name}"]`);
            if (radios.length) {
                if (![...radios].some((r) => r.checked)) {
                    for (const r of radios) { r.checked = r.value === value; }
                }
                continue;
            }
            const el = form.elements.namedItem(name);
            if (el && "value" in el && !el.value) { el.value = value; }
        }
    };

    // Hovering a star previews its word; leaving shows the chosen one.
    for (const wrap of form.querySelectorAll(".pbiv-stars-wrap")) {
        const word = wrap.querySelector(".pbiv-stars-word");
        for (const label of wrap.querySelectorAll(".pbiv-star")) {
            label.addEventListener("mouseenter", () => {
                const input = document.getElementById(label.getAttribute("for"));
                if (word && input) { word.textContent = WORDS[input.value] || ""; }
            });
        }
        wrap.addEventListener("mouseleave", refresh);
    }

    form.addEventListener("input", () => { refresh(); save(); });
    form.addEventListener("change", () => { refresh(); save(); });
    form.addEventListener("submit", (ev) => {
        const missing = questions.filter((q) => q.dataset.required === "1" && !answered(q));
        for (const q of questions) { q.classList.toggle("is-missing", missing.includes(q)); }
        if (missing.length) {
            ev.preventDefault();
            missing[0].scrollIntoView({ behavior: "smooth", block: "center" });
            const first = missing[0].querySelector("textarea, input");
            if (first) { first.focus({ preventScroll: true }); }
            return;
        }
        const s = store();
        if (s) { try { s.removeItem(key); } catch { /* ignore */ } }
        const btn = form.querySelector(".pbiv-send");
        if (btn) {
            btn.setAttribute("disabled", "disabled");
            const tx = btn.querySelector(".pbiv-send-tx");
            if (tx) { tx.textContent = "Sending…"; }
        }
    });

    restore();
    refresh();
    form.dataset.pbivReady = "1";
}

function boot() {
    const form = document.getElementById("pbiv-form");
    if (form && !form.dataset.pbivReady) { setupInterviewer(form); }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
} else {
    boot();
}
