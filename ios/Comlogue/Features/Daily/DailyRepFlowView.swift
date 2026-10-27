import SwiftUI

/// Today's 60-second rep: read the prompt → speak once → feedback on one target → try again or done.
@MainActor
@Observable
final class DailyRepModel {
    enum Stage: Equatable {
        case loading
        case intro
        case conversation(Conversation)
        case waiting
        case feedback
        case failed(String)
    }

    var stage: Stage = .loading
    var rep: DailyRep?
    var isShuffling = false
    var error: String?
    private let requestedDate: String?
    private let app: AppModel
    private var pollTask: Task<Void, Never>?

    init(date: String?, app: AppModel) {
        requestedDate = date
        self.app = app
    }

    /// A reminder for today links to today's date, which may arrive before the app has loaded today's rep.
    var isToday: Bool {
        requestedDate == nil || requestedDate == app.daily?.date
            || requestedDate == HabitMath.dayString(Date(), timeZone: .current)
    }

    /// The server takes attempts for today's rep, or yesterday's just after midnight.
    var canPractise: Bool {
        guard let date = rep?.date ?? requestedDate else { return true }
        let yesterday = HabitMath.dayString(HabitMath.adding(days: -1, to: Date(), timeZone: .current), timeZone: .current)
        return isToday || date >= yesterday
    }

    /// "Mon, 26 Oct" in the person's locale.
    static func displayDay(_ day: String) -> String {
        guard let date = HabitMath.date(fromDay: day, timeZone: .current) else { return day }
        return date.formatted(.dateTime.weekday(.abbreviated).day().month(.abbreviated))
    }

    func load() async {
        if isToday, let today = app.daily {
            rep = today
        }
        do {
            if let requestedDate {
                rep = try await app.api.dailyRep(date: requestedDate)
            } else {
                rep = try await app.api.dailyRep()
            }
            if isToday { app.daily = rep }
            route()
        } catch {
            if rep != nil { route() } else { stage = .failed(error.userMessage) }
        }
    }

    private func route() {
        guard let rep else { return }
        if rep.isProcessing {
            stage = .waiting
            poll()
        } else if !isToday, rep.latestAttempt?.feedback != nil {
            // An earlier day from the week strip or a notification: show how it went.
            stage = .feedback
        } else {
            stage = .intro
        }
    }

    func shuffle() async {
        isShuffling = true
        defer { isShuffling = false }
        do {
            let fresh = try await app.api.shuffleDailyRep()
            rep = fresh
            app.daily = fresh
            Haptics.selection()
        } catch {
            self.error = error.userMessage
        }
    }

    func start() async {
        guard let rep else { return }
        do {
            let conversation = try await app.api.createConversation(CreateConversationRequest(kind: "daily", dailyDate: rep.date))
            stage = .conversation(conversation)
        } catch {
            self.error = error.userMessage
        }
    }

    func finished() {
        stage = .waiting
        poll()
    }

    func showFeedback() { stage = .feedback }

    private func poll() {
        pollTask?.cancel()
        guard let date = rep?.date else { return }
        pollTask = Task { @MainActor [weak self] in
            var delay: UInt64 = 1_200_000_000
            for _ in 0..<60 {
                try? await Task.sleep(nanoseconds: delay)
                guard let self, !Task.isCancelled else { return }
                if let updated = try? await self.app.api.dailyRep(date: date) {
                    self.rep = updated
                    if !updated.isProcessing {
                        if self.isToday { self.app.daily = updated }
                        self.stage = updated.latestAttempt == nil ? .intro : .feedback
                        if updated.completed { Haptics.success() }
                        await self.app.refreshProgress()
                        return
                    }
                }
                delay = min(delay + 500_000_000, 3_000_000_000)
            }
            self?.stage = .failed("Feedback is taking longer than usual. Your rep is saved — check back in a minute.")
        }
    }

    func stopPolling() { pollTask?.cancel() }
}

struct DailyRepFlowView: View {
    @Environment(AppModel.self) private var app
    let date: String?
    @State private var model: DailyRepModel?

    var body: some View {
        Group {
            if let model {
                DailyRepContent(model: model)
            } else {
                LoadingStateView(title: "Getting today's rep…").screenBackground()
            }
        }
        .task {
            guard model == nil else { return }
            let created = DailyRepModel(date: date, app: app)
            model = created
            await created.load()
        }
    }
}

