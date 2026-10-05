# Stage 2 Model Evaluation Report

**Date:** 2026-10-03

**Training Data:** Canonical labels from `Stage2_WeakLabels_v4_Model_Challenge.xlsx`

**IMPORTANT:** These labels are analyst-derived weak labels (prototype), NOT independently verified ground truth.

---

## Executive Summary

Trained and evaluated classification models for three tasks:

### Alert Type

- **Classes:** 16
- **Test Samples:** 134
- **Selected Model:** tfidf_lr_alert_type
- **Selection Criterion:** Validation weighted F1 = 0.9554
- **Final Test F1 (weighted):** 0.6036

**Test Metrics (locked model, evaluated once):**

- Accuracy: 0.6194
- Precision (macro): 0.7376
- Recall (macro): 0.7224
- F1 (macro): 0.6707
- F1 (weighted): 0.6036

### Severity

- **Classes:** 4
- **Test Samples:** 134
- **Selected Model:** embedding_svm_severity
- **Selection Criterion:** Validation weighted F1 = 0.8583
- **Final Test F1 (weighted):** 0.8808

**Test Metrics (locked model, evaluated once):**

- Accuracy: 0.8806
- Precision (macro): 0.9199
- Recall (macro): 0.8720
- F1 (macro): 0.8857
- F1 (weighted): 0.8808

### Business Impact

- **Classes:** 3
- **Test Samples:** 134
- **Selected Model:** embedding_svm_business_impact
- **Selection Criterion:** Validation weighted F1 = 0.9771
- **Final Test F1 (weighted):** 0.9391

**Test Metrics (locked model, evaluated once):**

- Accuracy: 0.9403
- Precision (macro): 0.9447
- Recall (macro): 0.9028
- F1 (macro): 0.9217
- F1 (weighted): 0.9391

---

## Model Architectures Evaluated

For each task, we trained and compared:

1. **TF-IDF + Logistic Regression** (primary baseline)
2. **TF-IDF + Linear SVM**
3. **Embedding + Logistic Regression** (Sentence-BERT)
4. **Embedding + Linear SVM** (Sentence-BERT)

**Model Selection:** Based on VALIDATION weighted F1 score.
**Test Evaluation:** Each selected model was evaluated ONCE on the held-out test set.

**CRITICAL:** Test set was NOT used for model selection to avoid overfitting.

---

## Data Split

**Chronological split to prevent data leakage:**

- Train: 70% (earliest alerts)
- Validation: 15%
- Test: 15% (most recent alerts)

**Forbidden Features (excluded to prevent target leakage):**

- Historical Priority (when predicting Severity/Business Impact)
- Historical Assignment Group
- Post-resolution fields (Resolved, Resolution code, etc.)
- Post-triage metrics (Reassignment count, Reopen count)

---

## Detailed Results

### Alert Type

**Number of Classes:** 16

**Model Comparison (Validation F1 used for selection):**

| Model | Val F1 (weighted) | Test Accuracy | Test F1 (weighted) | Selected? |
|-------|-------------------|---------------|--------------------|--------|
| tfidf_lr_alert_type | 0.9554 | 0.6194 | 0.6036 | ✅ YES |
| tfidf_svm_alert_type | 0.9381 | 0.6194 | 0.5697 | No |
| embedding_lr_alert_type | 0.9309 | 0.6194 | 0.5979 | No |
| embedding_svm_alert_type | 0.9223 | 0.6194 | 0.5641 | No |

**Selected Model:** tfidf_lr_alert_type

**Selection Criterion:** Highest validation weighted F1 (0.9554)

**IMPORTANT:** Model selected using validation set BEFORE test evaluation.

**Per-Class Metrics (Top 10 by Support):**

| Class | Precision | Recall | F1 | Support |
|-------|-----------|--------|----|---------|
| Batch Job Failure | 1.0000 | 0.0811 | 0.1500 | 37 |
| Data Hub Batch Workflow Failure | 0.5217 | 1.0000 | 0.6857 | 12 |
| File Transfer / SFTP Workflow | 0.0000 | 0.0000 | 0.0000 | 11 |
| Disk Space | 1.0000 | 1.0000 | 1.0000 | 10 |
| Monitoring Agent Offline | 1.0000 | 1.0000 | 1.0000 | 10 |
| API Error Rate | 1.0000 | 1.0000 | 1.0000 | 9 |
| Service / Process Not Running | 0.8182 | 1.0000 | 0.9000 | 9 |
| Synthetic Monitoring (ThousandEyes) | 1.0000 | 1.0000 | 1.0000 | 7 |
| Memory Utilization | 1.0000 | 1.0000 | 1.0000 | 6 |
| Server Unreachable / Uptime | 1.0000 | 1.0000 | 1.0000 | 6 |

... and 6 more classes

**Classes with Poor Performance (F1 < 0.3):**

