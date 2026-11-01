import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../config/constants.dart';
import '../models/assignment.dart';
import '../services/sync_service.dart';
import '../widgets/custom_card.dart';
import '../widgets/offline_banner.dart';
import '../widgets/state_views.dart';

class AssignmentTrackingScreen extends StatefulWidget {
  final SyncService syncService;
  final void Function(int assignmentId) onSelectAssignment;

  const AssignmentTrackingScreen({
    super.key,
    required this.syncService,
    required this.onSelectAssignment,
  });

  @override
  State<AssignmentTrackingScreen> createState() => _AssignmentTrackingScreenState();
}

class _AssignmentTrackingScreenState extends State<AssignmentTrackingScreen> {
  // 3 main filters: Pending, In Progress, Completed
  String _selectedFilter = 'All';
  bool _filterOverdueOnly = false;

  List<TaskAssignment> _assignments = [];
  bool _isLoading = true;
  String? _errorMessage;

  final List<String> _filterTabs = ['All', 'Pending', 'In Progress', 'Completed'];

  @override
  void initState() {
    super.initState();
    _loadAssignments();
  }

  Future<void> _loadAssignments() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      String? backendStatus;
      if (_selectedFilter == 'Pending') {
        backendStatus = 'awaiting_confirmation';
      } else if (_selectedFilter == 'In Progress') {
        backendStatus = 'in_progress';
      } else if (_selectedFilter == 'Completed') {
        backendStatus = 'completed';
      }

      final list = await widget.syncService.fetchAssignments(
        status: backendStatus,
        overdue: _filterOverdueOnly ? true : null,
      );

