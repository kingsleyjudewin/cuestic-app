import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import '../config/constants.dart';
import '../models/mc_script.dart';
import '../models/documentation.dart';
import '../models/event.dart';
import '../services/auth_service.dart';
import '../services/mc_service.dart';
import '../services/sync_service.dart';
import '../services/community_service.dart';
import '../utils/download_helper.dart';
import '../widgets/custom_card.dart';
import '../widgets/state_views.dart';
import 'community_screen.dart';
import 'mc_script_editor_screen.dart';

class McDashboardScreen extends StatefulWidget {
  final AuthService authService;
  final SyncService syncService;
  final VoidCallback onLogout;
  final VoidCallback? onSwitchToAdmin;

  const McDashboardScreen({
    super.key,
    required this.authService,
    required this.syncService,
    required this.onLogout,
    this.onSwitchToAdmin,
  });

  @override
  State<McDashboardScreen> createState() => _McDashboardScreenState();
}

class _McDashboardScreenState extends State<McDashboardScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  late McService _mcService;

  bool _isLoadingFolders = true;
  bool _isLoadingScripts = true;
  bool _isLoadingTemplates = true;
  bool _isLoadingTasks = true;

  String? _folderError;
  String? _scriptError;
  String? _templateError;
  String? _taskError;

  List<EventFolder> _folders = [];
  List<McScript> _scripts = [];
  List<McTemplate> _templates = [];
  List<EventTypeOption> _eventTypes = [];
  List<Map<String, dynamic>> _myTasks = [];
  List<Event> _availableEvents = [];

  EventFolder? _selectedFolder;
  bool _isLoadingFolderDocs = false;

  String _scriptStatusFilter = 'all';

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _mcService = McService(apiClient: widget.syncService.apiClient);

    // Instant 0ms pre-population from in-memory cache
    if (McService.hasCachedFolders) {
      _folders = McService.cachedFolders!;
      _isLoadingFolders = false;
    }
    if (McService.hasCachedScripts) {
      _scripts = McService.cachedScripts!;
      _isLoadingScripts = false;
    }
    if (McService.hasCachedTemplates) {
      _templates = McService.cachedTemplates!;
      _eventTypes = McService.cachedEventTypes!;
      _isLoadingTemplates = false;
    }
    if (McService.hasCachedTasks) {
      _myTasks = McService.cachedMyTasks!;
      _isLoadingTasks = false;
    }
    if (McService.hasCachedEvents) {
      _availableEvents = McService.cachedAvailableEvents!;
    }

    _loadAll();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadAll() async {
    await Future.wait([
      _loadFolders(),
      _loadScripts(),
      _loadTemplatesAndEventTypes(),
      _loadMyTasks(),
      _loadAvailableEvents(),
    ]);
  }

  Future<void> _loadFolders() async {
    if (_folders.isEmpty) {
      setState(() {
        _isLoadingFolders = true;
        _folderError = null;
      });
    }
    try {
      final folders = await _mcService.fetchFolders();
      if (mounted) {
        setState(() {
          _folders = folders;
          _isLoadingFolders = false;
        });
      }
    } catch (e) {
      if (mounted && _folders.isEmpty) {
        setState(() {
          _folderError = 'Failed to load event folders: $e';
          _isLoadingFolders = false;
        });
      }
    }
  }

  Future<void> _loadScripts() async {
    if (_scripts.isEmpty) {
      setState(() {
        _isLoadingScripts = true;
        _scriptError = null;
      });
    }
    try {
      final statusParam = _scriptStatusFilter == 'all' ? null : _scriptStatusFilter;
      final scripts = await _mcService.fetchScripts(status: statusParam);
      if (mounted) {
        setState(() {
          _scripts = scripts;
          _isLoadingScripts = false;
        });
      }
    } catch (e) {
      if (mounted && _scripts.isEmpty) {
        setState(() {
          _scriptError = 'Failed to load MC hosting scripts: $e';
          _isLoadingScripts = false;
        });
      }
    }
  }

  Future<void> _loadTemplatesAndEventTypes() async {
    if (_templates.isEmpty || _eventTypes.isEmpty) {
      setState(() {
        _isLoadingTemplates = true;
        _templateError = null;
      });
    }
    try {
      final results = await Future.wait([
        _mcService.fetchTemplates(),
        _mcService.fetchEventTypes(),
      ]);
      if (mounted) {
        setState(() {
          _templates = results[0] as List<McTemplate>;
          _eventTypes = results[1] as List<EventTypeOption>;
          _isLoadingTemplates = false;
        });
      }
    } catch (e) {
      if (mounted && _templates.isEmpty) {
        setState(() {
          _templateError = 'Failed to load templates: $e';
          _isLoadingTemplates = false;
        });
      }
    }
  }

  Future<void> _loadMyTasks() async {
    if (_myTasks.isEmpty) {
      setState(() {
        _isLoadingTasks = true;
        _taskError = null;
      });
    }
    try {
      final tasks = await _mcService.fetchMyTasks();
      if (mounted) {
        setState(() {
          _myTasks = tasks;
          _isLoadingTasks = false;
        });
      }
    } catch (e) {
      if (mounted && _myTasks.isEmpty) {
        setState(() {
          _taskError = 'Failed to load assigned tasks: $e';
          _isLoadingTasks = false;
        });
      }
    }
  }

  Future<void> _loadAvailableEvents() async {
    try {
      final evts = await _mcService.fetchAvailableEvents();
      if (mounted) {
        setState(() => _availableEvents = evts);
      }
    } catch (_) {}
  }

  // ---------------------------------------------------------------------------
  // Folder Operations
  // ---------------------------------------------------------------------------
  Future<void> _showCreateFolderDialog() async {
    final nameCtrl = TextEditingController();
    final descCtrl = TextEditingController();
    final driveCtrl = TextEditingController();

    await showDialog(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          backgroundColor: AppConstants.pureWhite,
          surfaceTintColor: Colors.transparent,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: const BorderSide(color: AppConstants.borderLight),
          ),
          title: const Text('Create Event Folder', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameCtrl,
                  autofocus: true,
                  decoration: const InputDecoration(
                    labelText: 'Folder Name *',
                    hintText: 'e.g. Annual Department Symposium 2026',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: descCtrl,
                  maxLines: 2,
                  decoration: const InputDecoration(
                    labelText: 'Description (Optional)',
                    hintText: 'e.g. Master hosting notes, anchor assignments, and stage scripts',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: driveCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Google Drive Folder Link / ID (Optional)',
                    hintText: 'https://drive.google.com/drive/folders/...',
                    prefixIcon: Icon(Icons.cloud_outlined, size: 20),
                    border: OutlineInputBorder(),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel', style: TextStyle(color: AppConstants.pureBlack)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppConstants.pureBlack,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              onPressed: () async {
                final name = nameCtrl.text.trim();
                if (name.isEmpty) return;
                Navigator.pop(ctx);
                try {
                  await _mcService.createFolder(
                    name,
                    description: descCtrl.text.trim(),
                    driveLink: driveCtrl.text.trim(),
                  );
                  _loadFolders();
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Folder "$name" created successfully.')),
                    );
                  }
                } catch (e) {
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
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
    );
  }

  Future<void> _openFolder(EventFolder folder) async {
    setState(() {
      _selectedFolder = folder;
      _isLoadingFolderDocs = true;
    });
    try {
      final updated = await _mcService.getFolder(folder.id);
      if (mounted) {
        setState(() {
          _selectedFolder = updated;
          _isLoadingFolderDocs = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoadingFolderDocs = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to load folder contents: $e')),
        );
      }
    }
  }

  Future<void> _uploadScriptToFolder(EventFolder folder) async {
    try {
      final file = await FilePicker.pickFile();
      if (file == null) return;

      final bytes = await file.readAsBytes();

      final uploaded = await _mcService.uploadDocument(
        folderId: folder.id,
        fileBytes: bytes,
        filename: file.name,
      );

      await _openFolder(folder);
      _loadFolders();

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Uploaded "${uploaded.fileName}" successfully!'),
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
    try {
      final bytes = await _mcService.downloadDocument(doc.id);
      final msg = await DownloadHelper.downloadFile(bytes, doc.fileName);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(msg), backgroundColor: AppConstants.successGreen),
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
        content: Text('Are you sure you want to delete "${doc.fileName}"?'),
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
      await _mcService.deleteDocument(doc.id);
      if (_selectedFolder != null) {
        await _openFolder(_selectedFolder!);
      }
      _loadFolders();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Document deleted.')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to delete document: $e')));
      }
    }
  }

  Future<void> _deleteFolder(EventFolder folder) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Folder'),
        content: Text('Are you sure you want to delete "${folder.name}" and all uploaded documents?'),
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
      await _mcService.deleteFolder(folder.id);
      if (_selectedFolder?.id == folder.id) {
        setState(() => _selectedFolder = null);
      }
      _loadFolders();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Folder "${folder.name}" deleted.')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to delete folder: $e')));
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Multi-step Script Creation Wizard
  // ---------------------------------------------------------------------------
  Future<void> _showCreateScriptWizard({String? preselectedEventType, int? preselectedTemplateId}) async {
    final titleCtrl = TextEditingController(text: 'University Department Event Hosting Script');
    final venueCtrl = TextEditingController(text: 'Campus Auditorium');
    final deptCtrl = TextEditingController(text: 'Department of Electronics and Communication Engineering');
    final clubCtrl = TextEditingController(text: 'CUestIC & IEEE Student Branch');
    final dateCtrl = TextEditingController(text: DateTime.now().toString().split(' ')[0]);

    String selectedType = preselectedEventType ?? (_eventTypes.isNotEmpty ? _eventTypes.first.eventType : 'Technical Talk');
    int? selectedTemplateId = preselectedTemplateId;
    String selectedTone = 'Formal';

    List<TextEditingController> anchorCtrls = [
      TextEditingController(text: 'Merrick Dias'),
      TextEditingController(text: 'Qurrath Ul Ain'),
    ];

    int? linkedEventId;

    await showDialog(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (dialogCtx, setModalState) {
            return AlertDialog(
              backgroundColor: AppConstants.pureWhite,
              surfaceTintColor: Colors.transparent,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(14),
                side: const BorderSide(color: AppConstants.borderLight),
              ),
              title: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppConstants.pureBlack,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.mic, color: Colors.white, size: 20),
                  ),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Create New MC Script', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
                        Text('Configure event details, anchors, and select programme blueprint',
                            style: TextStyle(fontSize: 12, color: AppConstants.textSecondary)),
                      ],
                    ),
                  ),
                ],
              ),
              content: SizedBox(
                width: 680,
                child: SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Section 1: Link Existing Event (Optional)
                      if (_availableEvents.isNotEmpty) ...[
                        const Text('Link Department Event (Optional)',
                            style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                        const SizedBox(height: 6),
                        DropdownButtonFormField<int>(
                          initialValue: linkedEventId,
                          decoration: InputDecoration(
                            hintText: 'Select an existing club event to auto-fill details',
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                          ),
                          items: [
                            const DropdownMenuItem<int>(
                              value: null,
                              child: Text('None (Enter details manually)'),
                            ),
                            ..._availableEvents.map((e) => DropdownMenuItem<int>(
                                  value: e.id,
                                  child: Text('${e.name} (${e.startAt.toIso8601String().split('T')[0]})'),
                                )),
                          ],
                          onChanged: (val) {
                            setModalState(() {
                              linkedEventId = val;
                              if (val != null) {
                                final evt = _availableEvents.firstWhere((e) => e.id == val);
                                titleCtrl.text = '${evt.name} - Hosting Script';
                                if (evt.location != null && evt.location!.isNotEmpty) {
                                  venueCtrl.text = evt.location!;
                                }
                                dateCtrl.text = evt.startAt.toIso8601String().split('T')[0];
                              }
                            });
                          },
                        ),
                        const SizedBox(height: 14),
                      ],

                      // Section 2: Event Details
                      const Text('Event Information', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 6),
                      TextField(
                        controller: titleCtrl,
                        decoration: InputDecoration(
                          labelText: 'Event Script Title *',
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                        ),
                      ),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: venueCtrl,
                              decoration: InputDecoration(
                                labelText: 'Venue',
                                border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: TextField(
                              controller: dateCtrl,
                              decoration: InputDecoration(
                                labelText: 'Date (YYYY-MM-DD)',
                                border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: deptCtrl,
                              decoration: InputDecoration(
                                labelText: 'Organizing Department',
                                border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: TextField(
                              controller: clubCtrl,
                              decoration: InputDecoration(
                                labelText: 'Club / Association',
                                border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Section 3: MC Anchors Roster
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text('MC Anchors on Stage', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                          TextButton.icon(
                            icon: const Icon(Icons.add, size: 16),
                            label: const Text('Add MC', style: TextStyle(fontSize: 12)),
                            onPressed: () {
                              setModalState(() {
                                anchorCtrls.add(TextEditingController(text: 'Anchor ${anchorCtrls.length + 1}'));
                              });
                            },
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Column(
                        children: List.generate(anchorCtrls.length, (idx) {
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: Row(
                              children: [
                                CircleAvatar(
                                  radius: 14,
                                  backgroundColor: AppConstants.pureBlack,
                                  child: Text('MC ${idx + 1}',
                                      style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold)),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: TextField(
                                    controller: anchorCtrls[idx],
                                    decoration: InputDecoration(
                                      labelText: 'MC ${idx + 1} Name',
                                      contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                                    ),
                                  ),
                                ),
                                if (anchorCtrls.length > 1)
                                  IconButton(
                                    icon: const Icon(Icons.remove_circle_outline, size: 18, color: Colors.red),
                                    onPressed: () {
                                      setModalState(() {
                                        anchorCtrls.removeAt(idx);
                                      });
                                    },
                                  ),
                              ],
                            ),
                          );
                        }),
                      ),
                      const SizedBox(height: 14),

                      // Section 4: Hosting Tone
                      const Text('Desired Hosting Tone', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 8,
                        children: ['Formal', 'Semi-formal', 'Energetic', 'Celebratory'].map((tone) {
                          final isSel = selectedTone == tone;
                          return ChoiceChip(
                            label: Text(tone),
                            selected: isSel,
                            selectedColor: AppConstants.pureBlack,
                            labelStyle: TextStyle(
                              color: isSel ? Colors.white : Colors.black87,
                              fontWeight: isSel ? FontWeight.bold : FontWeight.normal,
                              fontSize: 12,
                            ),
                            onSelected: (val) {
                              if (val) setModalState(() => selectedTone = tone);
                            },
                          );
                        }).toList(),
                      ),
                      const SizedBox(height: 16),

                      // Section 5: Programme Blueprint / Event Type Selection
                      const Text('Select Event Type & Programme Blueprint (15 Types)',
                          style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 6),
                      Container(
                        height: 180,
                        decoration: BoxDecoration(
                          border: Border.all(color: AppConstants.borderLight),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: ListView.separated(
                          itemCount: _eventTypes.isNotEmpty ? _eventTypes.length : 1,
                          separatorBuilder: (c, i) => const Divider(height: 1),
                          itemBuilder: (c, i) {
                            if (_eventTypes.isEmpty) {
                              return const ListTile(title: Text('Standard Technical Talk Blueprint'));
                            }
                            final opt = _eventTypes[i];
                            final isSel = selectedType == opt.eventType;
                            return ListTile(
                              dense: true,
                              selected: isSel,
                              selectedTileColor: Colors.black.withValues(alpha: 0.04),
                              leading: Icon(
                                isSel ? Icons.radio_button_checked : Icons.radio_button_off,
                                color: isSel ? AppConstants.pureBlack : Colors.grey,
                                size: 18,
                              ),
                              title: Row(
                                children: [
                                  Text(opt.eventType, style: TextStyle(fontWeight: isSel ? FontWeight.bold : FontWeight.normal)),
                                  const SizedBox(width: 8),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: Colors.grey.shade200,
                                      borderRadius: BorderRadius.circular(10),
                                    ),
                                    child: Text('${opt.suggestedSegmentCount} Segments', style: const TextStyle(fontSize: 10)),
                                  ),
                                ],
                              ),
                              subtitle: Text(opt.description, style: const TextStyle(fontSize: 11)),
                              onTap: () {
                                setModalState(() {
                                  selectedType = opt.eventType;
                                  // Find matching template if available
                                  final matching = _templates.firstWhere(
                                    (t) => t.eventType == opt.eventType && t.isDefault,
                                    orElse: () => _templates.isNotEmpty ? _templates.first : McTemplate(id: 0, name: '', eventType: ''),
                                  );
                                  if (matching.id > 0) {
                                    selectedTemplateId = matching.id;
                                  }
                                });
                              },
                            );
                          },
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text('Cancel', style: TextStyle(color: AppConstants.pureBlack)),
                ),
                ElevatedButton.icon(
                  icon: const Icon(Icons.arrow_forward, size: 16),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppConstants.pureBlack,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                  ),
                  label: const Text('Create & Open Programme Builder'),
                  onPressed: () async {
                    final title = titleCtrl.text.trim();
                    if (title.isEmpty) return;

                    Navigator.pop(ctx);

                    final anchorsPayload = anchorCtrls
                        .where((c) => c.text.trim().isNotEmpty)
                        .map((c) => {'name': c.text.trim(), 'role': 'Host'})
                        .toList();

                    try {
                      final script = await _mcService.createScript({
                        'title': title,
                        'event_type': selectedType,
                        'template_id': selectedTemplateId,
                        'event_id': linkedEventId,
                        'venue': venueCtrl.text.trim(),
                        'event_date': dateCtrl.text.trim(),
                        'tone': selectedTone,
                        'number_of_anchors': anchorsPayload.length,
                        'anchors': anchorsPayload,
                        'event_metadata': {
                          'organizing_department': deptCtrl.text.trim(),
                          'organizing_club': clubCtrl.text.trim(),
                        },
                      });

                      _loadScripts();

                      if (mounted) {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (ctx) => McScriptEditorScreen(
                              scriptId: script.id,
                              mcService: _mcService,
                              authService: widget.authService,
                            ),
                          ),
                        ).then((_) => _loadScripts());
                      }
                    } catch (e) {
                      if (mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('Failed to initialize script: $e'), backgroundColor: Colors.red),
                        );
                      }
                    }
                  },
                ),
              ],
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
      backgroundColor: const Color(0xFFFAFAFA),
      appBar: AppBar(
        backgroundColor: AppConstants.pureWhite,
        foregroundColor: AppConstants.pureBlack,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: AppConstants.pureBlack,
                borderRadius: BorderRadius.circular(6),
              ),
              child: const Icon(Icons.mic, color: Colors.white, size: 18),
            ),
            const SizedBox(width: 10),
            const Text('MC Team Portal', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
            const SizedBox(width: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: Colors.grey.shade200,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                widget.authService.displayName,
                style: const TextStyle(fontSize: 11, color: AppConstants.pureBlack, fontWeight: FontWeight.w600),
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, size: 20),
            tooltip: 'Refresh',
            onPressed: _loadAll,
          ),
          IconButton(
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
          if (widget.authService.isAdmin && widget.onSwitchToAdmin != null)
            TextButton.icon(
              icon: const Icon(Icons.admin_panel_settings, size: 18),
              label: const Text('Admin Portal'),
              onPressed: widget.onSwitchToAdmin,
            ),
          IconButton(
            tooltip: 'Logout',
            icon: const Icon(Icons.logout, size: 20),
            onPressed: () async {
              final confirm = await showDialog<bool>(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Text('Logout'),
                  content: const Text('Are you sure you want to log out of your MC account?'),
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
        ],
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppConstants.pureBlack,
          unselectedLabelColor: AppConstants.textSecondary,
          indicatorColor: AppConstants.pureBlack,
          indicatorWeight: 2.5,
          tabs: const [
            Tab(icon: Icon(Icons.folder_outlined, size: 18), text: 'Event Documents'),
            Tab(icon: Icon(Icons.mic_none, size: 18), text: 'MC Scripts'),
            Tab(icon: Icon(Icons.dashboard_customize_outlined, size: 18), text: 'Saved Templates'),
            Tab(icon: Icon(Icons.task_alt_outlined, size: 18), text: 'Assigned Tasks'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildEventDocumentsTab(),
          _buildScriptsTab(),
          _buildTemplatesTab(),
          _buildTasksTab(),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 1: Event Documents (Folders & Uploads)
  // ---------------------------------------------------------------------------
  Widget _buildEventDocumentsTab() {
    if (_selectedFolder != null) {
      return _buildFolderDetailView();
    }

    if (_isLoadingFolders) {
      return const LoadingView(message: 'Loading event folders...');
    }

    if (_folderError != null) {
      return ErrorView(message: _folderError!, onRetry: _loadFolders);
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Event Script Folders', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                  SizedBox(height: 4),
                  Text('Organize hosting scripts, speaker bios, and files by event',
                      style: TextStyle(color: AppConstants.textSecondary, fontSize: 13)),
                ],
              ),
              ElevatedButton.icon(
                icon: const Icon(Icons.create_new_folder_outlined, size: 16),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppConstants.pureBlack,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                ),
                label: const Text('Create Folder'),
                onPressed: _showCreateFolderDialog,
              ),
            ],
          ),
          const SizedBox(height: 20),
          if (_folders.isEmpty)
            CustomCard(
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 40),
                  child: Column(
                    children: [
                      Icon(Icons.folder_open_outlined, size: 48, color: Colors.grey.shade400),
                      const SizedBox(height: 12),
                      const Text('No folders created yet', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                      const SizedBox(height: 6),
                      const Text('Create an event folder to upload hosting scripts and files',
                          style: TextStyle(color: AppConstants.textSecondary, fontSize: 13)),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        style: ElevatedButton.styleFrom(backgroundColor: AppConstants.pureBlack, foregroundColor: Colors.white),
                        onPressed: _showCreateFolderDialog,
                        child: const Text('Create First Folder'),
                      ),
                    ],
                  ),
                ),
              ),
            )
          else
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                maxCrossAxisExtent: 320,
                crossAxisSpacing: 16,
                mainAxisSpacing: 16,
                childAspectRatio: 1.35,
              ),
              itemCount: _folders.length,
              itemBuilder: (ctx, i) {
                final folder = _folders[i];
                return InkWell(
                  onTap: () => _openFolder(folder),
                  borderRadius: BorderRadius.circular(12),
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppConstants.pureWhite,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppConstants.borderLight),
                      boxShadow: [
                        BoxShadow(color: Colors.black.withValues(alpha: 0.02), blurRadius: 4, offset: const Offset(0, 2)),
                      ],
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: Colors.grey.shade100,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: const Icon(Icons.folder, color: AppConstants.pureBlack, size: 24),
                            ),
                            const Spacer(),
                            PopupMenuButton<String>(
                              icon: const Icon(Icons.more_vert, size: 18),
                              onSelected: (val) {
                                if (val == 'upload') _uploadScriptToFolder(folder);
                                if (val == 'delete') _deleteFolder(folder);
                              },
                              itemBuilder: (c) => [
                                const PopupMenuItem(value: 'upload', child: Text('Upload Script')),
                                const PopupMenuItem(value: 'delete', child: Text('Delete Folder', style: TextStyle(color: Colors.red))),
                              ],
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Text(
                          folder.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                        ),
                        if (folder.description != null && folder.description!.isNotEmpty) ...[
                          const SizedBox(height: 4),
                          Text(
                            folder.description!,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(color: AppConstants.textSecondary, fontSize: 11),
                          ),
                        ],
                        const Spacer(),
                        Row(
                          children: [
                            Icon(Icons.description_outlined, size: 13, color: Colors.grey.shade600),
                            const SizedBox(width: 4),
                            Text('${folder.documentCount} docs', style: TextStyle(color: Colors.grey.shade600, fontSize: 11)),
                            const Spacer(),
                            if (folder.driveWebViewLink != null && folder.driveWebViewLink!.isNotEmpty)
                              const Icon(Icons.cloud_done_outlined, size: 15, color: Colors.blueGrey),
                          ],
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
                    Text(folder.name, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                    if (folder.description != null && folder.description!.isNotEmpty)
                      Text(folder.description!, style: const TextStyle(color: AppConstants.textSecondary, fontSize: 13)),
                  ],
                ),
              ),
              ElevatedButton.icon(
                icon: const Icon(Icons.upload_file, size: 16),
                style: ElevatedButton.styleFrom(backgroundColor: AppConstants.pureBlack, foregroundColor: Colors.white),
                label: const Text('Upload Script File'),
                onPressed: () => _uploadScriptToFolder(folder),
              ),
            ],
          ),
          const SizedBox(height: 20),
          if (_isLoadingFolderDocs)
            const Center(child: Padding(padding: EdgeInsets.all(40), child: CircularProgressIndicator()))
          else if (folder.documents.isEmpty)
            CustomCard(
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 40),
                  child: Column(
                    children: [
                      Icon(Icons.upload_file, size: 48, color: Colors.grey.shade400),
                      const SizedBox(height: 12),
                      const Text('No scripts or files uploaded yet', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                      const SizedBox(height: 6),
                      const Text('Upload DOCX, PDF, or TXT hosting scripts',
                          style: TextStyle(color: AppConstants.textSecondary, fontSize: 12)),
                      const SizedBox(height: 14),
                      ElevatedButton(
                        style: ElevatedButton.styleFrom(backgroundColor: AppConstants.pureBlack, foregroundColor: Colors.white),
                        onPressed: () => _uploadScriptToFolder(folder),
                        child: const Text('Upload Script'),
                      ),
                    ],
                  ),
                ),
              ),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: folder.documents.length,
              separatorBuilder: (context, index) => const SizedBox(height: 8),
              itemBuilder: (ctx, i) {
                final doc = folder.documents[i];
                return Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppConstants.pureWhite,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppConstants.borderLight),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.description, color: AppConstants.pureBlack, size: 28),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(doc.fileName, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                            const SizedBox(height: 2),
                            Text(
                              'Uploaded by ${doc.uploadedByName} • ${doc.createdAt.toIso8601String().split('T')[0]}',
                              style: const TextStyle(fontSize: 11, color: AppConstants.textSecondary),
                            ),
                          ],
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.download, size: 20),
                        tooltip: 'Download',
                        onPressed: () => _downloadDoc(doc),
                      ),
                      IconButton(
                        icon: const Icon(Icons.delete_outline, size: 20, color: Colors.red),
                        tooltip: 'Delete',
                        onPressed: () => _deleteDoc(doc),
                      ),
                    ],
                  ),
                );
              },
            ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 2: MC Scripts (Dynamic Neon Postgres Data)
  // ---------------------------------------------------------------------------
  Widget _buildScriptsTab() {
    if (_isLoadingScripts) {
      return const LoadingView(message: 'Loading MC scripts...');
    }

    if (_scriptError != null) {
      return ErrorView(message: _scriptError!, onRetry: _loadScripts);
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Event Hosting Scripts', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                  SizedBox(height: 4),
                  Text('Build, reorder segments, and generate stage scripts with AI',
                      style: TextStyle(color: AppConstants.textSecondary, fontSize: 13)),
                ],
              ),
              ElevatedButton.icon(
                icon: const Icon(Icons.add, size: 16),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppConstants.pureBlack,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                ),
                label: const Text('Create New MC Script'),
                onPressed: () => _showCreateScriptWizard(),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Status Filter Chips
          Wrap(
            spacing: 8,
            children: [
              {'label': 'All Scripts', 'val': 'all'},
              {'label': 'Draft', 'val': 'draft'},
              {'label': 'In Progress', 'val': 'in_progress'},
              {'label': 'Ready for Review', 'val': 'ready_for_review'},
              {'label': 'Finalized', 'val': 'finalized'},
            ].map((f) {
              final isSel = _scriptStatusFilter == f['val'];
              return ChoiceChip(
                label: Text(f['label']!),
                selected: isSel,
                selectedColor: AppConstants.pureBlack,
                labelStyle: TextStyle(
                  color: isSel ? Colors.white : Colors.black87,
                  fontSize: 12,
                  fontWeight: isSel ? FontWeight.bold : FontWeight.normal,
                ),
                onSelected: (val) {
                  setState(() => _scriptStatusFilter = f['val']!);
                  _loadScripts();
                },
              );
            }).toList(),
          ),
          const SizedBox(height: 16),

          if (_scripts.isEmpty)
            CustomCard(
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 40),
                  child: Column(
                    children: [
                      Icon(Icons.mic_external_off_outlined, size: 48, color: Colors.grey.shade400),
                      const SizedBox(height: 12),
                      const Text('No MC hosting scripts found', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                      const SizedBox(height: 6),
                      const Text('Launch the Intelligent MC Script Template Builder to create a stage-ready script',
                          style: TextStyle(color: AppConstants.textSecondary, fontSize: 13)),
                      const SizedBox(height: 16),
                      ElevatedButton.icon(
                        icon: const Icon(Icons.add, size: 16),
                        style: ElevatedButton.styleFrom(backgroundColor: AppConstants.pureBlack, foregroundColor: Colors.white),
                        onPressed: () => _showCreateScriptWizard(),
                        label: const Text('Create New MC Script'),
                      ),
                    ],
                  ),
                ),
              ),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _scripts.length,
              separatorBuilder: (context, index) => const SizedBox(height: 12),
              itemBuilder: (ctx, i) {
                final s = _scripts[i];
                return Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppConstants.pureWhite,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppConstants.borderLight),
                    boxShadow: [
                      BoxShadow(color: Colors.black.withValues(alpha: 0.02), blurRadius: 4, offset: const Offset(0, 2)),
                    ],
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: AppConstants.pureBlack,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(Icons.mic, color: Colors.white, size: 22),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Text(s.title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                  decoration: BoxDecoration(
                                    color: s.statusColor.withValues(alpha: 0.12),
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  child: Text(
                                    s.statusLabel,
                                    style: TextStyle(color: s.statusColor, fontSize: 11, fontWeight: FontWeight.bold),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 6),
                            Wrap(
                              spacing: 12,
                              runSpacing: 4,
                              children: [
                                Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(Icons.category_outlined, size: 13, color: Colors.grey.shade600),
                                    const SizedBox(width: 4),
                                    Text(s.eventType ?? 'Department Event',
                                        style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
                                  ],
                                ),
                                Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(Icons.view_agenda_outlined, size: 13, color: Colors.grey.shade600),
                                    const SizedBox(width: 4),
                                    Text('${s.segments.length} Segments',
                                        style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
                                  ],
                                ),
                                Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(Icons.person_outline, size: 13, color: Colors.grey.shade600),
                                    const SizedBox(width: 4),
                                    Text('By ${s.creatorName ?? 'MC Team'}',
                                        style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
                                  ],
                                ),
                                Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(Icons.schedule, size: 13, color: Colors.grey.shade600),
                                    const SizedBox(width: 4),
                                    Text('Updated ${s.updatedAt?.split('T')[0] ?? ''}',
                                        style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
                                  ],
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 12),
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          IconButton(
                            icon: const Icon(Icons.download_outlined, size: 20),
                            tooltip: 'Download Stage DOCX',
                            onPressed: () async {
                              try {
                                final bytes = await _mcService.downloadDocxBytes(s.id);
                                final msg = await DownloadHelper.downloadFile(
                                  bytes,
                                  'MC_Script_${s.title.replaceAll(' ', '_')}.docx',
                                );
                                if (mounted) {
                                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
                                }
                              } catch (e) {
                                if (mounted) {
                                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Export failed: $e')));
                                }
                              }
                            },
                          ),
                          ElevatedButton.icon(
                            icon: const Icon(Icons.edit_note, size: 16),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppConstants.pureBlack,
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                            ),
                            label: const Text('Open Editor'),
                            onPressed: () {
                              Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (ctx) => McScriptEditorScreen(
                                    scriptId: s.id,
                                    mcService: _mcService,
                                    authService: widget.authService,
                                  ),
                                ),
                              ).then((_) => _loadScripts());
                            },
                          ),
                        ],
                      ),
                    ],
                  ),
                );
              },
            ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 3: Saved Templates
  // ---------------------------------------------------------------------------
  Widget _buildTemplatesTab() {
    if (_isLoadingTemplates) {
      return const LoadingView(message: 'Loading programme templates...');
    }

    if (_templateError != null) {
      return ErrorView(message: _templateError!, onRetry: _loadTemplatesAndEventTypes);
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Reusable MC Programme Templates', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                  SizedBox(height: 4),
                  Text('Pre-configured programme flows modeled after official university protocols',
                      style: TextStyle(color: AppConstants.textSecondary, fontSize: 13)),
                ],
              ),
              ElevatedButton.icon(
                icon: const Icon(Icons.add, size: 16),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppConstants.pureBlack,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                label: const Text('New Script from Blueprint'),
                onPressed: () => _showCreateScriptWizard(),
              ),
            ],
          ),
          const SizedBox(height: 20),
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
              maxCrossAxisExtent: 380,
              crossAxisSpacing: 16,
              mainAxisSpacing: 16,
              childAspectRatio: 1.25,
            ),
            itemCount: _templates.length,
            itemBuilder: (ctx, i) {
              final t = _templates[i];
              return Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppConstants.pureWhite,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppConstants.borderLight),
                  boxShadow: [
                    BoxShadow(color: Colors.black.withValues(alpha: 0.02), blurRadius: 4, offset: const Offset(0, 2)),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: t.isDefault ? Colors.grey.shade100 : Colors.blue.shade50,
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(color: t.isDefault ? Colors.grey.shade300 : Colors.blue.shade200),
                          ),
                          child: Text(
                            t.isDefault ? 'Standard Blueprint' : 'Custom Team Blueprint',
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                              color: t.isDefault ? Colors.grey.shade700 : Colors.blue.shade800,
                            ),
                          ),
                        ),
                        const Spacer(),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.grey.shade200,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text('${t.segmentCount} Segments', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(t.name, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                    const SizedBox(height: 2),
                    Text(t.eventType, style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary, fontWeight: FontWeight.w500)),
                    if (t.description != null && t.description!.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text(
                        t.description!,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 11, color: AppConstants.textSecondary),
                      ),
                    ],
                    const Spacer(),
                    Row(
                      children: [
                        TextButton(
                          onPressed: () => _viewTemplateSegments(t),
                          child: const Text('View Segments', style: TextStyle(fontSize: 12, color: AppConstants.pureBlack)),
                        ),
                        const Spacer(),
                        ElevatedButton(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppConstants.pureBlack,
                            foregroundColor: Colors.white,
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          ),
                          onPressed: () => _showCreateScriptWizard(
                            preselectedEventType: t.eventType,
                            preselectedTemplateId: t.id,
                          ),
                          child: const Text('Use Blueprint', style: TextStyle(fontSize: 11)),
                        ),
                      ],
                    ),
                  ],
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  void _viewTemplateSegments(McTemplate t) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Row(
          children: [
            const Icon(Icons.view_agenda_outlined, size: 20),
            const SizedBox(width: 8),
            Expanded(child: Text('${t.name} (${t.segments.length} Segments)', style: const TextStyle(fontSize: 16))),
          ],
        ),
        content: SizedBox(
          width: 500,
          child: ListView.separated(
            shrinkWrap: true,
            itemCount: t.segments.length,
            separatorBuilder: (context, index) => const Divider(height: 1),
            itemBuilder: (c, idx) {
              final s = t.segments[idx];
              return ListTile(
                dense: true,
                leading: CircleAvatar(
                  radius: 12,
                  backgroundColor: AppConstants.pureBlack,
                  child: Text('${s.sequenceOrder}', style: const TextStyle(color: Colors.white, fontSize: 10)),
                ),
                title: Text(s.title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                subtitle: Text(
                  'Default MC: ${s.defaultMcAssignment} • ${s.segmentType}',
                  style: const TextStyle(fontSize: 11, color: AppConstants.textSecondary),
                ),
              );
            },
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppConstants.pureBlack, foregroundColor: Colors.white),
            onPressed: () {
              Navigator.pop(ctx);
              _showCreateScriptWizard(preselectedEventType: t.eventType, preselectedTemplateId: t.id);
            },
            child: const Text('Use Template'),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 4: Assigned Tasks
  // ---------------------------------------------------------------------------
  Widget _buildTasksTab() {
    if (_isLoadingTasks) {
      return const LoadingView(message: 'Loading assigned tasks...');
    }

    if (_taskError != null) {
      return ErrorView(message: _taskError!, onRetry: _loadMyTasks);
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('MC Team Tasks', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                  SizedBox(height: 4),
                  Text('Event hosting and script preparation tasks assigned from the Management',
                      style: TextStyle(color: AppConstants.textSecondary, fontSize: 13)),
                ],
              ),
              IconButton(icon: const Icon(Icons.refresh), onPressed: _loadMyTasks),
            ],
          ),
          const SizedBox(height: 20),
          if (_myTasks.isEmpty)
            CustomCard(
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 40),
                  child: Column(
                    children: [
                      Icon(Icons.task_alt, size: 48, color: Colors.grey.shade400),
                      const SizedBox(height: 12),
                      const Text('No assigned tasks at the moment', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                      const SizedBox(height: 6),
                      const Text('Tasks assigned to you will appear here with instant script linking',
                          style: TextStyle(color: AppConstants.textSecondary, fontSize: 12)),
                    ],
                  ),
                ),
              ),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _myTasks.length,
              separatorBuilder: (context, index) => const SizedBox(height: 12),
              itemBuilder: (ctx, i) {
                final task = _myTasks[i];
                final status = task['status']?.toString() ?? 'pending';
                final isCompleted = status.toLowerCase() == 'completed';

                return Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppConstants.pureWhite,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppConstants.borderLight),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        isCompleted ? Icons.check_circle : Icons.radio_button_unchecked,
                        color: isCompleted ? Colors.green : Colors.grey,
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              task['task']?['title']?.toString() ?? 'MC Hosting Task',
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                            ),
                            if (task['task']?['description'] != null)
                              Text(
                                task['task']['description'].toString(),
                                style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                              ),
                          ],
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: isCompleted ? Colors.green.shade50 : Colors.orange.shade50,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: isCompleted ? Colors.green.shade200 : Colors.orange.shade200),
                        ),
                        child: Text(
                          status.toUpperCase(),
                          style: TextStyle(
                            color: isCompleted ? Colors.green.shade800 : Colors.orange.shade800,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
        ],
      ),
    );
  }
}