- File Transfer / SFTP Workflow: F1=0.0000, Support=11
- Server Reboot: F1=0.0000, Support=2
- Batch Job Failure: F1=0.1500, Support=37

### Severity

**Number of Classes:** 4

**Model Comparison (Validation F1 used for selection):**

| Model | Val F1 (weighted) | Test Accuracy | Test F1 (weighted) | Selected? |
|-------|-------------------|---------------|--------------------|--------|
| tfidf_lr_severity | 0.7820 | 0.8582 | 0.8592 | No |
| tfidf_svm_severity | 0.8350 | 0.8731 | 0.8712 | No |
| embedding_lr_severity | 0.8258 | 0.8657 | 0.8659 | No |
| embedding_svm_severity | 0.8583 | 0.8806 | 0.8808 | ✅ YES |

**Selected Model:** embedding_svm_severity

**Selection Criterion:** Highest validation weighted F1 (0.8583)

**IMPORTANT:** Model selected using validation set BEFORE test evaluation.

**Per-Class Metrics (Top 10 by Support):**

| Class | Precision | Recall | F1 | Support |
|-------|-----------|--------|----|---------|
| Sev1 - Critical | 0.9403 | 0.9265 | 0.9333 | 68 |
| Sev2 - High | 0.7391 | 0.8947 | 0.8095 | 38 |
| Sev3 - Medium | 1.0000 | 0.6667 | 0.8000 | 21 |
| Sev4 - Low | 1.0000 | 1.0000 | 1.0000 | 7 |

### Business Impact

**Number of Classes:** 3

**Model Comparison (Validation F1 used for selection):**

| Model | Val F1 (weighted) | Test Accuracy | Test F1 (weighted) | Selected? |
|-------|-------------------|---------------|--------------------|--------|
| tfidf_lr_business_impact | 0.9619 | 0.8955 | 0.8894 | No |
| tfidf_svm_business_impact | 0.9619 | 0.8955 | 0.8894 | No |
| embedding_lr_business_impact | 0.9541 | 0.9403 | 0.9391 | No |
| embedding_svm_business_impact | 0.9771 | 0.9403 | 0.9391 | ✅ YES |

**Selected Model:** embedding_svm_business_impact

**Selection Criterion:** Highest validation weighted F1 (0.9771)

**IMPORTANT:** Model selected using validation set BEFORE test evaluation.

**Per-Class Metrics (Top 10 by Support):**

| Class | Precision | Recall | F1 | Support |
|-------|-----------|--------|----|---------|
| High | 0.9412 | 1.0000 | 0.9697 | 80 |
| Medium | 0.8929 | 0.8333 | 0.8621 | 30 |
| Low | 1.0000 | 0.8750 | 0.9333 | 24 |

---

## Limitations

### Data Quality

- **Weak Labels:** Canonical labels are analyst-derived rules, not verified ground truth
- **No Independent Validation:** Labels have not been validated by independent reviewers
- **Prototype Status:** These labels are for model challenge/comparison purposes

### Model Limitations

- **Class Imbalance:** Some alert types/severities are rare, affecting model performance
- **Text-Only:** Models use only normalized description (no metadata features)
- **Generalization:** Performance on production data may differ from test set

### Evaluation Limitations

- **No Production Validation:** Models not tested on live production data
- **Time-Based Drift:** Alert patterns may change over time
- **Client-Specific Patterns:** Performance may vary by client

---

## Model Selection Rationale

Models were selected based on **VALIDATION weighted F1 score**, NOT test performance.

**Why This Methodology?**

1. **Prevents Overfitting:** Test set never used for model selection
2. **Proper Evaluation:** Test metrics represent true generalization performance
3. **Honest Reporting:** Test F1 is unbiased estimate of future performance

**Why Weighted F1 for Selection?**

- Balances precision and recall
- Weights classes by support (handles imbalance)
- More robust than accuracy for imbalanced datasets

**Selection Summary:**

- **Alert Type:** tfidf_lr_alert_type
  - Selection: Val F1=0.9554
  - Final Test: F1=0.6036
- **Severity:** embedding_svm_severity
  - Selection: Val F1=0.8583
  - Final Test: F1=0.8808
- **Business Impact:** embedding_svm_business_impact
  - Selection: Val F1=0.9771
  - Final Test: F1=0.9391

---

## Files Generated

- `training_results.json` - Complete metrics for all models
- `alert_type_predictions.csv` - 889 predictions with confidence scores
- `severity_predictions.csv` - 889 predictions with confidence scores
- `business_impact_predictions.csv` - 889 predictions with confidence scores
- `models/alert_type/` - Trained model artifacts
- `models/severity/` - Trained model artifacts
- `models/business_impact/` - Trained model artifacts
- `STAGE2_MODEL_EVALUATION_REPORT.md` - This report

---

**Report Generated:** 2026-10-03 21:10:07
