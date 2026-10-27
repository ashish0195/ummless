import SwiftUI

/// Free practice outside the course, kept to a few big choices — rehearse a conversation, group discussions and
/// panels, a real moment coming up, great speakers, a real conversation. Each opens its own simple screen.
@MainActor
struct PracticeHubView: View {
    @Environment(AppModel.self) private var app
    @State private var library = PracticeLibrary()

    /// Group discussions are an Indian placement staple; everyone gets panel interviews.
    private var panels: [Panel] { app.panels }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text("Practice").font(.displayLarge).foregroundStyle(Theme.ink)
                            Spacer()
                            if app.isDemo { DemoBadge() }
                        }
                        Text("Rehearse before the real thing.")
                            .font(.subheadline)
                            .foregroundStyle(Theme.inkSecondary)
                    }
                    .padding(.bottom, 12)
                    ForEach(routes, id: \.self) { route in
                        NavigationLink(value: route) { row(for: route) }
                            .buttonStyle(.pressableCard)
                    }
                }
                .padding(Theme.gutter)
            }
            .screenBackground()
            .navigationDestination(for: PracticeRoute.self) { route in
                destination(for: route)
            }
            .navigationDestination(for: SparSession.self) { session in
                SparReportView(conversationId: session.conversationId)
            }
            .navigationDestination(for: TalkSummary.self) { talk in
                TalkView(talkId: talk.id)
            }
            .navigationDestination(for: UpcomingEvent.self) { event in
                EventDetailView(event: event)
            }
            .task(id: app.dataVersion) { await library.load(app) }
            .refreshable { await library.load(app) }
        }
    }

    // MARK: Rows

    private var routes: [PracticeRoute] {
        var routes: [PracticeRoute] = [.rehearse]
        if !panels.isEmpty {
            // In India the GD round comes first: it's what most people here are practising for.
            if app.market == .in && panels.contains(where: \.isGroupDiscussion) {
                routes.insert(.groups, at: 0)
            } else {
                routes.append(.groups)
            }
        }
        return routes + [.comingUp, .talks, .realConversation]
    }

    private var groupsCopy: (title: String, row: String, screen: String) {
        let discussions = panels.contains(where: \.isGroupDiscussion)
        let interviews = panels.contains { !$0.isGroupDiscussion }
        if discussions {
            return ("Group discussions", interviews ? "GD rounds and panel interviews" : "Practise the GD round with AI voices",
                    "Several AI voices and you. Practise getting your point in.")
        }
        return ("Panel interviews", "Several interviewers, one of you", "Several interviewers, one of you.")
    }

    /// The next real moment, so the row says what's actually coming up.
    private var comingUpSubtitle: String {
        let today = HabitMath.dayString(Date(), timeZone: .current)
        if let next = app.events.filter({ $0.date >= today }).min(by: { ($0.date, $0.time ?? "") < ($1.date, $1.time ?? "") }) {
            return "\(next.title) · \(EventFormatting.when(next))"
        }
        return "An interview, a pitch or a hard talk"
    }

    private func row(for route: PracticeRoute) -> HubRow {
        switch route {
        case .rehearse:
            return HubRow(symbol: "bubble.left.and.bubble.right.fill", color: Theme.indigo,
                          title: "Rehearse a conversation", subtitle: "Practise with an AI partner first")
        case .groups:
            return HubRow(symbol: "person.3.fill", color: Theme.violet, title: groupsCopy.title, subtitle: groupsCopy.row)
        case .comingUp:
            return HubRow(symbol: "calendar", color: Theme.coral, title: "Get ready for a big moment", subtitle: comingUpSubtitle)
        case .talks:
            return HubRow(symbol: "quote.bubble.fill", color: Theme.amber,
                          title: "Learn from great speakers", subtitle: "Copy how they pace and pause")
        case .realConversation:
            return HubRow(symbol: "waveform", color: Theme.mint,
                          title: "Review a real conversation", subtitle: "Upload or record one for feedback")
        }
    }

    @ViewBuilder
    private func destination(for route: PracticeRoute) -> some View {
        switch route {
        case .rehearse:
            RehearseView(library: library)
        case .groups:
            GroupsListView(title: groupsCopy.title, subtitle: groupsCopy.screen)
        case .comingUp:
            ComingUpView()
        case .talks:
            TalksListView(library: library)
        case .realConversation:
            RealConversationView()
        }
    }
}

