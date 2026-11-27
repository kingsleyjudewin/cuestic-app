import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'config/app_theme.dart';
import 'config/constants.dart';
import 'screens/assignment_detail_screen.dart';
import 'screens/assignment_message_screen.dart';
import 'screens/assignment_tracking_screen.dart';
import 'screens/create_assignment_screen.dart';
import 'screens/login_screen.dart';
import 'screens/member_directory_screen.dart';
import 'screens/select_event_screen.dart';
import 'screens/select_team_screen.dart';
import 'screens/volunteer_dashboard_screen.dart';
import 'screens/documentation_portal_screen.dart';
import 'screens/media_dashboard_screen.dart';
import 'screens/mc_dashboard_screen.dart';
import 'screens/community_screen.dart';
import 'screens/mandatory_password_change_screen.dart';
import 'screens/faculty_dashboard_screen.dart';
import 'screens/student_researcher_dashboard_screen.dart';
import 'services/api_client.dart';
import 'services/auth_service.dart';
import 'services/community_service.dart';
import 'services/notification_service.dart';
import 'services/storage_service.dart';
import 'services/sync_service.dart';
import 'services/whatsapp_service.dart';
import 'services/research_service.dart';
import 'widgets/visitor_mode_banner.dart';


void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Refuse to start a build whose compiled-in backend URL is unusable (e.g. a release build
  // that still points at 127.0.0.1), instead of failing on every request later.
  final configError = ApiConfig.configurationError;
  if (configError != null) {
    debugPrint('Invalid API configuration: $configError');
    runApp(ConfigurationErrorApp(message: configError));
    return;
  }

  // Initialize SQLite FFI on desktop platforms (Linux, macOS, Windows)
  if (!kIsWeb &&
      (defaultTargetPlatform == TargetPlatform.linux ||
       defaultTargetPlatform == TargetPlatform.windows ||
       defaultTargetPlatform == TargetPlatform.macOS)) {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  }

  final authService = AuthService();
  await authService.initialize();

  final storageService = StorageService();
  final apiClient = ApiClient(authService: authService);
  final syncService = SyncService(apiClient: apiClient, storageService: storageService);
  final whatsAppService = WhatsAppService(syncService: syncService);
  final communityService = CommunityService(apiClient: apiClient);

  final navigatorKey = GlobalKey<NavigatorState>();
  final notificationService = NotificationService(
    apiClient: apiClient,
    authService: authService,
    navigatorKey: navigatorKey,
  );

  final researchService = ResearchService(authService);

  // Initialize push notification service safely
  await notificationService.initialize();

  runApp(DepartmentClubApp(
    navigatorKey: navigatorKey,
    authService: authService,
    researchService: researchService,
    syncService: syncService,
    whatsAppService: whatsAppService,
    communityService: communityService,
    notificationService: notificationService,
  ));
}

class DepartmentClubApp extends StatefulWidget {
  final GlobalKey<NavigatorState> navigatorKey;
  final AuthService authService;
  final ResearchService researchService;
  final SyncService syncService;
  final WhatsAppService whatsAppService;
  final CommunityService communityService;
  final NotificationService notificationService;

  const DepartmentClubApp({
    super.key,
    required this.navigatorKey,
    required this.authService,
    required this.researchService,
    required this.syncService,
    required this.whatsAppService,
    required this.communityService,
    required this.notificationService,
  });

  @override
  State<DepartmentClubApp> createState() => _DepartmentClubAppState();
}

class _DepartmentClubAppState extends State<DepartmentClubApp> {
  @override
  void initState() {
    super.initState();
    widget.authService.addListener(_onAuthChanged);
    _wasPasswordChangeRequired = widget.authService.isAuthenticated && widget.authService.mustChangePassword;
  }

  @override
  void dispose() {
    widget.authService.removeListener(_onAuthChanged);
    super.dispose();
  }

  bool _wasPasswordChangeRequired = false;

