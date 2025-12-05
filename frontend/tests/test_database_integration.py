"""
Integration tests for database persistence.

These tests verify that analyses are correctly saved to the database
in both API mode and network_log mode.
"""

import pytest
import tempfile
import os
from types import SimpleNamespace
from datetime import datetime
from src.database import Database
from src.config import Config


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
        db_path = tmp.name

    # Create database with temp file
    db = Database(database_url=f'sqlite:///{db_path}')
    db.create_tables()
    db.ensure_providers()

    yield db

    # Cleanup
    try:
        os.unlink(db_path)
    except Exception:
        pass


class TestDatabasePersistence:
    """Test that all analysis modes save to database correctly."""

    def test_save_api_mode_interaction(self, test_db):
        """Test saving an API mode interaction to database."""
        # Create test data
        search_queries = [
            SimpleNamespace(
                query='test query',
                sources=[
                    SimpleNamespace(
                        url='https://example.com/1',
                        title='Test Source 1',
                        domain='example.com',
                        rank=1,
                        pub_date='2024-01-01',
                        snippet_text='Test snippet',
                        internal_score=None,
                        metadata=None
                    )
                ],
                timestamp=datetime.now(),
                order_index=0
            )
        ]

        citations = [
            SimpleNamespace(
                url='https://example.com/1',
                title='Test Source 1',
                rank=1,
                snippet_used='Test snippet',
                citation_confidence=None,
                metadata={'query_index': 0}
            )
        ]

        # Save interaction
        response_id = test_db.save_interaction(
            provider_name='openai',
            model='gpt-5.1',
            prompt='Test prompt',
            response_text='Test response',
            search_queries=search_queries,
            sources=[],  # API mode: sources are in query.sources
            citations=citations,
            response_time_ms=1000,
            raw_response={'test': 'data'},
            data_source='api',
            extra_links_count=0
        )

        # Verify saved
        assert response_id is not None

        # Retrieve and verify
        interactions = test_db.get_recent_interactions(limit=10)
        assert len(interactions) == 1

        interaction = interactions[0]
        assert interaction['prompt'] == 'Test prompt'
        assert interaction['model'] == 'gpt-5.1'
        assert interaction['provider'] == 'OpenAI'
        assert interaction['searches'] == 1
        assert interaction['sources'] == 1
        assert interaction['citations'] == 1
        assert interaction['avg_rank'] == 1.0
        assert interaction['extra_links'] == 0
        assert interaction['data_source'] == 'api'

    def test_save_network_log_interaction(self, test_db):
        """Test saving a network_log mode interaction to database."""
        # Create test data
        search_queries = [
            SimpleNamespace(
                query='test query',
                sources=[],  # Network log: sources may be empty in queries
                timestamp=datetime.now(),
                order_index=0
            )
        ]

        all_sources = [
            SimpleNamespace(
                url='https://example.com/1',
                title='Test Source 1',
                domain='example.com',
                rank=1,
                pub_date='2024-01-01',
                snippet_text='Test snippet',
                internal_score=0.95,
                metadata={'network_log_data': 'test'}
            ),
            SimpleNamespace(
                url='https://example.com/2',
                title='Test Source 2',
                domain='example.com',
                rank=2,
                pub_date='2024-01-02',
                snippet_text='Test snippet 2',
                internal_score=0.85,
                metadata=None
            )
        ]

        citations = [
            SimpleNamespace(
                url='https://example.com/1',
                title='Test Source 1',
                rank=1,
                snippet_used='Test snippet',
                citation_confidence=0.9,
                metadata={'query_index': 0}
            ),
            SimpleNamespace(
                url='https://example.com/extra',
                title='Extra Link',
                rank=None,  # No rank = extra link
                snippet_used=None,
                citation_confidence=None,
                metadata=None
            )
        ]

        # Save interaction
        response_id = test_db.save_interaction(
            provider_name='openai',
            model='chatgpt-free',
            prompt='Test network log prompt',
            response_text='Test network log response',
            search_queries=search_queries,
            sources=all_sources,  # Network log: sources passed at top level
            citations=citations,
            response_time_ms=2000,
            raw_response={'network': 'log', 'data': 'test'},
            data_source='network_log',
            extra_links_count=1
        )

        # Verify saved
        assert response_id is not None

        # Retrieve and verify
        interactions = test_db.get_recent_interactions(limit=10)
        assert len(interactions) == 1

        interaction = interactions[0]
        assert interaction['prompt'] == 'Test network log prompt'
        assert interaction['model'] == 'chatgpt-free'
        assert interaction['provider'] == 'OpenAI'
        assert interaction['searches'] == 1
        assert interaction['sources'] == 2  # From all_sources
        assert interaction['citations'] == 1  # Only ranked citations
        assert interaction['avg_rank'] == 1.0
        assert interaction['extra_links'] == 1  # Citations without rank
        assert interaction['data_source'] == 'network_log'

    def test_save_multiple_interactions(self, test_db):
        """Test saving multiple interactions and retrieving them."""
        # Save 3 interactions
        for i in range(3):
            search_queries = [SimpleNamespace(
                query=f'query {i}',
                sources=[],
                timestamp=datetime.now(),
                order_index=0
            )]

            test_db.save_interaction(
                provider_name='openai',
                model='gpt-5.1',
                prompt=f'Test prompt {i}',
                response_text=f'Test response {i}',
                search_queries=search_queries,
                sources=[],
                citations=[],
                response_time_ms=1000 + i * 100,
                raw_response={'test': i},
                data_source='api',
                extra_links_count=0
            )

        # Retrieve all
        interactions = test_db.get_recent_interactions(limit=10)
        assert len(interactions) == 3

        # Verify order (most recent first)
        assert interactions[0]['prompt'] == 'Test prompt 2'
        assert interactions[1]['prompt'] == 'Test prompt 1'
        assert interactions[2]['prompt'] == 'Test prompt 0'

    def test_delete_interaction(self, test_db):
        """Test deleting an interaction from database."""
        # Save interaction
        search_queries = [SimpleNamespace(
            query='test query',
            sources=[],
            timestamp=datetime.now(),
            order_index=0
        )]

        response_id = test_db.save_interaction(
            provider_name='openai',
            model='gpt-5.1',
            prompt='Test prompt to delete',
            response_text='Test response',
            search_queries=search_queries,
            sources=[],
            citations=[],
            response_time_ms=1000,
            raw_response={'test': 'data'},
            data_source='api',
            extra_links_count=0
        )

        # Verify saved
        interactions = test_db.get_recent_interactions(limit=10)
        assert len(interactions) == 1
        prompt_id = interactions[0]['id']

        # Get response ID from prompt
        session = test_db.get_session()
        from src.database import Prompt
        prompt_obj = session.query(Prompt).filter_by(id=prompt_id).first()
        response_id = prompt_obj.response.id
        session.close()

        # Delete
        result = test_db.delete_interaction(response_id)
        assert result is True

        # Verify deleted
        interactions = test_db.get_recent_interactions(limit=10)
        assert len(interactions) == 0

    def test_get_interaction_details_api_mode(self, test_db):
        """Test retrieving detailed interaction for API mode."""
        # Save interaction
        search_queries = [SimpleNamespace(
            query='detailed test query',
            sources=[SimpleNamespace(
                url='https://example.com/1',
                title='Test Source',
                domain='example.com',
                rank=1,
                pub_date='2024-01-01',
                snippet_text='Test snippet',
                internal_score=None,
                metadata=None
            )],
            timestamp=datetime.now(),
            order_index=0
        )]

        citations = [SimpleNamespace(
            url='https://example.com/1',
            title='Test Source',
            rank=1,
            snippet_used='Test snippet',
            citation_confidence=None,
            metadata={'query_index': 0, 'snippet': 'Test snippet'}
        )]

        test_db.save_interaction(
            provider_name='openai',
            model='gpt-5.1',
            prompt='Detailed test prompt',
            response_text='Detailed test response',
            search_queries=search_queries,
            sources=[],
            citations=citations,
            response_time_ms=1500,
            raw_response={'test': 'detailed'},
            data_source='api',
            extra_links_count=0
        )

        # Get prompt ID
        interactions = test_db.get_recent_interactions(limit=1)
        prompt_id = interactions[0]['id']

        # Get details
        details = test_db.get_interaction_details(prompt_id)

        assert details is not None
        assert details['prompt'] == 'Detailed test prompt'
        assert details['response_text'] == 'Detailed test response'
        assert details['provider'] == 'OpenAI'
        assert details['model'] == 'gpt-5.1'
        assert details['response_time_ms'] == 1500
        assert details['data_source'] == 'api'
        assert len(details['search_queries']) == 1
        assert details['search_queries'][0]['query'] == 'detailed test query'
        assert len(details['search_queries'][0]['sources']) == 1
        assert len(details['citations']) == 1

    def test_get_interaction_details_network_log_mode(self, test_db):
        """Test retrieving detailed interaction for network_log mode."""
        # Save interaction
        search_queries = [SimpleNamespace(
            query='network log query',
            sources=[],  # Empty for network logs
            timestamp=datetime.now(),
            order_index=0
        )]

        all_sources = [
            SimpleNamespace(
                url='https://example.com/1',
                title='Network Source',
                domain='example.com',
                rank=1,
                pub_date='2024-01-01',
                snippet_text='Network snippet',
                internal_score=0.95,
                metadata={'network': 'data'}
            )
        ]

        citations = [SimpleNamespace(
            url='https://example.com/1',
            title='Network Source',
            rank=1,
            snippet_used='Network snippet',
            citation_confidence=0.9,
            metadata={'query_index': 0}
        )]

        test_db.save_interaction(
            provider_name='openai',
            model='chatgpt-free',
            prompt='Network log prompt',
            response_text='Network log response',
            search_queries=search_queries,
            sources=all_sources,
            citations=citations,
            response_time_ms=2500,
            raw_response={'network': 'log'},
            data_source='network_log',
            extra_links_count=0
        )

        # Get prompt ID
        interactions = test_db.get_recent_interactions(limit=1)
        prompt_id = interactions[0]['id']

        # Get details
        details = test_db.get_interaction_details(prompt_id)

        assert details is not None
        assert details['prompt'] == 'Network log prompt'
        assert details['data_source'] == 'network_log'
        assert len(details['all_sources']) == 1  # Network log uses all_sources
        assert details['all_sources'][0]['url'] == 'https://example.com/1'
        assert details['all_sources'][0]['snippet'] == 'Network snippet'


