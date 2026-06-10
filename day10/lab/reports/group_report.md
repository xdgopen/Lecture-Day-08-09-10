# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** AI in Action Day 10 lab team  
**Thành viên:**
| Tên | MSSV | Vai trò (Day 10) | Email |
|-----|------|------------------|-------|
| Nguyễn Danh Thành | 2A202600581 | Ingestion / Cleaning / Embed / Monitoring | nguyendanhthanh.dev@gmail.com |

**Ngày nộp:** 2026-06-10  
**Repo:** https://github.com/xdgopen/Lecture-Day-08-09-10  
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Nộp tại:** `reports/group_report.md`  
> **Deadline commit:** xem `SCORING.md` (code/trace sớm; report có thể muộn hơn nếu được phép).  
> Phải có **run_id**, **đường dẫn artifact**, và **bằng chứng before/after** (CSV eval hoặc screenshot).

---

## 1. Pipeline tổng quan (150–200 từ)

> Nguồn raw là gì (CSV mẫu / export thật)? Chuỗi lệnh chạy end-to-end? `run_id` lấy ở đâu trong log?

**Tóm tắt luồng:**

Pipeline đọc `data/raw/policy_export_dirty.csv` gồm 247 records và 39 `doc_id` unique. Baseline bỏ sót nguồn hợp lệ `access_control_sop`, đồng thời để lọt HR stale content “10 ngày phép năm”. Sau khi sửa, luồng là ingest raw CSV, clean/quarantine theo contract, validate bằng expectation suite, publish cleaned snapshot vào Chroma `day10_kb`, ghi manifest/log/quarantine theo `run_id`. Run tốt cuối là `after-fix`, ghi tại `artifacts/logs/run_after-fix.log` và `artifacts/manifests/manifest_after-fix.json`.

**Lệnh chạy một dòng (copy từ README thực tế của nhóm):**

```bash
python etl_pipeline.py run --run-id after-fix && python eval_retrieval.py --out artifacts/eval/after_fix_eval.csv && python grading_run.py --out artifacts/eval/grading_run.jsonl
```

---

## 2. Cleaning & expectation (150–200 từ)

> Baseline đã có nhiều rule (allowlist, ngày ISO, HR stale, refund, dedupe…). Nhóm thêm **≥3 rule mới** + **≥2 expectation mới**. Khai báo expectation nào **halt**.

### 2a. Bảng metric_impact (bắt buộc — chống trivial)

| Rule / Expectation mới (tên ngắn) | Trước (số liệu) | Sau / khi inject (số liệu) | Chứng cứ (log / CSV / commit) |
|-----------------------------------|------------------|-----------------------------|-------------------------------|
| Add `access_control_sop` allowlist + `required_doc_ids_present` | Baseline `access_control_sop` bị tính vào `unknown_doc_id`; quarantine unknown = 117 | Sau fix unknown = 109, required docs missing = `[]` | `artifacts/quarantine/quarantine_after-fix.csv`, `run_after-fix.log` |
| `stale_hr_policy_content` | Baseline halt: `hr_leave_no_stale_10d_annual violations=2` | Sau fix `stale_hr_policy_content=6`, expectation HR OK | `run_baseline-before-fix.log`, `quarantine_after-fix.csv` |
| `invalid_exported_at_format` + `exported_at_iso_datetime` | Baseline không kiểm tra exported_at | Sau fix quarantine `invalid_exported_at_format=6`, expectation OK | `quarantine_after-fix.csv`, `run_after-fix.log` |
| `ambiguous_chunk_text` + `no_ambiguous_chunk_text` | Baseline để marker “Nội dung không rõ ràng” có thể lọt cleaned | Sau fix quarantine `ambiguous_chunk_text=5`, expectation OK | `quarantine_after-fix.csv` |
| `out_of_scope_sla_priority` + SLA enrich expectation | P1 escalation từng fail grading vì chunk P2/fragmented context | Sau fix `sla_p1_no_p2_priority_chunk OK`, `sla_p1_core_chunk_has_escalation OK`, grading 10/10 | `grading_run.jsonl`, `instructor_quick_check.py` |
| `low_signal_helpdesk_onboarding` | Self-eval còn 1 top1 mismatch do FAQ onboarding chen lên câu P1 update | Sau fix self-eval 21/21: `contains_no=0`, `forbidden_yes=0`, `top1_no=0` | `artifacts/eval/after_fix_eval.csv` |
| Inject `--no-refund-fix` | Normal run: refund expectation OK | Inject: `refund_no_stale_14d_window FAIL violations=2`, eval `q_refund_window hits_forbidden=yes` | `run_inject-bad.log`, `after_inject_bad.csv` |

