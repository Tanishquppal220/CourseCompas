"""
Automated tests for Cloudflare-Resilient LangGraph Browser Automation Agent.
Tests:
1. Cloudflare Turnstile challenge detection and interrupt() triggering.
2. Diagnostic message and user instructions generation.
3. Resuming paused execution via Command(resume=...).
4. Form field population and successful submission on Mock LMS portal.
"""

import asyncio
import os
import threading
import time
import pytest
import uvicorn

from app.browser_agent import (
    get_portal_automation_status,
    resume_portal_automation,
    start_portal_automation,
)
from app.main import app

TEST_PORT = 8765
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"


class ServerThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        config = uvicorn.Config(app, host="127.0.0.1", port=TEST_PORT, log_level="warning")
        self.server = uvicorn.Server(config)

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True


@pytest.fixture(scope="session", autouse=True)
def live_server():
    """Starts a live uvicorn server for Playwright to interact with."""
    os.environ["PLAYWRIGHT_HEADLESS"] = "true"  # Run headless for CI/test run
    server_thread = ServerThread()
    server_thread.start()
    time.sleep(1.5)  # Wait for server to bind
    yield
    server_thread.stop()


@pytest.mark.asyncio
async def test_cloudflare_challenge_detection_and_interrupt():
    """Verify that visiting a Cloudflare challenge pauses execution and surfaces diagnostics."""
    thread_id = "test_thread_challenge_001"
    candidate_info = {
        "name": "Alex Mercer",
        "registration_number": "12204567",
        "email": "alex.mercer@lpu.in",
        "course_code": "CSE205",
        "category": "Internship beyond Curriculum",
        "details": "3 months startup internship at 12k/mo",
    }

    # Target URL with Cloudflare challenge
    target_url = f"{BASE_URL}/mock-lms/apply?challenge=turnstile"

    result = await start_portal_automation(
        candidate_info=candidate_info,
        thread_id=thread_id,
        target_url=target_url,
    )

    print("\n--- Test Challenge Result ---")
    print("Status:", result["execution_status"])
    print("Is Paused:", result["is_paused"])
    print("Diagnostic:", result["diagnostic"])

    # Assertions
    assert result["is_paused"] is True
    assert result["execution_status"] == "verification_required"
    diag = result["diagnostic"]
    assert diag.get("blocker_type") in ("cloudflare_challenge", "cloudflare_turnstile_widget")
    assert "Cloudflare" in diag.get("diagnostic_summary", "")
    assert "browser" in diag.get("user_action_prompt", "").lower()

    # Now test resuming the paused thread
    resume_result = await resume_portal_automation(
        thread_id=thread_id,
        resume_payload={"status": "resolved", "message": "User solved challenge"},
    )

    assert resume_result["thread_id"] == thread_id
    assert "User resolved blocker" in " ".join(resume_result["messages"])


@pytest.mark.asyncio
async def test_normal_form_submission_success():
    """Verify standard happy-path form filling and confirmation reference extraction."""
    thread_id = "test_thread_normal_002"
    candidate_info = {
        "name": "Sara Connor",
        "registration_number": "12209999",
        "email": "sara.connor@lpu.in",
        "course_code": "CSE316",
        "category": "Technical Competitions / Hackathons",
        "details": "1st place Smart India Hackathon",
    }

    target_url = f"{BASE_URL}/mock-lms/apply"

    result = await start_portal_automation(
        candidate_info=candidate_info,
        thread_id=thread_id,
        target_url=target_url,
    )

    print("\n--- Test Normal Submission Result ---")
    print("Status:", result["execution_status"])
    print("Messages:", result["messages"])

    assert result["execution_status"] == "complete"
    assert result["is_paused"] is False
    all_msgs = " ".join(result["messages"])
    assert "Application submitted successfully" in all_msgs
    assert "REF-" in all_msgs


@pytest.mark.asyncio
async def test_automation_api_endpoints():
    """Verify that FastAPI automation REST endpoints submit, query status, and resume properly."""
    import httpx

    thread_id = "test_api_thread_003"
    payload = {
        "candidate_info": {
            "name": "David Miller",
            "registration_number": "12201122",
            "email": "david.miller@lpu.in",
            "course_code": "CSE202",
            "category": "10% Attendance Benefit",
            "details": "GATE Exam pre-final year preparation",
        },
        "target_url": f"{BASE_URL}/mock-lms/apply?challenge=turnstile",
        "thread_id": thread_id,
    }

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # 1. Start automation via API
        resp = await client.post("/api/automation/submit", json=payload, timeout=30.0)
        assert resp.status_code == 200
        data = resp.json()
        assert data["thread_id"] == thread_id
        assert data["is_paused"] is True
        assert data["diagnostic"]["blocker_type"] == "cloudflare_challenge"

        # 2. Check status via API
        status_resp = await client.get(f"/api/automation/status/{thread_id}")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["is_paused"] is True

        # 3. Resume via API
        resume_payload = {
            "thread_id": thread_id,
            "status": "resolved",
            "message": "User checked the Turnstile box in browser",
        }
        resume_resp = await client.post("/api/automation/resume", json=resume_payload, timeout=30.0)
        assert resume_resp.status_code == 200
        resume_data = resume_resp.json()
        assert "User resolved blocker" in " ".join(resume_data["messages"])

