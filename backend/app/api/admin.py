from datetime import date, timedelta
from io import BytesIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from app.core.security import require_admin
from app.db.mongodb import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])

def format_location(location: dict | None) -> str:
    if not location or location.get("latitude") is None or location.get("longitude") is None:
        return ""
    if location.get("display_name"):
        return location["display_name"]
    if location.get("area"):
        city = location.get("city")
        return f"{location['area']}, {city}" if city and city not in location["area"] else location["area"]
    accuracy = location.get("accuracy")
    suffix = f", +/- {round(accuracy)} m" if accuracy is not None else ""
    return f"{location['latitude']:.5f}, {location['longitude']:.5f}{suffix}"

@router.get("/export")
def export_attendance(
    export_range: str = Query("day", alias="range", pattern="^(day|week|month|year)$"),
    anchor_date: date = Query(default_factory=date.today, alias="date"),
    _claims: dict = Depends(require_admin),
):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    if export_range == "day":
        start_date = end_date = anchor_date
    elif export_range == "week":
        start_date = anchor_date - timedelta(days=anchor_date.weekday())
        end_date = start_date + timedelta(days=6)
    elif export_range == "month":
        start_date = anchor_date.replace(day=1)
        next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = next_month - timedelta(days=1)
    else:
        start_date = anchor_date.replace(month=1, day=1)
        end_date = anchor_date.replace(month=12, day=31)

    db = get_db()
    records = list(db.attendance.find(
        {"date": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()}},
        {"_id": 0},
    ).sort([("date", -1), ("employee_id", 1)]))
    employee_ids = {record.get("employee_id") for record in records}
    employees = {
        employee["employee_id"]: employee
        for employee in db.employees.find(
            {"employee_id": {"$in": list(employee_ids)}},
            {"employee_id": 1, "full_name": 1, "email": 1, "department": 1},
        )
    }

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Attendance"
    headers = ["Date", "Employee ID", "Employee", "Email", "Department", "Check In", "Check In Location", "Check Out", "Check Out Location", "Status"]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for record in records:
        employee = employees.get(record.get("employee_id"), {})
        sheet.append([
            record.get("date"), record.get("employee_id"), employee.get("full_name", ""), employee.get("email", ""),
            employee.get("department", ""), record.get("check_in_time"), format_location(record.get("check_in_location")),
            record.get("check_out_time"), format_location(record.get("check_out_location")), record.get("final_status"),
        ])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        width = min(max(len(str(cell.value or "")) for cell in column) + 2, 30)
        sheet.column_dimensions[column[0].column_letter].width = width

    output = BytesIO()
    workbook.save(output)
    filename = f"aurelix-attendance-{export_range}-{start_date.isoformat()}-{end_date.isoformat()}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
