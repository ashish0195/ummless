import Foundation

struct AuthResponse: Codable, Sendable {
    let token: String
    let userId: String
    let isNew: Bool
}

struct DeviceAuthRequest: Codable, Sendable {
    let deviceId: String
    let platform: String
    let appVersion: String
}

struct HealthResponse: Codable, Sendable {
    let status: String
    let demoMode: Bool
    let version: String
}

struct LanguageOption: Codable, Hashable, Sendable, Identifiable {
    let code: String
    let name: String
    var id: String { code }
}

struct Track: Codable, Hashable, Sendable, Identifiable {
    let id: TrackId
    let title: String
    let subtitle: String
    let symbol: String
}

struct ChoiceOption: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let title: String
}

struct DimensionMeta: Codable, Hashable, Sendable, Identifiable {
    let id: DimensionId
    let title: String
    let description: String
    let symbol: String
    let colorHex: String
}

struct ActivityMeta: Codable, Hashable, Sendable, Identifiable {
    let id: ActivityId
    let title: String
    let prompt: String
    let durationLabel: String
    let suggestedSeconds: Int
    let dimensions: [DimensionId]
}

struct Pricing: Codable, Hashable, Sendable {
    let monthlyUsd: Double
    let yearlyUsd: Double
    let trialDays: Int
    let monthlyProductId: String
    let yearlyProductId: String
    let note: String
}

struct ConsentText: Codable, Hashable, Sendable {
    let version: String
    let title: String
    let body: String
    let bullets: [String]
}

struct Consents: Codable, Hashable, Sendable {
    let analysis: ConsentText
    let voiceReference: ConsentText
    let recording: ConsentText
}

struct Limits: Codable, Hashable, Sendable {
    let freeSparPerWeek: Int
    let freeTalks: Int
    let maxUploadMb: Int
    let maxRecordingMinutes: Int
}

struct Meta: Codable, Sendable {
    let demoMode: Bool
    let apiVersion: String
    let languages: [LanguageOption]
    let tracks: [Track]
    let contexts: [ChoiceOption]
    let easeTargets: [ChoiceOption]
    let dimensions: [DimensionMeta]
    let activities: [ActivityMeta]
    let assessmentEstimateMinutes: [Int]
    let voiceSetupEstimateMinutes: Int
    let pricing: Pricing
    let consents: Consents
    let limits: Limits

    func dimension(_ id: DimensionId) -> DimensionMeta? { dimensions.first { $0.id == id } }
    func activity(_ id: ActivityId) -> ActivityMeta? { activities.first { $0.id == id } }
    func track(_ id: TrackId?) -> Track? { tracks.first { $0.id == id } }
}

struct RegionOption: Codable, Hashable, Sendable, Identifiable {
    let code: String
    let name: String
    var id: String { code }
}

struct RecordingRules: Codable, Hashable, Sendable {
    let region: String
    let regionName: String
    let rule: String
    let headline: String
    let detail: String
    let policy: String
    let howToAsk: String
    let disclaimer: String
    let regions: [RegionOption]
}

struct APIErrorEnvelope: Codable, Sendable {
    struct Body: Codable, Sendable {
        let code: String
        let message: String
    }
    let error: Body
}
