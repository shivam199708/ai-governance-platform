"""Enterprise service for agent registry and analytics"""
from google.cloud import bigquery
from app.config import get_settings
from app.models.schemas import AgentRegister, AgentInfo, DepartmentStats, UsageAnalytics
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
import json

logger = logging.getLogger(__name__)


class EnterpriseService:
    """Service for enterprise-level agent management and analytics"""

    def __init__(self):
        self.settings = get_settings()
        try:
            self.client = bigquery.Client(project=self.settings.project_id)
            self.dataset_id = f"{self.settings.project_id}.{self.settings.bigquery_dataset}"
            self.agents_table = f"{self.dataset_id}.agents"
            self.audit_table = f"{self.dataset_id}.{self.settings.bigquery_audit_table}"
            self.initialized = True
            logger.info(f"Enterprise service initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Enterprise service: {e}")
            self.initialized = False

    async def setup_enterprise_tables(self):
        """Create enterprise tables if they don't exist"""
        if not self.initialized:
            return

        try:
            # Agents registry table
            agents_schema = [
                bigquery.SchemaField("agent_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("agent_name", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("department", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("team", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("description", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("owner_email", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("environment", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("tags", "STRING", mode="NULLABLE"),  # JSON array
                bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("is_active", "BOOLEAN", mode="REQUIRED"),
            ]

            table = bigquery.Table(self.agents_table, schema=agents_schema)
            try:
                self.client.create_table(table, exists_ok=True)
                logger.info(f"Agents table {self.agents_table} ready")
            except Exception as e:
                logger.error(f"Error creating agents table: {e}")

        except Exception as e:
            logger.error(f"Error setting up enterprise tables: {e}")

    async def register_agent(self, agent: AgentRegister) -> AgentInfo:
        """Register a new AI agent"""
        if not self.initialized:
            raise Exception("Enterprise service not initialized")

        now = datetime.utcnow()
        row_data = {
            "agent_id": agent.agent_id,
            "agent_name": agent.agent_name,
            "department": agent.department,
            "team": agent.team,
            "description": agent.description,
            "owner_email": agent.owner_email,
            "environment": agent.environment,
            "tags": json.dumps(agent.tags) if agent.tags else None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "is_active": True,
        }

        errors = self.client.insert_rows_json(self.agents_table, [row_data])
        if errors:
            logger.error(f"Error registering agent: {errors}")
            raise Exception(f"Failed to register agent: {errors}")

        logger.info(f"Registered agent: {agent.agent_id} for department: {agent.department}")

        return AgentInfo(
            agent_id=agent.agent_id,
            agent_name=agent.agent_name,
            department=agent.department,
            team=agent.team,
            description=agent.description,
            owner_email=agent.owner_email,
            environment=agent.environment,
            tags=agent.tags,
            created_at=now,
            is_active=True,
            total_requests=0,
            pii_incidents=0
        )

    async def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent information with usage stats"""
        if not self.initialized:
            return None

        query = f"""
        WITH agent_stats AS (
            SELECT
                agent_id,
                COUNT(*) as total_requests,
                COUNTIF(has_pii = true) as pii_incidents
            FROM `{self.audit_table}`
            WHERE agent_id = @agent_id
            GROUP BY agent_id
        )
        SELECT
            a.*,
            COALESCE(s.total_requests, 0) as total_requests,
            COALESCE(s.pii_incidents, 0) as pii_incidents
        FROM `{self.agents_table}` a
        LEFT JOIN agent_stats s ON a.agent_id = s.agent_id
        WHERE a.agent_id = @agent_id
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("agent_id", "STRING", agent_id)
            ]
        )

        try:
            results = self.client.query(query, job_config=job_config).result()
            for row in results:
                return AgentInfo(
                    agent_id=row.agent_id,
                    agent_name=row.agent_name,
                    department=row.department,
                    team=row.team,
                    description=row.description,
                    owner_email=row.owner_email,
                    environment=row.environment,
                    tags=json.loads(row.tags) if row.tags else [],
                    created_at=row.created_at,
                    is_active=row.is_active,
                    total_requests=row.total_requests,
                    pii_incidents=row.pii_incidents
                )
        except Exception as e:
            logger.error(f"Error getting agent: {e}")

        return None

    async def list_agents(self, department: Optional[str] = None) -> List[AgentInfo]:
        """List all registered agents, optionally filtered by department"""
        if not self.initialized:
            return []

        where_clause = ""
        params = []
        if department:
            where_clause = "WHERE a.department = @department"
            params.append(bigquery.ScalarQueryParameter("department", "STRING", department))

        query = f"""
        WITH agent_stats AS (
            SELECT
                agent_id,
                COUNT(*) as total_requests,
                COUNTIF(has_pii = true) as pii_incidents
            FROM `{self.audit_table}`
            GROUP BY agent_id
        )
        SELECT
            a.*,
            COALESCE(s.total_requests, 0) as total_requests,
            COALESCE(s.pii_incidents, 0) as pii_incidents
        FROM `{self.agents_table}` a
        LEFT JOIN agent_stats s ON a.agent_id = s.agent_id
        {where_clause}
        ORDER BY a.department, a.agent_name
        """

        job_config = bigquery.QueryJobConfig(query_parameters=params) if params else None

        agents = []
        try:
            results = self.client.query(query, job_config=job_config).result()
            for row in results:
                agents.append(AgentInfo(
                    agent_id=row.agent_id,
                    agent_name=row.agent_name,
                    department=row.department,
                    team=row.team,
                    description=row.description,
                    owner_email=row.owner_email,
                    environment=row.environment,
                    tags=json.loads(row.tags) if row.tags else [],
                    created_at=row.created_at,
                    is_active=row.is_active,
                    total_requests=row.total_requests,
                    pii_incidents=row.pii_incidents
                ))
        except Exception as e:
            logger.error(f"Error listing agents: {e}")

        return agents

    async def get_usage_analytics(self, days: int = 7) -> UsageAnalytics:
        """Get enterprise-wide usage analytics"""
        if not self.initialized:
            raise Exception("Enterprise service not initialized")

        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=days)

        # Overall stats
        overall_query = f"""
        SELECT
            COUNT(*) as total_requests,
            COUNT(DISTINCT user_id) as unique_users,
            COUNT(DISTINCT agent_id) as unique_agents,
            COUNTIF(has_pii = true) as pii_detected_count,
            COUNTIF(status = 'blocked') as blocked_count,
            COUNTIF(status = 'passed') as passed_count
        FROM `{self.audit_table}`
        WHERE timestamp >= @start_date AND timestamp <= @end_date
        """

        # By department
        dept_query = f"""
        SELECT
            COALESCE(department, 'unknown') as department,
            COUNT(DISTINCT agent_id) as total_agents,
            COUNT(*) as total_requests,
            COUNT(DISTINCT user_id) as total_users,
            COUNTIF(has_pii = true) as pii_incidents,
            COUNTIF(status = 'blocked') as blocked_requests,
            AVG(processing_time_ms) as avg_response_time_ms
        FROM `{self.audit_table}`
        WHERE timestamp >= @start_date AND timestamp <= @end_date
        GROUP BY department
        ORDER BY total_requests DESC
        """

        # By agent
        agent_query = f"""
        SELECT
            agent_id,
            COUNT(*) as total_requests,
            COUNT(DISTINCT user_id) as unique_users,
            COUNTIF(has_pii = true) as pii_incidents,
            AVG(processing_time_ms) as avg_response_time_ms
        FROM `{self.audit_table}`
        WHERE timestamp >= @start_date AND timestamp <= @end_date
        GROUP BY agent_id
        ORDER BY total_requests DESC
        LIMIT 10
        """

        # By guardrail type
        guardrail_query = f"""
        SELECT
            guardrail_type,
            COUNT(*) as count
        FROM `{self.audit_table}`
        WHERE timestamp >= @start_date AND timestamp <= @end_date
        GROUP BY guardrail_type
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start_date", "TIMESTAMP", period_start),
                bigquery.ScalarQueryParameter("end_date", "TIMESTAMP", period_end),
            ]
        )

        try:
            # Execute queries
            overall_result = list(self.client.query(overall_query, job_config=job_config).result())[0]
            dept_results = list(self.client.query(dept_query, job_config=job_config).result())
            agent_results = list(self.client.query(agent_query, job_config=job_config).result())
            guardrail_results = list(self.client.query(guardrail_query, job_config=job_config).result())

            # Build department stats
            dept_stats = []
            for row in dept_results:
                dept_stats.append(DepartmentStats(
                    department=row.department,
                    total_agents=row.total_agents,
                    total_requests=row.total_requests,
                    total_users=row.total_users,
                    pii_incidents=row.pii_incidents,
                    blocked_requests=row.blocked_requests,
                    avg_response_time_ms=row.avg_response_time_ms or 0,
                    top_agents=[]
                ))

            # Build agent stats
            agent_stats = []
            for row in agent_results:
                agent_stats.append({
                    "agent_id": row.agent_id,
                    "total_requests": row.total_requests,
                    "unique_users": row.unique_users,
                    "pii_incidents": row.pii_incidents,
                    "avg_response_time_ms": row.avg_response_time_ms or 0
                })

            # Build guardrail stats
            guardrail_stats = {}
            for row in guardrail_results:
                guardrail_stats[row.guardrail_type] = row.count

            return UsageAnalytics(
                period_start=period_start,
                period_end=period_end,
                total_requests=overall_result.total_requests or 0,
                unique_users=overall_result.unique_users or 0,
                unique_agents=overall_result.unique_agents or 0,
                pii_detected_count=overall_result.pii_detected_count or 0,
                blocked_count=overall_result.blocked_count or 0,
                passed_count=overall_result.passed_count or 0,
                by_department=dept_stats,
                by_agent=agent_stats,
                by_guardrail=guardrail_stats
            )

        except Exception as e:
            logger.error(f"Error getting analytics: {e}")
            raise

    async def get_department_leaderboard(self) -> List[Dict[str, Any]]:
        """Get department usage leaderboard"""
        if not self.initialized:
            return []

        query = f"""
        SELECT
            COALESCE(department, 'unknown') as department,
            COUNT(*) as total_requests,
            COUNT(DISTINCT user_id) as unique_users,
            COUNT(DISTINCT agent_id) as unique_agents,
            COUNTIF(has_pii = true) as pii_incidents,
            ROUND(COUNTIF(has_pii = true) * 100.0 / COUNT(*), 2) as pii_rate
        FROM `{self.audit_table}`
        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
        GROUP BY department
        ORDER BY total_requests DESC
        """

        results = []
        try:
            for row in self.client.query(query).result():
                results.append({
                    "department": row.department,
                    "total_requests": row.total_requests,
                    "unique_users": row.unique_users,
                    "unique_agents": row.unique_agents,
                    "pii_incidents": row.pii_incidents,
                    "pii_rate": row.pii_rate
                })
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")

        return results


# Global instance
_enterprise_service: "EnterpriseService" = None  # type: ignore


def get_enterprise_service() -> EnterpriseService:
    """Get or create the Enterprise service instance"""
    global _enterprise_service
    if _enterprise_service is None:
        _enterprise_service = EnterpriseService()
    return _enterprise_service