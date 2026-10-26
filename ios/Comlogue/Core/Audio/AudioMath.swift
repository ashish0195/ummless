import Foundation

/// Frame-level analysis of a mono recording.
struct AudioAnalysis: Sendable {
    let metrics: ClientAudioMetrics
    let frameSeconds: Double
    /// One flag per frame: true where speech-like energy was detected.
    let speechMask: [Bool]
    /// Pauses inside the spoken region (start, end) in seconds.
    let pauses: [ClosedRange<Double>]

    var hasSpeech: Bool { metrics.speechSeconds >= 0.6 }
}

struct RhythmMatch: Sendable, Equatable {
    /// 0–100. A practice signal for shadowing, never a skill score.
    let score: Int
    let referencePauses: Int
    let attemptPauses: Int
    let durationRatio: Double
    let feedback: String
}

/// Dependency-free signal processing used for on-device checks before upload.
/// Thresholds mirror the server's first-pass values and still need pilot calibration.
enum AudioMath {
    static let silenceFloorDb = -60.0

    static func analyze(samples: [Float], sampleRate: Double, frameSeconds: Double = 0.02) -> AudioAnalysis {
        let frameLength = max(1, Int(sampleRate * frameSeconds))
        let frameCount = samples.count / frameLength
        let duration = sampleRate > 0 ? Double(samples.count) / sampleRate : 0
        guard frameCount > 0 else {
            return AudioAnalysis(
                metrics: ClientAudioMetrics(durationSeconds: duration, speechSeconds: 0, activeLevelDb: silenceFloorDb,
                                            noiseFloorDb: silenceFloorDb, clippingRatio: 0, pauseCount: 0, avgPauseSeconds: 0),
                frameSeconds: frameSeconds, speechMask: [], pauses: []
            )
        }

        var energies = [Double]()
        energies.reserveCapacity(frameCount)
        var clipped = 0
        for frame in 0..<frameCount {
            let start = frame * frameLength
            var sum: Float = 0
            for i in start..<(start + frameLength) {
                let sample = samples[i]
                sum += sample * sample
                if abs(sample) >= 0.99 { clipped += 1 }
            }
            let rms = sqrt(sum / Float(frameLength))
            energies.append(decibels(Double(rms)))
        }

        let sorted = energies.sorted()
        let noiseFloor = percentile(sorted, 0.10)
        // Relative to the noise floor, with an absolute floor low enough that quiet-but-clear speech is
        // reported as "too quiet" rather than "no speech".
        let threshold = max(noiseFloor + 10, -62)
        var mask = energies.map { $0 > threshold }
        mask = closeGaps(mask, maxGapFrames: Int(0.15 / frameSeconds))
        mask = removeShortRuns(mask, minFrames: max(1, Int(0.06 / frameSeconds)))

        let speechFrames = mask.filter { $0 }.count
        let speechEnergies = zip(energies, mask).filter { $0.1 }.map { $0.0 }
        let activeLevel = speechEnergies.isEmpty ? silenceFloorDb : speechEnergies.reduce(0, +) / Double(speechEnergies.count)
        let pauses = detectPauses(mask: mask, frameSeconds: frameSeconds, minPause: 0.25)
        let pauseLengths = pauses.map { $0.upperBound - $0.lowerBound }

        let metrics = ClientAudioMetrics(
            durationSeconds: duration,
            speechSeconds: Double(speechFrames) * frameSeconds,
            activeLevelDb: activeLevel,
            noiseFloorDb: noiseFloor,
            clippingRatio: samples.isEmpty ? 0 : Double(clipped) / Double(samples.count),
            pauseCount: pauses.count,
            avgPauseSeconds: pauseLengths.isEmpty ? 0 : pauseLengths.reduce(0, +) / Double(pauseLengths.count)
        )
        return AudioAnalysis(metrics: metrics, frameSeconds: frameSeconds, speechMask: mask, pauses: pauses)
    }

