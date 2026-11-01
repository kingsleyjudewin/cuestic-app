import 'dart:async';
import 'package:flutter/material.dart';
import '../config/app_theme.dart';
import '../config/constants.dart';
import '../models/community.dart';
import '../services/auth_service.dart';
import '../services/community_service.dart';

class CommunityScreen extends StatefulWidget {
  final CommunityService communityService;
  final AuthService authService;
  final bool enablePolling;

  const CommunityScreen({
    super.key,
    required this.communityService,
    required this.authService,
    this.enablePolling = true,
  });

  @override
  State<CommunityScreen> createState() => _CommunityScreenState();
}

class _CommunityScreenState extends State<CommunityScreen> {
  List<Community> _communities = [];
  Community? _selectedCommunity;
  CommunityChannel? _selectedChannel;
  List<ChatMessage> _messages = [];

  bool _isLoadingCommunities = false;
  bool _isLoadingMessages = false;
  bool _isSending = false;
  String? _error;

  final TextEditingController _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  Timer? _pollingTimer;

  @override
  void initState() {
    super.initState();
    _loadCommunities();
    // Auto-refresh chat messages every 4 seconds if polling enabled
    if (widget.enablePolling) {
      _pollingTimer = Timer.periodic(const Duration(seconds: 4), (_) {
        if (_selectedCommunity != null && _selectedChannel != null && !_isSending) {
          _refreshMessagesSilent();
        }
      });
    }
  }

  @override
  void dispose() {
    _pollingTimer?.cancel();
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _loadCommunities() async {
    setState(() {
      _isLoadingCommunities = true;
      _error = null;
    });

    try {
      final list = await widget.communityService.fetchCommunities();
      if (!mounted) return;
      setState(() {
        _communities = list;
        _isLoadingCommunities = false;
      });
      if (list.isNotEmpty) {
        await _selectCommunity(list.first);
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoadingCommunities = false;
        _error = e.toString().replaceFirst('Exception: ', '');
      });
    }
  }

  Future<void> _selectCommunity(Community community) async {
    setState(() {
      _selectedCommunity = community;
      _selectedChannel = null;
      _messages = [];
    });

    // If channels are already present in community object, select the first channel immediately
    if (community.channels.isNotEmpty) {
      _selectChannel(community.channels.first);
    }

    try {
      final detailed = await widget.communityService.fetchCommunityDetails(community.id);
      if (!mounted) return;
      setState(() {
        _selectedCommunity = detailed;
      });
      if (_selectedChannel == null && detailed.channels.isNotEmpty) {
        await _selectChannel(detailed.channels.first);
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to load community details: $e'), backgroundColor: AppConstants.dangerRed),
      );
    }
  }

  Future<void> _selectChannel(CommunityChannel channel) async {
    setState(() {
      _selectedChannel = channel;
      _isLoadingMessages = true;
    });

    await _fetchMessages();
  }

