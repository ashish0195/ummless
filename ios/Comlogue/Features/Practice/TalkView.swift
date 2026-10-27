import SwiftUI

/// "Steal their style": learn what makes a speaker work, then shadow them line by line. The rhythm match is
/// computed on-device against the talk's documented pace and pause markers — a practice signal, not a skill score.
@MainActor
struct TalkView: View {
    private enum Mode: String, CaseIterable, Identifiable {
        case learn = "Learn", shadow = "Try it"
        var id: String { rawValue }
    }

    @Environment(AppModel.self) private var app
    let talkId: String
    @State private var talk: Talk?
    @State private var error: String?
    @State private var mode: Mode = .learn
    @State private var lineIndex = 0
    @State private var recorder = AudioRecorder()
    @State private var match: RhythmMatch?
    @State private var isAnalysing = false
    @State private var showPaywall = false

    var body: some View {
        Group {
            if let talk {
                content(talk)
            } else if let error {
                ErrorStateView(message: error) { Task { await load() } }
            } else {
                LoadingStateView()
            }
        }
        .screenBackground()
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .onDisappear {
            app.player.stop()
            app.speech.stop()
            if recorder.isActive { recorder.discard() }
        }
        .sheet(isPresented: $showPaywall) { PaywallView { showPaywall = false }.environment(app) }
    }

