import '../models/mc_script.dart';
import '../models/documentation.dart';
import '../models/event.dart';
import 'api_client.dart';

class McService {
  final ApiClient apiClient;

  // ---------------------------------------------------------------------------
  // In-Memory Stale-While-Revalidate Caches (Instant 0ms responses)
  // ---------------------------------------------------------------------------
  static List<EventFolder>? _cachedFolders;
  static List<McScript>? _cachedScripts;
  static List<McTemplate>? _cachedTemplates;
  static List<EventTypeOption>? _cachedEventTypes;
  static List<Map<String, dynamic>>? _cachedMyTasks;
  static List<Event>? _cachedAvailableEvents;
  static Map<String, dynamic>? _cachedDashboard;
  static final Map<int, McScript> _cachedScriptDetails = {};
  static final Map<int, EventFolder> _cachedFolderDetails = {};
  static final Map<int, McTemplate> _cachedTemplateDetails = {};

  // Cache getters for instant UI pre-population
  static List<EventFolder>? get cachedFolders => _cachedFolders;
  static List<McScript>? get cachedScripts => _cachedScripts;
  static List<McTemplate>? get cachedTemplates => _cachedTemplates;
  static List<EventTypeOption>? get cachedEventTypes => _cachedEventTypes;
  static List<Map<String, dynamic>>? get cachedMyTasks => _cachedMyTasks;
  static List<Event>? get cachedAvailableEvents => _cachedAvailableEvents;
  static Map<String, dynamic>? get cachedDashboard => _cachedDashboard;

  static bool get hasCachedFolders => _cachedFolders != null;
  static bool get hasCachedScripts => _cachedScripts != null;
  static bool get hasCachedTemplates => _cachedTemplates != null && _cachedEventTypes != null;
  static bool get hasCachedTasks => _cachedMyTasks != null;
  static bool get hasCachedEvents => _cachedAvailableEvents != null;

  static void clearAllCaches() {
    _cachedFolders = null;
    _cachedScripts = null;
    _cachedTemplates = null;
    _cachedEventTypes = null;
    _cachedMyTasks = null;
    _cachedAvailableEvents = null;
    _cachedDashboard = null;
    _cachedScriptDetails.clear();
    _cachedFolderDetails.clear();
    _cachedTemplateDetails.clear();
  }

  McService({required this.apiClient});

  dynamic _unwrap(dynamic response) {
    if (response is Map<String, dynamic> && response.containsKey('data')) {
      return response['data'];
    }
    return response;
  }

  Future<Map<String, dynamic>> fetchDashboard({bool forceRefresh = false}) async {
    if (!forceRefresh && _cachedDashboard != null) {
      _refreshDashboardInBackground();
      return _cachedDashboard!;
    }
    final res = _unwrap(await apiClient.get('/mc/dashboard'));
    if (res is Map<String, dynamic>) {
      _cachedDashboard = res;
      return res;
    }
    return _cachedDashboard ?? {};
  }

  void _refreshDashboardInBackground() {
    apiClient.get('/mc/dashboard').then((res) {
      final unwrapped = _unwrap(res);
      if (unwrapped is Map<String, dynamic>) {
        _cachedDashboard = unwrapped;
      }
    }).catchError((_) {});
  }

  Future<List<Event>> fetchAvailableEvents({bool forceRefresh = false}) async {
    if (!forceRefresh && _cachedAvailableEvents != null) {
      _refreshAvailableEventsInBackground();
      return _cachedAvailableEvents!;
    }
    final res = _unwrap(await apiClient.get('/mc/events'));
    if (res is List) {
      final list = res.map((e) => Event.fromJson(e as Map<String, dynamic>)).toList();
      _cachedAvailableEvents = list;
      return list;
    }
    return _cachedAvailableEvents ?? [];
  }

