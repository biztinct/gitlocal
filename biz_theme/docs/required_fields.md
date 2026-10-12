# Required-field feedback

`biz_required_fields` is a shared service in the backend and frontend theme bundles. Standard form Save and workflow actions use the relational model's existing required-field checks. They retain server validation, field modifiers, access checks and numeric-zero semantics.

A rejected save opens one accessible dialog listing the missing field labels. Closing the dialog (button, X or Escape) focuses the first missing field after overlay teardown. Native notebook pages are opened as necessary. The first field receives a three-pixel highlight without shifting the layout. Correcting a field clears its highlight; drafts stay in place.

## Custom panels

Give the panel `data-biz-validation-scope="true"` when it is not already a `form`, `.pbim-modal`, `.pplw-card` or `[role="dialog"]`. Annotate Save/Create/Submit actions with `data-biz-validate="true"`. Retain guards for permissions, processing, invalid proofs and other business rules; missing required values alone should not disable the action.

Declare mandatory inputs using `required` or `aria-required="true"`. Existing labels ending in `*` are also recognised. Use a real associated label; `aria-label` provides a label when one is absent. A custom choice group can use `data-biz-required="Field label"`, a reactive `data-biz-missing="true|false"`, and focusable choices. Explicit `data-biz-required-label` overrides the label if needed. Optional, hidden, disabled and read-only controls are excluded. Whitespace is empty in custom text inputs; numeric zero remains valid.

For conditional mandatory values, render or update this metadata with the same state used by the component's validation. A custom save invoked outside a DOM event can call `env.services.biz_required_fields.validate(panelElement)` and return when false. Existing domain-specific validation should remain after this check.

The shared service does not infer undeclared business requirements or remove server validation. New custom panels must declare their required fields and save action. The rollout registers 74 existing actions and replaces missing-value-only button guards in role editing, people and payroll wizards, hiring, holidays, objectives and reason dialogs.
