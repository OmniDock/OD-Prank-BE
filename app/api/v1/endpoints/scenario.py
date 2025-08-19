from fastapi import APIRouter, Depends
from app.core.auth import get_current_user, AuthUser
from app.schemas.scenario import ScenarioCreateRequest
from fastapi import Body
from app.langchain.scenarios.initial_processor import InitialScenarioProcessor
from app.core.utils.enums import VoiceLineTypeEnum

router = APIRouter(tags=["scenario"])


@router.post("/")
async def create_scenario(
    user: AuthUser = Depends(get_current_user),
    scenario_create_request: ScenarioCreateRequest = Body(...),
):
    target_counts = {
        VoiceLineTypeEnum.OPENING: 3,
        VoiceLineTypeEnum.QUESTION: 8,
        VoiceLineTypeEnum.RESPONSE: 5,
        VoiceLineTypeEnum.CLOSING: 3,
    }
    scenario_processor = InitialScenarioProcessor(target_counts)
    result = await scenario_processor._process_scenario(scenario_create_request)

    return result