  void _refreshAvailableEventsInBackground() {
    apiClient.get('/mc/events').then((res) {
      final unwrapped = _unwrap(res);
      if (unwrapped is List) {
        _cachedAvailableEvents = unwrapped.map((e) => Event.fromJson(e as Map<String, dynamic>)).toList();
      }
    }).catchError((_) {});
  }

  Future<List<Map<String, dynamic>>> fetchMyTasks({bool forceRefresh = false}) async {
    if (!forceRefresh && _cachedMyTasks != null) {
      _refreshMyTasksInBackground();
      return _cachedMyTasks!;
    }
    final res = _unwrap(await apiClient.get('/mc/my-tasks'));
    if (res is List) {
      final list = List<Map<String, dynamic>>.from(res);
      _cachedMyTasks = list;
      return list;
    }
    return _cachedMyTasks ?? [];
  }

  void _refreshMyTasksInBackground() {
    apiClient.get('/mc/my-tasks').then((res) {
      final unwrapped = _unwrap(res);
      if (unwrapped is List) {
        _cachedMyTasks = List<Map<String, dynamic>>.from(unwrapped);
      }
    }).catchError((_) {});
  }

  Future<List<McScript>> fetchScripts({
    String? status,
    int? eventId,
    String? query,
    bool forceRefresh = false,
  }) async {
    final isDefaultQuery = (status == null || status.isEmpty || status == 'all') &&
        eventId == null &&
        (query == null || query.isEmpty);

    if (!forceRefresh && isDefaultQuery && _cachedScripts != null) {
      _refreshScriptsInBackground();
      return _cachedScripts!;
    }

    final params = <String, String>{};
    if (status != null && status.isNotEmpty) params['status'] = status;
    if (eventId != null) params['event_id'] = eventId.toString();
    if (query != null && query.isNotEmpty) params['q'] = query;

    final queryString = params.isNotEmpty
        ? '?${params.entries.map((e) => '${e.key}=${Uri.encodeComponent(e.value)}').join('&')}'
        : '';

    final res = _unwrap(await apiClient.get('/mc/scripts$queryString'));
    if (res is List) {
      final list = res.map((s) => McScript.fromJson(s as Map<String, dynamic>)).toList();
      if (isDefaultQuery) {
        _cachedScripts = list;
      }
      return list;
    }
    return isDefaultQuery ? (_cachedScripts ?? []) : [];
  }

  void _refreshScriptsInBackground() {
    apiClient.get('/mc/scripts').then((res) {
      final unwrapped = _unwrap(res);
      if (unwrapped is List) {
        _cachedScripts = unwrapped.map((s) => McScript.fromJson(s as Map<String, dynamic>)).toList();
      }
    }).catchError((_) {});
  }

  Future<McScript> fetchScriptDetail(int scriptId, {bool forceRefresh = false}) async {
    if (!forceRefresh && _cachedScriptDetails.containsKey(scriptId)) {
      _refreshScriptDetailInBackground(scriptId);
      return _cachedScriptDetails[scriptId]!;
    }
    final res = _unwrap(await apiClient.get('/mc/scripts/$scriptId'));
    if (res is Map<String, dynamic>) {
      final script = McScript.fromJson(res);
      _cachedScriptDetails[scriptId] = script;
      return script;
    }
    if (_cachedScriptDetails.containsKey(scriptId)) {
      return _cachedScriptDetails[scriptId]!;
    }
    throw Exception('Failed to load script details.');
  }

  void _refreshScriptDetailInBackground(int scriptId) {
    apiClient.get('/mc/scripts/$scriptId').then((res) {
      final unwrapped = _unwrap(res);
      if (unwrapped is Map<String, dynamic>) {
        _cachedScriptDetails[scriptId] = McScript.fromJson(unwrapped);
      }
    }).catchError((_) {});
  }

