#if DEBUG
import Foundation

/// Debug-only: launch with `-ComlogueScreenshotScene <scene>` against a backend that allows dev tools to
/// open a specific screen with seeded demo data. Used by CI to capture real simulator screenshots.
enum ScreenshotScene: String, CaseIterable {
    case welcome, getStarted, activity, spar, results, recording, debrief, today, course, mission, practice, you, paywall

    static var current: ScreenshotScene? {
        UserDefaults.standard.string(forKey: "ComlogueScreenshotScene").flatMap(ScreenshotScene.init(rawValue:))
    }
}

extension AppModel {
    /// Sets up a fresh demo account and navigates to `scene`.
    func runScreenshotScene(_ scene: ScreenshotScene) async {
        DeviceIdentity.reset()
        LocalFlags.reset()
        api.token = nil
        LocalFlags.hasSeenFirstRun = true
        guard await authenticate() else {
            phase = .failed("Screenshot mode couldn't reach the server at \(AppConfig.baseURL.absoluteString).")
            return
        }
        meta = try? await api.meta()
        if scene == .welcome {
            me = try? await api.me()
            phase = .onboarding
            return
        }
        let seed = try? await api.seedDemo(pro: scene == .mission)
        me = try? await api.me()
        phase = .ready
        await refreshAll()
        switch scene {
        case .welcome:
            break
        case .getStarted:
            activeFlow = .getStarted
        case .activity:
            activeFlow = .gapFill(activityId: "respond_to_someone")
        case .spar:
            activeFlow = .spar(SparLaunch(title: "Skeptical CFO", personaId: "skeptical_cfo", customScenario: nil,
                                          difficulty: .brutal, eventId: nil, prepId: nil))
        case .results:
            if let id = seed?.assessmentId { activeFlow = .guidedAssessment(resumeId: id) }
        case .recording:
            if let id = seed?.recordingNeedsConfirmationId { activeFlow = .recordingDetail(id: id) }
        case .debrief:
            if let id = seed?.recordingCompleteId { activeFlow = .recordingDetail(id: id) }
        case .today:
            selectedTab = .today
        case .course:
            selectedTab = .course
        case .mission:
            if let id = seed?.missionId { activeFlow = .mission(id: id, quick: false) }
        case .practice:
            selectedTab = .practice
        case .you:
            selectedTab = .you
        case .paywall:
            activeFlow = .paywall
        }
    }
}
#endif
