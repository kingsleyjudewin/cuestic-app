import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../config/constants.dart';
import '../models/research.dart';
import 'auth_service.dart';

class ResearchService extends ChangeNotifier {
  final AuthService _authService;
  final http.Client _client;

  // Stale-While-Revalidate In-Memory Caches
  List<ResearchTeam>? _cachedTeams;
  List<ResearchStudentProfile>? _cachedDirectory;
  List<ResearchProject>? _cachedProjects;
  List<ResearchMeeting>? _cachedMeetings;
  Map<String, dynamic>? _cachedStudentOverview;
  List<ResearchNotification>? _cachedNotifications;

      
  ResearchService(this._authService, {http.Client? client})
      : _client = client ?? http.Client();

  List<ResearchTeam>? get cachedTeams => _cachedTeams;
  List<ResearchStudentProfile>? get cachedDirectory => _cachedDirectory;
  List<ResearchProject>? get cachedProjects => _cachedProjects;
  List<ResearchMeeting>? get cachedMeetings => _cachedMeetings;
  Map<String, dynamic>? get cachedStudentOverview => _cachedStudentOverview;
  List<ResearchNotification>? get cachedNotifications => _cachedNotifications;

  Future<String> _getBaseUrl() async {
    final configured = await _authService.getConfiguredBaseUrl();
    return configured ?? AppConstants.defaultBaseUrl;
  }

  Map<String, String> _headers() {
    final token = _authService.token ?? '';
    return {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'Authorization': 'Bearer $token',
    };
  }

  void clearCache() {
    _cachedTeams = null;
    _cachedDirectory = null;
    _cachedProjects = null;
    _cachedMeetings = null;
    _cachedStudentOverview = null;
    _cachedNotifications = null;
    notifyListeners();
  }

