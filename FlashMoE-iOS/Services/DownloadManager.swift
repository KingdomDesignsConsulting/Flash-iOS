/*
 * DownloadManager.swift — Background download orchestration for HuggingFace models
 *
 * Uses URLSession background downloads that survive app termination.
 * Downloads files sequentially within a model for clean progress tracking.
 * State persisted to downloads.json for resume across app launches.
 */

import Foundation
import Observation

// MARK: - Download State

enum DownloadStatus: String, Codable, Sendable {
    case downloading
    case paused
    case failed
    case complete
}

struct DownloadState: Codable {
    let catalogId: String
    let repoId: String
    var generationID: String?
    var completedFiles: [String]
    var completedBytes: UInt64
    var currentFile: String?
    var status: DownloadStatus
    var errorMessage: String?
}

// MARK: - DownloadManager

@Observable
final class DownloadManager: NSObject, @unchecked Sendable {
    static let shared = DownloadManager()

    // Observable state
    private(set) var activeDownload: DownloadState?
    private(set) var overallProgress: Double = 0
    private(set) var currentFileProgress: Double = 0
    private(set) var bytesDownloaded: UInt64 = 0
    private(set) var totalBytes: UInt64 = 0
    private(set) var error: String?
    private(set) var downloadSpeed: Double = 0 // bytes/sec

    // Background session callback
    var backgroundCompletionHandler: (() -> Void)?

    // Private state
    private var backgroundSession: URLSession!
    private var currentTask: URLSessionDownloadTask?
    private var currentEntry: CatalogEntry?
    private var resumeData: Data?
    private var speedSampleTime: Date?
    private var speedSampleBytes: UInt64 = 0

    private static let sessionIdentifier = "com.flashmoe.model-download"

    // MARK: - Initialization

    override private init() {
        super.init()
        let config = URLSessionConfiguration.background(withIdentifier: Self.sessionIdentifier)
        config.isDiscretionary = false
        config.sessionSendsLaunchEvents = true
        config.allowsCellularAccess = true
        backgroundSession = URLSession(configuration: config, delegate: self, delegateQueue: nil)

        // Restore persisted state
        loadPersistedState()

        // Reconnect to any in-flight background tasks
        backgroundSession.getTasksWithCompletionHandler { [weak self] _, _, downloadTasks in
            DispatchQueue.main.async {
                guard let self else { return }
                self.currentTask = downloadTasks.first {
                    self.taskMatchesActiveDownload($0)
                }
            }
        }
    }

    // MARK: - Public API

    func startDownload(entry: CatalogEntry) {
        // Allow starting if no active download, or previous one finished/failed
        if let status = activeDownload?.status, status == .downloading || status == .paused {
            if activeDownload?.catalogId != entry.id {
                error = "A different download is already in progress"
                return
            }
            // Same model — resume instead
            resumeDownload()
            return
        }

        // Clear stale state from previous download
        if activeDownload != nil {
            activeDownload = nil
            clearPersistedState()
        }

        // Check disk space
        let available = availableDiskSpace()
        if available < entry.totalSizeBytes {
            let needed = formatBytes(entry.totalSizeBytes)
            let have = formatBytes(available)
            error = "Not enough space: \(needed) needed, \(have) available"
            return
        }

        error = nil
        currentEntry = entry
        totalBytes = entry.totalSizeBytes

        // Create model directory
        let modelDir = modelDirectory(for: entry.id)
        createDirectoryStructure(for: entry, at: modelDir)

        activeDownload = DownloadState(
            catalogId: entry.id,
            repoId: entry.repoId,
            generationID: UUID().uuidString,
            completedFiles: [],
            completedBytes: 0,
            currentFile: nil,
            status: .downloading
        )
        persistState()
        downloadNextFile()
    }

    func pauseDownload() {
        guard activeDownload?.status == .downloading else { return }

        currentTask?.cancel(byProducingResumeData: { [weak self] data in
            DispatchQueue.main.async {
                guard let self else { return }
                self.resumeData = data
                self.activeDownload?.status = .paused
                self.persistState()
                self.currentTask = nil
            }
        })
    }

