import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../config/constants.dart';
import '../models/member.dart';
import '../models/team.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';
import '../services/sync_service.dart';
import '../widgets/primary_button.dart';

class CreateMemberAccountScreen extends StatefulWidget {
  final SyncService syncService;
  final AuthService authService;
  final int? initialTeamId;
  final Member? prefillMember;
  final void Function(Member member)? onAccountCreated;

  const CreateMemberAccountScreen({
    super.key,
    required this.syncService,
    required this.authService,
    this.initialTeamId,
    this.prefillMember,
    this.onAccountCreated,
  });

  @override
  State<CreateMemberAccountScreen> createState() => _CreateMemberAccountScreenState();
}

class _CreateMemberAccountScreenState extends State<CreateMemberAccountScreen> {
  final _formKey = GlobalKey<FormState>();

  final _fullNameController = TextEditingController();
  final _regNoController = TextEditingController();
  final _classNameController = TextEditingController();
  final _sectionController = TextEditingController();
  final _phoneController = TextEditingController();
  final _usernameController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  List<Team> _teams = [];
  int? _selectedTeamId;
  String _selectedRole = 'member';
  bool _obscurePassword = true;

  bool _isLoadingTeams = true;
  bool _isSubmitting = false;

  String? _fullNameError;
  String? _regNoError;
  String? _classNameError;
  String? _phoneError;
  String? _usernameError;
  String? _emailError;
  String? _passwordError;
  String? _teamError;
  String? _generalError;

  @override
  void initState() {
    super.initState();
    _initPrefill();
    _loadTeams();
  }

  void _initPrefill() {
    if (widget.prefillMember != null) {
      final m = widget.prefillMember!;
      _fullNameController.text = m.fullName;
      _regNoController.text = m.registrationNumber ?? '';
      _classNameController.text = m.className;
      _sectionController.text = m.section ?? '';
      _phoneController.text = m.phoneNumber.replaceAll('+91', '');
      _selectedTeamId = m.teamId;
      if (m.linkedUsername != null) {
        _usernameController.text = m.linkedUsername!;
      } else {
        _usernameController.text = m.fullName.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '_');
      }
      if (m.linkedEmail != null) {
        _emailController.text = m.linkedEmail!;
      }
    } else {
      _generateTemporaryPassword();
    }

