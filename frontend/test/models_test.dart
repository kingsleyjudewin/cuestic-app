import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/models/assignment.dart';
import 'package:mobile/models/event.dart';
import 'package:mobile/models/member.dart';
import 'package:mobile/models/message_draft.dart';
import 'package:mobile/models/team.dart';


void main() {
  group('Model Serialization Tests', () {
    test('Event fromJson and toSqliteMap', () {
      final json = {
        'id': 1,
        'name': 'MAGNOVITE 2026',
        'description': 'Tech fest',
        'start_at': '2026-10-28T09:00:00Z',
        'end_at': '2026-10-30T18:00:00Z',
        'location': 'Auditorium',
        'status': 'upcoming',
        'created_by': 2,
      };

      final event = Event.fromJson(json);
      expect(event.id, 1);
      expect(event.name, 'MAGNOVITE 2026');
      expect(event.status, 'upcoming');

      final sqliteMap = event.toSqliteMap();
      expect(sqliteMap['name'], 'MAGNOVITE 2026');
      expect(sqliteMap.containsKey('cached_at'), isTrue);

      final fromSqlite = Event.fromSqliteMap(sqliteMap);
      expect(fromSqlite.id, 1);
      expect(fromSqlite.name, 'MAGNOVITE 2026');
    });

    test('Team fromJson and toSqliteMap', () {
      final json = {
        'id': 3,
        'name': 'Documentation',
        'slug': 'documentation',
        'description': 'Maintains records',
        'leader_user_id': 2,
        'leader_username': 'doc_leader',
        'member_count': 5,
        'is_active': true,
        'event_task_assignments_count': 2,
      };

      final team = Team.fromJson(json);
      expect(team.name, 'Documentation');
      expect(team.memberCount, 5);

      final sqliteMap = team.toSqliteMap();
      expect(sqliteMap['is_active'], 1);
      final fromSqlite = Team.fromSqliteMap(sqliteMap);
      expect(fromSqlite.isActive, isTrue);
      expect(fromSqlite.name, 'Documentation');
    });

    test('Member fromJson, classAndSection formatting', () {
      final json = {
        'id': 10,
        'full_name': 'Rohan Verma',
        'registration_number': 'REG-002',
        'class_name': '3rd Year CSE',
        'section': 'B',
        'phone_number': '+919876500002',
        'country_code': '+91',
        'team_id': 1,
        'team_name': 'Volunteering',
        'whatsapp_opt_in': true,
        'is_active': true,
        'has_history': false,
      };

      final member = Member.fromJson(json);
      expect(member.fullName, 'Rohan Verma');
      expect(member.classAndSection, '3rd Year CSE - Sec B');

      final sqliteMap = member.toSqliteMap();
      expect(sqliteMap['registration_number'], 'REG-002');
      final fromSqlite = Member.fromSqliteMap(sqliteMap);
      expect(fromSqlite.fullName, 'Rohan Verma');
    });

    test('Task and TaskAssignment state transitions', () {
      final assignment = TaskAssignment(
        id: 1,
        taskId: 101,
        memberId: 5,
        assignedBy: 1,
        status: 'awaiting_confirmation',
      );

      // Allowed transitions from awaiting_confirmation: accepted, declined, in_progress, cancelled
      expect(assignment.canTransitionTo('accepted'), isTrue);
      expect(assignment.canTransitionTo('in_progress'), isTrue);
      expect(assignment.canTransitionTo('declined'), isTrue);
      expect(assignment.canTransitionTo('completed'), isFalse); // Cannot jump directly to completed

      final inProgressAssignment = TaskAssignment(
        id: 2,
        taskId: 101,
        memberId: 5,
        assignedBy: 1,
        status: 'in_progress',
      );

      expect(inProgressAssignment.canTransitionTo('submitted'), isTrue);
      expect(inProgressAssignment.canTransitionTo('blocked'), isTrue);
      expect(inProgressAssignment.canTransitionTo('awaiting_confirmation'), isFalse);
    });

    test('MessageDraft fromJson', () {
      final json = {
        'assignment_id': 42,
        'message_log_id': 7,
        'whatsapp_url': 'https://wa.me/919876500001?text=Hello',
        'phone_number': '+919876500001',
        'wa_phone': '919876500001',
        'message_text': 'Hello! You have a new task.',
        'disclaimer': 'Official club notification',
      };

      final draft = MessageDraft.fromJson(json, memberName: 'Ananya Sharma', taskTitle: 'Poster Design');
      expect(draft.assignmentId, 42);
      expect(draft.whatsappUrl, contains('https://wa.me/'));
      expect(draft.memberName, 'Ananya Sharma');
      expect(draft.isSent, isFalse);
    });
  });
}
