"""Search module facade combining exact SQL queries and vector similarity."""

from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.vector.local import LocalVectorIndex, VectorDocument, VectorMatch
from app.application.query_forms import FormFilters, FormTrace, QueryForms, SearchResult


class SearchFacade:
    """Search boundary backed by the exact query service and vector index."""

    def __init__(
        self,
        repository: SqlAlchemyFormRepository,
        vector_index: LocalVectorIndex | None = None,
    ) -> None:
        self._queries = QueryForms(repository)
        self._vector = vector_index or LocalVectorIndex()

    # --- Exact SQL search ---

    def search(self, filters: FormFilters) -> list[SearchResult]:
        """Search forms by exact field filters (form_id, employee_id, etc.)."""
        return self._queries.search(filters)

    def trace(self, form_id: str) -> FormTrace:
        """Retrieve the full audit trail for a single form."""
        return self._queries.trace(form_id)

    # --- Vector similarity search ---

    def add_document(self, document: VectorDocument) -> None:
        """Index a document for vector similarity search."""
        self._vector.add(document)

    def vector_search(self, query: str, *, limit: int = 10) -> list[VectorMatch]:
        """Search indexed documents by character-bigram cosine similarity."""
        return self._vector.search(query, limit=limit)

    def list_documents(self) -> list[VectorDocument]:
        """Return all currently indexed documents."""
        return list(self._vector._documents.values())
