import 'package:flutter/material.dart';

class AppConstants {
  // Default API Host (configurable in-app for emulator/device/local dev)
  static const String defaultBaseUrl = 'http://127.0.0.1:5000/api/v1';

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
