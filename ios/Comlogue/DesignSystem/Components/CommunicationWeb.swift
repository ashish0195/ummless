import SwiftUI

/// The seven-dimension "communication web".
///
/// Spec rules this view enforces:
/// - Dimensions without evidence are drawn as unavailable (dashed spoke and "?"), never as zero.
/// - The shape is only filled between *adjacent assessed* dimensions, so a partial profile never looks
///   like a complete polygon.
/// - Provisional (early) reads are hollow points.
struct CommunicationWeb: View {
    let dimensions: [DimensionResult]
    var showLabels: Bool = true
    var animate: Bool = true

    @State private var progress: Double = 0

    private var ordered: [DimensionResult] {
        DimensionId.allCases.compactMap { id in dimensions.first { $0.dimension == id } }
    }

    var body: some View {
        GeometryReader { proxy in
            let size = min(proxy.size.width, proxy.size.height)
            let labelInset: CGFloat = showLabels ? 58 : 6
            let radius = size / 2 - labelInset
            let center = CGPoint(x: proxy.size.width / 2, y: proxy.size.height / 2)
            ZStack {
                WebGrid(axes: ordered.count, radius: radius, center: center, missing: ordered.map { !$0.status.hasLevel })
                WebFill(results: ordered, radius: radius, center: center, progress: progress)
                ForEach(Array(ordered.enumerated()), id: \.element.dimension) { index, result in
                    marker(for: result, index: index, radius: radius, center: center)
                    if showLabels {
                        label(for: result, index: index, radius: radius + 12, center: center)
                    }
                }
            }
        }
        .aspectRatio(1, contentMode: .fit)
        .onAppear {
            if animate {
                withAnimation(.spring(response: 0.9, dampingFraction: 0.8).delay(0.1)) { progress = 1 }
            } else {
                progress = 1
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(accessibilitySummary)
    }

    static func point(index: Int, count: Int, distance: CGFloat, center: CGPoint) -> CGPoint {
        let angle = -Double.pi / 2 + Double(index) / Double(max(count, 1)) * 2 * .pi
        return CGPoint(x: center.x + CGFloat(cos(angle)) * distance, y: center.y + CGFloat(sin(angle)) * distance)
    }

    @ViewBuilder
    private func marker(for result: DimensionResult, index: Int, radius: CGFloat, center: CGPoint) -> some View {
        let color = Theme.color(for: result.dimension)
        if let level = result.displayLevel {
            let point = Self.point(index: index, count: ordered.count,
                                   distance: radius * CGFloat(Double(level) / 5.0 * progress), center: center)
            Group {
                if result.status == .provisional {
                    Circle().strokeBorder(color, lineWidth: 2.5).background(Circle().fill(Theme.surface))
                } else {
                    Circle().fill(color).overlay(Circle().strokeBorder(Color.white, lineWidth: 2))
                }
            }
            .frame(width: 13, height: 13)
            .position(point)
        } else {
            let point = Self.point(index: index, count: ordered.count, distance: radius, center: center)
            Text("?")
                .font(.caption2.weight(.heavy))
                .foregroundStyle(Theme.inkTertiary)
                .frame(width: 18, height: 18)
                .background(Circle().fill(Theme.surfaceMuted))
                .overlay(Circle().strokeBorder(Theme.inkTertiary.opacity(0.5), style: StrokeStyle(lineWidth: 1, dash: [2, 2])))
                .position(point)
        }
    }

    private func label(for result: DimensionResult, index: Int, radius: CGFloat, center: CGPoint) -> some View {
        let point = Self.point(index: index, count: ordered.count, distance: radius, center: center)
        let assessed = result.status.hasLevel
        let anchor = Self.labelAnchor(index: index, count: ordered.count)
        return VStack(alignment: anchor.horizontal, spacing: 1) {
            Text(DimensionCatalog.title(result.dimension))
                .font(.caption2.weight(.bold))
                .foregroundStyle(assessed ? Theme.color(for: result.dimension) : Theme.inkTertiary)
            if let label = result.displayLevel.map(DimensionCatalog.levelLabel) {
                Text(label).font(.system(size: 9, weight: .medium, design: .rounded)).foregroundStyle(Theme.inkSecondary)
            }
        }
        .fixedSize()
        // A zero-size frame pinned just outside the vertex, so the label grows away from the web and never
        // covers the vertex marker (the "?" for missing evidence, or a level-5 point).
        .frame(width: 0, height: 0, alignment: anchor)
        .position(point)
    }

    /// Which edge of a label touches its anchor point: the edge facing the centre of the web.
    static func labelAnchor(index: Int, count: Int) -> Alignment {
        let angle = -Double.pi / 2 + Double(index) / Double(max(count, 1)) * 2 * .pi
        let horizontal: HorizontalAlignment = cos(angle) > 0.6 ? .leading : (cos(angle) < -0.6 ? .trailing : .center)
        let vertical: VerticalAlignment = sin(angle) > 0.6 ? .top : (sin(angle) < -0.6 ? .bottom : .center)
        return Alignment(horizontal: horizontal, vertical: vertical)
    }

    private var accessibilitySummary: String {
        let parts = ordered.map { result -> String in
            let name = DimensionCatalog.title(result.dimension)
            if let level = result.displayLevel {
                let prefix = result.status == .provisional ? "early read " : ""
                return "\(name): \(prefix)\(DimensionCatalog.levelLabel(level))"
            }
            return "\(name): not enough evidence yet"
        }
        return "Communication web. " + parts.joined(separator: ". ")
    }
}

/// Concentric heptagons and spokes. Spokes for unassessed dimensions are dashed.
private struct WebGrid: View {
    let axes: Int
    let radius: CGFloat
    let center: CGPoint
    let missing: [Bool]

    var body: some View {
        ZStack {
            ForEach(1...5, id: \.self) { ring in
                Path { path in
                    for index in 0...axes {
                        let point = CommunicationWeb.point(index: index % max(axes, 1), count: axes,
                                                           distance: radius * CGFloat(ring) / 5, center: center)
                        if index == 0 { path.move(to: point) } else { path.addLine(to: point) }
                    }
                }
                .stroke(Theme.stroke, lineWidth: ring == 5 ? 1.2 : 0.8)
            }
            ForEach(0..<axes, id: \.self) { index in
                Path { path in
                    path.move(to: center)
                    path.addLine(to: CommunicationWeb.point(index: index, count: axes, distance: radius, center: center))
                }
                .stroke(missing[safe: index] == true ? Theme.inkTertiary.opacity(0.5) : Theme.stroke,
                        style: StrokeStyle(lineWidth: 1, dash: missing[safe: index] == true ? [3, 4] : []))
            }
        }
    }
}

/// Filled wedges only between neighbouring assessed dimensions.
private struct WebFill: View {
    let results: [DimensionResult]
    let radius: CGFloat
    let center: CGPoint
    let progress: Double

    var body: some View {
        let count = results.count
        ZStack {
            ForEach(0..<count, id: \.self) { index in
                let next = (index + 1) % count
                if let a = results[index].displayLevel, let b = results[next].displayLevel {
                    let pa = CommunicationWeb.point(index: index, count: count, distance: radius * CGFloat(Double(a) / 5 * progress), center: center)
                    let pb = CommunicationWeb.point(index: next, count: count, distance: radius * CGFloat(Double(b) / 5 * progress), center: center)
                    Path { path in
                        path.move(to: center)
                        path.addLine(to: pa)
                        path.addLine(to: pb)
                        path.closeSubpath()
                    }
                    .fill(
                        LinearGradient(colors: [Theme.color(for: results[index].dimension).opacity(0.28),
                                                Theme.color(for: results[next].dimension).opacity(0.28)],
                                       startPoint: UnitPoint(x: pa.x / max(center.x * 2, 1), y: pa.y / max(center.y * 2, 1)),
                                       endPoint: UnitPoint(x: pb.x / max(center.x * 2, 1), y: pb.y / max(center.y * 2, 1)))
                    )
                    Path { path in
                        path.move(to: pa)
                        path.addLine(to: pb)
                    }
                    .stroke(Theme.indigo.opacity(0.7), style: StrokeStyle(lineWidth: 2, lineCap: .round))
                }
            }
        }
    }
}

extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
