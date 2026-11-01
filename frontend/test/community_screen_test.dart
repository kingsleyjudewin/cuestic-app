import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/config/app_theme.dart';
import 'package:mobile/config/constants.dart';
import 'package:mobile/screens/community_screen.dart';
import 'package:mobile/services/api_client.dart';
import 'package:mobile/services/auth_service.dart';
import 'package:mobile/services/community_service.dart';

void main() {
  setUpAll(() {
    TestWidgetsFlutterBinding.ensureInitialized();
  });

  group('Discord-like Community & Group Chat Module Tests', () {
    late AuthService authService;

    setUp(() {
      FlutterSecureStorage.setMockInitialValues({
        AppConstants.keyAuthToken: 'test-community-token',
        AppConstants.keyUserData: jsonEncode({
          'id': 38,
          'username': 'sagar.cu',
          'role': 'member',
          'member_name': 'Sagar CU',
        }),
      });
      authService = AuthService();
    });

    testWidgets('1. CommunityScreen renders server rail, channels, and messages', (tester) async {
      tester.view.physicalSize = const Size(1000, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await authService.initialize();

      final mockClient = MockClient((request) async {
        if (request.url.path.endsWith('/communities') && request.method == 'GET') {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {
                  'id': 2,
                  'name': 'Volunteering Team Community',
                  'slug': 'volunteering-community',
                  'color': '#10B981',
                  'team_id': 1,
                  'channel_count': 3,
                  'member_count': 9,
                  'channels': [
                    {'id': 10, 'community_id': 2, 'name': 'general', 'topic': 'General discussion'},
                    {'id': 11, 'community_id': 2, 'name': 'announcements', 'topic': 'Broadcasts'},
                    {'id': 12, 'community_id': 2, 'name': 'volunteers-chat', 'topic': 'Task coordination'},
                  ],
                },
              ],
            }),
            200,
          );
        } else if (request.url.path.endsWith('/communities/2') && request.method == 'GET') {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {
                'id': 2,
                'name': 'Volunteering Team Community',
                'slug': 'volunteering-community',
                'channels': [
                  {'id': 10, 'community_id': 2, 'name': 'general', 'topic': 'General discussion'},
                  {'id': 11, 'community_id': 2, 'name': 'announcements', 'topic': 'Broadcasts'},
                  {'id': 12, 'community_id': 2, 'name': 'volunteers-chat', 'topic': 'Task coordination'},
                ],
                'members': [
                  {'id': 1, 'username': 'sagar.cu', 'display_name': 'Sagar CU', 'user_role': 'member', 'role': 'member'},
                  {'id': 2, 'username': 'kanishk', 'display_name': 'Kanishk M', 'user_role': 'member', 'role': 'member'},
                ],
              },
            }),
            200,
          );
        } else if (request.url.path.contains('/messages') && request.method == 'GET') {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {
                  'id': 101,
                  'community_id': 2,
                  'channel_id': 10,
                  'sender_name': 'Sagar CU',
                  'sender_role': 'member',
                  'content': 'Hello volunteering team!',
                  'created_at': DateTime.now().toIso8601String(),
                },
              ],
            }),
            200,
          );
        }
        return http.Response('{}', 200);
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final communityService = CommunityService(apiClient: apiClient);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: CommunityScreen(
            communityService: communityService,
            authService: authService,
            enablePolling: false,
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Verify Community Header & Server Rail
      expect(find.text('Volunteering Team Community'), findsWidgets);
      expect(find.byKey(const Key('server_icon_volunteering-community')), findsOneWidget);

      // Verify Channels list
      expect(find.text('general'), findsWidgets);
      expect(find.text('announcements'), findsOneWidget);
      expect(find.text('volunteers-chat'), findsOneWidget);

      // Verify Message
      expect(find.text('Hello volunteering team!'), findsOneWidget);
      expect(find.text('Sagar CU'), findsOneWidget);
    });

    testWidgets('2. Sending message posts to channel and renders immediately', (tester) async {
      tester.view.physicalSize = const Size(1000, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await authService.initialize();
      bool messageSent = false;
      String? sentContent;

      final mockClient = MockClient((request) async {
        if (request.url.path.endsWith('/communities') && request.method == 'GET') {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {
                  'id': 2,
                  'name': 'Volunteering Team Community',
                  'slug': 'volunteering-community',
                  'channels': [
                    {'id': 10, 'community_id': 2, 'name': 'volunteers-chat', 'topic': 'Task chat'},
                  ],
                },
              ],
            }),
            200,
          );
        } else if (request.url.path.endsWith('/communities/2') && request.method == 'GET') {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {
                'id': 2,
                'name': 'Volunteering Team Community',
                'slug': 'volunteering-community',
                'channels': [
                  {'id': 10, 'community_id': 2, 'name': 'volunteers-chat', 'topic': 'Task chat'},
                ],
                'members': [],
              },
            }),
            200,
          );
        } else if (request.url.path.contains('/messages') && request.method == 'GET') {
          return http.Response(
            jsonEncode({'success': true, 'data': []}),
            200,
          );
        } else if (request.url.path.contains('/messages') && request.method == 'POST') {
          messageSent = true;
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          sentContent = body['content'] as String;
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {
                'id': 202,
                'community_id': 2,
                'channel_id': 10,
                'sender_name': 'Kanishk M',
                'sender_role': 'member',
                'content': sentContent,
                'created_at': DateTime.now().toIso8601String(),
              },
            }),
            201,
          );
        }
        return http.Response('{}', 200);
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final communityService = CommunityService(apiClient: apiClient);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: CommunityScreen(
            communityService: communityService,
            authService: authService,
            enablePolling: false,
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Enter message and send
      await tester.enterText(
        find.byKey(const Key('input_chat_message')),
        'Hall seating counters setup is complete!',
      );
      await tester.tap(find.byKey(const Key('btn_send_chat_message')));
      await tester.pumpAndSettle();

      expect(messageSent, isTrue);
      expect(sentContent, 'Hall seating counters setup is complete!');
      expect(find.text('Hall seating counters setup is complete!'), findsOneWidget);
    });

    testWidgets('3. Creating a channel via modal adds it to community channels list', (tester) async {
      tester.view.physicalSize = const Size(1000, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await authService.initialize();
      bool createChannelCalled = false;

      final mockClient = MockClient((request) async {
        if (request.url.path.endsWith('/communities') && request.method == 'GET') {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': [
                {
                  'id': 2,
                  'name': 'Volunteering Team Community',
                  'slug': 'volunteering-community',
                  'channels': [
                    {'id': 10, 'community_id': 2, 'name': 'general', 'topic': 'General discussion'},
                  ],
                },
              ],
            }),
            200,
          );
        } else if (request.url.path.endsWith('/communities/2') && request.method == 'GET') {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {
                'id': 2,
                'name': 'Volunteering Team Community',
                'slug': 'volunteering-community',
                'channels': [
                  {'id': 10, 'community_id': 2, 'name': 'general', 'topic': 'General discussion'},
                ],
                'members': [],
              },
            }),
            200,
          );
        } else if (request.url.path.endsWith('/channels') && request.method == 'POST') {
          createChannelCalled = true;
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {
                'id': 15,
                'community_id': 2,
                'name': 'stage-audio-team',
                'topic': 'Stage and mic checks',
                'channel_type': 'group_chat',
                'position': 2,
              },
            }),
            201,
          );
        } else if (request.url.path.contains('/messages') && request.method == 'GET') {
          return http.Response(jsonEncode({'success': true, 'data': []}), 200);
        }
        return http.Response('{}', 200);
      });

      final apiClient = ApiClient(client: mockClient, authService: authService);
      final communityService = CommunityService(apiClient: apiClient);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: CommunityScreen(
            communityService: communityService,
            authService: authService,
            enablePolling: false,
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Tap Add Channel button
      await tester.tap(find.byKey(const Key('btn_add_channel')));
      await tester.pumpAndSettle();

      // Modal is open
      expect(find.text('Create Channel / Group Chat'), findsOneWidget);

      // Enter channel name
      await tester.enterText(find.byKey(const Key('input_new_channel_name')), 'stage-audio-team');
      await tester.enterText(find.byKey(const Key('input_new_channel_topic')), 'Stage and mic checks');

      // Tap Create Channel button
      await tester.tap(find.byKey(const Key('btn_confirm_create_channel')));
      await tester.pumpAndSettle();

      expect(createChannelCalled, isTrue);
      expect(find.text('stage-audio-team'), findsWidgets);
    });
  });
}
