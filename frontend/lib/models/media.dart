class MediaEventFolder {
  final int id;
  final String name;
  final String? description;
  final DateTime? eventDate;
  final int teamId;
  final int? createdById;
  final String? creatorName;
  final int mediaCount;
  final int geotaggedCount;
  final int photosCount;
  final int videosCount;
  final int postersCount;
  final String storageSource; // 'firebase', 'google_drive', 'both', 'none'
  final String? linkedDriveFolderId;
  final String? linkedDriveFolderName;
  final String? driveWebViewLink;
  final DateTime createdAt;
  final DateTime updatedAt;

  MediaEventFolder({
    required this.id,
    required this.name,
    this.description,
    this.eventDate,
    required this.teamId,
    this.createdById,
    this.creatorName,
    this.mediaCount = 0,
    this.geotaggedCount = 0,
    this.photosCount = 0,
    this.videosCount = 0,
    this.postersCount = 0,
    this.storageSource = 'none',
    this.linkedDriveFolderId,
    this.linkedDriveFolderName,
    this.driveWebViewLink,
    required this.createdAt,
    required this.updatedAt,
  });

  factory MediaEventFolder.fromJson(Map<String, dynamic> json) {
    return MediaEventFolder(
      id: (json['id'] as num).toInt(),
      name: json['name']?.toString() ?? 'Unnamed Event',
      description: json['description']?.toString(),
      eventDate: json['event_date'] != null ? DateTime.tryParse(json['event_date'].toString()) : null,
      teamId: (json['team_id'] as num?)?.toInt() ?? 3,
      createdById: (json['created_by'] as num?)?.toInt(),
      creatorName: json['creator_name']?.toString(),
      mediaCount: (json['media_count'] as num?)?.toInt() ?? 0,
      geotaggedCount: (json['geotagged_count'] as num?)?.toInt() ?? 0,
      photosCount: (json['photos_count'] as num?)?.toInt() ?? 0,
      videosCount: (json['videos_count'] as num?)?.toInt() ?? 0,
      postersCount: (json['posters_count'] as num?)?.toInt() ?? 0,
      storageSource: json['storage_source']?.toString() ?? 'none',
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

  bool get hasDriveLinked => linkedDriveFolderId != null && linkedDriveFolderId!.isNotEmpty;
}

class MediaFileItem {
  final int id;
  final int folderId;
  final String category; // 'geotagged_photos', 'photos', 'videos', 'posters'
  final String originalFilename;
  final String storageProvider; // 'firebase', 'google_drive', 'local'
  final String? storagePath;
  final String? driveFileId;
  final String? driveWebViewLink;
  final String? driveThumbnailLink;
  final String? mimeType;
  final int? fileSize;
  final String fileSizeFormatted;
  final int? uploadedBy;
  final String? uploaderName;
  final bool hasGps;
  final double? gpsLatitude;
  final double? gpsLongitude;
  final double? gpsAltitude;
  final DateTime? capturedAt;
  final String? cameraMake;
  final String? cameraModel;
  final String? mapsUrl;
  final String status;
  final DateTime createdAt;
  final DateTime updatedAt;

  MediaFileItem({
    required this.id,
    required this.folderId,
    required this.category,
    required this.originalFilename,
    required this.storageProvider,
    this.storagePath,
    this.driveFileId,
    this.driveWebViewLink,
    this.driveThumbnailLink,
    this.mimeType,
    this.fileSize,
    required this.fileSizeFormatted,
    this.uploadedBy,
    this.uploaderName,
    this.hasGps = false,
    this.gpsLatitude,
    this.gpsLongitude,
    this.gpsAltitude,
    this.capturedAt,
    this.cameraMake,
    this.cameraModel,
    this.mapsUrl,
    required this.status,
    required this.createdAt,
    required this.updatedAt,
  });

  factory MediaFileItem.fromJson(Map<String, dynamic> json) {
    return MediaFileItem(
      id: (json['id'] as num).toInt(),
      folderId: (json['folder_id'] as num).toInt(),
      category: json['category']?.toString() ?? 'photos',
      originalFilename: json['original_filename']?.toString() ?? 'Unnamed Media',
      storageProvider: json['storage_provider']?.toString() ?? 'firebase',
      storagePath: json['storage_path']?.toString(),
      driveFileId: json['drive_file_id']?.toString(),
      driveWebViewLink: json['drive_web_view_link']?.toString(),
      driveThumbnailLink: json['drive_thumbnail_link']?.toString(),
      mimeType: json['mime_type']?.toString(),
      fileSize: (json['file_size'] as num?)?.toInt(),
      fileSizeFormatted: json['file_size_formatted']?.toString() ?? '0 B',
      uploadedBy: (json['uploaded_by'] as num?)?.toInt(),
      uploaderName: json['uploader_name']?.toString(),
      hasGps: json['has_gps'] == true,
      gpsLatitude: (json['gps_latitude'] as num?)?.toDouble(),
      gpsLongitude: (json['gps_longitude'] as num?)?.toDouble(),
      gpsAltitude: (json['gps_altitude'] as num?)?.toDouble(),
      capturedAt: json['captured_at'] != null ? DateTime.tryParse(json['captured_at'].toString()) : null,
      cameraMake: json['camera_make']?.toString(),
      cameraModel: json['camera_model']?.toString(),
      mapsUrl: json['maps_url']?.toString(),
      status: json['status']?.toString() ?? 'active',
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
      updatedAt: json['updated_at'] != null
          ? DateTime.tryParse(json['updated_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }

  bool get isDrive => storageProvider == 'google_drive';
  bool get isFirebase => storageProvider == 'firebase' || storageProvider == 'local';
}

class GoogleDriveFolderItem {
  final String id;
  final String name;
  final String? webViewLink;
  final String? modifiedTime;

  GoogleDriveFolderItem({
    required this.id,
    required this.name,
    this.webViewLink,
    this.modifiedTime,
  });

  factory GoogleDriveFolderItem.fromJson(Map<String, dynamic> json) {
    return GoogleDriveFolderItem(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? 'Drive Folder',
      webViewLink: json['web_view_link']?.toString(),
      modifiedTime: json['modified_time']?.toString(),
    );
  }
}

class GoogleDriveFileItem {
  final String id;
  final String name;
  final String? mimeType;
  final int? fileSize;
  final String category;
  final String? webViewLink;
  final String? thumbnailLink;
  final String? modifiedTime;

  GoogleDriveFileItem({
    required this.id,
    required this.name,
    this.mimeType,
    this.fileSize,
    required this.category,
    this.webViewLink,
    this.thumbnailLink,
    this.modifiedTime,
  });

  factory GoogleDriveFileItem.fromJson(Map<String, dynamic> json) {
    return GoogleDriveFileItem(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? 'Drive File',
      mimeType: json['mime_type']?.toString(),
      fileSize: (json['file_size'] as num?)?.toInt(),
      category: json['category']?.toString() ?? 'photos',
      webViewLink: json['web_view_link']?.toString(),
      thumbnailLink: json['thumbnail_link']?.toString(),
      modifiedTime: json['modified_time']?.toString(),
    );
  }
}
