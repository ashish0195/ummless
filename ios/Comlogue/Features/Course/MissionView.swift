import SwiftUI

@MainActor
@Observable
final class MissionModel {
    let missionId: String
    private let app: AppModel
    var mission: Mission?
    var error: String?
    var activeConversation: Conversation?
    var feedbackAttempt: MissionAttempt?
    var showComplete = false
    var showReflection = false
    var showPaywall = false
    var isStarting = false
    var isWaitingForFeedback = false

    init(missionId: String, app: AppModel) {
        self.missionId = missionId
        self.app = app
    }

    func load() async {
        do {
            mission = try await app.api.mission(missionId)
            error = nil
        } catch {
            self.error = error.userMessage
        }
    }

    /// - Parameter harder: an optional tougher partner once the basic attempt feels comfortable.
    func startAttempt(quick: Bool, harder: Bool = false) async {
        guard !isStarting else { return }
        if mission?.isLocked == true { showPaywall = true; return }
        isStarting = true
        defer { isStarting = false }
        do {
            activeConversation = try await app.api.createConversation(
                CreateConversationRequest(kind: "mission", missionId: missionId, quick: quick, difficulty: harder ? .brutal : nil)
            )
        } catch let apiError as APIError where apiError.isSubscriptionRequired {
            showPaywall = true
        } catch {
            self.error = error.userMessage
        }
    }

    /// After the conversation ends, wait for the attempt's feedback and show it.
    func attemptFinished(_ result: FinishResult?) async {
        activeConversation = nil
        isWaitingForFeedback = true
        defer { isWaitingForFeedback = false }
        let attemptId = result?.resultRef?.id
        for _ in 0..<60 {
            await load()
            let attempt = attemptId.flatMap { id in mission?.attempts.first { $0.id == id } } ?? mission?.latestAttempt
            if let attempt, !attempt.isProcessing {
                feedbackAttempt = attempt
                await app.refreshProgress()
                return
            }
            try? await Task.sleep(nanoseconds: 2_000_000_000)
        }
        error = "Your feedback is taking longer than usual. It'll appear here when it's ready."
    }

    func complete(takeaway: String?) async -> Bool {
        do {
            mission = try await app.api.completeMission(missionId, takeaway: takeaway)
            await app.refreshAll()
            Haptics.success()
            return true
        } catch {
            self.error = error.userMessage
            return false
        }
    }

    func reflect(text: String, went: String?) async -> Reflection? {
        do {
            let reflection = try await app.api.addReflection(missionId: missionId, text: text, went: went)
            await load()
            return reflection
        } catch {
            self.error = error.userMessage
            return nil
        }
    }
}

/// One mission: situation, one observable target, an example, an AI attempt with feedback, optional retry,
/// and a clear finish (save a takeaway). Real-life missions add a reflection, with an AI alternative.
struct MissionView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let missionId: String
    var autoStartQuick: Bool = false
    var isRoot: Bool = false
    @State private var model: MissionModel?
    @State private var didAutoStart = false

    var body: some View {
        Group {
            if let model, let mission = model.mission {
                MissionContent(model: model, mission: mission)
            } else if let error = model?.error {
                ErrorStateView(message: error) { Task { await model?.load() } }
            } else {
                LoadingStateView()
            }
        }
        .screenBackground()
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if isRoot {
                ToolbarItem(placement: .topBarTrailing) {
                    CircleIconButton(systemName: "xmark") { app.dismissFlow() }
                }
            }
        }
        .task {
            if model == nil {
                let created = MissionModel(missionId: missionId, app: app)
                model = created
                await created.load()
                if autoStartQuick && !didAutoStart {
                    didAutoStart = true
                    await created.startAttempt(quick: true)
                }
            }
        }
    }
}

private struct MissionContent: View {
    @Environment(AppModel.self) private var app
    @Bindable var model: MissionModel
    let mission: Mission
    @State private var showsHow = false

    private var color: Color { Theme.color(for: mission.dimension) }
    private var hasAssessableAttempt: Bool {
        mission.attempts.contains { $0.feedback?.assessable == .yes || $0.feedback?.assessable == .partly }
    }

