import SwiftUI

/// Home: one obvious next action, a lighter two-minute option, practice towards a weekly target,
/// gaps to fill, and anything that needs the person (e.g. confirming their voice in a recording).
struct TodayView: View {
    @Environment(AppModel.self) private var app
    @State private var activeAssessment: Assessment?
    @State private var pendingRecordings: [Recording] = []
    @State private var events: [UpcomingEvent] = []
    @State private var isLoading = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    header

                    if let assessment = activeAssessment, assessment.status == .inProgress {
                        resumeCard(assessment)
                    }

                    ForEach(pendingRecordings) { recording in
                        attentionCard(recording)
                    }

                    if !(app.me?.hasResults ?? false) && activeAssessment == nil {
                        profileStarterCard
                    }

                    if let today = app.course?.today {
                        missionCard(today)
                    }

                    weeklyCard

                    if let gaps = app.course?.gapTasks, !gaps.isEmpty {
                        gapCard(gaps)
                    }

                    eventCard

                    if let profile = app.profile, profile.hasAnyAssessed {
                        profileSnapshot(profile)
                    }
                }
                .padding(Theme.gutter)
            }
            .screenBackground()
            .refreshable { await reload() }
            .task(id: app.dataVersion) { await loadLocal() }
            .navigationDestination(for: String.self) { recordingId in
                RecordingDetailView(recordingId: recordingId)
            }
        }
    }

    // MARK: Sections

    private var header: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 4) {
                Text(Date.now, format: .dateTime.weekday(.wide).month().day())
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(Theme.inkSecondary)
                Text(Formatting.greeting()).font(.displayLarge).foregroundStyle(Theme.ink)
            }
            Spacer()
            if app.isDemo { DemoBadge() }
        }
    }

    private func resumeCard(_ assessment: Assessment) -> some View {
        Button {
            app.present(.guidedAssessment(resumeId: assessment.id))
        } label: {
            HStack(spacing: 14) {
                ProgressRing(value: Double(assessment.doneCount) / Double(max(assessment.activities.count, 1)))
                    .frame(width: 48, height: 48)
                VStack(alignment: .leading, spacing: 3) {
                    Text("Continue your assessment").font(.headlineRounded).foregroundStyle(Theme.ink)
                    Text("\(assessment.doneCount) of \(assessment.activities.count) conversations done · your answers are saved")
                        .font(.footnote)
                        .foregroundStyle(Theme.inkSecondary)
                }
                Spacer()
                Image(systemName: "chevron.right").foregroundStyle(Theme.inkTertiary)
            }
            .card()
        }
        .buttonStyle(.pressableCard)
    }

    private func attentionCard(_ recording: Recording) -> some View {
        NavigationLink(value: recording.id) {
            HStack(spacing: 14) {
                Image(systemName: recording.status == .needsSpeakerConfirmation ? "person.crop.circle.badge.questionmark" : "waveform.badge.magnifyingglass")
                    .font(.title2)
                    .foregroundStyle(Theme.coral)
                VStack(alignment: .leading, spacing: 3) {
                    Text(recording.status == .needsSpeakerConfirmation ? "Which voice is yours?" : "Analysing “\(recording.title)”")
                        .font(.headlineRounded)
                        .foregroundStyle(Theme.ink)
                    Text(recording.status == .needsSpeakerConfirmation ? "Confirm your voice in “\(recording.title)” to get feedback." : "We'll have results shortly.")
                        .font(.footnote)
                        .foregroundStyle(Theme.inkSecondary)
                }
                Spacer()
                Image(systemName: "chevron.right").foregroundStyle(Theme.inkTertiary)
            }
            .card()
        }
        .buttonStyle(.pressableCard)
    }

    private var profileStarterCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            Eyebrow("Start here", color: .white.opacity(0.8))
            Text("Get your communication profile").font(.titleRounded).foregroundStyle(.white)
            Text("Talk with an AI partner, upload a conversation, or record one. Feedback appears only where there's evidence.")
                .font(.subheadline)
                .foregroundStyle(.white.opacity(0.9))
            Button("Choose how to start") { app.present(.getStarted) }
                .buttonStyle(.lightPill)
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.aurora, in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))
    }

    private func missionCard(_ today: TodayPlan) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Eyebrow("Today's mission · \(today.mission.minutes) min", color: .white.opacity(0.85))
                Spacer()
                Image(systemName: MissionCatalog.symbol(today.mission.type)).foregroundStyle(.white.opacity(0.85))
            }
            Text(today.mission.title).font(.titleRounded).foregroundStyle(.white).fixedSize(horizontal: false, vertical: true)
            Text(today.moduleTitle).font(.subheadline).foregroundStyle(.white.opacity(0.85))
            Button {
                if today.mission.isLocked { app.present(.paywall) } else { app.present(.mission(id: today.mission.id, quick: false)) }
            } label: {
                Label(today.mission.isLocked ? "Unlock with Pro" : "Start today's mission", systemImage: today.mission.isLocked ? "lock.fill" : "play.fill")
            }
            .buttonStyle(.lightPill)
            if let quick = today.quick, !today.mission.isLocked {
                Button {
                    app.present(.mission(id: quick.missionId, quick: true))
                } label: {
                    Text("Short on time? \(quick.title) · \(quick.minutes) min")
                        .font(.footnote.weight(.semibold))
                        .frame(maxWidth: .infinity)
                }
                .foregroundStyle(.white)
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.aurora, in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))
        .shadow(color: Theme.indigo.opacity(0.25), radius: 18, y: 10)
    }

    private var weeklyCard: some View {
        let week = app.progress?.practice.thisWeek
        let target = max(week?.target ?? app.me?.practiceSettings.weeklyTarget ?? 3, 1)
        let sessions = week?.sessions ?? 0
        return HStack(spacing: 16) {
            ZStack {
                ProgressRing(value: Double(sessions) / Double(target), lineWidth: 9)
                VStack(spacing: 0) {
                    Text("\(sessions)").font(.title3.weight(.bold).monospacedDigit()).foregroundStyle(Theme.ink)
                    Text("of \(target)").font(.caption2.weight(.semibold)).foregroundStyle(Theme.inkSecondary)
                }
            }
            .frame(width: 70, height: 70)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(sessions) of \(target) practice sessions this week")
            VStack(alignment: .leading, spacing: 4) {
                Text("This week").font(.headlineRounded).foregroundStyle(Theme.ink)
                Text(weeklyMessage(sessions: sessions, target: target))
                    .font(.footnote)
                    .foregroundStyle(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
        }
        .card()
    }

    private func weeklyMessage(sessions: Int, target: Int) -> String {
        if sessions >= target { return "Target reached. Anything more is a bonus — and rest counts too." }
        if sessions == 0 { return "No streaks to lose here. One session gets you going whenever you're ready." }
        return "\(target - sessions) more to reach the target you set. Practice sessions, not skill scores."
    }

    private func gapCard(_ gaps: [GapTask]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader("Fill a gap", subtitle: "Short scenarios that give us evidence we don't have yet.")
            ForEach(gaps.prefix(3)) { gap in
                Button {
                    app.present(.gapFill(activityId: gap.activityId))
                } label: {
                    HStack(spacing: 12) {
                        Image(systemName: DimensionCatalog.symbol(gap.dimension))
                            .foregroundStyle(.white)
                            .frame(width: 36, height: 36)
                            .background(Theme.color(for: gap.dimension), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                        VStack(alignment: .leading, spacing: 2) {
                            Text(gap.title).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                            Text(gap.reason).font(.caption).foregroundStyle(Theme.inkSecondary).lineLimit(2)
                        }
                        Spacer()
                        Text("\(gap.minutes) min").font(.caption.weight(.semibold)).foregroundStyle(Theme.inkSecondary)
                    }
                }
                .buttonStyle(.pressableCard)
            }
        }
        .card()
    }

    @ViewBuilder
    private var eventCard: some View {
        if let next = events.sorted(by: { $0.date < $1.date }).first {
            VStack(alignment: .leading, spacing: 10) {
                Eyebrow("Coming up · \(prettyDate(next.date))", color: Theme.coral)
                Text(next.title).font(.headlineRounded).foregroundStyle(Theme.ink)
                if let prep = next.prep.first {
                    Button {
                        app.present(.spar(SparLaunch(title: prep.title, personaId: nil, customScenario: prep.scenario,
                                                     difficulty: prep.difficulty, eventId: next.id, prepId: prep.id)))
                    } label: {
                        Label("Rehearse: \(prep.title)", systemImage: "play.circle.fill")
                    }
                    .buttonStyle(.secondaryPill)
                }
            }
            .card()
        } else {
            Button {
                app.selectedTab = .practice
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: "calendar.badge.plus").font(.title3).foregroundStyle(Theme.coral)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Something coming up?").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                        Text("Add an interview, pitch or date and rehearse it with AI.").font(.caption).foregroundStyle(Theme.inkSecondary)
                    }
                    Spacer()
                    Image(systemName: "chevron.right").foregroundStyle(Theme.inkTertiary)
                }
                .card()
            }
            .buttonStyle(.pressableCard)
        }
    }

    private func profileSnapshot(_ profile: Profile) -> some View {
        Button {
            app.selectedTab = .you
        } label: {
            HStack(spacing: 16) {
                CommunicationWeb(dimensions: profile.dimensions, showLabels: false, animate: false)
                    .frame(width: 96, height: 96)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Your communication profile").font(.headlineRounded).foregroundStyle(Theme.ink)
                    let assessed = profile.dimensions.filter { $0.status.hasLevel }.count
                    Text("\(assessed) of 7 skills assessed").font(.footnote).foregroundStyle(Theme.inkSecondary)
                    Text("See details").font(.footnote.weight(.semibold)).foregroundStyle(Theme.indigo)
                }
                Spacer()
            }
            .card()
        }
        .buttonStyle(.pressableCard)
    }

    private func prettyDate(_ day: String) -> String {
        guard let date = JSONCoding.day(from: day) else { return day }
        return date.formatted(.dateTime.weekday(.abbreviated).month(.abbreviated).day())
    }

    // MARK: Loading

    private func reload() async {
        await app.refreshAll()
        await loadLocal()
    }

    private func loadLocal() async {
        if let id = LocalFlags.activeAssessmentId {
            activeAssessment = try? await app.api.assessment(id)
            if activeAssessment?.isFinished == true {
                LocalFlags.activeAssessmentId = nil
                activeAssessment = nil
            }
        } else {
            activeAssessment = nil
        }
        var pending: [Recording] = []
        for id in LocalFlags.pendingRecordingIds {
            if let recording = try? await app.api.recording(id) {
                if recording.status == .needsSpeakerConfirmation || recording.status.isWorking {
                    pending.append(recording)
                } else {
                    LocalFlags.pendingRecordingIds.removeAll { $0 == id }
                }
            }
        }
        pendingRecordings = pending
        events = (try? await app.api.events()) ?? []
    }
}
