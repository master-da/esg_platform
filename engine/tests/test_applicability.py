import pytest

from app.compliance.applicability import ConditionError, evaluate, fields

ORANGE_50 = {
    "all": [
        {"field": "facility.environmental_classification", "op": "in", "value": ["ORANGE", "RED"]},
        {"field": "facility.employee_count", "op": "gte", "value": 50},
    ]
}


def test_all_conditions_must_hold():
    ok, why = evaluate(ORANGE_50, {"facility": {"environmental_classification": "RED", "employee_count": 1850}})
    assert ok and "facility.environmental_classification = RED" in why
    assert not evaluate(ORANGE_50, {"facility": {"environmental_classification": "GREEN", "employee_count": 1850}})[0]
    assert not evaluate(ORANGE_50, {"facility": {"environmental_classification": "RED", "employee_count": None}})[0]


def test_any_and_not():
    cond = {
        "any": [
            {"field": "company.sector_code", "op": "eq", "value": "PHARMA"},
            {"not": {"field": "company.company_size_code", "op": "in", "value": ["MICRO", "SMALL"]}},
        ]
    }
    assert evaluate(cond, {"company": {"sector_code": "TEXTILES_APPAREL", "company_size_code": "LARGE"}})[0]
    assert not evaluate(cond, {"company": {"sector_code": "TEXTILES_APPAREL", "company_size_code": "SMALL"}})[0]


def test_empty_all_applies_universally():
    assert evaluate({"all": []}, {})[0]


def test_unknown_operator_is_rejected():
    with pytest.raises(ConditionError):
        evaluate({"field": "company.x", "op": "like", "value": 1}, {})


def test_fields_lists_referenced_fields():
    assert fields(ORANGE_50) == {"facility.environmental_classification", "facility.employee_count"}
