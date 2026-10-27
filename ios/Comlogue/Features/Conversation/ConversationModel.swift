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
    /// Partner lines still to play (several in a row in a group conversation).
    private var speakQueue: [Turn] = []
    /// The line being spoken, or the last one spoken.
    private(set) var speakingTurn: Turn?

    init(conversation: Conversation, app: AppModel) {
        self.conversation = conversation
        self.app = app
    }

    var partnerLine: Turn? { speakingTurn ?? conversation.lastPartnerTurn }

    /// Who's talking now in a group conversation (the moderator before anyone has spoken).
    var currentSpeaker: Participant? {
        guard conversation.isGroup else { return nil }
        return conversation.participant(partnerLine?.speakerId) ?? conversation.participants?.first
    }
    var suggestedSeconds: Double { Double(conversation.setup.suggestedSeconds) }
    var userTurnCount: Int { conversation.turns.filter { $0.speaker == .user && !$0.excluded }.count }
    var canEndEarly: Bool { userTurnCount > 0 || conversation.kind == "spar" || conversation.kind == "group" }
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
        // Everything the partners said since the person last spoke: the opening, or a few voices in a group.
        let trailing = Array(conversation.turns.reversed().prefix { $0.speaker == .partner }.reversed())
        if conversation.status == .finished {
            phase = .finished
        } else if !trailing.isEmpty {
            speak(trailing)
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

    func speak(_ turn: Turn) { speak([turn]) }

    /// Plays partner lines one after another, then hands the floor back.
    func speak(_ turns: [Turn]) {
        speakQueue = turns
        playNext()
    }

    private func playNext() {
        guard !speakQueue.isEmpty else {
            if phase == .partnerSpeaking { phase = conversation.status == .finished ? .finished : .ready }
            return
        }
        let turn = speakQueue.removeFirst()
        speakingTurn = turn
        phase = .partnerSpeaking
        let done: () -> Void = { [weak self] in
            guard let self, self.phase == .partnerSpeaking else { return }
            self.playNext()
        }
        if let url = turn.audioUrl {
            let key = "turn-\(conversation.id)-\(turn.index)"
            Task { await app.player.play(path: url, api: app.api, key: key, onFinish: done) }
        } else {
            let voiceIndex = conversation.participants?.firstIndex { $0.id == turn.speakerId } ?? 0
            app.speech.speak(turn.text, languageCode: app.speechLanguage, variant: voiceIndex, onFinish: done)
        }
    }

    func replayPartner() {
        guard let line = partnerLine, phase != .recording, phase != .sending else { return }
        speak(line)
    }

    func skipPartner() {
        speakQueue = []
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
            } else if !result.allPartnerTurns.isEmpty {
                speak(result.allPartnerTurns)
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
