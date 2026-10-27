import SwiftUI

/// The first-run walkthrough, shown once: welcome → goal → practice time → privacy. One question per screen.
/// The spec's onboarding answers (ranked contexts, what should feel easier) are derived from the goal, and the
/// language is a small control on the welcome screen, so newcomers face as few decisions as possible.
@MainActor
@Observable
final class OnboardingModel {
    enum Step: Int, CaseIterable {
        case welcome, goal, reminder, consent
    }

    var step: Step = .welcome
    var goalTrack: String?
    var language: String = OnboardingModel.deviceLanguage
    var isSaving = false
    var error: String?
    // Practice plan
    var weeklyTarget = 3
    var routineId = "morning"
    var remindersOn = true
    // Consent
    var ageConfirmed = false

    static var deviceLanguage: String {
        String((Locale.preferredLanguages.first ?? "en").prefix(2))
    }

    var progressIndex: Int { max(0, step.rawValue - 1) }
    var progressTotal: Int { Step.allCases.count - 1 }

    func next() {
        guard let next = Step(rawValue: step.rawValue + 1) else { return }
        Haptics.tap()
        step = next
    }

    func back() {
        guard let previous = Step(rawValue: step.rawValue - 1) else { return }
        step = previous
    }

    func routine(for market: Market) -> PracticeRoutine {
        let options = PracticeRoutine.options(for: market)
        return options.first { $0.id == routineId } ?? options[0]
    }

    func patch(consentVersion: String, market: Market) -> MePatch {
        let goal = goalTrack ?? "business"
        let answers = GoalChoice.answers(for: goal)
        let routine = routine(for: market)
        return MePatch(
            onboarding: .init(
                completed: true,
                contextsRanked: answers.contexts,
                easeTargets: answers.ease,
                goalTrack: goal,
                language: language,
                region: RegionPreference.best,
                analysisConsentVersion: consentVersion,
                ageConfirmed: ageConfirmed
            ),
            practiceSettings: .init(weeklyTarget: weeklyTarget, reminderTime: routine.time,
                                    reminderDays: remindersOn ? HabitMath.defaultDays(forTarget: weeklyTarget) : [],
                                    anchor: routine.anchor)
        )
    }
}

struct OnboardingFlowView: View {
    @Environment(AppModel.self) private var app
    @State private var model = OnboardingModel()

    var body: some View {
        VStack(spacing: 0) {
            if model.step != .welcome {
                HStack(spacing: 16) {
                    CircleIconButton(systemName: "chevron.left") { withAnimation { model.back() } }
                    ProgressDots(current: model.progressIndex, total: model.progressTotal)
                    Spacer()
                    // Balances the back button so the dots sit in the middle.
                    Color.clear.frame(width: 40, height: 40)
                }
                .padding(.horizontal, Theme.gutter)
                .padding(.top, 8)
            }
            Group {
                switch model.step {
                case .welcome: WelcomeStep(model: model)
                case .goal: GoalStep(model: model)
                case .reminder: ReminderStep(model: model)
                case .consent: AnalysisConsentStep(model: model)
                }
            }
            .transition(.asymmetric(insertion: .move(edge: .trailing).combined(with: .opacity),
                                    removal: .move(edge: .leading).combined(with: .opacity)))
            .id(model.step)
        }
        .animation(.spring(response: 0.45, dampingFraction: 0.9), value: model.step)
        .screenBackground()
        #if DEBUG
        .onAppear { model.applyScreenshotScene(market: app.market) }
        #endif
    }
}

private struct ProgressDots: View {
    let current: Int
    let total: Int

    var body: some View {
        HStack(spacing: 8) {
            ForEach(0..<total, id: \.self) { index in
                Capsule()
                    .fill(index <= current ? AnyShapeStyle(Theme.aurora) : AnyShapeStyle(Theme.stroke))
                    .frame(width: index == current ? 28 : 8, height: 8)
            }
        }
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Step \(current + 1) of \(total)")
    }
}

/// Title, optional subtitle, the choices, and the buttons pinned to the bottom.
private struct OnboardingPage<Content: View, Footer: View>: View {
    let title: String
    var subtitle: String?
    @ViewBuilder let content: Content
    @ViewBuilder let footer: Footer

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text(title)
                        .font(.system(size: 34, weight: .bold, design: .rounded))
                        .foregroundStyle(Theme.ink)
                        .fixedSize(horizontal: false, vertical: true)
                    if let subtitle {
                        Text(subtitle).font(.body).foregroundStyle(Theme.inkSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    content.padding(.top, 16)
                }
                .padding(.horizontal, Theme.gutter)
                .padding(.vertical, 24)
            }
            VStack(spacing: 8) { footer }
                .padding(.horizontal, Theme.gutter)
                .padding(.bottom, 12)
        }
    }
}

