import SwiftUI

/// Home, kept deliberately simple: today's practice as the one obvious action, the week at a glance, and at most
/// two things that are up next (an interview tomorrow, the next lesson, a recording that needs you).
struct TodayView: View {
    @Environment(AppModel.self) private var app
    @State private var activeAssessment: Assessment?
    @State private var pendingRecordings: [Recording] = []

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    header
                    if let daily = app.daily {
                        practiceCard(daily)
                    }
                    weekSection
                    let items = upNext
                    if !items.isEmpty {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Up next").font(.title3Rounded).foregroundStyle(Theme.ink)
                            ForEach(items) { item in
                                UpNextRow(item: item)
                            }
                        }
                    }
                }
                .padding(.horizontal, Theme.gutter)
                .padding(.top, 8)
                .padding(.bottom, 24)
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
        HStack(alignment: .center) {
            VStack(alignment: .leading, spacing: 2) {
                Text(Date.now, format: .dateTime.weekday(.wide).month().day())
                    .font(.subheadline)
                    .foregroundStyle(Theme.inkSecondary)
                Text(Formatting.greeting()).font(.display).foregroundStyle(Theme.ink)
            }
            Spacer()
            InboxBellButton()
        }
    }

    private func practiceCard(_ rep: DailyRep) -> some View {
        let label: String = {
            if rep.completed { return "Done for today" }
            if app.progress?.welcomeBack != nil { return "Welcome back" }
            return "Today's practice · 1 min"
        }()
        return VStack(alignment: .leading, spacing: 18) {
            HStack(spacing: 6) {
                if rep.completed { Image(systemName: "checkmark.circle.fill") }
                Text(label)
            }
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(.white.opacity(0.85))
            Text(rep.title)
                .font(.system(size: 28, weight: .bold, design: .rounded))
                .foregroundStyle(.white)
                .fixedSize(horizontal: false, vertical: true)
            if rep.isProcessing {
                Label("Feedback on the way…", systemImage: "hourglass")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white)
            }
            Button {
                app.present(.daily(date: nil))
            } label: {
                Label(rep.completed ? "See feedback" : "Start", systemImage: rep.completed ? "text.bubble.fill" : "mic.fill")
            }
            .buttonStyle(.lightPill)
        }
        .padding(24)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.aurora, in: RoundedRectangle(cornerRadius: Theme.radius + 6, style: .continuous))
        .shadow(color: Theme.indigo.opacity(0.25), radius: 20, y: 10)
    }

    private var weekSection: some View {
        let week = app.progress?.practice.thisWeek
        let target = max(week?.target ?? app.me?.practiceSettings.weeklyTarget ?? 3, 1)
        let sessions = week?.sessions ?? 0
        let run = app.progress?.practice.weeksOnTarget ?? 0
        let summary: String = {
            if sessions >= target {
                return run >= 2 ? "Goal met · \(run) weeks in a row" : "Goal met"
            }
            return "\(sessions) of \(target) days"
        }()
        return VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                Text("This week").font(.title3Rounded).foregroundStyle(Theme.ink)
                Spacer()
                Text(summary)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(sessions >= target ? Theme.mint : Theme.inkSecondary)
            }
            WeekStrip(days: week?.days ?? [])
            if let until = breakEnd {
                HStack(spacing: 6) {
                    Text("On a break until \(PracticePlanView.display(day: until))")
                    Button("End") { Task { await endBreak() } }.fontWeight(.semibold)
                }
                .font(.footnote)
                .foregroundStyle(Theme.inkSecondary)
            } else if app.me?.practiceSettings.reminderDays.isEmpty ?? false {
                Button("Set a reminder") { app.present(.practicePlan) }
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(Theme.indigo)
            }
        }
    }

    /// At most two things, most time-sensitive first.
    private var upNext: [UpNextItem] {
        var items: [UpNextItem] = []
        let today = HabitMath.dayString(Date(), timeZone: .current)
        let tomorrow = HabitMath.dayString(HabitMath.adding(days: 1, to: Date(), timeZone: .current), timeZone: .current)
        let earliest = HabitMath.dayString(HabitMath.adding(days: -3, to: Date(), timeZone: .current), timeZone: .current)

        for recording in pendingRecordings {
            let confirm = recording.status == .needsSpeakerConfirmation
            items.append(UpNextItem(id: "rec-\(recording.id)", symbol: confirm ? "person.crop.circle.badge.questionmark" : "waveform",
                                    color: Theme.coral, title: confirm ? "Which voice is yours?" : "Analysing “\(recording.title)”",
                                    detail: confirm ? recording.title : "Results shortly",
                                    action: .push(recording.id)))
        }
        if let assessment = activeAssessment, assessment.status == .inProgress {
            items.append(UpNextItem(id: "asm", symbol: "bubble.left.and.text.bubble.right.fill", color: Theme.indigo,
                                    title: "Continue your profile",
                                    detail: "\(assessment.doneCount) of \(assessment.activities.count) done",
                                    action: .flow(.guidedAssessment(resumeId: assessment.id))))
        }
        if let past = app.events.filter({ $0.reflection == nil && $0.date < today && $0.date >= earliest }).max(by: { $0.date < $1.date }) {
            items.append(UpNextItem(id: "reflect-\(past.id)", symbol: "bubble.left.and.text.bubble.right.fill", color: Theme.violet,
                                    title: "How did it go?", detail: past.title, action: .flow(.event(id: past.id))))
        }
        if let next = app.events.filter({ $0.date >= today }).min(by: { ($0.date, $0.time ?? "") < ($1.date, $1.time ?? "") }) {
            let soon = next.date <= tomorrow
            items.append(UpNextItem(id: "event-\(next.id)", symbol: "calendar", color: Theme.coral,
                                    title: next.title, detail: (soon ? "Rehearse · " : "") + EventFormatting.when(next),
                                    action: .flow(.event(id: next.id))))
        }
        if !(app.me?.hasResults ?? false) && activeAssessment == nil {
            items.append(UpNextItem(id: "profile", symbol: "sparkles", color: Theme.indigo,
                                    title: "Get your communication profile", detail: "About 10 minutes",
                                    action: .flow(.getStarted)))
        }
        if let today = app.course?.today, !today.mission.isLocked {
            items.append(UpNextItem(id: "mission", symbol: MissionCatalog.symbol(today.mission.type), color: Theme.indigo,
                                    title: today.mission.title, detail: "Your course · \(today.mission.minutes) min",
                                    action: .flow(.mission(id: today.mission.id, quick: false))))
        }
        return Array(items.prefix(2))
    }

    private var breakEnd: String? {
        guard let until = app.me?.practiceSettings.pausedUntil,
              HabitMath.dayString(Date(), timeZone: .current) <= until else { return nil }
        return until
    }

    private func endBreak() async {
        var patch = MePatch()
        patch.practiceSettings = MePatch.PracticePatch(endsBreak: true)
        try? await app.updateMe(patch)
        await app.refreshProgress()
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

private struct UpNextItem: Identifiable {
    enum Action {
        case flow(AppFlow)
        case push(String)
    }

    let id: String
    let symbol: String
    let color: Color
    let title: String
    let detail: String
    let action: Action
}

private struct UpNextRow: View {
    @Environment(AppModel.self) private var app
    let item: UpNextItem

    var body: some View {
        switch item.action {
        case .flow(let flow):
            Button { app.present(flow) } label: { content }
                .buttonStyle(.pressableCard)
        case .push(let recordingId):
            NavigationLink(value: recordingId) { content }
                .buttonStyle(.pressableCard)
        }
    }

    private var content: some View {
        HStack(spacing: 14) {
            Image(systemName: item.symbol)
                .font(.headline)
                .foregroundStyle(item.color)
                .frame(width: 44, height: 44)
                .background(item.color.opacity(0.12), in: Circle())
            VStack(alignment: .leading, spacing: 2) {
                Text(item.title).font(.headlineRounded).foregroundStyle(Theme.ink).lineLimit(2)
                    .multilineTextAlignment(.leading)
                Text(item.detail).font(.subheadline).foregroundStyle(Theme.inkSecondary).lineLimit(1)
            }
            Spacer(minLength: 8)
            Image(systemName: "chevron.right").font(.footnote.weight(.bold)).foregroundStyle(Theme.inkTertiary)
        }
        .padding(16)
        .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))
    }
}