    @ViewBuilder
    private func content(_ talk: Talk) -> some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 10) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(talk.title).font(.titleRounded).foregroundStyle(Theme.ink)
                    Text(talk.speaker).font(.subheadline).foregroundStyle(Theme.inkSecondary)
                }
                Picker("Mode", selection: $mode) {
                    ForEach(Mode.allCases) { mode in Text(mode.rawValue).tag(mode) }
                }
                .pickerStyle(.segmented)
            }
            .padding(Theme.gutter)
            if talk.locked {
                VStack(spacing: 14) {
                    Spacer()
                    Image(systemName: "lock.fill").font(.largeTitle).foregroundStyle(Theme.inkTertiary)
                    Text("This talk is part of Pro").font(.headlineRounded)
                    Button("See Pro") { showPaywall = true }.buttonStyle(.pill(.primary, fullWidth: false))
                    Spacer()
                }
                .frame(maxWidth: .infinity)
            } else if mode == .learn {
                learn(talk)
            } else {
                shadow(talk)
            }
        }
    }

    // MARK: Learn

    private func learn(_ talk: Talk) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 8) {
                    Eyebrow("The technique", color: Theme.violet)
                    Text(talk.technique).font(.body).foregroundStyle(Theme.ink)
                }
                .card()
                VStack(alignment: .leading, spacing: 12) {
                    Eyebrow("Their style")
                    comparisonRow("Pace", theirs: "\(Int(talk.style.wpm)) wpm",
                                  yours: app.profile?.speechPatterns?.wordsPerMinute.map { "\(Int($0)) wpm" })
                    comparisonRow("Pauses", theirs: "\(Formatting.oneDecimal(talk.style.avgPauseSeconds)) s",
                                  yours: app.profile?.speechPatterns?.avgPauseSeconds.map { "\(Formatting.oneDecimal($0)) s" })
                    comparisonRow("Sentence length", theirs: "\(Int(talk.style.avgSentenceWords)) words", yours: nil)
                    if app.profile?.speechPatterns == nil {
                        Text("Get your profile to compare with your own.").font(.caption).foregroundStyle(Theme.inkTertiary)
                    }
                }
                .card()
                VStack(alignment: .leading, spacing: 8) {
                    Eyebrow("What to notice")
                    ForEach(talk.breakdown, id: \.self) { point in
                        Label(point, systemImage: "sparkle").font(.subheadline).foregroundStyle(Theme.ink)
                    }
                }
                .card()
                Button("Try it yourself") { mode = .shadow }.buttonStyle(.primaryPill)
                Text(talk.sourceNote).font(.caption2).foregroundStyle(Theme.inkTertiary)
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.bottom, 20)
        }
    }

    private func comparisonRow(_ title: String, theirs: String, yours: String?) -> some View {
        HStack {
            Text(title).font(.subheadline).foregroundStyle(Theme.inkSecondary)
            Spacer()
            Text(theirs).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.violet)
            if let yours {
                Text("· you \(yours)").font(.subheadline).foregroundStyle(Theme.inkSecondary)
            }
        }
    }

    // MARK: Shadow

    @ViewBuilder
    private func shadow(_ talk: Talk) -> some View {
        let lines = talk.lines
        if lines.isEmpty {
            EmptyStateView(systemImage: "text.alignleft", title: "No lines yet", message: "This talk doesn't have shadowing lines.")
        } else {
            let line = lines[min(lineIndex, lines.count - 1)]
            VStack(spacing: 18) {
                Eyebrow("Line \(line.index + 1) of \(lines.count)", color: Theme.violet)
                LineText(text: line.text)
                    .card()
                    .padding(.horizontal, Theme.gutter)
                HStack(spacing: 10) {
                    Tag(text: "\(line.pauseCount) pause\(line.pauseCount == 1 ? "" : "s")", color: Theme.violet, systemImage: "pause.fill")
                    if let match {
                        Tag(text: "Rhythm match \(match.score)%", color: match.score >= 75 ? Theme.mint : Theme.amber)
                    }
                }
                if let match {
                    Text(match.feedback).font(.footnote).foregroundStyle(Theme.inkSecondary).multilineTextAlignment(.center).padding(.horizontal, 30)
                }
                Spacer()
                if recorder.isActive {
                    RecordingStatusBar(
                        isRecording: recorder.state == .recording,
                        isPaused: recorder.state == .paused,
                        elapsed: recorder.elapsed,
                        level: recorder.level,
                        onPauseToggle: { recorder.togglePause() },
                        onStop: { Task { await evaluate(line: line, talk: talk) } }
                    )
                    .padding(.horizontal, Theme.gutter)
                } else if isAnalysing {
                    ProgressView()
                } else {
                    HStack(spacing: 24) {
                        CircleIconButton(systemName: "backward.fill", size: 48) { move(-1, count: lines.count) }
                            .disabled(lineIndex == 0)
                        Button {
                            listen(line)
                        } label: {
                            Label("Listen", systemImage: "speaker.wave.2.fill").font(.subheadline.weight(.semibold))
                        }
                        .buttonStyle(.pill(.secondary, fullWidth: false))
                        Button {
                            Task { await record() }
                        } label: {
                            Text("Your turn").font(.headline).foregroundStyle(.white)
                                .frame(width: 92, height: 92)
                                .background(Theme.coral, in: Circle())
                        }
                        .buttonStyle(.pressableCard)
                        CircleIconButton(systemName: "forward.fill", size: 48) { move(1, count: lines.count) }
                            .disabled(lineIndex >= lines.count - 1)
                    }
                }
                Text("A practice signal for timing and pauses — not a skill score.")
                    .font(.caption2)
                    .foregroundStyle(Theme.inkTertiary)
                    .padding(.bottom, 12)
            }
        }
    }

    private func move(_ delta: Int, count: Int) {
        app.player.stop()
        app.speech.stop()
        match = nil
        lineIndex = min(max(0, lineIndex + delta), count - 1)
    }

    private func listen(_ line: TalkLine) {
        if let url = line.audioUrl {
            app.player.toggle(path: url, api: app.api, key: "talk-\(talkId)-\(line.index)")
        } else {
            app.speech.speak(line.displayText, languageCode: "en")
        }
    }

    private func record() async {
        app.player.stop()
        app.speech.stop()
        match = nil
        _ = await recorder.start(quality: .conversation)
    }

    private func evaluate(line: TalkLine, talk: Talk) async {
        guard let url = recorder.stop() else { return }
        isAnalysing = true
        defer { isAnalysing = false }
        let attempt = await Task.detached(priority: .userInitiated) { AudioFileAnalyzer.analyze(url: url) }.value
        try? FileManager.default.removeItem(at: url)
        guard let attempt else { return }
        let reference = AudioMath.syntheticReference(text: line.text, wordsPerMinute: talk.style.wpm,
                                                     pauseSeconds: talk.style.avgPauseSeconds)
        withAnimation { match = AudioMath.rhythmMatch(reference: reference, attempt: attempt) }
        Haptics.success()
    }

    private func load() async {
        do {
            talk = try await app.api.talk(talkId)
            error = nil
        } catch {
            self.error = error.userMessage
        }
    }
}

/// Renders a line with its [pause] markers as visible pause beats.
private struct LineText: View {
    let text: String

    private var styled: Text {
        let parts = text.components(separatedBy: "[pause]")
        var combined = Text("")
        for (index, part) in parts.enumerated() {
            combined = combined + Text(part.trimmingCharacters(in: .whitespaces))
            if index < parts.count - 1 {
                combined = combined + Text("  ⏸  ").foregroundColor(Theme.violet)
            }
        }
        return combined
    }

    var body: some View {
        styled
            .font(.title3Rounded)
            .foregroundColor(Theme.ink)
            .multilineTextAlignment(.leading)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}
