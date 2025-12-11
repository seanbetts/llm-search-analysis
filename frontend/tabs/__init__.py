"""Tab modules for the Streamlit application."""

from frontend.tabs.batch import tab_batch
from frontend.tabs.history import tab_history
from frontend.tabs.interactive import tab_interactive
from frontend.tabs.live import tab_live

__all__ = ['tab_interactive', 'tab_batch', 'tab_history', 'tab_live']
