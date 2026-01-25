"""Authentication service for API key management"""
from google.cloud import bigquery
from app.config import get_settings
from app.models.schemas import APIKeyCreate, APIKeyResponse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
import secrets
import hashlib

logger = logging.getLogger(__name__)


class AuthService:
    """Service for API key authentication"""

    def __init__(self):
        self.settings = get_settings()
        try:
            self.client = bigquery.Client(project=self.settings.project_id)
            self.dataset_id = f"{self.settings.project_id}.{self.settings.bigquery_dataset}"
            self.keys_table = f"{self.dataset_id}.api_keys"
            self.initialized = True
            logger.info("Auth service initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Auth service: {e}")
            self.initialized = False

    async def setup_keys_table(self):
        """Create API keys table if it doesn't exist"""
        if not self.initialized:
            return

        try:
            schema = [
                bigquery.SchemaField("key_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("agent_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("key_hash", "STRING", mode="REQUIRED"),  # Hashed key
                bigquery.SchemaField("key_prefix", "STRING", mode="REQUIRED"),  # First 8 chars for display
                bigquery.SchemaField("description", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("expires_at", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("last_used_at", "TIMESTAMP", mode="NULLABLE"),
                bigquery.SchemaField("is_active", "BOOLEAN", mode="REQUIRED"),
            ]

            table = bigquery.Table(self.keys_table, schema=schema)

            try:
                self.client.create_table(table, exists_ok=True)
                logger.info(f"API keys table {self.keys_table} ready")
            except Exception as e:
                logger.error(f"Error creating API keys table: {e}")

        except Exception as e:
            logger.error(f"Error setting up API keys table: {e}")

    def _generate_api_key(self) -> str:
        """Generate a secure API key"""
        return f"gov_{secrets.token_urlsafe(32)}"

    def _hash_key(self, api_key: str) -> str:
        """Hash an API key for storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()

    async def create_api_key(self, request: APIKeyCreate) -> APIKeyResponse:
        """Create a new API key for an agent"""
        key_id = secrets.token_urlsafe(16)
        api_key = self._generate_api_key()
        key_hash = self._hash_key(api_key)
        key_prefix = api_key[:12] + "..."

        now = datetime.utcnow()
        expires_at = now + timedelta(days=request.expires_days)

        if self.initialized:
            try:
                row_data = {
                    "key_id": key_id,
                    "agent_id": request.agent_id,
                    "key_hash": key_hash,
                    "key_prefix": key_prefix,
                    "description": request.description,
                    "created_at": now.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "last_used_at": None,
                    "is_active": True,
                }

                errors = self.client.insert_rows_json(self.keys_table, [row_data])
                if errors:
                    logger.error(f"Error creating API key: {errors}")
                    raise Exception(f"Failed to create API key: {errors}")

            except Exception as e:
                logger.error(f"Error creating API key: {e}")
                raise

        return APIKeyResponse(
            key_id=key_id,
            agent_id=request.agent_id,
            api_key=api_key,  # Only returned once!
            created_at=now,
            expires_at=expires_at,
            is_active=True
        )

    async def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Validate an API key and return agent info if valid"""
        if not self.initialized:
            logger.warning("Auth service not initialized, allowing all requests")
            return {"agent_id": "default", "validated": False}

        key_hash = self._hash_key(api_key)

        query = f"""
        SELECT key_id, agent_id, expires_at, is_active
        FROM `{self.keys_table}`
        WHERE key_hash = @key_hash
        LIMIT 1
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("key_hash", "STRING", key_hash)
            ]
        )

        try:
            results = list(self.client.query(query, job_config=job_config).result())

            if not results:
                return None

            row = results[0]

            # Check if key is active and not expired
            if not row.is_active:
                logger.warning(f"API key {row.key_id} is inactive")
                return None

            if row.expires_at < datetime.utcnow():
                logger.warning(f"API key {row.key_id} has expired")
                return None

            # Update last used timestamp (fire and forget)
            try:
                update_query = f"""
                UPDATE `{self.keys_table}`
                SET last_used_at = CURRENT_TIMESTAMP()
                WHERE key_id = @key_id
                """
                update_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("key_id", "STRING", row.key_id)
                    ]
                )
                self.client.query(update_query, job_config=update_config)
            except Exception:
                pass  # Don't fail validation if update fails

            return {
                "key_id": row.key_id,
                "agent_id": row.agent_id,
                "validated": True
            }

        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            return None

    async def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key"""
        if not self.initialized:
            return False

        try:
            query = f"""
            UPDATE `{self.keys_table}`
            SET is_active = FALSE
            WHERE key_id = @key_id
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("key_id", "STRING", key_id)
                ]
            )
            self.client.query(query, job_config=job_config).result()
            logger.info(f"API key {key_id} revoked")
            return True

        except Exception as e:
            logger.error(f"Error revoking API key: {e}")
            return False

    async def list_agent_keys(self, agent_id: str) -> list:
        """List all API keys for an agent (without the actual keys)"""
        if not self.initialized:
            return []

        query = f"""
        SELECT key_id, key_prefix, description, created_at, expires_at, last_used_at, is_active
        FROM `{self.keys_table}`
        WHERE agent_id = @agent_id
        ORDER BY created_at DESC
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("agent_id", "STRING", agent_id)
            ]
        )

        keys = []
        try:
            for row in self.client.query(query, job_config=job_config).result():
                keys.append({
                    "key_id": row.key_id,
                    "key_prefix": row.key_prefix,
                    "description": row.description,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                    "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
                    "is_active": row.is_active
                })
        except Exception as e:
            logger.error(f"Error listing API keys: {e}")

        return keys


# Global instance
_auth_service: "AuthService" = None  # type: ignore


def get_auth_service() -> AuthService:
    """Get or create the Auth service instance"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service