private enum PracticeRoute: Hashable {
    case rehearse, groups, comingUp, talks, realConversation
}

/// What the Practice screens show, loaded once by the tab and shared with the screens it opens.
@MainActor
@Observable
final class PracticeLibrary {
    var personas: [Persona] = []
    var sessions: [SparSession] = []
    var talks: [TalkSummary] = []
    var hasLoaded = false

    func load(_ app: AppModel) async {
        async let personasRequest = app.api.personas()
        async let sessionsRequest = app.api.sparSessions()
        async let talksRequest = app.api.talks()
        async let eventsTask: Void = app.refreshEvents()
        async let panelsTask: Void = app.refreshPanels()
        personas = (try? await personasRequest) ?? personas
        sessions = (try? await sessionsRequest) ?? sessions
        talks = (try? await talksRequest) ?? talks
        _ = await (eventsTask, panelsTask)
        hasLoaded = true
    }
}

// MARK: - Shared pieces

/// A big, calm row: an icon in a soft circle, a title, one short line, and a chevron (or a lock).
private struct HubRow: View {
    let symbol: String
    let color: Color
    let title: String
    var subtitle: String?
    var locked = false

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: symbol)
                .font(.headline)
                .foregroundStyle(color)
                .frame(width: 44, height: 44)
                .background(color.opacity(0.12), in: Circle())
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.headlineRounded)
                    .foregroundStyle(Theme.ink)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                if let subtitle {
                    Text(subtitle)
                        .font(.subheadline)
                        .foregroundStyle(Theme.inkSecondary)
                        .lineLimit(2)
                        .multilineTextAlignment(.leading)
                }
            }
            Spacer(minLength: 8)
            Image(systemName: locked ? "lock.fill" : "chevron.right")
                .font(.footnote.weight(.bold))
                .foregroundStyle(Theme.inkTertiary)
                .accessibilityLabel("Pro")
                .accessibilityHidden(!locked)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))
    }
}

/// The title block at the top of each Practice screen.
private struct ScreenTitle: View {
    let title: String
    let subtitle: String?

    init(_ title: String, subtitle: String? = nil) {
        self.title = title
        self.subtitle = subtitle
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.display)
                .foregroundStyle(Theme.ink)
                .fixedSize(horizontal: false, vertical: true)
            if let subtitle {
                Text(subtitle)
                    .font(.subheadline)
                    .foregroundStyle(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.bottom, 10)
    }
}

// MARK: - Rehearse a conversation

private enum SparSetup: Identifiable {
    case persona(Persona)
    case custom

    var id: String {
        switch self {
        case .persona(let persona): return persona.id
        case .custom: return "custom"
        }
    }
}

