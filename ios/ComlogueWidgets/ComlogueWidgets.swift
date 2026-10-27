import SwiftUI
import WidgetKit

@main
struct ComlogueWidgetsBundle: WidgetBundle {
    var body: some Widget {
        TodayRepWidget()
        WeeklyPracticeWidget()
    }
}

// MARK: - Timeline

struct SnapshotEntry: TimelineEntry {
    let date: Date
    let snapshot: WidgetSnapshot
    let isPlaceholder: Bool
}

struct SnapshotProvider: TimelineProvider {
    private var stored: WidgetSnapshot? { WidgetSnapshot.load(from: UserDefaults(suiteName: WidgetSnapshot.appGroup)) }

    func placeholder(in context: Context) -> SnapshotEntry {
        SnapshotEntry(date: Date(), snapshot: .placeholder, isPlaceholder: true)
    }

    func getSnapshot(in context: Context, completion: @escaping (SnapshotEntry) -> Void) {
        completion(SnapshotEntry(date: Date(), snapshot: stored ?? .placeholder, isPlaceholder: stored == nil))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<SnapshotEntry>) -> Void) {
        let now = Date()
        let snapshot = stored ?? .placeholder
        // One entry now and one at local midnight, when yesterday's rep stops being "today's".
        let midnight = WidgetSnapshot.nextMidnight(after: now, timeZone: snapshot.timeZone)
        let entries = [
            SnapshotEntry(date: now, snapshot: snapshot, isPlaceholder: stored == nil),
            SnapshotEntry(date: midnight, snapshot: snapshot, isPlaceholder: stored == nil),
        ]
        completion(Timeline(entries: entries, policy: .after(midnight.addingTimeInterval(60))))
    }
}

// MARK: - Style

enum WidgetStyle {
    static let indigo = Color(red: 0.31, green: 0.27, blue: 0.90)
    static let violet = Color(red: 0.55, green: 0.36, blue: 0.96)
    static let coral = Color(red: 0.95, green: 0.44, blue: 0.54)
    static let aurora = LinearGradient(colors: [indigo, violet, coral], startPoint: .topLeading, endPoint: .bottomTrailing)
}

// MARK: - Today's rep

struct TodayRepWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "TodayRep", provider: SnapshotProvider()) { entry in
            TodayRepView(entry: entry)
                .containerBackground(for: .widget) { WidgetStyle.aurora }
                .widgetURL(WidgetLinks.dailyRep)
        }
        .configurationDisplayName("Today's practice")
        .description("Your 1-minute speaking practice for today, and how your week is going.")
        .supportedFamilies([.systemSmall, .systemMedium, .accessoryRectangular, .accessoryInline])
    }
}

struct TodayRepView: View {
    @Environment(\.widgetFamily) private var family
    let entry: SnapshotEntry

    private var snapshot: WidgetSnapshot { entry.snapshot }
    private var hasTodaysRep: Bool { entry.isPlaceholder || snapshot.isCurrent(at: entry.date) }
    private var title: String {
        if snapshot.isPaused(at: entry.date) { return "Enjoy your break" }
        if !hasTodaysRep { return "A new practice is ready" }
        if snapshot.repCompleted { return "Today's practice: done" }
        return snapshot.repTitle ?? "A new practice is ready"
    }

    var body: some View {
        switch family {
        case .accessoryInline:
            Label(title, systemImage: "waveform")
        case .accessoryRectangular:
            VStack(alignment: .leading, spacing: 2) {
                Label("Today's practice", systemImage: "waveform").font(.caption2.weight(.semibold))
                Text(title).font(.headline).lineLimit(2)
            }
        case .systemMedium:
            HStack(alignment: .top, spacing: 14) {
                repText
                Spacer(minLength: 0)
                WeekRing(done: weekDays, target: snapshot.weekTarget)
                    .frame(width: 64, height: 64)
            }
        default:
            repText
        }
    }