    /// Plain words for the mission type, shown above the conversation. A real-life mission's conversation is the
    /// rehearsal before the real thing.
    private var typeLabel: String {
        mission.type == .realLife ? "Rehearsal" : MissionCatalog.title(mission.type)
    }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(mission.title).font(.display).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
                        HStack(spacing: 10) {
                            if mission.isCompleted {
                                Label("Completed", systemImage: "checkmark.seal.fill").foregroundStyle(Theme.mint)
                            }
                            Text("\(mission.minutes) min · \(DimensionCatalog.title(mission.dimension))").foregroundStyle(Theme.inkSecondary)
                        }
                        .font(.subheadline.weight(.semibold))
                    }

                    if let error = model.error { InlineErrorBanner(message: error) { model.error = nil } }

                    if model.isWaitingForFeedback {
                        HStack(spacing: 10) {
                            ProgressView()
                            Text("Looking at how your attempt went…").font(.subheadline).foregroundStyle(Theme.inkSecondary)
                        }
                        .card()
                    }

                    infoCard("The situation", icon: "theatermasks.fill", text: mission.context, tint: Theme.inkSecondary)

                    VStack(alignment: .leading, spacing: 8) {
                        Eyebrow("Your target", color: color)
                        Text(mission.targetBehavior).font(.title3Rounded).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
                        DetailToggle(title: "How this works", isExpanded: $showsHow, tint: color)
                        if showsHow {
                            Text(mission.whyItMatters).font(.footnote).foregroundStyle(Theme.inkSecondary).fixedSize(horizontal: false, vertical: true)
                            ForEach(Array(mission.steps.enumerated()), id: \.offset) { index, step in
                                HStack(alignment: .top, spacing: 10) {
                                    Text("\(index + 1)").font(.caption.weight(.bold)).foregroundStyle(.white)
                                        .frame(width: 22, height: 22).background(color, in: Circle())
                                    Text(step).font(.subheadline).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
                                }
                            }
                        }
                    }
                    .padding(18)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(color.opacity(0.1), in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))

                    ExampleCard(example: mission.example, color: color)

                    if let realLife = mission.realLife {
                        realLifeCard(realLife)
                    }

                    if !mission.attempts.isEmpty {
                        attemptsSection
                    }

                    if !mission.reflections.isEmpty {
                        reflectionsSection
                    }

                    if let takeaway = mission.takeaway {
                        infoCard("Your takeaway", icon: "bookmark.fill", text: takeaway, tint: Theme.mint)
                    }
                }
                .padding(Theme.gutter)
            }
            footer
                .padding(.horizontal, Theme.gutter)
                .padding(.bottom, 12)
        }
        .fullScreenCover(item: $model.activeConversation) { conversation in
            ConversationScreen(
                conversation: conversation,
                app: app,
                progressLabel: typeLabel,
                finishTitle: "See feedback",
                endTitle: "End & get feedback",
                onFinished: { result in Task { await model.attemptFinished(result) } },
                onExit: { model.activeConversation = nil }
            )
            .environment(app)
        }
        .sheet(item: $model.feedbackAttempt) { attempt in
            AttemptFeedbackView(attempt: attempt, mission: mission, onRetry: {
                model.feedbackAttempt = nil
                Task { await model.startAttempt(quick: attempt.quick) }
            }, onFinish: {
                model.feedbackAttempt = nil
                model.showComplete = true
            })
            .environment(app)
        }
        .sheet(isPresented: $model.showComplete) {
            CompleteMissionSheet(suggestion: mission.attempts.last?.feedback?.oneChange) { takeaway in
                await model.complete(takeaway: takeaway)
            }
        }
        .sheet(isPresented: $model.showReflection) {
            ReflectionSheet(questions: mission.realLife?.reflectionQuestions ?? []) { text, went in
                await model.reflect(text: text, went: went)
            }
        }
        .sheet(isPresented: $model.showPaywall) {
            PaywallView { model.showPaywall = false }
                .environment(app)
        }
    }

    // MARK: Pieces

    private func infoCard(_ title: String, icon: String, text: String, tint: Color) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Label(title, systemImage: icon).font(.subheadline.weight(.semibold)).foregroundStyle(tint)
            Text(text).font(.body).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
        }
        .card()
    }

    private func realLifeCard(_ realLife: RealLifeTask) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("In real life", systemImage: "figure.walk").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.coral)
            Text(realLife.prompt).font(.title3Rounded).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
            if !realLife.reflectionQuestions.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Afterwards, reflect on:").font(.caption.weight(.semibold)).foregroundStyle(Theme.inkSecondary)
                    ForEach(realLife.reflectionQuestions, id: \.self) { question in
                        Text("• \(question)").font(.footnote).foregroundStyle(Theme.inkSecondary)
                    }
                }
            }
            Button("I tried it — reflect") { model.showReflection = true }
                .buttonStyle(.secondaryPill)
            Button(realLife.aiAlternativeTitle) { Task { await model.startAttempt(quick: false) } }
                .font(.footnote.weight(.semibold))
                .foregroundStyle(Theme.indigo)
                .frame(maxWidth: .infinity)
            Text("Reflections shape your goals. Only what we can hear changes your skill levels.")
                .font(.caption2)
                .foregroundStyle(Theme.inkTertiary)
        }
        .card()
    }

    private var attemptsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader("Your attempts")
            ForEach(mission.attempts.sorted { $0.attemptNumber > $1.attemptNumber }) { attempt in
                Button {
                    if attempt.feedback != nil { model.feedbackAttempt = attempt }
                } label: {
                    HStack(spacing: 12) {
                        Text("#\(attempt.attemptNumber)").font(.headline.monospacedDigit()).foregroundStyle(color).frame(width: 34)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(attempt.feedback?.headline ?? (attempt.isProcessing ? "Feedback on the way…" : "No feedback"))
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(Theme.ink)
                                .lineLimit(2)
                            Text(Formatting.relative(attempt.createdAt) + (attempt.quick ? " · 2-minute version" : ""))
                                .font(.caption)
                                .foregroundStyle(Theme.inkSecondary)
                        }
                        Spacer()
                        if let feedback = attempt.feedback { TargetMetBadge(targetMet: feedback.targetMet, assessable: feedback.assessable) }
                    }
                    .card(padding: 14)
                }
                .buttonStyle(.pressableCard)
            }
        }
    }

    private var reflectionsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader("Reflections")
            ForEach(mission.reflections) { reflection in
                VStack(alignment: .leading, spacing: 8) {
                    Text(reflection.text).font(.subheadline).foregroundStyle(Theme.ink)
                    if let reply = reflection.coachReply {
                        HStack(alignment: .top, spacing: 8) {
                            Image(systemName: "sparkles").foregroundStyle(Theme.violet)
                            Text(reply).font(.footnote).foregroundStyle(Theme.inkSecondary)
                        }
                    }
                }
                .card(padding: 14)
            }
        }
    }

    @ViewBuilder
    private var footer: some View {
        if mission.isLocked {
            VStack(spacing: 6) {
                Button {
                    model.showPaywall = true
                } label: {
                    Label("Unlock with Pro", systemImage: "lock.open.fill")
                }
                .buttonStyle(.primaryPill)
                Text("You're seeing a preview of this mission.").font(.caption).foregroundStyle(Theme.inkSecondary)
            }
        } else if mission.type == .weeklyReveal {
            Button("Open your weekly reveal") { app.present(.weeklyReview) }
                .buttonStyle(.primaryPill)
        } else {
            VStack(spacing: 8) {
                if mission.realLife == nil {
                    Button {
                        Task { await model.startAttempt(quick: false) }
                    } label: {
                        if model.isStarting { ProgressView().tint(.white) } else {
                            Label(mission.attempts.isEmpty ? "Start" : "Try again", systemImage: "mic.fill")
                        }
                    }
                    .buttonStyle(.primaryPill)
                    .disabled(model.isStarting)
                }
                HStack(spacing: 18) {
                    if mission.realLife == nil && mission.attempts.isEmpty {
                        Button("2-minute version") { Task { await model.startAttempt(quick: true) } }
                    }
                    if mission.realLife == nil && hasAssessableAttempt {
                        Button("Harder challenge") { Task { await model.startAttempt(quick: false, harder: true) } }
                    }
                    if (hasAssessableAttempt || !mission.reflections.isEmpty) && !mission.isCompleted {
                        Button("Finish") { model.showComplete = true }
                    }
                }
                .font(.footnote.weight(.semibold))
                .foregroundStyle(Theme.indigo)
            }
        }
    }
}

