import 'package:flutter/material.dart';
import '../config/constants.dart';
import '../models/event.dart';
import '../models/team.dart';
import '../services/sync_service.dart';
import '../widgets/offline_banner.dart';
import '../widgets/state_views.dart';

class SelectTeamScreen extends StatefulWidget {
  final Event event;
  final SyncService syncService;
  final void Function(Team team) onTeamSelected;

  const SelectTeamScreen({
    super.key,
    required this.event,
    required this.syncService,
    required this.onTeamSelected,
  });

  @override
  State<SelectTeamScreen> createState() => _SelectTeamScreenState();
}

class _SelectTeamScreenState extends State<SelectTeamScreen> {
  List<Team> _teams = [];
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadTeams();
  }

  Future<void> _loadTeams() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final teams = await widget.syncService.fetchTeams(widget.event.id);
      final List<Team> displayTeams = List.from(teams);

      // If backend currently has only 3 teams (Volunteering, Documentation, Media)
      // and no 4th team configured yet, ensure the 4th team row 'Registration' is displayed.
      // If the backend already configured a 4th team, reuse that name.
      if (displayTeams.length == 3) {
        displayTeams.add(
          Team(
            id: 0,
            name: 'Registration',
            slug: 'registration',
            description: 'Attendee registration & desk',
            memberCount: 0,
            isActive: true,
          ),
        );
      }

      if (mounted) {
        setState(() {
          _teams = displayTeams;
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppConstants.pureWhite,
      appBar: AppBar(
        title: const Text('Select Team'),
      ),
      body: SafeArea(
        child: Column(
          children: [
            OfflineBanner(
              isOffline: widget.syncService.isOffline,
              onRetry: _loadTeams,
            ),
            // Header showing selected event
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: AppConstants.borderLight)),
                color: AppConstants.pureWhite,
              ),
              child: Row(
                children: [
                  const Icon(Icons.event_outlined, size: 16, color: AppConstants.textSecondary),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      widget.event.name,
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: AppConstants.pureBlack,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: _isLoading
                  ? const LoadingView(message: 'Loading teams...')
                  : _errorMessage != null && _teams.isEmpty
                      ? ErrorView(
                          message: _errorMessage!,
                          onRetry: _loadTeams,
                        )
                      : _teams.isEmpty
                          ? const EmptyView(
                              message: 'No teams configured for this event.',
                              icon: Icons.group_outlined,
                            )
                          : ListView.separated(
                              padding: const EdgeInsets.symmetric(vertical: 8),
                              itemCount: _teams.length,
                              separatorBuilder: (_, _) => const Divider(

                                height: 1,
                                thickness: 1,
                                indent: 16,
                                endIndent: 16,
                              ),
                              itemBuilder: (context, index) {
                                final team = _teams[index];

                                return Material(
                                  color: AppConstants.pureWhite,
                                  child: InkWell(
                                    onTap: () => widget.onTeamSelected(team),
                                    child: Padding(
                                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 18),
                                      child: Row(
                                        children: [
                                          Expanded(
                                            child: Column(
                                              crossAxisAlignment: CrossAxisAlignment.start,
                                              children: [
                                                Text(
                                                  team.name,
                                                  style: const TextStyle(
                                                    fontSize: 15,
                                                    fontWeight: FontWeight.w600,
                                                    color: AppConstants.pureBlack,
                                                  ),
                                                ),
                                                const SizedBox(height: 3),
                                                Text(
                                                  '${team.memberCount} ${team.memberCount == 1 ? 'member' : 'members'}',
                                                  style: const TextStyle(
                                                    fontSize: 12,
                                                    color: AppConstants.textSecondary,
                                                  ),
                                                ),
                                              ],
                                            ),
                                          ),
                                          const Icon(
                                            Icons.chevron_right,
                                            size: 18,
                                            color: AppConstants.textSecondary,
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                );
                              },
                            ),
            ),
          ],
        ),
      ),
    );
  }
}
