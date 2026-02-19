import '../../../tickets/domain/entities/voice_transcript.dart';
import '../../domain/stt_provider.dart';

class CartesiaSttProvider implements SttProvider {
  @override
  String get providerName => 'cartesia';

  @override
  Future<VoiceTranscript> transcribeFile({
    required String audioPath,
    String languageCode = 'en',
  }) async {
    return const VoiceTranscript(
      rawText: '[raw transcript pending provider integration]',
      provider: 'cartesia',
      model: 'ink-stt',
      language: 'en',
    );
  }
}
