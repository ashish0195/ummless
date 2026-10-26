import SwiftUI

/// "How would you like to start?" — the three input routes from the spec, with honest time estimates.
/// Voice setup and recovery time are shown separately from the 10–15 minute guided assessment.
struct GetStartedView: View {
    @Environment(AppModel.self) private var app
    var showsClose: Bool = true

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    VStack(alignment: .leading, spacing: 8) {
                        Eyebrow("Your communication profile", color: Theme.indigo)
                        Text("How would you like to start?")
                            .font(.display)
                            .foregroundStyle(Theme.ink)
                        Text("We build your profile from real speech. Pick whatever's easiest today — you can add more conversations later.")
                            .font(.body)
                            .foregroundStyle(Theme.inkSecondary)
                    }

                    RouteCard(
                        icon: "bubble.left.and.text.bubble.right.fill",
                        title: "Talk with an AI partner",
                        detail: "Five short, friendly conversations. Only your voice is analysed, so no one else needs to agree.",
                        time: "\(Formatting.minutesRange(app.meta?.assessmentEstimateMinutes ?? [10, 15])) · guided",
                        highlight: true
                    ) {
                        LocalFlags.hasSeenFirstRun = true
                        app.present(.guidedAssessment(resumeId: LocalFlags.activeAssessmentId))
                    }

                    RouteCard(
                        icon: "square.and.arrow.up.on.square.fill",
                        title: "Upload conversations",
                        detail: "Calls, meetings or chats you recorded with everyone's permission. Add one or several.",
                        time: "A few minutes + processing",
                        highlight: false
                    ) {
                        LocalFlags.hasSeenFirstRun = true
                        app.present(.upload)
                    }

                    RouteCard(
                        icon: "record.circle.fill",
                        title: "Record a conversation",
                        detail: "Keep your phone nearby during a meeting or a chat. Everyone present needs to agree.",
                        time: "As long as your conversation",
                        highlight: false
                    ) {
                        LocalFlags.hasSeenFirstRun = true
                        app.present(.liveRecording)
                    }

                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: "clock.fill").foregroundStyle(Theme.inkTertiary)
                        Text("Uploads and recordings start with a quick voice setup (about \(app.meta?.voiceSetupEstimateMinutes ?? 1) min) so we can find your turns. It's optional — you can pick your voice by hand instead.")
                            .font(.footnote)
                            .foregroundStyle(Theme.inkSecondary)
                    }
                    .padding(.top, 4)

                    Divider().padding(.vertical, 4)

                    Button {
                        LocalFlags.hasSeenFirstRun = true
                        app.selectedTab = .course
                        app.dismissFlow()
                    } label: {
                        VStack(spacing: 4) {
                            Text("Not now — start a goal-based course")
                                .font(.subheadline.weight(.semibold))
                            Text("It's labelled \"Based on your goal\" until we have evidence from your speech.")
                                .font(.caption)
                                .foregroundStyle(Theme.inkTertiary)
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(Theme.indigo)
                }
                .padding(Theme.gutter)
            }
            .screenBackground()
            .toolbar {
                if showsClose {
                    ToolbarItem(placement: .topBarTrailing) {
                        CircleIconButton(systemName: "xmark") {
                            LocalFlags.hasSeenFirstRun = true
                            app.dismissFlow()
                        }
                    }
                }
                if app.isDemo {
                    ToolbarItem(placement: .topBarLeading) { DemoBadge() }
                }
            }
        }
    }
}

private struct RouteCard: View {
    let icon: String
    let title: String
    let detail: String
    let time: String
    let highlight: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 16) {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundStyle(highlight ? Color.white : Theme.indigo)
                    .frame(width: 52, height: 52)
                    .background(highlight ? AnyShapeStyle(Theme.aurora) : AnyShapeStyle(Theme.indigo.opacity(0.1)),
                                in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                VStack(alignment: .leading, spacing: 6) {
                    Text(title).font(.headlineRounded).foregroundStyle(Theme.ink)
                    Text(detail).font(.subheadline).foregroundStyle(Theme.inkSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                    Label(time, systemImage: "clock")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Theme.indigo)
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right").font(.footnote.weight(.bold)).foregroundStyle(Theme.inkTertiary)
                    .padding(.top, 4)
            }
            .card(background: highlight ? Theme.surface : Theme.surface)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.radius, style: .continuous)
                    .strokeBorder(highlight ? Theme.indigo.opacity(0.45) : Color.clear, lineWidth: 1.5)
            )
        }
        .buttonStyle(.pressableCard)
    }
}
