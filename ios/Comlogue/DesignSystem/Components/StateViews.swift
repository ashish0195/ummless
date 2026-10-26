import SwiftUI

struct LoadingStateView: View {
    var title: String = "Loading…"
    var subtitle: String?

    var body: some View {
        VStack(spacing: 16) {
            VoiceOrb(level: 0.15).frame(width: 90, height: 90)
            Text(title).font(.headlineRounded).foregroundStyle(Theme.ink)
            if let subtitle {
                Text(subtitle).font(.subheadline).foregroundStyle(Theme.inkSecondary).multilineTextAlignment(.center)
            }
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct ErrorStateView: View {
    let message: String
    var retryTitle: String = "Try again"
    let retry: () -> Void

    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 34, weight: .semibold))
                .foregroundStyle(Theme.inkTertiary)
            Text(message)
                .font(.body)
                .foregroundStyle(Theme.inkSecondary)
                .multilineTextAlignment(.center)
            Button(retryTitle, action: retry)
                .buttonStyle(.pill(.secondary, fullWidth: false))
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct EmptyStateView: View {
    let systemImage: String
    let title: String
    let message: String
    var actionTitle: String?
    var action: (() -> Void)?

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: systemImage)
                .font(.system(size: 32, weight: .semibold))
                .foregroundStyle(Theme.indigo)
                .frame(width: 64, height: 64)
                .background(Theme.indigo.opacity(0.1), in: Circle())
            Text(title).font(.headlineRounded).foregroundStyle(Theme.ink)
            Text(message).font(.subheadline).foregroundStyle(Theme.inkSecondary).multilineTextAlignment(.center)
            if let actionTitle, let action {
                Button(actionTitle, action: action).buttonStyle(.pill(.primary, fullWidth: false)).padding(.top, 4)
            }
        }
        .padding(24)
        .frame(maxWidth: .infinity)
    }
}

/// Inline banner for errors that don't replace the whole screen.
struct InlineErrorBanner: View {
    let message: String
    var onDismiss: (() -> Void)?

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "exclamationmark.circle.fill").foregroundStyle(Theme.danger)
            Text(message).font(.subheadline).foregroundStyle(Theme.ink).frame(maxWidth: .infinity, alignment: .leading)
            if let onDismiss {
                Button(action: onDismiss) { Image(systemName: "xmark").font(.caption.weight(.bold)) }
                    .buttonStyle(.plain)
                    .foregroundStyle(Theme.inkSecondary)
            }
        }
        .padding(14)
        .background(Theme.danger.opacity(0.1), in: RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous))
    }
}

/// Explains a specific audio or attribution problem — never phrased as a skill judgement.
struct IssueCard: View {
    let issues: [Issue]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ForEach(issues) { issue in
                HStack(alignment: .top, spacing: 12) {
                    Image(systemName: icon(for: issue.code))
                        .font(.body.weight(.semibold))
                        .foregroundStyle(issue.severity == .blocking ? Theme.coral : Theme.amber)
                        .frame(width: 28)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(issue.title).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                        Text(issue.detail).font(.footnote).foregroundStyle(Theme.inkSecondary)
                    }
                }
            }
        }
        .card()
    }

    private func icon(for code: String) -> String {
        switch code {
        case "too_quiet": return "speaker.wave.1.fill"
        case "noisy", "background_voices": return "waveform.badge.exclamationmark"
        case "overlapping_voices", "multiple_speakers": return "person.2.wave.2.fill"
        case "clipping": return "waveform.path.badge.minus"
        case "file_unreadable": return "doc.badge.ellipsis"
        case "speaker_uncertain", "user_not_found": return "person.crop.circle.badge.questionmark"
        case "no_speech", "too_short", "too_little_user_speech": return "mic.slash.fill"
        default: return "exclamationmark.triangle.fill"
        }
    }
}

struct SectionHeader: View {
    let title: String
    var subtitle: String?
    var trailing: AnyView?

    init(_ title: String, subtitle: String? = nil, trailing: AnyView? = nil) {
        self.title = title
        self.subtitle = subtitle
        self.trailing = trailing
    }

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.title3Rounded).foregroundStyle(Theme.ink)
                if let subtitle { Text(subtitle).font(.footnote).foregroundStyle(Theme.inkSecondary) }
            }
            Spacer()
            if let trailing { trailing }
        }
    }
}

/// Segmented progress used in multi-step flows.
struct StepProgressBar: View {
    let current: Int
    let total: Int

    var body: some View {
        HStack(spacing: 6) {
            ForEach(0..<max(total, 1), id: \.self) { index in
                Capsule()
                    .fill(index <= current ? AnyShapeStyle(Theme.aurora) : AnyShapeStyle(Theme.stroke))
                    .frame(height: 5)
            }
        }
        .animation(.easeInOut, value: current)
        .accessibilityElement()
        .accessibilityLabel("Step \(current + 1) of \(total)")
    }
}

/// A ring showing practice towards a weekly target (practice completion — not a skill measure).
struct ProgressRing: View {
    let value: Double
    var lineWidth: CGFloat = 8
    var color: AnyShapeStyle = AnyShapeStyle(Theme.aurora)

    var body: some View {
        ZStack {
            Circle().stroke(Theme.stroke, lineWidth: lineWidth)
            Circle()
                .trim(from: 0, to: min(1, max(0.001, value)))
                .stroke(color, style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
                .rotationEffect(.degrees(-90))
                .animation(.spring(response: 0.6, dampingFraction: 0.8), value: value)
        }
    }
}
