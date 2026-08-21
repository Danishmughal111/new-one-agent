"""Task routes.

Status changes are only possible through the transition endpoint (backed by
``TaskStateMachine``). PATCH cannot modify status.
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_task_service
from app.schemas.audit import TaskStatusHistoryResponse
from app.schemas.task import (
    TaskAssign,
    TaskCreate,
    TaskResponse,
    TaskStatusTransition,
    TaskUpdate,
)
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    service: TaskService = Depends(get_task_service),
) -> list:
    return await service.list()


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    payload: TaskCreate,
    service: TaskService = Depends(get_task_service),
):
    return await service.create(payload)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
):
    return await service.get(task_id)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    payload: TaskUpdate,
    service: TaskService = Depends(get_task_service),
):
    return await service.update(task_id, payload)


@router.post("/{task_id}/assign", response_model=TaskResponse)
async def assign_task(
    task_id: str,
    payload: TaskAssign,
    service: TaskService = Depends(get_task_service),
):
    return await service.assign(
        task_id,
        assignee_agent_id=payload.assignee_agent_id,
        changed_by_agent_id=payload.changed_by_agent_id,
    )


@router.post("/{task_id}/transition", response_model=TaskResponse)
async def transition_task(
    task_id: str,
    payload: TaskStatusTransition,
    service: TaskService = Depends(get_task_service),
):
    return await service.transition(task_id, payload)


@router.get("/{task_id}/history", response_model=list[TaskStatusHistoryResponse])
async def task_history(
    task_id: str,
    service: TaskService = Depends(get_task_service),
) -> list:
    return await service.get_history(task_id)