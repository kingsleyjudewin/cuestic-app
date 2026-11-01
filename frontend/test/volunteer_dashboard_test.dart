import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/config/app_theme.dart';
import 'package:mobile/config/constants.dart';
import 'package:mobile/models/assignment.dart';
import 'package:mobile/models/event.dart';
import 'package:mobile/models/member.dart';
import 'package:mobile/models/team.dart';
import 'package:mobile/screens/select_event_screen.dart';
import 'package:mobile/screens/volunteer_dashboard_screen.dart';
import 'package:mobile/services/api_client.dart';
import 'package:mobile/services/auth_service.dart';
import 'package:mobile/services/storage_service.dart';
import 'package:mobile/services/sync_service.dart';

class TestStorageService extends StorageService {
  List<Event> eventsList = [];
  List<Team> teamsList = [];
  Map<int, List<Member>> membersMap = {};
  List<TaskAssignment> assignmentsList = [];

  @override
  Future<void> cacheEvents(List<Event> events) async {
    eventsList = List.from(events);
  }

  @override
  Future<List<Event>> getCachedEvents() async => List.from(eventsList);

  @override
  Future<void> cacheTeams(List<Team> teams) async {
    teamsList = List.from(teams);
  }

  @override
  Future<List<Team>> getCachedTeams() async => List.from(teamsList);

  @override
  Future<void> cacheMembers(int teamId, List<Member> members) async {
    membersMap[teamId] = List.from(members);
  }

  @override
  Future<List<Member>> getCachedMembers(int teamId, {String? query}) async =>
      List.from(membersMap[teamId] ?? []);

  @override
  Future<void> cacheAssignments(List<TaskAssignment> assignments, {bool append = false}) async {
    if (append) {
      assignmentsList.addAll(assignments);
    } else {
      assignmentsList = List.from(assignments);
    }
  }

  @override
  Future<List<TaskAssignment>> getCachedAssignments({String? status, bool? overdue}) async {
    return List.from(assignmentsList);
  }

  @override
  Future<void> updateSingleCachedAssignment(TaskAssignment assignment) async {
    final idx = assignmentsList.indexWhere((a) => a.id == assignment.id);
    if (idx != -1) {
      assignmentsList[idx] = assignment;
    } else {
      assignmentsList.add(assignment);
    }
  }
}

