import SwiftUI

/// A ring that drains over the suggested time. When time runs out it turns into a calm overtime
/// counter — recording never stops on its own (spec: "time is a suggestion and that's clear").
struct SuggestionTimerRing: View {
    let elapsed: Double
    let suggested: Double
    var lineWidth: CGFloat = 6

    private var remainingFraction: Double {
        guard suggested > 0 else { return 0 }
        return max(0, 1 - elapsed / suggested)
    }

    private var isOvertime: Bool { suggested > 0 && elapsed >= suggested }

    var body: some View {
        ZStack {
            Circle().stroke(Theme.stroke, lineWidth: lineWidth)
            Circle()
                .trim(from: 0, to: isOvertime ? 1 : remainingFraction)
                .stroke(isOvertime ? AnyShapeStyle(Theme.violet.opacity(0.55)) : AnyShapeStyle(Theme.aurora),
                        style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
                .rotationEffect(.degrees(-90))
                .animation(.linear(duration: 0.25), value: elapsed)
        }
        .accessibilityElement()
        .accessibilityLabel(isOvertime ? "Suggested time passed. Keep going if you're mid-thought." :
                                "\(Int(max(0, suggested - elapsed))) seconds suggested time left")
    }
}

/// Caption under the timer ring.
struct SuggestionTimerCaption: View {
    let elapsed: Double
    let suggested: Double

    var body: some View {
        VStack(spacing: 2) {
            if suggested > 0 && elapsed >= suggested {
                Text("+\(Formatting.clock(elapsed - suggested))")
                    .font(.metricSmall)
                    .foregroundStyle(Theme.violet)
                Text("Time's a suggestion — finish your thought")
                    .font(.caption)
                    .foregroundStyle(Theme.inkSecondary)
            } else {
                Text(Formatting.clock(max(0, suggested - elapsed)))
                    .font(.metricSmall)
                    .foregroundStyle(Theme.ink)
                Text("suggested · we keep recording after")
                    .font(.caption)
                    .foregroundStyle(Theme.inkSecondary)
            }
        }
        .multilineTextAlignment(.center)
    }
}

/// Always-visible recording status with pause/resume and stop (spec: status, pause and stop stay visible).
struct RecordingStatusBar: View {
    let isRecording: Bool
    let isPaused: Bool
    let elapsed: Double
    var level: Double = 0
    var stopTitle: String = "Done"
    let onPauseToggle: () -> Void
    let onStop: () -> Void

    @State private var blink = false

    var body: some View {
        HStack(spacing: 12) {
            HStack(spacing: 8) {
                Circle()
                    .fill(isPaused ? Theme.amber : Theme.recording)
                    .frame(width: 10, height: 10)
                    .opacity(isPaused ? 1 : (blink ? 0.35 : 1))
                    .animation(isPaused ? .default : .easeInOut(duration: 0.8).repeatForever(), value: blink)
                VStack(alignment: .leading, spacing: 0) {
                    Text(isPaused ? "Paused" : "Recording")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(isPaused ? Theme.amber : Theme.recording)
                    Text(Formatting.clock(elapsed))
                        .font(.subheadline.weight(.semibold).monospacedDigit())
                        .foregroundStyle(Theme.ink)
                }
            }
            LevelBars(level: isPaused ? 0 : level)
                .frame(height: 22)
            Spacer(minLength: 4)
            Button(action: onPauseToggle) {
                Image(systemName: isPaused ? "play.fill" : "pause.fill")
                    .font(.subheadline.weight(.bold))
                    .frame(width: 40, height: 40)
                    .background(Theme.surfaceMuted, in: Circle())
                    .foregroundStyle(Theme.ink)
            }
            .buttonStyle(.plain)
            .accessibilityLabel(isPaused ? "Resume recording" : "Pause recording")
            Button(action: onStop) {
                HStack(spacing: 6) {
                    Image(systemName: "stop.fill").font(.caption.weight(.bold))
                    Text(stopTitle).font(.subheadline.weight(.bold))
                }
                .padding(.horizontal, 16)
                .frame(height: 40)
                .background(Theme.ink, in: Capsule())
                .foregroundStyle(Theme.background)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Stop recording")
        }
        .padding(12)
        .background(Theme.surface, in: Capsule())
        .overlay(Capsule().strokeBorder(Theme.stroke, lineWidth: 1))
        .onAppear { blink = true }
    }
}

/// Five bars that respond to the input level.
struct LevelBars: View {
    let level: Double
    var color: Color = Theme.indigo

    var body: some View {
        HStack(alignment: .center, spacing: 3) {
            ForEach(0..<5, id: \.self) { index in
                let weights: [Double] = [0.55, 0.85, 1.0, 0.8, 0.6]
                let height = max(0.18, min(1, level * 1.6 * weights[index]))
                Capsule()
                    .fill(color.opacity(0.85))
                    .frame(width: 4)
                    .frame(maxHeight: .infinity)
                    .scaleEffect(x: 1, y: height, anchor: .center)
                    .animation(.spring(response: 0.18, dampingFraction: 0.7), value: level)
            }
        }
        .accessibilityHidden(true)
    }
}

/// The big round record button.
struct RecordButton: View {
    let isRecording: Bool
    var size: CGFloat = 84
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            ZStack {
                Circle().fill(Theme.aurora)
                    .shadow(color: Theme.indigo.opacity(0.35), radius: 16, x: 0, y: 8)
                if isRecording {
                    RoundedRectangle(cornerRadius: 6).fill(Color.white).frame(width: size * 0.3, height: size * 0.3)
                } else {
                    Image(systemName: "mic.fill").font(.system(size: size * 0.34, weight: .semibold)).foregroundStyle(.white)
                }
            }
            .frame(width: size, height: size)
        }
        .buttonStyle(.pressableCard)
        .accessibilityLabel(isRecording ? "Stop recording" : "Start recording")
    }
}
