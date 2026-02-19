import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:universal_io/io.dart';

enum MediaKind { image, video, audio }

class MediaAttachment {
  const MediaAttachment({
    required this.path,
    required this.fileName,
    required this.mimeType,
    required this.sizeBytes,
    required this.sha256,
    required this.kind,
    this.bytes,
  });

  final String path;
  final String fileName;
  final String mimeType;
  final int sizeBytes;
  final String sha256;
  final MediaKind kind;
  final List<int>? bytes;

  factory MediaAttachment.fromJson(Map<String, dynamic> json) {
    final kindName = (json['kind'] ?? 'image').toString();
    return MediaAttachment(
      path: (json['path'] ?? '').toString(),
      fileName: (json['file_name'] ?? '').toString(),
      mimeType: (json['mime_type'] ?? '').toString(),
      sizeBytes: int.tryParse((json['size_bytes'] ?? '0').toString()) ?? 0,
      sha256: (json['sha256'] ?? '').toString(),
      kind: MediaKind.values.firstWhere(
        (item) => item.name == kindName,
        orElse: () => MediaKind.image,
      ),
      bytes: null,
    );
  }

  static Future<MediaAttachment> fromPath({
    required String path,
    required String fileName,
    required String mimeType,
    required MediaKind kind,
  }) async {
    final file = File(path);
    final bytes = await file.readAsBytes();
    return MediaAttachment(
      path: path,
      fileName: fileName,
      mimeType: mimeType,
      sizeBytes: bytes.length,
      sha256: sha256Hex(bytes),
      kind: kind,
      bytes: bytes,
    );
  }

  static Future<MediaAttachment> fromBytes({
    required List<int> bytes,
    required String fileName,
    required String mimeType,
    required MediaKind kind,
    String path = '',
  }) async {
    return MediaAttachment(
      path: path,
      fileName: fileName,
      mimeType: mimeType,
      sizeBytes: bytes.length,
      sha256: sha256Hex(bytes),
      kind: kind,
      bytes: bytes,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'path': path,
      'file_name': fileName,
      'mime_type': mimeType,
      'size_bytes': sizeBytes,
      'sha256': sha256,
      'kind': kind.name,
    };
  }
}

String sha256Hex(List<int> bytes) => sha256.convert(bytes).toString();

String sha256Text(String value) => sha256.convert(utf8.encode(value)).toString();
