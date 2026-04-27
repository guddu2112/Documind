"""Tests for structured output schemas.

Validates that:
    - All registered schemas are valid JSON Schema dicts.
    - Schema lookup works for known doc-type + task combinations.
    - Unknown combinations return None (graceful fallback).
    - Schemas have the required structure for GPT-4o response_format.
"""

import pytest
from documind.core.schemas import (
    get_response_schema,
    list_registered_schemas,
    _SCHEMA_REGISTRY,
)


class TestSchemaRegistry:
    """Tests for the schema registry itself."""

    def test_registry_has_three_entries(self):
        """Should have schemas for rfp/summarize, contract/extract_clauses,
        spec/compliance_check."""
        expected = {
            ("rfp", "summarize"),
            ("contract", "extract_clauses"),
            ("spec", "compliance_check"),
        }
        actual = set(_SCHEMA_REGISTRY.keys())
        assert actual == expected

    def test_list_registered_returns_all_keys(self):
        """list_registered_schemas should return the same keys as the registry."""
        result = list_registered_schemas()
        assert len(result) == 3
        assert set(result) == set(_SCHEMA_REGISTRY.keys())


class TestGetResponseSchema:
    """Tests for the get_response_schema function."""

    @pytest.mark.parametrize(
        "doc_type,task",
        [
            ("rfp", "summarize"),
            ("contract", "extract_clauses"),
            ("spec", "compliance_check"),
        ],
    )
    def test_known_pair_returns_schema(self, doc_type, task):
        """Known doc_type + task should return a non-None schema dict."""
        schema = get_response_schema(doc_type, task)
        assert schema is not None
        assert isinstance(schema, dict)

    def test_unknown_pair_returns_none(self):
        """Unknown combination should return None for graceful fallback."""
        schema = get_response_schema("invoice", "parse")
        assert schema is None

    def test_case_sensitive_lookup(self):
        """Schema lookup should be case-sensitive (matches YAML config)."""
        assert get_response_schema("RFP", "summarize") is None
        assert get_response_schema("rfp", "Summarize") is None


class TestSchemaStructure:
    """Tests that schemas have the correct structure for GPT-4o."""

    @pytest.mark.parametrize(
        "doc_type,task",
        [
            ("rfp", "summarize"),
            ("contract", "extract_clauses"),
            ("spec", "compliance_check"),
        ],
    )
    def test_schema_has_json_schema_format(self, doc_type, task):
        """Each schema should have type='json_schema' and a json_schema key."""
        schema = get_response_schema(doc_type, task)

        assert schema["type"] == "json_schema"
        assert "json_schema" in schema
        assert "name" in schema["json_schema"]
        assert "strict" in schema["json_schema"]
        assert schema["json_schema"]["strict"] is True
        assert "schema" in schema["json_schema"]

    @pytest.mark.parametrize(
        "doc_type,task",
        [
            ("rfp", "summarize"),
            ("contract", "extract_clauses"),
            ("spec", "compliance_check"),
        ],
    )
    def test_schema_has_required_fields(self, doc_type, task):
        """The inner schema should have 'required' and 'properties' keys."""
        schema = get_response_schema(doc_type, task)
        inner = schema["json_schema"]["schema"]

        assert inner["type"] == "object"
        assert "properties" in inner
        assert "required" in inner
        assert isinstance(inner["required"], list)
        assert len(inner["required"]) > 0

    @pytest.mark.parametrize(
        "doc_type,task",
        [
            ("rfp", "summarize"),
            ("contract", "extract_clauses"),
            ("spec", "compliance_check"),
        ],
    )
    def test_schema_disallows_additional_properties(self, doc_type, task):
        """All schemas should have additionalProperties: false for strict mode."""
        schema = get_response_schema(doc_type, task)
        inner = schema["json_schema"]["schema"]
        assert inner["additionalProperties"] is False

    def test_rfp_schema_has_expected_fields(self):
        """RFP summary schema should have all expected fields."""
        schema = get_response_schema("rfp", "summarize")
        props = schema["json_schema"]["schema"]["properties"]

        expected_fields = [
            "executive_summary",
            "mandatory_requirements",
            "optional_requirements",
            "evaluation_criteria",
            "key_dates",
            "budget_range",
            "risks",
        ]
        for field in expected_fields:
            assert field in props, f"Missing field: {field}"

    def test_contract_schema_has_clauses(self):
        """Contract clauses schema should include a 'clauses' array."""
        schema = get_response_schema("contract", "extract_clauses")
        props = schema["json_schema"]["schema"]["properties"]

        assert "clauses" in props
        assert props["clauses"]["type"] == "array"
        # Each clause should have risk_level
        clause_props = props["clauses"]["items"]["properties"]
        assert "risk_level" in clause_props

    def test_spec_schema_has_scores(self):
        """Spec compliance schema should include scoring fields."""
        schema = get_response_schema("spec", "compliance_check")
        props = schema["json_schema"]["schema"]["properties"]

        assert "completeness_score" in props
        assert props["completeness_score"]["type"] == "number"
        assert "clarity_score" in props
        assert props["clarity_score"]["type"] == "number"

    def test_risk_item_has_severity_enum(self):
        """Risk items should have severity as an enum."""
        schema = get_response_schema("rfp", "summarize")
        risk_items_schema = schema["json_schema"]["schema"]["properties"]["risks"]["items"]

        assert "severity" in risk_items_schema["properties"]
        severity = risk_items_schema["properties"]["severity"]
        assert severity["type"] == "string"
        assert "enum" in severity
        assert set(severity["enum"]) == {"low", "medium", "high", "critical"}
