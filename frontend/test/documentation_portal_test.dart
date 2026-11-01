import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/screens/documentation_portal_screen.dart';
import 'package:mobile/screens/activity_report_editor_screen.dart';
import 'package:mobile/services/api_client.dart';
import 'package:mobile/services/auth_service.dart';
import 'package:mobile/services/documentation_service.dart';
import 'package:mobile/services/sync_service.dart';
import 'package:mobile/services/storage_service.dart';

class MockApiClient extends ApiClient {
  MockApiClient({required super.authService});

  @override
  Future<dynamic> get(String endpoint, {Map<String, String>? queryParams, bool requiresAuth = true}) async {
    if (endpoint == '/documentation/folders') {
      return [
        {
          'id': 1,
          'name': 'AI Workshop Folder',
          'description': 'Master materials',
          'document_count': 2,
          'created_by_id': 10,
          'created_by_name': 'Surasmita',
          'created_at': '2026-03-25T10:00:00',
          'updated_at': '2026-03-25T10:00:00',
        }
      ];
    } else if (endpoint == '/documentation/reports') {
      return [
        {
          'id': 1,
          'title': 'Quantum Computing Session',
          'status': 'draft',
          'created_by_id': 10,
          'created_by_name': 'Surasmita',
          'data': {},
          'created_at': '2026-03-25T10:00:00',
          'updated_at': '2026-03-25T10:00:00',
        }
      ];
    } else if (endpoint == '/documentation/ai/models') {
      return [
        {
          'provider': 'gemini',
          'name': 'Gemini 3.5 Flash',
          'model': 'gemini-3.5-flash',
          'is_configured': true,
          'is_default': true,
        },
        {
          'provider': 'grok',
          'name': 'Grok / Groq LPU',
          'model': 'qwen/qwen3.8-27b',
          'is_configured': true,
          'is_default': false,
        },
      ];
    } else if (endpoint.startsWith('/documentation/reports/1')) {
      return {
        'id': 1,
        'title': 'Quantum Computing Session',
        'status': 'draft',
        'created_by_id': 10,
        'created_by_name': 'Surasmita',
        'data': {
          'general_information': {
            'type_of_activity': 'Workshop',
            'title_of_activity': 'Quantum Computing Session',
            'venue': 'Audi 2',
          },
          'speakers': [
            {
              'name': 'Dr. Feynman',
              'title': 'Keynote Speaker',
              'organization': 'Caltech',
              'contact': 'feynman@caltech.edu',
            }
          ],
          'participants': {
            'type_of_participants': 'UG Students',
            'summary': 'Intro to qubits.',
          },
        },
        'created_at': '2026-03-25T10:00:00',
        'updated_at': '2026-03-25T10:00:00',
      };
    }
    return [];
  }

  @override
  Future<dynamic> post(String endpoint, {Map<String, dynamic>? body, bool requiresAuth = true}) async {
    if (endpoint.contains('ai-assist')) {
      return {
        'generated_text': 'AI Generated formal summary of quantum workshop.',
        'field_key': body?['field_key'],
        'provider': 'Gemini AI',
      };
    }
    return {'id': 2, 'title': 'New Draft', 'name': 'New Folder', 'status': 'draft', 'document_count': 0};
  }

  @override
  Future<dynamic> put(String endpoint, {Map<String, dynamic>? body, bool requiresAuth = true}) async {
    return {'id': 1, 'title': body?['title'] ?? 'Updated', 'status': 'draft'};
  }
}

class MockAuthService extends AuthService {
  final Map<String, dynamic> user;

  MockAuthService({required this.user});

  @override
  bool get isAuthenticated => true;

  @override
  Map<String, dynamic>? get currentUser => user;

  @override
  String get username => user['username']?.toString() ?? 'surasmita';

  @override
  String get userRole => user['role']?.toString() ?? 'member';

  @override
  String? get teamName => user['team_name']?.toString() ?? 'Documentation';

  @override
  int? get teamId => (user['team_id'] as num?)?.toInt() ?? 2;

