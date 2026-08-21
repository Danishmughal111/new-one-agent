"""Agent routes."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_agent_service
from app.schemas.agent import AgentCreate, AgentResponse, AgentUpdate
from app.services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    service: AgentService = Depends(get_agent_service),
) -> list:
    return await service.list()


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    payload: AgentCreate,
    service: AgentService = Depends(get_agent_service),
):
    return await service.create(payload)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    service: AgentService = Depends(get_agent_service),
):
    return await service.get(agent_id)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    service: AgentService = Depends(get_agent_service),
):
    return await service.update(agent_id, payload)