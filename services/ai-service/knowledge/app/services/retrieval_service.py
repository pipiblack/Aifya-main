"""
Retrieval service using Qdrant for vector similarity search.
All queries are scoped by facility_id for multi-tenant isolation.
"""

import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from structlog import get_logger

from app.config import get_settings
from app.services.embedding_service import embed_query

logger = get_logger(__name__)
settings = get_settings()

_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """
    Get or create the Qdrant client singleton.

    @returns QdrantClient instance
    """
    global _client
    if _client is None:
        _client = QdrantClient(
            url=settings.qdrant_endpoint,
            api_key=settings.qdrant_api_key,
            timeout=30.0,
        )
    return _client


async def ensure_collection() -> None:
    """
    Create the Qdrant collection if it doesn't exist.
    Uses cosine similarity for BGE-M3 normalized embeddings.
    """
    client = get_qdrant_client()
    collections = client.get_collections().collections
    existing = {c.name for c in collections}

    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=qmodels.VectorParams(
                size=settings.embedding_dimension,
                distance=qmodels.Distance.COSINE,
            ),
        )

        client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="facility_id",
            field_schema=qmodels.PayloadSchemaType.KEYWORD,
        )
        client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="document_id",
            field_schema=qmodels.PayloadSchemaType.KEYWORD,
        )
        client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="category",
            field_schema=qmodels.PayloadSchemaType.KEYWORD,
        )
        client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="department",
            field_schema=qmodels.PayloadSchemaType.KEYWORD,
        )

        logger.info(
            "qdrant_collection_created",
            collection=settings.qdrant_collection,
            dimension=settings.embedding_dimension,
        )
    else:
        logger.info(
            "qdrant_collection_exists",
            collection=settings.qdrant_collection,
        )


def upsert_vectors(
    points: list[dict],
) -> None:
    """
    Upsert embedding vectors with metadata payloads into Qdrant.

    @param points: List of dicts with keys: id, vector, payload
                   payload must include facility_id, document_id, category,
                   chunk_index, text, page_number, section_title, document_title
    """
    client = get_qdrant_client()

    qdrant_points = [
        qmodels.PointStruct(
            id=p["id"],
            vector=p["vector"],
            payload=p["payload"],
        )
        for p in points
    ]

    batch_size = 100
    for i in range(0, len(qdrant_points), batch_size):
        batch = qdrant_points[i : i + batch_size]
        client.upsert(
            collection_name=settings.qdrant_collection,
            points=batch,
        )
        logger.debug("qdrant_upsert_batch", start=i, count=len(batch))


def delete_document_vectors(
    facility_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    """
    Delete all vectors for a document. Scoped by facility_id for safety.

    @param facility_id: Facility UUID (multi-tenant guard)
    @param document_id: Document UUID to delete vectors for
    """
    client = get_qdrant_client()
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="facility_id",
                        match=qmodels.MatchValue(value=str(facility_id)),
                    ),
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchValue(value=str(document_id)),
                    ),
                ]
            )
        ),
    )
    logger.info(
        "qdrant_vectors_deleted",
        facility_id=str(facility_id),
        document_id=str(document_id),
    )


def search_similar(
    query_text: str,
    facility_id: uuid.UUID,
    top_k: int | None = None,
    categories: list[str] | None = None,
    department: str | None = None,
    document_ids: list[uuid.UUID] | None = None,
) -> list[dict]:
    """
    Search for similar document chunks within a facility.

    @param query_text: Natural language query
    @param facility_id: Facility UUID (mandatory multi-tenant filter)
    @param top_k: Number of results to return
    @param categories: Optional category filter
    @param department: Optional department filter
    @param document_ids: Optional document ID filter
    @returns List of dicts with score, payload
    """
    client = get_qdrant_client()
    top_k = top_k or settings.retrieval_top_k

    query_vector = embed_query(query_text)

    must_conditions: list[qmodels.Condition] = [
        qmodels.FieldCondition(
            key="facility_id",
            match=qmodels.MatchValue(value=str(facility_id)),
        )
    ]

    if categories:
        must_conditions.append(
            qmodels.FieldCondition(
                key="category",
                match=qmodels.MatchAny(any=[c for c in categories]),
            )
        )

    if department:
        must_conditions.append(
            qmodels.FieldCondition(
                key="department",
                match=qmodels.MatchValue(value=department),
            )
        )

    if document_ids:
        must_conditions.append(
            qmodels.FieldCondition(
                key="document_id",
                match=qmodels.MatchAny(any=[str(d) for d in document_ids]),
            )
        )

    results = client.search(
        collection_name=settings.qdrant_collection,
        query_vector=query_vector,
        query_filter=qmodels.Filter(must=must_conditions),
        limit=top_k,
        score_threshold=settings.similarity_threshold,
    )

    hits: list[dict] = []
    for point in results:
        hits.append(
            {
                "score": point.score,
                "point_id": point.id,
                **point.payload,
            }
        )

    logger.info(
        "qdrant_search_complete",
        facility_id=str(facility_id),
        query_length=len(query_text),
        results=len(hits),
    )
    return hits


def check_health() -> str:
    """
    Check Qdrant connectivity.

    @returns Status string: 'connected' or 'disconnected'
    """
    try:
        client = get_qdrant_client()
        client.get_collections()
        return "connected"
    except Exception:
        return "disconnected"
