import SwiftUI
import UIKit

/// The person's practice plan: how often, which days, when, and the routine it hangs on. Used in onboarding and
/// in Settings. Plans anchored to an existing routine ("after my morning chai") are far easier to keep.
struct PracticePlanEditor: View {
    @Binding var weeklyTarget: Int
    @Binding var days: Set<Int>
    @Binding var time: String
    @Binding var anchor: String?
    let market: Market

    @State private var customTime = false

    private let targets = [2, 3, 4, 5, 7]

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            VStack(alignment: .leading, spacing: 10) {
                Text("How many days a week?").font(.headlineRounded).foregroundStyle(Theme.ink)
                FlowLayout(spacing: 8) {
                    ForEach(targets, id: \.self) { value in
                        SelectableChip(title: value == 7 ? "Every day" : "\(value) days", isSelected: weeklyTarget == value) {
                            weeklyTarget = value
                            days = Set(HabitMath.defaultDays(forTarget: value))
                        }
                    }
                }
                Text("Pick what fits your life. A missed week never erases progress.")
                    .font(.footnote).foregroundStyle(Theme.inkSecondary)
            }

            VStack(alignment: .leading, spacing: 10) {
                Text("Which days?").font(.headlineRounded).foregroundStyle(Theme.ink)
                HStack(spacing: 6) {
                    ForEach(1...7, id: \.self) { day in
                        let selected = days.contains(day)
                        Button {
                            if selected { days.remove(day) } else { days.insert(day) }
                            Haptics.selection()
                        } label: {
                            Text(HabitMath.weekdayShortNames[day - 1])
                                .font(.caption.weight(.semibold))
                                .frame(maxWidth: .infinity, minHeight: 38)
                                .background(selected ? AnyShapeStyle(Theme.aurora) : AnyShapeStyle(Theme.surfaceMuted), in: Capsule())
                                .foregroundStyle(selected ? Color.white : Theme.ink)
                        }
                        .buttonStyle(.plain)
                        .accessibilityAddTraits(selected ? .isSelected : [])
                    }
                }
            }

            VStack(alignment: .leading, spacing: 10) {
                Text("Right after…").font(.headlineRounded).foregroundStyle(Theme.ink)
                Text("Tie practice to something you already do every day.")
                    .font(.footnote).foregroundStyle(Theme.inkSecondary)
                FlowLayout(spacing: 8) {
                    ForEach(PracticeAnchor.presets(for: market), id: \.self) { preset in
                        SelectableChip(title: preset, isSelected: anchor == preset) {
                            anchor = anchor == preset ? nil : preset
                        }
                    }
                }
            }

            VStack(alignment: .leading, spacing: 10) {
                Text("What time?").font(.headlineRounded).foregroundStyle(Theme.ink)
                FlowLayout(spacing: 8) {
                    ForEach(PracticeTime.allCases) { preset in
                        SelectableChip(title: "\(preset.title) · \(Self.displayTime(preset.time))",
                                       isSelected: !customTime && time == preset.time) {
                            customTime = false
                            time = preset.time
                        }
                    }
                    SelectableChip(title: "Other", isSelected: customTime || PracticeTime.matching(time) == nil) {
                        customTime = true
                    }
                }
                if customTime || PracticeTime.matching(time) == nil {
                    DatePicker("Time", selection: timeBinding, displayedComponents: .hourAndMinute)
                        .datePickerStyle(.compact)
                }
            }

            if !days.isEmpty {
                Label(summary, systemImage: "calendar.badge.clock")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Theme.indigo)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private var summary: String {
        let names = days.sorted().map { HabitMath.weekdayShortNames[$0 - 1] }
        let dayText = days.count == 7 ? "Every day" : names.joined(separator: ", ")
        let cue = anchor.map { " — \(PracticeAnchor.secondPerson($0).lowercasedFirst)" } ?? ""
        return "\(dayText) at \(Self.displayTime(time))\(cue)."
    }

    private var timeBinding: Binding<Date> {
        Binding(
            get: {
                let parts = HabitMath.parseTime(time) ?? (hour: 19, minute: 0)
                return Calendar.current.date(bySettingHour: parts.hour, minute: parts.minute, second: 0, of: Date()) ?? Date()
            },
            set: { date in
                let parts = Calendar.current.dateComponents([.hour, .minute], from: date)
                time = HabitMath.timeString(hour: parts.hour ?? 19, minute: parts.minute ?? 0)
            }
        )
    }

    /// "19:00" → "7:00 PM" in the person's locale.
    static func displayTime(_ value: String) -> String {
        guard let parts = HabitMath.parseTime(value),
              let date = Calendar.current.date(bySettingHour: parts.hour, minute: parts.minute, second: 0, of: Date())
        else { return value }
        return date.formatted(date: .omitted, time: .shortened)
    }
}

