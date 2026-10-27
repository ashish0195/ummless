import Foundation
import UIKit
import UserNotifications

/// Deep links waiting for the app to be ready (e.g. a notification tapped at cold start). Persisted briefly so a
/// tap that launches the app isn't lost while it signs in.
enum PendingLink {
    private static let linkKey = "comlogue.pendingLink"
    private static let notificationKey = "comlogue.pendingLinkNotification"
    static let posted = Notification.Name("comlogue.pendingLink")

    static func enqueue(_ link: DeepLink, notificationId: String? = nil) {
        UserDefaults.standard.set(link.url.absoluteString, forKey: linkKey)
        UserDefaults.standard.set(notificationId, forKey: notificationKey)
        NotificationCenter.default.post(name: posted, object: nil)
    }

    static func dequeue() -> (link: DeepLink, notificationId: String?)? {
        defer {
            UserDefaults.standard.removeObject(forKey: linkKey)
            UserDefaults.standard.removeObject(forKey: notificationKey)
        }
        guard let raw = UserDefaults.standard.string(forKey: linkKey), let link = DeepLink(string: raw) else { return nil }
        return (link, UserDefaults.standard.string(forKey: notificationKey))
    }
}

/// Permission, categories, APNs registration, local scheduling and the badge.
@MainActor
@Observable
final class NotificationManager: NSObject {
    static let shared = NotificationManager()

    private(set) var status: UNAuthorizationStatus = .notDetermined
    /// Hex APNs token. Remembered across launches: the server replaces its copy with whatever the app reports, and
    /// iOS only hands the token over again a moment after `registerForRemoteNotifications()`.
    private(set) var deviceToken: String? = UserDefaults.standard.string(forKey: NotificationManager.tokenKey)
    private static let tokenKey = "comlogue.apnsToken"
    /// Called when a new APNs token arrives so the app can register it with the server.
    var onTokenChange: (() -> Void)?
    /// The person's quiet hours, kept for "Remind me later" (set whenever reminders are rescheduled).
    var settings = NotificationSettings.defaults

    private let center = UNUserNotificationCenter.current()

    enum Category {
        static let dailyRep = "DAILY_REP"
        static let eventPrep = "EVENT_PREP"
        static let checkIn = "CHECK_IN"
    }

    enum Action {
        static let startRep = "START_REP"
        static let remindLater = "REMIND_LATER"
        static let warmUp = "WARM_UP"
        static let reflect = "REFLECT"
    }

    /// The server's name for the current permission state.
    var authorizationName: String {
        switch status {
        case .authorized: return "authorized"
        case .provisional: return "provisional"
        case .ephemeral: return "ephemeral"
        case .denied: return "denied"
        default: return "not_determined"
        }
    }

    /// Notifications can be delivered (quietly, for provisional).
    var canDeliver: Bool { [.authorized, .provisional, .ephemeral].contains(status) }
    var isDenied: Bool { status == .denied }
    var isQuiet: Bool { status == .provisional }

    // MARK: Permission

    func refreshStatus() async {
        status = await center.notificationSettings().authorizationStatus
    }

    /// The system prompt. Only asked after we've explained what the reminders are for.
    @discardableResult
    func requestFull() async -> Bool {
        let granted = (try? await center.requestAuthorization(options: [.alert, .sound, .badge])) ?? false
        await refreshStatus()
        if granted { registerForRemote() }
        return granted
    }

    /// Quiet delivery to Notification Center without a prompt; the person can keep or turn them off from there.
    func requestProvisional() async {
        _ = try? await center.requestAuthorization(options: [.alert, .sound, .badge, .provisional])
        await refreshStatus()
        if canDeliver { registerForRemote() }
    }

    func registerForRemote() {
        UIApplication.shared.registerForRemoteNotifications()
    }

    /// Apple asks apps to register at every launch because the token can change. Never prompts: it only registers
    /// once the person has allowed notifications.
    func registerIfAllowed() async {
        await refreshStatus()
        if canDeliver { registerForRemote() }
    }

    func didRegister(token: Data) {
        let hex = token.map { String(format: "%02x", $0) }.joined()
        guard hex != deviceToken else { return }
        deviceToken = hex
        UserDefaults.standard.set(hex, forKey: Self.tokenKey)
        onTokenChange?()
    }

