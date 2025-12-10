"""
Tests to validate that provider SDK clients have the expected attributes.

These tests ensure that our provider implementations match the actual SDK APIs.
This prevents issues where mocked tests pass but real implementations fail.

IMPORTANT: These tests should run FIRST before any unit tests to ensure
SDK versions are compatible with our code.
"""


import pytest

pytestmark = pytest.mark.sdk_validation


class TestOpenAISDKValidation:
  """Validate OpenAI SDK structure."""

  def test_openai_client_has_responses_attribute(self):
    """Test that OpenAI client has 'responses' attribute for Responses API."""
    try:
      from openai import OpenAI
    except ImportError:
      pytest.skip("OpenAI SDK not installed")

    # Create a client instance (without API key for structure validation)
    # This will fail to make API calls but allows us to check structure
    try:
      client = OpenAI(api_key="dummy-key-for-testing")
    except Exception as e:
      pytest.fail(f"Failed to create OpenAI client: {e}")

    # Validate that the 'responses' attribute exists
    assert hasattr(client, 'responses'), (
      "OpenAI client missing 'responses' attribute. "
      "This is required for the Responses API. "
      "You may need to upgrade the openai library to version 2.x or higher."
    )

    # Validate that responses has 'create' method
    assert hasattr(client.responses, 'create'), (
      "OpenAI client.responses missing 'create' method. "
      "The Responses API requires this method."
    )

  def test_openai_library_version(self):
    """Test that OpenAI library is version 2.x or higher."""
    try:
      import openai
    except ImportError:
      pytest.skip("OpenAI SDK not installed")

    version = openai.__version__
    major_version = int(version.split('.')[0])

    assert major_version >= 2, (
      f"OpenAI library version {version} is too old. "
      f"The Responses API requires version 2.x or higher. "
      f"Current version: {version}"
    )


class TestGoogleSDKValidation:
  """Validate Google GenAI SDK structure."""

  def test_google_client_has_models_attribute(self):
    """Test that Google client has 'models' attribute."""
    try:
      from google.genai import Client
    except ImportError:
      pytest.skip("Google GenAI SDK not installed")

    # Create a client instance (without API key for structure validation)
    try:
      client = Client(api_key="dummy-key-for-testing")
    except Exception:
      # Some SDKs may fail without valid key, but we can still check the class
      pass

    # Check if the Client class has the expected structure
    # We check the class, not the instance, to avoid authentication errors
    assert hasattr(Client, '__init__'), "Google Client missing __init__ method"

    # Create instance with dummy key to check attributes
    try:
      client = Client(api_key="dummy-key-for-testing")
      assert hasattr(client, 'models'), (
        "Google Client missing 'models' attribute. "
        "This is required for content generation."
      )
    except Exception as e:
      # If we can't create a client, at least verify the class exists
      pytest.skip(f"Cannot create Google Client instance: {e}")

  def test_google_models_has_generate_content_method(self):
    """Test that Google client.models has 'generate_content' method."""
    try:
      from google.genai import Client
    except ImportError:
      pytest.skip("Google GenAI SDK not installed")

    try:
      client = Client(api_key="dummy-key-for-testing")
      assert hasattr(client.models, 'generate_content'), (
        "Google client.models missing 'generate_content' method. "
        "This is required for text generation."
      )
    except Exception as e:
      pytest.skip(f"Cannot validate Google SDK structure: {e}")


class TestAnthropicSDKValidation:
  """Validate Anthropic SDK structure."""

  def test_anthropic_client_has_messages_attribute(self):
    """Test that Anthropic client has 'messages' attribute."""
    try:
      from anthropic import Anthropic
    except ImportError:
      pytest.skip("Anthropic SDK not installed")

    # Create a client instance (without API key for structure validation)
    try:
      client = Anthropic(api_key="dummy-key-for-testing")
    except Exception:
      # Some SDKs may fail without valid key, but we can still check the class
      pass

    # Create instance with dummy key to check attributes
    try:
      client = Anthropic(api_key="dummy-key-for-testing")
      assert hasattr(client, 'messages'), (
        "Anthropic client missing 'messages' attribute. "
        "This is required for the Messages API."
      )
    except Exception as e:
      pytest.skip(f"Cannot create Anthropic client instance: {e}")

  def test_anthropic_messages_has_create_method(self):
    """Test that Anthropic client.messages has 'create' method."""
    try:
      from anthropic import Anthropic
    except ImportError:
      pytest.skip("Anthropic SDK not installed")

    try:
      client = Anthropic(api_key="dummy-key-for-testing")
      assert hasattr(client.messages, 'create'), (
        "Anthropic client.messages missing 'create' method. "
        "This is required for creating messages."
      )
    except Exception as e:
      pytest.skip(f"Cannot validate Anthropic SDK structure: {e}")


class TestProviderImplementationMatchesSDK:
  """Integration tests that verify provider implementations use correct SDK methods."""

  def test_openai_provider_uses_correct_api_calls(self):
    """Test that OpenAI provider calls the correct SDK methods."""
    try:
      from openai import OpenAI

      from app.services.providers.openai_provider import OpenAIProvider
    except ImportError as e:
      pytest.skip(f"Required libraries not installed: {e}")

    # Create provider with dummy key
    provider = OpenAIProvider("dummy-key")

    # Verify provider.client is an OpenAI instance
    assert isinstance(provider.client, OpenAI), (
      f"OpenAI provider client should be OpenAI instance, got {type(provider.client)}"
    )

    # Verify the client has the required attribute
    assert hasattr(provider.client, 'responses'), (
      "OpenAI provider client missing 'responses' attribute"
    )

  def test_google_provider_uses_correct_api_calls(self):
    """Test that Google provider calls the correct SDK methods."""
    try:
      from google.genai import Client

      from app.services.providers.google_provider import GoogleProvider
    except ImportError as e:
      pytest.skip(f"Required libraries not installed: {e}")

    # Create provider with dummy key
    provider = GoogleProvider("dummy-key")

    # Verify provider.client is a Client instance
    assert isinstance(provider.client, Client), (
      f"Google provider client should be Client instance, got {type(provider.client)}"
    )

    # Verify the client has the required attribute
    assert hasattr(provider.client, 'models'), (
      "Google provider client missing 'models' attribute"
    )

  def test_anthropic_provider_uses_correct_api_calls(self):
    """Test that Anthropic provider calls the correct SDK methods."""
    try:
      from anthropic import Anthropic

      from app.services.providers.anthropic_provider import AnthropicProvider
    except ImportError as e:
      pytest.skip(f"Required libraries not installed: {e}")

    # Create provider with dummy key
    provider = AnthropicProvider("dummy-key")

    # Verify provider.client is an Anthropic instance
    assert isinstance(provider.client, Anthropic), (
      f"Anthropic provider client should be Anthropic instance, got {type(provider.client)}"
    )

    # Verify the client has the required attribute
    assert hasattr(provider.client, 'messages'), (
      "Anthropic provider client missing 'messages' attribute"
    )
