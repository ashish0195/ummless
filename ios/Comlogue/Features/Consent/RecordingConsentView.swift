import SwiftUI

/// Just-in-time recording consent: shown only when someone chooses to record or upload a conversation with
/// other people (never on the landing screen). Shows the region's rule for context, but the product
/// policy is the same everywhere: everyone in the conversation must agree.
struct RecordingConsentView: View {
    enum Kind { case upload, live }

    @Environment(AppModel.self) private var app
    let kind: Kind
    let onAgree: (RecordingConsentPayload) -> Void
    let onUseAIPractice: () -> Void

    @State private var rules: RecordingRules?
    @State private var region: String? = RegionPreference.best
    @State private var attested = false
    @State private var showScript = false
    @State private var loadError: String?

    private var consent: ConsentText? { app.meta?.consents.recording }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Eyebrow(kind == .upload ? "Before you upload" : "Before you record", color: Theme.indigo)
                Text(kind == .upload ? "Recordings with other people need their OK" : "Everyone needs to know you're recording")
                    .font(.display)
                    .foregroundStyle(Theme.ink)
                    .fixedSize(horizontal: false, vertical: true)

                regionRow

                if let rules {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack(spacing: 8) {
                            Image(systemName: ruleIcon(rules.rule)).foregroundStyle(ruleColor(rules.rule))
                            Text(rules.headline).font(.headlineRounded).foregroundStyle(Theme.ink)
                        }
                        Text(rules.detail).font(.subheadline).foregroundStyle(Theme.inkSecondary).fixedSize(horizontal: false, vertical: true)
                        Divider()
                        Label(rules.policy, systemImage: "person.3.fill")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(Theme.ink)
                    }
                    .card()

                    DisclosureGroup(isExpanded: $showScript) {
                        Text(rules.howToAsk)
                            .font(.subheadline)
                            .foregroundStyle(Theme.ink)
                            .padding(.top, 8)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    } label: {
                        Label("How to ask (a script you can use)", systemImage: "quote.bubble.fill")
                            .font(.subheadline.weight(.semibold))
                    }
                    .tint(Theme.indigo)
                    .card()
                } else if let loadError {
                    InlineErrorBanner(message: loadError)
                } else {
                    ProgressView().frame(maxWidth: .infinity).padding()
                }

                if let consent {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(consent.bullets, id: \.self) { bullet in
                            HStack(alignment: .top, spacing: 8) {
                                Image(systemName: "lock.shield.fill").foregroundStyle(Theme.mint)
                                Text(bullet).font(.footnote).foregroundStyle(Theme.inkSecondary)
                            }
                        }
                    }
                }

                Toggle(isOn: $attested) {
                    Text(kind == .upload
                         ? "Everyone in these recordings agreed to be recorded, and I'm allowed to share them."
                         : "Everyone here knows I'm recording and is OK with it.")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(Theme.ink)
                }
                .toggleStyle(CheckboxToggleStyle())
                .padding(.top, 4)

                if let rules {
                    Text(rules.disclaimer).font(.caption).foregroundStyle(Theme.inkTertiary)
                }

                Button("Continue") {
                    onAgree(RecordingConsentPayload(attested: true, region: region, rule: rules?.rule,
                                                    consentVersion: consent?.version ?? "recording-v1"))
                }
                .buttonStyle(.primaryPill)
                .disabled(!attested)
                .padding(.top, 6)

                Button {
                    onUseAIPractice()
                } label: {
                    Text("Can't ask everyone? Practise with an AI partner instead")
                        .font(.footnote.weight(.semibold))
                        .frame(maxWidth: .infinity)
                }
                .foregroundStyle(Theme.indigo)
            }
            .padding(Theme.gutter)
        }
        .screenBackground()
        .task(id: region) { await loadRules() }
    }

    private var regionRow: some View {
        HStack {
            Image(systemName: "mappin.and.ellipse").foregroundStyle(Theme.indigo)
            VStack(alignment: .leading, spacing: 1) {
                Text("Rules for").font(.caption).foregroundStyle(Theme.inkSecondary)
                Text(rules?.regionName ?? region ?? "Your region").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
            }
            Spacer()
            if let regions = rules?.regions, !regions.isEmpty {
                Menu {
                    ForEach(regions) { option in
                        Button(option.name) {
                            region = option.code
                            RegionPreference.stored = option.code
                        }
                    }
                } label: {
                    Text("Change").font(.subheadline.weight(.semibold))
                }
            }
        }
        .padding(14)
        .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous))
    }

    private func loadRules() async {
        do {
            rules = try await app.api.recordingRules(region: region)
            loadError = nil
        } catch {
            loadError = "We couldn't load local guidance. The rule still applies: get everyone's OK before recording."
        }
    }

    private func ruleIcon(_ rule: String) -> String {
        switch rule {
        case "all_party": return "person.3.sequence.fill"
        case "one_party": return "person.fill.checkmark"
        case "mixed": return "exclamationmark.triangle.fill"
        default: return "info.circle.fill"
        }
    }

    private func ruleColor(_ rule: String) -> Color {
        switch rule {
        case "all_party": return Theme.coral
        case "mixed": return Theme.amber
        default: return Theme.indigo
        }
    }
}

struct CheckboxToggleStyle: ToggleStyle {
    func makeBody(configuration: Configuration) -> some View {
        Button {
            configuration.isOn.toggle()
            Haptics.selection()
        } label: {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: configuration.isOn ? "checkmark.square.fill" : "square")
                    .font(.title3)
                    .foregroundStyle(configuration.isOn ? Theme.indigo : Theme.inkTertiary)
                configuration.label
                    .multilineTextAlignment(.leading)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(14)
            .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous)
                    .strokeBorder(configuration.isOn ? Theme.indigo : Theme.stroke, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(configuration.isOn ? .isSelected : [])
    }
}
