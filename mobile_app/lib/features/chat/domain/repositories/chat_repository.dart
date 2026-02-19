import '../entities/chat_message.dart';

class ChatSendResult {
  const ChatSendResult({
    required this.replyText,
    this.transcript = '',
  });

  final String replyText;
  final String transcript;
}

abstract class ChatRepository {
  Future<ChatSendResult> sendMessage({
    required String chatSessionId,
    required ChatMessage message,
  });

  Future<ChatSendResult> sendVoiceMessage({
    required String chatSessionId,
    String? audioPath,
    String? textHint,
  });
}
