import AVFoundation
import Observation

enum AudioPermission {
    static func request() async -> Bool {
        switch AVAudioApplication.shared.recordPermission {
        case .granted: return true
        case .denied: return false
        case .undetermined: return await AVAudioApplication.requestRecordPermission()
        @unknown default: return false
        }
    }

    static var isDenied: Bool { AVAudioApplication.shared.recordPermission == .denied }
}

enum AudioSessionManager {
    /// One category for the whole conversation so playback and recording don't fight over routes.
    static func activate() throws {
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker, .allowBluetoothA2DP])
        try session.setActive(true, options: [])
    }

    static func deactivate() {
        try? AVAudioSession.sharedInstance().setActive(false, options: [.notifyOthersOnDeactivation])
    }
}

/// Records mono AAC with live metering, pause/resume, and interruption handling.
/// It never stops by itself: suggested durations are shown by the UI only.
@MainActor
@Observable
final class AudioRecorder {
    enum State: Equatable { case idle, recording, paused, finished }

    enum Quality {
        case conversation, meeting, enrollment

        var sampleRate: Double { self == .meeting ? 22_050 : 44_100 }
        var bitRate: Int { self == .meeting ? 32_000 : 64_000 }
    }

    private(set) var state: State = .idle
    private(set) var elapsed: TimeInterval = 0
    private(set) var level: Double = 0
    private(set) var fileURL: URL?
    private(set) var notice: String?
    var lastError: String?

    private var recorder: AVAudioRecorder?
    private var meterTask: Task<Void, Never>?
    private var interruptionObserver: NSObjectProtocol?

    var isActive: Bool { state == .recording || state == .paused }

    /// Starts a new recording. Returns false (with `lastError` set) if the mic is unavailable.
    @discardableResult
    func start(quality: Quality = .conversation) async -> Bool {
        lastError = nil
        notice = nil
        guard await AudioPermission.request() else {
            lastError = "Comlogue needs microphone access. You can turn it on in Settings → Privacy → Microphone."
            return false
        }
        do {
            try AudioSessionManager.activate()
            let url = FileManager.default.temporaryDirectory.appendingPathComponent("comlogue-\(UUID().uuidString).m4a")
            let settings: [String: Any] = [
                AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
                AVSampleRateKey: quality.sampleRate,
                AVNumberOfChannelsKey: 1,
                AVEncoderBitRateKey: quality.bitRate,
                AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue,
            ]
            let recorder = try AVAudioRecorder(url: url, settings: settings)
            recorder.isMeteringEnabled = true
            recorder.prepareToRecord()
            guard recorder.record() else {
                lastError = "We couldn't start the microphone. Is another app using it?"
                return false
            }
            self.recorder = recorder
            fileURL = url
            elapsed = 0
            state = .recording
            observeInterruptions()
            startMetering()
            return true
        } catch {
            lastError = "We couldn't start recording: \(error.localizedDescription)"
            return false
        }
    }

    func pause() {
        guard state == .recording else { return }
        recorder?.pause()
        state = .paused
        level = 0
    }

    func resume() {
        guard state == .paused, let recorder else { return }
        try? AudioSessionManager.activate()
        if recorder.record() {
            state = .recording
            notice = nil
        }
    }

    func togglePause() {
        state == .paused ? resume() : pause()
    }

    /// Stops and returns the finished file.
    @discardableResult
    func stop() -> URL? {
        guard let recorder else { return fileURL }
        elapsed = max(elapsed, recorder.currentTime)
        recorder.stop()
        self.recorder = nil
        state = .finished
        level = 0
        stopMetering()
        removeInterruptionObserver()
        return fileURL
    }

    /// Stops (if needed) and deletes the current file so the person can start over.
    func discard() {
        recorder?.stop()
        recorder = nil
        stopMetering()
        removeInterruptionObserver()
        if let fileURL { try? FileManager.default.removeItem(at: fileURL) }
        fileURL = nil
        elapsed = 0
        level = 0
        state = .idle
    }

    func reset() {
        if isActive { discard() }
        state = .idle
        elapsed = 0
        fileURL = nil
    }

    // MARK: Metering

    private func startMetering() {
        meterTask?.cancel()
        meterTask = Task { @MainActor [weak self] in
            while !Task.isCancelled {
                self?.tick()
                try? await Task.sleep(nanoseconds: 50_000_000)
            }
        }
    }

    private func stopMetering() {
        meterTask?.cancel()
        meterTask = nil
    }

    private func tick() {
        guard let recorder else { return }
        if state == .recording {
            recorder.updateMeters()
            level = AudioMath.normalizedLevel(decibels: Double(recorder.averagePower(forChannel: 0)))
        }
        elapsed = recorder.currentTime
    }

    // MARK: Interruptions (calls, Siri, other apps)

    private func observeInterruptions() {
        removeInterruptionObserver()
        interruptionObserver = NotificationCenter.default.addObserver(
            forName: AVAudioSession.interruptionNotification,
            object: AVAudioSession.sharedInstance(),
            queue: .main
        ) { [weak self] notification in
            guard let raw = notification.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
                  let type = AVAudioSession.InterruptionType(rawValue: raw) else { return }
            Task { @MainActor [weak self] in
                self?.handleInterruption(type)
            }
        }
    }

    private func handleInterruption(_ type: AVAudioSession.InterruptionType) {
        switch type {
        case .began:
            if state == .recording {
                pause()
                notice = "Recording paused by an interruption. Tap resume when you're ready."
            }
        case .ended:
            break
        @unknown default:
            break
        }
    }

    private func removeInterruptionObserver() {
        if let interruptionObserver { NotificationCenter.default.removeObserver(interruptionObserver) }
        interruptionObserver = nil
    }
}

/// Reads an audio file and runs the on-device checks from `AudioMath`.
enum AudioFileAnalyzer {
    /// Analyses up to `maxSeconds` of audio (enough for a pre-upload sanity check on long meetings).
    static func analyze(url: URL, maxSeconds: Double = 600) -> AudioAnalysis? {
        guard let file = try? AVAudioFile(forReading: url) else { return nil }
        let format = file.processingFormat
        let sampleRate = format.sampleRate
        guard sampleRate > 0 else { return nil }
        let totalFrames = min(file.length, AVAudioFramePosition(sampleRate * maxSeconds))
        guard totalFrames > 0 else { return nil }

        // Read in one-second blocks, keeping roughly 16 kHz worth of samples.
        let decimation = max(1, Int(sampleRate / 16_000))
        var samples: [Float] = []
        samples.reserveCapacity(Int(totalFrames) / decimation + 1)
        let blockSize = AVAudioFrameCount(sampleRate)
        guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: blockSize) else { return nil }
        var framesRead: AVAudioFramePosition = 0
        var phase = 0
        while framesRead < totalFrames {
            let toRead = AVAudioFrameCount(min(AVAudioFramePosition(blockSize), totalFrames - framesRead))
            do {
                try file.read(into: buffer, frameCount: toRead)
            } catch {
                break
            }
            guard buffer.frameLength > 0, let channel = buffer.floatChannelData?[0] else { break }
            let count = Int(buffer.frameLength)
            var index = phase
            while index < count {
                samples.append(channel[index])
                index += decimation
            }
            phase = index - count
            framesRead += AVAudioFramePosition(count)
        }
        return AudioMath.analyze(samples: samples, sampleRate: sampleRate / Double(decimation))
    }
}
