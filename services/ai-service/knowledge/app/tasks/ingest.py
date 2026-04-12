"""
Celery tasks for document ingestion pipeline.
Pipeline: Download from MinIO → Parse → Chunk → Embed → Store in Qdrant.
"""

import os
import tempfile
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from structlog import get_logger

from app.chunking.semantic_chunker import TextChunk, chunk_document
from app.config import get_settings
from app.models.document import DocumentChunk, KnowledgeDocument
from app.models.schemas import DocumentStatus
from app.parsers.base import ParsedDocument
from app.parsers.docx_parser import parse_docx
from app.parsers.pdf_parser import parse_pdf
from app.parsers.text_parser import parse_text
from app.services.document_service import download_file_from_minio
from app.services.embedding_service import embed_texts
from app.services.retrieval_service import upsert_vectors
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)
settings = get_settings()

_sync_engine = create_engine(
    settings.database_url.replace("+asyncpg", ""),
    pool_size=5,
    max_overflow=10,
)
_SyncSession = sessionmaker(bind=_sync_engine)

_MIME_PARSERS: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "docx",
    "text/plain": "text",
    "text/markdown": "text",
    "text/rtf": "text",
}


def _update_status(
    session: Session,
    document_id: uuid.UUID,
    status: DocumentStatus,
    error_message: str | None = None,
    chunk_count: int | None = None,
    page_count: int | None = None,
) -> None:
    """
    Synchronous status update for use in Celery tasks.

    @param session: Sync DB session
    @param document_id: Document UUID
    @param status: New status
    @param error_message: Error message if failed
    @param chunk_count: Chunk count
    @param page_count: Page count
    """
    doc = session.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == document_id
    ).first()
    if doc:
        doc.status = status.value
        if error_message is not None:
            doc.error_message = error_message
        if chunk_count is not None:
            doc.chunk_count = chunk_count
        if page_count is not None:
            doc.page_count = page_count
        session.commit()


@celery_app.task(
    name="app.tasks.ingest.ingest_document",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def ingest_document(
    self,
    document_id: str,
    facility_id: str,
    minio_object_key: str,
    mime_type: str,
    document_title: str,
    category: str,
    department: str | None = None,
) -> dict:
    """
    Full document ingestion pipeline.
    Runs as a Celery task (synchronous context).

    @param document_id: Document UUID string
    @param facility_id: Facility UUID string
    @param minio_object_key: MinIO object key
    @param mime_type: File MIME type
    @param document_title: Document title for Qdrant payload
    @param category: Document category
    @param department: Optional department
    @returns Dict with status, chunk_count, page_count
    """
    doc_uuid = uuid.UUID(document_id)
    fac_uuid = uuid.UUID(facility_id)
    session = _SyncSession()

    try:
        # --- Step 1: Download from MinIO ---
        _update_status(session, doc_uuid, DocumentStatus.PROCESSING)
        self.update_state(state="PROCESSING", meta={"progress": 10})

        parser_type = _MIME_PARSERS.get(mime_type, "text")
        suffix_map = {"pdf": ".pdf", "docx": ".docx", "text": ".txt"}
        suffix = suffix_map.get(parser_type, ".txt")

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name

        download_file_from_minio(minio_object_key, tmp_path)
        logger.info("file_downloaded", doc_id=document_id, path=tmp_path)

        # --- Step 2: Parse ---
        _update_status(session, doc_uuid, DocumentStatus.PROCESSING)
        self.update_state(state="PARSING", meta={"progress": 25})

        parsed: ParsedDocument
        if parser_type == "pdf":
            parsed = parse_pdf(tmp_path)
        elif parser_type == "docx":
            parsed = parse_docx(tmp_path)
        else:
            parsed = parse_text(tmp_path)

        _update_status(session, doc_uuid, DocumentStatus.CHUNKING, page_count=parsed.total_pages)
        self.update_state(state="CHUNKING", meta={"progress": 40})

        # --- Step 3: Chunk ---
        chunks: list[TextChunk] = chunk_document(parsed)
        logger.info("chunking_complete", doc_id=document_id, chunks=len(chunks))

        if not chunks:
            _update_status(
                session, doc_uuid, DocumentStatus.FAILED,
                error_message="No text content could be extracted from the document.",
            )
            return {"status": "failed", "error": "No extractable text"}

        # --- Step 4: Embed ---
        _update_status(session, doc_uuid, DocumentStatus.EMBEDDING)
        self.update_state(state="EMBEDDING", meta={"progress": 55})

        texts = [c.text for c in chunks]
        embeddings = embed_texts(texts)
        logger.info("embedding_complete", doc_id=document_id, vectors=len(embeddings))

        # --- Step 5: Store in Qdrant ---
        self.update_state(state="STORING", meta={"progress": 75})

        qdrant_points: list[dict] = []
        chunk_records: list[dict] = []

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid4())
            qdrant_points.append({
                "id": point_id,
                "vector": embedding,
                "payload": {
                    "facility_id": facility_id,
                    "document_id": document_id,
                    "document_title": document_title,
                    "category": category,
                    "department": department or "",
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "page_number": chunk.page_number,
                    "section_title": chunk.section_title or "",
                },
            })
            chunk_records.append({
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "page_number": chunk.page_number,
                "section_title": chunk.section_title,
                "token_count": chunk.token_count,
                "qdrant_point_id": point_id,
            })

        upsert_vectors(qdrant_points)

        # --- Step 6: Save chunks to PostgreSQL ---
        self.update_state(state="SAVING_CHUNKS", meta={"progress": 90})

        db_chunks = [
            DocumentChunk(
                document_id=doc_uuid,
                facility_id=fac_uuid,
                chunk_index=c["chunk_index"],
                text=c["text"],
                page_number=c.get("page_number"),
                section_title=c.get("section_title"),
                token_count=c.get("token_count", 0),
                qdrant_point_id=c.get("qdrant_point_id"),
            )
            for c in chunk_records
        ]
        session.add_all(db_chunks)
        session.commit()

        # --- Step 7: Mark as ready ---
        _update_status(
            session, doc_uuid, DocumentStatus.READY,
            chunk_count=len(chunks),
        )
        self.update_state(state="COMPLETED", meta={"progress": 100})

        logger.info(
            "ingest_complete",
            doc_id=document_id,
            chunks=len(chunks),
            pages=parsed.total_pages,
        )
        return {
            "status": "completed",
            "chunk_count": len(chunks),
            "page_count": parsed.total_pages,
        }

    except Exception as exc:
        logger.error(
            "ingest_failed",
            doc_id=document_id,
            error=str(exc),
            exc_info=True,
        )
        _update_status(
            session, doc_uuid, DocumentStatus.FAILED,
            error_message=str(exc)[:500],
        )
        raise self.retry(exc=exc)

    finally:
        session.close()
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
