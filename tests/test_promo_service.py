import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from promo_service import LiveEvent, ModerationQueue, PlayerAsset, PromoService


class FakeClient:
    def __init__(self):
        self.calls = []

    def create_bucket(self, name):
        self.calls.append(("bucket", name))

    def generate(self, queue):
        self.calls.append(("generate", queue.event.prompt))
        return "job-1"

    def status(self, job_id):
        self.calls.append(("status", job_id))
        return {"data": {"status": "completed"}}

    def signed_download(self, bucket, key):
        self.calls.append(("presign", bucket, key))
        return "https://signed.example/clip"


def test_accepted_queue_publishes_event_clip():
    queue = ModerationQueue(
        PlayerAsset("asset-1", "reference"),
        LiveEvent("event-1", "Arena", "Make a six-second arena trailer"),
        "accepted",
    )
    client = FakeClient()
    result = PromoService(client, sleep=lambda _: None).publish(queue, "clips")

    assert result.status == "published"
    assert result.download_url == "https://signed.example/clip"
    assert ("generate", "Make a six-second arena trailer") in client.calls
    assert client.calls[-1][0] == "presign"
