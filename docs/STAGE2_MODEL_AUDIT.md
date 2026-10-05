# STAGE 2 MODEL AUDIT REPORT

**Date**: September 25, 2026

**Status**: AUDIT COMPLETE

---

## 1. DATA SPLIT ANALYSIS

### Chronological Split Verification

#### Priority

**Training Set**:
- Count: 622
- Date Range: 2026-01-01 03:08:47 to 2026-05-11 21:17:19
- Label Distribution:
  - 2 - High: 52
  - 3 - Medium: 507
  - 4 - Low: 63

**Validation Set**:
- Count: 133
- Date Range: 2026-05-11 22:33:35 to 2026-06-18 12:03:37
- Label Distribution:
  - 2 - High: 18
  - 3 - Medium: 73
  - 4 - Low: 42

**Test Set**:
- Count: 134
- Date Range: 2026-06-18 22:13:39 to 2026-08-07 03:10:38
- Label Distribution:
  - 2 - High: 53
  - 3 - Medium: 65
  - 4 - Low: 16

#### Assignment group

**Training Set**:
- Count: 622
- Date Range: 2026-01-01 03:08:47 to 2026-05-11 21:17:19
- Label Distribution:
  - Client Support Subscription Services - Bridgestone: 156
  - Client Support Subscription Services - EA Sports: 80
  - Client Support Subscription Services - Pizza Hut Brands: 166
  - Product Support - Agility Loyalty: 220

**Validation Set**:
- Count: 133
- Date Range: 2026-05-11 22:33:35 to 2026-06-18 12:03:37
- Label Distribution:
  - Client Support Subscription Services - Bridgestone: 26
  - Client Support Subscription Services - EA Sports: 21
  - Client Support Subscription Services - Pizza Hut Brands: 45
  - Product Support - Agility Loyalty: 41

**Test Set**:
- Count: 134
- Date Range: 2026-06-18 22:13:39 to 2026-08-07 03:10:38
- Label Distribution:
  - Client Support Subscription Services - Bridgestone: 29
  - Client Support Subscription Services - EA Sports: 47
  - Client Support Subscription Services - Pizza Hut Brands: 18
  - Product Support - Agility Loyalty: 40

## 2. FEATURE LEAKAGE AUDIT

**✓ NO LEAKAGE DETECTED**: All forbidden fields properly filtered

Forbidden fields checked:
- Priority
- Assignment group
- Assigned to
- Resolved
- Resolved by
- Resolution code
- Resolve time
- Business duration
- Assigned to count
- Reassignment count
- Reopen count
- Approval
- Approval history
- Approval set

## 3. PRIORITY CLASSIFICATION

### Baseline Comparison

- Majority Class: 3 - Medium
- Majority Count: 65 / 134
- **Baseline Accuracy: 0.4851**

### Model Benchmark Results

| Model | Accuracy | Precision (Macro) | Recall (Macro) | F1 (Macro) | F1 (Weighted) | Avg Confidence | Brier Score | Improvement over Baseline |
|-------|----------|-------------------|----------------|------------|---------------|----------------|-------------|---------------------------|
| tfidf_lr | 0.5373 | 0.5039 | 0.4792 | 0.4286 | 0.4011 | 0.8369 | 0.2499 | +0.0522 |
| tfidf_svm | 0.4851 | 0.1617 | 0.3333 | 0.2178 | 0.3169 | 0.8414 | 0.2660 | +0.0000 |
| embedding_lr | 0.5299 | 0.5026 | 0.4583 | 0.4063 | 0.3919 | 0.8196 | 0.2427 | +0.0448 |
| embedding_svm | 0.4851 | 0.1617 | 0.3333 | 0.2178 | 0.3169 | 0.8181 | 0.2578 | +0.0000 |

### Per-Class Performance

#### tfidf_lr

| Class | Precision | Recall | F1 Score | Support |
|-------|-----------|--------|----------|----------|
| 2 - High | 0.0000 | 0.0000 | 0.0000 | 53 |
| 3 - Medium | 0.5118 | 1.0000 | 0.6771 | 65 |
| 4 - Low | 1.0000 | 0.4375 | 0.6087 | 16 |

**Confusion Matrix**: See `confusion_matrix_priority_tfidf_lr.png`
**Calibration Plot**: See `calibration_priority_tfidf_lr.png`

#### tfidf_svm

