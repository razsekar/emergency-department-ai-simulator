"""Knowledge base metadata and RAG chunk store (pgvector, 384 dims, HNSW cosine).

Revision ID: 0200
Revises: 0001
"""
from alembic import op

revision = "0200"
down_revision = "0001"
branch_labels = ("rag",)
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE knowledge_base.knowledge_documents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name text NOT NULL,
            original_filename text NOT NULL,
            content_sha256 char(64) NOT NULL UNIQUE,
            size_bytes integer NOT NULL CHECK (size_bytes > 0),
            page_count integer NOT NULL CHECK (page_count > 0),
            status text NOT NULL DEFAULT 'processing'
                CHECK (status IN ('processing', 'indexed', 'failed')),
            chunk_count integer NOT NULL DEFAULT 0,
            error_message text,
            is_sample boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_knowledge_documents_created_at "
        "ON knowledge_base.knowledge_documents (created_at DESC)"
    )
    # document_id is an opaque UUID: no cross-schema foreign key (module boundary).
    op.execute(
        """
        CREATE TABLE rag.document_chunks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id uuid NOT NULL,
            document_name text NOT NULL,
            page_number integer NOT NULL CHECK (page_number > 0),
            chunk_index integer NOT NULL CHECK (chunk_index >= 0),
            content text NOT NULL,
            injection_flagged boolean NOT NULL DEFAULT false,
            injection_signals text[] NOT NULL DEFAULT '{}',
            embedding vector(384) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (document_id, chunk_index)
        )
        """
    )
    op.execute("CREATE INDEX ix_document_chunks_document_id ON rag.document_chunks (document_id)")
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding_hnsw "
        "ON rag.document_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rag.document_chunks")
    op.execute("DROP TABLE IF EXISTS knowledge_base.knowledge_documents")
