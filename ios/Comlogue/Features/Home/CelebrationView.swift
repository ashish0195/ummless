import SwiftUI

/// A short, warm moment when a milestone lands. Practice milestones celebrate effort, never a skill score.
struct CelebrationView: View {
    @Environment(\.dismiss) private var dismiss
    let milestone: Milestone
    @State private var burst = false

    var body: some View {
        VStack(spacing: 18) {
            ZStack {
                ForEach(0..<14, id: \.self) { index in
                    Circle()
                        .fill(Theme.auroraColors[index % Theme.auroraColors.count])
                        .frame(width: CGFloat(6 + index % 4 * 2), height: CGFloat(6 + index % 4 * 2))
                        .offset(x: burst ? cos(Double(index) / 14 * 2 * .pi) * 92 : 0,
                                y: burst ? sin(Double(index) / 14 * 2 * .pi) * 92 : 0)
                        .opacity(burst ? 0 : 1)
                }
                Image(systemName: "star.fill")
                    .font(.system(size: 40, weight: .bold))
                    .foregroundStyle(.white)
                    .frame(width: 92, height: 92)
                    .background(Theme.aurora, in: Circle())
                    .scaleEffect(burst ? 1 : 0.6)
            }
            .frame(height: 200)
            Text(milestone.title).font(.display).foregroundStyle(Theme.ink).multilineTextAlignment(.center)
            Text(milestone.detail).font(.body).foregroundStyle(Theme.inkSecondary).multilineTextAlignment(.center)
            HStack(spacing: 10) {
                ShareLink(item: "I just reached a milestone on Comlogue: \(milestone.title). Practising how I communicate, one small change at a time.") {
                    Label("Share", systemImage: "square.and.arrow.up")
                }
                .buttonStyle(.pill(.secondary, fullWidth: true))
                Button("Nice!") { dismiss() }
                    .buttonStyle(.primaryPill)
            }
            .padding(.top, 4)
        }
        .padding(Theme.gutter)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .screenBackground()
        .onAppear {
            Haptics.success()
            withAnimation(.spring(response: 0.7, dampingFraction: 0.6)) { burst = true }
        }
    }
}
