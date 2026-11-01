import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'config/app_theme.dart';
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
import 'screens/community_screen.dart';
import 'services/api_client.dart';
import 'services/auth_service.dart';
import 'services/community_service.dart';
import 'services/notification_service.dart';
import 'services/storage_service.dart';
import 'services/sync_service.dart';
import 'services/whatsapp_service.dart';


void main() async {
  WidgetsFlutterBinding.ensureInitialized();

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

  // Initialize push notification service safely
  await notificationService.initialize();

  runApp(DepartmentClubApp(
    navigatorKey: navigatorKey,
    authService: authService,
    syncService: syncService,
    whatsAppService: whatsAppService,
    communityService: communityService,
    notificationService: notificationService,
  ));
}

class DepartmentClubApp extends StatefulWidget {
  final GlobalKey<NavigatorState> navigatorKey;
  final AuthService authService;
  final SyncService syncService;
  final WhatsAppService whatsAppService;
  final CommunityService communityService;
  final NotificationService notificationService;

  const DepartmentClubApp({
    super.key,
    required this.navigatorKey,
    required this.authService,
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
  }

  @override
  void dispose() {
    widget.authService.removeListener(_onAuthChanged);
    super.dispose();
  }

  void _onAuthChanged() {
    setState(() {});
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

    if (widget.authService.isAdmin || widget.authService.isTeamLeader) {
      return _buildSelectEventScreen();
    }

    if (widget.authService.isDocumentationTeam) {
      return DocumentationPortalScreen(
        authService: widget.authService,
        syncService: widget.syncService,
        onLogout: _handleLogout,
      );
    }

    if (widget.authService.isMediaTeam) {
      return MediaDashboardScreen(
        authService: widget.authService,
        syncService: widget.syncService,
        onLogout: _handleLogout,
      );
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
