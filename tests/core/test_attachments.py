"""Tests for attachments (upload, download, payment with confirmation file)."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.core.config import settings
from src.modules.students.models import Student


@pytest.fixture
def storage_tmp_path(tmp_path, monkeypatch):
    """Use tmp_path for attachment storage in API tests."""
    monkeypatch.setattr(settings, "storage_path", str(tmp_path))
    return tmp_path


class TestAttachmentEndpoints:
    """Tests for attachment API endpoints."""

    async def _get_admin_token(self, client: AsyncClient, db_session: AsyncSession) -> str:
        auth = AuthService(db_session)
        await auth.create_user(
            email="att_api@test.com",
            password="Pass123",
            full_name="Att API",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.commit()
        _, token, _ = await auth.authenticate("att_api@test.com", "Pass123")
        return token

    async def test_upload_attachment_image(
        self, client: AsyncClient, db_session: AsyncSession, storage_tmp_path
    ):
        """POST /attachments with image returns 201 and attachment id."""
        token = await self._get_admin_token(client, db_session)
        image_content = b"\xff\xd8\xff fake jpeg"
        response = await client.post(
            "/api/v1/attachments",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("proof.jpg", image_content, "image/jpeg")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] is not None
        assert data["data"]["file_name"] == "proof.jpg"
        assert data["data"]["content_type"] == "image/jpeg"
        assert data["data"]["file_size"] == len(image_content)

    async def test_upload_attachment_pdf(
        self, client: AsyncClient, db_session: AsyncSession, storage_tmp_path
    ):
        """POST /attachments with PDF returns 201."""
        token = await self._get_admin_token(client, db_session)
        pdf_content = b"%PDF-1.4 fake pdf"
        response = await client.post(
            "/api/v1/attachments",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("proof.pdf", pdf_content, "application/pdf")},
        )
        assert response.status_code == 201
        assert response.json()["data"]["content_type"] == "application/pdf"

    async def test_upload_attachment_invalid_type(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """POST /attachments with text/plain returns 400."""
        token = await self._get_admin_token(client, db_session)
        response = await client.post(
            "/api/v1/attachments",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("doc.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 422  # validation error

    async def test_get_attachment_info(
        self, client: AsyncClient, db_session: AsyncSession, storage_tmp_path
    ):
        """GET /attachments/{id} returns metadata."""
        token = await self._get_admin_token(client, db_session)
        upload_resp = await client.post(
            "/api/v1/attachments",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("x.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
        att_id = upload_resp.json()["data"]["id"]
        response = await client.get(
            f"/api/v1/attachments/{att_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["file_name"] == "x.jpg"

    async def test_download_attachment(
        self, client: AsyncClient, db_session: AsyncSession, storage_tmp_path
    ):
        """GET /attachments/{id}/download returns file."""
        token = await self._get_admin_token(client, db_session)
        body = b"\xff\xd8\xff jpeg"
        upload_resp = await client.post(
            "/api/v1/attachments",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("p.jpg", body, "image/jpeg")},
        )
        att_id = upload_resp.json()["data"]["id"]
        response = await client.get(
            f"/api/v1/attachments/{att_id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.content == body


class TestPaymentWithConfirmationAttachment:
    """Test payment create with confirmation_attachment_id (no reference)."""

    async def test_payment_create_with_confirmation_attachment_id(
        self, client: AsyncClient, db_session: AsyncSession, storage_tmp_path
    ):
        """Create payment with only confirmation_attachment_id (no reference text)."""
        from src.modules.students.models import Grade, StudentStatus

        auth = AuthService(db_session)
        user = await auth.create_user(
            email="pay_att@test.com",
            password="Pass123",
            full_name="Pay Att",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.commit()
        _, token, _ = await auth.authenticate("pay_att@test.com", "Pass123")

        grade = Grade(code="G1", name="Grade 1", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.flush()
        student = Student(
            student_number="S1",
            first_name="A",
            last_name="B",
            gender="male",
            grade_id=grade.id,
            guardian_name="G",
            guardian_phone="+254700000000",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add(student)
        await db_session.commit()

        # Upload attachment
        upload_resp = await client.post(
            "/api/v1/attachments",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("proof.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
        assert upload_resp.status_code == 201
        att_id = upload_resp.json()["data"]["id"]

        # Create payment with only confirmation_attachment_id (no reference)
        pay_resp = await client.post(
            "/api/v1/payments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "student_id": student.id,
                "amount": "1000.00",
                "payment_method": "mpesa",
                "payment_date": str(date.today()),
                "confirmation_attachment_id": att_id,
            },
        )
        assert pay_resp.status_code == 201
        pay_data = pay_resp.json()["data"]
        assert pay_data["confirmation_attachment_id"] == att_id
        assert pay_data["reference"] is None
        assert pay_data["status"] == "pending"