import SwiftUI

@MainActor
@Observable
final class RecordingDetailModel {
    let recordingId: String
    private let app: AppModel
    var recording: Recording?
    var error: String?
    var isSubmitting = false
    var isCorrecting = false
    private var pollTask: Task<Void, Never>?

    init(recordingId: String, app: AppModel) {
        self.recordingId = recordingId
        self.app = app
    }

    func load() async {
        do {
            recording = try await app.api.recording(recordingId)
            error = nil
            if recording?.status.isWorking == true { startPolling() }
        } catch {
            self.error = error.userMessage
        }
    }

    func startPolling() {
        pollTask?.cancel()
        pollTask = Task { @MainActor [weak self] in
            var delay: UInt64 = 2_000_000_000
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: delay)
                guard let self, !Task.isCancelled else { return }
                guard let updated = try? await self.app.api.recording(self.recordingId) else { continue }
                self.recording = updated
                if !updated.status.isWorking {
                    if updated.status == .complete || updated.status == .noUser {
                        LocalFlags.pendingRecordingIds.removeAll { $0 == updated.id }
                        await self.app.refreshAll()
                    }
                    return
                }
                delay = min(delay + 1_000_000_000, 6_000_000_000)
            }
        }
    }

    func stopPolling() { pollTask?.cancel() }

    func confirm(decision: String, label: String?) async {
        isSubmitting = true
        defer { isSubmitting = false }
        do {
            recording = try await app.api.confirmSpeaker(recordingId: recordingId, decision: decision, speakerLabel: label)
            isCorrecting = false
            Haptics.success()
            if recording?.status.isWorking == true { startPolling() } else { await app.refreshAll() }
        } catch {
            self.error = error.userMessage
        }
    }

    func delete() async -> Bool {
        do {
            try await app.api.deleteRecording(recordingId)
            LocalFlags.pendingRecordingIds.removeAll { $0 == recordingId }
            await app.refreshAll()
            return true
        } catch {
            self.error = error.userMessage
            return false
        }
    }
}

