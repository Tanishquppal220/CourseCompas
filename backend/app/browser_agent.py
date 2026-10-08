"""
Cloudflare-Resilient Browser Automation Agent with LangGraph & Playwright.

Orchestrates automated form filling, portal navigation, anti-bot avoidance,
DOM rendering diagnosis, and Human-in-the-Loop (HITL) interrupt handling.
"""

import asyncio
import base64
import logging
import operator
import os
import re
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt
from playwright.async_api import BrowserContext, Page, async_playwright

logger = logging.getLogger(__name__)

# Directory where persistent browser user data/profiles and cookies are preserved
PROFILES_DIR = Path(os.getenv("BROWSER_PROFILES_DIR", Path.cwd() / "profiles" / "portal_session"))
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
STATE_JSON_PATH = PROFILES_DIR / "state.json"


# ==============================================================================
# 1. State Schema
# ==============================================================================


class LMSAutomationState(TypedDict):
    """Global state schema for the browser automation graph."""

    # Chronological history of steps and observations
    messages: Annotated[list[str], operator.add]
    # Form data to populate
    candidate_info: dict[str, Any]
    # Target portal URL (e.g. UMS portal or mock LMS URL)
    target_url: str
    # Current URL in the browser
    active_url: str
    # Execution lifecycle status
    execution_status: Literal[
        "initialized",
        "navigating",
        "verification_required",
        "filling",
        "authorized",
        "submitting",
        "complete",
        "cancelled",
        "error",
    ]
    # Blockers and diagnostics
    challenge_detected: bool
    blocker_type: str | None
    diagnostic_summary: str | None
    user_action_prompt: str | None
    screenshot_b64: str | None
    # Retry counters
    step_retries: int


# ==============================================================================
# 2. Stealth Browser Context Launcher
# ==============================================================================


def get_browser_executable_path() -> str | None:
    """Finds available system Chrome / Chromium if Playwright default is not ready."""
    common_paths = [
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p
    return None


async def launch_stealth_context(p: Any, user_dir: Path, headless: bool = False) -> BrowserContext:
    """
    Launches a persistent browser context configured with stealth arguments
    to evade Cloudflare detection while retaining sessions and cookies.
    """
    args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--window-size=1280,800",
    ]

    executable_path = None
    # If not on standard downloaded playwright build, fallback to system chrome
    system_chrome = get_browser_executable_path()
    if system_chrome:
        executable_path = system_chrome

    # Check for saved storage state for temporary session cookies
    storage_state = str(STATE_JSON_PATH) if STATE_JSON_PATH.exists() else None

    try:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(user_dir),
            headless=headless,
            args=args,
            executable_path=executable_path,
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="Asia/Kolkata",
        )
        return context
    except Exception as e:
        logger.warning(f"Failed launch with custom executable, falling back to default: {e}")
        return await p.chromium.launch_persistent_context(
            user_data_dir=str(user_dir),
            headless=headless,
            args=args,
            viewport={"width": 1280, "height": 800},
        )


async def capture_screenshot_b64(page: Page) -> str | None:
    """Safely captures a JPEG screenshot encoded as base64."""
    try:
        img_bytes = await page.screenshot(type="jpeg", quality=65)
        return base64.b64encode(img_bytes).decode("utf-8")
    except Exception as e:
        logger.warning(f"Screenshot capture failed: {e}")
        return None


# ==============================================================================
# 3. Blocker & Rendering Diagnostic Logic
# ==============================================================================


