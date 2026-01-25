"""Authentication endpoints for API key management"""
from fastapi import APIRouter, HTTPException, Header, Depends
from app.models.schemas import APIKeyCreate, APIKeyResponse
from app.services.auth_service import get_auth_service
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/keys", response_model=APIKeyResponse)
async def create_api_key(request: APIKeyCreate):
    """
    Create a new API key for an agent.

    IMPORTANT: The API key is only shown ONCE in the response.
    Store it securely - it cannot be retrieved again.
    """
    auth_service = get_auth_service()

    try:
        result = await auth_service.create_api_key(request)
        logger.info(f"API key created for agent {request.agent_id}: {result.key_id}")
        return result

    except Exception as e:
        logger.error(f"Error creating API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error creating API key: {str(e)}"
        )


@router.get("/keys/{agent_id}")
async def list_agent_keys(agent_id: str) -> List[Dict[str, Any]]:
    """
    List all API keys for an agent.

    Note: The actual key values are NOT returned for security.
    Only key_id, prefix, and metadata are shown.
    """
    auth_service = get_auth_service()

    try:
        keys = await auth_service.list_agent_keys(agent_id)
        return keys

    except Exception as e:
        logger.error(f"Error listing API keys: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error listing API keys: {str(e)}"
        )


@router.delete("/keys/{key_id}")
async def revoke_api_key(key_id: str) -> Dict[str, Any]:
    """
    Revoke an API key.

    The key will be immediately invalidated and cannot be used.
    """
    auth_service = get_auth_service()

    try:
        success = await auth_service.revoke_api_key(key_id)
        if success:
            logger.info(f"API key revoked: {key_id}")
            return {"status": "revoked", "key_id": key_id}
        else:
            raise HTTPException(status_code=404, detail="Key not found or already revoked")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error revoking API key: {str(e)}"
        )


@router.post("/validate")
async def validate_api_key(
    x_api_key: str = Header(..., alias="X-API-Key", description="API key to validate")
) -> Dict[str, Any]:
    """
    Validate an API key.

    Send the API key in the X-API-Key header.
    Returns agent info if valid, 401 if invalid.
    """
    auth_service = get_auth_service()

    try:
        result = await auth_service.validate_api_key(x_api_key)

        if result is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired API key"
            )

        return {
            "valid": True,
            "agent_id": result["agent_id"],
            "key_id": result.get("key_id")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error validating API key: {str(e)}"
        )


# Helper dependency for protected routes
async def require_api_key(
    x_api_key: str = Header(..., alias="X-API-Key")
) -> Dict[str, Any]:
    """Dependency to require valid API key for protected routes"""
    auth_service = get_auth_service()
    result = await auth_service.validate_api_key(x_api_key)

    if result is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired API key"
        )

    return result