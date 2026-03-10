from __future__ import annotations
import time
from pathlib import Path
from .base import ConverterPlugin, ConversionResult

try:
    import mammoth
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


class MammothConverter(ConverterPlugin):
    name = "mammoth"
    label = "Mammoth"
    supported_extensions = [".docx"]
    supported_output_formats = ["html", "markdown"]

    def is_available(self) -> bool:
        return _AVAILABLE

    def convert(self, file_path: Path, output_format: str) -> ConversionResult:
        if output_format not in self.supported_output_formats:
            return self._unsupported(output_format)
        t0 = time.monotonic()
        try:
            with open(file_path, "rb") as f:
                if output_format == "html":
                    result = mammoth.convert_to_html(f)
                else:
                    result = mammoth.convert_to_markdown(f)
            return ConversionResult(
                converter_name=self.name,
                output_format=output_format,
                content=result.value,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        except Exception as exc:
            return ConversionResult(
                converter_name=self.name,
                output_format=output_format,
                error=str(exc),
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
