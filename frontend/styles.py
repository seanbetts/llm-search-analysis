"""Global CSS styles for the Streamlit application."""

import streamlit as st


def load_styles():
  """Load and inject custom CSS styles into the Streamlit app."""
  st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .search-query {
        background-color: var(--secondary-background-color, #e8f4f8);
        color: var(--text-color, #000);
        padding: 0.5rem 1rem;
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
        border-radius: 0.25rem;
    }
    .source-item {
        background-color: var(--secondary-background-color, #f9f9f9);
        color: var(--text-color, #000);
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 0.25rem;
        border: 1px solid rgba(0,0,0,0.1);
    }
    .citation-item {
        background-color: var(--secondary-background-color, #fff8e1);
        color: var(--text-color, #000);
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 0.25rem;
        border: 1px solid rgba(0,0,0,0.1);
    }
    /* Constrain images in responses to a small, uniform size and inline layout */
    .stMarkdown img {
        width: 140px;
        height: 90px;
        object-fit: cover;
        margin: 4px 8px 4px 0;
        display: inline-block;
        vertical-align: top;
        float: left;
    }
    .stMarkdown::after {
        content: "";
        display: block;
        clear: both;
    }
    .stMarkdown p {
        clear: both;
    }
    .response-container {
        margin-left: 18px;
        padding-left: 12px;
        border-left: 2px solid #d0d0d0;
    }
</style>
""", unsafe_allow_html=True)
