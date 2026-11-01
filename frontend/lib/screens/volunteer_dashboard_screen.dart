import 'package:flutter/material.dart';
import '../config/constants.dart';
import '../models/assignment.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';
import '../services/sync_service.dart';
import '../widgets/custom_card.dart';
import '../widgets/offline_banner.dart';
import '../widgets/secondary_button.dart';
import '../widgets/state_views.dart';
import 'community_screen.dart';
import '../services/community_service.dart';

class VolunteerDashboardScreen extends StatefulWidget {
  final SyncService syncService;
  final AuthService authService;
  final VoidCallback onLogout;

  const VolunteerDashboardScreen({
    super.key,
    required this.syncService,
    required this.authService,
    required this.onLogout,
  });

  @override
  State<VolunteerDashboardScreen> createState() => _VolunteerDashboardScreenState();
}

class _VolunteerDashboardScreenState extends State<VolunteerDashboardScreen> {
  List<TaskAssignment> _assignments = [];
  bool _isLoading = true;
  String? _errorMessage;
  bool _isSessionExpired = false;
  bool _isUnlinkedAccount = false;

  @override
  void initState() {
    super.initState();
    _fetchTasks();
    widget.authService.onSessionExpired.listen((_) {
      if (mounted) {
        setState(() {
          _isSessionExpired = true;
        });
      }
    });
  }

