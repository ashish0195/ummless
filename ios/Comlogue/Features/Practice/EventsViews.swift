import SwiftUI

/// An upcoming real moment with AI-built rehearsals.
struct EventDetailView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let event: UpcomingEvent
    @State private var confirmDelete = false
    @State private var showReflection = false
    @State private var reflection: Reflection?

    private var hasHappened: Bool { event.hasHappened(today: HabitMath.dayString(Date(), timeZone: .current)) }
    private var savedReflection: Reflection? { reflection ?? event.reflection }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(event.title).font(.display).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
                    Text("\(EventFormatting.kindTitle(event.kind, meta: app.meta)) · \(EventFormatting.when(event))")
                        .font(.subheadline)
                        .foregroundStyle(Theme.inkSecondary)
                }
                if let notes = event.notes, !notes.isEmpty {
                    Text(notes).font(.body).foregroundStyle(Theme.inkSecondary)
                }
                if hasHappened {
                    reflectionCard
                }
                SectionHeader("Rehearsals", subtitle: hasHappened ? "Run the tricky part again while it's fresh."
                                                                  : "Made for this moment. Start with any of them.")
                ForEach(event.prep) { item in
                    Button {
                        app.present(.spar(SparLaunch(title: item.title, personaId: nil, customScenario: item.scenario,
                                                     difficulty: item.difficulty, eventId: event.id, prepId: item.id)))
                    } label: {
                        RehearsalRow(item: item)
                    }
                    .buttonStyle(.pressableCard)
                }
                Button("Remove event", role: .destructive) { confirmDelete = true }
                    .font(.footnote.weight(.semibold))
                    .frame(maxWidth: .infinity)
            }
            .padding(Theme.gutter)
        }
        .screenBackground()
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $showReflection) {
            ReflectionSheet(questions: ["What did you say first?", "What would you change next time?"]) { text, went in
                do {
                    let updated = try await app.api.reflectOnEvent(event.id, text: text, went: went)
                    reflection = updated.reflection
                    await app.refreshEvents()
                    await app.refreshProgress()
                    app.dataVersion += 1
                    return updated.reflection
                } catch {
                    app.showToast(error.userMessage)
                    return nil
                }
            }
            .environment(app)
        }
        .confirmationDialog("Remove this event?", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("Remove", role: .destructive) {
                Task {
                    try? await app.api.deleteEvent(event.id)
                    await app.refreshEvents()
                    await app.rescheduleNotifications()
                    app.dataVersion += 1
                    dismiss()
                }
            }
        }
    }
}

extension EventDetailView {
    @ViewBuilder
    fileprivate var reflectionCard: some View {
        if let saved = savedReflection {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Eyebrow("Your reflection", color: Theme.violet)
                    Spacer()
                    if let went = saved.went { Tag(text: ReflectionSheet.label(for: went), color: Theme.violet) }
                }
                Text(saved.text).font(.subheadline).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
                if let reply = saved.coachReply {
                    Label(reply, systemImage: "sparkles").font(.subheadline).foregroundStyle(Theme.inkSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .card()
        } else {
            VStack(alignment: .leading, spacing: 10) {
                Text("How did it go?").font(.title3Rounded).foregroundStyle(Theme.ink)
                Text("Thirty seconds now makes the next one easier.")
                    .font(.subheadline).foregroundStyle(Theme.inkSecondary).fixedSize(horizontal: false, vertical: true)
                Button {
                    showReflection = true
                } label: {
                    Label("Reflect on it", systemImage: "bubble.left.and.text.bubble.right.fill")
                }
                .buttonStyle(.primaryPill)
            }
            .card()
        }
    }
}

struct AddEventSheet: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    var prefill: CalendarSuggestion?
    let onCreated: (UpcomingEvent) -> Void

    @State private var title = ""
    @State private var kind = "interview"
    @State private var date = Calendar.current.date(byAdding: .day, value: 3, to: Date()) ?? Date()
    @State private var knowsTime = false
    @State private var time = Calendar.current.date(bySettingHour: 10, minute: 0, second: 0, of: Date()) ?? Date()
    @State private var notes = ""
    @State private var isSaving = false
    @State private var error: String?
    @State private var showPriming = false
    @State private var applied = false

    /// Kinds offered in this market (a campus placement or GD only makes sense in India).
    private var kinds: [EventKindOption] {
        let all = app.meta?.eventKinds ?? EventFormatting.fallbackKinds
        let mine = all.filter { $0.markets.contains(app.market.rawValue) }
        return mine.isEmpty ? all : mine
    }

    var body: some View {
        NavigationStack {
            if showPriming {
                NotificationPrimingView(summary: "your plan") { dismiss() }
            } else {
                form
            }
        }
        .onAppear(perform: applyPrefill)
    }

