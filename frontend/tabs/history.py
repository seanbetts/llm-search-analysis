"""History tab for viewing past interactions."""

import traceback
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from frontend.components.response import extract_images_from_response, format_response_text
from frontend.helpers.error_handling import safe_api_call
from frontend.helpers.export_utils import dataframe_to_csv_bytes
from frontend.utils import format_pub_date


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_recent_interactions_cached(base_url: str, page: int, page_size: int):
  """Cached wrapper for fetching recent interactions.

  Cache TTL: 60 seconds to balance freshness with performance.
  Cache is keyed on base_url, page, and page_size.
  """
  from frontend.api_client import APIClient
  client = APIClient(base_url=base_url)
  return client.get_recent_interactions(page=page, page_size=page_size)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_interaction_details_cached(base_url: str, interaction_id: int):
  """Cached wrapper for fetching interaction details.

  Cache TTL: 300 seconds (5 minutes) since interaction details rarely change.
  Cache is keyed on base_url and interaction_id.
  """
  from frontend.api_client import APIClient
  client = APIClient(base_url=base_url)
  return client.get_interaction(interaction_id)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_interaction_markdown_cached(base_url: str, interaction_id: int):
  """Cached wrapper for fetching interaction markdown export.

  Cache TTL: 300 seconds (5 minutes) since exports are static.
  Cache is keyed on base_url and interaction_id.
  """
  from frontend.api_client import APIClient
  client = APIClient(base_url=base_url)
  return client.export_interaction_markdown(interaction_id)


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
    lambda x: 'Network Logs' if x == 'network_log' else 'API'
  )

  df['avg_rank_display'] = df['avg_rank'].apply(
    lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
  )
  df['response_time_display'] = df['response_time_ms'].apply(
    lambda x: f"{x / 1000:.1f}s" if pd.notna(x) else "N/A"
  )

  df['model_display'] = df.apply(
    lambda row: row.get('model_display_name') or row.get('model') if pd.notna(row.get('model')) else row.get('model'),
    axis=1
  )
  return df