  Future<void> _fetchTasks() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
      _isSessionExpired = false;
      _isUnlinkedAccount = false;
    });

    try {
      final tasks = await widget.syncService.fetchMyAssignments();
      if (mounted) {
        setState(() {
          _assignments = tasks;
          _isLoading = false;
        });
      }
    } on ApiException catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
          if (e.statusCode == 401 || e.code == 'UNAUTHORIZED') {
            _isSessionExpired = true;
            _errorMessage = 'Session expired. Please log in again.';
          } else if (e.statusCode == 404 || e.message.contains('not associated with any club member')) {
            _isUnlinkedAccount = true;
            _errorMessage = 'Your account is not linked to any member record. Please contact the administrator.';
          } else {
            _errorMessage = e.message;
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
          _errorMessage = e.toString().replaceFirst('Exception: ', '');
        });
      }
    }
  }

  Future<void> _handleStatusAction(TaskAssignment assignment, String targetStatus, {String? note}) async {
    try {
      await widget.syncService.updateAssignmentStatus(assignment.id, targetStatus, note: note);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(_getActionSuccessMessage(targetStatus)),
            backgroundColor: AppConstants.pureBlack,
            duration: const Duration(seconds: 2),
          ),
        );
        _fetchTasks();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to update: ${e.toString().replaceFirst("Exception: ", "")}')),
        );
      }
    }
  }

  String _getActionSuccessMessage(String status) {
    switch (status) {
      case 'accepted':
        return 'Task accepted successfully!';
      case 'in_progress':
        return 'Task marked in progress!';
      case 'submitted':
        return 'Work submitted for team leader review!';
      case 'declined':
        return 'Task assignment declined.';
      default:
        return 'Task updated.';
    }
  }

  Future<void> _promptSubmitWork(TaskAssignment assignment) async {
    final noteController = TextEditingController();
    final formKey = GlobalKey<FormState>();

    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppConstants.pureWhite,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        title: const Text('Submit Completed Work', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
        content: Form(
          key: formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Task: ${assignment.taskTitle ?? "Assigned Task"}',
                style: const TextStyle(fontSize: 13, color: AppConstants.textSecondary),
              ),
              const SizedBox(height: 12),
              const Text('Completion Note / Summary *', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
              const SizedBox(height: 6),
              TextFormField(
                controller: noteController,
                maxLines: 3,
                validator: (val) {
                  if (val == null || val.trim().isEmpty) return 'Please describe the work completed.';
                  return null;
                },
                decoration: InputDecoration(
                  hintText: 'e.g. Managed registration desk, registered 120 attendees...',
                  hintStyle: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                  contentPadding: const EdgeInsets.all(10),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Cancel', style: TextStyle(color: AppConstants.textSecondary)),
          ),
          TextButton(
            onPressed: () {
              if (formKey.currentState?.validate() ?? false) {
                final note = noteController.text.trim();
                Navigator.of(ctx).pop();
                _handleStatusAction(assignment, 'submitted', note: note);
              }
            },
            child: const Text('Submit', style: TextStyle(color: AppConstants.pureBlack, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  Future<void> _showChangePasswordDialog() async {
    final currentController = TextEditingController();
    final newController = TextEditingController();
    bool isSaving = false;
    String? dialogError;

    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              backgroundColor: AppConstants.pureWhite,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              title: const Text('Change Password', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              content: SizedBox(
                width: 380,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (dialogError != null) ...[
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: Colors.red.shade50,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(dialogError!, style: TextStyle(color: Colors.red.shade800, fontSize: 12)),
                      ),
                      const SizedBox(height: 10),
                    ],
                    const Text('Current Password', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 4),
                    TextField(
                      controller: currentController,
                      obscureText: true,
                      decoration: const InputDecoration(
                        hintText: 'Enter your current password',
                        contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                    const Text('New Password (min 6 chars)', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 4),
                    TextField(
                      controller: newController,
                      obscureText: true,
                      decoration: const InputDecoration(
                        hintText: 'Enter your new password',
                        contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                        border: OutlineInputBorder(),
                      ),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: isSaving ? null : () => Navigator.of(ctx).pop(),
                  child: const Text('Cancel', style: TextStyle(color: AppConstants.textSecondary)),
                ),
                TextButton(
                  onPressed: isSaving
                      ? null
                      : () async {
                          final current = currentController.text;
                          final newPwd = newController.text;
                          if (current.isEmpty || newPwd.length < 6) {
                            setDialogState(() => dialogError = 'New password must be at least 6 characters.');
                            return;
                          }

                          setDialogState(() {
                            isSaving = true;
                            dialogError = null;
                          });

                          try {
                            await widget.syncService.apiClient.post(
                              '/auth/change-password',
                              body: {'current_password': current, 'new_password': newPwd},
                            );
                            if (ctx.mounted) {
                              Navigator.of(ctx).pop();
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text('Password changed successfully! Please log in with your new password.'),
                                  backgroundColor: AppConstants.pureBlack,
                                ),
                              );
                              widget.onLogout();
                            }
                          } catch (e) {
                            setDialogState(() {
                              isSaving = false;
                              dialogError = e.toString().replaceFirst('Exception: ', '');
                            });
                          }
                        },
                  child: isSaving
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('Update', style: TextStyle(color: AppConstants.pureBlack, fontWeight: FontWeight.bold)),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Widget _buildVolunteerHeader() {
    final displayName = widget.authService.displayName;
    final teamName = widget.authService.teamName ?? 'Volunteering Team';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      decoration: const BoxDecoration(
        color: AppConstants.backgroundLight,
        border: Border(bottom: BorderSide(color: AppConstants.borderLight)),
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 22,
            backgroundColor: AppConstants.pureBlack,
            child: Text(
              displayName.isNotEmpty ? displayName.substring(0, 1).toUpperCase() : 'V',
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  displayName,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: AppConstants.pureBlack,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  teamName,
                  style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusBadge(String status) {
    Color bg = AppConstants.backgroundLight;
    Color fg = AppConstants.pureBlack;
    String label = status.replaceAll('_', ' ').toUpperCase();

    switch (status) {
      case 'awaiting_confirmation':
        bg = Colors.amber.shade100;
        fg = Colors.amber.shade900;
        label = 'PENDING';
        break;
      case 'accepted':
        bg = Colors.blue.shade50;
        fg = Colors.blue.shade800;
        label = 'ACCEPTED';
        break;
      case 'in_progress':
        bg = AppConstants.pureBlack;
        fg = Colors.white;
        label = 'IN PROGRESS';
        break;
      case 'submitted':
        bg = Colors.purple.shade50;
        fg = Colors.purple.shade800;
        label = 'SUBMITTED';
        break;
      case 'completed':
        bg = Colors.green.shade50;
        fg = Colors.green.shade800;
        label = 'COMPLETED';
        break;
      case 'declined':
        bg = Colors.grey.shade200;
        fg = Colors.grey.shade700;
        label = 'DECLINED';
        break;
      case 'blocked':
        bg = Colors.red.shade50;
        fg = Colors.red.shade800;
        label = 'BLOCKED';
        break;
      case 'cancelled':
        bg = Colors.grey.shade200;
        fg = Colors.grey.shade600;
        label = 'CANCELLED';
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(4)),
      child: Text(
        label,
        style: TextStyle(color: fg, fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 0.5),
      ),
    );
  }

  Widget _buildTaskCard(TaskAssignment assignment) {
    final title = assignment.taskTitle ?? 'Untitled Task';
    final eventName = assignment.eventName ?? 'Club Event';
    final description = assignment.taskDescription;
    final deadline = assignment.deadlineFormatted ?? assignment.deadline?.toString();
    final priority = (assignment.taskPriority ?? 'MEDIUM').toUpperCase();
    final status = assignment.status;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: CustomCard(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Top Row: Event Name & Priority Badge
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    eventName.toUpperCase(),
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: AppConstants.textSecondary,
                      letterSpacing: 0.5,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: priority == 'HIGH' ? Colors.red.shade50 : AppConstants.backgroundLight,
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: priority == 'HIGH' ? Colors.red.shade200 : AppConstants.borderLight),
                  ),
                  child: Text(
                    priority,
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                      color: priority == 'HIGH' ? Colors.red.shade800 : AppConstants.textSecondary,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),

            // Task Title
            Text(
              title,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AppConstants.pureBlack,
              ),
            ),
            const SizedBox(height: 6),

            // Task Description / Assigned Work
            if (description != null && description.isNotEmpty) ...[
              Text(
                'Assigned work: $description',
                style: const TextStyle(fontSize: 13, color: AppConstants.pureBlack, height: 1.4),
              ),
              const SizedBox(height: 8),
            ],

            // Deadline
            if (deadline != null) ...[
              Row(
                children: [
                  const Icon(Icons.schedule, size: 14, color: AppConstants.textSecondary),
                  const SizedBox(width: 4),
                  Text(
                    'Deadline: $deadline',
                    style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                  ),
                ],
              ),
              const SizedBox(height: 10),
            ],

            const Divider(height: 1, color: AppConstants.borderLight),
            const SizedBox(height: 10),

            // Status and Action Row
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    const Text('Status: ', style: TextStyle(fontSize: 12, color: AppConstants.textSecondary)),
                    _buildStatusBadge(status),
                  ],
                ),

                // Permitted volunteer status actions
                if (status == 'awaiting_confirmation') ...[
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      OutlinedButton(
                        style: OutlinedButton.styleFrom(
                          foregroundColor: Colors.red.shade700,
                          side: BorderSide(color: Colors.red.shade200),
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                          minimumSize: Size.zero,
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                        ),
                        onPressed: () => _handleStatusAction(assignment, 'declined'),
                        child: const Text('Decline', style: TextStyle(fontSize: 12)),
                      ),
                      const SizedBox(width: 8),
                      ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppConstants.pureBlack,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                          minimumSize: Size.zero,
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                        ),
                        onPressed: () => _handleStatusAction(assignment, 'accepted'),
                        child: const Text('Accept', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                      ),
                    ],
                  ),
                ] else if (status == 'accepted') ...[
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppConstants.pureBlack,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                    ),
                    onPressed: () => _handleStatusAction(assignment, 'in_progress'),
                    child: const Text('Start Task', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                  ),
                ] else if (status == 'in_progress') ...[
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppConstants.pureBlack,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                    ),
                    onPressed: () => _promptSubmitWork(assignment),
                    child: const Text('Submit Work', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                  ),
                ] else if (status == 'submitted') ...[
                  const Text(
                    'Under Leader Review',
                    style: TextStyle(fontSize: 11, fontStyle: FontStyle.italic, color: AppConstants.textSecondary),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppConstants.pureWhite,
      appBar: AppBar(
        title: const Text('My Tasks'),
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            key: const Key('btn_open_community'),
            icon: const Icon(Icons.forum_outlined, size: 20),
            tooltip: 'Discord Community',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (context) => CommunityScreen(
                    communityService: CommunityService(apiClient: widget.syncService.apiClient),
                    authService: widget.authService,
                  ),
                ),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.lock_outline, size: 20),
            tooltip: 'Change Password',
            onPressed: _showChangePasswordDialog,
          ),
          IconButton(
            icon: const Icon(Icons.refresh, size: 20),
            tooltip: 'Refresh',
            onPressed: _fetchTasks,
          ),
          IconButton(
            icon: const Icon(Icons.logout, size: 20),
            tooltip: 'Logout',
            onPressed: widget.onLogout,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            OfflineBanner(
              isOffline: widget.syncService.isOffline,
              onRetry: _fetchTasks,
            ),
            _buildVolunteerHeader(),
            Expanded(
              child: _buildBody(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const LoadingView(message: 'Loading your assigned tasks...');
    }

    if (_isSessionExpired) {
      return ErrorView(
        message: 'Your session has expired. Please log in again.',
        onRetry: widget.onLogout,
      );
    }

    if (_isUnlinkedAccount) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.account_circle_outlined, size: 48, color: AppConstants.textSecondary),
              const SizedBox(height: 16),
              const Text(
                'No Member Profile Linked',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
              ),
              const SizedBox(height: 8),
              const Text(
                'Your login account is not currently linked to any club member record. Please contact your club administrator to link your profile.',
                textAlign: TextAlign.center,
                style: TextStyle(color: AppConstants.textSecondary, fontSize: 13),
              ),
              const SizedBox(height: 20),
              SecondaryButton(label: 'Logout', onPressed: widget.onLogout, width: 140, height: 38),
            ],
          ),
        ),
      );
    }

    if (_errorMessage != null) {
      return ErrorView(
        message: _errorMessage!,
        onRetry: _fetchTasks,
      );
    }

    if (_assignments.isEmpty) {
      return RefreshIndicator(
        onRefresh: _fetchTasks,
        color: AppConstants.pureBlack,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            SizedBox(
              height: MediaQuery.of(context).size.height * 0.5,
              child: const EmptyView(
                message: 'No tasks assigned yet.\nCheck back once tasks are assigned to your team.',
                icon: Icons.task_alt_outlined,
              ),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _fetchTasks,
      color: AppConstants.pureBlack,
      child: ListView.builder(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: _assignments.length,
        itemBuilder: (context, index) {
          return _buildTaskCard(_assignments[index]);
        },
      ),
    );
  }
}
