import 'dart:convert';

class FolderDocument {
  final int id;
  final int folderId;
  final String fileName;
  final int fileSize;
  final String contentType;
  final String storageProvider;
  final String? downloadUrl;
  final int uploadedById;
  final String uploadedByName;
  final DateTime createdAt;

  FolderDocument({
    required this.id,
    required this.folderId,
    required this.fileName,
    required this.fileSize,
    required this.contentType,
    required this.storageProvider,
    this.downloadUrl,
    required this.uploadedById,
    required this.uploadedByName,
    required this.createdAt,
  });

  factory FolderDocument.fromJson(Map<String, dynamic> json) {
    int parseInt(dynamic val, [int def = 0]) {
      if (val is num) return val.toInt();
      if (val is String) return int.tryParse(val) ?? def;
      return def;
    }

    return FolderDocument(
      id: parseInt(json['id']),
      folderId: parseInt(json['folder_id']),
      fileName: json['file_name']?.toString() ?? json['original_filename']?.toString() ?? 'Unnamed Document',
      fileSize: parseInt(json['file_size']),
      contentType: json['content_type']?.toString() ?? 'application/octet-stream',
      storageProvider: json['storage_provider']?.toString() ?? 'local',
      downloadUrl: json['download_url']?.toString(),
      uploadedById: parseInt(json['uploaded_by_id'] ?? json['uploaded_by']),
      uploadedByName: json['uploaded_by_name']?.toString() ?? json['uploader_name']?.toString() ?? 'User',
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }

  String get formattedSize {
    if (fileSize < 1024) return '$fileSize B';
    if (fileSize < 1024 * 1024) return '${(fileSize / 1024).toStringAsFixed(1)} KB';
    return '${(fileSize / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
}

class EventFolder {
  final int id;
  final String name;
  final String? description;
  final int? eventId;
  final int createdById;
  final String createdByName;
  final int documentCount;
  final List<FolderDocument> documents;
  final String? linkedDriveFolderId;
  final String? linkedDriveFolderName;
  final String? driveWebViewLink;
  final DateTime createdAt;
  final DateTime updatedAt;

  EventFolder({
    required this.id,
    required this.name,
    this.description,
    this.eventId,
    required this.createdById,
    required this.createdByName,
    required this.documentCount,
    this.documents = const [],
    this.linkedDriveFolderId,
    this.linkedDriveFolderName,
    this.driveWebViewLink,
    required this.createdAt,
    required this.updatedAt,
  });

  factory EventFolder.fromJson(Map<String, dynamic> json) {
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

    final docsRaw = json['documents'] as List<dynamic>?;
    final docs = docsRaw != null
        ? docsRaw.map((d) => FolderDocument.fromJson(d as Map<String, dynamic>)).toList()
        : <FolderDocument>[];

    return EventFolder(
      id: parseInt(json['id']),
      name: json['name']?.toString() ?? 'Untitled Folder',
      description: json['description']?.toString(),
      eventId: parseOptionalInt(json['event_id']),
      createdById: parseInt(json['created_by_id'] ?? json['created_by']),
      createdByName: json['created_by_name']?.toString() ?? json['creator_name']?.toString() ?? 'User',
      documentCount: parseInt(json['document_count'], docs.length),
      documents: docs,
      linkedDriveFolderId: json['linked_drive_folder_id']?.toString(),
      linkedDriveFolderName: json['linked_drive_folder_name']?.toString(),
      driveWebViewLink: json['drive_web_view_link']?.toString(),
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
      updatedAt: json['updated_at'] != null
          ? DateTime.tryParse(json['updated_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }
}

class SpeakerEntry {
  String name;
  String title;
  String organization;
  String contact;

  SpeakerEntry({
    this.name = '',
    this.title = '',
    this.organization = '',
    this.contact = '',
  });

  factory SpeakerEntry.fromJson(Map<String, dynamic> json) {
    return SpeakerEntry(
      name: json['name']?.toString() ?? '',
      title: json['title']?.toString() ?? '',
      organization: json['organization']?.toString() ?? '',
      contact: json['contact']?.toString() ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'name': name.trim(),
        'title': title.trim(),
        'organization': organization.trim(),
        'contact': contact.trim(),
      };
}

class ActivityReport {
  final int id;
  final String title;
  final String? description;
  final String status;
  final int createdById;
  final String createdByName;
  final Map<String, dynamic> data;
  final String? generatedDocxPath;
  final DateTime createdAt;
  final DateTime updatedAt;

  ActivityReport({
    required this.id,
    required this.title,
    this.description,
    required this.status,
    required this.createdById,
    required this.createdByName,
    required this.data,
    this.generatedDocxPath,
    required this.createdAt,
    required this.updatedAt,
  });

  factory ActivityReport.fromJson(Map<String, dynamic> json) {
    Map<String, dynamic> dataMap = {};
    if (json['data'] is Map) {
      dataMap = Map<String, dynamic>.from(json['data'] as Map);
    } else if (json['data'] is String && (json['data'] as String).isNotEmpty) {
      try {
        dataMap = jsonDecode(json['data'] as String) as Map<String, dynamic>;
      } catch (_) {}
    }

    return ActivityReport(
      id: (json['id'] as num).toInt(),
      title: json['title']?.toString() ?? 'Untitled Report',
      description: json['description']?.toString(),
      status: json['status']?.toString() ?? 'draft',
      createdById: (json['created_by_id'] as num?)?.toInt() ?? (json['created_by'] as num?)?.toInt() ?? 0,
      createdByName: json['created_by_name']?.toString() ?? json['creator_name']?.toString() ?? 'User',
      data: dataMap,
      generatedDocxPath: json['generated_docx_path']?.toString(),
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
      updatedAt: json['updated_at'] != null
          ? DateTime.tryParse(json['updated_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }
}
