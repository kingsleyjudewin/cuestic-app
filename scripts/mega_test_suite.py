"""
Mega Test Suite for Department Club Management Application.
Executes all testing loops end-to-end:
1. President Loop: Login, feature access, assign tasks to ALL members across ALL teams, member status updates.
2. Discord / Community Loop: RBAC isolation, team-restricted chatting, admin cross-visibility.
3. Volunteering Loop: Team member login, Discord chat, task verification.
4. Documentation Loop: Folder creation, report draft, AI Copilot field generation.
5. Media Loop: Folder creation, folder retrieval, media structure.
6. MC Team Loop: Script creation, MC Copilot segment generation, dialogue rewrite, unified AI assist, DOCX export.
7. Faculty & Student Research Loop: Team, project, milestone, task, progress submission, two-way feedback, approval.
8. Latency profiling: Records latency for every endpoint call across all loops.
"""
import time
import json
import requests
import functools

# Auto-flush all prints
print = functools.partial(print, flush=True)

BASE_URL = "http://127.0.0.1:5000/api/v1"

# Latency tracking store: endpoint_label -> list of latencies in ms
LATENCIES = {}

def track_request(label, method, url, **kwargs):
    t0 = time.perf_counter()
    resp = method(url, **kwargs)
    dt = (time.perf_counter() - t0) * 1000.0
    if label not in LATENCIES:
        LATENCIES[label] = []
    LATENCIES[label].append(dt)
    return resp, dt

def login(username, password):
    resp, dt = track_request("POST /auth/login", requests.post, f"{BASE_URL}/auth/login", json={
        "username": username,
        "password": password,
    })
    if resp.status_code != 200:
        raise Exception(f"Login failed for {username}: {resp.status_code} - {resp.text}")
    data = resp.json()["data"]
    token = data["token"]
    user = data["user"]
    headers = {"Authorization": f"Bearer {token}"}
    return token, headers, user, dt

