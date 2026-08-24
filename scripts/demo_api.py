"""Run a safe synthetic upload demo against a running API server."""

import argparse
import time

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    with httpx.Client(base_url=base_url, timeout=30) as client:
        login = client.post(
            "/v1/auth/login",
            json={"username": args.username, "password": args.password},
        )
        login.raise_for_status()
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

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
        for _ in range(30):
            status = client.get(f"/v1/sessions/{session_id}/status")
            status.raise_for_status()
            counts = status.json().get("counts", {})
            if counts.get("scored", 0) or counts.get("score_failed", 0):
                break
            time.sleep(1)
        matches = client.get(f"/v1/sessions/{session_id}/matches?limit=25")
        matches.raise_for_status()
        print({"status": status.json(), "matches": matches.json()})


if __name__ == "__main__":
    main()
