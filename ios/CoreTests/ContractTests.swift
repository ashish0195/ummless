import XCTest
@testable import ComlogueCore

/// Decodes real responses captured from the backend (`backend/scripts/export_contract_fixtures.py`)
/// with the app's own models. If the backend and the app drift apart, these tests fail.
final class ContractTests: XCTestCase {
    private static let fixturesDirectory: URL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()   // CoreTests
        .deletingLastPathComponent()   // ios
        .deletingLastPathComponent()   // repo root
        .appendingPathComponent("contract-fixtures")

    private func fixture(_ name: String) throws -> Data {
        let url = Self.fixturesDirectory.appendingPathComponent(name)
        guard FileManager.default.fileExists(atPath: url.path) else {
            throw XCTSkip("Fixture \(name) not generated yet — run backend/scripts/export_contract_fixtures.py")
        }
        return try Data(contentsOf: url)
    }

    private func decode<T: Decodable>(_ type: T.Type, _ name: String, file: StaticString = #filePath, line: UInt = #line) throws -> T {
        let data = try fixture(name)
        do {
            return try JSONCoding.makeDecoder().decode(T.self, from: data)
        } catch {
            XCTFail("\(name) does not decode as \(T.self): \(error)", file: file, line: line)
            throw error
        }
    }

    func testEveryFixtureDecodes() throws {
        _ = try decode(AuthResponse.self, "auth_device.json")
        _ = try decode(Meta.self, "meta.json")
        _ = try decode(RecordingRules.self, "recording_rules.json")
        _ = try decode(Me.self, "me.json")
        _ = try decode(VoiceEnrollmentResult.self, "voice_reference_result.json")
        _ = try decode(Conversation.self, "conversation.json")
        _ = try decode(TurnResult.self, "turn_result.json")
        _ = try decode(FinishResult.self, "finish_result.json")
        _ = try decode(Assessment.self, "assessment_in_progress.json")
        _ = try decode(Assessment.self, "assessment_complete.json")
        _ = try decode(ItemsResponse<Assessment>.self, "assessments_list.json")
        _ = try decode(Recording.self, "recording_needs_confirmation.json")
        _ = try decode(Recording.self, "recording_complete.json")
        _ = try decode(ItemsResponse<Recording>.self, "recordings_list.json")
        _ = try decode(Transcript.self, "transcript.json")
        _ = try decode(Profile.self, "profile_empty.json")
        _ = try decode(Profile.self, "profile_partial.json")
        _ = try decode(Course.self, "course.json")
        _ = try decode(Mission.self, "mission.json")
        _ = try decode(Reflection.self, "reflection.json")
        _ = try decode(PersonasResponse.self, "personas.json")
        _ = try decode(SparReport.self, "spar_report.json")
        _ = try decode(ItemsResponse<SparSession>.self, "spar_sessions.json")
        _ = try decode(TalksResponse.self, "talks.json")
        _ = try decode(Talk.self, "talk.json")
        _ = try decode(EventsResponse.self, "events.json")
        _ = try decode(UpcomingEvent.self, "event.json")
        _ = try decode(ProgressSummary.self, "progress.json")
        _ = try decode(WeeklyReview.self, "weekly_review.json")
        _ = try decode(Entitlement.self, "entitlement.json")
        _ = try decode(APIErrorEnvelope.self, "error.json")
        _ = try decode(DemoSeed.self, "seed_demo.json")
        _ = try decode(FeedbackReportResponse.self, "feedback_report.json")
    }

