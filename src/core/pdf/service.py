"""PDF generation service (invoice and receipt) from HTML templates."""

import base64
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.core.exceptions import PdfGenerationUnavailableError

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "pdf"


def _amount_to_words(amount: float) -> str:
    """Convert amount to words (e.g. 50000 -> 'Fifty Thousand Shillings Only')."""
    try:
        from num2words import num2words
    except ImportError:
        return f"{int(amount):,} KES"
    amount_int = int(round(amount, 0))
    words = num2words(amount_int, lang="en").title()
    return f"{words} Shillings Only"


class PDFService:
    """Generate PDF documents from Jinja2 templates and WeasyPrint."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=True,
        )

    def generate_invoice_pdf(self, context: dict) -> bytes:
        """Render invoice template with context and return PDF bytes."""
        try:
            from weasyprint import HTML
        except (OSError, ImportError) as e:
            raise PdfGenerationUnavailableError(
                f"PDF generation unavailable (WeasyPrint/system libs). On macOS: brew install pango glib. {e!s}"
            ) from e
        template = self._env.get_template("invoice.html")
        html_content = template.render(**context)
        try:
            return HTML(string=html_content).write_pdf()
        except Exception as e:
            raise PdfGenerationUnavailableError(str(e)) from e

    def generate_receipt_pdf(self, context: dict) -> bytes:
        """Render receipt template with context and return PDF bytes."""
        try:
            from weasyprint import HTML
        except (OSError, ImportError) as e:
            raise PdfGenerationUnavailableError(
                f"PDF generation unavailable (WeasyPrint/system libs). On macOS: brew install pango glib. {e!s}"
            ) from e
        template = self._env.get_template("receipt.html")
        html_content = template.render(**context)
        try:
            return HTML(string=html_content).write_pdf()
        except Exception as e:
            raise PdfGenerationUnavailableError(str(e)) from e


def image_to_data_uri(content: bytes, content_type: str) -> str:
    """Convert image bytes to data URI for embedding in HTML."""
    b64 = base64.b64encode(content).decode("ascii")
    return f"data:{content_type};base64,{b64}"


def build_invoice_context(
    invoice,
    school_settings,
    logo_data_uri: str | None,
) -> dict:
    """Build template context for invoice PDF from ORM models and school settings."""
    student = invoice.student
    term = invoice.term
    grade_name = student.grade.name if student.grade else ""

    school_info = {
        "name": school_settings.school_name or "",
        "address": school_settings.school_address or "",
        "phone": school_settings.school_phone or "",
        "email": school_settings.school_email or "",
    }
    mpesa_info = None
    if school_settings.use_paybill and school_settings.mpesa_business_number:
        mpesa_info = {
            "business_number": school_settings.mpesa_business_number,
            "account_number": student.student_number,
        }
    bank_info = None
    if school_settings.use_bank_transfer and school_settings.bank_name:
        bank_info = {
            "bank_name": school_settings.bank_name or "",
            "account_name": school_settings.bank_account_name or "",
            "account_number": school_settings.bank_account_number or "",
            "branch": school_settings.bank_branch or "",
            "swift_code": school_settings.bank_swift_code or "",
        }

    lines = [
        {
            "description": line.description,
            "quantity": line.quantity,
            "unit_price": float(line.unit_price),
            "line_total": float(line.line_total),
        }
        for line in invoice.lines
    ]

    return {
        "invoice": {
            "invoice_number": invoice.invoice_number,
            "issue_date": invoice.issue_date,
            "due_date": invoice.due_date,
            "created_at": invoice.created_at,
            "subtotal": float(invoice.subtotal),
            "discount_total": float(invoice.discount_total),
            "total": float(invoice.total),
            "paid_total": float(invoice.paid_total),
            "amount_due": float(invoice.amount_due),
            "lines": lines,
            "student": {
                "full_name": student.full_name,
                "student_number": student.student_number,
                "grade": grade_name,
                "guardian_name": student.guardian_name,
                "guardian_phone": student.guardian_phone,
            },
            "term": {
                "display_name": term.display_name if term else "",
                "academic_year": f"{term.year}/{term.year + 1}" if term else "",
            },
        },
        "school_info": school_info,
        "mpesa_info": mpesa_info,
        "bank_info": bank_info,
        "logo_data_uri": logo_data_uri,
        "generated_at": invoice.updated_at or invoice.created_at,
    }


def build_receipt_context(
    payment,
    school_settings,
    logo_data_uri: str | None,
    stamp_data_uri: str | None,
) -> dict:
    """Build template context for receipt PDF."""
    student = payment.student
    grade_name = student.grade.name if student.grade else ""

    amount = float(payment.amount)
    amount_in_words = _amount_to_words(amount)

    school_info = {
        "name": school_settings.school_name or "",
        "address": school_settings.school_address or "",
        "phone": school_settings.school_phone or "",
        "email": school_settings.school_email or "",
    }

    received_by_name = ""
    if payment.received_by:
        received_by_name = payment.received_by.full_name

    return {
        "payment": {
            "amount": amount,
            "receipt_number": payment.receipt_number or payment.payment_number,
            "payment_method": payment.payment_method,
            "reference": payment.reference or "",
            "created_at": payment.created_at,
            "student": {
                "full_name": student.full_name,
                "student_number": student.student_number,
                "grade": grade_name,
                "guardian_name": student.guardian_name,
                "guardian_phone": student.guardian_phone,
            },
            "received_by_name": received_by_name,
        },
        "amount_in_words": amount_in_words,
        "school_info": school_info,
        "logo_data_uri": logo_data_uri,
        "stamp_data_uri": stamp_data_uri,
        "generated_at": payment.updated_at or payment.created_at,
    }


pdf_service = PDFService()
