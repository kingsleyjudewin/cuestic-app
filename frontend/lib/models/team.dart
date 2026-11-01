class Team {
  final int id;
  final String name;
  final String slug;
  final String? description;
  final int? leaderUserId;
  final String? leaderUsername;
  final int memberCount;
  final bool isActive;
  final int eventTaskAssignmentsCount;

  Team({
    required this.id,
    required this.name,
    required this.slug,
    this.description,
    this.leaderUserId,
    this.leaderUsername,
    this.memberCount = 0,
    this.isActive = true,
    this.eventTaskAssignmentsCount = 0,
  });

  factory Team.fromJson(Map<String, dynamic> json) {
    return Team(
      id: json['id'] as int,
      name: json['name'] as String? ?? 'Team',
      slug: json['slug'] as String? ?? '',
      description: json['description'] as String?,
      leaderUserId: json['leader_user_id'] as int?,
      leaderUsername: json['leader_username'] as String?,
      memberCount: (json['member_count'] as num?)?.toInt() ?? 0,
      isActive: json['is_active'] as bool? ?? true,
      eventTaskAssignmentsCount: (json['event_task_assignments_count'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'slug': slug,
      'description': description,
      'leader_user_id': leaderUserId,
      'leader_username': leaderUsername,
      'member_count': memberCount,
      'is_active': isActive,
      'event_task_assignments_count': eventTaskAssignmentsCount,
    };
  }

  factory Team.fromSqliteMap(Map<String, dynamic> map) {
    return Team(
      id: map['id'] as int,
      name: map['name'] as String,
      slug: map['slug'] as String? ?? '',
      description: map['description'] as String?,
      leaderUserId: map['leader_user_id'] as int?,
      leaderUsername: map['leader_username'] as String?,
      memberCount: (map['member_count'] as num?)?.toInt() ?? 0,
      isActive: (map['is_active'] as int? ?? 1) == 1,
      eventTaskAssignmentsCount: (map['event_task_assignments_count'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toSqliteMap() {
    return {
      'id': id,
      'name': name,
      'slug': slug,
      'description': description,
      'leader_user_id': leaderUserId,
      'leader_username': leaderUsername,
      'member_count': memberCount,
      'is_active': isActive ? 1 : 0,
      'event_task_assignments_count': eventTaskAssignmentsCount,
      'cached_at': DateTime.now().toUtc().toIso8601String(),
    };
  }
}
