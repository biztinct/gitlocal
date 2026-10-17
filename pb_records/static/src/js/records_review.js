/** @odoo-module **/
/**
 * Records Desk — the review drawer's list, and the ground it stands on.
 *
 * Two defects R3 named live here, and they are the same defect twice: a drawer
 * that stops being readable at scale.
 *
 * **What it shows (D2).** One person, one field, one `old → new` row is the
 * right unit for a hand-typed correction and the wrong one for a bulk fill:
 * setting SHUI Participation to NO for a department of 140 produced 140
 * identical rows, and a list nobody can read is a list nobody checks. So the
 * items are folded into BLOCKS first: a `(field, old → new)` that lands on
 * three or more people becomes ONE row — *"SHUI participation: YES → NO ·
 * 140 people"* — with a chevron that expands to the names, and everything else
 * stays exactly as it was, per person, in the order it arrived. Three is the
 * threshold because two names is shorter than the sentence that would replace
 * them.
 *
 * The counts on the drawer's header line are NOT computed from these blocks.
 * They come from the server's own `counts`, unchanged, because "140 people"
 * being a summary of what is on screen and "141 changes on 141 people" being a
 * summary of what will be written are two different promises and only the
 * second one may be wrong.
 *
 * **Where it stands (D1).** The drawer is `position: fixed` in the bottom-right
 * corner, and so are the app's floating helpers — the copilot pill and the
 * coach launcher, both owned by other modules and neither of them movable from
 * here. At 1600px the Apply button sat UNDER one of them: a primary action you
 * cannot click is a dead end, and the fix belongs to whoever arrived last.
 * `footerReserve` measures what is actually painted over the drawer's own
 * column and hands back the bottom safe area the footer must keep clear. It is
 * a pure function of rectangles so it can be asserted without a browser, and it
 * reserves NOTHING when nothing is there.
 */
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/**
 * A count with thousands separators — `4512` reads as `4,512`.
 *
 * Every counted number on this surface goes through it. A drawer that says
 * "4,512 rows" in one line and "4512 rows" in the next is a drawer somebody
 * reads twice to check they are the same number.
 */
export function grouped(count) {
    return String(Math.max(0, Math.round(Number(count) || 0)))
        .replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/** A `(field, old → new)` shared by at least this many people folds into one row. */
export const GROUP_MIN = 3;

/** The gap kept between the Apply button and whatever floats over it. */
export const SAFE_GAP = 12;

/**
 * Everything that can sit on top of the drawer, by name.
 *
 * A closed list rather than "every fixed element", because the answer to a
 * floating control that belongs to another module is to make room for it, and
 * the answer to a stray absolutely-positioned div is not. Each of these is a
 * live, clickable control the user may want while the drawer is open:
 *
 *   `.payai-floating-pill`  the data copilot pill (bottom right)
 *   `.lrn-fab`              the coach launcher ("Stuck?")
 *   `.pbc-launcher`         the retired guided-tour launcher, where installed
 */
export const FLOATERS = ".payai-floating-pill, .lrn-fab, .pbc-launcher";

/**
 * How much bottom clearance the drawer footer needs.
 *
 * `boxes` are viewport rectangles (`getBoundingClientRect()` shapes) and `view`
 * is `{height, left, right}` — the viewport height and the drawer's own column.
 * A control that floats somewhere else on screen is not in the way and reserves
 * nothing; a control over the drawer reserves down from its top edge, so the
 * footer clears the whole stack of them at once.
 */
export function footerReserve(boxes, view) {
    const height = (view && view.height) || 0;
    let top = height;
    for (const box of boxes || []) {
        if (!box || box.bottom <= 0 || box.top >= height) { continue; }
        if (box.right <= view.left || box.left >= view.right) { continue; }
        if (box.bottom - box.top < 1 || box.right - box.left < 1) { continue; }
        top = Math.min(top, box.top);
    }
    const reserve = height - top;
    return reserve > 0 ? Math.round(reserve + SAFE_GAP) : 0;
}

/**
 * Is this control actually PAINTED where it is, or is the drawer over it?
 *
 * The two corner helpers stack differently: the copilot pill is drawn ABOVE
 * the drawer and stays clickable through it, while the coach launcher sits
 * below and the drawer simply covers it. Reserving space for the covered one
 * would push Apply up by another eighty pixels to clear a control nobody can
 * see — so the question is asked of the BROWSER, at the control's own centre,
 * exactly as the overlap sweep asks it (MJ7's disproof, reused).
 */
export function isOnTop(el, doc = document) {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) { return false; }
    const hit = doc.elementFromPoint((r.left + r.right) / 2,
                                     (r.top + r.bottom) / 2);
    return !!hit && (hit === el || el.contains(hit));
}