    private var repText: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label(snapshot.repCompleted && hasTodaysRep ? "Done today" : "Today's practice",
                  systemImage: snapshot.repCompleted && hasTodaysRep ? "checkmark.circle.fill" : "waveform")
                .font(.caption.weight(.bold))
                .foregroundStyle(.white.opacity(0.85))
            Text(title)
                .font(.system(.headline, design: .rounded).weight(.bold))
                .foregroundStyle(.white)
                .lineLimit(3)
                .minimumScaleFactor(0.85)
            Spacer(minLength: 0)
            WeekDots(days: entry.isPlaceholder ? snapshot.weekDays : snapshot.practisedDays(at: entry.date))
        }
    }

    /// Days practised this week: the unit of the weekly target.
    private var weekDays: Int { (entry.isPlaceholder ? snapshot.weekDays : snapshot.practisedDays(at: entry.date)).count }
}

// MARK: - Weekly practice

struct WeeklyPracticeWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "WeeklyPractice", provider: SnapshotProvider()) { entry in
            WeeklyPracticeView(entry: entry)
                .containerBackground(for: .widget) { WidgetStyle.aurora }
                .widgetURL(WidgetLinks.today)
        }
        .configurationDisplayName("This week")
        .description("The days you practised this week, against the target you chose.")
        .supportedFamilies([.systemSmall, .accessoryCircular])
    }
}

struct WeeklyPracticeView: View {
    @Environment(\.widgetFamily) private var family
    let entry: SnapshotEntry

    var body: some View {
        let snapshot = entry.snapshot
        // A new week starts from zero until the app refreshes the snapshot.
        let days = (entry.isPlaceholder ? snapshot.weekDays : snapshot.practisedDays(at: entry.date)).count
        if family == .accessoryCircular {
            Gauge(value: Double(min(days, max(snapshot.weekTarget, 1))),
                  in: 0...Double(max(snapshot.weekTarget, 1))) {
                Image(systemName: "waveform")
            } currentValueLabel: {
                Text("\(days)")
            }
            .gaugeStyle(.accessoryCircular)
        } else {
            VStack(alignment: .leading, spacing: 8) {
                Text("This week").font(.caption.weight(.bold)).foregroundStyle(.white.opacity(0.85))
                WeekRing(done: days, target: snapshot.weekTarget)
                    .frame(width: 70, height: 70)
                Text(snapshot.weeksOnTarget > 1 ? "\(snapshot.weeksOnTarget) weeks on target" : "One minute counts")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.white.opacity(0.9))
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
            }
        }
    }
}

// MARK: - Pieces

struct WeekRing: View {
    let done: Int
    let target: Int

    var body: some View {
        let progress = target > 0 ? min(1, Double(done) / Double(target)) : 0
        ZStack {
            Circle().stroke(Color.white.opacity(0.25), lineWidth: 7)
            Circle()
                .trim(from: 0, to: max(0.001, progress))
                .stroke(Color.white, style: StrokeStyle(lineWidth: 7, lineCap: .round))
                .rotationEffect(.degrees(-90))
            VStack(spacing: 0) {
                Text("\(done)").font(.system(.title3, design: .rounded).weight(.bold)).foregroundStyle(.white)
                Text("of \(target)").font(.system(size: 9, weight: .semibold)).foregroundStyle(.white.opacity(0.85))
            }
        }
    }
}

struct WeekDots: View {
    let days: [Int]
    private let initials = ["M", "T", "W", "T", "F", "S", "S"]

    var body: some View {
        HStack(spacing: 4) {
            ForEach(1...7, id: \.self) { day in
                Text(initials[day - 1])
                    .font(.system(size: 8, weight: .bold))
                    .frame(width: 14, height: 14)
                    .background(Circle().fill(days.contains(day) ? Color.white : Color.white.opacity(0.22)))
                    .foregroundStyle(days.contains(day) ? WidgetStyle.indigo : Color.white)
            }
        }
    }
}
