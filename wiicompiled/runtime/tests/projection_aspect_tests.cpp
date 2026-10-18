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
    return 0;
}
