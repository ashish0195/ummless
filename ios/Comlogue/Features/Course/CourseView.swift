import SwiftUI

/// The course for the chosen goal: this week as the one obvious thing, the other weeks as a short list (each opens
/// its own page). Whether it's tailored to a profile or based on the goal alone is said once, quietly, at the end.
struct CourseView: View {
    @Environment(AppModel.self) private var app
    @State private var isChangingTrack = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                if let course = app.course {
                    VStack(alignment: .leading, spacing: 24) {
                        header(course)
                        if let error { InlineErrorBanner(message: error) { self.error = nil } }
                        let focus = course.modules.first(where: { $0.id == course.focusModuleId }) ?? course.modules.first
                        if let focus {
                            ModuleCard(module: focus, highlighted: true)
                        }
                        let others = course.modules.filter { $0.id != focus?.id }
                        if !others.isEmpty {
                            VStack(alignment: .leading, spacing: 10) {
                                Text("All weeks").font(.title3Rounded).foregroundStyle(Theme.ink)
                                ForEach(others) { module in
                                    NavigationLink {
                                        ModuleDetailView(moduleId: module.id)
                                    } label: {
                                        WeekRow(module: module)
                                    }
                                    .buttonStyle(.pressableCard)
                                }
                            }
                        }
                        if !course.gapTasks.isEmpty {
                            gapSection(course.gapTasks)
                        }
                        if !course.isPro {
                            proTeaser
                        }
                        basisNote(course)
                    }
                    .padding(Theme.gutter)
                } else {
                    LoadingStateView(title: "Loading your course…")
                        .frame(minHeight: 400)
                }
            }
            .screenBackground()
            .navigationTitle("Course")
            .navigationBarTitleDisplayMode(.inline)
            .refreshable { await app.refreshCourse() }
            .navigationDestination(for: MissionSummary.self) { mission in
                MissionView(missionId: mission.id)
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        ForEach(app.meta?.tracks ?? []) { track in
                            Button {
                                Task { await changeTrack(track.id) }
                            } label: {
                                if track.id == app.course?.track.id {
                                    Label(track.title, systemImage: "checkmark")
                                } else {
                                    Text(track.title)
                                }
                            }
                        }
                    } label: {
                        Label("Change goal", systemImage: "arrow.triangle.branch")
                    }
                }
            }
            .overlay {
                if isChangingTrack { LoadingStateView(title: "Updating your course…").background(.ultraThinMaterial) }
            }
        }
    }

    private func header(_ course: Course) -> some View {
        HStack(spacing: 12) {
            Image(systemName: course.track.symbol)
                .font(.title3)
                .foregroundStyle(.white)
                .frame(width: 44, height: 44)
                .background(Theme.aurora, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                Text(course.track.title).font(.titleRounded).foregroundStyle(Theme.ink)
                Text(course.track.subtitle).font(.footnote).foregroundStyle(Theme.inkSecondary).lineLimit(2)
            }
        }
    }

    private func gapSection(_ gaps: [GapTask]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader("Fill in your profile", subtitle: "Optional. A few minutes each.")
            ForEach(gaps) { gap in
                Button {
                    app.present(.gapFill(activityId: gap.activityId))
                } label: {
                    HStack {
                        DimensionTag(dimension: gap.dimension)
                        Text(gap.title).font(.subheadline).foregroundStyle(Theme.ink).lineLimit(1)
                        Spacer()
                        Text("\(gap.minutes) min").font(.caption.weight(.semibold)).foregroundStyle(Theme.inkSecondary)
                    }
                    .card(padding: 14)
                }
                .buttonStyle(.pressableCard)
            }
        }
    }

    private var proTeaser: some View {
        HStack(spacing: 14) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Unlock every week").font(.headlineRounded).foregroundStyle(Theme.ink)
                Text("One mission is free. Pro unlocks the rest.").font(.subheadline).foregroundStyle(Theme.inkSecondary)
            }
            Spacer(minLength: 8)
            Button("See Pro") { app.present(.paywall) }
                .buttonStyle(.pill(.secondary, fullWidth: false))
        }
        .card()
    }

    /// Honest about what the order rests on, without leading with it.
    private func basisNote(_ course: Course) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Label(course.basisLabel, systemImage: course.basis == "profile" ? "person.crop.circle.badge.checkmark" : "flag.fill")
                .font(.footnote.weight(.semibold))
                .foregroundStyle(Theme.inkSecondary)
            Text(course.basisExplainer)
                .font(.caption)
                .foregroundStyle(Theme.inkTertiary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func changeTrack(_ track: TrackId) async {
        guard track != app.course?.track.id else { return }
        isChangingTrack = true
        defer { isChangingTrack = false }
        do {
            app.course = try await app.api.changeTrack(track)
            await app.refreshMe()
            app.showToast("Goal updated")
        } catch {
            self.error = error.userMessage
        }
    }
}

