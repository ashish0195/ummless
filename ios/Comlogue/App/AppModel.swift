import Foundation
import Observation
import SwiftUI

enum AppTab: Hashable {
    case today, course, practice, you
}

struct SparLaunch: Hashable {
    var title: String
    var personaId: String?
    var customScenario: String?
    var difficulty: Difficulty
    var eventId: String?
    var prepId: String?
}

/// Full-screen flows that can be started from anywhere in the app.
enum AppFlow: Identifiable, Hashable {
    case getStarted
    case guidedAssessment(resumeId: String?)
    case gapFill(activityId: ActivityId)
    case upload
    case liveRecording
    case recordingDetail(id: String)
    case voiceSetup
    case mission(id: String, quick: Bool)
    case spar(SparLaunch)
    case paywall
    case weeklyReview
    case daily(date: String?)
    case group(panelId: String)
    case inbox
    case event(id: String)
    case notificationSettings
    case practicePlan
    case report(conversationId: String, title: String)

    var id: String {
        switch self {
        case .getStarted: return "getStarted"
        case .guidedAssessment(let id): return "assessment-\(id ?? "new")"
        case .gapFill(let activity): return "gap-\(activity)"
        case .upload: return "upload"
        case .liveRecording: return "live"
        case .recordingDetail(let id): return "recording-\(id)"
        case .voiceSetup: return "voiceSetup"
        case .mission(let id, let quick): return "mission-\(id)-\(quick)"
        case .spar(let launch): return "spar-\(launch.hashValue)"
        case .paywall: return "paywall"
        case .weeklyReview: return "weeklyReview"
        case .daily(let date): return "daily-\(date ?? "today")"
        case .group(let panelId): return "group-\(panelId)"
        case .inbox: return "inbox"
        case .event(let id): return "event-\(id)"
        case .notificationSettings: return "notificationSettings"
        case .practicePlan: return "practicePlan"
        case .report(let id, _): return "report-\(id)"
        }
    }
}

/// App-wide state: session, cached server data, and navigation between flows.
@MainActor
@Observable
final class AppModel {
    enum Phase: Equatable {
        case launching, onboarding, ready
        case failed(String)
    }

    let api: APIClient
    let player = AudioPlayer()
    let speech = SpeechFallback()
    let store = StoreManager()
    let notifications = NotificationManager.shared

    var phase: Phase = .launching
    var meta: Meta?
    var me: Me?
    var profile: Profile?
    var course: Course?
    var progress: ProgressSummary?
    var daily: DailyRep?
    var upcomingReps: [DailyRepPreview] = []
    var inbox: [InboxNotification] = []
    var unreadCount = 0
    var events: [UpcomingEvent] = []
    var panels: [Panel] = []
    /// The server pushes event prep, check-ins and nudges, so the device only schedules practice reminders.
    var serverSendsPush = false
    /// A milestone earned since the person last looked, celebrated once.
    var celebration: Milestone?
    var activeFlow: AppFlow?
    var selectedTab: AppTab = .today
    var toast: String?
    /// Bumped whenever results change so screens can reload.
    var dataVersion = 0

    var isDemo: Bool { meta?.demoMode ?? me?.demoMode ?? false }
    var isPro: Bool { me?.entitlement.isPro ?? false }
    var language: String { me?.onboarding.language ?? "en" }
    /// The server's market once a region is set; before that, the device's region is the better guess.
    var market: Market {
        guard let region = me?.onboarding.region else { return Market.from(region: RegionPreference.best) }
        return me?.market ?? Market.from(region: region)
    }
    /// On-device voice for spoken fallbacks: Hinglish and English in India read best with an Indian English voice.
    var speechLanguage: String {
        if language == "hinglish" { return "en-IN" }
        if language == "en" && market == .in { return "en-IN" }
        return language
    }
    var pricing: Pricing? { meta?.pricing(for: market) }
    private var lastDeviceRegistration: DeviceRegistration?
    private var lastActiveRefresh: Date?

    init() {
        api = APIClient(baseURL: AppConfig.baseURL, token: DeviceIdentity.token)
        api.reauthenticate = { [weak self] in
            guard let self else { return false }
            return await self.authenticate()
        }
        store.forwardTransaction = { [weak self] jws in
            guard let self else { return false }
            return await self.submitTransaction(jws)
        }
        notifications.onTokenChange = { [weak self] in
            Task { await self?.syncDevice() }
        }
    }

    // MARK: Session

    func bootstrap() async {
        phase = .launching
        api.updateBaseURL(AppConfig.baseURL)
        #if DEBUG
        if let scene = ScreenshotScene.current {
            await runScreenshotScene(scene)
            return
        }
        #endif
        do {
            if api.token == nil {
                guard await authenticate() else { throw APIError.network("Could not sign in") }
            }
            async let metaRequest = api.meta()
            async let meRequest = api.me()
            let (meta, me) = try await (metaRequest, meRequest)
            self.meta = meta
            self.me = me
            if me.onboarding.completed {
                phase = .ready
                await refreshAll()
                if !me.hasResults && !LocalFlags.hasSeenFirstRun && LocalFlags.activeAssessmentId == nil {
                    activeFlow = .getStarted
                }
            } else {
                phase = .onboarding
            }
            store.startListening()
            await syncDevice()
        } catch {
            phase = .failed(error.userMessage)
        }
    }

