import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

// Text nodes only: directory values never become HTML or executable URLs.
function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
}
function button(text, action, id, cls = "pborg-btn") {
    const node = el("button", cls, text);
    node.type = "button";
    node.dataset.action = action;
    if (id !== undefined) node.dataset.id = id;
    return node;
}
const fold = (s) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase();

export class OrganisationChart extends Interaction {
    static selector = "[data-orgchart]";
    dynamicContent = {
        _root: { "t-on-click": this.onClick, "t-on-dblclick": this.onDoubleClick,
            "t-on-input": this.onInput, "t-on-change": this.onChange, "t-on-keydown": this.onKeydown },
    };
    setup() {
        this.data = JSON.parse(this.el.dataset.orgchart);
        this.people = new Map(this.data.people.map(p => [p.id, { ...p, children: [], total: 0 }]));
        this.roots = [];
        for (const p of this.people.values()) {
            const manager = this.people.get(p.manager_id);
            (manager ? manager.children : this.roots).push(p.id);
        }
        const queue = this.roots.map(id => [id, 1]);
        for (let i = 0; i < queue.length; i++) {
            const [id, level] = queue[i], p = this.people.get(id);
            p.level = level;
            for (const child of p.children) queue.push([child, level + 1]);
        }
        for (const [id] of queue.reverse()) {
            const p = this.people.get(id), manager = this.people.get(p.manager_id);
            if (manager) manager.total += p.total + 1;
        }
        this.selected = this.data.focus || this.data.me;
        this.focus = this.data.focus || 0;
        this.expanded = new Set();
        this.limit = 300;
        this.zoom = 1;
        this.department = "all";
        this.query = this.data.query;
    }
    start() {
        const departments = new Map(this.data.people.map(p => [p.department_id, p.department || _t("No department")]));
        const select = this.$("[data-control=department]");
        for (const [id, name] of [...departments].sort((a, b) => a[1].localeCompare(b[1]))) {
            const option = el("option", "", name); option.value = id; select.append(option);
        }
        this.$("[data-control=search]").value = this.query;
        this.setLevels(2);
        this.reveal(this.selected);
        this.$("[data-control=levels]").value = "custom";
        this.render();
        this.renderSearch();
        this.scrollTo(this.selected);
    }
    $(selector) { return this.el.querySelector(selector); }
    ancestors(id) {
        const result = [], seen = new Set();
        let p = this.people.get(id);
        while (p && !seen.has(p.id)) {
            seen.add(p.id); result.unshift(p.id); p = this.people.get(p.manager_id);
        }
        return result;
    }
    reveal(id) { for (const ancestor of this.ancestors(id)) this.expanded.add(ancestor); }
    setLevels(value) {
        this.expanded.clear();
        const base = this.focus ? this.people.get(this.focus).level : 1;
        for (const p of this.people.values()) if (value === "all" || p.level - base + 1 < Number(value)) this.expanded.add(p.id);
    }
    filteredIds() {
        if (this.department === "all") return null;
        const included = new Set();
        for (const p of this.people.values()) if (String(p.department_id) === this.department) {
            for (const id of this.ancestors(p.id)) included.add(id);
        }
        return included;
    }
    renderSearch() {
        const box = this.$(".pborg-search-results"); box.replaceChildren(); box.hidden = !this.query.trim();
        if (box.hidden) return;
        const query = fold(this.query.trim());
        const matches = [...this.people.values()].filter(p => fold(`${p.name} ${p.job} ${p.department}`).includes(query));
        box.append(el("p", "", _t("%s matches. Select a person to reveal their reporting line.", matches.length)));
        for (const p of matches.slice(0, 30)) box.append(button(`${p.name} · ${p.job || p.department || _t("Colleague")}`, "reveal", p.id));
        if (matches.length > 30) box.append(el("p", "", _t("Showing the first 30. Refine your search to find someone else.")));
    }
    render() {
        const included = this.filteredIds(), host = this.$(".pborg-tree"); host.replaceChildren();
        const rootList = el("ul", "pborg-branches");
        const priority = new Set(this.ancestors(this.selected));
        const prioritize = ids => [...ids].sort((a, b) => Number(priority.has(b)) - Number(priority.has(a)));
        const roots = this.focus ? [this.focus] : prioritize(this.roots);
        let count = 0, truncated = false;
        // Iterative construction avoids overflowing the call stack on deep data.
        const stack = [...roots].reverse().map(id => [id, rootList, 1]);
        while (stack.length) {
            const [id, parent, depth] = stack.pop();
            if (included && !included.has(id)) continue;
            if (count >= this.limit) { truncated = true; break; }
            count++;
            const p = this.people.get(id), li = el("li", "pborg-branch"); parent.append(li);
            const card = el("div", "pborg-node" + (id === this.selected ? " is-selected" : "") +
                (included && String(p.department_id) !== this.department ? " is-context" : ""));
            card.dataset.node = id;
            const person = button("", "select", id, "pborg-person");
            person.setAttribute("aria-label", _t("%s, %s. Show details", p.name, p.job || _t("Colleague")));
            person.setAttribute("aria-pressed", String(id === this.selected));
            person.title = _t("%s · %s direct reports · %s people in team", p.name, p.children.length, p.total);
            const image = el("img", "pborg-avatar"); image.src = p.avatar; image.alt = ""; image.loading = "lazy";
            const text = el("span", "pborg-person-text");
            text.append(el("strong", "", p.name), el("span", "pborg-role", p.job || _t("Role not listed")), el("span", "pborg-dept", p.department || _t("No department")));
            person.append(image, text);
            card.append(person);
            const meta = el("div", "pborg-node-meta");
            meta.append(el("span", "", id === this.data.me ? _t("You · Level %s", depth) : _t("Level %s", depth)));
            if (p.children.length) {
                const toggle = button((this.expanded.has(id) ? "− " : "+ ") + _t("%s reports", p.children.length), "toggle", id, "pborg-disclosure");
                toggle.setAttribute("aria-expanded", String(this.expanded.has(id)));
                toggle.setAttribute("aria-label", (this.expanded.has(id) ? _t("Collapse %s's reports", p.name) : _t("Expand %s's reports", p.name)));
                meta.append(toggle);
            } else meta.append(el("span", "", _t("No reports")));
            card.append(meta); li.append(card);
            if (p.children.length && this.expanded.has(id)) {
                const children = prioritize(p.children.filter(child => !included || included.has(child)));
                if (children.length) {
                    const list = el("ul", "pborg-branches"); li.append(list);
                    for (const child of [...children].reverse()) stack.push([child, list, depth + 1]);
                }
            }
        }
        host.append(rootList);
        if (!count) host.append(el("p", "pborg-empty", _t("No people in this view. Try All teams or Organisation.")));
        if (truncated) host.append(button(_t("Show more people (showing %s)", count), "more"));
        this.$(".pborg-status").textContent = _t("%s shown · %s people in company", count, this.people.size);
        this.$("[data-action=organisation]").setAttribute("aria-pressed", String(!this.focus));
        this.$("[data-action=my-team]").setAttribute("aria-pressed", String(this.focus === this.data.me));
        const path = this.$(".pborg-path"); path.replaceChildren(button(this.data.company, "organisation", undefined, "pborg-path-link"));
        if (this.focus) for (const id of this.ancestors(this.focus)) {
            path.append(el("span", "", " / "), button(this.people.get(id).name, "focus", id, "pborg-path-link"));
        }
        this.renderDetails();
    }
    renderDetails() {
        const box = this.$(".pborg-detail"), p = this.people.get(this.selected); box.replaceChildren();
        if (!p) return;
        box.append(el("span", "pborg-kicker", _t("PERSON DETAILS")));
        const image = el("img", "pborg-detail-avatar"); image.src = p.avatar; image.alt = "";
        box.append(image, el("h2", "", p.name), el("p", "pborg-role", p.job || _t("Role not listed")), el("span", "pborg-tag", p.department || _t("No department")));
        if (p.id === this.data.me) box.append(el("span", "pborg-tag is-you", _t("That's you")));
        const stats = el("div", "pborg-stats");
        for (const [value, label] of [[p.children.length, _t("Direct reports")], [p.total, _t("Entire team")]]) {
            const stat = el("div"); stat.append(el("strong", "", value), el("span", "", label)); stats.append(stat);
        }
        box.append(stats, el("h3", "", _t("Reports to")));
        const manager = this.people.get(p.manager_id);
        box.append(manager ? button(manager.name, "reveal", manager.id, "pborg-related") : el("p", "", _t("No manager listed in this company")));
        if (p.hierarchy_note) box.append(el("p", "pborg-note", _t("Reporting line unavailable. This person is shown separately.")));
        if (p.email) {
            box.append(el("h3", "", _t("Work email")));
            const email = el("a", "pborg-email", p.email); email.href = `mailto:${encodeURIComponent(p.email)}`; box.append(email);
        }
        box.append(button(_t("Focus team"), "focus", p.id, "pborg-btn pborg-primary"), button(_t("Show in organisation"), "reveal", p.id));
        const peers = manager ? manager.children.filter(id => id !== p.id) : [];
        if (peers.length) {
            box.append(el("h3", "", _t("Same manager · %s", peers.length)));
            for (const id of peers.slice(0, 6)) box.append(button(this.people.get(id).name, "reveal", id, "pborg-related"));
            if (peers.length > 6) box.append(button(_t("See all teammates"), "focus", manager.id));
        }
    }
    scrollTo(id) {
        const node = this.$(`[data-node="${id}"]`), canvas = this.$(".pborg-canvas");
        if (node) {
            const a = node.getBoundingClientRect(), b = canvas.getBoundingClientRect();
            canvas.scrollLeft += a.left - b.left - (b.width - a.width) / 2;
            canvas.scrollTop += a.top - b.top - 50;
        }
    }
    reset(focus = 0) {
        this.focus = focus; this.department = "all"; this.limit = 300; this.query = "";
        this.$("[data-control=department]").value = "all";
        this.$("[data-control=search]").value = "";
        this.$("[data-control=levels]").value = "2";
        this.setLevels(2); this.renderSearch();
    }
    onClick(ev) {
        const target = ev.target.closest("[data-action]"); if (!target) return;
        const action = target.dataset.action, id = Number(target.dataset.id);
        const previous = this.selected;
        if (action === "select") { this.selected = id; }
        else if (action === "toggle") { this.expanded.has(id) ? this.expanded.delete(id) : this.expanded.add(id); }
        else if (action === "focus") { this.selected = id; this.reset(id); }
        else if (action === "my-team") { this.selected = this.data.me; this.reset(this.data.me); }
        else if (action === "organisation" || action === "reset") { this.reset(); }
        else if (action === "find-me" || action === "reveal") {
            this.selected = action === "find-me" ? this.data.me : id;
            this.reset(); this.reveal(this.selected);
            this.$("[data-control=levels]").value = "custom";
        } else if (action === "expand") { this.setLevels("all"); this.$("[data-control=levels]").value = "all"; }
        else if (action === "collapse") { this.expanded.clear(); }
        else if (action === "more") { this.limit += 300; }
        else if (action.startsWith("zoom")) {
            this.zoom = action === "zoom-reset" ? 1 : Math.min(1.3, Math.max(.6, this.zoom + (action === "zoom-in" ? .1 : -.1)));
            this.$(".pborg-tree").style.zoom = this.zoom;
            this.$(".pborg-zoom-value").textContent = `${Math.round(this.zoom * 100)}%`; return;
        } else return;
        // Do not replace the clicked card: its native dblclick must still fire.
        if (action === "select") {
            this.$(`[data-node="${previous}"]`)?.classList.remove("is-selected");
            this.$(`[data-node="${previous}"] [data-action=select]`)?.setAttribute("aria-pressed", "false");
            this.$(`[data-node="${id}"]`)?.classList.add("is-selected");
            target.setAttribute("aria-pressed", "true"); this.renderDetails();
            if (window.matchMedia("(max-width: 900px)").matches) this.$(".pborg-detail").scrollIntoView({ block: "nearest" });
            return;
        }
        if (["toggle", "collapse"].includes(action)) this.$("[data-control=levels]").value = "custom";
        this.render();
        if (["reveal", "find-me", "focus", "my-team"].includes(action)) this.scrollTo(this.selected);
        // Retain keyboard position after rebuilding a branch.
        if (action === "toggle") this.$(`[data-action=toggle][data-id="${id}"]`)?.focus({ preventScroll: true });
        if (action === "reset") { this.zoom = 1; this.$(".pborg-tree").style.zoom = 1; this.$(".pborg-zoom-value").textContent = "100%"; }
    }
    onDoubleClick(ev) {
        const person = ev.target.closest("[data-action=select]");
        if (person) { this.selected = Number(person.dataset.id); this.reset(this.selected); this.render(); this.scrollTo(this.selected); }
    }
    onInput(ev) { if (ev.target.dataset.control === "search") { this.query = ev.target.value; this.renderSearch(); } }
    onChange(ev) {
        const control = ev.target.dataset.control;
        if (control === "department") {
            this.department = ev.target.value;
            this.$("[data-control=levels]").value = "custom";
            if (this.department !== "all") {
                for (const p of this.people.values()) if (String(p.department_id) === this.department) this.reveal(p.id);
            }
        } else if (control === "levels") this.setLevels(ev.target.value);
        else return;
        this.render();
    }
    onKeydown(ev) {
        if (ev.key === "Escape" && this.query) { this.query = ""; this.$("[data-control=search]").value = ""; this.renderSearch(); }
        const card = ev.target.closest("[data-action=select]");
        if (!card || !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(ev.key)) return;
        ev.preventDefault();
        const p = this.people.get(Number(card.dataset.id));
        if (ev.key === "ArrowRight") this.expanded.add(p.id);
        if (ev.key === "ArrowLeft") this.expanded.delete(p.id);
        const ids = [...this.el.querySelectorAll(".pborg-node [data-action=select]")].map(n => Number(n.dataset.id));
        const next = ev.key === "ArrowDown" ? ids[Math.min(ids.length - 1, ids.indexOf(p.id) + 1)] : ev.key === "ArrowUp" ? ids[Math.max(0, ids.indexOf(p.id) - 1)] : p.id;
        this.render(); this.$(`[data-action=select][data-id="${next}"]`)?.focus();
    }
}
registry.category("public.interactions").add("pb_onboarding.orgchart", OrganisationChart);
