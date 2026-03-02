from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import io

from src.core.auth.dependencies import require_roles
from src.core.auth.models import UserRole, User
from src.core.database.session import get_db
from src.modules.employees.schemas import (
    EmployeeCreate,
    EmployeeCsvImportResult,
    EmployeeListFilters,
    EmployeeResponse,
    EmployeeUpdate,
)
from src.modules.employees.service import EmployeeService
from src.shared.schemas.base import ApiResponse, PaginatedResponse

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.get(
    "",
    response_model=ApiResponse[PaginatedResponse[EmployeeResponse]],
)
async def list_employees(
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.SUPER_ADMIN,
            UserRole.ADMIN,
            UserRole.ACCOUNTANT,
        )
    ),
):
    """List employees with filters and pagination."""
    from src.modules.employees.models import EmployeeStatus

    parsed_status = None
    if status:
        try:
            parsed_status = EmployeeStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status value")

    filters = EmployeeListFilters(
        status=parsed_status,
        search=search,
        page=page,
        limit=limit,
    )
    service = EmployeeService(db)
    employees, total = await service.list_employees(filters)
    items = [EmployeeResponse.model_validate(e) for e in employees]
    return ApiResponse(
        success=True,
        message="Employees fetched",
        data=PaginatedResponse[EmployeeResponse].create(
            items=items,
            total=total,
            page=page,
            limit=limit,
        ),
    )


@router.get(
    "/{employee_id:int}",
    response_model=ApiResponse[EmployeeResponse],
)
async def get_employee(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.SUPER_ADMIN,
            UserRole.ADMIN,
            UserRole.ACCOUNTANT,
        )
    ),
):
    """Get one employee by id."""
    service = EmployeeService(db)
    employee = await service.get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return ApiResponse(
        success=True,
        message="Employee fetched",
        data=EmployeeResponse.model_validate(employee.__dict__),
    )


@router.post(
    "",
    response_model=ApiResponse[EmployeeResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_employee(
    payload: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    """Create a new employee."""
    service = EmployeeService(db)
    employee = await service.create_employee(payload, created_by_id=current_user.id)
    return ApiResponse(
        success=True,
        message="Employee created",
        data=EmployeeResponse.model_validate(employee.__dict__),
    )


@router.get("/export")
async def export_employees_csv(
    format: str = "csv",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.SUPER_ADMIN,
            UserRole.ADMIN,
            UserRole.ACCOUNTANT,
        )
    ),
):
    """Export employees as CSV."""
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="Only csv format is supported")
    service = EmployeeService(db)
    csv_data = await service.export_csv()
    filename = f"employees_{datetime.utcnow().date().isoformat()}.csv"
    return StreamingResponse(
        io.StringIO(csv_data),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete(
    "/{employee_id:int}",
    response_model=ApiResponse[dict[str, bool]],
)
async def delete_employee(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    """Delete an employee by id."""
    service = EmployeeService(db)
    employee = await service.get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    try:
        await service.delete_employee(employee)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Employee is referenced by other records and cannot be deleted",
        ) from exc
    return ApiResponse(
        success=True,
        message="Employee deleted",
        data={"deleted": True},
    )


@router.put(
    "/{employee_id:int}",
    response_model=ApiResponse[EmployeeResponse],
)
async def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    """Update an existing employee."""
    service = EmployeeService(db)
    employee = await service.get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    employee = await service.update_employee(employee, payload)
    return ApiResponse(
        success=True,
        message="Employee updated",
        data=EmployeeResponse.model_validate(employee.__dict__),
    )


@router.post(
    "/import-csv",
    response_model=ApiResponse[EmployeeCsvImportResult],
)
async def import_employees_from_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    """Import employees from CSV exported from Google Form."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="CSV file is empty")
    service = EmployeeService(db)
    result = await service.import_from_csv(content, created_by_id=current_user.id)
    return ApiResponse(
        success=True,
        message="Import completed",
        data=result,
    )

