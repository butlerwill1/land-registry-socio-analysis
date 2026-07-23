from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..dependencies import get_current_principal, get_database_session
from ..entitlements import entitlement_response
from ..schemas import EntitlementResponse, Principal


router = APIRouter(prefix="/account", tags=["account"])


@router.get("/entitlements", response_model=EntitlementResponse)
def get_entitlements(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> EntitlementResponse:
    return entitlement_response(session, principal, request.app.state.settings)
