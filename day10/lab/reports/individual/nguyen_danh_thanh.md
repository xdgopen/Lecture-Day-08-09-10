# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Danh Thành  
**MSSV:** 2A202600581  
**Email:** nguyendanhthanh.dev@gmail.com  
**Vai trò:** Ingestion / Cleaning / Embed / Monitoring  
**Ngày nộp:** 2026-06-10

---

## 1. Tôi phụ trách phần nào?

Tôi phụ trách hoàn thiện luồng end-to-end từ phân tích raw CSV đến cleaned snapshot, expectation suite, embed Chroma, eval/grading và report. Các file chính tôi làm là `transform/cleaning_rules.py`, `quality/expectations.py`, `contracts/data_contract.yaml`, `docs/*.md`, `reports/group_report.md`, và artifact trong `artifacts/`. Run tốt cuối cùng là `after-fix`, có log tại `artifacts/logs/run_after-fix.log` và manifest tại `artifacts/manifests/manifest_after-fix.json`. Kết nối giữa các phần là mọi rule cleaning mới đều có expectation hoặc metric tương ứng trong report nhóm.

## 2. Một quyết định kỹ thuật

Tôi chọn để các lỗi có thể làm sai câu trả lời người dùng ở severity `halt`: stale refund 14 ngày, stale HR 10 ngày phép, thiếu doc_id bắt buộc, exported_at không ISO, chunk ambiguous, và SLA P2 gây nhiễu corpus P1. Các lỗi này không nên chỉ warn vì Chroma sẽ upsert snapshot ngay sau validate; nếu để lọt, agent Day 09 có thể đọc context sai nhưng vẫn trả lời tự tin. Pipeline vẫn hỗ trợ `--skip-validate` cho Sprint 3, nhưng chỉ dùng để inject corruption có kiểm soát và tạo evidence before/after.

## 3. Một lỗi hoặc anomaly đã xử lý

Anomaly lớn nhất là `access_control_sop` có 8 rows trong raw nhưng không nằm trong `ALLOWED_DOC_IDS`, làm nguồn hợp lệ bị quarantine nhầm và câu grading Level 4 Admin Access không thể trả lời. Tôi thêm `access_control_sop` vào allowlist/contract và thêm expectation `required_doc_ids_present`. Đồng thời baseline còn halt ở `hr_leave_no_stale_10d_annual violations=2`; tôi thêm rule `stale_hr_policy_content` để quarantine bản HR 2025/10 ngày dù effective_date mới. Sau fix, `unknown_doc_id` giảm từ 117 xuống 109, cleaned còn 33 rows, quarantine là 214 rows, self-eval 21/21 và grading chính thức 10/10 pass.

## 4. Bằng chứng trước / sau

Run `inject-bad` cố ý tắt refund fix:

```text
expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=2
after_inject_bad.csv: q_refund_window ... contains_expected=yes hits_forbidden=yes
```

Run `after-fix` phục hồi snapshot tốt:

```text
expectation[refund_no_stale_14d_window] OK (halt) :: violations=0
grading_run.jsonl: contains_false=0, forbidden_true=0, top1_false=0
```

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ, tôi sẽ thêm một script `make_report_summary.py` đọc log/eval/manifest và tự sinh bảng metric impact. Như vậy report ít phụ thuộc thao tác copy số liệu thủ công và dễ tái chạy khi đổi raw export.
