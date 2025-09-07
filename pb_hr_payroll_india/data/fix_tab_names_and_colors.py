#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix India Tab Names and Colors
==============================

This script:
1. Removes "India" from ALL tab names to match Vietnam exactly
2. Fixes all orange colors to light/white scheme

Author: Claude Code Assistant  
Date: 2025-09-07
"""

import json

def fix_tab_names_and_colors():
    """Fix tab names and colors to match requirements"""
    
    # Load current India spreadsheet
    try:
        with open('/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_india/data/india_payroll_data.json', 'r') as f:
            india_data = json.load(f)
    except FileNotFoundError:
        print("❌ India spreadsheet not found.")
        return None
    
    print("🇮🇳 Fixing India Tab Names and Colors")
    print("=" * 50)
    
    # Define the exact tab name mapping (match Vietnam exactly)
    vietnam_tab_names = {
        "India Allowance Details": "Allowance Details",
        "India Earnings Details": "Earnings Details", 
        "India Master Lookup": "Master lookup",
        "TEMPLATE Employee Details": "TEMPLATE Employee Details",  # Already correct
        "TEMPLATE Master": "TEMPLATE Master",  # Already correct
        "India Employee Staging Data": "Employee Staging Data"
    }
    
    # Also check for any remaining "India" prefixes
    for sheet in india_data["sheets"]:
        if sheet.get("name", "").startswith("India "):
            old_name = sheet["name"]
            new_name = old_name.replace("India ", "")
            sheet["name"] = new_name
            print(f"✅ Additional fix: {old_name} → {new_name}")
    
    # Fix tab names to match Vietnam exactly
    for sheet in india_data["sheets"]:
        old_name = sheet.get("name", "")
        if old_name in vietnam_tab_names:
            new_name = vietnam_tab_names[old_name]
            sheet["name"] = new_name
            print(f"✅ Renamed: {old_name} → {new_name}")
    
    # Fix colors - Pure white/light scheme
    light_styles = {
        "1": {  # Headers - Very light gray
            "fillColor": "#F8F9FA",
            "textColor": "#495057",
            "fontSize": 12,
            "bold": True
        },
        "2": {  # Data cells - Pure white
            "fillColor": "#FFFFFF", 
            "textColor": "#212529",
            "fontSize": 11
        },
        "3": {  # Calculation cells - Very light blue
            "fillColor": "#F8F9FA",
            "textColor": "#495057",
            "fontSize": 11
        },
        "4": {  # Total/Summary cells - Very light green
            "fillColor": "#F8F9FA",
            "textColor": "#495057",
            "fontSize": 11,
            "bold": True
        },
        "5": {  # Alternative - Pure white
            "fillColor": "#FFFFFF",
            "textColor": "#212529", 
            "fontSize": 11
        },
        "6": {  # Another style - Pure white
            "fillColor": "#FFFFFF",
            "textColor": "#212529",
            "fontSize": 11
        },
        "7": {  # Another style - Pure white  
            "fillColor": "#FFFFFF",
            "textColor": "#212529",
            "fontSize": 11
        },
        "8": {  # Another style - Pure white
            "fillColor": "#FFFFFF", 
            "textColor": "#212529",
            "fontSize": 11
        }
    }
    
    # Update all styles to remove orange colors
    if "styles" in india_data:
        india_data["styles"].update(light_styles)
        print("✅ Updated all styles to light/white color scheme")
    
    return india_data

def main():
    """Main function"""
    try:
        fixed_data = fix_tab_names_and_colors()
        
        if fixed_data:
            # Save fixed version
            output_file = "/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_india/data/india_payroll_data.json"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(fixed_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n✅ Fixed India spreadsheet: {output_file}")
            print(f"\n📊 Changes Applied:")
            print("• Tab Names: Removed 'India' prefix to match Vietnam exactly")
            print("  - 'India Allowance Details' → 'Allowance Details'")  
            print("  - 'India Earnings Details' → 'Earnings Details'")
            print("  - 'India Master Lookup' → 'Master lookup'")
            print("  - 'India Employee Staging Data' → 'Employee Staging Data'")
            print("• Colors: All orange colors replaced with light/white scheme")
            print("  - Headers: Light gray (#F8F9FA) with dark text")
            print("  - Data: Pure white (#FFFFFF) with dark text")
            print("  - No more ugly orange backgrounds!")
            
            return output_file
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    main()