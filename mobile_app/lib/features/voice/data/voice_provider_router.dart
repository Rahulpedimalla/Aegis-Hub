import '../../../config/app_config.dart';
import '../domain/realtime_voice_provider.dart';
import '../domain/stt_provider.dart';
import '../domain/tts_provider.dart';
import 'providers/cartesia_stt_provider.dart';
import 'providers/cartesia_tts_provider.dart';
import 'providers/deepgram_stt_provider.dart';
import 'providers/elevenlabs_stt_provider.dart';
import 'providers/elevenlabs_tts_provider.dart';
import 'providers/fallback_tts_provider.dart';
import 'providers/openai_realtime_provider.dart';

class VoiceProviderRouter {
  VoiceProviderRouter(this._config);

  final AppConfig _config;

  SttProvider resolveStt() {
    switch (_config.sttProvider.toLowerCase()) {
      case 'elevenlabs':
        return ElevenLabsSttProvider();
      case 'cartesia':
        return CartesiaSttProvider();
      case 'deepgram':
      default:
        return DeepgramSttProvider();
    }
  }

  TtsProvider resolveTts() {
    switch (_config.ttsProvider.toLowerCase()) {
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
