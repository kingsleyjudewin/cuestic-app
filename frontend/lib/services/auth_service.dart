import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import '../config/constants.dart';

class AuthService extends ChangeNotifier {
  final FlutterSecureStorage _storage;
  final http.Client _client;

  String? _token;
  Map<String, dynamic>? _currentUser;
  bool _isInitialized = false;

  final _sessionExpiredController = StreamController<void>.broadcast();
  Stream<void> get onSessionExpired => _sessionExpiredController.stream;

  AuthService({FlutterSecureStorage? storage, http.Client? client})
      : _storage = storage ?? const FlutterSecureStorage(),
        _client = client ?? http.Client();

  bool get isAuthenticated => _token != null && _token!.isNotEmpty;
  bool get isInitialized => _isInitialized;
  String? get token => _token;
  Map<String, dynamic>? get currentUser => _currentUser;
  String get username => _currentUser?['username']?.toString() ?? 'User';
  String get userRole => _currentUser?['role']?.toString() ?? 'member';
  bool get isAdmin => userRole == 'president' || userRole == 'admin';
  bool get isTeamLeader => userRole == 'team_leader';
  bool get isFacultyCoordinator => userRole == 'faculty_coordinator';
  bool get isStudentResearcher => userRole == 'student_researcher';
  bool get isResearchUser => isFacultyCoordinator || isStudentResearcher;
  /// Exact admin role only (not president): exempt from the mandatory password change.
  bool get isSystemAdmin => userRole == 'admin';

  /// True while the server requires a new password. The server enforces this on every request;
  /// this getter only decides which screen to show.
  bool get mustChangePassword {
    if (_currentUser == null || isSystemAdmin) return false;
    return _currentUser?['password_change_required'] == true ||
        _currentUser?['must_change_password'] == true ||
        _currentUser?['credential_setup_status'] == 'pending';
  }

  bool get isVolunteer =>
      !isAdmin &&
      !isTeamLeader &&
      !isDocumentationTeam &&
      !isMediaTeam &&
      !isMcTeam &&
      !isResearchUser;
  bool get isDocumentationTeam {
    if (isAdmin) return false;
    if (teamId == 2) return true;
    final name = teamName?.toLowerCase() ?? '';
    return name == 'documentation' || name.contains('doc');
  }
  bool get isMediaTeam {
    if (isAdmin) return false;
    if (teamId == 3) return true;
    final name = teamName?.toLowerCase() ?? '';
    return name == 'media' || name.contains('media') || name.contains('design');
  }
  bool get isMcTeam {
    if (isAdmin) return false;
    if (teamId == 5) return true;
    final name = teamName?.toLowerCase() ?? '';
    return name == 'mc' || name.contains('mc') || name.contains('ceremonies') || name.contains('anchor');
  }
  bool get canAccessDocumentation => isAdmin || isDocumentationTeam;
  bool get canAccessMc => isAdmin || isMcTeam;
  bool get canCreateEvent => isAdmin || isTeamLeader;
  int? get memberId {
    final v = _currentUser?['member_id'];
    if (v is num) return v.toInt();
    if (v is String) return int.tryParse(v);
    return null;
  }
  String? get memberName => _currentUser?['member_name']?.toString();
  String get displayName => memberName ?? username;
  int? get teamId {
    final v = _currentUser?['team_id'];
    if (v is num) return v.toInt();
    if (v is String) return int.tryParse(v);
    return null;
  }
  String? get teamName => _currentUser?['team_name']?.toString();

  Future<void> initialize() async {
    try {
      _token = await _storage.read(key: AppConstants.keyAuthToken);
      final userStr = await _storage.read(key: AppConstants.keyUserData);
      if (userStr != null && userStr.isNotEmpty) {
        _currentUser = jsonDecode(userStr) as Map<String, dynamic>?;
      }
    } catch (e) {
      debugPrint('AuthService init error: $e');
    } finally {
      _isInitialized = true;
      notifyListeners();
    }
  }

