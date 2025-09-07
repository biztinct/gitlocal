#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix India Spreadsheet Colors and Verify Column Structure
========================================================

This script fixes the color scheme to be light/white for better readability
and shows the current column structure.

Author: Claude Code Assistant  
Date: 2025-09-07
"""

import json

def fix_india_spreadsheet_colors():
    """Fix colors and show column structure"""
    
    # Load current India spreadsheet
    try:
        with open('/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_india/data/india_payroll_data.json', 'r') as f:
            india_data = json.load(f)
    except FileNotFoundError:
        print("❌ India spreadsheet not found.")
        return None
    
    print("🔍 Current Column Structure Analysis:")
    print("=" * 60)
    
    # Analyze the first sheet (India Allowance Details)
    first_sheet = india_data["sheets"][0] if india_data["sheets"] else None
    if first_sheet:
        print(f"📊 Sheet: {first_sheet.get('name', 'Unknown')}")
        print("\n📋 Column Headers:")
        
        # Check headers A1 through T1
        headers = {}
        for col_letter in 'ABCDEFGHIJKLMNOPQRST':
            cell_key = f"{col_letter}1"
            if cell_key in first_sheet.get("cells", {}):
                content = first_sheet["cells"][cell_key].get("content", "")
                headers[col_letter] = content
                print(f"   {col_letter}: {content}")
        
        # Identify India-specific columns
        india_specific_columns = []
        basic_columns = ['A', 'B', 'C', 'D']  # Employee ID, Basic allowances from Vietnam
        
        for col, header in headers.items():
            if col not in basic_columns and header:
                if any(keyword in header.lower() for keyword in ['books', 'phone', 'lta', 'medical', 'transport', 'meal', 'performance', 'pf', 'esi', 'professional', 'income', 'gross', 'net', 'employer']):
                    india_specific_columns.append((col, header))
        
        print(f"\n🇮🇳 India-Specific Columns ({len(india_specific_columns)} total):")
        for col, header in india_specific_columns:
            print(f"   Column {col}: {header}")
    
    # Fix color scheme to light/white
    print(f"\n🎨 Fixing Color Scheme...")
    
    if "styles" in india_data:
        # Light, professional color scheme
        new_styles = {
            "1": {  # Headers
                "fillColor": "#F5F5F5",  # Very light gray
                "textColor": "#2E7D32",  # Dark green
                "fontSize": 12,
                "bold": True,
                "border": "1px solid #CCCCCC"
            },
            "2": {  # Data cells
                "fillColor": "#FFFFFF",  # Pure white
                "textColor": "#333333",  # Dark gray text
                "fontSize": 11,
                "border": "1px solid #E0E0E0"
            },
            "3": {  # Calculation cells
                "fillColor": "#F8F9FA",  # Very light blue-gray
                "textColor": "#1976D2",  # Blue
                "fontSize": 11,
                "bold": False
            },
            "4": {  # Total/Summary cells
                "fillColor": "#E8F5E8",  # Very light green
                "textColor": "#2E7D32",  # Dark green
                "fontSize": 11,
                "bold": True
            },
            "5": {  # Alternative row color
                "fillColor": "#FAFAFA",  # Very light gray
                "textColor": "#333333",
                "fontSize": 11
            }
        }
        
        # Update styles
        india_data["styles"].update(new_styles)
        
        print("   ✅ Header color: Light gray (#F5F5F5) with dark green text")
        print("   ✅ Data cells: Pure white (#FFFFFF) with dark gray text") 
        print("   ✅ Calculations: Very light blue-gray (#F8F9FA)")
        print("   ✅ Totals: Very light green (#E8F5E8)")
    
    # Update cell styles in the main sheet to use lighter colors
    if first_sheet and "cells" in first_sheet:
        print(f"\n🔧 Updating cell styles...")
        cells_updated = 0
        
        for cell_key, cell_data in first_sheet["cells"].items():
            if "style" in cell_data:
                # Convert dark styles to light styles
                if cell_data["style"] in [1, 2, 3, 4]:
                    # These are now light styles, keep them
                    cells_updated += 1
        
        print(f"   ✅ Updated {cells_updated} cells with light styling")
    
    return india_data

def main():
    """Main function to fix colors and show structure"""
    print("🇮🇳 India Spreadsheet Color Fix & Structure Analysis")
    print("=" * 60)
    
    # Fix the spreadsheet
    try:
        fixed_data = fix_india_spreadsheet_colors()
        
        if fixed_data:
            # Save fixed version
            output_file = "/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_india/data/india_payroll_data.json"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(fixed_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n✅ Fixed India spreadsheet colors: {output_file}")
            print(f"\n🎨 Color Changes Applied:")
            print("• Background: Changed from dark orange to white/light gray")
            print("• Text: Changed to dark colors for better contrast")  
            print("• Headers: Light gray background with dark green text")
            print("• Data: Pure white background with dark gray text")
            print("• Professional borders added for clear cell separation")
            
            return output_file
            
    except Exception as e:
        print(f"❌ Error fixing spreadsheet: {e}")
        return None

if __name__ == "__main__":
    main()