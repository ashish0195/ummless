import AppIntents
import Foundation

/// Where an App Intent (Siri, Shortcuts, Spotlight, Action button) should take the person.
enum IntentRoute: String {
    case todaysMission, quickPractice, recordConversation, spar

    private static let key = "comlogue.pendingIntentRoute"
    static let notification = Notification.Name("comlogue.pendingIntentRoute")

    func enqueue() {
        UserDefaults.standard.set(rawValue, forKey: Self.key)
        NotificationCenter.default.post(name: Self.notification, object: nil)
    }

    static func dequeue() -> IntentRoute? {
        guard let raw = UserDefaults.standard.string(forKey: key) else { return nil }
        UserDefaults.standard.removeObject(forKey: key)
        return IntentRoute(rawValue: raw)
    }
}

struct StartTodaysMissionIntent: AppIntent {
    static var title: LocalizedStringResource = "Start today's mission"
    static var description = IntentDescription("Opens Comlogue on your next practice mission.")
    static var openAppWhenRun: Bool = true

    func perform() async throws -> some IntentResult {
        IntentRoute.todaysMission.enqueue()
        return .result()
    }
}

struct QuickPracticeIntent: AppIntent {
    static var title: LocalizedStringResource = "Two-minute practice"
    static var description = IntentDescription("Starts the short version of today's mission.")
    static var openAppWhenRun: Bool = true

    func perform() async throws -> some IntentResult {
        IntentRoute.quickPractice.enqueue()
        return .result()
    }
}

struct RecordConversationIntent: AppIntent {
    static var title: LocalizedStringResource = "Record a conversation"
    static var description = IntentDescription("Opens Comlogue ready to record a meeting or conversation. Everyone present must agree.")
    static var openAppWhenRun: Bool = true

    func perform() async throws -> some IntentResult {
        IntentRoute.recordConversation.enqueue()
        return .result()
    }
}

struct ComlogueShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: StartTodaysMissionIntent(),
            phrases: ["Start today's mission in \(.applicationName)", "Practice with \(.applicationName)"],
            shortTitle: "Today's mission",
            systemImageName: "play.circle.fill"
        )
        AppShortcut(
            intent: QuickPracticeIntent(),
            phrases: ["Quick practice in \(.applicationName)", "Two-minute practice with \(.applicationName)"],
            shortTitle: "2-minute practice",
            systemImageName: "timer"
        )
        AppShortcut(
            intent: RecordConversationIntent(),
            phrases: ["Record a conversation with \(.applicationName)", "Record my meeting in \(.applicationName)"],
            shortTitle: "Record a conversation",
            systemImageName: "record.circle"
        )
    }
}

extension AppModel {
    /// Opens whatever an App Intent asked for, once the app is ready.
    func handlePendingIntent() {
        guard phase == .ready, let route = IntentRoute.dequeue() else { return }
        switch route {
        case .todaysMission:
            if let today = course?.today, !today.mission.isLocked {
                present(.mission(id: today.mission.id, quick: false))
            } else {
                selectedTab = .today
            }
        case .quickPractice:
            if let quick = course?.today?.quick {
                present(.mission(id: quick.missionId, quick: true))
            } else {
                selectedTab = .today
            }
        case .recordConversation:
            present(.liveRecording)
        case .spar:
            selectedTab = .practice
        }
    }
}