/// One week of the course: what it teaches, the behavior to aim for, and its missions.
private struct ModuleCard: View {
    let module: CourseModule
    /// The week you're on: outlined so it reads as "now".
    var highlighted = false

    private var color: Color { Theme.color(for: module.dimension) }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                Eyebrow("Week \(module.index) · \(DimensionCatalog.title(module.dimension))", color: color)
                Spacer()
                Text(module.status == "completed" ? "Done" : "\(module.completedMissions) of \(module.missions.count) done")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(module.status == "completed" ? Theme.mint : Theme.inkSecondary)
            }
            Text(module.title).font(.titleRounded).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
            Text(module.targetBehavior).font(.subheadline).foregroundStyle(Theme.inkSecondary).fixedSize(horizontal: false, vertical: true)
            VStack(spacing: 8) {
                ForEach(module.missions) { mission in
                    NavigationLink(value: mission) {
                        MissionRow(mission: mission, color: color)
                    }
                    .buttonStyle(.pressableCard)
                }
            }
        }
        .card()
        .overlay(
            RoundedRectangle(cornerRadius: Theme.radius, style: .continuous)
                .strokeBorder(highlighted ? color.opacity(0.6) : Color.clear, lineWidth: 1.5)
        )
    }
}

/// A week that isn't the current one, on a single row: its skill, its title, and whether it's done or locked.
private struct WeekRow: View {
    let module: CourseModule

    private var color: Color { Theme.color(for: module.dimension) }
    private var isDone: Bool { module.status == "completed" }
    private var isLocked: Bool { !module.missions.isEmpty && module.missions.allSatisfy { $0.isLocked } }

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: isDone ? "checkmark" : DimensionCatalog.symbol(module.dimension))
                .font(.headline)
                .foregroundStyle(isDone ? Theme.mint : color)
                .frame(width: 44, height: 44)
                .background((isDone ? Theme.mint : color).opacity(0.12), in: Circle())
            VStack(alignment: .leading, spacing: 2) {
                Text(module.title).font(.headlineRounded).foregroundStyle(Theme.ink).lineLimit(2)
                    .multilineTextAlignment(.leading)
                Text("Week \(module.index) · \(DimensionCatalog.title(module.dimension))")
                    .font(.subheadline)
                    .foregroundStyle(Theme.inkSecondary)
                    .lineLimit(1)
            }
            Spacer(minLength: 8)
            Image(systemName: isLocked ? "lock.fill" : "chevron.right")
                .font(.footnote.weight(.bold))
                .foregroundStyle(Theme.inkTertiary)
        }
        .padding(16)
        .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))
    }
}

/// A week's own page: the full card, and a way to make it the week you're on.
private struct ModuleDetailView: View {
    @Environment(AppModel.self) private var app
    let moduleId: String
    @State private var error: String?

    var body: some View {
        ScrollView {
            if let course = app.course, let module = course.modules.first(where: { $0.id == moduleId }) {
                VStack(alignment: .leading, spacing: 18) {
                    if let error { InlineErrorBanner(message: error) { self.error = nil } }
                    ModuleCard(module: module, highlighted: module.id == course.focusModuleId)
                    if module.id != course.focusModuleId && module.status != "completed" {
                        Button("Focus on this week") { Task { await focus() } }
                            .buttonStyle(.secondaryPill)
                    }
                }
                .padding(Theme.gutter)
            }
        }
        .screenBackground()
        .navigationBarTitleDisplayMode(.inline)
    }

    private func focus() async {
        do {
            app.course = try await app.api.changeFocus(moduleId: moduleId)
            Haptics.selection()
            app.showToast("This week is now your focus")
        } catch {
            self.error = error.userMessage
        }
    }
}

private struct MissionRow: View {
    let mission: MissionSummary
    let color: Color

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: mission.isCompleted ? "checkmark.circle.fill" : MissionCatalog.symbol(mission.type))
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(mission.isCompleted ? Theme.mint : color)
                .frame(width: 32, height: 32)
                .background((mission.isCompleted ? Theme.mint : color).opacity(0.12), in: Circle())
            VStack(alignment: .leading, spacing: 2) {
                Text(mission.title).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink).lineLimit(2)
                    .multilineTextAlignment(.leading)
                Text("\(mission.minutes) min").font(.caption).foregroundStyle(Theme.inkSecondary)
            }
            Spacer()
            if mission.isLocked {
                Image(systemName: "lock.fill").font(.caption).foregroundStyle(Theme.inkTertiary)
            } else {
                Image(systemName: "chevron.right").font(.caption.weight(.bold)).foregroundStyle(Theme.inkTertiary)
            }
        }
        .padding(10)
        .background(Theme.surfaceMuted.opacity(0.6), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}
