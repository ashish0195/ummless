import SwiftUI

@MainActor
@Observable
final class OnboardingModel {
    enum Step: Int, CaseIterable {
        case welcome, contexts, ease, goal, language, consent
    }

    var step: Step = .welcome
    var contextsRanked: [String] = []
    var easeTargets: Set<String> = []
    var goalTrack: String?
    var language: String = OnboardingModel.deviceLanguage
    var isSaving = false
    var error: String?

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

    func toggleRank(_ id: String) {
        Haptics.selection()
        if let index = contextsRanked.firstIndex(of: id) {
            contextsRanked.remove(at: index)
        } else {
            contextsRanked.append(id)
        }
    }

    func toggleEase(_ id: String) {
        Haptics.selection()
        if easeTargets.contains(id) { easeTargets.remove(id) } else { easeTargets.insert(id) }
    }

    /// Suggests a goal area from the ranked contexts and ease targets. The person can always pick another.
    func suggestedTrack(available: [Track]) -> String? {
        GoalSuggestion.suggest(contextsRanked: contextsRanked, easeTargets: easeTargets, available: available.map(\.id))
    }

    func patch(consentVersion: String, allContexts: [String]) -> MePatch {
        let ranked = contextsRanked + allContexts.filter { !contextsRanked.contains($0) }
        return MePatch(
            onboarding: .init(
                completed: true,
                contextsRanked: ranked,
                easeTargets: Array(easeTargets).sorted(),
                goalTrack: goalTrack,
                language: language,
                region: RegionPreference.best,
                analysisConsentVersion: consentVersion
            ),
            practiceSettings: nil
        )
    }
}

struct OnboardingFlowView: View {
    @Environment(AppModel.self) private var app
    @State private var model = OnboardingModel()

    var body: some View {
        VStack(spacing: 0) {
            if model.step != .welcome {
                HStack(spacing: 14) {
                    CircleIconButton(systemName: "chevron.left") { withAnimation { model.back() } }
                    StepProgressBar(current: model.progressIndex, total: model.progressTotal)
                    if app.isDemo { DemoBadge() }
                }
                .padding(.horizontal, Theme.gutter)
                .padding(.top, 8)
            }
            Group {
                switch model.step {
                case .welcome: WelcomeStep(model: model)
                case .contexts: ContextRankStep(model: model)
                case .ease: EaseStep(model: model)
                case .goal: GoalStep(model: model)
                case .language: LanguageStep(model: model)
                case .consent: AnalysisConsentStep(model: model)
                }
            }
            .transition(.asymmetric(insertion: .move(edge: .trailing).combined(with: .opacity),
                                    removal: .move(edge: .leading).combined(with: .opacity)))
            .id(model.step)
        }
        .animation(.spring(response: 0.45, dampingFraction: 0.9), value: model.step)
        .screenBackground()
    }
}

// MARK: - Steps

private struct WelcomeStep: View {
    @Environment(AppModel.self) private var app
    let model: OnboardingModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text(Brand.name).font(.headlineRounded).foregroundStyle(Theme.ink)
                Spacer()
                if app.isDemo { DemoBadge() }
            }
            .padding(.top, 12)
            // The copy below never compresses; the orb is the only flexible piece (up to 220 pt), so on
            // small phones it shrinks instead of the text getting truncated.
            VoiceOrb(level: 0.25)
                .frame(maxWidth: 220, maxHeight: 220)
                .aspectRatio(1, contentMode: .fit)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
            Text("Say what you mean.\nBe understood.")
                .font(.system(size: 40, weight: .heavy, design: .rounded))
                .foregroundStyle(Theme.ink)
                .fixedSize(horizontal: false, vertical: true)
            Text("An AI coach that listens to how you really talk, shows you what's working — with evidence — and helps you practise one small change at a time.")
                .font(.body)
                .foregroundStyle(Theme.inkSecondary)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 12)
            VStack(alignment: .leading, spacing: 12) {
                welcomeRow("waveform.circle.fill", "Talk with an AI partner, upload a conversation, or record one")
                welcomeRow("checkmark.seal.fill", "Feedback only where there's real evidence — never a guess")
                welcomeRow("figure.walk.motion", "Missions that fit the moments you care about")
            }
            .padding(.top, 22)
            Spacer(minLength: 20).layoutPriority(-1)
            Button("Get started") { model.next() }
                .buttonStyle(.primaryPill)
            Text("About 2 minutes of questions first.")
                .font(.footnote)
                .foregroundStyle(Theme.inkTertiary)
                .frame(maxWidth: .infinity)
                .padding(.top, 10)
        }
        .padding(.horizontal, Theme.gutter)
        .padding(.bottom, 12)
    }

    private func welcomeRow(_ icon: String, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon).font(.title3).foregroundStyle(Theme.indigo).frame(width: 28)
            Text(text).font(.subheadline).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
        }
    }
}

