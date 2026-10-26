import Foundation
import UIKit
import UserNotifications

enum Haptics {
    static func tap() { UIImpactFeedbackGenerator(style: .light).impactOccurred() }
    static func press() { UIImpactFeedbackGenerator(style: .medium).impactOccurred() }
    static func success() { UINotificationFeedbackGenerator().notificationOccurred(.success) }
    static func warning() { UINotificationFeedbackGenerator().notificationOccurred(.warning) }
    static func selection() { UISelectionFeedbackGenerator().selectionChanged() }
}

/// Optional, user-chosen practice reminders. Gentle copy; missing a day is fine.
enum ReminderScheduler {
    private static let identifierPrefix = "comlogue.reminder."

    static func requestAuthorization() async -> Bool {
        let center = UNUserNotificationCenter.current()
        do {
            return try await center.requestAuthorization(options: [.alert, .sound, .badge])
        } catch {
            return false
        }
    }

    /// - Parameters:
    ///   - days: 1 = Monday … 7 = Sunday (API convention).
    ///   - time: "HH:mm".
    static func schedule(days: [Int], time: String) async {
        cancelAll()
        guard !days.isEmpty else { return }
        let parts = time.split(separator: ":").compactMap { Int($0) }
        guard parts.count == 2 else { return }
        let center = UNUserNotificationCenter.current()
        let messages = [
            "Your next mission takes about 6 minutes. Ready when you are.",
            "One small change today. Want to try it?",
            "Two minutes of practice still counts. Jump back in?",
        ]
        for (offset, day) in days.enumerated() {
            var components = DateComponents()
            components.weekday = day == 7 ? 1 : day + 1 // Calendar: 1 = Sunday
            components.hour = parts[0]
            components.minute = parts[1]
            let content = UNMutableNotificationContent()
            content.title = "Time to practice"
            content.body = messages[offset % messages.count]
            content.sound = .default
            let trigger = UNCalendarNotificationTrigger(dateMatching: components, repeats: true)
            let request = UNNotificationRequest(identifier: identifierPrefix + "\(day)", content: content, trigger: trigger)
            try? await center.add(request)
        }
    }

    static func cancelAll() {
        let center = UNUserNotificationCenter.current()
        let ids = (1...7).map { identifierPrefix + "\($0)" }
        center.removePendingNotificationRequests(withIdentifiers: ids)
    }
}

/// Region for recording-rules guidance. Derived from device settings (no location permission needed)
/// and refined by the person (e.g. picking their US state).
enum RegionPreference {
    private static let key = "comlogue.recordingRegion"

    static var stored: String? {
        get { UserDefaults.standard.string(forKey: key) }
        set { UserDefaults.standard.set(newValue, forKey: key) }
    }

    static var deviceCountry: String? { Locale.current.region?.identifier }

    static var best: String? { stored ?? deviceCountry }
}

/// Small persisted UI flags.
enum LocalFlags {
    private static let defaults = UserDefaults.standard

    static var declinedVoiceReference: Bool {
        get { defaults.bool(forKey: "comlogue.declinedVoiceReference") }
        set { defaults.set(newValue, forKey: "comlogue.declinedVoiceReference") }
    }

    static var hasSeenFirstRun: Bool {
        get { defaults.bool(forKey: "comlogue.hasSeenFirstRun") }
        set { defaults.set(newValue, forKey: "comlogue.hasSeenFirstRun") }
    }

    static var activeAssessmentId: String? {
        get { defaults.string(forKey: "comlogue.activeAssessmentId") }
        set { defaults.set(newValue, forKey: "comlogue.activeAssessmentId") }
    }

    static var pendingRecordingIds: [String] {
        get { defaults.stringArray(forKey: "comlogue.pendingRecordingIds") ?? [] }
        set { defaults.set(newValue, forKey: "comlogue.pendingRecordingIds") }
    }

    static func reset() {
        for key in ["comlogue.declinedVoiceReference", "comlogue.hasSeenFirstRun", "comlogue.activeAssessmentId",
                    "comlogue.pendingRecordingIds", "comlogue.recordingRegion"] {
            defaults.removeObject(forKey: key)
        }
    }
}
