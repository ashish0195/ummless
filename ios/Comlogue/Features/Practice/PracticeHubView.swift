import SwiftUI

/// Free practice outside the course: spar with AI personas, shadow great talks, rehearse upcoming events,
/// run a short scenario, or add a real conversation.
struct PracticeHubView: View {
    @Environment(AppModel.self) private var app
    @State private var personas: [Persona] = []
    @State private var sessions: [SparSession] = []
    @State private var talks: [TalkSummary] = []
    @State private var difficulty: Difficulty = .real
    @State private var customScenario = ""
    @State private var showAddEvent = false
    @State private var eventPrefill: CalendarSuggestion?
    @State private var calendarSuggestions: [CalendarSuggestion] = []
    @State private var calendarConnected = CalendarScanner.isAuthorized

    private var events: [UpcomingEvent] { app.events }
    /// Group discussions are an Indian placement staple; everyone gets panel interviews.
    private var panels: [Panel] { app.panels }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    HStack {
                        Text("Practice").font(.displayLarge).foregroundStyle(Theme.ink)
                        Spacer()
                        if app.isDemo { DemoBadge() }
                    }
                    sparSection
                    if !panels.isEmpty { groupSection }
                    if !sessions.isEmpty { recentSpars }
                    talksSection
                    eventsSection
                    scenariosSection
                    addConversationSection
                }
                .padding(Theme.gutter)
            }
            .screenBackground()
            .navigationDestination(for: SparSession.self) { session in
                SparReportView(conversationId: session.conversationId)
            }
            .navigationDestination(for: TalkSummary.self) { talk in
                TalkView(talkId: talk.id)
            }
            .navigationDestination(for: UpcomingEvent.self) { event in
                EventDetailView(event: event)
            }
            .sheet(isPresented: $showAddEvent) {
                AddEventSheet(prefill: eventPrefill) { _ in
                    Task {
                        await app.refreshEvents()
                        await app.rescheduleNotifications()
                        refreshCalendar()
                    }
                }
                .environment(app)
            }
            .onChange(of: showAddEvent) { _, isShowing in
                if !isShowing { eventPrefill = nil }
            }
            .task(id: app.dataVersion) { await load() }
            .refreshable { await load() }
        }
    }

    // MARK: Spar

    private var sparSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader("Spar with an AI", subtitle: "Rehearse a hard conversation before it's real.")
            LazyVGrid(columns: [GridItem(.flexible(), spacing: 12, alignment: .top),
                                GridItem(.flexible(), spacing: 12, alignment: .top)], spacing: 12) {
                ForEach(personas) { persona in
                    Button {
                        start(SparLaunch(title: persona.title, personaId: persona.id, customScenario: nil,
                                         difficulty: difficulty, eventId: nil, prepId: nil))
                    } label: {
                        PersonaCard(persona: persona, locked: !persona.isFree && !app.isPro)
                    }
                    .buttonStyle(.pressableCard)
                }
            }
            VStack(alignment: .leading, spacing: 10) {
                Text("Or describe any scenario").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                HStack(spacing: 10) {
                    TextField("e.g. Asking my landlord to fix the heating", text: $customScenario, axis: .vertical)
                        .lineLimit(1...3)
                        .padding(12)
                        .background(Theme.surface, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Theme.stroke))
                    Button {
                        start(SparLaunch(title: "Custom scenario", personaId: nil, customScenario: customScenario,
                                         difficulty: difficulty, eventId: nil, prepId: nil))
                        customScenario = ""
                    } label: {
                        Image(systemName: "arrow.up").font(.headline).foregroundStyle(.white)
                            .frame(width: 44, height: 44).background(Theme.aurora, in: Circle())
                    }
                    .disabled(customScenario.trimmingCharacters(in: .whitespacesAndNewlines).count < 6)
                    .opacity(customScenario.trimmingCharacters(in: .whitespacesAndNewlines).count < 6 ? 0.4 : 1)
                }
                Text("We emulate how someone behaves — never a real person's voice.").font(.caption).foregroundStyle(Theme.inkTertiary)
            }
            VStack(alignment: .leading, spacing: 8) {
                Text("Difficulty").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                Picker("Difficulty", selection: $difficulty) {
                    ForEach(Difficulty.allCases) { level in Text(DifficultyCatalog.title(level)).tag(level) }
                }
                .pickerStyle(.segmented)
                Text(DifficultyCatalog.blurb(difficulty)).font(.caption).foregroundStyle(Theme.inkSecondary)
            }
            if !app.isPro, let limit = app.meta?.limits.freeSparPerWeek {
                Text("Free plan: \(limit) spar\(limit == 1 ? "" : "s") a week. Pro is unlimited.")
                    .font(.caption)
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
    }

    // MARK: Groups

    private var groupSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(panels.contains { $0.isGroupDiscussion } ? "Group discussions & panels" : "Panel interviews",
                          subtitle: panels.contains { $0.isGroupDiscussion }
                              ? "Practise the GD round and multi-person interviews with several AI voices."
                              : "Several interviewers, one candidate: you.")
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(panels) { panel in
                        Button {
                            app.present(.group(panelId: panel.id))
                        } label: {
                            PanelCard(panel: panel, locked: !panel.isFree && !app.isPro)
                        }
                        .buttonStyle(.pressableCard)
                    }
                }
                .padding(.vertical, 4)
            }
        }
    }

    private var recentSpars: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader("Recent spars")
            ForEach(sessions.prefix(4)) { session in
                NavigationLink(value: session) {
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(session.title).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                            Text("\(session.personaName) · \(DifficultyCatalog.title(session.difficulty)) · \(Formatting.relative(session.createdAt))")
                                .font(.caption)
                                .foregroundStyle(Theme.inkSecondary)
                        }
                        Spacer()
                        if let outcome = session.outcomeLabel { Tag(text: outcome, color: Theme.indigo) }
                        Image(systemName: "chevron.right").font(.caption.weight(.bold)).foregroundStyle(Theme.inkTertiary)
                    }
                    .card(padding: 14)
                }
                .buttonStyle(.pressableCard)
            }
        }
    }

    // MARK: Talks

    private var talksSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader("Steal their style", subtitle: "Shadow great speakers line by line.")
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(talks) { talk in
                        NavigationLink(value: talk) {
                            TalkCard(talk: talk, locked: !talk.isFree && !app.isPro)
                        }
                        .buttonStyle(.pressableCard)
                    }
                }
                .padding(.vertical, 4)
            }
        }
    }

    // MARK: Events

    private var eventsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader("Coming up", subtitle: "Add a real moment and rehearse for it.",
                          trailing: AnyView(Button { showAddEvent = true } label: { Image(systemName: "plus.circle.fill").font(.title2) }))
            calendarCard
            if events.isEmpty {
                Button { showAddEvent = true } label: {
                    HStack(spacing: 12) {
                        Image(systemName: "calendar.badge.plus").font(.title2).foregroundStyle(Theme.coral)
                        Text("Interview, pitch, hard talk or first date? Add it and get three tailored rehearsals.")
                            .font(.subheadline)
                            .foregroundStyle(Theme.ink)
                            .multilineTextAlignment(.leading)
                    }
                    .card()
                }
                .buttonStyle(.pressableCard)
            } else {
                ForEach(events) { event in
                    NavigationLink(value: event) {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(event.title).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                                Text("\(EventFormatting.when(event)) · \(event.prep.count) rehearsals").font(.caption).foregroundStyle(Theme.inkSecondary)
                            }
                            Spacer()
                            if event.hasHappened(today: HabitMath.dayString(Date(), timeZone: .current)) && event.reflection == nil {
                                Tag(text: "How did it go?", color: Theme.violet)
                            }
                            Image(systemName: "chevron.right").font(.caption.weight(.bold)).foregroundStyle(Theme.inkTertiary)
                        }
                        .card(padding: 14)
                    }
                    .buttonStyle(.pressableCard)
                }
            }
        }
    }

    @ViewBuilder
    private var calendarCard: some View {
        if calendarConnected {
            if !calendarSuggestions.isEmpty {
                VStack(alignment: .leading, spacing: 10) {
                    Label("From your calendar", systemImage: "calendar").font(.subheadline.weight(.semibold))
                        .foregroundStyle(Theme.ink)
                    ForEach(calendarSuggestions.prefix(3)) { suggestion in
                        HStack(spacing: 10) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(suggestion.title).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink).lineLimit(1)
                                Text(suggestion.start.formatted(date: .abbreviated, time: suggestion.isAllDay ? .omitted : .shortened))
                                    .font(.caption).foregroundStyle(Theme.inkSecondary)
                            }
                            Spacer()
                            Button("Prep") {
                                eventPrefill = suggestion
                                showAddEvent = true
                            }
                            .buttonStyle(.pill(.secondary, fullWidth: false))
                        }
                    }
                    Text("Only what you choose to prep for leaves your phone.").font(.caption2).foregroundStyle(Theme.inkTertiary)
                }
                .card()
            }
        } else if CalendarScanner.canAsk {
            Button {
                Task {
                    calendarConnected = await CalendarScanner.requestAccess()
                    refreshCalendar()
                }
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: "calendar.badge.checkmark").font(.title2).foregroundStyle(Theme.indigo)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Find big moments in your calendar").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                        Text("Interviews, pitches, reviews and client calls, spotted on your phone so you can warm up.")
                            .font(.caption).foregroundStyle(Theme.inkSecondary).multilineTextAlignment(.leading)
                    }
                    Spacer(minLength: 0)
                }
                .card()
            }
            .buttonStyle(.pressableCard)
        }
    }

    private func refreshCalendar() {
        calendarSuggestions = CalendarScanner.suggestions(excluding: app.events)
    }

    // MARK: Scenarios & conversations

    private var scenariosSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader("Short scenarios", subtitle: "2–3 minutes each. They can update your profile when there's enough evidence.")
            ForEach(app.meta?.activities ?? []) { activity in
                Button {
                    app.present(.gapFill(activityId: activity.id))
                } label: {
                    HStack(spacing: 12) {
                        Image(systemName: ActivityCatalog.symbol(activity.id))
                            .foregroundStyle(Theme.indigo)
                            .frame(width: 36, height: 36)
                            .background(Theme.indigo.opacity(0.1), in: Circle())
                        VStack(alignment: .leading, spacing: 2) {
                            Text(activity.title).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                            Text(activity.dimensions.map(DimensionCatalog.title).joined(separator: " · "))
                                .font(.caption)
                                .foregroundStyle(Theme.inkSecondary)
                        }
                        Spacer()
                        Text(activity.durationLabel).font(.caption.weight(.semibold)).foregroundStyle(Theme.inkSecondary)
                    }
                    .card(padding: 14)
                }
                .buttonStyle(.pressableCard)
            }
        }
    }

    private var addConversationSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader("Add a real conversation")
            HStack(spacing: 12) {
                Button { app.present(.upload) } label: {
                    Label("Upload", systemImage: "square.and.arrow.up").frame(maxWidth: .infinity)
                }
                .buttonStyle(.pill(.secondary))
                Button { app.present(.liveRecording) } label: {
                    Label("Record", systemImage: "record.circle").frame(maxWidth: .infinity)
                }
                .buttonStyle(.pill(.secondary))
            }
        }
    }

    // MARK: Actions

    private func start(_ launch: SparLaunch) {
        app.present(.spar(launch))
    }

    private func load() async {
        async let personasRequest = app.api.personas()
        async let sessionsRequest = app.api.sparSessions()
        async let talksRequest = app.api.talks()
        async let eventsTask: Void = app.refreshEvents()
        async let panelsTask: Void = app.refreshPanels()
        personas = (try? await personasRequest) ?? personas
        sessions = (try? await sessionsRequest) ?? sessions
        talks = (try? await talksRequest) ?? talks
        _ = await (eventsTask, panelsTask)
        calendarConnected = CalendarScanner.isAuthorized
        refreshCalendar()
    }
}

