import SwiftUI

enum AssessmentPurpose: Hashable {
    case baseline(resumeId: String?)
    case gapFill(activityId: ActivityId)

    var isGapFill: Bool {
        if case .gapFill = self { return true }
        return false
    }
}

@MainActor
@Observable
final class AssessmentFlowModel {
    enum Stage: Equatable {
        case loading
        case intro
        case activityIntro(AssessmentActivity)
        case conversation(Conversation, AssessmentActivity)
        case processing
        case result
        case failed(String)
    }

    var stage: Stage = .loading
    private(set) var assessment: Assessment?
    let purpose: AssessmentPurpose
    private let app: AppModel
    private var pollTask: Task<Void, Never>?

    init(purpose: AssessmentPurpose, app: AppModel) {
        self.purpose = purpose
        self.app = app
    }

    var activities: [AssessmentActivity] { assessment?.activities ?? [] }

    func position(of activity: AssessmentActivity) -> Int {
        (activities.firstIndex { $0.id == activity.id } ?? 0) + 1
    }

    func load() async {
        stage = .loading
        do {
            switch purpose {
            case .baseline(let resumeId):
                if let resumeId, let existing = try? await app.api.assessment(resumeId), existing.purpose == "baseline" {
                    assessment = existing
                } else {
                    let created = try await app.api.createAssessment(CreateAssessmentRequest(purpose: "baseline", activityIds: nil, targetDimensions: nil))
                    assessment = created
                    LocalFlags.activeAssessmentId = created.id
                }
            case .gapFill(let activityId):
                assessment = try await app.api.createAssessment(
                    CreateAssessmentRequest(purpose: "gap_fill", activityIds: [activityId], targetDimensions: nil)
                )
            }
            route()
        } catch {
            stage = .failed(error.userMessage)
        }
    }

    private func route() {
        guard let assessment else { return }
        switch assessment.status {
        case .processing:
            stage = .processing
            startPolling()
        case .complete, .needsRecovery:
            stage = .result
            if !purpose.isGapFill { LocalFlags.activeAssessmentId = nil }
        case .inProgress:
            if let next = assessment.nextActivity {
                if purpose.isGapFill || assessment.doneCount > 0 || next.status == .inProgress {
                    stage = .activityIntro(next)
                } else {
                    stage = .intro
                }
            } else {
                Task { await finalize() }
            }
        }
    }

    func beginFirst() {
        if let next = assessment?.nextActivity { stage = .activityIntro(next) }
    }

    func start(_ activity: AssessmentActivity) async {
        guard let assessment else { return }
        do {
            let conversation = try await app.api.startActivity(assessmentId: assessment.id, activityId: activity.id)
            stage = .conversation(conversation, activity)
        } catch {
            stage = .failed(error.userMessage)
        }
    }

    func activityFinished() async {
        await refreshAndContinue()
    }

    func skip(_ activity: AssessmentActivity) async {
        guard let assessment else { return }
        do {
            self.assessment = try await app.api.skipActivity(assessmentId: assessment.id, activityId: activity.id)
            if self.assessment?.nextActivity == nil {
                await finalize()
            } else {
                route()
            }
        } catch {
            stage = .failed(error.userMessage)
        }
    }

    func finishNow() async { await finalize() }

    private func refreshAndContinue() async {
        guard let id = assessment?.id else { return }
        do {
            assessment = try await app.api.assessment(id)
            if assessment?.nextActivity == nil {
                await finalize()
            } else {
                route()
            }
        } catch {
            stage = .failed(error.userMessage)
        }
    }

    func finalize() async {
        guard let id = assessment?.id else { return }
        stage = .processing
        do {
            assessment = try await app.api.finalizeAssessment(id)
            route()
        } catch {
            stage = .failed(error.userMessage)
        }
    }

    private func startPolling() {
        pollTask?.cancel()
        guard let id = assessment?.id else { return }
        pollTask = Task { @MainActor [weak self] in
            var delay: UInt64 = 1_500_000_000
            for _ in 0..<120 {
                try? await Task.sleep(nanoseconds: delay)
                guard let self, !Task.isCancelled else { return }
                if let updated = try? await self.app.api.assessment(id) {
                    self.assessment = updated
                    if updated.status != .processing {
                        self.route()
                        await self.app.refreshAll()
                        return
                    }
                }
                delay = min(delay + 500_000_000, 4_000_000_000)
            }
            self?.stage = .failed("This is taking longer than usual. Your conversation is saved — check back in a minute.")
        }
    }

    func stopPolling() { pollTask?.cancel() }
}

struct AssessmentFlowView: View {
    @Environment(AppModel.self) private var app
    let purpose: AssessmentPurpose
    @State private var model: AssessmentFlowModel?

