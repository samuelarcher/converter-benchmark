from __future__ import annotations
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from .base import ConverterPlugin, ConversionResult

try:
    from markdownify import markdownify
    _MARKDOWNIFY = True
except ImportError:
    _MARKDOWNIFY = False


def _lo_available() -> bool:
    return shutil.which("soffice") is not None


def _strip_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class LibreOfficeConverter(ConverterPlugin):
    name = "libreoffice"
    label = "LibreOffice"
    supported_extensions = [
        ".docx", ".doc", ".odt", ".rtf", ".pptx", ".ppt", ".xlsx", ".xls", ".ods",
    ]
    supported_output_formats = ["markdown", "html", "text"]

    def is_available(self) -> bool:
        return _lo_available()

    def convert(self, file_path: Path, output_format: str) -> ConversionResult:
        if output_format not in self.supported_output_formats:
            return self._unsupported(output_format)
        t0 = time.monotonic()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                proc = subprocess.run(
                    [
                        "soffice", "--headless",
                        "--convert-to", "html",
                        "--outdir", tmpdir,
                        str(file_path),
                    ],
                    capture_output=True, text=True, timeout=120,
                )
                if proc.returncode != 0:
                    return ConversionResult(
                        converter_name=self.name,
                        output_format=output_format,
                        error=proc.stderr.strip() or f"soffice exited {proc.returncode}",
                        duration_ms=int((time.monotonic() - t0) * 1000),
                    )
                html_files = list(Path(tmpdir).glob("*.html"))
                if not html_files:
                    return ConversionResult(
                        converter_name=self.name,
                        output_format=output_format,
                        error="No HTML output from LibreOffice",
                        duration_ms=int((time.monotonic() - t0) * 1000),
                    )
                html = html_files[0].read_text(encoding="utf-8", errors="replace")

            if output_format == "html":
                content = html
            elif output_format == "markdown" and _MARKDOWNIFY:
                content = markdownify(html)
            elif output_format == "markdown":
                content = _strip_tags(html)
            else:  # text
                content = _strip_tags(html)

            return ConversionResult(
                converter_name=self.name,
                output_format=output_format,
                content=content,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        except subprocess.TimeoutExpired:
            return ConversionResult(
                converter_name=self.name,
                output_format=output_format,
                error="LibreOffice timed out after 120s",
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        except Exception as exc:
            return ConversionResult(
                converter_name=self.name,
                output_format=output_format,
                error=str(exc),
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
