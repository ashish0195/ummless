import SwiftUI

/// Feedback tied to one attempt: whether it could be assessed, whether the target appeared and where,
/// one change, and a comparison with the previous attempt on the same target.
struct AttemptFeedbackView: View {
    @Environment(\.dismiss) private var dismiss
    let attempt: MissionAttempt
    let mission: Mission
    let onRetry: () -> Void
    let onFinish: () -> Void

    private var color: Color { Theme.color(for: mission.dimension) }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let feedback = attempt.feedback {
                        HStack {
                            Eyebrow("Attempt #\(attempt.attemptNumber)", color: color)
                            Spacer()
                            TargetMetBadge(targetMet: feedback.targetMet, assessable: feedback.assessable)
                        }
                        Text(feedback.headline).font(.display).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)

                        if feedback.assessable == .no {
                            Text("We couldn't assess this attempt, so there's no judgement here — just what got in the way.")
                                .font(.subheadline)
                                .foregroundStyle(Theme.inkSecondary)
                            if !feedback.issues.isEmpty { IssueCard(issues: feedback.issues) }
                        } else {
                            if let moment = feedback.where {
                                VStack(alignment: .leading, spacing: 8) {
                                    Eyebrow("Where it showed up", color: color)
                                    EvidenceMomentRow(moment: moment, tint: color)
                                }
                                .card()
                            }
                            if !feedback.whatWorked.isEmpty {
                                VStack(alignment: .leading, spacing: 8) {
                                    Eyebrow("What worked", color: Theme.mint)
                                    ForEach(feedback.whatWorked, id: \.self) { item in
                                        Label(item, systemImage: "checkmark").font(.subheadline).foregroundStyle(Theme.ink)
                                    }
                                }
                                .card()
                            }
                            if let change = feedback.oneChange {
                                VStack(alignment: .leading, spacing: 6) {
                                    Eyebrow("One change for next time", color: .white.opacity(0.85))
                                    Text(change).font(.title3Rounded).foregroundStyle(.white).fixedSize(horizontal: false, vertical: true)
                                }
                                .padding(18)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(Theme.aurora, in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))
                            }
                            if let missing = feedback.missingEvidence {
                                Label(missing, systemImage: "info.circle")
                                    .font(.footnote)
                                    .foregroundStyle(Theme.inkSecondary)
                            }
                        }

                        NotQuiteRightButton(target: .attempt(attempt.id))

                        if let comparison = feedback.comparison {
                            VStack(alignment: .leading, spacing: 8) {
                                Eyebrow("Compared with your last attempt", color: Theme.violet)
                                Text(comparison.summary).font(.subheadline).foregroundStyle(Theme.ink)
                                ForEach(comparison.changes, id: \.self) { change in
                                    Label(change, systemImage: "arrow.left.arrow.right").font(.footnote).foregroundStyle(Theme.ink)
                                }
                                Text(comparison.note).font(.caption).foregroundStyle(Theme.inkTertiary)
                            }
                            .card()
                        }
                    } else {
                        LoadingStateView(title: "Feedback on the way…")
                    }
                }
                .padding(Theme.gutter)
            }
            .screenBackground()
            .safeAreaInset(edge: .bottom) {
                VStack(spacing: 8) {
                    Button("Try again with this change", action: onRetry).buttonStyle(.primaryPill)
                    Button("Save takeaway & finish", action: onFinish).buttonStyle(.ghostPill)
                }
                .padding(.horizontal, Theme.gutter)
                .padding(.vertical, 10)
                .background(Theme.background)
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) { Button("Close") { dismiss() } }
            }
        }
    }
}

struct CompleteMissionSheet: View {
    @Environment(\.dismiss) private var dismiss
    let suggestion: String?
    let onSave: (String?) async -> Bool
    @State private var takeaway = ""
    @State private var isSaving = false

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 16) {
                Text("What will you take with you?").font(.display).foregroundStyle(Theme.ink)
                Text("One sentence you can remember in a real conversation. This marks the mission complete — practice, not a skill score.")
                    .font(.subheadline)
                    .foregroundStyle(Theme.inkSecondary)
                TextField("e.g. Lead with the recommendation, then two reasons.", text: $takeaway, axis: .vertical)
                    .lineLimit(3...6)
                    .padding(14)
                    .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous).strokeBorder(Theme.stroke))
                Spacer()
                Button {
                    Task {
                        isSaving = true
                        let ok = await onSave(takeaway.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? nil : takeaway)
                        isSaving = false
                        if ok { dismiss() }
                    }
                } label: {
                    if isSaving { ProgressView().tint(.white) } else { Text("Finish mission") }
                }
                .buttonStyle(.primaryPill)
                .disabled(isSaving)
            }
            .padding(Theme.gutter)
            .screenBackground()
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Cancel") { dismiss() } } }
            .onAppear { if takeaway.isEmpty, let suggestion { takeaway = suggestion } }
        }
        .presentationDetents([.medium, .large])
    }
}

struct ReflectionSheet: View {
    static func label(for option: String) -> String {
        switch option {
        case "well": return "Went well"
        case "mixed": return "Mixed"
        default: return "Hard"
        }
    }

    @Environment(\.dismiss) private var dismiss
    let questions: [String]
    let onSubmit: (String, String?) async -> Reflection?
    @State private var text = ""
    @State private var went: String?
    @State private var isSaving = false
    @State private var reply: Reflection?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let reply {
                        Image(systemName: "sparkles").font(.largeTitle).foregroundStyle(Theme.violet)
                        Text("Thanks for trying it for real").font(.display).foregroundStyle(Theme.ink)
                        if let coach = reply.coachReply {
                            Text(coach).font(.body).foregroundStyle(Theme.ink).card()
                        }
                        Text("Your first real-life attempt is a milestone, whatever happened.").font(.footnote).foregroundStyle(Theme.inkSecondary)
                    } else {
                        Text("How did it go?").font(.display).foregroundStyle(Theme.ink)
                        HStack(spacing: 8) {
                            ForEach(["well", "mixed", "hard"], id: \.self) { option in
                                SelectableChip(title: Self.label(for: option), isSelected: went == option) { went = option }
                            }
                        }
                        if !questions.isEmpty {
                            VStack(alignment: .leading, spacing: 4) {
                                ForEach(questions, id: \.self) { question in
                                    Text("• \(question)").font(.footnote).foregroundStyle(Theme.inkSecondary)
                                }
                            }
                        }
                        TextField("What you said, how they reacted, how it felt…", text: $text, axis: .vertical)
                            .lineLimit(4...10)
                            .padding(14)
                            .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous))
                            .overlay(RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous).strokeBorder(Theme.stroke))
                        Text("Reflections inform your goals. They aren't used as audio evidence for skill estimates.")
                            .font(.caption)
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
                .padding(Theme.gutter)
            }
            .screenBackground()
            .safeAreaInset(edge: .bottom) {
                Group {
                    if reply == nil {
                        Button {
                            Task {
                                isSaving = true
                                reply = await onSubmit(text, went)
                                isSaving = false
                            }
                        } label: {
                            if isSaving { ProgressView().tint(.white) } else { Text("Save reflection") }
                        }
                        .buttonStyle(.primaryPill)
                        .disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).count < 3 || isSaving)
                    } else {
                        Button("Done") { dismiss() }.buttonStyle(.primaryPill)
                    }
                }
                .padding(.horizontal, Theme.gutter)
                .padding(.vertical, 10)
                .background(Theme.background)
            }
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Close") { dismiss() } } }
        }
    }
}
