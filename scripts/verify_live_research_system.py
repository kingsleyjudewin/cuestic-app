"""
End-to-End Live Verification Script for Faculty Research Management System.
Connects directly to the live running Flask API (http://127.0.0.1:5000)
and validates all flows end-to-end.
"""
import requests
import sys

BASE_URL = "http://127.0.0.1:5000/api/v1"

def test_live_flows():
    print("=== LIVE VERIFICATION: RESEARCH MANAGEMENT SYSTEM ===")

    # 1. Faculty Coordinator initial login (Dr Arunraja A)
    username = "arunraja.a"
    temp_pass = "Research2026!Arunraja"

    print(f"\n[1] Testing login for Faculty Coordinator '{username}'...")
    res = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": temp_pass})
    assert res.status_code == 200, f"Login failed: {res.text}"
    data = res.json()["data"]
    token = data["token"]
    user = data["user"]
    print(f"  -> Logged in successfully. Role: {user['role']}, must_change_password: {user['must_change_password']}")
    assert user["role"] == "faculty_coordinator"
    assert user["must_change_password"] is True

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Mandatory First-Login Password Change
    new_pass = "ArunrajaPermanent2026!Secure"
    print("\n[2] Executing first-login permanent password change...")
    res = requests.post(
        f"{BASE_URL}/research/auth/first-login-password",
        headers=headers,
        json={"current_password": temp_pass, "new_password": new_pass},
    )
    assert res.status_code == 200, f"Password change failed: {res.text}"
    user_updated = res.json()["data"]["user"]
    assert user_updated["must_change_password"] is False
    print(f"  -> Password changed. must_change_password is now: {user_updated['must_change_password']}")

    # 3. Create Research Team
    print("\n[3] Creating Research Team 'Wireless Sensor Networks Group'...")
    res = requests.post(
        f"{BASE_URL}/research/teams",
        headers=headers,
        json={
            "name": "Wireless Sensor Networks Group",
            "domain": "IoT & Sensor Networks",
            "description": "Smart campus mesh networks and low-power protocol development.",
            "objectives": "Deploy 10 LoRaWAN test nodes across Kengeri campus.",
        },
    )
    assert res.status_code == 201, f"Team creation failed: {res.text}"
    team = res.json()["data"]
    team_id = team["id"]
    print(f"  -> Team created: {team['name']} (ID: {team_id})")

    # 4. Add Student to Team
    print("\n[4] Adding Student Researcher 'Vikram Aditya' (2140201)...")
    res = requests.post(
        f"{BASE_URL}/research/teams/{team_id}/students",
        headers=headers,
        json={
            "full_name": "Vikram Aditya",
            "registration_number": "2140201",
            "email": "vikram.aditya@christuniversity.in",
            "programme": "B.Tech ECE",
            "semester": "Semester 6",
        },
    )
    assert res.status_code == 201, f"Add student failed: {res.text}"
    student_res = res.json()["data"]
    student_id = student_res["student"]["id"]
    student_user_id = student_res["student"]["user_id"]
    temp_student_pass = student_res.get("temporary_password")
    print(f"  -> Student added: ID {student_id}, Temp Password: {temp_student_pass}")

    # 5. Create Project under Team
    print("\n[5] Creating Project 'LoRaWAN Campus Node Deployment'...")
    res = requests.post(
        f"{BASE_URL}/research/projects",
        headers=headers,
        json={
            "team_id": team_id,
            "title": "LoRaWAN Campus Node Deployment",
            "research_problem": "Propagation loss and coverage in multi-story university buildings.",
            "objectives": "Analyze packet error rates and optimize gateway placement.",
            "assigned_student_ids": [student_id],
            "start_date": "2026-11-01T00:00:00Z",
            "expected_completion_date": "2026-12-20T00:00:00Z",
        },
    )
    assert res.status_code == 201, f"Project creation failed: {res.text}"
    project = res.json()["data"]
    project_id = project["id"]
    print(f"  -> Project created: {project['title']} (ID: {project_id})")

    # 6. Create Milestone & Task
    print("\n[6] Creating Milestone and Task...")
    res = requests.post(
        f"{BASE_URL}/research/projects/{project_id}/milestones",
        headers=headers,
        json={
            "title": "Phase 1: Transceiver Calibration",
            "target_criteria": "Calibrate RSSI sensitivity on SX1262 transceivers.",
            "priority": "high",
            "due_date": "2026-11-12T18:00:00Z",
            "assigned_student_ids": [student_id],
        },
    )
    assert res.status_code == 201, f"Milestone creation failed: {res.text}"
    milestone_id = res.json()["data"]["id"]

    res = requests.post(
        f"{BASE_URL}/research/milestones/{milestone_id}/tasks",
        headers=headers,
        json={
            "title": "Measure RSSI vs Distance on Open Ground",
            "instructions": "Log RSSI values from 10m to 500m line of sight in CSV.",
            "completion_criteria": "CSV dataset and scatter plot graph.",
            "priority": "high",
            "due_date": "2026-11-09T18:00:00Z",
            "assigned_student_ids": [student_id],
        },
    )
    assert res.status_code == 201, f"Task creation failed: {res.text}"
    task = res.json()["data"]
    task_id = task["id"]
    print(f"  -> Task created: {task['title']} (ID: {task_id})")

    # 7. Check Centralized Student Directory
    print("\n[7] Querying Centralized Student Directory...")
    res = requests.get(f"{BASE_URL}/research/directory", headers=headers)
    assert res.status_code == 200, f"Directory query failed: {res.text}"
    directory = res.json()["data"]
    print(f"  -> Student directory returned {len(directory)} unique student profiles.")
    assert any(s["registration_number"] == "2140201" for s in directory)

    # 8. Student Researcher Login & Progress Update
    student_username = f"res_vikram_2140201"
    print(f"\n[8] Logging in as Student Researcher '{student_username}'...")
    res = requests.post(f"{BASE_URL}/auth/login", json={"username": student_username, "password": temp_student_pass})
    assert res.status_code == 200, f"Student login failed: {res.text}"
    s_token = res.json()["data"]["token"]
    s_headers = {"Authorization": f"Bearer {s_token}"}

    print("  -> Submitting progress update (70%)...")
    res = requests.post(
        f"{BASE_URL}/research/tasks/{task_id}/submissions",
        headers=s_headers,
        json={
            "work_completed_percentage": 70,
            "papers_reviewed_count": 6,
            "citations_count": 4,
            "notes": "Completed line-of-sight measurements up to 350m on the sports field.",
            "challenges_faced": "Encountered packet drops past 400m near concrete water tank.",
            "next_steps": "Test with higher gain 5dBi omnidirectional antenna.",
        },
    )
    assert res.status_code == 201, f"Student submission failed: {res.text}"
    print("  -> Progress successfully submitted for review.")

    # 9. Faculty Two-Way Continuous Feedback & Approval
    print("\n[9] Faculty viewing feedback thread and approving...")
    res = requests.get(f"{BASE_URL}/research/tasks/{task_id}/thread", headers=headers)
    assert res.status_code == 200
    thread = res.json()["data"]
    print(f"  -> Thread loaded: {len(thread['messages'])} messages, Task status: {thread['task_status']}")
    assert thread["task_status"] == "submitted_for_review"

    res = requests.post(
        f"{BASE_URL}/research/tasks/{task_id}/messages",
        headers=headers,
        json={
            "message": "Excellent measurement dataset Vikram. Approved to proceed with 5dBi antenna tests.",
            "action": "approve",
        },
    )
    assert res.status_code == 201
    print("  -> Faculty approved work. Task status is now 'approved'.")

    # 10. Schedule Meeting
    print("\n[10] Scheduling Research Review Meeting...")
    res = requests.post(
        f"{BASE_URL}/research/meetings",
        headers=headers,
        json={
            "team_id": team_id,
            "title": "LoRaWAN Transceiver Test Review",
            "agenda": "Review packet loss data and finalize antenna specifications.",
            "scheduled_at": "2026-11-06T15:00:00Z",
            "duration_minutes": 45,
            "location_or_link": "Communications Lab 102",
            "participant_student_ids": [student_id],
        },
    )
    assert res.status_code == 201, f"Meeting scheduling failed: {res.text}"
    meeting = res.json()["data"]
    print(f"  -> Meeting scheduled: '{meeting['title']}' at {meeting['scheduled_at']}")

    print("\n=== ALL LIVE END-TO-END VERIFICATION CHECKS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    test_live_flows()
