class Event {
  final int id;
  final String name;
  final String? description;
  final DateTime startAt;
  final DateTime? endAt;
  final String? location;
  final String status;
  final int? createdBy;

  Event({
    required this.id,
    required this.name,
    this.description,
    required this.startAt,
    this.endAt,
    this.location,
    required this.status,
    this.createdBy,
  });

  factory Event.fromJson(Map<String, dynamic> json) {
    return Event(
      id: json['id'] as int,
      name: json['name'] as String? ?? 'Unnamed Event',
      description: json['description'] as String?,
      startAt: DateTime.tryParse(json['start_at']?.toString() ?? '') ?? DateTime.now(),
      endAt: json['end_at'] != null ? DateTime.tryParse(json['end_at'].toString()) : null,
      location: json['location'] as String?,
      status: json['status'] as String? ?? 'upcoming',
      createdBy: json['created_by'] as int?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'description': description,
      'start_at': startAt.toUtc().toIso8601String(),
      'end_at': endAt?.toUtc().toIso8601String(),
      'location': location,
      'status': status,
      'created_by': createdBy,
    };
  }

  factory Event.fromSqliteMap(Map<String, dynamic> map) {
    return Event(
      id: map['id'] as int,
      name: map['name'] as String,
      description: map['description'] as String?,
      startAt: DateTime.tryParse(map['start_at'] as String? ?? '') ?? DateTime.now(),
      endAt: map['end_at'] != null ? DateTime.tryParse(map['end_at'] as String) : null,
      location: map['location'] as String?,
      status: map['status'] as String? ?? 'upcoming',
      createdBy: map['created_by'] as int?,
    );
  }

  Map<String, dynamic> toSqliteMap() {
    return {
      'id': id,
      'name': name,
      'description': description,
      'start_at': startAt.toUtc().toIso8601String(),
      'end_at': endAt?.toUtc().toIso8601String(),
      'location': location,
      'status': status,
      'created_by': createdBy,
      'cached_at': DateTime.now().toUtc().toIso8601String(),
    };
  }
}
