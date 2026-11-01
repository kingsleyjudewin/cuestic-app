class TaskAssignment {
  final int id;
  final int taskId;
  final String? taskTitle;
  final String? taskDescription;
  final String? taskPriority;
  final DateTime? deadline;
  final String? deadlineFormatted;
  final int? eventId;
  final String? eventName;
  final int memberId;
  final String? memberName;
  final String? memberPhone;
  final String? memberRegNo;
  final int? teamId;
  final String? teamName;
  final int assignedBy;
  final String? assignerName;
  final String status;
  final bool isOverdue;
  final DateTime? assignedAt;
  final DateTime? confirmedAt;
  final DateTime? startedAt;
  final DateTime? submittedAt;
  final DateTime? completedAt;
  final String? completionNote;
  final DateTime? updatedAt;

  TaskAssignment({
    required this.id,
    required this.taskId,
    this.taskTitle,
    this.taskDescription,
    this.taskPriority,
    this.deadline,
    this.deadlineFormatted,
    this.eventId,
    this.eventName,
    required this.memberId,
    this.memberName,
    this.memberPhone,
    this.memberRegNo,
    this.teamId,
    this.teamName,
    required this.assignedBy,
    this.assignerName,
    required this.status,
    this.isOverdue = false,
    this.assignedAt,
    this.confirmedAt,
    this.startedAt,
    this.submittedAt,
    this.completedAt,
    this.completionNote,
    this.updatedAt,
  });

  static const Map<String, List<String>> allowedTransitions = {
    'awaiting_confirmation': ['accepted', 'declined', 'in_progress', 'cancelled'],
    'accepted': ['in_progress', 'declined', 'blocked', 'cancelled'],
    'declined': ['awaiting_confirmation', 'cancelled'],
    'in_progress': ['submitted', 'blocked', 'cancelled'],
    'submitted': ['completed', 'in_progress', 'cancelled'],
    'blocked': ['in_progress', 'cancelled'],
    'completed': ['in_progress'],
    'cancelled': [],
  };

  bool canTransitionTo(String targetStatus) {
    if (targetStatus == status) return true;
    final allowed = allowedTransitions[status] ?? [];
    return allowed.contains(targetStatus);
  }

  factory TaskAssignment.fromJson(Map<String, dynamic> json) {
    return TaskAssignment(
      id: json['id'] as int,
      taskId: json['task_id'] as int,
      taskTitle: json['task_title'] as String?,
      taskDescription: json['task_description'] as String?,
      taskPriority: json['task_priority'] as String?,
      deadline: json['deadline'] != null ? DateTime.tryParse(json['deadline'].toString()) : null,
      deadlineFormatted: json['deadline_formatted'] as String?,
      eventId: json['event_id'] as int?,
      eventName: json['event_name'] as String?,
      memberId: json['member_id'] as int,
      memberName: json['member_name'] as String?,
      memberPhone: json['member_phone'] as String?,
      memberRegNo: json['member_reg_no'] as String?,
      teamId: json['team_id'] as int?,
      teamName: json['team_name'] as String?,
      assignedBy: json['assigned_by'] as int? ?? 0,
      assignerName: json['assigner_name'] as String?,
      status: json['status'] as String? ?? 'awaiting_confirmation',
      isOverdue: json['is_overdue'] as bool? ?? false,
      assignedAt: json['assigned_at'] != null ? DateTime.tryParse(json['assigned_at'].toString()) : null,
      confirmedAt: json['confirmed_at'] != null ? DateTime.tryParse(json['confirmed_at'].toString()) : null,
      startedAt: json['started_at'] != null ? DateTime.tryParse(json['started_at'].toString()) : null,
      submittedAt: json['submitted_at'] != null ? DateTime.tryParse(json['submitted_at'].toString()) : null,
      completedAt: json['completed_at'] != null ? DateTime.tryParse(json['completed_at'].toString()) : null,
      completionNote: json['completion_note'] as String?,
      updatedAt: json['updated_at'] != null ? DateTime.tryParse(json['updated_at'].toString()) : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'task_id': taskId,
      'task_title': taskTitle,
      'task_description': taskDescription,
      'task_priority': taskPriority,
      'deadline': deadline?.toUtc().toIso8601String(),
      'deadline_formatted': deadlineFormatted,
      'event_id': eventId,
      'event_name': eventName,
      'member_id': memberId,
      'member_name': memberName,
      'member_phone': memberPhone,
      'member_reg_no': memberRegNo,
      'team_id': teamId,
      'team_name': teamName,
      'assigned_by': assignedBy,
      'assigner_name': assignerName,
      'status': status,
      'is_overdue': isOverdue,
      'assigned_at': assignedAt?.toUtc().toIso8601String(),
      'confirmed_at': confirmedAt?.toUtc().toIso8601String(),
      'started_at': startedAt?.toUtc().toIso8601String(),
      'submitted_at': submittedAt?.toUtc().toIso8601String(),
      'completed_at': completedAt?.toUtc().toIso8601String(),
      'completion_note': completionNote,
      'updated_at': updatedAt?.toUtc().toIso8601String(),
    };
  }

  factory TaskAssignment.fromSqliteMap(Map<String, dynamic> map) {
    return TaskAssignment(
      id: map['id'] as int,
      taskId: map['task_id'] as int,
      taskTitle: map['task_title'] as String?,
      taskPriority: map['task_priority'] as String?,
      deadline: map['deadline'] != null ? DateTime.tryParse(map['deadline'] as String) : null,
      deadlineFormatted: map['deadline_formatted'] as String?,
      eventId: map['event_id'] as int?,
      eventName: map['event_name'] as String?,
      memberId: map['member_id'] as int,
      memberName: map['member_name'] as String?,
      memberPhone: map['member_phone'] as String?,
      memberRegNo: map['member_reg_no'] as String?,
      teamId: map['team_id'] as int?,
      teamName: map['team_name'] as String?,
      assignedBy: map['assigned_by'] as int? ?? 0,
      assignerName: map['assigner_name'] as String?,
      status: map['status'] as String? ?? 'awaiting_confirmation',
      isOverdue: (map['is_overdue'] as int? ?? 0) == 1,
      assignedAt: map['assigned_at'] != null ? DateTime.tryParse(map['assigned_at'] as String) : null,
      confirmedAt: map['confirmed_at'] != null ? DateTime.tryParse(map['confirmed_at'] as String) : null,
      startedAt: map['started_at'] != null ? DateTime.tryParse(map['started_at'] as String) : null,
      submittedAt: map['submitted_at'] != null ? DateTime.tryParse(map['submitted_at'] as String) : null,
      completedAt: map['completed_at'] != null ? DateTime.tryParse(map['completed_at'] as String) : null,
      completionNote: map['completion_note'] as String?,
      updatedAt: map['updated_at'] != null ? DateTime.tryParse(map['updated_at'] as String) : null,
    );
  }

  Map<String, dynamic> toSqliteMap() {
    return {
      'id': id,
      'task_id': taskId,
      'task_title': taskTitle,
      'task_description': taskDescription,
      'task_priority': taskPriority,
      'deadline': deadline?.toUtc().toIso8601String(),
      'deadline_formatted': deadlineFormatted,
      'event_id': eventId,
      'event_name': eventName,
      'member_id': memberId,
      'member_name': memberName,
      'member_phone': memberPhone,
      'member_reg_no': memberRegNo,
      'team_id': teamId,
      'team_name': teamName,
      'assigned_by': assignedBy,
      'assigner_name': assignerName,
      'status': status,
      'is_overdue': isOverdue ? 1 : 0,
      'assigned_at': assignedAt?.toUtc().toIso8601String(),
      'confirmed_at': confirmedAt?.toUtc().toIso8601String(),
      'started_at': startedAt?.toUtc().toIso8601String(),
      'submitted_at': submittedAt?.toUtc().toIso8601String(),
      'completed_at': completedAt?.toUtc().toIso8601String(),
      'completion_note': completionNote,
      'updated_at': updatedAt?.toUtc().toIso8601String(),
      'cached_at': DateTime.now().toUtc().toIso8601String(),
    };
  }
}