    func registerCategories() {
        let start = UNNotificationAction(identifier: Action.startRep, title: "Start now", options: [.foreground])
        let later = UNNotificationAction(identifier: Action.remindLater, title: "Remind me later", options: [])
        let warmUp = UNNotificationAction(identifier: Action.warmUp, title: "Warm up now", options: [.foreground])
        let reflect = UNNotificationAction(identifier: Action.reflect, title: "Reflect now", options: [.foreground])
        center.setNotificationCategories([
            UNNotificationCategory(identifier: Category.dailyRep, actions: [start, later], intentIdentifiers: []),
            UNNotificationCategory(identifier: Category.eventPrep, actions: [warmUp], intentIdentifiers: []),
            UNNotificationCategory(identifier: Category.checkIn, actions: [reflect], intentIdentifiers: []),
        ])
    }

    func setBadge(_ count: Int) {
        center.setBadgeCount(max(0, count)) { _ in }
    }

    // MARK: Local schedule

    /// Replaces every reminder the app scheduled before with `plan`.
    func apply(_ plan: [LocalNotification]) async {
        let pending = await center.pendingNotificationRequests()
        let ours = pending.map(\.identifier).filter { $0.hasPrefix(NotificationPlanner.identifierPrefix) }
        center.removePendingNotificationRequests(withIdentifiers: ours)
        guard canDeliver else { return }
        for item in plan {
            let content = UNMutableNotificationContent()
            content.title = item.title
            content.body = item.body
            content.sound = .default
            content.threadIdentifier = item.threadId
            content.userInfo = ["deep_link": item.deepLink.url.absoluteString]
            switch item.kind {
            case .practice, .nudge: content.categoryIdentifier = Category.dailyRep
            case .eventPrep: content.categoryIdentifier = Category.eventPrep
            case .checkIn: content.categoryIdentifier = Category.checkIn
            case .weeklyReveal: break
            }
            content.interruptionLevel = item.kind == .nudge ? .passive : .active
            let parts = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: item.fireDate)
            let trigger = UNCalendarNotificationTrigger(dateMatching: parts, repeats: false)
            try? await center.add(UNNotificationRequest(identifier: item.id, content: content, trigger: trigger))
        }
    }

    func removeAllLocal() async {
        let pending = await center.pendingNotificationRequests()
        center.removePendingNotificationRequests(
            withIdentifiers: pending.map(\.identifier).filter { $0.hasPrefix(NotificationPlanner.identifierPrefix) })
    }

    /// "Remind me later" on a reminder: one more nudge in about two hours (outside quiet hours), then it's the
    /// person's call.
    private func remindLater(_ content: UNNotificationContent) {
        let copy = (content.mutableCopy() as? UNMutableNotificationContent) ?? UNMutableNotificationContent()
        let now = Date()
        let fireDate = NotificationPlanner.snoozeDate(now: now, settings: settings, timeZone: .current)
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: max(60, fireDate.timeIntervalSince(now)), repeats: false)
        let request = UNNotificationRequest(identifier: NotificationPlanner.identifierPrefix + "later.\(Int(Date().timeIntervalSince1970))",
                                            content: copy, trigger: trigger)
        center.add(request) { _ in }
    }

    fileprivate func handle(action: String, link: DeepLink?, notificationId: String?, content: UNNotificationContent) {
        switch action {
        case Action.remindLater:
            remindLater(content)
        case UNNotificationDismissActionIdentifier:
            break
        default:
            PendingLink.enqueue(link ?? .today, notificationId: notificationId)
        }
    }
}

extension NotificationManager: UNUserNotificationCenterDelegate {
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
                                            willPresent notification: UNNotification) async -> UNNotificationPresentationOptions {
        [.banner, .list, .sound]
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
                                            didReceive response: UNNotificationResponse) async {
        let content = response.notification.request.content
        let link = (content.userInfo["deep_link"] as? String).flatMap(DeepLink.init(string:))
        let notificationId = content.userInfo["notification_id"] as? String
        let action = response.actionIdentifier
        await MainActor.run {
            NotificationManager.shared.handle(action: action, link: link, notificationId: notificationId, content: content)
        }
    }
}

/// Receives the APNs token and sets up notification handling before any notification can arrive.
@MainActor
final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        UNUserNotificationCenter.current().delegate = NotificationManager.shared
        NotificationManager.shared.registerCategories()
        Task { await NotificationManager.shared.registerIfAllowed() }
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        NotificationManager.shared.didRegister(token: deviceToken)
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        // Push is a nice-to-have: local reminders and the in-app inbox keep working.
    }
}
