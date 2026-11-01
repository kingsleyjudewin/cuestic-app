import 'download_helper_stub.dart'
    if (dart.library.html) 'download_helper_web.dart'
    if (dart.library.io) 'download_helper_mobile.dart';

class DownloadHelper {
  static Future<String> downloadFile(List<int> bytes, String filename) async {
    return await saveFileImpl(bytes, filename);
  }
}
