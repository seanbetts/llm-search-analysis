"""Test script for error handling and logging.

This script tests various error scenarios to ensure custom exceptions,
error codes, and logging middleware work correctly.
"""

import requests
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"


def print_response(title: str, response: requests.Response):
  """Print formatted response details."""
  print(f"\n{'=' * 80}")
  print(f"TEST: {title}")
  print(f"{'=' * 80}")
  print(f"Status Code: {response.status_code}")
  print(f"Correlation ID: {response.headers.get('X-Correlation-ID', 'N/A')}")
  print(f"\nResponse Body:")
  try:
    print(json.dumps(response.json(), indent=2))
  except:
    print(response.text)
  print(f"{'=' * 80}\n")


def test_health_check():
  """Test health check endpoint (should succeed)."""
  response = requests.get(f"{BASE_URL}/health")
  print_response("Health Check (Success Case)", response)
  assert response.status_code == 200
  assert "X-Correlation-ID" in response.headers


def test_validation_error():
  """Test Pydantic validation error (missing required fields)."""
  response = requests.post(
    f"{API_V1}/interactions/send",
    json={}  # Missing required fields: prompt, model
  )
  print_response("Validation Error (Missing Fields)", response)
  assert response.status_code == 422
  assert "X-Correlation-ID" in response.headers
  data = response.json()
  assert data["error"]["code"] == "VALIDATION_ERROR"
  assert "errors" in data["error"]["details"]


def test_model_not_supported():
  """Test invalid model error."""
  response = requests.post(
    f"{API_V1}/interactions/send",
    json={
      "prompt": "What is the capital of France?",
      "provider": "openai",
      "model": "invalid-model-12345"
    }
  )
  print_response("Model Not Supported Error", response)
  assert response.status_code == 400
  assert "X-Correlation-ID" in response.headers
  data = response.json()
  assert data["error"]["code"] == "INVALID_REQUEST"
  assert "invalid-model-12345" in data["error"]["message"]


def test_interaction_not_found():
  """Test resource not found error."""
  response = requests.get(f"{API_V1}/interactions/999999")
  print_response("Interaction Not Found Error", response)
  assert response.status_code == 404
  assert "X-Correlation-ID" in response.headers
  data = response.json()
  assert data["error"]["code"] == "RESOURCE_NOT_FOUND"
  assert "999999" in data["error"]["message"]


def test_recent_interactions_success():
  """Test successful API call with logging."""
  response = requests.get(f"{API_V1}/interactions/recent?limit=5")
  print_response("Recent Interactions (Success Case)", response)
  assert response.status_code == 200
  assert "X-Correlation-ID" in response.headers


def test_correlation_id_propagation():
  """Test that custom correlation IDs are preserved."""
  custom_correlation_id = "test-correlation-12345"
  response = requests.get(
    f"{BASE_URL}/health",
    headers={"X-Correlation-ID": custom_correlation_id}
  )
  print_response("Correlation ID Propagation", response)
  assert response.status_code == 200
  assert response.headers.get("X-Correlation-ID") == custom_correlation_id


def main():
  """Run all error handling tests."""
  print("\n" + "=" * 80)
  print("ERROR HANDLING & LOGGING TEST SUITE")
  print("=" * 80)

  tests = [
    ("Health Check", test_health_check),
    ("Validation Error", test_validation_error),
    ("Model Not Supported", test_model_not_supported),
    ("Interaction Not Found", test_interaction_not_found),
    ("Recent Interactions Success", test_recent_interactions_success),
    ("Correlation ID Propagation", test_correlation_id_propagation),
  ]

  passed = 0
  failed = 0

  for name, test_func in tests:
    try:
      test_func()
      passed += 1
      print(f"✅ {name} PASSED")
    except AssertionError as e:
      failed += 1
      print(f"❌ {name} FAILED: {e}")
    except requests.exceptions.ConnectionError:
      print(f"❌ {name} FAILED: Could not connect to server at {BASE_URL}")
      print("   Make sure the backend server is running: cd backend && uvicorn app.main:app --reload")
      break
    except Exception as e:
      failed += 1
      print(f"❌ {name} FAILED: {e}")

  print(f"\n{'=' * 80}")
  print(f"TEST SUMMARY: {passed} passed, {failed} failed")
  print(f"{'=' * 80}\n")

  if failed > 0:
    exit(1)


if __name__ == "__main__":
  main()
