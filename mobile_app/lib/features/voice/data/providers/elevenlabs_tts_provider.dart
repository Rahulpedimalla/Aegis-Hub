import '../../domain/tts_provider.dart';

class ElevenLabsTtsProvider implements TtsProvider {
  @override
  String get providerName => 'elevenlabs';

  @override
  Future<void> speak(String text) async {
    // Integration point: synthesize and play voice response.
  }
}
