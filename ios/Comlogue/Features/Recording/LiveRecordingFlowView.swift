import SwiftUI

/// Keep the phone recording during a real meeting or conversation, then analyse it.
@MainActor
struct LiveRecordingFlowView: View {
    private enum Stage: Equatable { case consent, voiceSetup, ready, recording, review, uploading, detail(String), failed(String) }

    @Environment(AppModel.self) private var app
    @State private var stage: Stage = .consent
    @State private var consent: RecordingConsentPayload?
    @State private var recorder = AudioRecorder()
    @State private var title = ""
    @State private var recordedURL: URL?
    @State private var path = NavigationPath()
    @State private var confirmDiscard = false

    var body: some View {
        NavigationStack(path: $path) {
            Group {
                switch stage {
                case .consent:
                    RecordingConsentView(kind: .live, onAgree: { payload in
                        consent = payload
                        let needsVoice = !(app.me?.voiceReference.isActive ?? false) && !LocalFlags.declinedVoiceReference
                        stage = needsVoice ? .voiceSetup : .ready
                    }, onUseAIPractice: {
                        app.present(.guidedAssessment(resumeId: nil))
                    })
                case .voiceSetup:
                    VoiceSetupView(mode: .inline) { _ in stage = .ready }
                case .ready:
                    readyView
                case .recording:
                    recordingView
                case .review:
                    reviewView
                case .uploading:
                    LoadingStateView(title: "Uploading your conversation…", subtitle: "Longer recordings take a little longer.")
                        .screenBackground()
                case .detail(let recordingId):
                    RecordingDetailView(recordingId: recordingId, isRoot: false)
                case .failed(let message):
                    VStack(spacing: 12) {
                        ErrorStateView(message: message) { Task { await upload() } }
                        Button("Discard recording", role: .destructive) { discard() }
                            .buttonStyle(.ghostPill)
                    }
                    .screenBackground()
                }
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    CircleIconButton(systemName: "xmark") {
                        if recorder.isActive || recordedURL != nil { confirmDiscard = true } else { app.dismissFlow() }
                    }
                }
            }
            .navigationDestination(for: String.self) { id in
                RecordingDetailView(recordingId: id, isRoot: false)
            }
        }
        .confirmationDialog("Discard this recording?", isPresented: $confirmDiscard, titleVisibility: .visible) {
            Button("Discard", role: .destructive) {
                discard()
                app.dismissFlow()
            }
            Button("Keep it", role: .cancel) {}
        }
        .onChange(of: holdsUnsavedAudio, initial: true) { _, holds in app.holdsUnsavedRecording = holds }
        .onDisappear {
            app.holdsUnsavedRecording = false
            if recorder.isActive { _ = recorder.stop() }
        }
    }

    /// Recording, paused, or recorded and not uploaded yet.
    private var holdsUnsavedAudio: Bool { recorder.isActive || recordedURL != nil }

    private var readyView: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Eyebrow("Record a conversation", color: Theme.indigo)
                    Text("Keep your phone nearby and talk as you normally would").font(.display).foregroundStyle(Theme.ink)
                    TextField("What's this conversation? (optional)", text: $title)
                        .textFieldStyle(.plain)
                        .padding(14)
                        .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous).strokeBorder(Theme.stroke))
                    VStack(alignment: .leading, spacing: 12) {
                        tip("iphone.gen3", "Place the phone face up between you and the others, not in a pocket.")
                        tip("lock.fill", "You can lock the screen — we keep recording in the background.")
                        tip("pause.circle", "Pause any time. Nothing is analysed until you choose to.")
                        tip("person.3.fill", "Everyone present has agreed to be recorded.")
                    }
                    .card()
                }
                .padding(Theme.gutter)
            }
            Button {
                Task { await start() }
            } label: {
                Label("Start recording", systemImage: "record.circle")
            }
            .buttonStyle(.primaryPill)
            .padding(.horizontal, Theme.gutter)
            .padding(.bottom, 12)
            if let error = recorder.lastError {
                InlineErrorBanner(message: error).padding(.horizontal, Theme.gutter).padding(.bottom, 8)
            }
        }
        .screenBackground()
    }

    private var recordingView: some View {
        VStack(spacing: 24) {
            Spacer()
            Text(title.isEmpty ? "Recording your conversation" : title)
                .font(.headlineRounded)
                .foregroundStyle(Theme.inkSecondary)
            Text(Formatting.clock(recorder.elapsed))
                .font(.system(size: 64, weight: .bold, design: .rounded).monospacedDigit())
                .foregroundStyle(Theme.ink)
            VoiceOrb(level: recorder.level, isActive: recorder.state == .recording)
                .frame(width: 200, height: 200)
            if let notice = recorder.notice {
                Text(notice).font(.footnote).foregroundStyle(Theme.amber).multilineTextAlignment(.center).padding(.horizontal, 30)
            }
            Spacer()
            RecordingStatusBar(
                isRecording: recorder.state == .recording,
                isPaused: recorder.state == .paused,
                elapsed: recorder.elapsed,
                level: recorder.level,
                stopTitle: "Finish",
                onPauseToggle: { recorder.togglePause() },
                onStop: {
                    recordedURL = recorder.stop()
                    stage = .review
                    Haptics.success()
                }
            )
            .padding(.horizontal, Theme.gutter)
            .padding(.bottom, 12)
        }
        .frame(maxWidth: .infinity)
        .screenBackground()
    }

    private var reviewView: some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "waveform.circle.fill").font(.system(size: 64)).foregroundStyle(Theme.indigo)
            Text("Nice — \(Formatting.clock(recorder.elapsed)) recorded").font(.display).foregroundStyle(Theme.ink)
            Text("Next we'll check the audio, find your voice, and look for evidence in each skill. You'll confirm which voice is yours before any feedback.")
                .font(.body)
                .foregroundStyle(Theme.inkSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)
            Spacer()
            VStack(spacing: 8) {
                Button("Analyse this conversation") { Task { await upload() } }.buttonStyle(.primaryPill)
                Button("Discard", role: .destructive) { confirmDiscard = true }.buttonStyle(.ghostPill)
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.bottom, 12)
        }
        .screenBackground()
    }

    private func tip(_ icon: String, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icon).foregroundStyle(Theme.indigo).frame(width: 24)
            Text(text).font(.subheadline).foregroundStyle(Theme.ink)
        }
    }

    private func start() async {
        if await recorder.start(quality: .meeting) {
            stage = .recording
            Haptics.press()
        }
    }

    private func upload() async {
        guard let recordedURL, let consent else { return }
        stage = .uploading
        do {
            let file = try UploadFile.audio(at: recordedURL)
            let recording = try await app.api.uploadRecording(file: file, source: "live",
                                                              title: title.isEmpty ? nil : title, consent: consent)
            try? FileManager.default.removeItem(at: recordedURL)
            self.recordedURL = nil
            LocalFlags.pendingRecordingIds.append(recording.id)
            stage = .detail(recording.id)
        } catch {
            stage = .failed(error.userMessage)
        }
    }

    private func discard() {
        recorder.discard()
        if let recordedURL { try? FileManager.default.removeItem(at: recordedURL) }
        recordedURL = nil
        stage = .ready
    }
}