  void _onAuthChanged() {
    final required = widget.authService.isAuthenticated && widget.authService.mustChangePassword;
    setState(() {});
    // The server reported (403 PASSWORD_CHANGE_REQUIRED) that a new password is needed while a
    // pushed screen is open: drop every route so the blocking password screen is all that remains.
    if (required && !_wasPasswordChangeRequired) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        widget.navigatorKey.currentState?.pushNamedAndRemoveUntil('/', (route) => false);
      });
    }
    _wasPasswordChangeRequired = required;
  }

  void _handleLogout() async {
    await widget.notificationService.onUserLoggedOut();
    await widget.authService.logout();
    widget.navigatorKey.currentState?.pushNamedAndRemoveUntil('/login', (route) => false);
  }

  Widget _buildSelectEventScreen() {
    return SelectEventScreen(
      syncService: widget.syncService,
      authService: widget.authService,
      onEventSelected: (event) {
        widget.navigatorKey.currentState?.push(
          MaterialPageRoute(
            builder: (context) => SelectTeamScreen(
              event: event,
              syncService: widget.syncService,
              onTeamSelected: (team) {
                widget.navigatorKey.currentState?.push(
                  MaterialPageRoute(
                    builder: (context) => MemberDirectoryScreen(
                      event: event,
                      team: team,
                      syncService: widget.syncService,
                      onAssignTask: (members) {
                        widget.navigatorKey.currentState?.push(
                          MaterialPageRoute(
                            builder: (context) => CreateAssignmentScreen(
                              event: event,
                              team: team,
                              selectedMembers: members,
                              syncService: widget.syncService,
                              onTaskCreated: (task) {
                                widget.navigatorKey.currentState?.push(
                                  MaterialPageRoute(
                                    builder: (context) => AssignmentMessageScreen(
                                      task: task,
                                      syncService: widget.syncService,
                                      whatsAppService: widget.whatsAppService,
                                      onFinish: () {
                                        widget.navigatorKey.currentState?.pushAndRemoveUntil(
                                          MaterialPageRoute(
                                            builder: (context) => AssignmentTrackingScreen(
                                              syncService: widget.syncService,
                                              onSelectAssignment: (assignmentId) {
                                                widget.navigatorKey.currentState?.push(
                                                  MaterialPageRoute(
                                                    builder: (context) => AssignmentDetailScreen(
                                                      assignmentId: assignmentId,
                                                      syncService: widget.syncService,
                                                      authService: widget.authService,
                                                      whatsAppService: widget.whatsAppService,
                                                    ),
                                                  ),
                                                );
                                              },
                                            ),
                                          ),
                                          (route) => route.isFirst,
                                        );
                                      },
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                );
              },
            ),
          ),
        );
      },
      onOpenAssignments: () {
        widget.navigatorKey.currentState?.push(
          MaterialPageRoute(
            builder: (context) => AssignmentTrackingScreen(
              syncService: widget.syncService,
              onSelectAssignment: (assignmentId) {
                widget.navigatorKey.currentState?.push(
                  MaterialPageRoute(
                    builder: (context) => AssignmentDetailScreen(
                      assignmentId: assignmentId,
                      syncService: widget.syncService,
                      authService: widget.authService,
                      whatsAppService: widget.whatsAppService,
                    ),
                  ),
                );
              },
            ),
          ),
        );
      },
      onLogout: _handleLogout,
    );
  }

  Widget _buildHomeScreen() {
    if (!widget.authService.isAuthenticated) {
      return LoginScreen(
        authService: widget.authService,
        notificationService: widget.notificationService,
        onLoginSuccess: () {
          setState(() {});
          widget.navigatorKey.currentState?.pushNamedAndRemoveUntil('/', (route) => false);
        },
      );
    }

    if (widget.authService.mustChangePassword) {
      return MandatoryPasswordChangeScreen(
        authService: widget.authService,
        onPasswordChanged: () {
          setState(() {});
          widget.navigatorKey.currentState?.pushNamedAndRemoveUntil('/', (route) => false);
        },
        onLogout: _handleLogout,
      );
    }

    if (widget.authService.isFacultyCoordinator) {
      return FacultyDashboardScreen(
        authService: widget.authService,
        researchService: widget.researchService,
        onLogout: _handleLogout,
      );
    }

    if (widget.authService.isStudentResearcher) {
      return StudentResearcherDashboardScreen(
        authService: widget.authService,
        researchService: widget.researchService,
        onLogout: _handleLogout,
      );
    }

    if (widget.authService.isDocumentationTeam) {
      return DocumentationPortalScreen(
        authService: widget.authService,
        syncService: widget.syncService,
        onLogout: _handleLogout,
        onSwitchToAdmin: widget.authService.isAdmin
            ? () => widget.navigatorKey.currentState?.pushNamedAndRemoveUntil('/', (r) => false)
            : null,
      );
    }

    if (widget.authService.isMediaTeam) {
      return MediaDashboardScreen(
        authService: widget.authService,
        syncService: widget.syncService,
        onLogout: _handleLogout,
      );
    }

    if (widget.authService.isMcTeam) {
      return McDashboardScreen(
        authService: widget.authService,
        syncService: widget.syncService,
        onLogout: _handleLogout,
        onSwitchToAdmin: (widget.authService.isAdmin || widget.authService.isTeamLeader)
            ? () => widget.navigatorKey.currentState?.pushNamedAndRemoveUntil('/', (r) => false)
            : null,
      );
    }

    if (widget.authService.isAdmin || widget.authService.isTeamLeader) {
      return _buildSelectEventScreen();
    }

    return VolunteerDashboardScreen(
      syncService: widget.syncService,
      authService: widget.authService,
      onLogout: _handleLogout,
    );
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Club Tasks',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      navigatorKey: widget.navigatorKey,
      builder: (context, child) => ListenableBuilder(
        listenable: widget.authService,
        builder: (context, _) => widget.authService.isAuthenticated && widget.authService.isVisitor
            ? Column(children: [
                const VisitorModeBanner(),
                // The banner already covers the status bar, so screens below must not pad for it again.
                Expanded(
                  child: MediaQuery.removePadding(
                    context: context,
                    removeTop: true,
                    child: child ?? const SizedBox.shrink(),
                  ),
                ),
              ])
            : (child ?? const SizedBox.shrink()),
      ),
      home: _buildHomeScreen(),
      onGenerateRoute: (settings) {
        if (settings.name == '/' || settings.name == '/home') {
          return MaterialPageRoute(builder: (context) => _buildHomeScreen());
        } else if (settings.name == '/login') {
          return MaterialPageRoute(
            builder: (context) => LoginScreen(
              authService: widget.authService,
              notificationService: widget.notificationService,
              onLoginSuccess: () {
                setState(() {});
                widget.navigatorKey.currentState?.pushNamedAndRemoveUntil('/', (route) => false);
              },
            ),
          );
        } else if (settings.name == '/volunteer_dashboard' || settings.name == '/my_tasks') {
          return MaterialPageRoute(
            builder: (context) => VolunteerDashboardScreen(
              syncService: widget.syncService,
              authService: widget.authService,
              onLogout: _handleLogout,
            ),
          );
        } else if (settings.name == '/documentation' || settings.name == '/documentation_portal') {
          return MaterialPageRoute(
            builder: (context) => DocumentationPortalScreen(
              authService: widget.authService,
              syncService: widget.syncService,
              onLogout: _handleLogout,
              onSwitchToAdmin: widget.authService.isAdmin
                  ? () => widget.navigatorKey.currentState?.pushNamedAndRemoveUntil('/', (r) => false)
                  : null,
            ),
          );
        } else if (settings.name == '/media' || settings.name == '/media_dashboard') {
          return MaterialPageRoute(
            builder: (context) => MediaDashboardScreen(
              authService: widget.authService,
              syncService: widget.syncService,
              onLogout: _handleLogout,
            ),
          );
        } else if (settings.name == '/mc' || settings.name == '/mc_dashboard') {
          return MaterialPageRoute(
            builder: (context) => McDashboardScreen(
              authService: widget.authService,
              syncService: widget.syncService,
              onLogout: _handleLogout,
              onSwitchToAdmin: widget.authService.isAdmin
                  ? () => widget.navigatorKey.currentState?.pushNamedAndRemoveUntil('/', (r) => false)
                  : null,
            ),
          );
        } else if (settings.name == '/faculty_dashboard' || settings.name == '/faculty') {
          return MaterialPageRoute(
            builder: (context) => FacultyDashboardScreen(
              authService: widget.authService,
              researchService: widget.researchService,
              onLogout: _handleLogout,
            ),
          );
        } else if (settings.name == '/student_researcher_dashboard' || settings.name == '/student_research') {
          return MaterialPageRoute(
            builder: (context) => StudentResearcherDashboardScreen(
              authService: widget.authService,
              researchService: widget.researchService,
              onLogout: _handleLogout,
            ),
          );
        } else if (settings.name == '/change_password') {
          return MaterialPageRoute(builder: (context) => _buildHomeScreen());
        } else if (settings.name == '/assignment_detail') {
          final id = settings.arguments as int;
          return MaterialPageRoute(
            builder: (context) => AssignmentDetailScreen(
              assignmentId: id,
              syncService: widget.syncService,
              authService: widget.authService,
              whatsAppService: widget.whatsAppService,
            ),
          );
        } else if (settings.name == '/community' || settings.name == '/communities') {
          return MaterialPageRoute(
            builder: (context) => CommunityScreen(
              communityService: widget.communityService,
              authService: widget.authService,
            ),
          );
        } else if (settings.name == '/assignments') {
          return MaterialPageRoute(
            builder: (context) => AssignmentTrackingScreen(
              syncService: widget.syncService,
              onSelectAssignment: (assignmentId) {
                widget.navigatorKey.currentState?.push(
                  MaterialPageRoute(
                    builder: (context) => AssignmentDetailScreen(
                      assignmentId: assignmentId,
                      syncService: widget.syncService,
                      authService: widget.authService,
                      whatsAppService: widget.whatsAppService,
                    ),
                  ),
                );
              },
            ),
          );
        }
        return null;
      },
    );
  }
}


/// Shown instead of the app when the build's API configuration is invalid.
class ConfigurationErrorApp extends StatelessWidget {
  final String message;
  const ConfigurationErrorApp({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: Scaffold(
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.cloud_off, size: 48, color: Color(0xFFDC2626)),
                  const SizedBox(height: 16),
                  const Text(
                    'App configuration error',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 8),
                  Text(message, textAlign: TextAlign.center),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
