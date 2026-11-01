import 'package:flutter/material.dart';
import '../config/constants.dart';
import '../services/auth_service.dart';
import '../services/notification_service.dart';
import '../widgets/primary_button.dart';

class LoginScreen extends StatefulWidget {
  final AuthService authService;
  final NotificationService? notificationService;
  final VoidCallback onLoginSuccess;

  const LoginScreen({
    super.key,
    required this.authService,
    this.notificationService,
    required this.onLoginSuccess,
  });

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _serverUrlController = TextEditingController();

  bool _isLoading = false;
  bool _showServerConfig = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadServerUrl();
  }

  Future<void> _loadServerUrl() async {
    final url = await widget.authService.getConfiguredBaseUrl();
    _serverUrlController.text = url ?? AppConstants.defaultBaseUrl;
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _serverUrlController.dispose();
    super.dispose();
  }

  Future<void> _handleLogin() async {
    final username = _usernameController.text.trim();
    final password = _passwordController.text;

    if (username.isEmpty || password.isEmpty) {
      setState(() {
        _errorMessage = 'Please enter both username and password.';
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final customUrl = _showServerConfig && _serverUrlController.text.trim().isNotEmpty
          ? _serverUrlController.text.trim()
          : null;

      await widget.authService.login(
        username: username,
        password: password,
        customBaseUrl: customUrl,
      );

      // Register device token with backend if notification service is present
      if (widget.notificationService != null) {
        await widget.notificationService!.onUserLoggedIn();
      }

      widget.onLoginSuccess();
    } catch (e) {
      setState(() {
        _errorMessage = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppConstants.pureWhite,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Club Tasks',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w700,
                      color: AppConstants.pureBlack,
                      letterSpacing: -0.5,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Departmental Task Assignment & Operations',
                    style: TextStyle(
                      fontSize: 13,
                      color: AppConstants.textSecondary,
                    ),
                  ),
                  const SizedBox(height: 36),

                  if (_errorMessage != null) ...[
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFEF2F2),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: const Color(0xFFFCA5A5)),
                      ),
                      child: Text(
                        _errorMessage!,
                        style: const TextStyle(
                          color: AppConstants.dangerRed,
                          fontSize: 13,
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),
                  ],

                  // Username Field
                  const Text(
                    'Username or Email',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppConstants.pureBlack,
                    ),
                  ),
                  const SizedBox(height: 6),
                  TextField(
                    controller: _usernameController,
                    textInputAction: TextInputAction.next,
                    autocorrect: false,
                    enableSuggestions: false,
                    decoration: const InputDecoration(
                      hintText: 'e.g. clubadmin',
                    ),
                  ),
                  const SizedBox(height: 18),

                  // Password Field
                  const Text(
                    'Password',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppConstants.pureBlack,
                    ),
                  ),
                  const SizedBox(height: 6),
                  TextField(
                    controller: _passwordController,
                    obscureText: true,
                    textInputAction: TextInputAction.done,
                    onSubmitted: (_) => _handleLogin(),
                    decoration: const InputDecoration(
                      hintText: 'Enter your password',
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Server URL toggle
                  GestureDetector(
                    onTap: () {
                      setState(() {
                        _showServerConfig = !_showServerConfig;
                      });
                    },
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          _showServerConfig ? Icons.keyboard_arrow_up : Icons.keyboard_arrow_down,
                          size: 16,
                          color: AppConstants.textSecondary,
                        ),
                        const SizedBox(width: 4),
                        const Text(
                          'Server API URL',
                          style: TextStyle(
                            fontSize: 12,
                            color: AppConstants.textSecondary,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ),

                  if (_showServerConfig) ...[
                    const SizedBox(height: 10),
                    TextField(
                      controller: _serverUrlController,
                      style: const TextStyle(fontSize: 13),
                      decoration: const InputDecoration(
                        hintText: 'http://127.0.0.1:5000/api/v1',
                      ),
                    ),
                  ],

                  const SizedBox(height: 28),

                  // Sign In Button
                  PrimaryButton(
                    label: 'Sign In',
                    isLoading: _isLoading,
                    onPressed: _handleLogin,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
