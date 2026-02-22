import 'live_transcription_service_base.dart';

class _NoopLiveTranscriptionService implements LiveTranscriptionService {
  @override
  Future<bool> start({String localeId = 'en-IN'}) async {
    return false;
  }

  @override
  Future<String> stopAndCollect() async {
    return '';
  }

  @override
  Future<void> cancel() async {
    // No-op on non-web platforms for now.
  }
}

LiveTranscriptionService createLiveTranscriptionService() => _NoopLiveTranscriptionService();