async def diagnose_page_blockers(
    page: Page,
) -> tuple[bool, str | None, str | None, str | None]:
    """
    Evaluates page title, DOM elements, iframes, and network state to detect:
    - Cloudflare Turnstile / anti-bot challenges
    - Unfinished DOM rendering / loading spinners
    - Obscuring modal dialogs
    - Form validation errors
    """
    try:
        title = await page.title()
    except Exception:
        title = ""

    # 1. Cloudflare Turnstile / Challenge Detection in Title
    if any(marker in title for marker in ["Just a moment...", "Cloudflare", "Attention Required!"]):
        return (
            True,
            "cloudflare_challenge",
            f"Cloudflare anti-bot security challenge detected on page (Title: '{title}').",
            "A Cloudflare verification screen is active in the browser window. Please complete the verification in the opened browser, then click 'Resume'.",
        )

    # 2. Check for Cloudflare Turnstile iframes or widget wrappers in DOM
    try:
        turnstile_count = await page.locator(
            "iframe[src*='cloudflare'], div#turnstile-wrapper, div.cf-turnstile, iframe[src*='challenges.cloudflare.com']"
        ).count()
        if turnstile_count > 0:
            return (
                True,
                "cloudflare_turnstile_widget",
                "Cloudflare Turnstile verification widget detected in the page.",
                "Please click the 'Verify you are human' checkbox inside the browser window, then click 'Resume'.",
            )
    except Exception:
        pass

    # 3. Check for 403/503 access denial
    if any(code in title for code in ["403 Forbidden", "503 Service Unavailable"]):
        return (
            True,
            "access_denied",
            f"Access denied by remote gateway (HTTP status in title: '{title}').",
            "The portal returned an access denial. Please verify your VPN or login session in the browser window, then click 'Resume'.",
        )

    # 4. Check for active loading spinners or dynamic rendering locks
    try:
        spinner_locator = page.locator(
            ".spinner, .loading, [aria-busy='true'], .ant-spin, .lds-ring, #loading-spinner"
        )
        if await spinner_locator.count() > 0:
            if await spinner_locator.first.is_visible():
                return (
                    True,
                    "rendering_delay",
                    "Page is still dynamically loading data or components.",
                    "The portal page is still rendering. If it stays stuck, please interact with the browser window to dismiss or refresh, then click 'Resume'.",
                )
    except Exception:
        pass

    return (False, None, None, None)


# ==============================================================================
# 4. Graph Nodes
# ==============================================================================


async def planning_node(state: LMSAutomationState) -> dict[str, Any]:
    """Node 1: Validates incoming submission payload and configuration."""
    candidate = state.get("candidate_info", {})
    target_url = state.get("target_url") or "http://localhost:8000/mock-lms/apply"

    # Verify minimum required fields
    if not candidate.get("name") and not candidate.get("registration_number"):
        return {
            "messages": ["Validation failed: Missing student name or registration number."],
            "execution_status": "error",
            "target_url": target_url,
        }

    return {
        "messages": [
            f"Validated submission payload for candidate: {candidate.get('name', 'Student')} (Reg: {candidate.get('registration_number', 'N/A')})"
        ],
        "execution_status": "initialized",
        "target_url": target_url,
    }


async def navigation_node(state: LMSAutomationState) -> dict[str, Any]:
    """Node 2: Launches persistent stealth browser and navigates to target portal."""
    target_url = state["target_url"]
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"

    async with async_playwright() as p:
        context = await launch_stealth_context(p, PROFILES_DIR, headless=headless)
        page = await context.new_page()
        try:
            logger.info(f"Navigating to target portal: {target_url}")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=25000)
            await page.wait_for_timeout(1000)

            # Diagnose security challenges or rendering issues
            is_blocked, blocker, diag_summary, user_prompt = await diagnose_page_blockers(page)
            active_url = page.url
            screenshot = await capture_screenshot_b64(page) if is_blocked else None

            # Save state storage cookies
            try:
                await context.storage_state(path=str(STATE_JSON_PATH))
            except Exception:
                pass

            await context.close()

            if is_blocked:
                return {
                    "messages": [f"Blocker detected during navigation: {diag_summary}"],
                    "active_url": active_url,
                    "challenge_detected": True,
                    "blocker_type": blocker,
                    "diagnostic_summary": diag_summary,
                    "user_action_prompt": user_prompt,
                    "screenshot_b64": screenshot,
                    "execution_status": "verification_required",
                }

            return {
                "messages": [f"Successfully navigated to portal at {active_url}"],
                "active_url": active_url,
                "challenge_detected": False,
                "blocker_type": None,
                "diagnostic_summary": None,
                "user_action_prompt": None,
                "execution_status": "filling",
            }

        except Exception as e:
            logger.error(f"Navigation error: {e}")
            try:
                await context.close()
            except Exception:
                pass
            return {
                "messages": [f"Navigation failed: {e!s}"],
                "active_url": target_url,
                "challenge_detected": True,
                "blocker_type": "navigation_timeout",
                "diagnostic_summary": f"Could not load portal URL: {e!s}",
                "user_action_prompt": "Please ensure the portal is accessible and that your network connection is active, then click 'Resume'.",
                "execution_status": "verification_required",
            }