  Future<McScript> createScript(Map<String, dynamic> payload) async {
    final res = _unwrap(await apiClient.post('/mc/scripts', body: payload));
    if (res is Map<String, dynamic>) {
      final script = McScript.fromJson(res);
      if (_cachedScripts != null) {
        _cachedScripts!.insert(0, script);
      } else {
        _cachedScripts = [script];
      }
      _cachedScriptDetails[script.id] = script;
      _cachedDashboard = null; // Invalidate dashboard counters
      return script;
    }
    throw Exception('Failed to create script draft.');
  }

  Future<McScript> updateScript(int scriptId, Map<String, dynamic> payload) async {
    final res = _unwrap(await apiClient.put('/mc/scripts/$scriptId', body: payload));
    if (res is Map<String, dynamic>) {
      final script = McScript.fromJson(res);
      _cachedScriptDetails[scriptId] = script;
      if (_cachedScripts != null) {
        final idx = _cachedScripts!.indexWhere((s) => s.id == scriptId);
        if (idx != -1) {
          _cachedScripts![idx] = script;
        }
      }
      _cachedDashboard = null;
      return script;
    }
    throw Exception('Failed to update script.');
  }

  Future<void> deleteScript(int scriptId) async {
    await apiClient.delete('/mc/scripts/$scriptId');
    _cachedScriptDetails.remove(scriptId);
    if (_cachedScripts != null) {
      _cachedScripts!.removeWhere((s) => s.id == scriptId);
    }
    _cachedDashboard = null;
  }

  Future<McScript> submitForReview(int scriptId) async {
    final res = _unwrap(await apiClient.post('/mc/scripts/$scriptId/submit', body: {}));
    if (res is Map<String, dynamic>) {
      final script = McScript.fromJson(res);
      _cachedScriptDetails[scriptId] = script;
      if (_cachedScripts != null) {
        final idx = _cachedScripts!.indexWhere((s) => s.id == scriptId);
        if (idx != -1) _cachedScripts![idx] = script;
      }
      _cachedDashboard = null;
      return script;
    }
    throw Exception('Failed to submit script for review.');
  }

  Future<McScript> reviewScript(int scriptId, String decision, String? comments) async {
    final res = _unwrap(await apiClient.post('/mc/scripts/$scriptId/review', body: {
      'decision': decision,
      'comments': comments,
    }));
    if (res is Map<String, dynamic>) {
      final script = McScript.fromJson(res);
      _cachedScriptDetails[scriptId] = script;
      if (_cachedScripts != null) {
        final idx = _cachedScripts!.indexWhere((s) => s.id == scriptId);
        if (idx != -1) _cachedScripts![idx] = script;
      }
      _cachedDashboard = null;
      return script;
    }
    throw Exception('Failed to submit review.');
  }

  Future<Map<String, dynamic>> generateDocx(int scriptId) async {
    final res = _unwrap(await apiClient.post('/mc/scripts/$scriptId/generate-docx', body: {}));
    if (res is Map<String, dynamic>) {
      return res;
    }
    throw Exception('Failed to generate DOCX.');
  }

  Future<List<int>> downloadDocxBytes(int scriptId) async {
    return await apiClient.getBinary('/mc/scripts/$scriptId/download-docx');
  }

  Future<Map<String, dynamic>> uploadToDrive(int scriptId, {String? category}) async {
    final res = _unwrap(await apiClient.post('/mc/scripts/$scriptId/upload-drive', body: {
      'category': category ?? 'Final Approved Scripts',
    }));
    if (res is Map<String, dynamic>) {
      _cachedDashboard = null;
      return res;
    }
    throw Exception('Failed to upload script to Google Drive.');
  }

  Future<Map<String, dynamic>> aiGenerateFullScript(Map<String, dynamic> eventInfo) async {
    final res = _unwrap(await apiClient.post('/mc/ai/generate-script', body: eventInfo));
    if (res is Map<String, dynamic>) {
      return res;
    }
    throw Exception('AI script generation failed.');
  }

