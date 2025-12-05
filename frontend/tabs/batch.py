"""Batch analysis tab for testing multiple prompts."""

import streamlit as st
import pandas as pd
from datetime import datetime
from src.config import Config
from frontend.components.models import get_all_models


def tab_batch():
  """Tab 2: Batch Analysis."""
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

  # Run button
  if st.button("▶️ Run Batch Analysis", type="primary", disabled=len(prompts) == 0 or len(selected_models) == 0):
    st.session_state.batch_results = []

    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Calculate total runs
    total_runs = len(prompts) * len(selected_models)
    current_run = 0

    # Process each prompt with each model
    for prompt_idx, prompt in enumerate(prompts):
      for model_label, provider_name, model_name in selected_models:
        current_run += 1
        status_text.text(f"Processing run {current_run}/{total_runs}: {model_label} - Prompt {prompt_idx + 1}/{len(prompts)}")

        try:
          # Check data collection mode and route accordingly
          if st.session_state.data_collection_mode == 'network_log':
            # Use network log capture
            from src.network_capture.chatgpt_capturer import ChatGPTCapturer

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
              from types import SimpleNamespace
              from frontend.helpers.metrics import compute_metrics, get_model_display_name

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
              st.session_state.api_client.save_network_log(
                provider=provider_response.provider,
                model=provider_response.model,
                prompt=prompt,
                response_text=provider_response.response_text,
                search_queries=search_queries,
                sources=all_sources,
                citations=citations,
                response_time_ms=provider_response.response_time_ms,
                raw_response=provider_response.raw_response,
                extra_links_count=metrics['extra_links_count']
              )

            finally:
              # Always cleanup browser
              capturer.stop_browser()

          else:
            # Use API client to send prompt (handles provider call AND database save)
            response_data = st.session_state.api_client.send_prompt(
              prompt=prompt,
              provider=provider_name,
              model=model_name,
              data_mode="api",
              headless=True
            )

          # Store result using backend-computed metrics
          if st.session_state.data_collection_mode == 'api':
            # For API mode, use backend-computed metrics from response_data dict
            st.session_state.batch_results.append({
              'prompt': prompt,
              'model': model_label,
              'searches': len(response_data.get('search_queries', [])),
              'sources': response_data.get('sources_found', 0),
              'sources_used': response_data.get('sources_used', 0),
              'avg_rank': response_data.get('avg_rank'),
              'response_time_s': response_data.get('response_time_ms', 0) / 1000
            })
          else:
            # For network log mode, use backend-computed metrics from response object
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

    status_text.text("✅ Batch processing complete!")

  # Display results
  if st.session_state.batch_results:
    st.divider()
    st.markdown("### 📊 Batch Results")

    # Summary stats
    successful = [r for r in st.session_state.batch_results if 'error' not in r]
    failed = [r for r in st.session_state.batch_results if 'error' in r]

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
      st.metric("Total Runs", len(st.session_state.batch_results))
    with col2:
      st.metric("Successful", len(successful))
    with col3:
      if successful:
        avg_sources = sum(r['sources'] for r in successful) / len(successful)
        st.metric("Avg Sources", f"{avg_sources:.1f}")
    with col4:
      if successful:
        avg_sources_used = sum(r['sources_used'] for r in successful) / len(successful)
        st.metric("Avg Sources Used", f"{avg_sources_used:.1f}")
    with col5:
      if successful:
        ranks = [r['avg_rank'] for r in successful if r['avg_rank'] is not None]
        if ranks:
          overall_avg_rank = sum(ranks) / len(ranks)
          st.metric("Avg Rank", f"{overall_avg_rank:.1f}")
        else:
          st.metric("Avg Rank", "N/A")

    # Results table
    st.markdown("#### Detailed Results")
    df_results = pd.DataFrame(st.session_state.batch_results)

    # Format the display columns
    if not df_results.empty and 'error' not in df_results.columns:
      # Format avg_rank for display
      df_results['avg_rank_display'] = df_results['avg_rank'].apply(
        lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
      )

      # Format response_time for display
      df_results['response_time_display'] = df_results['response_time_s'].apply(
        lambda x: f"{x:.1f}s" if pd.notna(x) else "N/A"
      )

      # Select and rename columns for display
      display_df = df_results[['prompt', 'model', 'searches', 'sources', 'sources_used',
                               'avg_rank_display', 'response_time_display']]
      display_df.columns = ['Prompt', 'Model', 'Searches', 'Sources Found', 'Sources Used',
                           'Avg. Rank', 'Response Time']

      st.dataframe(display_df, use_container_width=True)
    else:
      st.dataframe(df_results, use_container_width=True)

    # Export button
    csv = df_results.to_csv(index=False)
    st.download_button(
      label="📥 Download Results as CSV",
      data=csv,
      file_name=f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
      mime="text/csv"
    )

    # Show errors if any
    if failed:
      st.warning(f"⚠️ {len(failed)} prompts failed")
      with st.expander("View Errors"):
        for idx, result in enumerate(failed, 1):
          st.error(f"{idx}. {result['prompt'][:50]}...\n Error: {result['error']}")
