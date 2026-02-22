import '../../domain/tts_provider.dart';
import 'system_tts_provider.dart';

class FallbackTtsProvider implements TtsProvider {
  FallbackTtsProvider() : _systemTts = SystemTtsProvider();

  final SystemTtsProvider _systemTts;

  @override
  String get providerName => 'fallback';

  @override
  Future<void> speak(String text) async {
    await _systemTts.speak(text);
  }
}