  Future<Map<String, dynamic>> aiGenerateSegment({
    required String segmentType,
    required Map<String, dynamic> eventInfo,
    String? currentContent,
    String? instructions,
  }) async {
    final res = _unwrap(await apiClient.post('/mc/ai/generate-segment', body: {
      'segment_type': segmentType,
      'event_info': eventInfo,
      'current_content': currentContent,
      'instructions': instructions,
    }));
    if (res is Map<String, dynamic>) {
      return res;
    }
    throw Exception('AI segment generation failed.');
  }

  Future<String> aiRewrite({
    required String text,
    required String tone,
    String action = 'adjust_tone',
  }) async {
    final res = _unwrap(await apiClient.post('/mc/ai/rewrite', body: {
      'text': text,
      'tone': tone,
      'action': action,
    }));
    if (res is Map<String, dynamic>) {
      return res['improved_text']?.toString() ?? text;
    }
    return text;
  }

  Future<Map<String, dynamic>> fetchDriveStatus() async {
    try {
      final res = _unwrap(await apiClient.get('/mc/drive/status'));
      if (res is Map<String, dynamic>) {
        return res;
      }
    } catch (_) {}
    return {'is_connected': false, 'is_configured': false};
  }

  Future<List<EventFolder>> fetchFolders({bool forceRefresh = false}) async {
    if (!forceRefresh && _cachedFolders != null) {
      _refreshFoldersInBackground();
      return _cachedFolders!;
    }
    final res = _unwrap(await apiClient.get('/mc/folders'));
    if (res is List) {
      final list = res.map((f) => EventFolder.fromJson(f as Map<String, dynamic>)).toList();
      _cachedFolders = list;
      return list;
    }
    return _cachedFolders ?? [];
  }

  void _refreshFoldersInBackground() {
    apiClient.get('/mc/folders').then((res) {
      final unwrapped = _unwrap(res);
      if (unwrapped is List) {
        _cachedFolders = unwrapped.map((f) => EventFolder.fromJson(f as Map<String, dynamic>)).toList();
      }
    }).catchError((_) {});
  }

  Future<EventFolder> getFolder(int folderId, {bool forceRefresh = false}) async {
    if (!forceRefresh && _cachedFolderDetails.containsKey(folderId)) {
      _refreshFolderDetailInBackground(folderId);
      return _cachedFolderDetails[folderId]!;
    }
    final res = _unwrap(await apiClient.get('/mc/folders/$folderId'));
    if (res is Map<String, dynamic>) {
      final folder = EventFolder.fromJson(res);
      _cachedFolderDetails[folderId] = folder;
      return folder;
    }
    if (_cachedFolderDetails.containsKey(folderId)) {
      return _cachedFolderDetails[folderId]!;
    }
    throw Exception('Failed to load folder details.');
  }

  void _refreshFolderDetailInBackground(int folderId) {
    apiClient.get('/mc/folders/$folderId').then((res) {
      final unwrapped = _unwrap(res);
      if (unwrapped is Map<String, dynamic>) {
        _cachedFolderDetails[folderId] = EventFolder.fromJson(unwrapped);
      }
    }).catchError((_) {});
  }

  Future<EventFolder> createFolder(
    String name, {
    String? description,
    String? eventDate,
    String? driveLink,
  }) async {
    final res = _unwrap(await apiClient.post('/mc/folders', body: {
      'name': name,
      if (description != null && description.isNotEmpty) 'description': description,
      'event_date': eventDate,
      if (driveLink != null && driveLink.isNotEmpty) 'drive_link': driveLink,
    }));
    if (res is Map<String, dynamic>) {
      final folder = EventFolder.fromJson(res);
      if (_cachedFolders != null) {
        _cachedFolders!.insert(0, folder);
      } else {
        _cachedFolders = [folder];
      }
      return folder;
    }
    throw Exception('Failed to create folder.');
  }

