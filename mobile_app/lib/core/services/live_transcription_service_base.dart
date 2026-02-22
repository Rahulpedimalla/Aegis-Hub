abstract class LiveTranscriptionService {
  Future<bool> start({String localeId = 'en-IN'});
  Future<String> stopAndCollect();
  Future<void> cancel();
}
