#pragma once
#include <cmath>

namespace aurora::gx {
struct ProjectionAspectScale { float horizontal = 1.0f, vertical = 1.0f; };

// Preserve geometry and the complete HUD when adapting the game's 16:9 cameras.
// Wider screens gain horizontal view; 16:10 gains vertical view with the same width.
inline ProjectionAspectScale projection_aspect_scale(float source, float target, bool screenSized) {
  if (!screenSized || !std::isfinite(source) || !std::isfinite(target) ||
      source <= 1.68f || source >= 1.88f || target <= 0.0f) return {};
  if (target < source) return {1.0f, target / source};
  return {source / target, 1.0f};
}
} // namespace aurora::gx
