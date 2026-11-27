import 'package:flutter/material.dart';
import '../services/auth_service.dart';
import '../utils/password_policy.dart';

/// Blocking "Create Your New Password" popup shown whenever the server requires a new password.
///
/// It cannot be dismissed (no back navigation, no barrier tap, nothing behind it): the only ways out
/// are a successful change confirmed by the server, or logging out. The server enforces the same
/// requirement on every API call, so this screen is UX, not the security boundary.
class MandatoryPasswordChangeScreen extends StatefulWidget {
  final AuthService authService;
  final VoidCallback onPasswordChanged;
  final VoidCallback onLogout;

  const MandatoryPasswordChangeScreen({
    super.key,
    required this.authService,
    required this.onPasswordChanged,
    required this.onLogout,
  });

  @override
  State<MandatoryPasswordChangeScreen> createState() => _MandatoryPasswordChangeScreenState();
}

class _MandatoryPasswordChangeScreenState extends State<MandatoryPasswordChangeScreen> {
  static const _ink = Color(0xFF111827);
  static const _muted = Color(0xFF6B7280);
  static const _border = Color(0xFFE5E7EB);
  static const _danger = Color(0xFFDC2626);
  static const _ok = Color(0xFF15803D);

  final _formKey = GlobalKey<FormState>();
  final _current = TextEditingController();
  final _new = TextEditingController();
  final _confirm = TextEditingController();

  bool _hideCurrent = true;
  bool _hideNew = true;
  bool _hideConfirm = true;
  bool _submitting = false;
  String? _error;
  String? _currentFieldError;
  List<String> _serverProblems = const [];

  @override
  void initState() {
    super.initState();
    _new.addListener(_refresh);
    _confirm.addListener(_refresh);
  }

  void _refresh() => setState(() => _serverProblems = const []);

