"""Helper functions for data serialization and conversion."""

from types import SimpleNamespace
from typing import Any, Dict, List, Union


def namespace_to_dict(obj: Any) -> Union[Dict, List, Any]:
  """
  Recursively convert SimpleNamespace objects to dictionaries for JSON serialization.

  This is needed when passing data from frontend display objects (SimpleNamespace)
  to API endpoints that require JSON-serializable dictionaries.

  Args:
    obj: Object to convert (SimpleNamespace, list, dict, or primitive)

  Returns:
    Converted object with all SimpleNamespace instances replaced by dicts

  Example:
    >>> ns = SimpleNamespace(name="test", items=[SimpleNamespace(id=1)])
    >>> result = namespace_to_dict(ns)
    >>> result
    {'name': 'test', 'items': [{'id': 1}]}
  """
  if isinstance(obj, SimpleNamespace):
    return {key: namespace_to_dict(value) for key, value in vars(obj).items()}
  elif isinstance(obj, list):
    return [namespace_to_dict(item) for item in obj]
  elif isinstance(obj, dict):
    return {key: namespace_to_dict(value) for key, value in obj.items()}
  else:
    return obj
