import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:file_picker/file_picker.dart';
import '../config/constants.dart';
import '../models/media.dart';
import '../services/auth_service.dart';
import '../services/media_service.dart';
import '../widgets/custom_card.dart';
import '../widgets/primary_button.dart';

class EventMediaFolderScreen extends StatefulWidget {
  final MediaEventFolder folder;
  final MediaService mediaService;
  final AuthService authService;

  const EventMediaFolderScreen({
    super.key,
    required this.folder,
    required this.mediaService,
    required this.authService,
  });

  @override
  State<EventMediaFolderScreen> createState() => _EventMediaFolderScreenState();
}

class _EventMediaFolderScreenState extends State<EventMediaFolderScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  late MediaEventFolder _currentFolder;

  bool _isLoading = false;
  String? _errorMessage;

  List<MediaFileItem> _allFiles = [];
  Map<String, dynamic> _driveStatus = {};

  final List<Map<String, dynamic>> _categories = [
    {
      'key': 'geotagged_photos',
      'label': 'Geotagged Photos',
      'icon': Icons.location_on_outlined,
      'color': Colors.teal,
    },
    {
      'key': 'photos',
      'label': 'Normal Photos',
      'icon': Icons.photo_outlined,
      'color': Colors.blue,
    },
    {
      'key': 'videos',
      'label': 'Video Clips',
      'icon': Icons.videocam_outlined,
      'color': Colors.purple,
    },
    {
      'key': 'posters',
      'label': 'Posters & Designs',
      'icon': Icons.palette_outlined,
      'color': Colors.deepOrange,
    },
  ];

  @override
  void initState() {
    super.initState();
    _currentFolder = widget.folder;
    _tabController = TabController(length: _categories.length, vsync: this);
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final updatedFolder = await widget.mediaService.getFolder(_currentFolder.id);
      final files = await widget.mediaService.listFolderFiles(_currentFolder.id);
      final driveStatus = await widget.mediaService.getDriveStatus();

      if (mounted) {
        setState(() {
          _currentFolder = updatedFolder;
          _allFiles = files;
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

  List<MediaFileItem> _getFilesForCategory(String categoryKey) {
    return _allFiles.where((f) => f.category == categoryKey).toList();
  }

  Future<void> _openUrl(String url) async {
    final uri = Uri.parse(url);
    try {
      if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Could not open link: $url')),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error launching link: $e')),
        );
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Google Drive Linking & Browsing Workflows
  // ---------------------------------------------------------------------------
  Future<void> _showLinkDriveDialog() async {
    final isConnected = _driveStatus['is_connected'] == true;
    if (!isConnected) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please connect your Google Drive account first from the Media Workspace.')),
      );
      return;
    }

    showDialog(
      context: context,
      builder: (ctx) => _SelectDriveFolderDialog(
        mediaService: widget.mediaService,
        onFolderSelected: (driveFolder) async {
          Navigator.of(ctx).pop();
          try {
            setState(() => _isLoading = true);
            final updated = await widget.mediaService.linkDriveFolder(
              folderId: _currentFolder.id,
              driveFolderId: driveFolder.id,
              driveFolderName: driveFolder.name,
              webViewLink: driveFolder.webViewLink,
            );
            if (mounted) {
              setState(() {
                _currentFolder = updated;
                _isLoading = false;
              });
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('Linked Google Drive folder: ${driveFolder.name}')),
              );
            }
          } catch (e) {
            if (mounted) {
              setState(() => _isLoading = false);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('Failed to link Drive folder: $e')),
              );
            }
          }
        },
      ),
    );
  }

  Future<void> _unlinkDriveFolder() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Unlink Google Drive Folder?'),
        content: const Text(
          'This will disconnect the Drive folder from this event. '
          'Your original files on Google Drive will NOT be deleted.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppConstants.dangerRed),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Unlink'),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    try {
      setState(() => _isLoading = true);
      final updated = await widget.mediaService.unlinkDriveFolder(_currentFolder.id);
      if (mounted) {
        setState(() {
          _currentFolder = updated;
          _isLoading = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Google Drive folder unlinked.')),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to unlink Drive folder: $e')),
        );
      }
    }
  }

  Future<void> _showBrowseDriveDialog() async {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => _BrowseDriveFilesSheet(
        folder: _currentFolder,
        mediaService: widget.mediaService,
        onFileLinked: () {
          _loadData();
        },
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Upload Workflow
  // ---------------------------------------------------------------------------
  Future<void> _showUploadDialog() async {
    final currentCat = _categories[_tabController.index]['key'] as String;
    String selectedCategory = currentCat;
    String selectedDestination = 'firebase';

    final hasDrive = _currentFolder.hasDriveLinked;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setModalState) {
          return Padding(
            padding: EdgeInsets.only(
              left: 20,
              right: 20,
              top: 20,
              bottom: MediaQuery.of(context).viewInsets.bottom + 24,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Upload Media Files',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close),
                      onPressed: () => Navigator.of(ctx).pop(),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                const Text('Select Category', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _categories.map((c) {
                    final isSel = c['key'] == selectedCategory;
                    return ChoiceChip(
                      label: Text(c['label'] as String, style: const TextStyle(fontSize: 12)),
                      selected: isSel,
                      onSelected: (val) {
                        if (val) setModalState(() => selectedCategory = c['key'] as String);
                      },
                    );
                  }).toList(),
                ),
                const SizedBox(height: 18),
                const Text('Storage Destination', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        style: OutlinedButton.styleFrom(
                          backgroundColor: selectedDestination == 'firebase'
                              ? Colors.indigo.withValues(alpha: 0.1)
                              : Colors.transparent,
                          side: BorderSide(
                            color: selectedDestination == 'firebase' ? Colors.indigo : AppConstants.borderLight,
                            width: 1.5,
                          ),
                          padding: const EdgeInsets.symmetric(vertical: 12),
                        ),
                        icon: const Icon(Icons.cloud_upload_outlined, size: 18),
                        label: const Text('Firebase Storage', style: TextStyle(fontSize: 12)),
                        onPressed: () => setModalState(() => selectedDestination = 'firebase'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: OutlinedButton.icon(
                        style: OutlinedButton.styleFrom(
                          backgroundColor: selectedDestination == 'google_drive'
                              ? Colors.green.withValues(alpha: 0.1)
                              : Colors.transparent,
                          side: BorderSide(
                            color: selectedDestination == 'google_drive' ? Colors.green : AppConstants.borderLight,
                            width: 1.5,
                          ),
                          padding: const EdgeInsets.symmetric(vertical: 12),
                        ),
                        icon: const Icon(Icons.add_to_drive, size: 18),
                        label: const Text('Google Drive', style: TextStyle(fontSize: 12)),
                        onPressed: hasDrive
                            ? () => setModalState(() => selectedDestination = 'google_drive')
                            : null,
                      ),
                    ),
                  ],
                ),
                if (!hasDrive && selectedDestination == 'google_drive')
                  const Padding(
                    padding: EdgeInsets.only(top: 6),
                    child: Text(
                      'Link a Google Drive folder first to enable direct Drive uploads.',
                      style: TextStyle(fontSize: 11, color: AppConstants.warningOrange),
                    ),
                  ),
                const SizedBox(height: 24),
                PrimaryButton(
                  label: 'Choose Files to Upload',
                  icon: Icons.attach_file,
                  onPressed: () async {
                    Navigator.of(ctx).pop();
                    await _pickAndUploadFiles(category: selectedCategory, destination: selectedDestination);
                  },
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Future<void> _pickAndUploadFiles({required String category, required String destination}) async {
    FileType pickType = FileType.any;
    if (category == 'geotagged_photos' || category == 'photos') {
      pickType = FileType.image;
    } else if (category == 'videos') {
      pickType = FileType.video;
    }

    try {
      final pickedFiles = await FilePicker.pickFiles(
        type: pickType,
      );

      if (pickedFiles.isEmpty) return;

      int successful = 0;
      int failed = 0;

      setState(() => _isLoading = true);

      for (final file in pickedFiles) {
        try {
          final bytes = await file.readAsBytes();
          final name = file.name;

          await widget.mediaService.uploadMedia(
            folderId: _currentFolder.id,
            bytes: bytes,
            filename: name,
            category: category,
            destination: destination,
          );
          successful++;
        } catch (e) {
          failed++;
          debugPrint('Failed uploading file ${file.name}: $e');
        }
      }

      await _loadData();

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Upload Complete: $successful uploaded'
              '${failed > 0 ? ', $failed failed' : ''}.',
            ),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('File picker error: $e')),
        );
      }
    }
  }

  Future<void> _deleteFile(MediaFileItem item) async {
    final isDrive = item.isDrive;
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(isDrive ? 'Unlink Drive File?' : 'Delete Media File?'),
        content: Text(
          isDrive
              ? "This unlinks '${item.originalFilename}' from this event. "
                "The original file on Google Drive will NOT be deleted."
              : "Permanently delete '${item.originalFilename}' from storage?",
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppConstants.dangerRed),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(isDrive ? 'Unlink' : 'Delete'),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    try {
      await widget.mediaService.deleteMediaFile(item.id);
      await _loadData();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(isDrive ? 'File unlinked from event.' : 'File deleted.')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete file: $e')),
        );
      }
    }
  }

  void _previewImage(MediaFileItem item) {
    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        backgroundColor: Colors.black87,
        insetPadding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.all(12.0),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Text(
                      item.originalFilename,
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close, color: Colors.white),
                    onPressed: () => Navigator.of(ctx).pop(),
                  ),
                ],
              ),
            ),
            Container(
              constraints: const BoxConstraints(maxHeight: 400),
              child: item.driveThumbnailLink != null
                  ? Image.network(
                      item.driveThumbnailLink!,
                      fit: BoxFit.contain,
                      errorBuilder: (_, _, _) => const Center(
                        child: Icon(Icons.broken_image, color: Colors.white54, size: 64),
                      ),
                    )
                  : const Center(
                      child: Icon(Icons.photo, color: Colors.white54, size: 96),
                    ),
            ),
            if (item.hasGps && item.mapsUrl != null)
              Padding(
                padding: const EdgeInsets.all(12.0),
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.teal),
                  icon: const Icon(Icons.map_outlined, size: 16),
                  label: Text('Open Location (${item.gpsLatitude?.toStringAsFixed(4)}, ${item.gpsLongitude?.toStringAsFixed(4)})'),
                  onPressed: () => _openUrl(item.mapsUrl!),
                ),
              ),
            if (item.isDrive && item.driveWebViewLink != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12.0, vertical: 6.0),
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
                  icon: const Icon(Icons.open_in_new, size: 16),
                  label: const Text('Open in Google Drive'),
                  onPressed: () => _openUrl(item.driveWebViewLink!),
                ),
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final df = DateFormat('dd MMM yyyy');
    final formattedDate = _currentFolder.eventDate != null ? df.format(_currentFolder.eventDate!) : 'No date set';

    return Scaffold(
      appBar: AppBar(
        title: Text(_currentFolder.name),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh),
            onPressed: _loadData,
          ),
        ],
      ),
      body: Column(
        children: [
          if (_isLoading) const LinearProgressIndicator(),
          if (_errorMessage != null)
            Container(
              padding: const EdgeInsets.all(8),
              color: AppConstants.dangerRed.withValues(alpha: 0.1),
              child: Row(
                children: [
                  const Icon(Icons.error_outline, size: 16, color: AppConstants.dangerRed),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _errorMessage!,
                      style: const TextStyle(fontSize: 12, color: AppConstants.dangerRed),
                    ),
                  ),
                ],
              ),
            ),

          // Header Card
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: CustomCard(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.event_outlined, size: 18, color: Colors.indigo),
                        const SizedBox(width: 8),
                        Text(
                          formattedDate,
                          style: const TextStyle(fontSize: 13, color: AppConstants.textSecondary, fontWeight: FontWeight.w500),
                        ),
                        const Spacer(),
                        _buildStorageSourceBadge(_currentFolder.storageSource),
                      ],
                    ),
                    if (_currentFolder.description != null && _currentFolder.description!.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Text(
                        _currentFolder.description!,
                        style: const TextStyle(fontSize: 13, color: AppConstants.darkGray),
                      ),
                    ],
                    const Divider(height: 24),
                    // Google Drive Toolbar
                    _buildDriveToolbar(),
                  ],
                ),
              ),
            ),
          ),

          // Category TabBar
          TabBar(
            controller: _tabController,
            isScrollable: true,
            labelColor: AppConstants.pureBlack,
            indicatorColor: AppConstants.pureBlack,
            tabs: _categories.map((c) {
              final count = _getFilesForCategory(c['key'] as String).length;
              return Tab(
                child: Row(
                  children: [
                    Icon(c['icon'] as IconData, size: 16, color: c['color'] as Color),
                    const SizedBox(width: 6),
                    Text('${c['label']} ($count)'),
                  ],
                ),
              );
            }).toList(),
          ),

          // Media Files TabBarView
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: _categories.map((c) {
                final files = _getFilesForCategory(c['key'] as String);
                return _buildCategoryFilesView(c['key'] as String, files);
              }).toList(),
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppConstants.pureBlack,
        icon: const Icon(Icons.add_photo_alternate, color: Colors.white),
        label: const Text('Upload Media', style: TextStyle(color: Colors.white)),
        onPressed: _showUploadDialog,
      ),
    );
  }

  Widget _buildStorageSourceBadge(String source) {
    Color bg;
    Color fg;
    String label;
    IconData icon;

    switch (source) {
      case 'google_drive':
        bg = Colors.green.withValues(alpha: 0.15);
        fg = Colors.green.shade800;
        label = 'Google Drive';
        icon = Icons.add_to_drive;
        break;
      case 'both':
        bg = Colors.purple.withValues(alpha: 0.15);
        fg = Colors.purple.shade800;
        label = 'Firebase & Drive';
        icon = Icons.cloud_done;
        break;
      case 'firebase':
      case 'local':
        bg = Colors.blue.withValues(alpha: 0.15);
        fg = Colors.blue.shade800;
        label = 'Firebase Storage';
        icon = Icons.cloud_queue;
        break;
      default:
        bg = Colors.grey.withValues(alpha: 0.15);
        fg = Colors.grey.shade700;
        label = 'Empty Folder';
        icon = Icons.folder_open;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(6)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: fg),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(fontSize: 11, color: fg, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  Widget _buildDriveToolbar() {
    if (_currentFolder.hasDriveLinked) {
      return Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: Colors.green.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.green.withValues(alpha: 0.3)),
        ),
        child: Row(
          children: [
            const Icon(Icons.folder_shared, color: Colors.green, size: 20),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Linked Google Drive Folder', style: TextStyle(fontSize: 10, color: Colors.green, fontWeight: FontWeight.bold)),
                  Text(
                    _currentFolder.linkedDriveFolderName ?? 'Drive Folder',
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            IconButton(
              tooltip: 'Browse Files in Drive',
              icon: const Icon(Icons.search, size: 20, color: Colors.green),
              onPressed: _showBrowseDriveDialog,
            ),
            if (_currentFolder.driveWebViewLink != null)
              IconButton(
                tooltip: 'Open in Google Drive',
                icon: const Icon(Icons.open_in_new, size: 20, color: Colors.green),
                onPressed: () => _openUrl(_currentFolder.driveWebViewLink!),
              ),
            IconButton(
              tooltip: 'Unlink Drive Folder',
              icon: const Icon(Icons.link_off, size: 20, color: AppConstants.dangerRed),
              onPressed: _unlinkDriveFolder,
            ),
          ],
        ),
      );
    }

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        const Text(
          'Google Drive not connected to this event',
          style: TextStyle(fontSize: 12, color: AppConstants.textSecondary),
        ),
        OutlinedButton.icon(
          style: OutlinedButton.styleFrom(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            foregroundColor: Colors.green.shade800,
            side: BorderSide(color: Colors.green.shade300),
          ),
          icon: const Icon(Icons.add_to_drive, size: 16),
          label: const Text('Connect Drive Folder', style: TextStyle(fontSize: 12)),
          onPressed: _showLinkDriveDialog,
        ),
      ],
    );
  }

  Widget _buildCategoryFilesView(String categoryKey, List<MediaFileItem> files) {
    if (files.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.folder_open, size: 48, color: Colors.grey.shade400),
            const SizedBox(height: 12),
            const Text(
              'No media files uploaded yet.',
              style: TextStyle(fontSize: 14, color: AppConstants.textSecondary, fontWeight: FontWeight.w500),
            ),
            const SizedBox(height: 6),
            const Text(
              'Use the "Upload Media" button below to add files.',
              style: TextStyle(fontSize: 12, color: AppConstants.textSecondary),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16.0),
      itemCount: files.length,
      itemBuilder: (context, index) {
        final item = files[index];
        return _buildMediaItemCard(item);
      },
    );
  }

  Widget _buildMediaItemCard(MediaFileItem item) {
    IconData typeIcon = Icons.insert_drive_file;
    Color typeColor = Colors.grey;

    if (item.category == 'geotagged_photos') {
      typeIcon = Icons.location_on;
      typeColor = Colors.teal;
    } else if (item.category == 'photos') {
      typeIcon = Icons.photo;
      typeColor = Colors.blue;
    } else if (item.category == 'videos') {
      typeIcon = Icons.videocam;
      typeColor = Colors.purple;
    } else if (item.category == 'posters') {
      typeIcon = Icons.palette;
      typeColor = Colors.deepOrange;
    }

    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: const BorderSide(color: AppConstants.borderLight),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                GestureDetector(
                  onTap: () => _previewImage(item),
                  child: Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: typeColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(typeIcon, color: typeColor, size: 24),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item.originalFilename,
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 3),
                      Row(
                        children: [
                          Text(
                            item.fileSizeFormatted,
                            style: const TextStyle(fontSize: 11, color: AppConstants.textSecondary),
                          ),
                          const SizedBox(width: 8),
                          // Provider Badge
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: item.isDrive ? Colors.green.withValues(alpha: 0.12) : Colors.blue.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(item.isDrive ? Icons.add_to_drive : Icons.cloud_queue, size: 10, color: item.isDrive ? Colors.green.shade800 : Colors.blue.shade800),
                                const SizedBox(width: 3),
                                Text(
                                  item.isDrive ? 'Google Drive' : 'Firebase',
                                  style: TextStyle(
                                    fontSize: 9,
                                    fontWeight: FontWeight.bold,
                                    color: item.isDrive ? Colors.green.shade800 : Colors.blue.shade800,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                // Actions Menu
                PopupMenuButton<String>(
                  icon: const Icon(Icons.more_vert, size: 18),
                  onSelected: (val) {
                    if (val == 'preview') {
                      _previewImage(item);
                    } else if (val == 'maps' && item.mapsUrl != null) {
                      _openUrl(item.mapsUrl!);
                    } else if (val == 'drive' && item.driveWebViewLink != null) {
                      _openUrl(item.driveWebViewLink!);
                    } else if (val == 'delete') {
                      _deleteFile(item);
                    }
                  },
                  itemBuilder: (ctx) => [
                    const PopupMenuItem(value: 'preview', child: Text('Preview')),
                    if (item.hasGps && item.mapsUrl != null)
                      const PopupMenuItem(value: 'maps', child: Text('Open Location on Maps')),
                    if (item.isDrive && item.driveWebViewLink != null)
                      const PopupMenuItem(value: 'drive', child: Text('Open in Google Drive')),
                    PopupMenuItem(
                      value: 'delete',
                      child: Text(
                        item.isDrive ? 'Unlink Reference' : 'Delete File',
                        style: const TextStyle(color: AppConstants.dangerRed),
                      ),
                    ),
                  ],
                ),
              ],
            ),

            // Geotag details bar
            const SizedBox(height: 8),
            if (item.hasGps) ...[
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.teal.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.location_on, size: 14, color: Colors.teal),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        'Geotagged: ${item.gpsLatitude?.toStringAsFixed(4)}, ${item.gpsLongitude?.toStringAsFixed(4)}'
                        '${item.capturedAt != null ? ' • ${DateFormat('dd MMM, hh:mm a').format(item.capturedAt!)}' : ''}',
                        style: const TextStyle(fontSize: 11, color: Colors.teal, fontWeight: FontWeight.w600),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    InkWell(
                      onTap: () {
                        if (item.mapsUrl != null) _openUrl(item.mapsUrl!);
                      },
                      child: const Row(
                        children: [
                          Text('Open Map', style: TextStyle(fontSize: 11, color: Colors.teal, fontWeight: FontWeight.bold)),
                          Icon(Icons.arrow_forward_ios, size: 10, color: Colors.teal),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ] else ...[
              const Padding(
                padding: EdgeInsets.only(left: 4),
                child: Text(
                  'No GPS metadata',
                  style: TextStyle(fontSize: 10, color: AppConstants.textSecondary),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

// -----------------------------------------------------------------------------
// Drive Folder Selection Dialog
// -----------------------------------------------------------------------------
class _SelectDriveFolderDialog extends StatefulWidget {
  final MediaService mediaService;
  final ValueChanged<GoogleDriveFolderItem> onFolderSelected;

  const _SelectDriveFolderDialog({
    required this.mediaService,
    required this.onFolderSelected,
  });

  @override
  State<_SelectDriveFolderDialog> createState() => _SelectDriveFolderDialogState();
}

class _SelectDriveFolderDialogState extends State<_SelectDriveFolderDialog> {
  bool _isLoading = true;
  String? _error;
  List<GoogleDriveFolderItem> _folders = [];
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _fetchFolders();
  }

  Future<void> _fetchFolders({String? query}) async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final list = await widget.mediaService.listDriveFolders(query: query);
      if (mounted) {
        setState(() {
          _folders = list;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
          _error = e.toString();
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Select Google Drive Folder'),
      content: SizedBox(
        width: double.maxFinite,
        height: 380,
        child: Column(
          children: [
            TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: 'Search Drive folders...',
                prefixIcon: const Icon(Icons.search, size: 18),
                suffixIcon: IconButton(
                  icon: const Icon(Icons.arrow_forward, size: 18),
                  onPressed: () => _fetchFolders(query: _searchController.text),
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
              ),
              onSubmitted: (q) => _fetchFolders(query: q),
            ),
            const SizedBox(height: 12),
            if (_isLoading)
              const Expanded(child: Center(child: CircularProgressIndicator()))
            else if (_error != null)
              Expanded(child: Center(child: Text('Error: $_error', style: const TextStyle(color: AppConstants.dangerRed))))
            else if (_folders.isEmpty)
              const Expanded(child: Center(child: Text('No Google Drive folders found.')))
            else
              Expanded(
                child: ListView.separated(
                  itemCount: _folders.length,
                  separatorBuilder: (_, _) => const Divider(height: 1),
                  itemBuilder: (ctx, i) {
                    final f = _folders[i];
                    return ListTile(
                      leading: const Icon(Icons.folder, color: Colors.green),
                      title: Text(f.name, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
                      trailing: const Icon(Icons.chevron_right, size: 18),
                      onTap: () => widget.onFolderSelected(f),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
      ],
    );
  }
}

// -----------------------------------------------------------------------------
// Browse Drive Files Bottom Sheet (Link to Event)
// -----------------------------------------------------------------------------
class _BrowseDriveFilesSheet extends StatefulWidget {
  final MediaEventFolder folder;
  final MediaService mediaService;
  final VoidCallback onFileLinked;

  const _BrowseDriveFilesSheet({
    required this.folder,
    required this.mediaService,
    required this.onFileLinked,
  });

  @override
  State<_BrowseDriveFilesSheet> createState() => _BrowseDriveFilesSheetState();
}

class _BrowseDriveFilesSheetState extends State<_BrowseDriveFilesSheet> {
  bool _isLoading = true;
  String? _error;
  List<GoogleDriveFileItem> _driveFiles = [];
  final String _selectedCategory = '';

  @override
  void initState() {
    super.initState();
    _fetchDriveFiles();
  }

  Future<void> _fetchDriveFiles() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final files = await widget.mediaService.listLinkedDriveFiles(
        widget.folder.id,
        category: _selectedCategory.isNotEmpty ? _selectedCategory : null,
      );
      if (mounted) {
        setState(() {
          _driveFiles = files;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
          _error = e.toString();
        });
      }
    }
  }

  Future<void> _linkFile(GoogleDriveFileItem file) async {
    try {
      await widget.mediaService.linkDriveFile(
        folderId: widget.folder.id,
        driveFileId: file.id,
        category: file.category,
      );
      widget.onFileLinked();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Linked '${file.name}' to event.")),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to link file: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: MediaQuery.of(context).size.height * 0.75,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Browse Drive: ${widget.folder.linkedDriveFolderName}',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
              ),
              IconButton(
                icon: const Icon(Icons.close),
                onPressed: () => Navigator.of(context).pop(),
              ),
            ],
          ),
          const SizedBox(height: 8),
          const Text(
            'Files already uploaded to Google Drive. Tap "Link" to add them to this event workspace without downloading or duplicating bytes.',
            style: TextStyle(fontSize: 12, color: AppConstants.textSecondary),
          ),
          const SizedBox(height: 12),
          if (_isLoading)
            const Expanded(child: Center(child: CircularProgressIndicator()))
          else if (_error != null)
            Expanded(child: Center(child: Text('Error: $_error', style: const TextStyle(color: AppConstants.dangerRed))))
          else if (_driveFiles.isEmpty)
            const Expanded(child: Center(child: Text('No files found in linked Drive folder.')))
          else
            Expanded(
              child: ListView.separated(
                itemCount: _driveFiles.length,
                separatorBuilder: (_, _) => const Divider(height: 1),
                itemBuilder: (ctx, i) {
                  final f = _driveFiles[i];
                  return ListTile(
                    leading: const Icon(Icons.insert_drive_file, color: Colors.green),
                    title: Text(f.name, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                    subtitle: Text(
                      'Category: ${f.category}'
                      '${f.fileSize != null ? ' • ${(f.fileSize! / (1024 * 1024)).toStringAsFixed(1)} MB' : ''}',
                      style: const TextStyle(fontSize: 11),
                    ),
                    trailing: OutlinedButton(
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        foregroundColor: Colors.green.shade800,
                      ),
                      child: const Text('Link', style: TextStyle(fontSize: 12)),
                      onPressed: () => _linkFile(f),
                    ),
                  );
                },
              ),
            ),
        ],
      ),
    );
  }
}
