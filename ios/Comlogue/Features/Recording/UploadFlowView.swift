import SwiftUI
import UniformTypeIdentifiers

/// Upload one or more recorded conversations: consent → optional voice setup → pick files → per-file
/// processing, speaker confirmation and results.
@MainActor
struct UploadFlowView: View {
    private enum Stage: Equatable { case consent, voiceSetup, pick, list }

    struct UploadItem: Identifiable, Equatable {
        enum Status: Equatable { case waiting, uploading, uploaded, failed }
        let id = UUID()
        let name: String
        let localURL: URL
        var status: Status = .waiting
        var recordingId: String?
        var error: String?
    }

    @Environment(AppModel.self) private var app
    @State private var stage: Stage = .consent
    @State private var consent: RecordingConsentPayload?
    @State private var showImporter = false
    @State private var items: [UploadItem] = []
    @State private var path = NavigationPath()
    @State private var isUploading = false

    private static let allowedTypes: [UTType] = [.audio, .mpeg4Audio, .mp3, .wav, .aiff, .movie, .quickTimeMovie, .mpeg4Movie]

    var body: some View {
        NavigationStack(path: $path) {
            Group {
                switch stage {
                case .consent:
                    RecordingConsentView(kind: .upload, onAgree: { payload in
                        consent = payload
                        let needsVoice = !(app.me?.voiceReference.isActive ?? false) && !LocalFlags.declinedVoiceReference
                        stage = needsVoice ? .voiceSetup : .pick
                    }, onUseAIPractice: {
                        app.present(.guidedAssessment(resumeId: nil))
                    })
                case .voiceSetup:
                    VoiceSetupView(mode: .inline) { _ in stage = .pick }
                case .pick:
                    pickIntro
                case .list:
                    uploadList
                }
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    CircleIconButton(systemName: "xmark") { app.dismissFlow() }
                }
            }
            .navigationDestination(for: String.self) { recordingId in
                RecordingDetailView(recordingId: recordingId, isRoot: false)
            }
        }
        .fileImporter(isPresented: $showImporter, allowedContentTypes: Self.allowedTypes, allowsMultipleSelection: true) { result in
            handleImport(result)
        }
    }

    private var pickIntro: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Eyebrow("Upload conversations", color: Theme.indigo)
                    Text("Choose one or more recordings").font(.display).foregroundStyle(Theme.ink)
                    Text("Meetings, calls, interviews or chats — anything where you talk with other people. Real conversations add natural context, but they're not automatically better than AI practice.")
                        .font(.body)
                        .foregroundStyle(Theme.inkSecondary)
                    VStack(alignment: .leading, spacing: 12) {
                        tip("doc.richtext", "Audio or video files: M4A, MP3, WAV, AIFF, MP4 or MOV.")
                        tip("clock", "Up to \(app.meta?.limits.maxRecordingMinutes ?? 60) minutes each. We analyse the clearest parts.")
                        tip("waveform", "Voice Memos: tap a memo → Share → Save to Files, then pick it here.")
                        tip("person.crop.circle.badge.questionmark", "We'll ask you to confirm which voice is yours before giving feedback.")
                    }
                    .card()
                }
                .padding(Theme.gutter)
            }
            Button("Choose files") { showImporter = true }
                .buttonStyle(.primaryPill)
                .padding(.horizontal, Theme.gutter)
                .padding(.bottom, 12)
        }
        .screenBackground()
    }

    private var uploadList: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Your uploads").font(.display).foregroundStyle(Theme.ink)
                    Text("Each recording is checked on its own: audio quality, which voice is yours, then the evidence for each skill.")
                        .font(.subheadline)
                        .foregroundStyle(Theme.inkSecondary)
                    ForEach(items) { item in
                        uploadRow(item)
                    }
                }
                .padding(Theme.gutter)
            }
            VStack(spacing: 8) {
                Button("Add more") { showImporter = true }
                    .buttonStyle(.secondaryPill)
                Button("Done") { app.dismissFlow() }
                    .buttonStyle(.ghostPill)
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.bottom, 12)
        }
        .screenBackground()
    }

    @ViewBuilder
    private func uploadRow(_ item: UploadItem) -> some View {
        let content = HStack(spacing: 12) {
            Image(systemName: "waveform")
                .foregroundStyle(Theme.indigo)
                .frame(width: 40, height: 40)
                .background(Theme.indigo.opacity(0.1), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            VStack(alignment: .leading, spacing: 3) {
                Text(item.name).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink).lineLimit(1)
                switch item.status {
                case .waiting: Text("Waiting…").font(.caption).foregroundStyle(Theme.inkSecondary)
                case .uploading: Text("Uploading…").font(.caption).foregroundStyle(Theme.indigo)
                case .uploaded: Text("Uploaded · tap to see progress").font(.caption).foregroundStyle(Theme.mint)
                case .failed: Text(item.error ?? "Upload failed").font(.caption).foregroundStyle(Theme.danger)
                }
            }
            Spacer()
            switch item.status {
            case .uploading: ProgressView()
            case .uploaded: Image(systemName: "chevron.right").foregroundStyle(Theme.inkTertiary)
            case .failed:
                Button("Retry") { retry(item.id) }.font(.caption.weight(.bold))
            case .waiting: EmptyView()
            }
        }
        .card(padding: 14)

        if let id = item.recordingId {
            NavigationLink(value: id) { content }.buttonStyle(.pressableCard)
        } else {
            content
        }
    }

    private func tip(_ icon: String, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icon).foregroundStyle(Theme.indigo).frame(width: 24)
            Text(text).font(.subheadline).foregroundStyle(Theme.ink)
        }
    }

    // MARK: Import & upload

    private func handleImport(_ result: Result<[URL], Error>) {
        guard case .success(let urls) = result, !urls.isEmpty else { return }
        let maxBytes = Int64((app.meta?.limits.maxUploadMb ?? 200) * 1_048_576)
        for url in urls {
            let accessing = url.startAccessingSecurityScopedResource()
            defer { if accessing { url.stopAccessingSecurityScopedResource() } }
            let destination = FileManager.default.temporaryDirectory
                .appendingPathComponent("upload-\(UUID().uuidString)")
                .appendingPathExtension(url.pathExtension.isEmpty ? "m4a" : url.pathExtension)
            do {
                try FileManager.default.copyItem(at: url, to: destination)
                var item = UploadItem(name: url.deletingPathExtension().lastPathComponent, localURL: destination)
                let size = (try? FileManager.default.attributesOfItem(atPath: destination.path)[.size] as? Int64) ?? 0
                if size > maxBytes {
                    item.status = .failed
                    item.error = "This file is larger than \(app.meta?.limits.maxUploadMb ?? 200) MB. Try a shorter recording."
                }
                items.append(item)
            } catch {
                var item = UploadItem(name: url.lastPathComponent, localURL: url)
                item.status = .failed
                item.error = "We couldn't open this file."
                items.append(item)
            }
        }
        stage = .list
        Task { await uploadPending() }
    }

    private func retry(_ id: UUID) {
        update(id) { item in
            item.status = .waiting
            item.error = nil
        }
        Task { await uploadPending() }
    }

    private func update(_ id: UUID, _ change: (inout UploadItem) -> Void) {
        guard let index = items.firstIndex(where: { $0.id == id }) else { return }
        change(&items[index])
    }

    private func uploadPending() async {
        guard !isUploading, let consent else { return }
        isUploading = true
        defer { isUploading = false }
        while let next = items.first(where: { $0.status == .waiting }) {
            update(next.id) { $0.status = .uploading }
            do {
                let file = try UploadFile.audio(at: next.localURL)
                let recording = try await app.api.uploadRecording(file: file, source: "upload", title: next.name, consent: consent)
                try? FileManager.default.removeItem(at: next.localURL)
                update(next.id) { item in
                    item.status = .uploaded
                    item.recordingId = recording.id
                }
                LocalFlags.pendingRecordingIds.append(recording.id)
            } catch {
                update(next.id) { item in
                    item.status = .failed
                    item.error = error.userMessage
                }
            }
        }
        if items.count == 1, let id = items.first?.recordingId, path.isEmpty {
            path.append(id)
        }
    }
}
