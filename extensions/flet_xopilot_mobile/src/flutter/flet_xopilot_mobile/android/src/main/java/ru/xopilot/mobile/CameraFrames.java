package ru.xopilot.mobile;

import android.Manifest;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.*;
import android.hardware.camera2.*;
import android.media.*;
import android.os.*;
import android.util.*;
import android.util.Base64;
import java.io.*;
import java.nio.ByteBuffer;
import java.util.*;
import io.flutter.plugin.common.MethodChannel;

/** Camera2 session independent of Activity/CameraX lifecycle; frames only in memory. */
final class CameraFrames {
    private final Context context;
    private final Handler main = new Handler(Looper.getMainLooper());
    private HandlerThread thread;
    private Handler handler;
    private CameraDevice camera;
    private CameraCaptureSession session;
    private ImageReader reader;
    private final List<MethodChannel.Result> pending = new ArrayList<>();
    private volatile byte[] latest;
    private long lastFrame;
    private volatile int generation;
    private int rotation;
    private boolean front;

    CameraFrames(Context context) { this.context = context; }
    boolean permission() { return context.checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED; }

    void frame(MethodChannel.Result result) {
        if (!permission()) { result.error("camera_permission", "Разрешите доступ к камере", null); return; }
        byte[] bytes = latest;
        if (bytes != null) { result.success(Base64.encodeToString(bytes, Base64.NO_WRAP)); return; }
        pending.add(result);
        if (thread != null) return;
        int version = ++generation;
        try {
            CameraManager manager = context.getSystemService(CameraManager.class);
            String selected = null;
            for (String id : manager.getCameraIdList()) {
                CameraCharacteristics properties = manager.getCameraCharacteristics(id);
                if (selected == null) selected = id;
                if (Objects.equals(properties.get(CameraCharacteristics.LENS_FACING), CameraCharacteristics.LENS_FACING_FRONT)) {
                    selected = id; break;
                }
            }
            if (selected == null) throw new IllegalStateException("Камера не найдена");
            CameraCharacteristics properties = manager.getCameraCharacteristics(selected);
            front = Objects.equals(properties.get(CameraCharacteristics.LENS_FACING), CameraCharacteristics.LENS_FACING_FRONT);
            Integer sensor = properties.get(CameraCharacteristics.SENSOR_ORIENTATION);
            rotation = sensor == null ? 0 : sensor;
            Size[] supported = properties.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP).getOutputSizes(ImageFormat.YUV_420_888);
            Size size = Arrays.stream(supported).filter(s -> s.getWidth() <= 640 && s.getHeight() <= 480)
                .max(Comparator.comparingInt(s -> s.getWidth() * s.getHeight())).orElse(supported[supported.length - 1]);
            thread = new HandlerThread("xopilot-camera"); thread.start(); handler = new Handler(thread.getLooper());
            reader = ImageReader.newInstance(size.getWidth(), size.getHeight(), ImageFormat.YUV_420_888, 2);
            reader.setOnImageAvailableListener(source -> read(source, version), handler);
            manager.openCamera(selected, new CameraDevice.StateCallback() {
                @Override public void onOpened(CameraDevice device) {
                    if (version != generation) { device.close(); return; }
                    camera = device;
                    try {
                        device.createCaptureSession(Collections.singletonList(reader.getSurface()), new CameraCaptureSession.StateCallback() {
                            @Override public void onConfigured(CameraCaptureSession configured) {
                                if (version != generation) { configured.close(); return; }
                                session = configured;
                                try {
                                    CaptureRequest.Builder request = device.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);
                                    request.addTarget(reader.getSurface());
                                    request.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_VIDEO);
                                    configured.setRepeatingRequest(request.build(), null, handler);
                                } catch (Exception error) { fail(version); }
                            }
                            @Override public void onConfigureFailed(CameraCaptureSession failed) { fail(version); }
                        }, main);
                    } catch (Exception error) { fail(version); }
                }
                @Override public void onDisconnected(CameraDevice device) { device.close(); fail(version); }
                @Override public void onError(CameraDevice device, int error) { device.close(); fail(version); }
            }, main);
            main.postDelayed(() -> { if (version == generation && latest == null) { fail(version); } }, 10000);
        } catch (Exception error) { fail(version); }
    }

    private void read(ImageReader source, int version) {
        try (Image image = source.acquireLatestImage()) {
            if (image == null || version != generation || SystemClock.elapsedRealtime() - lastFrame < 700) return;
            lastFrame = SystemClock.elapsedRealtime();
            int w = image.getWidth(), h = image.getHeight();
            byte[] nv21 = new byte[w * h * 3 / 2];
            Image.Plane[] planes = image.getPlanes();
            copy(planes[0], w, h, nv21, 0, 1);
            copy(planes[2], w / 2, h / 2, nv21, w * h, 2);
            copy(planes[1], w / 2, h / 2, nv21, w * h + 1, 2);
            ByteArrayOutputStream encoded = new ByteArrayOutputStream();
            new YuvImage(nv21, ImageFormat.NV21, w, h, null).compressToJpeg(new Rect(0, 0, w, h), 78, encoded);
            byte[] bytes = encoded.toByteArray();
            int displayRotation = context.getSystemService(android.view.WindowManager.class).getDefaultDisplay().getRotation() * 90;
            int uprightRotation = (rotation + (front ? displayRotation : -displayRotation) + 360) % 360;
            if (uprightRotation != 0) {
                Bitmap bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
                Matrix matrix = new Matrix(); matrix.postRotate(uprightRotation);
                Bitmap upright = Bitmap.createBitmap(bitmap, 0, 0, bitmap.getWidth(), bitmap.getHeight(), matrix, true);
                try { encoded.reset(); upright.compress(Bitmap.CompressFormat.JPEG, 78, encoded); bytes = encoded.toByteArray(); }
                finally { if (upright != bitmap) upright.recycle(); bitmap.recycle(); }
            }
            byte[] complete = bytes;
            main.post(() -> {
                if (version != generation) return;
                latest = complete;
                for (MethodChannel.Result result : pending) result.success(Base64.encodeToString(complete, Base64.NO_WRAP));
                pending.clear();
            });
        } catch (RuntimeException error) { fail(version); }
    }

    private void copy(Image.Plane plane, int width, int height, byte[] out, int offset, int step) {
        ByteBuffer data = plane.getBuffer(); int row = plane.getRowStride(), pixel = plane.getPixelStride();
        int base = data.position();
        for (int y = 0; y < height; y++) for (int x = 0; x < width; x++)
            out[offset + (y * width + x) * step] = data.get(base + y * row + x * pixel);
    }
    private void fail(int version) {
        main.post(() -> {
            if (version != generation) return;
            for (MethodChannel.Result result : pending) result.error("camera_unavailable", "Камера недоступна. Проверьте разрешение и повторите подключение.", null);
            pending.clear(); close();
        });
    }
    void close() {
        generation++; latest = null; lastFrame = 0;
        if (session != null) { session.close(); session = null; }
        if (camera != null) { camera.close(); camera = null; }
        if (reader != null) { reader.close(); reader = null; }
        if (thread != null) { thread.quitSafely(); thread = null; handler = null; }
        for (MethodChannel.Result result : pending) result.error("camera_closed", "Камера отключена", null);
        pending.clear();
    }
}
