"""
AI Governance SDK - Lightweight client for teams to integrate governance into their agents.

Install: pip install requests
Usage:
    from ai_governance import GovernanceClient

    gov = GovernanceClient(
        api_key="gov_xxx",
        agent_id="my-agent",
        governance_url="https://governance.company.com"
    )

    # Check input before sending to LLM
    result = gov.check_input("user message here")

    # Check output before showing to user
    result = gov.check_output("agent response here")
"""

import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from functools import wraps
import time
import uuid


@dataclass
class InputCheckResult:
    """Result of input guardrail check"""
    request_id: str
    passed: bool
    blocked: bool
    has_pii: bool
    pii_types: List[str]
    safe_prompt: Optional[str]  # Redacted version if PII found
    original_prompt: str


@dataclass
class OutputCheckResult:
    """Result of output guardrail check"""
    request_id: str
    is_safe: bool
    blocked: bool
    violations: List[str]
    blocked_reason: Optional[str]


@dataclass
class ConversationSession:
    """Active conversation session"""
    session_id: str
    agent_id: str
    turn_number: int = 0


class GovernanceClient:
    """
    AI Governance client for integrating guardrails into any AI agent.

    This SDK allows any team to:
    - Check user inputs for PII before sending to their LLM
    - Check agent outputs before showing to users
    - Track full conversations for compliance and training
    - Submit feedback for agent improvement

    The SDK only sends prompts/responses to the governance API.
    Your LLM code, model choice, and business logic remain private.
    """

    def __init__(
        self,
        api_key: str,
        agent_id: str,
        governance_url: str = "http://localhost:8080",
        department: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize the governance client.

        Args:
            api_key: Your agent's API key (get from /api/v1/auth/keys)
            agent_id: Your registered agent ID
            governance_url: URL of the governance API
            department: Your department (for analytics)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.agent_id = agent_id
        self.base_url = governance_url.rstrip("/")
        self.department = department
        self.timeout = timeout
        self.session: Optional[ConversationSession] = None

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }

    def _post(self, endpoint: str, data: Dict) -> Dict:
        """Make POST request to governance API"""
        url = f"{self.base_url}{endpoint}"
        response = requests.post(
            url,
            json=data,
            headers=self._headers(),
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    # ==================== INPUT GUARDRAILS ====================

    def check_input(
        self,
        prompt: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        guardrails: List[str] = None
    ) -> InputCheckResult:
        """
        Check user input before sending to your LLM.

        Args:
            prompt: The user's message/prompt
            user_id: Optional user identifier
            session_id: Optional session ID for conversation tracking
            guardrails: List of guardrails to apply (default: ["pii_detection"])

        Returns:
            InputCheckResult with pass/block status and safe prompt

        Example:
            result = gov.check_input("My SSN is 123-45-6789")
            if result.blocked:
                return "I detected sensitive information in your message"
            # Use result.safe_prompt which has PII redacted
            response = my_llm.generate(result.safe_prompt)
        """
        if guardrails is None:
            guardrails = ["pii_detection"]

        data = {
            "prompt": prompt,
            "agent_id": self.agent_id,
            "user_id": user_id,
            "department": self.department,
            "session_id": session_id or (self.session.session_id if self.session else None),
            "guardrails": guardrails
        }

        result = self._post("/api/v1/guardrails/check", data)

        # Find PII result
        has_pii = False
        pii_types = []
        for r in result.get("results", []):
            if r.get("guardrail_type") == "pii_detection":
                details = r.get("details", {})
                has_pii = details.get("has_pii", False)
                pii_types = details.get("pii_types", [])

        return InputCheckResult(
            request_id=result["request_id"],
            passed=result["overall_status"] == "passed",
            blocked=result["overall_status"] == "blocked",
            has_pii=has_pii,
            pii_types=pii_types,
            safe_prompt=result.get("safe_prompt") or prompt,
            original_prompt=prompt
        )

    # ==================== OUTPUT GUARDRAILS ====================

    def check_output(
        self,
        agent_response: str,
        user_id: Optional[str] = None,
        original_prompt: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> OutputCheckResult:
        """
        Check agent output before showing to user.

        This blocks responses that ask users for sensitive data like:
        - Social Security Numbers
        - Credit card numbers
        - Bank account details
        - Passwords

        Args:
            agent_response: Your LLM's generated response
            user_id: Optional user identifier
            original_prompt: The original user prompt (for context)
            session_id: Optional session ID

        Returns:
            OutputCheckResult with safe/blocked status

        Example:
            response = my_llm.generate(user_input)
            result = gov.check_output(response)
            if result.blocked:
                return "I cannot ask for that information"
            return response
        """
        data = {
            "agent_id": self.agent_id,
            "user_id": user_id,
            "department": self.department,
            "session_id": session_id or (self.session.session_id if self.session else None),
            "agent_response": agent_response,
            "original_prompt": original_prompt
        }

        result = self._post("/api/v1/guardrails/check-output", data)

        return OutputCheckResult(
            request_id=result["request_id"],
            is_safe=result["is_safe"],
            blocked=not result["is_safe"],
            violations=result.get("violations", []),
            blocked_reason=result.get("blocked_reason")
        )

    # ==================== CONVERSATION TRACKING ====================

    def start_conversation(
        self,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> ConversationSession:
        """
        Start a new conversation session for tracking.

        Call this when a user starts chatting with your agent.

        Args:
            user_id: Optional user identifier
            metadata: Optional metadata (channel, priority, etc.)

        Returns:
            ConversationSession to use for logging messages
        """
        data = {
            "agent_id": self.agent_id,
            "user_id": user_id,
            "department": self.department,
            "metadata": metadata
        }

        result = self._post("/api/v1/conversations/start", data)

        self.session = ConversationSession(
            session_id=result["session_id"],
            agent_id=self.agent_id,
            turn_number=0
        )

        return self.session

    def log_message(
        self,
        role: str,
        content: str,
        has_pii: bool = False,
        was_blocked: bool = False,
        guardrail_result: Optional[Dict] = None,
        processing_time_ms: Optional[float] = None
    ) -> str:
        """
        Log a message in the current conversation.

        Call this for EACH user message and agent response.

        Args:
            role: "user" or "assistant"
            content: The message content
            has_pii: Whether PII was detected
            was_blocked: Whether the message was blocked
            guardrail_result: Optional guardrail check result
            processing_time_ms: Optional processing time

        Returns:
            message_id
        """
        if not self.session:
            raise ValueError("No active conversation. Call start_conversation() first.")

        if role == "user":
            self.session.turn_number += 1

        data = {
            "session_id": self.session.session_id,
            "agent_id": self.agent_id,
            "role": role,
            "content": content,
            "turn_number": self.session.turn_number,
            "has_pii": has_pii,
            "was_blocked": was_blocked,
            "guardrail_result": guardrail_result,
            "processing_time_ms": processing_time_ms
        }

        result = self._post("/api/v1/conversations/message", data)
        return result["message_id"]

    def end_conversation(self, status: str = "completed"):
        """
        End the current conversation session.

        Args:
            status: "completed", "abandoned", or "error"
        """
        if not self.session:
            return

        data = {
            "session_id": self.session.session_id,
            "status": status
        }

        self._post("/api/v1/conversations/end", data)
        self.session = None

    # ==================== FEEDBACK ====================

    def submit_feedback(
        self,
        request_id: str,
        rating: str,
        user_id: Optional[str] = None,
        comment: Optional[str] = None,
        suggestion: Optional[str] = None,
        tags: List[str] = None
    ) -> str:
        """
        Submit feedback for an agent response.

        Args:
            request_id: The request_id from check_input or check_output
            rating: "helpful", "not_helpful", "incorrect", "inappropriate"
            user_id: Optional user who gave feedback
            comment: Optional comment
            suggestion: Optional improvement suggestion
            tags: Optional tags like ["accuracy", "speed", "tone"]

        Returns:
            feedback_id
        """
        data = {
            "request_id": request_id,
            "agent_id": self.agent_id,
            "user_id": user_id,
            "rating": rating,
            "comment": comment,
            "suggestion": suggestion,
            "tags": tags or []
        }

        result = self._post("/api/v1/feedback/submit", data)
        return result["feedback_id"]

    # ==================== DECORATOR FOR EASY INTEGRATION ====================

    def track(self, func):
        """
        Decorator to automatically track a chat function.

        Example:
            @gov.track
            def chat(user_input: str) -> str:
                return my_llm.generate(user_input)

            # Now every call is automatically:
            # 1. Input checked for PII
            # 2. Logged to conversation
            # 3. Output checked before return
        """
        @wraps(func)
        def wrapper(user_input: str, *args, **kwargs) -> str:
            # Start conversation if not active
            if not self.session:
                self.start_conversation()

            # Check input
            input_result = self.check_input(user_input)

            # Log user message
            self.log_message(
                role="user",
                content=user_input,
                has_pii=input_result.has_pii,
                was_blocked=input_result.blocked
            )

            if input_result.blocked:
                blocked_response = "I detected sensitive information. Please rephrase without personal data."
                self.log_message(role="assistant", content=blocked_response, was_blocked=True)
                return blocked_response

            # Call the actual function with safe prompt
            start = time.time()
            response = func(input_result.safe_prompt, *args, **kwargs)
            processing_time = (time.time() - start) * 1000

            # Check output
            output_result = self.check_output(response, original_prompt=user_input)

            if output_result.blocked:
                blocked_response = "I cannot provide that information."
                self.log_message(
                    role="assistant",
                    content=blocked_response,
                    was_blocked=True,
                    processing_time_ms=processing_time
                )
                return blocked_response

            # Log successful response
            self.log_message(
                role="assistant",
                content=response,
                processing_time_ms=processing_time
            )

            return response

        return wrapper


# ==================== ASYNC VERSION ====================

class AsyncGovernanceClient(GovernanceClient):
    """Async version for FastAPI/async applications"""

    async def _post_async(self, endpoint: str, data: Dict) -> Dict:
        """Make async POST request"""
        import aiohttp
        url = f"{self.base_url}{endpoint}"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=data,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def check_input_async(self, prompt: str, **kwargs) -> InputCheckResult:
        """Async version of check_input"""
        # Implementation similar to sync but using _post_async
        pass  # Would implement full async version

    async def check_output_async(self, agent_response: str, **kwargs) -> OutputCheckResult:
        """Async version of check_output"""
        pass  # Would implement full async version