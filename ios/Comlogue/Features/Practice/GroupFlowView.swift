import SwiftUI

/// A group discussion (the GD round in campus placements and MBA admissions) or a panel interview: several AI
/// voices and the person in one conversation, then a report on how they took part.
struct GroupFlowView: View {
    private enum Stage: Equatable {
        case loading, intro, starting, conversation(Conversation), report(String), paywall, failed(String)
    }

    @Environment(AppModel.self) private var app
    let panelId: String
    @State private var stage: Stage = .loading
    @State private var difficulty: Difficulty = .real

    private var panel: Panel? { app.panels.first { $0.id == panelId } }

    var body: some View {
        Group {
            switch stage {
            case .loading, .starting:
                LoadingStateView(title: stage == .loading ? "Getting the room ready…" : "Taking your seat…").screenBackground()
            case .intro:
                if let panel {
                    GroupIntroView(panel: panel, difficulty: $difficulty,
                                   onStart: { Task { await start() } },
                                   onClose: { app.dismissFlow(refresh: false) })
                }
            case .conversation(let conversation):
                ConversationScreen(
                    conversation: conversation,
                    app: app,
                    progressLabel: panel?.isGroupDiscussion == false ? "Panel interview" : "Group discussion",
                    finishTitle: "Get my report",
                    endTitle: "End & get report",
                    onFinished: { result in stage = .report(result?.resultRef?.id ?? conversation.id) },
                    onExit: { app.dismissFlow() }
                )
                .id(conversation.id)
            case .report(let conversationId):
                NavigationStack {
                    SparReportView(conversationId: conversationId, isRoot: true,
                                   onAgain: { stage = .intro },
                                   title: panel?.isGroupDiscussion == false ? "Interview report" : "Discussion report",
                                   againTitle: "Try it again")
                }
            case .paywall:
                PaywallView { app.dismissFlow() }
            case .failed(let message):
                VStack {
                    HStack { Spacer(); CircleIconButton(systemName: "xmark") { app.dismissFlow() } }.padding(Theme.gutter)
                    ErrorStateView(message: message) { Task { await load() } }
                }
                .screenBackground()
            }
        }
        .task { if stage == .loading { await load() } }
    }

    private func load() async {
        if panel == nil { await app.refreshPanels() }
        guard let panel else {
            stage = .failed("This practice room isn't available right now.")
            return
        }
        difficulty = panel.defaultDifficulty
        stage = .intro
    }

    private func start() async {
        stage = .starting
        do {
            let conversation = try await app.api.createConversation(
                CreateConversationRequest(kind: "group", difficulty: difficulty, panelId: panelId))
            stage = .conversation(conversation)
        } catch let error as APIError where error.isSubscriptionRequired {
            stage = .paywall
        } catch {
            stage = .failed(error.userMessage)
        }
    }
}

private struct GroupIntroView: View {
    @Environment(AppModel.self) private var app
    let panel: Panel
    @Binding var difficulty: Difficulty
    let onStart: () -> Void
    let onClose: () -> Void

    private var tips: [String] {
        if panel.isGroupDiscussion {
            return [
                "Enter early with one clear point. You don't need to speak first, just soon.",
                "Add something new rather than agreeing at length.",
                "Build on people by name: \"Building on Ananya's point…\"",
                "Bring in someone who hasn't spoken.",
                "Near the end, help the group land on a conclusion.",
            ]
        }
        return [
            "Answer the person who asked, then include the rest of the panel.",
            "Use one short story with a result, not a list of duties.",
            "If two panelists disagree, acknowledge both before you answer.",
            "Close with a question that shows you listened.",
        ]
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                if app.isDemo { DemoBadge() }
                Spacer()
                CircleIconButton(systemName: "xmark", action: onClose)
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.top, 10)
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Eyebrow("\(panel.isGroupDiscussion ? "Group discussion" : "Panel interview") · about \(panel.minutes) min",
                            color: Color(hex: panel.colorHex))
                    Text(panel.title).font(.display).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
                    Text(panel.description).font(.body).foregroundStyle(Theme.inkSecondary)
                        .fixedSize(horizontal: false, vertical: true)

                    if let topic = panel.topic {
                        VStack(alignment: .leading, spacing: 6) {
                            Eyebrow(panel.isGroupDiscussion ? "Topic" : "Role", color: Color(hex: panel.colorHex))
                            Text(topic).font(.title3Rounded).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
                        }
                        .card()
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        Text("In the room").font(.headlineRounded).foregroundStyle(Theme.ink)
                        ForEach(panel.participants) { participant in
                            HStack(spacing: 12) {
                                Image(systemName: SymbolName.safe(participant.symbol))
                                    .font(.subheadline.weight(.semibold))
                                    .foregroundStyle(.white)
                                    .frame(width: 36, height: 36)
                                    .background(Color(hex: participant.colorHex), in: Circle())
                                VStack(alignment: .leading, spacing: 1) {
                                    Text(participant.name).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                                    Text(participant.role).font(.caption).foregroundStyle(Theme.inkSecondary)
                                }
                            }
                        }
                        HStack(spacing: 12) {
                            Image(systemName: "person.fill").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.indigo)
                                .frame(width: 36, height: 36).background(Theme.indigo.opacity(0.12), in: Circle())
                            Text("You · \(panel.userRole)").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                        }
                    }
                    .card()

                    VStack(alignment: .leading, spacing: 8) {
                        Eyebrow("What good looks like", color: Theme.mint)
                        ForEach(tips, id: \.self) { tip in
                            Label(tip, systemImage: "checkmark").font(.subheadline).foregroundStyle(Theme.ink)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    .card()

                    VStack(alignment: .leading, spacing: 8) {
                        Text("Difficulty").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                        Picker("Difficulty", selection: $difficulty) {
                            ForEach(Difficulty.allCases) { level in Text(DifficultyCatalog.title(level)).tag(level) }
                        }
                        .pickerStyle(.segmented)
                    }
                }
                .padding(Theme.gutter)
            }
            Button(action: onStart) {
                Label(panel.isGroupDiscussion ? "Join the discussion" : "Start the interview", systemImage: "mic.fill")
            }
            .buttonStyle(.primaryPill)
            .padding(.horizontal, Theme.gutter)
            .padding(.bottom, 12)
        }
        .screenBackground()
    }
}

/// A card for one group discussion or panel interview.
struct PanelCard: View {
    let panel: Panel
    let locked: Bool

    var body: some View {
        let color = Color(hex: panel.colorHex)
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Image(systemName: SymbolName.safe(panel.symbol, fallback: "person.3.fill"))
                    .font(.headline)
                    .foregroundStyle(.white)
                    .frame(width: 40, height: 40)
                    .background(color, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                Spacer()
                if locked { Image(systemName: "lock.fill").font(.caption).foregroundStyle(Theme.inkTertiary) }
            }
            Text(panel.title).font(.headlineRounded).foregroundStyle(Theme.ink).lineLimit(2)
                .multilineTextAlignment(.leading)
            Text(panel.scenario).font(.caption).foregroundStyle(Theme.inkSecondary).lineLimit(2)
                .multilineTextAlignment(.leading)
            HStack(spacing: 4) {
                ForEach(panel.participants.prefix(4)) { participant in
                    Circle().fill(Color(hex: participant.colorHex)).frame(width: 10, height: 10)
                }
                Text("· \(panel.minutes) min").font(.caption2.weight(.semibold)).foregroundStyle(Theme.inkTertiary)
            }
        }
        .frame(width: 200, alignment: .leading)
        .card(padding: 16)
    }
}
