import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:mobile/models/assignment.dart';
import 'package:mobile/models/event.dart';
import 'package:mobile/models/member.dart';
import 'package:mobile/services/storage_service.dart';


void main() {
  setUpAll(() {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  });

  group('StorageService SQLite Cache Tests', () {
    late Database inMemoryDb;
    late StorageService storageService;

    setUp(() async {
      inMemoryDb = await databaseFactoryFfi.openDatabase(inMemoryDatabasePath);
      // Run table creations
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
        CREATE TABLE teams (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          slug TEXT NOT NULL,
          description TEXT,
          leader_user_id INTEGER,
          leader_username TEXT,
          member_count INTEGER NOT NULL DEFAULT 0,
          is_active INTEGER NOT NULL DEFAULT 1,
          event_task_assignments_count INTEGER NOT NULL DEFAULT 0,
          cached_at TEXT NOT NULL
        )
      ''');

      await inMemoryDb.execute('''
        CREATE TABLE members (
          id INTEGER PRIMARY KEY,
          full_name TEXT NOT NULL,
          email TEXT,
          registration_number TEXT,
          class_name TEXT NOT NULL,
          section TEXT,
          phone_number TEXT NOT NULL,
          country_code TEXT NOT NULL DEFAULT '+91',
          team_id INTEGER NOT NULL,
          team_name TEXT,
          linked_user_id INTEGER,
          linked_username TEXT,
          linked_email TEXT,
          linked_role TEXT,
          linked_user_is_active INTEGER,
          whatsapp_opt_in INTEGER NOT NULL DEFAULT 1,
          is_active INTEGER NOT NULL DEFAULT 1,
          has_history INTEGER NOT NULL DEFAULT 0,
          cached_at TEXT NOT NULL
        )
      ''');

      await inMemoryDb.execute('''
        CREATE TABLE assignments (
          id INTEGER PRIMARY KEY,
          task_id INTEGER NOT NULL,
          task_title TEXT,
          task_description TEXT,
          task_priority TEXT,
          deadline TEXT,
          deadline_formatted TEXT,
          event_id INTEGER,
          event_name TEXT,
          member_id INTEGER NOT NULL,
          member_name TEXT,
          member_phone TEXT,
          member_reg_no TEXT,
          team_id INTEGER,
          team_name TEXT,
          assigned_by INTEGER NOT NULL,
          assigner_name TEXT,
          status TEXT NOT NULL,
          is_overdue INTEGER NOT NULL DEFAULT 0,
          assigned_at TEXT,
          confirmed_at TEXT,
          started_at TEXT,
          submitted_at TEXT,
          completed_at TEXT,
          completion_note TEXT,
          updated_at TEXT,
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
    });

    tearDown(() async {
      await inMemoryDb.close();
    });

    test('Cache and retrieve events', () async {
      final events = [
        Event(
          id: 1,
          name: 'MAGNOVITE 2026',
          startAt: DateTime.parse('2026-10-28T09:00:00Z'),
          status: 'upcoming',
        ),
        Event(
          id: 2,
          name: 'Department Coding Sprint',
          startAt: DateTime.parse('2026-11-05T10:00:00Z'),
          status: 'upcoming',
        ),
      ];

      await storageService.cacheEvents(events);
      final cached = await storageService.getCachedEvents();

      expect(cached.length, 2);
      expect(cached.first.name, 'MAGNOVITE 2026');
      expect(cached.last.name, 'Department Coding Sprint');

      final lastSync = await storageService.getLastSyncTimestamp('events');
      expect(lastSync, isNotNull);
    });

    test('Cache and search members by name and registration number', () async {
      final members = [
        Member(
          id: 1,
          fullName: 'Ananya Sharma',
          registrationNumber: 'TEST-REG-001',
          className: '3rd Year CSE',
          phoneNumber: '+919876500001',
          teamId: 1,
        ),
        Member(
          id: 2,
          fullName: 'Rohan Verma',
          registrationNumber: 'TEST-REG-002',
          className: '3rd Year CSE',
          phoneNumber: '+919876500002',
          teamId: 1,
        ),
        Member(
          id: 3,
          fullName: 'Priya Patel',
          registrationNumber: 'TEST-REG-003',
          className: '2nd Year ECE',
          phoneNumber: '+919876500003',
          teamId: 2,
        ),
      ];

      await storageService.cacheMembers(1, members.where((m) => m.teamId == 1).toList());

      // Query all in team 1
      final team1Members = await storageService.getCachedMembers(1);
      expect(team1Members.length, 2);

      // Search by name
      final searchByName = await storageService.getCachedMembers(1, query: 'Ananya');
      expect(searchByName.length, 1);
      expect(searchByName.first.fullName, 'Ananya Sharma');

      // Search by reg number
      final searchByReg = await storageService.getCachedMembers(1, query: 'REG-002');
      expect(searchByReg.length, 1);
      expect(searchByReg.first.fullName, 'Rohan Verma');
    });

    test('Cache and update task assignments with status filters', () async {
      final assignments = [
        TaskAssignment(
          id: 1,
          taskId: 10,
          taskTitle: 'Design poster',
          memberId: 1,
          assignedBy: 1,
          status: 'awaiting_confirmation',
          isOverdue: false,
        ),
        TaskAssignment(
          id: 2,
          taskId: 11,
          taskTitle: 'Stage setup',
          memberId: 2,
          assignedBy: 1,
          status: 'in_progress',
          isOverdue: true,
        ),
        TaskAssignment(
          id: 3,
          taskId: 12,
          taskTitle: 'Write minutes',
          memberId: 3,
          assignedBy: 1,
          status: 'completed',
          isOverdue: false,
        ),
      ];

      await storageService.cacheAssignments(assignments);

      final pending = await storageService.getCachedAssignments(status: 'awaiting_confirmation');
      expect(pending.length, 1);
      expect(pending.first.taskTitle, 'Design poster');

      final overdueOnly = await storageService.getCachedAssignments(overdue: true);
      expect(overdueOnly.length, 1);
      expect(overdueOnly.first.taskTitle, 'Stage setup');

      // Update single assignment status
      final updatedAssignment = TaskAssignment(
        id: 1,
        taskId: 10,
        taskTitle: 'Design poster',
        memberId: 1,
        assignedBy: 1,
        status: 'in_progress',
        isOverdue: false,
      );
      await storageService.updateSingleCachedAssignment(updatedAssignment);

      final inProgressList = await storageService.getCachedAssignments(status: 'in_progress');
      expect(inProgressList.length, 2);
    });
  });
}
