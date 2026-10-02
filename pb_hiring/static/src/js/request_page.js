/** @odoo-module **/
/**
 * RECRUIT P3 — the manager's one-page hiring request (`/hiring/r/<token>`).
 *
 * THE HERO MOMENT: it saves as they type. No framework (the page lives
 * inside any client's website); everything here is a courtesy on top of a
 * plain HTML form that posts every field to /send, so the page still works
 * with the script blocked.
 *
 *   * each field saves 700 ms after the last keystroke (and on leaving it),
 *     through the JSON door `/save`; the answer carries the new count, the
 *     ticks and the budget sentence, so the page never guesses;
 *   * "Saved · 10:42" / "Saving…" / "Not saved — trying again" says what
 *     is true, and a failed save is retried with a growing wait;
 *   * the headcount stepper, the Confidential switch, the choice chips;
 *   * a pending save is flushed before "Send in" posts the form.
 *
 * No words are made up here: the sentences come from the server (the
 * budget note, the missing list) or are the page's own.
 */

const DEBOUNCE_MS = 700;

function now() {
    const d = new Date();
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function setupRequest(form) {
    const url = form.dataset.save;
    const saved = document.getElementById("pbrq-saved");
    const bar = document.getElementById("pbrq-bar");
    const count = document.getElementById("pbrq-answered");
    const budget = document.getElementById("pbrq-budget");
    const missing = document.getElementById("pbrq-missing");
    const timers = new Map();
    const pending = new Map();
    let inflight = null;
    let retry = 0;
    let closed = false;

    const say = (text, tone = "") => {
        if (!saved) { return; }
        saved.textContent = text;
        saved.className = "pbrq-saved" + (tone ? " is-" + tone : "");
    };

    const valueOf = (el) => {
        if (el.type === "checkbox") { return el.checked ? "1" : ""; }
        if (el.type === "radio") {
            const on = form.querySelector(`input[name="${el.name}"]:checked`);
            return on ? on.value : "";
        }
        return el.value;
    };

    const apply = (res) => {
        if (!res || !res.ok) { return; }
        if (count) { count.textContent = String(res.answered); }
        if (bar && res.total) { bar.style.width = `${Math.round((res.answered * 100) / res.total)}%`; }
        for (const [key, ok] of Object.entries(res.answers || {})) {
            const disc = form.querySelector(`.pbrq-q-n[data-q="${key}"]`);
            if (disc) { disc.classList.toggle("is-done", !!ok); }
        }
        if (budget && res.budget_note !== undefined) {
            budget.className = `pbrq-budget is-${res.budget_tone || "unknown"}`;
            const span = budget.querySelector("span");
            if (span && span.textContent !== res.budget_note) {
                span.textContent = res.budget_note;
                budget.classList.remove("is-fresh");
                void budget.offsetWidth;          // restart the soft flash
                budget.classList.add("is-fresh");
            }
        }
        if (missing) {
            const list = res.missing || [];
            missing.hidden = !list.length;
            if (list.length) { missing.textContent = `${missing.dataset.lead || "Still to answer:"} ${list.join(", ")}`; }
        }
    };

    const flush = async () => {
        if (closed || !pending.size) { return true; }
        if (inflight) { await inflight; }
        const body = Object.fromEntries(pending);
        pending.clear();
        say(form.dataset.saving || "Saving…");
        inflight = fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
            credentials: "same-origin",
        }).then(async (resp) => {
            let res = {};
            try { res = await resp.json(); } catch { res = {}; }
            if (resp.status === 409) {
                closed = true;
                say(res.error || "This request is closed.", "bad");
                return false;
            }
            if (!resp.ok || !res.ok) { throw new Error(res.error || String(resp.status)); }
            retry = 0;
            apply(res);
            say(`${form.dataset.savedAt || "Saved"} · ${now()}`, "ok");
            return true;
        }).catch(() => {
            // Put the answers back and try again later: a train tunnel must
            // never lose a manager's work.
            for (const [k, v] of Object.entries(body)) {
                if (!pending.has(k)) { pending.set(k, v); }
            }
            retry = Math.min(retry + 1, 5);
            say(form.dataset.retrying || "Not saved yet — trying again", "bad");
            setTimeout(flush, 1500 * retry);
            return false;
        }).finally(() => { inflight = null; });
        return inflight;
    };

    const queue = (el, now_ = false) => {
        if (!el.name || el.type === "file") { return; }
        pending.set(el.name, valueOf(el));
        clearTimeout(timers.get("all"));
        if (now_) { flush(); return; }
        timers.set("all", setTimeout(flush, DEBOUNCE_MS));
        say(form.dataset.typing || "…");
    };

    form.addEventListener("input", (ev) => {
        const el = ev.target;
        if (el.matches("input[type=text], input[type=number], textarea, input[type=date]")) { queue(el); }
    });
    form.addEventListener("change", (ev) => {
        const el = ev.target;
        if (el.type === "radio") {
            for (const lab of form.querySelectorAll(`input[name="${el.name}"]`)) {
                lab.closest(".pbrq-choice")?.classList.toggle("is-on", lab.checked);
            }
        }
        if (el.type === "checkbox") { el.closest(".pbrq-toggle")?.classList.toggle("is-on", el.checked); }
        queue(el, true);
    });
    form.addEventListener("focusout", (ev) => {
        if (pending.size && ev.target.name) { clearTimeout(timers.get("all")); flush(); }
    });

    // the money reads as money once you leave it (the server takes commas)
    const amt = form.querySelector("input[name=budget_cost]");
    const fmt = () => {
        const n = Number(String(amt.value).replace(/[^0-9.]/g, ""));
        if (amt.value && !isNaN(n)) { amt.value = n.toLocaleString("en-US", { maximumFractionDigits: 0 }); }
    };
    if (amt) { fmt(); amt.addEventListener("blur", fmt); }

    // the headcount stepper
    for (const btn of form.querySelectorAll(".pbrq-step")) {
        btn.addEventListener("click", () => {
            const input = form.querySelector("input[name=headcount]");
            const next = Math.max(1, Math.min(500, (parseInt(input.value, 10) || 1) + Number(btn.dataset.step)));
            input.value = String(next);
            queue(input, true);
        });
    }

    // Send in: flush first, then let the form post everything.
    form.addEventListener("submit", async (ev) => {
        if (form.dataset.sending) { return; }
        ev.preventDefault();
        const btn = document.getElementById("pbrq-send");
        if (btn) { btn.disabled = true; btn.classList.add("is-busy"); }
        await flush();
        form.dataset.sending = "1";
        form.submit();
    });

    // A file chosen on the attach form goes at once.
    const file = document.getElementById("f_jd_file");
    if (file) {
        file.removeAttribute("onchange");
        file.addEventListener("change", async () => {
            await flush();
            if (file.files && file.files.length) { file.form.submit(); }
        });
    }

    // Leaving with unsaved answers: say so.
    window.addEventListener("beforeunload", (ev) => {
        if (pending.size && !form.dataset.sending) { ev.preventDefault(); ev.returnValue = ""; }
    });

    const problem = document.getElementById("pbrq-problem");
    if (problem) { problem.scrollIntoView({ block: "center" }); }
    form.dataset.pbrqReady = "1";
}

function start() {
    const form = document.getElementById("pbrq-form");
    if (form && !form.dataset.pbrqReady) { setupRequest(form); }
}

if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
}