/// Processing → "which voice is yours?" → results (or a specific recovery) for one recording.
struct RecordingDetailView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let recordingId: String
    var isRoot: Bool = false
    @State private var model: RecordingDetailModel?
    @State private var confirmDelete = false

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                LoadingStateView()
            }
        }
        .screenBackground()
        .navigationTitle(model?.recording?.title ?? "Recording")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if isRoot {
                ToolbarItem(placement: .topBarTrailing) {
                    CircleIconButton(systemName: "xmark") { app.dismissFlow() }
                }
            }
            ToolbarItem(placement: .topBarLeading) {
                if model?.recording != nil {
                    Menu {
                        if model?.recording?.status == .complete || model?.recording?.status == .noUser {
                            Button("Change which voice is mine") { model?.isCorrecting = true }
                        }
                        Button("Delete recording", role: .destructive) { confirmDelete = true }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
        }
        .confirmationDialog("Delete this recording and its results?", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("Delete", role: .destructive) {
                Task {
                    if await model?.delete() == true {
                        if isRoot { app.dismissFlow() } else { dismiss() }
                    }
                }
            }
        } message: {
            Text("Your communication profile will be recalculated without it. This can't be undone.")
        }
        .task {
            if model == nil {
                let created = RecordingDetailModel(recordingId: recordingId, app: app)
                model = created
                await created.load()
            }
        }
        .onDisappear { model?.stopPolling() }
    }

    @ViewBuilder
    private func content(_ model: RecordingDetailModel) -> some View {
        if let recording = model.recording {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    if let error = model.error { InlineErrorBanner(message: error) { model.error = nil } }
                    if model.isCorrecting || recording.status == .needsSpeakerConfirmation {
                        SpeakerConfirmationView(recording: recording, isSubmitting: model.isSubmitting, isCorrection: model.isCorrecting) { decision, label in
                            Task { await model.confirm(decision: decision, label: label) }
                        }
                    } else {
                        statusContent(recording, model: model)
                    }
                }
                .padding(Theme.gutter)
            }
            .refreshable { await model.load() }
        } else if let error = model.error {
            ErrorStateView(message: error) { Task { await model.load() } }
        } else {
            LoadingStateView()
        }
    }

    @ViewBuilder
    private func statusContent(_ recording: Recording, model: RecordingDetailModel) -> some View {
        switch recording.status {
        case .processing, .assessing:
            RecordingProgressCard(recording: recording)
        case .needsSpeakerConfirmation:
            EmptyView()
        case .complete:
            if let quality = recording.quality, quality.usable == .partly {
                VStack(alignment: .leading, spacing: 8) {
                    Label("We used \(Formatting.clock(quality.usableSeconds)) of \(Formatting.clock(quality.totalSeconds)) — the clearest parts.",
                          systemImage: "scissors")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(Theme.inkSecondary)
                    if !quality.issues.isEmpty { IssueCard(issues: quality.issues) }
                }
            }
            if let result = recording.result {
                AnalysisResultView(result: result) { action in app.handle(action) }
            }
            if let debrief = recording.debrief {
                MeetingDebriefCard(debrief: debrief)
            }
            Button("Wrong voice? Change which one is yours") { model.isCorrecting = true }
                .font(.footnote.weight(.semibold))
                .foregroundStyle(Theme.indigo)
                .frame(maxWidth: .infinity)
        case .needsRecovery, .failed:
            VStack(alignment: .leading, spacing: 14) {
                if let quality = recording.quality, !quality.issues.isEmpty {
                    IssueCard(issues: quality.issues)
                }
                if let recovery = recording.recovery {
                    RecoveryCard(recovery: recovery) { action in
                        if action.type == .identifySpeaker { model.isCorrecting = true } else { app.handle(.recovery(action)) }
                    }
                } else if let recovery = recording.result?.recovery {
                    RecoveryCard(recovery: recovery) { action in app.handle(.recovery(action)) }
                }
                if let result = recording.result, result.status != .noneAssessed {
                    AnalysisResultView(result: result) { action in app.handle(action) }
                }
            }
        case .noUser:
            VStack(alignment: .leading, spacing: 12) {
                Image(systemName: "person.crop.circle.badge.xmark").font(.system(size: 40)).foregroundStyle(Theme.inkTertiary)
                Text("You're not in this one").font(.display).foregroundStyle(Theme.ink)
                Text("Since none of the voices are yours, we didn't assess anything. Other people's speech never goes into your profile.")
                    .font(.body)
                    .foregroundStyle(Theme.inkSecondary)
                Button("Actually, one of these voices is mine") { model.isCorrecting = true }
                    .buttonStyle(.secondaryPill)
                Button("Upload another conversation") { app.present(.upload) }
                    .buttonStyle(.ghostPill)
            }
        }
    }
}

private struct RecordingProgressCard: View {
    let recording: Recording

    private var steps: [(key: String, title: String)] {
        [("decoding", "Opening your recording"), ("checking_audio", "Checking audio quality"),
         ("identifying_speakers", "Separating the voices"), ("assessing", "Looking for evidence, skill by skill")]
    }

    private var currentIndex: Int {
        if recording.status == .assessing { return 3 }
        return steps.firstIndex { $0.key == recording.stage } ?? 0
    }

