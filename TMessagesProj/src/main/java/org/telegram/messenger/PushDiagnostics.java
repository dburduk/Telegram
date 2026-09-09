package org.telegram.messenger;

import android.app.Activity;
import android.app.NotificationManager;
import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.os.Build;
import android.os.PowerManager;
import android.widget.Toast;

import com.google.android.gms.common.GoogleApiAvailability;
import com.google.firebase.FirebaseApp;
import com.google.firebase.FirebaseOptions;

import org.telegram.ui.ActionBar.AlertDialog;

import java.lang.ref.WeakReference;
import java.security.MessageDigest;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** Local diagnostic report. Never includes push tokens, API keys or account identifiers. */
public final class PushDiagnostics {
    private static WeakReference<AlertDialog> visibleDialog = new WeakReference<>(null);

    public static String sanitize(String value) {
        if (value == null) return "(no details)";
        String result = value.replaceAll("AIza[A-Za-z0-9_-]+", "[API key]")
            .replaceAll("https?://\\S+", "[URL]")
            .replaceAll("[A-Za-z0-9_:-]{80,}", "[long value]")
            .replace('\n', ' ').replace('\r', ' ');
        return result.length() > 1000 ? result.substring(0, 1000) : result;
    }

    public static String describe(Throwable error) {
        if (error == null) return "Unknown error (no exception supplied)";
        StringBuilder result = new StringBuilder();
        for (int depth = 0; error != null && depth < 5; depth++) {
            if (depth > 0) result.append(" <- ");
            result.append(error.getClass().getSimpleName()).append(": ").append(sanitize(error.getMessage()));
            Throwable cause = error.getCause();
            if (cause == error) break;
            error = cause;
        }
        return result.toString();
    }

    public static synchronized void record(String event) {
        Context context = ApplicationLoader.applicationContext;
        if (context == null) return;
        String line = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(new Date()) + " " + sanitize(event);
        android.content.SharedPreferences prefs = context.getSharedPreferences("push_diagnostics", Context.MODE_PRIVATE);
        String[] previous = prefs.getString("events", "").split("\n");
        StringBuilder history = new StringBuilder();
        for (int i = Math.max(0, previous.length - 11); i < previous.length; i++) {
            if (!previous[i].isEmpty()) history.append(previous[i]).append('\n');
        }
        history.append(line);
        prefs.edit().putString("events", history.toString()).apply();
        if (BuildVars.LOGS_ENABLED) FileLog.d("Push diagnostics: " + line);
        AndroidUtilities.runOnUIThread(() -> {
            AlertDialog dialog = visibleDialog.get();
            if (dialog != null && dialog.isShowing()) dialog.setMessage(report(dialog.getContext()));
        });
    }

    public static String report(Context context) {
        StringBuilder result = new StringBuilder("Диагностика фоновых уведомлений\n\n");
        result.append("Package: ").append(context.getPackageName()).append('\n');
        result.append("Version: ").append(BuildVars.BUILD_VERSION_STRING).append(" / Android ").append(Build.VERSION.RELEASE).append('\n');
        result.append("Google Play services status: ").append(GoogleApiAvailability.getInstance().isGooglePlayServicesAvailable(context)).append(" (0 = OK)\n");
        result.append("FCM token present: ").append(!android.text.TextUtils.isEmpty(SharedConfig.pushString)).append('\n');
        try {
            FirebaseOptions options = FirebaseApp.getInstance().getOptions();
            result.append("Firebase project: ").append(options.getProjectId()).append('\n');
            result.append("Firebase app: ").append(options.getApplicationId()).append('\n');
            result.append("Sender: ").append(options.getGcmSenderId()).append('\n');
        } catch (Exception e) {
            result.append("Firebase initialization: ").append(describe(e)).append('\n');
        }
        try {
            Signature[] signatures;
            if (Build.VERSION.SDK_INT >= 28) {
                PackageInfo info = context.getPackageManager().getPackageInfo(context.getPackageName(), PackageManager.GET_SIGNING_CERTIFICATES);
                signatures = info.signingInfo.getApkContentsSigners();
            } else {
                signatures = context.getPackageManager().getPackageInfo(context.getPackageName(), PackageManager.GET_SIGNATURES).signatures;
            }
            StringBuilder certificate = new StringBuilder();
            for (byte b : MessageDigest.getInstance("SHA-1").digest(signatures[0].toByteArray())) certificate.append(String.format(Locale.US, "%02X", b & 255));
            result.append("Signing certificate SHA-1: ").append(certificate).append('\n');
        } catch (Exception e) {
            result.append("Certificate: ").append(describe(e)).append('\n');
        }
        NotificationManager notifications = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 24) result.append("Notifications allowed: ").append(notifications.areNotificationsEnabled()).append('\n');
        if (Build.VERSION.SDK_INT >= 34) result.append("Full-screen calls allowed: ").append(notifications.canUseFullScreenIntent()).append('\n');
        if (Build.VERSION.SDK_INT >= 23) {
            PowerManager power = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
            result.append("Battery optimization exempt: ").append(power.isIgnoringBatteryOptimizations(context.getPackageName())).append('\n');
        }
        for (int account = 0; account < UserConfig.MAX_ACCOUNT_COUNT; account++) {
            UserConfig config = UserConfig.getInstance(account);
            if (config.isClientActivated()) result.append("Account slot ").append(account + 1).append(" registered with Telegram: ").append(config.registeredForPush).append('\n');
        }
        result.append("\nПоследние события:\n").append(context.getSharedPreferences("push_diagnostics", Context.MODE_PRIVATE).getString("events", "Проверка ещё не запускалась."));
        return result.toString();
    }

    public static void show(Activity activity) {
        if (activity == null || activity.isFinishing()) return;
        AlertDialog dialog = new AlertDialog.Builder(activity)
            .setTitle("Диагностика уведомлений")
            .setMessage(report(activity))
            .setPositiveButton("Повторить", (d, which) -> {
                if (ApplicationLoader.getPushProvider().hasServices()) {
                    ApplicationLoader.getPushProvider().onRequestPushToken();
                } else {
                    record("Google Play services unavailable");
                }
            })
            .setNeutralButton("Скопировать", (d, which) -> {
                AndroidUtilities.addToClipboard(report(activity));
                Toast.makeText(activity, "Отчёт скопирован", Toast.LENGTH_SHORT).show();
            })
            .setNegativeButton("Закрыть", (d, which) -> d.dismiss())
            .create();
        dialog.setDismissDialogByButtons(false);
        visibleDialog = new WeakReference<>(dialog);
        dialog.show();
    }
}
