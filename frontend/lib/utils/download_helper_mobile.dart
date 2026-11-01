import 'dart:io';
import 'package:path_provider/path_provider.dart';

Future<String> saveFileImpl(List<int> bytes, String filename) async {
  Directory? dir;
  try {
    dir = await getDownloadsDirectory();
  } catch (_) {
    dir = null;
  }
  dir ??= await getApplicationDocumentsDirectory();

  final file = File('${dir.path}/$filename');
  await file.writeAsBytes(bytes);
  return 'Saved to ${file.path}';
}
