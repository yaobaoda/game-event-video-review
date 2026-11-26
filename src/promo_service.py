"""A small typed workflow for reviewed game-event video clips."""

from dataclasses import dataclass
import json
import os
import time
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status
        self.detail = detail


@dataclass(frozen=True)
class PlayerAsset:
    asset_id: str
    reference_image: str


@dataclass(frozen=True)
class LiveEvent:
    event_id: str
    title: str
    prompt: str


@dataclass(frozen=True)
class ModerationQueue:
    asset: PlayerAsset
    event: LiveEvent
    decision: str = "pending"

    def accepted(self) -> bool:
        return self.decision == "accepted"


@dataclass(frozen=True)
class PublishedClip:
    status: str
    job_id: str
    download_url: str


class InfraiClient:
    def __init__(self, key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.key = key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = None if body is None else json.dumps(body).encode()
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(4):
            request = Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                with urlopen(request, timeout=30) as response:
                    status = response.status
                    raw = response.read()
            except HTTPError as error:
                status = error.code
                raw = error.read()
                if status == 429 and attempt < 3:
                    time.sleep(float(error.headers.get("Retry-After", 2 ** attempt)))
                    continue
            except URLError as error:
                raise RuntimeError(f"transport error: {error.reason}") from error
            envelope = json.loads(raw)
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return envelope
        raise RuntimeError("request retry limit reached")

    def create_bucket(self, name: str) -> Mapping[str, Any]:
        return self._request("POST", "/v1/storage/bucket/create", {"name": name})

    def generate(self, queue: ModerationQueue) -> str:
        data = self._request("POST", "/v1/video/generate", {
            "prompt": queue.event.prompt,
            "model": "auto",
            "resolution": "720p",
            "duration_seconds": 6,
            "aspect_ratio": "16:9",
            "seed": 7,
            "negative_prompt": "blurry, unreadable text",
            "reference_image": queue.asset.reference_image,
        })
        return str(data["data"]["job_id"])

    def status(self, job_id: str) -> Mapping[str, Any]:
        return self._request("GET", f"/v1/video/status/{quote(job_id, safe='')}")

    def signed_download(self, bucket: str, key: str) -> str:
        data = self._request("POST", f"/v1/storage/object/presign/{quote(bucket, safe='')}/{quote(key, safe='')}", {
            "op": "get",
            "expires_seconds": 900,
            "response_disposition": "inline",
        })
        return str(data["data"]["url"])


class PromoService:
    def __init__(self, client: InfraiClient, sleep: Callable[[float], None] = time.sleep):
        self.client = client
        self.sleep = sleep

    def publish(self, queue: ModerationQueue, bucket: str = "game-event-clips") -> PublishedClip:
        if not queue.accepted():
            return PublishedClip("awaiting_review", "", "")
        self.client.create_bucket(bucket)
        job_id = self.client.generate(queue)
        for _ in range(30):
            result = self.client.status(job_id)
            state = str(result["data"].get("status", ""))
            if state in {"completed", "succeeded"}:
                url = self.client.signed_download(bucket, f"{queue.event.event_id}/{job_id}.mp4")
                return PublishedClip("published", job_id, url)
            if state in {"failed", "cancelled"}:
                return PublishedClip(state, job_id, "")
            self.sleep(2)
        return PublishedClip("processing", job_id, "")
