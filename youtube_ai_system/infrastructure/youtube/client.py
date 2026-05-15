"""YouTube Data API client adapter."""

from __future__ import annotations

from pathlib import Path


class YouTubeClient:
    def __init__(self, *, token_path: Path, client_secret_path: Path) -> None:
        self.token_path = token_path
        self.client_secret_path = client_secret_path

    def authorized_client(self, scopes: list[str]):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        credentials = None
        if self.token_path.exists():
            credentials = Credentials.from_authorized_user_file(str(self.token_path), scopes)
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self._write_token(credentials)
        if not credentials or not credentials.valid:
            flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret_path), scopes)
            credentials = flow.run_local_server(
                port=0,
                access_type="offline",
                include_granted_scopes="true",
                prompt="consent",
            )
            self._write_token(credentials)
        return build("youtube", "v3", credentials=credentials, cache_discovery=False)

    def _write_token(self, credentials) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(credentials.to_json(), encoding="utf-8")

