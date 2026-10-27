import SwiftUI
import UIKit

struct SettingsView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var showVoiceSetup = false
    @State private var confirmDeleteVoice = false
    @State private var confirmDeleteAll = false
    @State private var showPaywall = false
    @State private var error: String?
    @State private var isWorking = false
    @State private var isExporting = false
    @State private var exportFile: SharedFile?

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
                    Text("Your results stay if you change your goal.")
                }

                Section {
                    NavigationLink {
                        PracticePlanView()
                    } label: {
                        Label("Practice plan", systemImage: "calendar.badge.clock")
                    }
                    NavigationLink {
                        NotificationSettingsView()
                    } label: {
                        Label("Notifications", systemImage: "bell.badge")
                    }
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
                        Button("Set up voice matching") { showVoiceSetup = true }
                    }
                } header: {
                    Text("Voice matching")
                } footer: {
                    Text("Used only to find your voice in recordings.")
                }

                Section {
                    NavigationLink("Your recordings") { RecordingsManagerView() }
                    Button {
                        Task { await exportData() }
                    } label: {
                        HStack {
                            Text("Download my data")
                            if isExporting { Spacer(); ProgressView() }
                        }
                    }
                    .disabled(isExporting)
                    if let support = app.meta?.support {
                        Link(destination: URL(string: "mailto:\(support.grievanceEmail)")!) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(app.market == .in ? "Grievance officer" : "Privacy questions")
                                Text([support.grievanceOfficer, support.grievanceEmail].compactMap { $0 }.joined(separator: " · "))
                                    .font(.caption)
                                    .foregroundStyle(Theme.inkSecondary)
                            }
                        }
                    }
                    Button("Delete all my data", role: .destructive) { confirmDeleteAll = true }
                } header: {
                    Text("Privacy & data")
                } footer: {
                    Text("The download has everything we store about you, except audio.")
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
            .sheet(item: $exportFile) { file in ActivityView(items: [file.url]) }
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

    private func exportData() async {
        isExporting = true
        defer { isExporting = false }
        do {
            let data = try await app.api.exportData()
            let url = FileManager.default.temporaryDirectory.appendingPathComponent("comlogue-export.json")
            try data.write(to: url, options: .atomic)
            exportFile = SharedFile(url: url)
        } catch {
            self.error = error.userMessage
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


/// A file ready to hand to the share sheet.
struct SharedFile: Identifiable {
    let url: URL
    var id: String { url.absoluteString }
}

/// The system share sheet, for files.
struct ActivityView: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
