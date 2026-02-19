import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'sos_controller.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(sosControllerProvider);
    final controller = ref.read(sosControllerProvider.notifier);

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Card(
              child: ListTile(
                leading: Icon(
                  state.location == null ? Icons.gps_not_fixed : Icons.gps_fixed,
                  color: state.location == null ? Colors.orange : Colors.green,
                ),
                title: const Text('Emergency Readiness'),
                subtitle: Text(
                  state.location == null
                      ? 'Location not locked yet'
                      : 'GPS ${state.location!.latitude.toStringAsFixed(5)}, ${state.location!.longitude.toStringAsFixed(5)}',
                ),
              ),
            ),
            const SizedBox(height: 20),
            Expanded(
              child: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    GestureDetector(
                      onTap: state.isSubmitting
                          ? null
                          : () async {
                              if (!state.isRecording) {
                                await controller.startSos();
                              } else {
                                await controller.endAndSubmit();
                              }
                            },
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 220),
                        width: state.isRecording ? 220 : 240,
                        height: state.isRecording ? 220 : 240,
                        decoration: BoxDecoration(
                          color: state.isRecording ? const Color(0xFF8F0E0E) : const Color(0xFFB32020),
                          shape: BoxShape.circle,
                          boxShadow: [
                            BoxShadow(
                              color: Colors.red.withValues(alpha: 0.35),
                              blurRadius: 24,
                              spreadRadius: 8,
                            ),
                          ],
                        ),
                        child: Center(
                          child: Text(
                            state.isRecording ? 'END\nSOS' : 'SOS',
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 40,
                              fontWeight: FontWeight.w800,
                              height: 1.0,
                            ),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 18),
                    Text(
                      state.isSubmitting ? 'Submitting...' : state.statusText,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    if (state.startedAt != null && state.isRecording) ...[
                      const SizedBox(height: 8),
                      Text(
                        'Voice capture started at ${state.startedAt!.toLocal()}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                    if (state.isRecording) ...[
                      const SizedBox(height: 12),
                      TextButton.icon(
                        onPressed: state.isSubmitting ? null : controller.cancelSos,
                        icon: const Icon(Icons.close),
                        label: const Text('Cancel SOS'),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            if (state.previewTranscript.isNotEmpty)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(
                    'Raw transcript: ${state.previewTranscript}',
                    style: const TextStyle(fontSize: 13),
                  ),
                ),
              ),
            if (state.lastResult != null)
              Card(
                color: state.lastResult!.isQueued
                    ? const Color(0xFFFFF3E0)
                    : const Color(0xFFE8F5E9),
                child: ListTile(
                  leading: Icon(
                    state.lastResult!.isQueued ? Icons.schedule_send : Icons.check_circle,
                    color: state.lastResult!.isQueued ? Colors.orange : Colors.green,
                  ),
                  title: Text('Ticket ${state.lastResult!.ticketId}'),
                  subtitle: Text(
                    state.lastResult!.reassuranceMessage ??
                        'Reassurance: stay safe and keep chat open for follow-up.',
                  ),
                ),
              ),
            if (state.errorMessage != null)
              Card(
                color: const Color(0xFFFFEBEE),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(
                    state.errorMessage!,
                    style: const TextStyle(color: Colors.red),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
