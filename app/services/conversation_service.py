"""Conversation tracking service for session-based logging"""
from google.cloud import bigquery
from app.config import get_settings
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import json
import uuid

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for tracking full conversations (session-based)"""

    def __init__(self):
        self.settings = get_settings()
        try:
            self.client = bigquery.Client(project=self.settings.project_id)
            self.dataset_id = f"{self.settings.project_id}.{self.settings.bigquery_dataset}"
            self.conversations_table = f"{self.dataset_id}.conversations"
            self.messages_table = f"{self.dataset_id}.conversation_messages"
            self.initialized = True
            logger.info("Conversation service initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Conversation service: {e}")
            self.initialized = False

    async def setup_conversation_tables(self):
        """Create conversation tables if they don't exist"""
        if not self.initialized:
            return

        try:
            # Conversations table - one row per session
            conv_schema = [
                bigquery.SchemaField("session_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("agent_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("user_id", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("department", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("started_at", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("ended_at", "TIMESTAMP", mode="NULLABLE"),
                bigquery.SchemaField("message_count", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("total_pii_incidents", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("total_blocked", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("status", "STRING", mode="REQUIRED"),  # active, completed, abandoned
                bigquery.SchemaField("metadata", "STRING", mode="NULLABLE"),  # JSON
            ]

            conv_table = bigquery.Table(self.conversations_table, schema=conv_schema)
            conv_table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="started_at"
            )

            self.client.create_table(conv_table, exists_ok=True)
            logger.info(f"Conversations table {self.conversations_table} ready")

            # Messages table - one row per message in conversation
            msg_schema = [
                bigquery.SchemaField("message_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("session_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("agent_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("turn_number", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("role", "STRING", mode="REQUIRED"),  # user, assistant
                bigquery.SchemaField("content", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("has_pii", "BOOLEAN", mode="REQUIRED"),
                bigquery.SchemaField("was_blocked", "BOOLEAN", mode="REQUIRED"),
                bigquery.SchemaField("guardrail_result", "STRING", mode="NULLABLE"),  # JSON
                bigquery.SchemaField("feedback_rating", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("processing_time_ms", "FLOAT", mode="NULLABLE"),
            ]

            msg_table = bigquery.Table(self.messages_table, schema=msg_schema)
            msg_table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="timestamp"
            )

            self.client.create_table(msg_table, exists_ok=True)
            logger.info(f"Messages table {self.messages_table} ready")

        except Exception as e:
            logger.error(f"Error setting up conversation tables: {e}")

    async def start_conversation(
        self,
        agent_id: str,
        user_id: Optional[str] = None,
        department: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """Start a new conversation session"""
        session_id = session_id or str(uuid.uuid4())
        now = datetime.utcnow()

        if self.initialized:
            try:
                row_data = {
                    "session_id": session_id,
                    "agent_id": agent_id,
                    "user_id": user_id,
                    "department": department,
                    "started_at": now.isoformat(),
                    "ended_at": None,
                    "message_count": 0,
                    "total_pii_incidents": 0,
                    "total_blocked": 0,
                    "status": "active",
                    "metadata": json.dumps(metadata) if metadata else None,
                }

                errors = self.client.insert_rows_json(self.conversations_table, [row_data])
                if errors:
                    logger.error(f"Error starting conversation: {errors}")

            except Exception as e:
                logger.error(f"Error starting conversation: {e}")

        logger.info(f"Conversation started: {session_id} for agent {agent_id}")
        return session_id

    async def add_message(
        self,
        session_id: str,
        agent_id: str,
        role: str,  # "user" or "assistant"
        content: str,
        turn_number: int,
        has_pii: bool = False,
        was_blocked: bool = False,
        guardrail_result: Optional[Dict] = None,
        processing_time_ms: Optional[float] = None
    ) -> str:
        """Add a message to a conversation"""
        message_id = str(uuid.uuid4())
        now = datetime.utcnow()

        if self.initialized:
            try:
                row_data = {
                    "message_id": message_id,
                    "session_id": session_id,
                    "agent_id": agent_id,
                    "turn_number": turn_number,
                    "role": role,
                    "content": content,
                    "timestamp": now.isoformat(),
                    "has_pii": has_pii,
                    "was_blocked": was_blocked,
                    "guardrail_result": json.dumps(guardrail_result) if guardrail_result else None,
                    "feedback_rating": None,
                    "processing_time_ms": processing_time_ms,
                }

                errors = self.client.insert_rows_json(self.messages_table, [row_data])
                if errors:
                    logger.error(f"Error adding message: {errors}")

                # Update conversation stats (fire and forget)
                await self._update_conversation_stats(session_id, has_pii, was_blocked)

            except Exception as e:
                logger.error(f"Error adding message: {e}")

        return message_id

    async def _update_conversation_stats(self, session_id: str, has_pii: bool, was_blocked: bool):
        """Update conversation statistics"""
        try:
            # Using DML to update stats
            pii_increment = 1 if has_pii else 0
            blocked_increment = 1 if was_blocked else 0

            query = f"""
            UPDATE `{self.conversations_table}`
            SET
                message_count = message_count + 1,
                total_pii_incidents = total_pii_incidents + {pii_increment},
                total_blocked = total_blocked + {blocked_increment}
            WHERE session_id = @session_id
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("session_id", "STRING", session_id)
                ]
            )
            self.client.query(query, job_config=job_config)

        except Exception as e:
            logger.error(f"Error updating conversation stats: {e}")

    async def end_conversation(self, session_id: str, status: str = "completed"):
        """End a conversation session"""
        if not self.initialized:
            return

        try:
            query = f"""
            UPDATE `{self.conversations_table}`
            SET
                ended_at = CURRENT_TIMESTAMP(),
                status = @status
            WHERE session_id = @session_id
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("session_id", "STRING", session_id),
                    bigquery.ScalarQueryParameter("status", "STRING", status),
                ]
            )
            self.client.query(query, job_config=job_config).result()
            logger.info(f"Conversation ended: {session_id} with status {status}")

        except Exception as e:
            logger.error(f"Error ending conversation: {e}")

    async def get_conversation(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a conversation with all its messages"""
        if not self.initialized:
            return None

        try:
            # Get conversation metadata
            conv_query = f"""
            SELECT *
            FROM `{self.conversations_table}`
            WHERE session_id = @session_id
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("session_id", "STRING", session_id)
                ]
            )

            conv_results = list(self.client.query(conv_query, job_config=job_config).result())
            if not conv_results:
                return None

            conv = conv_results[0]

            # Get messages
            msg_query = f"""
            SELECT *
            FROM `{self.messages_table}`
            WHERE session_id = @session_id
            ORDER BY turn_number, timestamp
            """

            messages = []
            for row in self.client.query(msg_query, job_config=job_config).result():
                messages.append({
                    "message_id": row.message_id,
                    "turn_number": row.turn_number,
                    "role": row.role,
                    "content": row.content,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    "has_pii": row.has_pii,
                    "was_blocked": row.was_blocked,
                    "feedback_rating": row.feedback_rating,
                })

            return {
                "session_id": conv.session_id,
                "agent_id": conv.agent_id,
                "user_id": conv.user_id,
                "department": conv.department,
                "started_at": conv.started_at.isoformat() if conv.started_at else None,
                "ended_at": conv.ended_at.isoformat() if conv.ended_at else None,
                "message_count": conv.message_count,
                "total_pii_incidents": conv.total_pii_incidents,
                "total_blocked": conv.total_blocked,
                "status": conv.status,
                "messages": messages
            }

        except Exception as e:
            logger.error(f"Error getting conversation: {e}")
            return None

    async def get_training_export(
        self,
        agent_id: Optional[str] = None,
        days: int = 30,
        include_pii_incidents: bool = False,
        only_with_feedback: bool = False,
        min_messages: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Export conversations for training/fine-tuning.

        Returns conversations in a format suitable for model training.
        """
        if not self.initialized:
            return []

        try:
            where_clauses = [
                f"c.started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)",
                f"c.message_count >= {min_messages}",
                "c.status = 'completed'"
            ]

            if agent_id:
                where_clauses.append(f"c.agent_id = '{agent_id}'")

            if not include_pii_incidents:
                where_clauses.append("c.total_pii_incidents = 0")

            where_clause = " AND ".join(where_clauses)

            # Get qualifying conversations
            query = f"""
            SELECT
                c.session_id,
                c.agent_id,
                c.department,
                c.message_count,
                c.total_pii_incidents,
                c.total_blocked
            FROM `{self.conversations_table}` c
            WHERE {where_clause}
            ORDER BY c.started_at DESC
            LIMIT 1000
            """

            conversations = []
            for conv_row in self.client.query(query).result():
                # Get messages for this conversation
                msg_query = f"""
                SELECT
                    m.role,
                    m.content,
                    m.has_pii,
                    m.was_blocked,
                    m.feedback_rating
                FROM `{self.messages_table}` m
                WHERE m.session_id = @session_id
                ORDER BY m.turn_number, m.timestamp
                """

                msg_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("session_id", "STRING", conv_row.session_id)
                    ]
                )

                messages = []
                has_feedback = False
                for msg_row in self.client.query(msg_query, job_config=msg_config).result():
                    if msg_row.feedback_rating:
                        has_feedback = True
                    messages.append({
                        "role": msg_row.role,
                        "content": msg_row.content,
                        "feedback": msg_row.feedback_rating
                    })

                if only_with_feedback and not has_feedback:
                    continue

                conversations.append({
                    "session_id": conv_row.session_id,
                    "agent_id": conv_row.agent_id,
                    "department": conv_row.department,
                    "messages": messages,
                    "stats": {
                        "message_count": conv_row.message_count,
                        "pii_incidents": conv_row.total_pii_incidents,
                        "blocked_count": conv_row.total_blocked
                    }
                })

            logger.info(f"Exported {len(conversations)} conversations for training")
            return conversations

        except Exception as e:
            logger.error(f"Error exporting training data: {e}")
            return []


# Global instance
_conversation_service: "ConversationService" = None  # type: ignore


def get_conversation_service() -> ConversationService:
    """Get or create the Conversation service instance"""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service