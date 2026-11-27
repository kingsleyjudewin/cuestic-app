import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

/// Central backend URL configuration, fixed at build time.
///
///   flutter build web --release --dart-define=API_BASE_URL=https://YOUR-SERVICE.onrender.com/api/v1
///   flutter build apk --release --dart-define=API_BASE_URL=https://YOUR-SERVICE.onrender.com/api/v1
///
/// Debug builds fall back to a local backend and keep the "Server API URL" override on the
/// login screen. Release builds always use API_BASE_URL and ignore any stored override.
class ApiConfig {
  static const String _fromEnvironment = String.fromEnvironment('API_BASE_URL');
  static const String _developmentDefault = 'http://127.0.0.1:5000/api/v1';

  /// Lets testers point a build at another server. On by default only in debug builds.
  static const bool allowServerOverride =
      bool.fromEnvironment('ALLOW_SERVER_URL_OVERRIDE', defaultValue: !kReleaseMode);

  static String get baseUrl {
    final raw = _fromEnvironment.trim().isNotEmpty ? _fromEnvironment.trim() : _developmentDefault;
    return raw.endsWith('/') ? raw.substring(0, raw.length - 1) : raw;
  }

  /// Returns a human-readable problem with [url], or null when it is usable.
  static String? validate(String url, {bool release = kReleaseMode}) {
    final uri = Uri.tryParse(url.trim());
    if (url.trim().isEmpty || uri == null || !uri.hasScheme || uri.host.isEmpty) {
      return 'The server address "$url" is not a valid URL.';
    }
    if (uri.scheme != 'http' && uri.scheme != 'https') {
      return 'The server address must start with http:// or https://.';
    }
    if (release) {
      const localHosts = {'localhost', '127.0.0.1', '0.0.0.0', '10.0.2.2'};
      if (localHosts.contains(uri.host)) {
        return 'This release build points to a local development server ($url). '
            'Rebuild it with --dart-define=API_BASE_URL=https://<your-backend>/api/v1.';
      }
      if (uri.scheme != 'https') {
        return 'Release builds must use HTTPS for the server address ($url).';
      }
    }
    return null;
  }

  /// Set only for release builds that intentionally talk to a local backend
  /// (scripts/run_localhost.sh): --dart-define=ALLOW_LOCAL_API=true
  static const bool allowLocalApi = bool.fromEnvironment('ALLOW_LOCAL_API');

  /// Problem with the compiled-in configuration, or null when it is valid.
  static String? get configurationError => validate(baseUrl, release: kReleaseMode && !allowLocalApi);

  /// Picks the URL to use: a stored override (only when allowed and valid), else [baseUrl].
  static String resolve(String? storedOverride) {
    final stored = storedOverride?.trim() ?? '';
    if (allowServerOverride && stored.isNotEmpty && validate(stored, release: false) == null) {
      return stored.endsWith('/') ? stored.substring(0, stored.length - 1) : stored;
    }
    return baseUrl;
  }
}

class AppConstants {
  /// Backend API base URL from build configuration (see [ApiConfig]).
  static final String defaultBaseUrl = ApiConfig.baseUrl;

  // Secure Storage Keys
  static const String keyAuthToken = 'auth_token';
  static const String keyUserData = 'user_data';
  static const String keyApiBaseUrl = 'api_base_url';
  static const String keyLastSelectedEventId = 'last_selected_event_id';
  static const String keyLastSelectedEventName = 'last_selected_event_name';

  // Colors
  static const Color pureWhite = Color(0xFFFFFFFF);
  static const Color pureBlack = Color(0xFF111111);
  static const Color darkGray = Color(0xFF2E2E2E);
  static const Color textSecondary = Color(0xFF6B7280);
  static const Color borderLight = Color(0xFFE5E7EB);
  static const Color borderSubtle = Color(0xFFF3F4F6);
  static const Color backgroundLight = Color(0xFFFAFAFA);
  static const Color dangerRed = Color(0xFFDC2626);
  static const Color warningOrange = Color(0xFFD97706);
  static const Color successGreen = Color(0xFF059669);

  // Gradient for primary buttons
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [Color(0xFF111111), Color(0xFF2E2E2E)],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );

  static const LinearGradient disabledGradient = LinearGradient(
    colors: [Color(0xFF9CA3AF), Color(0xFF9CA3AF)],
  );
}