class TestDatabaseMetrics:
    """Test that metrics are correctly stored and retrieved."""

    def test_extra_links_count_stored(self, test_db):
        """Test that extra_links_count is correctly stored and retrieved."""
        search_queries = [SimpleNamespace(
            query='test',
            sources=[],
            timestamp=datetime.now(),
            order_index=0
        )]

        citations = [
            SimpleNamespace(url='https://example.com/1', title='Source 1', rank=1,
                          snippet_used=None, citation_confidence=None, metadata=None),
            SimpleNamespace(url='https://example.com/2', title='Extra', rank=None,
                          snippet_used=None, citation_confidence=None, metadata=None),
            SimpleNamespace(url='https://example.com/3', title='Extra 2', rank=None,
                          snippet_used=None, citation_confidence=None, metadata=None),
        ]

        test_db.save_interaction(
            provider_name='openai',
            model='gpt-5.1',
            prompt='Test extra links',
            response_text='Response',
            search_queries=search_queries,
            sources=[],
            citations=citations,
            response_time_ms=1000,
            raw_response={},
            data_source='api',
            extra_links_count=2  # 2 citations without ranks
        )

        interactions = test_db.get_recent_interactions(limit=1)
        assert interactions[0]['extra_links'] == 2

    def test_avg_rank_calculated(self, test_db):
        """Test that average rank is correctly calculated."""
        search_queries = [SimpleNamespace(
            query='test',
            sources=[],
            timestamp=datetime.now(),
            order_index=0
        )]

        citations = [
            SimpleNamespace(url='https://example.com/1', title='S1', rank=1,
                          snippet_used=None, citation_confidence=None, metadata=None),
            SimpleNamespace(url='https://example.com/2', title='S2', rank=3,
                          snippet_used=None, citation_confidence=None, metadata=None),
            SimpleNamespace(url='https://example.com/3', title='S3', rank=5,
                          snippet_used=None, citation_confidence=None, metadata=None),
        ]

        test_db.save_interaction(
            provider_name='openai',
            model='gpt-5.1',
            prompt='Test avg rank',
            response_text='Response',
            search_queries=search_queries,
            sources=[],
            citations=citations,
            response_time_ms=1000,
            raw_response={},
            data_source='api',
            extra_links_count=0
        )

        interactions = test_db.get_recent_interactions(limit=1)
        # Average of 1, 3, 5 = 3.0
        assert interactions[0]['avg_rank'] == 3.0
