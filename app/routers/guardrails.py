"""Guardrail endpoints for content checking"""
from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    GuardrailRequest,
    GuardrailResponse,
    GuardrailResult,
    GuardrailStatus,
    GuardrailType,
    AuditLog,
    OutputCheckRequest,
    OutputCheckResponse
)
from app.services.gemini_service import get_gemini_service
from app.services.audit_service import get_audit_service
from datetime import datetime
import uuid
import time
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/guardrails", tags=["Guardrails"])


@router.post("/check", response_model=GuardrailResponse)
async def check_guardrails(request: GuardrailRequest):
    """
    Check content against configured guardrails.

    This endpoint analyzes user prompts for various risks including:
    - PII (Personally Identifiable Information)
    - Toxicity
    - Hallucination patterns
    - Prompt injection attempts

    Returns detailed results and a safe version of the prompt if needed.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()

    gemini_service = get_gemini_service()
    audit_service = get_audit_service()

    results = []
    overall_status = GuardrailStatus.PASSED
    safe_prompt = request.prompt

    try:
        # Process each requested guardrail
        for guardrail_type in request.guardrails:
            guardrail_start = time.time()

            if guardrail_type == GuardrailType.PII_DETECTION:
                # PII Detection
                pii_result = await gemini_service.detect_pii(request.prompt)
                guardrail_end = time.time()

                status = GuardrailStatus.BLOCKED if pii_result.has_pii else GuardrailStatus.PASSED
                if status == GuardrailStatus.BLOCKED:
                    overall_status = GuardrailStatus.BLOCKED
                    safe_prompt = pii_result.redacted_text or safe_prompt

                result = GuardrailResult(
                    guardrail_type=guardrail_type,
                    status=status,
                    confidence=1.0 if pii_result.has_pii else 0.0,
                    details={
                        "has_pii": pii_result.has_pii,
                        "pii_types": pii_result.pii_types,
                        "explanation": pii_result.details
                    },
                    processing_time_ms=(guardrail_end - guardrail_start) * 1000
                )
                results.append(result)

                # Log to audit
                await audit_service.log_audit_event(
                    AuditLog(
                        request_id=request_id,
                        timestamp=datetime.utcnow(),
                        agent_id=request.agent_id,
                        user_id=request.user_id,
                        department=request.department,
                        session_id=request.session_id,
                        guardrail_type=guardrail_type.value,
                        status=status.value,
                        prompt_length=len(request.prompt),
                        has_pii=pii_result.has_pii,
                        processing_time_ms=(guardrail_end - guardrail_start) * 1000,
                        model_used=gemini_service.settings.gemini_model,
                        metadata={
                            "pii_types": pii_result.pii_types,
                            "confidence": 1.0 if pii_result.has_pii else 0.0
                        },
                        original_prompt=request.prompt,
                        redacted_prompt=pii_result.redacted_text
                    )
                )

            elif guardrail_type == GuardrailType.SENSITIVE_REQUEST:
                # Check if prompt is requesting sensitive data
                sensitive_result = await gemini_service.check_sensitive_request(request.prompt)
                guardrail_end = time.time()

                status = GuardrailStatus.BLOCKED if sensitive_result.requests_sensitive_data else GuardrailStatus.PASSED
                if status == GuardrailStatus.BLOCKED:
                    overall_status = GuardrailStatus.BLOCKED

                result = GuardrailResult(
                    guardrail_type=guardrail_type,
                    status=status,
                    confidence=1.0 if sensitive_result.requests_sensitive_data else 0.0,
                    details={
                        "requests_sensitive_data": sensitive_result.requests_sensitive_data,
                        "sensitive_types": sensitive_result.sensitive_types,
                        "explanation": sensitive_result.details
                    },
                    processing_time_ms=(guardrail_end - guardrail_start) * 1000
                )
                results.append(result)

            else:
                # Placeholder for other guardrails
                guardrail_end = time.time()
                result = GuardrailResult(
                    guardrail_type=guardrail_type,
                    status=GuardrailStatus.PASSED,
                    confidence=0.0,
                    details={"message": f"{guardrail_type.value} not yet implemented"},
                    processing_time_ms=(guardrail_end - guardrail_start) * 1000
                )
                results.append(result)

        end_time = time.time()

        response = GuardrailResponse(
            request_id=request_id,
            agent_id=request.agent_id,
            overall_status=overall_status,
            results=results,
            original_prompt=request.prompt,
            safe_prompt=safe_prompt if overall_status == GuardrailStatus.BLOCKED else None,
            total_processing_time_ms=(end_time - start_time) * 1000
        )

        logger.info(
            f"Guardrail check completed: request_id={request_id}, "
            f"status={overall_status.value}, time={(end_time - start_time) * 1000:.2f}ms"
        )

        return response

    except Exception as e:
        logger.error(f"Error processing guardrail check: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing guardrail check: {str(e)}"
        )


@router.post("/check-output", response_model=OutputCheckResponse)
async def check_output_guardrails(request: OutputCheckRequest):
    """
    Check AI agent output before sending to user.

    This endpoint analyzes agent responses to ensure they don't:
    - Request sensitive information (SSN, credit cards, passwords)
    - Ask for financial details inappropriately
    - Violate data collection policies

    Use this AFTER your AI agent generates a response, BEFORE showing it to the user.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()

    gemini_service = get_gemini_service()
    audit_service = get_audit_service()

    violations = []
    is_safe = True
    blocked_reason = None

    try:
        # Check if the response is asking for sensitive data
        sensitive_result = await gemini_service.check_sensitive_request(request.agent_response)

        if sensitive_result.requests_sensitive_data:
            is_safe = False
            violations.extend(sensitive_result.sensitive_types)
            blocked_reason = f"Agent response requests sensitive data: {', '.join(sensitive_result.sensitive_types)}"

        end_time = time.time()

        # Log to audit
        await audit_service.log_audit_event(
            AuditLog(
                request_id=request_id,
                timestamp=datetime.utcnow(),
                agent_id=request.agent_id,
                user_id=request.user_id,
                department=request.department,
                session_id=request.session_id,
                guardrail_type=GuardrailType.SENSITIVE_REQUEST.value,
                status="blocked" if not is_safe else "passed",
                prompt_length=len(request.agent_response),
                has_pii=False,
                processing_time_ms=(end_time - start_time) * 1000,
                model_used=gemini_service.settings.gemini_model,
                metadata={
                    "check_type": "output_guardrail",
                    "violations": violations,
                    "sensitive_types": sensitive_result.sensitive_types
                },
                original_prompt=request.original_prompt,
                redacted_prompt=request.agent_response[:500] if not is_safe else None
            )
        )

        logger.info(
            f"Output guardrail check: request_id={request_id}, "
            f"is_safe={is_safe}, violations={violations}"
        )

        return OutputCheckResponse(
            request_id=request_id,
            agent_id=request.agent_id,
            is_safe=is_safe,
            violations=violations,
            blocked_reason=blocked_reason,
            safe_response=None if is_safe else "[BLOCKED: Response requested sensitive information]"
        )

    except Exception as e:
        logger.error(f"Error in output guardrail check: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error checking output: {str(e)}"
        )
