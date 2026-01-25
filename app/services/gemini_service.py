"""Gemini AI service for guardrail checks"""
import os
from app.config import get_settings
from app.models.schemas import PIIDetectionResult, SensitiveRequestResult
import json
import re
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# Try to import Vertex AI (for GCP), fallback to Google GenAI (for API key)
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel as VertexModel, GenerationConfig as VertexConfig
    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False
    logger.warning("Vertex AI not available")

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("Google GenAI not available")


class GeminiService:
    """Service for interacting with Gemini models"""

    def __init__(self):
        self.settings = get_settings()
        self.initialized = False
        self.use_vertex = False

        # Try Google AI Studio API key first
        if self.settings.gemini_api_key and GENAI_AVAILABLE:
            try:
                genai.configure(api_key=self.settings.gemini_api_key)
                self.model = genai.GenerativeModel(self.settings.gemini_model)
                self.initialized = True
                self.use_vertex = False
                logger.info(f"Gemini service initialized with API key, model: {self.settings.gemini_model}")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini with API key: {e}")

        # Fallback to Vertex AI if API key not available
        if not self.initialized and VERTEX_AVAILABLE:
            try:
                vertexai.init(
                    project=self.settings.project_id,
                    location=self.settings.location
                )
                self.model = VertexModel(self.settings.gemini_model)
                self.initialized = True
                self.use_vertex = True
                logger.info(f"Gemini service initialized with Vertex AI, model: {self.settings.gemini_model}")
            except Exception as e:
                logger.warning(f"Failed to initialize Vertex AI: {e}")

        if not self.initialized:
            logger.warning("Gemini not initialized. Using regex fallback mode.")

    async def detect_pii(self, text: str) -> PIIDetectionResult:
        """
        Detect PII in the given text using Gemini.

        Args:
            text: The text to analyze for PII

        Returns:
            PIIDetectionResult with detection details and redacted text
        """
        if not self.initialized:
            return self._mock_pii_detection(text)

        try:
            prompt = f"""Analyze the following text for Personally Identifiable Information (PII).

Text to analyze:
"{text}"

Identify any PII such as:
- Email addresses
- Phone numbers
- Social Security Numbers
- Credit card numbers
- Street addresses
- Full names (when combined with other PII)
- Date of birth
- Driver's license numbers

Respond in JSON format:
{{
    "has_pii": true/false,
    "pii_types": ["email", "phone", etc.],
    "redacted_text": "text with PII replaced by [REDACTED_<TYPE>]",
    "details": "brief explanation"
}}

Be strict in detection. If unsure, flag it as PII."""

            if self.use_vertex:
                # Vertex AI configuration
                generation_config = VertexConfig(
                    temperature=self.settings.gemini_temperature,
                    max_output_tokens=1024,
                )
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
            else:
                # Google AI Studio configuration
                generation_config = {
                    'temperature': self.settings.gemini_temperature,
                    'max_output_tokens': 1024,
                }
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config
                )

            # Parse JSON response
            result_text = response.text.strip()

            # Extract JSON from markdown code blocks if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            result_data = json.loads(result_text)

            return PIIDetectionResult(
                has_pii=result_data.get("has_pii", False),
                pii_types=result_data.get("pii_types", []),
                redacted_text=result_data.get("redacted_text"),
                details=result_data.get("details")
            )

        except Exception as e:
            logger.error(f"Error in PII detection: {e}")
            # Fallback to regex-based detection
            return self._regex_pii_detection(text)

    def _regex_pii_detection(self, text: str) -> PIIDetectionResult:
        """Fallback regex-based PII detection"""
        pii_types = []
        redacted_text = text

        # Email detection
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if re.search(email_pattern, text):
            pii_types.append("email")
            redacted_text = re.sub(email_pattern, "[REDACTED_EMAIL]", redacted_text)

        # Phone number detection (US format)
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        if re.search(phone_pattern, text):
            pii_types.append("phone")
            redacted_text = re.sub(phone_pattern, "[REDACTED_PHONE]", redacted_text)

        # SSN detection
        ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
        if re.search(ssn_pattern, text):
            pii_types.append("ssn")
            redacted_text = re.sub(ssn_pattern, "[REDACTED_SSN]", redacted_text)

        # Credit card detection (basic)
        cc_pattern = r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'
        if re.search(cc_pattern, text):
            pii_types.append("credit_card")
            redacted_text = re.sub(cc_pattern, "[REDACTED_CC]", redacted_text)

        has_pii = len(pii_types) > 0

        return PIIDetectionResult(
            has_pii=has_pii,
            pii_types=pii_types,
            redacted_text=redacted_text if has_pii else None,
            details="Regex-based detection (fallback mode)" if has_pii else "No PII detected"
        )

    def _mock_pii_detection(self, text: str) -> PIIDetectionResult:
        """Mock PII detection for when Gemini is not initialized"""
        logger.info("Using mock PII detection")
        return self._regex_pii_detection(text)

    async def check_sensitive_request(self, text: str) -> SensitiveRequestResult:
        """
        Check if the text is REQUESTING sensitive information like SSN, credit cards, etc.
        This is for OUTPUT guardrails - blocking agents from asking users for sensitive data.
        """
        if not self.initialized:
            return self._regex_sensitive_request_check(text)

        try:
            prompt = f"""Analyze if the following text is REQUESTING or ASKING FOR sensitive personal information.

Text to analyze:
"{text}"

Check if the text asks the user to provide:
- Social Security Number (SSN)
- Credit card numbers or CVV
- Bank account numbers
- Passwords or PINs
- Driver's license numbers
- Passport numbers
- Tax ID numbers
- Full financial details

Respond in JSON format:
{{
    "requests_sensitive_data": true/false,
    "sensitive_types": ["ssn", "credit_card", "password", etc.],
    "details": "explanation of what sensitive data is being requested"
}}

Be STRICT. If the text asks for ANY sensitive financial or identity data, flag it."""

            if self.use_vertex:
                generation_config = VertexConfig(
                    temperature=self.settings.gemini_temperature,
                    max_output_tokens=512,
                )
                response = self.model.generate_content(prompt, generation_config=generation_config)
            else:
                generation_config = {
                    'temperature': self.settings.gemini_temperature,
                    'max_output_tokens': 512,
                }
                response = self.model.generate_content(prompt, generation_config=generation_config)

            result_text = response.text.strip()
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            result_data = json.loads(result_text)

            return SensitiveRequestResult(
                requests_sensitive_data=result_data.get("requests_sensitive_data", False),
                sensitive_types=result_data.get("sensitive_types", []),
                details=result_data.get("details")
            )

        except Exception as e:
            logger.error(f"Error in sensitive request check: {e}")
            return self._regex_sensitive_request_check(text)

    def _regex_sensitive_request_check(self, text: str) -> SensitiveRequestResult:
        """Fallback regex-based sensitive request detection"""
        text_lower = text.lower()
        sensitive_types = []

        # Check for requests for SSN
        ssn_patterns = [
            r'(provide|enter|give|share|what is|tell me).{0,30}(ssn|social security)',
            r'(ssn|social security).{0,20}(number|#)',
            r'your social security'
        ]
        for pattern in ssn_patterns:
            if re.search(pattern, text_lower):
                sensitive_types.append("ssn")
                break

        # Check for requests for credit card
        cc_patterns = [
            r'(provide|enter|give|share).{0,30}(credit card|card number|cvv|expir)',
            r'(credit card|debit card).{0,20}(number|details|info)',
            r'your (credit|debit) card'
        ]
        for pattern in cc_patterns:
            if re.search(pattern, text_lower):
                sensitive_types.append("credit_card")
                break

        # Check for requests for bank account
        bank_patterns = [
            r'(provide|enter|give|share).{0,30}(bank account|routing number|account number)',
            r'your bank.{0,20}(account|details|number)'
        ]
        for pattern in bank_patterns:
            if re.search(pattern, text_lower):
                sensitive_types.append("bank_account")
                break

        # Check for requests for passwords
        password_patterns = [
            r'(provide|enter|give|share|what is).{0,20}(password|pin|passcode)',
            r'your (password|pin)'
        ]
        for pattern in password_patterns:
            if re.search(pattern, text_lower):
                sensitive_types.append("password")
                break

        requests_sensitive = len(sensitive_types) > 0

        return SensitiveRequestResult(
            requests_sensitive_data=requests_sensitive,
            sensitive_types=sensitive_types,
            details=f"Detected request for: {', '.join(sensitive_types)}" if requests_sensitive else "No sensitive data requests detected"
        )


# Global instance
_gemini_service: "GeminiService" = None  # type: ignore


def get_gemini_service() -> GeminiService:
    """Get or create the Gemini service instance"""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
