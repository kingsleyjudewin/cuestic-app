import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/main.dart';
import 'package:mobile/screens/mandatory_password_change_screen.dart';
import 'package:mobile/services/api_client.dart';
import 'package:mobile/services/auth_service.dart';
import 'package:mobile/services/community_service.dart';
import 'package:mobile/services/notification_service.dart';
import 'package:mobile/services/research_service.dart';
import 'package:mobile/services/storage_service.dart';
import 'package:mobile/services/sync_service.dart';
import 'package:mobile/services/whatsapp_service.dart';
import 'package:mobile/utils/password_policy.dart';

const strongPw = 'Brand#NewSecret2026';

Map<String, dynamic> userJson(String role, {bool required = true}) => {
      'id': 7,
      'username': 'user.$role',
      'role': role,
      'password_change_required': required,
      'must_change_password': required,
      'credential_setup_status': 'completed',
    };

Future<AuthService> signedInAs(String role, {bool required = true, http.Client? client}) async {
  FlutterSecureStorage.setMockInitialValues({
    'auth_token': 'restricted_token',
    'user_data': jsonEncode(userJson(role, required: required)),
  });
  final auth = AuthService(client: client);
  await auth.initialize();
  return auth;
}

http.Response jsonResponse(Object body, int status) =>
    http.Response(jsonEncode(body), status, headers: {'content-type': 'application/json'});

http.Response error(int status, String code, String message, [Map<String, dynamic>? details]) => jsonResponse({
      'success': false,
      'error': {'code': code, 'message': message, 'details': details ?? {}},
    }, status);

/// Mirrors how main.dart picks the home screen, without the data-heavy dashboards.
class Harness extends StatefulWidget {
  final AuthService auth;
  const Harness(this.auth, {super.key});
  @override
  State<Harness> createState() => _HarnessState();
}

class _HarnessState extends State<Harness> {
  @override
  void initState() {
    super.initState();
    widget.auth.addListener(() => setState(() {}));
  }

  @override
  Widget build(BuildContext context) {
    Widget home;
    if (!widget.auth.isAuthenticated) {
      home = const Text('LOGIN SCREEN');
    } else if (widget.auth.mustChangePassword) {
      home = MandatoryPasswordChangeScreen(
        authService: widget.auth,
        onPasswordChanged: () => setState(() {}),
        onLogout: () => widget.auth.logout(),
      );
    } else {
      home = const Text('DASHBOARD');
    }
    return MaterialApp(home: home);
  }
}

Future<void> fillForm(WidgetTester t, {String current = 'Leaked-Pass-2025!', String next = strongPw, String? confirm}) async {
  await t.enterText(find.byKey(const Key('currentPasswordField')), current);
  await t.enterText(find.byKey(const Key('newPasswordField')), next);
  await t.enterText(find.byKey(const Key('confirmPasswordField')), confirm ?? next);
}

