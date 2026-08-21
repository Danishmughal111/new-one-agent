"""Department routes."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_department_service
from app.schemas.department import DepartmentCreate, DepartmentResponse, DepartmentUpdate
from app.services.department_service import DepartmentService

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentResponse])
async def list_departments(
    service: DepartmentService = Depends(get_department_service),
) -> list:
    return await service.list()


@router.post("", response_model=DepartmentResponse, status_code=201)
async def create_department(
    payload: DepartmentCreate,
    service: DepartmentService = Depends(get_department_service),
):
    return await service.create(payload)


@router.get("/{department_id}", response_model=DepartmentResponse)
async def get_department(
    department_id: str,
    service: DepartmentService = Depends(get_department_service),
):
    return await service.get(department_id)


@router.patch("/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: str,
    payload: DepartmentUpdate,
    service: DepartmentService = Depends(get_department_service),
):
    return await service.update(department_id, payload)