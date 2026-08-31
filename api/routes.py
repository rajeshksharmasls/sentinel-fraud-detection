"""
Sentinel REST API routes.

Provides endpoints for investigation submission, status polling, approval, and policy queries.
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
)

from .models import (
    ApprovalRequest,
    InvestigationStatusResponse,
    InvestigationSubmitRequest,
    InvestigationSubmitResponse,
)

from policy import create_policy_engine


def create_router(
    service,
) -> APIRouter:
    """Create FastAPI router with Sentinel endpoints."""

    router = APIRouter(prefix="/api/v1")

    @router.get("/health")
    async def health():
        """Health check endpoint."""
        return {
            "status": "ok",
        }

    @router.post(
        "/investigations",
        response_model=InvestigationSubmitResponse,
        status_code=202,
    )
    async def submit_investigation(
        request: InvestigationSubmitRequest,
    ):
        """Submit a fraud investigation."""

        try:

            result = service.triage_account(
                request.account_id,
                require_manual_approval=True,
            )

            return InvestigationSubmitResponse(
                job_id=result.get(
                    "approval_id",
                    "pending",
                ),
                account_id=request.account_id,
                status=result.get("status", "queued"),
                graph_thread_id=f"investigation-{result.get('approval_id', 'unknown')}",
            )

        except ValueError as exc:

            raise HTTPException(
                status_code=400,
                detail=str(exc),
            )

    @router.get(
        "/investigations/{job_id}",
        response_model=InvestigationStatusResponse,
    )
    async def get_investigation(
        job_id: str,
    ):
        """Get investigation status."""

        # For now, return a simple response since we don't have a queue store in the current app
        return InvestigationStatusResponse(
            job_id=job_id,
            account_id="unknown",
            status="completed",
            graph_thread_id=f"investigation-{job_id}",
        )

    @router.post(
        "/investigations/{job_id}/approval"
    )
    async def approve_investigation(
        job_id: str,
        request: ApprovalRequest,
    ):
        """Approve or reject an investigation action."""

        try:

            result = service.handle_approval(
                job_id,
                request.approved,
            )

            return {
                "job_id": job_id,
                "approved": request.approved,
                "reason": request.reason,
                "status": "completed",
                "result": result,
            }

        except KeyError:

            raise HTTPException(
                status_code=404,
                detail="Investigation not found.",
            )

    @router.get("/policies")
    async def get_policies():
        """List configured policy rules."""

        engine = create_policy_engine()

        return {
            "rules": [rule.__name__ for rule in engine.rules]
        }

    @router.post("/sweeps", status_code=202)
    async def start_sweep():
        """Start the isolated background queue worker and return without waiting."""
        return service.start_queue_sweep()

    @router.get("/sweeps/{job_id}")
    async def sweep_status(job_id: str):
        try:
            return service.get_job_status(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Sweep not found.")

    @router.get("/sweeps/{job_id}/results")
    async def sweep_results(job_id: str):
        try:
            return service.collect_results(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Sweep not found.")

    return router
