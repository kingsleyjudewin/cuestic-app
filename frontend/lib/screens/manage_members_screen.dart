import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';
import '../config/constants.dart';
import '../models/member.dart';
import '../models/team.dart';
import '../services/auth_service.dart';
import '../services/sync_service.dart';
import '../widgets/custom_card.dart';
import '../widgets/offline_banner.dart';
import '../widgets/primary_button.dart';
import '../widgets/state_views.dart';
import 'create_member_account_screen.dart';

class ManageMembersScreen extends StatefulWidget {
  final SyncService syncService;
  final AuthService authService;

  const ManageMembersScreen({
    super.key,
    required this.syncService,
    required this.authService,
  });

  @override
  State<ManageMembersScreen> createState() => _ManageMembersScreenState();
}

class _ManageMembersScreenState extends State<ManageMembersScreen> {
  final TextEditingController _searchController = TextEditingController();

  List<Team> _teams = [];
  List<Member> _allMembers = [];
  List<Member> _members = [];
  int? _selectedTeamId; // null = "All"
  bool _isLoading = true;
  String? _errorMessage;

  Timer? _debounceTimer;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  @override
  void dispose() {
    _debounceTimer?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  void _applyFilter() {
    if (_allMembers.isEmpty) return;
    final query = _searchController.text.trim().toLowerCase();
    setState(() {
      _members = _allMembers.where((m) {
        if (_selectedTeamId != null && m.teamId != _selectedTeamId) return false;
        if (query.isNotEmpty) {
          final queryNorm = query.replaceAll('e', 'i');
          final nameNorm = m.fullName.toLowerCase().replaceAll('e', 'i');
          final matchesName = m.fullName.toLowerCase().contains(query) || nameNorm.contains(queryNorm);
          final matchesReg = m.registrationNumber?.toLowerCase().contains(query) ?? false;
          final matchesUser = (m.linkedUsername?.toLowerCase().contains(query) ?? false) ||
              (m.linkedUsername?.toLowerCase().replaceAll('e', 'i').contains(queryNorm) ?? false);
          final matchesPhone = m.phoneNumber.toLowerCase().contains(query);
          if (!matchesName && !matchesReg && !matchesUser && !matchesPhone) return false;
        }
        return true;
      }).toList();
    });
  }

  Future<void> _loadData() async {
    // Render cached teams immediately if available for instant UI feedback
    final cachedTeams = await widget.syncService.storageService.getCachedTeams();
    if (cachedTeams.isNotEmpty && mounted) {
      setState(() {
        _teams = cachedTeams;
      });
    }

    setState(() {
      _isLoading = _members.isEmpty;
      _errorMessage = null;
    });

    try {
      final results = await Future.wait([
        widget.syncService.fetchClubTeams(),
        widget.syncService.fetchClubMembers(
          teamId: _selectedTeamId,
          search: _searchController.text.trim().isEmpty ? null : _searchController.text.trim(),
          isActive: null,
        ),
      ]);

      if (mounted) {
        setState(() {
          _teams = results[0] as List<Team>;
          _allMembers = results[1] as List<Member>;
          _members = _allMembers;
          _isLoading = false;
        });
        _applyFilter();
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

  Future<void> _refreshMembers() async {
    try {
      final members = await widget.syncService.fetchClubMembers(
        teamId: _selectedTeamId,
        search: _searchController.text.trim().isEmpty ? null : _searchController.text.trim(),
        isActive: null,
      );
      if (mounted) {
        setState(() {
          if (_selectedTeamId == null && _searchController.text.trim().isEmpty) {
            _allMembers = members;
          }
          _members = members;
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to refresh: ${e.toString()}')),
        );
      }
    }
  }

  void _onTeamSelected(int? teamId) {
    setState(() {
      _selectedTeamId = teamId;
    });
    _applyFilter();
    _refreshMembers();
  }

  void _onSearchChanged(String _) {
    _applyFilter();
    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(milliseconds: 300), () {
      if (mounted) {
        _refreshMembers();
      }
    });
  }

  Future<void> _openCreateMemberAccount({Member? prefill}) async {
    final created = await Navigator.of(context).push<Member>(
      MaterialPageRoute(
        builder: (context) => CreateMemberAccountScreen(
          syncService: widget.syncService,
          authService: widget.authService,
          initialTeamId: _selectedTeamId,
          prefillMember: prefill,
        ),
      ),
    );

    if (created != null && mounted) {
      _refreshMembers();
    }
  }

  Future<void> _showResetPasswordDialog(Member member) async {
    final passwordController = TextEditingController();
    bool obscure = true;
    bool isResetting = false;
    String? errorText;

    // Generate initial suggested password
    const chars = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#%*';
    final random = Random.secure();
    final pwd = List.generate(8, (_) => chars[random.nextInt(chars.length)]).join();
    passwordController.text = 'Reset!$pwd';

    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              backgroundColor: AppConstants.pureWhite,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              title: Text(
                'Reset Password for ${member.fullName}',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: AppConstants.pureBlack,
                ),
              ),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Account: @${member.linkedUsername ?? member.fullName}',
                    style: const TextStyle(fontSize: 13, color: AppConstants.textSecondary),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Enter a new temporary password. Active sessions for this account will be invalidated immediately.',
                    style: TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    key: const Key('input_reset_new_password'),
                    controller: passwordController,
                    obscureText: obscure,
                    decoration: InputDecoration(
                      labelText: 'New Password',
                      errorText: errorText,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: const BorderSide(color: AppConstants.borderLight),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: const BorderSide(color: AppConstants.pureBlack, width: 1.5),
                      ),
                      suffixIcon: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          IconButton(
                            icon: Icon(
                              obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                              size: 18,
                            ),
                            onPressed: () {
                              setDialogState(() => obscure = !obscure);
                            },
                          ),
                          IconButton(
                            icon: const Icon(Icons.autorenew, size: 18),
                            tooltip: 'Generate Password',
                            onPressed: () {
                              final p = List.generate(8, (_) => chars[random.nextInt(chars.length)]).join();
                              setDialogState(() => passwordController.text = 'Reset!$p');
                            },
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: isResetting ? null : () => Navigator.of(ctx).pop(),
                  child: const Text('Cancel', style: TextStyle(color: AppConstants.textSecondary)),
                ),
                TextButton(
                  key: const Key('btn_confirm_reset_password'),
                  onPressed: isResetting
                      ? null
                      : () async {
                          final newPwd = passwordController.text.trim();
                          if (newPwd.isEmpty) {
                            setDialogState(() => errorText = 'Password cannot be empty.');
                            return;
                          }

                          setDialogState(() {
                            isResetting = true;
                            errorText = null;
                          });

                          try {
                            await widget.syncService.resetMemberPassword(member.id, newPwd);
                            if (ctx.mounted) {
                              Navigator.of(ctx).pop();
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text('Password reset successfully for ${member.fullName}.'),
                                  backgroundColor: AppConstants.pureBlack,
                                ),
                              );
                            }
                          } catch (e) {
                            if (ctx.mounted) {
                              setDialogState(() {
                                isResetting = false;
                                errorText = e.toString().replaceFirst('Exception: ', '');
                              });
                            }
                          }
                        },
                  child: isResetting
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text(
                          'Reset Password',
                          style: TextStyle(
                            color: AppConstants.pureBlack,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  InputDecoration _buildInputDecoration({String? hint}) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(fontSize: 13, color: AppConstants.textSecondary),
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: AppConstants.borderLight),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: AppConstants.pureBlack, width: 1.5),
      ),
    );
  }

