import 'assignment.dart';

class Task {
  final int id;
  final int eventId;
  final String? eventName;
  final String title;
  final String? description;
  final String priority;
  final DateTime deadline;
  final String? deadlineFormatted;
  final bool isCancelled;
  final int assigneeCount;
  final List<TaskAssignment> assignments;

  Task({
    required this.id,
    required this.eventId,
    this.eventName,
    required this.title,
    this.description,
    this.priority = 'medium',
    required this.deadline,
    this.deadlineFormatted,
    this.isCancelled = false,
    this.assigneeCount = 0,
    this.assignments = const [],
  });

  factory Task.fromJson(Map<String, dynamic> json) {
    List<TaskAssignment> assignmentsList = [];
    if (json['assignments'] != null && json['assignments'] is List) {
      assignmentsList = (json['assignments'] as List)
          .map((a) => TaskAssignment.fromJson(a as Map<String, dynamic>))
          .toList();
    }

    return Task(
      id: json['id'] as int,
      eventId: (json['event_id'] as num?)?.toInt() ?? 0,
      eventName: json['event_name'] as String?,
      title: json['title'] as String? ?? 'Task',
      description: json['description'] as String?,
      priority: json['priority'] as String? ?? 'medium',
      deadline: DateTime.tryParse(json['deadline']?.toString() ?? '') ?? DateTime.now(),
      deadlineFormatted: json['deadline_formatted'] as String?,
      isCancelled: json['is_cancelled'] as bool? ?? false,
      assigneeCount: (json['assignee_count'] as num?)?.toInt() ?? assignmentsList.length,
      assignments: assignmentsList,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'event_id': eventId,
      'event_name': eventName,
      'title': title,
      'description': description,
      'priority': priority,
      'deadline': deadline.toUtc().toIso8601String(),
      'deadline_formatted': deadlineFormatted,
      'is_cancelled': isCancelled,
      'assignee_count': assigneeCount,
      'assignments': assignments.map((a) => a.toJson()).toList(),
    };
  }
}
