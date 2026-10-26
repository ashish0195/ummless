import SwiftUI

/// The course map for the chosen goal. Labelled "Tailored to your profile" only when evidence exists;
/// otherwise "Based on your goal".
struct CourseView: View {
    @Environment(AppModel.self) private var app
    @State private var isChangingTrack = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                if let course = app.course {
                    VStack(alignment: .leading, spacing: 18) {
                        header(course)
                        if let error { InlineErrorBanner(message: error) { self.error = nil } }
                        ForEach(course.modules) { module in
                            ModuleCard(module: module, isFocus: module.id == course.focusModuleId, isPro: course.isPro) {
                                Task { await focus(module.id) }
                            }
                        }
                        if !course.gapTasks.isEmpty {
                            gapSection(course.gapTasks)
                        }
                        if !course.isPro {
                            proTeaser
                        }
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
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
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
            HStack(alignment: .top, spacing: 8) {
                Tag(text: course.basisLabel, color: course.basis == "profile" ? Theme.mint : Theme.amber,
                    systemImage: course.basis == "profile" ? "person.crop.circle.badge.checkmark" : "flag.fill")
            }
            Text(course.basisExplainer).font(.footnote).foregroundStyle(Theme.inkSecondary).fixedSize(horizontal: false, vertical: true)
        }
    }

    private func gapSection(_ gaps: [GapTask]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader("Optional: fill evidence gaps", subtitle: "These help tailor the course. They never block it.")
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
        VStack(alignment: .leading, spacing: 10) {
            Text("You're previewing the full course").font(.headlineRounded).foregroundStyle(Theme.ink)
            Text("Your baseline, gap-filling tasks and one practice mission are free. Pro unlocks every mission, unlimited sparring and event prep.")
                .font(.subheadline)
                .foregroundStyle(Theme.inkSecondary)
            Button("See Pro") { app.present(.paywall) }.buttonStyle(.secondaryPill)
        }
        .card(background: Theme.surface)
    }

    private func focus(_ moduleId: String) async {
        do {
            app.course = try await app.api.changeFocus(moduleId: moduleId)
            Haptics.selection()
        } catch {
            self.error = error.userMessage
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

private struct ModuleCard: View {
    let module: CourseModule
    let isFocus: Bool
    let isPro: Bool
    let onFocus: () -> Void

    private var color: Color { Theme.color(for: module.dimension) }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Eyebrow("Week \(module.index) · \(DimensionCatalog.title(module.dimension))", color: color)
                    Text(module.title).font(.title3Rounded).foregroundStyle(Theme.ink)
                }
                Spacer()
                statusBadge
            }
            HStack(alignment: .top, spacing: 8) {
                Image(systemName: "scope").foregroundStyle(color)
                Text(module.targetBehavior).font(.subheadline).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
            }
            VStack(spacing: 8) {
                ForEach(module.missions) { mission in
                    NavigationLink(value: mission) {
                        MissionRow(mission: mission, color: color)
                    }
                    .buttonStyle(.pressableCard)
                }
            }
            if !isFocus && module.status != "completed" {
                Button("Focus on this module", action: onFocus)
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(Theme.indigo)
            }
        }
        .card()
        .overlay(
            RoundedRectangle(cornerRadius: Theme.radius, style: .continuous)
                .strokeBorder(isFocus ? color.opacity(0.6) : Color.clear, lineWidth: 1.5)
        )
    }

    @ViewBuilder private var statusBadge: some View {
        if module.status == "completed" {
            Tag(text: "Done", color: Theme.mint, systemImage: "checkmark")
        } else if isFocus {
            Tag(text: "Now", color: color, filled: true)
        } else {
            Text("\(module.completedMissions)/\(module.missions.count)").font(.caption.weight(.semibold)).foregroundStyle(Theme.inkSecondary)
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
                Text("\(MissionCatalog.title(mission.type)) · \(mission.minutes) min").font(.caption).foregroundStyle(Theme.inkSecondary)
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