/** The drawer's own column, and the viewport it floats in. */
export function measureReserve(doc = document, win = window) {
    const drawer = doc.querySelector(".rd-drawer");
    if (!drawer) { return 0; }
    const box = drawer.getBoundingClientRect();
    const boxes = [...doc.querySelectorAll(FLOATERS)]
        .filter((el) => isOnTop(el, doc))
        .map((el) => el.getBoundingClientRect());
    return footerReserve(boxes, {
        height: win.innerHeight || 0, left: box.left, right: box.right,
    });
}

/** The identity of a change AS A SENTENCE — two rows with this key read alike. */
function shapeKey(item) {
    // JSON rather than a joined string: a label may contain any separator a
    // person could think of, and two changes that only differ inside one label
    // must not fold into each other.
    return JSON.stringify([item.field_id, item.status, item.old_label ?? "",
                           item.new_label ?? "", item.why ?? ""]);
}

/**
 * The review list, folded.
 *
 * Returns blocks in the order the items arrived: a `person` block carries that
 * person's own rows exactly as before; a `group` block carries one row and the
 * names it stands for. `same` rows are not changes and are not shown in either.
 */
export function reviewBlocks(items, minGroup = GROUP_MIN) {
    const rows = (items || []).filter((i) => i && i.status !== "same");
    const buckets = new Map();
    for (const item of rows) {
        const key = shapeKey(item);
        if (!buckets.has(key)) { buckets.set(key, []); }
        buckets.get(key).push(item);
    }
    const bulk = new Set();
    for (const [key, list] of buckets) {
        const people = new Set(list.map((i) => i.emp_id));
        if (people.size >= minGroup) { bulk.add(key); }
    }
    const blocks = [];
    const groupAt = new Map();
    const personAt = new Map();
    for (const item of rows) {
        const key = shapeKey(item);
        if (bulk.has(key)) {
            if (!groupAt.has(key)) {
                groupAt.set(key, blocks.length);
                blocks.push({
                    type: "group", key,
                    field_label: item.field_label, old_label: item.old_label,
                    new_label: item.new_label, status: item.status,
                    why: item.why, names: [], ids: [],
                });
            }
            const block = blocks[groupAt.get(key)];
            if (!block.ids.includes(item.emp_id)) {
                block.ids.push(item.emp_id);
                block.names.push(item.emp_name);
            }
            continue;
        }
        if (!personAt.has(item.emp_id)) {
            personAt.set(item.emp_id, blocks.length);
            blocks.push({ type: "person", id: item.emp_id,
                          name: item.emp_name, rows: [] });
        }
        blocks[personAt.get(item.emp_id)].rows.push(item);
    }
    for (const block of blocks) {
        if (block.type === "group") { block.count = block.ids.length; }
    }
    return blocks;
}

/** "140 people", "1 person" — the group row's own count, never interpolated. */
export function groupCountLabel(count) {
    return count === 1 ? _t("1 person") : _t("%s people", grouped(count));
}

// ---------------------------------------------------------------------------
//  RdReviewList — the same list in both drawers
// ---------------------------------------------------------------------------
export class RdReviewList extends Component {
    static template = "pb_records.RdReviewList";
    static props = {
        items: { type: Array },
        minGroup: { type: Number, optional: true },
    };

    setup() {
        // Which groups are open. Closed by default: the whole point of a group
        // is that the reader does not have to read 140 names to approve them.
        this.state = useState({ open: {} });
    }

    ic(name, size = 13) { return ic(name, size); }

    get blocks() {
        return reviewBlocks(this.props.items, this.props.minGroup ?? GROUP_MIN);
    }

    isOpen(key) { return !!this.state.open[key]; }

    toggle(key) { this.state.open[key] = !this.state.open[key]; }

    countLabel(count) { return groupCountLabel(count); }

    namesLabel(block) {
        return block.names.join(" · ");
    }

    get emptyLine() { return _t("Nothing staged yet."); }
}
