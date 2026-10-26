import SwiftUI

struct SettingsView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var showVoiceSetup = false
    @State private var confirmDeleteVoice = false
    @State private var confirmDeleteAll = false
    @State private var showPaywall = false
    @State private var error: String?
    @State private var isWorking = false

    var body: some View {
        NavigationStack {
            Form {
                if let error {
                    Section { Text(error).foregroundStyle(Theme.danger) }
                }

                Section("Subscription") {
                    HStack {
                        Label(app.isPro ? "Comlogue Pro" : "Free plan", systemImage: app.isPro ? "star.circle.fill" : "circle.dashed")
                        Spacer()
                        if let expires = app.me?.entitlement.expiresAt {
                            Text("Renews \(Formatting.shortDate(expires))").font(.caption).foregroundStyle(Theme.inkSecondary)
                        }
                    }
                    if app.isPro {
                        Link("Manage subscription", destination: URL(string: "https://apps.apple.com/account/subscriptions")!)
                    } else {
                        Button("See Pro") { showPaywall = true }
                    }
                }

                Section {
                    Picker("Goal", selection: goalBinding) {
                        ForEach(app.meta?.tracks ?? []) { track in Text(track.title).tag(track.id) }
                    }
                    Picker("Language", selection: languageBinding) {
                        ForEach(app.meta?.languages ?? []) { language in Text(language.name).tag(language.code) }
                    }
                } header: {
                    Text("Goal & language")
                } footer: {
                    Text("Changing your goal re-orders your course. Your results stay.")
                }

                Section {
                    NavigationLink("Weekly target & reminders") { PracticeSettingsView() }
                } header: {
                    Text("Practice")
                }

                Section {
                    if app.me?.voiceReference.isActive == true {
                        Label("Voice sample saved", systemImage: "checkmark.seal.fill").foregroundStyle(Theme.mint)
                        if let created = app.me?.voiceReference.createdAt {
                            Text("Recorded \(Formatting.shortDate(created))").font(.caption).foregroundStyle(Theme.inkSecondary)
                        }
                        Button("Record a new sample") { showVoiceSetup = true }
                        Button("Delete voice sample", role: .destructive) { confirmDeleteVoice = true }
                    } else {
                        Text("No voice sample. You'll pick your voice by hand in each recording.")
                            .font(.footnote)
                            .foregroundStyle(Theme.inkSecondary)
                        Button("Set up voice matching") { showVoiceSetup = true }
                    }
                } header: {
                    Text("Voice matching")
                } footer: {
                    Text("Used only to find your turns in recordings. Deleting it stops automatic matching; your recordings and results are managed separately.")
                }

                Section {
                    NavigationLink("Your recordings") { RecordingsManagerView() }
                    Button("Delete all my data", role: .destructive) { confirmDeleteAll = true }
                } header: {
                    Text("Privacy & data")
                } footer: {
                    Text("Deleting everything removes your recordings, results, voice sample and account. This can't be undone.")
                }

                Section("About") {
                    Link("Privacy policy", destination: Brand.privacyURL)
                    Link("Terms of use", destination: Brand.termsURL)
                    Link("Contact support", destination: URL(string: "mailto:\(Brand.supportEmail)")!)
                    LabeledContent("Version", value: AppConfig.appVersion)
                }

                Section("Developer") {
                    NavigationLink("Server") { ServerSettingsSheet(embedded: true) }
                    if app.isDemo {
                        Label("Server is in demo mode — AI output is simulated", systemImage: "theatermasks.fill")
                            .font(.footnote)
                            .foregroundStyle(Theme.amber)
                    }
                    if !app.isPro {
                        Button("Unlock Pro for testing") {
                            Task {
                                if await app.devGrantPro() { app.showToast("Pro unlocked (testing)") } else {
                                    error = "This server doesn't allow test unlocks."
                                }
                            }
                        }
                    }
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { dismiss() } } }
            .disabled(isWorking)
            .sheet(isPresented: $showVoiceSetup) {
                NavigationStack {
                    VoiceSetupView(mode: .standalone) { _ in showVoiceSetup = false }
                }
                .environment(app)
            }
            .sheet(isPresented: $showPaywall) { PaywallView { showPaywall = false }.environment(app) }
            .confirmationDialog("Delete your voice sample?", isPresented: $confirmDeleteVoice, titleVisibility: .visible) {
                Button("Delete", role: .destructive) {
                    Task {
                        do {
                            try await app.api.deleteVoiceReference()
                            await app.refreshMe()
                            app.showToast("Voice sample deleted")
                        } catch {
                            self.error = error.userMessage
                        }
                    }
                }
            }
            .confirmationDialog("Delete all your data?", isPresented: $confirmDeleteAll, titleVisibility: .visible) {
                Button("Delete everything", role: .destructive) {
                    Task {
                        isWorking = true
                        defer { isWorking = false }
                        do {
                            try await app.deleteEverything()
                            dismiss()
                        } catch {
                            self.error = error.userMessage
                        }
                    }
                }
            } message: {
                Text("Recordings, results, voice sample and account will be permanently deleted.")
            }
        }
    }

    private var goalBinding: Binding<String> {
        Binding(
            get: { app.course?.track.id ?? app.me?.onboarding.goalTrack ?? "" },
            set: { newValue in
                Task {
                    if let course = try? await app.api.changeTrack(newValue) {
                        app.course = course
                        await app.refreshMe()
                    }
                }
            }
        )
    }

    private var languageBinding: Binding<String> {
        Binding(
            get: { app.me?.onboarding.language ?? "en" },
            set: { newValue in
                Task {
                    var patch = MePatch()
                    patch.onboarding = MePatch.OnboardingPatch(language: newValue)
                    try? await app.updateMe(patch)
                }
            }
        )
    }
}

