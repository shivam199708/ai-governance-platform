"""Demo Agent Service - A working AI agent that integrates with governance guardrails"""
import google.generativeai as genai
from app.config import get_settings
from app.services.gemini_service import get_gemini_service
from app.services.audit_service import get_audit_service
from app.services.conversation_service import get_conversation_service
from app.models.schemas import AuditLog, GuardrailType
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging
import uuid

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    role: str  # "user" or "assistant"
    content: str
    blocked: bool = False
    has_pii: bool = False


@dataclass
class ChatResponse:
    message: str
    was_input_blocked: bool
    was_output_blocked: bool
    input_pii_detected: List[str]
    output_violations: List[str]
    session_id: str
    request_id: str


class DemoAgentService:
    """
    A demo Support Agent that:
    1. Checks user input through governance guardrails
    2. Generates response using Gemini
    3. Checks output through governance guardrails
    4. Logs everything for compliance
    """

    SYSTEM_PROMPT = """You are a helpful Customer Support Agent for a technology company.

Your role:
- Help customers with their inquiries about products, orders, and services
- Collect relevant information to assist them (name, order number, issue description)
- Be friendly, professional, and concise

IMPORTANT RULES:
- NEVER ask for sensitive information like SSN, credit card numbers, bank accounts, or passwords
- If a customer shares sensitive data, acknowledge but don't repeat it
- Focus on resolving their issue efficiently

Example conversation:
User: Hi, I have a problem with my order
Agent: Hello! I'd be happy to help you with your order. Could you please provide your order number so I can look into this for you?
"""

    def __init__(self):
        self.settings = get_settings()
        self.gemini_service = get_gemini_service()
        self.audit_service = get_audit_service()
        self.conversation_service = get_conversation_service()

        # Configure Gemini for chat
        genai.configure(api_key=self.settings.gemini_api_key)
        self.model = genai.GenerativeModel(model_name=self.settings.gemini_model)

        # Store active chat sessions
        self.sessions: Dict[str, Any] = {}

        logger.info("Demo Agent Service initialized")

    def _get_or_create_session(self, session_id: Optional[str] = None) -> str:
        """Get existing session or create new one"""
        if session_id and session_id in self.sessions:
            return session_id

        new_session_id = session_id or str(uuid.uuid4())
        # Start chat with system prompt as first message in history
        self.sessions[new_session_id] = {
            "chat": self.model.start_chat(history=[
                {"role": "user", "parts": [f"System: {self.SYSTEM_PROMPT}"]},
                {"role": "model", "parts": ["Understood. I am ready to help as a Customer Support Agent. I will never ask for sensitive information like SSN, credit cards, or passwords."]}
            ]),
            "messages": [],
            "created_at": datetime.utcnow()
        }
        return new_session_id

    async def chat(
        self,
        user_message: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> ChatResponse:
        """
        Process a chat message through the full governance pipeline:
        1. Check input for PII
        2. Generate response
        3. Check output for sensitive requests
        4. Return safe response
        """
        request_id = str(uuid.uuid4())
        session_id = self._get_or_create_session(session_id)
        session = self.sessions[session_id]

        input_blocked = False
        output_blocked = False
        input_pii_types = []
        output_violations = []
        final_response = ""

        try:
            # ============ STEP 1: Check Input for PII ============
            logger.info(f"[{request_id}] Checking input for PII...")
            pii_result = await self.gemini_service.detect_pii(user_message)

            input_pii_types = pii_result.pii_types
            safe_prompt = pii_result.redacted_text if pii_result.has_pii else user_message

            if pii_result.has_pii:
                logger.info(f"[{request_id}] PII detected: {pii_result.pii_types}")
                # Log PII detection
                await self.audit_service.log_audit_event(
                    AuditLog(
                        request_id=request_id,
                        timestamp=datetime.utcnow(),
                        agent_id="support-agent-001",
                        user_id=user_id,
                        department="support",
                        session_id=session_id,
                        guardrail_type=GuardrailType.PII_DETECTION.value,
                        status="flagged",
                        prompt_length=len(user_message),
                        has_pii=True,
                        processing_time_ms=0,
                        model_used=self.settings.gemini_model,
                        metadata={"pii_types": pii_result.pii_types},
                        original_prompt=user_message,
                        redacted_prompt=pii_result.redacted_text
                    )
                )

            # Store user message
            session["messages"].append(ChatMessage(
                role="user",
                content=user_message,
                has_pii=pii_result.has_pii
            ))

            # ============ STEP 2: Generate Response ============
            logger.info(f"[{request_id}] Generating agent response...")

            # Use the safe (redacted) prompt for generation
            chat_response = session["chat"].send_message(safe_prompt)
            agent_response = chat_response.text

            logger.info(f"[{request_id}] Agent response generated: {agent_response[:100]}...")

            # ============ STEP 3: Check Output for Sensitive Requests ============
            logger.info(f"[{request_id}] Checking output for sensitive requests...")
            sensitive_result = await self.gemini_service.check_sensitive_request(agent_response)

            if sensitive_result.requests_sensitive_data:
                output_blocked = True
                output_violations = sensitive_result.sensitive_types
                final_response = "I apologize, but I cannot assist with that request. How else can I help you today?"

                logger.warning(f"[{request_id}] Output BLOCKED: {sensitive_result.sensitive_types}")

                # Log blocked output
                await self.audit_service.log_audit_event(
                    AuditLog(
                        request_id=request_id,
                        timestamp=datetime.utcnow(),
                        agent_id="support-agent-001",
                        user_id=user_id,
                        department="support",
                        session_id=session_id,
                        guardrail_type=GuardrailType.SENSITIVE_REQUEST.value,
                        status="blocked",
                        prompt_length=len(agent_response),
                        has_pii=False,
                        processing_time_ms=0,
                        model_used=self.settings.gemini_model,
                        metadata={
                            "check_type": "output_guardrail",
                            "violations": output_violations,
                            "original_response": agent_response[:500]
                        },
                        original_prompt=user_message,
                        redacted_prompt=agent_response[:500]
                    )
                )
            else:
                final_response = agent_response
                logger.info(f"[{request_id}] Output passed guardrails")

            # Store agent response
            session["messages"].append(ChatMessage(
                role="assistant",
                content=final_response,
                blocked=output_blocked
            ))

            return ChatResponse(
                message=final_response,
                was_input_blocked=input_blocked,
                was_output_blocked=output_blocked,
                input_pii_detected=input_pii_types,
                output_violations=output_violations,
                session_id=session_id,
                request_id=request_id
            )

        except Exception as e:
            logger.error(f"[{request_id}] Error in chat: {e}", exc_info=True)
            return ChatResponse(
                message="I'm sorry, I encountered an error. Please try again.",
                was_input_blocked=False,
                was_output_blocked=False,
                input_pii_detected=[],
                output_violations=[],
                session_id=session_id,
                request_id=request_id
            )

    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get chat history for a session"""
        if session_id not in self.sessions:
            return []

        return [
            {
                "role": msg.role,
                "content": msg.content,
                "blocked": msg.blocked,
                "has_pii": msg.has_pii
            }
            for msg in self.sessions[session_id]["messages"]
        ]

    def clear_session(self, session_id: str):
        """Clear a chat session"""
        if session_id in self.sessions:
            del self.sessions[session_id]


# Global instance
_demo_agent_service: Optional[DemoAgentService] = None


def get_demo_agent_service() -> DemoAgentService:
    """Get or create the Demo Agent service instance"""
    global _demo_agent_service
    if _demo_agent_service is None:
        _demo_agent_service = DemoAgentService()
    return _demo_agent_service