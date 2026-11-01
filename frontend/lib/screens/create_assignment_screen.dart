import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../config/constants.dart';
import '../models/event.dart';
import '../models/team.dart';
import '../models/member.dart';
import '../models/task.dart';
import '../services/api_client.dart';
import '../services/sync_service.dart';
import '../widgets/primary_button.dart';

class CreateAssignmentScreen extends StatefulWidget {
  final Event event;
  final Team team;
  final List<Member> selectedMembers;
  final SyncService syncService;
  final void Function(Task task) onTaskCreated;

  const CreateAssignmentScreen({
    super.key,
    required this.event,
    required this.team,
    required this.selectedMembers,
    required this.syncService,
    required this.onTaskCreated,
  });

  @override
  State<CreateAssignmentScreen> createState() => _CreateAssignmentScreenState();
}

class _CreateAssignmentScreenState extends State<CreateAssignmentScreen> {
  final _titleController = TextEditingController();
  final _descriptionController = TextEditingController();

  String _priority = 'medium';
  DateTime _deadline = DateTime.now().add(const Duration(days: 2, hours: 4));

  bool _isSubmitting = false;
  String? _titleError;
  String? _deadlineError;
  String? _generalError;

  final List<String> _priorities = ['low', 'medium', 'high', 'urgent'];

