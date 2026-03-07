from __future__ import annotations
import re
import time
from pathlib import Path
from .base import ConverterPlugin, ConversionResult

try:
    from markitdown import MarkItDown
    _CLIENT = MarkItDown()
    _AVAILABLE = True
except Exception:
    _CLIENT = None
    _AVAILABLE = False


class MarkItDownConverter(ConverterPlugin):
    name = "markitdown"
    label = "MarkItDown"
    supported_extensions = [
        ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
        ".html", ".htm", ".txt", ".csv", ".json", ".xml", ".zip",
        ".epub", ".md",
    ]
    supported_output_formats = ["markdown", "text"]

    def is_available(self) -> bool:
        return _AVAILABLE

    def convert(self, file_path: Path, output_format: str) -> ConversionResult:
        if output_format not in self.supported_output_formats:
            return self._unsupported(output_format)
        t0 = time.monotonic()
        try:
            result = _CLIENT.convert(str(file_path))
            md = result.text_content or ""
            if output_format == "text":
                content = _strip_markdown(md)
            else:
                content = md
            return ConversionResult(
                converter_name=self.name,
                output_format=output_format,
                content=content,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        except Exception as exc:
            return ConversionResult(
                converter_name=self.name,
                output_format=output_format,
                error=str(exc),
                duration_ms=int((time.monotonic() - t0) * 1000),
            )


def _strip_markdown(text: str) -> str:
    """Naively strip common markdown syntax."""
    # Remove headings
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}(.+?)_{1,3}", r"\1", text)
    # Remove inline code
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Remove links
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    # Remove images
    text = re.sub(r"!\[.*?\]\(.+?\)", "", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Remove blockquotes
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    return text.strip()
