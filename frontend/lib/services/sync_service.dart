import 'package:flutter/foundation.dart';
import '../models/event.dart';
import '../models/team.dart';
import '../models/member.dart';
import '../models/task.dart';
import '../models/assignment.dart';
import '../models/message_draft.dart';
import 'api_client.dart';
import 'storage_service.dart';

class SyncService extends ChangeNotifier {
  final ApiClient apiClient;
  final StorageService storageService;

  bool _isOffline = false;
  bool get isOffline => _isOffline;

  SyncService({
    required this.apiClient,
    required this.storageService,
  });


  void setOffline(bool offline) {
    if (_isOffline != offline) {
      _isOffline = offline;
      notifyListeners();
    }
  }

  // --- Screen 1: Events ---
  Future<List<Event>> fetchEvents() async {
    try {
      final res = await apiClient.get('/events');
      if (res is List) {
        final events = res.map((e) => Event.fromJson(e as Map<String, dynamic>)).toList();
        await storageService.cacheEvents(events);
        setOffline(false);
        return events;
      }
      return [];
    } on ApiException catch (e) {
      if (e.code == 'NETWORK_ERROR' || e.code == 'TIMEOUT' || e.code == 'CLIENT_ERROR') {
        setOffline(true);
        final cached = await storageService.getCachedEvents();
        if (cached.isNotEmpty) {
          return cached;
        }
      }
      rethrow;
    }
  }

  Future<Event> createEvent({
    required String name,
    String? description,
    required DateTime startAt,
    DateTime? endAt,
    String? location,
    String status = 'upcoming',
  }) async {
    if (_isOffline) {
      throw ApiException(
        code: 'OFFLINE',
        message: 'Network connection required to create events on the central server.',
      );
    }

    final payload = <String, dynamic>{
      'name': name.trim(),
      'description': description != null && description.trim().isNotEmpty ? description.trim() : null,
      'start_at': startAt.toUtc().toIso8601String(),
      'end_at': endAt?.toUtc().toIso8601String(),
      'location': location != null && location.trim().isNotEmpty ? location.trim() : null,
      'status': status.toLowerCase(),
    };

    final res = await apiClient.post('/events', body: payload);
    setOffline(false);
    final event = Event.fromJson(res as Map<String, dynamic>);
    await storageService.saveEvent(event);
    notifyListeners();
    return event;
  }

  // --- Screen 2: Teams for Event ---
  Future<List<Team>> fetchTeams(int eventId) async {
    try {
      final res = await apiClient.get('/events/$eventId/teams');
      if (res is Map<String, dynamic> && res['teams'] is List) {
        final teamsList = (res['teams'] as List)
            .map((t) => Team.fromJson(t as Map<String, dynamic>))
            .toList();
        await storageService.cacheTeams(teamsList);
        setOffline(false);
        return teamsList;
      }
      return [];
    } on ApiException catch (e) {
      if (e.code == 'NETWORK_ERROR' || e.code == 'TIMEOUT' || e.code == 'CLIENT_ERROR') {
        setOffline(true);
        final cached = await storageService.getCachedTeams();
        if (cached.isNotEmpty) {
          return cached;
        }
      }
      rethrow;
    }
  }

  // --- Screen 3: Members of Team ---
  Future<List<Member>> fetchMembers(int teamId, {String? query}) async {
    try {
      final res = await apiClient.get('/teams/$teamId/members');
      if (res is List) {
        final membersList = res.map((m) => Member.fromJson(m as Map<String, dynamic>)).toList();
        await storageService.cacheMembers(teamId, membersList);
        setOffline(false);

        if (query != null && query.trim().isNotEmpty) {
          final q = query.trim().toLowerCase();
          return membersList.where((m) =>
            m.fullName.toLowerCase().contains(q) ||
            (m.registrationNumber != null && m.registrationNumber!.toLowerCase().contains(q))
          ).toList();
        }
        return membersList;
      }
      return [];
    } on ApiException catch (e) {
      if (e.code == 'NETWORK_ERROR' || e.code == 'TIMEOUT' || e.code == 'CLIENT_ERROR') {
        setOffline(true);
        final cached = await storageService.getCachedMembers(teamId, query: query);
        if (cached.isNotEmpty) {
          return cached;
        }
      }
      rethrow;
    }
  }

  // --- Screen 4: Create Task & Assignments ---
  Future<Task> createTask({
    required int eventId,
    required String title,
    String? description,
    required String priority,
    required DateTime deadline,
    required List<int> memberIds,
  }) async {
    if (_isOffline) {
      throw ApiException(
        code: 'OFFLINE',
        message: 'Network connection required to create and assign tasks on the central server.',
      );
    }

    final payload = {
      'title': title.trim(),
      'description': description?.trim(),
      'priority': priority.toLowerCase(),
      'deadline': deadline.toUtc().toIso8601String(),
      'member_ids': memberIds,
    };

    final res = await apiClient.post('/events/$eventId/tasks', body: payload);
    setOffline(false);
    return Task.fromJson(res as Map<String, dynamic>);
  }

