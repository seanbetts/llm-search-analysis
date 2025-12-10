"""Network capture module for intercepting LLM provider network traffic.

This module provides browser automation and network traffic interception
capabilities to capture detailed search data that is not available through
official APIs.
"""

from .base_capturer import BaseCapturer

__all__ = ['BaseCapturer']