private extension String {
    var lowercasedFirst: String {
        guard let first else { return self }
        return first.lowercased() + dropFirst()
    }
}

/// Settings → Practice plan, with reminders and planned breaks.
struct PracticePlanView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    var isRoot = false

    @State private var weeklyTarget = 3
    @State private var days: Set<Int> = [1, 3, 5]
    @State private var time = "08:00"
    @State private var anchor: String?
    @State private var remindersOn = true
    @State private var loaded = false
    @State private var isSaving = false
    @State private var showPriming = false
    @State private var breakUntil = Date().addingTimeInterval(7 * 86_400)
    @State private var showBreakPicker = false
    @State private var error: String?

    private var pausedUntil: String? { app.me?.practiceSettings.pausedUntil }
    private var isOnBreak: Bool {
        guard let pausedUntil else { return false }
        return HabitMath.dayString(Date(), timeZone: .current) <= pausedUntil
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                if let error { InlineErrorBanner(message: error) { self.error = nil } }

                PracticePlanEditor(weeklyTarget: $weeklyTarget, days: $days, time: $time, anchor: $anchor, market: app.market)
                    .card()

                VStack(alignment: .leading, spacing: 10) {
                    Toggle(isOn: $remindersOn) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Remind me").font(.headlineRounded).foregroundStyle(Theme.ink)
                            Text("A reminder on your practice days, with that day's prompt in it.")
                                .font(.footnote).foregroundStyle(Theme.inkSecondary)
                        }
                    }
                    .tint(Theme.indigo)
                    if app.notifications.isDenied && remindersOn {
                        NotificationsOffBanner()
                    }
                }
                .card()

                breakCard
            }
            .padding(Theme.gutter)
        }
        .screenBackground()
        .navigationTitle("Practice plan")
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .bottom) {
            Button {
                Task { await save() }
            } label: {
                if isSaving { ProgressView().tint(.white) } else { Text("Save plan") }
            }
            .buttonStyle(.primaryPill)
            .disabled(isSaving || (remindersOn && days.isEmpty))
            .padding(.horizontal, Theme.gutter)
            .padding(.vertical, 10)
            .background(Theme.background)
        }
        .toolbar {
            if isRoot {
                ToolbarItem(placement: .topBarTrailing) {
                    CircleIconButton(systemName: "xmark") { app.dismissFlow(refresh: false) }
                }
            }
        }
        .sheet(isPresented: $showPriming) {
            NotificationPrimingView(summary: primingSummary) { showPriming = false; close() }
                .environment(app)
                .presentationDetents([.medium, .large])
        }
        .onAppear(perform: load)
    }

    private var breakCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Taking a break?").font(.headlineRounded).foregroundStyle(Theme.ink)
            if isOnBreak, let pausedUntil {
                Text("You're on a break until \(Self.display(day: pausedUntil)). Reminders and nudges are paused, and your weekly run is kept.")
                    .font(.footnote).foregroundStyle(Theme.inkSecondary)
                Button("End my break now") { Task { await endBreak() } }
                    .buttonStyle(.secondaryPill)
            } else {
                Text("Exams, travel, a festival week — pause reminders without losing your run.")
                    .font(.footnote).foregroundStyle(Theme.inkSecondary)
                HStack(spacing: 8) {
                    Button("1 week") { Task { await startBreak(days: 7) } }.buttonStyle(.pill(.secondary, fullWidth: false))
                    Button("2 weeks") { Task { await startBreak(days: 14) } }.buttonStyle(.pill(.secondary, fullWidth: false))
                    Button("Pick a date") { showBreakPicker.toggle() }.buttonStyle(.pill(.ghost, fullWidth: false))
                }
                if showBreakPicker {
                    DatePicker("Back on", selection: $breakUntil, in: Date()..., displayedComponents: .date)
                    Button("Start my break") { Task { await startBreak(until: breakUntil) } }
                        .buttonStyle(.secondaryPill)
                }
            }
        }
        .card()
    }

    private var primingSummary: String {
        let names = days.sorted().map { HabitMath.weekdayShortNames[$0 - 1] }.joined(separator: ", ")
        return "\(names) at \(PracticePlanEditor.displayTime(time))"
    }

    private func load() {
        guard !loaded, let settings = app.me?.practiceSettings else { return }
        loaded = true
        weeklyTarget = settings.weeklyTarget
        anchor = settings.anchor
        time = settings.reminderTime ?? "08:00"
        if settings.reminderDays.isEmpty {
            remindersOn = settings.reminderTime == nil ? true : false
            days = Set(HabitMath.defaultDays(forTarget: settings.weeklyTarget))
        } else {
            remindersOn = true
            days = Set(settings.reminderDays)
        }
    }

    private func save() async {
        isSaving = true
        defer { isSaving = false }
        var patch = MePatch()
        patch.practiceSettings = MePatch.PracticePatch(weeklyTarget: weeklyTarget, reminderTime: time,
                                                       reminderDays: remindersOn ? days.sorted() : [], anchor: anchor)
        do {
            try await app.updateMe(patch)
            await app.refreshProgress()
            await app.notifications.refreshStatus()
            if remindersOn && app.notifications.status == .notDetermined {
                showPriming = true
            } else {
                app.showToast("Plan saved")
                close()
            }
        } catch {
            self.error = error.userMessage
        }
    }

    private func startBreak(days count: Int) async {
        let until = Date().addingTimeInterval(Double(count - 1) * 86_400)
        await startBreak(until: until)
    }

    private func startBreak(until date: Date) async {
        var patch = MePatch()
        patch.practiceSettings = MePatch.PracticePatch(pausedUntil: HabitMath.dayString(date, timeZone: .current))
        do {
            try await app.updateMe(patch)
            await app.refreshProgress()
            showBreakPicker = false
            app.showToast("Enjoy your break")
        } catch {
            self.error = error.userMessage
        }
    }

    private func endBreak() async {
        var patch = MePatch()
        patch.practiceSettings = MePatch.PracticePatch(endsBreak: true)
        do {
            try await app.updateMe(patch)
            await app.refreshProgress()
            app.showToast("Welcome back")
        } catch {
            self.error = error.userMessage
        }
    }

    private func close() {
        if isRoot { app.dismissFlow() } else { dismiss() }
    }

    static func display(day: String) -> String {
        guard let date = HabitMath.date(fromDay: day, timeZone: .current) else { return day }
        return date.formatted(.dateTime.day().month(.abbreviated))
    }
}