  @override
  void dispose() {
    _current.dispose();
    _new.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _error = null;
      _currentFieldError = null;
      _serverProblems = const [];
    });
    if (!_formKey.currentState!.validate()) return;

    setState(() => _submitting = true);
    try {
      await widget.authService.changePassword(
        currentPassword: _current.text,
        newPassword: _new.text,
        confirmPassword: _confirm.text,
      );
      if (!mounted) return;
      ScaffoldMessenger.maybeOf(context)?.showSnackBar(
        const SnackBar(content: Text('Your new password is set.'), backgroundColor: _ink),
      );
      widget.onPasswordChanged();
    } on PasswordChangeException catch (e) {
      if (!mounted) return;
      if (e.code == 'SESSION_EXPIRED') {
        // AuthService already cleared the session; the app returns to the login screen.
        return;
      }
      setState(() {
        switch (e.code) {
          case 'INVALID_CURRENT_PASSWORD':
            _currentFieldError = 'Current password is incorrect.';
            break;
          case 'PASSWORD_MISMATCH':
            _error = 'New passwords do not match.';
            break;
          case 'WEAK_PASSWORD':
            _serverProblems = e.problems.isNotEmpty ? e.problems : [e.message];
            _error = 'Choose a stronger password.';
            break;
          default:
            _error = e.message;
        }
      });
      _formKey.currentState?.validate();
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  InputDecoration _decoration(String hint, bool hidden, VoidCallback toggle, String toggleKey) {
    OutlineInputBorder b(Color c, [double w = 1]) =>
        OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: BorderSide(color: c, width: w));
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(fontSize: 13, color: Color(0xFF9CA3AF)),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      border: b(const Color(0xFFD1D5DB)),
      enabledBorder: b(_border),
      focusedBorder: b(_ink, 1.5),
      errorMaxLines: 3,
      suffixIcon: IconButton(
        key: Key(toggleKey),
        tooltip: hidden ? 'Show password' : 'Hide password',
        icon: Icon(hidden ? Icons.visibility_outlined : Icons.visibility_off_outlined, size: 18, color: _muted),
        onPressed: toggle,
      ),
    );
  }

  Widget _label(String text) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Text(text, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF374151))),
      );

  Widget _strengthBar() {
    final s = PasswordPolicy.strength(_new.text);
    const colors = [_border, _danger, Color(0xFFD97706), Color(0xFF2563EB), _ok];
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        children: [
          for (var i = 1; i <= 4; i++)
            Expanded(
              child: Container(
                height: 4,
                margin: EdgeInsets.only(right: i < 4 ? 4 : 0),
                decoration: BoxDecoration(
                  color: i <= s ? colors[s] : _border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
          const SizedBox(width: 10),
          SizedBox(
            width: 52,
            child: Text(
              PasswordPolicy.strengthLabel(s),
              key: const Key('passwordStrengthLabel'),
              textAlign: TextAlign.right,
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: s == 0 ? _muted : colors[s]),
            ),
          ),
        ],
      ),
    );
  }

  Widget _requirements() {
    final p = _new.text;
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFF9FAFB),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: _border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final r in PasswordPolicy.rules)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: Row(
                children: [
                  Icon(
                    r.test(p) ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                    size: 15,
                    color: r.test(p) ? _ok : const Color(0xFF9CA3AF),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(r.label,
                        style: TextStyle(fontSize: 12.5, color: r.test(p) ? const Color(0xFF374151) : _muted)),
                  ),
                ],
              ),
            ),
          for (final extra in _serverProblems)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.error_outline_rounded, size: 15, color: _danger),
                  const SizedBox(width: 8),
                  Expanded(child: Text(extra, style: const TextStyle(fontSize: 12.5, color: _danger))),
                ],
              ),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final username = widget.authService.username;
    return PopScope(
      canPop: false,
      child: Scaffold(
        backgroundColor: const Color(0xFF1F2937),
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 460),
                child: Material(
                  key: const Key('mandatoryPasswordDialog'),
                  color: Colors.white,
                  elevation: 12,
                  shadowColor: const Color(0x33000000),
                  borderRadius: BorderRadius.circular(16),
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(24, 28, 24, 20),
                    child: Form(
                      key: _formKey,
                      child: AutofillGroup(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Center(
                              child: Container(
                                width: 52,
                                height: 52,
                                decoration: BoxDecoration(
                                  color: const Color(0xFFF3F4F6),
                                  borderRadius: BorderRadius.circular(12),
                                  border: Border.all(color: _border),
                                ),
                                child: const Icon(Icons.lock_reset_rounded, color: _ink, size: 26),
                              ),
                            ),
                            const SizedBox(height: 18),
                            const Text(
                              'Create Your New Password',
                              textAlign: TextAlign.center,
                              style: TextStyle(fontSize: 21, fontWeight: FontWeight.w700, letterSpacing: -0.4, color: _ink),
                            ),
                            const SizedBox(height: 8),
                            const Text(
                              "For your account's security, you must create a new password before continuing to the application.",
                              textAlign: TextAlign.center,
                              style: TextStyle(fontSize: 13.5, color: _muted, height: 1.45),
                            ),
                            const SizedBox(height: 22),
                            if (_error != null) ...[
                              Container(
                                key: const Key('passwordChangeError'),
                                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFFEF2F2),
                                  borderRadius: BorderRadius.circular(8),
                                  border: Border.all(color: const Color(0xFFFCA5A5)),
                                ),
                                child: Row(
                                  children: [
                                    const Icon(Icons.error_outline_rounded, color: _danger, size: 18),
                                    const SizedBox(width: 8),
                                    Expanded(child: Text(_error!, style: const TextStyle(fontSize: 13, color: _danger))),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 14),
                            ],
                            _label('Current Password'),
                            TextFormField(
                              key: const Key('currentPasswordField'),
                              controller: _current,
                              obscureText: _hideCurrent,
                              enabled: !_submitting,
                              autofillHints: const [AutofillHints.password],
                              textInputAction: TextInputAction.next,
                              decoration: _decoration('Your current password', _hideCurrent,
                                  () => setState(() => _hideCurrent = !_hideCurrent), 'toggleCurrentPassword'),
                              validator: (v) {
                                if (v == null || v.isEmpty) return 'Current password is required';
                                return _currentFieldError;
                              },
                            ),
                            const SizedBox(height: 14),
                            _label('New Password'),
                            TextFormField(
                              key: const Key('newPasswordField'),
                              controller: _new,
                              obscureText: _hideNew,
                              enabled: !_submitting,
                              autofillHints: const [AutofillHints.newPassword],
                              textInputAction: TextInputAction.next,
                              decoration: _decoration('Create a strong password', _hideNew,
                                  () => setState(() => _hideNew = !_hideNew), 'toggleNewPassword'),
                              validator: (v) {
                                final problems = PasswordPolicy.problems(v ?? '', username: username);
                                if (problems.isNotEmpty) return 'Password needs: ${problems.join(', ').toLowerCase()}';
                                if (v == _current.text) return 'New password must be different from the current one';
                                return null;
                              },
                            ),
                            _strengthBar(),
                            _requirements(),
                            const SizedBox(height: 14),
                            _label('Confirm New Password'),
                            TextFormField(
                              key: const Key('confirmPasswordField'),
                              controller: _confirm,
                              obscureText: _hideConfirm,
                              enabled: !_submitting,
                              autofillHints: const [AutofillHints.newPassword],
                              textInputAction: TextInputAction.done,
                              onFieldSubmitted: (_) => _submitting ? null : _submit(),
                              decoration: _decoration('Re-enter the new password', _hideConfirm,
                                  () => setState(() => _hideConfirm = !_hideConfirm), 'toggleConfirmPassword'),
                              validator: (v) {
                                if (v == null || v.isEmpty) return 'Please confirm your new password';
                                if (v != _new.text) return 'Passwords do not match';
                                return null;
                              },
                            ),
                            const SizedBox(height: 22),
                            ElevatedButton(
                              key: const Key('createPasswordButton'),
                              onPressed: _submitting ? null : _submit,
                              style: ElevatedButton.styleFrom(
                                backgroundColor: _ink,
                                foregroundColor: Colors.white,
                                disabledBackgroundColor: const Color(0xFF4B5563),
                                elevation: 0,
                                padding: const EdgeInsets.symmetric(vertical: 14),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                              ),
                              child: _submitting
                                  ? const SizedBox(
                                      width: 20,
                                      height: 20,
                                      child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                                    )
                                  : const Text('Create New Password',
                                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                            ),
                            const SizedBox(height: 8),
                            TextButton(
                              key: const Key('logoutButton'),
                              onPressed: _submitting ? null : widget.onLogout,
                              style: TextButton.styleFrom(foregroundColor: _muted),
                              child: const Text('Log Out', style: TextStyle(fontSize: 13)),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
