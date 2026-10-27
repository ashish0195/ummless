import XCTest
@testable import ComlogueCore

private let ist = TimeZone(identifier: "Asia/Kolkata")!
private let newYork = TimeZone(identifier: "America/New_York")!

private func instant(_ iso: String) -> Date {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime]
    return formatter.date(from: iso)!
}

private func rep(_ date: String, _ title: String) -> DailyRepPreview {
    DailyRepPreview(date: date, promptId: "p.\(date)", title: title, prompt: "Prompt for \(date)", dimension: .clarity)
}

final class HabitMathTests: XCTestCase {
    func testDayStringAndWeekdayUseTheLocalTimezone() {
        // 19:00 UTC on 26 Oct is already 00:30 on 27 Oct in India.
        let moment = instant("2026-10-26T19:00:00Z")
        XCTAssertEqual(HabitMath.dayString(moment, timeZone: ist), "2026-10-27")
        XCTAssertEqual(HabitMath.dayString(moment, timeZone: newYork), "2026-10-26")
        XCTAssertEqual(HabitMath.weekday(instant("2026-10-26T12:00:00Z"), timeZone: newYork), 1) // Monday
        XCTAssertEqual(HabitMath.weekday(instant("2026-11-01T12:00:00Z"), timeZone: newYork), 7) // Sunday
    }

    func testDefaultDaysSpreadTheTargetAcrossTheWeek() {
        XCTAssertEqual(HabitMath.defaultDays(forTarget: 3), [1, 3, 5])
        XCTAssertEqual(HabitMath.defaultDays(forTarget: 7).count, 7)
        XCTAssertEqual(HabitMath.defaultDays(forTarget: 0), [3])
    }

    func testWeekStripMarksPractisedTodayAndUpcoming() {
        let strip = HabitMath.weekStrip(practicedDays: [1, 2], today: 3)
        XCTAssertEqual(strip, [.practiced, .practiced, .today, .upcoming, .upcoming, .upcoming, .upcoming])
        XCTAssertEqual(HabitMath.weekStrip(practicedDays: [], today: 4)[0], .rest)
    }

    func testYearlySavingIsComputedFromPrices() {
        XCTAssertEqual(HabitMath.yearlySavingPercent(monthly: 14.99, yearly: 95.99), 46)
        XCTAssertEqual(HabitMath.yearlySavingPercent(monthly: 399, yearly: 2499), 47)
        XCTAssertNil(HabitMath.yearlySavingPercent(monthly: 10, yearly: 130))
        XCTAssertNil(HabitMath.yearlySavingPercent(monthly: 0, yearly: 50))
    }

    func testAnchorsReadInTheSecondPersonAndFitTheMarket() {
        XCTAssertEqual(PracticeAnchor.secondPerson("After my morning chai"), "After your morning chai")
        XCTAssertEqual(PracticeAnchor.secondPerson("Before I start work"), "Before you start work")
        XCTAssertTrue(PracticeAnchor.presets(for: .in).contains("After my morning chai"))
        XCTAssertTrue(PracticeAnchor.presets(for: .us).contains("After my morning coffee"))
    }

    func testMarketFromRegion() {
        XCTAssertEqual(Market.from(region: "IN"), .in)
        XCTAssertEqual(Market.from(region: "in-mh"), .in)
        XCTAssertEqual(Market.from(region: "US-CA"), .us)
        XCTAssertEqual(Market.from(region: "US-IN"), .us) // Indiana
        XCTAssertEqual(Market.from(region: "GB"), .global)
        XCTAssertEqual(Market.from(region: nil), .global)
    }
}

final class DeepLinkTests: XCTestCase {
    func testEveryLinkRoundTrips() {
        let links: [DeepLink] = [
            .today, .daily(date: nil), .daily(date: "2026-10-27"), .mission(id: "business.m1.learn"),
            .reflect(missionId: "business.m1.real"), .recording(id: "rec_1"), .assessment(id: "asm_1"),
            .event(id: "evt_1"), .weeklyReview, .inbox, .practice, .group(panelId: "gd.remote_work_india"), .paywall,
            .notificationSettings,
        ]
        for link in links {
            XCTAssertEqual(DeepLink(url: link.url), link, "\(link.url)")
        }
    }

