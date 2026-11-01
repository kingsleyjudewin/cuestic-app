import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/services/api_client.dart';
import 'package:mobile/services/auth_service.dart';

void main() {
  setUpAll(() {
    TestWidgetsFlutterBinding.ensureInitialized();
    FlutterSecureStorage.setMockInitialValues({
      'auth_token': 'mock_valid_token',
    });
  });

  group('ApiClient Tests', () {
    test('Successful GET unwraps data payload', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/events');
        return http.Response(
          jsonEncode({
            'success': true,
            'data': [
              {'id': 1, 'name': 'Demo Event'}
            ]
          }),
          200,
        );
      });

      final authService = AuthService();
      await authService.initialize();
      final client = ApiClient(client: mockClient, authService: authService);

      final result = await client.get('/events', requiresAuth: false);
      expect(result, isA<List>());
      expect((result as List).first['name'], 'Demo Event');
    });

    test('Attaches Authorization header when requiresAuth is true', () async {
      final mockClient = MockClient((request) async {
        expect(request.headers['Authorization'], 'Bearer mock_valid_token');
        return http.Response(jsonEncode({'success': true, 'data': {}}), 200);
      });

      final authService = AuthService();
      await authService.initialize();
      final client = ApiClient(client: mockClient, authService: authService);

      await client.get('/protected', requiresAuth: true);
    });

    test('Handles 401 Unauthorized by clearing session and throwing ApiException', () async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'success': false,
            'error': {
              'code': 'AUTHENTICATION_ERROR',
              'message': 'Token expired.',
            }
          }),
          401,
        );
      });

      final authService = AuthService();
      await authService.initialize();
      final client = ApiClient(client: mockClient, authService: authService);

      expect(
        () async => await client.get('/events'),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'statusCode', 401)),
      );
    });

    test('Handles 404 NotFound cleanly', () async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'success': false,
            'error': {
              'code': 'NOT_FOUND',
              'message': 'Event not found.',
            }
          }),
          404,
        );
      });

      final authService = AuthService();
      await authService.initialize();
      final client = ApiClient(client: mockClient, authService: authService);

      expect(
        () async => await client.get('/events/9999'),
        throwsA(isA<ApiException>().having((e) => e.code, 'code', 'NOT_FOUND')),
      );
    });

    test('Handles 500 Internal Server Error without leaking internal stack traces', () async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'success': false,
            'error': {
              'code': 'INTERNAL_SERVER_ERROR',
              'message': 'Internal error details',
            }
          }),
          500,
        );
      });

      final authService = AuthService();
      await authService.initialize();
      final client = ApiClient(client: mockClient, authService: authService);

      try {
        await client.get('/error');
        fail('Expected ApiException');
      } on ApiException catch (e) {
        expect(e.statusCode, 500);
        expect(e.message, contains('departmental server error'));
      }
    });
  });
}
