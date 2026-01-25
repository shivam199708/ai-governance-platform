"""Audit logging service for BigQuery"""
from google.cloud import bigquery
from app.config import get_settings
from app.models.schemas import AuditLog
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


class AuditService:
    """Service for logging audit events to BigQuery"""

    def __init__(self):
        self.settings = get_settings()
        try:
            self.client = bigquery.Client(project=self.settings.project_id)
            self.table_id = f"{self.settings.project_id}.{self.settings.bigquery_dataset}.{self.settings.bigquery_audit_table}"
            self.initialized = True
            logger.info(f"Audit service initialized for table: {self.table_id}")
        except Exception as e:
            logger.warning(f"Failed to initialize BigQuery: {e}. Audit logs will be logged locally only.")
            self.initialized = False
            self.local_logs = []

    async def log_audit_event(self, audit_log: AuditLog) -> bool:
        """
        Log an audit event to BigQuery.

        Args:
            audit_log: The audit log entry to store

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self.initialized:
                # Convert Pydantic model to dict for BigQuery
                row_data = {
                    "request_id": audit_log.request_id,
                    "timestamp": audit_log.timestamp.isoformat(),
                    "agent_id": audit_log.agent_id,
                    "user_id": audit_log.user_id,
                    "department": audit_log.department,
                    "session_id": audit_log.session_id,
                    "guardrail_type": audit_log.guardrail_type,
                    "status": audit_log.status,
                    "prompt_length": audit_log.prompt_length,
                    "has_pii": audit_log.has_pii,
                    "processing_time_ms": audit_log.processing_time_ms,
                    "model_used": audit_log.model_used,
                    "metadata": json.dumps(audit_log.metadata) if audit_log.metadata else None,
                    "original_prompt": audit_log.original_prompt,
                    "redacted_prompt": audit_log.redacted_prompt
                }

                errors = self.client.insert_rows_json(self.table_id, [row_data])

                if errors:
                    logger.error(f"Error inserting rows to BigQuery: {errors}")
                    self._log_locally(audit_log)
                    return False

                logger.debug(f"Audit log written to BigQuery: {audit_log.request_id}")
                return True
            else:
                self._log_locally(audit_log)
                return True

        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
            self._log_locally(audit_log)
            return False

    def _log_locally(self, audit_log: AuditLog):
        """Fallback: log to local storage/console"""
        if not self.initialized:
            if not hasattr(self, 'local_logs'):
                self.local_logs = []
            self.local_logs.append(audit_log.model_dump())

        log_entry = {
            "request_id": audit_log.request_id,
            "timestamp": audit_log.timestamp.isoformat(),
            "agent_id": audit_log.agent_id,
            "guardrail": audit_log.guardrail_type,
            "status": audit_log.status,
            "has_pii": audit_log.has_pii,
            "processing_time_ms": audit_log.processing_time_ms
        }
        logger.info(f"AUDIT_LOG: {json.dumps(log_entry)}")

    async def setup_bigquery_table(self):
        """Create BigQuery dataset and table if they don't exist"""
        if not self.initialized:
            logger.warning("BigQuery not initialized. Skipping table setup.")
            return

        try:
            # Create dataset
            dataset_id = f"{self.settings.project_id}.{self.settings.bigquery_dataset}"
            dataset = bigquery.Dataset(dataset_id)
            dataset.location = self.settings.location

            try:
                self.client.create_dataset(dataset, exists_ok=True)
                logger.info(f"Dataset {dataset_id} created or already exists")
            except Exception as e:
                logger.error(f"Error creating dataset: {e}")

            # Create table schema
            schema = [
                bigquery.SchemaField("request_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("agent_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("user_id", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("department", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("session_id", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("guardrail_type", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("prompt_length", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("has_pii", "BOOLEAN", mode="REQUIRED"),
                bigquery.SchemaField("processing_time_ms", "FLOAT", mode="REQUIRED"),
                bigquery.SchemaField("model_used", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("metadata", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("original_prompt", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("redacted_prompt", "STRING", mode="NULLABLE"),
            ]

            table = bigquery.Table(self.table_id, schema=schema)

            # Partition by day for better performance
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="timestamp"
            )

            try:
                self.client.create_table(table, exists_ok=True)
                logger.info(f"Table {self.table_id} created or already exists")
            except Exception as e:
                logger.error(f"Error creating table: {e}")

        except Exception as e:
            logger.error(f"Error setting up BigQuery: {e}")


# Global instance
_audit_service: "AuditService" = None  # type: ignore


def get_audit_service() -> AuditService:
    """Get or create the Audit service instance"""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service
