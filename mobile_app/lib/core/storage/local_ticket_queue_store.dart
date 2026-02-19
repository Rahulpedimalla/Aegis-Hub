import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:universal_io/io.dart';

class LocalTicketQueueStore {
  static final List<Map<String, dynamic>> _webQueue = <Map<String, dynamic>>[];

  Future<void> enqueue(Map<String, dynamic> item) async {
    if (kIsWeb) {
      _webQueue.add(item);
      return;
    }
    final entries = await readAll();
    entries.add(item);
    await _write(entries);
  }

  Future<List<Map<String, dynamic>>> readAll() async {
    if (kIsWeb) {
      return List<Map<String, dynamic>>.from(_webQueue);
    }
    final file = await _queueFile();
    if (!await file.exists()) {
      return <Map<String, dynamic>>[];
    }

    final content = await file.readAsString();
    if (content.trim().isEmpty) {
      return <Map<String, dynamic>>[];
    }

    final decoded = jsonDecode(content);
    if (decoded is! List) {
      return <Map<String, dynamic>>[];
    }

    return decoded
        .whereType<Map>()
        .map((entry) => entry.cast<String, dynamic>())
        .toList();
  }

  Future<void> removeByExternalId(String externalId) async {
    if (kIsWeb) {
      _webQueue.removeWhere((entry) => entry['external_id'] == externalId);
      return;
    }
    final entries = await readAll();
    final filtered = entries.where((entry) => entry['external_id'] != externalId).toList();
    await _write(filtered);
  }

  Future<void> _write(List<Map<String, dynamic>> entries) async {
    final file = await _queueFile();
    await file.parent.create(recursive: true);
    await file.writeAsString(jsonEncode(entries), flush: true);
  }

  Future<File> _queueFile() async {
    final dir = await getApplicationSupportDirectory();
    return File('${dir.path}/aegis_queue/pending_tickets.json');
  }
}