    var body: some View {
        VStack(spacing: 22) {
            VoiceOrb(level: 0.3).frame(width: 140, height: 140).padding(.top, 20)
            VStack(alignment: .leading, spacing: 14) {
                ForEach(Array(steps.enumerated()), id: \.offset) { index, step in
                    HStack(spacing: 12) {
                        ZStack {
                            if index < currentIndex {
                                Image(systemName: "checkmark.circle.fill").foregroundStyle(Theme.mint)
                            } else if index == currentIndex {
                                ProgressView().controlSize(.small)
                            } else {
                                Image(systemName: "circle").foregroundStyle(Theme.stroke)
                            }
                        }
                        .frame(width: 24)
                        Text(step.title)
                            .font(.subheadline.weight(index == currentIndex ? .semibold : .regular))
                            .foregroundStyle(index <= currentIndex ? Theme.ink : Theme.inkTertiary)
                    }
                }
            }
            .card()
            Text("You can close this — we'll keep working and let you know on the Today tab.")
                .font(.footnote)
                .foregroundStyle(Theme.inkSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
    }
}

/// "Which voice is yours?" — play candidate clips, confirm, choose another, or say you're not in it.
struct SpeakerConfirmationView: View {
    @Environment(AppModel.self) private var app
    let recording: Recording
    let isSubmitting: Bool
    var isCorrection: Bool = false
    let onDecision: (String, String?) -> Void

    @State private var showOthers = false

    private var proposed: SpeakerCandidate? { recording.speakers.first { $0.isProposedUser } }
    private var others: [SpeakerCandidate] { recording.speakers.filter { !$0.isProposedUser } }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Eyebrow(isCorrection ? "Correct the speaker" : "Before any feedback", color: Theme.indigo)
            Text(proposed == nil || isCorrection ? "Which voice is yours?" : "Is this you?")
                .font(.display)
                .foregroundStyle(Theme.ink)
            Text(recording.attribution.message ?? defaultMessage)
                .font(.body)
                .foregroundStyle(Theme.inkSecondary)
                .fixedSize(horizontal: false, vertical: true)

            if let proposed, !isCorrection {
                SpeakerRow(speaker: proposed, recordingId: recording.id, highlighted: true)
                VStack(spacing: 8) {
                    Button("Yes, that's me") { onDecision("confirm", proposed.label) }
                        .buttonStyle(.primaryPill)
                    Button("Choose another speaker") { withAnimation { showOthers.toggle() } }
                        .buttonStyle(.secondaryPill)
                    Button("I'm not in this recording") { onDecision("not_present", nil) }
                        .buttonStyle(.ghostPill)
                }
                .disabled(isSubmitting)
                if showOthers {
                    otherSpeakers(others)
                }
            } else {
                otherSpeakers(recording.speakers)
                Button("I'm not in this recording") { onDecision("not_present", nil) }
                    .buttonStyle(.ghostPill)
                    .disabled(isSubmitting)
            }

            if isSubmitting { ProgressView().frame(maxWidth: .infinity) }

            Text("Picking a speaker labels their turns, but it can't fix audio we couldn't hear clearly. We never assume \"Speaker A\" is the same person across recordings.")
                .font(.caption)
                .foregroundStyle(Theme.inkTertiary)
        }
    }

    private var defaultMessage: String {
        switch recording.attribution.reason {
        case "first_conversation": return "This is your first recording, so we'll check with you. Play the clip and confirm."
        case "uncertain_match", "conflict": return "We weren't sure which voice matched yours. Have a listen."
        case "no_reference": return "Play the clips and tap the one that's you."
        default: return "Play the clips and tap the one that's you."
        }
    }

    private func otherSpeakers(_ speakers: [SpeakerCandidate]) -> some View {
        VStack(spacing: 10) {
            ForEach(speakers) { speaker in
                VStack(spacing: 8) {
                    SpeakerRow(speaker: speaker, recordingId: recording.id, highlighted: false)
                    Button("This is me") { onDecision(speaker.isProposedUser ? "confirm" : "choose", speaker.label) }
                        .buttonStyle(.pill(.secondary))
                        .disabled(isSubmitting)
                }
            }
        }
    }
}

private struct SpeakerRow: View {
    @Environment(AppModel.self) private var app
    let speaker: SpeakerCandidate
    let recordingId: String
    let highlighted: Bool

