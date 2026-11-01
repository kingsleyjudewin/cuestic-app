class Member {
  final int id;
  final String fullName;
  final String? email;
  final String? registrationNumber;
  final String className;
  final String? section;
  final String phoneNumber;
  final String countryCode;
  final int teamId;
  final String? teamName;
  final int? linkedUserId;
  final String? linkedUsername;
  final String? linkedEmail;
  final String? linkedRole;
  final bool? linkedUserIsActive;
  final bool whatsappOptIn;
  final bool isActive;
  final bool hasHistory;

  Member({
    required this.id,
    required this.fullName,
    this.email,
    this.registrationNumber,
    required this.className,
    this.section,
    required this.phoneNumber,
    this.countryCode = '+91',
    required this.teamId,
    this.teamName,
    this.linkedUserId,
    this.linkedUsername,
    this.linkedEmail,
    this.linkedRole,
    this.linkedUserIsActive,
    this.whatsappOptIn = true,
    this.isActive = true,
    this.hasHistory = false,
  });

  bool get hasAccount => linkedUserId != null;

  String? get effectiveEmail {
    if (email != null && email!.trim().isNotEmpty) {
      return email!.trim();
    }
    if (linkedEmail != null && linkedEmail!.trim().isNotEmpty) {
      return linkedEmail!.trim();
    }
    return null;
  }

  String get displayRole {
    if (linkedRole != null && linkedRole!.isNotEmpty) {
      if (linkedRole == 'team_leader') return 'Team Leader';
      if (linkedRole == 'president') return 'President';
      if (linkedRole == 'admin') return 'Admin';
      return 'Member';
    }
    return 'Member';
  }

  String get classAndSection {
    if (section != null && section!.trim().isNotEmpty) {
      return '$className - Sec $section';
    }
    return className;
  }

  factory Member.fromJson(Map<String, dynamic> json) {
    final linkedUser = json['linked_user'] as Map<String, dynamic>?;
    final linkedUserId = (json['linked_user_id'] as num?)?.toInt() ?? (linkedUser?['id'] as num?)?.toInt();
    final linkedUsername = linkedUser?['username'] as String? ?? json['linked_username'] as String?;
    final linkedEmail = linkedUser?['email'] as String? ?? json['linked_email'] as String?;
    final memberEmail = json['email'] as String? ?? linkedEmail;
    final linkedRole = linkedUser?['role'] as String? ?? json['linked_role'] as String?;
    final linkedUserIsActive = linkedUser?['is_active'] as bool? ?? json['linked_user_is_active'] as bool?;

    return Member(
      id: json['id'] as int,
      fullName: json['full_name'] as String? ?? 'Member',
      email: memberEmail,
      registrationNumber: json['registration_number'] as String?,
      className: json['class_name'] as String? ?? '',
      section: json['section'] as String?,
      phoneNumber: json['phone_number'] as String? ?? '',
      countryCode: json['country_code'] as String? ?? '+91',
      teamId: (json['team_id'] as num?)?.toInt() ?? 0,
      teamName: json['team_name'] as String?,
      linkedUserId: linkedUserId,
      linkedUsername: linkedUsername,
      linkedEmail: linkedEmail,
      linkedRole: linkedRole,
      linkedUserIsActive: linkedUserIsActive,
      whatsappOptIn: json['whatsapp_opt_in'] as bool? ?? true,
      isActive: json['is_active'] as bool? ?? true,
      hasHistory: json['has_history'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'full_name': fullName,
      'email': effectiveEmail,
      'registration_number': registrationNumber,
      'class_name': className,
      'section': section,
      'phone_number': phoneNumber,
      'country_code': countryCode,
      'team_id': teamId,
      'team_name': teamName,
      'linked_user_id': linkedUserId,
      'linked_username': linkedUsername,
      'linked_email': linkedEmail,
      'linked_role': linkedRole,
      'linked_user_is_active': linkedUserIsActive,
      'whatsapp_opt_in': whatsappOptIn,
      'is_active': isActive,
      'has_history': hasHistory,
    };
  }

  factory Member.fromSqliteMap(Map<String, dynamic> map) {
    return Member(
      id: map['id'] as int,
      fullName: map['full_name'] as String,
      email: map['email'] as String? ?? map['linked_email'] as String?,
      registrationNumber: map['registration_number'] as String?,
      className: map['class_name'] as String? ?? '',
      section: map['section'] as String?,
      phoneNumber: map['phone_number'] as String? ?? '',
      countryCode: map['country_code'] as String? ?? '+91',
      teamId: map['team_id'] as int,
      teamName: map['team_name'] as String?,
      linkedUserId: map['linked_user_id'] as int?,
      linkedUsername: map['linked_username'] as String?,
      linkedEmail: map['linked_email'] as String?,
      linkedRole: map['linked_role'] as String?,
      linkedUserIsActive: map['linked_user_is_active'] == null ? null : (map['linked_user_is_active'] as int) == 1,
      whatsappOptIn: (map['whatsapp_opt_in'] as int? ?? 1) == 1,
      isActive: (map['is_active'] as int? ?? 1) == 1,
      hasHistory: (map['has_history'] as int? ?? 0) == 1,
    );
  }

  Map<String, dynamic> toSqliteMap() {
    return {
      'id': id,
      'full_name': fullName,
      'email': effectiveEmail,
      'registration_number': registrationNumber,
      'class_name': className,
      'section': section,
      'phone_number': phoneNumber,
      'country_code': countryCode,
      'team_id': teamId,
      'team_name': teamName,
      'linked_user_id': linkedUserId,
      'linked_username': linkedUsername,
      'linked_email': linkedEmail,
      'linked_role': linkedRole,
      'linked_user_is_active': linkedUserIsActive == null ? null : (linkedUserIsActive! ? 1 : 0),
      'whatsapp_opt_in': whatsappOptIn ? 1 : 0,
      'is_active': isActive ? 1 : 0,
      'has_history': hasHistory ? 1 : 0,
      'cached_at': DateTime.now().toUtc().toIso8601String(),
    };
  }
}
