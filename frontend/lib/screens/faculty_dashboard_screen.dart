import 'package:flutter/material.dart';
import '../models/research.dart';
import '../services/auth_service.dart';
import '../services/research_service.dart';

class FacultyDashboardScreen extends StatefulWidget {
  final AuthService authService;
  final ResearchService researchService;
  final VoidCallback? onLogout;

  const FacultyDashboardScreen({
    super.key,
    required this.authService,
    required this.researchService,
    this.onLogout,
  });

  @override
  State<FacultyDashboardScreen> createState() => _FacultyDashboardScreenState();
}

class _FacultyDashboardScreenState extends State<FacultyDashboardScreen> {
  int _selectedTabIndex = 0;
  bool _isLoading = true;
  String? _error;
    

  List<ResearchTeam> _teams = [];
  List<ResearchStudentProfile> _directory = [];
  List<ResearchProject> _projects = [];
  List<ResearchMeeting> _meetings = [];
  List<ResearchNotification> _notifications = [];

  // Search & Filter state for Directory
  final _searchController = TextEditingController();
  String? _selectedSemesterFilter;

  // Selected item for detail view / modals
  ResearchTask? _selectedTaskForReview;
  Map<String, dynamic>? _selectedTaskThread;

  // Profile Settings Password Change
  final _profCurrentPassCtrl = TextEditingController();
  final _profNewPassCtrl = TextEditingController();
  final _profConfirmPassCtrl = TextEditingController();
  bool _profObscureCurrent = true;
  bool _profObscureNew = true;
  bool _profObscureConfirm = true;
  bool _profIsChangingPass = false;
  String? _profPassError;

  @override
  void initState() {
    super.initState();
    _loadAllData();
  }

  @override
  void dispose() {
    _searchController.dispose();
    _profCurrentPassCtrl.dispose();
    _profNewPassCtrl.dispose();
    _profConfirmPassCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadAllData({bool forceRefresh = false, bool silent = false}) async {
    if (!silent) {
      setState(() {
        _isLoading = true;
        _error = null;
      });
    }

    try {
      final service = widget.researchService;
      final results = await Future.wait([
        service.getTeams(forceRefresh: forceRefresh),
        service.getStudentDirectory(forceRefresh: forceRefresh),
        service.getProjects(forceRefresh: forceRefresh),
        service.getMeetings(forceRefresh: forceRefresh),
        service.getNotifications(),
      ]);

      if (mounted) {
        setState(() {
          _teams = results[0] as List<ResearchTeam>;
          _directory = results[1] as List<ResearchStudentProfile>;
          _projects = results[2] as List<ResearchProject>;
          _meetings = results[3] as List<ResearchMeeting>;
          _notifications = results[4] as List<ResearchNotification>;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString().replaceAll('Exception:', '').trim();
          _isLoading = false;
        });
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Top Header with Profile Info & Fallback Avatar
  // ---------------------------------------------------------------------------
  Widget _buildHeader(BuildContext context) {
    final auth = widget.authService;
    final user = auth.currentUser;
    final facProfile = user?['faculty_profile'] as Map<String, dynamic>?;
    final fullName = facProfile?['full_name'] ?? user?['full_name'] ?? 'Faculty Coordinator';
    final dept = facProfile?['department'] ?? 'Electronics and Communication Engineering';
    final specialization = facProfile?['specialization'] ?? '';
    final imageUrl = facProfile?['profile_image_url'] as String?;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(bottom: BorderSide(color: Color(0xFFE5E7EB))),
      ),
      child: Row(
        children: [
          // Avatar with graceful network fallback
          CircleAvatar(
            radius: 22,
            backgroundColor: const Color(0xFF111827),
            child: ClipOval(
              child: imageUrl != null && imageUrl.isNotEmpty
                  ? Image.network(
                      imageUrl,
                      width: 44,
                      height: 44,
                      fit: BoxFit.cover,
                      errorBuilder: (context, error, stackTrace) {
                        return Center(
                          child: Text(
                            fullName.isNotEmpty ? fullName[0].toUpperCase() : 'F',
                            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 16),
                          ),
                        );
                      },
                    )
                  : Center(
                      child: Text(
                        fullName.isNotEmpty ? fullName[0].toUpperCase() : 'F',
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 16),
                      ),
                    ),
            ),
          ),
          const SizedBox(width: 14),

          // Titles
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Text(
                      fullName,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        letterSpacing: -0.3,
                        color: Color(0xFF111827),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF3F4F6),
                        borderRadius: BorderRadius.circular(4),
                        border: Border.all(color: const Color(0xFFE5E7EB)),
                      ),
                      child: const Text(
                        'FACULTY COORDINATOR',
                        style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: Color(0xFF374151)),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  specialization.isNotEmpty ? '$dept • $specialization' : dept,
                  style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),

          // Notification Bell
          IconButton(
            icon: Stack(
              clipBehavior: Clip.none,
              children: [
                const Icon(Icons.notifications_none_rounded, color: Color(0xFF374151), size: 22),
                if (_notifications.any((n) => !n.isRead))
                  Positioned(
                    top: -2,
                    right: -2,
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: const BoxDecoration(
                        color: Color(0xFFDC2626),
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
              ],
            ),
            onPressed: _showNotificationsDialog,
            tooltip: 'Notifications',
          ),
          const SizedBox(width: 8),

          // Refresh Button
          IconButton(
            icon: const Icon(Icons.refresh_rounded, color: Color(0xFF374151), size: 20),
            onPressed: () => _loadAllData(forceRefresh: true),
            tooltip: 'Refresh Data',
          ),
          const SizedBox(width: 8),

          // Change Password Button
          OutlinedButton.icon(
            icon: const Icon(Icons.lock_outline_rounded, size: 14, color: Color(0xFF111827)),
            label: const Text('Change Password', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF111827))),
            style: OutlinedButton.styleFrom(
              side: const BorderSide(color: Color(0xFFE5E7EB)),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () => _showChangePasswordDialog(context),
          ),
          const SizedBox(width: 8),

          // Logout Button
          IconButton(
            icon: const Icon(Icons.logout_rounded, color: Color(0xFF6B7280), size: 20),
            onPressed: () => _confirmLogout(context),
            tooltip: 'Sign Out',
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Segmented Navigation Tab Bar
  // ---------------------------------------------------------------------------
  Widget _buildTabBar() {
    final tabs = [
      {'label': 'Overview', 'icon': Icons.dashboard_outlined},
      {'label': 'My Research Teams', 'icon': Icons.groups_outlined},
      {'label': 'My Projects', 'icon': Icons.folder_outlined},
      {'label': 'Student Directory', 'icon': Icons.people_alt_outlined},
      {'label': 'Tasks & Milestones', 'icon': Icons.check_circle_outline_rounded},
      {'label': 'Progress Reviews', 'icon': Icons.rate_review_outlined},
      {'label': 'Meeting Scheduler', 'icon': Icons.event_outlined},
      {'label': 'Profile Settings', 'icon': Icons.person_outline_rounded},
    ];

    return Container(
      height: 48,
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(bottom: BorderSide(color: Color(0xFFE5E7EB))),
      ),
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: tabs.length,
        itemBuilder: (context, index) {
          final isSelected = _selectedTabIndex == index;
          final tab = tabs[index];
          return InkWell(
            onTap: () => setState(() => _selectedTabIndex = index),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                border: Border(
                  bottom: BorderSide(
                    color: isSelected ? const Color(0xFF111827) : Colors.transparent,
                    width: 2,
                  ),
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    tab['icon'] as IconData,
                    size: 16,
                    color: isSelected ? const Color(0xFF111827) : const Color(0xFF6B7280),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    tab['label'] as String,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                      color: isSelected ? const Color(0xFF111827) : const Color(0xFF6B7280),
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Main Body Dispatcher
  // ---------------------------------------------------------------------------
  @override
  Widget build(BuildContext context) {
        if (_error != null) {
      return Scaffold(
        backgroundColor: const Color(0xFFFAFAFA),
        body: Column(
          children: [
            _buildHeader(context),
            Expanded(
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Text('Error: $_error', style: const TextStyle(color: Color(0xFFDC2626))),
                ),
              ),
            ),
          ],
        ),
      );
    }

    if (_isLoading) {
      return Scaffold(
        backgroundColor: const Color(0xFFFAFAFA),
        body: Column(
          children: [
            _buildHeader(context),
            const Expanded(
              child: Center(
                child: CircularProgressIndicator(color: Color(0xFF111827), strokeWidth: 2),
              ),
            ),
          ],
        ),
      );
    }

    Widget content;
    switch (_selectedTabIndex) {
      case 0:
        content = _buildOverviewTab();
        break;
      case 1:
        content = _buildTeamsTab();
        break;
      case 2:
        content = _buildProjectsTab();
        break;
      case 3:
        content = _buildDirectoryTab();
        break;
      case 4:
        content = _buildTasksTab();
        break;
      case 5:
        content = _buildReviewsTab();
        break;
      case 6:
        content = _buildMeetingsTab();
        break;
      case 7:
        content = _buildProfileTab();
        break;
      default:
        content = _buildOverviewTab();
    }

    return Scaffold(
      backgroundColor: const Color(0xFFFAFAFA),
      body: Column(
        children: [
          _buildHeader(context),
          _buildTabBar(),
          Expanded(child: content),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // TAB 0: OVERVIEW
  // ---------------------------------------------------------------------------
  Widget _buildOverviewTab() {
    final activeTeamsCount = _teams.length;
    final activeProjectsCount = _projects.length;
    final enrolledStudentsCount = _directory.length;
    final scheduledMeetingsCount = _meetings.length;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Stat Metrics Row
          Row(
            children: [
              _buildStatCard('Research Teams', activeTeamsCount.toString(), Icons.groups_outlined, () {
                setState(() => _selectedTabIndex = 1);
              }),
              const SizedBox(width: 16),
              _buildStatCard('Active Projects', activeProjectsCount.toString(), Icons.folder_outlined, () {
                setState(() => _selectedTabIndex = 2);
              }),
              const SizedBox(width: 16),
              _buildStatCard('Total Students', enrolledStudentsCount.toString(), Icons.people_alt_outlined, () {
                setState(() => _selectedTabIndex = 3);
              }),
              const SizedBox(width: 16),
              _buildStatCard('Upcoming Meetings', scheduledMeetingsCount.toString(), Icons.event_outlined, () {
                setState(() => _selectedTabIndex = 6);
              }),
            ],
          ),
          const SizedBox(height: 28),

          // Quick Action Bar
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFFE5E7EB)),
            ),
            child: Row(
              children: [
                const Text(
                  'Quick Actions:',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
                ),
                const SizedBox(width: 16),
                _buildActionChip('+ Create Research Team', () => _showCreateTeamDialog(context)),
                const SizedBox(width: 10),
                _buildActionChip('+ Add Student', () => _showAddStudentDirectDialog(context)),
                const SizedBox(width: 10),
                _buildActionChip('+ Create Project', () => _showCreateProjectDialog(context)),
                const SizedBox(width: 10),
                _buildActionChip('+ Schedule Meeting', () => _showScheduleMeetingDialog(context)),
              ],
            ),
          ),
          const SizedBox(height: 28),

          // Two-column section: Recent Teams and Upcoming Meetings
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Left: Research Teams Summary
              Expanded(
                flex: 3,
                child: Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFE5E7EB)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'My Research Teams',
                            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
                          ),
                          TextButton(
                            onPressed: () => setState(() => _selectedTabIndex = 1),
                            child: const Text('View All', style: TextStyle(fontSize: 12, color: Color(0xFF111827))),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      if (_teams.isEmpty)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 24),
                          child: Center(
                            child: Text(
                              'No research teams created yet. Click "+ Create Research Team" to begin.',
                              style: TextStyle(fontSize: 13, color: Color(0xFF9CA3AF)),
                            ),
                          ),
                        )
                      else
                        ListView.separated(
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          itemCount: _teams.take(4).length,
                          separatorBuilder: (_, __) => const Divider(height: 20, color: Color(0xFFF3F4F6)),
                          itemBuilder: (context, i) {
                            final t = _teams[i];
                            return Row(
                              children: [
                                Container(
                                  width: 36,
                                  height: 36,
                                  decoration: BoxDecoration(
                                    color: const Color(0xFFF9FAFB),
                                    borderRadius: BorderRadius.circular(8),
                                    border: Border.all(color: const Color(0xFFE5E7EB)),
                                  ),
                                  child: const Icon(Icons.groups_outlined, size: 18, color: Color(0xFF374151)),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        t.name,
                                        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF111827)),
                                      ),
                                      Text(
                                        'Domain: ${t.domain} • ${t.memberCount} Students • ${t.projectCount} Projects',
                                        style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                                      ),
                                    ],
                                  ),
                                ),
                                OutlinedButton(
                                  onPressed: () {
                                    setState(() {
                                      
                                      _selectedTabIndex = 1;
                                    });
                                  },
                                  style: OutlinedButton.styleFrom(
                                    side: const BorderSide(color: Color(0xFFD1D5DB)),
                                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                  ),
                                  child: const Text('Manage', style: TextStyle(fontSize: 12, color: Color(0xFF111827))),
                                ),
                              ],
                            );
                          },
                        ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 20),