void main() {
  setUpAll(() {
    TestWidgetsFlutterBinding.ensureInitialized();
  });

  group('Volunteer Dashboard & Dynamic Login Tests', () {
    late TestStorageService storageService;

    setUp(() {
      storageService = TestStorageService();
    });

    testWidgets('1. Volunteer Dashboard displays dynamic volunteer name, team, and assigned tasks', (tester) async {
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'volunteer-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 10,
          'username': 'sagar.cu',
          'role': 'member',
          'member_name': 'Sagar CU',
          'team_name': 'Volunteering',
        }),
      });

      final authService = AuthService();
      await authService.initialize();

      final mockClient = MockClient((request) async {
        if (request.url.path.contains('/me/assignments')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {
                  'id': 101,
                  'task_id': 1,
                  'task_title': 'Crowd Control',
                  'task_description': 'Manage crowd flow at the auditorium entrance and coordinate with volunteering team.',
                  'task_priority': 'high',
                  'deadline': '2026-11-05T18:00:00Z',
                  'deadline_formatted': 'Nov 5, 2026 6:00 PM',
                  'event_id': 1,
                  'event_name': 'MAGNOVITE 2026',
                  'member_id': 10,
                  'member_name': 'Sagar CU',
                  'team_name': 'Volunteering',
                  'status': 'awaiting_confirmation',
                  'assigned_by': 1,
                  'assigner_name': 'Club President',
                  'is_overdue': false,
                  'assigned_at': '2026-10-27T10:00:00Z',
                }
              ]
            }),
            200,
          );
        }
        return http.Response('{"error": "not found"}', 404);
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: VolunteerDashboardScreen(
            syncService: syncService,
            authService: authService,
            onLogout: () {},
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Check header displays dynamic volunteer info
      expect(find.text('My Tasks'), findsOneWidget);
      expect(find.text('Sagar CU'), findsOneWidget);
      expect(find.text('Volunteering'), findsOneWidget);

      // Check task card content
      expect(find.text('MAGNOVITE 2026'), findsOneWidget);
      expect(find.text('Crowd Control'), findsOneWidget);
      expect(find.textContaining('Manage crowd flow at the auditorium entrance and coordinate with volunteering team.'), findsOneWidget);
      expect(find.textContaining('Nov 5, 2026'), findsOneWidget);
      expect(find.text('HIGH'), findsOneWidget);
      expect(find.text('PENDING'), findsOneWidget);

      // Action buttons for awaiting_confirmation
      expect(find.text('Accept'), findsOneWidget);
      expect(find.text('Decline'), findsOneWidget);
    });

    testWidgets('2. Empty state renders when volunteer has no assigned tasks', (tester) async {
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'volunteer-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 11,
          'username': 'devananda.ajith',
          'role': 'member',
          'member_name': 'Devananda Ajith',
          'team_name': 'Volunteering',
        }),
      });

      final authService = AuthService();
      await authService.initialize();

      final mockClient = MockClient((request) async {
        if (request.url.path.contains('/me/assignments')) {
          return http.Response(
            jsonEncode({'success': true, 'data': []}),
            200,
          );
        }
        return http.Response('{"error": "not found"}', 404);
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: VolunteerDashboardScreen(
            syncService: syncService,
            authService: authService,
            onLogout: () {},
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Devananda Ajith'), findsOneWidget);
      expect(find.textContaining('No tasks assigned yet'), findsOneWidget);
    });

    testWidgets('3. Volunteer task actions: Accept, Start, and Submit with note', (tester) async {
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'volunteer-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 12,
          'username': 'kanishk',
          'role': 'member',
          'member_name': 'Kanishk',
          'team_name': 'Volunteering',
        }),
      });

      final authService = AuthService();
      await authService.initialize();

      String currentStatus = 'awaiting_confirmation';
      String? recordedNote;

      final mockClient = MockClient((request) async {
        if (request.method == 'GET' && request.url.path.contains('/me/assignments')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {
                  'id': 202,
                  'task_id': 2,
                  'task_title': 'Stage Setup',
                  'task_description': 'Assemble podium and sound monitors.',
                  'task_priority': 'medium',
                  'deadline_formatted': 'Nov 6, 2026',
                  'event_name': 'Tech Symposium 2026',
                  'member_id': 12,
                  'member_name': 'Kanishk',
                  'status': currentStatus,
                  'assigned_by': 1,
                  'assigner_name': 'President',
                  'is_overdue': false,
                  'completion_note': recordedNote,
                }
              ]
            }),
            200,
          );
        }

        if (request.method == 'PATCH' && request.url.path.contains('/assignments/202/status')) {
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          currentStatus = body['status'] as String;
          if (body.containsKey('note')) {
            recordedNote = body['note'] as String;
          }
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {
                'id': 202,
                'task_id': 2,
                'task_title': 'Stage Setup',
                'task_description': 'Assemble podium and sound monitors.',
                'task_priority': 'medium',
                'event_name': 'Tech Symposium 2026',
                'member_id': 12,
                'member_name': 'Kanishk',
                'status': currentStatus,
                'completion_note': recordedNote,
              }
            }),
            200,
          );
        }

        return http.Response('{"error": "not found"}', 404);
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: VolunteerDashboardScreen(
            syncService: syncService,
            authService: authService,
            onLogout: () {},
          ),
        ),
      );

      await tester.pumpAndSettle();

      // 3a. Accept task
      expect(find.text('Accept'), findsOneWidget);
      await tester.tap(find.text('Accept'));
      await tester.pumpAndSettle();

      // Status should now be accepted -> action button should be "Start Task"
      expect(find.text('Start Task'), findsOneWidget);

      // 3b. Start task
      await tester.tap(find.text('Start Task'));
      await tester.pumpAndSettle();

      // Status should now be in_progress -> action button should be "Submit Work"
      expect(find.text('Submit Work'), findsOneWidget);

      // 3c. Tap "Submit Work" -> opens modal dialog
      await tester.tap(find.text('Submit Work'));
      await tester.pumpAndSettle();

      expect(find.text('Submit Completed Work'), findsOneWidget);

      // Enter notes and submit
      await tester.enterText(find.byType(TextFormField).last, 'Podium banners hung and sound checked.');
      await tester.tap(find.text('Submit'));
      await tester.pumpAndSettle();

      // Status should now be submitted
      expect(find.text('Under Leader Review'), findsOneWidget);
      expect(recordedNote, 'Podium banners hung and sound checked.');
    });

    testWidgets('4. Role-based app routing: volunteer goes to VolunteerDashboard, admin goes to SelectEventScreen', (tester) async {
      // 4a. Volunteer login -> routes to VolunteerDashboardScreen
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'volunteer-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 15,
          'username': 'shohil.mathew',
          'role': 'member',
          'member_name': 'Shohil Mathew',
          'team_name': 'Volunteering',
        }),
      });

      final volAuth = AuthService();
      await volAuth.initialize();

      final mockClient = MockClient((request) async {
        if (request.url.path.contains('/me/assignments')) {
          return http.Response(jsonEncode({'success': true, 'data': []}), 200);
        }
        if (request.url.path.contains('/events')) {
          return http.Response(jsonEncode({'success': true, 'data': []}), 200);
        }
        return http.Response('{"error": "not found"}', 404);
      });

      final volApiClient = ApiClient(client: mockClient, authService: volAuth);
      final volSync = SyncService(apiClient: volApiClient, storageService: storageService);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: volAuth.isAuthenticated
              ? (volAuth.isAdmin || volAuth.isTeamLeader
                  ? SelectEventScreen(
                      syncService: volSync,
                      authService: volAuth,
                      onEventSelected: (_) {},
                      onOpenAssignments: () {},
                      onLogout: () {},
                    )
                  : VolunteerDashboardScreen(
                      syncService: volSync,
                      authService: volAuth,
                      onLogout: () {},
                    ))
              : const Scaffold(body: Text('Login')),
        ),
      );

      await tester.pumpAndSettle();

      // Volunteer sees VolunteerDashboardScreen
      expect(find.byType(VolunteerDashboardScreen), findsOneWidget);
      expect(find.byType(SelectEventScreen), findsNothing);
      expect(find.text('Shohil Mathew'), findsOneWidget);
      // No admin buttons present
      expect(find.text('Create Event'), findsNothing);
      expect(find.text('Manage Members'), findsNothing);

      // 4b. Admin login -> routes to SelectEventScreen
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'admin-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 1,
          'username': 'clubadmin',
          'role': 'admin',
        }),
      });

      final adminAuth = AuthService();
      await adminAuth.initialize();

      final adminApiClient = ApiClient(client: mockClient, authService: adminAuth);
      final adminSync = SyncService(apiClient: adminApiClient, storageService: storageService);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: adminAuth.isAuthenticated
              ? (adminAuth.isAdmin || adminAuth.isTeamLeader
                  ? SelectEventScreen(
                      syncService: adminSync,
                      authService: adminAuth,
                      onEventSelected: (_) {},
                      onOpenAssignments: () {},
                      onLogout: () {},
                    )
                  : VolunteerDashboardScreen(
                      syncService: adminSync,
                      authService: adminAuth,
                      onLogout: () {},
                    ))
              : const Scaffold(body: Text('Login')),
        ),
      );

      await tester.pumpAndSettle();

      // Admin sees SelectEventScreen
      expect(find.byType(SelectEventScreen), findsOneWidget);
      expect(find.byType(VolunteerDashboardScreen), findsNothing);
    });
  });
}
