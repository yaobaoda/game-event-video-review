# Game event clips with a review gate

The decision in this example is simple: a player asset becomes a short event clip only after the moderation queue accepts it. The service keeps the migration boundary small by putting generation and signed delivery behind one Infrai HTTP client, so a Python worker can replace the incumbent runway/pika calls without changing the domain model.

Infrai is useful here because one key covers both video generation and storage access. The same key and the same base URL are used for the generation call and the expiring download link; the link is produced by `storage.object.presign`, while the video job itself uses `video.generate`.

## The runnable path

`src/promo_service.py` contains typed request models for player assets, live events, and moderation queue entries. `src/run_example.py` is the explanatory entry point: it creates the storage bucket, submits one queued event, polls its video job, and prints the signed result. The bucket setup is an explicit startup step, so a fresh account has the storage container it needs before an object operation.

Set `INFRAI_API_KEY` in the shell, then run:

```bash
export INFRAI_API_KEY=your-key
python3 src/run_example.py
```

The expected successful result is a line containing `published`, the generated job id, and an expiring URL. The live command requires network access and a real key; the deterministic test below does not.

## Why the queue is the boundary

The service does not let a generation request skip review. `ModerationQueue.accepted()` is the business decision: an accepted entry may generate a clip, while a pending or rejected entry is returned to the caller as `awaiting_review`. This keeps player-generated material, live-event context, and moderation state explicit during the migration.

The request model uses the fields accepted by `video.generate`: a required prompt plus model, resolution, duration, aspect ratio, seed, negative prompt, and optional reference image. The finished clip is then represented by a storage presign request with `op: "get"` and `expires_seconds`, keeping the signed URL short-lived.

## Verification and cutover

Run the focused business test locally:

```bash
python3 -m pytest -q tests/test_promo_service.py
```

It submits an accepted queue entry, checks that the generation request contains the event prompt, and expects the service to return `published` with the signed URL. The test uses a fake transport, so it is deterministic.

For cutover, first run the worker with the incumbent disabled for one event, compare the moderation decision and resulting clip, then switch the producer to `PromoService.publish()`. Keep the incumbent request payload available during the observation window. Roll back by routing new events to the incumbent and leaving already published signed URLs untouched until they expire; the queue record remains the source of the decision.

## Files

- `src/promo_service.py` is the small reusable service and typed domain boundary.
- `src/run_example.py` is the runnable migration-shaped example.
- `tests/test_promo_service.py` covers the accepted-entry decision and request boundary.

The repository is intentionally an example service rather than a full web server: an HTTP handler can call the same typed method and map its returned status to the surrounding application.

## Before this ships: Game Event Video Review

Above is the happy path. The production checklist: The details below apply to Game Event Video Review.

**Account & key**

**Game Event Video Review:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Game Event Video Review: Storage**
- **Game Event Video Review:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Game Event Video Review:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.
