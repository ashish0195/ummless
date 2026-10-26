import SwiftUI

/// The communication profile (evidence-based, per dimension, no overall score) plus practice progress
/// kept visibly separate from skill.
struct YouView: View {
    @Environment(AppModel.self) private var app
    @State private var showSettings = false
    @State private var recordings: [Recording] = []

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    HStack {
                        Text("You").font(.displayLarge).foregroundStyle(Theme.ink)
                        Spacer()
                        if app.isDemo { DemoBadge() }
                    }
                    if let profile = app.profile {
                        profileSection(profile)
                    } else {
                        LoadingStateView(title: "Loading your profile…").frame(minHeight: 300)
                    }
                    practiceSection
                    conversationsSection
                }
                .padding(Theme.gutter)
            }
            .screenBackground()
            .refreshable {
                await app.refreshAll()
                await loadRecordings()
            }
            .task(id: app.dataVersion) { await loadRecordings() }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showSettings = true } label: { Image(systemName: "gearshape.fill") }
                        .accessibilityLabel("Settings")
                }
            }
            .navigationDestination(for: DimensionId.self) { dimension in
                DimensionDetailView(dimension: dimension)
            }
            .navigationDestination(for: String.self) { recordingId in
                RecordingDetailView(recordingId: recordingId)
            }
            .sheet(isPresented: $showSettings) {
                SettingsView().environment(app)
            }
        }
    }

    // MARK: Profile

    @ViewBuilder
    private func profileSection(_ profile: Profile) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Eyebrow(basisLabel(profile.basis), color: Theme.indigo)
            Text(profile.headline).font(.titleRounded).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
            if let summary = profile.summary {
                Text(summary).font(.subheadline).foregroundStyle(Theme.inkSecondary)
            }
            if let updated = profile.updatedAt {
                Text("Updated \(Formatting.relative(updated))").font(.caption).foregroundStyle(Theme.inkTertiary)
            }
        }

        VStack(spacing: 12) {
            CommunicationWeb(dimensions: profile.dimensions)
                .frame(maxWidth: 360)
                .frame(maxWidth: .infinity)
            WebLegend()
            Text("No overall score — each skill stands on its own evidence.")
                .font(.caption)
                .foregroundStyle(Theme.inkTertiary)
        }
        .card()

        if !profile.hasAnyAssessed {
            EmptyStateView(systemImage: "waveform.badge.plus", title: "Nothing assessed yet",
                           message: "Talk with an AI partner, upload a conversation or record one to start your profile.",
                           actionTitle: "Get started") { app.present(.getStarted) }
                .card()
        }

        VStack(spacing: 8) {
            ForEach(profile.dimensions) { dimension in
                NavigationLink(value: dimension.dimension) {
                    DimensionRow(result: dimension)
                }
                .buttonStyle(.pressableCard)
            }
        }

        if let win = profile.firstWin {
            RewriteMomentCard(moment: win, title: "Try this next time")
        }
        if let patterns = profile.speechPatterns {
            SpeechPatternsCard(patterns: patterns)
        }
        StyleCard(style: profile.style)
        TwinCard(twin: profile.twin) { step in app.present(.gapFill(activityId: step.activityId)) }
    }

    private func basisLabel(_ basis: String) -> String {
        switch basis {
        case "assessment": return "Your communication profile"
        case "partial": return "Partial communication profile"
        case "goal_only": return "Based on your goal so far"
        default: return "Your communication profile"
        }
    }

    // MARK: Practice

    private var practiceSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader("Practice", subtitle: "What you've done — kept separate from what your skills show.")
            if let practice = app.progress?.practice {
                HStack(spacing: 12) {
                    statTile("\(practice.totalSessions)", "sessions")
                    statTile("\(practice.missionsCompleted)", "missions")
                    statTile("\(practice.minutes)", "minutes")
                    statTile("\(practice.weeksActive)", "weeks")
                }
            }
            if let milestones = app.progress?.milestones, !milestones.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 10) {
                        ForEach(milestones) { milestone in
                            VStack(alignment: .leading, spacing: 4) {
                                Image(systemName: "rosette").font(.title3).foregroundStyle(Theme.coral)
                                Text(milestone.title).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                                Text(milestone.detail).font(.caption).foregroundStyle(Theme.inkSecondary).lineLimit(2)
                            }
                            .frame(width: 170, alignment: .leading)
                            .card(padding: 14)
                        }
                    }
                }
            }
            Button {
                app.present(.weeklyReview)
            } label: {
                HStack {
                    Image(systemName: "gift.fill").foregroundStyle(Theme.violet)
                    Text("Your weekly reveal").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                    Spacer()
                    Image(systemName: "chevron.right").font(.caption.weight(.bold)).foregroundStyle(Theme.inkTertiary)
                }
                .card(padding: 14)
            }
            .buttonStyle(.pressableCard)
        }
    }

    private func statTile(_ value: String, _ label: String) -> some View {
        VStack(spacing: 2) {
            Text(value).font(.metricSmall).foregroundStyle(Theme.ink)
            Text(label).font(.caption2).foregroundStyle(Theme.inkSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(Theme.surface, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    // MARK: Conversations

    private var conversationsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader("Your conversations", trailing: AnyView(
                Menu {
                    Button { app.present(.upload) } label: { Label("Upload", systemImage: "square.and.arrow.up") }
                    Button { app.present(.liveRecording) } label: { Label("Record", systemImage: "record.circle") }
                    Button { app.present(.guidedAssessment(resumeId: nil)) } label: { Label("AI conversation", systemImage: "bubble.left.and.text.bubble.right") }
                } label: {
                    Image(systemName: "plus.circle.fill").font(.title2)
                }
            ))
            if recordings.isEmpty {
                Text("Recordings you add appear here with their results. You can delete any of them.")
                    .font(.footnote)
                    .foregroundStyle(Theme.inkSecondary)
            }
            ForEach(recordings) { recording in
                NavigationLink(value: recording.id) {
                    HStack(spacing: 12) {
                        Image(systemName: recording.source == "live" ? "record.circle" : "doc.richtext")
                            .foregroundStyle(Theme.indigo)
                            .frame(width: 36, height: 36)
                            .background(Theme.indigo.opacity(0.1), in: Circle())
                        VStack(alignment: .leading, spacing: 2) {
                            Text(recording.title).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink).lineLimit(1)
                            Text("\(statusText(recording)) · \(Formatting.relative(recording.createdAt))")
                                .font(.caption)
                                .foregroundStyle(Theme.inkSecondary)
                        }
                        Spacer()
                        Image(systemName: "chevron.right").font(.caption.weight(.bold)).foregroundStyle(Theme.inkTertiary)
                    }
                    .card(padding: 12)
                }
                .buttonStyle(.pressableCard)
            }
        }
    }

    private func statusText(_ recording: Recording) -> String {
        switch recording.status {
        case .processing, .assessing: return "Processing"
        case .needsSpeakerConfirmation: return "Needs you: which voice is yours?"
        case .complete: return recording.result?.status == .complete ? "Assessed" : "Partly assessed"
        case .needsRecovery: return "Couldn't assess — see why"
        case .failed: return "Couldn't open"
        case .noUser: return "You're not in it"
        }
    }

    private func loadRecordings() async {
        recordings = (try? await app.api.recordings()) ?? recordings
    }
}

