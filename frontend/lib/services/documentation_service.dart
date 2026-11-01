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
    final res = await apiClient.post('/documentation/reports/$reportId/generate-docx');
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
}
