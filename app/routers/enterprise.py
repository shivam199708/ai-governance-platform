"""Enterprise endpoints for agent management and analytics"""
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import (
    AgentRegister,
    AgentInfo,
    UsageAnalytics,
)
from app.services.enterprise_service import get_enterprise_service
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/enterprise", tags=["Enterprise"])


@router.post("/agents", response_model=AgentInfo)
async def register_agent(agent: AgentRegister):
    """
    Register a new AI agent in the governance platform.

    Each team/department must register their AI agents before using the guardrails API.
    This enables tracking, analytics, and compliance reporting.
    """
    enterprise_service = get_enterprise_service()

    try:
        return await enterprise_service.register_agent(agent)
    except Exception as e:
        logger.error(f"Error registering agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents", response_model=List[AgentInfo])
async def list_agents(department: Optional[str] = Query(None, description="Filter by department")):
    """
    List all registered AI agents.

    Optionally filter by department to see only agents owned by a specific team.
    """
    enterprise_service = get_enterprise_service()
    return await enterprise_service.list_agents(department)


@router.get("/agents/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str):
    """
    Get details and usage statistics for a specific agent.
    """
    enterprise_service = get_enterprise_service()
    agent = await enterprise_service.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    return agent


@router.get("/analytics", response_model=UsageAnalytics)
async def get_analytics(days: int = Query(default=7, ge=1, le=90, description="Number of days to analyze")):
    """
    Get enterprise-wide usage analytics.

    Returns aggregated statistics including:
    - Total requests and unique users
    - PII detection incidents
    - Usage breakdown by department and agent
    - Guardrail type distribution
    """
    enterprise_service = get_enterprise_service()

    try:
        return await enterprise_service.get_usage_analytics(days)
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leaderboard")
async def get_department_leaderboard():
    """
    Get department usage leaderboard for the last 30 days.

    Shows which departments are using AI agents most actively
    and their PII incident rates.
    """
    enterprise_service = get_enterprise_service()
    return await enterprise_service.get_department_leaderboard()


@router.get("/dashboard-data")
async def get_dashboard_data(days: int = Query(default=7, ge=1, le=90)):
    """
    Get all data needed for the dashboard in a single call.

    Combines analytics, leaderboard, and agent list for efficient dashboard loading.
    """
    enterprise_service = get_enterprise_service()

    try:
        analytics = await enterprise_service.get_usage_analytics(days)
        leaderboard = await enterprise_service.get_department_leaderboard()
        agents = await enterprise_service.list_agents()

        return {
            "analytics": analytics,
            "leaderboard": leaderboard,
            "agents": agents,
            "summary": {
                "total_agents": len(agents),
                "active_departments": len(set(a.department for a in agents)),
                "total_requests_period": analytics.total_requests,
                "pii_incident_rate": round(
                    (analytics.pii_detected_count / analytics.total_requests * 100)
                    if analytics.total_requests > 0 else 0,
                    2
                )
            }
        }
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))