/*
Файл: /extensions/flet_xopilot_mobile/android/LiveMicrophone.java
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: PCM16 микрофона с неблокирующим чтением и независимой остановкой.
*/
package ru.xopilot.mobile;

import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.media.audiofx.AcousticEchoCanceler;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import io.flutter.plugin.common.EventChannel;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicInteger;

final class LiveMicrophone implements EventChannel.StreamHandler {
    private final Handler main = new Handler(Looper.getMainLooper());
    private EventChannel.EventSink sink;
    private Take take;

    private static final class Take {
        final AudioRecord recorder;
        AcousticEchoCanceler echo;
        final AtomicInteger pending = new AtomicInteger();
        volatile boolean running = true;
        Take(AudioRecord recorder) { this.recorder = recorder; }
    }

    @Override public void onListen(Object args, EventChannel.EventSink events) { sink = events; }
    @Override public void onCancel(Object args) { stop(); sink = null; }

    @SuppressWarnings("MissingPermission")
    boolean start(boolean echoCancellation) {
        if (take != null) throw new IllegalStateException("Микрофон уже используется");
        if (sink == null) throw new IllegalStateException("Канал микрофона не открыт");
        int size = AudioRecord.getMinBufferSize(48000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
        if (size <= 0) throw new IllegalStateException("Микрофон не поддерживает PCM16 48 кГц");
        AudioRecord recorder = new AudioRecord(echoCancellation ? MediaRecorder.AudioSource.VOICE_COMMUNICATION : MediaRecorder.AudioSource.VOICE_RECOGNITION,
            48000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, Math.max(size * 2, 8192));
        if (recorder.getState() != AudioRecord.STATE_INITIALIZED) {
            recorder.release(); throw new IllegalStateException("Не удалось открыть микрофон");
        }
        Take current = new Take(recorder);
        if (echoCancellation) {
            try {
                if (AcousticEchoCanceler.isAvailable()) {
                    current.echo = AcousticEchoCanceler.create(recorder.getAudioSessionId());
                    if (current.echo != null) current.echo.setEnabled(true);
                }
                if (current.echo == null || !current.echo.getEnabled())
                    throw new IllegalStateException("barge_in_unavailable: эхоподавление недоступно");
            } catch (RuntimeException error) {
                if (current.echo != null) current.echo.release();
                recorder.release(); throw error;
            }
        }
        try { recorder.startRecording(); }
        catch (RuntimeException error) {
            if (current.echo != null) current.echo.release();
            recorder.release(); throw error;
        }
        take = current;
        Thread worker = new Thread(() -> capture(current), "xopilot-microphone");
        worker.setDaemon(true);
        worker.start();
        return current.echo != null && current.echo.getEnabled();
    }

    private void capture(Take current) {
        byte[] buffer = new byte[2880];
        long received = 0, reported = System.currentTimeMillis();
        int sum = 0, samples = 0;
        try {
            while (current.running) {
                int count = current.recorder.read(buffer, 0, buffer.length, AudioRecord.READ_NON_BLOCKING);
                if (count < 0) throw new IllegalStateException("Микрофон отключён (" + count + ")");
                received += count;
                byte[] converted = new byte[(count / 2 + 2) / 3 * 2];
                int written = 0;
                // Three 48 kHz samples per 16 kHz sample; retain partial groups.
                for (int i = 0; i + 1 < count; i += 2) {
                    sum += (buffer[i] & 255) | (buffer[i + 1] << 8);
                    if (++samples == 3) {
                        int value = sum / 3;
                        converted[written++] = (byte)value;
                        converted[written++] = (byte)(value >> 8);
                        sum = 0; samples = 0;
                    }
                }
                if (written > 0 && current.pending.get() < 4) {
                    byte[] chunk = Arrays.copyOf(converted, written);
                    current.pending.incrementAndGet();
                    main.post(() -> {
                        try { if (take == current && current.running && sink != null) sink.success(chunk); }
                        finally { current.pending.decrementAndGet(); }
                    });
                }
                if (System.currentTimeMillis() - reported >= 5000) {
                    Log.i("XopilotAudio", "Native received bytes=" + received + ", queued=" + current.pending.get());
                    reported = System.currentTimeMillis();
                }
                Thread.sleep(10);
            }
        } catch (Exception error) {
            if (current.running) main.post(() -> {
                if (take == current && sink != null) {
                    sink.error("microphone", error.getMessage(), null);
                    stop();
                }
            });
        } finally {
            main.post(() -> {
                try { if (take == current) stop(); }
                finally {
                    if (current.echo != null) current.echo.release();
                    current.recorder.release();
                }
            });
        }
    }

    void stop() {
        Take current = take;
        take = null;
        if (current == null) return;
        current.running = false;
        // Do not enqueue stop behind a blocking read or behind model inference.
        current.recorder.stop();
    }
}
