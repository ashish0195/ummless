import Foundation
import WidgetKit

/// Keeps the home- and lock-screen widgets in step with the app's data.
enum WidgetBridge {
    private static var sharedDefaults: UserDefaults? { UserDefaults(suiteName: WidgetSnapshot.appGroup) }

    static func update(daily: DailyRep?, progress: ProgressSummary?, me: Me?) {
        let zone = TimeZone.current
        let week = progress?.practice.thisWeek
        let snapshot = WidgetSnapshot(
            day: daily?.date ?? HabitMath.dayString(Date(), timeZone: zone),
            repTitle: daily?.title,
            repPrompt: daily?.prompt,
            repCompleted: daily?.completed ?? false,
            weekSessions: week?.sessions ?? 0,
            weekTarget: week?.target ?? me?.practiceSettings.weeklyTarget ?? 3,
            weekDays: week?.days ?? [],
            weeksOnTarget: progress?.practice.weeksOnTarget ?? 0,
            pausedUntil: me?.practiceSettings.pausedUntil,
            timeZoneIdentifier: zone.identifier)
        if snapshot.save(to: sharedDefaults) {
            WidgetCenter.shared.reloadAllTimelines()
        }
    }

    static func clear() {
        sharedDefaults?.removeObject(forKey: WidgetSnapshot.storageKey)
        WidgetCenter.shared.reloadAllTimelines()
    }
}
