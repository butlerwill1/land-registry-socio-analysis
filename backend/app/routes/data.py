from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..data_repository import DataAccessError, DataRepository
from ..dependencies import (
    get_current_principal,
    get_database_session,
    get_repository,
)
from ..entitlements import resolve_plan
from ..rate_limit import enforce_data_rate_limit
from ..schemas import (
    DistrictRecord,
    LsoaMapResponse,
    MapMetricResponse,
    MetricKey,
    Principal,
)


router = APIRouter(prefix="/data", tags=["data"])


@router.get("/districts/{district}", response_model=DistrictRecord)
def get_district(
    district: str,
    request: Request,
    repository: DataRepository = Depends(get_repository),
    principal: Principal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> DistrictRecord:
    enforce_data_rate_limit(request, principal.subject)
    try:
        return repository.get_district(
            district, resolve_plan(session, principal, request.app.state.settings)
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/map", response_model=MapMetricResponse)
def get_map_values(
    metric: MetricKey,
    year: int,
    request: Request,
    repository: DataRepository = Depends(get_repository),
    principal: Principal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> MapMetricResponse:
    enforce_data_rate_limit(request, principal.subject)
    try:
        return repository.map_values(
            metric,
            year,
            resolve_plan(session, principal, request.app.state.settings),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except DataAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@router.get("/lsoas/{district}", response_model=LsoaMapResponse)
def get_lsoa_values(
    district: str,
    metric: MetricKey,
    request: Request,
    repository: DataRepository = Depends(get_repository),
    principal: Principal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> LsoaMapResponse:
    enforce_data_rate_limit(request, principal.subject)
    if resolve_plan(session, principal, request.app.state.settings) != "pro":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="LSOA detail requires the Pro plan.",
        )
    try:
        return repository.lsoa_values(district, metric)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DataAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