    func resumeDownload() {
        guard activeDownload?.status == .paused || activeDownload?.status == .failed else { return }

        // Resolve the catalog entry
        if currentEntry == nil, let catalogId = activeDownload?.catalogId {
            currentEntry = ModelCatalog.models.first { $0.id == catalogId }
        }
        guard currentEntry != nil else {
            error = "Cannot find model in catalog"
            return
        }

        error = nil
        activeDownload?.status = .downloading
        activeDownload?.errorMessage = nil
        totalBytes = currentEntry?.totalSizeBytes ?? 0
        persistState()

        if let resumeData {
            let task = backgroundSession.downloadTask(withResumeData: resumeData)
            if let state = activeDownload, let filename = state.currentFile {
                task.taskDescription = taskDescription(for: state, filename: filename)
            }
            task.resume()
            currentTask = task
            self.resumeData = nil
        } else {
            downloadNextFile()
        }
    }

    func cancelDownload() {
        currentTask?.cancel()
        currentTask = nil
        resumeData = nil

        if let catalogId = activeDownload?.catalogId {
            let dir = modelDirectory(for: catalogId)
            try? FileManager.default.removeItem(at: dir)
        }

        activeDownload = nil
        overallProgress = 0
        currentFileProgress = 0
        bytesDownloaded = 0
        totalBytes = 0
        error = nil
        currentEntry = nil
        clearPersistedState()
    }

    func deleteModel(catalogId: String) {
        let dir = modelDirectory(for: catalogId)
        try? FileManager.default.removeItem(at: dir)

        if activeDownload?.catalogId == catalogId {
            activeDownload = nil
            clearPersistedState()
        }
    }

    func isModelDownloaded(_ catalogId: String) -> Bool {
        let dir = modelDirectory(for: catalogId)
        return FlashMoEEngine.validateModel(at: dir.path)
    }

    func modelPath(for catalogId: String) -> String {
        modelDirectory(for: catalogId).path
    }

    // MARK: - File Management

    private func modelDirectory(for catalogId: String) -> URL {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        return docs.appendingPathComponent(catalogId)
    }

    private func createDirectoryStructure(for entry: CatalogEntry, at baseURL: URL) {
        let fm = FileManager.default
        try? fm.createDirectory(at: baseURL, withIntermediateDirectories: true)

        // Create subdirectories for expert files
        var subdirs = Set<String>()
        for file in entry.files {
            let url = baseURL.appendingPathComponent(file.filename)
            let parent = url.deletingLastPathComponent()
            if parent != baseURL {
                subdirs.insert(parent.path)
            }
        }
        for dir in subdirs {
            try? fm.createDirectory(atPath: dir, withIntermediateDirectories: true)
        }
    }

    // MARK: - Sequential Download Engine

    // URLSession delegate callbacks arrive on a background delegate queue. Keep
    // the download state machine single-threaded on main; synchronous snapshots
    // are used only for the immutable values needed before a temp file is moved.
    private func mainThreadSnapshot<T>(_ body: () -> T) -> T {
        if Thread.isMainThread {
            return body()
        }
        return DispatchQueue.main.sync(execute: body)
    }

    private struct DownloadTaskIdentity {
        let catalogId: String?
        let generationID: String?
        let filename: String
    }

    private func taskDescription(for state: DownloadState, filename: String) -> String {
        guard let generationID = state.generationID else {
            // Legacy persisted downloads used the filename alone.
            return filename
        }
        return "v1|\(generationID)|\(state.catalogId)|\(filename)"
    }

    private func taskIdentity(from task: URLSessionTask) -> DownloadTaskIdentity? {
        guard let description = task.taskDescription, !description.isEmpty else { return nil }
        let parts = description.split(separator: "|", maxSplits: 3,
                                      omittingEmptySubsequences: false)
        if parts.count == 4, parts[0] == "v1" {
            return DownloadTaskIdentity(
                catalogId: String(parts[2]),
                generationID: String(parts[1]),
                filename: String(parts[3])
            )
        }
        // Backward compatibility for a task created before generation IDs existed.
        return DownloadTaskIdentity(catalogId: nil, generationID: nil,
                                    filename: description)
    }

