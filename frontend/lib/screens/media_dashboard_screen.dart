import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';
import '../config/constants.dart';
import '../models/media.dart';
import '../services/auth_service.dart';
import '../services/media_service.dart';
import '../services/sync_service.dart';
import '../widgets/custom_card.dart';
import 'event_media_folder_screen.dart';
import 'community_screen.dart';
import '../services/community_service.dart';

class MediaDashboardScreen extends StatefulWidget {
  final AuthService authService;
  final SyncService syncService;
  final VoidCallback onLogout;
  final MediaService? mediaService;

  const MediaDashboardScreen({
    super.key,
    required this.authService,
    required this.syncService,
    required this.onLogout,
    this.mediaService,
  });

  @override
  State<MediaDashboardScreen> createState() => _MediaDashboardScreenState();
}

class _MediaDashboardScreenState extends State<MediaDashboardScreen> {
  late MediaService _mediaService;
  bool _isLoading = false;
  String? _errorMessage;

  List<MediaEventFolder> _folders = [];
  Map<String, dynamic> _driveStatus = {};
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _mediaService = widget.mediaService ?? MediaService(apiClient: widget.syncService.apiClient);
    _loadDashboardData();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadDashboardData({String? search}) async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final folders = await _mediaService.listFolders(query: search);
      final driveStatus = await _mediaService.getDriveStatus();

