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
    return FolderDocument(
      id: (json['id'] as num).toInt(),
      folderId: (json['folder_id'] as num).toInt(),
      fileName: json['file_name']?.toString() ?? json['original_filename']?.toString() ?? 'Unnamed Document',
      fileSize: (json['file_size'] as num?)?.toInt() ?? 0,
      contentType: json['content_type']?.toString() ?? 'application/octet-stream',
      storageProvider: json['storage_provider']?.toString() ?? 'local',
      downloadUrl: json['download_url']?.toString(),
      uploadedById: (json['uploaded_by_id'] as num?)?.toInt() ?? (json['uploaded_by'] as num?)?.toInt() ?? 0,
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
    required this.createdAt,
    required this.updatedAt,
  });

  factory EventFolder.fromJson(Map<String, dynamic> json) {
    final docsRaw = json['documents'] as List<dynamic>?;
    final docs = docsRaw != null
        ? docsRaw.map((d) => FolderDocument.fromJson(d as Map<String, dynamic>)).toList()
        : <FolderDocument>[];

    return EventFolder(
      id: (json['id'] as num).toInt(),
      name: json['name']?.toString() ?? 'Untitled Folder',
      description: json['description']?.toString(),
      eventId: (json['event_id'] as num?)?.toInt(),
      createdById: (json['created_by_id'] as num?)?.toInt() ?? (json['created_by'] as num?)?.toInt() ?? 0,
      createdByName: json['created_by_name']?.toString() ?? json['creator_name']?.toString() ?? 'User',
      documentCount: (json['document_count'] as num?)?.toInt() ?? docs.length,
      documents: docs,
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
