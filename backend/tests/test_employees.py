from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import employees as employees_api
from app.core.security import current_claims
from app.main import app


class MemoryEmployees:
    def __init__(self, employees):
        self.employees = employees

    def find_one(self, query):
        for employee in self.employees:
            if all(self._matches(employee, key, value) for key, value in query.items()):
                return employee
        return None

    def _matches(self, employee, key, value):
        if isinstance(value, dict) and "$ne" in value:
            return employee.get(key) != value["$ne"]
        return employee.get(key) == value

    def update_one(self, query, update):
        employee = self.find_one(query)
        if employee:
            employee.update(update["$set"])

    def delete_one(self, query):
        employee = self.find_one(query)
        if employee:
            self.employees.remove(employee)


class MemoryAuditLogs:
    def insert_one(self, _event):
        pass


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def employee(employee_id, role="employee", **overrides):
    return {
        "_id": f"db-{employee_id}",
        "employee_id": employee_id,
        "full_name": "Test Person",
        "email": f"{employee_id.lower()}@example.com",
        "department": "Operations",
        "role": role,
        "password_hash": "old-hash",
        "is_active": True,
        **overrides,
    }


def employee_client(monkeypatch, employees, subject="ADM-1"):
    collection = MemoryEmployees(employees)
    db = SimpleNamespace(employees=collection, audit_logs=MemoryAuditLogs())
    monkeypatch.setattr(employees_api, "get_db", lambda: db)
    app.dependency_overrides[current_claims] = lambda: {"sub": subject, "role": "admin"}
    return TestClient(app), collection


def test_admin_can_edit_own_account(monkeypatch):
    administrator = employee("ADM-1", role="admin")
    client, collection = employee_client(monkeypatch, [administrator])
    monkeypatch.setattr(employees_api, "hash_password", lambda password: f"hashed:{password}")

    response = client.put("/api/employees/ADM-1", json={
        "employee_id": "ADM-2",
        "full_name": "Updated Admin",
        "email": "updated@example.com",
        "department": "Security",
        "role": "admin",
        "password": "new-password",
    })

    assert response.status_code == 200
    assert response.json()["employee_id"] == "ADM-2"
    assert response.json()["full_name"] == "Updated Admin"
    assert response.json()["email"] == "updated@example.com"
    assert response.json()["department"] == "Security"
    assert administrator["password_hash"] == "hashed:new-password"
    removal = client.delete("/api/employees/ADM-2")
    assert removal.status_code == 400
    assert removal.json()["detail"] == "Administrator accounts cannot be removed"
    assert collection.employees == [administrator]


def test_admin_cannot_delete_own_account(monkeypatch):
    administrator = employee("ADM-1", role="admin")
    client, collection = employee_client(monkeypatch, [administrator])

    response = client.delete("/api/employees/ADM-1")

    assert response.status_code == 400
    assert response.json()["detail"] == "You cannot remove your own administrator account."
    assert collection.employees == [administrator]


def test_admin_cannot_delete_another_administrator(monkeypatch):
    own_account = employee("ADM-1", role="admin")
    other_admin = employee("ADM-2", role="admin")
    client, collection = employee_client(monkeypatch, [own_account, other_admin])

    response = client.delete("/api/employees/ADM-2")

    assert response.status_code == 400
    assert response.json()["detail"] == "Administrator accounts cannot be removed"
    assert collection.employees == [own_account, other_admin]


def test_admin_can_update_and_delete_normal_employee(monkeypatch):
    administrator = employee("ADM-1", role="admin")
    staff_member = employee("EMP-1")
    client, collection = employee_client(monkeypatch, [administrator, staff_member])

    update = client.put("/api/employees/EMP-1", json={
        "employee_id": "EMP-2",
        "full_name": "Updated Employee",
        "email": "employee@example.com",
        "department": "Finance",
        "role": "employee",
        "password": None,
    })
    removal = client.delete("/api/employees/EMP-2")

    assert update.status_code == 200
    assert update.json()["employee_id"] == "EMP-2"
    assert removal.status_code == 200
    assert removal.json()["employee_id"] == "EMP-2"
    assert collection.employees == [administrator]