from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

OUTPUT_FORMATS = ["markdown", "html", "text", "json"]


@dataclass
class ConversionResult:
    converter_name: str
    output_format: str
    content: str = ""
    error: Optional[str] = None
    duration_ms: int = 0


class ConverterPlugin:
    name: str = ""
    label: str = ""
    supported_extensions: list[str] = []
    supported_output_formats: list[str] = []

    def convert(self, file_path: Path, output_format: str) -> ConversionResult:
        raise NotImplementedError

    def is_available(self) -> bool:
        return True

    def _unsupported(self, output_format: str) -> ConversionResult:
        return ConversionResult(
            converter_name=self.name,
            output_format=output_format,
            error=f"Unsupported output format: {output_format}",
        )
