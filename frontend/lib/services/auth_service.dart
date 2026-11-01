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
  bool get isVolunteer => !isAdmin && !isTeamLeader && !isDocumentationTeam && !isMediaTeam;
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
  bool get canAccessDocumentation => isAdmin || isDocumentationTeam;
  bool get canCreateEvent => isAdmin || isTeamLeader;
  int? get memberId => (_currentUser?['member_id'] as num?)?.toInt();
  String? get memberName => _currentUser?['member_name']?.toString();
  String get displayName => memberName ?? username;
  int? get teamId => (_currentUser?['team_id'] as num?)?.toInt();
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

  Future<String?> getConfiguredBaseUrl() async {
    return await _storage.read(key: AppConstants.keyApiBaseUrl);
  }

  Future<void> setConfiguredBaseUrl(String url) async {
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
    final baseUrl = customBaseUrl ?? (await getConfiguredBaseUrl()) ?? AppConstants.defaultBaseUrl;
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
