import SwiftUI

/// Everything Comlogue has told you: results that are ready, reminders about events, weekly reveals. Tapping
/// one takes you straight there.
struct InboxView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    var isRoot = false
    @State private var isLoading = false

    var body: some View {
        Group {
            if app.inbox.isEmpty {
                EmptyStateView(systemImage: "bell.badge",
                               title: isLoading ? "Checking…" : "Nothing new",
                               message: "Results, event reminders and your weekly reveal will show up here.")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List {
                    ForEach(app.inbox) { item in
                        Button {
                            open(item)
                        } label: {
                            InboxRow(item: item)
                        }
                        .listRowBackground(item.read ? Theme.surface : Theme.indigo.opacity(0.06))
                    }
                }
                .listStyle(.insetGrouped)
                .scrollContentBackground(.hidden)
            }
        }
        .screenBackground()
        .navigationTitle("Inbox")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if isRoot {
                ToolbarItem(placement: .topBarTrailing) {
                    CircleIconButton(systemName: "xmark") { app.dismissFlow(refresh: false) }
                }
            }
            ToolbarItem(placement: .topBarLeading) {
                if app.unreadCount > 0 {
                    Button("Mark all read") { Task { await app.markAllRead() } }
                        .font(.subheadline.weight(.semibold))
                }
            }
        }
        .refreshable { await app.refreshInbox() }
        .task {
            isLoading = true
            await app.refreshInbox()
            isLoading = false
        }
    }

    private func open(_ item: InboxNotification) {
        Task {
            await app.markRead(item)
            try? await app.api.notificationOpened(item.id)
        }
        guard let link = DeepLink(string: item.deepLink) else { return }
        if case .inbox = link { return }
        if isRoot {
            app.open(link)
        } else {
            dismiss()
            app.open(link)
        }
    }
}

private struct InboxRow: View {
    let item: InboxNotification

    private var style: (symbol: String, color: Color) {
        switch item.category {
        case .results: return ("chart.bar.doc.horizontal.fill", Theme.indigo)
        case .eventPrep: return ("calendar.badge.clock", Theme.coral)
        case .checkIn: return ("bubble.left.and.text.bubble.right.fill", Theme.violet)
        case .weeklyReveal: return ("gift.fill", Theme.amber)
        case .milestone: return ("star.fill", Theme.amber)
        case .practice, .nudge: return ("waveform", Theme.mint)
        case .tips, .other: return ("lightbulb.fill", Theme.inkSecondary)
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: style.symbol)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(style.color)
                .frame(width: 36, height: 36)
                .background(style.color.opacity(0.12), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            VStack(alignment: .leading, spacing: 3) {
                HStack(alignment: .firstTextBaseline) {
                    Text(item.title)
                        .font(.subheadline.weight(item.read ? .medium : .bold))
                        .foregroundStyle(Theme.ink)
                        .lineLimit(2)
                    Spacer(minLength: 6)
                    Text(Formatting.relative(item.createdAt)).font(.caption2).foregroundStyle(Theme.inkTertiary)
                }
                Text(item.body).font(.footnote).foregroundStyle(Theme.inkSecondary).lineLimit(3)
            }
            if !item.read {
                Circle().fill(Theme.indigo).frame(width: 8, height: 8).padding(.top, 6)
                    .accessibilityLabel("Unread")
            }
        }
        .padding(.vertical, 4)
        .contentShape(Rectangle())
    }
}

/// A bell with the unread count, for screen headers.
struct InboxBellButton: View {
    @Environment(AppModel.self) private var app

    var body: some View {
        Button {
            app.present(.inbox)
        } label: {
            ZStack(alignment: .topTrailing) {
                Image(systemName: "bell.fill")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(Theme.ink)
                    .frame(width: 40, height: 40)
                    .background(Theme.surface, in: Circle())
                    .overlay(Circle().strokeBorder(Theme.stroke))
                if app.unreadCount > 0 {
                    Text(app.unreadCount > 9 ? "9+" : "\(app.unreadCount)")
                        .font(.system(size: 10, weight: .bold, design: .rounded))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 5)
                        .frame(minWidth: 18, minHeight: 18)
                        .background(Theme.coral, in: Capsule())
                        .offset(x: 4, y: -4)
                }
            }
        }
        .buttonStyle(.plain)
        .accessibilityLabel(app.unreadCount > 0 ? "Inbox, \(app.unreadCount) unread" : "Inbox")
    }
}
