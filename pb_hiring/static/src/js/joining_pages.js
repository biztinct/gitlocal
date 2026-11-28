/** @odoo-module **/
/**
 * RECRUIT P6 — the three "Before they join" pages (buddy, laptop, the week
 * before). A courtesy layer on plain HTML forms: every page works with the
 * script blocked, and the server checks everything again.
 *
 *   * buddy: type to narrow the list; the order you tick is the order kept
 *     (the first is the buddy on day one), shown as numbered chips; the
 *     button says how many you named.
 *   * laptop: Send checks the one required answer and points at it.
 *   * week: only the follow-up for the answer you picked is shown.
 */

function setupBuddy(form) {
    const q = document.getElementById("pbjn-q");
    const order = document.getElementById("pbjn-order");
    const picked = document.getElementById("pbjn-picked");
    const none = document.getElementById("pbjn-none");
    const sendTx = document.getElementById("pbjn-send-tx");
    const rows = [...form.querySelectorAll(".pbjn-person")];
    const groups = [...form.querySelectorAll(".pbjn-group")];
    let chosen = [];

    const render = () => {
        order.value = chosen.join(",");
        picked.innerHTML = "";
        chosen.forEach((id, i) => {
            const row = rows.find((r) => r.querySelector("input").value === id);
            if (!row) { return; }
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = "pbjn-chip" + (i === 0 ? " is-first" : "");
            chip.textContent = `${i + 1}. ${row.querySelector("b").textContent}${i === 0 ? " — day one" : ""}`;
            chip.title = "Take them off";
            chip.addEventListener("click", () => {
                row.querySelector("input").checked = false;
                chosen = chosen.filter((x) => x !== id);
                render();
            });
            picked.appendChild(chip);
        });
        for (const row of rows) {
            const id = row.querySelector("input").value;
            const at = chosen.indexOf(id);
            row.classList.toggle("is-on", at > -1);
            row.querySelector(".pbjn-rank").textContent = at > -1 ? String(at + 1) : "";
        }
        if (sendTx) {
            sendTx.textContent = !chosen.length ? "Name the buddy"
                : chosen.length === 1 ? "Name 1 buddy" : `Name ${chosen.length} buddies`;
        }
    };

    for (const row of rows) {
        const input = row.querySelector("input");
        input.addEventListener("change", () => {
            if (input.checked) {
                if (chosen.length >= 5) { input.checked = false; return; }
                chosen.push(input.value);
            } else {
                chosen = chosen.filter((x) => x !== input.value);
            }
            render();
        });
    }
    if (q) {
        q.addEventListener("input", () => {
            const term = q.value.trim().toLowerCase();
            let shown = 0;
            for (const row of rows) {
                const hit = !term || (row.dataset.q || "").includes(term);
                row.hidden = !hit;
                shown += hit ? 1 : 0;
            }
            for (const g of groups) { g.hidden = !!term; }
            if (none) { none.hidden = shown > 0; }
        });
    }
    form.addEventListener("submit", (ev) => {
        if (!chosen.length) {
            ev.preventDefault();
            if (q) { q.focus(); }
            picked.innerHTML = '<span class="pbjn-need">Tick at least one person.</span>';
            return;
        }
        const btn = form.querySelector(".pbiv-send");
        if (btn) { btn.setAttribute("disabled", "disabled"); }
    });
    render();
    form.dataset.pbjnReady = "1";
}

function setupLaptop(form) {
    const kind = form.querySelector(".pbiv-q[data-kind=kind]");
    form.addEventListener("change", () => {
        if (kind && form.querySelector("input[name=kind]:checked")) { kind.classList.remove("is-missing"); }
    });
    form.addEventListener("submit", (ev) => {
        if (kind && !form.querySelector("input[name=kind]:checked")) {
            ev.preventDefault();
            kind.classList.add("is-missing");
            kind.scrollIntoView({ behavior: "smooth", block: "center" });
            return;
        }
        const btn = form.querySelector(".pbiv-send");
        if (btn) { btn.setAttribute("disabled", "disabled"); }
    });
    form.dataset.pbjnReady = "1";
}

function setupWeek(form) {
    const more = [...form.querySelectorAll(".pbjn-more")];
    const show = () => {
        const pick = form.querySelector("input[name=answer]:checked");
        const val = pick ? pick.value : "";
        for (const sec of more) { sec.hidden = sec.dataset.for !== val; }
    };
    form.addEventListener("change", show);
    form.addEventListener("submit", (ev) => {
        const pick = form.querySelector("input[name=answer]:checked");
        if (!pick) {
            ev.preventDefault();
            form.querySelector(".pbjn-answers").classList.add("is-missing");
            return;
        }
        if (pick.value === "changed") {
            const d = form.querySelector("input[name=new_date]");
            if (d && !d.value) { ev.preventDefault(); d.focus(); return; }
        }
        const btn = form.querySelector(".pbiv-send");
        if (btn) { btn.setAttribute("disabled", "disabled"); }
    });
    show();
    form.dataset.pbjnReady = "1";
}

function boot() {
    const b = document.getElementById("pbjn-buddy");
    if (b && !b.dataset.pbjnReady) { setupBuddy(b); }
    const l = document.getElementById("pbjn-laptop");
    if (l && !l.dataset.pbjnReady) { setupLaptop(l); }
    const w = document.getElementById("pbjn-week");
    if (w && !w.dataset.pbjnReady) { setupWeek(w); }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
} else {
    boot();
}
