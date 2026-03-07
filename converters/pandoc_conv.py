from __future__ import annotations
import subprocess
import shutil
import time
from pathlib import Path
from .base import ConverterPlugin, ConversionResult


def _pandoc_available() -> bool:
    return shutil.which("pandoc") is not None


class PandocConverter(ConverterPlugin):
    name = "pandoc"
    label = "Pandoc"
    supported_extensions = [
        ".docx", ".doc", ".odt", ".rtf", ".html", ".htm",
        ".epub", ".tex", ".md", ".txt", ".rst",
    ]
    supported_output_formats = ["markdown", "html", "text"]

    def is_available(self) -> bool:
        return _pandoc_available()

    def convert(self, file_path: Path, output_format: str) -> ConversionResult:
        if output_format not in self.supported_output_formats:
            return self._unsupported(output_format)
        format_map = {
            "markdown": "markdown",
            "html": "html",
            "text": "plain",
        }
        target = format_map[output_format]
        cmd = ["pandoc", str(file_path), "-t", target]
        if output_format == "markdown":
            cmd += ["--wrap=none"]
        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60
            )
            if proc.returncode != 0:
                return ConversionResult(
                    converter_name=self.name,
                    output_format=output_format,
                    error=proc.stderr.strip() or f"pandoc exited {proc.returncode}",
                    duration_ms=int((time.monotonic() - t0) * 1000),
                )
            return ConversionResult(
                converter_name=self.name,
                output_format=output_format,
                content=proc.stdout,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        except subprocess.TimeoutExpired:
            return ConversionResult(
                converter_name=self.name,
                output_format=output_format,
                error="pandoc timed out after 60s",
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        except Exception as exc:
            return ConversionResult(
                converter_name=self.name,
                output_format=output_format,
                error=str(exc),
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
