import pytest
from unittest.mock import AsyncMock, MagicMock
from pricetracker.agent.agent import LLMAgent
from pricetracker.core.llm import LLMClient
from pricetracker.core.interfaces import SearchResult

@pytest.fixture
def mock_llm_client():
    client = MagicMock(spec=LLMClient)
    client.chat_completion = AsyncMock()
    return client

@pytest.fixture
def agent(mock_llm_client):
    return LLMAgent(mock_llm_client)

@pytest.mark.asyncio
async def test_agent_search_parsing(agent, mock_llm_client):
    # Mock LLM response
    mock_response = """
    {
        "reasoning": "Found it",
        "action": "EXTRACT_RESULTS",
        "results": [
            {
                "title": "Test Product",
                "url": "http://example.com/p1",
                "price": 10.5
            }
        ]
    }
    """
    mock_llm_client.chat_completion.return_value = mock_response
    
    mock_page = MagicMock()
    mock_page.url = "http://example.com"
    mock_page.evaluate = AsyncMock(return_value="<html><body>Page Content</body></html>")
    mock_page.title = AsyncMock(return_value="Test Page")
    
    results = await agent.search(mock_page, "query")
    
    assert len(results) == 1
    assert results[0].title == "Test Product"
    assert results[0].price == 10.5

@pytest.mark.asyncio
async def test_agent_extract_parsing(agent, mock_llm_client):
    mock_response = """
    {
        "price": 20.0,
        "currency": "USD",
        "title": "My Product",
        "availability": "in_stock"
    }
    """
    mock_llm_client.chat_completion.return_value = mock_response
    
    mock_page = MagicMock()
    mock_page.url = "http://example.com/p1"
    mock_page.evaluate = AsyncMock(return_value="<html><body>Page Content</body></html>")
    mock_page.title = AsyncMock(return_value="Test Page")
    
    obs = await agent.extract(mock_page)
    
    assert obs.price == 20.0
    assert obs.title == "My Product"
    assert obs.availability == "in_stock"
