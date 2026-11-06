# Odoo 19 — Premium CSS/JS Design Guide

> Key learnings from implementing premium UI dashboards in Odoo 19.
> Follows the proven `pb_hr_workforce` pattern that works across modules.

---

## 1. Asset Loading — The Only Safe Pattern

### ✅ DO: Register CSS in `__manifest__.py` under `web.assets_backend`

```python
'assets': {
    'web.assets_backend': [
        'your_module/static/src/css/your_dashboard.css',
        'your_module/static/src/js/your_dashboard.js',
        'your_module/static/src/components/your_component/your_component.xml',
    ],
},
```

CSS files registered this way are **compiled into Odoo's global asset bundle**. They load on every backend page — so **selector scoping is critical** (see §2).

### ❌ DON'T: Inject CSS via JavaScript `<link>` tags

Dynamic `<link>` injection causes:
- **SPA leakage** — styles persist after navigating away (Odoo is a single-page app)
- **Flash of unstyled content** — CSS loads after HTML renders
- **Lifecycle complexity** — requires mount/unmount cleanup that's fragile

### ❌ DON'T: Use `@import url()` in `.scss` files

```scss
/* THIS WILL SILENTLY BREAK YOUR ENTIRE STYLESHEET */
@import url('https://fonts.googleapis.com/css2?family=Inter&display=swap');
```

Odoo 19 uses **Dart Sass** for SCSS compilation. `@import url()` is unsupported and causes the **entire file to silently fail** — zero CSS output, zero error messages.

### ✅ DO: Load external fonts via JavaScript

```javascript
if (!document.getElementById('my-font-link')) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.id = 'my-font-link';
    link.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap';
    document.head.appendChild(link);
}
```

This runs once at module load — the font `<link>` persists harmlessly across pages.

---

## 2. CSS Selector Naming — Prefix EVERYTHING

### The Rule: Every CSS class must start with a unique module prefix

| Module | Prefix | Examples |
|--------|--------|----------|
| `pb_hr_workforce` | `.wf-` | `.wf-dash-header`, `.wf-kpi-card`, `.wf-kpi-value` |
| `pb_hr_workforce` (attendance) | `.atl-` | `.atl-container`, `.atl-toolbar` |
| `pb_hr_workforce` (timecard) | `.tc-` | `.tc-container`, `.tc-toolbar` |
| `pb_hr_workforce` (payroll) | `.prd-` | `.prd-container`, `.prd-title` |
| `hr_development_ai` | `.bfsi-` | `.bfsi-dashboard-header`, `.bfsi-summary-card` |

### ❌ NEVER use generic class names

These WILL break other Odoo pages:
```css
/* BAD — conflicts with Odoo core, Bootstrap, other modules */
.summary-card { }
.card-icon { }
.filter-btn { }
.header-left { }
.card-value { }
.dashboard-title { }
```

### ✅ Always prefix

```css
/* GOOD — unique to your module, safe globally */
.bfsi-summary-card { }
.bfsi-card-icon { }
.bfsi-filter-btn { }
.bfsi-header-left { }
.bfsi-card-value { }
.bfsi-dash-title { }
```

### SVG / inner element classes — also prefix

Even classes inside SVGs (`.ring-bg`, `.score-high`) need prefixing:
```css
.bfsi-ring-bg { }
.bfsi-ring-fill { }
.bfsi-score-high { }
```

---

## 3. CSS Variables — Scope to Root Container

Define CSS variables on the **dashboard root class**, not `:root`:

```css
.bfsi-manager-dashboard {
    --bfsi-primary: #7C3AED;
    --bfsi-success: #10B981;
    --bfsi-card-bg: #ffffff;
    --bfsi-card-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
    --bfsi-card-radius: 16px;
    --bfsi-font: 'Inter', -apple-system, sans-serif;
}
```

This keeps variables isolated to your component tree.

---

## 4. File Organization (pb_hr_workforce Pattern)

```
your_module/
├── static/
│   └── src/
│       ├── css/                          # Standalone CSS files
│       │   ├── your_dashboard.css        # Premium styles (all selectors prefixed)
│       │   └── your_other_view.css
│       ├── js/                           # Standalone JS files
│       │   ├── your_dashboard.js
│       │   └── your_other_view.js
│       └── components/                   # OWL components (if using)
│           └── your_component/
│               ├── your_component.js
│               ├── your_component.xml
│               └── your_component.scss   # Component-scoped SCSS (no @import url!)
```

### File permissions on server

After deploying via `rsync`/`scp`, always fix ownership:
```bash
sudo chown -R odoo:ubuntu /odoo/odoo-server/addons/your_module/static/
sudo chmod -R 775 /odoo/odoo-server/addons/your_module/static/
```

Files owned by `ubuntu` instead of `odoo` can cause silent asset loading failures.

---

## 5. Module Upgrade — When Assets Don't Load

After changing CSS/JS files, a simple server restart may not be enough:

```bash
# 1. Clear cached asset bundles
sudo -u odoo psql YOUR_DB -c "DELETE FROM ir_attachment WHERE url LIKE '%/web/assets/%';"

# 2. Upgrade the module (recompiles assets)
sudo -u odoo python3 /odoo/odoo-server/odoo-bin \
    --config=/etc/odoo-server.conf \
    -u your_module --stop-after-init

# 3. Start server
sudo service odoo-server start
```

### Hard refresh in browser

Always **Ctrl+Shift+R** (or Cmd+Shift+R on Mac) after deploying CSS changes — browsers cache aggressively.

---

## 6. OWL Component vs Server-Side Form View

| Approach | Used By | CSS Loaded Via | Template |
|----------|---------|---------------|----------|
| **OWL Client Action** | `hr_development_ai` | Manifest `assets` | `.xml` OWL template |
| **Server Form View** | `pb_hr_workforce` | Manifest `assets` | Server-side `ir.ui.view` XML |

Both work equally well. The CSS loading mechanism is identical — manifests register assets into `web.assets_backend` bundle.

- **OWL**: Better for highly interactive dashboards with complex state management
- **Server Form View**: Simpler for chart-focused dashboards with minimal JS interaction

---

## 7. Checklist Before Deploying Premium CSS

- [ ] Every CSS selector starts with module-specific prefix
- [ ] No `@import url()` in `.scss` files
- [ ] External fonts loaded via JS `<link>` element
- [ ] CSS registered in `__manifest__.py` → `web.assets_backend`
- [ ] XML template class names match CSS selectors exactly
- [ ] JS class name references match CSS selectors exactly
- [ ] File permissions: `odoo:ubuntu` / `775` on server
- [ ] Asset cache cleared before upgrade
- [ ] Tested dashboard page styling
- [ ] Tested that Apps/other pages are NOT broken