    /// v2: the habit loop, notifications, group conversations and markets.
    func testHabitNotificationAndMarketFixturesDecode() throws {
        let device = try decode(DeviceInfo.self, "device.json")
        XCTAssertTrue(device.id.hasPrefix("dev_"))

        let inbox = try decode(NotificationsResponse.self, "notifications.json")
        XCTAssertFalse(inbox.items.isEmpty)
        for item in inbox.items {
            XCTAssertNotNil(DeepLink(string: item.deepLink), "\(item.deepLink) isn't a link the app can open")
            XCTAssertNotEqual(item.category, .other, "\(item.id) has a category the app doesn't know")
        }

        let daily = try decode(DailyRep.self, "daily_rep.json")
        XCTAssertTrue(daily.attempts.contains { $0.feedback != nil }, "daily_rep.json should include feedback")
        XCTAssertFalse(daily.targetBehavior.isEmpty)
        let upcoming = try decode(ItemsResponse<DailyRepPreview>.self, "daily_upcoming.json")
        XCTAssertFalse(upcoming.items.isEmpty)
        XCTAssertEqual(upcoming.items.map(\.date), upcoming.items.map(\.date).sorted(), "Upcoming reps are in date order")

        let panels = try decode(PanelsResponse.self, "panels.json")
        XCTAssertTrue(panels.panels.contains { $0.isGroupDiscussion })
        XCTAssertTrue(panels.panels.contains { !$0.isGroupDiscussion })
        for panel in panels.panels {
            XCTAssertGreaterThanOrEqual(panel.participants.count, 3, "\(panel.id) needs a moderator and participants")
        }
        let group = try decode(Conversation.self, "group_conversation.json")
        XCTAssertTrue(group.isGroup)
        for turn in group.turns where turn.speaker == .partner {
            XCTAssertNotNil(group.participant(turn.speakerId), "Turn \(turn.index) has an unknown speaker")
        }
        let groupTurn = try decode(TurnResult.self, "turn_result_group.json")
        XCTAssertFalse(groupTurn.partnerTurns?.isEmpty ?? true)

        let meta = try decode(Meta.self, "meta.json")
        XCTAssertEqual(meta.pricingByMarket?["in"]?.currency, "INR")
        XCTAssertEqual(meta.pricingByMarket?["us"]?.currency, "USD")
        XCTAssertTrue(meta.languages.contains { $0.code == "hinglish" })
        XCTAssertFalse(meta.eventKinds?.isEmpty ?? true)

        let me = try decode(Me.self, "me.json")
        XCTAssertNotNil(me.market)
        XCTAssertNotNil(me.notificationSettings)

        let event = try decode(UpcomingEvent.self, "event.json")
        XCTAssertNotNil(HabitMath.parseTime(event.time), "event.json should exercise a start time")
        XCTAssertNil(event.reflection)
        let reflected = try decode(UpcomingEvent.self, "event_reflected.json")
        XCTAssertEqual(reflected.reflection?.went, "well")
        XCTAssertNotNil(reflected.reflection?.coachReply)
    }

    func testProfileNeverHasAnOverallScoreAndMissingEvidenceHasNoLevel() throws {
        let raw = String(decoding: try fixture("profile_partial.json"), as: UTF8.self)
        XCTAssertFalse(raw.contains("overall_score"), "An overall numeric score is deferred by the spec")

        let profile = try decode(Profile.self, "profile_partial.json")
        XCTAssertEqual(profile.dimensions.count, DimensionId.allCases.count)
        for dimension in profile.dimensions where !dimension.status.hasLevel {
            XCTAssertNil(dimension.displayLevel, "\(dimension.dimension) has no evidence but carries a level")
        }
        XCTAssertTrue(profile.dimensions.contains { !$0.status.hasLevel }, "Fixture should exercise the partial state")
    }

    func testMissionFixtureExercisesFeedbackAndComparison() throws {
        let mission = try decode(Mission.self, "mission.json")
        XCTAssertTrue(mission.attempts.contains { $0.feedback?.comparison != nil })
        XCTAssertFalse(mission.reflections.isEmpty)
    }

    func testTimestampsHaveNoFractionalSeconds() throws {
        let names = ["me.json", "conversation.json", "assessment_complete.json", "recording_complete.json", "profile_partial.json"]
        let pattern = try NSRegularExpression(pattern: #"\d{2}:\d{2}:\d{2}\.\d+"#)
        for name in names {
            let raw = String(decoding: try fixture(name), as: UTF8.self)
            let matches = pattern.numberOfMatches(in: raw, range: NSRange(raw.startIndex..., in: raw))
            XCTAssertEqual(matches, 0, "\(name) contains fractional-second timestamps")
        }
    }
}
