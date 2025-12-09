"""Batch analysis tab for testing multiple prompts."""

import time
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from frontend.components.models import get_all_models
from frontend.config import Config
from frontend.helpers.error_handling import safe_api_call
from frontend.helpers.metrics import compute_metrics, get_model_display_name
from frontend.helpers.serialization import namespace_to_dict
from frontend.network_capture.chatgpt_capturer import ChatGPTCapturer


def summarize_batch_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
  """Compute summary statistics for a batch run."""
  total_runs = len(results)
  successful = [r for r in results if 'error' not in r]
  failed = [r for r in results if 'error' in r]

  def safe_average(values: List[Optional[float]]) -> Optional[float]:
    valid = [v for v in values if v is not None]
    if not valid:
      return None
    return sum(valid) / len(valid)

  avg_sources = safe_average([r.get('sources') for r in successful])
  avg_sources_used = safe_average([r.get('sources_used') for r in successful])
  avg_rank = safe_average([r.get('avg_rank') for r in successful if r.get('avg_rank') is not None])

  return {
    'total_runs': total_runs,
    'successful': len(successful),
    'failed': failed,
    'avg_sources': avg_sources,
    'avg_sources_used': avg_sources_used,
    'avg_rank': avg_rank,
  }


def build_rows_from_batch_status(status_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
  """Convert backend batch status payload into table rows."""
  rows: List[Dict[str, Any]] = []
  for response in status_payload.get('results', []):
    model_label = response.get('model_display_name') or get_model_display_name(response.get('model', ''))
    rows.append({
      'prompt': response.get('prompt'),
      'model': model_label,
      'searches': len(response.get('search_queries', [])),
      'sources': response.get('sources_found', 0),
      'sources_used': response.get('sources_used', 0),
      'avg_rank': response.get('avg_rank'),
      'response_time_s': (response.get('response_time_ms') or 0) / 1000,
    })

  for error in status_payload.get('errors', []):
    model_label = get_model_display_name(error.get('model', '')) if error.get('model') else error.get('provider')
    rows.append({
      'prompt': error.get('prompt'),
      'model': model_label,
      'error': error.get('error', 'Unknown error'),
    })

  return rows


def render_batch_results(results: List[Dict[str, Any]], placeholder: Optional[Any] = None):
  """Render batch result summary and table, optionally into a placeholder."""
  if placeholder:
    placeholder.empty()
    target = placeholder.container()
  else:
    target = st

  if not results:
    return

  summary = summarize_batch_results(results)

  target.divider()
  target.markdown("### 📊 Batch Results")

  col1, col2, col3, col4, col5 = target.columns(5)
  with col1:
    col1.metric("Total Runs", summary['total_runs'])
  with col2:
    col2.metric("Successful", summary['successful'])
  with col3:
    if summary['avg_sources'] is not None:
      col3.metric("Avg Sources", f"{summary['avg_sources']:.1f}")
    else:
      col3.metric("Avg Sources", "N/A")
  with col4:
    if summary['avg_sources_used'] is not None:
      col4.metric("Avg Sources Used", f"{summary['avg_sources_used']:.1f}")
    else:
      col4.metric("Avg Sources Used", "N/A")
  with col5:
    if summary['avg_rank'] is not None:
      col5.metric("Avg Rank", f"{summary['avg_rank']:.1f}")
    else:
      col5.metric("Avg Rank", "N/A")

  target.markdown("#### Detailed Results")
  df_results = pd.DataFrame(results)

  if not df_results.empty and 'error' not in df_results.columns:
    df_results['avg_rank_display'] = df_results['avg_rank'].apply(
      lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
    )
    df_results['response_time_display'] = df_results['response_time_s'].apply(
      lambda x: f"{x:.1f}s" if pd.notna(x) else "N/A"
    )

    display_df = df_results[['prompt', 'model', 'searches', 'sources', 'sources_used',
                             'avg_rank_display', 'response_time_display']]
    display_df.columns = ['Prompt', 'Model', 'Searches', 'Sources Found', 'Sources Used',
                          'Avg. Rank', 'Response Time']
    target.dataframe(display_df, use_container_width=True)
  else:
    target.dataframe(df_results, use_container_width=True)

  csv = df_results.to_csv(index=False)
  download_key_suffix = st.session_state.get('batch_results_download_key', 'default')
  render_counter = st.session_state.get('batch_results_render_counter', 0) + 1
  st.session_state['batch_results_render_counter'] = render_counter
  target.download_button(
    label="📥 Download Results as CSV",
    data=csv,
    file_name=f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    mime="text/csv",
    key=f"batch-results-download-{download_key_suffix}-{render_counter}"
  )

  if summary['failed']:
    target.warning(f"⚠️ {len(summary['failed'])} prompts failed")
    with target.expander("View Errors"):
      for idx, result in enumerate(summary['failed'], 1):
        target.error(f"{idx}. {result['prompt'][:50]}...\n Error: {result['error']}")


def tab_batch():
  """Tab 2: Batch Analysis."""
  st.session_state.setdefault('batch_results', [])
  st.session_state.setdefault('batch_results_download_key', 'initial')
  st.session_state.setdefault('batch_results_render_counter', 0)
  st.markdown("### 📦 Batch Analysis")
  st.caption("Run multiple prompts and analyze aggregate results")

  # Load all available models
  models = get_all_models()

  if not models:
    st.error("No API keys configured. Please set up your .env file with at least one provider API key.")
    return

  # Filter models based on data collection mode
  if st.session_state.data_collection_mode == 'network_log':
    # Only OpenAI models supported for network capture
    model_labels = [label for label in models.keys() if models[label][0] == 'openai']
    if not model_labels:
      st.error("Network log mode requires OpenAI models. Please configure OPENAI_API_KEY in your .env file or switch to API mode.")
      return
    st.info("🌐 **Network Capture Mode**: Only OpenAI/ChatGPT models available")
  else:
    model_labels = list(models.keys())

  # Model selection
  selected_labels = st.multiselect(
    "Select Models for Batch",
    model_labels,
    default=[model_labels[0]] if model_labels else [],
    help="Choose one or more models to compare across all prompts"
  )

  # Extract providers and models from selections
  selected_models = []
  if selected_labels:
    for label in selected_labels:
      provider, model = models[label]
      selected_models.append((label, provider, model))

  # Prompt input methods
  st.markdown("#### Enter Prompts")
  input_method = st.radio("Input Method", ["Text Area", "CSV Upload"], horizontal=True)

  prompts = []

  if input_method == "Text Area":
    prompts_text = st.text_area(
      "Enter prompts (one per line)",
      height=200,
      placeholder="What is the weather today?\nTell me about AI advancements\nWho won the latest sports championship?"
    )
    if prompts_text:
      prompts = [p.strip() for p in prompts_text.split('\n') if p.strip()]

  else:  # CSV Upload
    uploaded_file = st.file_uploader("Upload CSV file with 'prompt' column", type=['csv'])
    if uploaded_file is not None:
      try:
        df = pd.read_csv(uploaded_file)
        if 'prompt' not in df.columns:
          st.error("CSV must have a 'prompt' column")
        else:
          prompts = df['prompt'].dropna().tolist()
          st.success(f"Loaded {len(prompts)} prompts from CSV")
      except Exception as e:
        st.error(f"Error reading CSV: {str(e)}")

  # Display prompt and model count
  if prompts and selected_models:
    total_runs = len(prompts) * len(selected_models)
    st.info(f"Ready to process {len(prompts)} prompt(s) × {len(selected_models)} model(s) = {total_runs} total runs")

  run_batch_clicked = st.button(
    "▶️ Run Batch Analysis",
    type="primary",
    disabled=len(prompts) == 0 or len(selected_models) == 0
  )

  rendered_results = False
  results_placeholder = None

  if run_batch_clicked:
    st.session_state.batch_results = []
    st.session_state.batch_results_render_counter = 0

    if st.session_state.data_collection_mode == 'api':
      model_ids = [model_name for (_, _, model_name) in selected_models]
      progress_bar = st.progress(0)
      status_text = st.empty()
      results_placeholder = st.empty()

      batch_payload, creation_error = safe_api_call(
        st.session_state.api_client.start_batch,
        prompts=prompts,
        models=model_ids,
        show_spinner=True,
        spinner_text="Submitting batch to backend..."
      )
      if creation_error:
        st.error(creation_error)
        return

      batch_id = batch_payload.get('batch_id')
      total_tasks = batch_payload.get('total_tasks', len(prompts) * len(selected_models))
      st.session_state.batch_results_download_key = f"api-{batch_id or int(time.time())}"

      status_text.text(f"Batch {batch_id} submitted. Waiting for first results...")

      while True:
        status_data, status_error = safe_api_call(
          st.session_state.api_client.get_batch_status,
          batch_id=batch_id,
          show_spinner=False
        )
        if status_error:
          st.error(status_error)
          break

        rows = build_rows_from_batch_status(status_data)
        st.session_state.batch_results = rows

        completed = status_data.get('completed_tasks', 0)
        status_label = status_data.get('status', 'processing').title()
        progress = completed / total_tasks if total_tasks else 0
        progress_bar.progress(progress)
        status_text.text(f"{status_label}: {completed}/{total_tasks} runs complete")

        render_batch_results(rows, placeholder=results_placeholder)
        rendered_results = True

        if status_data.get('status') in ('completed', 'failed'):
          break
        time.sleep(1)

      status_text.text("✅ Batch processing complete!")

    else:
      # Progress tracking
      progress_bar = st.progress(0)
      status_text = st.empty()
      results_placeholder = st.empty()

      # Calculate total runs
      total_runs = len(prompts) * len(selected_models)
      current_run = 0
      st.session_state.batch_results_download_key = f"net-{int(time.time())}"

      # Process each prompt with each model in network capture mode
      for prompt_idx, prompt in enumerate(prompts):
        for model_label, provider_name, model_name in selected_models:
          current_run += 1
          status_text.text(f"Processing run {current_run}/{total_runs}: {model_label} - Prompt {prompt_idx + 1}/{len(prompts)}")

          try:
            # Only ChatGPT is supported for network logs currently
            if provider_name != 'openai':
              raise Exception(f"Network log mode only supports OpenAI/ChatGPT. Skipping {provider_name}")

            # Check if ChatGPT credentials are configured
            if not Config.CHATGPT_EMAIL or not Config.CHATGPT_PASSWORD:
              raise Exception("ChatGPT credentials not found. Please add CHATGPT_EMAIL and CHATGPT_PASSWORD to your .env file.")

            # Initialize and use capturer
            capturer = ChatGPTCapturer()
            capturer.start_browser(headless=not st.session_state.network_show_browser)

            try:
              # Authenticate with credentials from Config
              # Session persistence will restore saved sessions automatically
              if not capturer.authenticate(
                email=Config.CHATGPT_EMAIL,
                password=Config.CHATGPT_PASSWORD
              ):
                raise Exception("Failed to authenticate with ChatGPT")

              # Send prompt and capture
              # Always use 'chatgpt-free' for network capture (free accounts don't have model selection)
              provider_response = capturer.send_prompt(prompt, 'chatgpt-free')

              # Convert ProviderResponse to display format and save to database
              search_queries = [SimpleNamespace(
                query=q.query,
                sources=[SimpleNamespace(
                  url=s.url, title=s.title, domain=s.domain, rank=s.rank,
                  pub_date=s.pub_date, snippet_text=s.snippet_text,
                  internal_score=s.internal_score, metadata=s.metadata
                ) for s in q.sources],
                timestamp=q.timestamp,
                order_index=q.order_index
              ) for q in provider_response.search_queries]

              citations = [SimpleNamespace(
                url=c.url, title=c.title, rank=c.rank,
                snippet_used=c.snippet_used,
                citation_confidence=c.citation_confidence,
                metadata=c.metadata
              ) for c in provider_response.citations]

              all_sources = [SimpleNamespace(
                url=s.url, title=s.title, domain=s.domain, rank=s.rank,
                pub_date=s.pub_date, snippet_text=s.snippet_text,
                internal_score=s.internal_score, metadata=s.metadata
              ) for s in provider_response.sources]

              # Compute metrics
              metrics = compute_metrics(search_queries, citations, all_sources)

              # Create response object
              response = SimpleNamespace(
                provider=provider_response.provider,
                model=provider_response.model,
                model_display_name=get_model_display_name(provider_response.model),
                response_text=provider_response.response_text,
                search_queries=search_queries,
                all_sources=all_sources,
                citations=citations,
                response_time_ms=provider_response.response_time_ms,
                data_source='network_log',
                sources_found=metrics['sources_found'],
                sources_used=metrics['sources_used'],
                avg_rank=metrics['avg_rank'],
                extra_links_count=metrics['extra_links_count'],
                raw_response=provider_response.raw_response
              )

              # Save to database via backend API
              # Convert SimpleNamespace objects to dicts for JSON serialization
              _, save_error = safe_api_call(
                st.session_state.api_client.save_network_log,
                provider=provider_response.provider,
                model=provider_response.model,
                prompt=prompt,
                response_text=provider_response.response_text,
                search_queries=namespace_to_dict(search_queries),
                sources=namespace_to_dict(all_sources),
                citations=namespace_to_dict(citations),
                response_time_ms=provider_response.response_time_ms,
                raw_response=provider_response.raw_response,
                extra_links_count=metrics['extra_links_count'],
                show_spinner=False
              )
              if save_error:
                raise Exception(f"Failed to save: {save_error}")

            finally:
              # Always cleanup browser
              capturer.stop_browser()

            # Store result using backend-computed metrics
            st.session_state.batch_results.append({
              'prompt': prompt,
              'model': model_label,
              'searches': len(response.search_queries),
              'sources': getattr(response, 'sources_found', 0),
              'sources_used': getattr(response, 'sources_used', 0),
              'avg_rank': getattr(response, 'avg_rank', None),
              'response_time_s': response.response_time_ms / 1000
            })

          except Exception as e:
            st.session_state.batch_results.append({
              'prompt': prompt,
              'model': model_label,
              'error': str(e)
            })

          # Update progress
          progress_bar.progress(current_run / total_runs)
          render_batch_results(st.session_state.batch_results, placeholder=results_placeholder)
          rendered_results = True

      status_text.text("✅ Batch processing complete!")

  if results_placeholder is None:
    results_placeholder = st.empty()

  if st.session_state.batch_results and not rendered_results:
    render_batch_results(st.session_state.batch_results, placeholder=results_placeholder)