    func testParsesServerLinksAndRejectsOthers() {
        XCTAssertEqual(DeepLink(string: "comlogue://review/weekly"), .weeklyReview)
        XCTAssertEqual(DeepLink(string: "comlogue://settings/notifications"), .notificationSettings)
        XCTAssertNil(DeepLink(string: "https://comlogue.app/today"))
        XCTAssertNil(DeepLink(string: "comlogue://mission"))
        XCTAssertNil(DeepLink(string: "comlogue://unknown/thing"))
    }
}

final class NotificationPlannerTests: XCTestCase {
    private func input(now: String, zone: TimeZone = ist) -> NotificationPlanInput {
        var input = NotificationPlanInput(now: instant(now), timeZone: zone)
        input.practiceDays = [1, 3, 5]
        input.reminderTime = "08:00"
        return input
    }

    func testPracticeRemindersFollowTheChosenDaysAndTimeInIndia() {
        // Tuesday 27 Oct, 06:00 in India.
        var plan = input(now: "2026-10-27T00:30:00Z")
        plan.settings.nudges = false
        let reminders = NotificationPlanner.plan(plan).filter { $0.kind == .practice }
        XCTAssertEqual(reminders.map { HabitMath.dayString($0.fireDate, timeZone: ist) },
                       ["2026-10-28", "2026-10-30", "2026-11-02"])
        // 08:00 in India is 02:30 UTC.
        XCTAssertEqual(reminders.first?.fireDate, instant("2026-10-28T02:30:00Z"))
    }

    func testTodayIsSkippedWhenAlreadyPractisedOrPast() {
        // Monday 26 Oct 07:00 IST, a practice day.
        var plan = input(now: "2026-10-26T01:30:00Z")
        plan.settings.nudges = false
        XCTAssertEqual(NotificationPlanner.plan(plan).first?.fireDate, instant("2026-10-26T02:30:00Z"))
        plan.practicedToday = true
        XCTAssertNotEqual(NotificationPlanner.plan(plan).first?.fireDate, instant("2026-10-26T02:30:00Z"))
        // 09:00 IST: today's 08:00 has passed.
        var later = input(now: "2026-10-26T03:30:00Z")
        later.settings.nudges = false
        XCTAssertEqual(NotificationPlanner.plan(later).first.map { HabitMath.dayString($0.fireDate, timeZone: ist) },
                       "2026-10-28")
    }

    func testCopyUsesTheDaysPromptAndTheAnchor() {
        var plan = input(now: "2026-10-27T00:30:00Z")
        plan.anchor = "After my morning chai"
        plan.upcomingReps = [rep("2026-10-28", "Explain UPI to your US cousin")]
        let first = NotificationPlanner.plan(plan).first { $0.kind == .practice }
        XCTAssertEqual(first?.title, "Explain UPI to your US cousin")
        XCTAssertTrue(first?.body.hasPrefix("After your morning chai") == true)
        XCTAssertEqual(first?.deepLink, .daily(date: "2026-10-28"))
    }

    func testABreakPausesRemindersAndNudges() {
        var plan = input(now: "2026-10-27T00:30:00Z")
        plan.pausedUntil = "2026-11-01"
        let planned = NotificationPlanner.plan(plan)
        XCTAssertEqual(planned.filter { $0.kind == .practice }.map { HabitMath.dayString($0.fireDate, timeZone: ist) },
                       ["2026-11-02"])
        // The 3-day nudge falls inside the break; the 8-day one doesn't.
        XCTAssertEqual(planned.filter { $0.kind == .nudge }.map(\.id), ["comlogue.local.nudge.8"])
    }

    func testServerPushReplacesLocalEventPrepCheckInsAndNudges() {
        var plan = input(now: "2026-10-27T00:30:00Z")
        plan.events = [PlannedEvent(id: "evt_1", title: "Final round at Northwind", date: "2026-10-29", time: nil)]
        XCTAssertTrue(NotificationPlanner.plan(plan).contains { $0.kind == .eventPrep })
        plan.serverSendsPush = true
        let planned = NotificationPlanner.plan(plan)
        XCTAssertTrue(planned.allSatisfy { $0.kind == .practice })
        XCTAssertFalse(planned.isEmpty)
    }

