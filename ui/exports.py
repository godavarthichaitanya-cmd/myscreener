"""
ui/exports.py — builds the three export formats for a completed
evaluation: plain-text, CSV, and PDF.

All three take the SAME evaluation dict shape produced in
ui/single_stock.py's Evaluate step (st.session_state["last_eval"]) plus
the symbol/price, so there's one source of truth for what "a completed
evaluation" contains.
"""

import csv
import io
from datetime import datetime

from fpdf import FPDF


def build_copy_summary(symbol: str, cmp: float, ev: dict) -> str:
    """Plain-text summary of BOTH PP and Sampat results."""

    lines = [
        f"{symbol} — ₹{cmp}",
        "",
        f"PP FRAMEWORK: {ev['passed']}/{ev['total']} passed — {ev['verdict_text']}",
        "PASSED:",
    ]

    for label, ok in ev["checks"]:
        if ok is True:
            lines.append(f"  ✓ {label}")

    lines.append("FAILED / NO DATA:")

    for label, ok in ev["checks"]:
        if ok is False:
            lines.append(f"  ✗ {label}")
        elif ok is None:
            lines.append(f"  ○ {label} (no data)")

    lines += [
        "",
        f"SAMPAT MODE: "
        f"{ev['sampat']['passed']}/{ev['sampat']['total']} passed "
        f"({ev['sampat']['pct']}%) — {ev['sampat']['text']}",
        "PASSED:",
    ]

    for label, ok in ev["sampat"]["checks"]:
        if ok is True:
            lines.append(f"  ✓ {label}")

    lines.append("FAILED / NO DATA:")

    for label, ok in ev["sampat"]["checks"]:
        if ok is False:
            lines.append(f"  ✗ {label}")
        elif ok is None:
            lines.append(f"  ○ {label} (no data)")

    lines += [
        "",
        f"Checked: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ]

    return "\n".join(lines)


def build_csv_bytes(symbol: str, cmp: float, ev: dict) -> bytes:
    """
    One row per check for both PP and Sampat.
    """

    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow(
        ["symbol", "cmp", "framework", "check", "result"]
    )

    for label, ok in ev["checks"]:
        result = (
            "PASS"
            if ok is True
            else ("FAIL" if ok is False else "N/A")
        )
        writer.writerow(
            [symbol, cmp, "PP", label, result]
        )

    for label, ok in ev["sampat"]["checks"]:
        result = (
            "PASS"
            if ok is True
            else ("FAIL" if ok is False else "N/A")
        )
        writer.writerow(
            [symbol, cmp, "Sampat", label, result]
        )

    return buf.getvalue().encode("utf-8")


def _pdf_safe(text: str) -> str:
    """
    Convert Unicode characters that are unsupported by FPDF's built-in
    Helvetica font into ASCII-safe equivalents.

    FPDF's core fonts such as Helvetica do not support many Unicode
    characters, including:
        ≤ ≥ ₹ ✓ ✗ ○ → — – − × ÷ • …

    This function keeps the PDF independent of external font files.
    """

    if text is None:
        return ""

    text = str(text)

    replacements = {
        # Mathematical comparison symbols
        "≤": "<=",
        "≥": ">=",
        "≠": "!=",
        "≈": "~",

        # Currency
        "₹": "Rs.",

        # Check / status symbols
        "✓": "[OK]",
        "✔": "[OK]",
        "✗": "[X]",
        "✘": "[X]",
        "○": "[N/A]",

        # Arrows
        "→": "->",
        "←": "<-",
        "↔": "<->",
        "↑": "^",
        "↓": "v",

        # Dashes / minus
        "—": "-",
        "–": "-",
        "−": "-",

        # Math
        "×": "x",
        "÷": "/",

        # Bullets / ellipsis
        "•": "-",
        "…": "...",

        # Smart quotes
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',

        # Non-breaking space
        "\u00a0": " ",
    }

    for char, replacement in replacements.items():
        text = text.replace(char, replacement)

    # Final safety net:
    # Helvetica supports Latin-1, so replace anything else that remains.
    return text.encode("latin-1", "replace").decode("latin-1")


def build_pdf_bytes(symbol: str, cmp: float, ev: dict) -> bytes:
    """
    Build a PDF summary containing:
      - Stock symbol and current price
      - Evaluation timestamp
      - PP Framework result
      - Sampat Mode result
      - Individual checks

    All dynamic text is passed through _pdf_safe() before being sent
    to FPDF/Helvetica.
    """

    pdf = FPDF()
    pdf.add_page()

    # ---------------------------------------------------------
    # Header
    # ---------------------------------------------------------

    pdf.set_font("Helvetica", "B", 16)

    pdf.cell(
        0,
        10,
        _pdf_safe(f"{symbol} - Rs.{cmp}"),
        ln=True,
    )

    pdf.set_font("Helvetica", "", 10)

    pdf.cell(
        0,
        6,
        _pdf_safe(
            f"Checked: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        ),
        ln=True,
    )

    pdf.ln(4)

    # ---------------------------------------------------------
    # Framework writer
    # ---------------------------------------------------------

    def write_framework(
        title,
        passed,
        total,
        verdict_text,
        checks,
    ):
        # Framework heading
        pdf.set_font("Helvetica", "B", 13)

        pdf.cell(
            0,
            8,
            _pdf_safe(
                f"{title} - {passed}/{total} passed"
            ),
            ln=True,
        )

        # Verdict
        pdf.set_font("Helvetica", "I", 10)

        pdf.multi_cell(
            0,
            6,
            _pdf_safe(verdict_text),
        )

        pdf.ln(1)

        # Individual checks
        pdf.set_font("Helvetica", "", 10)

        for label, ok in checks:

            status = (
                "PASS"
                if ok is True
                else (
                    "FAIL"
                    if ok is False
                    else "N/A"
                )
            )

            line = f"  [{status}] {label}"

            pdf.cell(
                0,
                6,
                _pdf_safe(line),
                ln=True,
            )

        pdf.ln(4)

    # ---------------------------------------------------------
    # PP Framework
    # ---------------------------------------------------------

    write_framework(
        "PP FRAMEWORK",
        ev["passed"],
        ev["total"],
        ev["verdict_text"],
        ev["checks"],
    )

    # ---------------------------------------------------------
    # Sampat Mode
    # ---------------------------------------------------------

    write_framework(
        "SAMPAT MODE",
        ev["sampat"]["passed"],
        ev["sampat"]["total"],
        ev["sampat"]["text"],
        ev["sampat"]["checks"],
    )

    # ---------------------------------------------------------
    # Return PDF bytes
    # ---------------------------------------------------------

    return bytes(pdf.output())