      if (mounted) {
        setState(() {
          _folders = folders;
          _driveStatus = driveStatus;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
          _errorMessage = e.toString();
        });
      }
    }
  }

  Future<void> _connectGoogleDrive() async {
    try {
      final authUrl = await _mediaService.getDriveAuthUrl();
      if (authUrl == null || authUrl.isEmpty) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Could not generate Google authorization link.')),
          );
        }
        return;
      }

      final uri = Uri.parse(authUrl);
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Could not open authorization URL: $authUrl')),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Drive Connect Notice: $e')),
        );
      }
    }
  }

  Future<void> _disconnectGoogleDrive() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Disconnect Google Drive?'),
        content: const Text(
          'This will revoke stored application access to Google Drive. '
          'Your files in Google Drive will remain completely untouched.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppConstants.dangerRed),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Disconnect'),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    try {
      await _mediaService.disconnectDrive();
      await _loadDashboardData();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Google Drive disconnected.')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error disconnecting Drive: $e')),
        );
      }
    }
  }

  Future<void> _showCreateFolderDialog() async {
    final nameController = TextEditingController();
    final descController = TextEditingController();
    DateTime? selectedDate = DateTime.now();
    bool createInDrive = _driveStatus['is_connected'] == true;

    await showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) {
          final df = DateFormat('dd MMM yyyy');
          return AlertDialog(
            title: const Text('Create Event Folder'),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    controller: nameController,
                    decoration: const InputDecoration(
                      labelText: 'Event Name *',
                      hintText: 'e.g. Hackathon 2026, Annual Tech Fest',
                      border: OutlineInputBorder(),
                    ),
                    autofocus: true,
                  ),
                  const SizedBox(height: 14),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          selectedDate != null ? 'Date: ${df.format(selectedDate!)}' : 'No date chosen',
                          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
                        ),
                      ),
                      TextButton.icon(
                        icon: const Icon(Icons.calendar_today, size: 16),
                        label: const Text('Pick Date'),
                        onPressed: () async {
                          final picked = await showDatePicker(
                            context: context,
                            initialDate: selectedDate ?? DateTime.now(),
                            firstDate: DateTime(2020),
                            lastDate: DateTime(2035),
                          );
                          if (picked != null) {
                            setDialogState(() => selectedDate = picked);
                          }
                        },
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: descController,
                    maxLines: 2,
                    decoration: const InputDecoration(
                      labelText: 'Description (Optional)',
                      hintText: 'Brief summary of coverage or design tasks...',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  if (_driveStatus['is_connected'] == true) ...[
                    const SizedBox(height: 14),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Create in Google Drive', style: TextStyle(fontSize: 13)),
                      subtitle: const Text('Also creates a matching folder in your Drive', style: TextStyle(fontSize: 11)),
                      value: createInDrive,
                      activeThumbColor: Colors.green,
                      onChanged: (val) => setDialogState(() => createInDrive = val),
                    ),
                  ],
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(),
                child: const Text('Cancel'),
              ),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppConstants.pureBlack,
                  foregroundColor: Colors.white,
                ),
                onPressed: () async {
                  final name = nameController.text.trim();
                  if (name.isEmpty) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Please enter an event name.')),
                    );
                    return;
                  }

                  final messenger = ScaffoldMessenger.of(context);
                  final navigator = Navigator.of(context);
                  Navigator.of(ctx).pop();
                  try {
                    setState(() => _isLoading = true);
                    final newFolder = await _mediaService.createFolder(
                      name: name,
                      description: descController.text.trim(),
                      eventDate: selectedDate,
                      createInDrive: createInDrive,
                    );
                    await _loadDashboardData();
                    if (mounted) {
                      messenger.showSnackBar(
                        SnackBar(content: Text("Event folder '${newFolder.name}' created.")),
                      );
                      // Navigate directly into new folder
                      navigator.push(
                        MaterialPageRoute(
                          builder: (_) => EventMediaFolderScreen(
                            folder: newFolder,
                            mediaService: _mediaService,
                            authService: widget.authService,
                          ),
                        ),
                      );
                    }
                  } catch (e) {
                    if (mounted) {
                      setState(() => _isLoading = false);
                      messenger.showSnackBar(
                        SnackBar(content: Text('Failed to create folder: $e')),
                      );
                    }
                  }
                },
                child: const Text('Create Folder'),
              ),
            ],
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final memberName = widget.authService.displayName;
    final username = widget.authService.username;
    final teamName = widget.authService.teamName ?? 'Media';

    final isDriveConnected = _driveStatus['is_connected'] == true;
    final connectedEmail = _driveStatus['google_email']?.toString();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Media Team Portal'),
        elevation: 0,
        actions: [
          IconButton(
            key: const Key('btn_open_community'),
            icon: const Icon(Icons.forum_outlined),
            tooltip: 'Discord Community',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (context) => CommunityScreen(
                    communityService: CommunityService(apiClient: widget.syncService.apiClient),
                    authService: widget.authService,
                  ),
                ),
              );
            },
          ),
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh),
            onPressed: () => _loadDashboardData(search: _searchController.text),
          ),
          IconButton(
            tooltip: 'Logout',
            icon: const Icon(Icons.logout),
            onPressed: widget.onLogout,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => _loadDashboardData(search: _searchController.text),
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (_isLoading) const LinearProgressIndicator(),
              if (_errorMessage != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppConstants.dangerRed.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      _errorMessage!,
                      style: const TextStyle(fontSize: 12, color: AppConstants.dangerRed),
                    ),
                  ),
                ),

              // Welcome Profile Card
              CustomCard(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Row(
                    children: [
                      CircleAvatar(
                        radius: 28,
                        backgroundColor: Colors.indigo.withValues(alpha: 0.15),
                        child: Text(
                          memberName.isNotEmpty ? memberName[0].toUpperCase() : 'M',
                          style: const TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.bold,
                            color: Colors.indigo,
                          ),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              memberName,
                              style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              '@$username',
                              style: const TextStyle(
                                fontSize: 13,
                                color: AppConstants.textSecondary,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Wrap(
                              spacing: 8,
                              runSpacing: 4,
                              children: [
                                Chip(
                                  label: Text(
                                    teamName,
                                    style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold),
                                  ),
                                  backgroundColor: Colors.indigo.withValues(alpha: 0.1),
                                  visualDensity: VisualDensity.compact,
                                  padding: EdgeInsets.zero,
                                ),
                                const Chip(
                                  avatar: Icon(Icons.check_circle, size: 14, color: Colors.green),
                                  label: Text(
                                    'Active Account',
                                    style: TextStyle(fontSize: 11, color: Colors.green, fontWeight: FontWeight.w600),
                                  ),
                                  visualDensity: VisualDensity.compact,
                                  padding: EdgeInsets.zero,
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Google Drive Integration Card
              CustomCard(
                child: Padding(
                  padding: const EdgeInsets.all(14.0),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: isDriveConnected
                              ? Colors.green.withValues(alpha: 0.12)
                              : Colors.orange.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Icon(
                          Icons.add_to_drive,
                          color: isDriveConnected ? Colors.green.shade800 : Colors.orange.shade800,
                          size: 22,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              isDriveConnected ? 'Google Drive Connected' : 'Google Drive Storage',
                              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              isDriveConnected
                                  ? (connectedEmail != null ? 'Linked account: $connectedEmail' : 'Active OAuth connection')
                                  : 'Connect existing Drive folders to events without re-uploading',
                              style: const TextStyle(fontSize: 11, color: AppConstants.textSecondary),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton(
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          foregroundColor: isDriveConnected ? AppConstants.dangerRed : Colors.green.shade800,
                          side: BorderSide(color: isDriveConnected ? AppConstants.dangerRed.withValues(alpha: 0.4) : Colors.green),
                        ),
                        onPressed: isDriveConnected ? _disconnectGoogleDrive : _connectGoogleDrive,
                        child: Text(
                          isDriveConnected ? 'Disconnect' : 'Connect Drive',
                          style: const TextStyle(fontSize: 12),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),

              // Event Folders Header & Action Row
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Event Media Folders',
                    style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
                  ),
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppConstants.pureBlack,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    ),
                    icon: const Icon(Icons.create_new_folder_outlined, size: 16),
                    label: const Text('Create Event Folder', style: TextStyle(fontSize: 12)),
                    onPressed: _showCreateFolderDialog,
                  ),
                ],
              ),
              const SizedBox(height: 12),

              // Search Filter Bar
              TextField(
                controller: _searchController,
                decoration: InputDecoration(
                  hintText: 'Search event folders...',
                  prefixIcon: const Icon(Icons.search, size: 18),
                  suffixIcon: _searchController.text.isNotEmpty
                      ? IconButton(
                          icon: const Icon(Icons.clear, size: 18),
                          onPressed: () {
                            _searchController.clear();
                            _loadDashboardData();
                          },
                        )
                      : null,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                  filled: true,
                  fillColor: AppConstants.pureWhite,
                ),
                onSubmitted: (val) => _loadDashboardData(search: val),
              ),
              const SizedBox(height: 16),

              // Event Folders List
              if (_folders.isEmpty && !_isLoading) ...[
                Center(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 36.0),
                    child: Column(
                      children: [
                        Icon(Icons.folder_open, size: 54, color: Colors.grey.shade400),
                        const SizedBox(height: 12),
                        const Text(
                          'No event folders created yet.',
                          style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: AppConstants.darkGray),
                        ),
                        const SizedBox(height: 6),
                        const Text(
                          'Click "Create Event Folder" to start organizing event photos, videos, and posters.',
                          style: TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  ),
                ),
              ] else ...[
                ListView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: _folders.length,
                  itemBuilder: (context, index) {
                    final folder = _folders[index];
                    return _buildFolderCard(folder);
                  },
                ),
              ],

              const SizedBox(height: 24),

              // Operational Scope Card (Retained for documentation and team guidance)
              const Text(
                'Team Scope & Responsibilities',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              CustomCard(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(
                        children: [
                          Icon(Icons.palette_outlined, color: Colors.indigo, size: 20),
                          SizedBox(width: 8),
                          Text(
                            'Design & Media Department Operations',
                            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      const Text(
                        'This single unified team coordinates all visual design and media activities for the department club:',
                        style: TextStyle(fontSize: 13, color: AppConstants.textSecondary),
                      ),
                      const SizedBox(height: 14),
                      _buildResponsibilityRow(
                        Icons.camera_alt_outlined,
                        'Photography & Video Coverage',
                        'Capturing keynote sessions, ceremonies, audience reactions, and high-res media.',
                      ),
                      const SizedBox(height: 12),
                      _buildResponsibilityRow(
                        Icons.brush_outlined,
                        'Graphic Design & Creative Posters',
                        'Designing event banners, brochures, social release flyers, and certificates.',
                      ),
                      const SizedBox(height: 12),
                      _buildResponsibilityRow(
                        Icons.share_outlined,
                        'Social Media & Press Releases',
                        'Publishing highlights, managing Instagram/LinkedIn assets, and visual archives.',
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),

              // Workspaces & Tools section
              const Text(
                'Workspaces & Tools',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: _buildToolCard(
                      icon: Icons.folder_shared_outlined,
                      title: 'Asset Drive',
                      subtitle: 'Cloud storage integration',
                      tag: isDriveConnected ? 'Connected' : 'Ready',
                      onTap: () {
                        if (isDriveConnected) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Connected Drive: $connectedEmail')),
                          );
                        } else {
                          _connectGoogleDrive();
                        }
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildToolCard(
                      icon: Icons.assignment_outlined,
                      title: 'My Assignments',
                      subtitle: 'Active coverage duties',
                      tag: 'Active',
                      onTap: () {
                        Navigator.of(context).pushNamed('/my_tasks');
                      },
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFolderCard(MediaEventFolder folder) {
    final df = DateFormat('dd MMM yyyy');
    final formattedDate = folder.eventDate != null ? df.format(folder.eventDate!) : 'No date set';

    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: const BorderSide(color: AppConstants.borderLight),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: () async {
          await Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => EventMediaFolderScreen(
                folder: folder,
                mediaService: _mediaService,
                authService: widget.authService,
              ),
            ),
          );
          _loadDashboardData();
        },
        child: Padding(
          padding: const EdgeInsets.all(14.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: Colors.indigo.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.folder, color: Colors.indigo, size: 24),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          folder.name,
                          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 2),
                        Row(
                          children: [
                            const Icon(Icons.event_outlined, size: 14, color: AppConstants.textSecondary),
                            const SizedBox(width: 4),
                            Text(
                              formattedDate,
                              style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  _buildSourceChip(folder.storageSource),
                ],
              ),
              if (folder.description != null && folder.description!.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  folder.description!,
                  style: const TextStyle(fontSize: 12, color: AppConstants.darkGray),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
              const Divider(height: 18),
              // Media Statistics Row
              Row(
                children: [
                  _statChip(Icons.photo_outlined, '${folder.photosCount} Photos', Colors.blue),
                  const SizedBox(width: 8),
                  _statChip(Icons.location_on_outlined, '${folder.geotaggedCount} Geotagged', Colors.teal),
                  const SizedBox(width: 8),
                  _statChip(Icons.videocam_outlined, '${folder.videosCount} Videos', Colors.purple),
                  const SizedBox(width: 8),
                  _statChip(Icons.palette_outlined, '${folder.postersCount} Posters', Colors.deepOrange),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSourceChip(String source) {
    Color color;
    String label;
    IconData icon;

    if (source == 'google_drive') {
      color = Colors.green;
      label = 'Drive';
      icon = Icons.add_to_drive;
    } else if (source == 'both') {
      color = Colors.purple;
      label = 'Firebase & Drive';
      icon = Icons.cloud_done;
    } else if (source == 'firebase' || source == 'local') {
      color = Colors.blue;
      label = 'Firebase';
      icon = Icons.cloud_queue;
    } else {
      color = Colors.grey;
      label = 'Empty';
      icon = Icons.folder_open;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: color),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: color)),
        ],
      ),
    );
  }

  Widget _statChip(IconData icon, String label, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 13, color: color),
        const SizedBox(width: 3),
        Text(label, style: const TextStyle(fontSize: 11, color: AppConstants.textSecondary, fontWeight: FontWeight.w500)),
      ],
    );
  }

  Widget _buildResponsibilityRow(IconData icon, String title, String desc) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 18, color: Colors.indigo),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
              const SizedBox(height: 2),
              Text(desc, style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary)),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildToolCard({
    required IconData icon,
    required String title,
    required String subtitle,
    required String tag,
    required VoidCallback onTap,
  }) {
    return CustomCard(
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(12.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Icon(icon, color: Colors.indigo, size: 22),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.green.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      tag,
                      style: const TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: Colors.green,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                title,
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
              ),
              const SizedBox(height: 2),
              Text(
                subtitle,
                style: const TextStyle(fontSize: 11, color: AppConstants.textSecondary),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
