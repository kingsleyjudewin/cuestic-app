import 'dart:convert';
import 'package:flutter/foundation.dart';
import '../models/documentation.dart';
import 'api_client.dart';

class DocumentationService extends ChangeNotifier {
  final ApiClient apiClient;

  DocumentationService({required this.apiClient});

  // ---------------------------------------------------------------------------
  // Event Folders
  // ---------------------------------------------------------------------------
  Future<List<EventFolder>> fetchFolders() async {
    final res = await apiClient.get('/documentation/folders');
    if (res is List) {
      return res.map((f) => EventFolder.fromJson(f as Map<String, dynamic>)).toList();
    }
    return [];
  }

  Future<EventFolder> createFolder({
    required String name,
    String? description,
    int? eventId,
  }) async {
    final payload = <String, dynamic>{
      'name': name.trim(),
      if (description?.trim().isNotEmpty ?? false) 'description': description!.trim(),
      'event_id': ?eventId,
    };
    final res = await apiClient.post('/documentation/folders', body: payload);
    return EventFolder.fromJson(res as Map<String, dynamic>);
  }

  Future<EventFolder> getFolder(int folderId) async {
    final res = await apiClient.get('/documentation/folders/$folderId');
    return EventFolder.fromJson(res as Map<String, dynamic>);
  }

  Future<void> deleteFolder(int folderId) async {
    await apiClient.delete('/documentation/folders/$folderId');
    notifyListeners();
  }

  // ---------------------------------------------------------------------------
  // Folder Documents (Upload, Download, Delete)
  // ---------------------------------------------------------------------------
  Future<FolderDocument> uploadDocument({
    required int folderId,
    required List<int> fileBytes,
    required String filename,
  }) async {
    final res = await apiClient.uploadMultipart(
      '/documentation/folders/$folderId/documents',
      fileBytes: fileBytes,
      filename: filename,
    );
    notifyListeners();
    return FolderDocument.fromJson(res as Map<String, dynamic>);
  }

  Future<List<int>> downloadDocument(int documentId) async {
    return await apiClient.getBinary('/documentation/documents/$documentId/download');
  }

  Future<void> deleteDocument(int documentId) async {
    await apiClient.delete('/documentation/documents/$documentId');
    notifyListeners();
  }

  // ---------------------------------------------------------------------------
  // Activity Reports
  // ---------------------------------------------------------------------------
  Future<List<ActivityReport>> fetchReports() async {
    final res = await apiClient.get('/documentation/reports');
    if (res is List) {
      return res.map((r) => ActivityReport.fromJson(r as Map<String, dynamic>)).toList();
    }
    return [];
  }

  Future<ActivityReport> createReport({
    required String title,
    String? description,
    Map<String, dynamic>? data,
  }) async {
    final payload = <String, dynamic>{
      'title': title.trim(),
      if (description?.trim().isNotEmpty ?? false) 'description': description!.trim(),
      'data': ?data,
    };
    final res = await apiClient.post('/documentation/reports', body: payload);
    notifyListeners();
    return ActivityReport.fromJson(res as Map<String, dynamic>);
  }

  Future<ActivityReport> getReport(int reportId) async {
    final res = await apiClient.get('/documentation/reports/$reportId');
    return ActivityReport.fromJson(res as Map<String, dynamic>);
  }

  Future<ActivityReport> updateReport(
    int reportId, {
    String? title,
    String? description,
    Map<String, dynamic>? data,
    String? status,
  }) async {
    final payload = <String, dynamic>{};
    if (title != null) payload['title'] = title.trim();
    if (description != null) payload['description'] = description.trim();
    if (data != null) payload['data'] = data;
    if (status != null) payload['status'] = status;

    final res = await apiClient.put('/documentation/reports/$reportId', body: payload);
    notifyListeners();
    return ActivityReport.fromJson(res as Map<String, dynamic>);
  }

  Future<void> deleteReport(int reportId) async {
    await apiClient.delete('/documentation/reports/$reportId');
    notifyListeners();
  }

  // ---------------------------------------------------------------------------
  // AI Copilot Assist & Model Management
  // ---------------------------------------------------------------------------
  Future<List<Map<String, dynamic>>> fetchAvailableAiModels() async {
    final res = await apiClient.get('/documentation/ai/models');
    if (res is List) {
      return res.map((m) => Map<String, dynamic>.from(m as Map)).toList();
    }
    return [];
  }

  Future<List<Map<String, dynamic>>> fetchDriveImages() async {
    final res = await apiClient.get('/documentation/drive-images');
    if (res is List) {
      return res.map((m) => Map<String, dynamic>.from(m as Map)).toList();
    }
    return [];
  }

  Future<List<int>> downloadDocumentBytes(int documentId) async {
    return await apiClient.getBinary('/documentation/documents/$documentId/download');
  }

  Future<Map<String, dynamic>> analyzePoster({
    int? reportId,
    Uint8List? imageBytes,
    String? fileName,
    int? documentId,
    String? provider,
    String? model,
  }) async {
    final endpoint = reportId != null
        ? '/documentation/reports/$reportId/analyze-poster'
        : '/documentation/reports/analyze-poster';

    final payload = <String, dynamic>{
      'provider': ?provider,
      'model': ?model,
    };

    if (imageBytes != null) {
      payload['image_base64'] = base64Encode(imageBytes);
      payload['filename'] = fileName ?? 'poster.jpg';
    } else if (documentId != null) {
      payload['document_id'] = documentId;
    }

    final res = await apiClient.post(endpoint, body: payload);
    return res is Map<String, dynamic> ? res : {};
  }