struct PracticeSettingsView: View {
    @Environment(AppModel.self) private var app
    @State private var weeklyTarget = 3
    @State private var remindersOn = false
    @State private var time = Calendar.current.date(bySettingHour: 19, minute: 0, second: 0, of: Date()) ?? Date()
    @State private var days: Set<Int> = [1, 3, 5]
    @State private var loaded = false
    @State private var notice: String?

    private let dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    var body: some View {
        Form {
            Section {
                Stepper("\(weeklyTarget) session\(weeklyTarget == 1 ? "" : "s") a week", value: $weeklyTarget, in: 1...7)
            } header: {
                Text("Weekly target")
            } footer: {
                Text("Pick what fits your life. Missing a week never erases progress.")
            }
            Section {
                Toggle("Remind me", isOn: $remindersOn)
                if remindersOn {
                    DatePicker("Time", selection: $time, displayedComponents: .hourAndMinute)
                    HStack(spacing: 6) {
                        ForEach(1...7, id: \.self) { day in
                            let selected = days.contains(day)
                            Button(dayNames[day - 1]) {
                                if selected { days.remove(day) } else { days.insert(day) }
                            }
                            .font(.caption.weight(.semibold))
                            .frame(maxWidth: .infinity, minHeight: 34)
                            .background(selected ? AnyShapeStyle(Theme.aurora) : AnyShapeStyle(Theme.surfaceMuted), in: Capsule())
                            .foregroundStyle(selected ? Color.white : Theme.ink)
                            .buttonStyle(.plain)
                        }
                    }
                }
                if let notice { Text(notice).font(.footnote).foregroundStyle(Theme.amber) }
            } header: {
                Text("Reminders")
            }
        }
        .navigationTitle("Practice")
        .onAppear { load() }
        .onDisappear { Task { await save() } }
    }

