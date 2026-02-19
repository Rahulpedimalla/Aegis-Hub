import '../../../../core/network/api_client.dart';
import '../../domain/entities/chat_message.dart';
import '../../domain/repositories/chat_repository.dart';

class ChatRepositoryImpl implements ChatRepository {
  ChatRepositoryImpl(this._apiClient);

  final ApiClient _apiClient;

  @override
  Future<ChatSendResult> sendMessage({
    required String chatSessionId,
    required ChatMessage message,
  }) async {
    final reply = await _apiClient.sendChatMessage(
      chatSessionId: chatSessionId,
      message: message,
    );
    return ChatSendResult(replyText: reply);
  }

  @override
  Future<ChatSendResult> sendVoiceMessage({
    required String chatSessionId,
    String? audioPath,
    String? textHint,
  }) async {
    final result = await _apiClient.sendVoiceChatMessage(
      chatSessionId: chatSessionId,
      audioPath: audioPath,
      textHint: textHint,
    );
    return ChatSendResult(
      replyText: result['reply_text'] ?? '',
      transcript: result['transcript'] ?? '',
    );
  }
}
