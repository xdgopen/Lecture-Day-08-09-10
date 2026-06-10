"""
Expectation suite đơn giản (không bắt buộc Great Expectations).

Sinh viên có thể thay bằng GE / pydantic / custom — miễn là có halt có kiểm soát.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


EXPECTED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
        "access_control_sop",
    }
)


@dataclass
class ExpectationResult:
    name: str
    passed: bool
    severity: str  # "warn" | "halt"
    detail: str


def run_expectations(cleaned_rows: List[Dict[str, Any]]) -> Tuple[List[ExpectationResult], bool]:
    """
    Trả về (results, should_halt).

    should_halt = True nếu có bất kỳ expectation severity halt nào fail.
    """
    results: List[ExpectationResult] = []

    # E1: có ít nhất 1 dòng sau clean
    ok = len(cleaned_rows) >= 1
    results.append(
        ExpectationResult(
            "min_one_row",
            ok,
            "halt",
            f"cleaned_rows={len(cleaned_rows)}",
        )
    )

    # E2: không doc_id rỗng
    bad_doc = [r for r in cleaned_rows if not (r.get("doc_id") or "").strip()]
    ok2 = len(bad_doc) == 0
    results.append(
        ExpectationResult(
            "no_empty_doc_id",
            ok2,
            "halt",
            f"empty_doc_id_count={len(bad_doc)}",
        )
    )

    # E3: policy refund không được chứa cửa sổ sai 14 ngày (sau khi đã fix)
    bad_refund = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "policy_refund_v4"
        and "14 ngày làm việc" in (r.get("chunk_text") or "")
    ]
    ok3 = len(bad_refund) == 0
    results.append(
        ExpectationResult(
            "refund_no_stale_14d_window",
            ok3,
            "halt",
            f"violations={len(bad_refund)}",
        )
    )

    # E4: chunk_text đủ dài
    short = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) < 8]
    ok4 = len(short) == 0
    results.append(
        ExpectationResult(
            "chunk_min_length_8",
            ok4,
            "warn",
            f"short_chunks={len(short)}",
        )
    )

    # E5: effective_date đúng định dạng ISO sau clean (phát hiện parser lỏng)
    iso_bad = [
        r
        for r in cleaned_rows
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", (r.get("effective_date") or "").strip())
    ]
    ok5 = len(iso_bad) == 0
    results.append(
        ExpectationResult(
            "effective_date_iso_yyyy_mm_dd",
            ok5,
            "halt",
            f"non_iso_rows={len(iso_bad)}",
        )
    )

    # E6: không còn marker phép năm cũ 10 ngày trên doc HR (conflict version sau clean)
    bad_hr_annual = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "hr_leave_policy"
        and "10 ngày phép năm" in (r.get("chunk_text") or "")
    ]
    ok6 = len(bad_hr_annual) == 0
    results.append(
        ExpectationResult(
            "hr_leave_no_stale_10d_annual",
            ok6,
            "halt",
            f"violations={len(bad_hr_annual)}",
        )
    )

    # E7: cleaned corpus phải có đủ 5 nguồn cần cho grading/retrieval.
    present_doc_ids = {r.get("doc_id") for r in cleaned_rows}
    missing_doc_ids = sorted(EXPECTED_DOC_IDS - present_doc_ids)
    ok7 = len(missing_doc_ids) == 0
    results.append(
        ExpectationResult(
            "required_doc_ids_present",
            ok7,
            "halt",
            f"missing_doc_ids={missing_doc_ids}",
        )
    )

    # E8: exported_at phải là ISO datetime để freshness/lineage đáng tin.
    exported_at_bad = [
        r
        for r in cleaned_rows
        if not re.match(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
            (r.get("exported_at") or "").strip(),
        )
    ]
    ok8 = len(exported_at_bad) == 0
    results.append(
        ExpectationResult(
            "exported_at_iso_datetime",
            ok8,
            "halt",
            f"non_iso_exported_at_rows={len(exported_at_bad)}",
        )
    )

    # E9: không publish chunk đã tự gắn nhãn là không rõ ràng.
    ambiguous = [
        r
        for r in cleaned_rows
        if (r.get("chunk_text") or "").strip().lower().startswith("nội dung không rõ ràng:")
    ]
    ok9 = len(ambiguous) == 0
    results.append(
        ExpectationResult(
            "no_ambiguous_chunk_text",
            ok9,
            "halt",
            f"ambiguous_rows={len(ambiguous)}",
        )
    )

    # E10: corpus SLA publish cho lab này chỉ phục vụ P1; P2 gây nhiễu top-k P1.
    p2_sla = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "sla_p1_2026"
        and (r.get("chunk_text") or "").strip().lower().startswith("ticket p2:")
    ]
    ok10 = len(p2_sla) == 0
    results.append(
        ExpectationResult(
            "sla_p1_no_p2_priority_chunk",
            ok10,
            "halt",
            f"p2_chunks={len(p2_sla)}",
        )
    )

    # E11: chunk chính P1 phải đủ các facts thường hỏi cùng nhau.
    p1_core_missing_escalation = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "sla_p1_2026"
        and "SLA phản hồi ban đầu 15 phút" in (r.get("chunk_text") or "")
        and "10 phút" not in (r.get("chunk_text") or "")
    ]
    ok11 = len(p1_core_missing_escalation) == 0
    results.append(
        ExpectationResult(
            "sla_p1_core_chunk_has_escalation",
            ok11,
            "halt",
            f"core_chunks_missing_escalation={len(p1_core_missing_escalation)}",
        )
    )

    halt = any(not r.passed and r.severity == "halt" for r in results)
    return results, halt