    /// Issues worth flagging before upload. The server makes the final call.
    static func localIssues(_ metrics: ClientAudioMetrics) -> [LocalAudioIssue] {
        var issues: [LocalAudioIssue] = []
        if metrics.speechSeconds < 0.6 { issues.append(.noSpeech) }
        else if metrics.activeLevelDb < -42 { issues.append(.tooQuiet) }
        if metrics.activeLevelDb - metrics.noiseFloorDb < 12 && metrics.speechSeconds >= 0.6 { issues.append(.noisy) }
        if metrics.clippingRatio > 0.01 { issues.append(.clipping) }
        return issues
    }

    /// Compares where the speaker paused and how long they took against a reference reading.
    static func rhythmMatch(reference: AudioAnalysis, attempt: AudioAnalysis) -> RhythmMatch {
        let ref = trimmed(reference.speechMask)
        let att = trimmed(attempt.speechMask)
        guard !ref.isEmpty, !att.isEmpty else {
            return RhythmMatch(score: 0, referencePauses: reference.pauses.count, attemptPauses: attempt.pauses.count,
                               durationRatio: 0, feedback: "We didn't hear your attempt. Try again a little closer to the mic.")
        }
        let bins = 120
        let refBins = resample(ref, bins: bins)
        let attBins = resample(att, bins: bins)
        let agreement = Double(zip(refBins, attBins).filter { $0 == $1 }.count) / Double(bins)

        let refPauses = reference.pauses.count
        let attPauses = attempt.pauses.count
        let pauseScore: Double = refPauses == 0 && attPauses == 0 ? 1 : 1 - min(1, Double(abs(refPauses - attPauses)) / Double(max(refPauses, attPauses, 1)))

        let ratio = Double(att.count) / Double(ref.count)
        let durationScore = max(0, 1 - abs(log2(ratio)))
        let score = Int((100 * (0.5 * agreement + 0.3 * pauseScore + 0.2 * durationScore)).rounded())

        let feedback: String
        if ratio < 0.8 { feedback = "You went faster than the original — let the pauses breathe." }
        else if ratio > 1.3 { feedback = "A little slower than the original. Keep the pauses, trim the gaps between words." }
        else if attPauses < refPauses { feedback = "Good pace. Try landing \(refPauses - attPauses) more deliberate pause\(refPauses - attPauses == 1 ? "" : "s")." }
        else if attPauses > refPauses + 1 { feedback = "Nice and steady. A few extra stops crept in — keep the phrases together." }
        else { feedback = "Great rhythm — pauses landed close to the original." }

        return RhythmMatch(score: min(100, max(0, score)), referencePauses: refPauses, attemptPauses: attPauses,
                           durationRatio: ratio, feedback: feedback)
    }

    /// Maps a dB value (e.g. from metering) to 0…1 for visual meters.
    static func normalizedLevel(decibels db: Double, floor: Double = -55) -> Double {
        guard db.isFinite else { return 0 }
        let clamped = min(0, max(floor, db))
        let linear = (clamped - floor) / -floor
        return pow(linear, 1.6)
    }

    static func decibels(_ amplitude: Double) -> Double {
        20 * log10(max(amplitude, 1e-6))
    }

    // MARK: Helpers

    static func percentile(_ sorted: [Double], _ p: Double) -> Double {
        guard !sorted.isEmpty else { return silenceFloorDb }
        let index = min(sorted.count - 1, max(0, Int((Double(sorted.count - 1) * p).rounded())))
        return sorted[index]
    }

    static func closeGaps(_ mask: [Bool], maxGapFrames: Int) -> [Bool] {
        guard maxGapFrames > 0, mask.count > 2 else { return mask }
        var result = mask
        var i = 0
        while i < result.count {
            if !result[i] {
                var j = i
                while j < result.count && !result[j] { j += 1 }
                let isInterior = i > 0 && j < result.count
                if isInterior && (j - i) <= maxGapFrames {
                    for k in i..<j { result[k] = true }
                }
                i = j
            } else {
                i += 1
            }
        }
        return result
    }

    static func removeShortRuns(_ mask: [Bool], minFrames: Int) -> [Bool] {
        guard minFrames > 1 else { return mask }
        var result = mask
        var i = 0
        while i < result.count {
            if result[i] {
                var j = i
                while j < result.count && result[j] { j += 1 }
                if (j - i) < minFrames { for k in i..<j { result[k] = false } }
                i = j
            } else {
                i += 1
            }
        }
        return result
    }

