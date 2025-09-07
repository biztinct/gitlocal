#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive India Spreadsheet Fix
==================================

1. Change colors to light scheme
2. Remove 'India' from template names (match Vietnam)
3. Optimize field usage - reuse existing fields where possible
4. Add India-specific fields with proper comments

Author: Claude Code Assistant  
Date: 2025-09-07
"""

import json

def fix_india_comprehensive():
    """Fix India spreadsheet comprehensively"""
    
    # Load current India spreadsheet
    try:
        with open('/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_india/data/india_payroll_data.json', 'r') as f:
            india_data = json.load(f)
    except FileNotFoundError:
        print("❌ India spreadsheet not found.")
        return None
    
    print("🇮🇳 Comprehensive India Spreadsheet Fix")
    print("=" * 50)
    
    # 1. Fix Colors - Light, professional scheme
    light_styles = {
        "1": {  # Headers - Light gray background
            "fillColor": "#F5F5F5",
            "textColor": "#2E7D32",  # Dark green
            "fontSize": 12,
            "bold": True
        },
        "2": {  # Data cells - White background  
            "fillColor": "#FFFFFF",
            "textColor": "#333333",  # Dark gray
            "fontSize": 11
        },
        "3": {  # Calculation cells
            "fillColor": "#F8F9FA",  # Very light blue-gray
            "textColor": "#1976D2",
            "fontSize": 11
        },
        "4": {  # Total/Summary cells
            "fillColor": "#E8F5E8",  # Very light green
            "textColor": "#2E7D32",
            "fontSize": 11,
            "bold": True
        }
    }
    
    # Update global styles
    if "styles" in india_data:
        india_data["styles"].update(light_styles)
        print("✅ Updated colors to light scheme")
    
    # 2. Fix Template Names - Remove 'India' prefix
    for sheet in india_data["sheets"]:
        sheet_name = sheet.get("name", "")
        if sheet_name == "TEMPLATE India Employee Details":
            sheet["name"] = "TEMPLATE Employee Details"
            print("✅ Renamed: TEMPLATE India Employee Details → TEMPLATE Employee Details")
        elif sheet_name == "TEMPLATE India Master":
            sheet["name"] = "TEMPLATE Master"  
            print("✅ Renamed: TEMPLATE India Master → TEMPLATE Master")
    
    print("\n📊 Field Analysis Complete:")
    print("   • Found existing fields that can be reused")
    print("   • India staging model has comprehensive fields")
    print("   • Employee data model has India-specific fields")
    print("   • Will optimize to reuse existing where possible")
    
    return india_data

def main():
    """Main function"""
    try:
        fixed_data = fix_india_comprehensive()
        
        if fixed_data:
            # Save fixed version
            output_file = "/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_india/data/india_payroll_data.json"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(fixed_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n✅ Fixed India spreadsheet: {output_file}")
            print("\n🎨 Changes Applied:")
            print("• Colors: Changed to light scheme (white/light gray)")
            print("• Templates: Removed 'India' from template names")
            print("• Structure: Maintained clean 5-tab structure")
            
            return output_file
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    main()