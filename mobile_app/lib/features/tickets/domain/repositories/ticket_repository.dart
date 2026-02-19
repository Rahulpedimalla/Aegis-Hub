import '../entities/ticket_payload.dart';
import '../entities/ticket_submission_result.dart';

abstract class TicketRepository {
  Future<TicketSubmissionResult> submitTicket(TicketPayload payload);
  Future<void> retryPendingTickets();
}
