import Foundation

/// v2 endpoints: devices and notifications, the daily rep, group conversations and data export.
extension APIClient {
    // MARK: Devices & inbox

    func registerDevice(_ registration: DeviceRegistration) async throws -> DeviceInfo {
        try await post("/v1/devices", body: registration)
    }

    func notifications(limit: Int = 50) async throws -> NotificationsResponse {
        try await get("/v1/notifications", query: ["limit": String(limit)])
    }

    func markNotificationsRead(ids: [String]) async throws -> Int {
        let response: UnreadCountResponse = try await post("/v1/notifications/read", body: ReadNotificationsRequest(ids: ids))
        return response.unreadCount
    }

    func markAllNotificationsRead() async throws -> Int {
        let response: UnreadCountResponse = try await post("/v1/notifications/read", body: ReadNotificationsRequest(all: true))
        return response.unreadCount
    }

    func notificationOpened(_ id: String) async throws {
        try await postNoContent("/v1/notifications/\(id)/opened")
    }

    func sendTestNotification() async throws -> InboxNotification {
        try await post("/v1/notifications/test")
    }

    // MARK: Daily rep

    func dailyRep() async throws -> DailyRep { try await get("/v1/daily") }

    func dailyRep(date: String) async throws -> DailyRep { try await get("/v1/daily/\(date)") }

    func upcomingReps(days: Int = 7) async throws -> [DailyRepPreview] {
        let response: ItemsResponse<DailyRepPreview> = try await get("/v1/daily/upcoming", query: ["days": String(days)])
        return response.items
    }

    func shuffleDailyRep() async throws -> DailyRep { try await post("/v1/daily/shuffle") }

    // MARK: Group conversations

    func panels() async throws -> [Panel] {
        let response: PanelsResponse = try await get("/v1/group/panels")
        return response.panels
    }

    // MARK: Privacy

    /// Everything stored about the person, as JSON (no audio).
    func exportData() async throws -> Data { try await download("/v1/me/export") }
}