    private func load() {
        guard !loaded, let settings = app.me?.practiceSettings else { return }
        loaded = true
        weeklyTarget = settings.weeklyTarget
        if let reminder = settings.reminderTime, !settings.reminderDays.isEmpty {
            remindersOn = true
            days = Set(settings.reminderDays)
            let parts = reminder.split(separator: ":").compactMap { Int($0) }
            if parts.count == 2 {
                time = Calendar.current.date(bySettingHour: parts[0], minute: parts[1], second: 0, of: Date()) ?? time
            }
        }
    }

    private func save() async {
        let components = Calendar.current.dateComponents([.hour, .minute], from: time)
        let timeString = String(format: "%02d:%02d", components.hour ?? 19, components.minute ?? 0)
        let selectedDays = remindersOn ? days.sorted() : []
        var patch = MePatch()
        patch.practiceSettings = MePatch.PracticePatch(weeklyTarget: weeklyTarget, reminderTime: timeString, reminderDays: selectedDays)
        try? await app.updateMe(patch)
        if remindersOn, await ReminderScheduler.requestAuthorization() {
            await ReminderScheduler.schedule(days: selectedDays, time: timeString)
        } else {
            ReminderScheduler.cancelAll()
        }
        await app.refreshProgress()
    }
}

/// Lists recordings with separate delete controls (spec: recordings and results have their own deletion).
struct RecordingsManagerView: View {
    @Environment(AppModel.self) private var app
    @State private var recordings: [Recording] = []
    @State private var loading = true

    var body: some View {
        List {
            if recordings.isEmpty && !loading {
                Text("No recordings yet.").foregroundStyle(Theme.inkSecondary)
            }
            ForEach(recordings) { recording in
                VStack(alignment: .leading, spacing: 2) {
                    Text(recording.title).font(.subheadline.weight(.semibold))
                    Text(Formatting.shortDate(recording.createdAt)).font(.caption).foregroundStyle(Theme.inkSecondary)
                }
            }
            .onDelete { offsets in
                let targets = offsets.map { recordings[$0] }
                recordings.remove(atOffsets: offsets)
                Task {
                    for recording in targets { try? await app.api.deleteRecording(recording.id) }
                    await app.refreshAll()
                }
            }
        }
        .navigationTitle("Your recordings")
        .toolbar { EditButton() }
        .task {
            recordings = (try? await app.api.recordings()) ?? []
            loading = false
        }
    }
}

/// Point the app at a different backend (e.g. your laptop on the same Wi-Fi, or a staging server).
struct ServerSettingsSheet: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    var embedded = false
    @State private var url = AppConfig.baseURLOverride ?? ""
    @State private var status: String?

    var body: some View {
        let form = Form {
            Section {
                TextField(AppConfig.defaultBaseURL.absoluteString, text: $url)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.URL)
            } header: {
                Text("Server URL")
            } footer: {
                Text("Leave empty to use the default (\(AppConfig.defaultBaseURL.absoluteString)). On a device, use your computer's local IP, e.g. http://192.168.1.20:8000.")
            }
            Section {
                Button("Test connection") { Task { await test() } }
                Button("Save and reconnect") {
                    Task {
                        await app.changeServer(to: url.isEmpty ? nil : url)
                        dismiss()
                    }
                }
                if let status { Text(status).font(.footnote).foregroundStyle(Theme.inkSecondary) }
            }
        }
        .navigationTitle("Server")

        if embedded {
            form
        } else {
            NavigationStack {
                form.toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Close") { dismiss() } } }
            }
        }
    }

    private func test() async {
        guard let target = URL(string: url.isEmpty ? AppConfig.defaultBaseURL.absoluteString : url) else {
            status = "That doesn't look like a URL."
            return
        }
        let client = APIClient(baseURL: target)
        do {
            let health = try await client.health()
            status = "Connected · version \(health.version)\(health.demoMode ? " · demo mode" : "")"
        } catch {
            status = "Couldn't connect: \(error.userMessage)"
        }
    }
}
