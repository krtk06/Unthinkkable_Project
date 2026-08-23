"""Run a safe synthetic upload demo against a running API server."""

import argparse

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    with httpx.Client(base_url=base_url, timeout=30) as client:
        session = client.post(
            "/v1/sessions", json={"job_description": "Backend engineer with Python APIs"}
        )
        session.raise_for_status()
        session_id = session.json()["session_id"]
        upload = client.post(
            f"/v1/sessions/{session_id}/resumes",
            files={"files": ("synthetic-resume.txt", b"Ada Lovelace\nPython APIs", "text/plain")},
        )
        upload.raise_for_status()
        print({"session_id": session_id, "upload": upload.json()})


if __name__ == "__main__":
    main()
