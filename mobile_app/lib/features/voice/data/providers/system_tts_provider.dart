import 'package:flutter_tts/flutter_tts.dart';

import '../../domain/tts_provider.dart';

class SystemTtsProvider implements TtsProvider {
  SystemTtsProvider() {
    _tts.setSpeechRate(0.45);
    _tts.setVolume(1.0);
    _tts.setPitch(1.0);
    _tts.setLanguage('en-US');
  }

  final FlutterTts _tts = FlutterTts();

  @override
  String get providerName => 'system';

  @override
  Future<void> speak(String text) async {
    final message = text.trim();
    if (message.isEmpty) {
      return;
    }
    await _tts.stop();
    await _tts.speak(message);
  }
}
