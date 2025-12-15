"""Helpers for exporting interaction results as Markdown in the Streamlit UI."""

from __future__ import annotations

from typing import Optional

import streamlit as st

from frontend.helpers.error_handling import safe_api_call


@st.cache_data(ttl=300, show_spinner=False)
def fetch_interaction_markdown_cached(base_url: str, interaction_id: int) -> str:
  """Fetch the backend's Markdown export for an interaction (cached).

  Cache TTL: 300 seconds (5 minutes) since exports are static per interaction.
  Cache is keyed on base_url and interaction_id.
  """
  from frontend.api_client import APIClient

  client = APIClient(base_url=base_url)
  return client.export_interaction_markdown(interaction_id)


def get_interaction_markdown(base_url: str, interaction_id: int) -> str:
  """Return a Markdown export for an interaction, with user-facing fallback on failure."""
  md_export, export_error = safe_api_call(
    fetch_interaction_markdown_cached,
    base_url,
    interaction_id,
    show_spinner=False,
  )
  if export_error:
    st.warning(f"Could not generate markdown export: {export_error}")
    return "# Export failed\n\nCould not generate markdown export."
  return md_export or "# Export\n\n_No content available._"


def render_markdown_download_button(
  *,
  base_url: str,
  interaction_id: Optional[int],
  key: str,
  label: str = "📥 Download as Markdown",
  file_name: Optional[str] = None,
  use_container_width: bool = True,
) -> None:
  """Render a consistent Markdown download button for an interaction."""
  if not interaction_id:
    return

  export_text = get_interaction_markdown(base_url, interaction_id)
  st.download_button(
    label=label,
    data=export_text,
    file_name=file_name or f"interaction_{interaction_id}.md",
    mime="text/markdown",
    use_container_width=use_container_width,
    key=key,
  )

