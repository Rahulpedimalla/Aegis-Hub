class TicketSubmissionResult {
  const TicketSubmissionResult({
    required this.ticketId,
    required this.status,
    this.chatSessionId,
    this.reassuranceMessage,
    this.isQueued = false,
  });

  final String ticketId;
  final String status;
  final String? chatSessionId;
  final String? reassuranceMessage;
  final bool isQueued;
}
