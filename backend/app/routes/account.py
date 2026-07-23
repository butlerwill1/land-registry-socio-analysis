from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..dependencies import get_current_principal, get_database_session
from ..entitlements import entitlement_response
from ..rate_limit import enforce_pro_access_rate_limit
from ..schemas import AccessCodeRequest, EntitlementResponse, Principal


router = APIRouter(prefix="/account", tags=["account"])


@router.post("/access-code", response_model=EntitlementResponse)
def redeem_access_code(
    payload: AccessCodeRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_database_session),
) -> EntitlementResponse:
    enforce_pro_access_rate_limit(request)
    service = request.app.state.pro_access_code_service
    token, expires_at = service.redeem(payload.code.strip())
    response.set_cookie(
        key=service.cookie_name,
        value=token,
        expires=expires_at,
        httponly=True,
        secure=request.app.state.settings.app_env == "production",
        samesite="lax",
        path="/",
    )
    return entitlement_response(session, Principal(codePlan="pro"), request.app.state.settings)


@router.get("/entitlements", response_model=EntitlementResponse)
def get_entitlements(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> EntitlementResponse:
    return entitlement_response(session, principal, request.app.state.settings)
