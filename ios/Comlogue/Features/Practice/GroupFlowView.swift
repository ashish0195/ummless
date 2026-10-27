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
                    onFinished: { result in
                        // Leaving before saying anything has nothing to review.
                        if let id = result?.resultRef?.id { stage = .report(id) } else { app.dismissFlow() }
                    },
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

/// The one screen before the room: what it is, who's there, three things that work, and the start button.
private struct GroupIntroView: View {
    @Environment(AppModel.self) private var app
    let panel: Panel
    @Binding var difficulty: Difficulty
    let onStart: () -> Void
    let onClose: () -> Void

    /// Three things that matter most, short enough to remember in the room.
    private var tips: [String] {
        if panel.isGroupDiscussion {
            return [
                "Come in early with one clear point.",
                "Build on others by name.",
                "Help the group reach a conclusion.",
            ]
        }
        return [
            "Answer the person who asked, then the whole panel.",
            "Tell one short story with a result.",
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
                VStack(alignment: .leading, spacing: 22) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(panel.title).font(.display).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
                        // The GD topic, or the role being interviewed for.
                        Text(panel.topic ?? panel.scenario).font(.body).foregroundStyle(Theme.inkSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    room
                    VStack(alignment: .leading, spacing: 10) {
                        Text("What works").font(.headlineRounded).foregroundStyle(Theme.ink)
                        ForEach(tips, id: \.self) { tip in
                            Label {
                                Text(tip)
                            } icon: {
                                Image(systemName: "checkmark").foregroundStyle(Theme.mint)
                            }
                            .font(.subheadline)
                            .foregroundStyle(Theme.ink)
                            .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    .card()
                    HStack {
                        Text("How tough?").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                        Spacer()
                        Picker("How tough?", selection: $difficulty) {
                            ForEach(Difficulty.allCases) { level in Text(DifficultyCatalog.title(level)).tag(level) }
                        }
                        .pickerStyle(.menu)
                        .tint(Theme.indigo)
                    }
                    .card(padding: 14)
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

    /// Everyone in the room as a row of avatars, like a group call — names only; roles are read out by VoiceOver.
    private var room: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                Text("In the room").font(.headlineRounded).foregroundStyle(Theme.ink)
                Spacer()
                Text("About \(panel.minutes) min").font(.subheadline).foregroundStyle(Theme.inkSecondary)
            }
            HStack(alignment: .top, spacing: 4) {
                ForEach(panel.participants) { participant in
                    VStack(spacing: 6) {
                        Text(String(participant.name.prefix(1)))
                            .font(.headlineRounded)
                            .foregroundStyle(.white)
                            .frame(width: 48, height: 48)
                            .background(Color(hex: participant.colorHex), in: Circle())
                        Text(participant.name)
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(Theme.ink)
                            .lineLimit(1)
                            .minimumScaleFactor(0.8)
                    }
                    .frame(maxWidth: .infinity)
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel("\(participant.name), \(participant.role)")
                }
                VStack(spacing: 6) {
                    Image(systemName: "person.fill")
                        .font(.headline)
                        .foregroundStyle(Theme.indigo)
                        .frame(width: 48, height: 48)
                        .background(Theme.indigo.opacity(0.12), in: Circle())
                    Text("You").font(.caption.weight(.semibold)).foregroundStyle(Theme.ink)
                }
                .frame(maxWidth: .infinity)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("You, \(panel.userRole)")
            }
        }
        .card()
    }
}
