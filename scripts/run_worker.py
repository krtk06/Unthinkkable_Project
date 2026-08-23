"""Run the Atlas-backed processing worker."""

import argparse
import time
from uuid import uuid4

from app.api.dependencies import get_queue, get_worker
from app.workers.tasks import run_once


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()
    queue = get_queue()
    worker = get_worker()
    worker_id = uuid4().hex
    while True:
        if not run_once(queue, worker, worker_id):
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
