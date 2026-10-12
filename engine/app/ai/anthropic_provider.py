"""AIProvider backed by Claude (Anthropic API).

Two narrow uses only, both returning schema-constrained JSON (structured outputs):
  * extract_bill      - transcribe candidate values printed on a utility bill (PDF or photo)
  * suggest_category  - pick one category id from a closed list, or none
Every result is a suggestion for a person to confirm. Nothing here computes an emissions number.
On refusals or API errors the provider degrades gracefully: an empty extraction (manual entry)
or no suggestion (rules only).
"""

from __future__ import annotations

import base64
import json
import logging

import anthropic

from app.ai.provider import BillExtraction, CategorySuggestion

log = logging.getLogger(__name__)

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"

BILL_SYSTEM = (
    "You transcribe values printed on Bangladeshi utility bills (electricity) for a carbon accounting "
    "platform. A person will review and correct every value before it is saved, so accuracy matters "
    "more than completeness. Copy only what is printed on the document. Never calculate, estimate or "
    "infer a value that is not printed; if a field is absent, unreadable or ambiguous, return null and "
    "explain in notes. Dates use YYYY-MM-DD. Numbers are plain digits with a decimal point and no "
    "thousands separators or units. 'quantity' is the electricity consumed in kWh for the billing "
    "period (not the meter reading, not demand in kW). If the consumption is printed in MWh, convert "
    "nothing: return null for quantity and say so in notes. Rate confidence per field: high when the "
    "value is clearly labelled and legible, medium when the label or reading is uncertain, low otherwise."
)

CATEGORY_SYSTEM = (
    "You map a customer's activity description to one emission-factor category for a carbon accounting "
    "platform. Choose only from the categories given. If none clearly fits, return null: a person will "
    "choose instead, so an honest null is better than a guess. Explain your choice in one short sentence."
)


def _nullable_string() -> dict:
    return {"anyOf": [{"type": "string"}, {"type": "null"}]}


class AnthropicProvider:
    name = "anthropic"
    available = True

    def __init__(self, api_key: str, model: str):
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=2, timeout=120.0)

    def _create(self, *, system: str, content: list, schema: dict, effort: str):
        """One structured-output request with server-side refusal fallback."""
        return self.client.beta.messages.create(
            model=self.model,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )

    @staticmethod
    def _json(response) -> dict | None:
        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None) if response.stop_details else None
            log.warning("AI request declined (category=%s)", category)
            return None
        if response.stop_reason == "max_tokens":
            log.warning("AI response truncated at max_tokens")
            return None
        text = next((b.text for b in response.content if b.type == "text"), None)
        return json.loads(text) if text else None

    # -- bill extraction --------------------------------------------------------------------
    def extract_bill(self, data: bytes, media_type: str, fields: dict[str, str]) -> BillExtraction:
        keys = list(fields)
        if media_type == "application/pdf":
            doc = {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.standard_b64encode(data).decode(),
                },
            }
        elif media_type in IMAGE_TYPES:
            doc = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.standard_b64encode(data).decode(),
                },
            }
        else:
            return BillExtraction(None, dict.fromkeys(keys), {}, f"Unsupported file type {media_type}.")
        field_list = "\n".join(f"- {k}: {label}" for k, label in fields.items())
        schema = {
            "type": "object",
            "properties": {
                "document_type": {"type": "string", "enum": ["electricity_bill", "other_utility_bill", "not_a_bill"]},
                "fields": {
                    "type": "object",
                    "properties": {k: _nullable_string() for k in keys},
                    "required": keys,
                    "additionalProperties": False,
                },
                "confidence": {
                    "type": "object",
                    "properties": {k: {"type": "string", "enum": ["high", "medium", "low"]} for k in keys},
                    "required": keys,
                    "additionalProperties": False,
                },
                "notes": _nullable_string(),
            },
            "required": ["document_type", "fields", "confidence", "notes"],
            "additionalProperties": False,
        }
        try:
            response = self._create(
                system=BILL_SYSTEM,
                content=[doc, {"type": "text", "text": f"Fields to transcribe:\n{field_list}"}],
                schema=schema,
                effort="medium",
            )
            out = self._json(response)
        except anthropic.APIConnectionError as exc:
            log.warning("AI extraction unavailable: %s", exc)
            return BillExtraction(
                None, dict.fromkeys(keys), {}, "The extraction service could not be reached; enter the values manually."
            )
        except anthropic.APIStatusError as exc:
            log.warning("AI extraction failed (%s): %s", exc.status_code, exc.message)
            return BillExtraction(
                None, dict.fromkeys(keys), {}, "Automatic extraction failed; enter the values manually."
            )
        if out is None:
            return BillExtraction(None, dict.fromkeys(keys), {}, "No values could be extracted; enter them manually.")
        return BillExtraction(
            out["document_type"], {k: out["fields"].get(k) for k in keys}, out.get("confidence", {}), out.get("notes")
        )

    # -- category suggestion ----------------------------------------------------------------
    def suggest_category(
        self, terminal_label: str, inputs: dict[str, str], options: list[dict[str, str]]
    ) -> CategorySuggestion | None:
        ids = [o["id"] for o in options]
        listing = "\n".join(f"- {o['id']}: {o['path']}" for o in options)
        described = "; ".join(f"{k}: {v}" for k, v in inputs.items())
        schema = {
            "type": "object",
            "properties": {
                "category_id": {"anyOf": [{"type": "string", "enum": ids}, {"type": "null"}]},
                "reason": {"type": "string"},
            },
            "required": ["category_id", "reason"],
            "additionalProperties": False,
        }
        try:
            response = self._create(
                system=CATEGORY_SYSTEM,
                content=[
                    {
                        "type": "text",
                        "text": f"Upload category: {terminal_label}\nCustomer input: {described}\n\n"
                        f"Categories:\n{listing}",
                    }
                ],
                schema=schema,
                effort="low",
            )
            out = self._json(response)
        except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
            log.warning("AI category suggestion unavailable: %s", exc)
            return None
        if not out or out.get("category_id") not in ids:
            return None
        return CategorySuggestion(out["category_id"], out.get("reason"))
