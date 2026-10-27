import SwiftUI

/// Renders an initial assessment / communication profile result for one source (AI conversation or
/// recording). Kept short on first look: a title, one line, the web, then each skill with one thing to try.
/// Partial results are first-class: skills we didn't hear get a quick way to fill the gap (never a low score),
/// and the full explanation and measurements stay one tap away.
struct AnalysisResultView: View {
    @Environment(AppModel.self) private var app
    let result: AnalysisResult
    /// What this result is, shown with its context under "More detail": the first baseline is an "Initial assessment".
    var kind = "Initial assessment"
    var onAction: (ResultAction) -> Void
    @State private var showsMore = false

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            header

            if result.status != .noneAssessed {
                VStack(spacing: 12) {
                    CommunicationWeb(dimensions: result.dimensions)
                        .frame(maxWidth: 360)
                        .frame(maxWidth: .infinity)
                    HStack {
                        if let coverage = SkillSummary.coverage(result.dimensions) {
                            Text(coverage).font(.caption).foregroundStyle(Theme.inkTertiary)
                        }
                        Spacer()
                        HowItWorksLink()
                    }
                }
                .card()
            }

            if let recovery = result.recovery {
                RecoveryCard(recovery: recovery) { action in onAction(.recovery(action)) }
            }

            if let win = result.firstWin {
                RewriteMomentCard(moment: win)
            }

            if !result.assessedDimensions.isEmpty {
                SectionHeader("Skill by skill")
                ForEach(result.assessedDimensions) { dimension in
                    DimensionResultCard(result: dimension)
                }
            }

            if !result.missingDimensions.isEmpty {
                SectionHeader("Fill in the gaps", subtitle: "We didn't hear these yet. That's never a low score.")
                ForEach(result.missingDimensions) { dimension in
                    DimensionResultCard(result: dimension) { step in onAction(.gapFill(step.activityId)) }
                }
            }

            StyleCard(style: result.style)

            VStack(alignment: .leading, spacing: 14) {
                DetailToggle(title: showsMore ? "Less detail" : "More detail", isExpanded: $showsMore)
                if showsMore {
                    Text("\(kind) · \(result.contextLabel)").font(.caption.weight(.semibold)).foregroundStyle(Theme.inkSecondary)
                    if SkillSummary.line(result.dimensions) != nil {
                        Text(result.summary).font(.subheadline).foregroundStyle(Theme.inkSecondary).fixedSize(horizontal: false, vertical: true)
                    }
                    if let patterns = result.speechPatterns {
                        SpeechPatternsCard(patterns: patterns)
                    }
                }
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .top) {
                Text(title).font(.display).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 8)
                if app.isDemo { DemoBadge() }
            }
            // One line when skills have levels; otherwise the server's explanation is the whole story.
            Text(SkillSummary.line(result.dimensions) ?? result.summary)
                .font(.subheadline)
                .foregroundStyle(Theme.inkSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    /// The coverage caption under the web already says how much is in, so a partial first profile keeps a short title.
    private var title: String {
        result.headline == "Your partial communication profile" ? "Your communication profile" : result.headline
    }
}

extension AppModel {
    /// Shared handling for result-screen actions so every route offers the same recovery behaviour.
    func handle(_ action: ResultAction) {
        switch action {
        case .gapFill(let activityId):
            present(.gapFill(activityId: activityId))
        case .identifySpeaker:
            break
        case .done:
            dismissFlow()
        case .recovery(let recovery):
            switch recovery.type {
            case .gapFill:
                if let activity = recovery.activityId { present(.gapFill(activityId: activity)) } else { present(.guidedAssessment(resumeId: nil)) }
            case .aiPractice:
                if let activity = recovery.activityId { present(.gapFill(activityId: activity)) } else { present(.guidedAssessment(resumeId: nil)) }
            case .retry:
                present(.guidedAssessment(resumeId: nil))
            case .uploadAnother:
                present(.upload)
            case .recordAgain:
                present(.liveRecording)
            case .starterCourse:
                selectedTab = .course
                dismissFlow()
            case .identifySpeaker:
                break
            case .continueOn:
                dismissFlow()
            }
        }
    }
}