private struct PersonaCard: View {
    let persona: Persona
    let locked: Bool

    var body: some View {
        let color = Color(hex: persona.colorHex)
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Image(systemName: SymbolName.safe(persona.symbol))
                    .font(.headline)
                    .foregroundStyle(.white)
                    .frame(width: 40, height: 40)
                    .background(color, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                Spacer()
                if locked { Image(systemName: "lock.fill").font(.caption).foregroundStyle(Theme.inkTertiary) }
            }
            Text(persona.title).font(.headlineRounded).foregroundStyle(Theme.ink).lineLimit(2).multilineTextAlignment(.leading)
            Text(persona.scenario).font(.caption).foregroundStyle(Theme.inkSecondary).lineLimit(2).multilineTextAlignment(.leading)
            Spacer(minLength: 0)
            Tag(text: DifficultyCatalog.title(persona.defaultDifficulty).uppercased(), color: color)
        }
        // Cards in a row share the tallest one's height, with their tags lined up along the bottom.
        .frame(maxWidth: .infinity, minHeight: 150, maxHeight: .infinity, alignment: .topLeading)
        .card(padding: 14)
    }
}

private struct TalkCard: View {
    let talk: TalkSummary
    let locked: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "quote.bubble.fill").foregroundStyle(.white)
                Spacer()
                if locked { Image(systemName: "lock.fill").foregroundStyle(.white.opacity(0.85)) }
            }
            Spacer()
            Text(talk.title).font(.headlineRounded).foregroundStyle(.white).lineLimit(3).multilineTextAlignment(.leading)
            Text(talk.speaker).font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.85))
            Text("\(Int(talk.style.wpm)) wpm · \(Formatting.oneDecimal(talk.style.avgPauseSeconds))s pauses")
                .font(.caption2)
                .foregroundStyle(.white.opacity(0.75))
        }
        .padding(16)
        .frame(width: 210, height: 180, alignment: .topLeading)
        .background(
            LinearGradient(colors: [Color(rgb: 0x2A2470), Theme.violet], startPoint: .topLeading, endPoint: .bottomTrailing),
            in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous)
        )
    }
}

