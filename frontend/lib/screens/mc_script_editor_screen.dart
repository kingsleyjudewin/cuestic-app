import 'package:flutter/material.dart';
import '../config/constants.dart';
import '../models/mc_script.dart';
import '../services/mc_service.dart';
import '../services/auth_service.dart';
import '../utils/download_helper.dart';
import '../widgets/custom_card.dart';

class McScriptEditorScreen extends StatefulWidget {
  final int? scriptId;
  final int? initialEventId;
  final int? initialTaskId;
  final int? initialFolderId;
  final McService mcService;
  final AuthService authService;

  const McScriptEditorScreen({
    super.key,
    this.scriptId,
    this.initialEventId,
    this.initialTaskId,
    this.initialFolderId,
    required this.mcService,
    required this.authService,
  });

  @override
  State<McScriptEditorScreen> createState() => _McScriptEditorScreenState();
}

class _McScriptEditorScreenState extends State<McScriptEditorScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  bool _isLoading = true;
  bool _isSaving = false;
  bool _isAiBusy = false;
  bool _isValidating = false;
  String? _errorMessage;

  int? _scriptId;
  String _status = 'draft';
  String? _driveWebViewLink;

  // Event & metadata controllers
  final _titleController = TextEditingController();
  final _eventTypeController = TextEditingController(text: 'Technical Talk');
  final _venueController = TextEditingController(text: 'Campus Auditorium');
  final _durationController = TextEditingController(text: '2 Hours');
  final _deptController = TextEditingController(text: 'Department of Electronics and Communication Engineering');
  final _clubController = TextEditingController(text: 'CUestIC & IEEE Student Branch');
  final _chiefGuestController = TextEditingController();
  final _facultyController = TextEditingController();
  final _scheduleController = TextEditingController();

  int? _selectedEventId;
  String _selectedTone = 'Formal';

  List<McAnchor> _anchors = [
    const McAnchor(id: 1, name: 'Merrick Dias', role: 'MC 1'),
    const McAnchor(id: 2, name: 'Qurrath Ul Ain', role: 'MC 2'),
  ];

  List<McScriptSegment> _segments = [];
  int _activeSegmentIndex = 0;

  // AI Copilot state
  final _aiPromptController = TextEditingController();
  String _selectedAiAction = 'generate';
  String? _aiGeneratedDialogue;
  String? _aiGeneratedDirections;

  // Teleprompter state
  double _teleprompterFontSize = 16.0;
  ScriptValidationResult? _validationResult;

  // Segment Types Catalog
  final Map<String, Map<String, dynamic>> _segmentTypesCatalog = {
    'pre_event_announcement': {'title': 'Pre-Event Housekeeping & Decorum', 'icon': Icons.announcement_outlined},
    'opening_greeting': {'title': 'Opening Greeting & MC Introduction', 'icon': Icons.waving_hand_outlined},
    'dignitary_introduction': {'title': 'Dignitary Acknowledgement', 'icon': Icons.account_balance_outlined},
    'welcome_address': {'title': 'Welcome Address Invitation', 'icon': Icons.campaign_outlined},
    'speaker_introduction': {'title': 'Technical Speaker Introduction', 'icon': Icons.record_voice_over_outlined},
    'event_report': {'title': 'Event / Club Activity Report', 'icon': Icons.assessment_outlined},
    'prize_distribution': {'title': 'Prize Distribution Ceremony', 'icon': Icons.emoji_events_outlined},
    'badge_distribution': {'title': 'Badge & Leadership Distribution', 'icon': Icons.military_tech_outlined},
    'memento_presentation': {'title': 'Token of Reverence & Memento', 'icon': Icons.card_giftcard_outlined},
    'vote_of_thanks': {'title': 'Formal Vote of Thanks', 'icon': Icons.thumb_up_alt_outlined},
    'feedback_announcements': {'title': 'Feedback QR & Attendance', 'icon': Icons.qr_code_2_outlined},
    'anthem_closing': {'title': 'University / National Anthem', 'icon': Icons.music_note_outlined},
    'custom': {'title': 'Custom Programme Segment', 'icon': Icons.extension_outlined},
  };

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _scriptId = widget.scriptId;
    _selectedEventId = widget.initialEventId;
    _loadInitialData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _titleController.dispose();
    _eventTypeController.dispose();
    _venueController.dispose();
    _durationController.dispose();
    _deptController.dispose();
    _clubController.dispose();
    _chiefGuestController.dispose();
    _facultyController.dispose();
    _scheduleController.dispose();
    _aiPromptController.dispose();
    super.dispose();
  }

  Future<void> _loadInitialData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      if (_scriptId != null) {
        final script = await widget.mcService.fetchScriptDetail(_scriptId!);
        _titleController.text = script.title;
        _selectedEventId = script.eventId;
        _eventTypeController.text = script.eventType ?? 'Technical Talk';
        _venueController.text = script.venue ?? 'Campus Auditorium';
        _durationController.text = script.duration ?? '2 Hours';
        _selectedTone = script.tone;
        _anchors = script.anchors.isNotEmpty ? script.anchors : _anchors;
        _chiefGuestController.text = script.chiefGuestDetails ?? '';
        _facultyController.text = script.facultySpeakerDetails ?? '';
        _scheduleController.text = script.eventSchedule ?? '';
        _segments = script.segments;
        _status = script.status;

        if (script.eventMetadata.isNotEmpty) {
          if (script.eventMetadata['organizing_department'] != null) {
            _deptController.text = script.eventMetadata['organizing_department'];
          }
          if (script.eventMetadata['organizing_club'] != null) {
            _clubController.text = script.eventMetadata['organizing_club'];
          }
        }
      }
    } catch (e) {
      _errorMessage = 'Error loading script data: $e';
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Map<String, dynamic> _collectPayload() {
    return {
      'title': _titleController.text.trim(),
      'event_id': _selectedEventId,
      'task_id': widget.initialTaskId,
      if (widget.initialFolderId != null) 'folder_id': widget.initialFolderId,
      'event_type': _eventTypeController.text.trim(),
      'venue': _venueController.text.trim(),
      'duration': _durationController.text.trim(),
      'tone': _selectedTone,
      'number_of_anchors': _anchors.length,
      'anchors': _anchors.map((a) => a.toJson()).toList(),
      'chief_guest_details': _chiefGuestController.text.trim(),
      'faculty_speaker_details': _facultyController.text.trim(),
      'event_schedule': _scheduleController.text.trim(),
      'event_metadata': {
        'organizing_department': _deptController.text.trim(),
        'organizing_club': _clubController.text.trim(),
      },
      'segments': _segments.map((s) => s.toJson()).toList(),
    };
  }

  Future<void> _saveDraft({bool showNotice = true}) async {
    if (_titleController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a script title.')),
      );
      return;
    }

    setState(() => _isSaving = true);
    try {
      final payload = _collectPayload();
      McScript saved;
      if (_scriptId == null) {
        saved = await widget.mcService.createScript(payload);
        _scriptId = saved.id;
      } else {
        saved = await widget.mcService.updateScript(_scriptId!, payload);
      }

      setState(() {
        _status = saved.status;
      });

      if (showNotice && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Script saved to Neon PostgreSQL successfully!'),
            backgroundColor: AppConstants.pureBlack,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to save script: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  // ---------------------------------------------------------------------------
  // Visual Programme Segment Operations
  // ---------------------------------------------------------------------------
  void _onReorderSegments(int oldIndex, int newIndex) {
    setState(() {
      if (newIndex > oldIndex) newIndex -= 1;
      final seg = _segments.removeAt(oldIndex);
      _segments.insert(newIndex, seg);

      for (int i = 0; i < _segments.length; i++) {
        _segments[i].sequenceOrder = i + 1;
      }
    });

    if (_scriptId != null) {
      final ids = _segments.map((s) => s.intId ?? int.tryParse(s.id) ?? 0).where((id) => id > 0).toList();
      if (ids.length == _segments.length) {
        widget.mcService.reorderSegments(_scriptId!, ids).catchError((_) => <McScriptSegment>[]);
      }
    }
  }

  Future<void> _showAddSegmentDialog() async {
    String selectedType = 'speaker_introduction';
    final titleCtrl = TextEditingController(text: 'Guest Speaker Introduction');
    String assignedMc = _anchors.isNotEmpty ? _anchors.first.name : 'MC 1';

    await showDialog(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (dCtx, setDState) {
            return AlertDialog(
              backgroundColor: AppConstants.pureWhite,
              title: const Text('Add Programme Segment', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              content: SizedBox(
                width: 480,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Segment Type (13 Standards)', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 6),
                    DropdownButtonFormField<String>(
                      initialValue: selectedType,
                      decoration: InputDecoration(
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      ),
                      items: _segmentTypesCatalog.entries.map((e) {
                        return DropdownMenuItem<String>(
                          value: e.key,
                          child: Row(
                            children: [
                              Icon(e.value['icon'] as IconData, size: 16, color: AppConstants.pureBlack),
                              const SizedBox(width: 8),
                              Text(e.value['title'] as String, style: const TextStyle(fontSize: 13)),
                            ],
                          ),
                        );
                      }).toList(),
                      onChanged: (val) {
                        if (val != null) {
                          setDState(() {
                            selectedType = val;
                            titleCtrl.text = _segmentTypesCatalog[val]!['title'] as String;
                          });
                        }
                      },
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: titleCtrl,
                      decoration: InputDecoration(
                        labelText: 'Segment Title *',
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                      ),
                    ),
                    const SizedBox(height: 12),
                    const Text('Assigned MC', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 6),
                    DropdownButtonFormField<String>(
                      initialValue: assignedMc,
                      decoration: InputDecoration(
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      ),
                      items: _anchors.map((a) {
                        return DropdownMenuItem<String>(
                          value: a.name,
                          child: Text(a.name, style: const TextStyle(fontSize: 13)),
                        );
                      }).toList(),
                      onChanged: (val) {
                        if (val != null) setDState(() => assignedMc = val);
                      },
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(backgroundColor: AppConstants.pureBlack, foregroundColor: Colors.white),
                  onPressed: () async {
                    final title = titleCtrl.text.trim();
                    if (title.isEmpty) return;
                    Navigator.pop(ctx);

                    if (_scriptId != null) {
                      try {
                        final created = await widget.mcService.addSegment(_scriptId!, {
                          'segment_type': selectedType,
                          'title': title,
                          'assigned_mc': assignedMc,
                          'is_enabled': true,
                        });
                        setState(() {
                          _segments.add(created);
                          _activeSegmentIndex = _segments.length - 1;
                        });
                      } catch (_) {
                        _localAddSegment(selectedType, title, assignedMc);
                      }
                    } else {
                      _localAddSegment(selectedType, title, assignedMc);
                    }
                  },
                  child: const Text('Add to Programme'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  void _localAddSegment(String type, String title, String assignedMc) {
    setState(() {
      _segments.add(McScriptSegment(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        segmentType: type,
        title: title,
        sequenceOrder: _segments.length + 1,
        assignedMc: assignedMc,
        dialogue: '',
        stageDirections: '',
      ));
      _activeSegmentIndex = _segments.length - 1;
    });
  }

  Future<void> _duplicateSegment(int index) async {
    final seg = _segments[index];
    final copy = McScriptSegment(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      segmentType: seg.segmentType,
      title: '${seg.title} (Copy)',
      sequenceOrder: index + 2,
      assignedMc: seg.assignedMc,
      isEnabled: seg.isEnabled,
      inputData: Map<String, dynamic>.from(seg.inputData),
      dialogue: seg.dialogue,
      stageDirections: seg.stageDirections,
    );

    // Optimistic UI update (0ms instant card insertion)
    setState(() {
      _segments.insert(index + 1, copy);
      for (int i = 0; i < _segments.length; i++) {
        _segments[i].sequenceOrder = i + 1;
      }
    });

    if (_scriptId != null && seg.intId != null) {
      try {
        final dup = await widget.mcService.duplicateSegment(_scriptId!, seg.intId!);
        if (mounted) {
          setState(() {
            final targetIdx = _segments.indexOf(copy);
            if (targetIdx != -1) {
              _segments[targetIdx] = dup;
            }
          });
        }
      } catch (_) {}
    }
  }

  Future<void> _deleteSegment(int index) async {
    final seg = _segments[index];
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Programme Segment'),
        content: Text('Are you sure you want to delete "${seg.title}" from the programme flow?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    // Optimistic UI update (0ms instant removal)
    final removedSeg = _segments.removeAt(index);
    for (int i = 0; i < _segments.length; i++) {
      _segments[i].sequenceOrder = i + 1;
    }
    if (_activeSegmentIndex >= _segments.length) {
      _activeSegmentIndex = _segments.isNotEmpty ? _segments.length - 1 : 0;
    }
    setState(() {});

    if (_scriptId != null && seg.intId != null) {
      widget.mcService.deleteSegment(_scriptId!, seg.intId!).catchError((e) {
        if (mounted) {
          setState(() {
            _segments.insert(index, removedSeg);
          });
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Failed to delete segment: $e'), backgroundColor: Colors.red),
          );
        }
      });
    }
  }

  Future<void> _autoAssignMcs() async {
    if (_anchors.isEmpty) return;

    if (_scriptId != null) {
      try {
        final updated = await widget.mcService.autoAssignMcs(_scriptId!);
        setState(() => _segments = updated);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('MC dialogue turns automatically alternated across programme segments!')),
          );
        }
        return;
      } catch (_) {}
    }

    setState(() {
      int active = 0;
      for (var s in _segments) {
        if (s.isEnabled) {
          s.assignedMc = _anchors[active % _anchors.length].name;
          active++;
        }
      }
    });
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('MC dialogue turns alternated.')),
      );
    }
  }

  Future<void> _saveAsTemplate() async {
    if (_scriptId == null) {
      await _saveDraft(showNotice: false);
    }
    if (_scriptId == null) return;

    final nameCtrl = TextEditingController(text: '${_titleController.text.trim()} Flow');
    final descCtrl = TextEditingController(text: 'Reusable programme flow for ${_eventTypeController.text.trim()}');

    if (!mounted) return;
    final save = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Save Programme as Reusable Template'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: nameCtrl,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'Template Name *', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: descCtrl,
              maxLines: 2,
              decoration: const InputDecoration(labelText: 'Description', border: OutlineInputBorder()),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppConstants.pureBlack, foregroundColor: Colors.white),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Save Template'),
          ),
        ],
      ),
    );

    if (save != true) return;

    try {
      await widget.mcService.saveScriptAsTemplate(
        _scriptId!,
        nameCtrl.text.trim(),
        descCtrl.text.trim(),
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Programme flow saved to Saved Templates!'), backgroundColor: Colors.green),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to save template: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  // ---------------------------------------------------------------------------
  // AI Generation on Single Segment
  // ---------------------------------------------------------------------------
  Future<void> _runAiOnSegment(int index, {String action = 'generate'}) async {
    final seg = _segments[index];
    setState(() => _isAiBusy = true);

    try {
      if (_scriptId != null && seg.intId != null) {
        final result = await widget.mcService.aiGenerateSegmentDialogue(
          _scriptId!,
          seg.intId!,
          action: action,
          instruction: _aiPromptController.text.trim().isNotEmpty ? _aiPromptController.text.trim() : null,
          inputData: seg.inputData,
        );

        final updatedSeg = result['segment'];
        if (updatedSeg != null) {
          setState(() {
            _segments[index] = McScriptSegment.fromJson(updatedSeg as Map<String, dynamic>);
            _aiGeneratedDialogue = _segments[index].dialogue;
            _aiGeneratedDirections = _segments[index].stageDirections;
          });
        }
      } else {
        // Fallback segment generation
        final res = await widget.mcService.aiGenerateSegment(
          segmentType: seg.segmentType,
          eventInfo: {
            'title': _titleController.text.trim(),
            'event_type': _eventTypeController.text.trim(),
            'venue': _venueController.text.trim(),
            'tone': _selectedTone,
            'anchors': _anchors.map((a) => a.toJson()).toList(),
            'chief_guest_details': _chiefGuestController.text.trim(),
            'faculty_speaker_details': _facultyController.text.trim(),
          },
          currentContent: seg.dialogue,
          instructions: _aiPromptController.text.trim(),
        );

        if (res['segment'] != null && res['segment']['dialogue'] != null) {
          setState(() {
            seg.dialogue = res['segment']['dialogue'];
            if (res['segment']['stage_directions'] != null) {
              seg.stageDirections = res['segment']['stage_directions'];
            }
            _aiGeneratedDialogue = seg.dialogue;
            _aiGeneratedDirections = seg.stageDirections;
          });
        }
      }

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('✨ AI generated stage script for "${seg.title}"!'), backgroundColor: Colors.teal),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('AI Generation Notice: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _isAiBusy = false);
    }
  }

  // ---------------------------------------------------------------------------
  // Pre-flight Verification & Export
  // ---------------------------------------------------------------------------
  Future<void> _runPreflightValidation() async {
    if (_scriptId == null) {
      await _saveDraft(showNotice: false);
    }
    if (_scriptId == null) return;

    setState(() => _isValidating = true);
    try {
      final res = await widget.mcService.validateScript(_scriptId!);
      setState(() => _validationResult = res);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Validation check failed: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isValidating = false);
    }
  }

  Future<void> _exportDocx() async {
    await _saveDraft(showNotice: false);
    if (_scriptId == null) return;

    setState(() => _isSaving = true);
    try {
      final bytes = await widget.mcService.downloadDocxBytes(_scriptId!);
      final msg = await DownloadHelper.downloadFile(
        bytes,
        'MC_Script_${_titleController.text.trim().replaceAll(' ', '_')}.docx',
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(msg), backgroundColor: Colors.teal),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('DOCX export failed: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  Future<void> _uploadToGoogleDrive() async {
    await _saveDraft(showNotice: false);
    if (_scriptId == null) return;

    setState(() => _isSaving = true);
    try {
      final res = await widget.mcService.uploadToDrive(_scriptId!);
      setState(() {
        _status = 'uploaded';
        _driveWebViewLink = res['drive_web_view_link'];
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Final script uploaded to MC Google Drive folder!'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Google Drive upload notice: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  Future<void> _submitForReview() async {
    await _saveDraft(showNotice: false);
    if (_scriptId == null) return;

    setState(() => _isSaving = true);
    try {
      final updated = await widget.mcService.submitForReview(_scriptId!);
      setState(() => _status = updated.status);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Script submitted for MC Lead review!'), backgroundColor: Colors.green),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Submission failed: $e'), backgroundColor: Colors.red));
      }
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  // ---------------------------------------------------------------------------
  // Build Main Scaffold
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
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _titleController.text.isNotEmpty ? _titleController.text : 'Event Hosting Script',
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
            Row(
              children: [
                Text(_eventTypeController.text, style: const TextStyle(fontSize: 11, color: AppConstants.textSecondary)),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade200,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(_status.toUpperCase(), style: const TextStyle(fontSize: 9, fontWeight: FontWeight.bold)),
                ),
              ],
            ),
          ],
        ),
        actions: [
          if (_isSaving || _isAiBusy)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16),
              child: Center(
                child: SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(color: AppConstants.pureBlack, strokeWidth: 2),
                ),
              ),
            )
          else ...[
            TextButton.icon(
              icon: const Icon(Icons.save_outlined, color: AppConstants.pureBlack, size: 18),
              label: const Text('Save Draft', style: TextStyle(color: AppConstants.pureBlack, fontWeight: FontWeight.bold)),
              onPressed: () => _saveDraft(),
            ),
          ],
        ],
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: AppConstants.pureBlack,
          indicatorWeight: 2.5,
          labelColor: AppConstants.pureBlack,
          unselectedLabelColor: AppConstants.textSecondary,
          tabs: const [
            Tab(icon: Icon(Icons.reorder, size: 18), text: 'Visual Programme Builder'),
            Tab(icon: Icon(Icons.auto_awesome, size: 18), text: 'AI Script Editor'),
            Tab(icon: Icon(Icons.visibility_outlined, size: 18), text: 'Stage Teleprompter'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? Center(child: Text(_errorMessage!, style: const TextStyle(color: Colors.red)))
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildVisualProgrammeBuilderTab(),
                    _buildAiScriptEditorTab(),
                    _buildStageTeleprompterTab(),
                  ],
                ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 1: Visual Programme Builder
  // ---------------------------------------------------------------------------
  Widget _buildVisualProgrammeBuilderTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Top Action Toolbar
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Programme Sequence', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 2),
                  Text('${_segments.length} segments in sequence • Drag to reorder programme flow',
                      style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary)),
                ],
              ),
              Wrap(
                spacing: 8,
                children: [
                  OutlinedButton.icon(
                    icon: const Icon(Icons.swap_horiz, size: 16),
                    label: const Text('Auto Alternate MCs'),
                    style: OutlinedButton.styleFrom(foregroundColor: AppConstants.pureBlack),
                    onPressed: _autoAssignMcs,
                  ),
                  OutlinedButton.icon(
                    icon: const Icon(Icons.bookmark_border, size: 16),
                    label: const Text('Save as Blueprint'),
                    style: OutlinedButton.styleFrom(foregroundColor: AppConstants.pureBlack),
                    onPressed: _saveAsTemplate,
                  ),
                  ElevatedButton.icon(
                    icon: const Icon(Icons.add, size: 16),
                    label: const Text('Add Segment'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppConstants.pureBlack,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                    onPressed: _showAddSegmentDialog,
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Reorderable Segment List
          if (_segments.isEmpty)
            CustomCard(
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 40),
                  child: Column(
                    children: [
                      Icon(Icons.dashboard_customize_outlined, size: 48, color: Colors.grey.shade400),
                      const SizedBox(height: 12),
                      const Text('Programme has no segments yet', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                      const SizedBox(height: 6),
                      const Text('Click Add Segment to build your university event flow',
                          style: TextStyle(color: AppConstants.textSecondary, fontSize: 13)),
                      const SizedBox(height: 14),
                      ElevatedButton(
                        style: ElevatedButton.styleFrom(backgroundColor: AppConstants.pureBlack, foregroundColor: Colors.white),
                        onPressed: _showAddSegmentDialog,
                        child: const Text('Add Segment'),
                      ),
                    ],
                  ),
                ),
              ),
            )
          else
            ReorderableListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _segments.length,
              onReorder: _onReorderSegments,
              itemBuilder: (ctx, i) {
                final seg = _segments[i];
                final segTypeMeta = _segmentTypesCatalog[seg.segmentType] ?? _segmentTypesCatalog['custom']!;
                final bool isFilled = seg.dialogue.trim().isNotEmpty;

                return Container(
                  key: ValueKey('seg_${seg.id}_$i'),
                  margin: const EdgeInsets.only(bottom: 10),
                  decoration: BoxDecoration(
                    color: seg.isEnabled ? AppConstants.pureWhite : Colors.grey.shade100,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: _activeSegmentIndex == i ? AppConstants.pureBlack : AppConstants.borderLight,
                      width: _activeSegmentIndex == i ? 1.5 : 1.0,
                    ),
                    boxShadow: [
                      BoxShadow(color: Colors.black.withValues(alpha: 0.02), blurRadius: 4, offset: const Offset(0, 2)),
                    ],
                  ),
                  child: ListTile(
                    contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    leading: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.drag_indicator, color: Colors.grey, size: 20),
                        const SizedBox(width: 8),
                        CircleAvatar(
                          radius: 14,
                          backgroundColor: AppConstants.pureBlack,
                          child: Text('${i + 1}',
                              style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold)),
                        ),
                      ],
                    ),
                    title: Row(
                      children: [
                        Icon(segTypeMeta['icon'] as IconData, size: 16, color: AppConstants.pureBlack),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            seg.title,
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              fontSize: 14,
                              color: seg.isEnabled ? Colors.black87 : Colors.grey,
                            ),
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: isFilled ? Colors.green.shade50 : Colors.orange.shade50,
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(color: isFilled ? Colors.green.shade200 : Colors.orange.shade200),
                          ),
                          child: Text(
                            isFilled ? 'Drafted' : 'Empty',
                            style: TextStyle(
                              color: isFilled ? Colors.green.shade800 : Colors.orange.shade800,
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ],
                    ),
                    subtitle: Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: Colors.grey.shade100,
                              borderRadius: BorderRadius.circular(6),
                              border: Border.all(color: Colors.grey.shade300),
                            ),
                            child: Text('Assigned: ${seg.assignedMc}',
                                style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600)),
                          ),
                          const SizedBox(width: 8),
                          Text(segTypeMeta['title'] as String,
                              style: const TextStyle(fontSize: 11, color: AppConstants.textSecondary)),
                        ],
                      ),
                    ),
                    trailing: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        IconButton(
                          icon: const Icon(Icons.auto_awesome, color: Colors.purple, size: 20),
                          tooltip: 'AI Generate this Segment',
                          onPressed: () {
                            setState(() => _activeSegmentIndex = i);
                            _runAiOnSegment(i);
                          },
                        ),
                        IconButton(
                          icon: const Icon(Icons.edit_note, size: 22),
                          tooltip: 'Edit in AI Editor',
                          onPressed: () {
                            setState(() => _activeSegmentIndex = i);
                            _tabController.index = 1;
                          },
                        ),
                        Switch(
                          value: seg.isEnabled,
                          activeThumbColor: AppConstants.pureBlack,
                          onChanged: (val) {
                            setState(() => seg.isEnabled = val);
                          },
                        ),
                        PopupMenuButton<String>(
                          icon: const Icon(Icons.more_vert, size: 18),
                          onSelected: (val) {
                            if (val == 'duplicate') _duplicateSegment(i);
                            if (val == 'delete') _deleteSegment(i);
                          },
                          itemBuilder: (c) => [
                            const PopupMenuItem(value: 'duplicate', child: Text('Duplicate Segment')),
                            const PopupMenuItem(value: 'delete', child: Text('Delete Segment', style: TextStyle(color: Colors.red))),
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

  // ---------------------------------------------------------------------------
  // Tab 2: Two-Panel AI Script Editor
  // ---------------------------------------------------------------------------
  Widget _buildAiScriptEditorTab() {
    if (_segments.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text('No segments available to edit.'),
            const SizedBox(height: 12),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: AppConstants.pureBlack),
              onPressed: () => _tabController.index = 0,
              child: const Text('Go to Programme Builder', style: TextStyle(color: Colors.white)),
            ),
          ],
        ),
      );
    }

    final activeSeg = _segments[_activeSegmentIndex];

    return LayoutBuilder(
      builder: (ctx, constraints) {
        final isWide = constraints.maxWidth >= 900;

        if (isWide) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Left Panel: AI Copilot
              SizedBox(
                width: 380,
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: _buildAiCopilotPanel(activeSeg),
                ),
              ),
              const VerticalDivider(width: 1, color: AppConstants.borderLight),
              // Right Panel: Segment & Dialogue Editor
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(20),
                  child: _buildSegmentEditorPanel(activeSeg),
                ),
              ),
            ],
          );
        } else {
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                _buildSegmentEditorPanel(activeSeg),
                const SizedBox(height: 20),
                const Divider(),
                _buildAiCopilotPanel(activeSeg),
              ],
            ),
          );
        }
      },
    );
  }

  Widget _buildAiCopilotPanel(McScriptSegment activeSeg) {
    McScriptSegment? prevSeg = _activeSegmentIndex > 0 ? _segments[_activeSegmentIndex - 1] : null;
    McScriptSegment? nextSeg = _activeSegmentIndex < _segments.length - 1 ? _segments[_activeSegmentIndex + 1] : null;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: Colors.purple.shade700,
                borderRadius: BorderRadius.circular(6),
              ),
              child: const Icon(Icons.auto_awesome, color: Colors.white, size: 16),
            ),
            const SizedBox(width: 8),
            const Text('AI MC Copilot', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ],
        ),
        const SizedBox(height: 12),

        // Context Card
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.purple.shade50,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: Colors.purple.shade200),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Active: ${activeSeg.title}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
              Text('Assigned to: ${activeSeg.assignedMc}', style: const TextStyle(fontSize: 11)),
              if (prevSeg != null) ...[
                const SizedBox(height: 4),
                Text('Preceding: ${prevSeg.title} (${prevSeg.assignedMc})',
                    style: TextStyle(fontSize: 11, color: Colors.purple.shade900)),
              ],
              if (nextSeg != null) ...[
                const SizedBox(height: 2),
                Text('Succeeding: ${nextSeg.title} (${nextSeg.assignedMc})',
                    style: TextStyle(fontSize: 11, color: Colors.purple.shade900)),
              ],
            ],
          ),
        ),
        const SizedBox(height: 16),

        // Action Chips
        const Text('Copilot Action', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
        const SizedBox(height: 6),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: [
            {'label': 'Generate', 'action': 'generate'},
            {'label': 'Regenerate', 'action': 'regenerate'},
            {'label': 'Formalize', 'action': 'formalize'},
            {'label': 'Conversational', 'action': 'conversational'},
            {'label': 'Shorten', 'action': 'shorten'},
            {'label': 'Expand Bio', 'action': 'expand'},
            {'label': 'Fix Grammar', 'action': 'fix_grammar'},
            {'label': 'Add Transition', 'action': 'add_transition'},
          ].map((a) {
            final isSel = _selectedAiAction == a['action'];
            return ChoiceChip(
              label: Text(a['label']!),
              selected: isSel,
              selectedColor: Colors.purple.shade700,
              labelStyle: TextStyle(
                color: isSel ? Colors.white : Colors.black87,
                fontSize: 11,
                fontWeight: isSel ? FontWeight.bold : FontWeight.normal,
              ),
              onSelected: (val) {
                if (val) setState(() => _selectedAiAction = a['action']!);
              },
            );
          }).toList(),
        ),
        const SizedBox(height: 14),

        // Custom Prompt
        const Text('Custom Instructions (Optional)', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
        const SizedBox(height: 6),
        TextField(
          controller: _aiPromptController,
          maxLines: 3,
          decoration: InputDecoration(
            hintText: 'e.g. Acknowledge the Dean\'s welcoming speech; mention speaker has published over 100 IEEE papers...',
            hintStyle: const TextStyle(fontSize: 11, color: AppConstants.textSecondary),
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
            contentPadding: const EdgeInsets.all(10),
          ),
        ),
        const SizedBox(height: 12),

        // Run AI Button
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            icon: const Icon(Icons.auto_awesome, size: 16),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.purple.shade700,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            label: Text(_isAiBusy ? 'Generating with AI...' : 'Run Copilot on Segment'),
            onPressed: _isAiBusy ? null : () => _runAiOnSegment(_activeSegmentIndex, action: _selectedAiAction),
          ),
        ),
        const SizedBox(height: 16),

        if (_aiGeneratedDialogue != null && _aiGeneratedDialogue!.isNotEmpty) ...[
          const Text('Copilot Output Preview', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
          const SizedBox(height: 6),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Colors.grey.shade50,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.grey.shade300),
            ),
            child: Text(_aiGeneratedDialogue!, style: const TextStyle(fontSize: 12)),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: () {
                    setState(() {
                      activeSeg.dialogue = _aiGeneratedDialogue!;
                      if (_aiGeneratedDirections != null) {
                        activeSeg.stageDirections = _aiGeneratedDirections!;
                      }
                    });
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Applied to dialogue editor!')),
                    );
                  },
                  child: const Text('Apply to Editor', style: TextStyle(fontSize: 12)),
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }

  Widget _buildSegmentEditorPanel(McScriptSegment activeSeg) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Navigation row
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.arrow_back_ios, size: 16),
                  tooltip: 'Previous Segment',
                  onPressed: _activeSegmentIndex > 0
                      ? () => setState(() => _activeSegmentIndex--)
                      : null,
                ),
                Text('Segment ${_activeSegmentIndex + 1} of ${_segments.length}',
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                IconButton(
                  icon: const Icon(Icons.arrow_forward_ios, size: 16),
                  tooltip: 'Next Segment',
                  onPressed: _activeSegmentIndex < _segments.length - 1
                      ? () => setState(() => _activeSegmentIndex++)
                      : null,
                ),
              ],
            ),
            ElevatedButton.icon(
              icon: const Icon(Icons.check, size: 16),
              style: ElevatedButton.styleFrom(backgroundColor: AppConstants.pureBlack, foregroundColor: Colors.white),
              label: const Text('Save Script'),
              onPressed: () => _saveDraft(),
            ),
          ],
        ),
        const SizedBox(height: 14),

        // Title and MC Assignment
        Row(
          children: [
            Expanded(
              flex: 2,
              child: TextFormField(
                initialValue: activeSeg.title,
                key: ValueKey('title_${activeSeg.id}'),
                decoration: InputDecoration(
                  labelText: 'Segment Title',
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                ),
                onChanged: (val) => activeSeg.title = val,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              flex: 1,
              child: DropdownButtonFormField<String>(
                initialValue: _anchors.any((a) => a.name == activeSeg.assignedMc)
                    ? activeSeg.assignedMc
                    : (_anchors.isNotEmpty ? _anchors.first.name : 'MC 1'),
                decoration: InputDecoration(
                  labelText: 'Assigned MC',
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                ),
                items: _anchors.map((a) {
                  return DropdownMenuItem<String>(
                    value: a.name,
                    child: Text(a.name),
                  );
                }).toList(),
                onChanged: (val) {
                  if (val != null) setState(() => activeSeg.assignedMc = val);
                },
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),

        // Segment Specific Input Form
        _buildSegmentInputsForm(activeSeg),
        const SizedBox(height: 16),

        // Spoken Dialogue Editor
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('Spoken Dialogue (${activeSeg.assignedMc})',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
            TextButton.icon(
              icon: const Icon(Icons.auto_awesome, size: 14, color: Colors.purple),
              label: const Text('AI Draft', style: TextStyle(fontSize: 11, color: Colors.purple)),
              onPressed: () => _runAiOnSegment(_activeSegmentIndex),
            ),
          ],
        ),
        const SizedBox(height: 6),
        TextFormField(
          initialValue: activeSeg.dialogue,
          key: ValueKey('dialogue_${activeSeg.id}'),
          maxLines: 8,
          decoration: InputDecoration(
            hintText: 'e.g. (${activeSeg.assignedMc}): Good morning, everyone. We are delighted to welcome...',
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
            contentPadding: const EdgeInsets.all(12),
          ),
          onChanged: (val) => activeSeg.dialogue = val,
        ),
        const SizedBox(height: 16),

        // Stage Directions Editor
        const Text('Stage Directions (Enclosed in [Square Brackets])',
            style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
        const SizedBox(height: 6),
        TextFormField(
          initialValue: activeSeg.stageDirections,
          key: ValueKey('stagedir_${activeSeg.id}'),
          maxLines: 3,
          decoration: InputDecoration(
            hintText: 'e.g. [Anchor 1 steps to podium with warm smile; pauses for room silence]',
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
            contentPadding: const EdgeInsets.all(12),
          ),
          onChanged: (val) => activeSeg.stageDirections = val,
        ),
      ],
    );
  }

  // Segment inputs form depending on segment type
  Widget _buildSegmentInputsForm(McScriptSegment activeSeg) {
    final type = activeSeg.segmentType;

    if (type == 'speaker_introduction') {
      return Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.blue.shade50.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.blue.shade200),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.person, size: 16, color: Colors.blue),
                SizedBox(width: 6),
                Text('Speaker Introduction Details (Verified Facts)',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    initialValue: activeSeg.inputData['speaker_name']?.toString() ?? '',
                    decoration: const InputDecoration(labelText: 'Speaker Full Name *', isDense: true),
                    onChanged: (val) => activeSeg.inputData['speaker_name'] = val,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: TextFormField(
                    initialValue: activeSeg.inputData['speaker_designation']?.toString() ?? '',
                    decoration: const InputDecoration(labelText: 'Designation & Org', isDense: true),
                    onChanged: (val) => activeSeg.inputData['speaker_designation'] = val,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            TextFormField(
              initialValue: activeSeg.inputData['speaker_bio']?.toString() ?? '',
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: 'Bio Highlights (Degrees, Top 2% Scientist, IEEE Fellow, Awards)',
                isDense: true,
              ),
              onChanged: (val) => activeSeg.inputData['speaker_bio'] = val,
            ),
            const SizedBox(height: 8),
            TextFormField(
              initialValue: activeSeg.inputData['presentation_topic']?.toString() ?? '',
              decoration: const InputDecoration(labelText: 'Talk / Keynote Topic', isDense: true),
              onChanged: (val) => activeSeg.inputData['presentation_topic'] = val,
            ),
          ],
        ),
      );
    }

    if (type == 'prize_distribution') {
      return Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.amber.shade50.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.amber.shade300),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.emoji_events, size: 16, color: Colors.orange),
                SizedBox(width: 6),
                Text('Prize Distribution & Winners Roster',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
              ],
            ),
            const SizedBox(height: 8),
            TextFormField(
              initialValue: activeSeg.inputData['competition_name']?.toString() ?? '',
              decoration: const InputDecoration(labelText: 'Competition Name', isDense: true),
              onChanged: (val) => activeSeg.inputData['competition_name'] = val,
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    initialValue: activeSeg.inputData['winner_1st']?.toString() ?? '',
                    decoration: const InputDecoration(labelText: '1st Place Winner & Team', isDense: true),
                    onChanged: (val) => activeSeg.inputData['winner_1st'] = val,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextFormField(
                    initialValue: activeSeg.inputData['winner_2nd']?.toString() ?? '',
                    decoration: const InputDecoration(labelText: '2nd Place Winner', isDense: true),
                    onChanged: (val) => activeSeg.inputData['winner_2nd'] = val,
                  ),
                ),
              ],
            ),
          ],
        ),
      );
    }

    if (type == 'dignitary_introduction') {
      return Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.teal.shade50.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.teal.shade200),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.account_balance, size: 16, color: Colors.teal),
                SizedBox(width: 6),
                Text('Dignitary Dais Hierarchy', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
              ],
            ),
            const SizedBox(height: 8),
            TextFormField(
              initialValue: activeSeg.inputData['chief_guest']?.toString() ?? '',
              decoration: const InputDecoration(labelText: 'Chief Guest Name & Designation', isDense: true),
              onChanged: (val) => activeSeg.inputData['chief_guest'] = val,
            ),
            const SizedBox(height: 8),
            TextFormField(
              initialValue: activeSeg.inputData['hod_name']?.toString() ?? '',
              decoration: const InputDecoration(labelText: 'Head of Department / Director', isDense: true),
              onChanged: (val) => activeSeg.inputData['hod_name'] = val,
            ),
          ],
        ),
      );
    }

    return const SizedBox.shrink();
  }

  // ---------------------------------------------------------------------------
  // Tab 3: Stage Teleprompter & Validation
  // ---------------------------------------------------------------------------
  Widget _buildStageTeleprompterTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Validation Card
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppConstants.pureWhite,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppConstants.borderLight),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.checklist_rtl, size: 20),
                        SizedBox(width: 8),
                        Text('Pre-Flight Stage Verification', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                      ],
                    ),
                    ElevatedButton.icon(
                      icon: const Icon(Icons.refresh, size: 14),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppConstants.pureBlack,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                      ),
                      label: Text(_isValidating ? 'Validating...' : 'Run Checklist'),
                      onPressed: _isValidating ? null : _runPreflightValidation,
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                if (_validationResult != null) ...[
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: _validationResult!.isValid ? Colors.green.shade50 : Colors.orange.shade50,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(
                            color: _validationResult!.isValid ? Colors.green.shade300 : Colors.orange.shade300,
                          ),
                        ),
                        child: Text(
                          _validationResult!.isValid ? 'STAGE READY' : 'REVISION NEEDED',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: _validationResult!.isValid ? Colors.green.shade800 : Colors.orange.shade800,
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(6),
                          child: LinearProgressIndicator(
                            value: _validationResult!.completionPercentage / 100,
                            backgroundColor: Colors.grey.shade200,
                            color: _validationResult!.completionPercentage >= 80 ? Colors.green : Colors.orange,
                            minHeight: 8,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text('${_validationResult!.completionPercentage}% Complete',
                          style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                    ],
                  ),
                  if (_validationResult!.warnings.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    Column(
                      children: _validationResult!.warnings.map((w) {
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 4),
                          child: Row(
                            children: [
                              const Icon(Icons.warning_amber_rounded, size: 14, color: Colors.orange),
                              const SizedBox(width: 6),
                              Expanded(child: Text(w, style: const TextStyle(fontSize: 11, color: Colors.black87))),
                            ],
                          ),
                        );
                      }).toList(),
                    ),
                  ],
                ] else ...[
                  const Text('Run pre-flight checklist to verify all dialogue, anchor rosters, and placeholder tags.',
                      style: TextStyle(fontSize: 12, color: AppConstants.textSecondary)),
                ],
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Teleprompter Controls Bar
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  const Text('Teleprompter Font Size: ', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                  ChoiceChip(
                    label: const Text('Normal'),
                    selected: _teleprompterFontSize == 16.0,
                    onSelected: (val) => setState(() => _teleprompterFontSize = 16.0),
                  ),
                  const SizedBox(width: 6),
                  ChoiceChip(
                    label: const Text('Large'),
                    selected: _teleprompterFontSize == 20.0,
                    onSelected: (val) => setState(() => _teleprompterFontSize = 20.0),
                  ),
                  const SizedBox(width: 6),
                  ChoiceChip(
                    label: const Text('Stage XL'),
                    selected: _teleprompterFontSize == 24.0,
                    onSelected: (val) => setState(() => _teleprompterFontSize = 24.0),
                  ),
                ],
              ),
              Wrap(
                spacing: 8,
                children: [
                  OutlinedButton.icon(
                    icon: const Icon(Icons.download, size: 16),
                    label: const Text('Export Stage DOCX'),
                    style: OutlinedButton.styleFrom(foregroundColor: AppConstants.pureBlack),
                    onPressed: _exportDocx,
                  ),
                  OutlinedButton.icon(
                    icon: const Icon(Icons.cloud_upload_outlined, size: 16),
                    label: const Text('Upload to Drive'),
                    style: OutlinedButton.styleFrom(foregroundColor: AppConstants.pureBlack),
                    onPressed: _uploadToGoogleDrive,
                  ),
                  if (_driveWebViewLink != null && _driveWebViewLink!.isNotEmpty)
                    OutlinedButton.icon(
                      icon: const Icon(Icons.cloud_done, size: 16, color: Colors.blueGrey),
                      label: const Text('Drive Link'),
                      style: OutlinedButton.styleFrom(foregroundColor: AppConstants.pureBlack),
                      onPressed: () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('Drive link: $_driveWebViewLink')),
                        );
                      },
                    ),
                  ElevatedButton.icon(
                    icon: const Icon(Icons.send, size: 16),
                    label: const Text('Submit for Review'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppConstants.pureBlack,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                    ),
                    onPressed: _submitForReview,
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Teleprompter Live Reader Box
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: AppConstants.pureWhite,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppConstants.borderLight),
              boxShadow: [
                BoxShadow(color: Colors.black.withValues(alpha: 0.03), blurRadius: 6, offset: const Offset(0, 3)),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header block
                Center(
                  child: Column(
                    children: [
                      Text(
                        _deptController.text.toUpperCase(),
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, letterSpacing: 1.2),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        _clubController.text,
                        style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _titleController.text,
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 22),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Venue: ${_venueController.text} • Tone: $_selectedTone',
                        style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                const Divider(),
                const SizedBox(height: 16),

                // Anchor Dialogue Flows
                ListView.separated(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: _segments.length,
                  separatorBuilder: (context, index) => const Padding(
                    padding: EdgeInsets.symmetric(vertical: 16),
                    child: Divider(color: AppConstants.borderLight),
                  ),
                  itemBuilder: (ctx, i) {
                    final seg = _segments[i];
                    if (!seg.isEnabled) return const SizedBox.shrink();

                    final isAnchor1 = seg.assignedMc == (_anchors.isNotEmpty ? _anchors.first.name : 'MC 1');
                    final speakerColor = isAnchor1 ? const Color(0xFF0F3A60) : const Color(0xFF005953);

                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            CircleAvatar(
                              radius: 10,
                              backgroundColor: AppConstants.pureBlack,
                              child: Text('${i + 1}', style: const TextStyle(color: Colors.white, fontSize: 9)),
                            ),
                            const SizedBox(width: 8),
                            Text(seg.title.toUpperCase(),
                                style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 12,
                                  color: AppConstants.textSecondary,
                                  letterSpacing: 0.8,
                                )),
                          ],
                        ),
                        if (seg.stageDirections.isNotEmpty) ...[
                          const SizedBox(height: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: Colors.grey.shade100,
                              borderRadius: BorderRadius.circular(4),
                              border: Border.all(color: Colors.grey.shade300),
                            ),
                            child: Text(
                              seg.stageDirections.startsWith('[') ? seg.stageDirections : '[${seg.stageDirections}]',
                              style: TextStyle(
                                fontStyle: FontStyle.italic,
                                color: Colors.grey.shade800,
                                fontSize: _teleprompterFontSize - 2,
                              ),
                            ),
                          ),
                        ],
                        const SizedBox(height: 10),
                        Text(
                          seg.dialogue.isNotEmpty
                              ? seg.dialogue
                              : '(${seg.assignedMc}): [Dialogue pending generation...]',
                          style: TextStyle(
                            fontSize: _teleprompterFontSize,
                            color: seg.dialogue.isNotEmpty ? speakerColor : Colors.grey,
                            fontWeight: FontWeight.w500,
                            height: 1.6,
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
