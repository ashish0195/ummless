import Foundation

/// Typed endpoint wrappers. One method per route in docs/API.md.
extension APIClient {
    // MARK: Auth & meta

    func authenticateDevice(deviceId: String, appVersion: String) async throws -> AuthResponse {
        try await post("/v1/auth/device", body: DeviceAuthRequest(deviceId: deviceId, platform: "ios", appVersion: appVersion))
    }

    func health() async throws -> HealthResponse { try await get("/v1/health") }
    func meta() async throws -> Meta { try await get("/v1/meta") }

    func recordingRules(region: String?) async throws -> RecordingRules {
        try await get("/v1/meta/recording-rules", query: region.map { ["region": $0] } ?? [:])
    }

    // MARK: Me

    func me() async throws -> Me { try await get("/v1/me") }
    func updateMe(_ changes: MePatch) async throws -> Me { try await patch("/v1/me", body: changes) }
    func deleteAccount() async throws { try await delete("/v1/me") }

    // MARK: Voice reference

    func voiceReference() async throws -> VoiceReference { try await get("/v1/voice-reference") }

    func enrollVoice(file: UploadFile, consentVersion: String) async throws -> VoiceEnrollmentResult {
        try await upload("/v1/voice-reference", file: file, fields: [
            "consent_version": consentVersion,
            "consent_accepted": "true",
        ])
    }

    func deleteVoiceReference() async throws { try await delete("/v1/voice-reference") }

    // MARK: Conversations

    func createConversation(_ request: CreateConversationRequest) async throws -> Conversation {
        try await post("/v1/conversations", body: request)
    }

    func conversation(_ id: String) async throws -> Conversation { try await get("/v1/conversations/\(id)") }

    func sendTurn(conversationId: String, file: UploadFile, elapsedSeconds: Double, metrics: ClientAudioMetrics?) async throws -> TurnResult {
        var fields = ["elapsed_seconds": String(format: "%.1f", elapsedSeconds)]
        if let metrics { fields["client_metrics"] = encodeJSONString(metrics) }
        return try await upload("/v1/conversations/\(conversationId)/turns", file: file, fields: fields, timeout: 180)
    }

    func finishConversation(_ id: String) async throws -> FinishResult {
        try await post("/v1/conversations/\(id)/finish")
    }

    // MARK: Assessments

    func createAssessment(_ request: CreateAssessmentRequest) async throws -> Assessment {
        try await post("/v1/assessments", body: request)
    }

    func assessment(_ id: String) async throws -> Assessment { try await get("/v1/assessments/\(id)") }
    func assessments() async throws -> [Assessment] {
        let response: ItemsResponse<Assessment> = try await get("/v1/assessments")
        return response.items
    }

    func startActivity(assessmentId: String, activityId: ActivityId) async throws -> Conversation {
        try await post("/v1/assessments/\(assessmentId)/activities/\(activityId)/start")
    }

    func skipActivity(assessmentId: String, activityId: ActivityId) async throws -> Assessment {
        try await post("/v1/assessments/\(assessmentId)/activities/\(activityId)/skip")
    }

    func finalizeAssessment(_ id: String) async throws -> Assessment {
        try await post("/v1/assessments/\(id)/finalize")
    }

    // MARK: Recordings

    func uploadRecording(file: UploadFile, source: String, title: String?, consent: RecordingConsentPayload) async throws -> Recording {
        var fields = ["source": source, "consent": encodeJSONString(consent)]
        if let title, !title.isEmpty { fields["title"] = title }
        return try await upload("/v1/recordings", file: file, fields: fields, timeout: 600)
    }

    func recordings() async throws -> [Recording] {
        let response: ItemsResponse<Recording> = try await get("/v1/recordings")
        return response.items
    }

    func recording(_ id: String) async throws -> Recording { try await get("/v1/recordings/\(id)") }

    func confirmSpeaker(recordingId: String, decision: String, speakerLabel: String?) async throws -> Recording {
        try await post("/v1/recordings/\(recordingId)/speaker-confirmation",
                       body: SpeakerConfirmationRequest(decision: decision, speakerLabel: speakerLabel))
    }

    /// Re-runs processing on the saved audio. Only for recordings that failed on the server's side.
    func retryRecording(_ id: String) async throws -> Recording { try await post("/v1/recordings/\(id)/retry") }

    func transcript(recordingId: String) async throws -> Transcript { try await get("/v1/recordings/\(recordingId)/transcript") }
    func deleteRecording(_ id: String) async throws { try await delete("/v1/recordings/\(id)") }

    // MARK: Profile & course

    func profile() async throws -> Profile { try await get("/v1/profile") }
    func course() async throws -> Course { try await get("/v1/course") }
    func changeTrack(_ track: TrackId) async throws -> Course { try await post("/v1/course/track", body: TrackChangeRequest(track: track)) }
    func changeFocus(moduleId: String) async throws -> Course { try await post("/v1/course/focus", body: FocusChangeRequest(moduleId: moduleId)) }
    func mission(_ id: String) async throws -> Mission { try await get("/v1/missions/\(id)") }

    func completeMission(_ id: String, takeaway: String?) async throws -> Mission {
        try await post("/v1/missions/\(id)/complete", body: CompleteMissionRequest(takeaway: takeaway))
    }

    func addReflection(missionId: String, text: String, went: String?) async throws -> Reflection {
        try await post("/v1/missions/\(missionId)/reflections", body: ReflectionRequest(text: text, went: went))
    }

    // MARK: Spar, talks, events

    func personas() async throws -> [Persona] {
        let response: PersonasResponse = try await get("/v1/spar/personas")
        return response.personas
    }

    func sparSessions() async throws -> [SparSession] {
        let response: ItemsResponse<SparSession> = try await get("/v1/spar/sessions")
        return response.items
    }

    func sparReport(conversationId: String) async throws -> SparReport { try await get("/v1/spar/reports/\(conversationId)") }

    func talks() async throws -> [TalkSummary] {
        let response: TalksResponse = try await get("/v1/talks")
        return response.talks
    }

    func talk(_ id: String) async throws -> Talk { try await get("/v1/talks/\(id)") }

    func events() async throws -> [UpcomingEvent] {
        let response: EventsResponse = try await get("/v1/events")
        return response.events
    }

    func createEvent(_ request: CreateEventRequest) async throws -> UpcomingEvent { try await post("/v1/events", body: request) }
    func deleteEvent(_ id: String) async throws { try await delete("/v1/events/\(id)") }

    // MARK: Progress, review, billing

    func progress() async throws -> ProgressSummary { try await get("/v1/progress") }
    func weeklyReview() async throws -> WeeklyReview { try await get("/v1/review/weekly") }

    func submitAppStoreTransaction(_ jws: String) async throws -> Entitlement {
        try await post("/v1/billing/app-store", body: AppStoreTransactionRequest(signedTransaction: jws))
    }

    func devGrant(tier: String) async throws -> Entitlement {
        try await post("/v1/billing/dev-grant", body: DevGrantRequest(tier: tier))
    }
}
