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
                               message: "Feedback and reminders will show up here.")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List {
                    ForEach(app.inbox) { item in
                        Button {
                            open(item)
                        } label: {
                            InboxRow(item: item)
                        }
                        .listRowBackground(Theme.surface)
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

/// Title, one line and when — an unread dot is the only decoration.
private struct InboxRow: View {
    let item: InboxNotification

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Circle()
                .fill(item.read ? Color.clear : Theme.indigo)
                .frame(width: 8, height: 8)
                .padding(.top, 7)
                .accessibilityLabel("Unread")
                .accessibilityHidden(item.read)
            VStack(alignment: .leading, spacing: 4) {
                HStack(alignment: .firstTextBaseline) {
                    Text(item.title)
                        .font(.headlineRounded.weight(item.read ? .medium : .semibold))
                        .foregroundStyle(Theme.ink)
                        .lineLimit(2)
                        .multilineTextAlignment(.leading)
                    Spacer(minLength: 6)
                    Text(Formatting.relative(item.createdAt)).font(.caption).foregroundStyle(Theme.inkTertiary)
                }
                Text(item.body).font(.subheadline).foregroundStyle(Theme.inkSecondary).lineLimit(1)
            }
        }
        .padding(.vertical, 6)
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
