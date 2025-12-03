# Testing Guide

## Overview

This project uses pytest for testing. The test suite is organized into several categories:

1. **SDK Validation Tests** - Verify that installed SDK versions match our code
2. **Unit Tests** - Test individual components in isolation
3. **Integration Tests** - Test components working together

## Why SDK Validation Tests?

**Problem**: During development, we discovered that over-mocked unit tests were passing even though the real OpenAI SDK didn't have the `responses` attribute our code was using. This caused a 502 error in production that tests didn't catch.

**Solution**: SDK validation tests run FIRST to verify that:
- OpenAI SDK version 2.x+ is installed (has `client.responses` attribute)
- Google GenAI SDK has correct structure (`client.models.generate_content`)
- Anthropic SDK has correct structure (`client.messages.create`)

If these tests fail, your SDK versions are incompatible and unit tests will give false positives.

## Running Tests

### Quick Start (Recommended)

Use the test runner script which ensures SDK validation tests run first:

```bash
cd backend
./scripts/run_tests.sh
```

### Manual Test Execution

If you prefer to run tests manually:

```bash
cd backend

# Step 1: SDK Validation (MUST run first)
pytest tests/test_provider_sdk_validation.py -v -m sdk_validation

# Step 2: Unit Tests (only if SDK validation passes)
pytest tests/ -v -m "not sdk_validation"

# Step 3: Coverage Report (optional)
pytest tests/ --cov=app --cov-report=term-missing --cov-report=html
```

### Running Specific Tests

```bash
# Run only OpenAI provider tests
pytest tests/test_openai_provider.py -v

# Run only SDK validation tests
pytest -m sdk_validation

# Run tests with coverage
pytest --cov=app --cov-report=html
```

## Test Organization

```
backend/tests/
├── test_provider_sdk_validation.py  # SDK structure validation (run first!)
├── test_openai_provider.py          # OpenAI provider unit tests
├── test_google_provider.py          # Google provider unit tests
├── test_anthropic_provider.py       # Anthropic provider unit tests
├── test_provider_factory.py         # Provider factory tests
├── test_api.py                       # API endpoint tests
└── ...
```

## Understanding Test Markers

Tests are marked with pytest markers for categorization:

- `@pytest.mark.sdk_validation` - SDK validation tests (run first)
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow-running tests

## Common Issues

### Issue: SDK Validation Tests Fail

**Symptom**:
```
AttributeError: 'OpenAI' object has no attribute 'responses'
```

**Solution**:
Check your OpenAI library version:
```bash
pip show openai
```

Ensure version is 2.x or higher. If not:
```bash
pip install openai==2.8.1  # or latest
```

### Issue: Unit Tests Pass but Production Fails

**Cause**: Over-mocked tests that create attributes not present in real SDKs.

**Solution**:
1. Run SDK validation tests first
2. Update tests to use real SDK client classes (without making API calls)
3. Avoid creating mock attributes like `mock.client.responses.create = Mock(...)`

## Best Practices

1. **Always run SDK validation tests first** - Use `./scripts/run_tests.sh`
2. **Don't over-mock** - Use real SDK classes and only mock network calls
3. **Validate SDK structure** - Check that attributes exist before mocking methods
4. **Update SDK versions carefully** - Run full test suite after updates
5. **Run tests before commits** - Use pre-commit hooks if possible

## Continuous Integration

Our CI pipeline runs tests in this order:
1. SDK validation tests (fail fast if SDKs incompatible)
2. Unit tests
3. Integration tests
4. Coverage report

If SDK validation fails, the pipeline stops immediately to prevent wasting CI time on unit tests that would give false positives.

## Adding New Tests

When adding tests for new providers:

1. Add SDK validation tests to `test_provider_sdk_validation.py`
2. Create unit tests in `test_<provider>_provider.py`
3. Use real SDK client classes, only mock network calls
4. Mark tests appropriately (`@pytest.mark.unit`, etc.)

Example:

```python
# Good: Uses real SDK client, only mocks the API call
def test_new_provider(self):
    from new_sdk import Client
    from app.services.providers.new_provider import NewProvider

    provider = NewProvider("test-key")
    assert isinstance(provider.client, Client)  # Validates real SDK structure
    assert hasattr(provider.client, 'generate')  # Validates method exists

    # Now mock only the network call
    with patch.object(provider.client, 'generate') as mock_generate:
        mock_generate.return_value = {...}
        result = provider.send_prompt("test")
        assert result.response_text == "..."

# Bad: Over-mocked, creates attributes that may not exist
def test_new_provider_bad(self):
    with patch('new_sdk.Client') as MockClient:
        provider = NewProvider("test-key")
        provider.client.generate = Mock(...)  # Creates attribute that may not exist!
```

## Troubleshooting

### Tests pass locally but fail in CI

- Check SDK versions in requirements.txt match your local environment
- Run `pip freeze > requirements-local.txt` and compare with requirements.txt
- Ensure `.dockerignore` doesn't exclude test files if running in Docker

### Mocked tests passing but real API calls failing

- Run SDK validation tests first
- Check that mocked attributes actually exist in the real SDK
- Use `hasattr()` checks before mocking
- Consider adding integration tests with real API calls (mark as `@pytest.mark.integration`)

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [Google GenAI Python SDK](https://github.com/google/generative-ai-python)
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)
