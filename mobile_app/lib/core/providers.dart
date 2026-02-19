import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/config_providers.dart';
import '../features/chat/data/repositories/chat_repository_impl.dart';
import '../features/chat/domain/repositories/chat_repository.dart';
import '../features/tickets/data/repositories/ticket_repository_impl.dart';
import '../features/tickets/domain/repositories/ticket_repository.dart';
import '../features/voice/data/voice_provider_router.dart';
import '../features/voice/domain/realtime_voice_provider.dart';
import '../features/voice/domain/stt_provider.dart';
import '../features/voice/domain/tts_provider.dart';
import 'network/api_client.dart';
import 'services/audio_capture_service.dart';
import 'services/connectivity_service.dart';
import 'services/device_context_service.dart';
import 'services/location_service.dart';
import 'storage/local_ticket_queue_store.dart';

final apiClientProvider = Provider<ApiClient>((ref) {
  final config = ref.watch(appConfigProvider);
  return ApiClient(config);
});

final connectivityServiceProvider = Provider<ConnectivityService>((_) => ConnectivityService());
final locationServiceProvider = Provider<LocationService>((_) => LocationService());
final deviceContextServiceProvider =
    Provider<DeviceContextService>((ref) => DeviceContextService(connectivityService: ref.watch(connectivityServiceProvider)));
final audioCaptureServiceProvider = Provider<AudioCaptureService>((_) => AudioCaptureService());
final ticketQueueStoreProvider = Provider<LocalTicketQueueStore>((_) => LocalTicketQueueStore());

final voiceProviderRouterProvider = Provider<VoiceProviderRouter>((ref) {
  final config = ref.watch(appConfigProvider);
  return VoiceProviderRouter(config);
});

final sttProviderProvider = Provider<SttProvider>((ref) => ref.watch(voiceProviderRouterProvider).resolveStt());
final ttsProviderProvider = Provider<TtsProvider>((ref) => ref.watch(voiceProviderRouterProvider).resolveTts());
final realtimeVoiceProviderProvider =
    Provider<RealtimeVoiceProvider>((ref) => ref.watch(voiceProviderRouterProvider).resolveRealtime());

final ticketRepositoryProvider = Provider<TicketRepository>((ref) {
  return TicketRepositoryImpl(
    apiClient: ref.watch(apiClientProvider),
    queueStore: ref.watch(ticketQueueStoreProvider),
    connectivityService: ref.watch(connectivityServiceProvider),
  );
});

final chatRepositoryProvider =
    Provider<ChatRepository>((ref) => ChatRepositoryImpl(ref.watch(apiClientProvider)));

final activeChatSessionIdProvider = StateProvider<String?>((_) => null);
final latestReassuranceMessageProvider = StateProvider<String?>((_) => null);