private struct StepScaffold<Content: View>: View {
    let eyebrow: String
    let title: String
    let subtitle: String
    let canContinue: Bool
    var continueTitle: String = "Continue"
    let onContinue: () -> Void
    @ViewBuilder let content: Content

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    Eyebrow(eyebrow, color: Theme.indigo)
                    Text(title).font(.display).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
                    Text(subtitle).font(.body).foregroundStyle(Theme.inkSecondary)
                    content.padding(.top, 14)
                }
                .padding(.horizontal, Theme.gutter)
                .padding(.top, 24)
                .padding(.bottom, 24)
            }
            Button(continueTitle, action: onContinue)
                .buttonStyle(.primaryPill)
                .disabled(!canContinue)
                .padding(.horizontal, Theme.gutter)
                .padding(.bottom, 12)
        }
    }
}

private struct ContextRankStep: View {
    @Environment(AppModel.self) private var app
    let model: OnboardingModel

    private var contexts: [ChoiceOption] {
        app.meta?.contexts ?? [
            ChoiceOption(id: "social", title: "Friends & social situations"),
            ChoiceOption(id: "networking", title: "Networking"),
            ChoiceOption(id: "meetings", title: "Meetings"),
            ChoiceOption(id: "interviews", title: "Interviews"),
        ]
    }

    var body: some View {
        StepScaffold(
            eyebrow: "Step 1 · Where it matters",
            title: "Where would you most like to communicate better?",
            subtitle: "Tap them in order of importance. Your top picks shape your missions.",
            canContinue: !model.contextsRanked.isEmpty,
            onContinue: { model.next() }
        ) {
            VStack(spacing: 10) {
                ForEach(contexts) { option in
                    let rank = model.contextsRanked.firstIndex(of: option.id).map { $0 + 1 }
                    Button { model.toggleRank(option.id) } label: {
                        HStack(spacing: 14) {
                            Image(systemName: icon(option.id))
                                .font(.title3)
                                .foregroundStyle(rank == nil ? Theme.inkSecondary : Theme.indigo)
                                .frame(width: 30)
                            Text(option.title).font(.headlineRounded).foregroundStyle(Theme.ink)
                            Spacer()
                            ZStack {
                                Circle()
                                    .strokeBorder(rank == nil ? Theme.stroke : Color.clear, lineWidth: 1.5)
                                    .background(Circle().fill(rank == nil ? AnyShapeStyle(Color.clear) : AnyShapeStyle(Theme.aurora)))
                                if let rank {
                                    Text("\(rank)").font(.subheadline.weight(.bold)).foregroundStyle(.white)
                                }
                            }
                            .frame(width: 30, height: 30)
                        }
                        .padding(16)
                        .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous))
                        .overlay(
                            RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous)
                                .strokeBorder(rank == nil ? Theme.stroke : Theme.indigo.opacity(0.5), lineWidth: 1)
                        )
                    }
                    .buttonStyle(.pressableCard)
                    .accessibilityLabel(rank.map { "\(option.title), ranked \($0)" } ?? option.title)
                }
                if !model.contextsRanked.isEmpty {
                    Button("Clear ranking") { model.contextsRanked.removeAll() }
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(Theme.inkSecondary)
                        .padding(.top, 4)
                }
            }
        }
    }

    private func icon(_ id: String) -> String {
        switch id {
        case "social": return "person.2.fill"
        case "networking": return "point.3.connected.trianglepath.dotted"
        case "meetings": return "person.3.fill"
        case "interviews": return "briefcase.fill"
        default: return "bubble.left.fill"
        }
    }
}