    private func taskMatchesActiveDownload(_ task: URLSessionTask) -> Bool {
        guard let state = activeDownload,
              let identity = taskIdentity(from: task) else { return false }

        if let generationID = state.generationID {
            return identity.catalogId == state.catalogId &&
                   identity.generationID == generationID &&
                   identity.filename == state.currentFile
        }

        // A legacy persisted operation has no generation ID; constrain it to
        // the current filename so a later new-generation task cannot match it.
        return identity.generationID == nil &&
               identity.filename == state.currentFile
    }

    private func exactFileSize(at url: URL) -> UInt64? {
        guard let attrs = try? FileManager.default.attributesOfItem(atPath: url.path),
              let size = attrs[.size] as? NSNumber else {
            return nil
        }
        return size.uint64Value
    }

    private func revalidateCompletedFiles(_ state: DownloadState, entry: CatalogEntry) -> DownloadState {
        var corrected = state
        var validFiles: [String] = []
        var validBytes: UInt64 = 0
        let base = modelDirectory(for: entry.id)

        for filename in state.completedFiles {
            guard let expected = entry.files.first(where: { $0.filename == filename }) else {
                continue
            }
            let url = base.appendingPathComponent(filename)
            guard exactFileSize(at: url) == expected.sizeBytes else {
                try? FileManager.default.removeItem(at: url)
                continue
            }
            validFiles.append(filename)
            validBytes += expected.sizeBytes
        }

        corrected.completedFiles = validFiles
        corrected.completedBytes = validBytes
        if validFiles.count != state.completedFiles.count, corrected.status == .complete {
            corrected.status = .failed
            corrected.errorMessage = "Previously completed files failed exact-size validation"
        }
        return corrected
    }

    private func downloadNextFile() {
        guard var state = activeDownload, let entry = currentEntry else { return }

        state = revalidateCompletedFiles(state, entry: entry)
        activeDownload = state
        bytesDownloaded = state.completedBytes

        // Find next file to download
        let nextFile = entry.files.first { !state.completedFiles.contains($0.filename) }

        guard let file = nextFile else {
            // All files downloaded
            state.status = .complete
            state.currentFile = nil
            activeDownload = state
            overallProgress = 1.0
            persistState()

            // Protect from iOS storage optimization (exclude from backup/purge)
            let dir = modelDirectory(for: entry.id)
            var dirURL = dir
            var values = URLResourceValues()
            values.isExcludedFromBackup = true
            try? dirURL.setResourceValues(values)
            if let enumerator = FileManager.default.enumerator(at: dir, includingPropertiesForKeys: nil) {
                while let fileURL = enumerator.nextObject() as? URL {
                    var fURL = fileURL
                    try? fURL.setResourceValues(values)
                }
            }

            // Validate the model
            if !FlashMoEEngine.validateModel(at: dir.path) {
                error = "Download complete but model validation failed"
                state.status = .failed
                state.errorMessage = "Validation failed — some files may be corrupt"
                activeDownload = state
                persistState()
            }
            return
        }

        state.currentFile = file.filename
        activeDownload = state
        persistState()

        let url = entry.downloadURL(for: file)
        let task = backgroundSession.downloadTask(with: url)
        task.taskDescription = taskDescription(for: state, filename: file.filename)
        task.resume()
        currentTask = task
        currentFileProgress = 0
        speedSampleTime = Date()
        speedSampleBytes = bytesDownloaded
    }

    // MARK: - Disk Space

    private func availableDiskSpace() -> UInt64 {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        guard let values = try? docs.resourceValues(forKeys: [.volumeAvailableCapacityForImportantUsageKey]),
              let capacity = values.volumeAvailableCapacityForImportantUsage else {
            return 0
        }
        return UInt64(capacity)
    }

