from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, status

from deepticket.api.deps import get_service
from deepticket.api.schemas import (
    IngressEventRequest,
    IngressJobResponse,
)
from deepticket.auth.ingress_auth import verify_ingress_api_key
from deepticket.layers.input.ingress_models import IngressEvent

router = APIRouter(prefix="/api/ingress", tags=["Ingress"])


@router.get("/routes")
async def list_routes(
    request: Request,
    _: None = Depends(verify_ingress_api_key),
) -> dict:
    service = get_service(request)
    return {"routes": service.list_routes()}


@router.post(
    "/events",
    response_model=IngressJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_event(
    body: IngressEventRequest,
    request: Request,
    _: None = Depends(verify_ingress_api_key),
) -> IngressJobResponse:
    service = get_service(request)
    event = IngressEvent(
        source=body.source,
        project_id=body.project_id,
        external_id=body.external_id,
        question=body.question,
        image_urls=list(body.image_urls),
        extensions=dict(body.extensions),
    )
    try:
        service.projects.require(body.project_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        result = await service.submit_ingress_event(event)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        message = str(exc)
        if "LLM 未配置" in message:
            raise HTTPException(status_code=503, detail=message) from exc
        raise HTTPException(status_code=500, detail=message) from exc
    return IngressJobResponse(**asdict(result))


@router.get("/jobs/{job_id}", response_model=IngressJobResponse)
async def get_job(
    job_id: str,
    request: Request,
    _: None = Depends(verify_ingress_api_key),
) -> IngressJobResponse:
    service = get_service(request)
    doc = service.get_ingress_job(job_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    payload = {k: v for k, v in doc.items() if k not in {"updated_at", "route_type"}}
    return IngressJobResponse(**payload)
