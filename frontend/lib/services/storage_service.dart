import 'package:flutter/foundation.dart';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart' as p;
import '../models/event.dart';
import '../models/team.dart';
import '../models/member.dart';
import '../models/assignment.dart';

class StorageService {
  static const String dbName = 'department_club_cache.db';
  static const int dbVersion = 5;

  Database? _db;

  // Web in-memory fallback cache
  final List<Event> _webEvents = [];
  final List<Team> _webTeams = [];
  final Map<int, List<Member>> _webMembersByTeam = {};
  final List<TaskAssignment> _webAssignments = [];
  final Map<String, DateTime> _webSyncMeta = {};

  Future<Database> get database async {
    if (kIsWeb) {
      throw UnsupportedError('Direct SQLite database access is not supported on web.');
    }
    if (_db != null && _db!.isOpen) return _db!;
    _db = await _initDatabase();
    return _db!;
  }

  // Allow injecting custom Database (e.g. sqflite_common_ffi or in-memory in tests)
  void setDatabase(Database db) {
    _db = db;
  }

  Future<Database> _initDatabase() async {
    final databasesPath = await getDatabasesPath();
    final path = p.join(databasesPath, dbName);

    return await openDatabase(
      path,
      version: dbVersion,
      onCreate: (db, version) async {
        await _createTables(db);
      },
      onUpgrade: (db, oldVersion, newVersion) async {
        if (oldVersion < 2) {
          // Migration from version 1 to 2 if needed
          await db.execute('ALTER TABLE assignments ADD COLUMN task_priority TEXT');
        }
        if (oldVersion < 3) {
          await db.execute('ALTER TABLE members ADD COLUMN linked_user_id INTEGER');
          await db.execute('ALTER TABLE members ADD COLUMN linked_username TEXT');
          await db.execute('ALTER TABLE members ADD COLUMN linked_email TEXT');
          await db.execute('ALTER TABLE members ADD COLUMN linked_role TEXT');
          await db.execute('ALTER TABLE members ADD COLUMN linked_user_is_active INTEGER');
        }
        if (oldVersion < 4) {
          await db.execute('ALTER TABLE assignments ADD COLUMN task_description TEXT');
        }
        if (oldVersion < 5) {
          try {
            await db.execute('ALTER TABLE members ADD COLUMN email TEXT');
          } catch (_) {}
        }
      },
    );
  }

