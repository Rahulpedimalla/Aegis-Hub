import '../../domain/tts_provider.dart';
import 'system_tts_provider.dart';

class ElevenLabsTtsProvider implements TtsProvider {
  ElevenLabsTtsProvider() : _fallback = SystemTtsProvider();

  final SystemTtsProvider _fallback;

  @override
  String get providerName => 'elevenlabs';

  @override
  Future<void> speak(String text) async {
    // Fallback to system TTS until direct ElevenLabs API integration is configured.
    await _fallback.speak(text);
  }
}
