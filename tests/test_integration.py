import pytest
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock
from pricetracker.core.runner import JobRunner
from pricetracker.db.models import Observation, Base
from pricetracker.core.config import AppConfig

@pytest.mark.asyncio
async def test_job_runner_integration():
    cwd = os.getcwd()
    
    # Create temp config with absolute path
    with open("tests/config_test.yaml", "r") as f:
        content = f.read().format(cwd=cwd)
    
    with open("tests/config_test_run.yaml", "w") as f:
        f.write(content)

    runner = JobRunner(config_path="tests/config_test_run.yaml")
    
    # Create tables in in-memory DB
    engine = runner.session_factory.kw['bind']
    Base.metadata.create_all(engine)
    
    # Mock LLM Client
    mock_llm = MagicMock()
    
    # Sequence of responses:
    # 1. Search: "Yes I found it on this page"
    # 2. Extract: "Here is the price"
    
    search_response = """
    {
        "reasoning": "Found direct match",
        "action": "NAVIGATE",
        "target": "file://__CWD__/tests/mock_site/product.html",
        "results": [
            {
                "title": "Mock Milk 2L",
                "url": "file://__CWD__/tests/mock_site/product.html",
                "price": 2.50
            }
        ]
    }
    """.replace("__CWD__", cwd)

    extract_response = """
    {
        "price": 2.50,
        "currency": "BRL",
        "title": "Mock Milk 2L",
        "availability": "in_stock"
    }
    """
    
    mock_llm.chat_completion = AsyncMock(side_effect=[search_response, extract_response])
    runner.llm_client = mock_llm
    
    # Run
    await runner.run()
    
    # Verify DB
    with runner.session_factory() as session:
        observations = session.query(Observation).all()
        assert len(observations) > 0
        obs = observations[0]
        assert obs.price == 2.50
        assert obs.title == "Mock Milk 2L"
        assert obs.site.name == "MockSite"

    # Cleanup
    if os.path.exists("tests/config_test_run.yaml"):
        os.remove("tests/config_test_run.yaml")
