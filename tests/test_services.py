"""Tests for the PromptLoader service.

Validates that Jinja2 templates are discovered, rendered with context
variables, and handle missing templates gracefully.
"""

import pytest

from documind.services.prompt_loader import PromptLoader


class TestPromptLoader:
    """Tests for the PromptLoader service."""

    def test_lists_all_templates(self, prompt_loader):
        """Should discover all three prompt templates."""
        templates = prompt_loader.list_templates()
        assert "rfp-summary.txt" in templates
        assert "contract-clauses.txt" in templates
        assert "spec-compliance.txt" in templates

    def test_renders_rfp_template(self, prompt_loader):
        """The RFP prompt should render with {{ document_text }}."""
        rendered = prompt_loader.render(
            "rfp-summary.txt",
            document_text="This is a test RFP.",
        )
        # The rendered prompt should contain our document text
        assert "This is a test RFP." in rendered
        # It should also contain the template instructions
        assert "Executive Summary" in rendered

    def test_renders_contract_template(self, prompt_loader):
        """The contract prompt should render correctly."""
        rendered = prompt_loader.render(
            "contract-clauses.txt",
            document_text="Service Agreement between A and B.",
        )
        assert "Service Agreement between A and B." in rendered
        assert "Parties" in rendered

    def test_renders_spec_template(self, prompt_loader):
        """The spec compliance prompt should render correctly."""
        rendered = prompt_loader.render(
            "spec-compliance.txt",
            document_text="System shall support 1000 concurrent users.",
        )
        assert "1000 concurrent users" in rendered
        assert "Completeness Score" in rendered

    def test_missing_template_raises(self, prompt_loader):
        """Should raise TemplateNotFound for non-existent templates."""
        from jinja2 import TemplateNotFound

        with pytest.raises(TemplateNotFound):
            prompt_loader.render("nonexistent.txt", document_text="test")
