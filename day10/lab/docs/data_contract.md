# Data contract — Lab Day 10

> Bắt đầu từ `contracts/data_contract.yaml` — mở rộng và đồng bộ file này.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|-------------------|-------------------|----------------|
| `policy_refund_v4` | CSV export từ policy system, canonical `data/docs/policy_refund_v4.txt` | Chunk stale ghi 14 ngày làm việc thay vì 7 ngày; duplicate chunk | `refund_no_stale_14d_window`, `hits_forbidden` trong eval |
| `sla_p1_2026` | CSV export từ ITSM/SLA KB, canonical `data/docs/sla_p1_2026.txt` | Chunk P2 gây nhiễu top-k P1; thiếu fact escalation trong chunk chính | `sla_p1_no_p2_priority_chunk`, `sla_p1_core_chunk_has_escalation` |
| `it_helpdesk_faq` | CSV export từ FAQ nội bộ, canonical `data/docs/it_helpdesk_faq.txt` | Dòng rỗng, duplicate, doc_id giả mạo | `missing_chunk_text`, `duplicate_chunk_text`, `unknown_doc_id` |
| `hr_leave_policy` | CSV export từ HR KB, canonical `data/docs/hr_leave_policy.txt` | Bản HR 2025 còn 10 ngày phép; effective_date cũ hoặc thiếu | `hr_leave_no_stale_10d_annual`, `stale_hr_policy_effective_date` |
| `access_control_sop` | CSV export từ IT Security SOP, canonical `data/docs/access_control_sop.txt` | Nguồn hợp lệ bị allowlist cũ quarantine nhầm | `required_doc_ids_present`, số rows `unknown_doc_id` giảm |

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| chunk_id | string | Có | … |
| doc_id | string | Có | Phải thuộc allowlist trong `transform/cleaning_rules.py` và `contracts/data_contract.yaml` |
| chunk_text | string | Có | Không rỗng, không marker "Nội dung không rõ ràng", không chứa policy stale |
| effective_date | date | Có | Chuẩn `YYYY-MM-DD`; hỗ trợ normalize `DD/MM/YYYY` |
| exported_at | datetime | Có | ISO datetime, ví dụ `2026-04-11T00:00:00` |

---

## 3. Quy tắc quarantine vs drop

Record lỗi được ghi vào `artifacts/quarantine/quarantine_<run_id>.csv` kèm `reason`. Các lỗi contract/halt không được embed trừ khi chạy demo có chủ đích với `--skip-validate`. Owner tương ứng kiểm tra reason, sửa source hoặc cleaning rule, sau đó rerun pipeline. Không merge tay từ quarantine vào cleaned CSV.

---

## 4. Phiên bản & canonical

Source of truth:

- Refund: `data/docs/policy_refund_v4.txt`, window hiện hành 7 ngày làm việc.
- SLA P1: `data/docs/sla_p1_2026.txt`, first response 15 phút, resolution 4 giờ, escalation 10 phút.
- HR leave: `data/docs/hr_leave_policy.txt`, effective từ 2026-01-01, dưới 3 năm là 12 ngày phép năm.
- Access control: `data/docs/access_control_sop.txt`, Level 4 phê duyệt bởi IT Manager + CISO.
