class Community {
  final int id;
  final String name;
  final String slug;
  final String? description;
  final String? icon;
  final String? color;
  final int? teamId;
  final String? teamName;
  final String? teamSlug;
  final bool isTeamRestricted;
  final int channelCount;
  final int memberCount;
  final List<CommunityChannel> channels;
  final List<CommunityMember> members;

  Community({
    required this.id,
    required this.name,
    required this.slug,
    this.description,
    this.icon,
    this.color,
    this.teamId,
    this.teamName,
    this.teamSlug,
    this.isTeamRestricted = true,
    this.channelCount = 0,
    this.memberCount = 0,
    this.channels = const [],
    this.members = const [],
  });

  factory Community.fromJson(Map<String, dynamic> json) {
    var rawChannels = json['channels'] as List<dynamic>? ?? [];
    var rawMembers = json['members'] as List<dynamic>? ?? [];

    return Community(
      id: json['id'] as int,
      name: json['name'] as String,
      slug: json['slug'] as String,
      description: json['description'] as String?,
      icon: json['icon'] as String?,
      color: json['color'] as String?,
      teamId: json['team_id'] as int?,
      teamName: json['team_name'] as String?,
      teamSlug: json['team_slug'] as String?,
      isTeamRestricted: json['is_team_restricted'] as bool? ?? true,
      channelCount: json['channel_count'] as int? ?? rawChannels.length,
      memberCount: json['member_count'] as int? ?? rawMembers.length,
      channels: rawChannels.map((c) => CommunityChannel.fromJson(c as Map<String, dynamic>)).toList(),
      members: rawMembers.map((m) => CommunityMember.fromJson(m as Map<String, dynamic>)).toList(),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'slug': slug,
    'description': description,
    'icon': icon,
    'color': color,
    'team_id': teamId,
    'team_name': teamName,
    'team_slug': teamSlug,
    'is_team_restricted': isTeamRestricted,
    'channel_count': channelCount,
    'member_count': memberCount,
  };
}

class CommunityChannel {
  final int id;
  final int communityId;
  final String name;
  final String? topic;
  final String channelType;
  final int position;
  final bool isPrivate;
  final Map<String, dynamic>? lastMessage;

  CommunityChannel({
    required this.id,
    required this.communityId,
    required this.name,
    this.topic,
    this.channelType = 'text',
    this.position = 0,
    this.isPrivate = false,
    this.lastMessage,
  });

  factory CommunityChannel.fromJson(Map<String, dynamic> json) {
    return CommunityChannel(
      id: json['id'] as int? ?? 0,
      communityId: json['community_id'] as int? ?? 0,
      name: json['name'] as String? ?? 'general',
      topic: json['topic'] as String?,
      channelType: json['channel_type'] as String? ?? 'text',
      position: json['position'] as int? ?? 0,
      isPrivate: json['is_private'] as bool? ?? false,
      lastMessage: json['last_message'] as Map<String, dynamic>?,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'community_id': communityId,
    'name': name,
    'topic': topic,
    'channel_type': channelType,
    'position': position,
    'is_private': isPrivate,
  };
}

class CommunityMember {
  final int id;
  final int communityId;
  final int userId;
  final String? username;
  final String? displayName;
  final String role;
  final String? userRole;
  final String? nickname;
  final DateTime? joinedAt;

  CommunityMember({
    required this.id,
    required this.communityId,
    required this.userId,
    this.username,
    this.displayName,
    this.role = 'member',
    this.userRole,
    this.nickname,
    this.joinedAt,
  });

  factory CommunityMember.fromJson(Map<String, dynamic> json) {
    return CommunityMember(
      id: json['id'] as int? ?? 0,
      communityId: json['community_id'] as int? ?? 0,
      userId: json['user_id'] as int? ?? (json['id'] as int? ?? 0),
      username: json['username'] as String?,
      displayName: json['display_name'] as String?,
      role: json['role'] as String? ?? 'member',
      userRole: json['user_role'] as String?,
      nickname: json['nickname'] as String?,
      joinedAt: json['joined_at'] != null ? DateTime.tryParse(json['joined_at'] as String) : null,
    );
  }
}

class ChatMessage {
  final int id;
  final int communityId;
  final int channelId;
  final int userId;
  final String senderName;
  final String senderRole;
  final String content;
  final String messageType;
  final int? parentId;
  final String? attachmentUrl;
  final DateTime createdAt;

  ChatMessage({
    required this.id,
    required this.communityId,
    required this.channelId,
    required this.userId,
    required this.senderName,
    required this.senderRole,
    required this.content,
    this.messageType = 'text',
    this.parentId,
    this.attachmentUrl,
    required this.createdAt,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: json['id'] as int? ?? 0,
      communityId: json['community_id'] as int? ?? 0,
      channelId: json['channel_id'] as int? ?? 0,
      userId: json['user_id'] as int? ?? 0,
      senderName: json['sender_name'] as String? ?? 'Member',
      senderRole: json['sender_role'] as String? ?? 'member',
      content: json['content'] as String? ?? '',
      messageType: json['message_type'] as String? ?? 'text',
      parentId: json['parent_id'] as int?,
      attachmentUrl: json['attachment_url'] as String?,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String) ?? DateTime.now()
          : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'community_id': communityId,
    'channel_id': channelId,
    'user_id': userId,
    'sender_name': senderName,
    'sender_role': senderRole,
    'content': content,
    'message_type': messageType,
    'parent_id': parentId,
    'attachment_url': attachmentUrl,
    'created_at': createdAt.toIso8601String(),
  };
}
