enum ChatRole { system, user, assistant }

class ChatMessage {
  const ChatMessage({
    required this.role,
    required this.text,
    required this.timestampUtc,
  });

  final ChatRole role;
  final String text;
  final DateTime timestampUtc;
}
