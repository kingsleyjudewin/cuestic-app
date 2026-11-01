import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/config/app_theme.dart';
import 'package:mobile/models/assignment.dart';
import 'package:mobile/models/event.dart';
import 'package:mobile/models/member.dart';
import 'package:mobile/models/task.dart';
import 'package:mobile/models/team.dart';
import 'package:mobile/screens/assignment_message_screen.dart';
import 'package:mobile/screens/assignment_tracking_screen.dart';
import 'package:mobile/screens/create_assignment_screen.dart';
import 'package:mobile/screens/member_directory_screen.dart';
import 'package:mobile/screens/select_event_screen.dart';
import 'package:mobile/screens/select_team_screen.dart';
import 'package:mobile/services/api_client.dart';
import 'package:mobile/services/auth_service.dart';
import 'package:mobile/services/storage_service.dart';
import 'package:mobile/services/sync_service.dart';
import 'package:mobile/services/whatsapp_service.dart';
import 'package:mobile/widgets/primary_button.dart';

class FakeStorageService extends StorageService {
  List<Event> _events = [];
  List<Team> _teams = [];
  final Map<int, List<Member>> _members = {};
  List<TaskAssignment> _assignments = [];

  @override
  Future<void> cacheEvents(List<Event> events) async {
    _events = List.from(events);
  }

  @override
  Future<List<Event>> getCachedEvents() async => List.from(_events);

  @override
  Future<void> cacheTeams(List<Team> teams) async {
    _teams = List.from(teams);
  }

  @override
  Future<List<Team>> getCachedTeams() async => List.from(_teams);

  @override
  Future<void> cacheMembers(int teamId, List<Member> members) async {
    _members[teamId] = List.from(members);
  }

  @override
  Future<List<Member>> getCachedMembers(int teamId, {String? query}) async {
    final list = _members[teamId] ?? [];
    if (query != null && query.trim().isNotEmpty) {
      final q = query.toLowerCase();
      return list.where((m) =>
        m.fullName.toLowerCase().contains(q) ||
        (m.registrationNumber?.toLowerCase().contains(q) ?? false)
      ).toList();
    }
    return List.from(list);
  }

  @override
  Future<void> cacheAssignments(List<TaskAssignment> assignments) async {
    _assignments = List.from(assignments);
  }

  @override
  Future<List<TaskAssignment>> getCachedAssignments({String? status, bool? overdue}) async {
    var list = _assignments;
    if (status != null) list = list.where((a) => a.status == status).toList();
    if (overdue != null) list = list.where((a) => a.isOverdue == overdue).toList();
    return List.from(list);
  }
}

