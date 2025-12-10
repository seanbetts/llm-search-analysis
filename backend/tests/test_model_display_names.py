"""Tests for model display name formatting.

Following TDD, these tests define expected behavior BEFORE implementation.
"""

from app.core.utils import get_model_display_name


class TestModelDisplayNames:
  """Tests for get_model_display_name function."""

  def test_anthropic_claude_sonnet_4_5(self):
    """Test Claude Sonnet 4.5 variants."""
    assert get_model_display_name('claude-sonnet-4-5-20250929') == 'Claude Sonnet 4.5'
    assert get_model_display_name('claude-sonnet-4-5.2-0250929') == 'Claude Sonnet 4.5'
    assert get_model_display_name('claude-sonnet-4.5-20250929') == 'Claude Sonnet 4.5'

  def test_anthropic_claude_haiku_4_5(self):
    """Test Claude Haiku 4.5 variants."""
    assert get_model_display_name('claude-haiku-4-5-20251001') == 'Claude Haiku 4.5'
    assert get_model_display_name('claude-haiku-4.5-20251001') == 'Claude Haiku 4.5'

  def test_anthropic_claude_opus_4_1(self):
    """Test Claude Opus 4.1 variants."""
    assert get_model_display_name('claude-opus-4-1-20250805') == 'Claude Opus 4.1'
    assert get_model_display_name('claude-opus-4.1-20250805') == 'Claude Opus 4.1'

  def test_openai_gpt_5_1(self):
    """Test GPT-5.1 variants."""
    assert get_model_display_name('gpt-5.1') == 'GPT-5.1'
    assert get_model_display_name('gpt-5-1') == 'GPT-5.1'

  def test_openai_gpt_5_variants(self):
    """Test GPT-5 model variants."""
    assert get_model_display_name('gpt-5-mini') == 'GPT-5 Mini'
    assert get_model_display_name('gpt-5-nano') == 'GPT-5 Nano'

  def test_google_gemini_3_pro(self):
    """Test Gemini 3 Pro."""
    assert get_model_display_name('gemini-3-pro-preview') == 'Gemini 3 Pro (Preview)'

  def test_google_gemini_2_5_flash(self):
    """Test Gemini 2.5 Flash variants."""
    assert get_model_display_name('gemini-2.5-flash') == 'Gemini 2.5 Flash'
    assert get_model_display_name('gemini-2.5-flash-lite') == 'Gemini 2.5 Flash Lite'

  def test_chatgpt_free_variants(self):
    """Test ChatGPT Free variants from network capture."""
    assert get_model_display_name('ChatGPT (Free)') == 'ChatGPT (Free)'
    assert get_model_display_name('chatgpt-free') == 'ChatGPT (Free)'
    assert get_model_display_name('ChatGPT') == 'ChatGPT (Free)'

  def test_unknown_model_with_date_suffix(self):
    """Test unknown model with date suffix gets formatted nicely."""
    # Should remove date suffix and format nicely
    result = get_model_display_name('some-new-model-20250101')
    assert result == 'Some New Model'

  def test_unknown_model_with_version(self):
    """Test unknown model with version number."""
    # Should remove trailing version like .2
    result = get_model_display_name('some-model-v2.5')
    assert result == 'Some Model V2'

  def test_unknown_model_simple(self):
    """Test simple unknown model gets formatted nicely."""
    result = get_model_display_name('my-cool-model')
    assert result == 'My Cool Model'

  def test_already_formatted_model(self):
    """Test model that's already in display format."""
    # Should handle models without hyphens - capitalizes first letter
    result = get_model_display_name('GPT4')
    assert result == 'Gpt4'

  def test_empty_string(self):
    """Test empty string returns empty string."""
    assert get_model_display_name('') == ''

  def test_single_word(self):
    """Test single word model name."""
    assert get_model_display_name('claude') == 'Claude'