    @discardableResult
    func authenticate() async -> Bool {
        do {
            let response = try await api.authenticateDevice(deviceId: DeviceIdentity.deviceId, appVersion: AppConfig.appVersion)
            api.token = response.token
            DeviceIdentity.token = response.token
            return true
        } catch {
            return false
        }
    }

    func completeOnboarding(_ patch: MePatch) async throws {
        let updated = try await api.updateMe(patch)
        me = updated
        phase = .ready
        await refreshAll()
        activeFlow = .getStarted
    }

    // MARK: Data

    func refreshAll() async {
        async let meTask: Void = refreshMe()
        async let profileTask: Void = refreshProfile()
        async let courseTask: Void = refreshCourse()
        async let progressTask: Void = refreshProgress()
        async let dailyTask: Void = refreshDaily()
        async let inboxTask: Void = refreshInbox()
        async let eventsTask: Void = refreshEvents()
        async let panelsTask: Void = refreshPanels()
        _ = await (meTask, profileTask, courseTask, progressTask, dailyTask, inboxTask, eventsTask, panelsTask)
        dataVersion += 1
        afterRefresh()
    }

    /// Everything that depends on fresh data: widgets, scheduled reminders and celebrations.
    private func afterRefresh() {
        WidgetBridge.update(daily: daily, progress: progress, me: me)
        Task { await rescheduleNotifications() }
        checkForCelebration()
    }

    func refreshDaily() async {
        async let todayRequest = try? api.dailyRep()
        async let upcomingRequest = try? api.upcomingReps(days: 9)
        let (today, upcoming) = await (todayRequest, upcomingRequest)
        if let today { daily = today }
        if let upcoming { upcomingReps = upcoming }
    }

    func refreshInbox() async {
        guard let response = try? await api.notifications() else { return }
        inbox = response.items
        unreadCount = response.unreadCount
        notifications.setBadge(response.unreadCount)
    }

    func refreshEvents() async {
        if let updated = try? await api.events() { events = updated }
    }

    func refreshPanels() async {
        if let updated = try? await api.panels() { panels = updated }
    }

    func refreshMe() async {
        if let updated = try? await api.me() { me = updated }
    }

    func refreshProfile() async {
        if let updated = try? await api.profile() { profile = updated }
    }

    func refreshCourse() async {
        if let updated = try? await api.course() { course = updated }
    }

    func refreshProgress() async {
        if let updated = try? await api.progress() { progress = updated }
    }

    func updateMe(_ patch: MePatch) async throws {
        me = try await api.updateMe(patch)
        WidgetBridge.update(daily: daily, progress: progress, me: me)
        await rescheduleNotifications()
    }

    /// Back in the foreground: the day may have rolled over, the timezone changed, or new results arrived.
    func becameActive() async {
        guard phase == .ready else { return }
        if let last = lastActiveRefresh, Date().timeIntervalSince(last) < 120 { return }
        lastActiveRefresh = Date()
        await syncDevice()
        async let dailyTask: Void = refreshDaily()
        async let inboxTask: Void = refreshInbox()
        async let progressTask: Void = refreshProgress()
        _ = await (dailyTask, inboxTask, progressTask)
        afterRefresh()
    }

    // MARK: Notifications

    /// Tells the server about this install: APNs token, permission, timezone and locale.
    func syncDevice() async {
        guard api.token != nil else { return }
        await notifications.refreshStatus()
        let registration = DeviceRegistration(
            apnsToken: notifications.deviceToken,
            pushEnvironment: notifications.deviceToken == nil ? nil : AppConfig.pushEnvironment,
            authorization: notifications.authorizationName,
            timezone: TimeZone.current.identifier,
            locale: Locale.current.identifier(.bcp47),
            appVersion: AppConfig.appVersion)
        guard registration != lastDeviceRegistration else { return }
        if let device = try? await api.registerDevice(registration) {
            lastDeviceRegistration = registration
            serverSendsPush = device.pushEnabled
            await rescheduleNotifications()
        }
    }

    /// Plans this week's on-device reminders from the person's plan, prompts and events.
    func rescheduleNotifications() async {
        guard let me, phase == .ready else { return }
        await notifications.refreshStatus()
        guard notifications.canDeliver else {
            await notifications.removeAllLocal()
            return
        }
        let zone = TimeZone.current
        let now = Date()
        let practice = me.practiceSettings
        let practicedToday = daily?.completed == true
            || (progress?.practice.thisWeek.days ?? []).contains(HabitMath.weekday(now, timeZone: zone))
        var input = NotificationPlanInput(now: now, timeZone: zone)
        input.settings = me.resolvedNotificationSettings
        input.practiceDays = practice.reminderDays
        input.reminderTime = practice.reminderTime
        input.anchor = practice.anchor
        input.pausedUntil = practice.pausedUntil
        input.weeklyTarget = practice.weeklyTarget
        input.practicedToday = practicedToday
        input.practicedThisWeek = practicedToday || (progress?.practice.thisWeek.sessions ?? 0) > 0
        input.upcomingReps = upcomingReps
        input.events = events.map { PlannedEvent(id: $0.id, title: $0.title, date: $0.date, time: $0.time) }
        input.serverSendsPush = serverSendsPush
        notifications.settings = input.settings
        await notifications.apply(NotificationPlanner.plan(input))
    }

