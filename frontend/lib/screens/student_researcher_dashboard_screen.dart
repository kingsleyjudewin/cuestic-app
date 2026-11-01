import 'package:flutter/material.dart';
import '../models/research.dart';
import '../services/auth_service.dart';
import '../services/research_service.dart';

class StudentResearcherDashboardScreen extends StatefulWidget {
  final AuthService authService;
  final ResearchService researchService;
  final VoidCallback? onLogout;

  const StudentResearcherDashboardScreen({
    super.key,
    required this.authService,
    required this.researchService,
    this.onLogout,
  });

  @override
  State<StudentResearcherDashboardScreen> createState() => _StudentResearcherDashboardScreenState();
}

class _StudentResearcherDashboardScreenState extends State<StudentResearcherDashboardScreen> {
  int _selectedTab = 0;
  bool _isLoading = true;
  String? _error;
    

  
  List<ResearchTeam> _teams = [];
  List<ResearchProject> _projects = [];
  List<ResearchTask> _tasks = [];
  List<ResearchMeeting> _meetings = [];
  List<ResearchNotification> _notifications = [];

  ResearchTask? _selectedTaskForUpdate;
  Map<String, dynamic>? _taskThread;

  // Form controllers for progress submission
  final _pctController = TextEditingController(text: '50');
  final _papersController = TextEditingController();
  final _citationsController = TextEditingController();
  final _notesController = TextEditingController();
  final _challengesController = TextEditingController();
  final _nextStepsController = TextEditingController();
  final _replyMessageController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadOverview();
  }

  @override
  void dispose() {
    _pctController.dispose();
    _papersController.dispose();
    _citationsController.dispose();
    _notesController.dispose();
    _challengesController.dispose();
    _nextStepsController.dispose();
    _replyMessageController.dispose();
    super.dispose();
  }

  Future<void> _loadOverview({bool forceRefresh = false, bool silent = false}) async {
    if (!silent) {
      setState(() {
        _isLoading = true;
        _error = null;
      });
    }

    try {
      final service = widget.researchService;
      final data = await service.getStudentOverview(forceRefresh: forceRefresh);
      if (mounted) {
        final rawTeams = data['teams'] as List<dynamic>? ?? [];
        final rawProjects = data['projects'] as List<dynamic>? ?? [];
        final rawTasks = data['tasks'] as List<dynamic>? ?? [];
        final rawMeetings = data['upcoming_meetings'] as List<dynamic>? ?? [];
        final rawNotifs = data['notifications'] as List<dynamic>? ?? [];

        setState(() {
          _teams = rawTeams.map((e) => ResearchTeam.fromJson(Map<String, dynamic>.from(e as Map))).toList();
          _projects = rawProjects.map((e) => ResearchProject.fromJson(Map<String, dynamic>.from(e as Map))).toList();
          _tasks = rawTasks.map((e) => ResearchTask.fromJson(Map<String, dynamic>.from(e as Map))).toList();
          _meetings = rawMeetings.map((e) => ResearchMeeting.fromJson(Map<String, dynamic>.from(e as Map))).toList();
          _notifications = rawNotifs.map((e) => ResearchNotification.fromJson(Map<String, dynamic>.from(e as Map))).toList();
          _isLoading = false;
        });

        if (_tasks.isNotEmpty && _selectedTaskForUpdate == null) {
          _selectTask(_tasks.first);
        }
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

  Future<void> _selectTask(ResearchTask task) async {
    setState(() {
      _selectedTaskForUpdate = task;
      _pctController.text = task.progressPercentage.toString();
    });

    try {
      final service = widget.researchService;
      final thread = await service.getFeedbackThread(task.id);
      if (mounted) {
        setState(() {
          _taskThread = thread;
        });
      }
    } catch (_) {}
  }

  // ---------------------------------------------------------------------------
  // Top Header
  // ---------------------------------------------------------------------------
  Widget _buildHeader(BuildContext context) {
    final auth = widget.authService;
    final user = auth.currentUser;
    final st = user?['research_student_profile'] as Map<String, dynamic>?;
    final fullName = st?['full_name'] ?? user?['full_name'] ?? 'Student Researcher';
    final regNum = st?['registration_number'] ?? '';
    final dept = st?['department'] ?? 'ECE';
    final sem = st?['semester'] ?? 'Semester 5';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(bottom: BorderSide(color: Color(0xFFE5E7EB))),
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 20,
            backgroundColor: const Color(0xFF111827),
            child: Text(
              fullName.isNotEmpty ? fullName[0].toUpperCase() : 'S',
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 14),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Text(
                      fullName,
                      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
                    ),
                    if (regNum.isNotEmpty) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                        decoration: BoxDecoration(
                          color: const Color(0xFFF3F4F6),
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: const Color(0xFFE5E7EB)),
                        ),
                        child: Text(
                          regNum,
                          style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: Color(0xFF374151)),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  '$dept • $sem • Student Researcher Portal',
                  style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.refresh_rounded, color: Color(0xFF374151), size: 20),
            onPressed: () => _loadOverview(forceRefresh: true),
            tooltip: 'Refresh',
          ),
          const SizedBox(width: 8),
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
  // Tab Bar
  // ---------------------------------------------------------------------------
  Widget _buildTabBar() {
    final tabs = [
      {'label': 'My Projects & Teams', 'icon': Icons.folder_outlined},
      {'label': 'Assigned Tasks', 'icon': Icons.task_alt_rounded},
      {'label': 'Submit Progress & Feedback', 'icon': Icons.rate_review_outlined},
      {'label': 'Meetings & Notices', 'icon': Icons.calendar_month_outlined},
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
          final isSelected = _selectedTab == index;
          final tab = tabs[index];
          return InkWell(
            onTap: () => setState(() => _selectedTab = index),
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

    Widget body;
    switch (_selectedTab) {
      case 0:
        body = _buildProjectsAndTeamsTab();
        break;
      case 1:
        body = _buildTasksTab();
        break;
      case 2:
        body = _buildSubmitProgressTab();
        break;
      case 3:
        body = _buildMeetingsAndNoticesTab();
        break;
      default:
        body = _buildProjectsAndTeamsTab();
    }

    return Scaffold(
      backgroundColor: const Color(0xFFFAFAFA),
      body: Column(
        children: [
          _buildHeader(context),
          _buildTabBar(),
          Expanded(child: body),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // TAB 0: PROJECTS & TEAMS
  // ---------------------------------------------------------------------------
  Widget _buildProjectsAndTeamsTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'My Enrolled Research Teams',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
          ),
          const SizedBox(height: 14),

          if (_teams.isEmpty)
            const Text('You are not currently enrolled in any research teams.', style: TextStyle(color: Color(0xFF6B7280), fontSize: 13))
          else
            ..._teams.map((t) {
              return Container(
                margin: const EdgeInsets.only(bottom: 14),
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFFE5E7EB)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(t.name, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFF111827))),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF3F4F6),
                            borderRadius: BorderRadius.circular(4),
                            border: Border.all(color: const Color(0xFFE5E7EB)),
                          ),
                          child: Text(t.domain.toUpperCase(), style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: Color(0xFF374151))),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text('Coordinator: ${t.facultyName ?? "Faculty"} • ${t.memberCount} Members', style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
                    if (t.description != null && t.description!.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text(t.description!, style: const TextStyle(fontSize: 13, color: Color(0xFF374151))),
                    ],
                  ],
                ),
              );
            }),

          const SizedBox(height: 28),
          const Text(
            'Assigned Research Projects',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
          ),
          const SizedBox(height: 14),

          if (_projects.isEmpty)
            const Text('No research projects assigned to you yet.', style: TextStyle(color: Color(0xFF6B7280), fontSize: 13))
          else
            ..._projects.map((p) {
              return Container(
                margin: const EdgeInsets.only(bottom: 14),
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFFE5E7EB)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(p.title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFF111827))),
                    const SizedBox(height: 4),
                    Text('Status: ${p.status.toUpperCase()} • Target Date: ${p.expectedCompletionDate != null ? p.expectedCompletionDate!.substring(0, 10) : "TBD"}',
                        style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
                    if (p.researchProblem != null) ...[
                      const SizedBox(height: 8),
                      Text('Problem Statement: ${p.researchProblem}', style: const TextStyle(fontSize: 13, color: Color(0xFF374151))),
                    ],
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // TAB 1: ASSIGNED TASKS
  // ---------------------------------------------------------------------------
  Widget _buildTasksTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'My Assigned Research Tasks',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
          ),
          const SizedBox(height: 4),
          const Text('Submit deliverables and track progress toward milestone targets.', style: TextStyle(fontSize: 13, color: Color(0xFF6B7280))),
          const SizedBox(height: 20),

          if (_tasks.isEmpty)
            const Text('No tasks currently assigned to you.', style: TextStyle(color: Color(0xFF6B7280), fontSize: 13))
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _tasks.length,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (context, i) {
                final t = _tasks[i];
                return Container(
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: const Color(0xFFE5E7EB)),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        t.status == 'approved' ? Icons.check_circle_rounded : Icons.pending_actions_rounded,
                        color: t.status == 'approved' ? const Color(0xFF059669) : const Color(0xFF111827),
                        size: 22,
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(t.title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Color(0xFF111827))),
                            const SizedBox(height: 2),
                            Text('Priority: ${t.priority} • Due: ${t.dueDate != null ? t.dueDate!.substring(0, 10) : "Flexible"}',
                                style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
                            if (t.instructions != null && t.instructions!.isNotEmpty)
                              Padding(
                                padding: const EdgeInsets.only(top: 4),
                                child: Text(t.instructions!, style: const TextStyle(fontSize: 12, color: Color(0xFF374151))),
                              ),
                          ],
                        ),
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text('${t.progressPercentage}%', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Color(0xFF111827))),
                          const SizedBox(height: 6),
                          ElevatedButton(
                            onPressed: () {
                              setState(() => _selectedTab = 2);
                              _selectTask(t);
                            },
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF111827),
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                              elevation: 0,
                            ),
                            child: const Text('Update Progress', style: TextStyle(fontSize: 11)),
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
  // TAB 2: SUBMIT PROGRESS & CONVERSATION THREAD
  // ---------------------------------------------------------------------------
  Widget _buildSubmitProgressTab() {
    if (_selectedTaskForUpdate == null) {
      return const Center(child: Text('Please select a task from the Assigned Tasks tab.'));
    }

    final thread = _taskThread;
    final messages = thread?['messages'] as List<dynamic>? ?? [];

    return Row(
      children: [
        // Left: Submission Form
        Expanded(
          flex: 1,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Container(
              padding: const EdgeInsets.all(22),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFE5E7EB)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Submit Progress for: ${_selectedTaskForUpdate!.title}',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
                  ),
                  const SizedBox(height: 4),
                  const Text('Report your research deliverables, papers reviewed, and challenges.', style: TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
                  const SizedBox(height: 20),

                  const Text('Work Completed (Percentage %)', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 6),
                  TextField(
                    controller: _pctController,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(border: OutlineInputBorder(), hintText: 'e.g. 60'),
                  ),
                  const SizedBox(height: 14),

                  Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Papers Reviewed', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                            const SizedBox(height: 6),
                            TextField(controller: _papersController, keyboardType: TextInputType.number, decoration: const InputDecoration(border: OutlineInputBorder(), hintText: 'e.g. 12')),
                          ],
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Citations Prepared', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                            const SizedBox(height: 6),
                            TextField(controller: _citationsController, keyboardType: TextInputType.number, decoration: const InputDecoration(border: OutlineInputBorder(), hintText: 'e.g. 8')),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),

                  const Text('Work Summary / Notes *', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 6),
                  TextField(controller: _notesController, maxLines: 3, decoration: const InputDecoration(border: OutlineInputBorder(), hintText: 'Describe progress completed...')),
                  const SizedBox(height: 14),

                  const Text('Challenges Faced (Optional)', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 6),
                  TextField(controller: _challengesController, decoration: const InputDecoration(border: OutlineInputBorder(), hintText: 'e.g. Need IEEE access...')),
                  const SizedBox(height: 14),

                  const Text('Next Steps (Optional)', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 6),
                  TextField(controller: _nextStepsController, decoration: const InputDecoration(border: OutlineInputBorder(), hintText: 'e.g. Finish remaining 8 papers...')),
                  const SizedBox(height: 20),

                  ElevatedButton(
                    onPressed: _submitProgress,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF111827),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      elevation: 0,
                    ),
                    child: const Center(child: Text('Submit for Faculty Review', style: TextStyle(fontWeight: FontWeight.w600))),
                  ),
                ],
              ),
            ),
          ),
        ),

        // Right: Continuous Conversation Thread
        Expanded(
          flex: 1,
          child: Container(
            color: const Color(0xFFFAFAFA),
            child: Column(
              children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  color: Colors.white,
                  child: const Row(
                    children: [
                      Icon(Icons.forum_outlined, size: 18, color: Color(0xFF111827)),
                      SizedBox(width: 8),
                      Text('Faculty Feedback Conversation', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
                    ],
                  ),
                ),
                const Divider(height: 1, color: Color(0xFFE5E7EB)),
                Expanded(
                  child: messages.isEmpty
                      ? const Center(child: Text('No feedback messages yet. Submit an update to begin.', style: TextStyle(fontSize: 12, color: Color(0xFF9CA3AF))))
                      : ListView.builder(
                          padding: const EdgeInsets.all(16),
                          itemCount: messages.length,
                          itemBuilder: (context, i) {
                            final m = Map<String, dynamic>.from(messages[i] as Map);
                            final isFaculty = m['sender_role'] == 'faculty_coordinator';
                            final senderName = m['sender_name'] ?? (isFaculty ? 'Faculty' : 'You');
                            final text = m['message_text'] ?? '';
                            return Container(
                              margin: const EdgeInsets.only(bottom: 12),
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: isFaculty ? const Color(0xFFF9FAFB) : Colors.white,
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(color: const Color(0xFFE5E7EB)),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Text(senderName, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
                                      Text(
                                        isFaculty ? 'FACULTY' : 'STUDENT',
                                        style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: isFaculty ? const Color(0xFF111827) : const Color(0xFF2563EB)),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 6),
                                  Text(text, style: const TextStyle(fontSize: 13, color: Color(0xFF374151))),
                                ],
                              ),
                            );
                          },
                        ),
                ),
                Container(
                  padding: const EdgeInsets.all(12),
                  color: Colors.white,
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _replyMessageController,
                          decoration: const InputDecoration(hintText: 'Reply to faculty feedback...', contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10), border: OutlineInputBorder()),
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton(icon: const Icon(Icons.send_rounded, color: Color(0xFF111827)), onPressed: _sendStudentReply),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Future<void> _submitProgress() async {
    if (_selectedTaskForUpdate == null) return;
    final notes = _notesController.text.trim();
    if (notes.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Please enter work summary notes.')));
      return;
    }

    final pct = int.tryParse(_pctController.text.trim()) ?? 50;
    final papers = int.tryParse(_papersController.text.trim());
    final citations = int.tryParse(_citationsController.text.trim());
    final challenges = _challengesController.text.trim();
    final nextSteps = _nextStepsController.text.trim();

    // Instant optimistic update
    final currentTask = _selectedTaskForUpdate!;
    final updatedTask = currentTask.copyWith(
      status: 'submitted_for_review',
      progressPercentage: pct,
    );
    setState(() {
      _selectedTaskForUpdate = updatedTask;
      final idx = _tasks.indexWhere((t) => t.id == updatedTask.id);
      if (idx != -1) {
        _tasks[idx] = updatedTask;
      }
    });

    _notesController.clear();
    _challengesController.clear();
    _nextStepsController.clear();

    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Progress submitted for faculty review.')));

    try {
      final service = widget.researchService;
      await service.submitProgress(
        taskId: currentTask.id,
        progressPercentage: pct,
        papersReviewed: papers,
        citationsPrepared: citations,
        notes: notes,
        challenges: challenges,
        nextSteps: nextSteps,
      );
      _selectTask(updatedTask);
      _loadOverview(forceRefresh: true, silent: true);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  Future<void> _sendStudentReply() async {
    if (_selectedTaskForUpdate == null) return;
    final text = _replyMessageController.text.trim();
    if (text.isEmpty) return;

    // Instant optimistic update of message thread
    final currentThread = _taskThread != null ? Map<String, dynamic>.from(_taskThread!) : <String, dynamic>{};
    final currentMsgs = List<dynamic>.from(currentThread['messages'] ?? []);
    currentMsgs.add({
      'id': -1,
      'sender_role': 'student_researcher',
      'message_text': text,
      'message_type': 'comment',
      'created_at': DateTime.now().toUtc().toIso8601String(),
    });
    currentThread['messages'] = currentMsgs;
    setState(() {
      _taskThread = currentThread;
    });
    _replyMessageController.clear();

    try {
      final service = widget.researchService;
      await service.addFeedbackMessage(
        taskId: _selectedTaskForUpdate!.id,
        message: text,
        action: 'comment',
      );
      _selectTask(_selectedTaskForUpdate!);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  // ---------------------------------------------------------------------------
  // TAB 3: MEETINGS & NOTICES
  // ---------------------------------------------------------------------------
  Widget _buildMeetingsAndNoticesTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Scheduled Research Meetings', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Color(0xFF111827))),
          const SizedBox(height: 14),

          if (_meetings.isEmpty)
            const Text('No upcoming meetings scheduled.', style: TextStyle(color: Color(0xFF6B7280), fontSize: 13))
          else
            ..._meetings.map((m) {
              return Container(
                margin: const EdgeInsets.only(bottom: 12),
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFFE5E7EB)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(m.title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFF111827))),
                    const SizedBox(height: 2),
                    Text('Time: ${m.scheduledAt != null ? m.scheduledAt!.substring(0, 16).replaceAll("T", " ") : "TBD"}', style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
                    if (m.locationOrLink != null) ...[
                      const SizedBox(height: 4),
                      Text('Location / Meet: ${m.locationOrLink}', style: const TextStyle(fontSize: 12, color: Color(0xFF2563EB))),
                    ],
                    if (m.agenda != null) ...[
                      const SizedBox(height: 6),
                      Text('Agenda: ${m.agenda}', style: const TextStyle(fontSize: 13, color: Color(0xFF374151))),
                    ],
                  ],
                ),
              );
            }),

          const SizedBox(height: 28),
          const Text('In-App Notifications', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Color(0xFF111827))),
          const SizedBox(height: 14),

          if (_notifications.isEmpty)
            const Text('No notifications.', style: TextStyle(color: Color(0xFF6B7280), fontSize: 13))
          else
            ..._notifications.map((n) {
              return Container(
                margin: const EdgeInsets.only(bottom: 10),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFFE5E7EB)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(n.title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF111827))),
                    const SizedBox(height: 2),
                    Text(n.body, style: const TextStyle(fontSize: 12, color: Color(0xFF4B5563))),
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }

  void _confirmLogout(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Sign Out'),
        content: const Text('Are you sure you want to sign out of the Student Researcher portal?'),
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
                  'Update your student researcher password at any time according to your need.',
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
}
