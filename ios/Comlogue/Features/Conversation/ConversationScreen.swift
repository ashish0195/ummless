import SwiftUI

/// Full-screen AI voice conversation. Used for assessment activities, missions and spar.
@MainActor
struct ConversationScreen: View {
    @Environment(AppModel.self) private var app
    @State private var model: ConversationModel
    @State private var confirmExit = false
    @State private var confirmEnd = false

    var progressLabel: String?
    var finishTitle: String = "Continue"
    var endTitle: String = "End conversation"
    var onSkip: (() -> Void)?
    let onFinished: (FinishResult?) -> Void
    let onExit: () -> Void

    init(conversation: Conversation, app: AppModel, progressLabel: String? = nil, finishTitle: String = "Continue",
         endTitle: String = "End conversation", onSkip: (() -> Void)? = nil,
         onFinished: @escaping (FinishResult?) -> Void, onExit: @escaping () -> Void) {
        _model = State(initialValue: ConversationModel(conversation: conversation, app: app))
        self.progressLabel = progressLabel
        self.finishTitle = finishTitle
        self.endTitle = endTitle
        self.onSkip = onSkip
        self.onFinished = onFinished
        self.onExit = onExit
    }

    private var partnerColor: Color { Color(hex: model.conversation.partner.colorHex) }

    var body: some View {
        VStack(spacing: 0) {
            header
            ScrollView {
                VStack(spacing: 18) {
                    partnerStage
                    if let whisper = model.latestWhisper, model.phase != .recording {
                        CoachWhisperCard(text: whisper)
                    }
                    if let error = model.errorMessage {
                        InlineErrorBanner(message: error) { model.errorMessage = nil }
                    }
                }
                .padding(.horizontal, Theme.gutter)
                .padding(.bottom, 16)
            }
            controlPanel
                .padding(.horizontal, Theme.gutter)
                .padding(.bottom, 10)
        }
        .screenBackground()
        .onAppear { model.begin() }
        .onDisappear { model.cleanup() }
        .sheet(isPresented: $model.showTranscript) {
            TranscriptSheet(conversation: model.conversation)
        }
        .confirmationDialog("Leave this conversation?", isPresented: $confirmExit, titleVisibility: .visible) {
            Button("Leave", role: .destructive) {
                model.cleanup()
                onExit()
            }
            Button("Stay", role: .cancel) {}
        } message: {
            Text("Everything you've said so far is saved.")
        }
        .confirmationDialog(endTitle + "?", isPresented: $confirmEnd, titleVisibility: .visible) {
            Button(endTitle) { Task { await finish() } }
            Button("Keep going", role: .cancel) {}
        }
    }

    // MARK: Header

    private var header: some View {
        HStack(spacing: 12) {
            CircleIconButton(systemName: "xmark") {
                if model.phase == .recording || model.userTurnCount > 0 { confirmExit = true } else { model.cleanup(); onExit() }
            }
            VStack(alignment: .leading, spacing: 2) {
                if let progressLabel { Eyebrow(progressLabel, color: Theme.indigo) }
                Text(model.conversation.setup.title).font(.headlineRounded).foregroundStyle(Theme.ink).lineLimit(1)
            }
            Spacer()
            if model.conversation.demoMode { DemoBadge() }
            CircleIconButton(systemName: "text.bubble") { model.showTranscript = true }
                .accessibilityLabel("Show transcript")
        }
        .padding(.horizontal, Theme.gutter)
        .padding(.vertical, 10)
    }

    // MARK: Partner

