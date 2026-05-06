import json
from pathlib import Path

import pytest


@pytest.fixture
def fixture_payload() -> dict:
    return json.loads(Path("fixtures/sanitized_viewerapi_view50.json").read_text())