struct DimensionRow: View {
    let result: DimensionResult

    var body: some View {
        let color = Theme.color(for: result.dimension)
        HStack(spacing: 12) {
            Image(systemName: DimensionCatalog.symbol(result.dimension))
                .font(.subheadline.weight(.bold))
                .foregroundStyle(result.status.hasLevel ? .white : Theme.inkTertiary)
                .frame(width: 36, height: 36)
                .background(result.status.hasLevel ? AnyShapeStyle(color) : AnyShapeStyle(Theme.surfaceMuted),
                            in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                Text(result.title).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                if let level = result.displayLevel {
                    Text((result.levelLabel ?? DimensionCatalog.levelLabel(level)) + (result.status == .provisional ? " · early read" : ""))
                        .font(.caption)
                        .foregroundStyle(color)
                } else {
                    Text("Not enough evidence yet").font(.caption).foregroundStyle(Theme.inkTertiary)
                }
            }
            Spacer()
            if let level = result.displayLevel { LevelDots(level: level, color: color) }
            Image(systemName: "chevron.right").font(.caption.weight(.bold)).foregroundStyle(Theme.inkTertiary)
        }
        .card(padding: 12)
    }
}

/// One dimension: what it means, the current estimate with its evidence, how it changed over time.
struct DimensionDetailView: View {
    @Environment(AppModel.self) private var app
    let dimension: DimensionId

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                let color = Theme.color(for: dimension)
                HStack(spacing: 12) {
                    Image(systemName: DimensionCatalog.symbol(dimension))
                        .font(.title2)
                        .foregroundStyle(.white)
                        .frame(width: 56, height: 56)
                        .background(color, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                    VStack(alignment: .leading, spacing: 2) {
                        Text(DimensionCatalog.title(dimension)).font(.display).foregroundStyle(Theme.ink)
                        Text(app.meta?.dimension(dimension)?.description ?? DimensionCatalog.blurb(dimension))
                            .font(.subheadline)
                            .foregroundStyle(Theme.inkSecondary)
                    }
                }
                if let result = app.profile?.dimension(dimension) {
                    DimensionResultCard(result: result) { step in app.present(.gapFill(activityId: step.activityId)) }
                }
                let history = app.profile?.history(for: dimension) ?? []
                if !history.isEmpty {
                    VStack(alignment: .leading, spacing: 10) {
                        Eyebrow("History")
                        ForEach(Array(history.enumerated()), id: \.offset) { _, entry in
                            HStack(spacing: 10) {
                                Circle().fill(entry.status.hasLevel ? color : Theme.stroke).frame(width: 8, height: 8)
                                VStack(alignment: .leading, spacing: 1) {
                                    Text(entry.level.map { DimensionCatalog.levelLabel($0) } ?? "Not enough evidence")
                                        .font(.subheadline.weight(.semibold))
                                        .foregroundStyle(Theme.ink)
                                    Text("\(entry.contextLabel) · \(Formatting.shortDate(entry.assessedAt))")
                                        .font(.caption)
                                        .foregroundStyle(Theme.inkSecondary)
                                }
                            }
                        }
                        Text("Estimates only change when new, assessable evidence arrives. Unclear audio never lowers them.")
                            .font(.caption)
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    .card()
                }
            }
            .padding(Theme.gutter)
        }
        .screenBackground()
        .navigationBarTitleDisplayMode(.inline)
    }
}