    private var partnerStage: some View {
        VStack(spacing: 14) {
            if model.conversation.turns.count <= 1, !model.conversation.setup.context.isEmpty {
                Text(model.conversation.setup.context)
                    .font(.subheadline)
                    .foregroundStyle(Theme.inkSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.top, 4)
            }
            ZStack {
                VoiceOrb.tinted(partnerColor, level: model.partnerLevel, isActive: model.phase == .partnerSpeaking || model.phase == .sending)
                    .frame(width: 170, height: 170)
                Image(systemName: model.conversation.partner.symbol)
                    .font(.system(size: 34, weight: .semibold))
                    .foregroundStyle(.white.opacity(0.92))
            }
            .padding(.top, 8)
            VStack(spacing: 2) {
                Text(model.conversation.partner.name).font(.headlineRounded).foregroundStyle(Theme.ink)
                Text(model.conversation.partner.role).font(.caption).foregroundStyle(Theme.inkSecondary)
            }
            if let line = model.partnerLine {
                VStack(alignment: .leading, spacing: 10) {
                    Text(line.text)
                        .font(.title3Rounded)
                        .foregroundStyle(Theme.ink)
                        .fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    HStack {
                        Button {
                            model.replayPartner()
                        } label: {
                            Label("Replay", systemImage: "arrow.counterclockwise")
                                .font(.caption.weight(.semibold))
                        }
                        .disabled(model.phase == .recording || model.phase == .sending || model.phase == .checking)
                        Spacer()
                        if model.phase == .partnerSpeaking {
                            Button("Skip") { model.skipPartner() }.font(.caption.weight(.semibold))
                        }
                    }
                    .foregroundStyle(Theme.indigo)
                }
                .card()
                .animation(.easeInOut, value: line.index)
            }
            if let target = model.conversation.setup.targetBehavior, !target.isEmpty {
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: "scope").foregroundStyle(Theme.indigo)
                    VStack(alignment: .leading, spacing: 2) {
                        Eyebrow("Your target")
                        Text(target).font(.subheadline).foregroundStyle(Theme.ink)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(14)
                .background(Theme.indigo.opacity(0.08), in: RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous))
            }
        }
    }

    // MARK: Controls

    @ViewBuilder
    private var controlPanel: some View {
        switch model.phase {
        case .partnerSpeaking:
            VStack(spacing: 10) {
                Text("\(model.conversation.partner.name) is speaking…").font(.subheadline).foregroundStyle(Theme.inkSecondary)
                Button("Answer now") { Task { await model.startRecording() } }
                    .buttonStyle(.secondaryPill)
            }
        case .ready:
            readyPanel
        case .recording:
            recordingPanel
        case .checking, .sending:
            HStack(spacing: 12) {
                ProgressView()
                Text(model.phase == .checking ? "Checking your audio…" : "Listening to what you said…")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Theme.inkSecondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 22)
        case .retry(let issues, let local):
            retryPanel(issues: issues, local: local)
        case .uploadFailed(let message):
            VStack(spacing: 10) {
                InlineErrorBanner(message: message)
                Button("Send again") { Task { await model.retryUpload() } }.buttonStyle(.primaryPill)
                Button("Record again") { model.redo() }.buttonStyle(.ghostPill)
            }
        case .finishing:
            HStack(spacing: 12) {
                ProgressView()
                Text("Wrapping up…").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.inkSecondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 22)
        case .finished:
            VStack(spacing: 12) {
                Label("That's a wrap for this one", systemImage: "checkmark.circle.fill")
                    .font(.headlineRounded)
                    .foregroundStyle(Theme.mint)
                Button(finishTitle) { Task { await finish() } }
                    .buttonStyle(.primaryPill)
            }
        }
    }

    private var readyPanel: some View {
        VStack(spacing: 12) {
            RecordButton(isRecording: false) { Task { await model.startRecording() } }
            Text(model.userTurnCount == 0 ? "Tap to answer" : "Tap to reply")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(Theme.ink)
            Text("Suggested: about \(Formatting.shortDuration(model.suggestedSeconds)). Take the time you need.")
                .font(.caption)
                .foregroundStyle(Theme.inkSecondary)
            HStack(spacing: 18) {
                if let onSkip, model.userTurnCount == 0 {
                    Button("Skip this one") { model.cleanup(); onSkip() }
                }
                if model.canEndEarly {
                    Button(endTitle) { confirmEnd = true }
                }
            }
            .font(.footnote.weight(.semibold))
            .foregroundStyle(Theme.inkSecondary)
        }
        .frame(maxWidth: .infinity)
    }

    private var recordingPanel: some View {
        VStack(spacing: 14) {
            ZStack {
                SuggestionTimerRing(elapsed: model.recorder.elapsed, suggested: model.suggestedSeconds)
                    .frame(width: 112, height: 112)
                VoiceOrb(level: model.recorder.level, isActive: model.recorder.state == .recording)
                    .frame(width: 84, height: 84)
            }
            SuggestionTimerCaption(elapsed: model.recorder.elapsed, suggested: model.suggestedSeconds)
            if let notice = model.recorder.notice {
                Text(notice).font(.caption).foregroundStyle(Theme.amber).multilineTextAlignment(.center)
            }
            RecordingStatusBar(
                isRecording: model.recorder.state == .recording,
                isPaused: model.recorder.state == .paused,
                elapsed: model.recorder.elapsed,
                level: model.recorder.level,
                stopTitle: "Done",
                onPauseToggle: { model.togglePause() },
                onStop: { Task { await model.submit() } }
            )
            Button("Start over") { model.redo() }
                .font(.footnote.weight(.semibold))
                .foregroundStyle(Theme.inkSecondary)
        }
    }

    private func retryPanel(issues: [Issue], local: [LocalAudioIssue]) -> some View {
        VStack(spacing: 12) {
            if !local.isEmpty {
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(local, id: \.self) { issue in
                        HStack(alignment: .top, spacing: 10) {
                            Image(systemName: "mic.slash.fill").foregroundStyle(Theme.coral)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(issue.title).font(.subheadline.weight(.semibold))
                                Text(issue.detail).font(.footnote).foregroundStyle(Theme.inkSecondary)
                            }
                        }
                    }
                }
                .card()
            }
            if !issues.isEmpty { IssueCard(issues: issues) }
            Text("This isn't a judgement of how you speak — we just couldn't use that audio.")
                .font(.caption)
                .foregroundStyle(Theme.inkSecondary)
                .multilineTextAlignment(.center)
            Button("Try that again") { Task { await model.startRecording() } }.buttonStyle(.primaryPill)
            HStack(spacing: 18) {
                if let onSkip, model.userTurnCount == 0 {
                    Button("Skip this one") { model.cleanup(); onSkip() }
                }
                if model.canEndEarly {
                    Button(endTitle) { confirmEnd = true }
                }
            }
            .font(.footnote.weight(.semibold))
            .foregroundStyle(Theme.inkSecondary)
        }
    }

    private func finish() async {
        let result = await model.finish()
        if result != nil || model.conversation.status == .finished {
            onFinished(result)
        }
    }
}

