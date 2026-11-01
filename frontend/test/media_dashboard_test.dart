import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/config/app_theme.dart';
import 'package:mobile/models/media.dart';
import 'package:mobile/screens/event_media_folder_screen.dart';
import 'package:mobile/screens/media_dashboard_screen.dart';
import 'package:mobile/services/api_client.dart';
import 'package:mobile/services/auth_service.dart';
import 'package:mobile/services/media_service.dart';
import 'package:mobile/services/storage_service.dart';
import 'package:mobile/services/sync_service.dart';

class MockMediaAuthService extends AuthService {
  final Map<String, dynamic> user;

  MockMediaAuthService({required this.user});

  @override
  bool get isAuthenticated => true;

  @override
  Map<String, dynamic>? get currentUser => user;

  @override
  String get username => user['username']?.toString() ?? 'arpitha.cu';

  @override
  String get userRole => user['role']?.toString() ?? 'member';

  @override
  String? get teamName => user['team_name']?.toString() ?? 'Media';

  @override
  int? get teamId => (user['team_id'] as num?)?.toInt() ?? 3;

  @override
  String get displayName => user['member_name']?.toString() ?? 'Arpitha CU';

  @override
  Future<String?> getConfiguredBaseUrl() async => 'http://localhost:5000/api/v1';

  @override
  Future<String?> getToken() async => 'mock-jwt-token';
}

class FakeStorageService extends StorageService {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  final mockFolderData = {
    'id': 101,
    'name': 'Annual Tech Fest 2026',
    'description': 'Main stage and hackathon coverage',
    'event_date': '2026-04-15',
    'created_by_name': 'Arpitha CU',
    'created_at': '2026-03-25T10:00:00',
    'updated_at': '2026-03-25T10:00:00',
    'photos_count': 12,
    'videos_count': 3,
    'posters_count': 4,
    'geotagged_count': 8,
    'storage_source': 'Firebase',
    'linked_drive_folder_id': null,
    'linked_drive_folder_name': null,
  };

