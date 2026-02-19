import '../../domain/tts_provider.dart';

class FallbackTtsProvider implements TtsProvider {
  @override
  String get providerName => 'fallback';

  @override
  Future<void> speak(String text) async {}
}
