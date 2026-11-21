/** @odoo-module **/
/**
 * Small shared helpers for the Form builder screens: section tones, the icon
 * of each kind of change, and the server's facade name. Kept apart so the
 * grid, the Studio and the Field library agree.
 */

export const FACADE = "pb.form.studio";

/** Section tone → the class the cards paint (POC: teal / blue / green / amber / brand). */
export function toneClass(tone) {
    return ["teal", "blue", "green", "amber"].includes(tone) ? tone : "brand";
}

/** Change kind → icon, for the publish sheet. */
export const CHANGE_ICON = {
    added: "plusCircle", moved: "move", hidden: "eyeOff", shown: "eye",
    deleted: "trash", changed: "pencil",
};

/**
 * R24 — text folded for searching: no accents, no case, "đ" as "d", so
 * "ngay sinh" finds "Ngày sinh" and "nhom mau" finds "Nhóm máu".
 */
export function fold(text) {
    return String(text || "")
        .normalize("NFD")
        .replace(/[̀-ͯ]/g, "")
        .replace(/đ/g, "d")
        .replace(/Đ/g, "D")
        .toLowerCase()
        .trim();
}

/** Does folded `term` occur in any of `texts`? An empty term matches all. */
export function foldMatch(term, ...texts) {
    const t = fold(term);
    if (!t) { return true; }
    return texts.some((x) => fold(x).includes(t));
}

/**
 * FS-13 — the labels two or more DIFFERENT fields of one list share
 * (folded), so the list can tell them apart (e.g. "Work permit number" of
 * the standard ID papers and of the Vietnamese payroll details). Items with
 * no field name (lines the screen works out itself) are left out.
 */
export function sameLabels(items, labelOf) {
    const seen = new Map();
    for (const it of items || []) {
        if (!it || !it.name) { continue; }
        const key = fold(labelOf(it));
        if (!key) { continue; }
        if (!seen.has(key)) { seen.set(key, new Set()); }
        seen.get(key).add(it.name);
    }
    return new Set([...seen].filter(([, names]) => names.size > 1).map(([key]) => key));
}

/** R24 — the type filter of "Add existing": kind → group key. */
export const KIND_GROUP = {
    text: "text", longtext: "text", integer: "number", number: "number", money: "number",
    date: "date", select: "choice", bool: "bool", m2o: "link", readonly: "link", file: "text",
};

/** Is the key a "search here" key pressed outside any box a person types in? */
export function isSlashKey(ev) {
    if (ev.key !== "/" || ev.ctrlKey || ev.metaKey || ev.altKey) { return false; }
    const t = ev.target;
    const tag = (t && t.tagName) || "";
    return !(tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (t && t.isContentEditable));
}

/** True for a value the grid should show as "—". */
export function isEmptyDisplay(display) {
    return display === undefined || display === null || display === "";
}

/** Read a File into a data URL (for "File" fields). */
export function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
    });
}
