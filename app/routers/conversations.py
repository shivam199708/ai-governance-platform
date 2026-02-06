"""Conversation tracking endpoints for session-based logging"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.services.conversation_service import get_conversation_service
from typing import List, Dict, Any, Optional
from enum import Enum
import logging


class MessageRole(str, Enum):
    """Valid message roles"""
    USER = "user"
    ASSISTANT = "assistant"


class ConversationStatus(str, Enum):
    """Valid conversation statuses"""
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    ERROR = "error"

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/conversations", tags=["Conversations"])


# Request/Response Models
class StartConversationRequest(BaseModel):
    agent_id: str = Field(..., description="Agent handling this conversation")
    user_id: Optional[str] = Field(default=None, description="User in the conversation")
    department: Optional[str] = Field(default=None, description="User's department")
    session_id: Optional[str] = Field(default=None, description="Custom session ID (auto-generated if not provided)")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class AddMessageRequest(BaseModel):
    session_id: str = Field(..., description="Conversation session ID")
    agent_id: str = Field(..., description="Agent ID")
    role: MessageRole = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    turn_number: int = Field(..., ge=1, le=10000, description="Turn number in conversation (1, 2, 3...)")
    has_pii: bool = Field(default=False, description="Whether message contains PII")
    was_blocked: bool = Field(default=False, description="Whether message was blocked by guardrails")
    guardrail_result: Optional[Dict[str, Any]] = Field(default=None, description="Guardrail check result")
    processing_time_ms: Optional[float] = Field(default=None, description="Processing time")


class EndConversationRequest(BaseModel):
    session_id: str = Field(..., description="Conversation session ID")
    status: ConversationStatus = Field(default=ConversationStatus.COMPLETED, description="Final status: completed, abandoned, error")


@router.post("/start")
async def start_conversation(request: StartConversationRequest) -> Dict[str, Any]:
    """
    Start a new conversation session.

    Call this when a user begins interacting with an agent.
    Returns a session_id to use for subsequent messages.
    """
    conversation_service = get_conversation_service()

    try:
        session_id = await conversation_service.start_conversation(
            agent_id=request.agent_id,
            user_id=request.user_id,
            department=request.department,
            session_id=request.session_id,
            metadata=request.metadata
        )

        return {
            "session_id": session_id,
            "agent_id": request.agent_id,
            "status": "active",
            "message": "Conversation started"
        }

    except Exception as e:
        logger.error(f"Error starting conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message")
async def add_message(request: AddMessageRequest) -> Dict[str, Any]:
    """
    Add a message to an existing conversation.

    Call this for EACH user input and agent response.
    Include guardrail results if the message was checked.
    """
    conversation_service = get_conversation_service()

    try:
        message_id = await conversation_service.add_message(
            session_id=request.session_id,
            agent_id=request.agent_id,
            role=request.role.value,
            content=request.content,
            turn_number=request.turn_number,
            has_pii=request.has_pii,
            was_blocked=request.was_blocked,
            guardrail_result=request.guardrail_result,
            processing_time_ms=request.processing_time_ms
        )

        return {
            "message_id": message_id,
            "session_id": request.session_id,
            "turn_number": request.turn_number,
            "role": request.role,
            "status": "recorded"
        }

    except Exception as e:
        logger.error(f"Error adding message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/end")
async def end_conversation(request: EndConversationRequest) -> Dict[str, Any]:
    """
    End a conversation session.

    Call this when the conversation is complete or abandoned.
    """
    conversation_service = get_conversation_service()

    try:
        await conversation_service.end_conversation(
            session_id=request.session_id,
            status=request.status.value
        )

        return {
            "session_id": request.session_id,
            "status": request.status,
            "message": "Conversation ended"
        }

    except Exception as e:
        logger.error(f"Error ending conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}")
async def get_conversation(session_id: str) -> Dict[str, Any]:
    """
    Get a full conversation with all messages.

    Returns conversation metadata and ordered list of messages.
    """
    conversation_service = get_conversation_service()

    try:
        conversation = await conversation_service.get_conversation(session_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return conversation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/training")
async def export_training_data(
    agent_id: Optional[str] = Query(default=None, description="Filter by agent"),
    days: int = Query(default=30, ge=1, le=365, description="Days of data to export"),
    include_pii: bool = Query(default=False, description="Include conversations with PII incidents"),
    only_with_feedback: bool = Query(default=False, description="Only conversations with user feedback"),
    min_messages: int = Query(default=2, ge=1, le=1000, description="Minimum messages per conversation")
) -> Dict[str, Any]:
    """
    Export conversations for model training/fine-tuning.

    Returns filtered conversations in a training-friendly format.
    Use this endpoint for:
    - Monthly retraining data exports
    - Creating fine-tuning datasets
    - Analyzing conversation patterns
    """
    conversation_service = get_conversation_service()

    try:
        conversations = await conversation_service.get_training_export(
            agent_id=agent_id,
            days=days,
            include_pii_incidents=include_pii,
            only_with_feedback=only_with_feedback,
            min_messages=min_messages
        )

        return {
            "export_params": {
                "agent_id": agent_id,
                "days": days,
                "include_pii": include_pii,
                "only_with_feedback": only_with_feedback,
                "min_messages": min_messages
            },
            "total_conversations": len(conversations),
            "conversations": conversations
        }

    except Exception as e:
        logger.error(f"Error exporting training data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))