private struct EaseStep: View {
    @Environment(AppModel.self) private var app
    let model: OnboardingModel

    private var options: [ChoiceOption] {
        app.meta?.easeTargets ?? [
            ChoiceOption(id: "explaining", title: "Explaining myself"),
            ChoiceOption(id: "contributing", title: "Contributing"),
            ChoiceOption(id: "connecting", title: "Connecting"),
            ChoiceOption(id: "persuading", title: "Persuading"),
            ChoiceOption(id: "concise", title: "Being concise"),
        ]
    }

    var body: some View {
        StepScaffold(
            eyebrow: "Step 2 · What should feel easier",
            title: "What would you like to feel easier?",
            subtitle: "Tick all that apply.",
            canContinue: !model.easeTargets.isEmpty,
            onContinue: { model.next() }
        ) {
            VStack(spacing: 10) {
                ForEach(options) { option in
                    let selected = model.easeTargets.contains(option.id)
                    Button { model.toggleEase(option.id) } label: {
                        HStack(spacing: 14) {
                            Image(systemName: icon(option.id))
                                .font(.title3)
                                .foregroundStyle(selected ? Theme.indigo : Theme.inkSecondary)
                                .frame(width: 30)
                            Text(option.title).font(.headlineRounded).foregroundStyle(Theme.ink)
                            Spacer()
                            Image(systemName: selected ? "checkmark.circle.fill" : "circle")
                                .font(.title2)
                                .foregroundStyle(selected ? Theme.indigo : Theme.stroke)
                        }
                        .padding(16)
                        .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous))
                        .overlay(
                            RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous)
                                .strokeBorder(selected ? Theme.indigo.opacity(0.5) : Theme.stroke, lineWidth: 1)
                        )
                    }
                    .buttonStyle(.pressableCard)
                    .accessibilityAddTraits(selected ? .isSelected : [])
                }
            }
        }
    }

    private func icon(_ id: String) -> String {
        switch id {
        case "explaining": return "text.bubble.fill"
        case "contributing": return "hand.raised.fill"
        case "connecting": return "heart.text.square.fill"
        case "persuading": return "megaphone.fill"
        case "concise": return "scissors"
        default: return "circle"
        }
    }
}

private struct GoalStep: View {
    @Environment(AppModel.self) private var app
    @Bindable var model: OnboardingModel

    private var tracks: [Track] { app.meta?.tracks ?? [] }

    var body: some View {
        let suggestion = model.suggestedTrack(available: tracks)
        StepScaffold(
            eyebrow: "Step 3 · Your goal",
            title: "Pick a goal to start with",
            subtitle: "Your course follows this goal. You can change it any time.",
            canContinue: model.goalTrack != nil,
            onContinue: { model.next() }
        ) {
            VStack(spacing: 10) {
                ForEach(tracks) { track in
                    let selected = model.goalTrack == track.id
                    Button {
                        Haptics.selection()
                        model.goalTrack = track.id
                    } label: {
                        HStack(alignment: .top, spacing: 14) {
                            Image(systemName: track.symbol)
                                .font(.title3)
                                .foregroundStyle(selected ? Color.white : Theme.indigo)
                                .frame(width: 44, height: 44)
                                .background(selected ? AnyShapeStyle(Theme.aurora) : AnyShapeStyle(Theme.indigo.opacity(0.1)),
                                            in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(track.title).font(.headlineRounded).foregroundStyle(Theme.ink)
                                    if track.id == suggestion {
                                        Tag(text: "Suggested", color: Theme.mint)
                                    }
                                }
                                Text(track.subtitle).font(.footnote).foregroundStyle(Theme.inkSecondary)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                            Spacer(minLength: 0)
                        }
                        .padding(14)
                        .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous))
                        .overlay(
                            RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous)
                                .strokeBorder(selected ? Theme.indigo : Theme.stroke, lineWidth: selected ? 2 : 1)
                        )
                    }
                    .buttonStyle(.pressableCard)
                }
                if tracks.isEmpty {
                    ProgressView().padding()
                }
            }
        }
        .onAppear {
            if model.goalTrack == nil { model.goalTrack = suggestion }
        }
    }
}

