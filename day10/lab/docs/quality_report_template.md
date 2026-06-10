# Quality report — Lab Day 10 (nhóm)

**run_id:** `baseline-before-fix`, `inject-bad`, `after-fix`  
**Ngày:** 2026-06-10

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước | Sau | Ghi chú |
|--------|-------|-----|---------|
| raw_records | 247 | 247 | Cùng file `data/raw/policy_export_dirty.csv` |
| cleaned_records | 40 (`baseline-before-fix`) | 33 (`after-fix`) | Sau fix loại HR stale content, ambiguous, invalid exported_at, P2 scope, FAQ low-signal |
| quarantine_records | 207 | 214 | Access control không còn bị unknown; rules mới tăng quarantine có chủ đích |
| Expectation halt? | Có, `hr_leave_no_stale_10d_annual` fail | Không halt | Inject-bad cố ý fail refund nhưng dùng `--skip-validate` |

---

## 2. Before / after retrieval (bắt buộc)

> Đính kèm hoặc dẫn link tới `artifacts/eval/before_after_eval.csv` (hoặc 2 file before/after).

**Câu hỏi then chốt:** refund window (`q_refund_window`)  
**Trước:** `artifacts/eval/after_inject_bad.csv`: `q_refund_window top1_doc_id=policy_refund_v4 contains_expected=yes hits_forbidden=yes top1_doc_expected=yes`.

**Sau:** `artifacts/eval/after_fix_eval.csv`: `q_refund_window` không còn `hits_forbidden=yes`; grading chính thức `gq_d10_01` pass.

**Merit (khuyến nghị):** versioning HR — `q_leave_version` (`contains_expected`, `hits_forbidden`, cột `top1_doc_expected`)

**Trước:** baseline log `artifacts/logs/run_baseline-before-fix.log` halt do `hr_leave_no_stale_10d_annual violations=2`.

**Sau:** `artifacts/logs/run_after-fix.log` có `hr_leave_no_stale_10d_annual OK`, grading `gq_d10_09` pass với 12 ngày và không hit forbidden 10 ngày.

---

## 3. Freshness & monitor

`python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_after-fix.json` trả `FAIL` vì `latest_exported_at=2026-04-11T00:00:00`, `age_hours` khoảng 1448, vượt `sla_hours=24`. Đây là cảnh báo dữ liệu demo đã cũ so với ngày chạy 2026-06-10; pipeline vẫn pass quality content, nhưng production cần export mới trước khi publish.

---

## 4. Corruption inject (Sprint 3)

Chạy:

```bash
python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate
python eval_retrieval.py --out artifacts/eval/after_inject_bad.csv
```

Corruption là bỏ rule sửa refund 14 ngày thành 7 ngày. Expectation phát hiện `refund_no_stale_14d_window FAIL violations=2`; vì có `--skip-validate`, pipeline vẫn embed để tạo evidence. Eval inject có `hits_forbidden=yes` ở `q_refund_window`. Sau khi rerun chuẩn `after-fix`, grading 10/10 pass.

---

## 5. Hạn chế & việc chưa làm

- Eval tự kiểm 21 câu và bộ grading chính thức 10 câu đã pass toàn bộ ở snapshot `after-fix`.
- Freshness đang FAIL vì raw export là dữ liệu lab cũ; cần source export mới để đạt SLA thật.
- Chưa thêm dashboard/alert tự động ngoài log và manifest.
