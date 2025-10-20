import pytest
import requests
import os
from dotenv import load_dotenv 
from app.config.settings import settings 
from requests import Response

load_dotenv()

app_name = os.getenv("APP_NAME", "app")
app_port = os.getenv("APP_PORT", 8010)
@pytest.mark.integration
def test_health_endpoint_returns_200():
    response: Response = requests.get(f"http://{app_name}:{app_port}")

    assert response.status_code == 200
