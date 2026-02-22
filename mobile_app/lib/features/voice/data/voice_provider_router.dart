import '../../../config/app_config.dart';
import '../../../core/network/api_client.dart';
import '../domain/realtime_voice_provider.dart';
import '../domain/stt_provider.dart';
import '../domain/tts_provider.dart';
import 'providers/backend_gemini_stt_provider.dart';
import 'providers/cartesia_tts_provider.dart';
import 'providers/elevenlabs_tts_provider.dart';
import 'providers/fallback_tts_provider.dart';
import 'providers/openai_realtime_provider.dart';
import 'providers/system_tts_provider.dart';

class VoiceProviderRouter {
  VoiceProviderRouter(this._config, {required ApiClient apiClient}) : _apiClient = apiClient;

  final AppConfig _config;
  final ApiClient _apiClient;

  SttProvider resolveStt() {
    switch (_config.sttProvider.toLowerCase()) {
      case 'backend_gemini':
      case 'gemini':
        return BackendGeminiSttProvider(_apiClient);
      case 'elevenlabs':
      case 'cartesia':
      case 'deepgram':
        // Use backend Gemini STT until direct provider API integrations are configured.
        return BackendGeminiSttProvider(_apiClient);
      default:
        return BackendGeminiSttProvider(_apiClient);
    }
  }

  TtsProvider resolveTts() {
    switch (_config.ttsProvider.toLowerCase()) {
      case 'system':
      case 'flutter_tts':
        return SystemTtsProvider();
      case 'elevenlabs':
        return ElevenLabsTtsProvider();
      case 'cartesia':
        return CartesiaTtsProvider();
      default:
        return FallbackTtsProvider();
    }
  }

  RealtimeVoiceProvider resolveRealtime() {
    switch (_config.realtimeProvider.toLowerCase()) {
      case 'openai_realtime':
      default:
        return OpenAiRealtimeProvider();
    }
  }
}
