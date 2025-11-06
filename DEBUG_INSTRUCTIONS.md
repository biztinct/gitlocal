# HR Analytics Dashboard - Debug Instructions

## Problem Summary
- Dashboard form loads but charts don't display
- No `[HR Analytics]` debug messages appear in browser console
- This indicates the custom FormController is not being loaded

## Root Cause
The JavaScript files are properly declared in the manifest, but Odoo hasn't restarted to regenerate the asset bundle. Odoo caches and minifies JavaScript files when it starts up.

## Solution Steps

### Step 1: Restart Odoo Server
You need to **completely restart the Odoo server** to pick up the new asset files:

```bash
# If running Odoo locally:
# Press Ctrl+C to stop the server
# Then restart it with:
python -m odoo -c odoo.conf -d your_database --dev=reload,qweb,werkzeug,xml
```

### Step 2: Clear Browser Cache
After restarting the server, **clear your browser cache**:

#### Chrome/Edge:
1. Press `Ctrl+Shift+Delete` (Windows) or `Cmd+Shift+Delete` (Mac)
2. Select "All time" or "Last 7 days"
3. Check "Cookies and other site data" and "Cached images and files"
4. Click "Clear data"

#### Firefox:
1. Press `Ctrl+Shift+Delete` (Windows) or `Cmd+Shift+Delete` (Mac)
2. Select "Everything"
3. Click "Clear Now"

### Step 3: Force Hard Refresh
After clearing cache, perform a **hard refresh** of the dashboard page:
- `Ctrl+F5` (Windows) or `Cmd+Shift+R` (Mac)
- Or hold `Shift` and click the refresh button

### Step 4: Check Browser Console
Open the browser developer tools (`F12` or `Ctrl+Shift+I`) and look at the **Console** tab.

You should now see these debug messages:
```
[HR Analytics] Dashboard.js file loaded - about to define module
[HR Analytics] Dashboard module definition starting...
[HR Analytics] Attempting to load ChartLib...
[HR Analytics] Charts.js file loaded
[HR Analytics] Chart object available: true
[HR Analytics] FormController require complete, ChartLib available: true
[HR Analytics] Dashboard FormController successfully registered as pb_hr_payroll_analytics.Dashboard
[HR Analytics] FormController initialized
[HR Analytics] willStart called
[HR Analytics] Loading Chart.js from CDN...
[HR Analytics] Chart.js loaded successfully
[HR Analytics] start called
[HR Analytics] Setting up dashboard...
[HR Analytics] _setupDashboard called
[HR Analytics] Chart.js available: true
[HR Analytics] ChartLib available: true
[HR Analytics] Loading initial tab data (personnel_costs)...
[HR Analytics] _loadPersonnelCostsCharts: Loading Personnel Costs charts...
[HR Analytics] doughnut-chart-personnel element: <canvas>
[HR Analytics] Creating doughnut chart...
```

### Step 5: Verify Chart Rendering
Once you see these logs, the charts should appear:
- Personnel Costs tab: 2 charts (Doughnut breakdown, Stacked bar salary components)
- Cross-Country tab: 3 charts (Vertical bar costs, Pie headcount, Scatter plot)
- Statutory Contributions tab: 2 charts
- Headcount tab: 1 pie chart
- Dependents tab: 1 vertical bar chart
- Budget Variance tab: 2 charts (Budget vs Actual, Variance %)
- Annual Costs tab: 1 line chart

## Current Status: JavaScript Loading Success ✅

The JavaScript modules are now loading successfully! You should see in the console:
```
[HR Analytics] Dashboard.js file loaded - about to define module
[HR Analytics] Charts.js file loaded
[HR Analytics] DashboardController class created successfully
[HR Analytics] Dashboard module fully loaded and exported
```

## Next Issue: FormController Not Instantiating

The JavaScript modules are defined and registered, BUT the FormController's lifecycle methods (init, willStart, start) are not being called. This means the form is not using our custom controller.

### Diagnostic Steps

#### Step 1: Verify What's on Screen
1. Open the Analytics Dashboard
2. **What do you see?**
   - A form with fields (Country, Date From, Date To, stat cards)?
   - A list/tree view of dashboard records?
   - Something else?

**If you see a list view**, the issue is that the form action is not executing properly.

