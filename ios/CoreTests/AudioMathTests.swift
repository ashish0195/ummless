import XCTest
@testable import ComlogueCore

final class AudioMathTests: XCTestCase {
    private let sampleRate = 16_000.0

    /// Builds a signal of alternating tone (speech-like energy) and near-silence segments.
    private func signal(_ pattern: [(isTone: Bool, seconds: Double)], amplitude: Float = 0.3, noise: Float = 0.0005) -> [Float] {
        var samples: [Float] = []
        var phase: Float = 0
        var seed: UInt32 = 7
        func nextNoise() -> Float {
            seed = seed &* 1_103_515_245 &+ 12_345
            return (Float(seed % 2000) / 1000 - 1) * noise
        }
        for segment in pattern {
            let count = Int(segment.seconds * sampleRate)
            for _ in 0..<count {
                phase += 2 * .pi * 220 / Float(sampleRate)
                let tone = segment.isTone ? amplitude * sin(phase) : 0
                samples.append(tone + nextNoise())
            }
        }
        return samples
    }

    func testSpeechSecondsAndPauses() {
        let samples = signal([(false, 0.5), (true, 2.0), (false, 0.6), (true, 1.5), (false, 0.5)])
        let analysis = AudioMath.analyze(samples: samples, sampleRate: sampleRate)
        XCTAssertEqual(analysis.metrics.durationSeconds, 5.1, accuracy: 0.01)
        XCTAssertEqual(analysis.metrics.speechSeconds, 3.5, accuracy: 0.15)
        XCTAssertEqual(analysis.pauses.count, 1)
        XCTAssertEqual(analysis.metrics.pauseCount, 1)
        XCTAssertTrue(analysis.hasSpeech)
        XCTAssertTrue(AudioMath.localIssues(analysis.metrics).isEmpty, "\(AudioMath.localIssues(analysis.metrics))")
    }

    func testSilenceIsFlaggedAsNoSpeech() {
        let samples = signal([(false, 3.0)])
        let analysis = AudioMath.analyze(samples: samples, sampleRate: sampleRate)
        XCTAssertFalse(analysis.hasSpeech)
        XCTAssertEqual(AudioMath.localIssues(analysis.metrics).first, .noSpeech)
        XCTAssertTrue(LocalAudioIssue.noSpeech.isBlocking)
    }

    func testQuietSpeechIsFlagged() {
        let samples = signal([(false, 0.5), (true, 2.0), (false, 0.5)], amplitude: 0.004, noise: 0.00001)
        let analysis = AudioMath.analyze(samples: samples, sampleRate: sampleRate)
        XCTAssertTrue(AudioMath.localIssues(analysis.metrics).contains(.tooQuiet))
    }

    func testShortGapsDoNotCountAsPauses() {
        let samples = signal([(true, 1.0), (false, 0.1), (true, 1.0)])
        let analysis = AudioMath.analyze(samples: samples, sampleRate: sampleRate)
        XCTAssertEqual(analysis.pauses.count, 0)
    }

    func testRhythmMatchRewardsSimilarTiming() {
        let reference = AudioMath.analyze(samples: signal([(true, 1.0), (false, 0.8), (true, 1.0), (false, 0.8), (true, 1.0)]), sampleRate: sampleRate)
        let similar = AudioMath.analyze(samples: signal([(true, 1.1), (false, 0.7), (true, 0.9), (false, 0.8), (true, 1.0)]), sampleRate: sampleRate)
        let rushed = AudioMath.analyze(samples: signal([(true, 1.6)]), sampleRate: sampleRate)

        let good = AudioMath.rhythmMatch(reference: reference, attempt: similar)
        let poor = AudioMath.rhythmMatch(reference: reference, attempt: rushed)
        XCTAssertGreaterThan(good.score, 80)
        XCTAssertLessThan(poor.score, good.score)
        XCTAssertEqual(good.referencePauses, 2)
        XCTAssertEqual(poor.attemptPauses, 0)
    }

    func testNormalizedLevelIsClamped() {
        XCTAssertEqual(AudioMath.normalizedLevel(decibels: -120), 0)
        XCTAssertEqual(AudioMath.normalizedLevel(decibels: 3), 1, accuracy: 0.0001)
        XCTAssertEqual(AudioMath.normalizedLevel(decibels: .nan), 0)
    }
}

final class SyntheticReferenceTests: XCTestCase {
    func testPauseMarkersBecomePauses() {
        let reference = AudioMath.syntheticReference(
            text: "Here's the decision. [pause] Here's who owns it. [pause] Disagree now or commit.",
            wordsPerMinute: 140, pauseSeconds: 1.2
        )
        XCTAssertEqual(reference.pauses.count, 2)
        XCTAssertEqual(reference.metrics.pauseCount, 2)
        // 11 words at 140 wpm ≈ 4.7 s of speech plus two 1.2 s pauses.
        XCTAssertEqual(reference.metrics.speechSeconds, 11.0 / 140 * 60, accuracy: 0.15)
        XCTAssertEqual(reference.metrics.durationSeconds, 11.0 / 140 * 60 + 2.4, accuracy: 0.2)
    }

    func testLineWithoutMarkersHasNoPauses() {
        let reference = AudioMath.syntheticReference(text: "Four score and seven years ago", wordsPerMinute: 120, pauseSeconds: 1)
        XCTAssertTrue(reference.pauses.isEmpty)
        XCTAssertTrue(reference.hasSpeech)
    }
}