private struct LanguageStep: View {
    @Environment(AppModel.self) private var app
    @Bindable var model: OnboardingModel

    private var languages: [LanguageOption] {
        app.meta?.languages ?? [LanguageOption(code: "en", name: "English")]
    }

    var body: some View {
        StepScaffold(
            eyebrow: "Step 4 · Language",
            title: "Which language would you like to use?",
            subtitle: "Your AI partner will speak it, and your feedback will be written in it. The app's menus stay in English for now.",
            canContinue: true,
            onContinue: { model.next() }
        ) {
            VStack(alignment: .leading, spacing: 14) {
                Menu {
                    Picker("Language", selection: $model.language) {
                        ForEach(languages) { language in
                            Text(language.name).tag(language.code)
                        }
                    }
                } label: {
                    HStack {
                        Image(systemName: "globe").foregroundStyle(Theme.indigo)
                        Text(languages.first { $0.code == model.language }?.name ?? "English")
                            .font(.headlineRounded)
                            .foregroundStyle(Theme.ink)
                        Spacer()
                        Image(systemName: "chevron.up.chevron.down").foregroundStyle(Theme.inkTertiary)
                    }
                    .padding(16)
                    .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous).strokeBorder(Theme.stroke))
                }
                Label("We never score accent or pronunciation.", systemImage: "hand.thumbsup.fill")
                    .font(.footnote)
                    .foregroundStyle(Theme.inkSecondary)
            }
        }
        .onAppear {
            if !languages.contains(where: { $0.code == model.language }) { model.language = "en" }
        }
    }
}

private struct AnalysisConsentStep: View {
    @Environment(AppModel.self) private var app
    let model: OnboardingModel
    @State private var showFullText = false
    @State private var showDeclineInfo = false

    private var consent: ConsentText? { app.meta?.consents.analysis }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Eyebrow("Step 5 · Your voice, your call", color: Theme.indigo)
                    Text(consent?.title ?? "How Comlogue uses your voice")
                        .font(.display)
                        .foregroundStyle(Theme.ink)
                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(consent?.bullets ?? defaultBullets, id: \.self) { bullet in
                            HStack(alignment: .top, spacing: 10) {
                                Image(systemName: "checkmark.shield.fill").foregroundStyle(Theme.mint)
                                Text(bullet).font(.subheadline).foregroundStyle(Theme.ink)
                            }
                        }
                    }
                    .card()
                    .padding(.top, 6)
                    if let fullText = consent?.body {
                        DisclosureGroup("Read the full text", isExpanded: $showFullText) {
                            Text(fullText).font(.footnote).foregroundStyle(Theme.inkSecondary).padding(.top, 6)
                        }
                        .font(.subheadline.weight(.semibold))
                        .tint(Theme.indigo)
                    }
                    if let error = model.error { InlineErrorBanner(message: error) }
                }
                .padding(.horizontal, Theme.gutter)
                .padding(.vertical, 24)
            }
            VStack(spacing: 8) {
                Button {
                    Task { await agree() }
                } label: {
                    if model.isSaving { ProgressView().tint(.white) } else { Text("I agree") }
                }
                .buttonStyle(.primaryPill)
                .disabled(model.isSaving || app.meta == nil)
                Button("Not now") { showDeclineInfo = true }
                    .buttonStyle(.ghostPill)
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.bottom, 12)
        }
        .alert("Comlogue needs this to give feedback", isPresented: $showDeclineInfo) {
            Button("OK", role: .cancel) {}
        } message: {
            Text("Every route — AI conversations, uploads and recordings — relies on analysing your voice. You can come back whenever you're ready, and delete your data at any time.")
        }
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
            let allContexts = app.meta?.contexts.map(\.id) ?? []
            try await app.completeOnboarding(model.patch(consentVersion: consent.version, allContexts: allContexts))
            Haptics.success()
        } catch {
            model.error = error.userMessage
        }
    }
}
