import SwiftUI
import UIKit

/// The practice plan in the same words as the first-run walkthrough: a moment you already have ("with my morning
/// chai") and how often. Exact days, time and cue sit one tap away under "Days and time".
struct PracticePlanEditor: View {
    @Binding var weeklyTarget: Int
    @Binding var days: Set<Int>
    @Binding var time: String
    @Binding var anchor: String?
    @Binding var isCustomising: Bool
    let market: Market

    private var routines: [PracticeRoutine] { PracticeRoutine.options(for: market) }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(routines) { routine in
                let selected = Self.routine(anchor: anchor, time: time, market: market) == routine
                PlanRoutineRow(routine: routine, time: Self.displayTime(selected ? time : routine.time), selected: selected) {
                    Haptics.selection()
                    time = routine.time
                    anchor = routine.anchor
                }
            }
            Picker("How often", selection: targetBinding) {
                ForEach(targetOptions, id: \.self) { value in
                    Text(label(forTarget: value)).tag(value)
                }
            }
            .pickerStyle(.segmented)
            .padding(.vertical, 14)
            customCard
        }
    }

    /// Exact days, time and cue, folded away until someone wants them.
    private var customCard: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button {
                withAnimation(.spring(response: 0.3, dampingFraction: 0.9)) { isCustomising.toggle() }
            } label: {
                HStack(spacing: 14) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Days and time").font(.headlineRounded).foregroundStyle(Theme.ink)
                        Text(summary).font(.subheadline).foregroundStyle(Theme.inkSecondary)
                    }
                    Spacer(minLength: 8)
                    Image(systemName: "chevron.down")
                        .font(.footnote.weight(.bold))
                        .foregroundStyle(Theme.inkTertiary)
                        .rotationEffect(.degrees(isCustomising ? 180 : 0))
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityHint(isCustomising ? "Hides the days, time and cue" : "Shows the days, time and cue")

            if isCustomising {
                VStack(alignment: .leading, spacing: 20) {
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
                    DatePicker("Time", selection: timeBinding, displayedComponents: .hourAndMinute)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(Theme.ink)
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Right after…").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                        FlowLayout(spacing: 8) {
                            ForEach(PracticeAnchor.presets(for: market), id: \.self) { preset in
                                SelectableChip(title: preset, isSelected: anchor == preset) {
                                    anchor = anchor == preset ? nil : preset
                                }
                            }
                        }
                    }
                }
                .padding(.top, 18)
            }
        }
        .padding(16)
        .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.radius, style: .continuous)
                .strokeBorder(Theme.stroke, lineWidth: 1)
        )
    }

    /// The three choices from the walkthrough, plus an older plan's own target so it still shows as chosen.
    private var targetOptions: [Int] {
        var options = [3, 5, 7]
        if !options.contains(weeklyTarget) { options.append(weeklyTarget) }
        return options.sorted()
    }

    private func label(forTarget value: Int) -> String {
        if value >= 7 { return "Every day" }
        let count = value == 1 ? "1 day" : "\(value) days"
        return value == targetOptions.first ? "\(count) a week" : count
    }

    /// Choosing how often also spreads the practice days through the week; a saved plan's own days are kept
    /// until then.
    private var targetBinding: Binding<Int> {
        Binding(
            get: { weeklyTarget },
            set: { value in
                guard value != weeklyTarget else { return }
                weeklyTarget = value
                days = Set(HabitMath.defaultDays(forTarget: value))
            }
        )
    }

    /// "Weekdays · 8:30 AM"
    private var summary: String {
        let sorted = days.sorted()
        let dayText: String
        if sorted.isEmpty {
            dayText = "No days picked"
        } else if sorted.count == 7 {
            dayText = "Every day"
        } else if sorted == [1, 2, 3, 4, 5] {
            dayText = "Weekdays"
        } else if sorted == [6, 7] {
            dayText = "Weekends"
        } else {
            dayText = sorted.map { HabitMath.weekdayShortNames[$0 - 1] }.joined(separator: ", ")
        }
        return "\(dayText) · \(Self.displayTime(time))"
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

    /// The routine a plan follows: by its cue, or by its time when it has no cue.
    static func routine(anchor: String?, time: String, market: Market) -> PracticeRoutine? {
        let options = PracticeRoutine.options(for: market)
        if let anchor { return options.first { $0.anchor == anchor } }
        return options.first { $0.time == time }
    }

    /// "19:00" → "7:00 PM" in the person's locale.
    static func displayTime(_ value: String) -> String {
        guard let parts = HabitMath.parseTime(value),
              let date = Calendar.current.date(bySettingHour: parts.hour, minute: parts.minute, second: 0, of: Date())
        else { return value }
        return date.formatted(date: .omitted, time: .shortened)
    }
}

