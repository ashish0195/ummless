import Foundation

struct Onboarding: Codable, Hashable, Sendable {
    let completed: Bool
    let contextsRanked: [String]
    let easeTargets: [String]
    let goalTrack: TrackId?
    let language: String
    let region: String?
    let analysisConsentVersion: String?
    let analysisConsentedAt: Date?
    let ageConfirmed: Bool?

    var hasAnalysisConsent: Bool { analysisConsentVersion != nil }
}

struct PracticeSettings: Codable, Hashable, Sendable {
    let weeklyTarget: Int
    let reminderTime: String?
    let reminderDays: [Int]
    /// "After my morning chai or coffee" — the routine practice is attached to.
    let anchor: String?
    /// A planned break ("YYYY-MM-DD", local). Reminders and nudges pause; the weekly run is kept.
    let pausedUntil: String?

    func isPaused(on day: String) -> Bool {
        guard let pausedUntil else { return false }
        return day <= pausedUntil
    }
}

/// Which notifications the person wants, and their quiet hours. Mirrors the server's settings.
struct NotificationSettings: Codable, Hashable, Sendable {
    var practiceReminders: Bool
    var eventPrep: Bool
    var results: Bool
    var checkIns: Bool
    var nudges: Bool
    var weeklyReveal: Bool
    var tips: Bool
    var quietStart: String
    var quietEnd: String

    static let defaults = NotificationSettings(practiceReminders: true, eventPrep: true, results: true, checkIns: true,
                                               nudges: true, weeklyReveal: true, tips: false,
                                               quietStart: "22:00", quietEnd: "08:00")
}

struct VoiceReference: Codable, Hashable, Sendable {
    let status: String
    let createdAt: Date?
    let durationSeconds: Double?
    let consentVersion: String?

    var isActive: Bool { status == "active" }
}

struct Entitlement: Codable, Hashable, Sendable {
    let tier: String
    let expiresAt: Date?
    let source: String
    let productId: String?

    var isPro: Bool { tier == "pro" }
}

struct Me: Codable, Sendable {
    let userId: String
    let createdAt: Date
    let demoMode: Bool
    let onboarding: Onboarding
    let practiceSettings: PracticeSettings
    let voiceReference: VoiceReference
    let entitlement: Entitlement
    let hasResults: Bool
    let nextStep: String
    // v2
    let market: Market?
    let timezone: String?
    let notificationSettings: NotificationSettings?

    var resolvedMarket: Market { market ?? .global }
    var resolvedNotificationSettings: NotificationSettings { notificationSettings ?? .defaults }
}

/// PATCH /v1/me body. Nil fields are omitted by the encoder, so only changed values are sent.
struct MePatch: Codable, Sendable {
    struct OnboardingPatch: Codable, Sendable {
        var completed: Bool?
        var contextsRanked: [String]?
        var easeTargets: [String]?
        var goalTrack: String?
        var language: String?
        var region: String?
        var analysisConsentVersion: String?
        var courseStarted: Bool?
        var ageConfirmed: Bool?
    }

    struct PracticePatch: Codable, Sendable {
        var weeklyTarget: Int?
        var reminderTime: String?
        var reminderDays: [Int]?
        var anchor: String?
        var pausedUntil: String?
        /// Sends an explicit `"paused_until": null` to end a break.
        var endsBreak = false

        private enum CodingKeys: String, CodingKey {
            case weeklyTarget, reminderTime, reminderDays, anchor, pausedUntil
        }

        init(weeklyTarget: Int? = nil, reminderTime: String? = nil, reminderDays: [Int]? = nil, anchor: String? = nil,
             pausedUntil: String? = nil, endsBreak: Bool = false) {
            self.weeklyTarget = weeklyTarget
            self.reminderTime = reminderTime
            self.reminderDays = reminderDays
            self.anchor = anchor
            self.pausedUntil = pausedUntil
            self.endsBreak = endsBreak
        }

        init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            weeklyTarget = try container.decodeIfPresent(Int.self, forKey: .weeklyTarget)
            reminderTime = try container.decodeIfPresent(String.self, forKey: .reminderTime)
            reminderDays = try container.decodeIfPresent([Int].self, forKey: .reminderDays)
            anchor = try container.decodeIfPresent(String.self, forKey: .anchor)
            pausedUntil = try container.decodeIfPresent(String.self, forKey: .pausedUntil)
        }

        func encode(to encoder: Encoder) throws {
            var container = encoder.container(keyedBy: CodingKeys.self)
            try container.encodeIfPresent(weeklyTarget, forKey: .weeklyTarget)
            try container.encodeIfPresent(reminderTime, forKey: .reminderTime)
            try container.encodeIfPresent(reminderDays, forKey: .reminderDays)
            try container.encodeIfPresent(anchor, forKey: .anchor)
            if endsBreak {
                try container.encodeNil(forKey: .pausedUntil)
            } else {
                try container.encodeIfPresent(pausedUntil, forKey: .pausedUntil)
            }
        }
    }

    struct NotificationPatch: Codable, Sendable {
        var practiceReminders: Bool?
        var eventPrep: Bool?
        var results: Bool?
        var checkIns: Bool?
        var nudges: Bool?
        var weeklyReveal: Bool?
        var tips: Bool?
        var quietStart: String?
        var quietEnd: String?

        init(_ settings: NotificationSettings) {
            practiceReminders = settings.practiceReminders
            eventPrep = settings.eventPrep
            results = settings.results
            checkIns = settings.checkIns
            nudges = settings.nudges
            weeklyReveal = settings.weeklyReveal
            tips = settings.tips
            quietStart = settings.quietStart
            quietEnd = settings.quietEnd
        }
    }

    var onboarding: OnboardingPatch?
    var practiceSettings: PracticePatch?
    var notificationSettings: NotificationPatch?
}

struct VoiceEnrollmentResult: Codable, Sendable {
    let status: String
    let issues: [Issue]
    let message: String
    let reference: VoiceReference

    var accepted: Bool { status == "active" }
}

struct AppStoreTransactionRequest: Codable, Sendable {
    let signedTransaction: String
}

struct DevGrantRequest: Codable, Sendable {
    let tier: String
}