    func testEventPrepAndCheckInTimes() {
        var plan = input(now: "2026-10-27T00:30:00Z")
        plan.practiceDays = []
        plan.settings.nudges = false
        plan.events = [PlannedEvent(id: "evt_1", title: "Final round", date: "2026-10-29", time: "11:00")]
        let planned = NotificationPlanner.plan(plan)
        let byId = Dictionary(uniqueKeysWithValues: planned.map { ($0.id, $0) })
        // Eve at 19:00 IST = 13:30 UTC; morning-of 2 h before 11:00 = 09:00 IST = 03:30 UTC; check-in next day 19:00.
        XCTAssertEqual(byId["comlogue.local.event_eve.evt_1"]?.fireDate, instant("2026-10-28T13:30:00Z"))
        XCTAssertEqual(byId["comlogue.local.event_day.evt_1"]?.fireDate, instant("2026-10-29T03:30:00Z"))
        XCTAssertEqual(byId["comlogue.local.check_in.evt_1"]?.fireDate, instant("2026-10-30T13:30:00Z"))
        XCTAssertEqual(byId["comlogue.local.event_eve.evt_1"]?.title, "Tomorrow: Final round")
    }

    func testQuietHoursMoveNudgesButNotTheChosenPracticeTime() {
        var plan = input(now: "2026-10-27T00:30:00Z")
        plan.reminderTime = "23:00" // inside the default 22:00–08:00 quiet hours
        let planned = NotificationPlanner.plan(plan)
        let practice = planned.first { $0.kind == .practice }
        XCTAssertEqual(practice.map { HabitMath.dayString($0.fireDate, timeZone: ist) }, "2026-10-28")
        XCTAssertEqual(practice?.fireDate, instant("2026-10-28T17:30:00Z")) // 23:00 IST, as chosen
        // The 3-day nudge would also be 23:00; it moves to 08:00 the next morning.
        let nudge = planned.first { $0.id == "comlogue.local.nudge.3" }
        XCTAssertEqual(nudge?.fireDate, instant("2026-10-31T02:30:00Z"))
    }

    func testQuietHoursHelper() {
        let settings = NotificationSettings.defaults // 22:00–08:00
        // 23:30 IST → 08:00 the next day.
        XCTAssertEqual(NotificationPlanner.respectingQuietHours(instant("2026-10-27T18:00:00Z"), settings: settings, timeZone: ist),
                       instant("2026-10-28T02:30:00Z"))
        // 06:00 IST → 08:00 the same day.
        XCTAssertEqual(NotificationPlanner.respectingQuietHours(instant("2026-10-27T00:30:00Z"), settings: settings, timeZone: ist),
                       instant("2026-10-27T02:30:00Z"))
        // 12:00 IST is outside quiet hours.
        XCTAssertEqual(NotificationPlanner.respectingQuietHours(instant("2026-10-27T06:30:00Z"), settings: settings, timeZone: ist),
                       instant("2026-10-27T06:30:00Z"))
        var lunch = settings
        lunch.quietStart = "13:00"
        lunch.quietEnd = "14:00"
        XCTAssertEqual(NotificationPlanner.respectingQuietHours(instant("2026-10-27T08:00:00Z"), settings: lunch, timeZone: ist),
                       instant("2026-10-27T08:30:00Z"))
    }