/// A large, single-choice row.
private struct ChoiceRow: View {
    let symbol: String
    let title: String
    var detail: String?
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 16) {
                Image(systemName: symbol)
                    .font(.title3)
                    .foregroundStyle(selected ? Color.white : Theme.indigo)
                    .frame(width: 46, height: 46)
                    .background(selected ? AnyShapeStyle(Theme.aurora) : AnyShapeStyle(Theme.indigo.opacity(0.1)), in: Circle())
                Text(title).font(.headlineRounded).foregroundStyle(Theme.ink).multilineTextAlignment(.leading)
                Spacer(minLength: 8)
                if let detail {
                    Text(detail).font(.subheadline).foregroundStyle(Theme.inkSecondary)
                }
                if selected {
                    Image(systemName: "checkmark.circle.fill").font(.title3).foregroundStyle(Theme.indigo)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.radius, style: .continuous)
                    .strokeBorder(selected ? Theme.indigo : Theme.stroke, lineWidth: selected ? 2 : 1)
            )
        }
        .buttonStyle(.pressableCard)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}

// MARK: - Steps

private struct WelcomeStep: View {
    @Environment(AppModel.self) private var app
    @Bindable var model: OnboardingModel

    private var languages: [LanguageOption] {
        app.meta?.languages ?? [LanguageOption(code: "en", name: "English")]
    }

    private var languageName: String {
        if model.language == "hinglish" { return "Hinglish" }
        return languages.first { $0.code == model.language }?.name ?? "English"
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Spacer()
                // The practice language: the AI partner speaks it and feedback is written in it.
                Menu {
                    Picker("Practice language", selection: $model.language) {
                        ForEach(languages) { language in
                            Text(language.name).tag(language.code)
                        }
                    }
                } label: {
                    Label(languageName, systemImage: "globe")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(Theme.ink)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 9)
                        .background(Theme.surface, in: Capsule())
                        .overlay(Capsule().strokeBorder(Theme.stroke))
                }
                .accessibilityLabel("Practice language: \(languageName)")
            }
            .padding(.top, 12)
            Spacer(minLength: 12)
            VoiceOrb(level: 0.25)
                .frame(maxWidth: 260, maxHeight: 260)
                .aspectRatio(1, contentMode: .fit)
            Spacer(minLength: 12)
            VStack(spacing: 14) {
                Text("Say what you mean.\nBe understood.")
                    .font(.system(size: 38, weight: .heavy, design: .rounded))
                    .foregroundStyle(Theme.ink)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
                Text("A friendly AI coach. One minute a day.")
                    .font(.title3)
                    .foregroundStyle(Theme.inkSecondary)
                    .multilineTextAlignment(.center)
            }
            Spacer(minLength: 28)
            Button("Get started") { model.next() }
                .buttonStyle(.primaryPill)
        }
        .padding(.horizontal, Theme.gutter)
        .padding(.bottom, 12)
        .onAppear {
            if !languages.contains(where: { $0.code == model.language }) { model.language = "en" }
        }
    }
}

private struct GoalStep: View {
    @Environment(AppModel.self) private var app
    @Bindable var model: OnboardingModel

    var body: some View {
        OnboardingPage(title: "What do you want to get better at?", subtitle: "Pick one to start. You can change it any time.") {
            VStack(spacing: 10) {
                ForEach(GoalChoice.ordered(for: app.market, available: (app.meta?.tracks ?? []).map(\.id))) { choice in
                    ChoiceRow(symbol: choice.symbol, title: choice.title, selected: model.goalTrack == choice.id) {
                        Haptics.selection()
                        model.goalTrack = choice.id
                        // One tap is the answer: move on once the selection has registered.
                        Task {
                            try? await Task.sleep(nanoseconds: 280_000_000)
                            if model.step == .goal { model.next() }
                        }
                    }
                }
            }
        } footer: {
            EmptyView()
        }
    }
}

private struct ReminderStep: View {
    @Environment(AppModel.self) private var app
    @Bindable var model: OnboardingModel
    @State private var showPriming = false

