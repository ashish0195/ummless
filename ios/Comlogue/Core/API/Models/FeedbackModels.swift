import Foundation

/// "Not quite right?" — the person disputes a result or a piece of feedback. Reports are logged for
/// calibration; they never silently change a result.
struct FeedbackReportRequest: Codable, Sendable {
    let targetType: String
    let targetId: String
    let dimension: DimensionId?
    let reason: String
    let note: String?
}

struct FeedbackReportResponse: Codable, Sendable {
    let id: String
    let message: String
}

extension APIClient {
    func reportFeedback(_ request: FeedbackReportRequest) async throws -> FeedbackReportResponse {
        try await post("/v1/feedback-reports", body: request)
    }
}
