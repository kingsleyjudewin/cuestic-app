import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:mobile/models/event.dart';
import 'package:mobile/services/api_client.dart';
import 'package:mobile/services/auth_service.dart';
import 'package:mobile/services/storage_service.dart';
import 'package:mobile/services/sync_service.dart';

void main() {
  setUpAll(() {
    TestWidgetsFlutterBinding.ensureInitialized();
    FlutterSecureStorage.setMockInitialValues({});
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  });

  group('SyncService Offline Caching & Fallback Tests', () {
    late Database inMemoryDb;
    late StorageService storageService;
    late AuthService authService;

    setUp(() async {
      inMemoryDb = await databaseFactoryFfi.openDatabase(inMemoryDatabasePath);
      await inMemoryDb.execute('''
        CREATE TABLE events (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          description TEXT,
          start_at TEXT NOT NULL,
          end_at TEXT,
          location TEXT,
          status TEXT NOT NULL,
          created_by INTEGER,
          cached_at TEXT NOT NULL
        )
      ''');
      await inMemoryDb.execute('''
        CREATE TABLE sync_meta (
          key TEXT PRIMARY KEY,
          last_synced_at TEXT NOT NULL,
          metadata TEXT
        )
      ''');

      storageService = StorageService();
      storageService.setDatabase(inMemoryDb);
      authService = AuthService();
    });

    tearDown(() async {
      await inMemoryDb.close();
    });

    test('Online fetch updates SQLite cache and keeps isOffline false', () async {
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
              }
            ]
          }),
          200,
        );
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      final events = await syncService.fetchEvents();
      expect(events.length, 1);
      expect(events.first.name, 'MAGNOVITE 2026');
      expect(syncService.isOffline, isFalse);

      final cached = await storageService.getCachedEvents();
      expect(cached.length, 1);
      expect(cached.first.name, 'MAGNOVITE 2026');
    });

    test('Network failure falls back to cached SQLite data and flags isOffline true', () async {
      // Pre-seed local cache
      await storageService.cacheEvents([
        Event(
          id: 1,
          name: 'Cached Symposium Event',
          startAt: DateTime.parse('2026-10-28T09:00:00Z'),
          status: 'upcoming',
        )
      ]);

      // Mock network failure without const
      final mockClient = MockClient((request) async {
        throw http.ClientException('Network unreachable');
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      final events = await syncService.fetchEvents();
      expect(events.length, 1);
      expect(events.first.name, 'Cached Symposium Event');
      expect(syncService.isOffline, isTrue);
    });

    test('Attempting to create task while offline throws informative OFFLINE exception', () async {
      final mockClient = MockClient((request) async => http.Response('', 500));
      final apiClient = ApiClient(client: mockClient, authService: authService);
      final syncService = SyncService(apiClient: apiClient, storageService: storageService);

      syncService.setOffline(true);

      try {
        await syncService.createTask(
          eventId: 1,
          title: 'New Offline Task',
          priority: 'high',
          deadline: DateTime.now().add(const Duration(days: 2)),
          memberIds: [1, 2],
        );
        fail('Should throw OFFLINE exception');
      } on ApiException catch (e) {
        expect(e.code, 'OFFLINE');
        expect(e.message, contains('Network connection required'));
      }
    });
  });
}
