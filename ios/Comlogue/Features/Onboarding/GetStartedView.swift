import SwiftUI

/// "How do you want to start?" — the last screen of the first-run walkthrough. Two clear choices: the guided
/// conversations that build a communication profile, or a one-minute practice for a quick first win. Real
/// conversations (upload or record) stay one tap away for people who have them.
struct GetStartedView: View {
    @Environment(AppModel.self) private var app
    var showsClose: Bool = true
    @State private var showRealConversation = false

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 0) {
                Text("How do you want to start?")
                    .font(.system(size: 34, weight: .bold, design: .rounded))
                    .foregroundStyle(Theme.ink)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 8)
                VStack(spacing: 14) {
                    RouteCard(
                        icon: "bubble.left.and.text.bubble.right.fill",
                        title: "Talk with your AI coach",
                        detail: "\(Formatting.minutesRange(app.meta?.assessmentEstimateMinutes ?? [10, 15])) · see what's working",
                        highlight: true
                    ) {
                        LocalFlags.hasSeenFirstRun = true
                        app.present(.guidedAssessment(resumeId: LocalFlags.activeAssessmentId))
                    }
                    RouteCard(
                        icon: "bolt.fill",
                        title: "Try a 1-minute practice",
                        detail: "A quick first win",
                        highlight: false
                    ) {
                        LocalFlags.hasSeenFirstRun = true
                        app.present(.daily(date: nil))
                    }
                }
                .padding(.top, 28)
                Button("Use a real conversation instead") { showRealConversation = true }
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Theme.indigo)
                    .frame(maxWidth: .infinity)
                    .padding(.top, 22)
                Spacer()
                Button("Skip for now") { skip() }
                    .buttonStyle(.ghostPill)
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.bottom, 12)
            .screenBackground()
            .toolbar {
                if showsClose {
                    ToolbarItem(placement: .topBarTrailing) {
                        CircleIconButton(systemName: "xmark") { skip() }
                    }
                }
            }
            .confirmationDialog("Use a real conversation", isPresented: $showRealConversation, titleVisibility: .visible) {
                Button("Upload a recording") {
                    LocalFlags.hasSeenFirstRun = true
                    app.present(.upload)
                }
                Button("Record a conversation") {
                    LocalFlags.hasSeenFirstRun = true
                    app.present(.liveRecording)
                }
            } message: {
                Text("Everyone in the recording needs to agree to it.")
            }
        }
    }

    private func skip() {
        LocalFlags.hasSeenFirstRun = true
        app.dismissFlow()
        Task {
            var patch = MePatch()
            patch.onboarding = MePatch.OnboardingPatch(courseStarted: true)
            try? await app.updateMe(patch)
        }
    }
}

private struct RouteCard: View {
    let icon: String
    let title: String
    let detail: String
    let highlight: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 16) {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundStyle(highlight ? Color.white : Theme.indigo)
                    .frame(width: 56, height: 56)
                    .background(highlight ? AnyShapeStyle(Theme.aurora) : AnyShapeStyle(Theme.indigo.opacity(0.1)),
                                in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                VStack(alignment: .leading, spacing: 4) {
                    Text(title).font(.headlineRounded).foregroundStyle(Theme.ink)
                    Text(detail).font(.subheadline).foregroundStyle(Theme.inkSecondary)
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right").font(.footnote.weight(.bold)).foregroundStyle(Theme.inkTertiary)
            }
            .padding(18)
            .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.radius, style: .continuous)
                    .strokeBorder(highlight ? Theme.indigo.opacity(0.5) : Theme.stroke, lineWidth: highlight ? 2 : 1)
            )
        }
        .buttonStyle(.pressableCard)
    }
}
