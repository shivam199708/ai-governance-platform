"""Feedback endpoints for agent improvement tracking"""
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import FeedbackSubmit, FeedbackResponse
from app.services.feedback_service import get_feedback_service
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/feedback", tags=["Feedback"])


@router.post("/submit", response_model=FeedbackResponse)
async def submit_feedback(feedback: FeedbackSubmit):
    """
    Submit feedback for an agent interaction.

    Use this to track:
    - User ratings (helpful, not_helpful, incorrect, inappropriate)
    - Comments and suggestions for agent improvement
    - Tags for categorizing feedback (accuracy, speed, tone, etc.)
    """
    feedback_service = get_feedback_service()

    try:
        result = await feedback_service.submit_feedback(feedback)
        logger.info(f"Feedback submitted: {result.feedback_id} for agent {feedback.agent_id}")
        return result

    except Exception as e:
        logger.error(f"Error submitting feedback: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error submitting feedback: {str(e)}"
        )


@router.get("/agent/{agent_id}/summary")
async def get_agent_feedback_summary(
    agent_id: str,
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze")
) -> Dict[str, Any]:
    """
    Get feedback summary for a specific agent.

    Returns:
    - Total feedback count
    - Rating breakdown (helpful, not_helpful, etc.)
    - Helpful rate percentage
    - Unique users who provided feedback
    """
    feedback_service = get_feedback_service()

    try:
        summary = await feedback_service.get_agent_feedback_summary(agent_id, days)
        if not summary:
            return {
                "agent_id": agent_id,
                "total_feedback": 0,
                "message": "No feedback found for this agent"
            }
        return summary

    except Exception as e:
        logger.error(f"Error getting feedback summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error getting feedback summary: {str(e)}"
        )


@router.get("/suggestions")
async def get_recent_suggestions(
    agent_id: Optional[str] = Query(default=None, description="Filter by agent ID"),
    limit: int = Query(default=20, ge=1, le=100, description="Number of suggestions to return")
) -> List[Dict[str, Any]]:
    """
    Get recent improvement suggestions.

    Returns suggestions with non-null text, useful for:
    - Identifying common issues
    - Prioritizing agent improvements
    - Understanding user needs
    """
    feedback_service = get_feedback_service()

    try:
        suggestions = await feedback_service.get_recent_suggestions(agent_id, limit)
        return suggestions

    except Exception as e:
        logger.error(f"Error getting suggestions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error getting suggestions: {str(e)}"
        )