    static func detectPauses(mask: [Bool], frameSeconds: Double, minPause: Double) -> [ClosedRange<Double>] {
        guard let first = mask.firstIndex(of: true), let last = mask.lastIndex(of: true), first < last else { return [] }
        var pauses: [ClosedRange<Double>] = []
        var i = first
        while i <= last {
            if !mask[i] {
                var j = i
                while j <= last && !mask[j] { j += 1 }
                let length = Double(j - i) * frameSeconds
                if length >= minPause { pauses.append(Double(i) * frameSeconds...Double(j) * frameSeconds) }
                i = j
            } else {
                i += 1
            }
        }
        return pauses
    }

    static func trimmed(_ mask: [Bool]) -> [Bool] {
        guard let first = mask.firstIndex(of: true), let last = mask.lastIndex(of: true) else { return [] }
        return Array(mask[first...last])
    }

    static func resample(_ mask: [Bool], bins: Int) -> [Bool] {
        guard !mask.isEmpty, bins > 0 else { return [] }
        return (0..<bins).map { bin in
            let start = bin * mask.count / bins
            let end = max(start + 1, (bin + 1) * mask.count / bins)
            let slice = mask[start..<min(end, mask.count)]
            return slice.filter { $0 }.count * 2 >= slice.count
        }
    }
}

enum LocalAudioIssue: String, Sendable, CaseIterable {
    case noSpeech, tooQuiet, noisy, clipping

    var title: String {
        switch self {
        case .noSpeech: return "We didn't hear any speech"
        case .tooQuiet: return "That was very quiet"
        case .noisy: return "There's a lot of background noise"
        case .clipping: return "Your audio is distorting"
        }
    }

    var detail: String {
        switch self {
        case .noSpeech: return "Check that your microphone isn't covered, then try again."
        case .tooQuiet: return "Hold the phone a little closer, about a hand's width from your mouth."
        case .noisy: return "If you can, move somewhere quieter. We'll still try to use what we can."
        case .clipping: return "Hold the phone a bit further away so the loud parts don't distort."
        }
    }

    /// Only "no speech" stops an upload; everything else is a warning the server double-checks.
    var isBlocking: Bool { self == .noSpeech }
}

extension AudioMath {
    /// Builds the expected speech/pause timeline for a line of text (with `[pause]` markers) read at the
    /// talk's documented pace. Used as the shadowing reference, so rhythm matching works without
    /// downloading or analysing reference audio.
    static func syntheticReference(text: String, wordsPerMinute: Double, pauseSeconds: Double,
                                   frameSeconds: Double = 0.02) -> AudioAnalysis {
        let wpm = max(60, wordsPerMinute)
        let phrases = text.components(separatedBy: "[pause]")
            .map { $0.split(whereSeparator: { $0.isWhitespace }).count }
            .filter { $0 > 0 }
        var mask: [Bool] = []
        var pauses: [ClosedRange<Double>] = []
        let pauseFrames = max(1, Int((max(0.3, pauseSeconds) / frameSeconds).rounded()))
        for (index, words) in phrases.enumerated() {
            let speechFrames = max(1, Int((Double(words) / wpm * 60 / frameSeconds).rounded()))
            mask.append(contentsOf: Array(repeating: true, count: speechFrames))
            if index < phrases.count - 1 {
                let start = Double(mask.count) * frameSeconds
                mask.append(contentsOf: Array(repeating: false, count: pauseFrames))
                pauses.append(start...(Double(mask.count) * frameSeconds))
            }
        }
        let speechSeconds = Double(mask.filter { $0 }.count) * frameSeconds
        let metrics = ClientAudioMetrics(
            durationSeconds: Double(mask.count) * frameSeconds,
            speechSeconds: speechSeconds,
            activeLevelDb: -20,
            noiseFloorDb: -60,
            clippingRatio: 0,
            pauseCount: pauses.count,
            avgPauseSeconds: pauses.isEmpty ? 0 : pauses.map { $0.upperBound - $0.lowerBound }.reduce(0, +) / Double(pauses.count)
        )
        return AudioAnalysis(metrics: metrics, frameSeconds: frameSeconds, speechMask: mask, pauses: pauses)
    }
}