  group('Media Team Role & Portal Tests', () {
    test('1. AuthService correctly identifies Media Team members', () {
      final mediaMember = MockMediaAuthService(user: {
        'id': 15,
        'username': 'arpitha.cu',
        'role': 'member',
        'team_id': 3,
        'team_name': 'Media',
        'member_name': 'Arpitha CU',
      });

      expect(mediaMember.isMediaTeam, isTrue);
      expect(mediaMember.isVolunteer, isFalse);
      expect(mediaMember.isDocumentationTeam, isFalse);
      expect(mediaMember.isAdmin, isFalse);
      expect(mediaMember.displayName, equals('Arpitha CU'));
      expect(mediaMember.username, equals('arpitha.cu'));
    });

    testWidgets('2. MediaDashboardScreen renders profile, Drive status, and event folders', (tester) async {
      tester.view.physicalSize = const Size(1200, 900);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.resetPhysicalSize());

      bool onLogoutCalled = false;

      final authService = MockMediaAuthService(user: {
        'id': 15,
        'username': 'arpitha.cu',
        'email': 'arpitha.cu@gmail.com',
        'role': 'member',
        'team_id': 3,
        'team_name': 'Media',
        'member_name': 'Arpitha CU',
      });

      final mockClient = MockClient((request) async {
        if (request.url.path.contains('/media/drive/status')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {
                'is_connected': false,
                'email': null,
                'folder_id': null,
              },
            }),
            200,
          );
        }
        if (request.url.path.contains('/media/folders')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [mockFolderData],
            }),
            200,
          );
        }
        return http.Response(jsonEncode({'success': true, 'data': {}}), 200);
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final syncService = SyncService(apiClient: apiClient, storageService: FakeStorageService());
      final mediaService = MediaService(apiClient: apiClient);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: MediaDashboardScreen(
            authService: authService,
            syncService: syncService,
            mediaService: mediaService,
            onLogout: () {
              onLogoutCalled = true;
            },
          ),
        ),
      );

      // Allow async data fetching to complete
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // Verify Header & Member Identity
      expect(find.text('Media Team Portal'), findsOneWidget);
      expect(find.text('Arpitha CU'), findsOneWidget);
      expect(find.text('@arpitha.cu'), findsOneWidget);
      expect(find.text('Media'), findsOneWidget);
      expect(find.text('Active Account'), findsOneWidget);

      // Verify Google Drive Card
      expect(find.text('Google Drive Storage'), findsOneWidget);
      expect(find.text('Connect Drive'), findsOneWidget);

      // Verify Event Folder Section & Item
      expect(find.text('Event Media Folders'), findsOneWidget);
      expect(find.text('Create Event Folder'), findsOneWidget);
      expect(find.text('Annual Tech Fest 2026'), findsOneWidget);
      expect(find.text('Main stage and hackathon coverage'), findsOneWidget);

      // Verify Logout Action
      await tester.tap(find.byIcon(Icons.logout));
      await tester.pump();
      expect(onLogoutCalled, isTrue);
    });

    testWidgets('3. Create Event Folder dialog opens with form controls', (tester) async {
      tester.view.physicalSize = const Size(1200, 900);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.resetPhysicalSize());

      final authService = MockMediaAuthService(user: {
        'id': 15,
        'username': 'arpitha.cu',
        'role': 'member',
        'team_id': 3,
        'team_name': 'Media',
        'member_name': 'Arpitha CU',
      });

      final mockClient = MockClient((request) async {
        if (request.url.path.contains('/media/drive/status')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {'is_connected': true, 'email': 'media@deptclub.org'},
            }),
            200,
          );
        }
        if (request.url.path.contains('/media/folders')) {
          return http.Response(
            jsonEncode({'success': true, 'data': []}),
            200,
          );
        }
        return http.Response(jsonEncode({'success': true, 'data': {}}), 200);
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final syncService = SyncService(apiClient: apiClient, storageService: FakeStorageService());
      final mediaService = MediaService(apiClient: apiClient);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: MediaDashboardScreen(
            authService: authService,
            syncService: syncService,
            mediaService: mediaService,
            onLogout: () {},
          ),
        ),
      );

      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // Tap Create Event Folder button
      await tester.tap(find.text('Create Event Folder'));
      await tester.pumpAndSettle();

      // Verify Dialog fields
      expect(find.text('Create Event Folder'), findsWidgets);
      expect(find.text('Event Name *'), findsOneWidget);
      expect(find.text('Description (Optional)'), findsOneWidget);
      expect(find.text('Pick Date'), findsOneWidget);
      expect(find.text('Create in Google Drive'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);

      // Close dialog
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
    });

    testWidgets('4. EventMediaFolderScreen renders category tabs and Drive toolbar', (tester) async {
      tester.view.physicalSize = const Size(1200, 900);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.resetPhysicalSize());

      final folder = MediaEventFolder.fromJson(mockFolderData);

      final authService = MockMediaAuthService(user: {
        'id': 15,
        'username': 'arpitha.cu',
        'role': 'member',
        'team_id': 3,
        'team_name': 'Media',
        'member_name': 'Arpitha CU',
      });

      final mockClient = MockClient((request) async {
        if (request.url.path.contains('/media/folders/101/files')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {
                  'id': 201,
                  'folder_id': 101,
                  'filename': 'opening_ceremony.jpg',
                  'original_filename': 'opening_ceremony.jpg',
                  'category': 'geotagged_photos',
                  'storage_type': 'firebase',
                  'has_gps': true,
                  'gps_latitude': 12.9345,
                  'gps_longitude': 77.6050,
                  'file_size': 2500000,
                  'created_at': '2026-03-25T10:00:00',
                  'uploaded_by_name': 'Arpitha CU',
                }
              ],
            }),
            200,
          );
        }
        if (request.url.path.contains('/media/folders/101')) {
          return http.Response(
            jsonEncode({'success': true, 'data': mockFolderData}),
            200,
          );
        }
        if (request.url.path.contains('/media/drive/status')) {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {'is_connected': false},
            }),
            200,
          );
        }
        return http.Response(jsonEncode({'success': true, 'data': {}}), 200);
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final mediaService = MediaService(apiClient: apiClient);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: EventMediaFolderScreen(
            folder: folder,
            mediaService: mediaService,
            authService: authService,
          ),
        ),
      );

      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // Verify App Bar Title
      expect(find.text('Annual Tech Fest 2026'), findsOneWidget);

      // Verify the 4 Categories Tabs
      expect(find.textContaining('Geotagged Photos'), findsWidgets);
      expect(find.textContaining('Normal Photos'), findsOneWidget);
      expect(find.textContaining('Video Clips'), findsOneWidget);
      expect(find.textContaining('Posters & Designs'), findsOneWidget);

      // Verify Upload action button exists
      expect(find.text('Upload Media'), findsOneWidget);

      // Verify Geotagged file item
      expect(find.text('opening_ceremony.jpg'), findsOneWidget);
      expect(find.textContaining('Geotagged: 12.9345, 77.6050'), findsOneWidget);
      expect(find.text('Open Map'), findsOneWidget);
    });
  });
}