    func testRemindMeLaterStaysOutOfQuietHours() {
        let settings = NotificationSettings.defaults // 22:00–08:00
        func snooze(_ iso: String) -> Date { NotificationPlanner.snoozeDate(now: instant(iso), settings: settings, timeZone: ist) }
        // 13:00 IST → 15:00.
        XCTAssertEqual(snooze("2026-10-27T07:30:00Z"), instant("2026-10-27T09:30:00Z"))
        // 20:30 IST → 21:30 (two hours would be 22:30).
        XCTAssertEqual(snooze("2026-10-27T15:00:00Z"), instant("2026-10-27T16:00:00Z"))
        // 21:15 IST → 21:50, just before quiet hours.
        XCTAssertEqual(snooze("2026-10-27T15:45:00Z"), instant("2026-10-27T16:20:00Z"))
        // 21:50 IST → 08:00 the next morning.
        XCTAssertEqual(snooze("2026-10-27T16:20:00Z"), instant("2026-10-28T02:30:00Z"))
        // 06:30 IST → 08:30, after quiet hours end.
        XCTAssertEqual(snooze("2026-10-27T01:00:00Z"), instant("2026-10-27T03:00:00Z"))
        // 05:00 IST, inside quiet hours → 08:00 when they end.
        XCTAssertEqual(snooze("2026-10-26T23:30:00Z"), instant("2026-10-27T02:30:00Z"))
    }

    func testAtMostTwoPerDayWithEventPrepFirst() {
        // Wednesday 28 Oct: practice 08:00, and an event on the 29th puts its 19:00 eve reminder on the 28th, plus a
        // check-in for an event on the 27th.
        var plan = input(now: "2026-10-27T00:30:00Z")
        plan.settings.nudges = false
        plan.events = [
            PlannedEvent(id: "a", title: "Pitch", date: "2026-10-29", time: nil),
            PlannedEvent(id: "b", title: "Viva", date: "2026-10-27", time: nil),
        ]
        let onThe28th = NotificationPlanner.plan(plan).filter { HabitMath.dayString($0.fireDate, timeZone: ist) == "2026-10-28" }
        XCTAssertEqual(onThe28th.count, 2)
        XCTAssertEqual(Set(onThe28th.map(\.kind)), [.eventPrep, .checkIn])
    }

    func testDaylightSavingInNewYork() {
        // Friday 30 Oct 2026, noon in New York; clocks fall back on Sunday 1 Nov.
        var plan = NotificationPlanInput(now: instant("2026-10-30T16:00:00Z"), timeZone: newYork)
        plan.practiceDays = [6, 7]
        plan.reminderTime = "08:00"
        plan.settings.nudges = false
        let fires = NotificationPlanner.plan(plan).map(\.fireDate)
        XCTAssertEqual(fires, [instant("2026-10-31T12:00:00Z"), instant("2026-11-01T13:00:00Z")])
    }

    func testIdentifiersAreStableAndPrefixed() {
        let plan = input(now: "2026-10-27T00:30:00Z")
        let first = NotificationPlanner.plan(plan)
        let second = NotificationPlanner.plan(plan)
        XCTAssertEqual(first.map(\.id), second.map(\.id))
        XCTAssertTrue(first.allSatisfy { $0.id.hasPrefix(NotificationPlanner.identifierPrefix) })
        XCTAssertLessThanOrEqual(first.count, NotificationPlanner.maxPending)
    }
}

final class EventClassifierTests: XCTestCase {
    func testRecognisesMomentsWorthPreparingFor() {
        XCTAssertEqual(EventClassifier.kind(for: "Final round interview – Northwind"), "interview")
        XCTAssertEqual(EventClassifier.kind(for: "Campus placement drive: Zenith Systems"), "placement")
        XCTAssertEqual(EventClassifier.kind(for: "GD round + HR"), "group_discussion")
        XCTAssertEqual(EventClassifier.kind(for: "Weekly sync with client (US)"), "client_call")
        XCTAssertEqual(EventClassifier.kind(for: "Mid-year review with Elena"), "appraisal")
        XCTAssertEqual(EventClassifier.kind(for: "Pitch to Seed fund"), "presentation")
        XCTAssertEqual(EventClassifier.kind(for: "Thesis viva"), "viva")
        XCTAssertEqual(EventClassifier.kind(for: "Priya's wedding"), "social")
    }

    func testIgnoresRoutineEntries() {
        XCTAssertNil(EventClassifier.kind(for: "Dentist"))
        XCTAssertNil(EventClassifier.kind(for: "Gym"))
        XCTAssertNil(EventClassifier.kind(for: "Daily standup"))
        XCTAssertNil(EventClassifier.kind(for: "Pick up groceries"))
    }
}
