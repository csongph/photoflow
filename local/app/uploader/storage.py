from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from typing import Protocol

import httpx


DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink,webContentLink"
DRIVE_PERMISSIONS_URL = "https://www.googleapis.com/drive/v3/files/{file_id}/permissions"


class StorageProvider(Protocol):
    name: str

    def upload_file(self, local_path: Path, remote_key: str, mime_type: str) -> dict:
        ...


class GoogleDriveProvider:
    name = "google_drive"

    def __init__(self, client_id: str, client_secret: str, refresh_token: str | None = None, root_folder_name: str = "MomentLink Events"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.root_folder_name = root_folder_name

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)

    def access_token(self) -> str:
        if not self.client_id or not self.client_secret:
            raise RuntimeError("Google Drive OAuth credentials are not configured")
        if not self.refresh_token:
            raise RuntimeError("Google Drive is not connected")
        with httpx.Client(timeout=30) as client:
            response = client.post(
                TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
            )
        if response.status_code >= 400:
            raise RuntimeError(f"Google token refresh failed: {response.text[:500]}")
        return response.json()["access_token"]

    def ensure_folder(self, access_token: str, name: str, parent_id: str | None = None) -> str:
        safe_name = name.replace("'", "").strip()[:120] or "MomentLink"
        query = f"name = '{safe_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        headers = {"Authorization": f"Bearer {access_token}"}
        with httpx.Client(timeout=30) as client:
            search = client.get(DRIVE_FILES_URL, headers=headers, params={"q": query, "fields": "files(id,name)", "spaces": "drive"})
            if search.status_code >= 400:
                raise RuntimeError(f"Google Drive folder search failed: {search.text[:500]}")
            files = search.json().get("files", [])
            if files:
                return files[0]["id"]
            metadata = {"name": safe_name, "mimeType": "application/vnd.google-apps.folder"}
            if parent_id:
                metadata["parents"] = [parent_id]
            created = client.post(DRIVE_FILES_URL, headers={**headers, "Content-Type": "application/json"}, json=metadata, params={"fields": "id"})
            if created.status_code >= 400:
                raise RuntimeError(f"Google Drive folder create failed: {created.text[:500]}")
            return created.json()["id"]

    def upload_file(self, local_path: Path, remote_key: str, mime_type: str) -> dict:
        access_token = self.access_token()
        parts = [part for part in remote_key.replace("\\", "/").split("/") if part]
        folder_parts, filename = parts[:-1], parts[-1] if parts else local_path.name
        parent_id = self.ensure_folder(access_token, self.root_folder_name)
        for folder_name in folder_parts:
            parent_id = self.ensure_folder(access_token, folder_name, parent_id)

        mime_type = mime_type or mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
        metadata = {"name": filename, "parents": [parent_id], "mimeType": mime_type}
        boundary = "photoflow_upload_boundary"
        body = (
            f"--{boundary}\r\n"
            "Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{json.dumps(metadata)}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode("utf-8") + local_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
        }
        with httpx.Client(timeout=120) as client:
            response = client.post(DRIVE_UPLOAD_URL, headers=headers, content=body)
            if response.status_code >= 400:
                raise RuntimeError(f"Google Drive upload failed: {response.text[:500]}")
            data = response.json()
            permission = client.post(
                DRIVE_PERMISSIONS_URL.format(file_id=data["id"]),
                headers={**headers, "Content-Type": "application/json"},
                json={"role": "reader", "type": "anyone"},
            )
            if permission.status_code >= 400:
                raise RuntimeError(f"Google Drive sharing failed: {permission.text[:500]}")
        file_id = data["id"]
        return {
            "id": file_id,
            "web_view_link": data.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view",
            "download_link": data.get("webContentLink") or f"https://drive.google.com/uc?export=download&id={file_id}",
        }


def env_provider(refresh_token: str | None, root_folder_name: str = "MomentLink Events") -> GoogleDriveProvider:
    return GoogleDriveProvider(
        client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        refresh_token=refresh_token,
        root_folder_name=root_folder_name,
    )