  // ---------------------------------------------------------------------------
  // Profile & Password Management
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.post(
      Uri.parse('$baseUrl/research/auth/change-password'),
      headers: _headers(),
      body: jsonEncode({
        'current_password': currentPassword,
        'new_password': newPassword,
      }),
    );
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      final user = body['data']['user'] as Map<String, dynamic>;
      await _authService.updateCurrentUser(user);
      return user;
    }
    throw Exception(body['error']?['message'] ?? 'Failed to update password');
  }

  Future<Map<String, dynamic>> setStudentPassword({
    required int studentId,
    required String newPassword,
  }) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.post(
      Uri.parse('$baseUrl/research/students/$studentId/password'),
      headers: _headers(),
      body: jsonEncode({'new_password': newPassword}),
    );
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      return body['data'] as Map<String, dynamic>;
    }
    throw Exception(body['error']?['message'] ?? 'Failed to set student password');
  }

  Future<Map<String, dynamic>> changeFirstLoginPassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.post(
      Uri.parse('$baseUrl/research/auth/first-login-password'),
      headers: _headers(),
      body: jsonEncode({
        'current_password': currentPassword,
        'new_password': newPassword,
      }),
    );
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      final user = body['data']['user'] as Map<String, dynamic>;
      await _authService.updateCurrentUser(user);
      return user;
    }
    throw Exception(body['error']?['message'] ?? 'Failed to update password');
  }

  Future<FacultyProfile> updateFacultyProfile(Map<String, dynamic> data) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.put(
      Uri.parse('$baseUrl/research/faculty/profile'),
      headers: _headers(),
      body: jsonEncode(data),
    );
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      return FacultyProfile.fromJson(body['data']);
    }
    throw Exception(body['error']?['message'] ?? 'Failed to update profile');
  }

  // ---------------------------------------------------------------------------
  // Research Teams
  // ---------------------------------------------------------------------------

  Future<List<ResearchTeam>> getTeams({bool forceRefresh = false}) async {
    final baseUrl = await _getBaseUrl();
    if (!forceRefresh && _cachedTeams != null) {
      _fetchTeamsInBackground(baseUrl);
      return _cachedTeams!;
    }

    final res = await _client.get(Uri.parse('$baseUrl/research/teams'), headers: _headers());
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      final list = (body['data'] as List<dynamic>)
          .map((e) => ResearchTeam.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
      _cachedTeams = list;
            notifyListeners();
      return list;
    }
    throw Exception(body['error']?['message'] ?? 'Failed to fetch teams');
  }

  void _fetchTeamsInBackground(String baseUrl) async {
    try {
      final res = await _client.get(Uri.parse('$baseUrl/research/teams'), headers: _headers());
      if (res.statusCode >= 200 && res.statusCode < 300) {
        final body = jsonDecode(res.body);
        _cachedTeams = (body['data'] as List<dynamic>)
            .map((e) => ResearchTeam.fromJson(Map<String, dynamic>.from(e as Map)))
            .toList();
        notifyListeners();
      }
    } catch (_) {}
  }

  Future<ResearchTeam> createTeam({
    required String name,
    required String domain,
    String? description,
    String? objectives,
    String? tagsJson,
  }) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.post(
      Uri.parse('$baseUrl/research/teams'),
      headers: _headers(),
      body: jsonEncode({
        'name': name,
        'domain': domain,
        'description': description,
        'objectives': objectives,
        'tags_json': tagsJson,
      }),
    );
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      final team = ResearchTeam.fromJson(body['data']);
      _cachedTeams = [team, ...?_cachedTeams];
      notifyListeners();
      return team;
    }
    throw Exception(body['error']?['message'] ?? 'Failed to create team');
  }

  Future<ResearchTeam> getTeamDetails(int teamId) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.get(Uri.parse('$baseUrl/research/teams/$teamId'), headers: _headers());
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      return ResearchTeam.fromJson(body['data']);
    }
    throw Exception(body['error']?['message'] ?? 'Failed to load team details');
  }

  Future<Map<String, dynamic>> addStudentToTeam({
    required int teamId,
    required String fullName,
    required String registrationNumber,
    required String email,
    String? password,
    String programme = 'B.Tech ECE',
    String semester = 'Semester 5',
    String? phoneNumber,
  }) async {
    final baseUrl = await _getBaseUrl();
    final Map<String, dynamic> payload = {
      'full_name': fullName,
      'registration_number': registrationNumber,
      'email': email,
      'programme': programme,
      'semester': semester,
      'phone_number': phoneNumber,
    };
    if (password != null && password.trim().isNotEmpty) {
      payload['password'] = password.trim();
    }
    final res = await _client.post(
      Uri.parse('$baseUrl/research/teams/$teamId/students'),
      headers: _headers(),
      body: jsonEncode(payload),
    );
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      // Invalidate directory cache
      _cachedDirectory = null;
      notifyListeners();
      return body['data'] as Map<String, dynamic>;
    }
    throw Exception(body['error']?['message'] ?? 'Failed to add student');
  }

  Future<void> removeStudentFromTeam(int teamId, int studentId) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.delete(
      Uri.parse('$baseUrl/research/teams/$teamId/students/$studentId'),
      headers: _headers(),
    );
    if (res.statusCode >= 200 && res.statusCode < 300) {
      _cachedDirectory = null;
      notifyListeners();
      return;
    }
    final body = jsonDecode(res.body);
    throw Exception(body['error']?['message'] ?? 'Failed to remove student');
  }

  Future<void> deleteTeam(int teamId) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.delete(
      Uri.parse('$baseUrl/research/teams/$teamId'),
      headers: _headers(),
    );
    if (res.statusCode >= 200 && res.statusCode < 300) {
      _cachedTeams?.removeWhere((t) => t.id == teamId);
      notifyListeners();
      return;
    }
    final body = jsonDecode(res.body);
    throw Exception(body['error']?['message'] ?? 'Failed to delete team');
  }

  // ---------------------------------------------------------------------------
  // Centralized Student Directory
  // ---------------------------------------------------------------------------

  Future<List<ResearchStudentProfile>> getStudentDirectory({
    String? search,
    String? programme,
    String? semester,
    bool forceRefresh = false,
  }) async {
    final baseUrl = await _getBaseUrl();
    if (!forceRefresh && _cachedDirectory != null && search == null && programme == null && semester == null) {
      return _cachedDirectory!;
    }

    final queryParams = <String, String>{};
    if (search != null && search.isNotEmpty) queryParams['search'] = search;
    if (programme != null && programme.isNotEmpty) queryParams['programme'] = programme;
    if (semester != null && semester.isNotEmpty) queryParams['semester'] = semester;

    final uri = Uri.parse('$baseUrl/research/directory').replace(queryParameters: queryParams.isNotEmpty ? queryParams : null);
    final res = await _client.get(uri, headers: _headers());
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      final list = (body['data'] as List<dynamic>)
          .map((e) => ResearchStudentProfile.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
      if (queryParams.isEmpty) {
        _cachedDirectory = list;
              }
      notifyListeners();
      return list;
    }
    throw Exception(body['error']?['message'] ?? 'Failed to load student directory');
  }

  // ---------------------------------------------------------------------------
  // Projects, Milestones & Tasks
  // ---------------------------------------------------------------------------

  Future<List<ResearchProject>> getProjects({int? teamId, String? status, bool forceRefresh = false}) async {
    final baseUrl = await _getBaseUrl();
    if (!forceRefresh && _cachedProjects != null && teamId == null && status == null) {
      return _cachedProjects!;
    }

    final qp = <String, String>{};
    if (teamId != null) qp['team_id'] = teamId.toString();
    if (status != null) qp['status'] = status;
    final uri = Uri.parse('$baseUrl/research/projects').replace(queryParameters: qp.isNotEmpty ? qp : null);
    final res = await _client.get(uri, headers: _headers());
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      final list = (body['data'] as List<dynamic>)
          .map((e) => ResearchProject.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
      if (teamId == null && status == null) {
        _cachedProjects = list;
      }
      notifyListeners();
      return list;
    }
    throw Exception(body['error']?['message'] ?? 'Failed to fetch projects');
  }

  Future<ResearchProject> createProject({
    required int teamId,
    required String title,
    String? researchProblem,
    String? objectives,
    String? description,
    List<int>? assignedStudentIds,
    String? startDate,
    String? expectedCompletionDate,
  }) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.post(
      Uri.parse('$baseUrl/research/projects'),
      headers: _headers(),
      body: jsonEncode({
        'team_id': teamId,
        'title': title,
        'research_problem': researchProblem,
        'objectives': objectives,
        'description': description,
        'assigned_student_ids': assignedStudentIds,
        'start_date': startDate,
        'expected_completion_date': expectedCompletionDate,
      }),
    );
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      final p = ResearchProject.fromJson(body['data']);
      _cachedProjects = [p, ...?_cachedProjects];
      notifyListeners();
      return p;
    }
    throw Exception(body['error']?['message'] ?? 'Failed to create project');
  }

  Future<ResearchProject> getProjectDetails(int projectId) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.get(Uri.parse('$baseUrl/research/projects/$projectId'), headers: _headers());
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      return ResearchProject.fromJson(body['data']);
    }
    throw Exception(body['error']?['message'] ?? 'Failed to load project details');
  }

  Future<ResearchMilestone> createMilestone({
    required int projectId,
    required String title,
    String? description,
    String? targetCriteria,
    String? dueDate,
    String priority = 'Medium',
    List<int>? assignedStudentIds,
  }) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.post(
      Uri.parse('$baseUrl/research/projects/$projectId/milestones'),
      headers: _headers(),
      body: jsonEncode({
        'title': title,
        'description': description,
        'target_criteria': targetCriteria,
        'due_date': dueDate,
        'priority': priority,
        'assigned_student_ids': assignedStudentIds,
      }),
    );
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      return ResearchMilestone.fromJson(body['data']);
    }
    throw Exception(body['error']?['message'] ?? 'Failed to create milestone');
  }

  Future<ResearchTask> createTask({
    required int milestoneId,
    required String title,
    String? instructions,
    String? completionCriteria,
    String? dueDate,
    String priority = 'Medium',
    List<int>? assignedStudentIds,
  }) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.post(
      Uri.parse('$baseUrl/research/milestones/$milestoneId/tasks'),
      headers: _headers(),
      body: jsonEncode({
        'title': title,
        'instructions': instructions,
        'completion_criteria': completionCriteria,
        'due_date': dueDate,
        'priority': priority,
        'assigned_student_ids': assignedStudentIds,
      }),
    );
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      return ResearchTask.fromJson(body['data']);
    }
    throw Exception(body['error']?['message'] ?? 'Failed to create task');
  }

  Future<ResearchTask> updateTaskStatus({
    required int taskId,
    required String status,
    int? progressPercentage,
    String? notes,
  }) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.post(
      Uri.parse('$baseUrl/research/tasks/$taskId/status'),
      headers: _headers(),
      body: jsonEncode({
        'status': status,
        'progress_percentage': progressPercentage,
        'notes': notes,
      }),
    );
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      return ResearchTask.fromJson(body['data']);
    }
    throw Exception(body['error']?['message'] ?? 'Failed to update task status');
  }

  // ---------------------------------------------------------------------------
  // Progress Submissions & Two-Way Feedback
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> submitProgress({
    required int taskId,
    required int progressPercentage,
    int? papersReviewed,
    int? citationsPrepared,
    required String notes,
    String? challenges,
    String? nextSteps,
    List<Map<String, dynamic>>? attachments,
  }) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.post(
      Uri.parse('$baseUrl/research/tasks/$taskId/submissions'),
      headers: _headers(),
      body: jsonEncode({
        'work_completed_percentage': progressPercentage,
        'papers_reviewed_count': papersReviewed,
        'citations_count': citationsPrepared,
        'notes': notes,
        'challenges_faced': challenges,
        'next_steps': nextSteps,
        'attachments': attachments,
      }),
    );
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      return body['data'] as Map<String, dynamic>;
    }
    throw Exception(body['error']?['message'] ?? 'Failed to submit progress');
  }

  Future<Map<String, dynamic>> getFeedbackThread(int taskId) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.get(Uri.parse('$baseUrl/research/tasks/$taskId/thread'), headers: _headers());
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      return body['data'] as Map<String, dynamic>;
    }
    throw Exception(body['error']?['message'] ?? 'Failed to load feedback thread');
  }

  Future<ResearchFeedbackMessage> addFeedbackMessage({
    required int taskId,
    required String message,
    String action = 'comment',
    List<Map<String, dynamic>>? attachments,
  }) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.post(
      Uri.parse('$baseUrl/research/tasks/$taskId/messages'),
      headers: _headers(),
      body: jsonEncode({
        'message': message,
        'action': action,
        'attachments': attachments,
      }),
    );
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      return ResearchFeedbackMessage.fromJson(body['data']);
    }
    throw Exception(body['error']?['message'] ?? 'Failed to send message');
  }

  // ---------------------------------------------------------------------------
  // Meetings Scheduler
  // ---------------------------------------------------------------------------

  Future<List<ResearchMeeting>> getMeetings({bool forceRefresh = false}) async {
    final baseUrl = await _getBaseUrl();
    if (!forceRefresh && _cachedMeetings != null) {
      return _cachedMeetings!;
    }
    final res = await _client.get(Uri.parse('$baseUrl/research/meetings'), headers: _headers());
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      final list = (body['data'] as List<dynamic>)
          .map((e) => ResearchMeeting.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
      _cachedMeetings = list;
      notifyListeners();
      return list;
    }
    throw Exception(body['error']?['message'] ?? 'Failed to fetch meetings');
  }

  Future<ResearchMeeting> scheduleMeeting({
    required String title,
    required String scheduledAt,
    int? teamId,
    String? agenda,
    int durationMinutes = 60,
    String? locationOrLink,
    List<int>? participantStudentIds,
  }) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.post(
      Uri.parse('$baseUrl/research/meetings'),
      headers: _headers(),
      body: jsonEncode({
        'title': title,
        'scheduled_at': scheduledAt,
        'team_id': teamId,
        'agenda': agenda,
        'duration_minutes': durationMinutes,
        'location_or_link': locationOrLink,
        'participant_student_ids': participantStudentIds,
      }),
    );
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      final m = ResearchMeeting.fromJson(body['data']);
      _cachedMeetings = [m, ...?_cachedMeetings];
      notifyListeners();
      return m;
    }
    throw Exception(body['error']?['message'] ?? 'Failed to schedule meeting');
  }

  Future<void> recordAttendance({
    required int meetingId,
    required List<Map<String, dynamic>> attendance,
    String? notes,
  }) async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.post(
      Uri.parse('$baseUrl/research/meetings/$meetingId/attendance'),
      headers: _headers(),
      body: jsonEncode({
        'attendance': attendance,
        'notes': notes,
      }),
    );
    if (res.statusCode >= 200 && res.statusCode < 300) {
      _cachedMeetings = null;
      notifyListeners();
      return;
    }
    final body = jsonDecode(res.body);
    throw Exception(body['error']?['message'] ?? 'Failed to record attendance');
  }

  // ---------------------------------------------------------------------------
  // Student Portal Overview & Notifications
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> getStudentOverview({bool forceRefresh = false}) async {
    final baseUrl = await _getBaseUrl();
    if (!forceRefresh && _cachedStudentOverview != null) {
      return _cachedStudentOverview!;
    }
    final res = await _client.get(Uri.parse('$baseUrl/research/student/overview'), headers: _headers());
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      _cachedStudentOverview = body['data'] as Map<String, dynamic>;
      notifyListeners();
      return _cachedStudentOverview!;
    }
    throw Exception(body['error']?['message'] ?? 'Failed to load student overview');
  }

  Future<List<ResearchNotification>> getNotifications() async {
    final baseUrl = await _getBaseUrl();
    final res = await _client.get(Uri.parse('$baseUrl/research/notifications'), headers: _headers());
    final body = jsonDecode(res.body);
    if (res.statusCode >= 200 && res.statusCode < 300) {
      final list = (body['data'] as List<dynamic>)
          .map((e) => ResearchNotification.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
      _cachedNotifications = list;
      notifyListeners();
      return list;
    }
    throw Exception(body['error']?['message'] ?? 'Failed to load notifications');
  }

  Future<void> markNotificationRead(int notifId) async {
    final baseUrl = await _getBaseUrl();
    await _client.post(Uri.parse('$baseUrl/research/notifications/$notifId/read'), headers: _headers());
  }
}