/// One routine, as a large single-choice row (the same look as the walkthrough's choices).
private struct PlanRoutineRow: View {
    let routine: PracticeRoutine
    let time: String
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 16) {
                Image(systemName: routine.symbol)
                    .font(.title3)
                    .foregroundStyle(selected ? Color.white : Theme.indigo)
                    .frame(width: 46, height: 46)
                    .background(selected ? AnyShapeStyle(Theme.aurora) : AnyShapeStyle(Theme.indigo.opacity(0.1)), in: Circle())
                Text(routine.title).font(.headlineRounded).foregroundStyle(Theme.ink).multilineTextAlignment(.leading)
                Spacer(minLength: 8)
                Text(time).font(.subheadline).foregroundStyle(Theme.inkSecondary)
                if selected {
                    Image(systemName: "checkmark.circle.fill").font(.title3).foregroundStyle(Theme.indigo)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.radius, style: .continuous)
                    .strokeBorder(selected ? Theme.indigo : Theme.stroke, lineWidth: selected ? 2 : 1)
            )
        }
        .buttonStyle(.pressableCard)
        .accessibilityAddTraits(selected ? .isSelected : [])
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
    @State private var isCustomising = false
    @State private var remindersOn = true
    @State private var loaded = false
    @State private var isSaving = false
    @State private var showPriming = false
    @State private var showBreakOptions = false
    @State private var showBreakPicker = false
    @State private var breakUntil = Date().addingTimeInterval(7 * 86_400)
    @State private var error: String?

    private var pausedUntil: String? { app.me?.practiceSettings.pausedUntil }
    private var isOnBreak: Bool {
        guard let pausedUntil else { return false }
        return HabitMath.dayString(Date(), timeZone: .current) <= pausedUntil
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                if let error { InlineErrorBanner(message: error) { self.error = nil } }

                Text("When will you practise?")
                    .font(.display)
                    .foregroundStyle(Theme.ink)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.bottom, 4)

                PracticePlanEditor(weeklyTarget: $weeklyTarget, days: $days, time: $time, anchor: $anchor,
                                   isCustomising: $isCustomising, market: app.market)

                remindersCard
                breakRow
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
        .confirmationDialog("Take a break", isPresented: $showBreakOptions, titleVisibility: .visible) {
            Button("1 week") { Task { await startBreak(days: 7) } }
            Button("2 weeks") { Task { await startBreak(days: 14) } }
            Button("Pick a date") { showBreakPicker = true }
        } message: {
            Text("Reminders pause. Your progress and weekly run are kept.")
        }
        .sheet(isPresented: $showBreakPicker) { breakDateSheet }
        .onAppear(perform: load)
    }

    private var remindersCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Toggle(isOn: $remindersOn) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Remind me").font(.headlineRounded).foregroundStyle(Theme.ink)
                    Text("With that day's prompt").font(.subheadline).foregroundStyle(Theme.inkSecondary)
                }
            }
            .tint(Theme.indigo)
            if app.notifications.isDenied && remindersOn {
                NotificationsOffBanner()
            }
        }
        .card(padding: 16)
    }

    @ViewBuilder
    private var breakRow: some View {
        if isOnBreak, let pausedUntil {
            HStack(spacing: 14) {
                breakIcon
                VStack(alignment: .leading, spacing: 2) {
                    Text("On a break").font(.headlineRounded).foregroundStyle(Theme.ink)
                    Text("Until \(Self.display(day: pausedUntil))").font(.subheadline).foregroundStyle(Theme.inkSecondary)
                }
                Spacer(minLength: 8)
                Button("End break") { Task { await endBreak() } }
                    .buttonStyle(.pill(.secondary, fullWidth: false))
            }
            .card(padding: 16)
        } else {
            Button {
                showBreakOptions = true
            } label: {
                HStack(spacing: 14) {
                    breakIcon
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Take a break").font(.headlineRounded).foregroundStyle(Theme.ink)
                        Text("Exams, travel, a busy week").font(.subheadline).foregroundStyle(Theme.inkSecondary)
                    }
                    Spacer(minLength: 8)
                    Image(systemName: "chevron.right").font(.footnote.weight(.bold)).foregroundStyle(Theme.inkTertiary)
                }
                .card(padding: 16)
            }
            .buttonStyle(.pressableCard)
        }
    }

    private var breakIcon: some View {
        Image(systemName: "pause.fill")
            .font(.headline)
            .foregroundStyle(Theme.violet)
            .frame(width: 44, height: 44)
            .background(Theme.violet.opacity(0.12), in: Circle())
    }

    private var breakDateSheet: some View {
        NavigationStack {
            VStack(spacing: 16) {
                DatePicker("Pause until", selection: $breakUntil, in: Date()..., displayedComponents: .date)
                    .datePickerStyle(.graphical)
                    .tint(Theme.indigo)
                Spacer(minLength: 0)
                Button("Start my break") { Task { await startBreak(until: breakUntil) } }
                    .buttonStyle(.primaryPill)
            }
            .padding(Theme.gutter)
            .screenBackground()
            .navigationTitle("Pause until")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Cancel") { showBreakPicker = false }
                }
            }
        }
        .environment(app)
        .presentationDetents([.large])
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
        // A plan that matches none of the routines opens with its own days, time and cue on show.
        isCustomising = PracticePlanEditor.routine(anchor: anchor, time: time, market: app.market) == nil
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
            showBreakPicker = false
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
