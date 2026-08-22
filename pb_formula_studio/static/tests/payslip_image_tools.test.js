/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";
import {
    alignPayslipImage,
    cleanPayslipImages,
    decoratePayslipImages,
    resizePayslipImage,
} from "@pb_formula_studio/js/payslip_image_tools";

describe.current.tags("desktop");

function imageFixture() {
    const editor = document.createElement("div");
    editor.innerHTML = '<table><tbody><tr><td><img class="pb-ps-inline-image" '
        + 'src="/web/image/ir.attachment/17/datas?access_token=token" alt="Logo"></td></tr></tbody></table>';
    document.body.appendChild(editor);
    const [wrapper] = decoratePayslipImages(editor);
    return { editor, wrapper, image: wrapper.querySelector("img") };
}

test("images are decorated inside table cells and editor chrome is removed on save", () => {
    const { editor, wrapper, image } = imageFixture();
    expect(wrapper.closest("td")).not.toBe(null);
    expect(wrapper.getAttribute("contenteditable")).toBe("false");
    expect(wrapper.querySelectorAll("[data-ps-remove-image]").length).toBe(1);

    alignPayslipImage(wrapper, "right");
    resizePayslipImage(wrapper, "large");
    wrapper.classList.add("ps-rich-image-selected");
    const clone = editor.cloneNode(true);
    cleanPayslipImages(clone);

    expect(clone.querySelector("[data-ps-remove-image]")).toBe(null);
    expect(clone.querySelector(".ps-rich-image-selected")).toBe(null);
    expect(clone.querySelector(".pb-ps-inline-image-wrap").style.textAlign).toBe("right");
    expect(clone.querySelector("img").style.width).toBe("240px");
    expect(image.style.width).toBe("240px");
    editor.remove();
});

test("all three image alignments and responsive sizes are supported", () => {
    const { editor, wrapper, image } = imageFixture();
    expect(alignPayslipImage(wrapper, "left")).toBe(true);
    expect(alignPayslipImage(wrapper, "center")).toBe(true);
    expect(alignPayslipImage(wrapper, "right")).toBe(true);
    expect(wrapper.style.textAlign).toBe("right");
    expect(resizePayslipImage(wrapper, "full")).toBe(true);
    expect(image.style.width).toBe("100%");
    expect(resizePayslipImage(wrapper, "original")).toBe(true);
    expect(image.style.width).toBe("");
    expect(alignPayslipImage(wrapper, "diagonal")).toBe(false);
    editor.remove();
});

