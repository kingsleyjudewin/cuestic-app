import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'api_client.dart';
import 'auth_service.dart';

@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  // Ensure Firebase is initialized for background processing if needed
  try {
    await Firebase.initializeApp();
  } catch (_) {}
  debugPrint('FCM background message received: ${message.messageId}');
}

class NotificationService {
  final ApiClient apiClient;
  final AuthService authService;
  final GlobalKey<NavigatorState> navigatorKey;

  bool _isFirebaseAvailable = false;
  String? _fcmToken;
  StreamSubscription<String>? _tokenRefreshSub;

  NotificationService({
    required this.apiClient,
    required this.authService,
    required this.navigatorKey,
  });


  bool get isFirebaseAvailable => _isFirebaseAvailable;
  String? get fcmToken => _fcmToken;

  Future<void> initialize() async {
    try {
      // Try to initialize Firebase
      await Firebase.initializeApp();
      _isFirebaseAvailable = true;

      // Register background message handler
      FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);

      // Request notification permissions
      final messaging = FirebaseMessaging.instance;
      final settings = await messaging.requestPermission(
        alert: true,
        announcement: false,
        badge: true,
        carPlay: false,
        criticalAlert: false,
        provisional: false,
        sound: true,
      );

      debugPrint('FCM Notification permission status: ${settings.authorizationStatus}');

      // Get initial device token
      // ignore: deprecated_member_use
      _fcmToken = await messaging.getToken();
      if (_fcmToken != null && authService.isAuthenticated) {
        await _registerTokenWithBackend(_fcmToken!);
      }

      // Listen for token refreshes
      // ignore: deprecated_member_use
      _tokenRefreshSub = messaging.onTokenRefresh.listen((newToken) async {
        _fcmToken = newToken;
        if (authService.isAuthenticated) {
          await _registerTokenWithBackend(newToken);
        }
      });


      // Handle foreground notifications
      FirebaseMessaging.onMessage.listen((RemoteMessage message) {
        debugPrint('FCM Foreground message: ${message.notification?.title} - ${message.notification?.body}');
        _showForegroundNotificationBanner(message);
      });

      // Handle notification tap when app opened from background
      FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
        debugPrint('FCM Notification tapped from background: ${message.data}');
        _handleNotificationTap(message.data);
      });

      // Check if app was opened via initial notification tap
      final initialMessage = await messaging.getInitialMessage();
      if (initialMessage != null) {
        debugPrint('FCM App opened via initial notification: ${initialMessage.data}');
        _handleNotificationTap(initialMessage.data);
      }
    } catch (e) {
      _isFirebaseAvailable = false;
      debugPrint('Firebase messaging initialization skipped or not configured: $e');
    }
  }

  Future<void> onUserLoggedIn() async {
    if (_fcmToken != null) {
      await _registerTokenWithBackend(_fcmToken!);
    } else if (_isFirebaseAvailable) {
      try {
        // ignore: deprecated_member_use
        _fcmToken = await FirebaseMessaging.instance.getToken();
        if (_fcmToken != null) {

          await _registerTokenWithBackend(_fcmToken!);
        }
      } catch (_) {}
    }
  }

  Future<void> onUserLoggedOut() async {
    if (_fcmToken != null && authService.isAuthenticated) {
      try {
        await apiClient.delete('/notifications/device-token', body: {'token': _fcmToken});
      } catch (_) {}
    }
  }

  Future<void> _registerTokenWithBackend(String token) async {
    try {
      await apiClient.post(
        '/notifications/device-token',
        body: {
          'token': token,
          'device_type': defaultTargetPlatform == TargetPlatform.iOS ? 'ios' : 'android',
          'device_name': 'Mobile Device',
        },
      );
      debugPrint('FCM Token registered with backend successfully.');
    } catch (e) {
      debugPrint('Failed to register FCM token with backend: $e');
    }
  }

  void _showForegroundNotificationBanner(RemoteMessage message) {
    final title = message.notification?.title ?? 'Notification';
    final body = message.notification?.body ?? '';
    final context = navigatorKey.currentContext;
    if (context == null) return;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.w600, color: Colors.white)),
            if (body.isNotEmpty) Text(body, style: const TextStyle(fontSize: 12, color: Colors.white70)),
          ],
        ),
        action: SnackBarAction(
          label: 'View',
          textColor: Colors.white,
          onPressed: () {
            _handleNotificationTap(message.data);
          },
        ),
        duration: const Duration(seconds: 4),
        behavior: SnackBarBehavior.floating,
        backgroundColor: const Color(0xFF111111),
      ),
    );
  }

  void _handleNotificationTap(Map<String, dynamic> data) {
    final assignmentIdStr = data['assignment_id']?.toString();
    if (assignmentIdStr != null && assignmentIdStr.isNotEmpty) {
      final assignmentId = int.tryParse(assignmentIdStr);
      if (assignmentId != null) {
        navigatorKey.currentState?.pushNamed('/assignment_detail', arguments: assignmentId);
      }
    }
  }

  void dispose() {
    _tokenRefreshSub?.cancel();
  }
}