/// Who to rehearse with: an AI partner from the list, or a scenario described in your own words. How tough they
/// are is chosen on the next step, just before starting.
private struct RehearseView: View {
    @Environment(AppModel.self) private var app
    let library: PracticeLibrary
    @State private var setup: SparSetup?
    @State private var pendingLaunch: SparLaunch?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                ScreenTitle("Rehearse a conversation", subtitle: "Pick who you'll talk to. Stop whenever you like.")
                Button { setup = .custom } label: {
                    HubRow(symbol: "square.and.pencil", color: Theme.indigo, title: "Describe your own",
                           subtitle: "Any conversation on your mind")
                }
                .buttonStyle(.pressableCard)
                ForEach(library.personas) { persona in
                    Button { setup = .persona(persona) } label: {
                        HubRow(symbol: SymbolName.safe(persona.symbol), color: Color(hex: persona.colorHex),
                               title: persona.title, subtitle: persona.scenario, locked: !persona.isFree && !app.isPro)
                    }
                    .buttonStyle(.pressableCard)
                }
                if let activities = app.meta?.activities, !activities.isEmpty {
                    SectionHeader("Quick scenarios", subtitle: "They can add to your profile.")
                        .padding(.top, 16)
                    ForEach(activities) { activity in
                        Button { app.present(.gapFill(activityId: activity.id)) } label: {
                            HubRow(symbol: ActivityCatalog.symbol(activity.id), color: Theme.violet,
                                   title: activity.title, subtitle: activity.durationLabel)
                        }
                        .buttonStyle(.pressableCard)
                    }
                }
                if !library.sessions.isEmpty {
                    SectionHeader("Recent")
                        .padding(.top, 16)
                    ForEach(library.sessions.prefix(4)) { session in
                        NavigationLink(value: session) {
                            HubRow(symbol: "text.bubble.fill", color: Theme.indigo, title: session.title,
                                   subtitle: [session.outcomeLabel ?? session.personaName,
                                              Formatting.relative(session.createdAt)].joined(separator: " · "))
                        }
                        .buttonStyle(.pressableCard)
                    }
                }
                if !app.isPro, let limit = app.meta?.limits.freeSparPerWeek {
                    Text("Free plan: \(limit) rehearsal\(limit == 1 ? "" : "s") a week. Pro is unlimited.")
                        .font(.caption)
                        .foregroundStyle(Theme.inkTertiary)
                        .padding(.top, 8)
                }
            }
            .padding(Theme.gutter)
        }
        .screenBackground()
        .navigationBarTitleDisplayMode(.inline)
        .sheet(item: $setup, onDismiss: startPending) { setup in
            SparSetupSheet(setup: setup) { launch in
                pendingLaunch = launch
                self.setup = nil
            }
            .environment(app)
        }
    }

    /// The conversation opens once the sheet has gone: only one thing can be presented at a time.
    private func startPending() {
        guard let launch = pendingLaunch else { return }
        pendingLaunch = nil
        app.present(.spar(launch))
    }
}

/// The one step before a rehearsal: who it's with (or what it's about) and how tough they'll be.
private struct SparSetupSheet: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let setup: SparSetup
    let onStart: (SparLaunch) -> Void
    @State private var difficulty: Difficulty
    @State private var scenario = ""
    @FocusState private var scenarioFocused: Bool

    init(setup: SparSetup, onStart: @escaping (SparLaunch) -> Void) {
        self.setup = setup
        self.onStart = onStart
        if case .persona(let persona) = setup {
            _difficulty = State(initialValue: persona.defaultDifficulty)
        } else {
            _difficulty = State(initialValue: .real)
        }
    }

    private var trimmedScenario: String { scenario.trimmingCharacters(in: .whitespacesAndNewlines) }

    private var canStart: Bool {
        if case .custom = setup { return trimmedScenario.count >= 6 }
        return true
    }

    private var isLocked: Bool {
        if case .persona(let persona) = setup { return !persona.isFree && !app.isPro }
        return false
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack {
                    Spacer()
                    CircleIconButton(systemName: "xmark") { dismiss() }
                }
                setupContent
            }
            .padding(Theme.gutter)
        }
        .scrollBounceBehavior(.basedOnSize)
        .safeAreaInset(edge: .bottom) {
            VStack(spacing: 10) {
                if isLocked {
                    Label("Part of Pro", systemImage: "lock.fill")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(Theme.inkSecondary)
                }
                Button {
                    onStart(launch)
                } label: {
                    Label("Start", systemImage: "mic.fill")
                }
                .buttonStyle(.primaryPill)
                .disabled(!canStart)
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.top, 8)
            .padding(.bottom, 12)
            .background(Theme.background)
        }
        .screenBackground()
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .onAppear {
            if case .custom = setup { scenarioFocused = true }
        }
    }

    @ViewBuilder
    private var setupContent: some View {
        switch setup {
        case .persona(let persona):
            VStack(alignment: .leading, spacing: 8) {
                Text(persona.title).font(.display).foregroundStyle(Theme.ink)
                Text(persona.description)
                    .font(.body)
                    .foregroundStyle(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        case .custom:
            VStack(alignment: .leading, spacing: 10) {
                Text("What's the conversation?").font(.display).foregroundStyle(Theme.ink)
                TextField("e.g. Asking my landlord to fix the heating", text: $scenario, axis: .vertical)
                    .lineLimit(2...4)
                    .focused($scenarioFocused)
                    .padding(14)
                    .background(Theme.surface, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Theme.stroke))
                Text("We copy how people behave — never a real person's voice.")
                    .font(.caption)
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        VStack(alignment: .leading, spacing: 8) {
            Text("How tough?").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
            Picker("How tough?", selection: $difficulty) {
                ForEach(Difficulty.allCases) { level in Text(DifficultyCatalog.title(level)).tag(level) }
            }
            .pickerStyle(.segmented)
            Text(DifficultyCatalog.blurb(difficulty)).font(.footnote).foregroundStyle(Theme.inkSecondary)
        }
    }

    private var launch: SparLaunch {
        switch setup {
        case .persona(let persona):
            return SparLaunch(title: persona.title, personaId: persona.id, customScenario: nil,
                              difficulty: difficulty, eventId: nil, prepId: nil)
        case .custom:
            return SparLaunch(title: "Custom scenario", personaId: nil, customScenario: trimmedScenario,
                              difficulty: difficulty, eventId: nil, prepId: nil)
        }
    }
}

// MARK: - Group discussions and panels

private struct GroupsListView: View {
    @Environment(AppModel.self) private var app
    let title: String
    let subtitle: String

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                ScreenTitle(title, subtitle: subtitle)
                ForEach(app.panels) { panel in
                    Button { app.present(.group(panelId: panel.id)) } label: {
                        HubRow(symbol: SymbolName.safe(panel.symbol, fallback: "person.3.fill"), color: Color(hex: panel.colorHex),
                               title: panel.title, subtitle: "\(panel.minutes) min · with \(panel.participants.count) others",
                               locked: !panel.isFree && !app.isPro)
                    }
                    .buttonStyle(.pressableCard)
                }
            }
            .padding(Theme.gutter)
        }
        .screenBackground()
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await app.refreshPanels() }
    }
}