private struct DailyRepContent: View {
    @Environment(AppModel.self) private var app
    let model: DailyRepModel

    var body: some View {
        Group {
            switch model.stage {
            case .loading:
                LoadingStateView(title: "Getting today's rep…").screenBackground()
            case .intro:
                if let rep = model.rep { DailyRepIntro(model: model, rep: rep) }
            case .conversation(let conversation):
                ConversationScreen(
                    conversation: conversation,
                    app: app,
                    progressLabel: "Today's rep",
                    finishTitle: "See my feedback",
                    endTitle: "Finish this rep",
                    onFinished: { _ in model.finished() },
                    onExit: { app.dismissFlow() }
                )
                .id(conversation.id)
            case .waiting:
                VStack(spacing: 18) {
                    Spacer()
                    VoiceOrb(level: 0.35).frame(width: 150, height: 150)
                    Text("Listening back to your rep…").font(.title3Rounded).foregroundStyle(Theme.ink)
                    Text("Checking it against today's target.").font(.subheadline).foregroundStyle(Theme.inkSecondary)
                    Spacer()
                }
                .frame(maxWidth: .infinity)
                .screenBackground()
            case .feedback:
                if let rep = model.rep { DailyRepFeedback(model: model, rep: rep) }
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

private struct DailyRepIntro: View {
    @Environment(AppModel.self) private var app
    let model: DailyRepModel
    let rep: DailyRep
    @State private var showExample = false

    private var color: Color { Theme.color(for: rep.dimension) }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                if app.isDemo { DemoBadge() }
                Spacer()
                CircleIconButton(systemName: "xmark") { app.dismissFlow() }
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.top, 10)
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    HStack(spacing: 8) {
                        Eyebrow(model.isToday ? "Today's rep · about \(rep.suggestedSeconds) sec"
                                : "Rep for \(DailyRepModel.displayDay(rep.date))", color: color)
                        Spacer()
                        DimensionTag(dimension: rep.dimension)
                    }
                    Text(rep.title).font(.display).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)

                    VStack(alignment: .leading, spacing: 10) {
                        Text(rep.prompt)
                            .font(.title3Rounded)
                            .foregroundStyle(Theme.ink)
                            .fixedSize(horizontal: false, vertical: true)
                        Button {
                            app.speech.speak(rep.prompt, languageCode: app.speechLanguage)
                        } label: {
                            Label("Hear it", systemImage: "speaker.wave.2.fill").font(.caption.weight(.semibold))
                        }
                        .foregroundStyle(color)
                    }
                    .card()

                    VStack(alignment: .leading, spacing: 6) {
                        Eyebrow("Your target", color: color)
                        Text(rep.targetBehavior).font(.headlineRounded).foregroundStyle(Theme.ink)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(18)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(color.opacity(0.1), in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))

                    if !rep.tips.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(rep.tips, id: \.self) { tip in
                                Label(tip, systemImage: "lightbulb").font(.subheadline).foregroundStyle(Theme.inkSecondary)
                            }
                        }
                    }

                    if let example = rep.example {
                        DisclosureGroup(isExpanded: $showExample) {
                            Text("“\(example)”")
                                .font(.body.italic())
                                .foregroundStyle(Theme.ink)
                                .padding(.top, 6)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        } label: {
                            Text("See an example").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.indigo)
                        }
                    }

                    if let attempt = rep.latestAttempt, attempt.feedback != nil {
                        Button {
                            model.showFeedback()
                        } label: {
                            Label("See feedback on your last try", systemImage: "text.badge.checkmark")
                                .font(.subheadline.weight(.semibold))
                        }
                        .foregroundStyle(Theme.indigo)
                    }

                    if let error = model.error {
                        InlineErrorBanner(message: error) { model.error = nil }
                    }
                }
                .padding(Theme.gutter)
            }
            VStack(spacing: 8) {
                if model.canPractise {
                    Button {
                        Task { await model.start() }
                    } label: {
                        Label(rep.attempts.isEmpty ? "I'm ready" : "Try it again", systemImage: "mic.fill")
                    }
                    .buttonStyle(.primaryPill)
                } else {
                    // An old reminder: that day's rep has closed, today's is waiting.
                    Button {
                        app.present(.daily(date: nil))
                    } label: {
                        Label("Go to today's rep", systemImage: "arrow.right.circle.fill")
                    }
                    .buttonStyle(.primaryPill)
                }
                if rep.canShuffle && rep.attempts.isEmpty {
                    Button {
                        Task { await model.shuffle() }
                    } label: {
                        if model.isShuffling { ProgressView() } else { Label("Different prompt", systemImage: "shuffle") }
                    }
                    .buttonStyle(.ghostPill)
                    .disabled(model.isShuffling)
                }
                Text("Take the time you need. Recording never stops on its own.")
                    .font(.caption)
                    .foregroundStyle(Theme.inkTertiary)
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.bottom, 12)
        }
        .screenBackground()
    }
}