  Future<Map<String, dynamic>> aiAssist({
    int? reportId,
    required String fieldKey,
    required String fieldLabel,
    required String instruction,
    String? currentContent,
    String action = 'draft',
    String? provider,
    String? model,
    Uint8List? imageBytes,
    int? documentId,
    Map<String, dynamic>? posterContext,
    Map<String, dynamic>? reportContext,
  }) async {
    final payload = <String, dynamic>{
      'field_key': fieldKey,
      'field_label': fieldLabel,
      'instruction': instruction,
      'current_content': currentContent ?? '',
      'action': action,
      'provider': ?provider,
      'model': ?model,
      'poster_context': ?posterContext,
      'report_context': ?reportContext,
      'document_id': ?documentId,
      if (imageBytes != null) 'image_base64': base64Encode(imageBytes),
    };
    final endpoint = reportId != null
        ? '/documentation/reports/$reportId/ai-assist'
        : '/documentation/ai-assist';
    final res = await apiClient.post(endpoint, body: payload);
    return res is Map<String, dynamic> ? res : {};
  }

  // ---------------------------------------------------------------------------
  // DOCX Generation & Export
  // ---------------------------------------------------------------------------
  Future<Map<String, dynamic>> generateDocx(int reportId) async {
    final res = await apiClient.post(
      '/documentation/reports/$reportId/generate-docx',
      timeout: const Duration(seconds: 120),
    );
    return res is Map<String, dynamic> ? res : {};
  }

  Future<List<int>> downloadDocx(int reportId) async {
    return await apiClient.getBinary('/documentation/reports/$reportId/download-docx');
  }

  Future<FolderDocument> saveReportToFolder({
    required int reportId,
    required int folderId,
  }) async {
    final res = await apiClient.post(
      '/documentation/reports/$reportId/save-to-folder',
      body: {'folder_id': folderId},
    );
    return FolderDocument.fromJson(res as Map<String, dynamic>);
  }

  // ---------------------------------------------------------------------------
  // Automated Attendance Processing & Signature Verification
  // ---------------------------------------------------------------------------
  Future<Map<String, dynamic>> processAttendance({
    required List<int> fileBytes,
    required String filename,
    List<Map<String, dynamic>>? existingRecords,
  }) async {
    final b64 = base64Encode(fileBytes);
    final ext = filename.split('.').last.toLowerCase();
    final mime = ext == 'pdf' ? 'application/pdf' : 'image/$ext';
    final res = await apiClient.post(
      '/documentation/attendance/process',
      body: {
        'filename': filename,
        'file_base64': 'data:$mime;base64,$b64',
        'existing_records': ?existingRecords,
      },
      timeout: const Duration(seconds: 120),
    );
    return res is Map<String, dynamic> ? res : {};
  }

  Future<Map<String, dynamic>> verifyAttendance({
    required List<Map<String, dynamic>> records,
  }) async {
    final res = await apiClient.post(
      '/documentation/attendance/verify',
      body: {'records': records},
    );
    return res is Map<String, dynamic> ? res : {};
  }

  Future<String?> generateClassChart(List<dynamic> classDistribution) async {
    final res = await apiClient.post(
      '/documentation/attendance/class-chart',
      body: {'class_distribution': classDistribution},
    );
    if (res is Map<String, dynamic>) {
      return res['chart_base64'] as String?;
    }
    return null;
  }

  // ---------------------------------------------------------------------------
  // Feedback Analysis & PO Chart Generation
  // ---------------------------------------------------------------------------
  Future<Map<String, dynamic>> importFeedback({
    required List<int> fileBytes,
    required String filename,
  }) async {
    final b64 = base64Encode(fileBytes);
    final res = await apiClient.post(
      '/documentation/feedback/import',
      body: {
        'filename': filename,
        'file_base64': 'data:application/octet-stream;base64,$b64',
      },
      timeout: const Duration(seconds: 60),
    );
    return res is Map<String, dynamic> ? res : {};
  }

  Future<Map<String, dynamic>> analyzeFeedback({
    required List<dynamic> rows,
    required Map<String, String> poColumnMapping,
  }) async {
    final res = await apiClient.post(
      '/documentation/feedback/analyze',
      body: {
        'rows': rows,
        'po_column_mapping': poColumnMapping,
      },
      timeout: const Duration(seconds: 90),
    );
    return res is Map<String, dynamic> ? res : {};
  }

  // ---------------------------------------------------------------------------
  // Simulation Mode Methods: Impact Analysis & 12 PO Feedback Charts
  // ---------------------------------------------------------------------------
  Future<Map<String, dynamic>> generateSimulatedImpact({
    String? activityTitle,
    int? participantCount,
    int? seed,
  }) async {
    final payload = <String, dynamic>{
      'activity_title': ?activityTitle,
      'participant_count': ?participantCount,
      'seed': ?seed,
    };
    final res = await apiClient.post(
      '/documentation/simulate/impact',
      body: payload,
      timeout: const Duration(seconds: 45),
    );
    return res is Map<String, dynamic> ? res : {};
  }

  Future<Map<String, dynamic>> generateSimulatedFeedback({
    required int participantCount,
    String? activityTitle,
    int? seed,
    String? poId,
  }) async {
    final payload = <String, dynamic>{
      'participant_count': participantCount,
      'activity_title': ?activityTitle,
      'seed': ?seed,
      'po_id': ?poId,
    };
    final res = await apiClient.post(
      '/documentation/simulate/feedback',
      body: payload,
      timeout: const Duration(seconds: 90),
    );
    return res is Map<String, dynamic> ? res : {};
  }
}