  static Future<void> _createTables(Database db) async {
    await db.execute('''
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

    await db.execute('''
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

    await db.execute('''
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

    await db.execute('''
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

    await db.execute('''
      CREATE TABLE sync_meta (
        key TEXT PRIMARY KEY,
        last_synced_at TEXT NOT NULL,
        metadata TEXT
      )
    ''');
  }

  // --- Events Cache ---
  Future<void> cacheEvents(List<Event> events) async {
    if (kIsWeb) {
      _webEvents.clear();
      _webEvents.addAll(events);
      await updateSyncTimestamp('events');
      return;
    }
    final db = await database;
    final batch = db.batch();
    batch.delete('events');
    for (final event in events) {
      batch.insert('events', event.toSqliteMap(), conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
    await updateSyncTimestamp('events');
  }

  Future<void> saveEvent(Event event) async {
    if (kIsWeb) {
      _webEvents.removeWhere((e) => e.id == event.id);
      _webEvents.add(event);
      _webEvents.sort((a, b) => a.startAt.compareTo(b.startAt));
      await updateSyncTimestamp('events');
      return;
    }
    final db = await database;
    await db.insert('events', event.toSqliteMap(), conflictAlgorithm: ConflictAlgorithm.replace);
    await updateSyncTimestamp('events');
  }

  Future<List<Event>> getCachedEvents() async {
    if (kIsWeb) {
      return List<Event>.from(_webEvents);
    }
    final db = await database;
    final rows = await db.query('events', orderBy: 'start_at ASC');
    return rows.map((r) => Event.fromSqliteMap(r)).toList();
  }

  // --- Teams Cache ---
  Future<void> cacheTeams(List<Team> teams) async {
    if (kIsWeb) {
      _webTeams.clear();
      _webTeams.addAll(teams);
      await updateSyncTimestamp('teams');
      return;
    }
    final db = await database;
    final batch = db.batch();
    batch.delete('teams');
    for (final team in teams) {
      batch.insert('teams', team.toSqliteMap(), conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
    await updateSyncTimestamp('teams');
  }

  Future<List<Team>> getCachedTeams() async {
    if (kIsWeb) {
      return List<Team>.from(_webTeams);
    }
    final db = await database;
    final rows = await db.query('teams', orderBy: 'name ASC');
    return rows.map((r) => Team.fromSqliteMap(r)).toList();
  }

  // --- Members Cache ---
  Future<void> cacheMembers(int teamId, List<Member> members) async {
    if (kIsWeb) {
      _webMembersByTeam[teamId] = List<Member>.from(members);
      await updateSyncTimestamp('members_team_$teamId');
      return;
    }
    final db = await database;
    final batch = db.batch();
    batch.delete('members', where: 'team_id = ?', whereArgs: [teamId]);
    for (final member in members) {
      batch.insert('members', member.toSqliteMap(), conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
    await updateSyncTimestamp('members_team_$teamId');
  }

  Future<List<Member>> getCachedMembers(int teamId, {String? query}) async {
    if (kIsWeb) {
      final list = _webMembersByTeam[teamId] ?? [];
      if (query != null && query.trim().isNotEmpty) {
        final q = query.trim().toLowerCase();
        return list.where((m) =>
          m.fullName.toLowerCase().contains(q) ||
          (m.registrationNumber?.toLowerCase().contains(q) ?? false)
        ).toList();
      }
      return List<Member>.from(list);
    }
    final db = await database;
    List<Map<String, dynamic>> rows;
    if (query != null && query.trim().isNotEmpty) {
      final q = '%${query.trim()}%';
      rows = await db.query(
        'members',
        where: 'team_id = ? AND (full_name LIKE ? OR registration_number LIKE ?)',
        whereArgs: [teamId, q, q],
        orderBy: 'full_name ASC',
      );
    } else {
      rows = await db.query(
        'members',
        where: 'team_id = ?',
        whereArgs: [teamId],
        orderBy: 'full_name ASC',
      );
    }
    return rows.map((r) => Member.fromSqliteMap(r)).toList();
  }

  // --- Assignments Cache ---
  Future<void> cacheAssignments(List<TaskAssignment> assignments) async {
    if (kIsWeb) {
      _webAssignments.clear();
      _webAssignments.addAll(assignments);
      await updateSyncTimestamp('assignments');
      return;
    }
    final db = await database;
    final batch = db.batch();
    batch.delete('assignments');
    for (final assignment in assignments) {
      batch.insert('assignments', assignment.toSqliteMap(), conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
    await updateSyncTimestamp('assignments');
  }

  Future<void> updateSingleCachedAssignment(TaskAssignment assignment) async {
    if (kIsWeb) {
      final idx = _webAssignments.indexWhere((a) => a.id == assignment.id);
      if (idx >= 0) {
        _webAssignments[idx] = assignment;
      } else {
        _webAssignments.add(assignment);
      }
      return;
    }
    final db = await database;
    await db.insert('assignments', assignment.toSqliteMap(), conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<List<TaskAssignment>> getCachedAssignments({String? status, bool? overdue}) async {
    if (kIsWeb) {
      return _webAssignments.where((a) {
        if (status != null && status.isNotEmpty && a.status != status) return false;
        if (overdue != null && a.isOverdue != overdue) return false;
        return true;
      }).toList();
    }
    final db = await database;
    String? whereClause;
    List<dynamic> whereArgs = [];

    if (status != null && status.isNotEmpty) {
      whereClause = 'status = ?';
      whereArgs.add(status);
    }
    if (overdue != null) {
      final overdueStr = overdue ? 'is_overdue = 1' : 'is_overdue = 0';
      whereClause = whereClause == null ? overdueStr : '$whereClause AND $overdueStr';
    }

    final rows = await db.query(
      'assignments',
      where: whereClause,
      whereArgs: whereArgs.isNotEmpty ? whereArgs : null,
      orderBy: 'deadline ASC',
    );
    return rows.map((r) => TaskAssignment.fromSqliteMap(r)).toList();
  }

  // --- Sync Metadata ---
  Future<void> updateSyncTimestamp(String key) async {
    if (kIsWeb) {
      _webSyncMeta[key] = DateTime.now().toUtc();
      return;
    }
    try {
      final db = await database;
      await db.insert(
        'sync_meta',
        {
          'key': key,
          'last_synced_at': DateTime.now().toUtc().toIso8601String(),
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    } catch (e) {
      debugPrint('Sync timestamp update error: $e');
    }
  }

  Future<DateTime?> getLastSyncTimestamp(String key) async {
    if (kIsWeb) {
      return _webSyncMeta[key];
    }
    try {
      final db = await database;
      final rows = await db.query('sync_meta', where: 'key = ?', whereArgs: [key], limit: 1);
      if (rows.isNotEmpty) {
        return DateTime.tryParse(rows.first['last_synced_at'] as String);
      }
    } catch (_) {}
    return null;
  }

  Future<void> clearAllCache() async {
    if (kIsWeb) {
      _webEvents.clear();
      _webTeams.clear();
      _webMembersByTeam.clear();
      _webAssignments.clear();
      _webSyncMeta.clear();
      return;
    }
    final db = await database;
    await db.delete('events');
    await db.delete('teams');
    await db.delete('members');
    await db.delete('assignments');
    await db.delete('sync_meta');
  }
}
