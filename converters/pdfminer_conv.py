from __future__ import annotations
import time
from pathlib import Path
from .base import ConverterPlugin, ConversionResult

try:
    from pdfminer.high_level import extract_text
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


class PdfMinerConverter(ConverterPlugin):
    name = "pdfminer"
    label = "pdfminer.six"
    supported_extensions = [".pdf"]
    supported_output_formats = ["text"]

    def is_available(self) -> bool:
        return _AVAILABLE

    def convert(self, file_path: Path, output_format: str) -> ConversionResult:
        if output_format not in self.supported_output_formats:
            return self._unsupported(output_format)
        t0 = time.monotonic()
        try:
            text = extract_text(str(file_path))
            return ConversionResult(
                converter_name=self.name,
                output_format=output_format,
                content=text or "",
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        except Exception as exc:
            return ConversionResult(
                converter_name=self.name,
                output_format=output_format,
                error=str(exc),
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
