import '../../../../core/network/api_client.dart';
import '../../../../core/storage/local_ticket_queue_store.dart';
import '../../../../core/services/connectivity_service.dart';
import '../../domain/entities/ticket_payload.dart';
import '../../domain/entities/ticket_submission_result.dart';
import '../../domain/repositories/ticket_repository.dart';

class TicketRepositoryImpl implements TicketRepository {
  TicketRepositoryImpl({
    required ApiClient apiClient,
    required LocalTicketQueueStore queueStore,
    required ConnectivityService connectivityService,
  })  : _apiClient = apiClient,
        _queueStore = queueStore,
        _connectivityService = connectivityService;

  final ApiClient _apiClient;
  final LocalTicketQueueStore _queueStore;
  final ConnectivityService _connectivityService;

  @override
  Future<TicketSubmissionResult> submitTicket(TicketPayload payload) async {
    final hasNetwork = await _connectivityService.hasNetwork();
    if (!hasNetwork) {
      await _queueStore.enqueue(payload.toQueueJson());
      return TicketSubmissionResult(
        ticketId: payload.externalId,
        status: 'queued_offline',
        isQueued: true,
        reassuranceMessage: 'Ticket queued locally. We will send when network is available.',
      );
    }

    try {
      return await _apiClient.submitTicket(payload);
    } on RecoverableNetworkException {
      await _queueStore.enqueue(payload.toQueueJson());
      return TicketSubmissionResult(
        ticketId: payload.externalId,
        status: 'queued_retry',
        isQueued: true,
        reassuranceMessage: 'Ticket queued for retry due to temporary network/server issue.',
      );
    }
  }

  @override
  Future<void> retryPendingTickets() async {
    final hasNetwork = await _connectivityService.hasNetwork();
    if (!hasNetwork) {
      return;
    }

    final pending = await _queueStore.readAll();
    for (final entry in pending) {
      final payload = TicketPayload.fromQueueJson(entry);
      try {
        await _apiClient.submitTicket(payload);
        await _queueStore.removeByExternalId(payload.externalId);
      } on RecoverableNetworkException {
        break;
      } catch (_) {
        // Keep failed records for later retries.
      }
    }
  }
}
