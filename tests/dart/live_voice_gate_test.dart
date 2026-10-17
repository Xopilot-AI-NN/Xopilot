/*
Файл: /tests/dart/live_voice_gate_test.dart
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Проверка тихой речи, стабильного шума и адаптации порога Live.
*/
import '../../extensions/flet_xopilot_mobile/src/flutter/flet_xopilot_mobile/lib/src/live_voice_gate.dart';
void check(bool value, String reason) { if (!value) throw StateError(reason); }
void main() {
  final gate = LiveVoiceGate();
  for (int i = 0; i < 200; i++) check(!gate.isVoiced(39), 'Quiet room is not speech');
  for (int i = 0; i < 8; i++) check(gate.isVoiced(250), 'Quiet speech must pass AEC gate');
  check(gate.noiseFloor < 45, 'Voice must not raise the noise floor');
  final noisy = LiveVoiceGate();
  for (int i = 0; i < 200; i++) noisy.isVoiced(100);
  check(!noisy.isVoiced(150), 'Raised ambient noise needs a higher threshold');
  check(noisy.isVoiced(392), 'Observed phone-level speech must remain detectable');
  print('LiveVoiceGate: all checks passed');
}
