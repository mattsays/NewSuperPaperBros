#include "../../aurora-main/lib/gx/projection_aspect.hpp"
#include <cmath>
#include <iostream>

int main() {
    using aurora::gx::projection_aspect_scale;
    const float source = 16.0f / 9.0f;
    const auto mac = projection_aspect_scale(source, 1.6f, true);
    const auto cinema = projection_aspect_scale(source, 2.39f, true);
    const auto same = projection_aspect_scale(source, source, true);
    const auto textureCopy = projection_aspect_scale(source, 1.6f, false);
    const auto original = projection_aspect_scale(4.0f / 3.0f, 1.6f, true);
    const float projectionY = 1.0f / 228.0f;
    const float hudOffset = aurora::gx::projection_top_anchor_translation(source, 1.6f, projectionY, true);
    auto close = [](float a, float b) { return std::fabs(a-b) < 0.00001f; };
    // The corrected camera must match the display's pixel aspect. On 16:10 it
    // keeps the original width and exposes more height, keeping HUD edges visible.
    if (!close(source * mac.vertical / mac.horizontal, 1.6f) ||
        !close(mac.horizontal, 1.0f) || !close(mac.vertical, 0.9f) ||
        !close(source * cinema.vertical / cinema.horizontal, 2.39f) ||
        !close(cinema.vertical, 1.0f) ||
        !close(same.horizontal, 1.0f) || !close(same.vertical, 1.0f) ||
        !close(textureCopy.horizontal, 1.0f) || !close(textureCopy.vertical, 1.0f) ||
        !close(original.horizontal, 1.0f) || !close(original.vertical, 1.0f)) {
        std::cerr << "Projection changes distort geometry, crop the HUD or alter texture copies.\n";
        return 1;
    }
    // Same-width 16:10 has a taller picture. The original top margin and HUD
    // size in pixels must remain unchanged; all widgets receive one translation.
    for (const float y : {120.0f, 180.0f, 205.0f, 240.0f}) {
        const float originalNdc = y * projectionY;
        const float anchoredNdc = (y + hudOffset) * projectionY * mac.vertical;
        const float oldMargin = (1.0f - originalNdc) / 2.0f;
        const float newMargin = (1.0f - anchoredNdc) / (2.0f * mac.vertical);
        if (!close(oldMargin, newMargin)) {
            std::cerr << "HUD top inset moved or the hide animation was clamped.\n";
            return 1;
        }
    }
    // The live SPM HUD uses a perspective camera and renders icons and glyphs
    // at different depths. Their screen-space displacement must stay identical.
    const float hudSource = 1.688889f, hudProjectionY = 2.144507f;
    const auto hudScale = projection_aspect_scale(hudSource, 1.6f, true);
    for (const float depth : {400.0f, 600.0f, 1000.0f}) {
        const float offset = aurora::gx::projection_top_anchor_translation(
            hudSource, 1.6f, hudProjectionY, true, depth);
        const float screenShift = offset * hudProjectionY * hudScale.vertical / depth;
        if (!close(screenShift, 1.0f - hudScale.vertical)) {
            std::cerr << "Perspective HUD icons and glyphs no longer share a top anchor.\n";
            return 1;
        }
    }
    if (!close(hudOffset * projectionY, 1.0f / 9.0f) ||
        !close(aurora::gx::projection_top_anchor_translation(source, source, projectionY, true), 0.0f) ||
        !close(aurora::gx::projection_top_anchor_translation(source, 2.39f, projectionY, true), 0.0f) ||
        !close(aurora::gx::projection_top_anchor_translation(source, 1.6f, projectionY, false), 0.0f) ||
        !close(aurora::gx::projection_top_anchor_translation(source, 1.6f, 0.0f, true), 0.0f)) {
        std::cerr << "HUD anchoring changed another aspect mode or an offscreen camera.\n";
        return 1;
    }
    return 0;
}
