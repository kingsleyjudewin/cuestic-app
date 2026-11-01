import 'package:flutter/material.dart';
import '../config/constants.dart';

class OfflineBanner extends StatelessWidget {
  final bool isOffline;
  final VoidCallback? onRetry;

  const OfflineBanner({
    super.key,
    required this.isOffline,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    if (!isOffline) return const SizedBox.shrink();

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      color: const Color(0xFFF3F4F6),
      child: Row(
        children: [
          const Icon(Icons.cloud_off_outlined, size: 16, color: AppConstants.textSecondary),
          const SizedBox(width: 8),
          const Expanded(
            child: Text(
              'Offline — Viewing cached records',
              style: TextStyle(
                color: AppConstants.textSecondary,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          if (onRetry != null)
            GestureDetector(
              onTap: onRetry,
              child: const Text(
                'Retry',
                style: TextStyle(
                  color: AppConstants.pureBlack,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  decoration: TextDecoration.underline,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
