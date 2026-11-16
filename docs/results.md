# Saved results

Values come from reports/summary.json and reports/scoring.json.

| Measure | Saved value |
| --- | --- |
| Equipment items | 300 |
| Document register rows | 3008 |
| Findings requiring review | 200 |
| Logged safe changes | 16 |
| Required type coverage | 772 / 780 (98.9744%) |
| Overall synthetic precision | 100.00% |
| Overall synthetic recall | 100.00% |
| Measured runtime, seconds | 0.062144 |
| Passing local pytest cases | 160 |

Per-rule results:

| Rule | Expected | Detected | Precision | Recall |
| --- | --- | --- | --- | --- |
| `ambiguous_equipment` | 0 | 0 | N/A | N/A |
| `duplicate_doc_id` | 8 | 8 | 100.00% | 100.00% |
| `duplicate_file` | 8 | 8 | 100.00% | 100.00% |
| `exact_duplicate` | 8 | 8 | 100.00% | 100.00% |
| `filename_mismatch` | 16 | 16 | 100.00% | 100.00% |
| `future_date` | 8 | 8 | 100.00% | 100.00% |
| `invalid_date` | 8 | 8 | 100.00% | 100.00% |
| `invalid_doc_type` | 8 | 8 | 100.00% | 100.00% |
| `invalid_page_count` | 8 | 8 | 100.00% | 100.00% |
| `invalid_revision` | 8 | 8 | 100.00% | 100.00% |
| `invalid_status` | 8 | 8 | 100.00% | 100.00% |
| `missing_doc_id` | 0 | 0 | N/A | N/A |
| `missing_doc_type` | 0 | 0 | N/A | N/A |
| `missing_file_name` | 0 | 0 | N/A | N/A |
| `missing_issue_date` | 0 | 0 | N/A | N/A |
| `missing_page_count` | 0 | 0 | N/A | N/A |
| `missing_required` | 8 | 8 | 100.00% | 100.00% |
| `missing_revision` | 8 | 8 | 100.00% | 100.00% |
| `missing_status` | 0 | 0 | N/A | N/A |
| `missing_title` | 8 | 8 | 100.00% | 100.00% |
| `multiple_issued` | 8 | 8 | 100.00% | 100.00% |
| `near_duplicate_title` | 16 | 16 | 100.00% | 100.00% |
| `safe_normalization` | 16 | 16 | 100.00% | 100.00% |
| `superseded_without_replacement` | 40 | 40 | 100.00% | 100.00% |
| `tree_cycle` | 0 | 0 | N/A | N/A |
| `tree_duplicate_code` | 0 | 0 | N/A | N/A |
| `tree_invalid_parent` | 0 | 0 | N/A | N/A |
| `tree_level` | 0 | 0 | N/A | N/A |
| `tree_missing_code` | 0 | 0 | N/A | N/A |
| `tree_missing_name` | 0 | 0 | N/A | N/A |
| `unknown_equipment` | 8 | 8 | 100.00% | 100.00% |
| `unknown_equipment_class` | 0 | 0 | N/A | N/A |
| `unmapped_document` | 8 | 8 | 100.00% | 100.00% |
| `wrong_mapping_level` | 8 | 8 | 100.00% | 100.00% |

N/A means no denominator. Scores describe controlled synthetic faults only.