  @override
  void dispose() {
    _titleController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  Future<void> _pickDeadline() async {
    final now = DateTime.now();
    final pickedDate = await showDatePicker(
      context: context,
      initialDate: _deadline.isAfter(now) ? _deadline : now.add(const Duration(days: 1)),
      firstDate: now,
      lastDate: now.add(const Duration(days: 365)),
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: const ColorScheme.light(
              primary: AppConstants.pureBlack,
              onPrimary: AppConstants.pureWhite,
              surface: AppConstants.pureWhite,
              onSurface: AppConstants.pureBlack,
            ),
          ),
          child: child!,
        );
      },
    );

    if (pickedDate == null) return;

    if (!mounted) return;
    final pickedTime = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(_deadline),
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: const ColorScheme.light(
              primary: AppConstants.pureBlack,
              onPrimary: AppConstants.pureWhite,
              surface: AppConstants.pureWhite,
              onSurface: AppConstants.pureBlack,
            ),
          ),
          child: child!,
        );
      },
    );

    if (pickedTime == null) return;

    final newDeadline = DateTime(
      pickedDate.year,
      pickedDate.month,
      pickedDate.day,
      pickedTime.hour,
      pickedTime.minute,
    );

    setState(() {
      _deadline = newDeadline;
      if (_deadline.isBefore(DateTime.now())) {
        _deadlineError = 'Deadline must be in the future.';
      } else {
        _deadlineError = null;
      }
    });
  }

  Future<void> _handleSubmit() async {
    // Validate inputs
    setState(() {
      _titleError = null;
      _deadlineError = null;
      _generalError = null;
    });

    final title = _titleController.text.trim();
    bool hasError = false;

    if (title.isEmpty) {
      setState(() => _titleError = 'Task title is required.');
      hasError = true;
    } else if (title.length < 3) {
      setState(() => _titleError = 'Title must be at least 3 characters.');
      hasError = true;
    }

    if (_deadline.isBefore(DateTime.now())) {
      setState(() => _deadlineError = 'Task deadline must be in the future.');
      hasError = true;
    }

    if (widget.selectedMembers.isEmpty) {
      setState(() => _generalError = 'Please select at least one member.');
      hasError = true;
    }

    if (hasError) return;

    setState(() {
      _isSubmitting = true;
    });

    try {
      final task = await widget.syncService.createTask(
        eventId: widget.event.id,
        title: title,
        description: _descriptionController.text.trim().isNotEmpty ? _descriptionController.text.trim() : null,
        priority: _priority,
        deadline: _deadline,
        memberIds: widget.selectedMembers.map((m) => m.id).toList(),
      );

      if (mounted) {
        widget.onTaskCreated(task);
      }
    } on ApiException catch (e) {
      setState(() {
        if (e.details.containsKey('title')) {
          _titleError = (e.details['title'] as List).join(', ');
        }
        if (e.details.containsKey('deadline')) {
          _deadlineError = (e.details['deadline'] as List).join(', ');
        }
        _generalError = e.message;
      });
    } catch (e) {
      setState(() {
        _generalError = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final dateFormat = DateFormat('EEE, MMM d, yyyy • h:mm a');

    return Scaffold(
      backgroundColor: AppConstants.pureWhite,
      appBar: AppBar(
        title: const Text('Create Assignment'),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (_generalError != null) ...[
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFEF2F2),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: const Color(0xFFFCA5A5)),
                        ),
                        child: Text(
                          _generalError!,
                          style: const TextStyle(
                            color: AppConstants.dangerRed,
                            fontSize: 13,
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                    ],

                    // Selected Event & Team Summary Card
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF9FAFB),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: AppConstants.borderLight),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              const Icon(Icons.event_outlined, size: 14, color: AppConstants.textSecondary),
                              const SizedBox(width: 6),
                              Expanded(
                                child: Text(
                                  'Event: ${widget.event.name}',
                                  style: const TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                    color: AppConstants.pureBlack,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Row(
                            children: [
                              const Icon(Icons.group_outlined, size: 14, color: AppConstants.textSecondary),
                              const SizedBox(width: 6),
                              Expanded(
                                child: Text(
                                  'Team: ${widget.team.name}',
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: AppConstants.textSecondary,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),

                    const SizedBox(height: 18),

                    // Review Selected Members
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          'Selected Members',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: AppConstants.pureBlack,
                          ),
                        ),
                        Text(
                          '${widget.selectedMembers.length} ${widget.selectedMembers.length == 1 ? 'member' : 'members'}',
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppConstants.textSecondary,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: widget.selectedMembers.map((m) {
                        return Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                          decoration: BoxDecoration(
                            color: AppConstants.pureWhite,
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(color: AppConstants.borderLight),
                          ),
                          child: Text(
                            m.fullName,
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w500,
                              color: AppConstants.pureBlack,
                            ),
                          ),
                        );
                      }).toList(),
                    ),

                    const SizedBox(height: 22),

                    // Task Title
                    const Text(
                      'Task Title',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: AppConstants.pureBlack,
                      ),
                    ),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _titleController,
                      textInputAction: TextInputAction.next,
                      decoration: InputDecoration(
                        hintText: 'e.g. Prepare the event announcement poster',
                        errorText: _titleError,
                      ),
                    ),

                    const SizedBox(height: 18),

                    // Task Description
                    const Text(
                      'Task Description (Optional)',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: AppConstants.pureBlack,
                      ),
                    ),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _descriptionController,
                      maxLines: 3,
                      decoration: const InputDecoration(
                        hintText: 'Provide details, assets, requirements...',
                      ),
                    ),

                    const SizedBox(height: 18),

                    // Priority Selector
                    const Text(
                      'Priority',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: AppConstants.pureBlack,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: _priorities.map((p) {
                        final isSelected = _priority == p;
                        return Expanded(
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 3),
                            child: InkWell(
                              onTap: () => setState(() => _priority = p),
                              borderRadius: BorderRadius.circular(6),
                              child: Container(
                                padding: const EdgeInsets.symmetric(vertical: 9),
                                decoration: BoxDecoration(
                                  color: isSelected ? AppConstants.pureBlack : AppConstants.pureWhite,
                                  borderRadius: BorderRadius.circular(6),
                                  border: Border.all(
                                    color: isSelected ? AppConstants.pureBlack : AppConstants.borderLight,
                                  ),
                                ),
                                child: Center(
                                  child: Text(
                                    p.toUpperCase(),
                                    style: TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w600,
                                      color: isSelected ? AppConstants.pureWhite : AppConstants.pureBlack,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ),
                        );
                      }).toList(),
                    ),

                    const SizedBox(height: 20),

                    // Deadline Selector
                    const Text(
                      'Deadline',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: AppConstants.pureBlack,
                      ),
                    ),
                    const SizedBox(height: 6),
                    InkWell(
                      onTap: _pickDeadline,
                      borderRadius: BorderRadius.circular(8),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                        decoration: BoxDecoration(
                          color: AppConstants.pureWhite,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: _deadlineError != null ? AppConstants.dangerRed : AppConstants.borderLight,
                          ),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.calendar_today_outlined, size: 16, color: AppConstants.textSecondary),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(
                                dateFormat.format(_deadline),
                                style: const TextStyle(
                                  fontSize: 14,
                                  color: AppConstants.pureBlack,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ),
                            const Text(
                              'Change',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: AppConstants.pureBlack,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    if (_deadlineError != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        _deadlineError!,
                        style: const TextStyle(
                          color: AppConstants.dangerRed,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            // Bottom Action Button
            Container(
              padding: const EdgeInsets.all(16),
              decoration: const BoxDecoration(
                border: Border(top: BorderSide(color: AppConstants.borderLight, width: 1)),
                color: AppConstants.pureWhite,
              ),
              child: PrimaryButton(
                label: 'Create Assignment',
                isLoading: _isSubmitting,
                onPressed: _isSubmitting ? null : _handleSubmit,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
