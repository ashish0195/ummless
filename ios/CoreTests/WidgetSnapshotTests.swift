import XCTest
@testable import ComlogueShared

final class WidgetSnapshotTests: XCTestCase {
    private let ist = TimeZone(identifier: "Asia/Kolkata")!

    private func snapshot(day: String, pausedUntil: String? = nil) -> WidgetSnapshot {
        WidgetSnapshot(day: day, repTitle: "Explain UPI to your US cousin", repPrompt: "…", repCompleted: false,
                       weekSessions: 2, weekTarget: 3, weekDays: [1, 3], weeksOnTarget: 4, pausedUntil: pausedUntil,
                       timeZoneIdentifier: "Asia/Kolkata")
    }

    func testRoundTripsThroughSharedDefaultsAndReportsChanges() throws {
        let defaults = try XCTUnwrap(UserDefaults(suiteName: "comlogue.tests.\(UUID().uuidString)"))
        let value = snapshot(day: "2026-10-27")
        XCTAssertTrue(value.save(to: defaults))
        XCTAssertFalse(value.save(to: defaults), "Saving the same snapshot again shouldn't trigger a widget reload")
        XCTAssertEqual(WidgetSnapshot.load(from: defaults), value)
        XCTAssertNil(WidgetSnapshot.load(from: nil))
    }

    func testTodaysRepExpiresAtLocalMidnight() {
        let value = snapshot(day: "2026-10-27")
        // 23:59 IST on the 27th is still the same day; 00:01 IST on the 28th isn't.
        XCTAssertTrue(value.isCurrent(at: Date(timeIntervalSince1970: 1_793_125_740))) // 2026-10-27T18:29:00Z
        XCTAssertFalse(value.isCurrent(at: Date(timeIntervalSince1970: 1_793_125_860))) // 2026-10-27T18:31:00Z
        let midnight = WidgetSnapshot.nextMidnight(after: Date(timeIntervalSince1970: 1_793_100_000), timeZone: ist)
        XCTAssertEqual(WidgetSnapshot.dayString(midnight, timeZone: ist), "2026-10-28")
        XCTAssertEqual(midnight, Date(timeIntervalSince1970: 1_793_125_800)) // 2026-10-27T18:30:00Z
    }

    func testANewWeekStartsFromZero() throws {
        let formatter = ISO8601DateFormatter()
        let value = snapshot(day: "2026-11-01") // a Sunday
        // 23:00 IST on Sunday is still that week; 00:30 IST on Monday isn't.
        let sundayNight = try XCTUnwrap(formatter.date(from: "2026-11-01T17:30:00Z"))
        let mondayMorning = try XCTUnwrap(formatter.date(from: "2026-11-01T19:00:00Z"))
        XCTAssertTrue(value.isSameWeek(at: sundayNight))
        XCTAssertEqual(value.sessions(at: sundayNight), 2)
        XCTAssertEqual(value.practisedDays(at: sundayNight), [1, 3])
        XCTAssertFalse(value.isSameWeek(at: mondayMorning))
        XCTAssertEqual(value.sessions(at: mondayMorning), 0)
        XCTAssertEqual(value.practisedDays(at: mondayMorning), [])
        // Any day of the same week matches.
        XCTAssertTrue(snapshot(day: "2026-10-26").isSameWeek(at: sundayNight))
        XCTAssertFalse(snapshot(day: "").isSameWeek(at: sundayNight))
    }

    func testBreaksCoverTheirLastDay() {
        let value = snapshot(day: "2026-10-27", pausedUntil: "2026-10-27")
        XCTAssertTrue(value.isPaused(at: Date(timeIntervalSince1970: 1_793_100_000)))
        XCTAssertFalse(value.isPaused(at: Date(timeIntervalSince1970: 1_793_200_000)))
    }
}
