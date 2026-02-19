import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/providers.dart';
import '../domain/entities/chat_message.dart';

class ChatState {
  const ChatState({
    this.chatSessionId,
    this.messages = const [],
    this.isSending = false,
    this.errorMessage,
  });

  final String? chatSessionId;
  final List<ChatMessage> messages;
  final bool isSending;
  final String? errorMessage;

  ChatState copyWith({
    String? chatSessionId,
    List<ChatMessage>? messages,
    bool? isSending,
    String? errorMessage,
    bool clearError = false,
  }) {
    return ChatState(
      chatSessionId: chatSessionId ?? this.chatSessionId,
      messages: messages ?? this.messages,
      isSending: isSending ?? this.isSending,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class ChatController extends StateNotifier<ChatState> {
  ChatController(this._ref) : super(const ChatState());

  final Ref _ref;
  bool _initialized = false;

  void bootstrap() {
    if (_initialized) {
      return;
    }
    _initialized = true;
    final session = _ref.read(activeChatSessionIdProvider);
    final reassurance = _ref.read(latestReassuranceMessageProvider);
    final starter = reassurance ??
        'You are connected to Aegis support assistant. Share immediate safety status and injuries first.';
    state = state.copyWith(
      chatSessionId: session,
      messages: [
        ChatMessage(
          role: ChatRole.assistant,
          text: starter,
          timestampUtc: DateTime.now().toUtc(),
        ),
      ],
      clearError: true,
    );
  }

  void applyTicketContext({
    String? chatSessionId,
    String? reassuranceMessage,
  }) {
    final nextSessionId = chatSessionId ?? state.chatSessionId;
    if ((reassuranceMessage ?? '').trim().isEmpty) {
      state = state.copyWith(chatSessionId: nextSessionId);
      return;
    }

    final message = ChatMessage(
      role: ChatRole.assistant,
      text: reassuranceMessage!.trim(),
      timestampUtc: DateTime.now().toUtc(),
    );
    state = state.copyWith(
      chatSessionId: nextSessionId,
      messages: [...state.messages, message],
    );
  }

  Future<void> sendMessage(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || state.isSending) {
      return;
    }

    final userMessage = ChatMessage(
      role: ChatRole.user,
      text: trimmed,
      timestampUtc: DateTime.now().toUtc(),
    );
    state = state.copyWith(
      isSending: true,
      messages: [...state.messages, userMessage],
      clearError: true,
    );

    try {
      String replyText;
      if ((state.chatSessionId ?? '').isEmpty) {
        replyText =
            'Acknowledged. If you are in immediate danger, move to safe cover. How many people are with you and are there injuries?';
      } else {
        final result = await _ref.read(chatRepositoryProvider).sendMessage(
              chatSessionId: state.chatSessionId!,
              message: userMessage,
            );
        replyText = result.replyText.isNotEmpty
            ? result.replyText
            : 'Received. Please confirm current hazards and whether evacuation is possible.';
      }

      final assistantMessage = ChatMessage(
        role: ChatRole.assistant,
        text: replyText,
        timestampUtc: DateTime.now().toUtc(),
      );
      state = state.copyWith(
        isSending: false,
        messages: [...state.messages, assistantMessage],
      );

      await _ref.read(ttsProviderProvider).speak(replyText);
    } catch (_) {
      state = state.copyWith(
        isSending: false,
        errorMessage: 'Chat delivery failed. You can continue typing; messages will retry later.',
      );
    }
  }

  Future<void> sendVoiceMessage({
    String? audioPath,
    String? textHint,
  }) async {
    if (state.isSending) {
      return;
    }

    var userText = (textHint ?? '').trim();
    state = state.copyWith(isSending: true, clearError: true);

    try {
      String replyText;
      if ((state.chatSessionId ?? '').isEmpty) {
        if (userText.isEmpty) {
          userText = 'Need voice assistance.';
        }
        replyText =
            'Acknowledged. If you are in immediate danger, move to safe cover. How many people are with you and are there injuries?';
      } else {
        final result = await _ref.read(chatRepositoryProvider).sendVoiceMessage(
              chatSessionId: state.chatSessionId!,
              audioPath: audioPath,
              textHint: userText,
            );
        if (result.transcript.trim().isNotEmpty) {
          userText = result.transcript.trim();
        } else if (userText.isEmpty) {
          userText = 'Voice message received.';
        }
        replyText = result.replyText.isNotEmpty
            ? result.replyText
            : 'Received. Please confirm current hazards and whether evacuation is possible.';
      }

      final nextMessages = <ChatMessage>[
        ...state.messages,
        ChatMessage(
          role: ChatRole.user,
          text: userText,
          timestampUtc: DateTime.now().toUtc(),
        ),
        ChatMessage(
          role: ChatRole.assistant,
          text: replyText,
          timestampUtc: DateTime.now().toUtc(),
        ),
      ];
      state = state.copyWith(isSending: false, messages: nextMessages);
      await _ref.read(ttsProviderProvider).speak(replyText);
    } catch (_) {
      state = state.copyWith(
        isSending: false,
        errorMessage: 'Voice chat delivery failed. Try again or switch to text mode.',
      );
    }
  }
}

final chatControllerProvider = StateNotifierProvider<ChatController, ChatState>(
  (ref) => ChatController(ref),
);
