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
            self?.stage = .failed("Feedback is taking longer than usual. Your recording is saved — check back in a minute.")
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
                LoadingStateView(title: "Getting today's practice…").screenBackground()
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
                LoadingStateView(title: "Getting today's practice…").screenBackground()
            case .intro:
                if let rep = model.rep { DailyRepIntro(model: model, rep: rep) }
            case .conversation(let conversation):
                ConversationScreen(
                    conversation: conversation,
                    app: app,
                    progressLabel: "Today's practice",
                    finishTitle: "See my feedback",
                    endTitle: "Finish",
                    onFinished: { _ in model.finished() },
                    onExit: { app.dismissFlow() }
                )
                .id(conversation.id)
            case .waiting:
                VStack(spacing: 18) {
                    Spacer()
                    VoiceOrb(level: 0.35).frame(width: 150, height: 150)
                    Text("Listening back…").font(.title3Rounded).foregroundStyle(Theme.ink)
                    Text("Checking it against what you tried.").font(.subheadline).foregroundStyle(Theme.inkSecondary)
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
                Text(model.isToday ? "Today's practice" : DailyRepModel.displayDay(rep.date))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Theme.inkSecondary)
                Spacer()
                CircleIconButton(systemName: "xmark") { app.dismissFlow() }
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.top, 10)
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Text(rep.title).font(.display).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
                    Text(rep.prompt)
                        .font(.title3)
                        .foregroundStyle(Theme.ink)
                        .fixedSize(horizontal: false, vertical: true)
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Try this").font(.subheadline.weight(.semibold)).foregroundStyle(color)
                        Text(rep.targetBehavior).font(.headlineRounded).foregroundStyle(Theme.ink)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(18)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(color.opacity(0.1), in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))
                    if let example = rep.example {
                        Button(showExample ? "Hide the example" : "See an example") { withAnimation { showExample.toggle() } }
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(Theme.indigo)
                        if showExample {
                            Text("“\(example)”").font(.body.italic()).foregroundStyle(Theme.inkSecondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    if let attempt = rep.latestAttempt, attempt.feedback != nil {
                        Button("See feedback on your last try") { model.showFeedback() }
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(Theme.indigo)
                    }
                    if let error = model.error {
                        InlineErrorBanner(message: error) { model.error = nil }
                    }
                }
                .padding(.horizontal, Theme.gutter)
                .padding(.vertical, 20)
            }
            VStack(spacing: 6) {
                if model.canPractise {
                    Button {
                        Task { await model.start() }
                    } label: {
                        Label(rep.attempts.isEmpty ? "Start" : "Try again", systemImage: "mic.fill")
                    }
                    .buttonStyle(.primaryPill)
                } else {
                    // An old reminder: that day's practice has closed, today's is waiting.
                    Button {
                        app.present(.daily(date: nil))
                    } label: {
                        Label("Go to today's practice", systemImage: "arrow.right.circle.fill")
                    }
                    .buttonStyle(.primaryPill)
                }
                if rep.canShuffle && rep.attempts.isEmpty {
                    Button {
                        Task { await model.shuffle() }
                    } label: {
                        if model.isShuffling { ProgressView() } else { Text("Different prompt") }
                    }
                    .buttonStyle(.ghostPill)
                    .disabled(model.isShuffling)
                }
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
                Spacer()
                CircleIconButton(systemName: "xmark") { app.dismissFlow() }
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.top, 10)
            ScrollView {
                if let attempt = rep.latestAttempt {
                    AttemptFeedbackContent(attempt: attempt, color: Theme.color(for: rep.dimension))
                        .padding(.horizontal, Theme.gutter)
                        .padding(.vertical, 12)
                }
            }
            VStack(spacing: 6) {
                if model.canPractise {
                    Button {
                        Task { await model.start() }
                    } label: {
                        Label("Try again", systemImage: "arrow.counterclockwise")
                    }
                    .buttonStyle(.primaryPill)
                    Button("Done") { app.dismissFlow() }
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
