# Việt Úc Clinic Official Theme (Odoo 19 CE)

Official Việt Úc Clinic branding implementation for Odoo 19 Community Edition, based on the comprehensive brand guidelines from Brandingcompressed.pdf.

## Brand Essence

**Trustworthy • Professional • Compassionate • Modern & Clean**

This theme embodies the Việt Úc Clinic brand identity with its signature Deep Blue palette, professional typography, and accessible design system optimized for healthcare workflows.

## Features

- ✅ **Official Việt Úc Branding**: Complete implementation of Brandingcompressed.pdf guidelines
- ✅ **Professional Color System**: Deep Blue (#1565C0) + Accent Blue (#42A5F5) UI palette
- ✅ **Brand Typography**: Montserrat headings + Segoe body text hierarchy
- ✅ **WCAG AA Compliant**: All color combinations meet accessibility standards
- ✅ **Odoo 19 Native**: Uses `web._assets_primary_variables` for proper SCSS variable override
- ✅ **Zero Dependencies**: Only depends on core `web` module
- ✅ **Lightweight**: Minimal CSS footprint, maximum performance

## Official Color Palette

### Primary Logo Colors (Brand Identity - Never Alter)
These colors are reserved exclusively for logo and brand elements:

- **Hibiscus Red**: `#E53935` - Logo flower (passion, trust, responsibility)
  - Dark: `#C32B2E` | Darker: `#8B1A1F` | Light: `#F07C75` | Lightest: `#FBE3E1`
- **Hibiscus Orange**: `#FB8C00` - Logo flower gradient
  - Dark: `#D46E00` | Darker: `#9C4C00` | Light: `#FCB24D` | Lightest: `#FEE8C9`
- **Leaf Green**: `#43A047` - Logo leaf (natural, health-related)
  - Dark: `#3A8A41` | Darker: `#2E6B33` | Light: `#7BC685` | Lightest: `#DBF0DB`

### Secondary UI Colors (Application Theme)
Primary interface colors for the Odoo application:

- **Deep Blue**: `#1565C0` - Primary actions, buttons, navbar (calm & professional)
  - Darkest: `#0D356B` | Darker: `#1356A9` | Light: `#83C5FA` | Lightest: `#E4F4FD`
- **Accent Blue**: `#42A5F5` - Interactive elements, hover states (modern & engaging)
  - Darkest: `#1F5E97` | Darker: `#2E74BD` | Light: `#83C5FA` | Lightest: `#E4F4FD`

### Neutral Tones (Clean Professional Aesthetic)
- **Black**: `#121212` - Absolute darkest
- **Text Primary**: `#212121` - Main text color (high contrast)
- **Text Secondary**: `#424242` - Secondary text, muted content
- **Gray Light**: `#F5F5F5` - Light backgrounds, surface
- **Gray Lighter**: `#FAFAFA` - Subtle surface variations
- **White**: `#FFFFFF` - Main background, cards

### State Colors (Healthcare Compliance)
From Healthcare_Colour_Palette.pdf for consistent medical workflows:

- **Success**: `#176B47` (Medical green - positive outcomes)
- **Info**: `#2A7ABF` (Information blue - system messages)
- **Warning**: `#946200` (Caution amber - important notices)
- **Danger**: `#C0332A` (Alert red - critical actions)

## Typography System

### Official Brand Fonts
Based on Brandingcompressed.pdf page 19:

- **Primary Headings**: Montserrat
  - Regular 400, Semi Bold 600, Extra Bold 800
  - Used for: H1-H6, page titles, section headers
- **Body Text**: Segoe UI
  - Regular 400, Semi Bold 600, Bold 700
  - Used for: Paragraphs, labels, form fields, buttons
- **Fallback**: Arial (system fallback for compatibility)

### Implementation
```scss
$font-family-headings: 'Montserrat', 'Segoe UI', Arial, sans-serif;
$font-family-sans-serif: 'Segoe UI', Arial, sans-serif;
```

Fonts are loaded from Google Fonts CDN for optimal performance.

## UI Components

### Buttons
- **Primary**: Deep Blue (#1565C0) - Main actions, submit buttons
- **Secondary**: Accent Blue (#42A5F5) - Alternative actions
- **Hover States**: Darker shades for professional feedback

### Badges (ID, Age, etc.)
Professional pill-shaped badges with:
- Gradient backgrounds (Accent Blue tones)
- Deep Blue borders and labels
- Subtle shadows for depth
- Smooth hover transitions

### Navbar
- Deep Blue (#1565C0) background
- White text and icons
- Light hover states for navigation

### Forms & Cards
- Clean white backgrounds
- Subtle shadows for depth
- 6px border radius for modern look

## Installation

### Standard Installation
1. Copy `health_theme` to your Odoo addons directory
2. Update app list: **Apps → Update Apps List**
3. Install module: Search "Việt Úc Clinic Official Theme" and click **Install**
4. Refresh browser with **Ctrl+Shift+R** (Windows/Linux) or **Cmd+Shift+R** (Mac)

### Docker Installation
```bash
docker-compose restart odoo
# Then hard refresh browser
```

## Technical Architecture

This theme follows Odoo 19's best practices for SCSS theming:

### SCSS Variable Override Pattern
Uses `web._assets_primary_variables` to override Odoo's core variables **before** compilation:

```scss
// Odoo brand overrides
$o-brand-odoo: $vu-deep-blue;
$o-brand-primary: $vu-deep-blue;
$o-brand-secondary: $vu-accent-blue;

// Bootstrap overrides
$primary: $vu-deep-blue;
$secondary: $vu-accent-blue;
$link-color: $vu-deep-blue;
```

### File Structure
```
health_theme/
├── __manifest__.py                      # Module definition with branding docs
├── views/
│   └── webclient_templates.xml         # Theme color meta tag
└── static/src/scss/
    ├── primary_variables.scss           # Core variable overrides (185 lines)
    └── backend.scss                     # Component styling (typography, badges, etc.)
```

### Asset Loading Order
1. `primary_variables.scss` - Prepended to `web._assets_primary_variables`
2. Odoo core SCSS compilation
3. `backend.scss` - Loaded in `web.assets_backend`

This ensures proper variable inheritance and override behavior.

## Upgrade from Previous Version

If you're upgrading from an older version (teal theme):

```bash
./odoo-bin -c odoo.conf -d your_database -u health_theme --stop-after-init
```

Then restart Odoo and hard refresh your browser.

**Note**: This upgrade replaces the previous teal color palette (#0F6D66) with the official Deep Blue palette (#1565C0).

## Troubleshooting

### Colors not applying after installation?
1. Upgrade the module: `odoo-bin -u health_theme`
2. Restart Odoo server
3. Clear browser cache: **Ctrl+Shift+R** or **Cmd+Shift+R**
4. Check browser console for asset loading errors

### Still not working?
- Verify module is installed (not just "to install")
- Check Odoo logs for SCSS compilation errors
- Ensure no other theme modules are conflicting
- Try incognito/private browsing window

### Fonts not loading?
- Verify Google Fonts CDN access
- Check network tab for font loading errors
- Fallback to Segoe UI/Arial if CDN blocked

## Brand Compliance

### Logo Usage
The Primary Logo Colors (Hibiscus Red, Orange, Leaf Green) are **reserved exclusively** for:
- Company logo
- Brand marks
- Marketing materials

**DO NOT** use these colors for UI elements, buttons, or general interface components.

### UI Color Usage
Always use Secondary UI Colors (Deep Blue, Accent Blue) for:
- Buttons and interactive elements
- Navigation and menus
- Links and hover states
- Form controls

### Typography Rules
- **Headings**: Always use Montserrat (Semi Bold 600)
- **Body**: Always use Segoe UI (Regular 400)
- **Emphasis**: Use Semi Bold 600 or Bold 700, never italic
- **Never**: Mix fonts within the same component

## Version History

### 19.0.2.0.0 (Current)
- Implemented official Việt Úc Clinic branding from Brandingcompressed.pdf
- Replaced teal palette with Deep Blue (#1565C0) + Accent Blue (#42A5F5)
- Added Montserrat + Segoe typography system
- Enhanced badge styling with gradients and shadows
- Updated navbar to Deep Blue theme

### 19.0.1.0.0 (Legacy)
- Initial teal/blue-teal healthcare theme
- Basic color palette implementation

## License

LGPL-3

## Credits

**Author**: VAFHS Healthcare System - Vietnam-Australia Family Health Service
**Website**: https://vafhs.com
**Branding**: Based on official Việt Úc Clinic Brand Guidelines (Brandingcompressed.pdf)
**Architecture**: Inspired by MuK Web Theme patterns for Odoo 19 CE

---

**Made with ❤️ for Việt Úc Clinic by VAFHS Healthcare System**
