"""Tab modules for the Streamlit application."""

from frontend.tabs.api import tab_api
from frontend.tabs.batch import tab_batch
from frontend.tabs.history import tab_history
from frontend.tabs.web import tab_web

__all__ = ['tab_api', 'tab_web', 'tab_batch', 'tab_history']
