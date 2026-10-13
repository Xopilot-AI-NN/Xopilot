import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';
import 'package:flet/flet.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter/services.dart';
import 'package:record/record.dart';
import 'package:camera/camera.dart';
import 'package:flutter_tts/flutter_tts.dart';

class XopilotMobileService extends FletService with WidgetsBindingObserver {
  static const channel = MethodChannel('ru.xopilot/mobile');
  XopilotMobileService({required super.control});
  AudioRecorder? _recorder;
  FlutterTts? _tts;
  AudioRecorder get recorder => _recorder ??= AudioRecorder();
  FlutterTts get tts => _tts ??= FlutterTts();
  CameraController? camera;
  StreamSubscription<Uint8List>? audio;
  Timer? audioDeadline;
  BytesBuilder pcm = BytesBuilder(copy: false);
  Completer<String>? utterance;
  bool paused = false;
  bool floating = false;
  int lifecycleEpoch = 0;
  int epoch = 0;
  Future<void> cameraQueue = Future.value();

  @override
  void init() {
    super.init();
    // Every camera/screen frame has new bytes. Flutter's default 100 MiB LRU
    // otherwise retains old previews after capture stops on low-RAM phones.
    PaintingBinding.instance.imageCache.maximumSizeBytes = 16 << 20;
    PaintingBinding.instance.imageCache.maximumSize = 64;
    WidgetsBinding.instance.addObserver(this);
    control.addInvokeMethodListener(_invokeMethod);
    channel.setMethodCallHandler((call) async {
      if (call.method != 'liveAction') return;
      final action = call.arguments;
      if (action == 'mute' || action == 'stop') await cancelAudio();
      if (action == 'stop') {
        floating = false;
        await closeCamera();
        await _tts?.stop();
      }
    });
  }

  Future<void> startAudio(bool segment) async {
    if (paused) throw StateError('Вернитесь в приложение для записи звука');
    if (audio != null) throw StateError('Микрофон уже используется');
    final attempt = ++epoch;
    pcm.clear();
    if (!await recorder.hasPermission()) throw StateError('Разрешите доступ к микрофону в настройках Android');
    if (attempt != epoch || paused) throw StateError('Запись отменена');
    final stream = await recorder.startStream(const RecordConfig(
      encoder: AudioEncoder.pcm16bits, sampleRate: 16000, numChannels: 1,
      autoGain: true, echoCancel: true, noiseSuppress: true));
    bool speaking = false;
    int silence = 0, active = 0;
    final before = <Uint8List>[];
    final pending = BytesBuilder(copy: false);
    if (attempt != epoch || paused) { await recorder.cancel(); throw StateError('Запись отменена'); }
    audio = stream.listen((chunk) {
      if (!segment) {
        final remaining = 30 * 16000 * 2 - pcm.length;
        if (remaining > 0) pcm.add(chunk.sublist(0, min(remaining, chunk.length)));
        if (pcm.length >= 30 * 16000 * 2) unawaited(stopAudio());
        return;
      }
      pending.add(chunk);
      final bytes = pending.takeBytes();
      int offset = 0;
      // Fixed 30 ms PCM16 frames: hold a short pre-roll while waiting for voice.
      while (bytes.length - offset >= 960) {
        final frame = Uint8List.fromList(bytes.sublist(offset, offset + 960));
        offset += 960;
        final view = ByteData.sublistView(frame);
        double square = 0;
        for (int i = 0; i < frame.length; i += 2) {
          final sample = view.getInt16(i, Endian.little);
          square += sample * sample;
        }
        final voiced = sqrt(square / 480) > 300;
        if (!speaking) {
          before.add(frame);
          if (before.length > 10) before.removeAt(0);
          active = voiced ? active + 1 : 0;
          if (active >= 6) {
            speaking = true;
            for (final part in before) pcm.add(part);
            before.clear();
          }
        } else {
          pcm.add(frame);
          silence = voiced ? 0 : silence + 1;
          if (silence >= 30 || pcm.length >= 30 * 16000 * 2) {
            unawaited(finishUtterance());
            return;
          }
        }
      }
      if (offset < bytes.length) pending.add(bytes.sublist(offset));
    }, onError: (Object error) {
      if (utterance != null && !utterance!.isCompleted) utterance!.completeError(error);
      unawaited(stopAudio());
    });
    if (!segment) audioDeadline = Timer(const Duration(seconds: 30), () => unawaited(stopAudio()));
  }

  Future<void> stopAudio() async {
    audioDeadline?.cancel(); audioDeadline = null;
    final stream = audio; audio = null;
    await _recorder?.stop();
    await stream?.cancel();
  }

  Future<void> finishUtterance() async {
    final result = utterance;
    if (result == null || result.isCompleted) return;
    // Complete once before the asynchronous device stop; repeated frames cannot
    // finish a segment twice. PCM is cleared after transferring this segment.
    result.complete(base64Encode(pcm.takeBytes()));
    await stopAudio();
  }

  Future<void> cancelAudio() async {
    epoch++;
    final result = utterance;
    if (result != null && !result.isCompleted) result.completeError(StateError('Запись отменена'));
    await stopAudio();
    pcm.clear();
  }

