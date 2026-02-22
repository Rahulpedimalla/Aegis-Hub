import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:universal_io/io.dart';

class _CaptureFormat {
  const _CaptureFormat({
    required this.encoder,
    required this.extension,
    required this.mimeType,
    required this.sampleRate,
    required this.bitRate,
  });

  final AudioEncoder encoder;
  final String extension;
  final String mimeType;
  final int sampleRate;
  final int bitRate;
}

class RecordedAudio {
  const RecordedAudio({
    required this.path,
    required this.fileName,
    required this.mimeType,
  });

  final String path;
  final String fileName;
  final String mimeType;
}

class AudioCaptureService {
  AudioCaptureService({AudioRecorder? recorder}) : _recorder = recorder ?? AudioRecorder();

  final AudioRecorder _recorder;
  _CaptureFormat _activeFormat = const _CaptureFormat(
    encoder: AudioEncoder.aacLc,
    extension: 'm4a',
    mimeType: 'audio/m4a',
    sampleRate: 16000,
    bitRate: 128000,
  );

  Future<bool> startRecording() async {
    try {
      final hasPermission = await _recorder.hasPermission();
      if (!hasPermission) {
        return false;
      }
      _activeFormat = await _resolveCaptureFormat();
      final filePath = await _newRecordingPath(_activeFormat.extension);
      await _recorder.start(
        RecordConfig(
          encoder: _activeFormat.encoder,
          bitRate: _activeFormat.bitRate,
          sampleRate: _activeFormat.sampleRate,
        ),
        path: filePath,
      );
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<RecordedAudio?> stopRecording() async {
    final path = (await _recorder.stop())?.trim();
    if ((path ?? '').isEmpty) {
      return null;
    }

    final extension = _extensionFromPath(path!) ?? _activeFormat.extension;
    final mimeType = _mimeTypeForExtension(extension, fallback: _activeFormat.mimeType);
    final fileName =
        'aegis_audio_${DateTime.now().toUtc().millisecondsSinceEpoch}.$extension';
    return RecordedAudio(
      path: path,
      fileName: fileName,
      mimeType: mimeType,
    );
  }

  Future<void> cancelRecording() async {
    await _recorder.cancel();
  }

  Future<bool> isRecording() async {
    return _recorder.isRecording();
  }

  Stream<Amplitude> onAmplitudeChanged(Duration interval) {
    return _recorder.onAmplitudeChanged(interval);
  }

  Future<_CaptureFormat> _resolveCaptureFormat() async {
    if (!kIsWeb) {
      return const _CaptureFormat(
        encoder: AudioEncoder.aacLc,
        extension: 'm4a',
        mimeType: 'audio/m4a',
        sampleRate: 16000,
        bitRate: 128000,
      );
    }

    // Prefer Opus on web to avoid large WAV payloads and allow longer messages.
    final webOpus = const _CaptureFormat(
      encoder: AudioEncoder.opus,
      extension: 'webm',
      mimeType: 'audio/webm',
      sampleRate: 16000,
      bitRate: 64000,
    );
    final webWav = const _CaptureFormat(
      encoder: AudioEncoder.wav,
      extension: 'wav',
      mimeType: 'audio/wav',
      sampleRate: 16000,
      bitRate: 128000,
    );

    try {
      final supportsOpus = await _recorder.isEncoderSupported(AudioEncoder.opus);
      if (supportsOpus) {
        return webOpus;
      }
    } catch (_) {
      // Fall back to WAV when capability probing fails.
    }

    return webWav;
  }

  Future<String> _newRecordingPath(String extension) async {
    final timestamp = DateTime.now().toUtc().millisecondsSinceEpoch;
    if (kIsWeb) {
      // Web recorder still requires a path parameter, but browser storage is virtual.
      return 'aegis_web_audio_$timestamp.$extension';
    }

    final dir = await getApplicationSupportDirectory();
    final mediaDir = Directory('${dir.path}/aegis_recordings');
    await mediaDir.create(recursive: true);
    return '${mediaDir.path}/audio_$timestamp.$extension';
  }

  String _mimeTypeForExtension(String extension, {String fallback = 'audio/m4a'}) {
    switch (extension.toLowerCase()) {
      case 'wav':
        return 'audio/wav';
      case 'webm':
        return 'audio/webm';
      case 'ogg':
      case 'opus':
        return 'audio/ogg';
      case 'mp3':
        return 'audio/mpeg';
      default:
        return fallback;
    }
  }

  String? _extensionFromPath(String path) {
    final normalized = path.trim().toLowerCase();
    if (normalized.isEmpty || normalized.startsWith('blob:') || normalized.startsWith('data:')) {
      return null;
    }
    final parsed = Uri.tryParse(normalized);
    final segments = parsed?.pathSegments ?? const <String>[];
    if (segments.isEmpty) {
      return null;
    }
    final fileName = segments.last;
    final dotIndex = fileName.lastIndexOf('.');
    if (dotIndex <= 0 || dotIndex >= fileName.length - 1) {
      return null;
    }
    return fileName.substring(dotIndex + 1);
  }
}
