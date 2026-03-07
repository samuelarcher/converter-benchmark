from __future__ import annotations
import json
import time
from pathlib import Path
from .base import ConverterPlugin, ConversionResult

try:
    import pdfplumber
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


class PdfPlumberConverter(ConverterPlugin):
    name = "pdfplumber"
    label = "pdfplumber"
    supported_extensions = [".pdf"]
    supported_output_formats = ["text", "json"]

    def is_available(self) -> bool:
        return _AVAILABLE

    def convert(self, file_path: Path, output_format: str) -> ConversionResult:
        if output_format not in self.supported_output_formats:
            return self._unsupported(output_format)
        t0 = time.monotonic()
        try:
            with pdfplumber.open(str(file_path)) as pdf:
                if output_format == "text":
                    parts = []
                    for page in pdf.pages:
                        t = page.extract_text()
                        if t:
                            parts.append(t)
                    content = "\n\n".join(parts)
                else:  # json
                    pages = []
                    for i, page in enumerate(pdf.pages, 1):
                        text = page.extract_text() or ""
                        tables = page.extract_tables() or []
                        pages.append({"page": i, "text": text, "tables": tables})
                    content = json.dumps(pages, indent=2, ensure_ascii=False)
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
