import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import '../config/constants.dart';
import '../models/documentation.dart';
import '../services/auth_service.dart';
import '../services/documentation_service.dart';
import '../services/sync_service.dart';
import '../utils/download_helper.dart';
import '../widgets/custom_card.dart';
import '../widgets/primary_button.dart';
import '../widgets/secondary_button.dart';
import '../widgets/state_views.dart';
import 'activity_report_editor_screen.dart';
import 'community_screen.dart';
import '../services/community_service.dart';

class DocumentationPortalScreen extends StatefulWidget {
  final AuthService authService;
  final SyncService syncService;
  final VoidCallback onLogout;
  final VoidCallback? onSwitchToAdmin;

  const DocumentationPortalScreen({
    super.key,
    required this.authService,
    required this.syncService,
    required this.onLogout,
    this.onSwitchToAdmin,
  });

  @override
  State<DocumentationPortalScreen> createState() => _DocumentationPortalScreenState();
}

class _DocumentationPortalScreenState extends State<DocumentationPortalScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  late DocumentationService _docService;

  bool _isLoadingFolders = true;
  bool _isLoadingReports = true;
  String? _folderError;
  String? _reportError;

  List<EventFolder> _folders = [];
  List<ActivityReport> _reports = [];

  EventFolder? _selectedFolder;
  bool _isLoadingFolderDocs = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _docService = DocumentationService(apiClient: widget.syncService.apiClient);
    _loadAll();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadAll() async {
    _loadFolders();
    _loadReports();
  }

  Future<void> _loadFolders() async {
    setState(() {
      _isLoadingFolders = true;
      _folderError = null;
    });
    try {
      final folders = await _docService.fetchFolders();
      if (mounted) {
        setState(() {
          _folders = folders;
          _isLoadingFolders = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _folderError = 'Failed to load event folders: $e';
          _isLoadingFolders = false;
        });
      }
    }
  }

  Future<void> _loadReports() async {
    setState(() {
      _isLoadingReports = true;
      _reportError = null;
    });
    try {
      final reports = await _docService.fetchReports();
      if (mounted) {
        setState(() {
          _reports = reports;
          _isLoadingReports = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _reportError = 'Failed to load activity reports: $e';
          _isLoadingReports = false;
        });
      }
    }
  }

  Future<void> _showCreateFolderDialog() async {
    final nameCtrl = TextEditingController();
    final descCtrl = TextEditingController();

    await showDialog(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          title: const Text('Create Event Folder'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nameCtrl,
                autofocus: true,
                decoration: const InputDecoration(
                  labelText: 'Folder Name *',
                  hintText: 'e.g. Quantum AI Workshop 2026',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: descCtrl,
                maxLines: 2,
                decoration: const InputDecoration(
                  labelText: 'Description (Optional)',
                  hintText: 'e.g. Master documents, photos, and attendance records',
                  border: OutlineInputBorder(),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () async {
                final name = nameCtrl.text.trim();
                if (name.isEmpty) return;
                Navigator.pop(ctx);
                try {
                  await _docService.createFolder(
                    name: name,
                    description: descCtrl.text.trim(),
                  );
                  _loadFolders();
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text('Created folder "$name" successfully.'),
                        backgroundColor: AppConstants.successGreen,
                      ),
                    );
                  }
                } catch (e) {
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Failed to create folder: $e'), backgroundColor: AppConstants.dangerRed),
                    );
                  }
                }
              },
              child: const Text('Create Folder'),
            ),
          ],
        );
      },
    );
  }

  Future<void> _openFolder(EventFolder folder) async {
    setState(() {
      _selectedFolder = folder;
      _isLoadingFolderDocs = true;
    });

    try {
      final fullFolder = await _docService.getFolder(folder.id);
      if (mounted) {
        setState(() {
          _selectedFolder = fullFolder;
          _isLoadingFolderDocs = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoadingFolderDocs = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to load folder details: $e')),
        );
      }
    }
  }

  Future<void> _uploadDocumentToSelectedFolder() async {
    if (_selectedFolder == null) return;

    final file = await FilePicker.pickFile();
    if (file == null) return;

    final bytes = await file.readAsBytes();

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Uploading "${file.name}" to Cloud Storage...')),
      );
    }

    try {
      await _docService.uploadDocument(
        folderId: _selectedFolder!.id,
        fileBytes: bytes,
        filename: file.name,
      );
      // Reload folder and folder list
      await _openFolder(_selectedFolder!);
      _loadFolders();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Uploaded "${file.name}" successfully!'),
            backgroundColor: AppConstants.successGreen,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload failed: $e'), backgroundColor: AppConstants.dangerRed),
        );
      }
    }
  }

  Future<void> _downloadDoc(FolderDocument doc) async {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Downloading "${doc.fileName}"...')),
    );
    try {
      final bytes = await _docService.downloadDocument(doc.id);
      final msg = await DownloadHelper.downloadFile(bytes, doc.fileName);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(msg),
            backgroundColor: AppConstants.successGreen,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Download failed: $e'), backgroundColor: AppConstants.dangerRed),
        );
      }
    }
  }

  Future<void> _deleteDoc(FolderDocument doc) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Document'),
        content: Text('Are you sure you want to delete "${doc.fileName}" from cloud storage?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppConstants.dangerRed),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    try {
      await _docService.deleteDocument(doc.id);
      if (_selectedFolder != null) {
        await _openFolder(_selectedFolder!);
      }
      _loadFolders();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Document deleted.')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete document: $e')),
        );
      }
    }
  }

  Future<void> _deleteFolder(EventFolder folder) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Folder'),
        content: Text(
          'Are you sure you want to delete "${folder.name}" and all of its ${folder.documentCount} uploaded documents?',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppConstants.dangerRed),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete Folder', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    try {
      await _docService.deleteFolder(folder.id);
      if (_selectedFolder?.id == folder.id) {
        setState(() => _selectedFolder = null);
      }
      _loadFolders();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Folder "${folder.name}" deleted.')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete folder: $e')),
        );
      }
    }
  }

  Future<void> _createNewReport() async {
    final titleCtrl = TextEditingController(text: 'Annual Activity Report');

    final title = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('New Activity Report'),
        content: TextField(
          controller: titleCtrl,
          autofocus: true,
          decoration: const InputDecoration(
            labelText: 'Activity Report Title *',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, titleCtrl.text.trim()),
            child: const Text('Create & Open Editor'),
          ),
        ],
      ),
    );

    if (title == null || title.isEmpty) return;

    try {
      final rep = await _docService.createReport(title: title);
      _loadReports();
      if (mounted) {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (ctx) => ActivityReportEditorScreen(
              reportId: rep.id,
              docService: _docService,
              authService: widget.authService,
            ),
          ),
        ).then((_) => _loadReports());
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to create report: $e')),
        );
      }
    }
  }

  Future<void> _deleteReport(ActivityReport report) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Report Draft'),
        content: Text('Are you sure you want to delete "${report.title}"?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppConstants.dangerRed),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    try {
      await _docService.deleteReport(report.id);
      _loadReports();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Report deleted successfully.')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete report: $e')),
        );
      }
    }
  }

  Future<void> _openAiCopilotModal() async {
    final promptCtrl = TextEditingController();
    String selectedAction = 'draft';
    String selectedProvider = 'grok';
    String? generatedResult;
    String? providerUsed;
    bool isGenerating = false;
    String? errorText;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            final bottomInset = MediaQuery.of(context).viewInsets.bottom;
            return Container(
              height: MediaQuery.of(context).size.height * 0.85,
              padding: EdgeInsets.only(bottom: bottomInset),
              decoration: const BoxDecoration(
                color: AppConstants.pureWhite,
                borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
              ),
              child: Column(
                children: [
                  // Header
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                    decoration: const BoxDecoration(
                      border: Border(bottom: BorderSide(color: AppConstants.borderLight)),
                    ),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: Colors.purple.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Icon(Icons.auto_awesome, color: Colors.purple, size: 20),
                        ),
                        const SizedBox(width: 12),
                        const Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Documentation AI Copilot',
                                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                              ),
                              Text(
                                'Assists with institutional activity reports & academic content',
                                style: TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                              ),
                            ],
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.close),
                          onPressed: () => Navigator.pop(ctx),
                        ),
                      ],
                    ),
                  ),

                  // Body
                  Expanded(
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (errorText != null) ...[
                            Container(
                              padding: const EdgeInsets.all(10),
                              decoration: BoxDecoration(
                                color: Colors.red.shade50,
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(color: Colors.red.shade200),
                              ),
                              child: Text(errorText!, style: TextStyle(color: Colors.red.shade800, fontSize: 12)),
                            ),
                            const SizedBox(height: 14),
                          ],

                          // Action selector chips
                          const Text('Copilot Mode', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                          const SizedBox(height: 8),
                          Wrap(
                            spacing: 8,
                            runSpacing: 6,
                            children: [
                              ChoiceChip(
                                label: const Text('Draft Section'),
                                selected: selectedAction == 'draft',
                                selectedColor: Colors.purple.shade700,
                                labelStyle: TextStyle(color: selectedAction == 'draft' ? Colors.white : Colors.black, fontSize: 12),
                                onSelected: (sel) => setModalState(() => selectedAction = 'draft'),
                              ),
                              ChoiceChip(
                                label: const Text('Summarize Event'),
                                selected: selectedAction == 'summarize',
                                selectedColor: Colors.purple.shade700,
                                labelStyle: TextStyle(color: selectedAction == 'summarize' ? Colors.white : Colors.black, fontSize: 12),
                                onSelected: (sel) => setModalState(() => selectedAction = 'summarize'),
                              ),
                              ChoiceChip(
                                label: const Text('Formal Academic Polish'),
                                selected: selectedAction == 'formalize',
                                selectedColor: Colors.purple.shade700,
                                labelStyle: TextStyle(color: selectedAction == 'formalize' ? Colors.white : Colors.black, fontSize: 12),
                                onSelected: (sel) => setModalState(() => selectedAction = 'formalize'),
                              ),
                            ],
                          ),
                          const SizedBox(height: 16),

                          // AI Engine toggle
                          const Text('AI Engine', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              Expanded(
                                child: ChoiceChip(
                                  label: const Row(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Icon(Icons.bolt, size: 14),
                                      SizedBox(width: 4),
                                      Text('Groq LPU (Fast)'),
                                    ],
                                  ),
                                  selected: selectedProvider == 'grok',
                                  selectedColor: Colors.deepOrange.shade600,
                                  labelStyle: TextStyle(color: selectedProvider == 'grok' ? Colors.white : Colors.black, fontSize: 11),
                                  onSelected: (sel) => setModalState(() => selectedProvider = 'grok'),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: ChoiceChip(
                                  label: const Row(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Icon(Icons.auto_awesome, size: 14),
                                      SizedBox(width: 4),
                                      Text('Gemini 3.5 Flash'),
                                    ],
                                  ),
                                  selected: selectedProvider == 'gemini',
                                  selectedColor: Colors.blue.shade700,
                                  labelStyle: TextStyle(color: selectedProvider == 'gemini' ? Colors.white : Colors.black, fontSize: 11),
                                  onSelected: (sel) => setModalState(() => selectedProvider = 'gemini'),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 16),

                          // Instruction
                          const Text('Event Details / Prompt *', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                          const SizedBox(height: 6),
                          TextField(
                            controller: promptCtrl,
                            maxLines: 4,
                            decoration: InputDecoration(
                              hintText: 'e.g. Workshop on Embedded IoT Architecture organized by CUestIC on 25 Nov with 45 participants and hands-on sensor kit demos...',
                              hintStyle: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                              contentPadding: const EdgeInsets.all(12),
                            ),
                          ),
                          const SizedBox(height: 14),

                          // Run Button
                          PrimaryButton(
                            key: const Key('btn_run_doc_copilot'),
                            label: isGenerating ? 'AI Copilot is generating...' : 'Ask Documentation Copilot',
                            icon: Icons.auto_awesome,
                            isLoading: isGenerating,
                            onPressed: isGenerating
                                ? null
                                : () async {
                                    final text = promptCtrl.text.trim();
                                    if (text.isEmpty) {
                                      setModalState(() => errorText = 'Please enter event details or a prompt.');
                                      return;
                                    }
                                    setModalState(() {
                                      isGenerating = true;
                                      errorText = null;
                                    });

                                    try {
                                      final res = await _docService.aiAssist(
                                        fieldKey: 'general_documentation',
                                        fieldLabel: 'Activity Documentation',
                                        instruction: text,
                                        action: selectedAction,
                                        provider: selectedProvider,
                                      );
                                      setModalState(() {
                                        generatedResult = res['generated_text']?.toString();
                                        providerUsed = res['provider']?.toString();
                                        isGenerating = false;
                                      });
                                    } catch (e) {
                                      setModalState(() {
                                        isGenerating = false;
                                        errorText = e.toString().replaceFirst('Exception: ', '');
                                      });
                                    }
                                  },
                          ),

                          // Output
                          if (generatedResult != null) ...[
                            const SizedBox(height: 20),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                const Text('Copilot Output', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
                                if (providerUsed != null)
                                  Chip(
                                    label: Text(providerUsed!.toUpperCase(), style: const TextStyle(fontSize: 9, fontWeight: FontWeight.bold)),
                                    visualDensity: VisualDensity.compact,
                                    padding: EdgeInsets.zero,
                                  ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Container(
                              padding: const EdgeInsets.all(14),
                              decoration: BoxDecoration(
                                color: AppConstants.backgroundLight,
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(color: AppConstants.borderLight),
                              ),
                              child: SelectableText(
                                generatedResult!,
                                style: const TextStyle(fontSize: 13, height: 1.5),
                              ),
                            ),
                            const SizedBox(height: 12),
                            Row(
                              children: [
                                Expanded(
                                  child: OutlinedButton.icon(
                                    icon: const Icon(Icons.copy, size: 16),
                                    label: const Text('Copy Text'),
                                    onPressed: () {
                                      Clipboard.setData(ClipboardData(text: generatedResult!));
                                      ScaffoldMessenger.of(context).showSnackBar(
                                        const SnackBar(content: Text('Copied output to clipboard!')),
                                      );
                                    },
                                  ),
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: ElevatedButton.icon(
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: Colors.purple.shade700,
                                      foregroundColor: Colors.white,
                                    ),
                                    icon: const Icon(Icons.note_add, size: 16),
                                    label: const Text('Create Report'),
                                    onPressed: () async {
                                      Navigator.pop(ctx);
                                      try {
                                        final rep = await _docService.createReport(
                                          title: 'Activity Report from Copilot',
                                          description: generatedResult!,
                                        );
                                        _loadReports();
                                        if (mounted) {
                                          Navigator.push(
                                            context,
                                            MaterialPageRoute(
                                              builder: (c) => ActivityReportEditorScreen(
                                                reportId: rep.id,
                                                docService: _docService,
                                                authService: widget.authService,
                                              ),
                                            ),
                                          );
                                        }
                                      } catch (e) {
                                        if (mounted) {
                                          ScaffoldMessenger.of(context).showSnackBar(
                                            SnackBar(content: Text('Error creating report: $e')),
                                          );
                                        }
                                      }
                                    },
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  // ---------------------------------------------------------------------------
  // Build Method
  // ---------------------------------------------------------------------------
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(
        key: const Key('fab_doc_ai_copilot'),
        backgroundColor: Colors.purple.shade700,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.auto_awesome, size: 18),
        label: const Text('AI Copilot', style: TextStyle(fontWeight: FontWeight.bold)),
        onPressed: _openAiCopilotModal,
      ),
      appBar: AppBar(
        title: Row(
          children: [
            const Icon(Icons.description, size: 22),
            const SizedBox(width: 8),
            const Text('Documentation Portal'),
            const SizedBox(width: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: AppConstants.pureBlack,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                widget.authService.displayName,
                style: const TextStyle(
                  fontSize: 11,
                  color: AppConstants.pureWhite,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            key: const Key('btn_open_community'),
            icon: const Icon(Icons.forum_outlined, size: 20),
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
            key: const Key('btn_doc_portal_ai_copilot'),
            icon: const Icon(Icons.auto_awesome, color: Colors.purple, size: 22),
            tooltip: 'Documentation AI Copilot',
            onPressed: _openAiCopilotModal,
          ),
          if (widget.authService.isAdmin && widget.onSwitchToAdmin != null)
            TextButton.icon(
              icon: const Icon(Icons.admin_panel_settings, size: 18),
              label: const Text('Admin Portal'),
              onPressed: widget.onSwitchToAdmin,
            ),
          IconButton(
            tooltip: 'Logout',
            icon: const Icon(Icons.logout),
            onPressed: () async {
              final confirm = await showDialog<bool>(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Text('Logout'),
                  content: const Text('Are you sure you want to log out of your documentation account?'),
                  actions: [
                    TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(backgroundColor: AppConstants.pureBlack),
                      onPressed: () => Navigator.pop(ctx, true),
                      child: const Text('Logout', style: TextStyle(color: Colors.white)),
                    ),
                  ],
                ),
              );
              if (confirm == true) {
                widget.onLogout();
              }
            },
          ),
          const SizedBox(width: 8),
        ],
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppConstants.pureBlack,
          unselectedLabelColor: AppConstants.textSecondary,
          indicatorColor: AppConstants.pureBlack,
          indicatorWeight: 2.5,
          tabs: const [
            Tab(icon: Icon(Icons.folder_shared_outlined), text: 'Event Documents'),
            Tab(icon: Icon(Icons.auto_stories_outlined), text: 'AI Report Generator'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildEventDocumentsTab(),
          _buildAiReportGeneratorTab(),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 1: Event Documents
  // ---------------------------------------------------------------------------
  Widget _buildEventDocumentsTab() {
    if (_selectedFolder != null) {
      return _buildFolderDetailView();
    }

    if (_isLoadingFolders) {
      return const LoadingView(message: 'Loading event folders...');
    }

    if (_folderError != null) {
      return ErrorView(
        message: _folderError!,
        onRetry: _loadFolders,
      );
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Documentation Workspace',
                      style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, letterSpacing: -0.3),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Organize event document archives and attachments with Cloud Storage.',
                      style: TextStyle(fontSize: 13, color: AppConstants.textSecondary),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
              PrimaryButton(
                width: 220,
                height: 42,
                label: 'Create Event Folder',
                icon: Icons.create_new_folder_outlined,
                onPressed: _showCreateFolderDialog,
              ),
            ],
          ),
          const SizedBox(height: 24),
          if (_folders.isEmpty)
            Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 48.0),
                child: EmptyView(
                  message: 'No event folders found. Create your first folder to upload and organize documents.',
                  actionLabel: 'Create Event Folder',
                  onAction: _showCreateFolderDialog,
                ),
              ),
            )
          else
            LayoutBuilder(
              builder: (context, constraints) {
                final isWide = constraints.maxWidth >= 700;
                return GridView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: isWide ? 3 : 1,
                    crossAxisSpacing: 16,
                    mainAxisSpacing: 16,
                    mainAxisExtent: 180,
                  ),
                  itemCount: _folders.length,
                  itemBuilder: (context, index) {
                    final folder = _folders[index];
                    return CustomCard(
                      onTap: () => _openFolder(folder),
                      child: Padding(
                        padding: const EdgeInsets.all(16.0),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(8),
                                  decoration: BoxDecoration(
                                    color: AppConstants.pureBlack.withValues(alpha: 0.05),
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                  child: const Icon(Icons.folder, color: AppConstants.pureBlack, size: 24),
                                ),
                                const Spacer(),
                                IconButton(
                                  icon: const Icon(Icons.delete_outline, color: AppConstants.dangerRed, size: 18),
                                  tooltip: 'Delete Folder',
                                  onPressed: () => _deleteFolder(folder),
                                ),
                              ],
                            ),
                            const Spacer(),
                            Text(
                              folder.name,
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            if (folder.description != null && folder.description!.isNotEmpty) ...[
                              const SizedBox(height: 4),
                              Text(
                                folder.description!,
                                style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                            const SizedBox(height: 8),
                            Row(
                              children: [
                                Icon(Icons.file_present_outlined, size: 14, color: AppConstants.textSecondary),
                                const SizedBox(width: 4),
                                Text(
                                  '${folder.documentCount} file${folder.documentCount == 1 ? "" : "s"}',
                                  style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                );
              },
            ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Folder Detail Sub-View
  // ---------------------------------------------------------------------------
  Widget _buildFolderDetailView() {
    final folder = _selectedFolder!;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              IconButton(
                icon: const Icon(Icons.arrow_back),
                onPressed: () => setState(() => _selectedFolder = null),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      folder.name,
                      style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                    ),
                    if (folder.description != null)
                      Text(folder.description!, style: const TextStyle(color: AppConstants.textSecondary, fontSize: 13)),
                  ],
                ),
              ),
              PrimaryButton(
                width: 170,
                height: 40,
                label: 'Upload Document',
                icon: Icons.cloud_upload_outlined,
                onPressed: _uploadDocumentToSelectedFolder,
              ),
            ],
          ),
          const SizedBox(height: 20),
          const Divider(),
          const SizedBox(height: 16),
          if (_isLoadingFolderDocs)
            const Center(child: Padding(padding: EdgeInsets.all(32.0), child: CircularProgressIndicator()))
          else if (folder.documents.isEmpty)
            Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 48.0),
                child: EmptyView(
                  message: 'No files uploaded to this folder yet. Upload documents, reports, or annexures.',
                  actionLabel: 'Upload Document',
                  onAction: _uploadDocumentToSelectedFolder,
                ),
              ),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: folder.documents.length,
              separatorBuilder: (context, _) => const SizedBox(height: 8),
              itemBuilder: (context, index) {
                final doc = folder.documents[index];
                IconData iconData = Icons.insert_drive_file_outlined;
                if (doc.fileName.endsWith('.docx') || doc.fileName.endsWith('.doc')) {
                  iconData = Icons.description;
                } else if (doc.fileName.endsWith('.pdf')) {
                  iconData = Icons.picture_as_pdf;
                } else if (doc.fileName.endsWith('.jpg') || doc.fileName.endsWith('.png') || doc.fileName.endsWith('.jpeg')) {
                  iconData = Icons.image;
                }

                return Card(
                  child: ListTile(
                    leading: Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: AppConstants.pureBlack.withValues(alpha: 0.05),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Icon(iconData, color: AppConstants.pureBlack, size: 24),
                    ),
                    title: Text(doc.fileName, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                    subtitle: Text(
                      '${doc.formattedSize} • Uploaded by ${doc.uploadedByName}',
                      style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                    ),
                    trailing: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        IconButton(
                          tooltip: 'Download',
                          icon: const Icon(Icons.download_outlined, color: AppConstants.pureBlack),
                          onPressed: () => _downloadDoc(doc),
                        ),
                        IconButton(
                          tooltip: 'Delete',
                          icon: const Icon(Icons.delete_outline, color: AppConstants.dangerRed),
                          onPressed: () => _deleteDoc(doc),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 2: AI Report Generator
  // ---------------------------------------------------------------------------
  Widget _buildAiReportGeneratorTab() {
    if (_isLoadingReports) {
      return const LoadingView(message: 'Loading activity reports...');
    }

    if (_reportError != null) {
      return ErrorView(
        message: _reportError!,
        onRetry: _loadReports,
      );
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'AI-Assisted Report Generator',
                      style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, letterSpacing: -0.3),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Create institutional reports strictly conforming to the official CUestIC template.',
                      style: TextStyle(fontSize: 13, color: AppConstants.textSecondary),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
              PrimaryButton(
                width: 200,
                height: 42,
                label: 'Create New Report',
                icon: Icons.note_add_outlined,
                onPressed: _createNewReport,
              ),
            ],
          ),
          const SizedBox(height: 24),
          if (_reports.isEmpty)
            Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 48.0),
                child: EmptyView(
                  message: 'No activity reports created yet. Create a report draft to enter details and generate official .docx documents.',
                  actionLabel: 'Create New Report',
                  onAction: _createNewReport,
                ),
              ),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _reports.length,
              separatorBuilder: (context, _) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final report = _reports[index];
                final isGenerated = report.status == 'generated';

                return Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: Colors.purple.withValues(alpha: 0.08),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Icon(Icons.article_outlined, color: Colors.purple, size: 28),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    child: Text(
                                      report.title,
                                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: isGenerated
                                          ? AppConstants.successGreen.withValues(alpha: 0.1)
                                          : AppConstants.warningOrange.withValues(alpha: 0.1),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text(
                                      report.status.toUpperCase(),
                                      style: TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.bold,
                                        color: isGenerated
                                            ? AppConstants.successGreen
                                            : AppConstants.warningOrange,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'Created by ${report.createdByName} • Official CUestIC Template Enabled',
                                style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 16),
                        SecondaryButton(
                          width: 140,
                          height: 38,
                          label: 'Open Editor',
                          icon: Icons.edit_note,
                          onPressed: () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (ctx) => ActivityReportEditorScreen(
                                  reportId: report.id,
                                  docService: _docService,
                                  authService: widget.authService,
                                ),
                              ),
                            ).then((_) => _loadReports());
                          },
                        ),
                        const SizedBox(width: 8),
                        IconButton(
                          tooltip: 'Delete Report',
                          icon: const Icon(Icons.delete_outline, color: AppConstants.dangerRed),
                          onPressed: () => _deleteReport(report),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
        ],
      ),
    );
  }
}
