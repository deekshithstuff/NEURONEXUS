"""Text helpers shared by the document pipelines."""

from __future__ import annotations

import re

# Characters that XML 1.0 (and therefore python-docx/lxml) cannot represent.
# This includes NUL bytes, most C0 control characters, UTF-16 surrogates and
# the Unicode noncharacters that ``lxml`` rejects.
_XML_INCOMPATIBLE = re.compile(
    "["
    "\x00-\x08"
    "\x0b\x0c"
    "\x0e-\x1f"
    "\ud800-\udfff"
    "\ufdd0-\ufdef"
    "\ufffe\uffff"
    "\U0001fffe\U0001ffff"
    "\U0002fffe\U0002ffff"
    "\U0003fffe\U0003ffff"
    "\U0004fffe\U0004ffff"
    "\U0005fffe\U0005ffff"
    "\U0006fffe\U0006ffff"
    "\U0007fffe\U0007ffff"
    "\U0008fffe\U0008ffff"
    "\U0009fffe\U0009ffff"
    "\U000afffe\U000affff"
    "\U000bfffe\U000bffff"
    "\U000cfffe\U000cffff"
    "\U000dfffe\U000dffff"
    "\U000efffe\U000effff"
    "\U000ffffe\U000fffff"
    "\U0010fffe\U0010ffff"
    "]"
)


def sanitize_xml_text(value: object) -> str:
    """Return *value* as a string stripped of XML-incompatible characters.

    ``python-docx`` and ``lxml`` raise ``ValueError`` ("All strings must be XML
    compatible: Unicode or ASCII, no NULL bytes or control characters") when text
    containing NUL bytes or other control characters is written to a document.
    Removing them lets messy PDF/OCR text be imported instead of failing the
    whole upload. Legitimate whitespace (tab, newline, carriage return) is kept.
    """

    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    return _XML_INCOMPATIBLE.sub("", text)
