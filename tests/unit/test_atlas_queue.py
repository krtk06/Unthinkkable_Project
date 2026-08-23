from datetime import UTC, datetime, timedelta

import mongomock

from app.workers.queue import AtlasTaskQueue


def make_queue() -> AtlasTaskQueue:
    return AtlasTaskQueue(mongomock.MongoClient()["queue_test"])


def test_queue_persists_job_and_claims_it_atomically() -> None:
    queue = make_queue()

    job_id = queue.enqueue("process_candidate", {"candidate_id": "candidate-1"})
    job = queue.claim("worker-1")

    assert job is not None
    assert job["_id"] == job_id
    assert job["status"] == "processing"
    assert job["attempts"] == 1
    assert queue.pending_count() == 0


def test_queue_retries_then_dead_letters_failed_job() -> None:
    queue = AtlasTaskQueue(make_queue().database, max_attempts=2)
    queue.enqueue("process_candidate", {"candidate_id": "candidate-1"})

    first = queue.claim("worker-1")
    assert first is not None
    queue.fail(first["_id"], "provider timeout")
    second = queue.claim("worker-1")
    assert second is not None
    queue.fail(second["_id"], "provider timeout")

    stored = queue.jobs.find_one({"_id": second["_id"]})
    assert stored is not None
    assert stored["status"] == "dead_letter"
    assert stored["error"] == "provider timeout"


def test_queue_reclaims_expired_lease() -> None:
    queue = make_queue()
    queue.enqueue("process_candidate", {"candidate_id": "candidate-1"})
    claimed = queue.claim("worker-1")
    assert claimed is not None
    queue.jobs.update_one(
        {"_id": claimed["_id"]},
        {"$set": {"lease_until": datetime.now(UTC) - timedelta(minutes=1)}},
    )

    reclaimed = queue.claim("worker-2")

    assert reclaimed is not None
    assert reclaimed["_id"] == claimed["_id"]
    assert reclaimed["worker_id"] == "worker-2"