  Future<String> cameraFrame(dynamic args) {
    final result = Completer<String>();
    cameraQueue = cameraQueue.then((_) async {
      try {
        if (paused) throw StateError('Вернитесь в приложение для камеры');
        if (await channel.invokeMethod('cameraPermission') != true) {
          final cameras = await availableCameras();
          if (cameras.isEmpty) throw StateError('Камера не найдена');
          final chosen = cameras.firstWhere((c) => c.lensDirection == CameraLensDirection.front,
              orElse: () => cameras.first);
          final controller = CameraController(chosen, ResolutionPreset.medium, enableAudio: false);
          // Flutter requests the runtime permission while the Activity is
          // visible. The ongoing Camera2 session has no Activity lifecycle.
          try { await controller.initialize(); }
          finally { await controller.dispose(); }
        }
        final encoded = await channel.invokeMethod<String>('cameraFrame');
        if (encoded == null) throw StateError('Камера не вернула изображение');
        if (floating) await channel.invokeMethod('overlayFrame', {'frame': encoded});
        result.complete(encoded);
      } catch (error, trace) { result.completeError(error, trace); }
    });
    return result.future;
  }

  Future<void> closeCamera() {
    final closing = cameraQueue.then((_) async {
      final previous = camera; camera = null;
      await previous?.dispose();
      await channel.invokeMethod('cameraClose');
    });
    // Closing and taking a frame share a queue; a later frame cannot race with
    // dispose. Report a close failure to its caller without poisoning the queue.
    cameraQueue = closing.catchError((Object _) {});
    return closing;
  }

  Future<void> speak(dynamic args) async {
    final status = await channel.invokeMapMethod<String, dynamic>('speechEngines');
    if ((status?['engines'] as List?)?.isNotEmpty != true) {
      throw StateError('На телефоне нет движка синтеза речи. Установите его и скачайте офлайн-голоса в настройках Android.');
    }
    final locale = args['language'] == 'en' ? 'en' : 'ru';
    final voices = await tts.getVoices;
    final local = (voices as List).where((voice) =>
      voice['locale'].toString().startsWith(locale) &&
      (voice['network_required'] == false || voice['network_required'] == 'false')).toList();
    if (local.isEmpty) throw StateError('Установите офлайн-голос $locale в настройках синтеза речи Android');
    await tts.setVoice({'name': local.first['name'].toString(), 'locale': local.first['locale'].toString()});
    await tts.awaitSpeakCompletion(true);
    await tts.speak(args['text']);
  }

  Future<dynamic> _invokeMethod(String name, dynamic args) async {
    // Do not log arguments: they include private conversations and keys.
    switch (name) {
      case 'releaseMemory':
        if (audio != null || floating || camera != null) return false;
        return await channel.invokeMethod('releaseMemory');
      case 'overlayRequest':
      case 'overlayState':
        final enabled = await channel.invokeMethod(name, args);
        floating = enabled == true;
        return enabled;
      case 'overlayStop':
        floating = false;
        return await channel.invokeMethod(name, args);
      case 'viewportMetrics': return viewportMetrics();
      case 'audioStart': await startAudio(false); return null;
      case 'audioStop': await stopAudio(); return base64Encode(pcm.takeBytes());
      case 'audioCancel': await cancelAudio(); return null;
      case 'recordUtterance':
        utterance = Completer<String>();
        utterance!.future.ignore();
        try { await startAudio(true); return await utterance!.future; }
        finally { await stopAudio(); utterance = null; pcm.clear(); }
      case 'cameraFrame': return await cameraFrame(args);
      case 'cameraClose': await closeCamera(); return null;
      case 'speak': await speak(args); return null;
      case 'stopSpeech': await _tts?.stop(); return null;
      default: return await channel.invokeMethod(name, args);
    }
  }

  Map<String, double> viewportMetrics() {
    final view = WidgetsBinding.instance.platformDispatcher.views.first;
    final ratio = view.devicePixelRatio;
    return {'height': max(0.0, (view.physicalSize.height - view.viewInsets.bottom) / ratio),
            'keyboard': view.viewInsets.bottom / ratio};
  }

  @override
  void didChangeMetrics() {
    // Page MediaQuery can be inside a Scaffold that removes keyboard insets.
    // Read the platform view directly, without depending on that widget tree.
    control.triggerEvent('metrics', viewportMetrics());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive) return;
    final version = ++lifecycleEpoch;
    unawaited(updateLifecycle(state, version));
  }

  Future<void> updateLifecycle(AppLifecycleState state, int version) async {
    bool enabled = false;
    try { enabled = await channel.invokeMethod('overlayActive') == true; } catch (_) {}
    if (version != lifecycleEpoch) return;
    floating = enabled;
    paused = state != AppLifecycleState.resumed && !floating;
    if (!paused) return;
    await cancelAudio();
    await closeCamera();
    await _tts?.stop();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    control.removeInvokeMethodListener(_invokeMethod);
    channel.setMethodCallHandler(null);
    channel.invokeMethod('overlayStop');
    cancelAudio().whenComplete(() => _recorder?.dispose());
    closeCamera();
    _tts?.stop();
    channel.invokeMethod('screenStop');
    channel.invokeMethod('closeAll');
    super.dispose();
  }
}