    private var key: String { "speaker-\(recordingId)-\(speaker.label)" }

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            Button {
                if let url = speaker.sampleUrl {
                    app.player.toggle(path: url, api: app.api, key: key)
                }
            } label: {
                Image(systemName: app.player.isPlaying(key: key) ? "stop.fill" : "play.fill")
                    .font(.headline)
                    .foregroundStyle(.white)
                    .frame(width: 48, height: 48)
                    .background(speaker.sampleUrl == nil ? AnyShapeStyle(Theme.inkTertiary) : AnyShapeStyle(Theme.aurora), in: Circle())
            }
            .buttonStyle(.plain)
            .disabled(speaker.sampleUrl == nil)
            .accessibilityLabel("Play a clip of \(speaker.displayName)")
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(speaker.displayName).font(.headlineRounded).foregroundStyle(Theme.ink)
                    if speaker.isProposedUser, speaker.match != "none" {
                        Tag(text: matchLabel, color: speaker.matchStrength == "strong" ? Theme.mint : Theme.amber)
                    }
                }
                if let text = speaker.sampleText {
                    Text("“\(text)”").font(.footnote).italic().foregroundStyle(Theme.inkSecondary).lineLimit(3)
                }
                Text("\(Formatting.clock(speaker.speechSeconds)) of speech · \(speaker.turns) turns")
                    .font(.caption)
                    .foregroundStyle(Theme.inkTertiary)
            }
            Spacer(minLength: 0)
        }
        .card(padding: 14)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.radius, style: .continuous)
                .strokeBorder(highlighted ? Theme.indigo.opacity(0.5) : Color.clear, lineWidth: 1.5)
        )
    }

    private var matchLabel: String {
        switch speaker.match {
        case "reference": return speaker.matchStrength == "strong" ? "Matches your voice sample" : "Possible match"
        case "acoustic": return "Sounds like your sample"
        case "loudest": return "Closest to the phone"
        default: return "Suggested"
        }
    }
}

struct MeetingDebriefCard: View {
    @Environment(AppModel.self) private var app
    let debrief: MeetingDebrief

    private let palette: [Color] = [Theme.coral, Theme.indigo, Theme.violet, Theme.mint, Theme.amber, Theme.inkTertiary]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Eyebrow("Conversation debrief", color: Theme.coral)
            if !debrief.talkShare.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Who spoke").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                    GeometryReader { proxy in
                        HStack(spacing: 2) {
                            ForEach(Array(debrief.talkShare.enumerated()), id: \.offset) { index, share in
                                Rectangle()
                                    .fill(share.isUser ? Theme.coral : palette[(index % (palette.count - 1)) + 1])
                                    .frame(width: max(2, proxy.size.width * share.share))
                            }
                        }
                    }
                    .frame(height: 14)
                    .clipShape(Capsule())
                    FlowLayout(spacing: 10, lineSpacing: 6) {
                        ForEach(Array(debrief.talkShare.enumerated()), id: \.offset) { index, share in
                            HStack(spacing: 5) {
                                Circle().fill(share.isUser ? Theme.coral : palette[(index % (palette.count - 1)) + 1]).frame(width: 8, height: 8)
                                Text("\(share.isUser ? "You" : share.displayName) \(Formatting.percent(share.share))")
                                    .font(.caption.weight(share.isUser ? .bold : .regular))
                                    .foregroundStyle(Theme.ink)
                            }
                        }
                    }
                }
            }
            if let moment = debrief.bestMoment {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Your best moment").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                    EvidenceMomentRow(moment: moment, tint: Theme.coral)
                }
            }
            if !debrief.decisions.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Decisions").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                    ForEach(Array(debrief.decisions.enumerated()), id: \.offset) { index, decision in
                        HStack(alignment: .top, spacing: 8) {
                            Text("\(index + 1).").font(.footnote.weight(.bold)).foregroundStyle(Theme.inkSecondary)
                            Text(decision).font(.footnote).foregroundStyle(Theme.ink)
                        }
                    }
                }
            }
            if let thing = debrief.oneThingToTry {
                Label(thing, systemImage: "arrow.turn.down.right")
                    .font(.subheadline)
                    .foregroundStyle(Theme.ink)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Theme.coral.opacity(0.08), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
            if let summary = debrief.followUpSummary {
                ShareLink(item: summary) {
                    Label("Share follow-up summary", systemImage: "square.and.arrow.up")
                }
                .buttonStyle(.secondaryPill)
            }
        }
        .card()
    }
}
