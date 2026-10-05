#!/usr/bin/env python
"""Read and inspect Stage 2 finalized canonical labels"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

# Read the finalized labels
df = pd.read_excel("data/labels/Stage2_WeakLabels_v4_Model_Challenge.xlsx")

print(f"Total rows: {len(df)}")
print(f"\nColumns: {list(df.columns)}")
print(f"\nData types:\n{df.dtypes}")
print(f"\nFirst 5 rows:\n{df.head()}")

# Check for canonical label columns
canonical_cols = [col for col in df.columns if 'Alert' in col or 'Impact' in col or 'Severity' in col or 'Type' in col]
print(f"\nCanonical label columns: {canonical_cols}")

# Value counts
if 'Alert Type' in df.columns:
    print(f"\nAlert Type distribution:\n{df['Alert Type'].value_counts()}")
if 'Business Impact' in df.columns:
    print(f"\nBusiness Impact distribution:\n{df['Business Impact'].value_counts()}")
if 'Severity' in df.columns:
    print(f"\nSeverity distribution:\n{df['Severity'].value_counts()}")

# Check if there are any ML challenge columns
ml_cols = [col for col in df.columns if 'predicted' in col.lower() or 'ml' in col.lower() or 'model' in col.lower()]
print(f"\nML/predicted columns: {ml_cols}")

# Save summary
print(f"\nSaving CSV version for inspection...")
df.to_csv("data/labels/Stage2_WeakLabels_v4_Model_Challenge.csv", index=False)
print("Saved to: data/labels/Stage2_WeakLabels_v4_Model_Challenge.csv")
