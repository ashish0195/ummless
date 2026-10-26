import Foundation
import Observation

/// Drives one AI voice conversation: partner speaks → person records (timer is only a suggestion) →
/// on-device sanity check → upload → partner replies, or a specific recovery if the audio wasn't usable.
@MainActor
@Observable
final class ConversationModel {
    enum Phase: Equatable {
        case partnerSpeaking
        case ready
        case recording
        case checking
        case sending
        case retry(issues: [Issue], local: [LocalAudioIssue])
        case uploadFailed(String)
        case finishing
        case finished
    }

    private(set) var conversation: Conversation
    var phase: Phase = .ready
    var showTranscript = false
    var errorMessage: String?
    let recorder = AudioRecorder()

    private let app: AppModel
    private var pendingUpload: (url: URL, elapsed: Double, metrics: ClientAudioMetrics?)?
    private var hasBegun = false

    init(conversation: Conversation, app: AppModel) {
        self.conversation = conversation
        self.app = app
    }

    var partnerLine: Turn? { conversation.lastPartnerTurn }
    var suggestedSeconds: Double { Double(conversation.setup.suggestedSeconds) }
    var userTurnCount: Int { conversation.turns.filter { $0.speaker == .user && !$0.excluded }.count }
    var canEndEarly: Bool { userTurnCount > 0 || conversation.kind == "spar" }
    var isSpar: Bool { conversation.kind == "spar" }

    var partnerLevel: Double {
        if app.player.isPlaying { return max(0.1, app.player.level) }
        if app.speech.isSpeaking { return 0.45 }
        return 0.06
    }

    var latestWhisper: String? {
        guard let line = partnerLine else { return nil }
        return line.coachWhisper
    }

    // MARK: Lifecycle

    func begin() {
        guard !hasBegun else { return }
        hasBegun = true
        if conversation.status == .finished {
            phase = .finished
        } else if let last = conversation.turns.last, last.speaker == .partner {
            speak(last)
        } else {
            phase = .ready
        }
    }

    func cleanup() {
        app.player.stop()
        app.speech.stop()
        if recorder.isActive { recorder.discard() }
    }

    // MARK: Partner

    func speak(_ turn: Turn) {
        phase = .partnerSpeaking
        let done: () -> Void = { [weak self] in
            guard let self, self.phase == .partnerSpeaking else { return }
            self.phase = self.conversation.status == .finished ? .finished : .ready
        }
        if let url = turn.audioUrl {
            let key = "turn-\(conversation.id)-\(turn.index)"
            Task { await app.player.play(path: url, api: app.api, key: key, onFinish: done) }
        } else {
            app.speech.speak(turn.text, languageCode: app.language, onFinish: done)
        }
    }

    func replayPartner() {
        guard let line = partnerLine, phase != .recording, phase != .sending else { return }
        speak(line)
    }

    func skipPartner() {
        app.player.stop()
        app.speech.stop()
        phase = conversation.status == .finished ? .finished : .ready
    }

    // MARK: Recording

    func startRecording() async {
        app.player.stop()
        app.speech.stop()
        errorMessage = nil
        if await recorder.start(quality: .conversation) {
            phase = .recording
            Haptics.press()
        } else {
            errorMessage = recorder.lastError
            phase = .ready
        }
    }

    func togglePause() {
        recorder.togglePause()
        Haptics.tap()
    }

    func redo() {
        recorder.discard()
        phase = .ready
    }

    /// Stops recording, runs the on-device check and sends the turn.
    func submit() async {
        guard let url = recorder.stop() else { return }
        let elapsed = recorder.elapsed
        phase = .checking
        let analysis = await Task.detached(priority: .userInitiated) {
            AudioFileAnalyzer.analyze(url: url)
        }.value
        let local = analysis.map { AudioMath.localIssues($0.metrics) } ?? []
        if local.contains(where: \.isBlocking) {
            try? FileManager.default.removeItem(at: url)
            phase = .retry(issues: [], local: local)
            Haptics.warning()
            return
        }
        pendingUpload = (url, elapsed, analysis?.metrics)
        await upload()
    }

    func retryUpload() async {
        await upload()
    }

    private func upload() async {
        guard let pending = pendingUpload else { phase = .ready; return }
        phase = .sending
        do {
            let file = try UploadFile.audio(at: pending.url)
            let result = try await app.api.sendTurn(conversationId: conversation.id, file: file,
                                                     elapsedSeconds: pending.elapsed, metrics: pending.metrics)
            try? FileManager.default.removeItem(at: pending.url)
            pendingUpload = nil
            conversation = result.conversation
            if result.retrySuggested {
                phase = .retry(issues: result.userTurn.quality?.issues ?? [], local: [])
                Haptics.warning()
            } else if let partner = result.partnerTurn {
                speak(partner)
            } else if result.done || conversation.status == .finished {
                phase = .finished
                Haptics.success()
            } else {
                phase = .ready
            }
        } catch {
            phase = .uploadFailed(error.userMessage)
        }
    }

    // MARK: Finishing

    /// Ends the conversation on the server (idempotent) and returns where its result will appear.
    func finish() async -> FinishResult? {
        cleanup()
        phase = .finishing
        do {
            let result = try await app.api.finishConversation(conversation.id)
            conversation = result.conversation
            phase = .finished
            return result
        } catch {
            errorMessage = error.userMessage
            phase = conversation.status == .finished ? .finished : .ready
            return nil
        }
    }
}
