/// Client-side copy of the server password policy (app/utils/password_policy.py).
/// The server is the authority; this only gives instant feedback while typing.
class PasswordRule {
  final String label;
  final bool Function(String password) test;
  const PasswordRule(this.label, this.test);
}

class PasswordPolicy {
  static const int minLength = 12;
  static const int maxLength = 128;

  static final RegExp _upper = RegExp(r'[A-Z]');
  static final RegExp _lower = RegExp(r'[a-z]');
  static final RegExp _digit = RegExp(r'[0-9]');
  static final RegExp _special = RegExp(r'[^A-Za-z0-9\s]');

  static final List<PasswordRule> rules = [
    PasswordRule('At least $minLength characters', (p) => p.length >= minLength),
    PasswordRule('One uppercase letter', (p) => _upper.hasMatch(p)),
    PasswordRule('One lowercase letter', (p) => _lower.hasMatch(p)),
    PasswordRule('One number', (p) => _digit.hasMatch(p)),
    PasswordRule('One special character (e.g. ! @ # \$ %)', (p) => _special.hasMatch(p)),
  ];

  /// Problems shown under the field; empty when the password satisfies the rules.
  static List<String> problems(String password, {String? username}) {
    final out = <String>[];
    if (password.isEmpty) return ['New password is required'];
    for (final r in rules) {
      if (!r.test(password)) out.add(r.label);
    }
    if (password.length > maxLength) out.add('At most $maxLength characters');
    if (password != password.trim()) out.add('No spaces at the start or end');
    if (username != null) {
      var base = username.toLowerCase().split('@').first;
      if (base.endsWith('.cu')) base = base.substring(0, base.length - 3);
      if (base.length >= 4 && password.toLowerCase().contains(base)) {
        out.add('Must not contain your username');
      }
    }
    return out;
  }

  /// 0 (empty) .. 4 (strong). Strong only when every rule passes.
  static int strength(String password) {
    if (password.isEmpty) return 0;
    final passed = rules.where((r) => r.test(password)).length;
    if (passed < 3) return 1;
    if (passed < rules.length) return 2;
    return password.length >= 16 ? 4 : 3;
  }

  static String strengthLabel(int s) =>
      const ['', 'Weak', 'Fair', 'Good', 'Strong'][s.clamp(0, 4)];
}
