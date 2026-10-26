import SwiftUI

/// Something the person can do from a result screen.
enum ResultAction: Hashable {
    case gapFill(ActivityId)
    case recovery(RecoveryAction)
    case identifySpeaker
    case done
}

/// A playable quote that supports a result ("moment"). Audio is only shown when the server provides it.
struct EvidenceMomentRow: View {
    @Environment(AppModel.self) private var app
    let moment: EvidenceMoment
    var tint: Color = Theme.indigo

    private var key: String { "moment-\(moment.sourceId)-\(moment.turnIndex ?? -1)-\(moment.startSeconds ?? -1)" }

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            if let url = moment.audioUrl {
                Button {
                    app.player.toggle(path: url, api: app.api, key: key, start: moment.startSeconds, end: moment.endSeconds)
                } label: {
                    Image(systemName: app.player.isPlaying(key: key) ? "stop.fill" : "play.fill")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(.white)
                        .frame(width: 30, height: 30)
                        .background(tint, in: Circle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Play this moment")
            } else {
                Image(systemName: "quote.opening")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(tint)
                    .frame(width: 30, height: 30)
                    .background(tint.opacity(0.12), in: Circle())
            }
            VStack(alignment: .leading, spacing: 4) {
                Text("“\(moment.quote)”")
                    .font(.subheadline)
                    .italic()
                    .foregroundStyle(Theme.ink)
                    .fixedSize(horizontal: false, vertical: true)
                if let note = moment.note, !note.isEmpty {
                    Text(note).font(.caption).foregroundStyle(Theme.inkSecondary)
                }
                if let start = moment.startSeconds {
                    Text("at \(Formatting.clock(start))").font(.caption2.monospacedDigit()).foregroundStyle(Theme.inkTertiary)
                }
            }
        }
    }
}

/// One dimension with level, separate evidence confidence, and the moments behind it.
struct DimensionResultCard: View {
    let result: DimensionResult
    var expanded: Bool = true
    var onNextStep: ((NextStep) -> Void)?

    private var color: Color { Theme.color(for: result.dimension) }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                Image(systemName: DimensionCatalog.symbol(result.dimension))
                    .font(.subheadline.weight(.bold))
                    .foregroundStyle(.white)
                    .frame(width: 34, height: 34)
                    .background(result.status.hasLevel ? color : Theme.inkTertiary, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                VStack(alignment: .leading, spacing: 2) {
                    Text(result.title).font(.headlineRounded).foregroundStyle(Theme.ink)
                    if let level = result.displayLevel {
                        HStack(spacing: 6) {
                            Text(result.levelLabel ?? DimensionCatalog.levelLabel(level))
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(color)
                            if result.status == .provisional {
                                Tag(text: "Early read", color: Theme.amber)
                            }
                        }
                    } else {
                        Text("Not enough evidence yet").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.inkSecondary)
                    }
                }
                Spacer()
                if let level = result.displayLevel {
                    LevelDots(level: level, color: color)
                }
            }

            if result.status.hasLevel {
                HStack(spacing: 8) {
                    Tag(text: DimensionCatalog.confidenceLabel(result.confidence), color: Theme.inkSecondary, systemImage: "gauge.with.dots.needle.33percent")
                    if let context = result.contextLabel { Tag(text: context, color: Theme.inkSecondary) }
                }
                if let summary = result.summary {
                    Text(summary).font(.subheadline).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
                }
                if expanded {
                    if !result.strengths.isEmpty {
                        VStack(alignment: .leading, spacing: 6) {
                            ForEach(result.strengths, id: \.self) { strength in
                                Label(strength, systemImage: "checkmark")
                                    .font(.footnote)
                                    .foregroundStyle(Theme.ink)
                            }
                        }
                    }
                    if let change = result.oneChange {
                        HStack(alignment: .top, spacing: 8) {
                            Image(systemName: "arrow.turn.down.right").foregroundStyle(color)
                            VStack(alignment: .leading, spacing: 2) {
                                Eyebrow("One thing to try", color: color)
                                Text(change).font(.subheadline).foregroundStyle(Theme.ink)
                            }
                        }
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(color.opacity(0.08), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    }
                    if !result.evidence.isEmpty {
                        VStack(alignment: .leading, spacing: 10) {
                            Eyebrow("Moments behind this")
                            ForEach(Array(result.evidence.enumerated()), id: \.offset) { _, moment in
                                EvidenceMomentRow(moment: moment, tint: color)
                            }
                        }
                    }
                }
            } else {
                Text(result.missingReason ?? "We didn't hear a clear chance to show this skill yet. That says nothing about how good you are at it.")
                    .font(.subheadline)
                    .foregroundStyle(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
                if let step = result.nextStep, let onNextStep {
                    Button {
                        onNextStep(step)
                    } label: {
                        Label("\(step.title) · \(step.minutes) min", systemImage: "play.circle.fill")
                            .font(.subheadline.weight(.semibold))
                    }
                    .buttonStyle(.pill(.secondary, fullWidth: false))
                }
            }
        }
        .card()
    }
}

