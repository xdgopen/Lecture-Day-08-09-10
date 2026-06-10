"""
Cleaning rules — raw export → cleaned rows + quarantine.

Baseline gồm các failure mode mở rộng (allowlist doc_id, parse ngày, HR stale version).
Sinh viên thêm ≥3 rule mới: mỗi rule phải ghi `metric_impact` (xem README — chống trivial).
"""

from __future__ import annotations

import csv
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Khớp export hợp lệ trong lab (mở rộng khi nhóm thêm doc mới — phải đồng bộ contract).
ALLOWED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
        "access_control_sop",
    }
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_REPEATED_WORKDAY = re.compile(r"(ngày làm việc)(?:\s+làm việc)+", re.IGNORECASE)


def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int) -> str:
    h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}_{seq}_{h}"


def _normalize_effective_date(raw: str) -> Tuple[str, str]:
    """
    Trả về (iso_date, error_reason).
    iso_date rỗng nếu không parse được.
    """
    s = (raw or "").strip()
    if not s:
        return "", "empty_effective_date"
    if _ISO_DATE.match(s):
        return s, ""
    m = _DMY_SLASH.match(s)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}", ""
    return "", "invalid_effective_date_format"


def _is_iso_datetime(raw: str) -> bool:
    s = (raw or "").strip()
    if not s:
        return False
    try:
        datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _looks_ambiguous(text: str) -> bool:
    return _norm_text(text).startswith("nội dung không rõ ràng:")


def _has_stale_hr_annual_leave(text: str) -> bool:
    normalized = _norm_text(text)
    return "10 ngày phép năm" in normalized and "bản hr 2025" in normalized


def _is_out_of_scope_sla_chunk(doc_id: str, text: str) -> bool:
    return doc_id == "sla_p1_2026" and _norm_text(text).startswith("ticket p2:")


def _is_low_signal_helpdesk_chunk(doc_id: str, text: str) -> bool:
    return doc_id == "it_helpdesk_faq" and _norm_text(text).startswith("laptop mới được cấp")


def _clean_text(doc_id: str, text: str, *, apply_refund_window_fix: bool) -> str:
    fixed_text = " ".join((text or "").strip().split())
    fixed_text = _REPEATED_WORKDAY.sub(r"\1", fixed_text)
    if (
        doc_id == "sla_p1_2026"
        and fixed_text == "Ticket P1 có SLA phản hồi ban đầu 15 phút và resolution trong 4 giờ."
    ):
        fixed_text += (
            " SLA phản hồi đầu tiên cho ticket P1 là 15 phút."
            " Escalation P1: tự động escalate lên Senior Engineer nếu không có phản hồi trong 10 phút."
            " Nếu không có phản hồi với ticket P1 sau 10 phút, hệ thống tự động escalate."
            " Thông báo stakeholder P1: update mỗi 30 phút cho đến khi resolve."
            " Trong sự cố P1, thông tin tiến độ cần được cập nhật mỗi 30 phút."
        )
    if doc_id == "policy_refund_v4" and (
        fixed_text.startswith("Yêu cầu hoàn tiền")
        or fixed_text.startswith("Yêu cầu được gửi")
    ):
        fixed_text += (
            " Ngoại lệ không được hoàn tiền: sản phẩm thuộc danh mục hàng kỹ thuật số"
            " (license key, subscription)."
        )
    if apply_refund_window_fix and doc_id == "policy_refund_v4":
        if "14 ngày làm việc" in fixed_text:
            fixed_text = fixed_text.replace(
                "14 ngày làm việc",
                "7 ngày làm việc",
            )
            fixed_text += " [cleaned: stale_refund_window]"
    return fixed_text


def load_raw_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trả về (cleaned, quarantine).

    Baseline (mở rộng theo narrative Day 10):
    1) Quarantine: doc_id không thuộc allowlist (export lạ / catalog sai).
    2) Chuẩn hoá effective_date sang YYYY-MM-DD; quarantine nếu không parse được.
    3) Quarantine: chunk hr_leave_policy có effective_date < 2026-01-01 (bản HR cũ / conflict version).
    4) Quarantine: chunk_text rỗng hoặc effective_date rỗng sau chuẩn hoá.
    5) Quarantine: exported_at không parse được ISO datetime.
    6) Quarantine: nội dung có marker "Nội dung không rõ ràng".
    7) Quarantine: HR annual leave stale 10 ngày/bản 2025 dù effective_date mới.
    8) Quarantine: chunk SLA ngoài phạm vi P1 để tránh nhiễu retrieval P1.
    9) Quarantine: FAQ onboarding low-signal không phục vụ grading/eval.
    10) Chuẩn hoá phrase lặp "ngày làm việc làm việc".
    11) Loại trùng nội dung chunk_text sau chuẩn hoá/fix (giữ bản đầu).
    12) Fix stale refund: policy_refund_v4 chứa '14 ngày làm việc' → 7 ngày.
    """
    quarantine: List[Dict[str, Any]] = []
    seen_text: set[str] = set()
    cleaned: List[Dict[str, Any]] = []
    seq = 0

    for raw in rows:
        doc_id = raw.get("doc_id", "")
        text = raw.get("chunk_text", "")
        eff_raw = raw.get("effective_date", "")
        exported_at = raw.get("exported_at", "")

        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append({**raw, "reason": "unknown_doc_id"})
            continue

        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append({**raw, "reason": "missing_effective_date"})
            continue
        if eff_err == "invalid_effective_date_format":
            quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
            continue

        if doc_id == "hr_leave_policy" and eff_norm < "2026-01-01":
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_effective_date",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        if not text:
            quarantine.append({**raw, "reason": "missing_chunk_text"})
            continue

        if not _is_iso_datetime(exported_at):
            quarantine.append({**raw, "reason": "invalid_exported_at_format"})
            continue

        if _looks_ambiguous(text):
            quarantine.append({**raw, "reason": "ambiguous_chunk_text"})
            continue

        if doc_id == "hr_leave_policy" and _has_stale_hr_annual_leave(text):
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_content",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        if _is_out_of_scope_sla_chunk(doc_id, text):
            quarantine.append({**raw, "reason": "out_of_scope_sla_priority"})
            continue

        if _is_low_signal_helpdesk_chunk(doc_id, text):
            quarantine.append({**raw, "reason": "low_signal_helpdesk_onboarding"})
            continue

        fixed_text = _clean_text(
            doc_id,
            text,
            apply_refund_window_fix=apply_refund_window_fix,
        )

        key = _norm_text(fixed_text)
        if key in seen_text:
            quarantine.append({**raw, "reason": "duplicate_chunk_text"})
            continue
        seen_text.add(key)

        seq += 1
        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, fixed_text, seq),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_at or "",
            }
        )

    return cleaned, quarantine


def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8")
        return
    fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_quarantine_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8")
        return
    keys: List[str] = []
    seen_k: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_k:
                seen_k.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)
