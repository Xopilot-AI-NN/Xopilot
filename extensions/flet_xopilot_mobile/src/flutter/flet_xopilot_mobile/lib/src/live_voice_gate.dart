/*
Файл: /extensions/flet_xopilot_mobile/lib/src/live_voice_gate.dart
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Порог голосового перебивания с учётом фонового шума после эхоподавления.
*/
import 'dart:math';

class LiveVoiceGate {
  double noiseFloor = 40;
  bool isVoiced(double rms) {
    final threshold = max(140.0, min(450.0, noiseFloor * 3));
    final voiced = rms > threshold;
    // Do not learn a speaker's voice as background noise.
    if (!voiced) noiseFloor = noiseFloor * .98 + rms * .02;
    return voiced;
  }
}