/// Five small dots for the level band — a visual aid, not a score.
struct LevelDots: View {
    let level: Int
    let color: Color

    var body: some View {
        HStack(spacing: 3) {
            ForEach(1...5, id: \.self) { index in
                Circle()
                    .fill(index <= level ? color : Theme.stroke)
                    .frame(width: 7, height: 7)
            }
        }
        .accessibilityLabel("Level \(level) of 5, \(DimensionCatalog.levelLabel(level))")
    }
}

/// "Try this next time" — the first practical win from a real moment.
struct RewriteMomentCard: View {
    @Environment(AppModel.self) private var app
    let moment: RewriteMoment
    var title: String = "Your first win"

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Eyebrow(title, color: Theme.coral)
                Spacer()
                if let dimension = moment.dimension { DimensionTag(dimension: dimension, compact: true) }
            }
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("You said").font(.caption.weight(.bold)).foregroundStyle(Theme.inkSecondary)
                    if let start = moment.startSeconds { Text("· \(Formatting.clock(start))").font(.caption.monospacedDigit()).foregroundStyle(Theme.inkTertiary) }
                    Spacer()
                    if let url = moment.audioUrl {
                        let key = "rewrite-\(moment.sourceId)-\(moment.startSeconds ?? -1)"
                        Button {
                            app.player.toggle(path: url, api: app.api, key: key, start: moment.startSeconds, end: moment.endSeconds)
                        } label: {
                            Image(systemName: app.player.isPlaying(key: key) ? "stop.circle.fill" : "play.circle.fill")
                                .font(.title3)
                                .foregroundStyle(Theme.inkSecondary)
                        }
                        .buttonStyle(.plain)
                    }
                }
                Text("“\(moment.youSaid)”").font(.subheadline).foregroundStyle(Theme.inkSecondary)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.surfaceMuted, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            VStack(alignment: .leading, spacing: 6) {
                Text("Try").font(.caption.weight(.bold)).foregroundStyle(.white.opacity(0.85))
                Text("“\(moment.tryInstead)”").font(.headlineRounded).foregroundStyle(.white)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.aurora, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            Text(moment.why).font(.footnote).foregroundStyle(Theme.inkSecondary)
        }
        .card()
    }
}

/// Descriptive measurements from the sample — explicitly not scores.
struct SpeechPatternsCard: View {
    let patterns: SpeechPatterns

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Eyebrow("How you sounded in this sample")
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                metric("Pace", patterns.wordsPerMinute.map { "\(Int($0)) wpm" })
                metric("Fillers", patterns.languageSupported ? patterns.fillerPerMinute.map { "\(Formatting.oneDecimal($0))/min" } : nil,
                       unavailable: patterns.languageSupported ? nil : "Not available in this language yet")
                metric("Avg. pause", patterns.avgPauseSeconds.map { "\(Formatting.oneDecimal($0)) s" })
                metric("Longest turn", patterns.longestTurnSeconds.map { Formatting.clock($0) })
                if let share = patterns.talkShare { metric("Your talk share", Formatting.percent(share)) }
                metric("Your speech", Formatting.clock(patterns.userSpeechSeconds))
            }
            if !patterns.topFillers.isEmpty {
                Text("Most common fillers: " + patterns.topFillers.prefix(3).map { "“\($0)”" }.joined(separator: ", "))
                    .font(.caption)
                    .foregroundStyle(Theme.inkSecondary)
            }
            Text("These are measurements from this recording, not scores. A good pace depends on the moment.")
                .font(.caption)
                .foregroundStyle(Theme.inkTertiary)
        }
        .card()
    }

    private func metric(_ title: String, _ value: String?, unavailable: String? = nil) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.caption).foregroundStyle(Theme.inkSecondary)
            Text(value ?? "—").font(.metricSmall).foregroundStyle(value == nil ? Theme.inkTertiary : Theme.ink)
            if let unavailable { Text(unavailable).font(.caption2).foregroundStyle(Theme.inkTertiary) }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct StyleCard: View {
    let style: StyleResult

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Eyebrow("Your style", color: Theme.violet)
                Spacer()
                if style.status == .provisional { Tag(text: "Provisional", color: Theme.amber) }
            }
            if style.status == .notReady {
                Text(style.message ?? "We need more conversation to describe your style.")
                    .font(.subheadline)
                    .foregroundStyle(Theme.inkSecondary)
            } else {
                if let archetype = style.archetype {
                    Text(archetype).font(.titleRounded).foregroundStyle(Theme.ink)
                }
                if let description = style.description {
                    Text(description).font(.subheadline).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
                }
                if !style.traits.isEmpty {
                    FlowLayout(spacing: 6, lineSpacing: 6) {
                        ForEach(style.traits, id: \.self) { trait in Tag(text: trait, color: Theme.violet) }
                    }
                }
                if let message = style.message {
                    Text(message).font(.caption).foregroundStyle(Theme.inkTertiary)
                }
            }
        }
        .card()
    }
}

