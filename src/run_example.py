"""Run one accepted live-event clip through the review boundary."""

from promo_service import InfraiClient, LiveEvent, ModerationQueue, PlayerAsset, PromoService


def main() -> None:
    queue = ModerationQueue(
        asset=PlayerAsset("asset-42", "player-upload-reference"),
        event=LiveEvent("summer-arena", "Summer Arena", "A bright six-second trailer for the Summer Arena player showcase"),
        decision="accepted",
    )
    result = PromoService(InfraiClient()).publish(queue)
    print(result.status, result.job_id, result.download_url)


if __name__ == "__main__":
    main()
