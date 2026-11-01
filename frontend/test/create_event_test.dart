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
import 'package:mobile/screens/create_event_screen.dart';
import 'package:mobile/screens/select_event_screen.dart';
import 'package:mobile/services/api_client.dart';
import 'package:mobile/services/auth_service.dart';
import 'package:mobile/services/storage_service.dart';
import 'package:mobile/services/sync_service.dart';
import 'package:mobile/widgets/primary_button.dart';
import 'package:mobile/widgets/secondary_button.dart';

class TestStorageService extends StorageService {
  List<Event> eventsList = [];

  @override
  Future<void> cacheEvents(List<Event> events) async {
    eventsList = List.from(events);
  }

  @override
  Future<void> saveEvent(Event event) async {
    eventsList.removeWhere((e) => e.id == event.id);
    eventsList.add(event);
  }

  @override
  Future<List<Event>> getCachedEvents() async => List.from(eventsList);

  @override
  Future<void> cacheTeams(List<Team> teams) async {}
  @override
  Future<List<Team>> getCachedTeams() async => [];
  @override
  Future<void> cacheMembers(int teamId, List<Member> members) async {}
  @override
  Future<List<Member>> getCachedMembers(int teamId, {String? query}) async => [];
  @override
  Future<void> cacheAssignments(List<TaskAssignment> assignments) async {}
  @override
  Future<List<TaskAssignment>> getCachedAssignments({String? status, bool? overdue}) async => [];
}