  // --- Screen 5: WhatsApp message draft & link ---
  Future<MessageDraft> getMessageDraft(int assignmentId) async {
    final res = await apiClient.post(
      '/assignments/$assignmentId/message-draft',
      body: {'message_type': 'initial_assignment'},
    );
    setOffline(false);
    return MessageDraft.fromJson(res as Map<String, dynamic>);
  }

  Future<MessageDraft> getWhatsAppLink(int assignmentId, {String? memberName, String? taskTitle, DateTime? deadline}) async {
    final res = await apiClient.post(
      '/assignments/$assignmentId/whatsapp-link',
      body: {'message_type': 'initial_assignment'},
    );
    setOffline(false);
    return MessageDraft.fromJson(
      res as Map<String, dynamic>,
      memberName: memberName,
      taskTitle: taskTitle,
      deadline: deadline,
    );
  }

  Future<void> recordMessageAction({
    required int assignmentId,
    required int messageLogId,
    required String action,
  }) async {
    await apiClient.post(
      '/assignments/$assignmentId/message-action',
      body: {
        'message_log_id': messageLogId,
        'action': action,
      },
    );
    setOffline(false);
  }

  // --- Screen 6: Assignment Tracking ---
  Future<List<TaskAssignment>> fetchAssignments({String? status, bool? overdue}) async {
    Map<String, String> query = {};
    if (status != null && status.isNotEmpty) query['status'] = status;
    if (overdue != null) query['overdue'] = overdue.toString();

    try {
      final res = await apiClient.get('/assignments', queryParams: query);
      if (res is List) {
        final list = res.map((a) => TaskAssignment.fromJson(a as Map<String, dynamic>)).toList();
        if (status == null && overdue == null) {
          await storageService.cacheAssignments(list);
        }
        setOffline(false);
        return list;
      }
      return [];
    } on ApiException catch (e) {
      if (e.code == 'NETWORK_ERROR' || e.code == 'TIMEOUT' || e.code == 'CLIENT_ERROR') {
        setOffline(true);
        final cached = await storageService.getCachedAssignments(status: status, overdue: overdue);
        if (cached.isNotEmpty) {
          return cached;
        }
      }
      rethrow;
    }
  }

  /// Fetch personal task assignments strictly for the authenticated volunteer.
  /// Backend derives identity exclusively from the validated session token.
  Future<List<TaskAssignment>> fetchMyAssignments({String? status}) async {
    Map<String, String> query = {};
    if (status != null && status.isNotEmpty) query['status'] = status;

    try {
      final res = await apiClient.get('/me/assignments', queryParams: query);
      if (res is List) {
        final list = res.map((a) => TaskAssignment.fromJson(a as Map<String, dynamic>)).toList();
        setOffline(false);
        return list;
      }
      return [];
    } on ApiException catch (e) {
      if (e.code == 'NETWORK_ERROR' || e.code == 'TIMEOUT' || e.code == 'CLIENT_ERROR') {
        setOffline(true);
      }
      rethrow;
    }
  }

  Future<TaskAssignment> getAssignmentDetails(int assignmentId) async {
    final res = await apiClient.get('/assignments/$assignmentId');
    final assignment = TaskAssignment.fromJson(res as Map<String, dynamic>);
    await storageService.updateSingleCachedAssignment(assignment);
    setOffline(false);
    return assignment;
  }

  Future<TaskAssignment> updateAssignmentStatus(
    int assignmentId,
    String targetStatus, {
    String? note,
  }) async {
    if (_isOffline) {
      throw ApiException(
        code: 'OFFLINE',
        message: 'Network connection required to update assignment status.',
      );
    }

    final payload = <String, dynamic>{'status': targetStatus};
    if (note != null && note.isNotEmpty) {
      payload['note'] = note;
    }

    final res = await apiClient.patch(
      '/assignments/$assignmentId/status',
      body: payload,
    );
    final updated = TaskAssignment.fromJson(res as Map<String, dynamic>);
    await storageService.updateSingleCachedAssignment(updated);

    setOffline(false);
    return updated;
  }

  // --- President Member Account Management ---
  Future<List<Team>> fetchClubTeams() async {
    try {
      final res = await apiClient.get('/teams');
      if (res is List) {
        final teamsList = res
            .map((t) => Team.fromJson(t as Map<String, dynamic>))
            .toList();
        await storageService.cacheTeams(teamsList);
        setOffline(false);
        return teamsList;
      }
      return [];
    } on ApiException catch (e) {
      if (e.code == 'NETWORK_ERROR' || e.code == 'TIMEOUT' || e.code == 'CLIENT_ERROR') {
        setOffline(true);
        final cached = await storageService.getCachedTeams();
        if (cached.isNotEmpty) {
          return cached;
        }
      }
      rethrow;
    }
  }

