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
  final List<String> _photosBase64 = [];
  final List<String> _attendancePaths = [];
  final List<String> _attendanceBase64 = [];
  String? _posterPath;

  // Attendance OCR & Human Verification State
  List<Map<String, dynamic>> _attendanceRecords = [];
  Map<String, dynamic>? _attendanceSummary;
  bool _isProcessingAttendance = false;
  String? _classDistributionChartBase64;

  // Reference Poster & Vision Context
  Uint8List? _referencePosterBytes;
  String? _referencePosterName;
  int? _referencePosterDocId;
  String? _referencePosterSource; // 'local' or 'drive'
  Map<String, dynamic>? _extractedPosterContext;
  bool _isAnalyzingPoster = false;
  bool _includePosterContextInAi = true;

  // Section 6: E-Certificate Upload (Placed BEFORE Impact Analysis)
  String? _certificateFilename;
  String? _certificateBase64;
  Uint8List? _certificateBytes;
  final _certificateCategoryController = TextEditingController(text: 'Participation');
  final _certificateDescriptionController = TextEditingController();
  final _certificatesIssuedController = TextEditingController();
  final _certificateRecipientInfoController = TextEditingController();

  // Section 7: Impact Analysis (12 Configurable Questions)
  final _impactAnalysisController = TextEditingController();
  final List<Map<String, String>> _impactQuestions = [
    {'question': '1. How effectively did the activity address its stated objectives?', 'answer': 'The activity provided structured technical exposure, experiential problem-solving opportunities, and peer collaboration for participating engineering students.'},
    {'question': '2. How many verified participants attended the activity?', 'answer': 'Verified unique participants attended the activity with recorded signatures.'},
    {'question': '3. Which academic classes were represented?', 'answer': 'Participation was recorded across academic cohorts in the department.'},
    {'question': '4. Did the activity provide exposure to the intended technical subject?', 'answer': 'Yes, participants engaged with domain-specific engineering principles, structured problem statements, and real-time execution scenarios.'},
    {'question': '5. Did the activity provide opportunities for knowledge exchange?', 'answer': 'Yes, interactive discussions and group challenges facilitated collaborative knowledge transfer between participants and coordinators.'},
    {'question': '6. Did the activity encourage student engagement?', 'answer': 'High engagement levels were observed throughout the session with active participant questions and competitive execution.'},
    {'question': '7. Did the activity support practical or research-oriented learning?', 'answer': 'Yes, the activity emphasized analytical thinking, deductive reasoning, and hands-on application rather than passive theoretical instruction.'},
    {'question': '8. Did the activity facilitate interaction with speakers or experts?', 'answer': 'Organizers, faculty coordinators, and student leads actively mentored teams during the session.'},
    {'question': '9. Did the activity encourage interdisciplinary collaboration?', 'answer': 'The activity fostered cross-sectional teamwork among students from Electronics and Communication Engineering and associated cohorts.'},
    {'question': '10. Did the activity provide insights into relevant industry or research practices?', 'answer': 'The problem statements reflected industry methodologies requiring agile problem solving, communication, and systematic verification.'},
    {'question': '11. What key outcomes were documented during the activity?', 'answer': 'Documented outcomes include verified participant completion, peer interaction, and positive attainment of relevant engineering program outcomes.'},
    {'question': '12. What follow-up opportunities or improvements were identified?', 'answer': 'Recommended follow-ups include organizing advanced continuation modules and expanding time allocations for complex analytical challenges.'},
  ];

  // Section 8: Feedback Analysis & Program Outcomes (PO1-PO12)
  String? _feedbackFilename;
  List<String> _feedbackHeaders = [];
  List<dynamic> _feedbackRows = [];
  final Map<String, String> _poColumnMapping = {};
  Map<String, dynamic>? _feedbackAnalysisResult;
  bool _isImportingFeedback = false;
  bool _isAnalyzingFeedback = false;
  bool _isGeneratingImpact = false;
  bool _isGeneratingFeedback = false;
  final Map<String, bool> _isRegeneratingPo = {};
  int? _simulatedParticipantCount;
  int _simulationSeed = DateTime.now().millisecondsSinceEpoch;
  final _feedbackAnalysisController = TextEditingController();

  static const Map<String, String> _poDefinitions = {
    'PO1': 'Engineering Knowledge',
    'PO2': 'Problem Analysis',
    'PO3': 'Design/Development of Solutions',
    'PO4': 'Conduct Investigations of Complex Problems',
    'PO5': 'Modern Tool Usage',
    'PO6': 'The Engineer and Society',
    'PO7': 'Environment and Sustainability',
    'PO8': 'Ethics',
    'PO9': 'Individual and Team Work',
    'PO10': 'Communication',
    'PO11': 'Project Management and Finance',
    'PO12': 'Life-long Learning',
  };

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
    _certificateCategoryController.dispose();
    _certificateDescriptionController.dispose();
    _certificatesIssuedController.dispose();
    _certificateRecipientInfoController.dispose();
    _feedbackAnalysisController.dispose();
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
      final photosB64 = annexures['photos_base64'] as List<dynamic>?;
      if (photosB64 != null) {
        _photosBase64.clear();
        _photosBase64.addAll(photosB64.map((e) => e.toString()));
      }
      final attendance = annexures['attendance_sheets'] as List<dynamic>? ?? annexures['attendance_pages'] as List<dynamic>?;
      if (attendance != null) {
        _attendancePaths.clear();
        _attendancePaths.addAll(attendance.map((e) => e.toString()));
      }
      final attendanceB64 = (annexures['attendance_sheets_base64'] as List<dynamic>?) ??
          (annexures['attendance_pages_base64'] as List<dynamic>?);
      if (attendanceB64 != null) {
        _attendanceBase64.clear();
        _attendanceBase64.addAll(attendanceB64.map((e) => e.toString()));
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

      // Attendance Summary & Verified Records
      if (data['attendance_summary'] is Map) {
        _attendanceSummary = Map<String, dynamic>.from(data['attendance_summary'] as Map);
      }
      if (data['attendance_records'] is List) {
        _attendanceRecords = (data['attendance_records'] as List)
            .whereType<Map>()
            .map((e) => Map<String, dynamic>.from(e))
            .toList();
      }
      if (data['class_chart_base64'] != null) {
        _classDistributionChartBase64 = data['class_chart_base64'].toString();
      }

      // Certificate
      final cert = annexures['certificate']?.toString() ??
          annexures['certificate_base64']?.toString() ??
          data['certificate']?.toString();
      if (cert != null && cert.isNotEmpty) {
        _certificateBase64 = cert;
        _certificateFilename = annexures['certificate_filename']?.toString() ?? 'Certificate.png';
      }
      _certificateCategoryController.text = annexures['certificate_category']?.toString() ?? 'Participation';
      _certificatesIssuedController.text = annexures['certificates_issued']?.toString() ?? '';
      _certificateDescriptionController.text = annexures['certificate_description']?.toString() ?? '';
      _certificateRecipientInfoController.text = annexures['certificate_recipient_info']?.toString() ?? '';

      // Impact Questions
      if (data['impact_questions'] is List) {
        final savedQ = (data['impact_questions'] as List)
            .whereType<Map>()
            .map((e) => {
                  'question': e['question']?.toString() ?? e['q']?.toString() ?? '',
                  'answer': e['answer']?.toString() ?? e['a']?.toString() ?? '',
                })
            .where((e) => e['question']!.isNotEmpty)
            .toList();
        if (savedQ.isNotEmpty) {
          _impactQuestions.clear();
          _impactQuestions.addAll(savedQ);
        }
      }

      // Feedback Analysis
      _feedbackAnalysisController.text = data['feedback_analysis']?.toString() ?? '';
      if (data['feedback_data'] is Map<String, dynamic>) {
        _feedbackAnalysisResult = Map<String, dynamic>.from(data['feedback_data'] as Map);
      } else if (data['po_results'] is Map) {
        _feedbackAnalysisResult = {'po_results': Map<String, dynamic>.from(data['po_results'] as Map)};
      }

      if (data['is_simulated'] == true || (data['attendance_summary'] as Map?)?['is_simulated'] == true) {
        _simulatedParticipantCount = data['verified_attendance_count'] as int? ??
            (data['attendance_summary'] as Map?)?['total_verified_unique'] as int?;
      }
      if (data['simulation_seed'] is int) {
        _simulationSeed = data['simulation_seed'] as int;
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
      'attendance_summary': _attendanceSummary,
      'attendance_records': _attendanceRecords,
      'verified_attendance_count': _attendanceSummary?['total_verified_unique'],
      'class_chart_base64': _classDistributionChartBase64,
      'class_distribution': _attendanceSummary?['class_distribution'],
      'certificate': _certificateBase64,
      'impact_analysis': _impactAnalysisController.text.trim(),
      'impact_questions': _impactQuestions,
      'feedback_analysis': _feedbackAnalysisController.text.trim(),
      'po_results': _feedbackAnalysisResult?['po_results'],
      'feedback_data': _feedbackAnalysisResult,
      'is_simulated': _simulatedParticipantCount != null || (_attendanceSummary?['is_simulated'] == true),
      'simulation_seed': _simulationSeed,
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
        'photos_base64': _photosBase64,
        'attendance_sheets': _attendancePaths,
        'attendance_sheets_base64': _attendanceBase64,
        'attendance_pages': _attendancePaths,
        'attendance_pages_base64': _attendanceBase64,
        if (_posterPath != null) 'poster': _posterPath,
        if (_posterPath != null) 'poster_path': _posterPath,
        if (_referencePosterBytes != null) 'poster_base64': base64Encode(_referencePosterBytes!),
        if (_referencePosterDocId != null) 'poster_document_id': _referencePosterDocId,
        if (_referencePosterName != null) 'poster_filename': _referencePosterName,
        if (_certificateBase64 != null) 'certificate': _certificateBase64,
        if (_certificateBase64 != null) 'certificate_base64': _certificateBase64,
        if (_certificateFilename != null) 'certificate_filename': _certificateFilename,
        'certificate_category': _certificateCategoryController.text.trim(),
        'certificates_issued': _certificatesIssuedController.text.trim(),
        'certificate_description': _certificateDescriptionController.text.trim(),
        'certificate_recipient_info': _certificateRecipientInfoController.text.trim(),
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
  // Attendance, Certificate, Impact & Feedback Operations
  // ---------------------------------------------------------------------------
  Future<void> _processAttendanceWithOcr() async {
    if (_attendanceBase64.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please upload at least one attendance sheet before processing.')),
      );
      return;
    }

    setState(() => _isProcessingAttendance = true);

    try {
      final List<Map<String, dynamic>> accumulatedRecords = [];
      Map<String, dynamic>? lastSummary;

      for (int i = 0; i < _attendanceBase64.length; i++) {
        final b64Str = _attendanceBase64[i];
        final cleanB64 = b64Str.contains(',') ? b64Str.split(',').last : b64Str;
        final rawBytes = base64Decode(cleanB64);
        final fname = i < _attendancePaths.length ? _attendancePaths[i] : 'attendance_page_${i + 1}.png';

        final result = await widget.docService.processAttendance(
          fileBytes: rawBytes,
          filename: fname,
          existingRecords: accumulatedRecords,
        );

        if (result['records'] is List) {
          final pageRecords = (result['records'] as List)
              .whereType<Map>()
              .map((e) => Map<String, dynamic>.from(e))
              .toList();
          accumulatedRecords.addAll(pageRecords);
        }
        if (result['summary'] is Map) {
          lastSummary = Map<String, dynamic>.from(result['summary'] as Map);
        }
      }

      setState(() {
        _attendanceRecords = accumulatedRecords;
        _attendanceSummary = lastSummary;
      });

      // Generate class distribution chart
      if (lastSummary != null && lastSummary['class_distribution'] is List) {
        final chartB64 = await widget.docService.generateClassChart(lastSummary['class_distribution'] as List);
        if (chartB64 != null && mounted) {
          setState(() => _classDistributionChartBase64 = chartB64);
        }
      }

      // Auto-update Impact Analysis Questions with verified numbers
      final verifiedCount = lastSummary?['total_verified_unique']?.toString() ?? '0';
      final classDistList = lastSummary?['class_distribution'] as List? ?? [];
      final classNames = classDistList.map((c) => c['class_name']?.toString() ?? '').where((c) => c.isNotEmpty).join(', ');

      setState(() {
        if (_impactQuestions.length >= 3) {
          _impactQuestions[1]['answer'] = '$verifiedCount verified unique participants attended the activity with recorded signatures.';
          _impactQuestions[2]['answer'] = 'Participation was recorded across academic cohorts including ${classNames.isNotEmpty ? classNames : "department cohorts"}.';
        }
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('✅ Attendance verified: $verifiedCount participants counted across ${accumulatedRecords.length} detected rows.'),
            backgroundColor: AppConstants.successGreen,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to process attendance sheet: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _isProcessingAttendance = false);
    }
  }

  Future<void> _toggleRecordSignature(int index) async {
    if (index < 0 || index >= _attendanceRecords.length) return;
    final rec = _attendanceRecords[index];
    final currentSig = rec['signature_detected'] == true;
    final newSig = !currentSig;

    rec['signature_detected'] = newSig;
    rec['confidence'] = 'High';
    if (newSig && rec['status'] != 'Duplicate') {
      rec['status'] = 'Verified';
    } else if (!newSig) {
      rec['status'] = 'Excluded';
    }

    try {
      final res = await widget.docService.verifyAttendance(records: _attendanceRecords);
      if (res['summary'] is Map && mounted) {
        setState(() => _attendanceSummary = Map<String, dynamic>.from(res['summary'] as Map));
      }
    } catch (_) {
      setState(() {});
    }
  }

  void _editRecordRegistrationNumber(int index) {
    if (index < 0 || index >= _attendanceRecords.length) return;
    final rec = _attendanceRecords[index];
    final controller = TextEditingController(text: rec['reg_no']?.toString() ?? '');

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Edit Registration Number'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(
            labelText: 'Registration Number',
            hintText: 'e.g. 2460601',
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              final newReg = controller.text.trim();
              if (newReg.isNotEmpty) {
                rec['reg_no'] = newReg;
                if (newReg.startsWith('2460')) {
                  rec['mapped_class'] = '4BTEC';
                } else if (newReg.startsWith('2462')) {
                  rec['mapped_class'] = '4BTELCS';
                } else if (newReg.startsWith('2360')) {
                  rec['mapped_class'] = '6BTEC';
                } else if (newReg.startsWith('2362')) {
                  rec['mapped_class'] = '6BTELCS';
                } else if (newReg.startsWith('2260')) {
                  rec['mapped_class'] = '8BTEC';
                } else if (newReg.startsWith('2262')) {
                  rec['mapped_class'] = '8BTELCS';
                } else {
                  rec['mapped_class'] = 'Unmapped';
                }

                final res = await widget.docService.verifyAttendance(records: _attendanceRecords);
                if (res['summary'] is Map && mounted) {
                  setState(() => _attendanceSummary = Map<String, dynamic>.from(res['summary'] as Map));
                }
              }
              if (ctx.mounted) Navigator.pop(ctx);
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  Future<void> _excludeRecord(int index) async {
    if (index < 0 || index >= _attendanceRecords.length) return;
    _attendanceRecords[index]['status'] = 'Excluded';
    _attendanceRecords[index]['signature_detected'] = false;
    final res = await widget.docService.verifyAttendance(records: _attendanceRecords);
    if (res['summary'] is Map && mounted) {
      setState(() => _attendanceSummary = Map<String, dynamic>.from(res['summary'] as Map));
    }
  }

  void _addManualAttendanceRecord() {
    final regCtrl = TextEditingController();
    final nameCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Add Participant Record'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: regCtrl, decoration: const InputDecoration(labelText: 'Registration Number', hintText: '2460...')),
            const SizedBox(height: 8),
            TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Student Name')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              final reg = regCtrl.text.trim();
              if (reg.isNotEmpty) {
                String mappedClass = 'Unmapped';
                if (reg.startsWith('2460')) {
                  mappedClass = '4BTEC';
                } else if (reg.startsWith('2462')) {
                  mappedClass = '4BTELCS';
                } else if (reg.startsWith('2360')) {
                  mappedClass = '6BTEC';
                } else if (reg.startsWith('2362')) {
                  mappedClass = '6BTELCS';
                }

                setState(() {
                  _attendanceRecords.add({
                    'reg_no': reg,
                    'student_name': nameCtrl.text.trim(),
                    'signature_detected': true,
                    'confidence': 'High',
                    'status': 'Verified',
                    'mapped_class': mappedClass,
                    'is_duplicate': false,
                    'page_number': 1,
                  });
                });

                final res = await widget.docService.verifyAttendance(records: _attendanceRecords);
                if (res['summary'] is Map && mounted) {
                  setState(() => _attendanceSummary = Map<String, dynamic>.from(res['summary'] as Map));
                }
              }
              if (ctx.mounted) Navigator.pop(ctx);
            },
            child: const Text('Add & Verify'),
          ),
        ],
      ),
    );
  }

  Future<void> _uploadCertificateFile() async {
    try {
      final files = await FilePicker.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf', 'png', 'jpg', 'jpeg'],
      );
      if (files.isNotEmpty) {
        final f = files.first;
        final bytes = await f.readAsBytes();
        final ext = (f.extension ?? 'png').toLowerCase();
        final mime = ext == 'pdf' ? 'application/pdf' : 'image/$ext';
        setState(() {
          _certificateFilename = f.name;
          _certificateBytes = bytes;
          _certificateBase64 = 'data:$mime;base64,${base64Encode(bytes)}';
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to load certificate: $e')));
      }
    }
  }

  Future<void> _importFeedbackFile() async {
    try {
      final files = await FilePicker.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['csv', 'xlsx', 'xls', 'xml'],
      );
      if (files.isEmpty) return;

      setState(() => _isImportingFeedback = true);
      final f = files.first;
      final bytes = await f.readAsBytes();

      final result = await widget.docService.importFeedback(
        fileBytes: bytes,
        filename: f.name,
      );

      final headers = (result['headers'] as List?)?.map((e) => e.toString()).toList() ?? [];
      final rows = (result['rows'] as List?) ?? [];
      final suggested = (result['suggested_mappings'] as Map?)?.map((k, v) => MapEntry(k.toString(), v.toString())) ?? {};

      setState(() {
        _feedbackFilename = f.name;
        _feedbackHeaders = headers;
        _feedbackRows = rows;
        _poColumnMapping.clear();
        _poColumnMapping.addAll(suggested);
        _isImportingFeedback = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('✅ Loaded ${rows.length} feedback responses from ${f.name}.'),
            backgroundColor: AppConstants.successGreen,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isImportingFeedback = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to import feedback file: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _analyzeFeedbackPo() async {
    if (_feedbackRows.isEmpty || _poColumnMapping.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please map at least one PO question before analyzing.')),
      );
      return;
    }

    setState(() => _isAnalyzingFeedback = true);
    try {
      final result = await widget.docService.analyzeFeedback(
        rows: _feedbackRows,
        poColumnMapping: _poColumnMapping,
      );

      setState(() {
        _feedbackAnalysisResult = result;
        if (result['interpretation'] != null && _feedbackAnalysisController.text.trim().isEmpty) {
          _feedbackAnalysisController.text = result['interpretation'].toString();
        }
        _isAnalyzingFeedback = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('📊 Generated Google Forms style pie charts & PO distributions!'),
            backgroundColor: AppConstants.successGreen,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isAnalyzingFeedback = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Feedback analysis failed: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _generateSimulatedImpact() async {
    setState(() => _isGeneratingImpact = true);
    try {
      final title = _titleController.text.trim().isNotEmpty ? _titleController.text.trim() : 'Department Activity';
      final res = await widget.docService.generateSimulatedImpact(
        activityTitle: title,
        seed: _simulationSeed,
      );

      final count = res['participant_count'] as int? ?? 218;
      final classDist = (res['class_distribution'] as List?)?.map((e) => Map<String, dynamic>.from(e as Map)).toList() ?? [];
      final chartB64 = res['class_chart_base64'] as String?;
      final narrative = res['narrative']?.toString() ?? '';
      final questions = (res['questions'] as List?)?.map((e) => {
        'question': e['question']?.toString() ?? '',
        'answer': e['answer']?.toString() ?? '',
      }).toList() ?? [];

      setState(() {
        _simulatedParticipantCount = count;
        _classDistributionChartBase64 = chartB64;
        _impactAnalysisController.text = narrative;
        if (questions.isNotEmpty) {
          _impactQuestions.clear();
          _impactQuestions.addAll(questions);
        }
        _attendanceSummary = {
          'total_rows_detected': count,
          'total_verified_unique': count,
          'class_distribution': classDist,
          'is_simulated': true,
        };
        _isGeneratingImpact = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('✨ Impact Analysis simulated for $count participants across 8 cohorts!'),
            backgroundColor: AppConstants.successGreen,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isGeneratingImpact = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to simulate impact analysis: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _generateSimulatedFeedback() async {
    setState(() => _isGeneratingFeedback = true);
    try {
      final count = _simulatedParticipantCount ?? (_attendanceSummary?['total_verified_unique'] as int?) ?? 224;
      final title = _titleController.text.trim().isNotEmpty ? _titleController.text.trim() : 'Department Activity';
      final res = await widget.docService.generateSimulatedFeedback(
        participantCount: count,
        activityTitle: title,
        seed: _simulationSeed + 1,
      );

      setState(() {
        _feedbackAnalysisResult = res;
        _feedbackAnalysisController.text = res['overall_interpretation']?.toString() ?? '';
        _isGeneratingFeedback = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('📊 Generated all 12 Programme Outcome pie charts & distributions!'),
            backgroundColor: AppConstants.successGreen,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isGeneratingFeedback = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to generate feedback charts: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _regenerateSinglePo(String poId) async {
    setState(() => _isRegeneratingPo[poId] = true);
    try {
      final count = _simulatedParticipantCount ?? (_attendanceSummary?['total_verified_unique'] as int?) ?? 224;
      final res = await widget.docService.generateSimulatedFeedback(
        participantCount: count,
        seed: DateTime.now().millisecondsSinceEpoch,
        poId: poId,
      );

      setState(() {
        if (_feedbackAnalysisResult != null && _feedbackAnalysisResult!['po_results'] is Map) {
          final poMap = Map<String, dynamic>.from(_feedbackAnalysisResult!['po_results'] as Map);
          poMap[poId] = res;
          _feedbackAnalysisResult!['po_results'] = poMap;

          if (_feedbackAnalysisResult!['summary_table'] is List) {
            final sumList = List<Map<String, dynamic>>.from(
              (_feedbackAnalysisResult!['summary_table'] as List).map((x) => Map<String, dynamic>.from(x as Map)),
            );
            for (var i = 0; i < sumList.length; i++) {
              if (sumList[i]['po'] == poId) {
                sumList[i] = {
                  'po': poId,
                  'po_title': res['po_title'],
                  'excellent': res['counts']?['Excellent'] ?? 0,
                  'very_good': res['counts']?['Very Good'] ?? 0,
                  'fair': res['counts']?['Fair'] ?? 0,
                  'satisfactory': res['counts']?['Satisfactory'] ?? 0,
                  'total': count,
                  'positive_pct': res['positive_percentage'] ?? 0,
                };
                break;
              }
            }
            _feedbackAnalysisResult!['summary_table'] = sumList;
          }
        }
        _isRegeneratingPo[poId] = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('✨ Regenerated $poId chart and ratings!'),
            backgroundColor: AppConstants.successGreen,
            duration: const Duration(seconds: 2),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isRegeneratingPo[poId] = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to regenerate $poId: $e'), backgroundColor: Colors.red),
        );
      }
    }
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
                        try {
                          final files = await FilePicker.pickFiles(
                            type: FileType.image,
                          );
                          if (files.isNotEmpty) {
                            for (var file in files) {
                              try {
                                final bytes = await file.readAsBytes();
                                final ext = (file.extension ?? 'png').toLowerCase();
                                final b64 = 'data:image/$ext;base64,${base64Encode(bytes)}';
                                setState(() {
                                  _photoPaths.add(file.name);
                                  _photosBase64.add(b64);
                                });
                              } catch (readErr) {
                                setState(() {
                                  if (file.path != null) {
                                    _photoPaths.add(file.path!);
                                  } else {
                                    _photoPaths.add(file.name);
                                  }
                                });
                              }
                            }
                          }
                        } catch (e) {
                          if (mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text('Failed to load photos: $e')),
                            );
                          }
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
                          setState(() {
                            _photoPaths.removeAt(entry.key);
                            if (entry.key < _photosBase64.length) {
                              _photosBase64.removeAt(entry.key);
                            }
                          });
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
                    Wrap(
                      spacing: 8,
                      children: [
                        TextButton.icon(
                          icon: const Icon(Icons.post_add_outlined, size: 16),
                          label: const Text('Add Pages (>10 Pages)'),
                          onPressed: () async {
                            try {
                              final files = await FilePicker.pickFiles(
                                type: FileType.custom,
                                allowedExtensions: ['png', 'jpg', 'jpeg', 'webp', 'pdf'],
                              );
                              if (files.isNotEmpty) {
                                for (var file in files) {
                                  try {
                                    final bytes = await file.readAsBytes();
                                    final ext = (file.extension ?? 'png').toLowerCase();
                                    final isPdf = ext == 'pdf' ||
                                        (bytes.length >= 4 &&
                                            bytes[0] == 0x25 &&
                                            bytes[1] == 0x50 &&
                                            bytes[2] == 0x44 &&
                                            bytes[3] == 0x46);
                                    final mime = isPdf ? 'application/pdf' : 'image/$ext';
                                    final b64 = 'data:$mime;base64,${base64Encode(bytes)}';
                                    setState(() {
                                      _attendancePaths.add(file.name);
                                      _attendanceBase64.add(b64);
                                    });
                                  } catch (readErr) {
                                    setState(() {
                                      if (file.path != null) {
                                        _attendancePaths.add(file.path!);
                                      } else {
                                        _attendancePaths.add(file.name);
                                      }
                                    });
                                  }
                                }
                              }
                            } catch (e) {
                              if (mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(content: Text('Failed to load attendance sheets: $e')),
                                );
                              }
                            }
                          },
                        ),
                        if (_attendanceBase64.isNotEmpty)
                          ElevatedButton.icon(
                            icon: _isProcessingAttendance
                                ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                                : const Icon(Icons.document_scanner_outlined, size: 16),
                            label: Text(_isProcessingAttendance ? 'Extracting...' : 'Process Attendance (AI/OCR)'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.black,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                            ),
                            onPressed: _isProcessingAttendance ? null : _processAttendanceWithOcr,
                          ),
                      ],
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
                          setState(() {
                            _attendancePaths.removeAt(entry.key);
                            if (entry.key < _attendanceBase64.length) {
                              _attendanceBase64.removeAt(entry.key);
                            }
                          });
                        },
                      );
                    }).toList(),
                  ),

                // Attendance Verification UI (When records extracted)
                if (_attendanceSummary != null || _attendanceRecords.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.grey.withValues(alpha: 0.05),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppConstants.borderLight),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text('Verified Attendance Summary', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                            TextButton.icon(
                              icon: const Icon(Icons.person_add_alt_outlined, size: 14),
                              label: const Text('Add Participant', style: TextStyle(fontSize: 11)),
                              onPressed: _addManualAttendanceRecord,
                            ),
                          ],
                        ),
                        const SizedBox(height: 10),
                        Wrap(
                          spacing: 12,
                          runSpacing: 8,
                          children: [
                            _buildStatBadge('Total Detected', '${_attendanceSummary?['total_rows_detected'] ?? _attendanceRecords.length}', Colors.black87),
                            _buildStatBadge('Verified Unique', '${_attendanceSummary?['total_verified_unique'] ?? 0}', Colors.green.shade800),
                            _buildStatBadge('Duplicates', '${_attendanceSummary?['duplicate_records'] ?? 0}', Colors.orange.shade800),
                            _buildStatBadge('Excluded / No Signature', '${_attendanceSummary?['excluded_records'] ?? 0}', Colors.red.shade800),
                            _buildStatBadge('Review Required', '${_attendanceSummary?['review_required_records'] ?? 0}', Colors.purple.shade800),
                          ],
                        ),
                        const SizedBox(height: 16),

                        // Human Verification Table
                        const Text('Human Verification Table (Click to toggle signature or edit registration number):', style: TextStyle(fontSize: 11, color: AppConstants.textSecondary)),
                        const SizedBox(height: 6),
                        Container(
                          constraints: const BoxConstraints(maxHeight: 280),
                          decoration: BoxDecoration(
                            border: Border.all(color: AppConstants.borderLight),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: SingleChildScrollView(
                            scrollDirection: Axis.vertical,
                            child: SingleChildScrollView(
                              scrollDirection: Axis.horizontal,
                              child: DataTable(
                                headingRowHeight: 36,
                                dataRowMinHeight: 32,
                                dataRowMaxHeight: 40,
                                columns: const [
                                  DataColumn(label: Text('Reg No', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                                  DataColumn(label: Text('Class', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                                  DataColumn(label: Text('Signature', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                                  DataColumn(label: Text('Confidence', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                                  DataColumn(label: Text('Status', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                                  DataColumn(label: Text('Action', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                                ],
                                rows: _attendanceRecords.asMap().entries.map((entry) {
                                  final idx = entry.key;
                                  final rec = entry.value;
                                  final hasSig = rec['signature_detected'] == true;
                                  final status = rec['status']?.toString() ?? 'Unverified';

                                  return DataRow(
                                    cells: [
                                      DataCell(
                                        InkWell(
                                          onTap: () => _editRecordRegistrationNumber(idx),
                                          child: Row(
                                            mainAxisSize: MainAxisSize.min,
                                            children: [
                                              Text(rec['reg_no']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 11)),
                                              const SizedBox(width: 4),
                                              const Icon(Icons.edit, size: 11, color: Colors.grey),
                                            ],
                                          ),
                                        ),
                                      ),
                                      DataCell(Text(rec['mapped_class']?.toString() ?? 'Unmapped', style: const TextStyle(fontSize: 11))),
                                      DataCell(
                                        InkWell(
                                          onTap: () => _toggleRecordSignature(idx),
                                          child: Chip(
                                            visualDensity: VisualDensity.compact,
                                            avatar: Icon(hasSig ? Icons.check_circle : Icons.cancel, size: 12, color: hasSig ? Colors.green : Colors.red),
                                            label: Text(hasSig ? 'Yes' : 'No', style: TextStyle(fontSize: 10, color: hasSig ? Colors.green.shade800 : Colors.red.shade800)),
                                            backgroundColor: (hasSig ? Colors.green : Colors.red).withValues(alpha: 0.1),
                                          ),
                                        ),
                                      ),
                                      DataCell(Text(rec['confidence']?.toString() ?? 'High', style: const TextStyle(fontSize: 11))),
                                      DataCell(
                                        Chip(
                                          visualDensity: VisualDensity.compact,
                                          label: Text(status, style: const TextStyle(fontSize: 10)),
                                          backgroundColor: status == 'Verified' ? Colors.green.withValues(alpha: 0.15) : (status == 'Duplicate' ? Colors.orange.withValues(alpha: 0.15) : Colors.red.withValues(alpha: 0.1)),
                                        ),
                                      ),
                                      DataCell(
                                        IconButton(
                                          icon: const Icon(Icons.delete_outline, size: 14, color: Colors.red),
                                          tooltip: 'Exclude Record',
                                          onPressed: () => _excludeRecord(idx),
                                        ),
                                      ),
                                    ],
                                  );
                                }).toList(),
                              ),
                            ),
                          ),
                        ),

                        // Class Distribution & Google Forms Pie Chart Preview
                        if (_classDistributionChartBase64 != null || (_attendanceSummary?['class_distribution'] is List && (_attendanceSummary!['class_distribution'] as List).isNotEmpty)) ...[
                          const SizedBox(height: 16),
                          const Divider(),
                          const Text('Class-Wise Attendance Distribution', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
                          const SizedBox(height: 8),
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(
                                flex: 3,
                                child: Table(
                                  border: TableBorder.all(color: AppConstants.borderLight),
                                  children: [
                                    const TableRow(
                                      decoration: BoxDecoration(color: Color(0xFFF5F5F7)),
                                      children: [
                                        Padding(padding: EdgeInsets.all(6), child: Text('Academic Class', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                                        Padding(padding: EdgeInsets.all(6), child: Text('Count', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                                        Padding(padding: EdgeInsets.all(6), child: Text('Share (%)', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                                      ],
                                    ),
                                    ...((_attendanceSummary?['class_distribution'] as List? ?? []).map((c) {
                                      return TableRow(
                                        children: [
                                          Padding(padding: const EdgeInsets.all(6), child: Text(c['class_name']?.toString() ?? '', style: const TextStyle(fontSize: 11))),
                                          Padding(padding: const EdgeInsets.all(6), child: Text('${c['count'] ?? 0}', style: const TextStyle(fontSize: 11))),
                                          Padding(padding: const EdgeInsets.all(6), child: Text('${c['percentage'] ?? 0}%', style: const TextStyle(fontSize: 11))),
                                        ],
                                      );
                                    })),
                                  ],
                                ),
                              ),
                              if (_classDistributionChartBase64 != null) ...[
                                const SizedBox(width: 12),
                                Expanded(
                                  flex: 4,
                                  child: Container(
                                    height: 140,
                                    decoration: BoxDecoration(
                                      border: Border.all(color: AppConstants.borderLight),
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: ClipRRect(
                                      borderRadius: BorderRadius.circular(6),
                                      child: Image.memory(
                                        base64Decode(_classDistributionChartBase64!.split(',').last),
                                        fit: BoxFit.contain,
                                      ),
                                    ),
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
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

        // Section 6: E-Certificate Upload (Placed BEFORE Impact Analysis)
        _buildSectionHeader('6. Sample E-Certificate', Icons.card_membership_outlined),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Upload sample e-certificate or combined certificate PDF issued to participants.',
                  style: TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    ElevatedButton.icon(
                      icon: const Icon(Icons.upload_file, size: 16),
                      label: Text(_certificateFilename != null ? 'Change Certificate' : 'Upload E-Certificate (PDF/Image)'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.black,
                        foregroundColor: Colors.white,
                      ),
                      onPressed: _uploadCertificateFile,
                    ),
                    if (_certificateFilename != null) ...[
                      const SizedBox(width: 12),
                      Chip(
                        avatar: const Icon(Icons.check_circle, size: 14, color: Colors.green),
                        label: Text(_certificateFilename!, style: const TextStyle(fontSize: 11)),
                        onDeleted: () {
                          setState(() {
                            _certificateFilename = null;
                            _certificateBytes = null;
                            _certificateBase64 = null;
                          });
                        },
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _certificateCategoryController,
                        decoration: const InputDecoration(
                          labelText: 'Certificate Category',
                          hintText: 'e.g. Participation, Appreciation, Merit',
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextFormField(
                        controller: _certificatesIssuedController,
                        decoration: const InputDecoration(
                          labelText: 'Total Certificates Issued',
                          hintText: 'e.g. 61',
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _certificateDescriptionController,
                  decoration: const InputDecoration(
                    labelText: 'Certificate Description / Distribution Details',
                    hintText: 'e.g. Distributed electronically via institutional portal following attendance verification.',
                    border: OutlineInputBorder(),
                  ),
                ),
                if (_certificateBytes != null && _certificateFilename != null && !_certificateFilename!.toLowerCase().endsWith('.pdf')) ...[
                  const SizedBox(height: 12),
                  Container(
                    height: 160,
                    width: double.infinity,
                    decoration: BoxDecoration(
                      border: Border.all(color: AppConstants.borderLight),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: Image.memory(_certificateBytes!, fit: BoxFit.contain),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: 24),

        // Section 7: Impact Analysis (12 Configurable Questions)
        _buildSectionHeader('7. Impact Analysis', Icons.insights_outlined),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Top Action Bar with Simulation Indicator and Generate Button
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  alignment: WrapAlignment.spaceBetween,
                  children: [
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                          decoration: BoxDecoration(
                            color: Colors.purple.withValues(alpha: 0.08),
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(color: Colors.purple.withValues(alpha: 0.3)),
                          ),
                          child: const Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.auto_awesome, size: 13, color: Colors.purple),
                              SizedBox(width: 5),
                              Text(
                                'Simulated Impact Engine',
                                style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.purple),
                              ),
                            ],
                          ),
                        ),
                        if (_simulatedParticipantCount != null) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                            decoration: BoxDecoration(
                              color: Colors.black.withValues(alpha: 0.05),
                              borderRadius: BorderRadius.circular(6),
                              border: Border.all(color: AppConstants.borderLight),
                            ),
                            child: Text(
                              '$_simulatedParticipantCount Simulated Attendees',
                              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.black87),
                            ),
                          ),
                        ],
                      ],
                    ),
                    ElevatedButton.icon(
                      icon: _isGeneratingImpact
                          ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Icon(Icons.bolt, size: 16),
                      label: Text(_isGeneratingImpact
                          ? 'Simulating...'
                          : (_simulatedParticipantCount != null ? 'Regenerate Analysis' : 'Generate Impact Analysis')),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.black,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                      ),
                      onPressed: _isGeneratingImpact ? null : () {
                        _simulationSeed = DateTime.now().millisecondsSinceEpoch;
                        _generateSimulatedImpact();
                      },
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                // Class-wise Distribution: Chart + Table
                if (_classDistributionChartBase64 != null || (_attendanceSummary?['class_distribution'] is List && (_attendanceSummary!['class_distribution'] as List).isNotEmpty)) ...[
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.grey.withValues(alpha: 0.03),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppConstants.borderLight),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.pie_chart_outline, size: 16, color: Colors.black87),
                            SizedBox(width: 6),
                            Text(
                              'Class-wise Participant Distribution (8 Department Cohorts)',
                              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                            ),
                          ],
                        ),
                        const SizedBox(height: 10),
                        LayoutBuilder(
                          builder: (context, constraints) {
                            final isWide = constraints.maxWidth > 650;
                            final chartWidget = _classDistributionChartBase64 != null
                                ? Container(
                                    height: 180,
                                    decoration: BoxDecoration(
                                      color: Colors.white,
                                      border: Border.all(color: AppConstants.borderLight),
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: ClipRRect(
                                      borderRadius: BorderRadius.circular(6),
                                      child: Image.memory(
                                        base64Decode(_classDistributionChartBase64!.split(',').last),
                                        fit: BoxFit.contain,
                                      ),
                                    ),
                                  )
                                : const SizedBox.shrink();

                            final classList = (_attendanceSummary?['class_distribution'] as List?)
                                    ?.map((x) => Map<String, dynamic>.from(x as Map))
                                    .toList() ??
                                [];

                            final tableWidget = Table(
                              border: TableBorder.all(color: AppConstants.borderLight),
                              children: [
                                const TableRow(
                                  decoration: BoxDecoration(color: Color(0xFFF5F5F7)),
                                  children: [
                                    Padding(padding: EdgeInsets.symmetric(horizontal: 8, vertical: 6), child: Text('Cohort', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                                    Padding(padding: EdgeInsets.symmetric(horizontal: 8, vertical: 6), child: Text('Count', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                                    Padding(padding: EdgeInsets.symmetric(horizontal: 8, vertical: 6), child: Text('Percentage', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                                  ],
                                ),
                                ...classList.map((item) {
                                  return TableRow(
                                    children: [
                                      Padding(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4), child: Text('${item['class_name']}', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w500))),
                                      Padding(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4), child: Text('${item['count']}', style: const TextStyle(fontSize: 11))),
                                      Padding(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4), child: Text('${item['percentage']}%', style: const TextStyle(fontSize: 11))),
                                    ],
                                  );
                                }),
                              ],
                            );

                            if (isWide) {
                              return Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  if (_classDistributionChartBase64 != null)
                                    Expanded(flex: 5, child: chartWidget),
                                  if (_classDistributionChartBase64 != null)
                                    const SizedBox(width: 14),
                                  Expanded(flex: 6, child: tableWidget),
                                ],
                              );
                            } else {
                              return Column(
                                children: [
                                  if (_classDistributionChartBase64 != null) chartWidget,
                                  const SizedBox(height: 10),
                                  tableWidget,
                                ],
                              );
                            }
                          },
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                ],

                // Participation Summary Narrative Field
                _buildFieldWithAiTarget(
                  title: 'Participation Summary & Narrative Interpretation',
                  fieldKey: 'impact_analysis',
                  controller: _impactAnalysisController,
                  hint: 'Summarize attendance distribution, academic cohort representation, and learning outcomes...',
                  minLines: 3,
                ),
                const SizedBox(height: 20),

                // 12 Impact Questions
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Expanded(
                      child: Text(
                        'Configurable Impact Analysis Questions (12 ABET / NBA Metrics):',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '${_impactQuestions.length} Questions Drafted',
                      style: const TextStyle(fontSize: 11, color: AppConstants.textSecondary),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                const Text(
                  'Answers are automatically tailored to the simulated metrics and can be edited below:',
                  style: TextStyle(fontSize: 11, color: AppConstants.textSecondary),
                ),
                const SizedBox(height: 12),
                ListView.separated(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: _impactQuestions.length,
                  separatorBuilder: (ctx, i) => const SizedBox(height: 10),
                  itemBuilder: (ctx, i) {
                    final qObj = _impactQuestions[i];
                    return Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.grey.withValues(alpha: 0.04),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: AppConstants.borderLight),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(qObj['question'] ?? '', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
                          const SizedBox(height: 6),
                          TextFormField(
                            key: ValueKey('ia_${i}_${qObj['answer']?.hashCode}'),
                            initialValue: qObj['answer'],
                            maxLines: null,
                            minLines: 1,
                            style: const TextStyle(fontSize: 12),
                            decoration: const InputDecoration(
                              labelText: 'Factual Response (Editable)',
                              isDense: true,
                              border: OutlineInputBorder(),
                            ),
                            onChanged: (val) => _impactQuestions[i]['answer'] = val,
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 24),

        // Section 8: Feedback Analysis & PO1-PO12
        _buildSectionHeader('8. Feedback Analysis & Program Outcomes (PO1–PO12)', Icons.pie_chart_outline_rounded),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Simulation Notice Banner
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: Colors.blue.withValues(alpha: 0.06),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: Colors.blue.withValues(alpha: 0.2)),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.info_outline, size: 15, color: Colors.blue),
                      SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          '[Simulated Data: Generated for activity planning and departmental documentation]',
                          style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.blue),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 14),

                // Primary Action Button Row
                Wrap(
                  spacing: 12,
                  runSpacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    ElevatedButton.icon(
                      icon: _isGeneratingFeedback
                          ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Icon(Icons.pie_chart_rounded, size: 16),
                      label: Text(_isGeneratingFeedback
                          ? 'Generating 12 Charts...'
                          : (_feedbackAnalysisResult != null ? 'Regenerate 12 Feedback Charts' : 'Generate 12 Feedback Charts')),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.black,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                      ),
                      onPressed: _isGeneratingFeedback ? null : () {
                        _simulationSeed = DateTime.now().millisecondsSinceEpoch;
                        _generateSimulatedFeedback();
                      },
                    ),
                    if (_feedbackAnalysisResult != null && _feedbackAnalysisResult!['po_results'] is Map) ...[
                      Chip(
                        avatar: const Icon(Icons.check_circle, size: 15, color: Colors.green),
                        label: Text(
                          '12 PO Charts Active (${_feedbackAnalysisResult?['total_responses'] ?? 224} Responses)',
                          style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 16),

                // Overall Interpretation Field
                _buildFieldWithAiTarget(
                  title: 'Feedback Analysis Interpretation (Master Template Section 6)',
                  fieldKey: 'feedback_analysis',
                  controller: _feedbackAnalysisController,
                  hint: 'Detailed narrative describing feedback attainment, key strengths, and academic development areas...',
                  minLines: 3,
                ),
                const SizedBox(height: 20),

                // Overall PO Summary Table
                if (_feedbackAnalysisResult != null &&
                    (_feedbackAnalysisResult!['summary_table'] is List || _feedbackAnalysisResult!['po_results'] is Map)) ...[
                  _buildOverallPoSummaryTable(),
                  const SizedBox(height: 24),
                ],

                // All 12 PO Cards
                if (_feedbackAnalysisResult != null && _feedbackAnalysisResult!['po_results'] is Map) ...[
                  const Text(
                    'Programme Outcomes (PO1–PO12) Live Charts & Distributions:',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Google Forms style pie charts (Excellent: #109618, Very Good: #FF9900, Fair: #3366CC, Satisfactory: #DC3912)',
                    style: TextStyle(fontSize: 11, color: AppConstants.textSecondary),
                  ),
                  const SizedBox(height: 14),
                  _build12PoCardsList(),
                ],

                const SizedBox(height: 20),
                const Divider(),
                // Optional manual import expansion tile
                Theme(
                  data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                  child: ExpansionTile(
                    tilePadding: EdgeInsets.zero,
                    leading: const Icon(Icons.upload_file_outlined, size: 18, color: AppConstants.textSecondary),
                    title: const Text(
                      'Optional: Import Survey Responses from CSV/XLSX/XML file',
                      style: TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                    ),
                    children: [
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8.0),
                        child: _buildLegacyFeedbackImportWidget(),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 48),
      ],
    );
  }

  Widget _buildOverallPoSummaryTable() {
    List<Map<String, dynamic>> rows = [];
    if (_feedbackAnalysisResult?['summary_table'] is List) {
      rows = (_feedbackAnalysisResult!['summary_table'] as List)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
    } else if (_feedbackAnalysisResult?['po_results'] is Map) {
      final poMap = _feedbackAnalysisResult!['po_results'] as Map;
      for (int i = 1; i <= 12; i++) {
        final key = 'PO$i';
        final d = poMap[key] as Map? ?? {};
        final counts = d['counts'] as Map? ?? {};
        final pcts = d['percentages'] as Map? ?? {};
        rows.add({
          'po': key,
          'po_title': d['po_title'] ?? _poDefinitions[key] ?? key,
          'excellent': counts['Excellent'] ?? 0,
          'very_good': counts['Very Good'] ?? 0,
          'fair': counts['Fair'] ?? 0,
          'satisfactory': counts['Satisfactory'] ?? 0,
          'total': d['total_responses'] ?? 0,
          'positive_pct': d['positive_percentage'] ?? ((pcts['Excellent'] as num? ?? 0) + (pcts['Very Good'] as num? ?? 0)),
        });
      }
    }

    if (rows.isEmpty) {
      return const SizedBox.shrink();
    }

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: AppConstants.borderLight),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: const BoxDecoration(
              color: Color(0xFFF5F5F7),
              borderRadius: BorderRadius.only(topLeft: Radius.circular(8), topRight: Radius.circular(8)),
            ),
            child: const Row(
              children: [
                Icon(Icons.table_chart_outlined, size: 16, color: Colors.black87),
                SizedBox(width: 8),
                Text(
                  'Overall Programme Outcomes (PO1–PO12) Summary Table',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                ),
              ],
            ),
          ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: DataTable(
              headingRowHeight: 36,
              dataRowMinHeight: 32,
              dataRowMaxHeight: 36,
              horizontalMargin: 12,
              columnSpacing: 16,
              headingRowColor: WidgetStateProperty.all(const Color(0xFFFBFBFD)),
              columns: const [
                DataColumn(label: Text('PO', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                DataColumn(label: Text('Focus Title', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                DataColumn(label: Text('Excellent', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11, color: Color(0xFF109618)))),
                DataColumn(label: Text('Very Good', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11, color: Color(0xFFFF9900)))),
                DataColumn(label: Text('Fair', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11, color: Color(0xFF3366CC)))),
                DataColumn(label: Text('Satisfactory', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11, color: Color(0xFFDC3912)))),
                DataColumn(label: Text('Total', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                DataColumn(label: Text('Positive %', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
              ],
              rows: rows.map((r) {
                return DataRow(cells: [
                  DataCell(Text('${r['po']}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                  DataCell(Text('${r['po_title']}', style: const TextStyle(fontSize: 11))),
                  DataCell(Text('${r['excellent']}', style: const TextStyle(fontSize: 11))),
                  DataCell(Text('${r['very_good']}', style: const TextStyle(fontSize: 11))),
                  DataCell(Text('${r['fair']}', style: const TextStyle(fontSize: 11))),
                  DataCell(Text('${r['satisfactory']}', style: const TextStyle(fontSize: 11))),
                  DataCell(Text('${r['total']}', style: const TextStyle(fontSize: 11))),
                  DataCell(Text('${r['positive_pct']}%', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 11, color: Colors.green))),
                ]);
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _build12PoCardsList() {
    final poResults = _feedbackAnalysisResult!['po_results'] as Map;
    final poKeys = List.generate(12, (i) => 'PO${i + 1}');

    return Column(
      children: poKeys.map((poKey) {
        final poData = (poResults[poKey] as Map?) ?? {};
        if (poData.isEmpty) {
          return const SizedBox.shrink();
        }

        final chartB64 = poData['chart_base64']?.toString();
        final poTitle = poData['po_title'] ?? _poDefinitions[poKey] ?? poKey;
        final poQuestion = poData['po_question']?.toString() ?? '';
        final isRegen = _isRegeneratingPo[poKey] == true;

        final questionText = poQuestion.isNotEmpty
            ? (poQuestion.startsWith(poKey) ? poQuestion : '$poKey: $poQuestion')
            : '$poKey: $poTitle';

        return Container(
          margin: const EdgeInsets.only(bottom: 16),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: Colors.white,
            border: Border.all(color: AppConstants.borderLight),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 1. Question Title and Regenerate Action
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      questionText,
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, height: 1.3),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    iconSize: 16,
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                    tooltip: 'Regenerate $poKey Chart',
                    icon: isRegen
                        ? const SizedBox(width: 12, height: 12, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black))
                        : const Icon(Icons.refresh, color: AppConstants.textSecondary),
                    onPressed: isRegen ? null : () => _regenerateSinglePo(poKey),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              // 2. Pie Chart (Only question and pie chart, nothing below)
              if (chartB64 != null)
                Center(
                  child: Container(
                    constraints: const BoxConstraints(maxHeight: 220),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      border: Border.all(color: AppConstants.borderLight),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(6),
                      child: Image.memory(
                        base64Decode(chartB64.split(',').last),
                        fit: BoxFit.contain,
                      ),
                    ),
                  ),
                ),
            ],
          ),
        );
      }).toList(),
    );
  }

  Widget _buildLegacyFeedbackImportWidget() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            ElevatedButton.icon(
              icon: _isImportingFeedback
                  ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.file_upload_outlined, size: 16),
              label: Text(_isImportingFeedback ? 'Importing...' : 'Import Feedback File'),
              style: ElevatedButton.styleFrom(backgroundColor: Colors.black, foregroundColor: Colors.white),
              onPressed: _isImportingFeedback ? null : _importFeedbackFile,
            ),
            if (_feedbackFilename != null) ...[
              const SizedBox(width: 12),
              Chip(
                avatar: const Icon(Icons.check_circle, size: 14, color: Colors.green),
                label: Text('$_feedbackFilename (${_feedbackRows.length} responses)', style: const TextStyle(fontSize: 11)),
              ),
            ],
          ],
        ),
        if (_feedbackHeaders.isNotEmpty) ...[
          const SizedBox(height: 16),
          const Text('Map Survey Questions to Program Outcomes (PO1–PO12):', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
          const SizedBox(height: 8),
          Container(
            constraints: const BoxConstraints(maxHeight: 240),
            child: ListView(
              shrinkWrap: true,
              children: _poDefinitions.entries.map((e) {
                final poKey = e.key;
                final poDesc = e.value;
                final currentVal = _poColumnMapping[poKey];

                return Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Row(
                    children: [
                      Expanded(
                        flex: 2,
                        child: Text('$poKey: $poDesc', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        flex: 3,
                        child: DropdownButtonFormField<String>(
                          initialValue: _feedbackHeaders.contains(currentVal) ? currentVal : null,
                          isDense: true,
                          style: const TextStyle(fontSize: 11, color: Colors.black),
                          decoration: const InputDecoration(
                            contentPadding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                            border: OutlineInputBorder(),
                            hintText: 'Select Column',
                          ),
                          items: [
                            const DropdownMenuItem<String>(value: null, child: Text('None / Unmapped', style: TextStyle(fontSize: 11))),
                            ..._feedbackHeaders.map((h) => DropdownMenuItem(value: h, child: Text(h, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11)))),
                          ],
                          onChanged: (val) {
                            setState(() {
                              if (val == null) {
                                _poColumnMapping.remove(poKey);
                              } else {
                                _poColumnMapping[poKey] = val;
                              }
                            });
                          },
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),
          ),
          const SizedBox(height: 12),
          ElevatedButton.icon(
            icon: _isAnalyzingFeedback
                ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.analytics_outlined, size: 16),
            label: Text(_isAnalyzingFeedback ? 'Rendering Charts...' : 'Generate Google Forms Pie Charts & Distributions'),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.black, foregroundColor: Colors.white),
            onPressed: _isAnalyzingFeedback ? null : _analyzeFeedbackPo,
          ),
        ],
      ],
    );
  }

  Widget _buildStatBadge(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label, style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: color)),
          const SizedBox(height: 2),
          Text(value, style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: color)),
        ],
      ),
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
