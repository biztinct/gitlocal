/** @odoo-module **/
import { after, describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { click, queryAllTexts, queryFirst, waitFor } from "@odoo/hoot-dom";
import { Component, xml } from "@odoo/owl";
import { makeDialogMockEnv, mountWithCleanup, defineModels, models, fields, mountView, clickSave, getService, onRpc } from "@web/../tests/web_test_helpers";
import { collectRequired, createRequiredValidation } from "@biz_theme/js/required_fields";
import "@biz_theme/js/native_required_fields";

describe.current.tags("desktop");
class Panel extends Component {
    static template = xml`<div data-biz-validation-scope="true">
        <label for="qa-name">Name <span class="pbva-field-required">Required</span></label><input id="qa-name" required="required"/>
        <label><span>Department *</span><select id="qa-dept"><option value="">Choose…</option><option value="1">People</option></select></label>
        <label for="qa-zero">Amount *</label><input id="qa-zero" type="number" required="required" value="0"/>
        <input aria-label="Disabled" required="required" disabled="disabled"/>
        <input aria-label="Read only" required="required" readonly="readonly"/>
        <input aria-label="Hidden" required="required" style="display:none"/>
        <input aria-label="Optional"/>
        <button type="button" class="qa-save" data-biz-validate="true" t-on-click="save">Save</button>
    </div>`;
    static props = {};
    saved = 0;
    save() { this.saved++; }
}
async function panel() {
    const env = await makeDialogMockEnv();
    const component = await mountWithCleanup(Panel, { env });
    after(() => env.services.biz_required_fields.destroy());
    return { env, component, root: queryFirst("[data-biz-validation-scope]") };
}

test("all missing fields are listed; hidden, readonly, optional and zero values are excluded", async () => {
    const { root } = await panel();
    queryFirst("#qa-name").value = "   ";
    expect(collectRequired(root).map(f => f.label)).toEqual(["Name", "Department"]);
});

test("popup keeps the draft, then focuses and highlights the first field", async () => {
    const { env, root } = await panel();
    const validation = createRequiredValidation(env.services.dialog, root, root);
    after(() => validation.destroy());
    expect(validation.validate(root)).toBe(false);
    await animationFrame();
    expect(queryAllTexts(".biz-required-list li")).toEqual(["Name", "Department"]);
    expect("#qa-name").toHaveClass("biz-required-invalid");
    expect("#qa-dept").toHaveClass("biz-required-invalid");
    validation.validate(root);
    await animationFrame();
    expect(".biz-required-dialog").toHaveCount(1);
    await click(".biz-required-dialog footer button");
    await animationFrame();
    await animationFrame();
    expect(document.activeElement).toBe(queryFirst("#qa-name"));
    const first = queryFirst("#qa-name");
    first.value = "Kept draft";
    first.dispatchEvent(new Event("input", { bubbles: true }));
    expect(first).not.toHaveClass("biz-required-invalid");
    expect("#qa-dept").toHaveClass("biz-required-invalid");
    queryFirst("#qa-dept").value = "1";
    expect(validation.validate(root)).toBe(true);
    expect(first.value).toBe("Kept draft");
});

test("Escape closes validation without reaching the underlying panel", async () => {
    const { env, root } = await panel();
    const validation = createRequiredValidation(env.services.dialog, root, root);
    after(() => validation.destroy());
    validation.validate(root);
    await animationFrame();
    root.addEventListener("keydown", () => expect.step("underlying close"));
    root.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await animationFrame(); await animationFrame();
    expect(".biz-required-dialog").toHaveCount(0);
    expect(document.activeElement).toBe(queryFirst("#qa-name"));
    expect.verifySteps([]);
});

test("custom Save blocks its handler until all mandatory values are present", async () => {
    const { component } = await panel();
    await click(".qa-save"); await animationFrame();
    expect(component.saved).toBe(0);
    expect(queryAllTexts(".biz-required-list li")).toEqual(["Name", "Department"]);
    await click(".biz-required-dialog footer button");
    await animationFrame(); await animationFrame();
    queryFirst("#qa-name").value = "Complete";
    queryFirst("#qa-dept").value = "1";
    await click(".qa-save"); await animationFrame();
    expect(component.saved).toBe(1);
});

class Choices extends Component {
    static props = {};
    static template = xml`<div data-biz-validation-scope="true">
      <label><input id="qa-check" type="checkbox" required="required" data-biz-required-label="Consent"/>Consent *</label>
      <input id="qa-radio-a" name="qa-choice" type="radio" required="required" data-biz-required-label="Choice"/>
      <input id="qa-radio-b" name="qa-choice" type="radio" required="required" data-biz-required-label="Choice"/>
      <div id="qa-group" data-biz-required="Abilities" data-biz-missing="true" tabindex="-1"><button>Pick an ability</button></div>
    </div>`;
}
test("checkboxes, radio groups and custom choice groups report their missing values once", async () => {
    const env = await makeDialogMockEnv();
    after(() => env.services.biz_required_fields.destroy());
    await mountWithCleanup(Choices, { env });
    const root = queryFirst("[data-biz-validation-scope]");
    expect(collectRequired(root).map(f => f.label)).toEqual(["Consent", "Choice", "Abilities"]);
    queryFirst("#qa-check").checked = true;
    queryFirst("#qa-radio-b").checked = true;
    queryFirst("#qa-group").setAttribute("data-biz-missing", "false");
    expect(collectRequired(root)).toEqual([]);
});

class MandatoryQa extends models.Model {
    _name = "mandatory.qa";
    name = fields.Char({ string: "Name", required: true });
    code = fields.Char({ string: "Reference", required: true });
    amount = fields.Integer({ required: true });
}
defineModels([MandatoryQa]);

test("native Save lists every required field and never calls create", async () => {
    onRpc("mandatory.qa", "web_save", () => expect.step("save"));
    await mountView({ type: "form", resModel: "mandatory.qa", arch: '<form><group><field name="name"/><field name="code"/><field name="amount"/></group></form>' });
    await clickSave();
    await animationFrame();
    expect(queryAllTexts(".biz-required-list li")).toEqual(["Name", "Reference"]);
    await click(".biz-required-dialog footer button");
    await animationFrame(); await animationFrame();
    expect(document.activeElement).toBe(queryFirst('[name="name"] input'));
    expect('[name="name"]').toHaveClass("biz-required-invalid");
    expect.verifySteps([]);
    getService("biz_required_fields").destroy();
});

test("native Save reveals a missing field on another notebook page", async () => {
    await mountView({ type: "form", resModel: "mandatory.qa", arch: '<form><field name="name" invisible="1"/><notebook><page string="Overview" name="overview"><field name="amount"/></page><page string="Details" name="details"><field name="code"/></page></notebook></form>' });
    await clickSave(); await animationFrame();
    expect(queryAllTexts(".biz-required-list li")).toEqual(["Reference"]);
    await click(".biz-required-dialog footer button");
    await waitFor('[name="code"].biz-required-invalid');
    expect(document.activeElement).toBe(queryFirst('[name="code"] input'));
    expect('[name="code"]').toHaveClass("biz-required-invalid");
    getService("biz_required_fields").destroy();
});
