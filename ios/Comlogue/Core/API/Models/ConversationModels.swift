import Foundation

enum ConversationStatus: String, Codable, Hashable, Sendable {
    case active, finished

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = ConversationStatus(rawValue: raw) ?? .active
    }
}

struct ConversationSetup: Codable, Hashable, Sendable {
    let title: String
    let context: String
    let targetBehavior: String?
    let suggestedSeconds: Int
    let tips: [String]
    let activityId: ActivityId?
    let missionId: String?
    let personaId: String?
    let difficulty: Difficulty?
    let quick: Bool
}

struct Conversation: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let kind: String
    let status: ConversationStatus
    let partner: Partner
    let setup: ConversationSetup
    let turns: [Turn]
    let awaiting: String
    let userTurns: Int
    let maxUserTurns: Int
    let assessmentId: String?
    let missionId: String?
    let demoMode: Bool
    let createdAt: Date
    /// Group conversations only (moderator first); empty otherwise.
    let participants: [Participant]?

    var isGroup: Bool { !(participants ?? []).isEmpty }

    func participant(_ id: String?) -> Participant? {
        guard let id else { return nil }
        return participants?.first { $0.id == id }
    }

    var isAwaitingUser: Bool { status == .active && awaiting == "user" }
    var lastPartnerTurn: Turn? { turns.last { $0.speaker == .partner } }
    var usableUserTurns: [Turn] { turns.filter { $0.speaker == .user && !$0.excluded } }
}

struct TurnResult: Codable, Sendable {
    let conversation: Conversation
    let userTurn: Turn
    let partnerTurn: Turn?
    let retrySuggested: Bool
    let done: Bool
    /// Every partner line after the user's turn, in order (several in a group conversation).
    let partnerTurns: [Turn]?

    var allPartnerTurns: [Turn] {
        if let partnerTurns, !partnerTurns.isEmpty { return partnerTurns }
        return partnerTurn.map { [$0] } ?? []
    }
}

struct FinishResult: Codable, Sendable {
    let conversation: Conversation
    let resultRef: ResultRef?
}

struct CreateConversationRequest: Codable, Sendable {
    var kind: String
    var missionId: String?
    var quick: Bool?
    var personaId: String?
    var customScenario: String?
    var difficulty: Difficulty?
    var eventId: String?
    var prepId: String?
    var dailyDate: String?
    var panelId: String?
}

/// On-device measurements sent alongside a turn so the server can cross-check its own analysis.
struct ClientAudioMetrics: Codable, Hashable, Sendable {
    let durationSeconds: Double
    let speechSeconds: Double
    let activeLevelDb: Double
    let noiseFloorDb: Double
    let clippingRatio: Double
    let pauseCount: Int
    let avgPauseSeconds: Double
}

// MARK: - Assessments

enum AssessmentStatus: String, Codable, Hashable, Sendable {
    case inProgress = "in_progress"
    case processing
    case complete
    case needsRecovery = "needs_recovery"

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = AssessmentStatus(rawValue: raw) ?? .processing
    }
}

enum ActivityStatus: String, Codable, Hashable, Sendable {
    case pending
    case inProgress = "in_progress"
    case done
    case skipped

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = ActivityStatus(rawValue: raw) ?? .pending
    }
}

struct AssessmentActivity: Codable, Hashable, Sendable, Identifiable {
    let id: ActivityId
    let title: String
    let prompt: String
    let durationLabel: String
    let suggestedSeconds: Int
    let dimensions: [DimensionId]
    let status: ActivityStatus
    let conversationId: String?
}

struct Assessment: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let route: String
    let purpose: String
    let status: AssessmentStatus
    let stage: String?
    let activities: [AssessmentActivity]
    let estimateMinutes: [Int]
    let targetDimensions: [DimensionId]
    let result: AnalysisResult?
    let createdAt: Date
    let completedAt: Date?

    var nextActivity: AssessmentActivity? {
        activities.first { $0.status == .pending || $0.status == .inProgress }
    }
    var doneCount: Int { activities.filter { $0.status == .done }.count }
    var isFinished: Bool { status == .complete || status == .needsRecovery }
}

struct CreateAssessmentRequest: Codable, Sendable {
    var purpose: String
    var activityIds: [ActivityId]?
    var targetDimensions: [DimensionId]?
}

// MARK: - Recordings

enum RecordingStatus: String, Codable, Hashable, Sendable {
    case processing
    case needsSpeakerConfirmation = "needs_speaker_confirmation"
    case assessing
    case complete
    case needsRecovery = "needs_recovery"
    case failed
    case noUser = "no_user"

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = RecordingStatus(rawValue: raw) ?? .processing
    }

    var isWorking: Bool { self == .processing || self == .assessing }
}

struct RecordingQuality: Codable, Hashable, Sendable {
    let usable: Usable
    let issues: [Issue]
    let usableSeconds: Double
    let totalSeconds: Double
}

struct SpeakerCandidate: Codable, Hashable, Sendable, Identifiable {
    let label: String
    let displayName: String
    let speechSeconds: Double
    let turns: Int
    let sampleUrl: String?
    let sampleText: String?
    let isProposedUser: Bool
    let match: String
    let matchStrength: String?

    var id: String { label }
}

struct Attribution: Codable, Hashable, Sendable {
    let status: String
    let userSpeakerLabel: String?
    let requiresConfirmation: Bool
    let reason: String?
    let message: String?
}

struct TalkShare: Codable, Hashable, Sendable, Identifiable {
    let label: String
    let displayName: String
    let isUser: Bool
    let share: Double

    var id: String { label }
}

struct MeetingDebrief: Codable, Hashable, Sendable {
    let talkShare: [TalkShare]
    let bestMoment: EvidenceMoment?
    let decisions: [String]
    let followUpSummary: String?
    let oneThingToTry: String?
}

struct Recording: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let title: String
    let source: String
    let status: RecordingStatus
    let stage: String?
    let durationSeconds: Double?
    let createdAt: Date
    let quality: RecordingQuality?
    let speakers: [SpeakerCandidate]
    let attribution: Attribution
    let result: AnalysisResult?
    let debrief: MeetingDebrief?
    let recovery: Recovery?
}

struct RecordingConsentPayload: Codable, Sendable {
    let attested: Bool
    let region: String?
    let rule: String?
    let consentVersion: String
}

struct SpeakerConfirmationRequest: Codable, Sendable {
    let decision: String
    let speakerLabel: String?
}

struct TranscriptSegment: Codable, Hashable, Sendable {
    let speaker: String
    let isUser: Bool
    let start: Double
    let end: Double
    let text: String
    let excluded: Bool
    let exclusionReason: String?
}

struct Transcript: Codable, Sendable {
    let segments: [TranscriptSegment]
}