private struct DailyRepFeedback: View {
    @Environment(AppModel.self) private var app
    let model: DailyRepModel
    let rep: DailyRep

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Eyebrow(rep.title, color: Theme.color(for: rep.dimension))
                Spacer()
                CircleIconButton(systemName: "xmark") { app.dismissFlow() }
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.top, 10)
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let attempt = rep.latestAttempt {
                        AttemptFeedbackContent(attempt: attempt, color: Theme.color(for: rep.dimension))
                    }
                    if rep.completed, let week = app.progress?.practice.thisWeek {
                        WeekProgressCard(week: week, weeksOnTarget: app.progress?.practice.weeksOnTarget ?? 0)
                    }
                }
                .padding(Theme.gutter)
            }
            VStack(spacing: 8) {
                if model.canPractise {
                    Button {
                        Task { await model.start() }
                    } label: {
                        Label("Try again with that change", systemImage: "arrow.counterclockwise")
                    }
                    .buttonStyle(.primaryPill)
                    Button("Done for today") { app.dismissFlow() }
                        .buttonStyle(.ghostPill)
                } else {
                    Button("Done") { app.dismissFlow() }
                        .buttonStyle(.primaryPill)
                }
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.bottom, 12)
        }
        .screenBackground()
    }
}

/// "3 of 3 this week" with the Monday–Sunday strip: the visible payoff of a finished rep.
struct WeekProgressCard: View {
    let week: WeekProgress
    let weeksOnTarget: Int

    private var message: String {
        if week.targetMet {
            return weeksOnTarget > 1 ? "Target reached — \(weeksOnTarget) weeks in a row." : "Target reached for this week."
        }
        let left = max(0, week.target - week.sessions)
        return "\(left) more to reach the target you set."
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("This week").font(.headlineRounded).foregroundStyle(Theme.ink)
                Spacer()
                Text("\(week.sessions) of \(week.target)").font(.metricSmall).foregroundStyle(Theme.indigo)
            }
            WeekStrip(days: week.days ?? [])
            Text(message).font(.footnote).foregroundStyle(Theme.inkSecondary)
        }
        .card()
    }
}

/// M T W T F S S, filled on days with practice.
struct WeekStrip: View {
    let days: [Int]
    var today: Int = HabitMath.weekday(Date(), timeZone: .current)

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(HabitMath.weekStrip(practicedDays: days, today: today).enumerated()), id: \.offset) { index, state in
                VStack(spacing: 6) {
                    ZStack {
                        Circle()
                            .fill(state == .practiced ? AnyShapeStyle(Theme.aurora) : AnyShapeStyle(Theme.surfaceMuted))
                        if state == .practiced {
                            Image(systemName: "checkmark").font(.caption.weight(.bold)).foregroundStyle(.white)
                        }
                        if state == .today {
                            Circle().strokeBorder(Theme.indigo, lineWidth: 2)
                        }
                    }
                    .frame(width: 30, height: 30)
                    Text(HabitMath.weekdayInitials[index])
                        .font(.caption2.weight(state == .today ? .bold : .medium))
                        .foregroundStyle(state == .today ? Theme.indigo : Theme.inkTertiary)
                }
                .frame(maxWidth: .infinity)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(HabitMath.weekdayShortNames[index]): \(state == .practiced ? "practised" : state == .today ? "today" : "no practice")")
            }
        }
    }
}
