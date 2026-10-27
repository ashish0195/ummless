import Foundation

// MARK: - Profile

struct HistoryEntry: Codable, Hashable, Sendable {
    let dimension: DimensionId
    let status: DimensionStatus
    let level: Int?
    let levelLabel: String?
    let assessedAt: Date
    let contextLabel: String
    let sourceType: String
    let sourceId: String
}

struct ProfileSource: Codable, Hashable, Sendable, Identifiable {
    let type: String
    let id: String
    let title: String
    let createdAt: Date
    let status: String
}

struct TwinMatch: Codable, Hashable, Sendable, Identifiable {
    let aspect: String
    let aspectTitle: String
    let referenceName: String
    let referenceBlurb: String
    let closeness: Double
    let yourValue: String
    let referenceValue: String

    var id: String { aspect }
}

struct TwinResult: Codable, Hashable, Sendable {
    let status: String
    let message: String
    let disclaimer: String
    let nextStep: NextStep?
    let matches: [TwinMatch]

    var isReady: Bool { status == "ready" }
}

struct Profile: Codable, Sendable {
    let basis: String
    let headline: String
    let summary: String?
    let dimensions: [DimensionResult]
    let speechPatterns: SpeechPatterns?
    let style: StyleResult
    let twin: TwinResult
    let firstWin: RewriteMoment?
    let history: [HistoryEntry]
    let sources: [ProfileSource]
    let updatedAt: Date?

    func dimension(_ id: DimensionId) -> DimensionResult? { dimensions.first { $0.dimension == id } }
    func history(for id: DimensionId) -> [HistoryEntry] {
        history.filter { $0.dimension == id }.sorted { $0.assessedAt > $1.assessedAt }
    }
    var hasAnyAssessed: Bool { dimensions.contains { $0.status.hasLevel } }
}

// MARK: - Course

struct MissionSummary: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let type: MissionType
    let title: String
    let minutes: Int
    let status: String
    let lockedReason: String?

    var isLocked: Bool { status == "locked" }
    var isCompleted: Bool { status == "completed" }
}

struct CourseModule: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let index: Int
    let title: String
    let dimension: DimensionId
    let targetBehavior: String
    let summary: String
    let status: String
    let completedMissions: Int
    let missions: [MissionSummary]
}

struct GapTask: Codable, Hashable, Sendable, Identifiable {
    let dimension: DimensionId
    let activityId: ActivityId
    let title: String
    let minutes: Int
    let reason: String

    var id: String { dimension.rawValue + activityId }
}

struct QuickOption: Codable, Hashable, Sendable {
    let missionId: String
    let title: String
    let minutes: Int
}

struct TodayPlan: Codable, Hashable, Sendable {
    let mission: MissionSummary
    let moduleTitle: String
    let quick: QuickOption?
}

struct Course: Codable, Sendable {
    let track: Track
    let basis: String
    let basisLabel: String
    let basisExplainer: String
    let focusModuleId: String
    let modules: [CourseModule]
    let gapTasks: [GapTask]
    let today: TodayPlan?
    let isPro: Bool
    let freeMissionId: String?
}

struct MissionExample: Codable, Hashable, Sendable {
    let text: String
    let audioUrl: String?
    let explanation: String
}

struct RealLifeTask: Codable, Hashable, Sendable {
    let prompt: String
    let aiAlternativeTitle: String
    let reflectionQuestions: [String]
}

struct AttemptComparison: Codable, Hashable, Sendable {
    let previousAttemptId: String
    let summary: String
    let changes: [String]
    let note: String
}

struct AttemptFeedback: Codable, Hashable, Sendable {
    let assessable: Usable
    let targetMet: String
    let headline: String
    let `where`: EvidenceMoment?
    let whatWorked: [String]
    let oneChange: String?
    let missingEvidence: String?
    let comparison: AttemptComparison?
    let issues: [Issue]
}

struct MissionAttempt: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let conversationId: String
    let attemptNumber: Int
    let quick: Bool
    let status: String
    let feedback: AttemptFeedback?
    let createdAt: Date

    var isProcessing: Bool { status == "processing" }
    var isFailed: Bool { status == "failed" }
}

struct Reflection: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let text: String
    let went: String?
    let coachReply: String?
    let createdAt: Date
}

struct Mission: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let moduleId: String
    let trackId: TrackId
    let type: MissionType
    let title: String
    let dimension: DimensionId
    let minutes: Int
    let context: String
    let targetBehavior: String
    let whyItMatters: String
    let example: MissionExample
    let steps: [String]
    let suggestedSeconds: Int
    let realLife: RealLifeTask?
    let attempts: [MissionAttempt]
    let reflections: [Reflection]
    let status: String
    let lockedReason: String?
    let takeaway: String?

    var isLocked: Bool { status == "locked" }
    var isCompleted: Bool { status == "completed" }
    var latestAttempt: MissionAttempt? { attempts.max { $0.attemptNumber < $1.attemptNumber } }
}

struct TrackChangeRequest: Codable, Sendable { let track: TrackId }
struct FocusChangeRequest: Codable, Sendable { let moduleId: String }
struct CompleteMissionRequest: Codable, Sendable { let takeaway: String? }
struct ReflectionRequest: Codable, Sendable {
    let text: String
    let went: String?
}