async def form_filling_node(state: LMSAutomationState) -> dict[str, Any]:
    """Node 3: Enters student & achievement details into the portal form."""
    candidate = state.get("candidate_info", {})
    active_url = state.get("active_url") or state.get("target_url")
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"

    async with async_playwright() as p:
        context = await launch_stealth_context(p, PROFILES_DIR, headless=headless)
        page = await context.new_page()

        try:
            await page.goto(active_url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(1000)

            # Re-check for blockers before interacting
            is_blocked, blocker, diag_summary, user_prompt = await diagnose_page_blockers(page)
            if is_blocked:
                screenshot = await capture_screenshot_b64(page)
                await context.close()
                return {
                    "messages": [f"Rendering blocker appeared: {diag_summary}"],
                    "challenge_detected": True,
                    "blocker_type": blocker,
                    "diagnostic_summary": diag_summary,
                    "user_action_prompt": user_prompt,
                    "screenshot_b64": screenshot,
                    "execution_status": "verification_required",
                }

            # Flexible heuristic form filling
            filled_fields = []

            # 1. Full Name
            name_val = candidate.get("name") or candidate.get("student_name")
            if name_val:
                try:
                    name_input = page.get_by_role("textbox", name=re.compile(r"name|student", re.I))
                    if await name_input.count() > 0:
                        await name_input.first.fill(name_val)
                        filled_fields.append("Name")
                    else:
                        # Fallback CSS selector
                        fallback = page.locator("input[name*='name'], input#name, input#student_name")
                        if await fallback.count() > 0:
                            await fallback.first.fill(name_val)
                            filled_fields.append("Name")
                except Exception as e:
                    logger.debug(f"Name fill fallback: {e}")

            # 2. Registration Number
            reg_val = candidate.get("registration_number") or candidate.get("reg_no")
            if reg_val:
                try:
                    reg_input = page.get_by_role("textbox", name=re.compile(r"reg|id|roll", re.I))
                    if await reg_input.count() > 0:
                        await reg_input.first.fill(str(reg_val))
                        filled_fields.append("Registration Number")
                    else:
                        fallback = page.locator("input[name*='reg'], input#registration_number, input#reg_no")
                        if await fallback.count() > 0:
                            await fallback.first.fill(str(reg_val))
                            filled_fields.append("Registration Number")
                except Exception as e:
                    logger.debug(f"Reg no fill fallback: {e}")

            # 3. Email
            email_val = candidate.get("email")
            if email_val:
                try:
                    email_input = page.get_by_role("textbox", name=re.compile(r"email", re.I))
                    if await email_input.count() > 0:
                        await email_input.first.fill(email_val)
                        filled_fields.append("Email")
                    else:
                        fallback = page.locator("input[type='email'], input[name*='email']")
                        if await fallback.count() > 0:
                            await fallback.first.fill(email_val)
                            filled_fields.append("Email")
                except Exception as e:
                    logger.debug(f"Email fill fallback: {e}")

            # 4. Target Course Code
            course_val = candidate.get("course_code") or candidate.get("mapped_course")
            if course_val:
                try:
                    course_input = page.get_by_role("textbox", name=re.compile(r"course|subject", re.I))
                    if await course_input.count() > 0:
                        await course_input.first.fill(course_val)
                        filled_fields.append("Course Code")
                    else:
                        fallback = page.locator("input[name*='course'], input#course_code")
                        if await fallback.count() > 0:
                            await fallback.first.fill(course_val)
                            filled_fields.append("Course Code")
                except Exception as e:
                    logger.debug(f"Course fill fallback: {e}")

            # 5. Benefit Category
            cat_val = candidate.get("category") or candidate.get("benefit_type")
            if cat_val:
                try:
                    cat_select = page.locator("select[name*='category'], select#category")
                    if await cat_select.count() > 0:
                        await cat_select.first.select_option(label=cat_val)
                        filled_fields.append("Category")
                except Exception:
                    pass

            # 6. Description / Proof Details
            desc_val = candidate.get("details") or candidate.get("achievement_summary")
            if desc_val:
                try:
                    desc_input = page.locator("textarea, textarea[name*='detail'], textarea#details")
                    if await desc_input.count() > 0:
                        await desc_input.first.fill(desc_val)
                        filled_fields.append("Achievement Details")
                except Exception:
                    pass

            # Check if any fields were filled or if form element was missing
            if not filled_fields:
                screenshot = await capture_screenshot_b64(page)
                await context.close()
                return {
                    "messages": ["Form elements were not interactable or could not be detected."],
                    "challenge_detected": True,
                    "blocker_type": "element_missing",
                    "diagnostic_summary": "The form fields could not be found or are not yet rendered in the DOM.",
                    "user_action_prompt": "Please navigate to the exact form tab or section in the browser window, then click 'Resume'.",
                    "screenshot_b64": screenshot,
                    "execution_status": "verification_required",
                }

            # Submit the filled form directly on the active page
            submit_btn = page.get_by_role("button", name=re.compile(r"submit|apply|save", re.I))
            if await submit_btn.count() == 0:
                submit_btn = page.locator("button[type='submit'], input[type='submit'], .btn-submit")

            if await submit_btn.count() == 0:
                screenshot = await capture_screenshot_b64(page)
                await context.close()
                return {
                    "messages": [
                        f"Successfully filled form fields: {', '.join(filled_fields)}",
                        "Submit button could not be located on the form page.",
                    ],
                    "challenge_detected": True,
                    "blocker_type": "submit_button_missing",
                    "diagnostic_summary": "Form was filled, but the submit button was not found in the DOM.",
                    "user_action_prompt": "Please click the Submit button manually in the browser window, then click 'Resume'.",
                    "screenshot_b64": screenshot,
                    "execution_status": "verification_required",
                }

            # Click the submit button
            await submit_btn.first.click()
            await page.wait_for_timeout(2500)

            # Check for validation error alerts on page
            error_locator = page.locator(".alert-danger, .error-message, [role='alert'], .field-validation-error")
            if await error_locator.count() > 0 and await error_locator.first.is_visible():
                err_text = await error_locator.first.inner_text()
                screenshot = await capture_screenshot_b64(page)
                await context.close()
                return {
                    "messages": [f"Portal rejected submission with validation error: {err_text}"],
                    "challenge_detected": True,
                    "blocker_type": "form_validation_error",
                    "diagnostic_summary": f"Form validation error: {err_text}",
                    "user_action_prompt": f"Please correct the field error in the browser: '{err_text}', then click 'Resume'.",
                    "screenshot_b64": screenshot,
                    "execution_status": "verification_required",
                }

            # Extract confirmation reference and message if available
            ref_locator = page.locator("#reference-number, .confirmation-code")
            ref_text = ""
            if await ref_locator.count() > 0 and await ref_locator.first.is_visible():
                ref_text = await ref_locator.first.inner_text()

            confirm_locator = page.locator(".alert-success, .success-message")
            confirm_msg = ""
            if await confirm_locator.count() > 0 and await confirm_locator.first.is_visible():
                confirm_msg = await confirm_locator.first.inner_text()

            await context.close()
            msg = "Application submitted successfully to the portal!"
            if ref_text:
                msg += f" Reference ID: {ref_text.strip()}."
            if confirm_msg:
                msg += f" Confirmation details: {confirm_msg.strip()}"

            return {
                "messages": [
                    f"Successfully filled form fields: {', '.join(filled_fields)}",
                    msg,
                ],
                "execution_status": "complete",
                "challenge_detected": False,
                "blocker_type": None,
                "diagnostic_summary": None,
                "user_action_prompt": None,
            }

        except Exception as e:
            logger.error(f"Form filling error: {e}")
            try:
                await context.close()
            except Exception:
                pass
            return {
                "messages": [f"Form filling interrupted by error: {e!s}"],
                "challenge_detected": True,
                "blocker_type": "dom_interaction_error",
                "diagnostic_summary": f"Interaction error: {e!s}",
                "user_action_prompt": "Please manually fill any remaining fields or resolve the modal dialog in the browser window, then click 'Resume'.",
                "execution_status": "verification_required",
            }


def human_interaction_gate(state: LMSAutomationState) -> dict[str, Any]:
    """
    Node 4: Human-in-the-Loop Interrupt Gate.
    Pauses execution cleanly, surfaces diagnostic details and instructions,
    and awaits Command(resume=...) from the client.
    """
    verification_payload = {
        "status": "interaction_required",
        "blocker_type": state.get("blocker_type", "unknown"),
        "diagnostic_summary": state.get("diagnostic_summary", "Manual intervention required."),
        "user_action_prompt": state.get("user_action_prompt", "Please resolve the issue in the browser window and confirm."),
        "target_url": state.get("active_url") or state.get("target_url"),
        "candidate_info": state.get("candidate_info", {}),
        "screenshot_b64": state.get("screenshot_b64"),
    }

    # Pauses the graph and exposes verification_payload under __interrupt__
    user_response = interrupt(verification_payload)

    logger.info(f"Resumed from interrupt with user response: {user_response}")

    # Inspect the user's resolution decision
    if isinstance(user_response, dict) and user_response.get("status") in ("approved", "resolved", "continue"):
        return {
            "messages": [f"User resolved blocker: {user_response.get('message', 'Operator confirmed issue is fixed.')}"],
            "execution_status": "authorized",
            "challenge_detected": False,
            "blocker_type": None,
            "diagnostic_summary": None,
            "user_action_prompt": None,
            "screenshot_b64": None,
        }
    else:
        return {
            "messages": ["User rejected or aborted submission."],
            "execution_status": "cancelled",
        }


async def submission_node(state: LMSAutomationState) -> dict[str, Any]:
    """Node 5: Clicks submit button and verifies application confirmation."""
    active_url = state.get("active_url") or state.get("target_url")
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"

    async with async_playwright() as p:
        context = await launch_stealth_context(p, PROFILES_DIR, headless=headless)
        page = await context.new_page()

        try:
            await page.goto(active_url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(1000)

            # Locate submit button
            submit_btn = page.get_by_role("button", name=re.compile(r"submit|apply|save", re.I))
            if await submit_btn.count() == 0:
                submit_btn = page.locator("button[type='submit'], input[type='submit'], .btn-submit")

            if await submit_btn.count() == 0:
                screenshot = await capture_screenshot_b64(page)
                await context.close()
                return {
                    "messages": ["Submit button could not be located on the form page."],
                    "challenge_detected": True,
                    "blocker_type": "submit_button_missing",
                    "diagnostic_summary": "Submit button was not found in the DOM.",
                    "user_action_prompt": "Please click the Submit button manually in the browser window, then click 'Resume'.",
                    "screenshot_b64": screenshot,
                    "execution_status": "verification_required",
                }

            # Click the submit button
            await submit_btn.first.click()
            await page.wait_for_timeout(2500)

            # Check for validation error alerts on page
            error_locator = page.locator(".alert-danger, .error-message, [role='alert'], .field-validation-error")
            if await error_locator.count() > 0 and await error_locator.first.is_visible():
                err_text = await error_locator.first.inner_text()
                screenshot = await capture_screenshot_b64(page)
                await context.close()
                return {
                    "messages": [f"Portal rejected submission with validation error: {err_text}"],
                    "challenge_detected": True,
                    "blocker_type": "form_validation_error",
                    "diagnostic_summary": f"Form validation error: {err_text}",
                    "user_action_prompt": f"Please correct the following field error in the browser: '{err_text}', then click 'Resume'.",
                    "screenshot_b64": screenshot,
                    "execution_status": "verification_required",
                }

            # Extract confirmation reference if available
            confirm_locator = page.locator(".alert-success, .success-message, #reference-number, .confirmation-code")
            ref_text = ""
            if await confirm_locator.count() > 0 and await confirm_locator.first.is_visible():
                ref_text = await confirm_locator.first.inner_text()

            await context.close()
            msg = "Application submitted successfully to the portal!"
            if ref_text:
                msg += f" Confirmation details: {ref_text.strip()}"

            return {
                "messages": [msg],
                "execution_status": "complete",
            }

        except Exception as e:
            logger.error(f"Submission execution error: {e}")
            try:
                await context.close()
            except Exception:
                pass
            return {
                "messages": [f"Submission error: {e!s}"],
                "execution_status": "error",
            }


# ==============================================================================
# 5. Routing Logic & StateGraph Compilation
# ==============================================================================


def route_next_step(state: LMSAutomationState) -> str:
    """Routes execution based on execution_status."""
    status = state.get("execution_status")

    if status == "initialized":
        return "browser_navigation"
    elif status == "verification_required":
        return "human_interaction_gate"
    elif status == "filling":
        return "form_filling"
    elif status == "authorized":
        # When human approves, re-attempt filling or proceed to submit
        return "form_filling"
    elif status == "submitting":
        return "finalize_submission"
    return END


# In-memory checkpointer to persist paused threads
_checkpointer = InMemorySaver()


def build_automation_graph():
    """Builds and compiles the stateful LangGraph automation workflow."""
    workflow = StateGraph(LMSAutomationState)

    workflow.add_node("planning", planning_node)
    workflow.add_node("browser_navigation", navigation_node)
    workflow.add_node("form_filling", form_filling_node)
    workflow.add_node("human_interaction_gate", human_interaction_gate)
    workflow.add_node("finalize_submission", submission_node)

    workflow.set_entry_point("planning")

    workflow.add_conditional_edges(
        "planning",
        route_next_step,
        {"browser_navigation": "browser_navigation", END: END},
    )

    workflow.add_conditional_edges(
        "browser_navigation",
        route_next_step,
        {
            "form_filling": "form_filling",
            "human_interaction_gate": "human_interaction_gate",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "form_filling",
        route_next_step,
        {
            "finalize_submission": "finalize_submission",
            "human_interaction_gate": "human_interaction_gate",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "human_interaction_gate",
        route_next_step,
        {
            "form_filling": "form_filling",
            "finalize_submission": "finalize_submission",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "finalize_submission",
        route_next_step,
        {"human_interaction_gate": "human_interaction_gate", END: END},
    )

    return workflow.compile(checkpointer=_checkpointer)


# Singleton compiled graph instance
compiled_automation_graph = build_automation_graph()


# ==============================================================================
# 6. External Execution API (Stream, Inspect, Resume)
# ==============================================================================


async def start_portal_automation(
    candidate_info: dict[str, Any],
    thread_id: str,
    target_url: str | None = None,
) -> dict[str, Any]:
    """
    Initiates the browser automation graph for a candidate submission.
    Streams up until completion or pausing at a human-interaction interrupt.
    """
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: LMSAutomationState = {
        "messages": [],
        "candidate_info": candidate_info,
        "target_url": target_url or "http://localhost:8000/mock-lms/apply",
        "active_url": "",
        "execution_status": "initialized",
        "challenge_detected": False,
        "blocker_type": None,
        "diagnostic_summary": None,
        "user_action_prompt": None,
        "screenshot_b64": None,
        "step_retries": 0,
    }

    # Execute graph until pause or end
    async for _ in compiled_automation_graph.astream(
        initial_state, config=config, stream_mode="updates"
    ):
        pass

    state_snapshot = await compiled_automation_graph.aget_state(config)
    return format_graph_output(state_snapshot, thread_id)


async def resume_portal_automation(
    thread_id: str,
    resume_payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Resumes a paused browser automation thread using Command(resume=...).
    """
    config = {"configurable": {"thread_id": thread_id}}
    resume_command = Command(resume=resume_payload)

    async for _ in compiled_automation_graph.astream(
        resume_command, config=config, stream_mode="updates"
    ):
        pass

    state_snapshot = await compiled_automation_graph.aget_state(config)
    return format_graph_output(state_snapshot, thread_id)


async def get_portal_automation_status(thread_id: str) -> dict[str, Any]:
    """Fetches current execution state, interrupt payload, or diagnostic message."""
    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = await compiled_automation_graph.aget_state(config)
    return format_graph_output(state_snapshot, thread_id)


def format_graph_output(snapshot: Any, thread_id: str) -> dict[str, Any]:
    """Helper to structure snapshot into a clean API response."""
    values = snapshot.values or {}
    messages = values.get("messages", [])

    is_interrupted = False
    interrupt_payload = None

    if snapshot.tasks:
        for t in snapshot.tasks:
            if hasattr(t, "interrupts") and t.interrupts:
                is_interrupted = True
                interrupt_payload = t.interrupts[0].value
                break

    return {
        "thread_id": thread_id,
        "is_paused": is_interrupted,
        "execution_status": values.get("execution_status", "unknown"),
        "active_url": values.get("active_url", values.get("target_url")),
        "diagnostic": interrupt_payload or {
            "blocker_type": values.get("blocker_type"),
            "diagnostic_summary": values.get("diagnostic_summary"),
            "user_action_prompt": values.get("user_action_prompt"),
        },
        "screenshot_b64": values.get("screenshot_b64"),
        "messages": messages,
    }
