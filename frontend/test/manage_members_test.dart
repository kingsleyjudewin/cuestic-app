import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/config/app_theme.dart';
import 'package:mobile/config/constants.dart';
import 'package:mobile/models/event.dart';
import 'package:mobile/models/member.dart';
import 'package:mobile/models/team.dart';
import 'package:mobile/screens/create_member_account_screen.dart';
import 'package:mobile/screens/manage_members_screen.dart';
import 'package:mobile/screens/select_event_screen.dart';
import 'package:mobile/services/api_client.dart';
import 'package:mobile/services/auth_service.dart';
import 'package:mobile/services/storage_service.dart';
import 'package:mobile/services/sync_service.dart';

class TestStorageService extends StorageService {
  List<Event> eventsList = [];
  List<Team> teamsList = [];
  Map<int, List<Member>> membersMap = {};

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
}

void main() {
  setUpAll(() {
    TestWidgetsFlutterBinding.ensureInitialized();
  });

  group('President Member Account Management Tests', () {
    late TestStorageService storageService;

    setUp(() {
      storageService = TestStorageService();
    });

    testWidgets('1. President sees Manage Members entry points on SelectEventScreen; ordinary member does not', (tester) async {
      // 1a. President user
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'president-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 1,
          'username': 'club_president',
          'role': 'president',
        }),
      });
      final presAuth = AuthService();
      await presAuth.initialize();

      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'success': true,
            'data': [
              {
                'id': 1,
                'name': 'Club Symposium',
                'start_at': '2026-11-01T10:00:00Z',
                'status': 'upcoming',
              }
            ]
          }),
          200,
        );
      });

      final apiClient = ApiClient(client: mockClient, authService: presAuth);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: SelectEventScreen(
            syncService: syncService,
            authService: presAuth,
            onEventSelected: (_) {},
            onOpenAssignments: () {},
            onLogout: () {},
          ),
        ),
      );

      await tester.pumpAndSettle();

      // President sees Manage Members in AppBar and screen body
      expect(find.byKey(const Key('btn_manage_members_appbar')), findsOneWidget);
      expect(find.byKey(const Key('btn_manage_members_screen')), findsOneWidget);

      // 1b. Ordinary member user
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'member-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 2,
          'username': 'regular_member',
          'role': 'member',
        }),
      });
      final memberAuth = AuthService();
      await memberAuth.initialize();

      final memberSyncService = SyncService(
        apiClient: ApiClient(client: mockClient, authService: memberAuth),
        storageService: storageService,
      );

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

      await tester.pumpAndSettle();

      // Ordinary member should NOT see Manage Members
      expect(find.byKey(const Key('btn_manage_members_appbar')), findsNothing);
      expect(find.byKey(const Key('btn_manage_members_screen')), findsNothing);
    });

    testWidgets('2. ManageMembersScreen renders teams, member directory, and account badges', (tester) async {
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'president-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 1,
          'username': 'club_president',
          'role': 'president',
        }),
      });
      final authService = AuthService();
      await authService.initialize();

      final mockClient = MockClient((request) async {
        if (request.url.path.endsWith('/teams')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {'id': 1, 'name': 'Volunteering', 'slug': 'volunteering'},
                {'id': 2, 'name': 'Documentation', 'slug': 'documentation'},
                {'id': 3, 'name': 'Media', 'slug': 'media'},
                {'id': 4, 'name': 'Logistics', 'slug': 'logistics'},
              ],
            }),
            200,
          );
        } else if (request.url.path.endsWith('/members')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {
                  'id': 10,
                  'full_name': 'Rohan Lead',
                  'registration_number': 'REG2026-010',
                  'class_name': '3rd Year CSE',
                  'section': 'A',
                  'phone_number': '+919876543210',
                  'team_id': 1,
                  'team_name': 'Volunteering',
                  'linked_user_id': 50,
                  'linked_user': {
                    'id': 50,
                    'username': 'rohan_lead',
                    'email': 'rohan@test.edu',
                    'role': 'team_leader',
                    'is_active': true,
                  },
                  'is_active': true,
                },
                {
                  'id': 11,
                  'full_name': 'Pooja Member',
                  'registration_number': 'REG2026-011',
                  'class_name': '2nd Year ECE',
                  'section': 'B',
                  'phone_number': '+919876543211',
                  'team_id': 2,
                  'team_name': 'Documentation',
                  'linked_user_id': null,
                  'is_active': true,
                },
              ],
            }),
            200,
          );
        }
        return http.Response('{"error": "not found"}', 404);
      });

      final syncService = SyncService(
        apiClient: ApiClient(client: mockClient, authService: authService),
        storageService: storageService,
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: ManageMembersScreen(
            syncService: syncService,
            authService: authService,
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Check header
      expect(find.text('Manage Members'), findsOneWidget);

      // Check Team chips
      expect(find.text('All Teams'), findsOneWidget);
      expect(find.text('Volunteering'), findsWidgets);
      expect(find.text('Documentation'), findsWidgets);
      expect(find.text('Media'), findsOneWidget);
      expect(find.text('Logistics'), findsOneWidget);

      // Check member directory cards
      expect(find.text('Rohan Lead'), findsOneWidget);
      expect(find.text('LEADER'), findsOneWidget);
      expect(find.text('@rohan_lead'), findsOneWidget);

      expect(find.text('Pooja Member'), findsOneWidget);
      expect(find.text('No Login Account'), findsOneWidget);
    });

    testWidgets('3. CreateMemberAccountScreen validates inputs before submitting', (tester) async {
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'president-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 1,
          'username': 'club_president',
          'role': 'president',
        }),
      });
      final authService = AuthService();
      await authService.initialize();

      final mockClient = MockClient((request) async {
        if (request.url.path.endsWith('/teams')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {'id': 1, 'name': 'Volunteering', 'slug': 'volunteering'},
              ],
            }),
            200,
          );
        }
        return http.Response('{}', 200);
      });

      final syncService = SyncService(
        apiClient: ApiClient(client: mockClient, authService: authService),
        storageService: storageService,
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: CreateMemberAccountScreen(
            syncService: syncService,
            authService: authService,
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Clear the pre-generated password to test required password validation
      await tester.enterText(find.byKey(const Key('input_password')), '');
      await tester.pump();

      // Tap submit with empty fields
      await tester.ensureVisible(find.byKey(const Key('btn_submit_create_account')));
      await tester.ensureVisible(find.byKey(const Key('btn_submit_create_account')));
      await tester.tap(find.byKey(const Key('btn_submit_create_account')));
      await tester.pumpAndSettle();

      // Verify field validation errors
      expect(find.text('Full name is required.'), findsOneWidget);
      expect(find.text('Class / Year is required.'), findsOneWidget);
      expect(find.text('Phone number is required.'), findsOneWidget);
      expect(find.text('Username is required.'), findsOneWidget);
      expect(find.text('Email address is required.'), findsOneWidget);
      expect(find.text('Temporary password is required.'), findsOneWidget);
    });

    testWidgets('4. CreateMemberAccountScreen successfully creates member and shows confirmation dialog', (tester) async {
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'president-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 1,
          'username': 'club_president',
          'role': 'president',
        }),
      });
      final authService = AuthService();
      await authService.initialize();

      bool apiCalled = false;
      Map<String, dynamic>? receivedPayload;

      final mockClient = MockClient((request) async {
        if (request.url.path.endsWith('/teams')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {'id': 1, 'name': 'Volunteering', 'slug': 'volunteering'},
                {'id': 2, 'name': 'Documentation', 'slug': 'documentation'},
              ],
            }),
            200,
          );
        } else if (request.url.path.endsWith('/members/account')) {
          apiCalled = true;
          receivedPayload = jsonDecode(request.body) as Map<String, dynamic>;
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {
                'member': {
                  'id': 99,
                  'full_name': receivedPayload!['full_name'],
                  'class_name': receivedPayload!['class_name'],
                  'phone_number': receivedPayload!['phone_number'],
                  'team_id': receivedPayload!['team_id'],
                  'linked_user_id': 199,
                  'linked_user': {
                    'id': 199,
                    'username': receivedPayload!['username'],
                    'email': receivedPayload!['email'],
                    'role': receivedPayload!['role'],
                    'is_active': true,
                  },
                },
                'user': {
                  'id': 199,
                  'username': receivedPayload!['username'],
                  'email': receivedPayload!['email'],
                  'role': receivedPayload!['role'],
                },
              },
            }),
            201,
          );
        }
        return http.Response('{}', 200);
      });

      final syncService = SyncService(
        apiClient: ApiClient(client: mockClient, authService: authService),
        storageService: storageService,
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: CreateMemberAccountScreen(
            syncService: syncService,
            authService: authService,
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Enter valid form details
      await tester.enterText(find.byKey(const Key('input_full_name')), 'Aarav Gupta');
      await tester.enterText(find.byKey(const Key('input_class_name')), '3rd Year CSE');
      await tester.enterText(find.byKey(const Key('input_phone_number')), '9876500055');
      await tester.enterText(find.byKey(const Key('input_username')), 'aarav_gupta');
      await tester.enterText(find.byKey(const Key('input_email')), 'aarav@university.edu');
      await tester.enterText(find.byKey(const Key('input_password')), 'SecurePass123!');

      await tester.pump();

      // Submit form
      await tester.ensureVisible(find.byKey(const Key('btn_submit_create_account')));
      await tester.ensureVisible(find.byKey(const Key('btn_submit_create_account')));
      await tester.tap(find.byKey(const Key('btn_submit_create_account')));
      await tester.pumpAndSettle();

      // Verify API was called with correct payload
      expect(apiCalled, isTrue);
      expect(receivedPayload!['full_name'], equals('Aarav Gupta'));
      expect(receivedPayload!['username'], equals('aarav_gupta'));
      expect(receivedPayload!['email'], equals('aarav@university.edu'));
      expect(receivedPayload!['role'], equals('member'));

      // Verify confirmation dialog
      expect(find.text('Account Created'), findsOneWidget);
      expect(find.descendant(of: find.byType(AlertDialog), matching: find.text('aarav_gupta')), findsOneWidget);
      expect(find.text('Done'), findsOneWidget);
    });

    testWidgets('5. Server duplicate conflict displays specific error and preserves form values', (tester) async {
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'president-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 1,
          'username': 'club_president',
          'role': 'president',
        }),
      });
      final authService = AuthService();
      await authService.initialize();

      final mockClient = MockClient((request) async {
        if (request.url.path.endsWith('/teams')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {'id': 1, 'name': 'Volunteering', 'slug': 'volunteering'},
              ],
            }),
            200,
          );
        } else if (request.url.path.endsWith('/members/account')) {
          return http.Response(
            jsonEncode({
              'success': false,
              'error': {
                'code': 'CONFLICT',
                'message': 'Username is already taken by another account.',
                'details': {
                  'username': 'Username is already in use.',
                },
              },
            }),
            409,
          );
        }
        return http.Response('{}', 200);
      });

      final syncService = SyncService(
        apiClient: ApiClient(client: mockClient, authService: authService),
        storageService: storageService,
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: CreateMemberAccountScreen(
            syncService: syncService,
            authService: authService,
          ),
        ),
      );

      await tester.pumpAndSettle();

      await tester.enterText(find.byKey(const Key('input_full_name')), 'Duplicate Person');
      await tester.enterText(find.byKey(const Key('input_class_name')), '2nd Year');
      await tester.enterText(find.byKey(const Key('input_phone_number')), '9876543299');
      await tester.enterText(find.byKey(const Key('input_username')), 'taken_user');
      await tester.enterText(find.byKey(const Key('input_email')), 'taken@test.edu');
      await tester.enterText(find.byKey(const Key('input_password')), 'Password123!');

      await tester.ensureVisible(find.byKey(const Key('btn_submit_create_account')));
      await tester.tap(find.byKey(const Key('btn_submit_create_account')));
      await tester.pumpAndSettle();

      // Field error displayed
      expect(find.text('Username is already in use.'), findsOneWidget);

      // Entered values preserved
      expect(find.text('Duplicate Person'), findsOneWidget);
      expect(find.text('taken_user'), findsOneWidget);
    });

    testWidgets('6. Password reset flow prompts President and triggers backend reset', (tester) async {
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'president-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 1,
          'username': 'club_president',
          'role': 'president',
        }),
      });
      final authService = AuthService();
      await authService.initialize();

      bool resetApiCalled = false;

      final mockClient = MockClient((request) async {
        if (request.url.path.endsWith('/teams')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {'id': 1, 'name': 'Volunteering', 'slug': 'volunteering'},
              ],
            }),
            200,
          );
        } else if (request.url.path.endsWith('/members')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {
                  'id': 15,
                  'full_name': 'Meera Sen',
                  'class_name': '3rd Year',
                  'phone_number': '+919876543299',
                  'team_id': 1,
                  'linked_user_id': 88,
                  'linked_user': {
                    'id': 88,
                    'username': 'meera_sen',
                    'email': 'meera@test.edu',
                    'role': 'member',
                    'is_active': true,
                  },
                  'is_active': true,
                },
              ],
            }),
            200,
          );
        } else if (request.url.path.endsWith('/members/15/reset-password')) {
          resetApiCalled = true;
          return http.Response(
            jsonEncode({
              'success': true,
              'message': 'Password reset successfully.',
            }),
            200,
          );
        }
        return http.Response('{}', 200);
      });

      final syncService = SyncService(
        apiClient: ApiClient(client: mockClient, authService: authService),
        storageService: storageService,
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: ManageMembersScreen(
            syncService: syncService,
            authService: authService,
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Meera Sen'), findsOneWidget);

      // Open popup menu for Meera Sen
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();

      // Tap Reset Password option
      await tester.tap(find.text('Reset Password'));
      await tester.pumpAndSettle();

      // Check reset dialog
      expect(find.text('Reset Password for Meera Sen'), findsOneWidget);
      expect(find.text('Account: @meera_sen'), findsOneWidget);

      // Submit password reset
      await tester.tap(find.byKey(const Key('btn_confirm_reset_password')));
      await tester.pumpAndSettle();

      expect(resetApiCalled, isTrue);
      expect(find.text('Password reset successfully for Meera Sen.'), findsOneWidget);
    });

    testWidgets('7. Edit member details flow allows updating name, class, registration number, and team', (tester) async {
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'president-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 1,
          'username': 'club_president',
          'role': 'president',
        }),
      });
      final authService = AuthService();
      await authService.initialize();

      bool patchApiCalled = false;
      Map<String, dynamic>? patchBody;

      final mockClient = MockClient((request) async {
        if (request.url.path.endsWith('/teams')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {'id': 1, 'name': 'Volunteering', 'slug': 'volunteering'},
                {'id': 2, 'name': 'Documentation', 'slug': 'documentation'},
              ],
            }),
            200,
          );
        } else if (request.url.path.endsWith('/members/15') && request.method == 'PATCH') {
          patchApiCalled = true;
          patchBody = jsonDecode(request.body) as Map<String, dynamic>;
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {
                'id': 15,
                'full_name': patchBody?['full_name'] ?? 'Meera Sen Updated',
                'registration_number': patchBody?['registration_number'] ?? 'REG2026-999',
                'class_name': patchBody?['class_name'] ?? '4th Year',
                'section': patchBody?['section'],
                'phone_number': patchBody?['phone_number'] ?? '+919876543299',
                'team_id': patchBody?['team_id'] ?? 1,
                'linked_user_id': 88,
                'is_active': true,
              },
            }),
            200,
          );
        } else if (request.url.path.endsWith('/members')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {
                  'id': 15,
                  'full_name': 'Meera Sen',
                  'class_name': '3rd Year',
                  'phone_number': '+919876543299',
                  'team_id': 1,
                  'linked_user_id': 88,
                  'linked_user': {
                    'id': 88,
                    'username': 'meera_sen',
                    'email': 'meera@test.edu',
                    'role': 'member',
                    'is_active': true,
                  },
                  'is_active': true,
                },
              ],
            }),
            200,
          );
        }
        return http.Response('{}', 200);
      });

      final syncService = SyncService(
        apiClient: ApiClient(client: mockClient, authService: authService),
        storageService: storageService,
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: ManageMembersScreen(
            syncService: syncService,
            authService: authService,
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Meera Sen'), findsOneWidget);

      // Open Edit Dialog via edit icon button
      await tester.tap(find.byIcon(Icons.edit_outlined).first);
      await tester.pumpAndSettle();

      // Check edit dialog rendered
      expect(find.text('Edit Details: Meera Sen'), findsOneWidget);
      expect(find.text('Registration Number / Student ID'), findsOneWidget);

      // Enter registration number
      await tester.enterText(
        find.widgetWithText(TextField, 'e.g. 2460635 or REG2026-101'),
        'REG2026-999',
      );

      // Save changes
      await tester.tap(find.byKey(const Key('btn_confirm_edit_member')));
      await tester.pumpAndSettle();

      expect(patchApiCalled, isTrue);
      expect(patchBody?['registration_number'], 'REG2026-999');
      expect(patchBody?['full_name'], 'Meera Sen');
      expect(find.text('Details updated for Meera Sen.'), findsOneWidget);
    });
  });
}
