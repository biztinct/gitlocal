// In-page dump of what a native form SHOWS: every field / label / button /
// section title / tab, per tab, with visible / readonly / required / value.
// Runs inside the web client (CDP Runtime.evaluate, awaitPromise). Returns JSON.
async () => {
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    const forms = document.querySelectorAll(".o_action_manager .o_form_view");
    const root = forms[forms.length - 1];
    if (!root) {
        return { error: "no form" };
    }
    const vis = (el) => !!el && el.checkVisibility() && el.getClientRects().length > 0;
    const txt = (el) => ((el && (el.innerText || el.textContent)) || "").replace(/\s+/g, " ").trim().slice(0, 80);
    const rows = [];
    const nb = root.querySelector(".o_form_sheet .o_notebook");
    const fieldVal = (f) => {
        const cb = f.querySelector("input[type=checkbox]");
        if (cb && !f.querySelector("input:not([type=checkbox])")) {
            return cb.checked ? "[x]" : "[ ]";
        }
        const i = f.querySelector("input:not([type=checkbox]):not([type=file]), textarea, select");
        if (i) {
            return (i.value || "").replace(/\s+/g, " ").trim().slice(0, 60);
        }
        return txt(f).slice(0, 60);
    };
    const inScope = (el, where) => {
        if (where === "top") {
            return !(nb && nb.contains(el));
        }
        return true;
    };
    function scan(scope, where) {
        scope.querySelectorAll(".o_field_widget[name]").forEach((f) => {
            if (!inScope(f, where)) return;
            const ro = f.classList.contains("o_readonly_modifier") ? "ro" : "rw";
            const req = f.classList.contains("o_required_modifier") ? "req" : "";
            rows.push(["F", where, f.getAttribute("name"), vis(f) ? 1 : 0, ro, req, fieldVal(f)]);
        });
        scope.querySelectorAll("label.o_form_label, .o_form_label").forEach((l) => {
            if (!inScope(l, where)) return;
            const forAttr = (l.getAttribute("for") || "").replace(/_\d+$/, "");
            rows.push(["L", where, forAttr, vis(l) ? 1 : 0, txt(l)]);
        });
        scope.querySelectorAll("button, a.btn, a[type]").forEach((b) => {
            if (!inScope(b, where)) return;
            if (b.closest(".o_notebook_headers")) return;
            if (b.closest(".o_field_widget") && !b.getAttribute("name")) return; // widget internals
            const name = b.getAttribute("name") || "";
            rows.push(["B", where, name, vis(b) ? 1 : 0, b.disabled ? "disabled" : "", txt(b)]);
        });
        scope.querySelectorAll(".o_horizontal_separator").forEach((s) => {
            if (!inScope(s, where)) return;
            rows.push(["S", where, vis(s) ? 1 : 0, txt(s)]);
        });
        scope.querySelectorAll(".o_field_x2many").forEach((x) => {
            if (!inScope(x, where)) return;
            rows.push(["X", where, (x.closest("[name]") || x).getAttribute("name"), vis(x) ? 1 : 0,
                x.querySelectorAll(".o_data_row").length]);
        });
        scope.querySelectorAll(".alert, .o_widget, .ribbon").forEach((a) => {
            if (!inScope(a, where)) return;
            rows.push(["A", where, vis(a) ? 1 : 0, txt(a).slice(0, 60)]);
        });
    }
    // 1. Header (status bar) and the sheet outside the notebook
    scan(root, "top");
    // 2. Smart-button "More" drawer
    const more = root.querySelector(".o-form-buttonbox .o_button_more, .o-form-buttonbox .dropdown-toggle");
    if (more && vis(more)) {
        more.click();
        await sleep(400);
        document.querySelectorAll(".o-dropdown--menu button, .o-dropdown--menu .oe_stat_button").forEach((b) => {
            rows.push(["B", "more", b.getAttribute("name") || "", vis(b) ? 1 : 0, "", txt(b)]);
        });
        document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
        more.click();
        await sleep(200);
    }
    // 3. Every tab
    if (nb) {
        const links = [...nb.querySelectorAll(":scope > .o_notebook_headers .nav-link, :scope > div > .o_notebook_headers .nav-link")];
        const all = links.length ? links : [...nb.querySelectorAll(".o_notebook_headers .nav-link")];
        for (const a of all) {
            const pname = a.getAttribute("name") || txt(a);
            const v = vis(a);
            rows.push(["P", pname, v ? 1 : 0, txt(a)]);
            if (!v) continue;
            a.click();
            await sleep(500);
            const pane = nb.querySelector(".tab-content > .tab-pane.active") || nb.querySelector(".tab-pane.active");
            if (pane) scan(pane, "page:" + pname);
        }
    }
    const chatter = document.querySelector(".o-mail-Chatter");
    rows.push(["C", "chatter", vis(chatter) ? 1 : 0]);
    return {
        url: location.pathname,
        title: txt(root.querySelector(".oe_title h1")) || "",
        vuForm: !!root.querySelector(".o_form_renderer.vu-form"),
        rows,
    };
}