    var body: some View {
        Group {
            if let model {
                AssessmentFlowContent(model: model)
            } else {
                LoadingStateView(title: "Getting ready…").screenBackground()
            }
        }
        .task {
            guard model == nil else { return }
            let created = AssessmentFlowModel(purpose: purpose, app: app)
            model = created
            await created.load()
        }
    }
}

private struct AssessmentFlowContent: View {
    @Environment(AppModel.self) private var app
    let model: AssessmentFlowModel

    var body: some View {
        Group {
            switch model.stage {
            case .loading:
                LoadingStateView(title: "Getting ready…").screenBackground()
            case .intro:
                AssessmentIntroView(activities: model.activities, estimate: model.assessment?.estimateMinutes ?? [10, 15],
                                    onStart: { model.beginFirst() }, onClose: { app.dismissFlow() })
            case .activityIntro(let activity):
                ActivityIntroView(
                    activity: activity,
                    position: model.position(of: activity),
                    total: model.activities.count,
                    isGapFill: model.purpose.isGapFill,
                    canFinishNow: (model.assessment?.doneCount ?? 0) > 0,
                    onStart: { Task { await model.start(activity) } },
                    onSkip: { Task { await model.skip(activity) } },
                    onFinishNow: { Task { await model.finishNow() } },
                    onClose: { app.dismissFlow() }
                )
            case .conversation(let conversation, let activity):
                let position = model.position(of: activity)
                let isLast = position >= model.activities.count
                ConversationScreen(
                    conversation: conversation,
                    app: app,
                    progressLabel: model.purpose.isGapFill ? "Short scenario" : "Activity \(position) of \(model.activities.count)",
                    finishTitle: isLast ? "See my results" : "Next activity",
                    endTitle: "Finish this activity",
                    onSkip: { Task { await model.skip(activity) } },
                    onFinished: { _ in Task { await model.activityFinished() } },
                    onExit: { app.dismissFlow() }
                )
                .id(conversation.id)
            case .processing:
                AssessmentProcessingView(stageLabel: model.assessment?.stage)
            case .result:
                AssessmentResultScreen(model: model)
            case .failed(let message):
                VStack {
                    HStack {
                        Spacer()
                        CircleIconButton(systemName: "xmark") { app.dismissFlow() }
                    }
                    .padding(Theme.gutter)
                    ErrorStateView(message: message) { Task { await model.load() } }
                }
                .screenBackground()
            }
        }
        .onDisappear { model.stopPolling() }
    }
}

struct AssessmentIntroView: View {
    let activities: [AssessmentActivity]
    let estimate: [Int]
    let onStart: () -> Void
    let onClose: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Spacer()
                CircleIconButton(systemName: "xmark", action: onClose)
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.top, 10)
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Eyebrow("Guided conversation · \(Formatting.minutesRange(estimate))", color: Theme.indigo)
                    Text("Five short conversations with Maya")
                        .font(.display)
                        .foregroundStyle(Theme.ink)
                    Text("Each one gives you a different chance to show how you communicate. Nothing here is a trick question.")
                        .font(.body)
                        .foregroundStyle(Theme.inkSecondary)

                    VStack(spacing: 10) {
                        ForEach(Array(activities.enumerated()), id: \.element.id) { index, activity in
                            HStack(alignment: .top, spacing: 14) {
                                Text(String(format: "%02d", index + 1))
                                    .font(.headline.monospacedDigit())
                                    .foregroundStyle(Theme.indigo)
                                    .frame(width: 30, alignment: .leading)
                                VStack(alignment: .leading, spacing: 6) {
                                    HStack {
                                        Text(activity.title).font(.headlineRounded).foregroundStyle(Theme.ink)
                                        Spacer()
                                        Text(activity.durationLabel).font(.caption.weight(.semibold)).foregroundStyle(Theme.inkSecondary)
                                    }
                                    FlowLayout(spacing: 6, lineSpacing: 6) {
                                        ForEach(activity.dimensions) { dimension in DimensionTag(dimension: dimension, compact: true) }
                                    }
                                }
                            }
                            .card(padding: 14)
                        }
                    }

                    VStack(alignment: .leading, spacing: 10) {
                        tip("timer", "Times are suggestions. The recording keeps going until you tap Done.")
                        tip("person.wave.2", "Only your microphone is analysed. We still check for background voices.")
                        tip("speaker.wave.2", "Find a quiet spot and hold the phone about a hand's width away.")
                        tip("forward.end", "You can skip any activity — skipped skills are marked \"not enough evidence\", never low.")
                    }
                    .padding(.top, 4)
                }
                .padding(Theme.gutter)
            }
            Button("Start", action: onStart)
                .buttonStyle(.primaryPill)
                .padding(.horizontal, Theme.gutter)
                .padding(.bottom, 12)
        }
        .screenBackground()
    }

    private func tip(_ icon: String, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icon).foregroundStyle(Theme.indigo).frame(width: 22)
            Text(text).font(.footnote).foregroundStyle(Theme.inkSecondary)
        }
    }
}

