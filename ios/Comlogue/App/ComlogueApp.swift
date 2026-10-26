import SwiftUI

@main
struct ComlogueApp: App {
    @State private var app = AppModel()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(app)
                .tint(Theme.indigo)
        }
    }
}

struct RootView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        @Bindable var app = app
        ZStack(alignment: .top) {
            Group {
                switch app.phase {
                case .launching:
                    SplashView()
                case .onboarding:
                    OnboardingFlowView()
                case .ready:
                    MainTabView()
                case .failed(let message):
                    ConnectionProblemView(message: message)
                }
            }
            .transition(.opacity)

            if let toast = app.toast {
                ToastView(message: toast)
                    .padding(.top, 8)
                    .transition(.move(edge: .top).combined(with: .opacity))
                    .zIndex(1)
            }
        }
        .animation(.easeInOut(duration: 0.3), value: app.phase)
        .animation(.spring(response: 0.35, dampingFraction: 0.85), value: app.toast)
        .fullScreenCover(item: $app.activeFlow) { flow in
            FlowHost(flow: flow)
                .environment(app)
        }
        .task {
            if app.phase == .launching { await app.bootstrap() }
        }
        .onReceive(NotificationCenter.default.publisher(for: IntentRoute.notification)) { _ in
            app.handlePendingIntent()
        }
        .onChange(of: app.phase) { _, newPhase in
            if newPhase == .ready { app.handlePendingIntent() }
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active { app.handlePendingIntent() }
        }
    }
}

struct MainTabView: View {
    @Environment(AppModel.self) private var app

    var body: some View {
        @Bindable var app = app
        TabView(selection: $app.selectedTab) {
            TodayView()
                .tabItem { Label("Today", systemImage: "sun.horizon.fill") }
                .tag(AppTab.today)
            CourseView()
                .tabItem { Label("Course", systemImage: "map.fill") }
                .tag(AppTab.course)
            PracticeHubView()
                .tabItem { Label("Practice", systemImage: "waveform") }
                .tag(AppTab.practice)
            YouView()
                .tabItem { Label("You", systemImage: "person.crop.circle.fill") }
                .tag(AppTab.you)
        }
        .tint(Theme.indigo)
    }
}

/// Routes each full-screen flow to its view.
struct FlowHost: View {
    @Environment(AppModel.self) private var app
    let flow: AppFlow

    var body: some View {
        switch flow {
        case .getStarted:
            GetStartedView()
        case .guidedAssessment(let resumeId):
            AssessmentFlowView(purpose: .baseline(resumeId: resumeId))
        case .gapFill(let activityId):
            AssessmentFlowView(purpose: .gapFill(activityId: activityId))
        case .upload:
            UploadFlowView()
        case .liveRecording:
            LiveRecordingFlowView()
        case .recordingDetail(let id):
            NavigationStack {
                RecordingDetailView(recordingId: id, isRoot: true)
            }
        case .voiceSetup:
            NavigationStack {
                VoiceSetupView(mode: .standalone) { _ in app.dismissFlow() }
            }
        case .mission(let id, let quick):
            NavigationStack {
                MissionView(missionId: id, autoStartQuick: quick, isRoot: true)
            }
        case .spar(let launch):
            SparFlowView(launch: launch)
        case .paywall:
            PaywallView { app.dismissFlow() }
        case .weeklyReview:
            NavigationStack {
                WeeklyReviewView(isRoot: true)
            }
        }
    }
}

struct SplashView: View {
    var body: some View {
        VStack(spacing: 20) {
            VoiceOrb(level: 0.2).frame(width: 140, height: 140)
            Text(Brand.name).font(.displayLarge).foregroundStyle(Theme.ink)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .screenBackground()
    }
}

struct ConnectionProblemView: View {
    @Environment(AppModel.self) private var app
    let message: String
    @State private var showServerSheet = false

    var body: some View {
        VStack(spacing: 18) {
            Spacer()
            VoiceOrb(level: 0.05, colors: [Theme.inkTertiary, Theme.stroke, Theme.inkSecondary]).frame(width: 110, height: 110)
            Text("We can't reach Comlogue").font(.titleRounded).foregroundStyle(Theme.ink)
            Text(message).font(.body).foregroundStyle(Theme.inkSecondary).multilineTextAlignment(.center)
            Text("Server: \(AppConfig.baseURL.absoluteString)").font(.caption).foregroundStyle(Theme.inkTertiary)
            Spacer()
            Button("Try again") { Task { await app.bootstrap() } }.buttonStyle(.primaryPill)
            Button("Change server") { showServerSheet = true }.buttonStyle(.ghostPill)
        }
        .padding(Theme.gutter)
        .screenBackground()
        .sheet(isPresented: $showServerSheet) {
            ServerSettingsSheet()
                .environment(app)
        }
    }
}

struct ToastView: View {
    let message: String

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "checkmark.circle.fill").foregroundStyle(Theme.mint)
            Text(message).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
        }
        .padding(.vertical, 12)
        .padding(.horizontal, 18)
        .background(.regularMaterial, in: Capsule())
        .shadow(color: .black.opacity(0.12), radius: 12, y: 6)
    }
}
