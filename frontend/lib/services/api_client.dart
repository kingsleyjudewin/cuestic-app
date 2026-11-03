import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import '../config/constants.dart';
import 'auth_service.dart';

class ApiException implements Exception {
  final int? statusCode;
  final String code;
  final String message;
  final Map<String, dynamic> details;

  ApiException({
    this.statusCode,
    required this.code,
    required this.message,
    this.details = const {},
  });

  @override
  String toString() => message;
}

class ApiClient {
  final http.Client _client;
  final AuthService authService;
  String? _customBaseUrl;

  static const Duration timeoutDuration = Duration(seconds: 45);

  ApiClient({http.Client? client, required this.authService})
      : _client = client ?? http.Client();

  Future<String> get baseUrl async {
    if (_customBaseUrl != null) return _customBaseUrl!;
    final configured = await authService.getConfiguredBaseUrl();

    if (configured != null && configured.trim().isNotEmpty) {
      _customBaseUrl = configured.trim();
      return _customBaseUrl!;
    }
    return AppConstants.defaultBaseUrl;
  }

  void updateBaseUrl(String newUrl) {
    _customBaseUrl = newUrl.endsWith('/') ? newUrl.substring(0, newUrl.length - 1) : newUrl;
  }

  Future<Map<String, String>> _headers({bool requiresAuth = true}) async {
    final headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    if (requiresAuth) {
      final token = await authService.getToken();
      if (token != null && token.isNotEmpty) {
        headers['Authorization'] = 'Bearer $token';
      }
    }

    return headers;
  }