  Future<EventFolder> updateFolder(
    int folderId, {
    String? name,
    String? description,
    String? driveLink,
  }) async {
    final res = _unwrap(await apiClient.put('/mc/folders/$folderId', body: {
      'name': name,
      'description': description,
      'drive_link': driveLink,
    }));
    if (res is Map<String, dynamic>) {
      final folder = EventFolder.fromJson(res);
      _cachedFolderDetails[folderId] = folder;
      if (_cachedFolders != null) {
        final idx = _cachedFolders!.indexWhere((f) => f.id == folderId);
        if (idx != -1) _cachedFolders![idx] = folder;
      }
      return folder;
    }
    throw Exception('Failed to update folder.');
  }

  Future<FolderDocument> uploadDocument({
    required int folderId,
    required List<int> fileBytes,
    required String filename,
  }) async {
    final res = _unwrap(await apiClient.uploadMultipart(
      '/mc/folders/$folderId/upload',
      fileBytes: fileBytes,
      filename: filename,
    ));
    if (res is Map<String, dynamic>) {
      final docData = res['document'] ?? res;
      _cachedFolderDetails.remove(folderId); // Invalidate folder detail cache
      return FolderDocument.fromJson(docData as Map<String, dynamic>);
    }
    throw Exception('Failed to upload document.');
  }

  Future<Map<String, dynamic>> aiAssist({
    required String instruction,
    String action = 'draft',
    String? provider,
    String? model,
  }) async {
    final res = _unwrap(await apiClient.post('/mc/ai-assist', body: {
      'instruction': instruction,
      'action': action,
      'provider': provider,
      'model': model,
    }));
    if (res is Map<String, dynamic>) {
      return res;
    }
    throw Exception('AI copilot assist failed.');
  }

  Future<Map<String, dynamic>> fetchFolderDetail(int folderId) async {
    final res = _unwrap(await apiClient.get('/mc/folders/$folderId'));
    if (res is Map<String, dynamic>) {
      return res;
    }
    throw Exception('Failed to load folder details.');
  }

  Future<void> deleteFolder(int folderId) async {
    await apiClient.delete('/mc/folders/$folderId');
    _cachedFolderDetails.remove(folderId);
    if (_cachedFolders != null) {
      _cachedFolders!.removeWhere((f) => f.id == folderId);
    }
  }

  Future<Map<String, dynamic>> uploadScriptFile(int folderId, List<int> fileBytes, String filename) async {
    final res = _unwrap(await apiClient.uploadMultipart(
      '/mc/folders/$folderId/upload',
      fileBytes: fileBytes,
      filename: filename,
    ));
    if (res is Map<String, dynamic>) {
      _cachedFolderDetails.remove(folderId);
      _cachedScripts = null;
      _cachedDashboard = null;
      return res;
    }
    throw Exception('Failed to upload script.');
  }

  Future<List<int>> downloadDocument(int documentId) async {
    return await apiClient.getBinary('/mc/documents/$documentId/download');
  }

  Future<void> deleteDocument(int documentId) async {
    await apiClient.delete('/mc/documents/$documentId');
  }

  Future<List<Map<String, dynamic>>> fetchTeamMembers() async {
    final res = _unwrap(await apiClient.get('/mc/team-members'));
    if (res is List) {
      return List<Map<String, dynamic>>.from(res);
    }
    return [];
  }

  Future<Map<String, dynamic>> assignTask(int taskId, int memberId) async {
    final res = _unwrap(await apiClient.post('/mc/tasks/$taskId/assign', body: {
      'member_id': memberId,
    }));
    if (res is Map<String, dynamic>) {
      _cachedMyTasks = null;
      _cachedDashboard = null;
      return res;
    }
    throw Exception('Failed to assign task.');
  }

  Future<void> updateAssignmentStatus(int assignmentId, String status, {String? note}) async {
    await apiClient.patch('/assignments/$assignmentId/status', body: {
      'status': status,
      'note': note,
    });
    _cachedMyTasks = null;
  }