  Future<String?> getToken() async {
    if (_token != null) return _token;
    _token = await _storage.read(key: AppConstants.keyAuthToken);
    return _token;
  }

  /// The backend URL every service must use. A stored override is honoured only when
  /// [ApiConfig.allowServerOverride] is on (debug builds); release builds always use the
  /// API_BASE_URL compiled into the app, even if an old override is still stored.
  Future<String?> getConfiguredBaseUrl() async {
    String? stored;
    if (ApiConfig.allowServerOverride) {
      stored = await _storage.read(key: AppConstants.keyApiBaseUrl);
    }
    return ApiConfig.resolve(stored);
  }

  Future<void> setConfiguredBaseUrl(String url) async {
    if (!ApiConfig.allowServerOverride) return;
    await _storage.write(key: AppConstants.keyApiBaseUrl, value: url);
    notifyListeners();
  }

  Future<int?> getLastSelectedEventId() async {
    final str = await _storage.read(key: AppConstants.keyLastSelectedEventId);
    if (str != null) return int.tryParse(str);
    return null;
  }

  Future<void> setLastSelectedEvent(int eventId, String eventName) async {
    await _storage.write(key: AppConstants.keyLastSelectedEventId, value: eventId.toString());
    await _storage.write(key: AppConstants.keyLastSelectedEventName, value: eventName);
  }

  Future<void> login({
    required String username,
    required String password,
    String? deviceName,
    String? customBaseUrl,
  }) async {
    if (!ApiConfig.allowServerOverride) customBaseUrl = null;
    final baseUrl = customBaseUrl != null
        ? ApiConfig.resolve(customBaseUrl)
        : ((await getConfiguredBaseUrl()) ?? AppConstants.defaultBaseUrl);
    final uri = Uri.parse('$baseUrl/auth/login');

    http.Response response;
    try {
      response = await _client.post(
        uri,
        headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
        body: jsonEncode({
          'username': username.trim(),
          'password': password,
          'device_name': deviceName ?? 'Club Mobile App',
        }),
      ).timeout(const Duration(seconds: 15));
    } on http.ClientException catch (e) {
      throw Exception('Connection failed (${e.message}). Check that the backend server is reachable at $baseUrl.');
    } on TimeoutException catch (_) {
      throw Exception('Request timed out connecting to $baseUrl.');
    } catch (e) {
      if (e is Exception) rethrow;
      throw Exception('Unable to reach server at $baseUrl: $e');
    }

    final decoded = jsonDecode(response.body);

    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = decoded['data'] as Map<String, dynamic>;
      final rawToken = data['token'] as String;
      final userObj = data['user'] as Map<String, dynamic>;

      _token = rawToken;
      _currentUser = userObj;

      await _storage.write(key: AppConstants.keyAuthToken, value: rawToken);
      await _storage.write(key: AppConstants.keyUserData, value: jsonEncode(userObj));
      if (customBaseUrl != null) {
        await _storage.write(key: AppConstants.keyApiBaseUrl, value: customBaseUrl);
      }

      notifyListeners();
      return;
    }

