"""Compatibility exports for M-Pesa account-number normalization."""

from src.shared.utils.student_numbers import (
    format_student_number_short,
)
from src.shared.utils.student_numbers import (
    normalize_student_number as normalize_bill_ref_to_student_number,
)

__all__ = ["format_student_number_short", "normalize_bill_ref_to_student_number"]
