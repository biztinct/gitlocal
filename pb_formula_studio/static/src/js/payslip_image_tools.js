/** @odoo-module **/

const IMAGE_SELECTOR = "img.pb-ps-inline-image, img[src*='/web/image/ir.attachment/']";

/**
 * Turn persisted, print-safe image markup into an editor affordance.
 * The remove button and contenteditable boundary are editor-only and are
 * stripped again by cleanPayslipImages before the HTML is saved.
 */
export function decoratePayslipImages(editor) {
    if (!editor) return [];
    const wrappers = [];
    for (const image of editor.querySelectorAll(IMAGE_SELECTOR)) {
        image.classList.add("pb-ps-inline-image");
        image.setAttribute("draggable", "false");
        let wrapper = image.parentElement;
        if (!wrapper || !wrapper.classList.contains("pb-ps-inline-image-wrap")) {
            wrapper = document.createElement("span");
            wrapper.className = "pb-ps-inline-image-wrap";
            wrapper.style.display = "block";
            wrapper.style.textAlign = "left";
            image.before(wrapper);
            wrapper.appendChild(image);
        }
        wrapper.setAttribute("contenteditable", "false");
        if (!wrapper.querySelector("[data-ps-remove-image]")) {
            const remove = document.createElement("button");
            remove.type = "button";
            remove.tabIndex = -1;
            remove.dataset.psRemoveImage = "1";
            remove.title = "Remove image";
            remove.setAttribute("aria-label", "Remove image");
            remove.textContent = "×";
            wrapper.appendChild(remove);
        }
        wrappers.push(wrapper);
    }
    return wrappers;
}

/** Remove all editor-only image chrome from a cloned editor document. */
export function cleanPayslipImages(root) {
    if (!root) return;
    for (const remove of root.querySelectorAll("[data-ps-remove-image]")) remove.remove();
    for (const wrapper of root.querySelectorAll(".pb-ps-inline-image-wrap")) {
        wrapper.classList.remove("ps-rich-image-selected");
        wrapper.removeAttribute("contenteditable");
        wrapper.removeAttribute("data-ps-image-editor");
        if (!wrapper.className) wrapper.removeAttribute("class");
    }
    for (const image of root.querySelectorAll(".pb-ps-inline-image")) {
        image.classList.remove("ps-rich-image-selected");
        image.removeAttribute("draggable");
        image.removeAttribute("data-ps-image-id");
    }
}

export function alignPayslipImage(wrapper, alignment) {
    if (!wrapper || !["left", "center", "right"].includes(alignment)) return false;
    wrapper.style.display = "block";
    wrapper.style.textAlign = alignment;
    return true;
}

export function resizePayslipImage(wrapper, size) {
    const image = wrapper && wrapper.querySelector("img.pb-ps-inline-image");
    if (!image || !["original", "small", "medium", "large", "full"].includes(size)) return false;
    image.style.height = "auto";
    image.style.maxWidth = "100%";
    if (size === "original") image.style.removeProperty("width");
    else if (size === "full") image.style.width = "100%";
    else image.style.width = ({ small: "96px", medium: "160px", large: "240px" })[size];
    return true;
}

