import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'constants.dart';

class AppTheme {
  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: AppConstants.pureWhite,
      colorScheme: const ColorScheme.light(
        primary: AppConstants.pureBlack,
        onPrimary: AppConstants.pureWhite,
        surface: AppConstants.pureWhite,
        onSurface: AppConstants.pureBlack,
        error: AppConstants.dangerRed,
        onError: AppConstants.pureWhite,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppConstants.pureWhite,
        foregroundColor: AppConstants.pureBlack,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        systemOverlayStyle: SystemUiOverlayStyle.dark,
        titleTextStyle: TextStyle(
          color: AppConstants.pureBlack,
          fontSize: 18,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.2,
        ),
        iconTheme: IconThemeData(
          color: AppConstants.pureBlack,
          size: 20,
        ),
      ),
      cardTheme: const CardThemeData(
        color: AppConstants.pureWhite,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          side: BorderSide(color: AppConstants.borderLight, width: 1),
          borderRadius: BorderRadius.all(Radius.circular(8)),
        ),
      ),
      dividerTheme: const DividerThemeData(
        color: AppConstants.borderLight,
        thickness: 1,
        space: 1,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppConstants.pureWhite,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        hintStyle: const TextStyle(
          color: AppConstants.textSecondary,
          fontSize: 14,
          fontWeight: FontWeight.w400,
        ),
        labelStyle: const TextStyle(
          color: AppConstants.pureBlack,
          fontSize: 13,
          fontWeight: FontWeight.w500,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AppConstants.borderLight, width: 1),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AppConstants.borderLight, width: 1),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AppConstants.pureBlack, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AppConstants.dangerRed, width: 1),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AppConstants.dangerRed, width: 1.5),
        ),
        errorStyle: const TextStyle(
          color: AppConstants.dangerRed,
          fontSize: 12,
        ),
      ),
      textTheme: const TextTheme(
        displayLarge: TextStyle(color: AppConstants.pureBlack, fontSize: 28, fontWeight: FontWeight.w700),
        displayMedium: TextStyle(color: AppConstants.pureBlack, fontSize: 22, fontWeight: FontWeight.w600),
        titleLarge: TextStyle(color: AppConstants.pureBlack, fontSize: 18, fontWeight: FontWeight.w600),
        titleMedium: TextStyle(color: AppConstants.pureBlack, fontSize: 15, fontWeight: FontWeight.w600),
        bodyLarge: TextStyle(color: AppConstants.pureBlack, fontSize: 14, fontWeight: FontWeight.w400),
        bodyMedium: TextStyle(color: AppConstants.pureBlack, fontSize: 13, fontWeight: FontWeight.w400),
        bodySmall: TextStyle(color: AppConstants.textSecondary, fontSize: 12, fontWeight: FontWeight.w400),
        labelLarge: TextStyle(color: AppConstants.pureBlack, fontSize: 14, fontWeight: FontWeight.w500),
      ),
    );
  }
}
