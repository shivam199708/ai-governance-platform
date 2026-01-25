"""
Example test cases for the AI Governance Platform

Run this after starting the server to test PII detection
"""
import requests
import json

BASE_URL = "http://localhost:8080"


def test_health():
    """Test health endpoint"""
    print("\n1. Testing Health Check...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def test_pii_detection_positive():
    """Test PII detection with email"""
    print("\n2. Testing PII Detection (Email)...")
    payload = {
        "prompt": "My email is john.doe@company.com and I need help with my account.",
        "agent_id": "customer-support-bot",
        "user_id": "user123",
        "guardrails": ["pii_detection"]
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/guardrails/check",
        json=payload
    )

    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Overall Status: {result['overall_status']}")
    print(f"Original Prompt: {result['original_prompt']}")
    print(f"Safe Prompt: {result.get('safe_prompt', 'N/A')}")
    print(f"Processing Time: {result['total_processing_time_ms']:.2f}ms")
    print(f"Results: {json.dumps(result['results'], indent=2)}")


def test_pii_detection_phone():
    """Test PII detection with phone number"""
    print("\n3. Testing PII Detection (Phone Number)...")
    payload = {
        "prompt": "You can reach me at 555-123-4567 for urgent matters.",
        "agent_id": "customer-support-bot",
        "guardrails": ["pii_detection"]
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/guardrails/check",
        json=payload
    )

    result = response.json()
    print(f"Overall Status: {result['overall_status']}")
    print(f"Safe Prompt: {result.get('safe_prompt', 'N/A')}")


def test_pii_detection_negative():
    """Test PII detection with clean text"""
    print("\n4. Testing PII Detection (Clean Text)...")
    payload = {
        "prompt": "What is the weather like today? I need to plan my outdoor activities.",
        "agent_id": "general-assistant",
        "guardrails": ["pii_detection"]
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/guardrails/check",
        json=payload
    )

    result = response.json()
    print(f"Overall Status: {result['overall_status']}")
    print(f"Has Safe Prompt: {'Yes' if result.get('safe_prompt') else 'No'}")
    print(f"Processing Time: {result['total_processing_time_ms']:.2f}ms")


def test_multiple_pii():
    """Test PII detection with multiple PII types"""
    print("\n5. Testing Multiple PII Types...")
    payload = {
        "prompt": "Contact me at john@email.com or call 555-0123. My SSN is 123-45-6789.",
        "agent_id": "test-agent",
        "guardrails": ["pii_detection"]
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/guardrails/check",
        json=payload
    )

    result = response.json()
    print(f"Overall Status: {result['overall_status']}")
    print(f"Original: {result['original_prompt']}")
    print(f"Redacted: {result.get('safe_prompt', 'N/A')}")
    pii_types = result['results'][0]['details'].get('pii_types', [])
    print(f"PII Types Detected: {', '.join(pii_types)}")


if __name__ == "__main__":
    print("=" * 60)
    print("AI Governance Platform - Test Suite")
    print("=" * 60)

    try:
        test_health()
        test_pii_detection_positive()
        test_pii_detection_phone()
        test_pii_detection_negative()
        test_multiple_pii()

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("\nERROR: Could not connect to the server.")
        print("Make sure the server is running: python -m app.main")
    except Exception as e:
        print(f"\nERROR: {e}")
