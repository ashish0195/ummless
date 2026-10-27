import SwiftUI
import UIKit
import UserNotifications

/// Which notifications Comlogue sends, and when it stays quiet. Mirrors the server's settings so pushes and
/// on-device reminders follow the same choices.
struct NotificationSettingsView: View {
    @Environment(AppModel.self) private var app
    var isRoot = false

    @State private var settings = NotificationSettings.defaults
    @State private var loaded = false
    @State private var isSendingTest = false
    @State private var error: String?

    var body: some View {
        Form {
            Section {
                statusRow
            }

            Section {
                Toggle("Practice reminders", isOn: binding(\.practiceReminders))
                Toggle("Before big moments", isOn: binding(\.eventPrep))
                Toggle("Results are ready", isOn: binding(\.results))
                Toggle("How did it go?", isOn: binding(\.checkIns))
                Toggle("Gentle nudges after a quiet spell", isOn: binding(\.nudges))
                Toggle("Your weekly reveal", isOn: binding(\.weeklyReveal))
            } header: {
                Text("Send me")
            } footer: {
                Text("Practice reminders follow your plan. Event reminders come the evening before and the morning of anything you add in Practice. Nudges stop after two if you're busy — no guilt, no streaks to lose.")
            }

            Section {
                Toggle("Tips and product news", isOn: binding(\.tips))
            } footer: {
                Text("Occasional, and only if you want them.")
            }

            Section {
                DatePicker("From", selection: timeBinding(\.quietStart), displayedComponents: .hourAndMinute)
                DatePicker("Until", selection: timeBinding(\.quietEnd), displayedComponents: .hourAndMinute)
            } header: {
                Text("Quiet hours")
            } footer: {
                Text("Nothing arrives in these hours except a practice reminder at a time you chose yourself.")
            }

            Section {
                Button {
                    Task { await sendTest() }
                } label: {
                    HStack {
                        Text("Send me a test notification")
                        if isSendingTest { Spacer(); ProgressView() }
                    }
                }
                .disabled(isSendingTest || !app.notifications.canDeliver)
                NavigationLink("Practice plan") { PracticePlanView() }
            }

            if let error {
                Section { Text(error).foregroundStyle(Theme.danger) }
            }
        }
        .navigationTitle("Notifications")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if isRoot {
                ToolbarItem(placement: .topBarTrailing) {
                    CircleIconButton(systemName: "xmark") { app.dismissFlow(refresh: false) }
                }
            }
        }
        .task {
            await app.notifications.refreshStatus()
            if !loaded {
                loaded = true
                settings = app.me?.resolvedNotificationSettings ?? .defaults
            }
        }
    }

    @ViewBuilder
    private var statusRow: some View {
        let manager = app.notifications
        VStack(alignment: .leading, spacing: 8) {
            switch manager.status {
            case .authorized, .ephemeral:
                Label("Notifications are on", systemImage: "checkmark.circle.fill").foregroundStyle(Theme.mint)
            case .provisional:
                Label("Delivered quietly", systemImage: "bell.badge").foregroundStyle(Theme.amber)
                Text("They go to Notification Center without a sound or banner.")
                    .font(.footnote).foregroundStyle(Theme.inkSecondary)
                Button("Allow banners and sounds") {
                    Task {
                        await manager.requestFull()
                        await app.syncDevice()
                        await app.rescheduleNotifications()
                    }
                }
                .font(.footnote.weight(.semibold))
            case .denied:
                NotificationsOffBanner()
            default:
                Label("Not set up yet", systemImage: "bell").foregroundStyle(Theme.inkSecondary)
                Button("Turn on notifications") {
                    Task {
                        await manager.requestFull()
                        await app.syncDevice()
                        await app.rescheduleNotifications()
                    }
                }
                .font(.footnote.weight(.semibold))
            }
        }
        .font(.subheadline.weight(.semibold))
    }

    private func binding(_ keyPath: WritableKeyPath<NotificationSettings, Bool>) -> Binding<Bool> {
        Binding(
            get: { settings[keyPath: keyPath] },
            set: { newValue in
                settings[keyPath: keyPath] = newValue
                save()
            }
        )
    }

    private func timeBinding(_ keyPath: WritableKeyPath<NotificationSettings, String>) -> Binding<Date> {
        Binding(
            get: {
                let parts = HabitMath.parseTime(settings[keyPath: keyPath]) ?? (hour: 22, minute: 0)
                return Calendar.current.date(bySettingHour: parts.hour, minute: parts.minute, second: 0, of: Date()) ?? Date()
            },
            set: { date in
                let parts = Calendar.current.dateComponents([.hour, .minute], from: date)
                settings[keyPath: keyPath] = HabitMath.timeString(hour: parts.hour ?? 0, minute: parts.minute ?? 0)
                save()
            }
        )
    }

    private func save() {
        let snapshot = settings
        Task {
            var patch = MePatch()
            patch.notificationSettings = MePatch.NotificationPatch(snapshot)
            do {
                try await app.updateMe(patch)
                error = nil
            } catch {
                self.error = error.userMessage
            }
        }
    }

    private func sendTest() async {
        isSendingTest = true
        defer { isSendingTest = false }
        do {
            _ = try await app.api.sendTestNotification()
            await app.refreshInbox()
            if !app.serverSendsPush {
                // No push from the server on this device: show a local one so the person sees what to expect.
                let content = UNMutableNotificationContent()
                content.title = "Notifications are on"
                content.body = "This is how Comlogue will reach you. You can change what we send any time."
                content.sound = .default
                let request = UNNotificationRequest(identifier: NotificationPlanner.identifierPrefix + "test",
                                                    content: content,
                                                    trigger: UNTimeIntervalNotificationTrigger(timeInterval: 3, repeats: false))
                try? await UNUserNotificationCenter.current().add(request)
            }
            app.showToast("Test sent")
        } catch {
            self.error = error.userMessage
        }
    }
}