// MARK: - Spar flow

struct SparFlowView: View {
    private enum Stage: Equatable {
        case starting, conversation(Conversation), report(String), failed(String), paywall
    }

    @Environment(AppModel.self) private var app
    let launch: SparLaunch
    @State private var stage: Stage = .starting

    var body: some View {
        Group {
            switch stage {
            case .starting:
                LoadingStateView(title: "Setting the scene…").screenBackground()
            case .conversation(let conversation):
                ConversationScreen(
                    conversation: conversation,
                    app: app,
                    progressLabel: "Spar · \(DifficultyCatalog.title(launch.difficulty))",
                    finishTitle: "Get my report",
                    endTitle: "End & get report",
                    onFinished: { result in
                        stage = .report(result?.resultRef?.id ?? conversation.id)
                    },
                    onExit: { app.dismissFlow() }
                )
            case .report(let conversationId):
                NavigationStack {
                    SparReportView(conversationId: conversationId, isRoot: true, onAgain: {
                        stage = .starting
                        Task { await start() }
                    })
                }
            case .paywall:
                PaywallView { app.dismissFlow() }
            case .failed(let message):
                VStack {
                    HStack { Spacer(); CircleIconButton(systemName: "xmark") { app.dismissFlow() } }.padding(Theme.gutter)
                    ErrorStateView(message: message) { Task { await start() } }
                }
                .screenBackground()
            }
        }
        .task { if stage == .starting { await start() } }
    }

