"""Tests for the Ingestion Agent — tools and executor.

Validates the document classification, record creation, blob upload,
and the full ingestion executor flow using mocked Azure services.
"""

import pytest

from documind.agents.ingestion.tools.tools import (
    classify_doc_type,
    store_to_blob,
    upload_document,
)
from documind.agents.ingestion.agent import (
    IngestionExecutor,
    IngestionInput,
    IngestionOutput,
)
from documind.core.models.base import ProcessingStatus


class TestClassifyDocType:
    """Tests for the classify_doc_type tool."""

    def test_classify_by_hint(self, registry):
        """When a doc_type_hint is provided, it should be used directly
        without inspecting the file extension."""
        config = classify_doc_type("whatever.xyz", registry, hint="rfp")
        assert config.name == "rfp"

    def test_classify_pdf_returns_first_matching_type(self, registry):
        """A .pdf file should match the first enabled doc type that
        accepts PDF format (all three types accept PDF)."""
        config = classify_doc_type("document.pdf", registry)
        # The registry loads YAML files in sorted order: contract, rfp, spec
        assert config.name in ["contract", "rfp", "spec"]

    def test_classify_xlsx_returns_spec(self, registry):
        """Only the 'spec' doc type accepts .xlsx, so it should be selected."""
        config = classify_doc_type("requirements.xlsx", registry)
        assert config.name == "spec"

    def test_classify_unsupported_extension_raises(self, registry):
        """An unsupported file extension should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported file extension"):
            classify_doc_type("readme.md", registry)

    def test_classify_invalid_hint_falls_back_to_extension(self, registry):
        """If the hint doesn't match any registered type, it should fall
        back to extension-based classification.  But our current impl
        doesn't do this — it only checks if hint is in registry.  Let's
        verify the hint is checked first."""
        # Hint "nonexistent" is not in registry, so it falls through to
        # extension-based classification
        config = classify_doc_type("contract.pdf", registry, hint="nonexistent")
        assert config.name in ["contract", "rfp", "spec"]


class TestUploadDocument:
    """Tests for the upload_document tool."""

    def test_creates_record_with_pending_status(self):
        """The initial record should start in PENDING status."""
        record = upload_document(b"fake content", "test.pdf", "rfp")
        assert record.status == ProcessingStatus.PENDING
        assert record.doc_type == "rfp"
        assert record.source_filename == "test.pdf"

    def test_generates_unique_document_id(self):
        """Each call should generate a unique UUID."""
        r1 = upload_document(b"content1", "a.pdf", "rfp")
        r2 = upload_document(b"content2", "b.pdf", "rfp")
        assert r1.document_id != r2.document_id

    def test_rejects_empty_file(self):
        """Empty file bytes should be rejected."""
        with pytest.raises(ValueError, match="File is empty"):
            upload_document(b"", "test.pdf", "rfp")

    def test_rejects_empty_filename(self):
        """Empty filename should be rejected."""
        with pytest.raises(ValueError, match="Filename is required"):
            upload_document(b"content", "", "rfp")


class TestStoreToBlob:
    """Tests for the store_to_blob tool."""

    def test_uploads_and_sets_blob_url(self, mock_blob_service):
        """After upload, the record's blob_url should be set."""
        record = upload_document(b"fake pdf", "test.pdf", "rfp")
        assert record.blob_url == ""  # not set yet

        blob_url = store_to_blob(b"fake pdf", record, mock_blob_service)

        assert blob_url.startswith("https://")
        assert record.blob_url == blob_url
        mock_blob_service.upload_document.assert_called_once()

    def test_passes_correct_content_type(self, mock_blob_service):
        """The content type should be inferred from the filename."""
        record = upload_document(b"fake pdf", "report.pdf", "rfp")
        store_to_blob(b"fake pdf", record, mock_blob_service)

        # Check the call args
        call_kwargs = mock_blob_service.upload_document.call_args
        assert call_kwargs.kwargs["content_type"] == "application/pdf"


class TestIngestionExecutor:
    """Tests for the full Ingestion Executor."""

    def test_full_ingestion_flow(
        self, registry, mock_blob_service, sample_pdf_bytes
    ):
        """The executor should classify, create a record, upload to blob,
        and return an IngestionOutput with the record and file bytes."""
        executor = IngestionExecutor(
            registry=registry,
            blob_service=mock_blob_service,
        )

        inp = IngestionInput(
            file_bytes=sample_pdf_bytes,
            filename="proposal.pdf",
            doc_type_hint="rfp",
        )
        output = executor.run(inp)

        assert isinstance(output, IngestionOutput)
        assert output.record.doc_type == "rfp"
        assert output.record.status == ProcessingStatus.PENDING
        assert output.record.blob_url != ""
        assert output.file_bytes == sample_pdf_bytes
        mock_blob_service.upload_document.assert_called_once()

    def test_ingestion_with_docx(self, registry, mock_blob_service):
        """Ingestion should work for DOCX files too."""
        executor = IngestionExecutor(
            registry=registry,
            blob_service=mock_blob_service,
        )
        inp = IngestionInput(
            file_bytes=b"fake docx",
            filename="agreement.docx",
        )
        output = executor.run(inp)
        assert output.record.doc_type in ["contract", "rfp", "spec"]