    String err = 'Login failed.';
    if (decoded is Map<String, dynamic> && decoded['error'] != null) {
      err = decoded['error']['message'] ?? err;
    }
    throw Exception(err);
  }

  /// Completes a (mandatory) password change. On success the server revokes every previous
  /// session and returns a new token, which replaces the stored one.
  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
    required String confirmPassword,
  }) async {
    final baseUrl = (await getConfiguredBaseUrl()) ?? AppConstants.defaultBaseUrl;
    final currentToken = _token;
    if (currentToken == null) {
      throw const PasswordChangeException('SESSION_EXPIRED', 'Your session has expired. Please sign in again.');
    }

    http.Response response;
    try {
      response = await _client.post(
        Uri.parse('$baseUrl/auth/change-password'),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'Authorization': 'Bearer $currentToken',
        },
        body: jsonEncode({
          'current_password': currentPassword,
          'new_password': newPassword,
          'confirm_password': confirmPassword,
        }),
      ).timeout(const Duration(seconds: 30));
    } on TimeoutException {
      throw const PasswordChangeException('NETWORK_ERROR', 'The server did not respond. Check your connection and try again.');
    } catch (_) {
      throw const PasswordChangeException('NETWORK_ERROR', 'Could not reach the server. Check your connection and try again.');
    }

    Map<String, dynamic>? decoded;
    try {
      final body = jsonDecode(response.body);
      if (body is Map<String, dynamic>) decoded = body;
    } catch (_) {}

    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = decoded?['data'] as Map<String, dynamic>?;
      final newToken = data?['token'] as String?;
      final userObj = data?['user'] as Map<String, dynamic>?;
      if (newToken == null || userObj == null) {
        throw const PasswordChangeException('SERVER_ERROR', 'Unexpected response from the server. Please sign in again.');
      }
      _token = newToken;
      _currentUser = userObj;
      await _storage.write(key: AppConstants.keyAuthToken, value: newToken);
      await _storage.write(key: AppConstants.keyUserData, value: jsonEncode(userObj));
      notifyListeners();
      return;
    }

    final err = decoded?['error'] as Map<String, dynamic>?;
    final code = err?['code']?.toString() ?? 'HTTP_${response.statusCode}';
    final message = err?['message']?.toString();
    final details = err?['details'];
    List<String> problems = const [];
    if (details is Map && details['new_password'] is List) {
      problems = (details['new_password'] as List).map((e) => e.toString()).toList();
    }

    if (response.statusCode == 401) {
      handleSessionExpired();
      throw const PasswordChangeException('SESSION_EXPIRED', 'Your session has expired. Please sign in again.');
    }
    if (response.statusCode == 429) {
      throw const PasswordChangeException('RATE_LIMITED', 'Too many attempts. Please wait a minute and try again.');
    }
    if (response.statusCode >= 500) {
      throw const PasswordChangeException('SERVER_ERROR', 'The server could not complete the request. Please try again later.');
    }
    throw PasswordChangeException(code, message ?? 'The password could not be changed.', problems: problems);
  }

  /// Called when any request is answered with 403 PASSWORD_CHANGE_REQUIRED (for example after an
  /// administrator flagged the account while the app was open).
  Future<void> markPasswordChangeRequired() async {
    if (_currentUser == null || isSystemAdmin || mustChangePassword) return;
    _currentUser = {..._currentUser!, 'password_change_required': true};
    await _storage.write(key: AppConstants.keyUserData, value: jsonEncode(_currentUser));
    notifyListeners();
  }

  Future<void> updateCurrentUser(Map<String, dynamic> userObj) async {
    _currentUser = userObj;
    await _storage.write(key: AppConstants.keyUserData, value: jsonEncode(userObj));
    notifyListeners();
  }

  Future<void> logout() async {
    final currentToken = _token;
    final baseUrl = (await getConfiguredBaseUrl()) ?? AppConstants.defaultBaseUrl;

    if (currentToken != null) {
      try {
        await _client.post(
          Uri.parse('$baseUrl/auth/logout'),
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer $currentToken',
          },
        ).timeout(const Duration(seconds: 5));
      } catch (_) {
        // Continue clearing local storage even if remote logout times out
      }
    }

    _token = null;
    _currentUser = null;
    await _storage.delete(key: AppConstants.keyAuthToken);
    await _storage.delete(key: AppConstants.keyUserData);
    notifyListeners();
  }

  void handleSessionExpired() {
    _token = null;
    _currentUser = null;
    _storage.delete(key: AppConstants.keyAuthToken);
    _storage.delete(key: AppConstants.keyUserData);
    _sessionExpiredController.add(null);
    notifyListeners();
  }

  @override
  void dispose() {
    _sessionExpiredController.close();
    super.dispose();
  }
}

class PasswordChangeException implements Exception {
  final String code;
  final String message;
  final List<String> problems;
  const PasswordChangeException(this.code, this.message, {this.problems = const []});

  @override
  String toString() => message;
}
