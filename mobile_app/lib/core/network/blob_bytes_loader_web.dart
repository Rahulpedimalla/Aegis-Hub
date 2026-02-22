// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use

import 'dart:html' as html;
import 'dart:typed_data';

Future<List<int>?> readBlobBytesImpl(String url) async {
  if (url.trim().isEmpty) {
    return null;
  }

  try {
    final response = await html.HttpRequest.request(
      url,
      responseType: 'arraybuffer',
    );
    final payload = response.response;
    if (payload is ByteBuffer) {
      return payload.asUint8List();
    }
    if (payload is Uint8List) {
      return payload;
    }
  } catch (_) {
    return null;
  }

  return null;
}