    func markRead(_ notification: InboxNotification) async {
        guard !notification.read else { return }
        if let count = try? await api.markNotificationsRead(ids: [notification.id]) {
            unreadCount = count
            notifications.setBadge(count)
        }
        inbox = inbox.map { item in
            guard item.id == notification.id else { return item }
            return InboxNotification(id: item.id, category: item.category, title: item.title, body: item.body,
                                     deepLink: item.deepLink, createdAt: item.createdAt, read: true)
        }
    }

    func markAllRead() async {
        if let count = try? await api.markAllNotificationsRead() {
            unreadCount = count
            notifications.setBadge(count)
            await refreshInbox()
        }
    }

    // MARK: Deep links

    /// Opens whatever a notification, widget or link asked for, once the app is ready.
    func handlePendingLinks() {
        guard phase == .ready, let pending = PendingLink.dequeue() else { return }
        if let id = pending.notificationId {
            Task {
                try? await api.notificationOpened(id)
                await refreshInbox()
            }
        }
        open(pending.link)
    }

    func open(_ link: DeepLink) {
        switch link {
        case .today:
            selectedTab = .today
            if activeFlow != nil { dismissFlow(refresh: false) }
        case .daily(let date):
            present(.daily(date: date))
        case .mission(let id), .reflect(let id):
            present(.mission(id: id, quick: false))
        case .recording(let id):
            present(.recordingDetail(id: id))
        case .assessment(let id):
            present(.guidedAssessment(resumeId: id))
        case .event(let id):
            present(.event(id: id))
        case .weeklyReview:
            present(.weeklyReview)
        case .inbox:
            present(.inbox)
        case .practice:
            selectedTab = .practice
            if activeFlow != nil { dismissFlow(refresh: false) }
        case .group(let panelId):
            present(.group(panelId: panelId))
        case .paywall:
            present(.paywall)
        case .notificationSettings:
            present(.notificationSettings)
        }
    }

    // MARK: Celebrations

    /// Shows the newest milestone the person hasn't seen yet. The first launch just records what exists.
    private func checkForCelebration() {
        guard let milestones = progress?.milestones, phase == .ready else { return }
        var seen = LocalFlags.seenMilestones
        if seen == nil {
            LocalFlags.seenMilestones = Set(milestones.map(\.id))
            return
        }
        let fresh = milestones.filter { !(seen?.contains($0.id) ?? false) }.sorted { $0.achievedAt > $1.achievedAt }
        guard let newest = fresh.first else { return }
        seen?.formUnion(fresh.map(\.id))
        LocalFlags.seenMilestones = seen
        if activeFlow == nil { celebration = newest }
    }

    // MARK: Flows

    func present(_ flow: AppFlow) {
        player.stop()
        speech.stop()
        if activeFlow != nil || celebration != nil {
            // Replace the current flow (or a celebration sheet) after it dismisses; only one can be on screen.
            activeFlow = nil
            celebration = nil
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 450_000_000)
                self.activeFlow = flow
            }
        } else {
            activeFlow = flow
        }
    }

    func dismissFlow(refresh: Bool = true) {
        player.stop()
        speech.stop()
        activeFlow = nil
        if refresh { Task { await refreshAll() } }
    }

    func showToast(_ message: String) {
        toast = message
        Task { @MainActor in
            try? await Task.sleep(nanoseconds: 2_400_000_000)
            if self.toast == message { self.toast = nil }
        }
    }

    // MARK: Purchases

    func submitTransaction(_ jws: String) async -> Bool {
        do {
            _ = try await api.submitAppStoreTransaction(jws)
            await refreshMe()
            await refreshCourse()
            return true
        } catch {
            return false
        }
    }

    func devGrantPro() async -> Bool {
        do {
            _ = try await api.devGrant(tier: "pro")
            await refreshMe()
            await refreshCourse()
            return true
        } catch {
            return false
        }
    }

    // MARK: Account

    func deleteEverything() async throws {
        try await api.deleteAccount()
        DeviceIdentity.reset()
        LocalFlags.reset()
        await notifications.removeAllLocal()
        notifications.setBadge(0)
        WidgetBridge.clear()
        api.token = nil
        lastDeviceRegistration = nil
        me = nil
        profile = nil
        course = nil
        progress = nil
        daily = nil
        upcomingReps = []
        inbox = []
        unreadCount = 0
        events = []
        activeFlow = nil
        selectedTab = .today
        await bootstrap()
    }

    func changeServer(to url: String?) async {
        AppConfig.baseURLOverride = url
        DeviceIdentity.token = nil
        api.token = nil
        await bootstrap()
    }
}
