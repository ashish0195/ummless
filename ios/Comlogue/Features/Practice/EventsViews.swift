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
                Eyebrow("\(event.kind.capitalized) · \(event.date)", color: Theme.coral)
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
    let onCreated: (UpcomingEvent) -> Void

    @State private var title = ""
    @State private var kind = "interview"
    @State private var date = Calendar.current.date(byAdding: .day, value: 3, to: Date()) ?? Date()
    @State private var notes = ""
    @State private var isSaving = false
    @State private var error: String?

    private struct EventKind: Identifiable {
        let id: String
        let title: String
        let symbol: String
    }

    private let kinds: [EventKind] = [
        EventKind(id: "interview", title: "Interview", symbol: "briefcase.fill"),
        EventKind(id: "meeting", title: "Meeting", symbol: "person.3.fill"),
        EventKind(id: "presentation", title: "Presentation", symbol: "rectangle.on.rectangle"),
        EventKind(id: "negotiation", title: "Negotiation", symbol: "hand.raised.fill"),
        EventKind(id: "social", title: "Social", symbol: "person.2.fill"),
        EventKind(id: "other", title: "Other", symbol: "sparkles"),
    ]

    var body: some View {
        NavigationStack {
            Form {
                Section("What's coming up?") {
                    TextField("e.g. Product manager interview at Acme", text: $title)
                    Picker("Type", selection: $kind) {
                        ForEach(kinds) { item in Label(item.title, systemImage: item.symbol).tag(item.id) }
                    }
                    DatePicker("Date", selection: $date, in: Date()..., displayedComponents: .date)
                }
                Section {
                    TextField("Who'll be there, what you want from it, what worries you…", text: $notes, axis: .vertical)
                        .lineLimit(3...8)
                } header: {
                    Text("Details (optional)")
                } footer: {
                    Text("The more you share, the more realistic your rehearsals. We emulate behaviour, never a real person's voice.")
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
    }

    private func save() async {
        isSaving = true
        defer { isSaving = false }
        do {
            let event = try await app.api.createEvent(CreateEventRequest(
                title: title, kind: kind, date: JSONCoding.dayString(date), notes: notes.isEmpty ? nil : notes
            ))
            onCreated(event)
            Haptics.success()
            dismiss()
        } catch {
            self.error = error.userMessage
        }
    }
}