    // MARK: - State Persistence

    private var stateFileURL: URL {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        return docs.appendingPathComponent("downloads.json")
    }

    private func persistState() {
        guard let state = activeDownload else { return }
        if let data = try? JSONEncoder().encode(state) {
            try? data.write(to: stateFileURL)
        }
    }

    private func clearPersistedState() {
        try? FileManager.default.removeItem(at: stateFileURL)
    }

    private func loadPersistedState() {
        guard let data = try? Data(contentsOf: stateFileURL),
              let state = try? JSONDecoder().decode(DownloadState.self, from: data) else {
            return
        }

        currentEntry = ModelCatalog.models.first { $0.id == state.catalogId }

        if let entry = currentEntry {
            let corrected = revalidateCompletedFiles(state, entry: entry)
            activeDownload = corrected
            totalBytes = entry.totalSizeBytes
            bytesDownloaded = corrected.completedBytes
            overallProgress = totalBytes > 0 ? Double(bytesDownloaded) / Double(totalBytes) : 0
            if corrected.completedFiles != state.completedFiles ||
               corrected.completedBytes != state.completedBytes ||
               corrected.status != state.status {
                persistState()
            }
        } else {
            activeDownload = state
        }
    }

    // MARK: - Formatting

    private func formatBytes(_ bytes: UInt64) -> String {
        let gb = Double(bytes) / (1024 * 1024 * 1024)
        if gb >= 1 {
            return String(format: "%.1f GB", gb)
        }
        let mb = Double(bytes) / (1024 * 1024)
        return String(format: "%.0f MB", mb)
    }
}

// MARK: - URLSessionDownloadDelegate

extension DownloadManager: URLSessionDownloadDelegate {

    func urlSession(
        _ session: URLSession,
        downloadTask: URLSessionDownloadTask,
        didFinishDownloadingTo location: URL
    ) {
        let snapshot = mainThreadSnapshot { () -> (CatalogEntry, String)? in
            guard taskMatchesActiveDownload(downloadTask),
                  let entry = currentEntry,
                  let identity = taskIdentity(from: downloadTask) else { return nil }
            return (entry, identity.filename)
        }
        guard let (entry, filename) = snapshot else { return }

        // Check HTTP status code — HuggingFace returns 200 HTML pages for 404s
        if let httpResponse = downloadTask.response as? HTTPURLResponse,
           httpResponse.statusCode != 200 {
            let statusCode = httpResponse.statusCode
            DispatchQueue.main.async { [weak self] in
                guard let self, self.taskMatchesActiveDownload(downloadTask),
                      var state = self.activeDownload else { return }
                self.error = "HTTP \(statusCode) downloading \(filename)"
                state.status = .failed
                state.errorMessage = self.error
                self.activeDownload = state
                self.persistState()
            }
            return
        }

        // Move from temp to model directory (must happen synchronously before this method returns)
        let dest = modelDirectory(for: entry.id).appendingPathComponent(filename)
        let fm = FileManager.default
        try? fm.removeItem(at: dest)

        var moveError: Error?
        do {
            try fm.moveItem(at: location, to: dest)
        } catch {
            moveError = error
        }

        // Compute file size on this thread before dispatching
        let actualSize: UInt64
        if moveError == nil {
            let attrs = try? fm.attributesOfItem(atPath: dest.path)
            actualSize = attrs?[.size] as? UInt64 ?? 0
        } else {
            actualSize = 0
        }

        let expectedSize = entry.files.first(where: { $0.filename == filename })?.sizeBytes ?? 0

        // Check if we got an HTML error page instead of the actual file
        // (HuggingFace sometimes returns 200 with HTML for missing LFS files)
        if actualSize > 0 && actualSize < 10_000 && expectedSize > 100_000 {
            // Downloaded file is suspiciously small — likely an error page
            try? fm.removeItem(at: dest)
            DispatchQueue.main.async { [weak self] in
                guard let self, self.taskMatchesActiveDownload(downloadTask),
                      var state = self.activeDownload else { return }
                self.error = "File \(filename) not found on server (got \(actualSize) bytes, expected \(self.formatBytes(expectedSize)))"
                state.status = .failed
                state.errorMessage = self.error
                self.activeDownload = state
                self.persistState()
            }
            return
        }

        // All @Observable mutations on main thread
        DispatchQueue.main.async { [weak self] in
            guard let self, self.taskMatchesActiveDownload(downloadTask),
                  var state = self.activeDownload else {
                // A stale completion may already have moved its temp file.
                // Remove only that stale operation's destination.
                try? fm.removeItem(at: dest)
                return
            }

            if let moveError {
                self.error = "Failed to save \(filename): \(moveError.localizedDescription)"
                state.status = .failed
                state.errorMessage = self.error
                self.activeDownload = state
                self.persistState()
                return
            }

            // Catalog sizes are exact. Do not mark a truncated or oversized
            // artifact complete; resume state may otherwise permanently skip it.
            if expectedSize == 0 || actualSize != expectedSize {
                try? fm.removeItem(at: dest)
                self.error = "File \(filename) has wrong size (\(actualSize) vs expected \(expectedSize))"
                state.status = .failed
                state.errorMessage = self.error
                self.activeDownload = state
                self.persistState()
                return
            }

            state.completedBytes += actualSize
            state.completedFiles.append(filename)
            state.currentFile = nil
            self.activeDownload = state
            self.bytesDownloaded = state.completedBytes
            self.persistState()

            // Start next file
            self.downloadNextFile()
        }
    }

