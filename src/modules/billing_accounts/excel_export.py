"""Excel exports for parent billing account balances."""

from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

MONEY_FORMAT = '#,##0.00'


def _cell_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return value


def _write_rows(ws: Worksheet, rows: list[list[Any]], start_row: int = 1) -> None:
    for row_index, row in enumerate(rows, start=start_row):
        for column_index, value in enumerate(row, start=1):
            ws.cell(row=row_index, column=column_index, value=_cell_value(value))


def _style_header(ws: Worksheet, row: int, columns: int) -> None:
    fill = PatternFill("solid", fgColor="E2E8F0")
    for column in range(1, columns + 1):
        cell = ws.cell(row=row, column=column)
        cell.font = Font(bold=True)
        cell.fill = fill


def _style_money_columns(ws: Worksheet, columns: list[int], start_row: int = 1) -> None:
    for row in ws.iter_rows(min_row=start_row):
        for column in columns:
            cell = row[column - 1]
            if isinstance(cell.value, int | float):
                cell.number_format = MONEY_FORMAT


def _autosize(ws: Worksheet) -> None:
    for column_cells in ws.columns:
        width = 10
        column_letter = column_cells[0].column_letter
        for cell in column_cells:
            value = "" if cell.value is None else str(cell.value)
            width = max(width, min(len(value) + 2, 48))
        ws.column_dimensions[column_letter].width = width


