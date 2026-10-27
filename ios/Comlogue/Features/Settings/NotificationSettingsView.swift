import SwiftUI
import UIKit
import UserNotifications

/// Which notifications Comlogue sends, and when it stays quiet. Mirrors the server's settings so pushes and
/// on-device reminders follow the same choices. The everyday choices come first; the rest sit under
/// "More options".
struct NotificationSettingsView: View {
    @Environment(AppModel.self) private var app
    var isRoot = false

    @State private var settings = NotificationSettings.defaults
    @State private var loaded = false
    @State private var isSendingTest = false
    @State private var showQuietHours = false
    @State private var showMore = false
    @State private var error: String?

    var body: some View {
        Form {
            Section {
                statusCard
            }

            Section {
                Toggle("Practice reminders", isOn: binding(\.practiceReminders))
                Button {
                    withAnimation { showQuietHours.toggle() }
                } label: {
                    HStack {
                        Text("Quiet hours").foregroundStyle(Theme.ink)
                        Spacer()
                        Text(quietHoursLabel).foregroundStyle(Theme.inkSecondary)
                    }
                }
                .accessibilityHint(showQuietHours ? "Hides the start and end times" : "Shows the start and end times")
                if showQuietHours {
                    DatePicker("From", selection: timeBinding(\.quietStart), displayedComponents: .hourAndMinute)
                    DatePicker("Until", selection: timeBinding(\.quietEnd), displayedComponents: .hourAndMinute)
                }
                NavigationLink("Practice plan") { PracticePlanView() }
            } footer: {
                if showQuietHours {
                    Text("Only the practice reminder you set can arrive in quiet hours.")
                }
            }

            Section {
                DisclosureGroup("More options", isExpanded: $showMore) {
                    Toggle("Before big moments", isOn: binding(\.eventPrep))
                    Toggle("Results are ready", isOn: binding(\.results))
                    Toggle("How did it go?", isOn: binding(\.checkIns))
                    Toggle("Gentle nudges after a quiet spell", isOn: binding(\.nudges))
                    Toggle("Your weekly reveal", isOn: binding(\.weeklyReveal))
                    Toggle("Tips and product news", isOn: binding(\.tips))
                    Button {
                        Task { await sendTest() }
                    } label: {
                        HStack {
                            Text("Send me a test notification")
                            if isSendingTest { Spacer(); ProgressView() }
                        }
                    }
                    .disabled(isSendingTest || !app.notifications.canDeliver)
                }
            } footer: {
                if showMore {
                    Text("Nudges stop after two if you're busy. No streaks to lose.")
                }
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

    /// On, quiet or off — and the one button that fixes it.
    @ViewBuilder
    private var statusCard: some View {
        if app.notifications.isDenied {
            NotificationsOffBanner()
        } else {
            let status = statusInfo
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 14) {
                    Image(systemName: status.symbol)
                        .font(.headline)
                        .foregroundStyle(status.color)
                        .frame(width: 44, height: 44)
                        .background(status.color.opacity(0.12), in: Circle())
                    VStack(alignment: .leading, spacing: 2) {
                        Text(status.title).font(.headlineRounded).foregroundStyle(Theme.ink)
                        if let detail = status.detail {
                            Text(detail).font(.subheadline).foregroundStyle(Theme.inkSecondary)
                        }
                    }
                }
                if let actionTitle = status.action {
                    Button(actionTitle) {
                        Task {
                            await app.notifications.requestFull()
                            await app.syncDevice()
                            await app.rescheduleNotifications()
                        }
                    }
                    .buttonStyle(.primaryPill)
                }
            }
            .padding(.vertical, 6)
        }
    }

    private var statusInfo: (symbol: String, color: Color, title: String, detail: String?, action: String?) {
        switch app.notifications.status {
        case .authorized, .ephemeral:
            return ("bell.fill", Theme.mint, "Notifications are on", nil, nil)
        case .provisional:
            return ("bell.badge", Theme.amber, "Delivered quietly", "No sound or banner", "Allow banners and sounds")
        default:
            return ("bell.slash", Theme.inkSecondary, "Notifications are off", "Get your practice reminders", "Turn on notifications")
        }
    }

    /// "10:00 PM – 8:00 AM"
    private var quietHoursLabel: String {
        "\(PracticePlanEditor.displayTime(settings.quietStart)) – \(PracticePlanEditor.displayTime(settings.quietEnd))"
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
