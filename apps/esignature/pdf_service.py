"""
apps/esignature/pdf_service.py
──────────────────────────────
Production-ready PDF signing service.

Responsibilities
----------------
1.  Validate that the source PDF has not been tampered with (SHA-256 check).
2.  Overlay one or more signature images onto specified pages / coordinates.
3.  Stamp a visible "signed by / date / reference" banner onto the page.
4.  Append an invisible but machine-readable signing manifest page.
5.  Compute and return the SHA-256 of the resulting file.

Dependencies (already in requirements/base.txt)
------------------------------------------------
    reportlab >= 4.0
    PyPDF2    >= 3.0
    Pillow    >= 10.0

Public API
----------
    PDFSigningService.embed_signature(...)   → (bytes, sha256_hex)
    PDFSigningService.verify_integrity(...)  → bool
    PDFSigningService.generate_preview(...)  → bytes   (first-page PNG)
    PDFSigningService.build_signing_manifest(...)  → bytes
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import os
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger("esignature.pdf_service")

# ---------------------------------------------------------------------------
# Optional imports – fail loudly at import time so missing deps are caught
# early rather than at runtime.
# ---------------------------------------------------------------------------
try:
    from PyPDF2 import PdfReader, PdfWriter
    from PyPDF2.errors import PdfReadError
except ImportError as exc:  # pragma: no cover
    raise ImportError("PyPDF2 >= 3.0 is required: pip install PyPDF2") from exc

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas
except ImportError as exc:  # pragma: no cover
    raise ImportError("ReportLab >= 4.0 is required: pip install reportlab") from exc

try:
    from PIL import Image as PILImage
except ImportError as exc:  # pragma: no cover
    raise ImportError("Pillow >= 10.0 is required: pip install Pillow") from exc


# ---------------------------------------------------------------------------
# Data-transfer objects
# ---------------------------------------------------------------------------


@dataclass
class SignaturePlacement:
    """
    Where to embed a single signature on a PDF page.

    Coordinates use PDF user-space units (points, 1 pt = 1/72 inch).
    Origin is the bottom-left corner of the page (standard PDF convention).

    Attributes
    ----------
    page_number : int
        1-based page index.
    x : float
        Distance from left edge of page (points).
    y : float
        Distance from bottom edge of page (points).
    width : float
        Width of the signature box (points).
    height : float
        Height of the signature box (points).
    """

    page_number: int = 1
    x: float = 72.0  # ~1 inch from left
    y: float = 72.0  # ~1 inch from bottom
    width: float = 180.0  # ~2.5 inches
    height: float = 60.0  # ~0.83 inch

    @classmethod
    def from_dict(cls, data: dict) -> "SignaturePlacement":
        """Construct from the JSON blob stored on SignerAssignment.placement."""
        return cls(
            page_number=int(data.get("page", 1)),
            x=float(data.get("x", 72)),
            y=float(data.get("y", 72)),
            width=float(data.get("width", 180)),
            height=float(data.get("height", 60)),
        )

    def to_dict(self) -> dict:
        return {
            "page": self.page_number,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class SignatureStampData:
    """
    All information needed to stamp one signer's signature onto a PDF.
    """

    signer_name: str
    signer_email: str
    signed_at: datetime
    signing_reference: str  # e.g. "ESIG-2025-00042 · Signer 1 of 3"
    ip_address: str = ""
    placement: SignaturePlacement = field(default_factory=SignaturePlacement)
    # One of: base64 data-URI string, raw bytes, or a file-like object
    signature_image: Optional[object] = None
    # Optional initials-only image for a compact witness stamp
    initials_image: Optional[object] = None


# ---------------------------------------------------------------------------
# Colour / style constants (matches Enwealth brand palette)
# ---------------------------------------------------------------------------

BRAND_PRIMARY = colors.HexColor("#1a0a3c")  # deep purple
BRAND_ACCENT = colors.HexColor("#7dc143")  # green
BRAND_LIGHT = colors.HexColor("#e8f5d0")  # pale green bg
BORDER_GREY = colors.HexColor("#d1d5db")
TEXT_MUTED = colors.HexColor("#6b7280")

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"

SIG_BOX_PADDING = 4  # pts inside the stamp box
SIG_BOX_RADIUS = 4  # pts corner radius
BANNER_HEIGHT = 14  # pts — height of the top banner strip
FOOTER_FONT_SIZE = 6  # pts
LABEL_FONT_SIZE = 7  # pts


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_of_fileobj(fileobj) -> str:
    sha = hashlib.sha256()
    fileobj.seek(0)
    for chunk in iter(lambda: fileobj.read(65536), b""):
        sha.update(chunk)
    fileobj.seek(0)
    return sha.hexdigest()


def _load_image_bytes(source) -> bytes:
    """
    Accept a source that is one of:
      - bytes
      - a base64 data-URI string  (data:image/png;base64,…)
      - a Django FieldFile / file-like with .read()
      - a filesystem path string

    Returns raw image bytes.
    """
    if isinstance(source, bytes):
        return source

    if isinstance(source, str):
        if source.startswith("data:"):
            # Strip the data-URI header
            header, encoded = source.split(",", 1)
            return base64.b64decode(encoded)
        # Treat as filesystem path
        with open(source, "rb") as fh:
            return fh.read()

    # Django FieldFile or any file-like object
    if hasattr(source, "read"):
        pos = source.tell() if hasattr(source, "tell") else None
        data = source.read()
        if pos is not None:
            source.seek(pos)
        return data

    raise TypeError(f"Cannot load image from {type(source)!r}")


def _image_bytes_to_reader(img_bytes: bytes) -> ImageReader:
    """Convert raw image bytes to a ReportLab ImageReader."""
    buf = io.BytesIO(img_bytes)
    # Normalise to RGBA PNG so ReportLab handles transparency correctly
    pil_img = PILImage.open(buf).convert("RGBA")
    out = io.BytesIO()
    pil_img.save(out, format="PNG")
    out.seek(0)
    return ImageReader(out)


def _trim_transparent_borders(img_bytes: bytes) -> bytes:
    """
    Remove transparent / white borders from a signature image so it fills
    its target box as tightly as possible.
    """
    buf = io.BytesIO(img_bytes)
    img = PILImage.open(buf).convert("RGBA")
    r, g, b, a = img.split()
    # Build a mask: opaque pixels are considered "content"
    bbox = a.getbbox()
    if bbox:
        img = img.crop(bbox)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


# ---------------------------------------------------------------------------
# Overlay builder (ReportLab → overlay PDF bytes)
# ---------------------------------------------------------------------------


def _build_signature_overlay(
    page_width: float,
    page_height: float,
    stamp: SignatureStampData,
) -> bytes:
    """
    Draw a single signature stamp onto a blank ReportLab canvas sized to
    match the target page.  Returns the overlay as PDF bytes.

    Layout inside the stamp box
    ---------------------------
    ┌─────────────────────────────────────────┐  ← top accent bar (BRAND_ACCENT)
    │ [signature image]    Signed by: Name    │
    │                      Email              │
    │                      Date / Time        │
    │                      Ref: ESIG-…        │
    └─────────────────────────────────────────┘
    """
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(page_width, page_height))

    p = stamp.placement
    x, y, w, h = p.x, p.y, p.width, p.height

    # ------------------------------------------------------------------ frame
    c.saveState()
    c.setStrokeColor(BRAND_ACCENT)
    c.setLineWidth(1.2)
    c.roundRect(x, y, w, h, radius=SIG_BOX_RADIUS, stroke=1, fill=0)

    # Top accent banner
    c.setFillColor(BRAND_ACCENT)
    # Clip to top corners only by drawing a filled rect then masking
    c.rect(x, y + h - BANNER_HEIGHT, w, BANNER_HEIGHT, stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.setFont(FONT_BOLD, 7)
    c.drawString(
        x + SIG_BOX_PADDING,
        y + h - BANNER_HEIGHT + 4,
        "ELECTRONIC SIGNATURE",
    )

    # Optionally draw the signature image (left ~40 % of the box)
    img_area_width = w * 0.42
    text_x = x + img_area_width + SIG_BOX_PADDING * 2

    if stamp.signature_image:
        try:
            raw = _load_image_bytes(stamp.signature_image)
            raw = _trim_transparent_borders(raw)
            ir = _image_bytes_to_reader(raw)
            img_x = x + SIG_BOX_PADDING
            img_y = y + SIG_BOX_PADDING
            img_w = img_area_width - SIG_BOX_PADDING * 2
            img_h = h - BANNER_HEIGHT - SIG_BOX_PADDING * 2
            c.drawImage(
                ir,
                img_x,
                img_y,
                width=img_w,
                height=img_h,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
        except Exception as exc:
            logger.warning("Could not embed signature image: %s", exc)
            # Draw a placeholder line instead
            c.setStrokeColor(BRAND_PRIMARY)
            c.setLineWidth(0.8)
            mid_y = y + (h - BANNER_HEIGHT) / 2
            c.line(
                x + SIG_BOX_PADDING,
                mid_y,
                x + img_area_width - SIG_BOX_PADDING,
                mid_y,
            )

    # Vertical divider between image and text columns
    c.setStrokeColor(BORDER_GREY)
    c.setLineWidth(0.5)
    c.line(
        x + img_area_width,
        y + SIG_BOX_PADDING,
        x + img_area_width,
        y + h - BANNER_HEIGHT - SIG_BOX_PADDING,
    )

    # ------------------------------------------------------------------ text
    line_height = 9
    ty = y + h - BANNER_HEIGHT - SIG_BOX_PADDING - line_height

    # Signer name
    c.setFillColor(BRAND_PRIMARY)
    c.setFont(FONT_BOLD, LABEL_FONT_SIZE)
    c.drawString(text_x, ty, "Signed by:")
    c.setFont(FONT_REGULAR, LABEL_FONT_SIZE)
    ty -= line_height
    # Truncate long names
    display_name = stamp.signer_name[:38]
    c.drawString(text_x, ty, display_name)
    ty -= line_height

    # Email
    c.setFillColor(TEXT_MUTED)
    c.setFont(FONT_REGULAR, FOOTER_FONT_SIZE)
    display_email = stamp.signer_email[:40]
    c.drawString(text_x, ty, display_email)
    ty -= line_height

    # Date / time
    date_str = stamp.signed_at.strftime("%d %b %Y  %H:%M UTC")
    c.drawString(text_x, ty, date_str)
    ty -= line_height

    # Reference
    c.setFont(FONT_ITALIC, FOOTER_FONT_SIZE)
    ref = stamp.signing_reference[:50]
    c.drawString(text_x, ty, ref)

    # IP address (small, at very bottom of text area)
    if stamp.ip_address:
        ty -= line_height - 2
        c.setFont(FONT_REGULAR, FOOTER_FONT_SIZE - 1)
        c.setFillColor(BORDER_GREY)
        c.drawString(text_x, ty, f"IP: {stamp.ip_address}")

    c.restoreState()
    c.save()
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Main service class
# ---------------------------------------------------------------------------


class PDFSigningService:
    """
    Stateless service class.  All methods are class methods / static methods
    so the service can be used without instantiation.
    """

    # Maximum file size (20 MB) – reject anything larger
    MAX_FILE_SIZE = 20 * 1024 * 1024

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def embed_signature(
        cls,
        source_pdf: object,
        stamp: SignatureStampData,
        expected_hash: str = "",
    ) -> tuple[bytes, str]:
        """
        Embed a signature stamp onto *source_pdf* and return the modified PDF.

        Parameters
        ----------
        source_pdf : file-like | bytes | str (path)
            The original PDF to sign.
        stamp : SignatureStampData
            Placement and visual details of the signature.
        expected_hash : str
            If non-empty, the file's SHA-256 is verified before signing.
            Raises ``IntegrityError`` if the hash does not match.

        Returns
        -------
        (pdf_bytes, sha256_hex)
            The signed PDF as bytes plus its SHA-256.

        Raises
        ------
        IntegrityError
            Source PDF hash mismatch (tamper detected).
        PDFSigningError
            Any other PDF processing error.
        """
        pdf_bytes = (
            _load_image_bytes(source_pdf)
            if not isinstance(source_pdf, bytes)
            else source_pdf
        )

        # Integrity check
        if expected_hash:
            actual = _sha256_of_bytes(pdf_bytes)
            if actual != expected_hash:
                logger.error(
                    "Tamper detected: expected %s, got %s", expected_hash, actual
                )
                raise IntegrityError(
                    f"Document hash mismatch – expected {expected_hash[:16]}…, "
                    f"got {actual[:16]}…"
                )

        try:
            result_bytes = cls._apply_overlay(pdf_bytes, stamp)
        except PdfReadError as exc:
            raise PDFSigningError(f"Cannot read source PDF: {exc}") from exc
        except Exception as exc:
            raise PDFSigningError(f"PDF signing failed: {exc}") from exc

        sha = _sha256_of_bytes(result_bytes)
        return result_bytes, sha

    @classmethod
    def embed_multiple_signatures(
        cls,
        source_pdf: object,
        stamps: list[SignatureStampData],
        expected_hash: str = "",
    ) -> tuple[bytes, str]:
        """
        Embed all stamps in sequence onto the same PDF.

        Used when finalising a document after all signers have signed.
        """
        pdf_bytes = (
            _load_image_bytes(source_pdf)
            if not isinstance(source_pdf, bytes)
            else source_pdf
        )

        if expected_hash:
            actual = _sha256_of_bytes(pdf_bytes)
            if actual != expected_hash:
                raise IntegrityError(
                    f"Document hash mismatch – expected {expected_hash[:16]}…"
                )

        try:
            current = pdf_bytes
            for stamp in stamps:
                current = cls._apply_overlay(current, stamp)
        except Exception as exc:
            raise PDFSigningError(f"Multi-signature PDF failed: {exc}") from exc

        sha = _sha256_of_bytes(current)
        return current, sha

    @classmethod
    def verify_integrity(cls, pdf_source: object, expected_hash: str) -> bool:
        """
        Return True if the SHA-256 of *pdf_source* matches *expected_hash*.
        """
        try:
            pdf_bytes = (
                _load_image_bytes(pdf_source)
                if not isinstance(pdf_source, bytes)
                else pdf_source
            )
            return _sha256_of_bytes(pdf_bytes) == expected_hash
        except Exception as exc:
            logger.error("Integrity check failed: %s", exc)
            return False

    @classmethod
    def build_signing_manifest(
        cls,
        document_title: str,
        reference_number: str,
        original_hash: str,
        signed_hash: str,
        signers: list[dict],
        generated_at: datetime | None = None,
    ) -> bytes:
        """
        Generate a standalone PDF "Signing Manifest" page that can be
        appended to the signed document or delivered separately.

        Parameters
        ----------
        signers : list[dict]
            Each dict has keys: name, email, role, signed_at, ip_address.

        Returns
        -------
        bytes
            A single-page PDF.
        """
        if generated_at is None:
            generated_at = datetime.utcnow()

        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)
        page_w, page_h = A4

        # ---- Header bar ----
        c.setFillColor(BRAND_PRIMARY)
        c.rect(0, page_h - 60 * mm, page_w, 60 * mm, stroke=0, fill=1)

        c.setFillColor(colors.white)
        c.setFont(FONT_BOLD, 16)
        c.drawString(20 * mm, page_h - 20 * mm, "Electronic Signing Manifest")
        c.setFont(FONT_REGULAR, 9)
        c.drawString(
            20 * mm,
            page_h - 28 * mm,
            "Enwealth E-Board — Legally Traceable Digital Signature Record",
        )

        c.setFillColor(BRAND_ACCENT)
        c.setFont(FONT_BOLD, 11)
        c.drawString(20 * mm, page_h - 40 * mm, reference_number)

        c.setFillColor(colors.white)
        c.setFont(FONT_REGULAR, 8)
        c.drawString(
            20 * mm,
            page_h - 50 * mm,
            f"Generated: {generated_at.strftime('%d %b %Y %H:%M UTC')}",
        )

        # ---- Document details ----
        y = page_h - 70 * mm

        def section_title(text, y_pos):
            c.setFillColor(BRAND_PRIMARY)
            c.setFont(FONT_BOLD, 10)
            c.drawString(20 * mm, y_pos, text)
            c.setStrokeColor(BRAND_ACCENT)
            c.setLineWidth(0.8)
            c.line(20 * mm, y_pos - 2 * mm, page_w - 20 * mm, y_pos - 2 * mm)
            return y_pos - 8 * mm

        def kv_row(label, value, y_pos, mono=False):
            c.setFillColor(TEXT_MUTED)
            c.setFont(FONT_BOLD, 8)
            c.drawString(22 * mm, y_pos, label)
            c.setFillColor(BRAND_PRIMARY)
            c.setFont("Courier" if mono else FONT_REGULAR, 8)
            c.drawString(75 * mm, y_pos, str(value)[:80])
            return y_pos - 6 * mm

        y = section_title("Document Information", y)
        y = kv_row("Title", document_title, y)
        y = kv_row("Reference", reference_number, y)
        y = kv_row("Original SHA-256", original_hash, y, mono=True)
        y = kv_row("Signed SHA-256", signed_hash, y, mono=True)
        y -= 4 * mm

        # ---- Signers table ----
        y = section_title("Signature Records", y)

        col_name = 22 * mm
        col_email = 72 * mm
        col_date = 122 * mm
        col_ip = 162 * mm

        # Table header
        c.setFillColor(BRAND_LIGHT)
        c.rect(20 * mm, y - 2 * mm, page_w - 40 * mm, 7 * mm, stroke=0, fill=1)
        c.setFillColor(BRAND_PRIMARY)
        c.setFont(FONT_BOLD, 7)
        c.drawString(col_name, y + 1 * mm, "Signer")
        c.drawString(col_email, y + 1 * mm, "Email")
        c.drawString(col_date, y + 1 * mm, "Signed At (UTC)")
        c.drawString(col_ip, y + 1 * mm, "IP Address")
        y -= 8 * mm

        for i, signer in enumerate(signers):
            if y < 30 * mm:
                c.showPage()
                y = page_h - 20 * mm

            bg = BRAND_LIGHT if i % 2 == 0 else colors.white
            c.setFillColor(bg)
            c.rect(20 * mm, y - 2 * mm, page_w - 40 * mm, 7 * mm, stroke=0, fill=1)

            c.setFillColor(BRAND_PRIMARY)
            c.setFont(FONT_REGULAR, 7)
            c.drawString(col_name, y + 1 * mm, str(signer.get("name", ""))[:28])
            c.drawString(col_email, y + 1 * mm, str(signer.get("email", ""))[:30])

            signed_at = signer.get("signed_at")
            if isinstance(signed_at, datetime):
                signed_str = signed_at.strftime("%d %b %Y %H:%M")
            else:
                signed_str = str(signed_at or "Pending")
            c.drawString(col_date, y + 1 * mm, signed_str)
            c.drawString(col_ip, y + 1 * mm, str(signer.get("ip_address", ""))[:18])
            y -= 7 * mm

        # ---- Integrity notice ----
        y -= 6 * mm
        if y < 50 * mm:
            c.showPage()
            y = page_h - 20 * mm

        y = section_title("Integrity & Legal Notice", y)
        notice = (
            "This manifest is an automatically generated record of the electronic signing process "
            "conducted via the Enwealth E-Board platform.  Each signature was captured with IP address "
            "logging, timestamp recording, and optional OTP verification.  The SHA-256 hashes above can "
            "be used to independently verify that the signed document has not been altered after signing. "
            "This record constitutes a legally traceable audit trail under applicable electronic "
            "transactions legislation."
        )
        text_obj = c.beginText(22 * mm, y)
        text_obj.setFont(FONT_REGULAR, 7.5)
        text_obj.setFillColor(BRAND_PRIMARY)
        for line in textwrap.wrap(notice, width=100):
            text_obj.textLine(line)
        c.drawText(text_obj)

        # ---- Footer ----
        c.setFillColor(BRAND_ACCENT)
        c.rect(0, 0, page_w, 10 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont(FONT_REGULAR, 7)
        c.drawString(
            20 * mm,
            3.5 * mm,
            f"Enwealth E-Board  |  {reference_number}  |  "
            f"Generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        )
        c.drawRightString(
            page_w - 20 * mm,
            3.5 * mm,
            "CONFIDENTIAL – This document contains legally binding signatures",
        )

        c.save()
        buf.seek(0)
        return buf.read()

    @classmethod
    def append_manifest(
        cls,
        signed_pdf_bytes: bytes,
        manifest_bytes: bytes,
    ) -> bytes:
        """Append a manifest PDF page to the end of the signed PDF."""
        writer = PdfWriter()

        # Add all pages from the signed PDF
        reader = PdfReader(io.BytesIO(signed_pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)

        # Add manifest pages
        manifest_reader = PdfReader(io.BytesIO(manifest_bytes))
        for page in manifest_reader.pages:
            writer.add_page(page)

        out = io.BytesIO()
        writer.write(out)
        out.seek(0)
        return out.read()

    @classmethod
    def generate_preview_png(
        cls,
        pdf_source: object,
        page_number: int = 1,
        dpi: int = 96,
        max_width: int = 800,
    ) -> bytes | None:
        """
        Return a PNG thumbnail of a PDF page.

        Requires ``pdf2image`` (``poppler``) to be available.
        Returns None gracefully if the dependency is absent.
        """
        try:
            from pdf2image import convert_from_bytes  # optional dependency
        except ImportError:
            logger.debug("pdf2image not available; skipping preview generation")
            return None

        try:
            pdf_bytes = (
                _load_image_bytes(pdf_source)
                if not isinstance(pdf_source, bytes)
                else pdf_source
            )
            images = convert_from_bytes(
                pdf_bytes,
                dpi=dpi,
                first_page=page_number,
                last_page=page_number,
            )
            if not images:
                return None
            img = images[0]
            # Resize if wider than max_width
            if img.width > max_width:
                ratio = max_width / img.width
                new_size = (max_width, int(img.height * ratio))
                img = img.resize(new_size, PILImage.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            buf.seek(0)
            return buf.read()
        except Exception as exc:
            logger.warning("Preview generation failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @classmethod
    def _apply_overlay(cls, pdf_bytes: bytes, stamp: SignatureStampData) -> bytes:
        """
        Merge a ReportLab overlay onto the target page of the PDF.
        """
        reader = PdfReader(io.BytesIO(pdf_bytes))
        total_pages = len(reader.pages)
        target_page_idx = stamp.placement.page_number - 1  # 0-based

        if target_page_idx < 0 or target_page_idx >= total_pages:
            raise PDFSigningError(
                f"Page {stamp.placement.page_number} does not exist "
                f"(document has {total_pages} page(s))"
            )

        target_page = reader.pages[target_page_idx]

        # Determine the page's media box dimensions
        media_box = target_page.mediabox
        page_width = float(media_box.width)
        page_height = float(media_box.height)

        # Build the overlay PDF
        overlay_bytes = _build_signature_overlay(page_width, page_height, stamp)
        overlay_reader = PdfReader(io.BytesIO(overlay_bytes))
        overlay_page = overlay_reader.pages[0]

        # Merge overlay onto target page (overlay is "on top")
        target_page.merge_page(overlay_page)

        # Write all pages (with the modified target page) to a new PDF
        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            writer.add_page(page)

        # Set document metadata / producer string
        writer.add_metadata(
            {
                "/Producer": "Enwealth E-Board Electronic Signing Service",
                "/Creator": "Enwealth E-Board",
                "/Subject": "Electronically Signed Document",
            }
        )

        out = io.BytesIO()
        writer.write(out)
        out.seek(0)
        return out.read()


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class PDFSigningError(Exception):
    """Raised when the PDF signing process fails for a recoverable reason."""


class IntegrityError(Exception):
    """Raised when a document's SHA-256 hash does not match the stored value."""
