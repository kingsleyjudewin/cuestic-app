import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/config/constants.dart';

void main() {
  group('ApiConfig.validate', () {
    test('accepts an HTTPS production URL in release mode', () {
      expect(ApiConfig.validate('https://cuestic-api.onrender.com/api/v1', release: true), isNull);
    });

    test('rejects localhost and emulator hosts in release mode', () {
      for (final url in [
        'http://127.0.0.1:5000/api/v1',
        'https://localhost/api/v1',
        'http://10.0.2.2:5000/api/v1',
      ]) {
        expect(ApiConfig.validate(url, release: true), isNotNull, reason: url);
      }
    });

    test('rejects plain HTTP in release mode', () {
      expect(ApiConfig.validate('http://cuestic-api.onrender.com/api/v1', release: true), isNotNull);
    });

    test('allows local HTTP during development', () {
      expect(ApiConfig.validate('http://127.0.0.1:5000/api/v1', release: false), isNull);
    });

    test('rejects malformed URLs', () {
      expect(ApiConfig.validate('', release: false), isNotNull);
      expect(ApiConfig.validate('not a url', release: false), isNotNull);
      expect(ApiConfig.validate('ftp://example.com', release: false), isNotNull);
    });
  });

  group('ApiConfig.resolve', () {
    test('falls back to the compiled-in URL when nothing valid is stored', () {
      expect(ApiConfig.resolve(null), ApiConfig.baseUrl);
      expect(ApiConfig.resolve('   '), ApiConfig.baseUrl);
      expect(ApiConfig.resolve('garbage'), ApiConfig.baseUrl);
    });

    test('uses a valid stored override only when overrides are allowed', () {
      final resolved = ApiConfig.resolve('http://192.168.1.20:5000/api/v1/');
      if (ApiConfig.allowServerOverride) {
        expect(resolved, 'http://192.168.1.20:5000/api/v1');
      } else {
        expect(resolved, ApiConfig.baseUrl);
      }
    });

    test('base URL never ends with a slash', () {
      expect(ApiConfig.baseUrl.endsWith('/'), isFalse);
    });
  });
}