**Rule chính (baseline + mở rộng):**

- Allowlist chỉ publish 5 canonical sources: refund, SLA P1, IT FAQ, HR leave, access control SOP.
- Date normalize hỗ trợ ISO và `DD/MM/YYYY`; thiếu/sai date bị quarantine.
- HR policy trước 2026-01-01 hoặc nội dung bản 2025/10 ngày phép bị quarantine.
- Refund stale “14 ngày làm việc” được sửa thành “7 ngày làm việc”; khi tắt rule thì expectation halt.
- Chunk ambiguous, exported_at non-ISO, duplicate text, P2 SLA out-of-scope và FAQ onboarding low-signal đều bị quarantine.

**Ví dụ 1 lần expectation fail (nếu có) và cách xử lý:**

Ví dụ rõ nhất là run `baseline-before-fix`: expectation `hr_leave_no_stale_10d_annual` fail với `violations=2`, pipeline exit code 2 và không embed. Sau khi thêm rule `stale_hr_policy_content`, run `after-fix` exit 0.

---

## 3. Before / after ảnh hưởng retrieval hoặc agent (200–250 từ)

> Bắt buộc: inject corruption (Sprint 3) — mô tả + dẫn `artifacts/eval/…` hoặc log.

**Kịch bản inject:**

Chạy `python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate`. Lệnh này cố ý bỏ rule sửa refund window, expectation `refund_no_stale_14d_window` fail nhưng vẫn embed để tạo evidence Sprint 3.

**Kết quả định lượng (từ CSV / bảng):**

`after_inject_bad.csv`: 21 câu self-eval có `forbidden_yes=1`, cụ thể `q_refund_window` hit “14 ngày”. Sau rerun chuẩn `after_fix_eval.csv`: 21 rows, `contains_no=0`, `forbidden_yes=0`, `top1_no=0`. Grading chính thức `artifacts/eval/grading_run.jsonl` có 10 rows, `contains_expected=false = 0`, `hits_forbidden=true = 0`, `top1_doc_matches=false = 0`.

---

## 4. Freshness & monitoring (100–150 từ)

> SLA bạn chọn, ý nghĩa PASS/WARN/FAIL trên manifest mẫu.

SLA freshness đặt 24 giờ trong `contracts/data_contract.yaml`/env. Manifest `after-fix` có `latest_exported_at=2026-04-11T00:00:00`, nên vào ngày chạy 2026-06-10 freshness trả `FAIL` với age khoảng 1448 giờ. Ý nghĩa: content quality pass để làm lab, nhưng production phải yêu cầu source owner xuất raw export mới trước khi publish.

---

## 5. Liên hệ Day 09 (50–100 từ)

> Dữ liệu sau embed có phục vụ lại multi-agent Day 09 không? Nếu có, mô tả tích hợp; nếu không, giải thích vì sao tách collection.

Day 09 multi-agent nên dùng collection đã publish sau Day 10 thay vì đọc raw docs trực tiếp. Lợi ích là agent nhận context đã loại stale HR/refund, đủ access control SOP, có `run_id` để audit khi câu trả lời sai. Hiện lab tách collection `day10_kb` để không phá state cũ của Day 08/09.

---

## 6. Rủi ro còn lại & việc chưa làm

- Freshness FAIL do dữ liệu lab có export cũ; cần raw export mới để đạt SLA.
- Self-eval 21 câu và grading chính thức 10/10 pass ở snapshot `after-fix`.
- Chưa có alert tự động ngoài log/manifest.
- Thông tin thành viên đã cập nhật theo báo cáo cá nhân; nếu làm nhóm nhiều người thì bổ sung thêm dòng vào bảng thành viên.

## 7. Peer review 3 câu hỏi

1. Nếu thêm nguồn `data_privacy_guideline`, nhóm đã cập nhật đồng thời allowlist, contract, expectation và grading chưa?
2. Nếu freshness FAIL nhưng grading pass, có được publish production không? Trả lời: không, cần export mới hoặc approval ngoại lệ.
3. Nếu eval có `hits_forbidden=yes`, pipeline nên debug data layer hay prompt trước? Trả lời: data layer trước, theo thứ tự freshness/version, volume/errors, schema/contract, lineage/run_id.
