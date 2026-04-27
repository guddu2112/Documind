"""Tests for Cosmos DB vector index setup.

Validates that:
    - ensure_search_container() creates a container with vector index config.
    - The function is idempotent (no error on second call).
    - Container settings include DiskANN vector index and composite indexes.
"""

import pytest
from unittest.mock import MagicMock, patch, call

from documind.services.cosmos_vector_setup import ensure_search_container


def _make_mock_client():
    """Build a mock CosmosClient → database → container chain."""
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_container = MagicMock()
    mock_client.create_database_if_not_exists.return_value = mock_db
    mock_db.create_container_if_not_exists.return_value = mock_container
    return mock_client, mock_db, mock_container


class TestEnsureSearchContainer:
    """Tests for the ensure_search_container function."""

    def test_creates_container_with_correct_id(self):
        """Should create a container named 'search_index'."""
        mock_client, mock_db, _ = _make_mock_client()

        ensure_search_container(client=mock_client, database_name="test-db")

        mock_db.create_container_if_not_exists.assert_called_once()
        call_kwargs = mock_db.create_container_if_not_exists.call_args[1]
        assert call_kwargs["id"] == "search_index"

    def test_uses_doc_type_partition_key(self):
        """Should use /doc_type as the partition key path."""
        mock_client, mock_db, _ = _make_mock_client()

        ensure_search_container(client=mock_client, database_name="test-db")

        call_kwargs = mock_db.create_container_if_not_exists.call_args[1]
        pk = call_kwargs["partition_key"]
        # Partition key is passed as a dict with 'paths' containing '/doc_type'
        assert pk["paths"] == ["/doc_type"]

    def test_includes_vector_embedding_policy(self):
        """Should include a vector embedding policy for DiskANN."""
        mock_client, mock_db, _ = _make_mock_client()

        ensure_search_container(client=mock_client, database_name="test-db")

        call_kwargs = mock_db.create_container_if_not_exists.call_args[1]
        vector_policy = call_kwargs["vector_embedding_policy"]

        assert "vectorEmbeddings" in vector_policy
        embeddings = vector_policy["vectorEmbeddings"]
        assert len(embeddings) == 1
        assert embeddings[0]["path"] == "/embedding"
        assert embeddings[0]["dimensions"] == 1536
        assert embeddings[0]["distanceFunction"] == "cosine"
        assert embeddings[0]["dataType"] == "float32"

    def test_custom_container_name(self):
        """Should allow overriding the container name."""
        mock_client, mock_db, _ = _make_mock_client()

        ensure_search_container(
            client=mock_client,
            database_name="test-db",
            container_name="my_vectors",
        )

        call_kwargs = mock_db.create_container_if_not_exists.call_args[1]
        assert call_kwargs["id"] == "my_vectors"

    def test_indexing_policy_excludes_embedding(self):
        """The indexing policy should exclude /embedding/* from default index."""
        mock_client, mock_db, _ = _make_mock_client()

        ensure_search_container(client=mock_client, database_name="test-db")

        call_kwargs = mock_db.create_container_if_not_exists.call_args[1]
        indexing = call_kwargs["indexing_policy"]
        excluded_paths = [p["path"] for p in indexing["excludedPaths"]]
        assert "/embedding/*" in excluded_paths

    def test_indexing_policy_has_diskann_vector_index(self):
        """The indexing policy should include a diskANN vector index."""
        mock_client, mock_db, _ = _make_mock_client()

        ensure_search_container(client=mock_client, database_name="test-db")

        call_kwargs = mock_db.create_container_if_not_exists.call_args[1]
        indexing = call_kwargs["indexing_policy"]
        vector_indexes = indexing["vectorIndexes"]
        assert len(vector_indexes) == 1
        assert vector_indexes[0]["path"] == "/embedding"
        assert vector_indexes[0]["type"] == "diskANN"

    def test_creates_database_if_not_exists(self):
        """Should call create_database_if_not_exists with the database name."""
        mock_client, _, _ = _make_mock_client()

        ensure_search_container(client=mock_client, database_name="my-cosmos-db")

        mock_client.create_database_if_not_exists.assert_called_once_with(id="my-cosmos-db")

    def test_idempotent_on_existing_container(self):
        """create_container_if_not_exists should not raise if container exists."""
        mock_client, mock_db, _ = _make_mock_client()

        # Call twice — should not raise
        ensure_search_container(client=mock_client, database_name="test-db")
        ensure_search_container(client=mock_client, database_name="test-db")

        assert mock_db.create_container_if_not_exists.call_count == 2