/// The weekly reveal: practice done, a before/after, which skills changed (only with evidence), next focus.
struct WeeklyReviewView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    var isRoot: Bool = false
    @State private var review: WeeklyReview?
    @State private var error: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                if let review {
                    content(review)
                } else if let error {
                    ErrorStateView(message: error) { Task { await load() } }
                } else {
                    LoadingStateView(title: "Putting your week together…").frame(minHeight: 400)
                }
            }
            .padding(Theme.gutter)
        }
        .screenBackground()
        .navigationTitle("Weekly reveal")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if isRoot {
                ToolbarItem(placement: .topBarTrailing) { CircleIconButton(systemName: "xmark") { app.dismissFlow() } }
            }
        }
        .task { await load() }
    }

    @ViewBuilder
    private func content(_ review: WeeklyReview) -> some View {
        Eyebrow("\(review.weekStart) – \(review.weekEnd)", color: Theme.violet)
        Text(review.message).font(.display).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)

        HStack(spacing: 16) {
            ZStack {
                ProgressRing(value: Double(review.practice.sessions) / Double(max(review.practice.target, 1)), lineWidth: 10)
                VStack(spacing: 0) {
                    Text("\(review.practice.sessions)").font(.metric).foregroundStyle(Theme.ink)
                    Text("of \(review.practice.target)").font(.caption2).foregroundStyle(Theme.inkSecondary)
                }
            }
            .frame(width: 92, height: 92)
            VStack(alignment: .leading, spacing: 4) {
                Text("\(review.practice.missionsCompleted) missions · \(review.practice.attempts) attempts · \(review.practice.retries) retries")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Theme.ink)
                Text("\(review.practice.minutes) minutes of practice · \(review.practice.realLifeAttempts) real-life")
                    .font(.footnote)
                    .foregroundStyle(Theme.inkSecondary)
            }
        }
        .card()

        if !review.highlights.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                Eyebrow("Highlights", color: Theme.coral)
                ForEach(review.highlights, id: \.self) { item in
                    Label(item, systemImage: "sparkles").font(.subheadline).foregroundStyle(Theme.ink)
                }
            }
            .card()
        }

        if let beforeAfter = review.beforeAfter {
            VStack(alignment: .leading, spacing: 10) {
                Eyebrow("Before and after · \(beforeAfter.missionTitle)", color: Theme.indigo)
                Text("Before: “\(beforeAfter.beforeQuote)”").font(.subheadline).foregroundStyle(Theme.inkSecondary)
                Text("After: “\(beforeAfter.afterQuote)”").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                Text(beforeAfter.note).font(.caption).foregroundStyle(Theme.inkTertiary)
            }
            .card()
        }

        VStack(alignment: .leading, spacing: 8) {
            Eyebrow("Skills")
            ForEach(Array(review.skillUpdates.enumerated()), id: \.offset) { _, update in
                HStack(alignment: .top, spacing: 8) {
                    DimensionTag(dimension: update.dimension, compact: true)
                    Text(update.note).font(.footnote).foregroundStyle(Theme.ink)
                }
            }
            Text(review.evidenceNote).font(.caption).foregroundStyle(Theme.inkSecondary)
        }
        .card()

        if !review.nextFocusOptions.isEmpty {
            SectionHeader("Choose next week's focus")
            ForEach(review.nextFocusOptions) { option in
                Button {
                    Task {
                        if let course = try? await app.api.changeFocus(moduleId: option.moduleId) {
                            app.course = course
                            app.showToast("Next focus set")
                        }
                    }
                } label: {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(option.title).font(.headlineRounded).foregroundStyle(Theme.ink)
                        Text(option.reason).font(.footnote).foregroundStyle(Theme.inkSecondary)
                    }
                    .card()
                }
                .buttonStyle(.pressableCard)
            }
        }
    }

    private func load() async {
        do {
            review = try await app.api.weeklyReview()
            error = nil
        } catch {
            self.error = error.userMessage
        }
    }
}
