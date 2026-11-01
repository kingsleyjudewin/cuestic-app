import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import '../config/constants.dart';
import '../models/documentation.dart';
import '../services/documentation_service.dart';
import '../services/auth_service.dart';
import '../utils/download_helper.dart';
import '../widgets/primary_button.dart';
import '../widgets/secondary_button.dart';

class ActivityReportEditorScreen extends StatefulWidget {
  final int? reportId;
  final DocumentationService docService;
  final AuthService authService;

  const ActivityReportEditorScreen({
    super.key,
    this.reportId,
    required this.docService,
    required this.authService,
  });

  @override
  State<ActivityReportEditorScreen> createState() => _ActivityReportEditorScreenState();
}

class _ActivityReportEditorScreenState extends State<ActivityReportEditorScreen> {
  bool _isLoading = true;
  bool _isSaving = false;
  bool _isGenerating = false;
  bool _isAiBusy = false;
  String? _errorMessage;

  int? _currentReportId;
  String _reportStatus = 'draft';

  // Section 1: General Info
  final _titleController = TextEditingController();
  final _activityTypeController = TextEditingController(text: 'Workshop');
  final _dateController = TextEditingController();
  final _timeController = TextEditingController();
  final _venueController = TextEditingController();
  final _collaboratorsController = TextEditingController();

  // Section 2: Speakers (Dynamic list)
  final List<SpeakerEntry> _speakers = [SpeakerEntry()];

  // Section 3: Participants Profile & Content
  final _participantsTypeController = TextEditingController(text: 'UG / PG Students & Faculty');
  final _highlightsController = TextEditingController();
  final _summaryController = TextEditingController();
  final _keyTakeawaysController = TextEditingController();

  // Section 4: Speaker Profile & Organiser
  final _speakerProfileController = TextEditingController();
  final _organiserNameController = TextEditingController();
  final _organiserDesignationController = TextEditingController();
  final _organiserSignatureController = TextEditingController(text: 'Signed');

  // Section 5: Annexures
  final List<String> _photoPaths = [];
  final List<String> _attendancePaths = [];
  String? _posterPath;

  // Reference Poster & Vision Context
  Uint8List? _referencePosterBytes;
  String? _referencePosterName;
  int? _referencePosterDocId;
  String? _referencePosterSource; // 'local' or 'drive'
  Map<String, dynamic>? _extractedPosterContext;
  bool _isAnalyzingPoster = false;
  bool _includePosterContextInAi = true;

  // Section 6: Feedback & Impact
  final _impactAnalysisController = TextEditingController();

  // ---------------------------------------------------------------------------
  // AI Copilot State & Multi-Model Engine
  // ---------------------------------------------------------------------------
  String _selectedProvider = 'gemini';
  String _selectedModel = 'gemini-3.5-flash';
  List<Map<String, dynamic>> _availableModels = [];

  String _activeFieldKey = 'summary';
  String _activeFieldLabel = 'Summary of the Activity';
  TextEditingController? _activeFieldController;
  final _aiInstructionController = TextEditingController();
  String? _aiGeneratedText;
  String? _aiProviderName;

  final List<String> _activityTypes = [
    'Workshop',
    'Seminar',
    'Guest Lecture',
    'Technical Talk',
    'Hackathon',
    'Symposium',
    'Conference',
    'Panel Discussion',
    'Hands-on Training',
    'Department Club Activity',
    'Other',
  ];

  @override
  void initState() {
    super.initState();
    _currentReportId = widget.reportId;
    _activeFieldController = _summaryController;
    _loadReport();
    _loadModels();
  }

  Future<void> _loadModels() async {
    try {
      final models = await widget.docService.fetchAvailableAiModels();
      if (models.isNotEmpty && mounted) {
        setState(() {
          _availableModels = models;
          final def = models.firstWhere((m) => m['is_default'] == true, orElse: () => models.first);
          _selectedProvider = def['provider']?.toString() ?? 'gemini';
          _selectedModel = def['model']?.toString() ?? 'gemini-3.5-flash';
        });
      }
    } catch (_) {}
  }

  @override
  void dispose() {
    _titleController.dispose();
    _activityTypeController.dispose();
    _dateController.dispose();
    _timeController.dispose();
    _venueController.dispose();
    _collaboratorsController.dispose();
    _participantsTypeController.dispose();
    _highlightsController.dispose();
    _summaryController.dispose();
    _keyTakeawaysController.dispose();
    _speakerProfileController.dispose();
    _organiserNameController.dispose();
    _organiserDesignationController.dispose();
    _organiserSignatureController.dispose();
    _impactAnalysisController.dispose();
    _aiInstructionController.dispose();
    super.dispose();
  }

  void _setActiveField({
    required String key,
    required String label,
    required TextEditingController controller,
  }) {
    setState(() {
      _activeFieldKey = key;
      _activeFieldLabel = label;
      _activeFieldController = controller;
    });
  }