struct CoachWhisperCard: View {
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "ear.badge.waveform").foregroundStyle(Theme.violet)
            VStack(alignment: .leading, spacing: 3) {
                Eyebrow("Coach whisper", color: Theme.violet)
                Text(text).font(.subheadline).foregroundStyle(Theme.ink)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(Theme.violet.opacity(0.1), in: RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous))
    }
}

struct TranscriptSheet: View {
    let conversation: Conversation
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 12) {
                    ForEach(conversation.turns) { turn in
                        HStack {
                            if turn.speaker == .user { Spacer(minLength: 40) }
                            VStack(alignment: turn.speaker == .user ? .trailing : .leading, spacing: 4) {
                                Text(turn.speaker == .user ? "You" : conversation.partner.name)
                                    .font(.caption.weight(.bold))
                                    .foregroundStyle(Theme.inkSecondary)
                                Text(turn.text.isEmpty ? "…" : turn.text)
                                    .font(.subheadline)
                                    .foregroundStyle(turn.speaker == .user ? Color.white : Theme.ink)
                                    .padding(12)
                                    .background(
                                        turn.speaker == .user ? AnyShapeStyle(Theme.aurora) : AnyShapeStyle(Theme.surface),
                                        in: RoundedRectangle(cornerRadius: 18, style: .continuous)
                                    )
                                if turn.excluded {
                                    Label("Not used — the audio wasn't clear enough", systemImage: "info.circle")
                                        .font(.caption2)
                                        .foregroundStyle(Theme.amber)
                                }
                            }
                            if turn.speaker == .partner { Spacer(minLength: 40) }
                        }
                    }
                }
                .padding(Theme.gutter)
            }
            .screenBackground()
            .navigationTitle("Transcript")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) { Button("Done") { dismiss() } }
            }
        }
    }
}