    if (widget.initialTeamId != null) {
      _selectedTeamId = widget.initialTeamId;
    }
  }

  void _generateTemporaryPassword() {
    const chars = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#%*';
    final random = Random.secure();
    final pwd = List.generate(10, (index) => chars[random.nextInt(chars.length)]).join();
    _passwordController.text = 'Club!$pwd';
  }

  Future<void> _loadTeams() async {
    try {
      final teams = await widget.syncService.fetchClubTeams();
      if (mounted) {
        setState(() {
          _teams = teams;
          _isLoadingTeams = false;
          if (_selectedTeamId == null && teams.isNotEmpty) {
            _selectedTeamId = teams.first.id;
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoadingTeams = false;
          _generalError = 'Failed to load teams. Please retry.';
        });
      }
    }
  }

  @override
  void dispose() {
    _fullNameController.dispose();
    _regNoController.dispose();
    _classNameController.dispose();
    _sectionController.dispose();
    _phoneController.dispose();
    _usernameController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  bool _validateForm() {
    setState(() {
      _fullNameError = null;
      _regNoError = null;
      _classNameError = null;
      _phoneError = null;
      _usernameError = null;
      _emailError = null;
      _passwordError = null;
      _teamError = null;
      _generalError = null;
    });

    bool isValid = true;

    final fullName = _fullNameController.text.trim();
    if (fullName.isEmpty) {
      setState(() => _fullNameError = 'Full name is required.');
      isValid = false;
    } else if (fullName.length < 2) {
      setState(() => _fullNameError = 'Full name must be at least 2 characters.');
      isValid = false;
    }

    final className = _classNameController.text.trim();
    if (className.isEmpty) {
      setState(() => _classNameError = 'Class / Year is required.');
      isValid = false;
    }

    final phone = _phoneController.text.trim();
    if (phone.isEmpty) {
      setState(() => _phoneError = 'Phone number is required.');
      isValid = false;
    } else if (phone.replaceAll(RegExp(r'[^0-9]'), '').length < 10) {
      setState(() => _phoneError = 'Enter a valid 10-digit phone number.');
      isValid = false;
    }

    final username = _usernameController.text.trim();
    if (username.isEmpty) {
      setState(() => _usernameError = 'Username is required.');
      isValid = false;
    } else if (username.length < 3) {
      setState(() => _usernameError = 'Username must be at least 3 characters.');
      isValid = false;
    } else if (!RegExp(r'^[a-zA-Z0-9_.-]+$').hasMatch(username)) {
      setState(() => _usernameError = 'Username can only contain letters, numbers, dots, and underscores.');
      isValid = false;
    }

    final email = _emailController.text.trim();
    if (email.isEmpty) {
      setState(() => _emailError = 'Email address is required.');
      isValid = false;
    } else if (!email.contains('@') || !email.contains('.')) {
      setState(() => _emailError = 'Enter a valid email address.');
      isValid = false;
    }

    final password = _passwordController.text;
    if (password.isEmpty) {
      setState(() => _passwordError = 'Temporary password is required.');
      isValid = false;
    } else if (password.length < 4) {
      setState(() => _passwordError = 'Password must be at least 4 characters.');
      isValid = false;
    }

    if (_selectedTeamId == null) {
      setState(() => _teamError = 'Please select a club team.');
      isValid = false;
    }

    return isValid;
  }

  Future<void> _handleSubmit() async {
    if (_isSubmitting) return;
    if (!_validateForm()) return;

    setState(() {
      _isSubmitting = true;
      _generalError = null;
    });

    final fullName = _fullNameController.text.trim();
    final regNo = _regNoController.text.trim();
    final className = _classNameController.text.trim();
    final section = _sectionController.text.trim();
    final phone = _phoneController.text.trim();
    final username = _usernameController.text.trim().toLowerCase();
    final email = _emailController.text.trim().toLowerCase();
    final password = _passwordController.text;
    final teamId = _selectedTeamId!;
    final role = _selectedRole;

    try {
      final result = await widget.syncService.createMemberAccount(
        fullName: fullName,
        registrationNumber: regNo.isNotEmpty ? regNo : null,
        className: className,
        section: section.isNotEmpty ? section : null,
        phoneNumber: phone,
        teamId: teamId,
        username: username,
        email: email,
        password: password,
        role: role,
      );

      final createdMember = result['member'] as Member?;

      if (mounted) {
        setState(() {
          _isSubmitting = false;
        });

        // Show Account Created Confirmation Dialog
        await showDialog<void>(
          context: context,
          barrierDismissible: false,
          builder: (ctx) => AlertDialog(
            backgroundColor: AppConstants.pureWhite,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            title: Row(
              children: const [
                Icon(Icons.check_circle_outline, color: AppConstants.pureBlack, size: 24),
                SizedBox(width: 8),
                Text(
                  'Account Created',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: AppConstants.pureBlack,
                  ),
                ),
              ],
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Member login account for $fullName has been set up successfully.',
                  style: const TextStyle(fontSize: 14, color: AppConstants.pureBlack),
                ),
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppConstants.backgroundLight,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppConstants.borderLight),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildDetailRow('Username', username),
                      const SizedBox(height: 6),
                      _buildDetailRow('Email', email),
                      const SizedBox(height: 6),
                      _buildDetailRow('Role', role == 'team_leader' ? 'Team Leader' : 'Member'),
                      const SizedBox(height: 6),
                      _buildDetailRow('Temp Password', password, isCopyable: true),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                const Text(
                  'Credentials are confidential. Share them securely through official department channels.',
                  style: TextStyle(fontSize: 12, color: AppConstants.textSecondary),
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () {
                  Navigator.of(ctx).pop();
                },
                child: const Text(
                  'Done',
                  style: TextStyle(
                    color: AppConstants.pureBlack,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
        );

        if (mounted) {
          if (widget.onAccountCreated != null && createdMember != null) {
            widget.onAccountCreated!(createdMember);
          } else {
            Navigator.of(context).pop(createdMember);
          }
        }
      }
    } on ApiException catch (e) {
      if (mounted) {
        setState(() {
          _isSubmitting = false;

          if (e.details.containsKey('username')) {
            final val = e.details['username'];
            _usernameError = val is List ? val.join(', ') : val.toString();
          }
          if (e.details.containsKey('email')) {
            final val = e.details['email'];
            _emailError = val is List ? val.join(', ') : val.toString();
          }
          if (e.details.containsKey('phone_number')) {
            final val = e.details['phone_number'];
            _phoneError = val is List ? val.join(', ') : val.toString();
          }
          if (e.details.containsKey('registration_number')) {
            final val = e.details['registration_number'];
            _regNoError = val is List ? val.join(', ') : val.toString();
          }
          if (e.details.containsKey('team_id')) {
            final val = e.details['team_id'];
            _teamError = val is List ? val.join(', ') : val.toString();
          }

          if (_usernameError == null &&
              _emailError == null &&
              _phoneError == null &&
              _regNoError == null &&
              _teamError == null) {
            _generalError = e.message;
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
          _generalError = 'An unexpected error occurred: ${e.toString()}';
        });
      }
    }
  }

  Widget _buildDetailRow(String label, String value, {bool isCopyable = false}) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 12, color: AppConstants.textSecondary),
        ),
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              value,
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppConstants.pureBlack,
              ),
            ),
            if (isCopyable) ...[
              const SizedBox(width: 4),
              InkWell(
                onTap: () {
                  Clipboard.setData(ClipboardData(text: value));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Password copied to clipboard'),
                      duration: Duration(seconds: 2),
                    ),
                  );
                },
                child: const Icon(Icons.copy, size: 14, color: AppConstants.textSecondary),
              ),
            ],
          ],
        ),
      ],
    );
  }

  Widget _buildFieldLabel(String label, {bool isRequired = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppConstants.pureBlack,
            ),
          ),
          if (isRequired)
            const Text(
              ' *',
              style: TextStyle(color: Colors.red, fontWeight: FontWeight.bold),
            ),
        ],
      ),
    );
  }

  InputDecoration _inputDecoration({
    required String hintText,
    String? errorText,
    Widget? prefixIcon,
    Widget? suffixIcon,
  }) {
    return InputDecoration(
      hintText: hintText,
      hintStyle: const TextStyle(color: AppConstants.textSecondary, fontSize: 14),
      errorText: errorText,
      prefixIcon: prefixIcon,
      suffixIcon: suffixIcon,
      filled: true,
      fillColor: AppConstants.pureWhite,
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: AppConstants.borderLight),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: AppConstants.pureBlack, width: 1.5),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: Colors.red, width: 1),
      ),
      focusedErrorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: Colors.red, width: 1.5),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppConstants.pureWhite,
      appBar: AppBar(
        title: const Text('Create Member Account'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, size: 20),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
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
                      color: Colors.red.shade50,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.red.shade200),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(Icons.error_outline, color: Colors.red.shade700, size: 20),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            _generalError!,
                            style: TextStyle(
                              color: Colors.red.shade900,
                              fontSize: 13,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                ],

                // Section 1: Member Personal Details
                const Text(
                  'Member Profile',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                    color: AppConstants.pureBlack,
                  ),
                ),
                const SizedBox(height: 12),

                _buildFieldLabel('Full Name', isRequired: true),
                TextFormField(
                  key: const Key('input_full_name'),
                  controller: _fullNameController,
                  textCapitalization: TextCapitalization.words,
                  decoration: _inputDecoration(
                    hintText: 'e.g. Rahul Sharma',
                    errorText: _fullNameError,
                    prefixIcon: const Icon(Icons.person_outline, size: 18),
                  ),
                  onChanged: (val) {
                    if (_fullNameError != null) setState(() => _fullNameError = null);
                    if (_usernameController.text.isEmpty && val.trim().isNotEmpty) {
                      _usernameController.text = val.trim().toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '_');
                    }
                  },
                ),
                const SizedBox(height: 14),

                Row(
                  children: [
                    Expanded(
                      flex: 3,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _buildFieldLabel('Class / Year', isRequired: true),
                          TextFormField(
                            key: const Key('input_class_name'),
                            controller: _classNameController,
                            decoration: _inputDecoration(
                              hintText: '3rd Year CSE',
                              errorText: _classNameError,
                            ),
                            onChanged: (_) {
                              if (_classNameError != null) setState(() => _classNameError = null);
                            },
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      flex: 2,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _buildFieldLabel('Section'),
                          TextFormField(
                            key: const Key('input_section'),
                            controller: _sectionController,
                            textCapitalization: TextCapitalization.characters,
                            decoration: _inputDecoration(
                              hintText: 'A',
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),

                _buildFieldLabel('Registration Number / Student ID'),
                TextFormField(
                  key: const Key('input_reg_no'),
                  controller: _regNoController,
                  decoration: _inputDecoration(
                    hintText: 'e.g. REG2026-101',
                    errorText: _regNoError,
                    prefixIcon: const Icon(Icons.badge_outlined, size: 18),
                  ),
                  onChanged: (_) {
                    if (_regNoError != null) setState(() => _regNoError = null);
                  },
                ),
                const SizedBox(height: 14),

                _buildFieldLabel('Phone Number', isRequired: true),
                TextFormField(
                  key: const Key('input_phone_number'),
                  controller: _phoneController,
                  keyboardType: TextInputType.phone,
                  decoration: _inputDecoration(
                    hintText: '9876543210',
                    errorText: _phoneError,
                    prefixIcon: const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 10, vertical: 12),
                      child: Text(
                        '+91',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: AppConstants.pureBlack,
                          fontSize: 14,
                        ),
                      ),
                    ),
                  ),
                  onChanged: (_) {
                    if (_phoneError != null) setState(() => _phoneError = null);
                  },
                ),
                const SizedBox(height: 24),

                // Section 2: Team & Role
                const Text(
                  'Team & Assignment',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                    color: AppConstants.pureBlack,
                  ),
                ),
                const SizedBox(height: 12),

                _buildFieldLabel('Team', isRequired: true),
                _isLoadingTeams
                    ? Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: AppConstants.borderLight),
                        ),
                        child: const Row(
                          children: [
                            SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
                            SizedBox(width: 10),
                            Text('Loading club teams...', style: TextStyle(fontSize: 13)),
                          ],
                        ),
                      )
                    : Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: _teamError != null ? Colors.red : AppConstants.borderLight,
                          ),
                          color: AppConstants.pureWhite,
                        ),
                        child: DropdownButtonHideUnderline(
                          child: DropdownButton<int>(
                            key: const Key('dropdown_team'),
                            value: _selectedTeamId,
                            isExpanded: true,
                            hint: const Text('Select a team'),
                            items: _teams.map((t) {
                              return DropdownMenuItem<int>(
                                value: t.id,
                                child: Text(
                                  t.name,
                                  style: const TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w500,
                                    color: AppConstants.pureBlack,
                                  ),
                                ),
                              );
                            }).toList(),
                            onChanged: (id) {
                              setState(() {
                                _selectedTeamId = id;
                                _teamError = null;
                              });
                            },
                          ),
                        ),
                      ),
                if (_teamError != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    _teamError!,
                    style: const TextStyle(color: Colors.red, fontSize: 12),
                  ),
                ],
                const SizedBox(height: 14),

                _buildFieldLabel('Role', isRequired: true),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppConstants.borderLight),
                    color: AppConstants.pureWhite,
                  ),
                  child: DropdownButtonHideUnderline(
                    child: DropdownButton<String>(
                      key: const Key('dropdown_role'),
                      value: _selectedRole,
                      isExpanded: true,
                      items: const [
                        DropdownMenuItem(
                          value: 'member',
                          child: Text('Member (Task Assignee)'),
                        ),
                        DropdownMenuItem(
                          value: 'team_leader',
                          child: Text('Team Leader (Can View & Manage Team)'),
                        ),
                      ],
                      onChanged: (role) {
                        if (role != null) {
                          setState(() => _selectedRole = role);
                        }
                      },
                    ),
                  ),
                ),
                const SizedBox(height: 24),

                // Section 3: Login Credentials
                const Text(
                  'Login Credentials',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                    color: AppConstants.pureBlack,
                  ),
                ),
                const SizedBox(height: 12),

                _buildFieldLabel('Username', isRequired: true),
                TextFormField(
                  key: const Key('input_username'),
                  controller: _usernameController,
                  autocorrect: false,
                  enableSuggestions: false,
                  decoration: _inputDecoration(
                    hintText: 'e.g. rahul_sharma',
                    errorText: _usernameError,
                    prefixIcon: const Icon(Icons.alternate_email, size: 18),
                  ),
                  onChanged: (_) {
                    if (_usernameError != null) setState(() => _usernameError = null);
                  },
                ),
                const SizedBox(height: 14),

                _buildFieldLabel('Email Address', isRequired: true),
                TextFormField(
                  key: const Key('input_email'),
                  controller: _emailController,
                  keyboardType: TextInputType.emailAddress,
                  autocorrect: false,
                  decoration: _inputDecoration(
                    hintText: 'e.g. rahul@university.edu',
                    errorText: _emailError,
                    prefixIcon: const Icon(Icons.email_outlined, size: 18),
                  ),
                  onChanged: (_) {
                    if (_emailError != null) setState(() => _emailError = null);
                  },
                ),
                const SizedBox(height: 14),

                _buildFieldLabel('Temporary Password', isRequired: true),
                TextFormField(
                  key: const Key('input_password'),
                  controller: _passwordController,
                  obscureText: _obscurePassword,
                  decoration: _inputDecoration(
                    hintText: 'Min 8 characters',
                    errorText: _passwordError,
                    prefixIcon: const Icon(Icons.lock_outline, size: 18),
                    suffixIcon: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        IconButton(
                          icon: Icon(
                            _obscurePassword ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                            size: 18,
                            color: AppConstants.textSecondary,
                          ),
                          onPressed: () {
                            setState(() => _obscurePassword = !_obscurePassword);
                          },
                        ),
                        IconButton(
                          icon: const Icon(Icons.autorenew, size: 18, color: AppConstants.pureBlack),
                          tooltip: 'Generate Random Password',
                          onPressed: () {
                            _generateTemporaryPassword();
                          },
                        ),
                      ],
                    ),
                  ),
                  onChanged: (_) {
                    if (_passwordError != null) setState(() => _passwordError = null);
                  },
                ),
                const SizedBox(height: 28),

                PrimaryButton(
                  key: const Key('btn_submit_create_account'),
                  label: 'Create Member Account',
                  icon: Icons.person_add_alt_1,
                  isLoading: _isSubmitting,
                  onPressed: _handleSubmit,
                ),
                const SizedBox(height: 30),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
