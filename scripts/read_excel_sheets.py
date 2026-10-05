#!/usr/bin/env python
"""Read all sheets from the Excel file"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

excel_file = "data/labels/Stage2_WeakLabels_v4_Model_Challenge.xlsx"

# Read all sheets
xl = pd.ExcelFile(excel_file)
print(f"Sheets in file: {xl.sheet_names}")

for sheet_name in xl.sheet_names:
    df = pd.read_excel(excel_file, sheet_name=sheet_name)
    print(f"\n{'='*60}")
    print(f"Sheet: {sheet_name}")
    print(f"{'='*60}")
    print(f"Shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print(f"\nFirst 3 rows:")
    print(df.head(3))
    
    # If this looks like the main data (has 889 rows or close to it)
    if len(df) > 800:
        print(f"\n✓ This sheet has {len(df)} rows - likely the main alert data!")
        df.to_csv(f"data/labels/sheet_{sheet_name}.csv", index=False)
        print(f"Saved to: data/labels/sheet_{sheet_name}.csv")