private struct ExampleCard: View {
    @Environment(AppModel.self) private var app
    let example: MissionExample
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Eyebrow("Example", color: color)
                Spacer()
                Button {
                    play()
                } label: {
                    Label("Listen", systemImage: "speaker.wave.2.fill").font(.caption.weight(.semibold))
                }
                .foregroundStyle(color)
            }
            Text("“\(example.text)”").font(.body).italic().foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
            Text(example.explanation).font(.footnote).foregroundStyle(Theme.inkSecondary)
        }
        .card()
    }

    private func play() {
        if let url = example.audioUrl {
            app.player.toggle(path: url, api: app.api, key: "example-\(url)")
        } else if app.speech.isSpeaking {
            app.speech.stop()
        } else {
            app.speech.speak(example.text, languageCode: app.speechLanguage)
        }
    }
}

struct TargetMetBadge: View {
    let targetMet: String
    let assessable: Usable

    var body: some View {
        if assessable == .no {
            Tag(text: "Not assessable", color: Theme.inkSecondary)
        } else {
            switch targetMet {
            case "yes": Tag(text: "Target hit", color: Theme.mint, systemImage: "checkmark")
            case "partly": Tag(text: "Partly", color: Theme.amber)
            case "no": Tag(text: "Not yet", color: Theme.coral)
            default: Tag(text: "Unclear", color: Theme.inkSecondary)
            }
        }
    }
}
