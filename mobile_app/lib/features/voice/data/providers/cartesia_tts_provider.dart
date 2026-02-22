import '../../domain/tts_provider.dart';
import 'system_tts_provider.dart';

class CartesiaTtsProvider implements TtsProvider {
  CartesiaTtsProvider() : _fallback = SystemTtsProvider();

  final SystemTtsProvider _fallback;

  @override
  String get providerName => 'cartesia';

  @override
  Future<void> speak(String text) async {
    // Fallback to system TTS until direct Cartesia API integration is configured.
    await _fallback.speak(text);
  }
}
