import '../../../../core/network/api_client.dart';
import '../../../tickets/domain/entities/voice_transcript.dart';
import '../../domain/stt_provider.dart';

class BackendGeminiSttProvider implements SttProvider {
  BackendGeminiSttProvider(this._apiClient);

  final ApiClient _apiClient;

  @override
  String get providerName => 'backend_gemini';

  @override
  Future<VoiceTranscript> transcribeFile({
    required String audioPath,
    String languageCode = 'en-IN',
    String? audioMimeType,
    String? audioFileName,
  }) async {
    final result = await _apiClient.transcribeAudio(
      audioPath: audioPath,
      languageCode: languageCode,
      audioMimeType: audioMimeType,
      audioFileName: audioFileName,
    );
    return VoiceTranscript(
      rawText: (result['transcript'] ?? '').trim(),
      provider: result['provider'] ?? 'gemini',
      model: 'gemini-2.5-flash',
      language: result['language'] ?? languageCode,
    );
  }
}
