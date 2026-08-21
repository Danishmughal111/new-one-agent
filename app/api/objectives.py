"""Objective routes, including deterministic workflow execution."""

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_company_workflow,
    get_objective_service,
)
from app.orchestration.company_workflow import CompanyWorkflow
from app.schemas.objective import (
    ObjectiveCreate,
    ObjectiveResponse,
    ObjectiveRunResponse,
    ObjectiveUpdate,
)
from app.services.objective_service import ObjectiveService

router = APIRouter(prefix="/objectives", tags=["objectives"])


@router.get("", response_model=list[ObjectiveResponse])
async def list_objectives(
    service: ObjectiveService = Depends(get_objective_service),
) -> list:
    return await service.list()


@router.post("", response_model=ObjectiveResponse, status_code=201)
async def create_objective(
    payload: ObjectiveCreate,
    service: ObjectiveService = Depends(get_objective_service),
):
    return await service.create(payload)


@router.get("/{objective_id}", response_model=ObjectiveResponse)
async def get_objective(
    objective_id: str,
    service: ObjectiveService = Depends(get_objective_service),
):
    return await service.get(objective_id)


@router.patch("/{objective_id}", response_model=ObjectiveResponse)
async def update_objective(
    objective_id: str,
    payload: ObjectiveUpdate,
    service: ObjectiveService = Depends(get_objective_service),
):
    return await service.update(objective_id, payload)


@router.post("/{objective_id}/run", response_model=ObjectiveRunResponse)
async def run_objective(
    objective_id: str,
    service: ObjectiveService = Depends(get_objective_service),
    workflow: CompanyWorkflow = Depends(get_company_workflow),
):
    """Run the deterministic workflow for a persisted objective."""
    objective, result = await service.run(objective_id, workflow)
    return {"objective": objective, "workflow": result.to_dict()}