  Future<dynamic> get(String endpoint, {Map<String, String>? queryParams, bool requiresAuth = true, Duration? timeout}) async {
    final root = await baseUrl;
    var uri = Uri.parse('$root$endpoint');
    if (queryParams != null && queryParams.isNotEmpty) {
      uri = uri.replace(queryParameters: queryParams);
    }

    try {
      final headers = await _headers(requiresAuth: requiresAuth);
      final response = await _client.get(uri, headers: headers).timeout(timeout ?? timeoutDuration);
      return _handleResponse(response);
    } on SocketException catch (_) {
      throw ApiException(
        code: 'NETWORK_ERROR',
        message: 'Unable to connect to the club server. Please check your network or server URL.',
      );
    } on TimeoutException catch (_) {
      throw ApiException(
        code: 'TIMEOUT',
        message: 'The request timed out. Please verify that the backend server is running.',
      );
    } on http.ClientException catch (e) {
      throw ApiException(
        code: 'NETWORK_ERROR',
        message: 'Connection failed: ${e.message}',
      );
    }
 catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(
        code: 'UNKNOWN',
        message: 'An unexpected connection error occurred: ${e.toString()}',
      );
    }
  }

  Future<dynamic> post(String endpoint, {Map<String, dynamic>? body, bool requiresAuth = true, Duration? timeout}) async {
    final root = await baseUrl;
    final uri = Uri.parse('$root$endpoint');

    try {
      final headers = await _headers(requiresAuth: requiresAuth);
      final response = await _client
          .post(uri, headers: headers, body: body != null ? jsonEncode(body) : null)
          .timeout(timeout ?? timeoutDuration);
      return _handleResponse(response);
    } on SocketException catch (_) {
      throw ApiException(
        code: 'NETWORK_ERROR',
        message: 'Unable to connect to the club server. Please check your network or server URL.',
      );
    } on TimeoutException catch (_) {
      throw ApiException(
        code: 'TIMEOUT',
        message: 'The request timed out. Please try again.',
      );
    } on http.ClientException catch (e) {
      throw ApiException(
        code: 'NETWORK_ERROR',
        message: 'Connection failed: ${e.message}',
      );
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(
        code: 'UNKNOWN',
        message: 'An unexpected error occurred: ${e.toString()}',
      );
    }
  }

  Future<dynamic> put(String endpoint, {Map<String, dynamic>? body, bool requiresAuth = true, Duration? timeout}) async {
    final root = await baseUrl;
    final uri = Uri.parse('$root$endpoint');

    try {
      final headers = await _headers(requiresAuth: requiresAuth);
      final response = await _client
          .put(uri, headers: headers, body: body != null ? jsonEncode(body) : null)
          .timeout(timeout ?? timeoutDuration);
      return _handleResponse(response);
    } on SocketException catch (_) {
      throw ApiException(
        code: 'NETWORK_ERROR',
        message: 'Unable to connect to the club server.',
      );
    } on TimeoutException catch (_) {
      throw ApiException(
        code: 'TIMEOUT',
        message: 'Request timed out.',
      );
    } on http.ClientException catch (e) {
      throw ApiException(
        code: 'NETWORK_ERROR',
        message: 'Connection failed: ${e.message}',
      );
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(
        code: 'UNKNOWN',
        message: 'An unexpected error occurred: ${e.toString()}',
      );
    }
  }

  Future<dynamic> patch(String endpoint, {Map<String, dynamic>? body, bool requiresAuth = true, Duration? timeout}) async {
    final root = await baseUrl;
    final uri = Uri.parse('$root$endpoint');

    try {
      final headers = await _headers(requiresAuth: requiresAuth);
      final response = await _client
          .patch(uri, headers: headers, body: body != null ? jsonEncode(body) : null)
          .timeout(timeout ?? timeoutDuration);
      return _handleResponse(response);
    } on SocketException catch (_) {
      throw ApiException(
        code: 'NETWORK_ERROR',
        message: 'Unable to connect to the club server.',
      );
    } on TimeoutException catch (_) {
      throw ApiException(
        code: 'TIMEOUT',
        message: 'Request timed out.',
      );
    } on http.ClientException catch (e) {
      throw ApiException(
        code: 'NETWORK_ERROR',
        message: 'Connection failed: ${e.message}',
      );
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(
        code: 'UNKNOWN',
        message: 'An unexpected error occurred: ${e.toString()}',
      );
    }
  }

  Future<dynamic> delete(String endpoint, {Map<String, dynamic>? body, bool requiresAuth = true, Duration? timeout}) async {
    final root = await baseUrl;
    final uri = Uri.parse('$root$endpoint');

    try {
      final headers = await _headers(requiresAuth: requiresAuth);
      final response = await _client
          .delete(uri, headers: headers, body: body != null ? jsonEncode(body) : null)
          .timeout(timeout ?? timeoutDuration);
      return _handleResponse(response);
    } on http.ClientException catch (e) {
      throw ApiException(
        code: 'NETWORK_ERROR',
        message: 'Connection failed: ${e.message}',
      );
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(
        code: 'UNKNOWN',
        message: 'Delete request failed.',
      );
    }
  }

  Future<dynamic> uploadMultipart(
    String endpoint, {
    required List<int> fileBytes,
    required String filename,
    String fieldName = 'file',
    Map<String, String>? fields,
    bool requiresAuth = true,
  }) async {
    final root = await baseUrl;
    final uri = Uri.parse('$root$endpoint');
    final request = http.MultipartRequest('POST', uri);

    if (requiresAuth) {
      final token = await authService.getToken();
      if (token != null && token.isNotEmpty) {
        request.headers['Authorization'] = 'Bearer $token';
      }
    }
    if (fields != null) {
      request.fields.addAll(fields);
    }
    request.files.add(
      http.MultipartFile.fromBytes(
        fieldName,
        fileBytes,
        filename: filename,
      ),
    );

    final streamedResponse = await _client.send(request).timeout(const Duration(seconds: 45));
    final response = await http.Response.fromStream(streamedResponse);
    return _handleResponse(response);
  }

  Future<List<int>> getBinary(String endpoint, {bool requiresAuth = true}) async {
    final root = await baseUrl;
    final uri = Uri.parse('$root$endpoint');
    final headers = <String, String>{};
    if (requiresAuth) {
      final token = await authService.getToken();
      if (token != null && token.isNotEmpty) {
        headers['Authorization'] = 'Bearer $token';
      }
    }
    final response = await _client.get(uri, headers: headers).timeout(const Duration(seconds: 30));
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return response.bodyBytes;
    }
    throw ApiException(
      statusCode: response.statusCode,
      code: 'DOWNLOAD_FAILED',
      message: 'Failed to download file (${response.statusCode})',
    );
  }

  dynamic _handleResponse(http.Response response) {
    dynamic decoded;
    if (response.body.isNotEmpty) {
      try {
        decoded = jsonDecode(response.body);
      } catch (_) {
        decoded = null;
      }
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (decoded is Map<String, dynamic> && decoded.containsKey('data')) {
        return decoded['data'];
      }
      return decoded;
    }

    // Extract error info safely without leaking server stack traces
    String errorCode = 'HTTP_${response.statusCode}';
    String errorMessage = 'Server returned error (${response.statusCode})';
    Map<String, dynamic> details = {};

    if (decoded is Map<String, dynamic>) {
      if (decoded['error'] is Map<String, dynamic>) {
        final err = decoded['error'] as Map<String, dynamic>;
        errorCode = err['code']?.toString() ?? errorCode;
        errorMessage = err['message']?.toString() ?? errorMessage;
        if (err['details'] is Map<String, dynamic>) {
          details = err['details'] as Map<String, dynamic>;
        }
      } else if (decoded['message'] != null) {
        errorMessage = decoded['message'].toString();
      }
    }

    if (response.statusCode == 401) {
      authService.handleSessionExpired();
      throw ApiException(

        statusCode: 401,
        code: 'UNAUTHORIZED',
        message: errorMessage.isNotEmpty ? errorMessage : 'Session expired. Please log in again.',
        details: details,
      );
    } else if (response.statusCode == 403) {
      throw ApiException(
        statusCode: 403,
        code: 'FORBIDDEN',
        message: errorMessage.isNotEmpty ? errorMessage : 'You do not have permission for this action.',
        details: details,
      );
    } else if (response.statusCode == 404) {
      throw ApiException(
        statusCode: 404,
        code: 'NOT_FOUND',
        message: errorMessage.isNotEmpty ? errorMessage : 'The requested resource was not found.',
        details: details,
      );
    } else if (response.statusCode == 409) {
      throw ApiException(
        statusCode: 409,
        code: 'CONFLICT',
        message: errorMessage,
        details: details,
      );
    } else if (response.statusCode >= 500) {
      throw ApiException(
        statusCode: response.statusCode,
        code: 'SERVER_ERROR',
        message: 'A departmental server error occurred. Please try again later.',
        details: details,
      );
    } else {
      throw ApiException(
        statusCode: response.statusCode,
        code: errorCode,
        message: errorMessage,
        details: details,
      );
    }
  }
}
