import 'dart:typed_data';
import '../models/media.dart';
import 'api_client.dart';

class MediaService {
  final ApiClient apiClient;

  MediaService({required this.apiClient});

  // ---------------------------------------------------------------------------
  // Event Folders CRUD
  // ---------------------------------------------------------------------------
  Future<List<MediaEventFolder>> listFolders({String? query}) async {
    final endpoint = (query != null && query.trim().isNotEmpty)
        ? '/media/folders?q=${Uri.encodeComponent(query.trim())}'
        : '/media/folders';

    final res = await apiClient.get(endpoint);
    if (res is List) {
      return res.map((e) => MediaEventFolder.fromJson(e as Map<String, dynamic>)).toList();
    }
    return [];
  }

  Future<MediaEventFolder> createFolder({
    required String name,
    String? description,
    DateTime? eventDate,
    bool createInDrive = false,
  }) async {
    final payload = {
      'name': name.trim(),
      if (description != null && description.trim().isNotEmpty) 'description': description.trim(),
      if (eventDate != null) 'event_date': eventDate.toIso8601String(),
      'create_in_drive': createInDrive,
    };

    final res = await apiClient.post('/media/folders', body: payload);
    return MediaEventFolder.fromJson(res as Map<String, dynamic>);
  }

  Future<MediaEventFolder> getFolder(int folderId, {bool includeMedia = false}) async {
    final res = await apiClient.get('/media/folders/$folderId?include_media=$includeMedia');
    return MediaEventFolder.fromJson(res as Map<String, dynamic>);
  }

  Future<void> deleteFolder(int folderId) async {
    await apiClient.delete('/media/folders/$folderId');
  }

  // ---------------------------------------------------------------------------
  // Media Files & Uploads
  // ---------------------------------------------------------------------------
  Future<MediaFileItem> uploadMedia({
    required int folderId,
    required Uint8List bytes,
    required String filename,
    required String category,
    String destination = 'firebase',
  }) async {
    final res = await apiClient.uploadMultipart(
      '/media/folders/$folderId/upload',
      fileBytes: bytes,
      filename: filename,
      fields: {
        'category': category,
        'destination': destination,
      },
    );
    return MediaFileItem.fromJson(res as Map<String, dynamic>);
  }

  Future<List<MediaFileItem>> listFolderFiles(int folderId, {String? category}) async {
    final endpoint = category != null && category.isNotEmpty
        ? '/media/folders/$folderId/files?category=$category'
        : '/media/folders/$folderId/files';

    final res = await apiClient.get(endpoint);
    if (res is List) {
      return res.map((e) => MediaFileItem.fromJson(e as Map<String, dynamic>)).toList();
    }
    return [];
  }

  Future<void> deleteMediaFile(int fileId) async {
    await apiClient.delete('/media/files/$fileId');
  }

  // ---------------------------------------------------------------------------
  // Google Drive Integration
  // ---------------------------------------------------------------------------
  Future<Map<String, dynamic>> getDriveStatus() async {
    final res = await apiClient.get('/media/drive/status');
    return res is Map<String, dynamic> ? res : {};
  }

  Future<String?> getDriveAuthUrl({String? redirectUri}) async {
    final endpoint = redirectUri != null
        ? '/media/drive/auth-url?redirect_uri=${Uri.encodeComponent(redirectUri)}'
        : '/media/drive/auth-url';

    final res = await apiClient.get(endpoint);
    if (res is Map<String, dynamic>) {
      return res['auth_url']?.toString();
    }
    return null;
  }

  Future<void> disconnectDrive() async {
    await apiClient.post('/media/drive/disconnect');
  }

  Future<List<GoogleDriveFolderItem>> listDriveFolders({String? query}) async {
    final endpoint = (query != null && query.trim().isNotEmpty)
        ? '/media/drive/folders?q=${Uri.encodeComponent(query.trim())}'
        : '/media/drive/folders';

    final res = await apiClient.get(endpoint);
    if (res is List) {
      return res.map((e) => GoogleDriveFolderItem.fromJson(e as Map<String, dynamic>)).toList();
    }
    return [];
  }

  Future<MediaEventFolder> linkDriveFolder({
    required int folderId,
    required String driveFolderId,
    required String driveFolderName,
    String? webViewLink,
  }) async {
    final payload = {
      'drive_folder_id': driveFolderId,
      'drive_folder_name': driveFolderName,
      'web_view_link': ?webViewLink,
    };
    final res = await apiClient.post('/media/folders/$folderId/link-drive', body: payload);
    return MediaEventFolder.fromJson(res as Map<String, dynamic>);
  }

  Future<MediaEventFolder> unlinkDriveFolder(int folderId) async {
    final res = await apiClient.post('/media/folders/$folderId/unlink-drive');
    return MediaEventFolder.fromJson(res as Map<String, dynamic>);
  }

  Future<List<GoogleDriveFileItem>> listLinkedDriveFiles(
    int folderId, {
    String? category,
    String? query,
  }) async {
    final params = <String>[];
    if (category != null && category.isNotEmpty) params.add('category=$category');
    if (query != null && query.trim().isNotEmpty) params.add('q=${Uri.encodeComponent(query.trim())}');

    final queryString = params.isNotEmpty ? '?${params.join('&')}' : '';
    final res = await apiClient.get('/media/folders/$folderId/drive-files$queryString');
    if (res is List) {
      return res.map((e) => GoogleDriveFileItem.fromJson(e as Map<String, dynamic>)).toList();
    }
    return [];
  }

  Future<MediaFileItem> linkDriveFile({
    required int folderId,
    required String driveFileId,
    String? category,
  }) async {
    final payload = {
      'drive_file_id': driveFileId,
      'category': ?category,
    };
    final res = await apiClient.post('/media/folders/$folderId/link-drive-file', body: payload);
    return MediaFileItem.fromJson(res as Map<String, dynamic>);
  }

  Future<MediaFileItem> uploadToDrive({
    required int folderId,
    required Uint8List bytes,
    required String filename,
    required String category,
  }) async {
    final res = await apiClient.uploadMultipart(
      '/media/folders/$folderId/upload-drive',
      fileBytes: bytes,
      filename: filename,
      fields: {
        'category': category,
      },
    );
    return MediaFileItem.fromJson(res as Map<String, dynamic>);
  }
}
