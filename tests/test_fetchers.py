from unittest.mock import patch, MagicMock
from src.fetchers.vscode import fetch_vscode
from src.fetchers.docker import fetch_docker

def test_vscode_returns_empty_on_api_error():
    with patch("src.fetchers.vscode.requests.post") as mock:
        mock.return_value.status_code = 500
        result = fetch_vscode("python")
    assert result == []

def test_vscode_parses_response():
    mock_response = {
        "results": [{
            "extensions": [{
                "extensionName": "python",
                "publisher": {"publisherName": "ms-python"},
                "displayName": "Python",
                "shortDescription": "Python support",
                "statistics": [
                    {"statisticName": "install", "value": 100000000},
                    {"statisticName": "averagerating", "value": 4.5},
                ],
                "lastUpdated": "2026-01-01T00:00:00Z",
                "flags": "validated",
            }]
        }]
    }
    with patch("src.fetchers.vscode.requests.post") as mock:
        mock.return_value.status_code = 200
        mock.return_value.json.return_value = mock_response
        result = fetch_vscode("python")
    assert len(result) == 1
    assert result[0].name == "ms-python.python"
    assert result[0].source == "vscode"

def test_docker_returns_empty_on_api_error():
    with patch("src.fetchers.docker.requests.get") as mock:
        mock.return_value.status_code = 500
        result = fetch_docker("python")
    assert result == []

def test_docker_parses_official_image():
    mock_response = {
        "results": [{
            "repo_name": "python",
            "short_description": "Python official image",
            "star_count": 10000,
            "pull_count": 1000000000,
            "is_official": True,
            "last_updated": "2026-01-01T00:00:00Z",
        }]
    }
    with patch("src.fetchers.docker.requests.get") as mock:
        mock.return_value.status_code = 200
        mock.return_value.json.return_value = mock_response
        result = fetch_docker("python")
    assert len(result) == 1
    assert result[0].name == "python"
    assert result[0].maintainer_verified_org is True