def build_parent_balances_xlsx(data: dict[str, Any]) -> bytes:
    """Build an all-parents balance export."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Parent Balances"

    ws.cell(1, 1, "Parent Balances")
    ws.cell(1, 1).font = Font(bold=True, size=14)
    ws.cell(2, 1, "Generated on")
    ws.cell(2, 2, _cell_value(data.get("generated_on") or date.today()))
    if data.get("search"):
        ws.cell(3, 1, "Search")
        ws.cell(3, 2, data.get("search"))

    headers = [
        "Account #",
        "Parent / Family",
        "Guardian",
        "Phone",
        "Email",
        "Students",
        "Members",
        "Total Payments",
        "Refunds",
        "Net Paid",
        "Paid to Invoices",
        "Available Credit",
        "Total Invoiced",
        "Adjustments",
        "Outstanding Debt",
        "Amount to Pay Now",
        "Credit After Debts",
        "Net Balance",
        "Last Payment",
    ]
    header_row = 5
    _write_rows(ws, [headers], header_row)
    _style_header(ws, header_row, len(headers))

    rows = data.get("rows") or []
    row_index = header_row + 1
    for row in rows:
        _write_rows(
            ws,
            [
                [
                    row.get("account_number"),
                    row.get("display_name"),
                    row.get("primary_guardian_name"),
                    row.get("primary_guardian_phone"),
                    row.get("primary_guardian_email"),
                    row.get("students"),
                    row.get("member_count"),
                    row.get("total_payments"),
                    row.get("total_refunds"),
                    row.get("net_paid"),
                    row.get("paid_to_invoices"),
                    row.get("available_credit"),
                    row.get("total_invoiced"),
                    row.get("invoice_adjustments"),
                    row.get("outstanding_debt"),
                    row.get("amount_to_pay_now"),
                    row.get("credit_after_debts"),
                    row.get("net_balance"),
                    row.get("last_payment_date"),
                ]
            ],
            row_index,
        )
        row_index += 1

    summary = data.get("summary") or {}
    _write_rows(
        ws,
        [
            [
                "TOTAL",
                "",
                "",
                "",
                "",
                "",
                summary.get("account_count"),
                summary.get("total_payments"),
                summary.get("total_refunds"),
                summary.get("net_paid"),
                summary.get("paid_to_invoices"),
                summary.get("available_credit"),
                summary.get("total_invoiced"),
                summary.get("invoice_adjustments"),
                summary.get("outstanding_debt"),
                summary.get("amount_to_pay_now"),
                summary.get("credit_after_debts"),
                summary.get("net_balance"),
                "",
            ]
        ],
        row_index,
    )
    for column in range(1, len(headers) + 1):
        ws.cell(row_index, column).font = Font(bold=True)

    _style_money_columns(ws, list(range(8, 19)), header_row + 1)
    _autosize(ws)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_parent_balance_xlsx(data: dict[str, Any]) -> bytes:
    """Build a detailed balance export for one parent billing account."""
    wb = Workbook()
    summary_ws = wb.active
    summary_ws.title = "Summary"

    account = data.get("account") or {}
    summary = data.get("summary") or {}
    summary_rows = [
        ["Parent Balance"],
        ["Generated on", data.get("generated_on") or date.today()],
        ["Account #", account.get("account_number")],
        ["Parent / Family", account.get("display_name")],
        ["Guardian", account.get("primary_guardian_name")],
        ["Phone", account.get("primary_guardian_phone")],
        ["Email", account.get("primary_guardian_email")],
        ["Students", account.get("students")],
        [],
        ["Balance Summary", ""],
        ["Total payments received", summary.get("total_payments")],
        ["Refunds paid out", summary.get("total_refunds")],
        ["Net paid by parent", summary.get("net_paid")],
        ["Paid to invoices", summary.get("paid_to_invoices")],
        ["Available credit", summary.get("available_credit")],
        ["Total invoiced", summary.get("total_invoiced")],
        ["Invoice adjustments / write-offs", summary.get("invoice_adjustments")],
        ["Outstanding debt", summary.get("outstanding_debt")],
        ["Amount to pay now", summary.get("amount_to_pay_now")],
        ["Credit after debts", summary.get("credit_after_debts")],
        ["Net balance", summary.get("net_balance")],
    ]
    _write_rows(summary_ws, summary_rows)
    summary_ws.cell(1, 1).font = Font(bold=True, size=14)
    summary_ws.cell(10, 1).font = Font(bold=True)
    _style_money_columns(summary_ws, [2], 11)
    _autosize(summary_ws)

    students_ws = wb.create_sheet("Students")
    student_headers = ["Student #", "Student", "Grade", "Guardian", "Phone", "Status"]
    _write_rows(students_ws, [student_headers], 1)
    _style_header(students_ws, 1, len(student_headers))
    for index, student in enumerate(data.get("students") or [], start=2):
        _write_rows(
            students_ws,
            [[
                student.get("student_number"),
                student.get("student_name"),
                student.get("grade_name"),
                student.get("guardian_name"),
                student.get("guardian_phone"),
                student.get("status"),
            ]],
            index,
        )
    _autosize(students_ws)

    invoices_ws = wb.create_sheet("Invoices")
    invoice_headers = [
        "Invoice #",
        "Student",
        "Type",
        "Status",
        "Issue Date",
        "Due Date",
        "Total",
        "Paid",
        "Adjustments",
        "Amount Due",
    ]
    _write_rows(invoices_ws, [invoice_headers], 1)
    _style_header(invoices_ws, 1, len(invoice_headers))
    for index, invoice in enumerate(data.get("invoices") or [], start=2):
        _write_rows(
            invoices_ws,
            [[
                invoice.get("invoice_number"),
                invoice.get("student_name"),
                invoice.get("invoice_type"),
                invoice.get("status"),
                invoice.get("issue_date"),
                invoice.get("due_date"),
                invoice.get("total"),
                invoice.get("paid_total"),
                invoice.get("adjustment_total"),
                invoice.get("amount_due"),
            ]],
            index,
        )
    _style_money_columns(invoices_ws, [7, 8, 9, 10], 2)
    _autosize(invoices_ws)

    payments_ws = wb.create_sheet("Payments")
    payment_headers = [
        "Date",
        "Payment #",
        "Receipt #",
        "Student",
        "Method",
        "Reference",
        "Status",
        "Amount",
        "Refunded",
        "Net Amount",
    ]
    _write_rows(payments_ws, [payment_headers], 1)
    _style_header(payments_ws, 1, len(payment_headers))
    for index, payment in enumerate(data.get("payments") or [], start=2):
        _write_rows(
            payments_ws,
            [[
                payment.get("payment_date"),
                payment.get("payment_number"),
                payment.get("receipt_number"),
                payment.get("student_name"),
                payment.get("payment_method"),
                payment.get("reference"),
                payment.get("status"),
                payment.get("amount"),
                payment.get("refunded_amount"),
                payment.get("net_amount"),
            ]],
            index,
        )
    _style_money_columns(payments_ws, [8, 9, 10], 2)
    _autosize(payments_ws)

    refunds_ws = wb.create_sheet("Refunds")
    refund_headers = [
        "Date",
        "Refund #",
        "Method",
        "Reference",
        "Reason",
        "Amount",
    ]
    _write_rows(refunds_ws, [refund_headers], 1)
    _style_header(refunds_ws, 1, len(refund_headers))
    for index, refund in enumerate(data.get("refunds") or [], start=2):
        _write_rows(
            refunds_ws,
            [[
                refund.get("refund_date"),
                refund.get("refund_number"),
                refund.get("refund_method"),
                refund.get("reference_number"),
                refund.get("reason"),
                refund.get("amount"),
            ]],
            index,
        )
    _style_money_columns(refunds_ws, [6], 2)
    _autosize(refunds_ws)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
