#if DEBUG
import Foundation

/// Debug-only: launch with `-ComlogueScreenshotScene <scene>` against a backend that allows dev tools to
/// open a specific screen with seeded demo data. Used by CI to capture real simulator screenshots.
enum ScreenshotScene: String, CaseIterable {
    case welcome, goal, getStarted, activity, spar, results, recording, debrief, today, course, mission, practice, you, paywall
    // The habit loop, notifications and group conversations
    case daily, dailyFeedback, inbox, notifications, plan, group, groupReport
    // The India market
    case todayIndia, practiceIndia, paywallIndia, groupIndia, planIndia, consentIndia

    /// Scenes seeded as an Indian account.
    var market: Market {
        switch self {
        case .todayIndia, .practiceIndia, .paywallIndia, .groupIndia, .planIndia, .consentIndia: return .in
        default: return .us
        }
    }

    /// Scenes that show a step of onboarding instead of a seeded account.
    var onboardingStep: OnboardingModel.Step? {
        switch self {
        case .welcome: return .welcome
        case .goal: return .goal
        case .planIndia: return .reminder
        case .consentIndia: return .consent
        default: return nil
        }
    }

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
        // Onboarding reads the device region until the server has one.
        RegionPreference.stored = scene.market == .in ? "IN" : "US"
        guard await authenticate() else {
            phase = .failed("Screenshot mode couldn't reach the server at \(AppConfig.baseURL.absoluteString).")
            return
        }
        meta = try? await api.meta()
        if scene.onboardingStep != nil {
            me = try? await api.me()
            phase = .onboarding
            return
        }
        // The mission, the Brutal sparring partner and group conversations are Pro content; every other scene shows
        // the free tier.
        let pro: Bool
        switch scene {
        case .mission, .spar, .group, .groupReport, .groupIndia: pro = true
        default: pro = false
        }
        let seed = try? await api.seedDemo(pro: pro, market: scene.market)
        me = try? await api.me()
        phase = .ready
        await refreshAll()
        switch scene {
        case .welcome, .goal, .planIndia, .consentIndia:
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
        case .today, .todayIndia:
            selectedTab = .today
        case .course:
            selectedTab = .course
        case .mission:
            if let id = seed?.missionId { activeFlow = .mission(id: id, quick: false) }
        case .practice, .practiceIndia:
            selectedTab = .practice
        case .you:
            selectedTab = .you
        case .paywall, .paywallIndia:
            activeFlow = .paywall
        case .daily:
            activeFlow = .daily(date: nil)
        case .dailyFeedback:
            activeFlow = .daily(date: seed?.previousDailyDate)
        case .inbox:
            activeFlow = .inbox
        case .notifications:
            activeFlow = .notificationSettings
        case .plan:
            activeFlow = .practicePlan
        case .group, .groupIndia:
            if let id = seed?.panelId ?? panels.first?.id { activeFlow = .group(panelId: id) }
        case .groupReport:
            if let id = seed?.groupConversationId {
                let isPanel = panels.first { $0.id == seed?.panelId }?.isGroupDiscussion == false
                activeFlow = .report(conversationId: id, title: isPanel ? "Interview report" : "Discussion report")
            }
        }
    }
}

extension OnboardingModel {
    /// Jumps to the step a screenshot scene shows, with plausible answers filled in.
    func applyScreenshotScene(market: Market) {
        guard let scene = ScreenshotScene.current, let step = scene.onboardingStep, step != .welcome else { return }
        goalTrack = market == .in ? "interviews" : "business"
        routineId = "morning"
        ageConfirmed = step == .consent
        self.step = step
    }
}
#endif
