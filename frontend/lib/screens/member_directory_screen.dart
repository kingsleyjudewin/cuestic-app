import 'package:flutter/material.dart';
import '../config/constants.dart';
import '../models/event.dart';
import '../models/team.dart';
import '../models/member.dart';
import '../services/sync_service.dart';
import '../widgets/offline_banner.dart';
import '../widgets/primary_button.dart';
import '../widgets/state_views.dart';

class MemberDirectoryScreen extends StatefulWidget {
  final Event event;
  final Team team;
  final SyncService syncService;
  final void Function(List<Member> selectedMembers) onAssignTask;

  const MemberDirectoryScreen({
    super.key,
    required this.event,
    required this.team,
    required this.syncService,
    required this.onAssignTask,
  });

  @override
  State<MemberDirectoryScreen> createState() => _MemberDirectoryScreenState();
}

class _MemberDirectoryScreenState extends State<MemberDirectoryScreen> {
  final _searchController = TextEditingController();

  List<Member> _allMembers = [];
  List<Member> _filteredMembers = [];
  final Set<int> _selectedMemberIds = {};

  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadMembers();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadMembers() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final members = await widget.syncService.fetchMembers(widget.team.id);
      if (mounted) {
        setState(() {
          _allMembers = members;
          _applyFilter(_searchController.text);
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

  void _applyFilter(String query) {
    if (query.trim().isEmpty) {
      _filteredMembers = List.from(_allMembers);
    } else {
      final q = query.trim().toLowerCase();
      _filteredMembers = _allMembers.where((m) {
        final matchesName = m.fullName.toLowerCase().contains(q);
        final matchesReg = m.registrationNumber != null && m.registrationNumber!.toLowerCase().contains(q);
        return matchesName || matchesReg;
      }).toList();
    }
  }

  void _onSearchChanged(String query) {
    setState(() {
      _applyFilter(query);
    });
  }

  void _toggleMemberSelection(Member member) {
    setState(() {
      if (_selectedMemberIds.contains(member.id)) {
        _selectedMemberIds.remove(member.id);
      } else {
        _selectedMemberIds.add(member.id);
      }
    });
  }

  void _toggleSelectAll() {
    setState(() {
      final allFilteredSelected = _filteredMembers.every((m) => _selectedMemberIds.contains(m.id));
      if (allFilteredSelected) {
        for (final m in _filteredMembers) {
          _selectedMemberIds.remove(m.id);
        }
      } else {
        for (final m in _filteredMembers) {
          _selectedMemberIds.add(m.id);
        }
      }
    });
  }

  void _handleAssignTask() {
    final selected = _allMembers.where((m) => _selectedMemberIds.contains(m.id)).toList();
    if (selected.isEmpty) return;
    widget.onAssignTask(selected);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppConstants.pureWhite,
      appBar: AppBar(
        title: Text(widget.team.name),
        actions: [
          if (_filteredMembers.isNotEmpty)
            TextButton(
              onPressed: _toggleSelectAll,
              child: Text(
                _filteredMembers.every((m) => _selectedMemberIds.contains(m.id))
                    ? 'Deselect All'
                    : 'Select All',
                style: const TextStyle(
                  color: AppConstants.pureBlack,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            OfflineBanner(
              isOffline: widget.syncService.isOffline,
              onRetry: _loadMembers,
            ),
            // Search field
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 10),
              child: TextField(
                controller: _searchController,
                onChanged: _onSearchChanged,
                decoration: InputDecoration(
                  hintText: 'Search by name or reg number...',
                  prefixIcon: const Icon(Icons.search, size: 18, color: AppConstants.textSecondary),
                  suffixIcon: _searchController.text.isNotEmpty
                      ? IconButton(
                          icon: const Icon(Icons.clear, size: 16),
                          onPressed: () {
                            _searchController.clear();
                            _onSearchChanged('');
                          },
                        )
                      : null,
                ),
              ),
            ),
            Expanded(
              child: _isLoading
                  ? const LoadingView(message: 'Loading members...')
                  : _errorMessage != null && _allMembers.isEmpty
                      ? ErrorView(
                          message: _errorMessage!,
                          onRetry: _loadMembers,
                        )
                      : _filteredMembers.isEmpty
                          ? EmptyView(
                              message: _searchController.text.isNotEmpty
                                  ? 'No members match "${_searchController.text}".'
                                  : 'No members found in ${widget.team.name}.',
                              icon: Icons.person_off_outlined,
                            )
                          : ListView.separated(
                              padding: const EdgeInsets.symmetric(vertical: 4),
                              itemCount: _filteredMembers.length,
                              separatorBuilder: (_, _) => const Divider(

                                height: 1,
                                thickness: 1,
                                indent: 56,
                              ),
                              itemBuilder: (context, index) {
                                final member = _filteredMembers[index];
                                final isSelected = _selectedMemberIds.contains(member.id);

                                return Material(
                                  color: isSelected ? const Color(0xFFF9FAFB) : AppConstants.pureWhite,
                                  child: InkWell(
                                    onTap: () => _toggleMemberSelection(member),
                                    child: Padding(
                                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                                      child: Row(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          // Checkbox / selection control
                                          Padding(
                                            padding: const EdgeInsets.only(top: 2, right: 12),
                                            child: SizedBox(
                                              width: 20,
                                              height: 20,
                                              child: Checkbox(
                                                value: isSelected,
                                                activeColor: AppConstants.pureBlack,
                                                shape: RoundedRectangleBorder(
                                                  borderRadius: BorderRadius.circular(4),
                                                ),
                                                side: const BorderSide(
                                                  color: AppConstants.borderLight,
                                                  width: 1.5,
                                                ),
                                                onChanged: (_) => _toggleMemberSelection(member),
                                              ),
                                            ),
                                          ),
                                          // Member Info
                                          Expanded(
                                            child: Column(
                                              crossAxisAlignment: CrossAxisAlignment.start,
                                              children: [
                                                Row(
                                                  children: [
                                                    Expanded(
                                                      child: Text(
                                                        member.fullName,
                                                        style: const TextStyle(
                                                          fontSize: 14,
                                                          fontWeight: FontWeight.w600,
                                                          color: AppConstants.pureBlack,
                                                        ),
                                                      ),
                                                    ),
                                                    if (member.registrationNumber != null)
                                                      Text(
                                                        member.registrationNumber!,
                                                        style: const TextStyle(
                                                          fontSize: 12,
                                                          color: AppConstants.textSecondary,
                                                          fontWeight: FontWeight.w500,
                                                        ),
                                                      ),
                                                  ],
                                                ),
                                                const SizedBox(height: 3),
                                                Text(
                                                  member.classAndSection,
                                                  style: const TextStyle(
                                                    fontSize: 12,
                                                    color: AppConstants.textSecondary,
                                                  ),
                                                ),
                                                if (member.phoneNumber.isNotEmpty) ...[
                                                  const SizedBox(height: 3),
                                                  Row(
                                                    children: [
                                                      const Icon(
                                                        Icons.phone_outlined,
                                                        size: 13,
                                                        color: AppConstants.textSecondary,
                                                      ),
                                                      const SizedBox(width: 4),
                                                      Text(
                                                        member.phoneNumber,
                                                        style: const TextStyle(
                                                          fontSize: 12,
                                                          color: AppConstants.textSecondary,
                                                        ),
                                                      ),
                                                    ],
                                                  ),
                                                ],
                                              ],
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                );
                              },
                            ),
            ),
            // Bottom Action Bar
            Container(
              padding: const EdgeInsets.all(16),
              decoration: const BoxDecoration(
                border: Border(top: BorderSide(color: AppConstants.borderLight, width: 1)),
                color: AppConstants.pureWhite,
              ),
              child: PrimaryButton(
                label: _selectedMemberIds.isEmpty
                    ? 'Assign Task'
                    : 'Assign Task (${_selectedMemberIds.length})',
                onPressed: _selectedMemberIds.isNotEmpty ? _handleAssignTask : null,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