void main() {
  setUpAll(() {
    TestWidgetsFlutterBinding.ensureInitialized();
    FlutterSecureStorage.setMockInitialValues({});
  });

  group('Widget Workflow Tests', () {
    late FakeStorageService storageService;
    late AuthService authService;

    setUp(() {
      storageService = FakeStorageService();
      authService = AuthService();
    });

    testWidgets('Screen 1 — Select Event renders header, list, and continue button', (tester) async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'success': true,
            'data': [
              {
                'id': 1,
                'name': 'MAGNOVITE 2026',
                'start_at': '2026-10-28T09:00:00Z',
                'status': 'upcoming',
              },
              {
                'id': 2,
                'name': 'Hackathon Spring 2026',
                'start_at': '2026-11-15T09:00:00Z',
                'status': 'upcoming',
              },
            ]
          }),
          200,
        );
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      Event? selected;
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: SelectEventScreen(
            syncService: syncService,
            authService: authService,
            onEventSelected: (e) => selected = e,
            onOpenAssignments: () {},
            onLogout: () {},
          ),
        ),
      );

      await tester.pump();
      await tester.pump();

      // Events displayed
      expect(find.text('Events'), findsOneWidget);
      expect(find.text('MAGNOVITE 2026'), findsWidgets);
      expect(find.text('Hackathon Spring 2026'), findsOneWidget);

      // Tap Continue
      final continueButton = find.text('Continue');
      expect(continueButton, findsOneWidget);
      await tester.tap(continueButton);
      await tester.pump();

      expect(selected, isNotNull);
      expect(selected!.name, 'MAGNOVITE 2026');
    });

    testWidgets('Screen 2 — Select Team displays four teams with member counts and chevrons', (tester) async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'success': true,
            'data': {
              'event_id': 1,
              'event_name': 'MAGNOVITE 2026',
              'teams': [
                {'id': 1, 'name': 'Volunteering', 'slug': 'volunteering', 'member_count': 12, 'is_active': true},
                {'id': 2, 'name': 'Documentation', 'slug': 'documentation', 'member_count': 6, 'is_active': true},
                {'id': 3, 'name': 'Media', 'slug': 'media', 'member_count': 8, 'is_active': true},
                {'id': 4, 'name': 'Registration', 'slug': 'registration', 'member_count': 15, 'is_active': true},
              ]
            }
          }),
          200,
        );
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      final demoEvent = Event(
        id: 1,
        name: 'MAGNOVITE 2026',
        startAt: DateTime.parse('2026-10-28T09:00:00Z'),
        status: 'upcoming',
      );

      Team? pickedTeam;
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: SelectTeamScreen(
            event: demoEvent,
            syncService: syncService,
            onTeamSelected: (t) => pickedTeam = t,
          ),
        ),
      );

      await tester.pump();
      await tester.pump();

      expect(find.text('Volunteering'), findsOneWidget);
      expect(find.text('Documentation'), findsOneWidget);
      expect(find.text('Media'), findsOneWidget);
      expect(find.text('Registration'), findsOneWidget);
      expect(find.text('12 members'), findsOneWidget);

      await tester.tap(find.text('Media'));
      await tester.pump();

      expect(pickedTeam, isNotNull);
      expect(pickedTeam!.name, 'Media');
    });

    testWidgets('Screen 3 — Member Directory preserves selected members while searching', (tester) async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'success': true,
            'data': [
              {
                'id': 1,
                'full_name': 'Ananya Sharma',
                'registration_number': 'REG-001',
                'class_name': '3rd Year CSE',
                'section': 'A',
                'phone_number': '+919876500001',
                'team_id': 1,
                'team_name': 'Volunteering',
              },
              {
                'id': 2,
                'full_name': 'Rohan Verma',
                'registration_number': 'REG-002',
                'class_name': '3rd Year CSE',
                'section': 'B',
                'phone_number': '+919876500002',
                'team_id': 1,
                'team_name': 'Volunteering',
              },
            ]
          }),
          200,
        );
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      final demoEvent = Event(
        id: 1,
        name: 'MAGNOVITE 2026',
        startAt: DateTime.parse('2026-10-28T09:00:00Z'),
        status: 'upcoming',
      );
      final demoTeam = Team(id: 1, name: 'Volunteering', slug: 'volunteering', memberCount: 2);

      List<Member> assigned = [];
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: MemberDirectoryScreen(
            event: demoEvent,
            team: demoTeam,
            syncService: syncService,
            onAssignTask: (members) => assigned = members,
          ),
        ),
      );

      await tester.pump();
      await tester.pump();

      expect(find.text('Ananya Sharma'), findsOneWidget);
      expect(find.text('Rohan Verma'), findsOneWidget);

      // Select Ananya Sharma
      await tester.tap(find.text('Ananya Sharma'));
      await tester.pump();

      expect(find.text('Assign Task (1)'), findsOneWidget);

      // Filter by searching 'Rohan'
      await tester.enterText(find.byType(TextField), 'Rohan');
      await tester.pump();

      expect(find.text('Ananya Sharma'), findsNothing); // filtered out from view
      expect(find.text('Rohan Verma'), findsOneWidget);

      // Clear search
      await tester.enterText(find.byType(TextField), '');
      await tester.pump();

      // Ananya Sharma is still selected!
      expect(find.text('Assign Task (1)'), findsOneWidget);

      // Tap Assign Task
      await tester.tap(find.text('Assign Task (1)'));
      await tester.pump();

      expect(assigned.length, 1);
      expect(assigned.first.fullName, 'Ananya Sharma');
    });

    testWidgets('Screen 4 — Create Assignment validates title and triggers submission', (tester) async {
      final mockClient = MockClient((request) async {
        final body = jsonDecode(request.body);
        expect(body['title'], 'Design Main Stage Banner');
        expect(body['priority'], 'high');
        expect(body['member_ids'], [1]);

        return http.Response(
          jsonEncode({
            'success': true,
            'data': {
              'id': 100,
              'event_id': 1,
              'title': 'Design Main Stage Banner',
              'priority': 'high',
              'deadline': '2026-10-30T17:00:00Z',
              'is_cancelled': false,
              'assignments': [
                {
                  'id': 201,
                  'task_id': 100,
                  'member_id': 1,
                  'member_name': 'Ananya Sharma',
                  'status': 'awaiting_confirmation',
                }
              ]
            }
          }),
          201,
        );
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      final demoEvent = Event(
        id: 1,
        name: 'MAGNOVITE 2026',
        startAt: DateTime.parse('2026-10-28T09:00:00Z'),
        status: 'upcoming',
      );
      final demoTeam = Team(id: 1, name: 'Volunteering', slug: 'volunteering');
      final selectedMembers = [
        Member(
          id: 1,
          fullName: 'Ananya Sharma',
          className: '3rd Year CSE',
          phoneNumber: '+919876500001',
          teamId: 1,
        ),
      ];

      Task? createdTask;
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: CreateAssignmentScreen(
            event: demoEvent,
            team: demoTeam,
            selectedMembers: selectedMembers,
            syncService: syncService,
            onTaskCreated: (t) => createdTask = t,
          ),
        ),
      );

      await tester.pump();
      await tester.pump();

      // Tap Create Assignment button without entering title -> validation error
      final createButton = find.widgetWithText(PrimaryButton, 'Create Assignment');
      await tester.tap(createButton);
      await tester.pump();

      expect(find.text('Task title is required.'), findsOneWidget);

      // Enter title into the first TextField
      await tester.enterText(find.byType(TextField).first, 'Design Main Stage Banner');
      await tester.pump();

      // Select High Priority
      await tester.tap(find.text('HIGH'));
      await tester.pump();

      // Submit
      await tester.tap(createButton);
      await tester.pump();
      await tester.pump();

      expect(createdTask, isNotNull);
      expect(createdTask!.title, 'Design Main Stage Banner');
      expect(createdTask!.assignments.length, 1);
    });

    testWidgets('Screen 5 — Assignment Message displays plain-text preview and buttons', (tester) async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'success': true,
            'data': {
              'assignment_id': 201,
              'message_log_id': 50,
              'whatsapp_url': 'https://wa.me/919876500001?text=Hello',
              'phone_number': '+919876500001',
              'wa_phone': '919876500001',
              'message_text': 'Hi Ananya! You have been assigned: Prepare event poster.',
              'disclaimer': 'Official club task assignment',
            }
          }),
          200,
        );
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);
      final whatsAppService = WhatsAppService(syncService: syncService);

      final task = Task(
        id: 100,
        eventId: 1,
        title: 'Prepare event poster',
        deadline: DateTime.parse('2026-10-30T17:00:00Z'),
        assignments: [
          TaskAssignment(
            id: 201,
            taskId: 100,
            memberId: 1,
            memberName: 'Ananya Sharma',
            memberPhone: '+919876500001',
            assignedBy: 1,
            status: 'awaiting_confirmation',
          ),
        ],
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: AssignmentMessageScreen(
            task: task,
            syncService: syncService,
            whatsAppService: whatsAppService,
            onFinish: () {},
          ),
        ),
      );

      await tester.pump();
      await tester.pump();

      expect(find.text('Assignment Message'), findsOneWidget);
      expect(find.text('Hi Ananya! You have been assigned: Prepare event poster.'), findsOneWidget);
      expect(find.text('Open WhatsApp'), findsOneWidget);
      expect(find.text('Mark as Sent'), findsOneWidget);
    });

    testWidgets('Screen 6 — Assignment Tracking filters and overdue badges', (tester) async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'success': true,
            'data': [
              {
                'id': 1,
                'task_id': 10,
                'task_title': 'Design Poster',
                'event_name': 'MAGNOVITE 2026',
                'member_id': 1,
                'member_name': 'Ananya Sharma',
                'assigned_by': 1,
                'status': 'awaiting_confirmation',
                'is_overdue': false,
                'deadline': '2026-10-30T18:00:00Z',
              },
              {
                'id': 2,
                'task_id': 11,
                'task_title': 'Stage Rigging',
                'event_name': 'MAGNOVITE 2026',
                'member_id': 2,
                'member_name': 'Rohan Verma',
                'assigned_by': 1,
                'status': 'in_progress',
                'is_overdue': true,
                'deadline': '2026-10-24T18:00:00Z',
              },
            ]
          }),
          200,
        );
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      int? tappedId;
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: AssignmentTrackingScreen(
            syncService: syncService,
            onSelectAssignment: (id) => tappedId = id,
          ),
        ),
      );

      await tester.pump();
      await tester.pump();

      expect(find.text('Assignment Tracking'), findsOneWidget);
      expect(find.text('Design Poster'), findsOneWidget);
      expect(find.text('Stage Rigging'), findsOneWidget);
      expect(find.text('OVERDUE'), findsOneWidget);

      await tester.tap(find.text('Stage Rigging'));
      await tester.pump();

      expect(tappedId, 2);
    });
  });
}
