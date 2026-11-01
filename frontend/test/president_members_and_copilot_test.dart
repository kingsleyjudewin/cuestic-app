import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/config/app_theme.dart';
import 'package:mobile/config/constants.dart';
import 'package:mobile/models/member.dart';
import 'package:mobile/models/team.dart';
import 'package:mobile/screens/documentation_portal_screen.dart';
import 'package:mobile/screens/manage_members_screen.dart';
import 'package:mobile/services/api_client.dart';
import 'package:mobile/services/auth_service.dart';
import 'package:mobile/services/storage_service.dart';
import 'package:mobile/services/sync_service.dart';

class TestStorageService extends StorageService {
  List<Team> teamsList = [];
  Map<int, List<Member>> membersMap = {};

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

  group('President Manage Members & AI Copilot Enhancements', () {
    late TestStorageService storageService;

    setUp(() {
      storageService = TestStorageService();
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'president-test-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 1,
          'username': 'clubadmin',
          'role': 'president',
          'member_name': 'Club President',
        }),
      });
    });

    testWidgets('1. ManageMembersScreen renders Users section and displays Email ID', (tester) async {
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
        } else if (request.url.path.endsWith('/members')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {
                  'id': 101,
                  'full_name': 'Arjun Nair',
                  'email': 'arjun@cuestic.edu',
                  'registration_number': 'REG2026-101',
                  'class_name': '3rd Year CSE',
                  'section': 'A',
                  'phone_number': '+919876543210',
                  'team_id': 1,
                  'team_name': 'Volunteering',
                  'linked_user_id': 201,
                  'linked_user': {
                    'id': 201,
                    'username': 'arjun_nair',
                    'email': 'arjun@cuestic.edu',
                    'role': 'member',
                    'is_active': true,
                  },
                  'is_active': true,
                },
                {
                  'id': 102,
                  'full_name': 'Kavya Volunteer',
                  'email': null,
                  'registration_number': 'REG2026-102',
                  'class_name': '2nd Year ECE',
                  'section': 'B',
                  'phone_number': '+919876543211',
                  'team_id': 1,
                  'team_name': 'Volunteering',
                  'linked_user_id': null,
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

      // Verify Users section header
      expect(find.text('Users'), findsOneWidget);
      expect(find.text('2 members'), findsOneWidget);

      // Verify Arjun Nair with email
      expect(find.text('Arjun Nair'), findsOneWidget);
      expect(find.text('arjun@cuestic.edu'), findsOneWidget);

      // Verify Kavya Volunteer without email indicates edit to add
      expect(find.text('Kavya Volunteer'), findsOneWidget);
      expect(find.text('No Email ID (Edit to add)'), findsOneWidget);
    });

    testWidgets('2. Edit dialog allows setting email and role escalation by President', (tester) async {
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final authService = AuthService();
      await authService.initialize();

      bool patchCalled = false;
      Map<String, dynamic>? patchBody;

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
        } else if (request.url.path.endsWith('/members/101') && request.method == 'PATCH') {
          patchCalled = true;
          patchBody = jsonDecode(request.body) as Map<String, dynamic>;
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {
                'id': 101,
                'full_name': 'Arjun Nair Updated',
                'email': 'arjun.updated@cuestic.edu',
                'registration_number': 'REG2026-101',
                'class_name': '3rd Year CSE',
                'phone_number': '+919876543210',
                'team_id': 1,
                'linked_user_id': 201,
                'linked_user': {
                  'id': 201,
                  'username': 'arjun_nair',
                  'email': 'arjun.updated@cuestic.edu',
                  'role': 'admin',
                  'is_active': true,
                },
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
                  'id': 101,
                  'full_name': 'Arjun Nair',
                  'email': 'arjun@cuestic.edu',
                  'registration_number': 'REG2026-101',
                  'class_name': '3rd Year CSE',
                  'phone_number': '+919876543210',
                  'team_id': 1,
                  'linked_user_id': 201,
                  'linked_user': {
                    'id': 201,
                    'username': 'arjun_nair',
                    'email': 'arjun@cuestic.edu',
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

      // Tap on member card to edit
      await tester.tap(find.text('Arjun Nair'));
      await tester.pumpAndSettle();

      expect(find.text('Edit Details: Arjun Nair'), findsOneWidget);
      expect(find.text('Email ID'), findsOneWidget);
      expect(find.text('Role (President Managed)'), findsOneWidget);
      expect(find.byKey(const Key('btn_edit_dialog_reset_password')), findsOneWidget);

      // Change email
      await tester.enterText(
        find.widgetWithText(TextField, 'arjun@cuestic.edu'),
        'arjun.updated@cuestic.edu',
      );

      // Change role to Administrator
      await tester.tap(find.text('Member / Volunteer'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Administrator').last);
      await tester.pumpAndSettle();

      // Save changes
      await tester.tap(find.byKey(const Key('btn_confirm_edit_member')));
      await tester.pumpAndSettle();

      expect(patchCalled, isTrue);
      expect(patchBody?['email'], 'arjun.updated@cuestic.edu');
      expect(patchBody?['role'], 'admin');
    });

    testWidgets('3. DocumentationPortalScreen renders AI Copilot FAB and opens Copilot Assistant', (tester) async {
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final authService = AuthService();
      await authService.initialize();

      bool aiAssistCalled = false;

      final mockClient = MockClient((request) async {
        if (request.url.path.endsWith('/folders')) {
          return http.Response(jsonEncode({'success': true, 'data': []}), 200);
        } else if (request.url.path.endsWith('/reports')) {
          return http.Response(jsonEncode({'success': true, 'data': []}), 200);
        } else if (request.url.path.endsWith('/ai-assist') && request.method == 'POST') {
          aiAssistCalled = true;
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {
                'generated_text': 'This is an institutional activity report drafted by AI Copilot.',
                'provider': 'grok',
                'model': 'qwen/qwen3.8-27b',
              },
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
          home: DocumentationPortalScreen(
            authService: authService,
            syncService: syncService,
            onLogout: () {},
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Find AI Copilot FAB
      expect(find.byKey(const Key('fab_doc_ai_copilot')), findsOneWidget);
      expect(find.byKey(const Key('btn_doc_portal_ai_copilot')), findsOneWidget);

      // Tap AI Copilot FAB
      await tester.tap(find.byKey(const Key('fab_doc_ai_copilot')));
      await tester.pumpAndSettle();

      // Verify AI Copilot sheet
      expect(find.text('Documentation AI Copilot'), findsOneWidget);
      expect(find.text('Draft Section'), findsOneWidget);
      expect(find.text('Ask Documentation Copilot'), findsOneWidget);

      // Enter prompt
      await tester.enterText(
        find.widgetWithText(TextField, 'e.g. Workshop on Embedded IoT Architecture organized by CUestIC on 25 Nov with 45 participants and hands-on sensor kit demos...'),
        'Draft an overview of Quantum Computing Seminar with 50 students.',
      );

      // Tap run button
      await tester.ensureVisible(find.byKey(const Key('btn_run_doc_copilot')));
      await tester.tap(find.byKey(const Key('btn_run_doc_copilot')));
      await tester.pumpAndSettle();

      expect(aiAssistCalled, isTrue);
      expect(find.text('This is an institutional activity report drafted by AI Copilot.'), findsOneWidget);
      expect(find.text('Copy Text'), findsOneWidget);
      expect(find.text('Create Report'), findsOneWidget);
    });
  });
}