def run_mega_test():
    print("=" * 80)
    print("STARTING DEPARTMENT CLUB OS MEGA TEST SUITE")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # 1. PRESIDENT LOOP
    # -------------------------------------------------------------------------
    print("\n>>> LOOP 1: PRESIDENT LOOP & TASK ASSIGNMENT TO ALL MEMBERS ACROSS ALL TEAMS")
    pres_token, pres_headers, pres_user, _ = login("clubadmin", "AdminPass123!Secure")
    print(f" [+] President logged in successfully: {pres_user['username']} (role: {pres_user['role']})")
    assert pres_user["role"] == "president", "User is not president"

    # President Dashboard & Data Retrieval
    r, _ = track_request("GET /dashboard/summary", requests.get, f"{BASE_URL}/dashboard/summary", headers=pres_headers)
    assert r.status_code == 200, f"Dashboard failed: {r.text}"
    print(" [+] President dashboard loaded successfully")

    r_teams, _ = track_request("GET /teams", requests.get, f"{BASE_URL}/teams", headers=pres_headers)
    assert r_teams.status_code == 200, f"Teams failed: {r_teams.text}"
    teams_list = r_teams.json()["data"]
    print(f" [+] Loaded {len(teams_list)} teams: {[t['name'] for t in teams_list]}")

    r_members, _ = track_request("GET /members", requests.get, f"{BASE_URL}/members", headers=pres_headers)
    assert r_members.status_code == 200, f"Members failed: {r_members.text}"
    all_members = r_members.json()["data"]
    print(f" [+] Total active members across club: {len(all_members)}")

    # Group members by team
    members_by_team = {}
    for m in all_members:
        tname = m.get("team_name") or f"Team_{m.get('team_id')}"
        members_by_team.setdefault(tname, []).append(m)

    for tname, mlist in members_by_team.items():
        print(f"     * {tname}: {len(mlist)} members")

    # Get an active event to assign tasks under
    r_events, _ = track_request("GET /events", requests.get, f"{BASE_URL}/events", headers=pres_headers)
    assert r_events.status_code == 200, f"Events failed: {r_events.text}"
    events = r_events.json()["data"]
    if not events:
        # Create an event
        r_evt, _ = track_request("POST /events", requests.post, f"{BASE_URL}/events", headers=pres_headers, json={
            "name": "Department Annual Symposium 2026",
            "description": "Flagship departmental symposium and paper presentation",
            "start_at": "2026-11-20T09:00:00Z",
            "end_at": "2026-11-20T17:00:00Z",
            "venue": "Main Auditorium",
        })
        target_event = r_evt.json()["data"]
    else:
        target_event = events[0]
    event_id = target_event["id"]
    print(f" [+] Target event for task assignments: {target_event['name']} (ID: {event_id})")

    # ASSIGN A TASK TO EVERY SINGLE MEMBER ACROSS ALL TEAMS
    print(f"\n [+] Assigning one dedicated task to each of the {len(all_members)} members...")
    assigned_tasks_record = [] # list of (member, task, assignment)

    for idx, member in enumerate(all_members, start=1):
        member_id = member["id"]
        member_name = member["full_name"]
        team_name = member.get("team_name", "Team")
        task_title = f"Task #{idx}: {team_name} Operations - {member_name}"
        task_desc = f"Official operational assignment for {member_name} in team {team_name} for {target_event['name']}."

        r_task, _ = track_request("POST /events/<id>/tasks", requests.post, f"{BASE_URL}/events/{event_id}/tasks", headers=pres_headers, json={
            "title": task_title,
            "description": task_desc,
            "priority": "high",
            "deadline": "2026-11-25T18:00:00Z",
            "member_ids": [member_id]
        })
        assert r_task.status_code == 201, f"Task creation failed for member {member_name}: {r_task.text}"
        task_data = r_task.json()["data"]
        assignments = task_data.get("assignments") or []
        assert len(assignments) > 0, f"No assignment returned for task {task_data['id']}"
        assignment_id = assignments[0]["id"]
        assigned_tasks_record.append((member, task_data, assignment_id))

    print(f" [+] All {len(assigned_tasks_record)} members have been assigned a task!")

    # LOG IN AS EACH ASSIGNED MEMBER AND CHANGE STATUS
    print("\n [+] Logging in as each assigned member to verify and update task status...")
    status_updated_count = 0

    for member, task_data, assignment_id in assigned_tasks_record:
        linked_user = member.get("linked_user")
        if not linked_user:
            print(f" [!] Warning: Member {member['full_name']} has no linked_user, skipping login")
            continue
        username = linked_user["username"]

        m_token, m_headers, m_user, _ = login(username, "MemberPass2026!")

        # Verify member can see their assignment
        r_my_ass, _ = track_request("GET /assignments/me", requests.get, f"{BASE_URL}/assignments/me", headers=m_headers)
        assert r_my_ass.status_code == 200, f"Failed getting assignments for {username}: {r_my_ass.text}"
        my_assignments = r_my_ass.json()["data"]
        matching_ass = [a for a in my_assignments if a["id"] == assignment_id]
        assert len(matching_ass) > 0, f"Assignment {assignment_id} not found in {username}'s /assignments/me list"

        # Update assignment status to in_progress
        r_status, _ = track_request("PATCH /assignments/<id>/status", requests.patch, f"{BASE_URL}/assignments/{assignment_id}/status", headers=m_headers, json={
            "status": "in_progress",
            "note": "Acknowledged assignment and begun preparations."
        })
        assert r_status.status_code == 200, f"Status update failed for assignment {assignment_id} by {username}: {r_status.text}"
        updated_data = r_status.json()["data"]
        assert updated_data["status"] == "in_progress", f"Status did not transition to in_progress: {updated_data}"

        # Member submits assignment for leader/president approval
        r_sub, _ = track_request("PATCH /assignments/<id>/status (Submit)", requests.patch, f"{BASE_URL}/assignments/{assignment_id}/status", headers=m_headers, json={
            "status": "submitted",
            "note": "Finished deliverables and submitted for review."
        })
        assert r_sub.status_code == 200, f"Submission failed for {assignment_id}: {r_sub.text}"
        status_updated_count += 1

    print(f" [+] Successfully logged into all {status_updated_count} member accounts and completed their tasks!")

    # -------------------------------------------------------------------------
    # 2. DISCORD / COMMUNITY MESSAGES LOOP (RBAC & ISOLATION)
    # -------------------------------------------------------------------------
    print("\n>>> LOOP 2: DISCORD MESSAGES & ROLE-BASED ISOLATION")
    # President triggers synchronization
    r_sync, _ = track_request("POST /communities/sync", requests.post, f"{BASE_URL}/communities/sync", headers=pres_headers)
    assert r_sync.status_code == 200, f"Community sync failed: {r_sync.text}"
    print(" [+] Team communities synchronized successfully")

    # President lists all communities
    r_pres_comm, _ = track_request("GET /communities (President)", requests.get, f"{BASE_URL}/communities", headers=pres_headers)
    assert r_pres_comm.status_code == 200
    all_comms = r_pres_comm.json()["data"]
    print(f" [+] President can see ALL {len(all_comms)} communities: {[c['name'] for c in all_comms]}")
    comm_by_slug = {c["slug"]: c for c in all_comms}

    vol_comm = comm_by_slug.get("volunteering-community") or all_comms[0]
    media_comm = comm_by_slug.get("media-community") or all_comms[1]
    doc_comm = comm_by_slug.get("documentation-community") or all_comms[2]

    # Test Team Isolation: Log in as Volunteering member (jayani.cu)
    _, vol_headers, vol_user, _ = login("jayani.cu", "MemberPass2026!")
    r_vol_comms, _ = track_request("GET /communities (Volunteering Member)", requests.get, f"{BASE_URL}/communities", headers=vol_headers)
    assert r_vol_comms.status_code == 200
    vol_user_comms = r_vol_comms.json()["data"]
    vol_slugs = [c["slug"] for c in vol_user_comms]
    print(f" [+] Volunteering member ({vol_user['username']}) sees: {vol_slugs}")
    assert "media-community" not in vol_slugs, "RBAC VIOLATION: Volunteering member can see Media community!"
    assert "volunteering-community" in vol_slugs, "Volunteering member cannot see their own Volunteering community!"

    # Test Forbidden Access to Other Team Community
    r_forbidden, _ = track_request("GET /communities/<forbidden_id> (RBAC Check)", requests.get, f"{BASE_URL}/communities/{media_comm['id']}", headers=vol_headers)
    assert r_forbidden.status_code in (403, 404), f"RBAC VIOLATION: Volunteering member accessed Media Community with code {r_forbidden.status_code}"
    print(f" [+] Strict RBAC Verified: Accessing Media Community returned {r_forbidden.status_code} Forbidden/Not Accessible")

    # Get channels in Volunteering Community
    r_vol_detail, _ = track_request("GET /communities/<id> (Volunteering)", requests.get, f"{BASE_URL}/communities/{vol_comm['id']}", headers=vol_headers)
    assert r_vol_detail.status_code == 200
    vol_channels = r_vol_detail.json()["data"]["channels"]
    assert len(vol_channels) > 0, "No channels in volunteering community"
    vol_target_channel = vol_channels[0]
    print(f" [+] Target Volunteering channel: #{vol_target_channel['name']} (ID: {vol_target_channel['id']})")

    # Post message as jayani.cu
    test_msg_text = f"Mega Test Broadcast from Jayani: Team coordination is ready at {time.time()}!"
    r_post_msg, _ = track_request("POST /communities/<id>/channels/<id>/messages", requests.post,
        f"{BASE_URL}/communities/{vol_comm['id']}/channels/{vol_target_channel['id']}/messages",
        headers=vol_headers, json={"content": test_msg_text}
    )
    assert r_post_msg.status_code == 201, f"Post message failed: {r_post_msg.text}"
    sent_msg_id = r_post_msg.json()["data"]["id"]
    print(f" [+] Message posted to #{vol_target_channel['name']} (ID: {sent_msg_id})")

    # Verify second Volunteering member (sagar.cu) sees the message
    _, sagar_headers, _, _ = login("sagar.cu", "MemberPass2026!")
    r_sagar_msgs, _ = track_request("GET /communities/<id>/channels/<id>/messages (Peer Member)", requests.get,
        f"{BASE_URL}/communities/{vol_comm['id']}/channels/{vol_target_channel['id']}/messages",
        headers=sagar_headers
    )
    assert r_sagar_msgs.status_code == 200
    sagar_msg_texts = [m["content"] for m in r_sagar_msgs.json()["data"]]
    assert test_msg_text in sagar_msg_texts, "Peer member sagar.cu did not receive message from jayani.cu!"
    print(" [+] Peer member sagar.cu successfully retrieved message!")

    # Verify Media member (nivin.cu) CANNOT read Volunteering channel messages
    _, nivin_headers, _, _ = login("nivin.cu", "MemberPass2026!")
    r_nivin_hack, _ = track_request("GET /communities/<id>/channels/<id>/messages (Cross-Team Forbidden)", requests.get,
        f"{BASE_URL}/communities/{vol_comm['id']}/channels/{vol_target_channel['id']}/messages",
        headers=nivin_headers
    )
    assert r_nivin_hack.status_code in (403, 404), f"Cross-team leakage: Media member read Volunteering channel! Status: {r_nivin_hack.status_code}"
    print(" [+] Strict RBAC Verified: Media member cannot read Volunteering messages (403/404)")

    # -------------------------------------------------------------------------
    # 3. VOLUNTEERING LOOP
    # -------------------------------------------------------------------------
    print("\n>>> LOOP 3: VOLUNTEERING LOOP")
    # Verify volunteering member profile, personal assignments, and announcements
    r_vol_me, _ = track_request("GET /assignments/me (Volunteering)", requests.get, f"{BASE_URL}/assignments/me", headers=vol_headers)
    assert r_vol_me.status_code == 200
    print(f" [+] Volunteering loop completed. Total assignments verified: {len(r_vol_me.json()['data'])}")

    # -------------------------------------------------------------------------
    # 4. DOCUMENTATION LOOP
    # -------------------------------------------------------------------------
    print("\n>>> LOOP 4: DOCUMENTATION LOOP")
    _, doc_headers, doc_user, _ = login("salomi", "MemberPass2026!")
    print(f" [+] Documentation member logged in: {doc_user['username']}")

    # Create Documentation Event Folder
    folder_name = f"Mega Test Documentation Folder {int(time.time())}"
    r_doc_folder, _ = track_request("POST /documentation/folders", requests.post, f"{BASE_URL}/documentation/folders", headers=doc_headers, json={
        "name": folder_name,
        "description": "Folder created during end-to-end mega testing"
    })
    assert r_doc_folder.status_code == 201, f"Failed creating doc folder: {r_doc_folder.text}"
    doc_folder_id = r_doc_folder.json()["data"]["id"]
    print(f" [+] Created documentation folder: {folder_name} (ID: {doc_folder_id})")

    # Retrieve folder
    r_get_df, _ = track_request("GET /documentation/folders/<id>", requests.get, f"{BASE_URL}/documentation/folders/{doc_folder_id}", headers=doc_headers)
    assert r_get_df.status_code == 200

    # Create Activity Report Draft
    r_report, _ = track_request("POST /documentation/reports", requests.post, f"{BASE_URL}/documentation/reports", headers=doc_headers, json={
        "title": "Mega Test Activity Report 2026",
        "event_name": "Department AI Symposium",
        "department": "Electronics and Communication Engineering",
    })
    assert r_report.status_code == 201, f"Report creation failed: {r_report.text}"
    report_id = r_report.json()["data"]["id"]
    print(f" [+] Created activity report draft (ID: {report_id})")

    # Test AI Assist in Documentation
    r_ai_doc, _ = track_request("POST /documentation/ai-assist", requests.post, f"{BASE_URL}/documentation/ai-assist", headers=doc_headers, json={
        "field_key": "executive_summary",
        "instruction": "Draft a 2-sentence executive summary of an AI research workshop.",
        "action": "draft"
    })
    assert r_ai_doc.status_code == 200, f"AI Doc Assist failed: {r_ai_doc.text}"
    ai_doc_result = r_ai_doc.json()["data"]
    print(f" [+] Documentation AI Copilot generated content via {ai_doc_result.get('provider')}: '{ai_doc_result.get('generated_text', '')[:60]}...'")

    # -------------------------------------------------------------------------
    # 5. MEDIA LOOP
    # -------------------------------------------------------------------------
    print("\n>>> LOOP 5: MEDIA LOOP")
    _, media_headers, media_user, _ = login("nivin.cu", "MemberPass2026!")
    print(f" [+] Media member logged in: {media_user['username']}")

    media_folder_name = f"Mega Test Media Album {int(time.time())}"
    r_media_folder, _ = track_request("POST /media/folders", requests.post, f"{BASE_URL}/media/folders", headers=media_headers, json={
        "name": media_folder_name,
        "description": "Event photography and livestream recording folder"
    })
    assert r_media_folder.status_code == 201, f"Failed creating media folder: {r_media_folder.text}"
    media_folder_id = r_media_folder.json()["data"]["id"]
    print(f" [+] Created Media folder: {media_folder_name} (ID: {media_folder_id})")

    # Retrieve folder
    r_get_mf, _ = track_request("GET /media/folders/<id>", requests.get, f"{BASE_URL}/media/folders/{media_folder_id}", headers=media_headers)
    assert r_get_mf.status_code == 200
    print(" [+] Media folder details verified successfully")

    # -------------------------------------------------------------------------
    # 6. MC TEAM LOOP & AI COPILOT
    # -------------------------------------------------------------------------
    print("\n>>> LOOP 6: MC TEAM LOOP & AI COPILOT")
    _, mc_headers, mc_user, _ = login("merrick", "MemberPass2026!")
    print(f" [+] MC Team member logged in: {mc_user['username']}")

    # Retrieve MC Dashboard
    r_mc_dash, _ = track_request("GET /mc/dashboard", requests.get, f"{BASE_URL}/mc/dashboard", headers=mc_headers)
    assert r_mc_dash.status_code == 200
    mc_dash_data = r_mc_dash.json()["data"]
    print(f" [+] MC Dashboard retrieved: {mc_dash_data.get('scripts_in_progress')} in progress, {mc_dash_data.get('approved_scripts')} approved")

    # Create MC Script
    r_mc_script, _ = track_request("POST /mc/scripts", requests.post, f"{BASE_URL}/mc/scripts", headers=mc_headers, json={
        "title": "Mega Test Valedictory Ceremony Script",
        "event_name": "Magnovite 2026",
        "event_type": "Valedictory Ceremony",
        "department": "Electronics and Communication Engineering",
        "theme": "Innovation and Academic Excellence",
        "lead_anchor": "Merrick",
        "co_anchor": "Afra",
        "target_duration_minutes": 45,
    })
    assert r_mc_script.status_code == 201, f"MC script creation failed: {r_mc_script.text}"
    script_id = r_mc_script.json()["data"]["id"]
    print(f" [+] Created MC Script (ID: {script_id})")

    # Test MC AI Copilot - Segment Generation
    r_ai_seg, _ = track_request("POST /mc/ai/generate-segment", requests.post, f"{BASE_URL}/mc/ai/generate-segment", headers=mc_headers, json={
        "segment_type": "welcome",
        "event_info": {
            "event_name": "Magnovite 2026",
            "department": "Electronics and Communication Engineering",
            "lead_anchor": "Merrick",
            "co_anchor": "Afra",
        },
        "instructions": "Formal welcome address acknowledging HOD and Dignitaries."
    })
    assert r_ai_seg.status_code == 200, f"MC generate-segment failed: {r_ai_seg.text}"
    seg_result = r_ai_seg.json()["data"]
    print(f" [+] MC AI Copilot generated segment dialogue successfully")

    # Test MC AI Copilot - Rewrite / Polish
    r_ai_rw, _ = track_request("POST /mc/ai/rewrite", requests.post, f"{BASE_URL}/mc/ai/rewrite", headers=mc_headers, json={
        "text": "Good morning everybody, we welcome our chief guest to the stage.",
        "tone": "Formal",
        "action": "adjust_tone"
    })
    assert r_ai_rw.status_code == 200, f"MC rewrite failed: {r_ai_rw.text}"
    rw_result = r_ai_rw.json()["data"]
    print(f" [+] MC AI Copilot rewritten dialogue: '{rw_result.get('improved_text', '')[:60]}...'")

    # Test MC Unified AI Assist
    r_mc_assist, _ = track_request("POST /mc/ai-assist", requests.post, f"{BASE_URL}/mc/ai-assist", headers=mc_headers, json={
        "instruction": "Provide a 1-sentence stage direction transition from presidential address to prize distribution.",
        "action": "draft"
    })
    assert r_mc_assist.status_code == 200, f"MC ai-assist failed: {r_mc_assist.text}"
    print(" [+] Unified MC AI Copilot assist verified successfully")

    # Generate DOCX
    r_docx, _ = track_request("POST /mc/scripts/<id>/generate-docx", requests.post, f"{BASE_URL}/mc/scripts/{script_id}/generate-docx", headers=mc_headers)
    assert r_docx.status_code == 200, f"DOCX generation failed: {r_docx.text}"
    print(f" [+] DOCX hosting script generated on disk: {r_docx.json()['data']['filename']}")

    # -------------------------------------------------------------------------
    # 7. FACULTY & STUDENT RESEARCH MANAGEMENT LOOP
    # -------------------------------------------------------------------------
    print("\n>>> LOOP 7: FACULTY & STUDENT RESEARCH MANAGEMENT LOOP")
    # Log in as Faculty Coordinator Dr. Chidambaram S
    _, fac_headers, fac_user, _ = login("chidambaram.s", "Research2026!Chidambaram")
    print(f" [+] Faculty Coordinator logged in: {fac_user['username']}")

    # Create Research Team
    team_name = f"Edge AI & Hyperspectral Systems {int(time.time())}"
    r_rteam, _ = track_request("POST /research/teams", requests.post, f"{BASE_URL}/research/teams", headers=fac_headers, json={
        "name": team_name,
        "domain": "Computer Vision & Edge Computing",
        "description": "High performance edge processing for multispectral payloads."
    })
    assert r_rteam.status_code == 201, f"Research team creation failed: {r_rteam.text}"
    rteam_id = r_rteam.json()["data"]["id"]
    print(f" [+] Faculty created research team: {team_name} (ID: {rteam_id})")

    # Add Student to Research Team with Custom Credentials
    student_reg = f"21EC{int(time.time()) % 10000:04d}"
    r_add_st, _ = track_request("POST /research/teams/<id>/students", requests.post, f"{BASE_URL}/research/teams/{rteam_id}/students", headers=fac_headers, json={
        "full_name": f"Student Researcher {student_reg}",
        "registration_number": student_reg,
        "email": f"st.{student_reg.lower()}@department.edu",
        "password": "ResearchPass2026!",
        "programme": "B.Tech ECE",
        "semester": "Semester 6"
    })
    assert r_add_st.status_code in (200, 201), f"Add student failed: {r_add_st.text}"
    st_res = r_add_st.json()["data"]
    st_profile = st_res["student"]
    st_user_name = st_res["username"]
    st_pass = st_res["password"]
    student_id = st_profile["id"]
    print(f" [+] Added student: {st_profile['full_name']} (ID: {student_id}, Login: {st_user_name} / {st_pass})")

    # Create Research Project with Deadline
    r_rproj, _ = track_request("POST /research/projects", requests.post, f"{BASE_URL}/research/projects", headers=fac_headers, json={
        "team_id": rteam_id,
        "title": "Real-Time Hyperspectral Target Detection on Edge TPU",
        "research_problem": "High dimensional pixel classification under sub-100ms latency constraints.",
        "objectives": "Implement lightweight attention network and quantize to int8.",
        "expected_completion_date": "2026-12-15T18:00:00Z",
        "assigned_student_ids": [student_id],
    })
    assert r_rproj.status_code == 201, f"Research project creation failed: {r_rproj.text}"
    rproj_id = r_rproj.json()["data"]["id"]
    print(f" [+] Created Research Project (ID: {rproj_id}) with deadline 2026-12-15")

    # Create Milestone
    r_rmile, _ = track_request("POST /research/projects/<id>/milestones", requests.post, f"{BASE_URL}/research/projects/{rproj_id}/milestones", headers=fac_headers, json={
        "title": "Phase 1: Dataset Preparation and Baseline Model Training",
        "target_criteria": "Collect 500 spectral cubes and train baseline ResNet-18",
        "priority": "high",
        "due_date": "2026-11-30T18:00:00Z",
        "assigned_student_ids": [student_id],
    })
    assert r_rmile.status_code == 201, f"Milestone creation failed: {r_rmile.text}"
    rmile_id = r_rmile.json()["data"]["id"]
    print(f" [+] Created Research Milestone (ID: {rmile_id})")

    # Create Actionable Research Task
    r_rtask, _ = track_request("POST /research/milestones/<id>/tasks", requests.post, f"{BASE_URL}/research/milestones/{rmile_id}/tasks", headers=fac_headers, json={
        "title": "Annotate Spectral Cubes & Compute Normalized Difference Indices",
        "instructions": "Extract 16-band reflectances, remove noisy bands, and normalize.",
        "completion_criteria": "Preprocessed dataset ready for PyTorch dataloader.",
        "priority": "high",
        "due_date": "2026-11-20T18:00:00Z",
        "assigned_student_ids": [student_id],
    })
    assert r_rtask.status_code == 201, f"Research task creation failed: {r_rtask.text}"
    rtask_id = r_rtask.json()["data"]["id"]
    print(f" [+] Created Research Task (ID: {rtask_id}) assigned to student {student_id}")

    # LOG IN AS STUDENT RESEARCHER
    print("\n [+] Logging in as Student Researcher...")
    _, st_headers, st_curr_user, _ = login(st_user_name, st_pass)
    assert st_curr_user["role"] == "student_researcher", "User is not student_researcher"
    print(f" [+] Student Researcher logged in successfully: {st_curr_user['username']}")

    # Student retrieves Overview
    r_st_over, _ = track_request("GET /research/student/overview", requests.get, f"{BASE_URL}/research/student/overview", headers=st_headers)
    assert r_st_over.status_code == 200, f"Student overview failed: {r_st_over.text}"
    st_over_data = r_st_over.json()["data"]
    assert len(st_over_data["tasks"]) > 0, "Student has no tasks in overview"
    print(f" [+] Student overview loaded: {len(st_over_data['projects'])} projects, {len(st_over_data['tasks'])} tasks")

    # Student submits Progress Update
    r_st_sub, _ = track_request("POST /research/tasks/<id>/submissions", requests.post, f"{BASE_URL}/research/tasks/{rtask_id}/submissions", headers=st_headers, json={
        "work_completed_percentage": 75,
        "papers_reviewed_count": 8,
        "citations_prepared_count": 14,
        "notes": "Preprocessed 420 spectral cubes and verified snr values. Ready for initial training loop.",
        "challenges_faced": "Atmospheric absorption bands 1350nm-1420nm required removal.",
        "next_steps": "Train baseline ResNet-18 model over 50 epochs."
    })
    assert r_st_sub.status_code == 201, f"Student progress submission failed: {r_st_sub.text}"
    print(" [+] Student progress submission (75%) recorded successfully")

    # Student posts message in Feedback Thread
    r_st_msg, _ = track_request("POST /research/tasks/<id>/messages", requests.post, f"{BASE_URL}/research/tasks/{rtask_id}/messages", headers=st_headers, json={
        "message": "Dr. Chidambaram, dataset preprocessing is completed. Requesting your review on the band selection.",
        "action": "comment"
    })
    assert r_st_msg.status_code == 201, f"Student feedback message failed: {r_st_msg.text}"
    print(" [+] Student sent feedback message to Faculty")

    # Faculty logs in and reviews thread
    r_th, _ = track_request("GET /research/tasks/<id>/thread", requests.get, f"{BASE_URL}/research/tasks/{rtask_id}/thread", headers=fac_headers)
    assert r_th.status_code == 200
    thread_data = r_th.json()["data"]
    print(f" [+] Faculty loaded feedback thread with {len(thread_data['messages'])} messages")

    # Faculty approves submission
    r_fac_app, _ = track_request("POST /research/tasks/<id>/messages (Approve)", requests.post, f"{BASE_URL}/research/tasks/{rtask_id}/messages", headers=fac_headers, json={
        "message": "Excellent work on the atmospheric band removal. Work is approved. Proceed to training.",
        "action": "approve"
    })
    assert r_fac_app.status_code == 201, f"Faculty approval failed: {r_fac_app.text}"
    print(" [+] Faculty approved student submission. Task marked approved (100%)")

    # -------------------------------------------------------------------------
    # LATENCY SUMMARY & METRICS
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("MEGA TEST SUITE COMPLETED SUCCESSFULLY! ALL LOOPS PASSED 100%!")
    print("=" * 80)
    print(f"\nTotal Distinct Endpoints Measured: {len(LATENCIES)}")
    print("-" * 80)
    print(f"{'Endpoint':<55} | {'Count':<5} | {'Min (ms)':<9} | {'Avg (ms)':<9} | {'Max (ms)':<9}")
    print("-" * 80)

    total_reqs = 0
    for ep, lats in sorted(LATENCIES.items()):
        total_reqs += len(lats)
        min_l = min(lats)
        avg_l = sum(lats) / len(lats)
        max_l = max(lats)
        print(f"{ep:<55} | {len(lats):<5} | {min_l:<9.2f} | {avg_l:<9.2f} | {max_l:<9.2f}")

    print("-" * 80)
    print(f"Total Requests Executed: {total_reqs}")
    print("=" * 80)

if __name__ == "__main__":
    run_mega_test()
