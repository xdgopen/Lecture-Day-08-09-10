# Runbook — Lab Day 10 (incident tối giản)

---

## Symptom

User/agent trả lời chính sách hoàn tiền là “14 ngày” thay vì “7 ngày”, hoặc câu hỏi P1 escalation không trả được “10 phút”. Một dấu hiệu khác là grading/eval có `hits_forbidden=yes` hoặc `contains_expected=false`.

---

## Detection

- Pipeline log: `expectation[refund_no_stale_14d_window] FAIL (halt)` hoặc expectation khác fail.
- Eval: `artifacts/eval/after_inject_bad.csv` có `q_refund_window hits_forbidden=yes`.
- Grading: `artifacts/eval/grading_run.jsonl` phải có `contains_expected=true`, `hits_forbidden=false`, `top1_doc_matches=true` cho 10 câu.
- Freshness: `python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_after-fix.json` hiện trả `FAIL` vì latest export `2026-04-11T00:00:00` quá SLA 24h vào ngày 2026-06-10.

---

## Diagnosis

| Bước | Việc làm | Kết quả mong đợi |
|------|----------|------------------|
| 1 | Kiểm tra `artifacts/manifests/manifest_<run_id>.json` | Có `run_id`, `raw_records`, `cleaned_records`, `quarantine_records`, `latest_exported_at` |
| 2 | Mở `artifacts/logs/run_<run_id>.log` | Xác định expectation nào fail/halt |
| 3 | Mở `artifacts/quarantine/quarantine_<run_id>.csv` | Reason tăng đúng loại, ví dụ `stale_hr_policy_content`, `unknown_doc_id`, `ambiguous_chunk_text` |
| 4 | Chạy `python eval_retrieval.py --out artifacts/eval/debug_eval.csv` | Dòng nghi vấn lộ `contains_expected` hoặc `hits_forbidden` |
| 5 | Chạy `python grading_run.py --out artifacts/eval/grading_run.jsonl` | 10 câu chính thức đều pass |

---

## Mitigation

Rerun pipeline chuẩn:

```bash
python etl_pipeline.py run --run-id after-fix
python eval_retrieval.py --out artifacts/eval/after_fix_eval.csv
python grading_run.py --out artifacts/eval/grading_run.jsonl
```

Pipeline dùng snapshot publish: upsert theo `chunk_id` và prune ids không còn trong cleaned run. Nếu data freshness `FAIL`, vẫn có thể phục vụ demo lab nhưng phải ghi cảnh báo “data stale” và yêu cầu source owner xuất bản lại raw export mới.

---

## Prevention

- Giữ `required_doc_ids_present` để không bỏ sót nguồn hợp lệ như `access_control_sop`.
- Giữ expectation stale refund/HR/SLA để lỗi dữ liệu phổ biến halt trước khi embed.
- Monitor manifest theo SLA 24h; alert khi `freshness_check=FAIL`.
- Khi thêm policy mới, cập nhật contract + allowlist + grading/eval trước khi publish.
