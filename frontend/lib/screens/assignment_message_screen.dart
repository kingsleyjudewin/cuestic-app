import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../config/constants.dart';
import '../models/message_draft.dart';
import '../models/task.dart';

import '../services/sync_service.dart';
import '../services/whatsapp_service.dart';
import '../widgets/custom_card.dart';
import '../widgets/primary_button.dart';
import '../widgets/secondary_button.dart';
import '../widgets/state_views.dart';

class AssignmentMessageScreen extends StatefulWidget {
  final Task task;
  final SyncService syncService;
  final WhatsAppService whatsAppService;
  final VoidCallback onFinish;

  const AssignmentMessageScreen({
    super.key,
    required this.task,
    required this.syncService,
    required this.whatsAppService,
    required this.onFinish,
  });

  @override
  State<AssignmentMessageScreen> createState() => _AssignmentMessageScreenState();
}

class _AssignmentMessageScreenState extends State<AssignmentMessageScreen> {
  final Map<int, MessageDraft> _draftsByAssignmentId = {};
  int? _activeAssignmentId;

  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadDrafts();
  }

  Future<void> _loadDrafts() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final assignments = widget.task.assignments;
      for (final a in assignments) {
        final draft = await widget.syncService.getWhatsAppLink(
          a.id,
          memberName: a.memberName,
          taskTitle: a.taskTitle ?? widget.task.title,
          deadline: a.deadline ?? widget.task.deadline,
        );
        _draftsByAssignmentId[a.id] = draft;
      }

      if (mounted) {
        setState(() {
          _activeAssignmentId = assignments.isNotEmpty ? assignments.first.id : null;
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

  Future<void> _handleOpenWhatsApp(MessageDraft draft) async {
    final success = await widget.whatsAppService.launchWhatsAppUrl(draft.whatsappUrl);
    if (success) {
      await widget.whatsAppService.recordActionLinkOpened(
        assignmentId: draft.assignmentId,
        messageLogId: draft.messageLogId,
      );
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not open WhatsApp. Ensure WhatsApp is installed.')),
        );
      }
    }
  }

  Future<void> _handleMarkAsSent(MessageDraft draft) async {
    try {
      await widget.whatsAppService.recordActionMarkedSent(
        assignmentId: draft.assignmentId,
        messageLogId: draft.messageLogId,
      );
      setState(() {
        draft.isSent = true;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Marked as sent to ${draft.memberName ?? "member"}.')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to record action: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final dateFormat = DateFormat('MMM d, yyyy • h:mm a');
    final assignments = widget.task.assignments;
    final activeDraft = _activeAssignmentId != null ? _draftsByAssignmentId[_activeAssignmentId] : null;

    return Scaffold(
      backgroundColor: AppConstants.pureWhite,
      appBar: AppBar(
        title: const Text('Assignment Message'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.of(context).pop(),
        ),
        actions: [
          TextButton(
            onPressed: widget.onFinish,
            child: const Text(
              'Done',
              style: TextStyle(
                color: AppConstants.pureBlack,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: _isLoading
            ? const LoadingView(message: 'Generating WhatsApp message draft...')
            : _errorMessage != null
                ? ErrorView(message: _errorMessage!, onRetry: _loadDrafts)
                : assignments.isEmpty
                    ? const EmptyView(message: 'No assignments to notify.')
                    : Column(
                        children: [
                          Expanded(
                            child: SingleChildScrollView(
                              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  // Task Summary Card
                                  Container(
                                    width: double.infinity,
                                    padding: const EdgeInsets.all(14),
                                    decoration: BoxDecoration(
                                      color: const Color(0xFFF9FAFB),
                                      borderRadius: BorderRadius.circular(8),
                                      border: Border.all(color: AppConstants.borderLight),
                                    ),
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          widget.task.title,
                                          style: const TextStyle(
                                            fontSize: 15,
                                            fontWeight: FontWeight.w600,
                                            color: AppConstants.pureBlack,
                                          ),
                                        ),
                                        const SizedBox(height: 4),
                                        Row(
                                          children: [
                                            const Icon(Icons.schedule, size: 13, color: AppConstants.textSecondary),
                                            const SizedBox(width: 4),
                                            Text(
                                              'Deadline: ${dateFormat.format(widget.task.deadline)}',
                                              style: const TextStyle(
                                                fontSize: 12,
                                                color: AppConstants.textSecondary,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ],
                                    ),
                                  ),

                                  const SizedBox(height: 18),

                                  // If multiple members, show tab selector
                                  if (assignments.length > 1) ...[
                                    const Text(
                                      'Select Member Conversation',
                                      style: TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w600,
                                        color: AppConstants.pureBlack,
                                      ),
                                    ),
                                    const SizedBox(height: 8),
                                    SizedBox(
                                      height: 38,
                                      child: ListView.separated(
                                        scrollDirection: Axis.horizontal,
                                        itemCount: assignments.length,
                                        separatorBuilder: (_, _) => const SizedBox(width: 8),

                                        itemBuilder: (context, index) {
                                          final a = assignments[index];
                                          final draft = _draftsByAssignmentId[a.id];
                                          final isSelected = _activeAssignmentId == a.id;

                                          return InkWell(
                                            onTap: () {
                                              setState(() {
                                                _activeAssignmentId = a.id;
                                              });
                                            },
                                            borderRadius: BorderRadius.circular(6),
                                            child: Container(
                                              padding: const EdgeInsets.symmetric(horizontal: 12),
                                              alignment: Alignment.center,
                                              decoration: BoxDecoration(
                                                color: isSelected ? AppConstants.pureBlack : AppConstants.pureWhite,
                                                borderRadius: BorderRadius.circular(6),
                                                border: Border.all(
                                                  color: isSelected ? AppConstants.pureBlack : AppConstants.borderLight,
                                                ),
                                              ),
                                              child: Row(
                                                children: [
                                                  Text(
                                                    a.memberName ?? 'Member #${a.id}',
                                                    style: TextStyle(
                                                      fontSize: 12,
                                                      fontWeight: FontWeight.w500,
                                                      color: isSelected ? AppConstants.pureWhite : AppConstants.pureBlack,
                                                    ),
                                                  ),
                                                  if (draft?.isSent == true) ...[
                                                    const SizedBox(width: 4),
                                                    Icon(
                                                      Icons.check_circle,
                                                      size: 13,
                                                      color: isSelected ? Colors.white : AppConstants.successGreen,
                                                    ),
                                                  ],
                                                ],
                                              ),
                                            ),
                                          );
                                        },
                                      ),
                                    ),
                                    const SizedBox(height: 18),
                                  ],

                                  if (activeDraft != null) ...[
                                    // Target Member Info
                                    Row(
                                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                      children: [
                                        Text(
                                          'Recipient: ${activeDraft.memberName ?? "Member"}',
                                          style: const TextStyle(
                                            fontSize: 13,
                                            fontWeight: FontWeight.w600,
                                            color: AppConstants.pureBlack,
                                          ),
                                        ),
                                        if (activeDraft.phoneNumber.isNotEmpty)
                                          Text(
                                            activeDraft.phoneNumber,
                                            style: const TextStyle(
                                              fontSize: 12,
                                              color: AppConstants.textSecondary,
                                            ),
                                          ),
                                      ],
                                    ),

                                    const SizedBox(height: 10),

                                    // Plain-text Preview of WhatsApp Message
                                    CustomCard(
                                      padding: const EdgeInsets.all(14),
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Row(
                                            children: const [
                                              Icon(Icons.chat_bubble_outline, size: 14, color: AppConstants.textSecondary),
                                              SizedBox(width: 6),
                                              Text(
                                                'Message Preview',
                                                style: TextStyle(
                                                  fontSize: 12,
                                                  fontWeight: FontWeight.w600,
                                                  color: AppConstants.textSecondary,
                                                ),
                                              ),
                                            ],
                                          ),
                                          const SizedBox(height: 10),
                                          SelectableText(
                                            activeDraft.messageText,
                                            style: const TextStyle(
                                              fontSize: 13,
                                              color: AppConstants.pureBlack,
                                              height: 1.45,
                                              fontFamily: 'monospace',
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),

                                    const SizedBox(height: 12),
                                    const Text(
                                      'Note: Tapping "Open WhatsApp" launches the official WhatsApp conversation with the pre-filled message. It does not automatically send the message.',
                                      style: TextStyle(
                                        fontSize: 11,
                                        color: AppConstants.textSecondary,
                                        height: 1.3,
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            ),
                          ),

                          // Actions Footer
                          if (activeDraft != null)
                            Container(
                              padding: const EdgeInsets.all(16),
                              decoration: const BoxDecoration(
                                border: Border(top: BorderSide(color: AppConstants.borderLight, width: 1)),
                                color: AppConstants.pureWhite,
                              ),
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  PrimaryButton(
                                    label: 'Open WhatsApp',
                                    icon: Icons.send_outlined,
                                    onPressed: () => _handleOpenWhatsApp(activeDraft),
                                  ),
                                  const SizedBox(height: 8),
                                  SecondaryButton(
                                    label: activeDraft.isSent ? 'Sent ✓' : 'Mark as Sent',
                                    onPressed: activeDraft.isSent ? null : () => _handleMarkAsSent(activeDraft),
                                  ),
                                ],
                              ),
                            ),
                        ],
                      ),
      ),
    );
  }
}
