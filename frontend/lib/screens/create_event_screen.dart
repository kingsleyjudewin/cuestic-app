import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../config/constants.dart';
import '../models/event.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';
import '../services/sync_service.dart';
import '../widgets/primary_button.dart';

class CreateEventScreen extends StatefulWidget {
  final SyncService syncService;
  final AuthService authService;
  final void Function(Event event)? onEventCreated;

  const CreateEventScreen({
    super.key,
    required this.syncService,
    required this.authService,
    this.onEventCreated,
  });

  @override
  State<CreateEventScreen> createState() => _CreateEventScreenState();
}

class _CreateEventScreenState extends State<CreateEventScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _locationController = TextEditingController();

  DateTime _startAt = DateTime.now().add(const Duration(days: 1, hours: 2));
  DateTime? _endAt;
  String _status = 'upcoming';

  bool _isSubmitting = false;
  String? _nameError;
  String? _startAtError;
  String? _endAtError;
  String? _locationError;
  String? _generalError;

  final List<String> _statuses = ['upcoming', 'draft', 'active'];

  @override
  void initState() {
    super.initState();
    // Default endAt to 6 hours after startAt
    _endAt = _startAt.add(const Duration(hours: 6));
  }

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    _locationController.dispose();
    super.dispose();
  }

  Future<DateTime?> _pickDateTime({
    required BuildContext context,
    required DateTime initialDateTime,
    required DateTime firstDate,
    required DateTime lastDate,
  }) async {
    final pickedDate = await showDatePicker(
      context: context,
      initialDate: initialDateTime.isBefore(firstDate) ? firstDate : initialDateTime,
      firstDate: firstDate,
      lastDate: lastDate,
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

    if (pickedDate == null) return null;

    if (!context.mounted) return null;
    final pickedTime = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(initialDateTime),
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

    if (pickedTime == null) return null;

    return DateTime(
      pickedDate.year,
      pickedDate.month,
      pickedDate.day,
      pickedTime.hour,
      pickedTime.minute,
    );
  }

  Future<void> _selectStartAt() async {
    final now = DateTime.now();
    final picked = await _pickDateTime(
      context: context,
      initialDateTime: _startAt,
      firstDate: now.subtract(const Duration(days: 30)),
      lastDate: now.add(const Duration(days: 365 * 2)),
    );

    if (picked != null) {
      setState(() {
        _startAt = picked;
        _startAtError = null;
        if (_endAt != null && _endAt!.isBefore(_startAt)) {
          _endAt = _startAt.add(const Duration(hours: 4));
          _endAtError = null;
        }
      });
    }
  }

  Future<void> _selectEndAt() async {
    final now = DateTime.now();
    final initial = _endAt ?? _startAt.add(const Duration(hours: 4));
    final picked = await _pickDateTime(
      context: context,
      initialDateTime: initial,
      firstDate: _startAt.subtract(const Duration(days: 1)),
      lastDate: now.add(const Duration(days: 365 * 2)),
    );

    if (picked != null) {
      setState(() {
        _endAt = picked;
        if (_endAt!.isBefore(_startAt)) {
          _endAtError = 'End date & time cannot be earlier than start date & time.';
        } else {
          _endAtError = null;
        }
      });
    }
  }

  void _clearEndAt() {
    setState(() {
      _endAt = null;
      _endAtError = null;
    });
  }

  bool _validateForm() {
    setState(() {
      _nameError = null;
      _startAtError = null;
      _endAtError = null;
      _locationError = null;
      _generalError = null;
    });

    final name = _nameController.text.trim();
    bool hasError = false;

    if (name.isEmpty) {
      setState(() => _nameError = 'Event name is required.');
      hasError = true;
    } else if (name.length < 2) {
      setState(() => _nameError = 'Event name must be at least 2 characters.');
      hasError = true;
    } else if (name.length > 150) {
      setState(() => _nameError = 'Event name must not exceed 150 characters.');
      hasError = true;
    }

    if (_locationController.text.trim().length > 200) {
      setState(() => _locationError = 'Venue must not exceed 200 characters.');
      hasError = true;
    }

    if (_endAt != null && _endAt!.isBefore(_startAt)) {
      setState(() => _endAtError = 'End date & time cannot be earlier than start date & time.');
      hasError = true;
    }

    return !hasError;
  }

  Future<void> _handleSubmit() async {
    // Prevent duplicate submissions
    if (_isSubmitting) return;

    if (!_validateForm()) return;

    setState(() {
      _isSubmitting = true;
    });

    final name = _nameController.text.trim();
    final description = _descriptionController.text.trim();
    final location = _locationController.text.trim();

    try {
      final event = await widget.syncService.createEvent(
        name: name,
        description: description.isNotEmpty ? description : null,
        startAt: _startAt,
        endAt: _endAt,
        location: location.isNotEmpty ? location : null,
        status: _status,
      );

      if (mounted) {
        if (widget.onEventCreated != null) {
          widget.onEventCreated!(event);
        } else {
          Navigator.of(context).pop(event);
        }
      }
    } on ApiException catch (e) {
      setState(() {
        if (e.details.containsKey('name')) {
          final val = e.details['name'];
          _nameError = val is List ? val.join(', ') : val.toString();
        }
        if (e.details.containsKey('start_at')) {
          final val = e.details['start_at'];
          _startAtError = val is List ? val.join(', ') : val.toString();
        }
        if (e.details.containsKey('end_at')) {
          final val = e.details['end_at'];
          _endAtError = val is List ? val.join(', ') : val.toString();
        }
        if (e.details.containsKey('location')) {
          final val = e.details['location'];
          _locationError = val is List ? val.join(', ') : val.toString();
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
        title: const Text('Create Event'),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                child: Form(
                  key: _formKey,
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
                          child: Row(
                            children: [
                              const Icon(Icons.error_outline, size: 18, color: AppConstants.dangerRed),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  _generalError!,
                                  style: const TextStyle(
                                    color: AppConstants.dangerRed,
                                    fontSize: 13,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                      ],

                      // Event Name
                      const Text(
                        'Event Name *',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: AppConstants.pureBlack,
                        ),
                      ),
                      const SizedBox(height: 6),
                      TextField(
                        controller: _nameController,
                        textInputAction: TextInputAction.next,
                        decoration: InputDecoration(
                          hintText: 'e.g. MAGNOVITE 2026',
                          errorText: _nameError,
                        ),
                        onChanged: (_) {
                          if (_nameError != null) {
                            setState(() => _nameError = null);
                          }
                        },
                      ),

                      const SizedBox(height: 18),

                      // Description
                      const Text(
                        'Description (Optional)',
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
                        textInputAction: TextInputAction.newline,
                        decoration: const InputDecoration(
                          hintText: 'Provide overview, goals, or schedule details...',
                        ),
                      ),

                      const SizedBox(height: 18),

                      // Start Date & Time
                      const Text(
                        'Start Date & Time *',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: AppConstants.pureBlack,
                        ),
                      ),
                      const SizedBox(height: 6),
                      InkWell(
                        onTap: _selectStartAt,
                        borderRadius: BorderRadius.circular(8),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                          decoration: BoxDecoration(
                            color: AppConstants.pureWhite,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: _startAtError != null ? AppConstants.dangerRed : AppConstants.borderLight,
                            ),
                          ),
                          child: Row(
                            children: [
                              const Icon(Icons.calendar_today_outlined, size: 16, color: AppConstants.textSecondary),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Text(
                                  dateFormat.format(_startAt),
                                  style: const TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w500,
                                    color: AppConstants.pureBlack,
                                  ),
                                ),
                              ),
                              const Icon(Icons.arrow_drop_down, size: 20, color: AppConstants.textSecondary),
                            ],
                          ),
                        ),
                      ),
                      if (_startAtError != null) ...[
                        const SizedBox(height: 4),
                        Padding(
                          padding: const EdgeInsets.only(left: 4),
                          child: Text(
                            _startAtError!,
                            style: const TextStyle(fontSize: 12, color: AppConstants.dangerRed),
                          ),
                        ),
                      ],

                      const SizedBox(height: 18),

                      // End Date & Time
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'End Date & Time (Optional)',
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                              color: AppConstants.pureBlack,
                            ),
                          ),
                          if (_endAt != null)
                            GestureDetector(
                              onTap: _clearEndAt,
                              child: const Text(
                                'Clear',
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w500,
                                  color: AppConstants.textSecondary,
                                ),
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      InkWell(
                        onTap: _selectEndAt,
                        borderRadius: BorderRadius.circular(8),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                          decoration: BoxDecoration(
                            color: AppConstants.pureWhite,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: _endAtError != null ? AppConstants.dangerRed : AppConstants.borderLight,
                            ),
                          ),
                          child: Row(
                            children: [
                              const Icon(Icons.event_available_outlined, size: 16, color: AppConstants.textSecondary),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Text(
                                  _endAt != null ? dateFormat.format(_endAt!) : 'Tap to set end date and time',
                                  style: TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w500,
                                    color: _endAt != null ? AppConstants.pureBlack : AppConstants.textSecondary,
                                  ),
                                ),
                              ),
                              const Icon(Icons.arrow_drop_down, size: 20, color: AppConstants.textSecondary),
                            ],
                          ),
                        ),
                      ),
                      if (_endAtError != null) ...[
                        const SizedBox(height: 4),
                        Padding(
                          padding: const EdgeInsets.only(left: 4),
                          child: Text(
                            _endAtError!,
                            style: const TextStyle(fontSize: 12, color: AppConstants.dangerRed),
                          ),
                        ),
                      ],

                      const SizedBox(height: 18),

                      // Venue / Location
                      const Text(
                        'Venue / Location (Optional)',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: AppConstants.pureBlack,
                        ),
                      ),
                      const SizedBox(height: 6),
                      TextField(
                        controller: _locationController,
                        textInputAction: TextInputAction.done,
                        decoration: InputDecoration(
                          hintText: 'e.g. Main Auditorium & Lab Complex',
                          errorText: _locationError,
                        ),
                        onChanged: (_) {
                          if (_locationError != null) {
                            setState(() => _locationError = null);
                          }
                        },
                      ),

                      const SizedBox(height: 18),

                      // Status Selector
                      const Text(
                        'Initial Status',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: AppConstants.pureBlack,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: _statuses.map((s) {
                          final isSelected = _status == s;
                          return Expanded(
                            child: Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 3),
                              child: InkWell(
                                onTap: () => setState(() => _status = s),
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
                                      s.toUpperCase(),
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

                      const SizedBox(height: 24),
                    ],
                  ),
                ),
              ),
            ),

            // Submit Button
            Container(
              padding: const EdgeInsets.all(16),
              decoration: const BoxDecoration(
                border: Border(top: BorderSide(color: AppConstants.borderLight, width: 1)),
                color: AppConstants.pureWhite,
              ),
              child: PrimaryButton(
                label: 'Create Event',
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