// MARK: - Spar, talks, events

struct Persona: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let name: String
    let title: String
    let scenario: String
    let description: String
    let defaultDifficulty: Difficulty
    let symbol: String
    let colorHex: String
    let isFree: Bool
}

struct PersonasResponse: Codable, Sendable { let personas: [Persona] }

struct SparOutcome: Codable, Hashable, Sendable {
    let label: String
    let detail: String
}

struct MomentumPoint: Codable, Hashable, Sendable, Identifiable {
    let turnIndex: Int
    let value: Double
    let note: String?

    var id: Int { turnIndex }
}

struct SparObservation: Codable, Hashable, Sendable {
    let dimension: DimensionId
    let note: String
}

struct SparReport: Codable, Hashable, Sendable {
    let conversationId: String
    let status: String
    let title: String
    let outcome: SparOutcome?
    let momentum: [MomentumPoint]
    let moments: [RewriteMoment]
    let observations: [SparObservation]
    let nextStep: String?

    var isProcessing: Bool { status == "processing" }
}

struct SparSession: Codable, Hashable, Sendable, Identifiable {
    let conversationId: String
    let title: String
    let personaName: String
    let difficulty: Difficulty
    let createdAt: Date
    let status: String
    let outcomeLabel: String?

    var id: String { conversationId }
}

struct TalkStyle: Codable, Hashable, Sendable {
    let wpm: Double
    let avgPauseSeconds: Double
    let avgSentenceWords: Double
}

struct TalkSummary: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let title: String
    let speaker: String
    let sourceNote: String
    let year: Int?
    let durationLabel: String
    let linesCount: Int
    let style: TalkStyle
    let tags: [String]
    let isFree: Bool
}

struct TalksResponse: Codable, Sendable { let talks: [TalkSummary] }

struct TalkLine: Codable, Hashable, Sendable, Identifiable {
    let index: Int
    let text: String
    let displayText: String
    let pauseCount: Int
    let audioUrl: String?

    var id: Int { index }
}

struct Talk: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let title: String
    let speaker: String
    let sourceNote: String
    let year: Int?
    let durationLabel: String
    let linesCount: Int
    let style: TalkStyle
    let tags: [String]
    let isFree: Bool
    let technique: String
    let breakdown: [String]
    let lines: [TalkLine]
    let locked: Bool
}

struct PrepItem: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let title: String
    let scenario: String
    let partnerRole: String
    let difficulty: Difficulty
}

struct UpcomingEvent: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let title: String
    let kind: String
    let date: String
    let notes: String?
    let prep: [PrepItem]
    let createdAt: Date
    /// Optional local start time, "HH:MM".
    let time: String?
}

struct EventsResponse: Codable, Sendable { let events: [UpcomingEvent] }

struct CreateEventRequest: Codable, Sendable {
    let title: String
    let kind: String
    let date: String
    let notes: String?
    var time: String?
}

// MARK: - Progress & review

struct Milestone: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let title: String
    let detail: String
    let achievedAt: Date
}

struct WeekProgress: Codable, Hashable, Sendable {
    let sessions: Int
    let target: Int
    /// Weekdays with at least one session (1 = Monday).
    let days: [Int]?
    let met: Bool?

    var targetMet: Bool { met ?? (sessions >= target) }
}

struct PracticeStats: Codable, Hashable, Sendable {
    let totalSessions: Int
    let missionsCompleted: Int
    let minutes: Int
    let weeksActive: Int
    let thisWeek: WeekProgress
    // v2
    let reps: Int?
    let weeksOnTarget: Int?
    let bestWeeksOnTarget: Int?
    let pausedUntil: String?
}

struct WelcomeBack: Codable, Hashable, Sendable {
    let daysAway: Int
    let message: String
}

struct RecentItem: Codable, Hashable, Sendable {
    let type: String
    let title: String
    let createdAt: Date
}

struct ProgressSummary: Codable, Sendable {
    let practice: PracticeStats
    let milestones: [Milestone]
    let recent: [RecentItem]
    let welcomeBack: WelcomeBack?
}

struct WeeklyPractice: Codable, Hashable, Sendable {
    let sessions: Int
    let missionsCompleted: Int
    let attempts: Int
    let retries: Int
    let realLifeAttempts: Int
    let minutes: Int
    let target: Int
    let metTarget: Bool
}

struct BeforeAfter: Codable, Hashable, Sendable {
    let missionTitle: String
    let beforeQuote: String
    let afterQuote: String
    let note: String
}

struct SkillUpdate: Codable, Hashable, Sendable {
    let dimension: DimensionId
    let change: String
    let note: String
}

struct FocusOption: Codable, Hashable, Sendable, Identifiable {
    let moduleId: String
    let title: String
    let reason: String

    var id: String { moduleId }
}

struct WeeklyReview: Codable, Sendable {
    let weekStart: String
    let weekEnd: String
    let practice: WeeklyPractice
    let highlights: [String]
    let beforeAfter: BeforeAfter?
    let skillUpdates: [SkillUpdate]
    let evidenceNote: String
    let nextFocusOptions: [FocusOption]
    let milestones: [Milestone]
    let message: String
}
