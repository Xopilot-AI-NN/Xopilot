package ru.xopilot.mobile;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.*;
import android.util.Base64;
import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;

/** User-approved screen frames in memory. No recording files or exported service. */
public final class ScreenCaptureService extends Service {
    interface Started { void complete(String error); }
    static volatile ScreenCaptureService current;
    private static Started started;
    private static final String STOP = "ru.xopilot.mobile.STOP_SCREEN";
    private MediaProjection projection;
    private VirtualDisplay display;
    private ImageReader reader;
    private HandlerThread images;
    private final Handler main = new Handler(Looper.getMainLooper());
    private volatile byte[] frame;
    private volatile boolean closing;
    private long lastFrame;

    static void begin(Context context, int code, Intent consent, Started callback) {
        started = callback;
        try {
            context.startForegroundService(new Intent(context, ScreenCaptureService.class)
                .putExtra("code", code).putExtra("consent", consent));
        } catch (RuntimeException error) { complete("Не удалось начать демонстрацию экрана"); }
    }

    private static void complete(String error) {
        Started callback = started; started = null;
        if (callback != null) callback.complete(error);
    }

    static void stop(Context context) {
        context.stopService(new Intent(context, ScreenCaptureService.class));
        complete("Демонстрация экрана остановлена");
    }

    String latestFrame() {
        byte[] bytes = frame;
        if (bytes == null || closing) throw new IllegalStateException("Ожидаем изображение экрана…");
        return Base64.encodeToString(bytes, Base64.NO_WRAP);
    }

    boolean ready() { return frame != null && !closing; }
    byte[] previewBytes() { return closing ? null : frame; }

    @Override public void onCreate() {
        super.onCreate();
        NotificationManager notifications = getSystemService(NotificationManager.class);
        notifications.createNotificationChannel(new NotificationChannel("xopilot_screen",
            "Демонстрация экрана", NotificationManager.IMPORTANCE_LOW));
        PendingIntent stop = PendingIntent.getService(this, 0,
            new Intent(this, ScreenCaptureService.class).setAction(STOP), PendingIntent.FLAG_IMMUTABLE);
        Notification notice = new Notification.Builder(this, "xopilot_screen")
            .setSmallIcon(android.R.drawable.ic_menu_view).setContentTitle("Xopilot · экран включён")
            .setContentText("Изображение передаётся ИИ только с вашим вопросом")
            .setOngoing(true).addAction(new Notification.Action.Builder(null, "Остановить", stop).build()).build();
        if (Build.VERSION.SDK_INT >= 29) startForeground(1201, notice, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
        else startForeground(1201, notice);
    }

    @Override public int onStartCommand(Intent intent, int flags, int id) {
        if (intent == null || STOP.equals(intent.getAction())) { stopSelf(); return START_NOT_STICKY; }
        if (projection != null) return START_NOT_STICKY;
        try {
            MediaProjectionManager manager = getSystemService(MediaProjectionManager.class);
            Intent consent = intent.getParcelableExtra("consent");
            projection = manager.getMediaProjection(intent.getIntExtra("code", Activity.RESULT_CANCELED), consent);
            images = new HandlerThread("xopilot-screen"); images.start();
            projection.registerCallback(new MediaProjection.Callback() {
                @Override public void onStop() { stopSelf(); }
                @Override public void onCapturedContentResize(int width, int height) {
                    if (!closing && display != null) resize(width, height);
                }
            }, main);
            android.util.DisplayMetrics metrics = getResources().getDisplayMetrics();
            int[] size = boundedSize(metrics.widthPixels, metrics.heightPixels);
            reader = makeReader(size[0], size[1]);
            // One virtual display per consent token, including on Android 14+.
            display = projection.createVirtualDisplay("Xopilot screen", size[0], size[1], metrics.densityDpi,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR, reader.getSurface(), null, main);
            current = this;
            // Permission alone doesn't mean the display is producing frames.
            // Report success only after the first image, before the UI enables
            // questions/rotation controls against an uninitialized capture.
            main.postDelayed(() -> {
                if (!ready() && !closing) {
                    complete("Не удалось получить первый кадр экрана. Повторите подключение.");
                    stopSelf();
                }
            }, 10000);
        } catch (RuntimeException error) {
            complete("Не удалось получить доступ к экрану. Повторите системное разрешение."); stopSelf();
        }
        return START_NOT_STICKY;
    }

    private int[] boundedSize(int width, int height) {
        double scale = Math.min(1.0, 1024.0 / Math.max(width, height));
        return new int[] {Math.max(1, (int)(width * scale)), Math.max(1, (int)(height * scale))};
    }

    private ImageReader makeReader(int width, int height) {
        ImageReader next = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2);
        next.setOnImageAvailableListener(source -> {
            try (Image image = source.acquireLatestImage()) {
                if (image == null || closing || SystemClock.elapsedRealtime() - lastFrame < 900) return;
                lastFrame = SystemClock.elapsedRealtime();
                Image.Plane plane = image.getPlanes()[0];
                int paddedWidth = image.getWidth() + (plane.getRowStride() - plane.getPixelStride() * image.getWidth()) / plane.getPixelStride();
                Bitmap padded = Bitmap.createBitmap(paddedWidth, image.getHeight(), Bitmap.Config.ARGB_8888);
                Bitmap cropped = null;
                try {
                    ByteBuffer pixels = plane.getBuffer();
                    // Some devices omit the unused padding after the final row.
                    if (pixels.remaining() < padded.getByteCount()) {
                        ByteBuffer complete = ByteBuffer.allocate(padded.getByteCount());
                        complete.put(pixels);
                        complete.rewind();
                        pixels = complete;
                    }
                    padded.copyPixelsFromBuffer(pixels);
                    cropped = Bitmap.createBitmap(padded, 0, 0, image.getWidth(), image.getHeight());
                    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                    cropped.compress(Bitmap.CompressFormat.JPEG, 80, bytes);
                    if (!closing) {
                        boolean first = frame == null;
                        frame = bytes.toByteArray();
                        if (first) main.post(() -> complete(null));
                    }
                } finally {
                    if (cropped != null && cropped != padded) cropped.recycle();
                    padded.recycle();
                }
            } catch (RuntimeException ignored) {
                // Rotation/stop may close a reader while a queued frame arrives.
            }
        }, new Handler(images.getLooper()));
        return next;
    }

    private void resize(int width, int height) {
        if (width <= 0 || height <= 0) return;
        int[] size = boundedSize(width, height);
        if (reader.getWidth() == size[0] && reader.getHeight() == size[1]) return;
        ImageReader previous = reader;
        reader = makeReader(size[0], size[1]);
        display.resize(size[0], size[1], getResources().getDisplayMetrics().densityDpi);
        display.setSurface(reader.getSurface()); previous.close();
    }

    @Override public void onTaskRemoved(Intent root) { stopSelf(); }
    @Override public void onDestroy() {
        closing = true; frame = null;
        if (current == this) current = null;
        if (display != null) display.release();
        if (reader != null) reader.close();
        if (projection != null) projection.stop();
        if (images != null) images.quitSafely();
        complete("Демонстрация экрана остановлена");
        stopForeground(STOP_FOREGROUND_REMOVE);
        super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent) { return null; }
}
