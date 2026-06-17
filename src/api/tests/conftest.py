"""Pytest configuration — ensure `app` package is importable and env vars are set."""
import os
import sys
from pathlib import Path

# Add src/api to path so `app` is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Provide minimal env vars so Settings() doesn't fail during import
os.environ.setdefault("SQL_SERVER_FQDN", "test.database.windows.net")
os.environ.setdefault("SQL_DATABASE_NAME", "testdb")
os.environ.setdefault("AZURE_TENANT_ID", "00000000-0000-0000-0000-000000000000")
os.environ.setdefault("FOUNDRY_PROJECT_ENDPOINT", "https://test.services.ai.azure.com/api/projects/test")