              // Right: Upcoming Meetings
              Expanded(
                flex: 2,
                child: Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFE5E7EB)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'Upcoming Meetings',
                            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
                          ),
                          TextButton(
                            onPressed: () => setState(() => _selectedTabIndex = 6),
                            child: const Text('View All', style: TextStyle(fontSize: 12, color: Color(0xFF111827))),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      if (_meetings.isEmpty)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 24),
                          child: Center(
                            child: Text(
                              'No meetings scheduled.',
                              style: TextStyle(fontSize: 13, color: Color(0xFF9CA3AF)),
                            ),
                          ),
                        )
                      else
                        ListView.separated(
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          itemCount: _meetings.take(3).length,
                          separatorBuilder: (_, __) => const Divider(height: 16, color: Color(0xFFF3F4F6)),
                          itemBuilder: (context, i) {
                            final m = _meetings[i];
                            return Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  m.title,
                                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF111827)),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  m.scheduledAt != null ? m.scheduledAt!.substring(0, 16).replaceAll('T', ' ') : 'TBD',
                                  style: const TextStyle(fontSize: 11, color: Color(0xFF6B7280)),
                                ),
                                if (m.locationOrLink != null && m.locationOrLink!.isNotEmpty)
                                  Text(
                                    m.locationOrLink!,
                                    style: const TextStyle(fontSize: 11, color: Color(0xFF2563EB)),
                                  ),
                              ],
                            );
                          },
                        ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatCard(String title, String count, IconData icon, VoidCallback onTap) {
    return Expanded(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: const Color(0xFFE5E7EB)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    title,
                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF6B7280)),
                  ),
                  Icon(icon, size: 18, color: const Color(0xFF9CA3AF)),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                count,
                style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w700, color: Color(0xFF111827), letterSpacing: -0.5),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildActionChip(String label, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: const Color(0xFF111827),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(
          label,
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Colors.white),
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // TAB 1: MY RESEARCH TEAMS
  // ---------------------------------------------------------------------------
  Widget _buildTeamsTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'My Research Teams',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, letterSpacing: -0.5, color: Color(0xFF111827)),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'Manage research groups, enrolled students, and associated projects.',
                    style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                  ),
                ],
              ),
              ElevatedButton.icon(
                onPressed: () => _showCreateTeamDialog(context),
                icon: const Icon(Icons.add_rounded, size: 18),
                label: const Text('+ Create Research Team'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF111827),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  elevation: 0,
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),

          if (_teams.isEmpty)
            Container(
              padding: const EdgeInsets.symmetric(vertical: 60),
              alignment: Alignment.center,
              child: Column(
                children: [
                  const Icon(Icons.groups_outlined, size: 48, color: Color(0xFF9CA3AF)),
                  const SizedBox(height: 12),
                  const Text('No research teams found', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 4),
                  const Text('Create your first team to start adding student researchers.', style: TextStyle(fontSize: 13, color: Color(0xFF6B7280))),
                  const SizedBox(height: 16),
                  ElevatedButton(
                    onPressed: () => _showCreateTeamDialog(context),
                    style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF111827), foregroundColor: Colors.white),
                    child: const Text('+ Create Research Team'),
                  ),
                ],
              ),
            )
          else
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                maxCrossAxisExtent: 460,
                mainAxisExtent: 220,
                crossAxisSpacing: 16,
                mainAxisSpacing: 16,
              ),
              itemCount: _teams.length,
              itemBuilder: (context, i) {
                final t = _teams[i];
                return Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFE5E7EB)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF3F4F6),
                              borderRadius: BorderRadius.circular(4),
                              border: Border.all(color: const Color(0xFFE5E7EB)),
                            ),
                            child: Text(
                              t.domain.toUpperCase(),
                              style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: Color(0xFF374151)),
                            ),
                          ),
                          PopupMenuButton<String>(
                            icon: const Icon(Icons.more_vert, size: 18, color: Color(0xFF6B7280)),
                            onSelected: (val) {
                              if (val == 'delete') _deleteTeam(t.id);
                            },
                            itemBuilder: (ctx) => [
                              const PopupMenuItem(
                                value: 'delete',
                                child: Text('Delete Team', style: TextStyle(color: Color(0xFFDC2626), fontSize: 13)),
                              ),
                            ],
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        t.name,
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        t.description ?? 'No description provided.',
                        style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const Spacer(),
                      const Divider(height: 16, color: Color(0xFFF3F4F6)),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            '${t.memberCount} Students • ${t.projectCount} Projects',
                            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: Color(0xFF374151)),
                          ),
                          Row(
                            children: [
                              OutlinedButton.icon(
                                onPressed: () => _showAddStudentModal(context, t),
                                icon: const Icon(Icons.person_add_alt_1_outlined, size: 14),
                                label: const Text('+ Student', style: TextStyle(fontSize: 11)),
                                style: OutlinedButton.styleFrom(
                                  side: const BorderSide(color: Color(0xFFD1D5DB)),
                                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                ),
                              ),
                              const SizedBox(width: 8),
                              ElevatedButton(
                                onPressed: () => _openTeamDetailsModal(t),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: const Color(0xFF111827),
                                  foregroundColor: Colors.white,
                                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                                  elevation: 0,
                                ),
                                child: const Text('Open Team', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600)),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ],
                  ),
                );
              },
            ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // TAB 2: MY PROJECTS
  // ---------------------------------------------------------------------------
  Widget _buildProjectsTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Research Projects',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, letterSpacing: -0.5, color: Color(0xFF111827)),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'Track problem statements, research milestones, deliverables, and student assignments.',
                    style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                  ),
                ],
              ),
              ElevatedButton.icon(
                onPressed: () => _showCreateProjectDialog(context),
                icon: const Icon(Icons.add_rounded, size: 18),
                label: const Text('+ Create Project'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF111827),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  elevation: 0,
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),

          if (_projects.isEmpty)
            Container(
              padding: const EdgeInsets.symmetric(vertical: 60),
              alignment: Alignment.center,
              child: Column(
                children: [
                  const Icon(Icons.folder_outlined, size: 48, color: Color(0xFF9CA3AF)),
                  const SizedBox(height: 12),
                  const Text('No projects created yet', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 4),
                  const Text('Create projects under your research teams to assign milestones.', style: TextStyle(fontSize: 13, color: Color(0xFF6B7280))),
                  const SizedBox(height: 16),
                  ElevatedButton(
                    onPressed: () => _showCreateProjectDialog(context),
                    style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF111827), foregroundColor: Colors.white),
                    child: const Text('+ Create Project'),
                  ),
                ],
              ),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _projects.length,
              separatorBuilder: (_, __) => const SizedBox(height: 16),
              itemBuilder: (context, i) {
                final p = _projects[i];
                return Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFE5E7EB)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Row(
                              children: [
                                Text(
                                  p.title,
                                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
                                ),
                                const SizedBox(width: 10),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: p.status == 'completed' ? const Color(0xFFECFDF5) : const Color(0xFFEFF6FF),
                                    borderRadius: BorderRadius.circular(4),
                                    border: Border.all(color: p.status == 'completed' ? const Color(0xFFA7F3D0) : const Color(0xFFBFDBFE)),
                                  ),
                                  child: Text(
                                    p.status.toUpperCase().replaceAll('_', ' '),
                                    style: TextStyle(
                                      fontSize: 10,
                                      fontWeight: FontWeight.w700,
                                      color: p.status == 'completed' ? const Color(0xFF065F46) : const Color(0xFF1E40AF),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          OutlinedButton(
                            onPressed: () => _showCreateMilestoneDialog(context, p.id),
                            style: OutlinedButton.styleFrom(
                              side: const BorderSide(color: Color(0xFFD1D5DB)),
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            ),
                            child: const Text('+ Add Milestone', style: TextStyle(fontSize: 11, color: Color(0xFF111827))),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(
                        'Team: ${p.teamName ?? "Research Team"} • Target Date: ${p.expectedCompletionDate != null ? p.expectedCompletionDate!.substring(0, 10) : "TBD"}',
                        style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                      ),
                      if (p.researchProblem != null && p.researchProblem!.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Text(
                          'Problem: ${p.researchProblem}',
                          style: const TextStyle(fontSize: 13, color: Color(0xFF374151)),
                        ),
                      ],
                      const SizedBox(height: 12),
                      // Milestones mini list
                      if (p.milestones.isNotEmpty) ...[
                        const Text('Milestones:', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: Color(0xFF374151))),
                        const SizedBox(height: 6),
                        Wrap(
                          spacing: 8,
                          runSpacing: 6,
                          children: p.milestones.map((m) {
                            return Container(
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                              decoration: BoxDecoration(
                                color: const Color(0xFFF9FAFB),
                                borderRadius: BorderRadius.circular(6),
                                border: Border.all(color: const Color(0xFFE5E7EB)),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(
                                    m.status == 'completed' ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                                    size: 12,
                                    color: m.status == 'completed' ? const Color(0xFF059669) : const Color(0xFF6B7280),
                                  ),
                                  const SizedBox(width: 6),
                                  Text(m.title, style: const TextStyle(fontSize: 12, color: Color(0xFF111827))),
                                ],
                              ),
                            );
                          }).toList(),
                        ),
                      ],
                    ],
                  ),
                );
              },
            ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // TAB 3: CENTRALIZED STUDENT DIRECTORY (DEDUPLICATED)
  // ---------------------------------------------------------------------------
  Widget _buildDirectoryTab() {
    var filtered = _directory;
    final query = _searchController.text.toLowerCase().trim();
    if (query.isNotEmpty) {
      filtered = filtered.where((s) {
        return s.fullName.toLowerCase().contains(query) ||
            s.registrationNumber.toLowerCase().contains(query) ||
            s.email.toLowerCase().contains(query);
      }).toList();
    }
    if (_selectedSemesterFilter != null && _selectedSemesterFilter!.isNotEmpty) {
      filtered = filtered.where((s) => s.semester == _selectedSemesterFilter).toList();
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Centralized Student Directory',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, letterSpacing: -0.5, color: Color(0xFF111827)),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'All students across your research teams (${_directory.length} enrolled, deduplicated).',
                    style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                  ),
                ],
              ),
              ElevatedButton.icon(
                onPressed: () => _showAddStudentDirectDialog(context),
                icon: const Icon(Icons.person_add_alt_1_rounded, size: 18),
                label: const Text('+ Add Student'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF111827),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  elevation: 0,
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Search and Filters Bar
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchController,
                  onChanged: (_) => setState(() {}),
                  decoration: InputDecoration(
                    hintText: 'Search by student name, registration number, or email...',
                    hintStyle: const TextStyle(fontSize: 13, color: Color(0xFF9CA3AF)),
                    prefixIcon: const Icon(Icons.search_rounded, size: 18, color: Color(0xFF6B7280)),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: Color(0xFFE5E7EB))),
                    enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: Color(0xFFE5E7EB))),
                    focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: Color(0xFF111827))),
                    filled: true,
                    fillColor: Colors.white,
                  ),
                ),
              ),
              const SizedBox(width: 14),
              // Semester Dropdown Filter
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFFE5E7EB)),
                ),
                child: DropdownButton<String>(
                  value: _selectedSemesterFilter,
                  hint: const Text('All Semesters', style: TextStyle(fontSize: 13, color: Color(0xFF374151))),
                  underline: const SizedBox(),
                  icon: const Icon(Icons.keyboard_arrow_down_rounded, size: 18, color: Color(0xFF6B7280)),
                  items: [
                    const DropdownMenuItem(value: null, child: Text('All Semesters', style: TextStyle(fontSize: 13))),
                    const DropdownMenuItem(value: 'Semester 5', child: Text('Semester 5', style: TextStyle(fontSize: 13))),
                    const DropdownMenuItem(value: 'Semester 6', child: Text('Semester 6', style: TextStyle(fontSize: 13))),
                    const DropdownMenuItem(value: 'Semester 7', child: Text('Semester 7', style: TextStyle(fontSize: 13))),
                    const DropdownMenuItem(value: 'Semester 8', child: Text('Semester 8', style: TextStyle(fontSize: 13))),
                  ],
                  onChanged: (val) => setState(() => _selectedSemesterFilter = val),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),

          if (filtered.isEmpty)
            Container(
              padding: const EdgeInsets.symmetric(vertical: 60),
              alignment: Alignment.center,
              child: const Text('No students match the selected filter.', style: TextStyle(fontSize: 14, color: Color(0xFF6B7280))),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: filtered.length,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (context, i) {
                final s = filtered[i];
                final teamList = s.teams ?? [];

                return Container(
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: const Color(0xFFE5E7EB)),
                  ),
                  child: Row(
                    children: [
                      CircleAvatar(
                        radius: 20,
                        backgroundColor: const Color(0xFF111827),
                        child: Text(
                          s.fullName.isNotEmpty ? s.fullName[0].toUpperCase() : 'S',
                          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 14),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Text(
                                  s.fullName,
                                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
                                ),
                                const SizedBox(width: 8),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFFF3F4F6),
                                    borderRadius: BorderRadius.circular(4),
                                    border: Border.all(color: const Color(0xFFE5E7EB)),
                                  ),
                                  child: Text(
                                    s.registrationNumber,
                                    style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: Color(0xFF374151)),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 2),
                            Text(
                              '${s.email} • ${s.programme} • ${s.semester}',
                              style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                            ),
                            const SizedBox(height: 6),
                            Wrap(
                              spacing: 6,
                              children: teamList.map((t) {
                                final tm = Map<String, dynamic>.from(t as Map);
                                return Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFFEFF6FF),
                                    borderRadius: BorderRadius.circular(4),
                                    border: Border.all(color: const Color(0xFFBFDBFE)),
                                  ),
                                  child: Text(
                                    tm['name'] ?? 'Team',
                                    style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: Color(0xFF1E40AF)),
                                  ),
                                );
                              }).toList(),
                            ),
                          ],
                        ),
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text(
                            '${s.tasksCount} Tasks Assigned',
                            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF111827)),
                          ),
                          Text(
                            '${s.completedTasksCount} Completed',
                            style: const TextStyle(fontSize: 11, color: Color(0xFF059669)),
                          ),
                        ],
                      ),
                      const SizedBox(width: 12),
                      IconButton(
                        icon: const Icon(Icons.key_rounded, size: 18, color: Color(0xFF4B5563)),
                        tooltip: 'Set / Reset Student Password',
                        onPressed: () => _showSetStudentPasswordDialog(context, s.id, s.fullName),
                      ),
                    ],
                  ),
                );
              },
            ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // TAB 4: TASKS & MILESTONES MANAGEMENT
  // ---------------------------------------------------------------------------
  Widget _buildTasksTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Task & Milestone Tracking',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, letterSpacing: -0.5, color: Color(0xFF111827)),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'Review deliverables, assign students, and track research milestones.',
                    style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 24),

          if (_projects.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 40),
              child: Center(child: Text('Create a project first to define milestones and tasks.')),
            )
          else
            ..._projects.map((proj) {
              return Container(
                margin: const EdgeInsets.only(bottom: 24),
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFE5E7EB)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Project: ${proj.title}',
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
                        ),
                        OutlinedButton.icon(
                          onPressed: () => _showCreateMilestoneDialog(context, proj.id),
                          icon: const Icon(Icons.add_rounded, size: 14),
                          label: const Text('+ Milestone', style: TextStyle(fontSize: 11)),
                          style: OutlinedButton.styleFrom(
                            side: const BorderSide(color: Color(0xFFD1D5DB)),
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 14),

                    if (proj.milestones.isEmpty)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 12),
                        child: Text('No milestones created under this project yet.', style: TextStyle(fontSize: 12, color: Color(0xFF9CA3AF))),
                      )
                    else
                      ...proj.milestones.map((ms) {
                        return Container(
                          margin: const EdgeInsets.only(bottom: 12),
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF9FAFB),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: const Color(0xFFE5E7EB)),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    'Milestone: ${ms.title}',
                                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF111827)),
                                  ),
                                  TextButton.icon(
                                    onPressed: () => _showCreateTaskDialog(context, ms.id),
                                    icon: const Icon(Icons.add, size: 14, color: Color(0xFF111827)),
                                    label: const Text('+ Task', style: TextStyle(fontSize: 12, color: Color(0xFF111827))),
                                  ),
                                ],
                              ),
                              if (ms.targetCriteria != null && ms.targetCriteria!.isNotEmpty)
                                Text('Criteria: ${ms.targetCriteria}', style: const TextStyle(fontSize: 11, color: Color(0xFF6B7280))),
                              const SizedBox(height: 8),

                              // Tasks under milestone
                              if (ms.tasks.isEmpty)
                                const Text('No tasks created yet.', style: TextStyle(fontSize: 11, color: Color(0xFF9CA3AF)))
                              else
                                ...ms.tasks.map((tsk) {
                                  return Container(
                                    margin: const EdgeInsets.only(top: 6),
                                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                    decoration: BoxDecoration(
                                      color: Colors.white,
                                      borderRadius: BorderRadius.circular(6),
                                      border: Border.all(color: const Color(0xFFE5E7EB)),
                                    ),
                                    child: Row(
                                      children: [
                                        Icon(
                                          tsk.status == 'approved'
                                              ? Icons.check_circle_rounded
                                              : (tsk.status == 'revision_requested' ? Icons.error_outline_rounded : Icons.pending_outlined),
                                          size: 16,
                                          color: tsk.status == 'approved'
                                              ? const Color(0xFF059669)
                                              : (tsk.status == 'revision_requested' ? const Color(0xFFDC2626) : const Color(0xFFD97706)),
                                        ),
                                        const SizedBox(width: 8),
                                        Expanded(
                                          child: Text(
                                            tsk.title,
                                            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: Color(0xFF111827)),
                                          ),
                                        ),
                                        Text(
                                          '${tsk.progressPercentage}%',
                                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
                                        ),
                                        const SizedBox(width: 12),
                                        TextButton(
                                          onPressed: () => _openReviewModal(tsk),
                                          child: const Text('Review', style: TextStyle(fontSize: 12, color: Color(0xFF2563EB))),
                                        ),
                                      ],
                                    ),
                                  );
                                }),
                            ],
                          ),
                        );
                      }),
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // TAB 5: PROGRESS REVIEWS & TWO-WAY FEEDBACK THREAD
  // ---------------------------------------------------------------------------
  Widget _buildReviewsTab() {
    // Find tasks that have submissions or require review
    final allTasks = <ResearchTask>[];
    for (final p in _projects) {
      for (final m in p.milestones) {
        allTasks.addAll(m.tasks);
      }
    }

    return Row(
      children: [
        // Left sidebar: list of tasks
        Container(
          width: 320,
          decoration: const BoxDecoration(
            color: Colors.white,
            border: Border(right: BorderSide(color: Color(0xFFE5E7EB))),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text('Review Submissions', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Color(0xFF111827))),
              ),
              const Divider(height: 1, color: Color(0xFFE5E7EB)),
              Expanded(
                child: allTasks.isEmpty
                    ? const Center(child: Text('No tasks available for review.', style: TextStyle(fontSize: 12, color: Color(0xFF9CA3AF))))
                    : ListView.separated(
                        itemCount: allTasks.length,
                        separatorBuilder: (_, __) => const Divider(height: 1, color: Color(0xFFF3F4F6)),
                        itemBuilder: (context, i) {
                          final t = allTasks[i];
                          final isSelected = _selectedTaskForReview?.id == t.id;
                          return ListTile(
                            selected: isSelected,
                            selectedTileColor: const Color(0xFFF3F4F6),
                            title: Text(t.title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                            subtitle: Text('Status: ${t.status.replaceAll('_', ' ')} • ${t.progressPercentage}%', style: const TextStyle(fontSize: 11)),
                            onTap: () => _selectTaskForReview(t),
                          );
                        },
                      ),
              ),
            ],
          ),
        ),

        // Right pane: continuous conversation thread
        Expanded(
          child: _selectedTaskForReview == null
              ? const Center(
                  child: Text('Select a research task from the left sidebar to view progress updates and leave feedback.', style: TextStyle(color: Color(0xFF6B7280), fontSize: 13)),
                )
              : _buildFeedbackThreadView(),
        ),
      ],
    );
  }

  Widget _buildFeedbackThreadView() {
    final thread = _selectedTaskThread;
    final messages = thread?['messages'] as List<dynamic>? ?? [];

    return Container(
      color: const Color(0xFFFAFAFA),
      child: Column(
        children: [
          // Header
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
            decoration: const BoxDecoration(
              color: Colors.white,
              border: Border(bottom: BorderSide(color: Color(0xFFE5E7EB))),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _selectedTaskForReview!.title,
                      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
                    ),
                    Text(
                      'Status: ${_selectedTaskForReview!.status.replaceAll('_', ' ')} • Progress: ${_selectedTaskForReview!.progressPercentage}%',
                      style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                    ),
                  ],
                ),
                Row(
                  children: [
                    OutlinedButton(
                      onPressed: () => _sendReviewAction('request_revision'),
                      style: OutlinedButton.styleFrom(
                        side: const BorderSide(color: Color(0xFFDC2626)),
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      ),
                      child: const Text('Request Revision', style: TextStyle(color: Color(0xFFDC2626), fontSize: 12, fontWeight: FontWeight.w600)),
                    ),
                    const SizedBox(width: 8),
                    ElevatedButton(
                      onPressed: () => _sendReviewAction('approve'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF059669),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                        elevation: 0,
                      ),
                      child: const Text('Approve Work', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                    ),
                  ],
                ),
              ],
            ),
          ),

          // Message Thread List
          Expanded(
            child: messages.isEmpty
                ? const Center(child: Text('No feedback messages or submissions recorded yet.', style: TextStyle(fontSize: 12, color: Color(0xFF9CA3AF))))
                : ListView.builder(
                    padding: const EdgeInsets.all(20),
                    itemCount: messages.length,
                    itemBuilder: (context, i) {
                      final m = Map<String, dynamic>.from(messages[i] as Map);
                      final isFaculty = m['sender_role'] == 'faculty_coordinator';
                      final senderName = m['sender_name'] ?? (isFaculty ? 'Faculty Coordinator' : 'Student Researcher');
                      final text = m['message_text'] ?? '';
                      final action = m['action_decision'];
                      final created = m['created_at'] != null ? m['created_at'].toString().substring(0, 16).replaceAll('T', ' ') : '';

                      return Container(
                        margin: const EdgeInsets.only(bottom: 14),
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: isFaculty ? const Color(0xFFF9FAFB) : Colors.white,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: isFaculty ? const Color(0xFFE5E7EB) : const Color(0xFFD1D5DB)),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Row(
                                  children: [
                                    Text(senderName, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF111827))),
                                    const SizedBox(width: 6),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                                      decoration: BoxDecoration(
                                        color: isFaculty ? const Color(0xFF111827) : const Color(0xFF2563EB),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: Text(
                                        isFaculty ? 'FACULTY' : 'STUDENT',
                                        style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w700, color: Colors.white),
                                      ),
                                    ),
                                  ],
                                ),
                                Text(created, style: const TextStyle(fontSize: 11, color: Color(0xFF9CA3AF))),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Text(text, style: const TextStyle(fontSize: 13, color: Color(0xFF374151), height: 1.4)),
                            if (action != null && action.isNotEmpty) ...[
                              const SizedBox(height: 8),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                decoration: BoxDecoration(
                                  color: action == 'approve' ? const Color(0xFFECFDF5) : const Color(0xFFFEF2F2),
                                  borderRadius: BorderRadius.circular(4),
                                  border: Border.all(color: action == 'approve' ? const Color(0xFFA7F3D0) : const Color(0xFFFCA5A5)),
                                ),
                                child: Text(
                                  action == 'approve' ? 'APPROVED' : 'REVISION REQUESTED',
                                  style: TextStyle(
                                    fontSize: 10,
                                    fontWeight: FontWeight.w700,
                                    color: action == 'approve' ? const Color(0xFF065F46) : const Color(0xFFDC2626),
                                  ),
                                ),
                              ),
                            ],
                          ],
                        ),
                      );
                    },
                  ),
          ),

          // Message input
          Container(
            padding: const EdgeInsets.all(12),
            color: Colors.white,
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _feedbackInputController,
                    decoration: InputDecoration(
                      hintText: 'Type instructions or feedback to the student researcher...',
                      hintStyle: const TextStyle(fontSize: 13, color: Color(0xFF9CA3AF)),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: Color(0xFFE5E7EB))),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  icon: const Icon(Icons.send_rounded, color: Color(0xFF111827)),
                  onPressed: () => _sendReviewAction('comment'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  final _feedbackInputController = TextEditingController();

  Future<void> _selectTaskForReview(ResearchTask task) async {
    setState(() {
      _selectedTaskForReview = task;
    });
    try {
      final service = widget.researchService;
      final thread = await service.getFeedbackThread(task.id);
      if (mounted) {
        setState(() {
          _selectedTaskThread = thread;
        });
      }
    } catch (_) {}
  }

  Future<void> _sendReviewAction(String action) async {
    if (_selectedTaskForReview == null) return;
    final text = _feedbackInputController.text.trim();
    if (text.isEmpty && action == 'comment') return;

    try {
      final service = widget.researchService;
      await service.addFeedbackMessage(
        taskId: _selectedTaskForReview!.id,
        message: text.isNotEmpty ? text : (action == 'approve' ? 'Work approved by faculty.' : 'Revisions requested by faculty.'),
        action: action,
      );
      _feedbackInputController.clear();
      await _selectTaskForReview(_selectedTaskForReview!);
      await _loadAllData(forceRefresh: true, silent: true);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  void _openReviewModal(ResearchTask task) {
    setState(() {
      _selectedTabIndex = 5;
    });
    _selectTaskForReview(task);
  }

  // ---------------------------------------------------------------------------
  // TAB 6: MEETING SCHEDULER
  // ---------------------------------------------------------------------------
  Widget _buildMeetingsTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Research Meeting Scheduler',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, letterSpacing: -0.5, color: Color(0xFF111827)),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'Schedule reviews, record agenda, and track student attendance.',
                    style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                  ),
                ],
              ),
              ElevatedButton.icon(
                onPressed: () => _showScheduleMeetingDialog(context),
                icon: const Icon(Icons.add_rounded, size: 18),
                label: const Text('+ Schedule Meeting'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF111827),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  elevation: 0,
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),

          if (_meetings.isEmpty)
            Container(
              padding: const EdgeInsets.symmetric(vertical: 60),
              alignment: Alignment.center,
              child: const Text('No meetings scheduled yet.', style: TextStyle(fontSize: 14, color: Color(0xFF6B7280))),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _meetings.length,
              separatorBuilder: (_, __) => const SizedBox(height: 14),
              itemBuilder: (context, i) {
                final m = _meetings[i];
                return Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFE5E7EB)),
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(
                          color: const Color(0xFFF9FAFB),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: const Color(0xFFE5E7EB)),
                        ),
                        child: const Icon(Icons.calendar_month_outlined, size: 20, color: Color(0xFF111827)),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              m.title,
                              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              'Time: ${m.scheduledAt != null ? m.scheduledAt!.substring(0, 16).replaceAll("T", " ") : "TBD"} (${m.durationMinutes} mins)',
                              style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                            ),
                            if (m.locationOrLink != null && m.locationOrLink!.isNotEmpty)
                              Text('Location / Link: ${m.locationOrLink}', style: const TextStyle(fontSize: 12, color: Color(0xFF2563EB))),
                            if (m.agenda != null && m.agenda!.isNotEmpty)
                              Text('Agenda: ${m.agenda}', style: const TextStyle(fontSize: 12, color: Color(0xFF374151))),
                          ],
                        ),
                      ),
                      OutlinedButton(
                        onPressed: () => _showRecordAttendanceModal(context, m),
                        style: OutlinedButton.styleFrom(
                          side: const BorderSide(color: Color(0xFFD1D5DB)),
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        ),
                        child: const Text('Attendance & Notes', style: TextStyle(fontSize: 12, color: Color(0xFF111827))),
                      ),
                    ],
                  ),
                );
              },
            ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // TAB 7: PROFILE SETTINGS
  // ---------------------------------------------------------------------------
  Widget _buildProfileTab() {
    final auth = widget.authService;
    final user = auth.currentUser;
    final fac = user?['faculty_profile'] as Map<String, dynamic>?;

    final specCtrl = TextEditingController(text: fac?['specialization'] ?? '');
    final bioCtrl = TextEditingController(text: fac?['bio'] ?? '');
    final interestsCtrl = TextEditingController(text: fac?['research_interests'] ?? '');
    final phoneCtrl = TextEditingController(text: fac?['phone_number'] ?? '');
    final emailCtrl = TextEditingController(text: user?['email'] ?? '');

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 600),
          child: Column(
            children: [
              // Card 1: Faculty Profile Settings
              Container(
                padding: const EdgeInsets.all(28),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFE5E7EB)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Faculty Profile Settings', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Color(0xFF111827))),
                    const SizedBox(height: 4),
                    const Text('Update your research specialization, bio, and contact information.', style: TextStyle(fontSize: 13, color: Color(0xFF6B7280))),
                    const SizedBox(height: 24),

                    const Text('Specialization', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 6),
                    TextField(controller: specCtrl, decoration: const InputDecoration(border: OutlineInputBorder())),
                    const SizedBox(height: 16),

                    const Text('Research Interests', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 6),
                    TextField(controller: interestsCtrl, decoration: const InputDecoration(border: OutlineInputBorder())),
                    const SizedBox(height: 16),

                    const Text('Bio / Summary', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 6),
                    TextField(controller: bioCtrl, maxLines: 3, decoration: const InputDecoration(border: OutlineInputBorder())),
                    const SizedBox(height: 16),

                    const Text('Phone Number', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 6),
                    TextField(controller: phoneCtrl, decoration: const InputDecoration(border: OutlineInputBorder())),
                    const SizedBox(height: 16),

                    const Text('University Email', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 6),
                    TextField(controller: emailCtrl, decoration: const InputDecoration(border: OutlineInputBorder())),
                    const SizedBox(height: 24),

                    ElevatedButton(
                      onPressed: () async {
                        try {
                          final service = widget.researchService;
                          await service.updateFacultyProfile({
                            'specialization': specCtrl.text.trim(),
                            'bio': bioCtrl.text.trim(),
                            'research_interests': interestsCtrl.text.trim(),
                            'phone_number': phoneCtrl.text.trim(),
                            'email': emailCtrl.text.trim(),
                          });
                          if (mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Profile updated successfully.')));
                            _loadAllData(forceRefresh: true, silent: true);
                          }
                        } catch (e) {
                          if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                        }
                      },
                      style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF111827), foregroundColor: Colors.white),
                      child: const Text('Save Profile Changes'),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 24),

              // Card 2: Change Account Password
              Container(
                padding: const EdgeInsets.all(28),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFE5E7EB)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF3F4F6),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Icon(Icons.lock_outline_rounded, size: 20, color: Color(0xFF111827)),
                        ),
                        const SizedBox(width: 12),
                        const Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Change Account Password', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Color(0xFF111827))),
                              SizedBox(height: 2),
                              Text('Change your personal coordinator password anytime according to your will.', style: TextStyle(fontSize: 13, color: Color(0xFF6B7280))),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),

                    if (_profPassError != null) ...[
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFEF2F2),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: const Color(0xFFFCA5A5)),
                        ),
                        child: Text(_profPassError!, style: const TextStyle(fontSize: 12, color: Color(0xFFB91C1C), fontWeight: FontWeight.w500)),
                      ),
                      const SizedBox(height: 16),
                    ],

                    const Text('Current Password', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _profCurrentPassCtrl,
                      obscureText: _profObscureCurrent,
                      decoration: InputDecoration(
                        border: const OutlineInputBorder(),
                        suffixIcon: IconButton(
                          icon: Icon(_profObscureCurrent ? Icons.visibility_outlined : Icons.visibility_off_outlined, size: 18),
                          onPressed: () => setState(() => _profObscureCurrent = !_profObscureCurrent),
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),

                    const Text('New Password (min 6 characters)', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _profNewPassCtrl,
                      obscureText: _profObscureNew,
                      decoration: InputDecoration(
                        border: const OutlineInputBorder(),
                        suffixIcon: IconButton(
                          icon: Icon(_profObscureNew ? Icons.visibility_outlined : Icons.visibility_off_outlined, size: 18),
                          onPressed: () => setState(() => _profObscureNew = !_profObscureNew),
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),

                    const Text('Confirm New Password', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _profConfirmPassCtrl,
                      obscureText: _profObscureConfirm,
                      decoration: InputDecoration(
                        border: const OutlineInputBorder(),
                        suffixIcon: IconButton(
                          icon: Icon(_profObscureConfirm ? Icons.visibility_outlined : Icons.visibility_off_outlined, size: 18),
                          onPressed: () => setState(() => _profObscureConfirm = !_profObscureConfirm),
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),

                    ElevatedButton(
                      onPressed: _profIsChangingPass
                          ? null
                          : () async {
                              final curr = _profCurrentPassCtrl.text.trim();
                              final nxt = _profNewPassCtrl.text.trim();
                              final conf = _profConfirmPassCtrl.text.trim();

                              if (curr.isEmpty || nxt.isEmpty) {
                                setState(() => _profPassError = 'Please fill in current and new password.');
                                return;
                              }
                              if (nxt.length < 6) {
                                setState(() => _profPassError = 'New password must be at least 6 characters.');
                                return;
                              }
                              if (nxt != conf) {
                                setState(() => _profPassError = 'New password and confirmation do not match.');
                                return;
                              }
                              if (curr == nxt) {
                                setState(() => _profPassError = 'New password must be different from current password.');
                                return;
                              }

                              setState(() {
                                _profIsChangingPass = true;
                                _profPassError = null;
                              });

                              try {
                                await widget.researchService.changePassword(
                                  currentPassword: curr,
                                  newPassword: nxt,
                                );
                                _profCurrentPassCtrl.clear();
                                _profNewPassCtrl.clear();
                                _profConfirmPassCtrl.clear();
                                if (mounted) {
                                  setState(() {
                                    _profIsChangingPass = false;
                                  });
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(
                                      content: Text('Password changed successfully!'),
                                      backgroundColor: Color(0xFF111827),
                                    ),
                                  );
                                }
                              } catch (e) {
                                if (mounted) {
                                  setState(() {
                                    _profIsChangingPass = false;
                                    _profPassError = e.toString().replaceAll('Exception:', '').trim();
                                  });
                                }
                              }
                            },
                      style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF111827), foregroundColor: Colors.white),
                      child: _profIsChangingPass
                          ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Text('Update Password'),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Dialogs & Modals
  // ---------------------------------------------------------------------------

  void _showChangePasswordDialog(BuildContext context) {
    final currentPassCtrl = TextEditingController();
    final newPassCtrl = TextEditingController();
    final confirmPassCtrl = TextEditingController();
    bool obscureCurrent = true;
    bool obscureNew = true;
    bool obscureConfirm = true;
    bool isSubmitting = false;
    String? dialogError;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (dialogCtx, setDialogState) => AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          titlePadding: const EdgeInsets.fromLTRB(24, 24, 24, 8),
          contentPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
          actionsPadding: const EdgeInsets.fromLTRB(24, 16, 24, 20),
          title: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFFF3F4F6),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.lock_outline_rounded, size: 20, color: Color(0xFF111827)),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Text('Change Password', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 17, color: Color(0xFF111827))),
              ),
            ],
          ),
          content: SizedBox(
            width: 420,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Change your account login password at any time according to your will.',
                  style: TextStyle(fontSize: 13, color: Color(0xFF6B7280)),
                ),
                const SizedBox(height: 16),
                if (dialogError != null) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: const Color(0xFFFEF2F2),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: const Color(0xFFFCA5A5)),
                    ),
                    child: Text(dialogError!, style: const TextStyle(fontSize: 12, color: Color(0xFFB91C1C), fontWeight: FontWeight.w500)),
                  ),
                  const SizedBox(height: 12),
                ],
                TextField(
                  controller: currentPassCtrl,
                  obscureText: obscureCurrent,
                  decoration: InputDecoration(
                    labelText: 'Current Password *',
                    border: const OutlineInputBorder(),
                    suffixIcon: IconButton(
                      icon: Icon(obscureCurrent ? Icons.visibility_outlined : Icons.visibility_off_outlined, size: 18),
                      onPressed: () => setDialogState(() => obscureCurrent = !obscureCurrent),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: newPassCtrl,
                  obscureText: obscureNew,
                  decoration: InputDecoration(
                    labelText: 'New Password * (min 6 characters)',
                    border: const OutlineInputBorder(),
                    suffixIcon: IconButton(
                      icon: Icon(obscureNew ? Icons.visibility_outlined : Icons.visibility_off_outlined, size: 18),
                      onPressed: () => setDialogState(() => obscureNew = !obscureNew),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: confirmPassCtrl,
                  obscureText: obscureConfirm,
                  decoration: InputDecoration(
                    labelText: 'Confirm New Password *',
                    border: const OutlineInputBorder(),
                    suffixIcon: IconButton(
                      icon: Icon(obscureConfirm ? Icons.visibility_outlined : Icons.visibility_off_outlined, size: 18),
                      onPressed: () => setDialogState(() => obscureConfirm = !obscureConfirm),
                    ),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: isSubmitting ? null : () => Navigator.pop(ctx),
              child: const Text('Cancel', style: TextStyle(color: Color(0xFF6B7280))),
            ),
            ElevatedButton(
              onPressed: isSubmitting
                  ? null
                  : () async {
                      final curr = currentPassCtrl.text.trim();
                      final nxt = newPassCtrl.text.trim();
                      final conf = confirmPassCtrl.text.trim();

                      if (curr.isEmpty || nxt.isEmpty) {
                        setDialogState(() => dialogError = 'Please fill in all required password fields.');
                        return;
                      }
                      if (nxt.length < 6) {
                        setDialogState(() => dialogError = 'New password must be at least 6 characters.');
                        return;
                      }
                      if (nxt != conf) {
                        setDialogState(() => dialogError = 'New password and confirmation do not match.');
                        return;
                      }
                      if (curr == nxt) {
                        setDialogState(() => dialogError = 'New password must be different from current password.');
                        return;
                      }

                      final messenger = ScaffoldMessenger.of(context);
                      final nav = Navigator.of(ctx);

                      setDialogState(() {
                        isSubmitting = true;
                        dialogError = null;
                      });

                      try {
                        await widget.researchService.changePassword(
                          currentPassword: curr,
                          newPassword: nxt,
                        );
                        if (!mounted) return;
                        nav.pop();
                        messenger.showSnackBar(
                          const SnackBar(
                            content: Text('Password updated successfully!'),
                            backgroundColor: Color(0xFF111827),
                          ),
                        );
                      } catch (e) {
                        setDialogState(() {
                          isSubmitting = false;
                          dialogError = e.toString().replaceAll('Exception:', '').trim();
                        });
                      }
                    },
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF111827),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              child: isSubmitting
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Text('Update Password'),
            ),
          ],
        ),
      ),
    );
  }

  void _showSetStudentPasswordDialog(BuildContext context, int studentId, String studentName) {
    final newPassCtrl = TextEditingController();
    bool obscure = false;
    bool isSubmitting = false;
    String? dialogError;

    // Suggest a default
    final randTail = (1000 + (DateTime.now().millisecondsSinceEpoch % 9000)).toString();
    newPassCtrl.text = 'ResStudent2026!$randTail';

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (dialogCtx, setDialogState) => AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          titlePadding: const EdgeInsets.fromLTRB(24, 24, 24, 8),
          contentPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
          actionsPadding: const EdgeInsets.fromLTRB(24, 16, 24, 20),
          title: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFFF3F4F6),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.key_rounded, size: 20, color: Color(0xFF111827)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text('Set Password: $studentName', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16, color: Color(0xFF111827))),
              ),
            ],
          ),
          content: SizedBox(
            width: 400,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Assign a new login password for this student. The student can use this password to sign in and can change it later in their portal.',
                  style: TextStyle(fontSize: 13, color: Color(0xFF6B7280)),
                ),
                const SizedBox(height: 16),
                if (dialogError != null) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: const Color(0xFFFEF2F2),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: const Color(0xFFFCA5A5)),
                    ),
                    child: Text(dialogError!, style: const TextStyle(fontSize: 12, color: Color(0xFFB91C1C), fontWeight: FontWeight.w500)),
                  ),
                  const SizedBox(height: 12),
                ],
                TextField(
                  controller: newPassCtrl,
                  obscureText: obscure,
                  decoration: InputDecoration(
                    labelText: 'New Student Password *',
                    border: const OutlineInputBorder(),
                    suffixIcon: IconButton(
                      icon: Icon(obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined, size: 18),
                      onPressed: () => setDialogState(() => obscure = !obscure),
                    ),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: isSubmitting ? null : () => Navigator.pop(ctx),
              child: const Text('Cancel', style: TextStyle(color: Color(0xFF6B7280))),
            ),
            ElevatedButton(
              onPressed: isSubmitting
                  ? null
                  : () async {
                      final nxt = newPassCtrl.text.trim();
                      if (nxt.length < 6) {
                        setDialogState(() => dialogError = 'Password must be at least 6 characters.');
                        return;
                      }
                      final nav = Navigator.of(ctx);

                      setDialogState(() {
                        isSubmitting = true;
                        dialogError = null;
                      });

                      try {
                        final res = await widget.researchService.setStudentPassword(
                          studentId: studentId,
                          newPassword: nxt,
                        );
                        if (!mounted) return;
                        nav.pop();
                        _showStudentCredentialsDialog(
                          context,
                          studentName: studentName,
                          username: res['username']?.toString() ?? 'Student Account',
                          password: nxt,
                        );
                      } catch (e) {
                        setDialogState(() {
                          isSubmitting = false;
                          dialogError = e.toString().replaceAll('Exception:', '').trim();
                        });
                      }
                    },
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF111827),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              child: isSubmitting
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Text('Save Password'),
            ),
          ],
        ),
      ),
    );
  }

  void _showStudentCredentialsDialog(
    BuildContext context, {
    required String studentName,
    required String username,
    required String password,
  }) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        titlePadding: const EdgeInsets.fromLTRB(24, 24, 24, 8),
        contentPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
        actionsPadding: const EdgeInsets.fromLTRB(24, 12, 24, 20),
        title: Row(
          children: const [
            Icon(Icons.check_circle_rounded, color: Color(0xFF059669), size: 24),
            SizedBox(width: 10),
            Text('Student Account Ready', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 17, color: Color(0xFF111827))),
          ],
        ),
        content: SizedBox(
          width: 420,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Please share these login credentials with $studentName. They can sign in directly and can change their password at any time inside the student portal.',
                style: const TextStyle(fontSize: 13, color: Color(0xFF4B5563)),
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: const Color(0xFFF9FAFB),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFFE5E7EB)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('Username:', style: TextStyle(fontSize: 12, color: Color(0xFF6B7280), fontWeight: FontWeight.w600)),
                        SelectableText(username, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF111827))),
                      ],
                    ),
                    const Divider(height: 16),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('Assigned Password:', style: TextStyle(fontSize: 12, color: Color(0xFF6B7280), fontWeight: FontWeight.w600)),
                        SelectableText(password, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF059669))),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        actions: [
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx),
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF111827), foregroundColor: Colors.white),
            child: const Text('Done'),
          ),
        ],
      ),
    );
  }

  void _showCreateTeamDialog(BuildContext context) {
    final nameCtrl = TextEditingController();
    final domainCtrl = TextEditingController();
    final descCtrl = TextEditingController();
    final objCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Create Research Team', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
        content: SizedBox(
          width: 440,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Research Team Name *')),
              const SizedBox(height: 10),
              TextField(controller: domainCtrl, decoration: const InputDecoration(labelText: 'Research Domain * (e.g. Deep Learning)')),
              const SizedBox(height: 10),
              TextField(controller: descCtrl, decoration: const InputDecoration(labelText: 'Description')),
              const SizedBox(height: 10),
              TextField(controller: objCtrl, decoration: const InputDecoration(labelText: 'Objectives')),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              if (nameCtrl.text.trim().isEmpty || domainCtrl.text.trim().isEmpty) return;
              try {
                final service = widget.researchService;
                await service.createTeam(
                  name: nameCtrl.text.trim(),
                  domain: domainCtrl.text.trim(),
                  description: descCtrl.text.trim(),
                  objectives: objCtrl.text.trim(),
                );
                Navigator.pop(ctx);
                _loadAllData(forceRefresh: true, silent: true);
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF111827), foregroundColor: Colors.white),
            child: const Text('Create Team'),
          ),
        ],
      ),
    );
  }

  void _showAddStudentModal(BuildContext context, ResearchTeam team) {
    final nameCtrl = TextEditingController();
    final regCtrl = TextEditingController();
    final emailCtrl = TextEditingController();
    final passCtrl = TextEditingController();
    final semCtrl = TextEditingController(text: 'Semester 5');
    final phoneCtrl = TextEditingController();
    bool obscurePass = false;
    bool isSubmitting = false;
    String? dialogError;

    // Set initial suggested password
    final randTail = (1000 + (DateTime.now().millisecondsSinceEpoch % 9000)).toString();
    passCtrl.text = 'ResStudent2026!$randTail';

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (dialogCtx, setDialogState) => AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          titlePadding: const EdgeInsets.fromLTRB(24, 24, 24, 8),
          contentPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
          actionsPadding: const EdgeInsets.fromLTRB(24, 12, 24, 20),
          title: Text('Add Student to ${team.name}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          content: SizedBox(
            width: 440,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (dialogError != null) ...[
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFEF2F2),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: const Color(0xFFFCA5A5)),
                      ),
                      child: Text(dialogError!, style: const TextStyle(fontSize: 12, color: Color(0xFFB91C1C), fontWeight: FontWeight.w500)),
                    ),
                    const SizedBox(height: 12),
                  ],
                  TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Student Full Name *', border: OutlineInputBorder())),
                  const SizedBox(height: 10),
                  TextField(controller: regCtrl, decoration: const InputDecoration(labelText: 'Registration Number *', border: OutlineInputBorder())),
                  const SizedBox(height: 10),
                  TextField(controller: emailCtrl, decoration: const InputDecoration(labelText: 'University Email Address *', border: OutlineInputBorder())),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: passCtrl,
                          obscureText: obscurePass,
                          decoration: InputDecoration(
                            labelText: 'Student Login Password *',
                            helperText: 'Password assigned to the student (min 6 chars)',
                            border: const OutlineInputBorder(),
                            suffixIcon: IconButton(
                              icon: Icon(obscurePass ? Icons.visibility_outlined : Icons.visibility_off_outlined, size: 18),
                              onPressed: () => setDialogState(() => obscurePass = !obscurePass),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton(
                        onPressed: () {
                          final newTail = (1000 + (DateTime.now().millisecondsSinceEpoch % 9000)).toString();
                          setDialogState(() {
                            passCtrl.text = 'ResStudent2026!$newTail';
                          });
                        },
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 14),
                          side: const BorderSide(color: Color(0xFFE5E7EB)),
                        ),
                        child: const Text('Generate', style: TextStyle(fontSize: 11, color: Color(0xFF111827))),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  TextField(controller: semCtrl, decoration: const InputDecoration(labelText: 'Semester (e.g. Semester 5)', border: OutlineInputBorder())),
                  const SizedBox(height: 10),
                  TextField(controller: phoneCtrl, decoration: const InputDecoration(labelText: 'Optional Phone Number', border: OutlineInputBorder())),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: isSubmitting ? null : () => Navigator.pop(ctx),
              child: const Text('Cancel', style: TextStyle(color: Color(0xFF6B7280))),
            ),
            ElevatedButton(
              onPressed: isSubmitting
                  ? null
                  : () async {
                      final name = nameCtrl.text.trim();
                      final reg = regCtrl.text.trim();
                      final email = emailCtrl.text.trim();
                      final pass = passCtrl.text.trim();

                      if (name.isEmpty || reg.isEmpty || email.isEmpty) {
                        setDialogState(() => dialogError = 'Name, registration number, and email are required.');
                        return;
                      }
                      if (pass.isNotEmpty && pass.length < 6) {
                        setDialogState(() => dialogError = 'Password must be at least 6 characters.');
                        return;
                      }

                      setDialogState(() {
                        isSubmitting = true;
                        dialogError = null;
                      });

                      try {
                        final service = widget.researchService;
                        final res = await service.addStudentToTeam(
                          teamId: team.id,
                          fullName: name,
                          registrationNumber: reg,
                          email: email,
                          password: pass.isNotEmpty ? pass : null,
                          semester: semCtrl.text.trim(),
                          phoneNumber: phoneCtrl.text.trim(),
                        );
                        Navigator.pop(ctx);
                        final assignedPass = res['password'] ?? res['temporary_password'] ?? pass;
                        final assignedUsername = res['username'] ?? 'res_${reg.toLowerCase()}';
                        if (mounted) {
                          _showStudentCredentialsDialog(
                            context,
                            studentName: name,
                            username: assignedUsername,
                            password: assignedPass,
                          );
                        }
                        _loadAllData(forceRefresh: true, silent: true);
                      } catch (e) {
                        setDialogState(() {
                          isSubmitting = false;
                          dialogError = e.toString().replaceAll('Exception:', '').trim();
                        });
                      }
                    },
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF111827), foregroundColor: Colors.white),
              child: isSubmitting
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Text('Add Student'),
            ),
          ],
        ),
      ),
    );
  }

  void _showAddStudentDirectDialog(BuildContext context) {
    if (_teams.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please create a research team first.')),
      );
      return;
    }
    _showAddStudentModal(context, _teams.first);
  }

  void _openTeamDetailsModal(ResearchTeam team) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(team.name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 18)),
        content: SizedBox(
          width: 500,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Domain: ${team.domain}', style: const TextStyle(fontWeight: FontWeight.w600)),
              if (team.objectives != null) Text('Objectives: ${team.objectives}'),
              const Divider(height: 24),
              const Text('Enrolled Students:', style: TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              if (team.members.isEmpty)
                const Text('No students currently enrolled in this team.')
              else
                ...team.members.map((m) {
                  final st = m['student'] as Map<String, dynamic>?;
                  final name = st?['full_name'] ?? 'Student';
                  final reg = st?['registration_number'] ?? '';
                  final sid = m['student_id'] as int;
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('$name ($reg)'),
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            IconButton(
                              icon: const Icon(Icons.key_rounded, color: Color(0xFF4B5563), size: 18),
                              tooltip: 'Set/Reset Password',
                              onPressed: () {
                                _showSetStudentPasswordDialog(context, sid, name);
                              },
                            ),
                            IconButton(
                              icon: const Icon(Icons.remove_circle_outline, color: Color(0xFFDC2626), size: 18),
                              tooltip: 'Remove from Team',
                              onPressed: () async {
                                await widget.researchService.removeStudentFromTeam(team.id, sid);
                                Navigator.pop(ctx);
                                _loadAllData(forceRefresh: true);
                              },
                            ),
                          ],
                        ),
                      ],
                    ),
                  );
                }),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close')),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              _showAddStudentModal(context, team);
            },
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF111827), foregroundColor: Colors.white),
            child: const Text('+ Add Student'),
          ),
        ],
      ),
    );
  }

  void _showCreateProjectDialog(BuildContext context) {
    if (_teams.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Please create a research team first.')));
      return;
    }

    final titleCtrl = TextEditingController();
    final problemCtrl = TextEditingController();
    final objCtrl = TextEditingController();
    int selectedTeamId = _teams.first.id;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('Create Research Project', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          content: SizedBox(
            width: 440,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<int>(
                  value: selectedTeamId,
                  decoration: const InputDecoration(labelText: 'Research Team *'),
                  items: _teams.map((t) => DropdownMenuItem(value: t.id, child: Text(t.name))).toList(),
                  onChanged: (v) => setDialogState(() => selectedTeamId = v!),
                ),
                const SizedBox(height: 10),
                TextField(controller: titleCtrl, decoration: const InputDecoration(labelText: 'Project Title *')),
                const SizedBox(height: 10),
                TextField(controller: problemCtrl, decoration: const InputDecoration(labelText: 'Research Problem')),
                const SizedBox(height: 10),
                TextField(controller: objCtrl, decoration: const InputDecoration(labelText: 'Objectives')),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
            ElevatedButton(
              onPressed: () async {
                if (titleCtrl.text.trim().isEmpty) return;
                try {
                  final service = widget.researchService;
                  await service.createProject(
                    teamId: selectedTeamId,
                    title: titleCtrl.text.trim(),
                    researchProblem: problemCtrl.text.trim(),
                    objectives: objCtrl.text.trim(),
                  );
                  Navigator.pop(ctx);
                  _loadAllData(forceRefresh: true);
                } catch (e) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
                }
              },
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF111827), foregroundColor: Colors.white),
              child: const Text('Create Project'),
            ),
          ],
        ),
      ),
    );
  }

  void _showCreateMilestoneDialog(BuildContext context, int projectId) {
    final titleCtrl = TextEditingController();
    final descCtrl = TextEditingController();
    final targetCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Add Milestone', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
        content: SizedBox(
          width: 400,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(controller: titleCtrl, decoration: const InputDecoration(labelText: 'Milestone Title *')),
              const SizedBox(height: 10),
              TextField(controller: targetCtrl, decoration: const InputDecoration(labelText: 'Measurable Criteria (e.g. 20 papers)')),
              const SizedBox(height: 10),
              TextField(controller: descCtrl, decoration: const InputDecoration(labelText: 'Description')),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              if (titleCtrl.text.trim().isEmpty) return;
              try {
                final service = widget.researchService;
                await service.createMilestone(
                  projectId: projectId,
                  title: titleCtrl.text.trim(),
                  targetCriteria: targetCtrl.text.trim(),
                  description: descCtrl.text.trim(),
                );
                Navigator.pop(ctx);
                _loadAllData(forceRefresh: true, silent: true);
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF111827), foregroundColor: Colors.white),
            child: const Text('Save Milestone'),
          ),
        ],
      ),
    );
  }

  void _showCreateTaskDialog(BuildContext context, int milestoneId) {
    final titleCtrl = TextEditingController();
    final instrCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Add Task', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
        content: SizedBox(
          width: 400,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(controller: titleCtrl, decoration: const InputDecoration(labelText: 'Task Title *')),
              const SizedBox(height: 10),
              TextField(controller: instrCtrl, decoration: const InputDecoration(labelText: 'Instructions')),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              if (titleCtrl.text.trim().isEmpty) return;
              try {
                final service = widget.researchService;
                await service.createTask(
                  milestoneId: milestoneId,
                  title: titleCtrl.text.trim(),
                  instructions: instrCtrl.text.trim(),
                );
                Navigator.pop(ctx);
                _loadAllData(forceRefresh: true, silent: true);
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF111827), foregroundColor: Colors.white),
            child: const Text('Save Task'),
          ),
        ],
      ),
    );
  }

  void _showScheduleMeetingDialog(BuildContext context) {
    final titleCtrl = TextEditingController();
    final agendaCtrl = TextEditingController();
    final locCtrl = TextEditingController(text: 'Online / Google Meet');
    DateTime selectedDate = DateTime.now().add(const Duration(days: 1));

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Schedule Research Meeting', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
        content: SizedBox(
          width: 440,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(controller: titleCtrl, decoration: const InputDecoration(labelText: 'Meeting Title *')),
              const SizedBox(height: 10),
              TextField(controller: agendaCtrl, decoration: const InputDecoration(labelText: 'Agenda')),
              const SizedBox(height: 10),
              TextField(controller: locCtrl, decoration: const InputDecoration(labelText: 'Location or Google Meet Link')),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              if (titleCtrl.text.trim().isEmpty) return;
              try {
                final service = widget.researchService;
                await service.scheduleMeeting(
                  title: titleCtrl.text.trim(),
                  agenda: agendaCtrl.text.trim(),
                  locationOrLink: locCtrl.text.trim(),
                  scheduledAt: selectedDate.toIso8601String(),
                );
                Navigator.pop(ctx);
                _loadAllData(forceRefresh: true, silent: true);
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF111827), foregroundColor: Colors.white),
            child: const Text('Schedule'),
          ),
        ],
      ),
    );
  }

  void _showRecordAttendanceModal(BuildContext context, ResearchMeeting meeting) {
    final notesCtrl = TextEditingController(text: meeting.meetingNotes ?? '');
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Attendance & Notes: ${meeting.title}'),
        content: SizedBox(
          width: 440,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: notesCtrl,
                maxLines: 4,
                decoration: const InputDecoration(labelText: 'Meeting Minutes / Discussion Notes', border: OutlineInputBorder()),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              try {
                final service = widget.researchService;
                await service.recordAttendance(meetingId: meeting.id, attendance: [], notes: notesCtrl.text.trim());
                Navigator.pop(ctx);
                _loadAllData(forceRefresh: true, silent: true);
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF111827), foregroundColor: Colors.white),
            child: const Text('Save Minutes'),
          ),
        ],
      ),
    );
  }

  void _deleteTeam(int teamId) async {
    try {
      final service = widget.researchService;
      await service.deleteTeam(teamId);
      _loadAllData(forceRefresh: true, silent: true);
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  void _showNotificationsDialog() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Notifications', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
        content: SizedBox(
          width: 400,
          child: _notifications.isEmpty
              ? const Padding(padding: EdgeInsets.all(20), child: Text('No notifications.'))
              : ListView.separated(
                  shrinkWrap: true,
                  itemCount: _notifications.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (c, i) {
                    final n = _notifications[i];
                    return ListTile(
                      title: Text(n.title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                      subtitle: Text(n.body, style: const TextStyle(fontSize: 12)),
                    );
                  },
                ),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close'))],
      ),
    );
  }

  void _confirmLogout(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Sign Out'),
        content: const Text('Are you sure you want to sign out of the Faculty Coordinator portal?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              widget.onLogout != null ? widget.onLogout!() : widget.authService.logout();
            },
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFDC2626), foregroundColor: Colors.white),
            child: const Text('Sign Out'),
          ),
        ],
      ),
    );
  }
}
