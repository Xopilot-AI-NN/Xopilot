package ru.xopilot.mobile;

import android.app.*;
import android.content.*;
import android.content.pm.ActivityInfo;
import android.graphics.*;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.view.*;
import android.widget.*;
import java.util.*;
import java.util.concurrent.ConcurrentLinkedQueue;

/** User-enabled, non-focusable preview. No files, exported intents or launch on boot. */
final class LiveOverlay {
    interface Action { void send(String action); }
    private final Context context;
    private final WindowManager windows;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final Action action;
    private final Queue<String> actions = new ConcurrentLinkedQueue<>();
    private Activity activity;
    private LinearLayout root;
    private ImageView image;
    private TextView mute;
    private WindowManager.LayoutParams layout;
    private Bitmap cameraFrame;
    private boolean foreground = true, requested, active, expanded, muted, microphone;
    private String source = "";
    private int x = 12, y = 140;
    private long cameraSequence, renderedSequence = -1;
    private byte[] renderedScreen;
    private int captureTypes;

    LiveOverlay(Context context, Action action) {
        this.context = context; this.action = action;
        windows = context.getSystemService(WindowManager.class);
    }

    static void orient(Activity activity) {
        // Use the device's shortest dimension, not current window height or IME.
        // Tablets/foldables retain rotation and resizable ChromeOS windows.
        int width = activity.getResources().getConfiguration().smallestScreenWidthDp;
        activity.setRequestedOrientation(width < 600
            ? ActivityInfo.SCREEN_ORIENTATION_PORTRAIT : ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED);
    }

    void attach(Activity activity) { this.activity = activity; orient(activity); }
    void lifecycle(boolean foreground) {
        this.foreground = foreground;
        if (foreground) { if (activity != null) orient(activity); hide(); ensureCaptureService(); }
        else refresh();
    }

    boolean request(Map<String, Object> state) {
        requested = true; state(state);
        if (!Settings.canDrawOverlays(context)) {
            if (activity == null) throw new IllegalStateException("Вернитесь в Xopilot");
            activity.startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:" + context.getPackageName())));
            return false;
        }
        ensureCaptureService(); return true;
    }

    void minimize() {
        if (!active || !Settings.canDrawOverlays(context) || activity == null)
            throw new IllegalStateException("Включите источник и разрешите плавающее окно");
        ensureCaptureService();
        activity.moveTaskToBack(true);
    }

    void state(Map<String, Object> data) {
        source = String.valueOf(data.getOrDefault("source", ""));
        active = "camera".equals(source) || "screen".equals(source);
        muted = Boolean.TRUE.equals(data.get("muted"));
        // A muted running call retains the eligible service type so unmuting
        // does not try to start a new while-in-use service in the background.
        // Declaring that type does not open/record the microphone.
        microphone = Boolean.TRUE.equals(data.get("microphone")) && context.checkSelfPermission(
            android.Manifest.permission.RECORD_AUDIO) == android.content.pm.PackageManager.PERMISSION_GRANTED;
        if (!active) { stop(false); return; }
        ensureCaptureService(); refresh();
    }

    private void ensureCaptureService() {
        if (!requested || !active || !foreground || !Settings.canDrawOverlays(context)) return;
        // ScreenCaptureService already maintains projection. Camera/microphone
        // need their own while-in-use service, started while Activity is visible.
        if ("camera".equals(source) || microphone) {
            int nextTypes = ("camera".equals(source) ? 1 : 0) | (microphone ? 2 : 0);
            if (captureTypes == nextTypes) return;
            Intent intent = new Intent(context, LiveCaptureService.class)
                .putExtra("camera", "camera".equals(source)).putExtra("microphone", microphone);
            context.startForegroundService(intent);
            captureTypes = nextTypes;
        } else {
            context.stopService(new Intent(context, LiveCaptureService.class)); captureTypes = 0;
        }
    }

    Map<String, Object> poll() {
        Map<String, Object> value = new HashMap<>();
        List<String> pending = new ArrayList<>(); String item;
        while ((item = actions.poll()) != null) pending.add(item);
        value.put("actions", pending); value.put("foreground", foreground);
        value.put("enabled", requested && active && Settings.canDrawOverlays(context));
        return value;
    }
    boolean enabled() { return requested && active && Settings.canDrawOverlays(context); }

    void camera(byte[] bytes) {
        if (!requested || !active || !"camera".equals(source)) return;
        BitmapFactory.Options options = new BitmapFactory.Options(); options.inJustDecodeBounds = true;
        BitmapFactory.decodeByteArray(bytes, 0, bytes.length, options);
        options.inSampleSize = Math.max(1, Math.max(options.outWidth, options.outHeight) / 192);
        options.inJustDecodeBounds = false;
        Bitmap next = BitmapFactory.decodeByteArray(bytes, 0, bytes.length, options);
        Bitmap previous = cameraFrame; cameraFrame = next; cameraSequence++;
        if (image != null && "camera".equals(source)) image.setImageBitmap(next);
        if (previous != null) previous.recycle();
    }

