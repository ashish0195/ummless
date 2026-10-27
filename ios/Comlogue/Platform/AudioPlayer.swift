import AVFoundation
import Observation

/// Plays partner lines, evidence moments and examples. Supports playing a sub-range (start…end) of a file,
/// exposes a level for the voice orb, and caches downloads for the session.
@MainActor
@Observable
final class AudioPlayer {
    private(set) var isPlaying = false
    private(set) var isLoading = false
    private(set) var level: Double = 0
    private(set) var currentKey: String?
    var lastError: String?

    private var player: AVAudioPlayer?
    private var meterTask: Task<Void, Never>?
    private var stopAt: TimeInterval?
    private var onFinish: (() -> Void)?
    private var cache: [String: Data] = [:]

    /// Downloads (with auth) and plays an API audio URL.
    func play(path: String, api: APIClient, key: String? = nil, start: TimeInterval? = nil, end: TimeInterval? = nil,
              onFinish: (() -> Void)? = nil) async {
        let cacheKey = key ?? path
        stop()
        currentKey = cacheKey
        if let cached = cache[path] {
            play(data: cached, key: cacheKey, start: start, end: end, onFinish: onFinish)
            return
        }
        isLoading = true
        defer { isLoading = false }
        do {
            let data = try await api.download(path)
            guard currentKey == cacheKey else { return } // something else started meanwhile
            cache[path] = data
            play(data: data, key: cacheKey, start: start, end: end, onFinish: onFinish)
        } catch {
            lastError = error.userMessage
            currentKey = nil
            onFinish?()
        }
    }

    func play(fileURL: URL, key: String, start: TimeInterval? = nil, end: TimeInterval? = nil, onFinish: (() -> Void)? = nil) {
        guard let data = try? Data(contentsOf: fileURL) else {
            lastError = "That recording isn't available any more."
            onFinish?()
            return
        }
        play(data: data, key: key, start: start, end: end, onFinish: onFinish)
    }

    func play(data: Data, key: String, start: TimeInterval? = nil, end: TimeInterval? = nil, onFinish: (() -> Void)? = nil) {
        stop()
        do {
            try AudioSessionManager.activate()
            let player = try AVAudioPlayer(data: data)
            player.isMeteringEnabled = true
            player.prepareToPlay()
            if let start, start > 0, start < player.duration { player.currentTime = start }
            stopAt = end
            self.onFinish = onFinish
            self.player = player
            currentKey = key
            player.play()
            isPlaying = true
            startMetering()
        } catch {
            lastError = "We couldn't play that audio."
            currentKey = nil
            onFinish?()
        }
    }

    func toggle(path: String, api: APIClient, key: String? = nil, start: TimeInterval? = nil, end: TimeInterval? = nil) {
        let cacheKey = key ?? path
        if isPlaying && currentKey == cacheKey {
            stop()
        } else {
            Task { await play(path: path, api: api, key: cacheKey, start: start, end: end) }
        }
    }

    func isPlaying(key: String) -> Bool { isPlaying && currentKey == key }

    func stop() {
        let finish = onFinish
        onFinish = nil
        player?.stop()
        player = nil
        meterTask?.cancel()
        meterTask = nil
        isPlaying = false
        level = 0
        stopAt = nil
        currentKey = nil
        finish?()
    }

    private func startMetering() {
        meterTask?.cancel()
        meterTask = Task { @MainActor [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                if !self.tick() { return }
                try? await Task.sleep(nanoseconds: 40_000_000)
            }
        }
    }

    /// Returns false once playback has finished.
    private func tick() -> Bool {
        guard let player else { return false }
        if let stopAt, player.currentTime >= stopAt {
            stop()
            return false
        }
        if !player.isPlaying {
            stop()
            return false
        }
        player.updateMeters()
        level = AudioMath.normalizedLevel(decibels: Double(player.averagePower(forChannel: 0)))
        return true
    }
}

/// On-device speech for partner lines when the server has no TTS audio (demo mode, or TTS unavailable).
@MainActor
@Observable
final class SpeechFallback {
    private(set) var isSpeaking = false

    private let synthesizer = AVSpeechSynthesizer()
    private let delegate = SpeechDelegate()
    private var currentUtterance: AVSpeechUtterance?
    private var pendingFinish: (() -> Void)?

    init() {
        synthesizer.delegate = delegate
        delegate.onFinish = { [weak self] utterance in
            Task { @MainActor [weak self] in
                self?.handleFinished(utterance)
            }
        }
    }

    /// - Parameters:
    ///   - languageCode: "en", "hi", or a regional code such as "en-IN" to prefer that accent.
    ///   - variant: picks a different voice for each speaker in a group conversation.
    func speak(_ text: String, languageCode: String, variant: Int = 0, onFinish: (() -> Void)? = nil) {
        stop()
        try? AudioSessionManager.activate()
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = Self.voice(for: languageCode, variant: variant)
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate * 0.98
        utterance.pitchMultiplier = 1.02
        currentUtterance = utterance
        pendingFinish = onFinish
        isSpeaking = true
        synthesizer.speak(utterance)
    }

    func stop() {
        currentUtterance = nil
        pendingFinish = nil
        isSpeaking = false
        if synthesizer.isSpeaking { synthesizer.stopSpeaking(at: .immediate) }
    }

    /// Ignores callbacks from utterances that were replaced or cancelled.
    private func handleFinished(_ utterance: AVSpeechUtterance) {
        guard let currentUtterance, utterance === currentUtterance else { return }
        self.currentUtterance = nil
        isSpeaking = false
        let finish = pendingFinish
        pendingFinish = nil
        finish?()
    }

    static func bestVoice(for languageCode: String) -> AVSpeechSynthesisVoice? { voice(for: languageCode, variant: 0) }

    /// The best voices for the language (an exact regional match such as en-IN first), varied by `variant`.
    static func voice(for languageCode: String, variant: Int) -> AVSpeechSynthesisVoice? {
        let prefix = String(languageCode.prefix(2))
        let all = AVSpeechSynthesisVoice.speechVoices().filter { $0.language.hasPrefix(prefix) }
        let regional = all.filter { $0.language.caseInsensitiveCompare(languageCode) == .orderedSame }
        let pool = (regional.isEmpty ? all : regional).sorted {
            ($0.quality.rawValue, $0.identifier) > ($1.quality.rawValue, $1.identifier)
        }
        guard !pool.isEmpty else { return AVSpeechSynthesisVoice(language: languageCode) }
        return pool[variant % pool.count]
    }
}

private final class SpeechDelegate: NSObject, AVSpeechSynthesizerDelegate {
    var onFinish: ((AVSpeechUtterance) -> Void)?

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        onFinish?(utterance)
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        onFinish?(utterance)
    }
}
