import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../config/constants.dart';
import '../models/event.dart';
import '../services/auth_service.dart';
import '../services/sync_service.dart';
import '../widgets/custom_card.dart';
import '../widgets/offline_banner.dart';
import '../widgets/primary_button.dart';
import '../widgets/secondary_button.dart';
import '../widgets/state_views.dart';
import 'create_event_screen.dart';
import 'manage_members_screen.dart';
import 'documentation_portal_screen.dart';
import 'mc_dashboard_screen.dart';
import 'media_dashboard_screen.dart';
import 'faculty_dashboard_screen.dart';
import 'community_screen.dart';
import '../services/community_service.dart';
import '../services/research_service.dart';

class SelectEventScreen extends StatefulWidget {
  final SyncService syncService;
  final AuthService authService;
  final void Function(Event event) onEventSelected;
  final VoidCallback onOpenAssignments;
  final VoidCallback onLogout;

  const SelectEventScreen({
    super.key,
    required this.syncService,
    required this.authService,
    required this.onEventSelected,
    required this.onOpenAssignments,
    required this.onLogout,
  });

  @override
  State<SelectEventScreen> createState() => _SelectEventScreenState();
}

class _SelectEventScreenState extends State<SelectEventScreen> {
  List<Event> _events = [];
  Event? _selectedEvent;
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadEvents();
  }

  Future<void> _loadEvents() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final events = await widget.syncService.fetchEvents();
      final lastId = await widget.authService.getLastSelectedEventId();

      Event? defaultSelection;
      if (_selectedEvent != null && events.any((e) => e.id == _selectedEvent!.id)) {
        defaultSelection = events.firstWhere((e) => e.id == _selectedEvent!.id);
      } else if (lastId != null && events.any((e) => e.id == lastId)) {
        defaultSelection = events.firstWhere((e) => e.id == lastId);
      } else if (events.isNotEmpty) {
        defaultSelection = events.first;
      }

      if (mounted) {
        setState(() {
          _events = events;
          _selectedEvent = defaultSelection;
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

  void _handleContinue() {
    if (_selectedEvent == null) return;
    widget.authService.setLastSelectedEvent(_selectedEvent!.id, _selectedEvent!.name);
    widget.onEventSelected(_selectedEvent!);
  }

  Future<void> _openCreateEvent() async {
    final createdEvent = await Navigator.of(context).push<Event>(
      MaterialPageRoute(
        builder: (context) => CreateEventScreen(
          syncService: widget.syncService,
          authService: widget.authService,
          onEventCreated: (event) {
            Navigator.of(context).pop(event);
          },
        ),
      ),
    );

    if (createdEvent != null && mounted) {
      await _loadEvents();
      if (mounted) {
        setState(() {
          _selectedEvent = createdEvent;
        });
        widget.authService.setLastSelectedEvent(createdEvent.id, createdEvent.name);
        widget.onEventSelected(createdEvent);
      }
    }
  }

  Future<void> _openManageMembers() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => ManageMembersScreen(
          syncService: widget.syncService,
          authService: widget.authService,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final dateFormat = DateFormat('MMM d, yyyy');
    final canCreate = widget.authService.canCreateEvent;
    final canManageMembers = widget.authService.isAdmin;

    return Scaffold(
      backgroundColor: AppConstants.pureWhite,
      appBar: AppBar(
        title: const Text('Events'),
        actions: [
          if (canManageMembers)
            IconButton(
              key: const Key('btn_manage_members_appbar'),
              icon: const Icon(Icons.people_outline, size: 22),
              tooltip: 'Manage Members',
              onPressed: _openManageMembers,
            ),
          IconButton(
            key: const Key('btn_doc_portal_appbar'),
            icon: const Icon(Icons.description_outlined, size: 20),
            tooltip: 'Documentation Portal',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (context) => DocumentationPortalScreen(
                    authService: widget.authService,
                    syncService: widget.syncService,
                    onLogout: widget.onLogout,
                    onSwitchToAdmin: () => Navigator.of(context).pop(),
                  ),
                ),
              );
            },
          ),
          IconButton(
            key: const Key('btn_mc_portal_appbar'),
            icon: const Icon(Icons.mic_outlined, size: 20),
            tooltip: 'MC & Anchors Dashboard',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (context) => McDashboardScreen(
                    authService: widget.authService,
                    syncService: widget.syncService,
                    onLogout: widget.onLogout,
                    onSwitchToAdmin: () => Navigator.of(context).pop(),
                  ),
                ),
              );
            },
          ),
          IconButton(
            key: const Key('btn_media_portal_appbar'),
            icon: const Icon(Icons.photo_camera_outlined, size: 20),
            tooltip: 'Media Dashboard',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (context) => MediaDashboardScreen(
                    authService: widget.authService,
                    syncService: widget.syncService,
                    onLogout: widget.onLogout,
                  ),
                ),
              );
            },
          ),
          IconButton(
            key: const Key('btn_faculty_portal_appbar'),
            icon: const Icon(Icons.school_outlined, size: 20),
            tooltip: 'Faculty Research Portal',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (context) => FacultyDashboardScreen(
                    authService: widget.authService,
                    researchService: ResearchService(widget.authService),
                    onLogout: widget.onLogout,
                  ),
                ),
              );
            },
          ),
          if (canCreate)
            IconButton(
              key: const Key('btn_create_event_appbar'),
              icon: const Icon(Icons.add_circle_outline, size: 22),
              tooltip: 'Create Event',
              onPressed: _openCreateEvent,
            ),
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
            icon: const Icon(Icons.assignment_outlined, size: 20),
            tooltip: 'Assignments',
            onPressed: widget.onOpenAssignments,
          ),
          IconButton(
            icon: const Icon(Icons.logout_outlined, size: 20),
            tooltip: 'Sign Out',
            onPressed: widget.onLogout,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            OfflineBanner(
              isOffline: widget.syncService.isOffline,
              onRetry: _loadEvents,
            ),
            Expanded(
              child: _isLoading
                  ? const LoadingView(message: 'Loading events...')
                  : _errorMessage != null && _events.isEmpty
                      ? RefreshIndicator(
                          onRefresh: _loadEvents,
                          color: AppConstants.pureBlack,
                          backgroundColor: AppConstants.pureWhite,
                          child: SingleChildScrollView(
                            physics: const AlwaysScrollableScrollPhysics(),
                            child: SizedBox(
                              height: MediaQuery.of(context).size.height * 0.7,
                              child: ErrorView(
                                message: _errorMessage!,
                                onRetry: _loadEvents,
                              ),
                            ),
                          ),
                        )
                      : _events.isEmpty
                          ? RefreshIndicator(
                              onRefresh: _loadEvents,
                              color: AppConstants.pureBlack,
                              backgroundColor: AppConstants.pureWhite,
                              child: SingleChildScrollView(
                                physics: const AlwaysScrollableScrollPhysics(),
                                child: SizedBox(
                                  height: MediaQuery.of(context).size.height * 0.7,
                                  child: EmptyView(
                                    message: 'No events found in this club.',
                                    icon: Icons.event_busy_outlined,
                                    actionLabel: canCreate ? 'Create Event' : null,
                                    onAction: canCreate ? _openCreateEvent : null,
                                  ),
                                ),
                              ),
                            )
                          : RefreshIndicator(
                              onRefresh: _loadEvents,
                              color: AppConstants.pureBlack,
                              backgroundColor: AppConstants.pureWhite,
                              child: SingleChildScrollView(
                                physics: const AlwaysScrollableScrollPhysics(),
                                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    if (canManageMembers) ...[
                                      SecondaryButton(
                                        key: const Key('btn_manage_members_screen'),
                                        label: 'Manage Members',
                                        icon: Icons.people_outline,
                                        onPressed: _openManageMembers,
                                        height: 44,
                                      ),
                                      const SizedBox(height: 10),
                                    ],
                                    SecondaryButton(
                                      key: const Key('btn_open_community_button'),
                                      label: 'Discord Community',
                                      icon: Icons.forum_outlined,
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
                                      height: 44,
                                    ),
                                    const SizedBox(height: 10),
                                    if (canCreate) ...[
                                      SecondaryButton(
                                        label: 'Create Event',
                                        icon: Icons.add,
                                        onPressed: _openCreateEvent,
                                        height: 44,
                                      ),
                                      const SizedBox(height: 16),
                                    ],

                                    const Text(
                                      'Select Event',
                                      style: TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.w600,
                                        color: AppConstants.pureBlack,
                                      ),
                                    ),
                                    const SizedBox(height: 10),

                                    // Dropdown Selector
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 12),
                                      decoration: BoxDecoration(
                                        borderRadius: BorderRadius.circular(8),
                                        border: Border.all(color: AppConstants.borderLight),
                                        color: AppConstants.pureWhite,
                                      ),
                                      child: DropdownButtonHideUnderline(
                                        child: DropdownButton<int>(
                                          value: _selectedEvent?.id,
                                          isExpanded: true,
                                          icon: const Icon(Icons.keyboard_arrow_down, size: 18),
                                          items: _events.map((e) {
                                            return DropdownMenuItem<int>(
                                              value: e.id,
                                              child: Text(
                                                e.name,
                                                style: const TextStyle(
                                                  fontSize: 14,
                                                  fontWeight: FontWeight.w500,
                                                  color: AppConstants.pureBlack,
                                                ),
                                              ),
                                            );
                                          }).toList(),
                                          onChanged: (id) {
                                            if (id != null) {
                                              setState(() {
                                                _selectedEvent = _events.firstWhere((e) => e.id == id);
                                              });
                                            }
                                          },
                                        ),
                                      ),
                                    ),

                                    const SizedBox(height: 20),
                                    const Text(
                                      'Available Events',
                                      style: TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.w600,
                                        color: AppConstants.pureBlack,
                                      ),
                                    ),
                                    const SizedBox(height: 10),

                                    // List of events
                                    ListView.separated(
                                      shrinkWrap: true,
                                      physics: const NeverScrollableScrollPhysics(),
                                      itemCount: _events.length,
                                      separatorBuilder: (_, _) => const SizedBox(height: 10),
                                      itemBuilder: (context, index) {
                                        final event = _events[index];
                                        final isSelected = _selectedEvent?.id == event.id;

                                        return CustomCard(
                                          padding: const EdgeInsets.all(14),
                                          borderColor: isSelected ? AppConstants.pureBlack : AppConstants.borderLight,
                                          onTap: () {
                                            setState(() {
                                              _selectedEvent = event;
                                            });
                                          },
                                          child: Row(
                                            children: [
                                              Icon(
                                                isSelected ? Icons.radio_button_checked : Icons.radio_button_off,
                                                size: 18,
                                                color: isSelected ? AppConstants.pureBlack : AppConstants.textSecondary,
                                              ),
                                              const SizedBox(width: 12),
                                              Expanded(
                                                child: Column(
                                                  crossAxisAlignment: CrossAxisAlignment.start,
                                                  children: [
                                                    Text(
                                                      event.name,
                                                      style: const TextStyle(
                                                        fontSize: 14,
                                                        fontWeight: FontWeight.w600,
                                                        color: AppConstants.pureBlack,
                                                      ),
                                                    ),
                                                    const SizedBox(height: 3),
                                                    Text(
                                                      '${dateFormat.format(event.startAt)} • ${event.status.toUpperCase()}'
                                                      '${event.location != null && event.location!.isNotEmpty ? ' • ${event.location}' : ''}',
                                                      style: const TextStyle(
                                                        fontSize: 12,
                                                        color: AppConstants.textSecondary,
                                                      ),
                                                    ),
                                                  ],
                                                ),
                                              ),
                                            ],
                                          ),
                                        );
                                      },
                                    ),
                                  ],
                                ),
                              ),
                            ),
            ),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: const BoxDecoration(
                border: Border(top: BorderSide(color: AppConstants.borderLight, width: 1)),
                color: AppConstants.pureWhite,
              ),
              child: PrimaryButton(
                label: 'Continue',
                onPressed: _selectedEvent != null ? _handleContinue : null,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
