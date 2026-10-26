import XCTest
@testable import ComlogueCore

final class CodingAndFormattingTests: XCTestCase {
    func testDatesWithAndWithoutFractionalSeconds() throws {
        XCTAssertNotNil(JSONCoding.parseDate("2026-10-26T21:00:00Z"))
        XCTAssertNotNil(JSONCoding.parseDate("2026-10-26T21:00:00.123Z"))
        XCTAssertNotNil(JSONCoding.parseDate("2026-10-30"))
        XCTAssertNil(JSONCoding.parseDate("yesterday"))
    }

    func testUnknownEnumValuesFallBack() throws {
        struct Wrapper: Decodable {
            let status: DimensionStatus
            let difficulty: Difficulty
            let action: RecoveryActionType
        }
        let json = #"{"status":"brand_new_status","difficulty":"legendary","action":"teleport"}"#
        let decoded = try JSONCoding.makeDecoder().decode(Wrapper.self, from: Data(json.utf8))
        XCTAssertEqual(decoded.status, .notAssessed)
        XCTAssertEqual(decoded.difficulty, .real)
        XCTAssertEqual(decoded.action, .continueOn)
    }

    func testSnakeCaseRoundTrip() throws {
        let request = CreateConversationRequest(kind: "spar", missionId: nil, quick: nil, personaId: "skeptical_cfo",
                                                customScenario: "Ask my landlord", difficulty: .brutal, eventId: nil, prepId: nil)
        let data = try JSONCoding.makeEncoder().encode(request)
        let object = try XCTUnwrap(try JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(object["persona_id"] as? String, "skeptical_cfo")
        XCTAssertEqual(object["custom_scenario"] as? String, "Ask my landlord")
        XCTAssertEqual(object["difficulty"] as? String, "brutal")
        XCTAssertNil(object["mission_id"], "nil optionals must be omitted, not sent as null")
    }

    func testFormatting() {
        XCTAssertEqual(Formatting.clock(75), "1:15")
        XCTAssertEqual(Formatting.clock(-3), "0:00")
        XCTAssertEqual(Formatting.minutesRange([10, 15]), "10–15 min")
        XCTAssertEqual(Formatting.minutesRange([3]), "3 min")
        XCTAssertEqual(Formatting.percent(0.523), "52%")
        XCTAssertEqual(DimensionCatalog.levelLabel(3), "Capable")
        let rgb = Formatting.rgb(fromHex: "#FF8000")
        XCTAssertEqual(rgb?.red ?? 0, 1, accuracy: 0.001)
        XCTAssertEqual(rgb?.green ?? 0, 128.0 / 255, accuracy: 0.001)
    }

    func testMultipartBodyContainsFieldsAndFile() {
        let file = UploadFile(data: Data("abc".utf8), fileName: "turn.m4a", mimeType: "audio/mp4")
        let body = APIClient.multipartBody(boundary: "B", file: file, fields: ["elapsed_seconds": "12.0"])
        let text = String(decoding: body, as: UTF8.self)
        XCTAssertTrue(text.contains("name=\"elapsed_seconds\"\r\n\r\n12.0\r\n"))
        XCTAssertTrue(text.contains("name=\"audio\"; filename=\"turn.m4a\""))
        XCTAssertTrue(text.hasSuffix("--B--\r\n"))
    }

    func testRelativeURLResolution() {
        let client = APIClient(baseURL: URL(string: "https://api.example.com")!)
        XCTAssertEqual(client.resolve("/v1/media/med_1?sig=x")?.absoluteString, "https://api.example.com/v1/media/med_1?sig=x")
        XCTAssertEqual(client.resolve("https://cdn.example.com/a.mp3")?.absoluteString, "https://cdn.example.com/a.mp3")
    }
}
