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

  static const Map<String, int> _wordNumbers = {
    'zero': 0,
    'one': 1,
    'two': 2,
    'three': 3,
    'four': 4,
    'five': 5,
    'six': 6,
    'seven': 7,
    'eight': 8,
    'nine': 9,
    'ten': 10,
    'eleven': 11,
    'twelve': 12,
    'thirteen': 13,
    'fourteen': 14,
    'fifteen': 15,
    'sixteen': 16,
    'seventeen': 17,
    'eighteen': 18,
    'nineteen': 19,
    'twenty': 20,
    'thirty': 30,
    'forty': 40,
    'fifty': 50,
  };

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
        replyText = _buildLocalGuidanceReply(trimmed);
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
      final localReply = _buildLocalGuidanceReply(trimmed);
      final assistantMessage = ChatMessage(
        role: ChatRole.assistant,
        text: localReply,
        timestampUtc: DateTime.now().toUtc(),
      );
      state = state.copyWith(
        isSending: false,
        messages: [...state.messages, assistantMessage],
        errorMessage: 'Live chat unavailable. Local guidance mode is active.',
      );
      await _ref.read(ttsProviderProvider).speak(localReply);
    }
  }

  Future<void> sendVoiceMessage({
    String? audioPath,
    String? audioMimeType,
    String? audioFileName,
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
        replyText = _buildLocalGuidanceReply(userText);
      } else {
        final result = await _ref.read(chatRepositoryProvider).sendVoiceMessage(
              chatSessionId: state.chatSessionId!,
              audioPath: audioPath,
              audioMimeType: audioMimeType,
              audioFileName: audioFileName,
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
      if (userText.isNotEmpty) {
        final localReply = _buildLocalGuidanceReply(userText);
        final nextMessages = <ChatMessage>[
          ...state.messages,
          ChatMessage(
            role: ChatRole.user,
            text: userText,
            timestampUtc: DateTime.now().toUtc(),
          ),
          ChatMessage(
            role: ChatRole.assistant,
            text: localReply,
            timestampUtc: DateTime.now().toUtc(),
          ),
        ];
        state = state.copyWith(
          isSending: false,
          messages: nextMessages,
          errorMessage: 'Voice service unavailable. Continued with local guidance.',
        );
        await _ref.read(ttsProviderProvider).speak(localReply);
        return;
      }
      state = state.copyWith(
        isSending: false,
        errorMessage: 'Voice chat delivery failed. Try again or switch to text mode.',
      );
    }
  }

  String _buildLocalGuidanceReply(String latestUserText) {
    final fullContext = [
      ...state.messages
          .where((message) => message.role == ChatRole.user)
          .map((message) => message.text),
      latestUserText,
    ].join(' ').toLowerCase();

    final peopleHint = _extractPeopleCount(fullContext);
    final hasInjury = _containsAny(fullContext, const ['injur', 'bleed', 'fracture', 'burn', 'unconscious']);
    final hasFire = _containsAny(fullContext, const ['fire', 'smoke', 'flame', 'gas leak', 'explosion']);
    final hasFlood = _containsAny(fullContext, const ['flood', 'water', 'submerged', 'river', 'drown']);
    final hasTrapped = _containsAny(fullContext, const ['trapped', 'stuck', 'blocked', 'collapsed']);

    if (hasFire) {
      final question = _nextUnaskedQuestion(const [
        'Are exits open or is anyone trapped inside?',
        'Is the smoke getting thicker and are gas cylinders nearby?',
      ]);
      return 'Move away from smoke, stay low while moving, and switch off nearby gas only if safe. $question';
    }

    if (hasFlood) {
      final question = _nextUnaskedQuestion(const [
        'What is the current water depth and is it still rising?',
        'Can you share a nearby landmark for rescue navigation?',
      ]);
      final peopleLine =
          peopleHint != null ? 'You reported about $peopleHint people affected. ' : '';
      return '${peopleLine}Move to higher ground and avoid fast-moving water or exposed wires. $question';
    }

    if (hasInjury) {
      final question = _nextUnaskedQuestion(const [
        'How many people are unconscious or bleeding heavily right now?',
        'Can you confirm who needs immediate evacuation first?',
      ]);
      final peopleLine =
          peopleHint != null ? 'Understood, around $peopleHint people are affected. ' : '';
      return '${peopleLine}If safe, control bleeding with firm pressure and keep injured people warm. $question';
    }

    if (hasTrapped) {
      return 'Avoid unstable structures and keep voice contact with trapped people if possible. Can you confirm how many are trapped and from which side access is safest?';
    }

    final question = _nextUnaskedQuestion(const [
      'How many people are with you and are there injuries?',
      'Please share immediate hazards around you and whether evacuation is possible.',
    ]);
    return 'Acknowledged. Move to safe cover and stay connected. $question';
  }

  String _nextUnaskedQuestion(List<String> options) {
    final askedText = state.messages
        .where((message) => message.role == ChatRole.assistant)
        .map((message) => message.text.toLowerCase())
        .join(' ');
    for (final option in options) {
      if (!askedText.contains(option.toLowerCase())) {
        return option;
      }
    }
    return options.last;
  }

  bool _containsAny(String haystack, List<String> needles) {
    for (final needle in needles) {
      if (haystack.contains(needle)) {
        return true;
      }
    }
    return false;
  }

  int? _extractPeopleCount(String text) {
    final digitMatches = RegExp(r'\b(\d{1,4})\b').allMatches(text);
    var maxValue = 0;
    for (final match in digitMatches) {
      final value = int.tryParse(match.group(1) ?? '');
      if (value != null && value > maxValue) {
        maxValue = value;
      }
    }

    final tokens = text.split(RegExp(r'[^a-z0-9]+')).where((token) => token.isNotEmpty).toList();
    for (final token in tokens) {
      final value = _wordNumbers[token];
      if (value != null && value > maxValue) {
        maxValue = value;
      }
    }

    if (maxValue <= 0) {
      return null;
    }
    return maxValue;
  }
}

final chatControllerProvider = StateNotifierProvider<ChatController, ChatState>(
  (ref) => ChatController(ref),
);
