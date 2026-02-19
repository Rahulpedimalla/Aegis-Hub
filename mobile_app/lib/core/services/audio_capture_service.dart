import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:universal_io/io.dart';

class AudioCaptureService {
  AudioCaptureService({AudioRecorder? recorder}) : _recorder = recorder ?? AudioRecorder();

  final AudioRecorder _recorder;

  Future<bool> startRecording() async {
    try {
      final hasPermission = await _recorder.hasPermission();
      if (!hasPermission) {
        return false;
      }
      final filePath = await _newRecordingPath();
      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.aacLc,
          bitRate: 128000,
          sampleRate: 16000,
        ),
        path: filePath,
      );
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<String?> stopRecording() async {
    return _recorder.stop();
  }

  Future<void> cancelRecording() async {
    await _recorder.cancel();
  }

  Future<bool> isRecording() async {
    return _recorder.isRecording();
  }

  Future<String> _newRecordingPath() async {
    final timestamp = DateTime.now().toUtc().millisecondsSinceEpoch;
    if (kIsWeb) {
      // Web recorder still requires a path parameter, but browser storage is virtual.
      return 'aegis_web_audio_$timestamp.m4a';
    }

    final dir = await getApplicationSupportDirectory();
    final mediaDir = Directory('${dir.path}/aegis_recordings');
    await mediaDir.create(recursive: true);
    return '${mediaDir.path}/audio_$timestamp.m4a';
  }
}