    private int dp(int n) { return Math.round(n * context.getResources().getDisplayMetrics().density); }
    private GradientDrawable shape(boolean circle) {
        GradientDrawable value = new GradientDrawable(GradientDrawable.Orientation.TL_BR,
            new int[]{Color.rgb(0, 191, 187), Color.rgb(105, 91, 255)});
        value.setCornerRadius(dp(circle ? 44 : 20)); value.setStroke(dp(2), Color.WHITE);
        return value;
    }
    private TextView button(String text, String label, Runnable click) {
        TextView view = new TextView(context); view.setText(text); view.setTextColor(Color.WHITE);
        view.setTextSize(15); view.setGravity(Gravity.CENTER); view.setContentDescription(label);
        view.setPadding(dp(12), 0, dp(12), 0); view.setMinimumHeight(dp(48));
        view.setOnClickListener(v -> click.run()); return view;
    }

    private void refresh() {
        if (!requested || !active || foreground || !Settings.canDrawOverlays(context)) { hide(); return; }
        if (root == null) show();
        if (mute != null) {
            mute.setText(muted ? "Вкл. микрофон" : "Выкл. микрофон");
            mute.setContentDescription(muted ? "Включить микрофон" : "Выключить микрофон");
        }
    }

    private void show() {
        root = new LinearLayout(context); root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(3), dp(3), dp(3), dp(3)); root.setBackground(shape(!expanded));
        image = new ImageView(context); image.setScaleType(ImageView.ScaleType.CENTER_CROP);
        image.setClipToOutline(true); image.setBackground(shape(true));
        image.setContentDescription("camera".equals(source) ? "Предпросмотр камеры" : "Предпросмотр экрана");
        root.addView(image, new LinearLayout.LayoutParams(dp(expanded ? 180 : 78), dp(expanded ? 120 : 78)));
        image.setOnTouchListener(new View.OnTouchListener() {
            float downX, downY; int originX, originY; boolean dragged;
            public boolean onTouch(View view, android.view.MotionEvent event) {
                if (event.getAction() == MotionEvent.ACTION_DOWN) {
                    downX = event.getRawX(); downY = event.getRawY(); originX = layout.x; originY = layout.y; dragged = false;
                    return true;
                }
                if (event.getAction() == MotionEvent.ACTION_MOVE) {
                    float dx = event.getRawX() - downX, dy = event.getRawY() - downY;
                    if (Math.abs(dx) + Math.abs(dy) > dp(8)) dragged = true;
                    if (dragged) { layout.x = originX + (int)dx; layout.y = originY + (int)dy; clamp(); windows.updateViewLayout(root, layout); }
                    return true;
                }
                if (event.getAction() == MotionEvent.ACTION_UP) {
                    x = layout.x; y = layout.y;
                    if (!dragged) { expanded = !expanded; hide(); refresh(); }
                    return true;
                }
                return true;
            }
        });
        if (expanded) {
            root.addView(button("Вернуться", "Вернуться в Xopilot", () -> {
                Intent launch = context.getPackageManager().getLaunchIntentForPackage(context.getPackageName());
                if (launch != null) { launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT); context.startActivity(launch); }
            }));
            mute = button(muted ? "Вкл. микрофон" : "Выкл. микрофон", "Выключить микрофон", () -> {
                muted = !muted; emit(muted ? "mute" : "unmute"); refresh();
            });
            root.addView(mute);
            root.addView(button("Завершить", "Завершить трансляцию", () -> stop(true)));
        }
        layout = new WindowManager.LayoutParams(WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_SECURE,
            PixelFormat.TRANSLUCENT);
        layout.gravity = Gravity.TOP | Gravity.LEFT; layout.x = x; layout.y = y; clamp();
        try { windows.addView(root, layout); tick.run(); }
        catch (RuntimeException denied) { root = null; image = null; mute = null; }
    }

    private void clamp() {
        android.util.DisplayMetrics metrics = context.getResources().getDisplayMetrics();
        layout.x = Math.max(0, Math.min(layout.x, metrics.widthPixels - dp(expanded ? 186 : 84)));
        layout.y = Math.max(dp(24), Math.min(layout.y, metrics.heightPixels - dp(expanded ? 280 : 110)));
    }

    private final Runnable tick = new Runnable() {
        public void run() {
            if (root == null) return;
            if ("screen".equals(source)) {
                ScreenCaptureService screen = ScreenCaptureService.current;
                byte[] bytes = screen == null ? null : screen.previewBytes();
                if (bytes != null && bytes != renderedScreen) {
                    renderedScreen = bytes;
                    BitmapFactory.Options options = new BitmapFactory.Options(); options.inSampleSize = 4;
                    Bitmap next = BitmapFactory.decodeByteArray(bytes, 0, bytes.length, options);
                    Bitmap previous = cameraFrame; cameraFrame = next;
                    image.setImageBitmap(next); if (previous != null) previous.recycle();
                }
                if (screen == null) { stop(true); return; }
            } else if (cameraFrame != null && cameraSequence != renderedSequence) {
                renderedSequence = cameraSequence; image.setImageBitmap(cameraFrame);
            }
            main.postDelayed(this, 900);
        }
    };

    private void emit(String name) { actions.add(name); action.send(name); }
    void stop(boolean notify) {
        requested = active = false; hide();
        captureTypes = 0;
        context.stopService(new Intent(context, LiveCaptureService.class));
        if (notify) { ScreenCaptureService.stop(context); emit("stop"); }
        if (cameraFrame != null) { cameraFrame.recycle(); cameraFrame = null; }
        renderedScreen = null; renderedSequence = -1;
    }
    private void hide() {
        main.removeCallbacks(tick);
        if (root != null) { try { windows.removeView(root); } catch (RuntimeException ignored) {} }
        root = null; image = null; mute = null;
    }
    void dispose() { stop(true); activity = null; }
}
