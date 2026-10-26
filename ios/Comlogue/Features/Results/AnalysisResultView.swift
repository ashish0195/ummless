import SwiftUI

/// Renders an initial assessment / communication profile result for one source (AI conversation or
/// recording). Partial results are first-class: assessed skills first, then honest "not enough evidence"
/// cards with the smallest follow-up, then recovery when nothing was assessable.
struct AnalysisResultView: View {
    @Environment(AppModel.self) private var app
    let result: AnalysisResult
    /// What this result is, shown before its context: the first baseline is an "Initial assessment".
    var kind = "Initial assessment"
    var onAction: (ResultAction) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            header

            if result.status != .noneAssessed {
                VStack(spacing: 10) {
                    CommunicationWeb(dimensions: result.dimensions)
                        .frame(maxWidth: 360)
                        .frame(maxWidth: .infinity)
                    WebLegend()
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
                SectionHeader("What we could assess", subtitle: "Applies to this conversation — people sound different in different moments.")
                ForEach(result.assessedDimensions) { dimension in
                    DimensionResultCard(result: dimension)
                }
            }

            if !result.missingDimensions.isEmpty {
                SectionHeader("Not enough evidence yet", subtitle: "Missing evidence is never a low score. Each one has a short way to fill the gap.")
                ForEach(result.missingDimensions) { dimension in
                    DimensionResultCard(result: dimension) { step in onAction(.gapFill(step.activityId)) }
                }
            }

            if let patterns = result.speechPatterns {
                SpeechPatternsCard(patterns: patterns)
            }

            StyleCard(style: result.style)
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Eyebrow("\(kind) · \(result.contextLabel)", color: Theme.indigo)
                Spacer()
                if app.isDemo { DemoBadge() }
            }
            Text(result.headline).font(.display).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
            Text(result.summary).font(.body).foregroundStyle(Theme.inkSecondary).fixedSize(horizontal: false, vertical: true)
            HStack {
                if result.status == .partial {
                    Label("\(result.assessedDimensions.count) of \(result.dimensions.count) skills assessed so far", systemImage: "circle.lefthalf.filled")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(Theme.indigo)
                }
                Spacer()
                HowItWorksLink()
            }
            .padding(.top, 2)
        }
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