      if (mounted) {
        setState(() {
          _assignments = list;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString();
          _isLoading = false;
        });
      }
    }
  }

  void _onFilterChanged(String tab) {
    if (_selectedFilter != tab) {
      setState(() {
        _selectedFilter = tab;
      });
      _loadAssignments();
    }
  }

  void _toggleOverdueFilter() {
    setState(() {
      _filterOverdueOnly = !_filterOverdueOnly;
    });
    _loadAssignments();
  }

  Color _getStatusColor(String status) {
    switch (status) {
      case 'completed':
        return AppConstants.successGreen;
      case 'in_progress':
      case 'accepted':
      case 'submitted':
        return AppConstants.pureBlack;
      case 'blocked':
      case 'declined':
        return AppConstants.dangerRed;
      case 'awaiting_confirmation':
      default:
        return AppConstants.warningOrange;
    }
  }

  @override
  Widget build(BuildContext context) {
    final dateFormat = DateFormat('MMM d, yyyy');

    return Scaffold(
      backgroundColor: AppConstants.pureWhite,
      appBar: AppBar(
        title: const Text('Assignment Tracking'),
      ),
      body: SafeArea(
        child: Column(
          children: [
            OfflineBanner(
              isOffline: widget.syncService.isOffline,
              onRetry: _loadAssignments,
            ),

            // Main Filter Tabs
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: AppConstants.borderLight)),
                color: AppConstants.pureWhite,
              ),
              child: Column(
                children: [
                  Row(
                    children: _filterTabs.map((tab) {
                      final isSelected = _selectedFilter == tab;
                      return Expanded(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 2),
                          child: InkWell(
                            onTap: () => _onFilterChanged(tab),
                            borderRadius: BorderRadius.circular(6),
                            child: Container(
                              padding: const EdgeInsets.symmetric(vertical: 8),
                              decoration: BoxDecoration(
                                color: isSelected ? AppConstants.pureBlack : Colors.transparent,
                                borderRadius: BorderRadius.circular(6),
                                border: Border.all(
                                  color: isSelected ? AppConstants.pureBlack : AppConstants.borderLight,
                                ),
                              ),
                              child: Center(
                                child: Text(
                                  tab,
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                    color: isSelected ? Colors.white : AppConstants.pureBlack,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                      );
                    }).toList(),
                  ),


                  const SizedBox(height: 8),
                  // Overdue filter toggle
                  Row(
                    children: [
                      InkWell(
                        onTap: _toggleOverdueFilter,
                        borderRadius: BorderRadius.circular(4),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: _filterOverdueOnly ? const Color(0xFFFEF2F2) : Colors.transparent,
                            borderRadius: BorderRadius.circular(4),
                            border: Border.all(
                              color: _filterOverdueOnly ? AppConstants.dangerRed : AppConstants.borderLight,
                            ),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(
                                Icons.warning_amber_rounded,
                                size: 14,
                                color: _filterOverdueOnly ? AppConstants.dangerRed : AppConstants.textSecondary,
                              ),
                              const SizedBox(width: 4),
                              Text(
                                'Overdue only',
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w500,
                                  color: _filterOverdueOnly ? AppConstants.dangerRed : AppConstants.textSecondary,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const Spacer(),
                      Text(
                        '${_assignments.length} assignments',
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

            Expanded(
              child: _isLoading
                  ? const LoadingView(message: 'Loading assignments...')
                  : _errorMessage != null && _assignments.isEmpty
                      ? ErrorView(message: _errorMessage!, onRetry: _loadAssignments)
                      : _assignments.isEmpty
                          ? const EmptyView(
                              message: 'No assignments found matching this filter.',
                              icon: Icons.assignment_turned_in_outlined,
                            )
                          : RefreshIndicator(
                              color: AppConstants.pureBlack,
                              onRefresh: _loadAssignments,
                              child: ListView.separated(
                                padding: const EdgeInsets.all(16),
                                itemCount: _assignments.length,
                                separatorBuilder: (_, _) => const SizedBox(height: 10),
                                itemBuilder: (context, index) {
                                  final a = _assignments[index];

                                  return CustomCard(
                                    padding: const EdgeInsets.all(14),
                                    onTap: () => widget.onSelectAssignment(a.id),
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        // Header: Member Name & Status Badge
                                        Row(
                                          children: [
                                            Expanded(
                                              child: Text(
                                                a.memberName ?? 'Member #${a.memberId}',
                                                style: const TextStyle(
                                                  fontSize: 14,
                                                  fontWeight: FontWeight.w600,
                                                  color: AppConstants.pureBlack,
                                                ),
                                              ),
                                            ),
                                            // Overdue label if overdue
                                            if (a.isOverdue) ...[
                                              Container(
                                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                                margin: const EdgeInsets.only(right: 6),
                                                decoration: BoxDecoration(
                                                  color: const Color(0xFFFEF2F2),
                                                  borderRadius: BorderRadius.circular(4),
                                                  border: Border.all(color: const Color(0xFFFCA5A5)),
                                                ),
                                                child: const Text(
                                                  'OVERDUE',
                                                  style: TextStyle(
                                                    color: AppConstants.dangerRed,
                                                    fontSize: 10,
                                                    fontWeight: FontWeight.w700,
                                                    letterSpacing: 0.5,
                                                  ),
                                                ),
                                              ),
                                            ],
                                            // Status Badge
                                            Container(
                                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                              decoration: BoxDecoration(
                                                color: _getStatusColor(a.status).withValues(alpha: 0.08),
                                                borderRadius: BorderRadius.circular(4),
                                                border: Border.all(
                                                  color: _getStatusColor(a.status).withValues(alpha: 0.3),
                                                ),
                                              ),
                                              child: Text(
                                                a.status.replaceAll('_', ' ').toUpperCase(),
                                                style: TextStyle(
                                                  color: _getStatusColor(a.status),
                                                  fontSize: 10,
                                                  fontWeight: FontWeight.w600,
                                                ),
                                              ),
                                            ),
                                          ],
                                        ),

                                        const SizedBox(height: 6),

                                        // Task Title
                                        Text(
                                          a.taskTitle ?? 'Task',
                                          style: const TextStyle(
                                            fontSize: 13,
                                            fontWeight: FontWeight.w500,
                                            color: AppConstants.pureBlack,
                                          ),
                                        ),
                                        const SizedBox(height: 8),

                                        // Event Name & Deadline
                                        Row(
                                          children: [
                                            Expanded(
                                              child: Row(
                                                children: [
                                                  const Icon(Icons.event_outlined, size: 12, color: AppConstants.textSecondary),
                                                  const SizedBox(width: 4),
                                                  Expanded(
                                                    child: Text(
                                                      a.eventName ?? 'Event',
                                                      style: const TextStyle(
                                                        fontSize: 11,
                                                        color: AppConstants.textSecondary,
                                                      ),
                                                      maxLines: 1,
                                                      overflow: TextOverflow.ellipsis,
                                                    ),
                                                  ),
                                                ],
                                              ),
                                            ),
                                            if (a.deadline != null) ...[
                                              Row(
                                                children: [
                                                  Icon(
                                                    Icons.schedule,
                                                    size: 12,
                                                    color: a.isOverdue ? AppConstants.dangerRed : AppConstants.textSecondary,
                                                  ),
                                                  const SizedBox(width: 4),
                                                  Text(
                                                    dateFormat.format(a.deadline!),
                                                    style: TextStyle(
                                                      fontSize: 11,
                                                      color: a.isOverdue ? AppConstants.dangerRed : AppConstants.textSecondary,
                                                      fontWeight: a.isOverdue ? FontWeight.w600 : FontWeight.w400,
                                                    ),
                                                  ),
                                                ],
                                              ),
                                            ],
                                          ],
                                        ),
                                      ],
                                    ),
                                  );
                                },
                              ),
                            ),
            ),
          ],
        ),
      ),
    );
  }
}