struct TwinCard: View {
    let twin: TwinResult
    var onNextStep: ((NextStep) -> Void)?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Eyebrow("Conversational twin · beta", color: Theme.coral)
                Spacer()
            }
            if twin.isReady {
                ForEach(twin.matches) { match in
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text(match.aspectTitle).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                            Spacer()
                            Text(Formatting.percent(match.closeness) + " close").font(.caption.weight(.semibold)).foregroundStyle(Theme.coral)
                        }
                        Text(match.referenceName).font(.headlineRounded).foregroundStyle(Theme.ink)
                        Text(match.referenceBlurb).font(.footnote).foregroundStyle(Theme.inkSecondary)
                        Text("You: \(match.yourValue) · Them: \(match.referenceValue)").font(.caption).foregroundStyle(Theme.inkTertiary)
                    }
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Theme.surfaceMuted, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                }
            } else {
                Text(twin.message).font(.subheadline).foregroundStyle(Theme.inkSecondary)
                if let step = twin.nextStep, let onNextStep {
                    Button { onNextStep(step) } label: {
                        Label("\(step.title) · \(step.minutes) min", systemImage: "play.circle.fill").font(.subheadline.weight(.semibold))
                    }
                    .buttonStyle(.pill(.secondary, fullWidth: false))
                }
            }
            Text(twin.disclaimer).font(.caption2).foregroundStyle(Theme.inkTertiary)
        }
        .card()
    }
}

/// Explains what's missing and offers the smallest useful next step. Never a skill judgement.
struct RecoveryCard: View {
    let recovery: Recovery
    let onAction: (RecoveryAction) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                Image(systemName: icon).font(.title3).foregroundStyle(Theme.amber)
                Text(recovery.title).font(.headlineRounded).foregroundStyle(Theme.ink)
            }
            Text(recovery.message).font(.subheadline).foregroundStyle(Theme.inkSecondary).fixedSize(horizontal: false, vertical: true)
            if let minutes = recovery.extraMinutes {
                Label("About \(minutes) more min", systemImage: "clock").font(.caption.weight(.semibold)).foregroundStyle(Theme.inkSecondary)
            }
            VStack(spacing: 8) {
                ForEach(Array(recovery.actions.enumerated()), id: \.offset) { index, action in
                    Button(action.title) { onAction(action) }
                        .buttonStyle(.pill(index == 0 ? .primary : .secondary))
                }
            }
        }
        .card()
    }

    private var icon: String {
        switch recovery.problem {
        case "file_unreadable": return "doc.badge.ellipsis"
        case "audio_unclear": return "speaker.slash.fill"
        case "speaker_uncertain": return "person.crop.circle.badge.questionmark"
        default: return "puzzlepiece.extension.fill"
        }
    }
}

/// Legend for the communication web.
struct WebLegend: View {
    var body: some View {
        HStack(spacing: 14) {
            legendItem(Circle().fill(Theme.indigo), "Assessed")
            legendItem(Circle().strokeBorder(Theme.indigo, lineWidth: 2), "Early read")
            HStack(spacing: 5) {
                Text("?").font(.caption2.weight(.heavy)).foregroundStyle(Theme.inkTertiary)
                    .frame(width: 12, height: 12)
                    .background(Circle().fill(Theme.surfaceMuted))
                Text("Not enough evidence yet").font(.caption2).foregroundStyle(Theme.inkSecondary)
            }
        }
    }

    private func legendItem<S: View>(_ shape: S, _ label: String) -> some View {
        HStack(spacing: 5) {
            shape.frame(width: 9, height: 9)
            Text(label).font(.caption2).foregroundStyle(Theme.inkSecondary)
        }
    }
}