    func urlSession(
        _ session: URLSession,
        downloadTask: URLSessionDownloadTask,
        didWriteData bytesWritten: Int64,
        totalBytesWritten: Int64,
        totalBytesExpectedToWrite: Int64
    ) {
        let written = max(totalBytesWritten, 0)
        let expected = max(totalBytesExpectedToWrite, 0)

        DispatchQueue.main.async { [weak self] in
            guard let self, self.taskMatchesActiveDownload(downloadTask) else { return }

            let fileProgress = expected > 0
                ? Double(written) / Double(expected) : 0
            let completed = self.activeDownload?.completedBytes ?? 0
            let currentTotal = completed + UInt64(written)
            let total = self.totalBytes
            let overall = total > 0 ? Double(currentTotal) / Double(total) : 0

            var newSpeed: Double?
            let now = Date()
            if let sampleTime = self.speedSampleTime,
               now.timeIntervalSince(sampleTime) >= 2 {
                let elapsed = now.timeIntervalSince(sampleTime)
                let delta = currentTotal >= self.speedSampleBytes
                    ? currentTotal - self.speedSampleBytes : 0
                newSpeed = Double(delta) / elapsed
                self.speedSampleTime = now
                self.speedSampleBytes = currentTotal
            }

            self.currentFileProgress = fileProgress
            self.bytesDownloaded = currentTotal
            self.overallProgress = overall
            if let newSpeed {
                self.downloadSpeed = newSpeed
            }
        }
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: (any Error)?) {
        guard let error else { return }

        let nsError = error as NSError
        if nsError.code == NSURLErrorCancelled {
            return
        }

        let newResumeData = nsError.userInfo[NSURLSessionDownloadTaskResumeData] as? Data
        let errorMsg = error.localizedDescription

        DispatchQueue.main.async { [weak self] in
            guard let self, self.taskMatchesActiveDownload(task) else { return }
            if let newResumeData {
                self.resumeData = newResumeData
            }
            self.error = errorMsg
            self.activeDownload?.status = .failed
            self.activeDownload?.errorMessage = errorMsg
            self.persistState()
        }
    }

    func urlSessionDidFinishEvents(forBackgroundURLSession session: URLSession) {
        DispatchQueue.main.async { [weak self] in
            self?.backgroundCompletionHandler?()
            self?.backgroundCompletionHandler = nil
        }
    }
}
