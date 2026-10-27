import Foundation

/// Development-only endpoints (enabled on the server with ALLOW_DEV_ENTITLEMENTS=true).
struct DemoSeedRequest: Codable, Sendable {
    let pro: Bool
    var market: Market = .us
}

/// IDs of the demo data created by `POST /v1/dev/seed-demo`, used by screenshot mode.
struct DemoSeed: Codable, Sendable {
    let assessmentId: String
    let recordingNeedsConfirmationId: String?
    let recordingCompleteId: String?
    let missionId: String?
    let sparConversationId: String?
    let eventId: String?
    // v2
    let dailyDate: String?
    let groupConversationId: String?
    let panelId: String?
    let previousDailyDate: String?
}

extension APIClient {
    func seedDemo(pro: Bool, market: Market = .us) async throws -> DemoSeed {
        try await post("/v1/dev/seed-demo", body: DemoSeedRequest(pro: pro, market: market))
    }
}