  Future<void> _loadReport() async {
    if (_currentReportId == null) {
      // New report draft initialization
      _titleController.text = 'New Activity Report';
      _dateController.text = DateTime.now().toString().split(' ')[0];
      _timeController.text = '10:00 AM - 1:00 PM';
      _venueController.text = 'Central Campus, Auditorium';
      _collaboratorsController.text = 'CUestIC Student Chapter';
      _organiserNameController.text = widget.authService.displayName;
      _organiserDesignationController.text = 'Documentation Lead';
      setState(() => _isLoading = false);
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final report = await widget.docService.getReport(_currentReportId!);
      _reportStatus = report.status;
      _titleController.text = report.title;

      final data = report.data;
      final genInfo = data['general_information'] as Map<String, dynamic>? ?? {};
      _activityTypeController.text = genInfo['type_of_activity']?.toString() ?? 'Workshop';
      _dateController.text = genInfo['date']?.toString() ?? '';
      _timeController.text = genInfo['time']?.toString() ?? '';
      _venueController.text = genInfo['venue']?.toString() ?? '';
      _collaboratorsController.text = genInfo['collaborators']?.toString() ?? '';

      final spkList = data['speakers'] as List<dynamic>?;
      _speakers.clear();
      if (spkList != null && spkList.isNotEmpty) {
        for (var s in spkList) {
          _speakers.add(SpeakerEntry.fromJson(Map<String, dynamic>.from(s as Map)));
        }
      } else {
        _speakers.add(SpeakerEntry());
      }

      final participants = (data['participants'] as Map<String, dynamic>?) ??
          (data['participants_profile'] as Map<String, dynamic>?) ??
          {};
      _participantsTypeController.text =
          participants['type_of_participants']?.toString() ?? 'UG / PG Students & Faculty';
      _highlightsController.text = participants['highlights']?.toString() ??
          participants['highlights_of_activity']?.toString() ??
          '';
      _summaryController.text = participants['summary']?.toString() ??
          participants['summary_of_activities']?.toString() ??
          '';
      _keyTakeawaysController.text = participants['key_takeaways']?.toString() ?? '';

      _speakerProfileController.text = data['speaker_profile']?.toString() ?? '';
      _impactAnalysisController.text = data['impact_analysis']?.toString() ?? '';

      final organiser = (data['organiser'] as Map<String, dynamic>?) ??
          (data['report_prepared_by'] as Map<String, dynamic>?) ??
          {};
      _organiserNameController.text =
          organiser['name']?.toString() ?? organiser['organiser_name']?.toString() ?? widget.authService.displayName;
      _organiserDesignationController.text =
          organiser['designation']?.toString() ?? 'Documentation Lead';
      _organiserSignatureController.text =
          organiser['signature']?.toString() ?? organiser['signature_text']?.toString() ?? 'Signed';

      final annexures = data['annexures'] as Map<String, dynamic>? ?? {};
      final photos = annexures['photos'] as List<dynamic>?;
      if (photos != null) {
        _photoPaths.clear();
        _photoPaths.addAll(photos.map((e) => e.toString()));
      }
      final attendance = annexures['attendance_sheets'] as List<dynamic>? ?? annexures['attendance_pages'] as List<dynamic>?;
      if (attendance != null) {
        _attendancePaths.clear();
        _attendancePaths.addAll(attendance.map((e) => e.toString()));
      }
      _posterPath = annexures['poster']?.toString() ?? annexures['poster_path']?.toString();
      if (_posterPath != null && _posterPath!.isNotEmpty) {
        _referencePosterName = _posterPath;
      }
      if (annexures['poster_base64'] != null && _referencePosterBytes == null) {
        try {
          final b64 = annexures['poster_base64'].toString();
          final cleanB64 = b64.contains(',') ? b64.split(',').last : b64;
          _referencePosterBytes = base64Decode(cleanB64);
        } catch (_) {}
      }
      final savedPosterContext = data['reference_poster_context'] as Map<String, dynamic>?;
      if (savedPosterContext != null) {
        _extractedPosterContext = savedPosterContext;
      }

      setState(() => _isLoading = false);
    } catch (e) {
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load report: $e';
      });
    }
  }

  Map<String, dynamic> _buildPayloadData() {
    return {
      'general_information': {
        'type_of_activity': _activityTypeController.text.trim(),
        'title_of_activity': _titleController.text.trim(),
        'date': _dateController.text.trim(),
        'dates': _dateController.text.trim(),
        'time': _timeController.text.trim(),
        'timings': _timeController.text.trim(),
        'venue': _venueController.text.trim(),
        'collaborators': _collaboratorsController.text.trim(),
      },
      'speakers': _speakers.map((s) => s.toJson()).toList(),
      'participants': {
        'type_of_participants': _participantsTypeController.text.trim(),
        'highlights': _highlightsController.text.trim(),
        'summary': _summaryController.text.trim(),
        'key_takeaways': _keyTakeawaysController.text.trim(),
      },
      'participants_profile': {
        'type_of_participants': _participantsTypeController.text.trim(),
        'highlights_of_activity': _highlightsController.text.trim(),
        'summary_of_activities': _summaryController.text.trim(),
        'key_takeaways': _keyTakeawaysController.text.trim(),
      },
      'speaker_profile': _speakerProfileController.text.trim(),
      'impact_analysis': _impactAnalysisController.text.trim(),
      'organiser': {
        'name': _organiserNameController.text.trim(),
        'designation': _organiserDesignationController.text.trim(),
        'signature': _organiserSignatureController.text.trim(),
      },
      'report_prepared_by': {
        'organiser_name': _organiserNameController.text.trim(),
        'designation': _organiserDesignationController.text.trim(),
        'signature_text': _organiserSignatureController.text.trim(),
      },
      'annexures': {
        'photos': _photoPaths,
        'attendance_sheets': _attendancePaths,
        'attendance_pages': _attendancePaths,
        if (_posterPath != null) 'poster': _posterPath,
        if (_posterPath != null) 'poster_path': _posterPath,
        if (_referencePosterBytes != null) 'poster_base64': base64Encode(_referencePosterBytes!),
        if (_referencePosterDocId != null) 'poster_document_id': _referencePosterDocId,
        if (_referencePosterName != null) 'poster_filename': _referencePosterName,
      },
      if (_extractedPosterContext != null) 'reference_poster_context': _extractedPosterContext,
    };
  }

  Future<void> _saveDraft({bool showNotice = true}) async {
    setState(() => _isSaving = true);
    try {
      final payloadData = _buildPayloadData();
      final title = _titleController.text.trim().isNotEmpty
          ? _titleController.text.trim()
          : 'Untitled Activity Report';

      if (_currentReportId == null) {
        final newReport = await widget.docService.createReport(
          title: title,
          description: _summaryController.text.trim(),
          data: payloadData,
        );
        _currentReportId = newReport.id;
        _reportStatus = newReport.status;
      } else {
        final updated = await widget.docService.updateReport(
          _currentReportId!,
          title: title,
          description: _summaryController.text.trim(),
          data: payloadData,
        );
        _reportStatus = updated.status;
      }

      if (mounted && showNotice) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Draft saved successfully.'),
            backgroundColor: AppConstants.successGreen,
            duration: Duration(seconds: 2),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error saving draft: $e'),
            backgroundColor: AppConstants.dangerRed,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  Future<void> _runAiCopilot({String action = 'draft'}) async {
    if (_currentReportId == null) {
      await _saveDraft(showNotice: false);
    }
    if (_currentReportId == null) return;

    setState(() {
      _isAiBusy = true;
      _aiGeneratedText = null;
    });

    final bool hasExtractedContext = _extractedPosterContext != null;
    try {
      final res = await widget.docService.aiAssist(
        reportId: _currentReportId!,
        fieldKey: _activeFieldKey,
        fieldLabel: _activeFieldLabel,
        instruction: _aiInstructionController.text.trim().isNotEmpty
            ? _aiInstructionController.text.trim()
            : 'Draft formal institutional content for this section.',
        currentContent: _activeFieldController?.text,
        action: action,
        provider: _selectedProvider,
        model: _selectedModel,
        imageBytes: (_includePosterContextInAi && !hasExtractedContext) ? _referencePosterBytes : null,
        documentId: (_includePosterContextInAi && !hasExtractedContext) ? _referencePosterDocId : null,
        posterContext: _includePosterContextInAi ? _extractedPosterContext : null,
      );

      final genText = res['generated_text']?.toString();
      final prov = res['provider']?.toString();
      final mod = res['model']?.toString();
      final provLabel = prov == 'gemini' ? 'Google Gemini' : 'Grok (Groq LPU)';
      _aiProviderName = mod != null && mod.isNotEmpty ? '$provLabel • $mod' : provLabel;

      if (genText != null && genText.isNotEmpty) {
        setState(() {
          _aiGeneratedText = genText;
        });
      } else if (res['notice'] != null) {
        setState(() {
          _aiGeneratedText = 'Notice: ${res['notice']}';
        });
      }
    } catch (e) {
      setState(() {
        _aiGeneratedText = 'AI Generation Error: $e';
      });
    } finally {
      if (mounted) setState(() => _isAiBusy = false);
    }
  }

  void _insertAiTextIntoField() {
    if (_aiGeneratedText != null && _activeFieldController != null) {
      setState(() {
        _activeFieldController!.text = _aiGeneratedText!;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Inserted AI content into $_activeFieldLabel.'),
          duration: const Duration(seconds: 2),
        ),
      );
    }
  }

  Future<void> _generateAndDownloadDocx() async {
    await _saveDraft(showNotice: false);
    if (_currentReportId == null) return;

    setState(() => _isGenerating = true);
    try {
      // Call backend generator
      await widget.docService.generateDocx(_currentReportId!);
      // Download bytes
      final bytes = await widget.docService.downloadDocx(_currentReportId!);

      final safeName = _titleController.text
          .trim()
          .replaceAll(RegExp(r'[^\w\s\-]'), '_')
          .replaceAll(' ', '_');
      final filename = 'Activity_Report_${safeName.isNotEmpty ? safeName : "Report"}.docx';

      final msg = await DownloadHelper.downloadFile(bytes, filename);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(msg.isNotEmpty ? msg : 'Report generated and downloaded: $filename'),
            backgroundColor: AppConstants.successGreen,
            duration: const Duration(seconds: 4),
          ),
        );
      }
      setState(() => _reportStatus = 'generated');
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to generate report: $e'),
            backgroundColor: AppConstants.dangerRed,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isGenerating = false);
    }
  }

  Future<void> _showSaveToFolderDialog() async {
    await _saveDraft(showNotice: false);
    if (_currentReportId == null) return;

    List<EventFolder> folders = [];
    try {
      folders = await widget.docService.fetchFolders();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not load event folders: $e')),
        );
      }
      return;
    }

    if (!mounted) return;

    if (folders.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No event folders found. Create a folder in Workspace first.')),
      );
      return;
    }

    int? selectedFolderId = folders.first.id;

    await showDialog(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (dialogCtx, setDialogState) {
            return AlertDialog(
              title: const Text('Save Report DOCX to Event Folder'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Select an event folder to store the generated official .docx file:'),
                  const SizedBox(height: 16),
                  DropdownButtonFormField<int>(
                    initialValue: selectedFolderId,
                    isExpanded: true,
                    items: folders
                        .map(
                          (f) => DropdownMenuItem(
                            value: f.id,
                            child: Text(f.name, overflow: TextOverflow.ellipsis),
                          ),
                        )
                        .toList(),
                    onChanged: (val) {
                      setDialogState(() => selectedFolderId = val);
                    },
                    decoration: const InputDecoration(
                      labelText: 'Event Folder',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogCtx),
                  child: const Text('Cancel'),
                ),
                ElevatedButton(
                  onPressed: () async {
                    Navigator.pop(dialogCtx);
                    if (selectedFolderId != null) {
                      try {
                        final doc = await widget.docService.saveReportToFolder(
                          reportId: _currentReportId!,
                          folderId: selectedFolderId!,
                        );
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text('Report saved to folder as "${doc.fileName}"'),
                              backgroundColor: AppConstants.successGreen,
                            ),
                          );
                        }
                      } catch (err) {
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text('Failed to save to folder: $err'),
                              backgroundColor: AppConstants.dangerRed,
                            ),
                          );
                        }
                      }
                    }
                  },
                  child: const Text('Save Document'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  // ---------------------------------------------------------------------------
  // Reference Poster & Vision AI Methods
  // ---------------------------------------------------------------------------
  Future<void> _pickLocalPoster() async {
    try {
      final file = await FilePicker.pickFile(
        type: FileType.image,
      );
      if (file != null) {
        final bytes = await file.readAsBytes();
        setState(() {
          _referencePosterBytes = bytes;
          _referencePosterName = file.name;
          _referencePosterDocId = null;
          _referencePosterSource = 'local';
          _posterPath = file.name;
        });
        _analyzeAndAutoFillPoster();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not pick image: $e')),
        );
      }
    }
  }

  Future<void> _showDriveImagePickerDialog() async {
    showDialog(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return AlertDialog(
              title: const Row(
                children: [
                  Icon(Icons.cloud_outlined, color: Colors.blue),
                  SizedBox(width: 8),
                  Text('Event Documents / Drive'),
                ],
              ),
              content: SizedBox(
                width: 500,
                height: 400,
                child: FutureBuilder<List<Map<String, dynamic>>>(
                  future: widget.docService.fetchDriveImages(),
                  builder: (context, snapshot) {
                    if (snapshot.connectionState == ConnectionState.waiting) {
                      return const Center(child: CircularProgressIndicator());
                    }
                    if (snapshot.hasError) {
                      return Center(child: Text('Error loading drive images: ${snapshot.error}'));
                    }
                    final images = snapshot.data ?? [];
                    if (images.isEmpty) {
                      return const Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.image_not_supported_outlined, size: 48, color: Colors.grey),
                            SizedBox(height: 12),
                            Text(
                              'No image files found in Event Folders.',
                              style: TextStyle(fontWeight: FontWeight.bold),
                            ),
                            SizedBox(height: 4),
                            Text(
                              'Upload poster images into an event folder first, or choose Local Storage.',
                              textAlign: TextAlign.center,
                              style: TextStyle(fontSize: 12, color: Colors.grey),
                            ),
                          ],
                        ),
                      );
                    }
                    return ListView.separated(
                      itemCount: images.length,
                      separatorBuilder: (_, _) => const Divider(height: 1),
                      itemBuilder: (context, idx) {
                        final img = images[idx];
                        final docId = img['id'] as int;
                        final name = img['original_filename']?.toString() ?? 'Image';
                        final folderName = img['folder_name']?.toString() ?? 'Event';
                        final sizeFormatted = img['file_size_formatted']?.toString() ?? '';

                        return ListTile(
                          leading: Container(
                            width: 44,
                            height: 44,
                            decoration: BoxDecoration(
                              color: Colors.blue.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: const Icon(Icons.image, color: Colors.blue),
                          ),
                          title: Text(name, maxLines: 1, overflow: TextOverflow.ellipsis),
                          subtitle: Text('Folder: $folderName • $sizeFormatted', style: const TextStyle(fontSize: 12)),
                          trailing: const Icon(Icons.arrow_forward_ios, size: 14),
                          onTap: () async {
                            final messenger = ScaffoldMessenger.of(context);
                            Navigator.of(ctx).pop();
                            setState(() => _isLoading = true);
                            try {
                              final bytes = await widget.docService.downloadDocumentBytes(docId);
                              setState(() {
                                _referencePosterBytes = Uint8List.fromList(bytes);
                                _referencePosterName = name;
                                _referencePosterDocId = docId;
                                _referencePosterSource = 'drive';
                                _posterPath = name;
                                _isLoading = false;
                              });
                              _analyzeAndAutoFillPoster();
                            } catch (e) {
                              setState(() => _isLoading = false);
                              messenger.showSnackBar(
                                SnackBar(content: Text('Failed to download image from drive: $e')),
                              );
                            }
                          },
                        );
                      },
                    );
                  },
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(ctx).pop(),
                  child: const Text('Cancel'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  void _showPosterUploadSourceDialog() {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(20.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Select Poster Source',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 4),
                const Text(
                  'Choose where to import your reference poster or flyer from:',
                  style: TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                ),
                const SizedBox(height: 16),
                ListTile(
                  leading: Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.indigo.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.upload_file, color: Colors.indigo),
                  ),
                  title: const Text('Local Storage / File Picker'),
                  subtitle: const Text('Pick from your computer or phone local drive'),
                  onTap: () {
                    Navigator.of(ctx).pop();
                    _pickLocalPoster();
                  },
                ),
                const Divider(),
                ListTile(
                  leading: Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.blue.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.cloud_outlined, color: Colors.blue),
                  ),
                  title: const Text('Event Documents / Drive Storage'),
                  subtitle: const Text('Select a poster uploaded in one of your event folders'),
                  onTap: () {
                    Navigator.of(ctx).pop();
                    _showDriveImagePickerDialog();
                  },
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _analyzeAndAutoFillPoster() async {
    if (_referencePosterBytes == null && _referencePosterDocId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please attach a poster image first.')),
      );
      return;
    }
    setState(() => _isAnalyzingPoster = true);
    try {
      final res = await widget.docService.analyzePoster(
        reportId: _currentReportId,
        imageBytes: _referencePosterBytes,
        fileName: _referencePosterName,
        documentId: _referencePosterDocId,
        provider: _selectedProvider,
        model: _selectedModel,
      );
      final extracted = res['extracted_data'] as Map<String, dynamic>?;
      if (extracted != null && extracted.isNotEmpty) {
        setState(() {
          _extractedPosterContext = extracted;
        });
        if (mounted) {
          _showExtractedContextReviewDialog(extracted);
        }
      } else if (res['notice'] != null) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Notice: ${res['notice']}')),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to analyze poster: $e'), backgroundColor: AppConstants.dangerRed),
        );
      }
    } finally {
      if (mounted) setState(() => _isAnalyzingPoster = false);
    }
  }

  void _showExtractedContextReviewDialog(Map<String, dynamic> extracted) {
    showDialog(
      context: context,
      builder: (ctx) {
        final title = extracted['title_of_activity']?.toString() ?? '';
        final type = extracted['type_of_activity']?.toString() ?? '';
        final date = extracted['date']?.toString() ?? '';
        final time = extracted['time']?.toString() ?? '';
        final venue = extracted['venue']?.toString() ?? '';
        final collaborators = extracted['collaborators']?.toString() ?? '';
        final summary = extracted['summary']?.toString() ?? '';
        final highlights = extracted['highlights']?.toString() ?? '';
        final keyTakeaways = extracted['key_takeaways']?.toString() ?? '';
        final speakerProfile = extracted['speaker_profile']?.toString() ?? '';
        final speakers = (extracted['speakers'] as List<dynamic>?) ?? [];

        return AlertDialog(
          title: const Row(
            children: [
              Icon(Icons.auto_awesome, color: Colors.purple),
              SizedBox(width: 8),
              Expanded(child: Text('AI Extracted Poster Context')),
            ],
          ),
          content: SizedBox(
            width: 550,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'The AI inspected your poster and extracted the following details. Applying will populate your report fields automatically:',
                    style: TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                  ),
                  const SizedBox(height: 14),
                  if (title.isNotEmpty) _previewField('Title', title),
                  if (type.isNotEmpty) _previewField('Type', type),
                  if (date.isNotEmpty || time.isNotEmpty)
                    _previewField('Date & Time', '$date ${time.isNotEmpty ? "• $time" : ""}'),
                  if (venue.isNotEmpty) _previewField('Venue', venue),
                  if (collaborators.isNotEmpty) _previewField('Collaborators', collaborators),
                  if (speakers.isNotEmpty)
                    _previewField(
                      'Resource Person(s)',
                      speakers.map((s) {
                        if (s is Map) {
                          final n = s['name'] ?? '';
                          final t = s['title'] ?? '';
                          final o = s['organization'] ?? '';
                          return '$n ${t.isNotEmpty ? "($t)" : ""} ${o.isNotEmpty ? "- $o" : ""}';
                        }
                        return s.toString();
                      }).join('\n'),
                    ),
                  if (summary.isNotEmpty) _previewField('Summary', summary),
                  if (highlights.isNotEmpty) _previewField('Highlights', highlights),
                  if (keyTakeaways.isNotEmpty) _previewField('Key Takeaways', keyTakeaways),
                  if (speakerProfile.isNotEmpty) _previewField('Speaker Profile', speakerProfile),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('Cancel'),
            ),
            ElevatedButton.icon(
              icon: const Icon(Icons.check, size: 16),
              label: const Text('Apply to Report Form'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppConstants.pureBlack,
                foregroundColor: Colors.white,
              ),
              onPressed: () {
                Navigator.of(ctx).pop();
                setState(() {
                  if (title.isNotEmpty) _titleController.text = title;
                  if (type.isNotEmpty && _activityTypes.contains(type)) {
                    _activityTypeController.text = type;
                  }
                  if (date.isNotEmpty) _dateController.text = date;
                  if (time.isNotEmpty) _timeController.text = time;
                  if (venue.isNotEmpty) _venueController.text = venue;
                  if (collaborators.isNotEmpty) _collaboratorsController.text = collaborators;
                  if (summary.isNotEmpty) _summaryController.text = summary;
                  if (highlights.isNotEmpty) _highlightsController.text = highlights;
                  if (keyTakeaways.isNotEmpty) _keyTakeawaysController.text = keyTakeaways;
                  if (speakerProfile.isNotEmpty) _speakerProfileController.text = speakerProfile;

                  if (speakers.isNotEmpty) {
                    _speakers.clear();
                    for (var s in speakers) {
                      if (s is Map) {
                        _speakers.add(SpeakerEntry(
                          name: s['name']?.toString() ?? '',
                          title: s['title']?.toString() ?? '',
                          organization: s['organization']?.toString() ?? '',
                          contact: s['contact']?.toString() ?? '',
                        ));
                      }
                    }
                    if (_speakers.isEmpty) _speakers.add(SpeakerEntry());
                  }
                });

                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('✨ Report form populated from poster context!'),
                    backgroundColor: AppConstants.successGreen,
                  ),
                );
              },
            ),
          ],
        );
      },
    );
  }

  Widget _previewField(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8.0),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: Colors.grey.withValues(alpha: 0.06),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.indigo)),
            const SizedBox(height: 2),
            Text(value, style: const TextStyle(fontSize: 12)),
          ],
        ),
      ),
    );
  }

  void _showPosterImagePreviewDialog() {
    if (_referencePosterBytes == null) return;
    showDialog(
      context: context,
      builder: (ctx) {
        return Dialog(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              AppBar(
                title: Text(_referencePosterName ?? 'Event Poster Preview'),
                automaticallyImplyLeading: false,
                actions: [
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.of(ctx).pop(),
                  ),
                ],
              ),
              InteractiveViewer(
                child: Image.memory(
                  _referencePosterBytes!,
                  fit: BoxFit.contain,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildReferencePosterBanner() {
    final hasPoster = _referencePosterBytes != null || _referencePosterDocId != null;

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: hasPoster ? Colors.indigo.withValues(alpha: 0.3) : AppConstants.borderLight,
        ),
      ),
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
                    color: Colors.indigo.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.image_search_outlined, color: Colors.indigo),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Event Poster & Reference Material',
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        hasPoster
                            ? 'Multimodal AI can read your poster to auto-fill event fields and provide contextual answers.'
                            : 'Upload or pick an event flyer to auto-fill the form and supply visual context to AI.',
                        style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                      ),
                    ],
                  ),
                ),
                if (hasPoster)
                  IconButton(
                    tooltip: 'Change Poster',
                    icon: const Icon(Icons.swap_horiz),
                    onPressed: _showPosterUploadSourceDialog,
                  ),
              ],
            ),
            const SizedBox(height: 14),
            if (!hasPoster) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 16),
                decoration: BoxDecoration(
                  color: Colors.grey.withValues(alpha: 0.04),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: Colors.grey.withValues(alpha: 0.25),
                  ),
                ),
                child: Column(
                  children: [
                    const Icon(Icons.cloud_upload_outlined, size: 36, color: Colors.indigo),
                    const SizedBox(height: 8),
                    const Text(
                      'Attach Event Poster (PNG, JPG, WEBP)',
                      style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      'Drag & drop or choose your storage source below:',
                      style: TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                    ),
                    const SizedBox(height: 14),
                    Wrap(
                      spacing: 12,
                      runSpacing: 8,
                      alignment: WrapAlignment.center,
                      children: [
                        ElevatedButton.icon(
                          icon: const Icon(Icons.computer, size: 16),
                          label: const Text('Open Local Storage / Files'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.indigo,
                            foregroundColor: Colors.white,
                          ),
                          onPressed: _pickLocalPoster,
                        ),
                        OutlinedButton.icon(
                          icon: const Icon(Icons.cloud_outlined, size: 16),
                          label: const Text('Open Drive / Event Documents'),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: Colors.indigo,
                          ),
                          onPressed: _showDriveImagePickerDialog,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ] else ...[
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.indigo.withValues(alpha: 0.04),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.indigo.withValues(alpha: 0.2)),
                ),
                child: Column(
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        GestureDetector(
                          onTap: _showPosterImagePreviewDialog,
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(8),
                            child: Container(
                              width: 80,
                              height: 80,
                              color: Colors.grey[200],
                              child: _referencePosterBytes != null
                                  ? Image.memory(
                                      _referencePosterBytes!,
                                      fit: BoxFit.cover,
                                    )
                                  : const Icon(Icons.image, size: 40, color: Colors.grey),
                            ),
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                _referencePosterName ?? 'Official Poster',
                                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                              const SizedBox(height: 4),
                              Row(
                                children: [
                                  Chip(
                                    avatar: const Icon(Icons.check_circle, size: 14, color: Colors.green),
                                    label: Text(
                                      _referencePosterSource == 'drive' ? 'Drive Storage' : 'Local Storage',
                                      style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold),
                                    ),
                                    visualDensity: VisualDensity.compact,
                                    padding: EdgeInsets.zero,
                                  ),
                                  const SizedBox(width: 8),
                                  if (_extractedPosterContext != null)
                                    const Chip(
                                      avatar: Icon(Icons.auto_awesome, size: 14, color: Colors.purple),
                                      label: Text('Context Extracted', style: TextStyle(fontSize: 10, color: Colors.purple)),
                                      visualDensity: VisualDensity.compact,
                                      padding: EdgeInsets.zero,
                                    ),
                                ],
                              ),
                              const SizedBox(height: 6),
                              Text(
                                'Click image to preview fullscreen or auto-fill below.',
                                style: TextStyle(fontSize: 11, color: Colors.grey[600]),
                              ),
                            ],
                          ),
                        ),
                        IconButton(
                          tooltip: 'Remove Poster',
                          icon: const Icon(Icons.close, size: 18, color: Colors.red),
                          onPressed: () {
                            setState(() {
                              _referencePosterBytes = null;
                              _referencePosterName = null;
                              _referencePosterDocId = null;
                              _extractedPosterContext = null;
                              _posterPath = null;
                            });
                          },
                        ),
                      ],
                    ),
                    const Divider(height: 20),
                    Row(
                      children: [
                        Expanded(
                          child: PrimaryButton(
                            label: _isAnalyzingPoster ? 'Reading Poster with AI...' : 'Auto-Fill Report from Poster (AI)',
                            icon: Icons.auto_awesome,
                            isLoading: _isAnalyzingPoster,
                            onPressed: _isAnalyzingPoster ? null : _analyzeAndAutoFillPoster,
                          ),
                        ),
                        const SizedBox(width: 10),
                        SecondaryButton(
                          label: 'Preview',
                          icon: Icons.fullscreen,
                          onPressed: _showPosterImagePreviewDialog,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Build Methods
  // ---------------------------------------------------------------------------
  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Activity Report Editor')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (_errorMessage != null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Activity Report Editor')),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_errorMessage!, style: const TextStyle(color: AppConstants.dangerRed)),
              const SizedBox(height: 16),
              PrimaryButton(
                label: 'Retry',
                width: 120,
                onPressed: _loadReport,
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _titleController.text.trim().isNotEmpty
                  ? _titleController.text.trim()
                  : 'Activity Report Editor',
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const Text(
              'Official CUestIC Institutional Template Format',
              style: TextStyle(fontSize: 12, color: AppConstants.textSecondary),
            ),
          ],
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 8.0),
            child: Chip(
              label: Text(
                _reportStatus.toUpperCase(),
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  color: _reportStatus == 'generated'
                      ? AppConstants.successGreen
                      : AppConstants.warningOrange,
                ),
              ),
              backgroundColor: _reportStatus == 'generated'
                  ? AppConstants.successGreen.withValues(alpha: 0.1)
                  : AppConstants.warningOrange.withValues(alpha: 0.1),
              side: BorderSide.none,
              padding: EdgeInsets.zero,
            ),
          ),
          IconButton(
            tooltip: 'Save Draft',
            icon: _isSaving
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.save_outlined),
            onPressed: _isSaving ? null : () => _saveDraft(),
          ),
          IconButton(
            tooltip: 'Save to Event Folder',
            icon: const Icon(Icons.drive_folder_upload_outlined),
            onPressed: _showSaveToFolderDialog,
          ),
          IconButton(
            tooltip: 'Download Official .docx',
            icon: _isGenerating
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.download_outlined),
            onPressed: _isGenerating ? null : _generateAndDownloadDocx,
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final isWide = constraints.maxWidth >= 900;
          if (isWide) {
            return Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Left Panel: AI Copilot
                SizedBox(
                  width: 380,
                  child: Container(
                    decoration: const BoxDecoration(
                      border: Border(right: BorderSide(color: AppConstants.borderLight, width: 1)),
                      color: AppConstants.backgroundLight,
                    ),
                    child: _buildAiCopilotPanel(),
                  ),
                ),
                // Right Panel: Form
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(24.0),
                    child: _buildFormSections(),
                  ),
                ),
              ],
            );
          } else {
            // Narrow mobile screen: Stack with form and floating Copilot modal
            return SingleChildScrollView(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                children: [
                  _buildMobileAiCopilotCard(),
                  const SizedBox(height: 16),
                  _buildFormSections(),
                ],
              ),
            );
          }
        },
      ),
      bottomNavigationBar: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: const BoxDecoration(
          color: AppConstants.pureWhite,
          border: Border(top: BorderSide(color: AppConstants.borderLight)),
        ),
        child: SafeArea(
          child: Row(
            children: [
              Expanded(
                child: SecondaryButton(
                  label: _isSaving ? 'Saving...' : 'Save Draft',
                  icon: Icons.save_outlined,
                  isLoading: _isSaving,
                  onPressed: () => _saveDraft(),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                flex: 2,
                child: PrimaryButton(
                  label: _isGenerating ? 'Generating DOCX...' : 'Generate Official Report (.docx)',
                  icon: Icons.description_outlined,
                  isLoading: _isGenerating,
                  onPressed: _generateAndDownloadDocx,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // AI Copilot Panel UI
  // ---------------------------------------------------------------------------
  Widget _buildAiCopilotPanel() {
    return ListView(
      padding: const EdgeInsets.all(16.0),
      children: [
        Row(
          children: [
            const Icon(Icons.auto_awesome, color: Colors.purple, size: 20),
            const SizedBox(width: 8),
            const Expanded(
              child: Text(
                'AI Report Copilot',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (_aiProviderName != null)
              Chip(
                label: Text(
                  _aiProviderName!,
                  style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w600),
                ),
                visualDensity: VisualDensity.compact,
                padding: EdgeInsets.zero,
              ),
          ],
        ),
        const SizedBox(height: 8),
        const Text(
          'Targeting official academic writing standards. Content dynamically populates your selected form section.',
          style: TextStyle(fontSize: 12, color: AppConstants.textSecondary),
        ),
        const SizedBox(height: 16),
        // Active Target Indicator
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: Colors.purple.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: Colors.purple.withValues(alpha: 0.2)),
          ),
          child: Row(
            children: [
              const Icon(Icons.gps_fixed, size: 16, color: Colors.purple),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Active Target Field', style: TextStyle(fontSize: 10, color: Colors.purple)),
                    Text(
                      _activeFieldLabel,
                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        _buildModelSelector(),
        const SizedBox(height: 14),
        // Reference Poster Context Status
        if (_referencePosterBytes != null || _referencePosterDocId != null) ...[
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.green.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.green.withValues(alpha: 0.25)),
            ),
            child: Row(
              children: [
                const Icon(Icons.photo_outlined, size: 16, color: Colors.green),
                const SizedBox(width: 8),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Poster Context Active',
                        style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.green),
                      ),
                      Text(
                        _referencePosterName ?? 'Attached Image',
                        style: const TextStyle(fontSize: 11),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
                Switch(
                  value: _includePosterContextInAi,
                  activeThumbColor: Colors.green,
                  onChanged: (val) => setState(() => _includePosterContextInAi = val),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
        ] else ...[
          OutlinedButton.icon(
            icon: const Icon(Icons.add_photo_alternate_outlined, size: 16),
            label: const Text('Add Poster for AI Context', style: TextStyle(fontSize: 11)),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
              foregroundColor: Colors.indigo,
            ),
            onPressed: _showPosterUploadSourceDialog,
          ),
          const SizedBox(height: 14),
        ],
        const Text('Quick Actions', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: [
            _actionChip('Draft Content', 'draft'),
            _actionChip('Improve & Polish', 'improve'),
            _actionChip('Expand Details', 'expand'),
            _actionChip('Summarize', 'summarize'),
            _actionChip('Formal Academic', 'formalize'),
          ],
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _aiInstructionController,
          maxLines: 3,
          style: const TextStyle(fontSize: 13),
          decoration: InputDecoration(
            labelText: 'Custom Instruction (Optional)',
            hintText: 'e.g. Highlight hands-on coding demos and student engagement...',
            alignLabelWithHint: true,
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
            contentPadding: const EdgeInsets.all(12),
          ),
        ),
        const SizedBox(height: 12),
        PrimaryButton(
          label: _isAiBusy ? 'Generating with AI...' : 'Generate / Polish Content',
          icon: Icons.auto_awesome,
          isLoading: _isAiBusy,
          onPressed: _isAiBusy ? null : () => _runAiCopilot(action: 'draft'),
        ),
        const SizedBox(height: 20),
        if (_aiGeneratedText != null) ...[
          const Text('Copilot Output', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppConstants.pureWhite,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppConstants.borderLight),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SelectableText(
                  _aiGeneratedText!,
                  style: const TextStyle(fontSize: 13, height: 1.4),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: SecondaryButton(
                        height: 36,
                        label: 'Copy',
                        icon: Icons.copy,
                        onPressed: () {
                          Clipboard.setData(ClipboardData(text: _aiGeneratedText!));
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Copied to clipboard.')),
                          );
                        },
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.purple,
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                          minimumSize: const Size(0, 36),
                        ),
                        icon: const Icon(Icons.input, size: 16),
                        label: const Text('Insert', style: TextStyle(fontSize: 12)),
                        onPressed: _insertAiTextIntoField,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildMobileAiCopilotCard() {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: BorderSide(color: Colors.purple.withValues(alpha: 0.3)),
      ),
      color: Colors.purple.withValues(alpha: 0.04),
      child: ExpansionTile(
        initiallyExpanded: false,
        leading: const Icon(Icons.auto_awesome, color: Colors.purple),
        title: Text(
          'AI Copilot (Active: $_activeFieldLabel)',
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
        ),
        children: [
          Padding(
            padding: const EdgeInsets.all(12.0),
            child: Column(
              children: [
                _buildModelSelector(),
                const SizedBox(height: 10),
                if (_referencePosterBytes != null || _referencePosterDocId != null) ...[
                  Row(
                    children: [
                      const Icon(Icons.check_circle, size: 14, color: Colors.green),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          'Using context from: ${_referencePosterName ?? "Poster"}',
                          style: const TextStyle(fontSize: 11, color: Colors.green, fontWeight: FontWeight.w600),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      Switch(
                        value: _includePosterContextInAi,
                        activeThumbColor: Colors.green,
                        onChanged: (val) => setState(() => _includePosterContextInAi = val),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                ],
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    _actionChip('Draft Content', 'draft'),
                    _actionChip('Improve & Polish', 'improve'),
                    _actionChip('Expand Details', 'expand'),
                  ],
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _aiInstructionController,
                  maxLines: 2,
                  style: const TextStyle(fontSize: 13),
                  decoration: const InputDecoration(
                    labelText: 'Prompt / Instruction',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 8),
                PrimaryButton(
                  height: 40,
                  label: _isAiBusy ? 'Generating...' : 'Generate for $_activeFieldLabel',
                  icon: Icons.auto_awesome,
                  isLoading: _isAiBusy,
                  onPressed: _isAiBusy ? null : () => _runAiCopilot(action: 'draft'),
                ),
                if (_aiGeneratedText != null) ...[
                  const SizedBox(height: 12),
                  SelectableText(_aiGeneratedText!, style: const TextStyle(fontSize: 13)),
                  const SizedBox(height: 8),
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.purple,
                      foregroundColor: Colors.white,
                    ),
                    icon: const Icon(Icons.input),
                    label: const Text('Insert into Active Field'),
                    onPressed: _insertAiTextIntoField,
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildModelSelector() {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppConstants.pureWhite,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppConstants.borderLight),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.tune, size: 14, color: AppConstants.textSecondary),
              SizedBox(width: 6),
              Text(
                'AI Model Engine',
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppConstants.textSecondary),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: _availableModels.isNotEmpty
                ? _availableModels.map((m) {
                    final p = m['provider']?.toString() ?? 'gemini';
                    final isGemini = p == 'gemini';
                    return Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 4.0),
                        child: _modelSelectCard(
                          title: m['name']?.toString() ?? (isGemini ? 'Gemini 3.5 Flash' : 'Grok / Groq LPU'),
                          providerKey: p,
                          modelKey: m['model']?.toString() ?? (isGemini ? 'gemini-3.5-flash' : 'qwen/qwen3.8-27b'),
                          icon: isGemini ? Icons.auto_awesome : Icons.bolt,
                          color: isGemini ? Colors.blue.shade700 : Colors.deepOrange.shade600,
                        ),
                      ),
                    );
                  }).toList()
                : [
                    Expanded(
                      child: _modelSelectCard(
                        title: 'Gemini 3.5 Flash',
                        providerKey: 'gemini',
                        modelKey: 'gemini-3.5-flash',
                        icon: Icons.auto_awesome,
                        color: Colors.blue.shade700,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: _modelSelectCard(
                        title: 'Grok / Groq LPU',
                        providerKey: 'grok',
                        modelKey: 'qwen/qwen3.8-27b',
                        icon: Icons.bolt,
                        color: Colors.deepOrange.shade600,
                      ),
                    ),
                  ],
          ),
        ],
      ),
    );
  }

  Widget _modelSelectCard({
    required String title,
    required String providerKey,
    required String modelKey,
    required IconData icon,
    required Color color,
  }) {
    final isSelected = _selectedProvider == providerKey;
    return InkWell(
      borderRadius: BorderRadius.circular(6),
      onTap: () {
        setState(() {
          _selectedProvider = providerKey;
          _selectedModel = modelKey;
        });
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? color.withValues(alpha: 0.12) : AppConstants.backgroundLight,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(
            color: isSelected ? color : AppConstants.borderLight,
            width: isSelected ? 1.5 : 1.0,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 14, color: isSelected ? color : AppConstants.textSecondary),
            const SizedBox(width: 6),
            Flexible(
              child: Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                  color: isSelected ? color : AppConstants.pureBlack,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _actionChip(String label, String action) {
    return ActionChip(
      label: Text(label, style: const TextStyle(fontSize: 11)),
      avatar: const Icon(Icons.auto_fix_high, size: 14),
      onPressed: _isAiBusy ? null : () => _runAiCopilot(action: action),
      visualDensity: VisualDensity.compact,
    );
  }

  // ---------------------------------------------------------------------------
  // Section-Based Form UI
  // ---------------------------------------------------------------------------
  Widget _buildFormSections() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildReferencePosterBanner(),
        const SizedBox(height: 20),
        // Section 1: General Info
        _buildSectionHeader('1. General Information', Icons.info_outline),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                DropdownButtonFormField<String>(
                  initialValue: _activityTypes.contains(_activityTypeController.text)
                      ? _activityTypeController.text
                      : 'Workshop',
                  decoration: const InputDecoration(
                    labelText: 'Type of Activity *',
                    border: OutlineInputBorder(),
                  ),
                  items: _activityTypes
                      .map((t) => DropdownMenuItem(value: t, child: Text(t)))
                      .toList(),
                  onChanged: (val) {
                    if (val != null) setState(() => _activityTypeController.text = val);
                  },
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _titleController,
                  decoration: const InputDecoration(
                    labelText: 'Title of the Activity *',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _dateController,
                        decoration: const InputDecoration(
                          labelText: 'Date(s) of Activity *',
                          hintText: 'DD-MM-YYYY or Range',
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextFormField(
                        controller: _timeController,
                        decoration: const InputDecoration(
                          labelText: 'Time *',
                          hintText: 'e.g. 10:00 AM - 1:00 PM',
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _venueController,
                  decoration: const InputDecoration(
                    labelText: 'Venue *',
                    hintText: 'e.g. Block 2 Auditorium, Central Campus',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _collaboratorsController,
                  decoration: const InputDecoration(
                    labelText: 'Collaborating Departments / Bodies (if any)',
                    hintText: 'e.g. IEEE Student Branch & CUestIC',
                    border: OutlineInputBorder(),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 24),

        // Section 2: Speaker Details (Dynamic!)
        Wrap(
          alignment: WrapAlignment.spaceBetween,
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: 8,
          runSpacing: 4,
          children: [
            _buildSectionHeader('2. Speaker Details', Icons.record_voice_over_outlined),
            TextButton.icon(
              icon: const Icon(Icons.add, size: 16),
              label: const Text('Add Another Speaker'),
              onPressed: () {
                setState(() {
                  _speakers.add(SpeakerEntry());
                });
              },
            ),
          ],
        ),
        const SizedBox(height: 8),
        ..._speakers.asMap().entries.map((entry) {
          final index = entry.key;
          final speaker = entry.value;
          return Card(
            margin: const EdgeInsets.only(bottom: 12),
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'Speaker #${index + 1}',
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                      ),
                      if (_speakers.length > 1)
                        IconButton(
                          icon: const Icon(Icons.delete_outline, color: AppConstants.dangerRed, size: 20),
                          tooltip: 'Remove Speaker',
                          onPressed: () {
                            setState(() {
                              _speakers.removeAt(index);
                            });
                          },
                        ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: TextFormField(
                          initialValue: speaker.name,
                          decoration: const InputDecoration(
                            labelText: 'Speaker Name *',
                            border: OutlineInputBorder(),
                          ),
                          onChanged: (val) => speaker.name = val,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: TextFormField(
                          initialValue: speaker.title,
                          decoration: const InputDecoration(
                            labelText: 'Title / Designation *',
                            border: OutlineInputBorder(),
                          ),
                          onChanged: (val) => speaker.title = val,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: TextFormField(
                          initialValue: speaker.organization,
                          decoration: const InputDecoration(
                            labelText: 'Organization / Institution *',
                            border: OutlineInputBorder(),
                          ),
                          onChanged: (val) => speaker.organization = val,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: TextFormField(
                          initialValue: speaker.contact,
                          decoration: const InputDecoration(
                            labelText: 'Contact (Email / Phone)',
                            border: OutlineInputBorder(),
                          ),
                          onChanged: (val) => speaker.contact = val,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          );
        }),
        const SizedBox(height: 24),

        // Section 3: Participants Profile & Content Narrative
        _buildSectionHeader('3. Participants & Activity Narrative', Icons.groups_outlined),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextFormField(
                  controller: _participantsTypeController,
                  decoration: const InputDecoration(
                    labelText: 'Type of Participants *',
                    hintText: 'e.g. UG / PG Students & Faculty Members',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 20),
                _buildFieldWithAiTarget(
                  title: 'Highlights of the Activity',
                  fieldKey: 'highlights',
                  controller: _highlightsController,
                  hint: 'Key milestones, guest welcome, live demonstrations...',
                  minLines: 3,
                ),
                const SizedBox(height: 20),
                _buildFieldWithAiTarget(
                  title: 'Summary of the Activity (Master Template Table 4)',
                  fieldKey: 'summary',
                  controller: _summaryController,
                  hint: 'In-depth narrative of proceedings from start to finish...',
                  minLines: 6,
                ),
                const SizedBox(height: 20),
                _buildFieldWithAiTarget(
                  title: 'Key Takeaways',
                  fieldKey: 'key_takeaways',
                  controller: _keyTakeawaysController,
                  hint: 'Major outcomes, skills gained, and practical student learning...',
                  minLines: 3,
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 24),

        // Section 4: Speaker Profile & Organiser Details
        _buildSectionHeader('4. Speaker Profile & Organiser Verification', Icons.badge_outlined),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildFieldWithAiTarget(
                  title: 'Speaker Profile (Bio)',
                  fieldKey: 'speaker_profile',
                  controller: _speakerProfileController,
                  hint: 'Brief professional background, expertise, and accolades of the speaker(s)...',
                  minLines: 3,
                ),
                const SizedBox(height: 20),
                const Text(
                  'Report Prepared By (Faculty / Student Organiser)',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _organiserNameController,
                        decoration: const InputDecoration(
                          labelText: 'Organiser Name *',
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextFormField(
                        controller: _organiserDesignationController,
                        decoration: const InputDecoration(
                          labelText: 'Designation *',
                          hintText: 'e.g. Faculty Coordinator / Documentation Lead',
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 24),

        // Section 5: Annexures (Photos, Attendance >10 pages, Poster)
        _buildSectionHeader('5. Annexures & Verification Documents', Icons.attach_file),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Attach photos, attendance sheets (>10 pages supported with page breaks), and event posters to strictly populate official template annexures.',
                  style: TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                ),
                const SizedBox(height: 16),

                // Photos Picker
                Wrap(
                  alignment: WrapAlignment.spaceBetween,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 8,
                  runSpacing: 4,
                  children: [
                    Text('Activity Photos (${_photoPaths.length} selected)',
                        style: const TextStyle(fontWeight: FontWeight.bold)),
                    TextButton.icon(
                      icon: const Icon(Icons.add_a_photo_outlined, size: 16),
                      label: const Text('Add Photos'),
                      onPressed: () async {
                        final files = await FilePicker.pickFiles(
                          type: FileType.image,
                        );
                        if (files.isNotEmpty) {
                          setState(() {
                            for (var file in files) {
                              if (file.path != null) {
                                _photoPaths.add(file.path!);
                              } else if (file.name.isNotEmpty) {
                                _photoPaths.add(file.name);
                              }
                            }
                          });
                        }
                      },
                    ),
                  ],
                ),
                if (_photoPaths.isNotEmpty)
                  Wrap(
                    spacing: 8,
                    children: _photoPaths.asMap().entries.map((entry) {
                      return Chip(
                        label: Text('Photo #${entry.key + 1}', style: const TextStyle(fontSize: 11)),
                        onDeleted: () {
                          setState(() => _photoPaths.removeAt(entry.key));
                        },
                      );
                    }).toList(),
                  ),
                const Divider(height: 32),

                // Attendance Sheets Picker (>10 pages)
                Wrap(
                  alignment: WrapAlignment.spaceBetween,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 8,
                  runSpacing: 4,
                  children: [
                    Text('Attendance Sheets (${_attendancePaths.length} pages)',
                        style: const TextStyle(fontWeight: FontWeight.bold)),
                    TextButton.icon(
                      icon: const Icon(Icons.post_add_outlined, size: 16),
                      label: const Text('Add Pages (>10 Pages)'),
                      onPressed: () async {
                        final files = await FilePicker.pickFiles(
                          type: FileType.image,
                        );
                        if (files.isNotEmpty) {
                          setState(() {
                            for (var file in files) {
                              if (file.path != null) {
                                _attendancePaths.add(file.path!);
                              } else if (file.name.isNotEmpty) {
                                _attendancePaths.add(file.name);
                              }
                            }
                          });
                        }
                      },
                    ),
                  ],
                ),
                if (_attendancePaths.isNotEmpty)
                  Wrap(
                    spacing: 8,
                    children: _attendancePaths.asMap().entries.map((entry) {
                      return Chip(
                        label: Text('Sheet Page #${entry.key + 1}', style: const TextStyle(fontSize: 11)),
                        onDeleted: () {
                          setState(() => _attendancePaths.removeAt(entry.key));
                        },
                      );
                    }).toList(),
                  ),
                const Divider(height: 32),

                // Poster Picker
                Wrap(
                  alignment: WrapAlignment.spaceBetween,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 8,
                  runSpacing: 4,
                  children: [
                    Text(_posterPath != null ? 'Event Poster Selected' : 'Event Poster / Flyer',
                        style: const TextStyle(fontWeight: FontWeight.bold)),
                    TextButton.icon(
                      icon: const Icon(Icons.image_outlined, size: 16),
                      label: Text(_posterPath != null ? 'Change Poster' : 'Attach Poster'),
                      onPressed: _showPosterUploadSourceDialog,
                    ),
                  ],
                ),
                if (_posterPath != null)
                  Chip(
                    avatar: const Icon(Icons.check_circle, size: 14, color: Colors.green),
                    label: Text('Attached: ${_referencePosterName ?? _posterPath}', style: const TextStyle(fontSize: 11)),
                    onDeleted: () {
                      setState(() {
                        _posterPath = null;
                        _referencePosterBytes = null;
                        _referencePosterName = null;
                        _referencePosterDocId = null;
                        _extractedPosterContext = null;
                      });
                    },
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 24),

        // Section 6: Impact & Feedback Analysis
        _buildSectionHeader('6. Feedback & Impact Analysis', Icons.analytics_outlined),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: _buildFieldWithAiTarget(
              title: 'Impact Analysis (Master Template Section 7)',
              fieldKey: 'impact_analysis',
              controller: _impactAnalysisController,
              hint: 'Summarize post-session survey metrics, participant satisfaction, learning efficacy...',
              minLines: 4,
            ),
          ),
        ),
        const SizedBox(height: 48),
      ],
    );
  }

  Widget _buildFieldWithAiTarget({
    required String title,
    required String fieldKey,
    required TextEditingController controller,
    required String hint,
    int minLines = 3,
  }) {
    final isSelected = _activeFieldKey == fieldKey;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Expanded(
              child: Text(
                title,
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
              ),
            ),
            InkWell(
              borderRadius: BorderRadius.circular(4),
              onTap: () => _setActiveField(key: fieldKey, label: title, controller: controller),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: isSelected
                      ? Colors.purple.withValues(alpha: 0.15)
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(
                    color: isSelected ? Colors.purple : AppConstants.borderLight,
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      isSelected ? Icons.check_circle : Icons.auto_awesome,
                      size: 14,
                      color: isSelected ? Colors.purple : AppConstants.textSecondary,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      isSelected ? 'Copilot Target' : 'Send to Copilot',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                        color: isSelected ? Colors.purple : AppConstants.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        TextFormField(
          controller: controller,
          maxLines: null,
          minLines: minLines,
          style: const TextStyle(fontSize: 14, height: 1.4),
          decoration: InputDecoration(
            hintText: hint,
            alignLabelWithHint: true,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: BorderSide(
                color: isSelected ? Colors.purple : AppConstants.borderLight,
                width: isSelected ? 1.5 : 1.0,
              ),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: const BorderSide(color: Colors.purple, width: 2.0),
            ),
          ),
          onTap: () => _setActiveField(key: fieldKey, label: title, controller: controller),
        ),
      ],
    );
  }

  Widget _buildSectionHeader(String title, IconData icon) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 20, color: AppConstants.pureBlack),
        const SizedBox(width: 8),
        Flexible(
          child: Text(
            title,
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, letterSpacing: -0.2),
          ),
        ),
      ],
    );
  }
}
