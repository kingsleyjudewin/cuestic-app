import pytest
from app.models.device_token import DeviceToken
from app.services.notification_service import NotificationService


def test_register_device_token(client, admin_user):
    headers = admin_user["headers"]
    res = client.post("/api/v1/notifications/device-token", json={
        "token": "test_fcm_token_12345",
        "device_type": "android",
        "device_name": "Test Pixel Device"
    }, headers=headers)

    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["device_type"] == "android"
    assert data["device_name"] == "Test Pixel Device"
    assert data["is_active"] is True

    # Check listing
    res_list = client.get("/api/v1/notifications/devices", headers=headers)
    assert res_list.status_code == 200
    devices = res_list.get_json()["data"]
    assert len(devices) >= 1
    assert any(d["device_name"] == "Test Pixel Device" for d in devices)

    # Deactivate / Unregister
    res_del = client.delete("/api/v1/notifications/device-token", json={
        "token": "test_fcm_token_12345"
    }, headers=headers)
    assert res_del.status_code == 200

    # Device should no longer be active
    res_list_after = client.get("/api/v1/notifications/devices", headers=headers)
    assert not any(d["id"] == data["id"] for d in res_list_after.get_json()["data"])