    private var form: some View {
        Form {
            Section("What's coming up?") {
                TextField(app.market == .in ? "e.g. Final HR round at Zenith Systems" : "e.g. Product manager interview at Acme",
                          text: $title)
                Picker("Type", selection: $kind) {
                    ForEach(kinds) { item in Label(item.title, systemImage: SymbolName.safe(item.symbol, fallback: "calendar")).tag(item.id) }
                }
                DatePicker("Date", selection: $date, in: Calendar.current.startOfDay(for: Date())..., displayedComponents: .date)
                Toggle("I know the time", isOn: $knowsTime)
                if knowsTime {
                    DatePicker("Starts at", selection: $time, displayedComponents: .hourAndMinute)
                }
            }
            Section {
                TextField("Who'll be there, what you want from it, what worries you…", text: $notes, axis: .vertical)
                    .lineLimit(3...8)
            } header: {
                Text("Details (optional)")
            } footer: {
                Text("More detail makes the rehearsals more realistic. We copy how people behave, never their voice. We'll remind you the evening before and the morning of.")
            }
            if let error {
                Section { Text(error).foregroundStyle(Theme.danger) }
            }
        }
        .navigationTitle("Add an event")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarLeading) { Button("Cancel") { dismiss() } }
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    Task { await save() }
                } label: {
                    if isSaving { ProgressView() } else { Text("Add").bold() }
                }
                .disabled(title.trimmingCharacters(in: .whitespaces).count < 3 || isSaving)
            }
        }
    }

    private func applyPrefill() {
        guard !applied else { return }
        applied = true
        if !kinds.contains(where: { $0.id == kind }), let first = kinds.first { kind = first.id }
        guard let prefill else { return }
        title = prefill.title
        if kinds.contains(where: { $0.id == prefill.kind }) { kind = prefill.kind }
        date = prefill.start
        if !prefill.isAllDay {
            knowsTime = true
            time = prefill.start
        }
    }

    private func save() async {
        isSaving = true
        defer { isSaving = false }
        do {
            var request = CreateEventRequest(title: title, kind: kind, date: JSONCoding.dayString(date),
                                             notes: notes.isEmpty ? nil : notes)
            if knowsTime {
                let parts = Calendar.current.dateComponents([.hour, .minute], from: time)
                request.time = HabitMath.timeString(hour: parts.hour ?? 10, minute: parts.minute ?? 0)
            }
            let event = try await app.api.createEvent(request)
            onCreated(event)
            Haptics.success()
            await app.notifications.refreshStatus()
            if app.notifications.status == .notDetermined && !LocalFlags.notificationPrimingShown {
                showPriming = true
            } else {
                dismiss()
            }
        } catch {
            self.error = error.userMessage
        }
    }
}

/// One rehearsal for an event, started with a tap: what it's about, in a line or two.
private struct RehearsalRow: View {
    let item: PrepItem

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: "play.fill")
                .font(.subheadline.weight(.bold))
                .foregroundStyle(Theme.coral)
                .frame(width: 44, height: 44)
                .background(Theme.coral.opacity(0.12), in: Circle())
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(item.title)
                    .font(.headlineRounded)
                    .foregroundStyle(Theme.ink)
                    .multilineTextAlignment(.leading)
                Text(item.scenario)
                    .font(.subheadline)
                    .foregroundStyle(Theme.inkSecondary)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
            }
            Spacer(minLength: 8)
            Image(systemName: "chevron.right")
                .font(.footnote.weight(.bold))
                .foregroundStyle(Theme.inkTertiary)
                .accessibilityHidden(true)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))
        .accessibilityHint("Starts a rehearsal with \(item.partnerRole), \(DifficultyCatalog.title(item.difficulty).lowercased())")
    }
}

/// Opens an event from a notification or link.
struct EventLinkView: View {
    @Environment(AppModel.self) private var app
    let eventId: String
    @State private var missing = false

    var body: some View {
        Group {
            if let event = app.events.first(where: { $0.id == eventId }) {
                EventDetailView(event: event)
            } else if missing {
                EmptyStateView(systemImage: "calendar.badge.exclamationmark", title: "Event not found",
                               message: "It may have been removed.")
            } else {
                LoadingStateView()
            }
        }
        .screenBackground()
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                CircleIconButton(systemName: "xmark") { app.dismissFlow() }
            }
        }
        .task {
            if !app.events.contains(where: { $0.id == eventId }) {
                await app.refreshEvents()
                missing = !app.events.contains(where: { $0.id == eventId })
            }
        }
    }
}

enum EventFormatting {
    static let fallbackKinds: [EventKindOption] = [
        EventKindOption(id: "interview", title: "Job interview", symbol: "person.crop.rectangle", markets: ["us", "in", "global"]),
        EventKindOption(id: "meeting", title: "Meeting", symbol: "person.3.fill", markets: ["us", "in", "global"]),
        EventKindOption(id: "presentation", title: "Presentation", symbol: "rectangle.on.rectangle", markets: ["us", "in", "global"]),
        EventKindOption(id: "negotiation", title: "Negotiation", symbol: "hand.raised.fill", markets: ["us", "in", "global"]),
        EventKindOption(id: "social", title: "Social", symbol: "person.2.fill", markets: ["us", "in", "global"]),
        EventKindOption(id: "other", title: "Other", symbol: "sparkles", markets: ["us", "in", "global"]),
    ]

    static func kindTitle(_ kind: String, meta: Meta?) -> String {
        (meta?.eventKinds ?? fallbackKinds).first { $0.id == kind }?.title ?? kind.replacingOccurrences(of: "_", with: " ").capitalized
    }

    /// "Thu, 29 Oct · 11:00 AM" in the person's locale.
    static func when(_ event: UpcomingEvent) -> String {
        guard let day = HabitMath.date(fromDay: event.date, timeZone: .current) else { return event.date }
        var text = day.formatted(.dateTime.weekday(.abbreviated).day().month(.abbreviated))
        if let time = HabitMath.parseTime(event.time),
           let moment = Calendar.current.date(bySettingHour: time.hour, minute: time.minute, second: 0, of: day) {
            text += " · " + moment.formatted(date: .omitted, time: .shortened)
        }
        return text
    }
}
