import logging

from app.tasks.deadline_tasks import scan_deadlines


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logging.getLogger(__name__).info(
        "Starting scheduled deadline reminder scan"
    )

    scan_deadlines(direct_send=True)

    logging.getLogger(__name__).info(
        "Finished scheduled deadline reminder scan"
    )


if __name__ == "__main__":
    main()