    private func start() async {
        do {
            let conversation = try await app.api.createConversation(CreateConversationRequest(
                kind: "spar", missionId: nil, quick: nil, personaId: launch.personaId,
                customScenario: launch.customScenario, difficulty: launch.difficulty,
                eventId: launch.eventId, prepId: launch.prepId
            ))
            stage = .conversation(conversation)
        } catch let error as APIError where error.isSubscriptionRequired {
            stage = .paywall
        } catch {
            stage = .failed(error.userMessage)
        }
    }
}

struct SparReportView: View {
    @Environment(AppModel.self) private var app
    let conversationId: String
    var isRoot: Bool = false
    var onAgain: (() -> Void)?
    var title = "Spar report"
    var againTitle = "Spar again"
    @State private var report: SparReport?
    @State private var error: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                if let report, !report.isProcessing {
                    reportContent(report)
                } else if let error {
                    ErrorStateView(message: error) { Task { await load() } }
                } else {
                    LoadingStateView(title: "Writing your report…", subtitle: "Finding the moments that mattered.")
                        .frame(minHeight: 400)
                }
            }
            .padding(Theme.gutter)
        }
        .screenBackground()
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if isRoot {
                ToolbarItem(placement: .topBarTrailing) { CircleIconButton(systemName: "xmark") { app.dismissFlow() } }
            }
        }
        .task { await load() }
    }

    @ViewBuilder
    private func reportContent(_ report: SparReport) -> some View {
        Eyebrow("Session report", color: Theme.indigo)
        Text(report.title).font(.display).foregroundStyle(Theme.ink)
        if let outcome = report.outcome {
            VStack(alignment: .leading, spacing: 6) {
                Text(outcome.label).font(.titleRounded).foregroundStyle(.white)
                Text(outcome.detail).font(.subheadline).foregroundStyle(.white.opacity(0.9))
            }
            .padding(18)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.aurora, in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))
        }
        if !report.momentum.isEmpty {
            MomentumChart(points: report.momentum)
        }
        if !report.moments.isEmpty {
            SectionHeader("Rewrite these moments")
            ForEach(Array(report.moments.enumerated()), id: \.offset) { _, moment in
                RewriteMomentCard(moment: moment, title: "Rewrite this moment")
            }
        }
        if !report.observations.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                Eyebrow("What we noticed")
                ForEach(Array(report.observations.enumerated()), id: \.offset) { _, observation in
                    HStack(alignment: .top, spacing: 10) {
                        DimensionTag(dimension: observation.dimension, compact: true)
                        Text(observation.note).font(.subheadline).foregroundStyle(Theme.ink)
                    }
                }
                Text("Observations from one practice conversation. Your profile only changes from assessments and recordings.")
                    .font(.caption)
                    .foregroundStyle(Theme.inkTertiary)
            }
            .card()
        }
        if let next = report.nextStep {
            Label(next, systemImage: "arrow.turn.down.right").font(.subheadline).foregroundStyle(Theme.ink).card()
        }
        NotQuiteRightButton(target: .sparReport(report.conversationId))
        if let onAgain {
            Button(againTitle, action: onAgain).buttonStyle(.primaryPill)
        }
    }

    private func load() async {
        for _ in 0..<60 {
            do {
                let latest = try await app.api.sparReport(conversationId: conversationId)
                report = latest
                error = nil
                if !latest.isProcessing { return }
            } catch {
                self.error = error.userMessage
                return
            }
            try? await Task.sleep(nanoseconds: 2_000_000_000)
        }
    }
}

/// How the conversation was going for the other person over time — a story of the exchange, not a score.
struct MomentumChart: View {
    let points: [MomentumPoint]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Eyebrow("How it was going for them")
            HStack(alignment: .bottom, spacing: 6) {
                ForEach(points) { point in
                    RoundedRectangle(cornerRadius: 5, style: .continuous)
                        .fill(point.value >= 0.5 ? AnyShapeStyle(Theme.aurora) : AnyShapeStyle(Theme.coral.opacity(0.85)))
                        .frame(height: max(10, 90 * point.value))
                        .frame(maxWidth: .infinity)
                }
            }
            .frame(height: 92, alignment: .bottom)
            if let turning = points.first(where: { $0.note != nil })?.note {
                Text(turning).font(.footnote).foregroundStyle(Theme.inkSecondary)
            }
        }
        .card()
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Momentum across \(points.count) turns")
    }
}