def _fetch_all_interactions(base_url: str, page_size: int = 100) -> Dict[str, Any]:
  """Fetch all interaction pages for full-history export."""
  from frontend.api_client import APIClient

  client = APIClient(base_url=base_url)
  page = 1
  items: List[Dict[str, Any]] = []
  stats: Dict[str, Any] = {}

  while True:
    result = client.get_recent_interactions(page=page, page_size=page_size)
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

  # Get recent interactions with pagination (cached)
  try:
    base_url = st.session_state.api_client.base_url
    result, error = safe_api_call(
      _fetch_recent_interactions_cached,
      base_url,
      st.session_state.history_page,
      st.session_state.history_page_size,
      spinner_text="Loading interaction history..."
    )
    if error:
      st.error(f"Error loading history: {error}")
      return

    if not result or not result.get('items'):
      st.info("No interactions recorded yet. Start by submitting prompts in the Interactive tab!")
      return

    # Extract items and pagination metadata
    interactions = result['items']
    pagination = result['pagination']

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

    # Filters and sorting layout
    col_search, col_analysis, col_provider, col_model = st.columns([1.2, 1, 1, 1])

    with col_search:
      search_query = st.text_input("🔍 Search prompts", placeholder="Enter keywords to filter...")

    with col_analysis:
      analysis_options = sorted(df['analysis_type'].dropna().unique().tolist())
      selected_analysis = st.multiselect(
        "Analysis type",
        options=analysis_options,
        default=analysis_options,
      ) if analysis_options else []

    with col_provider:
      provider_options = sorted(df['provider'].dropna().unique().tolist())
      selected_providers = st.multiselect(
        "Provider",
        options=provider_options,
        default=provider_options,
      ) if provider_options else []

    with col_model:
      # Get unique display names (Phase 1.2: now from backend)
      model_display_options_df = df[['model', 'model_display']].drop_duplicates()
      model_display_options = _build_model_display_mapping(model_display_options_df)
      model_display_labels = list(model_display_options.keys())
      selected_model_displays = st.multiselect(
        "Model",
        options=model_display_labels,
        default=model_display_labels,
      ) if model_display_labels else []
      # Convert selected display names back to raw model IDs for filtering
      selected_models = set()
      for display in selected_model_displays:
        selected_models.update(model_display_options.get(display, set()))

    # Apply filters
    if search_query:
      df = df[df['prompt'].str.contains(search_query, case=False, na=False)]
    if selected_analysis:
      df = df[df['analysis_type'].isin(selected_analysis)]
    if selected_providers:
      df = df[df['provider'].isin(selected_providers)]
    if selected_models:
      df = df[df['model'].isin(selected_models)]

    # Default sort (newest first); users can re-sort via table headers
    df = df.sort_values(by="timestamp", ascending=False, na_position="last")

    display_df = df[
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
        # Download interaction as markdown (cached)
        md_export, export_error = safe_api_call(
          _fetch_interaction_markdown_cached,
          base_url,
          selected_id,
          show_spinner=False
        )
        if export_error:
          st.warning(f"Could not generate markdown export: {export_error}")
          md_export = "# Export failed\n\nCould not generate markdown export."
        btn_wrap, _ = st.columns([1, 4])
        with btn_wrap:
          btn_col1, btn_col2 = st.columns(2, gap="small")
          with btn_col1:
            st.download_button(
              label="📥 Download as Markdown",
              data=md_export,
              file_name=f"interaction_{selected_id}.md",
              mime="text/markdown",
              use_container_width=True,
              key=f"history-detail-md-{selected_id}",
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
        # Prompt header
        st.markdown(f"### 🗣️ *\"{details['prompt']}\"*")

        # Calculate metrics
        num_searches = len(details.get('search_queries', []))
        # For network logs, sources are in all_sources; for API, they're in query.sources
        if details.get('data_source') == 'network_log':
          num_sources = len(details.get('all_sources') or [])
        else:
          num_sources = sum(len(query.get('sources', [])) for query in details.get('search_queries', []))
        # Count only citations with ranks (from search results)
        citations_with_rank = [c for c in details.get('citations', []) if c.get('rank') is not None]
        num_sources_used = len(citations_with_rank)
        avg_rank_display = f"{sum(c['rank'] for c in citations_with_rank) / len(citations_with_rank):.1f}" if citations_with_rank else "N/A"  # noqa: E501
        response_time_s = f"{details['response_time_ms'] / 1000:.1f}s"
        # Extra links from stored value; fallback to citations without rank
        extra_links_count = details.get('extra_links', len([c for c in details.get('citations', []) if not c.get('rank')]))  # noqa: E501
        # Response metadata
        col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([1.5, 2, 1, 1, 1, 1, 1, 1])

        # Provider display names
        provider_names = {
          'openai': 'OpenAI',
          'google': 'Google',
          'anthropic': 'Anthropic'
        }

        with col1:
          st.metric("Provider", provider_names.get(details['provider'].lower(), details['provider']))
        with col2:
          # Use backend-provided model_display_name (Phase 1.2)
          model_display = details.get('model_display_name') or details['model']
          st.metric("Model", model_display)
        with col3:
          st.metric("Response Time", response_time_s)
        with col4:
          st.metric("Search Queries", num_searches)
        with col5:
          st.metric("Sources Found", num_sources)
        with col6:
          st.metric("Sources Used", num_sources_used)
        with col7:
          st.metric("Avg. Rank", avg_rank_display)
        with col8:
          st.metric("Extra Links", extra_links_count)

        st.divider()

        st.markdown(f"### 💬 Response ({response_time_s}):")
        # Format response text (convert citation references to inline links)
        formatted_detail_response = format_response_text(details['response_text'], details.get('citations', []))
        formatted_detail_response, extracted_images = extract_images_from_response(formatted_detail_response)

        if extracted_images:
          # Render images inline with minimal gaps
          img_html = "".join([f'<img src="{url}" style="width:210px;height:135px;object-fit:cover;margin:4px 6px 4px 0;vertical-align:top;"/>' for url in extracted_images])  # noqa: E501
          st.markdown(f"<div style='display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;'>{img_html}</div>", unsafe_allow_html=True)  # noqa: E501

        # Render markdown with indented container styling
        # Use newlines around content to ensure markdown processing works inside the div
        st.markdown(
          f'<div class="response-container">\n\n{formatted_detail_response}\n\n</div>',
          unsafe_allow_html=True
        )

        st.divider()

        if details.get('search_queries'):
          st.markdown(f"### 🔍 Search Queries ({len(details.get('search_queries', []))}):")
          for i, query in enumerate(details.get('search_queries', []), 1):
            # Display query with same styling as interactive tab
            st.markdown(f"""
            <div class="search-query">
                <strong>Query {i}:</strong> {query['query']}
            </div>
            """, unsafe_allow_html=True)

          st.divider()

          # Display sources differently for API vs Network Log
          data_source = details.get('data_source', 'api')
          if data_source == 'api':
            # API: Sources are associated with queries
            # Calculate total sources count
            total_sources_count = sum(len(q.get('sources', [])) for q in details.get('search_queries', []))
            st.markdown(f"### 📚 Sources Found ({total_sources_count}):")
            for i, query in enumerate(details.get('search_queries', []), 1):
              query_sources = query.get('sources', [])
              if query_sources:
                # Truncate long queries for display
                query_text = query.get('query', '')
                query_display = query_text if len(query_text) <= 60 else query_text[:60] + "..."
                with st.expander(f"{query_display} ({len(query_sources)} sources)", expanded=False):
                  for j, src in enumerate(query_sources, 1):
                    url_display = src.get('url') or 'No URL'
                    # Use domain as title fallback when title is missing
                    display_title = src.get('title') or src.get('domain') or 'Unknown source'
                    snippet = src.get('snippet_text') or src.get('snippet')
                    pub_date = src.get('pub_date')
                    snippet_display = snippet if snippet else "N/A"
                    pub_date_fmt = format_pub_date(pub_date) if pub_date else "N/A"
                    snippet_block = f"<div style='margin-top:4px; font-size:0.95rem;'><strong>Snippet:</strong> <em>{snippet_display}</em></div>"  # noqa: E501
                    pub_date_block = f"<small><strong>Published:</strong> {pub_date_fmt}</small>"
                    domain_link = f'<a href="{url_display}" target="_blank">{src.get("domain") or "Open source"}</a>'
                    st.markdown(f"""
                    <div class="source-item">
                        <strong>{j}. {display_title}</strong><br/>
                        <small>{domain_link}</small>
                        {snippet_block}
                        {pub_date_block}
                    </div>
                    """, unsafe_allow_html=True)
          else:
            # Network Log: Sources aren't associated with specific queries
            all_sources = details.get('all_sources') or []
            if all_sources:
              st.markdown(f"### 📚 Sources Found ({len(all_sources)}):")
              st.caption("_Note: Network logs don't provide reliable query-to-source mapping._")
              with st.expander(f"View all {len(all_sources)} sources", expanded=False):
                for j, src in enumerate(all_sources, 1):
                  url_display = src.get('url') or 'No URL'
                  # Use domain as title fallback when title is missing
                  display_title = src.get('title') or src.get('domain') or 'Unknown source'
                  snippet = src.get('snippet_text') or src.get('snippet')
                  pub_date = src.get('pub_date')
                  snippet_display = snippet if snippet else "N/A"
                  pub_date_fmt = format_pub_date(pub_date) if pub_date else "N/A"
                  snippet_block = f"<div style='margin-top:4px; font-size:0.95rem;'><strong>Snippet:</strong> <em>{snippet_display}</em></div>"  # noqa: E501
                  pub_date_block = f"<small><strong>Published:</strong> {pub_date_fmt}</small>"
                  domain_link = f'<a href="{url_display}" target="_blank">{src.get("domain") or "Open source"}</a>'
                  st.markdown(f"""
                  <div class="source-item">
                      <strong>{j}. {display_title}</strong><br/>
                      <small>{domain_link}</small>
                      {snippet_block}
                      {pub_date_block}
                  </div>
                  """, unsafe_allow_html=True)

        # Sources used (from web search) - only citations with ranks
        citations_with_rank = [c for c in details.get('citations', []) if c.get('rank')]
        if citations_with_rank:
          st.divider()
          st.markdown(f"### 📝 Sources Used ({len(citations_with_rank)}):")
          st.caption("Sources the model consulted via web search")

          # Build URL -> source lookup for metadata fallback
          all_sources = details.get('all_sources') or []
          url_to_source = {src['url']: src for src in all_sources if src.get('url')}

          for i, citation in enumerate(citations_with_rank, 1):
            with st.container():
              url_display = citation.get('url') or 'No URL'
              domain_link = f'<a href="{url_display}" target="_blank">{urlparse(url_display).netloc or url_display}</a>'

              # Extract rank and display in parentheses
              rank = citation.get('rank')
              rank_display = f" (Rank {rank})" if rank else ""

              # Extract domain from URL for fallback
              domain = urlparse(url_display).netloc if url_display != 'No URL' else 'Unknown domain'
              display_title = citation.get('title') or domain or 'Unknown source'

              # Get snippet and pub_date from citation metadata or source fallback
              snippet = citation.get('snippet')
              pub_date_val = citation.get('pub_date')

              # Fallback to source data if available
              if not snippet or not pub_date_val:
                source_fallback = url_to_source.get(url_display)
                if source_fallback:
                  snippet = snippet or source_fallback.get('snippet_text') or source_fallback.get('snippet')
                  pub_date_val = pub_date_val or source_fallback.get('pub_date')

              snippet_block = f"<div style='margin-top:4px; font-size:0.95rem;'><strong>Snippet:</strong> <em>{snippet or 'N/A'}</em></div>"  # noqa: E501
              pub_date_fmt = format_pub_date(pub_date_val) if pub_date_val else "N/A"
              pub_date_block = f"<small><strong>Published:</strong> {pub_date_fmt}</small>"

              st.markdown(f"""
              <div class="citation-item">
                  <strong>{i}. {display_title}{rank_display}</strong><br/>
                  {domain_link}
                  {snippet_block}
                  {pub_date_block}
              </div>
              """, unsafe_allow_html=True)

        # Extra links (citations not from search results)
        extra_links = [c for c in details.get('citations', []) if not c.get('rank')]
        if extra_links:
          st.divider()
          st.markdown(f"### 🔗 Extra Links ({len(extra_links)}):")
          st.caption("Links mentioned in the response that weren't from search results")

          for i, citation in enumerate(extra_links, 1):
            with st.container():
              url_display = citation.get('url') or 'No URL'
              domain_link = f'<a href="{url_display}" target="_blank">{urlparse(url_display).netloc or url_display}</a>'
              domain = urlparse(url_display).netloc if url_display != 'No URL' else 'Unknown domain'
              display_title = citation.get('title') or domain or 'Unknown source'

              # Get snippet if available
              snippet = citation.get('snippet')
              snippet_block = f"<div style='margin-top:4px; font-size:0.95rem;'><strong>Snippet:</strong> <em>{snippet or 'N/A'}</em></div>" if snippet else ""  # noqa: E501

              st.markdown(f"""
              <div class="citation-item">
                  <strong>{i}. {display_title}</strong><br/>
                  {domain_link}
                  {snippet_block}
              </div>
              """, unsafe_allow_html=True)

  except Exception as e:
    st.error(f"Error loading history: {str(e)}")
    st.error(f"Traceback: {traceback.format_exc()}")
