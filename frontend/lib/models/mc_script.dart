import 'package:flutter/material.dart';

class McAnchor {
  final int id;
  final String name;
  final String role;

  const McAnchor({
    required this.id,
    required this.name,
    required this.role,
  });

  factory McAnchor.fromJson(Map<String, dynamic> json) {
    int parseInt(dynamic val, [int def = 1]) {
      if (val is num) return val.toInt();
      if (val is String) return int.tryParse(val) ?? def;
      return def;
    }

    return McAnchor(
      id: parseInt(json['id'], 1),
      name: json['name']?.toString() ?? 'Anchor',
      role: json['role']?.toString() ?? 'Host',
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'role': role,
  };
}

class McScriptSegment {
  final String id;
  final int? intId;
  String segmentType;
  String title;
  int sequenceOrder;
  String assignedMc;
  bool isEnabled;
  Map<String, dynamic> inputData;
  String dialogue;
  String stageDirections;
  String? notes;

  McScriptSegment({
    required this.id,
    this.intId,
    this.segmentType = 'custom',
    required this.title,
    this.sequenceOrder = 1,
    required this.assignedMc,
    this.isEnabled = true,
    Map<String, dynamic>? inputData,
    required this.dialogue,
    this.stageDirections = '',
    this.notes,
  }) : inputData = inputData ?? {};

  // Backward compatibility getter/setter for anchor
  String get anchor => assignedMc;
  set anchor(String val) => assignedMc = val;

  String? get stageDirection => stageDirections.isNotEmpty ? stageDirections : null;
  set stageDirection(String? val) => stageDirections = val ?? '';

  factory McScriptSegment.fromJson(Map<String, dynamic> json) {
    int? parsedIntId;
    if (json['id'] is num) {
      parsedIntId = (json['id'] as num).toInt();
    } else if (json['id'] is String) {
      parsedIntId = int.tryParse(json['id']);
    }

    int seq = 1;
    if (json['sequence_order'] is num) {
      seq = (json['sequence_order'] as num).toInt();
    } else if (json['sequence_order'] is String) {
      seq = int.tryParse(json['sequence_order']) ?? 1;
    }

    Map<String, dynamic> inputs = {};
    if (json['input_data'] is Map) {
      inputs = Map<String, dynamic>.from(json['input_data']);
    }

    return McScriptSegment(
      id: json['id']?.toString() ?? DateTime.now().millisecondsSinceEpoch.toString(),
      intId: parsedIntId,
      segmentType: json['segment_type']?.toString() ?? 'custom',
      title: json['title']?.toString() ?? 'Segment',
      sequenceOrder: seq,
      assignedMc: json['assigned_mc']?.toString() ?? json['anchor']?.toString() ?? 'MC 1',
      isEnabled: json['is_enabled'] != false,
      inputData: inputs,
      dialogue: json['generated_dialogue']?.toString() ?? json['dialogue']?.toString() ?? '',
      stageDirections: json['stage_directions']?.toString() ?? json['stage_direction']?.toString() ?? '',
      notes: json['notes']?.toString(),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': intId ?? id,
    'segment_type': segmentType,
    'title': title,
    'sequence_order': sequenceOrder,
    'assigned_mc': assignedMc,
    'anchor': assignedMc,
    'is_enabled': isEnabled,
    'input_data': inputData,
    'dialogue': dialogue,
    'generated_dialogue': dialogue,
    'stage_directions': stageDirections,
    'stage_direction': stageDirections,
    'notes': notes,
  };
}

class McTemplateSegment {
  final int id;
  final int templateId;
  final String segmentType;
  final String title;
  final int sequenceOrder;
  final String defaultMcAssignment;
  final String? aiInstructions;
  final String? defaultStageDirections;

  McTemplateSegment({
    required this.id,
    required this.templateId,
    required this.segmentType,
    required this.title,
    required this.sequenceOrder,
    required this.defaultMcAssignment,
    this.aiInstructions,
    this.defaultStageDirections,
  });