**If you see a form**, proceed to Step 2.

#### Step 2: Inspect the Form HTML

1. Right-click on any field in the form
2. Select **Inspect** (or **Inspect Element**)
3. Look for the `<form>` tag
4. Check if it has `js_class="pb_hr_payroll_analytics.Dashboard"`

**Expected HTML:**
```html
<form ... js_class="pb_hr_payroll_analytics.Dashboard" ...>
```

**If js_class is NOT there**, the issue is the view not being loaded correctly.

#### Step 3: Check for JavaScript Errors

1. In the browser console (F12)
2. Look for **RED error messages**
3. Expand them to see full stack traces
4. Take note of any errors and provide them

**Common errors to look for:**
- `Uncaught SyntaxError` in JavaScript
- `Cannot read property X of undefined`
- `Module not found: pb_hr_payroll_analytics.Dashboard`

#### Step 4: Check the Network Tab

1. Open browser DevTools (F12)
2. Go to **Network** tab
3. Hard refresh the page (`Ctrl+F5`)
4. Look for these files and verify they loaded (status 200):
   - `hr_analytics_dashboard.js`
   - `hr_analytics_charts.js`
   - Check for any files that returned errors (red status codes like 404)

#### Step 5: Check Odoo Console Logs

In the browser console, scroll up and look for all `[HR Analytics]` messages in order:
1. `Dashboard.js file loaded` ✅ (should see this)
2. `Charts.js file loaded` ✅ (should see this)
3. `FormController init called` ❌ (if you DON'T see this, the controller isn't being instantiated)

---

## If Charts Still Don't Appear

### Check for JavaScript Errors
1. Look in the Console tab for any RED error messages
2. Look at the **Network** tab to verify the JavaScript files loaded:
   - `hr_analytics_dashboard.js`
   - `hr_analytics_charts.js`
   - `chart.min.js` (from CDN)

### Verify Module Installation
```bash
# In Odoo, go to Settings > Apps and search for "analytics"
# Should see "HR Analytics & Reporting" as "Installed"
```

### Check Odoo Log File
Look at the Odoo server console output for errors:
```
ERROR pb_hr_payroll_analytics
WARNING pb_hr_payroll_analytics
```

## Expected Behavior After Fix

1. **Page Load**: Dashboard form loads with:
   - Global filter section (Country, Date From, Date To)
   - Quick stat cards showing values
   - 7 navigation tabs

2. **Tab 1 - Personnel Costs**:
   - Doughnut chart showing cost breakdown by department
   - Stacked bar chart showing salary components (Basic, Allowances, Contributions)

3. **Tab 2 - Cross Country**:
   - Vertical bar chart showing costs by country
   - Pie chart showing headcount distribution
   - Scatter plot showing cost per employee vs headcount

4. **Tabs 3-7**: Similar charts for each category

5. **Refresh Button**: Updates all charts with fresh data

## Technical Details for Advanced Debugging

### Check Asset Pipeline
If the JavaScript files still aren't loading, check Odoo's asset pipeline:

1. Go to `Settings > Technical > Assets`
2. Look for bundles with `pb_hr_payroll_analytics` in the name
3. Click on `web.assets_backend` bundle
4. Verify these files are included:
   - `pb_hr_payroll_analytics/static/src/css/hr_analytics_dashboard.css`
   - `pb_hr_payroll_analytics/static/src/css/hr_analytics_responsive.css`
   - `pb_hr_payroll_analytics/static/src/js/hr_analytics_dashboard.js`
   - `pb_hr_payroll_analytics/static/src/js/hr_analytics_charts.js`

### Verify Form View Configuration
Check that the dashboard view has the custom controller:
1. Go to `Settings > Technical > Views`
2. Search for "HR Analytics Dashboard"
3. Verify the form has: `js_class="pb_hr_payroll_analytics.Dashboard"`

## If You Still Need Help

Provide the following information:
1. **Odoo version and module version**: From installed modules list
2. **Browser console output**: The complete Console tab content
3. **Network tab output**: The JavaScript file requests and their status
4. **Error logs**: Any error messages from the Odoo server console

---

**Note**: This is a debugging guide for the HR Analytics module chart display issue. The module is fully functional once the asset pipeline properly loads the JavaScript files.