// MARK: - Coming up

/// Real moments the person has added (an interview, a pitch), with calendar suggestions when they've allowed it.
private struct ComingUpView: View {
    @Environment(AppModel.self) private var app
    @State private var showAddEvent = false
    @State private var eventPrefill: CalendarSuggestion?
    @State private var calendarSuggestions: [CalendarSuggestion] = []
    @State private var calendarConnected = CalendarScanner.isAuthorized

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                ScreenTitle("Get ready for a big moment", subtitle: "Add it, and rehearse before it happens.")
                if app.events.isEmpty {
                    VStack(alignment: .leading, spacing: 14) {
                        Image(systemName: "calendar.badge.plus").font(.title).foregroundStyle(Theme.coral)
                        Text("An interview, a pitch or a hard talk coming up? Add it and get three rehearsals made for it.")
                            .font(.body)
                            .foregroundStyle(Theme.ink)
                            .fixedSize(horizontal: false, vertical: true)
                        Button { showAddEvent = true } label: {
                            Label("Add what's coming up", systemImage: "plus")
                        }
                        .buttonStyle(.primaryPill)
                    }
                    .card()
                } else {
                    ForEach(app.events) { event in
                        NavigationLink(value: event) {
                            HubRow(symbol: symbol(for: event), color: Theme.coral, title: event.title, subtitle: subtitle(for: event))
                        }
                        .buttonStyle(.pressableCard)
                    }
                    Button { showAddEvent = true } label: {
                        Label("Add another", systemImage: "plus")
                    }
                    .buttonStyle(.secondaryPill)
                    .padding(.top, 4)
                }
                calendarSection
            }
            .padding(Theme.gutter)
        }
        .screenBackground()
        .navigationBarTitleDisplayMode(.inline)
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
        .task(id: app.dataVersion) {
            calendarConnected = CalendarScanner.isAuthorized
            refreshCalendar()
        }
        .refreshable {
            await app.refreshEvents()
            refreshCalendar()
        }
    }

    private func subtitle(for event: UpcomingEvent) -> String {
        if event.hasHappened(today: HabitMath.dayString(Date(), timeZone: .current)) && event.reflection == nil {
            return "How did it go?"
        }
        return EventFormatting.when(event)
    }

    private func symbol(for event: UpcomingEvent) -> String {
        let kinds = app.meta?.eventKinds ?? EventFormatting.fallbackKinds
        return SymbolName.safe(kinds.first { $0.id == event.kind }?.symbol ?? "calendar", fallback: "calendar")
    }

    @ViewBuilder
    private var calendarSection: some View {
        if calendarConnected {
            if !calendarSuggestions.isEmpty {
                VStack(alignment: .leading, spacing: 12) {
                    Text("From your calendar").font(.headlineRounded).foregroundStyle(Theme.ink)
                    ForEach(calendarSuggestions.prefix(3)) { suggestion in
                        HStack(spacing: 10) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(suggestion.title)
                                    .font(.subheadline.weight(.semibold))
                                    .foregroundStyle(Theme.ink)
                                    .lineLimit(1)
                                Text(suggestion.start.formatted(date: .abbreviated, time: suggestion.isAllDay ? .omitted : .shortened))
                                    .font(.caption)
                                    .foregroundStyle(Theme.inkSecondary)
                            }
                            Spacer()
                            Button("Add") {
                                eventPrefill = suggestion
                                showAddEvent = true
                            }
                            .buttonStyle(.pill(.secondary, fullWidth: false))
                        }
                    }
                    Text("Only what you add leaves your phone.").font(.caption2).foregroundStyle(Theme.inkTertiary)
                }
                .card()
                .padding(.top, 12)
            }
        } else if CalendarScanner.canAsk {
            Button {
                Task {
                    calendarConnected = await CalendarScanner.requestAccess()
                    refreshCalendar()
                }
            } label: {
                HubRow(symbol: "calendar.badge.checkmark", color: Theme.indigo, title: "Check my calendar",
                       subtitle: "Spot interviews and pitches. It stays on your phone.")
            }
            .buttonStyle(.pressableCard)
            .padding(.top, 12)
        }
    }

    private func refreshCalendar() {
        calendarSuggestions = CalendarScanner.suggestions(excluding: app.events)
    }
}