  factory McTemplateSegment.fromJson(Map<String, dynamic> json) {
    int parseInt(dynamic val, [int def = 0]) {
      if (val is num) return val.toInt();
      if (val is String) return int.tryParse(val) ?? def;
      return def;
    }

    return McTemplateSegment(
      id: parseInt(json['id']),
      templateId: parseInt(json['template_id']),
      segmentType: json['segment_type']?.toString() ?? 'custom',
      title: json['title']?.toString() ?? 'Segment',
      sequenceOrder: parseInt(json['sequence_order'], 1),
      defaultMcAssignment: json['default_mc_assignment']?.toString() ?? 'MC 1',
      aiInstructions: json['ai_instructions']?.toString(),
      defaultStageDirections: json['default_stage_directions']?.toString(),
    );
  }
}

class McTemplate {
  final int id;
  final String name;
  final String eventType;
  final String? description;
  final int? createdBy;
  final String? creatorName;
  final bool isPublicToTeam;
  final bool isDefault;
  final int segmentCount;
  final List<McTemplateSegment> segments;
  final String? createdAt;
  final String? updatedAt;

  McTemplate({
    required this.id,
    required this.name,
    required this.eventType,
    this.description,
    this.createdBy,
    this.creatorName,
    this.isPublicToTeam = true,
    this.isDefault = false,
    this.segmentCount = 0,
    this.segments = const [],
    this.createdAt,
    this.updatedAt,
  });

  factory McTemplate.fromJson(Map<String, dynamic> json) {
    int parseInt(dynamic val, [int def = 0]) {
      if (val is num) return val.toInt();
      if (val is String) return int.tryParse(val) ?? def;
      return def;
    }

    var rawSegs = json['segments'];
    List<McTemplateSegment> parsedSegs = [];
    if (rawSegs is List) {
      parsedSegs = rawSegs.map((s) => McTemplateSegment.fromJson(s as Map<String, dynamic>)).toList();
    }

    return McTemplate(
      id: parseInt(json['id']),
      name: json['name']?.toString() ?? 'Template',
      eventType: json['event_type']?.toString() ?? 'Department Event',
      description: json['description']?.toString(),
      createdBy: json['created_by'] != null ? parseInt(json['created_by']) : null,
      creatorName: json['creator_name']?.toString(),
      isPublicToTeam: json['is_public_to_team'] == true,
      isDefault: json['is_default'] == true,
      segmentCount: parseInt(json['segment_count'], parsedSegs.length),
      segments: parsedSegs,
      createdAt: json['created_at']?.toString(),
      updatedAt: json['updated_at']?.toString(),
    );
  }
}

class EventTypeOption {
  final String eventType;
  final String description;
  final int suggestedSegmentCount;
  final List<Map<String, dynamic>> suggestedSegments;

  EventTypeOption({
    required this.eventType,
    required this.description,
    required this.suggestedSegmentCount,
    required this.suggestedSegments,
  });

  factory EventTypeOption.fromJson(Map<String, dynamic> json) {
    int parseInt(dynamic val, [int def = 0]) {
      if (val is num) return val.toInt();
      if (val is String) return int.tryParse(val) ?? def;
      return def;
    }

    var raw = json['suggested_segments'];
    List<Map<String, dynamic>> segs = [];
    if (raw is List) {
      segs = raw.map((s) => Map<String, dynamic>.from(s as Map)).toList();
    }

    return EventTypeOption(
      eventType: json['event_type']?.toString() ?? 'General Event',
      description: json['description']?.toString() ?? '',
      suggestedSegmentCount: parseInt(json['suggested_segment_count'], segs.length),
      suggestedSegments: segs,
    );
  }
}

class ScriptValidationResult {
  final bool isValid;
  final List<String> errors;
  final List<String> warnings;
  final int completionPercentage;
  final int totalSegments;
  final int enabledSegments;
  final String scriptStatus;

  ScriptValidationResult({
    required this.isValid,
    required this.errors,
    required this.warnings,
    required this.completionPercentage,
    required this.totalSegments,
    required this.enabledSegments,
    required this.scriptStatus,
  });

