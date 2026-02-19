import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/providers.dart';
import '../domain/entities/chat_message.dart';
import 'chat_controller.dart';

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  late final TextEditingController _messageController;
  final _scrollController = ScrollController();
  bool _voiceMode = false;
  bool _recordingVoiceInput = false;

  @override
  void initState() {
    super.initState();
    _messageController = TextEditingController();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(chatControllerProvider.notifier).bootstrap();
    });
  }

  @override
  void dispose() {
    if (_recordingVoiceInput) {
      ref.read(audioCaptureServiceProvider).cancelRecording();
    }
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<String?>(activeChatSessionIdProvider, (_, next) {
      ref.read(chatControllerProvider.notifier).applyTicketContext(chatSessionId: next);
    });
    ref.listen<String?>(latestReassuranceMessageProvider, (_, next) {
      ref
          .read(chatControllerProvider.notifier)
          .applyTicketContext(chatSessionId: ref.read(activeChatSessionIdProvider), reassuranceMessage: next);
    });

    final state = ref.watch(chatControllerProvider);
    final controller = ref.read(chatControllerProvider.notifier);

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
      }
    });

    return SafeArea(
      child: Column(
        children: [
          ListTile(
            title: const Text('Aegis AI Follow-up'),
            subtitle: Text(
              state.chatSessionId == null
                  ? 'Local guidance mode'
                  : 'Session ${state.chatSessionId}',
            ),
            trailing: SegmentedButton<bool>(
              segments: const [
                ButtonSegment(value: false, label: Text('Text')),
                ButtonSegment(value: true, label: Text('Voice')),
              ],
              selected: {_voiceMode},
              onSelectionChanged: (values) {
                setState(() => _voiceMode = values.first);
              },
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              itemCount: state.messages.length,
              itemBuilder: (context, index) {
                final message = state.messages[index];
                final isUser = message.role == ChatRole.user;
                return Align(
                  alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    padding: const EdgeInsets.all(12),
                    constraints: const BoxConstraints(maxWidth: 320),
                    decoration: BoxDecoration(
                      color: isUser ? const Color(0xFFB32020) : Colors.white,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      message.text,
                      style: TextStyle(color: isUser ? Colors.white : Colors.black87),
                    ),
                  ),
                );
              },
            ),
          ),
          if (state.errorMessage != null)
            Padding(
              padding: const EdgeInsets.all(8),
              child: Text(
                state.errorMessage!,
                style: const TextStyle(color: Colors.red),
              ),
            ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _messageController,
                    minLines: 1,
                    maxLines: 4,
                    decoration: InputDecoration(
                      hintText: _voiceMode
                          ? 'Voice mode enabled; type fallback message'
                          : 'Type your update',
                      border: const OutlineInputBorder(),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: state.isSending
                      ? null
                      : () async {
                          if (!_voiceMode) {
                            final text = _messageController.text;
                            _messageController.clear();
                            await controller.sendMessage(text);
                            return;
                          }

                          if (!_recordingVoiceInput) {
                            final started = await ref.read(audioCaptureServiceProvider).startRecording();
                            if (started) {
                              setState(() => _recordingVoiceInput = true);
                            }
                            return;
                          }

                          final path = await ref.read(audioCaptureServiceProvider).stopRecording();
                          setState(() => _recordingVoiceInput = false);
                          final fallbackText = _messageController.text.trim();
                          _messageController.clear();
                          await controller.sendVoiceMessage(
                            audioPath: (path ?? '').trim().isEmpty ? null : path,
                            textHint: fallbackText.isEmpty ? null : fallbackText,
                          );
                        },
                  child: state.isSending
                      ? const SizedBox.square(
                          dimension: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Icon(
                          _voiceMode
                              ? (_recordingVoiceInput ? Icons.stop_circle_outlined : Icons.mic)
                              : Icons.send,
                        ),
                ),
              ],
            ),
          ),
          if (_voiceMode && _recordingVoiceInput)
            const Padding(
              padding: EdgeInsets.only(bottom: 12),
              child: Text(
                'Recording voice input... tap mic again to send.',
                style: TextStyle(color: Colors.red),
              ),
            ),
        ],
      ),
    );
  }
}
