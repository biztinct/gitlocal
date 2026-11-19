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
