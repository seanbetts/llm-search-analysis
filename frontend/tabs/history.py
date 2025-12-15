"""History tab for viewing past interactions."""

import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from frontend.components.response import display_response
from frontend.helpers.error_handling import safe_api_call
from frontend.helpers.export_utils import dataframe_to_csv_bytes
from frontend.helpers.interactive import build_api_response
from frontend.helpers.markdown_export import render_markdown_download_button


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_interaction_details_cached(base_url: str, interaction_id: int):
  """Cached wrapper for fetching interaction details.

  Cache TTL: 300 seconds (5 minutes) since interaction details rarely change.
  Cache is keyed on base_url and interaction_id.
  """
  from frontend.api_client import APIClient
  client = APIClient(base_url=base_url)
  return client.get_interaction(interaction_id)


def _prepare_history_dataframe(interactions: List[Dict[str, Any]]) -> pd.DataFrame:
  """Normalize interaction list into a DataFrame with derived fields for display/export."""
  if not interactions:
    return pd.DataFrame(columns=[
      'id', 'timestamp', 'analysis_type', 'prompt', 'prompt_preview', 'provider',
      'model', 'model_display', 'searches', 'sources', 'citations', 'avg_rank',
      'avg_rank_display', 'response_time_ms', 'response_time_display',
      'extra_links', 'data_source'
    ])

  df = pd.DataFrame(interactions)
  rename_map = {
    'interaction_id': 'id',
    'created_at': 'timestamp',
    'search_query_count': 'searches',
    'source_count': 'sources',
    'citation_count': 'citations',
    'average_rank': 'avg_rank',
    'extra_links_count': 'extra_links'
  }
  df = df.rename(columns=rename_map)

  if 'timestamp' in df.columns:
    df['_ts_dt'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values(by='_ts_dt', ascending=False)
    df['timestamp'] = df['_ts_dt'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df = df.drop(columns=['_ts_dt'])

  if 'prompt' in df.columns:
    df['prompt_preview'] = df['prompt'].apply(
      lambda text: (text[:80] + ('...' if len(text) > 80 else '')) if isinstance(text, str) else ''
    )
  else:
    df['prompt_preview'] = ''

  if 'extra_links' not in df.columns:
    df['extra_links'] = 0
  if 'response_time_ms' not in df.columns:
    df['response_time_ms'] = None

  df['analysis_type'] = df['data_source'].apply(
    lambda x: 'Web' if x in ('web', 'network_log') else 'API'
  )

  df['avg_rank_display'] = df['avg_rank'].apply(
    lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
  )
  df['response_time_display'] = df['response_time_ms'].apply(
    lambda x: f"{x / 1000:.1f}s" if pd.notna(x) else "N/A"
  )

  def _safe(value):
    return value if pd.notna(value) else None

  df['model_display'] = df.apply(
    lambda row: _safe(row.get('model_display_name')) or _safe(row.get('model')),
    axis=1
  )
  return df


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_all_interactions(
  base_url: str,
  page_size: int = 100,
  data_source: Optional[str] = None,
) -> Dict[str, Any]:
  """Fetch all interaction pages for full-history filtering."""
  from frontend.api_client import APIClient

  client = APIClient(base_url=base_url)
  page = 1
  items: List[Dict[str, Any]] = []
  stats: Dict[str, Any] = {}

  while True:
    result = client.get_recent_interactions(
      page=page,
      page_size=page_size,
      data_source=data_source
    )
    items.extend(result.get('items', []))
    if not stats:
      stats = result.get('stats') or {}
    pagination = result.get('pagination') or {}
    if not pagination.get('has_next'):
      break
    page += 1

  return {'items': items, 'stats': stats}


def _build_model_display_mapping(model_display_options_df):
  """Build mapping of display_name -> set(raw model ids) for filtering.

  Multiple model ids can share the same human-readable label (e.g.,
  old vs normalized Anthropic IDs). This helper ensures the filter keeps
  all ids selected whenever a label is chosen.
  """
  model_display_options = {}
  for _, row in model_display_options_df.iterrows():
    model = row.get('model')
    display = row.get('model_display')
    if pd.isna(model) or pd.isna(display):
      continue
    model_display_options.setdefault(display, set()).add(model)
  return dict(sorted(model_display_options.items()))


def tab_history():
  """Tab 3: Query History."""
  st.markdown("### 📜 Query History")

  # Initialize pagination state
  if 'history_page' not in st.session_state:
    st.session_state.history_page = 1
  if 'history_page_size' not in st.session_state:
    st.session_state.history_page_size = 10
  st.session_state.setdefault('history_full_export', None)
  st.session_state.setdefault('history_search_query', "")
  st.session_state.setdefault('history_provider_filter', None)
  st.session_state.setdefault('history_model_filter', None)
  st.session_state.setdefault('history_filter_signature', None)
  analysis_filter_options = ["API", "Web"]
  st.session_state.setdefault('history_analysis_filter', analysis_filter_options.copy())
  st.session_state.setdefault('history_last_filter', tuple(sorted(analysis_filter_options)))

  selected_analysis_filter = st.session_state.history_analysis_filter or analysis_filter_options.copy()
  if not st.session_state.history_analysis_filter:
    st.session_state.history_analysis_filter = analysis_filter_options.copy()
    selected_analysis_filter = analysis_filter_options.copy()

  normalized_filter = tuple(sorted(selected_analysis_filter))
  if normalized_filter != st.session_state.history_last_filter:
    st.session_state.history_page = 1
    st.session_state.history_last_filter = normalized_filter

  data_source_filter = None
  if len(selected_analysis_filter) == 1:
    data_source_filter = 'api' if selected_analysis_filter[0] == 'API' else 'web'

  # Get all interactions for current analysis (cached)
  try:
    base_url = st.session_state.api_client.base_url
    result, error = safe_api_call(
      _fetch_all_interactions,
      base_url,
      100,
      data_source_filter,
      spinner_text="Loading interaction history..."
    )
    if error:
      st.error(f"Error loading history: {error}")
      return

    interactions = result.get('items', [])

    if not interactions:
      st.info("No interactions recorded yet. Start by submitting prompts in the Web or API tabs!")
      return

    df = _prepare_history_dataframe(interactions)
    stats_data = result.get('stats') or {}
    stats_cols = st.columns(6)
    stats_cols[0].metric("Analyses", stats_data.get('analyses', 0))
    avg_resp = stats_data.get('avg_response_time_ms')
    stats_cols[1].metric(
      "Avg. Response Time",
      f"{avg_resp / 1000:.1f}s" if avg_resp is not None else "N/A"
    )
    stats_cols[2].metric(
      "Avg. Searches",
      f"{stats_data.get('avg_searches', 0):.1f}" if stats_data.get('avg_searches') is not None else "N/A"
    )
    stats_cols[3].metric(
      "Avg. Sources Found",
      f"{stats_data.get('avg_sources_found', 0):.1f}" if stats_data.get('avg_sources_found') is not None else "N/A"
    )
    stats_cols[4].metric(
      "Avg. Sources Used",
      f"{stats_data.get('avg_sources_used', 0):.1f}" if stats_data.get('avg_sources_used') is not None else "N/A"
    )
    stats_cols[5].metric(
      "Avg. Rank",
      f"{stats_data.get('avg_rank', 0):.1f}" if stats_data.get('avg_rank') is not None else "N/A"
    )

    # Use backend-provided model_display_name (Phase 1.2)
    # Fallback to raw model name if display name not available
    df['model_display'] = df.apply(
      lambda row: row.get('model_display_name') or row['model'] if pd.notna(row.get('model')) else row.get('model'),
      axis=1
    )

    # Build filter options prior to rendering
    provider_options = sorted(df['provider'].dropna().unique().tolist())
    if st.session_state.history_provider_filter is None:
      st.session_state.history_provider_filter = provider_options.copy()
    else:
      st.session_state.history_provider_filter = [
        p for p in st.session_state.history_provider_filter if p in provider_options
      ] or provider_options.copy()

    model_display_options_df = df[['model', 'model_display']].drop_duplicates()
    model_display_mapping = _build_model_display_mapping(model_display_options_df)
    model_display_labels = list(model_display_mapping.keys())
    if st.session_state.history_model_filter is None:
      st.session_state.history_model_filter = model_display_labels.copy()
    else:
      st.session_state.history_model_filter = [
        m for m in st.session_state.history_model_filter if m in model_display_labels
      ] or model_display_labels.copy()

    # Filters layout
    col_search, col_analysis, col_provider, col_model = st.columns([1.2, 1, 1, 1])

    with col_search:
      st.text_input(
        "🔍 Search prompts",
        placeholder="Enter keywords to filter...",
        key="history_search_query"
      )

    with col_analysis:
      st.multiselect(
        "Analysis type",
        options=analysis_filter_options,
        key="history_analysis_filter"
      )
      analysis_selection = st.session_state.history_analysis_filter or analysis_filter_options

    with col_provider:
      selected_providers = st.multiselect(
        "Provider",
        options=provider_options,
        key="history_provider_filter"
      )
      selected_providers = selected_providers or provider_options

    with col_model:
      selected_model_displays = st.multiselect(
        "Model",
        options=model_display_labels,
        key="history_model_filter"
      )
      selected_model_displays = selected_model_displays or model_display_labels
      selected_models = set()
      for display in selected_model_displays:
        selected_models.update(model_display_mapping.get(display, set()))

    current_signature = (
      tuple(sorted(analysis_selection or analysis_filter_options)),
      st.session_state.history_search_query.strip().lower(),
      tuple(sorted(selected_providers)),
      tuple(sorted(selected_models)),
    )
    if current_signature != st.session_state.history_filter_signature:
      st.session_state.history_page = 1
      st.session_state.history_filter_signature = current_signature

    # Apply filters
    search_query = st.session_state.history_search_query.strip()
    if search_query:
      df = df[df['prompt'].str.contains(search_query, case=False, na=False)]
    if analysis_selection:
      df = df[df['analysis_type'].isin(analysis_selection)]
    if selected_providers:
      df = df[df['provider'].isin(selected_providers)]
    if selected_models:
      df = df[df['model'].isin(selected_models)]

    # Default sort (newest first); users can re-sort via table headers
    df = df.sort_values(by="timestamp", ascending=False, na_position="last")

    total_filtered = len(df)
    page_size = st.session_state.history_page_size
    total_pages = max(1, (total_filtered + page_size - 1) // page_size)
    if st.session_state.history_page > total_pages:
      st.session_state.history_page = total_pages
      st.rerun()
    start_idx = (st.session_state.history_page - 1) * page_size
    end_idx = start_idx + page_size
    page_df = df.iloc[start_idx:end_idx]
    pagination = {
      'page': st.session_state.history_page,
      'page_size': page_size,
      'total_items': total_filtered,
      'total_pages': total_pages,
      'has_next': st.session_state.history_page < total_pages,
      'has_prev': st.session_state.history_page > 1,
    }

    if total_filtered == 0:
      st.warning("No interactions match your filters.")

    display_df = page_df[
      [
        'id', 'timestamp', 'analysis_type', 'prompt_preview', 'provider',
        'model_display', 'response_time_display', 'searches', 'sources',
        'citations', 'avg_rank_display', 'extra_links'
      ]
    ]
    display_df.columns = [
      'ID', 'Timestamp', 'Analysis Type', 'Prompt', 'Provider', 'Model',
      'Response Time', 'Searches', 'Sources Found', 'Sources Used', 'Avg. Rank',
      'Extra Links'
    ]

    # Configure column widths and alignment
    # Let Streamlit autosize columns; avoid fixed widths
    column_config = {
      "ID": st.column_config.NumberColumn("ID"),
      "Timestamp": st.column_config.TextColumn("Timestamp"),
      "Analysis Type": st.column_config.TextColumn("Analysis Type"),
      "Prompt": st.column_config.TextColumn("Prompt"),
      "Provider": st.column_config.TextColumn("Provider"),
      "Model": st.column_config.TextColumn("Model"),
      "Response Time": st.column_config.TextColumn("Response Time"),
      "Searches": st.column_config.NumberColumn("Searches"),
      "Sources Found": st.column_config.NumberColumn("Sources Found"),
      "Sources Used": st.column_config.NumberColumn("Sources Used"),
      "Avg. Rank": st.column_config.TextColumn("Avg. Rank"),
      "Extra Links": st.column_config.NumberColumn("Extra Links"),
    }

    st.dataframe(
      display_df,
      use_container_width=True,
      height=400,
      hide_index=True,
      column_config=column_config,
    )

    # Pagination controls
    col_prev, col_info, col_next = st.columns([1, 2, 1])

    with col_prev:
      if st.button("← Previous", disabled=not pagination['has_prev'], use_container_width=True):
        st.session_state.history_page -= 1
        st.rerun()

    with col_info:
      st.markdown(
        f"<div style='text-align: center; padding-top: 8px;'>"
        f"Page {pagination['page']} of {pagination['total_pages']} "
        f"({pagination['total_items']} total items)"
        f"</div>",
        unsafe_allow_html=True
      )

    with col_next:
      if st.button("Next →", disabled=not pagination['has_next'], use_container_width=True):
        st.session_state.history_page += 1
        st.rerun()

    export_df = df[['id', 'timestamp', 'analysis_type', 'prompt', 'provider', 'model_display',
                    'response_time_display', 'searches', 'sources', 'citations',
                    'avg_rank_display', 'extra_links']].copy()
    export_df.columns = ['ID', 'Timestamp', 'Analysis Type', 'Prompt', 'Provider', 'Model',
                         'Response Time', 'Searches', 'Sources Found', 'Sources Used',
                         'Avg. Rank', 'Extra Links']

    csv_bytes = dataframe_to_csv_bytes(export_df, text_columns=['Prompt'])
    export_wrap, _ = st.columns([1, 4])
    with export_wrap:
      exp_row_left, exp_row_right = st.columns(2, gap="small")
      with exp_row_left:
        st.download_button(
          label="📥 Export Page as CSV",
          data=csv_bytes,
          file_name=f"query_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
          mime="text/csv",
          use_container_width=True,
          key="history-export-csv",
        )
      with exp_row_right:
        if st.button("📦 Export Full History", use_container_width=True):
          with st.spinner("Preparing full history export..."):
            full_result, full_error = safe_api_call(
              _fetch_all_interactions,
              base_url,
              show_spinner=False
            )

          if full_error:
            st.error(full_error)
          else:
            full_items = (full_result or {}).get('items', [])
            full_df = _prepare_history_dataframe(full_items)
            if full_df.empty:
              st.warning("No history available to export.")
            else:
              full_export_df = full_df[['id', 'timestamp', 'analysis_type', 'prompt', 'provider', 'model_display',
                                        'response_time_display', 'searches', 'sources', 'citations',
                                        'avg_rank_display', 'extra_links']].copy()
              full_export_df.columns = export_df.columns
              csv_full_bytes = dataframe_to_csv_bytes(full_export_df, text_columns=['Prompt'])
              st.download_button(
                label=f"📥 Download Full History ({len(full_export_df)} rows)",
                data=csv_full_bytes,
                file_name=f"query_history_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
                key=f"history-export-csv-full-{datetime.now().timestamp()}",
              )
    st.divider()

    # View details
    st.markdown("### 🧾 View Interaction Details")
    selected_id = st.selectbox(
      "Select an interaction to view details",
      options=df['id'].tolist(),
      format_func=lambda x: f"ID {x}: {df[df['id'] == x]['prompt_preview'].values[0]}"
    )

    if selected_id:
      base_url = st.session_state.api_client.base_url
      # Fetch interaction details (cached)
      details, details_error = safe_api_call(
        _fetch_interaction_details_cached,
        base_url,
        selected_id,
        show_spinner=False
      )
      if details_error:
        st.error(f"Error loading interaction: {details_error}")
      elif details:
        btn_wrap, _ = st.columns([1, 4])
        with btn_wrap:
          btn_col1, btn_col2 = st.columns(2, gap="small")
          with btn_col1:
            render_markdown_download_button(
              base_url=base_url,
              interaction_id=selected_id,
              key=f"history-detail-md-{selected_id}",
              file_name=f"interaction_{selected_id}.md",
            )
          with btn_col2:
            if st.button("🗑️ Delete Interaction", type="secondary", use_container_width=True):
              deleted, delete_error = safe_api_call(
                st.session_state.api_client.delete_interaction,
                selected_id,
                show_spinner=False
              )
              if delete_error:
                st.error(f"Failed to delete interaction: {delete_error}")
              elif deleted:
                st.success(f"Interaction ID {selected_id} deleted.")
                try:
                  # Streamlit >=1.22 uses st.rerun
                  rerun = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
                  if rerun:
                    rerun()
                except Exception:
                  pass
              else:
                st.warning("Interaction not found.")

        st.divider()
        response_ns = build_api_response(details)
        response_ns.data_source = details.get("data_source", response_ns.data_source)
        display_response(response_ns, details.get("prompt"))

  except Exception as e:
    st.error(f"Error loading history: {str(e)}")
    st.error(f"Traceback: {traceback.format_exc()}")