| Class | Precision | Recall | F1 Score | Support |
|-------|-----------|--------|----------|----------|
| 2 - High | 0.0000 | 0.0000 | 0.0000 | 53 |
| 3 - Medium | 0.4851 | 1.0000 | 0.6533 | 65 |
| 4 - Low | 0.0000 | 0.0000 | 0.0000 | 16 |

**Confusion Matrix**: See `confusion_matrix_priority_tfidf_svm.png`
**Calibration Plot**: See `calibration_priority_tfidf_svm.png`

#### embedding_lr

| Class | Precision | Recall | F1 Score | Support |
|-------|-----------|--------|----------|----------|
| 2 - High | 0.0000 | 0.0000 | 0.0000 | 53 |
| 3 - Medium | 0.5078 | 1.0000 | 0.6736 | 65 |
| 4 - Low | 1.0000 | 0.3750 | 0.5455 | 16 |

**Confusion Matrix**: See `confusion_matrix_priority_embedding_lr.png`
**Calibration Plot**: See `calibration_priority_embedding_lr.png`

#### embedding_svm

| Class | Precision | Recall | F1 Score | Support |
|-------|-----------|--------|----------|----------|
| 2 - High | 0.0000 | 0.0000 | 0.0000 | 53 |
| 3 - Medium | 0.4851 | 1.0000 | 0.6533 | 65 |
| 4 - Low | 0.0000 | 0.0000 | 0.0000 | 16 |

**Confusion Matrix**: See `confusion_matrix_priority_embedding_svm.png`
**Calibration Plot**: See `calibration_priority_embedding_svm.png`

## 4. ASSIGNMENT GROUP CLASSIFICATION

### Baseline Comparison

- Majority Class: Client Support Subscription Services - EA Sports
- Majority Count: 47 / 134
- **Baseline Accuracy: 0.3507**

### Model Benchmark Results

| Model | Accuracy | Precision (Macro) | Recall (Macro) | F1 (Macro) | F1 (Weighted) | Avg Confidence | Brier Score | Improvement over Baseline |
|-------|----------|-------------------|----------------|------------|---------------|----------------|-------------|---------------------------|
| tfidf_lr | 0.8060 | 0.8241 | 0.7505 | 0.7674 | 0.8057 | 0.7976 | 0.0630 | +0.4552 |

### Per-Class Performance

#### tfidf_lr

| Class | Precision | Recall | F1 Score | Support |
|-------|-----------|--------|----------|----------|
| Client Support Subscription Services - Bridgestone | 1.0000 | 0.8621 | 0.9259 | 29 |
| Client Support Subscription Services - EA Sports | 0.9756 | 0.8511 | 0.9091 | 47 |
| Client Support Subscription Services - Pizza Hut Brands | 0.7000 | 0.3889 | 0.5000 | 18 |
| Product Support - Agility Loyalty | 0.6207 | 0.9000 | 0.7347 | 40 |

**Confusion Matrix**: See `confusion_matrix_routing_tfidf_lr.png`
**Calibration Plot**: See `calibration_routing_tfidf_lr.png`

## 5. KEY FINDINGS

### Priority Classification Issues

1. **Baseline Performance**: 0.4851
2. **Best Model**: tfidf_lr with accuracy 0.5373
3. **Improvement over Baseline**: +0.0522
4. **Confidence vs Accuracy Mismatch**: Average confidence 0.8369 despite accuracy 0.5373
5. **Calibration Quality**: Brier score 0.2499 (lower is better)

### Assignment Group Classification Performance

1. **Baseline Performance**: 0.3507
2. **Best Model**: tfidf_lr with accuracy 0.8060
3. **Improvement over Baseline**: +0.4552
4. **Strong Performance**: Significant improvement over baseline

## 6. RECOMMENDATIONS

### Immediate Actions

1. **Priority Model**:
   - Do NOT use high confidence threshold (0.70+) for routing - confidence is poorly calibrated
   - Consider collecting labels for Alert Type, Severity, and Business Impact
   - These features may improve Priority prediction
   - Address class imbalance (3-Medium dominates)

2. **Assignment Group Model**:
   - Model performs well and is ready for production evaluation
   - Calibration is reasonable
   - Monitor performance on Pizza Hut (lower recall)

3. **Claude Fallback**:
   - Do not implement confidence-based fallback yet
   - Confidence scores do not reliably indicate accuracy
   - Need better calibration before using thresholds

### Before Stage 3

1. Verify no feature leakage in production pipeline
2. Document that Alert Type, Severity, Business Impact require labeling
3. Consider retraining Priority with additional features once labeled

---

**Audit Status**: COMPLETE

**Next Steps**: Await approval before proceeding to Stage 3
