from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import SuperAdminUser
from src.core.database import get_db
from src.modules.terms.schemas import (
    FixedFeeCreate,
    FixedFeeResponse,
    FixedFeeUpdate,
    PriceSettingBulkUpdate,
    PriceSettingResponse,
    TermCreate,
    TermDetailResponse,
    TermResponse,
    TermUpdate,
    TransportPricingBulkUpdate,
    TransportPricingResponse,
    TransportZoneCreate,
    TransportZoneResponse,
    TransportZoneUpdate,
)
from src.modules.terms.service import TermService
from src.shared.schemas import SuccessResponse

router = APIRouter(prefix="/terms", tags=["Terms & Pricing"])


# --- Term Endpoints ---

@router.get("", response_model=SuccessResponse[list[TermResponse]])
async def list_terms(
    current_user: SuperAdminUser,
    year: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all terms."""
    service = TermService(db)
    terms = await service.list_terms(year=year)
    return SuccessResponse(
        data=[TermResponse.model_validate(t) for t in terms],
        message="Terms retrieved",
    )


@router.get("/active", response_model=SuccessResponse[TermDetailResponse | None])
async def get_active_term(
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Get the currently active term with pricing."""
    service = TermService(db)
    term = await service.get_active_term()

    if not term:
        return SuccessResponse(data=None, message="No active term")

    term = await service.get_term_by_id(term.id, with_pricing=True)
    return SuccessResponse(
        data=_term_to_detail_response(term),
        message="Active term retrieved",
    )


@router.post("", response_model=SuccessResponse[TermResponse], status_code=201)
async def create_term(
    data: TermCreate,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new term.

    Pricing is automatically copied from the previous term.
    The term is created in Draft status.
    """
    service = TermService(db)
    term = await service.create_term(data, created_by_id=current_user.id)

    return SuccessResponse(
        data=TermResponse.model_validate(term),
        message="Term created with pricing copied from previous term",
    )


@router.put("/{term_id}", response_model=SuccessResponse[TermResponse])
async def update_term(
    term_id: int,
    data: TermUpdate,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Update term data (not status)."""
    service = TermService(db)
    term = await service.update_term(term_id, data, updated_by_id=current_user.id)

    return SuccessResponse(
        data=TermResponse.model_validate(term),
        message="Term updated",
    )


@router.post("/{term_id}/activate", response_model=SuccessResponse[TermResponse])
async def activate_term(
    term_id: int,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Activate a term.

    The currently active term will be automatically closed.
    """
    service = TermService(db)
    term = await service.activate_term(term_id, activated_by_id=current_user.id)
    term = await service.get_term_by_id(term.id)

    return SuccessResponse(
        data=TermResponse.model_validate(term),
        message="Term activated (previous active term was closed)",
    )


@router.post("/{term_id}/close", response_model=SuccessResponse[TermResponse])
async def close_term(
    term_id: int,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Close a term manually."""
    service = TermService(db)
    term = await service.close_term(term_id, closed_by_id=current_user.id)
    term = await service.get_term_by_id(term.id)

    return SuccessResponse(
        data=TermResponse.model_validate(term),
        message="Term closed",
    )


# --- Price Settings Endpoints ---

@router.put("/{term_id}/price-settings", response_model=SuccessResponse[list[PriceSettingResponse]])
async def update_price_settings(
    term_id: int,
    data: PriceSettingBulkUpdate,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Bulk update price settings for a term."""
    service = TermService(db)
    settings = await service.update_price_settings(
        term_id, data.price_settings, updated_by_id=current_user.id
    )

    return SuccessResponse(
        data=[PriceSettingResponse.model_validate(s) for s in settings],
        message="Price settings updated",
    )


# --- Transport Zone Endpoints ---

@router.get("/transport-zones", response_model=SuccessResponse[list[TransportZoneResponse]])
async def list_transport_zones(
    current_user: SuperAdminUser,
    include_inactive: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """List all transport zones."""
    service = TermService(db)
    zones = await service.list_transport_zones(include_inactive=include_inactive)

    return SuccessResponse(
        data=[TransportZoneResponse.model_validate(z) for z in zones],
        message="Transport zones retrieved",
    )


@router.post("/transport-zones", response_model=SuccessResponse[TransportZoneResponse], status_code=201)
async def create_transport_zone(
    data: TransportZoneCreate,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Create a new transport zone."""
    service = TermService(db)
    zone = await service.create_transport_zone(data, created_by_id=current_user.id)

    return SuccessResponse(
        data=TransportZoneResponse.model_validate(zone),
        message="Transport zone created",
    )


@router.put("/transport-zones/{zone_id}", response_model=SuccessResponse[TransportZoneResponse])
async def update_transport_zone(
    zone_id: int,
    data: TransportZoneUpdate,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Update a transport zone."""
    service = TermService(db)
    zone = await service.update_transport_zone(zone_id, data, updated_by_id=current_user.id)

    return SuccessResponse(
        data=TransportZoneResponse.model_validate(zone),
        message="Transport zone updated",
    )


# --- Transport Pricing Endpoints ---

@router.put("/{term_id}/transport-pricing", response_model=SuccessResponse[list[TransportPricingResponse]])
async def update_transport_pricing(
    term_id: int,
    data: TransportPricingBulkUpdate,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Bulk update transport pricing for a term."""
    service = TermService(db)
    pricings = await service.update_transport_pricing(
        term_id, data.transport_pricings, updated_by_id=current_user.id
    )

    # Reload with zone data
    term = await service.get_term_by_id(term_id, with_pricing=True)

    return SuccessResponse(
        data=[
            TransportPricingResponse(
                id=tp.id,
                term_id=tp.term_id,
                zone_id=tp.zone_id,
                zone_name=tp.zone.zone_name,
                zone_code=tp.zone.zone_code,
                transport_fee_amount=tp.transport_fee_amount,
            )
            for tp in term.transport_pricings
        ],
        message="Transport pricing updated",
    )


# --- Fixed Fee Endpoints ---

@router.get("/fixed-fees", response_model=SuccessResponse[list[FixedFeeResponse]])
async def list_fixed_fees(
    current_user: SuperAdminUser,
    include_inactive: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """List all fixed fees (kits from 'Fixed Fees' category)."""
    service = TermService(db)
    kits = await service.list_fixed_fees(include_inactive=include_inactive)

    return SuccessResponse(
        data=[FixedFeeResponse.from_kit(kit) for kit in kits],
        message="Fixed fees retrieved",
    )


@router.post("/fixed-fees", response_model=SuccessResponse[FixedFeeResponse], status_code=201)
async def create_fixed_fee(
    data: FixedFeeCreate,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Create a new fixed fee (kit in 'Fixed Fees' category)."""
    service = TermService(db)
    kit = await service.create_fixed_fee(data, created_by_id=current_user.id)

    return SuccessResponse(
        data=FixedFeeResponse.from_kit(kit),
        message="Fixed fee created",
    )


@router.put("/fixed-fees/{fee_id}", response_model=SuccessResponse[FixedFeeResponse])
async def update_fixed_fee(
    fee_id: int,
    data: FixedFeeUpdate,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Update a fixed fee (kit in 'Fixed Fees' category)."""
    service = TermService(db)
    kit = await service.update_fixed_fee(fee_id, data, updated_by_id=current_user.id)

    return SuccessResponse(
        data=FixedFeeResponse.from_kit(kit),
        message="Fixed fee updated",
    )


@router.get("/{term_id}", response_model=SuccessResponse[TermDetailResponse])
async def get_term(
    term_id: int,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Get term by ID with pricing."""
    service = TermService(db)
    term = await service.get_term_by_id(term_id, with_pricing=True)

    if not term:
        from src.core.exceptions import NotFoundError
        raise NotFoundError("Term", term_id)

    return SuccessResponse(
        data=_term_to_detail_response(term),
        message="Term retrieved",
    )


# --- Helper Functions ---

def _term_to_detail_response(term) -> TermDetailResponse:
    """Convert Term model to TermDetailResponse."""
    return TermDetailResponse(
        id=term.id,
        year=term.year,
        term_number=term.term_number,
        display_name=term.display_name,
        status=term.status,
        start_date=term.start_date,
        end_date=term.end_date,
        created_at=term.created_at,
        updated_at=term.updated_at,
        price_settings=[
            PriceSettingResponse.model_validate(ps) for ps in term.price_settings
        ],
        transport_pricings=[
            TransportPricingResponse(
                id=tp.id,
                term_id=tp.term_id,
                zone_id=tp.zone_id,
                zone_name=tp.zone.zone_name,
                zone_code=tp.zone.zone_code,
                transport_fee_amount=tp.transport_fee_amount,
            )
            for tp in term.transport_pricings
        ],
    )