  // ---------------------------------------------------------------------------
  // MC Templates & Event Types Catalog (Cached)
  // ---------------------------------------------------------------------------
  Future<List<EventTypeOption>> fetchEventTypes({bool forceRefresh = false}) async {
    if (!forceRefresh && _cachedEventTypes != null) {
      return _cachedEventTypes!;
    }
    final res = _unwrap(await apiClient.get('/mc/event-types'));
    if (res is List) {
      final list = res.map((e) => EventTypeOption.fromJson(e as Map<String, dynamic>)).toList();
      _cachedEventTypes = list;
      return list;
    }
    return _cachedEventTypes ?? [];
  }

  Future<List<McTemplate>> fetchTemplates({String? eventType, bool forceRefresh = false}) async {
    final isDefault = eventType == null || eventType.isEmpty;
    if (!forceRefresh && isDefault && _cachedTemplates != null) {
      _refreshTemplatesInBackground();
      return _cachedTemplates!;
    }

    final query = (eventType != null && eventType.isNotEmpty)
        ? '?event_type=${Uri.encodeComponent(eventType)}'
        : '';
    final res = _unwrap(await apiClient.get('/mc/templates$query'));
    if (res is List) {
      final list = res.map((t) => McTemplate.fromJson(t as Map<String, dynamic>)).toList();
      if (isDefault) _cachedTemplates = list;
      return list;
    }
    return isDefault ? (_cachedTemplates ?? []) : [];
  }

  void _refreshTemplatesInBackground() {
    apiClient.get('/mc/templates').then((res) {
      final unwrapped = _unwrap(res);
      if (unwrapped is List) {
        _cachedTemplates = unwrapped.map((t) => McTemplate.fromJson(t as Map<String, dynamic>)).toList();
      }
    }).catchError((_) {});
  }

  Future<McTemplate> fetchTemplateDetail(int templateId, {bool forceRefresh = false}) async {
    if (!forceRefresh && _cachedTemplateDetails.containsKey(templateId)) {
      return _cachedTemplateDetails[templateId]!;
    }
    final res = _unwrap(await apiClient.get('/mc/templates/$templateId'));
    if (res is Map<String, dynamic>) {
      final t = McTemplate.fromJson(res);
      _cachedTemplateDetails[templateId] = t;
      return t;
    }
    if (_cachedTemplateDetails.containsKey(templateId)) {
      return _cachedTemplateDetails[templateId]!;
    }
    throw Exception('Failed to load template details.');
  }

  Future<McTemplate> createTemplate(Map<String, dynamic> payload) async {
    final res = _unwrap(await apiClient.post('/mc/templates', body: payload));
    if (res is Map<String, dynamic>) {
      final t = McTemplate.fromJson(res);
      if (_cachedTemplates != null) {
        _cachedTemplates!.insert(0, t);
      } else {
        _cachedTemplates = [t];
      }
      _cachedTemplateDetails[t.id] = t;
      return t;
    }
    throw Exception('Failed to create template.');
  }

  Future<McTemplate> updateTemplate(int templateId, Map<String, dynamic> payload) async {
    final res = _unwrap(await apiClient.put('/mc/templates/$templateId', body: payload));
    if (res is Map<String, dynamic>) {
      final t = McTemplate.fromJson(res);
      _cachedTemplateDetails[templateId] = t;
      if (_cachedTemplates != null) {
        final idx = _cachedTemplates!.indexWhere((x) => x.id == templateId);
        if (idx != -1) _cachedTemplates![idx] = t;
      }
      return t;
    }
    throw Exception('Failed to update template.');
  }

  Future<void> deleteTemplate(int templateId) async {
    await apiClient.delete('/mc/templates/$templateId');
    _cachedTemplateDetails.remove(templateId);
    if (_cachedTemplates != null) {
      _cachedTemplates!.removeWhere((t) => t.id == templateId);
    }
  }

