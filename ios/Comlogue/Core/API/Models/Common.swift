import Foundation

// Shared API types. Field names mirror docs/API.md in camelCase; the decoder converts from snake_case.
// Enums that the server may extend decode unknown values to a safe fallback instead of failing.

typealias ActivityId = String
typealias TrackId = String

enum DimensionId: String, Codable, CaseIterable, Hashable, Sendable, Identifiable {
    case clarity, structure, listening, warmth, persuasion, concision, storytelling

    var id: String { rawValue }
}

enum DimensionStatus: String, Codable, Hashable, Sendable {
    case assessed
    case provisional
    case notEnoughEvidence = "not_enough_evidence"
    case notAssessed = "not_assessed"

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = DimensionStatus(rawValue: raw) ?? .notAssessed
    }

    /// Whether this status carries a level that can be drawn on the communication web.
    var hasLevel: Bool { self == .assessed || self == .provisional }
}

enum Confidence: String, Codable, Hashable, Sendable {
    case low, moderate, high

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = Confidence(rawValue: raw) ?? .low
    }
}

enum Usable: String, Codable, Hashable, Sendable {
    case yes, partly, no

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = Usable(rawValue: raw) ?? .partly
    }
}

enum Difficulty: String, Codable, CaseIterable, Hashable, Sendable, Identifiable {
    case kind, real, brutal

    var id: String { rawValue }

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = Difficulty(rawValue: raw) ?? .real
    }
}

enum MissionType: String, Codable, Hashable, Sendable {
    case learnAndTry = "learn_and_try"
    case remix
    case realLife = "real_life"
    case weeklyReveal = "weekly_reveal"

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = MissionType(rawValue: raw) ?? .learnAndTry
    }
}

enum IssueSeverity: String, Codable, Hashable, Sendable {
    case blocking, warning

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = IssueSeverity(rawValue: raw) ?? .warning
    }
}

struct Issue: Codable, Hashable, Sendable, Identifiable {
    let code: String
    let title: String
    let detail: String
    let severity: IssueSeverity

    var id: String { code + title }
}

struct Partner: Codable, Hashable, Sendable {
    let name: String
    let role: String
    let voice: String
    let symbol: String
    let colorHex: String
}

enum TurnSpeaker: String, Codable, Hashable, Sendable {
    case partner, user

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = TurnSpeaker(rawValue: raw) ?? .partner
    }
}

struct TurnQuality: Codable, Hashable, Sendable {
    let usable: Usable
    let issues: [Issue]
    let speechSeconds: Double
    let durationSeconds: Double
}

struct Turn: Codable, Hashable, Sendable, Identifiable {
    let index: Int
    let speaker: TurnSpeaker
    let text: String
    let audioUrl: String?
    let createdAt: Date
    let quality: TurnQuality?
    let coachWhisper: String?
    let excluded: Bool

    var id: Int { index }
}

struct EvidenceMoment: Codable, Hashable, Sendable {
    let quote: String
    let note: String?
    let sourceType: String
    let sourceId: String
    let turnIndex: Int?
    let startSeconds: Double?
    let endSeconds: Double?
    let audioUrl: String?
}

struct NextStep: Codable, Hashable, Sendable {
    let type: String
    let activityId: ActivityId
    let title: String
    let minutes: Int
}

struct DimensionResult: Codable, Hashable, Sendable, Identifiable {
    let dimension: DimensionId
    let title: String
    let status: DimensionStatus
    let level: Int?
    let levelLabel: String?
    let confidence: Confidence?
    let summary: String?
    let strengths: [String]
    let oneChange: String?
    let evidence: [EvidenceMoment]
    let missingReason: String?
    let nextStep: NextStep?
    let assessedAt: Date?
    let contextLabel: String?

    var id: DimensionId { dimension }

    /// A level is only meaningful when the status says the dimension was (provisionally) assessed.
    var displayLevel: Int? { status.hasLevel ? level : nil }
}

struct SpeechPatterns: Codable, Hashable, Sendable {
    let wordsPerMinute: Double?
    let fillerPerMinute: Double?
    let topFillers: [String]
    let hedgesPerMinute: Double?
    let avgPauseSeconds: Double?
    let longestTurnSeconds: Double?
    let talkShare: Double?
    let userSpeechSeconds: Double
    let languageSupported: Bool
}

struct RewriteMoment: Codable, Hashable, Sendable {
    let dimension: DimensionId?
    let youSaid: String
    let tryInstead: String
    let why: String
    let sourceType: String
    let sourceId: String
    let turnIndex: Int?
    let startSeconds: Double?
    let endSeconds: Double?
    let audioUrl: String?
}

enum StyleStatus: String, Codable, Hashable, Sendable {
    case ready, provisional
    case notReady = "not_ready"

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = StyleStatus(rawValue: raw) ?? .notReady
    }
}

struct StyleResult: Codable, Hashable, Sendable {
    let status: StyleStatus
    let archetype: String?
    let description: String?
    let traits: [String]
    let message: String?
}

enum RecoveryActionType: String, Codable, Hashable, Sendable {
    case retry
    case recordAgain = "record_again"
    case uploadAnother = "upload_another"
    case aiPractice = "ai_practice"
    case identifySpeaker = "identify_speaker"
    case gapFill = "gap_fill"
    case starterCourse = "starter_course"
    case continueOn = "continue"

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = RecoveryActionType(rawValue: raw) ?? .continueOn
    }
}

struct RecoveryAction: Codable, Hashable, Sendable {
    let type: RecoveryActionType
    let title: String
    let activityId: ActivityId?
}

struct Recovery: Codable, Hashable, Sendable {
    let problem: String
    let title: String
    let message: String
    let actions: [RecoveryAction]
    let extraMinutes: Int?
}

enum AnalysisStatus: String, Codable, Hashable, Sendable {
    case complete, partial
    case noneAssessed = "none"

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = AnalysisStatus(rawValue: raw) ?? .partial
    }
}

struct AnalysisResult: Codable, Hashable, Sendable {
    let status: AnalysisStatus
    let headline: String
    let summary: String
    let dimensions: [DimensionResult]
    let speechPatterns: SpeechPatterns?
    let firstWin: RewriteMoment?
    let style: StyleResult
    let recovery: Recovery?
    let contextLabel: String
    let createdAt: Date

    var assessedDimensions: [DimensionResult] { dimensions.filter { $0.status.hasLevel } }
    var missingDimensions: [DimensionResult] { dimensions.filter { !$0.status.hasLevel } }
}

struct ItemsResponse<Item: Codable & Sendable>: Codable, Sendable {
    let items: [Item]
}

struct ResultRef: Codable, Hashable, Sendable {
    let type: String
    let id: String
}
