import '../models/community.dart';
import 'api_client.dart';

class CommunityService {
  final ApiClient apiClient;

  CommunityService({required this.apiClient});

  /// Fetch all communities accessible to the authenticated user
  Future<List<Community>> fetchCommunities() async {
    final data = await apiClient.get('/communities');
    final list = data as List<dynamic>? ?? [];
    return list.map((item) => Community.fromJson(item as Map<String, dynamic>)).toList();
  }

  /// Fetch full details for a single community (channels & members)
  Future<Community> fetchCommunityDetails(int communityId) async {
    final data = await apiClient.get('/communities/$communityId');
    return Community.fromJson(data as Map<String, dynamic>);
  }

  /// Create a new channel or group chat in a community
  Future<CommunityChannel> createChannel({
    required int communityId,
    required String name,
    String? topic,
    String channelType = 'text',
  }) async {
    final data = await apiClient.post(
      '/communities/$communityId/channels',
      body: {
        'name': name,
        'topic': topic,
        'channel_type': channelType,
      },
    );
    return CommunityChannel.fromJson(data as Map<String, dynamic>);
  }

  /// Fetch messages for a channel
  Future<List<ChatMessage>> fetchMessages({
    required int communityId,
    required int channelId,
    int limit = 50,
    int? beforeId,
  }) async {
    String query = '?limit=$limit';
    if (beforeId != null) query += '&before_id=$beforeId';

    final data = await apiClient.get('/communities/$communityId/channels/$channelId/messages$query');
    final list = data as List<dynamic>? ?? [];
    return list.map((item) => ChatMessage.fromJson(item as Map<String, dynamic>)).toList();
  }

  /// Post a message to a channel
  Future<ChatMessage> sendMessage({
    required int communityId,
    required int channelId,
    required String content,
    String messageType = 'text',
    int? parentId,
  }) async {
    final data = await apiClient.post(
      '/communities/$communityId/channels/$channelId/messages',
      body: {
        'content': content,
        'message_type': messageType,
        'parent_id': parentId,
      },
    );
    return ChatMessage.fromJson(data as Map<String, dynamic>);
  }

  /// Create a custom community
  Future<Community> createCommunity({
    required String name,
    String? description,
    String? icon,
    String? color,
  }) async {
    final data = await apiClient.post(
      '/communities',
      body: {
        'name': name,
        'description': description,
        'icon': icon,
        'color': color,
      },
    );
    return Community.fromJson(data as Map<String, dynamic>);
  }
}
