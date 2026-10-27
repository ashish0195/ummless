import SwiftUI

/// Home: today's 60-second rep as the one obvious action, the week at a glance, this week's mission,
/// gaps to fill, and anything that needs the person (e.g. confirming their voice in a recording).
struct TodayView: View {
    @Environment(AppModel.self) private var app
    @State private var activeAssessment: Assessment?
    @State private var pendingRecordings: [Recording] = []
    @State private var isLoading = false

    private var events: [UpcomingEvent] { app.events }
    /// The next event from today on (past ones wait for their check-in).
    private var nextEvent: UpcomingEvent? {
        let today = HabitMath.dayString(Date(), timeZone: .current)
        return events.filter { $0.date >= today }.min { ($0.date, $0.time ?? "") < ($1.date, $1.time ?? "") }
    }
    /// An event from the last three days that hasn't been reflected on yet.
    private var eventToReflectOn: UpcomingEvent? {
        let today = HabitMath.dayString(Date(), timeZone: .current)
        let earliest = HabitMath.dayString(HabitMath.adding(days: -3, to: Date(), timeZone: .current), timeZone: .current)
        return events.filter { $0.reflection == nil && $0.date < today && $0.date >= earliest }.max { $0.date < $1.date }
    }
    /// Today or tomorrow: worth more than the rest of the screen.
    private var eventIsImminent: Bool {
        guard let next = nextEvent else { return false }
        let tomorrow = HabitMath.dayString(HabitMath.adding(days: 1, to: Date(), timeZone: .current), timeZone: .current)
        return next.date <= tomorrow
    }
    private var isOnBreak: Bool {
        guard let until = app.me?.practiceSettings.pausedUntil else { return false }
        return HabitMath.dayString(Date(), timeZone: .current) <= until
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    header

                    if let welcome = app.progress?.welcomeBack {
                        welcomeBackCard(welcome)
                    } else if isOnBreak {
                        breakCard
                    }

                    if let assessment = activeAssessment, assessment.status == .inProgress {
                        resumeCard(assessment)
                    }

                    ForEach(pendingRecordings) { recording in
                        attentionCard(recording)
                    }

                    if !(app.me?.hasResults ?? false) && activeAssessment == nil {
                        profileStarterCard
                    }

                    if let daily = app.daily {
                        // Until there's a profile, getting one is the hero; the rep is the quick alternative.
                        dailyRepCard(daily, prominent: app.me?.hasResults ?? false || activeAssessment != nil)
                    }

                    if let past = eventToReflectOn {
                        reflectCard(past)
                    }

                    if eventIsImminent { eventCard }

                    weeklyCard

                    if let today = app.course?.today {
                        missionCard(today)
                    }

                    if let gaps = app.course?.gapTasks, !gaps.isEmpty {
                        gapCard(gaps)
                    }

                    if !eventIsImminent { eventCard }

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
            HStack(spacing: 10) {
                if app.isDemo { DemoBadge() }
                InboxBellButton()
            }
        }
    }

    private func dailyRepCard(_ rep: DailyRep, prominent: Bool) -> some View {
        let ink: Color = prominent ? .white : Theme.ink
        let secondaryInk: Color = prominent ? .white.opacity(0.88) : Theme.inkSecondary
        return VStack(alignment: .leading, spacing: 12) {
            HStack {
                Eyebrow(rep.completed ? "Today's rep · done" : prominent ? "Today's rep · \(rep.suggestedSeconds) sec"
                        : "Or warm up · today's \(rep.suggestedSeconds)-second rep",
                        color: prominent ? .white.opacity(0.85) : Theme.indigo)
                Spacer()
                Tag(text: DimensionCatalog.title(rep.dimension), color: prominent ? .white : Theme.color(for: rep.dimension),
                    systemImage: DimensionCatalog.symbol(rep.dimension))
            }
            Text(rep.title).font(prominent ? .titleRounded : .title3Rounded).foregroundStyle(ink)
                .fixedSize(horizontal: false, vertical: true)
            Text(rep.prompt).font(.subheadline).foregroundStyle(secondaryInk).lineLimit(3)
            if rep.isProcessing {
                Label("Feedback on the way…", systemImage: "hourglass").font(.footnote.weight(.semibold)).foregroundStyle(ink)
            }
            Button {
                app.present(.daily(date: nil))
            } label: {
                if rep.completed {
                    Label("See feedback or go again", systemImage: "checkmark.circle.fill")
                } else {
                    Label("Start today's rep", systemImage: "mic.fill")
                }
            }
            .buttonStyle(.pill(prominent ? .light : .secondary))
            if let anchor = app.me?.practiceSettings.anchor, !rep.completed {
                Text(PracticeAnchor.secondPerson(anchor) + " is a good moment for it.")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(prominent ? .white.opacity(0.85) : Theme.inkTertiary)
                    .frame(maxWidth: .infinity)
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background {
            if prominent {
                RoundedRectangle(cornerRadius: Theme.radius, style: .continuous).fill(Theme.aurora)
                    .shadow(color: Theme.indigo.opacity(0.25), radius: 18, y: 10)
            } else {
                RoundedRectangle(cornerRadius: Theme.radius, style: .continuous).fill(Theme.surface)
                    .overlay(RoundedRectangle(cornerRadius: Theme.radius, style: .continuous)
                        .strokeBorder(Theme.stroke.opacity(0.7), lineWidth: 0.5))
                    .shadow(color: Color.black.opacity(0.04), radius: 12, x: 0, y: 6)
            }
        }
    }

    private func welcomeBackCard(_ welcome: WelcomeBack) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Welcome back", systemImage: "hand.wave.fill").font(.headlineRounded).foregroundStyle(Theme.ink)
            Text(welcome.message).font(.subheadline).foregroundStyle(Theme.inkSecondary)
                .fixedSize(horizontal: false, vertical: true)
            Button {
                app.present(.daily(date: nil))
            } label: {
                Label("Start with a 60-second rep", systemImage: "mic.fill")
            }
            .buttonStyle(.secondaryPill)
        }
        .card()
    }

    private var breakCard: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "pause.circle.fill").font(.title2).foregroundStyle(Theme.violet)
            VStack(alignment: .leading, spacing: 4) {
                Text("On a break until \(PracticePlanView.display(day: app.me?.practiceSettings.pausedUntil ?? ""))")
                    .font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                Text("Reminders are paused and your run is kept. Practise any time — it still counts.")
                    .font(.footnote).foregroundStyle(Theme.inkSecondary)
                Button("End break") {
                    Task {
                        var patch = MePatch()
                        patch.practiceSettings = MePatch.PracticePatch(endsBreak: true)
                        try? await app.updateMe(patch)
                        await app.refreshProgress()
                    }
                }
                .font(.footnote.weight(.semibold))
            }
            Spacer(minLength: 0)
        }
        .card()
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
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Eyebrow("Your course · \(today.mission.minutes) min", color: Theme.indigo)
                Spacer()
                Image(systemName: MissionCatalog.symbol(today.mission.type)).foregroundStyle(Theme.indigo)
            }
            Text(today.mission.title).font(.title3Rounded).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
            Text(today.moduleTitle).font(.subheadline).foregroundStyle(Theme.inkSecondary)
            Button {
                if today.mission.isLocked { app.present(.paywall) } else { app.present(.mission(id: today.mission.id, quick: false)) }
            } label: {
                Label(today.mission.isLocked ? "Unlock with Pro" : "Start this mission", systemImage: today.mission.isLocked ? "lock.fill" : "play.fill")
            }
            .buttonStyle(.secondaryPill)
            if let quick = today.quick, !today.mission.isLocked {
                Button {
                    app.present(.mission(id: quick.missionId, quick: true))
                } label: {
                    Text("Short on time? \(quick.title) · \(quick.minutes) min")
                        .font(.footnote.weight(.semibold))
                        .frame(maxWidth: .infinity)
                }
                .foregroundStyle(Theme.indigo)
            }
        }
        .card()
    }

    private var weeklyCard: some View {
        let week = app.progress?.practice.thisWeek
        let target = max(week?.target ?? app.me?.practiceSettings.weeklyTarget ?? 3, 1)
        let sessions = week?.sessions ?? 0
        let run = app.progress?.practice.weeksOnTarget ?? 0
        let hasPlan = !(app.me?.practiceSettings.reminderDays.isEmpty ?? true)
        return VStack(alignment: .leading, spacing: 14) {
        HStack(spacing: 16) {
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
                HStack(spacing: 6) {
                    Text("This week").font(.headlineRounded).foregroundStyle(Theme.ink)
                    if run >= 2 {
                        Tag(text: "\(run) weeks on target", color: Theme.mint, systemImage: "checkmark.seal.fill")
                    }
                }
                Text(weeklyMessage(sessions: sessions, target: target))
                    .font(.footnote)
                    .foregroundStyle(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
        }
        WeekStrip(days: week?.days ?? [])
        if !hasPlan {
            Button {
                app.present(.practicePlan)
            } label: {
                Label("Pick your practice days and a reminder", systemImage: "calendar.badge.clock")
                    .font(.footnote.weight(.semibold))
            }
            .foregroundStyle(Theme.indigo)
        }
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

    private func reflectCard(_ event: UpcomingEvent) -> some View {
        Button {
            app.present(.event(id: event.id))
        } label: {
            HStack(spacing: 14) {
                Image(systemName: "bubble.left.and.text.bubble.right.fill")
                    .font(.title3)
                    .foregroundStyle(Theme.violet)
                    .frame(width: 44, height: 44)
                    .background(Theme.violet.opacity(0.12), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                VStack(alignment: .leading, spacing: 3) {
                    Text("How did \(event.title) go?").font(.headlineRounded).foregroundStyle(Theme.ink)
                        .multilineTextAlignment(.leading)
                    Text("Thirty seconds to note what worked. It counts as practice.")
                        .font(.footnote).foregroundStyle(Theme.inkSecondary)
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right").foregroundStyle(Theme.inkTertiary)
            }
            .card()
        }
        .buttonStyle(.pressableCard)
    }

    @ViewBuilder
    private var eventCard: some View {
        if let next = nextEvent {
            VStack(alignment: .leading, spacing: 10) {
                Eyebrow("\(eventIsImminent ? "Soon" : "Coming up") · \(EventFormatting.when(next))", color: Theme.coral)
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
    }
}
