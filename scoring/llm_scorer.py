"""LLM scoring via Claude API."""
from __future__ import annotations
import json
import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

try:
    import anthropic
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False

_CLIENT = None


def _get_client():

    global _CLIENT
    if _CLIENT is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        _CLIENT = anthropic.Anthropic(api_key=api_key)
    
    return _CLIENT

MODEL = "claude-sonnet-4-6"

RUBRICS = {
    "markdown": [
        "content_completeness",
        "structure_preservation",
        "table_accuracy",
        "formatting_fidelity",
        "readability",
        "overall",
    ],
    "html": [
        "content_completeness",
        "structure_preservation",
        "table_accuracy",
        "formatting_fidelity",
        "readability",
        "overall",
    ],
    "text": [
        "content_completeness",
        "readability",
        "overall",
    ],
    "json": [
        "content_completeness",
        "schema_consistency",
        "table_accuracy",
        "overall",
    ],
}


def _rubric_keys(output_format: str) -> list[str]:
    return RUBRICS.get(output_format, RUBRICS["text"])


def score_conversion(
    converted_content: str,
    output_format: str,
    reference_text: str,
    converter_name: str,
    filename: str,
) -> dict:
    """Call Claude to score a single conversion. Returns rubric dict with scores 1-5."""
    if not _AVAILABLE or not converted_content.strip():
        return {}

    keys = _rubric_keys(output_format)
    keys_json = json.dumps(keys)

    prompt = f"""You are evaluating a file converter's output quality.

File: {filename}
Converter: {converter_name}
Output format: {output_format}

=== REFERENCE (plain text baseline) ===
{reference_text[:4000]}

=== CONVERTER OUTPUT ===
{converted_content[:4000]}

Score the converter output on each criterion from 1 (very poor) to 5 (excellent).
Respond with ONLY a valid JSON object using these keys: {keys_json}
Each value must be an integer 1-5. No extra keys, no explanation outside JSON.
Example: {{"content_completeness": 4, "readability": 3, "overall": 4}}"""

    try:
        msg = _get_client().messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        # Extract JSON even if wrapped in markdown code fence
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        rubric = json.loads(text)
        # Validate and clamp
        result = {}
        for k in keys:
            v = rubric.get(k)
            if isinstance(v, (int, float)):
                result[k] = max(1, min(5, int(v)))
        return result
    except Exception as exc:
        log.error("LLM scoring failed for %s/%s: %s", converter_name, output_format, exc)
        return {}


def score_all_conversions(
    conversions: list[dict],
    filename: str,
) -> dict[int, tuple[dict, int]]:
    """
    Score all conversions for a document.
    Returns mapping of conversion_id -> (rubric_dict, overall_score).
    Uses pdfminer plain-text as reference baseline; falls back to first non-empty conversion.
    """
    if not _AVAILABLE:
        log.warning("Anthropic client not available (check ANTHROPIC_API_KEY)")
        return {}

    # Find reference text
    reference_text = ""
    for c in conversions:
        if c["converter_name"] == "pdfminer" and c["output_format"] == "text":
            reference_text = c["content"] or ""
            break
    if not reference_text:
        for c in conversions:
            if c["content"]:
                reference_text = c["content"]
                break

    results = {}
    for c in conversions:
        content = c["content"] or ""
        if not content.strip():
            continue
        rubric = score_conversion(
            converted_content=content,
            output_format=c["output_format"],
            reference_text=reference_text,
            converter_name=c["converter_name"],
            filename=filename,
        )
        if rubric:
            overall = rubric.get("overall", sum(rubric.values()) // len(rubric))
            results[c["id"]] = (rubric, overall)
    return results
