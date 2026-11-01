import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../config/constants.dart';
import '../models/assignment.dart';
import '../services/auth_service.dart';
import '../services/sync_service.dart';
import '../services/whatsapp_service.dart';
import '../widgets/custom_card.dart';
import '../widgets/primary_button.dart';
import '../widgets/secondary_button.dart';
import '../widgets/state_views.dart';

class AssignmentDetailScreen extends StatefulWidget {
  final int assignmentId;
  final SyncService syncService;
  final AuthService authService;
  final WhatsAppService whatsAppService;

  const AssignmentDetailScreen({
    super.key,
    required this.assignmentId,
    required this.syncService,
    required this.authService,
    required this.whatsAppService,
  });

  @override
  State<AssignmentDetailScreen> createState() => _AssignmentDetailScreenState();
}

class _AssignmentDetailScreenState extends State<AssignmentDetailScreen> {
  TaskAssignment? _assignment;
  bool _isLoading = true;
  bool _isUpdating = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadDetails();
  }

  Future<void> _loadDetails() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final assignment = await widget.syncService.getAssignmentDetails(widget.assignmentId);
      if (mounted) {
        setState(() {
          _assignment = assignment;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString().replaceFirst('Exception: ', '');
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _transitionStatus(String targetStatus) async {
    String? note;

    if (targetStatus == 'completed' || targetStatus == 'blocked' || targetStatus == 'declined') {
      final noteController = TextEditingController();
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) {
          return AlertDialog(
            backgroundColor: AppConstants.pureWhite,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            title: Text(
              'Confirm Transition: ${targetStatus.replaceAll('_', ' ').toUpperCase()}',
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: AppConstants.pureBlack),
            ),
            content: TextField(
              controller: noteController,
              decoration: InputDecoration(
                hintText: targetStatus == 'completed'
                    ? 'Optional completion note...'
                    : 'Reason for status update...',
              ),
              maxLines: 2,
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Cancel', style: TextStyle(color: AppConstants.textSecondary)),
              ),
              PrimaryButton(
                label: 'Confirm',
                onPressed: () => Navigator.pop(context, true),
                width: 100,
                height: 38,
              ),
            ],
          );
        },
      );

      if (confirmed != true) return;
      note = noteController.text.trim().isNotEmpty ? noteController.text.trim() : null;
    }

    setState(() {
      _isUpdating = true;
    });

    try {
      final updated = await widget.syncService.updateAssignmentStatus(
        widget.assignmentId,
        targetStatus,
        note: note,
      );
      if (mounted) {
        setState(() {
          _assignment = updated;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Status updated to ${targetStatus.replaceAll('_', ' ')}.')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Update failed: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isUpdating = false;
        });
      }
    }
  }

  Future<void> _openWhatsApp() async {
    if (_assignment == null) return;
    try {
      final draft = await widget.syncService.getWhatsAppLink(_assignment!.id);
      final launched = await widget.whatsAppService.launchWhatsAppUrl(draft.whatsappUrl);
      if (launched) {
        await widget.whatsAppService.recordActionLinkOpened(
          assignmentId: draft.assignmentId,
          messageLogId: draft.messageLogId,
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not open WhatsApp: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final dateFormat = DateFormat('EEE, MMM d, yyyy • h:mm a');
    final a = _assignment;

    final allowedNextStatuses = a != null
        ? (TaskAssignment.allowedTransitions[a.status] ?? [])
        : <String>[];

    // Filter allowed transitions based on user role:
    // Regular members cannot mark completed or cancelled
    final isAdminOrLeader = widget.authService.isAdmin || widget.authService.isTeamLeader;
    final availableTransitions = allowedNextStatuses.where((status) {
      if ((status == 'completed' || status == 'cancelled') && !isAdminOrLeader) {
        return false;
      }
      return true;
    }).toList();

    return Scaffold(
      backgroundColor: AppConstants.pureWhite,
      appBar: AppBar(
        title: const Text('Assignment Details'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, size: 20),
            onPressed: _loadDetails,
          ),
        ],
      ),
      body: SafeArea(
        child: _isLoading
            ? const LoadingView(message: 'Loading assignment details...')
            : _errorMessage != null && a == null
                ? ErrorView(message: _errorMessage!, onRetry: _loadDetails)
                : a == null
                    ? const EmptyView(message: 'Assignment not found.')
                    : SingleChildScrollView(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Task Title & Event
                            Text(
                              a.taskTitle ?? 'Task',
                              style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.w700,
                                color: AppConstants.pureBlack,
                                letterSpacing: -0.2,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              'Event: ${a.eventName ?? "Unknown"}',
                              style: const TextStyle(
                                fontSize: 13,
                                color: AppConstants.textSecondary,
                              ),
                            ),
                            const SizedBox(height: 18),

                            // Status Card
                            CustomCard(
                              padding: const EdgeInsets.all(14),
                              child: Row(
                                children: [
                                  Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      const Text(
                                        'CURRENT STATUS',
                                        style: TextStyle(
                                          fontSize: 10,
                                          fontWeight: FontWeight.w700,
                                          color: AppConstants.textSecondary,
                                          letterSpacing: 0.5,
                                        ),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        a.status.replaceAll('_', ' ').toUpperCase(),
                                        style: const TextStyle(
                                          fontSize: 14,
                                          fontWeight: FontWeight.w700,
                                          color: AppConstants.pureBlack,
                                        ),
                                      ),
                                    ],
                                  ),
                                  const Spacer(),
                                  if (a.isOverdue) ...[
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                      decoration: BoxDecoration(
                                        color: const Color(0xFFFEF2F2),
                                        borderRadius: BorderRadius.circular(4),
                                        border: Border.all(color: const Color(0xFFFCA5A5)),
                                      ),
                                      child: const Text(
                                        'OVERDUE',
                                        style: TextStyle(
                                          color: AppConstants.dangerRed,
                                          fontSize: 11,
                                          fontWeight: FontWeight.w700,
                                        ),
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            ),

                            const SizedBox(height: 16),

                            // Assignee Info Card
                            CustomCard(
                              padding: const EdgeInsets.all(14),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text(
                                    'ASSIGNED MEMBER',
                                    style: TextStyle(
                                      fontSize: 10,
                                      fontWeight: FontWeight.w700,
                                      color: AppConstants.textSecondary,
                                      letterSpacing: 0.5,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Row(
                                    children: [
                                      const Icon(Icons.person_outline, size: 16, color: AppConstants.textSecondary),
                                      const SizedBox(width: 8),
                                      Expanded(
                                        child: Text(
                                          a.memberName ?? 'Member',
                                          style: const TextStyle(
                                            fontSize: 14,
                                            fontWeight: FontWeight.w600,
                                            color: AppConstants.pureBlack,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                  if (a.memberRegNo != null) ...[
                                    const SizedBox(height: 4),
                                    Padding(
                                      padding: const EdgeInsets.only(left: 24),
                                      child: Text(
                                        'Reg: ${a.memberRegNo}',
                                        style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                                      ),
                                    ),
                                  ],
                                  if (a.memberPhone != null && a.memberPhone!.isNotEmpty) ...[
                                    const SizedBox(height: 4),
                                    Padding(
                                      padding: const EdgeInsets.only(left: 24),
                                      child: Text(
                                        'Phone: ${a.memberPhone}',
                                        style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                                      ),
                                    ),
                                  ],
                                  if (a.teamName != null) ...[
                                    const SizedBox(height: 4),
                                    Padding(
                                      padding: const EdgeInsets.only(left: 24),
                                      child: Text(
                                        'Team: ${a.teamName}',
                                        style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            ),

                            const SizedBox(height: 16),

                            // Deadline Info
                            CustomCard(
                              padding: const EdgeInsets.all(14),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text(
                                    'DEADLINE & SCHEDULE',
                                    style: TextStyle(
                                      fontSize: 10,
                                      fontWeight: FontWeight.w700,
                                      color: AppConstants.textSecondary,
                                      letterSpacing: 0.5,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Row(
                                    children: [
                                      const Icon(Icons.schedule, size: 16, color: AppConstants.textSecondary),
                                      const SizedBox(width: 8),
                                      Text(
                                        a.deadline != null ? dateFormat.format(a.deadline!) : 'No deadline',
                                        style: TextStyle(
                                          fontSize: 13,
                                          fontWeight: FontWeight.w500,
                                          color: a.isOverdue ? AppConstants.dangerRed : AppConstants.pureBlack,
                                        ),
                                      ),
                                    ],
                                  ),
                                  if (a.completedAt != null) ...[
                                    const SizedBox(height: 6),
                                    Text(
                                      'Completed on: ${dateFormat.format(a.completedAt!)}',
                                      style: const TextStyle(fontSize: 12, color: AppConstants.successGreen),
                                    ),
                                  ],
                                  if (a.completionNote != null && a.completionNote!.isNotEmpty) ...[
                                    const SizedBox(height: 6),
                                    Text(
                                      'Note: "${a.completionNote}"',
                                      style: const TextStyle(fontSize: 12, fontStyle: FontStyle.italic, color: AppConstants.textSecondary),
                                    ),
                                  ],
                                ],
                              ),
                            ),

                            const SizedBox(height: 24),

                            // Allowed Status Transitions
                            if (availableTransitions.isNotEmpty) ...[
                              const Text(
                                'Update Status',
                                style: TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                  color: AppConstants.pureBlack,
                                ),
                              ),
                              const SizedBox(height: 10),
                              Wrap(
                                spacing: 8,
                                runSpacing: 8,
                                children: availableTransitions.map((target) {
                                  return SizedBox(
                                    width: 160,
                                    child: PrimaryButton(
                                      label: target.replaceAll('_', ' ').toUpperCase(),
                                      isLoading: _isUpdating,
                                      height: 42,
                                      onPressed: _isUpdating ? null : () => _transitionStatus(target),
                                    ),
                                  );
                                }).toList(),
                              ),
                              const SizedBox(height: 18),
                            ],

                            // WhatsApp Action
                            SecondaryButton(
                              label: 'WhatsApp Message Draft',
                              icon: Icons.chat_outlined,
                              onPressed: _openWhatsApp,
                            ),
                          ],
                        ),
                      ),
      ),
    );
  }
}