  // ---------------------------------------------------------------------------
  // Visual Programme Segment Operations
  // ---------------------------------------------------------------------------
  Future<McScriptSegment> addSegment(int scriptId, Map<String, dynamic> payload) async {
    final res = _unwrap(await apiClient.post('/mc/scripts/$scriptId/segments', body: payload));
    if (res is Map<String, dynamic>) {
      _cachedScriptDetails.remove(scriptId); // Invalidate detail
      return McScriptSegment.fromJson(res);
    }
    throw Exception('Failed to add segment.');
  }

  Future<McScriptSegment> updateSegment(int scriptId, int segmentId, Map<String, dynamic> payload) async {
    final res = _unwrap(await apiClient.put('/mc/scripts/$scriptId/segments/$segmentId', body: payload));
    if (res is Map<String, dynamic>) {
      _cachedScriptDetails.remove(scriptId);
      return McScriptSegment.fromJson(res);
    }
    throw Exception('Failed to update segment.');
  }

  Future<void> deleteSegment(int scriptId, int segmentId) async {
    await apiClient.delete('/mc/scripts/$scriptId/segments/$segmentId');
    _cachedScriptDetails.remove(scriptId);
  }

  Future<McScriptSegment> duplicateSegment(int scriptId, int segmentId) async {
    final res = _unwrap(await apiClient.post('/mc/scripts/$scriptId/segments/$segmentId/duplicate', body: {}));
    if (res is Map<String, dynamic>) {
      _cachedScriptDetails.remove(scriptId);
      return McScriptSegment.fromJson(res);
    }
    throw Exception('Failed to duplicate segment.');
  }

  Future<List<McScriptSegment>> reorderSegments(int scriptId, List<int> orderedIds) async {
    final res = _unwrap(await apiClient.post('/mc/scripts/$scriptId/segments/reorder', body: {
      'segment_ids': orderedIds,
    }));
    if (res is List) {
      _cachedScriptDetails.remove(scriptId);
      return res.map((s) => McScriptSegment.fromJson(s as Map<String, dynamic>)).toList();
    }
    return [];
  }

  Future<List<McScriptSegment>> autoAssignMcs(int scriptId) async {
    final res = _unwrap(await apiClient.post('/mc/scripts/$scriptId/auto-assign-mcs', body: {}));
    if (res is List) {
      _cachedScriptDetails.remove(scriptId);
      return res.map((s) => McScriptSegment.fromJson(s as Map<String, dynamic>)).toList();
    }
    return [];
  }

  Future<ScriptValidationResult> validateScript(int scriptId) async {
    final res = _unwrap(await apiClient.post('/mc/scripts/$scriptId/validate', body: {}));
    if (res is Map<String, dynamic>) {
      return ScriptValidationResult.fromJson(res);
    }
    throw Exception('Failed to validate script.');
  }

  Future<McTemplate> saveScriptAsTemplate(int scriptId, String name, String? description) async {
    final res = _unwrap(await apiClient.post('/mc/scripts/$scriptId/save-as-template', body: {
      'name': name,
      if (description != null && description.isNotEmpty) 'description': description,
    }));
    if (res is Map<String, dynamic>) {
      final t = McTemplate.fromJson(res);
      if (_cachedTemplates != null) {
        _cachedTemplates!.insert(0, t);
      }
      return t;
    }
    throw Exception('Failed to save script as template.');
  }

  Future<Map<String, dynamic>> aiGenerateSegmentDialogue(
    int scriptId,
    int segmentId, {
    String action = 'generate',
    String? instruction,
    Map<String, dynamic>? inputData,
  }) async {
    final res = _unwrap(await apiClient.post(
      '/mc/scripts/$scriptId/segments/$segmentId/ai-generate',
      body: {
        'action': action,
        'instruction': instruction,
        'input_data': inputData,
      },
    ));
    if (res is Map<String, dynamic>) {
      _cachedScriptDetails.remove(scriptId);
      return res;
    }
    throw Exception('Failed to generate segment dialogue.');
  }
}