  Future<List<Member>> fetchClubMembers({int? teamId, String? search, bool? isActive}) async {
    Map<String, String> query = {};
    if (teamId != null) query['team_id'] = teamId.toString();
    if (search != null && search.trim().isNotEmpty) query['search'] = search.trim();
    if (isActive != null) query['is_active'] = isActive.toString();

    try {
      final res = await apiClient.get('/members', queryParams: query);
      if (res is List) {
        final membersList = res
            .map((m) => Member.fromJson(m as Map<String, dynamic>))
            .toList();
        if (teamId != null) {
          await storageService.cacheMembers(teamId, membersList);
        }
        setOffline(false);
        return membersList;
      }
      return [];
    } on ApiException catch (e) {
      if (e.code == 'NETWORK_ERROR' || e.code == 'TIMEOUT' || e.code == 'CLIENT_ERROR') {
        setOffline(true);
        if (teamId != null) {
          final cached = await storageService.getCachedMembers(teamId, query: search);
          if (cached.isNotEmpty) return cached;
        }
      }
      rethrow;
    }
  }

  Future<Map<String, dynamic>> createMemberAccount({
    required String fullName,
    String? registrationNumber,
    required String className,
    String? section,
    required String phoneNumber,
    String countryCode = '+91',
    required int teamId,
    required String username,
    required String email,
    required String password,
    String role = 'member',
  }) async {
    if (_isOffline) {
      throw ApiException(
        code: 'OFFLINE',
        message: 'Network connection required to create member accounts on the central server.',
      );
    }

    final payload = <String, dynamic>{
      'full_name': fullName.trim(),
      'registration_number': registrationNumber?.trim().isNotEmpty == true ? registrationNumber!.trim() : null,
      'class_name': className.trim(),
      'section': section?.trim().isNotEmpty == true ? section!.trim() : null,
      'phone_number': phoneNumber.trim(),
      'country_code': countryCode.trim(),
      'team_id': teamId,
      'username': username.trim().toLowerCase(),
      'email': email.trim().toLowerCase(),
      'password': password,
      'role': role.trim().toLowerCase(),
    };

    final res = await apiClient.post('/members/account', body: payload);
    setOffline(false);
    notifyListeners();

    Member? member;
    if (res is Map<String, dynamic> && res['member'] is Map<String, dynamic>) {
      member = Member.fromJson(res['member'] as Map<String, dynamic>);
    }
    return {
      'member': member,
      'user': res is Map<String, dynamic> ? res['user'] : null,
    };
  }

  Future<void> resetMemberPassword(int memberId, String newPassword) async {
    if (_isOffline) {
      throw ApiException(
        code: 'OFFLINE',
        message: 'Network connection required to reset member password.',
      );
    }

    await apiClient.post(
      '/members/$memberId/reset-password',
      body: {'new_password': newPassword},
    );
    setOffline(false);
    notifyListeners();
  }

  Future<Member> toggleMemberActiveStatus(int memberId, bool isActive) async {
    if (_isOffline) {
      throw ApiException(
        code: 'OFFLINE',
        message: 'Network connection required to update member status.',
      );
    }

    final res = await apiClient.patch(
      '/members/$memberId',
      body: {'is_active': isActive},
    );
    setOffline(false);
    final updated = Member.fromJson(res as Map<String, dynamic>);
    notifyListeners();
    return updated;
  }

  Future<Member> updateMemberDetails({
    required int memberId,
    String? fullName,
    String? registrationNumber,
    String? className,
    String? section,
    String? phoneNumber,
    int? teamId,
    String? email,
    String? role,
    bool? whatsappOptIn,
  }) async {
    if (_isOffline) {
      throw ApiException(
        code: 'OFFLINE',
        message: 'Network connection required to update member details.',
      );
    }

    final payload = <String, dynamic>{};
    if (fullName != null) payload['full_name'] = fullName.trim();
    if (registrationNumber != null) {
      payload['registration_number'] = registrationNumber.trim().isEmpty ? null : registrationNumber.trim();
    }
    if (className != null) payload['class_name'] = className.trim();
    if (section != null) {
      payload['section'] = section.trim().isEmpty ? null : section.trim();
    }
    if (phoneNumber != null) payload['phone_number'] = phoneNumber.trim();
    if (teamId != null) payload['team_id'] = teamId;
    if (email != null) {
      payload['email'] = email.trim().isEmpty ? null : email.trim();
    }
    if (role != null) payload['role'] = role;
    if (whatsappOptIn != null) payload['whatsapp_opt_in'] = whatsappOptIn;

    final res = await apiClient.patch(
      '/members/$memberId',
      body: payload,
    );
    setOffline(false);
    final updated = Member.fromJson(res as Map<String, dynamic>);
    notifyListeners();
    return updated;
  }
}
