import SwiftUI

/// An upcoming real moment with AI-built rehearsals.
struct EventDetailView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let event: UpcomingEvent
    @State private var confirmDelete = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Eyebrow("\(EventFormatting.kindTitle(event.kind, meta: app.meta)) · \(EventFormatting.when(event))", color: Theme.coral)
                Text(event.title).font(.display).foregroundStyle(Theme.ink)
                if let notes = event.notes, !notes.isEmpty {
                    Text(notes).font(.body).foregroundStyle(Theme.inkSecondary)
                }
                SectionHeader("Rehearsals", subtitle: "Built for this moment. Start with any of them.")
                ForEach(event.prep) { item in
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Text(item.title).font(.headlineRounded).foregroundStyle(Theme.ink)
                            Spacer()
                            Tag(text: DifficultyCatalog.title(item.difficulty), color: Theme.coral)
                        }
                        Text(item.scenario).font(.subheadline).foregroundStyle(Theme.inkSecondary)
                        Text("Partner: \(item.partnerRole)").font(.caption).foregroundStyle(Theme.inkTertiary)
                        Button {
                            app.present(.spar(SparLaunch(title: item.title, personaId: nil, customScenario: item.scenario,
                                                         difficulty: item.difficulty, eventId: event.id, prepId: item.id)))
                        } label: {
                            Label("Rehearse", systemImage: "play.fill")
                        }
                        .buttonStyle(.secondaryPill)
                    }
                    .card()
                }
                Button("Remove event", role: .destructive) { confirmDelete = true }
                    .font(.footnote.weight(.semibold))
                    .frame(maxWidth: .infinity)
            }
            .padding(Theme.gutter)
        }
        .screenBackground()
        .navigationBarTitleDisplayMode(.inline)
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
                Text("The more you share, the more realistic your rehearsals. We emulate behaviour, never a real person's voice. We'll remind you the evening before and the morning of.")
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
