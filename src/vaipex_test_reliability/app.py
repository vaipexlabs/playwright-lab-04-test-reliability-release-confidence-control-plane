"""Deterministic checkout application for reliability-control scenarios."""

from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Annotated

from fastapi import FastAPI, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

PACKAGE_ROOT = Path(__file__).parent


class CheckoutScenario(StrEnum):
    """Supported deterministic reliability scenarios."""

    STABLE = "stable"
    TRANSIENT = "transient"
    CRITICAL_FAILURE = "critical-failure"


class ScenarioState:
    """Maintain deterministic request counts for controlled recovery."""

    def __init__(self) -> None:
        self._attempts: dict[CheckoutScenario, int] = {}
        self._lock = Lock()

    def next_attempt(self, scenario: CheckoutScenario) -> int:
        with self._lock:
            attempt = self._attempts.get(scenario, 0) + 1
            self._attempts[scenario] = attempt
            return attempt

    def reset(self) -> None:
        with self._lock:
            self._attempts.clear()


scenario_state = ScenarioState()
app = FastAPI(
    title="Vaipex Release Confidence Lab",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.mount("/static", StaticFiles(directory=PACKAGE_ROOT / "static"), name="static")
templates = Jinja2Templates(directory=PACKAGE_ROOT / "templates")


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    """Expose a stable readiness contract for local orchestration."""

    return {"status": "ready"}


@app.post("/api/control/reset")
def reset_scenarios() -> dict[str, str]:
    """Reset deterministic scenario state between complete test runs."""

    scenario_state.reset()
    return {"status": "reset"}


@app.post("/api/checkout")
def complete_checkout(
    scenario: Annotated[CheckoutScenario, Query()] = CheckoutScenario.STABLE,
) -> JSONResponse:
    """Return stable, transient-recovery, or persistent-failure outcomes."""

    attempt = scenario_state.next_attempt(scenario)
    if scenario is CheckoutScenario.TRANSIENT and attempt == 1:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "attempt": attempt,
                "message": "Payment service temporarily unavailable",
                "outcome": "transient-failure",
            },
        )
    if scenario is CheckoutScenario.CRITICAL_FAILURE:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "attempt": attempt,
                "message": "Payment authorization failed",
                "outcome": "critical-failure",
            },
        )
    return JSONResponse(
        content={
            "attempt": attempt,
            "message": "Order confirmed",
            "order_id": "VXP-2048",
            "outcome": "confirmed",
        }
    )


@app.get("/", response_class=HTMLResponse)
def checkout(
    request: Request,
    scenario: CheckoutScenario = CheckoutScenario.STABLE,
) -> HTMLResponse:
    """Render an addressable checkout reliability scenario."""

    scenario_contract = {
        CheckoutScenario.STABLE: {
            "badge": "Stable path",
            "description": "A healthy customer-critical checkout journey.",
            "expectation": "Passes on the first attempt",
        },
        CheckoutScenario.TRANSIENT: {
            "badge": "Controlled recovery",
            "description": "The first payment request fails; the second recovers.",
            "expectation": "Preserves a flaky recovery signal",
        },
        CheckoutScenario.CRITICAL_FAILURE: {
            "badge": "Critical failure",
            "description": "Payment authorization fails on every attempt.",
            "expectation": "Blocks release regardless of aggregate rate",
        },
    }[scenario]
    return templates.TemplateResponse(
        request=request,
        name="checkout.html",
        context={"scenario": scenario.value, **scenario_contract},
    )