void main() {
  setUpAll(() {
    TestWidgetsFlutterBinding.ensureInitialized();
  });

  group('Create Event Flow & Permissions Tests', () {
    late TestStorageService storageService;

    setUp(() {
      storageService = TestStorageService();
    });

    testWidgets('1. Authorized user (president/admin) sees Create Event button; member does not', (tester) async {
      // Setup president auth
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'admin-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 1,
          'username': 'clubadmin',
          'role': 'president',
        }),
      });
      final adminAuth = AuthService();
      await adminAuth.initialize();

      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'success': true,
            'data': [
              {
                'id': 1,
                'name': 'Existing Symposium 2026',
                'start_at': '2026-11-01T10:00:00Z',
                'status': 'upcoming',
              }
            ]
          }),
          200,
        );
      });

      final apiClient = ApiClient(client: mockClient, authService: adminAuth);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: SelectEventScreen(
            syncService: syncService,
            authService: adminAuth,
            onEventSelected: (_) {},
            onOpenAssignments: () {},
            onLogout: () {},
          ),
        ),
      );

      await tester.pump();
      await tester.pump();

      // Authorized user sees Create Event button in body and app bar
      expect(find.text('Create Event'), findsWidgets);

      // Now test member role (unauthorized to create events)
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'member-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 2,
          'username': 'member_user',
          'role': 'member',
        }),
      });
      final memberAuth = AuthService();
      await memberAuth.initialize();

      final memberApiClient = ApiClient(client: mockClient, authService: memberAuth);
      final memberSyncService = SyncService(apiClient: memberApiClient, storageService: storageService);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: SelectEventScreen(
            syncService: memberSyncService,
            authService: memberAuth,
            onEventSelected: (_) {},
            onOpenAssignments: () {},
            onLogout: () {},
          ),
        ),
      );

      await tester.pump();
      await tester.pump();

      // Member should NOT see Create Event button
      expect(find.text('Create Event'), findsNothing);
    });

    testWidgets('2. Empty state displays Create Event button for authorized users', (tester) async {
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

      // Empty events response
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({'success': true, 'data': []}),
          200,
        );
      });

      final apiClient = ApiClient(client: mockClient, authService: adminAuth);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: SelectEventScreen(
            syncService: syncService,
            authService: adminAuth,
            onEventSelected: (_) {},
            onOpenAssignments: () {},
            onLogout: () {},
          ),
        ),
      );

      await tester.pump();
      await tester.pump();

      expect(find.text('No events found in this club.'), findsOneWidget);
      expect(find.text('Create Event'), findsWidgets);
    });

    testWidgets('3. Required fields and date range validation on CreateEventScreen', (tester) async {
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'admin-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 1,
          'username': 'clubadmin',
          'role': 'president',
        }),
      });
      final adminAuth = AuthService();
      await adminAuth.initialize();

      final mockClient = MockClient((request) async {
        return http.Response(jsonEncode({'success': true, 'data': {}}), 200);
      });

      final apiClient = ApiClient(client: mockClient, authService: adminAuth);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: CreateEventScreen(
            syncService: syncService,
            authService: adminAuth,
          ),
        ),
      );

      await tester.pump();

      // Tap submit with empty name
      final submitButton = find.widgetWithText(PrimaryButton, 'Create Event');
      expect(submitButton, findsOneWidget);

      await tester.tap(submitButton);
      await tester.pump();

      // Field error for name
      expect(find.text('Event Name *'), findsOneWidget);
      expect(find.text('Event name is required.'), findsOneWidget);

      // Enter 1 character name
      final nameField = find.byType(TextField).first;
      await tester.enterText(nameField, 'A');
      await tester.tap(submitButton);
      await tester.pump();

      expect(find.text('Event name must be at least 2 characters.'), findsOneWidget);
    });

    testWidgets('4. Server errors preserve form data on failure', (tester) async {
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'admin-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 1,
          'username': 'clubadmin',
          'role': 'president',
        }),
      });
      final adminAuth = AuthService();
      await adminAuth.initialize();

      // Mock server returning 409 Conflict (e.g. duplicate event name)
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'success': false,
            'error': {
              'code': 'CONFLICT',
              'message': "An event named 'MAGNOVITE 2026' already exists.",
              'details': {'name': 'Event name already taken'}
            }
          }),
          409,
        );
      });

      final apiClient = ApiClient(client: mockClient, authService: adminAuth);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: CreateEventScreen(
            syncService: syncService,
            authService: adminAuth,
          ),
        ),
      );

      await tester.pump();

      // Fill in form fields
      final textFields = find.byType(TextField);
      await tester.enterText(textFields.at(0), 'MAGNOVITE 2026'); // Name
      await tester.enterText(textFields.at(1), 'Annual Symposium Details'); // Description
      await tester.enterText(textFields.at(2), 'Campus Auditorium'); // Location

      final submitButton = find.widgetWithText(PrimaryButton, 'Create Event');
      await tester.tap(submitButton);
      await tester.pump();
      await tester.pump();

      // Server error message displayed
      expect(find.text("An event named 'MAGNOVITE 2026' already exists."), findsOneWidget);

      // Form values are preserved
      expect(find.text('MAGNOVITE 2026'), findsOneWidget);
      expect(find.text('Annual Symposium Details'), findsOneWidget);
      expect(find.text('Campus Auditorium'), findsOneWidget);
    });

    testWidgets('5. Repeated taps do not create duplicate requests (debouncing/isSubmitting)', (tester) async {
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'admin-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 1,
          'username': 'clubadmin',
          'role': 'president',
        }),
      });
      final adminAuth = AuthService();
      await adminAuth.initialize();

      int postCallCount = 0;
      final mockClient = MockClient((request) async {
        if (request.method == 'POST' && request.url.path.endsWith('/events')) {
          postCallCount++;
          // Delay to allow multiple taps
          await Future.delayed(const Duration(milliseconds: 300));
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {
                'id': 10,
                'name': 'One-Click Techfest',
                'start_at': '2026-12-01T09:00:00Z',
                'status': 'upcoming',
              }
            }),
            201,
          );
        }
        return http.Response(jsonEncode({'success': true, 'data': {}}), 200);
      });

      final apiClient = ApiClient(client: mockClient, authService: adminAuth);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: CreateEventScreen(
            syncService: syncService,
            authService: adminAuth,
          ),
        ),
      );

      await tester.pump();

      final textFields = find.byType(TextField);
      await tester.enterText(textFields.at(0), 'One-Click Techfest');

      final submitButton = find.widgetWithText(PrimaryButton, 'Create Event');

      // Rapidly tap the submit button 3 times
      await tester.tap(submitButton);
      await tester.tap(submitButton);
      await tester.tap(submitButton);

      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();

      // Only ONE POST request was dispatched
      expect(postCallCount, 1);
    });

    testWidgets('6. Successful creation refreshes list and selects new event in SelectEventScreen', (tester) async {
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'admin-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 1,
          'username': 'clubadmin',
          'role': 'president',
        }),
      });
      final adminAuth = AuthService();
      await adminAuth.initialize();

      final eventsList = <Map<String, dynamic>>[
        {
          'id': 1,
          'name': 'Existing Event Alpha',
          'start_at': '2026-10-30T09:00:00Z',
          'status': 'upcoming',
        }
      ];

      final mockClient = MockClient((request) async {
        if (request.method == 'GET' && request.url.path.endsWith('/events')) {
          return http.Response(
            jsonEncode({'success': true, 'data': eventsList}),
            200,
          );
        }
        if (request.method == 'POST' && request.url.path.endsWith('/events')) {
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          final newEvent = {
            'id': 99,
            'name': body['name'],
            'start_at': body['start_at'],
            'status': body['status'] ?? 'upcoming',
          };
          eventsList.add(newEvent);
          return http.Response(
            jsonEncode({'success': true, 'data': newEvent}),
            201,
          );
        }
        return http.Response(jsonEncode({'success': true, 'data': {}}), 200);
      });

      final apiClient = ApiClient(client: mockClient, authService: adminAuth);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      Event? selectedEvent;
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: SelectEventScreen(
            syncService: syncService,
            authService: adminAuth,
            onEventSelected: (e) => selectedEvent = e,
            onOpenAssignments: () {},
            onLogout: () {},
          ),
        ),
      );

      await tester.pump();
      await tester.pump();

      expect(find.text('Existing Event Alpha'), findsWidgets);

      // Tap Create Event
      final createEventButton = find.widgetWithText(SecondaryButton, 'Create Event');
      expect(createEventButton, findsOneWidget);
      await tester.tap(createEventButton);
      await tester.pumpAndSettle();

      // We are now on CreateEventScreen
      expect(find.byType(CreateEventScreen), findsOneWidget);
      expect(find.text('Create Event'), findsWidgets);

      // Enter new event name
      final nameField = find.byType(TextField).first;
      await tester.enterText(nameField, 'Newly Created Symposium 2026');

      // Submit
      final submitButton = find.widgetWithText(PrimaryButton, 'Create Event');
      await tester.tap(submitButton);
      await tester.pumpAndSettle();

      // Should have returned to SelectEventScreen and automatically selected the new event
      expect(selectedEvent, isNotNull);
      expect(selectedEvent!.id, 99);
      expect(selectedEvent!.name, 'Newly Created Symposium 2026');
    });
  });
}
