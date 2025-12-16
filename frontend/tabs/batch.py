"""Batch analysis tab for testing multiple prompts."""

import time
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from frontend.components.models import get_all_models
from frontend.helpers.error_handling import safe_api_call
from frontend.helpers.export_utils import dataframe_to_csv_bytes
from frontend.helpers.metrics import compute_metrics, get_model_display_name
from frontend.helpers.serialization import namespace_to_dict
from frontend.network_capture.account_pool import AccountPoolError, AccountQuotaExceededError, select_chatgpt_account
from frontend.network_capture.chatgpt_capturer import ChatGPTCapturer


def _safe_rerun():
  """Streamlit rerun helper to support both old and new APIs."""
  rerun_fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
  if rerun_fn:
    rerun_fn()


def summarize_batch_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
  """Compute summary statistics for a batch run."""
  total_runs = len(results)
  successful = [r for r in results if 'error' not in r]
  failed = [r for r in results if 'error' in r]

  def safe_average(values: List[Optional[float]]) -> Optional[float]:
    """Return average of provided values ignoring None entries."""
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

  export_df = df_results.copy()

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
    export_df = display_df.copy()
  else:
    target.dataframe(df_results, use_container_width=True)
    rename_map = {
      'prompt': 'Prompt',
      'model': 'Model',
      'searches': 'Searches',
      'sources': 'Sources Found',
      'sources_used': 'Sources Used',
      'avg_rank': 'Avg. Rank',
      'response_time_s': 'Response Time (s)',
      'error': 'Error'
    }
    export_df = export_df.rename(columns={k: v for k, v in rename_map.items() if k in export_df.columns})

  csv_bytes = dataframe_to_csv_bytes(export_df, text_columns=['Prompt'])
  download_key_suffix = st.session_state.get('batch_results_download_key', 'default')
  render_counter = st.session_state.get('batch_results_render_counter', 0) + 1
  st.session_state['batch_results_render_counter'] = render_counter
  target.download_button(
    label="📥 Download Results as CSV",
    data=csv_bytes,
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
  st.session_state.setdefault('active_api_batch', None)
  st.session_state.setdefault('api_cancel_requested', False)
  st.session_state.setdefault('api_cancel_sent', False)
  st.session_state.setdefault('network_batch_state', None)
  st.session_state.setdefault('network_cancel_requested', False)
  st.session_state.setdefault('network_show_browser', False)
  st.markdown("### 📦 Batch Analysis")
  st.caption("Run multiple prompts and analyze aggregate results")

  mode = st.radio(
    "Data collection mode",
    ["API", "Web"],
    horizontal=True,
    key="batch_mode_radio"
  )
  is_network_mode = mode == "Web"
  if is_network_mode:
    st.checkbox(
      "Show browser window during captures",
      value=st.session_state.network_show_browser,
      key="network_show_browser",
      help="Uncheck to run headless for faster captures.",
    )

  # Load all available models
  models = get_all_models()

  if not models:
    st.error("No API keys configured. Please set up your .env file with at least one provider API key.")
    return

  # Filter models based on data collection mode
  if is_network_mode:
    # Only OpenAI models supported for network capture
    model_labels = [label for label in models.keys() if models[label][0] == 'openai']
    if not model_labels:
      st.error("Network log mode requires OpenAI models. Please configure OPENAI_API_KEY in your .env file or switch to API mode.")  # noqa: E501
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

  disable_run = (
    len(prompts) == 0
    or len(selected_models) == 0
    or bool(st.session_state.active_api_batch)
    or bool(st.session_state.network_batch_state)
  )
  run_batch_clicked = st.button(
    "▶️ Run Batch Analysis",
    type="primary",
    disabled=disable_run
  )

  rendered_results = False

  active_api_batch = st.session_state.active_api_batch if not is_network_mode else None  # noqa: E501
  network_batch_state = st.session_state.network_batch_state if is_network_mode else None  # noqa: E501

  # Handle ongoing API batch polling (non-blocking to allow cancel button)
  if active_api_batch and not is_network_mode:
    batch_id = active_api_batch.get('batch_id')
    total_tasks = active_api_batch.get('total_tasks', 0)

    status_indicator = st.status(f"Batch {batch_id} in progress...", expanded=False)
    cancel_clicked = st.button("⏹ Cancel Batch", key="cancel_api_batch_btn")
    if cancel_clicked:
      st.session_state.api_cancel_requested = True

    status_data = None
    if st.session_state.api_cancel_requested and not st.session_state.api_cancel_sent:
      status_data, cancel_error = safe_api_call(
        st.session_state.api_client.cancel_batch,
        batch_id=batch_id,
        show_spinner=True,
        spinner_text="Requesting cancellation..."
      )
      if cancel_error:
        st.error(cancel_error)
      else:
        st.session_state.api_cancel_sent = True

    if status_data is None:
      status_data, status_error = safe_api_call(
        st.session_state.api_client.get_batch_status,
        batch_id=batch_id,
        show_spinner=False
      )
      if status_error:
        st.error(status_error)
        status_data = None

    if status_data:
      rows = build_rows_from_batch_status(status_data)
      st.session_state.batch_results = rows

      completed = status_data.get('completed_tasks', 0)
      status_label = status_data.get('status', 'processing').title()
      progress = completed / total_tasks if total_tasks else 0

      st.progress(progress)
      status_indicator.update(
        label=f"{status_label}: {completed}/{total_tasks} runs complete",
        state="running"
      )

      render_batch_results(rows)
      rendered_results = True

      if status_data.get('status') == 'cancelled' and status_data.get('cancel_reason'):
        st.warning(f"Batch cancelled: {status_data.get('cancel_reason')}")

      if status_data.get('status') in ('completed', 'failed', 'cancelled'):
        status_indicator.update(label=f"✅ Batch {status_data.get('status', '').title()}!", state="complete")
        st.session_state.active_api_batch = None
        st.session_state.api_cancel_requested = False
        st.session_state.api_cancel_sent = False
      else:
        time.sleep(1)
        _safe_rerun()

  # Handle network capture batch execution one task per rerun to enable cancel
  if network_batch_state and is_network_mode:
    total_runs = network_batch_state.get('total_runs', 0)
    completed_runs = network_batch_state.get('completed_runs', 0)
    tasks = network_batch_state.get('tasks', [])

    status_indicator = st.status("Network capture batch running...", expanded=False)
    cancel_clicked = st.button("⏹ Cancel Batch", key="cancel_network_batch_btn")
    if cancel_clicked:
      st.session_state.network_cancel_requested = True
      network_batch_state['tasks'] = []

    if tasks and not st.session_state.network_cancel_requested:
      prompt_idx, prompt, model_label, provider_name, model_name = tasks.pop(0)
      try:
        if provider_name != 'openai':
          raise Exception(f"Network log mode only supports OpenAI/ChatGPT. Skipping {provider_name}")

        try:
          account, storage_state_path = select_chatgpt_account()
        except AccountQuotaExceededError as exc:
          wait_hint = ""
          if exc.next_available_in_seconds is not None:
            minutes = max(1, int(exc.next_available_in_seconds / 60))
            wait_hint = f" Next slot available in ~{minutes} min."
          raise Exception(f"{exc}.{wait_hint}") from exc
        except AccountPoolError as exc:
          raise Exception(str(exc)) from exc

        capturer = ChatGPTCapturer(storage_state_path=storage_state_path)
        capturer.start_browser(headless=not st.session_state.network_show_browser)

        try:
          if not capturer.authenticate(
            email=account.email,
            password=account.password,
          ):
            raise Exception("Failed to authenticate with ChatGPT")

          provider_response = capturer.send_prompt(prompt, 'chatgpt-free')

          search_queries = [SimpleNamespace(
            query=q.query,
            sources=[SimpleNamespace(
              url=s.url, title=s.title, domain=s.domain, rank=s.rank,
              pub_date=s.pub_date,
              search_description=getattr(s, "search_description", None) or getattr(s, "snippet_text", None),
              internal_score=s.internal_score, metadata=s.metadata
            ) for s in q.sources],
            timestamp=q.timestamp,
            order_index=q.order_index
          ) for q in provider_response.search_queries]

          citations = [SimpleNamespace(
            url=c.url, title=c.title, rank=c.rank,
            snippet_cited=c.snippet_cited,
            citation_confidence=c.citation_confidence,
            metadata=c.metadata
          ) for c in provider_response.citations]

          all_sources = [SimpleNamespace(
            url=s.url, title=s.title, domain=s.domain, rank=s.rank,
            pub_date=s.pub_date,
            search_description=getattr(s, "search_description", None) or getattr(s, "snippet_text", None),
            internal_score=s.internal_score, metadata=s.metadata
          ) for s in provider_response.sources]

          metrics = compute_metrics(search_queries, citations, all_sources)

          response = SimpleNamespace(
            provider=provider_response.provider,
            model=provider_response.model,
            model_display_name=get_model_display_name(provider_response.model),
            response_text=provider_response.response_text,
            search_queries=search_queries,
            all_sources=all_sources,
            citations=citations,
            response_time_ms=provider_response.response_time_ms,
            data_source='web',
            sources_found=metrics['sources_found'],
            sources_used=metrics['sources_used'],
            avg_rank=metrics['avg_rank'],
            extra_links_count=metrics['extra_links_count'],
            raw_response=provider_response.raw_response
          )

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

          st.session_state.batch_results.append({
            'prompt': prompt,
            'model': model_label,
            'searches': len(response.search_queries),
            'sources': getattr(response, 'sources_found', 0),
            'sources_used': getattr(response, 'sources_used', 0),
            'avg_rank': getattr(response, 'avg_rank', None),
            'response_time_s': response.response_time_ms / 1000
          })

        finally:
          capturer.stop_browser()

      except Exception as e:
        st.session_state.batch_results.append({
          'prompt': prompt,
          'model': model_label,
          'error': str(e)
        })

      completed_runs += 1
      network_batch_state['completed_runs'] = completed_runs
      network_batch_state['tasks'] = tasks
      network_batch_state['results'] = st.session_state.batch_results
      st.session_state.network_batch_state = network_batch_state

      st.progress(completed_runs / total_runs if total_runs else 0)
      status_indicator.update(
        label=f"Processing {completed_runs}/{total_runs} · {model_label} · Prompt {prompt_idx + 1}/{len(prompts)}",
        state="running"
      )
      render_batch_results(st.session_state.batch_results)
      rendered_results = True

      if st.session_state.network_cancel_requested:
        status_indicator.update(label="⏹ Batch cancelled", state="complete")
        st.session_state.network_batch_state = None
        st.session_state.network_cancel_requested = False
      elif tasks:
        time.sleep(0.5)
        _safe_rerun()
      else:
        status_indicator.update(label="✅ Batch processing complete!", state="complete")
        st.session_state.network_batch_state = None
        st.session_state.network_cancel_requested = False
    else:
      # No tasks (either completed or cancelled before running)
      if st.session_state.network_cancel_requested:
        status_indicator.update(label="⏹ Batch cancelled", state="complete")
      else:
        status_indicator.update(label="✅ Batch processing complete!", state="complete")
      st.session_state.network_batch_state = None
      st.session_state.network_cancel_requested = False
      if st.session_state.batch_results:
        render_batch_results(st.session_state.batch_results)
        rendered_results = True

  if run_batch_clicked:
    st.session_state.batch_results = []
    st.session_state.batch_results_render_counter = 0

    if not is_network_mode:
      model_ids = [model_name for (_, _, model_name) in selected_models]
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

      st.session_state.active_api_batch = {
        'batch_id': batch_id,
        'total_tasks': total_tasks
      }
      st.session_state.api_cancel_requested = False
      st.session_state.api_cancel_sent = False
      _safe_rerun()

    else:
      # Initialize network capture batch state; process one task per rerun
      tasks = []
      for prompt_idx, prompt in enumerate(prompts):
        for model_label, provider_name, model_name in selected_models:
          tasks.append((prompt_idx, prompt, model_label, provider_name, model_name))

      st.session_state.batch_results_download_key = f"net-{int(time.time())}"
      st.session_state.batch_results = []
      st.session_state.network_batch_state = {
        'tasks': tasks,
        'total_runs': len(tasks),
        'completed_runs': 0,
        'results': []
      }
      st.session_state.network_cancel_requested = False
      _safe_rerun()

  if st.session_state.batch_results and not rendered_results:
    render_batch_results(st.session_state.batch_results)
