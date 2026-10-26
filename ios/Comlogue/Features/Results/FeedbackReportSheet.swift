import SwiftUI

/// Lets people say a result or piece of feedback doesn't match their experience.
struct FeedbackReportSheet: View {
    enum Target {
        case dimension(DimensionId, sourceId: String?)
        case attempt(String)
        case sparReport(String)

        var type: String {
            switch self {
            case .dimension: return "dimension_result"
            case .attempt: return "attempt_feedback"
            case .sparReport: return "spar_report"
            }
        }

        var id: String {
            switch self {
            case .dimension(let dimension, let sourceId): return sourceId ?? "profile-\(dimension.rawValue)"
            case .attempt(let id): return id
            case .sparReport(let id): return id
            }
        }

        var dimension: DimensionId? {
            if case .dimension(let dimension, _) = self { return dimension }
            return nil
        }
    }

    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let target: Target

    @State private var reason = "inaccurate"
    @State private var note = ""
    @State private var isSending = false
    @State private var error: String?

    private let reasons: [(id: String, title: String)] = [
        ("inaccurate", "This doesn't match what I did"),
        ("misheard", "It misheard what I said"),
        ("wrong_speaker", "It used someone else's speech"),
        ("unfair", "It feels unfair to my style or culture"),
        ("other", "Something else"),
    ]

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Picker("What's off?", selection: $reason) {
                        ForEach(reasons, id: \.id) { item in Text(item.title).tag(item.id) }
                    }
                    .pickerStyle(.inline)
                    .labelsHidden()
                } header: {
                    Text("What's not quite right?")
                } footer: {
                    Text("We review these to calibrate Comlogue. Your result stays visible with its date and context.")
                }
                Section("Anything to add? (optional)") {
                    TextField("Tell us what happened", text: $note, axis: .vertical).lineLimit(2...6)
                }
                if let error {
                    Section { Text(error).foregroundStyle(Theme.danger) }
                }
            }
            .navigationTitle("Not quite right?")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await send() }
                    } label: {
                        if isSending { ProgressView() } else { Text("Send").bold() }
                    }
                    .disabled(isSending)
                }
            }
        }
        .presentationDetents([.medium, .large])
    }

    private func send() async {
        isSending = true
        defer { isSending = false }
        do {
            let response = try await app.api.reportFeedback(FeedbackReportRequest(
                targetType: target.type, targetId: target.id, dimension: target.dimension,
                reason: reason, note: note.isEmpty ? nil : note
            ))
            app.showToast(response.message)
            dismiss()
        } catch {
            self.error = error.userMessage
        }
    }
}

/// A small, unobtrusive entry point to the report sheet.
struct NotQuiteRightButton: View {
    @Environment(AppModel.self) private var app
    let target: FeedbackReportSheet.Target
    @State private var showSheet = false

    var body: some View {
        Button {
            showSheet = true
        } label: {
            Label("Not quite right?", systemImage: "hand.raised")
                .font(.caption.weight(.semibold))
        }
        .foregroundStyle(Theme.inkSecondary)
        .sheet(isPresented: $showSheet) {
            FeedbackReportSheet(target: target)
                .environment(app)
        }
    }
}