// MARK: - Great speakers

private struct TalksListView: View {
    @Environment(AppModel.self) private var app
    let library: PracticeLibrary

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                ScreenTitle("Learn from great speakers", subtitle: "See what makes them work, then say it their way.")
                if library.talks.isEmpty && !library.hasLoaded {
                    ProgressView().frame(maxWidth: .infinity).padding(.top, 40)
                }
                ForEach(library.talks) { talk in
                    NavigationLink(value: talk) {
                        HubRow(symbol: "quote.bubble.fill", color: Theme.amber, title: talk.title, subtitle: talk.speaker,
                               locked: !talk.isFree && !app.isPro)
                    }
                    .buttonStyle(.pressableCard)
                }
            }
            .padding(Theme.gutter)
        }
        .screenBackground()
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - A real conversation

private struct RealConversationView: View {
    @Environment(AppModel.self) private var app

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                ScreenTitle("Review a real conversation", subtitle: "A meeting, a call or a chat. See how you came across.")
                Button { app.present(.upload) } label: {
                    HubRow(symbol: "square.and.arrow.up", color: Theme.mint, title: "Upload a recording",
                           subtitle: "An audio file from your phone")
                }
                .buttonStyle(.pressableCard)
                Button { app.present(.liveRecording) } label: {
                    HubRow(symbol: "record.circle", color: Theme.coral, title: "Record a conversation",
                           subtitle: "Start when everyone's ready")
                }
                .buttonStyle(.pressableCard)
                Label("Everyone in the recording needs to agree to it.", systemImage: "hand.raised.fill")
                    .font(.footnote)
                    .foregroundStyle(Theme.inkSecondary)
                    .padding(.top, 6)
            }
            .padding(Theme.gutter)
        }
        .screenBackground()
        .navigationBarTitleDisplayMode(.inline)
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
                    progressLabel: "Rehearsal · \(DifficultyCatalog.title(launch.difficulty))",
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
    var title = "How it went"
    var againTitle = "Try again"
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
                Text("Notes from one practice. They don't change your profile.")
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
