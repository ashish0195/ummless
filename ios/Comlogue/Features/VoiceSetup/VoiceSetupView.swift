import SwiftUI

/// Optional, consented voice reference used only to find the person's turns in recordings.
/// The enrollment prompt is never scored.
@MainActor
struct VoiceSetupView: View {
    enum Mode { case standalone, inline }
    enum Outcome { case enrolled, skipped }
    private enum Step: Equatable { case explain, record, review, uploading, accepted, rejected }

    @Environment(AppModel.self) private var app
    let mode: Mode
    let onDone: (Outcome) -> Void

    @State private var step: Step = .explain
    @State private var recorder = AudioRecorder()
    @State private var recordedURL: URL?
    @State private var result: VoiceEnrollmentResult?
    @State private var error: String?

    private let suggestedSeconds = 25.0

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    switch step {
                    case .explain: explain
                    case .record: recordStep
                    case .review: review
                    case .uploading: LoadingStateView(title: "Checking your sample…", subtitle: "Making sure it's one clear voice.")
                    case .accepted: accepted
                    case .rejected: rejected
                    }
                    if let error { InlineErrorBanner(message: error) { self.error = nil } }
                }
                .padding(Theme.gutter)
            }
            footer
                .padding(.horizontal, Theme.gutter)
                .padding(.bottom, 12)
        }
        .screenBackground()
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if mode == .standalone {
                ToolbarItem(placement: .topBarTrailing) {
                    CircleIconButton(systemName: "xmark") {
                        recorder.reset()
                        onDone(.skipped)
                    }
                }
            }
        }
        .onDisappear {
            app.player.stop()
            if recorder.isActive { recorder.discard() }
        }
    }

    // MARK: Steps

    private var explain: some View {
        VStack(alignment: .leading, spacing: 14) {
            Eyebrow("Voice setup · about \(app.meta?.voiceSetupEstimateMinutes ?? 1) min · optional", color: Theme.indigo)
            Text("Let's learn your voice so we can find your speaking turns")
                .font(.display)
                .foregroundStyle(Theme.ink)
                .fixedSize(horizontal: false, vertical: true)
            Text("In recordings with other people, we only give feedback on turns we're confident are yours. A short sample makes that more accurate.")
                .font(.body)
                .foregroundStyle(Theme.inkSecondary)
            VStack(alignment: .leading, spacing: 10) {
                ForEach(app.meta?.consents.voiceReference.bullets ?? defaultBullets, id: \.self) { bullet in
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: "checkmark.shield.fill").foregroundStyle(Theme.mint)
                        Text(bullet).font(.subheadline).foregroundStyle(Theme.ink)
                    }
                }
            }
            .card()
            Text("Voice matching is an estimate, not identity verification. You'll always be able to confirm or correct which voice is yours.")
                .font(.caption)
                .foregroundStyle(Theme.inkTertiary)
        }
    }

    private var recordStep: some View {
        VStack(spacing: 18) {
            Eyebrow("Say anything — this isn't scored", color: Theme.indigo)
            Text("Tell us about your morning so far. What did you do, and what's next?")
                .font(.titleRounded)
                .foregroundStyle(Theme.ink)
                .multilineTextAlignment(.center)
            ZStack {
                SuggestionTimerRing(elapsed: recorder.elapsed, suggested: suggestedSeconds)
                    .frame(width: 150, height: 150)
                VoiceOrb(level: recorder.level, isActive: recorder.state == .recording)
                    .frame(width: 112, height: 112)
            }
            .padding(.top, 8)
            SuggestionTimerCaption(elapsed: recorder.elapsed, suggested: suggestedSeconds)
            if recorder.isActive {
                RecordingStatusBar(
                    isRecording: recorder.state == .recording,
                    isPaused: recorder.state == .paused,
                    elapsed: recorder.elapsed,
                    level: recorder.level,
                    onPauseToggle: { recorder.togglePause() },
                    onStop: {
                        recordedURL = recorder.stop()
                        step = .review
                    }
                )
            }
        }
        .frame(maxWidth: .infinity)
    }

    private var review: some View {
        VStack(spacing: 16) {
            Text("Have a listen").font(.titleRounded).foregroundStyle(Theme.ink)
            Text("Is it just your voice, clear and without much background noise?")
                .font(.subheadline)
                .foregroundStyle(Theme.inkSecondary)
                .multilineTextAlignment(.center)
            if let recordedURL {
                Button {
                    if app.player.isPlaying(key: "voice-sample") {
                        app.player.stop()
                    } else {
                        app.player.play(fileURL: recordedURL, key: "voice-sample")
                    }
                } label: {
                    Label(app.player.isPlaying(key: "voice-sample") ? "Stop" : "Play my sample",
                          systemImage: app.player.isPlaying(key: "voice-sample") ? "stop.fill" : "play.fill")
                }
                .buttonStyle(.secondaryPill)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 30)
    }

    private var accepted: some View {
        VStack(spacing: 14) {
            Image(systemName: "checkmark.seal.fill").font(.system(size: 54)).foregroundStyle(Theme.mint)
            Text("Got it").font(.display).foregroundStyle(Theme.ink)
            Text(result?.message ?? "We'll use this to find your turns in recordings. You can replace or delete it any time in Settings.")
                .font(.body)
                .foregroundStyle(Theme.inkSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 40)
    }

    private var rejected: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Let's try that once more").font(.display).foregroundStyle(Theme.ink)
            Text(result?.message ?? "We couldn't use that sample.").font(.body).foregroundStyle(Theme.inkSecondary)
            if let issues = result?.issues, !issues.isEmpty { IssueCard(issues: issues) }
        }
    }

    // MARK: Footer

    @ViewBuilder
    private var footer: some View {
        switch step {
        case .explain:
            VStack(spacing: 8) {
                Button("Allow and record a sample") { Task { await startRecording() } }.buttonStyle(.primaryPill)
                Button(mode == .inline ? "Skip — I'll pick my voice in each recording" : "Not now") {
                    LocalFlags.declinedVoiceReference = true
                    onDone(.skipped)
                }
                .buttonStyle(.ghostPill)
            }
        case .record:
            if !recorder.isActive {
                Button("Start") { Task { await startRecording() } }.buttonStyle(.primaryPill)
            }
        case .review:
            VStack(spacing: 8) {
                Button("Use this sample") { Task { await upload() } }.buttonStyle(.primaryPill)
                Button("Record again") { Task { await startRecording() } }.buttonStyle(.ghostPill)
            }
        case .uploading:
            EmptyView()
        case .accepted:
            Button("Continue") { onDone(.enrolled) }.buttonStyle(.primaryPill)
        case .rejected:
            VStack(spacing: 8) {
                Button("Record again") { Task { await startRecording() } }.buttonStyle(.primaryPill)
                Button(mode == .inline ? "Skip — I'll pick my voice manually" : "Not now") { onDone(.skipped) }
                    .buttonStyle(.ghostPill)
            }
        }
    }

    private var defaultBullets: [String] {
        [
            "Used only to find your turns in recordings you add.",
            "Never used to judge how you speak.",
            "Replace or delete it any time in Settings.",
        ]
    }

    // MARK: Actions

    private func startRecording() async {
        app.player.stop()
        error = nil
        recorder.reset()
        step = .record
        if !(await recorder.start(quality: .enrollment)) {
            error = recorder.lastError
            step = .explain
        }
    }

    private func upload() async {
        guard let recordedURL else { return }
        app.player.stop()
        step = .uploading
        do {
            let file = try UploadFile.audio(at: recordedURL)
            let version = app.meta?.consents.voiceReference.version ?? "voice-reference-v1"
            let response = try await app.api.enrollVoice(file: file, consentVersion: version)
            result = response
            if response.accepted {
                LocalFlags.declinedVoiceReference = false
                try? FileManager.default.removeItem(at: recordedURL)
                await app.refreshMe()
                Haptics.success()
                step = .accepted
            } else {
                Haptics.warning()
                step = .rejected
            }
        } catch {
            self.error = error.userMessage
            step = .review
        }
    }
}
