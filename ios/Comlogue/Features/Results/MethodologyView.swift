import SwiftUI

/// Plain-language explanation of how Comlogue turns speech into feedback — and what it refuses to do.
struct MethodologyView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("How Comlogue gives feedback").font(.display).foregroundStyle(Theme.ink)
                Text("We'd rather say \"not enough evidence yet\" than guess. Every result passes three checks first.")
                    .font(.body)
                    .foregroundStyle(Theme.inkSecondary)

                check(1, "Can we hear it?", "waveform",
                      "We check volume, background noise, distortion and overlapping voices. Unclear sections are set aside — never scored.")
                check(2, "Is it you?", "person.crop.circle.badge.checkmark",
                      "In AI conversations your microphone is yours. In recordings we match your voice sample (if you saved one) and always ask you to confirm. Other people's speech never goes into your profile.")
                check(3, "Was there a chance to show the skill?", "magnifyingglass",
                      "Listening needs someone to listen to. Persuasion needs a case to make. If a conversation didn't offer the opportunity, that skill is marked \"not enough evidence yet\".")

                VStack(alignment: .leading, spacing: 10) {
                    Eyebrow("Levels and confidence")
                    Text("Each skill gets a level band — Emerging, Developing, Capable, Strong or Exceptional — tied to a written rubric and the moments that support it. Confidence is shown separately: a clear level from one short sample is still low confidence.")
                        .font(.subheadline)
                        .foregroundStyle(Theme.ink)
                    HStack(spacing: 6) {
                        ForEach(1...5, id: \.self) { level in
                            Text(DimensionCatalog.levelLabel(level))
                                .font(.caption2.weight(.semibold))
                                .padding(.vertical, 6)
                                .frame(maxWidth: .infinity)
                                .background(Theme.indigo.opacity(0.08 + Double(level) * 0.06), in: Capsule())
                                .foregroundStyle(Theme.ink)
                        }
                    }
                }
                .card()

                VStack(alignment: .leading, spacing: 8) {
                    Eyebrow("What we don't do")
                    bullet("No overall score. Each skill stands on its own evidence, and the overall number is deferred until the method is validated.")
                    bullet("No penalty for missing evidence, unclear audio, accents or pronunciation.")
                    bullet("No diagnosis. Results describe how you communicated in the sampled conversation.")
                    bullet("No changes from reflections alone. Only assessable audio updates your profile.")
                }
                .card()

                VStack(alignment: .leading, spacing: 8) {
                    Eyebrow("Your style and conversational twin")
                    Text("Style descriptions need at least a couple of minutes of your speech from different conversations, and stay provisional until there's more. Twins compare specific habits — like pacing or pausing — with reference speakers; they're for fun and inspiration, not a verdict.")
                        .font(.subheadline)
                        .foregroundStyle(Theme.ink)
                }
                .card()

                Text("Spot something that doesn't match your experience? Tap \"Not quite right?\" on any result — we review every report.")
                    .font(.footnote)
                    .foregroundStyle(Theme.inkSecondary)
            }
            .padding(Theme.gutter)
        }
        .screenBackground()
        .navigationTitle("How it works")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func check(_ number: Int, _ title: String, _ icon: String, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 14) {
            ZStack {
                Circle().fill(Theme.aurora).frame(width: 40, height: 40)
                Image(systemName: icon).font(.subheadline.weight(.bold)).foregroundStyle(.white)
            }
            VStack(alignment: .leading, spacing: 4) {
                Text("\(number). \(title)").font(.headlineRounded).foregroundStyle(Theme.ink)
                Text(text).font(.subheadline).foregroundStyle(Theme.inkSecondary).fixedSize(horizontal: false, vertical: true)
            }
        }
        .card()
    }

    private func bullet(_ text: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "xmark.circle.fill").foregroundStyle(Theme.coral).font(.footnote)
            Text(text).font(.subheadline).foregroundStyle(Theme.ink)
        }
    }
}

/// Small link that opens the methodology explainer in a sheet.
struct HowItWorksLink: View {
    @State private var show = false

    var body: some View {
        Button {
            show = true
        } label: {
            Label("How we assess", systemImage: "info.circle")
                .font(.footnote.weight(.semibold))
        }
        .foregroundStyle(Theme.indigo)
        .sheet(isPresented: $show) {
            NavigationStack {
                MethodologyView()
                    .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { show = false } } }
            }
        }
    }
}
