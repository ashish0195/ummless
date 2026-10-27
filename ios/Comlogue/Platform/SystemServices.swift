import Foundation
import UIKit

enum Haptics {
    static func tap() { UIImpactFeedbackGenerator(style: .light).impactOccurred() }
    static func press() { UIImpactFeedbackGenerator(style: .medium).impactOccurred() }
    static func success() { UINotificationFeedbackGenerator().notificationOccurred(.success) }
    static func warning() { UINotificationFeedbackGenerator().notificationOccurred(.warning) }
    static func selection() { UISelectionFeedbackGenerator().selectionChanged() }
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

    /// Milestones already celebrated. `nil` until the first refresh, which records existing ones silently.
    static var seenMilestones: Set<String>? {
        get { defaults.stringArray(forKey: "comlogue.seenMilestones").map(Set.init) }
        set { defaults.set(newValue.map { Array($0).sorted() }, forKey: "comlogue.seenMilestones") }
    }

    /// The reminder explainer was shown once (we never ask twice unprompted).
    static var notificationPrimingShown: Bool {
        get { defaults.bool(forKey: "comlogue.notificationPrimingShown") }
        set { defaults.set(newValue, forKey: "comlogue.notificationPrimingShown") }
    }

    static func reset() {
        for key in ["comlogue.declinedVoiceReference", "comlogue.hasSeenFirstRun", "comlogue.activeAssessmentId",
                    "comlogue.pendingRecordingIds", "comlogue.recordingRegion", "comlogue.seenMilestones",
                    "comlogue.notificationPrimingShown"] {
            defaults.removeObject(forKey: key)
        }
    }
}
