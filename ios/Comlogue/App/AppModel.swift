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

    var phase: Phase = .launching
    var meta: Meta?
    var me: Me?
    var profile: Profile?
    var course: Course?
    var progress: ProgressSummary?
    var activeFlow: AppFlow?
    var selectedTab: AppTab = .today
    var toast: String?
    /// Bumped whenever results change so screens can reload.
    var dataVersion = 0

    var isDemo: Bool { meta?.demoMode ?? me?.demoMode ?? false }
    var isPro: Bool { me?.entitlement.isPro ?? false }
    var language: String { me?.onboarding.language ?? "en" }

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
        _ = await (meTask, profileTask, courseTask, progressTask)
        dataVersion += 1
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
    }

    // MARK: Flows

    func present(_ flow: AppFlow) {
        player.stop()
        speech.stop()
        if activeFlow != nil {
            // Replace the current flow after the cover dismisses.
            activeFlow = nil
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
        ReminderScheduler.cancelAll()
        api.token = nil
        me = nil
        profile = nil
        course = nil
        progress = nil
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
