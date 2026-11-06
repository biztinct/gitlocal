# UI Guidelines for hr_development_ai Module

## Icons
- **ALWAYS use Font Awesome (FA) icons** — NEVER use emoji icons (🎯 📊 etc.)
- Apply modern CSS styling to FA icons (color, margin, spacing)
- Example: `<i class="fa fa-bar-chart" style="color: #4A7DAA; margin-right: 4px;"></i>`
- FA icons are more consistent across platforms and look professional in Odoo

## Colors — AI Coaching Chat Questions Panel
- **Header gradient**: `linear-gradient(135deg, #4A7DAA, #3A6D94)` (darker blue)
- **Panel background**: `#D4E4F2` (light sky blue)
- **Button background**: `#E8F0F8` (very light blue)
- **Button text**: `#2C5F85` (dark blue)
- **Border**: `#B8D0E4` (medium blue)
- **Category label text**: `#3A6D94` (dark blue)
- **Icon accent**: `#4A7DAA` (medium blue)
- **Box shadow**: `rgba(74,125,170,0.12)`

## Auto-Scroll Strategy
- **Messages are rendered newest-first** (`reversed(messages)`) so the latest AI response is always visible at the top when the dialog reloads
- Do NOT use `<script>`, `<img onload>`, or any JS injection for scrolling — Odoo's HTML widget strips/doesn't execute them

## Sticky Elements
- **Questions panel**: `position: sticky; top: 0;` — stays visible when scrolling down
- **Message input**: `position: sticky; bottom: 0;` — always accessible at the bottom

## General Rules
- Avoid raw JSON in UI — always format dicts/lists as readable HTML
- Use `button type="object"` with `context` for click actions — never use inline `onclick` JS
- Keep question chips compact with short labels; full question text goes in `context`
- Use `<details>/<summary>` for collapsible sections (lightweight, zero-JS)