  factory ScriptValidationResult.fromJson(Map<String, dynamic> json) {
    int parseInt(dynamic val, [int def = 0]) {
      if (val is num) return val.toInt();
      if (val is String) return int.tryParse(val) ?? def;
      return def;
    }

    List<String> parseList(dynamic val) {
      if (val is List) return val.map((e) => e.toString()).toList();
      return [];
    }

    return ScriptValidationResult(
      isValid: json['is_valid'] == true,
      errors: parseList(json['errors']),
      warnings: parseList(json['warnings']),
      completionPercentage: parseInt(json['completion_percentage']),
      totalSegments: parseInt(json['total_segments']),
      enabledSegments: parseInt(json['enabled_segments']),
      scriptStatus: json['script_status']?.toString() ?? 'draft',
    );
  }
}

class McScriptReview {
  final int id;
  final int scriptId;
  final int? reviewerId;
  final String? reviewerName;
  final String decision;
  final String? comments;
  final String? createdAt;

  const McScriptReview({
    required this.id,
    required this.scriptId,
    this.reviewerId,
    this.reviewerName,
    required this.decision,
    this.comments,
    this.createdAt,
  });

  factory McScriptReview.fromJson(Map<String, dynamic> json) {
    int parseInt(dynamic val, [int def = 0]) {
      if (val is num) return val.toInt();
      if (val is String) return int.tryParse(val) ?? def;
      return def;
    }

    int? parseOptionalInt(dynamic val) {
      if (val == null) return null;
      if (val is num) return val.toInt();
      if (val is String) return int.tryParse(val);
      return null;
    }

    return McScriptReview(
      id: parseInt(json['id']),
      scriptId: parseInt(json['script_id']),
      reviewerId: parseOptionalInt(json['reviewer_id']),
      reviewerName: json['reviewer_name']?.toString(),
      decision: json['decision']?.toString() ?? 'reviewed',
      comments: json['comments']?.toString(),
      createdAt: json['created_at']?.toString(),
    );
  }
}

class McScript {
  final int id;
  String title;
  int? eventId;
  String? eventName;
  int? templateId;
  int? taskId;
  String? taskTitle;
  int? folderId;
  String? folderName;
  int? createdBy;
  String? creatorName;
  String status;
  String? eventType;
  String? venue;
  String? eventDate;
  String? duration;
  String language;
  String tone;
  int numberOfAnchors;
  List<McAnchor> anchors;
  Map<String, dynamic> eventMetadata;
  String? chiefGuestDetails;
  String? facultySpeakerDetails;
  String? eventSchedule;
  String? fullScriptContent;
  List<McScriptSegment> segments;
  List<McScriptReview> reviews;
  bool hasGeneratedDocx;
  String? driveFileId;
  String? driveFolderId;
  String? driveWebViewLink;
  String? createdAt;
  String? updatedAt;

  McScript({
    required this.id,
    required this.title,
    this.eventId,
    this.eventName,
    this.templateId,
    this.taskId,
    this.taskTitle,
    this.folderId,
    this.folderName,
    this.createdBy,
    this.creatorName,
    required this.status,
    this.eventType,
    this.venue,
    this.eventDate,
    this.duration,
    this.language = 'English',
    this.tone = 'Formal',
    this.numberOfAnchors = 2,
    this.anchors = const [],
    Map<String, dynamic>? eventMetadata,
    this.chiefGuestDetails,
    this.facultySpeakerDetails,
    this.eventSchedule,
    this.fullScriptContent,
    this.segments = const [],
    this.reviews = const [],
    this.hasGeneratedDocx = false,
    this.driveFileId,
    this.driveFolderId,
    this.driveWebViewLink,
    this.createdAt,
    this.updatedAt,
  }) : eventMetadata = eventMetadata ?? {};