  Future<void> _fetchMessages() async {
    if (_selectedCommunity == null || _selectedChannel == null) return;

    try {
      final msgs = await widget.communityService.fetchMessages(
        communityId: _selectedCommunity!.id,
        channelId: _selectedChannel!.id,
      );
      if (!mounted) return;
      setState(() {
        _messages = msgs;
        _isLoadingMessages = false;
      });
      _scrollToBottom();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoadingMessages = false;
      });
    }
  }

  Future<void> _refreshMessagesSilent() async {
    if (_selectedCommunity == null || _selectedChannel == null) return;
    try {
      final msgs = await widget.communityService.fetchMessages(
        communityId: _selectedCommunity!.id,
        channelId: _selectedChannel!.id,
      );
      if (!mounted) return;
      if (msgs.length != _messages.length || (msgs.isNotEmpty && _messages.isNotEmpty && msgs.last.id != _messages.last.id)) {
        setState(() {
          _messages = msgs;
        });
        _scrollToBottom();
      }
    } catch (_) {}
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _handleSendMessage() async {
    final text = _messageController.text.trim();
    if (text.isEmpty || _selectedCommunity == null || _selectedChannel == null || _isSending) return;

    _messageController.clear();
    setState(() => _isSending = true);

    try {
      final sent = await widget.communityService.sendMessage(
        communityId: _selectedCommunity!.id,
        channelId: _selectedChannel!.id,
        content: text,
      );
      if (!mounted) return;
      setState(() {
        _messages.add(sent);
        _isSending = false;
      });
      _scrollToBottom();
    } catch (e) {
      if (!mounted) return;
      setState(() => _isSending = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to send: $e'), backgroundColor: AppConstants.dangerRed),
      );
    }
  }

  Future<void> _showCreateChannelDialog() async {
    if (_selectedCommunity == null) return;
    final nameCtrl = TextEditingController();
    final topicCtrl = TextEditingController();
    String channelType = 'text';

    await showDialog(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setDlgState) {
            return AlertDialog(
              title: const Text('Create Channel / Group Chat'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Channel Name', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                  const SizedBox(height: 6),
                  TextField(
                    key: const Key('input_new_channel_name'),
                    controller: nameCtrl,
                    decoration: const InputDecoration(
                      hintText: 'e.g. stage-setup or group-chat',
                      prefixText: '# ',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Text('Topic / Purpose (Optional)', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                  const SizedBox(height: 6),
                  TextField(
                    key: const Key('input_new_channel_topic'),
                    controller: topicCtrl,
                    decoration: const InputDecoration(
                      hintText: 'e.g. Tasks discussion for volunteers',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Text('Channel Type', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                  const SizedBox(height: 6),
                  DropdownButtonFormField<String>(
                    value: channelType,
                    items: const [
                      DropdownMenuItem(value: 'text', child: Text('Text Channel (#)')),
                      DropdownMenuItem(value: 'group_chat', child: Text('Group Chat (👥)')),
                      DropdownMenuItem(value: 'announcement', child: Text('Announcement (📢)')),
                    ],
                    onChanged: (val) {
                      if (val != null) setDlgState(() => channelType = val);
                    },
                    decoration: const InputDecoration(border: OutlineInputBorder()),
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text('Cancel'),
                ),
                ElevatedButton(
                  key: const Key('btn_confirm_create_channel'),
                  onPressed: () async {
                    final rawName = nameCtrl.text.trim();
                    if (rawName.isEmpty) return;
                    Navigator.pop(ctx);
                    try {
                      final newCh = await widget.communityService.createChannel(
                        communityId: _selectedCommunity!.id,
                        name: rawName,
                        topic: topicCtrl.text.trim(),
                        channelType: channelType,
                      );
                      setState(() {
                        _selectedCommunity!.channels.add(newCh);
                        _selectChannel(newCh);
                      });
                      if (mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text('Created channel #${newCh.name} successfully!'),
                            backgroundColor: AppConstants.successGreen,
                          ),
                        );
                      }
                    } catch (e) {
                      if (mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('Failed to create channel: $e'), backgroundColor: AppConstants.dangerRed),
                        );
                      }
                    }
                  },
                  child: const Text('Create Channel'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  void _showCommunityMembersSheet() {
    if (_selectedCommunity == null) return;

    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) {
        return Container(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Community Members (${_selectedCommunity!.members.length})',
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(ctx),
                  ),
                ],
              ),
              const Divider(),
              Expanded(
                child: ListView.builder(
                  itemCount: _selectedCommunity!.members.length,
                  itemBuilder: (ctx, idx) {
                    final mem = _selectedCommunity!.members[idx];
                    return ListTile(
                      leading: CircleAvatar(
                        backgroundColor: _getRoleColor(mem.userRole ?? mem.role).withValues(alpha: 0.15),
                        child: Text(
                          (mem.displayName ?? mem.username ?? '?')[0].toUpperCase(),
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: _getRoleColor(mem.userRole ?? mem.role),
                          ),
                        ),
                      ),
                      title: Text(mem.displayName ?? mem.username ?? 'Member', style: const TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: Text('@${mem.username ?? ''}', style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary)),
                      trailing: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: _getRoleColor(mem.userRole ?? mem.role).withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: _getRoleColor(mem.userRole ?? mem.role).withValues(alpha: 0.4)),
                        ),
                        child: Text(
                          (mem.userRole ?? mem.role).toUpperCase(),
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: _getRoleColor(mem.userRole ?? mem.role),
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Color _getRoleColor(String role) {
    switch (role.toLowerCase()) {
      case 'president':
        return Colors.red.shade700;
      case 'admin':
        return Colors.blue.shade700;
      case 'team_leader':
      case 'moderator':
        return Colors.amber.shade800;
      default:
        return Colors.teal.shade700;
    }
  }

  Color _getCommunityColor(Community c) {
    if (c.slug.contains('volunteering')) return const Color(0xFF10B981); // Emerald
    if (c.slug.contains('documentation')) return const Color(0xFF8B5CF6); // Purple
    if (c.slug.contains('media')) return const Color(0xFFF59E0B); // Amber
    return const Color(0xFF2563EB); // Blue
  }

  @override
  Widget build(BuildContext context) {
    final isDesktop = MediaQuery.of(context).size.width >= 800;

    return Scaffold(
      backgroundColor: const Color(0xFFF2F3F5),
      appBar: AppBar(
        elevation: 0.5,
        backgroundColor: AppConstants.pureWhite,
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: const Color(0xFF5865F2).withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.forum_outlined, color: Color(0xFF5865F2), size: 22),
            ),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _selectedCommunity?.name ?? 'CUestIC Discord Community',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: AppConstants.pureBlack),
                ),
                if (_selectedChannel != null)
                  Text(
                    '# ${_selectedChannel!.name}',
                    style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                  ),
              ],
            ),
          ],
        ),
        actions: [
          if (_selectedCommunity != null)
            IconButton(
              tooltip: 'Members (${_selectedCommunity!.members.length})',
              icon: const Icon(Icons.people_outline, color: AppConstants.pureBlack),
              onPressed: _showCommunityMembersSheet,
            ),
          IconButton(
            key: const Key('btn_refresh_community'),
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh, color: AppConstants.pureBlack),
            onPressed: () {
              _loadCommunities();
            },
          ),
        ],
      ),
      body: _isLoadingCommunities
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.error_outline, size: 48, color: AppConstants.dangerRed),
                      const SizedBox(height: 12),
                      Text(_error!, style: const TextStyle(color: AppConstants.dangerRed)),
                      const SizedBox(height: 16),
                      ElevatedButton(onPressed: _loadCommunities, child: const Text('Retry')),
                    ],
                  ),
                )
              : Row(
                  children: [
                    // 1. Left Server Rail
                    _buildServerRail(),

                    // 2. Middle Channels Sidebar (desktop) or Drawer
                    if (isDesktop) _buildChannelsSidebar(),

                    // 3. Main Chat View
                    Expanded(child: _buildChatPane(showChannelHeaderDropdown: !isDesktop)),
                  ],
                ),
    );
  }

  Widget _buildServerRail() {
    return Container(
      width: 72,
      decoration: const BoxDecoration(
        color: Color(0xFFE3E5E8),
        border: Border(right: BorderSide(color: Color(0xFFD1D5DB))),
      ),
      child: Column(
        children: [
          const SizedBox(height: 12),
          // CUestIC Club Home Icon
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: const Color(0xFF5865F2),
              borderRadius: BorderRadius.circular(16),
            ),
            child: const Icon(Icons.groups, color: Colors.white, size: 28),
          ),
          const SizedBox(height: 8),
          const Divider(indent: 14, endIndent: 14, thickness: 1.5),
          const SizedBox(height: 6),

          // Community Server Icons
          Expanded(
            child: ListView.separated(
              itemCount: _communities.length,
              separatorBuilder: (context, _) => const SizedBox(height: 10),
              itemBuilder: (ctx, idx) {
                final c = _communities[idx];
                final isSelected = _selectedCommunity?.id == c.id;
                final color = _getCommunityColor(c);

                return InkWell(
                  key: Key('server_icon_${c.slug}'),
                  onTap: () => _selectCommunity(c),
                  child: Row(
                    children: [
                      // White active bar indicator
                      Container(
                        width: 4,
                        height: isSelected ? 36 : 8,
                        decoration: BoxDecoration(
                          color: isSelected ? Colors.black87 : Colors.transparent,
                          borderRadius: const BorderRadius.horizontal(right: Radius.circular(4)),
                        ),
                      ),
                      const SizedBox(width: 8),
                      // Server Bubble
                      Tooltip(
                        message: c.name,
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 200),
                          width: 48,
                          height: 48,
                          decoration: BoxDecoration(
                            color: color,
                            borderRadius: BorderRadius.circular(isSelected ? 16 : 24),
                            boxShadow: isSelected
                                ? [BoxShadow(color: color.withValues(alpha: 0.4), blurRadius: 6, offset: const Offset(0, 2))]
                                : null,
                          ),
                          child: Center(
                            child: Text(
                              c.name.split(' ').map((w) => w.isNotEmpty ? w[0] : '').take(2).join(),
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                                fontSize: 16,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChannelsSidebar() {
    if (_selectedCommunity == null) {
      return const SizedBox(width: 220);
    }

    final channels = _selectedCommunity!.channels;

    return Container(
      width: 220,
      decoration: const BoxDecoration(
        color: Color(0xFFF2F3F5),
        border: Border(right: BorderSide(color: Color(0xFFE5E7EB))),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Community Header
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: Color(0xFFE5E7EB))),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    _selectedCommunity!.name,
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),

          // Channel Category & Add Channel Button
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 8, 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Expanded(
                  child: Text(
                    'CHANNELS & GROUP CHATS',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: AppConstants.textSecondary,
                      letterSpacing: 0.5,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                IconButton(
                  key: const Key('btn_add_channel'),
                  icon: const Icon(Icons.add, size: 18, color: AppConstants.pureBlack),
                  tooltip: 'Create Channel',
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                  onPressed: _showCreateChannelDialog,
                ),
              ],
            ),
          ),

          // Channel List
          Expanded(
            child: ListView.builder(
              itemCount: channels.length,
              itemBuilder: (ctx, idx) {
                final ch = channels[idx];
                final isSelected = _selectedChannel?.id == ch.id;

                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  child: InkWell(
                    key: Key('channel_tile_${ch.name}'),
                    onTap: () => _selectChannel(ch),
                    borderRadius: BorderRadius.circular(6),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                      decoration: BoxDecoration(
                        color: isSelected ? Colors.black.withValues(alpha: 0.08) : Colors.transparent,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            ch.channelType == 'announcement'
                                ? Icons.campaign
                                : ch.channelType == 'group_chat'
                                    ? Icons.people
                                    : Icons.tag,
                            size: 18,
                            color: isSelected ? AppConstants.pureBlack : AppConstants.textSecondary,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              ch.name,
                              style: TextStyle(
                                fontSize: 13,
                                fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                                color: isSelected ? AppConstants.pureBlack : const Color(0xFF4B5563),
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChatPane({required bool showChannelHeaderDropdown}) {
    if (_selectedCommunity == null) {
      return const Center(child: Text('Select a community to begin chatting.'));
    }

    if (_selectedChannel == null) {
      return const Center(child: Text('No channels available.'));
    }

    return Container(
      color: AppConstants.pureWhite,
      child: Column(
        children: [
          // Channel Title Bar
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: AppConstants.borderLight)),
            ),
            child: Row(
              children: [
                Icon(
                  _selectedChannel!.channelType == 'announcement'
                      ? Icons.campaign
                      : _selectedChannel!.channelType == 'group_chat'
                          ? Icons.people
                          : Icons.tag,
                  color: AppConstants.pureBlack,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Text(
                  _selectedChannel!.name,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                ),
                if (_selectedChannel!.topic != null && _selectedChannel!.topic!.isNotEmpty) ...[
                  const SizedBox(width: 12),
                  const Text('|', style: TextStyle(color: AppConstants.borderLight)),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      _selectedChannel!.topic!,
                      style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ] else
                  const Spacer(),
                if (showChannelHeaderDropdown) ...[
                  PopupMenuButton<CommunityChannel>(
                    tooltip: 'Switch Channel',
                    icon: const Icon(Icons.keyboard_arrow_down),
                    onSelected: _selectChannel,
                    itemBuilder: (ctx) => _selectedCommunity!.channels.map((ch) {
                      return PopupMenuItem(
                        value: ch,
                        child: Text('# ${ch.name}'),
                      );
                    }).toList(),
                  ),
                  IconButton(
                    tooltip: 'Create Channel',
                    icon: const Icon(Icons.add, size: 20),
                    onPressed: _showCreateChannelDialog,
                  ),
                ],
              ],
            ),
          ),

          // Message Stream
          Expanded(
            child: _isLoadingMessages
                ? const Center(child: CircularProgressIndicator())
                : _messages.isEmpty
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(32.0),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Container(
                                padding: const EdgeInsets.all(16),
                                decoration: BoxDecoration(
                                  color: Colors.purple.withValues(alpha: 0.1),
                                  shape: BoxShape.circle,
                                ),
                                child: const Icon(Icons.waving_hand, size: 36, color: Colors.purple),
                              ),
                              const SizedBox(height: 16),
                              Text(
                                'Welcome to #${_selectedChannel!.name}!',
                                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
                              ),
                              const SizedBox(height: 6),
                              const Text(
                                'This is the start of the community chat channel. Send a message to say hello!',
                                textAlign: TextAlign.center,
                                style: TextStyle(color: AppConstants.textSecondary, fontSize: 13),
                              ),
                            ],
                          ),
                        ),
                      )
                    : ListView.builder(
                        controller: _scrollController,
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        itemCount: _messages.length,
                        itemBuilder: (ctx, idx) {
                          final msg = _messages[idx];
                          final roleColor = _getRoleColor(msg.senderRole);

                          return Padding(
                            padding: const EdgeInsets.symmetric(vertical: 8.0),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                CircleAvatar(
                                  radius: 18,
                                  backgroundColor: roleColor.withValues(alpha: 0.15),
                                  child: Text(
                                    msg.senderName.isNotEmpty ? msg.senderName[0].toUpperCase() : '?',
                                    style: TextStyle(fontWeight: FontWeight.bold, color: roleColor, fontSize: 14),
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        children: [
                                          Text(
                                            msg.senderName,
                                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                                          ),
                                          const SizedBox(width: 8),
                                          Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
                                            decoration: BoxDecoration(
                                              color: roleColor.withValues(alpha: 0.12),
                                              borderRadius: BorderRadius.circular(4),
                                            ),
                                            child: Text(
                                              msg.senderRole.toUpperCase(),
                                              style: TextStyle(
                                                fontSize: 9,
                                                fontWeight: FontWeight.bold,
                                                color: roleColor,
                                              ),
                                            ),
                                          ),
                                          const SizedBox(width: 8),
                                          Text(
                                            '${msg.createdAt.hour.toString().padLeft(2, '0')}:${msg.createdAt.minute.toString().padLeft(2, '0')}',
                                            style: const TextStyle(fontSize: 10, color: AppConstants.textSecondary),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        msg.content,
                                        style: const TextStyle(fontSize: 14, height: 1.35, color: Color(0xFF1F2937)),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
          ),

          // Message Composer Input Box
          Container(
            padding: const EdgeInsets.all(12),
            decoration: const BoxDecoration(
              color: AppConstants.pureWhite,
              border: Border(top: BorderSide(color: AppConstants.borderLight)),
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    key: const Key('input_chat_message'),
                    controller: _messageController,
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => _handleSendMessage(),
                    decoration: InputDecoration(
                      hintText: 'Message #${_selectedChannel!.name}',
                      hintStyle: const TextStyle(fontSize: 13, color: AppConstants.textSecondary),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      filled: true,
                      fillColor: const Color(0xFFF3F4F6),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: BorderSide.none,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  key: const Key('btn_send_chat_message'),
                  icon: _isSending
                      ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.send_rounded, color: Color(0xFF5865F2)),
                  onPressed: _isSending ? null : _handleSendMessage,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