  Future<void> _showEditMemberDialog(Member member) async {
    final nameController = TextEditingController(text: member.fullName);
    final regNoController = TextEditingController(text: member.registrationNumber ?? '');
    final phoneController = TextEditingController(text: member.phoneNumber);
    final classController = TextEditingController(text: member.className);
    final sectionController = TextEditingController(text: member.section ?? '');
    final emailController = TextEditingController(text: member.effectiveEmail ?? '');

    int selectedTeamId = member.teamId;
    String selectedRole = member.linkedRole ?? 'member';
    bool whatsappOptIn = member.whatsappOptIn;

    bool isSaving = false;
    String? errorMessage;

    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              backgroundColor: AppConstants.pureWhite,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              title: Row(
                children: [
                  const Icon(Icons.edit_outlined, size: 20, color: AppConstants.pureBlack),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Edit Details: ${member.fullName}',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: AppConstants.pureBlack,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
              content: SizedBox(
                width: 460,
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (errorMessage != null) ...[
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: Colors.red.shade50,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: Colors.red.shade200),
                          ),
                          child: Text(
                            errorMessage!,
                            style: TextStyle(color: Colors.red.shade800, fontSize: 12),
                          ),
                        ),
                        const SizedBox(height: 12),
                      ],

                      // Full Name
                      const Text('Full Name *', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 4),
                      TextField(
                        controller: nameController,
                        decoration: _buildInputDecoration(hint: 'e.g. John Doe'),
                      ),
                      const SizedBox(height: 12),

                      // Registration Number
                      const Text('Registration Number / Student ID', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 4),
                      TextField(
                        controller: regNoController,
                        decoration: _buildInputDecoration(hint: 'e.g. 2460635 or REG2026-101'),
                      ),
                      const SizedBox(height: 12),

                      // Phone Number
                      const Text('Phone Number *', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 4),
                      TextField(
                        controller: phoneController,
                        decoration: _buildInputDecoration(hint: 'e.g. +91 98765 43210'),
                      ),
                      const SizedBox(height: 12),

                      // Class and Section Row
                      Row(
                        children: [
                          Expanded(
                            flex: 2,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text('Class / Year *', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                                const SizedBox(height: 4),
                                TextField(
                                  controller: classController,
                                  decoration: _buildInputDecoration(hint: 'e.g. 6BTEC'),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            flex: 1,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text('Section', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                                const SizedBox(height: 4),
                                TextField(
                                  controller: sectionController,
                                  decoration: _buildInputDecoration(hint: 'e.g. A'),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),

                      // Team Selection
                      const Text('Assigned Team *', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 4),
                      DropdownButtonFormField<int>(
                        initialValue: selectedTeamId,
                        decoration: _buildInputDecoration(),
                        items: _teams.map((t) {
                          return DropdownMenuItem<int>(
                            value: t.id,
                            child: Text(t.name, style: const TextStyle(fontSize: 13)),
                          );
                        }).toList(),
                        onChanged: (val) {
                          if (val != null) {
                            setDialogState(() => selectedTeamId = val);
                          }
                        },
                      ),
                      const SizedBox(height: 12),

                      // Email ID field for all members
                      const Text('Email ID', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 4),
                      TextField(
                        controller: emailController,
                        keyboardType: TextInputType.emailAddress,
                        decoration: _buildInputDecoration(hint: 'e.g. member@cuestic.edu or name@gmail.com'),
                      ),
                      const SizedBox(height: 12),

                      // Linked Account fields if hasAccount
                      if (member.hasAccount) ...[
                        const Text('Role (President Managed)', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                        const SizedBox(height: 4),
                        DropdownButtonFormField<String>(
                          initialValue: selectedRole,
                          decoration: _buildInputDecoration(),
                          items: const [
                            DropdownMenuItem(value: 'member', child: Text('Member / Volunteer', style: TextStyle(fontSize: 13))),
                            DropdownMenuItem(value: 'team_leader', child: Text('Team Leader', style: TextStyle(fontSize: 13))),
                            DropdownMenuItem(value: 'admin', child: Text('Administrator', style: TextStyle(fontSize: 13))),
                            DropdownMenuItem(value: 'president', child: Text('President', style: TextStyle(fontSize: 13))),
                          ],
                          onChanged: (val) {
                            if (val != null) {
                              setDialogState(() => selectedRole = val);
                            }
                          },
                        ),
                        const SizedBox(height: 10),

                        // Direct Change Password button
                        OutlinedButton.icon(
                          key: const Key('btn_edit_dialog_reset_password'),
                          icon: const Icon(Icons.lock_reset, size: 16),
                          label: const Text('Change Password (No Old Password Needed)', style: TextStyle(fontSize: 12)),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: AppConstants.pureBlack,
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                            side: const BorderSide(color: AppConstants.borderLight),
                          ),
                          onPressed: () {
                            Navigator.of(ctx).pop();
                            _showResetPasswordDialog(member);
                          },
                        ),
                        const SizedBox(height: 12),
                      ] else ...[
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: AppConstants.backgroundLight,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: AppConstants.borderLight),
                          ),
                          child: Row(
                            children: [
                              const Icon(Icons.info_outline, size: 16, color: AppConstants.textSecondary),
                              const SizedBox(width: 8),
                              const Expanded(
                                child: Text(
                                  'No login account linked yet.',
                                  style: TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                                ),
                              ),
                              TextButton(
                                onPressed: () {
                                  Navigator.of(ctx).pop();
                                  _openCreateMemberAccount(prefill: member);
                                },
                                child: const Text('Create Account', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 12),
                      ],

                      // WhatsApp Opt-in
                      CheckboxListTile(
                        value: whatsappOptIn,
                        contentPadding: EdgeInsets.zero,
                        title: const Text('WhatsApp Notifications Opt-in', style: TextStyle(fontSize: 13)),
                        controlAffinity: ListTileControlAffinity.leading,
                        activeColor: AppConstants.pureBlack,
                        onChanged: (val) {
                          setDialogState(() => whatsappOptIn = val ?? true);
                        },
                      ),
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: isSaving ? null : () => Navigator.of(ctx).pop(),
                  child: const Text('Cancel', style: TextStyle(color: AppConstants.textSecondary)),
                ),
                TextButton(
                  key: const Key('btn_confirm_edit_member'),
                  onPressed: isSaving
                      ? null
                      : () async {
                          final fullName = nameController.text.trim();
                          final phone = phoneController.text.trim();
                          final className = classController.text.trim();

                          if (fullName.length < 2) {
                            setDialogState(() => errorMessage = 'Full Name must be at least 2 characters.');
                            return;
                          }
                          if (phone.isEmpty) {
                            setDialogState(() => errorMessage = 'Phone number is required.');
                            return;
                          }
                          if (className.isEmpty) {
                            setDialogState(() => errorMessage = 'Class is required.');
                            return;
                          }

                          setDialogState(() {
                            isSaving = true;
                            errorMessage = null;
                          });

                          try {
                            await widget.syncService.updateMemberDetails(
                              memberId: member.id,
                              fullName: fullName,
                              registrationNumber: regNoController.text,
                              phoneNumber: phone,
                              className: className,
                              section: sectionController.text,
                              teamId: selectedTeamId,
                              email: emailController.text.trim(),
                              role: member.hasAccount ? selectedRole : null,
                              whatsappOptIn: whatsappOptIn,
                            );

                            if (ctx.mounted) {
                              Navigator.of(ctx).pop();
                              _refreshMembers();
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text('Details updated for $fullName.'),
                                  backgroundColor: AppConstants.pureBlack,
                                ),
                              );
                            }
                          } catch (e) {
                            setDialogState(() {
                              isSaving = false;
                              errorMessage = e.toString().replaceFirst('Exception: ', '');
                            });
                          }
                        },
                  child: isSaving
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text(
                          'Save Changes',
                          style: TextStyle(
                            color: AppConstants.pureBlack,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> _toggleActiveStatus(Member member) async {
    final nextStatus = !member.isActive;
    final actionName = nextStatus ? 'activate' : 'deactivate';

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppConstants.pureWhite,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        title: Text(
          '${nextStatus ? "Activate" : "Deactivate"} ${member.fullName}?',
          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
        ),
        content: Text(
          nextStatus
              ? 'Activating will re-enable the member and their linked login account.'
              : 'Deactivating will disable login access and revoke active sessions for this member while preserving their task assignment history.',
          style: const TextStyle(fontSize: 13, color: AppConstants.textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel', style: TextStyle(color: AppConstants.textSecondary)),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(
              nextStatus ? 'Activate' : 'Deactivate',
              style: TextStyle(
                color: nextStatus ? AppConstants.pureBlack : Colors.red,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      try {
        await widget.syncService.toggleMemberActiveStatus(member.id, nextStatus);
        _refreshMembers();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('${member.fullName} has been ${actionName}d.'),
              backgroundColor: AppConstants.pureBlack,
            ),
          );
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Failed to update status: ${e.toString()}')),
          );
        }
      }
    }
  }

  Widget _buildTeamChips() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          ChoiceChip(
            label: const Text('All Teams'),
            selected: _selectedTeamId == null,
            selectedColor: AppConstants.pureBlack,
            backgroundColor: AppConstants.pureWhite,
            labelStyle: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: _selectedTeamId == null ? AppConstants.pureWhite : AppConstants.pureBlack,
            ),
            side: const BorderSide(color: AppConstants.borderLight),
            onSelected: (selected) {
              if (selected) _onTeamSelected(null);
            },
          ),
          const SizedBox(width: 8),
          ..._teams.map((t) {
            final isSelected = _selectedTeamId == t.id;
            return Padding(
              padding: const EdgeInsets.only(right: 8),
              child: ChoiceChip(
                label: Text(t.name),
                selected: isSelected,
                selectedColor: AppConstants.pureBlack,
                backgroundColor: AppConstants.pureWhite,
                labelStyle: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: isSelected ? AppConstants.pureWhite : AppConstants.pureBlack,
                ),
                side: const BorderSide(color: AppConstants.borderLight),
                onSelected: (selected) {
                  if (selected) _onTeamSelected(t.id);
                },
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: TextField(
        controller: _searchController,
        onChanged: _onSearchChanged,
        decoration: InputDecoration(
          hintText: 'Search members by name, reg no, username...',
          hintStyle: const TextStyle(fontSize: 13, color: AppConstants.textSecondary),
          prefixIcon: const Icon(Icons.search, size: 20, color: AppConstants.textSecondary),
          suffixIcon: _searchController.text.isNotEmpty
              ? IconButton(
                  icon: const Icon(Icons.clear, size: 18),
                  onPressed: () {
                    _searchController.clear();
                    _refreshMembers();
                  },
                )
              : null,
          filled: true,
          fillColor: AppConstants.pureWhite,
          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: const BorderSide(color: AppConstants.borderLight),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: const BorderSide(color: AppConstants.pureBlack, width: 1.5),
          ),
        ),
      ),
    );
  }

  Widget _buildMemberCard(Member member) {
    final teamName = member.teamName ??
        _teams.firstWhere((t) => t.id == member.teamId, orElse: () => Team(id: 0, name: 'Team', slug: '')).name;

    final isLeader = member.linkedRole == 'team_leader';
    final isAdminRole = member.linkedRole == 'admin';
    final isPresidentRole = member.linkedRole == 'president';
    final hasAccount = member.hasAccount;
    final isAccountActive = member.isActive && (member.linkedUserIsActive ?? true);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: CustomCard(
        padding: const EdgeInsets.all(14),
        onTap: () => _showEditMemberDialog(member),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CircleAvatar(
                  radius: 20,
                  backgroundColor: isPresidentRole
                      ? Colors.indigo.shade900
                      : isAdminRole
                          ? Colors.blueGrey.shade800
                          : isLeader
                              ? AppConstants.pureBlack
                              : AppConstants.backgroundLight,
                  child: Text(
                    member.fullName.isNotEmpty ? member.fullName.substring(0, 1).toUpperCase() : 'M',
                    style: TextStyle(
                      color: (isPresidentRole || isAdminRole || isLeader)
                          ? AppConstants.pureWhite
                          : AppConstants.pureBlack,
                      fontWeight: FontWeight.bold,
                      fontSize: 15,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              member.fullName,
                              style: const TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.bold,
                                color: AppConstants.pureBlack,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          if (isPresidentRole) ...[
                            const SizedBox(width: 6),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: Colors.indigo.shade900,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: const Text(
                                'PRESIDENT',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 0.5,
                                ),
                              ),
                            ),
                          ] else if (isAdminRole) ...[
                            const SizedBox(width: 6),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: Colors.blueGrey.shade900,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: const Text(
                                'ADMIN',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 0.5,
                                ),
                              ),
                            ),
                          ] else if (isLeader) ...[
                            const SizedBox(width: 6),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: AppConstants.pureBlack,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: const Text(
                                'LEADER',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 0.5,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '${member.classAndSection}${member.registrationNumber != null ? " • ${member.registrationNumber}" : ""}',
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppConstants.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.edit_outlined, size: 19, color: AppConstants.textSecondary),
                  tooltip: 'Edit Member Details',
                  splashRadius: 18,
                  onPressed: () => _showEditMemberDialog(member),
                ),
                PopupMenuButton<String>(
                  icon: const Icon(Icons.more_vert, size: 20, color: AppConstants.textSecondary),
                  onSelected: (val) {
                    Future.microtask(() {
                      if (!mounted) return;
                      if (val == 'edit_details') {
                        _showEditMemberDialog(member);
                      } else if (val == 'reset_password') {
                        _showResetPasswordDialog(member);
                      } else if (val == 'toggle_active') {
                        _toggleActiveStatus(member);
                      } else if (val == 'create_account') {
                        _openCreateMemberAccount(prefill: member);
                      }
                    });
                  },
                  itemBuilder: (context) => [
                    const PopupMenuItem(
                      value: 'edit_details',
                      child: Row(
                        children: [
                          Icon(Icons.edit_outlined, size: 18),
                          SizedBox(width: 8),
                          Expanded(child: Text('Edit Member Details')),
                        ],
                      ),
                    ),
                    if (hasAccount) ...[
                      const PopupMenuItem(
                        value: 'reset_password',
                        child: Row(
                          children: [
                            Icon(Icons.lock_reset, size: 18),
                            SizedBox(width: 8),
                            Expanded(child: Text('Reset Password')),
                          ],
                        ),
                      ),
                      PopupMenuItem(
                        value: 'toggle_active',
                        child: Row(
                          children: [
                            Icon(
                              member.isActive ? Icons.person_off_outlined : Icons.person_outline,
                              size: 18,
                              color: member.isActive ? Colors.red : Colors.green,
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                member.isActive ? 'Deactivate Member' : 'Activate Member',
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ] else ...[
                      const PopupMenuItem(
                        value: 'create_account',
                        child: Row(
                          children: [
                            Icon(Icons.person_add_alt_1, size: 18),
                            SizedBox(width: 8),
                            Expanded(child: Text('Create Login Account')),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              ],
            ),
            const SizedBox(height: 10),
            const Divider(height: 1, color: AppConstants.borderLight),
            const SizedBox(height: 10),

            // Badges row: Team + Account Status
            Wrap(
              spacing: 8,
              runSpacing: 6,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                // Team Badge
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppConstants.backgroundLight,
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: AppConstants.borderLight),
                  ),
                  child: Text(
                    teamName,
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: AppConstants.pureBlack,
                    ),
                  ),
                ),

                // Account Badge
                if (hasAccount) ...[
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: isAccountActive ? Colors.black : Colors.red.shade50,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          isAccountActive ? Icons.check_circle_outline : Icons.block,
                          size: 12,
                          color: isAccountActive ? Colors.white : Colors.red.shade700,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          isAccountActive
                              ? '@${member.linkedUsername ?? "account"}'
                              : 'Deactivated',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: isAccountActive ? Colors.white : Colors.red.shade800,
                          ),
                        ),
                      ],
                    ),
                  ),
                ] else ...[
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(color: AppConstants.borderLight),
                    ),
                    child: const Text(
                      'No Login Account',
                      style: TextStyle(
                        fontSize: 11,
                        color: AppConstants.textSecondary,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],

                // Phone info
                if (member.phoneNumber.isNotEmpty)
                  Text(
                    member.phoneNumber,
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppConstants.textSecondary,
                    ),
                  ),

                // Email info
                if (member.effectiveEmail != null && member.effectiveEmail!.isNotEmpty)
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.email_outlined, size: 12, color: AppConstants.textSecondary),
                      const SizedBox(width: 4),
                      Text(
                        member.effectiveEmail!,
                        style: const TextStyle(
                          fontSize: 11,
                          color: AppConstants.textSecondary,
                        ),
                      ),
                    ],
                  )
                else
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.mail_outline, size: 12, color: Colors.orange.shade800),
                      const SizedBox(width: 4),
                      Text(
                        'No Email ID (Edit to add)',
                        style: TextStyle(
                          fontSize: 11,
                          color: Colors.orange.shade800,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
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
        title: const Text('Manage Members'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, size: 20),
          onPressed: () => Navigator.of(context).pop(),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.person_add_alt_1, size: 22),
            tooltip: 'Create Account',
            onPressed: () => _openCreateMemberAccount(),
          ),
          IconButton(
            icon: const Icon(Icons.refresh, size: 22),
            tooltip: 'Refresh',
            onPressed: _loadData,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            OfflineBanner(
              isOffline: widget.syncService.isOffline,
              onRetry: _loadData,
            ),

            // Top action button
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 6),
              child: PrimaryButton(
                label: 'Create Member Account',
                icon: Icons.person_add_alt_1,
                height: 44,
                onPressed: () => _openCreateMemberAccount(),
              ),
            ),

            // Team Chips Filter
            _buildTeamChips(),

            // Search Bar
            _buildSearchBar(),

            // Users / All Team Members Section Header
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 6, 16, 4),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Users',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppConstants.pureBlack,
                    ),
                  ),
                  Text(
                    '${_members.length} ${_members.length == 1 ? "member" : "members"}',
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: AppConstants.textSecondary,
                    ),
                  ),
                ],
              ),
            ),

            // Members Directory
            Expanded(
              child: _isLoading
                  ? const LoadingView(message: 'Loading member directory...')
                  : _errorMessage != null && _members.isEmpty
                      ? RefreshIndicator(
                          onRefresh: _loadData,
                          color: AppConstants.pureBlack,
                          backgroundColor: AppConstants.pureWhite,
                          child: SingleChildScrollView(
                            physics: const AlwaysScrollableScrollPhysics(),
                            child: SizedBox(
                              height: MediaQuery.of(context).size.height * 0.5,
                              child: ErrorView(
                                message: _errorMessage!,
                                onRetry: _loadData,
                              ),
                            ),
                          ),
                        )
                      : _members.isEmpty
                          ? RefreshIndicator(
                              onRefresh: _loadData,
                              color: AppConstants.pureBlack,
                              backgroundColor: AppConstants.pureWhite,
                              child: SingleChildScrollView(
                                physics: const AlwaysScrollableScrollPhysics(),
                                child: SizedBox(
                                  height: MediaQuery.of(context).size.height * 0.5,
                                  child: EmptyView(
                                    message: 'No members found in this team.',
                                    icon: Icons.people_outline,
                                    actionLabel: 'Create Member Account',
                                    onAction: () => _openCreateMemberAccount(),
                                  ),
                                ),
                              ),
                            )
                          : RefreshIndicator(
                              onRefresh: _loadData,
                              color: AppConstants.pureBlack,
                              backgroundColor: AppConstants.pureWhite,
                              child: ListView.builder(
                                physics: const AlwaysScrollableScrollPhysics(),
                                padding: const EdgeInsets.only(top: 6, bottom: 24),
                                itemCount: _members.length,
                                itemBuilder: (context, index) {
                                  return _buildMemberCard(_members[index]);
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
