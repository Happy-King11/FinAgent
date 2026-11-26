"""可重试的文档、报告和索引任务入口。"""

from app.infrastructure.queue.celery_app import create_celery_app


celery_app = create_celery_app() if __name__ != "__main__" else None

if celery_app:
    @celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
    def rebuild_document_index(self, document_id: str, tenant_id: str, task_id: str) -> str:
        """Validate one durable document and record the bounded task lifecycle."""
        from app.core.config import get_settings
        from app.infrastructure.database.session import create_session_factory
        from app.repositories.sql import SQLDocumentRepository
        from app.repositories.workflow import SQLWorkflowRecordStore

        settings = get_settings()
        if settings.persistence_backend != "postgresql":
            raise RuntimeError("document index task requires PostgreSQL persistence")
        records = SQLWorkflowRecordStore(create_session_factory())
        records.put("task", task_id, tenant_id, {"task_id": task_id, "tenant_id": tenant_id, "task_type": "document_index", "status": "running", "attempts": self.request.retries + 1, "document_id": document_id})
        try:
            document = SQLDocumentRepository(create_session_factory()).get(document_id, tenant_id)
            if not document.content:
                raise ValueError("document content is unavailable for indexing")
            from app.application.document_indexing import DocumentIndexer
            from app.infrastructure.vector_store.factory import create_vector_store
            from app.llm.embeddings import HashingEmbedding, OpenAICompatibleEmbedding

            if settings.embedding_provider == "openai_compatible":
                embedding_provider = OpenAICompatibleEmbedding(
                    settings.embedding_base_url,
                    settings.embedding_api_key,
                    settings.embedding_model,
                    settings.embedding_dimension,
                    settings.embedding_timeout_seconds,
                )
            else:
                embedding_provider = HashingEmbedding(settings.embedding_dimension)
            index_result = DocumentIndexer(
                embedding_provider,
                create_vector_store(),
            ).index(document)
            result = {"task_id": task_id, "tenant_id": tenant_id, "task_type": "document_index", "status": "succeeded", "attempts": self.request.retries + 1, "document_id": document_id, "result_ref": index_result}
            records.put("task", task_id, tenant_id, result)
            return document_id
        except (ConnectionError, TimeoutError, RuntimeError) as exc:
            records.put("task", task_id, tenant_id, {"task_id": task_id, "tenant_id": tenant_id, "task_type": "document_index", "status": "retrying", "attempts": self.request.retries + 1, "document_id": document_id, "error_type": type(exc).__name__})
            raise self.retry(exc=exc) from exc
        except Exception as exc:
            records.put("task", task_id, tenant_id, {"task_id": task_id, "tenant_id": tenant_id, "task_type": "document_index", "status": "failed", "attempts": self.request.retries + 1, "document_id": document_id, "error_type": type(exc).__name__})
            raise