    var body: some View {
        OnboardingPage(title: "When will you practise?", subtitle: "One minute is enough. We'll send a gentle reminder.") {
            VStack(spacing: 10) {
                ForEach(PracticeRoutine.options(for: app.market)) { routine in
                    ChoiceRow(symbol: routine.symbol, title: routine.title,
                              detail: PracticePlanEditor.displayTime(routine.time),
                              selected: model.routineId == routine.id) {
                        Haptics.selection()
                        model.routineId = routine.id
                    }
                }
                Picker("How often", selection: $model.weeklyTarget) {
                    Text("3 days a week").tag(3)
                    Text("5 days").tag(5)
                    Text("Every day").tag(7)
                }
                .pickerStyle(.segmented)
                .padding(.top, 14)
            }
        } footer: {
            Button("Continue") { continueTapped(reminders: true) }
                .buttonStyle(.primaryPill)
            Button("No reminders") { continueTapped(reminders: false) }
                .buttonStyle(.ghostPill)
        }
        .sheet(isPresented: $showPriming, onDismiss: { model.next() }) {
            NotificationPrimingView(summary: summary) { showPriming = false }
                .environment(app)
                .presentationDetents([.large])
        }
    }

    private var summary: String {
        let routine = model.routine(for: app.market)
        return "\(routine.title.lowercased()), \(PracticePlanEditor.displayTime(routine.time))"
    }

    private func continueTapped(reminders: Bool) {
        model.remindersOn = reminders
        Task {
            await app.notifications.refreshStatus()
            if reminders && app.notifications.status == .notDetermined {
                showPriming = true
            } else {
                model.next()
            }
        }
    }
}

private struct AnalysisConsentStep: View {
    @Environment(AppModel.self) private var app
    @Bindable var model: OnboardingModel
    @State private var showFullText = false
    @State private var showDeclineInfo = false
    @State private var readInHindi = false

    private var consent: ConsentText? { app.meta?.consents.analysis }
    private var text: ConsentTranslation? { consent?.localized(readInHindi ? "hi" : nil) }
    private var hasHindi: Bool { consent?.translations?["hi"] != nil }

    var body: some View {
        OnboardingPage(title: text?.title ?? "Your voice, your call") {
            VStack(alignment: .leading, spacing: 16) {
                ForEach(text?.bullets ?? defaultBullets, id: \.self) { bullet in
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: "checkmark.shield.fill").foregroundStyle(Theme.mint)
                        Text(bullet).font(.subheadline).foregroundStyle(Theme.ink)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                HStack(spacing: 18) {
                    if text?.body != nil {
                        Button("Read the full text") { showFullText = true }
                    }
                    if hasHindi && (app.market == .in || readInHindi) {
                        Button(readInHindi ? "Read in English" : "हिन्दी में पढ़ें") { readInHindi.toggle() }
                    }
                }
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(Theme.indigo)
                .padding(.top, 4)
            }
        } footer: {
            // The age check sits with the button it unlocks, so long (e.g. Hindi) text never hides it.
            Toggle(isOn: $model.ageConfirmed) {
                Text("I'm 18 or older").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
            }
            .toggleStyle(CheckboxToggleStyle())
            if let error = model.error { InlineErrorBanner(message: error) }
            Button {
                Task { await agree() }
            } label: {
                if model.isSaving { ProgressView().tint(.white) } else { Text("Agree and continue") }
            }
            .buttonStyle(.primaryPill)
            .disabled(model.isSaving || app.meta == nil || !model.ageConfirmed)
            Button("Not now") { showDeclineInfo = true }
                .buttonStyle(.ghostPill)
        }
        .sheet(isPresented: $showFullText) {
            NavigationStack {
                ScrollView {
                    Text(text?.body ?? "").font(.body).foregroundStyle(Theme.ink).padding(Theme.gutter)
                }
                .navigationTitle("How Comlogue uses your voice")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { showFullText = false } } }
            }
        }
        .alert("Comlogue needs this to give feedback", isPresented: $showDeclineInfo) {
            Button("OK", role: .cancel) {}
        } message: {
            Text("Every route — AI conversations, uploads and recordings — relies on analysing your voice. You can come back whenever you're ready, and delete your data at any time.")
        }
        #if DEBUG
        .onAppear { if ScreenshotScene.current == .consentIndia && hasHindi { readInHindi = true } }
        #endif
    }

    private var defaultBullets: [String] {
        [
            "We analyse your speech with AI to give you feedback.",
            "Only speech we can confidently attribute to you is assessed.",
            "You can delete your recordings and results at any time.",
        ]
    }

    private func agree() async {
        guard let consent = app.meta?.consents.analysis else { return }
        model.isSaving = true
        model.error = nil
        defer { model.isSaving = false }
        do {
            try await app.completeOnboarding(model.patch(consentVersion: consent.version, market: app.market))
            Haptics.success()
        } catch {
            model.error = error.userMessage
        }
    }
}