Future<void> submit(WidgetTester t) async {
  await t.ensureVisible(find.byKey(const Key('createPasswordButton')));
  await t.tap(find.byKey(const Key('createPasswordButton')));
  await t.pumpAndSettle();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Who must change their password', () {
    for (final role in ['president', 'team_leader', 'member', 'faculty_coordinator', 'student_researcher']) {
      test('$role is restricted', () async {
        expect((await signedInAs(role)).mustChangePassword, isTrue);
      });
    }

    test('admin is never restricted, even if the flag is set', () async {
      expect((await signedInAs('admin')).mustChangePassword, isFalse);
    });

    test('user who completed the change is not restricted', () async {
      expect((await signedInAs('member', required: false)).mustChangePassword, isFalse);
    });

    test('403 PASSWORD_CHANGE_REQUIRED from any API call switches the app to the popup', () async {
      final auth = await signedInAs('member', required: false);
      final api = ApiClient(
        authService: auth,
        client: MockClient((_) async => error(403, 'PASSWORD_CHANGE_REQUIRED', 'Change your password before accessing this resource.')),
      );
      await expectLater(api.get('/teams'), throwsA(isA<ApiException>().having((e) => e.code, 'code', 'PASSWORD_CHANGE_REQUIRED')));
      expect(auth.mustChangePassword, isTrue);
      expect(auth.isAuthenticated, isTrue); // not logged out
    });

    test('a normal 403 does not trigger the popup', () async {
      final auth = await signedInAs('member', required: false);
      final api = ApiClient(authService: auth, client: MockClient((_) async => error(403, 'PERMISSION_DENIED', 'No.')));
      await expectLater(api.get('/teams'), throwsA(isA<ApiException>()));
      expect(auth.mustChangePassword, isFalse);
    });
  });

  group('Password policy (same rules as the server)', () {
    test('accepts a strong password and rejects weak ones', () {
      expect(PasswordPolicy.problems(strongPw), isEmpty);
      expect(PasswordPolicy.problems('short#A1'), isNotEmpty);
      expect(PasswordPolicy.problems('alllowercase#2026'), isNotEmpty);
      expect(PasswordPolicy.problems('NoSpecialChars2026'), isNotEmpty);
      expect(PasswordPolicy.problems('Kingsley#Strong2026', username: 'kingsley.cu'), contains('Must not contain your username'));
      expect(PasswordPolicy.strength(''), 0);
      expect(PasswordPolicy.strength('abc'), 1);
      expect(PasswordPolicy.strength(strongPw), greaterThanOrEqualTo(3));
    });
  });

  group('Popup', () {
    testWidgets('restricted user opening the real app sees the popup instead of a dashboard', (t) async {
      final auth = await signedInAs('president');
      final api = ApiClient(authService: auth, client: MockClient((_) async => jsonResponse({'success': true, 'data': []}, 200)));
      final key = GlobalKey<NavigatorState>();
      final sync = SyncService(apiClient: api, storageService: StorageService());
      await t.pumpWidget(DepartmentClubApp(
        navigatorKey: key,
        authService: auth,
        researchService: ResearchService(auth),
        syncService: sync,
        whatsAppService: WhatsAppService(syncService: sync),
        communityService: CommunityService(apiClient: api),
        notificationService: NotificationService(apiClient: api, authService: auth, navigatorKey: key),
      ));
      await t.pump();
      expect(find.byType(MandatoryPasswordChangeScreen), findsOneWidget);
      expect(find.text('Create Your New Password'), findsOneWidget);
    });

    testWidgets('shows title, description, three fields and both buttons', (t) async {
      await t.pumpWidget(Harness(await signedInAs('member')));
      expect(find.text('Create Your New Password'), findsOneWidget);
      expect(find.textContaining("For your account's security"), findsOneWidget);
      expect(find.byKey(const Key('currentPasswordField')), findsOneWidget);
      expect(find.byKey(const Key('newPasswordField')), findsOneWidget);
      expect(find.byKey(const Key('confirmPasswordField')), findsOneWidget);
      expect(find.text('Create New Password'), findsOneWidget);
      expect(find.text('Log Out'), findsOneWidget);
    });

    testWidgets('admin never sees the popup', (t) async {
      await t.pumpWidget(Harness(await signedInAs('admin')));
      expect(find.byType(MandatoryPasswordChangeScreen), findsNothing);
      expect(find.text('DASHBOARD'), findsOneWidget);
    });

    testWidgets('cannot be dismissed with the back button', (t) async {
      await t.pumpWidget(Harness(await signedInAs('member')));
      final popped = await t.binding.handlePopRoute();
      await t.pumpAndSettle();
      expect(popped, isTrue); // PopScope consumed the back gesture
      expect(find.byType(MandatoryPasswordChangeScreen), findsOneWidget);
    });

    testWidgets('visibility toggle shows and hides the password', (t) async {
      await t.pumpWidget(Harness(await signedInAs('member')));
      EditableText field() => t.widget<EditableText>(
          find.descendant(of: find.byKey(const Key('newPasswordField')), matching: find.byType(EditableText)));
      expect(field().obscureText, isTrue);
      await t.tap(find.byKey(const Key('toggleNewPassword')));
      await t.pump();
      expect(field().obscureText, isFalse);
      await t.tap(find.byKey(const Key('toggleNewPassword')));
      await t.pump();
      expect(field().obscureText, isTrue);
    });

    testWidgets('validates mismatch and weak passwords without calling the server', (t) async {
      var calls = 0;
      final auth = await signedInAs('member', client: MockClient((_) async {
        calls++;
        return jsonResponse({}, 500);
      }));
      await t.pumpWidget(Harness(auth));
      await fillForm(t, confirm: 'Different#Secret2026');
      await submit(t);
      expect(find.text('Passwords do not match'), findsOneWidget);

      await fillForm(t, next: 'weakpass', confirm: 'weakpass');
      await submit(t);
      expect(find.textContaining('Password needs'), findsOneWidget);
      expect(calls, 0);
    });

    testWidgets('strength indicator reacts to typing', (t) async {
      await t.pumpWidget(Harness(await signedInAs('member')));
      await t.enterText(find.byKey(const Key('newPasswordField')), 'abc');
      await t.pump();
      expect(t.widget<Text>(find.byKey(const Key('passwordStrengthLabel'))).data, 'Weak');
      await t.enterText(find.byKey(const Key('newPasswordField')), 'Much#Stronger2026Pass');
      await t.pump();
      expect(t.widget<Text>(find.byKey(const Key('passwordStrengthLabel'))).data, 'Strong');
    });

    testWidgets('shows server errors: wrong current password, weak password, network failure', (t) async {
      final responses = <http.Response Function()>[
        () => error(400, 'INVALID_CURRENT_PASSWORD', 'Current password is incorrect.'),
        () => error(400, 'WEAK_PASSWORD', 'too common', {'new_password': ['This password is too common or has appeared in a data leak. Choose a different one.']}),
        () => throw http.ClientException('offline'),
      ];
      final auth = await signedInAs('member', client: MockClient((_) async => responses.removeAt(0)()));
      await t.pumpWidget(Harness(auth));

      await fillForm(t);
      await submit(t);
      expect(find.text('Current password is incorrect.'), findsOneWidget);

      await fillForm(t);
      await submit(t);
      expect(find.textContaining('appeared in a data leak'), findsOneWidget);

      await fillForm(t);
      await submit(t);
      expect(find.textContaining('Could not reach the server'), findsOneWidget);
      expect(find.byType(MandatoryPasswordChangeScreen), findsOneWidget); // still blocked
      expect(auth.isAuthenticated, isTrue);
    });

    testWidgets('disables the button and shows a spinner while submitting', (t) async {
      final auth = await signedInAs('member', client: MockClient((_) async {
        await Future<void>.delayed(const Duration(milliseconds: 300));
        return error(400, 'INVALID_CURRENT_PASSWORD', 'Current password is incorrect.');
      }));
      await t.pumpWidget(Harness(auth));
      await fillForm(t);
      await t.ensureVisible(find.byKey(const Key('createPasswordButton')));
      await t.tap(find.byKey(const Key('createPasswordButton')));
      await t.pump();
      expect(t.widget<ElevatedButton>(find.byKey(const Key('createPasswordButton'))).onPressed, isNull);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      await t.pumpAndSettle();
    });

    testWidgets('success replaces the session and opens the dashboard only after server confirmation', (t) async {
      late http.Request sent;
      final auth = await signedInAs('member', client: MockClient((req) async {
        sent = req;
        return jsonResponse({
          'success': true,
          'data': {'token': 'fresh_token', 'user': userJson('member', required: false), 'password_change_required': false},
        }, 200);
      }));
      await t.pumpWidget(Harness(auth));
      await fillForm(t);
      await submit(t);

      expect(sent.url.path, endsWith('/auth/change-password'));
      expect(sent.headers['Authorization'], 'Bearer restricted_token');
      expect(jsonDecode(sent.body), {
        'current_password': 'Leaked-Pass-2025!',
        'new_password': strongPw,
        'confirm_password': strongPw,
      });
      expect(auth.token, 'fresh_token');
      expect(auth.mustChangePassword, isFalse);
      expect(find.text('DASHBOARD'), findsOneWidget);
      expect(find.byType(MandatoryPasswordChangeScreen), findsNothing);
    });

    testWidgets('expired session returns the user to login', (t) async {
      final auth = await signedInAs('member', client: MockClient((_) async => error(401, 'AUTHENTICATION_ERROR', 'Token is invalid, expired, or revoked.')));
      await t.pumpWidget(Harness(auth));
      await fillForm(t);
      await submit(t);
      expect(auth.isAuthenticated, isFalse);
      expect(find.text('LOGIN SCREEN'), findsOneWidget);
    });

    testWidgets('Log Out leaves the popup and signs out', (t) async {
      final auth = await signedInAs('member', client: MockClient((_) async => jsonResponse({'success': true}, 200)));
      await t.pumpWidget(Harness(auth));
      await t.ensureVisible(find.byKey(const Key('logoutButton')));
      await t.tap(find.byKey(const Key('logoutButton')));
      await t.pumpAndSettle();
      expect(auth.isAuthenticated, isFalse);
      expect(find.text('LOGIN SCREEN'), findsOneWidget);
    });

    testWidgets('fits a narrow phone and a wide desktop window', (t) async {
      for (final size in [const Size(360, 740), const Size(1440, 900)]) {
        t.view.physicalSize = size;
        t.view.devicePixelRatio = 1;
        await t.pumpWidget(Harness(await signedInAs('member')));
        await t.pumpAndSettle();
        expect(t.takeException(), isNull);
        expect(t.getSize(find.byKey(const Key('mandatoryPasswordDialog'))).width, lessThanOrEqualTo(460));
      }
      t.view.resetPhysicalSize();
      t.view.resetDevicePixelRatio();
    });
  });
}
