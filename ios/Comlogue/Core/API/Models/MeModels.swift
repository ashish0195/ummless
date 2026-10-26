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

    var hasAnalysisConsent: Bool { analysisConsentVersion != nil }
}

struct PracticeSettings: Codable, Hashable, Sendable {
    let weeklyTarget: Int
    let reminderTime: String?
    let reminderDays: [Int]
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
    }

    struct PracticePatch: Codable, Sendable {
        var weeklyTarget: Int?
        var reminderTime: String?
        var reminderDays: [Int]?
    }

    var onboarding: OnboardingPatch?
    var practiceSettings: PracticePatch?
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
