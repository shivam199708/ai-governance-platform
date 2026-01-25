"""Feedback service for tracking agent improvement suggestions"""
from google.cloud import bigquery
from app.config import get_settings
from app.models.schemas import FeedbackSubmit, FeedbackResponse
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import json
import uuid

logger = logging.getLogger(__name__)


class FeedbackService:
    """Service for managing agent feedback and improvement tracking"""

    def __init__(self):
        self.settings = get_settings()
        try:
            self.client = bigquery.Client(project=self.settings.project_id)
            self.dataset_id = f"{self.settings.project_id}.{self.settings.bigquery_dataset}"
            self.feedback_table = f"{self.dataset_id}.feedback"
            self.initialized = True
            logger.info("Feedback service initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Feedback service: {e}")
            self.initialized = False

    async def setup_feedback_table(self):
        """Create feedback table if it doesn't exist"""
        if not self.initialized:
            return

        try:
            schema = [
                bigquery.SchemaField("feedback_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("request_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("agent_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("user_id", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("rating", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("comment", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("suggestion", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("tags", "STRING", mode="NULLABLE"),  # JSON array
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
            ]

            table = bigquery.Table(self.feedback_table, schema=schema)
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="timestamp"
            )

            try:
                self.client.create_table(table, exists_ok=True)
                logger.info(f"Feedback table {self.feedback_table} ready")
            except Exception as e:
                logger.error(f"Error creating feedback table: {e}")

        except Exception as e:
            logger.error(f"Error setting up feedback table: {e}")

    async def submit_feedback(self, feedback: FeedbackSubmit) -> FeedbackResponse:
        """Submit feedback for an agent interaction"""
        feedback_id = str(uuid.uuid4())
        now = datetime.utcnow()

        if self.initialized:
            try:
                row_data = {
                    "feedback_id": feedback_id,
                    "request_id": feedback.request_id,
                    "agent_id": feedback.agent_id,
                    "user_id": feedback.user_id,
                    "rating": feedback.rating.value,
                    "comment": feedback.comment,
                    "suggestion": feedback.suggestion,
                    "tags": json.dumps(feedback.tags) if feedback.tags else None,
                    "timestamp": now.isoformat(),
                }

                errors = self.client.insert_rows_json(self.feedback_table, [row_data])
                if errors:
                    logger.error(f"Error inserting feedback: {errors}")

            except Exception as e:
                logger.error(f"Error submitting feedback: {e}")

        return FeedbackResponse(
            feedback_id=feedback_id,
            request_id=feedback.request_id,
            agent_id=feedback.agent_id,
            status="received",
            timestamp=now
        )

    async def get_agent_feedback_summary(self, agent_id: str, days: int = 30) -> Dict[str, Any]:
        """Get feedback summary for an agent"""
        if not self.initialized:
            return {}

        query = f"""
        SELECT
            agent_id,
            COUNT(*) as total_feedback,
            COUNTIF(rating = 'helpful') as helpful_count,
            COUNTIF(rating = 'not_helpful') as not_helpful_count,
            COUNTIF(rating = 'incorrect') as incorrect_count,
            COUNTIF(rating = 'inappropriate') as inappropriate_count,
            COUNT(DISTINCT user_id) as unique_users
        FROM `{self.feedback_table}`
        WHERE agent_id = @agent_id
          AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        GROUP BY agent_id
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("agent_id", "STRING", agent_id),
                bigquery.ScalarQueryParameter("days", "INT64", days),
            ]
        )

        try:
            results = list(self.client.query(query, job_config=job_config).result())
            if results:
                row = results[0]
                return {
                    "agent_id": row.agent_id,
                    "total_feedback": row.total_feedback,
                    "helpful_count": row.helpful_count,
                    "not_helpful_count": row.not_helpful_count,
                    "incorrect_count": row.incorrect_count,
                    "inappropriate_count": row.inappropriate_count,
                    "unique_users": row.unique_users,
                    "helpful_rate": round(row.helpful_count / row.total_feedback * 100, 2) if row.total_feedback > 0 else 0
                }
        except Exception as e:
            logger.error(f"Error getting feedback summary: {e}")

        return {}

    async def get_recent_suggestions(self, agent_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent improvement suggestions"""
        if not self.initialized:
            return []

        where_clause = "WHERE suggestion IS NOT NULL"
        params = []

        if agent_id:
            where_clause += " AND agent_id = @agent_id"
            params.append(bigquery.ScalarQueryParameter("agent_id", "STRING", agent_id))

        query = f"""
        SELECT
            feedback_id,
            request_id,
            agent_id,
            user_id,
            rating,
            comment,
            suggestion,
            timestamp
        FROM `{self.feedback_table}`
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT {limit}
        """

        job_config = bigquery.QueryJobConfig(query_parameters=params) if params else None

        suggestions = []
        try:
            for row in self.client.query(query, job_config=job_config).result():
                suggestions.append({
                    "feedback_id": row.feedback_id,
                    "request_id": row.request_id,
                    "agent_id": row.agent_id,
                    "user_id": row.user_id,
                    "rating": row.rating,
                    "comment": row.comment,
                    "suggestion": row.suggestion,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None
                })
        except Exception as e:
            logger.error(f"Error getting suggestions: {e}")

        return suggestions


# Global instance
_feedback_service: "FeedbackService" = None  # type: ignore


def get_feedback_service() -> FeedbackService:
    """Get or create the Feedback service instance"""
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = FeedbackService()
    return _feedback_service