struct ActivityIntroView: View {
    let activity: AssessmentActivity
    let position: Int
    let total: Int
    let isGapFill: Bool
    let canFinishNow: Bool
    let onStart: () -> Void
    let onSkip: () -> Void
    let onFinishNow: () -> Void
    let onClose: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                if !isGapFill {
                    StepProgressBar(current: position - 1, total: total)
                }
                Spacer(minLength: 16)
                CircleIconButton(systemName: "xmark", action: onClose)
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.top, 10)
            Spacer()
            VStack(spacing: 18) {
                Image(systemName: ActivityCatalog.symbol(activity.id))
                    .font(.system(size: 34, weight: .semibold))
                    .foregroundStyle(.white)
                    .frame(width: 84, height: 84)
                    .background(Theme.aurora, in: Circle())
                Eyebrow(isGapFill ? "Short scenario · \(activity.durationLabel)" : "Activity \(position) of \(total) · \(activity.durationLabel)",
                        color: Theme.indigo)
                Text(activity.title).font(.display).foregroundStyle(Theme.ink).multilineTextAlignment(.center)
                Text(activity.prompt)
                    .font(.title3Rounded)
                    .foregroundStyle(Theme.inkSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 8)
                FlowLayout(spacing: 6, lineSpacing: 6) {
                    ForEach(activity.dimensions) { dimension in DimensionTag(dimension: dimension) }
                }
                .frame(maxWidth: 320)
            }
            .padding(.horizontal, Theme.gutter)
            Spacer()
            VStack(spacing: 8) {
                Button("I'm ready", action: onStart).buttonStyle(.primaryPill)
                HStack(spacing: 20) {
                    Button("Skip this one", action: onSkip)
                    if canFinishNow && !isGapFill {
                        Button("Finish & see results", action: onFinishNow)
                    }
                }
                .font(.footnote.weight(.semibold))
                .foregroundStyle(Theme.inkSecondary)
                .padding(.top, 4)
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.bottom, 12)
        }
        .screenBackground()
    }
}

struct AssessmentProcessingView: View {
    let stageLabel: String?
    @State private var step = 0

    private let steps = [
        ("waveform", "Checking your audio"),
        ("person.crop.circle.badge.checkmark", "Confirming it's your voice"),
        ("magnifyingglass", "Looking for evidence, skill by skill"),
        ("text.badge.checkmark", "Writing your profile"),
    ]

    var body: some View {
        VStack(spacing: 28) {
            Spacer()
            VoiceOrb(level: 0.3).frame(width: 160, height: 160)
            VStack(alignment: .leading, spacing: 14) {
                ForEach(Array(steps.enumerated()), id: \.offset) { index, item in
                    HStack(spacing: 12) {
                        ZStack {
                            if index < step {
                                Image(systemName: "checkmark.circle.fill").foregroundStyle(Theme.mint)
                            } else if index == step {
                                ProgressView().controlSize(.small)
                            } else {
                                Image(systemName: item.0).foregroundStyle(Theme.inkTertiary)
                            }
                        }
                        .frame(width: 24)
                        Text(item.1)
                            .font(.subheadline.weight(index == step ? .semibold : .regular))
                            .foregroundStyle(index <= step ? Theme.ink : Theme.inkTertiary)
                    }
                }
            }
            .card()
            .padding(.horizontal, Theme.gutter)
            Text("Usually under a minute. We only score speech we're confident is yours.")
                .font(.footnote)
                .foregroundStyle(Theme.inkSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Spacer()
        }
        .screenBackground()
        .task {
            for next in 1..<steps.count {
                try? await Task.sleep(nanoseconds: 2_600_000_000)
                withAnimation { step = next }
            }
        }
    }
}

private struct AssessmentResultScreen: View {
    @Environment(AppModel.self) private var app
    let model: AssessmentFlowModel

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    if let result = model.assessment?.result {
                        AnalysisResultView(result: result) { action in app.handle(action) }
                    } else {
                        EmptyStateView(systemImage: "hourglass", title: "Results are on the way",
                                       message: "We're still putting your profile together.")
                    }
                    VStack(spacing: 10) {
                        Button(model.purpose.isGapFill ? "Back to my profile" : "See my course") {
                            app.selectedTab = model.purpose.isGapFill ? .you : .course
                            app.dismissFlow()
                        }
                        .buttonStyle(.primaryPill)
                        if !model.purpose.isGapFill {
                            Button("Add a real conversation too") { app.present(.upload) }
                                .buttonStyle(.ghostPill)
                        }
                    }
                    .padding(.top, 6)
                }
                .padding(Theme.gutter)
            }
            .screenBackground()
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    CircleIconButton(systemName: "xmark") { app.dismissFlow() }
                }
            }
        }
    }
}
