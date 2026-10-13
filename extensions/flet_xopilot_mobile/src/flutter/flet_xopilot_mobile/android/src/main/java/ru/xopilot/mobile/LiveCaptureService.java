package ru.xopilot.mobile;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.os.*;

/** Keeps explicitly minimized camera/microphone access eligible on modern Android. */
public final class LiveCaptureService extends Service {
    static Runnable stopped;
    @Override public int onStartCommand(Intent intent, int flags, int id) {
        if (intent == null || "stop".equals(intent.getAction())) {
            if (stopped != null) stopped.run(); stopSelf(); return START_NOT_STICKY;
        }
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel("xopilot_live", "Разговор Xopilot", NotificationManager.IMPORTANCE_LOW));
        Intent launch = getPackageManager().getLaunchIntentForPackage(getPackageName());
        PendingIntent open = PendingIntent.getActivity(this, 1, launch, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop = PendingIntent.getService(this, 2,
            new Intent(this, LiveCaptureService.class).setAction("stop"), PendingIntent.FLAG_IMMUTABLE);
        Notification notice = new Notification.Builder(this, "xopilot_live")
            .setSmallIcon(android.R.drawable.ic_menu_view).setContentTitle("Xopilot · разговор продолжается")
            .setContentText("Камера или микрофон включены").setContentIntent(open).setOngoing(true)
            .addAction(new Notification.Action.Builder(null, "Завершить", stop).build()).build();
        int types = 0;
        if (intent.getBooleanExtra("camera", false)) types |= ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA;
        if (intent.getBooleanExtra("microphone", false)) types |= ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE;
        try {
            if (Build.VERSION.SDK_INT >= 29) startForeground(1202, notice, types);
            else startForeground(1202, notice);
        } catch (RuntimeException denied) {
            if (stopped != null) stopped.run(); stopSelf();
        }
        return START_NOT_STICKY;
    }
    @Override public void onTaskRemoved(Intent root) { if (stopped != null) stopped.run(); stopSelf(); }
    @Override public IBinder onBind(Intent intent) { return null; }
}