  @override
  String get displayName => user['member_name']?.toString() ?? 'Surasmita';
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Documentation Team Role & Portal Tests', () {
    test('1. AuthService correctly identifies Documentation Team member', () {
      final docUser = MockAuthService(user: {
        'id': 10,
        'username': 'surasmita',
        'role': 'member',
        'team_id': 2,
        'team_name': 'Documentation',
        'member_name': 'Surasmita',
      });

      expect(docUser.isDocumentationTeam, isTrue);
      expect(docUser.canAccessDocumentation, isTrue);
      expect(docUser.isVolunteer, isFalse);
      expect(docUser.isAdmin, isFalse);

      final volUser = MockAuthService(user: {
        'id': 11,
        'username': 'sagar.cu',
        'role': 'member',
        'team_id': 1,
        'team_name': 'Volunteering',
        'member_name': 'Sagar CU',
      });

      expect(volUser.isDocumentationTeam, isFalse);
      expect(volUser.canAccessDocumentation, isFalse);
      expect(volUser.isVolunteer, isTrue);

      final adminUser = MockAuthService(user: {
        'id': 1,
        'username': 'clubadmin',
        'role': 'president',
        'team_id': null,
        'team_name': null,
      });

      expect(adminUser.isAdmin, isTrue);
      expect(adminUser.canAccessDocumentation, isTrue);
    });

    testWidgets('2. DocumentationPortalScreen renders tabs and loads workspace', (tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.resetPhysicalSize());

      final authService = MockAuthService(user: {
        'id': 10,
        'username': 'surasmita',
        'role': 'member',
        'team_id': 2,
        'team_name': 'Documentation',
        'member_name': 'Surasmita',
      });

      final apiClient = MockApiClient(authService: authService);
      final syncService = SyncService(
        apiClient: apiClient,
        storageService: StorageService(),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: DocumentationPortalScreen(
            authService: authService,
            syncService: syncService,
            onLogout: () {},
          ),
        ),
      );

      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // Check app bar title & tabs
      expect(find.text('Documentation Portal'), findsOneWidget);
      expect(find.text('Surasmita'), findsOneWidget);
      expect(find.text('Event Documents'), findsOneWidget);
      expect(find.text('AI Report Generator'), findsOneWidget);

      // Check workspace contents
      expect(find.text('Documentation Workspace'), findsOneWidget);
      expect(find.text('AI Workshop Folder'), findsOneWidget);

      // Switch to AI Report Generator Tab
      await tester.tap(find.text('AI Report Generator'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      expect(find.text('AI-Assisted Report Generator'), findsOneWidget);
      expect(find.text('Quantum Computing Session'), findsOneWidget);
      expect(find.text('Open Editor'), findsOneWidget);
    });

    testWidgets('3. ActivityReportEditorScreen renders two-panel GUI and dynamic speakers', (tester) async {
      tester.view.physicalSize = const Size(1400, 900);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.resetPhysicalSize());

      final authService = MockAuthService(user: {
        'id': 10,
        'username': 'surasmita',
        'role': 'member',
        'team_id': 2,
        'team_name': 'Documentation',
        'member_name': 'Surasmita',
      });

      final apiClient = MockApiClient(authService: authService);
      final docService = DocumentationService(apiClient: apiClient);

      await tester.pumpWidget(
        MaterialApp(
          home: ActivityReportEditorScreen(
            reportId: 1,
            docService: docService,
            authService: authService,
          ),
        ),
      );

      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // Left panel: AI Copilot
      expect(find.text('AI Report Copilot'), findsOneWidget);
      expect(find.text('Draft Content'), findsOneWidget);
      expect(find.text('Improve & Polish'), findsOneWidget);

      // Model Engine Switcher
      expect(find.text('Gemini 3.5 Flash'), findsOneWidget);
      expect(find.text('Grok / Groq LPU'), findsOneWidget);

      // Switch to Grok
      await tester.tap(find.text('Grok / Groq LPU'));
      await tester.pump();

      // Switch back to Gemini
      await tester.tap(find.text('Gemini 3.5 Flash'));
      await tester.pump();

      // Right panel: Section 1 & 2
      expect(find.text('1. General Information'), findsOneWidget);
      expect(find.text('2. Speaker Details'), findsOneWidget);
      expect(find.text('Dr. Feynman'), findsOneWidget);

      // Add another dynamic speaker
      await tester.ensureVisible(find.text('Add Another Speaker'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Add Another Speaker'));
      await tester.pumpAndSettle();

      expect(find.text('Speaker #2'), findsOneWidget);

      // Trigger AI Copilot assist
      await tester.ensureVisible(find.text('Generate / Polish Content'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Generate / Polish Content'));
      await tester.pumpAndSettle();

      // Scroll AI panel down so output is rendered
      await tester.drag(find.text('AI Report Copilot'), const Offset(0, -400));
      await tester.pumpAndSettle();

      expect(find.text('AI Generated formal summary of quantum workshop.'), findsOneWidget);

      expect(find.text('AI Generated formal summary of quantum workshop.'), findsOneWidget);
      expect(find.text('Insert'), findsOneWidget);

      // Insert AI content into form
      await tester.ensureVisible(find.text('Insert'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Insert'));
      await tester.pump();
    });
  });
}
