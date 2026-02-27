from __future__ import annotations

import re


_FULL_STUDENT_NUMBER_RE = re.compile(r"^STU-(\d{4})-(\d{6})$")
_SHORT_ADMISSION_RE = re.compile(r"^(\d{2})(\d{1,6})$")


def normalize_bill_ref_to_student_number(bill_ref_number: str) -> str | None:
    """
    Convert M-Pesa BillRefNumber (account number) into internal Student.student_number.

    Supported inputs:
    - Full form: STU-YYYY-NNNNNN
    - Short admission#: YY + N... (NNN... is numeric part without leading zeros),
      as shown in UI by formatStudentNumberShort().
      Example: 26123 -> STU-2026-000123
    """
    raw = (bill_ref_number or "").strip().upper()
    if not raw:
        return None

    # Normalize common separators/spaces parents may include.
    compact = "".join(ch for ch in raw if ch.isalnum() or ch == "-")
    compact = compact.replace(" ", "").replace("_", "").replace("/", "")

    m_full = _FULL_STUDENT_NUMBER_RE.match(compact)
    if m_full:
        return compact

    digits_only = "".join(ch for ch in compact if ch.isdigit())
    m_short = _SHORT_ADMISSION_RE.match(digits_only)
    if not m_short:
        return None

    yy = int(m_short.group(1))
    num = int(m_short.group(2))
    if num <= 0 or num > 999999:
        return None

    year = 2000 + yy
    if year < 2000 or year > 2099:
        return None

    return f"STU-{year}-{num:06d}"

