import 'package:flutter/material.dart';

/// Thin strip shown above every screen while the shared visitor (demo) account is signed in.
/// The server keeps that account on an empty, read-only workspace.
class VisitorModeBanner extends StatelessWidget {
  const VisitorModeBanner({super.key});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: const Color(0xFFFEF3C7),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          child: Row(
            children: const [
              Icon(Icons.visibility_outlined, size: 16, color: Color(0xFF92400E)),
              SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Visitor mode: explore every feature. Nothing you do here is saved.',
                  style: TextStyle(color: Color(0xFF92400E), fontSize: 12, fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
