"""AnthropicProvider response handling without network calls (refusals, truncation, closed option lists)."""

from types import SimpleNamespace

from app.ai.anthropic_provider import AnthropicProvider


def response(text=None, stop_reason="end_turn"):
    content = [SimpleNamespace(type="text", text=text)] if text is not None else []
    return SimpleNamespace(stop_reason=stop_reason, stop_details=None, content=content)


def provider(resp):
    p = AnthropicProvider.__new__(AnthropicProvider)
    p.model = "claude-opus-5-5"
    p._create = lambda **_: resp
    return p


def test_refusal_degrades_to_manual_entry():
    out = provider(response(stop_reason="refusal")).extract_bill(b"%PDF", "application/pdf", {"quantity": "kWh"})
    assert out.document_type is None and out.fields == {"quantity": None}


def test_extraction_maps_fields():
    text = (
        '{"document_type": "electricity_bill", "fields": {"quantity": "125000"}, '
        '"confidence": {"quantity": "high"}, "notes": null}'
    )
    out = provider(response(text)).extract_bill(b"%PDF", "application/pdf", {"quantity": "kWh"})
    assert out.fields == {"quantity": "125000"} and out.confidence == {"quantity": "high"}


def test_unsupported_media_type_is_not_sent():
    out = provider(None).extract_bill(b"x", "text/plain", {"quantity": "kWh"})
    assert out.document_type is None


def test_category_must_come_from_the_options():
    opts = [{"id": "a", "path": "X"}, {"id": "b", "path": "Y"}]
    assert provider(response('{"category_id": "b", "reason": "r"}')).suggest_category("t", {}, opts).node_id == "b"
    assert provider(response('{"category_id": "zzz", "reason": "r"}')).suggest_category("t", {}, opts) is None
    assert provider(response('{"category_id": null, "reason": "r"}')).suggest_category("t", {}, opts) is None
    assert provider(response(stop_reason="max_tokens")).suggest_category("t", {}, opts) is None