  factory McScript.fromJson(Map<String, dynamic> json) {
    int parseInt(dynamic val, [int def = 0]) {
      if (val is num) return val.toInt();
      if (val is String) return int.tryParse(val) ?? def;
      return def;
    }

    int? parseOptionalInt(dynamic val) {
      if (val == null) return null;
      if (val is num) return val.toInt();
      if (val is String) return int.tryParse(val);
      return null;
    }

    var rawAnchors = json['anchors'];
    List<McAnchor> parsedAnchors = [];
    if (rawAnchors is List) {
      parsedAnchors = rawAnchors.map((a) => McAnchor.fromJson(a as Map<String, dynamic>)).toList();
    }

    var rawSegments = json['segments'];
    List<McScriptSegment> parsedSegments = [];
    if (rawSegments is List) {
      parsedSegments = rawSegments.map((s) => McScriptSegment.fromJson(s as Map<String, dynamic>)).toList();
    }

    var rawReviews = json['reviews'];
    List<McScriptReview> parsedReviews = [];
    if (rawReviews is List) {
      parsedReviews = rawReviews.map((r) => McScriptReview.fromJson(r as Map<String, dynamic>)).toList();
    }

    Map<String, dynamic> meta = {};
    if (json['event_metadata'] is Map) {
      meta = Map<String, dynamic>.from(json['event_metadata']);
    }

    return McScript(
      id: parseInt(json['id']),
      title: json['title']?.toString() ?? 'Hosting Script',
      eventId: parseOptionalInt(json['event_id']),
      eventName: json['event_name']?.toString(),
      templateId: parseOptionalInt(json['template_id']),
      taskId: parseOptionalInt(json['task_id']),
      taskTitle: json['task_title']?.toString(),
      folderId: parseOptionalInt(json['folder_id']),
      folderName: json['folder_name']?.toString(),
      createdBy: parseOptionalInt(json['created_by']),
      creatorName: json['creator_name']?.toString(),
      status: json['status']?.toString() ?? 'draft',
      eventType: json['event_type']?.toString(),
      venue: json['venue']?.toString(),
      eventDate: json['event_date']?.toString(),
      duration: json['duration']?.toString(),
      language: json['language']?.toString() ?? 'English',
      tone: json['tone']?.toString() ?? 'Formal',
      numberOfAnchors: parseInt(json['number_of_anchors'], 2),
      anchors: parsedAnchors,
      eventMetadata: meta,
      chiefGuestDetails: json['chief_guest_details']?.toString(),
      facultySpeakerDetails: json['faculty_speaker_details']?.toString(),
      eventSchedule: json['event_schedule']?.toString(),
      fullScriptContent: json['full_script_content']?.toString(),
      segments: parsedSegments,
      reviews: parsedReviews,
      hasGeneratedDocx: json['has_generated_docx'] == true,
      driveFileId: json['drive_file_id']?.toString(),
      driveFolderId: json['drive_folder_id']?.toString(),
      driveWebViewLink: json['drive_web_view_link']?.toString(),
      createdAt: json['created_at']?.toString(),
      updatedAt: json['updated_at']?.toString(),
    );
  }

  String get statusLabel {
    switch (status) {
      case 'draft':
        return 'Draft';
      case 'in_progress':
        return 'In Progress';
      case 'ready_for_review':
      case 'submitted':
        return 'Ready for Review';
      case 'revision_requested':
        return 'Revision Requested';
      case 'finalized':
      case 'approved':
        return 'Finalized';
      case 'uploaded':
        return 'Uploaded to Drive';
      default:
        return status.toUpperCase();
    }
  }

  Color get statusColor {
    switch (status) {
      case 'draft':
        return Colors.grey.shade700;
      case 'in_progress':
        return Colors.blue.shade700;
      case 'ready_for_review':
      case 'submitted':
        return Colors.orange.shade800;
      case 'revision_requested':
        return Colors.red.shade700;
      case 'finalized':
      case 'approved':
        return Colors.teal.shade700;
      case 'uploaded':
        return Colors.green.shade800;
      default:
        return Colors.grey.shade600;
    }
  }

  bool get isApproved => status == 'approved' || status == 'finalized' || status == 'uploaded';
  bool get isUploaded => driveFileId != null && driveFileId!.isNotEmpty;
}
