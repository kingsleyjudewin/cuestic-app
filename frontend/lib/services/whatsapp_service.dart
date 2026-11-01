import 'package:flutter/foundation.dart';
import 'package:url_launcher/url_launcher.dart';
import 'sync_service.dart';

class WhatsAppService {
  final SyncService syncService;

  WhatsAppService({required this.syncService});


  Future<bool> launchWhatsAppUrl(String urlString) async {
    if (urlString.isEmpty) return false;
    try {
      final uri = Uri.parse(urlString);
      final canLaunch = await canLaunchUrl(uri);
      if (canLaunch) {
        return await launchUrl(uri, mode: LaunchMode.externalApplication);
      } else {
        // Fallback to in-app or browser
        return await launchUrl(uri, mode: LaunchMode.platformDefault);
      }
    } catch (e) {
      debugPrint('Failed to launch WhatsApp URL: $e');
      return false;
    }
  }

  Future<void> recordActionLinkOpened({
    required int assignmentId,
    required int messageLogId,
  }) async {
    try {
      await syncService.recordMessageAction(
        assignmentId: assignmentId,
        messageLogId: messageLogId,
        action: 'link_opened',
      );
    } catch (e) {
      debugPrint('Could not record link_opened action: $e');
    }
  }

  Future<void> recordActionMarkedSent({
    required int assignmentId,
    required int messageLogId,
  }) async {
    await syncService.recordMessageAction(
      assignmentId: assignmentId,
      messageLogId: messageLogId,
      action: 'marked_sent',
    );
  }

}
