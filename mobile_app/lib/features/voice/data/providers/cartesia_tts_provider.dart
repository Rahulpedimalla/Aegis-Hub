import '../../domain/tts_provider.dart';

class CartesiaTtsProvider implements TtsProvider {
  @override
  String get providerName => 'cartesia';

  @override
  Future<void> speak(String text) async {
    // Integration point: synthesize and play voice response.
    // Intentionally no-op in baseline implementation.
  }
}