/// Explains reminders before iOS asks, so the person decides knowing what they'll get. If they'd rather not, we
/// fall back to quiet delivery in Notification Center instead of asking again.
struct NotificationPrimingView: View {
    @Environment(AppModel.self) private var app
    let summary: String
    let onDone: () -> Void
    @State private var isAsking = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Image(systemName: "bell.badge.fill")
                .font(.system(size: 34, weight: .semibold))
                .foregroundStyle(.white)
                .frame(width: 64, height: 64)
                .background(Theme.aurora, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            Text("Want a nudge at the right moment?").font(.display).foregroundStyle(Theme.ink)
            VStack(alignment: .leading, spacing: 10) {
                Label("Your practice reminder — \(summary), with that day's prompt", systemImage: "waveform")
                Label("The evening before an interview or presentation you add", systemImage: "calendar.badge.clock")
                Label("When feedback on a recording is ready", systemImage: "chart.bar.doc.horizontal")
            }
            .font(.subheadline)
            .foregroundStyle(Theme.ink)
            Text("At most two a day, quiet at night, and no streak guilt. You can change any of it in Settings.")
                .font(.footnote)
                .foregroundStyle(Theme.inkSecondary)
            Spacer(minLength: 0)
            Button {
                Task {
                    isAsking = true
                    LocalFlags.notificationPrimingShown = true
                    await app.notifications.requestFull()
                    await app.syncDevice()
                    await app.rescheduleNotifications()
                    isAsking = false
                    onDone()
                }
            } label: {
                if isAsking { ProgressView().tint(.white) } else { Text("Yes, remind me") }
            }
            .buttonStyle(.primaryPill)
            Button("Not now") {
                Task {
                    LocalFlags.notificationPrimingShown = true
                    await app.notifications.requestProvisional()
                    await app.syncDevice()
                    await app.rescheduleNotifications()
                    onDone()
                }
            }
            .buttonStyle(.ghostPill)
        }
        .padding(Theme.gutter)
        .screenBackground()
    }
}

/// Shown when notifications are turned off in iOS Settings.
struct NotificationsOffBanner: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Notifications are off for Comlogue", systemImage: "bell.slash.fill")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(Theme.ink)
            Text("Turn them on in Settings to get your reminders. Everything else keeps working.")
                .font(.footnote)
                .foregroundStyle(Theme.inkSecondary)
            Button("Open Settings") {
                if let url = URL(string: UIApplication.openNotificationSettingsURLString) {
                    UIApplication.shared.open(url)
                }
            }
            .font(.footnote.weight(.semibold))
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.amber.opacity(0.12), in: RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous))
    }
}
